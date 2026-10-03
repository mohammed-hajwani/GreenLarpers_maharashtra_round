# Re:Learn — PRD (Claude Code Edition)

Domain: introductory physics, mechanics. Target: working end-to-end demo plus evaluation report. Runs offline by default.

## 1. Product summary

Re:Learn diagnoses the misconception behind a learner's answer, disambiguates between look-alike misconceptions, delivers a targeted intervention, reassesses with transfer and trap items, and tracks per-misconception state across attempts. A single correct follow-up never marks a misconception resolved.

Core loop: `submit -> diagnose -> (probe) -> intervene -> reassess -> update learner model`.

Delivery: the demo is a publicly hosted web app (Hugging Face Spaces, free CPU). Nothing is run on a presenter's laptop. Training happens once on Google Colab; the trained model is published to the Hugging Face Hub and the hosted app downloads it at startup.

## 2. Goals and non-goals

Goals: G1 misconception classification, G2 differentiation of confusable pairs, G3 targeted intervention, G4 evidence-based resolution, G5 learner model over time, G6 a publicly hosted demo that works on a free CPU host with no API key.

Non-goals: multi-domain support, accounts or auth, teacher dashboards, image or voice input, autoscaling or any hosting beyond a free-tier public host.

## 3. Taxonomy (fixed for MVP)

| ID | Label | Short description |
|---|---|---|
| M01 | force_for_constant_velocity | Believes a net force is needed to keep constant velocity |
| M02 | heavier_falls_faster | Believes heavier objects fall faster in vacuum or ignoring drag |
| M03 | zero_v_zero_a_at_apex | Believes acceleration is zero at the top of a throw |
| M04 | velocity_acceleration_conflation | Treats velocity and acceleration as the same idea |
| M05 | action_reaction_same_object | Believes action-reaction forces act on the same object |
| M06 | normal_equals_weight | Believes normal force always equals weight |
| M07 | mass_weight_conflation | Treats mass and weight as the same quantity |
| M08 | centripetal_extra_force | Treats centripetal force as an additional separate force |
| M09 | impetus | Believes a thrown object carries a force from the hand |
| M10 | energy_used_up | Believes energy is consumed rather than transformed |
| M11 | bigger_object_bigger_force | Believes the larger object exerts the larger force in a collision |
| M12 | net_force_along_velocity | Believes net force direction always matches velocity direction |

Label `none` is used for correct responses. Total classes: 13.

Confusable groups (`confusable_group` values):
- CG1: {M03, M04} — "acceleration is zero at the top"
- CG2: {M01, M09, M12} — "object keeps moving so a force acts forward"
- CG3: {M05, M11} — "which force is bigger in a collision"
- CG4: {M06, M07} — "weight and normal force are the same number"

## 4. Tech stack (pinned choices)

- Python 3.11, `uv` or pip with `requirements.txt`
- `pydantic>=2`, `pyyaml`, `numpy`, `pandas`, `scikit-learn`, `joblib`
- `torch` (CPU), `transformers`, `datasets`
- Main model default: `distilbert-base-uncased`, max length 256, fine-tuned for sequence classification. Alternative via config: `microsoft/MiniLM-L12-H384-uncased`.
- UI: `streamlit`
- Storage: `sqlite3` from stdlib
- Tests: `pytest`; lint/format: `ruff`
- LLM: Anthropic SDK optional, behind `LLMClient` protocol; `StubLLMClient` is the default
- Training: Google Colab free T4 GPU via `notebooks/train_colab.ipynb`
- Model hosting: public Hugging Face model repo (`HF_MODEL_REPO`)
- App hosting: Hugging Face Spaces, Streamlit SDK, free CPU; fallback host is Streamlit Community Cloud using the same `app.py`
- `huggingface_hub` for download and upload; CPU-only `torch` in the hosting `requirements.txt`

## 5. Repository layout

