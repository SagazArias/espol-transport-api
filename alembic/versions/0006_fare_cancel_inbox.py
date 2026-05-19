"""trip fare, booking cancel, inbox alerts

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

booking_status = postgresql.ENUM("active", "cancelled", name="booking_status", create_type=True)
booking_status_col = postgresql.ENUM("active", "cancelled", name="booking_status", create_type=False)


def upgrade() -> None:
    booking_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "driver_weekly_profiles",
        sa.Column("trip_fare_usd", sa.Numeric(4, 2), nullable=False, server_default="1.50"),
    )

    op.add_column(
        "trip_bookings",
        sa.Column("status", booking_status_col, nullable=False, server_default="active"),
    )
    op.add_column(
        "trip_bookings",
        sa.Column("trip_fare_usd", sa.Numeric(4, 2), nullable=False, server_default="1.50"),
    )
    op.add_column("trip_bookings", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trip_bookings", sa.Column("cancelled_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("trip_bookings", sa.Column("cancellation_reason", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        "fk_trip_bookings_cancelled_by",
        "trip_bookings",
        "users",
        ["cancelled_by_id"],
        ["id"],
    )

    op.create_table(
        "inbox_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trip_bookings.id"), nullable=True),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inbox_alerts_recipient_id", "inbox_alerts", ["recipient_id"])


def downgrade() -> None:
    op.drop_index("ix_inbox_alerts_recipient_id", table_name="inbox_alerts")
    op.drop_table("inbox_alerts")
    op.drop_constraint("fk_trip_bookings_cancelled_by", "trip_bookings", type_="foreignkey")
    op.drop_column("trip_bookings", "cancellation_reason")
    op.drop_column("trip_bookings", "cancelled_by_id")
    op.drop_column("trip_bookings", "cancelled_at")
    op.drop_column("trip_bookings", "trip_fare_usd")
    op.drop_column("trip_bookings", "status")
    op.drop_column("driver_weekly_profiles", "trip_fare_usd")
    op.execute("DROP TYPE IF EXISTS booking_status")
