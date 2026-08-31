from __future__ import annotations

import argparse
import json
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
from app.retrieval.concept_retriever import ConceptRetriever  # noqa: E402
from app.retrieval.corpus_builder import build_concept_documents, corpus_hash  # noqa: E402
from app.retrieval.embedding_backend import SentenceTransformerEmbeddingBackend  # noqa: E402
from app.retrieval.embedding_cache import EmbeddingCache  # noqa: E402
from app.retrieval.reranker import CrossEncoderReranker, TokenOverlapReranker  # noqa: E402
from evals.metrics import latency_summary, reciprocal_rank, safe_ratio  # noqa: E402
from evals.stage2_runner import (  # noqa: E402
    FULL_CONCEPTS,
    FULL_RELATIONS,
    SAMPLE_CONCEPTS,
    SAMPLE_RELATIONS,
    TARGET_DATASET,
    _enrich_corpus,
    _read_csv,
    _read_jsonl,
    _sha256,
)


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


def _rank_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    def subset(language: str | None = None) -> list[dict[str, Any]]:
        return [
            case
            for case in cases
            if language is None or case["query_language"] == language
        ]

    def metrics(group: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "top_1_accuracy": safe_ratio(
                sum(case["top_1_correct"] for case in group), len(group)
            ),
            "recall_at_k": safe_ratio(
                sum(case["reciprocal_rank"] > 0 for case in group), len(group)
            ),
            "mrr_at_k": round(
                sum(case["reciprocal_rank"] for case in group) / len(group), 6
            )
            if group
            else None,
        }

    return {
        **metrics(subset()),
        "by_language": {
            language: metrics(subset(language)) for language in ("zh", "en", "mixed")
        },
    }


