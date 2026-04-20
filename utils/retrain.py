"""
Retrain Module
==============
Retrain ONLY the 1-day horizon models (RF, XGBoost, LSTM).
5-day and 10-day models are left unchanged.

Can be run:
  - From Airflow DAG (inside Docker, CPU)
  - Standalone on host machine with GPU:
      cd c:\\Work\\vnstock
      python -m utils.retrain
"""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

# Ensure project root is on path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.feature_engineering import (
    FEATURE_COLS,
    WINDOW_KEEP,
    prepare_training_data,
)
from utils.inference import StackedLSTMClassifier


# Hyperparameters (identical to training notebooks)

# Random Forest 1D
RF_PARAMS_1D = dict(
    n_estimators=1000,
    max_depth=10,
    min_samples_leaf=30,
    n_jobs=-1,
    random_state=42,
    # class_weight set dynamically based on neg/pos ratio
)

# XGBoost 1D
XGB_PARAMS_1D = dict(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.5,
    colsample_bytree=0.5,
    min_child_weight=30,
    gamma=1.0,
    eval_metric="logloss",
    tree_method="hist",
    random_state=42,
    use_label_encoder=False,
    # scale_pos_weight set dynamically
)

# LSTM 1D
LSTM_HIDDEN_1 = 128
LSTM_HIDDEN_2 = 64
LSTM_FC       = 32
LSTM_DROPOUT  = 0.3
LSTM_BATCH    = 512
LSTM_LR       = 1e-3
LSTM_EPOCHS   = 50
LSTM_PATIENCE = 7
LSTM_WD       = 1e-4


# Retrain Random Forest 1D

def retrain_rf_1d(X_train, y_train, X_val, y_val, X_test, y_test, models_dir):
    """Retrain Random Forest 1D model."""
    print("\n── Retraining RF 1D ──────────────────────────────────────────")

    # Flatten: (N, 20, 16) → (N, 320)
    Xtr = X_train.reshape(len(X_train), -1)
    Xvl = X_val.reshape(len(X_val), -1)
    Xte = X_test.reshape(len(X_test), -1)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    ratio = neg / max(pos, 1)

    params = RF_PARAMS_1D.copy()
    params["class_weight"] = {0: 1.0, 1: ratio}

    rf = RandomForestClassifier(**params)
    rf.fit(Xtr, y_train)

    # Evaluate
    y_pred = rf.predict(Xte)
    y_prob = rf.predict_proba(Xte)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob)

    print(f"  Test — Acc: {acc:.4f} | F1: {f1:.4f} | AUC: {auc:.4f}")

    # Save
    path = os.path.join(models_dir, "rf_model_1d.pkl")
    joblib.dump(rf, path)
    print(f"  Saved: {path}")

    return {"acc": acc, "f1": f1, "auc": auc}


# Retrain XGBoost 1D

def retrain_xgb_1d(X_train, y_train, X_val, y_val, X_test, y_test, models_dir):
    """Retrain XGBoost 1D model."""
    print("\n── Retraining XGBoost 1D ─────────────────────────────────────")

    Xtr = X_train.reshape(len(X_train), -1)
    Xvl = X_val.reshape(len(X_val), -1)
    Xte = X_test.reshape(len(X_test), -1)

    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    ratio = neg / max(pos, 1)

    params = XGB_PARAMS_1D.copy()
    params["scale_pos_weight"] = ratio

    xgb = XGBClassifier(**params)
    xgb.fit(Xtr, y_train, eval_set=[(Xvl, y_val)], verbose=False)

    y_pred = xgb.predict(Xte)
    y_prob = xgb.predict_proba(Xte)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    f1  = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob)

    print(f"  Test — Acc: {acc:.4f} | F1: {f1:.4f} | AUC: {auc:.4f}")

    path = os.path.join(models_dir, "xgb_model_1d.pkl")
    joblib.dump(xgb, path)
    print(f"  Saved: {path}")

    return {"acc": acc, "f1": f1, "auc": auc}


# Retrain LSTM 1D

