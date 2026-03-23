class RepositoryUnavailableError(RuntimeError):
    """Raised when backend repositories are unavailable (e.g. Neo4j down/misconfigured)."""

