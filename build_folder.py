import os

# -------------------------------------------------------------------------
# MACHINE LEARNING TRADING BOT BUILDER (Alpaca + Scikit-Learn)
# -------------------------------------------------------------------------

base_dir = "ml_trading_bot"
file_contents = {}

# 1. REQUIREMENTS
file_contents["requirements.txt"] = """ccxt
pandas
numpy
scikit-learn
joblib
python-dotenv
"""

# 2. CONFIGURATION (Fixes Alpaca Data Bug)
file_contents["config.py"] = """import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
SYMBOL = os.getenv('SYMBOL', 'BTC/USD')
TIMEFRAME = os.getenv('TIMEFRAME', '1h')

def get_exchange():
    exchange = ccxt.alpaca({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
    })
    
    # CRITICAL: Force Paper Trading Mode
    exchange.set_sandbox_mode(True)
    
    # CRITICAL: Fix "Empty Data" bug by forcing the correct feed
    # 'us' for Crypto, 'sip' or 'iex' for Stocks
    if 'BTC' in SYMBOL or 'ETH' in SYMBOL:
        exchange.options['defaultDataFeed'] = 'us'
    else:
        exchange.options['defaultDataFeed'] = 'sip'
        
    return exchange
"""

# 3. DATA LOADER (Robust Error Handling)
file_contents["data_loader.py"] = """import pandas as pd
import time
from config import get_exchange

def get_historical_data(symbol, timeframe, limit=500):
    exchange = get_exchange()
    print(f"🔄 Fetching {limit} candles for {symbol}...")
    
    try:
        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        # Check for empty data BEFORE processing
        if not ohlcv or len(ohlcv) == 0:
            print(f"⚠️  No data returned. Waiting for market or check symbol format.")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        
        # Ensure we have enough rows for ML lags
        if len(df) < 50:
            print(f"⚠️  Not enough data ({len(df)} rows) to train model.")
            return None
            
        return df.sort_values('ts').reset_index(drop=True)

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None
"""

# 4. STRATEGY (Random Forest Logic)
file_contents["strategy.py"] = """import pandas as pd
from sklearn.ensemble import RandomForestRegressor

def prepare_ml_data(df, lags=5):
    # 1. Feature Engineering: Create "Lags" (Price 1h ago, 2h ago...)
    df = df.copy()
    for i in range(1, lags + 1):
        df[f'lag_{i}'] = df['close'].shift(i)
    
    # 2. Add Moving Average as a feature
    df['ma_20'] = df['close'].rolling(window=20).mean()
    
    # 3. Target: We want to predict the *next* close
    df['target'] = df['close'].shift(-1)
    
    # 4. Drop NaNs created by shifting/rolling
    return df.dropna()

def get_ml_prediction(df):
    # Prepare data
    data = prepare_ml_data(df)
    
    if data.empty:
        return None, None

    # Define Features (X) and Target (y)
    feature_cols = [c for c in data.columns if 'lag' in c or 'ma' in c]
    X = data[feature_cols]
    y = data['target']
    
    # Train Model (Retrains every loop - "Walk Forward")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Predict for the MOST RECENT candle
    # We use the last row of features to predict the "future"
    last_features = X.iloc[[-1]] 
    prediction = model.predict(last_features)[0]
    
    return prediction, last_features
"""

# 5. MAIN BOT LOOP (The Coordinator)
file_contents["main.py"] = """import time
import os
from config import SYMBOL, TIMEFRAME, get_exchange
from data_loader import get_historical_data
from strategy import get_ml_prediction

def run_bot():
    print(f"--- 🤖 ML TRADING BOT STARTED ({SYMBOL}) ---")
    exchange = get_exchange()
    
    # Verify Connection
    try:
        bal = exchange.fetch_balance()['free']['USD']
        print(f"✅ Connected to Alpaca. Balance: ${bal:.2f}")
    except Exception as e:
        print(f"❌ Auth Error: Check .env keys. {e}")
        return

    while True:
        print("\\n⏳ Analying Market...")
        
        # 1. Fetch Data
        df = get_historical_data(SYMBOL, TIMEFRAME, limit=500)
        
        if df is None:
            print("SLEEPING: Waiting for data availability...")
            time.sleep(60)
            continue
            
        # 2. Get Prediction
        current_price = df['close'].iloc[-1]
        predicted_price, _ = get_ml_prediction(df)
        
        if predicted_price is None:
            print("⚠️  Not enough data to generate features.")
            time.sleep(60)
            continue
            
        # 3. Calculate Signal
        percent_diff = ((predicted_price - current_price) / current_price) * 100
        print(f"💲 Price: {current_price:.2f} | 🔮 Prediction: {predicted_price:.2f} ({percent_diff:+.2f}%)")
        
        # 4. Execution Logic (Threshold: 0.5% predicted move)
        if percent_diff > 0.5:
            print("🚀 BUY SIGNAL: Strong Uptrend Predicted")
            # exchange.create_market_buy_order(SYMBOL, 0.01) 
        elif percent_diff < -0.5:
            print("📉 SELL SIGNAL: Strong Downtrend Predicted")
            # exchange.create_market_sell_order(SYMBOL, 0.01)
        else:
            print("zzz No clear trend (Hold)")

        # Wait for next candle
        print("Waiting 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    run_bot()
"""

# 6. ENV FILE (Template)
file_contents[".env"] = """ALPACA_API_KEY=paste_key_here
ALPACA_SECRET_KEY=paste_secret_here
SYMBOL=BTC/USD
TIMEFRAME=1h
"""

# --- BUILDER LOGIC ---
def build():
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    for filename, content in file_contents.items():
        filepath = os.path.join(base_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created: {filepath}")

    print("\n🎉 BUILD COMPLETE.")
    print(f"1. cd {base_dir}")
    print("2. pip install -r requirements.txt")
    print("3. Edit .env with your Alpaca Keys")
    print("4. python main.py")

if __name__ == "__main__":
    build()