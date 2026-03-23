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
    assert payload["meta"]["retrieval_strategy"] == "graph+vector+rrf+rerank"
    assert payload["meta"]["model"] == "template-grounded-answer"
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
