import os
import ccxt
from dotenv import load_dotenv

load_dotenv()
IS_CRYPTO=os.getenv("IS_CRYPTO")
IS_CRYPTO=bool(IS_CRYPTO=="True")
API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
SYMBOL = os.getenv('SYMBOL')
TIMEFRAME = os.getenv('TIMEFRAME')

def get_timeframe_seconds():
    unit = TIMEFRAME[-1]
    amount = int(TIMEFRAME[:-1])
    if unit == 'm': return amount * 60
    if unit == 'h': return amount * 3600
    if unit == 'd': return amount * 86400
    return 60 # Default

def get_exchange():
    exchange = ccxt.alpaca({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
        'enableRateLimit': True,
        'options': {'adjustForTimeDifference': True}
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
