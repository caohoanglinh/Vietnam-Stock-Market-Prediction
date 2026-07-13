#!/usr/bin/env python
# coding: utf-8

# # Global LSTM — Multi-Ticker Stock Prediction
# 
# - **Input**: 20-day sliding window of 16 features (13 technical + market proxy + relative strength + ticker_id) computed over 12 stocks.
# - **Output**: Buy (1) vs Sell (0)
# - **Architecture**: 2-layer Stacked LSTM (hidden 128→64) + FC head
# - **Split**: 80% train / 10% val / 10% test (chronological globally across all stocks)
# 
# ---

# ## Cell 1 · Imports & Configuration

# In[18]:


import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
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
BUY_THRESHOLD = 0.5

TRAIN_RATIO   = 0.80
VAL_RATIO     = 0.10
TEST_RATIO    = 0.10

# ── LSTM Hyperparameters ─────────────────────────────────────────────────────
HIDDEN_SIZE_1  = 128
HIDDEN_SIZE_2  = 64
FC_HIDDEN      = 32
DROPOUT        = 0.3
BATCH_SIZE     = 512
LEARNING_RATE  = 1e-3
NUM_EPOCHS     = 50
EARLY_STOP     = 7        # patience (epochs without val improvement)
WEIGHT_DECAY   = 1e-4

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print(f"Global LSTM Model (All Tickers)")
print(f"Device         : {DEVICE}")
print(f"Window (raw)   : {WINDOW_RAW} days")
print(f"Window (keep)  : {WINDOW_KEEP} days")
print(f"Warm-up trim   : {WARMUP} days")
print(f"Buy threshold  : {BUY_THRESHOLD}")
print(f"Split          : {TRAIN_RATIO:.0%} / {VAL_RATIO:.0%} / {TEST_RATIO:.0%}")
print(f"Architecture   : LSTM({HIDDEN_SIZE_1}) → LSTM({HIDDEN_SIZE_2}) → FC({FC_HIDDEN}) → 1")


# ## Cell 2 · Load OHLCV & Compute 16 Features

# In[19]:


raw = pd.read_csv(RAW_FILE, parse_dates=["date"])

if "ticker_id" not in raw.columns:
    unique_tickers = raw["ticker"].unique()
    ticker_to_id = {t: i + 1 for i, t in enumerate(unique_tickers)}
    raw["ticker_id"] = raw["ticker"].map(ticker_to_id)

raw = raw.sort_values(["ticker", "date"]).reset_index(drop=True)
raw["temp_ret_1d"] = raw.groupby("ticker")["close"].pct_change(1)

market_proxy = raw.groupby("date")["temp_ret_1d"].mean().reset_index()
market_proxy.rename(columns={"temp_ret_1d": "market_ret_1d"}, inplace=True)
raw = pd.merge(raw, market_proxy, on="date", how="left")


