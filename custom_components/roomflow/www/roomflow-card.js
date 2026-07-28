// RoomFlow - custom Lovelace card / sidebar panel
// Place this file at /config/www/roomflow-card.js and register it as a
// resource: Settings -> Dashboards -> Resources -> /local/roomflow-card.js
// (JavaScript module)

// Schedules are a user-editable list stored in this._config_data.schedules
// (mirrors const.py's `schedules`/infer_schedules - each {id, name,
// periods}), each an independently named, priority-ordered `periods` list.
// A room follows one schedule at a time (room.schedule_id), so e.g.
// outdoor lighting can have its own simple on/off window instead of the
// shared indoor one. A period is active if ANY of its condition groups is
// true (OR across groups); a group is true only if ALL of its conditions
// hold (AND within a group) - i.e. "OR of AND groups", built by picking a
// condition type from a flat list instead of a fixed set of always-visible
// source rows. First period (list order, top = highest) with a true group
// wins - see _get_period in __init__.py.

const CONDITION_TYPES = [
  { key: "time", labelKey: "condition_type_time" },
  { key: "sun", labelKey: "condition_type_sun" },
  { key: "numeric", labelKey: "condition_type_numeric" },
  { key: "state", labelKey: "condition_type_state" },
  { key: "day_type", labelKey: "condition_type_day_type" },
  { key: "home", labelKey: "condition_type_home" },
];

// Every condition type's own fields (besides "id"/"type") with their
// defaults - mirrors const.py's DEFAULT_CONDITION_FIELDS, used both to
// backfill an entry saved before a field existed and to seed a freshly
// added condition of that type. "value" is reused across types for
// whatever that type's single comparison value is (a time-of-day, a
// sensor value, or a fixed weekday/weekend | home/away choice).
const DEFAULT_CONDITION_FIELDS = {
  time: { operator: "after", value: "00:00:00" },
  sun: { operator: "after", event: "sunrise", offset_minutes: 0, earliest: "", latest: "" },
  numeric: { operator: "above", entity_id: null, value: "" },
  state: { operator: "is", entity_id: null, value: "on" },
  day_type: { operator: "is", value: "weekend" },
  home: { operator: "is", value: "away" },
};

function normalizeCondition(condition) {
  const ctype = DEFAULT_CONDITION_FIELDS[condition.type] ? condition.type : "time";
  const defaults = DEFAULT_CONDITION_FIELDS[ctype];
  const rest = { ...condition };
  delete rest.id;
  delete rest.type;
  return { id: condition.id || uid(), type: ctype, ...defaults, ...rest };
}

function normalizeConditionGroups(groups) {
  return (groups || [])
    .map((group) => ({ id: group.id || uid(), conditions: (group.conditions || []).map(normalizeCondition) }))
    .filter((group) => group.conditions.length > 0);
}

// ---------- legacy period migration ----------
// Entries saved before periods used condition_groups have either a
// `sources` dict (5 fixed source types, each optionally enabled) or -
// oldest of all - a single `source`/`config` pair. Both migrate into the
// current shape below, mirroring const.py's _migrate_sources_periods /
// _normalize_periods_list - see that module for the full reasoning (the
// old boundary-race algorithm resolved a period's clock sources against
// *every other period's* clock sources at once, so the migration has to
// too, batching every legacy period together rather than one at a time).
const LEGACY_SOURCE_TYPES = ["schedule", "sun", "illuminance", "boolean", "sensor"];
const LEGACY_DEFAULT_AND_CONDITION = { enabled: false, entity_id: null, operator: "above", value: "" };
const LEGACY_DEFAULT_SOURCE_FIELDS = {
  schedule: { time: "00:00:00", weekend_enabled: false, weekend_time: "00:00:00" },
  sun: {
    event: "sunrise",
    offset_minutes: 0,
    min_time: "00:00:00",
    weekend_enabled: false,
    weekend_event: "sunrise",
    weekend_offset_minutes: 0,
  },
  illuminance: { entity_id: null, threshold: 0 },
  boolean: { entity_id: null },
  sensor: { entity_id: null, value: "" },
};
LEGACY_SOURCE_TYPES.forEach((key) => {
  LEGACY_DEFAULT_SOURCE_FIELDS[key].and_condition = { ...LEGACY_DEFAULT_AND_CONDITION };
});

// A legacy source's approximate time-of-day, in minutes since midnight,
// used only to sort/chain legacy clock sources during migration - the
// *relative* order of solar events within a day is fixed everywhere, so a
// rough fixed table is enough to reproduce the old boundary-race priority
// correctly without needing hass/astral access.
const SUN_EVENT_APPROX_MINUTES = {
  midnight: 0,
  dawn: 5 * 60 + 30,
  sunrise: 6 * 60,
  noon: 12 * 60,
  sunset: 18 * 60,
  dusk: 18 * 60 + 30,
};

function hmsToMinutes(value) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function andConditionToExtra(andCfg) {
  if (!andCfg || !andCfg.enabled || !andCfg.entity_id) return null;
  const operator = andCfg.operator || "above";
  if (operator === "equals") {
    return { id: uid(), type: "state", operator: "is", entity_id: andCfg.entity_id, value: andCfg.value || "" };
  }
  return { id: uid(), type: "numeric", operator, entity_id: andCfg.entity_id, value: andCfg.value || "" };
}

function legacyClockCondition(kind, cfg, weekend) {
  if (kind === "time") {
    const value = (weekend ? cfg.weekend_time : cfg.time) || "00:00:00";
    return { id: uid(), type: "time", operator: "after", value };
  }
  const event = (weekend ? cfg.weekend_event : cfg.event) || "sunrise";
  const offset = (weekend ? cfg.weekend_offset_minutes : cfg.offset_minutes) || 0;
  let earliest = weekend ? "" : cfg.min_time || "";
  if (earliest === "00:00:00") earliest = "";
  return { id: uid(), type: "sun", operator: "after", event, offset_minutes: offset, earliest, latest: "" };
}

function legacyClockMinutes(condition) {
  if (condition.type === "time") return hmsToMinutes(condition.value);
  const minutes = (SUN_EVENT_APPROX_MINUTES[condition.event] || 0) + (condition.offset_minutes || 0);
  return ((minutes % 1440) + 1440) % 1440;
}

// Convert a batch of legacy-shape periods (id, normalized `sources` dict)
// into {periodId: condition_groups} - see the header comment above.
function migrateSourcesPeriods(entries) {
  const chain = [];
  const result = {};
  entries.forEach(([periodId]) => {
    result[periodId] = [];
  });

  entries.forEach(([periodId, sources]) => {
    [
      ["time", "schedule"],
      ["sun", "sun"],
    ].forEach(([kind, sourceKey]) => {
      const cfg = sources[sourceKey];
      if (!cfg || !cfg.enabled) return;
      const andExtra = andConditionToExtra(cfg.and_condition);
      const cond = legacyClockCondition(kind, cfg, false);
      // A weekend override makes the two variants mutually exclusive by
      // day (the old algorithm substituted one time_str for the other
      // rather than considering both at once) - tag the normal variant
      // "weekday" too in that case, not just the override "weekend".
      const dayTypeValue = cfg.weekend_enabled ? "weekday" : null;
      chain.push([legacyClockMinutes(cond), periodId, cond, dayTypeValue, andExtra]);
      if (cfg.weekend_enabled) {
        const weekendCond = legacyClockCondition(kind, cfg, true);
        chain.push([legacyClockMinutes(weekendCond), periodId, weekendCond, "weekend", andExtra]);
      }
    });
  });

  chain.sort((a, b) => a[0] - b[0]);
  const count = chain.length;

  function extraConditions(dayTypeValue, andExtra) {
    const extra = [];
    if (dayTypeValue) extra.push({ id: uid(), type: "day_type", operator: "is", value: dayTypeValue });
    if (andExtra) extra.push({ ...andExtra, id: uid() });
    return extra;
  }

  chain.forEach(([, periodId, cond, dayTypeValue, andExtra], i) => {
    const extra = extraConditions(dayTypeValue, andExtra);

    if (count === 1) {
      // The only clock condition in this whole batch - the old algorithm
      // always resolved to it regardless of time of day, so it must match
      // all 24h: "after X" OR "before X".
      const before = { ...cond, id: uid(), operator: "before" };
      result[periodId].push({ id: uid(), conditions: [{ ...cond }, ...extra] });
      result[periodId].push({ id: uid(), conditions: [before, ...extra] });
      return;
    }

    const nextCond = chain[(i + 1) % count][2];
    const before = { ...nextCond, id: uid(), operator: "before" };
    if (i === count - 1) {
      // Latest boundary of the chain - wraps past midnight into the
      // first one, so it needs two OR'd groups instead of one range.
      result[periodId].push({ id: uid(), conditions: [{ ...cond }, ...extra] });
      result[periodId].push({ id: uid(), conditions: [before, ...extra] });
    } else {
      result[periodId].push({ id: uid(), conditions: [{ ...cond }, before, ...extra] });
    }
  });

  const independentSources = [
    ["illuminance", "numeric", "above", (cfg) => String(cfg.threshold ?? 0)],
    ["boolean", "state", "is", () => "on"],
    ["sensor", "state", "is", (cfg) => cfg.value || ""],
  ];
  entries.forEach(([periodId, sources]) => {
    independentSources.forEach(([sourceKey, ctype, operator, valueFn]) => {
      const cfg = sources[sourceKey];
      if (!cfg || !cfg.enabled || !cfg.entity_id) return;
      const conditions = [{ id: uid(), type: ctype, operator, entity_id: cfg.entity_id, value: valueFn(cfg) }];
      const andExtra = andConditionToExtra(cfg.and_condition);
      if (andExtra) conditions.push(andExtra);
      result[periodId].push({ id: uid(), conditions });
    });
  });

  return result;
}

function normalizeLegacySources(existing) {
  const sources = {};
  LEGACY_SOURCE_TYPES.forEach((key) => {
    const defaults = LEGACY_DEFAULT_SOURCE_FIELDS[key];
    const saved = existing[key] || {};
    sources[key] = {
      enabled: false,
      ...defaults,
      ...saved,
      and_condition: { ...defaults.and_condition, ...(saved.and_condition || {}) },
    };
  });
  return sources;
}

function legacySourcesFromSingle(oldSource, oldConfig) {
  const sources = {};
  LEGACY_SOURCE_TYPES.forEach((key) => {
    sources[key] =
      key === oldSource
        ? { enabled: true, ...LEGACY_DEFAULT_SOURCE_FIELDS[key], ...oldConfig }
        : { enabled: false, ...LEGACY_DEFAULT_SOURCE_FIELDS[key] };
  });
  return sources;
}

// The single source of truth for turning a whole stored `periods` list
// (in whichever shape each entry was saved in) into the current {id,
// name, condition_groups} shape - mirrors const.py's
// _normalize_periods_list. Must see every legacy-shape entry at once (not
// one period at a time) since their implicit clock-boundary chain spans
// all of them together.
function normalizePeriodsList(rawPeriods) {
  const entries = rawPeriods.map((period) => {
    if (period.condition_groups) {
      return { kind: "new", id: period.id, name: period.name || "", payload: period.condition_groups };
    }
    if (period.sources) {
      return { kind: "legacy", id: period.id, name: period.name || "", payload: normalizeLegacySources(period.sources) };
    }
    const oldSource = period.source || "schedule";
    const oldConfig = period.config || {};
    return {
      kind: "legacy",
      id: period.id,
      name: period.name || "",
      payload: legacySourcesFromSingle(oldSource, oldConfig),
    };
  });

  const legacyEntries = entries.filter((e) => e.kind === "legacy").map((e) => [e.id, e.payload]);
  const migrated = legacyEntries.length ? migrateSourcesPeriods(legacyEntries) : {};

  return entries.map((e) => ({
    id: e.id,
    name: e.name,
    condition_groups: e.kind === "new" ? normalizeConditionGroups(e.payload) : migrated[e.id] || [],
  }));
}

// Schedules: a named, independent `periods` list of its own - a room picks
// which schedule governs it (room.schedule_id), so e.g. outdoor lighting can
// follow its own simple dusk-to-dawn window instead of the shared indoor
// morning/day/afternoon/evening/night one. Mirrors const.py's
// CONF_SCHEDULES/infer_schedules; every install has at least one schedule
// (DEFAULT_SCHEDULE_ID).
const DEFAULT_SCHEDULE_ID = "main";
const DEFAULT_SCHEDULE_NAME = "Main";

function normalizeSchedule(schedule) {
  return {
    id: schedule.id || uid(),
    name: schedule.name || "",
    periods: normalizePeriodsList(schedule.periods || []),
  };
}

// Keys must match actual astral.sun attribute names (what Home Assistant's
// get_astral_event_date looks up) - "noon"/"midnight", not "solar_noon"/
// "solar_midnight".
const SUN_EVENTS = [
  { key: "dawn", labelKey: "sun_event_dawn" },
  { key: "sunrise", labelKey: "sun_event_sunrise" },
  { key: "noon", labelKey: "sun_event_noon" },
  { key: "sunset", labelKey: "sun_event_sunset" },
  { key: "dusk", labelKey: "sun_event_dusk" },
  { key: "midnight", labelKey: "sun_event_midnight" },
];

const WEEKDAYS = [
  { key: "mon", labelKey: "weekday_mon" },
  { key: "tue", labelKey: "weekday_tue" },
  { key: "wed", labelKey: "weekday_wed" },
  { key: "thu", labelKey: "weekday_thu" },
  { key: "fri", labelKey: "weekday_fri" },
  { key: "sat", labelKey: "weekday_sat" },
  { key: "sun", labelKey: "weekday_sun" },
];

const DEFAULT_TRANSITIONS = { morning: 1, day: 0, afternoon: 0, evening: 2, night: 3 };
const DEFAULT_WEEKEND_DAYS = ["sat", "sun"];

// The 5 starting periods for a fresh install (or migrating from an old
// install that never had a `periods` list) - schedule-sourced, ids match
// the old fixed canonical names 1:1 so existing device behavior data
// (keyed by these same strings) needs no migration of its own.
const DEFAULT_PERIOD_IDS = ["morning", "day", "afternoon", "evening", "night"];
const DEFAULT_PERIOD_NAMES = {
  morning: "Morning",
  day: "Day",
  afternoon: "Afternoon",
  evening: "Evening",
  night: "Night",
};
const DEFAULT_SCHEDULE = { morning: "06:00:00", day: "10:00:00", afternoon: "13:00:00", evening: "18:00:00", night: "22:00:00" };

function buildDefaultPeriods() {
  return DEFAULT_PERIOD_IDS.map((id) => ({
    id,
    name: DEFAULT_PERIOD_NAMES[id],
    source: "schedule",
    config: { time: DEFAULT_SCHEDULE[id] },
  }));
}

// One-time migration for installs saved before periods were user-editable:
// they have the old global time_sources/time_mode plus parallel per-period
// dicts instead of a `periods` list. Mirrors const.py's infer_periods -
// picks, for every one of the 5 legacy periods, the single source that
// would have won under the old fixed fallback-chain precedence, since that
// one combination applied uniformly to every period before.
const TIME_SOURCE_PRECEDENCE = ["sensor", "boolean", "illuminance", "sun", "schedule"];
const DEFAULT_PERIOD_MAP = { morning: "morning", day: "day", afternoon: "afternoon", evening: "evening", night: "night" };
const DEFAULT_SUN_EVENTS = {
  morning: { event: "dawn", offset_minutes: 0 },
  day: { event: "sunrise", offset_minutes: 0 },
  afternoon: { event: "noon", offset_minutes: 0 },
  evening: { event: "sunset", offset_minutes: 0 },
  night: { event: "dusk", offset_minutes: 0 },
};
const DEFAULT_ILLUMINANCE_THRESHOLDS = { night: 0, morning: 10, evening: 50, afternoon: 300, day: 1000 };

function buildPeriodsFromLegacy(cd) {
  const legacyKeys = [
    "time_mode", "time_sources", "time_sensor", "schedule", "sun_events",
    "illuminance_sensor", "illuminance_thresholds", "period_booleans",
  ];
  if (!legacyKeys.some((k) => cd[k] !== undefined)) {
    return buildDefaultPeriods();
  }

  const timeSources = cd.time_sources || (cd.time_mode ? [cd.time_mode] : cd.time_sensor ? ["sensor"] : []);
  const chosenSource = TIME_SOURCE_PRECEDENCE.find((s) => timeSources.includes(s)) || "schedule";

  const periodMap = cd.period_map || DEFAULT_PERIOD_MAP;
  const periodBooleans = cd.period_booleans || {};
  const illuminanceThresholds = cd.illuminance_thresholds || DEFAULT_ILLUMINANCE_THRESHOLDS;
  const sunEvents = cd.sun_events || DEFAULT_SUN_EVENTS;
  const schedule = cd.schedule || DEFAULT_SCHEDULE;

  return DEFAULT_PERIOD_IDS.map((id) => {
    const name = DEFAULT_PERIOD_NAMES[id];
    if (chosenSource === "sensor") {
      return { id, name, source: "sensor", config: { entity_id: cd.time_sensor, value: periodMap[id] || id } };
    }
    if (chosenSource === "boolean") {
      return { id, name, source: "boolean", config: { entity_id: periodBooleans[id] } };
    }
    if (chosenSource === "illuminance") {
      return {
        id, name, source: "illuminance",
        config: { entity_id: cd.illuminance_sensor, threshold: illuminanceThresholds[id] ?? 0 },
      };
    }
    if (chosenSource === "sun") {
      const ev = sunEvents[id] || DEFAULT_SUN_EVENTS[id];
      return { id, name, source: "sun", config: { event: ev.event, offset_minutes: ev.offset_minutes || 0 } };
    }
    return { id, name, source: "schedule", config: { time: schedule[id] || DEFAULT_SCHEDULE[id] } };
  });
}

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function parseDeviceKey(deviceKey) {
  const idx = deviceKey.indexOf(":");
  return { roomId: deviceKey.slice(0, idx), entityId: deviceKey.slice(idx + 1) };
}

function emptyVariant(base, withToggle) {
  const v = { ...base };
  if (withToggle) v.enabled = false;
  return v;
}