def retrain_lstm_1d(X_train, y_train, X_val, y_val, X_test, y_test, models_dir):
    """Retrain LSTM 1D model."""
    print("\n── Retraining LSTM 1D ────────────────────────────────────────")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    n_features = X_train.shape[2]

    N, T, F = X_train.shape
    scaler = StandardScaler()
    scaler.fit(X_train.reshape(-1, F))

    Xtr_s = scaler.transform(X_train.reshape(-1, F)).reshape(N, T, F)
    Xvl_s = scaler.transform(X_val.reshape(-1, F)).reshape(len(X_val), T, F)
    Xte_s = scaler.transform(X_test.reshape(-1, F)).reshape(len(X_test), T, F)

    from torch.utils.data import Dataset, DataLoader

    class SeqDataset(Dataset):
        def __init__(self, X, y):
            self.X = torch.tensor(X, dtype=torch.float32)
            self.y = torch.tensor(y, dtype=torch.float32)
        def __len__(self):
            return len(self.X)
        def __getitem__(self, idx):
            return self.X[idx], self.y[idx]

    tr_loader  = DataLoader(SeqDataset(Xtr_s, y_train), batch_size=LSTM_BATCH, shuffle=True)
    val_loader = DataLoader(SeqDataset(Xvl_s, y_val),   batch_size=LSTM_BATCH, shuffle=False)
    te_loader  = DataLoader(SeqDataset(Xte_s, y_test),  batch_size=LSTM_BATCH, shuffle=False)

    ratio = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))
    pw = np.sqrt(ratio)

    model = StackedLSTMClassifier(
        input_size=n_features,
        hidden_size1=LSTM_HIDDEN_1,
        hidden_size2=LSTM_HIDDEN_2,
        fc_hidden=LSTM_FC,
        dropout=LSTM_DROPOUT,
    ).to(device)

    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pw], dtype=torch.float32).to(device)
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LSTM_LR, weight_decay=LSTM_WD)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=3
    )

    best_f1, best_ep, patience_cnt = -1.0, 0, 0
    ckpt_path = os.path.join(models_dir, "lstm_model_1d.pt")

    for epoch in range(1, LSTM_EPOCHS + 1):
        # Train
        model.train()
        for X_b, y_b in tr_loader:
            logits = model(X_b.to(device))
            loss   = criterion(logits, y_b.to(device))
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        # Validate
        model.eval()
        val_preds = []
        with torch.no_grad():
            for X_b, _ in val_loader:
                pr = torch.sigmoid(model(X_b.to(device))).cpu().numpy()
                val_preds.extend((pr >= 0.5).astype(int))

        vf1 = f1_score(y_val.astype(int), val_preds, zero_division=0)
        scheduler.step(vf1)

        marker = ""
        if vf1 > best_f1:
            best_f1, best_ep, patience_cnt = vf1, epoch, 0
            torch.save(model.state_dict(), ckpt_path)
            marker = " *best*"
        else:
            patience_cnt += 1

        if epoch <= 5 or epoch % 5 == 0 or marker:
            print(f"    Epoch {epoch:3d} | Val F1: {vf1:.4f}{marker}")

        if patience_cnt >= LSTM_PATIENCE:
            print(f"    Early stop at epoch {epoch} (best: {best_ep})")
            break

    print(f"  Best Val F1: {best_f1:.4f} at epoch {best_ep}")

    # ── Evaluate on test ─────────────────────────────────────────────────────
    model.load_state_dict(torch.load(ckpt_path, map_location=device))
    model.eval()

    te_probs, te_preds = [], []
    with torch.no_grad():
        for X_b, _ in te_loader:
            pr = torch.sigmoid(model(X_b.to(device))).cpu().numpy()
            te_probs.extend(pr)
            te_preds.extend((pr >= 0.5).astype(int))

    acc = accuracy_score(y_test.astype(int), te_preds)
    f1  = f1_score(y_test.astype(int), te_preds, zero_division=0)
    auc = roc_auc_score(y_test.astype(int), te_probs)

    print(f"  Test — Acc: {acc:.4f} | F1: {f1:.4f} | AUC: {auc:.4f}")

    # ── Save scaler ──────────────────────────────────────────────────────────
    scaler_path = os.path.join(models_dir, "scaler_1d.pkl")
    joblib.dump(scaler, scaler_path)
    print(f"  Saved: {ckpt_path}")
    print(f"  Saved: {scaler_path}")

    return {"acc": acc, "f1": f1, "auc": auc}


# Main Retrain Entry Point

def retrain_1d_models(project_root):
    print("\n" + "=" * 60)
    print("  RETRAIN 1D MODELS")
    print("  (RF, XGBoost, LSTM — 5D/10D unchanged)")
    print("=" * 60)

    raw_path   = os.path.join(project_root, "data", "raw_data.csv")
    models_dir = os.path.join(project_root, "models")
    config_path = os.path.join(project_root, "config", "model_weights.json")

    # ── Load data ────────────────────────────────────────────────────────────
    print("\n  Loading raw data...")
    raw = pd.read_csv(raw_path, parse_dates=["date"])
    print(f"  Raw data: {len(raw):,} rows, {raw['ticker'].nunique()} tickers")

    # ── Prepare training data (horizon=1) ────────────────────────────────────
    print("\n  Preparing training data (1D horizon)...")
    X_train, y_train, X_val, y_val, X_test, y_test = prepare_training_data(
        raw, horizon=1
    )

    # ── Retrain each model ───────────────────────────────────────────────────
    results = {}
    results["rf"]   = retrain_rf_1d(X_train, y_train, X_val, y_val, X_test, y_test, models_dir)
    results["xgb"]  = retrain_xgb_1d(X_train, y_train, X_val, y_val, X_test, y_test, models_dir)
    results["lstm"] = retrain_lstm_1d(X_train, y_train, X_val, y_val, X_test, y_test, models_dir)

    # ── Update AUC weights ───────────────────────────────────────────────────
    print("\n── Updating AUC weights ──────────────────────────────────────")
    with open(config_path, "r") as f:
        weights = json.load(f)

    weights["1d"] = {
        "rf":   round(results["rf"]["auc"], 4),
        "xgb":  round(results["xgb"]["auc"], 4),
        "lstm": round(results["lstm"]["auc"], 4),
    }

    with open(config_path, "w") as f:
        json.dump(weights, f, indent=4)
    print(f"  Updated 1D weights: {weights['1d']}")
    print(f"  5D/10D weights unchanged: {weights['5d']}, {weights['10d']}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RETRAIN COMPLETE")
    print("=" * 60)
    for name, r in results.items():
        print(f"  {name.upper():5s} — Acc: {r['acc']:.4f} | F1: {r['f1']:.4f} | AUC: {r['auc']:.4f}")

    return results


# Standalone execution: python -m utils.retrain

if __name__ == "__main__":
    retrain_1d_models(PROJECT_ROOT)
