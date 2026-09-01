from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable

import httpx

from app.evidence.citation_validator import validate_citation_ids


AnswerLlmCallable = Callable[[list[dict[str, str]]], dict[str, Any] | str]
VALID_RESPONSE_LANGUAGES = {"auto", "zh", "en"}


def resolve_answer_language(question: str, response_language: str = "auto") -> str:
    requested = (response_language or "auto").strip().lower()
    if requested not in VALID_RESPONSE_LANGUAGES:
        raise ValueError(f"Unsupported response_language: {response_language}")
    if requested in {"zh", "en"}:
        return requested
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", question or ""))
    latin_count = len(re.findall(r"[A-Za-z]", question or ""))
    return "zh" if cjk_count >= latin_count and cjk_count > 0 else "en"


def _language_matches(text: str, expected: str) -> bool:
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text or ""))
    latin_count = len(re.findall(r"[A-Za-z]", text or ""))
    if expected == "zh":
        return cjk_count > 0 and cjk_count >= max(1, latin_count // 3)
    return latin_count > cjk_count


def _pack_items(evidence_pack: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in evidence_pack.get("items", []) if item.get("evidence_id")]


def _concept_label(concept: dict[str, Any], language: str) -> str:
    preferred = concept.get("name_en") if language == "en" else concept.get("name")
    return str(preferred or concept.get("name") or concept.get("name_en") or concept.get("id") or "")


def _localized_reason(reason: str, language: str) -> str:
    parts = [part.strip() for part in re.split(r"[；;]", reason or "") if part.strip()]
    if len(parts) < 2:
        return reason
    return parts[-1] if language == "en" else parts[0]


def _fallback_answer(
    target_concept_id: str,
    path: list[str],
    evidence_pack: dict[str, Any],
    language: str,
) -> tuple[str, list[str]]:
    items = _pack_items(evidence_pack)
    citations = [item["evidence_id"] for item in items]
    if language == "zh":
        path_text = " → ".join(path) if path else target_concept_id
        if not items:
            return (
                f"建议从目标知识点 {target_concept_id} 开始学习。当前证据包中没有额外的先修关系。",
                [],
            )
        reasons = [
            f"{_concept_label(item.get('from_concept', {}), 'zh')}"
            f" 是 {_concept_label(item.get('to_concept', {}), 'zh')} 的前置知识"
            f"（{_localized_reason(item.get('reason') or '关系证据已记录', 'zh')}）"
            for item in items
        ]
        return f"建议按顺序学习：{path_text}。" + "；".join(reasons) + "。", citations

    path_text = " → ".join(path) if path else target_concept_id
    if not items:
        return (
            f"Start with the target concept {target_concept_id}. The current evidence pack contains no additional prerequisite relationship.",
            [],
        )
    reasons = [
        f"{_concept_label(item.get('from_concept', {}), 'en')}"
        f" is a prerequisite for {_concept_label(item.get('to_concept', {}), 'en')}"
        f" ({_localized_reason(item.get('reason') or 'relationship evidence is recorded', 'en')})"
        for item in items
    ]
    return f"Follow this learning order: {path_text}. " + "; ".join(reasons) + ".", citations


def _strict_payload(raw: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, str):
        text = raw.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1)
        payload = json.loads(text)
    else:
        raise ValueError("Answer generator returned an unsupported payload type")
    if not isinstance(payload, dict):
        raise ValueError("Answer generator payload must be an object")
    answer = payload.get("answer")
    citations = payload.get("cited_evidence_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Structured answer is missing a non-empty answer")
    if not isinstance(citations, list) or not all(
        isinstance(item, str) for item in citations
    ):
        raise ValueError("Structured answer cited_evidence_ids must be a string list")
    return {"answer": answer.strip(), "cited_evidence_ids": citations}


def build_answer_messages(
    question: str,
    target_concept_id: str,
    path: list[str],
    evidence_pack: dict[str, Any],
    language: str,
) -> list[dict[str, str]]:
    allowed_ids = [item["evidence_id"] for item in _pack_items(evidence_pack)]
    schema = {
        "answer": "string",
        "cited_evidence_ids": ["one or more IDs from allowed_evidence_ids"],
    }
    bounded_input = {
        "question": question,
        "target_concept_id": target_concept_id,
        "path": path,
        "evidence_pack": evidence_pack,
        "allowed_evidence_ids": allowed_ids,
        "required_answer_language": language,
        "output_schema": schema,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are a grounded learning-path answer generator. Use only the supplied "
                "path and Evidence Pack. Do not add facts, relationships, or evidence IDs. "
                "Return one JSON object only. Every cited ID must appear in allowed_evidence_ids."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(bounded_input, ensure_ascii=False, separators=(",", ":")),
        },
    ]