```
relearn/
  CLAUDE.md
  PRD.md
  DECISIONS.md
  README.md
  Makefile
  requirements.txt
  requirements-train.txt
  .env.example
  app.py
  notebooks/
    train_colab.ipynb
  artifacts/                   committed, small: baseline.joblib, label_map.json, temperature.json, metrics_snapshot.json
  configs/
    default.yaml
    loops.yaml
  content/
    demo_script.json
    misconceptions.yaml
    question_templates/        one YAML per misconception
    probes.yaml
    interventions.yaml
    item_bank.yaml
  src/relearn/
    schemas.py
    config.py
    llm/
      base.py
      stub.py
      anthropic_client.py
      cache.py
    data/
      generator.py
      splits.py
      validate.py
    models/
      baseline.py
      transformer.py
      calibration.py
      inference.py
      loader.py
    diagnosis/
      disambiguator.py
    intervention/
      selector.py
      builder.py
      checker.py
    assessment/
      planner.py
      evaluator.py
    learner/
      state.py
      store.py
    loops/
      active_learning.py
      hard_negatives.py
      scheduler.py
    pipeline.py
    app/
      streamlit_app.py
  scripts/
    generate_data.py
    train.py
    evaluate.py
    simulate_learners.py
    push_to_hub.py
    pull_metrics.py
    deploy_space.py
    smoke_remote.py
  tests/
  data/                        generated, gitignored
  reports/                     metrics.json, figures
```

## 6. Data contracts (`src/relearn/schemas.py`)

```python
from enum import Enum
from pydantic import BaseModel, Field

class QuestionType(str, Enum):
    mcq = "mcq"
    explanation = "explanation"
    numeric = "numeric"

class Question(BaseModel):
    question_id: str
    template_id: str
    question_type: QuestionType
    stem: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    concept_tags: list[str] = Field(default_factory=list)

class LearnerResponse(BaseModel):
    question_id: str
    answer: str
    working: str = ""

class Sample(BaseModel):
    sample_id: str
    question: Question
    response: LearnerResponse
    is_correct: bool
    misconception_label: str
    confusable_group: str | None = None
    rationale: str
    source: str

class Diagnosis(BaseModel):
    top_labels: list[tuple[str, float]]
    is_correct: bool
    ambiguous: bool
    confusable_group: str | None = None

class Probe(BaseModel):
    probe_id: str
    confusable_group: str
    stem: str
    options: list[str]
    expected_answer_by_label: dict[str, str]

class Intervention(BaseModel):
    misconception: str
    strategy: str
    text: str
    follow_up_prompt: str

class AssessmentItem(BaseModel):
    item_id: str
    misconception: str
    kind: str
    stem: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    trap_answer_maps_to: dict[str, str] = Field(default_factory=dict)

class AssessmentResult(BaseModel):
    misconception: str
    transfer_correct: int
    transfer_total: int
    trap_passed: bool | None = None
    retest_passed: bool | None = None
    item_correct: dict[str, bool] = Field(default_factory=dict)

class MisconceptionState(str, Enum):
    unseen = "unseen"
    active = "active"
    intervened = "intervened"
    resolved = "resolved"
    relapsed = "relapsed"

class LearnerRecord(BaseModel):
    learner_id: str
    misconception: str
    state: MisconceptionState
    alpha: float
    beta: float
    strategies_tried: list[str]
    last_updated: str
```

`AssessmentItem.kind` is one of `transfer`, `trap`, `retest`.

## 7. Module interfaces

```python
class LLMClient(Protocol):
    def complete(self, system: str, prompt: str, max_tokens: int = 400) -> str: ...

def generate_dataset(cfg: Config) -> list[Sample]: ...
def split_by_template(samples: list[Sample], cfg: Config) -> dict[str, list[Sample]]: ...
def train_baseline(train: list[Sample], cfg: Config) -> BaselineModel: ...
def train_transformer(train: list[Sample], val: list[Sample], cfg: Config) -> str: ...
def fit_temperature(model_dir: str, val: list[Sample]) -> float: ...
def diagnose(question: Question, response: LearnerResponse) -> Diagnosis: ...
def select_probe(diagnosis: Diagnosis) -> Probe | None: ...
def update_with_probe(diagnosis: Diagnosis, probe: Probe, answer: str) -> Diagnosis: ...
def select_strategy(learner_id: str, misconception: str) -> str: ...
def build_intervention(misconception: str, strategy: str, response: LearnerResponse, history: list[LearnerRecord], llm: LLMClient) -> Intervention: ...
def check_intervention(intervention: Intervention) -> bool: ...
def plan_assessment(misconception: str, learner_id: str) -> list[AssessmentItem]: ...
def evaluate_assessment(items: list[AssessmentItem], answers: dict[str, str]) -> AssessmentResult: ...
def update_learner(learner_id: str, misconception: str, result: AssessmentResult) -> LearnerRecord: ...
```

## 8. Functional requirements

