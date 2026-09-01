"""Reproduce GraphRAG status-gating and long-path evidence coverage checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for entry in (str(BACKEND), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

os.environ["EMBEDDING_BACKEND"] = "unicode_hashing"
os.environ["LLM_ENABLED"] = "false"

from app.core.errors import TargetConceptNotFoundError  # noqa: E402
from app.services.graphrag_service import query_graphrag  # noqa: E402


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


class ContractRepository:
    def __init__(self, mode: str = "long") -> None:
        self.mode = mode
        self.nodes, self.edges = self._graph()

    @staticmethod
    def _graph() -> tuple[list[str], list[tuple[str, str]]]:
        nodes = [f"C{index:03d}" for index in range(1, 43)]
        edges = list(zip(nodes, nodes[1:]))
        for source_index, source in enumerate(nodes):
            for target in nodes[source_index + 2 :]:
                edge = (source, target)
                if edge not in edges:
                    edges.append(edge)
                if len(edges) == 107:
                    return nodes, edges
        raise RuntimeError("Unable to build the 107-edge fixture")

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict:
        if self.mode == "not_found":
            return {"target_exists": False, "node_ids": [], "edges": []}
        payload = {
            "target_exists": True,
            "target_concept_id": target_concept_id,
            "node_ids": self.nodes,
            "edges": self.edges,
            "max_depth": 41,
            "planner_strategy": "contract_fixture",
        }
        if self.mode == "truncated":
            payload.update(truncated=True, omitted_node_count=1)
        elif self.mode == "cycle":
            payload["edges"] = [*self.edges, (self.nodes[1], self.nodes[0])]
            payload["has_cycle"] = True
        return payload

    def get_relation_corpus(self, relation_types=("PREREQUISITE_OF",)) -> list[dict]:
        return [
            {
                "from_concept_id": source,
                "from_name": source,
                "to_concept_id": target,
                "to_name": target,
                "relation_type": "PREREQUISITE_OF",
                "evidence_text": f"{source} supports {target}.",
                "source_chapters": ["Contract Fixture"],
                "source_images": [],
                "confidence_max": 1.0,
                "verification_status": "contract_fixture",
            }
            for source, target in self.edges
        ]


def _query(repo: ContractRepository, mastered: list[str] | None = None) -> dict:
    return query_graphrag(
        question="How should I learn C042?",
        target_concept_id="C042",
        mastered_concepts=mastered or [],
        repo=repo,
        response_language="en",
    )


def main() -> int:
    not_found_rejected = False
    try:
        _query(ContractRepository("not_found"))
    except TargetConceptNotFoundError:
        not_found_rejected = True

    mastered = _query(ContractRepository(), ["C042"])
    truncated = _query(ContractRepository("truncated"))
    cycle = _query(ContractRepository("cycle"))
    long_path = _query(ContractRepository())
    meta = long_path["meta"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "fixture": {"path_nodes": 42, "path_edges": 107, "answer_evidence_limit": 8},
        "status_gates": {
            "not_found_rejected": not_found_rejected,
            "already_mastered": mastered["status"] == "already_mastered" and mastered["answer_source"] == "system",
            "truncated": truncated["status"] == "truncated" and truncated["answer_source"] == "system",
            "cycle": cycle["status"] == "cycle" and cycle["answer_source"] == "system",
        },
        "evidence_coverage": {
            "path_node_count": len(long_path["path"]),
            "path_edge_count": meta["path_edge_count"],
            "full_evidence_count": len(long_path["full_evidence_pack"]["items"]),
            "selected_answer_evidence_count": len(long_path["selected_answer_evidence"]["items"]),
            "missing_path_evidence_count": meta["missing_path_evidence_count"],
            "path_edge_evidence_coverage": meta["path_edge_evidence_coverage"],
            "answer_evidence_citation_coverage": meta["answer_evidence_citation_coverage"],
        },
    }
    report["passed"] = all(report["status_gates"].values()) and (
        report["evidence_coverage"]["path_edge_count"] == 107
        and report["evidence_coverage"]["full_evidence_count"] == 107
        and report["evidence_coverage"]["selected_answer_evidence_count"] == 8
        and report["evidence_coverage"]["path_edge_evidence_coverage"] == 1.0
    )

    report_dir = ROOT / "evals" / "reports"
    json_path = report_dir / "graphrag_contract.json"
    markdown_path = report_dir / "graphrag_contract.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage = report["evidence_coverage"]
    gates = report["status_gates"]
    markdown_path.write_text(
        "# GraphRAG Contract Regression\n\n"
        f"- Overall: `{'PASS' if report['passed'] else 'FAIL'}`\n"
        f"- Fixture: `{coverage['path_node_count']}` path nodes / `{coverage['path_edge_count']}` path edges\n"
        f"- Full evidence: `{coverage['full_evidence_count']}`\n"
        f"- Selected answer evidence: `{coverage['selected_answer_evidence_count']}`\n"
        f"- Path-edge evidence coverage: `{coverage['path_edge_evidence_coverage']:.1%}`\n"
        f"- Answer-evidence citation coverage: `{coverage['answer_evidence_citation_coverage']:.1%}`\n\n"
        "## Status gates\n\n"
        + "\n".join(f"- `{name}`: `{'PASS' if passed else 'FAIL'}`" for name, passed in gates.items())
        + "\n\nThe full evidence set is deterministic graph coverage. Only the bounded selected set is passed to the Answer Generator.\n",
        encoding="utf-8",
    )
    print(markdown_path)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
