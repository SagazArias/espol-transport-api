"""Elimina una cuenta y sus datos relacionados."""

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    DriverDayPlan,
    DriverDayZone,
    DriverRating,
    DriverWeeklyProfile,
    InboxAlert,
    LoginLockout,
    PasswordRecoveryLockout,
    PasswordRecoveryLog,
    PublishedRoute,
    RouteStop,
    TripBooking,
    User,
    Vehicle,
)

logger = logging.getLogger(__name__)


def delete_user_account(db: Session, user: User) -> None:
    uid = user.id
    email = user.email.lower()

    booking_ids = db.execute(
        select(TripBooking.id).where(
            (TripBooking.passenger_id == uid) | (TripBooking.driver_id == uid)
        )
    ).scalars().all()

    if booking_ids:
        db.execute(delete(DriverRating).where(DriverRating.booking_id.in_(booking_ids)))
        db.execute(delete(InboxAlert).where(InboxAlert.booking_id.in_(booking_ids)))

    db.execute(delete(DriverRating).where((DriverRating.passenger_id == uid) | (DriverRating.driver_id == uid)))
    db.execute(delete(InboxAlert).where(InboxAlert.recipient_id == uid))
    db.execute(
        delete(TripBooking).where((TripBooking.passenger_id == uid) | (TripBooking.driver_id == uid))
    )

    route_ids = db.execute(select(PublishedRoute.id).where(PublishedRoute.driver_id == uid)).scalars().all()
    if route_ids:
        db.execute(delete(RouteStop).where(RouteStop.route_id.in_(route_ids)))
        db.execute(delete(PublishedRoute).where(PublishedRoute.id.in_(route_ids)))

    plan_ids = db.execute(select(DriverDayPlan.id).where(DriverDayPlan.driver_id == uid)).scalars().all()
    if plan_ids:
        db.execute(delete(DriverDayZone).where(DriverDayZone.day_plan_id.in_(plan_ids)))
        db.execute(delete(DriverDayPlan).where(DriverDayPlan.id.in_(plan_ids)))

    db.execute(delete(DriverWeeklyProfile).where(DriverWeeklyProfile.driver_id == uid))
    db.execute(delete(Vehicle).where(Vehicle.owner_id == uid))
    db.execute(delete(LoginLockout).where(LoginLockout.email == email))
    db.execute(delete(PasswordRecoveryLockout).where(PasswordRecoveryLockout.email == email))
    db.execute(delete(PasswordRecoveryLog).where(PasswordRecoveryLog.email == email))

    db.delete(user)
    db.commit()
    logger.info("Cuenta eliminada: user_id=%s email=%s", uid, email)
