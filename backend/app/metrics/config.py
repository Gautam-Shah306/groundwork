"""Pydantic configuration loader and validator for config/metrics.yaml."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import get_settings

ILLUSTRATIVE_SLA_NOTE = (
    "Illustrative threshold from configuration, not agreed with the client"
)


class HourWindowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(..., ge=0, le=23)
    end: int = Field(..., ge=0, le=24)

    @model_validator(mode="after")
    def validate_non_empty(self) -> HourWindowConfig:
        if self.start == self.end:
            raise ValueError("Hour window start and end must differ.")
        return self

    def covered_hours(self) -> list[int]:
        """Return the set of integer hours [0..23] covered by [start, end)."""
        if self.start < self.end:
            return list(range(self.start, self.end))
        # Wrap around midnight, e.g. 22 -> 9 covers 22, 23, 0, ..., 8
        return list(range(self.start, 24)) + list(range(0, self.end))


class AgeingBucketConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float = Field(..., ge=0)
    max: float | None = Field(default=None)

    @model_validator(mode="after")
    def validate_bounds(self) -> AgeingBucketConfig:
        if self.max is not None and self.max <= self.min:
            raise ValueError("Ageing bucket max must be greater than min.")
        return self


class SlaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_response_hours: float = Field(..., gt=0)
    resolution_hours: float = Field(..., gt=0)


class TriageShareThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weak: float = Field(..., ge=0.0, le=1.0)
    moderate: float = Field(..., ge=0.0, le=1.0)
    strong: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_order(self) -> TriageShareThresholds:
        if not (self.weak <= self.moderate <= self.strong):
            raise ValueError("triage_share thresholds must satisfy weak <= moderate <= strong.")
        return self


class MisroutingThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_rate: float = Field(..., ge=0.0, le=1.0)
    ratio_moderate: float = Field(..., ge=1.0)
    ratio_strong: float = Field(..., ge=1.0)
    min_category_n: int = Field(..., ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> MisroutingThresholds:
        if self.ratio_moderate > self.ratio_strong:
            raise ValueError("misrouting ratio_moderate must be <= ratio_strong.")
        return self


class EveningThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diff_hours_moderate: float = Field(..., gt=0.0)
    diff_hours_strong: float = Field(..., gt=0.0)

    @model_validator(mode="after")
    def validate_order(self) -> EveningThresholds:
        if self.diff_hours_moderate > self.diff_hours_strong:
            raise ValueError("evening diff_hours_moderate must be <= diff_hours_strong.")
        return self


class WorkloadThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_n: int = Field(..., ge=1)
    frt_diff_hours_moderate: float = Field(..., gt=0.0)
    frt_diff_hours_strong: float = Field(..., gt=0.0)

    @model_validator(mode="after")
    def validate_order(self) -> WorkloadThresholds:
        if self.frt_diff_hours_moderate > self.frt_diff_hours_strong:
            raise ValueError(
                "workload frt_diff_hours_moderate must be <= frt_diff_hours_strong."
            )
        return self


class BacklogThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_share_over_7d: float = Field(..., ge=0.0, le=1.0)


class CoverageThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_excluded_share: float = Field(..., ge=0.0, le=1.0)


class FindingsThresholdsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triage_share: TriageShareThresholds
    misrouting: MisroutingThresholds
    evening: EveningThresholds
    workload: WorkloadThresholds
    backlog: BacklogThresholds
    coverage: CoverageThresholds


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str
    staffed_hours: HourWindowConfig
    creation_bands: dict[str, HourWindowConfig]
    ageing_buckets_days: dict[str, AgeingBucketConfig]
    sla: SlaConfig
    min_sample: int = Field(..., ge=1)
    findings_thresholds: FindingsThresholdsConfig

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone '{value}'.") from exc
        return value

    @model_validator(mode="after")
    def validate_bands_and_buckets(self) -> MetricsConfig:
        if not self.creation_bands:
            raise ValueError("creation_bands must not be empty.")

        seen_hours: dict[int, str] = {}
        for band_name, window in self.creation_bands.items():
            for hour in window.covered_hours():
                if hour in seen_hours:
                    raise ValueError(
                        f"Overlapping creation_bands at hour {hour}: "
                        f"'{seen_hours[hour]}' and '{band_name}'."
                    )
                seen_hours[hour] = band_name

        missing_hours = sorted(set(range(24)) - set(seen_hours.keys()))
        if missing_hours:
            raise ValueError(
                f"creation_bands have gap(s) missing hour(s): {missing_hours}."
            )

        if not self.ageing_buckets_days:
            raise ValueError("ageing_buckets_days must not be empty.")

        ordered_buckets = sorted(
            self.ageing_buckets_days.items(), key=lambda pair: pair[1].min
        )
        if ordered_buckets[0][1].min != 0:
            raise ValueError("ageing_buckets_days must start at 0 days.")
        for idx in range(len(ordered_buckets) - 1):
            curr_name, curr_bucket = ordered_buckets[idx]
            next_name, next_bucket = ordered_buckets[idx + 1]
            if curr_bucket.max is None:
                raise ValueError(
                    f"Open-ended ageing bucket '{curr_name}' must be the final bucket."
                )
            if curr_bucket.max != next_bucket.min:
                raise ValueError(
                    f"ageing_buckets_days gap or overlap between '{curr_name}' and '{next_name}'."
                )
        if ordered_buckets[-1][1].max is not None:
            raise ValueError("Final ageing bucket must have max: null (unbounded).")

        return self

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_metrics_config(config_dir: Path | None = None) -> MetricsConfig:
    """Load and validate config/metrics.yaml using Pydantic."""
    resolved_dir = (
        config_dir if config_dir is not None else get_settings().resolved_config_dir
    )
    path = resolved_dir / "metrics.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Required metrics configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Metrics configuration file {path} must contain a YAML mapping.")
    return MetricsConfig.model_validate(raw)
