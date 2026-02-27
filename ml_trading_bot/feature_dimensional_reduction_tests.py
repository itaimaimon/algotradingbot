from statsmodels.stats.outliers_influence import variance_inflation_factor
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import itertools
import csv
import time
from config import SYMBOL, TIMEFRAME
from data_loader import get_historical_data
from strategy import add_indicators, train_master_model
from backtester import run_backtest


all_features = [
                    'returns', 
                    'range', 
                    'rsi', 
                    'volatility', 
                    'adx', 
                    'volume_change', 
                    'dist_from_mean',
                    'relative_volume',
                    'order_flow',
                    'daily_trend',
                    'btc_corr'
                ]

potential_features = [
                    'returns', 
                    'range', 
                    'volume_change', 
                    'dist_from_mean',
                    'relative_volume',
                    'order_flow',
                    'daily_trend',
                    'btc_corr'
                ] 

def run_feature_tournament(iterations =10):
    df = get_historical_data(SYMBOL, TIMEFRAME,target_rows=5000)
    while df is None:
        time.sleep(60)
        df = get_historical_data(SYMBOL, TIMEFRAME)
    df=add_indicators(df)    

    # Split data into 3 equal chunks
    """
    chunk_size = len(df) // 3
    df1 = df.iloc[:chunk_size]
    df2 = df.iloc[chunk_size : chunk_size*2]
    df3 = df.iloc[chunk_size*2:]
    """

    """Runs the combinatorial backtest loop we discussed earlier."""
    all_features = [
                    'returns', 
                    'range', 
                    'rsi', 
                    'volatility', 
                    'adx', 
                    'volume_change', 
                    'dist_from_mean',
                    'relative_volume',
                    'order_flow',
                    'daily_trend',
                    'btc_corr'
                ]

    potential_features = [
                    'returns', 
                    'range', 
                    'volume_change', 
                    'dist_from_mean',
                    'relative_volume',
                    'order_flow',
                    'daily_trend',
                    'btc_corr'
                ] 



    print("🏟️ Starting Feature Tournament...")
    log_file = "backtest_results.csv"

    # 2. Prepare the CSV file and write the header
    with open(log_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['num_features','Features', 'mean_sharpe', 'std_sharpe', 'mean_returns', 'std_returns', 'Is_Stable'])
        for r in range(3,len(potential_features)):
            for combo in itertools.combinations(potential_features, r):
                combo_list = list(combo)
                sharpe_results = []
                total_return_results = []
                for i in range(iterations):
                    seed = np.random.randint(1,10000)
                    print(f"🧪 Testing Combo: {combo_list}")
                    

                    # not split into three attempts with less info
                    report = run_backtest(df, add_indicators_happened=True, active_features=combo_list,random_seed=seed)
                    
                    sharpe = report["Sharpe Ratio"]

                    total_return= report["Total Return"]  

                    sharpe_results.append(sharpe)
                    total_return_results.append(total_return)

                    # split in three attempts with less info
                    """
                    report1 = run_backtest(df1, active_features=combo_list,random_seed=seed)
                    report2 = run_backtest(df2, active_features=combo_list,random_seed= seed)
                    report3 = run_backtest(df3, active_features=combo_list,random_seed= seed)

                    s1 = report1["Sharpe Ratio"]
                    s2 = report2["Sharpe Ratio"]
                    s3 = report3["Sharpe Ratio"]

                    total_return_1= report1["Total Return"]  
                    total_return_2= report2["Total Return"] 
                    total_return_3= report3["Total Return"]   
                    savg = (s1+s2+s3)/3
                    total_return_avg= (total_return_1+total_return_2+total_return_3)/3
                     
                    sharpe_results.append(savg)
                    total_return_results.append(total_return_avg)
                    """
                # 3. Final Analysis
                mean_sharpe = np.mean(sharpe_results)
                std_sharpe = np.std(sharpe_results)
                mean_returns = np.mean(total_return_results)
                std_returns=np.std(total_return_results)

                is_stable = std_sharpe < 0.2 * mean_sharpe
                with open(log_file, mode='a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([r,"|".join(combo_list), mean_sharpe, std_sharpe, mean_returns, std_returns, is_stable])












def calculate_vif(df, features):
    X = df[features].dropna()
    vif_data = pd.DataFrame()
    vif_data["feature"] = X.columns
    
    # Calculating VIF for each feature
    vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(len(X.columns))]
    
    return vif_data.sort_values(by="VIF", ascending=False)

def plot_correlation_matrix(df, features):
    # Calculate the correlation matrix
    corr = df[features].corr()
    
    # Plotting
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=0.5)
    plt.title("Feature Correlation Matrix")
    plt.show()

def run_rfe_tournament(df, initial_features, iterations=5):
    current_features = list(initial_features)
    history_log = []

    print(f"🧹 Starting Recursive Feature Elimination...")
    print(f"Initial Set: {current_features}")

    while len(current_features) > 0:
        print(f"\n--- Testing with {len(current_features)} Features ---")
        
        # 1. Run Stability Check on Current Set
        sharpes = []
        for _ in range(iterations):
            seed = np.random.randint(1, 10000)
            report = run_backtest(df, active_features= current_features, random_seed=seed)
            s = report["Sharpe Ratio"]
            
            sharpes.append(s)

        mean_s = np.mean(sharpes)
        std_s = np.std(sharpes)
        robust_score = mean_s - std_s
        
        history_log.append({
            'num_features': len(current_features),
            'features': list(current_features),
            'robust_score': robust_score,
            'mean_sharpe': mean_s
        })

        print(f"✅ Robust Score: {robust_score:.4f} (Mean: {mean_s:.2f})")

        if len(current_features) == 1:
            break

        # 2. Identify the "Weakest Link"
        # We train one model on the full current set to get Feature Importances
        model = train_master_model(df, active_features=current_features)
        importances = model.feature_importances_
        
        # Find index of the least important feature
        least_important_idx = np.argmin(importances)
        dropped_feature = current_features.pop(least_important_idx)
        
        print(f"🗑️ Dropping weakest feature: {dropped_feature} (Importance: {importances[least_important_idx]:.4f})")

    # 3. Final Report
    report_df = pd.DataFrame(history_log)
    print("\n" + "="*50)
    print("🏆 RFE FINAL REPORT")
    print("="*50)
    print(report_df[['num_features', 'robust_score', 'mean_sharpe']])
    
    return report_df



#df = get_historical_data(SYMBOL, TIMEFRAME, target_rows=5000)
#df = add_indicators(df)

#rfe_results = run_rfe_tournament(df, potential_features)

#plot_correlation_matrix(df, potential_features)
#print(calculate_vif(df,potential_features))