from __future__ import annotations

from typing import Any, Protocol


class EmbeddingBackend(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    @property
    def normalize(self) -> bool: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class Reranker(Protocol):
    @property
    def model_id(self) -> str: ...

    def rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]: ...


class AnswerGenerator(Protocol):
    def generate(
        self,
        question: str,
        target_concept_id: str,
        path: list[str],
        evidence_pack: dict[str, Any],
        response_language: str = "auto",
    ) -> dict[str, Any]: ...