def compute_rsi(series, window=14):
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_atr(high, low, close, window=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


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

    obv       = compute_obv(c, v)
    obv_lag5  = obv.shift(5)
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

# Outlier clipping (same as XGBoost pipeline)
for col in FEATURE_COLS:
    if col == "ticker_id":
        continue
    p01 = global_df[col].quantile(0.01)
    p99 = global_df[col].quantile(0.99)
    global_df[col] = global_df[col].clip(lower=p01, upper=p99)

print(f"Total rows after processing: {len(global_df):,}")
print(f"Features : {len(FEATURE_COLS)}")
print(f"Label    : {global_df['label'].value_counts().sort_index().to_dict()}")


# ## Cell 3 · Create Sliding Windows & Global Chronological Split

# In[20]:


W = WINDOW_KEEP

# Keep 3D shape (samples, timesteps, features) — key difference vs XGBoost
X_list       = []
y_list       = []
dates        = []
tickers_list = []

for ticker, grp in global_df.groupby("ticker"):
    grp = grp.reset_index(drop=True)
    for i in range(W - 1, len(grp)):
        window = grp[FEATURE_COLS].iloc[i - W + 1 : i + 1].values  # (20, 16)
        X_list.append(window)
        y_list.append(int(grp["label"].iloc[i]))
        dates.append(grp["date"].iloc[i])
        tickers_list.append(ticker)

X       = np.array(X_list, dtype=np.float32)   # (N, 20, 16)
y       = np.array(y_list, dtype=np.float32)    # (N,)
dates   = np.array(dates)
tickers = np.array(tickers_list)

# Sort chronologically (global time cut-off)
sort_idx = np.argsort(dates)
X        = X[sort_idx]
y        = y[sort_idx]
dates    = dates[sort_idx]
tickers  = tickers[sort_idx]

n         = len(X)
train_end = int(n * TRAIN_RATIO)
val_end   = int(n * (TRAIN_RATIO + VAL_RATIO))

X_train, y_train = X[:train_end],        y[:train_end]
X_val,   y_val   = X[train_end:val_end], y[train_end:val_end]
X_test,  y_test  = X[val_end:],          y[val_end:]
d_train          = dates[:train_end]
d_val            = dates[train_end:val_end]
d_test           = dates[val_end:]
t_test           = tickers[val_end:]

print(f"Input shape : {X.shape}  (samples, timesteps, features)")
print()
print(f"{'Set':<8} {'Rows':>7}  {'Date Range':<32}  {'Down':>6}  {'Up':>6}  {'Up%':>6}")
print("-" * 75)
for name, xs, ys, ds in [
    ("Train", X_train, y_train, d_train),
    ("Val",   X_val,   y_val,   d_val),
    ("Test",  X_test,  y_test,  d_test),
]:
    n0  = int((ys == 0).sum())
    n1  = int((ys == 1).sum())
    pct = n1 / len(ys) * 100
    d0  = pd.Timestamp(ds.min()).strftime('%Y-%m-%d')
    d1  = pd.Timestamp(ds.max()).strftime('%Y-%m-%d')
    print(f"{name:<8} {len(xs):>7,}  {d0} → {d1:<19}  {n0:>6,}  {n1:>6,}  {pct:>5.1f}%")


# ## Cell 4 · Feature Scaling & Dataset / DataLoader

# In[21]:


# ── StandardScaler: fit on train only, transform all sets ───────────────────
# Reshape to 2D to fit scaler, then reshape back to 3D
N_TRAIN, T, F = X_train.shape

scaler = StandardScaler()
X_train_2d = X_train.reshape(-1, F)
scaler.fit(X_train_2d)

X_train_scaled = scaler.transform(X_train.reshape(-1, F)).reshape(N_TRAIN, T, F)
X_val_scaled   = scaler.transform(X_val.reshape(-1, F)).reshape(len(X_val), T, F)
X_test_scaled  = scaler.transform(X_test.reshape(-1, F)).reshape(len(X_test), T, F)

print(f"Scaling done. Train mean ≈ {X_train_scaled.mean():.4f}, std ≈ {X_train_scaled.std():.4f}")


# ── PyTorch Dataset ──────────────────────────────────────────────────────────
class StockSequenceDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


train_dataset = StockSequenceDataset(X_train_scaled, y_train)
val_dataset   = StockSequenceDataset(X_val_scaled,   y_val)
test_dataset  = StockSequenceDataset(X_test_scaled,  y_test)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True,  num_workers=0, pin_memory=True)
val_loader   = DataLoader(val_dataset,   batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True)
test_loader  = DataLoader(test_dataset,  batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True)

print(f"Train batches : {len(train_loader)}")
print(f"Val   batches : {len(val_loader)}")
print(f"Test  batches : {len(test_loader)}")


# ## Cell 5 · Model Definition

