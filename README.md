---
title: Re:Learn
sdk: streamlit
sdk_version: 1.65.0
app_file: app.py
pinned: false
---

# Re:Learn: an adaptive misconception tutor for introductory mechanics

## Problem

Most practice tools only grade answers right or wrong. A student who answers "a 2.7 N force keeps the ball rolling" is not just wrong: they hold a specific misconception, and the right help depends on which one. A single correct follow-up answer also does not prove the student has learned anything.

## Solution

Re:Learn reads the question, the answer and the learner's own reasoning, and then:

1. **Diagnoses** which of 12 classic misconceptions is behind the answer, with a calibrated confidence.
2. **Disambiguates** look-alike misconceptions with the diagnostic probe that has the highest expected information gain.
3. **Intervenes** with an explanation targeted at that misconception, grounded in retrieved passages from the content.
4. **Reassesses** with transfer items, a trap item and a delayed retest. A misconception is resolved only when all three pass; mastery scores never shortcut this rule.
5. **Tracks** per-concept mastery as a Beta posterior, adapts difficulty, and logs every decision to an inspectable **AI Decision Trace**.

## Architecture

```
content/ (12 misconceptions, 7 concepts, 48 templates, 12 probes, 36 interventions, 66 items, 65 hand-written tests)
   │
   ▼ data/generator → clean → deduplicate → split by template (train / val / test)
   │
   ▼ models/
   │   baseline       TF-IDF (word + char) → logistic regression
   │   v1_embedding   TF-IDF + MiniLM(answer) + MiniLM(working) → logistic regression
   │   both: temperature-calibrated on validation, versioned with metadata.json
   │
   ▼ diagnosis/  diagnoser (posterior, confidence, entropy, route: accept / probe / uncertain)
   │             disambiguator (expected-information-gain probe choice, Bayesian update)
   │             explain (TF-IDF contributions, nearest training examples, word occlusion)
   │
   ▼ intervention/  selector (escalation) → grounded builder (RAG + optional LLM) → checker
   ▼ assessment/    planner (3 transfer + trap) → evaluator; delayed retest
   ▼ learner/       misconception state machine + concept mastery (Beta) + SQLite store
   ▼ adaptive/      difficulty engine (mastery bands + recent accuracy + severity + confidence)
   ▼ progress/      simulated-learner progress predictor
   ▼ trace.py       one decision-trace row per interaction
   │
   ▼ pipeline.Tutor ──► services/ ──► Streamlit UI
                                      (Practice, Dashboard, Profile, Model Evaluation, Demo mode)
```

## Models

| Component | Method |
|---|---|
| Baseline classifier | TF-IDF word 1-2 grams and char 3-5 grams, balanced logistic regression |
| Advanced classifier (`v1_embedding`) | `sentence-transformers/all-MiniLM-L6-v2` embeddings of the answer and of the working, concatenated with TF-IDF features, then logistic regression. Picked on validation against MiniLM-only logistic regression and gradient boosting. |
| Calibration | Temperature scaling on validation. ECE is reported before and after. |
| Routing | accept at or above a threshold tuned on validation (v1 0.70, baseline 0.80); probe from 0.50; uncertain below 0.50 |
| Adaptive probing | Picks the probe with the largest expected entropy drop, using each probe's stored expected answers with 10% answer noise; at most 2 probes |
| Learner model | Per-concept Beta mastery with decay; per-misconception unseen / active / intervened / resolved / relapsed states, tied only to the resolution criteria |
| Difficulty adaptation | Rule bands (below 0.40 easy, 0.40 to 0.70 medium, above 0.70 hard) adjusted by streaks, active misconceptions, uncertain diagnoses and the previous band. Deterministic. |
| Progress prediction | Logistic regression trained on simulated learner trajectories. **Estimate based on simulated learners, not validated on real students.** |
| RAG and LLM intervention | Cosine retrieval over 114 content passages. With `ANTHROPIC_API_KEY`, Claude rewrites the intervention from the retrieved passages, and the output must pass the checker; otherwise the app uses the template plus a retrieved passage. The LLM never classifies. |

