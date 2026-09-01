from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.metrics import latency_summary, reciprocal_rank, safe_ratio


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from evals.baselines.stage0 import (  # noqa: E402
    Stage0VectorStore,
    stage0_answer,
    stage0_interpret,
    stage0_query,
    stage0_recommend,
    stage0_rerank,
)


DATASETS = {
    "target_resolver": ROOT / "evals/datasets/target_resolver.jsonl",
    "path_planner": ROOT / "evals/datasets/path_planner.jsonl",
    "evidence_retriever": ROOT / "evals/datasets/evidence_retriever.jsonl",
    "answer_generator": ROOT / "evals/datasets/answer_generator.jsonl",
}
FULL_CONCEPTS = ROOT / "章节数据/数据汇总/outputs/fixed/concepts_all.csv"
FULL_RELATIONS = ROOT / "章节数据/数据汇总/outputs/fixed/relations_all.csv"
SAMPLE_CONCEPTS = ROOT / "data/seed/concepts.csv"
SAMPLE_RELATIONS = ROOT / "data/seed/relations.csv"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected an object in {path}:{line_number}")
            rows.append(payload)
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _select_graph_files(
    concepts_override: Path | None,
    relations_override: Path | None,
) -> tuple[Path, Path, str]:
    if concepts_override or relations_override:
        if not concepts_override or not relations_override:
            raise ValueError("--concepts-csv and --relations-csv must be supplied together")
        return concepts_override, relations_override, "explicit"
    if FULL_CONCEPTS.exists() and FULL_RELATIONS.exists():
        return FULL_CONCEPTS, FULL_RELATIONS, "full_local"
    return SAMPLE_CONCEPTS, SAMPLE_RELATIONS, "sample"


def _concept_corpus(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    # This intentionally mirrors GraphRepository.get_concept_corpus in the frozen baseline.
    return [
        {
            "concept_id": (row.get("concept_id") or "").strip(),
            "name": (row.get("name") or "").strip(),
            "description": (row.get("description") or "").strip(),
        }
        for row in sorted(rows, key=lambda item: item.get("concept_id") or "")
        if (row.get("concept_id") or "").strip()
    ]


def _evaluate_target_resolver(cases: list[dict[str, Any]], corpus: list[dict[str, str]]) -> dict:
    docs = [
        {
            "concept_id": row["concept_id"],
            "text": f"{row['concept_id']} {row['name']} {row['description']}".strip(),
        }
        for row in corpus
    ]
    store = Stage0VectorStore(docs)
    details: list[dict[str, Any]] = []
    latencies: list[float] = []

    for case in cases:
        started = time.perf_counter()
        planner = stage0_interpret(case["question"], corpus)
        vector_hits = store.search(case["question"], top_k=5)
        reranked = stage0_rerank(case["question"], vector_hits, top_k=5)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)

        acceptable = set(case["acceptable_target_ids"])
        planner_target = planner.get("target_concept_id")
        should_reject = bool(case["should_reject"])
        rejected = planner_target is None
        vector_ids = [hit.get("concept_id", "") for hit in reranked]
        details.append(
            {
                "case_id": case["case_id"],
                "query_language": case["query_language"],
                "should_reject": should_reject,
                "planner_target": planner_target,
                "planner_correct": (rejected if should_reject else planner_target in acceptable),
                "rejected": rejected,
                "vector_top_5": vector_ids,
                "vector_top_1_correct": bool(acceptable and vector_ids and vector_ids[0] in acceptable),
                "vector_reciprocal_rank": reciprocal_rank(vector_ids, acceptable),
                "latency_ms": round(elapsed_ms, 3),
            }
        )

    positive = [item for item in details if not item["should_reject"]]
    negative = [item for item in details if item["should_reject"]]
    language_metrics: dict[str, Any] = {}
    for language in sorted({item["query_language"] for item in details}):
        group = [item for item in positive if item["query_language"] == language]
        language_metrics[language] = {
            "planner_top_1_accuracy": safe_ratio(sum(item["planner_correct"] for item in group), len(group)),
            "vector_top_1_accuracy": safe_ratio(sum(item["vector_top_1_correct"] for item in group), len(group)),
            "vector_recall_at_5": safe_ratio(
                sum(item["vector_reciprocal_rank"] > 0 for item in group), len(group)
            ),
        }

    return {
        "implementation": {
            "planner": "exact concept-id/name fallback",
            "vector_backend": "hashing-fallback",
            "reranker": "token-overlap",
            "aliases_indexed": False,
        },
        "metrics": {
            "planner_top_1_accuracy": safe_ratio(sum(item["planner_correct"] for item in positive), len(positive)),
            "planner_rejection_accuracy": safe_ratio(sum(item["planner_correct"] for item in negative), len(negative)),
            "planner_false_rejection_rate": safe_ratio(sum(item["rejected"] for item in positive), len(positive)),
            "vector_top_1_accuracy": safe_ratio(sum(item["vector_top_1_correct"] for item in positive), len(positive)),
            "vector_recall_at_5": safe_ratio(sum(item["vector_reciprocal_rank"] > 0 for item in positive), len(positive)),
            "vector_mrr_at_5": round(sum(item["vector_reciprocal_rank"] for item in positive) / len(positive), 6)
            if positive
            else None,
            "by_language": language_metrics,
            "latency": latency_summary(latencies),
        },
        "failures": [item for item in details if not item["planner_correct"] or (not item["should_reject"] and not item["vector_top_1_correct"])],
        "cases": details,
    }


