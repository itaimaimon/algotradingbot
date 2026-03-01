import yfinance as yf
import pandas as pd
import numpy as np
from config import SYMBOL, TIMEFRAME

def get_historical_data(symbol=SYMBOL, timeframe=TIMEFRAME, target_rows=730*24):
    """
    Fetches stock data and calculates equity-specific quant features.
    Note: yfinance limits 1h data to the last 730 days.
    """
    print(f"📥 Fetching {timeframe} of {target_rows} data for {symbol}...")
    
    interval=timeframe
    period = str(int(target_rows/24)) + "d"
    # 1. Fetch Target Stock
    df = yf.download(symbol, interval=interval, period=period, progress=False)
    
    if df.empty:
        print(f"❌ Failed to fetch data for {symbol}")
        return None

    # Flatten multi-index columns if yfinance returns them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # Standardize column names to lowercase to match your crypto setup
    df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
    
    # 2. Fetch SPY for Market Context


    #yf
    
    print("📈 Fetching SPY context...")
    df_spy = yf.download("SPY", interval=interval, period=period, progress=False)
    if isinstance(df_spy.columns, pd.MultiIndex):
        df_spy.columns = df_spy.columns.get_level_values(0)
    
    # 3. Feature Engineering
    print("⚙️ Calculating Equity Features...")
    
    # --- Base Features ---
    # Safe division for range
    range_span = (df['high'] - df['low']).replace(0, 1e-9)
    df['range'] = range_span / df['close']
    df['volume_change'] = df['volume'].pct_change()
    df['returns']=df['close'].pct_change()

    # --- Equity Specific Context ---
    # Overnight Gap (How much did it jump from yesterday's close?)
    df['prev_close'] = df['close'].shift(1)
    df['gap_pct'] = (df['open'] - df['prev_close']) / df['prev_close'].replace(0, 1e-9)
    
    # Intraday Order Flow (Close location weighted by relative volume)
    close_location = (df['close'] - df['low']) / range_span
    buying_intensity = (close_location * 2) - 1  # Scales to [-1, 1]
    vol_norm = df['volume'] / df['volume'].rolling(14).mean().replace(0, 1e-9)
    df['order_flow'] = buying_intensity * vol_norm
    
    # Market Correlation (SPY)
    merged = pd.DataFrame()
    merged['close'] = df['close']
    merged['close_spy']=df_spy["close"]
    df['spy_corr'] = merged['close'].rolling(window=14).corr(merged['close_spy'])
    df['spy_corr'].fillna(0.8, inplace=True) # Assume high correlation early on
    
    # Time of Day Filter (Hour)
    df['hour'] = df.index.hour

    # Clean up NaN values caused by rolling windows and shifts
    df.dropna(inplace=True)
    df.drop(columns=['prev_close'], inplace=True, errors='ignore')
    
    print(f"✅ Dataset ready: {len(df)} rows.")
    return df

# Quick test
if __name__ == "__main__":
    test_df = get_historical_data("AAPL")
    print(test_df[['close', 'gap_pct', 'order_flow', 'spy_corr']].head())