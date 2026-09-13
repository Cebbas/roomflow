# Changelog

## Unreleased

- **Temporary diagnostic logging in `_handle_button_press`** - a
  warning-level log line on every invocation, added to chase down a live
  report of a button's own final click-type-classification state change
  (e.g. `single_push` following its own `btn_down`/`btn_up`) never
  reaching the handler at all, while the two earlier states in the same
  press do. To be removed once root-caused - not a real feature, don't
  rely on this log line.

- **A room-level button can now toggle a custom condition directly**
  (e.g. a "Mys"/scene helper), not just a device or the whole room. A
  house often has a physical button wired to flip a scene-style
  `input_boolean` rather than any one light - previously the only way to
  wire that up was a hand-written automation outside RoomFlow entirely.
  New room button action "Toggle a condition": pick which of the room's
  own custom conditions to flip, and RoomFlow calls
  `homeassistant.toggle` on that condition's own entity when the button
  fires.

- **A motion sensor's own hold time can now be configured, so the
  turn-off timeout means what it says.** A real motion sensor typically
  keeps reporting "on" for a while after the room is actually empty (a
  hardware/firmware hold time that varies per sensor model) - RoomFlow's
  own off-timer only ever started counting from when the sensor's
  `binary_sensor` finally went "off", so the *actual* total time since
  someone left was always longer than the configured timeout by however
  long that sensor holds. Added a per-motion-trigger "hold time"
  (seconds) field in the Motion sensors tab - it's subtracted from every
  timeout that definition drives (the off-delay and, transitively, the
  warn-then-off sequence), so a configured "10 minutes" is 10 minutes
  from when the person actually left, not from whenever the specific
  sensor's own hold time happens to expire. Defaults to 0 (no change in
  behavior) for every existing definition until set.

- **A device's own icon (e.g. from a custom icon pack like Custom Brand
  Icons) now renders correctly in RoomFlow's panel.** RoomFlow is a
  standalone page, not a Lovelace dashboard - so a custom icon
  namespace an entity's `icon` attribute points at (anything other than
  the built-in `mdi:` set) only ever resolved on the user's actual
  dashboards, where that icon pack's own resource script had already run
  once in the page. RoomFlow's own panel now best-effort mirrors every
  registered Lovelace module-type resource into itself at setup, so any
  icon pack (or other resource) that already works on a dashboard also
  works here - read from Home Assistant's own resource storage, not
  hardcoded to any specific pack.

- **The Overview tab now shows a room's motion sensor and humidity
  reading, not just its devices.** If any device in a room uses a
  motion_sensors definition, its motion trigger's live on/off state and
  its humidity threshold trigger's current reading (if either exists)
  now appear alongside the device icons in that room's status row -
  live-updating the same way the device icons already do, not just on a
  full re-render.

- **A flaky BLE/mesh reconnect no longer fires a phantom button press.**
  An `event.*` button trigger (e.g. a Plejd device with an unstable
  connection) can cycle `unavailable` -> its own last cached press
  timestamp -> `unavailable` again purely from reconnecting - not a new
  physical press, but RoomFlow had no way to tell the difference and
  reacted to it as a real one. Since a `event` domain entity's state is
  always the ISO timestamp of when it last fired, a re-announced
  timestamp that's more than 10 seconds old, arriving right after the
  entity was `unavailable` a moment earlier, is now recognized as a stale
  reconnect echo and ignored (logged as `stale_reconnect` in the button
  activity log) rather than triggering the attached action. A genuine
  press always reports a fresh timestamp, so this doesn't affect real
  button presses at all - only ones whose own timestamp gives them away
  as old.

- **A genuine motion pulse now re-lights a motion_on device even when a
  sticky secondary trigger already had the room "active".** A motion
  definition can combine several triggers with OR (e.g. motion OR a
  humidity threshold, so a bathroom light stays on through a shower even
  once someone stops moving) - but only the definition's own
  inactive-to-active edge used to cause anything to re-apply. If a
  secondary trigger stayed satisfied for a long time (humidity lingering
  above its threshold for tens of minutes after a shower), the combined
  flag never went back to false, so a later, real motion pulse - someone
  actually walking back in - looked like "nothing changed" and did
  nothing, even though the light itself had gone off in the meantime for
  an unrelated reason. RoomFlow now also recognizes an actual motion-type
  trigger transitioning to "on" while the definition was already active,
  and re-applies the on-behavior to any motion_on device that's currently
  off - independent of whether the combined flag itself flipped. Threshold
  triggers (humidity, etc.) don't gain this behavior on their own; only a
  real motion-type trigger's own on-transition does.

