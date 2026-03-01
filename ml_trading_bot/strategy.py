
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
from datetime import datetime, timedelta
from config import SYMBOL, TIMEFRAME, IS_CRYPTO
import pandas as pd
import numpy as np
import ccxt
import yfinance as yf
import random


MODEL_CONSTRUCTED = False
LAST_TRAIN_TIME = None

MODEL_PATH = "trading_model.joblib"


def add_equity_context(df,symbol =SYMBOL,timeframe= TIMEFRAME):    
    # Standardize column names to lowercase to match your crypto setup

    # 3. Feature Engineering
    print("⚙️ Calculating Equity Features...")
    
    # --- Base Features ---
    # Safe division for range


    # --- Equity Specific Context ---
    # Overnight Gap (How much did it jump from yesterday's close?)
    df['prev_close'] = df['close'].shift(1)
    df['gap_pct'] = (df['open'] - df['prev_close']) / df['prev_close'].replace(0, 1e-9)
    
    # Intraday Order Flow (Close location weighted by relative volume)
    range_span = (df['high'] - df['low']).replace(0, 1e-9)
    close_location = (df['close'] - df['low']) / range_span
    buying_intensity = (close_location * 2) - 1  # Scales to [-1, 1]
    vol_norm = df['volume'] / df['volume'].rolling(14).mean().replace(0, 1e-9)
    df['order_flow'] = buying_intensity * vol_norm
    
    # Market Correlation (SPY)

    # Calculate 24-period Rolling Correlation
    if 'SPY' in symbol:
        df['spy_corr'] = 1.0 # Placeholder for BTC itself
    else:
        df['spy_corr'] = df['close'].rolling(window=24).corr(df['close_spy'])
            
    # Fill NaN (first 24 rows) with 0.8 (assume high correlation initially)
    df['spy_corr']=df['spy_corr'].fillna(0.8)
    
    # Time of Day Filter (Hour)
    df['hour'] = df.index.hour

    # Clean up NaN values caused by rolling windows and shifts
    df=df.dropna()
    
    print(f"✅ Dataset ready: {len(df)} rows.")
    return df

def add_crypto_context(df, symbol=SYMBOL, timeframe=TIMEFRAME, exchange=None):
    """
    Adds 3 'Level 2' features:
    1. pseudo_order_flow: Estimates Buy/Sell pressure from candle shape + volume.
    2. daily_trend: The slope of the 24-hour trend (context).
    3. btc_corr: Correlation with Bitcoin (market beta).
    """
    #print("🧠 Injecting Advanced Contextual Features...")

    # --- 1. PSEUDO ORDER FLOW (The "Fight") ---
    # Logic: Volume * (Where did we close relative to the range?)
    # -1.0 = Max Selling Pressure (Closed on Low)
    # +1.0 = Max Buying Pressure (Closed on High)
    
    # Avoid division by zero
    range_span = (df['high'] - df['low']).replace(0, 1e-9)
    close_location = (df['close'] - df['low']) / range_span
    
    # Scale from [0, 1] to [-1, 1]
    buying_intensity = (close_location * 2) - 1 
    
    # Weigh it by Volume (The "Force" of the move)
    # We normalize volume first so it doesn't explode the scale
    vol_norm = df['volume'] / df['volume'].rolling(24).mean()
    df['order_flow'] = buying_intensity * vol_norm


    # --- 2. MULTI-TIMEFRAME CONTEXT (The "Daily Trend") ---
    # instead of fetching new data, we mathematically derive the Daily Trend
    # from the Hourly data (24 hours ago).
    
    # Is the price above the 24h Moving Average?
    df['daily_ma'] = df['close'].rolling(window=24).mean()
    df['daily_trend'] = (df['close'] - df['daily_ma']) / df['daily_ma']
    
    
    # --- 3. MARKET CORRELATION (The "BTC Factor") ---
    # We must fetch BTC data to compare.
    # Note: If you are trading BTC, this feature is redundant (corr = 1.0).
    
    if 'BTC' in symbol:
        df['btc_corr'] = 1.0 # Placeholder for BTC itself
    else:
        
        # Calculate 24-period Rolling Correlation
        df['btc_corr'] = df['close'].rolling(window=24).corr(df['close_btc'])
            
        # Fill NaN (first 24 rows) with 0.8 (assume high correlation initially)
        df['btc_corr']=df['btc_corr'].fillna(0.8)

    # Cleanup
    df=df.drop(columns=['daily_ma'], errors='ignore')
    return df

