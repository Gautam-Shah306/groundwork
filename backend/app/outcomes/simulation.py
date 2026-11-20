"""Pure deterministic pilot simulation module (no LLM, no DB access).

Follows non-negotiable rules R1 (deterministic Python only) and R7 (visibly labelled Simulated result).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from app.metrics.config import load_metrics_config


def compute_bootstrap_ci(
    pilot_vals: np.ndarray,
    comp_vals: np.ndarray,
    resamples: int = 2000,
    seed: int = 43,
) -> tuple[float, float]:
    """Compute 95% bootstrap confidence interval for difference of medians (pilot - comp)."""
    rng = np.random.default_rng(seed)
    n_p = len(pilot_vals)
    n_c = len(comp_vals)
    boot_diffs = np.empty(resamples, dtype=float)
    for i in range(resamples):
        p_boot = rng.integers(0, n_p, size=n_p)
        c_boot = rng.integers(0, n_c, size=n_c)
        boot_diffs[i] = np.median(pilot_vals[p_boot]) - np.median(comp_vals[c_boot])

    ci_low, ci_high = np.percentile(boot_diffs, [2.5, 97.5], method="linear")
    return float(ci_low), float(ci_high)


def run_pilot_simulation(
    population_df: pd.DataFrame,
    *,
    pilot_share: float = 0.5,
    reduction_pct: float = 50.0,
    adoption_pct: float = 80.0,
    rework_share: float = 0.0,
    seed: int = 42,
    bootstrap_resamples: int = 2000,
    sla_threshold_hours: float | None = None,
    rework_share_source: str = "eval_run",
) -> dict[str, Any]:
    """Execute the pure deterministic simulation algorithm specified in Prompt 10 B4.

    Population DataFrame must contain columns 'first_response_hours' and 'triage_hours',
    ordered by row_id ascending.
    """
    if sla_threshold_hours is None:
        try:
            mcfg = load_metrics_config()
            sla_threshold_hours = float(mcfg.sla.first_response_hours)
        except Exception:
            sla_threshold_hours = 4.0

    # Validate parameter bounds
    if not (0.2 <= pilot_share <= 0.8):
        raise ValueError(f"pilot_share must be between 0.2 and 0.8 (got {pilot_share})")
    if not (0.0 <= reduction_pct <= 90.0):
        raise ValueError(f"reduction_pct must be between 0.0 and 90.0 (got {reduction_pct})")
    if not (0.0 <= adoption_pct <= 100.0):
        raise ValueError(f"adoption_pct must be between 0.0 and 100.0 (got {adoption_pct})")
    if not (0.0 <= rework_share <= 1.0):
        raise ValueError(f"rework_share must be between 0.0 and 1.0 (got {rework_share})")

    frt = population_df["first_response_hours"].to_numpy(dtype=float)
    triage = population_df["triage_hours"].to_numpy(dtype=float)
    n = len(frt)
    if n == 0:
        raise ValueError("Population for simulation cannot be empty.")

    # 1. Permutation and split
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_pilot = round(pilot_share * n)  # Python round
    n_comparison = n - n_pilot
    pilot_idx = np.sort(perm[:n_pilot])
    comparison_idx = np.sort(perm[n_pilot:])

    # 2. Draw u AFTER permutation, in pilot_idx order
    u = rng.random(n_pilot)
    p_treat = (adoption_pct / 100.0) * (1.0 - rework_share)
    treated = u < p_treat
    n_treated = int(np.sum(treated))

    # 3. Simulate effect on pilot group
    frt_pilot_before = frt[pilot_idx]
    frt_pilot_after = frt_pilot_before - treated * triage[pilot_idx] * (reduction_pct / 100.0)
    frt_comp = frt[comparison_idx]

    # Group statistics
    med_comp = float(np.median(frt_comp))
    p90_comp = float(np.percentile(frt_comp, 90, method="linear"))
    mean_comp = float(np.mean(frt_comp))

    med_pilot_before = float(np.median(frt_pilot_before))
    p90_pilot_before = float(np.percentile(frt_pilot_before, 90, method="linear"))
    mean_pilot_before = float(np.mean(frt_pilot_before))

    med_pilot_after = float(np.median(frt_pilot_after))
    p90_pilot_after = float(np.percentile(frt_pilot_after, 90, method="linear"))
    mean_pilot_after = float(np.mean(frt_pilot_after))

    diff_medians = float(med_pilot_after - med_comp)

    # 4. Bootstrap 95% interval
    ci_low, ci_high = compute_bootstrap_ci(
        frt_pilot_after, frt_comp, resamples=bootstrap_resamples, seed=seed + 1
    )

    # 5. SLA Attainment
    sla_comp = float(np.mean(frt_comp <= sla_threshold_hours) * 100.0)
    sla_pilot_after = float(np.mean(frt_pilot_after <= sla_threshold_hours) * 100.0)

    # 6. Sensitivity Grid
    reduction_grid = [25.0, 50.0, 75.0]
    adoption_grid = [50.0, 80.0, 100.0]
    grid_cells: list[dict[str, Any]] = []

    for r_pct in reduction_grid:
        for a_pct in adoption_grid:
            cell_p_treat = (a_pct / 100.0) * (1.0 - rework_share)
            cell_treated = u < cell_p_treat
            cell_pilot = frt_pilot_before - cell_treated * triage[pilot_idx] * (r_pct / 100.0)
            cell_diff = float(np.median(cell_pilot) - med_comp)
            grid_cells.append(
                {
                    "reduction_pct": r_pct,
                    "adoption_pct": a_pct,
                    "difference_hours": round(cell_diff, 2),
                    "median_pilot_after": round(float(np.median(cell_pilot)), 2),
                }
            )

    results = {
        "simulated": True,
        "label": "Simulated result: not a real client result",
        "parameters": {
            "pilot_share": pilot_share,
            "reduction_pct": reduction_pct,
            "adoption_pct": adoption_pct,
            "rework_share": rework_share,
            "seed": seed,
            "bootstrap_resamples": bootstrap_resamples,
            "sla_threshold_hours": sla_threshold_hours,
        },
        "rework_share_source": rework_share_source,
        "note": "The simulation applies assumed effects; it shows what the assumptions imply, not evidence that the intervention works.",
        "sample_sizes": {
            "n": n,
            "n_pilot": n_pilot,
            "n_comparison": n_comparison,
            "n_treated": n_treated,
            "p_treat": round(p_treat, 4),
        },
        "comparison_group": {
            "median": round(med_comp, 2),
            "p90": round(p90_comp, 2),
            "mean": round(mean_comp, 2),
            "sla_attainment_pct": round(sla_comp, 2),
            "sla_note": "Illustrative SLA threshold from configuration",
        },
        "pilot_group_before": {
            "median": round(med_pilot_before, 2),
            "p90": round(p90_pilot_before, 2),
            "mean": round(mean_pilot_before, 2),
        },
        "pilot_group_after": {
            "median": round(med_pilot_after, 2),
            "p90": round(p90_pilot_after, 2),
            "mean": round(mean_pilot_after, 2),
            "sla_attainment_pct": round(sla_pilot_after, 2),
            "sla_note": "Illustrative SLA threshold from configuration",
        },
        "effect": {
            "difference_of_medians_hours": round(diff_medians, 2),
            "bootstrap_ci_95": [round(float(ci_low), 2), round(float(ci_high), 2)],
        },
        "sensitivity_grid": grid_cells,
    }

    # Compute deterministic results_hash
    canonical_json = json.dumps(results, sort_keys=True)
    results_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    results["results_hash"] = results_hash

    return results
