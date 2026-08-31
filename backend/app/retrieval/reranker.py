from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.core.config import settings


class RerankerUnavailable(RuntimeError):
    pass


def _tokens(text: str) -> set[str]:
    lowered = (text or "").lower()
    return set(re.findall(r"[a-zA-Z0-9_]+", lowered)) | {
        character for character in lowered if "\u3400" <= character <= "\u9fff"
    }


def _stable_sort(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        hits,
        key=lambda item: (
            -float(item.get("rerank_score") or 0.0),
            int(item.get("rank") or 10**9),
            str(item.get("id") or item.get("concept_id") or ""),
        ),
    )


class TokenOverlapReranker:
    @property
    def model_id(self) -> str:
        return "token-overlap-v2"

    def rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        rescored = rerank_hits(query, hits, top_k)
        for rank, hit in enumerate(rescored, start=1):
            hit["rank"] = rank
        return rescored


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str,
        *,
        allow_download: bool = False,
        device: str | None = None,
        batch_size: int = 16,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.allow_download = allow_download
        self.device = device or None
        self.batch_size = batch_size
        self.max_length = max_length
        self._model: Any | None = None

    @property
    def model_id(self) -> str:
        return self.model_name

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            import torch
            from sentence_transformers import CrossEncoder
        except (ImportError, RuntimeError) as exc:
            raise RerankerUnavailable(
                "sentence-transformers is unavailable; install backend/requirements-embeddings.txt"
            ) from exc
        try:
            self._model = CrossEncoder(
                self.model_name,
                device=self.device,
                max_length=self.max_length,
                activation_fn=torch.nn.Sigmoid(),
                local_files_only=not self.allow_download,
            )
        except Exception as exc:
            mode = "download allowed" if self.allow_download else "local-files-only"
            raise RerankerUnavailable(
                f"Unable to load reranker {self.model_name} ({mode}): {exc}"
            ) from exc
        return self._model

    def ensure_available(self) -> None:
        self._load_model()

    def rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        if not hits:
            return []
        scores = self._load_model().predict(
            [(query, str(hit.get("text") or "")) for hit in hits],
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        rescored: list[dict[str, Any]] = []
        for hit, score in zip(hits, scores):
            merged = dict(hit)
            merged["rerank_score"] = float(score)
            merged["score"] = float(score)
            rescored.append(merged)
        rescored = _stable_sort(rescored)[: max(1, top_k)]
        for rank, hit in enumerate(rescored, start=1):
            hit["rank"] = rank
        return rescored


def rerank_hits(question: str, hits: list[dict], top_k: int = 6) -> list[dict]:
    if not hits:
        return []

    q_tokens = _tokens(question)
    rescored: list[dict[str, Any]] = []
    for hit in hits:
        h_tokens = _tokens(str(hit.get("text") or ""))
        overlap = len(q_tokens & h_tokens)
        base = float(hit.get("rrf_score", hit.get("score", 0.0)) or 0.0)
        final_score = base + 0.05 * overlap
        merged = dict(hit)
        merged["rerank_score"] = final_score
        merged["score"] = final_score
        rescored.append(merged)

    return _stable_sort(rescored)[: max(1, top_k)]


@lru_cache(maxsize=1)
def get_reranker() -> tuple[Any, bool, str | None]:
    if settings.reranker_backend == "token_overlap":
        return TokenOverlapReranker(), True, (
            "token_overlap explicitly configured; semantic pair scoring is disabled"
        )
    if settings.reranker_backend != "cross_encoder":
        raise RerankerUnavailable(
            f"Unsupported reranker backend: {settings.reranker_backend}"
        )

    reranker = CrossEncoderReranker(
        settings.reranker_model,
        allow_download=settings.reranker_allow_download,
        device=settings.reranker_device or None,
        batch_size=settings.reranker_batch_size,
        max_length=settings.reranker_max_length,
    )
    try:
        reranker.ensure_available()
        return reranker, False, None
    except RerankerUnavailable as exc:
        if settings.reranker_fallback_backend != "token_overlap":
            raise
        return TokenOverlapReranker(), True, str(exc)
