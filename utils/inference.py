

import json
import os

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler

from utils.feature_engineering import FEATURE_COLS, WINDOW_KEEP


# LSTM Model Definition (must match training notebook exactly)

class StackedLSTMClassifier(nn.Module):
    """
    2-layer Stacked LSTM for binary stock direction classification.

    Architecture:
        Input  : (batch, seq_len=20, input_size=16)
        LSTM-1 : hidden_size=128, returns full sequence
        LSTM-2 : hidden_size=64,  returns last hidden state only
        LayerNorm → FC(64→32) → ReLU → Dropout → FC(32→1)
    """

    def __init__(
        self,
        input_size:   int = 16,
        hidden_size1: int = 128,
        hidden_size2: int = 64,
        fc_hidden:    int = 32,
        dropout:      float = 0.3,
    ):
        super().__init__()

        self.lstm1 = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size1,
            num_layers=1,
            batch_first=True,
        )
        self.dropout1 = nn.Dropout(dropout)

        self.lstm2 = nn.LSTM(
            input_size=hidden_size1,
            hidden_size=hidden_size2,
            num_layers=1,
            batch_first=True,
        )

        self.norm = nn.LayerNorm(hidden_size2)

        self.fc = nn.Sequential(
            nn.Linear(hidden_size2, fc_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(fc_hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out1, _     = self.lstm1(x)
        out1        = self.dropout1(out1)
        out2, _     = self.lstm2(out1)
        last_hidden = out2[:, -1, :]
        normed      = self.norm(last_hidden)
        logit       = self.fc(normed)
        return logit.squeeze(1)


# Model Loading

def load_all_models(models_dir):

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    n_features = len(FEATURE_COLS)

    loaded = {"device": device}

    # ── Random Forest ────────────────────────────────────────────────────────
    for h in ["1d", "5d", "10d"]:
        path = os.path.join(models_dir, f"rf_model_{h}.pkl")
        loaded[f"rf_{h}"] = joblib.load(path)
        print(f"  [OK] RF  {h}: {path}")

    # ── XGBoost ──────────────────────────────────────────────────────────────
    for h in ["1d", "5d", "10d"]:
        path = os.path.join(models_dir, f"xgb_model_{h}.pkl")
        loaded[f"xgb_{h}"] = joblib.load(path)
        print(f"  [OK] XGB {h}: {path}")

    # ── LSTM ─────────────────────────────────────────────────────────────────
    for h in ["1d", "5d", "10d"]:
        model_path  = os.path.join(models_dir, f"lstm_model_{h}.pt")
        scaler_path = os.path.join(models_dir, f"scaler_{h}.pkl")

        lstm = StackedLSTMClassifier(input_size=n_features).to(device)
        lstm.load_state_dict(torch.load(model_path, map_location=device))
        lstm.eval()
        loaded[f"lstm_{h}"]   = lstm
        loaded[f"scaler_{h}"] = joblib.load(scaler_path)
        print(f"  [OK] LSTM {h}: {model_path}")

    return loaded


def load_auc_weights(config_path):

    with open(config_path, "r") as f:
        return json.load(f)


# Prediction for a Single Ticker

def predict_single_ticker(window, models, weights, horizon="1d"):
    """
    Run RF + XGBoost + LSTM on a single ticker's window.

    Args:
        window: np.array shape (20, 16) — one ticker's feature window.
        models: dict from load_all_models().
        weights: AUC weights for the given horizon {"rf": w, "xgb": w, "lstm": w}.
        horizon: "1d", "5d", or "10d".

    Returns:
        dict with prob_rf, prob_xgb, prob_lstm, ensemble prob, and prediction.
    """
    device = models["device"]

    # ── RF: flatten → predict_proba ──────────────────────────────────────────
    X_flat = window.flatten().reshape(1, -1)  # (1, 320)
    prob_rf = float(models[f"rf_{horizon}"].predict_proba(X_flat)[:, 1][0])

    # ── XGBoost: flatten → predict_proba ─────────────────────────────────────
    prob_xgb = float(models[f"xgb_{horizon}"].predict_proba(X_flat)[:, 1][0])

    # ── LSTM: scale → tensor → sigmoid ───────────────────────────────────────
    scaler = models[f"scaler_{horizon}"]
    window_scaled = scaler.transform(
        window.reshape(-1, window.shape[1])
    ).reshape(1, window.shape[0], window.shape[1])  # (1, 20, 16)

    X_tensor = torch.tensor(window_scaled, dtype=torch.float32).to(device)
    with torch.no_grad():
        logit = models[f"lstm_{horizon}"](X_tensor)
        prob_lstm = float(torch.sigmoid(logit).cpu().numpy()[0])

    # ── Weighted ensemble ────────────────────────────────────────────────────
    w_rf   = weights["rf"]
    w_xgb  = weights["xgb"]
    w_lstm = weights["lstm"]
    total  = w_rf + w_xgb + w_lstm

    ensemble = (w_rf * prob_rf + w_xgb * prob_xgb + w_lstm * prob_lstm) / total
    pred     = 1 if ensemble >= 0.5 else 0

    return {
        f"prob_rf_{horizon}":   round(prob_rf,   6),
        f"prob_xgb_{horizon}":  round(prob_xgb,  6),
        f"prob_lstm_{horizon}": round(prob_lstm,  6),
        f"ensemble_{horizon}":  round(ensemble,   6),
        f"pred_{horizon}":      pred,
    }


# Full Prediction Pipeline: All Tickers × 3 Horizons + Consensus

def run_ensemble_predictions(windows, models, auc_weights):
    """
    Run predictions for all tickers across all 3 horizons.

    Args:
        windows: dict {ticker: np.array (20, 16)} from extract_inference_windows.
        models: dict from load_all_models().
        auc_weights: dict from load_auc_weights().

    Returns:
        pd.DataFrame with columns:
            ticker, prob_rf_1d, prob_xgb_1d, prob_lstm_1d, ensemble_1d, pred_1d,
            (same for 5d, 10d), consensus_votes, consensus_decision
    """
    rows = []

    for ticker, window in sorted(windows.items()):
        row = {"ticker": ticker}

        for horizon in ["1d", "5d", "10d"]:
            preds = predict_single_ticker(
                window, models, auc_weights[horizon], horizon
            )
            row.update(preds)

        # ── Multi-Horizon Consensus ──────────────────────────────────────────
        votes = row["pred_1d"] + row["pred_5d"] + row["pred_10d"]
        row["consensus_votes"] = votes

        if votes == 3:
            row["consensus_decision"] = "STRONG_BUY"
        elif votes == 2:
            row["consensus_decision"] = "BUY"
        elif votes == 1:
            row["consensus_decision"] = "HOLD"
        else:
            row["consensus_decision"] = "SELL"

        rows.append(row)

    df = pd.DataFrame(rows)

    # ── Summary ──────────────────────────────────────────────────────────────
    n_strong = (df["consensus_decision"] == "STRONG_BUY").sum()
    n_buy    = (df["consensus_decision"] == "BUY").sum()
    n_hold   = (df["consensus_decision"] == "HOLD").sum()
    n_sell   = (df["consensus_decision"] == "SELL").sum()

    print(f"\n  Consensus Results:")
    print(f"    STRONG_BUY : {n_strong}")
    print(f"    BUY        : {n_buy}")
    print(f"    HOLD       : {n_hold}")
    print(f"    SELL       : {n_sell}")

    return df
