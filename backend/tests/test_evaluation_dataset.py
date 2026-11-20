"""Tests for evaluation dataset loading, validation, fingerprinting, and stratified sampling (B2)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.evaluation.dataset import (
    EvalTicket,
    compute_config_fingerprint,
    compute_dataset_fingerprint,
    load_eval_tickets,
    select_sample,
)
from app.triage.config import load_triage_config


# 1. test_load_eval_tickets_loads_all_150_valid_tickets
def test_load_eval_tickets_loads_all_150_valid_tickets() -> None:
    tickets = load_eval_tickets()
    assert len(tickets) == 150
    assert all(isinstance(t, EvalTicket) for t in tickets)


# 2. test_load_eval_tickets_rejects_missing_file
def test_load_eval_tickets_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        load_eval_tickets(missing)


# 3. test_load_eval_tickets_validates_id_format
def test_load_eval_tickets_validates_id_format(tmp_path: Path) -> None:
    bad_data = [{"id": "INVALID-123", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": [], "true_priority": "low", "is_ambiguous": False, "secondary_category": None, "body": "test"}]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid id"):
        load_eval_tickets(f)


# 4. test_load_eval_tickets_detects_duplicate_id
def test_load_eval_tickets_detects_duplicate_id(tmp_path: Path) -> None:
    bad_data = [
        {"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": [], "true_priority": "medium", "is_ambiguous": False, "secondary_category": None, "body": "1"},
        {"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": [], "true_priority": "medium", "is_ambiguous": False, "secondary_category": None, "body": "2"},
    ]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate ticket id"):
        load_eval_tickets(f)


# 5. test_load_eval_tickets_validates_channel_vocabulary
def test_load_eval_tickets_validates_channel_vocabulary(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "telegram", "language": "en", "true_category": "order_tracking", "true_signals": [], "true_priority": "low", "is_ambiguous": False, "secondary_category": None, "body": "test"}]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid channel"):
        load_eval_tickets(f)


# 6. test_load_eval_tickets_validates_language_vocabulary
def test_load_eval_tickets_validates_language_vocabulary(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "french", "true_category": "order_tracking", "true_signals": [], "true_priority": "low", "is_ambiguous": False, "secondary_category": None, "body": "test"}]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid language"):
        load_eval_tickets(f)


# 7. test_load_eval_tickets_validates_category_in_queues_config
def test_load_eval_tickets_validates_category_in_queues_config(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "unknown_cat", "true_signals": [], "true_priority": "low", "is_ambiguous": False, "secondary_category": None, "body": "test"}]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown true_category"):
        load_eval_tickets(f)


# 8. test_load_eval_tickets_validates_signals_in_rules_config
def test_load_eval_tickets_validates_signals_in_rules_config(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": ["unknown_signal"], "true_priority": "low", "is_ambiguous": False, "secondary_category": None, "body": "test"}]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown signal"):
        load_eval_tickets(f)


# 9. test_load_eval_tickets_confirms_true_priority_matches_deterministic_rules
def test_load_eval_tickets_confirms_true_priority_matches_deterministic_rules(tmp_path: Path) -> None:
    # legal_or_chargeback_threat maps deterministically to high; claim it is low
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": ["legal_or_chargeback_threat"], "true_priority": "low", "is_ambiguous": False, "secondary_category": None, "body": "test"}]
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="true_priority 'low' does not match deterministic priority 'high'"):
        load_eval_tickets(f)


# 10. test_load_eval_tickets_validates_is_ambiguous_and_secondary_consistency
def test_load_eval_tickets_validates_is_ambiguous_and_secondary_consistency(tmp_path: Path) -> None:
    # is_ambiguous True but secondary_category is None
    bad_1 = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": [], "true_priority": "medium", "is_ambiguous": True, "secondary_category": None, "body": "test"}]
    f1 = tmp_path / "bad1.json"
    f1.write_text(json.dumps(bad_1), encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguous ticket must have non-null secondary_category"):
        load_eval_tickets(f1)

    # is_ambiguous False but secondary_category is set
    bad_2 = [{"id": "EV-002", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": [], "true_priority": "medium", "is_ambiguous": False, "secondary_category": "damaged_item", "body": "test"}]
    f2 = tmp_path / "bad2.json"
    f2.write_text(json.dumps(bad_2), encoding="utf-8")
    with pytest.raises(ValueError, match="non-ambiguous ticket must have secondary_category=None"):
        load_eval_tickets(f2)


# 11. test_dataset_fingerprint_is_sha256_and_deterministic
def test_dataset_fingerprint_is_sha256_and_deterministic() -> None:
    fp1 = compute_dataset_fingerprint("data/eval_tickets.json")
    fp2 = compute_dataset_fingerprint("data/eval_tickets.json")
    assert fp1 == fp2
    assert len(fp1) == 64
    int(fp1, 16)  # valid hex


# 12. test_config_fingerprint_changes_on_prompt_change
def test_config_fingerprint_changes_on_prompt_change() -> None:
    fp1 = compute_config_fingerprint(model="test-model")
    with patch("app.triage.prompts.build_classification_system_prompt", return_value="altered prompt"):
        fp2 = compute_config_fingerprint(model="test-model")
    assert fp1 != fp2


# 13. test_config_fingerprint_changes_on_queues_yaml_change
def test_config_fingerprint_changes_on_queues_yaml_change(tmp_path: Path) -> None:
    q = tmp_path / "queues.yaml"
    q.write_text("queues: [General]\ncategories: []", encoding="utf-8")
    fp1 = compute_config_fingerprint(model="test-model")
    fp2 = compute_config_fingerprint(model="test-model", queues_path=q)
    assert fp1 != fp2


# 14. test_config_fingerprint_changes_on_rules_yaml_change
def test_config_fingerprint_changes_on_rules_yaml_change(tmp_path: Path) -> None:
    r = tmp_path / "priority_rules.yaml"
    r.write_text("signals: {}\nrules: []\ndefault_priority: {priority: low, rule_id: R-DEF}", encoding="utf-8")
    fp1 = compute_config_fingerprint(model="test-model")
    fp2 = compute_config_fingerprint(model="test-model", rules_path=r)
    assert fp1 != fp2


# 15. test_config_fingerprint_changes_on_model_change
def test_config_fingerprint_changes_on_model_change() -> None:
    fp1 = compute_config_fingerprint(model="model-alpha")
    fp2 = compute_config_fingerprint(model="model-beta")
    assert fp1 != fp2


# 16. test_select_sample_150_returns_all_tickets_in_file_order
def test_select_sample_150_returns_all_tickets_in_file_order() -> None:
    tickets = load_eval_tickets()
    sample = select_sample(tickets, 150)
    assert len(sample) == 150
    assert [t.id for t in sample] == [t.id for t in tickets]


# 17. test_select_sample_20_stratified_has_representation_from_every_category
def test_select_sample_20_stratified_has_representation_from_every_category() -> None:
    tickets = load_eval_tickets()
    sample = select_sample(tickets, 20)
    assert len(sample) == 20
    categories = {t.true_category for t in sample}
    config = load_triage_config()
    all_categories = {c.id for c in config.categories}
    assert categories == all_categories
    from collections import Counter
    counts = Counter(t.true_category for t in sample)
    min_count = 20 // len(all_categories)
    for cat, cnt in counts.items():
        assert cnt >= min_count


# 18. test_select_sample_is_deterministic_for_same_n
def test_select_sample_is_deterministic_for_same_n() -> None:
    tickets = load_eval_tickets()
    s1 = select_sample(tickets, 35)
    s2 = select_sample(tickets, 35)
    assert [t.id for t in s1] == [t.id for t in s2]
