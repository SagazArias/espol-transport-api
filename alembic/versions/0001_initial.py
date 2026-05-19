"""initial schema and seed zones

Revision ID: 0001
Revises:
Create Date: 2026-05-13

"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

user_role = postgresql.ENUM("student", "driver", name="user_role", create_type=True)
provider_type = postgresql.ENUM("student", "third_party", name="provider_type", create_type=True)

# Column definitions must not re-emit CREATE TYPE (types are created explicitly below).
user_role_col = postgresql.ENUM("student", "driver", name="user_role", create_type=False)
provider_type_col = postgresql.ENUM("student", "third_party", name="provider_type", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    provider_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_espol_campus", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_zones_slug", "zones", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", user_role_col, nullable=False, server_default=sa.text("'student'::user_role")),
        sa.Column("provider_type", provider_type_col, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plate", sa.String(length=32), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vehicles_owner_id", "vehicles", ["owner_id"])

    op.create_table(
        "published_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("weekdays", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("target_arrival_at_espol", sa.Time(), nullable=False),
        sa.Column("estimate_window_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_published_routes_driver_id", "published_routes", ["driver_id"])
    op.create_index("ix_published_routes_vehicle_id", "published_routes", ["vehicle_id"])

    op.create_table(
        "route_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("published_routes.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("leg_minutes_to_next", sa.Integer(), nullable=True),
        sa.UniqueConstraint("route_id", "sequence", name="uq_route_stop_sequence"),
    )
    op.create_index("ix_route_stops_route_id", "route_stops", ["route_id"])
    op.create_index("ix_route_stops_zone_id", "route_stops", ["zone_id"])

    zones_table = sa.table(
        "zones",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_espol_campus", sa.Boolean()),
    )
    op.bulk_insert(
        zones_table,
        [
            {
                "id": uuid.UUID("a0000001-0000-0000-0000-000000000001"),
                "slug": "mucho-lote-2",
                "name": "Mucho Lote 2",
                "is_espol_campus": False,
            },
            {
                "id": uuid.UUID("a0000001-0000-0000-0000-000000000002"),
                "slug": "romareda",
                "name": "Romareda",
                "is_espol_campus": False,
            },
            {
                "id": uuid.UUID("a0000001-0000-0000-0000-000000000003"),
                "slug": "la-joya",
                "name": "La Joya",
                "is_espol_campus": False,
            },
            {
                "id": uuid.UUID("a0000001-0000-0000-0000-000000000004"),
                "slug": "samborondon-centro",
                "name": "Samborondón (centro)",
                "is_espol_campus": False,
            },
            {
                "id": uuid.UUID("a0000001-0000-0000-0000-000000000005"),
                "slug": "urdesa-central",
                "name": "Urdesa Central",
                "is_espol_campus": False,
            },
            {
                "id": uuid.UUID("a0000001-0000-0000-0000-000000000099"),
                "slug": "espol-campus",
                "name": "ESPOL (campus)",
                "is_espol_campus": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_route_stops_zone_id", table_name="route_stops")
    op.drop_index("ix_route_stops_route_id", table_name="route_stops")
    op.drop_table("route_stops")

    op.drop_index("ix_published_routes_vehicle_id", table_name="published_routes")
    op.drop_index("ix_published_routes_driver_id", table_name="published_routes")
    op.drop_table("published_routes")

    op.drop_index("ix_vehicles_owner_id", table_name="vehicles")
    op.drop_table("vehicles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_zones_slug", table_name="zones")
    op.drop_table("zones")

    provider_type.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
