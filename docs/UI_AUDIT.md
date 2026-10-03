# UI Audit (before the student-learning-flow overhaul)

Audited on 2026-10-03 at commit `d3a69ea` (`main`), on branch `ui/student-learning-flow`.

## Project map

| Area | Where | Notes |
|---|---|---|
| UI framework | Streamlit 1.65 (`app.py` → `relearn.app.streamlit_app.main`) | Single page app; the sidebar radio selects a "page" |
| Pages | Practice, Dashboard, Profile, Model Evaluation, Demo mode | All rendered by `streamlit_app.main` |
| Components | `app/practice.py` (practice flow), `app/views.py` (diagnosis, probe, intervention, assessment, profile renderers), `app/trace_view.py` (why panel and decision trace), `app/dashboard.py` (analytics and model evaluation), `app/demo.py` (scripted run) | Render functions, no components package |
| Styling | Streamlit defaults; `.streamlit/config.toml` sets only server options | No theme, no tokens, no injected CSS |
| State | `st.session_state` keys listed in `practice.KEYS` (phase string: answer, probe, diagnosed, intervened, assessing, assessed) | Flow logic lives inside the Streamlit functions; not testable without AppTest |
| Questions | 48 templates in `content/question_templates`, rendered by `data.generator.make_question`; adaptive choice by `adaptive.planner.plan_next_question` | Params cycle by attempt count, so repeats within a session are possible |
| Item bank | `content/item_bank.yaml`: transfer, trap and retest items per misconception | Used by `assessment.planner` |
| Answer checking | `models.inference.answer_key_verdict` (mcq and numeric exact match) plus the classifier; `diagnosis.screening` filters non-answers | |
| Diagnosis, probe, intervention | `diagnosis.diagnoser`, `diagnosis.disambiguator` (information gain), `intervention.selector/grounded/checker` | |
| Resolution and mastery | `learner.state` (misconception state machine, resolution criteria), `learner.mastery` (concept Beta mastery), `assessment.evaluator` | Single source of truth for "resolved" |
| Storage | `learner.store` SQLite: attempts, learner_state, concept_mastery, mastery_log, decision_trace, intervention_stats, llm_cache | |
| Service layer | `relearn.services` | The UI already calls only this |
| Tests | 121 passing, AppTest-based UI tests in `test_s8_app`, `test_sH_trace`, `test_sJ_dashboard`, `test_sK_demo_fallback`, `test_screening` | |

## Technical AI elements currently in front of students

| Element | Location |
|---|---|
| "Likely misconception: … calibrated confidence N%", top-3 probability bars, route and entropy wording | `views.render_diagnosis` (Practice page) |
| "Your answer fits two closely related ideas… probe" | `practice._probe_form` |
| "Why did the AI make this prediction?" expander | `trace_view.render_practice_trace` (Practice page) |
| "AI Decision Trace" expanders (practice and assessment) | `trace_view` (Practice page) |
| "Strategy: `counterexample` targeting M01 …" | `views.render_intervention` |
| "Sources used for this intervention (mode)" | `views.render_intervention` |
| Transfer and trap labels, "Status: NOT RESOLVED", item correctness tables | `views.render_assessment` |
| "Next question selected because your mastery … Difficulty: medium · mastery 50% maps to the medium band" | `practice._topic_picker` |
| Active-model badge, "MiniLM embedding hybrid" | `streamlit_app.model_badge` and sidebar |
| Dashboard, Profile (posterior P(held)), Model Evaluation, Demo mode with traces | sidebar pages |

## Current learning flow

Pick concept → answer and reasoning → diagnosis card with misconception name and probabilities → optional probe → "Help me with this" → intervention with strategy and sources → "Check my understanding" → 4-item form with transfer and trap → status with resolution wording → "Try another explanation". The learner sees model internals at every step.

## Missing student features

| Feature | Status |
|---|---|
| Reveal Answer | Not present |
| Try Again on the same question | Not present (after a wrong answer the flow moves to diagnosis and intervention) |
| Try Another Question of This Type (same concept and mix-up, no repeats) | Not present (the next question is chosen by the planner and may repeat a stem) |
| Progress indicator ("Question 2 of 5") | Not present |
| Mastery loop with a cap per visit and a review flag | Not present (state machine exists, no visit-level loop) |
| Short student-language hints with escalation | Not present (full intervention text with technical framing) |
| Separate Insights view | Not present |
| Theme, tokens, responsive and accessibility work | Not present |

## Backend calls for each new student action

| Student action | Backend |
|---|---|
| Start lesson or Continue learning | `services.next_question` (planner) with session de-duplication; `services.due_retests` before new practice |
| Check Answer | `services.screen` → `services.diagnose` (logs attempt) → if routed to probe: `services.next_probe` → shown as "Quick check" → `services.answer_probe` → `services.finalize` (mastery, misconception state, decision trace) |
| Hint after a wrong answer | `services.intervention` (selector escalates strategies; the text is shortened into a hint) |
| Try Again | Re-submits the same question through Check Answer |
| Reveal Answer | Logs a `reveal` attempt with `revealed: true`; no mastery evidence |
| Try Another Question of This Type | Template generator for the same concept, preferring templates with the same mix-up, excluding question ids seen this session |
| One more to lock it in | `services.plan_assessment` → items shown one at a time → `services.submit_assessment` |
| Review check | `services.due_retests` → `services.submit_retest` |
| Mastered badge | Concept is mastered only when the backend shows concept mastery ≥ 0.70 and every seen misconception in the concept is `resolved` |
| Come back later (loop cap) | Logs a `review_flag` attempt for the concept |
