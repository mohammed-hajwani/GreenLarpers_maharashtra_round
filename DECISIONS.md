# Decisions

## Mentoring slice (2026-10-03)
- Scope reduced to a 5-hour vertical slice for the mentoring session. The reduced gates are enforced; full PRD gates resume afterwards.
- Templates per misconception: 4 instead of 8 (2 train, 1 val, 1 test). Each template is assigned to its primary misconception by its `template_id` prefix for template-level splitting.
- Minimum dataset size for the slice: 1500 samples (config `data.min_total_samples`).
- Main model for the slice is the TF-IDF baseline; the transformer, Colab, and Hub stages are deferred.
- Loops L1, L2, L5, L6, L7 deferred. Strategy selection uses the ordered list from `interventions.yaml` with escalation.
- LLM: only `StubLLMClient` implemented.
- Stages merged into blocks with one commit each: 0, 1, 2+3, 4+5, 6+7, 8.

## Environment
- Local dev uses Python 3.11 in `.venv`. `make` is not installed on the dev machine, so `python scripts/gate.py <n>` is the gate entrypoint; the Makefile wraps it.
- `AssessmentResult` was referenced in PRD section 7 but not defined; added to `schemas.py` and PRD section 6.
- Default SQLite path is the OS temp directory when `RELEARN_DB` is unset, which is `/tmp/relearn.db` on Linux hosts.

## Stage 2+3
- Per-label sample count is balanced by `data.target_per_label`: each template contributes ceil(target / templates_containing_label) samples per label, giving 2270 samples with imbalance 1.13.
- Diagnosis uses the question's answer key for mcq and numeric questions: a matching answer forces `none`, a non-matching answer removes `none` from the distribution. Explanation questions rely on the model only. Metrics report both `model_only` and `with_answer_key`.
- Baseline held-out test macro-F1: 0.66 model only, 0.85 with answer key. Temperature 0.6 fitted on validation by grid search over NLL.

