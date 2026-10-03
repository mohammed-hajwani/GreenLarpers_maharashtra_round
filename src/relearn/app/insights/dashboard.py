import pandas as pd
import streamlit as st

from relearn import services as svc
from relearn.pipeline import Tutor

EMPTY = "No data yet. Answer a few practice questions to populate this view."


def _section(title: str, rows: list | dict, render) -> None:
    st.subheader(title)
    if not rows:
        st.caption(EMPTY)
        return
    render(rows)


def render_dashboard(tutor: Tutor, learner_id: str) -> None:
    data = svc.dashboard(tutor, learner_id)
    if data["empty"]:
        st.info(EMPTY)
        return
    cols = st.columns(2)
    cols[0].metric("Overall mastery", f"{100 * data['overall_mastery']:.1f}%")
    avg = data["average_confidence"]
    cols[1].metric("Average diagnostic confidence", "n/a" if avg is None else f"{100 * avg:.1f}%")
    _section(
        "Concept mastery",
        data["concept_mastery"],
        lambda r: st.bar_chart(pd.DataFrame(r).set_index("concept")["mastery"], y_label="mastery"),
    )
    _section(
        "Mastery over time",
        data["mastery_over_time"],
        lambda r: st.line_chart(pd.DataFrame(r).pivot_table(index="step", columns="concept", values="mastery").ffill()),
    )
    _section(
        "Misconception distribution (wrong practice answers by diagnosis)",
        data["misconception_distribution"],
        lambda r: st.bar_chart(pd.Series(r, name="count")),
    )
    _section(
        "Probe effectiveness (entropy in bits, confidence before and after each probe)",
        data["probe_effectiveness"],
        lambda r: st.dataframe(pd.DataFrame(r), hide_index=True, width="stretch"),
    )
    _section(
        "Intervention effectiveness (concept mastery before and after each reassessment)",
        data["intervention_effectiveness"],
        lambda r: st.dataframe(pd.DataFrame(r), hide_index=True, width="stretch"),
    )
    st.subheader("Learning progress estimate")
    st.caption(data["progress_label"])
    if data["progress_estimates"]:
        st.dataframe(pd.DataFrame(data["progress_estimates"]).round(3), hide_index=True, width="stretch")
    else:
        st.caption(EMPTY)
    _section(
        "Difficulty progression (1 easy, 2 medium, 3 hard)",
        data["difficulty_progression"],
        lambda r: st.line_chart(pd.DataFrame(r).set_index("attempt")["level"]),
    )


def render_evaluation_page() -> None:
    data = svc.evaluate()
    if not data["available"]:
        st.warning("evaluation not run")
        return
    m = data["metrics"]
    st.caption(f"Data provenance: **{m['data_provenance']}** · generated {m['generated_at']}")
    ds = m["dataset"]
    st.markdown(
        f"Dataset: **{ds['total']}** samples, splits {ds['split_sizes']} ({ds['split_method']}). "
        f"Hand-written set: **{ds['handwritten_test_size']}** items ({ds['handwritten_provenance']})."
    )
    st.subheader("Model comparison")
    st.dataframe(pd.DataFrame(m["comparison"]).round(3), hide_index=True, width="stretch")
    for kind, meta in data["metadata"].items():
        if not meta:
            continue
        result = m["models"].get(kind)
        with st.expander(f"{kind}: {meta['name']} v{meta['version']} (trained {meta['training_date']})"):
            st.markdown(f"Features: {meta['feature_method']}")
            if meta.get("candidate_val_macro_f1"):
                st.markdown(f"Validation candidates (macro-F1): {meta['candidate_val_macro_f1']}")
            if result:
                for split in ("test", "handwritten"):
                    st.markdown(f"**{split} confusion matrix** (rows true, columns predicted)")
                    cm = pd.DataFrame(
                        result[split]["confusion_matrix"],
                        index=result[split]["labels"],
                        columns=result[split]["labels"],
                    )
                    st.dataframe(cm, width="stretch")
                    st.code(result[split]["classification_report"])
    if "progress_model" in m:
        st.subheader("Progress predictor (simulated learners)")
        st.caption(m["progress_model"]["label"])
        rows = [{"target": t, "model": r["model"], **r["test"]} for t, r in m["progress_model"]["metrics"].items()]
        st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
    if "probing" in m:
        st.subheader("Probe selection on simulated learners")
        st.caption(m["probing"]["method"])
        rows = [
            {
                "model": kind,
                "split": split,
                **{s: r[s]["accuracy_mean"] for s in ("no_probe", "random_probe", "information_gain_probe")},
            }
            for kind, splits in m["probing"]["results"].items()
            for split, r in splits.items()
        ]
        st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
