from __future__ import annotations

from pathlib import Path

from app.repositories.csv_graph_repository import CsvGraphRepository
from app.services.graphrag_service import query_graphrag

ROOT = Path(__file__).resolve().parents[2]


class PublicSampleRepository(CsvGraphRepository):
    def __init__(self) -> None:
        super().__init__(
            ROOT / "data/seed/concepts.csv",
            ROOT / "data/seed/relations.csv",
        )


def test_public_sample_is_bilingual_curated_and_connected() -> None:
    repo = PublicSampleRepository()
    assert 10 <= len(repo.concepts) <= 20
    assert all(row["name"] and row["name_en"] and row["description"] and row["description_en"] for row in repo.concepts)
    assert all(row["verification_status"] == "public_sample_curated" for row in repo.relations)
    closure = repo.get_prerequisite_subgraph("c_006")
    assert closure["target_exists"] is True
    assert closure["has_cycle"] is False
    assert closure["node_ids"] == ["c_001", "c_002", "c_003", "c_004", "c_005", "c_006"]


def test_cross_language_public_sample_runs_full_graphrag_chain(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", str(tmp_path))
    result = query_graphrag(
        question="What should I learn before studying Karnaugh maps?",
        target_concept_id="c_006", mastered_concepts=[], repo=PublicSampleRepository(),
        response_language="en",
    )
    assert result["path"][-1] == "c_006"
    assert result["answer_language"] == "en"
    assert result["answer_source"] == "fallback"
    assert result["status"] == "ok"
    assert result["full_evidence_pack"]["items"]
    assert result["selected_answer_evidence"]["items"]
    assert result["meta"]["path_edge_evidence_coverage"] == 1.0
    assert result["meta"]["citation_integrity"] == 1.0
    assert result["meta"]["invalid_evidence_id_count"] == 0
    assert set(result["cited_evidence_ids"]) <= {item["evidence_id"] for item in result["selected_answer_evidence"]["items"]}


def test_cross_platform_entrypoints_exist() -> None:
    for name in ("setup.sh", "start-dev.sh", "stop-dev.sh", "setup.ps1", "start-dev.ps1", "stop-dev.ps1", "compose.yaml"):
        assert (ROOT / name).exists()
