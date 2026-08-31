from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.retrieval.corpus_builder import (  # noqa: E402
    build_concept_documents,
    build_evidence_documents,
    corpus_hash,
)
from app.retrieval.embedding_backend import (  # noqa: E402
    SentenceTransformerEmbeddingBackend,
    UnicodeHashingEmbeddingBackend,
)
from app.retrieval.embedding_cache import EmbeddingCache  # noqa: E402
from app.services.target_resolver import resolve_target  # noqa: E402
from evals.metrics import latency_summary, reciprocal_rank, safe_ratio  # noqa: E402


FULL_CONCEPTS = ROOT / "章节数据/数据汇总/outputs/fixed/concepts_all.csv"
FULL_RELATIONS = ROOT / "章节数据/数据汇总/outputs/fixed/relations_all.csv"
SAMPLE_CONCEPTS = ROOT / "data/seed/concepts.csv"
SAMPLE_RELATIONS = ROOT / "data/seed/relations.csv"
TARGET_DATASET = ROOT / "evals/datasets/target_resolver.jsonl"
BASELINE_REPORT = ROOT / "evals/reports/stage0_baseline_current.json"
I18N_OVERLAY = ROOT / "data/metadata/concept_i18n.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _select_files(
    concepts_override: Path | None, relations_override: Path | None
) -> tuple[Path, Path, str]:
    if concepts_override or relations_override:
        if not concepts_override or not relations_override:
            raise ValueError("--concepts-csv and --relations-csv must be supplied together")
        return concepts_override, relations_override, "explicit"
    if FULL_CONCEPTS.exists() and FULL_RELATIONS.exists():
        return FULL_CONCEPTS, FULL_RELATIONS, "full_local"
    return SAMPLE_CONCEPTS, SAMPLE_RELATIONS, "sample"


def _enrich_corpus(
    concepts: list[dict[str, str]], relations: list[dict[str, str]]
) -> list[dict[str, Any]]:
    overlays = {
        row["concept_id"]: row for row in _read_csv(I18N_OVERLAY)
    } if I18N_OVERLAY.exists() else {}
    names = {
        (row.get("concept_id") or "").strip(): (row.get("name") or "").strip()
        for row in concepts
    }
    predecessors: dict[str, set[str]] = defaultdict(set)
    successors: dict[str, set[str]] = defaultdict(set)
    for row in relations:
        if (row.get("relation_type") or "").strip() != "PREREQUISITE_OF":
            continue
        source = (row.get("from_concept_id") or "").strip()
        target = (row.get("to_concept_id") or "").strip()
        if source and target:
            predecessors[target].add(names.get(source, source))
            successors[source].add(names.get(target, target))
    output = []
    for row in concepts:
        concept_id = (row.get("concept_id") or "").strip()
        if not concept_id:
            continue
        overlay = overlays.get(concept_id, {})
        aliases = sorted(set(
            str(row.get("aliases") or row.get("alias") or "").split("|")
            + str(overlay.get("alias") or "").split("|")
        ) - {""})
        aliases_en = sorted(set(
            str(row.get("aliases_en") or "").split("|")
            + str(overlay.get("aliases_en") or "").split("|")
        ) - {""})
        output.append(
            {
                **row,
                "concept_id": concept_id,
                "name_en": overlay.get("name_en") or row.get("name_en") or "",
                "aliases": aliases,
                "aliases_en": aliases_en,
                "description_en": overlay.get("description_en") or row.get("description_en") or "",
                "predecessor_names": sorted(predecessors.get(concept_id, set())),
                "successor_names": sorted(successors.get(concept_id, set())),
            }
        )
    return output


def _relation_corpus(
    concepts: list[dict[str, Any]], relations: list[dict[str, str]]
) -> list[dict[str, Any]]:
    by_id = {row["concept_id"]: row for row in concepts}
    output = []
    for row in relations:
        source = (row.get("from_concept_id") or "").strip()
        target = (row.get("to_concept_id") or "").strip()
        output.append(
            {
                **row,
                "from_name": by_id.get(source, {}).get("name", ""),
                "to_name": by_id.get(target, {}).get("name", ""),
                "source_chapters": sorted(
                    set(
                        str(by_id.get(source, {}).get("source_chapters") or "").split("|")
                        + str(by_id.get(target, {}).get("source_chapters") or "").split("|")
                    )
                    - {""}
                ),
                "verification_status": row.get("verification_status") or "unreviewed",
            }
        )
    return output


class CsvConceptRepository:
    def __init__(self, corpus: list[dict[str, Any]]) -> None:
        self.corpus = corpus

    def get_concept_corpus(self, limit: int = 2000) -> list[dict[str, Any]]:
        return self.corpus[:limit]


def _backend(args: argparse.Namespace):
    if args.backend == "unicode_hashing":
        return UnicodeHashingEmbeddingBackend()
    return SentenceTransformerEmbeddingBackend(
        args.model,
        allow_download=args.allow_download,
        device=args.device,
    )