def _evaluate(
    documents: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    embedding_backend,
    cache: EmbeddingCache,
    cross_encoder: CrossEncoderReranker,
    candidate_k: int,
    final_k: int,
) -> dict[str, Any]:
    available = {document["concept_id"] for document in documents}
    positive_cases = [
        case
        for case in cases
        if not case["should_reject"]
        and set(case["acceptable_target_ids"]).intersection(available)
    ]
    retriever = ConceptRetriever(embedding_backend, cache=cache)
    rerankers = {
        "none": None,
        "token_overlap": TokenOverlapReranker(),
        "cross_encoder": cross_encoder,
    }
    strategy_cases: dict[str, list[dict[str, Any]]] = {
        name: [] for name in rerankers
    }
    rerank_latencies: dict[str, list[float]] = {name: [] for name in rerankers}
    total_latencies: dict[str, list[float]] = {name: [] for name in rerankers}
    retrieval_latencies: list[float] = []
    cache_statuses: list[str] = []

    for case in positive_cases:
        retrieval_started = time.perf_counter()
        result = retriever.search(
            query=case["question"],
            documents=documents,
            mode="vector_only",
            top_k_vector=candidate_k,
            top_k_final=candidate_k,
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        retrieval_latencies.append(retrieval_ms)
        cache_statuses.append(result["cache_status"])
        acceptable = set(case["acceptable_target_ids"])

        for strategy, reranker in rerankers.items():
            started = time.perf_counter()
            ranked_hits = (
                [dict(hit) for hit in result["hits"][:final_k]]
                if reranker is None
                else reranker.rerank(
                    case["question"], [dict(hit) for hit in result["hits"]], final_k
                )
            )
            rerank_ms = (time.perf_counter() - started) * 1000
            rerank_latencies[strategy].append(rerank_ms)
            total_latencies[strategy].append(retrieval_ms + rerank_ms)
            ranked_ids = [hit["concept_id"] for hit in ranked_hits]
            strategy_cases[strategy].append(
                {
                    "case_id": case["case_id"],
                    "question": case["question"],
                    "query_language": case["query_language"],
                    "acceptable_target_ids": sorted(acceptable),
                    "ranked_ids": ranked_ids,
                    "scores": [
                        {
                            "concept_id": hit["concept_id"],
                            "vector_score": hit.get("vector_score"),
                            "rerank_score": hit.get("rerank_score"),
                        }
                        for hit in ranked_hits
                    ],
                    "top_1_correct": bool(ranked_ids and ranked_ids[0] in acceptable),
                    "reciprocal_rank": reciprocal_rank(ranked_ids, acceptable),
                    "retrieval_latency_ms": round(retrieval_ms, 3),
                    "rerank_latency_ms": round(rerank_ms, 3),
                }
            )

    strategies = {}
    for strategy in rerankers:
        details = strategy_cases[strategy]
        strategies[strategy] = {
            "metrics": _rank_metrics(details),
            "latency": {
                "rerank_only": latency_summary(rerank_latencies[strategy]),
                "retrieval_plus_rerank": latency_summary(total_latencies[strategy]),
            },
            "failures": [case for case in details if not case["top_1_correct"]],
            "cases": details,
        }

    baseline = strategies["none"]["metrics"]
    cross = strategies["cross_encoder"]["metrics"]
    top1_gain = (
        cross["top_1_accuracy"]["value"] - baseline["top_1_accuracy"]["value"]
    )
    language_regressions = [
        language
        for language in ("zh", "en", "mixed")
        if cross["by_language"][language]["top_1_accuracy"]["value"]
        < baseline["by_language"][language]["top_1_accuracy"]["value"]
    ]
    cross_p95 = strategies["cross_encoder"]["latency"]["rerank_only"]["p95_ms"]
    quality_gate = top1_gain > 0 and not language_regressions
    latency_gate = cross_p95 is not None and cross_p95 <= 1000.0
    recommended = "cross_encoder" if quality_gate and latency_gate else "none"
    return {
        "candidate_count": candidate_k,
        "final_count": final_k,
        "evaluated_positive_cases": len(positive_cases),
        "retrieval_latency": latency_summary(retrieval_latencies),
        "embedding_cache": {
            "rebuilt": sum(status == "rebuilt" for status in cache_statuses),
            "hits": sum(status == "hit" for status in cache_statuses),
        },
        "strategies": strategies,
        "decision": {
            "recommended_default": recommended,
            "top_1_gain_vs_none": round(top1_gain, 6),
            "language_regressions": language_regressions,
            "quality_gate": quality_gate,
            "latency_gate_p95_le_1000ms": latency_gate,
            "policy": (
                "Enable the cross-encoder only if it improves Top-1, causes no language "
                "subgroup Top-1 regression, and reranking P95 is at most 1000 ms on the target Mac."
            ),
        },
    }


def _percentage(metric: dict[str, Any]) -> str:
    value = metric["value"]
    return "N/A" if value is None else f"{value:.1%}"


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    evaluation = report["evaluation"]
    lines = [
        "# Stage 3 reranker ablation",
        "",
        f"- Generated at: `{report['run']['generated_at']}`",
        f"- Dataset profile: `{report['run']['dataset_profile']}`",
        f"- Bi-encoder: `{report['models']['embedding']}`",
        f"- Cross-encoder: `{report['models']['cross_encoder']}`",
        f"- Device: `{report['models']['cross_encoder_device']}`",
        f"- Candidate/final K: `{evaluation['candidate_count']} / {evaluation['final_count']}`",
        "",
        "## Quality and latency",
        "",
        "| Strategy | Top-1 | MRR@5 | Recall@5 | Rerank P50 | Rerank P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy, result in evaluation["strategies"].items():
        metrics = result["metrics"]
        latency = result["latency"]["rerank_only"]
        lines.append(
            f"| {strategy} | {_percentage(metrics['top_1_accuracy'])} | "
            f"{metrics['mrr_at_k']} | {_percentage(metrics['recall_at_k'])} | "
            f"{latency['p50_ms']} ms | {latency['p95_ms']} ms |"
        )
    decision = evaluation["decision"]
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Recommended default: `{decision['recommended_default']}`",
            f"- Cross-encoder Top-1 gain vs none: `{decision['top_1_gain_vs_none']:+.1%}`",
            f"- Language subgroup regressions: `{decision['language_regressions']}`",
            f"- Quality gate passed: `{decision['quality_gate']}`",
            f"- Latency gate passed: `{decision['latency_gate_p95_le_1000ms']}`",
            "",
            f"> {decision['policy']}",
            "",
            "This is a directional 30-case concept-ranking ablation. Curated aliases are part of the corpus, and the result is not a claim of statistical significance. Per-case scores and failures are available in the adjacent JSON report.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the stage-3 reranker ablation.")
    parser.add_argument("--embedding-model", default=settings.embedding_model)
    parser.add_argument("--reranker-model", default=settings.reranker_model)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--device", default=settings.reranker_device or None)
    parser.add_argument("--candidate-k", type=int, default=8)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--cache-dir", type=Path, default=BACKEND / ".cache/embeddings")
    parser.add_argument("--output-json", type=Path, default=ROOT / "evals/reports/stage3_reranker_ablation.json")
    parser.add_argument("--output-markdown", type=Path, default=ROOT / "evals/reports/stage3_reranker_ablation.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    concepts_path, relations_path, profile = _select_files()
    concepts = _enrich_corpus(_read_csv(concepts_path), _read_csv(relations_path))
    documents = build_concept_documents(concepts)
    embedding = SentenceTransformerEmbeddingBackend(
        args.embedding_model, allow_download=args.allow_download
    )
    cross_encoder = CrossEncoderReranker(
        args.reranker_model,
        allow_download=args.allow_download,
        device=args.device,
        batch_size=settings.reranker_batch_size,
        max_length=settings.reranker_max_length,
    )
    load_started = time.perf_counter()
    cross_encoder.ensure_available()
    load_ms = (time.perf_counter() - load_started) * 1000
    evaluation = _evaluate(
        documents,
        _read_jsonl(TARGET_DATASET),
        embedding,
        EmbeddingCache(args.cache_dir),
        cross_encoder,
        max(1, args.candidate_k),
        max(1, args.final_k),
    )
    report = {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_profile": profile,
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--porcelain")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "target_dataset_sha256": _sha256(TARGET_DATASET),
            "concept_corpus_hash": corpus_hash(documents),
        },
        "models": {
            "embedding": embedding.model_id,
            "cross_encoder": cross_encoder.model_id,
            "cross_encoder_device": str(cross_encoder._model.device),
            "cross_encoder_load_ms": round(load_ms, 3),
            "cross_encoder_license": "apache-2.0",
            "cross_encoder_languages": ["zh", "en", "multilingual (15 languages in model card)"],
            "cross_encoder_score_activation": "sigmoid",
        },
        "evaluation": evaluation,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, args.output_markdown)
    summary = {
        "json": str(args.output_json),
        "markdown": str(args.output_markdown),
        "device": report["models"]["cross_encoder_device"],
        "decision": evaluation["decision"],
        "strategies": {
            name: {
                "top_1": result["metrics"]["top_1_accuracy"],
                "mrr_at_5": result["metrics"]["mrr_at_k"],
                "rerank_latency": result["latency"]["rerank_only"],
            }
            for name, result in evaluation["strategies"].items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
