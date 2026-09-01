# Stage 4 relationship evidence and citation report

- Generated at: `2026-09-01T06:19:30.196924+00:00`
- Dataset profile: `full_local`
- Embedding model: `intfloat/multilingual-e5-small`
- Relationship corpus: `708` documents
- Cold model/index warmup: `3761.557 ms` (`hit`)

## Evidence retrieval

| Strategy | Recall@5 | MRR@5 | nDCG@5 | Top-1 | P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| global_vector | 83.3% | 0.708333 | 0.738446 | 66.7% | 63.029/65.01 ms |
| graph_scoped_vector | 100.0% | 1.0 | 1.0 | 100.0% | 56.085/56.324 ms |

## Citation validation

- Citation Integrity: `6/6 = 100.0%`
- Invalid Evidence IDs: `0`
- Human-labeled Top-1 correctness: `6/6 = 100.0%`

> Graph-scoped retrieval can rank only relationships already selected by the prerequisite graph; vector similarity cannot alter the learning path.

The six-case reviewed fixture is directional and not statistically representative. Production `verification_status` remains separate from evaluation relevance labels. Per-case ranks, scores, hashes, and failures are in the adjacent JSON report.
