from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DriverRating


def driver_rating_averages(db: Session, driver_ids: list[UUID]) -> dict[UUID, tuple[float, int]]:
    if not driver_ids:
        return {}
    rows = db.execute(
        select(
            DriverRating.driver_id,
            func.avg(DriverRating.stars),
            func.count(DriverRating.id),
        )
        .where(DriverRating.driver_id.in_(driver_ids))
        .group_by(DriverRating.driver_id)
    ).all()
    return {driver_id: (float(avg), int(count)) for driver_id, avg, count in rows}


def driver_reputation_sort_key(avg: float | None, count: int) -> float:
    """Clave interna de orden (no expuesta al cliente como «reputación»)."""
    if count == 0:
        return -1.0
    return avg or 0.0
