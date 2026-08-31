# Priority recommendation

An XGBoost classifier recommends a priority for a report. **The recommendation is
advisory.** An authority reviewer confirms or overrides it, and only the confirmed value
becomes `final_priority`.

```
Report ──▶ feature extraction ──▶ XGBoost ──▶ predicted_priority + confidence
                                                        │
                                          Authority reviews and confirms
                                                        ▼
                                                 final_priority
```

Both values are stored, along with who confirmed and when, so how often humans disagree
with the model is measurable rather than guessed at.

## Classes

`Low`, `Medium`, `High`, `Critical`.

## Features

`backend/ml/features.py`:

| Feature | Meaning |
| --- | --- |
| `severity_ordinal` | Citizen-reported severity, 0–2 |
| `issue_impact` | How completely the issue type blocks step-free access (0.35–0.90) |
| `source_trust` | Reliability weight of the reporting channel |
| `has_image` | Photo evidence attached |
| `description_length`, `description_words` | Detail in the report |
| `age_days` | How long the report has been open |
| `hour_of_day`, `is_weekend` | Reporting time in IST |
| `is_validated` | Already validated by a reviewer |
| `issue_0 … issue_6` | One-hot issue type |

Issue impact weights encode the accessibility judgement explicitly:

```
Ramp Blocked            0.90    Waterlogging       0.70
No Accessible Entrance  0.85    Footpath Damaged   0.55
Stairs / No Ramp        0.80    Other              0.35
Blocked Crossing        0.75
```

## Training

There is no historical corpus for a new deployment, so the model is trained on a
**deterministic synthetic corpus** (`build_training_set`, seed `20260831`): 4000 reports
sampled across every issue type, severity, source and age, labelled by a transparent
rule engine plus calibrated Gaussian noise. The noise stops the tree from simply
memorising the thresholds and makes it learn the interactions between them.

```python
XGBClassifier(
    n_estimators=180, max_depth=4, learning_rate=0.16,
    subsample=0.9, colsample_bytree=0.9,
    objective="multi:softprob", num_class=4,
    eval_metric="mlogloss", tree_method="hist",
    random_state=20260831, n_jobs=1,
)
```

Training happens on first use and takes a second or two. The booster is cached in
process and persisted to `ML_MODEL_DIR` (default `/tmp/routesathi-ml`), so warm
containers reuse it.

**Replacing the synthetic corpus is the intended next step.** Once enough reports carry
a human-confirmed `final_priority`, train on those instead: the columns needed are
already recorded on every report.

## Fallbacks

| Order | Backend | When |
| --- | --- | --- |
| 1 | `xgboost` | Normal operation |
| 2 | `sklearn-gbm` | XGBoost cannot be imported |
| 3 | `rules` | Neither is available, or `ML_ENABLED=0` |

The rule engine is the same scoring function used to label the training data, so its
output is consistent with the model's rather than being an unrelated heuristic:

```
score = 0.40·impact + 0.34·severity + 0.10·source_trust
      + 0.08·min(age/21, 1) + 0.05·has_image + 0.03·is_validated (+0.02 long description)

score ≥ 0.78 → Critical    ≥ 0.62 → High    ≥ 0.42 → Medium    else Low
```

Every prediction names its backend, and so does `GET /api/health`.

## API

```
POST /api/authority/reports/{report_id}/priority/predict
```

```json
{
  "report_id": "RS-1001",
  "predicted_priority": "Critical",
  "confidence": 0.7184,
  "model": "xgboost",
  "rationale": [
    "'Ramp Blocked' fully blocks step-free access",
    "Citizen-reported severity is High",
    "Photo evidence attached",
    "Source: Community"
  ],
  "probabilities": { "Low": 0.01, "Medium": 0.06, "High": 0.21, "Critical": 0.72 }
}
```

The `rationale` strings are generated from the same features the model consumes, so the
reviewer sees why a report scored the way it did rather than a bare label.

```
POST /api/authority/reports/{report_id}/priority/confirm
{ "final_priority": "Critical" }
```

The audit entry records both values and an `overridden` flag.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ML_ENABLED` | `1` | `0` uses the rule engine exclusively |
| `ML_MODEL_DIR` | `/tmp/routesathi-ml` | Model cache; must be writable |

On Vercel only `/tmp` is writable. If the path cannot be written the model is retrained
in memory — slower on a cold start, but never a failure.

## Note on CSV import

The importer runs **no** inference. Imported reports have null priority columns until a
reviewer explicitly asks for a recommendation.
