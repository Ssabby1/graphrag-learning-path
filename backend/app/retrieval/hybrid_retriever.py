from __future__ import annotations

from app.core.config import settings
from app.retrieval.concept_retriever import ConceptRetriever
from app.retrieval.corpus_builder import build_concept_documents
from app.retrieval.embedding_backend import get_embedding_backend
from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.reranker import TokenOverlapReranker


def hybrid_retrieve(
    question: str,
    repo,
    graph_ids: list[str],
    top_k_vector: int | None = None,
    top_k_final: int | None = None,
    mode: str | None = None,
) -> dict:
    corpus = repo.get_concept_corpus() if hasattr(repo, "get_concept_corpus") else []
    documents = build_concept_documents(corpus)
    backend, degraded, degradation_reason = get_embedding_backend()
    selected_mode = mode or settings.retrieval_mode
    reranker = TokenOverlapReranker() if selected_mode == "hybrid_rrf_rerank" else None
    result = ConceptRetriever(
        backend, cache=EmbeddingCache(), reranker=reranker
    ).search(
        query=question,
        documents=documents,
        graph_ids=graph_ids,
        mode=selected_mode,
        top_k_vector=top_k_vector or settings.retrieval_top_k_vector,
        top_k_final=top_k_final or settings.retrieval_top_k_final,
        rrf_k=settings.retrieval_rrf_k,
    )
    return {
        **result,
        "retrieval_mode": selected_mode,
        "vector_backend": backend.model_id,
        "embedding_model": backend.model_id,
        "embedding_degraded": degraded,
        "embedding_degradation_reason": degradation_reason,
        "fusion": "rrf" if selected_mode.startswith("hybrid") else "none",
        "rrf_k": settings.retrieval_rrf_k if selected_mode.startswith("hybrid") else None,
        "reranker": reranker.model_id if reranker is not None else "none",
    }
