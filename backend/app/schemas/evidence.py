from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceConcept(BaseModel):
    id: str
    name: str = ""


class EvidenceRetrievalTrace(BaseModel):
    graph_rank: int | None = None
    vector_rank: int | None = None
    graph_score: float | None = None
    vector_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    source: str = "unknown"


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    from_concept: EvidenceConcept
    relation: str
    to_concept: EvidenceConcept
    reason: str
    source_chapters: list[str] = Field(default_factory=list)
    source_images: list[str] = Field(default_factory=list)
    confidence: float | None = None
    confidence_type: str = "extraction_confidence"
    verification_status: str = "unreviewed"
    retrieval: EvidenceRetrievalTrace = Field(default_factory=EvidenceRetrievalTrace)


class EvidencePack(BaseModel):
    evidence_pack_version: str = "1.0"
    target_concept_id: str
    path: list[str] = Field(default_factory=list)
    items: list[EvidenceItem] = Field(default_factory=list)
