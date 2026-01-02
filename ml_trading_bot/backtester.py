import pandas as pd
import matplotlib.pyplot as plt
from strategy import get_ml_prediction

def run_backtest(df, initial_balance=10000):
    balance = initial_balance
    results = []
    
    # We need a 'warm-up' period for the ML model
    start_idx = 100 
    
    print(f"📊 Running Visual Backtest...")

    for i in range(start_idx, len(df) - 1):
        current_window = df.iloc[:i]
        current_price = df.iloc[i]['close']
        actual_next_price = df.iloc[i+1]['close']
        timestamp = df.iloc[i]['ts']
        
        # Predict
        prediction, _ = get_ml_prediction(current_window)
        
        if prediction and prediction > current_price * 1.005: # 0.5% Threshold
            # Simulate a BUY
            change = (actual_next_price - current_price) / current_price
            balance += (balance * change)
            
        results.append({'ts': timestamp, 'price': current_price, 'balance': balance})

    backtest_df = pd.DataFrame(results)
    plot_results(backtest_df)
    return backtest_df

def plot_results(df):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    # Top Plot: BTC Price
    ax1.plot(df['ts'], df['price'], color='blue', label='Asset Price')
    ax1.set_title("Market Price vs. Strategy Performance")
    ax1.set_ylabel("Price ($)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Bottom Plot: Portfolio Value
    ax2.fill_between(df['ts'], df['balance'], 10000, color='green', alpha=0.2)
    ax2.plot(df['ts'], df['balance'], color='green', linewidth=2, label='Portfolio Value')
    ax2.set_ylabel("Balance ($)")
    ax2.set_xlabel("Time")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()