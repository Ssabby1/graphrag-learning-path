# Stage 0 frozen baseline

- Generated at: `2026-08-30T12:13:04.580104+00:00`
- Dataset profile: `full_local`
- Git commit: `dfe94a51119c3e62f92dc9ebd0bd3fe1788cf480`
- Vector backend: `hashing-fallback`
- Reranker: `token-overlap`

> This report records the pre-refactor implementation. Unsupported capabilities are reported as unsupported; they are not estimated.

## Core metrics

| Metric | Count | Value |
| --- | ---: | ---: |
| Planner target Top-1 accuracy | 20/30 | 66.7% |
| Planner rejection accuracy | 5/6 | 83.3% |
| Hashing vector Top-1 accuracy | 1/30 | 3.3% |
| Hashing vector Recall@5 | 2/30 | 6.7% |
| All-target structural closure recall | 1503/1514 | 99.3% |
| Targets with truncated closure | 11/190 | 5.8% |
| Topological violation rate | 0/2573 | 0.0% |
| Relationship evidence Recall@K | 0/6 | 0.0% |
| Structured answer success | 0/6 | 0.0% |
| Prompt-template leak rate | 6/6 | 100.0% |
| Required citation completeness | 0/5 | 0.0% |

## Language breakdown

| Language | Planner Top-1 | Vector Top-1 | Vector Recall@5 |
| --- | ---: | ---: | ---: |
| en | 0.0% | 14.3% | 14.3% |
| mixed | 33.3% | 0.0% | 0.0% |
| zh | 95.0% | 0.0% | 5.0% |

## Observed limitations

- `11` targets lose ancestors under the current 8-edge traversal cap.
- The resolver indexes concept IDs, Chinese names, and sparse descriptions only; aliases are absent.
- The hashing tokenizer accepts ASCII words only, so Chinese queries produce zero query vectors.
- Relationship-level evidence and evidence IDs are not implemented, so evidence retrieval is scored as unsupported.
- The answer builder returns a prompt-shaped string and exposes neither `answer_source` nor `answer_language`.

Detailed per-case failures and the complete configuration snapshot are in the adjacent JSON report.
