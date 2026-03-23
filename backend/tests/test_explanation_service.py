from app.services.explanation_service import (
    _candidate_base_urls,
    _parse_llm_content,
    generate_reasoning_payload,
    generate_reasoning_and_explanation,
)


def test_explanation_service_fallback_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    steps, explanation = generate_reasoning_and_explanation(
        target_concept_id="C4",
        path=["C1", "C2", "C4"],
        evidence=["C1", "C2"],
        has_cycle=False,
    )

    assert len(steps) >= 3
    assert explanation


def test_explanation_service_uses_llm_output(monkeypatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_llm(_target: str, _path: list[str], _evidence: list[str]) -> dict:
        return {
            "reasoning_steps": ["s1", "s2", "s3"],
            "explanation": "这是 LLM 生成的说明。",
        }

    steps, explanation = generate_reasoning_and_explanation(
        target_concept_id="C4",
        path=["C1", "C2", "C4"],
        evidence=["C1", "C2"],
        has_cycle=False,
        llm_callable=fake_llm,
    )

    assert steps == ["s1", "s2", "s3"]
    assert explanation == "这是 LLM 生成的说明。"


def test_explanation_service_fallback_when_llm_raises(monkeypatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def bad_llm(_target: str, _path: list[str], _evidence: list[str]) -> dict:
        raise RuntimeError("boom")

    steps, explanation = generate_reasoning_and_explanation(
        target_concept_id="C4",
        path=["C1", "C2", "C4"],
        evidence=["C1", "C2"],
        has_cycle=True,
        llm_callable=bad_llm,
    )

    assert len(steps) >= 3
    assert "环路" in explanation


def test_generate_reasoning_payload_marks_llm_source(monkeypatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_llm(_target: str, _path: list[str], _evidence: list[str]) -> dict:
        return {
            "reasoning_steps": ["s1", "s2", "s3"],
            "explanation": "这是 LLM 生成的说明。",
        }

    payload = generate_reasoning_payload(
        target_concept_id="C4",
        path=["C1", "C2", "C4"],
        evidence=["C1", "C2"],
        has_cycle=False,
        llm_callable=fake_llm,
    )

    assert payload["explanation_source"] == "llm"
    assert payload["explanation"] == "这是 LLM 生成的说明。"


def test_generate_reasoning_payload_falls_back_when_llm_disabled(monkeypatch) -> None:
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    payload = generate_reasoning_payload(
        target_concept_id="C4",
        path=["C1", "C2", "C4"],
        evidence=["C1", "C2"],
        has_cycle=False,
    )

    assert payload["explanation_source"] == "fallback"
    assert payload["explanation"]


def test_candidate_base_urls_appends_or_strips_v1() -> None:
    assert _candidate_base_urls("https://api.scnet.cn/api/llm") == [
        "https://api.scnet.cn/api/llm",
        "https://api.scnet.cn/api/llm/v1",
    ]
    assert _candidate_base_urls("https://api.scnet.cn/api/llm/v1") == [
        "https://api.scnet.cn/api/llm/v1",
        "https://api.scnet.cn/api/llm",
    ]


def test_parse_llm_content_handles_plain_text_with_think() -> None:
    content = "<think>internal reasoning</think>这是一个学习建议说明。"
    parsed = _parse_llm_content(content)

    assert isinstance(parsed["reasoning_steps"], list)
    assert "学习建议说明" in parsed["explanation"]


def test_parse_llm_content_handles_embedded_json() -> None:
    content = "prefix {\"reasoning_steps\":[\"a\"],\"explanation\":\"b\"} suffix"
    parsed = _parse_llm_content(content)

    assert parsed["reasoning_steps"] == ["a"]
    assert parsed["explanation"] == "b"
