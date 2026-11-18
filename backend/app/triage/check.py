"""CLI check verifying triage configuration loads cleanly natively and in Docker."""

from __future__ import annotations

from app.triage.config import load_triage_config


def main() -> None:
    config = load_triage_config()
    category_ids = [cat.id for cat in config.categories]
    print(f"Categories ({len(category_ids)}): {', '.join(category_ids)}")
    print(f"Queues ({len(config.queues)}): {', '.join(config.queues)}")
    print(f"Signals: {len(config.signals)}")
    print(f"Rules: {len(config.rules)} (default={config.default_priority.rule_id}:{config.default_priority.priority})")


if __name__ == "__main__":
    main()
