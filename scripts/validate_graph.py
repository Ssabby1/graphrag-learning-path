"""Validate Neo4j graph quality for the learning-path project.

Usage example:
    python scripts/validate_graph.py --uri bolt://127.0.0.1:7687 \
        --user neo4j --password 12345678

Environment variables (optional):
    NEO4J_URI
    NEO4J_USER
    NEO4J_PASSWORD
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.graph.graph_snapshot import GraphSnapshot
from app.graph.prerequisite_index import PrerequisiteGraphIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate graph data quality in Neo4j and export a markdown report."
    )
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--concepts-csv", help="Validate a concept CSV without requiring Neo4j.")
    parser.add_argument("--relations-csv", help="Validate a relation CSV without requiring Neo4j.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="How many concept targets to sample for prerequisite sanity checks.",
    )
    parser.add_argument(
        "--max-cycle-depth",
        type=int,
        default=12,
        help="Deprecated compatibility option; cycle validation is now always unbounded/full.",
    )
    parser.add_argument(
        "--depth-threshold",
        type=int,
        default=8,
        help="Report how many targets have prerequisite depth above this threshold.",
    )
    parser.add_argument(
        "--report",
        default="docs/graph_validation_report.md",
        help="Report output path.",
    )
    parser.add_argument("--json-report", help="Optional machine-readable JSON report path.")
    return parser.parse_args()


def run_scalar(tx, query: str, **params: Any) -> Any:
    record = tx.run(query, **params).single()
    return None if record is None else record[0]


def run_rows(tx, query: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in tx.run(query, **params)]


def _find_cycle_examples(index: PrerequisiteGraphIndex, limit: int = 5) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    state: dict[str, int] = {node: 0 for node in index.concept_ids}
    stack: list[str] = []
    positions: dict[str, int] = {}

    def visit(node: str) -> None:
        if len(examples) >= limit:
            return
        state[node] = 1
        positions[node] = len(stack)
        stack.append(node)
        for neighbor in index.forward[node]:
            if state[neighbor] == 0:
                visit(neighbor)
            elif state[neighbor] == 1 and len(examples) < limit:
                cycle = stack[positions[neighbor] :] + [neighbor]
                if cycle not in [item["cycle_nodes"] for item in examples]:
                    examples.append({"cycle_nodes": cycle})
        stack.pop()
        positions.pop(node, None)
        state[node] = 2

    for concept_id in sorted(index.concept_ids):
        if state[concept_id] == 0:
            visit(concept_id)
    return examples


def analyze_prerequisite_graph(
    concept_rows: list[dict[str, Any]],
    relation_rows: list[dict[str, Any]],
    depth_threshold: int,
) -> dict[str, Any]:
    concept_ids = [str(row.get("concept_id") or "").strip() for row in concept_rows]
    valid_concepts = [item for item in concept_ids if item]
    raw_edges = [
        (str(row.get("from_id") or "").strip(), str(row.get("to_id") or "").strip())
        for row in relation_rows
        if str(row.get("from_id") or "").strip() and str(row.get("to_id") or "").strip()
    ]
    snapshot = GraphSnapshot.build(valid_concepts, raw_edges)
    index = PrerequisiteGraphIndex(snapshot)
    _, has_cycle = index.topological_sort(set(snapshot.concept_ids), snapshot.prerequisite_edges)
    cycle_examples = _find_cycle_examples(index)

    depths: dict[str, int] = {}
    closure_sizes: dict[str, int] = {}
    oracle_reverse = {node: set() for node in snapshot.concept_ids}
    for source, target in snapshot.prerequisite_edges:
        oracle_reverse[target].add(source)
    oracle_match_count = 0
    oracle_expected_total = 0
    oracle_returned_total = 0
    for target in snapshot.concept_ids:
        closure = index.closure(target, max_nodes=max(1, len(snapshot.concept_ids)), max_edges=max(1, len(snapshot.prerequisite_edges)))
        depths[target] = closure.max_depth
        closure_sizes[target] = max(0, len(closure.node_ids) - 1)
        expected: set[str] = set()
        pending = [target]
        while pending:
            node = pending.pop()
            for predecessor in oracle_reverse[node]:
                if predecessor not in expected:
                    expected.add(predecessor)
                    pending.append(predecessor)
        expected.discard(target)
        returned = set(closure.node_ids) - {target}
        oracle_match_count += returned == expected
        oracle_expected_total += len(expected)
        oracle_returned_total += len(returned & expected)

    evidence_present = sum(bool(str(row.get("evidence_text") or "").strip()) for row in relation_rows)
    source_images_present = sum(bool(row.get("source_images")) for row in relation_rows)
    confidence_present = sum(row.get("confidence_max") is not None for row in relation_rows)
    names = {str(row.get("concept_id") or "").strip(): row.get("name") or "" for row in concept_rows}
    return {
        "dataset_hash": snapshot.content_hash,
        "full_dag_check": not has_cycle,
        "cycle_example_count": len(cycle_examples),
        "cycle_examples": cycle_examples,
        "self_loop_count": sum(source == target for source, target in raw_edges),
        "duplicate_prerequisite_pair_count": len(raw_edges) - len(set(raw_edges)),
        "duplicate_prerequisite_examples": [
            {"from_id": source, "to_id": target, "cnt": count}
            for (source, target), count in sorted(Counter(raw_edges).items())
            if count > 1
        ][:10],
        "longest_path_edges": max(depths.values(), default=0) if not has_cycle else None,
        "depth_distribution": [
            {"depth": depth, "target_count": count} for depth, count in sorted(Counter(depths.values()).items())
        ],
        "targets_above_depth_threshold": sum(depth > depth_threshold for depth in depths.values()),
        "closure_stats": {
            "target_count": len(closure_sizes),
            "total_ancestor_references": sum(closure_sizes.values()),
            "min_ancestors": min(closure_sizes.values(), default=0),
            "max_ancestors": max(closure_sizes.values(), default=0),
            "average_ancestors": round(sum(closure_sizes.values()) / len(closure_sizes), 3) if closure_sizes else 0,
        },
        "oracle_closure_match_count": oracle_match_count,
        "oracle_closure_target_count": len(snapshot.concept_ids),
        "structural_closure_recall_numerator": oracle_returned_total,
        "structural_closure_recall_denominator": oracle_expected_total,
        "evidence_text_present_count": evidence_present,
        "source_images_present_count": source_images_present,
        "confidence_present_count": confidence_present,
        "relationship_provenance": "project_curated_input",
        "sample_targets": [
            {
                "target_concept_id": target,
                "target_name": names.get(target, ""),
                "prerequisite_count": closure_sizes[target],
                "max_depth": depths[target],
            }
            for target in sorted(snapshot.concept_ids)
        ],
    }


def collect_metrics(
    driver, database: str, sample_size: int, max_cycle_depth: int, depth_threshold: int = 8
) -> dict[str, Any]:
    del max_cycle_depth  # retained in the CLI only for backward compatibility
    metrics: dict[str, Any] = {}
    with driver.session(database=database) as session:
        labels = session.run("CALL db.labels() YIELD label RETURN collect(label) AS labels").single()["labels"]
        rel_types = session.run(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS rel_types"
        ).single()["rel_types"]
        metrics["labels"] = labels
        metrics["relationship_types"] = rel_types
        metrics["has_expected_schema"] = "Concept" in labels and "PREREQUISITE_OF" in rel_types
        metrics["node_count"] = session.execute_read(run_scalar, "MATCH (n) RETURN count(n)")
        metrics["edge_count"] = session.execute_read(run_scalar, "MATCH ()-[r]->() RETURN count(r)")
        metrics["relation_type_dist"] = session.execute_read(
            run_rows,
            "MATCH ()-[r]->() RETURN type(r) AS relation_type, count(r) AS cnt ORDER BY cnt DESC",
        )
        if not metrics["has_expected_schema"]:
            metrics.update(
                {
                    "concept_count": 0,
                    "prerequisite_edge_count": 0,
                    "concept_missing_id_count": 0,
                    "duplicate_concept_id_count": 0,
                    "orphan_concept_count": 0,
                    "isolated_concept_count": 0,
                    "full_dag_check": False,
                    "cycle_example_count": 0,
                    "cycle_examples": [],
                    "self_loop_count": 0,
                    "duplicate_prerequisite_pair_count": 0,
                    "duplicate_prerequisite_examples": [],
                    "sample_targets": [],
                    "dataset_hash": "",
                    "longest_path_edges": None,
                    "depth_distribution": [],
                    "targets_above_depth_threshold": 0,
                    "closure_stats": {},
                    "evidence_text_present_count": 0,
                    "source_images_present_count": 0,
                    "confidence_present_count": 0,
                    "relationship_provenance": "project_curated_input",
                }
            )
            return metrics

        concept_rows = session.execute_read(
            run_rows,
            "MATCH (c:Concept) RETURN c.concept_id AS concept_id, c.name AS name ORDER BY concept_id",
        )
        relation_rows = session.execute_read(
            run_rows,
            """
            MATCH (a:Concept)-[r:PREREQUISITE_OF]->(b:Concept)
            RETURN a.concept_id AS from_id, b.concept_id AS to_id,
                   r.evidence_text AS evidence_text, r.source_images AS source_images,
                   r.confidence_max AS confidence_max,
                   r.verification_status AS verification_status
            ORDER BY from_id, to_id
            """,
        )
        metrics["concept_count"] = len(concept_rows)
        metrics["prerequisite_edge_count"] = len(relation_rows)
        metrics["concept_missing_id_count"] = session.execute_read(
            run_scalar,
            'MATCH (c:Concept) WHERE c.concept_id IS NULL OR trim(toString(c.concept_id)) = "" RETURN count(c)',
        )
        metrics["duplicate_concept_id_count"] = session.execute_read(
            run_scalar,
            """MATCH (c:Concept) WHERE c.concept_id IS NOT NULL
            WITH c.concept_id AS cid, count(*) AS cnt WHERE cnt > 1 RETURN count(cid)""",
        )
        metrics["orphan_concept_count"] = session.execute_read(
            run_scalar, "MATCH (c:Concept) WHERE NOT ()-[:HAS_CONCEPT]->(c) RETURN count(c)"
        )
        metrics["isolated_concept_count"] = session.execute_read(
            run_scalar, "MATCH (c:Concept) WHERE NOT (c)-[]-() RETURN count(c)"
        )
        analysis = analyze_prerequisite_graph(concept_rows, relation_rows, depth_threshold)
        analysis["sample_targets"] = analysis["sample_targets"][: max(0, sample_size)]
        metrics.update(analysis)
    return metrics


def collect_csv_metrics(
    concepts_path: Path, relations_path: Path, sample_size: int, depth_threshold: int
) -> dict[str, Any]:
    with concepts_path.open(encoding="utf-8-sig", newline="") as handle:
        concept_rows = list(csv.DictReader(handle))
    with relations_path.open(encoding="utf-8-sig", newline="") as handle:
        all_relations = list(csv.DictReader(handle))
    prerequisite_rows = [
        {
            "from_id": row.get("from_concept_id"),
            "to_id": row.get("to_concept_id"),
            "evidence_text": row.get("evidence_text"),
            "source_images": row.get("source_images"),
            "confidence_max": row.get("confidence_max") or None,
            "verification_status": row.get("verification_status"),
        }
        for row in all_relations
        if (row.get("relation_type") or "").strip() == "PREREQUISITE_OF"
    ]
    metrics: dict[str, Any] = {
        "labels": ["Concept"],
        "relationship_types": sorted(
            {(row.get("relation_type") or "").strip() for row in all_relations if row.get("relation_type")}
        ),
        "has_expected_schema": bool(concept_rows and prerequisite_rows),
        "concept_count": len(concept_rows),
        "node_count": len(concept_rows),
        "edge_count": len(all_relations),
        "prerequisite_edge_count": len(prerequisite_rows),
        "concept_missing_id_count": sum(not (row.get("concept_id") or "").strip() for row in concept_rows),
        "duplicate_concept_id_count": sum(
            count > 1
            for concept_id, count in Counter(
                (row.get("concept_id") or "").strip() for row in concept_rows if (row.get("concept_id") or "").strip()
            ).items()
        ),
        "orphan_concept_count": "not_available_in_csv_profile",
        "isolated_concept_count": "not_available_in_csv_profile",
        "relation_type_dist": [
            {"relation_type": relation_type, "cnt": count}
            for relation_type, count in Counter(
                (row.get("relation_type") or "").strip() for row in all_relations
            ).most_common()
        ],
    }
    analysis = analyze_prerequisite_graph(concept_rows, prerequisite_rows, depth_threshold)
    analysis["sample_targets"] = analysis["sample_targets"][: max(0, sample_size)]
    metrics.update(analysis)
    return metrics


def build_report(metrics: dict[str, Any], args: argparse.Namespace) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hard_fail_checks = {
        "has_expected_schema": metrics.get("has_expected_schema", False),
        "full_dag_check": metrics.get("full_dag_check", False),
        "duplicate_prerequisite_pair_count": metrics["duplicate_prerequisite_pair_count"] == 0,
        "self_loop_count": metrics["self_loop_count"] == 0,
        "concept_missing_id_count": metrics["concept_missing_id_count"] == 0,
        "duplicate_concept_id_count": metrics["duplicate_concept_id_count"] == 0,
    }
    overall_pass = all(hard_fail_checks.values())

    lines: list[str] = []
    lines.append("# Graph Validation Report")
    lines.append("")
    lines.append(f"- Generated at: `{now}`")
    if args.concepts_csv:
        lines.append(f"- Concepts CSV: `{args.concepts_csv}`")
        lines.append(f"- Relations CSV: `{args.relations_csv}`")
    else:
        lines.append(f"- URI: `{args.uri}`")
        lines.append(f"- Database: `{args.database}`")
    lines.append(f"- Sample size: `{args.sample_size}`")
    lines.append("- Cycle validation: `full graph (unbounded)`")
    lines.append(f"- Depth reporting threshold: `{args.depth_threshold}`")
    lines.append(f"- Overall result: `{'PASS' if overall_pass else 'FAIL'}`")
    lines.append("")

    if not metrics.get("has_expected_schema", True):
        lines.append("## Schema Check")
        lines.append("")
        lines.append(
            "- Expected `Concept` label and `PREREQUISITE_OF` relationship type were not both found."
        )
        lines.append(f"- Found labels: `{metrics.get('labels', [])}`")
        lines.append(f"- Found relationship types: `{metrics.get('relationship_types', [])}`")
        lines.append("- Conclusion: graph data may not be imported into this database yet.")
        lines.append("")

    lines.append("## Summary Metrics")
    lines.append("")
    lines.append(f"- Concept nodes: `{metrics['concept_count']}`")
    lines.append(f"- Total nodes: `{metrics['node_count']}`")
    lines.append(f"- Total relations: `{metrics['edge_count']}`")
    lines.append(f"- PREREQUISITE_OF relations: `{metrics['prerequisite_edge_count']}`")
    lines.append(f"- Missing concept_id: `{metrics['concept_missing_id_count']}`")
    lines.append(f"- Duplicate concept_id groups: `{metrics['duplicate_concept_id_count']}`")
    lines.append(
        f"- Duplicate PREREQUISITE_OF pairs: `{metrics['duplicate_prerequisite_pair_count']}`"
    )
    lines.append(f"- PREREQUISITE_OF self loops: `{metrics['self_loop_count']}`")
    lines.append(f"- Concepts without HAS_CONCEPT parent: `{metrics['orphan_concept_count']}`")
    lines.append(f"- Fully isolated concepts: `{metrics['isolated_concept_count']}`")
    lines.append(f"- Full DAG check: `{'PASS' if metrics.get('full_dag_check') else 'FAIL'}`")
    lines.append(f"- Cycle examples found: `{metrics['cycle_example_count']}`")
    lines.append(f"- Longest prerequisite path (edges): `{metrics.get('longest_path_edges')}`")
    lines.append(
        f"- Targets deeper than {args.depth_threshold}: `{metrics.get('targets_above_depth_threshold', 0)}`"
    )
    lines.append(f"- Dataset hash (SHA-256): `{metrics.get('dataset_hash', '')}`")
    lines.append(
        f"- Independent oracle closure matches: `{metrics.get('oracle_closure_match_count', 0)}` / `{metrics.get('oracle_closure_target_count', 0)}`"
    )
    recall_denominator = metrics.get("structural_closure_recall_denominator", 0)
    recall_numerator = metrics.get("structural_closure_recall_numerator", 0)
    recall_value = recall_numerator / recall_denominator if recall_denominator else 1.0
    lines.append(
        f"- Structural Closure Recall: `{recall_numerator}` / `{recall_denominator}` = `{recall_value:.1%}`"
    )
    lines.append(
        f"- Relationship evidence_text present: `{metrics.get('evidence_text_present_count', 0)}` / `{metrics['prerequisite_edge_count']}`"
    )
    lines.append(
        f"- Relationship source_images present: `{metrics.get('source_images_present_count', 0)}` / `{metrics['prerequisite_edge_count']}`"
    )
    lines.append(
        f"- Relationship confidence_max present: `{metrics.get('confidence_present_count', 0)}` / `{metrics['prerequisite_edge_count']}`"
    )
    lines.append(
        f"- Relationship provenance: `{metrics.get('relationship_provenance', 'project_curated_input')}`"
    )
    lines.append("")

    lines.append("## Ancestor Closure Statistics")
    lines.append("")
    closure_stats = metrics.get("closure_stats", {})
    for key in (
        "target_count",
        "total_ancestor_references",
        "min_ancestors",
        "max_ancestors",
        "average_ancestors",
    ):
        lines.append(f"- {key}: `{closure_stats.get(key, 0)}`")
    lines.append("")

    lines.append("## Prerequisite Depth Distribution")
    lines.append("")
    lines.append("| depth_edges | target_count |")
    lines.append("| ---: | ---: |")
    for row in metrics.get("depth_distribution", []):
        lines.append(f"| {row['depth']} | {row['target_count']} |")
    lines.append("")

    lines.append("## Hard-Fail Checks")
    lines.append("")
    for check_name, passed in hard_fail_checks.items():
        lines.append(f"- `{check_name}`: `{'PASS' if passed else 'FAIL'}`")
    lines.append("")

    lines.append("## Relation Type Distribution")
    lines.append("")
    lines.append("| relation_type | count |")
    lines.append("| --- | ---: |")
    for row in metrics["relation_type_dist"]:
        lines.append(f"| {row['relation_type']} | {row['cnt']} |")
    lines.append("")

    lines.append("## Duplicate PREREQUISITE_OF Examples")
    lines.append("")
    if metrics["duplicate_prerequisite_examples"]:
        lines.append("| from_id | to_id | duplicate_count |")
        lines.append("| --- | --- | ---: |")
        for row in metrics["duplicate_prerequisite_examples"]:
            lines.append(f"| {row['from_id']} | {row['to_id']} | {row['cnt']} |")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Cycle Examples")
    lines.append("")
    if metrics["cycle_examples"]:
        for row in metrics["cycle_examples"]:
            lines.append(f"- {' -> '.join(row['cycle_nodes'])}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Deterministic Target Prerequisite Sample")
    lines.append("")
    lines.append("| target_concept_id | target_name | prerequisite_count | max_depth |")
    lines.append("| --- | --- | ---: | ---: |")
    for row in metrics["sample_targets"]:
        lines.append(
            f"| {row['target_concept_id']} | {row['target_name']} | {row['prerequisite_count']} | {row['max_depth']} |"
        )
    lines.append("")
    lines.append(
        "> Chapter-level prerequisite relationships were curated from course materials; structural validation and AI-assisted plausibility checks are reported separately."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if bool(args.concepts_csv) != bool(args.relations_csv):
        print("ERROR: --concepts-csv and --relations-csv must be provided together.")
        return 2
    if not args.concepts_csv and not args.password:
        print("ERROR: missing Neo4j password. Use --password or set NEO4J_PASSWORD.")
        return 2

    driver = None
    try:
        if args.concepts_csv:
            metrics = collect_csv_metrics(
                Path(args.concepts_csv), Path(args.relations_csv), args.sample_size, args.depth_threshold
            )
        else:
            driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
            metrics = collect_metrics(
                driver=driver,
                database=args.database,
                sample_size=args.sample_size,
                max_cycle_depth=args.max_cycle_depth,
                depth_threshold=args.depth_threshold,
            )
    except Exception as exc:
        print(f"ERROR: failed to validate graph. {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass

    report = build_report(metrics, args)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"Validation report written to: {report_path}")
    if args.json_report:
        json_path = Path(args.json_report)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(
                {
                    "report_version": "1.0",
                    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "input_profile": "csv" if args.concepts_csv else "neo4j",
                    "depth_threshold": args.depth_threshold,
                    "metrics": metrics,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"JSON validation report written to: {json_path}")
    print(
        "Summary: "
        f"cycles={metrics['cycle_example_count']}, "
        f"duplicate_pairs={metrics['duplicate_prerequisite_pair_count']}, "
        f"self_loops={metrics['self_loop_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
