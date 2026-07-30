import uuid

DOMAIN = "roomflow"
VERSION = "0.0.18"
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
# like a room's devices). Each period holds a list of *condition groups*
# that are OR'd together (the period is active if ANY group is true), where
# each group is a list of *conditions* that are AND'd together (the group is
# only true if ALL of its conditions hold) - i.e. arbitrary "OR of AND
# groups" logic, built from a flat pick-a-condition-type list instead of a
# fixed set of always-visible source rows. First period (list order, top =
# highest) with a true group wins - see _get_period in __init__.py.
CONF_PERIODS = "periods"  # ordered list of {id, name, condition_groups}

# Schedules: a named, independent `periods` list of its own (see CONF_PERIODS
# above) - a room picks *which* schedule governs it (room["schedule_id"]),
# so e.g. outdoor lighting can follow its own simple dusk-to-dawn window
# instead of the shared indoor morning/day/afternoon/evening/night one,
# without cluttering every other room's period list with an entry only
# relevant to one room. Every install has at least one schedule
# (DEFAULT_SCHEDULE_ID) - existing configs migrate their single top-level
# `periods` list into it once (see infer_schedules), so every room without
# an explicit schedule_id keeps behaving exactly as before.
CONF_SCHEDULES = "schedules"  # ordered list of {id, name, periods}
DEFAULT_SCHEDULE_ID = "main"
DEFAULT_SCHEDULE_NAME = "Main"

CONDITION_TYPE_TIME = "time"          # operator: after/before; value: "HH:MM:SS"
CONDITION_TYPE_SUN = "sun"            # operator: after/before; event, offset_minutes, earliest, latest
CONDITION_TYPE_NUMERIC = "numeric"    # operator: above/below/equals; entity_id, value
CONDITION_TYPE_STATE = "state"        # operator: is/is_not; entity_id, value
CONDITION_TYPE_DAY_TYPE = "day_type"  # operator: is; value: "weekday" | "weekend"
CONDITION_TYPE_HOME = "home"          # operator: is; value: "home" | "away"
CONDITION_TYPES = [
    CONDITION_TYPE_TIME,
    CONDITION_TYPE_SUN,
    CONDITION_TYPE_NUMERIC,
    CONDITION_TYPE_STATE,
    CONDITION_TYPE_DAY_TYPE,
    CONDITION_TYPE_HOME,
]

# Every condition type's own fields (besides "id"/"type", added to every
# condition) with their defaults - used both to backfill an entry saved
# before a field existed and to seed a freshly added condition of that type.
# "earliest"/"latest" on a sun condition clamp its resolved boundary to
# never be earlier/later than that fixed time on any day (e.g. sunset, but
# never before 18:00 and never after 22:00); blank means no clamp on that
# side. "value" is reused across several types for whatever that type's
# single comparison value is (a time-of-day, a sensor value, or a fixed
# weekday/weekend | home/away choice).
DEFAULT_CONDITION_FIELDS = {
    CONDITION_TYPE_TIME: {"operator": "after", "value": "00:00:00"},
    CONDITION_TYPE_SUN: {
        "operator": "after",
        "event": "sunrise",
        "offset_minutes": 0,
        "earliest": "",
        "latest": "",
    },
    CONDITION_TYPE_NUMERIC: {"operator": "above", "entity_id": None, "value": ""},
    CONDITION_TYPE_STATE: {"operator": "is", "entity_id": None, "value": "on"},
    CONDITION_TYPE_DAY_TYPE: {"operator": "is", "value": "weekend"},
    CONDITION_TYPE_HOME: {"operator": "is", "value": "away"},
}

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


def _new_condition_id() -> str:
    return uuid.uuid4().hex[:8]


def _time_condition(operator: str, value: str) -> dict:
    return {"id": _new_condition_id(), "type": CONDITION_TYPE_TIME, "operator": operator, "value": value}


def _default_condition_groups(period_id: str) -> list[dict]:
    """One bounded [after own start, before next period's start] group per
    default period, except the last (night) which wraps past midnight and
    so needs two OR'd groups instead - see the migration helpers below for
    the general form of this same shape."""
    ids = TIME_PERIODS
    idx = ids.index(period_id)
    own_time = DEFAULT_SCHEDULE[period_id]
    if idx == len(ids) - 1:
        next_time = DEFAULT_SCHEDULE[ids[0]]
        return [
            {"id": _new_condition_id(), "conditions": [_time_condition("after", own_time)]},
            {"id": _new_condition_id(), "conditions": [_time_condition("before", next_time)]},
        ]
    next_time = DEFAULT_SCHEDULE[ids[idx + 1]]
    return [
        {
            "id": _new_condition_id(),
            "conditions": [_time_condition("after", own_time), _time_condition("before", next_time)],
        }
    ]