- **Device commands are now sent blocking, so a real failure is no longer
  logged as a success.** Every light/switch service call RoomFlow makes
  (`_apply_behavior`, toggle/off/dim button actions, motion off, the
  motion dim-warning) previously used Home Assistant's default
  fire-and-forget dispatch: the call returned as soon as it was handed
  off, before the target integration actually executed it. If the device
  then failed (unavailable, a flaky Zigbee/mesh link, a timeout) that
  failure surfaced only as a separate, disconnected error in Home
  Assistant's own log - RoomFlow's own try/except never saw it, so it
  still wrote a normal success entry to the device log. Every one of
  those calls (except the 50ms hold-to-dim ramp tick, deliberately left
  fire-and-forget so a laggy device can't back up the ramp, and which
  never wrote a device-log entry anyway) now passes `blocking=True`, so a
  genuine execution failure raises where the existing error handling
  already expected it - correctly skipping the device-log entry and
  logging a warning instead. No behavior change when devices are healthy;
  the device log now only claims a light actually did something when it
  did.

- **Motion-restore events now log as their own source instead of
  reusing `motion_on`.** A device configured with motion off but not
  motion on (e.g. turned on by a button, then left to motion purely to
  dim-and-turn-off after inactivity) could have its restore-on-return
  event - motion coming back while its off-timer/dim-warning was still
  counting down - show up in the device log as `source: motion_on`,
  which looked like motion was turning the device on from cold despite
  motion_on being disabled. That path now logs as `motion_restored`,
  keeping it clearly distinct from a genuine motion_on activation. No
  behavior change, log clarity only.

- **A manual "turn on" button press is no longer blocked by an
  off-resolving condition or away override.** Previously, if a room
  condition (e.g. a "Natt" override tied to a global night switch) or the
  away override was active and configured to turn a device off, pressing
  its button to turn it back *on* kept resolving to that same "off"
  value for as long as the condition/away state stayed active - not just
  at the moment it started. A manual on now only honours a condition/away
  tier that itself wants "on"; an off-resolving one is skipped in favour
  of the next tier, ultimately the period's own default - so a device can
  force off automatically the moment a condition activates while still
  staying fully button-controllable afterward, on the period's configured
  brightness (set a period's default to a real "on" value, e.g. a dim
  night brightness, to control exactly what a press turns it on to during
  that period).

- **Continuous hold-to-dim button action.** A device's Buttons section can
  now attach a trigger to "Hold to dim" - the light ramps brightness
  smoothly for as long as the button is held, alternating direction each
  time (down from above ~80%, up from below ~20%, otherwise the opposite
  of last time), the same wall-switch pattern several rooms previously
  needed a hand-written automation outside RoomFlow for. Works off any
  entity that reports a live press/release-style signal - an `event.*`
  entity (Plejd, Zigbee2MQTT/ZHA) via its state/`event_type`, or a plain
  `binary_sensor.*` (e.g. a Shelly channel's own `*_input` sensor, "on"
  for exactly as long as the button is physically held) via its on/off
  state. A raw device-event trigger (the Shelly gen1 "Device event"
  option) can't drive this - a completed `shelly.click` event carries no
  "still holding" signal, only a classification after release - point a
  hold trigger at the channel's own input `binary_sensor` instead. Doesn't
  actually start ramping until held past the same threshold used for
  timed short/long press detection, so a plain short click - which also
  briefly reports the same "on"/"press" signal - never nudges the
  brightness, even when a separate toggle trigger shares the same
  physical button/input.

- **A motion-controlled device left to dim-and-turn-off after motion
  stops now correctly restores to full brightness if motion comes back
  mid-countdown.** Previously this only worked for devices motion itself
  also turns *on* (`motion_on` enabled) - a device meant to be turned on
  some other way (typically a bound button) and left purely to motion for
  the dim-warning/off/restore sequence (`motion_on` off, `motion_off` on)
  had no way to interrupt its own countdown: if someone was still there
  when it dimmed as a warning, it kept counting down to off regardless.
  Fixes the classic bathroom/toilet pattern of "button turns the light
  on, motion governs when it dims and turns back off."

