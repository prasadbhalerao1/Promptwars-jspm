"""record whether the deck plagiarism check actually ran

`presentation_scores` stored plagiarism results only as rows in `plagiarism_matches`, so
"the check ran and found nothing" and "the check could not run" were both an empty list.
The report UI renders that empty list as "No similarity matches found against prior
submissions" — an affirmative all-clear.

That is not hypothetical: a Qdrant client method removed in 1.18 raised AttributeError
inside a blanket `except Exception: return []`, and every deck was reported clean until
someone noticed by hand.

NOT NULL with server_default true: existing rows were produced by a check that did run
(the swallowed-failure window aside, which is not distinguishable retroactively), so
defaulting them to true preserves their current meaning. Only newly-failed checks write
false.

Revision ID: c7e2a4f81b30
Revises: b4c1d9f27a10
Create Date: 2026-08-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7e2a4f81b30"
down_revision: Union[str, Sequence[str], None] = "b4c1d9f27a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "presentation_scores",
        sa.Column(
            "plagiarism_checked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("presentation_scores", "plagiarism_checked")
