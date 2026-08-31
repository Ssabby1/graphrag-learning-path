from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_ROOT, settings
from app.retrieval.corpus_builder import corpus_hash


INDEX_SCHEMA_VERSION = "embedding-index-v1"


@dataclass(frozen=True)
class EmbeddingIndex:
    documents: list[dict[str, Any]]
    vectors: list[list[float]]
    metadata: dict[str, Any]
    cache_status: str


class EmbeddingCache:
    def __init__(self, cache_dir: str | Path | None = None) -> None:
        configured = Path(cache_dir or settings.embedding_cache_dir)
        self.cache_dir = configured if configured.is_absolute() else BACKEND_ROOT / configured

    def get_or_build(self, documents: list[dict[str, Any]], backend) -> EmbeddingIndex:
        documents = sorted(documents, key=lambda item: str(item.get("id") or ""))
        dimension = int(backend.dimension)
        metadata = {
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "corpus_hash": corpus_hash(documents),
            "model_id": backend.model_id,
            "dimension": dimension,
            "normalization": bool(backend.normalize),
            "document_count": len(documents),
        }
        key = hashlib.sha256(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        path = self.cache_dir / f"{key}.json"
        cached = self._load(path, metadata, documents)
        if cached is not None:
            return cached

        vectors = backend.embed_documents([document.get("text", "") for document in documents])
        self._validate_vectors(vectors, len(documents), dimension)
        payload = {"metadata": metadata, "documents": documents, "vectors": vectors}
        self._write_atomic(path, payload)
        return EmbeddingIndex(documents, vectors, metadata, "rebuilt")

    def _load(
        self,
        path: Path,
        expected_metadata: dict[str, Any],
        expected_documents: list[dict[str, Any]],
    ) -> EmbeddingIndex | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("metadata") != expected_metadata:
                return None
            documents = payload.get("documents")
            vectors = payload.get("vectors")
            if documents != expected_documents:
                return None
            self._validate_vectors(
                vectors, expected_metadata["document_count"], expected_metadata["dimension"]
            )
            return EmbeddingIndex(documents, vectors, expected_metadata, "hit")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    @staticmethod
    def _validate_vectors(vectors: Any, count: int, dimension: int) -> None:
        if not isinstance(vectors, list) or len(vectors) != count:
            raise ValueError("Embedding cache vector count mismatch")
        if any(not isinstance(vector, list) or len(vector) != dimension for vector in vectors):
            raise ValueError("Embedding cache vector dimension mismatch")

    def _write_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
