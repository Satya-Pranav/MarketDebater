"""Debate orchestrator — Phase 2.

Runs the multi-round debate (Phase 4 will swap the internals for the Microsoft
Agent Framework group chat; the public API stays the same) and hands the final
arguments to the Chair.

CLI:  python -m app.orchestrator RELIANCE.NS
"""
from __future__ import annotations

import sys
from typing import Any, Iterator

from . import config
from .agents import PERSONAS, run_persona
from .chair import judge
from .data_aggregator import aggregate

PERSONA_ORDER = ["bull", "bear", "neutral"]


def run_debate(ticker: str) -> dict[str, Any]:
    """Full pipeline: aggregate data -> debate rounds -> chair verdict."""
    return _collect(stream_debate(ticker))


def stream_debate(ticker: str) -> Iterator[dict[str, Any]]:
    """Yield debate events as they happen (for the Streamlit live transcript).

    Event types: 'data', 'argument', 'verdict'.
    """
    data = aggregate(ticker)
    snapshot, news = data["snapshot"], data["news"]
    yield {"type": "data", "snapshot": snapshot, "news": news}

    rounds = max(1, config.DEBATE_ROUNDS)
    latest: dict[str, dict] = {}

    for rnd in range(1, rounds + 1):
        opponents = (
            {p: {"stance": a.get("stance"), "points": a.get("points")} for p, a in latest.items()}
            if rnd > 1
            else None
        )
        for persona in PERSONA_ORDER:
            others = {p: v for p, v in (opponents or {}).items() if p != persona} or None
            arg = run_persona(persona, snapshot, news, opponents=others)
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
        elif ev["type"] == "argument":
            result["transcript"].append(ev)
        elif ev["type"] == "verdict":
            result["verdict"], result["arguments"] = ev["verdict"], ev["arguments"]
    return result


def _main() -> int:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE.NS"
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
    print(f"\n{v['disclaimer']}")
    print("=" * 60)

    assert v["verdict"] in ["Strong Buy", "Accumulate", "Hold", "Reduce"], "Invalid verdict"
    print("\n✅ Phase 2 gate passed: debate ran, verdict in enum, grounding computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
