import time
import pandas as pd
from datetime import datetime, timezone
import logging
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest,  LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.requests import StockLatestQuoteRequest
import pandas_market_calendars as mcal


from strategy import generate_signal, MODEL_CONSTRUCTED, LAST_TRAIN_TIME, train_master_model
# Import your existing tools
from data_loader_alpaca import get_exchange
from data_loader import get_historical_data 
from config import SYMBOL, TIMEFRAME, get_timeframe_seconds, IS_CRYPTO, API_KEY, SECRET_KEY
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
    
    print(f" Balance: {usd_free:.2f} {quote} | {crypto_free:.6f} {base}")

    # 2. SELL LOGIC (Exit to Cash)
    # If the signal is SELL, or if we need to flip from Long to Long (rebalance), 
    # we usually sell everything first to simplify the logic.
    if crypto_free > 0.0001: # Threshold to avoid dust errors
        try:
            print(f"Selling all {base}...")
            exchange.create_market_sell_order(symbol, crypto_free)
            print(" Sell Order Sent")
            time.sleep(2) # Wait for fill
            # Update balance after sell
            balance = exchange.fetch_balance()
            usd_free = balance[quote]['free']
        except Exception as e:
            print(f"Sell Error: {e}")

    # 3. BUY LOGIC (Enter Long)
    if signal == "BUY":
        try:
            # Calculate how much to buy. We use 95% of cash to save room for fees.
            if usd_free > 10.0: # Minimum 10 USD to trade
                # We need the current price to calculate amount
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                amount_to_buy = (usd_free * 0.95) / current_price
                
                print(f" Buying {amount_to_buy:.6f} {base} at ~${current_price:.2f}...")
                exchange.create_market_buy_order(symbol, amount_to_buy)
                print(" Buy Order Sent")
            else:
                print(" Not enough cash to buy.")
                
        except Exception as e:
            print(f" Buy Error: {e}")



def execute_equities_trade(trading_client, data_client, signal, symbol):
    """
    Executes trades only when the signal deviates from current position.
    signal: 1 (Long), -1 (Short), 0 (Flat)
    """

    # Create a NYSE calendar
    nyse = mcal.get_calendar('NYSE')

    now = datetime.now(timezone.utc)
    schedule = nyse.schedule(start_date=now - pd.Timedelta(days=1), end_date=now + pd.Timedelta(days=1))

    # Check if market is open right now
    is_open = nyse.is_open_now(schedule)

    
    try:
        # --- NEW STEP: THE ZOMBIE SWEEPER ---
        # Cancel any pending orders for AAPL so our shares aren't locked up
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        open_orders = trading_client.get_orders(req)
        
        if open_orders:
            print(f"🧹 Sweeping {len(open_orders)} open/pending order(s) for {symbol}...")
            for order in open_orders:
                trading_client.cancel_order_by_id(order.id)
            
            # Wait 2 seconds for Alpaca's servers to officially unlock the shares
            time.sleep(2) 
            
        # Get Current Position
       
        try:
            position = trading_client.get_open_position(symbol)
            if float(position.current_price) * float(position.qty)>5000:
                if position.side.value == 'long':
                    current_state = "BUY"
                else:
                    current_state = "SELL"
            else:
                current_state = "HOLD"
        except:
            current_state = "HOLD"
        
        account = trading_client.get_account()
            
            # Use 90% of buying power to avoid price-slip rejections
        buying_power = float(account.buying_power) 
        
        if signal == current_state and (buying_power <5000 or signal == "HOLD") :
            print(f"💎 Signal ({signal}) matches current state and little extra capital. No trade needed.")
            return

        # Close Existing Position if mismatch
        if signal != current_state and current_state != "HOLD":
            print(f"📉 Closing {current_state} position to switch states...")
            
            if is_open:
                trading_client.close_position(symbol)
                time.sleep(3) # Wait for settlement
            else: 
                change_position_after_hours(trading_client,data_client, symbol, "CLOSE")
                time.sleep(15) #takes longer

        # Enter New Position
        if signal != "HOLD":

            # Use 90% of buying power to avoid price-slip rejections
            # found after closing current positions
            notional_amt = round(float(account.buying_power)*.9,2)
            side = OrderSide.BUY if signal == "BUY" else OrderSide.SELL

            if is_open: 
                order = MarketOrderRequest(
                symbol=symbol,
                notional=notional_amt,
                side=side,
                time_in_force=TimeInForce.DAY
            )
                trading_client.submit_order(order)
                print("✅ Order Submitted.")
            else: 
                change_position_after_hours(trading_client,data_client, symbol, signal)
 
                print(f"🚀 Entering {side} with ${notional_amt:.2f} after market")
            
    except Exception as e:
        print(f"❌ Execution Error: {e}")