// ---------- i18n ----------
// The card has no build step, so this is a plain in-file lookup table
// (keyed by ISO language code) rather than separate translation files or
// Home Assistant's own frontend translation system. English is the
// canonical set of keys; every other language falls back to English for
// any key it doesn't have, so an incomplete/future translation never
// breaks rendering. Room/device/period/condition *names* the user typed
// in themselves are data, not UI copy, and are never looked up here.
const STRINGS = {
  en: {
    tab_add_room: "+ Room",
    tab_buttons: "Buttons",
    tab_settings: "Settings",
    test_all: "Test all",

    add_room_header: "Add room",
    custom_name_option: "— Custom name —",
    room_name_placeholder: "Room name",
    add: "Add",
    add_room_help: "Picking an area adds its lights/outlets to the room automatically.",

    seconds: "seconds",
    day_type_condition_label: "Day-type condition (weekend):",
    home_away_condition_label: "Home/away condition:",
    status_enabled: "enabled",
    status_not_configured: "not configured",
    enable_more_conditions_help:
      "Set the relevant source below (Weekday/weekend and/or Home/away) to enable more conditions.",
    default_transition_header: "Default transition time",
    room_schedule_label: "Schedule",

    operator_above: "is above",
    operator_below: "is below",
    operator_equals: "equals",
    operator_after: "after",
    operator_before: "before",
    operator_is: "is",
    operator_is_not: "is not",

    min_offset: "min offset",
    lx: "lx",
    value_placeholder: "value",
    earliest_label: "· earliest",
    latest_label: "· latest",

    condition_type_time: "Time",
    condition_type_sun: "Sun position",
    condition_type_numeric: "Numeric sensor",
    condition_type_state: "Sensor state",
    condition_type_day_type: "Weekday/weekend",
    condition_type_home: "Home/away",
    condition_value_weekday: "weekday",
    condition_value_weekend: "weekend",
    condition_value_home: "home",
    condition_value_away: "away",

    sun_event_dawn: "Dawn",
    sun_event_sunrise: "Sunrise",
    sun_event_noon: "Solar noon",
    sun_event_sunset: "Sunset",
    sun_event_dusk: "Dusk",
    sun_event_midnight: "Solar midnight",

    schedules_header: "Schedules",
    schedules_help:
      "Each schedule is its own independent, priority-ordered list of periods (top wins) - the first period with a true condition group is the current one for that schedule. A room follows one schedule at a time (set when adding it), so e.g. outdoor lighting can have its own simple on/off window instead of the shared indoor one. Each period is a list of OR'd groups (any group being true makes the period active); each group is a list of AND'd conditions (all of them must hold). Pick a condition type to add one.",
    and_within_group_help: "All conditions below must hold (AND)",
    or_between_groups_label: "or",
    add_condition_placeholder: "+ Add condition...",
    add_condition_group: "+ Add OR group",
    name_placeholder: "Name",
    add_period: "+ Add period",
    add_schedule: "+ Add schedule",
    schedule_name_placeholder: "Schedule name",
    schedule_fallback_name: "Schedule",
    new_schedule_name: "New schedule",

    day_type_sensor_help: 'For a plain on/off sensor (no "weekend"/"helg"-style text), pick what "on" means:',
    day_type_sensor_inverted_label:
      '"On" means weekday (e.g. a workday/jobbdag-style sensor) - unchecked means "on" = weekend',
    weekend_days_help: 'Which days count as "weekend":',
    weekday_weekend_header: "Weekday/weekend",
    option_not_used: "Not used",
    option_existing_sensor: "Existing sensor",
    option_weekday_selection: "Weekday selection",

    weekday_mon: "Monday",
    weekday_tue: "Tuesday",
    weekday_wed: "Wednesday",
    weekday_thu: "Thursday",
    weekday_fri: "Friday",
    weekday_sat: "Saturday",
    weekday_sun: "Sunday",

    home_away_header: "Home/away",
    option_person_entities: "Person entities",
    add_person: "+ Add",

    device_header: "Device",
    device_help: "Groups RoomFlow's own sensors (current period, day type, home state, per-period booleans).",
    no_area_option: "— No area —",

    buttons_header: "Physical buttons",
    buttons_help:
      'Bind a physical button/remote (e.g. a Zigbee button that shows up as an "event" or "sensor" entity in Home Assistant) to an action in a room.',
    add_button_header: "Add button",
    new_button_entity_placeholder: "entity_id (e.g. event.kitchen_button)",
    choose_room_option: "Choose room…",
    action_toggle: "Toggle on/off",
    action_off: "Turn off room",
    action_apply_now: "Run scheduled behavior now",
    action_force_period: "Force a specific period",
    room_missing: "(room missing)",

    motion_sensor_value_above: "Sensor value above",
    motion_label: "Motion",
    motion_active_label: "Motion control active in this room",
    motion_or_logic_help: 'The room counts as "active" if ANY condition below is currently true (OR logic).',
    add_motion_sensor: "+ Motion sensor",
    add_threshold: "+ Threshold (e.g. humidity)",
    turn_off_after: "Turn off after",
    turn_off_after_suffix: "minutes with no condition true (default for devices below with no override of their own)",
    dim_warning_label: "Dim as a warning before turning off",
    dim_to: "Dim to",
    brightness_for: "brightness for",
    minutes_before_off: "minutes before turning off - motion during this window restores full brightness instead.",
    motion_footer_help:
      'When active, the room\'s scheduled behavior runs immediately (like "Test now"). Pick which devices react to motion, and their own off-delay, on each device below.',

    condition_is: "is",
    custom_conditions_header: "Custom conditions",
    custom_conditions_help:
      "Room-specific overrides, checked in priority order (top wins) - above away/weekend/default. Each gets its own morning/day/afternoon/evening/night behavior per device below, same as away/weekend.",
    add_condition: "+ Add condition",

    test_now: "Test now",
    remove_room: "Remove room",
    add_device_option: "+ Add device…",

    default_variant_help:
      "Let the schedule control this period (uncheck to leave this device alone here - e.g. button/manual only)",
    custom_setting_for: "Custom setting for {label}",
    on_label: "On",
    brightness_label: "Brightness:",
    color_temp_label: "Color temp (K):",

    variant_default: "Default",
    variant_weekend: "Weekend",
    variant_away: "Away",
    condition_fallback_name: "Condition",

    transition_time_label: "Transition time (sec) — default is {s}s:",
    device_motion_reacts: "Reacts to this room's motion/threshold triggers",
    device_off_after: "Off after",
    device_off_after_suffix: "minutes (blank = room default)",

    status_unavailable: "· unavailable",
    status_on: "· now: on",
    status_on_pct: "· now: on ({pct}%)",
    status_off: "· now: off",

    applying: "Applying…",
    done: "Done!",

    new_condition_name: "New condition",
    new_period_name: "New period",
    period_fallback_name: "Period",

    loading: "Loading…",
  },

  sv: {
    tab_add_room: "+ Rum",
    tab_buttons: "Knappar",
    tab_settings: "Inställningar",
    test_all: "Testa alla",

    add_room_header: "Lägg till rum",
    custom_name_option: "— Eget namn —",
    room_name_placeholder: "Rumsnamn",
    add: "Lägg till",
    add_room_help: "Att välja en area lägger automatiskt till dess lampor/uttag i rummet.",

    seconds: "sekunder",
    day_type_condition_label: "Dagstyp-villkor (helg):",
    home_away_condition_label: "Hemma/borta-villkor:",
    status_enabled: "aktiverat",
    status_not_configured: "inte konfigurerat",
    enable_more_conditions_help:
      "Ställ in relevant källa nedan (Vardag/helg och/eller Hemma/borta) för att aktivera fler villkor.",
    default_transition_header: "Standard transitionstid",
    room_schedule_label: "Schema",

    operator_above: "är över",
    operator_below: "är under",
    operator_equals: "är lika med",
    operator_after: "efter",
    operator_before: "före",
    operator_is: "är",
    operator_is_not: "är inte",

    min_offset: "min offset",
    lx: "lx",
    value_placeholder: "värde",
    earliest_label: "· tidigast",
    latest_label: "· senast",

    condition_type_time: "Klockslag",
    condition_type_sun: "Solens position",
    condition_type_numeric: "Numerisk sensor",
    condition_type_state: "Sensortillstånd",
    condition_type_day_type: "Vardag/helg",
    condition_type_home: "Hemma/borta",
    condition_value_weekday: "vardag",
    condition_value_weekend: "helg",
    condition_value_home: "hemma",
    condition_value_away: "borta",

    sun_event_dawn: "Gryning",
    sun_event_sunrise: "Soluppgång",
    sun_event_noon: "Solmiddag",
    sun_event_sunset: "Solnedgång",
    sun_event_dusk: "Skymning",
    sun_event_midnight: "Solmidnatt",

    schedules_header: "Scheman",
    schedules_help:
      "Varje schema är sin egen oberoende, prioritetsordnade lista av perioder (överst vinner) - den första perioden med en sann villkorsgrupp är den aktuella för det schemat. Ett rum följer ett schema åt gången (valt när det läggs till), så t.ex. ytterbelysning kan ha sitt eget enkla på/av-fönster istället för det delade inomhusschemat. Varje period är en lista av ELLER-ihopkopplade grupper (perioden är aktiv om NÅGON grupp är sann); varje grupp är en lista av OCH-ihopkopplade villkor (alla måste stämma). Välj en villkorstyp för att lägga till ett.",
    and_within_group_help: "Alla villkor nedan måste stämma (OCH)",
    or_between_groups_label: "eller",
    add_condition_placeholder: "+ Lägg till villkor...",
    add_condition_group: "+ Lägg till ELLER-grupp",
    name_placeholder: "Namn",
    add_period: "+ Lägg till period",
    add_schedule: "+ Lägg till schema",
    schedule_name_placeholder: "Schemanamn",
    schedule_fallback_name: "Schema",
    new_schedule_name: "Nytt schema",

    day_type_sensor_help: 'För en vanlig på/av-sensor (ingen "weekend"/"helg"-liknande text), välj vad "på" betyder:',
    day_type_sensor_inverted_label:
      '"På" betyder vardag (t.ex. en jobbdag-liknande sensor) - avkryssad betyder "på" = helg',
    weekend_days_help: 'Vilka dagar räknas som "helg":',
    weekday_weekend_header: "Vardag/helg",
    option_not_used: "Används inte",
    option_existing_sensor: "Befintlig sensor",
    option_weekday_selection: "Veckodagsval",

    weekday_mon: "Måndag",
    weekday_tue: "Tisdag",
    weekday_wed: "Onsdag",
    weekday_thu: "Torsdag",
    weekday_fri: "Fredag",
    weekday_sat: "Lördag",
    weekday_sun: "Söndag",

    home_away_header: "Hemma/borta",
    option_person_entities: "Personentiteter",
    add_person: "+ Lägg till",

    device_header: "Enhet",
    device_help: "Grupperar RoomFlows egna sensorer (aktuell period, dagstyp, hemma-status, per-period-booleaner).",
    no_area_option: "— Ingen area —",

    buttons_header: "Fysiska knappar",
    buttons_help:
      'Bind en fysisk knapp/fjärrkontroll (t.ex. en Zigbee-knapp som visas som en "event"- eller "sensor"-entitet i Home Assistant) till en åtgärd i ett rum.',
    add_button_header: "Lägg till knapp",
    new_button_entity_placeholder: "entity_id (t.ex. event.kitchen_button)",
    choose_room_option: "Välj rum…",
    action_toggle: "Växla på/av",
    action_off: "Stäng av rum",
    action_apply_now: "Kör schemalagt beteende nu",
    action_force_period: "Tvinga en specifik period",
    room_missing: "(rum saknas)",

    motion_sensor_value_above: "Sensorvärde över",
    motion_label: "Rörelse",
    motion_active_label: "Rörelsekontroll aktiv i det här rummet",
    motion_or_logic_help: 'Rummet räknas som "aktivt" om NÅGOT villkor nedan just nu är sant (ELLER-logik).',
    add_motion_sensor: "+ Rörelsesensor",
    add_threshold: "+ Tröskelvärde (t.ex. luftfuktighet)",
    turn_off_after: "Stäng av efter",
    turn_off_after_suffix: "minuter utan att något villkor är sant (standard för enheter nedan utan egen inställning)",
    dim_warning_label: "Dimra som en varning innan avstängning",
    dim_to: "Dimra till",
    brightness_for: "ljusstyrka i",
    minutes_before_off: "minuter innan avstängning - rörelse under det fönstret återställer full ljusstyrka istället.",
    motion_footer_help:
      'När aktivt körs rummets schemalagda beteende direkt (som "Testa nu"). Välj vilka enheter som reagerar på rörelse, och deras egen avstängningsfördröjning, på varje enhet nedan.',

    condition_is: "är",
    custom_conditions_header: "Egna villkor",
    custom_conditions_help:
      "Rumsspecifika undantag, kontrollerade i prioritetsordning (överst vinner) - ovanför borta/helg/standard. Varje villkor får sin egen morgon/dag/eftermiddag/kväll/natt-beteendevariant per enhet nedan, precis som helg/borta.",
    add_condition: "+ Lägg till villkor",

    test_now: "Testa nu",
    remove_room: "Ta bort rum",
    add_device_option: "+ Lägg till enhet…",

    default_variant_help:
      "Låt schemat styra den här perioden (avmarkera för att lämna den här enheten ifred här - t.ex. knapp/manuellt läge)",
    custom_setting_for: "Egen inställning för {label}",
    on_label: "På",
    brightness_label: "Ljusstyrka:",
    color_temp_label: "Färgtemp (K):",

    variant_default: "Standard",
    variant_weekend: "Helg",
    variant_away: "Borta",
    condition_fallback_name: "Villkor",

    transition_time_label: "Transitionstid (sek) — standard är {s}s:",
    device_motion_reacts: "Reagerar på det här rummets rörelse-/tröskelvärdestriggers",
    device_off_after: "Av efter",
    device_off_after_suffix: "minuter (tomt = rummets standard)",

    status_unavailable: "· otillgänglig",
    status_on: "· nu: på",
    status_on_pct: "· nu: på ({pct}%)",
    status_off: "· nu: av",

    applying: "Tillämpar…",
    done: "Klart!",

    new_condition_name: "Nytt villkor",
    new_period_name: "Ny period",
    period_fallback_name: "Period",

    loading: "Laddar…",
  },

  no: {
    tab_add_room: "+ Rom",
    tab_buttons: "Knapper",
    tab_settings: "Innstillinger",
    test_all: "Test alle",

    add_room_header: "Legg til rom",
    custom_name_option: "— Eget navn —",
    room_name_placeholder: "Romnavn",
    add: "Legg til",
    add_room_help: "Å velge et område legger automatisk til dets lys/stikkontakter i rommet.",

    seconds: "sekunder",
    day_type_condition_label: "Dagstype-betingelse (helg):",
    home_away_condition_label: "Hjemme/borte-betingelse:",
    status_enabled: "aktivert",
    status_not_configured: "ikke konfigurert",
    enable_more_conditions_help:
      "Sett relevant kilde nedenfor (Hverdag/helg og/eller Hjemme/borte) for å aktivere flere betingelser.",
    default_transition_header: "Standard overgangstid per periode",
    default_transition_help:
      "Gjelder alle lys, med mindre en enkelt enhet har sin egen overgangstid satt.",

    weekend_override_time: "Annet tidspunkt i helgen",
    weekend_override_sun: "Annen solhendelse i helgen",

    operator_above: "er over",
    operator_below: "er under",
    operator_equals: "er lik",
    and_condition_label: "Krev også en sensorbetingelse",

    never_before: "· aldri før",
    min_time_title:
      "Gulv - det beregnede starttidspunktet er aldri tidligere enn dette, selv om solhendelsen er det. 00:00 = ingen begrensning.",
    min_offset: "min offset",
    lx: "lx",
    value_placeholder: "verdi",

    source_schedule: "Tidsplan",
    source_sun: "Solens posisjon",
    source_illuminance: "Lyssensor",
    source_boolean: "Eksisterende boolsk",
    source_sensor: "Eksisterende sensor",

    sun_event_dawn: "Demring",
    sun_event_sunrise: "Soloppgang",
    sun_event_noon: "Middag",
    sun_event_sunset: "Solnedgang",
    sun_event_dusk: "Skumring",
    sun_event_midnight: "Solmidnatt",

    periods_header: "Tid-på-døgnet-perioder",
    periods_help:
      'Prioritetsrekkefølge (øverst vinner) - den første perioden med en aktivert kilde som for øyeblikket er "aktiv" er den gjeldende perioden. Legg til, fjern, gi nytt navn eller endre rekkefølge fritt; kryss av for hvilke kilder du vil at hver periode skal bruke - hvis mer enn én er krysset av, er perioden aktiv når NOEN av dem sier det.',
    periods_help_weekend_yes: "Tidsplan-/sol-kilder kan også ha et annet tidspunkt i helger.",
    periods_help_weekend_no: "Sett en Hverdag/helg-kilde nedenfor for å låse opp et helgeunntak for tidsplan-/sol-kilder.",
    name_placeholder: "Navn",
    add_period: "+ Legg til periode",

    day_type_sensor_help: 'For en vanlig på/av-sensor (ingen "weekend"/"helg"-lignende tekst), velg hva "på" betyr:',
    day_type_sensor_inverted_label:
      '"På" betyr hverdag (f.eks. en hverdag/jobbdag-lignende sensor) - avkrysset betyr "på" = helg',
    weekend_days_help: 'Hvilke dager teller som "helg":',
    weekday_weekend_header: "Hverdag/helg",
    option_not_used: "Ikke i bruk",
    option_existing_sensor: "Eksisterende sensor",
    option_weekday_selection: "Ukedagsvalg",

    weekday_mon: "Mandag",
    weekday_tue: "Tirsdag",
    weekday_wed: "Onsdag",
    weekday_thu: "Torsdag",
    weekday_fri: "Fredag",
    weekday_sat: "Lørdag",
    weekday_sun: "Søndag",

    home_away_header: "Hjemme/borte",
    option_person_entities: "Personentiteter",
    add_person: "+ Legg til",

    device_header: "Enhet",
    device_help: "Grupperer RoomFlows egne sensorer (gjeldende periode, dagstype, hjemme-status, per-periode-boolske).",
    no_area_option: "— Ingen sone —",

    buttons_header: "Fysiske knapper",
    buttons_help:
      'Bind en fysisk knapp/fjernkontroll (f.eks. en Zigbee-knapp som vises som en "event"- eller "sensor"-entitet i Home Assistant) til en handling i et rom.',
    add_button_header: "Legg til knapp",
    new_button_entity_placeholder: "entity_id (f.eks. event.kitchen_button)",
    choose_room_option: "Velg rom…",
    action_toggle: "Veksle på/av",
    action_off: "Slå av rom",
    action_apply_now: "Kjør planlagt atferd nå",
    action_force_period: "Tving frem en bestemt periode",
    room_missing: "(rom mangler)",

    motion_sensor_value_above: "Sensorverdi over",
    motion_label: "Bevegelse",
    motion_active_label: "Bevegelseskontroll aktiv i dette rommet",
    motion_or_logic_help: 'Rommet regnes som "aktivt" hvis NOEN betingelse nedenfor for øyeblikket er sann (ELLER-logikk).',
    add_motion_sensor: "+ Bevegelsessensor",
    add_threshold: "+ Terskel (f.eks. luftfuktighet)",
    turn_off_after: "Slå av etter",
    turn_off_after_suffix: "minutter uten at noen betingelse er sann (standard for enheter nedenfor uten egen innstilling)",
    dim_warning_label: "Demp som en advarsel før avslåing",
    dim_to: "Demp til",
    brightness_for: "lysstyrke i",
    minutes_before_off: "minutter før avslåing - bevegelse i det vinduet gjenoppretter full lysstyrke i stedet.",
    motion_footer_help:
      'Når aktivt kjøres rommets planlagte atferd umiddelbart (som "Test nå"). Velg hvilke enheter som reagerer på bevegelse, og deres egen avslåingsforsinkelse, på hver enhet nedenfor.',

    condition_is: "er",
    custom_conditions_header: "Egendefinerte betingelser",
    custom_conditions_help:
      "Romspesifikke unntak, sjekket i prioritert rekkefølge (øverst vinner) - over borte/helg/standard. Hver betingelse får sin egen morgen/dag/ettermiddag/kveld/natt-atferdsvariant per enhet nedenfor, akkurat som helg/borte.",
    add_condition: "+ Legg til betingelse",

    test_now: "Test nå",
    remove_room: "Fjern rom",
    add_device_option: "+ Legg til enhet…",

    default_variant_help:
      "La tidsplanen styre denne perioden (fjern haken for å la denne enheten være i fred her - f.eks. knapp/manuell modus)",
    custom_setting_for: "Egendefinert innstilling for {label}",
    on_label: "På",
    brightness_label: "Lysstyrke:",
    color_temp_label: "Fargetemp (K):",

    variant_default: "Standard",
    variant_weekend: "Helg",
    variant_away: "Borte",
    condition_fallback_name: "Betingelse",

    transition_time_label: "Overgangstid (sek) — standard er {s}s:",
    device_motion_reacts: "Reagerer på dette rommets bevegelses-/terskeltriggere",
    device_off_after: "Av etter",
    device_off_after_suffix: "minutter (tomt = romstandard)",

    status_unavailable: "· utilgjengelig",
    status_on: "· nå: på",
    status_on_pct: "· nå: på ({pct}%)",
    status_off: "· nå: av",

    applying: "Bruker…",
    done: "Ferdig!",

    new_condition_name: "Ny betingelse",
    new_period_name: "Ny periode",
    period_fallback_name: "Periode",

    loading: "Laster…",
  },

  da: {
    tab_add_room: "+ Rum",
    tab_buttons: "Knapper",
    tab_settings: "Indstillinger",
    test_all: "Test alle",

    add_room_header: "Tilføj rum",
    custom_name_option: "— Eget navn —",
    room_name_placeholder: "Rumnavn",
    add: "Tilføj",
    add_room_help: "At vælge et område tilføjer automatisk dets lys/stikkontakter til rummet.",

    seconds: "sekunder",
    day_type_condition_label: "Dagstype-betingelse (weekend):",
    home_away_condition_label: "Hjemme/væk-betingelse:",
    status_enabled: "aktiveret",
    status_not_configured: "ikke konfigureret",
    enable_more_conditions_help:
      "Angiv den relevante kilde nedenfor (Hverdag/weekend og/eller Hjemme/væk) for at aktivere flere betingelser.",
    default_transition_header: "Standard overgangstid per periode",
    default_transition_help:
      "Gælder for alle lys, medmindre en bestemt enhed har sin egen overgangstid indstillet.",

    weekend_override_time: "Andet tidspunkt i weekenden",
    weekend_override_sun: "Anden solbegivenhed i weekenden",

    operator_above: "er over",
    operator_below: "er under",
    operator_equals: "er lig med",
    and_condition_label: "Kræv også en sensorbetingelse",

    never_before: "· aldrig før",
    min_time_title:
      "Gulv - det beregnede starttidspunkt er aldrig tidligere end dette, selv hvis solbegivenheden er det. 00:00 = ingen begrænsning.",
    min_offset: "min offset",
    lx: "lx",
    value_placeholder: "værdi",

    source_schedule: "Tidsplan",
    source_sun: "Solens position",
    source_illuminance: "Lyssensor",
    source_boolean: "Eksisterende boolean",
    source_sensor: "Eksisterende sensor",

    sun_event_dawn: "Daggry",
    sun_event_sunrise: "Solopgang",
    sun_event_noon: "Middag",
    sun_event_sunset: "Solnedgang",
    sun_event_dusk: "Skumring",
    sun_event_midnight: "Solmidnat",

    periods_header: "Tid-på-dagen-perioder",
    periods_help:
      'Prioritetsrækkefølge (øverst vinder) - den første periode med en aktiveret kilde, der lige nu er "aktiv", er den aktuelle periode. Tilføj, fjern, omdøb eller omorganiser frit; afkryds hvilke kilder du vil have hver periode til at bruge - hvis mere end én er afkrydset, er perioden aktiv, når NOGEN af dem siger det.',
    periods_help_weekend_yes: "Tidsplan-/sol-kilder kan også have et andet tidspunkt i weekender.",
    periods_help_weekend_no: "Angiv en Hverdag/weekend-kilde nedenfor for at låse op for en weekendundtagelse på tidsplan-/sol-kilder.",
    name_placeholder: "Navn",
    add_period: "+ Tilføj periode",

    day_type_sensor_help: 'For en almindelig til/fra-sensor (ingen "weekend"-lignende tekst), vælg hvad "til" betyder:',
    day_type_sensor_inverted_label:
      '"Til" betyder hverdag (f.eks. en hverdag-lignende sensor) - afkrydset betyder "til" = weekend',
    weekend_days_help: 'Hvilke dage tæller som "weekend":',
    weekday_weekend_header: "Hverdag/weekend",
    option_not_used: "Ikke brugt",
    option_existing_sensor: "Eksisterende sensor",
    option_weekday_selection: "Ugedagsvalg",

    weekday_mon: "Mandag",
    weekday_tue: "Tirsdag",
    weekday_wed: "Onsdag",
    weekday_thu: "Torsdag",
    weekday_fri: "Fredag",
    weekday_sat: "Lørdag",
    weekday_sun: "Søndag",

    home_away_header: "Hjemme/væk",
    option_person_entities: "Personentiteter",
    add_person: "+ Tilføj",

    device_header: "Enhed",
    device_help: "Grupperer RoomFlows egne sensorer (aktuel periode, dagstype, hjemme-status, per-periode-booleans).",
    no_area_option: "— Intet område —",

    buttons_header: "Fysiske knapper",
    buttons_help:
      'Bind en fysisk knap/fjernbetjening (f.eks. en Zigbee-knap, der vises som en "event"- eller "sensor"-entitet i Home Assistant) til en handling i et rum.',
    add_button_header: "Tilføj knap",
    new_button_entity_placeholder: "entity_id (f.eks. event.kitchen_button)",
    choose_room_option: "Vælg rum…",
    action_toggle: "Skift til/fra",
    action_off: "Sluk rum",
    action_apply_now: "Kør planlagt adfærd nu",
    action_force_period: "Gennemtving en bestemt periode",
    room_missing: "(rum mangler)",

    motion_sensor_value_above: "Sensorværdi over",
    motion_label: "Bevægelse",
    motion_active_label: "Bevægelseskontrol aktiv i dette rum",
    motion_or_logic_help: 'Rummet betragtes som "aktivt", hvis NOGEN betingelse nedenfor lige nu er sand (ELLER-logik).',
    add_motion_sensor: "+ Bevægelsessensor",
    add_threshold: "+ Tærskel (f.eks. luftfugtighed)",
    turn_off_after: "Sluk efter",
    turn_off_after_suffix: "minutter uden at nogen betingelse er sand (standard for enheder nedenfor uden egen indstilling)",
    dim_warning_label: "Dæmp som en advarsel før slukning",
    dim_to: "Dæmp til",
    brightness_for: "lysstyrke i",
    minutes_before_off: "minutter før slukning - bevægelse i det vindue genopretter fuld lysstyrke i stedet.",
    motion_footer_help:
      'Når aktivt køres rummets planlagte adfærd med det samme (som "Test nu"). Vælg hvilke enheder der reagerer på bevægelse, og deres egen slukforsinkelse, på hver enhed nedenfor.',

    condition_is: "er",
    custom_conditions_header: "Brugerdefinerede betingelser",
    custom_conditions_help:
      "Rumspecifikke undtagelser, tjekket i prioriteret rækkefølge (øverst vinder) - over væk/weekend/standard. Hver betingelse får sin egen morgen/dag/eftermiddag/aften/nat-adfærdsvariant per enhed nedenfor, ligesom weekend/væk.",
    add_condition: "+ Tilføj betingelse",

    test_now: "Test nu",
    remove_room: "Fjern rum",
    add_device_option: "+ Tilføj enhed…",

    default_variant_help:
      "Lad tidsplanen styre denne periode (fjern fluebenet for at lade denne enhed være i fred her - f.eks. knap/manuel tilstand)",
    custom_setting_for: "Brugerdefineret indstilling for {label}",
    on_label: "Til",
    brightness_label: "Lysstyrke:",
    color_temp_label: "Farvetemp. (K):",

    variant_default: "Standard",
    variant_weekend: "Weekend",
    variant_away: "Væk",
    condition_fallback_name: "Betingelse",

    transition_time_label: "Overgangstid (sek) — standard er {s}s:",
    device_motion_reacts: "Reagerer på dette rums bevægelses-/tærskeltriggere",
    device_off_after: "Fra efter",
    device_off_after_suffix: "minutter (tomt = rumstandard)",

    status_unavailable: "· utilgængelig",
    status_on: "· nu: til",
    status_on_pct: "· nu: til ({pct}%)",
    status_off: "· nu: fra",

    applying: "Anvender…",
    done: "Færdig!",

    new_condition_name: "Ny betingelse",
    new_period_name: "Ny periode",
    period_fallback_name: "Periode",

    loading: "Indlæser…",
  },

  fi: {
    tab_add_room: "+ Huone",
    tab_buttons: "Painikkeet",
    tab_settings: "Asetukset",
    test_all: "Testaa kaikki",

    add_room_header: "Lisää huone",
    custom_name_option: "— Oma nimi —",
    room_name_placeholder: "Huoneen nimi",
    add: "Lisää",
    add_room_help: "Alueen valitseminen lisää automaattisesti sen valot/pistorasiat huoneeseen.",

    seconds: "sekuntia",
    day_type_condition_label: "Päivätyyppiehto (viikonloppu):",
    home_away_condition_label: "Koti/poissa-ehto:",
    status_enabled: "käytössä",
    status_not_configured: "ei määritetty",
    enable_more_conditions_help:
      "Aseta asiaankuuluva lähde alla (Arki/viikonloppu ja/tai Koti/poissa) ottaaksesi käyttöön lisää ehtoja.",
    default_transition_header: "Oletussiirtymäaika jaksoa kohti",
    default_transition_help:
      "Koskee jokaista valoa, ellei yksittäiselle laitteelle ole asetettu omaa siirtymäaikaa.",

    weekend_override_time: "Eri aika viikonloppuna",
    weekend_override_sun: "Eri auringon tapahtuma viikonloppuna",

    operator_above: "on yli",
    operator_below: "on alle",
    operator_equals: "on yhtä suuri kuin",
    and_condition_label: "Vaadi myös anturiehto",

    never_before: "· ei koskaan ennen",
    min_time_title:
      "Alaraja - ratkaistu alkamisaika ei ole koskaan tätä aikaisempi, vaikka auringon tapahtuma olisi. 00:00 = ei alarajaa.",
    min_offset: "min siirtymä",
    lx: "lx",
    value_placeholder: "arvo",

    source_schedule: "Aikataulu",
    source_sun: "Auringon asema",
    source_illuminance: "Valaistusanturi",
    source_boolean: "Olemassa oleva totuusarvo",
    source_sensor: "Olemassa oleva anturi",

    sun_event_dawn: "Sarastus",
    sun_event_sunrise: "Auringonnousu",
    sun_event_noon: "Keskipäivä",
    sun_event_sunset: "Auringonlasku",
    sun_event_dusk: "Hämärä",
    sun_event_midnight: "Aurinko-keskiyö",

    periods_header: "Vuorokaudenajan jaksot",
    periods_help:
      'Tärkeysjärjestys (ylin voittaa) - ensimmäinen jakso, jonka jokin käytössä oleva lähde on juuri nyt "aktiivinen", on nykyinen jakso. Lisää, poista, nimeä uudelleen tai järjestä uudelleen vapaasti; valitse, mitä lähteitä kunkin jakson tulisi käyttää - jos useampi kuin yksi on valittu, jakso on aktiivinen, kun MIKÄ TAHANSA niistä sanoo niin.',
    periods_help_weekend_yes: "Aikataulu-/aurinkolähteillä voi myös olla eri aika viikonloppuisin.",
    periods_help_weekend_no: "Aseta Arki/viikonloppu-lähde alla ottaaksesi käyttöön viikonloppupoikkeuksen aikataulu-/aurinkolähteille.",
    name_placeholder: "Nimi",
    add_period: "+ Lisää jakso",

    day_type_sensor_help: 'Tavalliselle päällä/pois-anturille (ei "weekend"-tyylistä tekstiä), valitse mitä "päällä" tarkoittaa:',
    day_type_sensor_inverted_label:
      '"Päällä" tarkoittaa arkea (esim. työpäivä-tyylinen anturi) - ei valittuna tarkoittaa "päällä" = viikonloppu',
    weekend_days_help: 'Mitkä päivät lasketaan "viikonlopuksi":',
    weekday_weekend_header: "Arki/viikonloppu",
    option_not_used: "Ei käytössä",
    option_existing_sensor: "Olemassa oleva anturi",
    option_weekday_selection: "Viikonpäivävalinta",

    weekday_mon: "Maanantai",
    weekday_tue: "Tiistai",
    weekday_wed: "Keskiviikko",
    weekday_thu: "Torstai",
    weekday_fri: "Perjantai",
    weekday_sat: "Lauantai",
    weekday_sun: "Sunnuntai",

    home_away_header: "Koti/poissa",
    option_person_entities: "Henkilöentiteetit",
    add_person: "+ Lisää",

    device_header: "Laite",
    device_help: "Ryhmittelee RoomFlow'n omat anturit (nykyinen jakso, päivätyyppi, kotitila, jaksokohtaiset totuusarvot).",
    no_area_option: "— Ei aluetta —",

    buttons_header: "Fyysiset painikkeet",
    buttons_help:
      'Sido fyysinen painike/kaukosäädin (esim. Zigbee-painike, joka näkyy Home Assistantissa "event"- tai "sensor"-entiteettinä) toimintoon huoneessa.',
    add_button_header: "Lisää painike",
    new_button_entity_placeholder: "entity_id (esim. event.kitchen_button)",
    choose_room_option: "Valitse huone…",
    action_toggle: "Vaihda päällä/pois",
    action_off: "Sammuta huone",
    action_apply_now: "Aja ajastettu toiminta nyt",
    action_force_period: "Pakota tietty jakso",
    room_missing: "(huone puuttuu)",

    motion_sensor_value_above: "Anturin arvo yli",
    motion_label: "Liike",
    motion_active_label: "Liikeohjaus käytössä tässä huoneessa",
    motion_or_logic_help: 'Huone lasketaan "aktiiviseksi", jos MIKÄ TAHANSA alla oleva ehto on juuri nyt tosi (TAI-logiikka).',
    add_motion_sensor: "+ Liikeanturi",
    add_threshold: "+ Kynnysarvo (esim. ilmankosteus)",
    turn_off_after: "Sammuta",
    turn_off_after_suffix: "minuutin kuluttua, jos mikään ehto ei ole tosi (oletus laitteille, joilla ei ole omaa asetusta)",
    dim_warning_label: "Himmennä varoituksena ennen sammutusta",
    dim_to: "Himmennä tasolle",
    brightness_for: "kirkkaus",
    minutes_before_off: "minuutiksi ennen sammutusta - liike tänä aikana palauttaa täyden kirkkauden sen sijaan.",
    motion_footer_help:
      'Kun aktiivinen, huoneen ajastettu toiminta käynnistyy heti (kuten "Testaa nyt"). Valitse, mitkä laitteet reagoivat liikkeeseen, ja niiden oma sammutusviive, kunkin laitteen kohdalla alla.',

    condition_is: "on",
    custom_conditions_header: "Omat ehdot",
    custom_conditions_help:
      "Huonekohtaiset ohitukset, tarkistettu tärkeysjärjestyksessä (ylin voittaa) - poissa/viikonloppu/oletuksen yläpuolella. Jokainen ehto saa oman aamu/päivä/iltapäivä/ilta/yö-toimintavarianttinsa laitteittain alla, aivan kuten viikonloppu/poissa.",
    add_condition: "+ Lisää ehto",

    test_now: "Testaa nyt",
    remove_room: "Poista huone",
    add_device_option: "+ Lisää laite…",

    default_variant_help:
      "Anna aikataulun ohjata tätä jaksoa (poista valinta jättääksesi tämän laitteen rauhaan täällä - esim. painike-/manuaalitila)",
    custom_setting_for: "Oma asetus kohteelle {label}",
    on_label: "Päällä",
    brightness_label: "Kirkkaus:",
    color_temp_label: "Värilämpötila (K):",

    variant_default: "Oletus",
    variant_weekend: "Viikonloppu",
    variant_away: "Poissa",
    condition_fallback_name: "Ehto",

    transition_time_label: "Siirtymäaika (s) — oletus on {s}s:",
    device_motion_reacts: "Reagoi tämän huoneen liike-/kynnysarvolaukaisimiin",
    device_off_after: "Pois",
    device_off_after_suffix: "minuutin kuluttua (tyhjä = huoneen oletus)",

    status_unavailable: "· ei saatavilla",
    status_on: "· nyt: päällä",
    status_on_pct: "· nyt: päällä ({pct}%)",
    status_off: "· nyt: pois",

    applying: "Otetaan käyttöön…",
    done: "Valmis!",

    new_condition_name: "Uusi ehto",
    new_period_name: "Uusi jakso",
    period_fallback_name: "Jakso",

    loading: "Ladataan…",
  },

  de: {
    tab_add_room: "+ Raum",
    tab_buttons: "Tasten",
    tab_settings: "Einstellungen",
    test_all: "Alle testen",

    add_room_header: "Raum hinzufügen",
    custom_name_option: "— Eigener Name —",
    room_name_placeholder: "Raumname",
    add: "Hinzufügen",
    add_room_help: "Die Auswahl eines Bereichs fügt dessen Lampen/Steckdosen automatisch zum Raum hinzu.",

    seconds: "Sekunden",
    day_type_condition_label: "Tagestyp-Bedingung (Wochenende):",
    home_away_condition_label: "Zuhause/Abwesend-Bedingung:",
    status_enabled: "aktiviert",
    status_not_configured: "nicht konfiguriert",
    enable_more_conditions_help:
      "Stelle die entsprechende Quelle unten ein (Werktag/Wochenende und/oder Zuhause/Abwesend), um weitere Bedingungen zu aktivieren.",
    default_transition_header: "Standard-Übergangszeit pro Zeitraum",
    default_transition_help:
      "Gilt für jede Lampe, sofern nicht ein einzelnes Gerät seine eigene Übergangszeit hat.",

    weekend_override_time: "Andere Uhrzeit am Wochenende",
    weekend_override_sun: "Anderes Sonnenereignis am Wochenende",

    operator_above: "ist über",
    operator_below: "ist unter",
    operator_equals: "ist gleich",
    and_condition_label: "Zusätzlich eine Sensorbedingung erfordern",

    never_before: "· nie vor",
    min_time_title:
      "Untergrenze - die berechnete Startzeit liegt nie früher als diese, auch wenn das Sonnenereignis es ist. 00:00 = keine Untergrenze.",
    min_offset: "Min. Versatz",
    lx: "lx",
    value_placeholder: "Wert",

    source_schedule: "Zeitplan",
    source_sun: "Sonnenposition",
    source_illuminance: "Helligkeitssensor",
    source_boolean: "Vorhandener Boolean",
    source_sensor: "Vorhandener Sensor",

    sun_event_dawn: "Morgendämmerung",
    sun_event_sunrise: "Sonnenaufgang",
    sun_event_noon: "Mittag",
    sun_event_sunset: "Sonnenuntergang",
    sun_event_dusk: "Abenddämmerung",
    sun_event_midnight: "Solare Mitternacht",

    periods_header: "Tageszeit-Zeiträume",
    periods_help:
      'Prioritätsreihenfolge (oben gewinnt) - der erste Zeitraum mit einer aktivierten Quelle, die gerade "aktiv" ist, ist der aktuelle Zeitraum. Füge frei hinzu, entferne, benenne um oder ordne neu an; kreuze an, welche Quellen jeder Zeitraum verwenden soll - wenn mehr als eine angekreuzt ist, ist der Zeitraum aktiv, wenn IRGENDEINE davon zutrifft.',
    periods_help_weekend_yes: "Zeitplan-/Sonnen-Quellen können am Wochenende auch eine abweichende Uhrzeit haben.",
    periods_help_weekend_no: "Stelle unten eine Werktag/Wochenende-Quelle ein, um eine Wochenend-Ausnahme für Zeitplan-/Sonnen-Quellen freizuschalten.",
    name_placeholder: "Name",
    add_period: "+ Zeitraum hinzufügen",

    day_type_sensor_help: 'Für einen einfachen An/Aus-Sensor (kein "Wochenende"-artiger Text) wähle, was "an" bedeutet:',
    day_type_sensor_inverted_label:
      '"An" bedeutet Werktag (z. B. ein Werktag-artiger Sensor) - nicht angekreuzt bedeutet "an" = Wochenende',
    weekend_days_help: 'Welche Tage als "Wochenende" zählen:',
    weekday_weekend_header: "Werktag/Wochenende",
    option_not_used: "Nicht verwendet",
    option_existing_sensor: "Vorhandener Sensor",
    option_weekday_selection: "Wochentagsauswahl",

    weekday_mon: "Montag",
    weekday_tue: "Dienstag",
    weekday_wed: "Mittwoch",
    weekday_thu: "Donnerstag",
    weekday_fri: "Freitag",
    weekday_sat: "Samstag",
    weekday_sun: "Sonntag",

    home_away_header: "Zuhause/Abwesend",
    option_person_entities: "Personen-Entitäten",
    add_person: "+ Hinzufügen",

    device_header: "Gerät",
    device_help: "Gruppiert RoomFlows eigene Sensoren (aktueller Zeitraum, Tagestyp, Zuhause-Status, Zeitraum-Booleans).",
    no_area_option: "— Kein Bereich —",

    buttons_header: "Physische Tasten",
    buttons_help:
      'Binde eine physische Taste/Fernbedienung (z. B. eine Zigbee-Taste, die als "event"- oder "sensor"-Entität erscheint) an eine Aktion in einem Raum.',
    add_button_header: "Taste hinzufügen",
    new_button_entity_placeholder: "entity_id (z. B. event.kitchen_button)",
    choose_room_option: "Raum wählen…",
    action_toggle: "An/Aus umschalten",
    action_off: "Raum ausschalten",
    action_apply_now: "Geplantes Verhalten jetzt ausführen",
    action_force_period: "Bestimmten Zeitraum erzwingen",
    room_missing: "(Raum fehlt)",

    motion_sensor_value_above: "Sensorwert über",
    motion_label: "Bewegung",
    motion_active_label: "Bewegungssteuerung in diesem Raum aktiv",
    motion_or_logic_help: 'Der Raum gilt als "aktiv", wenn IRGENDEINE Bedingung unten gerade wahr ist (ODER-Logik).',
    add_motion_sensor: "+ Bewegungssensor",
    add_threshold: "+ Schwellenwert (z. B. Luftfeuchtigkeit)",
    turn_off_after: "Ausschalten nach",
    turn_off_after_suffix: "Minuten ohne wahre Bedingung (Standard für Geräte unten ohne eigene Einstellung)",
    dim_warning_label: "Als Warnung dimmen vor dem Ausschalten",
    dim_to: "Dimmen auf",
    brightness_for: "Helligkeit für",
    minutes_before_off: "Minuten vor dem Ausschalten - Bewegung in diesem Fenster stellt stattdessen die volle Helligkeit wieder her.",
    motion_footer_help:
      'Wenn aktiv, wird das geplante Verhalten des Raums sofort ausgeführt (wie "Jetzt testen"). Wähle unten pro Gerät, welche Geräte auf Bewegung reagieren, und ihre eigene Ausschaltverzögerung.',

    condition_is: "ist",
    custom_conditions_header: "Benutzerdefinierte Bedingungen",
    custom_conditions_help:
      "Raumspezifische Ausnahmen, geprüft in Prioritätsreihenfolge (oben gewinnt) - über Abwesend/Wochenende/Standard. Jede Bedingung erhält ihre eigene Morgen/Tag/Nachmittag/Abend/Nacht-Verhaltensvariante pro Gerät unten, genau wie Wochenende/Abwesend.",
    add_condition: "+ Bedingung hinzufügen",

    test_now: "Jetzt testen",
    remove_room: "Raum entfernen",
    add_device_option: "+ Gerät hinzufügen…",

    default_variant_help:
      "Lass den Zeitplan diesen Zeitraum steuern (deaktivieren, um dieses Gerät hier in Ruhe zu lassen - z. B. Tasten-/manueller Modus)",
    custom_setting_for: "Eigene Einstellung für {label}",
    on_label: "An",
    brightness_label: "Helligkeit:",
    color_temp_label: "Farbtemp. (K):",

    variant_default: "Standard",
    variant_weekend: "Wochenende",
    variant_away: "Abwesend",
    condition_fallback_name: "Bedingung",

    transition_time_label: "Übergangszeit (Sek.) — Standard ist {s}s:",
    device_motion_reacts: "Reagiert auf die Bewegungs-/Schwellenwert-Trigger dieses Raums",
    device_off_after: "Aus nach",
    device_off_after_suffix: "Minuten (leer = Raumstandard)",

    status_unavailable: "· nicht verfügbar",
    status_on: "· jetzt: an",
    status_on_pct: "· jetzt: an ({pct}%)",
    status_off: "· jetzt: aus",

    applying: "Wird angewendet…",
    done: "Fertig!",

    new_condition_name: "Neue Bedingung",
    new_period_name: "Neuer Zeitraum",
    period_fallback_name: "Zeitraum",

    loading: "Lädt…",
  },

  fr: {
    tab_add_room: "+ Pièce",
    tab_buttons: "Boutons",
    tab_settings: "Paramètres",
    test_all: "Tout tester",

    add_room_header: "Ajouter une pièce",
    custom_name_option: "— Nom personnalisé —",
    room_name_placeholder: "Nom de la pièce",
    add: "Ajouter",
    add_room_help: "Choisir une zone ajoute automatiquement ses lumières/prises à la pièce.",

    seconds: "secondes",
    day_type_condition_label: "Condition de type de jour (week-end) :",
    home_away_condition_label: "Condition présent/absent :",
    status_enabled: "activée",
    status_not_configured: "non configurée",
    enable_more_conditions_help:
      "Configurez la source concernée ci-dessous (Semaine/week-end et/ou Présent/absent) pour activer plus de conditions.",
    default_transition_header: "Temps de transition par défaut par période",
    default_transition_help:
      "S'applique à toutes les lumières, sauf si un appareil a son propre temps de transition défini.",

    weekend_override_time: "Heure différente le week-end",
    weekend_override_sun: "Événement solaire différent le week-end",

    operator_above: "est supérieur à",
    operator_below: "est inférieur à",
    operator_equals: "est égal à",
    and_condition_label: "Exiger aussi une condition de capteur",

    never_before: "· jamais avant",
    min_time_title:
      "Plancher - l'heure de début calculée n'est jamais plus tôt que ceci, même si l'événement solaire l'est. 00:00 = pas de plancher.",
    min_offset: "décalage (min)",
    lx: "lx",
    value_placeholder: "valeur",

    source_schedule: "Horaire fixe",
    source_sun: "Position du soleil",
    source_illuminance: "Capteur de luminosité",
    source_boolean: "Booléen existant",
    source_sensor: "Capteur existant",

    sun_event_dawn: "Aube",
    sun_event_sunrise: "Lever du soleil",
    sun_event_noon: "Midi solaire",
    sun_event_sunset: "Coucher du soleil",
    sun_event_dusk: "Crépuscule",
    sun_event_midnight: "Minuit solaire",

    periods_header: "Périodes de la journée",
    periods_help:
      "Ordre de priorité (le premier l'emporte) - la première période avec une source activée actuellement « active » est la période actuelle. Ajoutez, supprimez, renommez ou réorganisez librement ; cochez les sources que chaque période doit utiliser - si plusieurs sont cochées, la période est active quand N'IMPORTE LAQUELLE d'entre elles le dit.",
    periods_help_weekend_yes: "Les sources horaire fixe/soleil peuvent aussi avoir une heure différente le week-end.",
    periods_help_weekend_no: "Configurez une source Semaine/week-end ci-dessous pour débloquer une dérogation week-end sur les sources horaire fixe/soleil.",
    name_placeholder: "Nom",
    add_period: "+ Ajouter une période",

    day_type_sensor_help: "Pour un simple capteur allumé/éteint (pas de texte type « week-end »), choisissez ce que « allumé » signifie :",
    day_type_sensor_inverted_label:
      "« Allumé » signifie semaine (par ex. un capteur de type jour ouvré) - non coché signifie « allumé » = week-end",
    weekend_days_help: "Quels jours comptent comme « week-end » :",
    weekday_weekend_header: "Semaine/week-end",
    option_not_used: "Non utilisé",
    option_existing_sensor: "Capteur existant",
    option_weekday_selection: "Sélection des jours",

    weekday_mon: "Lundi",
    weekday_tue: "Mardi",
    weekday_wed: "Mercredi",
    weekday_thu: "Jeudi",
    weekday_fri: "Vendredi",
    weekday_sat: "Samedi",
    weekday_sun: "Dimanche",

    home_away_header: "Présent/absent",
    option_person_entities: "Entités personne",
    add_person: "+ Ajouter",

    device_header: "Appareil",
    device_help: "Regroupe les propres capteurs de RoomFlow (période actuelle, type de jour, état de présence, booléens par période).",
    no_area_option: "— Aucune zone —",

    buttons_header: "Boutons physiques",
    buttons_help:
      "Liez un bouton physique/une télécommande (par ex. un bouton Zigbee apparaissant comme une entité « event » ou « sensor ») à une action dans une pièce.",
    add_button_header: "Ajouter un bouton",
    new_button_entity_placeholder: "entity_id (par ex. event.kitchen_button)",
    choose_room_option: "Choisir une pièce…",
    action_toggle: "Basculer allumé/éteint",
    action_off: "Éteindre la pièce",
    action_apply_now: "Exécuter le comportement programmé maintenant",
    action_force_period: "Forcer une période spécifique",
    room_missing: "(pièce manquante)",

    motion_sensor_value_above: "Valeur du capteur supérieure à",
    motion_label: "Mouvement",
    motion_active_label: "Contrôle par mouvement actif dans cette pièce",
    motion_or_logic_help: "La pièce est considérée « active » si N'IMPORTE QUELLE condition ci-dessous est actuellement vraie (logique OU).",
    add_motion_sensor: "+ Capteur de mouvement",
    add_threshold: "+ Seuil (par ex. humidité)",
    turn_off_after: "Éteindre après",
    turn_off_after_suffix: "minutes sans qu'aucune condition ne soit vraie (par défaut pour les appareils ci-dessous sans réglage propre)",
    dim_warning_label: "Tamiser comme avertissement avant extinction",
    dim_to: "Tamiser à",
    brightness_for: "de luminosité pendant",
    minutes_before_off: "minutes avant extinction - un mouvement pendant cette fenêtre restaure la pleine luminosité à la place.",
    motion_footer_help:
      "Lorsqu'actif, le comportement programmé de la pièce s'exécute immédiatement (comme « Tester maintenant »). Choisissez quels appareils réagissent au mouvement, et leur propre délai d'extinction, sur chaque appareil ci-dessous.",

    condition_is: "est",
    custom_conditions_header: "Conditions personnalisées",
    custom_conditions_help:
      "Dérogations propres à la pièce, vérifiées par ordre de priorité (le premier l'emporte) - au-dessus de absence/week-end/par défaut. Chaque condition obtient sa propre variante de comportement matin/journée/après-midi/soir/nuit par appareil ci-dessous, exactement comme week-end/absence.",
    add_condition: "+ Ajouter une condition",

    test_now: "Tester maintenant",
    remove_room: "Supprimer la pièce",
    add_device_option: "+ Ajouter un appareil…",

    default_variant_help:
      "Laissez l'horaire fixe contrôler cette période (décochez pour laisser cet appareil tranquille ici - par ex. mode bouton/manuel)",
    custom_setting_for: "Réglage personnalisé pour {label}",
    on_label: "Allumé",
    brightness_label: "Luminosité :",
    color_temp_label: "Temp. de couleur (K) :",

    variant_default: "Par défaut",
    variant_weekend: "Week-end",
    variant_away: "Absence",
    condition_fallback_name: "Condition",

    transition_time_label: "Temps de transition (s) — par défaut {s}s :",
    device_motion_reacts: "Réagit aux déclencheurs de mouvement/seuil de cette pièce",
    device_off_after: "Éteint après",
    device_off_after_suffix: "minutes (vide = valeur par défaut de la pièce)",

    status_unavailable: "· indisponible",
    status_on: "· actuellement : allumé",
    status_on_pct: "· actuellement : allumé ({pct}%)",
    status_off: "· actuellement : éteint",

    applying: "Application…",
    done: "Terminé !",

    new_condition_name: "Nouvelle condition",
    new_period_name: "Nouvelle période",
    period_fallback_name: "Période",

    loading: "Chargement…",
  },

  nl: {
    tab_add_room: "+ Kamer",
    tab_buttons: "Knoppen",
    tab_settings: "Instellingen",
    test_all: "Alles testen",

    add_room_header: "Kamer toevoegen",
    custom_name_option: "— Eigen naam —",
    room_name_placeholder: "Kamernaam",
    add: "Toevoegen",
    add_room_help: "Het kiezen van een gebied voegt automatisch de bijbehorende lampen/stopcontacten toe aan de kamer.",

    seconds: "seconden",
    day_type_condition_label: "Dagtype-voorwaarde (weekend):",
    home_away_condition_label: "Thuis/afwezig-voorwaarde:",
    status_enabled: "ingeschakeld",
    status_not_configured: "niet geconfigureerd",
    enable_more_conditions_help:
      "Stel de relevante bron hieronder in (Doordeweeks/weekend en/of Thuis/afwezig) om meer voorwaarden in te schakelen.",
    default_transition_header: "Standaard overgangstijd per periode",
    default_transition_help:
      "Geldt voor elke lamp, tenzij een specifiek apparaat een eigen overgangstijd heeft ingesteld.",

    weekend_override_time: "Andere tijd in het weekend",
    weekend_override_sun: "Andere zonnegebeurtenis in het weekend",

    operator_above: "is hoger dan",
    operator_below: "is lager dan",
    operator_equals: "is gelijk aan",
    and_condition_label: "Ook een sensorvoorwaarde vereisen",

    never_before: "· nooit voor",
    min_time_title:
      "Bodemwaarde - de berekende starttijd is nooit eerder dan dit, zelfs als de zonnegebeurtenis dat wel is. 00:00 = geen bodemwaarde.",
    min_offset: "min. verschuiving",
    lx: "lx",
    value_placeholder: "waarde",

    source_schedule: "Schema",
    source_sun: "Zonpositie",
    source_illuminance: "Lichtsterktesensor",
    source_boolean: "Bestaande boolean",
    source_sensor: "Bestaande sensor",

    sun_event_dawn: "Dageraad",
    sun_event_sunrise: "Zonsopgang",
    sun_event_noon: "Zonnemiddag",
    sun_event_sunset: "Zonsondergang",
    sun_event_dusk: "Schemering",
    sun_event_midnight: "Zonnemiddernacht",

    periods_header: "Tijdstip-van-de-dag-periodes",
    periods_help:
      'Prioriteitsvolgorde (bovenaan wint) - de eerste periode met een ingeschakelde bron die op dit moment "actief" is, is de huidige periode. Voeg vrij toe, verwijder, hernoem of herschik; vink aan welke bronnen elke periode moet gebruiken - als er meer dan één is aangevinkt, is de periode actief wanneer OM HET EVEN WELKE daarvan dat aangeeft.',
    periods_help_weekend_yes: "Schema-/zonbronnen kunnen ook een afwijkende tijd hebben in het weekend.",
    periods_help_weekend_no: "Stel hieronder een Doordeweeks/weekend-bron in om een weekendoverride voor schema-/zonbronnen te ontgrendelen.",
    name_placeholder: "Naam",
    add_period: "+ Periode toevoegen",

    day_type_sensor_help: 'Voor een gewone aan/uit-sensor (geen "weekend"-achtige tekst), kies wat "aan" betekent:',
    day_type_sensor_inverted_label:
      '"Aan" betekent doordeweeks (bijv. een werkdag-achtige sensor) - niet aangevinkt betekent "aan" = weekend',
    weekend_days_help: 'Welke dagen tellen als "weekend":',
    weekday_weekend_header: "Doordeweeks/weekend",
    option_not_used: "Niet gebruikt",
    option_existing_sensor: "Bestaande sensor",
    option_weekday_selection: "Weekdagselectie",

    weekday_mon: "Maandag",
    weekday_tue: "Dinsdag",
    weekday_wed: "Woensdag",
    weekday_thu: "Donderdag",
    weekday_fri: "Vrijdag",
    weekday_sat: "Zaterdag",
    weekday_sun: "Zondag",

    home_away_header: "Thuis/afwezig",
    option_person_entities: "Persoon-entiteiten",
    add_person: "+ Toevoegen",

    device_header: "Apparaat",
    device_help: "Groepeert RoomFlows eigen sensoren (huidige periode, dagtype, thuisstatus, periodeboolean).",
    no_area_option: "— Geen gebied —",

    buttons_header: "Fysieke knoppen",
    buttons_help:
      'Koppel een fysieke knop/afstandsbediening (bijv. een Zigbee-knop die verschijnt als een "event"- of "sensor"-entiteit) aan een actie in een kamer.',
    add_button_header: "Knop toevoegen",
    new_button_entity_placeholder: "entity_id (bijv. event.kitchen_button)",
    choose_room_option: "Kies kamer…",
    action_toggle: "Aan/uit omschakelen",
    action_off: "Kamer uitschakelen",
    action_apply_now: "Gepland gedrag nu uitvoeren",
    action_force_period: "Specifieke periode forceren",
    room_missing: "(kamer ontbreekt)",

    motion_sensor_value_above: "Sensorwaarde boven",
    motion_label: "Beweging",
    motion_active_label: "Bewegingsbesturing actief in deze kamer",
    motion_or_logic_help: 'De kamer wordt als "actief" beschouwd als OM HET EVEN WELKE voorwaarde hieronder op dit moment waar is (OF-logica).',
    add_motion_sensor: "+ Bewegingssensor",
    add_threshold: "+ Drempelwaarde (bijv. vochtigheid)",
    turn_off_after: "Uitschakelen na",
    turn_off_after_suffix: "minuten zonder dat een voorwaarde waar is (standaard voor apparaten hieronder zonder eigen instelling)",
    dim_warning_label: "Dimmen als waarschuwing vóór uitschakelen",
    dim_to: "Dimmen naar",
    brightness_for: "helderheid gedurende",
    minutes_before_off: "minuten vóór uitschakelen - beweging tijdens dat venster herstelt in plaats daarvan volledige helderheid.",
    motion_footer_help:
      'Indien actief wordt het geplande gedrag van de kamer onmiddellijk uitgevoerd (zoals "Nu testen"). Kies welke apparaten op beweging reageren, en hun eigen uitschakelvertraging, per apparaat hieronder.',

    condition_is: "is",
    custom_conditions_header: "Aangepaste voorwaarden",
    custom_conditions_help:
      "Kamerspecifieke overrides, gecontroleerd op volgorde van prioriteit (bovenaan wint) - boven afwezig/weekend/standaard. Elke voorwaarde krijgt zijn eigen ochtend/dag/middag/avond/nacht-gedragsvariant per apparaat hieronder, net als weekend/afwezig.",
    add_condition: "+ Voorwaarde toevoegen",

    test_now: "Nu testen",
    remove_room: "Kamer verwijderen",
    add_device_option: "+ Apparaat toevoegen…",

    default_variant_help:
      "Laat het schema deze periode besturen (vink uit om dit apparaat hier met rust te laten - bijv. knop-/handmatige modus)",
    custom_setting_for: "Aangepaste instelling voor {label}",
    on_label: "Aan",
    brightness_label: "Helderheid:",
    color_temp_label: "Kleurtemp. (K):",

    variant_default: "Standaard",
    variant_weekend: "Weekend",
    variant_away: "Afwezig",
    condition_fallback_name: "Voorwaarde",

    transition_time_label: "Overgangstijd (sec) — standaard is {s}s:",
    device_motion_reacts: "Reageert op de beweging-/drempelwaardetriggers van deze kamer",
    device_off_after: "Uit na",
    device_off_after_suffix: "minuten (leeg = kamerstandaard)",

    status_unavailable: "· niet beschikbaar",
    status_on: "· nu: aan",
    status_on_pct: "· nu: aan ({pct}%)",
    status_off: "· nu: uit",

    applying: "Bezig met toepassen…",
    done: "Klaar!",

    new_condition_name: "Nieuwe voorwaarde",
    new_period_name: "Nieuwe periode",
    period_fallback_name: "Periode",

    loading: "Bezig met laden…",
  },
};

