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
CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
PERSONA_DEPLOYMENT = os.getenv("AZURE_OPENAI_PERSONA_DEPLOYMENT", "gpt-4o-mini")
EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-3-small")

# Local-dev fallback to standard OpenAI if Azure isn't provisioned yet.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ----- Azure AI Search -----
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "marketdebater-news")

# ----- Data / news -----
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
DEFAULT_TICKERS = [
    t.strip()
    for t in os.getenv(
        "DEFAULT_TICKERS",
        "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS",
    ).split(",")
    if t.strip()
]

# ----- App behaviour -----
DEBATE_ROUNDS = int(os.getenv("DEBATE_ROUNDS", "2"))
MOCK_MODE = _flag("MOCK_MODE", "0")
MAX_AGENT_TURNS = int(os.getenv("MAX_AGENT_TURNS", "12"))


def llm_backend() -> str:
    """Which LLM backend is configured: 'azure', 'openai', or 'none'."""
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
        return "azure"
    if OPENAI_API_KEY:
        return "openai"
    return "none"
