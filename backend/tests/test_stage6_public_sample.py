from __future__ import annotations

from pathlib import Path

from app.graph.graph_snapshot import GraphSnapshot
from app.graph.prerequisite_index import PrerequisiteGraphIndex
from app.services.graphrag_service import query_graphrag
from scripts.import_data import load_concepts, load_relations

ROOT = Path(__file__).resolve().parents[2]


class PublicSampleRepository:
    def __init__(self) -> None:
        self.concepts = load_concepts(ROOT / "data/seed/concepts.csv")
        self.relations = load_relations(ROOT / "data/seed/relations.csv")
        self.snapshot = GraphSnapshot.build(
            [row["concept_id"] for row in self.concepts],
            [(row["from_concept_id"], row["to_concept_id"]) for row in self.relations],
        )

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        closure = PrerequisiteGraphIndex(self.snapshot).closure(
            target=target_concept_id, max_nodes=100, max_edges=200
        )
        return {
            "target_exists": closure.target_exists, "target_concept_id": target_concept_id,
            "node_ids": list(closure.node_ids), "edges": list(closure.edges),
            "has_cycle": closure.has_cycle, "truncated": closure.truncated,
            "max_depth": closure.max_depth, "dataset_hash": closure.content_hash,
            "planner_strategy": "cached_graph_ancestor_closure",
        }

    def get_relation_corpus(self, relation_types=("PREREQUISITE_OF",)) -> list[dict]:
        names = {row["concept_id"]: row["name"] for row in self.concepts}
        return [{**row, "from_name": names[row["from_concept_id"]], "to_name": names[row["to_concept_id"]], "source_chapters": ["Public Sample"]} for row in self.relations if row["relation_type"] in relation_types]


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
    assert result["evidence_pack"]["items"]
    assert result["meta"]["citation_integrity"] == 1.0
    assert result["meta"]["invalid_evidence_id_count"] == 0
    assert set(result["cited_evidence_ids"]) <= {item["evidence_id"] for item in result["evidence_pack"]["items"]}


def test_cross_platform_entrypoints_exist() -> None:
    for name in ("setup.sh", "start-dev.sh", "stop-dev.sh", "setup.ps1", "start-dev.ps1", "stop-dev.ps1", "compose.yaml"):
        assert (ROOT / name).exists()
