# Test Readings

Every value below comes from a real run. The raw outputs are in the appendix and in `docs/test_runs/`. **Before** is commit `d3a69ea` (`main`, before the UI overhaul). **After** is the final state of branch `ui/student-learning-flow`.

## 1. Test environment

| Item | Before | After |
|---|---|---|
| OS | Windows 11 Home 10.0.26200 | same |
| Python | 3.11.9 | same |
| Key packages | streamlit 1.65.0, scikit-learn 1.9.1, torch 2.14.1+cpu, sentence-transformers 6.1.0 | same (no new hosting dependencies) |
| Dev-only | playwright (chromium headless shell 153) in `requirements-dev.txt` | playwright 1.63.0, dev-only; `requirements.txt` unchanged in size and contains no playwright |
| Test command | `python -m pytest -q` | `python scripts/gate.py L` (ruff, no-comments check, full pytest) |
| Readings command | `python scripts/ui_readings.py baseline` | `python scripts/ui_readings.py after`, `python scripts/ui_screenshots.py`, `python scripts/ui_a11y_check.py` |

## 2. Functional tests

| Check | Before | After |
|---|---|---|
| Full pytest suite | 121 passed, 0 failed | 140 passed, 0 failed |
| `?health=1` | `ok`, `model: v1_embedding` | `ok` (`test_health_still_ok`, `test_health_query`) |
| App exceptions on the student view after a wrong answer (AppTest) | 0 | 0 |

## 3. Question flow tests

| Check | Before | After |
|---|---|---|
| 10 consecutive planner requests for one concept without answering: unique stems | 1 of 10 | 1 of 10 (backend planner unchanged; see Known issues) |
| 10 consecutive "Try another question" in the lesson flow: unique question ids | Not present before this change | 10 of 10, all in Force vs Motion |
| No repeated question within a session | Not present before this change | `test_no_repeats_in_session`: 21 ids, all unique (pass) |
| Lesson progress indicator | Not present before this change | "Question n of 5" with dots, from flow state (`test_live_lesson_actions`) |

## 4. Answer validation tests

| Check | Before | After |
|---|---|---|
| "idk" with no reasoning is screened, not graded | screened (true) | screened; the lesson shows "Give it a go…" and does not count the check (`test_screened_answer_not_counted`) |
| Real wrong answer with reasoning reaches diagnosis | yes | yes (feedback status `incorrect`, then quick check when the backend asks for one) |
| Check Answer works from the keyboard | Enter submits the text answer form | Enter in the answer field submits; the polite live region appears (`a11y_check.json`: `enter_submits_answer: true`) |

## 5. Reveal Answer tests

| Check | Before | After |
|---|---|---|
| Reveal Answer button | Not present before this change | present after a wrong answer; shows the answer and "Why it works" (`test_reveal_is_logged_and_not_mastery_evidence`) |
| Revealed attempt logged with `revealed = true` | Not present before this change | `reveal` attempt with `revealed: true` in the store (pass) |
| Revealed attempt gives no mastery evidence | Not present before this change | mastery-log length unchanged by the reveal; Try again disabled after a reveal (pass) |

## 6. Try Another Question tests

| Check | Before | After |
|---|---|---|
| Same concept and same mix-up | Not present before this change | same concept; template contains the diagnosed mix-up (`test_try_another_same_concept_and_mix_up`, pass) |
| Not a duplicate within the session | Not present before this change | pass (see section 3) |
| Friendly message when nothing new can be generated | Not present before this change | "That's every version we have of this one…" with Continue (`test_exhausted_try_another`, pass); Free Fall offers more than 20 distinct variants before running out (`test_exhausted_bank_message`) |

## 7. Mastery and concept loop tests

| Check | Before | After |
|---|---|---|
| "Pass first item, fail trap → not resolved" | passes | passes (unchanged test) |
| Resolution requires transfer, trap and delayed retest | passes | passes; the lesson's lock-in uses the same reassessment, and a failed trap is not resolved (`test_lockin_trap_failure_not_resolved`) |
| Loop capped at 6 checks per concept visit, with a review flag | Not present before this change | after 6 wrong checks: "Let's come back to this later", `review_flag` logged, lesson completes, concept status `review` (`test_loop_cap_defers_and_flags_review`, pass) |
| "Mastered" shown only from backend state | Not present before this change | `concept_status` = mastered only when stored concept mastery ≥ 0.70 and every seen tricky idea in the concept is `resolved`; after a failed lock-in it is not mastered (pass) |
| Guided demo end to end | Not present before this change (only the technical walkthrough) | 16 steps through the real engine; covers quick check, incorrect, revealed, correct and "Locked in for now" (`test_guided_demo_runs`, `test_guided_demo_screens_are_clean`) |

## 8. UI tests

| Check | Before | After |
|---|---|---|
| Banned strings in the student view after one wrong answer | 11 hits: "Decision Trace" ×1, "confidence" ×4, "probability" ×3, "misconception" ×3 | 0 (also 0 after a reveal) |
| Banned strings on every student screen | Not measured | 0 on landing, all 16 guided-demo states, the live lesson (wrong, reveal, try another) and the completion screen (AppTest); 0 in all 27 Playwright states |
| Separate Insights view (`?view=insights`) | Not present before this change | present; shows the why panel, decision trace, strategy and sources, model evaluation and dashboard from real stored data (`test_insights_shows_every_moved_element`) |
| Student modules import Insights | n/a | never (AST test) |
| Theme: dark, purple accent | Streamlit default | tokens in `theme.css` plus `.streamlit/config.toml` |
| Visible focus state | default | 3 px solid outline on the focused button (`a11y_check.json`) |
| Body text contrast against the background | not measured | question 17.38, subtitle 9.55, progress 9.55, footer 5.43 |
| Feedback announced politely; icon plus text | no | `role="status" aria-live="polite"`, starts with ✓ / ✗ / → plus words |
| `prefers-reduced-motion` | no | animation name `none` under reduced motion |

