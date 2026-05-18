from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.feature_engineering import FEATURE_COLS, WINDOW_KEEP, prepare_featured_data


WEB_ROOT = PROJECT_ROOT / "web"
STATIC_DATA_DIR = WEB_ROOT / "static" / "data"
TICKER_DATA_DIR = STATIC_DATA_DIR / "tickers"
AVATAR_DIR = WEB_ROOT / "img" / "ava"
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw_data.csv"
DAILY_DIR = PROJECT_ROOT / "data" / "predictions" / "daily"
COMPARISON_DIR = PROJECT_ROOT / "data" / "predictions" / "comparison"
NEWS_ANALYSIS_DIR = PROJECT_ROOT / "data" / "news_analysis"
SUPPORTED_AVATAR_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _to_number(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _latest_csv(directory: Path) -> Path:
    files = sorted(directory.glob("*.csv"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No CSV files found in {directory}")
    return files[-1]


def _load_latest_predictions() -> tuple[Path, pd.DataFrame]:
    latest = _latest_csv(DAILY_DIR)
    frame = pd.read_csv(latest)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    return latest, frame.sort_values("ticker").reset_index(drop=True)


def _load_latest_comparison() -> tuple[Path | None, pd.DataFrame | None]:
    files = sorted(COMPARISON_DIR.glob("*.csv"), key=lambda path: path.stat().st_mtime)
    if not files:
        return None, None
    latest = files[-1]
    frame = pd.read_csv(latest)
    frame["ticker"] = frame["ticker"].astype(str).str.upper()
    return latest, frame.sort_values("ticker").reset_index(drop=True)


def _load_latest_news_analysis() -> tuple[Path | None, dict | None, dict[str, dict]]:
    latest_path = NEWS_ANALYSIS_DIR / "latest.json"
    if latest_path.exists():
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        lookup = {str(item["ticker"]).upper(): item for item in items}
        return latest_path, payload, lookup

    daily_dir = NEWS_ANALYSIS_DIR / "daily"
    files = sorted(daily_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
    if not files:
        return None, None, {}

    latest = files[-1]
    payload = json.loads(latest.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    lookup = {str(item["ticker"]).upper(): item for item in items}
    return latest, payload, lookup


def _avatar_path_for_ticker(ticker: str) -> str | None:
    for ext in SUPPORTED_AVATAR_EXTS:
        candidate = AVATAR_DIR / f"{ticker}{ext}"
        if candidate.exists():
            return f"../img/ava/{candidate.name}"
    return None


def _load_recent_feature_windows(target_tickers: list[str]) -> dict[str, pd.DataFrame]:
    raw = pd.read_csv(RAW_DATA_PATH, parse_dates=["date"])
    featured = prepare_featured_data(raw, tickers_list=target_tickers)

    recent_windows: dict[str, pd.DataFrame] = {}
    for ticker, group in featured.groupby("ticker"):
        clean = (
            group.sort_values("date")
            .dropna(subset=FEATURE_COLS)
            .tail(WINDOW_KEEP)
            .reset_index(drop=True)
        )
        recent_windows[ticker] = clean
    return recent_windows


def _build_prediction_summary(row: pd.Series) -> dict:
    return {
        "predictionDate": str(row["date"]),
        "consensusVotes": int(row["consensus_votes"]),
        "consensusDecision": row["consensus_decision"],
        "horizons": {
            "1d": {
                "rf": _to_number(row["prob_rf_1d"]),
                "xgb": _to_number(row["prob_xgb_1d"]),
                "lstm": _to_number(row["prob_lstm_1d"]),
                "ensemble": _to_number(row["ensemble_1d"]),
                "pred": int(row["pred_1d"]),
            },
            "5d": {
                "rf": _to_number(row["prob_rf_5d"]),
                "xgb": _to_number(row["prob_xgb_5d"]),
                "lstm": _to_number(row["prob_lstm_5d"]),
                "ensemble": _to_number(row["ensemble_5d"]),
                "pred": int(row["pred_5d"]),
            },
            "10d": {
                "rf": _to_number(row["prob_rf_10d"]),
                "xgb": _to_number(row["prob_xgb_10d"]),
                "lstm": _to_number(row["prob_lstm_10d"]),
                "ensemble": _to_number(row["ensemble_10d"]),
                "pred": int(row["pred_10d"]),
            },
        },
    }


def _build_comparison_lookup(comparison_df: pd.DataFrame | None) -> dict[str, dict]:
    if comparison_df is None:
        return {}

    lookup: dict[str, dict] = {}
    for _, row in comparison_df.iterrows():
        lookup[row["ticker"]] = {
            "predDate": str(row["pred_date"]),
            "evalDate": str(row["eval_date"]),
            "pred1d": int(row["pred_1d"]),
            "actual1d": int(row["actual_1d"]),
            "correct": bool(row["correct"]),
            "ensemble1d": _to_number(row["ensemble_1d"]),
        }
    return lookup


def _build_feature_rows(feature_window: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, row in feature_window.iterrows():
        item = {"date": row["date"].strftime("%Y-%m-%d")}
        for col in FEATURE_COLS:
            value = _to_number(row[col])
            if col == "ticker_id" and value is not None:
                value = int(value)
            item[col] = value
        rows.append(item)
    return rows


def main() -> None:
    STATIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TICKER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    latest_daily_path, predictions_df = _load_latest_predictions()
    latest_comparison_path, comparison_df = _load_latest_comparison()
    latest_news_analysis_path, news_analysis_payload, news_analysis_lookup = _load_latest_news_analysis()
    comparison_lookup = _build_comparison_lookup(comparison_df)

    tickers = predictions_df["ticker"].tolist()
    feature_windows = _load_recent_feature_windows(tickers)

    index_items: list[dict] = []
    missing_avatars: list[str] = []
    missing_feature_windows: list[str] = []

    for _, row in predictions_df.iterrows():
        ticker = row["ticker"]
        avatar_path = _avatar_path_for_ticker(ticker)
        if avatar_path is None:
            missing_avatars.append(ticker)

        feature_window = feature_windows.get(ticker)
        if feature_window is None or len(feature_window) < WINDOW_KEEP:
            missing_feature_windows.append(ticker)
            feature_rows: list[dict] = []
            feature_end_date = None
        else:
            feature_rows = _build_feature_rows(feature_window)
            feature_end_date = feature_rows[-1]["date"]

        prediction_summary = _build_prediction_summary(row)
        comparison_summary = comparison_lookup.get(ticker)
        news_analysis_summary = news_analysis_lookup.get(ticker)

        ticker_payload = {
            "ticker": ticker,
            "avatarPath": avatar_path,
            "prediction": prediction_summary,
            "comparison": comparison_summary,
            "newsAnalysis": news_analysis_summary,
            "featureColumns": FEATURE_COLS,
            "featureWindowSize": WINDOW_KEEP,
            "featureEndDate": feature_end_date,
            "featureRows": feature_rows,
        }

        (TICKER_DATA_DIR / f"{ticker}.json").write_text(
            json.dumps(ticker_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        index_items.append(
            {
                "ticker": ticker,
                "avatarPath": avatar_path,
                "consensusDecision": prediction_summary["consensusDecision"],
                "consensusVotes": prediction_summary["consensusVotes"],
                "predictionDate": prediction_summary["predictionDate"],
                "ensemble1d": prediction_summary["horizons"]["1d"]["ensemble"],
                "ensemble5d": prediction_summary["horizons"]["5d"]["ensemble"],
                "ensemble10d": prediction_summary["horizons"]["10d"]["ensemble"],
                "hasComparison": comparison_summary is not None,
                "hasNewsAnalysis": news_analysis_summary is not None,
                "newsSentiment": news_analysis_summary.get("sentiment") if news_analysis_summary else None,
                "newsScore": news_analysis_summary.get("newsScore") if news_analysis_summary else None,
            }
        )

    index_payload = {
        "generatedAt": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "predictionSourceFile": latest_daily_path.name,
        "comparisonSourceFile": latest_comparison_path.name if latest_comparison_path else None,
        "newsAnalysisSourceFile": latest_news_analysis_path.name if latest_news_analysis_path else None,
        "latestNewsAnalysisDate": news_analysis_payload.get("analysisDate") if news_analysis_payload else None,
        "tickerCount": len(index_items),
        "pageSize": 10,
        "featureColumns": FEATURE_COLS,
        "tickers": index_items,
        "missingAvatars": missing_avatars,
        "missingFeatureWindows": missing_feature_windows,
    }

    (STATIC_DATA_DIR / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"Built dashboard data for {len(index_items)} tickers")
    print(f"Latest predictions: {latest_daily_path.name}")
    if latest_comparison_path:
        print(f"Latest comparison: {latest_comparison_path.name}")
    if latest_news_analysis_path:
        print(f"Latest news analysis snapshot: {latest_news_analysis_path.name}")
    if missing_avatars:
        print(f"Missing avatars: {', '.join(missing_avatars)}")
    if missing_feature_windows:
        print(f"Missing feature windows: {', '.join(missing_feature_windows)}")


if __name__ == "__main__":
    main()
