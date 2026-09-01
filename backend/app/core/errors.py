class RepositoryUnavailableError(RuntimeError):
    """Raised when backend repositories are unavailable (e.g. Neo4j down/misconfigured)."""


class TargetConceptNotFoundError(LookupError):
    """Raised when a requested learning target does not exist in the graph."""

    def __init__(self, concept_id: str) -> None:
        self.concept_id = concept_id
        super().__init__(f"Target concept not found: {concept_id}")
