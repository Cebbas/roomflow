DOMAIN = "roomflow"
VERSION = "0.0.8"
STORAGE_KEY = "roomflow.rooms"
STORAGE_VERSION = 1

CONF_TIME_SENSOR = "time_sensor"
CONF_DAY_TYPE_SENSOR = "day_type_sensor"
CONF_DAY_TYPE_SENSOR_INVERTED = "day_type_sensor_inverted"
CONF_HOME_SENSOR = "home_sensor"
CONF_PERIOD_MAP = "period_map"
CONF_DEVICE_NAME = "device_name"
CONF_AREA_ID = "area_id"

# How each of the three inputs is sourced: either an existing HA entity
# ("sensor", the original/only behavior) or built/computed by RoomFlow itself
# with no external entity at all. The three choices are fully independent.
CONF_TIME_MODE = "time_mode"
CONF_DAY_TYPE_MODE = "day_type_mode"
CONF_HOME_MODE = "home_mode"

TIME_MODE_SENSOR = "sensor"
TIME_MODE_SCHEDULE = "schedule"

DAY_TYPE_MODE_NONE = "none"
DAY_TYPE_MODE_SENSOR = "sensor"
DAY_TYPE_MODE_WEEKDAY_SELECTION = "weekday_selection"

HOME_MODE_NONE = "none"
HOME_MODE_SENSOR = "sensor"
HOME_MODE_PERSONS = "persons"

# Built-in ("no external entity") input config
CONF_SCHEDULE = "schedule"
CONF_WEEKEND_DAYS = "weekend_days"
CONF_PERSON_ENTITIES = "person_entities"

# The time-of-day input can combine several sources at once as a fallback
# chain: try each in this fixed precedence, use the first that resolves to a
# period right now. Reactive/entity-based sources come first (they can be
# unavailable/unrecognized, so it's worth falling through); fully computed
# sources come last (they always succeed, so they're the natural final
# fallback). The user picks which of these to enable (CONF_TIME_SOURCES);
# this list is only ever used to derive that fixed try-order, never as
# user-orderable storage.
TIME_SOURCE_SENSOR = "sensor"
TIME_SOURCE_BOOLEAN = "boolean"
TIME_SOURCE_ILLUMINANCE = "illuminance"
TIME_SOURCE_SUN = "sun"
TIME_SOURCE_SCHEDULE = "schedule"
TIME_SOURCE_PRECEDENCE = [
    TIME_SOURCE_SENSOR,
    TIME_SOURCE_BOOLEAN,
    TIME_SOURCE_ILLUMINANCE,
    TIME_SOURCE_SUN,
    TIME_SOURCE_SCHEDULE,
]

CONF_TIME_SOURCES = "time_sources"  # list, any subset of TIME_SOURCE_PRECEDENCE

# One existing boolean-ish entity (binary_sensor/input_boolean) per period,
# "on" meaning that period is currently active. This is an INPUT you point
# at entities you already have - distinct from the per-period binary_sensor
# OUTPUT entities RoomFlow itself creates (see binary_sensor.py), which are
# derived from whichever source resolves the period, regardless of source.
CONF_PERIOD_BOOLEANS = "period_booleans"  # {period: entity_id}

CONF_SUN_EVENTS = "sun_events"  # {period: {"event": ..., "offset_minutes": int}}
# These must match actual attribute names on astral.sun (what
# homeassistant.helpers.sun.get_astral_event_date looks up via getattr) -
# "noon"/"midnight", not "solar_noon"/"solar_midnight".
SUN_EVENT_KEYS = ["dawn", "sunrise", "noon", "sunset", "dusk", "midnight"]
DEFAULT_SUN_EVENTS = {
    "morning": {"event": "dawn", "offset_minutes": 0},
    "day": {"event": "sunrise", "offset_minutes": 0},
    "afternoon": {"event": "noon", "offset_minutes": 0},
    "evening": {"event": "sunset", "offset_minutes": 0},
    "night": {"event": "dusk", "offset_minutes": 0},
}

CONF_ILLUMINANCE_SENSOR = "illuminance_sensor"
CONF_ILLUMINANCE_THRESHOLDS = "illuminance_thresholds"  # {period: number}
DEFAULT_ILLUMINANCE_THRESHOLDS = {
    "night": 0,
    "morning": 10,
    "evening": 50,
    "afternoon": 300,
    "day": 1000,
}

# Index == date.weekday()
WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DEFAULT_SCHEDULE = {
    "morning": "06:00:00",
    "day": "10:00:00",
    "afternoon": "13:00:00",
    "evening": "18:00:00",
    "night": "22:00:00",
}
DEFAULT_WEEKEND_DAYS = ["sat", "sun"]

