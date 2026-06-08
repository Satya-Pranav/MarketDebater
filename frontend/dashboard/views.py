"""Dashboard views for the MarketDebater frontend."""

from __future__ import annotations

import json
import logging
import re
import threading
import time

from django.contrib import messages
from django.http import (
    HttpResponseRedirect,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from app import config, storage
from app.orchestrator import run_debate, stream_debate
from app.scan import scan_universe

from .companies import ticker_options
from .forms import MAX_SCAN_TICKERS, TICKER_REGEX, TickerForm
from .jobs import DebateJob, create_job, get_job

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
    cleaned = re.sub(r'^\s*\[MOCK\]\s*', '', text)
    return cleaned


def _backend_mode() -> str:
    return "MOCK" if config.MOCK_MODE or config.llm_backend() == "none" else config.llm_backend().upper()


def _base_context() -> dict:
    """Context every page needs (nav + suggested tickers + ticker dropdown)."""
    return {
        "backend_mode": _backend_mode(),
        "persona_labels": PERSONA_LABELS,
        "suggested_tickers": SUGGESTED_TICKERS,
        "ticker_options": ticker_options(),
    }


def home(request):
    form = TickerForm()
    ctx = _base_context()
    ctx.update({
        "form": form,
        "submitted": False,
        "ticker": "",
        "result": None,
        "error": None,
        "rejected_claims": [],
        "disclaimer": None,
    })
    return render(request, "dashboard/home.html", ctx)


def _build_result_context(ticker: str, result: dict, persisted_to_board: bool, error: str | None) -> dict:
    """Assemble the template context for the rich-result page from a debate result.

    Extracted so both the legacy synchronous view and the new async result view
    feed the same template with the same shape.
    """
    rejected_claims = []
    disclaimer = None
    arguments_by_persona: dict[str, list] = {p: [] for p in PERSONA_LABELS}
    if result:
        if result.get("verdict") and result["verdict"].get("rationale"):
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
        for turn in result.get("transcript", []) or []:
            arg = turn.get("argument") or {}
            persona_key = arg.get("persona")
            if persona_key in arguments_by_persona:
                arguments_by_persona[persona_key].append(arg)
        for persona_key in arguments_by_persona:
            arguments_by_persona[persona_key].sort(key=lambda a: a.get("round", 0))
        timings_meta = result.get("timings") or {}
        total_rounds = timings_meta.get("rounds") or max(
            (a.get("round", 0) for args in arguments_by_persona.values() for a in args),
            default=config.DEBATE_ROUNDS,
        )
        result["debate_rounds"] = total_rounds

    ctx = _base_context()
    ctx.update({
        "form": TickerForm(),
        "submitted": True,
        "ticker": ticker,
        "result": result,
        "error": error,
        "rejected_claims": rejected_claims,
        "disclaimer": disclaimer,
        "persisted_to_board": persisted_to_board,
        "arguments_by_persona": arguments_by_persona,
    })
    return ctx


# --------------------------------------------------------------------------
# Async / streaming debate flow (the live path the UI uses now).
# --------------------------------------------------------------------------


def _run_job(job: DebateJob) -> None:
    """Background thread body: drive stream_debate, push events, persist result.

    Runs in a daemon=False thread so it survives the original request handler
    returning. Catches any exception so the job ends in a known state — the SSE
    endpoint relies on `job.done=True` to terminate the stream cleanly.
    """
    result: dict = {"transcript": []}
    try:
        for ev in stream_debate(job.ticker, rounds=job.rounds):
            job.push(ev)
            t = ev.get("type")
            if t == "data":
                result["snapshot"] = ev["snapshot"]
                result["news"] = ev["news"]
                result["filings"] = ev.get("filings", [])
                result["filings_metrics"] = ev.get("filings_metrics", {})
            elif t == "argument":
                result["transcript"].append(ev)
            elif t == "timings":
                result["timings"] = ev["timings"]
            elif t == "verdict":
                result["verdict"] = ev["verdict"]
                result["arguments"] = ev["arguments"]

        # Persist to leaderboard. Mirrors the legacy sync view — keep this in the
        # thread so the live page's leaderboard pill reflects the same write.
        try:
            if storage.is_configured() and result.get("verdict"):
                date = storage.today_date()
                payload = storage.to_persisted_payload(job.ticker, result)
                if storage.put_verdict(date, job.ticker, payload):
                    storage.write_merged_index(date)
                    job.persisted = True
                    logger.info(f"Persisted {job.ticker} to leaderboard for {date}")
        except Exception as persist_exc:
            logger.exception(f"Failed to persist {job.ticker}: {persist_exc}")
        job.finish(result=result)
    except Exception as exc:
        logger.exception(f"Debate job {job.id} crashed: {exc}")
        # Push a synthetic error event so SSE consumers can surface it.
        job.push({"type": "error", "message": str(exc)})
        job.finish(error=str(exc))


@require_POST
def debate_start_view(request):
    """POST handler: validate, create job, spawn worker thread, redirect to live page."""
    form = TickerForm(request.POST)
    if not form.is_valid():
        # Re-render the landing form with the validation error inline.
        ctx = _base_context()
        ctx.update({
            "form": form,
            "submitted": False,
            "ticker": "",
            "result": None,
            "error": "Select a valid company ticker.",
            "rejected_claims": [],
            "disclaimer": None,
        })
        return render(request, "dashboard/home.html", ctx)

    ticker = form.cleaned_data["ticker"]
    rounds = form.cleaned_data.get("rounds") or config.DEBATE_ROUNDS

    job = create_job(ticker, rounds)
    thread = threading.Thread(target=_run_job, args=(job,), name=f"debate-{job.id[:8]}")
    thread.start()
    logger.info(f"Started debate job {job.id} for {ticker} rounds={rounds}")

    return HttpResponseRedirect(reverse("debate-live", args=[job.id]))


@require_GET
def debate_live_view(request, job_id: str):
    """Render the streaming UI shell — the page that opens an EventSource."""
    job = get_job(job_id)
    if not job:
        messages.error(request, "Debate session expired. Please start a new one.")
        return HttpResponseRedirect(reverse("home"))

    ctx = _base_context()
    ctx.update({
        "form": TickerForm(),
        "job_id": job_id,
        "ticker": job.ticker,
        "rounds": job.rounds,
    })
    return render(request, "dashboard/debate_live.html", ctx)


@require_GET
def debate_stream_view(request, job_id: str):
    """SSE endpoint streaming events for a debate job.

    Yields events as they're pushed by the worker thread. Sends a keepalive
    comment every ~10s so intermediate proxies (Railway edge, carrier NAT)
    don't kill the connection during quiet periods like long LLM calls.
    """
    job = get_job(job_id)
    if not job:
        return JsonResponse({"error": "job not found"}, status=404)

    def event_stream():
        # Initial nudge so the browser knows the connection is live.
        yield ": connected\n\n"
        last_index = 0
        last_keepalive = time.time()
        while True:
            event_count = job.wait_for_event(last_index, timeout=10.0)
            while last_index < event_count:
                ev = job.events[last_index]
                last_index += 1
                yield f"data: {json.dumps(ev)}\n\n"
            if job.done and last_index >= len(job.events):
                # Tell the browser exactly where to land — main UI hides the
                # spinner and redirects to the rich result page.
                payload = {"job_id": job.id, "error": job.error}
                yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
                return
            now = time.time()
            if now - last_keepalive >= 15:
                yield ": keepalive\n\n"
                last_keepalive = now

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    # Hint to nginx-style proxies to not buffer the stream. Railway uses a
    # different proxy but the header is a harmless no-op there.
    resp["X-Accel-Buffering"] = "no"
    return resp


@require_GET
def debate_result_view(request, job_id: str):
    """Render the final rich verdict UI using the stored result for the job."""
    job = get_job(job_id)
    if not job:
        messages.error(request, "Debate session expired. Please start a new one.")
        return HttpResponseRedirect(reverse("home"))
    if not job.done:
        # Bounce back to the live page if the user hits this URL too early.
        return HttpResponseRedirect(reverse("debate-live", args=[job_id]))

    if job.error or not job.result:
        ctx = _base_context()
        ctx.update({
            "form": TickerForm(),
            "submitted": True,
            "ticker": job.ticker,
            "result": None,
            "error": job.error or "Debate failed without a result.",
            "rejected_claims": [],
            "disclaimer": None,
            "persisted_to_board": False,
            "arguments_by_persona": {p: [] for p in PERSONA_LABELS},
        })
        return render(request, "dashboard/home.html", ctx)

    ctx = _build_result_context(job.ticker, job.result, job.persisted, None)
    return render(request, "dashboard/home.html", ctx)


# --------------------------------------------------------------------------
# Legacy synchronous view (kept for direct CLI / scripted callers, but the UI
# no longer routes here — it goes through the async/SSE path above).
# --------------------------------------------------------------------------


def run_debate_view(request):
    logger.info("=== run_debate_view (sync, legacy) called ===")
    if request.method != "POST":
        return home(request)

    form = TickerForm(request.POST)
    result = None
    error = None
    ticker = ""
    persisted_to_board = False
    if form.is_valid():
        ticker = form.cleaned_data["ticker"]
        rounds = form.cleaned_data.get("rounds") or config.DEBATE_ROUNDS
        try:
            start = time.time()
            result = run_debate(ticker, rounds=rounds)
            logger.info(f"run_debate completed in {time.time() - start:.2f}s")
            if storage.is_configured() and result and result.get("verdict"):
                try:
                    date = storage.today_date()
                    payload = storage.to_persisted_payload(ticker, result)
                    if storage.put_verdict(date, ticker, payload):
                        storage.write_merged_index(date)
                        persisted_to_board = True
                except Exception as persist_exc:
                    logger.exception(f"Failed to persist {ticker}: {persist_exc}")
        except Exception as exc:
            logger.exception(f"Exception in run_debate for {ticker}: {exc}")
            error = f"Debate failed for **{ticker}**: {exc}"
    elif form.errors:
        error = "Select a valid company ticker."

    ctx = _build_result_context(ticker, result, persisted_to_board, error)
    return render(request, "dashboard/home.html", ctx)


def leaderboard_view(request):
    """Daily suggestions: ranked cross-stock leaderboard for the requested date."""
    requested_date = request.GET.get("date", "latest").strip() or "latest"
    available_dates = []
    payload = None
    storage_configured = storage.is_configured()
    storage_hint = None

    if storage_configured:
        try:
            available_dates = sorted(storage.list_dates(), reverse=True)
        except Exception as exc:
            logger.exception(f"list_dates failed: {exc}")
            available_dates = []
        try:
            payload = storage.get_index(requested_date)
        except Exception as exc:
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
    """Trigger an inline cross-stock scan and persist verdicts."""
    raw = (request.POST.get("tickers") or "").strip()
    submitted = [t.strip().upper() for t in raw.split(",") if t.strip()]
    tickers = submitted or list(SUGGESTED_TICKERS)

    invalid = [t for t in tickers if not TICKER_REGEX.fullmatch(t)]
    if invalid:
        messages.error(
            request,
            "Invalid ticker(s): " + ", ".join(invalid[:5])
            + (" ..." if len(invalid) > 5 else "")
            + ". Use US symbols like AAPL or MSFT.",
        )
        return HttpResponseRedirect(reverse("leaderboard"))
    if len(tickers) > MAX_SCAN_TICKERS:
        messages.error(
            request,
            f"Too many tickers ({len(tickers)}); the in-browser scan is capped at "
            f"{MAX_SCAN_TICKERS}. Run `python -m app.scan` from the CLI for larger universes.",
        )
        return HttpResponseRedirect(reverse("leaderboard"))

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
    except Exception as exc:
        logger.exception(f"Scan failed: {exc}")
        messages.error(request, f"Scan failed: {exc}")
    return HttpResponseRedirect(reverse("leaderboard"))
