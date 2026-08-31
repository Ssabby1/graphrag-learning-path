# Stage 2 multilingual retrieval report

- Generated at: `2026-08-30T12:54:31.296556+00:00`
- Dataset profile: `full_local`
- Embedding model: `intfloat/multilingual-e5-small`
- Dimension: `384`
- Minimum acceptance score: `0.8`
- Minimum Top-1 margin: `0.01`
- Concept corpus: `190` documents
- Relationship corpus: `708` documents

## Target Resolver metrics

| Metric | Count | Value |
| --- | ---: | ---: |
| Top-1 accuracy | 30/30 | 100.0% |
| Recall@5 | 30/30 | 100.0% |
| Rejection accuracy | 6/6 | 100.0% |
| False rejection rate | 0/30 | 0.0% |
| Cross-lingual Top-1 accuracy | 10/10 | 100.0% |

- MRR@5: `1.0`
- Latency P50/P95: `22.106 / 24.123 ms`
- Cache rebuilt/hit: `1 / 35`
- Stage 0 vector Top-1: `0.03333333333333333`
- Stage 0 vector Recall@5: `0.06666666666666667`

## Language breakdown

| Language | Top-1 | Recall@5 |
| --- | ---: | ---: |
| zh | 100.0% | 100.0% |
| en | 100.0% | 100.0% |
| mixed | 100.0% | 100.0% |

## Notes

- Concept and relationship evidence use separate deterministic corpora and cache keys.
- E5 query/passages prefixes are applied by the embedding adapter.
- The acceptance threshold is reported explicitly; this directional dataset is too small for statistical claims.
- Full per-query ranks, scores, failures, hashes, and runtime configuration are in the adjacent JSON report.
