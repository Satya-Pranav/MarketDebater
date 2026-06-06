"""Dashboard views for the MarketDebater frontend."""

from __future__ import annotations

import logging
import re
import time

from django.shortcuts import render

from app import config
from app.orchestrator import run_debate

from .forms import TickerForm

logger = logging.getLogger(__name__)


PERSONA_LABELS = {
    "bull": "PermaBull",
    "bear": "PermaBear",
    "neutral": "RiskManager",
}

# Suggested tickers for the landing page
SUGGESTED_TICKERS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
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
    
    if form.is_valid():
        ticker = form.cleaned_data["ticker"]
        logger.info(f"Processing ticker: {ticker}")
        try:
            logger.info("Calling run_debate...")
            start = time.time()
            result = run_debate(ticker)
            elapsed = time.time() - start
            logger.info(f"run_debate completed in {elapsed:.2f}s")
            
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
        },
    )
