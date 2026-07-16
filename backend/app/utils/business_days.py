"""Utility: business-day (Mon-Fri) arithmetic for SLA checks."""
from datetime import datetime, date, timedelta

_ONE_DAY = timedelta(days=1)


def business_days_between(start: date, end: date) -> int:
    """Count weekdays strictly between two dates (excludes weekends, ignores holidays)."""
    if end <= start:
        return 0
    count = 0
    cursor = start
    while cursor < end:
        cursor = cursor + _ONE_DAY
        if cursor.weekday() < 5:
            count += 1
    return count


def to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value
