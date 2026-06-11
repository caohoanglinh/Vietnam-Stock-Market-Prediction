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

# Penalty / regulatory news — negative signal source
CAFEF_PENALTY_URL = "https://cafef.vn/xu-phat.chn"

# Macro / policy news — market-wide context
CAFEF_MACRO_URLS = [
    "https://cafef.vn/vi-mo-dau-tu.chn",       # Vĩ mô đầu tư
    "https://cafef.vn/tai-chinh-ngan-hang.chn", # Tài chính ngân hàng
]


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_cafef_articles(html: str, ticker: str) -> list[dict]:

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

    all_articles = []
    for ticker in tickers:
        try:
            articles = crawl_stock_news(ticker, max_per_ticker)
            all_articles.extend(articles)
        except Exception as e:
            logger.error(f"Failed to crawl {ticker}: {e}")
    return all_articles


def _parse_cafef_list_page(html: str, source_label: str, ticker: str = "MACRO") -> list[dict]:
    """Generic parser for CafeF list/category pages (penalty, macro, etc.)."""
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    crawled_at = datetime.now(tz=timezone.utc)

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

            published_at_raw = ""
            summary = ""
            for sibling in h3.next_siblings:
                if isinstance(sibling, NavigableString):
                    text = sibling.strip()
                    if not text:
                        continue
                    if not published_at_raw:
                        published_at_raw = text
                    else:
                        summary = text
                        break
                elif sibling.name in ("p", "span", "div"):
                    text = sibling.get_text(strip=True)
                    if not published_at_raw:
                        published_at_raw = text
                    else:
                        summary = text
                        break
                elif sibling.name == "h3":
                    break

            published_at = _parse_date(published_at_raw)
            articles.append({
                "ticker": ticker,
                "title": title,
                "summary": summary,
                "url": url,
                "published_at_raw": published_at_raw,
                "published_at": published_at.isoformat() if published_at else None,
                "source": source_label,
                "crawled_at": crawled_at.isoformat(),
            })
        except Exception as e:
            logger.warning(f"[{source_label}] Failed to parse article: {e}")
            continue
    return articles


def crawl_penalty_news(max_articles: int = 30) -> list[dict]:
    """
    Crawl CafeF's penalty/regulatory section (cafef.vn/xu-phat.chn).
    Articles are stored with ticker='PENALTY' initially.
    The DAG will call the LLM batch extractor to assign real tickers.

    Returns:
        List of article dicts with ticker='PENALTY' and source='cafef_penalty'
    """
    articles = []
    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        try:
            response = client.get(CAFEF_PENALTY_URL)
            if response.status_code == 200:
                parsed = _parse_cafef_list_page(response.text, source_label="cafef_penalty", ticker="PENALTY")
                articles.extend(parsed)
                logger.info(f"[PENALTY] Crawled {len(parsed)} articles from {CAFEF_PENALTY_URL}")
            else:
                logger.warning(f"[PENALTY] HTTP {response.status_code} for {CAFEF_PENALTY_URL}")
        except Exception as e:
            logger.error(f"[PENALTY] Error crawling: {e}")

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique = []
    for article in articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique.append(article)

    return unique[:max_articles]


def crawl_macro_news(max_articles: int = 20) -> list[dict]:
    """
    Crawl macro/policy news from CafeF (vi-mo-dau-tu, tai-chinh-ngan-hang).
    Stored with ticker='MACRO' for use as context in LLM analysis.

    Returns:
        List of article dicts with ticker='MACRO' and source='cafef_macro'
    """
    articles = []
    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        for url in CAFEF_MACRO_URLS:
            try:
                response = client.get(url)
                if response.status_code == 200:
                    parsed = _parse_cafef_list_page(response.text, source_label="cafef_macro", ticker="MACRO")
                    articles.extend(parsed)
                    logger.info(f"[MACRO] Crawled {len(parsed)} articles from {url}")
                else:
                    logger.warning(f"[MACRO] HTTP {response.status_code} for {url}")
            except Exception as e:
                logger.error(f"[MACRO] Error crawling {url}: {e}")

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique = []
    for article in articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique.append(article)

    return unique[:max_articles]