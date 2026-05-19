import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import app.models  # noqa: F401  # register ORM models

from app.config import settings
from app.database import init_engine
from app.rate_limit import limiter
from app.routers import auth, bookings, driver_schedule, match, published_routes, trip_times, vehicles, zones

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_engine(settings.database_url)
    yield


app = FastAPI(title="ESPOL Transport API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if settings.force_https_redirect:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto != "https":
            url = request.url.replace(scheme="https")
            return RedirectResponse(str(url), status_code=301)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.app_environment.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    detail = str(exc) if settings.expose_api_errors else "Error interno del servidor"
    return JSONResponse(status_code=500, content={"detail": detail})


app.include_router(auth.router)
app.include_router(zones.router)
app.include_router(vehicles.router)
app.include_router(published_routes.router)
app.include_router(match.router)
app.include_router(driver_schedule.router)
app.include_router(trip_times.router)
app.include_router(bookings.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_environment}
