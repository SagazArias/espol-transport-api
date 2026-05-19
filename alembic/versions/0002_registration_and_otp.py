"""registration profile fields and student email OTP

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("espol_verified_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE users SET first_name = full_name WHERE first_name IS NULL")
    op.execute("UPDATE users SET last_name = '' WHERE last_name IS NULL")

    op.create_table(
        "student_email_otps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_student_email_otps_email", "student_email_otps", ["email"])


def downgrade() -> None:
    op.drop_index("ix_student_email_otps_email", table_name="student_email_otps")
    op.drop_table("student_email_otps")

    op.drop_column("users", "espol_verified_at")
    op.drop_column("users", "phone")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
