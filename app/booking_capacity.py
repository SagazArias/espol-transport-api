from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BookingStatus, TripBooking


def count_active_driver_bookings(db: Session, driver_id: UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(TripBooking)
            .where(
                TripBooking.driver_id == driver_id,
                TripBooking.status == BookingStatus.active,
            )
        ).scalar_one()
    )


def active_booking_counts(db: Session, driver_ids: list[UUID]) -> dict[UUID, int]:
    if not driver_ids:
        return {}
    rows = db.execute(
        select(TripBooking.driver_id, func.count())
        .where(
            TripBooking.driver_id.in_(driver_ids),
            TripBooking.status == BookingStatus.active,
        )
        .group_by(TripBooking.driver_id)
    ).all()
    return {driver_id: int(count) for driver_id, count in rows}