def _graph_maps(
    concept_rows: list[dict[str, str]], relation_rows: list[dict[str, str]]
) -> tuple[set[str], list[tuple[str, str]], dict[str, set[str]]]:
    concept_ids = {(row.get("concept_id") or "").strip() for row in concept_rows}
    concept_ids.discard("")
    edges = sorted(
        {
            ((row.get("from_concept_id") or "").strip(), (row.get("to_concept_id") or "").strip())
            for row in relation_rows
            if (row.get("relation_type") or "").strip() == "PREREQUISITE_OF"
            and (row.get("from_concept_id") or "").strip()
            and (row.get("to_concept_id") or "").strip()
        }
    )
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        reverse[target].add(source)
    return concept_ids, edges, reverse


def _ancestors(target: str, reverse: dict[str, set[str]], max_depth: int | None = None) -> set[str]:
    found: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(target, 0)])
    while queue:
        node, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for predecessor in sorted(reverse.get(node, set())):
            if predecessor in found:
                continue
            found.add(predecessor)
            queue.append((predecessor, depth + 1))
    return found


class _CsvBaselineRepository:
    def __init__(
        self,
        concept_ids: set[str],
        edges: list[tuple[str, str]],
        reverse: dict[str, set[str]],
        corpus: list[dict[str, str]] | None = None,
    ) -> None:
        self.concept_ids = concept_ids
        self.edges = edges
        self.reverse = reverse
        self.corpus = corpus or []

    def get_concept_corpus(self, limit: int = 2000) -> list[dict[str, str]]:
        return self.corpus[:limit]

    def get_prerequisite_subgraph(self, target_concept_id: str) -> dict[str, Any]:
        if target_concept_id not in self.concept_ids:
            return {"target_exists": False, "target_concept_id": target_concept_id, "node_ids": [], "edges": []}
        ancestors = _ancestors(target_concept_id, self.reverse, max_depth=8)
        nodes = ancestors | {target_concept_id}
        edges = [edge for edge in self.edges if edge[0] in nodes and edge[1] in nodes]
        return {
            "target_exists": True,
            "target_concept_id": target_concept_id,
            "node_ids": sorted(nodes),
            "edges": edges,
        }


