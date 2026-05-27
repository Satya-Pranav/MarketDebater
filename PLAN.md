# MarketDebater Swarm — Implementation Plan

## Context
Retail investors in India get a single, homogenized AI "answer" that hides the real tension
between upside and risk. We are building an **Agentic Investment Committee**: three rival
persona agents (Perma-Bull, Perma-Bear, Risk Manager) debate a stock, and a **Chair of the
Board** agent grades their arguments on *data grounding* and *confidence*, then issues a
transparent verdict (Strong Buy / Accumulate / Hold / Reduce).

The differentiator vs. a normal chatbot is **visible, graded disagreement** — the user watches
the debate and sees *why* the committee landed where it did, with hallucinated stats caught and
penalized.

**Locked decisions (from user):**
- **Stack:** Strictly Microsoft for the core — Microsoft Agent Framework (orchestration),
  Azure AI Foundry / Azure OpenAI **GPT-4o** (personas + judge), Azure AI Search (RAG).
  Azure access/credits available.
- **UI:** Streamlit (live debate transcript + verdict card).
- **Data:** Hackathon-reliable free path — `yfinance` for NSE EOD OHLCV (`.NS` tickers),
  technicals computed locally; news via RSS (Google News / Moneycontrol / ET). EOD fidelity is
  sufficient.
- **Scope:** Hackathon (days) — functional end-to-end slice over polish.

---

## Architecture (data → debate → verdict → UI)

```
[Azure Function timer / on-demand]                Streamlit UI
        │  daily pull                                  ▲
        ▼                                              │ stream
  data_aggregator.py ──► snapshot.json (price+technicals, structured)
        │                         │
        │ news/filings chunks     │ passed directly to agents (ground truth numbers)
        ▼                         │
  Azure AI Search (vector index)  │
        ▲                         ▼
        └──── retrieval tool ──► Microsoft Agent Framework group chat
                                   ├─ BullAgent   (GPT-4o)
                                   ├─ BearAgent   (GPT-4o)
                                   ├─ NeutralAgent (GPT-4o)
                                   └─ ChairAgent  (GPT-4o, judge) ──► verdict.json
```

### 1. Data Aggregator — `app/data_aggregator.py`
- `get_market_snapshot(ticker)` → `yfinance` OHLCV (e.g. `RELIANCE.NS`), then compute
  **RSI, MACD, SMA/EMA(20/50/200), Bollinger, 52w high/low, volume trend** with
  `pandas-ta` (or hand-rolled — avoid heavy deps). Return a typed dict — this is the
  **ground-truth numbers** the Chair fact-checks against.
- `get_news(ticker)` → `feedparser` over Google News RSS + Moneycontrol/ET RSS (no API key).
  Fall back to `yfinance` financials for earnings/filings highlights.
- `index_news_to_search(articles)` → embed via Azure OpenAI `text-embedding-3-small`,
  upsert into Azure AI Search.
- **Ingestion = Azure Function (timer trigger, daily)** — the Microsoft-native lightweight
  substitute for Azure Data Factory (ADF is too heavy to wire in a hackathon; note ADF as the
  production path in the writeup to satisfy the stack mapping).

### 2. RAG — Azure AI Search (`app/search_client.py`)
- One vector index: news/filing chunks + `{ticker, source, date, url}` metadata.
- `retrieve(query, ticker, k=5)` exposed to agents as a **tool** so each persona pulls its own
  supporting evidence (bull pulls growth news, bear pulls risk news).

### 3. Debate Tier — Microsoft Agent Framework (`app/agents.py`)
- Three persona agents with **strict system prompts** enforcing role
  (e.g. Bear = "aggressive short-seller, find every reason this falls").
- Each agent gets: the structured `snapshot` (in-context) + the `retrieve` tool.
- **Structured output (JSON):** every agent must emit
  `{ stance, points:[{claim, cited_metric, source}], confidence:0-1 }` — no free-form prose
  only. This makes the Chair's job numeric, not vibes-based.
- **Two-round group chat:** Round 1 = independent cases; Round 2 = each sees opponents and
  files **one rebuttal**. Cap at 2 rounds for cost/latency. (Real debate, not 3 monologues.)

### 4. Chair of the Board — `app/chair.py` (Validator + deterministic verifier)
- **Deterministic grounding check first** (`verify_grounding`): regex-extract every numeric
  claim from each agent's `cited_metric`/points and cross-check against `snapshot` within a
  tolerance. Unverifiable/contradicted numbers → grounding penalty. *This is the anti-
  hallucination core — do not rely on the LLM alone.*
- **LLM-as-judge (GPT-4o):** given the three arguments + grounding scores, weight them and
  emit `{ verdict ∈ {Strong Buy, Accumulate, Hold, Reduce}, rationale,
  per_agent:{grounding, confidence, weight} }`.
- Prominent **SEBI/educational disclaimer** attached to every verdict ("not investment advice").

### 5. UI — `app/streamlit_app.py`
- Nifty-50 ticker dropdown + "Run Debate" button.
- **Stream** agent messages as they arrive (debate transcript fills live).
- Final **verdict card**: badge (color-coded), per-agent grounding/confidence bars, citations.
- `st.cache_data` on snapshot + embeddings (Streamlit reruns on every click — caching keeps the
  demo fast and cheap).

### Cost / reliability guardrails (hackathon-critical)
- **Persona agents on `gpt-4o-mini`, Chair on `gpt-4o`** — control spend, keep judge sharp.
- **`MOCK_MODE` flag + fixtures** (`app/fixtures/`): full pipeline runs from cached
  snapshot/news/index so the **live demo survives** yfinance/RSS/Azure rate-limits during judging.
