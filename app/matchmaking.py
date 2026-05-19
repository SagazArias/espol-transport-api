from datetime import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import PublishedRoute, RouteStop, Zone
from app.schemas import MatchQuery, MatchResult, PublishedRouteOut
from app.time_utils import minutes_between, subtract_minutes


def get_espol_zone_id(db: Session) -> UUID:
    z = db.execute(select(Zone.id).where(Zone.is_espol_campus.is_(True)).limit(1)).scalar_one_or_none()
    if z is None:
        raise RuntimeError("ESPOL campus zone is not seeded")
    return z


def assert_last_stop_is_espol(db: Session, stops: list[tuple[UUID, int | None]]) -> None:
    espol_id = get_espol_zone_id(db)
    last_zone_id, last_leg = stops[-1]
    if last_zone_id != espol_id:
        raise ValueError("Last stop must be the ESPOL campus zone")
    if last_leg is not None:
        raise ValueError("Last stop must have leg_minutes_to_next null")


def add_minutes(t: time, minutes: int) -> time:
    return subtract_minutes(t, -minutes)


def leg_sum_to_espol(stops: list[RouteStop], origin_index: int, espol_index: int) -> int:
    total = 0
    for i in range(origin_index, espol_index):
        leg = stops[i].leg_minutes_to_next
        if leg is None:
            raise ValueError("Missing leg duration before ESPOL")
        total += leg
    return total


def match_routes(db: Session, q: MatchQuery) -> list[MatchResult]:
    espol_id = get_espol_zone_id(db)
    stmt = (
        select(PublishedRoute)
        .where(PublishedRoute.active.is_(True))
        .where(PublishedRoute.weekdays.contains([q.weekday]))
        .options(
            joinedload(PublishedRoute.stops).joinedload(RouteStop.zone),
            joinedload(PublishedRoute.vehicle),
            joinedload(PublishedRoute.driver),
        )
    )
    routes = db.execute(stmt).unique().scalars().all()

    results: list[MatchResult] = []
    for route in routes:
        stops = sorted(route.stops, key=lambda s: s.sequence)
        if not stops:
            continue
        try:
            espol_idx = next(i for i, s in enumerate(stops) if s.zone_id == espol_id)
        except StopIteration:
            continue
        if espol_idx != len(stops) - 1:
            continue
        try:
            origin_idx = next(i for i, s in enumerate(stops) if s.zone_id == q.origin_zone_id)
        except StopIteration:
            continue
        if origin_idx >= espol_idx:
            continue

        delta = minutes_between(route.target_arrival_at_espol, q.desired_arrival_at_espol)
        if abs(delta) > q.tolerance_minutes:
            continue

        leg_total = leg_sum_to_espol(stops, origin_idx, espol_idx)
        pickup = subtract_minutes(route.target_arrival_at_espol, leg_total)
        w = route.estimate_window_minutes

        out_route = PublishedRouteOut.model_validate(route)
        results.append(
            MatchResult(
                route=out_route,
                origin_stop_sequence=stops[origin_idx].sequence,
                estimated_pickup_time_at_origin=pickup,
                estimated_pickup_window_start=subtract_minutes(pickup, w),
                estimated_pickup_window_end=add_minutes(pickup, w),
                arrival_delta_minutes=delta,
            )
        )

    results.sort(key=lambda r: (abs(r.arrival_delta_minutes), r.route.target_arrival_at_espol))
    return results
