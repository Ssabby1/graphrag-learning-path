from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.errors import TargetConceptNotFoundError
from app.evidence.citation_validator import validate_citation_ids
from app.evidence.pack_builder import build_evidence_pack
from app.repositories.graph_repository import GraphRepository
from app.retrieval.corpus_builder import build_evidence_documents, evidence_id
from app.retrieval.embedding_backend import get_embedding_backend
from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.evidence_retriever import EvidenceRetriever
from app.services.answer_generator import StructuredAnswerGenerator, resolve_answer_language
from app.services.path_service import recommend_path


def _empty_pack(target_concept_id: str, path: list[str]) -> dict[str, Any]:
    return build_evidence_pack(target_concept_id, path, [])


def _full_graph_hits(
    relation_rows: list[dict[str, Any]], allowed_evidence_ids: list[str]
) -> list[dict[str, Any]]:
    documents = {
        document["evidence_id"]: document
        for document in build_evidence_documents(relation_rows)
    }
    hits = []
    for rank, evidence_id_value in enumerate(allowed_evidence_ids, start=1):
        document = documents.get(evidence_id_value)
        if document is None:
            continue
        hits.append(
            {
                "id": evidence_id_value,
                "evidence_id": evidence_id_value,
                "rank": rank,
                "source": "graph",
                "graph_rank": rank,
                "vector_rank": None,
                "graph_score": 1.0 / rank,
                "vector_score": None,
                "rrf_score": None,
                "rerank_score": None,
                "score": None,
                "text": document["text"],
                "metadata": document["metadata"],
            }
        )
    return hits


def _path_coverage(
    allowed_evidence_ids: list[str], full_evidence_pack: dict[str, Any]
) -> dict[str, int | float]:
    expected = set(allowed_evidence_ids)
    available = {
        item["evidence_id"] for item in full_evidence_pack.get("items", [])
    }
    covered = len(expected & available)
    total = len(expected)
    return {
        "path_edge_count": total,
        "path_edge_evidence_count": covered,
        "missing_path_evidence_count": len(expected - available),
        "path_edge_evidence_coverage": covered / total if total else 1.0,
    }


def _status_answer(status: str, target_concept_id: str, language: str) -> str:
    messages = {
        "already_mastered": {
            "zh": f"目标知识点 {target_concept_id} 已经掌握，无需生成额外学习路径。",
            "en": f"The target concept {target_concept_id} is already mastered. No additional learning path is required.",
        },
        "truncated": {
            "zh": "图安全限制已触发，当前路径可能不完整，因此没有生成正常学习建议。",
            "en": "The graph safety limit was reached, so this path may be incomplete. No normal learning answer was generated.",
        },
        "cycle": {
            "zh": "先修图中存在环路，无法生成安全的学习顺序；请先检查图谱关系。",
            "en": "The prerequisite graph contains a cycle, so a safe learning order cannot be generated. Review the graph relationships first.",
        },
    }
    return messages[status][language]


