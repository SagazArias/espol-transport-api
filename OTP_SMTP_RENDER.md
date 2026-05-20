# OTP por correo en Render — solución al error 502

El endpoint `POST /auth/passenger/send-otp` devuelve **502** cuando falla el envío SMTP. La API ya registra el error real en los **logs de Render** (busca `OTP email failed`).

## Variables en Render (Environment)

| Variable | Gmail (recomendado) | SendGrid |
|----------|---------------------|----------|
| `APP_ENVIRONMENT` | `production` | `production` |
| `OTP_DELIVERY` | `smtp` | `smtp` |
| `SMTP_HOST` | `smtp.gmail.com` | `smtp.sendgrid.net` |
| `SMTP_PORT` | `587` | `587` |
| `SMTP_USE_TLS` | `true` | `true` |
| `SMTP_USE_SSL` | `false` | `false` |
| `SMTP_USER` | tu correo Gmail | `apikey` |
| `SMTP_PASSWORD` | **contraseña de aplicación** (16 caracteres) | API key SendGrid |
| `SMTP_FROM` | mismo correo o alias verificado | correo verificado en SendGrid |
| `EXPOSE_DEV_OTP` | `false` | `false` |
| `EXPOSE_API_ERRORS` | `true` (temporal, para ver el detalle en la app) | igual |

### Puerto 465 (SSL directo)

Si tu proveedor usa **465**:

```env
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USE_TLS=false
```

No uses `SMTP_USE_TLS=true` con el puerto 465.

## Gmail — pasos

1. Activa verificación en 2 pasos en la cuenta Google.
2. Crea una **Contraseña de aplicación** (Google Cuenta → Seguridad → Contraseñas de aplicaciones).
3. Usa esa contraseña en `SMTP_PASSWORD`, **no** la contraseña normal de Gmail.

## Después de desplegar

1. En Render → Shell o en el comando de inicio: `alembic upgrade head`
2. Redeploy con las variables guardadas.
3. Prueba OTP y revisa **Logs** si sigue el 502; el mensaje incluirá el error SMTP concreto.

## Migración pendiente

Si añadiste recuperación de contraseña, ejecuta también la migración `0009`:

```bash
alembic upgrade head
```
