from pydantic import BaseModel, Field


class GraphOverviewResponse(BaseModel):
    course_count: int = Field(default=0)
    chapter_count: int = Field(default=0)
    concept_count: int = Field(default=0)
    prerequisite_rel_count: int = Field(default=0)


class ConceptDetailResponse(BaseModel):
    concept_id: str
    name: str | None = None
    description: str | None = None
    chapter_id: str | None = None
    chapter_name: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    successors: list[str] = Field(default_factory=list)


class ConceptSummary(BaseModel):
    concept_id: str
    name: str = ""
    description: str = ""


class ConceptCorpusResponse(BaseModel):
    items: list[ConceptSummary] = Field(default_factory=list)