## Results

All numbers come from `reports/metrics.json` (`make eval`). **Data provenance: synthetic.** There are 2296 template-generated samples, split by template into train 1097, val 568 and test 631; test templates never appear in training. A separate set of 65 hand-written items was written by the team in different phrasing (not real student data).

Macro-F1 ("with answer key" also uses the question's answer key for MCQ and numeric items):

| Model | Synthetic test, model only | Synthetic test, with key | Hand-written, model only | Hand-written, with key |
|---|---|---|---|---|
| Baseline | 0.683 | 0.867 | 0.775 | 0.831 |
| v1 embedding hybrid | 0.632 | 0.775 | **0.831** | **0.846** |

v1 was selected on validation (macro-F1 0.649 vs 0.574) and generalizes better to the new phrasing in the hand-written set. It is worse on the synthetic test split, and we report that rather than hide it.

Calibration ECE (uncalibrated → calibrated): baseline test 0.195 → 0.117; v1 hand-written 0.179 → 0.116; v1 synthetic test 0.093 → 0.149 (worse).

Probe selection on simulated learners (confusable subset, mean accuracy over 5 seeds):

| Model / split | No probe | Random relevant probe | Information-gain probe |
|---|---|---|---|
| v1 / val | 0.628 | 0.831 | **0.876** |
| v1 / test | 0.726 | 0.855 | **0.886** |
| baseline / val | 0.831 | 0.963 | **0.965** |
| baseline / test | 0.820 | 0.928 | **0.945** |

Information gain beats random in all 4 settings. Simulated learners answer by the same expected-answer map the likelihood uses, so these lifts are upper bounds.

Progress predictor (1000 held-out simulated learners): reach mastery AUC 0.974 (base rate 0.684); misconception persists AUC 0.885 (base rate 0.096, so its 0.90 accuracy is no better than always predicting "no").

Latency on a laptop CPU: diagnosis 0.03 s, explanation 0.06 s. Health check after a cold start of Streamlit: about 10 s.

## Limitations

- All training data is synthetic, from one domain (introductory mechanics). The hand-written set is small (65 items) and was written by the team.
- Probe, resolution and progress evaluations use simulated learners whose behavior matches the model's own assumptions. Nothing has been validated on real students.
- Difficulty labels are judgment calls. Some concept bands have only one template (listed in `difficulty_coverage.gaps`).

## Future work

More subjects; real interaction data and classroom pilots; multilingual and voice input; larger fine-tuned transformers trained on real answers; long-term learner modeling across sessions.

## Environment variables

| Variable | Purpose |
|---|---|
| `RELEARN_DB` | SQLite path (default: OS temp dir `relearn.db`) |
| `RELEARN_MODEL_CACHE` | Where the MiniLM encoder is cached (default `.cache/hf`) |
| `RELEARN_FORCE_MODEL` | `baseline` or `none`, to test fallbacks |
| `ANTHROPIC_API_KEY` | Optional; enables grounded LLM interventions |
| `RELEARN_LLM_MODEL` | Optional Claude model override (default `claude-opus-5-5`) |
| `HF_TOKEN` | Optional; for deploying the Space |

## Train, evaluate and run

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt -e .
make train
make eval
make test
make app
```

On machines without `make`, run the scripts named in the `Makefile` directly. Open **Demo mode → Start demo → Show all** for the full scripted walkthrough. Health check: `/?health=1`.

## Deploy to Hugging Face Spaces

1. Create a Space (SDK Streamlit, CPU basic, public).
2. Push this repository to it. The front matter at the top of this README configures the Space; `.streamlit/config.toml` disables the file watcher for a fast cold start.
3. Optionally add `ANTHROPIC_API_KEY` as a Space secret.
4. Open `https://<user>-<space>.hf.space/?health=1`. It should report `ok` and the active model.

The MiniLM encoder (about 90 MB) downloads once on first start. If the Hub is unreachable the app falls back to the committed baseline, and if no model loads it falls back to a replay labeled as such.

Live URL: not deployed yet.
