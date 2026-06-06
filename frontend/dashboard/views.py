"""Dashboard views for the MarketDebater frontend."""

from __future__ import annotations

import logging
import re
import time

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from app import config, storage
from app.orchestrator import run_debate
from app.scan import scan_universe

from .forms import TickerForm

logger = logging.getLogger(__name__)


PERSONA_LABELS = {
    "bull": "PermaBull",
    "bear": "PermaBear",
    "neutral": "RiskManager",
}

# Suggested tickers for the landing page (US watchlist — matches .env DEFAULT_TICKERS).
SUGGESTED_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "NVDA",
    "AMZN",
]


def clean_rationale(text):
    """Remove [MOCK] prefix from rationale text."""
    if not text:
        return text
    # Remove [MOCK] prefix and any trailing spaces
    cleaned = re.sub(r'^\s*\[MOCK\]\s*', '', text)
    return cleaned


def home(request):
    form = TickerForm()
    backend_mode = "MOCK" if config.MOCK_MODE or config.llm_backend() == "none" else config.llm_backend().upper()

    return render(
        request,
        "dashboard/home.html",
        {
            "form": form,
            "submitted": False,
            "ticker": "",
            "result": None,
            "error": None,
            "backend_mode": backend_mode,
            "persona_labels": PERSONA_LABELS,
            "rejected_claims": [],
            "disclaimer": None,
            "suggested_tickers": SUGGESTED_TICKERS,
        },
    )


def run_debate_view(request):
    logger.info("=== run_debate_view called ===")
    logger.info(f"Request method: {request.method}")
    
    if request.method != "POST":
        logger.info("Not a POST request, redirecting to home")
        return home(request)

    form = TickerForm(request.POST)
    result = None
    error = None
    ticker = ""
    rejected_claims = []
    disclaimer = None

    backend_mode = "MOCK" if config.MOCK_MODE or config.llm_backend() == "none" else config.llm_backend().upper()

    logger.info(f"Form is_valid: {form.is_valid()}")
    logger.info(f"Form errors: {form.errors}")
    
    persisted_to_board = False
    arguments_by_persona: dict[str, list] = {p: [] for p in PERSONA_LABELS}
    if form.is_valid():
        ticker = form.cleaned_data["ticker"]
        rounds = form.cleaned_data.get("rounds") or config.DEBATE_ROUNDS
        logger.info(f"Processing ticker: {ticker} (rounds={rounds})")
        try:
            logger.info("Calling run_debate...")
            start = time.time()
            result = run_debate(ticker, rounds=rounds)
            elapsed = time.time() - start
            logger.info(f"run_debate completed in {elapsed:.2f}s")

            # Push the verdict to the daily-suggestions leaderboard. put_verdict
            # overwrites any prior entry for this ticker on today's date, then
            # write_merged_index reranks the leaderboard from per-ticker blobs.
            # Silently no-ops when storage isn't configured.
            if storage.is_configured() and result and result.get("verdict"):
                try:
                    date = storage.today_date()
                    payload = storage.to_persisted_payload(ticker, result)
                    if storage.put_verdict(date, ticker, payload):
                        storage.write_merged_index(date)
                        persisted_to_board = True
                        logger.info(f"Persisted {ticker} to leaderboard for {date}")
                except Exception as persist_exc:
                    # Persistence failure must not break the user's verdict view.
                    logger.exception(f"Failed to persist {ticker} to leaderboard: {persist_exc}")

            # Clean rationale to remove [MOCK] prefix
            if result and result.get("verdict") and result["verdict"].get("rationale"):
                result["verdict"]["rationale"] = clean_rationale(result["verdict"]["rationale"])
            
            grounding_scores = result.get("verdict", {}).get("grounding_scores", {})
            disclaimer = result.get("verdict", {}).get("disclaimer")
            rejected_claims = [
                {
                    "persona": persona,
                    "label": label,
                    "metrics": grounding_scores.get(persona, {}).get("unverified_metrics", []),
                }
                for persona, label in PERSONA_LABELS.items()
            ]

            # Group transcript turns by persona so the deep-dive tabs render
            # each persona's points across all rounds. Sorted by round ascending.
            for turn in result.get("transcript", []) or []:
                arg = turn.get("argument") or {}
                persona_key = arg.get("persona")
                if persona_key in arguments_by_persona:
                    arguments_by_persona[persona_key].append(arg)
            for persona_key in arguments_by_persona:
                arguments_by_persona[persona_key].sort(key=lambda a: a.get("round", 0))

            # Stash total round count on the result so round labels in the
            # template can decide between Case / Rebuttal / Closing suffixes.
            timings_meta = result.get("timings") or {}
            total_rounds = timings_meta.get("rounds") or max(
                (a.get("round", 0) for args in arguments_by_persona.values() for a in args),
                default=rounds or config.DEBATE_ROUNDS,
            )
            result["debate_rounds"] = total_rounds
            logger.info(f"Successfully processed debate result with {len(rejected_claims)} persona claims")
        except Exception as exc:  # keep the dashboard usable when data or models fail
            logger.exception(f"Exception in run_debate for {ticker}: {exc}")
            error = f"Debate failed for **{ticker}**: {exc}"
    elif form.errors:
        error = "Select a valid company ticker."

    logger.info(f"Rendering with error: {error}, result: {result is not None}")
    if result:
        logger.info(f"Result news count: {len(result.get('news', []))}")
        if result.get('news'):
            logger.info(f"First news item: {result['news'][0]}")
    
    return render(
        request,
        "dashboard/home.html",
        {
            "form": form,
            "submitted": True,
            "ticker": ticker,
            "result": result,
            "error": error,
            "backend_mode": backend_mode,
            "persona_labels": PERSONA_LABELS,
            "rejected_claims": rejected_claims,
            "disclaimer": disclaimer,
            "suggested_tickers": SUGGESTED_TICKERS,
            "persisted_to_board": persisted_to_board,
            "arguments_by_persona": arguments_by_persona,
        },
    )


