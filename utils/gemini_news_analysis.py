from __future__ import annotations

import json
import logging
import os
import time
from datetime import date
from typing import Any

import httpx


logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "gemini-2.5-flash-lite"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
REQUEST_TIMEOUT_SECONDS = 60
MAX_RETRIES = 5
INTER_REQUEST_DELAY_SECONDS = 4.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
ALLOWED_SENTIMENTS = {"positive", "neutral", "negative"}
ALLOWED_HORIZONS = {"1d", "5d", "10d", "mixed"}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_list(value: Any, max_items: int = 3) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned[:max_items]
    text = str(value).strip()
    return [text] if text else []


def _extract_response_text(response_json: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in response_json.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    if not parts:
        raise ValueError("Gemini response did not contain text parts")
    return "\n".join(parts).strip()


def _extract_first_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in Gemini response")

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : idx + 1])

    raise ValueError("Incomplete JSON object in Gemini response")


def _normalize_output(parsed: dict[str, Any]) -> dict[str, Any]:
    sentiment = str(parsed.get("sentiment") or "neutral").strip().lower()
    if sentiment not in ALLOWED_SENTIMENTS:
        sentiment = "neutral"

    impact_horizon = str(parsed.get("impact_horizon") or "mixed").strip().lower()
    if impact_horizon not in ALLOWED_HORIZONS:
        impact_horizon = "mixed"

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = round(_clamp(confidence, 0.0, 1.0), 4)

    try:
        news_score = float(parsed.get("news_score", 0.0))
    except (TypeError, ValueError):
        news_score = 0.0
    news_score = round(_clamp(news_score, -1.0, 1.0), 4)

    summary = str(parsed.get("summary") or "").strip()

    return {
        "sentiment": sentiment,
        "impact_horizon": impact_horizon,
        "confidence": confidence,
        "news_score": news_score,
        "summary": summary,
        "bull_points": _normalize_list(parsed.get("bull_points")),
        "bear_points": _normalize_list(parsed.get("bear_points")),
        "risk_flags": _normalize_list(parsed.get("risk_flags")),
    }


def build_prompt(
    ticker: str,
    analysis_date: date,
    articles: list[dict[str, Any]],
    macro_headlines: list[str] | None = None,
) -> str:
    compact_articles = [
        {
            "title": article.get("title"),
            "summary": article.get("summary"),
            "published_at": article.get("publishedAt"),
            "source": article.get("source"),
            "url": article.get("url"),
        }
        for article in articles
    ]
    articles_json = json.dumps(compact_articles, ensure_ascii=False, indent=2)

    macro_section = ""
    if macro_headlines:
        headlines_text = "\n".join(f"- {h}" for h in macro_headlines[:10])
        macro_section = f"""
Macro & Market Context (today's top macro/regulatory headlines — use for risk awareness only):
{headlines_text}
"""

    return f"""
You are a skeptical buy-side analyst for Vietnamese stocks. Your job is to find BOTH the upside AND the risks.
Analyze the news items for ticker {ticker} on {analysis_date.isoformat()}.
Use only the provided articles and macro context below. Do not invent facts. Do not forecast exact prices.

CRITICAL RULES:
1. You MUST populate bear_points with at least 1 item, even for seemingly positive news.
   Think like a short-seller: what could go wrong? What is the market already pricing in?
2. You MUST populate risk_flags with at least 1 item. Look for: dilution risk, insider selling,
   regulatory risk, sector headwinds, high valuation, debt concerns, or macro risks.
3. news_score should only be strongly positive (>0.5) if the news is GENUINELY SURPRISING
   (unexpected earnings beat, major new contract, strategic acquisition).
   Routine events (dividend, planned capital raise, share buyback registration) should score near 0.
4. If the only news is a management insider BUY registration, be cautious — this often signals
   insiders protecting price before a difficult period. Mark confidence low.
5. If the evidence is weak, sparse, duplicated, or contradictory, prefer neutral sentiment.

Scoring examples:
- Capital raise (tăng vốn) → bull: more resources; bear: dilution risk → news_score: 0.0 to 0.2
- Insider buy registration → bull: confidence signal; bear: could be price defense → news_score: 0.1 to 0.3
- UBCKNN fine/penalty → sentiment: negative; news_score: -0.5 to -0.8
- Major unexpected partnership → sentiment: positive; news_score: 0.5 to 0.8
- Generic market recap → sentiment: neutral; news_score: 0.0

Return ONLY one JSON object with exactly these keys:
- sentiment: one of [positive, neutral, negative]
- impact_horizon: one of [1d, 5d, 10d, mixed]
- confidence: float from 0 to 1
- news_score: float from -1 to 1
- summary: string with 2 to 4 concise sentences
- bull_points: array of up to 3 short bullet strings (REQUIRED — never empty)
- bear_points: array of up to 3 short bullet strings (REQUIRED — never empty)
- risk_flags: array of up to 3 short bullet strings (REQUIRED — never empty)
{macro_section}
Articles:
{articles_json}
""".strip()


