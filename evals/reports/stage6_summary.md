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
| Structured Answer Generator | 0.0% structured | 100.0% | Keep contract + fallback |

All values are copied from versioned stage reports; limitations remain attached to each module report.
