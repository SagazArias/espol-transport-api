# Base de datos — dónde están los usuarios y credenciales

## Ubicación física

| Entorno | Dónde está |
|---------|------------|
| **Local (tu PC)** | Contenedor Docker `postgres:16` definido en `docker-compose.yml`, puerto **5432** |
| **Producción** | PostgreSQL gestionado (Railway, Render, Supabase, Neon, VPS propio, etc.) — la URL va en `DATABASE_URL` |

No hay un archivo “usuarios.txt”. Todo vive en **PostgreSQL**.

## Conexión local

```powershell
cd espol-transport-api
docker compose up -d
```

Credenciales por defecto del `docker-compose.yml`:

- Host: `localhost`
- Puerto: `5432`
- Base: `espol_transport`
- Usuario: `espol`
- Contraseña: `espol_dev`

## Ver datos con psql (línea de comandos)

```powershell
docker exec -it espol-transport-api-db-1 psql -U espol -d espol_transport
```

(Si el nombre del contenedor difiere, usa `docker ps` y sustituye el nombre.)

Consultas útiles:

```sql
-- Usuarios (pasajeros y conductores)
SELECT id, email, role, first_name, last_name, phone, espol_verified_at, created_at
FROM users
ORDER BY created_at DESC;

-- Contraseñas: NUNCA en texto plano, solo hash bcrypt
SELECT email, role, left(password_hash, 20) AS hash_preview
FROM users;

-- Vehículos de conductores
SELECT u.email, v.plate, v.brand, v.model
FROM vehicles v
JOIN users u ON u.id = v.owner_id;

-- OTP pendientes (solo hash del código, no el código en claro)
SELECT email, expires_at, consumed_at, created_at
FROM student_email_otps
ORDER BY created_at DESC
LIMIT 20;

-- Bloqueos por intentos fallidos de login
SELECT * FROM login_lockouts;

-- Reservas activas
SELECT * FROM trip_bookings WHERE status = 'active';
```

## Tablas principales

| Tabla | Contenido |
|-------|-----------|
| `users` | Cuenta: email, `password_hash` (bcrypt), nombre, teléfono, rol (`student` / `driver`), `espol_verified_at` |
| `student_email_otps` | Códigos de verificación ESPOL (hash + expiración 15 min) |
| `login_lockouts` | Intentos fallidos de login por email |
| `vehicles` | Placa, marca, modelo del conductor |
| `driver_weekly_profiles` / `driver_day_plans` | Horarios y tarifa del conductor |
| `trip_bookings` | Viajes agendados pasajero ↔ conductor |
| `inbox_alerts` | Avisos en bandeja |

## Importante sobre contraseñas

- En `users.password_hash` solo hay **bcrypt** (función `hash_password` en `app/security.py`).
- **No puedes “ver” la contraseña original**; es lo correcto. Si olvidas una cuenta de prueba, borra el usuario o restablece con un script nuevo hash.

## Cliente gráfico (opcional)

- [DBeaver](https://dbeaver.io/) o pgAdmin  
- JDBC/URL: `postgresql://espol:espol_dev@localhost:5432/espol_transport`
