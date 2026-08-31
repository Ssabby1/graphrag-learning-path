from fastapi.testclient import TestClient

from app.api.deps import get_graph_repository
from app.core.errors import RepositoryUnavailableError
from app.main import app


class HealthyRepo:
    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        return {
            "target_exists": True,
            "target_concept_id": target_concept_id,
            "node_ids": ["C1", "C2", target_concept_id],
            "edges": [("C1", "C2"), ("C2", target_concept_id)],
        }

    def get_concept_corpus(self) -> list[dict]:
        return [
            {"concept_id": "C1", "name": "Binary", "description": "binary basics"},
            {"concept_id": "C2", "name": "Logic Gate", "description": "gate design"},
            {"concept_id": "C3", "name": "Combinational", "description": "combinational circuit"},
        ]

    def get_relation_corpus(self, relation_types=("PREREQUISITE_OF", "RELATED_TO")) -> list[dict]:
        rows = [
            {
                "from_concept_id": "C1",
                "from_name": "Binary",
                "to_concept_id": "C2",
                "to_name": "Logic Gate",
                "relation_type": "PREREQUISITE_OF",
                "evidence_text": "Binary supports logic gates.",
                "source_chapters": ["Chapter 1"],
                "source_images": ["img-1"],
                "confidence_max": 0.9,
                "verification_status": "unreviewed",
            },
            {
                "from_concept_id": "C2",
                "from_name": "Logic Gate",
                "to_concept_id": "C3",
                "to_name": "Combinational",
                "relation_type": "PREREQUISITE_OF",
                "evidence_text": "Logic gates support combinational circuits.",
                "source_chapters": ["Chapter 2"],
                "source_images": ["img-2"],
                "confidence_max": 0.95,
                "verification_status": "unreviewed",
            },
        ]
        return [row for row in rows if row["relation_type"] in relation_types]

    def close(self) -> None:
        return None


class UnavailableRepo(HealthyRepo):
    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        raise RepositoryUnavailableError("Neo4j unavailable: test")


def _override_with(repo):
    def _dep():
        try:
            yield repo
        finally:
            repo.close()

    return _dep


def test_graphrag_query_returns_contract() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.post(
        "/graphrag/query",
        json={
            "question": "How should I learn C3?",
            "target_concept_id": "C3",
            "mastered_concepts": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "answer" in payload
    assert "path" in payload
    assert "evidence" in payload
    assert "citations" in payload
    assert "meta" in payload
    assert payload["path"][-1] == "C3"
    assert payload["meta"]["retrieval_strategy"] == "graph_scoped_vector"
    assert payload["meta"]["reranker"] == "none"
    assert payload["meta"]["reranker_degraded"] is False
    assert payload["meta"]["citation_integrity"] == 1.0
    assert payload["meta"]["invalid_evidence_id_count"] == 0
    assert payload["evidence_pack"]["evidence_pack_version"] == "1.0"
    pack_ids = {item["evidence_id"] for item in payload["evidence_pack"]["items"]}
    assert pack_ids
    assert {citation["evidence_id"] for citation in payload["citations"]} <= pack_ids
    assert all(citation["kind"] == "relationship" for citation in payload["citations"])
    assert payload["meta"]["embedding_model"]
    assert payload["meta"]["model"] == "template-grounded-answer"
    assert payload["meta"]["truncated"] is False
    assert payload["meta"]["max_depth"] == 2
    assert payload["path"][-1] == "C3"
    app.dependency_overrides.clear()


def test_graphrag_query_returns_503_when_repo_unavailable() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(UnavailableRepo())
    client = TestClient(app)

    response = client.post(
        "/graphrag/query",
        json={
            "question": "How should I learn C3?",
            "target_concept_id": "C3",
            "mastered_concepts": [],
        },
    )

    assert response.status_code == 503
    assert "Neo4j unavailable" in response.json()["detail"]
    app.dependency_overrides.clear()