### FR1 Dataset (content-first, offline)
- Content lives in `content/question_templates/*.yaml`. Each template defines a stem with parameter ranges, a correct answer rule, and for each misconception a wrong-answer rule plus a `working` pattern that exhibits the error.
- The generator instantiates parameters with the seeded RNG; no LLM is needed. The LLM client may optionally paraphrase `rationale` and free-text explanations (`source: llm_aug`); `source: template` otherwise.
- Required coverage: per misconception at least 8 templates across all three question types; at least 2 templates per misconception are reserved for the test split and 1 for validation.
- Target size: at least 2000 samples, class balance within 2x, at least 150 samples in each confusable group.
- Confusable samples: for each CG, include templates where two or more misconceptions yield the same final answer and differ only in working or explanation.
- Validation (`validate.py`): schema validity, no duplicate `sample_id`, no template appearing in two splits, every misconception label exists, correct samples have label `none`, every confusable sample has `confusable_group` set.

Example template shape (illustrative, no comments in real files):

```yaml
template_id: m06_block_on_incline_01
question_type: numeric
stem: "A {m} kg block rests on a frictionless incline of {theta} degrees. What is the normal force on the block? Use g = 9.8."
params:
  m: [2, 3, 5, 8]
  theta: [20, 30, 40]
correct:
  answer: "{m*9.8*cos(theta):.1f} N"
  working: "Normal force balances the component of weight perpendicular to the incline: N = m g cos(theta)."
wrong:
  M06:
    answer: "{m*9.8:.1f} N"
    working: "Normal force equals weight, so N = m g."
    rationale: "Ignores incline geometry and equates normal force with weight."
  M07:
    answer: "{m:.1f} N"
    working: "The block has mass {m}, so the normal force is {m}."
    rationale: "Uses mass as if it were a force."
```

### FR2 Misconception model
- Baseline: TF-IDF (word 1-2 grams plus char 3-5 grams) on `stem + answer + working`, logistic regression, class_weight balanced.
- Main: DistilBERT sequence classification on `[CLS] stem [SEP] answer + working`, 13 classes, 4 epochs default, batch 16, lr 5e-5, early stopping on val macro-F1.
- Calibration: temperature scaling fit on validation set; inference returns calibrated top-3.
- `diagnose()` sets `ambiguous = True` when the top-1 vs top-2 gap is below `tau` (default 0.20) and both labels share a `confusable_group`.
- Reports: accuracy, macro-F1, per-class F1, confusion matrix PNG, confusable-subset metrics, baseline vs main comparison, calibration ECE.

### FR3 Differentiation
- `content/probes.yaml` holds at least 3 probes per confusable group. Each probe is a question whose correct-option choice differs by held misconception (`expected_answer_by_label`).
- Posterior update: for each candidate label `l`, multiply current probability by `0.85` if the learner's answer equals `expected_answer_by_label[l]` else `0.10`, then renormalize.
- Stop after at most `max_probes` (default 2) or when the gap reaches `tau`.
- Evaluation: simulated learners (`scripts/simulate_learners.py`) hold a known misconception and answer with 10% noise; report confusable-subset accuracy with and without probing.

### FR4 Interventions
- `content/interventions.yaml` defines for each misconception an ordered list of at least 3 strategies from: `counterexample`, `cognitive_conflict`, `fbd_walkthrough`, `predict_then_check`, `worked_example`, `analogy`. Each has a template with placeholders `{learner_answer}`, `{learner_working}`, `{correct_concept}`.
- `build_intervention()` fills the template; if `llm_personalize` is true in config, the LLM rewrites only a 2-3 sentence wrapper that references the learner's answer. Result is cached by `(misconception, strategy, template_hash)`.
- `check_intervention()` rejects text that is empty, contradicts the stored `correct_concept` string, or exceeds 250 words.
- Interventions target one misconception and never re-teach the whole topic.

### FR5 Resolution assessment
- `content/item_bank.yaml` holds per misconception at least 4 transfer items (differing in surface form: numeric, conceptual, scenario, described diagram) and at least 2 trap items with `trap_answer_maps_to` mapping the tempting wrong option to the misconception.
- `plan_assessment()` returns 3 transfer items plus 1 trap item, never reusing items already seen by that learner when unused items remain.
- Resolved criteria, all required:
  1. At least 2 of 3 transfer items correct.
  2. Trap item answered correctly (tempting wrong answer not chosen).
  3. A delayed retest item, served after at least `retest_gap` (default 3) other attempts, answered correctly.
