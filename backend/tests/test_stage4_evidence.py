from __future__ import annotations

from app.evidence.citation_validator import validate_citation_ids
from app.evidence.pack_builder import build_evidence_pack
from app.retrieval.evidence_retriever import EvidenceRetriever


def _hit(evidence_id: str = "prereq:C1:C2") -> dict:
    return {
        "id": evidence_id,
        "evidence_id": evidence_id,
        "rank": 1,
        "source": "graph+vector",
        "graph_rank": 1,
        "vector_rank": 2,
        "graph_score": 1.0,
        "vector_score": 0.81,
        "rrf_score": None,
        "rerank_score": None,
        "metadata": {
            "from_concept_id": "C1",
            "from_name": "逻辑函数表达式",
            "to_concept_id": "C2",
            "to_name": "卡诺图构成",
            "relation_type": "PREREQUISITE_OF",
            "evidence_text": "学习卡诺图构成前需要理解逻辑函数表达式。",
            "source_chapters": ["第三章", "第一章", "第三章"],
            "source_images": "img-2|img-1",
            "confidence_max": "0.92",
            "verification_status": "unreviewed",
        },
    }


def test_evidence_pack_is_deterministic_traceable_and_deduplicated() -> None:
    pack = build_evidence_pack("C2", ["C1", "C2"], [_hit(), _hit()])

    assert pack["evidence_pack_version"] == "1.0"
    assert len(pack["items"]) == 1
    item = pack["items"][0]
    assert item["evidence_id"] == "prereq:C1:C2"
    assert item["evidence_type"] == "required_prerequisite"
    assert item["from_concept"] == {"id": "C1", "name": "逻辑函数表达式", "name_en": ""}
    assert item["to_concept"] == {"id": "C2", "name": "卡诺图构成", "name_en": ""}
    assert item["source_chapters"] == ["第一章", "第三章"]
    assert item["source_images"] == ["img-1", "img-2"]
    assert item["confidence"] == 0.92
    assert item["confidence_type"] == "extraction_confidence"
    assert item["retrieval"]["vector_score"] == 0.81


def test_citation_validator_removes_unknown_ids_and_reports_integrity() -> None:
    pack = build_evidence_pack("C2", ["C1", "C2"], [_hit()])
    result = validate_citation_ids(
        ["prereq:C1:C2", "invented:evidence", "prereq:C1:C2"], pack
    )

    assert result["valid_evidence_ids"] == ["prereq:C1:C2"]
    assert result["invalid_evidence_ids"] == ["invented:evidence"]
    assert result["integrity_numerator"] == 1
    assert result["integrity_denominator"] == 2
    assert result["integrity"] == 0.5


def test_empty_graph_scope_does_not_build_or_query_vector_index() -> None:
    class BackendThatMustNotRun:
        @property
        def dimension(self):
            raise AssertionError("embedding backend should not run")

    result = EvidenceRetriever(BackendThatMustNotRun()).search(
        "question", [_hit()["metadata"]], allowed_evidence_ids=[]
    )

    assert result == {"hits": [], "cache_status": "not_used", "index_metadata": None}