# ---------------------------------------------------------------------------
# Periods: a user-editable, priority-ordered list (add/remove/rename/reorder,
# like a room's devices). Each period can combine several sources at once -
# it's "active" if ANY of its own enabled sources currently resolves true
# (OR logic, same pattern as a room's motion triggers/custom conditions).
# This replaces the old model above (CONF_TIME_SOURCES etc.) where sources
# were chosen globally and applied uniformly to a fixed 5-period set - those
# constants are kept only so infer_periods() can migrate old stored data.
CONF_PERIODS = "periods"  # ordered list of {id, name, sources}

PERIOD_SOURCE_SCHEDULE = "schedule"        # fields: {"time": "HH:MM:SS"}
PERIOD_SOURCE_SUN = "sun"                  # fields: {"event": ..., "offset_minutes": int}
PERIOD_SOURCE_ILLUMINANCE = "illuminance"  # fields: {"entity_id": ..., "threshold": number}
PERIOD_SOURCE_BOOLEAN = "boolean"          # fields: {"entity_id": ...}
PERIOD_SOURCE_SENSOR = "sensor"            # fields: {"entity_id": ..., "value": "..."}
PERIOD_SOURCES = [
    PERIOD_SOURCE_SCHEDULE,
    PERIOD_SOURCE_SUN,
    PERIOD_SOURCE_ILLUMINANCE,
    PERIOD_SOURCE_BOOLEAN,
    PERIOD_SOURCE_SENSOR,
]

# Source types whose "is this period active" check is a clock-time boundary
# comparison against other periods' clock-based sources (see _get_period in
# __init__.py), as opposed to an independent true/false check of their own
# (illuminance/boolean/sensor).
CLOCK_BASED_PERIOD_SOURCES = (PERIOD_SOURCE_SCHEDULE, PERIOD_SOURCE_SUN)

# Every source can also require an extra AND condition on top of its own
# check - e.g. a sun-sourced period only counts as active at sunrise AND
# only if a lux sensor is currently below some value too. This is separate
# from (and stacks with) the OR relationship between a period's different
# *sources* - "value" is a plain string here and parsed as a number for
# above/below (blank/invalid = condition not met) or compared case-
# insensitively as text for equals, mirroring the existing "sensor" source.
DEFAULT_AND_CONDITION = {
    "enabled": False,
    "entity_id": None,
    "operator": "above",  # "above" | "below" | "equals"
    "value": "",
}

# Each source type's own fields (besides "enabled" and "and_condition",
# added to every type below), with their defaults - every period gets an
# entry for every type in `sources`, most left disabled, so the card can
# always show all 5 side by side. The two clock-based types also carry an
# optional weekend override (weekend_enabled + their own weekend_* fields)
# - e.g. a period whose schedule normally starts at 06:00 can start at
# 08:00 on weekend_days instead, without needing a whole separate period.
# Only meaningful once a weekend/weekday day-type source is configured (see
# infer_day_type_mode) - otherwise every day resolves "weekday" and the
# override never applies. The sun source also has "min_time": a floor -
# its resolved boundary is never earlier than this on any day - e.g. sunrise
# but never before 08:00. "00:00:00" (midnight) is a no-op floor (nothing
# resolves earlier than that within a day), so it's a safe inert default.
DEFAULT_SOURCE_FIELDS = {
    PERIOD_SOURCE_SCHEDULE: {
        "time": "00:00:00",
        "weekend_enabled": False,
        "weekend_time": "00:00:00",
    },
    PERIOD_SOURCE_SUN: {
        "event": "sunrise",
        "offset_minutes": 0,
        "min_time": "00:00:00",
        "weekend_enabled": False,
        "weekend_event": "sunrise",
        "weekend_offset_minutes": 0,
    },
    PERIOD_SOURCE_ILLUMINANCE: {"entity_id": None, "threshold": 0},
    PERIOD_SOURCE_BOOLEAN: {"entity_id": None},
    PERIOD_SOURCE_SENSOR: {"entity_id": None, "value": ""},
}
for _fields in DEFAULT_SOURCE_FIELDS.values():
    _fields["and_condition"] = dict(DEFAULT_AND_CONDITION)

DEFAULT_PERIOD_LABELS = {
    "morning": "Morning",
    "day": "Day",
    "afternoon": "Afternoon",
    "evening": "Evening",
    "night": "Night",
}

# Dispatcher signal fired whenever period/day-type/home-state may have
# changed, regardless of what triggered the recompute (entity state change,
# schedule boundary, or midnight rollover). RoomFlow only supports a single
# instance, so one global signal name is fine.
SIGNAL_RECOMPUTE = f"{DOMAIN}_recompute"

DEFAULT_DEVICE_NAME = "RoomFlow"

