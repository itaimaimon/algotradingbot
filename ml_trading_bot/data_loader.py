# data_loader.py
import ccxt
import pandas as pd
import time
from config import SYMBOL, TIMEFRAME, API_KEY, SECRET_KEY

def get_exchange():
    exchange= ccxt.alpaca({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
    })
    if API_KEY.startswith('PK'):
        print("📝 Detected PAPER keys.")
        exchange.urls['api'] = {
            'trader': 'https://paper-api.alpaca.markets', # CCXT needs this key!
            'market': 'https://data.alpaca.markets'
        }
    else:
        print("💰 Detected LIVE keys.")
        exchange.urls['api'] = {
            'trader': 'https://api.alpaca.markets',
            'market': 'https://data.alpaca.markets'
        }
    return exchange    
    
import datetime

import datetime
import time # Ensure time is imported

def get_historical_data(symbol, timeframe, target_rows=1000):
    exchange = get_exchange()
    
    # 1. SETUP: Start 60 days ago to be safe
    # This ensures we have plenty of runway to find 1000 rows
    start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)
    since = int(start_time.timestamp() * 1000)
    
    print(f"🔄 Fetching data for {symbol} starting from {start_time.strftime('%Y-%m-%d')}...")

    all_ohlcv = []
    
    while len(all_ohlcv) < target_rows:
        try:
            # 2. FETCH: Ask for 1000 rows at a time
            # Alpaca v2 allows larger limits, which speeds this up
            batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            
            if not batch or len(batch) == 0:
                print("🏁 API returned no more data.")
                break
            
            # 3. COLLECT
            all_ohlcv.extend(batch)
            print(f"   📥 Collected {len(batch)} rows. Total: {len(all_ohlcv)}")
            
            # 4. UPDATE 'SINCE': Move the pointer forward
            last_timestamp = batch[-1][0]
            
            # Safety Check: If we didn't move forward, stop (prevent infinite loop)
            if last_timestamp == since:
                print("⚠️ Timestamp didn't advance. Stopping.")
                break
                
            since = last_timestamp + 1 # Start next batch 1ms after the last candle
            
            time.sleep(0.2) # Friendly rate limit

        except Exception as e:
            print(f"⚠️ Data Fetch Error: {e}")
            break

    if not all_ohlcv:
        return None

    # 5. FORMAT
    df = pd.DataFrame(all_ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df = df.drop_duplicates(subset=['ts']).sort_values('ts').reset_index(drop=True)
    
    # Trim to exactly target_rows if we got too many
    if len(df) > target_rows:
        df = df.iloc[-target_rows:].reset_index(drop=True)
    
    print(f"✅ Final Dataset: {len(df)} rows ready for ML.")
    return df