import numpy as np

class RiskManager:
    def __init__(self, stop_loss_pct=0.02, risk_per_trade=0.01):
        self.stop_loss_pct = stop_loss_pct  # 2% stop loss
        self.risk_per_trade = risk_per_trade # Risk 1% of total equity per trade

    def calculate_position_size(self, balance, current_price, atr=None):
        """
        Calculates how much to buy. 
        If ATR is provided, it uses volatility-based sizing.
        """
        risk_amount = balance * self.risk_per_trade
        
        # Use ATR for stop distance if available, else fixed %
        if atr:
            stop_distance = atr * 2 
        else:
            stop_distance = current_price * self.stop_loss_pct
            
        if stop_distance == 0: return 0
        
        # Units = Amount to Risk / Distance to Stop
        units_to_buy = risk_amount / stop_distance
        return round(units_to_buy, 6)

    def get_trade_decision(self, current_price, predicted_price, threshold=0.005):
        """Determines if the predicted move is large enough to justify a trade."""
        expected_return = (predicted_price - current_price) / current_price
        
        if expected_return > threshold:
            return "BUY"
        elif expected_return < -threshold:
            return "SELL"
        return "HOLD"