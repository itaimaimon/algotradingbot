import pandas as pd
from sklearn.ensemble import RandomForestRegressor

def prepare_ml_data(df, lags=5):
    # 1. Feature Engineering: Create "Lags" (Price 1h ago, 2h ago...)
    df = df.copy()
    for i in range(1, lags + 1):
        df[f'lag_{i}'] = df['close'].shift(i)
    
    # 2. Add Moving Average as a feature
    df['ma_20'] = df['close'].rolling(window=20).mean()
    
    # 3. Target: We want to predict the *next* close
    df['target'] = df['close'].shift(-1)
    
    # 4. Drop NaNs created by shifting/rolling
    return df.dropna()

def get_ml_prediction(df):
    # Prepare data
    data = prepare_ml_data(df)
    
    if data.empty:
        return None, None

    # Define Features (X) and Target (y)
    feature_cols = [c for c in data.columns if 'lag' in c or 'ma' in c]
    X = data[feature_cols]
    y = data['target']
    
    # Train Model (Retrains every loop - "Walk Forward")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Predict for the MOST RECENT candle
    # We use the last row of features to predict the "future"
    last_features = X.iloc[[-1]] 
    prediction = model.predict(last_features)[0]
    
    return prediction, last_features
