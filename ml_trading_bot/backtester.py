
import pandas as pd
import matplotlib.pyplot as plt
from strategy import get_ml_prediction
from performance_metrics import generate_report

#Feature: Slippage & Fees
FEE_PCT = 0.001       # 0.1% per trade
SLIPPAGE_PCT = 0.0005 # 0.05% slippage

def run_backtest(df, initial_balance=10000):
    if df is None or len(df) < 50:
        print("Error: Not enough data to backtest. Need at least 50 rows.")
        return None

    balance = initial_balance
    equity_curve = []
    dates = []
    
    # DYNAMIC START INDEX:
    # We need enough data to train (at least 50 rows), but we can't start 
    # at 100 if we only have 90 rows.
    # We use min(100, len(df) - 10) to ensure we always have a loop.
    start_idx = min(100, int(len(df) * 0.8)) 
    
    # Ensure start_idx is at least 20 to give the ML model *some* history
    if start_idx < 20: start_idx = 20

    print(f"Running Realistic Backtest on {len(df)} rows...")
    print(f"   (Training on first {start_idx} candles, testing on remainder)")

    # Pre-fill equity curve for the training period (flat line)
    # This aligns the charts so they start at the correct timestamp
    for i in range(start_idx):
        equity_curve.append(initial_balance)
        dates.append(df.iloc[i]['ts'])

    # --- THE MAIN LOOP ---
    for i in range(start_idx, len(df) - 1):
        current_window = df.iloc[:i]
        
        # Validation: Check if window is empty
        if len(current_window) < 10:
            continue
            
        current_price = df.iloc[i]['close']
        actual_next_price = df.iloc[i+1]['close']
        timestamp = df.iloc[i+1]['ts']
        
        # Get Prediction
        try:
            prediction, _ = get_ml_prediction(current_window)
        except Exception as e:
            # If ML fails (e.g., data too small), skip this candle
            prediction = None
        
        # Trading Logic
        if prediction and prediction > current_price * 1.005:
            # BUY SIGNAL
            entry_price = current_price * (1 + SLIPPAGE_PCT) # Slippage
            gross_change = (actual_next_price - entry_price) / entry_price
            net_change = gross_change - (FEE_PCT * 2)        # Fees
            
            balance += (balance * net_change)
            
        equity_curve.append(balance)
        dates.append(timestamp)

    # --- RESULTS ---
    if len(equity_curve) < 2:
        print("Loop finished but no data recorded. Check if DataFrame is empty.")
        return None

    equity_series = pd.Series(equity_curve, index=pd.to_datetime(dates))
    
    # Generate Report
    report = generate_report(equity_series)
    print("\n--- Professional Performance Report ---")
    for k, v in report.items():
        print(f"{k}: {v}")
    print("------------------------------------------")

    plot_results(equity_series) # Call plotting
    return report

def plot_results(equity_series):
    plt.figure(figsize=(12, 6))
    plt.plot(equity_series.index, equity_series.values, label='Portfolio Value', color='green')
    plt.title("Backtest Equity Curve (with Fees & Slippage)")
    plt.xlabel("Date")
    plt.ylabel("Balance ($)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()