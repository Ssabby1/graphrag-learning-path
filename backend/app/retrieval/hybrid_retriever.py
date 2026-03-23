from __future__ import annotations

from app.retrieval.reranker import rerank_hits
from app.retrieval.vector_store import VectorStore, rrf_fuse


def _as_text(record: dict) -> str:
    concept_id = record.get("concept_id", "")
    name = record.get("name", "")
    description = record.get("description", "")
    return f"{concept_id} {name} {description}".strip()


def hybrid_retrieve(
    question: str,
    repo,
    graph_ids: list[str],
    top_k_vector: int = 8,
    top_k_final: int = 6,
) -> dict:
    corpus = []
    if hasattr(repo, "get_concept_corpus"):
        corpus = repo.get_concept_corpus()

    docs = [{
        "concept_id": row.get("concept_id", ""),
        "text": _as_text(row),
    } for row in corpus]

    vector_store = VectorStore(docs)
    vector_hits = vector_store.search(question, top_k=top_k_vector)

    graph_rank = [item for item in graph_ids if item]
    vector_rank = [item.get("concept_id", "") for item in vector_hits]

    fused = rrf_fuse([graph_rank, vector_rank], k=60)
    fused_map = {concept_id: score for concept_id, score in fused}

    by_id = {doc.get("concept_id", ""): doc for doc in docs}
    merged_hits: list[dict] = []
    for concept_id, rrf_score in fused:
        text = by_id.get(concept_id, {}).get("text", concept_id)
        source = "graph+vector"
        if concept_id in graph_rank and concept_id not in vector_rank:
            source = "graph"
        elif concept_id in vector_rank and concept_id not in graph_rank:
            source = "vector"

        merged_hits.append({
            "concept_id": concept_id,
            "text": text,
            "score": rrf_score,
            "source": source,
        })

    reranked = rerank_hits(question=question, hits=merged_hits, top_k=top_k_final)
    return {
        "hits": reranked,
        "vector_backend": "hashing-fallback",
        "fusion": "rrf",
        "rrf_k": 60,
        "reranker": "token-overlap",
        "raw_rrf_scores": fused_map,
    }