function t(lang, key, vars) {
  let str = (STRINGS[lang] && STRINGS[lang][key]) ?? STRINGS.en[key] ?? key;
  if (vars) {
    Object.keys(vars).forEach((k) => {
      str = str.replace(new RegExp(`\\{${k}\\}`, "g"), vars[k]);
    });
  }
  return str;
}

function detectLang(hass) {
  const code = ((hass && hass.language) || "en").slice(0, 2).toLowerCase();
  return STRINGS[code] ? code : "en";
}

// ---------- icons ----------
// Small icon() helper renders a native <ha-icon>, themed automatically by
// Home Assistant (color/size via CSS custom properties in RF_STYLES below)
// - no separate icon assets or sprite sheets needed.
function icon(name, extraStyle, className) {
  return `<ha-icon icon="${name}" class="${className || ""}" style="${extraStyle || ""}"></ha-icon>`;
}

// ---------- native HA form components, with a plain-HTML fallback ----------
// ha-icon is always part of Home Assistant's core frontend bundle, but
// ha-textfield/ha-switch are only pulled in by more specialized panels
// (e.g. settings dialogs, config flows) and aren't guaranteed to be
// registered as custom elements yet just because the frontend is running -
// depends on what else the user has opened in that browser session. An
// unregistered custom element renders as an empty, non-interactive box (no
// value shown, nothing happens on click) - not an error, just silently
// broken. customElements.get() is a reliable, synchronous way to check
// "is this actually going to work" before using it, so every field falls
// back to a plain native element instead of risking that silent failure.
function textField(attrsHtml) {
  return typeof customElements !== "undefined" && customElements.get("ha-textfield")
    ? `<ha-textfield ${attrsHtml}></ha-textfield>`
    : `<input ${attrsHtml} />`;
}
function switchEl(attrsHtml) {
  return typeof customElements !== "undefined" && customElements.get("ha-switch")
    ? `<ha-switch ${attrsHtml}></ha-switch>`
    : `<input type="checkbox" ${attrsHtml} />`;
}