- **Genuine short vs. long press for press/release-only button entities
  (e.g. Plejd).** Hardware whose `event.*` entity only ever reports a
  plain `press`/`release` pair, with no click-duration classification of
  its own (confirmed with Plejd buttons via `thomasloven/hass-plejd` -
  see `BUTTON_PROFILES.md`), can now use two new click types, "Short
  press (timed)" / "Long press (timed)", which RoomFlow resolves itself
  by timing the gap between the entity's `press` and its matching
  `release` (500ms threshold by default, or a custom threshold in
  milliseconds set per trigger). Bind two triggers to the same entity,
  one of each type, to get distinct short-press and long-press actions
  from a single physical button.
- **Physical buttons can now bind directly to a raw device event, not
  just an entity - Shelly (gen1) built in.** Some button hardware (e.g.
  Shelly gen1 relays/inputs) fires a raw Home Assistant event
  (`shelly.click`) with no backing entity at all, so it previously
  couldn't be bound without hand-writing an external template-sensor
  package to bridge it into something RoomFlow could see. The Buttons
  tab's "Add button trigger" form now offers a "Device event" option
  alongside "Entity": pick a built-in device profile (Shelly gen1 to
  start), enter its device ID/channel (found via Developer Tools →
  Events), and RoomFlow listens for and matches the raw event itself -
  same click-type (single/double/long) support as an entity-based
  trigger. Every button trigger can also be copied (as a small JSON
  snippet) and pasted into another RoomFlow install, so a working
  Shelly/Zigbee button setup can be shared with someone who has the same
  hardware. See `BUTTON_PROFILES.md` for the Shelly gen1 profile details
  and a community "tested against" hardware list, and for how to add a
  new device profile.
- **Button presses are now logged.** The Buttons tab has a new "Button
  activity" log showing every recognized press of a bound button,
  whether or not it ended up attached to anything - so a press that
  doesn't do what's expected is answerable from the card itself ("is
  Home Assistant even seeing this?") instead of only from server logs.
- **Fixed: the card could keep running a stale cached copy of itself
  after an update.** The card's JS module URL now includes a
  `?v=<version>` query string that changes on every release, so the
  browser's own module cache can't silently keep serving an old version
  against a newer backend until a hard refresh.
- **Fixed: a failed config save could fail silently.** If the
  `roomflow/save_config` websocket call was rejected (backend exception,
  connection dropped mid-request), the change stayed only in the card's
  in-memory state with no indication anything went wrong until the next
  reload quietly dropped it - now logged to the browser console.
- **Button-driven "on" now applies the device's real per-period
  brightness/color, and devices can be bound to dim up/down.** Pressing a
  toggle/on button used to call a bare `light.turn_on`/`switch.turn_on`
  with no brightness or color - the light just came back at whatever it
  last had, ignoring RoomFlow's configured Default/Weekend/Away/condition
  value for the current period, even though motion-driven "on" already
  resolved this correctly. Fixed by resolving the same behavior a manual
  press should apply (still working for "button" control-mode devices,
  which schedule/motion ticks deliberately leave alone - a manual press
  is the only trigger those ever get). "Off" is unchanged - a bare
  turn off. Also new: a device's Buttons section can bind a trigger to
  "Dim up"/"Dim down" (light devices only), stepping brightness by 10% per
  press.
- **Fixed: adding a button trigger did nothing.** The new shared
  `button_triggers` catalog was never initialized to an empty list for
  existing configs (unlike `motion_sensors`/`rooms`/`buttons`), so both
  adding a fresh trigger and migrating old button bindings crashed with a
  silent JS error - "Add" in the Buttons tab just did nothing, and configs
  with existing bindings could fail to load at all.
- **Buttons are now a shared trigger library, like motion sensors, with
  click-type support.** The Buttons tab is now a catalog of reusable
  button triggers (entity + optional click type: single/double/long
  press) instead of a flat list bundling entity, room, target device and
  action together. Each device gets its own small "Buttons" section
  (attach a trigger → toggle/turn off just that device) and each room
  gets a "Room buttons" section (whole-room toggle/off, or run
  schedule/force a period) - so the same physical button can drive more
  than one attachment, and a Zigbee/Shelly button's single vs. long-press
  can trigger different things. Existing button bindings migrate
  automatically with no behavior change.
- **Motion sensors are now a shared, named library instead of a
  per-room setting.** A new "Motion sensors" tab lets you build named,
  reusable motion-sensor definitions (sensors, timeout, dim-warning)
  once. Each device's control mode now picks *which* definition it
  subscribes to, per period - not a room-wide switch, so two devices in
  the same room can react to two different sensors, and two rooms can
  share one. Existing per-room motion setups migrate automatically into
  their own definition with no behavior change.
- **Button bindings can target one specific device, not just the whole
  room.** `toggle`/`off` button actions used to always act on every
  device in the room together (`toggle` even picked on-vs-off by majority
  vote) - there was no way to bind two physical switch channels in the
  same room to two different lights. Adding a button now lets you pick a
  device from the chosen room, or leave it as "Whole room" for the
  existing behavior.
- **Ambient re-applies no longer fight manual changes.** Every routine
  recompute (a tracked sensor changing, a time boundary, or - if any
  period uses a sun condition - a 1-minute poll) used to re-issue the
  exact same `light.turn_on`/`turn_off` call and log entry for every
  schedule-controlled device, even when nothing had changed, which meant
  manually turning off a light that's "on" per schedule got undone again
  within a minute. RoomFlow now remembers the target it last set per
  device and skips a re-apply whenever the schedule's own target hasn't
  moved since - so a manual change (app, voice, physical button) sticks
  until the schedule's target actually changes (new period, condition,
  weekend/away state), not on every ambient tick in between. Explicit
  triggers (Test now, bound buttons' apply_now/force_period) are
  unaffected and still force a re-apply as before.
- **Per-period control mode (schedule / motion sensor / button-manual),
  replacing the old "let the schedule control this period" checkbox.**
  Each device/period now picks explicitly how it's controlled: by the
  schedule, by this room's motion trigger (with independent "turns on
  with motion" / "turns off with motion" toggles, so a device can react
  to only one), or left alone for button/manual control only - so a
  device can be schedule-driven during the day and motion-driven at
  night, per period, instead of one all-or-nothing device-wide motion
  flag. Existing configs migrate automatically with no behavior change.
