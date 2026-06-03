"""Data Aggregator — fans out to three I/O-bound clients in parallel.

Three co-equal inputs feed the debate:
  - **Prices** (yfinance, technicals computed locally) — see app.prices_client
  - **News**   (Grok web search, RSS fallback)        — see app.news_client
  - **Filings**(sec-api.io 10-K/10-Q/8-K + XBRL)      — see app.filings_client

The public ``aggregate(ticker) -> {snapshot, news, filings, filings_metrics}``
shape is what every downstream layer (agents, chair, orchestrator, scan, search)
depends on. Filings-derived metrics are also folded into the snapshot so the
existing flat-key grounding verifier in chair.py works without changes.

CLI:  python -m app.data_aggregator AAPL
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from . import filings_client, news_client, prices_client, universe


def aggregate(ticker: str) -> dict[str, Any]:
    """Fetch prices, news, and filings in parallel for one ticker."""
    cik = ""
    try:
        cik = universe.cik_for(ticker)
    except Exception:
        # universe sheet may be unavailable in dev; CIK is optional anyway.
        cik = ""

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snap = pool.submit(prices_client.get_market_snapshot, ticker)
        f_news = pool.submit(news_client.get_news, ticker)
        f_bundle = pool.submit(filings_client.get_filings_bundle, ticker, cik)
        snap = f_snap.result().to_dict()
        news = f_news.result() or []
        bundle = f_bundle.result() or {"filings": [], "metrics": {}}

    metrics = bundle.get("metrics", {}) or {}
    # Fold filings-derived metrics into the snapshot so chair.verify_grounding()
    # can resolve `revenue=...`, `eps_diluted=...` etc. without code changes.
    for k, v in metrics.items():
        snap.setdefault(k, v)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": snap,
        "news": news,
        "filings": bundle.get("filings", []) or [],
        "filings_metrics": metrics,
    }


def _main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    data = aggregate(ticker)
    s = data["snapshot"]
    print(f"\n=== {s['company']} ({s['ticker']}) — as of {s['as_of']} ===")
    print(f"  Price {s['currency']} {s['price']}  ({s['change_pct']:+}% vs prev close)")
    print(f"  RSI(14): {s['rsi_14']}   SMA 20/50/200: {s['sma_20']} / {s['sma_50']} / {s['sma_200']}")
    print(f"\n  News ({len(data['news'])} items):")
    for n in data["news"][:5]:
        print(f"   - {n['title']}  [{n['source']}]")
    print(f"\n  Filings ({len(data['filings'])} items):")
    for f in data["filings"][:5]:
        print(f"   - {f['form']:6} {f['filed_at']}  {(f['sections'] or '')[:80]!r}")
    print(f"\n  Filings metrics: {data['filings_metrics']}")
    assert 0 <= s["rsi_14"] <= 100, "RSI out of range"
    assert s["price"] > 0, "Non-positive price"
    print("\nOK: snapshot valid, RSI in range, fetched ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
