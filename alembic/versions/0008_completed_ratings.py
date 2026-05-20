"""booking completed status and driver ratings

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'completed'")

    op.add_column(
        "trip_bookings",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "driver_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trip_bookings.id"), nullable=False),
        sa.Column("passenger_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("booking_id", name="uq_driver_rating_booking"),
    )
    op.create_index("ix_driver_ratings_driver_id", "driver_ratings", ["driver_id"])


def downgrade() -> None:
    op.drop_index("ix_driver_ratings_driver_id", table_name="driver_ratings")
    op.drop_table("driver_ratings")
    op.drop_column("trip_bookings", "completed_at")
    # PostgreSQL no permite quitar valores de enum fácilmente; se deja 'completed' en downgrade parcial.
