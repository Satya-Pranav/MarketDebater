"""SEC filings client — sec-api.io wrapper.

Pulls the last few 10-K / 10-Q / 8-K filings for a US ticker, extracts a
representative section per filing (Risk Factors for periodic filings, item body
for 8-Ks), and pulls a tiny set of XBRL-derived fundamentals from the latest
10-Q so the Chair grounding verifier can fact-check claims like
``revenue=395760000000``.

Graceful degradation: missing ``SEC_API_KEY`` → returns empty lists / dicts,
the debate still runs from price + news.

Public surface:
    get_recent_filings(ticker, cik='') -> list[{form, filed_at, url, summary, sections}]
    get_filings_metrics(ticker, cik='')  -> dict[str, float]
    get_filings_bundle(ticker, cik='')   -> {"filings": [...], "metrics": {...}}

CLI:  python -m app.filings_client AAPL
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from typing import Any

import requests

from . import config


# How many filings to pull per ticker. Each filing => 1 query + 1 section + 1 XBRL.
_MAX_FILINGS = 4
_SECTION_TRIM_CHARS = 2000
_HTTP_TIMEOUT = 30

# 10-K / 10-Q section keys (per sec-api.io Section Extractor docs).
#   1A = Risk Factors   7  = MD&A   1  = Business
_PERIODIC_SECTION = "1A"

# Minimal XBRL pulls we actually use to ground numeric claims.
# Keys are the snapshot field name; values are XBRL StatementsOfIncome /
# BalanceSheets concept names.
_XBRL_FIELDS = {
    "revenue": ("StatementsOfIncome", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    "revenue_total": ("StatementsOfIncome", "Revenues"),
    "gross_profit": ("StatementsOfIncome", "GrossProfit"),
    "operating_income": ("StatementsOfIncome", "OperatingIncomeLoss"),
    "net_income": ("StatementsOfIncome", "NetIncomeLoss"),
    "eps_diluted": ("StatementsOfIncome", "EarningsPerShareDiluted"),
    "total_assets": ("BalanceSheets", "Assets"),
    "total_liabilities": ("BalanceSheets", "Liabilities"),
    "stockholders_equity": ("BalanceSheets", "StockholdersEquity"),
}


def is_configured() -> bool:
    return bool(config.SEC_API_KEY)


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{config.SEC_API_BASE.rstrip('/')}{path}?token={urllib.parse.quote(config.SEC_API_KEY)}"
    resp = requests.post(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _get(path: str, params: dict[str, str]) -> Any:
    url = f"{config.SEC_API_BASE.rstrip('/')}{path}"
    resp = requests.get(
        url,
        params={**params, "token": config.SEC_API_KEY},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    # /extractor returns text/plain; others return JSON.
    ct = resp.headers.get("Content-Type", "")
    if "json" in ct:
        return resp.json()
    try:
        return resp.json()
    except ValueError:
        return resp.text


def _query_recent_filings(ticker: str) -> list[dict[str, Any]]:
    body = {
        "query": (
            f'ticker:{ticker} AND (formType:"10-K" OR formType:"10-Q" OR formType:"8-K")'
        ),
        "from": "0",
        "size": str(_MAX_FILINGS),
        "sort": [{"filedAt": {"order": "desc"}}],
    }
    data = _post("", body)
    return list(data.get("filings", []) or [])


def _extract_section(filing_url: str, item: str) -> str:
    """Pull cleaned text of one section from a 10-K/10-Q filing."""
    try:
        text = _get(
            "/extractor",
            {"url": filing_url, "item": item, "type": "text"},
        )
        if isinstance(text, dict):
            text = json.dumps(text)
        text = (text or "").strip()
        return text[:_SECTION_TRIM_CHARS]
    except Exception:
        return ""


def _summarize_filing(f: dict[str, Any]) -> dict[str, Any]:
    """Per-filing fetch: section text for periodics; item description for 8-Ks."""
    form = (f.get("formType") or "").upper()
    url = f.get("linkToFilingDetails") or f.get("linkToHtml") or f.get("linkToTxt") or ""
    section = ""
    if form in {"10-K", "10-Q"} and url:
        section = _extract_section(url, _PERIODIC_SECTION)
    elif form == "8-K":
        # 8-K bodies are short — the metadata's `items` + `description` is usually enough,
        # so we skip the section extractor call and save quota.
        items = f.get("items") or []
        desc = f.get("description") or ""
        section = ("; ".join(map(str, items)) + " — " + desc).strip(" —")[:_SECTION_TRIM_CHARS]
    return {
        "form": form,
        "filed_at": f.get("filedAt", ""),
        "period_of_report": f.get("periodOfReport", ""),
        "url": url,
        "summary": (f.get("description") or "")[:300],
        "sections": section,
    }


def get_recent_filings(ticker: str, cik: str = "") -> list[dict[str, Any]]:
    """Return the last ~4 filings (10-K/10-Q/8-K) with extracted snippets."""
    if not is_configured():
        return []
    try:
        raw = _query_recent_filings(ticker)
    except Exception:
        return []
    return [_summarize_filing(f) for f in raw[:_MAX_FILINGS]]


def _latest_periodic_url(ticker: str) -> str:
    """URL of the most recent 10-Q (preferred) or 10-K."""
    body = {
        "query": f'ticker:{ticker} AND (formType:"10-Q" OR formType:"10-K")',
        "from": "0",
        "size": "1",
        "sort": [{"filedAt": {"order": "desc"}}],
    }
    try:
        data = _post("", body)
        filings = data.get("filings") or []
        if not filings:
            return ""
        f = filings[0]
        return f.get("linkToFilingDetails") or f.get("linkToHtml") or ""
    except Exception:
        return ""


def _xbrl(filing_url: str) -> dict[str, Any]:
    try:
        return _get("/xbrl-to-json", {"htm-url": filing_url}) or {}
    except Exception:
        return {}


def _first_numeric(values: list[dict[str, Any]]) -> float | None:
    """Pick the most recent (largest endDate) USD value from an XBRL field list."""
    if not values:
        return None
    usd = [v for v in values if (v.get("unitRef") or "").upper().startswith("USD")] or values
    usd.sort(key=lambda v: v.get("period", {}).get("endDate", ""), reverse=True)
    raw = usd[0].get("value")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def get_filings_metrics(ticker: str, cik: str = "") -> dict[str, float]:
    """Return a tiny dict of XBRL-derived fundamentals from the latest periodic filing.

    Keys (when available): revenue, gross_profit, operating_income, net_income,
    eps_diluted, total_assets, total_liabilities, stockholders_equity,
    gross_margin (derived), debt_to_equity (derived).
    """
    if not is_configured():
        return {}
    url = _latest_periodic_url(ticker)
    if not url:
        return {}
    xbrl = _xbrl(url)
    out: dict[str, float] = {}
    for key, (statement, concept) in _XBRL_FIELDS.items():
        section = xbrl.get(statement) or {}
        values = section.get(concept) if isinstance(section, dict) else None
        if isinstance(values, list):
            n = _first_numeric(values)
            if n is not None:
                out[key] = round(n, 4)
    # Prefer the "ExcludingAssessedTax" concept; fall back to Revenues if absent.
    if "revenue" not in out and "revenue_total" in out:
        out["revenue"] = out["revenue_total"]
    out.pop("revenue_total", None)
    # Derived ratios — only when inputs are present.
    if "gross_profit" in out and out.get("revenue"):
        out["gross_margin"] = round(out["gross_profit"] / out["revenue"], 4)
    if "total_liabilities" in out and out.get("stockholders_equity"):
        out["debt_to_equity"] = round(out["total_liabilities"] / out["stockholders_equity"], 4)
    return out


def get_filings_bundle(ticker: str, cik: str = "") -> dict[str, Any]:
    """Convenience: filings list + metrics in one shot."""
    return {
        "filings": get_recent_filings(ticker, cik),
        "metrics": get_filings_metrics(ticker, cik),
    }


def _main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    if not is_configured():
        print("SEC_API_KEY not set — get_recent_filings() / get_filings_metrics() will return empty.")
        return 1
    bundle = get_filings_bundle(ticker)
    print(f"[{ticker}] {len(bundle['filings'])} filings")
    for f in bundle["filings"]:
        snippet = (f["sections"] or "")[:120].replace("\n", " ")
        print(f"  - {f['form']:6} {f['filed_at']}  {snippet!r}")
    print(f"\nMetrics: {bundle['metrics']}")
    return 0 if bundle["filings"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
