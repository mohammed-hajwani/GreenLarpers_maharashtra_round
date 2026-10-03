from functools import lru_cache
from html import escape

import yaml

from relearn.config import ROOT

W, H = 460, 300
FORCE = "#3DD68C"
VEL = "#A78BFA"
WRONG = "#FF6B7A"
INK = "#F4F2FF"
MUTED = "#8A84A6"
BODY = "#2A2542"
EDGE = "#7C5CFF"
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


@lru_cache(maxsize=1)
def load_visuals() -> dict:
    with (ROOT / "content" / "visuals.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)["visuals"]


def _defs() -> str:
    heads = "".join(
        f'<marker id="h-{name}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        for name, color in (("f", FORCE), ("v", VEL), ("w", WRONG))
    )
    return f"<defs>{heads}</defs>"


def arrow(
    x1: float, y1: float, x2: float, y2: float, kind: str, label: str = "", crossed: bool = False, at: str = "tip"
) -> str:
    color = {"f": FORCE, "v": VEL, "w": WRONG}[kind]
    dash = ' stroke-dasharray="6 5"' if kind in ("v", "w") else ""
    out = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3.5"{dash} '
        f'marker-end="url(#h-{kind})"/>'
    )
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if crossed:
        out += _cross(mx, my)
    if not label:
        return out
    if at == "above":
        return out + text(mx, min(y1, y2) - 10, label, color, size=12.5)
    if at == "below":
        return out + text(mx, max(y1, y2) + 20, label, color, size=12.5)
    if at == "left":
        return out + text(min(x1, x2) - 8, my + 4, label, color, anchor="end", size=12.5)
    if at == "right":
        return out + text(max(x1, x2) + 8, my + 4, label, color, anchor="start", size=12.5)
    lx = x2 + (10 if x2 > x1 else -10 if x2 < x1 else 0)
    ly = y2 + (18 if y2 > y1 else -10 if y2 < y1 else 4)
    anchor = "start" if x2 > x1 else "end" if x2 < x1 else "middle"
    return out + text(lx, ly, label, color, anchor=anchor, size=12.5)


def text(x: float, y: float, value: str, color: str = INK, anchor: str = "middle", size: float = 13) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" text-anchor="{anchor}" '
        f'font-family="Source Sans Pro, system-ui, sans-serif">{escape(value)}</text>'
    )


def box(x: float, y: float, w: float, h: float, label: str = "") -> str:
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{BODY}" stroke="{EDGE}" stroke-width="2"/>'
    return out + (text(x + w / 2, y + h / 2 + 5, label, size=12) if label else "")


def ball(x: float, y: float, r: float = 16, label: str = "") -> str:
    out = f'<circle cx="{x}" cy="{y}" r="{r}" fill="{BODY}" stroke="{EDGE}" stroke-width="2"/>'
    return out + (text(x, y + 4, label, size=11) if label else "")


def ground(y: float, x1: float = 30, x2: float = W - 30) -> str:
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{MUTED}" stroke-width="2"/>'


def note(label: str) -> str:
    return text(24, 262, f"✗ not a real force: {label}", WRONG, anchor="start", size=12.5)


def _forces(cx: float, cy: float, spec: dict, length: float = 55) -> str:
    out = ""
    for f in spec.get("forces", []):
        dx, dy = DIRS[f["dir"]]
        side = "right" if dy else "above"
        out += arrow(
            cx + dx * 22, cy + dy * 22, cx + dx * (22 + length), cy + dy * (22 + length), "f", f["label"], at=side
        )
    v = spec.get("velocity")
    if v in DIRS:
        dx, dy = DIRS[v]
        sx, sy = (cx + 70, cy - 58) if dx else (cx - 34, cy - 10)
        out += arrow(sx, sy, sx + dx * 70, sy + dy * 70, "v", "velocity", at="above" if dx else "left")
    t = spec.get("tempting")
    if t and t.get("dir") in DIRS:
        dx, dy = DIRS[t["dir"]]
        sx, sy = (cx + 40, cy + 8) if dx else (cx + 34, cy - 10)
        out += arrow(sx, sy, sx + dx * 66, sy + dy * 66, "w", crossed=True) + note(t["label"])
    return out


def _cross(x: float, y: float) -> str:
    return (
        f'<line x1="{x - 8}" y1="{y - 8}" x2="{x + 8}" y2="{y + 8}" stroke="{WRONG}" stroke-width="3"/>'
        f'<line x1="{x - 8}" y1="{y + 8}" x2="{x + 8}" y2="{y - 8}" stroke="{WRONG}" stroke-width="3"/>'
    )


def scene_block(spec: dict) -> str:
    return ground(150) + box(175, 110, 70, 40) + _forces(210, 130, spec)


def scene_ball_air(spec: dict) -> str:
    return ball(230, 125) + _forces(230, 125, spec)


def scene_ball_top(spec: dict) -> str:
    out = '<path d="M70 240 Q 230 -20 390 240" fill="none" stroke="#2E2A45" stroke-width="2" stroke-dasharray="4 6"/>'
    out += ball(230, 100) + text(230, 68, "speed = 0 for an instant", VEL, size=12.5)
    out += arrow(230, 120, 230, 185, "f", "a = g, still", at="right")
    return out + _cross(30, 258) + text(46, 262, "not real: a = 0 at the top", WRONG, anchor="start", size=12.5)


