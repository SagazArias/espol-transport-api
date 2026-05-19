# Seguridad — registro, login y OTP

## Qué está implementado

| Riesgo OWASP | Medida en esta API |
|--------------|-------------------|
| Fuerza bruta / credential stuffing | Rate limit por IP (`slowapi`), bloqueo tras 5 intentos fallidos (`login_lockouts`) |
| Contraseñas débiles | Política: 8+ caracteres, mayúscula, minúscula, número y símbolo (`app/password_policy.py`) |
| Enumeración de usuarios | Mensajes genéricos en login y registro; OTP siempre responde el mismo texto |
| IDOR | Rutas y reservas filtran por usuario autenticado (ej. `GET /published-routes/{id}` solo dueño) |
| Contraseñas en texto plano | bcrypt con 12 rondas (`app/security.py`) |
| OTP en texto plano en BD | Hash con HMAC (`app/otp_utils.py`) |
| OTP de prueba en producción | `APP_ENVIRONMENT=production` fuerza `OTP_DELIVERY=smtp` y `EXPOSE_DEV_OTP=false` |
| Transmisión HTTP | `FORCE_HTTPS_REDIRECT=true` detrás de proxy; cabecera HSTS en producción |
| Sesiones largas | JWT con expiración (`ACCESS_TOKEN_EXPIRE_MINUTES`, máx. 12 h en producción) |
| Bots | reCAPTCHA v3 opcional si defines `RECAPTCHA_SECRET_KEY` |
| Errores internos filtrados | `EXPOSE_API_ERRORS=false` en producción |

## OTP real para estudiantes ESPOL

1. En `.env` de producción:

```env
APP_ENVIRONMENT=production
OTP_DELIVERY=smtp
EXPOSE_DEV_OTP=false
SMTP_HOST=smtp.tuproveedor.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=ESPOL Transporte <noreply@tudominio.com>
SMTP_USE_TLS=true
```

2. El estudiante usa correo `@espol.edu.ec` → `POST /auth/passenger/send-otp` → recibe **6 dígitos por correo** (válidos 15 min).

3. Completa registro con `POST /auth/passenger/register` y el código.

Para pruebas locales sin SMTP real puedes usar Mailpit (`docker compose` + `SMTP_HOST=localhost`, puerto 1025) o temporalmente `OTP_DELIVERY=log` solo con `APP_ENVIRONMENT=development`.

## Android y tokens

La app guarda el JWT en **DataStore** (almacenamiento privado de la app), no en `localStorage` del navegador. Para una futura versión web, usar cookies `HttpOnly; Secure; SameSite=Strict`.

## MFA / 2FA (siguiente fase)

No está en esta versión. Recomendación: TOTP (Google Authenticator) con tabla `user_mfa_secrets` y verificación en login. Se puede integrar después sin cambiar el modelo de contraseñas.

## reCAPTCHA (opcional)

1. Crear sitio en [Google reCAPTCHA](https://www.google.com/recaptcha/admin) (v3).
2. `RECAPTCHA_SECRET_KEY` en el servidor.
3. En Android/Web enviar `captcha_token` en login, registro y `send-otp` (campo ya existe en la API).

Si la clave está vacía, la API **no** exige captcha (útil en desarrollo).

## Variables de entorno

Ver `.env.example` y `app/config.py`.