def change_position_after_hours(trading_client,data_client, symbol, signal_or_close ):
    quote_req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quote = data_client.get_stock_latest_quote(quote_req)
            
    current_ask = quote[symbol].ask_price
    current_bid = quote[symbol].bid_price
    
    account = trading_client.get_account()
            
    # Use 90% of buying power to avoid price-slip rejections
    notional_amt = round(float(account.buying_power)*.9,2)
    # 2. Calculate "Marketable" Limit Price (0.1% Buffer)
    if signal_or_close == "BUY":
        # We are willing to pay up to 0.1% more than the current ask
        limit_price = round(current_ask * 1.001, 2)
        side = OrderSide.BUY
    else:
        # We are willing to sell for down to 0.1% less than the current bid
        limit_price = round(current_bid * 0.999, 2)
        side = OrderSide.SELL

    if signal_or_close == "CLOSE":
        position = trading_client.get_open_position(symbol)
        qty= position.qty
    else:
        qty= round(notional_amt/limit_price,2)
        
    order = LimitOrderRequest(
        symbol=symbol,
        limit_price=limit_price, # This is the "Limit"
        qty=qty,
        side=side,
        time_in_force=TimeInForce.DAY
    )

    
    trading_client.submit_order(order)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
    )

rm = RiskManager(risk_per_trade=0.02) # Risk 2% per trade

