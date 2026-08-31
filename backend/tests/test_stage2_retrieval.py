import json
from pathlib import Path

import pytest

from app.retrieval.concept_retriever import ConceptRetriever
from app.retrieval.corpus_builder import (
    build_concept_documents,
    build_evidence_documents,
    corpus_hash,
)
from app.retrieval.embedding_backend import (
    SentenceTransformerEmbeddingBackend,
    UnicodeHashingEmbeddingBackend,
)
from app.retrieval.embedding_cache import EmbeddingCache
from app.retrieval.evidence_retriever import EvidenceRetriever
from app.retrieval.reranker import TokenOverlapReranker
from app.services.target_resolver import detect_query_language, resolve_target


class FakeMultilingualEmbedding:
    model_id = "fake-multilingual-v1"
    dimension = 3
    normalize = True

    def __init__(self) -> None:
        self.document_calls = 0

    @staticmethod
    def _embed(text: str) -> list[float]:
        lowered = text.lower()
        if "卡诺" in lowered or "karnaugh" in lowered or "k-map" in lowered:
            return [1.0, 0.0, 0.0]
        if "二进制" in lowered or "binary" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def _concept_rows() -> list[dict]:
    return [
        {
            "concept_id": "C1",
            "name": "二进制",
            "name_en": "Binary",
            "aliases": ["Binary number"],
            "description": "二进制数制",
            "description_en": "Base-two numeral system",
            "source_chapters": ["第一章"],
            "predecessor_names": [],
            "successor_names": ["卡诺图"],
        },
        {
            "concept_id": "C2",
            "name": "卡诺图",
            "name_en": "Karnaugh Map",
            "aliases_en": ["K-map"],
            "description": "逻辑函数图形化简方法",
            "source_chapters": ["第三章"],
            "predecessor_names": ["二进制"],
            "successor_names": [],
        },
    ]


def test_concept_and_evidence_corpora_are_deterministic_and_separate() -> None:
    concepts = build_concept_documents(list(reversed(_concept_rows())))
    evidence = build_evidence_documents(
        [
            {
                "from_concept_id": "C1",
                "from_name": "二进制",
                "to_concept_id": "C2",
                "to_name": "卡诺图",
                "relation_type": "PREREQUISITE_OF",
                "evidence_text": "二进制是前置知识",
                "source_chapters": ["第三章", "第一章"],
                "confidence_max": 0.9,
            }
        ]
    )

    assert [document["id"] for document in concepts] == ["C1", "C2"]
    assert "英文名称：Karnaugh Map" in concepts[1]["text"]
    assert "直接前置知识：二进制" in concepts[1]["text"]
    assert evidence[0]["id"] == "prereq:C1:C2"
    assert evidence[0]["id"] not in {document["id"] for document in concepts}
    assert corpus_hash(concepts) == corpus_hash(build_concept_documents(_concept_rows()))


def test_unicode_fallback_produces_nonzero_stable_multilingual_vectors() -> None:
    backend = UnicodeHashingEmbeddingBackend(dimension=64)
    vectors = [
        backend.embed_query("卡诺图"),
        backend.embed_query("Karnaugh map"),
        backend.embed_query("K-map 卡诺图"),
    ]

    assert all(any(value != 0 for value in vector) for vector in vectors)
    assert backend.embed_query("卡诺图") == vectors[0]


def test_e5_backend_applies_query_and_passage_prefixes() -> None:
    captured: list[str] = []

    class FakeModel:
        def get_sentence_embedding_dimension(self):
            return 2

        def encode(self, texts, **kwargs):
            captured.extend(texts)
            return [[1.0, 0.0] for _ in texts]

    backend = SentenceTransformerEmbeddingBackend("intfloat/multilingual-e5-small")
    backend._model = FakeModel()
    backend.embed_documents(["document"])
    backend.embed_query("question")

    assert captured == ["passage: document", "query: question"]


def test_embedding_cache_hits_invalidates_and_recovers_corruption(tmp_path: Path) -> None:
    backend = FakeMultilingualEmbedding()
    cache = EmbeddingCache(tmp_path)
    documents = build_concept_documents(_concept_rows())

    first = cache.get_or_build(documents, backend)
    second = cache.get_or_build(documents, backend)
    changed = cache.get_or_build(
        [*documents, {"id": "C3", "concept_id": "C3", "text": "other", "metadata": {}}],
        backend,
    )
    cache_files = sorted(tmp_path.glob("*.json"))
    for cache_file in cache_files:
        cache_file.write_text("{broken", encoding="utf-8")
    recovered = cache.get_or_build(documents, backend)

    assert first.cache_status == "rebuilt"
    assert second.cache_status == "hit"
    assert changed.cache_status == "rebuilt"
    assert recovered.cache_status == "rebuilt"
    assert backend.document_calls == 3


