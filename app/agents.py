"""Persona debate agents — Phase 2.

Three hyper-specialized analysts argue the same stock from fixed viewpoints.
Each returns STRUCTURED JSON so the Chair can grade and weight numerically:
    {stance, points:[{claim, cited_metric, source}], confidence:0..1}
"""
from __future__ import annotations

import json
from typing import Any

from . import config, search_client
from .llm import chat_json

_JSON_SHAPE = (
    'Return JSON: {"stance": "<Buy|Sell|Hold|...>", '
    '"points": [{"claim": "...", "cited_metric": "<name=value from the snapshot>", '
    '"source": "technicals|news|fundamentals"}], "confidence": 0.0-1.0}. '
    "Every point MUST cite a real metric/value from the provided snapshot — do not invent numbers."
)

PERSONAS: dict[str, dict[str, str]] = {
    "bull": {
        "name": "The Perma-Bull",
        "system": (
            "You are THE PERMA-BULL, an aggressive growth-focused equity analyst. Your job is to "
            "build the STRONGEST possible case to BUY this stock. Hunt for growth drivers, technical "
            "breakouts, hidden value, oversold conditions, and positive catalysts in the news. "
            "Be persuasive but you MUST ground every point in the real numbers provided. " + _JSON_SHAPE
        ),
    },
    "bear": {
        "name": "The Perma-Bear",
        "system": (
            "You are THE PERMA-BEAR, an aggressive short-seller. Your job is to build the STRONGEST "
            "possible case to SELL/SHORT this stock. Hunt for overvaluation, overhead resistance, "
            "weakening momentum, systemic risks, and negative news. Be ruthless but you MUST ground "
            "every point in the real numbers provided. " + _JSON_SHAPE
        ),
    },
    "neutral": {
        "name": "The Risk Manager",
        "system": (
            "You are THE RISK MANAGER, a disciplined, statistics-first analyst. You favor HOLD/WAIT "
            "unless data is decisive. Focus on moving averages, historical baselines, volatility, "
            "and consolidation patterns. Avoid hype in either direction. " + _JSON_SHAPE
        ),
    },
}


# Persona-specific retrieval queries — each agent pulls the evidence that helps its case.
PERSONA_QUERY: dict[str, str] = {
    "bull": "growth expansion profit earnings beat order win deal positive catalyst upgrade",
    "bear": "risk decline loss probe downgrade weak demand selloff debt litigation fall",
    "neutral": "outlook guidance results analyst rating volatility valuation",
}


def _build_user_prompt(
    snapshot: dict[str, Any],
    news: list[dict[str, str]],
    opponents: dict[str, dict] | None,
    evidence: list[dict[str, Any]] | None = None,
) -> str:
    parts = [
        "MARKET SNAPSHOT (ground truth — cite these exact values):",
        json.dumps(snapshot, indent=2, default=str),
        "\nRECENT NEWS HEADLINES:",
        "\n".join(f"- {n['title']} [{n.get('source','')}]" for n in news[:6]) or "(none)",
    ]
    if evidence:
        parts.append("\nRETRIEVED EVIDENCE (Azure AI Search — supports your angle):")
        parts.append(
            "\n".join(
                f"- {e['title']}: {(e.get('content') or '')[:200]} [{e.get('source','')}]"
                for e in evidence
            )
        )
    if opponents:
        parts.append("\nOPPONENTS' ARGUMENTS (rebut their weakest claims):")
        parts.append(json.dumps(opponents, indent=2, default=str))
        parts.append("\nFile your REBUTTAL: strengthen your case and attack their reasoning.")
    return "\n".join(parts)


def run_persona(
    persona: str,
    snapshot: dict[str, Any],
    news: list[dict[str, str]],
    opponents: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Run one persona agent for one debate turn; returns its structured argument."""
    spec = PERSONAS[persona]
    evidence = search_client.retrieve(PERSONA_QUERY[persona], snapshot.get("ticker", ""))
    user = _build_user_prompt(snapshot, news, opponents, evidence=evidence)
    arg = chat_json(
        spec["system"],
        user,
        deployment=config.PERSONA_DEPLOYMENT if config.llm_backend() == "azure" else None,
        temperature=0.5,
        context={"snapshot": snapshot},
    )
    arg.setdefault("stance", "Hold")
    arg.setdefault("points", [])
    arg.setdefault("confidence", 0.5)
    arg["persona"] = persona
    arg["persona_name"] = spec["name"]
    return arg
