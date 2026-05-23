from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.booking_capacity import count_active_driver_bookings
from app.database import get_db
from app.deps import get_current_user, require_match_access
from app.models import (
    BookingStatus,
    DriverRating,
    DriverWeeklyProfile,
    InboxAlert,
    TripBooking,
    TripDirection,
    User,
    UserRole,
    Vehicle,
)
from app.schemas import (
    InboxAlertOut,
    InboxOut,
    TripBookingCancelIn,
    TripBookingCompleteOut,
    TripBookingCreate,
    TripBookingOut,
    TripBookingRateIn,
    TripBookingRateOut,
    TripInboxItemOut,
    utc_now,
)
from app.weekday_labels import weekday_name
from app.zone_matching import resolve_zone_id

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _passenger_name_parts(passenger: User | None) -> tuple[str, str]:
    if passenger is None:
        return "", ""
    first = (passenger.first_name or "").strip()
    last = (passenger.last_name or "").strip()
    if not first and not last and passenger.full_name:
        parts = passenger.full_name.strip().split(None, 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
    return first, last


def _route_summary(weekday: int, direction: TripDirection, trip_time, zone_name: str) -> str:
    dir_label = "Ida hacia ESPOL" if direction == TripDirection.ida else "Regreso a casa"
    return f"{dir_label} · {weekday_name(weekday)} {trip_time.strftime('%H:%M')} · {zone_name}"


def _booking_to_out(db: Session, booking: TripBooking) -> TripBookingOut:
    passenger = booking.passenger or db.get(User, booking.passenger_id)
    zone = booking.home_zone
    if zone is None:
        from app.models import Zone

        zone = db.get(Zone, booking.home_zone_id)
    summary = _route_summary(booking.weekday, booking.direction, booking.trip_time, zone.name if zone else "")
    p_first, p_last = _passenger_name_parts(passenger)
    return TripBookingOut(
        id=booking.id,
        passenger_first_name=p_first,
        passenger_last_name=p_last,
        passenger_phone=passenger.phone if passenger else None,
        weekday=booking.weekday,
        direction=booking.direction,
        trip_time=booking.trip_time,
        home_zone_name=zone.name if zone else "",
        route_summary=summary,
        trip_fare_usd=float(booking.trip_fare_usd),
        created_at=booking.created_at,
        read_by_driver=booking.driver_read_at is not None,
        notification_message=(
            f"Pasajero {p_first} {p_last} agendó un viaje: {summary} "
            f"({'tel. ' + passenger.phone if passenger and passenger.phone else 'sin teléfono'})"
        ),
    )


def _inbox_trip_item(db: Session, booking: TripBooking, viewer: User) -> TripInboxItemOut:
    passenger = booking.passenger or db.get(User, booking.passenger_id)
    driver = booking.driver or db.get(User, booking.driver_id)
    zone = booking.home_zone
    if zone is None:
        from app.models import Zone

        zone = db.get(Zone, booking.home_zone_id)
    is_driver = viewer.role == UserRole.driver
    vehicle = None
    if is_driver:
        vehicle = db.execute(select(Vehicle).where(Vehicle.owner_id == driver.id).limit(1)).scalar_one_or_none()
        counterparty = passenger
    else:
        vehicle = db.execute(select(Vehicle).where(Vehicle.owner_id == driver.id).limit(1)).scalar_one_or_none()
        counterparty = driver

    summary = _route_summary(booking.weekday, booking.direction, booking.trip_time, zone.name if zone else "")
    return TripInboxItemOut(
        id=booking.id,
        weekday=booking.weekday,
        direction=booking.direction,
        trip_time=booking.trip_time,
        home_zone_name=zone.name if zone else "",
        route_summary=summary,
        trip_fare_usd=float(booking.trip_fare_usd),
        created_at=booking.created_at,
        counterparty_name=counterparty.full_name if counterparty else "",
        counterparty_phone=counterparty.phone if counterparty else None,
        vehicle_plate=vehicle.plate if vehicle else None,
        vehicle_brand=vehicle.brand if vehicle else None,
        vehicle_model=vehicle.model if vehicle else None,
        is_driver_view=is_driver,
    )


@router.get("/inbox", response_model=InboxOut)
def get_inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InboxOut:
    if user.role == UserRole.student:
        trip_filter = TripBooking.passenger_id == user.id
    else:
        trip_filter = TripBooking.driver_id == user.id

    trips = db.execute(
        select(TripBooking)
        .where(trip_filter, TripBooking.status == BookingStatus.active)
        .options(
            joinedload(TripBooking.passenger),
            joinedload(TripBooking.driver),
            joinedload(TripBooking.home_zone),
        )
        .order_by(TripBooking.created_at.desc())
    ).unique().scalars().all()

    alerts = db.execute(
        select(InboxAlert)
        .where(InboxAlert.recipient_id == user.id, InboxAlert.read_at.is_(None))
        .order_by(InboxAlert.created_at.desc())
        .limit(20)
    ).scalars().all()

    for alert in alerts:
        alert.read_at = utc_now()
    if alerts:
        db.commit()

    return InboxOut(
        trips=[_inbox_trip_item(db, b, user) for b in trips],
        alerts=[InboxAlertOut(id=a.id, message=a.message, created_at=a.created_at) for a in alerts],
    )


@router.post("", response_model=TripBookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    body: TripBookingCreate,
    db: Session = Depends(get_db),
    passenger: User = Depends(require_match_access),
) -> TripBooking:
    if passenger.role != UserRole.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo pasajeros pueden agendar viajes.")

    driver = db.get(User, body.driver_id)
    if driver is None or driver.role != UserRole.driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")

    zone_id = resolve_zone_id(db, body.home_sector_text)
    if zone_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sector no reconocido.")

    profile = db.execute(
        select(DriverWeeklyProfile).where(DriverWeeklyProfile.driver_id == driver.id)
    ).scalar_one_or_none()
    seat_capacity = profile.seat_capacity if profile else 3
    active_count = count_active_driver_bookings(db, driver.id)
    if active_count >= seat_capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este conductor ya no tiene cupos disponibles.",
        )
    fare = profile.trip_fare_usd if profile else 1.50

    booking = TripBooking(
        passenger_id=passenger.id,
        driver_id=body.driver_id,
        weekday=body.weekday,
        direction=body.direction,
        trip_time=body.trip_time,
        home_zone_id=zone_id,
        trip_fare_usd=fare,
        status=BookingStatus.active,
        driver_read_at=None,
        created_at=utc_now(),
    )
    db.add(booking)
    db.flush()

    from app.models import Zone as ZoneModel

    z = db.get(ZoneModel, zone_id)
    summary = _route_summary(body.weekday, body.direction, body.trip_time, z.name if z else "")

    p_first, p_last = _passenger_name_parts(passenger)
    db.add(
        InboxAlert(
            recipient_id=driver.id,
            booking_id=booking.id,
            message=(
                f"Nuevo viaje agendado — Pasajero: {p_first} {p_last}. "
                f"Ruta: {summary}. Tel: {passenger.phone or 'no indicado'}."
            ),
            created_at=utc_now(),
        )
    )
    db.commit()
    db.refresh(booking)
    return _booking_to_out(db, booking)