def _evaluate_path_planner(
    cases: list[dict[str, Any]], concept_rows: list[dict[str, str]], relation_rows: list[dict[str, str]]
) -> dict:
    concept_ids, edges, reverse = _graph_maps(concept_rows, relation_rows)
    repo = _CsvBaselineRepository(concept_ids, edges, reverse, _concept_corpus(concept_rows))
    all_expected = 0
    all_returned = 0
    truncated_targets: list[str] = []
    violations = 0
    checked_constraints = 0

    for target in sorted(concept_ids):
        expected = _ancestors(target, reverse)
        result = stage0_recommend(target, [], repo)
        returned = set(result.get("path", [])) - {target}
        all_expected += len(expected)
        all_returned += len(returned & expected)
        if returned != expected:
            truncated_targets.append(target)
        positions = {node: index for index, node in enumerate(result.get("path", []))}
        for source, destination in edges:
            if source in positions and destination in positions:
                checked_constraints += 1
                if positions[source] >= positions[destination]:
                    violations += 1

    case_details: list[dict[str, Any]] = []
    for case in cases:
        result = stage0_recommend(case["target_concept_id"], case["mastered_concepts"], repo)
        returned = set(result.get("path", []))
        required = set(case["required_prerequisite_ids"])
        forbidden = set(case["forbidden_ids"])
        case_details.append(
            {
                "case_id": case["case_id"],
                "curation_status": case["curation_status"],
                "path": result.get("path", []),
                "required_recall": safe_ratio(len(returned & required), len(required)),
                "forbidden_absent": safe_ratio(len(forbidden - returned), len(forbidden)),
                "has_cycle": bool(result.get("has_cycle", False)),
            }
        )

    reviewed = [item for item in case_details if item["curation_status"] == "author_curated"]
    return {
        "implementation": {
            "repository_traversal": "Neo4j variable path limited to 8 edges (CSV emulation)",
            "planner": "deterministic topological sort",
            "mastered_rule": "removes mastered node only; does not skip its ancestors",
        },
        "metrics": {
            "all_target_structural_closure_recall": safe_ratio(all_returned, all_expected),
            "targets_with_truncated_closure": safe_ratio(len(truncated_targets), len(concept_ids)),
            "topological_violation_rate": safe_ratio(violations, checked_constraints),
            "author_curated_required_recall": safe_ratio(
                sum((item["required_recall"]["numerator"] for item in reviewed), 0),
                sum((item["required_recall"]["denominator"] for item in reviewed), 0),
            ),
        },
        "truncated_target_ids": truncated_targets,
        "cases": case_details,
    }


def _build_api_samples(
    concept_rows: list[dict[str, str]], relation_rows: list[dict[str, str]]
) -> dict[str, Any]:
    concept_ids, edges, reverse = _graph_maps(concept_rows, relation_rows)
    corpus = _concept_corpus(concept_rows)
    repo = _CsvBaselineRepository(concept_ids, edges, reverse, corpus)
    planner_questions = [
        "想学卡诺图构成，应该先掌握什么？",
        "What should I learn before studying Binary?",
        "Binary 二进制转换怎么入门？",
        "今天天气怎么样？",
    ]
    return {
        "note": "Service-level samples use a deterministic CSV repository that emulates the current Neo4j depth-8 query.",
        "planner_interpret": [
            {"question": question, "response": stage0_interpret(question, corpus)}
            for question in planner_questions
        ],
        "path_recommend": stage0_recommend("G000079", [], repo),
        "graphrag_query": stage0_query("想学卡诺图构成，应该先掌握什么？", "G000079", [], repo),
    }


