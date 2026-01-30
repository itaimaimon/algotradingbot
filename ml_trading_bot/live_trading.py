import time
import pandas as pd
from datetime import datetime, timedelta
from strategy import generate_signal
# Import your existing tools
from data_loader import get_exchange, get_historical_data 
from config import SYMBOL, TIMEFRAME
import logging
from risk_manager import RiskManager



def get_base_currency(symbol):
    """
    Extracts 'BTC' from 'BTC/USD'. 
    Needed to check balances in CCXT.
    """
    return symbol.split('/')[0]

def get_quote_currency(symbol):
    """
    Extracts 'USD' from 'BTC/USD'.
    """
    return symbol.split('/')[1]

def execute_ccxt_trade(exchange, signal, symbol):
    """
    Executes trades using the CCXT library (same as your data loader).
    """
    base = get_base_currency(symbol) # e.g., BTC
    quote = get_quote_currency(symbol) # e.g., USD
    
    # 1. Fetch current balance
    balance = exchange.fetch_balance()
    
    # Check how much cash (USD) and crypto (BTC) we have
    usd_free = balance[quote]['free']
    crypto_free = balance[base]['free']
    
    print(f"💰 Balance: {usd_free:.2f} {quote} | {crypto_free:.6f} {base}")

    # 2. SELL LOGIC (Exit to Cash)
    # If the signal is SELL, or if we need to flip from Long to Long (rebalance), 
    # we usually sell everything first to simplify the logic.
    if crypto_free > 0.0001: # Threshold to avoid dust errors
        try:
            print(f"📉 Selling all {base}...")
            exchange.create_market_sell_order(symbol, crypto_free)
            print("✅ Sell Order Sent")
            time.sleep(2) # Wait for fill
            # Update balance after sell
            balance = exchange.fetch_balance()
            usd_free = balance[quote]['free']
        except Exception as e:
            print(f"❌ Sell Error: {e}")

    # 3. BUY LOGIC (Enter Long)
    if signal == "BUY":
        try:
            # Calculate how much to buy. We use 95% of cash to save room for fees.
            if usd_free > 10.0: # Minimum 10 USD to trade
                # We need the current price to calculate amount
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                amount_to_buy = (usd_free * 0.95) / current_price
                
                print(f"🚀 Buying {amount_to_buy:.6f} {base} at ~${current_price:.2f}...")
                exchange.create_market_buy_order(symbol, amount_to_buy)
                print("✅ Buy Order Sent")
            else:
                print("⚠️ Not enough cash to buy.")
                
        except Exception as e:
            print(f"❌ Buy Error: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
    )

rm = RiskManager(risk_per_trade=0.02) # Risk 2% per trade

def run_live_bot(active_features):
    logging.info("🤖 Starting ML Trading Bot...")
    exchange = get_exchange()
    
    # Verify Connection
    try:
        bal = exchange.fetch_balance()['free']['USD']
        logging.info(f"connected to Alpaca. Balance: ${bal:.2f}")
    except Exception as e:
        logging.error(f"Auth Error: Check .env keys. {e}")
        return
    rm.set_daily_baseline(bal)

    last_Four_positions = ["HOLD","HOLD","HOLD","HOLD"]
    switch_counter=0
    hold_counter = 0
    
    # Track "Logical" position (what the bot thinks it is doing)
    # logic: if we have crypto > dust, we are "BUY", else "HOLD"
    balance = exchange.fetch_balance()
    base = get_base_currency(SYMBOL)
    if balance.get('total', {}).get(base, 0) > 0.0001:
        current_position = "BUY"
    else:
        current_position = "HOLD"

    while True:
        try:
            current_balance = exchange.fetch_balance()['free']['USD']
            if rm.check_circuit_breaker(current_balance):
                logging.critical(" CIRCUIT BREAKER TRIGGERED! Max daily loss exceeded. Halting.")
                break
            logging.info("\n Analying Market...")


            # 2. WAIT FOR NEXT CANDLE
            # Calculate wait time
            now = datetime.now()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_hour - now).total_seconds() + 10 # 10s buffer
            
            print(f"⏳ Waiting {int(wait_seconds // 60)}m {int(wait_seconds % 60)}s for candle close...")
            time.sleep(wait_seconds)

            # 3. GET DATA (Using your data_loader)
            # We fetch 300 rows to ensure indicators have enough warmup data
            print("📥 Fetching live data...")
            df = get_historical_data(SYMBOL, TIMEFRAME, target_rows=300)
            
            # Data loader returns 'ts' column, we might need to ensure column names match strategy
            # Your data_loader returns: ['ts', 'open', 'high', 'low', 'close', 'volume']
            # This is perfectly compatible with the strategy.
    

            # 4. GET SIGNAL
            raw_signal = generate_signal(df, active_features)
            print(f"🔮 Raw Signal: {raw_signal}")

            # 5. BUFFER LOGIC (n-Signal Confirmation)
            #(3 chosen here but easily extendable down back to two or back up to 4)
            if raw_signal != "HOLD":
                hold_counter = 0
                last_Four_positions[3]=last_Four_positions[2]
                last_Four_positions[2]=last_Four_positions[1]
                last_Four_positions[1]=last_Four_positions[0]
                last_Four_positions[0]=raw_signal
                if raw_signal!= current_position:
                    switch_counter +=1 
                else:
                    switch_counter =0 
            else:
                hold_counter +=1
                if hold_counter == 4:
                    switch_counter=0
                    
                last_Four_positions[3]=last_Four_positions[2]
                last_Four_positions[2]=last_Four_positions[1]
                last_Four_positions[1]=last_Four_positions[0]

            confirmed_signal = current_position
            if switch_counter==3:
                confirmed_signal= raw_signal
                switch_counter = 0
                hold_counter = 0

            print(f"🛡️ Confirmed: {confirmed_signal} | Current Logical Pos: {current_position}")

            # 6. EXECUTE
            if confirmed_signal != current_position:
                print(f"⚡ SWITCHING: {current_position} -> {confirmed_signal}")
                execute_ccxt_trade(exchange, confirmed_signal, SYMBOL)
                current_position = confirmed_signal
            else:
                print("💤 No trade required.")

        except Exception as e:
            print(f"⚠️ Loop Error: {e}")
            time.sleep(60) # Wait 1 min before retrying