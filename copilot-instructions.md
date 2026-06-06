# MarketDebater Swarm - project instructions

These instructions apply to every chat and agent request in this workspace. Read them before scaffolding, writing, or editing code.

## What we are building

An agentic investment committee for **US-listed stocks** (NYSE / Nasdaq). For a requested stock, a small swarm of agents fetches grounded data, runs an internal debate between three rival persona agents, fact-checks every statistic deterministically, and a Chair issues a transparent verdict (Strong Buy / Accumulate / Hold / Reduce). It is built for a hackathon under an "Agent Swarms" theme, so the orchestration and the validator are the things that must shine.

The product is also run as a cross-stock daily scan over a curated US watchlist (default ~25 tickers in `app/data/watchlist.txt`; the full ~4.6k-ticker Google Sheet is opt-in via `UNIVERSE_FROM_SHEET=1`). Verdicts are ranked by a continuous `net_bull_score` (`weights[bull] - weights[bear]`), so a single scan surfaces both the top buys and the top shorts.

Educational only - not investment advice. This rule is non-negotiable. The system produces a transparent, grounded debate, never a financial recommendation or prediction. Every user-facing output must carry a clear disclaimer to consult an **SEC/FINRA-registered** advisor. Do not write code, comments, or UI copy that frames the output as personalized advice or a guaranteed forecast.

## The one thing that makes this project different (do not water this down)

The differentiator is a deterministic verifier: plain Python code - NOT an LLM, NOT an LLM-as-judge - that takes every numeric claim an agent makes and re-checks it against the ground-truth snapshot, recomputing arithmetic where needed. If an agent says "P/E is 18" and the snapshot says 24, the claim is rejected and the agent is penalized.

Rules for the verifier:

- It must be a pure, testable function with no model calls and no randomness.
- It must have thorough unit tests. This is the most important module in the repo.
- It runs BEFORE the Chair judges anything. The Chair only ever weighs claims the verifier has already validated.
- Catching wrong arithmetic matters most - generic fact-checkers miss this. Recompute ratios/percentages against the source numbers; do not just string-match.

If you ever find yourself implementing grounding-checking as an LLM call, stop - that is the wrong design.

## Architecture (the swarm)

Top-to-bottom flow:

1. Planner - decides which retrievers to call for the requested stock.
2. Retriever sub-swarm (run in parallel) - specialized fetch agents:
3. Prices/technicals (`app/prices_client.py`, yfinance + pandas — OHLCV, RSI, MACD, SMAs, Bollinger).
4. **SEC filings** (`app/filings_client.py`, sec-api.io 10-K / 10-Q / 8-K + XBRL fundamentals like revenue, eps_diluted, gross_margin, debt_to_equity) - this is the trusted source.
5. News/sentiment (`app/news_client.py`, Google News RSS → Grok-via-Foundry editor) - secondary only.
6. Shared snapshot - all retriever output converges into ONE immutable snapshot object. This is the single source of truth. Every downstream agent argues only from this snapshot. The snapshot is also what the verifier checks claims against. **Filings-derived XBRL metrics are folded into the same flat snapshot dict** so the grounding verifier resolves them without special-casing.
7. Debaters (executors, run off the same snapshot) - three fixed personas:
   - PermaBull - builds the strongest case to buy (growth, breakouts, upside).
   - PermaBear - builds the strongest case to sell/avoid (risk, overvaluation, negative anomalies).
   - RiskManager - the neutral hold/wait case (baselines, moving averages, consolidation).
   The personas differ ONLY by their system prompt. Same model is fine for all three. Do not train separate models; do not give them different data.
8. **Three debate rounds** (case → rebuttal → closing). The round-3 prompt requires each persona to explicitly address the strongest opponent point from round 2.
9. Deterministic verifier - see above. Fact-checks every debater claim against the snapshot.
10. Chair of the board (LLM-as-judge) - weighs the verified arguments and outputs the verdict with per-agent weights and a transparent rationale. Run the Chair on a DIFFERENT model than the debaters so it does not share their blind spots.
11. Verdict - Strong Buy / Accumulate / Hold / Reduce, plus the debate transcript, the rejected claims, and a `net_bull_score`.

## Data source hierarchy (enforce this strictly)

- Ground truth for prices/technicals: `yfinance` EOD OHLCV for US tickers (plain symbols like `AAPL`, no exchange suffix). yfinance is acceptable for the demo but treated as unreliable; isolated behind `prices_client.py` so it can be swapped.
- Ground truth for fundamentals: **sec-api.io** for SEC filings (10-K / 10-Q / 8-K) — Query API + Section Extractor for Risk Factors text + XBRL-to-JSON for revenue / eps_diluted / gross_margin / debt_to_equity.
- Secondary only: news (Google News RSS, then routed through **Grok 4.1 Fast Reasoning** via Azure AI Foundry to select + summarize the most material items). Usable for sentiment, NEVER as the source the verifier checks against.
- A verifier that validates a claim against a news headline instead of a filing is a bug. Verify only against the structured snapshot.

## Tech stack

