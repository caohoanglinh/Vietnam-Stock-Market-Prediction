from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg2.extras

from utils.news_db import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEWS_ANALYSIS_DIR = PROJECT_ROOT / "data" / "news_analysis"
DAILY_ANALYSIS_DIR = NEWS_ANALYSIS_DIR / "daily"

CREATE_ANALYSIS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_news_daily_analysis (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    analysis_date   DATE NOT NULL,
    article_count   INTEGER NOT NULL,
    news_input_hash TEXT NOT NULL,
    sentiment       VARCHAR(20) NOT NULL,
    impact_horizon  VARCHAR(10),
    confidence      DOUBLE PRECISION,
    news_score      DOUBLE PRECISION,
    summary         TEXT,
    bull_points     JSONB,
    bear_points     JSONB,
    risk_flags      JSONB,
    model_name      VARCHAR(100) NOT NULL,
    raw_response    JSONB,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (ticker, analysis_date)
);

CREATE INDEX IF NOT EXISTS idx_stock_news_daily_analysis_date
    ON stock_news_daily_analysis (analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_stock_news_daily_analysis_ticker_date
    ON stock_news_daily_analysis (ticker, analysis_date DESC);
"""

LOCAL_DATE_EXPR = "((crawled_at AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"


def init_news_analysis_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_ANALYSIS_TABLE_SQL)
        conn.commit()


def _normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    text = str(value).strip()
    return text or None


def _normalize_article(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "title": str(row.get("title") or "").strip(),
        "summary": str(row.get("summary") or "").strip(),
        "url": str(row.get("url") or "").strip(),
        "source": str(row.get("source") or "").strip() or "cafef.vn",
        "publishedAt": _normalize_timestamp(row.get("published_at")),
        "crawledAt": _normalize_timestamp(row.get("crawled_at")),
    }


def build_news_input_hash(ticker: str, analysis_date: date, articles: list[dict[str, Any]]) -> str:
    canonical = {
        "ticker": ticker.upper(),
        "analysis_date": analysis_date.isoformat(),
        "articles": [
            {
                "url": article.get("url"),
                "title": article.get("title"),
                "summary": article.get("summary"),
                "publishedAt": article.get("publishedAt"),
                "crawledAt": article.get("crawledAt"),
            }
            for article in articles
        ],
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def fetch_articles_grouped_for_analysis(
    analysis_date: date,
    max_articles_per_ticker: int = 8,
    tickers: list[str] | None = None,
) -> list[dict[str, Any]]:
    sql = f"""
        SELECT id, ticker, title, summary, url, source, published_at, crawled_at
        FROM stock_news
        WHERE {LOCAL_DATE_EXPR} = %s
    """
    params: list[Any] = [analysis_date]

    if tickers:
        sql += " AND ticker = ANY(%s)"
        params.append([ticker.upper() for ticker in tickers])

    sql += " ORDER BY ticker ASC, crawled_at DESC NULLS LAST, published_at DESC NULLS LAST"

    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_urls: dict[str, set[str]] = defaultdict(set)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    for row in rows:
        ticker = str(row["ticker"]).upper()
        article = _normalize_article(dict(row))
        if not article["title"]:
            continue
        if article["url"] and article["url"] in seen_urls[ticker]:
            continue
        if article["url"]:
            seen_urls[ticker].add(article["url"])
        grouped_rows[ticker].append(article)

    groups: list[dict[str, Any]] = []
    for ticker in sorted(grouped_rows):
        deduped_articles = grouped_rows[ticker]
        selected_articles = deduped_articles[:max_articles_per_ticker]
        if not selected_articles:
            continue
        groups.append(
            {
                "ticker": ticker,
                "analysisDate": analysis_date.isoformat(),
                "articles": selected_articles,
                "articleCount": len(selected_articles),
                "totalArticleCount": len(deduped_articles),
                "newsInputHash": build_news_input_hash(ticker, analysis_date, selected_articles),
            }
        )
    return groups


def get_existing_analysis(ticker: str, analysis_date: date) -> dict[str, Any] | None:
    sql = """
        SELECT *
        FROM stock_news_daily_analysis
        WHERE ticker = %s AND analysis_date = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (ticker.upper(), analysis_date))
            row = cur.fetchone()
    return dict(row) if row else None


