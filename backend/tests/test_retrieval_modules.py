from app.retrieval.reranker import rerank_hits
from app.retrieval.vector_store import VectorStore, rrf_fuse


def test_rrf_fuse_prioritizes_consensus() -> None:
    merged = rrf_fuse([["C1", "C2", "C3"], ["C2", "C4", "C1"]], k=60)
    assert merged[0][0] in {"C1", "C2"}
    merged_ids = [item[0] for item in merged]
    assert "C4" in merged_ids


def test_vector_store_returns_top_hits() -> None:
    docs = [
        {"concept_id": "C1", "text": "binary bit number system"},
        {"concept_id": "C2", "text": "logic gate and truth table"},
    ]
    store = VectorStore(docs)
    hits = store.search("truth table logic", top_k=1)
    assert len(hits) == 1
    assert hits[0]["concept_id"] == "C2"


def test_reranker_increases_overlap_candidates() -> None:
    hits = [
        {"concept_id": "C1", "text": "binary bit", "score": 0.2},
        {"concept_id": "C2", "text": "truth table logic", "score": 0.19},
    ]
    reranked = rerank_hits("logic truth", hits, top_k=2)
    assert reranked[0]["concept_id"] == "C2"
