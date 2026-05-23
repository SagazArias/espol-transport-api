# Desplegar la API (sin depender de tu laptop)

Objetivo: la app Android apunte a una URL pública `https://api.tudominio.com` que siga activa aunque apagues el PC.

## Arquitectura recomendada

```
[App Android]  --HTTPS-->  [API FastAPI]  --->  [PostgreSQL gestionado]
                                |
```

## Opción A — Railway o Render (rápido)

1. Sube el repo (o solo la carpeta `espol-transport-api`) a GitHub.
2. Crea un servicio **Web** con:
   - Build: `pip install -r requirements.txt`
   - Start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Añade **PostgreSQL** como add-on y copia su `DATABASE_URL` a variables de entorno.
4. Variables obligatorias:

```env
APP_ENVIRONMENT=production
DATABASE_URL=postgresql://...
JWT_SECRET=<genera 64 caracteres aleatorios>
EXPOSE_API_ERRORS=false
FORCE_HTTPS_REDIRECT=true
```

5. La plataforma te da `https://tu-app.onrender.com` o similar.

## Opción B — VPS (DigitalOcean, Hetzner, AWS EC2)

1. Ubuntu + Docker + Docker Compose o systemd.
2. Nginx o Caddy delante con **certificado Let's Encrypt**.
3. Postgres en el mismo VPS o managed (recomendado managed).
4. Ejemplo Caddyfile:

```text
api.tudominio.com {
    reverse_proxy localhost:8000
}
```

5. En `.env` del servidor: `FORCE_HTTPS_REDIRECT=true`.

## Migraciones en el servidor

```bash
cd espol-transport-api
alembic upgrade head
```

Ejecutar en cada despliegue antes o al arrancar (como en el comando `Start` de arriba).

## Actualizar la app Android

En `espol-transport-android/local.properties`:

```properties
api.base.url=https://api.tudominio.com/
```

Recompila e instala el APK. **No uses** `http://192.168.x.x` en producción.

## Checklist antes de producción

- [ ] `APP_ENVIRONMENT=production`
- [ ] `alembic upgrade head` (incluye migración `0010` si venías de OTP)
- [ ] Registro pasajero con `@espol.edu.ec` probado desde la app
- [ ] `EXPOSE_DEV_OTP=false`
- [ ] `JWT_SECRET` único y largo
- [ ] HTTPS activo
- [ ] `alembic upgrade head` en la BD de producción
- [ ] Android con `api.base.url` HTTPS
- [ ] Firewall: solo puertos 80/443 públicos; Postgres no expuesto a Internet

## Coste orientativo

| Servicio | Aproximado |
|----------|------------|
| Render/Railway free tier | $0 (con límites de sueño) |
| VPS pequeño | $5–12/mes |
| Postgres managed | $0–15/mes |
| Dominio | ~$10/año |

## Publicar APK (opcional)

- Google Play Console (cuenta desarrollador).
- O distribución interna (Firebase App Distribution) para pilotos ESPOL.
