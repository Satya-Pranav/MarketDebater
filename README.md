# MarketDebater Swarm

> **Live demo**: [web-production-f16ae.up.railway.app](https://web-production-f16ae.up.railway.app/)
> **Submission deck**: [`MarketDebaters_Deck.pdf`](MarketDebaters_Deck.pdf)
> **Team**: P Satya Pranav · PVR Pratyusha

An **agentic investment committee** for US-listed stocks. Three rival persona
agents — PermaBull, PermaBear, Risk Manager — debate every ticker from one
immutable snapshot of prices, news, and SEC filings. A **deterministic Python
verifier** re-checks every numeric claim against the snapshot before the
**Chair** weights the arguments and issues a transparent verdict
(**Strong Buy / Accumulate / Hold / Reduce**). Verdicts persist to a daily
ranked leaderboard surfacing both top buys and top shorts.

The differentiator vs. a normal chatbot is **visible, graded disagreement** —
you see the full debate, and **hallucinated stats are caught and penalized by
plain Python before any verdict is rendered**. If grounding were an LLM call,
the whole project would be theatre.

> **Educational only — not investment advice.** This system produces a
> *transparent, grounded debate*, not financial predictions. Consult a
> SEC/FINRA-registered advisor before investing.

---

## Project status (as of 2026-06-07)

| Area | Status |
|---|---|
| Backend (agents, chair, orchestrator, verifier) | ✅ Shipped — V4-Flash default, R1 wired |
| Django frontend (UI, debate, leaderboard) | ✅ Shipped — collapsible persona deep-dive, timing UI, footer hover card |
| Streamlit frontend | ✅ Shipped — separate UI, same Blob data contract |
| Persistence (Azure Blob) | ✅ Wired & verified end-to-end |
| Cross-stock scan (CLI + UI button) | ✅ Shipped — 25-ticker watchlist + ad-hoc subsets |
| GitHub Actions workflow | ✅ `workflow_dispatch`-only (no cron, predictable spend) |
| Live production deploy | ✅ Railway (gunicorn + WhiteNoise + Django 6) |
| Security hardening | ✅ SECRET_KEY required when DEBUG off, scan ticker regex + cap, HSTS, X-Forwarded-Proto trust, etc. |
| Submission deck | ✅ `MarketDebaters_Deck.pdf` (10 slides, ~25 KB) |
| Demo script | ✅ See `MarketDebaters_Deck.pdf` slide 7-8 and conversation history |

---

## How it works

```
                    Universe (25-ticker watchlist · 4.6K-ticker sheet opt-in)
                                          │
                                          ▼
          ┌─────────────────── per ticker, in parallel ──────────────────┐
          │                              │                               │
   yfinance (prices)            Grok 4.1 (news editor)            sec-api.io
          │                              │                               │
          └─────────────► IMMUTABLE SNAPSHOT ◄────────────────────────────┘
                                          │   (XBRL fundamentals folded in)
                                          ▼
          ┌──── 3-round debate (Case → Rebuttal → Closing) ────┐
          │                                                    │
          │   PermaBull       PermaBear       Risk Manager     │
          │   (V4-Flash)      (V4-Flash)      (V4-Flash)       │
          │   ↓                ↓               ↓               │
          │   {stance, points: [{claim, cited_metric, source}], confidence}
          └────────────────────────┬──────────────────────────────┘
                                   ▼
                  ┌──── Chair (DeepSeek-V4-Flash) ────┐
                  │  1. verify_grounding()  ← pure Python; re-checks every
                  │                            cited_metric against snapshot
                  │  2. LLM-as-judge       ← weights = grounding × confidence
                  │                          → verdict + net_bull_score
                  └─────────────────┬─────────────────┘
                                    ▼
                  Azure Blob Storage  ·  verdicts/<date>/<ticker>.json
                                                ·  index.json (ranked leaderboard)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
            Django frontend                Streamlit frontend
       (live on Railway)                 (collaborator-owned)
```

1. **Universe**: default is `app/data/watchlist.txt` (25 sector-diverse US tickers — Mag 7, financials, healthcare, consumer, energy, industrial, NFLX). Set `UNIVERSE_FROM_SHEET=1` to use the full ~4.6K-ticker Google Sheet instead.

2. **Three co-equal data sources, fetched in parallel** via `ThreadPoolExecutor`:
   - **Prices** (`app/prices_client.py`) — yfinance 1y EOD OHLCV + technicals (RSI-14, MACD, SMA 20/50/200, Bollinger, 52w range, volume) computed in pure pandas.
   - **News** (`app/news_client.py`) — Google News RSS pulled via `requests` (bundled certs), then routed through **Grok 4.1 Fast Reasoning** (served via Azure AI Foundry's catalog) to select and summarize the 8 most material headlines. `GROK_MODEL=''` falls back to raw RSS with no LLM editing.
   - **Filings** (`app/filings_client.py`) — sec-api.io for last few 10-K / 10-Q / 8-K filings, with Section Extractor pulling Risk Factors text and XBRL-to-JSON yielding `revenue`, `eps_diluted`, `gross_margin`, `debt_to_equity`. Fundamentals fold into the snapshot so the verifier resolves them with the same code path as technicals.

3. **Persona agents** (Bull / Bear / Risk Manager, all in `app/agents.py`) emit structured JSON with a strict shape so the verifier can mechanically check every numeric claim:
   ```json
   {
     "stance": "Buy",
     "points": [
       {"claim": "AAPL RSI 42.5 leaves headroom for a move up.",
        "cited_metric": "rsi_14=42.5",
        "source": "technicals"}
     ],
     "confidence": 0.72
   }
   ```
   - Default routing: all three personas use **DeepSeek-V4-Flash** (`AZURE_OPENAI_PERSONA_DEPLOYMENT`).
   - Optional: set `AZURE_OPENAI_PERSONA_R1_DEPLOYMENT=DeepSeek-R1-0528` to route personas through the R1 reasoning model. Verified 2026-06-03: V4-Flash produced equivalent grounded arguments at ~6× the speed and ~20× lower cost — the deterministic verifier is what makes verdicts trustworthy, not chain-of-thought depth.

4. **Three rounds** (`DEBATE_ROUNDS=3` default; configurable per call):
   - Round 1: independent cases from each persona.
   - Round 2: rebuttals (each persona sees opponents' Round 1 points).
   - Round 3: closing — each persona must explicitly address the strongest opponent point from Round 2.
   - The Django UI exposes a 1–5 round selector on the search form.

5. **Chair** (`app/chair.py`, runs on V4-Flash via `AZURE_OPENAI_CHAT_DEPLOYMENT`):
   - **Stage 1**: `verify_grounding()` — pure Python, no LLM. Parses every `cited_metric=name=value` with a regex (`r"([A-Za-z_][\w.]*)\s*=\s*(-?\d[\d,]*\.?\d*)"`), resolves the metric against the snapshot (handles flat keys, dot-paths, and underscore-flattened nested forms interchangeably), and verifies the claimed value within a 5% tolerance. Fabricated stats land in `unverified_metrics` and slash the persona's grounding score.
   - **Stage 2**: LLM-as-judge — weights only verified claims by `grounding × confidence`, picks the verdict tier, emits a rationale. The Chair never sees rejected claims.

6. **Ranking**: `net_bull_score = weights[bull] − weights[bear]` (continuous, sortable, surfaces top buys and top shorts in one signal). Drives the leaderboard ordering.

7. **Persistence & on-demand scan**:
   - Each verdict writes to `verdicts/<YYYY-MM-DD>/<TICKER>.json` on Azure Blob.
   - A per-date `index.json` holds the ranked leaderboard.
   - `verdicts/latest/index.json` mirrors the most recent date for the frontend.
   - `LOCAL_RESULTS_DIR` env var redirects writes to the filesystem for dev.
   - The Django UI persists single-debate verdicts to the leaderboard automatically (the "✓ Added to Daily Suggestions" pill).
   - GitHub Actions workflow at `.github/workflows/nightly-scan.yml` is `workflow_dispatch`-only — manual triggers, no cron, predictable LLM spend.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Persona LLM** (Bull / Bear / Risk) | Azure AI Foundry — **DeepSeek-V4-Flash** (DeepSeek-R1 wired) |
| **Chair LLM** (judge) | Azure AI Foundry — DeepSeek-V4-Flash |
| **News editor** | Azure AI Foundry — **Grok 4.1 Fast Reasoning** (same Azure key, no separate xAI account) |
| **Filings** | **sec-api.io** (Query API + Section Extractor + XBRL-to-JSON) |
| **Prices + technicals** | yfinance + pandas (no extra deps) |
| **RAG** | Azure AI Search (BM25 over news + filings, optional) |
| **Persistence** | Azure Blob Storage (`marketdebater-verdicts` container) |
| **Web frontend** | **Django 6** + WhiteNoise + gunicorn |
| **Auxiliary UI** | Streamlit (`app/streamlit_app.py`) |
| **Orchestration** | Built-in debate orchestrator + optional Microsoft Agent Framework (`USE_AGENT_FRAMEWORK=1`) |
| **Hosting** | **Railway** (auto-deploy from `main`) |
| **CI / scan workflow** | GitHub Actions (`workflow_dispatch`-only) |

---

## Repository layout

```
MarketDebater/
├── app/                        # core swarm implementation (canonical)
│   ├── data/watchlist.txt      # default 25-ticker US universe
│   ├── universe.py             # watchlist + Google Sheet loader
│   ├── prices_client.py        # yfinance + hand-rolled technicals
│   ├── news_client.py          # RSS + Grok-via-Foundry editor
│   ├── filings_client.py       # sec-api.io 10-K/10-Q/8-K + XBRL
│   ├── data_aggregator.py      # parallel fanout to the three clients
│   ├── llm.py                  # OpenAI-compatible client + 429 retry
│   ├── agents.py               # Bull / Bear / Risk Manager personas
│   ├── chair.py                # deterministic verifier + LLM-as-judge
│   ├── orchestrator.py         # 3-round debate + verdict + per-phase timing
│   ├── orchestrator_maf.py     # optional MS Agent Framework path
│   ├── scan.py                 # cross-stock scan; shards + merge-index
│   ├── search_client.py        # Azure AI Search (BM25)
│   ├── storage.py              # Blob + LOCAL_RESULTS_DIR dev mode
│   └── streamlit_app.py        # Streamlit UI
├── backend/marketdebater/      # thin re-export shim (backend.marketdebater.X → app.X)
├── frontend/                   # Django UI
│   ├── manage.py
│   ├── dashboard/              # views, forms, urls, templatetags
│   ├── marketdebater_frontend/ # settings, wsgi, asgi
│   ├── static/dashboard/       # styles.css (~2K lines)
│   └── templates/dashboard/    # home.html, leaderboard.html, base.html
├── manage.py                   # repo-root Django entrypoint
├── Procfile                    # Railway: release (migrate + collectstatic) + web (gunicorn)
├── MarketDebaters_Deck.pdf     # 10-slide submission deck
├── .github/workflows/
│   └── nightly-scan.yml        # workflow_dispatch-only scan
├── .env.example                # configuration template
├── requirements.txt            # primary Python deps
├── requirements-maf.txt        # optional MAF deps
├── copilot-instructions.md     # AI-assistant project guardrails
└── README.md
```

---

## Run locally

Requires **Python 3.11+** (3.10+ minimum for the optional Microsoft Agent Framework path).

```bash
# 1. clone + virtualenv
git clone https://github.com/Satya-Pranav/MarketDebater.git
cd MarketDebater
python -m venv .venv && source .venv/bin/activate

# 2. install deps
pip install -r requirements.txt

# 3. configure
cp .env.example .env
# Edit .env — at minimum set DJANGO_DEBUG=1 for local dev, plus the Azure /
# sec-api keys for a real run. See "Configuration" below.
```

### Run the Django frontend

```bash
DJANGO_DEBUG=1 python manage.py migrate
DJANGO_DEBUG=1 python manage.py runserver
```

Open http://127.0.0.1:8000. Enter a US ticker (e.g. `AAPL`), pick rounds (1–5), click **Debate**. The result page renders the verdict, the persona deep-dive playcard (collapsible), the timing breakdown, and a "✓ Added to Daily Suggestions" pill. The leaderboard tab shows the ranked verdicts from the most recent scan.

### Try it without any credentials (mock mode)

```bash
MOCK_MODE=1 python -m app.orchestrator AAPL          # full debate + verdict from deterministic stubs
MOCK_MODE=1 LOCAL_RESULTS_DIR=./tmp \
  python -m app.scan --tickers AAPL,MSFT,NVDA       # 3-ticker scan to ./tmp/verdicts/
```

### Single-ticker live debate (V4-Flash personas + V4 chair)

```bash
python -m app.data_aggregator AAPL                # data smoke test
python -m app.orchestrator AAPL                   # full debate + verdict in the terminal
```

### Cross-ticker scan (CLI)

```bash
# Dev: write to filesystem instead of Blob
LOCAL_RESULTS_DIR=./out python -m app.scan --tickers AAPL,MSFT,NVDA

# Real: writes to Azure Blob (AZURE_STORAGE_CONNECTION_STRING set in .env)
python -m app.scan                                # the 25-ticker watchlist
UNIVERSE_FROM_SHEET=1 python -m app.scan          # ~4.6K tickers from the Google Sheet (slow!)
python -m app.scan --shard 0 --shards 4           # optional sharding for big universes
python -m app.scan --merge-index                  # rebuild today's leaderboard from blobs
python -m app.scan --tickers AAPL,MSFT --rounds 1 # round-count override
```

### Streamlit UI (auxiliary)

```bash
streamlit run app/streamlit_app.py
```

### Microsoft Agent Framework path (optional)

```bash
pip install -r requirements-maf.txt
USE_AGENT_FRAMEWORK=1 python -m app.orchestrator AAPL
```

Same event stream / verdict; the deterministic grounding verifier and Chair are reused. Falls back to the built-in orchestrator automatically if the package is missing or in `MOCK_MODE`.

---

## Deploy to Railway

The repo includes a `Procfile` for one-click Railway deployment. The same setup works on Render / Heroku / Fly with minimal changes.

1. Sign in to https://railway.app/ with GitHub.
2. **New Project → Deploy from GitHub repo → MarketDebater**.
3. **Variables** tab → **Raw Editor** → paste the config from your local `.env`, then add:
   - `DJANGO_SECRET_KEY=...` — generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
   - `DJANGO_ALLOWED_HOSTS=<your-app>.up.railway.app`
   - Leave `DJANGO_DEBUG` **unset** (defaults to off; raises `ImproperlyConfigured` if `SECRET_KEY` is also missing — fail-fast).
4. First build runs `release: python manage.py migrate && python manage.py collectstatic`, then `web: gunicorn marketdebater_frontend.wsgi:application` via the `Procfile`.
5. Verify: open the URL → landing page renders styled; click AAPL → debate completes in 60–120s.

**Known limitation**: Railway's request timeout is ~5 minutes. Single debates at 1–3 rounds and small scans (2–3 tickers, 1 round) work; full 5-ticker scans or 5-round debates require switching to SSE streaming or a background worker (roadmap item).

---

## Configuration

Copy `.env.example` → `.env`. Essentials for a real run:

### LLM / data keys

| Variable | Purpose |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Foundry resource host (code appends `/openai/v1`) |
| `AZURE_OPENAI_API_KEY` | Foundry key — serves DeepSeek + Grok + Embeddings |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chair deployment (default `DeepSeek-V4-Flash`) |
| `AZURE_OPENAI_PERSONA_DEPLOYMENT` | Persona deployment (default `DeepSeek-V4-Flash`) |
| `AZURE_OPENAI_PERSONA_R1_DEPLOYMENT` | Optional: route personas through R1 (e.g. `DeepSeek-R1-0528`) |
| `GROK_MODEL` | Foundry catalog name (default `grok-4-1-fast-reasoning`; blank = RSS-only news) |
| `SEC_API_KEY` | sec-api.io key |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob for verdict persistence |
| `BLOB_CONTAINER` | default `marketdebater-verdicts` |
| `UNIVERSE_SHEET_ID` | Google Sheet ID for the opt-in 4.6K universe |
| `DEBATE_ROUNDS` | default `3` |
| `MOCK_MODE` | `1` = offline deterministic stubs |
| `LOCAL_RESULTS_DIR` | dev only: filesystem path instead of Blob |

### Django production settings

| Variable | Purpose |
|---|---|
| `DJANGO_DEBUG` | defaults to **off**. Set `1` for local dev. |
| `DJANGO_SECRET_KEY` | **required when DEBUG is off** (raises `ImproperlyConfigured` at startup) |
| `DJANGO_ALLOWED_HOSTS` | comma-separated hostnames (e.g. `myapp.up.railway.app`) |
| `DJANGO_HSTS_SECONDS` | default `3600` (1h). Bump to `31536000` (1yr) once HTTPS is stable. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | extra comma-separated origins (custom domains). `*.up.railway.app` is always trusted. |

Without `AZURE_OPENAI_*`, the app falls back to standard `OPENAI_API_KEY`, else mock mode. Without `GROK_MODEL`, news passes through raw RSS. Without `SEC_API_KEY`, filings input is empty (debate still runs from prices + news).

---

## Security posture

Hardened end-to-end ahead of public deploy. Key safeguards (verified in audit, PR #2):

- ✅ `.env` gitignored; only `.env.example` (template, no values) in repo.
- ✅ `DJANGO_DEBUG` defaults off; fail-fast on missing `DJANGO_SECRET_KEY`.
- ✅ `SECURE_PROXY_SSL_HEADER`, HSTS, `X_FRAME_OPTIONS=DENY`, `SECURE_REFERRER_POLICY` all set in production.
- ✅ CSRF middleware enabled; all POST endpoints use `{% csrf_token %}`.
- ✅ Ticker input regex-validated (`[A-Z0-9]{1,10}(\.[A-Z]{1,2})?`) on both single-debate and scan endpoints.
- ✅ Scan POST capped at 25 tickers to prevent quota / runtime abuse.
- ✅ TLS verification enabled on all outbound HTTP (no `verify=False` anywhere).
- ✅ No `eval` / `exec` / `pickle.loads` / `shell=True` / raw SQL.
- ✅ LLM 429s caught and retried with exponential backoff (2/4/8s).
- ⚠️ Deferred: rate limiting (per-IP), `APP_PASSWORD` gate for Django (Streamlit already has it), `|safe` on rationale (low practical risk — LLM-quoted news).

---

## Data contract (frontend-facing)

The Django and Streamlit frontends read identical shapes from Blob:

**Leaderboard** — `verdicts/<YYYY-MM-DD>/index.json` (and mirrored to `verdicts/latest/index.json`):
```json
{
  "date": "2026-06-06",
  "generated_at": "2026-06-06T11:14:22Z",
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

**Per-ticker detail** — `verdicts/<YYYY-MM-DD>/<TICKER>.json`: full snapshot, news, filings, three-round transcript, verdict, and arguments.

---

## On-demand scan workflow (GitHub Actions)

`.github/workflows/nightly-scan.yml` is `workflow_dispatch`-only — no cron. Trigger from the Actions tab when you want a fresh leaderboard.

Inputs:
- **date** — override the scan date (default: today UTC).
- **tickers** — comma-separated subset, overrides the watchlist for one run.
- **use_sheet** — `true` to scan the full Google Sheet (~4.6K tickers; only viable with V4-Flash and sharding).

Required GitHub Secrets: same set as `.env` — `AZURE_OPENAI_*`, `GROK_MODEL`, `SEC_API_KEY`, `AZURE_STORAGE_CONNECTION_STRING`, etc.

---

## Validation

```bash
# Smoke each client standalone (no Azure / no LLM needed):
python -m app.prices_client AAPL                # snapshot + technicals
python -m app.news_client AAPL                  # Grok or RSS fallback
python -m app.filings_client AAPL               # sec-api.io
python -m app.universe                          # ticker count

# Full single-ticker pipeline
python -m app.orchestrator AAPL                 # 3 rounds, V4 personas, net_bull_score in verdict

# Sharded scan against the filesystem
LOCAL_RESULTS_DIR=./out python -m app.scan --tickers AAPL,MSFT,NVDA
ls ./out/verdicts/$(date -u +%F)/                # 3 per-ticker JSONs + index.json
```

**The anti-hallucination property is the headline correctness check.** Cite `revenue=999_999_999_999` for a stock whose snapshot says otherwise, and `verify_grounding()` flags the claim, lists it under `unverified_metrics`, and the Chair penalizes the persona's weight. This works equally for technicals (`rsi_14`, `sma_50`, …) and filings-derived metrics (`revenue`, `eps_diluted`, `gross_margin`, `debt_to_equity`).

---

## Roadmap (Future versions yet to come)

1. **Wider US universe** — Nasdaq 100, S&P 500, Russell 3000 (4.6K-ticker sheet already wired).
2. **IPO coverage** — S-1 prospectus ingestion + lockup expiry + dilution risk tracking.
3. **Other markets** — LSE, HKEX, TSE via yfinance suffix; return to NSE / BSE where this project originated.
4. **Earnings calls** — Transcript ingestion + persona Q&A on management tone, sentiment delta folded into the snapshot.
5. **Backtested accuracy** — Per-persona win rate vs forward returns; Chair auto-learns weighting from history.
6. **Streaming + mobile** — SSE live debate transcripts (no more 5-min hosting timeout), background workers for whole-universe scans, PWA.

---

## Team

| Member | GitHub | Role |
|---|---|---|
| **P Satya Pranav** | [@pranavps47](https://github.com/pranavps47) | Frontend · Deployment · Security |
| **PVR Pratyusha** | [@PVRPratyusha](https://github.com/PVRPratyusha) | Backend · Orchestration |

Built as a hackathon submission. Live URL, repo, and submission deck linked at the top of this README.
