# SPDX-License-Identifier: AGPL-3.0-or-later
"""payment orders (optional credit packs)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-19 23:15:40.075464

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("pack_id", sa.String(length=32), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_uzs", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("provider_order_id", sa.String(length=64), nullable=True),
        sa.Column("pay_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_txn_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount_uzs > 0", name="ck_payment_orders_amount_pos"),
        sa.CheckConstraint("credits > 0", name="ck_payment_orders_credits_pos"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_order_id", name="uq_payment_orders_provider_order_id"),
    )
    with op.batch_alter_table("payment_orders", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_payment_orders_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_payment_orders_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_payment_orders_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("payment_orders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_payment_orders_user_id"))
        batch_op.drop_index(batch_op.f("ix_payment_orders_status"))
        batch_op.drop_index(batch_op.f("ix_payment_orders_created_at"))

    op.drop_table("payment_orders")
