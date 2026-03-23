import json
import os
import re
import time
from typing import Callable

import httpx

LlmCallable = Callable[[str, list[str], list[str]], dict]


def _get_llm_api_key() -> str:
    return os.getenv("MINIMAX_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()


def _get_llm_base_url() -> str:
    return os.getenv("MINIMAX_BASE_URL", "").strip() or os.getenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1")


def _get_llm_model() -> str:
    return os.getenv("MINIMAX_MODEL", "").strip() or os.getenv("OPENAI_MODEL", "MiniMax-M2.7")


def get_fallback_reasoning_and_explanation(has_cycle: bool) -> tuple[list[str], str]:
    fallback_steps = [
        "Retrieve prerequisite closure for the target concept",
        "Filter out mastered concepts from candidate nodes",
        "Apply deterministic topological sort on prerequisite graph",
    ]
    fallback_explanation = "已基于前驱闭包和拓扑排序生成学习路径。"
    if has_cycle:
        fallback_explanation = "检测到疑似环路，已使用稳定回退顺序输出待学习节点。"

    return fallback_steps, fallback_explanation


def generate_reasoning_and_explanation(
    target_concept_id: str,
    path: list[str],
    evidence: list[str],
    has_cycle: bool,
    llm_callable: LlmCallable | None = None,
) -> tuple[list[str], str]:
    fallback_steps, fallback_explanation = get_fallback_reasoning_and_explanation(has_cycle)

    if not _llm_enabled():
        return fallback_steps, fallback_explanation

    try:
        caller = llm_callable or _call_remote_llm
        payload = caller(target_concept_id, path, evidence)
        steps = payload.get("reasoning_steps") or fallback_steps
        explanation = payload.get("explanation") or fallback_explanation

        if not isinstance(steps, list) or not all(isinstance(item, str) for item in steps):
            steps = fallback_steps
        if not isinstance(explanation, str):
            explanation = fallback_explanation

        return steps, explanation
    except Exception:
        return fallback_steps, fallback_explanation


def generate_reasoning_payload(
    target_concept_id: str,
    path: list[str],
    evidence: list[str],
    has_cycle: bool,
    llm_callable: LlmCallable | None = None,
) -> dict:
    fallback_steps, fallback_explanation = get_fallback_reasoning_and_explanation(has_cycle)

    if not _llm_enabled():
        return {
            "reasoning_steps": fallback_steps,
            "explanation": fallback_explanation,
            "explanation_source": "fallback",
        }

    try:
        caller = llm_callable or _call_remote_llm
        payload = caller(target_concept_id, path, evidence)
        steps = payload.get("reasoning_steps") or fallback_steps
        explanation = payload.get("explanation") or fallback_explanation

        if not isinstance(steps, list) or not all(isinstance(item, str) for item in steps):
            steps = fallback_steps
        if not isinstance(explanation, str):
            explanation = fallback_explanation

        return {
            "reasoning_steps": steps,
            "explanation": explanation,
            "explanation_source": "llm",
        }
    except Exception:
        return {
            "reasoning_steps": fallback_steps,
            "explanation": fallback_explanation,
            "explanation_source": "fallback",
        }


def _llm_enabled() -> bool:
    enabled = os.getenv("LLM_ENABLED", "false").strip().lower()
    api_key = _get_llm_api_key()
    return enabled in {"1", "true", "yes", "on"} and bool(api_key)


def _candidate_base_urls(raw_base_url: str) -> list[str]:
    base = raw_base_url.rstrip("/")
    candidates = [base]

    if base.endswith("/v1"):
        candidates.append(base[: -len("/v1")])
    else:
        candidates.append(f"{base}/v1")

    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _parse_llm_content(content: str) -> dict:
    text = content.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            payload = json.loads(match.group(0))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        cleaned = "已基于路径与证据生成学习建议。"

    return {
        "reasoning_steps": [
            "Analyze target concept and prerequisite path",
            "Identify key dependencies from evidence",
            "Generate concise learning explanation",
        ],
        "explanation": cleaned[:800],
    }


def _call_remote_llm(target_concept_id: str, path: list[str], evidence: list[str]) -> dict:
    api_key = _get_llm_api_key()
    raw_base_url = _get_llm_base_url()
    model = _get_llm_model()
    timeout_s = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    max_retries = max(0, int(os.getenv("LLM_MAX_RETRIES", "2")))

    prompt = (
        "You are an educational assistant. "
        "Given a target concept and a prerequisite learning path, "
        "produce JSON with keys reasoning_steps (array of 3-5 short strings) "
        "and explanation (1 short paragraph in Chinese).\n"
        f"target_concept_id: {target_concept_id}\n"
        f"path: {path}\n"
        f"evidence: {evidence}\n"
        "Keep explanation concrete and aligned with the provided path."
    )

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    errors: list[Exception] = []
    with httpx.Client(timeout=timeout_s) as client:
        for base_url in _candidate_base_urls(raw_base_url):
            for attempt in range(max_retries + 1):
                try:
                    response = client.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=body,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    return _parse_llm_content(content)
                except httpx.HTTPStatusError as exc:
                    errors.append(exc)
                    status = exc.response.status_code
                    if status in {401, 403, 404}:
                        break
                    if attempt < max_retries:
                        time.sleep(0.8 * (attempt + 1))
                except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as exc:
                    errors.append(exc)
                    if attempt < max_retries:
                        time.sleep(0.8 * (attempt + 1))
                except Exception as exc:
                    errors.append(exc)
                    break

    raise RuntimeError(f"All LLM endpoint attempts failed: {errors[-1]}") from errors[-1]
