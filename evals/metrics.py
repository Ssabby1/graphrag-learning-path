from __future__ import annotations

import math
from statistics import median


def safe_ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def reciprocal_rank(ranked_ids: list[str], acceptable_ids: set[str]) -> float:
    for rank, item_id in enumerate(ranked_ids, start=1):
        if item_id in acceptable_ids:
            return 1.0 / rank
    return 0.0


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def latency_summary(values_ms: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values_ms),
        "p50_ms": round(median(values_ms), 3) if values_ms else None,
        "p95_ms": round(percentile(values_ms, 0.95), 3) if values_ms else None,
    }

