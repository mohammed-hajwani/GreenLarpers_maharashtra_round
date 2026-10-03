const C = {bg: "#181526", ink: "#F4F2FF", muted: "#8A84A6", body: "#2A2542", edge: "#7C5CFF", force: "#3DD68C", vel: "#A78BFA", heat: "#F5B544", line: "#2E2A45"};
const cv = document.getElementById("sim");
const ctx = cv.getContext("2d");
const out = document.getElementById("readout");
const ui = document.getElementById("controls");
const W = cv.width, H = cv.height, G = 9.8;
let raf = null, last = 0, state = {};

function say(msg) { out.textContent = msg; }
function clear() { ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H); }
function line(x1, y1, x2, y2, color, w) { ctx.strokeStyle = color; ctx.lineWidth = w || 2; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }
function label(t, x, y, color, align) { ctx.fillStyle = color || C.ink; ctx.font = "15px system-ui, sans-serif"; ctx.textAlign = align || "left"; ctx.fillText(t, x, y); }
function arrow(x1, y1, x2, y2, color, text, dashed) {
  const len = Math.hypot(x2 - x1, y2 - y1); if (len < 3) return;
  ctx.setLineDash(dashed ? [7, 6] : []); line(x1, y1, x2, y2, color, 4); ctx.setLineDash([]);
  const a = Math.atan2(y2 - y1, x2 - x1); ctx.fillStyle = color; ctx.beginPath();
  ctx.moveTo(x2, y2); ctx.lineTo(x2 - 13 * Math.cos(a - 0.45), y2 - 13 * Math.sin(a - 0.45));
  ctx.lineTo(x2 - 13 * Math.cos(a + 0.45), y2 - 13 * Math.sin(a + 0.45)); ctx.closePath(); ctx.fill();
  if (text) label(text, x2 + (x2 >= x1 ? 8 : -8), y2 + (y2 > y1 ? 16 : y2 < y1 ? -6 : -8), color, x2 > x1 ? "left" : x2 < x1 ? "right" : "center");
}
function rect(x, y, w, h, t) { ctx.fillStyle = C.body; ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.beginPath(); ctx.roundRect(x, y, w, h, 8); ctx.fill(); ctx.stroke(); if (t) label(t, x + w / 2, y + h / 2 + 5, C.ink, "center"); }
function circle(x, y, r, t) { ctx.fillStyle = C.body; ctx.strokeStyle = C.edge; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill(); ctx.stroke(); if (t) label(t, x, y + 5, C.ink, "center"); }
function bar(x, base, h, color, t) { ctx.fillStyle = color; ctx.fillRect(x, base - h, 56, h); label(t, x + 28, base + 18, C.muted, "center"); }
function button(text, fn) { const b = document.createElement("button"); b.textContent = text; b.onclick = fn; ui.appendChild(b); return b; }
function slider(text, min, max, step, value, fn) {
  const wrap = document.createElement("label"); const s = document.createElement("input");
  s.type = "range"; s.min = min; s.max = max; s.step = step; s.value = value;
  const v = document.createElement("span"); v.textContent = value;
  s.oninput = () => { v.textContent = s.value; fn(parseFloat(s.value)); draw(); };
  wrap.append(text + " ", s, v); ui.appendChild(wrap); fn(parseFloat(value)); return s;
}
function select(text, options, fn) {
  const wrap = document.createElement("label"); const s = document.createElement("select");
  for (const [k, v] of options) { const o = document.createElement("option"); o.value = v; o.textContent = k; s.appendChild(o); }
  s.onchange = () => { fn(parseFloat(s.value)); draw(); }; wrap.append(text + " ", s); ui.appendChild(wrap); fn(parseFloat(options[0][1])); return s;
}
function run(step) {
  cancelAnimationFrame(raf); last = 0;
  const tick = t => { const dt = last ? Math.min((t - last) / 1000, 0.04) : 0; last = t; if (step(dt) !== false) { draw(); raf = requestAnimationFrame(tick); } else { draw(); } };
  raf = requestAnimationFrame(tick);
}
let draw = () => {};