## 9. Responsive tests

| Width | Before (practice page) | After (9 states each: landing, question, quick check, hint, second hint, revealed, correct, lock-in, live lesson) |
|---|---|---|
| 375 | no horizontal scroll | no horizontal scroll; every visible button ≥ 44 px tall; buttons stack full width |
| 768 | no horizontal scroll | no horizontal scroll; every button ≥ 44 px |
| 1280 | no horizontal scroll | no horizontal scroll; every button ≥ 44 px |

Screenshots: `docs/screenshots/w{375,768,1280}/*.png`, `docs/screenshots/report.json`.

## 10. Existing AI and backend tests

| Area | Before | After |
|---|---|---|
| Classifiers, calibration, routing, probes, mastery, difficulty, trace, dashboards, demo, progress, RAG, services | all pass within the 121 | all pass within the 140. Five AppTest files now open the Insights view via a shared `insights_app` helper, because those pages moved there. |

## 11. Known issues

| Before | After |
|---|---|
| The student flow exposed model internals; questions repeated when re-requested; no reveal or retry; no visit cap | **Planner repeats:** the backend planner on its own still returns the same question when asked again without an answer. The lesson flow prevents repeats with a per-browser-session seen-set, which resets on a new session. |
| | **No reference screenshot:** none was provided in `docs/reference/`, so the design follows the written design language in the brief. |
| | **"Ask your own question" moved:** the free-text box now lives only in the Insights AI practice console, not in the student flow. |
| | **"Mastered" cannot appear on a first visit:** resolution needs a delayed retest, which is served after 3 further attempts (usually in a later lesson). This is intended. |
| | **Lock-in progress:** lock-in items appear inside the current question slot of the progress indicator, labelled "One more to lock it in · k of 4". |
| | **Guided demo is read-only:** it always uses the kicked-ball scenario, and its buttons are disabled while "Next step" drives it. |
| | **Insights needs the learner id:** opened without `&learner=`, Insights shows an empty state for a new learner. The footer link always includes it. |

## 12. Changes made

- **Separation (`relearn/app/student` and `relearn/app/insights`):** the student flow is the default route. Technical components moved unchanged into Insights at `?view=insights&learner=…`, linked from the footer as "Insights (for judges and teachers)".
- **Lesson engine (`relearn/learning`):**
  - Check Answer; quick check (backend probe); short hints with escalation.
  - Try Again; Reveal Answer (logged, no mastery evidence); Try Another (same concept and mix-up, no repeats).
  - Lock-in through the existing reassessment; review items through the existing retest.
  - A 6-check visit cap with a review flag; 5-question lessons; a guided demo script.
- **Student UI components:** lesson header, progress indicator, question card, answer input, feedback, explanation card, navigation buttons, concept cards, completion card; a theme stylesheet and the `.streamlit/config.toml` dark theme.
- **Services:** `log_event`, `misconception_states`, `concept_status`, `traces`, `passages_by_id`.
- **Content:** a one-line subtitle per concept.
- **Docs and scripts:** `DESIGN.md`, `docs/UI_AUDIT.md`, this file; `scripts/ui_readings.py`, `scripts/ui_screenshots.py`, `scripts/ui_a11y_check.py` (dev-only); `requirements-dev.txt`.

## Appendix: raw outputs

### Before: pytest (`python -m pytest -q`)

```
........................................................................ [ 59%]
.................................................                        [100%]
121 passed in 27.00s
```

### After: gate (`python scripts/gate.py L`)

```
140 passed in 29.42s
$ ...python.exe -m ruff check src scripts tests app.py
$ ...python.exe -m pytest -q
gate L passed
```

### Before: readings (`python scripts/ui_readings.py baseline`)

```json
{
  "repeats": {"questions_requested": 10, "unique_stems": 1},
  "screening_flags": {"idk": true, "blank_reasoning_answer": false, "real": false},
  "student_view_banned_strings": {
    "landing": {},
    "after_wrong_answer": {"Decision Trace": 1, "confidence": 4, "probability": 3, "misconception": 3},
    "exceptions": 0
  }
}
```

### After: readings (`python scripts/ui_readings.py after`)

```json
{
  "repeats": {"questions_requested": 10, "unique_stems": 1},
  "flow_try_another": {"questions_requested": 10, "unique_question_ids": 10, "concepts": ["force_motion"]},
  "screening_flags": {"idk": true, "blank_reasoning_answer": false, "real": false},
  "student_view_banned_strings": {
    "landing": {}, "after_wrong_answer": {}, "after_reveal": {},
    "feedback_status": "revealed", "exceptions": 0
  }
}
```

### After: accessibility (`python scripts/ui_a11y_check.py`)

```json
{
  "tab_focus": {"tag": "BUTTON", "text": "Continue learning", "outline": "solid 3px"},
  "contrast_vs_background": {".rl-question": 17.38, ".rl-subtitle": 9.55, ".rl-progress-text": 9.55, ".rl-footer": 5.43},
  "enter_submits_answer": true,
  "live_region_text": "✗ Let's work through this. Here's a hint: Consider a hockey puck on perfectly frictionless ice: ...",
  "icon_plus_text": true,
  "reduced_motion_animation": "none"
}
```

### Responsive (Playwright, `scrollWidth > innerWidth`, buttons under 44 px, banned strings)

```
Before: {375: {'horizontal_scroll': False}, 768: {'horizontal_scroll': False}, 1280: {'horizontal_scroll': False}}
After:  27 of 27 states (9 states x 3 widths): horizontal_scroll False, small_buttons [], banned []
```