DEFAULT_PERIODS = [
    {
        "id": period_id,
        "name": DEFAULT_PERIOD_LABELS[period_id],
        "condition_groups": _default_condition_groups(period_id),
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

# ---------------------------------------------------------------------------
# Migration: entries saved before periods used condition_groups have either
# a `sources` dict (5 fixed source types, each optionally enabled, one round
# of "combine several sources with OR" already added) or - oldest of all - a
# single `source`/`config` pair. Both migrate into the current shape below,
# on every load (see infer_periods) since the migrated shape is never
# written back to storage until the user next edits periods from the card.
_LEGACY_SOURCE_SCHEDULE = "schedule"
_LEGACY_SOURCE_SUN = "sun"
_LEGACY_SOURCE_ILLUMINANCE = "illuminance"
_LEGACY_SOURCE_BOOLEAN = "boolean"
_LEGACY_SOURCE_SENSOR = "sensor"
_LEGACY_SOURCE_TYPES = [
    _LEGACY_SOURCE_SCHEDULE,
    _LEGACY_SOURCE_SUN,
    _LEGACY_SOURCE_ILLUMINANCE,
    _LEGACY_SOURCE_BOOLEAN,
    _LEGACY_SOURCE_SENSOR,
]

_LEGACY_DEFAULT_AND_CONDITION = {"enabled": False, "entity_id": None, "operator": "above", "value": ""}

_LEGACY_DEFAULT_SOURCE_FIELDS = {
    _LEGACY_SOURCE_SCHEDULE: {"time": "00:00:00", "weekend_enabled": False, "weekend_time": "00:00:00"},
    _LEGACY_SOURCE_SUN: {
        "event": "sunrise",
        "offset_minutes": 0,
        "min_time": "00:00:00",
        "weekend_enabled": False,
        "weekend_event": "sunrise",
        "weekend_offset_minutes": 0,
    },
    _LEGACY_SOURCE_ILLUMINANCE: {"entity_id": None, "threshold": 0},
    _LEGACY_SOURCE_BOOLEAN: {"entity_id": None},
    _LEGACY_SOURCE_SENSOR: {"entity_id": None, "value": ""},
}
for _fields in _LEGACY_DEFAULT_SOURCE_FIELDS.values():
    _fields["and_condition"] = dict(_LEGACY_DEFAULT_AND_CONDITION)

# A legacy source's approximate time-of-day, in minutes since midnight, used
# only to sort/chain legacy clock sources during migration (see
# _migrate_sources_periods) - real sun-event resolution needs `hass` (not
# available in this pure module), but the *relative order* of solar events
# within a day is fixed everywhere, so a rough fixed table is enough to
# reproduce the old boundary-race priority correctly.
_SUN_EVENT_APPROX_MINUTES = {
    "midnight": 0,
    "dawn": 5 * 60 + 30,
    "sunrise": 6 * 60,
    "noon": 12 * 60,
    "sunset": 18 * 60,
    "dusk": 18 * 60 + 30,
}


def _hms_to_minutes(value: str) -> int:
    hour, minute, *_rest = (int(part) for part in value.split(":"))
    return hour * 60 + minute


def _and_condition_to_extra(and_cfg: dict | None) -> dict | None:
    """Convert a legacy source's extra AND condition (see
    _LEGACY_DEFAULT_AND_CONDITION) into an equivalent condition dict, or
    None if it was disabled/unconfigured."""
    if not and_cfg or not and_cfg.get("enabled") or not and_cfg.get("entity_id"):
        return None
    operator = and_cfg.get("operator", "above")
    if operator == "equals":
        return {
            "id": _new_condition_id(),
            "type": CONDITION_TYPE_STATE,
            "operator": "is",
            "entity_id": and_cfg["entity_id"],
            "value": and_cfg.get("value", ""),
        }
    return {
        "id": _new_condition_id(),
        "type": CONDITION_TYPE_NUMERIC,
        "operator": operator,
        "entity_id": and_cfg["entity_id"],
        "value": and_cfg.get("value", ""),
    }


def _legacy_clock_condition(kind: str, cfg: dict, weekend: bool) -> dict:
    """The primary 'after' condition for one legacy clock source (schedule
    or sun), using its weekend_* fields instead if `weekend`."""
    if kind == CONDITION_TYPE_TIME:
        value = (cfg.get("weekend_time") if weekend else cfg.get("time")) or "00:00:00"
        return _time_condition("after", value)
    event = (cfg.get("weekend_event") if weekend else cfg.get("event")) or "sunrise"
    offset = (cfg.get("weekend_offset_minutes") if weekend else cfg.get("offset_minutes")) or 0
    earliest = "" if weekend else (cfg.get("min_time") or "")
    if earliest == "00:00:00":
        earliest = ""
    return {
        "id": _new_condition_id(),
        "type": CONDITION_TYPE_SUN,
        "operator": "after",
        "event": event,
        "offset_minutes": offset,
        "earliest": earliest,
        "latest": "",
    }


def _legacy_clock_minutes(condition: dict) -> int:
    if condition["type"] == CONDITION_TYPE_TIME:
        return _hms_to_minutes(condition["value"])
    minutes = _SUN_EVENT_APPROX_MINUTES.get(condition.get("event"), 0) + (condition.get("offset_minutes") or 0)
    return minutes % 1440


def _migrate_sources_periods(entries: list[tuple[str, dict]]) -> dict[str, list[dict]]:
    """Convert a batch of legacy-shape periods (id, normalized `sources`
    dict) into {period_id: condition_groups}, resolving their *shared*
    implicit clock-boundary chain together so the result keeps behaving
    exactly like the old boundary-race algorithm did (see _get_period's
    previous implementation) - each enabled schedule/sun source becomes an
    explicit [after its own boundary, before the next one in the combined
    chain] group, wrapping the latest one past midnight into two OR'd
    groups instead of one bounded range. Independent (non-clock)
    illuminance/boolean/sensor sources don't participate in the chain -
    they become their own single-condition group each, same as their old
    independent OR'd check.

    Known limitation: a weekend override splits its own source's chain
    entry into two day-type-tagged variants, but a *neighboring* period
    with no override of its own only bounds against the weekday variant -
    on a weekend day, that can leave a brief gap (equal to the override's
    delta) where neither period's group matches. Narrow edge case (needs a
    weekend-overridden source directly adjacent to a non-split one); not
    worth the added complexity of chaining a separate weekday/weekend
    boundary sequence to close it."""
    chain: list[tuple[int, str, dict, str | None, dict | None]] = []
    result: dict[str, list[dict]] = {period_id: [] for period_id, _ in entries}

    for period_id, sources in entries:
        for kind, source_key in ((CONDITION_TYPE_TIME, _LEGACY_SOURCE_SCHEDULE), (CONDITION_TYPE_SUN, _LEGACY_SOURCE_SUN)):
            cfg = sources.get(source_key)
            if not cfg or not cfg.get("enabled"):
                continue
            and_extra = _and_condition_to_extra(cfg.get("and_condition"))
            cond = _legacy_clock_condition(kind, cfg, weekend=False)
            # A weekend override makes the two variants mutually exclusive
            # by day (the old algorithm substituted one time_str for the
            # other rather than considering both at once) - tag the normal
            # variant "weekday" too in that case, not just the override
            # "weekend", or it would also apply on weekend days.
            day_type_value = "weekday" if cfg.get("weekend_enabled") else None
            chain.append((_legacy_clock_minutes(cond), period_id, cond, day_type_value, and_extra))
            if cfg.get("weekend_enabled"):
                weekend_cond = _legacy_clock_condition(kind, cfg, weekend=True)
                chain.append((_legacy_clock_minutes(weekend_cond), period_id, weekend_cond, "weekend", and_extra))

    chain.sort(key=lambda entry: entry[0])
    count = len(chain)

    def _extra_conditions(day_type_value: str | None, and_extra: dict | None) -> list[dict]:
        extra = []
        if day_type_value:
            extra.append({"id": _new_condition_id(), "type": CONDITION_TYPE_DAY_TYPE, "operator": "is", "value": day_type_value})
        if and_extra:
            extra.append({**and_extra, "id": _new_condition_id()})
        return extra

    for i, (_, period_id, cond, day_type_value, and_extra) in enumerate(chain):
        extra = _extra_conditions(day_type_value, and_extra)

        if count == 1:
            # The only clock condition in this whole batch - the old
            # algorithm always resolved to it regardless of the time of day
            # (see _period_from_schedule's wraparound fallback), so it must
            # match all 24h: "after X" OR "before X".
            before = {**cond, "id": _new_condition_id(), "operator": "before"}
            result[period_id].append({"id": _new_condition_id(), "conditions": [dict(cond)] + extra})
            result[period_id].append({"id": _new_condition_id(), "conditions": [before] + extra})
            continue

        next_cond = chain[(i + 1) % count][2]
        before = {**next_cond, "id": _new_condition_id(), "operator": "before"}
        if i == count - 1:
            # Latest boundary of the chain - wraps past midnight into the
            # first one, so it needs two OR'd groups instead of one range.
            result[period_id].append({"id": _new_condition_id(), "conditions": [dict(cond)] + extra})
            result[period_id].append({"id": _new_condition_id(), "conditions": [before] + extra})
        else:
            result[period_id].append({"id": _new_condition_id(), "conditions": [dict(cond), before] + extra})

    _independent_sources = (
        (_LEGACY_SOURCE_ILLUMINANCE, CONDITION_TYPE_NUMERIC, "above", lambda cfg: str(cfg.get("threshold", 0))),
        (_LEGACY_SOURCE_BOOLEAN, CONDITION_TYPE_STATE, "is", lambda _cfg: "on"),
        (_LEGACY_SOURCE_SENSOR, CONDITION_TYPE_STATE, "is", lambda cfg: cfg.get("value", "")),
    )
    for period_id, sources in entries:
        for source_key, ctype, operator, value_fn in _independent_sources:
            cfg = sources.get(source_key)
            if not cfg or not cfg.get("enabled") or not cfg.get("entity_id"):
                continue
            conditions = [
                {
                    "id": _new_condition_id(),
                    "type": ctype,
                    "operator": operator,
                    "entity_id": cfg["entity_id"],
                    "value": value_fn(cfg),
                }
            ]
            and_extra = _and_condition_to_extra(cfg.get("and_condition"))
            if and_extra:
                conditions.append(and_extra)
            result[period_id].append({"id": _new_condition_id(), "conditions": conditions})

    return result


def _normalize_legacy_sources(existing: dict) -> dict:
    sources = {}
    for source_type in _LEGACY_SOURCE_TYPES:
        defaults = _LEGACY_DEFAULT_SOURCE_FIELDS[source_type]
        saved = existing.get(source_type) or {}
        merged = {"enabled": False, **defaults, **saved}
        merged["and_condition"] = {**defaults["and_condition"], **(saved.get("and_condition") or {})}
        sources[source_type] = merged
    return sources


def _legacy_sources_from_single(old_source: str, old_config: dict) -> dict:
    sources = {}
    for source_type in _LEGACY_SOURCE_TYPES:
        sources[source_type] = (
            {"enabled": True, **_LEGACY_DEFAULT_SOURCE_FIELDS[source_type], **old_config}
            if source_type == old_source
            else {"enabled": False, **_LEGACY_DEFAULT_SOURCE_FIELDS[source_type]}
        )
    return sources

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


def _normalize_condition(condition: dict) -> dict:
    """Backfill defaults for one condition, keyed by its type, so a
    condition saved before a field existed (or a whole new field added to
    its type later) never crashes evaluation."""
    ctype = condition.get("type")
    defaults = DEFAULT_CONDITION_FIELDS.get(ctype, DEFAULT_CONDITION_FIELDS[CONDITION_TYPE_TIME])
    ctype = ctype if ctype in DEFAULT_CONDITION_FIELDS else CONDITION_TYPE_TIME
    merged = {**defaults, **{k: v for k, v in condition.items() if k not in ("id", "type")}}
    return {"id": condition.get("id") or _new_condition_id(), "type": ctype, **merged}


def _normalize_condition_groups(groups: list) -> list[dict]:
    normalized = []
    for group in groups or []:
        conditions = [_normalize_condition(c) for c in (group.get("conditions") or [])]
        if conditions:
            normalized.append({"id": group.get("id") or _new_condition_id(), "conditions": conditions})
    return normalized


def _normalize_periods_list(raw_periods: list[dict]) -> list[dict]:
    """The single source of truth for turning stored period entries (in
    whichever shape they were saved in) into the current {id, name,
    condition_groups} shape. Entries already in that shape are just
    backfilled/validated; entries saved before condition_groups existed
    (a `sources` dict, or oldest of all a single `source`/`config` pair)
    are migrated together as one batch, since the old boundary-race
    algorithm they came from resolved a period's clock sources against
    *every other period's* clock sources at once - see
    _migrate_sources_periods for how that's reproduced."""
    entries = []
    for period in raw_periods:
        if "condition_groups" in period:
            entries.append(("new", period["id"], period.get("name", ""), period["condition_groups"]))
        elif "sources" in period:
            entries.append(("legacy", period["id"], period.get("name", ""), _normalize_legacy_sources(period["sources"])))
        else:
            old_source = period.get("source", _LEGACY_SOURCE_SCHEDULE)
            old_config = period.get("config") or {}
            entries.append(
                ("legacy", period["id"], period.get("name", ""), _legacy_sources_from_single(old_source, old_config))
            )

    legacy_sources = [(period_id, payload) for kind, period_id, _name, payload in entries if kind == "legacy"]
    migrated = _migrate_sources_periods(legacy_sources) if legacy_sources else {}

    result = []
    for kind, period_id, name, payload in entries:
        groups = _normalize_condition_groups(payload) if kind == "new" else migrated.get(period_id, [])
        result.append({"id": period_id, "name": name, "condition_groups": groups})
    return result


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
        return _normalize_periods_list(data[CONF_PERIODS])

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
        return _normalize_periods_list(DEFAULT_PERIODS)

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
            source = _LEGACY_SOURCE_SENSOR
            config = {"entity_id": time_sensor, "value": period_map.get(period_id, period_id)}
        elif chosen_source == TIME_SOURCE_BOOLEAN:
            source = _LEGACY_SOURCE_BOOLEAN
            config = {"entity_id": period_booleans.get(period_id)}
        elif chosen_source == TIME_SOURCE_ILLUMINANCE:
            source = _LEGACY_SOURCE_ILLUMINANCE
            config = {
                "entity_id": illuminance_sensor,
                "threshold": illuminance_thresholds.get(period_id, 0),
            }
        elif chosen_source == TIME_SOURCE_SUN:
            source = _LEGACY_SOURCE_SUN
            config = dict(sun_events.get(period_id, DEFAULT_SUN_EVENTS[period_id]))
        else:  # schedule, or nothing ever configured at all
            source = _LEGACY_SOURCE_SCHEDULE
            config = {"time": schedule.get(period_id, DEFAULT_SCHEDULE[period_id])}
        periods.append({"id": period_id, "name": name, "source": source, "config": config})
    return _normalize_periods_list(periods)


def infer_schedules(data: dict) -> list[dict]:
    """The single source of truth for the list of schedules - each an
    independently named, priority-ordered `periods` list (see
    _normalize_periods_list) that a room can opt into via its
    `schedule_id` instead of the default one. Entries saved before
    schedules existed have a flat top-level `periods` list (or older
    legacy fields still - see infer_periods) instead of CONF_SCHEDULES -
    migrate that into a single default schedule (DEFAULT_SCHEDULE_ID) so
    every existing room (which has no schedule_id yet) keeps following
    exactly the same periods as before. Always returns at least one
    schedule."""
    if CONF_SCHEDULES in data:
        schedules = [
            {
                "id": schedule["id"],
                "name": schedule.get("name", ""),
                "periods": _normalize_periods_list(schedule.get("periods") or []),
            }
            for schedule in data[CONF_SCHEDULES]
        ]
        if schedules:
            return schedules
    return [{"id": DEFAULT_SCHEDULE_ID, "name": DEFAULT_SCHEDULE_NAME, "periods": infer_periods(data)}]


def periods_for_schedule(data: dict, schedule_id: str | None) -> list[dict]:
    """A specific schedule's periods, falling back to the first schedule
    (never empty - see infer_schedules) if `schedule_id` is unset or no
    longer exists (e.g. its schedule was deleted after a room was pointed
    at it) - so a dangling reference degrades gracefully instead of
    leaving the room with no periods at all."""
    schedules = infer_schedules(data)
    match = next((s for s in schedules if s["id"] == schedule_id), None)
    return (match or schedules[0])["periods"]


def transitions_for_schedule(data: dict, schedule_id: str | None) -> dict:
    """A schedule's {period_id: seconds} default-transition map, nested
    under the top-level `default_transitions` by schedule id now that
    periods live inside per-schedule lists (see async_setup_entry's
    one-time nesting migration in __init__.py) - empty for a schedule with
    no defaults saved yet rather than falling back to another schedule's
    timings, which were tuned for that schedule's own period names."""
    return (data.get("default_transitions") or {}).get(schedule_id) or {}


def infer_day_type_mode(data: dict) -> str:
    if CONF_DAY_TYPE_MODE in data:
        return data[CONF_DAY_TYPE_MODE]
    return DAY_TYPE_MODE_SENSOR if data.get(CONF_DAY_TYPE_SENSOR) else DAY_TYPE_MODE_NONE


def infer_home_mode(data: dict) -> str:
    if CONF_HOME_MODE in data:
        return data[CONF_HOME_MODE]
    return HOME_MODE_SENSOR if data.get(CONF_HOME_SENSOR) else HOME_MODE_NONE
