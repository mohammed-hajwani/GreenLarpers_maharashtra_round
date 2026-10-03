from html import escape

from relearn.content import load_content

INK, MUTED, LINE, SURF = "#F4F2FF", "#B9B3D1", "#2E2A45", "#211D33"
STATUS = {
    "not_started": ("#8A84A6", "○", "Not started"),
    "in_progress": ("#A78BFA", "◐", "In progress"),
    "mastered": ("#3DD68C", "✓", "Mastered"),
    "review": ("#F5B544", "↺", "Come back to this"),
}
POSITIONS = {
    "kinematics": (110, 70),
    "free_fall": (110, 190),
    "force_motion": (330, 70),
    "third_law": (330, 190),
    "weight_normal": (550, 70),
    "circular": (550, 190),
    "energy": (770, 130),
}
EDGES = [
    ("kinematics", "free_fall"),
    ("kinematics", "force_motion"),
    ("force_motion", "third_law"),
    ("force_motion", "weight_normal"),
    ("weight_normal", "circular"),
    ("circular", "energy"),
    ("weight_normal", "energy"),
]


def _t(
    x: float, y: float, s: str, color: str = INK, size: float = 14, weight: int = 400, anchor: str = "middle"
) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'font-family="Source Sans Pro, system-ui, sans-serif">{escape(s)}</text>'
    )


def concept_map_svg(statuses: dict[str, str]) -> str:
    content = load_content()
    edges = "".join(
        f'<line x1="{POSITIONS[a][0]}" y1="{POSITIONS[a][1]}" x2="{POSITIONS[b][0]}" y2="{POSITIONS[b][1]}" '
        f'stroke="{LINE}" stroke-width="3"/>'
        for a, b in EDGES
    )
    nodes = ""
    summary = []
    for cid, (x, y) in POSITIONS.items():
        color, icon, label = STATUS[statuses.get(cid, "not_started")]
        name = content.concepts[cid].name
        summary.append(f"{name}: {label}")
        nodes += (
            f'<rect x="{x - 95}" y="{y - 34}" width="190" height="68" rx="16" fill="{SURF}" stroke="{color}" '
            f'stroke-width="2.5"/>'
            + _t(x, y - 6, name, size=14.5, weight=700)
            + _t(x, y + 18, f"{icon} {label}", color, size=13)
        )
    desc = escape("; ".join(summary))
    return (
        '<svg viewBox="0 0 880 260" width="100%" role="img" aria-labelledby="cm-t cm-d" '
        'xmlns="http://www.w3.org/2000/svg"><title id="cm-t">Your learning journey</title>'
        f'<desc id="cm-d">{desc}</desc>{edges}{nodes}</svg>'
    )


def cy_label(y: float) -> float:
    return y + 52


def concept_map_list(statuses: dict[str, str]) -> str:
    content = load_content()
    rows = ""
    for cid in POSITIONS:
        color, icon, label = STATUS[statuses.get(cid, "not_started")]
        rows += (
            f'<li><span class="rl-map-name">{escape(content.concepts[cid].name)}</span>'
            f'<span class="rl-map-status" style="color:{color}">{icon} {escape(label)}</span></li>'
        )
    return f'<ul class="rl-map-list">{rows}</ul>'


def class_map_svg(rows: dict[str, dict]) -> str:
    content = load_content()
    groups = list(POSITIONS)
    cols = 3
    width, height = 1000, 760
    cell_w, cell_h = width / cols, 245
    centers: dict[str, tuple[float, float]] = {}
    body = ""
    for i, cid in enumerate(groups):
        cx, cy = (i % cols) * cell_w + 12, (i // cols) * cell_h + 12
        body += (
            f'<rect x="{cx}" y="{cy}" width="{cell_w - 24}" height="{cell_h - 24}" rx="18" fill="#181526" '
            f'stroke="{LINE}" stroke-width="1.5"/>'
            + _t(cx + 16, cy + 26, content.concepts[cid].name, MUTED, 14, 700, "start")
        )
        members = content.concepts[cid].misconceptions
        for j, m in enumerate(members):
            x = cx + (cell_w - 24) * (j + 1) / (len(members) + 1)
            y = cy + 105
            centers[m] = (x, y)
    for members in content.confusable_groups.values():
        for a, b in zip(members, members[1:], strict=False):
            (x1, y1), (x2, y2) = centers[a], centers[b]
            body += (
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#7C5CFF" stroke-width="2" '
                'stroke-dasharray="6 6"/>'
            )
    top = max([r["held"] for r in rows.values()] + [1])
    for m, (x, y) in centers.items():
        r = rows.get(m, {"held": 0, "resolved": 0, "best_modality": None})
        radius = 16 + 14 * (r["held"] / top)
        share = r["resolved"] / r["held"] if r["held"] else 0
        body += f'<circle cx="{x}" cy="{y}" r="{radius}" fill="#2A2542" stroke="#A78BFA" stroke-width="2"/>'
        if share:
            body += f'<circle cx="{x}" cy="{y}" r="{radius * share**0.5}" fill="#3DD68C" opacity="0.85"/>'
        body += _t(x, y + 5, m, INK, 13, 700)
        body += _t(x, cy_label(y), f"{r['held']} held", MUTED, 12)
        body += _t(x, cy_label(y) + 16, f"{r['resolved']} resolved", "#3DD68C" if r["resolved"] else MUTED, 12)
        if r.get("best_modality"):
            body += _t(x, cy_label(y) + 32, f"best: {r['best_modality']}", "#F5B544", 11.5)
    legend = _t(
        16,
        height - 10,
        "bubble size = learners who showed it · green core = share resolved · dashed = look-alike pair",
        MUTED,
        12.5,
        anchor="start",
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Class misconception map" '
        f'xmlns="http://www.w3.org/2000/svg">{body}{legend}</svg>'
    )