const PERIOD_ICONS = {
  morning: "mdi:weather-sunset-up",
  day: "mdi:white-balance-sunny",
  afternoon: "mdi:weather-sunny",
  evening: "mdi:weather-sunset-down",
  night: "mdi:weather-night",
};
const DEFAULT_PERIOD_ICON = "mdi:clock-outline";
function periodIcon(periodId) {
  return PERIOD_ICONS[periodId] || DEFAULT_PERIOD_ICON;
}

function deviceIcon(device) {
  if (device.type === "outlet") return "mdi:power-plug-outline";
  if (!device.supports_color_temp && !device.supports_brightness) return "mdi:lightbulb-outline";
  return "mdi:lightbulb-on-outline";
}

const VARIANT_ICONS = {
  default: "mdi:calendar-check-outline",
  weekend: "mdi:calendar-weekend-outline",
  away: "mdi:home-export-outline",
  condition: "mdi:tune-variant",
};

const CONDITION_TYPE_ICONS = {
  time: "mdi:clock-time-eight-outline",
  sun: "mdi:weather-sunny",
  numeric: "mdi:thermometer-lines",
  state: "mdi:toggle-switch-outline",
  day_type: "mdi:calendar-weekend-outline",
  home: "mdi:home-export-outline",
};

// One shared stylesheet, injected once per render into the card's own
// light-DOM innerHTML (RoomFlowCard has no shadow root) - re-parsing a
// <style> tag on every render is cheap and keeps every rule scoped under
// .rf-root so it can never leak into the surrounding dashboard.
const RF_STYLES = `
<style>
  .rf-root { font-size: 0.95em; }
  .rf-root ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }

  .rf-topbar {
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid var(--divider-color); padding: 0 8px;
  }
  .rf-tabs { display: flex; overflow-x: auto; }
  .rf-tab {
    display: flex; align-items: center; gap: 6px;
    background: none; border: none; border-bottom: 2px solid transparent;
    padding: 10px 12px; cursor: pointer; font-size: 0.95em; white-space: nowrap;
    color: var(--secondary-text-color); font-family: inherit;
  }
  .rf-tab ha-icon { --mdc-icon-size: 18px; }
  .rf-tab.active { border-bottom-color: var(--primary-color); color: var(--primary-color); font-weight: 600; }
  .rf-tab.active ha-icon { color: var(--primary-color); }

  .rf-btn {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--primary-color); color: var(--text-primary-color, #fff);
    border: none; border-radius: 8px; padding: 7px 14px; cursor: pointer;
    font-size: 0.9em; font-family: inherit; white-space: nowrap;
  }
  .rf-btn ha-icon { color: inherit; --mdc-icon-size: 18px; }
  .rf-btn.rf-btn-flat {
    background: none; color: var(--primary-color); padding: 7px 10px;
  }
  .rf-btn.rf-btn-danger { background: none; color: var(--error-color, #db4437); padding: 7px 10px; }
  .rf-btn:disabled { opacity: 0.4; cursor: default; }

  .rf-icon-btn {
    display: inline-flex; align-items: center; justify-content: center;
    background: none; border: none; cursor: pointer; border-radius: 50%;
    width: 32px; height: 32px; color: var(--secondary-text-color);
  }
  .rf-icon-btn:hover { background: var(--divider-color); }
  .rf-icon-btn:disabled { opacity: 0.3; cursor: default; background: none; }
  .rf-icon-btn ha-icon { --mdc-icon-size: 18px; }
  .rf-icon-btn.rf-danger:hover { color: var(--error-color, #db4437); }

  .rf-card {
    background: var(--secondary-background-color); border-radius: 12px;
    padding: 12px; margin-bottom: 12px;
  }
  .rf-card-title {
    display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 4px;
  }
  .rf-help { opacity: 0.7; font-size: 0.85em; margin-top: 4px; }

  .rf-section { margin-top: 22px; }
  .rf-section-title { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 1.05em; }

  .rf-room-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .rf-room-header h2 { display: flex; align-items: center; gap: 8px; font-size: 1.15em; margin: 0; font-weight: 600; }

  .rf-chip-row { display: flex; gap: 6px; flex-wrap: wrap; }
  .rf-chip {
    display: flex; align-items: center; gap: 4px;
    padding: 5px 12px; border-radius: 999px; cursor: pointer;
    background: var(--card-background-color); border: 1px solid var(--divider-color);
    font-size: 0.85em; color: var(--primary-text-color); font-family: inherit;
  }
  .rf-chip ha-icon { --mdc-icon-size: 16px; }
  .rf-chip.active { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .rf-chip.active ha-icon { color: inherit; }

  .rf-device {
    background: var(--card-background-color); border: 1px solid var(--divider-color);
    border-radius: 12px; margin-bottom: 10px; overflow: hidden;
  }
  .rf-device-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 12px; cursor: pointer;
  }
  .rf-device-header .rf-caret { --mdc-icon-size: 20px; opacity: 0.5; flex: none; }
  .rf-device.rf-open .rf-device-header { border-bottom: 1px solid var(--divider-color); }
  .rf-device-name { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .rf-device-name .rf-device-icon { --mdc-icon-size: 22px; color: var(--state-icon-active-color, var(--paper-item-icon-active-color, #fdd835)); flex: none; }
  .rf-device-name .rf-device-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rf-device-name small { opacity: 0.65; margin-left: 4px; }
  .rf-device-body { padding: 10px 12px; }

  .rf-badge {
    font-size: 0.72em; padding: 2px 9px; border-radius: 999px; white-space: nowrap;
    background: var(--divider-color); color: var(--primary-text-color); margin-left: 8px;
  }
  .rf-badge.rf-on { background: #4caf5026; color: #2e7d32; }
  .rf-badge.rf-off { background: var(--divider-color); color: var(--secondary-text-color); }

  .rf-variant {
    border-radius: 8px; padding: 8px 10px; margin-top: 8px;
    border-left: 3px solid var(--divider-color); background: var(--secondary-background-color);
  }
  .rf-variant.rf-disabled { opacity: 0.55; }
  .rf-variant-default { border-left-color: var(--primary-color); }
  .rf-variant-weekend { border-left-color: #8e6fce; }
  .rf-variant-away { border-left-color: #ff8a50; }
  .rf-variant-condition { border-left-color: #26a69a; }
  .rf-variant-title { display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 0.92em; }
  .rf-variant-title ha-icon { --mdc-icon-size: 17px; }

  .rf-condition-group {
    margin-top: 6px;
    padding: 8px;
    border: 1px solid var(--divider-color);
    border-radius: 8px;
  }
  .rf-or-divider {
    text-align: center;
    font-size: 0.8em;
    font-weight: 600;
    opacity: 0.6;
    margin: 4px 0;
    text-transform: uppercase;
  }

  .rf-slider-row { margin-top: 6px; }
  .rf-slider-row input[type="range"] { width: 100%; accent-color: var(--primary-color); }

  .rf-root ha-textfield { --mdc-typography-subtitle1-font-size: 0.92em; }
  .rf-root ha-switch { flex: none; vertical-align: middle; }

  .rf-empty { opacity: 0.65; font-size: 0.9em; padding: 8px 0; }
</style>
`;

