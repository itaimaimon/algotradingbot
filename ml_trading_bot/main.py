import time
import os
from config import SYMBOL, TIMEFRAME, get_exchange, API_KEY, SECRET_KEY
from data_loader import get_historical_data
from strategy import generate_signal
# Top of main.py
from risk_manager import RiskManager
from backtester import run_backtest
from backtester import run_backtest
import logging
rm = RiskManager(risk_per_trade=0.02) # Risk 2% per trade

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)


def run_bot():
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
    current_balance = bal

    while True:
        try:
            if rm.check_circuit_breaker(current_balance):
                logging.critical(" CIRCUIT BREAKER TRIGGERED! Max daily loss exceeded. Halting.")
                break
            logging.info("\n Analying Market...")
        
            # 1. Fetch Data
            df = get_historical_data(SYMBOL, TIMEFRAME)
        
            if df is None:
                logging.info("SLEEPING: Waiting for data availability...")
                time.sleep(60)
                continue
                
            run_backtest(df) 
            break

            # 2. Get Prediction
            current_price = df['close'].iloc[-1]
            predicted_price, _ = generate_signal(df)
        
            if predicted_price is None:
                logging.info("  Not enough data to generate features.")
                time.sleep(60)
                continue
            
            # 3. Calculate Signal
            percent_diff = ((predicted_price - current_price) / current_price) * 100
            logging.info(f" Price: {current_price:.2f} |  Prediction: {predicted_price:.2f} ({percent_diff:+.2f}%)")
        
            # 4. Execution Logic (Threshold: 0.5% predicted move)
            decision = rm.get_trade_decision(current_price, predicted_price)    
            balance = float(exchange.fetch_balance()['free']['USD'])

            if decision == "BUY":
                qty = rm.calculate_position_size(balance, current_price)
                logging.info(f" Risk Manager: Recommended Qty {qty}")
                # exchange.create_market_buy_order(SYMBOL, qty)
            elif decision == "SELL":
                qty = rm.calculate_position_size(balance, current_price)
                logging.info(f" Risk Manager: Recommended Qty {qty}")
                # exchange.create_market_sell_order(SYMBOL, qty)
            else:
                logging.info("zzz No clear trend (Hold)")
            """

        if percent_diff > 0.5:
            print(" BUY SIGNAL: Strong Uptrend Predicted")
            # exchange.create_market_buy_order(SYMBOL, 0.01) 
        elif percent_diff < -0.5:
            print("SELL SIGNAL: Strong Downtrend Predicted")
            # exchange.create_market_sell_order(SYMBOL, 0.01)
        else:
            print("zzz No clear trend (Hold)")
        """
            # Wait for next candle
            logging.info("Waiting 60 seconds...")
            time.sleep(60)
        except KeyboardInterrupt:
            logging.info(" Bot stopped by user.")
            break
        except Exception as e:
            logging.error(f" Unexpected Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
