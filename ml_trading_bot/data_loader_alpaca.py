

# data_loader.py

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from datetime import datetime, timedelta, timezone
import pandas as pd
import ccxt
import pandas as pd
import time
from config import API_KEY, SECRET_KEY, TIMEFRAME
import time # Ensure time is imported



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




def get_stock_data(symbol, timeframe, target_rows=1000):
    # 1. Initialize the STOCK client (not crypto)
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    
    # 2. Set timeframe (Timezone-aware start is required) (1m or 1h)(1h default) 
    if timeframe == "1m":
        days_back = int(target_rows/(4*60))
        start_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=start_time,
            adjustment='all', # Corrects for stock splits automatically
            feed=DataFeed.IEX  # Use IEX for the free tier
        )
        request_params_spy = StockBarsRequest(
            symbol_or_symbols="SPY",
            timeframe=TimeFrame.Minute,
            start=start_time,
            adjustment='all', # Corrects for stock splits automatically
            feed=DataFeed.IEX  # Use IEX for the free tier
        )
    #default 1h timeframe
    else:

        days_back = int(target_rows/5)
        start_time = datetime.now(timezone.utc) - timedelta(days=days_back)
    
        # 3. Request parameters
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start_time,
            adjustment='all', # Corrects for stock splits automatically
            feed=DataFeed.IEX  # Use IEX for the free tier
        )
        request_params_spy = StockBarsRequest(
            symbol_or_symbols="SPY",
            timeframe=TimeFrame.Hour,
            start=start_time,
            adjustment='all', # Corrects for stock splits automatically
            feed=DataFeed.IEX  # Use IEX for the free tier
        )
    
    
    # 4. Fetch and Convert to DataFrame
    bars = client.get_stock_bars(request_params)
    df = bars.df
    
    bars_spy= client.get_stock_bars(request_params_spy)
    spy=bars_spy.df
    df = df.reset_index(level=0, drop=True) # Removes the 'symbol' index level
    df.index = df.index.tz_localize(None)    # Removes timezone for easier math
    spy = spy.reset_index(level=0, drop=True) # Removes the 'symbol' index level
    spy.index = spy.index.tz_localize(None)    # Removes timezone for easier math
    
    df= df.join(spy,rsuffix='_spy')

    # Standardize format for your model

    if len(df) > target_rows:
        df = df.iloc[-target_rows:]
    
    print(f"📊 Successfully loaded {len(df)} bars for {symbol}")

    return df

def get_crypto_data(symbol, timeframe, target_rows=1000):
    exchange = get_exchange()
    
    # 1. SETUP: Start 60 days ago to be safe
    # This ensures we have plenty of runway to find 1000 rows
    start_time = datetime.now(timezone.utc) - timedelta(days=int(target_rows/24))
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

    start_time = datetime.now(timezone.utc) - timedelta(days=int(target_rows/24))
    since = int(start_time.timestamp() * 1000)
    
    print(f"🔄 Fetching data for BTC/USD starting from {start_time.strftime('%Y-%m-%d')}...")
    BTC_all_ohlcv= []
    batch= []
    while len(BTC_all_ohlcv) < target_rows:
        try:
            # 2. FETCH: Ask for 1000 rows at a time
            # Alpaca v2 allows larger limits, which speeds this up
            batch = exchange.fetch_ohlcv("BTC/USD", timeframe, since=since, limit=1000)
            
            if not batch or len(batch) == 0:
                print("🏁 API returned no more data.")
                break
            
            # 3. COLLECT
            BTC_all_ohlcv.extend(batch)
            print(f"   📥 Collected {len(batch)} rows. Total: {len(BTC_all_ohlcv)}")
            
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

    # 5. FORMAT
    df = pd.DataFrame(all_ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df=df.set_index("ts")

    df_btc = pd.DataFrame(BTC_all_ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df_btc['ts'] = pd.to_datetime(df_btc['ts'], unit='ms')
    df_btc=df_btc.set_index('ts')

    df= df.join(df_btc, rsuffix= '_btc')
    
    # Trim to exactly target_rows if we got too many
    if len(df) > target_rows:
        df = df.iloc[-target_rows:]
    
    print(f"✅ Final Dataset: {len(df)} rows ready for ML.")
    #df.to_csv("btc_hourly.csv", index = False)
    return df

if __name__ == "__main__":
    test_df = get_crypto_data("ETH/USD","1h")
    print(test_df[['close', 'close_btc']].head(111))