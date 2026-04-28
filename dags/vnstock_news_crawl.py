from __future__ import annotations

import sys
import logging
from datetime import timedelta

from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

# All 99 tracked tickers
TICKERS = [
    "ACB", "AGF", "AGR", "ANV", "BCC", "BFC", "BID", "BMP", "BSI", "BWE",
    "CAN", "CMG", "CSM", "CSV", "CTD", "CTG", "CTS", "DCM", "DGC", "DGW",
    "DHG", "DIG", "DPM", "DPR", "DRC", "DXG", "ELC", "FMC", "FPT", "FRT",
    "FTS", "GAS", "GEG", "GIL", "GMD", "GVR", "HAH", "HBC", "HCM", "HDB",
    "HDC", "HDG", "HPG", "HSG", "HT1", "HVN", "IDC", "IJC", "ITA", "KBC",
    "KDC", "KDH", "LAF", "LPB", "MBB", "MBS", "MSB", "MSN", "MWG", "NKG",
    "NLG", "NT2", "NVL", "OCB", "PDR", "PET", "PHR", "PLX", "PNJ", "POW",
    "PPC", "PVT", "REE", "SAB", "SBT", "SHB", "SHS", "SJS", "SSB", "SSI",
    "STB", "SZC", "TCB", "TCM", "TDM", "TNG", "TPB", "VCB", "VCG", "VCI",
    "VGI", "VHC", "VHM", "VIB", "VIC", "VJC", "VND", "VNM", "VOS",
]

DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Split tickers into batches for parallel execution
BATCH_SIZE = 10
TICKER_BATCHES = [
    TICKERS[i : i + BATCH_SIZE] for i in range(0, len(TICKERS), BATCH_SIZE)
]


@dag(
    dag_id="vnstock_news_crawl",
    description="Crawl daily stock news from CafeF for all 99 tickers (parallel batches)",
    schedule="0 12 * * 1-5",   # Every weekday at 19:00 ICT (UTC+7 = UTC+7, server UTC)
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["news", "crawl"],
)
def vnstock_news_crawl_dag():

    @task()
    def init_database():
        """Ensure stock_news table exists."""
        sys.path.insert(0, "/opt/airflow/project")
        from utils.news_db import init_db
        init_db()
        logger.info("Database initialized")

    @task()
    def crawl_batch(batch: list[str]) -> dict:
        """
        Crawl news for one batch of tickers and store in PostgreSQL.
        Multiple instances of this task run in parallel via expand().
        """
        sys.path.insert(0, "/opt/airflow/project")
        from utils.news_crawler import crawl_stock_news
        from utils.news_db import insert_articles

        total_inserted = 0
        failed = []

        for ticker in batch:
            try:
                articles = crawl_stock_news(ticker, max_articles=20)
                if articles:
                    inserted = insert_articles(articles)
                    total_inserted += inserted
                    logger.info(f"[{ticker}] {inserted} new articles saved")
                else:
                    logger.info(f"[{ticker}] No articles found")
            except Exception as e:
                logger.error(f"[{ticker}] Failed: {e}")
                failed.append(ticker)

        logger.info(
            f"Batch {batch[:2]}... done: {total_inserted} inserted, failed: {failed}"
        )
        return {"total_inserted": total_inserted, "failed": failed}

    @task()
    def log_summary(results: list[dict]):
        """Aggregate and log final crawl summary across all batches."""
        total = sum(r["total_inserted"] for r in results)
        all_failed = [t for r in results for t in r["failed"]]
        logger.info(
            f"[NEWS CRAWL SUMMARY] "
            f"Inserted: {total} | "
            f"Failed tickers ({len(all_failed)}): {all_failed}"
        )

    # DAG flow: init → N parallel batch tasks → summary
    init = init_database()
    batch_results = crawl_batch.expand(batch=TICKER_BATCHES)
    batch_results.set_upstream(init)
    log_summary(batch_results)


vnstock_news_crawl_dag()