# The 5 default period ids RoomFlow starts with (a fresh install, or an
# upgrade from before periods were user-editable). Periods are now a
# user-editable, priority-ordered list (see CONF_PERIODS/infer_periods
# below) - this is only the *starting point*/migration seed, not a fixed
# set application logic iterates over anymore.
TIME_PERIODS = ["morning", "day", "afternoon", "evening", "night"]

# Sensible defaults for the period mapping: assumes the sensor already
# reports these exact English words. Override during setup if your sensor
# uses different wording (any language).
DEFAULT_PERIOD_MAP = {
    "morning": "morning",
    "day": "day",
    "afternoon": "afternoon",
    "evening": "evening",
    "night": "night",
}

# The starting `periods` list for a fresh install: schedule-sourced (only
# "schedule" enabled, same clock times as the old DEFAULT_SCHEDULE), all
# other source types present but disabled, in canonical order.
def _default_sources(period_id: str) -> dict:
    sources = {
        source_type: {"enabled": False, **DEFAULT_SOURCE_FIELDS[source_type]}
        for source_type in PERIOD_SOURCES
    }
    sources[PERIOD_SOURCE_SCHEDULE] = {
        **sources[PERIOD_SOURCE_SCHEDULE],
        "enabled": True,
        "time": DEFAULT_SCHEDULE[period_id],
    }
    return sources


DEFAULT_PERIODS = [
    {
        "id": period_id,
        "name": DEFAULT_PERIOD_LABELS[period_id],
        "sources": _default_sources(period_id),
    }
    for period_id in TIME_PERIODS
]

# Backward-compatibility: older (pre-English) versions of this integration
# stored period keys in Swedish. Existing stored configs are migrated once
# on load using this map.
LEGACY_PERIOD_KEY_MAP = {
    "morgon": "morning",
    "dag": "day",
    "eftermiddag": "afternoon",
    "kvall": "evening",
    "natt": "night",
}

DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_OUTLET = "outlet"

DEFAULT_BEHAVIOR_LIGHT = {
    "state": "off",
    "brightness": 255,
    "color_temp_kelvin": 3000,
}

DEFAULT_BEHAVIOR_OUTLET = {
    "state": "off",
}

# Which state values (case-insensitive) count as "weekend" and "home",
# respectively, for the optional day-type/home sensors. Includes a few
# common synonyms across languages. A plain "on"/"off" binary_sensor is
# handled separately (see CONF_DAY_TYPE_SENSOR_INVERTED) since - unlike
# home/away, where "on" universally means "home" in HA convention - there's
# no universal polarity for a day-type sensor: some report "on" for weekend,
# others (e.g. a "workday" sensor) report "on" for weekday.
WEEKEND_STATES = {"weekend", "holiday", "helg", "ledig", "lov"}
HOME_STATES = {"home", "hemma", "on", "true"}

# Default transition time (seconds) per period, used unless the device or a
# global setting specifies something else
DEFAULT_TRANSITIONS = {
    "morning": 1,
    "day": 0,
    "afternoon": 0,
    "evening": 2,
    "night": 3,
}


# Entries stored before the mode fields existed have no CONF_*_MODE key at
# all. These infer the equivalent mode from the legacy fields so old configs
# keep behaving exactly as before, with no storage migration needed.
def infer_time_mode(data: dict) -> str:
    return data.get(CONF_TIME_MODE, TIME_MODE_SENSOR)


def infer_time_sources(data: dict) -> list[str]:
    """Entries saved before combinable time sources existed have either a
    single CONF_TIME_MODE (the previous round's either/or choice) or
    nothing at all (fully legacy). Both collapse to a single-element list
    here so infer_time_sources is always the one source of truth."""
    if CONF_TIME_SOURCES in data:
        return [source for source in TIME_SOURCE_PRECEDENCE if source in data[CONF_TIME_SOURCES]]
    return [infer_time_mode(data)]


def _normalize_period(period: dict) -> dict:
    """Normalize one period entry to the current multi-source shape ({id,
    name, sources: {type: {enabled, and_condition, ...fields}}}), where a
    period can have several of its 5 sources enabled at once (OR logic -
    see _get_period in __init__.py). Entries saved before that (single
    `source`/`config` pair) migrate that one active source in as enabled;
    every other type is present but disabled with blank defaults so the
    card can always show all 5 side by side. Also backfills any type - or
    any field within a type, e.g. `and_condition`/`min_time` added after a
    period was already multi-source - missing from an already-saved entry,
    so upgrading never crashes on a field that didn't exist yet when it was
    saved."""
    if "sources" in period:
        existing = period["sources"]
        sources = {}
        for source_type in PERIOD_SOURCES:
            defaults = DEFAULT_SOURCE_FIELDS[source_type]
            saved = existing.get(source_type) or {}
            merged = {"enabled": False, **defaults, **saved}
            merged["and_condition"] = {
                **defaults["and_condition"],
                **(saved.get("and_condition") or {}),
            }
            sources[source_type] = merged
        return {"id": period["id"], "name": period.get("name", ""), "sources": sources}

    old_source = period.get("source", PERIOD_SOURCE_SCHEDULE)
    old_config = period.get("config") or {}
    sources = {}
    for source_type in PERIOD_SOURCES:
        if source_type == old_source:
            sources[source_type] = {"enabled": True, **DEFAULT_SOURCE_FIELDS[source_type], **old_config}
        else:
            sources[source_type] = {"enabled": False, **DEFAULT_SOURCE_FIELDS[source_type]}
    return {"id": period["id"], "name": period.get("name", ""), "sources": sources}


