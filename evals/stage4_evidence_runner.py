from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for entry in (str(BACKEND), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from app.core.config import settings  # noqa: E402
from app.evidence.citation_validator import validate_citation_ids  # noqa: E402
from app.evidence.pack_builder import build_evidence_pack  # noqa: E402
from app.retrieval.corpus_builder import (  # noqa: E402
    build_evidence_documents,
    corpus_hash,
    evidence_id,
)
from app.retrieval.embedding_backend import SentenceTransformerEmbeddingBackend  # noqa: E402
from app.retrieval.embedding_cache import EmbeddingCache  # noqa: E402
from app.retrieval.evidence_retriever import EvidenceRetriever  # noqa: E402
from evals.metrics import latency_summary, reciprocal_rank, safe_ratio  # noqa: E402
from evals.stage2_runner import (  # noqa: E402
    FULL_CONCEPTS,
    FULL_RELATIONS,
    SAMPLE_CONCEPTS,
    SAMPLE_RELATIONS,
    _enrich_corpus,
    _read_csv,
    _read_jsonl,
    _relation_corpus,
    _sha256,
)


DATASET = ROOT / "evals/datasets/evidence_retriever.jsonl"


def _git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _select_files() -> tuple[Path, Path, str]:
    if FULL_CONCEPTS.exists() and FULL_RELATIONS.exists():
        return FULL_CONCEPTS, FULL_RELATIONS, "full_local"
    return SAMPLE_CONCEPTS, SAMPLE_RELATIONS, "sample"


def _ndcg(ranked_ids: list[str], grades: dict[str, int], k: int) -> float:
    dcg = sum(
        (2 ** int(grades.get(item_id, 0)) - 1) / math.log2(rank + 1)
        for rank, item_id in enumerate(ranked_ids[:k], start=1)
    )
    ideal_grades = sorted((int(value) for value in grades.values()), reverse=True)[:k]
    ideal = sum(
        (2**grade - 1) / math.log2(rank + 1)
        for rank, grade in enumerate(ideal_grades, start=1)
    )
    return dcg / ideal if ideal else 0.0


def _scope_from_path(path: list[str]) -> list[str]:
    return [
        evidence_id("PREREQUISITE_OF", source, target)
        for source, target in zip(path, path[1:])
    ]


def _strategy_metrics(cases: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    relevant_total = sum(len(case["relevant_evidence_ids"]) for case in cases)
    retrieved_relevant = sum(case["retrieved_relevant_count"] for case in cases)
    return {
        "evidence_recall_at_k": safe_ratio(retrieved_relevant, relevant_total),
        "mrr_at_k": round(
            sum(case["reciprocal_rank"] for case in cases) / len(cases), 6
        )
        if cases
        else None,
        "ndcg_at_k": round(sum(case["ndcg"] for case in cases) / len(cases), 6)
        if cases
        else None,
        "top_1_accuracy": safe_ratio(
            sum(case["top_1_correct"] for case in cases), len(cases)
        ),
        "latency": latency_summary([case["latency_ms"] for case in cases]),
        "k": top_k,
    }


def _evaluate(
    cases: list[dict[str, Any]],
    relation_rows: list[dict[str, Any]],
    retriever: EvidenceRetriever,
    top_k: int,
) -> dict[str, Any]:
    available = {
        document["evidence_id"] for document in build_evidence_documents(relation_rows)
    }
    usable = [
        case
        for case in cases
        if set(case["relevant_evidence_ids"]).issubset(available)
    ]
    skipped = [
        {"case_id": case["case_id"], "reason": "gold evidence absent from corpus"}
        for case in cases
        if case not in usable
    ]
    results: dict[str, list[dict[str, Any]]] = {
        "global_vector": [],
        "graph_scoped_vector": [],
    }
    citation_valid = 0
    citation_total = 0
    invalid_ids: list[str] = []
    cache_statuses: list[str] = []

    warmup_started = time.perf_counter()
    warmup = retriever.search(
        "evidence index warmup", relation_rows, allowed_evidence_ids=None, top_k=1
    )
    warmup_ms = (time.perf_counter() - warmup_started) * 1000

    for case in usable:
        relevant = set(case["relevant_evidence_ids"])
        grades = {key: int(value) for key, value in case["graded_relevance"].items()}
        for strategy, allowed in (
            ("global_vector", None),
            ("graph_scoped_vector", _scope_from_path(case["path"])),
        ):
            started = time.perf_counter()
            response = retriever.search(
                case["question"], relation_rows, allowed_evidence_ids=allowed, top_k=top_k
            )
            latency_ms = (time.perf_counter() - started) * 1000
            cache_statuses.append(response["cache_status"])
            ranked_ids = [hit["evidence_id"] for hit in response["hits"]]
            results[strategy].append(
                {
                    "case_id": case["case_id"],
                    "question": case["question"],
                    "review_status": case["review_status"],
                    "relevant_evidence_ids": sorted(relevant),
                    "scope_evidence_ids": allowed,
                    "ranked_evidence_ids": ranked_ids,
                    "scores": [
                        {
                            "evidence_id": hit["evidence_id"],
                            "graph_rank": hit.get("graph_rank"),
                            "vector_rank": hit.get("vector_rank"),
                            "graph_score": hit.get("graph_score"),
                            "vector_score": hit.get("vector_score"),
                            "source": hit.get("source"),
                        }
                        for hit in response["hits"]
                    ],
                    "retrieved_relevant_count": len(relevant.intersection(ranked_ids)),
                    "top_1_correct": bool(ranked_ids and ranked_ids[0] in relevant),
                    "reciprocal_rank": reciprocal_rank(ranked_ids, relevant),
                    "ndcg": round(_ndcg(ranked_ids, grades, top_k), 6),
                    "latency_ms": round(latency_ms, 3),
                }
            )
            if strategy == "graph_scoped_vector":
                pack = build_evidence_pack(
                    case["target_concept_id"], case["path"], response["hits"]
                )
                validation = validate_citation_ids(
                    [item["evidence_id"] for item in pack["items"]], pack
                )
                citation_valid += validation["valid_count"]
                citation_total += validation["citation_count"]
                invalid_ids.extend(validation["invalid_evidence_ids"])

    strategies = {
        strategy: {
            "metrics": _strategy_metrics(details, top_k),
            "failures": [case for case in details if not case["top_1_correct"]],
            "cases": details,
        }
        for strategy, details in results.items()
    }
    reviewed_cases = [
        case
        for case in results["graph_scoped_vector"]
        if case["review_status"] == "human_verified"
    ]
    return {
        "strategies": strategies,
        "citation": {
            "integrity": safe_ratio(citation_valid, citation_total),
            "invalid_evidence_id_count": len(invalid_ids),
            "invalid_evidence_ids": sorted(set(invalid_ids)),
            "human_labeled_top_1_correctness": safe_ratio(
                sum(case["top_1_correct"] for case in reviewed_cases),
                len(reviewed_cases),
            ),
            "note": (
                "Human labels come from the versioned evaluation fixtures; production "
                "relationship verification_status remains independent."
            ),
        },
        "cache": {
            "warmup_status": warmup["cache_status"],
            "warmup_latency_ms": round(warmup_ms, 3),
            "rebuilt": sum(status == "rebuilt" for status in cache_statuses),
            "hits": sum(status == "hit" for status in cache_statuses),
        },
        "skipped": skipped,
    }


def _percent(metric: dict[str, Any]) -> str:
    value = metric["value"]
    return "N/A" if value is None else f"{value:.1%}"


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    evaluation = report["evaluation"]
    lines = [
        "# Stage 4 relationship evidence and citation report",
        "",
        f"- Generated at: `{report['run']['generated_at']}`",
        f"- Dataset profile: `{report['run']['dataset_profile']}`",
        f"- Embedding model: `{report['model']['embedding_model']}`",
        f"- Relationship corpus: `{report['corpus']['document_count']}` documents",
        f"- Cold model/index warmup: `{evaluation['cache']['warmup_latency_ms']} ms` (`{evaluation['cache']['warmup_status']}`)",
        "",
        "## Evidence retrieval",
        "",
        "| Strategy | Recall@5 | MRR@5 | nDCG@5 | Top-1 | P50/P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy, result in evaluation["strategies"].items():
        metrics = result["metrics"]
        latency = metrics["latency"]
        lines.append(
            f"| {strategy} | {_percent(metrics['evidence_recall_at_k'])} | "
            f"{metrics['mrr_at_k']} | {metrics['ndcg_at_k']} | "
            f"{_percent(metrics['top_1_accuracy'])} | "
            f"{latency['p50_ms']}/{latency['p95_ms']} ms |"
        )
    citation = evaluation["citation"]
    lines.extend(
        [
            "",
            "## Citation validation",
            "",
            f"- Citation Integrity: `{citation['integrity']['numerator']}/{citation['integrity']['denominator']} = {_percent(citation['integrity'])}`",
            f"- Invalid Evidence IDs: `{citation['invalid_evidence_id_count']}`",
            f"- Human-labeled Top-1 correctness: `{citation['human_labeled_top_1_correctness']['numerator']}/{citation['human_labeled_top_1_correctness']['denominator']} = {_percent(citation['human_labeled_top_1_correctness'])}`",
            "",
            "> Graph-scoped retrieval can rank only relationships already selected by the prerequisite graph; vector similarity cannot alter the learning path.",
            "",
            "The six-case reviewed fixture is directional and not statistically representative. Production `verification_status` remains separate from evaluation relevance labels. Per-case ranks, scores, hashes, and failures are in the adjacent JSON report.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stage-4 relationship evidence evaluation.")
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--cache-dir", type=Path, default=BACKEND / ".cache/embeddings")
    parser.add_argument("--output-json", type=Path, default=ROOT / "evals/reports/stage4_evidence.json")
    parser.add_argument("--output-markdown", type=Path, default=ROOT / "evals/reports/stage4_evidence.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    concepts_path, relations_path, profile = _select_files()
    source_relations = _read_csv(relations_path)
    concepts = _enrich_corpus(_read_csv(concepts_path), source_relations)
    relation_rows = _relation_corpus(concepts, source_relations)
    documents = build_evidence_documents(relation_rows)
    backend = SentenceTransformerEmbeddingBackend(
        args.model, allow_download=args.allow_download
    )
    evaluation = _evaluate(
        _read_jsonl(DATASET),
        relation_rows,
        EvidenceRetriever(backend, EmbeddingCache(args.cache_dir)),
        max(1, args.top_k),
    )
    report = {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_profile": profile,
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--porcelain")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dataset_sha256": _sha256(DATASET),
        },
        "model": {
            "embedding_model": backend.model_id,
            "dimension": backend.dimension,
            "normalization": backend.normalize,
        },
        "corpus": {
            "document_count": len(documents),
            "hash": corpus_hash(documents),
            "schema": "evidence-v1",
        },
        "evaluation": evaluation,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, args.output_markdown)
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "markdown": str(args.output_markdown),
                "strategies": {
                    name: result["metrics"]
                    for name, result in evaluation["strategies"].items()
                },
                "citation": evaluation["citation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
