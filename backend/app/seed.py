"""Idempotent synthetic demonstration seed data for Kora Living."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.config import get_settings
from app.db import create_db_engine, create_session_factory, init_db
from app.models import Engagement, EngagementStage, InterviewNote, utc_now

DEMO_ENGAGEMENT_NAME = "Kora Living: Customer support turnaround"
DEMO_CLIENT_NAME = "Kora Living"
DEMO_INDUSTRY = "D2C home-goods retail"
DEMO_CLIENT_STATEMENT = (
    "Our customer support team is overwhelmed. Customers are waiting too long for "
    "responses. We have hired more employees, but the problem hasn't improved."
)

DEMO_NOTE_TITLE = "Operations lead intake interview — Maya Chen"
DEMO_NOTE_CONTENT = (
    "I lead day-to-day support operations here at Kora Living, and honestly the inbox "
    "has felt like a treadmill since our seasonal home-goods launch picked up. Every "
    "morning when the team signs on, the shared queue is already overflowing with "
    "overnight emails, web form submissions, and follow-up messages from shoppers who "
    "say they never heard back from us the first time. We sell bulky ceramics, lighting, "
    "and woven textiles directly to consumers, so when something arrives late or cracked, "
    "customers get anxious quickly and start messaging across every channel they can find.\n\n"
    "Right now our workflow is mostly manual from the moment a message lands. Everything "
    "pours into one general intake view, and senior specialists spend a large stretch of "
    "their shift skimming subject lines, guessing which specialist group should own the "
    "case, and dragging tickets into separate folders for order tracking, damaged items, "
    "returns, and billing questions. When someone misjudges what a customer actually "
    "needs, the ticket bounces between queues and sits untouched until another agent "
    "spots it. Newer hires tell me they hesitate before claiming complex cases because "
    "they are unsure which replacement or carrier policy applies, so they either leave "
    "those tickets behind or pass them to a senior teammate for a second look.\n\n"
    "The leadership team assumed we were simply short-handed, so over the past few "
    "seasons we brought on additional generalist agents and stretched shift coverage "
    "later into the evening. What surprised everyone is that adding people barely moved "
    "the needle on how backed up the floor feels. Our most experienced specialists now "
    "spend much of their day answering internal Slack questions, reviewing drafts for "
    "new hires, and untangling reassigned threads instead of closing customer cases. "
    "Meanwhile, routine delivery status inquiries pile up right next to urgent damage "
    "claims and high-value order cancellations, because nothing reliably separates "
    "straightforward requests from time-sensitive escalations.\n\n"
    "We also tried writing a few shared response snippets in a static document so agents "
    "could copy and paste policy wording faster. In practice, people rarely trust those "
    "snippets because our return window and damaged-item instructions were revised a "
    "couple of times and nobody is sure which version is current. Agents end up rewriting "
    "similar replies from scratch or putting tickets on hold while they check with the "
    "warehouse liaison.\n\n"
    "Customer complaints have started showing up in post-purchase surveys and social "
    "comments, mostly mentioning slow replies, repeated requests for the same order "
    "information, and inconsistent answers when a thread changes hands. Some managers "
    "are already pushing to buy an automated chatbot to deflect incoming messages, "
    "while others want to hire again before the holiday rush. Before we spend budget on "
    "either option, I want hard evidence from our ticket history showing where the delays "
    "actually build up, which categories are creating the heaviest drag, and whether a "
    "structured triage workflow with human sign-off would relieve the bottleneck."
)


def seed_demo_data(db: Session) -> dict[str, Any]:
    """Idempotently seed the Kora Living synthetic engagement and intake transcript."""
    engagement = db.scalar(
        select(Engagement).where(Engagement.name == DEMO_ENGAGEMENT_NAME)
    )
    created_engagement = False
    created_note = False

    if engagement is None:
        now = utc_now()
        engagement = Engagement(
            name=DEMO_ENGAGEMENT_NAME,
            client_name=DEMO_CLIENT_NAME,
            industry=DEMO_INDUSTRY,
            client_statement=DEMO_CLIENT_STATEMENT,
            stage=EngagementStage.discover,
            is_synthetic=True,
            created_at=now,
            updated_at=now,
        )
        db.add(engagement)
        db.flush()
        record_audit_event(
            db,
            engagement_id=engagement.id,
            action="create",
            entity_type="engagement",
            entity_id=engagement.id,
            details={"name": engagement.name, "client_name": engagement.client_name, "seeded": True},
        )
        created_engagement = True

    existing_note = db.scalar(
        select(InterviewNote).where(
            InterviewNote.engagement_id == engagement.id,
            InterviewNote.title == DEMO_NOTE_TITLE,
        )
    )
    if existing_note is None:
        note = InterviewNote(
            engagement_id=engagement.id,
            title=DEMO_NOTE_TITLE,
            content=DEMO_NOTE_CONTENT,
            created_at=utc_now(),
        )
        db.add(note)
        db.flush()
        record_audit_event(
            db,
            engagement_id=engagement.id,
            action="create",
            entity_type="note",
            entity_id=note.id,
            details={"title": note.title, "seeded": True},
        )
        created_note = True

    db.commit()
    return {
        "engagement_id": engagement.id,
        "created_engagement": created_engagement,
        "created_note": created_note,
    }


def main() -> None:
    """CLI entrypoint for `python -m app.seed`."""
    settings = get_settings()
    engine = create_db_engine(settings.resolved_database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        result = seed_demo_data(session)
    print(
        f"Seed complete (engagement_id={result['engagement_id']}, "
        f"created_engagement={result['created_engagement']}, "
        f"created_note={result['created_note']})"
    )


if __name__ == "__main__":
    main()
