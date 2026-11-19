"""Discovery module for qualitative interview analysis and structured problem briefs."""

from app.discovery.postprocess import postprocess_brief
from app.discovery.prompts import (
    DISCOVERY_REPAIR_PROMPT,
    DISCOVERY_SYSTEM_PROMPT,
    NOTE_BLOCK_END,
    NOTE_BLOCK_START,
    VALID_METRIC_IDS,
)
from app.discovery.schema import (
    BriefSections,
    Item,
    KnownFactItem,
    KpiCandidate,
    ProblemStatement,
    QuestionItem,
)
from app.discovery.service import (
    build_analysis_payload,
    execute_discovery_analysis,
    record_brief_version,
)

__all__ = [
    "BriefSections",
    "DISCOVERY_REPAIR_PROMPT",
    "DISCOVERY_SYSTEM_PROMPT",
    "Item",
    "KnownFactItem",
    "KpiCandidate",
    "NOTE_BLOCK_END",
    "NOTE_BLOCK_START",
    "ProblemStatement",
    "QuestionItem",
    "VALID_METRIC_IDS",
    "build_analysis_payload",
    "execute_discovery_analysis",
    "postprocess_brief",
    "record_brief_version",
]
