from __future__ import annotations

try:
    from langchain_core.prompts import PromptTemplate
except Exception:  # pragma: no cover - optional dependency
    PromptTemplate = None


def build_grounded_answer(
    question: str,
    path: list[str],
    explanation: str,
    retrieval_hits: list[dict],
) -> str:
    hit_preview = ", ".join(hit.get("concept_id", "") for hit in retrieval_hits[:5])
    path_text = " -> ".join(path) if path else "No additional path needed"

    if PromptTemplate is not None:
        prompt = PromptTemplate.from_template(
            "Question: {question}\n"
            "Path: {path_text}\n"
            "Evidence concepts: {hits}\n"
            "Explanation: {explanation}\n"
            "Answer:"
        )
        return prompt.format(
            question=question,
            path_text=path_text,
            hits=hit_preview or "none",
            explanation=explanation,
        )

    return (
        f"Question: {question}\n"
        f"Path: {path_text}\n"
        f"Evidence concepts: {hit_preview or 'none'}\n"
        f"Explanation: {explanation}"
    )
