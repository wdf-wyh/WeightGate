"""Per-tenant vector store (Phase 3) — isolated directory + lightweight local index.

Layout:
  data/tenants/{tenant_id}/vector/
    collections/{collection}/docs.jsonl

No cross-tenant reads/writes. Optional Chroma persist dir binding via chromadb
when installed; otherwise LocalVectorStore (hash embedding) is the default demo path.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .fs import (
    TenantIsolationError,
    ensure_tenant_layout,
    safe_tenant_path,
    tenant_root,
    validate_tenant_id,
)

_COLLECTION_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")
EMBED_DIM = 64


def tenant_vector_dir(tenant_id: str) -> Path:
    """Return (and ensure) the tenant-scoped vector root."""
    ensure_tenant_layout(tenant_id)
    root = tenant_root(tenant_id) / "vector"
    root.mkdir(parents=True, exist_ok=True)
    return root


def chroma_persist_dir(tenant_id: str) -> Path:
    """Chroma (or equal) persist directory — never shared across tenants."""
    path = tenant_vector_dir(tenant_id) / "chroma"
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_collection_name(name: str) -> str:
    if not _COLLECTION_RE.fullmatch(name):
        raise TenantIsolationError(f"invalid collection name: {name!r}")
    return name


def assert_vector_access(tenant_id: str, *parts: str) -> Path:
    """Resolve a path under tenant vector/; reject escapes / other tenants."""
    validate_tenant_id(tenant_id)
    return safe_tenant_path(tenant_id, "vector", *parts)


def hash_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic bag-of-tokens hash embedding (no numpy / no GPU)."""
    vec = [0.0] * dim
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", (text or "").lower())
    if not tokens:
        tokens = ["_empty"]
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


@dataclass
class VectorHit:
    id: str
    score: float
    document: str
    metadata: dict[str, Any]


class LocalVectorStore:
    """Minimal JSONL vector index under data/tenants/{id}/vector/collections/."""

    def __init__(self, tenant_id: str, collection: str = "default") -> None:
        self.tenant_id = validate_tenant_id(tenant_id)
        self.collection = validate_collection_name(collection)
        self._dir = assert_vector_access(self.tenant_id, "collections", self.collection)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "docs.jsonl"

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> int:
        if len(ids) != len(documents):
            raise ValueError("ids and documents length mismatch")
        metas = metadatas or [{} for _ in ids]
        if len(metas) != len(ids):
            raise ValueError("metadatas length mismatch")

        existing: dict[str, dict[str, Any]] = {}
        if self._path.is_file():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                existing[str(row["id"])] = row

        now = time.time()
        for i, doc_id, doc in zip(range(len(ids)), ids, documents):
            existing[str(doc_id)] = {
                "id": str(doc_id),
                "document": doc,
                "metadata": metas[i],
                "embedding": hash_embed(doc),
                "updated_at": now,
                "tenant_id": self.tenant_id,
            }

        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for row in existing.values():
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp.replace(self._path)
        return len(ids)

    def _iter_rows(self) -> Iterable[dict[str, Any]]:
        if not self._path.is_file():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)

    def query(self, *, text: str, top_k: int = 5) -> list[VectorHit]:
        q = hash_embed(text)
        scored: list[VectorHit] = []
        for row in self._iter_rows() or []:
            # Hard isolation: refuse foreign tenant_id if somehow present
            if row.get("tenant_id") and row["tenant_id"] != self.tenant_id:
                continue
            emb = row.get("embedding") or hash_embed(str(row.get("document") or ""))
            scored.append(
                VectorHit(
                    id=str(row["id"]),
                    score=cosine(q, emb),
                    document=str(row.get("document") or ""),
                    metadata=dict(row.get("metadata") or {}),
                )
            )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[: max(1, top_k)]

    def count(self) -> int:
        return sum(1 for _ in (self._iter_rows() or []))
