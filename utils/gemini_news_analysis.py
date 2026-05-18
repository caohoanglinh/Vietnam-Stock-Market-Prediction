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


def build_prompt(ticker: str, analysis_date: date, articles: list[dict[str, Any]]) -> str:
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

    return f"""
You are a financial-news analyst for Vietnamese stocks.
Analyze the news items for ticker {ticker} on {analysis_date.isoformat()}.
Use only the provided articles. Do not invent facts. Do not forecast exact prices.
If the evidence is weak, sparse, duplicated, or contradictory, prefer a neutral sentiment and lower confidence.
Return only one JSON object with exactly these keys:
- sentiment: one of [positive, neutral, negative]
- impact_horizon: one of [1d, 5d, 10d, mixed]
- confidence: float from 0 to 1
- news_score: float from -1 to 1
- summary: string with 2 to 4 concise sentences
- bull_points: array of up to 3 short bullet strings
- bear_points: array of up to 3 short bullet strings
- risk_flags: array of up to 3 short bullet strings

Scoring guidance:
- positive means the news flow is net supportive for the stock
- negative means the news flow is net harmful for the stock
- neutral means no clear directional edge
- news_score should be near 0 when the evidence is mixed or weak

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
            "maxOutputTokens": 700,
        },
    }


def analyze_ticker_news(
    ticker: str,
    analysis_date: date,
    articles: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, Any]:
    if not articles:
        raise ValueError(f"No articles provided for ticker {ticker}")

    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    url = GEMINI_API_URL.format(model=model_name, api_key=resolved_api_key)
    prompt = build_prompt(ticker=ticker, analysis_date=analysis_date, articles=articles)
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
