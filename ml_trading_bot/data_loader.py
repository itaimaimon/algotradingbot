# data_loader.py 
# just uses alpaca for time being
from data_loader_alpaca import get_crypto_data, get_stock_data
from config import SYMBOL, TIMEFRAME, IS_CRYPTO

def get_historical_data(symbol=SYMBOL, timeframe=TIMEFRAME, is_crypto=IS_CRYPTO, target_rows=1000):
    if is_crypto:
        return get_crypto_data(symbol,timeframe,target_rows)
    else:
        return get_stock_data(symbol,timeframe,target_rows)
    
