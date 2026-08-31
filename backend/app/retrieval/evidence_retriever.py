from __future__ import annotations

from typing import Any, Iterable

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
        allowed_evidence_ids: Iterable[str] | None = None,
        top_k: int = 8,
    ) -> dict[str, Any]:
        allowed_sequence = (
            list(dict.fromkeys(item for item in allowed_evidence_ids if item))
            if allowed_evidence_ids is not None
            else None
        )
        if allowed_sequence == []:
            return {"hits": [], "cache_status": "not_used", "index_metadata": None}
        documents = build_evidence_documents(relation_rows)
        index = self.cache.get_or_build(documents, self.backend)
        query_vector = self.backend.embed_query(query)
        allowed = set(allowed_sequence) if allowed_sequence is not None else None
        graph_positions = {
            evidence_id: rank
            for rank, evidence_id in enumerate(allowed_sequence or [], start=1)
        }
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
                "source": "graph+vector" if allowed is not None else "vector",
                "graph_rank": graph_positions.get(evidence_id),
                "vector_rank": rank,
                "graph_score": (
                    1.0 / graph_positions[evidence_id]
                    if evidence_id in graph_positions
                    else None
                ),
                "vector_score": score,
                "rrf_score": None,
                "rerank_score": None,
                "score": score,
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
