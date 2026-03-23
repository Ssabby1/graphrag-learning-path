from pydantic import BaseModel, Field


class PlannerInterpretRequest(BaseModel):
    question: str = Field(min_length=1)


class PlannerInterpretResponse(BaseModel):
    target_concept_id: str | None = None
    mastered_concepts: list[str] = Field(default_factory=list)
    matched_concepts: list[str] = Field(default_factory=list)
    summary: str = ""
    interpretation_source: str = "fallback"
