import re

# Mínimo 8 caracteres, mayúscula, minúscula, dígito y carácter especial.
_PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$"
)


def validate_password_strength(password: str) -> str:
    if password != password.strip() or " " in password:
        raise ValueError(
            "La contraseña debe ser una sola cadena sin espacios al inicio, al final ni en el medio."
        )
    if not _PASSWORD_RE.match(password):
        raise ValueError(
            "La contraseña debe tener al menos 8 caracteres, "
            "incluir mayúscula, minúscula, número y un carácter especial."
        )
    return password
