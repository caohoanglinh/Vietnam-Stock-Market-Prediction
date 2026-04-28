import os
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime

logger = logging.getLogger(__name__)

# Connection string from env, fallback to docker-compose defaults
NEWS_DB_CONN = os.getenv(
    "NEWS_DB_CONN",
    "postgresql://airflow:airflow@localhost:5432/stock_news"
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_news (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(10)  NOT NULL,
    title       TEXT         NOT NULL,
    summary     TEXT,
    url         TEXT         UNIQUE,
    published_at_raw VARCHAR(100),
    published_at TIMESTAMP,              -- parsed from published_at_raw
    source      VARCHAR(100),
    crawled_at  TIMESTAMP    DEFAULT NOW(),
    sentiment   VARCHAR(20),   -- filled later by LLM pipeline
    llm_summary TEXT           -- filled later by LLM pipeline
);

CREATE INDEX IF NOT EXISTS idx_stock_news_ticker ON stock_news(ticker);
CREATE INDEX IF NOT EXISTS idx_stock_news_published_at ON stock_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_news_crawled_at ON stock_news(crawled_at DESC);
"""


def get_connection():
    """Get a psycopg2 connection to stock_news DB."""
    return psycopg2.connect(NEWS_DB_CONN)


def init_db():
    """Create tables if they don't exist."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    logger.info("stock_news DB initialized")


def insert_articles(articles: list[dict]) -> int:
    """
    Insert articles into DB, skip duplicates (by URL).

    Returns:
        Number of new articles inserted
    """
    if not articles:
        return 0

    insert_sql = """
        INSERT INTO stock_news
            (ticker, title, summary, url, published_at_raw, published_at, source, crawled_at)
        VALUES
            (%(ticker)s, %(title)s, %(summary)s, %(url)s,
             %(published_at_raw)s, %(published_at)s, %(source)s, %(crawled_at)s)
        ON CONFLICT (url) DO NOTHING
    """

    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for article in articles:
                # Ensure crawled_at is datetime
                if isinstance(article.get("crawled_at"), str):
                    article["crawled_at"] = datetime.utcnow()

                cur.execute(insert_sql, article)
                inserted += cur.rowcount
        conn.commit()

    logger.info(f"Inserted {inserted}/{len(articles)} new articles")
    return inserted


def get_news_by_ticker(ticker: str, limit: int = 20) -> list[dict]:
    """
    Fetch latest news for a ticker.

    Returns:
        List of article dicts ordered by crawled_at DESC
    """
    sql = """
        SELECT id, ticker, title, summary, url, published_at_raw,
               source, crawled_at, sentiment, llm_summary
        FROM stock_news
        WHERE ticker = %s
        ORDER BY crawled_at DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (ticker.upper(), limit))
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_news_by_tickers(tickers: list[str], limit_per_ticker: int = 10) -> dict[str, list[dict]]:
    """
    Fetch latest news for multiple tickers at once.

    Returns:
        Dict mapping ticker -> list of articles
    """
    if not tickers:
        return {}

    sql = """
        SELECT DISTINCT ON (ticker, url)
               id, ticker, title, summary, url, published_at_raw,
               source, crawled_at, sentiment, llm_summary
        FROM stock_news
        WHERE ticker = ANY(%s)
        ORDER BY ticker, url, crawled_at DESC
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, ([t.upper() for t in tickers],))
            rows = cur.fetchall()

    # Group by ticker
    result: dict[str, list[dict]] = {t.upper(): [] for t in tickers}
    for row in rows:
        ticker = row["ticker"]
        if len(result[ticker]) < limit_per_ticker:
            result[ticker].append(dict(row))
    return result


def update_llm_analysis(article_id: int, sentiment: str, llm_summary: str):
    """Update sentiment and LLM summary for an article (called by LLM pipeline)."""
    sql = """
        UPDATE stock_news
        SET sentiment = %s, llm_summary = %s
        WHERE id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (sentiment, llm_summary, article_id))
        conn.commit()