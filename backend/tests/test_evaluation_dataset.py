"""Tests for evaluation dataset loader and stratified sampler (B2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.config import get_project_root
from app.evaluation.dataset import (
    EvalTicket,
    compute_config_fingerprint,
    compute_dataset_fingerprint,
    load_eval_tickets,
    select_sample,
)
from app.triage.config import load_triage_config


def test_eval_ticket_input_fields_equal_the_real_file_keys() -> None:
    """Verify that EvalTicket input fields equal the real 10 keys in data/eval_tickets.json."""
    project_root = get_project_root()
    eval_path = project_root / "data" / "eval_tickets.json"
    with eval_path.open("r", encoding="utf-8") as f:
        raw_items = json.load(f)
    assert len(raw_items) == 150
    expected_keys = {
        "id",
        "subject",
        "body",
        "channel",
        "language",
        "true_category",
        "true_signals",
        "true_priority",
        "is_ambiguous",
        "secondary_category",
    }
    for item in raw_items:
        assert set(item.keys()) == expected_keys
    ticket_fields = set(EvalTicket.model_fields.keys())
    derived_fields = {"true_queue", "is_hinglish", "is_short"}
    assert ticket_fields == expected_keys | derived_fields


# 7. test_load_eval_tickets_loads_all_150_valid_tickets
def test_load_eval_tickets_loads_all_150_valid_tickets() -> None:
    tickets = load_eval_tickets()
    assert len(tickets) == 150
    assert all(isinstance(t, EvalTicket) for t in tickets)


# A2 test_eval_loader_accepts_the_real_file_and_derives_queue_language_and_short_flags
def test_eval_loader_accepts_the_real_file_and_derives_queue_language_and_short_flags() -> None:
    tickets = load_eval_tickets()
    assert len(tickets) == 150
    valid_queues = {"Order support", "Returns and refunds", "Payments", "General", "Escalations"}
    for t in tickets:
        assert t.true_queue in valid_queues
        assert t.is_hinglish == (t.language == "hinglish")
        assert t.is_short == (len(t.body.split()) < 12)


# 8. test_load_eval_tickets_rejects_missing_file
def test_load_eval_tickets_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_eval_tickets(tmp_path / "nonexistent.json")


# 9. test_load_eval_tickets_validates_id_format
def test_load_eval_tickets_validates_id_format(tmp_path: Path) -> None:
    bad_data = [{"id": "INVALID-123", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_priority": "low", "is_ambiguous": False}]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid id"):
        load_eval_tickets(p)


# 10. test_load_eval_tickets_detects_duplicate_id
def test_load_eval_tickets_detects_duplicate_id(tmp_path: Path) -> None:
    bad_data = [
        {"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_priority": "medium", "is_ambiguous": False},
        {"id": "EV-001", "channel": "email", "language": "en", "true_category": "order_tracking", "true_priority": "medium", "is_ambiguous": False},
    ]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate ticket id"):
        load_eval_tickets(p)


# 11. test_load_eval_tickets_validates_channel_vocabulary
def test_load_eval_tickets_validates_channel_vocabulary(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "carrier_pigeon", "language": "en", "true_category": "order_tracking", "true_priority": "low", "is_ambiguous": False}]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid channel"):
        load_eval_tickets(p)


# 12. test_load_eval_tickets_validates_language_vocabulary
def test_load_eval_tickets_validates_language_vocabulary(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "french", "true_category": "order_tracking", "true_priority": "low", "is_ambiguous": False}]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid language"):
        load_eval_tickets(p)


# 13. test_load_eval_tickets_validates_category_in_queues_config
def test_load_eval_tickets_validates_category_in_queues_config(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "alien_invasion", "true_priority": "low", "is_ambiguous": False}]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown true_category"):
        load_eval_tickets(p)


# 14. test_load_eval_tickets_validates_signals_in_rules_config
def test_load_eval_tickets_validates_signals_in_rules_config(tmp_path: Path) -> None:
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": ["unknown_phantom_signal"], "true_priority": "low", "is_ambiguous": False}]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown signal"):
        load_eval_tickets(p)


# 15. test_load_eval_tickets_confirms_true_priority_matches_deterministic_rules
def test_load_eval_tickets_confirms_true_priority_matches_deterministic_rules(tmp_path: Path) -> None:
    # legal_or_chargeback_threat deterministically yields 'high', we claim 'low'
    bad_data = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_signals": ["legal_or_chargeback_threat"], "true_priority": "low", "is_ambiguous": False}]
    p = tmp_path / "eval.json"
    p.write_text(json.dumps(bad_data), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match deterministic priority"):
        load_eval_tickets(p)


# 16. test_load_eval_tickets_validates_is_ambiguous_and_secondary_consistency
def test_load_eval_tickets_validates_is_ambiguous_and_secondary_consistency(tmp_path: Path) -> None:
    # Ambiguous without secondary
    bad1 = [{"id": "EV-001", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_priority": "medium", "is_ambiguous": True, "secondary_category": None}]
    p1 = tmp_path / "eval1.json"
    p1.write_text(json.dumps(bad1), encoding="utf-8")
    with pytest.raises(ValueError, match="must have non-null secondary_category"):
        load_eval_tickets(p1)

    # Non-ambiguous with secondary
    bad2 = [{"id": "EV-002", "channel": "chat", "language": "en", "true_category": "order_tracking", "true_priority": "medium", "is_ambiguous": False, "secondary_category": "payment_issues"}]
    p2 = tmp_path / "eval2.json"
    p2.write_text(json.dumps(bad2), encoding="utf-8")
    with pytest.raises(ValueError, match="must have secondary_category=None"):
        load_eval_tickets(p2)


# 17. test_dataset_fingerprint_is_sha256_and_deterministic
def test_dataset_fingerprint_is_sha256_and_deterministic() -> None:
    fp1 = compute_dataset_fingerprint()
    fp2 = compute_dataset_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 64
    assert re.match(r"^[0-9a-f]{64}$", fp1)


# 18. test_config_fingerprint_changes_on_prompt_change
def test_config_fingerprint_changes_on_prompt_change() -> None:
    fp = compute_config_fingerprint(model="test-model")
    assert len(fp) == 64


# A7.11 test_fingerprint_changes_with_prompt_or_model_and_is_stable_otherwise
def test_fingerprint_changes_with_prompt_or_model_and_is_stable_otherwise() -> None:
    fp_base1 = compute_config_fingerprint(model="model-alpha", temperature=0.0)
    fp_base2 = compute_config_fingerprint(model="model-alpha", temperature=0.0)
    assert fp_base1 == fp_base2

    fp_diff_model = compute_config_fingerprint(model="model-beta", temperature=0.0)
    assert fp_base1 != fp_diff_model

    fp_diff_temp = compute_config_fingerprint(model="model-alpha", temperature=0.7)
    assert fp_base1 != fp_diff_temp


# 19. test_config_fingerprint_changes_on_queues_yaml_change
def test_config_fingerprint_changes_on_queues_yaml_change(tmp_path: Path) -> None:
    fp1 = compute_config_fingerprint(model="test-model")
    q = tmp_path / "queues.yaml"
    q.write_text("modified: true", encoding="utf-8")
    fp2 = compute_config_fingerprint(model="test-model", queues_path=q)
    assert fp1 != fp2


# 20. test_config_fingerprint_changes_on_rules_yaml_change
def test_config_fingerprint_changes_on_rules_yaml_change(tmp_path: Path) -> None:
    fp1 = compute_config_fingerprint(model="test-model")
    r = tmp_path / "rules.yaml"
    r.write_text("modified: true", encoding="utf-8")
    fp2 = compute_config_fingerprint(model="test-model", rules_path=r)
    assert fp1 != fp2


# 21. test_config_fingerprint_changes_on_model_change
def test_config_fingerprint_changes_on_model_change() -> None:
    fp1 = compute_config_fingerprint(model="model-alpha")
    fp2 = compute_config_fingerprint(model="model-beta")
    assert fp1 != fp2


# 22. test_select_sample_150_returns_all_tickets_in_file_order
def test_select_sample_150_returns_all_tickets_in_file_order() -> None:
    tickets = load_eval_tickets()
    sample = select_sample(tickets, 150)
    assert len(sample) == 150
    assert [t.id for t in sample] == [t.id for t in tickets]


# 23. test_select_sample_20_stratified_has_representation_from_every_category
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


# 24. test_select_sample_is_deterministic_for_same_n
def test_select_sample_is_deterministic_for_same_n() -> None:
    tickets = load_eval_tickets()
    s1 = select_sample(tickets, 35)
    s2 = select_sample(tickets, 35)
    assert [t.id for t in s1] == [t.id for t in s2]


# A7.5 test_messages_sent_to_provider_contain_only_the_fenced_ticket_and_no_label_keys
def test_messages_sent_to_provider_contain_only_the_fenced_ticket_and_no_label_keys() -> None:
    from app.llm.base import LLMResponse
    from app.llm.fake import FakeProvider
    from app.triage.service import TriageTicketInput, classify_and_prioritise
    from app.config import Settings
    ticket = load_eval_tickets()[0]
    fake_provider = FakeProvider([
        LLMResponse(
            text=json.dumps({"category": "order_tracking", "secondary_category": None, "signals": [], "rationale": "r"}),
            tool_calls=[],
        )
    ])
    classify_and_prioritise(
        TriageTicketInput(subject=ticket.subject, body=ticket.body, channel=ticket.channel),
        provider=fake_provider,
        settings=Settings(_env_file=None),
    )
    prompt_sent = fake_provider.calls[0].messages[0].content
    assert "<ticket>" in prompt_sent
    assert "</ticket>" in prompt_sent
    # None of the ground truth label keys or values must appear
    forbidden = [
        "true_category",
        "true_signals",
        "true_priority",
        "is_ambiguous",
        "secondary_category",
    ]
    for key in forbidden:
        assert key not in prompt_sent


# A7.12 test_only_evaluation_package_references_eval_tickets_and_label_names_and_triage_never_imports_evaluation
def test_only_evaluation_package_references_eval_tickets_and_label_names_and_triage_never_imports_evaluation() -> None:
    backend_root = Path(__file__).resolve().parent.parent / "app"
    # 1. triage must never import from evaluation
    triage_dir = backend_root / "triage"
    for py_file in triage_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "app.evaluation" not in content, f"{py_file} imports app.evaluation"
        assert "eval_tickets" not in content, f"{py_file} references eval_tickets"

    # 2. outside app/evaluation and app/api/evaluation, eval_tickets and true_category should not appear
    for py_file in backend_root.rglob("*.py"):
        rel = py_file.relative_to(backend_root).as_posix()
        if rel.startswith("evaluation") or rel.startswith("api/evaluation"):
            continue
        content = py_file.read_text(encoding="utf-8")
        assert "eval_tickets" not in content, f"{rel} references eval_tickets"
        assert "true_category" not in content, f"{rel} references true_category"


# A7.13 test_prompts_and_config_share_no_six_word_sequence_with_eval_tickets
def test_prompts_and_config_share_no_six_word_sequence_with_eval_tickets() -> None:
    def extract_6grams(text: str) -> set[tuple[str, ...]]:
        words = re.findall(r"\b[a-z0-9]+\b", text.lower())
        if len(words) < 6:
            return set()
        return {tuple(words[i:i+6]) for i in range(len(words) - 5)}

    from app.triage.prompts import build_classification_system_prompt
    prompt_text = build_classification_system_prompt()
    root = get_project_root()
    queues_text = (root / "config/queues.yaml").read_text(encoding="utf-8")
    rules_text = (root / "config/priority_rules.yaml").read_text(encoding="utf-8")

    combined_ref = f"{prompt_text}\n{queues_text}\n{rules_text}"
    ref_6grams = extract_6grams(combined_ref)

    eval_tickets = json.loads((root / "data/eval_tickets.json").read_text(encoding="utf-8"))
    eval_text = " ".join(f"{t.get('subject', '')} {t.get('body', '')}" for t in eval_tickets)
    eval_6grams = extract_6grams(eval_text)

    overlap = ref_6grams & eval_6grams
    assert len(overlap) == 0, f"Found {len(overlap)} overlapping 6-word sequences: {overlap}"