def add_indicators(df):
    """
    Takes raw OHLVC data and adds technical indicators.
    Used by both Training and Live Prediction to ensure consistency.
    """
    data = df.copy()
    
    # Avoid division by zero errors
    epsilon = 1e-9

    # --- Basic Math ---
    data['returns'] = data['close'].pct_change()
    data['range'] = (data['high'] - data['low']) / data['close']
    data['volume_change'] = data['volume'].pct_change()

    # --- RSI (Relative Strength Index) ---
    window_rsi = 14
    delta = data['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window_rsi).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window_rsi).mean()
    rs = gain / (loss + epsilon)
    data['rsi'] = 100 - (100 / (1 + rs))

    # --- ADX (Average Directional Index) ---
    # Simplified calculation for speed
    window_adx = 14
    data['tr'] = np.maximum(data['high'] - data['low'], 
                            np.maximum(abs(data['high'] - data['close'].shift(1)), 
                                       abs(data['low'] - data['close'].shift(1))))
    data['atr'] = data['tr'].rolling(window=window_adx).mean()
    
    data['plus_dm'] = np.where((data['high'] - data['high'].shift(1)) > (data['low'].shift(1) - data['low']), 
                               data['high'] - data['high'].shift(1), 0)
    data['plus_dm'] = np.where(data['plus_dm'] < 0, 0, data['plus_dm'])
    
    data['minus_dm'] = np.where((data['low'].shift(1) - data['low']) > (data['high'] - data['high'].shift(1)), 
                                data['low'].shift(1) - data['low'], 0)
    data['minus_dm'] = np.where(data['minus_dm'] < 0, 0, data['minus_dm'])

    data['plus_di'] = 100 * (data['plus_dm'].rolling(window=window_adx).mean() / (data['atr'] + epsilon))
    data['minus_di'] = 100 * (data['minus_dm'].rolling(window=window_adx).mean() / (data['atr'] + epsilon))
    
    dx = 100 * abs(data['plus_di'] - data['minus_di']) / (data['plus_di'] + data['minus_di'] + epsilon)
    data['adx'] = dx.rolling(window=window_adx).mean()

    # --- Volatility ---
    data['volatility'] = data['returns'].rolling(window=20).std()

    # --- Relative Volume ---
    # Compares current volume to the 20-period average
    baseline_vol = data['volume'].shift(1).rolling(window=20).mean()
    data['relative_volume'] = data['volume'] / (baseline_vol + epsilon)
    data['relative_volume'] = data['relative_volume'].fillna(0)

    # --- Distance from Mean ---
    # Z-Score style distance
    ma_window = 20
    rolling_mean = data['close'].rolling(window=ma_window).mean()
    rolling_std = data['close'].rolling(window=ma_window).std()
    data['dist_from_mean'] = (data['close'] - rolling_mean) / (rolling_std + epsilon)

    #Replace any math errors (inf) with NaN
    data=data.replace([np.inf, -np.inf], np.nan)
    
    # Fill the very first rows (which are NaN due to shifting) with 0
    # This prevents dropna() from eating your entire 200-row window
    data['dist_from_mean'] = data['dist_from_mean'].fillna(0)
    if IS_CRYPTO:
        data = add_crypto_context(data)
    else:
        data = add_equity_context(data)
    return data

def train_master_model(df,add_indicators_happened=False, random_seed=42, active_features= ['returns', 'range', 'rsi', 'volatility','adx','volume_change', 'relative_volume','dist_from_mean']):
    print("made new model")
    global MODEL_CONSTRUCTED
    MODEL_CONSTRUCTED = True
    global LAST_TRAIN_TIME 
    LAST_TRAIN_TIME = datetime.now()
    # 1. Warm-up Check
    
    if len(df) < 50:
        return "HOLD"
    data=df.copy()
    if not add_indicators_happened:
        data=add_indicators(df)
    
    
    # Target: 1 if next price is higher, else 0
    threshold = 0.00
    future_returns = data['close'].pct_change().shift(-1)
    
    data['target'] = (future_returns > threshold).astype(int)

    data = data.dropna()

    # Safety: ensure we still have data after dropping NaNs
    if len(data) < 30:
        return 

    # 3. Define Features List (Matches your error context)
    #features = ['returns', 'range', 'rsi', 'volatility','adx','volume_change', 'relative_volume','dist_from_mean']
    features = active_features
    X = data[features]
    y = data['target']

    # 4. Train
    # We fit on everything except the last row
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=random_seed)
    model.fit(X.iloc[:-1], y.iloc[:-1])


    #5. Save to disk
    joblib.dump(model, MODEL_PATH)
    print(f"💾 Model saved to {MODEL_PATH}")
    return model

    #optional: model importance report if desired 
    """
    if np.random.random() < .1: # Prints roughly every 100 bars
        importances = model.feature_importances_
        print("\n--- 🧠 Model Intelligence Report ---")
        for name, imp in zip(features, importances):
            print(f"{name.upper()}: {imp:.2%}")
        
        # Save a plot to a file just in case you want to see it
        plt.figure(figsize=(8,4))
        plt.barh(features, importances)
        plt.title("Feature Importance")
        plt.show()
        plt.savefig("feature_importance.png") # This creates a file in your folder
        plt.close()
    """