def _evaluate_evidence(cases: list[dict[str, Any]]) -> dict:
    relevant_count = sum(len(case["relevant_evidence_ids"]) for case in cases)
    details = [
        {
            "case_id": case["case_id"],
            "expected_evidence_ids": case["relevant_evidence_ids"],
            "returned_evidence_ids": [],
            "status": "unsupported_current_baseline",
            "reason": "Current evidence and citations are concept IDs, not relationship evidence IDs.",
        }
        for case in cases
    ]
    return {
        "implementation": {
            "relationship_evidence_supported": False,
            "current_evidence_type": "concept_id",
            "current_citation_type": "concept",
        },
        "metrics": {
            "evidence_recall_at_k": safe_ratio(0, relevant_count),
            "citation_integrity": {"numerator": 0, "denominator": 0, "value": None, "status": "not_measurable"},
            "invalid_evidence_id_count": 0,
        },
        "failures": details,
        "cases": details,
    }


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def _evaluate_answers(cases: list[dict[str, Any]]) -> dict:
    details: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter()
        hits = [
            {"concept_id": item["from_concept"]["id"], "score": 1.0, "source": "graph"}
            for item in case["evidence_pack"]["items"]
        ]
        answer = stage0_answer(
            case["question"], case["path"], "已基于前驱闭包和拓扑排序生成学习路径。", hits
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)
        template_leak = any(marker in answer for marker in ("Question:", "Path:", "Evidence concepts:", "Answer:"))
        expected_language = case["expected_answer_language"]
        language_match = _contains_cjk(answer) if expected_language == "zh" else not _contains_cjk(answer)
        required = case["required_citation_ids"]
        details.append(
            {
                "case_id": case["case_id"],
                "expected_answer_language": expected_language,
                "answer_preview": answer[:300],
                "structured_output_success": False,
                "answer_source_present": False,
                "answer_language_present": False,
                "language_match_heuristic": language_match,
                "prompt_template_leak": template_leak,
                "valid_required_citations": 0,
                "required_citations": len(required),
                "latency_ms": round(elapsed_ms, 3),
            }
        )

    required_total = sum(item["required_citations"] for item in details)
    return {
        "implementation": {
            "generator": "PromptTemplate formatter",
            "structured_output": False,
            "relationship_citations": False,
            "response_language_control": False,
        },
        "metrics": {
            "structured_output_success_rate": safe_ratio(0, len(details)),
            "answer_source_field_rate": safe_ratio(0, len(details)),
            "answer_language_field_rate": safe_ratio(0, len(details)),
            "prompt_template_leak_rate": safe_ratio(sum(item["prompt_template_leak"] for item in details), len(details)),
            "answer_language_match_rate_heuristic": safe_ratio(sum(item["language_match_heuristic"] for item in details), len(details)),
            "required_citation_completeness": safe_ratio(0, required_total),
            "latency": latency_summary(latencies),
        },
        "failures": [item for item in details if item["prompt_template_leak"] or not item["structured_output_success"]],
        "cases": details,
    }


