# Changelog

## Unreleased

- **Reverted: native `ha-switch`/`ha-textfield` form components (v0.0.7).**
  After release, many fields became unreadable/uneditable in practice -
  reverted back to plain browser `<input>` for checkboxes and text/number
  fields, since that was proven to work reliably throughout this project
  and the Material component swap couldn't be verified live before
  shipping. Same visual redesign (icons, colors, layout) stays in place;
  only the underlying form elements changed back.
- **Fixed: "Test now" (room and all-rooms) lost its icon after the first
  click.** The button's transient "Applying…"/"Done!" text was set via
  `textContent`, which wiped out the icon element inside it instead of
  just swapping the visible label. Now saves/restores `innerHTML` so the
  icon survives.
- **Visual redesign of the card.** Icons throughout (device type, period,
  Default/Weekend/Away/condition variant, source type, and every action
  button), a shared stylesheet replacing most of the scattered inline
  styles, colored accent borders per behavior variant so
  Default/Weekend/Away/condition boxes are easier to tell apart at a
  glance, and device cards are now collapsible (click the header to
  expand/collapse, open by default) with a live on/off status badge
  instead of plain text. Purely visual - no config shape or behavior
  changes.
- **Fixed: a room's period tabs didn't work.** They shared the same
  `data-room-tab` attribute as the unrelated room-switcher tabs (Living
  Room/Kitchen/+ Room/etc.), so clicking a period tab was silently
  swallowed by the room-switcher's click handler instead. Renamed to
  `data-room-period-tab` to fix it.
- **Room-level period overview tabs.** Each room now has its own row of
  period tabs (Morning/Day/Afternoon/Evening/Night) above its device list.
  Clicking one switches every device in the room to that period at once, so
  you can compare what all of a room's devices are set to do for a given
  period side by side, instead of opening each device and clicking through
  its own tabs individually. Devices can still be flipped to a different
  period on their own afterward for a closer look at just that one.
- **The card and the config flow are now fully multi-language**, matching
  the README's 7 languages (sv/no/da/fi/de/fr/nl) plus English. The card
  (`www/roomflow-card.js`) picks its language from Home Assistant's own
  `hass.language`, via an in-file string table (`STRINGS`/`_t()`) with
  English fallback for any missing key — no build step, no external
  translation files. The config flow's confirmation step
  (`custom_components/roomflow/translations/`) is translated the same way.
  Room/device/period/condition names you type in yourself are left alone —
  only the card's own labels, buttons, and help text are translated.
- **Schedule/sun period sources can have a different time on weekends.**
  Once a Weekday/weekend source is configured, a schedule-sourced period
  can optionally set a separate start time for weekend days, and a
  sun-sourced period can optionally set a separate solar event/offset —
  without needing a whole separate period just for weekends.
- **The card now lives inside the integration itself**
  (`custom_components/roomflow/www/roomflow-card.js`) instead of a separate
  top-level `www/` folder. Installing (HACS or manual) is now a single
  folder copy — RoomFlow serves the card itself and auto-registers it as a
  Lovelace resource, so the old manual `config/www` copy and **Settings →
  Dashboards → Resources** steps are no longer needed. Requires Home
  Assistant 2024.7.0+ (bumped from 2024.1.0) for the static-path
  registration API this relies on
- **Time-of-day periods are now a user-editable, priority-ordered list.**
  Morning/day/afternoon/evening/night are no longer fixed — add, remove,
  rename, and reorder periods freely from the card's Settings tab. Each
  period can combine any of 5 sources at once (schedule, sun position,
  illuminance/lux sensor, an existing boolean, an existing sensor) instead
  of one source config shared across all periods — a period is active if
  ANY of its enabled sources currently resolves true (OR logic, same
  pattern as a room's motion triggers). Which period is "current" is
  resolved by priority order: the first period in the list that's active
  wins — the same model already used for per-room custom conditions.
  Existing installs migrate automatically: the 5 built-in periods keep
  their original ids, so no device behavior data or entity IDs change on
  upgrade
- **Opt a device out of the schedule for specific periods.** The "Default"
  behavior per device/period now has its own on/off toggle, just like
  weekend/away already did — uncheck it for a period to leave that device
  completely alone then (e.g. button/manual-only during the day), while
  away/weekend/room-condition overrides for that same period still apply
  normally when active. Fixed the `websocket_api.py` area lookup for the
  card's room-add flow along the way: most entities get their area from the
  *device* they belong to, not the entity itself, so devices in an area
  weren't being detected before
- **Advanced per-device motion control.** Motion/threshold triggers are still
  room-level (OR-combined), but which *devices* react and their own
  off-delay are now per-device instead of one shared room timeout. Optional
  dim-to-a-low-brightness warning stage before turning off (motion during
  the warning restores full brightness instead). A physical button
  (`toggle`/`off`) now locks a device out of motion control until the next
  fresh motion cycle (inactive→active), so a manual press doesn't get
  immediately fought by ongoing motion
- **Per-room custom conditions.** Each room can now define its own ordered
  list of conditions (name + entity + expected state, e.g. `binary_sensor.
  daughter_home` is `on`), checked in priority order above away/weekend/
  default. Each condition gets its own morning/day/afternoon/evening/night
  behavior per device, exactly like the built-in weekend/away overrides —
  useful for behavior tied to something specific to that room rather than
  the whole house's day-type/home-away state
- Weekday/weekend "existing sensor" mode now also accepts a plain on/off
  `binary_sensor` (previously only text values like "weekend"/"helg" were
  recognized) — pick which polarity "on" means (weekday or weekend) per sensor
- **All settings moved from the config flow into the card's Settings tab.**
  "Add integration" is now a single confirmation with nothing to fill in;
  time-of-day sources, weekday/weekend, home/away, and the RoomFlow device's
  name/area are all configured from the card instead, the same way
  rooms/devices/buttons/motion already are — and every change applies
  instantly, with no integration reload. Existing installs are migrated
  automatically (one-time, on first load after upgrading): whatever was set
  via the old config flow keeps working unchanged. The old "Configure"
  options flow no longer exists, since there's nothing left for it to edit
- Time-of-day, weekday/weekend, and home/away can each independently be
  sourced from an existing sensor (as before) **or** built by RoomFlow itself
  with no external entity: a clock-time schedule per period, a weekday
  checklist, or a list of `person.*` entities — mix and match freely across
  the three
- Time-of-day sources are combinable: pick any subset of existing sensor,
  existing per-period booleans (`binary_sensor`/`input_boolean`), illuminance
  (lux) sensor, sun position (solar event + offset per period), and clock
  schedule — RoomFlow tries them in that fixed order and uses whichever
  resolves first, as a fallback chain. Every source is optional; only
  picking at least one is required
- New per-period `binary_sensor` output entities (morning/day/afternoon/
  evening/night) — "on" exactly when that period is the currently resolved
  one, regardless of which source(s) determined it
- New sensor entities: current period, day type, and home state — real HA
  entities usable in your own automations
- Diagnostics support (Settings → Devices & services → RoomFlow → Download
  diagnostics)

## 0.1.0

Initial release.

- Time-of-day scheduling (5 configurable periods) per room, per light/outlet
- Optional weekend and away overrides per device/period (precedence: away > weekend > default)
- Per-device and global default transition times
- Physical button bindings: toggle, turn off, run now, or force a specific period
- Motion control per room with multiple OR-combined triggers (motion sensors
  and/or numeric threshold sensors, e.g. humidity)
- Auto-registered sidebar page, plus a reusable custom Lovelace card
- Live device status and per-room/all "test now" buttons
