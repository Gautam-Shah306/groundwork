"""Tests for deterministic synthetic dataset, eval set, and answer key generation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.triage.config import load_triage_config  # noqa: E402
from app.triage.priority import evaluate_priority  # noqa: E402
from generate_data import (  # noqa: E402
    CSV_COLUMNS,
    INJECTED_COUNTS,
    PERIOD_END,
    PERIOD_START,
    SEED,
    generate_all,
)

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture(scope="module")
def generated_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out_dir = tmp_path_factory.mktemp("synthetic_data")
    generate_all(output_dir=out_dir, seed=SEED)
    return out_dir


def _load_clean_df(csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    triage_config = load_triage_config()
    valid_categories = {cat.id for cat in triage_config.categories}

    raw = pd.read_csv(csv_path, dtype={"ticket_id": str, "customer_id": str})
    created = pd.to_datetime(raw["created_at"], errors="coerce")
    assigned = pd.to_datetime(raw["assigned_at"], errors="coerce")
    first_resp = pd.to_datetime(raw["first_response_at"], errors="coerce")
    resolved = pd.to_datetime(raw["resolved_at"], errors="coerce")

    bad_mask = (
        raw["ticket_id"].duplicated(keep="first")
        | ((raw["status"] == "resolved") & first_resp.isna())
        | (first_resp.notna() & (first_resp < created))
        | (~raw["category"].isin(valid_categories))
        | ((raw["status"] == "resolved") & resolved.isna())
        | (resolved.notna() & ((resolved - created) > pd.Timedelta(days=300)))
    )
    clean = raw.loc[~bad_mask].copy()
    clean["created_dt"] = created.loc[~bad_mask]
    clean["assigned_dt"] = assigned.loc[~bad_mask]
    clean["first_resp_dt"] = first_resp.loc[~bad_mask]
    clean["resolved_dt"] = resolved.loc[~bad_mask]
    clean["created_hour"] = clean["created_dt"].dt.hour
    clean["triage_lag_h"] = (clean["assigned_dt"] - clean["created_dt"]).dt.total_seconds() / 3600.0
    clean["agent_lag_h"] = (clean["first_resp_dt"] - clean["assigned_dt"]).dt.total_seconds() / 3600.0
    clean["frt_h"] = (clean["first_resp_dt"] - clean["created_dt"]).dt.total_seconds() / 3600.0
    return raw, clean


def test_generation_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    dir_a = tmp_path / "run_a"
    dir_b = tmp_path / "run_b"

    generate_all(output_dir=dir_a, seed=SEED)
    generate_all(output_dir=dir_b, seed=SEED)

    for filename in ("sample_tickets.csv", "eval_tickets.json", "answer_key.json"):
        assert (dir_a / filename).read_bytes() == (dir_b / filename).read_bytes()


def test_sample_csv_has_expected_columns_and_about_2000_rows(generated_dir: Path) -> None:
    raw = pd.read_csv(generated_dir / "sample_tickets.csv")

    assert list(raw.columns) == CSV_COLUMNS
    assert 1950 <= len(raw) <= 2050


def test_timestamps_have_explicit_offset_and_period_is_correct(generated_dir: Path) -> None:
    raw = pd.read_csv(generated_dir / "sample_tickets.csv", dtype=str).fillna("")

    for col in ("created_at", "assigned_at", "first_response_at", "resolved_at"):
        non_empty = raw.loc[raw[col] != "", col]
        assert len(non_empty) > 0
        assert non_empty.str.endswith("+05:30").all()

    created = pd.to_datetime(raw["created_at"])
    assert created.min() >= pd.Timestamp(PERIOD_START)
    assert created.max() <= pd.Timestamp(PERIOD_END)


def test_category_channel_status_values_are_in_vocabulary_except_injected_unknowns(
    generated_dir: Path,
) -> None:
    triage_config = load_triage_config()
    valid_categories = {cat.id for cat in triage_config.categories}
    raw = pd.read_csv(generated_dir / "sample_tickets.csv")

    unknown_cats = set(raw["category"].unique()) - valid_categories
    assert unknown_cats == {"billing_misc"}
    assert set(raw["channel"].unique()).issubset({"email", "chat", "web_form", "whatsapp"})
    assert set(raw["status"].unique()).issubset({"resolved", "pending", "open"})
    assert set(raw["priority"].unique()).issubset({"low", "medium", "high"})
    assert set(raw["queue"].unique()).issubset(set(triage_config.queues))


def test_injected_quality_issue_counts_are_exact(generated_dir: Path) -> None:
    raw = pd.read_csv(generated_dir / "sample_tickets.csv", dtype={"ticket_id": str})
    created = pd.to_datetime(raw["created_at"], errors="coerce")
    first_resp = pd.to_datetime(raw["first_response_at"], errors="coerce")
    resolved = pd.to_datetime(raw["resolved_at"], errors="coerce")

    assert int(((raw["status"] == "resolved") & first_resp.isna()).sum()) == 12
    assert int(raw["ticket_id"].duplicated(keep="first").sum()) == 3
    assert int((first_resp.notna() & (first_resp < created)).sum()) == 8
    assert int((raw["category"] == "billing_misc").sum()) == 6
    assert int(((raw["status"] == "resolved") & resolved.isna()).sum()) == 9
    assert int((resolved.notna() & ((resolved - created) > pd.Timedelta(days=300))).sum()) == 4


def test_triage_lag_is_dominant_share_of_first_response_time(generated_dir: Path) -> None:
    _, clean = _load_clean_df(generated_dir / "sample_tickets.csv")
    staffed = clean[(clean["created_hour"] >= 9) & (clean["created_hour"] < 22)]

    triage_share = float((staffed["triage_lag_h"] / staffed["frt_h"]).median())
    assert 0.45 <= triage_share <= 0.75


def test_misrouting_rate_is_at_least_three_times_higher_for_order_and_returns(
    generated_dir: Path,
) -> None:
    _, clean = _load_clean_df(generated_dir / "sample_tickets.csv")
    or_mask = clean["category"].isin(["order_tracking", "returns_refunds"])

    rate_or = float((clean.loc[or_mask, "reassignment_count"] > 0).mean())
    rate_other = float((clean.loc[~or_mask, "reassignment_count"] > 0).mean())
    assert rate_other > 0
    assert rate_or >= 3.0 * rate_other


def test_evening_band_first_response_is_at_least_one_hour_slower_than_afternoon_band(
    generated_dir: Path,
) -> None:
    _, clean = _load_clean_df(generated_dir / "sample_tickets.csv")
    afternoon = clean[(clean["created_hour"] >= 14) & (clean["created_hour"] < 18)]
    evening = clean[(clean["created_hour"] >= 18) & (clean["created_hour"] < 22)]

    assert float(evening["frt_h"].median()) - float(afternoon["frt_h"].median()) >= 1.0


def test_top_three_agents_carry_between_35_and_45_percent(generated_dir: Path) -> None:
    _, clean = _load_clean_df(generated_dir / "sample_tickets.csv")
    counts = clean["assigned_agent"].value_counts()
    top3_share = float(counts.head(3).sum() / len(clean))

    assert 0.35 <= top3_share <= 0.45


def test_workload_skew_effect_is_smaller_than_triage_effect(generated_dir: Path) -> None:
    _, clean = _load_clean_df(generated_dir / "sample_tickets.csv")
    staffed = clean[(clean["created_hour"] >= 9) & (clean["created_hour"] < 22)]
    top3 = set(clean["assigned_agent"].value_counts().head(3).index)

    top3_median_frt = float(staffed.loc[staffed["assigned_agent"].isin(top3), "frt_h"].median())
    other_median_frt = float(staffed.loc[~staffed["assigned_agent"].isin(top3), "frt_h"].median())
    workload_effect = abs(top3_median_frt - other_median_frt)
    triage_effect = float(staffed["triage_lag_h"].median())

    assert workload_effect < triage_effect


def test_overnight_tickets_wait_for_next_shift_start(generated_dir: Path) -> None:
    _, clean = _load_clean_df(generated_dir / "sample_tickets.csv")
    overnight = clean[(clean["created_hour"] >= 22) | (clean["created_hour"] < 9)]
    assert len(overnight) > 0

    for _, row in overnight.iterrows():
        created_dt: datetime = row["created_dt"].to_pydatetime().astimezone(IST)
        assigned_dt: datetime = row["assigned_dt"].to_pydatetime().astimezone(IST)
        if created_dt.hour >= 22:
            target_date = (created_dt + timedelta(days=1)).date()
        else:
            target_date = created_dt.date()
        shift_start = datetime(target_date.year, target_date.month, target_date.day, 9, 0, 0, tzinfo=IST)
        assert assigned_dt >= shift_start


def test_eval_set_has_150_unique_tickets(generated_dir: Path) -> None:
    eval_tickets = json.loads((generated_dir / "eval_tickets.json").read_text(encoding="utf-8"))

    assert len(eval_tickets) == 150
    ids = [t["id"] for t in eval_tickets]
    assert len(set(ids)) == 150
    assert ids[0] == "EV-001"
    assert ids[-1] == "EV-150"


def test_eval_set_covers_every_category_at_least_12_times(generated_dir: Path) -> None:
    triage_config = load_triage_config()
    eval_tickets = json.loads((generated_dir / "eval_tickets.json").read_text(encoding="utf-8"))

    counts: dict[str, int] = {}
    for ticket in eval_tickets:
        counts[ticket["true_category"]] = counts.get(ticket["true_category"], 0) + 1

    for category in triage_config.categories:
        assert counts.get(category.id, 0) >= 12


def test_eval_set_labels_and_signals_are_in_vocabulary(generated_dir: Path) -> None:
    triage_config = load_triage_config()
    valid_categories = {cat.id for cat in triage_config.categories}
    valid_signals = set(triage_config.signals.keys())
    valid_channels = {"email", "chat", "web_form", "whatsapp"}
    valid_languages = {"en", "hinglish"}

    eval_tickets = json.loads((generated_dir / "eval_tickets.json").read_text(encoding="utf-8"))
    for ticket in eval_tickets:
        assert ticket["true_category"] in valid_categories
        assert ticket["channel"] in valid_channels
        assert ticket["language"] in valid_languages
        assert set(ticket["true_signals"]).issubset(valid_signals)
        if ticket["is_ambiguous"]:
            assert ticket["secondary_category"] in valid_categories
            assert ticket["secondary_category"] != ticket["true_category"]
        else:
            assert ticket["secondary_category"] is None


def test_eval_true_priority_matches_priority_function_for_true_signals(
    generated_dir: Path,
) -> None:
    triage_config = load_triage_config()
    eval_tickets = json.loads((generated_dir / "eval_tickets.json").read_text(encoding="utf-8"))

    for ticket in eval_tickets:
        expected = evaluate_priority(set(ticket["true_signals"]), triage_config).priority
        assert ticket["true_priority"] == expected


def test_eval_set_has_required_ambiguous_hinglish_and_short_counts(
    generated_dir: Path,
) -> None:
    eval_tickets = json.loads((generated_dir / "eval_tickets.json").read_text(encoding="utf-8"))

    ambiguous = sum(1 for t in eval_tickets if t["is_ambiguous"])
    hinglish = sum(1 for t in eval_tickets if t["language"] == "hinglish")
    short = sum(1 for t in eval_tickets if len(t["body"].split()) < 12)
    urgency_or_delay = sum(
        1
        for t in eval_tickets
        if "explicit_urgency" in t["true_signals"]
        or "delivery_delayed_over_3_days" in t["true_signals"]
    )

    assert ambiguous >= 15
    assert hinglish >= 10
    assert short >= 10
    assert urgency_or_delay >= 20


def test_eval_set_has_no_duplicate_bodies(generated_dir: Path) -> None:
    eval_tickets = json.loads((generated_dir / "eval_tickets.json").read_text(encoding="utf-8"))
    bodies = [t["body"] for t in eval_tickets]

    assert len(set(bodies)) == len(bodies)


def test_answer_key_matches_generated_data_and_documents_seed(generated_dir: Path) -> None:
    answer_key = json.loads((generated_dir / "answer_key.json").read_text(encoding="utf-8"))
    raw = pd.read_csv(generated_dir / "sample_tickets.csv")

    assert answer_key["seed"] == SEED
    assert answer_key["injected_quality_issues"] == INJECTED_COUNTS
    assert answer_key["measured_effects"]["total_rows"] == len(raw)
    assert answer_key["measured_effects"]["injected_quality_issues"] == INJECTED_COUNTS
    assert answer_key["eval_set_summary"]["total_tickets"] == 150


def test_app_package_never_references_answer_key() -> None:
    app_dir = REPO_ROOT / "backend" / "app"
    matches: list[str] = []
    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "answer_key" in content:
            matches.append(str(py_file.relative_to(REPO_ROOT)))

    assert matches == []
