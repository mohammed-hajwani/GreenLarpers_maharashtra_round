import pandas as pd
import streamlit as st

from relearn.app.insights.visuals import gauge, html, kv_card, occlusion_text, prob_bars
from relearn.content import load_content


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def bits(value: float) -> str:
    return f"{value:.3f} bits"


def concept_name(concept: str) -> str:
    info = load_content().concepts.get(concept)
    return info.name if info else concept


def name(label: str) -> str:
    info = load_content().misconceptions.get(label)
    return f"{label} ({info.label})" if info else "correct (none)"


def practice_rows(record: dict) -> list[tuple[str, str]]:
    rows = [
        ("Trace id", str(record["id"])),
        ("Input hash", record["input_hash"]),
        ("Model", f"{record['model_name']} v{record['model_version']}"),
        (
            "Thresholds",
            f"accept >= {pct(record['thresholds']['accept'])}, probe >= {pct(record['thresholds']['probe'])}",
        ),
        ("Initial prediction", f"{name(record['initial']['predicted'])} at {pct(record['initial']['confidence'])}"),
        ("Initial route", record["initial"]["route"]),
        ("Initial entropy", bits(record["initial"]["entropy"])),
    ]
    for i, p in enumerate(record["probes"], 1):
        rows += [
            (f"Probe {i}", f"{p['probe_id']} (expected gain {bits(p['expected_information_gain'])})"),
            (f"Probe {i} runners-up", ", ".join(f"{pid} {bits(g)}" for pid, g in p["runners_up"]) or "none"),
            (f"Probe {i} answer", p["answer"]),
            (f"Probe {i} entropy", f"{bits(p['entropy_before'])} -> {bits(p['entropy_after'])}"),
            (f"Probe {i} information gain", bits(p["information_gain"])),
        ]
    rows += [
        ("Final prediction", f"{name(record['final']['predicted'])} at {pct(record['final']['confidence'])}"),
        ("Final route", record["final"]["route"]),
        ("Final entropy", bits(record["final"]["entropy"])),
        ("Misconception state", record["misconception_state"] or "n/a (answer correct)"),
    ]
    m = record.get("mastery")
    if m:
        rows.append(("Mastery", f"{concept_name(m['concept'])}: {pct(m['before'])} -> {pct(m['after'])}"))
    nd = record.get("next_difficulty")
    if nd:
        rows += [("Next difficulty", nd["band"]), ("Next difficulty reason", nd["headline"])]
    return rows


def render_why(record: dict) -> None:
    final = record["final"]
    st.markdown(f"**Predicted:** {name(final['predicted'])}")
    html(gauge(final["confidence"]))
    st.markdown("**Calibrated probabilities** (predicted label first, then competing labels):")
    html(prob_bars(final["top_predictions"], name))
    exp = record.get("explanation") or {}
    if exp.get("influential_features"):
        st.markdown("**Influential features** (TF-IDF weight × coefficient):")
        st.dataframe(pd.DataFrame(exp["influential_features"]), hide_index=True, width="stretch")
    if exp.get("occlusion") and record.get("working"):
        st.markdown("**Word importance** (drop in predicted-label probability when the word is removed):")
        html(occlusion_text(record["working"], exp["occlusion"]))
    if exp.get("similar_examples"):
        st.markdown("**Most similar training examples** (cosine similarity of answer and working embeddings):")
        st.dataframe(pd.DataFrame(exp["similar_examples"]), hide_index=True, width="stretch")
    for p in record["probes"]:
        st.markdown(
            f"**Probe reason:** `{p['probe_id']}` had the highest expected information gain "
            f"({bits(p['expected_information_gain'])}); it reduced entropy by {bits(p['information_gain'])}."
        )
    m = record.get("mastery")
    if m:
        st.markdown(
            f"**Knowledge state change:** {concept_name(m['concept'])} mastery {pct(m['before'])} → {pct(m['after'])}"
        )


def render_practice_trace(record: dict) -> None:
    with st.expander("Why did the AI make this prediction?"):
        render_why(record)
    with st.expander("AI Decision Trace"):
        html(kv_card(practice_rows(record)))


def assessment_rows(record: dict) -> list[tuple[str, str]]:
    rows = [
        ("Trace id", str(record["id"])),
        ("Misconception", name(record["misconception"])),
        ("State", f"{record['state_before']} -> {record['state_after']}"),
        ("Transfer", record["transfer"]),
        ("Trap passed", str(record["trap_passed"])),
        ("Retest passed", str(record["retest_passed"])),
        ("Resolution rule", record["resolution_rule"]),
    ]
    rows += [
        (
            f"Mastery after {u['event']} {u['ref_id']}",
            f"{concept_name(u['concept'])}: {pct(u['before'])} -> {pct(u['after'])}",
        )
        for u in record["mastery_updates"]
    ]
    return rows


def render_assessment_trace(record: dict) -> None:
    with st.expander("AI Decision Trace"):
        html(kv_card(assessment_rows(record)))
