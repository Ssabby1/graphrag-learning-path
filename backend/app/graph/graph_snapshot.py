from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class GraphSnapshot:
    """Immutable, platform-neutral snapshot of direct prerequisite relations."""

    concept_ids: tuple[str, ...]
    prerequisite_edges: tuple[tuple[str, str], ...]
    content_hash: str
    loaded_at: str

    @classmethod
    def build(
        cls,
        concept_ids: list[str] | tuple[str, ...] | set[str],
        prerequisite_edges: list[tuple[str, str]] | tuple[tuple[str, str], ...] | set[tuple[str, str]],
    ) -> "GraphSnapshot":
        normalized_concepts = tuple(sorted({item.strip() for item in concept_ids if item and item.strip()}))
        concept_set = set(normalized_concepts)
        normalized_edges = tuple(
            sorted(
                {
                    (source.strip(), target.strip())
                    for source, target in prerequisite_edges
                    if source
                    and target
                    and source.strip() in concept_set
                    and target.strip() in concept_set
                }
            )
        )
        canonical = json.dumps(
            {"concept_ids": normalized_concepts, "prerequisite_edges": normalized_edges},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls(
            concept_ids=normalized_concepts,
            prerequisite_edges=normalized_edges,
            content_hash=hashlib.sha256(canonical).hexdigest(),
            loaded_at=datetime.now(timezone.utc).isoformat(),
        )

