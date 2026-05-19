from datetime import time
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_match_access
from app.matchmaking import match_routes
from app.models import User
from app.passenger_matching import search_passenger_matches
from app.schemas import (
    MatchQuery,
    MatchResult,
    PassengerMatchResponse,
    PassengerMatchSearch,
)

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/legacy", response_model=list[MatchResult])
def get_matches_legacy(
    origin_zone_id: UUID,
    desired_arrival_at_espol: time,
    weekday: int,
    tolerance_minutes: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_match_access),
) -> list[MatchResult]:
    q = MatchQuery(
        origin_zone_id=origin_zone_id,
        desired_arrival_at_espol=desired_arrival_at_espol,
        weekday=weekday,
        tolerance_minutes=tolerance_minutes,
    )
    return match_routes(db, q)


@router.post("/search", response_model=PassengerMatchResponse)
def search_matches(
    body: PassengerMatchSearch,
    db: Session = Depends(get_db),
    _: User = Depends(require_match_access),
) -> PassengerMatchResponse:
    results, message = search_passenger_matches(db, body)
    return PassengerMatchResponse(results=results, message=message)
