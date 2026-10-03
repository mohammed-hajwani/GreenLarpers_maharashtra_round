const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.APPLY_THEME);

const ROOT = path.resolve(__dirname, "..");
const ASSETS = path.join(ROOT, "docs", "deck", "assets", "crops");
const OUT = path.join(ROOT, "docs", "deck", "ReLearn_pitch.pptx");
const M = JSON.parse(fs.readFileSync(path.join(ROOT, "reports", "metrics.json"), "utf-8"));

const THEME = {
  name: "Re:Learn Dark",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "F4F2FF", lt1: "0F0D1A", dk2: "B9B3D1", lt2: "211D33",
    accent1: "7C5CFF", accent2: "A78BFA", accent3: "3DD68C", accent4: "F5B544", accent5: "FF6B7A", accent6: "8A84A6",
    hlink: "A78BFA", folHlink: "A78BFA",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "Re:Learn";
pres.author = "Team GreenLarpers";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const f2 = v => v.toFixed(2);
const pct = v => `${(100 * v).toFixed(1)}%`;
const imgSize = file => {
  const buf = fs.readFileSync(file);
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
};

pres.defineSlideMaster({
  title: "TITLE",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 2.0, w: 6.2, h: 1.3, fontSize: 60, bold: true, color: C.text1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.9, fontSize: 30, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "Re:Learn · Team GreenLarpers", options: { x: 0.6, y: 7.0, w: 6, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, align: "right" },
});

function card(slide, x, y, w, h, name, fill) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill || C.background2 }, line: { color: C.background2, width: 0.75 },
    objectName: name,
  });
}

function text(slide, value, opts) {
  slide.addText(value, { isTextBox: true, margin: 0, color: C.text1, fontSize: 15, valign: "top", ...opts });
}

function badge(slide, x, y, label, color, name) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.55, h: 0.55, fill: { color }, line: { color }, objectName: name });
  text(slide, label, { x, y, w: 0.55, h: 0.55, align: "center", valign: "middle", bold: true, fontSize: 16, color: C.background1 });
}

function picture(slide, file, x, y, maxW, maxH, name) {
  const size = imgSize(path.join(ASSETS, file));
  const scale = Math.min(maxW / size.w, maxH / size.h);
  const w = size.w * scale, h = size.h * scale;
  const px = x + (maxW - w) / 2, py = y + (maxH - h) / 2;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: px - 0.05, y: py - 0.05, w: w + 0.1, h: h + 0.1, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: C.accent1, width: 1 }, objectName: `${name} frame` });
  slide.addImage({ path: path.join(ASSETS, file), x: px, y: py, w, h, altText: name, objectName: name });
}

function chartStyle(title) {
  return {
    showTitle: true, title, titleColor: HEX.dk1, titleFontSize: 14, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.dk1, dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.accent6, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "2E2A45", size: 0.75 }, catGridLine: { style: "none" },
    legendColor: HEX.dk2, legendFontSize: 12, legendFontFace: "+mn-lt",
    catAxisLineColor: "2E2A45", valAxisLineShow: false,
  };
}

const comp = (model, set) => M.comparison.find(r => r.model === model && r.eval_set === set && r.mode === "model_only").macro_f1;
const compKey = (model, set) => M.comparison.find(r => r.model === model && r.eval_set === set && r.mode === "with_answer_key").macro_f1;

pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Opening" });
s.addText("Re:Learn", { placeholder: "title" });
text(s, "TEAM GREENLARPERS · PHYSICS: MECHANICS", { x: 0.6, y: 1.4, w: 6.2, h: 0.4, fontSize: 14, bold: true, color: C.accent2, charSpacing: 2 });
text(s, "Find the wrong idea, not just the wrong answer.", { x: 0.6, y: 3.45, w: 6.2, h: 1.0, fontSize: 26, color: C.text2 });
text(s, "An adaptive, multimodal learning system that diagnoses the misconception behind a student's answer, teaches against that idea, and only calls it fixed when the evidence says so.", { x: 0.6, y: 4.55, w: 6.0, h: 1.4, fontSize: 16, color: C.text2 });
["Diagnose", "Teach (see · try · explain)", "Verify"].forEach((label, i) => {
  const x = [0.6, 2.05, 5.25][i], w = [1.3, 3.05, 1.0][i];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 6.1, w, h: 0.45, rectRadius: 0.2, fill: { color: C.accent1, transparency: 55 }, line: { color: C.accent1 }, objectName: `chip ${label}` });
  text(s, label, { x, y: 6.1, w, h: 0.45, align: "center", valign: "middle", fontSize: 13, bold: true });
});
picture(s, "landing.png", 7.2, 0.6, 5.5, 6.3, "Student landing page screenshot");
s.addNotes("Most learning tools mark an answer right or wrong. Re:Learn asks why it was wrong: which specific misconception produced it. Then it teaches against that idea, in several modes, and only counts it as fixed after transfer questions, a trap question and a delayed retest.");

pres.addSection({ title: "Problem and solution" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and solution" });
s.addText("One wrong answer can hide three different wrong ideas", { placeholder: "title" });
card(s, 0.6, 1.6, 4.6, 4.6, "question card");
text(s, "THE QUESTION", { x: 0.9, y: 1.85, w: 4.0, h: 0.3, fontSize: 12, bold: true, color: C.accent2 });
text(s, "A 0.5 kg puck slides across frictionless ice at a constant 8 m/s. What is the net force on it?", { x: 0.9, y: 2.25, w: 4.0, h: 1.5, fontSize: 20, bold: true });
text(s, "Three students all answer", { x: 0.9, y: 3.95, w: 4.0, h: 0.35, fontSize: 14, color: C.text2 });
text(s, "4.0 N forward", { x: 0.9, y: 4.35, w: 4.0, h: 0.8, fontSize: 40, bold: true, color: C.accent5 });
text(s, "Correct answer: 0 N", { x: 0.9, y: 5.35, w: 4.0, h: 0.4, fontSize: 16, color: C.accent3 });
const reasons = [
  ["M01", "\"Something has to keep pushing it, or it would stop.\"", "A force is needed to keep moving"],
  ["M09", "\"The hit put a force into the puck that it still carries.\"", "Impetus: the force is stored inside"],
  ["M12", "\"It moves forward, so the net force points forward.\"", "Net force always follows the motion"],
];
reasons.forEach(([code, quote, idea], i) => {
  const y = 1.6 + i * 1.55;
  card(s, 5.6, y, 7.1, 1.35, `reason ${code}`);
  badge(s, 5.85, y + 0.4, String(i + 1), C.accent2, `badge ${code}`);
  text(s, quote, { x: 6.6, y: y + 0.2, w: 5.9, h: 0.55, fontSize: 16, italic: true });
  text(s, `${code} · ${idea}`, { x: 6.6, y: y + 0.8, w: 5.9, h: 0.4, fontSize: 13, color: C.accent2, bold: true });
});
text(s, "Marking it wrong fixes none of them. Showing the right answer doesn't either: each student needs a different explanation.", { x: 0.6, y: 6.4, w: 12.1, h: 0.45, fontSize: 15, color: C.text2 });
s.addNotes("This is the core problem from the brief. These three misconceptions produce the identical wrong answer. A plain right or wrong check cannot tell them apart, and a generic explanation will miss two of the three students. They are one of our four look-alike groups.");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and solution" });
s.addText("Re:Learn closes the loop from mistake to verified understanding", { placeholder: "title" });
const steps = [
  ["Diagnose", "A classifier reads the question, answer and reasoning, and names one of 12 misconceptions with a calibrated confidence."],
  ["Quick check", "If two look-alike ideas are close, ask the one question that best separates them (highest expected information gain)."],
  ["Teach", "Targeted hint in the mode most likely to work for this idea: explanation, force diagram or interactive simulation."],
  ["Reassess", "New transfer questions plus a trap question built to catch the old idea. One right answer is never enough."],
  ["Lock in", "Delayed retest a few questions later, and the student explains the idea back in their own words."],
];
steps.forEach(([head, body], i) => {
  const x = 0.6 + i * 2.5;
  card(s, x, 1.7, 2.25, 3.7, `step ${head}`);
  badge(s, x + 0.2, 1.95, String(i + 1), C.accent1, `step badge ${i + 1}`);
  text(s, head, { x: x + 0.2, y: 2.65, w: 1.9, h: 0.45, fontSize: 20, bold: true });
  text(s, body, { x: x + 0.2, y: 3.15, w: 1.9, h: 2.2, fontSize: 13, color: C.text2 });
  if (i < steps.length - 1) {
    s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.27, y: 3.4, w: 0.2, h: 0.3, fill: { color: C.accent2 }, line: { color: C.accent2 }, objectName: `arrow ${i}` });
  }
});
card(s, 0.6, 5.65, 12.1, 1.1, "learner model band");
text(s, [
  { text: "Learner model underneath every step: ", options: { bold: true, color: C.accent3 } },
  { text: "per-concept mastery (Bayesian), per-misconception state (active → intervened → resolved → relapsed), and a decision trace for every interaction.", options: { color: C.text1 } },
], { x: 0.9, y: 5.8, w: 11.6, h: 0.8, fontSize: 15, valign: "middle" });
s.addNotes("This is the whole system on one slide. Each step maps to a requirement in the brief: diagnosis, differentiation, adaptive intervention, resolution assessment, learner model. The quick check and the teaching mode are chosen by algorithms, not fixed rules.");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem and solution" });
s.addText("What a student sees: see it, try it, explain it", { placeholder: "title" });
[["hint.png", "A wrong answer gets a short targeted hint, here with a force diagram that crosses out the force that isn't real"],
 ["simulation_m01.png", "Or an interactive simulation: set friction to zero and watch the puck keep going with no forward force"],
 ["explain_back.png", "Once the idea is locked in, the student explains it in their own words and the model checks it"]].forEach(([file, cap], i) => {
  const x = 0.6 + i * 4.1;
  picture(s, file, x, 1.55, 3.85, 4.3, `screenshot ${file}`);
  text(s, cap, { x, y: 6.0, w: 3.85, h: 0.85, fontSize: 13, color: C.text2 });
});
s.addNotes("These are real screenshots from the running app. No probabilities or misconception codes are shown to students; that information lives in a separate Insights view for teachers and judges.");

