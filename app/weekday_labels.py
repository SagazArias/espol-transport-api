WEEKDAY_NAMES_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def weekday_name(weekday: int) -> str:
    if 0 <= weekday < len(WEEKDAY_NAMES_ES):
        return WEEKDAY_NAMES_ES[weekday]
    return f"Día {weekday}"
