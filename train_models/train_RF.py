#!/usr/bin/env python
# coding: utf-8

# # 1. Configuration & Initial Setup

# In[1]:


import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, roc_auc_score
)
import warnings
warnings.filterwarnings("ignore")

# ── Configuration ────────────────────────────────────────────────────────────
RAW_FILE      = "data/raw_data.csv"
WINDOW_RAW    = 55    
WINDOW_KEEP   = 20    
WARMUP        = WINDOW_RAW - WINDOW_KEEP  
BUY_THRESHOLD = 0.50  

TRAIN_RATIO   = 0.80
VAL_RATIO     = 0.10
TEST_RATIO    = 0.10

print(f"Global RF Model V2")
print(f"Window (raw)  : {WINDOW_RAW} days")
print(f"Window (keep) : {WINDOW_KEEP} days")
print(f"Buy threshold : {BUY_THRESHOLD}")
print(f"Split         : {TRAIN_RATIO:.0%} / {VAL_RATIO:.0%} / {TEST_RATIO:.0%}")


# # 2. Data Preparation & Feature Engineering
# Computes technical indicators and creates default 1D label.

# In[2]:


raw = pd.read_csv(RAW_FILE, parse_dates=["date"])

if "ticker_id" not in raw.columns:
    unique_tickers = raw["ticker"].unique()
    ticker_to_id = {t: i+1 for i, t in enumerate(unique_tickers)}
    raw["ticker_id"] = raw["ticker"].map(ticker_to_id)

raw = raw.sort_values(["ticker", "date"]).reset_index(drop=True)
raw["temp_ret_1d"] = raw.groupby("ticker")["close"].pct_change(1)

market_proxy = raw.groupby("date")["temp_ret_1d"].mean().reset_index()
market_proxy.rename(columns={"temp_ret_1d": "market_ret_1d"}, inplace=True)
raw = pd.merge(raw, market_proxy, on="date", how="left")

