from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta

import pendulum
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)

PROJECT_ROOT = "/opt/airflow/project"
sys.path.insert(0, PROJECT_ROOT)

LOCAL_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")
MAX_ARTICLES_PER_TICKER = 8
MAX_TICKERS_PER_RUN = 100

DEFAULT_ARGS = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="vnstock_news_llm_analysis",
    description="Analyze daily stock news with Gemini and export dashboard snapshots",
    schedule="30 19 * * 1-5",
    start_date=datetime(2026, 5, 18, tzinfo=LOCAL_TZ),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["news", "llm", "gemini"],
)
def vnstock_news_llm_analysis_dag():

    @task()
    def init_analysis_tables() -> None:
        from utils.news_analysis_db import init_news_analysis_db

        init_news_analysis_db()
        logger.info("stock_news_daily_analysis table is ready")

    @task()
    def analyze_daily_news() -> dict:
        from utils.gemini_news_analysis import (
            DEFAULT_MODEL_NAME,
            INTER_REQUEST_DELAY_SECONDS,
            analyze_ticker_news,
        )
        from utils.news_analysis_db import (
            export_daily_analysis_snapshot,
            fetch_articles_grouped_for_analysis,
            get_daily_analysis_records,
            get_existing_analysis,
            upsert_daily_analysis,
        )

        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not configured in environment")

        analysis_date = pendulum.now(LOCAL_TZ).date()
        logger.info("Starting Gemini news analysis for %s", analysis_date)

        groups = fetch_articles_grouped_for_analysis(
            analysis_date=analysis_date,
            max_articles_per_ticker=MAX_ARTICLES_PER_TICKER,
        )

        if MAX_TICKERS_PER_RUN and len(groups) > MAX_TICKERS_PER_RUN:
            logger.warning(
                "Candidate ticker groups=%s exceeds MAX_TICKERS_PER_RUN=%s. Truncating.",
                len(groups),
                MAX_TICKERS_PER_RUN,
            )
            groups = groups[:MAX_TICKERS_PER_RUN]

        summary = {
            "analysis_date": analysis_date.isoformat(),
            "candidate_tickers": len(groups),
            "analyzed": 0,
            "skipped_unchanged": 0,
            "failed": 0,
            "failures": [],
        }

        for index, group in enumerate(groups, start=1):
            ticker = group["ticker"]
            existing = get_existing_analysis(ticker, analysis_date)
            if existing and existing.get("news_input_hash") == group["newsInputHash"]:
                summary["skipped_unchanged"] += 1
                logger.info(
                    "[%s/%s] %s skipped: unchanged hash",
                    index,
                    len(groups),
                    ticker,
                )
                continue

            logger.info(
                "[%s/%s] %s analyzing %s articles (total crawled=%s)",
                index,
                len(groups),
                ticker,
                group["articleCount"],
                group["totalArticleCount"],
            )

            try:
                analysis = analyze_ticker_news(
                    ticker=ticker,
                    analysis_date=analysis_date,
                    articles=group["articles"],
                    model_name=DEFAULT_MODEL_NAME,
                )
                record = {
                    "ticker": ticker,
                    "analysis_date": analysis_date,
                    "article_count": group["articleCount"],
                    "news_input_hash": group["newsInputHash"],
                    "sentiment": analysis["sentiment"],
                    "impact_horizon": analysis["impact_horizon"],
                    "confidence": analysis["confidence"],
                    "news_score": analysis["news_score"],
                    "summary": analysis["summary"],
                    "bull_points": analysis["bull_points"],
                    "bear_points": analysis["bear_points"],
                    "risk_flags": analysis["risk_flags"],
                    "model_name": analysis["model_name"],
                    "raw_response": analysis["raw_response"],
                }
                upsert_daily_analysis(record)
                summary["analyzed"] += 1
            except Exception as exc:
                summary["failed"] += 1
                summary["failures"].append({"ticker": ticker, "error": str(exc)})
                logger.exception("Gemini analysis failed for %s", ticker)

            if index < len(groups):
                time.sleep(INTER_REQUEST_DELAY_SECONDS)

        records = get_daily_analysis_records(analysis_date)
        if records:
            snapshot_path = export_daily_analysis_snapshot(
                analysis_date=analysis_date,
                records=records,
                model_name=DEFAULT_MODEL_NAME,
            )
            summary["exported_records"] = len(records)
            summary["snapshot_path"] = str(snapshot_path)
            logger.info("Exported news analysis snapshot: %s", snapshot_path)
        else:
            summary["exported_records"] = 0
            logger.info("No news analysis records available to export for %s", analysis_date)

        return summary

    @task()
    def log_summary(summary: dict) -> None:
        logger.info("[GEMINI NEWS SUMMARY] %s", summary)

    init_task = init_analysis_tables()
    summary_task = analyze_daily_news()
    init_task >> summary_task
    log_summary(summary_task)


vnstock_news_llm_analysis_dag()
