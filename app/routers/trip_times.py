from fastapi import APIRouter

from app.fare_utils import ALLOWED_FARES_USD
from app.schemas import AllowedFaresOut, TripTimesOut
from app.trip_times import IDA_TIMES, REGRESO_TIMES

router = APIRouter(prefix="/trip-times", tags=["trip-times"])


@router.get("", response_model=TripTimesOut)
def list_trip_times() -> TripTimesOut:
    return TripTimesOut(
        ida=[t.strftime("%H:%M") for t in IDA_TIMES],
        regreso=[t.strftime("%H:%M") for t in REGRESO_TIMES],
    )


@router.get("/fares", response_model=AllowedFaresOut)
def list_allowed_fares() -> AllowedFaresOut:
    return AllowedFaresOut(fares_usd=[float(f) for f in ALLOWED_FARES_USD])
