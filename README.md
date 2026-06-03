# MarketDebater Swarm

An **agentic investment committee** that runs an on-demand ranked scan over a
curated US watchlist (default ~25 tickers; the full Google Sheet of ~4.6k is
opt-in). Three rival persona agents debate each stock for three rounds, and a
**Chair of the Board** grades the debate on **data grounding** and
**confidence**, then issues a transparent verdict: **Strong Buy / Accumulate /
Hold / Reduce**. Verdicts are ranked into a leaderboard by a `net_bull_score`
that surfaces both the top buys and the top shorts.

The differentiator vs. a normal chatbot is **visible, graded disagreement** —
you see the debate, and hallucinated stats are caught and penalized by a
deterministic verifier before any verdict is rendered.

> **Educational only — not investment advice.** This system produces a
> *transparent, grounded debate*, not financial predictions. Consult a
> SEC/FINRA-registered advisor before investing.

---

## How it works

```
   Google Sheet (~99 US tickers, refreshed at scan-start)
                        │
                        ▼
          ┌─────────── per ticker ────────────┐
          │                                   │
   yfinance (EOD OHLCV)            Grok web search (live news)
          │                                   │
          └─────► data_aggregator ◄──── sec-api.io (10-K / 10-Q / 8-K + XBRL)
                        │
                        ▼
         ┌─── 3-round debate (case → rebuttal → closing) ───┐
         │  Bull (R1)   Bear (R1)   Risk Manager (R1)        │
         └──────────────────────┬───────────────────────────┘
                                ▼
                  Chair (DeepSeek-V4-Flash)
                  ├── verify_grounding()  [deterministic]
                  └── LLM-as-judge → verdict + net_bull_score
                                │
                                ▼
                 Azure Blob Storage (verdicts/<date>/...)
                                │
                                ▼
                 GitHub Actions cron (nightly, 4 shards)
```

1. **Universe** comes from `app/data/watchlist.txt` (default ~25 sector-diverse
   US tickers, one per line — edit freely). Set `UNIVERSE_FROM_SHEET=1` to fall
   back to the Google Sheet of ~4.6k US IR-database tickers (`UNIVERSE_SHEET_ID`),
   read fresh on every scan. The watchlist is the default because a full
   ~4.6k-ticker scan with DeepSeek-R1 personas is days of compute.
2. **Three co-equal data inputs per ticker:**
   - **Prices** via `yfinance` → snapshot of price + technicals (RSI, MACD,
     SMA 20/50/200, Bollinger, 52w high/low, volume) computed in pure pandas.
   - **News** via Google News RSS, then routed through **Grok 4.1 Fast Reasoning**
     (served by Foundry) to select the most material items and write tight
     summaries. Grok shares the same Azure key as DeepSeek; no separate xAI
     subscription needed. If `GROK_MODEL` is blank, raw RSS is used as-is.
   - **Filings** via **sec-api.io** — last few 10-K/10-Q/8-K filings, with
     Risk-Factors text extracted, plus a small XBRL-derived fundamentals dict
     (`revenue`, `eps_diluted`, `gross_margin`, `debt_to_equity`, etc.) folded
     into the snapshot so the chair can fact-check claims like
     `revenue=395_760_000_000`.
3. **Persona agents** (Bull / Bear / Risk Manager) emit **structured JSON**
   (`{stance, points:[{claim, cited_metric, source}], confidence}`). They route
   to **DeepSeek-R1** (reasoning model) on Azure when `AZURE_OPENAI_PERSONA_R1_DEPLOYMENT`
   is set; otherwise to V4-Flash.
4. **Three rounds:** Round 1 = independent cases; Round 2 = rebuttals;
   Round 3 = closing — each persona must explicitly concede or refute the
   strongest opponent point from round 2.
5. **Chair** (DeepSeek-V4-Flash) runs a **deterministic grounding check** —
   every `cited_metric` is resolved against the snapshot and value-matched, so
   fabricated numbers are flagged programmatically. Then an LLM-as-judge
   weights the arguments by `grounding × confidence` and issues the verdict.
6. **Ranking:** `net_bull_score = weights[bull] − weights[bear]` (continuous,
   sortable, weights well-grounded arguments by construction). Top of the list
   = best buy candidate; bottom = best short candidate.
7. **Persistence + on-demand cron:** verdicts land in **Azure Blob Storage** as
   JSON keyed by date and ticker, plus a per-date `index.json` leaderboard
   mirrored to `verdicts/latest/index.json` for the UI. A **GitHub Actions**
   workflow runs the scan on **manual trigger** (`workflow_dispatch`) — one job
   per scan, no cron, so spend stays predictable. At ~25 tickers the whole scan
   finishes in ~2h even with R1.

---

## Tech stack

