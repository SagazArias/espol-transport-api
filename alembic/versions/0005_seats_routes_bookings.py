"""seat capacity, route direction per zone, trip bookings

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

trip_direction = postgresql.ENUM("ida", "regreso", name="trip_direction", create_type=True)
trip_direction_col = postgresql.ENUM("ida", "regreso", name="trip_direction", create_type=False)


def upgrade() -> None:
    trip_direction.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "driver_weekly_profiles",
        sa.Column("seat_capacity", sa.Integer(), nullable=False, server_default="3"),
    )

    op.drop_constraint("uq_driver_day_zone", "driver_day_zones", type_="unique")
    op.add_column(
        "driver_day_zones",
        sa.Column("direction", trip_direction_col, nullable=False, server_default="ida"),
    )
    op.execute("UPDATE driver_day_zones SET direction = 'ida' WHERE direction IS NULL")
    op.create_unique_constraint("uq_driver_day_zone_dir", "driver_day_zones", ["day_plan_id", "zone_id", "direction"])

    op.create_table(
        "trip_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("passenger_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("direction", trip_direction_col, nullable=False),
        sa.Column("trip_time", sa.Time(), nullable=False),
        sa.Column("home_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("driver_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trip_bookings_driver_id", "trip_bookings", ["driver_id"])
    op.create_index("ix_trip_bookings_passenger_id", "trip_bookings", ["passenger_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_bookings_passenger_id", table_name="trip_bookings")
    op.drop_index("ix_trip_bookings_driver_id", table_name="trip_bookings")
    op.drop_table("trip_bookings")
    op.drop_constraint("uq_driver_day_zone_dir", "driver_day_zones", type_="unique")
    op.drop_column("driver_day_zones", "direction")
    op.create_unique_constraint("uq_driver_day_zone", "driver_day_zones", ["day_plan_id", "zone_id"])
    op.drop_column("driver_weekly_profiles", "seat_capacity")
    op.execute("DROP TYPE IF EXISTS trip_direction")