def _evaluate(
    cases: list[dict[str, Any]],
    repo: CsvConceptRepository,
    backend,
    cache: EmbeddingCache,
    min_score: float,
    min_margin: float,
) -> dict[str, Any]:
    available = {row["concept_id"] for row in repo.corpus}
    details: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    latencies: list[float] = []
    for case in cases:
        acceptable = set(case["acceptable_target_ids"])
        if acceptable and not acceptable.intersection(available):
            skipped.append({"case_id": case["case_id"], "reason": "gold IDs absent from corpus"})
            continue
        started = time.perf_counter()
        result = resolve_target(
            case["question"],
            repo,
            top_k=5,
            embedding_backend=backend,
            embedding_cache=cache,
            min_score=min_score,
            min_margin=min_margin,
        )
        elapsed = (time.perf_counter() - started) * 1000
        latencies.append(elapsed)
        ranked_ids = [item["concept_id"] for item in result["candidates"]]
        should_reject = bool(case["should_reject"])
        correct = result["rejected"] if should_reject else result["target_concept_id"] in acceptable
        details.append(
            {
                "case_id": case["case_id"],
                "question": case["question"],
                "query_language": case["query_language"],
                "should_reject": should_reject,
                "acceptable_target_ids": sorted(acceptable),
                "target_concept_id": result["target_concept_id"],
                "rejected": result["rejected"],
                "correct": correct,
                "ranked_ids": ranked_ids,
                "reciprocal_rank": reciprocal_rank(ranked_ids, acceptable),
                "candidates": result["candidates"],
                "resolution_source": result["resolution_source"],
                "cache_status": result["resolver_meta"]["cache_status"],
                "latency_ms": round(elapsed, 3),
            }
        )

    positive = [item for item in details if not item["should_reject"]]
    negative = [item for item in details if item["should_reject"]]

    def group_metrics(group: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "top_1_accuracy": safe_ratio(sum(item["correct"] for item in group), len(group)),
            "recall_at_5": safe_ratio(
                sum(item["reciprocal_rank"] > 0 for item in group), len(group)
            ),
        }

    by_language = {
        language: group_metrics(
            [item for item in positive if item["query_language"] == language]
        )
        for language in ("zh", "en", "mixed")
    }
    return {
        "metrics": {
            "top_1_accuracy": safe_ratio(sum(item["correct"] for item in positive), len(positive)),
            "mrr_at_5": round(
                sum(item["reciprocal_rank"] for item in positive) / len(positive), 6
            )
            if positive
            else None,
            "recall_at_5": safe_ratio(
                sum(item["reciprocal_rank"] > 0 for item in positive), len(positive)
            ),
            "rejection_accuracy": safe_ratio(
                sum(item["correct"] for item in negative), len(negative)
            ),
            "false_rejection_rate": safe_ratio(
                sum(item["rejected"] for item in positive), len(positive)
            ),
            "cross_lingual_top_1_accuracy": safe_ratio(
                sum(item["correct"] for item in positive if item["query_language"] in {"en", "mixed"}),
                sum(item["query_language"] in {"en", "mixed"} for item in positive),
            ),
            "by_language": by_language,
            "latency": latency_summary(latencies),
        },
        "cache": {
            "rebuilt": sum(item["cache_status"] == "rebuilt" for item in details),
            "hits": sum(item["cache_status"] == "hit" for item in details),
        },
        "failures": [item for item in details if not item["correct"]],
        "skipped": skipped,
        "cases": details,
    }


