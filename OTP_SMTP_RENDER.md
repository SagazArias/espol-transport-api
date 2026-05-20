# ⚠️ SMTP en Render

Render **bloquea conexiones SMTP** en el plan gratuito. No uses `OTP_DELIVERY=smtp` en Render.

**Usa Resend:** consulta [OTP_RESEND.md](./OTP_RESEND.md).

`OTP_DELIVERY=smtp` queda solo para desarrollo local con **Mailpit** (`docker compose`, puerto 1025).
