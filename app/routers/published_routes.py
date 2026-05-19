from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require_driver
from app.matchmaking import assert_last_stop_is_espol
from app.models import PublishedRoute, RouteStop, User, Vehicle, Zone
from app.schemas import PublishedRouteCreate, PublishedRouteOut, utc_now

router = APIRouter(prefix="/published-routes", tags=["published-routes"])


def _validate_zone_ids(db: Session, zone_ids: list[UUID]) -> None:
    found = db.execute(select(Zone.id).where(Zone.id.in_(zone_ids))).scalars().all()
    found_set = set(found)
    missing = [z for z in zone_ids if z not in found_set]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown zone_id in route")


@router.post("", response_model=PublishedRouteOut)
def create_published_route(
    body: PublishedRouteCreate,
    db: Session = Depends(get_db),
    driver: User = Depends(require_driver),
) -> PublishedRoute:
    vehicle = db.get(Vehicle, body.vehicle_id)
    if vehicle is None or vehicle.owner_id != driver.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="vehicle_id not found for this driver")

    tuples = [(s.zone_id, s.leg_minutes_to_next) for s in body.stops]
    zone_ids = [z for z, _ in tuples]
    _validate_zone_ids(db, zone_ids)
    try:
        assert_last_stop_is_espol(db, tuples)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    route = PublishedRoute(
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        title=body.title,
        active=True,
        weekdays=body.weekdays,
        target_arrival_at_espol=body.target_arrival_at_espol,
        estimate_window_minutes=body.estimate_window_minutes,
        created_at=utc_now(),
    )
    db.add(route)
    db.flush()

    for seq, stop in enumerate(body.stops):
        db.add(
            RouteStop(
                route_id=route.id,
                sequence=seq,
                zone_id=stop.zone_id,
                leg_minutes_to_next=stop.leg_minutes_to_next,
            )
        )

    db.commit()

    return _get_route_or_404(db, route.id)


@router.get("/mine", response_model=list[PublishedRouteOut])
def list_my_routes(db: Session = Depends(get_db), driver: User = Depends(require_driver)) -> list[PublishedRoute]:
    stmt = (
        select(PublishedRoute)
        .where(PublishedRoute.driver_id == driver.id)
        .options(
            joinedload(PublishedRoute.stops).joinedload(RouteStop.zone),
            joinedload(PublishedRoute.vehicle),
            joinedload(PublishedRoute.driver),
        )
        .order_by(PublishedRoute.created_at.desc())
    )
    return list(db.execute(stmt).unique().scalars().all())


@router.get("/{route_id}", response_model=PublishedRouteOut)
def get_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PublishedRoute:
    route = _get_route_or_404(db, route_id)
    if route.driver_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para ver esta ruta.")
    return route


def _get_route_or_404(db: Session, route_id: UUID) -> PublishedRoute:
    stmt = (
        select(PublishedRoute)
        .where(PublishedRoute.id == route_id)
        .options(
            joinedload(PublishedRoute.stops).joinedload(RouteStop.zone),
            joinedload(PublishedRoute.vehicle),
            joinedload(PublishedRoute.driver),
        )
    )
    route = db.execute(stmt).unique().scalar_one_or_none()
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return route
