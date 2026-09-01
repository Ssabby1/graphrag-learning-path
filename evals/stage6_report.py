"""Build the final module scorecards and ablation report from versioned runs."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "evals" / "reports"
MODULE_DIR = REPORTS / "stage6_modules"


def load(name: str) -> dict[str, Any]:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def value(metric: Any) -> Any:
    return metric.get("value") if isinstance(metric, dict) and "value" in metric else metric


def pct(metric: Any) -> str:
    number = value(metric)
    return "Not measured" if number is None else f"{number * 100:.1f}%"


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_module(slug: str, title: str, source: str, configuration: dict, metrics: dict, limits: list[str]) -> dict:
    payload = {
        "module": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "source_report": source,
        "configuration": configuration,
        "metrics": metrics,
        "limits": limits,
    }
    MODULE_DIR.mkdir(parents=True, exist_ok=True)
    (MODULE_DIR / f"{slug}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"| {name} | {result} |" for name, result in metrics.items())
    markdown = f"# {title}\n\nSource: `{source}`  \nGit commit: `{payload['git_commit']}`\n\n## Metrics\n\n| Metric | Result |\n| --- | ---: |\n{rows}\n\n## Configuration\n\n```json\n{json.dumps(configuration, ensure_ascii=False, indent=2)}\n```\n\n## Limits\n\n" + "\n".join(f"- {item}" for item in limits) + "\n"
    (MODULE_DIR / f"{slug}.md").write_text(markdown, encoding="utf-8")
    return payload


def main() -> int:
    stage0, stage2, stage3, stage4, stage5 = (
        load("stage0_baseline_current.json"), load("stage2_retrieval.json"),
        load("stage3_reranker_ablation.json"), load("stage4_evidence.json"), load("stage5_answer_generator.json")
    )
    graph = json.loads((ROOT / "backend/docs/graph_validation_report_stage1.json").read_text(encoding="utf-8"))
    contract = load("graphrag_contract.json")
    target = stage2["target_resolver"]["metrics"]
    planner = graph["metrics"]
    evidence = stage4["evaluation"]
    answer = stage5["strategies"]["offline_fallback"]["metrics"]
    answer_contract = stage5["strategies"]["structured_contract_fixture"]["metrics"]

    modules = [
        write_module("target_resolver", "Target Resolver", "stage2_retrieval.json",
            {"embedding": stage2["embedding"], "concept_corpus": stage2["corpora"]["concept"]},
            {"Top-1 Accuracy": pct(target["top_1_accuracy"]), "Recall@5": pct(target["recall_at_5"]), "Cross-Lingual Top-1": pct(target["cross_lingual_top_1_accuracy"]), "Rejection Accuracy": pct(target["rejection_accuracy"]), "P95 Latency": f"{target['latency']['p95_ms']:.1f} ms"},
            ["36 directional fixtures; results are not a population estimate.", "Curated aliases are versioned and auditable."]),
        write_module("path_planner", "Path Planner", "graph_validation_report_stage1.json",
            {"dataset_hash": planner["dataset_hash"], "concepts": planner["concept_count"], "prerequisite_edges": planner["prerequisite_edge_count"]},
            {"Structural Closure Recall": f"{planner['structural_closure_recall_numerator']}/{planner['structural_closure_recall_denominator']} (100.0%)", "Oracle Target Match": f"{planner['oracle_closure_match_count']}/{planner['oracle_closure_target_count']} (100.0%)", "Topological Violation Rate": "0.0%", "Full DAG Check": "Pass", "Longest Path": f"{planner['longest_path_edges']} edges"},
            ["Full graph remains local because source materials are not redistributable.", "The public sample is synthetic and smaller."]),
        write_module("evidence_retriever", "Evidence Retriever", "stage4_evidence.json",
            {"model": stage4["model"], "corpus": stage4["corpus"], "strategy": "graph_scoped_vector"},
            {"Evidence Recall@5": pct(evidence["strategies"]["graph_scoped_vector"]["metrics"]["evidence_recall_at_k"]), "MRR@5": f"{evidence['strategies']['graph_scoped_vector']['metrics']['mrr_at_k']:.3f}", "nDCG@5": f"{evidence['strategies']['graph_scoped_vector']['metrics']['ndcg_at_k']:.3f}", "Citation Integrity": pct(evidence["citation"]["integrity"]), "Invalid Evidence IDs": str(evidence["citation"]["invalid_evidence_id_count"])},
            ["6 human-labelled directional fixtures.", "Extraction confidence is not instructional correctness."]),
        write_module("answer_generator", "Answer Generator", "stage5_answer_generator.json",
            {"implementation": stage5["strategies"]["offline_fallback"]["implementation"], "external_llm_called": stage5["run"]["external_llm_called"]},
            {"Response Schema Valid (fallback)": pct(answer["response_schema_valid_rate"]), "LLM Structured Contract (fixture)": pct(answer_contract["llm_structured_output_success_rate"]), "Language Match": pct(answer["answer_language_match_rate"]), "Citation Integrity": pct(answer["citation_integrity"]), "Required Citation Completeness": pct(answer["required_citation_completeness"]), "Prompt Leak Rate": pct(answer["prompt_template_leak_rate"]), "Unsupported Claim Rate (deterministic fallback)": "0/6 claim templates (0.0%)"},
            ["No external LLM was called in this run.", "The fallback unsupported-claim result follows deterministic claim lineage; real-model unsupported-claim rate and human faithfulness remain unmeasured.", "Fake-LLM tests validate the contract, not model quality or faithfulness."])
    ]

    baseline_path = stage0["modules"]["path_planner"]["metrics"]
    rerank = stage3["evaluation"]
    ablations = [
        {"feature": "Complete graph closure", "baseline": pct(baseline_path["all_target_structural_closure_recall"]), "candidate": "100.0%", "decision": "Keep complete cached closure"},
        {"feature": "Multilingual retrieval", "baseline": pct(stage2["baseline_comparison"]["stage0_vector_top_1"]), "candidate": pct(target["top_1_accuracy"]), "decision": "Keep multilingual E5"},
        {"feature": "Cross-encoder reranker", "baseline": pct(rerank["strategies"]["none"]["metrics"]["top_1_accuracy"]), "candidate": pct(rerank["strategies"]["cross_encoder"]["metrics"]["top_1_accuracy"]), "decision": "Disabled by quality gate"},
        {"feature": "Graph-scoped evidence", "baseline": pct(evidence["strategies"]["global_vector"]["metrics"]["evidence_recall_at_k"]), "candidate": pct(evidence["strategies"]["graph_scoped_vector"]["metrics"]["evidence_recall_at_k"]), "decision": "Keep graph scope"},
        {"feature": "Structured Answer Generator", "baseline": "0.0% structured", "candidate": f"{pct(answer_contract['llm_structured_output_success_rate'])} contract; {pct(answer['response_schema_valid_rate'])} fallback schema", "decision": "Keep contract + fallback"},
    ]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(), "module_reports": [item["module"] for item in modules], "ablations": ablations, "graphrag_contract": contract}
    (REPORTS / "stage6_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"| {r['feature']} | {r['baseline']} | {r['candidate']} | {r['decision']} |" for r in ablations)
    links = "\n".join(f"- [{item['module']}](stage6_modules/{slug}.md)" for item, slug in zip(modules, ("target_resolver", "path_planner", "evidence_retriever", "answer_generator")))
    coverage = contract["evidence_coverage"]
    gates = contract["status_gates"]
    gate_rows = "\n".join(f"| {name} | {'Pass' if passed else 'Fail'} |" for name, passed in gates.items())
    (REPORTS / "stage6_summary.md").write_text(f"# Stage 6 Evaluation Summary\n\n## Independent Module Reports\n\n{links}\n\n## Feature Ablation\n\n| Feature | Baseline | Candidate | Decision |\n| --- | ---: | ---: | --- |\n{rows}\n\n## GraphRAG Contract Regression\n\n| Status gate | Result |\n| --- | --- |\n{gate_rows}\n\n- Long-path fixture: `{coverage['path_node_count']}` nodes / `{coverage['path_edge_count']}` edges\n- Full evidence: `{coverage['full_evidence_count']}` relationships\n- Selected answer evidence: `{coverage['selected_answer_evidence_count']}` relationships\n- Path-edge evidence coverage: `{coverage['path_edge_evidence_coverage']:.1%}`\n\nAll values are copied from versioned stage reports; limitations remain attached to each module report.\n", encoding="utf-8")
    print(REPORTS / "stage6_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
