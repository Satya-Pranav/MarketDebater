"""Persona debate agents.

Three hyper-specialized analysts argue the same stock from fixed viewpoints.
Each returns STRUCTURED JSON so the Chair can grade and weight numerically:
    {stance, points:[{claim, cited_metric, source}], confidence:0..1}

Personas route to ``PERSONA_R1_DEPLOYMENT`` (DeepSeek-R1, reasoning) when set;
otherwise ``PERSONA_DEPLOYMENT`` (defaults to DeepSeek-V4-Flash). Chair always
uses CHAT_DEPLOYMENT — never collapse them.
"""
from __future__ import annotations

import json
from typing import Any

from . import config, search_client
from .llm import chat_json

_JSON_SHAPE = (
    'Return JSON: {"stance": "<Buy|Sell|Hold|...>", '
    '"points": [{"claim": "...", "cited_metric": "<name=value pairs only, from snapshot>", '
    '"source": "<news url, filing form/url, or \'technicals\'/\'fundamentals\'>"}], '
    '"confidence": 0.0-1.0}. '
    "STRICT RULES for cited_metric:\n"
    "  - It must contain ONE OR MORE name=value pairs, comma-separated, drawn from real "
    "snapshot keys (e.g. rsi_14=73.72, sma_50=277.61, week52_high=315.2, revenue=80208000000, "
    "eps_diluted=2.01, gross_margin=0.683, debt_to_equity=2.48). DO NOT invent numbers.\n"
    "  - For purely qualitative claims (news / filings) leave cited_metric as an empty string "
    "and put the URL or filing reference in the 'source' field instead.\n"
    "  - NEVER put URLs, free text, or anything other than name=value pairs in cited_metric — "
    "URL query strings will be misparsed as bogus metrics and your point will be flagged as "
    "hallucinated."
)

PERSONAS: dict[str, dict[str, str]] = {
    "bull": {
        "name": "The Perma-Bull",
        "system": (
            "You are THE PERMA-BULL, an aggressive growth-focused equity analyst. Your job is to "
            "build the STRONGEST possible case to BUY this US-listed stock. Hunt for growth drivers, "
            "technical breakouts, hidden value, oversold conditions, positive catalysts in the news, "
            "and bullish signals in the latest 10-K/10-Q/8-K filings. Be persuasive but you MUST "
            "ground every numeric point in the real values provided. " + _JSON_SHAPE
        ),
    },
    "bear": {
        "name": "The Perma-Bear",
        "system": (
            "You are THE PERMA-BEAR, an aggressive short-seller. Your job is to build the STRONGEST "
            "possible case to SELL/SHORT this US-listed stock. Hunt for overvaluation, overhead "
            "resistance, weakening momentum, systemic risks, deteriorating fundamentals (margin "
            "compression, leverage), risk-factor disclosures in 10-K/10-Q filings, and negative "
            "news. Be ruthless but you MUST ground every numeric point in the real values "
            "provided. " + _JSON_SHAPE
        ),
    },
    "neutral": {
        "name": "The Risk Manager",
        "system": (
            "You are THE RISK MANAGER, a disciplined, statistics-first analyst. You favor HOLD/WAIT "
            "unless data is decisive. Focus on moving averages, historical baselines, volatility, "
            "consolidation patterns, and balance-sheet stability from the latest filings. Avoid "
            "hype in either direction. " + _JSON_SHAPE
        ),
    },
}


# Persona-specific retrieval queries — each agent pulls evidence that helps its case.
PERSONA_QUERY: dict[str, str] = {
    "bull": "growth expansion profit earnings beat order win deal positive catalyst upgrade",
    "bear": "risk decline loss probe downgrade weak demand selloff debt litigation fall",
    "neutral": "outlook guidance results analyst rating volatility valuation",
}


def _build_user_prompt(
    snapshot: dict[str, Any],
    news: list[dict[str, str]],
    filings: list[dict[str, Any]] | None,
    opponents: dict[str, dict] | None,
    evidence: list[dict[str, Any]] | None = None,
    round_num: int = 1,
    final_round: bool = False,
) -> str:
    parts = [
        "MARKET SNAPSHOT (ground truth — cite these exact values):",
        json.dumps(snapshot, indent=2, default=str),
        "\nRECENT NEWS HEADLINES:",
        "\n".join(f"- {n['title']} [{n.get('source','')}] {n.get('url','')}" for n in news[:6]) or "(none)",
    ]
    if filings:
        parts.append("\nRECENT SEC FILINGS (10-K / 10-Q / 8-K — quote the snippets):")
        parts.append(
            "\n".join(
                f"- {f.get('form','')} filed {f.get('filed_at','')[:10]} "
                f"{(f.get('sections') or '')[:300]!r} {f.get('url','')}"
                for f in filings[:4]
            )
        )
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
        if final_round:
            parts.append(
                "\nCLOSING ROUND. Pick the SINGLE strongest opponent point and either CONCEDE it "
                "(explicitly) or REFUTE it with a snapshot-grounded counter. Then restate your "
                "1-line conviction. Do not simply repeat earlier points."
            )
        else:
            parts.append("\nFile your REBUTTAL: strengthen your case and attack their reasoning.")
    parts.append(f"\nROUND {round_num}.")
    return "\n".join(parts)


def _persona_deployment() -> tuple[str | None, bool]:
    """Return (deployment, is_reasoning_model) for persona calls.

    Reasoning route only kicks in when both PERSONA_R1_DEPLOYMENT is set AND we
    are on the Azure backend (R1 is served via Foundry).
    """
    if config.llm_backend() != "azure":
        return None, False
    if config.PERSONA_R1_DEPLOYMENT:
        return config.PERSONA_R1_DEPLOYMENT, True
    return config.PERSONA_DEPLOYMENT, False


def run_persona(
    persona: str,
    snapshot: dict[str, Any],
    news: list[dict[str, str]],
    opponents: dict[str, dict] | None = None,
    filings: list[dict[str, Any]] | None = None,
    round_num: int = 1,
    final_round: bool = False,
) -> dict[str, Any]:
    """Run one persona agent for one debate turn; returns its structured argument."""
    spec = PERSONAS[persona]
    evidence = search_client.retrieve(PERSONA_QUERY[persona], snapshot.get("ticker", ""))
    user = _build_user_prompt(
        snapshot,
        news,
        filings=filings,
        opponents=opponents,
        evidence=evidence,
        round_num=round_num,
        final_round=final_round,
    )
    deployment, is_reasoning = _persona_deployment()
    arg = chat_json(
        spec["system"],
        user,
        deployment=deployment,
        temperature=0.5,
        context={"snapshot": snapshot},
        is_reasoning_model=is_reasoning,
    )
    arg.setdefault("stance", "Hold")
    arg.setdefault("points", [])
    arg.setdefault("confidence", 0.5)
    arg["persona"] = persona
    arg["persona_name"] = spec["name"]
    return arg
