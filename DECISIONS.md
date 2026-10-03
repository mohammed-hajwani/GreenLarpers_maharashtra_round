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
