"""Configuration loader and Pydantic schemas for the Outcomes stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from app.config import get_settings


class KpiCatalogueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    name: str
    unit: str
    direction: Literal["lower_is_better", "higher_is_better"]
    description: str = ""


class SimulationDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_share: float = Field(default=0.5, ge=0.2, le=0.8)
    reduction_pct: float = Field(default=50.0, ge=0.0, le=90.0)
    adoption_pct: float = Field(default=80.0, ge=0.0, le=100.0)
    seed: int = 42
    bootstrap_resamples: int = 2000


class SimulationBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pilot_share: list[float]
    reduction_pct: list[float]
    adoption_pct: list[float]
    rework_share: list[float]


class SimulationSensitivityGrids(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reduction_pct: list[float]
    adoption_pct: list[float]


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaults: SimulationDefaults
    bounds: SimulationBounds
    sensitivity_grids: SimulationSensitivityGrids


class PrioritisationWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact: float = Field(default=0.5, ge=0.0, le=1.0)
    ease: float = Field(default=0.3, ge=0.0, le=1.0)
    safety: float = Field(default=0.2, ge=0.0, le=1.0)

    @field_validator("safety")
    @classmethod
    def validate_sum(cls, v: float, info: Any) -> float:
        data = info.data
        total = data.get("impact", 0.0) + data.get("ease", 0.0) + v
        if abs(total - 1.0) > 1e-5:
            raise ValueError(f"Prioritisation weights must sum to 1.0 (got {total:.2f})")
        return v


class PrioritisationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weights: PrioritisationWeights


class SeededIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    impact: int = Field(ge=1, le=5)
    effort: int = Field(ge=1, le=5)
    risk: int = Field(ge=1, le=5)
    rationale: str = ""


class OutcomesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi_catalogue: list[KpiCatalogueItem]
    simulation: SimulationConfig
    prioritisation: PrioritisationConfig
    seeded_interventions: list[SeededIntervention]

    @field_validator("kpi_catalogue")
    @classmethod
    def validate_catalogue(cls, v: list[KpiCatalogueItem]) -> list[KpiCatalogueItem]:
        if not v:
            raise ValueError("kpi_catalogue cannot be empty")
        ids = [item.metric_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("kpi_catalogue metric_ids must be unique")
        return v


def load_outcomes_config(config_dir: Path | None = None) -> OutcomesConfig:
    """Load and validate config/outcomes.yaml with clear validation errors."""
    resolved_dir = config_dir if config_dir is not None else get_settings().resolved_config_dir
    config_file = resolved_dir / "outcomes.yaml"
    if not config_file.exists():
        # Fallback to current working directory
        config_file = Path("config/outcomes.yaml").resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"Outcomes configuration file not found at {config_file}")

    try:
        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML in {config_file}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {config_file}, got {type(data).__name__}")

    return OutcomesConfig.model_validate(data)
