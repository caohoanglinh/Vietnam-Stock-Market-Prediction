import os
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pendulum
from airflow.sdk import DAG, task


LOCAL_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")
BASE_COLUMNS = ["date", "open", "high", "low", "close", "volume", "ticker", "ticker_id"]
FULL_HISTORY_START = "2000-01-01"
REQUEST_SLEEP_SECONDS = 1.0
VNSTOCK_SOURCE = "VCI"

# This is the current intended 100-stock universe from collect_data.ipynb.
TICKERS_100 = [
    "VNM", "DHG", "FPT", "PNJ", "KDC", "ACB", "REE", "VIC", "PPC", "DPM", "AGF", "HPG",
    "VCB", "BID", "CTG", "MBB", "TCB", "VPB", "STB", "HDB", "SHB", "VIB", "TPB", "LPB", "MSB", "OCB", "SSB",
    "SSI", "HCM", "VND", "VCI", "SHS", "MBS", "FTS", "BSI", "CTS", "AGR",
    "VHM", "VRE", "NVL", "KDH", "NLG", "PDR", "DIG", "DXG", "KBC", "ITA", "SJS", "HDC", "HDG", "CTD", "HBC", "VCG", "IJC", "SZC", "IDC",
    "HSG", "NKG", "HT1", "BCC", "DCM", "BFC", "DGC", "CSV",
    "MSN", "SAB", "SBT", "MWG", "DGW", "PET", "FRT",
    "GAS", "PLX", "POW", "NT2", "VSH", "BWE", "TDM", "GEG",
    "CMG", "ELC", "VGI",
    "GMD", "VJC", "HVN", "PVT", "HAH", "VOS",
    "VHC", "ANV", "FMC", "TCM", "TNG", "GIL", "DRC", "CSM", "PHR", "DPR", "GVR", "BMP",
]


def _project_root() -> Path:
    configured = Path(os.environ.get("VNSTOCK_PROJECT_ROOT", "/opt/airflow/project"))
    if configured.exists():
        return configured
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _project_root()
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "raw_data.csv"
SINGULAR_STOCK_DIR = DATA_DIR / "singular_stock"


def _load_existing_mapping() -> dict[str, int]:
    if not RAW_DATA_PATH.exists():
        return {}

    try:
        raw = pd.read_csv(RAW_DATA_PATH, usecols=["ticker", "ticker_id"])
    except Exception:
        return {}

    raw = raw.dropna(subset=["ticker", "ticker_id"]).drop_duplicates(subset=["ticker"], keep="last")
    return {row.ticker: int(row.ticker_id) for row in raw.itertuples(index=False)}


def _build_target_mapping() -> dict[str, int]:
    existing_mapping = _load_existing_mapping()
    mapping: dict[str, int] = {}

    for ticker in TICKERS_100:
        if ticker in existing_mapping:
            mapping[ticker] = existing_mapping[ticker]

    next_id = max(existing_mapping.values(), default=0)
    for ticker in TICKERS_100:
        if ticker not in mapping:
            next_id += 1
            mapping[ticker] = next_id

    return mapping


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=BASE_COLUMNS)


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return _empty_frame()

    frame = pd.read_csv(path)
    missing_columns = [col for col in BASE_COLUMNS if col not in frame.columns]
    if missing_columns:
        return _empty_frame()

    frame = frame[BASE_COLUMNS].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["ticker"] = frame["ticker"].astype(str)
    frame["ticker_id"] = pd.to_numeric(frame["ticker_id"], errors="coerce").astype("Int64")
    return frame


def _load_existing_ticker_frame(ticker: str) -> pd.DataFrame:
    singular_path = SINGULAR_STOCK_DIR / f"{ticker}.csv"
    singular_frame = _read_csv_if_exists(singular_path)
    if not singular_frame.empty:
        return singular_frame

    if not RAW_DATA_PATH.exists():
        return _empty_frame()

    raw = pd.read_csv(RAW_DATA_PATH)
    if "ticker" not in raw.columns:
        return _empty_frame()

    frame = raw.loc[raw["ticker"] == ticker, BASE_COLUMNS].copy()
    if frame.empty:
        return frame

    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["ticker_id"] = pd.to_numeric(frame["ticker_id"], errors="coerce").astype("Int64")
    return frame


