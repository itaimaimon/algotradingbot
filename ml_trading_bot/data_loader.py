import pandas as pd
import time
import ccxt
from config import get_exchange

def get_historical_data(symbol, timeframe, limit=1000):
    exchange = get_exchange()
    
    # --- FIX: Look back 30 days instead of 48 hours ---
    # 30 days * 24 hours * 60 min * 60 sec * 1000 ms
    lookback_days = 30
    since = exchange.milliseconds() - (lookback_days * 24 * 60 * 60 * 1000)
    
    print(f"🔄 Requesting {lookback_days} days of history for {symbol}...")
    
    try:
        # We increase the limit to 1000 to ensure we get all 720 hours
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        
        if not ohlcv:
            print("❌ No data received.")
            return None

        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        
        # Filter out incomplete candles (optional, but good for ML)
        df = df.iloc[:-1] 
        
        print(f"✅ Success: Received {len(df)} rows.")
        
        # Verify we have enough data for indicators
        if len(df) < 50:
            print("⚠️ Warning: Data is still short. ML models typically need 200+ rows.")
            
        return df.sort_values('ts').reset_index(drop=True)

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None