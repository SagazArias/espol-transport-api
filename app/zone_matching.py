import re
import unicodedata
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Zone


def normalize_sector_text(text: str) -> str:
    s = text.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _score_zone(query: str, zone: Zone) -> int:
    if not query:
        return 0
    slug = normalize_sector_text(zone.slug.replace("-", " "))
    name = normalize_sector_text(zone.name)
    if query == slug or query == name:
        return 100
    if query in slug or query in name or slug in query or name in query:
        return 80
    q_tokens = set(query.split())
    z_tokens = set(slug.split()) | set(name.split())
    overlap = len(q_tokens & z_tokens)
    if overlap > 0:
        return 50 + overlap * 10
    return 0


def list_residential_zones(db: Session) -> list[Zone]:
    rows = db.execute(select(Zone).where(Zone.is_espol_campus.is_(False)).order_by(Zone.name)).scalars().all()
    return list(rows)


def resolve_zone(db: Session, text: str) -> Zone | None:
    query = normalize_sector_text(text)
    if not query:
        return None
    zones = list_residential_zones(db)
    best: Zone | None = None
    best_score = 0
    for zone in zones:
        score = _score_zone(query, zone)
        if score > best_score:
            best_score = score
            best = zone
    return best if best_score >= 50 else None


def resolve_zone_or_suggestions(db: Session, text: str, limit: int = 5) -> tuple[Zone | None, list[Zone]]:
    query = normalize_sector_text(text)
    zones = list_residential_zones(db)
    if not query:
        return None, zones[:limit]
    ranked = sorted(zones, key=lambda z: _score_zone(query, z), reverse=True)
    if ranked and _score_zone(query, ranked[0]) >= 50:
        return ranked[0], ranked[:limit]
    return None, ranked[:limit]


def resolve_zone_id(db: Session, text: str) -> UUID | None:
    z = resolve_zone(db, text)
    return z.id if z else None
