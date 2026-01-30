import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import matplotlib.pyplot as plt
def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_adx(df, window=14):
    """
    Calculates the Average Directional Index (ADX).
    ADX measures trend STRENGTH, not direction.
    ADX > 25 usually implies a strong trend.
    ADX < 25 usually implies a ranging market.
    """
    data = df.copy()
    data['tr0'] = abs(data['high'] - data['low'])
    data['tr1'] = abs(data['high'] - data['close'].shift(1))
    data['tr2'] = abs(data['low'] - data['close'].shift(1))
    data['tr'] = data[['tr0', 'tr1', 'tr2']].max(axis=1)

    data['pdm'] = 0.0
    data['ndm'] = 0.0
    
    # Directional Movement
    data.loc[(data['high'] - data['high'].shift(1)) > (data['low'].shift(1) - data['low']), 'pdm'] = \
        (data['high'] - data['high'].shift(1)).clip(lower=0)
    data.loc[(data['low'].shift(1) - data['low']) > (data['high'] - data['high'].shift(1)), 'ndm'] = \
        (data['low'].shift(1) - data['low']).clip(lower=0)

    # Smooth the TR, +DM, -DM
    alpha = 1 / window
    tr_smooth = data['tr'].ewm(alpha=alpha, adjust=False).mean()
    pdm_smooth = data['pdm'].ewm(alpha=alpha, adjust=False).mean()
    ndm_smooth = data['ndm'].ewm(alpha=alpha, adjust=False).mean()

    # Calculate DI+ and DI-
    pdi = 100 * (pdm_smooth / tr_smooth)
    ndi = 100 * (ndm_smooth / tr_smooth)
    
    # Calculate DX and ADX
    dx = 100 * (abs(pdi - ndi) / (pdi + ndi))
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    
    return adx


def generate_signal(df,active_features= ['returns', 'range', 'rsi', 'volatility','adx','volume_change', 'relative_volume','dist_from_mean']):
    # 1. Warm-up Check
    if len(df) < 50:
        return "HOLD"

    data = df.copy()
    
    # 2. Calculate All Features
    data['returns'] = data['close'].pct_change()
    data['range'] = (data['high'] - data['low']) / data['close']
    data['rsi'] = calculate_rsi(data['close'])
    data['volatility'] = data['returns'].rolling(window=10).std()
    data['adx'] = calculate_adx(data)
   
    # --- 1. DATA-EFFICIENT DIST FROM MEAN ---
    # We use a 20-period window. This is better for 1h charts 
    # and leaves 180 rows of data for the model to learn from.
    ma_window = 20
    
    # We do NOT use shift(1) here for the Z-score calculation, 
    # as we want to know the current price's position relative to the current mean.
    rolling_mean = data['close'].rolling(window=ma_window).mean()
    rolling_std = data['close'].rolling(window=ma_window).std()
    
    # Calculate Z-score: (Price - Mean) / StdDev
    data['dist_from_mean'] = (data['close'] - rolling_mean) / (rolling_std + 1e-9)

    # --- 3. THE "CLEANING" STEP (Critical) ---
    # 1. Replace any math errors (inf) with NaN
    data.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # 2. Fill the very first rows (which are NaN due to shifting) with 0
    # This prevents dropna() from eating your entire 200-row window
    data['dist_from_mean'] = data['dist_from_mean'].fillna(0)


    # Instead of raw volume, use the percentage change
    data['volume_change'] = data['volume'].pct_change()
 
    #"Relative Volume" (Current volume vs. 24-hour average)
    #Broken: data['relative_volume'] = data['volume'] / data['volume'].rolling(window=24).mean()
    
    # 1. Calculate the baseline from the PREVIOUS 24 hours (excluding now)
    # We shift by 1 so the average at index 'i' is based on 'i-1' down to 'i-24'
    baseline_volume = data['volume'].shift(1).rolling(window=24).mean()

    # 2. Calculate Relative Volume
    # Add a tiny epsilon (1e-9) to the denominator just to prevent "Division by Zero" crashes
    data['relative_volume'] = data['volume'] / (baseline_volume + 1e-9)

    # 3. Handle the NaN values created by the shift and rolling window
    data['relative_volume'] = data['relative_volume'].fillna(0)
        
        
    
    # Target: 1 if next price is higher, else 0
    data['target'] = (data['close'].shift(-1) > data['close']).astype(int)
    
    data = data.dropna()

    # Safety: ensure we still have data after dropping NaNs
    if len(data) < 30:
        return "HOLD"

    # 3. Define Features List (Matches your error context)
    #features = ['returns', 'range', 'rsi', 'volatility','adx','volume_change', 'relative_volume','dist_from_mean']
    features = active_features
    X = data[features]
    y = data['target']

    # 4. Train
    # We fit on everything except the last row
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X.iloc[:-1], y.iloc[:-1])
    
    if np.random.random() < .1: # Prints roughly every 100 bars
        importances = model.feature_importances_
        print("\n--- 🧠 Model Intelligence Report ---")
        for name, imp in zip(features, importances):
            print(f"{name.upper()}: {imp:.2%}")
        """
        # Save a plot to a file just in case you want to see it
        plt.figure(figsize=(8,4))
        plt.barh(features, importances)
        plt.title("Feature Importance")
        plt.show()
        plt.savefig("feature_importance.png") # This creates a file in your folder
        plt.close()
        """
    # 5. Predict
    latest_features = X.iloc[[-1]]
    
    # robust unpacking: we don't assume 2 classes, we just want the probability of "1" (Up)
    try:
        # predict_proba returns a list of probabilities for each class
        # We take [0] to get the first row, and use max() or specific index
        probs = model.predict_proba(latest_features)[0]
        
        # If model has 2 classes (0 and 1), probs has length 2.
        # probs[1] is the probability of going UP.
        prob_up = probs[1] if len(probs) > 1 else 0
        
    except IndexError:
        return "HOLD"
    
    current_adx = data['adx'].iloc[-1]
    
    # THRESHOLD for "Strong Trend"
    ADX_THRESHOLD = 25 
    
    # HIGH CONFIDENCE BAR (To beat fees)
    CONFIDENCE = 0.60

    if current_adx > ADX_THRESHOLD:
        # === TRENDING REGIME (Normal Logic) ===
        # If trend is strong, TRUST the model direction.
        if prob_up > CONFIDENCE:
            return "BUY"
        elif prob_up < (1 - CONFIDENCE):
            return "SELL"
    else:
        # === RANGING REGIME (Contrarian Logic) ===
        # If trend is weak, FADE the model direction.
        # This is the "Switch" that gave you the +0.54 Sharpe
        if prob_up > CONFIDENCE:
            return "SELL" # Model screams UP -> We sell top
        elif prob_up < (1 - CONFIDENCE):
            return "BUY"  # Model screams DOWN -> We buy dip

    return "HOLD"
    # 6. Conviction Logic
    # Returns a SINGLE string value to match your backtester
    """
    if prob_up > 0.6:
        return "SELL"
    elif prob_up < 0.4:
        return "BUY"
    else:
        return "HOLD"
    """