# In[22]:


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
        # x: (batch, seq_len, input_size)
        out1, _      = self.lstm1(x)           # (batch, seq_len, hidden1)
        out1         = self.dropout1(out1)
        out2, _      = self.lstm2(out1)         # (batch, seq_len, hidden2)
        last_hidden  = out2[:, -1, :]           # (batch, hidden2) — last timestep
        normed       = self.norm(last_hidden)
        logit        = self.fc(normed)          # (batch, 1)
        return logit.squeeze(1)                 # (batch,)


model = StackedLSTMClassifier(
    input_size=len(FEATURE_COLS),
    hidden_size1=HIDDEN_SIZE_1,
    hidden_size2=HIDDEN_SIZE_2,
    fc_hidden=FC_HIDDEN,
    dropout=DROPOUT,
).to(DEVICE)

total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(model)
print(f"\nTrainable parameters: {total_params:,}")


# ## Cell 6 · Training with Early Stopping

# In[23]:


# ── Class-imbalance weight (equivalent to scale_pos_weight in XGBoost) ───────
""" pos_weight_value = float((y_train == 0).sum() / (y_train == 1).sum())"""
ratio = float((y_train == 0).sum() / (y_train == 1).sum())
pos_weight_value = np.sqrt(ratio) 

pos_weight       = torch.tensor([pos_weight_value], dtype=torch.float32).to(DEVICE)

criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode="max", factor=0.5, patience=3
)

print(f"pos_weight      : {pos_weight_value:.4f}")
print(f"Optimizer       : AdamW (lr={LEARNING_RATE}, wd={WEIGHT_DECAY})")
print(f"LR Scheduler    : ReduceLROnPlateau (patience=3, factor=0.5)")
print(f"Early stopping  : {EARLY_STOP} epochs without val F1 improvement")
print()


def run_epoch(loader, train: bool):
    """Run one epoch; return (avg_loss, accuracy, f1)."""
    if train:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    all_labels, all_preds = [], []

    ctx = torch.no_grad() if not train else torch.enable_grad()
    with ctx:
        for X_batch, y_batch in loader:
            X_batch = X_batch.to(DEVICE)
            y_batch = y_batch.to(DEVICE)

            logits = model(X_batch)
            loss   = criterion(logits, y_batch)

            if train:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # gradient clipping
                optimizer.step()

            total_loss += loss.item() * len(y_batch)
            preds = (torch.sigmoid(logits) >= BUY_THRESHOLD).long().cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(y_batch.long().cpu().numpy())

    avg_loss = total_loss / len(loader.dataset)
    acc      = accuracy_score(all_labels, all_preds)
    f1       = f1_score(all_labels, all_preds, zero_division=0)
    return avg_loss, acc, f1


# ── Training Loop ─────────────────────────────────────────────────────────────
best_val_f1    = -1.0
best_epoch     = 0
patience_count = 0
history        = []

os.makedirs("models", exist_ok=True)
CHECKPOINT_PATH = "models/lstm_best.pt"

print(f"{'Ep':>4}  {'Train Loss':>10}  {'Train Acc':>9}  {'Train F1':>8}  "
      f"{'Val Loss':>9}  {'Val Acc':>8}  {'Val F1':>7}")
print("-" * 72)

for epoch in range(1, NUM_EPOCHS + 1):
    tr_loss, tr_acc, tr_f1 = run_epoch(train_loader, train=True)
    vl_loss, vl_acc, vl_f1 = run_epoch(val_loader,   train=False)

    scheduler.step(vl_f1)
    history.append({"epoch": epoch, "tr_loss": tr_loss, "tr_f1": tr_f1,
                    "vl_loss": vl_loss, "vl_f1": vl_f1})

    marker = ""
    if vl_f1 > best_val_f1:
        best_val_f1    = vl_f1
        best_epoch     = epoch
        patience_count = 0
        torch.save(model.state_dict(), CHECKPOINT_PATH)
        marker = "  ✅ best"
    else:
        patience_count += 1

    print(f"{epoch:>4}  {tr_loss:>10.4f}  {tr_acc:>9.4f}  {tr_f1:>8.4f}  "
          f"{vl_loss:>9.4f}  {vl_acc:>8.4f}  {vl_f1:>7.4f}{marker}")

    if patience_count >= EARLY_STOP:
        print(f"\nEarly stopping at epoch {epoch}  (best epoch: {best_epoch})")
        break

