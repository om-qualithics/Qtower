"""Idempotent one-time setup: seeds the 5-module AI-usage training
curriculum (handoff §5f). training_module is shared platform content, not
per-org data (see apps/api/modules/training/models.py's docstring) - this
script only ever needs to run once per deployment, not once per org.

Every module starts with video_type="placeholder" (video_url=None) - no
real videos exist yet. Titles/body text/checkpoint questions here are a
first draft, expected to be edited later (via training.manage endpoints,
or by re-running this script after editing it) once the real videos and
final copy exist - upserts by `key`, so it's safe to re-run.

    python -m apps.api.scripts.seed_training_modules
"""
from sqlalchemy import select

from apps.api.core.db import SessionLocal
from apps.api.modules.training.models import TrainingModule

MODULES = [
    dict(
        order_index=1,
        key="choosing",
        title="Choosing",
        description="I found a tool. Can I use it?",
        body_text=(
            "Before you use any AI tool for work, check whether it's already on the Approved AI Tools list. "
            "This module covers how to check, what separates an enterprise account (governed, monitored, "
            "covered by our AI policy) from a personal/consumer account (not governed, not covered), and how "
            "to request a tool that isn't approved yet instead of just using it."
        ),
        questions=[
            {
                "id": "choosing-q1",
                "prompt": "Where do you check whether a tool is already approved before using it?",
                "options": ["The AI Tools catalog in Q Tower", "Ask a coworker informally", "Just try it and see"],
            },
            {
                "id": "choosing-q2",
                "prompt": "In your own words, what's the practical difference between an enterprise and a consumer AI account?",
                "options": None,
            },
            {
                "id": "choosing-q3",
                "prompt": "If a tool isn't on the approved list yet, what should you do?",
                "options": [
                    "Request access via the AI Tools page",
                    "Use it anyway since it seems safe",
                    "Ask IT informally and skip the request",
                ],
            },
        ],
    ),
    dict(
        order_index=2,
        key="using",
        title="Using",
        description="I'm about to put something into an AI tool. What do I need to think about?",
        body_text=(
            "Not all company data is equal. This module walks through our data classification framework - "
            "Restricted, Confidential, Internal, Public - from the perspective of someone about to paste "
            "something into an AI tool, not as abstract policy: a practical filter for 'should this go in?'"
        ),
        questions=[
            {
                "id": "using-q1",
                "prompt": "Which data classification tier needs the most caution before you paste it into an AI tool?",
                "options": ["Restricted", "Confidential", "Internal", "Public"],
            },
            {
                "id": "using-q2",
                "prompt": "Before using an AI tool with company data, what's the first thing to check?",
                "options": [
                    "Whether the tool is cleared for that data's classification tier",
                    "Nothing - AI tools are safe by default",
                    "Whether the tool is free",
                ],
            },
        ],
    ),
    dict(
        order_index=3,
        key="trusting",
        title="Trusting",
        description="The AI gave me an output. How much should I rely on it?",
        body_text=(
            "AI tools can sound confident and still be wrong - this is called hallucination. This module "
            "covers how to verify AI output, and when human review matters, using examples from everyday "
            "work tasks rather than abstract cases."
        ),
        questions=[
            {
                "id": "trusting-q1",
                "prompt": "What does \"hallucination\" mean in the context of an AI tool's output?",
                "options": None,
            },
            {
                "id": "trusting-q2",
                "prompt": "Give an example of a work task where you'd want human review before trusting AI output.",
                "options": None,
            },
        ],
    ),
    dict(
        order_index=4,
        key="protecting",
        title="Protecting",
        description="Something feels off.",
        body_text=(
            "AI has made deepfakes, AI-powered phishing, and executive impersonation more convincing and more "
            "common. This module covers what these look like, how to spot them, and what to do when something "
            "feels off."
        ),
        questions=[
            {
                "id": "protecting-q1",
                "prompt": "Name one warning sign of an AI-powered phishing attempt or a deepfake.",
                "options": None,
            },
            {
                "id": "protecting-q2",
                "prompt": "If you get an urgent request that seems to be from an executive, what should you do first?",
                "options": [
                    "Verify through a separate, known channel before acting",
                    "Act immediately since it's urgent",
                    "Forward it to a coworker and let them decide",
                ],
            },
        ],
    ),
    dict(
        order_index=5,
        key="reporting",
        title="Reporting",
        description="Something went wrong - or I think it did.",
        body_text=(
            "Reporting a concern early is how issues get addressed before they become incidents. This module "
            "covers what counts as a reportable event, who to contact, and why raising a concern in good faith "
            "is protected, not penalized."
        ),
        questions=[
            {
                "id": "reporting-q1",
                "prompt": "Where do you report a suspected AI-related incident?",
                "options": ["Raise Alert (Escalations) in Q Tower", "Wait and see if it happens again", "Nowhere - it's not worth reporting"],
            },
            {
                "id": "reporting-q2",
                "prompt": "Is raising a concern in good faith protected from retaliation?",
                "options": ["Yes", "No", "Only for govern/assure roles"],
            },
        ],
    ),
]


def seed_training_modules() -> None:
    db = SessionLocal()
    try:
        for spec in MODULES:
            existing = db.scalars(select(TrainingModule).where(TrainingModule.key == spec["key"])).first()
            if existing is not None:
                for field in ("order_index", "title", "description", "body_text", "questions"):
                    setattr(existing, field, spec[field])
                print(f"Updated module: {spec['key']}")
            else:
                db.add(TrainingModule(**spec))
                print(f"Created module: {spec['key']}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_training_modules()
