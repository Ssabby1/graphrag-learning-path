# Path Planner

Source: `graph_validation_report_stage1.json`  
Git commit: `4d9a2293f97162eb58ce3955c2ff801a00631fe6`

## Metrics

| Metric | Result |
| --- | ---: |
| Structural Closure Recall | 1514/1514 (100.0%) |
| Oracle Target Match | 190/190 (100.0%) |
| Topological Violation Rate | 0.0% |
| Full DAG Check | Pass |
| Longest Path | 16 edges |

## Configuration

```json
{
  "dataset_hash": "b679cc2133f4531fc023e65fd7ae1ecf76ce67aa8fdfd227a79ac9b98501b264",
  "concepts": 190,
  "prerequisite_edges": 409
}
```

## Limits

- Full graph remains local because source materials are not redistributable.
- The public sample is synthetic and smaller.
