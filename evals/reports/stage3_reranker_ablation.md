# Stage 3 reranker ablation

- Generated at: `2026-08-31T03:39:11.965112+00:00`
- Dataset profile: `full_local`
- Bi-encoder: `intfloat/multilingual-e5-small`
- Cross-encoder: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
- Device: `cpu`
- Candidate/final K: `8 / 5`

## Quality and latency

| Strategy | Top-1 | MRR@5 | Recall@5 | Rerank P50 | Rerank P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| none | 86.7% | 0.925 | 100.0% | 0.002 ms | 0.003 ms |
| token_overlap | 83.3% | 0.911111 | 100.0% | 0.089 ms | 0.124 ms |
| cross_encoder | 83.3% | 0.897222 | 100.0% | 54.74 ms | 109.998 ms |

## Decision

- Recommended default: `none`
- Cross-encoder Top-1 gain vs none: `-3.3%`
- Language subgroup regressions: `['en']`
- Quality gate passed: `False`
- Latency gate passed: `True`

> Enable the cross-encoder only if it improves Top-1, causes no language subgroup Top-1 regression, and reranking P95 is at most 1000 ms on the target Mac.

This is a directional 30-case concept-ranking ablation. Curated aliases are part of the corpus, and the result is not a claim of statistical significance. Per-case scores and failures are available in the adjacent JSON report.
