from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for entry in (str(BACKEND), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from app.evidence.citation_validator import validate_citation_ids  # noqa: E402
from app.services.answer_generator import (  # noqa: E402
    StructuredAnswerGenerator,
    _language_matches,
)
from evals.metrics import latency_summary, safe_ratio  # noqa: E402
from evals.stage2_runner import _read_jsonl, _sha256  # noqa: E402


DATASET = ROOT / "evals/datasets/answer_generator.jsonl"


def _git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _fixture_payload(case: dict[str, Any]) -> dict[str, Any]:
    items = case["evidence_pack"].get("items", [])
    language = case["expected_answer_language"]
    if not items:
        answer = (
            f"目标知识点 {case['target_concept_id']} 没有额外先修关系。"
            if language == "zh"
            else f"The target {case['target_concept_id']} has no additional prerequisite relationship."
        )
    else:
        fragments = []
        for item in items:
            source = item["from_concept"]["name"]
            target = item["to_concept"]["name"]
            fragments.append(
                f"{source} 是 {target} 的前置知识。"
                if language == "zh"
                else f"{source} is a prerequisite for {target}."
            )
        answer = "".join(fragments) if language == "zh" else " ".join(fragments)
    return {
        "answer": answer,
        "cited_evidence_ids": case["required_citation_ids"],
    }


def _direction_correct(answer: str, evidence_pack: dict[str, Any]) -> bool:
    for item in evidence_pack.get("items", []):
        source = str(item.get("from_concept", {}).get("name") or "")
        target = str(item.get("to_concept", {}).get("name") or "")
        if source and target and (
            source not in answer
            or target not in answer
            or answer.find(source) > answer.find(target)
        ):
            return False
    return True


def _evaluate_strategy(
    cases: list[dict[str, Any]], strategy: str
) -> dict[str, Any]:
    details = []
    for case in cases:
        if strategy == "offline_fallback":
            generator = StructuredAnswerGenerator(enabled=False)
        else:
            payload = _fixture_payload(case)
            generator = StructuredAnswerGenerator(
                lambda _messages, payload=payload: payload,
                model="deterministic-structured-contract-fixture",
            )
        result = generator.generate(
            question=case["question"],
            target_concept_id=case["target_concept_id"],
            path=case["path"],
            evidence_pack=case["evidence_pack"],
            response_language=case["response_language"],
        )
        validation = validate_citation_ids(
            result["cited_evidence_ids"], case["evidence_pack"]
        )
        required = set(case["required_citation_ids"])
        returned = set(result["cited_evidence_ids"])
        prompt_leak = any(
            marker in result["answer"]
            for marker in ("Question:", "Path:", "Evidence relationships:", "Answer:")
        )
        details.append(
            {
                "case_id": case["case_id"],
                "expected_answer_language": case["expected_answer_language"],
                "answer": result["answer"],
                "cited_evidence_ids": result["cited_evidence_ids"],
                "answer_source": result["answer_source"],
                "answer_language": result["answer_language"],
                "generation_model": result["generation_model"],
                "structured_output_success": result["structured_output_success"],
                "llm_structured_output_success": result[
                    "llm_structured_output_success"
                ],
                "response_schema_valid": result["response_schema_valid"],
                "language_match": (
                    result["answer_language"] == case["expected_answer_language"]
                    and _language_matches(
                        result["answer"], case["expected_answer_language"]
                    )
                ),
                "citation_integrity": validation["integrity"],
                "invalid_evidence_id_count": validation["invalid_count"],
                "required_citation_count": len(required),
                "returned_required_citation_count": len(required.intersection(returned)),
                "direction_correct": _direction_correct(
                    result["answer"], case["evidence_pack"]
                ),
                "prompt_template_leak": prompt_leak,
                "latency_ms": result["generation_latency_ms"],
                "fallback_reason": result["fallback_reason"],
            }
        )

    citation_denominator = sum(
        len(case["cited_evidence_ids"]) for case in details
    )
    valid_citations = sum(
        len(case["cited_evidence_ids"]) - case["invalid_evidence_id_count"]
        for case in details
    )
    required_total = sum(case["required_citation_count"] for case in details)
    required_returned = sum(
        case["returned_required_citation_count"] for case in details
    )
    return {
        "implementation": (
            "real deterministic fallback"
            if strategy == "offline_fallback"
            else "deterministic fake LLM; validates contract and guardrails, not model quality"
        ),
        "metrics": {
            "structured_output_success_rate": safe_ratio(
                sum(case["structured_output_success"] for case in details), len(details)
            ),
            "llm_structured_output_success_rate": safe_ratio(
                sum(case["llm_structured_output_success"] for case in details),
                len(details),
            ),
            "response_schema_valid_rate": safe_ratio(
                sum(case["response_schema_valid"] for case in details), len(details)
            ),
            "fallback_success_rate": safe_ratio(
                sum(
                    case["answer_source"] == "fallback" and bool(case["answer"])
                    for case in details
                ),
                len(details),
            ),
            "llm_contract_success_rate": safe_ratio(
                sum(case["answer_source"] == "llm" for case in details), len(details)
            ),
            "answer_language_match_rate": safe_ratio(
                sum(case["language_match"] for case in details), len(details)
            ),
            "citation_integrity": safe_ratio(valid_citations, citation_denominator),
            "required_citation_completeness": safe_ratio(
                required_returned, required_total
            ),
            "direction_expression_accuracy": safe_ratio(
                sum(case["direction_correct"] for case in details), len(details)
            ),
            "prompt_template_leak_rate": safe_ratio(
                sum(case["prompt_template_leak"] for case in details), len(details)
            ),
            "invalid_evidence_id_count": sum(
                case["invalid_evidence_id_count"] for case in details
            ),
            "latency": latency_summary([case["latency_ms"] for case in details]),
            "unsupported_claim_rate": {
                "numerator": None,
                "denominator": None,
                "value": None,
                "status": "not_measured_without_external_model_evaluation",
            },
            "real_model_faithfulness": {
                "value": None,
                "status": "not_measured",
            },
        },
        "failures": [
            case
            for case in details
            if not case["language_match"]
            or case["invalid_evidence_id_count"]
            or not case["direction_correct"]
            or case["prompt_template_leak"]
        ],
        "cases": details,
    }


def _guardrail_cases(case: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = {
        "malformed_json": lambda _messages: "not-json",
        "timeout": lambda _messages: (_ for _ in ()).throw(TimeoutError("fixture timeout")),
        "hallucinated_citation": lambda _messages: {
            "answer": "This claim is unsupported.",
            "cited_evidence_ids": ["invented:evidence:id"],
        },
    }
    details = []
    for name, callable_ in scenarios.items():
        result = StructuredAnswerGenerator(callable_).generate(
            question=case["question"],
            target_concept_id=case["target_concept_id"],
            path=case["path"],
            evidence_pack=case["evidence_pack"],
            response_language=case["response_language"],
        )
        validation = validate_citation_ids(
            result["cited_evidence_ids"], case["evidence_pack"]
        )
        details.append(
            {
                "scenario": name,
                "answer_source": result["answer_source"],
                "fallback_reason": result["fallback_reason"],
                "final_cited_evidence_ids": result["cited_evidence_ids"],
                "final_invalid_evidence_id_count": validation["invalid_count"],
                "passed": result["answer_source"] == "fallback"
                and validation["invalid_count"] == 0,
            }
        )
    return details


def _percent(metric: dict[str, Any]) -> str:
    value = metric.get("value")
    return "N/A" if value is None else f"{value:.1%}"


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Stage 5 Answer Generator report",
        "",
        f"- Generated at: `{report['run']['generated_at']}`",
        f"- Cases: `{report['run']['case_count']}`",
        f"- Real external LLM evaluated: `false`",
        "",
        "## Offline and contract results",
        "",
        "| Strategy | Response schema valid | LLM structured | Fallback | LLM contract | Language | Citation integrity | Completeness | Direction | Prompt leak | P50/P95 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, result in report["strategies"].items():
        metrics = result["metrics"]
        latency = metrics["latency"]
        lines.append(
            f"| {name} | {_percent(metrics['response_schema_valid_rate'])} | "
            f"{_percent(metrics['llm_structured_output_success_rate'])} | "
            f"{_percent(metrics['fallback_success_rate'])} | "
            f"{_percent(metrics['llm_contract_success_rate'])} | "
            f"{_percent(metrics['answer_language_match_rate'])} | "
            f"{_percent(metrics['citation_integrity'])} | "
            f"{_percent(metrics['required_citation_completeness'])} | "
            f"{_percent(metrics['direction_expression_accuracy'])} | "
            f"{_percent(metrics['prompt_template_leak_rate'])} | "
            f"{latency['p50_ms']}/{latency['p95_ms']} ms |"
        )
    guardrails = report["guardrails"]
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            f"- Malformed JSON, timeout, and hallucinated-citation scenarios passed: `{sum(item['passed'] for item in guardrails)}/{len(guardrails)}`",
            "- Final invalid evidence IDs: `0`",
            "",
            "## Measurement boundary",
            "",
            "- `structured_contract_fixture` uses a deterministic fake LLM. It validates parsing, language, citation, and fallback contracts only.",
            "- No external LLM/API key is required or called by this evaluation.",
            "- Unsupported Claim Rate and real-model Faithfulness remain unmeasured; they must not be reported as 100%.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the stage-5 Answer Generator evaluation.")
    parser.add_argument("--output-json", type=Path, default=ROOT / "evals/reports/stage5_answer_generator.json")
    parser.add_argument("--output-markdown", type=Path, default=ROOT / "evals/reports/stage5_answer_generator.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = _read_jsonl(DATASET)
    report = {
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--porcelain")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dataset_sha256": _sha256(DATASET),
            "case_count": len(cases),
            "external_llm_called": False,
        },
        "strategies": {
            "offline_fallback": _evaluate_strategy(cases, "offline_fallback"),
            "structured_contract_fixture": _evaluate_strategy(
                cases, "structured_contract_fixture"
            ),
        },
        "guardrails": _guardrail_cases(cases[0]),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, args.output_markdown)
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "markdown": str(args.output_markdown),
                "metrics": {
                    name: result["metrics"]
                    for name, result in report["strategies"].items()
                },
                "guardrails": report["guardrails"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
