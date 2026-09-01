"""Build or refresh a deterministic AI-assisted quality queue for core prerequisite edges."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

FIELDS = [
    "evidence_id",
    "from_concept_id",
    "from_name",
    "to_concept_id",
    "to_name",
    "relation_type",
    "evidence_text",
    "source_images",
    "confidence_max",
    "core_score",
    "check_status",
    "checked_by",
    "checked_at",
    "check_notes",
]
ALLOWED_STATUSES = {
    "pending",
    "ai_plausible",
    "needs_relation_revision",
    "likely_wrong_direction",
    "likely_unrelated",
    "needs_source_check",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concepts-csv", required=True)
    parser.add_argument("--relations-csv", required=True)
    parser.add_argument("--output", default="output/relationship_quality_queue.csv")
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 30 <= args.limit <= 50:
        raise SystemExit("--limit must be between 30 and 50")

    concepts = {
        row["concept_id"].strip(): (row.get("name") or "").strip()
        for row in read_rows(Path(args.concepts_csv))
        if (row.get("concept_id") or "").strip()
    }
    relations = [
        row
        for row in read_rows(Path(args.relations_csv))
        if (row.get("relation_type") or "").strip() == "PREREQUISITE_OF"
    ]
    degree: Counter[str] = Counter()
    for row in relations:
        degree[(row.get("from_concept_id") or "").strip()] += 1
        degree[(row.get("to_concept_id") or "").strip()] += 1

    output = Path(args.output)
    existing: dict[str, dict[str, str]] = {}
    if output.exists():
        existing = {row.get("evidence_id", ""): row for row in read_rows(output)}

    ranked = sorted(
        relations,
        key=lambda row: (
            -(degree[(row.get("from_concept_id") or "").strip()] + degree[(row.get("to_concept_id") or "").strip()]),
            (row.get("from_concept_id") or "").strip(),
            (row.get("to_concept_id") or "").strip(),
        ),
    )[: args.limit]

    queue: list[dict[str, str | int]] = []
    for row in ranked:
        source = (row.get("from_concept_id") or "").strip()
        target = (row.get("to_concept_id") or "").strip()
        item_id = f"prereq:{source}:{target}"
        prior = existing.get(item_id, {})
        status = (prior.get("check_status") or "pending").strip()
        if status not in ALLOWED_STATUSES:
            raise SystemExit(f"Invalid check_status {status!r} for {item_id}")
        queue.append(
            {
                "evidence_id": item_id,
                "from_concept_id": source,
                "from_name": concepts.get(source, ""),
                "to_concept_id": target,
                "to_name": concepts.get(target, ""),
                "relation_type": "PREREQUISITE_OF",
                "evidence_text": (row.get("evidence_text") or "").strip(),
                "source_images": (row.get("source_images") or "").strip(),
                "confidence_max": (row.get("confidence_max") or "").strip(),
                "core_score": degree[source] + degree[target],
                "check_status": status,
                "checked_by": prior.get("checked_by", ""),
                "checked_at": prior.get("checked_at", ""),
                "check_notes": prior.get("check_notes", ""),
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(queue)

    counts = Counter(str(row["check_status"]) for row in queue)
    print(f"Wrote {len(queue)} core prerequisite relationships to {output}")
    print("Check status: " + ", ".join(f"{name}={counts.get(name, 0)}" for name in sorted(ALLOWED_STATUSES)))


if __name__ == "__main__":
    main()