const KINDS = {
  slide() {
    state = {x: 80, v: 0, mu: 0.2};
    slider("Friction", 0, 0.5, 0.05, 0.2, v => state.mu = v);
    button("Push once", () => { state.v = 6; run(dt => { if (state.v > 0) state.v = Math.max(0, state.v - state.mu * G * dt); state.x += state.v * 60 * dt; if (state.x > W - 40) state.x = 40; return state.v > 0; }); });
    button("Reset", () => { cancelAnimationFrame(raf); state.x = 80; state.v = 0; draw(); });
    draw = () => {
      clear(); line(20, 190, W - 20, 190, C.muted); rect(state.x - 30, 150, 60, 40);
      arrow(state.x, 150, state.x, 105, C.force, "normal"); arrow(state.x, 190, state.x, 235, C.force, "weight");
      if (state.v > 0) { arrow(state.x + 35, 140, state.x + 35 + state.v * 14, 140, C.vel, "velocity", true); if (state.mu > 0) arrow(state.x - 35, 170, state.x - 35 - state.mu * 140, 170, C.force, "friction"); }
      const forces = state.v > 0 && state.mu > 0 ? "weight, normal force, friction" : "weight and normal force (they cancel)";
      say(`Speed ${state.v.toFixed(1)} m/s. Forces acting now: ${forces}. There is no forward force after the push.`);
    };
  },
  fall() {
    state = {y1: 30, y2: 30, v1: 0, v2: 0, air: 0, t: 0, done1: null, done2: null};
    select("Air", [["off (vacuum)", 0], ["on", 1]], v => state.air = v);
    button("Drop both", () => {
      Object.assign(state, {y1: 30, y2: 30, v1: 0, v2: 0, t: 0, done1: null, done2: null});
      run(dt => { state.t += dt; for (const [k, m] of [["1", 10], ["2", 0.5]]) { if (state["done" + k] !== null) continue; const v = state["v" + k]; const drag = state.air ? 0.9 * v * v / m : 0; state["v" + k] = v + (G - drag) * dt; state["y" + k] += state["v" + k] * 12 * dt; if (state["y" + k] >= 205) { state["y" + k] = 205; state["done" + k] = state.t; } } return state.done1 === null || state.done2 === null; });
    });
    draw = () => {
      clear(); line(20, 230, W - 20, 230, C.muted); circle(200, state.y1, 24, "10 kg"); circle(400, state.y2, 12, "0.5");
      arrow(200, state.y1 + 26, 200, state.y1 + 70, C.force, "a"); arrow(400, state.y2 + 14, 400, state.y2 + 58, C.force, "a");
      const t1 = state.done1 === null ? "falling" : state.done1.toFixed(2) + " s", t2 = state.done2 === null ? "falling" : state.done2.toFixed(2) + " s";
      say(`Air ${state.air ? "on" : "off"}. Heavy ball: ${t1}. Light ball: ${t2}. ${state.air ? "Air slows the light ball more." : "With no air both speed up at g."}`);
    };
  },
  throw() {
    state = {y: 210, v: 0, moving: false, paused: false, autoPause: 1};
    select("Pause at the top", [["yes", 1], ["no", 0]], v => state.autoPause = v);
    button("Throw up", () => { Object.assign(state, {y: 210, v: 14, moving: true, paused: false}); run(dt => { const before = state.v; state.v -= G * dt; state.y -= state.v * 11 * dt; if (state.autoPause && before > 0 && state.v <= 0) { state.v = 0; state.paused = true; return false; } if (state.v < 0 && state.y >= 210) { state.y = 210; state.v = 0; state.moving = false; return false; } return true; }); });
    button("Continue", () => { if (state.paused) { state.paused = false; state.v = -0.01; run(dt => { state.v -= G * dt; state.y -= state.v * 11 * dt; if (state.y >= 210) { state.y = 210; state.v = 0; return false; } return true; }); } });
    draw = () => {
      clear(); line(20, 232, W - 20, 232, C.muted); circle(300, state.y, 18);
      if (Math.abs(state.v) > 0.05) arrow(255, state.y, 255, state.y - state.v * 6, C.vel, "velocity", true);
      arrow(345, state.y, 345, state.y + 60, C.force, "a = g (net force down)");
      const where = state.paused ? "At the top the speed is 0, but the acceleration is still 9.8 m/s² downward." : `Velocity ${state.v.toFixed(1)} m/s ${state.v >= 0 ? "up" : "down"}; acceleration 9.8 m/s² down the whole time.`;
      say(where);
    };
  },
  collide() {
    state = {m1: 2, m2: 2, x1: 250, x2: 350, v1: 0, v2: 0, push: 0};
    slider("Left cart mass (kg)", 1, 10, 1, 2, v => state.m1 = v);
    slider("Right cart mass (kg)", 1, 10, 1, 2, v => state.m2 = v);
    button("Push apart", () => { Object.assign(state, {x1: 250, x2: 350, v1: 0, v2: 0, push: 0.25}); run(dt => { const F = 40; if (state.push > 0) { state.v1 -= F / state.m1 * dt; state.v2 += F / state.m2 * dt; state.push -= dt; } state.x1 += state.v1 * 30 * dt; state.x2 += state.v2 * 30 * dt; return state.x1 > 30 && state.x2 < W - 30; }); });
    draw = () => {
      clear(); line(20, 190, W - 20, 190, C.muted);
      const w1 = 30 + state.m1 * 6, w2 = 30 + state.m2 * 6; rect(state.x1 - w1, 150, w1, 40, state.m1 + " kg"); rect(state.x2, 150, w2, 40, state.m2 + " kg");
      if (state.push > 0) { arrow(state.x1 - w1 / 2, 135, state.x1 - w1 / 2 - 60, 135, C.force, "40 N"); arrow(state.x2 + w2 / 2, 135, state.x2 + w2 / 2 + 60, 135, C.force, "40 N"); }
      say(`Each cart feels 40 N from the other: equal and opposite, on different carts. Accelerations: left ${(40 / state.m1).toFixed(1)} m/s², right ${(40 / state.m2).toFixed(1)} m/s².`);
    };
  },
  normal() {
    state = {push: 0, rope: 0, g: 9.8};
    slider("Push down (N)", 0, 60, 5, 0, v => state.push = v);
    slider("Rope pulling up (N)", 0, 40, 5, 0, v => state.rope = v);
    select("Planet", [["Earth (9.8)", 9.8], ["Moon (1.6)", 1.6], ["Mars (3.7)", 3.7]], v => state.g = v);
    draw = () => {
      clear(); line(20, 200, W - 20, 200, C.muted); rect(130, 150, 90, 50, "5 kg");
      const weight = 5 * state.g, normal = Math.max(0, weight + state.push - state.rope);
      bar(330, 200, weight * 1.8, C.force, "weight"); bar(400, 200, normal * 1.8, C.vel, "normal");
      if (state.push) arrow(175, 100, 175, 145, C.force, "push"); if (state.rope) arrow(205, 145, 205, 100, C.force, "rope");
      say(`Mass stays 5 kg. Weight = m g = ${weight.toFixed(1)} N. Normal force = ${normal.toFixed(1)} N, which only equals the weight when nothing else pushes or pulls.`);
    };
  },
  circle() {
    state = {a: 0, cut: false, x: 0, y: 0, vx: 0, vy: 0, w: 2.2};
    button("Spin", () => { Object.assign(state, {a: 0, cut: false}); run(dt => { if (!state.cut) { state.a += state.w * dt; } else { state.x += state.vx * dt; state.y += state.vy * dt; if (state.x < 0 || state.x > W || state.y < 0 || state.y > H) return false; } return true; }); });
    button("Cut the string", () => { if (state.cut) return; const r = 85, cx = 300, cy = 130; state.cut = true; state.x = cx + r * Math.cos(state.a); state.y = cy + r * Math.sin(state.a); state.vx = -r * state.w * Math.sin(state.a); state.vy = r * state.w * Math.cos(state.a); });
    draw = () => {
      clear(); const r = 85, cx = 300, cy = 130; ctx.setLineDash([5, 6]); ctx.strokeStyle = C.line; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.stroke(); ctx.setLineDash([]);
      if (!state.cut) { const x = cx + r * Math.cos(state.a), y = cy + r * Math.sin(state.a); line(cx, cy, x, y, C.muted, 1.5); circle(x, y, 13); arrow(x - (x - cx) * 0.15, y - (y - cy) * 0.15, x - (x - cx) * 0.55, y - (y - cy) * 0.55, C.force, "tension"); say("While the string holds, tension is the only sideways force. It points to the centre: that is the centripetal force."); }
      else { circle(state.x, state.y, 13); say("String cut: no force pulls it inward, so it flies off in a straight line along its velocity."); }
    };
  },
  energy() {
    state = {s: 0, v: 0, mu: 0.2, heat: 0, moving: false};
    slider("Friction", 0, 0.5, 0.05, 0.2, v => state.mu = v);
    button("Release", () => { Object.assign(state, {s: 0, v: 0, heat: 0}); run(dt => { const ang = 0.5, a = G * (Math.sin(ang) - state.mu * Math.cos(ang)); const before = state.v; state.v = Math.max(0, state.v + a * dt); const ds = (before + state.v) / 2 * dt; state.s += ds; state.heat += state.mu * G * Math.cos(ang) * ds; return state.s < 10 && (a > 0 || state.v > 0); }); });
    draw = () => {
      clear(); const total = G * Math.sin(0.5) * 10, h = G * Math.sin(0.5) * (10 - Math.min(state.s, 10));
      const ke = 0.5 * state.v * state.v, heat = Math.max(0, total - h - ke);
      line(40, 60, 260, 220, C.muted); const p = Math.min(state.s, 10) / 10; circle(40 + 220 * p, 60 + 160 * p - 14, 12);
      const k = 3.4; bar(330, 220, h * k, C.force, "height"); bar(395, 220, ke * k, C.vel, "motion"); bar(460, 220, heat * k, C.heat, "heat");
      ctx.strokeStyle = C.ink; ctx.setLineDash([4, 4]); ctx.strokeRect(325, 220 - total * k, 197, total * k); ctx.setLineDash([]);
      say(`Total energy stays ${total.toFixed(1)} J per kg. Now: height ${h.toFixed(1)}, motion ${ke.toFixed(1)}, heat ${heat.toFixed(1)}. Nothing is used up; it changes form.`);
    };
  },
};

KINDS[document.body.dataset.kind]();
draw();
