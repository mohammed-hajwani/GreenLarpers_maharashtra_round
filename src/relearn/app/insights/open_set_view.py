import pandas as pd
import streamlit as st

SCORE_NAMES = {
    "msp": "MSP (1 − top misconception probability)",
    "energy": "Energy (−T·logsumexp of logits)",
    "knn": "kNN distance to training answers",
    "definition": "Distance to misconception definitions",
    "combined": "MSP + kNN rank average",
    "energy_definition": "Energy + definition rank average",
}


def render_open_set(o: dict) -> None:
    st.subheader("Open-Set / Unseen Misconception Evaluation")
    st.caption(
        "Leave-one-misconception-out: the v1 model is retrained 12 times, each time without one misconception, and "
        "each novelty score is judged on whether it flags that misconception's test answers as unfamiliar. "
        f"Thresholds target a {o['target_false_flag_rate_on_val']:.0%} false-flag rate on validation. "
        f"Selected for runtime: **{SCORE_NAMES.get(o['selected_score'], o['selected_score'])}** "
        "(chosen by validation AUROC among scores the app can compute live)."
    )
    scores = pd.DataFrame(o["scores"]).T
    scores.index = [SCORE_NAMES.get(k, k) for k in scores.index]
    st.dataframe(scores.round(3), width="stretch")
    curves = o.get("curves")
    if curves:
        st.markdown("**Rejection curves on test** (share of unseen-misconception answers flagged vs share of known)")
        frame = pd.DataFrame(
            {SCORE_NAMES.get(k, k): c["detection_rate"] for k, c in curves.items()},
            index=next(iter(curves.values()))["false_flag_rate"],
        )
        frame.index.name = "false-flag rate"
        st.line_chart(frame, x_label="false-flag rate (known mistakes flagged)", y_label="detection rate")
    st.markdown("**Per held-out misconception** (test AUROC for each score, plus zero-shot definition matching)")
    rows = pd.DataFrame(o["per_misconception"]).T
    keep = [c for c in rows.columns if c.endswith("_auroc") and c != "test_auroc"]
    keep += [c for c in ("zero_shot_top1", "most_confused_with", "test_unknown_n") if c in rows.columns]
    st.dataframe(rows[keep] if keep else rows, width="stretch")
    if "zero_shot_top1" in rows.columns:
        st.caption(
            "zero_shot_top1: share of the held-out misconception's answers whose working is closest (MiniLM cosine) "
            "to that misconception's own definition among all 12 definitions. Chance is 1/12 ≈ 0.083."
        )
