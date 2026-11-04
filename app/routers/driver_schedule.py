from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_driver
from app.models import DriverDayPlan, DriverDayZone, DriverWeeklyProfile, TripDirection, User
from app.schemas import (
    DriverDayPlanOut,
    DriverWeeklyScheduleIn,
    DriverWeeklyScheduleOut,
    ZoneOut,
    utc_now,
)
from app.fare_utils import parse_and_validate_fare
from app.zone_matching import resolve_zone_id

router = APIRouter(prefix="/driver/weekly-schedule", tags=["driver-schedule"])


def _zones_by_direction(plan: DriverDayPlan, direction: TripDirection) -> list[ZoneOut]:
    return [ZoneOut.model_validate(s.zone) for s in plan.sectors if s.direction == direction]


def _load_schedule(db: Session, driver_id) -> DriverWeeklyScheduleOut:
    profile = db.execute(
        select(DriverWeeklyProfile)
        .where(DriverWeeklyProfile.driver_id == driver_id)
        .options(joinedload(DriverWeeklyProfile.home_zone))
    ).scalar_one_or_none()

    plans = db.execute(
        select(DriverDayPlan)
        .where(DriverDayPlan.driver_id == driver_id)
        .where(DriverDayPlan.weekday <= 4)
        .options(joinedload(DriverDayPlan.sectors).joinedload(DriverDayZone.zone))
        .order_by(DriverDayPlan.weekday)
    ).unique().scalars().all()

    days: list[DriverDayPlanOut] = []
    for plan in plans:
        days.append(
            DriverDayPlanOut(
                weekday=plan.weekday,
                ida_time=plan.ida_time,
                regreso_time=plan.regreso_time,
                ida_sectors=_zones_by_direction(plan, TripDirection.ida),
                regreso_sectors=_zones_by_direction(plan, TripDirection.regreso),
            )
        )

    return DriverWeeklyScheduleOut(
        home_zone=ZoneOut.model_validate(profile.home_zone) if profile else None,
        seat_capacity=profile.seat_capacity if profile else 3,
        trip_fare_usd=float(profile.trip_fare_usd) if profile else 1.50,
        days=days,
    )


def _add_sectors_from_texts(
    db: Session,
    plan: DriverDayPlan,
    texts: list[str],
    direction: TripDirection,
    seen: set[tuple],
) -> None:
    for text in texts:
        zid = resolve_zone_id(db, text.strip())
        if zid is None:
            continue
        key = (zid, direction)
        if key in seen:
            continue
        seen.add(key)
        db.add(DriverDayZone(day_plan_id=plan.id, zone_id=zid, direction=direction))


@router.get("", response_model=DriverWeeklyScheduleOut)
def get_weekly_schedule(
    db: Session = Depends(get_db),
    driver: User = Depends(require_driver),
) -> DriverWeeklyScheduleOut:
    return _load_schedule(db, driver.id)


@router.put("", response_model=DriverWeeklyScheduleOut)
def put_weekly_schedule(
    body: DriverWeeklyScheduleIn,
    db: Session = Depends(get_db),
    driver: User = Depends(require_driver),
) -> DriverWeeklyScheduleOut:
    if body.seat_capacity < 1 or body.seat_capacity > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Los cupos deben ser entre 1 y 20.")

    try:
        fare = parse_and_validate_fare(body.trip_fare_usd)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    home_zone_id = resolve_zone_id(db, body.home_sector_text)
    if home_zone_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No reconocimos el sector de origen. Usa nombres como Mucho Lote, Romareda, La Joya, etc.",
        )

    for day_in in body.days:
        if day_in.weekday < 0 or day_in.weekday > 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permiten días de lunes (0) a viernes (4).",
            )

    profile = db.execute(
        select(DriverWeeklyProfile).where(DriverWeeklyProfile.driver_id == driver.id)
    ).scalar_one_or_none()
    now = utc_now()
    if profile is None:
        profile = DriverWeeklyProfile(
            driver_id=driver.id,
            home_zone_id=home_zone_id,
            seat_capacity=body.seat_capacity,
            trip_fare_usd=fare,
            updated_at=now,
        )
        db.add(profile)
    else:
        profile.home_zone_id = home_zone_id
        profile.seat_capacity = body.seat_capacity
        profile.trip_fare_usd = fare
        profile.updated_at = now

    existing_plans = {
        p.weekday: p
        for p in db.execute(select(DriverDayPlan).where(DriverDayPlan.driver_id == driver.id)).scalars().all()
    }

    for day_in in body.days:
        plan = existing_plans.get(day_in.weekday)
        if plan is None:
            plan = DriverDayPlan(driver_id=driver.id, weekday=day_in.weekday)
            db.add(plan)
            db.flush()
            existing_plans[day_in.weekday] = plan
        else:
            for sector in list(plan.sectors):
                db.delete(sector)
            # SQLAlchemy ejecuta INSERT antes que DELETE en un mismo flush: sin esto, volver a guardar
            # un sector que ya existía viola uq_driver_day_zone_dir y la API responde 500.
            db.flush()

        plan.ida_time = day_in.ida_time
        plan.regreso_time = day_in.regreso_time

        seen: set[tuple] = set()
        _add_sectors_from_texts(db, plan, day_in.ida_sector_texts, TripDirection.ida, seen)
        _add_sectors_from_texts(db, plan, day_in.regreso_sector_texts, TripDirection.regreso, seen)

        if day_in.ida_time is not None and profile.home_zone_id not in {z for z, d in seen if d == TripDirection.ida}:
            db.add(
                DriverDayZone(
                    day_plan_id=plan.id,
                    zone_id=profile.home_zone_id,
                    direction=TripDirection.ida,
                )
            )

    db.commit()
    return _load_schedule(db, driver.id)
