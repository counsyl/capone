from pytz import UTC


def to_utc(timestamp):
    """Convert a given timestamp to UTC.

    If the given datetime has no timezone attached, assume it is naive UTC
    timestamp and tack on the UTC tzinfo. If the timestamp has a timezone
    attached, then just convert it to UTC.

    Returns a datetime with tzinfo=UTC.
    """
    if not hasattr(timestamp, 'tzinfo') or not timestamp.tzinfo:
        timestamp = UTC.localize(timestamp)
    if timestamp.tzinfo != UTC:
        timestamp = timestamp.astimezone(UTC)
    return timestamp
