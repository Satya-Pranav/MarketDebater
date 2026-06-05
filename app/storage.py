"""Verdict persistence — Azure Blob Storage with a local-filesystem dev mode.

Key layout (under blob container ``BLOB_CONTAINER`` or under ``LOCAL_RESULTS_DIR``):
    verdicts/<YYYY-MM-DD>/<TICKER>.json   # full debate detail
    verdicts/<YYYY-MM-DD>/index.json      # ranked leaderboard for that date
    verdicts/latest/index.json            # copy of the most recent index.json

When ``LOCAL_RESULTS_DIR`` is set, all reads/writes go to that filesystem path
(handy for dev without an Azure account). Otherwise we use
``AZURE_STORAGE_CONNECTION_STRING``. If neither is set, every write becomes a
no-op (returns ``False``) — so the scan still runs end-to-end and prints
verdicts even with no persistence configured.

Public surface:
    put_verdict(date, ticker, payload) -> bool
    put_index(date, payload)            -> bool
    get_verdict(date, ticker)           -> dict | None
    get_index(date | "latest")          -> dict | None
    list_verdicts(date)                 -> list[str]    # tickers
    list_dates()                        -> list[str]
"""
from __future__ import annotations

import io
import json
import os
from typing import Any, Iterable

from . import config


def _local_root() -> str | None:
    return config.LOCAL_RESULTS_DIR or None


def _container_client():
    from azure.storage.blob import BlobServiceClient

    svc = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
    container = svc.get_container_client(config.BLOB_CONTAINER)
    try:
        container.create_container()
    except Exception:
        pass  # already exists
    return container


def _is_configured() -> bool:
    return bool(_local_root() or config.AZURE_STORAGE_CONNECTION_STRING)


# --------------------------------------------------------------------------- #
# Local filesystem implementation                                             #
# --------------------------------------------------------------------------- #
def _local_path(key: str) -> str:
    root = _local_root() or ""
    return os.path.join(root, key)


def _local_put(key: str, payload: dict[str, Any]) -> bool:
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    return True


def _local_get(key: str) -> dict[str, Any] | None:
    path = _local_path(key)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _local_list(prefix: str) -> list[str]:
    root = _local_path(prefix)
    if not os.path.isdir(root):
        return []
    return sorted(os.listdir(root))


# --------------------------------------------------------------------------- #
# Azure Blob implementation                                                   #
# --------------------------------------------------------------------------- #
def _blob_put(key: str, payload: dict[str, Any]) -> bool:
    container = _container_client()
    data = json.dumps(payload, indent=2, default=str).encode("utf-8")
    container.upload_blob(
        name=key, data=io.BytesIO(data), length=len(data), overwrite=True
    )
    return True


def _blob_get(key: str) -> dict[str, Any] | None:
    container = _container_client()
    try:
        downloader = container.download_blob(key)
    except Exception:
        return None
    return json.loads(downloader.readall().decode("utf-8"))


def _blob_list(prefix: str) -> list[str]:
    container = _container_client()
    return sorted({b.name[len(prefix):].split("/", 1)[0] for b in container.list_blobs(name_starts_with=prefix) if b.name.startswith(prefix)})


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def _put(key: str, payload: dict[str, Any]) -> bool:
    if not _is_configured():
        return False
    if _local_root():
        return _local_put(key, payload)
    return _blob_put(key, payload)


def _get(key: str) -> dict[str, Any] | None:
    if not _is_configured():
        return None
    if _local_root():
        return _local_get(key)
    return _blob_get(key)


def _list(prefix: str) -> list[str]:
    if not _is_configured():
        return []
    if _local_root():
        return _local_list(prefix)
    return _blob_list(prefix)


def put_verdict(date: str, ticker: str, payload: dict[str, Any]) -> bool:
    """Write one ticker's full debate result for a given date."""
    return _put(f"verdicts/{date}/{ticker.upper()}.json", payload)


def put_index(date: str, payload: dict[str, Any], also_latest: bool = True) -> bool:
    """Write the ranked leaderboard for a given date; also mirror to verdicts/latest/."""
    ok = _put(f"verdicts/{date}/index.json", payload)
    if also_latest and ok:
        _put("verdicts/latest/index.json", payload)
    return ok


def get_verdict(date: str, ticker: str) -> dict[str, Any] | None:
    return _get(f"verdicts/{date}/{ticker.upper()}.json")


def get_index(date: str = "latest") -> dict[str, Any] | None:
    return _get(f"verdicts/{date}/index.json")


def list_verdicts(date: str) -> list[str]:
    """Tickers for which a verdict file exists for the given date."""
    names = _list(f"verdicts/{date}/")
    return sorted({n.split(".", 1)[0] for n in names if n.endswith(".json") and n != "index.json"})


def list_dates() -> list[str]:
    """All YYYY-MM-DD subdirs under verdicts/ (excluding 'latest')."""
    return [d for d in _list("verdicts/") if d and d != "latest"]


def _gather_index_for_date(date: str) -> dict[str, Any]:
    """Rebuild the leaderboard for a date from per-ticker blobs (used by --merge-index)."""
    tickers = list_verdicts(date)
    ranked: list[dict[str, Any]] = []
    for t in tickers:
        v = get_verdict(date, t)
        if not v:
            continue
        verdict = v.get("verdict", {})
        snap = v.get("snapshot", {})
        args = v.get("arguments", {})
        ranked.append(
            {
                "ticker": t,
                "company": snap.get("company", t),
                "verdict": verdict.get("verdict", "Hold"),
                "net_bull_score": verdict.get("net_bull_score", 0.0),
                "weights": verdict.get("weights", {}),
                "grounding": {p: g.get("grounding", 0.0) for p, g in (verdict.get("grounding_scores") or {}).items()},
                "confidence": {p: a.get("confidence", 0.0) for p, a in (args or {}).items()},
                "rationale_short": (verdict.get("rationale", "") or "")[:240],
                "as_of": snap.get("as_of", ""),
            }
        )
    ranked.sort(key=lambda r: r.get("net_bull_score", 0.0), reverse=True)
    return {"date": date, "generated_at": _now(), "ranked": ranked}


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def write_merged_index(date: str) -> dict[str, Any]:
    """Recompute and write index.json (and latest/) for a date from per-ticker blobs."""
    payload = _gather_index_for_date(date)
    put_index(date, payload)
    return payload


def is_configured() -> bool:
    return _is_configured()
