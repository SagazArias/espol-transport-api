"""Pruebas de punta a punta contra PostgreSQL: auth, horario del conductor, búsqueda y ciclo de una reserva."""
from __future__ import annotations

import pytest

from app.password_policy import validate_password_strength

SCHEDULE = {
    "home_sector_text": "Mucho Lote 2",
    "seat_capacity": 3,
    "trip_fare_usd": 2.0,
    "days": [
        {
            "weekday": w,
            "ida_time": "09:00:00",
            "regreso_time": "17:00:00",
            "ida_sector_texts": ["Mucho Lote 2", "La Joya"],
            "regreso_sector_texts": ["La Joya", "Mucho Lote 2"],
        }
        for w in range(5)
    ],
}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_catalogo_de_zonas_y_horarios(client):
    zonas = client.get("/zones").json()
    assert {"Mucho Lote 2", "La Joya"} <= {z["name"] for z in zonas}
    tiempos = client.get("/trip-times").json()
    assert tiempos["ida"] and tiempos["regreso"]


@pytest.mark.parametrize("pwd", ["corta1!", "sinmayuscula1!", "SINMINUSCULA1!", "SinNumero!!", "SinSimbolo123", "Con espacio1!"])
def test_politica_de_contrasena_rechaza(pwd):
    with pytest.raises(ValueError):
        validate_password_strength(pwd)


def test_pasajero_solo_con_correo_espol(client):
    r = client.post(
        "/auth/passenger/register",
        json={
            "first_name": "X",
            "last_name": "Y",
            "phone": "0990000003",
            "email": "alguien@gmail.com",
            "password": "Prueba#2026",
            "recovery_phrase": "clave-prueba",
        },
    )
    assert r.status_code == 422


def test_me_y_roles(client, driver, passenger):
    assert client.get("/auth/me", headers=driver["headers"]).json()["role"] == "driver"
    assert client.get("/auth/me", headers=passenger["headers"]).json()["role"] == "student"
    assert client.get("/auth/me").status_code == 401


def test_guardar_horario_dos_veces(client, driver):
    """Regresión: reemplazar los sectores de un día existente respondía 500 (uq_driver_day_zone_dir)."""
    for _ in range(2):
        r = client.put("/driver/weekly-schedule", json=SCHEDULE, headers=driver["headers"])
        assert r.status_code == 200, r.text

    dias = client.get("/driver/weekly-schedule", headers=driver["headers"]).json()["days"]
    assert len(dias) == 5
    assert {z["name"] for z in dias[0]["ida_sectors"]} == {"Mucho Lote 2", "La Joya"}
    assert {z["name"] for z in dias[0]["regreso_sectors"]} == {"Mucho Lote 2", "La Joya"}


def test_dia_vacio_borra_los_viajes(client, driver):
    client.put("/driver/weekly-schedule", json=SCHEDULE, headers=driver["headers"])
    vacio = {**SCHEDULE, "days": [{"weekday": 0, "ida_time": None, "regreso_time": None}]}
    r = client.put("/driver/weekly-schedule", json=vacio, headers=driver["headers"])
    assert r.status_code == 200, r.text
    lunes = next(d for d in r.json()["days"] if d["weekday"] == 0)
    assert lunes["ida_time"] is None and lunes["regreso_time"] is None
    assert lunes["ida_sectors"] == [] and lunes["regreso_sectors"] == []


def _buscar(client, passenger, weekday=1):
    r = client.post(
        "/matches/search",
        json={"direction": "ida", "home_sector_text": "La Joya", "weekday": weekday, "trip_time": "09:00:00"},
        headers=passenger["headers"],
    )
    assert r.status_code == 200, r.text
    return r.json()["results"]


def _reservar(client, passenger, match):
    r = client.post(
        "/bookings",
        json={
            "driver_id": match["driver_id"],
            "weekday": match["weekday"],
            "direction": match["direction"],
            "trip_time": match["trip_time"],
            "home_sector_text": "La Joya",
        },
        headers=passenger["headers"],
    )
    assert r.status_code == 201, r.text


def _de(client, driver, results):
    """El resultado de esta conductora (otras pruebas crean conductoras con el mismo nombre)."""
    driver_id = client.get("/auth/me", headers=driver["headers"]).json()["id"]
    return next(m for m in results if m["driver_id"] == driver_id)


def test_reservar_concluir_y_calificar(client, driver, passenger):
    client.put("/driver/weekly-schedule", json=SCHEDULE, headers=driver["headers"])
    match = _de(client, driver, _buscar(client, passenger))
    assert match["available_seats"] == 3
    _reservar(client, passenger, match)

    viaje = client.get("/bookings/inbox", headers=passenger["headers"]).json()["trips"][0]
    assert any(t["id"] == viaje["id"] for t in client.get("/bookings/inbox", headers=driver["headers"]).json()["trips"])

    fin = client.post(f"/bookings/{viaje['id']}/complete", headers=passenger["headers"])
    assert fin.status_code == 200, fin.text
    assert fin.json()["prompt_passenger_rating"] is True

    r = client.post(f"/bookings/{viaje['id']}/rate", json={"stars": 5}, headers=passenger["headers"])
    assert r.status_code == 200, r.text

    calificado = _de(client, driver, _buscar(client, passenger))
    assert calificado["driver_rating_count"] >= 1
    assert calificado["driver_rating_avg"] == pytest.approx(5.0)


def test_cancelar_con_motivo(client, driver, passenger):
    client.put("/driver/weekly-schedule", json=SCHEDULE, headers=driver["headers"])
    _reservar(client, passenger, _de(client, driver, _buscar(client, passenger, weekday=2)))
    viaje = client.get("/bookings/inbox", headers=passenger["headers"]).json()["trips"][0]

    r = client.post(f"/bookings/{viaje['id']}/cancel", json={"reason": "Cambio de planes"}, headers=passenger["headers"])
    assert r.status_code == 200, r.text
    assert all(t["id"] != viaje["id"] for t in r.json()["trips"])
