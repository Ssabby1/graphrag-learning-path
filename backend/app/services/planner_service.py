import json
import re

import httpx

from app.repositories.graph_repository import GraphRepository
from app.services.explanation_service import (
    _candidate_base_urls,
    _get_llm_api_key,
    _get_llm_base_url,
    _get_llm_model,
    _llm_enabled,
)

MASTERED_HINTS = [
    "已经学过",
    "学过",
    "掌握",
    "会了",
    "已掌握",
    "already know",
    "learned",
    "mastered",
    "know",
]

TARGET_HINTS = [
    "想学",
    "学习",
    "想了解",
    "want to learn",
    "want to study",
    "learn",
    "study",
]


def interpret_learning_request(question: str, repo: GraphRepository) -> dict:
    corpus = repo.get_concept_corpus(limit=2000)
    fallback = _fallback_interpretation(question, corpus)

    if not _llm_enabled():
        return fallback

    try:
        llm_result = _call_planner_llm(question, corpus, fallback)
        return _normalize_interpretation(llm_result, corpus, fallback)
    except Exception:
        return fallback


def _fallback_interpretation(question: str, corpus: list[dict]) -> dict:
    matches = _find_matches(question, corpus)
    target = None
    mastered: list[str] = []

    for match in matches:
        if match["is_mastered"]:
            mastered.append(match["concept_id"])

    unmatched = [item["concept_id"] for item in matches if item["concept_id"] not in mastered]
    if unmatched:
        target = unmatched[-1]
    elif matches:
        target = matches[-1]["concept_id"]

    summary_parts = []
    if target:
        summary_parts.append(f"目标知识点识别为 {target}")
    if mastered:
        summary_parts.append(f"已掌握知识点识别为 {', '.join(mastered)}")
    if not summary_parts:
        summary_parts.append("未能稳定识别目标知识点，请手动选择后继续。")

    return {
        "target_concept_id": target,
        "mastered_concepts": _unique(mastered),
        "matched_concepts": [item["concept_id"] for item in matches],
        "summary": "；".join(summary_parts),
        "interpretation_source": "fallback",
    }


def _find_matches(question: str, corpus: list[dict]) -> list[dict]:
    lowered = question.lower()
    matches: list[dict] = []

    for item in corpus:
        concept_id = (item.get("concept_id") or "").strip()
        name = (item.get("name") or "").strip()
        if not concept_id:
            continue

        candidates = [concept_id.lower()]
        if name:
            candidates.append(name.lower())

        hit_index = None
        matched_text = ""
        for candidate in candidates:
            if candidate and candidate in lowered:
                index = lowered.index(candidate)
                if hit_index is None or index < hit_index:
                    hit_index = index
                    matched_text = candidate

        if hit_index is None:
            continue

        window_start = max(0, hit_index - 18)
        context = lowered[window_start:hit_index]
        last_mastered = max((context.rfind(hint) for hint in MASTERED_HINTS), default=-1)
        last_target = max((context.rfind(hint) for hint in TARGET_HINTS), default=-1)
        is_mastered = last_mastered >= 0 and last_mastered > last_target

        matches.append(
            {
                "concept_id": concept_id,
                "name": name,
                "index": hit_index,
                "matched_text": matched_text,
                "is_mastered": is_mastered,
            }
        )

    matches.sort(key=lambda item: (item["index"], item["concept_id"]))
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in matches:
        if item["concept_id"] in seen:
            continue
        deduped.append(item)
        seen.add(item["concept_id"])
    return deduped


def _call_planner_llm(question: str, corpus: list[dict], fallback: dict) -> dict:
    api_key = _get_llm_api_key()
    base_url = _get_llm_base_url()
    model = _get_llm_model()
    timeout_s = 12.0

    matched = _find_matches(question, corpus)
    candidate_ids = [item["concept_id"] for item in matched]
    if not candidate_ids:
        candidate_ids = [item.get("concept_id") for item in corpus[:80] if item.get("concept_id")]

    candidate_lookup = {
        item["concept_id"]: (item.get("name") or "")
        for item in corpus
        if item.get("concept_id") in candidate_ids
    }
    candidate_lines = [f"{concept_id}: {name}".strip() for concept_id, name in candidate_lookup.items()]

    system_prompt = (
        "You map user learning requests to a target concept and mastered concepts. "
        "Return only valid JSON with keys target_concept_id, mastered_concepts, summary."
    )
    user_prompt = (
        f"User request: {question}\n"
        f"Allowed concepts:\n" + "\n".join(candidate_lines[:80]) + "\n"
        f"Fallback target: {fallback.get('target_concept_id')}\n"
        f"Fallback mastered: {fallback.get('mastered_concepts', [])}\n"
        "Choose only concept IDs from the allowed list. summary should be one short Chinese sentence."
    )

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    errors: list[Exception] = []
    with httpx.Client(timeout=timeout_s) as client:
        for candidate_base in _candidate_base_urls(base_url):
            try:
                response = client.post(
                    f"{candidate_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(_extract_json(content))
            except Exception as exc:
                errors.append(exc)

    raise RuntimeError(f"planner llm failed: {errors[-1] if errors else 'unknown'}")


def _extract_json(content: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return match.group(0)
    return text


def _normalize_interpretation(payload: dict, corpus: list[dict], fallback: dict) -> dict:
    corpus_ids = {item.get("concept_id") for item in corpus if item.get("concept_id")}
    target = payload.get("target_concept_id")
    if target not in corpus_ids:
        target = fallback.get("target_concept_id")

    mastered = payload.get("mastered_concepts") or []
    if not isinstance(mastered, list):
        mastered = []
    mastered = [item for item in mastered if isinstance(item, str) and item in corpus_ids]
    if not mastered:
        mastered = fallback.get("mastered_concepts", [])

    matched = _unique([*(fallback.get("matched_concepts", [])), *mastered, *( [target] if target else [])])
    summary = payload.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = fallback.get("summary", "")

    return {
        "target_concept_id": target,
        "mastered_concepts": _unique(mastered),
        "matched_concepts": matched,
        "summary": summary.strip(),
        "interpretation_source": "llm",
    }


def _unique(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped
