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
    def log_summary(batch_results: list[dict], penalty_macro_result: dict):
        """Aggregate and log final crawl summary across all batches."""
        total = sum(r.get("total_inserted", 0) for r in batch_results) + penalty_macro_result.get("penalty_inserted", 0) + penalty_macro_result.get("macro_inserted", 0)
        all_failed = [t for r in batch_results if "failed" in r for t in r["failed"]]
        logger.info(
            f"[NEWS CRAWL SUMMARY] "
            f"Inserted: {total} | "
            f"Failed tickers ({len(all_failed)}): {all_failed}"
        )

    @task()
    def crawl_penalty_and_macro() -> dict:
        """
        Crawl CafeF penalty/regulatory news and macro headlines.

        Penalty articles: use a single LLM batch call to identify which tickers
        they relate to, then re-insert each article once per matched ticker.

        Macro articles: stored as-is with ticker='MACRO' for use as LLM context.
        """
        sys.path.insert(0, "/opt/airflow/project")
        from utils.news_crawler import crawl_macro_news, crawl_penalty_news
        from utils.news_db import insert_articles
        from utils.gemini_news_analysis import extract_tickers_from_penalty_articles

        result = {"penalty_inserted": 0, "macro_inserted": 0, "penalty_articles": 0}

        # --- Macro news ---
        macro_articles = crawl_macro_news(max_articles=20)
        if macro_articles:
            result["macro_inserted"] = insert_articles(macro_articles)
            logger.info(f"[MACRO] {result['macro_inserted']} macro articles saved")

        # --- Penalty news ---
        penalty_articles = crawl_penalty_news(max_articles=30)
        result["penalty_articles"] = len(penalty_articles)
        logger.info(f"[PENALTY] Crawled {len(penalty_articles)} penalty articles")

        if penalty_articles:
            # Single LLM call to map articles → tickers
            matches = extract_tickers_from_penalty_articles(
                articles=penalty_articles,
                known_tickers=TICKERS,
            )
            logger.info(f"[PENALTY] LLM matched tickers in {len(matches)} articles")

            # Re-insert each penalty article once per matched ticker
            tagged_articles = []
            matched_indices = {m["article_index"]: m["tickers"] for m in matches}
            for i, article in enumerate(penalty_articles):
                tickers_for_article = matched_indices.get(i, [])
                if tickers_for_article:
                    for ticker in tickers_for_article:
                        tagged = dict(article)
                        tagged["ticker"] = ticker.upper()
                        tagged_articles.append(tagged)
                # Always keep the original PENALTY record for audit trail
                tagged_articles.append(article)

            result["penalty_inserted"] = insert_articles(tagged_articles)
            logger.info(f"[PENALTY] {result['penalty_inserted']} penalty articles saved (incl. per-ticker copies)")

        return result

    # DAG flow: init → N parallel batch tasks + penalty/macro → summary
    init = init_database()
    batch_results = crawl_batch.expand(batch=TICKER_BATCHES)
    penalty_macro_result = crawl_penalty_and_macro()
    batch_results.set_upstream(init)
    penalty_macro_result.set_upstream(init)
    log_summary(batch_results, penalty_macro_result)


vnstock_news_crawl_dag()