"""Central config — reads .env (python-dotenv) with os.getenv fallbacks.

Matches the repo convention of plain ``os.getenv('VAR', default)``.
Importing this module loads the .env file once.
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

# Load .env from the project root (one level above app/).
load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"))


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# ----- Azure AI Foundry / Azure OpenAI -----
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "DeepSeek-V4-Flash")
PERSONA_DEPLOYMENT = os.getenv("AZURE_OPENAI_PERSONA_DEPLOYMENT", "DeepSeek-V4-Flash")
# When set, persona agents route to this reasoning-model deployment (DeepSeek-R1).
# Chair always stays on CHAT_DEPLOYMENT for speed + cost.
PERSONA_R1_DEPLOYMENT = os.getenv("AZURE_OPENAI_PERSONA_R1_DEPLOYMENT", "")
EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-small")

# Local-dev fallback to standard OpenAI if Azure isn't provisioned yet.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ----- Azure AI Search -----
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "marketdebater-news")

# ----- Grok (news layer) — routed through Azure AI Foundry -----
# Foundry's model catalog now serves xAI Grok via the same /openai/v1 endpoint
# and the same Azure key. GROK_MODEL is the Foundry deployment name; blank = disable.
GROK_MODEL = os.getenv("GROK_MODEL", "").strip()

# ----- SEC filings (sec-api.io) -----
SEC_API_KEY = os.getenv("SEC_API_KEY", "")
SEC_API_BASE = os.getenv("SEC_API_BASE", "https://api.sec-api.io")

# ----- Universe -----
# Default source = curated watchlist file (small, fast, deterministic).
# When UNIVERSE_FROM_SHEET=1, fall back to the Google Sheet (4k+ tickers).
WATCHLIST_FILE = os.getenv("WATCHLIST_FILE", "").strip() or os.path.join(
    os.path.dirname(__file__), "data", "watchlist.txt"
)
UNIVERSE_FROM_SHEET = _flag("UNIVERSE_FROM_SHEET", "0")
UNIVERSE_SHEET_ID = os.getenv(
    "UNIVERSE_SHEET_ID", "1PEFP4UJzsEOv3h04kXlGkbhYHwOiTycCMR4WzKan2Cs"
)
UNIVERSE_SHEET_GID = os.getenv("UNIVERSE_SHEET_GID", "0")

# ----- Verdict persistence (Azure Blob Storage) -----
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER", "marketdebater-verdicts")
# Dev-only: if set, storage writes go to this filesystem dir instead of Blob.
LOCAL_RESULTS_DIR = os.getenv("LOCAL_RESULTS_DIR", "")

# ----- Data / news -----
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
DEFAULT_TICKERS = [
    t.strip()
    for t in os.getenv(
        "DEFAULT_TICKERS",
        "AAPL,MSFT,GOOGL,NVDA,AMZN",
    ).split(",")
    if t.strip()
]

# ----- App behaviour -----
DEBATE_ROUNDS = int(os.getenv("DEBATE_ROUNDS", "3"))
MOCK_MODE = _flag("MOCK_MODE", "0")
MAX_AGENT_TURNS = int(os.getenv("MAX_AGENT_TURNS", "12"))
# Run the debate through Microsoft Agent Framework agents (needs `agent-framework`,
# Python 3.10+). Falls back to the built-in orchestrator if unset or unavailable.
USE_AGENT_FRAMEWORK = _flag("USE_AGENT_FRAMEWORK", "0")


def llm_backend() -> str:
    """Which LLM backend is configured: 'azure', 'openai', or 'none'."""
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
        return "azure"
    if OPENAI_API_KEY:
        return "openai"
    return "none"
