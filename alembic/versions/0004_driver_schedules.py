"""driver weekly schedules for ida/regreso matching

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

trip_direction = postgresql.ENUM("ida", "regreso", name="trip_direction", create_type=True)


def upgrade() -> None:
    op.create_table(
        "driver_weekly_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("home_zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("driver_id", name="uq_driver_weekly_profile_driver"),
    )
    op.create_index("ix_driver_weekly_profiles_driver_id", "driver_weekly_profiles", ["driver_id"])

    op.create_table(
        "driver_day_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("ida_time", sa.Time(), nullable=True),
        sa.Column("regreso_time", sa.Time(), nullable=True),
        sa.UniqueConstraint("driver_id", "weekday", name="uq_driver_day_weekday"),
    )
    op.create_index("ix_driver_day_plans_driver_id", "driver_day_plans", ["driver_id"])

    op.create_table(
        "driver_day_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("day_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("driver_day_plans.id"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=False),
        sa.UniqueConstraint("day_plan_id", "zone_id", name="uq_driver_day_zone"),
    )
    op.create_index("ix_driver_day_zones_day_plan_id", "driver_day_zones", ["day_plan_id"])


def downgrade() -> None:
    op.drop_index("ix_driver_day_zones_day_plan_id", table_name="driver_day_zones")
    op.drop_table("driver_day_zones")
    op.drop_index("ix_driver_day_plans_driver_id", table_name="driver_day_plans")
    op.drop_table("driver_day_plans")
    op.drop_index("ix_driver_weekly_profiles_driver_id", table_name="driver_weekly_profiles")
    op.drop_table("driver_weekly_profiles")
