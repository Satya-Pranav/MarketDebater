# MarketDebater Swarm - project instructions

These instructions apply to every chat and agent request in this workspace. Read them before scaffolding, writing, or editing code.

## What we are building

An agentic investment committee for Indian (NSE/BSE) stocks. For a requested stock, a small swarm of agents fetches grounded data, runs an internal debate between three rival persona agents, fact-checks every statistic deterministically, and a Chair issues a transparent verdict (Strong Buy / Accumulate / Hold / Reduce). It is built for a hackathon under an "Agent Swarms" theme, so the orchestration and the validator are the things that must shine.

Educational only - not investment advice. This rule is non-negotiable. The system produces a transparent, grounded debate, never a financial recommendation or prediction. Every user-facing output must carry a clear disclaimer to consult a SEBI-registered advisor. Do not write code, comments, or UI copy that frames the output as personalized advice or a guaranteed forecast.

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
3. Prices/technicals (OHLCV, RSI, MACD)
4. Corporate filings (NSE/BSE official disclosures) - this is the trusted source
5. News/sentiment (secondary only)
6. Sector peers + insider/promoter disclosures
7. Shared snapshot - all retriever output converges into ONE immutable snapshot object. This is the single source of truth. Every downstream agent argues only from this snapshot. The snapshot is also what the verifier checks claims against.
8. Debaters (executors, run off the same snapshot) - three fixed personas:
9. PermaBull - builds the strongest case to buy (growth, breakouts, upside).
10. PermaBear - builds the strongest case to sell/avoid (risk, overvaluation, negative anomalies).
11. RiskManager - the neutral hold/wait case (baselines, moving averages, consolidation).
12. The personas differ ONLY by their system prompt. Same model is fine for all three to start. Do not train separate models; do not give them different data.
13. Deterministic verifier - see above. Fact-checks every debater claim against the snapshot.
14. Chair of the board (LLM-as-judge) - weighs the verified arguments and outputs the verdict with per-agent weights and a transparent rationale. Run the Chair on a DIFFERENT model than the debaters so it does not share their blind spots.
15. Verdict - Strong Buy / Accumulate / Hold / Reduce, plus the debate transcript and the list of rejected claims.

## Data source hierarchy (enforce this strictly)

- Ground truth for prices/technicals: NSE bhavcopy (official EOD) or a broker data API. yfinance is acceptable for an early demo (use the .NS suffix for NSE tickers) but treat it as unreliable; isolate it behind a data-source interface so it can be swapped.
- Ground truth for news/fundamentals: official NSE/BSE corporate filings (Regulation 30 material events, results).
- Secondary only: news/RSS (moneycontrol, ET, etc.) - usable for sentiment, NEVER as the source the verifier checks against.
- A verifier that validates a claim against a news headline instead of a filing is a bug. Verify only against the structured snapshot.

## Tech stack

- Language: Python 3.11+.
- Orchestration: Microsoft Agent Framework 1.0 (agent-framework, the unified successor to AutoGen + Semantic Kernel). Use its concurrent pattern for the retriever sub-swarm and group-chat/Magentic patterns for the debate + Chair. This SDK is new (released 2026) - when unsure of an exact API, import path, or class name, consult the official docs/repo rather than guessing or inventing method names.
- Models: Azure AI Foundry (e.g. a GPT-4o-class model for debaters, a different model for the Chair). Read model deployment names and endpoints from environment variables.
- RAG: Azure AI Search for filings/news retrieval.
- API/backend: FastAPI (async, supports streaming the live debate transcript via SSE). Prefer this over a synchronous framework because the debate streams token-by-token.
- Containerization: each tier should be runnable as a service; provide a docker-compose.yml. The theme rewards visibly containerized, scalable architecture.
- Frontend: a simple web dashboard that streams the debate and shows the verdict card plus rejected-claim badges. A custom web page streams the live transcript better than Power Apps; if Power Apps/Copilot Studio is required for judging, keep the streaming logic in the backend.

## Coding conventions

- Type hints everywhere; use Pydantic models for the snapshot, claims, agent outputs, and verdict - they double as clean API contracts.
- The snapshot is immutable once built (frozen dataclass / frozen Pydantic model).
- No secrets in code. All keys, endpoints, and deployment names via environment variables / .env (git-ignored). Provide a .env.example.
- Every numeric claim from an agent must be a structured object (value + what it refers to + source field), not free text - so the verifier can check it mechanically.
- Write unit tests for the verifier first and keep coverage high there. Other modules get tests as practical.
- Log every agent output, every verifier decision (pass/reject + reason), and the final verdict. The transparency/audit trail is part of the product.
- Keep data sources behind an interface so yfinance can be swapped for bhavcopy/broker APIs without touching agent code.

## Suggested project structure

```text
marketdebater/
  data/            # retrievers + data-source adapters (yfinance, bhavcopy, filings, news)
  snapshot/        # snapshot model (immutable ground truth)
  agents/          # planner, bull, bear, risk_manager, chair + their prompts
  verifier/        # deterministic claim checker (pure python) + tests
  orchestration/   # Agent Framework wiring of the swarm
  api/             # FastAPI app, SSE streaming of the debate
  web/             # dashboard
  tests/
  docker-compose.yml
  .env.example
```

## Suggested build order

1. Snapshot model + one data source (yfinance EOD) -> produce a real snapshot for a ticker.
2. Deterministic verifier + its unit tests, against the snapshot. Prove the core idea before any agents.
3. The three debater agents (prompt-only personas) producing structured claims off the snapshot.
4. Wire verifier between debaters and a basic Chair; output a verdict.
5. Orchestrate with Microsoft Agent Framework; add the planner and parallel retrievers.
6. FastAPI + streaming dashboard; containerize.
7. Upgrade data sources (bhavcopy/filings) and add Azure AI Search RAG.

## Guardrails recap

- Educational only; never personalized advice or a guaranteed prediction; always show the disclaimer.
- The verifier is deterministic Python, never an LLM.
- All agents argue from the same immutable snapshot.
- Verify claims only against structured ground truth (filings/snapshot), never news.
- Confidence from an agent is checked, not trusted.