- Trap failure, or any later response diagnosed with the same misconception, sets state to `relapsed` (if previously resolved) or keeps `intervened -> active` and escalates strategy.
- A learner who passes the first follow-up item but fails the trap must be shown as not resolved. This is a required test.

### FR6 Learner model
- Per `(learner_id, misconception)`: Beta posterior over probability the misconception is currently held, prior `Beta(1,1)`. Wrong-with-that-diagnosis adds to alpha by diagnosis confidence; passing trap or transfer adds to beta.
- State machine:
  - `unseen -> active` on first confident diagnosis (confidence >= 0.5).
  - `active -> intervened` after an intervention is delivered.
  - `intervened -> resolved` only via FR5 criteria and posterior mean of held-probability below 0.25.
  - `resolved -> relapsed` on later diagnosis of the same misconception.
  - `relapsed -> intervened` after a new intervention.
- SQLite tables: `attempts`, `learner_state`, `intervention_stats`, `llm_cache`.
- Profile view lists each misconception, state, posterior mean, attempt count, strategies tried, and a timeline.

### FR7 UI (Streamlit)
Pages: Practice (question, answer, working input), Diagnosis (labels, confidence, explanation, optional probe), Intervention, Reassessment, Profile. Session state holds the current learner id. Include a "demo mode" button that loads a scripted learner for the demo scenario.

### FR8 Hosted deployment
- Target: public URL on Hugging Face Spaces (Streamlit SDK, free CPU). `README.md` starts with the Space front matter block (`title`, `sdk: streamlit`, `app_file: app.py`, `sdk_version` matching the pinned streamlit version, `pinned: false`). Verify the front matter fields against current Hugging Face docs.
- Entrypoint: `app.py` at repo root imports and runs `relearn.app.streamlit_app`.
- Model delivery: Colab trains the transformer and `scripts/push_to_hub.py` uploads weights, tokenizer, `label_map.json`, `temperature.json`, and `metrics.json` to the public repo named by `HF_MODEL_REPO`. The app calls `huggingface_hub.snapshot_download` once inside `st.cache_resource`.
- Committed artifacts: `artifacts/baseline.joblib`, `label_map.json`, `temperature.json`, `metrics_snapshot.json`. Total repo size under 100 MB; no transformer weights in git.
- Loader fallback chain (`models/loader.py`): (1) Hub transformer, (2) committed baseline, (3) error banner with demo-script replay only. The UI shows which model is active.
- Resource budgets on 2 vCPU: cold start under 90 s, diagnosis under 2 s, RAM under 4 GB. Stretch: `torch.quantization.quantize_dynamic` for faster CPU inference.
- State: SQLite path from env `RELEARN_DB`, default `/tmp/relearn.db`. Storage is ephemeral and that is acceptable. Learner id is created per browser session. A Reset demo button wipes it.
- Demo mode: replays `content/demo_script.json` (scripted inputs plus cached expected diagnoses, probe answers, and assessment results) through the real pipeline. If the model failed to load, it replays the cached outputs so the demo still completes.
- LLM at runtime: `StubLLMClient` by default. If `ANTHROPIC_API_KEY` is present and `llm_personalize` is true, use `AnthropicClient` with a 5 s timeout and fall back to the stub on any error.
- Secrets: set as Space secrets or variables, never committed. `.env.example` lists `HF_MODEL_REPO`, `HF_TOKEN`, `ANTHROPIC_API_KEY`, `RELEARN_DB`.
- Health check: `app.py?health=1` renders `ok` plus the active model source; `scripts/smoke_remote.py --url <url>` checks it and replays demo mode.
- Notice in the UI footer: all training data is synthetic and the tool is a prototype.

## 9. Efficiency loops (all configured in `configs/loops.yaml`)

```yaml
active_learning:
  enabled: true
  max_rounds: 3
  samples_per_round: 300
  uncertainty: margin
  stop_if_macro_f1_gain_below: 0.01
hard_negatives:
  enabled: true
  max_rounds: 2
  oversample_factor: 3
disambiguation:
  tau: 0.20
  max_probes: 2
escalation:
  max_strategies_per_misconception: 3
  on_exhausted: flag_for_human
spaced_retest:
  intervals_attempts: [3, 8, 20]
  stop_after_consecutive_passes: 2
strategy_selection:
  method: epsilon_greedy
  epsilon: 0.15
  min_trials_before_exploit: 5
llm_cache:
  enabled: true
  target_hit_rate: 0.7
dev_gate:
  fail_fast: true
```