def run_live_bot(active_features, is_crypto= IS_CRYPTO):
    logging.info("Starting ML Trading Bot...")
    
    

    exchange = get_exchange()
    data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    # Verify Connection
    try:
        bal = exchange.fetch_balance()['free']['USD']
        logging.info(f"connected to Alpaca. Balance: ${bal:.2f}")
    except Exception as e:
        logging.error(f"Auth Error: Check .env keys. {e}")
        return
    rm.set_daily_baseline(bal)

    last_Four_positions = ["HOLD","HOLD","HOLD","HOLD"]
    switch_counter =0
    hold_counter = 0
    
    # Track "Logical" position (what the bot thinks it is doing)
    # logic: if we have crypto > dust, we are "BUY", else "HOLD"

    if is_crypto:
        balance = exchange.fetch_balance()
        base = get_base_currency(SYMBOL)
        
        
        if balance.get('total', {}).get(base, 0) > 0.0001:
            current_position = "BUY"
        else:
            current_position = "HOLD"
    else: 
        position = trading_client.get_open_position(SYMBOL)
        if position.side.value == "long":
            current_position = "BUY"
        elif position.side.value == "short":
            current_position = "SELL"
        else:
            current_position = "HOLD"
    
    interval_sec = get_timeframe_seconds()
    print(f"Bot synchronized to {TIMEFRAME} timeframe.")
    First_check= True
    while True:
        try:
            consecutive_errors = 0 # Reset the error counter
            current_balance = exchange.fetch_balance()['free']['USD']
            if rm.check_circuit_breaker(current_balance):
                logging.critical(" CIRCUIT BREAKER TRIGGERED! Max daily loss exceeded. Halting.")
                break
            logging.info("\n Analying Market...")


            # 2. WAIT FOR NEXT CANDLE
            # Calculate wait time
            now = datetime.now()
            
            current_ts = int(now.timestamp())
            next_boundary = (current_ts // interval_sec + 1) * interval_sec
            sleep_time = (next_boundary - current_ts) + 2 # 2s buffer
            
            if First_check:
                First_check = False
            else:
                print(f"⏳ Next {TIMEFRAME} candle at {datetime.fromtimestamp(next_boundary)}")        
                time.sleep(max(0, sleep_time))

            if MODEL_CONSTRUCTED == False or LAST_TRAIN_TIME is None or (now - LAST_TRAIN_TIME).total_seconds()>3600: 
                print(" Retraining Master Model...")
                big_df = get_historical_data(symbol=SYMBOL, timeframe=TIMEFRAME, target_rows=5000, is_crypto= is_crypto)
                train_master_model(big_df, active_features=active_features)
            
            # 3. GET DATA (Using your data_loader)
            # We fetch 500 rows to ensure indicators have enough warmup data
            print("Fetching live data...")
            current_df = get_historical_data(symbol=SYMBOL, timeframe=TIMEFRAME, target_rows=300)
            # Data loader returns 'ts' column, we might need to ensure column names match strategy
            # Your data_loader returns: ['ts', 'open', 'high', 'low', 'close', 'volume']
            # This is perfectly compatible with the strategy.
    

            # 4. GET SIGNAL
            raw_signal = generate_signal(current_df, active_features=active_features)
            print(f" Raw Signal: {raw_signal}")

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

            print(f" Confirmed: {confirmed_signal} | Current Logical Pos: {current_position}")

            # 6. EXECUTE
            
            account = trading_client.get_account()
            if confirmed_signal != current_position or (float(account.buying_power) > 10000 and confirmed_signal != "HOLD"):
                print(f" SWITCHING: {current_position} -> {confirmed_signal} or just investing more into confirmed signal")
                if is_crypto:
                    execute_ccxt_trade(exchange, confirmed_signal, SYMBOL)
                else:
                    execute_equities_trade(trading_client, data_client, confirmed_signal, SYMBOL)
                current_position = confirmed_signal
            else:                    
                print(" No trade required.")

        except Exception as e:
            error_msg = str(e)
            consecutive_errors += 1
            MAX_ERRORS =10    
            print(f"⚠️ ERROR CAUGHT (Strike {consecutive_errors}/{MAX_ERRORS}): {error_msg}")
                
                # Check if the Circuit Breaker should trip
            if consecutive_errors >= MAX_ERRORS:
                print("🛑 CIRCUIT BREAKER TRIPPED! Too many consecutive errors.")
                print("🔌 Shutting down bot to protect account. Please investigate.")
                sys.exit(1) # This kills the script entirely
                
            # If it's a known network/server error, wait and retry
            if "getaddrinfo" in error_msg or "Max retries" in error_msg or "500" in error_msg or "504" in error_msg:
                print("📶 Network/Server issue detected. Waiting 60 seconds to retry...")
                time.sleep(60)
                
            # If it's an unknown error, it might be a logic bug. 
            # We skip the rest of this hour's cycle and try again on the NEXT hour.
            else:
                print("🐛 Unknown/Logic error detected. Skipping this hour's trade.")
                time.sleep(3600)
FEATURE_SETS = {
    "BTC/USD": ['volume_change', 'relative_volume', 'dist_from_mean', 'order_flow', 'daily_trend'],
    "AAPL": ['returns', 'volatility', 'relative_volume', 'spy_corr']
}


if __name__ == "__main__":
    big_df = get_historical_data(symbol=SYMBOL, timeframe=TIMEFRAME, is_crypto=IS_CRYPTO, target_rows=5000)
    while big_df is None:
        logging.info("SLEEPING: Waiting for data availability...")
        time.sleep(60)
        big_df = get_historical_data(symbol=SYMBOL, timeframe=TIMEFRAME,is_crypto=IS_CRYPTO)
    model = train_master_model(big_df, active_features=FEATURE_SETS[SYMBOL])
    
    print("RUNNING IN LIVE PAPER TRADING MODE")
    print("Press Ctrl+C to stop.")
    # Passes the winning features to the live bot
    run_live_bot(active_features=FEATURE_SETS[SYMBOL])