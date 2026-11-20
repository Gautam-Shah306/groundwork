"""Tests for Outcomes configuration loader and settings defaults."""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from app.config import Settings
from app.outcomes.config import OutcomesConfig, load_outcomes_config


def test_outcomes_config_loads_and_rejects_invalid_values(tmp_path: Path):
    """Test 1: Outcomes config loads valid YAML and rejects out-of-bound or corrupted values."""
    # 1. Valid config loads
    cfg = load_outcomes_config()
    assert isinstance(cfg, OutcomesConfig)
    assert len(cfg.kpi_catalogue) == 6
    assert cfg.simulation.defaults.pilot_share == 0.5
    assert cfg.prioritisation.weights.impact == 0.5
    assert len(cfg.seeded_interventions) == 4

    # 2. Reject weights not summing to 1.0
    bad_data = {
        "kpi_catalogue": [item.model_dump() for item in cfg.kpi_catalogue],
        "simulation": cfg.simulation.model_dump(),
        "prioritisation": {
            "weights": {"impact": 0.5, "ease": 0.5, "safety": 0.5}  # sum = 1.5
        },
        "seeded_interventions": [i.model_dump() for i in cfg.seeded_interventions],
    }
    bad_yaml = tmp_path / "outcomes.yaml"
    bad_yaml.write_text(yaml.safe_dump(bad_data), encoding="utf-8")
    with pytest.raises(Exception):
        load_outcomes_config(tmp_path)

    # 3. Reject empty catalogue
    bad_data["prioritisation"]["weights"] = {"impact": 0.5, "ease": 0.3, "safety": 0.2}
    bad_data["kpi_catalogue"] = []
    bad_yaml.write_text(yaml.safe_dump(bad_data), encoding="utf-8")
    with pytest.raises(Exception):
        load_outcomes_config(tmp_path)


def test_llm_outcomes_max_output_tokens_default_is_4000():
    """Test 40: Default setting for LLM_OUTCOMES_MAX_OUTPUT_TOKENS is 4000."""
    settings = Settings()
    assert settings.llm_outcomes_max_output_tokens == 4000
