# ESPOL Transport API

API REST del sistema de **carpooling para estudiantes de la ESPOL** (Guayaquil, Ecuador). Conecta a conductores que viajan hacia o desde el campus con pasajeros de su misma zona. La consume la app Android [`espol-transport-android`](https://github.com/SagazArias/espol-transport-android).

[![CI](https://github.com/SagazArias/espol-transport-api/actions/workflows/ci.yml/badge.svg)](https://github.com/SagazArias/espol-transport-api/actions/workflows/ci.yml)

**API en vivo:** [documentación interactiva (Swagger)](https://espol-transport.onrender.com/docs) · [ReDoc](https://espol-transport.onrender.com/redoc). Está en el plan gratuito de Render, así que la primera petición puede tardar 30–60 s mientras el servidor despierta.

| Documentación en vivo (Swagger) | La app que la consume |
|---|---|
| <a href="https://espol-transport.onrender.com/docs"><img src="docs/capturas/swagger.webp" alt="Swagger de la API con los endpoints de auth y zonas" width="480"></a> | <img src="https://raw.githubusercontent.com/SagazArias/espol-transport-android/main/docs/capturas/resultados.webp" alt="Resultado de búsqueda en la app Android" width="150"> <img src="https://raw.githubusercontent.com/SagazArias/espol-transport-android/main/docs/capturas/horario.webp" alt="Horario del conductor en la app Android" width="150"> |

## Problema

Muchos estudiantes hacen a diario el mismo trayecto hacia la ESPOL, y muchos van en carro con asientos vacíos. Esta API organiza ese transporte: el conductor publica su horario semanal y las zonas por las que pasa, el pasajero busca por sector y hora, reserva un asiento con una tarifa fija y, al terminar el viaje, califica al conductor.

## Funcionalidades

- **Registro por rol**: los pasajeros solo pueden registrarse con un correo `@espol.edu.ec`. Los conductores se registran junto con su vehículo.
- **Login con JWT**, consulta de perfil y **eliminación de cuenta** con confirmación por contraseña.
- **Recuperación de contraseña con una palabra clave** que el usuario define al registrarse. No usa correo.
- **Horario semanal del conductor**: para cada día, la hora, la dirección (ida o regreso) y los sectores que cubre.
- **Rutas publicadas** con paradas ordenadas. La última parada siempre es el campus ESPOL.
- **Matching de pasajeros**: el sector escrito por el pasajero se resuelve a una zona y se cruza con los horarios de los conductores. Los resultados se ordenan por reputación.
- **Reservas** con control de cupos, cancelación, cierre del viaje y calificación al conductor.
- **Bandeja de avisos** (inbox) para pasajeros y conductores, por ejemplo cuando se cancela una reserva.
- **Tarifas fijas** permitidas: $1.00 a $2.50, en pasos de $0.25 (`app/fare_utils.py`).

## Stack

| Componente | Versión |
|---|---|
| Python | 3.11+ |
| FastAPI | 0.115.6 |
| Uvicorn | 0.32.1 |
| SQLAlchemy | 2.0.x |
| PostgreSQL | 16 (Docker `postgres:16-alpine`) |
| psycopg | 3.3.4 |
| Alembic | 1.14.0 |
| Pydantic / pydantic-settings | 2.x |
| python-jose (JWT) | 3.3.0 |
| bcrypt | 4.1+ |
| slowapi (rate limiting) | 0.1.9 |
| httpx (reCAPTCHA, TestClient) | 0.28.1 |

## Arquitectura

```
[App Android] --HTTPS/JSON--> [FastAPI]
                                 ├─ routers/       (capa HTTP, validación con Pydantic)
                                 ├─ módulos de dominio (matchmaking, cupos, tarifas, ratings…)
                                 ├─ seguridad (JWT, bcrypt, bloqueos, rate limit, reCAPTCHA)
                                 └─ SQLAlchemy ORM ──> PostgreSQL (migraciones con Alembic)
```

- La configuración se lee de `.env` con `pydantic-settings` (`app/config.py`). Cuando `APP_ENVIRONMENT=production`, la API exige un `JWT_SECRET` propio, oculta los errores internos y limita la duración del token a 12 h.
- Un middleware añade las cabeceras `X-Content-Type-Options`, `X-Frame-Options` y `Referrer-Policy`, y también HSTS en producción. Si se activa, redirige a HTTPS usando `X-Forwarded-Proto`.
- Un manejador global de excepciones devuelve un 500 genérico cuando `EXPOSE_API_ERRORS=false`.

### Modelo de datos

| Entidad (tabla) | Propósito |
|---|---|
| `users` | Pasajeros y conductores (`role`), con hash de contraseña y de palabra clave de recuperación |
| `vehicles` | Vehículo del conductor (placa, marca…) |
| `zones` | Sectores de la ciudad. Uno de ellos está marcado como campus ESPOL (`is_espol_campus`). Se cargan en la migración inicial |
| `published_routes` / `route_stops` | Rutas publicadas y sus paradas ordenadas, con los minutos hasta la siguiente parada |
| `driver_weekly_profiles` / `driver_day_plans` / `driver_day_zones` | Horario semanal del conductor: plan por día y sectores por dirección (`TripDirection`) |
| `trip_bookings` | Reservas de pasajeros, con estado (`BookingStatus`) y tarifa |
| `driver_ratings` | Calificaciones a conductores tras un viaje completado |
| `inbox_alerts` | Avisos para la bandeja de entrada |
| `login_lockouts` | Intentos fallidos de login y bloqueo temporal |
| `password_recovery_lockouts` / `password_recovery_logs` | Bloqueo y auditoría (incluida la IP) de los intentos de recuperación |

## Endpoints principales

Documentación interactiva en `/docs` (Swagger) y `/redoc`; en producción: [espol-transport.onrender.com/docs](https://espol-transport.onrender.com/docs).

| Router | Método y ruta | Descripción |
|---|---|---|
| — | `GET /health` | Estado y entorno |
| auth | `POST /auth/passenger/register` | Registro de pasajero (`@espol.edu.ec`) · 8/min |
| auth | `POST /auth/driver/register` | Registro de conductor y su vehículo · 8/min |
| auth | `POST /auth/register` | Registro genérico · 8/min |
| auth | `POST /auth/login` | Devuelve un JWT · 12/min |
| auth | `GET /auth/me` · `DELETE /auth/me` | Perfil y eliminación de cuenta con contraseña · 5/min |
| auth | `POST /auth/password-recovery/verify` | Valida la palabra clave y emite un token de reseteo · 8/min |
| auth | `POST /auth/password-recovery/reset` | Cambia la contraseña con ese token · 8/min |
| zones | `GET /zones` · `POST /zones/resolve` | Lista las zonas y resuelve un texto libre a una zona |
| vehicles | `GET /vehicles` · `POST /vehicles` | Vehículos del conductor |
| published-routes | `POST /published-routes` · `GET /published-routes/mine` · `GET /published-routes/{id}` | Rutas del conductor |
| driver-schedule | `GET /driver/weekly-schedule` · `PUT /driver/weekly-schedule` | Horario semanal |
| matches | `POST /matches/search` | Busca conductores para un pasajero |
| matches | `GET /matches/legacy` | Matching anterior, basado en rutas publicadas |
| trip-times | `GET /trip-times` · `GET /trip-times/fares` | Horarios y tarifas permitidas |
| bookings | `POST /bookings` | Crea una reserva y valida los cupos |
| bookings | `GET /bookings/inbox` | Bandeja de avisos |
| bookings | `POST /bookings/{id}/cancel` · `/complete` · `/rate` | Cancelar, completar y calificar |
| bookings | `GET /bookings/driver/notifications` | Reservas recibidas por el conductor |

## Seguridad

| Riesgo | Medida |
|---|---|
| Robo de credenciales | Las contraseñas se guardan con **bcrypt (12 rounds)**. Nunca se almacenan en texto plano |
| Sesiones | **JWT HS256** con expiración configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`, máximo 12 h en producción). El token de reseteo es distinto y dura 15 min |
| Fuerza bruta | **Rate limit por IP** (slowapi) y **bloqueo de login** tras 5 intentos fallidos durante 15 min (`login_lockouts`) |
| Contraseñas débiles | Política en `app/password_policy.py`: 8 o más caracteres, mayúscula, minúscula, número y símbolo, sin espacios |
| Recuperación | La **palabra clave** se guarda con bcrypt y es distinta de la contraseña. Admite 5 intentos con cooldown, y cada intento queda registrado con su IP |
| Bots | Verificación opcional con **reCAPTCHA** (`RECAPTCHA_SECRET_KEY`, umbral `RECAPTCHA_MIN_SCORE`) |
| IDOR | Cada recurso se filtra por el usuario autenticado |
| Cuentas duplicadas | Un correo corresponde a una cuenta (responde 409). Eliminar la cuenta libera el correo |
| Fuga de información | `EXPOSE_API_ERRORS=false` en producción, cabeceras de seguridad y HSTS |

Detalle en [SEGURIDAD.md](SEGURIDAD.md).

## Cómo se construyó

El esquema evolucionó en **10 migraciones Alembic** (`alembic/versions/`):

| # | Cambio |
|---|---|
| 0001 | Esquema inicial y carga de las zonas |
| 0002 | Registro por rol y verificación OTP por correo |
| 0003 | Se elimina `provider_type` |
| 0004 | Horarios semanales del conductor |
| 0005 | Cupos, rutas y reservas |
| 0006 | Tarifa, cancelación y bandeja de avisos |
| 0007 | Bloqueo de login |
| 0008 | Viajes completados y calificaciones |
| 0009 | Frase de recuperación |
| 0010 | Se elimina la tabla `student_email_otps` (fin del OTP) |

Decisiones relevantes:

- **Se eliminó el OTP por correo.** Al principio los pasajeros verificaban un código de 6 dígitos enviado por SMTP. Se reemplazó por una validación del dominio `@espol.edu.ec` y una palabra clave de recuperación, para no depender de un proveedor de correo. Por eso [OTP_SMTP_RENDER.md](OTP_SMTP_RENDER.md) se conserva solo como **registro histórico**.
- **`bcrypt` directo en lugar de passlib**, porque passlib 1.7.4 falla con bcrypt 4.1 o superior.
- **Tarifas en `Decimal`** con una lista cerrada de valores, para evitar errores de redondeo y precios arbitrarios.
- **Matching por zonas** en lugar de geolocalización. Es más simple y suficiente para trayectos que siempre empiezan o terminan en el campus.

## Ejecución local

Requisitos: Docker y Python 3.11 o superior.

```bash
# 1. PostgreSQL en Docker
docker compose up -d db

# 2. Entorno virtual y dependencias
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env             # Windows: Copy-Item .env.example .env

# 4. Migraciones
alembic upgrade head

# 5. Servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger en http://localhost:8000/docs
- Prueba rápida, que verifica bcrypt, la conexión a la BD y el registro de un conductor de prueba:

```bash
python scripts/smoke_test.py
```

Valores de `.env.example` (son placeholders de desarrollo):

```env
APP_ENVIRONMENT=development
DATABASE_URL=postgresql+psycopg://espol:espol_dev@localhost:5432/espol_transport
JWT_SECRET=dev-secret-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=720
EXPOSE_API_ERRORS=true
LOGIN_MAX_FAILED_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
RECAPTCHA_SECRET_KEY=
RECAPTCHA_MIN_SCORE=0.5
FORCE_HTTPS_REDIRECT=false
```

### Pruebas

La suite de `tests/` corre de punta a punta contra **PostgreSQL real**: recrea la base, aplica las migraciones de Alembic y prueba auth, roles, el horario del conductor, la búsqueda, la reserva, concluir, calificar y cancelar. Usa una base aparte, así que no toca tus datos de desarrollo.

```bash
docker run -d --rm --name espol-test-pg -e POSTGRES_USER=espol -e POSTGRES_PASSWORD=espol_dev   -e POSTGRES_DB=espol_test -p 55432:5432 postgres:16-alpine
pip install -r requirements-dev.txt
pytest -q
```

Para usar otra base, define `TEST_DATABASE_URL`, que **se vacía en cada corrida**. El CI de GitHub Actions corre la misma suite con un Postgres de servicio en cada push y en cada PR.

> `docker-compose.yml` también define un servicio `mailpit`, que quedó de la etapa OTP. Ya no es necesario.

Para probar con la app Android, apunta `api.base.url=http://<IP_DE_TU_PC>:8000/` en su `local.properties`. Ver [SETUP_PRUEBAS.md](SETUP_PRUEBAS.md).

## Despliegue

Resumen de [DESPLIEGUE.md](DESPLIEGUE.md):

- **Render o Railway**: un servicio web con build `pip install -r requirements.txt` y start `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`, más PostgreSQL gestionado. La API acepta `postgresql://` y lo normaliza a `postgresql+psycopg://`.
- **VPS**: Docker o systemd con Caddy o Nginx delante y certificado Let's Encrypt. Postgres no debe quedar expuesto a Internet.
- Variables de producción: `APP_ENVIRONMENT=production`, un `JWT_SECRET` largo y aleatorio, `EXPOSE_API_ERRORS=false` y `FORCE_HTTPS_REDIRECT=true`.
- La app Android debe usar una URL `https://`.

Más documentación:

- [BASE_DE_DATOS.md](BASE_DE_DATOS.md): dónde viven los datos, cómo conectarse con psql y consultas útiles.
- [SEGURIDAD.md](SEGURIDAD.md): medidas de seguridad.
- [SETUP_PRUEBAS.md](SETUP_PRUEBAS.md): entorno de pruebas con un pasajero y un conductor.
- [OTP_SMTP_RENDER.md](OTP_SMTP_RENDER.md): histórico. El OTP ya no existe.

## Estructura

```
.
├── app/
│   ├── main.py               # App FastAPI, middleware, routers, /health
│   ├── config.py             # Settings (.env) y salvaguardas de producción
│   ├── database.py, deps.py  # Engine/sesión y dependencias (usuario actual)
│   ├── models.py, schemas.py # ORM SQLAlchemy y esquemas Pydantic
│   ├── routers/              # auth, zones, vehicles, published_routes, match,
│   │                         # driver_schedule, trip_times, bookings
│   ├── security.py           # bcrypt y JWT
│   ├── auth_security.py      # Bloqueo de login
│   ├── recovery_security.py  # Bloqueo y log de recuperación
│   ├── rate_limit.py, recaptcha.py
│   ├── password_policy.py, recovery_phrase_policy.py
│   ├── matchmaking.py, passenger_matching.py, zone_matching.py
│   ├── booking_capacity.py, fare_utils.py, driver_ratings.py
│   └── account_deletion.py, trip_times.py, time_utils.py, weekday_labels.py
├── alembic/versions/         # Migraciones 0001–0010
├── scripts/smoke_test.py
├── tests/                    # pytest de punta a punta contra PostgreSQL
├── .github/workflows/ci.yml  # CI: pytest con Postgres de servicio
├── docker-compose.yml
├── requirements.txt, requirements-dev.txt
└── .env.example
```

## Mejoras futuras

- Ampliar las pruebas: recuperación de contraseña, eliminación de cuenta, cupos llenos y bloqueo por intentos fallidos.
- Dockerfile para la API, para desplegar con una sola imagen.
- Notificaciones push (FCM) en lugar de consultar la bandeja de avisos.
- Rate limit con almacenamiento compartido (Redis). Hoy se guarda en memoria y es por proceso.
- Retirar `GET /matches/legacy` y el servicio `mailpit` si ya no se usan.
- Limpiar en DESPLIEGUE.md la referencia a `EXPOSE_DEV_OTP`, que viene de la etapa OTP.

## Licencia

Distribuido bajo la licencia MIT. Copyright (c) 2026 Samuel Arias. Ver [LICENSE](LICENSE).
