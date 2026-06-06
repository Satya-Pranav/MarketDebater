"""Debate orchestrator.

Runs the multi-round debate (3 rounds by default: case -> rebuttal -> closing)
and hands the final arguments to the Chair. Streams events for the UI.

CLI:  python -m app.orchestrator AAPL
"""
from __future__ import annotations

import sys
from typing import Any, Iterator

from . import config, search_client
from .agents import PERSONAS, run_persona
from .chair import judge
from .data_aggregator import aggregate

PERSONA_ORDER = ["bull", "bear", "neutral"]


def run_debate(ticker: str, rounds: int | None = None) -> dict[str, Any]:
    """Full pipeline: aggregate data -> debate rounds -> chair verdict.

    ``rounds`` overrides ``config.DEBATE_ROUNDS`` for this call (lets the UI
    expose a debate-depth slider without mutating global config).
    """
    return _collect(stream_debate(ticker, rounds=rounds))


def _use_maf() -> bool:
    """True if the Microsoft Agent Framework path is enabled, installed, and usable."""
    if not config.USE_AGENT_FRAMEWORK or config.MOCK_MODE or config.llm_backend() == "none":
        return False
    import importlib.util

    return importlib.util.find_spec("agent_framework") is not None


def stream_debate(ticker: str, rounds: int | None = None) -> Iterator[dict[str, Any]]:
    """Yield debate events as they happen (for the Streamlit live transcript).

    Event types: 'data', 'argument', 'verdict'. Delegates to the Microsoft Agent
    Framework path when enabled; otherwise runs the built-in debate below.
    """
    if _use_maf():
        from .orchestrator_maf import stream_debate_maf

        yield from stream_debate_maf(ticker, rounds=rounds)
        return

    data = aggregate(ticker)
    snapshot, news = data["snapshot"], data["news"]
    filings = data.get("filings", [])
    yield {
        "type": "data",
        "snapshot": snapshot,
        "news": news,
        "filings": filings,
        "filings_metrics": data.get("filings_metrics", {}),
    }

    # Index both news AND filings for RAG retrieval. Both are no-ops when AI Search isn't configured.
    search_client.index_news(ticker, news)
    search_client.index_filings(ticker, filings)

    rounds = max(1, rounds if rounds is not None else config.DEBATE_ROUNDS)
    latest: dict[str, dict] = {}

    for rnd in range(1, rounds + 1):
        opponents = (
            {p: {"stance": a.get("stance"), "points": a.get("points")} for p, a in latest.items()}
            if rnd > 1
            else None
        )
        for persona in PERSONA_ORDER:
            others = {p: v for p, v in (opponents or {}).items() if p != persona} or None
            arg = run_persona(
                persona,
                snapshot,
                news,
                opponents=others,
                filings=filings,
                round_num=rnd,
                final_round=(rnd == rounds and rounds > 1),
            )
            arg["round"] = rnd
            latest[persona] = arg
            yield {"type": "argument", "round": rnd, "persona": persona, "argument": arg}

    verdict = judge(latest, snapshot, news)
    yield {"type": "verdict", "verdict": verdict, "arguments": latest}


def _collect(events: Iterator[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"transcript": []}
    for ev in events:
        if ev["type"] == "data":
            result["snapshot"], result["news"] = ev["snapshot"], ev["news"]
            result["filings"] = ev.get("filings", [])
            result["filings_metrics"] = ev.get("filings_metrics", {})
        elif ev["type"] == "argument":
            result["transcript"].append(ev)
        elif ev["type"] == "verdict":
            result["verdict"], result["arguments"] = ev["verdict"], ev["arguments"]
    return result


def _main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    backend = config.llm_backend()
    mode = "MOCK" if (config.MOCK_MODE or backend == "none") else backend.upper()
    print(f"\n[backend: {mode}]  Running debate for {ticker} ...\n")

    result = run_debate(ticker)
    for ev in result["transcript"]:
        a = ev["argument"]
        print(f"--- Round {ev['round']}: {a['persona_name']} → {a['stance']} (conf {a['confidence']}) ---")
        for pt in a["points"]:
            print(f"   • {pt['claim']}  [{pt.get('cited_metric','')}]")
        print()

    v = result["verdict"]
    print("=" * 60)
    print(f"VERDICT: {v['verdict']}")
    print(f"Rationale: {v.get('rationale','')}")
    print(f"Grounding: " + ", ".join(
        f"{p}={g['grounding']}" for p, g in v["grounding_scores"].items()))
    print(f"Weights:   {v['weights']}")
    print(f"Net bull score: {v.get('net_bull_score')}")
    print(f"\n{v['disclaimer']}")
    print("=" * 60)

    assert v["verdict"] in ["Strong Buy", "Accumulate", "Hold", "Reduce"], "Invalid verdict"
    print("\nOK: debate ran, verdict in enum, grounding computed, net_bull_score present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
