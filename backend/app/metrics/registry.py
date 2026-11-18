"""Metric registry mapping metric_id -> pure metric function."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd

from app.metrics import compute
from app.metrics.config import MetricsConfig, load_metrics_config
from app.metrics.results import MetricResult

MetricFn = Callable[
    [pd.DataFrame, MetricsConfig, datetime | None, dict[str, Any] | None],
    MetricResult,
]

METRIC_REGISTRY: dict[str, MetricFn] = {
    "first_response_time": compute.first_response_time,
    "agent_response_time": compute.agent_response_time,
    "triage_time": compute.triage_time,
    "triage_share_of_first_response": compute.triage_share_of_first_response,
    "resolution_time": compute.resolution_time,
    "volume_by_day": compute.volume_by_day,
    "volume_by_hour": compute.volume_by_hour,
    "volume_by_band": compute.volume_by_band,
    "volume_by_category": compute.volume_by_category,
    "volume_by_channel": compute.volume_by_channel,
    "first_response_by_band": compute.first_response_by_band,
    "category_delay_table": compute.category_delay_table,
    "backlog_ageing": compute.backlog_ageing,
    "agent_workload": compute.agent_workload,
    "reassignment_rate": compute.reassignment_rate,
    "reassigned_vs_not": compute.reassigned_vs_not,
    "sla_attainment": compute.sla_attainment,
    "factor_comparison": compute.factor_comparison,
}


def compute_metric(
    metric_id: str,
    frame: pd.DataFrame,
    config: MetricsConfig | None = None,
    as_of: datetime | None = None,
    params: dict[str, Any] | None = None,
) -> MetricResult:
    """Invoke a single registered metric function deterministically."""
    if metric_id not in METRIC_REGISTRY:
        raise KeyError(f"Unknown metric_id '{metric_id}'.")
    resolved_config = config if config is not None else load_metrics_config()
    return METRIC_REGISTRY[metric_id](frame, resolved_config, as_of, params)


def compute_all_metrics(
    frame: pd.DataFrame,
    config: MetricsConfig | None = None,
    as_of: datetime | None = None,
) -> dict[str, MetricResult]:
    """Compute all registered metrics for a ticket DataFrame."""
    resolved_config = config if config is not None else load_metrics_config()
    return {
        metric_id: fn(frame, resolved_config, as_of, None)
        for metric_id, fn in METRIC_REGISTRY.items()
    }
