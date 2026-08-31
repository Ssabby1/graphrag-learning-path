from __future__ import annotations

from typing import Any

from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.fusion import reciprocal_rank_fusion


VALID_RETRIEVAL_MODES = {
    "graph_only",
    "vector_only",
    "hybrid_rrf",
    "hybrid_rrf_rerank",
}


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class ConceptRetriever:
    def __init__(self, backend, cache: EmbeddingCache | None = None, reranker=None) -> None:
        self.backend = backend
        self.cache = cache or EmbeddingCache()
        self.reranker = reranker

    def search(
        self,
        query: str,
        documents: list[dict[str, Any]],
        graph_ids: list[str] | None = None,
        mode: str = "hybrid_rrf",
        top_k_vector: int = 8,
        top_k_final: int = 6,
        rrf_k: int = 60,
    ) -> dict[str, Any]:
        if mode not in VALID_RETRIEVAL_MODES:
            raise ValueError(f"Unsupported retrieval mode: {mode}")
        graph_rank = list(dict.fromkeys(item for item in (graph_ids or []) if item))
        graph_positions = {item_id: rank for rank, item_id in enumerate(graph_rank, start=1)}
        by_id = {document["id"]: document for document in documents}

        if mode == "graph_only":
            hits = [
                self._hit(
                    item_id,
                    by_id,
                    graph_rank=rank,
                    graph_score=1.0 / rank,
                    source="graph",
                )
                for item_id, rank in graph_positions.items()
                if item_id in by_id
            ][:top_k_final]
            self._assign_ranks(hits)
            return {"hits": hits, "cache_status": "not_used", "index_metadata": None}

        index = self.cache.get_or_build(documents, self.backend)
        query_vector = self.backend.embed_query(query)
        if len(query_vector) != index.metadata["dimension"]:
            raise ValueError("Query embedding dimension does not match document index")
        scored = [
            (document["id"], _dot(query_vector, vector))
            for document, vector in zip(index.documents, index.vectors)
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))
        vector_top = scored[: max(1, top_k_vector)]
        vector_rank = [item_id for item_id, _ in vector_top]
        vector_positions = {item_id: rank for rank, item_id in enumerate(vector_rank, start=1)}
        vector_scores = dict(vector_top)

        if mode == "vector_only":
            hits = [
                self._hit(
                    item_id,
                    by_id,
                    vector_rank=vector_positions[item_id],
                    vector_score=score,
                    source="vector",
                )
                for item_id, score in vector_top[:top_k_final]
            ]
            self._assign_ranks(hits)
            return {
                "hits": hits,
                "cache_status": index.cache_status,
                "index_metadata": index.metadata,
            }

        fused = reciprocal_rank_fusion([graph_rank, vector_rank], k=rrf_k)
        hits = []
        for item_id, rrf_score in fused:
            if item_id not in by_id:
                continue
            in_graph = item_id in graph_positions
            in_vector = item_id in vector_positions
            source = "graph+vector" if in_graph and in_vector else "graph" if in_graph else "vector"
            hits.append(
                self._hit(
                    item_id,
                    by_id,
                    graph_rank=graph_positions.get(item_id),
                    vector_rank=vector_positions.get(item_id),
                    graph_score=(1.0 / graph_positions[item_id]) if in_graph else None,
                    vector_score=vector_scores.get(item_id),
                    rrf_score=rrf_score,
                    source=source,
                )
            )

        if mode == "hybrid_rrf_rerank":
            if self.reranker is None:
                raise ValueError("hybrid_rrf_rerank requires a configured reranker")
            hits = self.reranker.rerank(query, hits, top_k_final)
        else:
            hits = hits[:top_k_final]
            self._assign_ranks(hits)
        return {
            "hits": hits,
            "cache_status": index.cache_status,
            "index_metadata": index.metadata,
        }

    @staticmethod
    def _assign_ranks(hits: list[dict[str, Any]]) -> None:
        for rank, hit in enumerate(hits, start=1):
            hit["rank"] = rank

    @staticmethod
    def _hit(
        item_id: str,
        by_id: dict[str, dict[str, Any]],
        *,
        graph_rank: int | None = None,
        vector_rank: int | None = None,
        graph_score: float | None = None,
        vector_score: float | None = None,
        rrf_score: float | None = None,
        rerank_score: float | None = None,
        source: str,
    ) -> dict[str, Any]:
        document = by_id[item_id]
        return {
            "id": item_id,
            "concept_id": document.get("concept_id", item_id),
            "text": document.get("text", ""),
            "metadata": document.get("metadata", {}),
            "rank": None,
            "source": source,
            "graph_rank": graph_rank,
            "vector_rank": vector_rank,
            "graph_score": graph_score,
            "vector_score": vector_score,
            "rrf_score": rrf_score,
            "rerank_score": rerank_score,
            "score": rerank_score if rerank_score is not None else rrf_score if rrf_score is not None else vector_score if vector_score is not None else graph_score,
        }
