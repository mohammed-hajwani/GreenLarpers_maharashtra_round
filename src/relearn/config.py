import os
import tempfile
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]


class PathsConfig(BaseModel):
    content_dir: str
    data_dir: str
    models_dir: str
    reports_dir: str


class DataConfig(BaseModel):
    target_per_label: int
    val_templates_per_misconception: int
    test_templates_per_misconception: int
    min_total_samples: int
    max_class_imbalance: float


class BaselineConfig(BaseModel):
    word_ngram_max: int
    char_ngram_min: int
    char_ngram_max: int
    C: float
    max_iter: int
    min_macro_f1: float


class EmbeddingConfig(BaseModel):
    encoder: str
    C: float
    max_iter: int
    try_gradient_boosting: bool
    exemplars_per_class: int


class TransformerConfig(BaseModel):
    model_name: str
    max_length: int
    epochs: int
    batch_size: int
    lr: float


class DiagnosisConfig(BaseModel):
    top_k: int
    confident_threshold: float


class DisambiguationConfig(BaseModel):
    max_probes: int
    match_likelihood: float
    mismatch_likelihood: float


class InterventionConfig(BaseModel):
    max_words: int
    llm_personalize: bool


class AssessmentConfig(BaseModel):
    transfer_count: int
    trap_count: int
    transfer_pass_min: int
    retest_gap: int
    resolved_posterior_max: float


class LearnerConfig(BaseModel):
    prior_alpha: float
    prior_beta: float
    pass_beta_increment: float
    fail_alpha_increment: float


class AppConfig(BaseModel):
    db_env: str
    db_filename: str


class Config(BaseModel):
    seed: int
    paths: PathsConfig
    data: DataConfig
    baseline: BaselineConfig
    transformer: TransformerConfig
    embedding: EmbeddingConfig
    diagnosis: DiagnosisConfig
    disambiguation: DisambiguationConfig
    intervention: InterventionConfig
    assessment: AssessmentConfig
    learner: LearnerConfig
    app: AppConfig
    loops: dict

    def path(self, name: str) -> Path:
        return ROOT / getattr(self.paths, name)

    def db_path(self) -> Path:
        override = os.environ.get(self.app.db_env)
        if override:
            return Path(override)
        return Path(tempfile.gettempdir()) / self.app.db_filename


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@lru_cache(maxsize=1)
def load_config() -> Config:
    raw = _read_yaml(ROOT / "configs" / "default.yaml")
    raw["loops"] = _read_yaml(ROOT / "configs" / "loops.yaml")
    return Config.model_validate(raw)
