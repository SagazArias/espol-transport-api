# Seguridad — registro, login y cuentas

## Medidas implementadas

| Riesgo | Medida |
|--------|--------|
| Fuerza bruta en login | Rate limit + bloqueo tras 5 intentos (`login_lockouts`) |
| Contraseñas débiles | Política en `app/password_policy.py` (8+ chars, mayúscula, minúscula, número, símbolo, sin espacios) |
| Recuperación de contraseña | Palabra clave con bcrypt; máx. 5 intentos + cooldown |
| Un correo, una cuenta | Registro rechaza correo duplicado (409); eliminar cuenta libera el correo |
| IDOR | Recursos filtrados por usuario autenticado |
| Eliminar cuenta | `DELETE /auth/me` con contraseña obligatoria |
| Pasajeros ESPOL | Solo correos `@espol.edu.ec` al registrarse |
| JWT | Expiración configurable; sesión opcional en Android (DataStore) |

## Registro pasajero

- Correo institucional `@espol.edu.ec` (sin OTP por correo).
- Nombre y apellido obligatorios (aparecen en avisos al conductor).
- Palabra clave de recuperación (hash bcrypt, distinta de la contraseña).

## Eliminar cuenta

`DELETE /auth/me` con cuerpo `{ "password": "..." }`. Borra perfil, horarios, reservas y datos asociados.

## Variables de entorno

Ver `.env.example` y `app/config.py`.
