from __future__ import annotations

from typing import Any, Iterable


def validate_citation_ids(
    cited_evidence_ids: Iterable[str], evidence_pack: dict[str, Any]
) -> dict[str, Any]:
    allowed = {
        str(item.get("evidence_id") or "")
        for item in evidence_pack.get("items", [])
        if item.get("evidence_id")
    }
    requested = list(
        dict.fromkeys(
            str(evidence_id).strip()
            for evidence_id in cited_evidence_ids
            if str(evidence_id).strip()
        )
    )
    valid = [evidence_id for evidence_id in requested if evidence_id in allowed]
    invalid = [evidence_id for evidence_id in requested if evidence_id not in allowed]
    return {
        "valid_evidence_ids": valid,
        "invalid_evidence_ids": invalid,
        "valid_count": len(valid),
        "invalid_count": len(invalid),
        "citation_count": len(requested),
        "integrity_numerator": len(valid),
        "integrity_denominator": len(requested),
        "integrity": len(valid) / len(requested) if requested else 1.0,
    }
