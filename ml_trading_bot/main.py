import time
import os
from config import SYMBOL, TIMEFRAME, get_exchange
from data_loader import get_historical_data
from strategy import get_ml_prediction
# Top of main.py
from risk_manager import RiskManager
from backtester import run_backtest
from backtester import run_backtest
rm = RiskManager(risk_per_trade=0.02) # Risk 2% per trade




def run_bot():
    print(f"--- 🤖 ML TRADING BOT STARTED ({SYMBOL}) ---")
    exchange = get_exchange()
    
    # Verify Connection
    try:
        bal = exchange.fetch_balance()['free']['USD']
        print(f"✅ Connected to Alpaca. Balance: ${bal:.2f}")
    except Exception as e:
        print(f"❌ Auth Error: Check .env keys. {e}")
        return

    while True:
        print("\n⏳ Analying Market...")
        
        # 1. Fetch Data
        df = get_historical_data(SYMBOL, TIMEFRAME, limit=500)
        
        if df is None:
            print("SLEEPING: Waiting for data availability...")
            time.sleep(60)
            continue
        """
        run_backtest(df) 
        """

        # 2. Get Prediction
        current_price = df['close'].iloc[-1]
        predicted_price, _ = get_ml_prediction(df)
        
        if predicted_price is None:
            print("⚠️  Not enough data to generate features.")
            time.sleep(60)
            continue
            
        # 3. Calculate Signal
        percent_diff = ((predicted_price - current_price) / current_price) * 100
        print(f"💲 Price: {current_price:.2f} | 🔮 Prediction: {predicted_price:.2f} ({percent_diff:+.2f}%)")
        
        # 4. Execution Logic (Threshold: 0.5% predicted move)
        decision = rm.get_trade_decision(current_price, predicted_price)    
        balance = float(exchange.fetch_balance()['free']['USD'])

        if decision == "BUY":
            qty = rm.calculate_position_size(balance, current_price)
            print(f"💰 Risk Manager: Recommended Qty {qty}")
            # exchange.create_market_buy_order(SYMBOL, qty)
        elif decision == "SELL":
            qty = rm.calculate_position_size(balance, current_price)
            print(f"💰 Risk Manager: Recommended Qty {qty}")
            # exchange.create_market_sell_order(SYMBOL, qty)
        else:
            print("zzz No clear trend (Hold)")
        """

        if percent_diff > 0.5:
            print("🚀 BUY SIGNAL: Strong Uptrend Predicted")
            # exchange.create_market_buy_order(SYMBOL, 0.01) 
        elif percent_diff < -0.5:
            print("📉 SELL SIGNAL: Strong Downtrend Predicted")
            # exchange.create_market_sell_order(SYMBOL, 0.01)
        else:
            print("zzz No clear trend (Hold)")
        """
        # Wait for next candle
        print("Waiting 60 seconds...")
        time.sleep(60)

if __name__ == "__main__":
    run_bot()
