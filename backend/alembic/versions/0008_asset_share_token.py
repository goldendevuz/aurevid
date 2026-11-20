# SPDX-License-Identifier: AGPL-3.0-or-later
"""asset share token (admin-created public link)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("share_token", sa.String(length=48), nullable=True))
        batch_op.create_index("ix_assets_share_token", ["share_token"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_index("ix_assets_share_token")
        batch_op.drop_column("share_token")