- Language: Python 3.9+ (3.10+ for the optional Microsoft Agent Framework path).
- Orchestration: built-in `app/orchestrator.py` is the canonical path; the **Microsoft Agent Framework** path lives in `app/orchestrator_maf.py` behind `USE_AGENT_FRAMEWORK=1`. Use concurrent fanout for the retriever sub-swarm.
- Models (via Azure AI Foundry's OpenAI-compatible `/openai/v1` route — one Azure key serves all deployments):
  - Personas: **DeepSeek-V4-Flash** by default (`AZURE_OPENAI_PERSONA_DEPLOYMENT`). Set `AZURE_OPENAI_PERSONA_R1_DEPLOYMENT=DeepSeek-R1-0528` to route personas through the R1 reasoning model — wired and works, but 2026-06-03 head-to-head testing showed V4-Flash produces equivalent grounded arguments at ~6× the speed and ~20× lower cost (the deterministic verifier is what makes verdicts trustworthy, not chain-of-thought depth).
  - Chair: **DeepSeek-V4-Flash** (`AZURE_OPENAI_CHAT_DEPLOYMENT`) — fast, cheap, supports `response_format=json_object`.
  - News editor: **grok-4-1-fast-reasoning** via the same Foundry endpoint (no separate xAI subscription). Disable by leaving `GROK_MODEL` blank.
- Persistence: **Azure Blob Storage** container `marketdebater-verdicts` keyed by `verdicts/<YYYY-MM-DD>/<TICKER>.json` + per-date `index.json`. `LOCAL_RESULTS_DIR` redirects writes to the filesystem for dev.
- Scheduling: GitHub Actions `workflow_dispatch` only (`.github/workflows/nightly-scan.yml`) — manual triggers, no cron, so LLM spend stays predictable.
- RAG: Azure AI Search (BM25 over both news AND filings — `index_news` + `index_filings`).
- Frontends:
  - **Streamlit** (`app/streamlit_app.py`) — the original surface; reads verdicts from Blob.
  - **Django** (`frontend/`, served from the repo-root `manage.py`) — the production-facing UI. Same data contract as Streamlit.
  - Both call `app.orchestrator.run_debate(ticker)` for single-ticker debates and read Blob for leaderboard views.

## Coding conventions

- Type hints everywhere; use dataclasses / Pydantic-style models for the snapshot, claims, agent outputs, and verdict - they double as clean API contracts.
- The snapshot is effectively immutable once built (the aggregator returns it; downstream code should not mutate it).
- No secrets in code. All keys, endpoints, and deployment names via environment variables / `.env` (git-ignored). `.env.example` is the source of truth for what env vars exist.
- Every numeric claim from an agent must be a structured `cited_metric=name=value` string referencing a real snapshot key - so the verifier can check it mechanically. URLs, free text, and qualitative claims go in the `source` field instead; never in `cited_metric`.
- Write unit tests for the verifier first and keep coverage high there. Other modules get tests as practical.
- Log every agent output, every verifier decision (pass/reject + reason), and the final verdict. The transparency/audit trail is part of the product.
- Keep data sources behind an interface so yfinance can be swapped without touching agent code.

## Repository structure (current)

```text
MarketDebater/
  app/                  # canonical swarm implementation
    data/watchlist.txt  # curated 25-ticker default US universe (one per line)
    universe.py         # read watchlist by default; Google Sheet opt-in
    prices_client.py    # yfinance + hand-rolled technicals
    news_client.py      # RSS bundle → Grok-via-Foundry editor
    filings_client.py   # sec-api.io 10-K/10-Q/8-K + XBRL fundamentals
    data_aggregator.py  # parallel fanout to the three clients
    llm.py              # OpenAI-compatible client; R1-aware JSON parsing
    agents.py           # Bull / Bear / Risk personas
    chair.py            # deterministic verifier + LLM-as-judge
    orchestrator.py     # 3-round debate flow + verdict emit
    orchestrator_maf.py # optional Microsoft Agent Framework path
    search_client.py    # Azure AI Search (BM25 over news + filings)
    storage.py          # local or Azure Blob persistence
    scan.py             # cross-ticker scan; sharded + merge-index
    streamlit_app.py    # Streamlit UI
  backend/marketdebater/ # thin re-export shim so `backend.marketdebater.X` resolves to `app.X`
  frontend/             # Django UI (dashboard app + templates + static + sqlite)
  manage.py             # repo-root Django entrypoint
  .github/workflows/
    nightly-scan.yml    # workflow_dispatch-only scan workflow
  .env.example          # configuration template (copy to .env)
  requirements.txt
  requirements-maf.txt  # optional MAF deps (separate install)
  README.md
```

## Guardrails recap

- Educational only; never personalized advice or a guaranteed prediction; always show the **SEC/FINRA-registered advisor** disclaimer.
- US universe (plain ticker symbols like `AAPL`, no `.NS` / `.BO` suffix in new code, no INR / ₹ in new copy).
- The verifier is deterministic Python, never an LLM.
- All agents argue from the same immutable snapshot (which includes filings-derived XBRL metrics).
- Verify claims only against structured ground truth (filings/snapshot), never news.
- Confidence from an agent is checked, not trusted.
- Frontend templates own currency rendering — read `result.snapshot.currency` ("USD") rather than hardcoding a symbol.
