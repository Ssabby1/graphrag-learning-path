"""Import cleaned graph CSV data into Neo4j.

Default inputs:
- 章节数据/数据汇总/outputs/fixed/concepts_all.csv
- 章节数据/数据汇总/outputs/fixed/relations_all.csv

Example:
    python scripts/import_data.py --uri bolt://127.0.0.1:7687 --user neo4j --password xxx --clear-target
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONCEPTS = ROOT / "章节数据" / "数据汇总" / "outputs" / "fixed" / "concepts_all.csv"
DEFAULT_RELATIONS = ROOT / "章节数据" / "数据汇总" / "outputs" / "fixed" / "relations_all.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import graph data into Neo4j.")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--course-id", default="digital-logic")
    parser.add_argument("--course-name", default="Digital Logic")
    parser.add_argument("--concepts-csv", default=str(DEFAULT_CONCEPTS))
    parser.add_argument("--relations-csv", default=str(DEFAULT_RELATIONS))
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--clear-target",
        action="store_true",
        help="Clear Course/Chapter/Concept subgraph before importing.",
    )
    return parser.parse_args()


def split_multi(value: str | None) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    return [x.strip() for x in text.split("|") if x.strip()]


def to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_concepts(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            concept_id = (row.get("concept_id") or "").strip()
            if not concept_id:
                continue
            rows.append(
                {
                    "concept_id": concept_id,
                    "name": (row.get("name") or "").strip(),
                    "alias": split_multi(row.get("alias")),
                    "description": (row.get("description") or "").strip(),
                    "difficulty": (row.get("difficulty") or "").strip(),
                    "source_chapters": split_multi(row.get("source_chapters")),
                    "source_images": split_multi(row.get("source_images")),
                    "confidence_max": to_float(row.get("confidence_max"), 0.0),
                }
            )
    return rows


def load_relations(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_id = (row.get("from_concept_id") or "").strip()
            to_id = (row.get("to_concept_id") or "").strip()
            rel_type = (row.get("relation_type") or "").strip().upper()
            if not from_id or not to_id or not rel_type:
                continue
            rows.append(
                {
                    "from_concept_id": from_id,
                    "to_concept_id": to_id,
                    "relation_type": rel_type,
                    "evidence_text": (row.get("evidence_text") or "").strip(),
                    "source_images": split_multi(row.get("source_images")),
                    "confidence_max": to_float(row.get("confidence_max"), 0.0),
                }
            )
    return rows


def ensure_constraints(session) -> None:
    session.run(
        """
        CREATE CONSTRAINT concept_id_unique IF NOT EXISTS
        FOR (c:Concept)
        REQUIRE c.concept_id IS UNIQUE
        """
    )
    session.run(
        """
        CREATE CONSTRAINT chapter_name_unique IF NOT EXISTS
        FOR (ch:Chapter)
        REQUIRE ch.name IS UNIQUE
        """
    )
    session.run(
        """
        CREATE CONSTRAINT course_id_unique IF NOT EXISTS
        FOR (co:Course)
        REQUIRE co.course_id IS UNIQUE
        """
    )


def clear_target_subgraph(session) -> None:
    session.run(
        """
        MATCH (n)
        WHERE n:Concept OR n:Chapter OR n:Course
        DETACH DELETE n
        """
    )


def import_course(session, course_id: str, course_name: str) -> None:
    session.run(
        """
        MERGE (co:Course {course_id: $course_id})
        SET co.name = $course_name
        """,
        course_id=course_id,
        course_name=course_name,
    )


def import_concepts_and_chapters(session, course_id: str, batch: list[dict[str, Any]]) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (c:Concept {concept_id: row.concept_id})
        SET c.name = row.name,
            c.alias = row.alias,
            c.description = row.description,
            c.difficulty = row.difficulty,
            c.source_images = row.source_images,
            c.confidence_max = row.confidence_max
        WITH row, c
        UNWIND row.source_chapters AS chapter_name
        MERGE (ch:Chapter {name: chapter_name})
        MERGE (co:Course {course_id: $course_id})
        MERGE (co)-[:HAS_CHAPTER]->(ch)
        MERGE (ch)-[:HAS_CONCEPT]->(c)
        """,
        rows=batch,
        course_id=course_id,
    )


def import_relation_type(session, rel_type: str, rows: list[dict[str, Any]]) -> None:
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", rel_type):
        raise ValueError(f"Invalid relation_type for Cypher: {rel_type}")
    query = f"""
    UNWIND $rows AS row
    MATCH (a:Concept {{concept_id: row.from_concept_id}})
    MATCH (b:Concept {{concept_id: row.to_concept_id}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r.evidence_text = row.evidence_text,
        r.source_images = row.source_images,
        r.confidence_max = row.confidence_max
    """
    session.run(query, rows=rows)


def main() -> int:
    args = parse_args()
    if not args.password:
        print("ERROR: missing Neo4j password. Use --password or NEO4J_PASSWORD.")
        return 2

    concepts_path = Path(args.concepts_csv)
    relations_path = Path(args.relations_csv)
    if not concepts_path.exists():
        print(f"ERROR: concepts csv not found: {concepts_path}")
        return 2
    if not relations_path.exists():
        print(f"ERROR: relations csv not found: {relations_path}")
        return 2

    concepts = load_concepts(concepts_path)
    relations = load_relations(relations_path)

    print(f"Loaded concepts: {len(concepts)}")
    print(f"Loaded relations: {len(relations)}")

    driver = None
    try:
        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        with driver.session(database=args.database) as session:
            ensure_constraints(session)
            if args.clear_target:
                clear_target_subgraph(session)
                print("Cleared existing Course/Chapter/Concept subgraph.")

            import_course(session, args.course_id, args.course_name)
            for batch in chunked(concepts, max(1, args.batch_size)):
                import_concepts_and_chapters(session, args.course_id, batch)

            by_type: dict[str, list[dict[str, Any]]] = {}
            for r in relations:
                by_type.setdefault(r["relation_type"], []).append(r)

            for rel_type, rows in by_type.items():
                for batch in chunked(rows, max(1, args.batch_size)):
                    import_relation_type(session, rel_type, batch)

            concept_count = session.run("MATCH (c:Concept) RETURN count(c) AS n").single()["n"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]

        print(f"Import finished. Concepts in DB: {concept_count}")
        print(f"Import finished. Relations in DB: {rel_count}")
        return 0
    except Exception as exc:
        print(f"ERROR: import failed. {exc}")
        return 1
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    sys.exit(main())