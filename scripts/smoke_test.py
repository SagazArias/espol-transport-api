"""Prueba rápida: DB + hash de contraseña + registro conductor."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import init_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password, verify_password  # noqa: E402


def main() -> None:
    pwd = "Smoke#1234"
    phrase = "mi-clave-recuperacion"
    print("1) Hash bcrypt...")
    h = hash_password(pwd)
    assert verify_password(pwd, h)
    print("   OK")

    print("2) Conexión DB + registro conductor de prueba...")
    init_engine(settings.database_url)
    client = TestClient(app)
    email = "smoke.driver@example.com"
    r = client.post(
        "/auth/driver/register",
        json={
            "first_name": "Smoke",
            "last_name": "Test",
            "phone": "0999999999",
            "email": email,
            "password": pwd,
            "recovery_phrase": phrase,
            "plate": "TST001",
            "brand": "Test",
            "model": "Car",
        },
    )
    print(f"   HTTP {r.status_code}")
    if r.status_code not in (200, 409):
        print(r.text)
        sys.exit(1)
    print("   OK — reinicia uvicorn y prueba la app Android.")


if __name__ == "__main__":
    main()
