"""Dashboard views for the MarketDebater frontend."""

from __future__ import annotations

import logging
import time

from django.shortcuts import render

from backend.marketdebater import config
from backend.marketdebater.orchestrator import run_debate

from .forms import TickerForm

logger = logging.getLogger(__name__)


PERSONA_LABELS = {
    "bull": "PermaBull",
    "bear": "PermaBear",
    "neutral": "RiskManager",
}


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
    
    if form.is_valid():
        ticker = form.cleaned_data["ticker"]
        logger.info(f"Processing ticker: {ticker}")
        try:
            logger.info("Calling run_debate...")
            start = time.time()
            result = run_debate(ticker)
            elapsed = time.time() - start
            logger.info(f"run_debate completed in {elapsed:.2f}s")
            
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
            logger.info(f"Successfully processed debate result with {len(rejected_claims)} persona claims")
        except Exception as exc:  # keep the dashboard usable when data or models fail
            logger.exception(f"Exception in run_debate for {ticker}: {exc}")
            error = f"Debate failed for {ticker}: {exc}"
    elif form.errors:
        error = "Select a valid company ticker."

    logger.info(f"Rendering with error: {error}, result: {result is not None}")
    
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
        },
    )
