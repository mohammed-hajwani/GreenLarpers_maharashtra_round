---
title: Re:Learn
sdk: streamlit
sdk_version: 1.65.0
app_file: app.py
pinned: false
---

# Re:Learn

Re:Learn diagnoses the misconception behind a learner's answer in introductory mechanics, tells look-alike misconceptions apart with short probes, delivers a targeted intervention, and only marks a misconception resolved after transfer items, a trap item, and a delayed retest.

Core loop: `submit → diagnose → (probe) → intervene → reassess → update learner model`.

## Status: mentoring slice

This is a 5-hour vertical slice. The full loop works end to end with a TF-IDF baseline. The DistilBERT model, Hugging Face hosting, and efficiency loops come next. See `DECISIONS.md`.

## Run locally

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -e .
.venv/Scripts/python.exe scripts/train.py
.venv/Scripts/python.exe -m streamlit run app.py
```

Open the **Demo mode** page and press **Start demo**, then **Next step**. Health check: `?health=1`.

## Architecture

```
content/ (taxonomy, 48 templates, probes, interventions, item bank)
   │
   ▼
data/generator ──► 2270 synthetic samples ──► template-level split (train / val / test)
   │
   ▼
models/baseline (TF-IDF word+char → logistic regression, temperature-scaled)
   │
   ▼
diagnosis/diagnoser ──► ambiguous within a confusable group? ──► diagnosis/disambiguator (Bayesian probe update)
   │
   ▼
intervention/selector → builder → checker   (escalates through strategies, flags for a human when exhausted)
   │
   ▼
assessment/planner → evaluator  (3 transfer + 1 trap, then a delayed retest)
   │
   ▼
learner/state + store (Beta posterior, state machine, SQLite)  ──►  pipeline.Tutor  ──►  Streamlit app
```

## Results (held-out templates, baseline)

| Metric | Value |
|---|---|
| Macro-F1, model only | 0.66 |
| Macro-F1, with answer key for mcq and numeric | 0.85 |
| Probing lift on the confusable subset (val / test) | +3.8 / +1.2 points |
| Tests | 45 passing |

The confusion matrix is in `reports/confusion_matrix.png` and the full metrics are in `reports/metrics.json`.

## Limitations

- All data is synthetic and template-generated, from one domain.
- Test templates are unseen at training time, but the phrasing style is shared.
- Probing lift is below the +10 point target, because most confusable-subset errors are cross-group.
- Evaluation uses scripted and simulated learners, not real students.
