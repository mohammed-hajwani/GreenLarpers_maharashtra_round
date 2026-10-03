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