def infer_periods(data: dict) -> list[dict]:
    """The single source of truth for the priority-ordered `periods` list.
    Entries saved before periods were user-editable have the old global
    time_sources/time_mode plus parallel per-period dicts (period_map/
    schedule/sun_events/illuminance_thresholds/period_booleans) instead of
    a `periods` list - migrate those into the new shape once, picking for
    every one of the 5 legacy periods the single source that would have won
    under the old fixed fallback-chain precedence (TIME_SOURCE_PRECEDENCE),
    since that one combination applied uniformly to every period before."""
    if CONF_PERIODS in data:
        return [_normalize_period(period) for period in data[CONF_PERIODS]]

    legacy_keys = (
        CONF_TIME_MODE,
        CONF_TIME_SOURCES,
        CONF_TIME_SENSOR,
        CONF_SCHEDULE,
        CONF_SUN_EVENTS,
        CONF_ILLUMINANCE_SENSOR,
        CONF_ILLUMINANCE_THRESHOLDS,
        CONF_PERIOD_BOOLEANS,
    )
    if not any(key in data for key in legacy_keys):
        # Genuinely fresh install - nothing to migrate, just start from the
        # sensible defaults rather than infer_time_mode's "sensor" default
        # (which only made sense back when CONF_TIME_SENSOR was required).
        return [_normalize_period(period) for period in DEFAULT_PERIODS]

    time_sources = infer_time_sources(data)
    chosen_source = next(
        (source for source in TIME_SOURCE_PRECEDENCE if source in time_sources),
        TIME_SOURCE_SCHEDULE,
    )

    time_sensor = data.get(CONF_TIME_SENSOR)
    period_map = data.get(CONF_PERIOD_MAP, DEFAULT_PERIOD_MAP)
    period_booleans = data.get(CONF_PERIOD_BOOLEANS, {})
    illuminance_sensor = data.get(CONF_ILLUMINANCE_SENSOR)
    illuminance_thresholds = data.get(CONF_ILLUMINANCE_THRESHOLDS, DEFAULT_ILLUMINANCE_THRESHOLDS)
    sun_events = data.get(CONF_SUN_EVENTS, DEFAULT_SUN_EVENTS)
    schedule = data.get(CONF_SCHEDULE, DEFAULT_SCHEDULE)

    periods = []
    for period_id in TIME_PERIODS:
        name = DEFAULT_PERIOD_LABELS[period_id]
        if chosen_source == TIME_SOURCE_SENSOR:
            source = PERIOD_SOURCE_SENSOR
            config = {"entity_id": time_sensor, "value": period_map.get(period_id, period_id)}
        elif chosen_source == TIME_SOURCE_BOOLEAN:
            source = PERIOD_SOURCE_BOOLEAN
            config = {"entity_id": period_booleans.get(period_id)}
        elif chosen_source == TIME_SOURCE_ILLUMINANCE:
            source = PERIOD_SOURCE_ILLUMINANCE
            config = {
                "entity_id": illuminance_sensor,
                "threshold": illuminance_thresholds.get(period_id, 0),
            }
        elif chosen_source == TIME_SOURCE_SUN:
            source = PERIOD_SOURCE_SUN
            config = dict(sun_events.get(period_id, DEFAULT_SUN_EVENTS[period_id]))
        else:  # schedule, or nothing ever configured at all
            source = PERIOD_SOURCE_SCHEDULE
            config = {"time": schedule.get(period_id, DEFAULT_SCHEDULE[period_id])}
        periods.append({"id": period_id, "name": name, "source": source, "config": config})
    return [_normalize_period(period) for period in periods]


def infer_day_type_mode(data: dict) -> str:
    if CONF_DAY_TYPE_MODE in data:
        return data[CONF_DAY_TYPE_MODE]
    return DAY_TYPE_MODE_SENSOR if data.get(CONF_DAY_TYPE_SENSOR) else DAY_TYPE_MODE_NONE


def infer_home_mode(data: dict) -> str:
    if CONF_HOME_MODE in data:
        return data[CONF_HOME_MODE]
    return HOME_MODE_SENSOR if data.get(CONF_HOME_SENSOR) else HOME_MODE_NONE
