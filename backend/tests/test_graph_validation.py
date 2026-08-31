import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_graph import analyze_prerequisite_graph


def test_graph_analysis_reports_full_depth_hash_and_evidence_completeness() -> None:
    concepts = [
        {"concept_id": "A", "name": "A"},
        {"concept_id": "B", "name": "B"},
        {"concept_id": "C", "name": "C"},
        {"concept_id": "T", "name": "T"},
    ]
    relations = [
        {
            "from_id": source,
            "to_id": target,
            "evidence_text": "evidence",
            "source_images": ["image"],
            "confidence_max": 0.9,
            "verification_status": "human_verified" if source == "C" else "unreviewed",
        }
        for source, target in [("A", "B"), ("B", "C"), ("C", "T")]
    ]

    metrics = analyze_prerequisite_graph(concepts, relations, depth_threshold=2)

    assert metrics["full_dag_check"] is True
    assert metrics["longest_path_edges"] == 3
    assert metrics["targets_above_depth_threshold"] == 1
    assert metrics["closure_stats"]["max_ancestors"] == 3
    assert metrics["oracle_closure_match_count"] == 4
    assert metrics["structural_closure_recall_numerator"] == 6
    assert metrics["structural_closure_recall_denominator"] == 6
    assert len(metrics["dataset_hash"]) == 64
    assert metrics["evidence_text_present_count"] == 3
    assert metrics["human_verified_relation_count"] == 1


def test_graph_analysis_detects_arbitrary_cycle_and_self_loop() -> None:
    concepts = [{"concept_id": item, "name": item} for item in ["A", "B", "C"]]
    relations = [
        {"from_id": "A", "to_id": "B"},
        {"from_id": "B", "to_id": "C"},
        {"from_id": "C", "to_id": "A"},
        {"from_id": "C", "to_id": "C"},
    ]

    metrics = analyze_prerequisite_graph(concepts, relations, depth_threshold=8)

    assert metrics["full_dag_check"] is False
    assert metrics["cycle_example_count"] >= 1
    assert metrics["self_loop_count"] == 1
    assert metrics["longest_path_edges"] is None
