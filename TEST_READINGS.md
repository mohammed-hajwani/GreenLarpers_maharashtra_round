# Test Readings

Every value below comes from a real run. The raw outputs are in the appendix and in `docs/test_runs/`. **Before** is commit `d3a69ea` (`main`, before the UI overhaul). **After** is filled in from the final runs on `ui/student-learning-flow`.

## 1. Test environment

| Item | Before | After |
|---|---|---|
| OS | Windows 11 Home 10.0.26200 | pending |
| Python | 3.11.9 | pending |
| Key packages | streamlit 1.65.0, scikit-learn 1.9.1, torch 2.14.1+cpu, sentence-transformers 6.1.0 | pending |
| Dev-only | playwright (chromium headless shell 153) in `requirements-dev.txt` | pending |
| Test command | `python -m pytest -q` | pending |
| Readings command | `python scripts/ui_readings.py baseline` | pending |

## 2. Functional tests

| Check | Before | After |
|---|---|---|
| Full pytest suite | 121 passed, 0 failed | pending |
| `?health=1` | `ok`, `model: v1_embedding` | pending |
| App exceptions on the practice page after a wrong answer (AppTest) | 0 | pending |

## 3. Question flow tests

| Check | Before | After |
|---|---|---|
| 10 consecutive question requests for one concept without answering: unique stems | 1 of 10 (the same question repeats) | pending |
| No repeated question within a session | Not present before this change | pending |
| Lesson progress indicator | Not present before this change | pending |

## 4. Answer validation tests

| Check | Before | After |
|---|---|---|
| "idk" with no reasoning is screened, not graded | screened (true) | pending |
| Real wrong answer with reasoning reaches diagnosis | yes (not screened) | pending |
| Check Answer works from the keyboard | Enter submits the text answer form | pending |

## 5. Reveal Answer tests

| Check | Before | After |
|---|---|---|
| Reveal Answer button | Not present before this change | pending |
| Revealed attempt logged with `revealed = true` | Not present before this change | pending |
| Revealed attempt gives no mastery evidence | Not present before this change | pending |

## 6. Try Another Question tests

| Check | Before | After |
|---|---|---|
| Same concept and same mix-up | Not present before this change | pending |
| Not a duplicate within the session | Not present before this change | pending |
| Friendly message when nothing new can be generated | Not present before this change | pending |

## 7. Mastery and concept loop tests

| Check | Before | After |
|---|---|---|
| "Pass first item, fail trap → not resolved" | passes | pending |
| Resolution requires transfer, trap and delayed retest | passes (`test_s6_assessment`) | pending |
| Loop capped at 6 attempts per concept visit, with a review flag | Not present before this change | pending |
| "Mastered" shown only from backend state | Not present before this change | pending |

## 8. UI tests

| Check | Before | After |
|---|---|---|
| Banned strings in the student view after one wrong answer | 11 hits: "Decision Trace" ×1, "confidence" ×4, "probability" ×3, "misconception" ×3 | pending |
| Banned strings on the landing screen | 0 | pending |
| Separate Insights view (`?view=insights`) | Not present before this change | pending |
| Theme: dark, purple accent | Not present (Streamlit default theme) | pending |

## 9. Responsive tests

| Width | Before (horizontal scroll on the practice page, Playwright) | After |
|---|---|---|
| 375 | none | pending |
| 768 | none | pending |
| 1280 | none | pending |

Before screenshots: `docs/screenshots/before/practice_{375,768,1280}.png`.

## 10. Existing AI and backend tests

| Area | Before | After |
|---|---|---|
| Classifiers, calibration, routing, probes, mastery, difficulty, trace, dashboards, demo, progress, RAG, services | all pass within the 121 | pending |

## 11. Known issues

| Before | After |
|---|---|
| The student flow exposes model internals; questions repeat when re-requested; no reveal or retry; no visit cap | pending |

## 12. Changes made

pending

## Appendix: raw outputs

### Baseline pytest (`python -m pytest -q`)

```
........................................................................ [ 59%]
.................................................                        [100%]
121 passed in 27.00s
```

### Baseline readings (`python scripts/ui_readings.py baseline`)

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

### Baseline responsive check (Playwright, `scrollWidth > innerWidth`)

```
{375: {'horizontal_scroll': False}, 768: {'horizontal_scroll': False}, 1280: {'horizontal_scroll': False}}
```
