# Entorno de pruebas — ESPOL Transporte

Guía para probar **1 pasajero** y **1 conductor** en local (API + Android).

## Requisitos

- Docker Desktop
- Python 3.11+
- Android Studio (teléfono físico o emulador)

## 1. Base de datos

```powershell
cd espol-transport-api
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2. Registro

- **Pasajero:** correo `@espol.edu.ec`, nombre, apellido, celular, contraseña (dos veces), palabra clave de recuperación.
- **Conductor:** mismos datos + vehículo.
- **Un correo = una cuenta.** Si el correo ya existe, debes iniciar sesión o eliminar la cuenta anterior.

## 3. Android

En `espol-transport-android/local.properties`:

```properties
api.base.url=http://<IP_DE_TU_PC>:8000/
```

Recompila e instala el APK.

## 4. Eliminar cuenta

Desde la bandeja de entrada (o horario del conductor): **Eliminar mi cuenta** → confirmar con contraseña. El correo queda libre para un registro nuevo.