print(f"\nTraining complete. Best Val F1 = {best_val_f1:.4f} at epoch {best_epoch}")


# ## Cell 7 · Evaluation on All Sets

# In[24]:


# Load the best checkpoint before evaluation
model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE))
model.eval()


def get_predictions(loader):
    """Return (probabilities, predicted labels) for a DataLoader."""
    all_probs, all_preds = [], []
    with torch.no_grad():
        for X_batch, _ in loader:
            logits = model(X_batch.to(DEVICE))
            probs  = torch.sigmoid(logits).cpu().numpy()
            preds  = (probs >= BUY_THRESHOLD).astype(int)
            all_probs.extend(probs)
            all_preds.extend(preds)
    return np.array(all_probs), np.array(all_preds)


def evaluate(y_true, y_pred, y_prob, set_name):
    acc  = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec  = recall_score(y_true, y_pred, zero_division=0)
    f1   = f1_score(y_true, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_true, y_prob)
    except Exception:
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


prob_train, pred_train = get_predictions(train_loader)
prob_val,   pred_val   = get_predictions(val_loader)
prob_test,  pred_test  = get_predictions(test_loader)

m_train = evaluate(y_train.astype(int), pred_train, prob_train, "TRAIN")
m_val   = evaluate(y_val.astype(int),   pred_val,   prob_val,   "VALIDATION")
m_test  = evaluate(y_test.astype(int),  pred_test,  prob_test,  "TEST")

print(f"\n{'='*60}\n  SUMMARY\n{'='*60}")
summary_df = pd.DataFrame({"Train": m_train, "Val": m_val, "Test": m_test}).T
print(summary_df.round(4).to_string())

gap = m_train["f1"] - m_test["f1"]
print(f"\n  Train-Test F1 gap: {gap:.4f}")


# ## Cell 8 · Multi-Horizon Training (5d & 10d)

# In[25]:


