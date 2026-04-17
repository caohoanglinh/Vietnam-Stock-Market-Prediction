import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

os.makedirs('img', exist_ok=True)

# Load Random Forest feature columns
try:
    feature_cols = joblib.load("models/feature_cols_rf.pkl")
except FileNotFoundError:
    print("Error: models/feature_cols_rf.pkl not found.")
    exit(1)

W = 20
num_features = len(feature_cols)
y_labels = [f"t-{W - d}" if (W-d) != 0 else "t (Current)" for d in range(1, W + 1)]
cmaps = {1: "YlGnBu", 5: "Oranges", 10: "Reds"}

for horizon in [1, 5, 10]:
    try:
        model = joblib.load(f"models/rf_model_{horizon}d.pkl")
        
        # Random Forest importances has shape (320,)
        importances = model.feature_importances_
        importance_matrix = importances.reshape((W, num_features))
        
        plt.figure(figsize=(14, 10))
        sns.heatmap(importance_matrix, 
                    xticklabels=feature_cols, 
                    yticklabels=y_labels, 
                    cmap=cmaps.get(horizon, "viridis"), 
                    annot=False, 
                    linewidths=.5)
        
        plt.title(f"Random Forest Feature Importance Matrix - {horizon}D Horizon", fontsize=16, fontweight="bold")
        plt.xlabel("Technical Indicators", fontsize=14)
        plt.ylabel("Time Steps (Sliding Window)", fontsize=14)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        save_path = f"img/rf_feature_matrix_{horizon}d.png"
        plt.savefig(save_path, dpi=150)
        plt.close()
        print(f"✅ Saved Random Forest matrix for {horizon}D to {save_path}")
    except FileNotFoundError:
        print(f"Skipping RF {horizon}D: model file not found.")
