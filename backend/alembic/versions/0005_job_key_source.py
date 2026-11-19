# SPDX-License-Identifier: AGPL-3.0-or-later
"""job key source (free share of the owner's keys)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("key_source", sa.String(length=8), nullable=True))
        batch_op.create_index(batch_op.f("ix_jobs_key_source"), ["key_source"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_jobs_key_source"))
        batch_op.drop_column("key_source")
