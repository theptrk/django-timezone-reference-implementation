from datetime import UTC, datetime, time, timedelta
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, available_timezones

from django.core.exceptions import ValidationError


@lru_cache(maxsize=1)
def zone_names():
    return frozenset(available_timezones())


def validate_zone(value):
    if not isinstance(value, str) or value not in zone_names():
        raise ValidationError("Choose a valid IANA timezone, such as America/Los_Angeles.")


def safe_zone(value, fallback="UTC"):
    try:
        validate_zone(value)
    except ValidationError:
        return fallback
    return value


def resolve_zone(preference):
    # Detection can suggest a change, but only an explicit save changes account display.
    return safe_zone(preference.display_timezone, safe_zone(preference.reporting_timezone))


def week_bounds(instant, zone_name):
    """Return UTC [Monday, next Monday) for the instant's LOCAL calendar week.

    ZoneInfo uses the offset at each boundary, so DST weeks need not be 168 hours.
    A midnight gap uses the pre-transition offset (the first instant after the gap);
    a midnight fold uses the first occurrence. This is an explicit calendar policy.
    """
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("week_bounds requires an aware instant")
    zone = ZoneInfo(zone_name)
    local_date = instant.astimezone(zone).date()
    monday = local_date - timedelta(days=local_date.weekday())
    start = datetime.combine(monday, time.min, tzinfo=zone)
    end = datetime.combine(monday + timedelta(days=7), time.min, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


@lru_cache(maxsize=1)
def timezone_choices():
    """US-first presentation; tzdata's maintained country table supplies coverage.

    Keep validation separate: browsers and existing accounts may use valid aliases.
    Do not collapse zones by today's offset; historical and future rules can differ.
    """
    common = [
        ("America/New_York", "Eastern — New York"),
        ("America/Chicago", "Central — Chicago"),
        ("America/Denver", "Mountain — Denver (also Navajo Nation)"),
        ("America/Phoenix", "Arizona — Phoenix (no DST; except Navajo Nation)"),
        ("America/Los_Angeles", "Pacific — Los Angeles"),
        ("America/Anchorage", "Alaska — Anchorage"),
        ("America/Adak", "Hawaii–Aleutian — Adak (observes DST)"),
        ("Pacific/Honolulu", "Hawaii — Honolulu (no DST)"),
    ]
    territories = [
        ("America/Puerto_Rico", "Atlantic — Puerto Rico"),
        ("America/St_Thomas", "Atlantic — U.S. Virgin Islands"),
        ("Pacific/Guam", "Chamorro — Guam"),
        ("Pacific/Saipan", "Chamorro — Northern Mariana Islands"),
        ("Pacific/Pago_Pago", "Samoa — American Samoa"),
        ("Pacific/Midway", "U.S. minor outlying islands — Midway"),
        ("Pacific/Wake", "U.S. minor outlying islands — Wake Island"),
    ]
    used = {zone for zone, label in common + territories}
    regional = []
    international = []
    table = files("tzdata.zoneinfo").joinpath("zone.tab").read_text()
    for line in table.splitlines():
        if not line or line.startswith("#"):
            continue
        country, coordinates, zone, *comment = line.split("\t")
        if zone in used or zone not in zone_names():
            continue
        place = zone.replace("_", " ").replace("/", " / ")
        if country in {"US", "AS", "GU", "MP", "PR", "VI", "UM"}:
            regional.append((zone, place.removeprefix("America / ")))
        else:
            international.append((zone, place))
        used.add(zone)

    def labeled(items):
        return [(zone, f"{label} · {zone}") for zone, label in items]

    return [
        ("United States — main regions", labeled(common)),
        ("U.S. territories & outlying islands", labeled(territories)),
        ("Additional U.S. locations — historical rules", labeled(sorted(regional))),
        ("UTC", [("UTC", "UTC — Coordinated Universal Time")]),
        ("Worldwide locations", labeled(sorted(international))),
        (
            "Other supported identifiers & aliases",
            [(zone, zone) for zone in sorted(zone_names() - used - {"UTC"})],
        ),
    ]


@lru_cache(maxsize=1)
def timezone_search_data():
    """Country names supplement visible city/region labels in the local picker search."""
    root = files("tzdata.zoneinfo")
    countries = {}
    for line in root.joinpath("iso3166.tab").read_text().splitlines():
        if line and not line.startswith("#"):
            code, name = line.split("\t", 1)
            countries[code] = name
    result = {}
    for line in root.joinpath("zone.tab").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        country, coordinates, zone, *comment = line.split("\t")
        words = [country, countries.get(country, ""), *comment]
        if country in {"US", "AS", "GU", "MP", "PR", "VI", "UM"}:
            words.extend(["United States", "USA", "US"])
        result[zone] = " ".join(words)
    return result
