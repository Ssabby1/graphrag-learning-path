from __future__ import annotations

import json

from app.services.answer_generator import (
    StructuredAnswerGenerator,
    build_answer_messages,
    resolve_answer_language,
)


def _pack() -> dict:
    return {
        "evidence_pack_version": "1.0",
        "target_concept_id": "C2",
        "path": ["C1", "C2"],
        "items": [
            {
                "evidence_id": "prereq:C1:C2",
                "relation": "PREREQUISITE_OF",
                "from_concept": {"id": "C1", "name": "反码"},
                "to_concept": {"id": "C2", "name": "补码"},
                "reason": "反码推导补码",
            }
        ],
    }


def test_bilingual_fallback_follows_auto_and_explicit_language() -> None:
    generator = StructuredAnswerGenerator(enabled=False)
    zh = generator.generate("为什么先学反码？", "C2", ["C1", "C2"], _pack())
    en = generator.generate(
        "为什么先学反码？", "C2", ["C1", "C2"], _pack(), response_language="en"
    )

    assert zh["answer_source"] == en["answer_source"] == "fallback"
    assert zh["structured_output_success"] is False
    assert zh["llm_structured_output_success"] is False
    assert zh["response_schema_valid"] is True
    assert zh["answer_language"] == "zh"
    assert en["answer_language"] == "en"
    assert "建议按顺序学习" in zh["answer"]
    assert "Follow this learning order" in en["answer"]
    assert zh["cited_evidence_ids"] == en["cited_evidence_ids"] == ["prereq:C1:C2"]
    assert "Question:" not in zh["answer"]


def test_structured_llm_output_keeps_only_pack_citations() -> None:
    def fake_llm(_messages):
        return {
            "answer": "Learn 反码 before 补码 because it is the recorded prerequisite.",
            "cited_evidence_ids": ["prereq:C1:C2", "invented:C9:C10"],
        }

    result = StructuredAnswerGenerator(fake_llm, model="fake-llm").generate(
        "Why learn ones' complement first?", "C2", ["C1", "C2"], _pack()
    )

    assert result["answer_source"] == "llm"
    assert result["cited_evidence_ids"] == ["prereq:C1:C2"]
    assert result["discarded_invalid_citation_count"] == 1
    assert result["structured_output_success"] is True
    assert result["llm_structured_output_success"] is True
    assert result["response_schema_valid"] is True


def test_only_hallucinated_citations_force_grounded_fallback() -> None:
    def hallucinating_llm(_messages):
        return {
            "answer": "Learn an unrelated concept first.",
            "cited_evidence_ids": ["invented:C9:C10"],
        }

    result = StructuredAnswerGenerator(hallucinating_llm).generate(
        "Why learn ones' complement first?", "C2", ["C1", "C2"], _pack()
    )

    assert result["answer_source"] == "fallback"
    assert result["structured_output_success"] is False
    assert result["llm_structured_output_success"] is False
    assert result["response_schema_valid"] is True
    assert result["fallback_reason"] == "no_valid_citations"
    assert result["cited_evidence_ids"] == ["prereq:C1:C2"]
    assert result["discarded_invalid_citation_count"] == 1


def test_malformed_output_timeout_and_language_mismatch_use_fallback() -> None:
    malformed = StructuredAnswerGenerator(lambda _messages: "not-json").generate(
        "为什么先学反码？", "C2", ["C1", "C2"], _pack()
    )

    def timeout(_messages):
        raise TimeoutError("test timeout")

    timed_out = StructuredAnswerGenerator(timeout).generate(
        "Why first?", "C2", ["C1", "C2"], _pack()
    )
    mismatch = StructuredAnswerGenerator(
        lambda _messages: {
            "answer": "这是中文回答。",
            "cited_evidence_ids": ["prereq:C1:C2"],
        }
    ).generate("Explain this path", "C2", ["C1", "C2"], _pack(), "en")

    assert malformed["answer_source"] == "fallback"
    assert malformed["llm_structured_output_success"] is False
    assert malformed["response_schema_valid"] is True
    assert "structured_generation_failed" in malformed["fallback_reason"]
    assert timed_out["answer_source"] == "fallback"
    assert timed_out["fallback_reason"].startswith("TimeoutError")
    assert mismatch["answer_source"] == "fallback"
    assert mismatch["fallback_reason"] == "answer_language_mismatch"


def test_prompt_contains_only_bounded_inputs_and_json_contract() -> None:
    messages = build_answer_messages(
        "Why?", "C2", ["C1", "C2"], _pack(), "en"
    )
    payload = json.loads(messages[1]["content"])

    assert set(payload) == {
        "question",
        "target_concept_id",
        "path",
        "evidence_pack",
        "allowed_evidence_ids",
        "required_answer_language",
        "output_schema",
    }
    assert payload["allowed_evidence_ids"] == ["prereq:C1:C2"]
    assert "Return one JSON object only" in messages[0]["content"]


def test_language_resolution_handles_auto_mixed_and_invalid_values() -> None:
    assert resolve_answer_language("为什么学习补码？") == "zh"
    assert resolve_answer_language("Why learn two's complement?") == "en"
    assert resolve_answer_language("K-map 卡诺图怎么学？") == "zh"

    try:
        resolve_answer_language("question", "fr")
    except ValueError as exc:
        assert "Unsupported response_language" in str(exc)
    else:
        raise AssertionError("unsupported language must fail")
