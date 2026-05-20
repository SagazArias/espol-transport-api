"""recovery phrase and password recovery lockout/logs

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("recovery_phrase_hash", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "password_recovery_lockouts",
        sa.Column("email", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "password_recovery_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False, index=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("password_recovery_logs")
    op.drop_table("password_recovery_lockouts")
    op.drop_column("users", "recovery_phrase_hash")
