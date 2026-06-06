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
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from . import filings_client, news_client, prices_client, universe


def _timed(fn, *args, **kwargs):
    """Run ``fn(*args, **kwargs)`` and return ``(result, elapsed_seconds)``."""
    t0 = time.perf_counter()
    try:
        return fn(*args, **kwargs), time.perf_counter() - t0
    except Exception as exc:
        # Return a sentinel + elapsed; the caller maps None into the empty default.
        return exc, time.perf_counter() - t0


def aggregate(ticker: str) -> dict[str, Any]:
    """Fetch prices, news, and filings in parallel for one ticker."""
    cik = ""
    try:
        cik = universe.cik_for(ticker)
    except Exception:
        # universe sheet may be unavailable in dev; CIK is optional anyway.
        cik = ""

    wall_t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snap = pool.submit(_timed, prices_client.get_market_snapshot, ticker)
        f_news = pool.submit(_timed, news_client.get_news, ticker)
        f_bundle = pool.submit(_timed, filings_client.get_filings_bundle, ticker, cik)
        snap_raw, t_snap = f_snap.result()
        news_raw, t_news = f_news.result()
        bundle_raw, t_bundle = f_bundle.result()

    # _timed returns exceptions instead of raising; reraise prices errors (fatal)
    # but tolerate news/filings failures so the debate can still run.
    if isinstance(snap_raw, Exception):
        raise snap_raw
    snap = snap_raw.to_dict()
    news = [] if isinstance(news_raw, Exception) else (news_raw or [])
    bundle = {"filings": [], "metrics": {}} if isinstance(bundle_raw, Exception) else (bundle_raw or {"filings": [], "metrics": {}})
    wall = time.perf_counter() - wall_t0
    print(
        f"[timing] {ticker} data: prices={t_snap:.1f}s news={t_news:.1f}s "
        f"filings={t_bundle:.1f}s wall={wall:.1f}s",
        flush=True,
    )

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
