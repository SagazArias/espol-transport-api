"""drop provider_type from users

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "provider_type")
    op.execute("DROP TYPE IF EXISTS provider_type")


def downgrade() -> None:
    provider_type = postgresql.ENUM("student", "third_party", name="provider_type", create_type=True)
    provider_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("provider_type", provider_type, nullable=True),
    )