- Cap debate to 2 rounds; cache daily data.

---

## File layout
```
MarketDebater/
├── app/
│   ├── data_aggregator.py    # yfinance + technicals + RSS news
│   ├── search_client.py      # Azure AI Search index + retrieve tool
│   ├── agents.py             # 3 persona agents (Agent Framework)
│   ├── chair.py              # deterministic verifier + judge
│   ├── orchestrator.py       # wires debate → chair, streams events
│   ├── streamlit_app.py      # UI
│   ├── config.py             # Azure endpoints/keys via env (.env)
│   └── fixtures/             # MOCK_MODE sample data
├── functions/                # Azure Function timer-trigger ingestion
├── tests/                    # validation suite (below)
├── requirements.txt
└── README.md                 # incl. MS stack mapping + disclaimer
```

---

## Build order (hackathon sequencing)
1. **Vertical slice first, real data, no Azure:** `data_aggregator` → 3 agents (direct GPT-4o
   calls) → chair → print verdict in a script. Proves the idea works end-to-end fast.
2. Wrap in **Streamlit** with streaming transcript + verdict card.
3. Swap orchestration to **Microsoft Agent Framework** group chat (2 rounds + tools).
4. Add **Azure AI Search** RAG + embeddings; agents retrieve evidence.
5. Add **deterministic grounding verifier** in the Chair.
6. Add **Azure Function** timer ingestion + `MOCK_MODE` fixtures.
7. Polish: disclaimer, caching, cost split (mini/4o), README + stack mapping.

> Steps 1–2 give a demoable product on day 1; 3–5 are the "Microsoft swarm" credibility;
> 6–7 are demo-safety + judging polish.

---

## New suggestions added beyond the original brief
1. **Deterministic grounding verifier** — programmatically fact-check numeric claims against the
   snapshot, not just LLM trust. Biggest credibility win and directly answers "did they hallucinate?".
2. **Structured JSON output per agent** (stance/points/citations/confidence) so the Chair weights
   numerically.
3. **Rebuttal round** — agents see and rebut each other once; makes it a real debate.
4. **MOCK_MODE + fixtures** — demo survives flaky data/rate limits during judging.
5. **Model split (mini for personas, 4o for Chair)** — cost control without dumbing down the judge.
6. **Lightweight backtest as an eval metric** (see validation #6) — a "does it actually work" number.
7. **SEBI/educational disclaimer** — non-negotiable for an Indian financial-advice product.

---

## Validation — "is the project actually working?" (`tests/`)
Run with `pytest tests/` (most use `MOCK_MODE=1` to be deterministic; a few hit live APIs).

1. **Data smoke test** — `get_market_snapshot("RELIANCE.NS")` returns non-empty OHLCV;
   `0 ≤ RSI ≤ 100`, MACD/SMA present and numeric.
2. **RAG test** — index has docs; `retrieve("Q2 earnings", ticker)` returns ≥1 relevant hit
   with required metadata.
3. **Persona-distinctness test** — on the same stock, Bull stance ≠ Bear stance (assert the
   personas didn't collapse into agreement). Quick guard against prompt regressions.
4. **Anti-hallucination golden test** — inject an agent argument citing a fabricated number
   (e.g. "P/E of 3" when snapshot says 25); assert `verify_grounding` flags it and the Chair
   penalizes that agent's weight. *This is the headline correctness test.*
5. **End-to-end test** — run full pipeline on 3 tickers (RELIANCE, TCS, INFY); assert: verdict ∈
   the 4-value enum, transcript non-empty, every cited metric resolvable, latency < target.
6. **Backtest-lite (eval, not pass/fail)** — replay verdicts on ~10 historical dates and compare
   to subsequent 5-day return; report directional hit-rate as a sanity signal. *Explicitly
   labeled "sanity metric, not a performance claim"* (disclaimer).
7. **Manual demo checklist** — pick ticker in Streamlit → watch transcript stream → verdict card
   renders with per-agent grounding bars + disclaimer; toggle `MOCK_MODE` and confirm identical
   flow offline.

---

## Confidence: **7.5 / 10** for a working hackathon demo in the timeframe
- **High (9/10):** agent debate logic, Chair/verifier, Streamlit UI, GPT-4o personas — well-trodden,
  I can scaffold these quickly.
- **Medium (7/10):** Azure AI Search index + Azure AI Foundry GPT-4o deployment/quota wiring —
  doable but config/region/quota friction can eat hackathon hours. Mitigated by building the
  vertical slice without Azure first (step 1).
- **Lower (5–6/10):** reliable live Indian market + news data during a live demo — NSE/RSS can
  rate-limit or break. **Mitigated by yfinance (most reliable free source) + MOCK_MODE fixtures.**
- **Out of scope / honest caveat:** this does **not** produce financially accurate predictions;
  it produces a *transparent, grounded debate*. The backtest is a sanity signal only.

---

## Open questions / assumptions (non-blocking — state these, proceed on assumptions)
- **Azure resources:** Assuming GPT-4o (or 4o-mini) is already deployable in your Azure AI Foundry
  region with quota, and an Azure AI Search service can be created. If not provisioned yet, that's
  the first thing to set up (can run in parallel with step 1).
- **Tickers:** Defaulting the demo to a Nifty-50 dropdown (RELIANCE, TCS, INFY, HDFCBANK, etc.).
- **Debate depth:** Assuming 2 rounds (1 case + 1 rebuttal). Can drop to 1 round if latency hurts
  the demo.
- **Microsoft Agent Framework version/API:** will pin the current Python SDK and use its
  group-chat / sequential orchestration primitive; exact API surface confirmed at build time.