def _fetch_quote_history(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    from vnstock.common.data import Quote

    frame = Quote(ticker, VNSTOCK_SOURCE).history(start=start_date, end=end_date, interval="1D")
    if frame is None or frame.empty:
        return _empty_frame()

    frame = frame.rename(columns={"time": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None).dt.normalize()
    frame["open"] = pd.to_numeric(frame["open"], errors="coerce")
    frame["high"] = pd.to_numeric(frame["high"], errors="coerce")
    frame["low"] = pd.to_numeric(frame["low"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    return frame[["date", "open", "high", "low", "close", "volume"]].copy()


def _merge_ticker_frame(existing_frame: pd.DataFrame, fetched_frame: pd.DataFrame, ticker: str, ticker_id: int) -> pd.DataFrame:
    existing = existing_frame.copy() if not existing_frame.empty else _empty_frame()
    fetched = fetched_frame.copy() if not fetched_frame.empty else _empty_frame()

    if not fetched.empty:
        fetched["ticker"] = ticker
        fetched["ticker_id"] = ticker_id
        fetched = fetched[BASE_COLUMNS]

    combined = pd.concat([existing, fetched], ignore_index=True)
    if combined.empty:
        return combined

    combined["date"] = pd.to_datetime(combined["date"]).dt.normalize()
    combined["ticker"] = ticker
    combined["ticker_id"] = ticker_id
    combined["volume"] = pd.to_numeric(combined["volume"], errors="coerce").astype("Int64")
    combined = combined.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    combined = combined.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    return combined[BASE_COLUMNS]


def _write_ticker_frame(frame: pd.DataFrame, ticker: str) -> None:
    SINGULAR_STOCK_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SINGULAR_STOCK_DIR / f"{ticker}.csv"
    frame_to_save = frame.copy()
    frame_to_save["date"] = pd.to_datetime(frame_to_save["date"]).dt.strftime("%Y-%m-%d")
    frame_to_save["ticker_id"] = frame_to_save["ticker_id"].astype("Int64")
    frame_to_save.to_csv(output_path, index=False)


def _rebuild_raw_data(target_mapping: dict[str, int]) -> dict[str, int]:
    frames: list[pd.DataFrame] = []
    for ticker in TICKERS_100:
        frame = _read_csv_if_exists(SINGULAR_STOCK_DIR / f"{ticker}.csv")
        if frame.empty:
            continue
        frame["ticker"] = ticker
        frame["ticker_id"] = target_mapping[ticker]
        frames.append(frame[BASE_COLUMNS])

    if frames:
        raw = pd.concat(frames, ignore_index=True)
        raw = raw.sort_values(["ticker", "date"]).reset_index(drop=True)
    else:
        raw = _empty_frame()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_to_save = raw.copy()
    if not raw_to_save.empty:
        raw_to_save["date"] = pd.to_datetime(raw_to_save["date"]).dt.strftime("%Y-%m-%d")
        raw_to_save["ticker_id"] = raw_to_save["ticker_id"].astype("Int64")
    raw_to_save.to_csv(RAW_DATA_PATH, index=False)

    last_dates = {}
    if not raw.empty:
        grouped = raw.groupby("ticker")["date"].max()
        last_dates = {ticker: str(value.date()) for ticker, value in grouped.items()}
    return last_dates


def sync_vnstock_quotes(run_label: str) -> dict[str, object]:
    from vnstock import Vnstock

    api_key = os.environ.get("VNSTOCK_API_KEY")
    if api_key:
        Vnstock.api_key = api_key

    today = pendulum.now(LOCAL_TZ).date()
    target_mapping = _build_target_mapping()

    fetched_tickers = 0
    skipped_tickers = 0
    total_new_rows = 0
    full_history_tickers: list[str] = []

    for index, ticker in enumerate(TICKERS_100, start=1):
        existing = _load_existing_ticker_frame(ticker)
        ticker_id = target_mapping[ticker]

        if existing.empty:
            fetch_start = FULL_HISTORY_START
            full_history_tickers.append(ticker)
        else:
            latest_date = pd.to_datetime(existing["date"]).max().date()
            fetch_start = str(latest_date + timedelta(days=1))

        if pendulum.parse(fetch_start).date() > today:
            skipped_tickers += 1
            continue

        fetched = _fetch_quote_history(ticker=ticker, start_date=fetch_start, end_date=str(today))
        merged = _merge_ticker_frame(existing, fetched, ticker=ticker, ticker_id=ticker_id)
        added_rows = max(len(merged) - len(existing), 0)
        total_new_rows += added_rows

        _write_ticker_frame(merged, ticker=ticker)
        fetched_tickers += 1

        print(
            f"[{index:03d}/{len(TICKERS_100)}] {ticker}: start={fetch_start} fetched={len(fetched):,} "
            f"added={added_rows:,} total={len(merged):,}"
        )
        time.sleep(REQUEST_SLEEP_SECONDS)

    last_dates = _rebuild_raw_data(target_mapping)
    active_tickers = sorted(last_dates.keys())
    missing_output_tickers = [ticker for ticker in TICKERS_100 if ticker not in active_tickers]

    summary = {
        "run_label": run_label,
        "today": str(today),
        "target_ticker_count": len(TICKERS_100),
        "active_output_ticker_count": len(active_tickers),
        "fetched_tickers": fetched_tickers,
        "skipped_tickers": skipped_tickers,
        "full_history_tickers": full_history_tickers,
        "missing_output_tickers": missing_output_tickers,
        "total_new_rows": total_new_rows,
        "raw_data_path": str(RAW_DATA_PATH),
    }
    print(summary)
    return summary


with DAG(
    dag_id="vnstock_backfill_to_today",
    start_date=pendulum.datetime(2026, 4, 17, 0, 0, tz=LOCAL_TZ),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["vnstock", "quotes", "backfill"],
    doc_md="""
    Manual DAG to catch up local quote data to today.

    Behavior:
    - Reads the current local files in `data/raw_data.csv` and `data/singular_stock/*.csv`
    - Fetches only the missing daily rows for the configured 100-stock universe
    - Rebuilds `data/raw_data.csv` from the per-ticker raw files
    """,
) as backfill_dag:
    @task(task_id="sync_quotes_to_today")
    def run_backfill():
        return sync_vnstock_quotes(run_label="manual_backfill")

    run_backfill()


with DAG(
    dag_id="vnstock_weekday_quotes_18h",
    start_date=pendulum.datetime(2026, 4, 17, 18, 0, tz=LOCAL_TZ),
    schedule="0 18 * * 1-5",
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["vnstock", "quotes", "daily"],
    doc_md="""
    Scheduled DAG to refresh quote data every weekday at 18:00 Asia/Ho_Chi_Minh.

    Behavior:
    - Runs on Monday-Friday only
    - Detects the latest local date per ticker and fetches only the missing rows
    - Keeps the raw quote dataset current after the initial backfill run
    """,
) as weekday_dag:
    @task(task_id="sync_quotes_incremental")
    def run_incremental():
        return sync_vnstock_quotes(run_label="weekday_18h_incremental")

    run_incremental()
