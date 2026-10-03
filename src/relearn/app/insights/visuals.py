from html import escape
from pathlib import Path

import streamlit as st

from relearn.app.student.components import inject_theme

CSS_PATH = Path(__file__).with_name("insights.css")
GAUGE = [
    (0.8, "confident", "🟢", "Confident"),
    (0.5, "ambiguous", "🟡", "Ambiguous"),
    (0.0, "uncertain", "🔴", "Uncertain"),
]


def inject_insights_theme() -> None:
    inject_theme()
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def kv_card(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<div class="ri-kv-row"><span class="ri-kv-key">{escape(k)}</span>'
        f'<span class="ri-kv-value">{escape(v)}</span></div>'
        for k, v in rows
    )
    return f'<div class="ri-card ri-kv">{body}</div>'


def gauge(confidence: float) -> str:
    _, tone, icon, label = next(g for g in GAUGE if confidence >= g[0])
    return (
        f'<span class="ri-gauge {tone}" title="{label}"><span aria-hidden="true">{icon}</span> {label} '
        f'<span class="ri-gauge-track"><span class="ri-gauge-fill" style="width:{100 * confidence:.1f}%"></span>'
        f"</span> {100 * confidence:.1f}%</span>"
    )


def prob_bars(top: list, name) -> str:
    rows = ""
    for i, (label, p) in enumerate(top):
        width = min(max(float(p), 0.0), 1.0) * 100
        lead = " lead" if i == 0 else ""
        rows += (
            f'<div class="ri-bar-row{lead}" role="listitem"><span class="ri-bar-label">{escape(name(label))}</span>'
            f'<span class="ri-bar-track"><span class="ri-bar-fill" style="width:{width:.1f}%"></span></span>'
            f'<span class="ri-bar-value">{width:.1f}%</span></div>'
        )
    return f'<div class="ri-bars" role="list">{rows}</div>'


def occlusion_text(working: str, drops: list[dict]) -> str:
    weights = {d["word"].lower(): float(d["probability_drop"]) for d in drops}
    top = max((abs(v) for v in weights.values()), default=0.0) or 1.0
    out = []
    for token in working.split():
        key = token.strip(".,;:!?\"'()").lower()
        if key in weights:
            w = weights[key]
            tone = "for" if w >= 0 else "against"
            alpha = 0.25 + 0.6 * abs(w) / top
            out.append(
                f'<mark class="ri-occ {tone}" style="--a:{alpha:.2f}" title="probability drop {w:+.4f}">'
                f"{escape(token)}</mark>"
            )
        else:
            out.append(escape(token))
    legend = (
        '<p class="ri-occ-legend"><mark class="ri-occ for" style="--a:0.7">supports the prediction</mark> '
        '<mark class="ri-occ against" style="--a:0.7">works against it</mark> · stronger colour = bigger effect '
        "when the word is removed</p>"
    )
    return f'<div class="ri-card"><p class="ri-occ-text">{" ".join(out)}</p>{legend}</div>'
