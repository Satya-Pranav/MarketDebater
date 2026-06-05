"""Azure AI Search RAG.

Optional evidence retrieval over recent news AND recent SEC filings. When
``AZURE_SEARCH_*`` is configured, ``index_news()`` / ``index_filings()`` upsert
ticker-tagged documents; each persona pulls supporting snippets via
``retrieve(query, ticker)``.

Uses **keyword (BM25) search** — no embeddings required, so it works without an
Azure OpenAI embedding quota. A vector field can be added later as a drop-in.

Everything degrades to a safe no-op when unconfigured, so the demo never breaks.

Note: index schema gained a ``source_type`` field ('news' | 'filing') in the
US-pivot. If you have an older ``marketdebater-news`` index without that field,
drop and recreate it (or rename via ``AZURE_SEARCH_INDEX``) to enable filtering.
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
    """Create the news/filings index if it doesn't already exist (keyword search)."""
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
                SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="source", type=SearchFieldDataType.String),
                SimpleField(name="url", type=SearchFieldDataType.String),
                SimpleField(name="published", type=SearchFieldDataType.String),
            ],
        )
    )


def _doc_id(ticker: str, source_type: str, text: str) -> str:
    return hashlib.sha1(f"{ticker}:{source_type}:{text}".encode()).hexdigest()


def index_news(ticker: str, articles: list[dict[str, str]]) -> int:
    """Upsert news articles for a ticker into the index. Returns count (0 if unconfigured)."""
    if not is_configured() or not articles:
        return 0
    try:
        ensure_index()
        docs = [
            {
                "id": _doc_id(ticker, "news", a.get("title", "")),
                "ticker": ticker,
                "source_type": "news",
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


def index_filings(ticker: str, filings: list[dict[str, Any]]) -> int:
    """Upsert SEC filings for a ticker into the index. Returns count (0 if unconfigured)."""
    if not is_configured() or not filings:
        return 0
    try:
        ensure_index()
        docs = []
        for f in filings:
            url = f.get("url", "")
            form = f.get("form", "")
            section = f.get("sections", "") or f.get("summary", "")
            if not section:
                continue
            title = f"{form} filed {f.get('filed_at','')[:10]}"
            docs.append(
                {
                    "id": _doc_id(ticker, "filing", url or title),
                    "ticker": ticker,
                    "source_type": "filing",
                    "title": title,
                    "content": section,
                    "source": f"SEC {form}",
                    "url": url,
                    "published": f.get("filed_at", ""),
                }
            )
        if docs:
            _search_client().merge_or_upload_documents(documents=docs)
        return len(docs)
    except Exception:
        return 0


def retrieve(
    query: str, ticker: str, k: int = 4, source_type: str | None = None
) -> list[dict[str, Any]]:
    """Keyword-search the index, filtered to a ticker (and optionally a source_type)."""
    if not is_configured():
        return []
    try:
        filt = f"ticker eq '{ticker.replace(chr(39), chr(39) * 2)}'"
        if source_type:
            filt += f" and source_type eq '{source_type}'"
        results = _search_client().search(search_text=query, filter=filt, top=k)
        return [
            {
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "source": r.get("source", ""),
                "url": r.get("url", ""),
                "source_type": r.get("source_type", ""),
                "score": r.get("@search.score"),
            }
            for r in results
        ]
    except Exception:
        return []
