# Architecture Audit (pre-upgrade)

Audited on 2026-10-03 at commit `eac3799` on `main`.

## Verification results

| Check | Result |
|---|---|
| `pytest -q` | 45 passed, 0 failed |
| `scripts/evaluate.py` | ran; saved to `reports/reference/baseline_metrics_pre_upgrade.json` |
| `streamlit run app.py`, `?health=1` | `ok`, `model: baseline` |

Reference baseline on the held-out-template test split (627 samples):

| Metric | Value |
|---|---|
| Accuracy, model only | 0.640 |
| Macro-F1, model only | 0.664 |
| Accuracy, with answer key | 0.844 |
| Macro-F1, with answer key | 0.850 |
| Confusable-subset accuracy (n=428) | 0.783 |
| ECE, after temperature 0.6 | 0.143 |

## Current system

**Data pipeline.** `content/question_templates/*.yaml` holds 48 templates, 4 per misconception, each with parameter ranges, a correct rule, and wrong rules per misconception. `data/generator.py` instantiates them with a seeded RNG, balancing per-label counts through `data.target_per_label`, which gives 2270 samples. `data/splits.py` splits by template within each primary misconception: the last template goes to test and the second-to-last to val. `data/validate.py` checks schema, duplicate ids, leakage, labels and balance. Generated data is not deduplicated by text.

**Models.** `models/baseline.py` is a TF-IDF (word 1-2 grams plus char_wb 3-5 grams) logistic-regression model with balanced classes. `models/calibration.py` runs a temperature grid search on validation NLL, plus ECE. The artifacts live in `artifacts/`. There is no embedding model and no model metadata or versioning.

**Inference path.** `diagnosis/diagnoser.diagnose` computes model probabilities, then applies the answer key for mcq and numeric questions, then takes the top-3 and sets the ambiguity flag. `ambiguous` means a same-group rival is within `tau` of the top-1 label. There are no confidence-threshold routes.

**Probe logic.** `diagnosis/disambiguator.py` picks the first unused probe in the group whose expected answers separate top-1 from the rival, then multiplies by 0.85 or 0.10 and renormalises over the top-3 only, with at most 2 probes. Selection does not use information gain and logs no entropy.

**Learner model.** `learner/state.py` keeps a per-misconception Beta posterior of the misconception being held, plus a state machine (unseen, active, intervened, resolved, relapsed). There is no per-concept mastery and no before/after logging.

**Resolution logic.** `assessment/evaluator.py` and `learner/state.py` require at least 2 of 3 transfer items, a passed trap, a delayed retest after `retest_gap` attempts, and a posterior below 0.25. This is tested, including the "pass first item, fail trap, not resolved" case.

**Interventions.** `intervention/selector.py` uses an ordered strategy list with escalation and a `flag_for_human` exit. `builder.py` fills templates and can prepend an optional LLM wrapper (stub by default, cached in SQLite). `checker.py` checks length, presence of the correct concept, and forbidden claims.

**Storage.** `learner/store.py` holds SQLite tables `attempts`, `learner_state`, `intervention_stats` and `llm_cache`.

**UI.** `app/streamlit_app.py` has Practice, Profile and Demo mode pages, a health query and a footer notice. `app/demo.py` runs the scripted learner through the real pipeline and keeps a recorded replay. `pipeline.Tutor` orchestrates the flow.

## Gaps against the upgrade objectives

| Objective | Gap |
|---|---|
| B: stronger classifier | No embedding model; no model directories with `metadata.json`; no hand-written test set; no deduplication; the evaluation report lacks per-class precision and recall, a classification report and a provenance label |
| C: calibrated routing | Temperature scaling exists, but ECE is reported only after calibration; no accept, probe or uncertain thresholds; the diagnosis lacks model name, version and route |
| D: information-gain probes | Selection is heuristic; the posterior covers the top-3 only; no entropy or gain logging; no random-probe comparison |
| E: learner mastery | No per-concept mastery; no update log with before and after values |
| F: adaptive difficulty | Templates and items have no difficulty labels; question selection is random |
| G: progress prediction | Not present; there are no simulated learner trajectories |
| H: explainability and trace | No feature attributions, no similar examples, no decision-trace table |
| I: RAG | Not present |
| J: dashboards | Profile shows the posterior and timeline only; no analytics page; no model evaluation page |
| K: demo and fallback | Demo covers the resolution story but not mastery, entropy, difficulty or the trace; the loader has no embedding tier |
| L: service layer | `pipeline.Tutor` is a partial service layer, but the UI calls it directly and there is no `services/` package |
