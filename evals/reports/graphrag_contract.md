# GraphRAG Contract Regression

- Overall: `PASS`
- Fixture: `42` path nodes / `107` path edges
- Full evidence: `107`
- Selected answer evidence: `8`
- Path-edge evidence coverage: `100.0%`
- Answer-evidence citation coverage: `100.0%`

## Status gates

- `not_found_rejected`: `PASS`
- `already_mastered`: `PASS`
- `truncated`: `PASS`
- `cycle`: `PASS`

The full evidence set is deterministic graph coverage. Only the bounded selected set is passed to the Answer Generator.
