from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.retrieval.concept_retriever import ConceptRetriever
from app.retrieval.corpus_builder import build_concept_documents
from app.retrieval.embedding_backend import get_embedding_backend
from app.retrieval.embedding_cache import EmbeddingCache


def detect_query_language(text: str) -> str:
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", text or ""))
    has_latin = bool(re.search(r"[A-Za-z]", text or ""))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    return "en"


def _labels(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("concept_id", "name", "name_en"):
        value = str(row.get(key) or "").strip()
        if value:
            values.append(value)
    for key in ("aliases", "alias", "aliases_en"):
        raw = row.get(key) or []
        if isinstance(raw, str):
            raw = raw.split("|")
        values.extend(str(item).strip() for item in raw if str(item).strip())
    name = str(row.get("name") or "").strip()
    if name.endswith("的分析"):
        values.append(f"分析{name.removesuffix('的分析')}")
    return list(dict.fromkeys(values))


def _exact_matches(question: str, corpus: list[dict[str, Any]]) -> list[tuple[str, int]]:
    lowered = question.lower()
    matches: list[tuple[str, int, int]] = []
    for row in corpus:
        concept_id = str(row.get("concept_id") or "").strip()
        occurrences = [
            (len(label), lowered.rfind(label.lower()))
            for label in _labels(row)
            if label.lower() in lowered
        ]
        if concept_id and occurrences:
            length, position = max(occurrences)
            matches.append((concept_id, length, position))
    goal_cues = list(re.finditer(r"(?:想学|学习|掌握|了解)\s*", lowered))
    if goal_cues:
        goal_start = goal_cues[-1].end()
        goal_matches = [item for item in matches if item[2] >= goal_start]
        if goal_matches:
            matches = goal_matches
    return [(item[0], item[1]) for item in sorted(matches, key=lambda item: (-item[1], -item[2], item[0]))]


def resolve_target(
    question: str,
    repo,
    top_k: int | None = None,
    response_language: str = "auto",
    *,
    embedding_backend=None,
    embedding_cache: EmbeddingCache | None = None,
    min_score: float | None = None,
    min_margin: float | None = None,
) -> dict[str, Any]:
    del response_language  # reserved for the answer generator; resolver reports query language only
    corpus = repo.get_concept_corpus(limit=2000)
    documents = build_concept_documents(corpus)
    requested_top_k = top_k or settings.target_resolver_top_k
    if embedding_backend is None:
        backend, degraded, degradation_reason = get_embedding_backend()
    else:
        backend, degraded, degradation_reason = embedding_backend, False, None
    threshold = settings.target_resolver_min_score if min_score is None else min_score
    margin_threshold = (
        settings.target_resolver_min_margin if min_margin is None else min_margin
    )
    vector_result = ConceptRetriever(backend, cache=embedding_cache or EmbeddingCache()).search(
        query=question,
        documents=documents,
        mode="vector_only",
        top_k_vector=max(requested_top_k, settings.retrieval_top_k_vector),
        top_k_final=requested_top_k,
    )
    vector_by_id = {hit["concept_id"]: hit for hit in vector_result["hits"]}
    exact = _exact_matches(question, corpus)
    ordered_ids = [item_id for item_id, _ in exact]
    ordered_ids.extend(
        hit["concept_id"] for hit in vector_result["hits"] if hit["concept_id"] not in ordered_ids
    )
    exact_ids = {item_id for item_id, _ in exact}
    candidates = []
    for rank, concept_id in enumerate(ordered_ids[:requested_top_k], start=1):
        vector_hit = vector_by_id.get(concept_id, {})
        exact_match = concept_id in exact_ids
        candidates.append(
            {
                "concept_id": concept_id,
                "score": 1.0 if exact_match else float(vector_hit.get("vector_score") or 0.0),
                "rank": rank,
                "source": "exact" if exact_match else "vector",
                "vector_score": vector_hit.get("vector_score"),
            }
        )
    top = candidates[0] if candidates else None
    vector_scores = [
        float(item["score"]) for item in candidates if item["source"] == "vector"
    ]
    score_margin = (
        vector_scores[0] - vector_scores[1]
        if len(vector_scores) >= 2
        else vector_scores[0] if vector_scores else None
    )
    ambiguous_exact = len(exact) > 1 and bool(
        re.search(r"比较|对比|区别|差异|\bcompare\b|\bdifference\b", question, re.IGNORECASE)
    )
    accepted = bool(
        top
        and not ambiguous_exact
        and (
            top["source"] == "exact"
            or (
                top["score"] >= threshold
                and score_margin is not None
                and score_margin >= margin_threshold
            )
        )
    )
    rejection_reason = None
    if not accepted:
        if top is None:
            rejection_reason = "no_candidate"
        elif ambiguous_exact:
            rejection_reason = "multiple_explicit_targets"
        else:
            rejection_reason = "score_or_margin_below_configured_threshold"
    return {
        "target_concept_id": top["concept_id"] if accepted and top else None,
        "candidates": candidates,
        "resolution_source": top["source"] if accepted and top else "rejected",
        "query_language": detect_query_language(question),
        "rejected": not accepted,
        "rejection_reason": rejection_reason,
        "resolver_meta": {
            "embedding_model": backend.model_id,
            "embedding_degraded": degraded,
            "embedding_degradation_reason": degradation_reason,
            "cache_status": vector_result["cache_status"],
            "min_score": threshold,
            "min_margin": margin_threshold,
            "score_margin": score_margin,
            "threshold_source": "stage2_directional_development_set",
        },
    }
