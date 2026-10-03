# Demo script (about 7 minutes)

## Before you start
- Run `streamlit run app.py` and open http://localhost:8501 at least 2 minutes early. The first diagnosis loads MiniLM, which takes a while.
- Open a second tab at http://localhost:8501/?view=insights&learner=guided-demo
- Keep `docs/deck/ReLearn_pitch.pptx` open. Have a backup screen recording of the guided demo ready.

## Flow
1. **Slides 1 to 3 (90 s):** the problem (one wrong answer, three wrong ideas) and the loop.
2. **Live demo (3 min):** click **Start guided demo**, then press **Next step** and narrate:
   - Wrong answer with reasoning → targeted hint with a diagram or simulation ("see it, try it").
   - Quick check: one question separates look-alike ideas.
   - Transfer questions, then the trap question. Point out that passing the first question does not resolve the misconception.
   - Delayed retest, then explain it back in your own words.
   - Completion: the learning journey map updates.
3. **Insights tab (1 min):** the class misconception map, then Student decisions → AI Decision Trace → "Why did the AI make this prediction?". Mention the teacher review queue for unfamiliar mistakes.
4. **Slides 7 to 11 (2 min):** results. Say "simulated" wherever the slide says it.
5. **Slide 13 (30 s):** limitations, then invite a judge to type their own answer.

## Likely questions
- *Is the data real?* No. It is synthetic from 48 templates; 65 hand-written answers test new phrasing. A classroom pilot is the next step.
- *Why not just use an LLM?* The classifier runs on a free CPU, is calibrated and inspectable, and its decisions are evaluated. An LLM can optionally reword hints but never decides the misconception.
- *What about a mistake it has never seen?* Leave-one-misconception-out test AUROC is 0.71. Distinct ideas are flagged; look-alikes are absorbed by their sibling, so flags go to a teacher queue.
