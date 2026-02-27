import numpy as np
import pandas as pd
from backtester import run_backtest
from strategy import train_master_model
from data_loader import get_historical_data
from config import TIMEFRAME, SYMBOL



def run_stability_check(df, active_features, iterations=10):
    sharpe_results = []
    total_returns = []
    
    print(f"🧪 Testing Stability for: {active_features}")
    print(f"🔄 Running {iterations} iterations with unique random seeds...")

    for i in range(iterations):
        # Generate a new random seed for each run
        current_seed = np.random.randint(1, 10000)
        
        # 1. We must slightly modify the trainer to accept a seed
        # For this test, we skip the joblib save and just run the backtest
        report = run_backtest(df, active_features=active_features, random_seed=current_seed)
        

        sharpe = report["Sharpe Ratio"]
        total_return= report["Total Return"]
        
      
            
        sharpe_results.append(sharpe)
        total_returns.append(total_return)
        
        print(f"  Run {i+1}: Seed {current_seed} | Sharpe: {sharpe} | Return: {total_return}%")

    # 3. Final Analysis
    mean_sharpe = np.mean(sharpe_results)
    std_sharpe = np.std(sharpe_results)
    
    print("\n" + "="*30)
    print(f"📊 FINAL STABILITY REPORT")
    print(f"Average Sharpe: {mean_sharpe:.4f}")
    print(f"Sharpe Variance: {std_sharpe:.4f}")
    print(f"Consistency Score: {max(0, 100 - (std_sharpe/mean_sharpe*100)):.2f}%")
    print("="*30)

    if std_sharpe > 0.2 * mean_sharpe:
        print("⚠️ WARNING: High variance detected. Strategy is seed-sensitive (LUCKY).")
    else:
        print("✅ SUCCESS: Low variance detected. Strategy is robust (RELIABLE).")

# To use:[]
# df = pd.read_csv("btc_hourly.csv")
# run_stability_check(df, ['range', 'volume_change', 'relative_volume'])
big_df = get_historical_data(SYMBOL, TIMEFRAME, target_rows=5000)
run_stability_check(big_df, ['range', 'volume_change', 'relative_volume'])