from app.repositories.graph_repository import GraphRepository
from app.retrieval.hybrid_retriever import hybrid_retrieve
from app.services.langchain_adapter import build_grounded_answer
from app.services.path_service import recommend_path


def query_graphrag(
    question: str,
    target_concept_id: str,
    mastered_concepts: list[str],
    repo: GraphRepository,
) -> dict:
    path_result = recommend_path(
        target_concept_id=target_concept_id,
        mastered_concepts=mastered_concepts,
        repo=repo,
    )

    path = path_result.get("path", [])
    evidence = path_result.get("evidence", [])
    explanation = path_result.get("explanation", "")
    has_cycle = bool(path_result.get("has_cycle", False))
    path_meta = path_result.get("meta", {})

    graph_ids = list(dict.fromkeys([*path, *evidence]))
    retrieval = hybrid_retrieve(question=question, repo=repo, graph_ids=graph_ids)
    hits = retrieval.get("hits", [])

    answer = build_grounded_answer(
        question=question,
        path=path,
        explanation=explanation,
        retrieval_hits=hits,
    )

    citations = [
        {
            "concept_id": hit.get("concept_id", ""),
            "kind": "concept",
            "score": float(hit.get("rerank_score") or hit.get("score") or 0.0),
            "source": hit.get("source", "unknown"),
        }
        for hit in hits
        if hit.get("concept_id")
    ]

    return {
        "answer": answer,
        "path": path,
        "evidence": evidence,
        "citations": citations,
        "meta": {
            "has_cycle": has_cycle,
            "truncated": bool(path_result.get("truncated", False)),
            "max_depth": int(path_result.get("max_depth", 0)),
            "planner_strategy": path_meta.get(
                "planner_strategy", "cached_graph_ancestor_closure"
            ),
            "dataset_hash": path_meta.get("dataset_hash"),
            "source": "path_service+hybrid_retrieval",
            "model": "template-grounded-answer",
            "retrieval_strategy": retrieval.get("retrieval_mode", "graph_only"),
            "vector_backend": retrieval.get("vector_backend", "unknown"),
            "embedding_model": retrieval.get("embedding_model", "unknown"),
            "embedding_degraded": bool(retrieval.get("embedding_degraded", False)),
            "embedding_degradation_reason": retrieval.get("embedding_degradation_reason"),
            "embedding_cache_status": retrieval.get("cache_status", "not_used"),
            "fusion": retrieval.get("fusion", "none"),
            "reranker": retrieval.get("reranker", "none"),
        },
    }
