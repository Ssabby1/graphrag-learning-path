from __future__ import annotations

from typing import Any


EVIDENCE_PACK_VERSION = "1.0"


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    values = value.split("|") if isinstance(value, str) else value
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_evidence_pack(
    target_concept_id: str,
    path: list[str],
    retrieval_hits: list[dict[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    ordered_hits = sorted(
        retrieval_hits,
        key=lambda hit: (
            int(hit.get("rank") or 10**9),
            str(hit.get("evidence_id") or hit.get("id") or ""),
        ),
    )
    for hit in ordered_hits:
        metadata = dict(hit.get("metadata") or {})
        evidence_id = str(hit.get("evidence_id") or hit.get("id") or "").strip()
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        relation = str(metadata.get("relation_type") or "").strip().upper()
        from_id = str(metadata.get("from_concept_id") or "").strip()
        to_id = str(metadata.get("to_concept_id") or "").strip()
        from_name = str(metadata.get("from_name") or "").strip()
        to_name = str(metadata.get("to_name") or "").strip()
        evidence_text = str(metadata.get("evidence_text") or "").strip()
        reason = evidence_text or (
            f"后置知识点：{to_name or to_id}；前置知识点：{from_name or from_id}"
        )
        items.append(
            {
                "evidence_id": evidence_id,
                "evidence_type": (
                    "required_prerequisite"
                    if relation == "PREREQUISITE_OF"
                    else "supplemental_context"
                ),
                "from_concept": {"id": from_id, "name": from_name},
                "relation": relation,
                "to_concept": {"id": to_id, "name": to_name},
                "reason": reason,
                "source_chapters": _strings(metadata.get("source_chapters")),
                "source_images": _strings(metadata.get("source_images")),
                "confidence": _optional_float(metadata.get("confidence_max")),
                "confidence_type": "extraction_confidence",
                "verification_status": str(
                    metadata.get("verification_status") or "unreviewed"
                ),
                "retrieval": {
                    "graph_rank": hit.get("graph_rank"),
                    "vector_rank": hit.get("vector_rank"),
                    "graph_score": hit.get("graph_score"),
                    "vector_score": hit.get("vector_score"),
                    "rrf_score": hit.get("rrf_score"),
                    "rerank_score": hit.get("rerank_score"),
                    "source": str(hit.get("source") or "unknown"),
                },
            }
        )
    return {
        "evidence_pack_version": EVIDENCE_PACK_VERSION,
        "target_concept_id": target_concept_id,
        "path": list(path),
        "items": items,
    }
