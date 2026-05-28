# ⚖️ MarketDebater Swarm

An **agentic investment committee** for Indian (NSE) stocks. Instead of a single,
homogenized AI "answer," three rival persona agents **debate** a stock and a
**Chair of the Board** grades their arguments on **data grounding** and **confidence**,
then issues a transparent verdict: **Strong Buy / Accumulate / Hold / Reduce**.

The differentiator vs. a normal chatbot is **visible, graded disagreement** — you watch
the debate and see *why* the committee landed where it did, with hallucinated stats
caught and penalized by a deterministic verifier.

> ⚠️ **Educational only — not investment advice.** This system produces a *transparent,
> grounded debate*, not financial predictions. Consult a SEBI-registered advisor before investing.

---

## How it works

```
                       Streamlit UI (live transcript + verdict card)
                                        ▲  stream
                                        │
yfinance (EOD OHLCV) ─┐                 │
   + RSS news ────────┼─► data_aggregator ─► snapshot (price + technicals = GROUND TRUTH)
                      │                       │
                      │                       ▼
                      │      ┌──────── debate (2 rounds: case → rebuttal) ────────┐
                      │      │  🐂 Perma-Bull   🐻 Perma-Bear   ⚖️ Risk Manager   │
                      │      └───────────────────────┬──────────────────────────┘
                      │                              ▼
                      │            Chair of the Board ── verify_grounding() [deterministic]
                      │                              └─ LLM-as-judge ─► verdict + per-agent weights
                      ▼
          Azure AI Search (RAG, optional evidence retrieval)
```

1. **Data aggregator** pulls 1y of EOD OHLCV via `yfinance` and computes technicals
   (RSI, MACD, SMA 20/50/200, Bollinger, 52w high/low, volume trend) in pure pandas.
   Plus recent headlines from Google News RSS. This structured snapshot is the
   **ground truth** the Chair fact-checks against.
2. **Persona agents** (Bull / Bear / Risk Manager) each emit **structured JSON**:
   `{stance, points:[{claim, cited_metric, source}], confidence}`. Round 1 is independent
   cases; round 2 is rebuttals.
3. **Chair** runs a **deterministic grounding check** first — every `cited_metric` is
   resolved against the snapshot and value-matched, so fabricated numbers are flagged
   programmatically (not left to the LLM's good faith). Then an LLM-as-judge weights the
   arguments by `grounding × confidence` and issues the verdict.

---

## Tech stack (Microsoft-native)

| Layer | Technology |
|---|---|
| LLM (personas + judge) | **Azure AI Foundry** — DeepSeek-V4-Flash via the OpenAI-compatible `/openai/v1` route (swap in any catalog model) |
| Orchestration | Debate orchestrator (Microsoft Agent Framework group-chat path planned) |
| RAG | **Azure AI Search** (optional evidence retrieval) |
| UI | **Streamlit** |
| Market data | `yfinance` (NSE EOD) + Google News RSS — no API keys required |

> **Production stack mapping:** daily ingestion is designed as an Azure Function (timer
> trigger) — the lightweight, hackathon-friendly substitute for Azure Data Factory.

---

## Repository layout

```
MarketDebater/
├── app/
│   ├── data_aggregator.py   # yfinance + hand-rolled technicals + RSS news
│   ├── llm.py               # OpenAI-compatible backend (Azure Foundry / OpenAI / mock)
│   ├── agents.py            # Bull / Bear / Risk personas → structured JSON
│   ├── chair.py             # deterministic grounding verifier + LLM-as-judge
│   ├── orchestrator.py      # multi-round debate; streams data/argument/verdict events
│   ├── streamlit_app.py     # UI (live transcript + graded verdict card)
│   └── config.py            # env/.env config
├── .env.example             # configuration template (copy to .env)
├── requirements.txt
├── PLAN.md                  # full design doc + build sequencing
└── README.md
```

---

## Run locally

Requires **Python 3.9+**.

```bash
# 1. clone + virtualenv
git clone https://github.com/Satya-Pranav/MarketDebater.git
cd MarketDebater
python -m venv .venv && source .venv/bin/activate

# 2. install deps
pip install -r requirements.txt

# 3. configure
cp .env.example .env
#   then edit .env — see "Configuration" below
```

### Try it without any credentials (mock mode)
The whole pipeline runs offline on deterministic stubs — great for development/demos:

```bash
MOCK_MODE=1 python -m app.orchestrator RELIANCE.NS     # prints a full debate + verdict
MOCK_MODE=1 streamlit run app/streamlit_app.py          # UI, no Azure needed
```

### Run for real (Azure)
With your Azure values in `.env`:

```bash
python -m app.data_aggregator RELIANCE.NS   # data smoke test
python -m app.orchestrator RELIANCE.NS      # live debate + verdict in the terminal
streamlit run app/streamlit_app.py          # the full UI at http://localhost:8501
```

---

## Configuration

Copy `.env.example` → `.env` and fill in. The essentials for a live run:

| Variable | What it is |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Base resource host, e.g. `https://<resource>.services.ai.azure.com/` (code appends `/openai/v1`) |
| `AZURE_OPENAI_API_KEY` | Key from your Azure AI Foundry resource |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Deployment name for the Chair (e.g. `DeepSeek-V4-Flash`) |
| `AZURE_OPENAI_PERSONA_DEPLOYMENT` | Deployment name for the personas (can be the same) |
| `MOCK_MODE` | `1` = offline stubs, `0` = live |
| `APP_PASSWORD` | Optional gate for the hosted app (see below) |

No `AZURE_OPENAI_*`? The app falls back to standard `OPENAI_API_KEY` if set, else mock mode.

---

## Deploy to the web (Streamlit Community Cloud)

End-to-end, free, public URL:

1. **Push to GitHub** (already done for this repo: `Satya-Pranav/MarketDebater`).
2. Go to **https://share.streamlit.io** → sign in with GitHub → authorize repo access.
3. **Create app → Deploy a public app from GitHub**:
   - Repository: `Satya-Pranav/MarketDebater`
   - Branch: `main`
   - Main file path: `app/streamlit_app.py`
4. **Advanced settings → Secrets** — paste (TOML), filling in your values:
   ```toml
   AZURE_OPENAI_ENDPOINT = "https://<resource>.services.ai.azure.com/"
   AZURE_OPENAI_API_KEY = "your-azure-key"
   AZURE_OPENAI_CHAT_DEPLOYMENT = "DeepSeek-V4-Flash"
   AZURE_OPENAI_PERSONA_DEPLOYMENT = "DeepSeek-V4-Flash"
   APP_PASSWORD = "pick-a-password-to-share"
   ```
5. **Deploy.** You'll get a public `https://<name>.streamlit.app` URL.

**Cost protection:** when `APP_PASSWORD` is set, visitors must enter it before running a
real (paid) debate — share it only with people you trust. Without it the app is open;
the **Demo mode** toggle always runs free, offline mock debates.

Secrets live in Streamlit's dashboard and are mirrored into the environment at startup —
they are **never** committed (`.env` is gitignored).

---

## Validation

```bash
MOCK_MODE=1 python -m app.orchestrator RELIANCE.NS   # asserts verdict ∈ enum, grounding computed
python -m app.data_aggregator RELIANCE.NS            # asserts RSI ∈ [0,100], price > 0, news fetched
```

The headline correctness property — the deterministic verifier flags fabricated numbers —
can be checked directly: cite `pe_ratio=3` when the snapshot says `22.65` and
`verify_grounding` marks the claim unverified and lists the bad metric.