- **Device-wide default away behavior**, shown next to the period tabs
  and applying to every period while away, unless that period has its
  own away override enabled (existing per-period away setting still
  takes priority when set) - instead of having to configure away
  behavior period by period from scratch.
- The device header icon now shows the entity's own registered icon
  (falling back to the generic lightbulb/plug icon only if it has none).
- **Multiple independent schedules, so a room (e.g. outdoor lighting) can
  follow its own periods instead of the shared indoor one.** Periods used
  to be one single global list shared by every room. Settings -> Schedules
  now lets you create as many named schedules as you want, each with its
  own independent, priority-ordered periods list (built with the same
  condition-group editor as before). Every room picks which schedule
  governs it when it's added (defaulting to the existing "Main" schedule,
  auto-created from your current periods, so nothing changes for existing
  rooms). Each schedule's periods also get their own default-transition
  timing and their own "current period"/per-period on-off sensors, grouped
  under a device named after the schedule so two schedules can both have a
  period called e.g. "morning" without colliding.
- **Periods are now built from a condition list instead of 5 fixed source
  rows.** Each period previously always showed all 5 source types
  (schedule/sun/illuminance/boolean/sensor) at once, each with its own
  enable toggle, plus a hidden weekend-override sub-row and an "extra AND
  condition" sub-row. That's replaced by an explicit condition-list
  builder: pick a condition type (time, sun position, numeric sensor,
  sensor state, weekday/weekend, home/away) from a list to add it, group
  conditions with AND within a group and OR between groups, and use
  before/after (time/sun) or above/below/equals (numeric) or is/is not
  (state) operators - plus new earliest/latest clamps on sun conditions
  (the old "never before" floor now also has a ceiling). The backend
  resolution algorithm is simplified to match: the first period (priority
  order) with a true condition group wins, replacing the old special-cased
  clock-boundary race. Existing saved periods migrate automatically to the
  new shape with equivalent behavior.
- **Fixed: `ha-switch`/`ha-textfield` fields could end up unreadable/
  uneditable (v0.0.7).** Unlike `ha-icon`, which is always part of Home
  Assistant's core frontend bundle, `ha-textfield`/`ha-switch` are only
  loaded by more specialized panels (settings dialogs, config flows) and
  aren't guaranteed to be registered as custom elements yet just because
  the frontend is running - depends on what else was open in that browser
  session. An unregistered custom element silently renders as an empty,
  non-interactive box instead of erroring. Every checkbox and text/number
  field now checks `customElements.get(...)` first and falls back to a
  plain `<input>` when the native component isn't actually available, so
  it always works either way.
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
