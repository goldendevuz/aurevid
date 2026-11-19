# SPDX-License-Identifier: AGPL-3.0-or-later
"""asset alt text (image description)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-20 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("alt_text", sa.String(length=400), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("alt_text")
