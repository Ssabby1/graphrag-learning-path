from app.services.path_service import recommend_path


class FakeGraphRepository:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        return self.payload


def test_recommend_path_when_target_mastered() -> None:
    repo = FakeGraphRepository(payload={"target_exists": True, "node_ids": [], "edges": []})

    result = recommend_path(
        target_concept_id="C3",
        mastered_concepts=["C1", "C3"],
        repo=repo,
    )

    assert result["path"] == []
    assert result["graph_nodes"] == []
    assert result["graph_edges"] == []
    assert "already in mastered_concepts" in result["evidence"][0]


def test_recommend_path_when_target_not_found() -> None:
    repo = FakeGraphRepository(
        payload={
            "target_exists": False,
            "target_concept_id": "NOPE",
            "node_ids": [],
            "edges": [],
        }
    )

    result = recommend_path(
        target_concept_id="NOPE",
        mastered_concepts=[],
        repo=repo,
    )

    assert result["path"] == []
    assert result["graph_nodes"] == []
    assert result["graph_edges"] == []
    assert "不存在" in result["explanation"]


def test_recommend_path_topological_order_and_mastered_filter() -> None:
    repo = FakeGraphRepository(
        payload={
            "target_exists": True,
            "target_concept_id": "C4",
            "node_ids": ["C1", "C2", "C3", "C4"],
            "edges": [("C1", "C2"), ("C2", "C4"), ("C3", "C4")],
        }
    )

    result = recommend_path(
        target_concept_id="C4",
        mastered_concepts=["C2"],
        repo=repo,
    )

    assert result["path"][-1] == "C4"
    assert "C2" not in result["path"]
    assert result["path"] == ["C1", "C3", "C4"]
    assert result["evidence"] == ["C1", "C3"]
    assert result["graph_nodes"] == ["C1", "C2", "C3", "C4"]
    assert result["graph_edges"] == [("C1", "C2"), ("C2", "C4"), ("C3", "C4")]
    assert result["explanation_source"] == "fallback"


def test_recommend_path_keeps_mastered_bridge_in_graph_context() -> None:
    repo = FakeGraphRepository(
        payload={
            "target_exists": True,
            "target_concept_id": "T",
            "node_ids": ["A", "M", "B", "T"],
            "edges": [("A", "M"), ("M", "B"), ("B", "T")],
        }
    )

    result = recommend_path(
        target_concept_id="T",
        mastered_concepts=["M"],
        repo=repo,
    )

    assert result["path"] == ["A", "B", "T"]
    assert "M" not in result["evidence"]
    assert result["graph_nodes"] == ["A", "M", "B", "T"]
    assert result["graph_edges"] == [("A", "M"), ("M", "B"), ("B", "T")]


def test_recommend_path_cycle_fallback_order() -> None:
    repo = FakeGraphRepository(
        payload={
            "target_exists": True,
            "target_concept_id": "C3",
            "node_ids": ["C1", "C2", "C3"],
            "edges": [("C1", "C2"), ("C2", "C1"), ("C2", "C3")],
        }
    )

    result = recommend_path(
        target_concept_id="C3",
        mastered_concepts=[],
        repo=repo,
    )

    assert sorted(result["path"]) == ["C1", "C2", "C3"]
    assert result["path"][-1] == "C3"
    assert sorted(result["graph_nodes"]) == ["C1", "C2", "C3"]
    assert sorted(result["graph_edges"]) == [("C1", "C2"), ("C2", "C1"), ("C2", "C3")]
    assert "环路" in result["explanation"]
    assert result["explanation_source"] == "fallback"
