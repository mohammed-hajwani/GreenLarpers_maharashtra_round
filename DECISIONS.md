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
