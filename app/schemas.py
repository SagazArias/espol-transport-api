from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator, model_validator

from app.fare_utils import parse_and_validate_fare
from app.models import BookingStatus, TripDirection, UserRole
from app.password_policy import validate_password_strength
from app.recovery_phrase_policy import validate_recovery_phrase


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    role: UserRole = UserRole.student
    captcha_token: str | None = None

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    captcha_token: str | None = None


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    espol_verified_at: Optional[datetime] = None
    role: UserRole

    model_config = {"from_attributes": True}

    @computed_field
    def espol_student_verified(self) -> bool:
        return self.espol_verified_at is not None


class PassengerSendOtp(BaseModel):
    email: EmailStr
    captcha_token: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("email")
    @classmethod
    def must_be_espol_domain(cls, v: EmailStr) -> EmailStr:
        s = str(v).lower()
        if not s.endswith("@espol.edu.ec"):
            raise ValueError("El correo debe ser institucional (@espol.edu.ec)")
        return v


class PassengerRegister(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=8, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    recovery_phrase: str = Field(min_length=4, max_length=64)
    otp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    captcha_token: str | None = None

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("recovery_phrase")
    @classmethod
    def valid_recovery_phrase(cls, v: str) -> str:
        return validate_recovery_phrase(v)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("email")
    @classmethod
    def must_be_espol_domain(cls, v: EmailStr) -> EmailStr:
        s = str(v).lower()
        if not s.endswith("@espol.edu.ec"):
            raise ValueError("El correo debe ser institucional (@espol.edu.ec)")
        return v


class DriverRegister(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=8, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    recovery_phrase: str = Field(min_length=4, max_length=64)
    plate: str = Field(min_length=3, max_length=32)
    brand: str = Field(min_length=2, max_length=120)
    model: str = Field(min_length=1, max_length=120)
    captcha_token: str | None = None

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("recovery_phrase")
    @classmethod
    def valid_recovery_phrase(cls, v: str) -> str:
        return validate_recovery_phrase(v)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class PasswordRecoveryVerifyIn(BaseModel):
    email: EmailStr
    recovery_phrase: str = Field(min_length=4, max_length=64)
    captcha_token: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("recovery_phrase")
    @classmethod
    def valid_recovery_phrase(cls, v: str) -> str:
        return validate_recovery_phrase(v)


class PasswordRecoveryVerifyOut(BaseModel):
    reset_token: str
    expires_in_minutes: int


class PasswordRecoveryResetIn(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validate_password_strength(v)


class PasswordRecoveryResetOut(BaseModel):
    message: str = "Contraseña actualizada. Ya puedes iniciar sesión."


class OtpSentResponse(BaseModel):
    message: str = "Si el correo es válido, se envió un código de verificación."
    expires_in_minutes: int
    dev_code: Optional[str] = Field(
        default=None,
        description="Solo en desarrollo: código OTP para pruebas sin leer el correo.",
    )


class ZoneOut(BaseModel):
    id: UUID
    slug: str
    name: str
    is_espol_campus: bool

    model_config = {"from_attributes": True}


class VehicleCreate(BaseModel):
    plate: str = Field(min_length=3, max_length=32)
    brand: str = Field(min_length=2, max_length=120)
    model: str = Field(min_length=1, max_length=120)


class VehicleOut(BaseModel):
    id: UUID
    plate: str
    brand: str
    model: str

    model_config = {"from_attributes": True}


class RouteStopIn(BaseModel):
    zone_id: UUID
    leg_minutes_to_next: Optional[int] = Field(
        default=None,
        description="Minutes from this stop to the next. Null only for the last stop (ESPOL).",
    )


class PublishedRouteCreate(BaseModel):
    vehicle_id: UUID
    title: Optional[str] = None
    weekdays: list[int] = Field(min_length=1)
    target_arrival_at_espol: time
    estimate_window_minutes: int = Field(default=10, ge=0, le=120)
    stops: list[RouteStopIn] = Field(min_length=2)

    @field_validator("weekdays")
    @classmethod
    def weekdays_range(cls, v: list[int]) -> list[int]:
        for d in v:
            if d < 0 or d > 6:
                raise ValueError("weekdays must be 0=Monday .. 6=Sunday (Python weekday convention)")
        return sorted(set(v))

    @model_validator(mode="after")
    def validate_stops(self) -> "PublishedRouteCreate":
        if self.stops[-1].leg_minutes_to_next is not None:
            raise ValueError("Last stop must have leg_minutes_to_next = null")
        for s in self.stops[:-1]:
            if s.leg_minutes_to_next is None or s.leg_minutes_to_next < 0:
                raise ValueError("All non-final stops require leg_minutes_to_next >= 0")
        return self


class RouteStopOut(BaseModel):
    id: UUID
    sequence: int
    zone: ZoneOut
    leg_minutes_to_next: Optional[int]

    model_config = {"from_attributes": True}


class PublishedRouteOut(BaseModel):
    id: UUID
    title: Optional[str]
    active: bool
    weekdays: list[int]
    target_arrival_at_espol: time
    estimate_window_minutes: int
    vehicle: VehicleOut
    stops: list[RouteStopOut]
    driver: UserPublic

    model_config = {"from_attributes": True}


class MatchQuery(BaseModel):
    origin_zone_id: UUID
    desired_arrival_at_espol: time
    weekday: int = Field(ge=0, le=6, description="0=Monday .. 6=Sunday")
    tolerance_minutes: int = Field(default=20, ge=0, le=180)


class MatchResult(BaseModel):
    route: PublishedRouteOut
    origin_stop_sequence: int
    estimated_pickup_time_at_origin: time
    estimated_pickup_window_start: time
    estimated_pickup_window_end: time
    arrival_delta_minutes: int = Field(
        description="Signed difference: route ESPOL arrival vs student desired (negative = route earlier)."
    )


class TripTimesOut(BaseModel):
    ida: list[str]
    regreso: list[str]


class ZoneResolveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=255)


class ZoneResolveResponse(BaseModel):
    matched: Optional[ZoneOut] = None
    suggestions: list[ZoneOut] = Field(default_factory=list)


class DriverDayPlanIn(BaseModel):
    weekday: int = Field(ge=0, le=4, description="0=Lunes .. 4=Viernes")
    ida_time: Optional[time] = None
    regreso_time: Optional[time] = None
    ida_sector_texts: list[str] = Field(default_factory=list)
    regreso_sector_texts: list[str] = Field(default_factory=list)


class DriverWeeklyScheduleIn(BaseModel):
    home_sector_text: str = Field(min_length=1, max_length=255)
    seat_capacity: int = Field(ge=1, le=20, default=3)
    trip_fare_usd: float = Field(default=1.50, description="Tarifa en USD (1.00–2.50, pasos de 0.25)")
    days: list[DriverDayPlanIn] = Field(default_factory=list)

    @field_validator("trip_fare_usd")
    @classmethod
    def validate_fare(cls, v: float) -> float:
        return float(parse_and_validate_fare(v))


class DriverDayPlanOut(BaseModel):
    weekday: int
    ida_time: Optional[time] = None
    regreso_time: Optional[time] = None
    ida_sectors: list[ZoneOut] = Field(default_factory=list)
    regreso_sectors: list[ZoneOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DriverWeeklyScheduleOut(BaseModel):
    home_zone: Optional[ZoneOut] = None
    seat_capacity: int = 3
    trip_fare_usd: float = 1.50
    days: list[DriverDayPlanOut] = Field(default_factory=list)


class AllowedFaresOut(BaseModel):
    fares_usd: list[float]


class PassengerMatchSearch(BaseModel):
    direction: TripDirection
    home_sector_text: str = Field(min_length=1, max_length=255)
    weekday: int = Field(ge=0, le=4, description="0=Lunes .. 4=Viernes")
    trip_time: time
    tolerance_minutes: int = Field(default=20, ge=0, le=120)


class PassengerMatchResult(BaseModel):
    driver_id: UUID
    driver_name: str
    driver_first_name: str
    driver_last_name: str
    driver_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    matched_zone_name: str
    matched_route_summary: str
    weekday: int
    direction: TripDirection
    trip_time: time
    time_delta_minutes: int
    seat_capacity: int = 3
    available_seats: int = 0
    seats_full: bool = False
    driver_rating_avg: Optional[float] = None
    driver_rating_count: int = 0
    trip_fare_usd: float = 1.50
    ida_route_sectors: list[str] = Field(default_factory=list)
    regreso_route_sectors: list[str] = Field(default_factory=list)


class PassengerMatchResponse(BaseModel):
    results: list[PassengerMatchResult] = Field(default_factory=list)
    message: Optional[str] = None


class TripBookingCreate(BaseModel):
    driver_id: UUID
    weekday: int = Field(ge=0, le=4)
    direction: TripDirection
    trip_time: time
    home_sector_text: str = Field(min_length=1, max_length=255)


class TripBookingOut(BaseModel):
    id: UUID
    passenger_first_name: str
    passenger_last_name: str
    passenger_phone: Optional[str] = None
    weekday: int
    direction: TripDirection
    trip_time: time
    home_zone_name: str
    route_summary: str
    trip_fare_usd: float = 1.50
    created_at: datetime
    read_by_driver: bool
    notification_message: str


class TripInboxItemOut(BaseModel):
    id: UUID
    weekday: int
    direction: TripDirection
    trip_time: time
    home_zone_name: str
    route_summary: str
    trip_fare_usd: float
    created_at: datetime
    counterparty_name: str
    counterparty_phone: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_brand: Optional[str] = None
    vehicle_model: Optional[str] = None
    is_driver_view: bool


class InboxAlertOut(BaseModel):
    id: UUID
    message: str
    created_at: datetime


class InboxOut(BaseModel):
    trips: list[TripInboxItemOut] = Field(default_factory=list)
    alerts: list[InboxAlertOut] = Field(default_factory=list)


class TripBookingCancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class TripBookingCompleteOut(BaseModel):
    inbox: InboxOut
    prompt_passenger_rating: bool = False
    driver_id: Optional[UUID] = None
    booking_id: UUID


class TripBookingRateIn(BaseModel):
    stars: int = Field(ge=1, le=5)


class TripBookingRateOut(BaseModel):
    message: str = "Calificación registrada."


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
