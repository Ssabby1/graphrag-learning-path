from __future__ import annotations

from typing import Any

from app.retrieval.corpus_builder import build_evidence_documents
from app.retrieval.embedding_cache import EmbeddingCache


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class EvidenceRetriever:
    """Vector retrieval over relationship documents, optionally graph-scoped."""

    def __init__(self, backend, cache: EmbeddingCache | None = None) -> None:
        self.backend = backend
        self.cache = cache or EmbeddingCache()

    def search(
        self,
        query: str,
        relation_rows: list[dict[str, Any]],
        allowed_evidence_ids: set[str] | None = None,
        top_k: int = 8,
    ) -> dict[str, Any]:
        documents = build_evidence_documents(relation_rows)
        index = self.cache.get_or_build(documents, self.backend)
        query_vector = self.backend.embed_query(query)
        allowed = allowed_evidence_ids
        scored = []
        for document, vector in zip(index.documents, index.vectors):
            evidence_id = document["id"]
            if allowed is not None and evidence_id not in allowed:
                continue
            scored.append((evidence_id, _dot(query_vector, vector), document))
        scored.sort(key=lambda item: (-item[1], item[0]))
        hits = [
            {
                "id": evidence_id,
                "evidence_id": evidence_id,
                "rank": rank,
                "source": "vector",
                "vector_rank": rank,
                "vector_score": score,
                "text": document["text"],
                "metadata": document["metadata"],
            }
            for rank, (evidence_id, score, document) in enumerate(scored[:top_k], start=1)
        ]
        return {
            "hits": hits,
            "cache_status": index.cache_status,
            "index_metadata": index.metadata,
        }