class StructuredAnswerGenerator:
    def __init__(
        self,
        llm_callable: AnswerLlmCallable | None = None,
        *,
        enabled: bool | None = None,
        model: str | None = None,
    ) -> None:
        self.llm_callable = llm_callable
        self.enabled = enabled
        self.model = model or _get_llm_model()

    def generate(
        self,
        question: str,
        target_concept_id: str,
        path: list[str],
        evidence_pack: dict[str, Any],
        response_language: str = "auto",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        language = resolve_answer_language(question, response_language)
        fallback_answer, fallback_citations = _fallback_answer(
            target_concept_id, path, evidence_pack, language
        )
        use_llm = self.enabled if self.enabled is not None else _llm_enabled()
        if self.llm_callable is not None and self.enabled is None:
            use_llm = True
        if not use_llm:
            return self._fallback_result(
                fallback_answer,
                fallback_citations,
                language,
                started,
                "llm_disabled_or_missing_api_key",
            )

        try:
            messages = build_answer_messages(
                question, target_concept_id, path, evidence_pack, language
            )
            raw = (
                self.llm_callable(messages)
                if self.llm_callable is not None
                else _call_remote_answer(messages, self.model)
            )
            payload = _strict_payload(raw)
            validation = validate_citation_ids(
                payload["cited_evidence_ids"], evidence_pack
            )
            pack_has_evidence = bool(_pack_items(evidence_pack))
            if pack_has_evidence and not validation["valid_evidence_ids"]:
                return self._fallback_result(
                    fallback_answer,
                    fallback_citations,
                    language,
                    started,
                    "no_valid_citations",
                    discarded_invalid_count=validation["invalid_count"],
                )
            if not _language_matches(payload["answer"], language):
                return self._fallback_result(
                    fallback_answer,
                    fallback_citations,
                    language,
                    started,
                    "answer_language_mismatch",
                    discarded_invalid_count=validation["invalid_count"],
                )
            return {
                "answer": payload["answer"],
                "cited_evidence_ids": validation["valid_evidence_ids"],
                "answer_source": "llm",
                "answer_language": language,
                "generation_model": self.model,
                "generation_latency_ms": round(
                    (time.perf_counter() - started) * 1000, 3
                ),
                "structured_output_success": True,
                "llm_structured_output_success": True,
                "response_schema_valid": True,
                "fallback_reason": None,
                "discarded_invalid_citation_count": validation["invalid_count"],
            }
        except Exception as exc:
            return self._fallback_result(
                fallback_answer,
                fallback_citations,
                language,
                started,
                f"{type(exc).__name__}:structured_generation_failed",
            )

    def _fallback_result(
        self,
        answer: str,
        citations: list[str],
        language: str,
        started: float,
        reason: str,
        discarded_invalid_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "answer": answer,
            "cited_evidence_ids": citations,
            "answer_source": "fallback",
            "answer_language": language,
            "generation_model": "deterministic-evidence-fallback-v1",
            "generation_latency_ms": round(
                (time.perf_counter() - started) * 1000, 3
            ),
            "structured_output_success": False,
            "llm_structured_output_success": False,
            "response_schema_valid": True,
            "fallback_reason": reason,
            "discarded_invalid_citation_count": discarded_invalid_count,
        }


def _get_llm_api_key() -> str:
    return (
        os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("MINIMAX_API_KEY", "").strip()
    )


def _get_llm_model() -> str:
    return (
        os.getenv("DEEPSEEK_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or os.getenv("MINIMAX_MODEL", "").strip()
        or "deepseek-chat"
    )


def _get_llm_base_url() -> str:
    return (
        os.getenv("DEEPSEEK_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
        or os.getenv("MINIMAX_BASE_URL", "").strip()
        or "https://api.deepseek.com"
    ).rstrip("/")


def _llm_enabled() -> bool:
    enabled = os.getenv("LLM_ENABLED", "false").strip().lower()
    return enabled in {"1", "true", "yes", "on"} and bool(_get_llm_api_key())


def _candidate_urls(base_url: str) -> list[str]:
    candidates = [base_url]
    candidates.append(base_url[: -len("/v1")] if base_url.endswith("/v1") else f"{base_url}/v1")
    return list(dict.fromkeys(item for item in candidates if item))


def _call_remote_answer(messages: list[dict[str, str]], model: str) -> dict[str, Any]:
    api_key = _get_llm_api_key()
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    max_retries = max(0, int(os.getenv("LLM_MAX_RETRIES", "2")))
    body = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    errors: list[Exception] = []
    with httpx.Client(timeout=timeout_seconds) as client:
        for base_url in _candidate_urls(_get_llm_base_url()):
            for attempt in range(max_retries + 1):
                try:
                    response = client.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                    response.raise_for_status()
                    return _strict_payload(response.json()["choices"][0]["message"]["content"])
                except httpx.HTTPStatusError as exc:
                    errors.append(exc)
                    if exc.response.status_code in {400, 401, 403, 404}:
                        break
                    if attempt < max_retries:
                        time.sleep(0.5 * (attempt + 1))
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    errors.append(exc)
                    if attempt < max_retries:
                        time.sleep(0.5 * (attempt + 1))
                except Exception as exc:
                    errors.append(exc)
                    break
    last_error = errors[-1] if errors else RuntimeError("unknown generation error")
    raise RuntimeError(f"All answer generation endpoint attempts failed: {last_error}") from last_error
