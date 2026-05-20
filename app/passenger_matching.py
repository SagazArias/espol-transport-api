from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.booking_capacity import active_booking_counts
from app.driver_ratings import driver_rating_averages, driver_reputation_sort_key
from app.models import DriverDayPlan, DriverDayZone, DriverWeeklyProfile, TripDirection, User
from app.schemas import PassengerMatchResult, PassengerMatchSearch
from app.time_utils import minutes_between
from app.weekday_labels import weekday_name
from app.zone_matching import resolve_zone


def _zones_for_direction(plan: DriverDayPlan, direction: TripDirection) -> set:
    return {s.zone_id for s in plan.sectors if s.direction == direction}


def _zone_names_for_direction(plan: DriverDayPlan, direction: TripDirection) -> list[str]:
    return [s.zone.name for s in plan.sectors if s.direction == direction]


def search_passenger_matches(db: Session, q: PassengerMatchSearch) -> tuple[list[PassengerMatchResult], str | None]:
    zone = resolve_zone(db, q.home_sector_text)
    if zone is None:
        return [], "No reconocimos ese sector. Prueba con: Mucho Lote, Romareda, La Joya, Samborondón o Urdesa."

    target_time = q.trip_time

    stmt = (
        select(DriverDayPlan)
        .where(DriverDayPlan.weekday == q.weekday)
        .options(
            joinedload(DriverDayPlan.driver).joinedload(User.weekly_profile).joinedload(DriverWeeklyProfile.home_zone),
            joinedload(DriverDayPlan.sectors).joinedload(DriverDayZone.zone),
            joinedload(DriverDayPlan.driver).joinedload(User.vehicles),
        )
    )
    plans = db.execute(stmt).unique().scalars().all()

    driver_ids = list({p.driver.id for p in plans})
    booking_counts = active_booking_counts(db, driver_ids)
    rating_stats = driver_rating_averages(db, driver_ids)

    results: list[PassengerMatchResult] = []
    for plan in plans:
        route_zone_ids = _zones_for_direction(plan, q.direction)
        includes_home = zone.id in route_zone_ids
        includes_weekly_origin = (
            q.direction == TripDirection.ida
            and plan.driver.weekly_profile is not None
            and plan.driver.weekly_profile.home_zone_id == zone.id
        )
        if not includes_home and not includes_weekly_origin:
            continue

        driver_time: time | None
        if q.direction == TripDirection.ida:
            driver_time = plan.ida_time
        else:
            driver_time = plan.regreso_time

        if driver_time is None:
            continue

        delta = minutes_between(driver_time, target_time)
        if abs(delta) > q.tolerance_minutes:
            continue

        vehicle = plan.driver.vehicles[0] if plan.driver.vehicles else None
        profile = plan.driver.weekly_profile
        seat_capacity = profile.seat_capacity if profile else 3
        active_count = booking_counts.get(plan.driver.id, 0)
        remaining = max(0, seat_capacity - active_count)
        seats_full = remaining <= 0
        fare = float(profile.trip_fare_usd) if profile else 1.50
        dir_label = "Ida hacia ESPOL" if q.direction == TripDirection.ida else "Regreso a casa"
        matched_summary = (
            f"{dir_label} · {weekday_name(q.weekday)} {driver_time.strftime('%H:%M')} · {zone.name}"
        )

        avg_stars, rating_count = rating_stats.get(plan.driver.id, (0.0, 0))
        driver_rating_avg = round(avg_stars, 1) if rating_count > 0 else None

        results.append(
            PassengerMatchResult(
                driver_id=plan.driver.id,
                driver_name=plan.driver.full_name,
                driver_first_name=plan.driver.first_name or plan.driver.full_name.split()[0],
                driver_last_name=plan.driver.last_name or "",
                driver_phone=plan.driver.phone,
                vehicle_plate=vehicle.plate if vehicle else None,
                vehicle_brand=vehicle.brand if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                matched_zone_name=zone.name,
                matched_route_summary=matched_summary,
                weekday=q.weekday,
                direction=q.direction,
                trip_time=driver_time,
                time_delta_minutes=delta,
                seat_capacity=seat_capacity,
                available_seats=remaining,
                seats_full=seats_full,
                driver_rating_avg=driver_rating_avg,
                driver_rating_count=rating_count,
                trip_fare_usd=fare,
                ida_route_sectors=_zone_names_for_direction(plan, TripDirection.ida),
                regreso_route_sectors=_zone_names_for_direction(plan, TripDirection.regreso),
            )
        )

    results.sort(
        key=lambda r: (
            -driver_reputation_sort_key(r.driver_rating_avg, r.driver_rating_count),
            abs(r.time_delta_minutes),
            r.driver_name.lower(),
        )
    )
    if not results:
        dir_label = "ida hacia ESPOL" if q.direction == TripDirection.ida else "regreso a casa"
        return [], (
            f"No hay conductores con {dir_label} el {weekday_name(q.weekday)} "
            f"cerca de las {target_time.strftime('%H:%M')} pasando por {zone.name}."
        )
    return results, None
