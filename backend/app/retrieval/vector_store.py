from __future__ import annotations

import math
import re
from collections import defaultdict


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())


def _embed_text(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    for token in _tokenize(text):
        idx = hash(token) % dim
        vec[idx] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class VectorStore:
    """A lightweight vector retriever.

    The implementation uses hashing embeddings so it works without external
    services. It is suitable for demo-grade FAISS-like retrieval behavior.
    """

    def __init__(self, docs: list[dict], dim: int = 256) -> None:
        self._docs = docs
        self._dim = dim
        self._vectors = [_embed_text(doc.get("text", ""), dim=dim) for doc in docs]

    def search(self, query: str, top_k: int = 8) -> list[dict]:
        if not self._docs:
            return []

        qvec = _embed_text(query, dim=self._dim)
        scored = []
        for doc, vec in zip(self._docs, self._vectors):
            scored.append({
                "concept_id": doc.get("concept_id", ""),
                "text": doc.get("text", ""),
                "score": _dot(qvec, vec),
                "source": "vector",
            })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(1, top_k)]


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)

    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            if not doc_id:
                continue
            scores[doc_id] += 1.0 / (k + rank)

    merged = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return merged
