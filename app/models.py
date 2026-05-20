import enum
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    student = "student"
    driver = "driver"


class TripDirection(str, enum.Enum):
    ida = "ida"
    regreso = "regreso"


class BookingStatus(str, enum.Enum):
    active = "active"
    cancelled = "cancelled"
    completed = "completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.student)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    first_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    espol_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="owner")
    published_routes: Mapped[list["PublishedRoute"]] = relationship(back_populates="driver")
    weekly_profile: Mapped[Optional["DriverWeeklyProfile"]] = relationship(
        back_populates="driver", uselist=False
    )
    day_plans: Mapped[list["DriverDayPlan"]] = relationship(back_populates="driver", cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    plate: Mapped[str] = mapped_column(String(32))
    brand: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    owner: Mapped["User"] = relationship(back_populates="vehicles")
    routes: Mapped[list["PublishedRoute"]] = relationship(back_populates="vehicle")


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_espol_campus: Mapped[bool] = mapped_column(Boolean, default=False)


class PublishedRoute(Base):
    __tablename__ = "published_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    target_arrival_at_espol: Mapped[time] = mapped_column(Time)
    estimate_window_minutes: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    driver: Mapped["User"] = relationship(back_populates="published_routes")
    vehicle: Mapped["Vehicle"] = relationship(back_populates="routes")
    stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route", order_by="RouteStop.sequence", cascade="all, delete-orphan"
    )


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_route_stop_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("published_routes.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id"), index=True)
    leg_minutes_to_next: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    route: Mapped["PublishedRoute"] = relationship(back_populates="stops")
    zone: Mapped["Zone"] = relationship()


class DriverWeeklyProfile(Base):
    __tablename__ = "driver_weekly_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, index=True
    )
    home_zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id"), index=True)
    seat_capacity: Mapped[int] = mapped_column(Integer, default=3)
    trip_fare_usd: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1.50"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    driver: Mapped["User"] = relationship(back_populates="weekly_profile")
    home_zone: Mapped["Zone"] = relationship()


class DriverDayPlan(Base):
    __tablename__ = "driver_day_plans"
    __table_args__ = (UniqueConstraint("driver_id", "weekday", name="uq_driver_day_weekday"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    ida_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    regreso_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    driver: Mapped["User"] = relationship(back_populates="day_plans")
    sectors: Mapped[list["DriverDayZone"]] = relationship(
        back_populates="day_plan", cascade="all, delete-orphan"
    )


class DriverDayZone(Base):
    __tablename__ = "driver_day_zones"
    __table_args__ = (UniqueConstraint("day_plan_id", "zone_id", "direction", name="uq_driver_day_zone_dir"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("driver_day_plans.id"), index=True)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id"), index=True)
    direction: Mapped[TripDirection] = mapped_column(Enum(TripDirection, name="trip_direction"))

    day_plan: Mapped["DriverDayPlan"] = relationship(back_populates="sectors")
    zone: Mapped["Zone"] = relationship()


class TripBooking(Base):
    __tablename__ = "trip_bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    passenger_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    direction: Mapped[TripDirection] = mapped_column(Enum(TripDirection, name="trip_direction"))
    trip_time: Mapped[time] = mapped_column(Time)
    home_zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id"), index=True)
    trip_fare_usd: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1.50"))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), default=BookingStatus.active
    )
    driver_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    passenger: Mapped["User"] = relationship(foreign_keys=[passenger_id])
    driver: Mapped["User"] = relationship(foreign_keys=[driver_id])
    home_zone: Mapped["Zone"] = relationship()


class DriverRating(Base):
    __tablename__ = "driver_ratings"
    __table_args__ = (UniqueConstraint("booking_id", name="uq_driver_rating_booking"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("trip_bookings.id"), index=True)
    passenger_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class InboxAlert(Base):
    __tablename__ = "inbox_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_bookings.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(String(1000))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoginLockout(Base):
    __tablename__ = "login_lockouts"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StudentEmailOtp(Base):
    __tablename__ = "student_email_otps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
