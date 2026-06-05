"""US-ticker universe loader.

Default source is the curated watchlist file (``app/data/watchlist.txt``, one
ticker per line, ``#`` comments and blanks ignored). Small + deterministic, so
the scan finishes in well under an hour and the cron stays predictable.

For broader coverage, set ``UNIVERSE_FROM_SHEET=1`` to fall back to the Google
Sheet of US IR-database tickers (~4.6k rows including SPACs/warrants — handle
the volume before turning this on).

CLI:  python -m app.universe        # prints count + first 10 tickers
"""
from __future__ import annotations

import csv
import io
import os
import sys
from typing import Any

import requests

from . import config


# --------------------------------------------------------------------------- #
# Watchlist (default source)                                                  #
# --------------------------------------------------------------------------- #
def _read_watchlist(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line.split()[0].upper())
    # De-dupe preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


# --------------------------------------------------------------------------- #
# Google Sheet (opt-in, ~4.6k tickers)                                        #
# --------------------------------------------------------------------------- #
def _csv_url() -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{config.UNIVERSE_SHEET_ID}"
        f"/export?format=csv&gid={config.UNIVERSE_SHEET_GID}"
    )


def _fetch_csv() -> str:
    resp = requests.get(
        _csv_url(),
        headers={"User-Agent": "MarketDebater/1.0 (+https://github.com/Satya-Pranav/MarketDebater)"},
        timeout=30,
        allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def load_universe() -> list[dict[str, str]]:
    """Return all rows from the Google Sheet as dicts (full metadata).

    Used for richer per-ticker info (CIK, IR URL, 8-K feed); call ``load_tickers()``
    if you only need symbols. Raises on fetch failure.
    """
    text = _fetch_csv()
    reader = csv.DictReader(io.StringIO(text))
    rows = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    if not rows:
        raise RuntimeError(f"Universe sheet returned no rows ({_csv_url()})")
    return rows


def _tickers_from_sheet() -> list[str]:
    rows = load_universe()
    key = next((k for k in rows[0].keys() if k.lower() in {"ticker", "symbol"}), None)
    if not key:
        raise RuntimeError(
            f"No Ticker/Symbol column in sheet. Columns: {list(rows[0].keys())}"
        )
    tickers = [r[key].upper() for r in rows if r.get(key)]
    seen: set[str] = set()
    out: list[str] = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def load_tickers() -> list[str]:
    """Return the active ticker universe.

    Reads ``WATCHLIST_FILE`` (default ``app/data/watchlist.txt``) by default.
    Set ``UNIVERSE_FROM_SHEET=1`` to use the Google Sheet (~4.6k tickers) instead.
    """
    if config.UNIVERSE_FROM_SHEET:
        return _tickers_from_sheet()
    tickers = _read_watchlist(config.WATCHLIST_FILE)
    if not tickers:
        raise RuntimeError(
            f"Watchlist {config.WATCHLIST_FILE!r} is empty or missing. "
            "Add tickers to it or set UNIVERSE_FROM_SHEET=1."
        )
    return tickers


def cik_for(ticker: str) -> str:
    """Return the SEC CIK for a ticker if the sheet has it; '' otherwise.

    Always hits the sheet (CIK isn't in the watchlist file) — best-effort,
    swallows fetch errors so callers can keep going without CIK enrichment.
    """
    try:
        for row in load_universe():
            if row.get("Ticker", "").upper() == ticker.upper():
                cik = row.get("CIK", "").strip()
                return cik.zfill(10) if cik.isdigit() else cik
    except Exception:
        pass
    return ""


def metadata_for(ticker: str) -> dict[str, Any]:
    """Return the full sheet row for a ticker, or {} on miss/failure."""
    try:
        for row in load_universe():
            if row.get("Ticker", "").upper() == ticker.upper():
                return row
    except Exception:
        pass
    return {}


def _main() -> int:
    src = "sheet" if config.UNIVERSE_FROM_SHEET else f"watchlist ({config.WATCHLIST_FILE})"
    tickers = load_tickers()
    print(f"[{src}] {len(tickers)} tickers")
    print("First 10:", tickers[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