def train_and_evaluate_horizon(horizon: int, threshold: float = 0.5):
    print(f"\n{'='*60}\n  HORIZON: {horizon} DAYS\n{'='*60}")

    # ── Rebuild features with new label ──────────────────────────────────────
    df = raw.copy()
    frames = []
    for ticker, grp in df.groupby("ticker"):
        res = process_ticker(grp.copy())
        shifted       = res["close"].shift(-horizon)
        res["label"]  = (shifted > res["close"]).astype(int)
        res           = res.dropna(subset=["label"] + FEATURE_COLS)
        frames.append(res)

    global_h = pd.concat(frames, ignore_index=True)
    global_h = global_h.replace([np.inf, -np.inf], np.nan)
    global_h = global_h.dropna(subset=FEATURE_COLS + ["label"]).reset_index(drop=True)

    for col in FEATURE_COLS:
        if col == "ticker_id":
            continue
        p01 = global_h[col].quantile(0.01)
        p99 = global_h[col].quantile(0.99)
        global_h[col] = global_h[col].clip(lower=p01, upper=p99)

    # ── Build windows ─────────────────────────────────────────────────────────
    X_list_h, y_list_h, dates_h = [], [], []
    for ticker, grp in global_h.groupby("ticker"):
        grp = grp.reset_index(drop=True)
        for i in range(W - 1, len(grp)):
            window = grp[FEATURE_COLS].iloc[i - W + 1 : i + 1].values
            X_list_h.append(window)
            y_list_h.append(int(grp["label"].iloc[i]))
            dates_h.append(grp["date"].iloc[i])

    Xh     = np.array(X_list_h, dtype=np.float32)
    yh     = np.array(y_list_h, dtype=np.float32)
    dates_h = np.array(dates_h)

    sort_idx = np.argsort(dates_h)
    Xh       = Xh[sort_idx]
    yh       = yh[sort_idx]

    nh         = len(Xh)
    tr_end_h   = int(nh * TRAIN_RATIO)
    val_end_h  = int(nh * (TRAIN_RATIO + VAL_RATIO))

    Xh_train, yh_train = Xh[:tr_end_h],          yh[:tr_end_h]
    Xh_val,   yh_val   = Xh[tr_end_h:val_end_h], yh[tr_end_h:val_end_h]
    Xh_test,  yh_test  = Xh[val_end_h:],          yh[val_end_h:]

    # ── Scale ─────────────────────────────────────────────────────────────────
    _, T_h, F_h = Xh_train.shape
    sc_h = StandardScaler()
    sc_h.fit(Xh_train.reshape(-1, F_h))
    Xh_train_s = sc_h.transform(Xh_train.reshape(-1, F_h)).reshape(len(Xh_train), T_h, F_h)
    Xh_val_s   = sc_h.transform(Xh_val.reshape(-1, F_h)).reshape(len(Xh_val), T_h, F_h)
    Xh_test_s  = sc_h.transform(Xh_test.reshape(-1, F_h)).reshape(len(Xh_test), T_h, F_h)

    # ── DataLoaders ───────────────────────────────────────────────────────────
    tr_loader_h  = DataLoader(StockSequenceDataset(Xh_train_s, yh_train), batch_size=BATCH_SIZE, shuffle=True)
    val_loader_h = DataLoader(StockSequenceDataset(Xh_val_s,   yh_val),   batch_size=BATCH_SIZE, shuffle=False)
    te_loader_h  = DataLoader(StockSequenceDataset(Xh_test_s,  yh_test),  batch_size=BATCH_SIZE, shuffle=False)

    # ── Model ─────────────────────────────────────────────────────────────────
    """pw_h = float((yh_train == 0).sum() / max((yh_train == 1).sum(), 1))"""

    pw_h = 1.0

    model_h = StackedLSTMClassifier(
        input_size=F_h, hidden_size1=HIDDEN_SIZE_1, hidden_size2=HIDDEN_SIZE_2,
        fc_hidden=FC_HIDDEN, dropout=DROPOUT
    ).to(DEVICE)
    crit_h = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pw_h]).to(DEVICE))
    opt_h  = torch.optim.AdamW(model_h.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    sch_h  = torch.optim.lr_scheduler.ReduceLROnPlateau(opt_h, mode="max", factor=0.5, patience=3)

    best_f1_h, best_ep_h, pat_h = -1.0, 0, 0
    ckpt_h = f"models/lstm_best_{horizon}d.pt"

    for epoch in range(1, NUM_EPOCHS + 1):
        # train
        model_h.train()
        for X_b, y_b in tr_loader_h:
            logits = model_h(X_b.to(DEVICE))
            loss   = crit_h(logits, y_b.to(DEVICE))
            opt_h.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(model_h.parameters(), 1.0)
            opt_h.step()
        # val
        model_h.eval()
        vp, vl_preds = [], []
        with torch.no_grad():
            for X_b, _ in val_loader_h:
                pr = torch.sigmoid(model_h(X_b.to(DEVICE))).cpu().numpy()
                vp.extend(pr)
                vl_preds.extend((pr >= threshold).astype(int))
        vf1 = f1_score(yh_val.astype(int), vl_preds, zero_division=0)
        sch_h.step(vf1)
        if vf1 > best_f1_h:
            best_f1_h, best_ep_h, pat_h = vf1, epoch, 0
            torch.save(model_h.state_dict(), ckpt_h)
        else:
            pat_h += 1
        if pat_h >= EARLY_STOP:
            break

    print(f"Best Val F1: {best_f1_h:.4f} at epoch {best_ep_h}")

    # ── Test evaluation ───────────────────────────────────────────────────────
    model_h.load_state_dict(torch.load(ckpt_h, map_location=DEVICE))
    model_h.eval()
    te_probs, te_preds = [], []
    with torch.no_grad():
        for X_b, _ in te_loader_h:
            pr = torch.sigmoid(model_h(X_b.to(DEVICE))).cpu().numpy()
            te_probs.extend(pr)
            te_preds.extend((pr >= threshold).astype(int))

    evaluate(yh_test.astype(int), np.array(te_preds), np.array(te_probs), f"TEST {horizon}D")

    return model_h, sc_h


# In[26]:


lstm_5d, scaler_5d = train_and_evaluate_horizon(horizon=5, threshold=0.5)


# In[27]:


lstm_10d, scaler_10d = train_and_evaluate_horizon(horizon=10, threshold=0.5)


# In[28]:


import joblib
import os

# Create models directory if not exists
os.makedirs("models", exist_ok=True)

# 1. Save Model State Dicts (PyTorch best practice)
torch.save(model.state_dict(), "models/lstm_model_1d.pt")

if 'lstm_5d' in locals():
    torch.save(lstm_5d.state_dict(), "models/lstm_model_5d.pt")
if 'lstm_10d' in locals():
    torch.save(lstm_10d.state_dict(), "models/lstm_model_10d.pt")

# 2. Save Scalers (Crucial for inference to ensure same normalization)
joblib.dump(scaler, "models/scaler_1d.pkl")

if 'scaler_5d' in locals():
    joblib.dump(scaler_5d, "models/scaler_5d.pkl")
if 'scaler_10d' in locals():
    joblib.dump(scaler_10d, "models/scaler_10d.pkl")

# 3. Save feature columns for consistency
joblib.dump(FEATURE_COLS, "models/feature_cols_lstm.pkl")

print("✅ All LSTM models and scalers saved to 'models/' directory.")


# In[29]:


# --- PREDICTIONS FOR ALL TICKERS ON LATEST DATE ---
model.eval()
latest_date = d_test[-1]
mask_latest = (d_test == latest_date)

# Get scaled data for the latest day
X_latest_scaled = X_test_scaled[mask_latest]
t_latest_day = t_test[mask_latest]

# Convert numpy to torch tensor for inference
X_tensor = torch.tensor(X_latest_scaled, dtype=torch.float32).to(DEVICE)

with torch.no_grad():
    logits = model(X_tensor)
    # Apply sigmoid to get probabilities (0 to 1)
    probs = torch.sigmoid(logits).cpu().numpy()

# Build prediction table
all_predictions = pd.DataFrame({
    'Ticker'  : t_latest_day,
    'Date'    : pd.to_datetime([latest_date] * len(t_latest_day)).strftime('%Y-%m-%d'),
    'Prob_Buy': probs,
    'Decision': ["BUY" if p >= BUY_THRESHOLD else "SELL" for p in probs]
})

# Sort by highest probability
all_predictions = all_predictions.sort_values(by='Prob_Buy', ascending=False).reset_index(drop=True)

print(f"--- LSTM PREDICTIONS FOR ALL TICKERS (Date: {all_predictions['Date'].iloc[0]}) ---")
print(f"Total Tickers found: {len(all_predictions)}")
print("-" * 60)
print(all_predictions.to_string(index=False))

# Show only BUY signals
buy_signals = all_predictions[all_predictions['Decision'] == "BUY"]
print("\n" + "="*60)
print(f"⭐ TOP BUY SIGNALS ({len(buy_signals)} symbols)")
print("="*60)
if not buy_signals.empty:
    print(buy_signals.to_string(index=False))
else:
    print("No BUY signals found for current threshold.")

