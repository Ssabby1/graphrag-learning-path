from __future__ import annotations

from types import SimpleNamespace

import app.retrieval.reranker as reranker_module
from app.retrieval.reranker import (
    CrossEncoderReranker,
    RerankerUnavailable,
    TokenOverlapReranker,
)


def _hits() -> list[dict]:
    return [
        {"id": "C1", "text": "二进制基础", "rank": 1, "rrf_score": 0.03, "score": 0.03},
        {"id": "C2", "text": "卡诺图构成", "rank": 2, "rrf_score": 0.02, "score": 0.02},
    ]


def test_cross_encoder_reranker_scores_pairs_and_preserves_stage_scores() -> None:
    captured: dict = {}

    class FakeCrossEncoder:
        def predict(self, pairs, **kwargs):
            captured["pairs"] = pairs
            captured["kwargs"] = kwargs
            return [0.1, 0.9]

    reranker = CrossEncoderReranker("fake-cross-encoder", batch_size=4)
    reranker._model = FakeCrossEncoder()
    result = reranker.rerank("如何学习卡诺图？", _hits(), top_k=2)

    assert [hit["id"] for hit in result] == ["C2", "C1"]
    assert [hit["rerank_score"] for hit in result] == [0.9, 0.1]
    assert [hit["score"] for hit in result] == [0.9, 0.1]
    assert result[0]["rrf_score"] == 0.02
    assert captured["pairs"][1] == ("如何学习卡诺图？", "卡诺图构成")
    assert captured["kwargs"] == {"batch_size": 4, "show_progress_bar": False}


def test_cross_encoder_ties_keep_input_rank_stable() -> None:
    class TiedCrossEncoder:
        def predict(self, pairs, **kwargs):
            return [0.5 for _ in pairs]

    reranker = CrossEncoderReranker("fake-cross-encoder")
    reranker._model = TiedCrossEncoder()

    assert [hit["id"] for hit in reranker.rerank("query", _hits(), 2)] == ["C1", "C2"]


def test_token_overlap_updates_final_score_without_losing_rrf_score() -> None:
    result = TokenOverlapReranker().rerank("卡诺图", _hits(), top_k=2)

    assert result[0]["id"] == "C2"
    assert result[0]["score"] == result[0]["rerank_score"]
    assert result[0]["rrf_score"] == 0.02


def test_reranker_factory_falls_back_explicitly_without_downloading(monkeypatch) -> None:
    reranker_module.get_reranker.cache_clear()
    monkeypatch.setattr(
        reranker_module,
        "settings",
        SimpleNamespace(
            reranker_backend="cross_encoder",
            reranker_model="missing-local-model",
            reranker_allow_download=False,
            reranker_device="",
            reranker_batch_size=4,
            reranker_max_length=128,
            reranker_fallback_backend="token_overlap",
        ),
    )

    def unavailable(self):
        raise RerankerUnavailable("offline test")

    monkeypatch.setattr(CrossEncoderReranker, "ensure_available", unavailable)
    reranker, degraded, reason = reranker_module.get_reranker()

    assert reranker.model_id == "token-overlap-v2"
    assert degraded is True
    assert reason == "offline test"
    reranker_module.get_reranker.cache_clear()
