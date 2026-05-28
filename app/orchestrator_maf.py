"""Microsoft Agent Framework debate path — Phase 4.

Runs the persona debate using Microsoft Agent Framework `ChatAgent`s (one per
persona) backed by the same Azure AI Foundry OpenAI-compatible endpoint the rest
of the app uses. It yields the **same event stream** as the built-in orchestrator
(`data` / `argument` / `verdict`), so the UI and CLI are unchanged.

Selected via `USE_AGENT_FRAMEWORK=1`. Requires `agent-framework` (Python 3.10+):
    pip install -r requirements-maf.txt
The Chair's deterministic verifier + judge are reused as-is from `chair.py`.
"""
from __future__ import annotations

import asyncio
from typing import Any, Iterator

from . import config, search_client
from .agents import PERSONA_QUERY, PERSONAS, _build_user_prompt
from .chair import judge
from .data_aggregator import aggregate
from .llm import _parse_json

PERSONA_ORDER = ["bull", "bear", "neutral"]


def _build_client():
    """OpenAI-compatible MAF chat client pointed at the Foundry /openai/v1 route."""
    from agent_framework.openai import OpenAIChatClient

    base = config.AZURE_OPENAI_ENDPOINT.rstrip("/")
    if not base.endswith("/openai/v1"):
        base += "/openai/v1"
    return OpenAIChatClient(
        base_url=base + "/",
        api_key=config.AZURE_OPENAI_API_KEY,
        model=config.PERSONA_DEPLOYMENT,
    )


def _shape(arg: dict[str, Any], persona: str, rnd: int) -> dict[str, Any]:
    arg.setdefault("stance", "Hold")
    arg.setdefault("points", [])
    arg.setdefault("confidence", 0.5)
    arg["persona"] = persona
    arg["persona_name"] = PERSONAS[persona]["name"]
    arg["round"] = rnd
    return arg


async def _run_rounds(snapshot: dict, news: list) -> tuple[list[dict], dict[str, dict]]:
    """Run all persona turns inside one async context (MAF telemetry uses contextvars,
    so a single event loop avoids cross-context token errors)."""
    client = _build_client()
    agents = {
        p: client.as_agent(name=PERSONAS[p]["name"], instructions=PERSONAS[p]["system"])
        for p in PERSONA_ORDER
    }

    rounds = max(1, config.DEBATE_ROUNDS)
    latest: dict[str, dict] = {}
    events: list[dict] = []

    for rnd in range(1, rounds + 1):
        opponents = (
            {p: {"stance": a.get("stance"), "points": a.get("points")} for p, a in latest.items()}
            if rnd > 1
            else None
        )
        for persona in PERSONA_ORDER:
            others = {p: v for p, v in (opponents or {}).items() if p != persona} or None
            evidence = search_client.retrieve(PERSONA_QUERY[persona], snapshot.get("ticker", ""))
            user = _build_user_prompt(snapshot, news, others, evidence=evidence)
            resp = await agents[persona].run(user)
            text = getattr(resp, "text", None) or str(resp)
            arg = _shape(_parse_json(text), persona, rnd)
            latest[persona] = arg
            events.append({"type": "argument", "round": rnd, "persona": persona, "argument": arg})

    return events, latest


def stream_debate_maf(ticker: str) -> Iterator[dict[str, Any]]:
    """Debate via MAF agents; yields data/argument/verdict events (sync generator)."""
    data = aggregate(ticker)
    snapshot, news = data["snapshot"], data["news"]
    yield {"type": "data", "snapshot": snapshot, "news": news}

    search_client.index_news(ticker, news)  # no-op unless Azure AI Search is configured

    events, latest = asyncio.run(_run_rounds(snapshot, news))
    yield from events

    verdict = judge(latest, snapshot, news)
    yield {"type": "verdict", "verdict": verdict, "arguments": latest}
