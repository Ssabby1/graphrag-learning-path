import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.metrics import latency_summary, reciprocal_rank, safe_ratio


DATASET_FIELDS = {
    "target_resolver.jsonl": {
        "case_id",
        "question",
        "acceptable_target_ids",
        "should_reject",
        "query_language",
        "tags",
    },
    "path_planner.jsonl": {
        "case_id",
        "target_concept_id",
        "mastered_concepts",
        "required_prerequisite_ids",
        "forbidden_ids",
        "curation_status",
    },
    "evidence_retriever.jsonl": {
        "case_id",
        "question",
        "target_concept_id",
        "path",
        "relevant_evidence_ids",
        "graded_relevance",
    },
    "answer_generator.jsonl": {
        "case_id",
        "question",
        "response_language",
        "expected_answer_language",
        "target_concept_id",
        "path",
        "evidence_pack",
        "required_citation_ids",
    },
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_eval_datasets_have_unique_cases_and_required_fields() -> None:
    dataset_dir = ROOT / "evals/datasets"
    for filename, required_fields in DATASET_FIELDS.items():
        rows = _load_jsonl(dataset_dir / filename)
        assert rows, filename
        assert len({row["case_id"] for row in rows}) == len(rows), filename
        assert all(required_fields <= row.keys() for row in rows), filename


def test_target_dataset_covers_languages_and_rejections() -> None:
    rows = _load_jsonl(ROOT / "evals/datasets/target_resolver.jsonl")
    assert {row["query_language"] for row in rows} >= {"zh", "en", "mixed"}
    assert any(row["should_reject"] for row in rows)
    assert any(not row["should_reject"] for row in rows)


def test_evidence_ids_are_relationship_ids() -> None:
    rows = _load_jsonl(ROOT / "evals/datasets/evidence_retriever.jsonl")
    evidence_ids = [item for row in rows for item in row["relevant_evidence_ids"]]
    assert evidence_ids
    assert all(item.startswith("prereq:") for item in evidence_ids)


def test_metrics_keep_counts_and_percentiles() -> None:
    assert safe_ratio(2, 4) == {"numerator": 2, "denominator": 4, "value": 0.5}
    assert reciprocal_rank(["A", "B", "C"], {"B"}) == 0.5
    assert latency_summary([1.0, 2.0, 3.0])["p50_ms"] == 2.0
