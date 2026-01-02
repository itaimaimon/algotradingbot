import numpy as np
import pandas as pd

def calculate_sharpe_ratio(returns, risk_free_rate=0.0, periods_per_year=365):
    """
    Calculates the Annualized Sharpe Ratio.
    Args:
        returns (pd.Series): Percentage returns (daily).
        risk_free_rate (float): Annual risk-free rate (e.g. 0.02 for 2%).
        periods_per_year (int): 365 for Crypto (252 for Stocks).
    """
    if len(returns) < 2:
        return 0.0
    
    # Calculate excess returns
    excess_returns = returns - (risk_free_rate / periods_per_year)
    
    # Avoid division by zero
    std_dev = excess_returns.std()
    if std_dev == 0:
        return 0.0
        
    sharpe = (excess_returns.mean() / std_dev) * np.sqrt(periods_per_year)
    return round(sharpe, 2)

def calculate_max_drawdown(equity_curve):
    """
    Calculates Maximum Drawdown (MDD) from an equity curve series.
    """
    # Calculate rolling peak
    rolling_max = equity_curve.cummax()
    
    # Calculate drawdown percentage
    drawdown = (equity_curve - rolling_max) / rolling_max
    
    # Max Drawdown is the minimum (most negative) value
    max_dd = drawdown.min()
    
    return round(max_dd * 100, 2) # Return as percentage

def generate_report(equity_curve):
    # Convert equity curve to percentage returns
    returns = equity_curve.pct_change().dropna()
    
    sharpe = calculate_sharpe_ratio(returns)
    mdd = calculate_max_drawdown(equity_curve)
    total_return = ((equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]) * 100
    
    return {
        "Sharpe Ratio": sharpe,
        "Max Drawdown": f"{mdd}%",
        "Total Return": f"{round(total_return, 2)}%"
    }