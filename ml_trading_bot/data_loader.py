import pandas as pd
import time
from config import get_exchange

def get_historical_data(symbol, timeframe, limit=500):
    exchange = get_exchange()
    
    # Calculate "since" as 48 hours ago in milliseconds
    # (2 days * 24 hours * 60 mins * 60 secs * 1000 ms)
    since = exchange.milliseconds() - (48 * 60 * 60 * 1000)
    
    print(f"🔄 Requesting history for {symbol} since 48h ago...")
    
    try:
        # Pass the 'since' parameter to force the API to look back in time
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        
        if not ohlcv or len(ohlcv) < 5:
            print(f"⚠️ Still getting low data ({len(ohlcv)} rows).")
            print("TIP: If you just created your Alpaca account, it can take 1 hour for historical data to activate.")
            return None

        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
        
        print(f"✅ Success: Received {len(df)} rows.")
        return df.sort_values('ts').reset_index(drop=True)

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None