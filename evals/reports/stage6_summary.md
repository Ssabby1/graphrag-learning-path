# Stage 6 Evaluation Summary

## Independent Module Reports

- [Target Resolver](stage6_modules/target_resolver.md)
- [Path Planner](stage6_modules/path_planner.md)
- [Evidence Retriever](stage6_modules/evidence_retriever.md)
- [Answer Generator](stage6_modules/answer_generator.md)

## Feature Ablation

| Feature | Baseline | Candidate | Decision |
| --- | ---: | ---: | --- |
| Complete graph closure | 99.3% | 100.0% | Keep complete cached closure |
| Multilingual retrieval | 3.3% | 100.0% | Keep multilingual E5 |
| Cross-encoder reranker | 86.7% | 83.3% | Disabled by quality gate |
| Graph-scoped evidence | 83.3% | 100.0% | Keep graph scope |
| Structured Answer Generator | 0.0% structured | 100.0% contract; 100.0% fallback schema | Keep contract + fallback |

## GraphRAG Contract Regression

| Status gate | Result |
| --- | --- |
| not_found_rejected | Pass |
| already_mastered | Pass |
| truncated | Pass |
| cycle | Pass |

- Long-path fixture: `42` nodes / `107` edges
- Full evidence: `107` relationships
- Selected answer evidence: `8` relationships
- Path-edge evidence coverage: `100.0%`

All values are copied from versioned stage reports; limitations remain attached to each module report.