def scene_drop_two(spec: dict) -> str:
    out = ground(225) + ball(150, 60, 24, "10 kg") + ball(310, 60, 12, "1 kg")
    out += arrow(150, 90, 150, 160, "f", "a = g", at="right") + arrow(310, 78, 310, 160, "f", "a = g", at="right")
    out += text(230, 205, "same acceleration, so they land together", INK, size=12.5)
    return out + note("extra speed for the heavy ball")


def scene_two_cars(spec: dict) -> str:
    out = ground(100) + box(40, 65, 80, 35, "Car A") + arrow(130, 82, 260, 82, "v", "fast, steady", at="above")
    out += text(300, 87, "a = 0", FORCE, anchor="start", size=13)
    out += ground(195) + box(40, 160, 80, 35, "Car B") + arrow(130, 168, 165, 168, "v", "slow", at="right")
    return out + arrow(130, 186, 220, 186, "f", "speeding up: a > 0", at="right")


def scene_pair(spec: dict) -> str:
    left, right = spec.get("left", "A"), spec.get("right", "B")
    out = ground(175) + box(30, 120, 110, 55, left) + box(330, 130, 80, 45, right)
    out += arrow(322, 140, 150, 140, "f", f"{right} pushes {left}", at="above")
    out += arrow(150, 162, 322, 162, "f", f"{left} pushes {right}", at="below")
    return out + text(230, 228, "equal size, opposite directions, on different objects", INK, size=12.5)


def scene_incline(spec: dict) -> str:
    out = '<polygon points="40,230 420,230 420,70" fill="none" stroke="#8A84A6" stroke-width="2"/>'
    out += '<g transform="rotate(-22.8 270 160)">' + box(240, 132, 60, 36) + "</g>"
    out += arrow(270, 160, 270, 228, "f", "weight", at="right")
    out += arrow(262, 140, 238, 83, "f", "normal (smaller)", at="left")
    out += arrow(300, 140, 300, 60, "w", crossed=True)
    return out + note("normal force = weight")


def scene_mass_weight(spec: dict) -> str:
    out = (
        ground(150)
        + box(170, 100, 110, 50, "mass 5 kg")
        + arrow(225, 150, 225, 215, "f", "weight = m g = 49 N", at="right")
    )
    return out + arrow(290, 125, 360, 125, "w", crossed=True) + note("a weight of 5 kg")


def scene_circle(spec: dict) -> str:
    out = '<circle cx="200" cy="130" r="88" fill="none" stroke="#2E2A45" stroke-width="2" stroke-dasharray="5 6"/>'
    out += ball(200, 130, 5) + f'<line x1="200" y1="130" x2="288" y2="130" stroke="{MUTED}" stroke-width="1.5"/>'
    out += ball(288, 130, 13) + arrow(272, 130, 222, 130, "f", "tension", at="above")
    out += arrow(288, 114, 288, 50, "v", "velocity", at="right")
    return out + arrow(304, 146, 350, 192, "w", crossed=True) + note("an extra centripetal force")


def scene_energy(spec: dict) -> str:
    out = text(230, 34, "same total height: energy changes form, it never vanishes", INK, size=12.5)
    for i, (label, motion, heat) in enumerate((("start", 90, 0), ("end", 40, 50))):
        x, y = 110 + i * 150, 225
        out += text(x + 50, y + 18, label, MUTED, size=12)
        for value, color, name in ((motion, VEL, "motion"), (heat, FORCE, "heat")):
            if value:
                top = y - value * 1.7
                out += (
                    f'<rect x="{x}" y="{top}" width="100" height="{value * 1.7}" rx="4" fill="{color}" opacity="0.9"/>'
                )
                out += text(x + 50, top + value * 0.85 + 4, name, "#0F0D1A", size=12)
                y = top
    return out


SCENES = {
    "block": scene_block,
    "ball_air": scene_ball_air,
    "ball_top": scene_ball_top,
    "drop_two": scene_drop_two,
    "two_cars": scene_two_cars,
    "pair": scene_pair,
    "incline": scene_incline,
    "mass_weight": scene_mass_weight,
    "circle": scene_circle,
    "energy": scene_energy,
}


def legend() -> str:
    return (
        text(24, 288, "green = real force", FORCE, anchor="start", size=11.5)
        + text(170, 288, "dashed purple = motion", VEL, anchor="start", size=11.5)
        + text(330, 288, "red ✗ = not real", WRONG, anchor="start", size=11.5)
    )


def diagram_svg(misconception: str) -> str | None:
    spec = load_visuals().get(misconception, {}).get("diagram")
    if not spec:
        return None
    body = SCENES[spec["scene"]](spec)
    title, desc = escape(spec["title"]), escape(spec["caption"])
    return (
        f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="d-{misconception}-t d-{misconception}-d" '
        f'xmlns="http://www.w3.org/2000/svg"><title id="d-{misconception}-t">{title}</title>'
        f'<desc id="d-{misconception}-d">{desc}</desc>{_defs()}{body}{legend()}</svg>'
    )


def diagram_caption(misconception: str) -> tuple[str, str]:
    spec = load_visuals()[misconception]["diagram"]
    return spec["title"], spec["caption"]
