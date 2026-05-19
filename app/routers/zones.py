from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Zone
from app.schemas import ZoneOut, ZoneResolveRequest, ZoneResolveResponse
from app.zone_matching import resolve_zone_or_suggestions

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("", response_model=list[ZoneOut])
def list_zones(db: Session = Depends(get_db)) -> list[Zone]:
    rows = db.execute(select(Zone).where(Zone.is_espol_campus.is_(False)).order_by(Zone.name)).scalars().all()
    return list(rows)


@router.post("/resolve", response_model=ZoneResolveResponse)
def resolve_zone_text(body: ZoneResolveRequest, db: Session = Depends(get_db)) -> ZoneResolveResponse:
    matched, suggestions = resolve_zone_or_suggestions(db, body.text)
    return ZoneResolveResponse(
        matched=ZoneOut.model_validate(matched) if matched else None,
        suggestions=[ZoneOut.model_validate(z) for z in suggestions],
    )
