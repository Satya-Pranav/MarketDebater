"""Azure AI Search RAG — Phase 5.

Optional evidence retrieval over recent news. When AZURE_SEARCH_* is configured,
fetched news is indexed and each persona can pull its own supporting snippets via
`retrieve()` (the "tool" each agent uses to find evidence).

Uses **keyword (BM25) search** — no embeddings required, so it works without Azure
OpenAI embedding quota (which the free tier lacks). A vector field can be added
later as a drop-in once an embedding deployment is available.

Everything degrades to a safe no-op when unconfigured, so the demo never breaks.
"""
from __future__ import annotations

import hashlib
from typing import Any

from . import config


def is_configured() -> bool:
    """True when an Azure AI Search endpoint + key are set."""
    return bool(config.AZURE_SEARCH_ENDPOINT and config.AZURE_SEARCH_API_KEY)


def _index_client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient

    return SearchIndexClient(
        config.AZURE_SEARCH_ENDPOINT, AzureKeyCredential(config.AZURE_SEARCH_API_KEY)
    )


def _search_client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    return SearchClient(
        config.AZURE_SEARCH_ENDPOINT,
        config.AZURE_SEARCH_INDEX,
        AzureKeyCredential(config.AZURE_SEARCH_API_KEY),
    )


def ensure_index() -> None:
    """Create the news index if it doesn't already exist (keyword search; no vectors)."""
    from azure.search.documents.indexes.models import (
        SearchableField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
    )

    client = _index_client()
    if config.AZURE_SEARCH_INDEX in {idx.name for idx in client.list_indexes()}:
        return
    client.create_index(
        SearchIndex(
            name=config.AZURE_SEARCH_INDEX,
            fields=[
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="ticker", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="source", type=SearchFieldDataType.String),
                SimpleField(name="url", type=SearchFieldDataType.String),
                SimpleField(name="published", type=SearchFieldDataType.String),
            ],
        )
    )


def _doc_id(ticker: str, text: str) -> str:
    return hashlib.sha1(f"{ticker}:{text}".encode()).hexdigest()


def index_news(ticker: str, articles: list[dict[str, str]]) -> int:
    """Upsert news articles for a ticker into the index. Returns count (0 if unconfigured)."""
    if not is_configured() or not articles:
        return 0
    try:
        ensure_index()
        docs = [
            {
                "id": _doc_id(ticker, a.get("title", "")),
                "ticker": ticker,
                "title": a.get("title", ""),
                "content": a.get("summary", "") or a.get("title", ""),
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "published": a.get("published", ""),
            }
            for a in articles
            if a.get("title")
        ]
        if docs:
            _search_client().merge_or_upload_documents(documents=docs)
        return len(docs)
    except Exception:
        return 0


def retrieve(query: str, ticker: str, k: int = 4) -> list[dict[str, Any]]:
    """Keyword-search the news index, filtered to a ticker.

    Returns [] when unconfigured or on any error, so callers can treat retrieval as
    best-effort enrichment.
    """
    if not is_configured():
        return []
    try:
        results = _search_client().search(
            search_text=query,
            filter=f"ticker eq '{ticker.replace(chr(39), chr(39) * 2)}'",
            top=k,
        )
        return [
            {
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "source": r.get("source", ""),
                "url": r.get("url", ""),
                "score": r.get("@search.score"),
            }
            for r in results
        ]
    except Exception:
        return []
