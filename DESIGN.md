# Re:Learn Design

Status: draft written before implementation; finalized at the end of the UI overhaul to describe what was actually built.

## 1. Design goal

Re:Learn should feel like a polished interactive learning platform in the spirit of Brilliant, centred on learning, understanding, practice, feedback, progression, curiosity and confidence. It is not an AI debugging dashboard, a model console or an admin analytics tool. The AI pipeline (diagnosis, quick checks, targeted hints, resolution, mastery) keeps running behind the scenes. Its internals live in a separate **Insights** view for judges and teachers.

## 2. Visual language

- Dark theme with a purple accent, subtle radial gradients behind the main column, rounded cards (16 px radius), soft 1 px borders.
- Generous spacing, large question type, minimal icons (text plus a symbol, never colour alone).
- Smooth, subtle motion: cards fade and rise in, feedback slides in, progress dots fill.
- Strong, visible focus rings.
- Its own identity: purple-to-violet gradient on the progress bar and the lesson header chip.

## 3. Tokens

Defined as CSS variables on `:root` in the injected stylesheet, and mirrored in `.streamlit/config.toml` for native widgets. Contrast was measured with the WCAG formula.

| Token | Value | Use | Contrast on background / surface |
|---|---|---|---|
| `--bg` | `#0F0D1A` | page background | n/a |
| `--surface` | `#181526` | cards | n/a |
| `--elevated` | `#211D33` | question card, inputs | n/a |
| `--primary` | `#7C5CFF` | accents, focus ring, progress | 4.42 / 4.12 (non-text, ≥ 3 required) |
| `--primary-strong` | `#6A4BEF` | filled button background | white text 5.43 |
| `--secondary` | `#A78BFA` | links, highlights | 7.06 / 6.57 |
| `--text` | `#F4F2FF` | primary text | 17.38 / 16.18 |
| `--text-2` | `#B9B3D1` | secondary text | 9.55 / 8.88 |
| `--muted` | `#8A84A6` | supporting text | 5.43 / 5.05 (4.60 on elevated) |
| `--success` | `#3DD68C` | correct state | 10.25 / 9.54 |
| `--warning` | `#F5B544` | hint state | 10.59 / 9.86 |
| `--error` | `#FF6B7A` | wrong state (never alone; always with an icon and text) | 6.99 / 6.50 |
| `--border` | `#2E2A45` | card borders | n/a |

## 4. Typography

The existing Streamlit font stack ("Source Sans", then system UI fallbacks).

| Role | Size and weight |
|---|---|
| Page title | 2.0 rem, 700 |
| Section heading | 1.25 rem, 700 |
| Question text | 1.35 rem, 600, line-height 1.45 (the largest body text) |
| Body | 1.0 rem, 400 |
| Supporting text | 0.9 rem, `--muted` |
| Button text | 1.0 rem, 600 |
| Progress text | 0.85 rem, 600, letter-spacing 0.02 em |

## 5. Layout

- **Lesson (landing) page:** a welcome header, a "Continue learning" card, a grid of concept cards (name, one-line subtitle, status: "Not started", "In progress", "Mastered" from the backend), a "Start guided demo" button, and a small footer link to Insights.
- **Question page:** a back link and lesson progress at the top; the concept title and subtitle; a large question card (the visual focus) with the answer input and a "Your thinking" box; Check Answer as the primary action.
- **Answer states:** a feedback card below the question card.
  - Correct: success styling, "Why it works", Continue.
  - Incorrect: calm wording, a hint, Try Again and Reveal Answer.
  - Revealed: the answer and "Why it works", clearly separated, with Try Another Question of This Type and Continue.
- **Explanation state:** a "Why it works" card inside the feedback card.
- **Progress state:** "Question n of N" with dots filled from real lesson state.
- **Completion state:** a lesson summary card ("Nice work!"), with backend mastery shown as "Mastered" only when the backend says so, and next-concept options.

## 6. Learning flow

Lesson → Question → Check Answer → feedback → explanation → practice → mastery.

- **Check Answer** is the primary action, and is submitted with Enter or the button. Each attempt is logged by the existing pipeline.
- **Correct:** a positive state, a short "Why it works" explanation from the question template, and Continue. If the backend says the student is working through a tricky idea that has not been locked in, the next items are the existing reassessment items, presented as "One more to lock it in".
- **Incorrect:** "Let's work through this." plus a hint, with Try Again and Reveal Answer. The hint comes from the existing targeted explanation, shortened. The second wrong attempt on the same question gives a more explicit hint, which adds the key idea sentence.
- **Quick check:** when the backend wants a diagnostic probe, the student sees an ordinary short question labelled "Quick check".
- **Reveal Answer:** hidden until pressed. It shows the answer and "Why it works", with no penalty. It is logged as a `reveal` attempt with `revealed = true` and gives no mastery evidence. It offers Try Another Question of This Type.
- **Try Another Question of This Type:** same concept, preferring templates that contain the same tricky idea, never a question id already seen this session, with new parameters. If nothing is left, a friendly message and Continue.
- **Mastery loop:** the existing misconception state machine and concept mastery are the only source of truth; there is no separate streak counter. The visit is capped at 6 answer checks per concept. After that the student sees "Let's come back to this later", a `review_flag` is logged, and the lesson continues.
- **Progress:** "Question n of N" for the lesson (N = 5 practice questions) with dots.

## 7. Removed from the student UI (moved to Insights)

- "Why did the AI make this prediction?" panel
- AI Decision Trace (practice and assessment)
- Sources used for this intervention
- Strategy names
- Model Evaluation page
- Analytics dashboard and learner profile with posteriors
- Confidence, probability bars, entropy, route wording, misconception codes and names
- Probe wording ("fits two closely related ideas")
- Transfer, trap and resolution status wording, difficulty-engine reasons
- Active-model badge and the technical demo walkthrough

## 8. Student language

Use "Nice work!", "You're getting it.", "Almost there.", "Let's try a similar one.", "Here's a hint.", "Now try it yourself.", "Let's work through this.", "One more to lock it in.", "Quick check". Say "tricky idea" or "common mix-up" instead of "misconception". Never show: misconception, model confidence, prediction probability, decision trace, intervention source, strategy, evaluation.

## 9. Progress, responsiveness, accessibility, motion

- **Progress:** a thin gradient bar plus "Question n of N" text and dots, all from flow state. "Mastered" appears only from backend state.
- **Responsive:** a single column with max-width 760 px. At 375 px, 16 px gutters and stacked buttons. Touch targets are at least 44 px tall. No horizontal scroll at 375, 768 or 1280.
- **Accessibility:** body text contrast at least 4.5:1 (table above); a visible 3 px focus ring in `--primary`; every action is a native button or form, so the keyboard reaches all of them; feedback is announced through a `role="status" aria-live="polite"` region; correct and wrong use an icon plus text, never colour alone; `prefers-reduced-motion` disables animation.
- **Motion:** 180–260 ms ease-out fade and rise on cards and feedback; progress width transitions; hover lifts on concept cards.
