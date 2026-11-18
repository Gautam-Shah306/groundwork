"""Pure statistical summary helpers using deterministic NumPy calculations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


def describe_hours(values: pd.Series | Iterable[float | int | None]) -> dict[str, Any]:
    """Compute {n, median, p90, mean} in hours using numpy linear percentiles.

    Empty inputs return n=0 and nulls without raising.
    """
    if isinstance(values, pd.Series):
        cleaned = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    else:
        raw_list = [float(v) for v in values if v is not None and not pd.isna(v)]
        cleaned = np.asarray(raw_list, dtype=float)

    n = int(cleaned.size)
    if n == 0:
        return {"n": 0, "median": None, "p90": None, "mean": None}

    return {
        "n": n,
        "median": float(np.percentile(cleaned, 50, method="linear")),
        "p90": float(np.percentile(cleaned, 90, method="linear")),
        "mean": float(np.mean(cleaned)),
    }


def gini_coefficient(counts: Iterable[float | int]) -> float | None:
    """Compute the standard Gini coefficient over non-negative counts.

    All equal positive counts -> 0.0.
    One entity holding all volume among n entities -> (n - 1) / n.
    Empty or zero-sum input -> None.
    """
    arr = np.asarray([float(c) for c in counts], dtype=float)
    n = int(arr.size)
    if n == 0:
        return None
    total = float(arr.sum())
    if total <= 0.0:
        return None
    diffs = np.abs(arr[:, None] - arr[None, :]).sum()
    return float(diffs / (2.0 * n * total))