def generate_signal(df,add_indicators_happened=False,active_features=['returns', 'range', 'rsi', 'volatility','adx','volume_change', 'relative_volume','dist_from_mean'],bigdf=None):
    #load model
    global MODEL_PATH
        #1. add indicators and fix Nans
    global LAST_TRAIN_TIME
    data= df.copy()
    if not add_indicators_happened:
        data = add_indicators(df)
    data=data.fillna(0)
 
    if random.randint(1,100)==1 or datetime.now()-LAST_TRAIN_TIME > timedelta(minutes =10):
        train_master_model(df,active_features=active_features,add_indicators_happened=True)   
    
    try:
        model = joblib.load(MODEL_PATH)
    except:
        #only works if big dataframe is set ie bigdf!=None
        print("⚠️ No model found! Need to train first.")
        train_master_model(df,active_features=active_features,add_indicators_happened=True)   
        model = joblib.load(MODEL_PATH)

    # 2. Predict
    latest_features = data[active_features].iloc[[-1]]
    
    # robust unpacking: we don't assume 2 classes, we just want the probability of "1" (Up)
    try:
        # predict_proba returns a list of probabilities for each class
        # We take [0] to get the first row, and use max() or specific index
        probs = model.predict_proba(latest_features)[0]
        # If model has 2 classes (0 and 1), probs has length 2.
        # probs[1] is the probability of going UP.
        prob_up = probs[1]
        print(prob_up)
        
    except IndexError:
        return "HOLD"
    
    # Conviction and Contrarian logic
    current_adx = data['adx'].iloc[-1]
    
    # THRESHOLD for "Strong Trend"
    ADX_THRESHOLD = -100000
    
    # HIGH CONFIDENCE BAR (To beat fees)
    CONFIDENCE = 0.5

    if current_adx > ADX_THRESHOLD:
        # === TRENDING REGIME (Normal Logic) ===
        # If trend is strong, TRUST the model direction.
        if prob_up > CONFIDENCE:
            print("buy")
            return "BUY"
        elif prob_up < (1 - CONFIDENCE):
            print("sell")        
            return "SELL"
    else:
        # === RANGING REGIME (Contrarian Logic) ===
        # If trend is weak, FADE the model direction.
        # This is the "Switch" that gave you the +0.54 Sharpe
        if prob_up > CONFIDENCE:
            print("sell")
            return "SELL" # Model screams UP -> We sell top
        elif prob_up < (1 - CONFIDENCE):
            print("buy")
            return "BUY"  # Model screams DOWN -> We buy dip

    return "HOLD"
