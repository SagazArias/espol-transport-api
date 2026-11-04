"""Fixtures de pruebas: una base PostgreSQL real con las migraciones aplicadas.

Usa TEST_DATABASE_URL (por defecto un Postgres local en el puerto 55432; el CI levanta uno igual).
La base se recrea vacía en cada corrida, así que nunca apuntes esto a datos reales.
"""
from __future__ import annotations

import os
import uuid

import pytest

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://espol:espol_dev@localhost:55432/espol_test",
)
# Debe fijarse antes de importar la app: settings se lee al importar.
os.environ["DATABASE_URL"] = TEST_DB
os.environ.setdefault("RECAPTCHA_SECRET_KEY", "")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.main import app  # noqa: E402
from app.rate_limit import limiter  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Prueba#2026"


@pytest.fixture(scope="session", autouse=True)
def _database():
    engine = create_engine(TEST_DB)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    engine.dispose()
    command.upgrade(Config(os.path.join(ROOT, "alembic.ini")), "head")
    yield


@pytest.fixture(scope="session")
def client():
    limiter.enabled = False  # los límites por minuto bloquearían la suite
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def driver(client):
    email = f"conductor.{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/auth/driver/register",
        json={
            "first_name": "Ana",
            "last_name": "Conductora",
            "phone": "0990000001",
            "email": email,
            "password": PASSWORD,
            "recovery_phrase": "clave-prueba",
            "plate": "PRB1234",
            "brand": "Kia",
            "model": "Rio",
        },
    )
    assert r.status_code == 200, r.text
    return {"email": email, "headers": _login(client, email)}


@pytest.fixture
def passenger(client):
    email = f"pasajero.{uuid.uuid4().hex[:8]}@espol.edu.ec"
    r = client.post(
        "/auth/passenger/register",
        json={
            "first_name": "Luis",
            "last_name": "Pasajero",
            "phone": "0990000002",
            "email": email,
            "password": PASSWORD,
            "recovery_phrase": "clave-prueba",
        },
    )
    assert r.status_code == 200, r.text
    return {"email": email, "headers": _login(client, email)}
