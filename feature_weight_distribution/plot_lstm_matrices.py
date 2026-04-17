import torch
import torch.nn as nn
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

os.makedirs('img', exist_ok=True)

# ── 1. REDEFINE THE LSTM CLASS EXACTLY AS TRAINED ────────────────────────────
class StackedLSTMClassifier(nn.Module):
    def __init__(self, input_size=16, hidden_size1=128, hidden_size2=64, fc_hidden=32, dropout=0.3):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size=input_size, hidden_size=hidden_size1, num_layers=1, batch_first=True)
        self.dropout1 = nn.Dropout(dropout)
        self.lstm2 = nn.LSTM(input_size=hidden_size1, hidden_size=hidden_size2, num_layers=1, batch_first=True)
        self.norm = nn.LayerNorm(hidden_size2)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size2, fc_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_hidden, 1),
        )
    def forward(self, x): pass # Not needed for weight extraction

# ── 2. LOAD FEATURES AND PLOT WEIGHTS ────────────────────────────────────────
try:
    feature_cols = joblib.load("models/feature_cols_lstm.pkl")
except FileNotFoundError:
    print("Error: models/feature_cols_lstm.pkl not found.")
    exit(1)

DEVICE = torch.device("cpu") # Load on CPU for analysis
colors = {1: "skyblue", 5: "orange", 10: "salmon"}

for horizon in [1, 5, 10]:
    model_path = f"models/lstm_model_{horizon}d.pt"
    if not os.path.exists(model_path):
        print(f"Skipping LSTM {horizon}D: {model_path} not found.")
        continue
        
    model = StackedLSTMClassifier(input_size=len(feature_cols))
    model.load_state_dict(torch.load(model_path, map_location=DEVICE))
    model.eval()

    # In LSTM, weights are shared across all 20 timesteps! 
    # So we cannot extract a 20x16 static matrix natively like in Random Forest.
    # We estimate 'Feature Importance' by taking the L1 norm (absolute sum) 
    # of the Input-To-Hidden weights for the first LSTM layer.
    
    # weight_ih_l0 shape: (4 * hidden_size1, input_size) => (512, 16)
    w_ih = model.lstm1.weight_ih_l0.detach().cpu().numpy()
    
    # Sum absolute weights across the hidden gates to see which feature signals strongest
    feature_importance = np.sum(np.abs(w_ih), axis=0) 
    
    # Normalize to 100 for readability
    feature_importance = 100.0 * (feature_importance / feature_importance.max())
    
    # Sort and plot
    imp_series = pd.Series(feature_importance, index=feature_cols).sort_values(ascending=True)
    
    plt.figure(figsize=(10, 8))
    # Use barh for 1D rendering since matrix representation isn't physically valid for LSTM static weights
    imp_series.plot(kind="barh", color=colors.get(horizon, "gray"), edgecolor="black")
    
    plt.title(f"LSTM Feature Impact (Input-Weight L1 Norm) - {horizon}D Horizon\n(Note: LSTM shares weights identically across all 20 timesteps)", fontsize=13, fontweight="bold")
    plt.xlabel("Relative Importance Score", fontsize=12)
    plt.ylabel("Technical Indicators", fontsize=12)
    plt.tight_layout()
    
    save_path = f"img/lstm_feature_weights_{horizon}d.png"
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"✅ Saved LSTM Feature Impact for {horizon}D to {save_path}")
