import pandas as pd
import streamlit as st

from relearn.content import load_content

STATE_BADGE = {
    "unseen": ":gray[unseen]",
    "active": ":red[active]",
    "intervened": ":orange[intervened]",
    "resolved": ":green[RESOLVED]",
    "relapsed": ":red[relapsed]",
}


def label_name(label: str) -> str:
    info = load_content().misconceptions.get(label)
    return f"{label} · {info.label}" if info else "correct (none)"


def render_top_labels(top_labels: list) -> None:
    for label, p in top_labels:
        st.progress(min(max(float(p), 0.0), 1.0), text=f"{label_name(label)} — {float(p):.0%}")


def render_diagnosis(data: dict) -> None:
    if data.get("stem"):
        st.markdown(f"**Question:** {data['stem']}")
        st.markdown(f"**Answer:** `{data['answer']}`  \n**Working:** _{data.get('working') or '—'}_")
    if data["is_correct"]:
        st.success("Correct. No misconception detected.")
        return
    top = data["top_labels"][0][0]
    info = load_content().misconceptions[top]
    confidence = data.get("confidence") or data["top_labels"][0][1]
    st.error(f"Likely misconception: **{label_name(top)}** — calibrated confidence {confidence:.1%}")
    st.caption(info.description)
    render_top_labels(data["top_labels"])
    route = data.get("route", "accept")
    if route == "probe":
        st.warning(
            "Confidence is below the accept threshold, so the system asks a diagnostic probe. "
            f"Entropy {data.get('entropy', 0):.3f} bits."
        )
    elif route == "uncertain":
        st.warning("Confidence is below 50%: diagnosis is uncertain and routed to a probe or review.")


def render_probe(data: dict) -> None:
    st.markdown(f"**Probe:** {data['stem']}")
    st.markdown(f"Learner chose: `{data['answer']}`")
    if "expected_gain" in data:
        runners = ", ".join(f"{pid} ({g:.3f})" for pid, g in data["runners_up"]) or "none"
        st.markdown(
            f"Expected information gain **{data['expected_gain']:.3f} bits** (runners-up: {runners}). "
            f"Entropy **{data['entropy_before']:.3f} → {data['entropy_after']:.3f} bits**."
        )
    cols = st.columns(2)
    with cols[0]:
        st.caption("Before probe")
        render_top_labels(data["before"])
    with cols[1]:
        st.caption("After probe")
        render_top_labels(data["top_labels"])


def render_intervention(data: dict) -> None:
    st.markdown(f"**Strategy:** `{data['strategy']}` targeting {label_name(data['misconception'])}")
    st.info(data["text"])
    st.markdown(f"**Think about it:** {data['follow_up_prompt']}")


def status_line(state: str, trap_passed, pending) -> None:
    if state == "resolved":
        st.success("Status: RESOLVED")
    elif trap_passed is False:
        st.error("Status: NOT RESOLVED — the trap item exposed the misconception. Escalating strategy.")
    elif state == "intervened" and pending is not None:
        st.warning(f"Status: not yet resolved — passed reassessment, retest due after {pending} more attempts.")
    else:
        st.error(f"Status: NOT RESOLVED ({state}).")


def render_assessment(data: dict) -> None:
    rows = pd.DataFrame(data["items"])
    rows["correct"] = rows["correct"].map({True: "✅", False: "❌"})
    st.dataframe(rows, hide_index=True, width="stretch")
    st.markdown(f"Transfer: **{data['transfer']}** · Trap passed: **{data['trap_passed']}**")
    if "mastery_before" in data:
        st.markdown(f"Concept mastery: **{data['mastery_before']:.1%} → {data['mastery_after']:.1%}**")
    status_line(data["state"], data["trap_passed"], data.get("pending_retest_in"))


def render_practice_rows(data: dict) -> None:
    rows = pd.DataFrame(data["rows"])
    rows["correct"] = rows["correct"].map({True: "✅", False: "❌"})
    st.dataframe(rows, hide_index=True, width="stretch")


def render_retest(data: dict) -> None:
    st.markdown(f"**Retest:** {data['stem']}")
    st.markdown(f"Learner answered `{data['answer']}` — {'correct' if data['correct'] else 'wrong'}")
    if "mastery_before" in data:
        st.markdown(f"Concept mastery: **{data['mastery_before']:.1%} → {data['mastery_after']:.1%}**")
    status_line(data["state"], None, None)


def render_profile(data: dict) -> None:
    rows = data["rows"]
    if not rows:
        st.info("No misconceptions recorded yet.")
        return
    table = pd.DataFrame(rows)
    table["state"] = table["state"].str.upper()
    st.dataframe(table, hide_index=True, width="stretch")
    st.bar_chart(table.set_index("misconception")["posterior_held"], y_label="P(held)")
    events = [
        {
            "step": i + 1,
            "event": e["kind"],
            "ref": e["ref_id"],
            "state": e.get("state", ""),
            "correct": e["correct"],
        }
        for i, e in enumerate(data["timeline"])
    ]
    with st.expander("Timeline", expanded=False):
        st.dataframe(pd.DataFrame(events), hide_index=True, width="stretch")
    dash = data.get("dashboard")
    if dash and not dash["empty"]:
        st.markdown(f"**Overall mastery:** {dash['overall_mastery']:.1%}")
        st.bar_chart(pd.DataFrame(dash["concept_mastery"]).set_index("concept")["mastery"], y_label="mastery")
        st.line_chart(
            pd.DataFrame(dash["mastery_over_time"])
            .pivot_table(index="step", columns="concept", values="mastery")
            .ffill()
        )


def render_trace_step(data: dict) -> None:
    from relearn.app.trace_view import render_practice_trace

    m = data.get("mastery")
    if m:
        concept = load_content().concepts[m["concept"]].name
        st.markdown(f"**{concept}** mastery {m['before']:.1%} → {m['after']:.1%} after this answer.")
    render_practice_trace(data)


def render_next(data: dict) -> None:
    st.info(data["headline"])
    st.caption(f"Difficulty: **{data['band']}** · " + "; ".join(data["reasons"]))


RENDERERS = {
    "diagnosis": render_diagnosis,
    "probe": render_probe,
    "intervention": render_intervention,
    "assessment": render_assessment,
    "practice": render_practice_rows,
    "retest": render_retest,
    "profile": render_profile,
    "trace": render_trace_step,
    "next": render_next,
}


def render_step(step: dict) -> None:
    st.subheader(step["title"])
    RENDERERS[step["kind"]](step["data"])