pres.addSection({ title: "System" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "System" });
s.addText("Architecture: an ML pipeline behind a learning-first interface", { placeholder: "title" });
const arch = [
  ["Content", "12 misconceptions · 7 concepts · 48 templates · 66 items · 12 visual specs"],
  ["Data", "Template generator → clean → dedupe → split by template"],
  ["Models", "TF-IDF baseline · MiniLM + TF-IDF hybrid · temperature calibration"],
  ["Diagnosis", "Routing by confidence · information-gain probes · novelty flag"],
  ["Teaching", "Strategies × modality (text, diagram, simulation) via Thompson sampling · retrieval grounding"],
  ["Assessment", "Transfer + trap · delayed retest · explain-it-back"],
  ["Learner model", "Beta mastery per concept · misconception state machine · SQLite store"],
];
arch.forEach(([head, body], i) => {
  const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
  const x = 0.6 + col * 6.2, y = 1.6 + row * 1.3;
  card(s, x, y, 5.9, 1.1, `arch ${head}`);
  text(s, head, { x: x + 0.25, y: y + 0.15, w: 5.4, h: 0.35, fontSize: 17, bold: true, color: C.accent2 });
  text(s, body, { x: x + 0.25, y: y + 0.52, w: 5.4, h: 0.5, fontSize: 13, color: C.text2 });
});
card(s, 6.8, 5.5, 5.9, 1.1, "interfaces", C.accent1);
text(s, "Two views", { x: 7.05, y: 5.65, w: 5.4, h: 0.35, fontSize: 17, bold: true });
text(s, "Student view with no AI jargon · Insights view for teachers and judges", { x: 7.05, y: 6.07, w: 5.4, h: 0.5, fontSize: 13 });
s.addNotes("Everything runs on a free CPU with no API key. A Claude rewrite of the hint is optional when a key is present; the classifier, never the LLM, decides the misconception. 167 automated tests cover the pipeline.");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "System" });
s.addText("Evaluation built to test generalisation, not memory", { placeholder: "title" });
const ds = M.dataset;
const stats = [
  [ds.total.toLocaleString("en-US"), "synthetic answers with reasoning, 13 classes (12 misconceptions + correct)"],
  [`${ds.split_sizes.test}`, "test answers from question templates never seen in training"],
  [`${ds.handwritten_test_size}`, "hand-written answers in different phrasing, scored separately"],
  ["12", "leave-one-misconception-out retrains, to test truly unseen mistakes"],
];
stats.forEach(([big, label], i) => {
  const x = 0.6 + i * 3.1;
  card(s, x, 1.7, 2.85, 2.9, `stat ${i}`);
  text(s, big, { x: x + 0.25, y: 1.95, w: 2.4, h: 1.0, fontSize: 48, bold: true, color: C.accent2 });
  text(s, label, { x: x + 0.25, y: 3.05, w: 2.4, h: 1.4, fontSize: 14, color: C.text2 });
});
card(s, 0.6, 4.95, 12.1, 1.75, "provenance");
text(s, [
  { text: "Honest about provenance. ", options: { bold: true, color: C.accent4 } },
  { text: "All training data is synthetic, generated from 48 hand-written templates whose wrong answers and reasoning encode each misconception. Splits are by template, so test questions have new scenarios and numbers. The hand-written answers and explanations were written by the team, not collected from students.", options: { color: C.text1 } },
], { x: 0.9, y: 5.1, w: 11.6, h: 1.45, fontSize: 15, valign: "middle" });
s.addNotes("The brief asks for evaluation on responses and misconceptions not seen during training. We test both: unseen question templates and phrasing, and unseen misconceptions via leave-one-out.");

