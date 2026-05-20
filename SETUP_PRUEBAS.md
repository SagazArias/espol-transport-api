# Entorno de pruebas — ESPOL Transporte

> **Producción / seguridad / despliegue:** `SEGURIDAD.md`, `DESPLIEGUE.md`, `BASE_DE_DATOS.md`.  
> OTP en Render/producción: `OTP_DELIVERY=resend` + `RESEND_API_KEY` (ver `OTP_RESEND.md`). SMTP no funciona en Render free tier.

Guía para probar **1 pasajero** y **1 conductor** en local (API + Android).

## Qué necesitas instalado

| Herramienta | Para qué |
|-------------|----------|
| **Docker Desktop** | PostgreSQL + Mailpit (correo de prueba) |
| **Python 3.11+** | API FastAPI |
| **Android Studio** | App en emulador o teléfono |

## 1. Base de datos y correo (Docker)

En PowerShell, desde la carpeta de la API:

```powershell
cd C:\Users\Sagaz\.cursor\projects\empty-window\espol-transport-api
docker compose up -d
```

Esto levanta:

- **PostgreSQL** en `localhost:5432` (usuario `espol`, contraseña `espol_dev`, base `espol_transport`)
- **Mailpit** (correo falso para pruebas):
  - SMTP: `localhost:1025`
  - Bandeja web: http://localhost:8025

## 2. API (backend)

```powershell
cd C:\Users\Sagaz\.cursor\projects\empty-window\espol-transport-api

# Entorno virtual (solo la primera vez)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Si el registro fallaba con "Internal Server Error", ejecuta la prueba:
python scripts/smoke_test.py

# Configuración (solo la primera vez)
Copy-Item .env.example .env

# Migraciones (incluye quitar tipo de conductor)
$env:PYTHONPATH = (Get-Location).Path
alembic upgrade head

# Arrancar API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Comprueba: http://127.0.0.1:8000/health → `{"status":"ok"}`

Documentación interactiva: http://127.0.0.1:8000/docs

### OTP / correo — dos modos

En `.env`:

#### Modo A — más simple (recomendado al empezar)

```env
OTP_DELIVERY=log
EXPOSE_DEV_OTP=true
```

- El código de 6 dígitos aparece en la **consola de uvicorn** y la app Android lo **rellena solo** en el registro.
- No necesitas leer ningún correo.

#### Modo B — correo visible en Mailpit

```env
OTP_DELIVERY=smtp
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_FROM=espol-transport@localhost
EXPOSE_DEV_OTP=true
```

- Reinicia `uvicorn` después de cambiar `.env`.
- Abre http://localhost:8025 y busca el mensaje con el código.

> **Sobre el error de puerto:** si tenías `SMTP_HOST` apuntando a Gmail u otro servidor con puerto incorrecto (por ejemplo 30000), la API fallaba con 502. Con `OTP_DELIVERY=log` o Mailpit en el puerto **1025** eso desaparece.

## 3. App Android

1. Abre `espol-transport-android` en Android Studio.
2. **Emulador:** por defecto usa `http://10.0.2.2:8000/` (no cambies nada).
3. **Teléfono físico** (misma Wi‑Fi que el PC):
   - En PowerShell en el PC: `ipconfig` → anota la **IPv4** (ej. `192.168.100.25`).
   - En `espol-transport-android/local.properties` añade:
     ```properties
     api.base.url=http://192.168.100.25:8000/
     ```
     (usa tu IP real, no la del teléfono).
   - **Rebuild** la app (Build → Rebuild Project) e instálala de nuevo.
   - En el teléfono, abre el navegador: `http://TU_IP:8000/health` debe mostrar `{"status":"ok"}`.
   - Si no carga, permite el puerto **8000** en el firewall de Windows o desactiva temporalmente el firewall para probar.

Ejecuta la app (Run).

## 4. Crear cuentas de prueba

### Pasajero (estudiante)

1. Pantalla inicial → **Soy pasajero**.
2. Correo: debe terminar en `@espol.edu.ec` (puede ser ficticio para pruebas, ej. `juan.perez@espol.edu.ec`).
3. **Enviar código**:
   - Modo `log`: mira la consola de uvicorn o el campo OTP ya rellenado en la siguiente pantalla.
   - Modo `smtp`: abre http://localhost:8025.
4. Completa nombre, apellido, celular, contraseña (mín. 8 caracteres) → **Registrar**.
5. **Iniciar sesión** con el mismo correo y contraseña.

### Conductor

1. Pantalla inicial → **Soy conductor**.
2. Completa datos personales, correo (cualquier email válido), contraseña, placa, marca y modelo.
3. **Registrar conductor** → **Iniciar sesión**.

Ya tienes dos usuarios distintos para seguir probando rutas y matches cuando esas pantallas estén en la app.

## 5. Simular pasajero + conductor (matchmaking)

1. Aplica migraciones (incluye horarios semanales):
   ```powershell
   alembic upgrade head
   ```
2. **Conductor** (desde la app): regístrate → inicia sesión → pantalla **Ruta semanal**:
   - Origen: `Romareda` (o Mucho Lote, La Joya, etc.)
   - Por cada día que conduces: elige hora **Ida** (ej. 07:00) y/o **Regreso** (ej. 17:00)
   - Sectores: `Romareda, La Joya` (separados por coma)
   - **Guardar horario semanal**
3. **Pasajero** (otro usuario): regístrate con `@espol.edu.ec` + OTP → inicia sesión → **Buscar conductor**:
   - Ida o Regreso
   - Sector hogar: `romareda`
   - Día y horario (ej. Lunes 07:00)
   - Debe listar al conductor si coincide sector y hora
4. Si no hay coincidencias, la app muestra el mensaje del servidor (sector u horario sin conductores).

Sectores reconocidos (texto aproximado): Mucho Lote 2, Romareda, La Joya, Samborondón centro, Urdesa Central.

## 6. Probar la API sin Android (opcional)

Con la API en marcha y un token JWT tras login:

```powershell
# Listar zonas
curl http://127.0.0.1:8000/zones

# Login pasajero
curl -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d "{\"email\":\"juan.perez@espol.edu.ec\",\"password\":\"tu_password\"}"
```

Usa `/docs` para publicar rutas (`/published-routes`) y buscar matches (`GET /matches`) como conductor/pasajero verificado.

## Resumen de puertos

| Servicio | Puerto |
|----------|--------|
| API FastAPI | 8000 |
| PostgreSQL | 5432 |
| Mailpit SMTP | 1025 |
| Mailpit web | 8025 |

## Producción

Antes de producción:

- `JWT_SECRET` largo y aleatorio
- `OTP_DELIVERY=smtp` con servidor real (Gmail, SendGrid, etc.)
- `EXPOSE_DEV_OTP=false`
- No uses HTTP en claro en la app Android