class RoomFlowCard extends HTMLElement {
  constructor() {
    super();
    this._config_data = {
      rooms: [],
      buttons: [],
      default_transitions: { ...DEFAULT_TRANSITIONS },
    };
    this._areas = [];
    this._entities = [];
    this._activeTab = {}; // deviceKey -> period
    this._activeRoomPeriod = {}; // room.id -> period, drives every device's tab in that room at once
    this._openDevices = {}; // deviceKey -> bool, undefined defaults to open (matches pre-collapse behavior)
    this._activeRoomId = null; // room.id | "__add__" | "__buttons__" | "__settings__"
    this._saveTimeout = null;
    this._lang = "en";

    this.addEventListener("click", (e) => this._onClick(e));
    this.addEventListener("change", (e) => this._onChange(e));
    this.addEventListener("input", (e) => this._onInput(e));
  }

  // Card-wide translation lookup - see the STRINGS table and t()/detectLang()
  // near the top of this file.
  _t(key, vars) {
    return t(this._lang, key, vars);
  }

  // Custom element constructors must not add child nodes (the spec
  // forbids it and browsers enforce it - "A newly constructed custom
  // element must not have child nodes"). The initial placeholder has to
  // wait until here instead.
  connectedCallback() {
    if (!this.hasChildNodes()) {
      this.innerHTML = `<ha-card><div style='padding:16px'>${this._t("loading")}</div></ha-card>`;
    }
  }

