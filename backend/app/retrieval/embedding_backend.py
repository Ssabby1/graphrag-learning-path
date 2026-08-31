from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Any

from app.core.config import settings


class EmbeddingBackendUnavailable(RuntimeError):
    pass


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return vector if norm == 0 else [value / norm for value in vector]


def _unicode_tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    ascii_tokens = re.findall(r"[a-z0-9_]+", lowered)
    cjk = [character for character in lowered if "\u3400" <= character <= "\u9fff"]
    cjk_bigrams = ["".join(cjk[index : index + 2]) for index in range(max(0, len(cjk) - 1))]
    return ascii_tokens + cjk + cjk_bigrams


class UnicodeHashingEmbeddingBackend:
    """Deterministic offline fallback; non-semantic and always marked degraded."""

    def __init__(self, dimension: int = 512, normalize: bool = True) -> None:
        self._dimension = dimension
        self._normalize = normalize

    @property
    def model_id(self) -> str:
        return f"unicode-hashing-v1:{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def normalize(self) -> bool:
        return self._normalize

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in _unicode_tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self._dimension
            vector[index] += 1.0
        return _l2_normalize(vector) if self._normalize else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class SentenceTransformerEmbeddingBackend:
    def __init__(
        self,
        model_name: str,
        normalize: bool = True,
        allow_download: bool = False,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self._normalize = normalize
        self.allow_download = allow_download
        self.device = device
        self._model: Any | None = None

    @property
    def model_id(self) -> str:
        return self.model_name

    @property
    def normalize(self) -> bool:
        return self._normalize

    @property
    def dimension(self) -> int:
        model = self._load_model()
        get_dimension = getattr(model, "get_embedding_dimension", None)
        dimension = (
            get_dimension()
            if get_dimension is not None
            else model.get_sentence_embedding_dimension()
        )
        if not dimension:
            raise EmbeddingBackendUnavailable(
                f"Embedding dimension unavailable for model {self.model_name}"
            )
        return int(dimension)

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except (ImportError, RuntimeError) as exc:
            raise EmbeddingBackendUnavailable(
                "sentence-transformers is not installed; install backend/requirements-embeddings.txt"
            ) from exc
        try:
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                local_files_only=not self.allow_download,
            )
        except Exception as exc:
            mode = "download allowed" if self.allow_download else "local-files-only"
            raise EmbeddingBackendUnavailable(
                f"Unable to load {self.model_name} ({mode}): {exc}"
            ) from exc
        return self._model

    def _document_text(self, text: str) -> str:
        return f"passage: {text}" if "e5" in self.model_name.lower() else text

    def _query_text(self, text: str) -> str:
        return f"query: {text}" if "e5" in self.model_name.lower() else text

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load_model().encode(
            texts,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._document_text(text) for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self._query_text(text)])[0]


@lru_cache(maxsize=1)
def get_embedding_backend() -> tuple[Any, bool, str | None]:
    if settings.embedding_backend == "unicode_hashing":
        return UnicodeHashingEmbeddingBackend(normalize=settings.embedding_normalize), True, (
            "unicode_hashing explicitly configured; semantic cross-lingual retrieval is disabled"
        )

    backend = SentenceTransformerEmbeddingBackend(
        model_name=settings.embedding_model,
        normalize=settings.embedding_normalize,
        allow_download=settings.embedding_allow_download,
    )
    try:
        _ = backend.dimension
        return backend, False, None
    except EmbeddingBackendUnavailable as exc:
        if settings.embedding_fallback_backend != "unicode_hashing":
            raise
        fallback = UnicodeHashingEmbeddingBackend(normalize=settings.embedding_normalize)
        return fallback, True, str(exc)