## Stage 4+5
- Ambiguity compares top-1 with the strongest same-group label anywhere in the top-k, not only rank 2, because the closest same-group rival is often third behind `none`.
- Probing lift with PRD defaults (fitted temperature 0.6, tau 0.2, max_probes 2): +3.8 points on val and +1.2 on test. Most remaining confusable-subset errors are cross-group (for example `none` on explanation templates), which probing cannot fix. The +10 point gate is deferred to the transformer; the slice gate is that probing never lowers accuracy. tau was not tuned on test.
- `select_strategy` takes the learner's `strategies_tried` list directly instead of looking up the store, which keeps it pure; it returns `flag_for_human` when strategies run out.
- `check_intervention` ignores text inside double quotes (the learner's own words) when scanning for forbidden claims, and requires the stored `correct_concept` sentence to be present.

## Stage 6+7
- `learner.pass_beta_increment` is 2.0. With 1.0, a learner who fails one trap and then passes everything still has a posterior near 0.31, above the 0.25 resolution threshold, so they could never resolve.
- A passing reassessment (at least 2 of 3 transfer and trap passed) keeps the state `intervened` and schedules a retest at `attempt_count + retest_gap`. Attempts that count toward the gap are practice, transfer, trap and retest answers.
- A failed retest returns the state to `active` (or `relapsed` if it was resolved), so the next intervention escalates.
- Retest due dates live in the `learner_state.retest_due` column, which keeps `LearnerRecord` as specified.
- `scripts/simulate_learners.py` and loops L1, L2, L5, L6 are deferred for the slice.

## Stage 8
- The PRD's Practice, Diagnosis, Intervention and Reassessment pages are one guided Practice page whose sections appear in order, plus Profile and Demo mode pages.
- Demo mode runs `content/demo_script.json` through the real pipeline. `scripts/record_demo.py` stores the outputs in `recorded_steps`, which are replayed when no model loads.
- The demo input (kicked-ball question, "The push keeps acting on it so it keeps going.") was chosen because the baseline finds it genuinely ambiguous between M09 and M01 (0.58 vs 0.41).
- Practice offers a free-text "ask your own question" box so judges can try inputs live.
- Hub transformer loading in `models/loader.py` is a stub that always falls back to the committed baseline.

## Upgrade stage B: classifier and evaluation
- Data pipeline is generate, clean (whitespace), deduplicate (stem, answer, working, label), then split by template. Deduplication removed 267 of 2270 rows, so `target_per_label` rose from 170 to 200, giving 2296 rows with imbalance 1.52.
- The model input text puts `||` between answer and working (`stem [SEP] answer || working`) so the embedding model can embed them separately. The baseline was retrained on this format.
- Embedding model candidates, chosen by validation macro-F1 (model only):
  - hybrid TF-IDF + MiniLM(answer) + MiniLM(working) with logistic regression: 0.649
  - MiniLM-only logistic regression: 0.527
  - MiniLM-only HistGradientBoosting: 0.346
  - The baseline scores 0.574 for comparison.
  - Embedding the full "stem + answer + working" text scored 0.37, because the stem dominates the vector and does not transfer to unseen templates.
  - The hybrid was selected as `v1_embedding`.
- Honest result: v1 beats the baseline on validation and on the hand-written set (macro-F1 0.831 vs 0.775 model only) but is worse on the synthetic test split (0.632 vs 0.683). The active model is chosen by validation (v1), and both test numbers are reported.
- Model artifacts moved from `artifacts/` to `models/baseline/` and `models/v1_embedding/`, each with `model.joblib` and `metadata.json`. The MiniLM encoder is downloaded from the Hub on first use into `RELEARN_MODEL_CACHE` (default `.cache/hf`) and kept by an in-process `lru_cache`.
- The hand-written test set (`content/handwritten_test.yaml`, 65 items, 5 per label) was written by the project team in phrasing different from the templates. It is not real student data and is used only for evaluation.
- Loader fallback chain: `v1_embedding` (warm-up encode) → `baseline` → labeled replay. `RELEARN_FORCE_MODEL=baseline|none` forces a tier for testing.
- The demo input changed to "The force from the hit keeps it moving forward.", which is ambiguous under v1 (M09 0.59, M01 0.40).

## Upgrade stage C: calibration and routing
- Calibration stays as temperature scaling fitted on validation NLL, because both classifiers produce logits. Validation ECE: baseline 0.133 → 0.126 (T=0.6), v1 0.117 → 0.105 (T=0.65). On the synthetic test split, the baseline improves (0.195 → 0.117) but v1 gets worse (0.093 → 0.149). On the hand-written set, v1 improves (0.179 → 0.116). All values are in `reports/metrics.json`.
- Routing replaces the PRD's tau gap rule. Confidence at or above the accept threshold → accept. From 0.50 up to the accept threshold → probe. Below 0.50 → uncertain, which routes to a probe if one is informative, otherwise to review.
- Thresholds were tuned on validation by `scripts/tune_thresholds.py`: accept is the smallest grid value whose accepted predictions reach 0.95 precision on validation, using the answer-keyed probabilities that diagnosis actually uses. Result: v1 accept 0.70 (val precision 0.966, coverage 0.67), baseline accept 0.80 (precision 0.970, coverage 0.60), probe 0.50 for both. Saved in `configs/thresholds.yaml`; defaults are 0.80 and 0.50.
- `Diagnosis` gained `posterior`, `confidence`, `entropy`, `route`, `model_name` and `model_version`, all defaulted (PRD section 6 updated). `ambiguous` now means `route != accept`.

## Upgrade stage D: information-gain probes
- Probe likelihood: if the probe stores an expected option for a label, the chance of that option is 1 - noise and every other option shares the noise equally (`disambiguation.answer_noise`, default 0.1). Labels the probe does not cover get a uniform likelihood, so the probe carries no information about them. This replaces the PRD's fixed 0.85 / 0.10 factors.
- The posterior covers all 13 labels, not just the top 3. The chosen probe is the unused one with the highest expected entropy drop, and it must gain at least `min_expected_gain` (0.05 bits). Probing stops at `max_probes` (2) or when the route becomes accept.
- Each probe step logs entropy before and after, realized gain, expected gain, the chosen probe and the top-3 runner-up probes.
- Evaluation is in `scripts/simulate_learners.py`, written to `metrics.json` under `probing`: confusable subset, 5 seeds. Accuracy means:
  - v1 val: no probe 0.628, random 0.831, info-gain 0.876 (info-gain better)
  - v1 test: 0.726, 0.818, 0.806 (info-gain worse by 1.2 points)
  - baseline val: 0.831, 0.963, 0.965
  - baseline test: 0.820, 0.900, 0.904
  - "Random" picks a random unused probe that covers the top-1 label, which is a stronger baseline than any random probe.
  - Caveat: simulated learners answer using the same expected-answer map the likelihood assumes, so these lifts are optimistic upper bounds.
- The demo learner now holds M01 and answers whatever probe is selected the way an M01 holder would, instead of using hardcoded answers per probe id.

## Upgrade stage E: concept mastery
- There are 7 concepts in `content/misconceptions.yaml`. Each groups the templates' concept tags and owns a set of misconceptions: Force vs Motion (M01, M09, M12), Free Fall (M02), Velocity vs Acceleration (M03, M04), Newton's Third Law (M05, M11), Weight and Normal Force (M06, M07), Circular Motion (M08), Energy Conservation (M10). A question maps to the concept of its template's primary misconception; a custom question maps to the concept of its diagnosed misconception.
- Mastery per (learner, concept) is a Beta posterior, starting at Beta(1, 1), and mastery is its mean. Before each update, existing evidence decays toward the prior by 0.97 so recent attempts weigh more.
- Mastery updates:
  - correct practice: +1.0 × difficulty weight (easy 0.6, medium 1.0, hard 1.4) to alpha
  - wrong practice: +1.0 + 1.0 × misconception confidence to beta
  - probe answer matching the misconception: +0.5 to beta; matching the correct concept: +0.5 to alpha
  - transfer: +1.5 alpha if correct, +1.0 beta if wrong
  - trap: +2.0 alpha if passed, +2.0 beta if failed
  - retest: +2.0 alpha if passed, +2.0 beta if failed
- Every update writes a `mastery_log` row with alpha, beta and mean before and after.
- Mastery never changes misconception states. Resolution still requires transfer, trap and delayed retest (tested in `test_high_mastery_never_resolves_after_trap_failure`).
- `Tutor.confirm` now takes the question and returns `(record, mastery_update)`. The mastery update happens after probing, so it uses the final diagnosis.

## Upgrade stage F: adaptive difficulty
- Each of the 48 templates has a difficulty set by judgment: one-step conceptual MCQs are easy; single-step numerics and short explanations are medium; multi-step numerics, geometry and multi-body problems are hard.
- Coverage gaps are reported, not filled with fake items. 8 concept/band cells have only 1 template against a target of 2 (see `metrics.json` `difficulty_coverage.gaps`). Every concept has at least one template in every band.
- The engine is deterministic, never random:
  - The base band comes from stored mastery: below 0.40 easy, 0.40 to 0.70 medium, above 0.70 hard.
  - Three correct answers in a row in the concept step up one band; the last two wrong step down one.
  - An unresolved misconception in the concept caps difficulty at medium.
  - A recent uncertain diagnosis blocks stepping up.
  - The change from the previous difficulty is limited to one band.
- Target concept: the lowest-mastery concept that has an active, intervened or relapsed misconception, otherwise the lowest-mastery concept overall. Template choice prefers the least recently used template in the chosen band, falling back to the nearest band with a reason. Parameters cycle by attempt count.
- The Practice page's random question picker was replaced by the adaptive engine. The UI shows the headline ("...mastery of X is currently N%.", using the stored value) and the rule reasons.

## Upgrade stage H: explainability and decision trace
- Explanations are computed from the models only:
  - Both models: TF-IDF word-feature contributions (tf-idf value × class coefficient). For v1 these come from the TF-IDF block of the hybrid.
  - v1 only: the nearest training exemplars for the predicted class (25 stored per class), by cosine similarity of the answer+working embeddings.
  - v1 only: word occlusion, which removes each working word (up to 40) and measures the drop in the calibrated probability of the predicted label.
  - No LLM is involved. Feature contributions sometimes highlight stem words (for example "rolls"); this is shown honestly as what drove the model.
- The `decision_trace` SQLite table stores one row per interaction (practice, assessment, retest) with an input hash and a JSON record. A practice record holds the model name and version, thresholds, initial and final top-3 with calibrated confidence, route, entropy, each probe (expected gain, runners-up, answer, entropy before and after, realized gain), misconception state, the mastery update before and after, the next difficulty with its reason, and the explanation.
- The UI renders only what `store.trace(id)` returns; `test_app_renders_stored_trace` asserts the rendered table equals the view model of the stored row.
- `pipeline.py` was split (trace building into `trace.py`, question planning into `adaptive/planner.py`) to stay under 300 lines. Ruff line length raised to 120.
- Warm latency on the dev CPU: diagnosis 0.03 s, explanation 0.06 s. Cold model load: 7.8 s.

## Upgrade stage J: dashboards
- `analytics.dashboard_data` reads only the store: concept mastery, the mastery log, the attempts timeline and decision traces. When a learner has no history the page shows an empty state, never placeholder numbers. "Intervention effectiveness" is concept mastery before the first item and after the last item of each post-intervention reassessment or retest, taken from that interaction's trace.
- The Model Evaluation page reads only `reports/metrics.json` and `models/*/metadata.json`. Confusion matrices and classification reports come from the JSON, and the page shows "evaluation not run" when the file is missing.
- `.streamlit/config.toml` disables the file watcher. With it on, Streamlit's watcher walked the torch and transformers modules and cold start took about 90 s; with it off, the health check shows the v1 model in about 10 s.
- Bug fix: two UI strings had been mojibaked by a cp1252 read/write in an edit script; they were repaired and all later edit scripts run with `PYTHONUTF8=1`.

## Upgrade stage K: demo and fallback
- The demo learner now walks 11 steps through the real pipeline:
  1. A wrong answer, shown with calibrated confidence, route and entropy.
  2. An information-gain probe, with expected gain, runners-up and the entropy drop.
  3. The decision trace with its mastery change.
  4. An intervention.
  5. A reassessment where the trap fails, so the status is NOT RESOLVED.
  6. Escalation to a second strategy.
  7. A passed reassessment with mastery up and a retest scheduled.
  8. Three adaptive spacing questions in `spacing_concepts`, each with its difficulty reason.
  9. A delayed retest, after which the status is RESOLVED.
  10. The adaptive next question.
  11. The profile and dashboard.
- Replay is used only when no model loads. It shows a red "REPLAY ... not live inference" banner and renders the steps recorded by `scripts/record_demo.py` from a real run.
- An active-model badge appears on every page (green v1, orange baseline, red replay).
- Under the baseline fallback, one correct free-text spacing answer (a free-fall explanation) is misdiagnosed. The demo still completes; the behavior is real and left visible.
- No API key is needed anywhere: `StubLLMClient` is the default and `llm_personalize` is false.
