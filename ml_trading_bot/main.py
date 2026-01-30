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
import itertools
import csv
import pandas  as pd
from live_trading import run_live_bot

# --- SETTINGS ---
BACKTESTING = True  # <--- TOGGLE THIS: True = Lab Mode, False = Real Money
TOURNAMENT_BACKTEST = False
DATA_FILE = "btc_hourly.csv" # Your historical data file

# The features you found were "Best" (Update this list based on your findings)
BEST_FEATURES = ["returns","rsi","adx","dist_from_mean"]


def run_feature_tournament():
    df = get_historical_data(SYMBOL, TIMEFRAME)
        
    while df is None:
        time.sleep(60)
        df = get_historical_data(SYMBOL, TIMEFRAME)

    """Runs the combinatorial backtest loop we discussed earlier."""
    potential_features = [
                    'returns', 
                    'range', 
                    'rsi', 
                    'volatility', 
                    'adx', 
                    'volume_change', 
                    'dist_from_mean',
                    'relative_volume'
                ]
    print("🏟️ Starting Feature Tournament...")
    log_file = "backtest_results.csv"

    # 2. Prepare the CSV file and write the header
    with open(log_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Combination_Size', 'Features', 'Sharpe_Ratio', 'max Drawdown','Total_Return_Pct'])
        
        for r in range(1,len(potential_features)):
            for combo in itertools.combinations(potential_features, r):
                combo_list = list(combo)
                print(f"🧪 Testing Combo: {combo_list}")
                report = run_backtest(df, active_features=combo_list)
                with open(log_file, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([r, "|".join(combo_list), report["Sharpe Ratio"], report["Max Drawdown"],report["Total Return"]])

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    if BACKTESTING:
        print("🧪 RUNNING IN BACKTEST MODE")
        
        # OPTION A: Run the Tournament to find best features
        if TOURNAMENT_BACKTEST:
            run_feature_tournament() 
        else:
            # OPTION B: Run a single backtest with your best features
            df = get_historical_data(SYMBOL, TIMEFRAME)
        
            while df is None:
                logging.info("SLEEPING: Waiting for data availability...")
                time.sleep(60)
                df = get_historical_data(SYMBOL, TIMEFRAME)
            print(f"Running single test with: {BEST_FEATURES}")
            history = run_backtest(df, active_features=BEST_FEATURES)
            print(f"🏁 Final Balance: ${history[-1]:.2f}")
        
    else:
        print("⚠️ RUNNING IN LIVE PAPER TRADING MODb")
        print("Press Ctrl+C to stop.")
        # Passes the winning features to the live bot
        run_live_bot(active_features=BEST_FEATURES)




"""
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
            
            #backtest part
            if doing_backtest: 
                potential_features = [
                    'returns', 
                    'range', 
                    'rsi', 
                    'volatility', 
                    'adx', 
                    'volume_change', 
                    'dist_from_mean',
                    'relative_volume'
                ]

                log_file = "backtest_results.csv"

                # 2. Prepare the CSV file and write the header
                with open(log_file, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Combination_Size', 'Features', 'Sharpe_Ratio', 'max Drawdown','Total_Return_Pct'])
                for r in range(1,len(potential_features)):
                    for combo in itertools.combinations(potential_features, r):
                        combo_list = list(combo)
                        print(f"🧪 Testing Combo: {combo_list}")
                        report = run_backtest(df, active_features=combo_list)
                        with open(log_file, mode='a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([r, "|".join(combo_list), report["Sharpe Ratio"], report["Max Drawdown"],report["Total Return"]])
                break
            break
            #needs to be changed to backend implementation

            
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
            
        if percent_diff > 0.5:
            print(" BUY SIGNAL: Strong Uptrend Predicted")
            # exchange.create_market_buy_order(SYMBOL, 0.01) 
        elif percent_diff < -0.5:
            print("SELL SIGNAL: Strong Downtrend Predicted")
            # exchange.create_market_sell_order(SYMBOL, 0.01)
        else:
            print("zzz No clear trend (Hold)")
        
            # Wait for next candle
            logging.info("Waiting 60 seconds...")
            time.sleep(60)
        except KeyboardInterrupt:
            logging.info(" Bot stopped by user.")
            break
        except Exception as e:
            logging.error(f" Unexpected Error: {e}")
            time.sleep(10)
"""

