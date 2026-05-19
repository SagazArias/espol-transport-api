from datetime import time, timedelta


def _time_to_td(t: time) -> timedelta:
    return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)


def _td_to_time(td: timedelta) -> time:
    total = int(td.total_seconds()) % 86400
    if total < 0:
        total += 86400
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return time(hour=h, minute=m, second=s)


def subtract_minutes(t: time, minutes: int) -> time:
    base = _time_to_td(t)
    return _td_to_time(base - timedelta(minutes=minutes))


def minutes_between(a: time, b: time) -> int:
    """Returns (a - b) in minutes as integer, in range roughly [-12h, 12h] by normalizing."""
    da = int(_time_to_td(a).total_seconds())
    db = int(_time_to_td(b).total_seconds())
    diff = (da - db) // 60
    if diff > 720:
        diff -= 1440
    if diff < -720:
        diff += 1440
    return diff
