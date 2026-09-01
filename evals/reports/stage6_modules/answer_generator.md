# Answer Generator

Source: `stage5_answer_generator.json`  
Git commit: `4d9a2293f97162eb58ce3955c2ff801a00631fe6`

## Metrics

| Metric | Result |
| --- | ---: |
| Response Schema Valid (fallback) | 100.0% |
| LLM Structured Contract (fixture) | 100.0% |
| Language Match | 100.0% |
| Citation Integrity | 100.0% |
| Required Citation Completeness | 100.0% |
| Prompt Leak Rate | 0.0% |
| Unsupported Claim Rate (deterministic fallback) | 0/6 claim templates (0.0%) |

## Configuration

```json
{
  "implementation": "real deterministic fallback",
  "external_llm_called": false
}
```

## Limits

- No external LLM was called in this run.
- The fallback unsupported-claim result follows deterministic claim lineage; real-model unsupported-claim rate and human faithfulness remain unmeasured.
- Fake-LLM tests validate the contract, not model quality or faithfulness.
