"""Cross-ticker scan.

Runs the full debate over the US-ticker universe (loaded from the Google Sheet)
and writes per-ticker JSON + a ranked leaderboard JSON to Blob (or
``LOCAL_RESULTS_DIR`` in dev). Designed for matrix-sharded GitHub Actions:

    python -m app.scan --shard 0 --shards 4
    python -m app.scan --tickers AAPL,MSFT,NVDA      # ad-hoc subset
    python -m app.scan --merge-index                  # rebuild today's index.json
    python -m app.scan --merge-index --date 2026-06-03

Per-ticker failures are caught and logged so one bad symbol can't kill the scan.
Each verdict is written to storage IMMEDIATELY on completion, so a 5-hour job
that crashes at hour 4 still keeps partial results.

Ranking signal: ``net_bull_score = weights[bull] - weights[bear]`` (continuous,
sortable, naturally surfaces both top buys and top shorts in one scan).
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from . import config, storage, universe
from .orchestrator import run_debate


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _select_tickers(args: argparse.Namespace) -> list[str]:
    if args.tickers:
        return [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    universe_tickers = universe.load_tickers()
    if args.shards and args.shard is not None:
        # tickers[shard::shards] = round-robin assignment; balances workload.
        return universe_tickers[args.shard :: args.shards]
    return universe_tickers


_to_persisted_payload = storage.to_persisted_payload  # backwards-compat alias


def _run_one(ticker: str, rounds: int | None, date: str) -> dict[str, Any]:
    """Run one debate, write its verdict, and return a per-ticker timing record.

    Pulled out as a top-level function so ThreadPoolExecutor can submit it for
    the concurrent-scan path. Catches exceptions per-ticker — one bad symbol
    shouldn't kill a scan of many.
    """
    t0 = time.perf_counter()
    try:
        result = run_debate(ticker, rounds=rounds)
        storage.put_verdict(date, ticker, _to_persisted_payload(ticker, result))
        v = result.get("verdict", {})
        return {
            "ticker": ticker,
            "elapsed": round(time.perf_counter() - t0, 2),
            "verdict": v.get("verdict"),
            "net_bull_score": v.get("net_bull_score"),
            "error": None,
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "ticker": ticker,
            "elapsed": round(time.perf_counter() - t0, 2),
            "verdict": None,
            "net_bull_score": None,
            "error": str(e),
        }


def scan_universe(
    date: str | None = None,
    shard: int | None = None,
    shards: int | None = None,
    tickers: list[str] | None = None,
    write_index: bool = True,
    rounds: int | None = None,
    concurrency: int = 1,
) -> dict[str, Any]:
    """Run debates over the (optionally sharded) universe and persist results.

    ``rounds`` overrides config.DEBATE_ROUNDS for each debate (useful for the
    UI "Run scan" button, which defaults to a 1-round fast scan).
    ``concurrency`` runs that many debates in parallel via ThreadPoolExecutor.
    Default 1 = serial (preserves existing behavior); the UI passes 3, which
    is the empirical sweet spot before Azure rate-limit retries eat the gains.

    Returns a dict with: ``date``, ``ok``, ``fail`` (list of failed tickers),
    ``timings`` (per-ticker {ticker, elapsed, verdict, net_bull_score, error}),
    ``wall_time`` (total seconds), ``ranked`` (the merged leaderboard rows when
    written, else []).
    """
    date = date or _today()
    ns = argparse.Namespace(
        tickers=",".join(tickers) if tickers else "", shard=shard, shards=shards
    )
    targets = _select_tickers(ns)
    print(
        f"[scan] date={date}  shard={shard}/{shards}  tickers={len(targets)}  "
        f"rounds={rounds or 'default'}  concurrency={concurrency}"
    )

    t_total0 = time.perf_counter()
    timings: list[dict[str, Any]] = []
    if concurrency > 1 and len(targets) > 1:
        max_workers = min(concurrency, len(targets))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_one, t, rounds, date): t for t in targets}
            for fut in as_completed(futures):
                rec = fut.result()
                timings.append(rec)
                if rec["error"]:
                    print(f"[scan]   FAIL {rec['ticker']}: {rec['error']}", flush=True)
                else:
                    print(
                        f"[scan]   {rec['ticker']} -> {rec['verdict']} "
                        f"net={rec['net_bull_score']} in {rec['elapsed']}s",
                        flush=True,
                    )
    else:
        for i, ticker in enumerate(targets, 1):
            print(f"[scan] ({i}/{len(targets)}) {ticker} ...", flush=True)
            rec = _run_one(ticker, rounds, date)
            timings.append(rec)
            if rec["error"]:
                print(f"[scan]   FAIL {ticker}: {rec['error']}", flush=True)
            else:
                print(
                    f"[scan]   -> {rec['verdict']}  net={rec['net_bull_score']} in {rec['elapsed']}s",
                    flush=True,
                )

    wall_time = round(time.perf_counter() - t_total0, 2)
    failures = [r["ticker"] for r in timings if r["error"]]
    ok = len(timings) - len(failures)
    print(f"[scan] done. ok={ok} fail={len(failures)} wall={wall_time}s")
    if failures:
        print(f"[scan] failed tickers: {failures}")

    ranked: list[dict[str, Any]] = []
    if write_index and shards in (None, 1):
        # Sharded runs would race on index.json; the CI workflow's merge job
        # handles that case with --merge-index after all shards finish.
        idx_payload = storage.write_merged_index(date)
        ranked = idx_payload.get("ranked", []) or []
        print(f"[scan] index.json has {len(ranked)} ranked entries")

    return {
        "date": date,
        "ok": ok,
        "fail": failures,
        "timings": timings,
        "wall_time": wall_time,
        "ranked": ranked,
    }


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MarketDebater cross-ticker scan")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today UTC)")
    p.add_argument("--shard", type=int, default=None, help="0-indexed shard id")
    p.add_argument("--shards", type=int, default=None, help="total shard count")
    p.add_argument("--tickers", default="", help="comma-separated ticker subset (overrides universe)")
    p.add_argument(
        "--merge-index",
        action="store_true",
        help="Recompute index.json from already-written per-ticker blobs (CI merge step).",
    )
    args = p.parse_args(argv)

    if not storage.is_configured():
        print(
            "[scan] WARNING: neither AZURE_STORAGE_CONNECTION_STRING nor LOCAL_RESULTS_DIR "
            "is set — verdicts will not be persisted.",
            file=sys.stderr,
        )

    if args.merge_index:
        date = args.date or _today()
        payload = storage.write_merged_index(date)
        print(f"[merge] {date}: {len(payload['ranked'])} ranked entries")
        if payload["ranked"]:
            top = payload["ranked"][0]
            bot = payload["ranked"][-1]
            print(f"[merge] top:    {top['ticker']:6} net={top['net_bull_score']:+.3f}  {top['verdict']}")
            print(f"[merge] bottom: {bot['ticker']:6} net={bot['net_bull_score']:+.3f}  {bot['verdict']}")
        return 0

    scan_universe(
        date=args.date,
        shard=args.shard,
        shards=args.shards,
        tickers=[t.strip() for t in args.tickers.split(",") if t.strip()] or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
