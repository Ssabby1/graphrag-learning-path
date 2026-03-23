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
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate graph data quality in Neo4j and export a markdown report."
    )
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
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
        help="Max relationship depth when searching for PREREQUISITE_OF cycles.",
    )
    parser.add_argument(
        "--report",
        default="docs/graph_validation_report.md",
        help="Report output path.",
    )
    return parser.parse_args()


def run_scalar(tx, query: str, **params: Any) -> Any:
    record = tx.run(query, **params).single()
    return None if record is None else record[0]


def run_rows(tx, query: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in tx.run(query, **params)]


def collect_metrics(
    driver, database: str, sample_size: int, max_cycle_depth: int
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    depth = max(1, int(max_cycle_depth))
    cycle_count_query = (
        f"MATCH p=(c:Concept)-[:PREREQUISITE_OF*1..{depth}]->(c) RETURN count(p)"
    )
    cycle_examples_query = (
        "MATCH p=(c:Concept)-[:PREREQUISITE_OF*1.."
        f"{depth}"
        "]->(c) "
        'RETURN [n IN nodes(p) | coalesce(n.concept_id, n.name, "UNKNOWN")] AS cycle_nodes '
        "LIMIT 5"
    )

    with driver.session(database=database) as session:
        labels = session.run("CALL db.labels() YIELD label RETURN collect(label) AS labels").single()[
            "labels"
        ]
        rel_types = session.run(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS rel_types"
        ).single()["rel_types"]
        metrics["labels"] = labels
        metrics["relationship_types"] = rel_types

        has_concept = "Concept" in labels
        has_prereq = "PREREQUISITE_OF" in rel_types
        metrics["has_expected_schema"] = bool(has_concept and has_prereq)

        if not metrics["has_expected_schema"]:
            metrics["concept_count"] = 0
            metrics["node_count"] = session.execute_read(
                run_scalar, "MATCH (n) RETURN count(n)"
            )
            metrics["edge_count"] = session.execute_read(
                run_scalar, "MATCH ()-[r]->() RETURN count(r)"
            )
            metrics["prerequisite_edge_count"] = 0
            metrics["concept_missing_id_count"] = 0
            metrics["duplicate_concept_id_count"] = 0
            metrics["duplicate_prerequisite_pair_count"] = 0
            metrics["self_loop_count"] = 0
            metrics["orphan_concept_count"] = 0
            metrics["isolated_concept_count"] = 0
            metrics["cycle_example_count"] = 0
            metrics["relation_type_dist"] = session.execute_read(
                run_rows,
                """
                MATCH ()-[r]->()
                RETURN type(r) AS relation_type, count(r) AS cnt
                ORDER BY cnt DESC
                """,
            )
            metrics["duplicate_prerequisite_examples"] = []
            metrics["cycle_examples"] = []
            metrics["sample_targets"] = []
            return metrics

        metrics["concept_count"] = session.execute_read(
            run_scalar, "MATCH (c:Concept) RETURN count(c)"
        )
        metrics["node_count"] = session.execute_read(
            run_scalar, "MATCH (n) RETURN count(n)"
        )
        metrics["edge_count"] = session.execute_read(
            run_scalar, "MATCH ()-[r]->() RETURN count(r)"
        )
        metrics["prerequisite_edge_count"] = session.execute_read(
            run_scalar, "MATCH ()-[r:PREREQUISITE_OF]->() RETURN count(r)"
        )
        metrics["concept_missing_id_count"] = session.execute_read(
            run_scalar,
            """
            MATCH (c:Concept)
            WHERE c.concept_id IS NULL OR trim(toString(c.concept_id)) = ""
            RETURN count(c)
            """,
        )
        metrics["duplicate_concept_id_count"] = session.execute_read(
            run_scalar,
            """
            MATCH (c:Concept)
            WHERE c.concept_id IS NOT NULL AND trim(toString(c.concept_id)) <> ""
            WITH c.concept_id AS cid, count(*) AS cnt
            WHERE cnt > 1
            RETURN count(cid)
            """,
        )
        metrics["duplicate_prerequisite_pair_count"] = session.execute_read(
            run_scalar,
            """
            MATCH (a:Concept)-[r:PREREQUISITE_OF]->(b:Concept)
            WITH a.concept_id AS from_id, b.concept_id AS to_id, count(r) AS cnt
            WHERE cnt > 1
            RETURN count(*)
            """,
        )
        metrics["self_loop_count"] = session.execute_read(
            run_scalar,
            """
            MATCH (c:Concept)-[:PREREQUISITE_OF]->(c)
            RETURN count(c)
            """,
        )
        metrics["orphan_concept_count"] = session.execute_read(
            run_scalar,
            """
            MATCH (c:Concept)
            WHERE NOT ()-[:HAS_CONCEPT]->(c)
            RETURN count(c)
            """,
        )
        metrics["isolated_concept_count"] = session.execute_read(
            run_scalar,
            """
            MATCH (c:Concept)
            WHERE NOT (c)-[]-()
            RETURN count(c)
            """,
        )
        metrics["cycle_example_count"] = session.execute_read(run_scalar, cycle_count_query)
        metrics["relation_type_dist"] = session.execute_read(
            run_rows,
            """
            MATCH ()-[r]->()
            RETURN type(r) AS relation_type, count(r) AS cnt
            ORDER BY cnt DESC
            """,
        )
        metrics["duplicate_prerequisite_examples"] = session.execute_read(
            run_rows,
            """
            MATCH (a:Concept)-[r:PREREQUISITE_OF]->(b:Concept)
            WITH a.concept_id AS from_id, b.concept_id AS to_id, count(r) AS cnt
            WHERE cnt > 1
            RETURN from_id, to_id, cnt
            ORDER BY cnt DESC, from_id, to_id
            LIMIT 10
            """,
        )
        metrics["cycle_examples"] = session.execute_read(run_rows, cycle_examples_query)
        metrics["sample_targets"] = session.execute_read(
            run_rows,
            """
            MATCH (t:Concept)
            WITH t ORDER BY rand() LIMIT $sample_size
            OPTIONAL MATCH (pre:Concept)-[:PREREQUISITE_OF*1..20]->(t)
            RETURN
              t.concept_id AS target_concept_id,
              t.name AS target_name,
              count(DISTINCT pre) AS prerequisite_count
            ORDER BY prerequisite_count DESC, target_concept_id
            """,
            sample_size=sample_size,
        )
    return metrics


def build_report(metrics: dict[str, Any], args: argparse.Namespace) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hard_fail_checks = {
        "has_expected_schema": metrics.get("has_expected_schema", False),
        "cycle_example_count": metrics["cycle_example_count"] == 0,
        "duplicate_prerequisite_pair_count": metrics["duplicate_prerequisite_pair_count"] == 0,
        "self_loop_count": metrics["self_loop_count"] == 0,
        "concept_missing_id_count": metrics["concept_missing_id_count"] == 0,
        "duplicate_concept_id_count": metrics["duplicate_concept_id_count"] == 0,
    }
    overall_pass = all(hard_fail_checks.values())

    lines: list[str] = []
    lines.append("# Neo4j Graph Validation Report")
    lines.append("")
    lines.append(f"- Generated at: `{now}`")
    lines.append(f"- URI: `{args.uri}`")
    lines.append(f"- Database: `{args.database}`")
    lines.append(f"- Sample size: `{args.sample_size}`")
    lines.append(f"- Max cycle depth: `{args.max_cycle_depth}`")
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
    lines.append(
        f"- Cycle path matches (<= depth {args.max_cycle_depth}): `{metrics['cycle_example_count']}`"
    )
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

    lines.append("## Sampled Target Prerequisite Counts")
    lines.append("")
    lines.append("| target_concept_id | target_name | prerequisite_count |")
    lines.append("| --- | --- | ---: |")
    for row in metrics["sample_targets"]:
        lines.append(
            f"| {row['target_concept_id']} | {row['target_name']} | {row['prerequisite_count']} |"
        )
    lines.append("")
    lines.append(
        "> Manual check suggestion: randomly pick 20 PREREQUISITE_OF rows and verify against source material."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if not args.password:
        print("ERROR: missing Neo4j password. Use --password or set NEO4J_PASSWORD.")
        return 2

    driver = None
    try:
        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        metrics = collect_metrics(
            driver=driver,
            database=args.database,
            sample_size=args.sample_size,
            max_cycle_depth=args.max_cycle_depth,
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
    print(
        "Summary: "
        f"cycles={metrics['cycle_example_count']}, "
        f"duplicate_pairs={metrics['duplicate_prerequisite_pair_count']}, "
        f"self_loops={metrics['self_loop_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
