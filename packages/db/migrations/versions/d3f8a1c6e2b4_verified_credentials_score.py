"""add the verified_credentials talent sub-score

Certificates and resume data were parsed and stored but never fed the Talent Score.
This column holds the sub-score that now reads them. Nullable like every other
sub-score: candidates who have provided neither get None, and the weight renormalizes
away rather than scoring them zero.

Revision ID: d3f8a1c6e2b4
Revises: c7e2a4f81b30
Create Date: 2026-10-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3f8a1c6e2b4"
down_revision: Union[str, Sequence[str], None] = "c7e2a4f81b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("talent_scores", sa.Column("verified_credentials", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("talent_scores", "verified_credentials")
