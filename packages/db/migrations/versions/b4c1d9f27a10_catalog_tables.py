"""curated catalogs to DB: role skill requirements, skill descriptions, avatar hash blacklist

Moves three curated datasets out of Python literals and into tables, so extending them is
an operational action rather than a code change + redeploy:

  * `role_skill_requirements` <- ROLE_SKILL_TAXONOMY (~100 role/skill weights)
  * `skill_descriptions`      <- SKILL_DESCRIPTIONS (~45 entries)
  * `default_avatar_hashes`   <- DEFAULT_AVATAR_HASH_BLACKLIST, which shipped empty with
    the comment "populate with real default-avatar hashes as they're identified in
    production" — impossible to honour while it lived in source.

Schema only. Seed rows are inserted by scripts/seed_db.py, matching how course_catalog
and skill_taxonomy are already populated in this repo (the baseline migration inserts no
data at all).

Revision ID: b4c1d9f27a10
Revises: e8c387ea8123
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c1d9f27a10"
down_revision: Union[str, Sequence[str], None] = "e8c387ea8123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "role_skill_requirements",
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("skill_name", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), server_default="0.5", nullable=False),
        # (role, skill_name) is the natural key: skill_gap.py derives a deterministic
        # Qdrant point id from exactly this pair, so uniqueness here is what stops the
        # vector collection accumulating duplicate points on re-seed.
        sa.PrimaryKeyConstraint("role", "skill_name"),
        sa.CheckConstraint("weight >= 0 AND weight <= 1", name="ck_role_skill_weight_range"),
    )
    op.create_index("idx_role_skill_requirements_role", "role_skill_requirements", ["role"], unique=False)

    op.create_table(
        "skill_descriptions",
        sa.Column("skill_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("skill_name"),
    )

    op.create_table(
        "default_avatar_hashes",
        sa.Column("phash", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("phash"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("default_avatar_hashes")
    op.drop_table("skill_descriptions")
    op.drop_index("idx_role_skill_requirements_role", table_name="role_skill_requirements")
    op.drop_table("role_skill_requirements")
