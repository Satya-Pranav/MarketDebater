"""News client — Grok (via Azure AI Foundry) with RSS fallback.

Foundry's model catalog now serves xAI Grok behind the same OpenAI-compatible
``/openai/v1`` endpoint and the same Azure key — so we reuse the project's
existing LLM client (``llm.chat_json``) and just route to ``GROK_MODEL``
(e.g. ``grok-4-1-fast-reasoning``). No separate xAI subscription needed.

Grok models served via Foundry do not expose a built-in ``web_search`` tool, so
we use Grok to **summarize and rank a small bundle of Google News RSS items**,
which gives us both live URLs (RSS) and Grok's reasoning-model judgment about
which items are actually material. When ``GROK_MODEL`` is unset, we skip the LLM
step and pass raw RSS through.

Public surface:
    get_news(query, limit=8) -> list[{title, source, url, summary, published}]

CLI:  python -m app.news_client AAPL
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from typing import Any

from . import config
from .llm import chat_json

_RSS_PRIMARY_LIMIT = 20  # pull this many from RSS, let Grok cut to `limit`

_NEWS_SYSTEM = (
    "You are a financial news editor. You receive a list of recent news "
    "headlines about a US-listed company (with source + URL). Your job is to "
    "SELECT and SUMMARIZE the most market-moving items (earnings, guidance, "
    "M&A, regulatory, analyst rating changes, product launches, leadership) "
    "and drop noise (rumor, opinion pieces, repeat coverage). "
    "Return ONLY a JSON object of the exact shape "
    '{"articles": [{"title": str, "source": str, "url": str, "summary": str, '
    '"published": str}]}. Preserve the original URL exactly. Each summary <= 280 chars. '
    "No commentary, no markdown, no <think> in the FINAL output."
)


def _rss_news(query: str, limit: int) -> list[dict[str, str]]:
    """Google News RSS (US edition). Free, no key required.

    Uses requests for the fetch (bundled certs) + feedparser for parsing,
    since feedparser's stdlib-urllib fetch hits SSL cert verification errors
    on stock macOS Python installs.
    """
    try:
        import feedparser  # type: ignore
        import requests
    except ImportError:
        return []
    q = urllib.parse.quote_plus(f"{query} stock")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(
            url, timeout=20, headers={"User-Agent": "Mozilla/5.0 MarketDebater/1.0"}
        )
        resp.raise_for_status()
    except Exception:
        return []
    feed = feedparser.parse(resp.content)
    items: list[dict[str, str]] = []
    for entry in feed.entries[:limit]:
        src = entry.get("source")
        items.append(
            {
                "title": entry.get("title", ""),
                "source": src.get("title", "Google News") if isinstance(src, dict) else "Google News",
                "published": entry.get("published", ""),
                "url": entry.get("link", ""),
                "summary": (entry.get("summary", "") or "")[:400],
            }
        )
    return items


def _grok_filter(raw: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    """Route a raw RSS bundle through Grok-via-Foundry for selection + summarization."""
    if not raw:
        return raw
    user = (
        f"Pick the top {limit} most material items from this list of recent news. "
        f"Return them in the JSON shape described in the system message. "
        f"Items:\n{json.dumps(raw, indent=2, default=str)}"
    )
    try:
        data = chat_json(
            _NEWS_SYSTEM,
            user,
            deployment=config.GROK_MODEL,
            temperature=0.3,
            is_reasoning_model=True,
        )
    except Exception:
        return raw[:limit]

    out: list[dict[str, str]] = []
    for a in (data.get("articles") or [])[:limit]:
        if not isinstance(a, dict) or not a.get("title"):
            continue
        out.append(
            {
                "title": str(a.get("title", "")).strip(),
                "source": str(a.get("source", "Google News")).strip(),
                "url": str(a.get("url", "")).strip(),
                "summary": str(a.get("summary", "")).strip()[:400],
                "published": str(a.get("published", "")).strip(),
            }
        )
    return out or raw[:limit]


def get_news(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Recent headlines for a US-listed company/ticker.

    Pulls a raw bundle from Google News RSS, then (if ``GROK_MODEL`` is set)
    routes it through Foundry-served Grok to pick the most material items and
    write tight summaries. Returns RSS-only when Grok is unconfigured or errors.
    """
    raw = _rss_news(query, _RSS_PRIMARY_LIMIT)
    if not raw:
        return []
    if config.GROK_MODEL:
        return _grok_filter(raw, limit)
    return raw[:limit]


def _main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    items = get_news(query)
    src = f"GROK ({config.GROK_MODEL})" if config.GROK_MODEL else "RSS"
    print(f"[{src}] {len(items)} news items for {query!r}:")
    for n in items:
        print(f"  - {n['title']}  [{n['source']}]")
        if n.get("summary"):
            print(f"    {n['summary'][:160]}")
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(_main())