def _metric_line(name: str, metric: dict[str, Any]) -> str:
    numerator = metric.get("numerator")
    denominator = metric.get("denominator")
    value = metric.get("value")
    rendered = "N/A" if value is None else f"{value:.1%}"
    return f"| {name} | {numerator}/{denominator} | {rendered} |"


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    target = report["modules"]["target_resolver"]["metrics"]
    planner = report["modules"]["path_planner"]["metrics"]
    evidence = report["modules"]["evidence_retriever"]["metrics"]
    answer = report["modules"]["answer_generator"]["metrics"]
    lines = [
        "# Stage 0 frozen baseline",
        "",
        f"- Generated at: `{report['run']['generated_at']}`",
        f"- Dataset profile: `{report['run']['dataset_profile']}`",
        f"- Git commit: `{report['run']['git_commit']}`",
        f"- Vector backend: `hashing-fallback`",
        f"- Reranker: `token-overlap`",
        "",
        "> This report records the pre-refactor implementation. Unsupported capabilities are reported as unsupported; they are not estimated.",
        "",
        "## Core metrics",
        "",
        "| Metric | Count | Value |",
        "| --- | ---: | ---: |",
        _metric_line("Planner target Top-1 accuracy", target["planner_top_1_accuracy"]),
        _metric_line("Planner rejection accuracy", target["planner_rejection_accuracy"]),
        _metric_line("Hashing vector Top-1 accuracy", target["vector_top_1_accuracy"]),
        _metric_line("Hashing vector Recall@5", target["vector_recall_at_5"]),
        _metric_line("All-target structural closure recall", planner["all_target_structural_closure_recall"]),
        _metric_line("Targets with truncated closure", planner["targets_with_truncated_closure"]),
        _metric_line("Topological violation rate", planner["topological_violation_rate"]),
        _metric_line("Relationship evidence Recall@K", evidence["evidence_recall_at_k"]),
        _metric_line("Structured answer success", answer["structured_output_success_rate"]),
        _metric_line("Prompt-template leak rate", answer["prompt_template_leak_rate"]),
        _metric_line("Required citation completeness", answer["required_citation_completeness"]),
        "",
        "## Language breakdown",
        "",
        "| Language | Planner Top-1 | Vector Top-1 | Vector Recall@5 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for language, values in target["by_language"].items():
        def percent(metric: dict[str, Any]) -> str:
            return "N/A" if metric["value"] is None else f"{metric['value']:.1%}"

        lines.append(
            f"| {language} | {percent(values['planner_top_1_accuracy'])} | "
            f"{percent(values['vector_top_1_accuracy'])} | {percent(values['vector_recall_at_5'])} |"
        )
    lines.extend(
        [
            "",
            "## Observed limitations",
            "",
            f"- `{len(report['modules']['path_planner']['truncated_target_ids'])}` targets lose ancestors under the current 8-edge traversal cap.",
            "- The resolver indexes concept IDs, Chinese names, and sparse descriptions only; aliases are absent.",
            "- The hashing tokenizer accepts ASCII words only, so Chinese queries produce zero query vectors.",
            "- Relationship-level evidence and evidence IDs are not implemented, so evidence retrieval is scored as unsupported.",
            "- The answer builder returns a prompt-shaped string and exposes neither `answer_source` nor `answer_language`.",
            "",
            "Detailed per-case failures and the complete configuration snapshot are in the adjacent JSON report.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen stage-0 GraphRAG baseline.")
    parser.add_argument("--concepts-csv", type=Path)
    parser.add_argument("--relations-csv", type=Path)
    parser.add_argument("--output-json", type=Path, default=ROOT / "evals/reports/stage0_baseline_current.json")
    parser.add_argument("--output-markdown", type=Path, default=ROOT / "evals/reports/stage0_baseline_current.md")
    parser.add_argument("--output-api-samples", type=Path, default=ROOT / "evals/reports/stage0_api_samples.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    concepts_path, relations_path, profile = _select_graph_files(args.concepts_csv, args.relations_csv)
    concept_rows = _read_csv(concepts_path)
    relation_rows = _read_csv(relations_path)
    datasets = {name: _read_jsonl(path) for name, path in DATASETS.items()}

    report = {
        "report_version": "1.0",
        "baseline_name": "stage0-pre-refactor-hashing-token-overlap",
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_profile": profile,
            "concepts_csv": str(concepts_path.relative_to(ROOT) if concepts_path.is_relative_to(ROOT) else concepts_path),
            "relations_csv": str(relations_path.relative_to(ROOT) if relations_path.is_relative_to(ROOT) else relations_path),
            "concept_count": len(concept_rows),
            "prerequisite_relation_count": sum(
                (row.get("relation_type") or "").strip() == "PREREQUISITE_OF" for row in relation_rows
            ),
            "file_hashes": {
                "concepts_csv": _sha256(concepts_path),
                "relations_csv": _sha256(relations_path),
                **{name: _sha256(path) for name, path in DATASETS.items()},
            },
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_status": _git_value("status", "--short"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "python_hash_seed": os.getenv("PYTHONHASHSEED", "random"),
            "network_calls": False,
            "llm_enabled": False,
        },
        "modules": {
            "target_resolver": _evaluate_target_resolver(datasets["target_resolver"], _concept_corpus(concept_rows)),
            "path_planner": _evaluate_path_planner(datasets["path_planner"], concept_rows, relation_rows),
            "evidence_retriever": _evaluate_evidence(datasets["evidence_retriever"]),
            "answer_generator": _evaluate_answers(datasets["answer_generator"]),
        },
    }
    api_samples = _build_api_samples(concept_rows, relation_rows)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_api_samples.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report, args.output_markdown)
    args.output_api_samples.write_text(json.dumps(api_samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_markdown}")
    print(f"Wrote {args.output_api_samples}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
