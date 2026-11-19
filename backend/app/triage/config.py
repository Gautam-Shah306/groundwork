"""Pydantic loaders and validators for triage queue and priority configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import get_settings

PriorityLevel = Literal["low", "medium", "high"]


class CategoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    queue: str = Field(..., min_length=1)
    description: str | None = None


class QueuesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queues: list[str] = Field(..., min_length=1)
    categories: list[CategoryConfig] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_queue_mappings(self) -> QueuesConfig:
        queue_set = set(self.queues)
        if len(queue_set) != len(self.queues):
            raise ValueError("Duplicate queue names found in queues.yaml.")

        seen_categories: set[str] = set()
        for category in self.categories:
            if category.id in seen_categories:
                raise ValueError(f"Duplicate category '{category.id}' in queues.yaml.")
            seen_categories.add(category.id)
            if not category.queue.strip():
                raise ValueError(f"Category '{category.id}' has no assigned queue.")
            if category.queue not in queue_set:
                raise ValueError(
                    f"Category '{category.id}' maps to unknown queue '{category.queue}'."
                )
        return self


class PriorityRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    description: str = Field(default="")
    any_of: list[str] = Field(default_factory=list)
    all_of: list[str] = Field(default_factory=list)
    only_if_no_other_signals: bool = False
    priority: PriorityLevel
    queue_override: str | None = None

    @model_validator(mode="after")
    def validate_conditions(self) -> PriorityRuleConfig:
        if not self.any_of and not self.all_of:
            raise ValueError(
                f"Rule '{self.id}' must define at least one signal in any_of or all_of."
            )
        return self


class DefaultPriorityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., min_length=1)
    priority: PriorityLevel


class PriorityRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: dict[str, str] = Field(..., min_length=1)
    rules: list[PriorityRuleConfig] = Field(..., min_length=1)
    default: DefaultPriorityConfig

    @model_validator(mode="after")
    def validate_signal_references(self) -> PriorityRulesConfig:
        known_signals = set(self.signals.keys())
        seen_rule_ids: set[str] = set()
        for rule in self.rules:
            if rule.id in seen_rule_ids:
                raise ValueError(f"Duplicate rule id '{rule.id}' in priority_rules.yaml.")
            seen_rule_ids.add(rule.id)

            referenced = set(rule.any_of) | set(rule.all_of)
            unknown = sorted(referenced - known_signals)
            if unknown:
                raise ValueError(
                    f"Rule '{rule.id}' references unknown signal(s): {', '.join(unknown)}."
                )
        return self


class TriageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queues_config: QueuesConfig
    priority_rules_config: PriorityRulesConfig

    @model_validator(mode="after")
    def validate_cross_file_references(self) -> TriageConfig:
        valid_queues = set(self.queues_config.queues)
        for rule in self.priority_rules_config.rules:
            if rule.queue_override is not None and rule.queue_override not in valid_queues:
                raise ValueError(
                    f"Rule '{rule.id}' specifies unknown queue_override '{rule.queue_override}'."
                )
        return self

    @property
    def queues(self) -> list[str]:
        return list(self.queues_config.queues)

    @property
    def categories(self) -> list[CategoryConfig]:
        return list(self.queues_config.categories)

    @property
    def category_to_queue(self) -> dict[str, str]:
        return {cat.id: cat.queue for cat in self.queues_config.categories}

    @property
    def signals(self) -> dict[str, str]:
        return dict(self.priority_rules_config.signals)

    @property
    def rules(self) -> list[PriorityRuleConfig]:
        return list(self.priority_rules_config.rules)

    @property
    def default_priority(self) -> DefaultPriorityConfig:
        return self.priority_rules_config.default


def _load_yaml_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file {path} must contain a YAML mapping.")
    return data


def load_triage_config(config_dir: Path | None = None) -> TriageConfig:
    """Load and validate queues.yaml and priority_rules.yaml with Pydantic."""
    resolved_dir = config_dir if config_dir is not None else get_settings().resolved_config_dir
    queues_raw = _load_yaml_file(resolved_dir / "queues.yaml")
    rules_raw = _load_yaml_file(resolved_dir / "priority_rules.yaml")

    queues_config = QueuesConfig.model_validate(queues_raw)
    priority_rules_config = PriorityRulesConfig.model_validate(rules_raw)
    return TriageConfig(
        queues_config=queues_config,
        priority_rules_config=priority_rules_config,
    )
