# Evidence Retriever

Source: `stage4_evidence.json`  
Git commit: `4b455217bcfeae93aaeb1c71b34fd17f9506c4eb`

## Metrics

| Metric | Result |
| --- | ---: |
| Evidence Recall@5 | 100.0% |
| MRR@5 | 1.000 |
| nDCG@5 | 1.000 |
| Citation Integrity | 100.0% |
| Invalid Evidence IDs | 0 |

## Configuration

```json
{
  "model": {
    "embedding_model": "intfloat/multilingual-e5-small",
    "dimension": 384,
    "normalization": true
  },
  "corpus": {
    "document_count": 708,
    "hash": "458f3f053665e146a87d5b5ea4369146bbe54e40ea83a0521524b6b7f367f465",
    "schema": "evidence-v1"
  },
  "strategy": "graph_scoped_vector"
}
```

## Limits

- 6 author-curated directional fixtures.
- Extraction confidence is not instructional correctness.
