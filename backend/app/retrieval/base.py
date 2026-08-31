from __future__ import annotations

from typing import Protocol


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

