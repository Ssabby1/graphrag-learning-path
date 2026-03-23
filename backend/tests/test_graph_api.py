from fastapi.testclient import TestClient

from app.api.deps import get_graph_repository
from app.core.errors import RepositoryUnavailableError
from app.main import app


class HealthyRepo:
    def get_graph_overview(self) -> dict:
        return {
            "course_count": 1,
            "chapter_count": 2,
            "concept_count": 3,
            "prerequisite_rel_count": 4,
        }

    def get_concept_detail(self, concept_id: str):
        return None

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        return {
            "target_exists": True,
            "target_concept_id": target_concept_id,
            "node_ids": [target_concept_id],
            "edges": [],
        }

    def get_concept_corpus(self, limit: int = 2000) -> list[dict]:
        return [
            {
                "concept_id": "C001",
                "name": "Binary Logic",
                "description": "Introduction to binary logic",
            },
            {
                "concept_id": "C002",
                "name": "Boolean Algebra",
                "description": "Boolean algebra basics",
            },
        ][:limit]

    def close(self) -> None:
        return None


class UnavailableRepo(HealthyRepo):
    def get_graph_overview(self) -> dict:
        raise RepositoryUnavailableError("Neo4j unavailable: test")

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        raise RepositoryUnavailableError("Neo4j unavailable: test")


def _override_with(repo):
    def _dep():
        try:
            yield repo
        finally:
            repo.close()

    return _dep


def test_graph_overview_returns_data() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.get("/graph/overview")

    assert response.status_code == 200
    assert response.json()["concept_count"] == 3
    app.dependency_overrides.clear()


def test_graph_overview_returns_503_when_repo_unavailable() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(UnavailableRepo())
    client = TestClient(app)

    response = client.get("/graph/overview")

    assert response.status_code == 503
    assert "Neo4j unavailable" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_concept_returns_404_when_not_found() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.get("/concept/NOT_EXISTS")

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_path_recommend_returns_503_when_repo_unavailable() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(UnavailableRepo())
    client = TestClient(app)

    response = client.post(
        "/path/recommend",
        json={"target_concept_id": "C1", "mastered_concepts": []},
    )

    assert response.status_code == 503
    assert "Neo4j unavailable" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_path_explain_returns_fallback_payload(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    client = TestClient(app)

    response = client.post(
        "/path/explain",
        json={
            "target_concept_id": "C1",
            "path": ["C1"],
            "evidence": [],
            "has_cycle": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["explanation"]
    assert payload["explanation_source"] == "fallback"


def test_planner_interpret_returns_structured_result(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.post(
        "/planner/interpret",
        json={"question": "I already know Binary and want to learn Boolean Algebra"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interpretation_source"] == "fallback"
    assert payload["matched_concepts"]
    app.dependency_overrides.clear()


def test_concept_corpus_returns_data() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.get("/concepts")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["concept_id"] == "C001"
    app.dependency_overrides.clear()