pres.addSection({ title: "Results" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Diagnosis: the embedding model handles new phrasing better", { placeholder: "title" });
s.addChart(pres.ChartType.bar, [
  { name: "TF-IDF baseline", labels: ["Unseen templates (synthetic)", "Hand-written answers"], values: [comp("baseline", "test"), comp("baseline", "handwritten")] },
  { name: "MiniLM hybrid (v1)", labels: ["Unseen templates (synthetic)", "Hand-written answers"], values: [comp("v1_embedding", "test"), comp("v1_embedding", "handwritten")] },
], { x: 0.6, y: 1.5, w: 7.3, h: 5.2, barDir: "col", barGapWidthPct: 60, chartColors: [HEX.accent6, HEX.accent1], valAxisMinVal: 0, valAxisMaxVal: 1, dataLabelFormatCode: "0.00", showLegend: true, legendPos: "b", ...chartStyle("Macro-F1, model only (13 classes)") });
card(s, 8.3, 1.6, 4.4, 5.0, "results commentary");
text(s, [
  { text: f2(comp("v1_embedding", "handwritten")), options: { fontSize: 44, bold: true, color: C.accent2, breakLine: true } },
  { text: "macro-F1 on hand-written answers (v1), vs " + f2(comp("baseline", "handwritten")) + " for the baseline", options: { fontSize: 14, color: C.text2, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "Using the question's answer key as well: " + f2(compKey("v1_embedding", "handwritten")) + " (v1) and " + f2(compKey("baseline", "test")) + " (baseline, unseen templates).", options: { fontSize: 14, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "v1 was chosen on validation. It is weaker on the synthetic test split, and we report that rather than hide it.", options: { fontSize: 14, color: C.accent4 } },
], { x: 8.55, y: 1.85, w: 3.9, h: 4.6 });
s.addNotes("Hand-written answers are the closer proxy for real students because they use different wording from the templates. The hybrid model combines MiniLM sentence embeddings of the answer and the reasoning with TF-IDF features. Pure embeddings scored 0.53 macro-F1 on validation; the hybrid scored 0.65.");

const pr = M.probing.results.v1_embedding;
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Telling look-alikes apart: one well-chosen quick check", { placeholder: "title" });
s.addChart(pres.ChartType.bar, [
  { name: "Validation", labels: ["No quick check", "Random quick check", "Information-gain quick check"], values: [pr.val.no_probe.accuracy_mean, pr.val.random_probe.accuracy_mean, pr.val.information_gain_probe.accuracy_mean] },
  { name: "Test", labels: ["No quick check", "Random quick check", "Information-gain quick check"], values: [pr.test.no_probe.accuracy_mean, pr.test.random_probe.accuracy_mean, pr.test.information_gain_probe.accuracy_mean] },
], { x: 0.6, y: 1.5, w: 7.3, h: 5.2, barDir: "col", barGapWidthPct: 60, chartColors: [HEX.accent6, HEX.accent1], valAxisMinVal: 0, valAxisMaxVal: 1, dataLabelFormatCode: "0.00", showLegend: true, legendPos: "b", ...chartStyle("Accuracy on look-alike misconceptions (v1, 5 seeds)") });
card(s, 8.3, 1.6, 4.4, 5.0, "probing commentary");
const lift = 100 * (pr.test.information_gain_probe.accuracy_mean - pr.test.no_probe.accuracy_mean);
text(s, [
  { text: `+${lift.toFixed(0)} pts`, options: { fontSize: 44, bold: true, color: C.accent3, breakLine: true } },
  { text: "accuracy on look-alike misconceptions (test) after quick checks", options: { fontSize: 14, color: C.text2, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "Each candidate question is scored by its expected drop in uncertainty (entropy) over the full diagnosis; the best one is asked, at most two per answer.", options: { fontSize: 14, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "Measured with simulated learners who answer as their misconception predicts, so these are upper bounds.", options: { fontSize: 14, color: C.accent4 } },
], { x: 8.55, y: 1.85, w: 3.9, h: 4.6 });
s.addNotes("Information gain beats a random relevant probe in all four settings we tested. The student just sees a short 'Quick check' question; the uncertainty maths stays in Insights.");

const os = M.open_set, osSel = os.scores[os.selected_score];
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Unseen misconceptions: distinct ones get flagged", { placeholder: "title" });
const ids = Object.keys(os.per_misconception);
s.addChart(pres.ChartType.bar, [
  { name: "AUROC", labels: ids, values: ids.map(k => os.per_misconception[k].test_auroc || 0) },
], { x: 0.6, y: 1.5, w: 8.0, h: 5.2, barDir: "col", barGapWidthPct: 40, chartColors: [HEX.accent2], valAxisMinVal: 0, valAxisMaxVal: 1.08, valAxisMajorUnit: 0.25, dataLabelFormatCode: "0.00", dataLabelFontSize: 10, showLegend: false, ...chartStyle("Test AUROC for each misconception when left out of training") });
card(s, 8.95, 1.6, 3.75, 5.0, "open set commentary");
text(s, [
  { text: f2(osSel.test_auroc), options: { fontSize: 44, bold: true, color: C.accent2, breakLine: true } },
  { text: `overall test AUROC; flags ${pct(osSel.test_detection_rate)} of unseen-misconception answers at a ${pct(osSel.test_false_flag_rate)} false-flag rate`, options: { fontSize: 13, color: C.text2, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "An unseen idea that resembles a known one is mistaken for it: M03 is read as M04, and M06 as M07.", options: { fontSize: 13, breakLine: true } },
  { text: " ", options: { fontSize: 8, breakLine: true } },
  { text: "So unfamiliar mistakes go to a teacher review queue, never to the student.", options: { fontSize: 13, color: C.accent3 } },
], { x: 9.2, y: 1.85, w: 3.3, h: 4.6 });
s.addNotes("We retrained the model twelve times, each time without one misconception, and asked whether it could say 'this is unfamiliar'. Clearly distinct misconceptions score 0.90 to 1.00. Look-alike pairs are the honest failure case, which is exactly why our quick checks exist.");

const ms = M.modality_simulation.results;
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Multimodal teaching that learns which mode works", { placeholder: "title" });
picture(s, "diagram_m01.png", 0.6, 1.5, 4.4, 2.7, "Force diagram for M01");
picture(s, "simulation_m01.png", 0.6, 4.35, 4.4, 2.45, "Puck simulation for M01");
s.addChart(pres.ChartType.bar, [
  { name: "First-try resolution", labels: ["Text only", "Fixed rotation", "Random mode", "Adaptive (Thompson)"], values: [ms.text_only.first_try_resolution.mean, ms.fixed_rotation.first_try_resolution.mean, ms.random.first_try_resolution.mean, ms.adaptive.first_try_resolution.mean] },
], { x: 5.4, y: 1.5, w: 7.3, h: 4.3, barDir: "col", barGapWidthPct: 50, chartColors: [HEX.accent1], valAxisMinVal: 0, valAxisMaxVal: 0.7, dataLabelFormatCode: "0.00", showLegend: false, ...chartStyle("Misconception resolved by the first intervention (simulated learners)") });
text(s, [
  { text: "12 code-drawn diagrams and 7 interactive simulations. ", options: { bold: true, color: C.accent2 } },
  { text: `The adaptive policy needs ${f2(ms.adaptive.mean_interventions.mean)} interventions on average vs ${f2(ms.text_only.mean_interventions.mean)} for text only. 3,000 simulated learners × 5 seeds; assumptions are in the report.`, options: { color: C.text2 } },
], { x: 5.4, y: 5.95, w: 7.3, h: 0.9, fontSize: 13 });
s.addNotes("The backstory says adaptive systems usually change difficulty, not how a concept is taught. Re:Learn changes the teaching mode. A Thompson-sampling policy learns, per misconception, which mode leads to a passed reassessment. The resolution data used in the simulation is synthetic and labelled as such.");

const ex = M.explain_back.counts, pm = M.progress_model.metrics;
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Resolution is earned with evidence, and tracked over time", { placeholder: "title" });
const cols = [
  ["Never one right answer", C.accent1, [
    "Resolved only after ≥2 of 3 transfer questions", "plus a trap question aimed at the old idea", "plus a delayed retest a few questions later",
    "\"Pass the first follow-up, fail the trap → not resolved\" is a permanent test"]],
  ["Explain it back", C.accent3, [
    `${ex.holds.tricky + ex.holds.partly} of ${ex.holds.tricky + ex.holds.partly + ex.holds.clear} misconception-holding explanations are not cleared`,
    `${ex.sound.clear} of ${ex.sound.tricky + ex.sound.partly + ex.sound.clear} sound explanations are accepted`,
    "A second, independent signal of understanding (24 hand-written explanations)"]],
  ["Learner model", C.accent4, [
    "Per-concept Bayesian mastery, every update logged before and after",
    "Misconception states: active → intervened → resolved → relapsed",
    `Progress predictor AUC ${f2(pm.reach_mastery.test.auc)} (reach mastery) and ${f2(pm.misconception_persists.test.auc)} (persists), on simulated learners`]],
];
cols.forEach(([head, color, items], i) => {
  const x = 0.6 + i * 4.1;
  card(s, x, 1.6, 3.85, 3.9, `column ${head}`);
  badge(s, x + 0.25, 1.85, String(i + 1), color, `column badge ${i}`);
  text(s, head, { x: x + 0.95, y: 1.9, w: 2.75, h: 0.45, fontSize: 18, bold: true });
  text(s, items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })), { x: x + 0.25, y: 2.65, w: 3.4, h: 2.8, fontSize: 14, color: C.text2, paraSpaceAfter: 8 });
});
card(s, 0.6, 5.75, 12.1, 0.95, "mastery rule", C.accent1);
text(s, "Mastery scores set difficulty and feed dashboards, but they can never mark a misconception resolved on their own.", { x: 0.9, y: 5.75, w: 11.6, h: 0.95, fontSize: 16, bold: true, valign: "middle" });
s.addNotes("This is the brief's key requirement: don't assume a correct follow-up means learning happened. Mastery scores inform difficulty and dashboards, but they can never mark a misconception resolved on their own.");

pres.addSection({ title: "Close" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
s.addText("Insights: every AI decision is inspectable", { placeholder: "title" });
picture(s, "insights_map.png", 0.6, 1.5, 6.0, 4.6, "Class misconception map screenshot");
picture(s, "insights_trace.png", 6.85, 1.5, 5.85, 4.6, "Decision trace screenshot");
text(s, "Class misconception map · teacher review queue for unfamiliar mistakes · per-answer decision trace with confidence, quick-check entropy, mastery change and model explanations (TF-IDF features, nearest examples, word occlusion) · model evaluation · teaching-mode outcomes.", { x: 0.6, y: 6.25, w: 12.1, h: 0.65, fontSize: 13, color: C.text2 });
s.addNotes("The student view stays clean. Judges and teachers open Insights from the footer link. Every number there is read from storage or from the metrics report.");

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Close" });
s.addText("Limitations and what comes next", { placeholder: "title" });
card(s, 0.6, 1.6, 5.9, 3.9, "limitations");
card(s, 6.8, 1.6, 5.9, 3.9, "next steps");
text(s, "Limitations", { x: 0.9, y: 1.85, w: 5.3, h: 0.45, fontSize: 20, bold: true, color: C.accent4 });
text(s, "Next steps", { x: 7.1, y: 1.85, w: 5.3, h: 0.45, fontSize: 20, bold: true, color: C.accent3 });
const lim = [
  "Synthetic training data and one domain (mechanics)",
  "Quick-check, teaching-mode and progress results come from simulated learners",
  `Unseen-misconception detector still flags ${pct(osSel.test_false_flag_rate)} of known mistakes, so it only feeds a review queue`,
  "Explain-back evaluated on 24 hand-written explanations",
];
const nxt = [
  "Classroom pilot to collect real answers and reasoning",
  "Fine-tune a larger model on real data; recalibrate thresholds",
  "More subjects: algebra and introductory programming",
  "Voice and handwriting input; longer-term learner modelling",
];
text(s, lim.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < lim.length - 1 } })), { x: 0.9, y: 2.45, w: 5.3, h: 3.6, fontSize: 15, color: C.text2, paraSpaceAfter: 10 });
text(s, nxt.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < nxt.length - 1 } })), { x: 7.1, y: 2.45, w: 5.3, h: 3.6, fontSize: 15, color: C.text2, paraSpaceAfter: 10 });
card(s, 0.6, 5.75, 12.1, 0.95, "closing band", C.accent1);
text(s, "167 automated tests · runs on a free CPU with no API key · every number here comes from reports/metrics.json", { x: 0.9, y: 5.75, w: 11.6, h: 0.95, fontSize: 16, bold: true, valign: "middle" });
s.addNotes("Close by restating the loop: diagnose the idea, teach it in the mode that works, verify with evidence. Then invite a judge to try a live question in the app.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
