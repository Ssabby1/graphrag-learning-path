"""Read-only GraphRepository adapter for the redistributable public sample."""

from __future__ import annotations

import csv
from pathlib import Path

from app.graph.graph_snapshot import GraphSnapshot
from app.graph.prerequisite_index import PrerequisiteGraphIndex


def _split(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split("|") if item.strip()]


class CsvGraphRepository:
    def __init__(self, concepts_csv: str | Path, relations_csv: str | Path) -> None:
        self.concepts_path = Path(concepts_csv).resolve()
        self.relations_path = Path(relations_csv).resolve()
        with self.concepts_path.open(encoding="utf-8-sig", newline="") as handle:
            self.concepts = [dict(row) for row in csv.DictReader(handle)]
        with self.relations_path.open(encoding="utf-8-sig", newline="") as handle:
            self.relations = [dict(row) for row in csv.DictReader(handle)]
        self.by_id = {row["concept_id"]: row for row in self.concepts}
        self.snapshot = GraphSnapshot.build(
            self.by_id,
            [(row["from_concept_id"], row["to_concept_id"]) for row in self.relations if row["relation_type"] == "PREREQUISITE_OF"],
        )

    def close(self) -> None:
        return None

    def get_graph_overview(self) -> dict[str, int]:
        chapters = {chapter for row in self.concepts for chapter in _split(row.get("source_chapters"))}
        return {"course_count": 1, "chapter_count": len(chapters), "concept_count": len(self.concepts), "prerequisite_rel_count": sum(row["relation_type"] == "PREREQUISITE_OF" for row in self.relations)}

    def get_concept_corpus(self, limit: int = 2000) -> list[dict]:
        predecessors: dict[str, list[str]] = {item: [] for item in self.by_id}
        successors: dict[str, list[str]] = {item: [] for item in self.by_id}
        for row in self.relations:
            source, target = row["from_concept_id"], row["to_concept_id"]
            predecessors[target].append(self.by_id[source]["name"])
            successors[source].append(self.by_id[target]["name"])
        return [{"concept_id": row["concept_id"], "name": row.get("name", ""), "name_en": row.get("name_en", ""), "aliases": _split(row.get("alias")), "aliases_en": _split(row.get("aliases_en")), "description": row.get("description", ""), "description_en": row.get("description_en", ""), "difficulty": row.get("difficulty", ""), "source_chapters": _split(row.get("source_chapters")), "predecessor_names": predecessors[row["concept_id"]], "successor_names": successors[row["concept_id"]]} for row in self.concepts[:limit]]

    def get_concept_detail(self, concept_id: str) -> dict | None:
        row = self.by_id.get(concept_id)
        if row is None:
            return None
        prerequisites = [item["from_concept_id"] for item in self.relations if item["to_concept_id"] == concept_id and item["relation_type"] == "PREREQUISITE_OF"]
        successors = [item["to_concept_id"] for item in self.relations if item["from_concept_id"] == concept_id and item["relation_type"] == "PREREQUISITE_OF"]
        chapters = _split(row.get("source_chapters"))
        return {"concept_id": concept_id, "name": row.get("name"), "description": row.get("description"), "chapter_id": None, "chapter_name": chapters[0] if chapters else None, "prerequisites": prerequisites, "successors": successors}

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        closure = PrerequisiteGraphIndex(self.snapshot).closure(target=target_concept_id, max_nodes=2000, max_edges=10000)
        return {"target_exists": closure.target_exists, "target_concept_id": target_concept_id, "node_ids": list(closure.node_ids), "edges": list(closure.edges), "has_cycle": closure.has_cycle, "truncated": closure.truncated, "max_depth": closure.max_depth, "omitted_node_count": closure.omitted_node_count, "omitted_edge_count": closure.omitted_edge_count, "dataset_hash": closure.content_hash, "planner_strategy": "csv_graph_ancestor_closure"}

    def get_relation_corpus(self, relation_types=("PREREQUISITE_OF", "RELATED_TO")) -> list[dict]:
        rows = []
        for row in self.relations:
            if row["relation_type"] not in relation_types:
                continue
            source, target = self.by_id[row["from_concept_id"]], self.by_id[row["to_concept_id"]]
            rows.append({"from_concept_id": source["concept_id"], "from_name": source["name"], "from_name_en": source.get("name_en", ""), "to_concept_id": target["concept_id"], "to_name": target["name"], "to_name_en": target.get("name_en", ""), "relation_type": row["relation_type"], "evidence_text": row.get("evidence_text", ""), "source_images": _split(row.get("source_images")), "confidence_max": float(row.get("confidence_max") or 0), "verification_status": row.get("verification_status") or "unreviewed", "source_chapters": sorted(set(_split(source.get("source_chapters")) + _split(target.get("source_chapters"))))})
        return rows