| Layer | Technology |
|---|---|
| Persona LLM (Bull / Bear / Risk) | **Azure AI Foundry — DeepSeek-R1** (reasoning) |
| Judge LLM (Chair) | **Azure AI Foundry — DeepSeek-V4-Flash** |
| News editor LLM | **Azure AI Foundry — Grok 4.1 Fast Reasoning** (filters + summarizes RSS) |
| Filings | **sec-api.io** (Query + Section Extractor + XBRL-to-JSON) |
| Prices + technicals | `yfinance` + pandas (no extra dependencies) |
| RAG | **Azure AI Search** (keyword/BM25 over news + filings) |
| Persistence | **Azure Blob Storage** (`marketdebater-verdicts` container) |
| Cron | **GitHub Actions** scheduled workflow (matrix-sharded) |
| Orchestration | Built-in debate orchestrator + optional **Microsoft Agent Framework** path (`USE_AGENT_FRAMEWORK=1`) |
| UI | **Streamlit** (frontend owned by collaborator; reads from Blob) |

---

## Repository layout

```
MarketDebater/
├── app/
│   ├── data/watchlist.txt      # curated 25-ticker default universe (one per line)
│   ├── universe.py             # read watchlist by default; Google Sheet opt-in
│   ├── prices_client.py        # yfinance + hand-rolled technicals
│   ├── news_client.py          # Grok web search (RSS fallback)
│   ├── filings_client.py       # sec-api.io 10-K/10-Q/8-K + XBRL fundamentals
│   ├── data_aggregator.py      # parallel fanout to the three clients
│   ├── llm.py                  # OpenAI-compatible chat client; R1-aware JSON parsing
│   ├── agents.py               # Bull / Bear / Risk personas (route to R1 when set)
│   ├── chair.py                # deterministic verifier + LLM-as-judge + net_bull_score
│   ├── orchestrator.py         # 3-round debate; streams data/argument/verdict events
│   ├── orchestrator_maf.py     # optional Microsoft Agent Framework path (same events)
│   ├── search_client.py        # Azure AI Search (index_news + index_filings + retrieve)
│   ├── storage.py              # Azure Blob persistence (LOCAL_RESULTS_DIR for dev)
│   ├── scan.py                 # cross-ticker scan; sharded; --merge-index
│   ├── streamlit_app.py        # (owned by frontend collaborator)
│   └── config.py               # env / .env config
├── .github/workflows/
│   └── nightly-scan.yml        # on-demand scan (workflow_dispatch only)
├── .env.example                # configuration template
├── requirements.txt
├── requirements-maf.txt        # optional MAF deps
└── README.md
```

---

## Run locally

Requires **Python 3.9+** (3.10+ for the optional Microsoft Agent Framework path).

```bash
# 1. clone + virtualenv
git clone https://github.com/Satya-Pranav/MarketDebater.git
cd MarketDebater
python -m venv .venv && source .venv/bin/activate

# 2. install deps
pip install -r requirements.txt

# 3. configure
cp .env.example .env
# then edit .env — see "Configuration" below
```

### Try it without any credentials (mock mode)

```bash
MOCK_MODE=1 python -m app.orchestrator AAPL          # full debate + verdict from stubs
MOCK_MODE=1 LOCAL_RESULTS_DIR=./tmp \
  python -m app.scan --tickers AAPL,MSFT,NVDA       # 3-ticker scan to ./tmp/verdicts/
```

### Single-ticker live debate (R1 personas + V4 chair)

```bash
python -m app.data_aggregator AAPL          # data smoke test
python -m app.orchestrator AAPL             # full debate + verdict in the terminal
```

### Cross-ticker scan (the on-demand product)

```bash
# Dev: write to filesystem instead of Blob
LOCAL_RESULTS_DIR=./out python -m app.scan --tickers AAPL,MSFT,NVDA

# Real: writes to Azure Blob (AZURE_STORAGE_CONNECTION_STRING set in .env)
python -m app.scan                          # the 25-ticker watchlist
UNIVERSE_FROM_SHEET=1 python -m app.scan    # ~4.6k tickers from the Google Sheet (long!)
python -m app.scan --shard 0 --shards 4     # optional sharding for big universes
python -m app.scan --merge-index            # rebuild today's leaderboard from blobs
```

### Microsoft Agent Framework path (optional)

```bash
pip install -r requirements-maf.txt
USE_AGENT_FRAMEWORK=1 python -m app.orchestrator AAPL
```

Same event stream / verdict; the deterministic grounding verifier and Chair are
reused. Falls back to the built-in orchestrator automatically if the package is
missing or in `MOCK_MODE`. Personas route to R1 when configured.

---

## Configuration

Copy `.env.example` → `.env` and fill in. The essentials for a real run:

