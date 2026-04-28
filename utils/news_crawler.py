import httpx
import logging
from datetime import datetime, timezone
from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# CafeF stock news URL pattern
# Primary: tag page (redirects to https://cafef.vn/tags/{ticker}.chn)
CAFEF_STOCK_URL = "https://cafef.vn/{ticker}.html"
# Fallback: keyword search page
CAFEF_SEARCH_URL = "https://cafef.vn/tim-kiem.chn?keywords={ticker}"


def _parse_date(raw: str) -> datetime | None:
    """
    Parse CafeF date string 'DD/MM/YYYY HH:MM' -> UTC datetime.
    Returns None if parsing fails.
    """
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_cafef_articles(html: str, ticker: str) -> list[dict]:
    """
    Parse articles from CafeF ticker tag page.

    Live HTML structure (confirmed from cafef.vn/{ticker}.html):
        <h3>
            <a href="/article-slug.chn">Title text</a>
        </h3>
        <!-- text node: "DD/MM/YYYY HH:MM" -->
        <!-- text node: summary text -->
    """
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    crawled_at = datetime.now(tz=timezone.utc)

    # Primary: ticker tag page — each article is a <h3> with an <a> child
    headings = soup.select("h3")

    for h3 in headings:
        try:
            link = h3.find("a", href=True)
            if not link:
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            url = link["href"]
            if not url.startswith("http"):
                url = "https://cafef.vn" + url

            # Sibling text nodes immediately after <h3> carry date then summary
            published_at_raw = ""
            summary = ""
            for sibling in h3.next_siblings:
                if isinstance(sibling, NavigableString):
                    text = sibling.strip()
                    if not text:
                        continue
                    if not published_at_raw:
                        published_at_raw = text  # first non-empty text = date
                    else:
                        summary = text           # second = summary
                        break
                elif sibling.name in ("p", "span", "div"):
                    text = sibling.get_text(strip=True)
                    if not published_at_raw:
                        published_at_raw = text
                    else:
                        summary = text
                        break
                elif sibling.name == "h3":
                    break  # next article block reached

            published_at = _parse_date(published_at_raw)

            articles.append({
                "ticker": ticker,
                "title": title,
                "summary": summary,
                "url": url,
                "published_at_raw": published_at_raw,
                "published_at": published_at.isoformat() if published_at else None,
                "source": "cafef.vn",
                "crawled_at": crawled_at.isoformat(),
            })

        except Exception as e:
            logger.warning(f"[{ticker}] Failed to parse article: {e}")
            continue

    return articles


def crawl_stock_news(ticker: str, max_articles: int = 20) -> list[dict]:
    """
    Crawl latest news for a stock ticker from CafeF.

    Args:
        ticker: Stock symbol (e.g. 'VCB', 'HPG')
        max_articles: Maximum number of articles to return

    Returns:
        List of article dicts with keys:
        ticker, title, summary, url, published_at_raw, source, crawled_at
    """
    articles = []
    urls_to_try = [
        CAFEF_STOCK_URL.format(ticker=ticker.lower()),
        CAFEF_SEARCH_URL.format(ticker=ticker),
    ]

    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        for url in urls_to_try:
            try:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(f"[{ticker}] HTTP {response.status_code} for {url}")
                    continue

                parsed = _parse_cafef_articles(response.text, ticker)
                articles.extend(parsed)

                if articles:
                    break  # Stop if first URL returned results

            except Exception as e:
                logger.error(f"[{ticker}] Error crawling {url}: {e}")
                continue

    # Deduplicate by URL
    seen_urls = set()
    unique_articles = []
    for article in articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)

    logger.info(f"[{ticker}] Crawled {len(unique_articles)} articles")
    return unique_articles[:max_articles]


def crawl_multiple_tickers(tickers: list[str], max_per_ticker: int = 20) -> list[dict]:
    """
    Crawl news for multiple tickers.

    Args:
        tickers: List of stock symbols
        max_per_ticker: Max articles per ticker

    Returns:
        Combined list of articles from all tickers
    """
    all_articles = []
    for ticker in tickers:
        try:
            articles = crawl_stock_news(ticker, max_per_ticker)
            all_articles.extend(articles)
        except Exception as e:
            logger.error(f"Failed to crawl {ticker}: {e}")
    return all_articles