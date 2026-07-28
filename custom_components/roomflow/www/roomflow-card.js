// RoomFlow - custom Lovelace card / sidebar panel
// Place this file at /config/www/roomflow-card.js and register it as a
// resource: Settings -> Dashboards -> Resources -> /local/roomflow-card.js
// (JavaScript module)

// Periods are a user-editable, priority-ordered list stored in
// this._config_data.periods (mirrors const.py's `periods`/infer_periods -
// each {id, name, sources: {type: {enabled, ...fields}}}). A period can
// have several of its 5 sources enabled at once - it's active if ANY of
// them currently resolves true (OR logic). These constants are only the
// *shape* helpers (source-type choices, default seed values,
// legacy-migration inputs) - never a fixed list of periods themselves.

const PERIOD_SOURCES = [
  { key: "schedule", label: "Schedule" },
  { key: "sun", label: "Sun position" },
  { key: "illuminance", label: "Illuminance (lux) sensor" },
  { key: "boolean", label: "Existing boolean" },
  { key: "sensor", label: "Existing sensor" },
];

const DEFAULT_SOURCE_FIELDS = {
  schedule: { time: "00:00:00" },
  sun: { event: "sunrise", offset_minutes: 0 },
  illuminance: { entity_id: null, threshold: 0 },
  boolean: { entity_id: null },
  sensor: { entity_id: null, value: "" },
};

// Normalize one period to the current multi-source shape ({id, name,
// sources: {type: {enabled, ...fields}}}), mirroring const.py's
// _normalize_period. Entries saved before a period could combine several
// sources at once have a single `source`/`config` pair instead - migrate
// that one active source in as enabled; every other type is present but
// disabled with blank defaults so the card can always show all 5 side by
// side. Also backfills any type missing from an already multi-source entry.
function normalizePeriod(period) {
  if (period.sources) {
    const sources = {};
    PERIOD_SOURCES.forEach(({ key }) => {
      sources[key] = period.sources[key]
        ? { ...period.sources[key] }
        : { enabled: false, ...DEFAULT_SOURCE_FIELDS[key] };
    });
    return { id: period.id, name: period.name || "", sources };
  }

  const oldSource = period.source || "schedule";
  const oldConfig = period.config || {};
  const sources = {};
  PERIOD_SOURCES.forEach(({ key }) => {
    sources[key] =
      key === oldSource
        ? { enabled: true, ...DEFAULT_SOURCE_FIELDS[key], ...oldConfig }
        : { enabled: false, ...DEFAULT_SOURCE_FIELDS[key] };
  });
  return { id: period.id, name: period.name || "", sources };
}

// Keys must match actual astral.sun attribute names (what Home Assistant's
// get_astral_event_date looks up) - "noon"/"midnight", not "solar_noon"/
// "solar_midnight".
const SUN_EVENTS = [
  { key: "dawn", label: "Dawn" },
  { key: "sunrise", label: "Sunrise" },
  { key: "noon", label: "Solar noon" },
  { key: "sunset", label: "Sunset" },
  { key: "dusk", label: "Dusk" },
  { key: "midnight", label: "Solar midnight" },
];