@router.post("/{booking_id}/cancel", response_model=InboxOut)
def cancel_booking(
    booking_id: UUID,
    body: TripBookingCancelIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InboxOut:
    booking = db.execute(
        select(TripBooking)
        .where(TripBooking.id == booking_id, TripBooking.status == BookingStatus.active)
        .options(joinedload(TripBooking.passenger), joinedload(TripBooking.driver), joinedload(TripBooking.home_zone))
    ).scalar_one_or_none()

    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado o ya cancelado.")

    if user.id not in (booking.passenger_id, booking.driver_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes cancelar este viaje.")

    now = utc_now()
    booking.status = BookingStatus.cancelled
    booking.cancelled_at = now
    booking.cancelled_by_id = user.id
    booking.cancellation_reason = body.reason.strip()

    zone_name = booking.home_zone.name if booking.home_zone else ""
    summary = _route_summary(booking.weekday, booking.direction, booking.trip_time, zone_name)
    canceller_name = user.full_name

    if user.id == booking.passenger_id:
        recipient_id = booking.driver_id
        other_label = "El pasajero"
    else:
        recipient_id = booking.passenger_id
        other_label = "El conductor"

    db.add(
        InboxAlert(
            recipient_id=recipient_id,
            booking_id=booking.id,
            message=(
                f"{other_label} {canceller_name} canceló el viaje ({summary}). "
                f"Motivo: {booking.cancellation_reason}"
            ),
            created_at=now,
        )
    )
    db.commit()
    return get_inbox(db=db, user=user)


@router.post("/{booking_id}/complete", response_model=TripBookingCompleteOut)
def complete_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TripBookingCompleteOut:
    booking = db.execute(
        select(TripBooking)
        .where(TripBooking.id == booking_id, TripBooking.status == BookingStatus.active)
        .options(joinedload(TripBooking.passenger), joinedload(TripBooking.driver), joinedload(TripBooking.home_zone))
    ).scalar_one_or_none()

    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado o ya finalizado.")

    if user.id not in (booking.passenger_id, booking.driver_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes finalizar este viaje.")

    now = utc_now()
    booking.status = BookingStatus.completed
    booking.completed_at = now

    zone_name = booking.home_zone.name if booking.home_zone else ""
    summary = _route_summary(booking.weekday, booking.direction, booking.trip_time, zone_name)
    completer_name = user.full_name

    if user.id == booking.passenger_id:
        recipient_id = booking.driver_id
        other_label = "El pasajero"
    else:
        recipient_id = booking.passenger_id
        other_label = "El conductor"

    db.add(
        InboxAlert(
            recipient_id=recipient_id,
            booking_id=booking.id,
            message=f"{other_label} {completer_name} marcó como concluido el viaje ({summary}).",
            created_at=now,
        )
    )
    db.commit()

    prompt_rating = user.role == UserRole.student and user.id == booking.passenger_id
    return TripBookingCompleteOut(
        inbox=get_inbox(db=db, user=user),
        prompt_passenger_rating=prompt_rating,
        driver_id=booking.driver_id if prompt_rating else None,
        booking_id=booking.id,
    )


@router.post("/{booking_id}/rate", response_model=TripBookingRateOut)
def rate_driver_after_trip(
    booking_id: UUID,
    body: TripBookingRateIn,
    db: Session = Depends(get_db),
    passenger: User = Depends(get_current_user),
) -> TripBookingRateOut:
    if passenger.role != UserRole.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo pasajeros pueden calificar.")

    booking = db.execute(
        select(TripBooking).where(
            TripBooking.id == booking_id,
            TripBooking.passenger_id == passenger.id,
            TripBooking.status == BookingStatus.completed,
        )
    ).scalar_one_or_none()
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede calificar este viaje.",
        )

    existing = db.execute(
        select(DriverRating.id).where(DriverRating.booking_id == booking_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya calificaste este viaje.")

    db.add(
        DriverRating(
            booking_id=booking.id,
            passenger_id=passenger.id,
            driver_id=booking.driver_id,
            stars=body.stars,
            created_at=utc_now(),
        )
    )
    db.commit()
    return TripBookingRateOut()


@router.get("/driver/notifications", response_model=list[TripBookingOut])
def driver_notifications(
    db: Session = Depends(get_db),
    driver: User = Depends(get_current_user),
) -> list[TripBookingOut]:
    if driver.role != UserRole.driver:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores.")
    rows = db.execute(
        select(TripBooking)
        .where(TripBooking.driver_id == driver.id, TripBooking.status == BookingStatus.active)
        .options(joinedload(TripBooking.passenger), joinedload(TripBooking.home_zone))
        .order_by(TripBooking.created_at.desc())
        .limit(50)
    ).unique().scalars().all()
    return [_booking_to_out(db, b) for b in rows]