def _metric_line(name: str, metric: dict[str, Any]) -> str:
    value = metric["value"]
    rendered = "N/A" if value is None else f"{value:.1%}"
    return f"| {name} | {metric['numerator']}/{metric['denominator']} | {rendered} |"


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    metrics = report["target_resolver"]["metrics"]
    baseline = report["baseline_comparison"]
    lines = [
        "# Stage 2 multilingual retrieval report",
        "",
        f"- Generated at: `{report['run']['generated_at']}`",
        f"- Dataset profile: `{report['run']['dataset_profile']}`",
        f"- Embedding model: `{report['embedding']['model_id']}`",
        f"- Dimension: `{report['embedding']['dimension']}`",
        f"- Minimum acceptance score: `{report['embedding']['min_score']}`",
        f"- Minimum Top-1 margin: `{report['embedding']['min_margin']}`",
        f"- Concept corpus: `{report['corpora']['concept']['document_count']}` documents",
        f"- Relationship corpus: `{report['corpora']['relationship']['document_count']}` documents",
        "",
        "## Target Resolver metrics",
        "",
        "| Metric | Count | Value |",
        "| --- | ---: | ---: |",
        _metric_line("Top-1 accuracy", metrics["top_1_accuracy"]),
        _metric_line("Recall@5", metrics["recall_at_5"]),
        _metric_line("Rejection accuracy", metrics["rejection_accuracy"]),
        _metric_line("False rejection rate", metrics["false_rejection_rate"]),
        _metric_line("Cross-lingual Top-1 accuracy", metrics["cross_lingual_top_1_accuracy"]),
        "",
        f"- MRR@5: `{metrics['mrr_at_5']}`",
        f"- Latency P50/P95: `{metrics['latency']['p50_ms']} / {metrics['latency']['p95_ms']} ms`",
        f"- Cache rebuilt/hit: `{report['target_resolver']['cache']['rebuilt']} / {report['target_resolver']['cache']['hits']}`",
        f"- Stage 0 vector Top-1: `{baseline.get('stage0_vector_top_1')}`",
        f"- Stage 0 vector Recall@5: `{baseline.get('stage0_vector_recall_at_5')}`",
        "",
        "## Language breakdown",
        "",
        "| Language | Top-1 | Recall@5 |",
        "| --- | ---: | ---: |",
    ]
    for language, values in metrics["by_language"].items():
        top1 = values["top_1_accuracy"]["value"]
        recall = values["recall_at_5"]["value"]
        lines.append(
            f"| {language} | {'N/A' if top1 is None else f'{top1:.1%}'} | "
            f"{'N/A' if recall is None else f'{recall:.1%}'} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Concept and relationship evidence use separate deterministic corpora and cache keys.",
            "- E5 query/passages prefixes are applied by the embedding adapter.",
            "- The acceptance threshold is reported explicitly; this directional dataset is too small for statistical claims.",
            "- Full per-query ranks, scores, failures, hashes, and runtime configuration are in the adjacent JSON report.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the stage-2 multilingual retrieval evaluation.")
    parser.add_argument("--backend", choices=("sentence_transformers", "unicode_hashing"), default="sentence_transformers")
    parser.add_argument("--model", default=settings.embedding_model)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--device")
    parser.add_argument("--min-score", type=float, default=settings.target_resolver_min_score)
    parser.add_argument("--min-margin", type=float, default=settings.target_resolver_min_margin)
    parser.add_argument("--concepts-csv", type=Path)
    parser.add_argument("--relations-csv", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=BACKEND / ".cache/embeddings")
    parser.add_argument("--output-json", type=Path, default=ROOT / "evals/reports/stage2_retrieval.json")
    parser.add_argument("--output-markdown", type=Path, default=ROOT / "evals/reports/stage2_retrieval.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    concepts_path, relations_path, profile = _select_files(args.concepts_csv, args.relations_csv)
    concept_rows = _enrich_corpus(_read_csv(concepts_path), _read_csv(relations_path))
    relation_rows = _relation_corpus(concept_rows, _read_csv(relations_path))
    concept_documents = build_concept_documents(concept_rows)
    relationship_documents = build_evidence_documents(relation_rows)
    backend = _backend(args)
    cache = EmbeddingCache(args.cache_dir)
    relationship_index_first = cache.get_or_build(relationship_documents, backend)
    relationship_index_second = cache.get_or_build(relationship_documents, backend)
    evaluation = _evaluate(
        _read_jsonl(TARGET_DATASET), CsvConceptRepository(concept_rows), backend, cache, args.min_score, args.min_margin
    )
    baseline = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    baseline_metrics = baseline["modules"]["target_resolver"]["metrics"]
    report = {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_profile": profile,
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--porcelain")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "concepts_csv": str(concepts_path.relative_to(ROOT)),
            "relations_csv": str(relations_path.relative_to(ROOT)),
            "target_dataset_sha256": _sha256(TARGET_DATASET),
        },
        "embedding": {
            "backend": args.backend,
            "model_id": backend.model_id,
            "dimension": backend.dimension,
            "normalization": backend.normalize,
            "allow_download": args.allow_download,
            "min_score": args.min_score,
            "min_margin": args.min_margin,
            "threshold_source": "stage2_directional_development_set",
        },
        "corpora": {
            "concept": {"document_count": len(concept_documents), "hash": corpus_hash(concept_documents)},
            "relationship": {
                "document_count": len(relationship_documents),
                "hash": corpus_hash(relationship_documents),
                "first_cache_status": relationship_index_first.cache_status,
                "second_cache_status": relationship_index_second.cache_status,
            },
        },
        "retrieval_modes": ["graph_only", "vector_only", "hybrid_rrf", "hybrid_rrf_rerank"],
        "target_resolver": evaluation,
        "baseline_comparison": {
            "stage0_vector_top_1": baseline_metrics["vector_top_1_accuracy"]["value"],
            "stage0_vector_recall_at_5": baseline_metrics["vector_recall_at_5"]["value"],
            "stage0_planner_top_1": baseline_metrics["planner_top_1_accuracy"]["value"],
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, args.output_markdown)
    print(json.dumps({"json": str(args.output_json), "markdown": str(args.output_markdown), "metrics": evaluation["metrics"], "failures": len(evaluation["failures"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
