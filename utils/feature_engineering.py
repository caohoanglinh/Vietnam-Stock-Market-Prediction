"""
Feature Engineering Module
==========================
Shared between training notebooks and inference pipeline.
Computes 16 features for stock prediction models.

Features (16 total):
  1. ticker_id           — static per-ticker integer ID
  2. hl_range            — (high - low) / close
  3. body_ratio          — |close - open| / (high - low)
  4. close_position      — (close - low) / (high - low)
  5. return_1d           — 1-day close return
  6. obv_change          — OBV change over 5 days
  7. return_5d           — 5-day close return
  8. rsi                 — RSI-14 (EWM)
  9. atr_ratio           — ATR-14 / close
 10. ema_ratio           — EMA3/EMA10 - 1
 11. bb_pctb             — Bollinger %B (window=10)
 12. volume_ratio        — volume / MA10(volume)
 13. vol_trend           — rolling_std(4) / rolling_std(10)
 14. macd_hist           — MACD histogram (5/10/5)
 15. market_ret_1d       — avg return across all tickers
 16. relative_strength   — return_1d - market_ret_1d
"""

import numpy as np
import pandas as pd


# ── Feature column definition (must match training notebooks exactly) ────────
FEATURE_COLS = [
    "ticker_id",
    "hl_range", "body_ratio", "close_position",
    "return_1d", "obv_change", "return_5d",
    "rsi", "atr_ratio", "ema_ratio",
    "bb_pctb", "volume_ratio", "vol_trend", "macd_hist",
    "market_ret_1d", "relative_strength",
]

# ── Configuration ────────────────────────────────────────────────────────────
WINDOW_RAW  = 55   # Total days needed for feature warmup
WINDOW_KEEP = 20   # Days to keep in sliding window
WARMUP      = WINDOW_RAW - WINDOW_KEEP  # = 35


# Technical Indicator Helpers (identical to training notebooks)