  // setConfig is only called when the card is used inside a dashboard (not
  // when used as a sidebar panel via panel_custom).
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    const firstRun = !this._hass;
    this._hass = hass;
    this._lang = detectLang(hass);
    if (firstRun) {
      this._loadAll();
    } else if (this._activeRoomId) {
      // Only refresh live-status text, don't fully re-render on every tick
      this._updateLiveStatusTexts();
    }
  }

  async _loadAll() {
    const [config, areas, entities] = await Promise.all([
      this._hass.callWS({ type: "roomflow/get_config" }),
      this._hass.callWS({ type: "roomflow/list_areas" }),
      this._hass.callWS({ type: "roomflow/list_entities" }),
    ]);
    this._config_data = config && config.rooms ? config : { rooms: [] };
    this._areas = areas;
    this._entities = entities;
    this._migrateConfig();
    this._render();
  }

  _hasDayType() {
    return (this._config_data.day_type_mode || "none") !== "none";
  }

  _hasHome() {
    return (this._config_data.home_mode || "none") !== "none";
  }

  // A room's icon follows the HA Area it's linked to (set via Settings ->
  // Areas -> pick icon), same as the rest of the HA UI - falls back to a
  // generic room icon for a manually-named room with no area, or an area
  // that hasn't had a custom icon set.
  _roomIcon(room) {
    const area = room.area_id && this._areas.find((a) => a.area_id === room.area_id);
    return (area && area.icon) || "mdi:sofa-outline";
  }

  _schedule(scheduleId) {
    const schedules = this._config_data.schedules || [];
    return schedules.find((s) => s.id === scheduleId) || schedules[0];
  }

  _roomSchedule(room) {
    return this._schedule(room.schedule_id);
  }

  _roomPeriods(room) {
    const schedule = this._roomSchedule(room);
    return (schedule && schedule.periods) || [];
  }

  _migrateConfig() {
    const cd = this._config_data;
    if (!cd.rooms) cd.rooms = [];
    if (!cd.buttons) cd.buttons = [];

    // Schedules: a named, independent periods list of its own (see
    // DEFAULT_SCHEDULE_ID docs above) - a room follows one via its
    // schedule_id. Older installs have either the pre-existing global
    // time_sources/time_mode plus parallel per-period dicts, or a flat
    // top-level `periods` list from before schedules existed (both
    // predate condition_groups too, in which case normalizePeriodsList
    // handles that layer) - migrate either into a single "Main" schedule
    // so every room without an explicit schedule_id keeps following
    // exactly the same periods as before.
    if (!cd.schedules) {
      const periods = cd.periods || buildPeriodsFromLegacy(cd);
      cd.schedules = [{ id: DEFAULT_SCHEDULE_ID, name: DEFAULT_SCHEDULE_NAME, periods }];
    }
    delete cd.periods;
    cd.schedules = cd.schedules.map(normalizeSchedule);
    if (!cd.schedules.length) {
      cd.schedules = [{ id: DEFAULT_SCHEDULE_ID, name: DEFAULT_SCHEDULE_NAME, periods: [] }];
    }

    // default_transitions used to be a flat {period_id: seconds} map,
    // shared by every room via the single old global periods list. Now
    // that periods live inside per-schedule lists, it nests one level
    // deeper by schedule id - detected by value type (old shape's values
    // are plain numbers, new shape's are objects), mirroring __init__.py's
    // _migrate_default_transitions_nesting.
    if (!cd.default_transitions) {
      cd.default_transitions = { [DEFAULT_SCHEDULE_ID]: { ...DEFAULT_TRANSITIONS } };
    } else {
      const values = Object.values(cd.default_transitions);
      const looksFlat = values.length > 0 && typeof values[0] === "number";
      if (looksFlat) cd.default_transitions = { [DEFAULT_SCHEDULE_ID]: cd.default_transitions };
    }
    cd.schedules.forEach((s) => {
      if (!cd.default_transitions[s.id]) cd.default_transitions[s.id] = {};
    });

    // Day-type/home-away: infer "sensor" if an older bare sensor field is
    // already set and no explicit mode was ever saved.
    if (!cd.day_type_mode) cd.day_type_mode = cd.day_type_sensor ? "sensor" : "none";
    if (!cd.weekend_days) cd.weekend_days = [...DEFAULT_WEEKEND_DAYS];
    if (!cd.home_mode) cd.home_mode = cd.home_sensor ? "sensor" : "none";
    if (!cd.person_entities) cd.person_entities = [];

    if (!cd.device_name) cd.device_name = "RoomFlow";
    if (cd.area_id === undefined) cd.area_id = null;

    cd.rooms.forEach((room) => {
      // A room follows one schedule (schedule_id) - fall back to the
      // first schedule if unset or dangling (its schedule was deleted),
      // same graceful-degradation as const.py's periods_for_schedule.
      if (!room.schedule_id || !cd.schedules.some((s) => s.id === room.schedule_id)) {
        room.schedule_id = cd.schedules[0].id;
      }
      if (!room.motion) {
        room.motion = { enabled: false, timeout_minutes: 10, triggers: [] };
      } else if (!room.motion.triggers) {
        room.motion = {
          enabled: !!room.motion.enabled,
          timeout_minutes: room.motion.timeout_minutes || 10,
          triggers: [],
        };
      }
      if (room.motion.warn_enabled === undefined) room.motion.warn_enabled = false;
      if (room.motion.warn_minutes === undefined) room.motion.warn_minutes = 3;
      if (room.motion.warn_brightness === undefined) room.motion.warn_brightness = 25;
      if (!room.custom_conditions) room.custom_conditions = [];
      const roomPeriods = this._roomPeriods(room);
      (room.devices || []).forEach((device) => {
        if (!device.transitions) device.transitions = {};
        if (!device.motion) device.motion = { enabled: false, off_delay_minutes: null };
        const behaviors = device.behaviors || {};
        roomPeriods.forEach((p) => {
          const raw = behaviors[p.id];
          const base = { state: "off" };
          if (device.supports_brightness) base.brightness = 255;
          if (device.supports_color_temp) base.color_temp_kelvin = 3000;

          if (!raw) {
            behaviors[p.id] = {
              default: { ...base, enabled: true },
              weekend: emptyVariant(base, true),
              away: emptyVariant(base, true),
            };
          } else if (!raw.default && !raw.weekend && !raw.away) {
            // Legacy format: the whole object was the behavior itself
            behaviors[p.id] = {
              default: { ...raw, enabled: true },
              weekend: emptyVariant({ ...raw }, true),
              away: emptyVariant({ ...raw }, true),
            };
          } else {
            if (!raw.default) raw.default = { ...base, enabled: true };
            else if (raw.default.enabled === undefined) raw.default.enabled = true;
            if (!raw.weekend) raw.weekend = emptyVariant(raw.default, true);
            if (!raw.away) raw.away = emptyVariant(raw.default, true);
          }
        });
        device.behaviors = behaviors;
      });
    });
  }

  _scheduleSave() {
    if (this._saveTimeout) clearTimeout(this._saveTimeout);
    this._saveTimeout = setTimeout(() => {
      this._hass.callWS({
        type: "roomflow/save_config",
        config: this._config_data,
      });
    }, 400);
  }

  _buildDevice(entity, scheduleId) {
    const type = entity.domain === "light" ? "light" : "outlet";
    const supportsBrightness = !!entity.supports_brightness;
    const supportsColorTemp = !!entity.supports_color_temp;

    const base = { state: "off" };
    if (supportsBrightness) base.brightness = 255;
    if (supportsColorTemp) base.color_temp_kelvin = 3000;

    const behaviors = {};
    const periods = (this._schedule(scheduleId) || {}).periods || [];
    periods.forEach((p) => {
      behaviors[p.id] = {
        default: { ...base },
        weekend: emptyVariant(base, true),
        away: emptyVariant(base, true),
      };
    });

    return {
      entity_id: entity.entity_id,
      name: entity.name,
      type: type,
      supports_brightness: supportsBrightness,
      supports_color_temp: supportsColorTemp,
      transitions: {},
      behaviors: behaviors,
    };
  }

  _addRoom(name, areaId, scheduleId) {
    const schedule = this._schedule(scheduleId);
    // Lights/outlets already assigned to this area in Home Assistant are
    // added automatically, so a room tied to an area starts pre-populated
    // instead of empty.
    const devices = areaId
      ? this._entities.filter((e) => e.area_id === areaId).map((e) => this._buildDevice(e, schedule.id))
      : [];
    const room = { id: uid(), name: name, area_id: areaId || null, schedule_id: schedule.id, devices: devices };
    this._config_data.rooms.push(room);
    this._activeRoomId = room.id;
    this._scheduleSave();
    this._render();
  }

  _removeRoom(roomId) {
    this._config_data.rooms = this._config_data.rooms.filter((r) => r.id !== roomId);
    if (this._activeRoomId === roomId) {
      const remaining = this._config_data.rooms;
      this._activeRoomId = remaining.length ? remaining[0].id : "__add__";
    }
    this._scheduleSave();
    this._render();
  }

  _addDevice(roomId, entityId) {
    const entity = this._entities.find((e) => e.entity_id === entityId);
    if (!entity) return;
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    room.devices.push(this._buildDevice(entity, room.schedule_id));
    this._scheduleSave();
    this._render();
  }

  _removeDevice(roomId, entityId) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    room.devices = room.devices.filter((d) => d.entity_id !== entityId);
    this._scheduleSave();
    this._render();
  }

  _addButton(entityId, roomId, action, forcePeriod) {
    this._config_data.buttons.push({
      id: uid(),
      entity_id: entityId,
      room_id: roomId,
      action: action,
      force_period: action === "force_period" ? forcePeriod : null,
    });
    this._scheduleSave();
    this._render();
  }

  _removeButton(buttonId) {
    this._config_data.buttons = this._config_data.buttons.filter((b) => b.id !== buttonId);
    this._scheduleSave();
    this._render();
  }

  _updateMotion(roomId, field, value) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    room.motion[field] = value;
    this._scheduleSave();
  }

  _addMotionTrigger(roomId, type) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    const trigger = { id: uid(), type: type, entity_id: "" };
    if (type === "threshold_above") trigger.threshold = 60;
    room.motion.triggers.push(trigger);
    this._scheduleSave();
    this._render();
  }

  _removeMotionTrigger(roomId, triggerId) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    room.motion.triggers = room.motion.triggers.filter((t) => t.id !== triggerId);
    this._scheduleSave();
    this._render();
  }

  _updateMotionTrigger(roomId, triggerId, field, value) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    const trigger = room.motion.triggers.find((t) => t.id === triggerId);
    if (!trigger) return;
    trigger[field] = value;
    this._scheduleSave();
  }

  // Room-level custom conditions: an ORDERED list (order = priority, top =
  // highest), unlike motion triggers which are unordered/OR-combined. Each
  // one gets its own per-period behavior variant on every device in the
  // room, same shape as the built-in weekend/away variants.
  _addCustomCondition(roomId) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    if (!room.custom_conditions) room.custom_conditions = [];
    room.custom_conditions.push({ id: uid(), name: this._t("new_condition_name"), entity_id: "", state: "on" });
    this._scheduleSave();
    this._render();
  }

  _removeCustomCondition(roomId, conditionId) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    room.custom_conditions = (room.custom_conditions || []).filter((c) => c.id !== conditionId);
    this._scheduleSave();
    this._render();
  }

  _updateCustomCondition(roomId, conditionId, field, value) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return;
    const condition = (room.custom_conditions || []).find((c) => c.id === conditionId);
    if (!condition) return;
    condition[field] = value;
    this._scheduleSave();
  }

  _moveCustomCondition(roomId, conditionId, direction) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room || !room.custom_conditions) return;
    const index = room.custom_conditions.findIndex((c) => c.id === conditionId);
    if (index === -1) return;
    const swapWith = direction === "up" ? index - 1 : index + 1;
    if (swapWith < 0 || swapWith >= room.custom_conditions.length) return;
    const conditions = room.custom_conditions;
    [conditions[index], conditions[swapWith]] = [conditions[swapWith], conditions[index]];
    this._scheduleSave();
    this._render();
  }

  // Time-of-day periods: a top-level ORDERED list (order = priority, top =
  // highest, first period with a true condition group wins). Each period
  // holds a list of condition groups, OR'd together; each group holds a
  // list of conditions, AND'd together - "OR of AND groups", mirrors
  // const.py's DEFAULT_PERIODS/infer_periods on the backend. Unlike custom
  // conditions above, groups/conditions don't need move-up/down: AND and
  // OR are both commutative, so only add/remove are needed.

  // Schedules: a named, independent periods list of its own (see
  // DEFAULT_SCHEDULE_ID docs) - like schedules themselves, no move-up/down
  // (order has no effect, only room.schedule_id picks which one applies).
  _addSchedule() {
    if (!this._config_data.schedules) this._config_data.schedules = [];
    this._config_data.schedules.push({ id: uid(), name: this._t("new_schedule_name"), periods: [] });
    this._scheduleSave();
    this._render();
  }

  // Refuses to remove the last remaining schedule (every room needs one to
  // fall back on) and reassigns any room pointed at the removed schedule
  // to the first remaining one, mirroring const.py's periods_for_schedule
  // fallback so nothing is left dangling.
  _removeSchedule(scheduleId) {
    const schedules = this._config_data.schedules || [];
    if (schedules.length <= 1) return;
    this._config_data.schedules = schedules.filter((s) => s.id !== scheduleId);
    const fallbackId = this._config_data.schedules[0].id;
    (this._config_data.rooms || []).forEach((room) => {
      if (room.schedule_id === scheduleId) room.schedule_id = fallbackId;
    });
    this._scheduleSave();
    this._render();
  }

  _updateScheduleName(scheduleId, name) {
    const schedule = (this._config_data.schedules || []).find((s) => s.id === scheduleId);
    if (!schedule) return;
    schedule.name = name;
    this._scheduleSave();
  }

  _addPeriod(scheduleId) {
    const schedule = this._schedule(scheduleId);
    if (!schedule) return;
    schedule.periods.push({ id: uid(), name: this._t("new_period_name"), condition_groups: [] });
    this._scheduleSave();
    this._render();
  }

  _removePeriod(scheduleId, periodId) {
    const schedule = this._schedule(scheduleId);
    if (!schedule) return;
    schedule.periods = schedule.periods.filter((p) => p.id !== periodId);
    this._scheduleSave();
    this._render();
  }

  _updatePeriod(scheduleId, periodId, field, value) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    if (!period) return;
    period[field] = value;
    this._scheduleSave();
  }

  // Adds a new OR'd group to the period, seeded with one default ("time")
  // condition - an empty group would never match anything (see
  // _period_condition_groups_match in __init__.py) so there's no point
  // showing one with nothing in it.
  _addConditionGroup(scheduleId, periodId) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    if (!period) return;
    period.condition_groups.push({ id: uid(), conditions: [normalizeCondition({ type: "time" })] });
    this._scheduleSave();
    this._render();
  }

  _removeConditionGroup(scheduleId, periodId, groupId) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    if (!period) return;
    period.condition_groups = period.condition_groups.filter((g) => g.id !== groupId);
    this._scheduleSave();
    this._render();
  }

  // Adds a new AND'd condition to an existing group.
  _addCondition(scheduleId, periodId, groupId, type) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    const group = period && period.condition_groups.find((g) => g.id === groupId);
    if (!group) return;
    group.conditions.push(normalizeCondition({ type }));
    this._scheduleSave();
    this._render();
  }

  // Removes one condition from a group; a group left with none is dropped
  // too rather than lingering as a dead, never-matching group in the UI.
  _removeCondition(scheduleId, periodId, groupId, conditionId) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    const group = period && period.condition_groups.find((g) => g.id === groupId);
    if (!group) return;
    group.conditions = group.conditions.filter((c) => c.id !== conditionId);
    if (group.conditions.length === 0) {
      period.condition_groups = period.condition_groups.filter((g) => g.id !== groupId);
    }
    this._scheduleSave();
    this._render();
  }

  // Switching a condition's type resets its fields to that type's
  // defaults (the old type's fields don't apply), keeping only its id.
  _updateConditionType(scheduleId, periodId, groupId, conditionId, newType) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    const group = period && period.condition_groups.find((g) => g.id === groupId);
    const index = group ? group.conditions.findIndex((c) => c.id === conditionId) : -1;
    if (index === -1) return;
    group.conditions[index] = normalizeCondition({ id: conditionId, type: newType });
    this._scheduleSave();
    this._render();
  }

  _updateCondition(scheduleId, periodId, groupId, conditionId, field, value) {
    const schedule = this._schedule(scheduleId);
    const period = schedule && schedule.periods.find((p) => p.id === periodId);
    const group = period && period.condition_groups.find((g) => g.id === groupId);
    const condition = group && group.conditions.find((c) => c.id === conditionId);
    if (!condition) return;
    condition[field] = value;
    this._scheduleSave();
  }

  _movePeriod(scheduleId, periodId, direction) {
    const schedule = this._schedule(scheduleId);
    if (!schedule) return;
    const periods = schedule.periods;
    const index = periods.findIndex((p) => p.id === periodId);
    if (index === -1) return;
    const swapWith = direction === "up" ? index - 1 : index + 1;
    if (swapWith < 0 || swapWith >= periods.length) return;
    [periods[index], periods[swapWith]] = [periods[swapWith], periods[index]];
    this._scheduleSave();
    this._render();
  }

  _findDevice(roomId, entityId) {
    const room = this._config_data.rooms.find((r) => r.id === roomId);
    if (!room) return null;
    return room.devices.find((d) => d.entity_id === entityId) || null;
  }

  _availableEntities(room) {
    const used = new Set(room.devices.map((d) => d.entity_id));
    return this._entities.filter((e) => !used.has(e.entity_id));
  }

  _liveStatusText(device) {
    const st = this._hass && this._hass.states[device.entity_id];
    if (!st) return "";
    let raw;
    if (st.state === "unavailable") {
      raw = this._t("status_unavailable");
    } else if (st.state === "on") {
      const b = st.attributes ? st.attributes.brightness : null;
      raw = b ? this._t("status_on_pct", { pct: Math.round((b / 255) * 100) }) : this._t("status_on");
    } else {
      raw = this._t("status_off");
    }
    return raw.replace(/^·\s*/, "");
  }

  _liveStatusClass(device) {
    const st = this._hass && this._hass.states[device.entity_id];
    if (!st || st.state === "unavailable") return "";
    return st.state === "on" ? "rf-on" : "rf-off";
  }

  _updateLiveStatusTexts() {
    this.querySelectorAll("[data-live-status]").forEach((el) => {
      const { roomId, entityId } = parseDeviceKey(el.getAttribute("data-live-status"));
      const device = this._findDevice(roomId, entityId);
      if (device) {
        el.textContent = this._liveStatusText(device);
        el.className = `rf-badge ${this._liveStatusClass(device)}`.trim();
      }
    });
  }

  // ---------- Event delegation ----------

  _onClick(e) {
    const roomTab = e.target.closest("[data-room-tab]");
    if (roomTab) {
      this._activeRoomId = roomTab.getAttribute("data-room-tab");
      this._render();
      return;
    }

    const removeRoomBtn = e.target.closest("[data-remove-room]");
    if (removeRoomBtn) {
      this._removeRoom(removeRoomBtn.getAttribute("data-remove-room"));
      return;
    }

    const removeDeviceBtn = e.target.closest("[data-remove-device]");
    if (removeDeviceBtn) {
      const [roomId, entityId] = removeDeviceBtn.getAttribute("data-remove-device").split("|");
      this._removeDevice(roomId, entityId);
      return;
    }

    // Collapse/expand a device card - checked after data-remove-device
    // above so clicking the remove button (which lives inside this same
    // header) removes the device instead of also toggling the card.
    const deviceToggle = e.target.closest("[data-device-toggle]");
    if (deviceToggle) {
      const deviceKey = deviceToggle.getAttribute("data-device-toggle");
      this._openDevices[deviceKey] = this._openDevices[deviceKey] === false;
      this._render();
      return;
    }

    const periodTab = e.target.closest("[data-tab]");
    if (periodTab) {
      const [deviceKey, period] = periodTab.getAttribute("data-tab").split("|");
      this._activeTab[deviceKey] = period;
      this._render();
      return;
    }

    // Room-level period tab: switches every device in the room to the same
    // period at once, so their Default/Weekend/Away/etc. boxes are all
    // visible side by side for that one period without opening each device
    // individually.
    const roomPeriodTab = e.target.closest("[data-room-period-tab]");
    if (roomPeriodTab) {
      const [roomId, period] = roomPeriodTab.getAttribute("data-room-period-tab").split("|");
      this._activeRoomPeriod[roomId] = period;
      const room = (this._config_data.rooms || []).find((r) => r.id === roomId);
      (room?.devices || []).forEach((d) => {
        this._activeTab[`${roomId}:${d.entity_id}`] = period;
      });
      this._render();
      return;
    }

    const removeTriggerBtn = e.target.closest("[data-remove-motion-trigger]");
    if (removeTriggerBtn) {
      const [roomId, triggerId] = removeTriggerBtn.getAttribute("data-remove-motion-trigger").split("|");
      this._removeMotionTrigger(roomId, triggerId);
      return;
    }

    const addMotionBtn = e.target.closest("[data-add-motion-trigger]");
    if (addMotionBtn) {
      const [roomId, type] = addMotionBtn.getAttribute("data-add-motion-trigger").split("|");
      this._addMotionTrigger(roomId, type);
      return;
    }

    const addConditionBtn = e.target.closest("[data-add-custom-condition]");
    if (addConditionBtn) {
      this._addCustomCondition(addConditionBtn.getAttribute("data-add-custom-condition"));
      return;
    }

    const removeConditionBtn = e.target.closest("[data-remove-custom-condition]");
    if (removeConditionBtn) {
      const [roomId, conditionId] = removeConditionBtn.getAttribute("data-remove-custom-condition").split("|");
      this._removeCustomCondition(roomId, conditionId);
      return;
    }

    const moveConditionUpBtn = e.target.closest("[data-move-custom-condition-up]");
    if (moveConditionUpBtn) {
      const [roomId, conditionId] = moveConditionUpBtn.getAttribute("data-move-custom-condition-up").split("|");
      this._moveCustomCondition(roomId, conditionId, "up");
      return;
    }

    const moveConditionDownBtn = e.target.closest("[data-move-custom-condition-down]");
    if (moveConditionDownBtn) {
      const [roomId, conditionId] = moveConditionDownBtn.getAttribute("data-move-custom-condition-down").split("|");
      this._moveCustomCondition(roomId, conditionId, "down");
      return;
    }

    if (e.target.closest("[data-add-schedule]")) {
      this._addSchedule();
      return;
    }

    const removeScheduleBtn = e.target.closest("[data-remove-schedule]");
    if (removeScheduleBtn) {
      this._removeSchedule(removeScheduleBtn.getAttribute("data-remove-schedule"));
      return;
    }

    const addPeriodBtn = e.target.closest("[data-add-period]");
    if (addPeriodBtn) {
      this._addPeriod(addPeriodBtn.getAttribute("data-add-period"));
      return;
    }

    const removePeriodBtn = e.target.closest("[data-remove-period]");
    if (removePeriodBtn) {
      const [scheduleId, periodId] = removePeriodBtn.getAttribute("data-remove-period").split("|");
      this._removePeriod(scheduleId, periodId);
      return;
    }

    const movePeriodUpBtn = e.target.closest("[data-move-period-up]");
    if (movePeriodUpBtn) {
      const [scheduleId, periodId] = movePeriodUpBtn.getAttribute("data-move-period-up").split("|");
      this._movePeriod(scheduleId, periodId, "up");
      return;
    }

    const movePeriodDownBtn = e.target.closest("[data-move-period-down]");
    if (movePeriodDownBtn) {
      const [scheduleId, periodId] = movePeriodDownBtn.getAttribute("data-move-period-down").split("|");
      this._movePeriod(scheduleId, periodId, "down");
      return;
    }

    const addConditionGroupBtn = e.target.closest("[data-add-condition-group]");
    if (addConditionGroupBtn) {
      const [scheduleId, periodId] = addConditionGroupBtn.getAttribute("data-add-condition-group").split("|");
      this._addConditionGroup(scheduleId, periodId);
      return;
    }

    const removeConditionGroupBtn = e.target.closest("[data-remove-condition-group]");
    if (removeConditionGroupBtn) {
      const [scheduleId, periodId, groupId] = removeConditionGroupBtn.getAttribute("data-remove-condition-group").split("|");
      this._removeConditionGroup(scheduleId, periodId, groupId);
      return;
    }

    const removePeriodConditionBtn = e.target.closest("[data-remove-condition]");
    if (removePeriodConditionBtn) {
      const [scheduleId, periodId, groupId, conditionId] = removePeriodConditionBtn.getAttribute("data-remove-condition").split("|");
      this._removeCondition(scheduleId, periodId, groupId, conditionId);
      return;
    }

    const removeButtonBtn = e.target.closest("[data-remove-button]");
    if (removeButtonBtn) {
      this._removeButton(removeButtonBtn.getAttribute("data-remove-button"));
      return;
    }

    if (e.target.closest("#add-button-btn")) {
      const entityInput = this.querySelector("#new-button-entity");
      const roomSelect = this.querySelector("#new-button-room");
      const actionSelect = this.querySelector("#new-button-action");
      const periodSelect = this.querySelector("#new-button-period");
      const entityId = entityInput.value.trim();
      const roomId = roomSelect.value;
      const action = actionSelect.value;
      const forcePeriod = periodSelect ? periodSelect.value : null;
      if (!entityId || !roomId) return;
      this._addButton(entityId, roomId, action, forcePeriod);
      return;
    }

    if (e.target.closest("#add-room-btn")) {
      const areaSelect = this.querySelector("#new-room-area");
      const nameInput = this.querySelector("#new-room-name");
      const scheduleSelect = this.querySelector("#new-room-schedule");
      const areaId = areaSelect.value;
      let name = nameInput.value.trim();
      if (areaId) {
        const area = this._areas.find((a) => a.area_id === areaId);
        name = name || (area ? area.name : "");
      }
      if (!name) return;
      this._addRoom(name, areaId || null, scheduleSelect ? scheduleSelect.value : undefined);
      return;
    }

    if (e.target.closest("#apply-all-btn")) {
      const btn = e.target.closest("#apply-all-btn");
      // Save/restore innerHTML (not textContent) so the button's icon
      // isn't permanently wiped out by the transient text-only feedback.
      const original = btn.innerHTML;
      btn.textContent = this._t("applying");
      btn.disabled = true;
      this._hass.callWS({ type: "roomflow/apply_now" }).finally(() => {
        btn.textContent = this._t("done");
        setTimeout(() => {
          btn.innerHTML = original;
          btn.disabled = false;
        }, 1200);
      });
      return;
    }

    const applyRoomBtn = e.target.closest("[data-apply-room]");
    if (applyRoomBtn) {
      const roomId = applyRoomBtn.getAttribute("data-apply-room");
      const original = applyRoomBtn.innerHTML;
      applyRoomBtn.textContent = this._t("applying");
      applyRoomBtn.disabled = true;
      this._hass
        .callWS({ type: "roomflow/apply_room", room_id: roomId })
        .finally(() => {
          applyRoomBtn.textContent = this._t("done");
          setTimeout(() => {
            applyRoomBtn.innerHTML = original;
            applyRoomBtn.disabled = false;
          }, 1200);
        });
      return;
    }

    const removePersonBtn = e.target.closest("[data-remove-person]");
    if (removePersonBtn) {
      const entityId = removePersonBtn.getAttribute("data-remove-person");
      this._config_data.person_entities = (this._config_data.person_entities || []).filter(
        (p) => p !== entityId
      );
      this._scheduleSave();
      this._render();
      return;
    }

    if (e.target.closest("#add-person-btn")) {
      const input = this.querySelector("#new-person-entity");
      const entityId = input.value.trim();
      if (!entityId) return;
      if (!this._config_data.person_entities) this._config_data.person_entities = [];
      if (!this._config_data.person_entities.includes(entityId)) {
        this._config_data.person_entities.push(entityId);
      }
      this._scheduleSave();
      this._render();
      return;
    }
  }

  _onChange(e) {
    const newDeviceSelect = e.target.closest("[data-new-device]");
    if (newDeviceSelect) {
      const roomId = newDeviceSelect.getAttribute("data-new-device");
      const entityId = newDeviceSelect.value;
      if (entityId) this._addDevice(roomId, entityId);
      return;
    }

    if (e.target.closest("#new-button-action")) {
      // Show/hide the period picker depending on the chosen action; nothing
      // is saved here, this only affects the add-form UI
      const periodWrap = this.querySelector("#new-button-period-wrap");
      if (periodWrap) {
        periodWrap.style.display =
          e.target.closest("#new-button-action").value === "force_period" ? "inline-block" : "none";
      }
      return;
    }

    if (e.target.closest("#new-button-room")) {
      // "Force period" always targets the chosen room, so its period
      // choices come from that room's own schedule - repopulate directly
      // (no save/re-render) rather than losing the rest of the in-progress
      // add-button form.
      const periodSelect = this.querySelector("#new-button-period");
      if (periodSelect) {
        const roomId = e.target.closest("#new-button-room").value;
        const room = this._config_data.rooms.find((r) => r.id === roomId);
        const periods = room ? this._roomPeriods(room) : [];
        periodSelect.innerHTML = periods.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
      }
      return;
    }

    const motionEnabled = e.target.closest("[data-motion-enabled]");
    if (motionEnabled) {
      this._updateMotion(motionEnabled.getAttribute("data-motion-enabled"), "enabled", motionEnabled.checked);
      this._render();
      return;
    }

    const motionEntity = e.target.closest("[data-motion-trigger-entity]");
    if (motionEntity) {
      const [roomId, triggerId] = motionEntity.getAttribute("data-motion-trigger-entity").split("|");
      this._updateMotionTrigger(roomId, triggerId, "entity_id", motionEntity.value.trim());
      return;
    }

    const motionThreshold = e.target.closest("[data-motion-trigger-threshold]");
    if (motionThreshold) {
      const [roomId, triggerId] = motionThreshold.getAttribute("data-motion-trigger-threshold").split("|");
      const val = parseFloat(motionThreshold.value);
      this._updateMotionTrigger(roomId, triggerId, "threshold", isNaN(val) ? 0 : val);
      return;
    }

    const conditionName = e.target.closest("[data-condition-name]");
    if (conditionName) {
      const [roomId, conditionId] = conditionName.getAttribute("data-condition-name").split("|");
      this._updateCustomCondition(roomId, conditionId, "name", conditionName.value.trim() || this._t("condition_fallback_name"));
      return;
    }

    const conditionEntity = e.target.closest("[data-condition-entity]");
    if (conditionEntity) {
      const [roomId, conditionId] = conditionEntity.getAttribute("data-condition-entity").split("|");
      this._updateCustomCondition(roomId, conditionId, "entity_id", conditionEntity.value.trim());
      return;
    }

    const conditionState = e.target.closest("[data-condition-state]");
    if (conditionState) {
      const [roomId, conditionId] = conditionState.getAttribute("data-condition-state").split("|");
      this._updateCustomCondition(roomId, conditionId, "state", conditionState.value.trim());
      return;
    }

    const motionTimeout = e.target.closest("[data-motion-timeout]");
    if (motionTimeout) {
      const val = parseInt(motionTimeout.value, 10);
      this._updateMotion(
        motionTimeout.getAttribute("data-motion-timeout"),
        "timeout_minutes",
        isNaN(val) ? 10 : val
      );
      return;
    }

    const motionWarnEnabled = e.target.closest("[data-motion-warn-enabled]");
    if (motionWarnEnabled) {
      this._updateMotion(
        motionWarnEnabled.getAttribute("data-motion-warn-enabled"),
        "warn_enabled",
        motionWarnEnabled.checked
      );
      this._render();
      return;
    }

    const motionWarnMinutes = e.target.closest("[data-motion-warn-minutes]");
    if (motionWarnMinutes) {
      const val = parseInt(motionWarnMinutes.value, 10);
      this._updateMotion(
        motionWarnMinutes.getAttribute("data-motion-warn-minutes"),
        "warn_minutes",
        isNaN(val) ? 3 : val
      );
      return;
    }

    const motionWarnBrightness = e.target.closest("[data-motion-warn-brightness]");
    if (motionWarnBrightness) {
      const val = parseInt(motionWarnBrightness.value, 10);
      this._updateMotion(
        motionWarnBrightness.getAttribute("data-motion-warn-brightness"),
        "warn_brightness",
        isNaN(val) ? 25 : val
      );
      return;
    }

    const deviceMotionEnabled = e.target.closest("[data-device-motion-enabled]");
    if (deviceMotionEnabled) {
      const { roomId, entityId } = parseDeviceKey(deviceMotionEnabled.getAttribute("data-device-motion-enabled"));
      const device = this._findDevice(roomId, entityId);
      if (device) {
        if (!device.motion) device.motion = { enabled: false, off_delay_minutes: null };
        device.motion.enabled = deviceMotionEnabled.checked;
        this._scheduleSave();
        this._render();
      }
      return;
    }

    const deviceMotionDelay = e.target.closest("[data-device-motion-delay]");
    if (deviceMotionDelay) {
      const { roomId, entityId } = parseDeviceKey(deviceMotionDelay.getAttribute("data-device-motion-delay"));
      const device = this._findDevice(roomId, entityId);
      if (device) {
        if (!device.motion) device.motion = { enabled: false, off_delay_minutes: null };
        const raw = deviceMotionDelay.value.trim();
        const val = parseInt(raw, 10);
        device.motion.off_delay_minutes = raw === "" || isNaN(val) ? null : val;
        this._scheduleSave();
      }
      return;
    }

    const variantToggle = e.target.closest("[data-variant-toggle]");
    if (variantToggle) {
      const [deviceKey, period, variant] = variantToggle.getAttribute("data-variant-toggle").split("|");
      const { roomId, entityId } = parseDeviceKey(deviceKey);
      const device = this._findDevice(roomId, entityId);
      if (device) {
        device.behaviors[period][variant].enabled = variantToggle.checked;
        this._scheduleSave();
        this._render();
      }
      return;
    }

    const transitionInput = e.target.closest("[data-transition]");
    if (transitionInput) {
      const [deviceKey, period] = transitionInput.getAttribute("data-transition").split("|");
      const { roomId, entityId } = parseDeviceKey(deviceKey);
      const device = this._findDevice(roomId, entityId);
      if (device) {
        const val = transitionInput.value.trim();
        device.transitions[period] = val === "" ? null : parseFloat(val);
        this._scheduleSave();
      }
      return;
    }

    const defaultTransitionInput = e.target.closest("[data-default-transition]");
    if (defaultTransitionInput) {
      const [scheduleId, periodId] = defaultTransitionInput.getAttribute("data-default-transition").split("|");
      const val = parseFloat(defaultTransitionInput.value);
      if (!this._config_data.default_transitions[scheduleId]) this._config_data.default_transitions[scheduleId] = {};
      this._config_data.default_transitions[scheduleId][periodId] = isNaN(val) ? 0 : val;
      this._scheduleSave();
      return;
    }

    // ---------- Settings tab: schedules/periods / day-type / home-away / device ----------

    const scheduleNameInput = e.target.closest("[data-schedule-name]");
    if (scheduleNameInput) {
      this._updateScheduleName(
        scheduleNameInput.getAttribute("data-schedule-name"),
        scheduleNameInput.value.trim() || this._t("schedule_fallback_name")
      );
      return;
    }

    const periodNameInput = e.target.closest("[data-period-name]");
    if (periodNameInput) {
      const [scheduleId, periodId] = periodNameInput.getAttribute("data-period-name").split("|");
      this._updatePeriod(scheduleId, periodId, "name", periodNameInput.value.trim() || this._t("period_fallback_name"));
      return;
    }

    const conditionTypeSelect = e.target.closest("[data-condition-type]");
    if (conditionTypeSelect) {
      const [scheduleId, periodId, groupId, conditionId] = conditionTypeSelect.getAttribute("data-condition-type").split("|");
      this._updateConditionType(scheduleId, periodId, groupId, conditionId, conditionTypeSelect.value);
      return;
    }

    const addConditionSelect = e.target.closest("[data-add-condition]");
    if (addConditionSelect) {
      const [scheduleId, periodId, groupId] = addConditionSelect.getAttribute("data-add-condition").split("|");
      if (addConditionSelect.value) this._addCondition(scheduleId, periodId, groupId, addConditionSelect.value);
      return;
    }

    const conditionField = e.target.closest("[data-condition]");
    if (conditionField) {
      const [scheduleId, periodId, groupId, conditionId, field] = conditionField.getAttribute("data-condition").split("|");
      let value;
      if (field === "offset_minutes") {
        const val = parseFloat(conditionField.value);
        value = isNaN(val) ? 0 : val;
      } else if (conditionField.type === "time") {
        const raw = conditionField.value; // "HH:MM" or "HH:MM:SS" depending on browser
        const normalized = raw ? (raw.length === 5 ? `${raw}:00` : raw) : "";
        value = normalized || (field === "earliest" || field === "latest" ? "" : "00:00:00");
      } else {
        value = conditionField.value.trim();
      }
      this._updateCondition(scheduleId, periodId, groupId, conditionId, field, value);
      return;
    }

    const dayTypeModeSelect = e.target.closest("[data-day-type-mode]");
    if (dayTypeModeSelect) {
      this._config_data.day_type_mode = dayTypeModeSelect.value;
      this._scheduleSave();
      this._render();
      return;
    }

    const dayTypeSensorInput = e.target.closest("[data-day-type-sensor]");
    if (dayTypeSensorInput) {
      this._config_data.day_type_sensor = dayTypeSensorInput.value.trim();
      this._scheduleSave();
      return;
    }

    const dayTypeSensorInverted = e.target.closest("[data-day-type-sensor-inverted]");
    if (dayTypeSensorInverted) {
      this._config_data.day_type_sensor_inverted = dayTypeSensorInverted.checked;
      this._scheduleSave();
      return;
    }

    const weekendDayCheckbox = e.target.closest("[data-weekend-day]");
    if (weekendDayCheckbox) {
      const key = weekendDayCheckbox.getAttribute("data-weekend-day");
      const days = new Set(this._config_data.weekend_days || []);
      if (weekendDayCheckbox.checked) days.add(key);
      else days.delete(key);
      this._config_data.weekend_days = Array.from(days);
      this._scheduleSave();
      return;
    }

    const homeModeSelect = e.target.closest("[data-home-mode]");
    if (homeModeSelect) {
      this._config_data.home_mode = homeModeSelect.value;
      this._scheduleSave();
      this._render();
      return;
    }

    const homeSensorInput = e.target.closest("[data-home-sensor]");
    if (homeSensorInput) {
      this._config_data.home_sensor = homeSensorInput.value.trim();
      this._scheduleSave();
      return;
    }

    const deviceNameInput = e.target.closest("[data-device-name]");
    if (deviceNameInput) {
      this._config_data.device_name = deviceNameInput.value.trim() || "RoomFlow";
      this._scheduleSave();
      return;
    }

    const areaIdSelect = e.target.closest("[data-area-id]");
    if (areaIdSelect) {
      this._config_data.area_id = areaIdSelect.value || null;
      this._scheduleSave();
      return;
    }

    const field = e.target.closest("[data-field]");
    if (field) {
      const [deviceKey, period, variant, key] = field.getAttribute("data-field").split("|");
      const { roomId, entityId } = parseDeviceKey(deviceKey);
      const device = this._findDevice(roomId, entityId);
      if (!device) return;
      const target = device.behaviors[period][variant];
      if (key === "state") {
        target.state = field.checked ? "on" : "off";
      } else if (key === "brightness" || key === "color_temp_kelvin") {
        target[key] = parseInt(field.value, 10);
      }
      this._scheduleSave();
      if (key === "state") this._render();
    }
  }

  _onInput(e) {
    // Live-update the number next to the slider without saving/re-rendering
    const field = e.target.closest('[data-field][type="range"]');
    if (!field) return;
    const parts = field.getAttribute("data-field").split("|");
    const key = parts[3];
    const variantPrefix = parts.slice(0, 3).join("|");
    if (key === "brightness") {
      const span = this.querySelector(`[data-brightness-val="${variantPrefix}"]`);
      if (span) span.textContent = field.value;
    } else if (key === "color_temp_kelvin") {
      const span = this.querySelector(`[data-kelvin-val="${variantPrefix}"]`);
      if (span) span.textContent = field.value;
    }
  }

  // ---------- Rendering ----------

  _render() {
    if (!this._config_data) return;
    const rooms = this._config_data.rooms;

    if (
      this._activeRoomId !== "__add__" &&
      this._activeRoomId !== "__settings__" &&
      this._activeRoomId !== "__buttons__" &&
      !rooms.some((r) => r.id === this._activeRoomId)
    ) {
      this._activeRoomId = rooms.length ? rooms[0].id : "__add__";
    }

    const tabBtn = (id, label, iconName) => `
      <button data-room-tab="${id}" class="rf-tab${id === this._activeRoomId ? " active" : ""}">
        ${iconName ? icon(iconName) : ""}${label}
      </button>`;

    const roomTabsHtml = rooms.map((r) => tabBtn(r.id, r.name, this._roomIcon(r))).join("");
    const activeRoom = rooms.find((r) => r.id === this._activeRoomId);

    let contentHtml;
    if (this._activeRoomId === "__add__") {
      contentHtml = this._renderAddRoomForm();
    } else if (this._activeRoomId === "__settings__") {
      contentHtml = this._renderSettingsForm();
    } else if (this._activeRoomId === "__buttons__") {
      contentHtml = this._renderButtonsTab();
    } else if (activeRoom) {
      contentHtml = this._renderRoom(activeRoom);
    } else {
      contentHtml = this._renderAddRoomForm();
    }

    const allEntityIds = this._hass ? Object.keys(this._hass.states).sort() : [];
    const datalistHtml = `
      <datalist id="all-entities-list">
        ${allEntityIds.map((id) => `<option value="${id}"></option>`).join("")}
      </datalist>
    `;

    this.innerHTML = `
      ${RF_STYLES}
      <ha-card header="RoomFlow" class="rf-root">
        <div class="rf-topbar">
          <div class="rf-tabs">
            ${roomTabsHtml}
            ${tabBtn("__add__", this._t("tab_add_room").replace(/^\+\s*/, ""), "mdi:plus")}
            ${tabBtn("__buttons__", this._t("tab_buttons"), "mdi:gesture-tap-button")}
            ${tabBtn("__settings__", this._t("tab_settings"), "mdi:cog-outline")}
          </div>
          <button id="apply-all-btn" class="rf-btn" style="margin:6px">${icon("mdi:play-outline")}${this._t("test_all")}</button>
        </div>
        <div style="padding:16px">
          ${contentHtml}
        </div>
        ${datalistHtml}
      </ha-card>
    `;
  }

  _renderAddRoomForm() {
    const areaOptions = this._areas
      .map((a) => `<option value="${a.area_id}">${a.name}</option>`)
      .join("");
    const schedules = this._config_data.schedules || [];
    const scheduleOptions = schedules.map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
    return `
      <div class="rf-card">
        <div class="rf-card-title">${icon("mdi:plus-circle-outline")}${this._t("add_room_header")}</div>
        <div style="margin-top:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <select id="new-room-area">
            <option value="">${this._t("custom_name_option")}</option>
            ${areaOptions}
          </select>
          ${textField(`id="new-room-name" placeholder="${this._t("room_name_placeholder")}"`)}
          ${
            schedules.length > 1
              ? `<select id="new-room-schedule" title="${this._t("room_schedule_label")}">${scheduleOptions}</select>`
              : ""
          }
          <button id="add-room-btn" class="rf-btn">${icon("mdi:plus")}${this._t("add")}</button>
        </div>
        <div class="rf-help">
          ${this._t("add_room_help")}
        </div>
      </div>
    `;
  }

  _renderSettingsForm() {
    const hasDayType = this._hasDayType();
    const hasHome = this._hasHome();
    const capsInfo = `
      <div style="font-size:0.9em;opacity:0.8;display:flex;flex-direction:column;gap:4px">
        <span>${icon(hasDayType ? "mdi:check-circle-outline" : "mdi:circle-outline")}${this._t("day_type_condition_label")} ${hasDayType ? this._t("status_enabled") : this._t("status_not_configured")}</span>
        <span>${icon(hasHome ? "mdi:check-circle-outline" : "mdi:circle-outline")}${this._t("home_away_condition_label")} ${hasHome ? this._t("status_enabled") : this._t("status_not_configured")}</span>
        ${!hasDayType || !hasHome ? this._t("enable_more_conditions_help") : ""}
      </div>
    `;

    return `
      <div>
        ${capsInfo}
        <div style="margin-top:20px;border-top:1px solid var(--divider-color);padding-top:4px">
          ${this._renderSchedulesSection()}
          ${this._renderDayTypeSection()}
          ${this._renderHomeSection()}
          ${this._renderDeviceSection()}
        </div>
      </div>
    `;
  }

  // One condition's type-specific operator + value field(s). Every
  // condition type gets its own <select data-condition-type> so switching
  // it (see _updateConditionType) resets the row to that type's defaults.
  _renderConditionFields(scheduleId, p, groupId, c) {
    const path = `${scheduleId}|${p.id}|${groupId}|${c.id}`;

    if (c.type === "time") {
      const operatorOptions = ["after", "before"]
        .map((op) => `<option value="${op}" ${op === c.operator ? "selected" : ""}>${this._t(`operator_${op}`)}</option>`)
        .join("");
      return `
        <select data-condition="${path}|operator">${operatorOptions}</select>
        <input type="time" step="1" data-condition="${path}|value" value="${c.value || "00:00:00"}" style="width:110px" />`;
    }

    if (c.type === "sun") {
      const operatorOptions = ["after", "before"]
        .map((op) => `<option value="${op}" ${op === c.operator ? "selected" : ""}>${this._t(`operator_${op}`)}</option>`)
        .join("");
      const sunEventOptions = SUN_EVENTS.map(
        (s) => `<option value="${s.key}" ${s.key === c.event ? "selected" : ""}>${this._t(s.labelKey)}</option>`
      ).join("");
      return `
        <select data-condition="${path}|operator">${operatorOptions}</select>
        <select data-condition="${path}|event">${sunEventOptions}</select>
        ${textField(`type="number" step="1" data-condition="${path}|offset_minutes" value="${c.offset_minutes ?? 0}" style="width:70px"`)} ${this._t("min_offset")}
        <span style="opacity:0.7;font-size:0.85em">${this._t("earliest_label")}</span>
        <input type="time" step="1" data-condition="${path}|earliest" value="${c.earliest || ""}" style="width:110px" />
        <span style="opacity:0.7;font-size:0.85em">${this._t("latest_label")}</span>
        <input type="time" step="1" data-condition="${path}|latest" value="${c.latest || ""}" style="width:110px" />`;
    }

    if (c.type === "numeric") {
      const operatorOptions = ["above", "below", "equals"]
        .map((op) => `<option value="${op}" ${op === c.operator ? "selected" : ""}>${this._t(`operator_${op}`)}</option>`)
        .join("");
      return `
        <input list="all-entities-list" data-condition="${path}|entity_id" value="${c.entity_id || ""}"
          placeholder="sensor...." style="width:190px" />
        <select data-condition="${path}|operator">${operatorOptions}</select>
        ${textField(`data-condition="${path}|value" value="${c.value || ""}" placeholder="${this._t("value_placeholder")}" style="width:90px"`)}`;
    }

    if (c.type === "state") {
      const operatorOptions = ["is", "is_not"]
        .map((op) => `<option value="${op}" ${op === c.operator ? "selected" : ""}>${this._t(`operator_${op}`)}</option>`)
        .join("");
      return `
        <input list="all-entities-list" data-condition="${path}|entity_id" value="${c.entity_id || ""}"
          placeholder="binary_sensor...." style="width:190px" />
        <select data-condition="${path}|operator">${operatorOptions}</select>
        ${textField(`data-condition="${path}|value" value="${c.value || ""}" placeholder="on" style="width:90px"`)}`;
    }

    if (c.type === "day_type") {
      const valueOptions = ["weekday", "weekend"]
        .map((v) => `<option value="${v}" ${v === c.value ? "selected" : ""}>${this._t(`condition_value_${v}`)}</option>`)
        .join("");
      return `<select data-condition="${path}|value">${valueOptions}</select>`;
    }

    // c.type === "home"
    const valueOptions = ["home", "away"]
      .map((v) => `<option value="${v}" ${v === c.value ? "selected" : ""}>${this._t(`condition_value_${v}`)}</option>`)
      .join("");
    return `<select data-condition="${path}|value">${valueOptions}</select>`;
  }

  _renderConditionRow(scheduleId, p, groupId, c) {
    const typeOptions = CONDITION_TYPES.map(
      (t) => `<option value="${t.key}" ${t.key === c.type ? "selected" : ""}>${this._t(t.labelKey)}</option>`
    ).join("");
    return `
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px">
        ${icon(CONDITION_TYPE_ICONS[c.type])}
        <select data-condition-type="${scheduleId}|${p.id}|${groupId}|${c.id}">${typeOptions}</select>
        ${this._renderConditionFields(scheduleId, p, groupId, c)}
        <button class="rf-icon-btn rf-danger" data-remove-condition="${scheduleId}|${p.id}|${groupId}|${c.id}">${icon("mdi:close")}</button>
      </div>`;
  }

  // One OR'd group: its conditions are AND'd together (see const.py's
  // period docs). No move-up/down needed here (or between groups) - AND/OR
  // are both commutative, so only add/remove matter.
  _renderConditionGroup(scheduleId, p, group) {
    const rows = group.conditions.map((c) => this._renderConditionRow(scheduleId, p, group.id, c)).join("");
    const addOptions = CONDITION_TYPES.map((t) => `<option value="${t.key}">${this._t(t.labelKey)}</option>`).join("");
    return `
      <div class="rf-condition-group">
        <div style="display:flex;align-items:center;gap:6px">
          <span style="font-size:0.85em;opacity:0.7;flex:1">${this._t("and_within_group_help")}</span>
          <button class="rf-icon-btn rf-danger" data-remove-condition-group="${scheduleId}|${p.id}|${group.id}">${icon("mdi:close")}</button>
        </div>
        ${rows}
        <div style="margin-top:6px">
          <select data-add-condition="${scheduleId}|${p.id}|${group.id}">
            <option value="" selected disabled>${this._t("add_condition_placeholder")}</option>
            ${addOptions}
          </select>
        </div>
      </div>`;
  }

  // One period within one schedule - its own name/transition/priority
  // controls plus its condition groups.
  _renderPeriod(scheduleId, p, i, periodCount, defaultTransitions) {
    const groupsHtml = p.condition_groups
      .map((g, gi) => `${gi > 0 ? `<div class="rf-or-divider">${this._t("or_between_groups_label")}</div>` : ""}${this._renderConditionGroup(scheduleId, p, g)}`)
      .join("");
    return `
      <div class="rf-card" style="margin-bottom:8px">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          ${icon(periodIcon(p.id), "", "rf-device-icon")}
          ${textField(`data-period-name="${scheduleId}|${p.id}" value="${p.name || ""}" placeholder="${this._t("name_placeholder")}" style="width:110px"`)}
          ${textField(`type="number" min="0" step="0.5" value="${defaultTransitions[p.id] ?? 0}" data-default-transition="${scheduleId}|${p.id}" style="width:70px" title="${this._t("default_transition_header")}"`)} ${this._t("seconds")}
          <button class="rf-icon-btn" data-move-period-up="${scheduleId}|${p.id}" ${i === 0 ? "disabled" : ""}>${icon("mdi:arrow-up")}</button>
          <button class="rf-icon-btn" data-move-period-down="${scheduleId}|${p.id}" ${i === periodCount - 1 ? "disabled" : ""}>${icon("mdi:arrow-down")}</button>
          <button class="rf-icon-btn rf-danger" data-remove-period="${scheduleId}|${p.id}">${icon("mdi:close")}</button>
        </div>
        <div style="margin-top:6px">${groupsHtml}</div>
        <div style="margin-top:6px">
          <button class="rf-btn rf-btn-flat" data-add-condition-group="${scheduleId}|${p.id}">${icon("mdi:plus")}${this._t("add_condition_group")}</button>
        </div>
      </div>`;
  }

  // One schedule: a named, independent periods list of its own (see
  // DEFAULT_SCHEDULE_ID docs) - a room follows one via room.schedule_id,
  // so e.g. outdoor lighting can have its own simple dusk-to-dawn window
  // instead of the shared indoor morning/day/afternoon/evening/night one.
  _renderSchedule(schedule, scheduleCount) {
    const defaultTransitions = (this._config_data.default_transitions || {})[schedule.id] || {};
    const periods = schedule.periods;
    const periodsHtml = periods
      .map((p, i) => this._renderPeriod(schedule.id, p, i, periods.length, defaultTransitions))
      .join("");

    return `
      <div class="rf-card" style="margin-bottom:12px">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          ${icon("mdi:calendar-clock-outline", "", "rf-device-icon")}
          ${textField(`data-schedule-name="${schedule.id}" value="${schedule.name || ""}" placeholder="${this._t("schedule_name_placeholder")}" style="width:140px"`)}
          ${
            scheduleCount > 1
              ? `<button class="rf-icon-btn rf-danger" data-remove-schedule="${schedule.id}">${icon("mdi:close")}</button>`
              : ""
          }
        </div>
        <div style="margin-top:8px">${periodsHtml}</div>
        <div>
          <button class="rf-btn rf-btn-flat" data-add-period="${schedule.id}">${icon("mdi:plus")}${this._t("add_period")}</button>
        </div>
      </div>`;
  }

  _renderSchedulesSection() {
    const schedules = this._config_data.schedules || [];
    const schedulesHtml = schedules.map((s) => this._renderSchedule(s, schedules.length)).join("");

    return `
      <div class="rf-section">
        <div class="rf-section-title">${icon("mdi:clock-time-eight-outline")}${this._t("schedules_header")}</div>
        <div class="rf-help">
          ${this._t("schedules_help")}
        </div>
        <div style="margin-top:10px">${schedulesHtml}</div>
        <div>
          <button class="rf-btn rf-btn-flat" data-add-schedule>${icon("mdi:plus")}${this._t("add_schedule")}</button>
        </div>
      </div>
    `;
  }

  _renderDayTypeSection() {
    const cd = this._config_data;
    const mode = cd.day_type_mode || "none";

    let detailsHtml = "";
    if (mode === "sensor") {
      detailsHtml = `
        <div style="margin-top:8px">
          <input list="all-entities-list" data-day-type-sensor value="${cd.day_type_sensor || ""}"
            placeholder="sensor.day_type / binary_sensor.jobbdag" style="width:260px" />
        </div>
        <div style="margin-top:6px;font-size:0.85em;opacity:0.85">
          ${this._t("day_type_sensor_help")}
        </div>
        <label style="display:inline-flex;align-items:center;gap:4px;margin-top:4px">
          ${switchEl(`data-day-type-sensor-inverted ${cd.day_type_sensor_inverted ? "checked" : ""}`)}
          ${this._t("day_type_sensor_inverted_label")}
        </label>`;
    } else if (mode === "weekday_selection") {
      const weekendDays = cd.weekend_days || [];
      const checkboxes = WEEKDAYS.map(
        (w) => `
        <label style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;margin-top:6px">
          ${switchEl(`data-weekend-day="${w.key}" ${weekendDays.includes(w.key) ? "checked" : ""}`)}
          ${this._t(w.labelKey)}
        </label>`
      ).join("");
      detailsHtml = `
        <div style="margin-top:8px">
          <div style="opacity:0.7;font-size:0.85em">${this._t("weekend_days_help")}</div>
          ${checkboxes}
        </div>`;
    }

    return `
      <div class="rf-section">
        <div class="rf-section-title">${icon("mdi:calendar-weekend-outline")}${this._t("weekday_weekend_header")}</div>
        <div style="margin-top:6px">
          <select data-day-type-mode>
            <option value="none" ${mode === "none" ? "selected" : ""}>${this._t("option_not_used")}</option>
            <option value="sensor" ${mode === "sensor" ? "selected" : ""}>${this._t("option_existing_sensor")}</option>
            <option value="weekday_selection" ${mode === "weekday_selection" ? "selected" : ""}>${this._t("option_weekday_selection")}</option>
          </select>
        </div>
        ${detailsHtml}
      </div>
    `;
  }

  _renderHomeSection() {
    const cd = this._config_data;
    const mode = cd.home_mode || "none";

    let detailsHtml = "";
    if (mode === "sensor") {
      detailsHtml = `
        <div style="margin-top:8px">
          <input list="all-entities-list" data-home-sensor value="${cd.home_sensor || ""}"
            placeholder="device_tracker.phone / input_boolean.home" style="width:240px" />
        </div>`;
    } else if (mode === "persons") {
      const persons = cd.person_entities || [];
      const rows = persons
        .map(
          (p) => `
        <div style="display:flex;align-items:center;gap:6px;margin-top:6px">
          ${icon("mdi:account-outline")}<span>${p}</span>
          <button class="rf-icon-btn rf-danger" data-remove-person="${p}">${icon("mdi:close")}</button>
        </div>`
        )
        .join("");
      detailsHtml = `
        <div style="margin-top:8px">
          ${rows}
          <div style="margin-top:6px">
            <input list="all-entities-list" id="new-person-entity" placeholder="person.alice" style="width:180px" />
            <button id="add-person-btn" class="rf-btn rf-btn-flat">${icon("mdi:plus")}${this._t("add_person")}</button>
          </div>
        </div>`;
    }

    return `
      <div class="rf-section">
        <div class="rf-section-title">${icon("mdi:home-export-outline")}${this._t("home_away_header")}</div>
        <div style="margin-top:6px">
          <select data-home-mode>
            <option value="none" ${mode === "none" ? "selected" : ""}>${this._t("option_not_used")}</option>
            <option value="sensor" ${mode === "sensor" ? "selected" : ""}>${this._t("option_existing_sensor")}</option>
            <option value="persons" ${mode === "persons" ? "selected" : ""}>${this._t("option_person_entities")}</option>
          </select>
        </div>
        ${detailsHtml}
      </div>
    `;
  }

  _renderDeviceSection() {
    const cd = this._config_data;
    const areaOptions = this._areas
      .map((a) => `<option value="${a.area_id}" ${a.area_id === cd.area_id ? "selected" : ""}>${a.name}</option>`)
      .join("");

    return `
      <div class="rf-section">
        <div class="rf-section-title">${icon("mdi:tune")}${this._t("device_header")}</div>
        <div class="rf-help">
          ${this._t("device_help")}
        </div>
        <div style="margin-top:6px;display:flex;align-items:center;gap:8px">
          ${textField(`data-device-name value="${cd.device_name || "RoomFlow"}" style="width:200px"`)}
          <select data-area-id>
            <option value="">${this._t("no_area_option")}</option>
            ${areaOptions}
          </select>
        </div>
      </div>
    `;
  }

  _renderButtonsTab() {
    const rooms = this._config_data.rooms;
    const actionLabels = {
      toggle: this._t("action_toggle"),
      off: this._t("action_off"),
      apply_now: this._t("action_apply_now"),
      force_period: this._t("action_force_period"),
    };

    const buttonsHtml = (this._config_data.buttons || [])
      .map((b) => {
        const room = rooms.find((r) => r.id === b.room_id);
        // "Force period" always targets the button's own room, so its
        // period choices come from that room's own schedule.
        const roomPeriods = room ? this._roomPeriods(room) : [];
        const actionText =
          actionLabels[b.action] +
          (b.action === "force_period" && b.force_period
            ? ` (${roomPeriods.find((p) => p.id === b.force_period)?.name || b.force_period})`
            : "");
        return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:10px;margin-bottom:8px">
          <span style="display:flex;align-items:center;gap:8px">${icon("mdi:gesture-tap-button")}<b>${b.entity_id}</b> → ${room ? room.name : this._t("room_missing")}: ${actionText}</span>
          <button class="rf-icon-btn rf-danger" data-remove-button="${b.id}">${icon("mdi:close")}</button>
        </div>`;
      })
      .join("");

    const roomOptions = rooms.map((r) => `<option value="${r.id}">${r.name}</option>`).join("");
    // Empty until a room is picked (see the #new-button-room handler in
    // _onChange, which repopulates this from that room's own schedule) -
    // periods aren't a single global list any more, so there's nothing
    // meaningful to show before a room is chosen.
    const periodOptions = "";

    return `
      <div>
        <div class="rf-section-title">${icon("mdi:gesture-tap-button")}${this._t("buttons_header")}</div>
        <div class="rf-help">
          ${this._t("buttons_help")}
        </div>
        <div style="margin-top:12px">${buttonsHtml}</div>
        <div class="rf-card" style="margin-top:16px">
          <div class="rf-card-title">${icon("mdi:plus-circle-outline")}${this._t("add_button_header")}</div>
          <div style="margin-top:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <input id="new-button-entity" list="all-entities-list" placeholder="${this._t("new_button_entity_placeholder")}"
              style="width:220px" />
            <select id="new-button-room">
              <option value="">${this._t("choose_room_option")}</option>
              ${roomOptions}
            </select>
            <select id="new-button-action">
              <option value="toggle">${this._t("action_toggle")}</option>
              <option value="off">${this._t("action_off")}</option>
              <option value="apply_now">${this._t("action_apply_now")}</option>
              <option value="force_period">${this._t("action_force_period")}</option>
            </select>
            <span id="new-button-period-wrap" style="display:none">
              <select id="new-button-period">${periodOptions}</select>
            </span>
            <button id="add-button-btn" class="rf-btn">${icon("mdi:plus")}${this._t("add")}</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderMotionBox(room) {
    const motion = room.motion || { enabled: false, timeout_minutes: 10, triggers: [] };
    const triggers = motion.triggers || [];

    const triggerRows = triggers
      .map((t) => {
        if (t.type === "threshold_above") {
          return `
          <div style="display:flex;align-items:center;gap:6px;margin-top:6px">
            ${icon("mdi:gauge")}
            <span style="opacity:0.7;font-size:0.9em;width:120px">${this._t("motion_sensor_value_above")}</span>
            <input list="all-entities-list" data-motion-trigger-entity="${room.id}|${t.id}"
              value="${t.entity_id || ""}" placeholder="sensor.humidity_..." style="width:180px" />
            ${textField(`type="number" step="1" data-motion-trigger-threshold="${room.id}|${t.id}" value="${t.threshold ?? 60}" style="width:55px"`)}
            <button class="rf-icon-btn rf-danger" data-remove-motion-trigger="${room.id}|${t.id}">${icon("mdi:close")}</button>
          </div>`;
        }
        return `
        <div style="display:flex;align-items:center;gap:6px;margin-top:6px">
          ${icon("mdi:motion-sensor")}
          <span style="opacity:0.7;font-size:0.9em;width:120px">${this._t("motion_label")}</span>
          <input list="all-entities-list" data-motion-trigger-entity="${room.id}|${t.id}"
            value="${t.entity_id || ""}" placeholder="binary_sensor.motion_..." style="width:220px" />
          <button class="rf-icon-btn rf-danger" data-remove-motion-trigger="${room.id}|${t.id}">${icon("mdi:close")}</button>
        </div>`;
      })
      .join("");

    return `
      <div class="rf-card">
        <label class="rf-card-title" style="cursor:pointer">
          ${switchEl(`data-motion-enabled="${room.id}" ${motion.enabled ? "checked" : ""}`)}
          ${icon("mdi:motion-sensor")} ${this._t("motion_active_label")}
        </label>
        <div style="margin-top:6px${motion.enabled ? "" : ";opacity:0.5;pointer-events:none"}">
          <div class="rf-help" style="margin-top:0">
            ${this._t("motion_or_logic_help")}
          </div>
          ${triggerRows}
          <div style="margin-top:8px">
            <button class="rf-btn rf-btn-flat" data-add-motion-trigger="${room.id}|motion">${icon("mdi:motion-sensor")}${this._t("add_motion_sensor")}</button>
            <button class="rf-btn rf-btn-flat" data-add-motion-trigger="${room.id}|threshold_above">${icon("mdi:gauge")}${this._t("add_threshold")}</button>
          </div>
          <div style="margin-top:10px;display:flex;align-items:center;gap:6px;flex-wrap:wrap">
            ${icon("mdi:timer-off-outline")}
            ${this._t("turn_off_after")}
            ${textField(`type="number" min="1" data-motion-timeout="${room.id}" value="${motion.timeout_minutes || 10}" style="width:55px"`)}
            ${this._t("turn_off_after_suffix")}
          </div>
          <div style="margin-top:10px">
            <label style="cursor:pointer;display:flex;align-items:center;gap:6px">
              ${switchEl(`data-motion-warn-enabled="${room.id}" ${motion.warn_enabled ? "checked" : ""}`)}
              ${icon("mdi:brightness-4")} ${this._t("dim_warning_label")}
            </label>
            <div style="margin-top:4px${motion.warn_enabled ? "" : ";opacity:0.5;pointer-events:none"}">
              ${this._t("dim_to")} ${textField(`type="number" min="1" max="255" data-motion-warn-brightness="${room.id}" value="${motion.warn_brightness ?? 25}" style="width:55px"`)} ${this._t("brightness_for")}
              ${textField(`type="number" min="1" data-motion-warn-minutes="${room.id}" value="${motion.warn_minutes ?? 3}" style="width:55px"`)} ${this._t("minutes_before_off")}
            </div>
          </div>
        </div>
        <div class="rf-help">
          ${this._t("motion_footer_help")}
        </div>
      </div>
    `;
  }

  _renderCustomConditionsBox(room) {
    const conditions = room.custom_conditions || [];

    const rows = conditions
      .map(
        (c, i) => `
      <div style="display:flex;align-items:center;gap:6px;margin-top:6px">
        ${textField(`data-condition-name="${room.id}|${c.id}" value="${c.name || ""}" placeholder="${this._t("name_placeholder")}" style="width:120px"`)}
        <input list="all-entities-list" data-condition-entity="${room.id}|${c.id}"
          value="${c.entity_id || ""}" placeholder="binary_sensor...." style="width:200px" />
        <span style="opacity:0.7;font-size:0.85em">${this._t("condition_is")}</span>
        ${textField(`data-condition-state="${room.id}|${c.id}" value="${c.state || ""}" placeholder="on" style="width:70px"`)}
        <button class="rf-icon-btn" data-move-custom-condition-up="${room.id}|${c.id}" ${i === 0 ? "disabled" : ""}>${icon("mdi:arrow-up")}</button>
        <button class="rf-icon-btn" data-move-custom-condition-down="${room.id}|${c.id}" ${
          i === conditions.length - 1 ? "disabled" : ""
        }>${icon("mdi:arrow-down")}</button>
        <button class="rf-icon-btn rf-danger" data-remove-custom-condition="${room.id}|${c.id}">${icon("mdi:close")}</button>
      </div>`
      )
      .join("");

    return `
      <div class="rf-card">
        <div class="rf-card-title">${icon("mdi:tune-variant")}${this._t("custom_conditions_header")}</div>
        <div class="rf-help" style="margin-top:0">
          ${this._t("custom_conditions_help")}
        </div>
        ${rows}
        <div style="margin-top:8px">
          <button class="rf-btn rf-btn-flat" data-add-custom-condition="${room.id}">${icon("mdi:plus")}${this._t("add_condition")}</button>
        </div>
      </div>
    `;
  }

  // One row of period tabs for the whole room: clicking a period here
  // switches every device below to that same period at once (see the
  // data-room-period-tab handler in _onClick), so you can compare what all
  // of the room's devices are set to do for one period side by side,
  // instead of opening each device and clicking through its own tabs
  // individually. Devices can still be flipped to a different period on
  // their own below afterward for a closer look at just that one.
  _renderRoomPeriodTabs(room) {
    const periods = this._roomPeriods(room);
    if (!periods.length) return "";
    const activePeriod = this._activeRoomPeriod[room.id] || periods[0].id;

    const tabsHtml = periods
      .map(
        (p) => `
      <button data-room-period-tab="${room.id}|${p.id}" class="rf-chip${p.id === activePeriod ? " active" : ""}">
        ${icon(periodIcon(p.id))}${p.name}
      </button>`
      )
      .join("");

    return `<div class="rf-chip-row" style="margin-bottom:14px">${tabsHtml}</div>`;
  }

  _renderRoom(room) {
    const devicesHtml = room.devices.map((d) => this._renderDevice(room, d)).join("");
    const availEntities = this._availableEntities(room);
    const entityOptions = availEntities
      .map((e) => `<option value="${e.entity_id}">${e.name} (${e.entity_id})</option>`)
      .join("");

    return `
      <div>
        <div class="rf-room-header">
          <h2>${icon(this._roomIcon(room))}${room.name}</h2>
          <div>
            <button class="rf-btn rf-btn-flat" data-apply-room="${room.id}">${icon("mdi:play-outline")}${this._t("test_now")}</button>
            <button class="rf-btn rf-btn-danger" data-remove-room="${room.id}">${icon("mdi:delete-outline")}${this._t("remove_room")}</button>
          </div>
        </div>
        ${this._renderMotionBox(room)}
        ${this._renderCustomConditionsBox(room)}
        ${this._renderRoomPeriodTabs(room)}
        <div>${devicesHtml}</div>
        <div style="margin-top:14px;display:flex;align-items:center;gap:8px">
          ${icon("mdi:plus-circle-outline")}
          <select data-new-device="${room.id}">
            <option value="">${this._t("add_device_option")}</option>
            ${entityOptions}
          </select>
        </div>
      </div>
    `;
  }

  _renderVariantControls(deviceKey, device, period, variantKey, label, hasToggle, toggleText) {
    const variant = device.behaviors[period][variantKey];
    const supportsBrightness = !!device.supports_brightness;
    const supportsColorTemp = !!device.supports_color_temp;
    const fieldPrefix = `${deviceKey}|${period}|${variantKey}`;
    // Missing/undefined `enabled` means "on" (e.g. "default" on older saved
    // configs never had this field, and unlike weekend/away/conditions -
    // which are always created with an explicit false - it should default
    // to enabled rather than disabled).
    const enabled = variant.enabled !== false;
    const disabled = hasToggle && !enabled;
    const variantClass = ["default", "weekend", "away"].includes(variantKey) ? variantKey : "condition";
    const variantIcon = icon(VARIANT_ICONS[variantClass]);

    const toggleHtml = hasToggle
      ? `<label class="rf-variant-title" style="cursor:pointer">
          ${switchEl(`data-variant-toggle="${fieldPrefix}" ${enabled ? "checked" : ""}`)}
          ${variantIcon}${toggleText || this._t("custom_setting_for", { label: label.toLowerCase() })}
        </label>`
      : `<div class="rf-variant-title">${variantIcon}${label}</div>`;

    return `
      <div class="rf-variant rf-variant-${variantClass}${disabled ? " rf-disabled" : ""}">
        ${toggleHtml}
        <div style="margin-top:6px${disabled ? ";pointer-events:none" : ""}">
          <label style="cursor:pointer">
            ${switchEl(`data-field="${fieldPrefix}|state" ${variant.state === "on" ? "checked" : ""} ${disabled ? "disabled" : ""}`)}
            ${this._t("on_label")}
          </label>
          ${
            supportsBrightness
              ? `<div class="rf-slider-row">
                  ${icon("mdi:brightness-6")} ${this._t("brightness_label")} <span data-brightness-val="${fieldPrefix}">${variant.brightness ?? 255}</span>
                  <input type="range" min="1" max="255" value="${variant.brightness ?? 255}"
                    data-field="${fieldPrefix}|brightness" ${disabled ? "disabled" : ""} />
                </div>`
              : ""
          }
          ${
            supportsColorTemp
              ? `<div class="rf-slider-row">
                  ${icon("mdi:thermometer")} ${this._t("color_temp_label")} <span data-kelvin-val="${fieldPrefix}">${variant.color_temp_kelvin ?? 3000}</span>
                  <input type="range" min="2000" max="6500" step="100" value="${variant.color_temp_kelvin ?? 3000}"
                    data-field="${fieldPrefix}|color_temp_kelvin" ${disabled ? "disabled" : ""} />
                </div>`
              : ""
          }
        </div>
      </div>
    `;
  }

  _renderDevice(room, device) {
    const deviceKey = `${room.id}:${device.entity_id}`;
    // Undefined (never toggled) defaults to open, matching the old
    // always-expanded behavior so nothing looks like it "disappeared" for
    // existing users after this became collapsible.
    const isOpen = this._openDevices[deviceKey] !== false;

    let bodyHtml = "";
    if (isOpen) {
      const periods = this._roomPeriods(room);
      const activePeriod = this._activeTab[deviceKey] || (periods[0] && periods[0].id);

      const tabsHtml = periods
        .map(
          (p) => `
        <button data-tab="${deviceKey}|${p.id}" class="rf-chip${p.id === activePeriod ? " active" : ""}">
          ${icon(periodIcon(p.id))}${p.name}
        </button>`
        )
        .join("");

      let controlsHtml = this._renderVariantControls(
        deviceKey, device, activePeriod, "default", this._t("variant_default"), true,
        this._t("default_variant_help")
      );
      if (this._hasDayType()) {
        controlsHtml += this._renderVariantControls(deviceKey, device, activePeriod, "weekend", this._t("variant_weekend"), true);
      }
      if (this._hasHome()) {
        controlsHtml += this._renderVariantControls(deviceKey, device, activePeriod, "away", this._t("variant_away"), true);
      }
      (room.custom_conditions || []).forEach((cond) => {
        // Lazily initialize this condition's variant so conditions added
        // mid-session don't need a reload to become editable per device.
        if (!device.behaviors[activePeriod][cond.id]) {
          device.behaviors[activePeriod][cond.id] = emptyVariant(device.behaviors[activePeriod].default, true);
        }
        controlsHtml += this._renderVariantControls(
          deviceKey, device, activePeriod, cond.id, cond.name || this._t("condition_fallback_name"), true
        );
      });

      if (device.type === "light") {
        const deviceTransition = device.transitions ? device.transitions[activePeriod] : null;
        const globalDefault = this._config_data.default_transitions
          ? this._config_data.default_transitions[activePeriod] ?? 0
          : 0;
        controlsHtml += `
          <div style="margin-top:10px;font-size:0.9em;display:flex;align-items:center;gap:6px">
            ${icon("mdi:transition")}
            ${this._t("transition_time_label", { s: globalDefault })}
            ${textField(`type="number" min="0" step="0.5" placeholder="${globalDefault}" value="${deviceTransition !== null && deviceTransition !== undefined ? deviceTransition : ""}" data-transition="${deviceKey}|${activePeriod}" style="width:70px"`)}
          </div>
        `;
      }

      if (room.motion && room.motion.enabled) {
        const deviceMotion = device.motion || { enabled: false, off_delay_minutes: null };
        controlsHtml += `
          <div style="margin-top:10px;font-size:0.9em">
            <label style="cursor:pointer;display:flex;align-items:center;gap:6px">
              ${switchEl(`data-device-motion-enabled="${deviceKey}" ${deviceMotion.enabled ? "checked" : ""}`)}
              ${icon("mdi:motion-sensor")} ${this._t("device_motion_reacts")}
            </label>
            <div style="margin-top:4px${deviceMotion.enabled ? "" : ";opacity:0.5;pointer-events:none"}">
              ${this._t("device_off_after")}
              ${textField(`type="number" min="1" placeholder="${room.motion.timeout_minutes || 10}" value="${
                  deviceMotion.off_delay_minutes !== null && deviceMotion.off_delay_minutes !== undefined
                    ? deviceMotion.off_delay_minutes
                    : ""
                }" data-device-motion-delay="${deviceKey}" style="width:55px"`)}
              ${this._t("device_off_after_suffix")}
            </div>
          </div>
        `;
      }

      bodyHtml = `
        <div class="rf-device-body">
          <div class="rf-chip-row">${tabsHtml}</div>
          <div style="margin-top:8px">${controlsHtml}</div>
        </div>
      `;
    }

    return `
      <div class="rf-device${isOpen ? " rf-open" : ""}">
        <div class="rf-device-header" data-device-toggle="${deviceKey}">
          <div class="rf-device-name">
            ${icon(deviceIcon(device), "", "rf-device-icon")}
            <span class="rf-device-text">${device.name}</span>
            <small>(${device.entity_id})</small>
            <span class="rf-badge ${this._liveStatusClass(device)}" data-live-status="${deviceKey}">${this._liveStatusText(device)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:2px;flex:none">
            <button class="rf-icon-btn rf-danger" data-remove-device="${room.id}|${device.entity_id}">${icon("mdi:delete-outline")}</button>
            ${icon(isOpen ? "mdi:chevron-up" : "mdi:chevron-down", "", "rf-caret")}
          </div>
        </div>
        ${bodyHtml}
      </div>
    `;
  }

  getCardSize() {
    return 6;
  }
}

customElements.define("roomflow-card", RoomFlowCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "roomflow-card",
  name: "RoomFlow",
  description: "Control lights and outlets per room based on time of day",
});