| Loop | Module | Behavior |
|---|---|---|
| L1 Active learning | `loops/active_learning.py` | Score unlabeled generated pool by margin, add the 300 most uncertain samples, retrain, stop on gain threshold or max rounds |
| L2 Hard negatives | `loops/hard_negatives.py` | Collect val errors inside confusable groups, oversample in next training run |
| L3 Disambiguation | `diagnosis/disambiguator.py` | Probe loop capped by `max_probes` |
| L4 Escalation | `intervention/selector.py` | Failed resolution moves to next untried strategy; exhaustion flags for human help |
| L5 Spaced retest | `loops/scheduler.py` | Re-serve resolved misconceptions at growing attempt intervals |
| L6 Strategy effectiveness | `intervention/selector.py` | Epsilon-greedy using resolution rate per (misconception, strategy) from `intervention_stats` |
| L7 Cache | `llm/cache.py` | SQLite cache keyed by content hash; log hit rate |
| L8 Dev gates | `Makefile` | `make gate` runs tests and thresholds; stage cannot be marked done on failure |

Every loop respects its cap. Log each loop iteration to `reports/loop_log.jsonl`.

## 10. Build order and gates

Each gate is a command that must pass before the next stage. Rows marked HUMAN need credentials or hardware Claude Code does not have. For those, Claude Code finishes the preparation, prints the exact steps from section 16, and waits for the user.

| Stage | Deliverable | Gate |
|---|---|---|
| 0 | Repo scaffold, config, schemas, Makefile, empty tests, `DECISIONS.md` | `make gate STAGE=0`: imports succeed, `pytest` collects, ruff clean |
| 1 | `content/` files for taxonomy, templates, probes, interventions, item bank | YAML loads into schemas; each misconception has required template, strategy, and item counts |
| 2 | Dataset generator, validation, template-level splits | At least 2000 samples, balance within 2x, no template leakage, validator passes |
| 3 | Baseline and transformer training code, calibration, evaluation code; smoke-train of 1 epoch on 300 samples on CPU | Baseline macro-F1 >= 0.60 on held-out templates; smoke-trained model saves and reloads; baseline artifacts written to `artifacts/` |
| 4 | Disambiguator, probes, simulated-learner evaluation | Probing lifts confusable-subset accuracy by at least 10 points over no probing |
| 5 | Intervention selector, builder, checker, cache | Every misconception yields valid interventions for all strategies; cache hit on repeat call |
| 6 | Assessment planner and evaluator, resolution logic | Test "pass first item, fail trap -> not resolved" passes; all FR5 criteria tests pass |
| 7 | Learner model, store, state machine, loops L1-L2, L5-L6 | State machine transition tests pass; `simulate_learners.py` shows resolved rate and relapse detection |
| 8 | Pipeline, `app.py`, Streamlit UI, demo mode with `content/demo_script.json` | Scripted end-to-end test passes; `streamlit run app.py --server.headless true` boots and `?health=1` returns ok |
| 9 | `notebooks/train_colab.ipynb`, `push_to_hub.py`, `pull_metrics.py`, `models/loader.py` with fallback chain | Notebook JSON has only code cells and no comment lines; loader tests cover Hub success, Hub failure to baseline, both failing to banner; `push_to_hub.py --dry-run` passes |
| H1 HUMAN | Run the Colab notebook, publish model to the Hub | `python scripts/pull_metrics.py` shows transformer macro-F1 >= 0.75 and the model repo is public |
| 10 | Space packaging: README front matter, hosting `requirements.txt`, `deploy_space.py`, `smoke_remote.py` | `deploy_space.py --dry-run` lists only allowed files, repo under 100 MB, requirements resolve with `pip install --dry-run`, app boots with Hub model and with Hub unreachable |
| H2 HUMAN | Create the Space and deploy | `python scripts/smoke_remote.py --url <space_url>` returns ok within 90 s and demo mode completes |
| 11 | Evaluation report and README with architecture diagram, results, limitations, live URL | `reports/metrics.json` includes all section 11 metrics; README contains the live URL |

## 11. Evaluation and success metrics

| Metric | Target |
|---|---|
| Transformer macro-F1, held-out templates | >= 0.75 |
| Baseline macro-F1 | reported |
| Confusable-subset accuracy gain with probing | >= +10 points |
| Intervention resolution rate vs "show correct answer" control (simulated learners) | higher, reported with counts |
| False-resolved rate caught by trap items | reported |
| LLM cache hit rate (after warm-up) | >= 70% |
| Diagnosis latency (CPU) | < 2 s |
| Hosted cold start | < 90 s |
| Hosted demo completes with no API key and with Hub unreachable | yes |

