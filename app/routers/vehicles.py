from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_driver
from app.models import User, Vehicle
from app.schemas import VehicleCreate, VehicleOut, utc_now

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("", response_model=VehicleOut)
def create_vehicle(
    body: VehicleCreate,
    db: Session = Depends(get_db),
    driver: User = Depends(require_driver),
) -> Vehicle:
    v = Vehicle(
        owner_id=driver.id,
        plate=body.plate.strip(),
        brand=body.brand.strip(),
        model=body.model.strip(),
        created_at=utc_now(),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.get("", response_model=list[VehicleOut])
def list_my_vehicles(db: Session = Depends(get_db), driver: User = Depends(require_driver)) -> list[Vehicle]:
    rows = db.execute(select(Vehicle).where(Vehicle.owner_id == driver.id).order_by(Vehicle.created_at.desc())).scalars().all()
    return list(rows)