def _build_request_body(prompt: str) -> dict[str, Any]:
    return {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.15,
            "topP": 0.8,
            "maxOutputTokens": 1000,
        },
    }


def extract_tickers_from_penalty_articles(
    articles: list[dict[str, Any]],
    known_tickers: list[str],
    *,
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> list[dict[str, Any]]:
    """
    Batch LLM call: given a list of penalty/regulatory articles,
    extract which ticker(s) each article is about.

    Returns a list of dicts: [{"article_index": int, "tickers": [str, ...]}, ...]
    Only returns entries where tickers were found.
    """
    if not articles:
        return []

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    tickers_str = ", ".join(known_tickers)
    articles_list = [
        {"index": i, "title": a.get("title", ""), "summary": a.get("summary", "")}
        for i, a in enumerate(articles)
    ]
    articles_json = json.dumps(articles_list, ensure_ascii=False, indent=2)

    prompt = f"""You are a Vietnamese stock market expert.
Below is a list of regulatory/penalty news articles from Vietnam's financial market.
For each article, identify which Vietnamese stock ticker codes (from the list below) are mentioned
or are clearly the subject of the article.

Known tickers: {tickers_str}

Return ONLY a JSON array. Each element must have:
- "index": the article index (integer)
- "tickers": array of matching ticker strings (empty array if none found)

Only include entries where at least one ticker was found.
Do not include articles that are general market news with no specific company.

Articles:
{articles_json}""".strip()

    url = GEMINI_API_URL.format(model=model_name, api_key=resolved_api_key)
    request_body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.05, "maxOutputTokens": 800},
    }

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.post(url, json=request_body)
                if response.status_code == 200:
                    text = _extract_response_text(response.json())
                    # Extract JSON array from response
                    start = text.find("[")
                    end = text.rfind("]") + 1
                    if start == -1 or end == 0:
                        logger.warning("No JSON array in penalty extraction response")
                        return []
                    results = json.loads(text[start:end])
                    return [r for r in results if r.get("tickers")]
                if response.status_code in RETRYABLE_STATUS_CODES:
                    time.sleep(min(60, 2 ** attempt))
                    continue
                logger.error("Penalty ticker extraction failed: status=%s", response.status_code)
                return []
            except Exception as exc:
                logger.warning("Penalty extraction attempt %s failed: %s", attempt, exc)
                if attempt >= MAX_RETRIES:
                    return []
                time.sleep(min(60, 2 ** attempt))
    return []


def analyze_ticker_news(
    ticker: str,
    analysis_date: date,
    articles: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    macro_headlines: list[str] | None = None,
) -> dict[str, Any]:
    if not articles:
        raise ValueError(f"No articles provided for ticker {ticker}")

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    url = GEMINI_API_URL.format(model=model_name, api_key=resolved_api_key)
    prompt = build_prompt(
        ticker=ticker,
        analysis_date=analysis_date,
        articles=articles,
        macro_headlines=macro_headlines,
    )
    request_body = _build_request_body(prompt)

    last_error: Exception | None = None
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.post(url, json=request_body)
                if response.status_code == 200:
                    response_json = response.json()
                    response_text = _extract_response_text(response_json)
                    parsed = _extract_first_json_object(response_text)
                    normalized = _normalize_output(parsed)
                    return {
                        **normalized,
                        "model_name": model_name,
                        "raw_response": {
                            "response_text": response_text,
                            "response_json": response_json,
                        },
                    }

                if response.status_code in RETRYABLE_STATUS_CODES:
                    wait_seconds = min(60, 2 ** attempt)
                    logger.warning(
                        "Gemini retryable error for %s attempt %s/%s: status=%s wait=%ss",
                        ticker,
                        attempt,
                        MAX_RETRIES,
                        response.status_code,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue

                snippet = response.text[:500]
                raise RuntimeError(f"Gemini API failed for {ticker} with status {response.status_code}: {snippet}")
            except Exception as exc:
                last_error = exc
                if attempt >= MAX_RETRIES:
                    break
                wait_seconds = min(60, 2 ** attempt)
                logger.warning(
                    "Gemini exception for %s attempt %s/%s: %s. Retrying in %ss",
                    ticker,
                    attempt,
                    MAX_RETRIES,
                    exc,
                    wait_seconds,
                )
                time.sleep(wait_seconds)

    raise RuntimeError(f"Gemini analysis failed for {ticker}: {last_error}")