def upsert_daily_analysis(record: dict[str, Any]) -> None:
    sql = """
        INSERT INTO stock_news_daily_analysis (
            ticker, analysis_date, article_count, news_input_hash,
            sentiment, impact_horizon, confidence, news_score,
            summary, bull_points, bear_points, risk_flags,
            model_name, raw_response, updated_at
        )
        VALUES (
            %(ticker)s, %(analysis_date)s, %(article_count)s, %(news_input_hash)s,
            %(sentiment)s, %(impact_horizon)s, %(confidence)s, %(news_score)s,
            %(summary)s, %(bull_points)s, %(bear_points)s, %(risk_flags)s,
            %(model_name)s, %(raw_response)s, NOW()
        )
        ON CONFLICT (ticker, analysis_date) DO UPDATE SET
            article_count = EXCLUDED.article_count,
            news_input_hash = EXCLUDED.news_input_hash,
            sentiment = EXCLUDED.sentiment,
            impact_horizon = EXCLUDED.impact_horizon,
            confidence = EXCLUDED.confidence,
            news_score = EXCLUDED.news_score,
            summary = EXCLUDED.summary,
            bull_points = EXCLUDED.bull_points,
            bear_points = EXCLUDED.bear_points,
            risk_flags = EXCLUDED.risk_flags,
            model_name = EXCLUDED.model_name,
            raw_response = EXCLUDED.raw_response,
            updated_at = NOW()
    """
    payload = {
        "ticker": str(record["ticker"]).upper(),
        "analysis_date": record["analysis_date"],
        "article_count": int(record["article_count"]),
        "news_input_hash": str(record["news_input_hash"]),
        "sentiment": str(record["sentiment"]),
        "impact_horizon": record.get("impact_horizon"),
        "confidence": record.get("confidence"),
        "news_score": record.get("news_score"),
        "summary": record.get("summary"),
        "bull_points": psycopg2.extras.Json(record.get("bull_points", [])),
        "bear_points": psycopg2.extras.Json(record.get("bear_points", [])),
        "risk_flags": psycopg2.extras.Json(record.get("risk_flags", [])),
        "model_name": str(record["model_name"]),
        "raw_response": psycopg2.extras.Json(record.get("raw_response", {})),
    }
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, payload)
        conn.commit()


def get_daily_analysis_records(analysis_date: date) -> list[dict[str, Any]]:
    sql = """
        SELECT *
        FROM stock_news_daily_analysis
        WHERE analysis_date = %s
        ORDER BY ticker ASC
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (analysis_date,))
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def fetch_macro_headlines_for_date(analysis_date: date, limit: int = 10) -> list[str]:
    """
    Fetch macro/policy news headlines crawled on a given date.
    Used to inject macro context into per-ticker LLM prompts.

    Returns:
        List of headline strings (title only), most recent first.
    """
    sql = f"""
        SELECT title
        FROM stock_news
        WHERE ticker = 'MACRO'
          AND {LOCAL_DATE_EXPR} = %s
        ORDER BY crawled_at DESC NULLS LAST
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (analysis_date, limit))
            rows = cur.fetchall()
    return [row[0] for row in rows if row[0]]


def _normalize_points(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _snapshot_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(record["ticker"]).upper(),
        "analysisDate": str(record["analysis_date"]),
        "articleCount": int(record.get("article_count") or 0),
        "newsInputHash": str(record.get("news_input_hash") or ""),
        "sentiment": str(record.get("sentiment") or "neutral"),
        "impactHorizon": record.get("impact_horizon"),
        "confidence": float(record["confidence"]) if record.get("confidence") is not None else None,
        "newsScore": float(record["news_score"]) if record.get("news_score") is not None else None,
        "summary": str(record.get("summary") or "").strip(),
        "bullPoints": _normalize_points(record.get("bull_points")),
        "bearPoints": _normalize_points(record.get("bear_points")),
        "riskFlags": _normalize_points(record.get("risk_flags")),
        "modelName": str(record.get("model_name") or ""),
        "updatedAt": _normalize_timestamp(record.get("updated_at")),
    }


def export_daily_analysis_snapshot(
    analysis_date: date,
    records: list[dict[str, Any]],
    model_name: str | None = None,
) -> Path:
    NEWS_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    items = [_snapshot_item(record) for record in records]
    payload = {
        "analysisDate": analysis_date.isoformat(),
        "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "tickerCount": len(items),
        "modelName": model_name or (items[0]["modelName"] if items else None),
        "items": items,
    }

    json_path = DAILY_ANALYSIS_DIR / f"{analysis_date.isoformat()}.json"
    csv_path = DAILY_ANALYSIS_DIR / f"{analysis_date.isoformat()}.csv"
    latest_path = NEWS_ANALYSIS_DIR / "latest.json"

    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    latest_path.write_text(json_text, encoding="utf-8")

    fieldnames = [
        "ticker",
        "analysisDate",
        "articleCount",
        "sentiment",
        "impactHorizon",
        "confidence",
        "newsScore",
        "summary",
        "bullPoints",
        "bearPoints",
        "riskFlags",
        "modelName",
        "updatedAt",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "ticker": item.get("ticker"),
                    "analysisDate": item.get("analysisDate"),
                    "articleCount": item.get("articleCount"),
                    "sentiment": item.get("sentiment"),
                    "impactHorizon": item.get("impactHorizon"),
                    "confidence": item.get("confidence"),
                    "newsScore": item.get("newsScore"),
                    "summary": item.get("summary"),
                    "bullPoints": " | ".join(item.get("bullPoints", [])),
                    "bearPoints": " | ".join(item.get("bearPoints", [])),
                    "riskFlags": " | ".join(item.get("riskFlags", [])),
                    "modelName": item.get("modelName"),
                    "updatedAt": item.get("updatedAt"),
                }
            )

    return json_path