| Variable | What it is |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Foundry resource host (code appends `/openai/v1`) |
| `AZURE_OPENAI_API_KEY` | Foundry key |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chair deployment (e.g. `DeepSeek-V4-Flash`) |
| `AZURE_OPENAI_PERSONA_R1_DEPLOYMENT` | DeepSeek-R1 deployment for personas (requires paid Azure) |
| `GROK_MODEL` | Foundry deployment name for Grok (e.g. `grok-4-1-fast-reasoning`) — uses Azure key. Blank = RSS-only news. |
| `SEC_API_KEY` | sec-api.io key for the filings client |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob storage for verdicts |
| `BLOB_CONTAINER` | default `marketdebater-verdicts` |
| `UNIVERSE_SHEET_ID` | Google Sheet ID for the ticker universe |
| `DEBATE_ROUNDS` | default `3` |
| `MOCK_MODE` | `1` = offline stubs |
| `LOCAL_RESULTS_DIR` | dev-only: filesystem path for storage instead of Blob |

Without `AZURE_OPENAI_*`, the app falls back to standard `OPENAI_API_KEY`,
else mock mode. Without `GROK_MODEL`, news passes through raw RSS (no LLM
re-ranking). Without `SEC_API_KEY`, filings input is empty (debate still runs
from prices + news).

---

## Data contract (frontend-facing)

The frontend reads from Blob via two shapes:

**Leaderboard** — `verdicts/<YYYY-MM-DD>/index.json` and `verdicts/latest/index.json`:
```json
{
  "date": "2026-06-03",
  "generated_at": "2026-06-03T11:14:22Z",
  "ranked": [
    {
      "ticker": "AAPL",
      "company": "Apple Inc.",
      "verdict": "Accumulate",
      "net_bull_score": 0.37,
      "weights":    {"bull": 0.62, "bear": 0.25, "neutral": 0.40},
      "grounding":  {"bull": 0.85, "bear": 0.50, "neutral": 0.80},
      "confidence": {"bull": 0.73, "bear": 0.50, "neutral": 0.50},
      "rationale_short": "..."
    }
  ]
}
```

**Per-ticker detail** — `verdicts/<YYYY-MM-DD>/<TICKER>.json`: full snapshot,
news, filings, three-round transcript, and verdict (everything `run_debate()`
returns, plus `net_bull_score`).

**3 bar graphs per persona**: read `grounding[persona]`, `weights[persona]`,
`confidence[persona]` — all already in the verdict, no extra computation.

---

## On-demand scan (GitHub Actions)

`.github/workflows/nightly-scan.yml` is `workflow_dispatch`-only — no cron, you
trigger it manually from the Actions tab when you want a fresh leaderboard.

Inputs:
- **date** — override the scan date (default: today UTC). Useful for backfills.
- **tickers** — comma-separated subset, overrides the watchlist for one run.
- **use_sheet** — set `true` to scan the full Google Sheet (~4.6k tickers).
  At ~5 min/ticker with R1 this exceeds GHA's 6h job limit — only flip it on
  with a smaller persona model or after re-introducing matrix sharding.

The default 25-ticker watchlist finishes in ~2h with R1 personas; a few minutes
with V4-Flash.

Required GitHub Secrets (Settings → Secrets and variables → Actions):
`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`,
`AZURE_OPENAI_PERSONA_DEPLOYMENT`, `AZURE_OPENAI_PERSONA_R1_DEPLOYMENT`,
`GROK_MODEL`, `SEC_API_KEY`, `AZURE_STORAGE_CONNECTION_STRING`,
`BLOB_CONTAINER`, `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_API_KEY`,
`UNIVERSE_SHEET_ID`. (No separate `GROK_API_KEY` — Grok routes through Foundry on the Azure key.)

---

## Validation

```bash
# Smoke each client standalone (no Azure / no LLM needed):
python -m app.prices_client AAPL                # snapshot + technicals
python -m app.news_client AAPL                  # Grok or RSS
python -m app.filings_client AAPL               # sec-api.io
python -m app.universe                          # ticker count

# Full single-ticker pipeline
python -m app.orchestrator AAPL                 # 3 rounds, R1 personas, net_bull_score in verdict

# Sharded scan against the filesystem
LOCAL_RESULTS_DIR=./out python -m app.scan --tickers AAPL,MSFT,NVDA
ls ./out/verdicts/$(date -u +%F)/                # 3 per-ticker JSONs + index.json
```

The **anti-hallucination** property is the headline correctness check: cite
`revenue=999_999_999_999` for a stock whose snapshot says otherwise, and
`verify_grounding()` flags the claim, lists it under `unverified_metrics`, and
the Chair penalizes the weight. This works equally for technicals
(`rsi_14`, `sma_50`, …) and filings-derived metrics (`revenue`, `eps_diluted`,
`gross_margin`, `debt_to_equity`).