const WEEKDAYS = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
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
    this._activeRoomId = null; // room.id | "__add__" | "__buttons__" | "__settings__"
    this._saveTimeout = null;

    this.addEventListener("click", (e) => this._onClick(e));
    this.addEventListener("change", (e) => this._onChange(e));
    this.addEventListener("input", (e) => this._onInput(e));
  }

  // Custom element constructors must not add child nodes (the spec
  // forbids it and browsers enforce it - "A newly constructed custom
  // element must not have child nodes"). The initial placeholder has to
  // wait until here instead.
  connectedCallback() {
    if (!this.hasChildNodes()) {
      this.innerHTML = "<ha-card><div style='padding:16px'>Loading…</div></ha-card>";
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

  _migrateConfig() {
    const cd = this._config_data;
    if (!cd.rooms) cd.rooms = [];
    if (!cd.buttons) cd.buttons = [];
    if (!cd.default_transitions) cd.default_transitions = { ...DEFAULT_TRANSITIONS };

    // Periods: a user-editable, priority-ordered list (add/remove/rename/
    // reorder), each combining any of 5 sources at once (OR logic). Older
    // installs have either the pre-existing global time_sources/time_mode
    // plus parallel per-period dicts instead of a `periods` list, or a
    // `periods` list from before a period could combine several sources -
    // normalizePeriod migrates both into the current shape (mirrors
    // const.py's infer_periods on the backend).
    if (!cd.periods) {
      cd.periods = buildPeriodsFromLegacy(cd);
    }
    cd.periods = cd.periods.map(normalizePeriod);

    // Day-type/home-away: infer "sensor" if an older bare sensor field is
    // already set and no explicit mode was ever saved.
    if (!cd.day_type_mode) cd.day_type_mode = cd.day_type_sensor ? "sensor" : "none";
    if (!cd.weekend_days) cd.weekend_days = [...DEFAULT_WEEKEND_DAYS];
    if (!cd.home_mode) cd.home_mode = cd.home_sensor ? "sensor" : "none";
    if (!cd.person_entities) cd.person_entities = [];

    if (!cd.device_name) cd.device_name = "RoomFlow";
    if (cd.area_id === undefined) cd.area_id = null;

    cd.rooms.forEach((room) => {
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
      (room.devices || []).forEach((device) => {
        if (!device.transitions) device.transitions = {};
        if (!device.motion) device.motion = { enabled: false, off_delay_minutes: null };
        const behaviors = device.behaviors || {};
        cd.periods.forEach((p) => {
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

  _buildDevice(entity) {
    const type = entity.domain === "light" ? "light" : "outlet";
    const supportsBrightness = !!entity.supports_brightness;
    const supportsColorTemp = !!entity.supports_color_temp;

    const base = { state: "off" };
    if (supportsBrightness) base.brightness = 255;
    if (supportsColorTemp) base.color_temp_kelvin = 3000;

    const behaviors = {};
    (this._config_data.periods || []).forEach((p) => {
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

  _addRoom(name, areaId) {
    // Lights/outlets already assigned to this area in Home Assistant are
    // added automatically, so a room tied to an area starts pre-populated
    // instead of empty.
    const devices = areaId
      ? this._entities.filter((e) => e.area_id === areaId).map((e) => this._buildDevice(e))
      : [];
    const room = { id: uid(), name: name, area_id: areaId || null, devices: devices };
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
    room.devices.push(this._buildDevice(entity));
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
    room.custom_conditions.push({ id: uid(), name: "New condition", entity_id: "", state: "on" });
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
  // highest, first period whose own sources resolve active wins). Each
  // period can have several of its 5 sources enabled at once - it's active
  // if ANY of them currently resolves true (OR logic, same pattern as a
  // room's motion triggers/custom conditions) - mirrors custom conditions
  // above and const.py's DEFAULT_PERIODS/infer_periods on the backend.
  _addPeriod() {
    if (!this._config_data.periods) this._config_data.periods = [];
    this._config_data.periods.push(
      normalizePeriod({ id: uid(), name: "New period", source: "schedule", config: { time: "00:00:00" } })
    );
    this._scheduleSave();
    this._render();
  }

  _removePeriod(periodId) {
    this._config_data.periods = (this._config_data.periods || []).filter((p) => p.id !== periodId);
    this._scheduleSave();
    this._render();
  }

  _updatePeriod(periodId, field, value) {
    const period = (this._config_data.periods || []).find((p) => p.id === periodId);
    if (!period) return;
    period[field] = value;
    this._scheduleSave();
  }

  _updatePeriodConfig(periodId, sourceType, field, value) {
    const period = (this._config_data.periods || []).find((p) => p.id === periodId);
    if (!period) return;
    period.sources[sourceType][field] = value;
    this._scheduleSave();
    if (field === "enabled") this._render();
  }

  _movePeriod(periodId, direction) {
    const periods = this._config_data.periods || [];
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
    if (st.state === "unavailable") return " · unavailable";
    if (st.state === "on") {
      const b = st.attributes ? st.attributes.brightness : null;
      return ` · now: on${b ? ` (${Math.round((b / 255) * 100)}%)` : ""}`;
    }
    return " · now: off";
  }

  _updateLiveStatusTexts() {
    this.querySelectorAll("[data-live-status]").forEach((el) => {
      const { roomId, entityId } = parseDeviceKey(el.getAttribute("data-live-status"));
      const device = this._findDevice(roomId, entityId);
      if (device) el.textContent = this._liveStatusText(device);
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

    const periodTab = e.target.closest("[data-tab]");
    if (periodTab) {
      const [deviceKey, period] = periodTab.getAttribute("data-tab").split("|");
      this._activeTab[deviceKey] = period;
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

    if (e.target.closest("[data-add-period]")) {
      this._addPeriod();
      return;
    }

    const removePeriodBtn = e.target.closest("[data-remove-period]");
    if (removePeriodBtn) {
      this._removePeriod(removePeriodBtn.getAttribute("data-remove-period"));
      return;
    }

    const movePeriodUpBtn = e.target.closest("[data-move-period-up]");
    if (movePeriodUpBtn) {
      this._movePeriod(movePeriodUpBtn.getAttribute("data-move-period-up"), "up");
      return;
    }

    const movePeriodDownBtn = e.target.closest("[data-move-period-down]");
    if (movePeriodDownBtn) {
      this._movePeriod(movePeriodDownBtn.getAttribute("data-move-period-down"), "down");
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
      const areaId = areaSelect.value;
      let name = nameInput.value.trim();
      if (areaId) {
        const area = this._areas.find((a) => a.area_id === areaId);
        name = name || (area ? area.name : "");
      }
      if (!name) return;
      this._addRoom(name, areaId || null);
      return;
    }

    if (e.target.closest("#apply-all-btn")) {
      const btn = e.target.closest("#apply-all-btn");
      const original = btn.textContent;
      btn.textContent = "Applying…";
      btn.disabled = true;
      this._hass.callWS({ type: "roomflow/apply_now" }).finally(() => {
        btn.textContent = "Done!";
        setTimeout(() => {
          btn.textContent = original;
          btn.disabled = false;
        }, 1200);
      });
      return;
    }

    const applyRoomBtn = e.target.closest("[data-apply-room]");
    if (applyRoomBtn) {
      const roomId = applyRoomBtn.getAttribute("data-apply-room");
      const original = applyRoomBtn.textContent;
      applyRoomBtn.textContent = "Applying…";
      applyRoomBtn.disabled = true;
      this._hass
        .callWS({ type: "roomflow/apply_room", room_id: roomId })
        .finally(() => {
          applyRoomBtn.textContent = "Done!";
          setTimeout(() => {
            applyRoomBtn.textContent = original;
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
      this._updateCustomCondition(roomId, conditionId, "name", conditionName.value.trim() || "Condition");
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
      const period = defaultTransitionInput.getAttribute("data-default-transition");
      const val = parseFloat(defaultTransitionInput.value);
      this._config_data.default_transitions[period] = isNaN(val) ? 0 : val;
      this._scheduleSave();
      return;
    }

    // ---------- Settings tab: time-of-day periods / day-type / home-away / device ----------

    const periodNameInput = e.target.closest("[data-period-name]");
    if (periodNameInput) {
      this._updatePeriod(
        periodNameInput.getAttribute("data-period-name"),
        "name",
        periodNameInput.value.trim() || "Period"
      );
      return;
    }

    const periodSourceEnabled = e.target.closest("[data-period-source-enabled]");
    if (periodSourceEnabled) {
      const [periodId, sourceType] = periodSourceEnabled.getAttribute("data-period-source-enabled").split("|");
      this._updatePeriodConfig(periodId, sourceType, "enabled", periodSourceEnabled.checked);
      return;
    }

    const periodConfigField = e.target.closest("[data-period-config]");
    if (periodConfigField) {
      const [periodId, sourceType, field] = periodConfigField.getAttribute("data-period-config").split("|");
      let value;
      if (field === "threshold" || field === "offset_minutes") {
        const val = parseFloat(periodConfigField.value);
        value = isNaN(val) ? 0 : val;
      } else if (field === "time") {
        const raw = periodConfigField.value; // "HH:MM" or "HH:MM:SS" depending on browser
        value = raw ? (raw.length === 5 ? `${raw}:00` : raw) : "00:00:00";
      } else {
        value = periodConfigField.value.trim();
      }
      this._updatePeriodConfig(periodId, sourceType, field, value);
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

    const tabBtn = (id, label) => `
      <button data-room-tab="${id}" style="
        ${id === this._activeRoomId
          ? "font-weight:bold;border-bottom:2px solid var(--primary-color);color:var(--primary-color)"
          : "border-bottom:2px solid transparent"};
        background:none;border-top:none;border-left:none;border-right:none;
        padding:8px 12px;cursor:pointer;font-size:1em;white-space:nowrap
      ">${label}</button>`;

    const roomTabsHtml = rooms.map((r) => tabBtn(r.id, r.name)).join("");
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
      <ha-card header="RoomFlow">
        <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--divider-color);padding:0 8px">
          <div style="display:flex;overflow-x:auto">
            ${roomTabsHtml}
            ${tabBtn("__add__", "+ Room")}
            ${tabBtn("__buttons__", "🔘 Buttons")}
            ${tabBtn("__settings__", "⚙ Settings")}
          </div>
          <button id="apply-all-btn" style="margin:6px;white-space:nowrap">Test all</button>
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
    return `
      <div>
        <b>Add room</b><br>
        <select id="new-room-area" style="margin-top:6px">
          <option value="">— Custom name —</option>
          ${areaOptions}
        </select>
        <input id="new-room-name" placeholder="Room name" style="margin-left:6px" />
        <button id="add-room-btn" style="margin-left:6px">Add</button>
        <div style="opacity:0.7;font-size:0.85em;margin-top:6px">
          Picking an area adds its lights/outlets to the room automatically.
        </div>
      </div>
    `;
  }

  _renderSettingsForm() {
    const dt = this._config_data.default_transitions || {};
    const periods = this._config_data.periods || [];
    const rows = periods.map(
      (p) => `
      <div style="margin-top:8px;display:flex;align-items:center;gap:8px">
        <span style="width:110px">${p.name}</span>
        <input type="number" min="0" step="0.5" value="${dt[p.id] ?? 0}"
          data-default-transition="${p.id}" style="width:70px" /> seconds
      </div>`
    ).join("");

    const hasDayType = this._hasDayType();
    const hasHome = this._hasHome();
    const capsInfo = `
      <div style="margin-top:16px;font-size:0.9em;opacity:0.8">
        Day-type condition (weekend): ${hasDayType ? "enabled" : "not configured"}<br>
        Home/away condition: ${hasHome ? "enabled" : "not configured"}<br>
        ${
          !hasDayType || !hasHome
            ? "Set the relevant source below (Weekday/weekend and/or Home/away) to enable more conditions."
            : ""
        }
      </div>
    `;

    return `
      <div>
        <b>Default transition time per period</b>
        <div style="opacity:0.7;font-size:0.9em;margin-top:4px">
          Applies to every light, unless an individual device has its own transition time set.
        </div>
        ${rows}
        ${capsInfo}
        <div style="margin-top:20px;border-top:1px solid var(--divider-color);padding-top:12px">
          ${this._renderPeriodsSection()}
          ${this._renderDayTypeSection()}
          ${this._renderHomeSection()}
          ${this._renderDeviceSection()}
        </div>
      </div>
    `;
  }

  _renderPeriodSourceRow(p, sourceKey, label) {
    const cfg = p.sources[sourceKey];
    const enabled = !!cfg.enabled;

    let fieldsHtml = "";
    if (sourceKey === "schedule") {
      fieldsHtml = `
        <input type="time" step="1" data-period-config="${p.id}|schedule|time"
          value="${cfg.time || "00:00:00"}" ${enabled ? "" : "disabled"} style="width:110px" />`;
    } else if (sourceKey === "sun") {
      const sunEventOptions = SUN_EVENTS.map(
        (s) => `<option value="${s.key}" ${s.key === cfg.event ? "selected" : ""}>${s.label}</option>`
      ).join("");
      fieldsHtml = `
        <select data-period-config="${p.id}|sun|event" ${enabled ? "" : "disabled"}>${sunEventOptions}</select>
        <input type="number" step="1" data-period-config="${p.id}|sun|offset_minutes"
          value="${cfg.offset_minutes ?? 0}" ${enabled ? "" : "disabled"} style="width:70px" /> min offset`;
    } else if (sourceKey === "illuminance") {
      fieldsHtml = `
        <input list="all-entities-list" data-period-config="${p.id}|illuminance|entity_id"
          value="${cfg.entity_id || ""}" placeholder="sensor.outdoor_illuminance" ${enabled ? "" : "disabled"} style="width:200px" />
        <input type="number" data-period-config="${p.id}|illuminance|threshold"
          value="${cfg.threshold ?? 0}" ${enabled ? "" : "disabled"} style="width:80px" /> lx`;
    } else if (sourceKey === "boolean") {
      fieldsHtml = `
        <input list="all-entities-list" data-period-config="${p.id}|boolean|entity_id"
          value="${cfg.entity_id || ""}" placeholder="binary_sensor...." ${enabled ? "" : "disabled"} style="width:220px" />`;
    } else if (sourceKey === "sensor") {
      fieldsHtml = `
        <input list="all-entities-list" data-period-config="${p.id}|sensor|entity_id"
          value="${cfg.entity_id || ""}" placeholder="sensor.time_of_day" ${enabled ? "" : "disabled"} style="width:200px" />
        <span style="opacity:0.7;font-size:0.85em">=</span>
        <input data-period-config="${p.id}|sensor|value" value="${cfg.value || ""}"
          placeholder="value" ${enabled ? "" : "disabled"} style="width:100px" />`;
    }

    return `
      <div style="display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap">
        <label style="display:flex;align-items:center;gap:4px;width:170px">
          <input type="checkbox" data-period-source-enabled="${p.id}|${sourceKey}" ${enabled ? "checked" : ""} />
          ${label}
        </label>
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap${enabled ? "" : ";opacity:0.5"}">
          ${fieldsHtml}
        </div>
      </div>`;
  }

  _renderPeriodsSection() {
    const periods = this._config_data.periods || [];

    const rows = periods
      .map(
        (p, i) => `
      <div style="margin-top:8px;padding:8px;border:1px dashed var(--divider-color);border-radius:6px">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
          <input data-period-name="${p.id}" value="${p.name || ""}" placeholder="Name" style="width:110px" />
          <button data-move-period-up="${p.id}" ${i === 0 ? "disabled" : ""}>↑</button>
          <button data-move-period-down="${p.id}" ${i === periods.length - 1 ? "disabled" : ""}>↓</button>
          <button data-remove-period="${p.id}">✕</button>
        </div>
        ${PERIOD_SOURCES.map((s) => this._renderPeriodSourceRow(p, s.key, s.label)).join("")}
      </div>`
      )
      .join("");

    return `
      <div>
        <b>Time-of-day periods</b>
        <div style="opacity:0.7;font-size:0.85em;margin-top:4px">
          Priority order (top wins) - the first period with any enabled source
          currently resolving to "active" is the current period. Add, remove,
          rename or reorder freely; check off whichever sources you want each
          period to use - if more than one is checked, the period is active
          when ANY of them says so.
        </div>
        ${rows}
        <div style="margin-top:8px">
          <button data-add-period>+ Add period</button>
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
          For a plain on/off sensor (no "weekend"/"helg"-style text), pick what "on" means:
        </div>
        <label style="display:inline-flex;align-items:center;gap:4px;margin-top:4px">
          <input type="checkbox" data-day-type-sensor-inverted ${cd.day_type_sensor_inverted ? "checked" : ""} />
          "On" means weekday (e.g. a workday/jobbdag-style sensor) - unchecked means "on" = weekend
        </label>`;
    } else if (mode === "weekday_selection") {
      const weekendDays = cd.weekend_days || [];
      const checkboxes = WEEKDAYS.map(
        (w) => `
        <label style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;margin-top:6px">
          <input type="checkbox" data-weekend-day="${w.key}" ${weekendDays.includes(w.key) ? "checked" : ""} />
          ${w.label}
        </label>`
      ).join("");
      detailsHtml = `
        <div style="margin-top:8px">
          <div style="opacity:0.7;font-size:0.85em">Which days count as "weekend":</div>
          ${checkboxes}
        </div>`;
    }

    return `
      <div style="margin-top:20px">
        <b>Weekday/weekend</b>
        <div style="margin-top:6px">
          <select data-day-type-mode>
            <option value="none" ${mode === "none" ? "selected" : ""}>Not used</option>
            <option value="sensor" ${mode === "sensor" ? "selected" : ""}>Existing sensor</option>
            <option value="weekday_selection" ${mode === "weekday_selection" ? "selected" : ""}>Weekday selection</option>
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
          <span>${p}</span>
          <button data-remove-person="${p}">✕</button>
        </div>`
        )
        .join("");
      detailsHtml = `
        <div style="margin-top:8px">
          ${rows}
          <div style="margin-top:6px">
            <input list="all-entities-list" id="new-person-entity" placeholder="person.alice" style="width:180px" />
            <button id="add-person-btn" style="margin-left:6px">+ Add</button>
          </div>
        </div>`;
    }

    return `
      <div style="margin-top:20px">
        <b>Home/away</b>
        <div style="margin-top:6px">
          <select data-home-mode>
            <option value="none" ${mode === "none" ? "selected" : ""}>Not used</option>
            <option value="sensor" ${mode === "sensor" ? "selected" : ""}>Existing sensor</option>
            <option value="persons" ${mode === "persons" ? "selected" : ""}>Person entities</option>
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
      <div style="margin-top:20px">
        <b>Device</b>
        <div style="opacity:0.7;font-size:0.85em;margin-top:4px">
          Groups RoomFlow's own sensors (current period, day type, home state, per-period booleans).
        </div>
        <div style="margin-top:6px;display:flex;align-items:center;gap:8px">
          <input data-device-name value="${cd.device_name || "RoomFlow"}" style="width:200px" />
          <select data-area-id>
            <option value="">— No area —</option>
            ${areaOptions}
          </select>
        </div>
      </div>
    `;
  }

  _renderButtonsTab() {
    const rooms = this._config_data.rooms;
    const periods = this._config_data.periods || [];
    const actionLabels = {
      toggle: "Toggle on/off",
      off: "Turn off room",
      apply_now: "Run scheduled behavior now",
      force_period: "Force a specific period",
    };

    const buttonsHtml = (this._config_data.buttons || [])
      .map((b) => {
        const room = rooms.find((r) => r.id === b.room_id);
        const actionText =
          actionLabels[b.action] +
          (b.action === "force_period" && b.force_period
            ? ` (${periods.find((p) => p.id === b.force_period)?.name || b.force_period})`
            : "");
        return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:var(--secondary-background-color);border-radius:6px;margin-bottom:8px">
          <span><b>${b.entity_id}</b> → ${room ? room.name : "(room missing)"}: ${actionText}</span>
          <button data-remove-button="${b.id}">✕</button>
        </div>`;
      })
      .join("");

    const roomOptions = rooms.map((r) => `<option value="${r.id}">${r.name}</option>`).join("");
    const periodOptions = periods.map((p) => `<option value="${p.id}">${p.name}</option>`).join("");

    return `
      <div>
        <b>Physical buttons</b>
        <div style="opacity:0.7;font-size:0.9em;margin-top:4px">
          Bind a physical button/remote (e.g. a Zigbee button that shows up as an
          "event" or "sensor" entity in Home Assistant) to an action in a room.
        </div>
        <div style="margin-top:12px">${buttonsHtml}</div>
        <div style="margin-top:16px;border-top:1px solid var(--divider-color);padding-top:12px">
          <b>Add button</b><br>
          <input id="new-button-entity" list="all-entities-list" placeholder="entity_id (e.g. event.kitchen_button)"
            style="margin-top:6px;width:220px" />
          <select id="new-button-room" style="margin-left:6px">
            <option value="">Choose room…</option>
            ${roomOptions}
          </select>
          <select id="new-button-action" style="margin-left:6px">
            <option value="toggle">Toggle on/off</option>
            <option value="off">Turn off room</option>
            <option value="apply_now">Run scheduled behavior now</option>
            <option value="force_period">Force a specific period</option>
          </select>
          <span id="new-button-period-wrap" style="display:none">
            <select id="new-button-period">${periodOptions}</select>
          </span>
          <button id="add-button-btn" style="margin-left:6px">Add</button>
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
            <span style="opacity:0.7;font-size:0.9em;width:130px">Sensor value above</span>
            <input list="all-entities-list" data-motion-trigger-entity="${room.id}|${t.id}"
              value="${t.entity_id || ""}" placeholder="sensor.humidity_..." style="width:180px" />
            <input type="number" step="1" data-motion-trigger-threshold="${room.id}|${t.id}"
              value="${t.threshold ?? 60}" style="width:55px" />
            <button data-remove-motion-trigger="${room.id}|${t.id}">✕</button>
          </div>`;
        }
        return `
        <div style="display:flex;align-items:center;gap:6px;margin-top:6px">
          <span style="opacity:0.7;font-size:0.9em;width:130px">Motion</span>
          <input list="all-entities-list" data-motion-trigger-entity="${room.id}|${t.id}"
            value="${t.entity_id || ""}" placeholder="binary_sensor.motion_..." style="width:220px" />
          <button data-remove-motion-trigger="${room.id}|${t.id}">✕</button>
        </div>`;
      })
      .join("");

    return `
      <div style="margin-bottom:14px;padding:8px;border:1px dashed var(--divider-color);border-radius:6px">
        <label>
          <input type="checkbox" data-motion-enabled="${room.id}" ${motion.enabled ? "checked" : ""} />
          Motion control active in this room
        </label>
        <div style="margin-top:6px${motion.enabled ? "" : ";opacity:0.5;pointer-events:none"}">
          <div style="font-size:0.85em;opacity:0.7">
            The room counts as "active" if ANY condition below is currently true (OR logic).
          </div>
          ${triggerRows}
          <div style="margin-top:8px">
            <button data-add-motion-trigger="${room.id}|motion">+ Motion sensor</button>
            <button data-add-motion-trigger="${room.id}|threshold_above" style="margin-left:6px">+ Threshold (e.g. humidity)</button>
          </div>
          <div style="margin-top:8px">
            Turn off after
            <input type="number" min="1" data-motion-timeout="${room.id}"
              value="${motion.timeout_minutes || 10}" style="width:55px" />
            minutes with no condition true (default for devices below with no
            override of their own)
          </div>
          <div style="margin-top:8px">
            <label>
              <input type="checkbox" data-motion-warn-enabled="${room.id}" ${
                motion.warn_enabled ? "checked" : ""
              } />
              Dim as a warning before turning off
            </label>
            <div style="margin-top:4px${motion.warn_enabled ? "" : ";opacity:0.5;pointer-events:none"}">
              Dim to <input type="number" min="1" max="255" data-motion-warn-brightness="${room.id}"
                value="${motion.warn_brightness ?? 25}" style="width:55px" /> brightness for
              <input type="number" min="1" data-motion-warn-minutes="${room.id}"
                value="${motion.warn_minutes ?? 3}" style="width:55px" /> minutes before turning off -
              motion during this window restores full brightness instead.
            </div>
          </div>
        </div>
        <div style="opacity:0.7;font-size:0.85em;margin-top:6px">
          When active, the room's scheduled behavior runs immediately (like "Test now"). Pick
          which devices react to motion, and their own off-delay, on each device below.
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
        <input data-condition-name="${room.id}|${c.id}" value="${c.name || ""}"
          placeholder="Name" style="width:120px" />
        <input list="all-entities-list" data-condition-entity="${room.id}|${c.id}"
          value="${c.entity_id || ""}" placeholder="binary_sensor...." style="width:200px" />
        <span style="opacity:0.7;font-size:0.85em">is</span>
        <input data-condition-state="${room.id}|${c.id}" value="${c.state || ""}"
          placeholder="on" style="width:70px" />
        <button data-move-custom-condition-up="${room.id}|${c.id}" ${i === 0 ? "disabled" : ""}>↑</button>
        <button data-move-custom-condition-down="${room.id}|${c.id}" ${
          i === conditions.length - 1 ? "disabled" : ""
        }>↓</button>
        <button data-remove-custom-condition="${room.id}|${c.id}">✕</button>
      </div>`
      )
      .join("");

    return `
      <div style="margin-bottom:14px;padding:8px;border:1px dashed var(--divider-color);border-radius:6px">
        <b>Custom conditions</b>
        <div style="opacity:0.7;font-size:0.85em;margin-top:4px">
          Room-specific overrides, checked in priority order (top wins) - above
          away/weekend/default. Each gets its own morning/day/afternoon/evening/night
          behavior per device below, same as away/weekend.
        </div>
        ${rows}
        <div style="margin-top:8px">
          <button data-add-custom-condition="${room.id}">+ Add condition</button>
        </div>
      </div>
    `;
  }

  _renderRoom(room) {
    const devicesHtml = room.devices.map((d) => this._renderDevice(room, d)).join("");
    const availEntities = this._availableEntities(room);
    const entityOptions = availEntities
      .map((e) => `<option value="${e.entity_id}">${e.name} (${e.entity_id})</option>`)
      .join("");

    return `
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <b style="font-size:1.1em">${room.name}</b>
          <div>
            <button data-apply-room="${room.id}" style="margin-right:6px">Test now</button>
            <button data-remove-room="${room.id}">Remove room</button>
          </div>
        </div>
        ${this._renderMotionBox(room)}
        ${this._renderCustomConditionsBox(room)}
        <div>${devicesHtml}</div>
        <div style="margin-top:10px">
          <select data-new-device="${room.id}">
            <option value="">+ Add device…</option>
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

    const toggleHtml = hasToggle
      ? `<label><input type="checkbox" data-variant-toggle="${fieldPrefix}" ${
          enabled ? "checked" : ""
        } /> ${toggleText || `Custom setting for ${label.toLowerCase()}`}</label>`
      : `<b>${label}</b>`;

    return `
      <div style="margin-top:10px;padding:8px;border:1px dashed var(--divider-color);border-radius:6px;${
        disabled ? "opacity:0.5" : ""
      }">
        ${toggleHtml}
        <div style="margin-top:6px${disabled ? ";pointer-events:none" : ""}">
          <label>
            <input type="checkbox" data-field="${fieldPrefix}|state" ${
              variant.state === "on" ? "checked" : ""
            } ${disabled ? "disabled" : ""} />
            On
          </label>
          ${
            supportsBrightness
              ? `<div style="margin-top:4px">
                  Brightness: <span data-brightness-val="${fieldPrefix}">${variant.brightness ?? 255}</span><br>
                  <input type="range" min="1" max="255" value="${variant.brightness ?? 255}"
                    data-field="${fieldPrefix}|brightness" ${disabled ? "disabled" : ""} style="width:100%" />
                </div>`
              : ""
          }
          ${
            supportsColorTemp
              ? `<div style="margin-top:4px">
                  Color temp (K): <span data-kelvin-val="${fieldPrefix}">${variant.color_temp_kelvin ?? 3000}</span><br>
                  <input type="range" min="2000" max="6500" step="100" value="${variant.color_temp_kelvin ?? 3000}"
                    data-field="${fieldPrefix}|color_temp_kelvin" ${disabled ? "disabled" : ""} style="width:100%" />
                </div>`
              : ""
          }
        </div>
      </div>
    `;
  }

  _renderDevice(room, device) {
    const deviceKey = `${room.id}:${device.entity_id}`;
    const periods = this._config_data.periods || [];
    const activePeriod = this._activeTab[deviceKey] || (periods[0] && periods[0].id);

    const tabsHtml = periods.map(
      (p) => `
      <button data-tab="${deviceKey}|${p.id}" style="${
        p.id === activePeriod
          ? "font-weight:bold;border-bottom:2px solid var(--primary-color)"
          : ""
      };margin-right:4px;background:none;border:none;padding:4px 6px;cursor:pointer">${p.name}</button>`
    ).join("");

    let controlsHtml = this._renderVariantControls(
      deviceKey, device, activePeriod, "default", "Default", true,
      "Let the schedule control this period (uncheck to leave this device alone here - e.g. button/manual only)"
    );
    if (this._hasDayType()) {
      controlsHtml += this._renderVariantControls(deviceKey, device, activePeriod, "weekend", "Weekend", true);
    }
    if (this._hasHome()) {
      controlsHtml += this._renderVariantControls(deviceKey, device, activePeriod, "away", "Away", true);
    }
    (room.custom_conditions || []).forEach((cond) => {
      // Lazily initialize this condition's variant so conditions added
      // mid-session don't need a reload to become editable per device.
      if (!device.behaviors[activePeriod][cond.id]) {
        device.behaviors[activePeriod][cond.id] = emptyVariant(device.behaviors[activePeriod].default, true);
      }
      controlsHtml += this._renderVariantControls(
        deviceKey, device, activePeriod, cond.id, cond.name || "Condition", true
      );
    });

    if (device.type === "light") {
      const deviceTransition = device.transitions ? device.transitions[activePeriod] : null;
      const globalDefault = this._config_data.default_transitions
        ? this._config_data.default_transitions[activePeriod] ?? 0
        : 0;
      controlsHtml += `
        <div style="margin-top:10px;font-size:0.9em">
          Transition time (sec) — default is ${globalDefault}s:
          <input type="number" min="0" step="0.5" placeholder="${globalDefault}"
            value="${deviceTransition !== null && deviceTransition !== undefined ? deviceTransition : ""}"
            data-transition="${deviceKey}|${activePeriod}" style="width:70px" />
        </div>
      `;
    }

    if (room.motion && room.motion.enabled) {
      const deviceMotion = device.motion || { enabled: false, off_delay_minutes: null };
      controlsHtml += `
        <div style="margin-top:10px;font-size:0.9em">
          <label>
            <input type="checkbox" data-device-motion-enabled="${deviceKey}" ${
              deviceMotion.enabled ? "checked" : ""
            } />
            Reacts to this room's motion/threshold triggers
          </label>
          <div style="margin-top:4px${deviceMotion.enabled ? "" : ";opacity:0.5;pointer-events:none"}">
            Off after
            <input type="number" min="1" placeholder="${room.motion.timeout_minutes || 10}"
              value="${
                deviceMotion.off_delay_minutes !== null && deviceMotion.off_delay_minutes !== undefined
                  ? deviceMotion.off_delay_minutes
                  : ""
              }"
              data-device-motion-delay="${deviceKey}" style="width:55px" />
            minutes (blank = room default)
          </div>
        </div>
      `;
    }

    return `
      <div style="margin-bottom:14px;padding:8px;background:var(--secondary-background-color);border-radius:6px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>${device.name} <small style="opacity:0.7">(${device.entity_id})</small><small data-live-status="${deviceKey}">${this._liveStatusText(device)}</small></span>
          <button data-remove-device="${room.id}|${device.entity_id}">✕</button>
        </div>
        <div style="margin-top:6px">${tabsHtml}</div>
        <div style="margin-top:8px">${controlsHtml}</div>
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
