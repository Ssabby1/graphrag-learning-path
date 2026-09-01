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


class MissingTargetRepo(HealthyRepo):
    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        return {"target_exists": False, "node_ids": [], "edges": []}

    def get_relation_corpus(self, relation_types=("PREREQUISITE_OF", "RELATED_TO")) -> list[dict]:
        raise AssertionError("not-found targets must stop before evidence retrieval")


class TruncatedRepo(HealthyRepo):
    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        payload = super().get_prerequisite_subgraph(target_concept_id)
        return {**payload, "truncated": True, "omitted_node_count": 2}


class CycleRepo(HealthyRepo):
    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        return {
            "target_exists": True,
            "target_concept_id": target_concept_id,
            "node_ids": ["C1", "C2", target_concept_id],
            "edges": [("C1", "C2"), ("C2", "C1"), ("C2", target_concept_id)],
            "has_cycle": True,
        }


class LongPathRepo(HealthyRepo):
    @staticmethod
    def _graph() -> tuple[list[str], list[tuple[str, str]]]:
        nodes = [f"C{index:03d}" for index in range(1, 43)]
        edges = list(zip(nodes, nodes[1:]))
        for source_index, source in enumerate(nodes):
            for target in nodes[source_index + 2 :]:
                edge = (source, target)
                if edge not in edges:
                    edges.append(edge)
                if len(edges) == 107:
                    return nodes, edges
        raise AssertionError("test graph did not reach 107 edges")

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        nodes, edges = self._graph()
        return {
            "target_exists": True,
            "target_concept_id": target_concept_id,
            "node_ids": nodes,
            "edges": edges,
        }

    def get_relation_corpus(self, relation_types=("PREREQUISITE_OF", "RELATED_TO")) -> list[dict]:
        rows = []
        _, edges = self._graph()
        for source, target in edges:
            rows.append(
                {
                    "from_concept_id": source,
                    "from_name": source,
                    "to_concept_id": target,
                    "to_name": target,
                    "relation_type": "PREREQUISITE_OF",
                    "evidence_text": f"{source} supports {target}.",
                    "source_chapters": ["Test"],
                    "source_images": [],
                    "confidence_max": 1.0,
                    "verification_status": "test_verified",
                }
            )
        return rows


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
    assert payload["status"] == "ok"
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
    assert payload["meta"]["answer_evidence_citation_coverage"] == 1.0
    assert payload["meta"]["path_edge_evidence_coverage"] == 1.0
    assert payload["full_evidence_pack"]["evidence_pack_version"] == "1.0"
    pack_ids = {item["evidence_id"] for item in payload["selected_answer_evidence"]["items"]}
    assert pack_ids
    assert {citation["evidence_id"] for citation in payload["citations"]} <= pack_ids
    assert all(citation["kind"] == "relationship" for citation in payload["citations"])
    assert payload["meta"]["embedding_model"]
    assert payload["meta"]["model"] == "deterministic-evidence-fallback-v1"
    assert payload["answer_source"] == "fallback"
    assert payload["answer_language"] == "en"
    assert payload["cited_evidence_ids"]
    assert "Question:" not in payload["answer"]
    assert "Evidence relationships:" not in payload["answer"]
    assert payload["meta"]["truncated"] is False
    assert payload["meta"]["max_depth"] == 2
    assert payload["path"][-1] == "C3"
    app.dependency_overrides.clear()


def test_graphrag_query_returns_404_when_target_not_found() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(MissingTargetRepo())
    client = TestClient(app)

    response = client.post(
        "/graphrag/query",
        json={"question": "Explain it", "target_concept_id": "DOES_NOT_EXIST"},
    )

    assert response.status_code == 404
    assert "DOES_NOT_EXIST" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_graphrag_query_returns_mastered_status_without_normal_answer() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.post(
        "/graphrag/query",
        json={
            "question": "How should I learn C3?",
            "target_concept_id": "C3",
            "mastered_concepts": ["C3"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "already_mastered"
    assert payload["path"] == []
    assert payload["answer_source"] == "system"
    assert "already mastered" in payload["answer"]
    assert payload["full_evidence_pack"]["items"] == []
    assert payload["selected_answer_evidence"]["items"] == []
    app.dependency_overrides.clear()


def test_long_path_keeps_full_evidence_while_bounding_answer_context() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(LongPathRepo())
    client = TestClient(app)

    response = client.post(
        "/graphrag/query",
        json={"question": "How should I learn C042?", "target_concept_id": "C042"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["path"]) == 42
    assert len(payload["full_evidence_pack"]["items"]) == 107
    assert len(payload["selected_answer_evidence"]["items"]) == 8
    assert payload["meta"]["path_edge_count"] == 107
    assert payload["meta"]["path_edge_evidence_count"] == 107
    assert payload["meta"]["missing_path_evidence_count"] == 0
    assert payload["meta"]["path_edge_evidence_coverage"] == 1.0
    assert payload["meta"]["answer_evidence_citation_coverage"] == 1.0
    app.dependency_overrides.clear()


def test_unsafe_graph_statuses_do_not_generate_normal_answers() -> None:
    client = TestClient(app)
    for repo, expected_status in (
        (TruncatedRepo(), "truncated"),
        (CycleRepo(), "cycle"),
    ):
        app.dependency_overrides[get_graph_repository] = _override_with(repo)
        response = client.post(
            "/graphrag/query",
            json={"question": "How should I learn C3?", "target_concept_id": "C3"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == expected_status
        assert payload["answer_source"] == "system"
        assert payload["selected_answer_evidence"]["items"] == []
        assert payload["meta"]["generation_model"] == "not_used"
        assert payload["meta"]["llm_structured_output_success"] is False
        assert payload["meta"]["fallback_reason"] == f"path_status:{expected_status}"
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


def test_graphrag_query_honors_explicit_response_language() -> None:
    app.dependency_overrides[get_graph_repository] = _override_with(HealthyRepo())
    client = TestClient(app)

    response = client.post(
        "/graphrag/query",
        json={
            "question": "How should I learn C3?",
            "target_concept_id": "C3",
            "mastered_concepts": [],
            "response_language": "zh",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer_language"] == "zh"
    assert "建议按顺序学习" in response.json()["answer"]
    app.dependency_overrides.clear()
