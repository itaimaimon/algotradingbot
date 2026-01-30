import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
SYMBOL = os.getenv('SYMBOL')
TIMEFRAME = os.getenv('TIMEFRAME')

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
