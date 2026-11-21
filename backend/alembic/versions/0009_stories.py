# SPDX-License-Identifier: AGPL-3.0-or-later
"""multi-scene video: stories table, jobs.story_id and jobs.scene_index

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-21 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "stitching",
                "ready",
                "partial",
                "failed",
                name="storystatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.String(length=64), nullable=True),
        sa.Column("final_asset_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("stories", schema=None) as batch_op:
        batch_op.create_index("ix_stories_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_stories_status", ["status"], unique=False)
        batch_op.create_index("ix_stories_created_at", ["created_at"], unique=False)

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("story_id", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("scene_index", sa.Integer(), nullable=True))
        batch_op.create_index("ix_jobs_story_id", ["story_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_jobs_story_id_stories", "stories", ["story_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_jobs_story_id_stories", type_="foreignkey")
        batch_op.drop_index("ix_jobs_story_id")
        batch_op.drop_column("scene_index")
        batch_op.drop_column("story_id")
    with op.batch_alter_table("stories", schema=None) as batch_op:
        batch_op.drop_index("ix_stories_created_at")
        batch_op.drop_index("ix_stories_status")
        batch_op.drop_index("ix_stories_user_id")
    op.drop_table("stories")
