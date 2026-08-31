# Stage 5 Answer Generator report

- Generated at: `2026-08-31T04:14:09.921321+00:00`
- Cases: `6`
- Real external LLM evaluated: `false`

## Offline and contract results

| Strategy | Structured | Fallback | LLM contract | Language | Citation integrity | Completeness | Direction | Prompt leak | P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| offline_fallback | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.003/0.567 ms |
| structured_contract_fixture | 100.0% | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.01/0.031 ms |

## Guardrails

- Malformed JSON, timeout, and hallucinated-citation scenarios passed: `3/3`
- Final invalid evidence IDs: `0`

## Measurement boundary

- `structured_contract_fixture` uses a deterministic fake LLM. It validates parsing, language, citation, and fallback contracts only.
- No external LLM/API key is required or called by this evaluation.
- Unsupported Claim Rate and human Faithfulness remain unmeasured; they must not be reported as 100%.
