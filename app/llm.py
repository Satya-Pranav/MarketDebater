"""LLM backend wrapper — Phase 2.

One entry point, ``chat_json``, that returns parsed JSON from the model. It
auto-selects the backend from config:
  - 'azure'  -> Azure OpenAI (the strictly-Microsoft path)
  - 'openai' -> standard OpenAI (local-dev fallback)
  - mock     -> deterministic, offline, stance-aware stub (MOCK_MODE or no keys)

The mock lets the entire debate pipeline run and be tested with zero credentials,
then lights up for real the moment Azure/OpenAI keys land in .env.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import config


def chat_json(
    system: str,
    user: str,
    *,
    deployment: str | None = None,
    temperature: float = 0.4,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a chat completion constrained to a JSON object and parse it.

    ``context`` (e.g. the market snapshot) is only used by the mock backend to
    produce grounded citations; real backends ignore it.
    """
    backend = config.llm_backend()
    if config.MOCK_MODE or backend == "none":
        return _mock_json(system, context or {})

    from openai import OpenAI

    messages = [
        {"role": "system", "content": system + "\nRespond with a single valid JSON object — no markdown, no commentary."},
        {"role": "user", "content": user},
    ]

    if backend == "azure":
        # Azure AI Foundry exposes an OpenAI-compatible route at /openai/v1 that
        # serves the whole catalog (GPT, DeepSeek, Llama, ...) via the standard
        # OpenAI SDK. `model` is the DEPLOYMENT name, not the base model id.
        base = config.AZURE_OPENAI_ENDPOINT.rstrip("/")
        if not base.endswith("/openai/v1"):
            base += "/openai/v1"
        client = OpenAI(base_url=base + "/", api_key=config.AZURE_OPENAI_API_KEY)
        model = deployment or config.CHAT_DEPLOYMENT
    else:  # standard OpenAI (local-dev fallback)
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        model = deployment or "gpt-4o"

    base_kwargs: dict[str, Any] = {"model": model, "messages": messages}
    try:
        resp = client.chat.completions.create(
            **base_kwargs,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except Exception:
        # Some Foundry catalog models reject response_format / custom temperature;
        # fall back to a bare call and lean on the prompt + robust parsing.
        resp = client.chat.completions.create(**base_kwargs)
    return _parse_json(resp.choices[0].message.content or "{}")


def _parse_json(content: str) -> dict[str, Any]:
    """Parse model output into a dict, tolerating <think> blocks and code fences."""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


# --------------------------------------------------------------------------- #
# Deterministic mock backend                                                  #
# --------------------------------------------------------------------------- #
def _stance_from_system(system: str) -> str:
    s = system.upper()
    # CHAIR first: the Chair's prompt names the personas ("bull, bear, ...") and
    # would otherwise be misclassified as one of them.
    for marker in ("CHAIR", "PERMA-BULL", "BULL", "PERMA-BEAR", "BEAR", "RISK MANAGER", "NEUTRAL"):
        if marker in s:
            return {
                "PERMA-BULL": "bull",
                "BULL": "bull",
                "PERMA-BEAR": "bear",
                "BEAR": "bear",
                "RISK MANAGER": "neutral",
                "NEUTRAL": "neutral",
                "CHAIR": "chair",
            }[marker]
    return "neutral"


def _mock_json(system: str, ctx: dict[str, Any]) -> dict[str, Any]:
    role = _stance_from_system(system)
    snap = ctx.get("snapshot", ctx) if isinstance(ctx, dict) else {}
    price = snap.get("price", 0)
    rsi = snap.get("rsi_14", 50)
    sma50 = snap.get("sma_50", price)
    sma200 = snap.get("sma_200", price)
    hi = snap.get("week52_high", price)

    if role == "chair":
        # weight = grounding-ish * confidence; provided by orchestrator in real path.
        return {
            "verdict": "Hold",
            "rationale": (
                "[MOCK] Balanced signals: momentum is neutral and the stock trades "
                "between its 50- and 200-day averages. Awaiting a clearer catalyst."
            ),
            "per_agent": {
                "bull": {"weight": 0.33},
                "bear": {"weight": 0.33},
                "neutral": {"weight": 0.34},
            },
        }

    if role == "bull":
        return {
            "stance": "Buy",
            "points": [
                {"claim": f"Trading at {price}, below its 52-week high of {hi} — room to run.",
                 "cited_metric": f"week52_high={hi}", "source": "technicals"},
                {"claim": f"RSI at {rsi} is not overbought, leaving upside.",
                 "cited_metric": f"rsi_14={rsi}", "source": "technicals"},
            ],
            "confidence": 0.7,
        }
    if role == "bear":
        return {
            "stance": "Sell",
            "points": [
                {"claim": f"Price {price} sits below the 200-day SMA of {sma200} — bearish trend.",
                 "cited_metric": f"sma_200={sma200}", "source": "technicals"},
                {"claim": f"RSI {rsi} shows no buying momentum.",
                 "cited_metric": f"rsi_14={rsi}", "source": "technicals"},
            ],
            "confidence": 0.65,
        }
    # neutral
    return {
        "stance": "Hold",
        "points": [
            {"claim": f"Price {price} is wedged between SMA50 {sma50} and SMA200 {sma200} — consolidation.",
             "cited_metric": f"sma_50={sma50}", "source": "technicals"},
        ],
        "confidence": 0.6,
    }


def extract_numbers(text: str) -> list[float]:
    """Pull numeric tokens from a string (used by the grounding verifier)."""
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", text or "")]
