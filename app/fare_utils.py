from decimal import Decimal, InvalidOperation

ALLOWED_FARES_USD: list[Decimal] = [
    Decimal("1.00"),
    Decimal("1.25"),
    Decimal("1.50"),
    Decimal("1.75"),
    Decimal("2.00"),
    Decimal("2.25"),
    Decimal("2.50"),
]


def parse_and_validate_fare(value: float | str | Decimal) -> Decimal:
    try:
        fare = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Tarifa inválida.") from exc
    if fare not in ALLOWED_FARES_USD:
        allowed = ", ".join(f"${f}" for f in ALLOWED_FARES_USD)
        raise ValueError(f"La tarifa debe ser una de: {allowed}")
    return fare