def leaderboard_view(request):
    """Daily suggestions: ranked cross-stock leaderboard for the requested date.

    Reads ``verdicts/<date>/index.json`` (or ``verdicts/latest/index.json``)
    via ``app.storage``. ``?date=YYYY-MM-DD`` picks a specific scan; the default
    is ``latest``. Handles both Blob and ``LOCAL_RESULTS_DIR`` modes, and
    degrades gracefully when storage isn't configured or no scans have run.
    """
    requested_date = request.GET.get("date", "latest").strip() or "latest"
    available_dates = []
    payload = None
    storage_configured = storage.is_configured()
    storage_hint = None

    if storage_configured:
        try:
            available_dates = sorted(storage.list_dates(), reverse=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(f"list_dates failed: {exc}")
            available_dates = []
        try:
            payload = storage.get_index(requested_date)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(f"get_index({requested_date}) failed: {exc}")
            payload = None
    else:
        storage_hint = (
            "No storage configured. Set AZURE_STORAGE_CONNECTION_STRING (Blob) or "
            "LOCAL_RESULTS_DIR=./out (filesystem) in .env, then run "
            "`python -m app.scan` to populate verdicts."
        )

    ranked = (payload or {}).get("ranked", []) or []
    actual_date = (payload or {}).get("date", "") if payload else ""
    generated_at = (payload or {}).get("generated_at", "") if payload else ""

    return render(
        request,
        "dashboard/leaderboard.html",
        {
            "requested_date": requested_date,
            "actual_date": actual_date,
            "generated_at": generated_at,
            "ranked": ranked,
            "available_dates": available_dates,
            "storage_configured": storage_configured,
            "storage_hint": storage_hint,
            "persona_labels": PERSONA_LABELS,
            "default_scan_tickers": ",".join(SUGGESTED_TICKERS),
        },
    )


@require_POST
def run_scan_view(request):
    """Trigger an inline cross-stock scan and persist verdicts.

    Synchronous: blocks the request until the scan completes. To keep the demo
    snappy we default to 1 round and the 5-ticker suggested list — at ~10-20s
    per ticker on V4-Flash that's ~1-2min total. Wraps `app.scan.scan_universe`
    which handles per-ticker failures + index rebuild.
    """
    raw = (request.POST.get("tickers") or "").strip()
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()] or list(SUGGESTED_TICKERS)
    try:
        rounds = int(request.POST.get("rounds") or 1)
    except ValueError:
        rounds = 1
    rounds = max(1, min(5, rounds))

    if not storage.is_configured():
        messages.error(
            request,
            "Storage isn't configured. Set AZURE_STORAGE_CONNECTION_STRING or "
            "LOCAL_RESULTS_DIR=./out in .env before running a scan.",
        )
        return HttpResponseRedirect(reverse("leaderboard"))

    start = time.time()
    logger.info(f"Triggering inline scan: tickers={tickers} rounds={rounds}")
    try:
        payload = scan_universe(tickers=tickers, rounds=rounds)
        elapsed = time.time() - start
        ok = len(payload.get("ranked", []))
        messages.success(
            request,
            f"Scan complete in {elapsed:.1f}s — {ok} ticker(s) ranked at {rounds} round(s).",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(f"Scan failed: {exc}")
        messages.error(request, f"Scan failed: {exc}")
    return HttpResponseRedirect(reverse("leaderboard"))
