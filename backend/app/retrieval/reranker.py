from __future__ import annotations

import re


def _tokens(text: str) -> set[str]:
    lowered = (text or "").lower()
    return set(re.findall(r"[a-zA-Z0-9_]+", lowered)) | {
        character for character in lowered if "\u3400" <= character <= "\u9fff"
    }


class TokenOverlapReranker:
    @property
    def model_id(self) -> str:
        return "token-overlap-v2"

    def rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        rescored = rerank_hits(query, hits, top_k)
        for rank, hit in enumerate(rescored, start=1):
            hit["rank"] = rank
        return rescored


def rerank_hits(question: str, hits: list[dict], top_k: int = 6) -> list[dict]:
    if not hits:
        return []

    q_tokens = _tokens(question)
    rescored: list[dict] = []
    for hit in hits:
        text = hit.get("text", "")
        h_tokens = _tokens(text)
        overlap = len(q_tokens & h_tokens)
        base = float(hit.get("rrf_score", hit.get("score", 0.0)) or 0.0)
        final_score = base + 0.05 * overlap

        merged = dict(hit)
        merged["rerank_score"] = final_score
        rescored.append(merged)

    rescored.sort(key=lambda item: item["rerank_score"], reverse=True)
    return rescored[: max(1, top_k)]