@pytest.mark.parametrize(
    "mode",
    ["graph_only", "vector_only", "hybrid_rrf", "hybrid_rrf_rerank"],
)
def test_all_retrieval_modes_preserve_stage_scores(tmp_path: Path, mode: str) -> None:
    backend = FakeMultilingualEmbedding()
    retriever = ConceptRetriever(
        backend,
        cache=EmbeddingCache(tmp_path),
        reranker=TokenOverlapReranker(),
    )
    result = retriever.search(
        "Karnaugh map",
        build_concept_documents(_concept_rows()),
        graph_ids=["C1", "C2"],
        mode=mode,
        top_k_vector=2,
        top_k_final=2,
    )

    assert [hit["rank"] for hit in result["hits"]] == list(
        range(1, len(result["hits"]) + 1)
    )
    assert all(
        {
            "graph_rank",
            "vector_rank",
            "graph_score",
            "vector_score",
            "rrf_score",
            "rerank_score",
        }
        <= hit.keys()
        for hit in result["hits"]
    )
    if mode == "graph_only":
        assert result["cache_status"] == "not_used"
        assert all(hit["vector_score"] is None for hit in result["hits"])
    if mode == "vector_only":
        assert all(hit["graph_score"] is None for hit in result["hits"])
    if mode == "hybrid_rrf_rerank":
        assert all(hit["rerank_score"] is not None for hit in result["hits"])


def test_target_resolver_handles_cross_lingual_query_and_rejection(monkeypatch, tmp_path: Path) -> None:
    backend = FakeMultilingualEmbedding()
    monkeypatch.setattr(
        "app.services.target_resolver.get_embedding_backend",
        lambda: (backend, False, None),
    )
    monkeypatch.setattr(
        "app.services.target_resolver.EmbeddingCache", lambda: EmbeddingCache(tmp_path)
    )

    class Repo:
        def get_concept_corpus(self, limit: int = 2000):
            return _concept_rows()[:limit]

    resolved = resolve_target("What should I learn before studying Karnaugh maps?", Repo())
    unrelated = resolve_target("weather forecast", Repo())

    assert resolved["target_concept_id"] == "C2"
    assert resolved["query_language"] == "en"
    assert resolved["candidates"][0]["vector_score"] is not None
    assert unrelated["rejected"] is True
    assert detect_query_language("K-map 卡诺图") == "mixed"


def test_target_resolver_prefers_latest_learning_intent_and_rejects_comparison(tmp_path: Path) -> None:
    backend = FakeMultilingualEmbedding()

    class Repo:
        def get_concept_corpus(self, limit: int = 2000):
            return [
                {"concept_id": "C1", "name": "原码"},
                {"concept_id": "C2", "name": "反码"},
                {"concept_id": "C3", "name": "海明码"},
            ][:limit]

    learned_then_target = resolve_target(
        "我已学过原码，现在想学反码",
        Repo(),
        embedding_backend=backend,
        embedding_cache=EmbeddingCache(tmp_path),
    )
    comparison = resolve_target(
        "比较反码和海明码",
        Repo(),
        embedding_backend=backend,
        embedding_cache=EmbeddingCache(tmp_path),
    )

    assert learned_then_target["target_concept_id"] == "C2"
    assert comparison["rejected"] is True
    assert comparison["rejection_reason"] == "multiple_explicit_targets"


def test_relationship_corpus_uses_independent_graph_scoped_index(tmp_path: Path) -> None:
    backend = FakeMultilingualEmbedding()
    rows = [
        {
            "from_concept_id": "C1",
            "from_name": "二进制",
            "to_concept_id": "C2",
            "to_name": "卡诺图",
            "relation_type": "PREREQUISITE_OF",
            "evidence_text": "学习卡诺图前需要二进制基础",
        },
        {
            "from_concept_id": "C3",
            "from_name": "Other",
            "to_concept_id": "C4",
            "to_name": "Other",
            "relation_type": "RELATED_TO",
            "evidence_text": "unrelated",
        },
    ]
    result = EvidenceRetriever(backend, EmbeddingCache(tmp_path)).search(
        "Why learn Karnaugh maps?",
        rows,
        allowed_evidence_ids={"prereq:C1:C2"},
    )

    assert [hit["evidence_id"] for hit in result["hits"]] == ["prereq:C1:C2"]
    assert result["index_metadata"]["document_count"] == 2
