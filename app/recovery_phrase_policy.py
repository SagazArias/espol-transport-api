import re

# Palabra clave: 4–64 caracteres, sin espacios (una sola cadena).
_RECOVERY_PHRASE_RE = re.compile(r"^[^\s]{4,64}$")


def validate_recovery_phrase(phrase: str) -> str:
    phrase = phrase.strip()
    if phrase != phrase.strip() or " " in phrase or "\t" in phrase:
        raise ValueError(
            "La palabra clave debe ser una sola cadena sin espacios al inicio, al final ni en el medio."
        )
    if not _RECOVERY_PHRASE_RE.match(phrase):
        raise ValueError("La palabra clave debe tener entre 4 y 64 caracteres, sin espacios.")
    return phrase