def compute_rsi(series, window=14):
    """Compute RSI using EWM method."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_atr(high, low, close, window=14):
    """Compute Average True Range using EWM method."""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def compute_obv(close, volume):
    """Compute On-Balance Volume."""
    sign = np.sign(close.diff()).fillna(0)
    return (sign * volume).cumsum()


# Per-Ticker Feature Computation

def compute_ticker_features(df):
    """
    Compute 13 technical features for a single ticker DataFrame.
    Does NOT compute market_ret_1d / relative_strength (cross-ticker).
    Does NOT compute label (not needed for inference).

    Args:
        df: DataFrame sorted by date, with [date, open, high, low, close, volume]

    Returns:
        Same DataFrame with 13 feature columns added.
    """
    c  = df["close"]
    o  = df["open"]
    h  = df["high"]
    lo = df["low"]
    v  = df["volume"].astype(float)
    hl = h - lo

    df["hl_range"]       = hl / c
    df["body_ratio"]     = (c - o).abs() / hl.replace(0, np.nan)
    df["close_position"] = (c - lo) / hl.replace(0, np.nan)
    df["return_1d"]      = c.pct_change(1)

    obv      = compute_obv(c, v)
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

    return df


# Full Pipeline: Raw OHLCV → Featured DataFrame

def prepare_featured_data(raw_df, tickers_list=None):
    """
    Compute all 16 features from raw OHLCV data.

    Args:
        raw_df: DataFrame with columns [date, open, high, low, close, volume, ticker, ticker_id]
        tickers_list: Optional list of tickers to process. If None, process all.

    Returns:
        DataFrame with all 16 feature columns, sorted by [ticker, date].
    """
    df = raw_df.copy()
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # ── Market return (cross-ticker) ─────────────────────────────────────────
    df["temp_ret_1d"] = df.groupby("ticker")["close"].pct_change(1)
    market_proxy = df.groupby("date")["temp_ret_1d"].mean().reset_index()
    market_proxy.rename(columns={"temp_ret_1d": "market_ret_1d"}, inplace=True)
    df = pd.merge(df, market_proxy, on="date", how="left")
    df.drop(columns=["temp_ret_1d"], inplace=True)

    # ── Filter tickers if specified ──────────────────────────────────────────
    if tickers_list is not None:
        df = df[df["ticker"].isin(tickers_list)]

    # ── Ensure ticker_id exists ──────────────────────────────────────────────
    if "ticker_id" not in df.columns:
        unique_tickers = sorted(df["ticker"].unique())
        ticker_to_id = {t: i + 1 for i, t in enumerate(unique_tickers)}
        df["ticker_id"] = df["ticker"].map(ticker_to_id)

    # ── Per-ticker technical features ────────────────────────────────────────
    frames = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.copy().reset_index(drop=True)
        grp = compute_ticker_features(grp)
        grp["relative_strength"] = grp["return_1d"] - grp["market_ret_1d"]
        frames.append(grp)

    result = pd.concat(frames, ignore_index=True)
    result = result.replace([np.inf, -np.inf], np.nan)

    return result


def extract_inference_windows(featured_df, window_keep=WINDOW_KEEP):
    """
    Extract the latest sliding window for each ticker for model inference.

    Args:
        featured_df: DataFrame with all 16 features (output of prepare_featured_data).
        window_keep: Number of timesteps in sliding window (default 20).

    Returns:
        windows: dict {ticker: np.array shape (window_keep, 16)}
        prediction_date: the latest date in the data (pd.Timestamp)
        skipped: list of tickers that were skipped (insufficient data)
    """
    windows = {}
    skipped = []
    prediction_date = None

    for ticker, grp in featured_df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)

        # Drop rows with NaN in any feature column
        grp_clean = grp.dropna(subset=FEATURE_COLS)

        if len(grp_clean) < window_keep:
            print(f"  [WARN] {ticker}: only {len(grp_clean)} clean rows, need {window_keep}. Skipping.")
            skipped.append(ticker)
            continue

        # Take last window_keep rows
        window_df = grp_clean.tail(window_keep)
        window = window_df[FEATURE_COLS].values.astype(np.float32)  # (20, 16)
        windows[ticker] = window

        # Track latest date
        latest_date = grp_clean["date"].iloc[-1]
        if prediction_date is None or latest_date > prediction_date:
            prediction_date = latest_date

    return windows, prediction_date, skipped


# Training Pipeline: Full Featured Data with Labels + Split

def prepare_training_data(raw_df, horizon=1, train_ratio=0.80, val_ratio=0.10):
    """
    Prepare complete training data: features + labels + chronological split.
    Used by retrain.py.

    Args:
        raw_df: Raw OHLCV DataFrame.
        horizon: Prediction horizon in days (1, 5, or 10).
        train_ratio, val_ratio: Split ratios. Test = 1 - train - val.

    Returns:
        X_train, y_train, X_val, y_val, X_test, y_test: numpy arrays
        X arrays have shape (N, WINDOW_KEEP, len(FEATURE_COLS))
        y arrays have shape (N,)
    """
    # Compute features
    featured_df = prepare_featured_data(raw_df)

    # ── Add labels per ticker ────────────────────────────────────────────────
    frames = []
    for ticker, grp in featured_df.groupby("ticker"):
        grp = grp.copy().sort_values("date").reset_index(drop=True)

        # Label: close[t + horizon] > close[t]
        shifted = grp["close"].shift(-horizon)
        grp["label"] = (shifted > grp["close"]).astype(int)

        # Drop rows without features or label
        grp = grp.dropna(subset=FEATURE_COLS + ["label"])

        # Outlier clipping (1st-99th percentile, per training notebooks)
        for col in FEATURE_COLS:
            if col == "ticker_id":
                continue
            p01 = grp[col].quantile(0.01)
            p99 = grp[col].quantile(0.99)
            grp[col] = grp[col].clip(lower=p01, upper=p99)

        frames.append(grp)

    global_df = pd.concat(frames, ignore_index=True)

    # ── Build sliding windows ────────────────────────────────────────────────
    W = WINDOW_KEEP
    X_list, y_list, dates_list = [], [], []

    for ticker, grp in global_df.groupby("ticker"):
        grp = grp.reset_index(drop=True)
        for i in range(W - 1, len(grp)):
            window = grp[FEATURE_COLS].iloc[i - W + 1 : i + 1].values  # (20, 16)
            X_list.append(window)
            y_list.append(int(grp["label"].iloc[i]))
            dates_list.append(grp["date"].iloc[i])

    X      = np.array(X_list, dtype=np.float32)   # (N, 20, 16)
    y      = np.array(y_list, dtype=np.float32)    # (N,)
    dates  = np.array(dates_list)

    # ── Sort chronologically (global) ────────────────────────────────────────
    sort_idx = np.argsort(dates)
    X     = X[sort_idx]
    y     = y[sort_idx]

    # ── Chronological split ──────────────────────────────────────────────────
    n         = len(X)
    train_end = int(n * train_ratio)
    val_end   = int(n * (train_ratio + val_ratio))

    X_train, y_train = X[:train_end],        y[:train_end]
    X_val,   y_val   = X[train_end:val_end], y[train_end:val_end]
    X_test,  y_test  = X[val_end:],          y[val_end:]

    print(f"  Horizon {horizon}D | Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")
    print(f"  Label distribution — Train: {int(y_train.sum()):,} buy / {int((y_train==0).sum()):,} sell")

    return X_train, y_train, X_val, y_val, X_test, y_test
