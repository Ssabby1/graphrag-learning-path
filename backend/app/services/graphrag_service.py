from app.core.config import settings
from app.evidence.citation_validator import validate_citation_ids
from app.evidence.pack_builder import build_evidence_pack
from app.repositories.graph_repository import GraphRepository
from app.retrieval.corpus_builder import evidence_id
from app.retrieval.embedding_backend import get_embedding_backend
from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.evidence_retriever import EvidenceRetriever
from app.services.answer_generator import StructuredAnswerGenerator
from app.services.path_service import recommend_path


def query_graphrag(
    question: str,
    target_concept_id: str,
    mastered_concepts: list[str],
    repo: GraphRepository,
    response_language: str = "auto",
    answer_generator: StructuredAnswerGenerator | None = None,
) -> dict:
    path_result = recommend_path(
        target_concept_id=target_concept_id,
        mastered_concepts=mastered_concepts,
        repo=repo,
    )
    path = path_result.get("path", [])
    path_meta = path_result.get("meta", {})
    path_nodes = set(path)
    allowed_evidence_ids = [
        evidence_id("PREREQUISITE_OF", source, target)
        for source, target in path_result.get("graph_edges", [])
        if source in path_nodes and target in path_nodes
    ]

    backend = None
    embedding_degraded = False
    embedding_degradation_reason = None
    if allowed_evidence_ids:
        backend, embedding_degraded, embedding_degradation_reason = get_embedding_backend()
        relation_rows = repo.get_relation_corpus(("PREREQUISITE_OF",))
        retrieval = EvidenceRetriever(backend, EmbeddingCache()).search(
            query=question,
            relation_rows=relation_rows,
            allowed_evidence_ids=allowed_evidence_ids,
            top_k=settings.evidence_top_k,
        )
    else:
        retrieval = {"hits": [], "cache_status": "not_used", "index_metadata": None}
    hits = retrieval.get("hits", [])
    evidence_pack = build_evidence_pack(target_concept_id, path, hits)

    answer_result = (answer_generator or StructuredAnswerGenerator()).generate(
        question=question,
        target_concept_id=target_concept_id,
        path=path,
        evidence_pack=evidence_pack,
        response_language=response_language,
    )
    validation = validate_citation_ids(
        answer_result["cited_evidence_ids"], evidence_pack
    )
    item_by_id = {
        item["evidence_id"]: item for item in evidence_pack.get("items", [])
    }
    hit_by_id = {hit["evidence_id"]: hit for hit in hits}
    citations = []
    for evidence_id_value in validation["valid_evidence_ids"]:
        item = item_by_id[evidence_id_value]
        hit = hit_by_id.get(evidence_id_value, {})
        citations.append(
            {
                "evidence_id": evidence_id_value,
                "concept_id": item["to_concept"]["id"] or None,
                "kind": "relationship",
                "score": hit.get("score"),
                "source": hit.get("source", "graph"),
            }
        )

    pack_item_count = len(evidence_pack.get("items", []))
    citation_completeness = (
        len(validation["valid_evidence_ids"]) / pack_item_count
        if pack_item_count
        else 1.0
    )
    return {
        "answer": answer_result["answer"],
        "cited_evidence_ids": validation["valid_evidence_ids"],
        "answer_source": answer_result["answer_source"],
        "answer_language": answer_result["answer_language"],
        "path": path,
        "evidence": path_result.get("evidence", []),
        "evidence_pack": evidence_pack,
        "citations": citations,
        "meta": {
            "has_cycle": bool(path_result.get("has_cycle", False)),
            "truncated": bool(path_result.get("truncated", False)),
            "max_depth": int(path_result.get("max_depth", 0)),
            "planner_strategy": path_meta.get(
                "planner_strategy", "cached_graph_ancestor_closure"
            ),
            "dataset_hash": path_meta.get("dataset_hash"),
            "source": "path_service+relationship_evidence_retrieval",
            "model": answer_result["generation_model"],
            "retrieval_strategy": "graph_scoped_vector",
            "vector_backend": backend.model_id if backend is not None else "not_used",
            "embedding_model": backend.model_id if backend is not None else "not_used",
            "embedding_degraded": embedding_degraded,
            "embedding_degradation_reason": embedding_degradation_reason,
            "embedding_cache_status": retrieval.get("cache_status", "not_used"),
            "fusion": "none",
            "reranker": "none",
            "reranker_degraded": False,
            "reranker_degradation_reason": None,
            "evidence_retrieval_strategy": "graph_scoped_vector",
            "evidence_count": len(evidence_pack.get("items", [])),
            "citation_integrity": validation["integrity"],
            "invalid_evidence_id_count": validation["invalid_count"],
            "answer_source": answer_result["answer_source"],
            "answer_language": answer_result["answer_language"],
            "generation_model": answer_result["generation_model"],
            "generation_latency_ms": answer_result["generation_latency_ms"],
            "structured_output_success": answer_result[
                "structured_output_success"
            ],
            "fallback_reason": answer_result["fallback_reason"],
            "discarded_invalid_citation_count": answer_result[
                "discarded_invalid_citation_count"
            ],
            "citation_completeness": citation_completeness,
        },
    }