Simulated learners: each holds one or two misconceptions with a configured probability of abandoning each after a matching intervention; they answer with 10% noise. Used for loop and resolution evaluation.

## 12. Demo scenario (scripted)

1. Learner submits a wrong answer on a force question; system labels `M01` with explanation.
2. Top-2 labels close; one probe separates them.
3. Targeted counterexample intervention appears.
4. Learner answers the first follow-up correctly but fails the trap; status shown as **not resolved**.
5. Escalation selects a second strategy; learner passes transfer, trap, and delayed retest; status becomes **resolved**.
6. Profile shows state timeline and posterior.

## 13. Risks

| Risk | Mitigation |
|---|---|
| Template-driven data leaks patterns | Template-level splits; paraphrase augmentation; report generalization honestly |
| Label noise in confusable samples | Validator rules plus manual audit of 100 random samples logged in `DECISIONS.md` |
| LLM physics errors | Template-first interventions; `check_intervention`; stub default |
| Overfit to synthetic style | Hold-out templates; include hand-written test set of at least 60 samples in `content/handwritten_test.yaml` |
| Loop runaway | Caps and logging for every loop |
| Free host sleeping or slow cold start | Open the URL 10 minutes before presenting; smoke script run before the demo |
| Hub download fails during the demo | Committed baseline fallback and cached demo-script replay |
| Ephemeral storage resets | Demo mode reseeds the learner; Reset demo button |
| Colab session disconnects mid-training | Notebook saves checkpoints and pushes to the Hub at the end of each epoch |

## 14. Definition of done

All gates in section 10 pass; `make test` green; `make eval` writes full metrics; the public Space URL completes the demo scenario; README states the live URL and limitations (synthetic data, one domain, simulated-learner evaluation).

## 15. First message to give Claude Code

```
Read CLAUDE.md and PRD.md in full. Begin at Stage 0. Write your plan for the stage, implement it, run the gate, commit, then continue to the next stage. Record any assumption in DECISIONS.md. When you reach a HUMAN stage, finish all preparation, print the matching steps from PRD.md section 16 with values filled in, and stop until I confirm. Stop and report only after Stage 11 passes or if you are blocked.
```

## 16. Deployment runbook (human steps)

Claude Code cannot hold your credentials or use Colab, so these steps are yours. Claude Code prints them with real values at each HUMAN stage.

**Before starting:** a Hugging Face account, a write-access token (Settings, Access Tokens), the repo pushed to GitHub (public, so Colab can clone it), and a Google account for Colab.

**H1 Train and publish the model**
1. Open `notebooks/train_colab.ipynb` in Colab and set Runtime to a T4 GPU.
2. Add a Colab secret named `HF_TOKEN` with your write token and enable notebook access.
3. In the first cell, set `REPO_URL` and `HF_MODEL_REPO` (for example `yourname/relearn-distilbert`).
4. Run all cells. Expect 10 to 20 minutes. The last cell prints macro-F1 and the model URL.
5. Locally run `python scripts/pull_metrics.py` to fetch `metrics.json` into `reports/` and `artifacts/metrics_snapshot.json`, then commit.

Notebook cell order (code cells only, no comments): install requirements, set variables, clone repo and `cd`, log in with `google.colab.userdata`, `make data`, train with checkpoint push each epoch, evaluate, final push, print summary.

**H2 Create and deploy the Space**
1. On huggingface.co create a new Space: SDK Streamlit, hardware CPU basic, visibility public.
2. Export `HF_TOKEN` in your terminal and run `python scripts/deploy_space.py --space yourname/relearn`. It uploads only the allowed files. As an alternative, add the Space as a git remote and push `main`.
3. In the Space settings add the variable `HF_MODEL_REPO`. Optionally add the secret `ANTHROPIC_API_KEY`.
4. Wait for the build to finish, then run `python scripts/smoke_remote.py --url https://yourname-relearn.hf.space`.
5. Open the URL and run demo mode once end to end.

## 17. Demo-day plan

- Open the Space URL 10 minutes before presenting to wake it; confirm the footer shows the transformer model, not the baseline.
- Use demo mode for the main walkthrough, then take one live question from a judge.
- Keep a screen recording of a full successful run as a backup in case of network problems.
- Have the metrics table and confusion matrix from `reports/` ready as slides.
