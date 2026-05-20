# OTP con Resend (Render y producción)

Render **bloquea SMTP** en el plan gratuito. Esta API envía los códigos de 6 dígitos con la **API HTTP de Resend** (`OTP_DELIVERY=resend`).

## 1. Cuenta Resend

1. Regístrate en [https://resend.com](https://resend.com).
2. **API Keys** → crea una clave → copia `re_...`.

## 2. Remitente (FROM)

| Fase | `RESEND_FROM` |
|------|----------------|
| Pruebas | `ESPOL Transporte <onboarding@resend.dev>` (solo envía a tu correo registrado en Resend) |
| Producción ESPOL | Verifica el dominio `espol.edu.ec` en Resend → Domains → luego `ESPOL Transporte <noreply@espol.edu.ec>` |

Sin dominio verificado, Resend **no** entregará a correos `@espol.edu.ec` arbitrarios.

## 3. Variables en Render

En el servicio Web de la API → **Environment**:

```env
APP_ENVIRONMENT=production
OTP_DELIVERY=resend
RESEND_API_KEY=re_tu_clave_aqui
RESEND_FROM=ESPOL Transporte <onboarding@resend.dev>
EXPOSE_DEV_OTP=false
EXPOSE_API_ERRORS=false
JWT_SECRET=<cadena larga aleatoria>
DATABASE_URL=<postgres de render>
```

Guarda, **redeploy** y prueba `POST /auth/passenger/send-otp`.

## 4. Desarrollo local

```env
OTP_DELIVERY=log
EXPOSE_DEV_OTP=true
```

O prueba Resend real con tu `RESEND_API_KEY` en `.env` local.

## 5. Errores frecuentes

| Log / error | Solución |
|-------------|----------|
| `RESEND_API_KEY no está configurado` | Añade la variable en Render y redeploy |
| `validation_error` / dominio | Usa `onboarding@resend.dev` en pruebas o verifica tu dominio |
| 502 en send-otp | Revisa logs: `OTP email failed` — el detalle viene de Resend |
| Correo no llega a @espol.edu.ec | Verifica dominio `espol.edu.ec` en Resend (DNS SPF/DKIM) |

## 6. SMTP (opcional)

`OTP_DELIVERY=smtp` sigue disponible para **Mailpit** en local (`localhost:1025`). No uses SMTP en Render free tier.
