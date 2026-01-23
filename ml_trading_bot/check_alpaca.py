import ccxt
from config import API_KEY, SECRET_KEY

def diagnostic():
    print("🔍 Starting Alpaca Diagnostic (Bypassing Status Check)...")
    
    exchange = ccxt.alpaca({
        'apiKey': API_KEY,
        'secret': SECRET_KEY,
    })

# Use THIS structure to satisfy the CCXT internal 'trader' check
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
    try:
        # TEST 1: Skip Status (Not supported by Alpaca CCXT)
        # print("📡 Testing Connectivity...")
        
        # TEST 2: Account Access (THIS IS THE BIG ONE)
        print("👤 Testing Account Access (fetch_balance)...")
        balance = exchange.fetch_balance()
        print(f"✅ Account Connected! Cash Balance: {balance['free'].get('USD', 0)}")

        # TEST 3: Market Data Access
        print("📈 Testing Market Data (fetch_ohlcv)...")
        ohlcv = exchange.fetch_ohlcv('BTC/USD', '1h', limit=5)
        print(f"✅ Data Received! Rows: {len(ohlcv)}")

    except Exception as e:
        print(f"\n❌ DIAGNOSTIC FAILED!")
        print(f"Error Type: {type(e).__name__}")
        # THIS WILL PRINT THE FULL ERROR STACK IF IT HAPPENS
        import traceback
        traceback.print_exc() 

if __name__ == "__main__":
    diagnostic()