def compute_rsi(series, window=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_atr(high, low, close, window=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/window, min_periods=window, adjust=False).mean()

def compute_obv(close, volume):
    sign = np.sign(close.diff()).fillna(0)
    return (sign * volume).cumsum()

def process_ticker(df):
    c, o, h, lo, v = df["close"], df["open"], df["high"], df["low"], df["volume"].astype(float)
    hl = h - lo

    df["hl_range"]       = hl / c
    df["body_ratio"]     = (c - o).abs() / hl.replace(0, np.nan)
    df["close_position"] = (c - lo) / hl.replace(0, np.nan)
    df["return_1d"]      = c.pct_change(1)

    obv = compute_obv(c, v)
    obv_lag5 = obv.shift(5)
    df["obv_change"]     = (obv - obv_lag5) / obv_lag5.abs().replace(0, np.nan)
    df["return_5d"]      = c.pct_change(5)
    df["rsi"]            = compute_rsi(c, window=14)
    df["atr_ratio"]      = compute_atr(h, lo, c, window=14) / c

    ema3  = c.ewm(span=3,  adjust=False).mean()
    ema10 = c.ewm(span=10, adjust=False).mean()
    df["ema_ratio"]      = ema3 / ema10 - 1

    bb_mid   = c.rolling(10).mean()
    bb_std   = c.rolling(10).std(ddof=0)
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    df["bb_pctb"]        = (c - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    vol_ma10 = v.rolling(10).mean()
    df["volume_ratio"]   = v / vol_ma10.replace(0, np.nan)

    ret   = c.pct_change(1)
    std4  = ret.rolling(4).std()
    std10 = ret.rolling(10).std()
    df["vol_trend"]      = std4 / std10.replace(0, np.nan)

    macd_line = c.ewm(span=5,  adjust=False).mean() - c.ewm(span=10, adjust=False).mean()
    signal    = macd_line.ewm(span=5, adjust=False).mean()
    df["macd_hist"]      = macd_line - signal

    df["relative_strength"] = df["return_1d"] - df["market_ret_1d"]

    df["label"] = (df["close"].shift(-1) > df["close"]).astype(int)

    return df.iloc[WARMUP:-1].reset_index(drop=True)


# # 3. Sliding Window Creation & Chronological Splitting
# Applies outlier clipping, builds 20-day rolling windows (flattened to 1D for RF), and splits into Train/Val/Test.

# In[3]:


processed_frames = []
for ticker, grp in raw.groupby("ticker"):
    res = process_ticker(grp.copy())
    processed_frames.append(res)

global_df = pd.concat(processed_frames, ignore_index=True)

FEATURE_COLS = [
    "ticker_id",
    "hl_range", "body_ratio", "close_position",
    "return_1d", "obv_change", "return_5d",
    "rsi", "atr_ratio", "ema_ratio",
    "bb_pctb", "volume_ratio", "vol_trend", "macd_hist",
    "market_ret_1d", "relative_strength"
]

global_df = global_df.replace([np.inf, -np.inf], np.nan)
global_df = global_df.dropna(subset=FEATURE_COLS + ["label"]).reset_index(drop=True)

# Outlier Clipping
for col in FEATURE_COLS:
    if col == "ticker_id": continue
    p01 = global_df[col].quantile(0.01)
    p99 = global_df[col].quantile(0.99)
    global_df[col] = global_df[col].clip(lower=p01, upper=p99)

W = WINDOW_KEEP

X_list = []
y_list = []
dates  = []
tickers_list = []

for ticker, grp in global_df.groupby("ticker"):
    grp = grp.reset_index(drop=True)
    for i in range(W - 1, len(grp)):
        window = grp[FEATURE_COLS].iloc[i - W + 1 : i + 1].values
        # Cán phẳng matrix (20, 16) thành (320,)
        X_list.append(window.flatten())                              
        y_list.append(int(grp["label"].iloc[i]))
        dates.append(grp["date"].iloc[i])
        tickers_list.append(ticker)

X       = np.array(X_list, dtype=np.float32)
y       = np.array(y_list, dtype=np.float32)
dates   = np.array(dates)
tickers = np.array(tickers_list)

# Global Date Sort for splits
sort_idx = np.argsort(dates)
X       = X[sort_idx]
y       = y[sort_idx]
dates   = dates[sort_idx]
tickers = tickers[sort_idx]

n = len(X)
train_end = int(n * TRAIN_RATIO)
val_end   = int(n * (TRAIN_RATIO + VAL_RATIO))

X_train, y_train, d_train, t_train = X[:train_end], y[:train_end], dates[:train_end], tickers[:train_end]
X_val,   y_val,   d_val,   t_val   = X[train_end:val_end], y[train_end:val_end], dates[train_end:val_end], tickers[train_end:val_end]
X_test,  y_test,  d_test,  t_test  = X[val_end:], y[val_end:], dates[val_end:], tickers[val_end:]

print(f"X_train shape : {X_train.shape}  ({len(FEATURE_COLS)} features × {W} days)")
print(f"Label dist 1D : 0: {sum(y_train == 0)}, 1: {sum(y_train == 1)}")


# # 4. Train & Evaluate Random Forest (1-Day Horizon)
# Handles class imbalance by mapping XGBoost-like scale_pos_weight dynamic ratio into RandomForest class_weight feature.

# In[4]:


# Random Forest Class Imbalance Handling for 1D horizon
# Matches XGBoost scale_pos_weight
ratio_1d = float(sum(y_train == 0) / sum(y_train == 1))
class_weight_1d = {0: 1.0, 1: ratio_1d}

print(f"Using class weights for 1D: {class_weight_1d}")

rf_1d = RandomForestClassifier(
    n_estimators=1000,
    max_depth=10,            
    min_samples_leaf=30,
    max_features="sqrt",
    class_weight=class_weight_1d, # Replaces "balanced" to match XGBoost scale_pos_weight
    random_state=42,
    n_jobs=-1,
)

rf_1d.fit(X_train, y_train)

prob_train = rf_1d.predict_proba(X_train)[:, 1]
prob_val   = rf_1d.predict_proba(X_val)[:, 1]
prob_test  = rf_1d.predict_proba(X_test)[:, 1]

pred_train = (prob_train >= BUY_THRESHOLD).astype(int)
pred_val   = (prob_val   >= BUY_THRESHOLD).astype(int)
pred_test  = (prob_test  >= BUY_THRESHOLD).astype(int)

def evaluate(y_true, y_pred, y_prob, set_name):
    acc  = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec  = recall_score(y_true, y_pred, zero_division=0)
    f1   = f1_score(y_true, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_true, y_prob)
    except:
        auc = float("nan")

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    print(f"\n{'='*60}")
    print(f"  {set_name} SET  (threshold = {BUY_THRESHOLD})")
    print(f"{'='*60}")
    print(f"  Accuracy  : {acc:.4f}")
    print(f"  Precision : {prec:.4f}")
    print(f"  Recall    : {rec:.4f}")
    print(f"  F1-score  : {f1:.4f}")
    print(f"  AUC-ROC   : {auc:.4f}")
    print(f"\n  Confusion Matrix:")
    print(f"                  Predicted")
    print(f"               Sell     Buy")
    print(f"  Actual Sell  {cm[0,0]:>5,}   {cm[0,1]:>5,}")
    print(f"  Actual Buy   {cm[1,0]:>5,}   {cm[1,1]:>5,}")

    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "auc": auc}

m_train = evaluate(y_train, pred_train, prob_train, "TRAIN")
m_val   = evaluate(y_val,   pred_val,   prob_val,   "VALIDATION")
m_test  = evaluate(y_test,  pred_test,  prob_test,  "TEST")


# # 5. Multi-Horizon Training (5-Day & 10-Day)
# Reprocesses target labels dynamically and trains models independently. Uses unweighted classes to parallel XGBoost setup for longer time windows.

# In[6]:


def train_and_evaluate_horizon(horizon, threshold=0.5):
    print(f"\n{'='*60}\n  HORIZON: {horizon} DAYS (Threshold: {threshold})\n{'='*60}")

    frames = []
    for ticker, grp in raw.groupby("ticker"):
        res = process_ticker(grp.copy())
        # Tạo label cho riêng horizon này (giống mô hình XGBoost module)
        shifted = res["close"].shift(-horizon)
        res["label"] = (shifted > res["close"]).astype(int)
        res = res.dropna(subset=["label"])
        frames.append(res)

    global_h = pd.concat(frames, ignore_index=True)
    global_h = global_h.replace([np.inf, -np.inf], np.nan)
    global_h = global_h.dropna(subset=FEATURE_COLS + ["label"]).reset_index(drop=True)

    # Outlier Clipping
    for col in FEATURE_COLS:
        if col == "ticker_id": continue
        p01 = global_h[col].quantile(0.01)
        p99 = global_h[col].quantile(0.99)
        global_h[col] = global_h[col].clip(lower=p01, upper=p99)

    X_list_h, y_list_h, dates_h = [], [], []
    for ticker, grp in global_h.groupby("ticker"):
        grp = grp.reset_index(drop=True)
        for i in range(W - 1, len(grp)):
            window = grp[FEATURE_COLS].iloc[i - W + 1 : i + 1].values
            X_list_h.append(window.flatten())
            y_list_h.append(int(grp["label"].iloc[i]))
            dates_h.append(grp["date"].iloc[i])

    Xh = np.array(X_list_h, dtype=np.float32)
    yh = np.array(y_list_h, dtype=np.float32)
    dates_h = np.array(dates_h)

    sort_idx = np.argsort(dates_h)
    Xh = Xh[sort_idx]
    yh = yh[sort_idx]

    nh = len(Xh)
    train_end = int(nh * TRAIN_RATIO)
    val_end   = int(nh * (TRAIN_RATIO + VAL_RATIO))

    Xh_train, yh_train = Xh[:train_end], yh[:train_end]
    Xh_val, yh_val     = Xh[train_end:val_end], yh[train_end:val_end]
    Xh_test, yh_test   = Xh[val_end:], yh[val_end:]

    print(f"Label dist {horizon}D train -> 0: {sum(yh_train == 0)}, 1: {sum(yh_train == 1)}")

    # XGBoost for 5D and 10D uses scale_pos_weight=1.0 (No heavy balancing)
    class_weight_h = "balanced"
    print(f"Using class weights for {horizon}D: {class_weight_h}")

    rf_h = RandomForestClassifier(
        n_estimators=500,
        max_depth=5,
        min_samples_leaf=150,
        max_features="sqrt",
        class_weight=class_weight_h, 
        random_state=42,
        n_jobs=-1,
    )
    rf_h.fit(Xh_train, yh_train)

    prob_test = rf_h.predict_proba(Xh_test)[:, 1]
    pred_test = (prob_test >= threshold).astype(int)

    evaluate(yh_test, pred_test, prob_test, f"TEST {horizon}D")

    return rf_h

rf_5d = train_and_evaluate_horizon(horizon=5, threshold=0.5)
rf_10d = train_and_evaluate_horizon(horizon=10, threshold=0.5)


# # 6. Save Models & Scalers
# Exports the trained models to the local disk.

# In[7]:


import joblib

os.makedirs("models", exist_ok=True)
joblib.dump(rf_1d, "models/rf_model_1d.pkl")
if 'rf_5d' in locals(): joblib.dump(rf_5d, "models/rf_model_5d.pkl")
if 'rf_10d' in locals(): joblib.dump(rf_10d, "models/rf_model_10d.pkl")
joblib.dump(FEATURE_COLS, "models/feature_cols_rf.pkl")

print("✅ Random Forest V2 models saved to 'models/' directory.")