def _special_status_response(
    *,
    status: str,
    question: str,
    response_language: str,
    target_concept_id: str,
    path_result: dict[str, Any],
    full_evidence_pack: dict[str, Any],
    coverage: dict[str, int | float],
) -> dict[str, Any]:
    language = resolve_answer_language(question, response_language)
    empty_answer_pack = _empty_pack(target_concept_id, path_result.get("path", []))
    path_meta = path_result.get("meta", {})
    return {
        "status": status,
        "answer": _status_answer(status, target_concept_id, language),
        "cited_evidence_ids": [],
        "answer_source": "system",
        "answer_language": language,
        "path": path_result.get("path", []),
        "evidence": path_result.get("evidence", []),
        "full_evidence_pack": full_evidence_pack,
        "selected_answer_evidence": empty_answer_pack,
        "citations": [],
        "meta": {
            "has_cycle": bool(path_result.get("has_cycle", False)),
            "truncated": bool(path_result.get("truncated", False)),
            "max_depth": int(path_result.get("max_depth", 0)),
            "planner_strategy": path_meta.get(
                "planner_strategy", "cached_graph_ancestor_closure"
            ),
            "dataset_hash": path_meta.get("dataset_hash"),
            "source": "path_service",
            "model": "not_used",
            "retrieval_strategy": "graph_only",
            "vector_backend": "not_used",
            "embedding_model": "not_used",
            "embedding_degraded": False,
            "embedding_degradation_reason": None,
            "embedding_cache_status": "not_used",
            "fusion": "none",
            "reranker": "none",
            "reranker_degraded": False,
            "reranker_degradation_reason": None,
            "evidence_retrieval_strategy": "full_graph_scope",
            "evidence_count": len(full_evidence_pack.get("items", [])),
            "answer_evidence_count": 0,
            **coverage,
            "citation_integrity": 1.0,
            "invalid_evidence_id_count": 0,
            "answer_source": "system",
            "answer_language": language,
            "generation_model": "not_used",
            "generation_latency_ms": 0.0,
            "structured_output_success": False,
            "llm_structured_output_success": False,
            "response_schema_valid": True,
            "fallback_reason": f"path_status:{status}",
            "discarded_invalid_citation_count": 0,
            "citation_completeness": 1.0,
            "answer_evidence_citation_coverage": 1.0,
        },
    }


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
    status = path_result.get("status", "ok")
    if status == "not_found":
        raise TargetConceptNotFoundError(target_concept_id)

    path = path_result.get("path", [])
    path_nodes = set(path)
    allowed_evidence_ids = list(
        dict.fromkeys(
            evidence_id("PREREQUISITE_OF", source, target)
            for source, target in path_result.get("graph_edges", [])
            if source in path_nodes and target in path_nodes
        )
    )

    if status == "already_mastered":
        full_evidence_pack = _empty_pack(target_concept_id, path)
        return _special_status_response(
            status=status,
            question=question,
            response_language=response_language,
            target_concept_id=target_concept_id,
            path_result=path_result,
            full_evidence_pack=full_evidence_pack,
            coverage=_path_coverage([], full_evidence_pack),
        )

    relation_rows = repo.get_relation_corpus(("PREREQUISITE_OF",))
    full_hits = _full_graph_hits(relation_rows, allowed_evidence_ids)
    full_evidence_pack = build_evidence_pack(target_concept_id, path, full_hits)
    coverage = _path_coverage(allowed_evidence_ids, full_evidence_pack)

    if status in {"truncated", "cycle"}:
        return _special_status_response(
            status=status,
            question=question,
            response_language=response_language,
            target_concept_id=target_concept_id,
            path_result=path_result,
            full_evidence_pack=full_evidence_pack,
            coverage=coverage,
        )

    backend = None
    embedding_degraded = False
    embedding_degradation_reason = None
    if allowed_evidence_ids:
        backend, embedding_degraded, embedding_degradation_reason = get_embedding_backend()
        retrieval = EvidenceRetriever(backend, EmbeddingCache()).search(
            query=question,
            relation_rows=relation_rows,
            allowed_evidence_ids=allowed_evidence_ids,
            top_k=settings.evidence_top_k,
        )
    else:
        retrieval = {"hits": [], "cache_status": "not_used", "index_metadata": None}
    hits = retrieval.get("hits", [])
    selected_answer_evidence = build_evidence_pack(target_concept_id, path, hits)

    answer_result = (answer_generator or StructuredAnswerGenerator()).generate(
        question=question,
        target_concept_id=target_concept_id,
        path=path,
        evidence_pack=selected_answer_evidence,
        response_language=response_language,
    )
    validation = validate_citation_ids(
        answer_result["cited_evidence_ids"], selected_answer_evidence
    )
    item_by_id = {
        item["evidence_id"]: item
        for item in selected_answer_evidence.get("items", [])
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

    answer_item_count = len(selected_answer_evidence.get("items", []))
    answer_evidence_citation_coverage = (
        len(validation["valid_evidence_ids"]) / answer_item_count
        if answer_item_count
        else 1.0
    )
    path_meta = path_result.get("meta", {})
    return {
        "status": "ok",
        "answer": answer_result["answer"],
        "cited_evidence_ids": validation["valid_evidence_ids"],
        "answer_source": answer_result["answer_source"],
        "answer_language": answer_result["answer_language"],
        "path": path,
        "evidence": path_result.get("evidence", []),
        "full_evidence_pack": full_evidence_pack,
        "selected_answer_evidence": selected_answer_evidence,
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
            "evidence_retrieval_strategy": "full_graph+selected_vector",
            "evidence_count": len(full_evidence_pack.get("items", [])),
            "answer_evidence_count": answer_item_count,
            **coverage,
            "citation_integrity": validation["integrity"],
            "invalid_evidence_id_count": validation["invalid_count"],
            "answer_source": answer_result["answer_source"],
            "answer_language": answer_result["answer_language"],
            "generation_model": answer_result["generation_model"],
            "generation_latency_ms": answer_result["generation_latency_ms"],
            "structured_output_success": answer_result["structured_output_success"],
            "llm_structured_output_success": answer_result[
                "llm_structured_output_success"
            ],
            "response_schema_valid": answer_result["response_schema_valid"],
            "fallback_reason": answer_result["fallback_reason"],
            "discarded_invalid_citation_count": answer_result[
                "discarded_invalid_citation_count"
            ],
            "citation_completeness": answer_evidence_citation_coverage,
            "answer_evidence_citation_coverage": answer_evidence_citation_coverage,
        },
    }
