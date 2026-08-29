from app.services.planner_service import interpret_learning_request


class FakeGraphRepository:
    def get_concept_corpus(self, limit: int = 2000) -> list[dict]:
        return [
            {"concept_id": "C1", "name": "Binary", "description": "binary basics"},
            {"concept_id": "C2", "name": "Logic Gate", "description": "gate design"},
            {"concept_id": "C3", "name": "Boolean Algebra", "description": "boolean algebra basics"},
        ][:limit]


def test_interpret_learning_request_fallback_extracts_target_and_mastered(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    repo = FakeGraphRepository()

    result = interpret_learning_request("我已经学过 Binary，现在想学 Boolean Algebra", repo)

    assert result["target_concept_id"] == "C3"
    assert result["mastered_concepts"] == ["C1"]
    assert result["interpretation_source"] == "fallback"


def test_interpret_learning_request_prefers_more_specific_target_match(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)

    class OverlapGraphRepository:
        def get_concept_corpus(self, limit: int = 2000) -> list[dict]:
            return [
                {"concept_id": "C1", "name": "逻辑函数", "description": ""},
                {"concept_id": "C2", "name": "逻辑函数化简", "description": ""},
                {"concept_id": "C3", "name": "带无关项的逻辑函数化简", "description": ""},
            ][:limit]

    result = interpret_learning_request("如果我想学习带无关项的逻辑函数化简，应该先掌握什么？", OverlapGraphRepository())

    assert result["target_concept_id"] == "C3"
    assert result["interpretation_source"] == "fallback"
