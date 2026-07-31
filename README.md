<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

🌍 **English** | [Svenska](README.sv.md) | [Norsk](README.no.md) | [Suomi](README.fi.md) | [Dansk](README.da.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

> ⚠️ **Early days:** this integration is under active development — expect
> some rough edges and occasional breaking changes between releases.

Control lights and outlets per room based on time of day — with optional
weekend/away overrides, transition times, physical button bindings, and
motion/threshold-based automation. Built for Home Assistant as a custom
integration plus a companion Lovelace card that also works as a full
sidebar page.

## Why

Most "time of day" lighting setups end up as a pile of automations that are
painful to adjust. RoomFlow gives you one place to say, per room and per
device: *what should this light/outlet do in the morning, during the day,
in the evening, at night — and does that change on weekends or when nobody's
home?* Then layers on top of that for physical buttons and motion/sensor
triggers.

## Features

- **Time-of-day scheduling** — define behavior (on/off, brightness, color
  temperature) per device for as many periods as you want. Periods
  (morning/day/afternoon/evening/night by default) are a fully user-editable,
  priority-ordered list: add, remove, rename, and reorder them freely from
  the card. Each period can combine any of 5 sources at once, checked off
  independently: a built-in **clock schedule** (a start time), the **sun's
  position** (a solar event - dawn/sunrise/solar noon/sunset/dusk - plus
  offset), an **illuminance sensor** (a lux threshold), an **existing
  boolean** (point a `binary_sensor`/`input_boolean` you already have at it —
  "on" means it's active), or an **existing sensor** (map one of its state
  values to it, so this works with any time-of-day sensor in any language).
  A period is active if ANY of its enabled sources currently says so (OR
  logic). Which period is "current" is resolved by priority: the first
  active period in the list (top = highest priority) wins — so you can
  freely mix source types (e.g. an illuminance-sourced period above a
  schedule-sourced one to let darkness override the clock). Once
  weekday/weekend is configured (see below), the schedule and sun sources
  can each optionally set a different time/solar event for weekends — e.g.
  morning can start later on Saturdays and Sundays — without needing a
  whole separate period just for that.
- **Weekend and away overrides** (optional) — for each, choose an existing
  sensor (a plain on/off `binary_sensor` works too — just tell RoomFlow which
  polarity "on" means for weekday/weekend), a built-in option (pick which
  weekdays count as weekend; pick one or more `person.*` entities for
  home/away), or leave it unused. These two choices, and the time-of-day
  source above, are fully independent — mix and match. Override the default
  behavior for specific devices during weekends or while away. Precedence:
  **away > weekend > default**.
- **Per-room custom conditions** — beyond the house-wide weekend/away axes,
  each room can define its own ordered list of conditions (a name + an
  entity + the state that means it's active), checked in priority order
  *above* away/weekend/default. Each condition gets its own per-period
  (morning/day/afternoon/evening/night) behavior per device, exactly like
  weekend/away — useful for behavior tied to something specific to that
  room (e.g. a particular person's presence) rather than the whole house.
- **Transition times** — a global default per period, overridable per
  device/period.
- **Physical buttons** — bind any entity (a Zigbee button showing up as an
  `event` or `sensor` entity, for example) to an action: toggle the room,
  turn it off, run the scheduled behavior now, or force a specific period
  regardless of the actual time.
- **Motion & threshold triggers per room** — combine multiple conditions
  with OR logic: motion sensors and/or numeric threshold sensors (e.g.
  "humidity above 65%"). The room is considered "active" the moment any
  condition is true, runs its scheduled behavior immediately, and each
  motion-enabled device (picked per device, with its own off-delay
  overriding the room's default) turns off again once nothing is true
  anymore — optionally dimming to a low brightness first as a warning
  (motion during that window restores full brightness instead of turning
  off). A physical button press locks that device out of motion control
  until the next fresh motion cycle, so it doesn't immediately get
  overridden.
- **Card UI** — manage *everything* (rooms, devices, buttons, motion, and
  all the time-of-day/weekday/home-away settings above) from a tabbed
  custom card, either embedded in a dashboard or as its own auto-registered
  sidebar page. Nothing is configured through Home Assistant's native "Add
  integration" wizard — that step just adds RoomFlow with a single click;
  everything else lives in the card's Settings tab and applies instantly,
  no reload needed.
- **Live status & manual test** — see each device's actual current state,
  and trigger "test now" per room or for everything at once.
- **Diagnostics** — download a diagnostics file (Settings → Devices &
  services → RoomFlow → Download diagnostics) for bug reports, without
  exposing your specific device entity_ids.
- **Exposed as real entities** — RoomFlow creates three ordinary sensor
  entities (current period, day type, home state) plus one binary_sensor
  per period (morning/day/afternoon/evening/night — "on" exactly when that
  period is the currently resolved one, regardless of which source(s)
  determined it) that show up like any other entity: usable in your own
  automations/dashboards. Their device name and area are set from the
  card's Settings tab, no need to hunt them down under Entities afterward.
- **Resilient** — a failing device logs a warning instead of blocking the
  rest of the room.

## Installation

### Via HACS (custom repository)

1. HACS → Integrations → the three-dot menu → **Custom repositories**
2. Add this repository URL, category **Integration**
3. Install "RoomFlow", restart Home Assistant

### Manual

1. Copy `custom_components/roomflow` into `config/custom_components/`
   (the card is bundled inside it, at `custom_components/roomflow/www/` —
   no separate copy needed)
2. Restart Home Assistant

### Setup

1. **Settings → Devices & services → Add integration → RoomFlow** — there's
   nothing to fill in, just confirm. Everything else happens in the card.

   RoomFlow serves its own card and registers it automatically — no
   `config/www` copy and no manual **Settings → Dashboards → Resources**
   entry needed. It also adds itself as a page in the sidebar. You can add
   the card to any dashboard manually too:
   ```yaml
   type: custom:roomflow-card
   ```
2. Open the RoomFlow card (sidebar or dashboard) → **⚙ Settings** tab, and
   configure:
   - **Time-of-day periods** — an ordered list (top = highest priority),
     starting with the 5 defaults (morning/day/afternoon/evening/night).
     Add, remove, rename, or reorder (↑/↓) freely. Each period can check off
     any combination of 5 sources — it's active if ANY enabled one currently
     says so (OR logic):
     - Schedule: a start time.
     - Sun position: a solar event (dawn/sunrise/solar noon/sunset/dusk) +
       an optional +/- minute offset.
     - Illuminance: a lux sensor + a lux threshold.
     - Existing boolean: a `binary_sensor`/`input_boolean` that's "on"
       exactly when this period should be active.
     - Existing sensor: an entity + the state value that means this period
       is active (works with any time-of-day sensor in any language).
     The current period is whichever one is highest in the list that's
     currently active. Once Weekday/weekend below is configured, Schedule
     and Sun position each get an optional weekend override — a separate
     start time or solar event just for weekend days.
   - **Weekday/weekend** and **Home/away** — each either "not used", an
     existing sensor, or a built-in option (weekday checklist; one or more
     `person.*` entities), independent of everything else.
   - **Device** — name and area for RoomFlow's own sensors.

   Every change here applies instantly — no reload, nothing to save
   separately.

## How it works

Each room contains devices (lights/outlets). Each device has a behavior per
period, picked in this order when RoomFlow applies it:

1. **Away** override, if enabled for that period and the home/away source
   currently reports "away"
2. **Weekend** override, if enabled for that period and the weekday/weekend
   source currently reports a weekend value
3. **Default** behavior

RoomFlow re-applies automatically whenever a configured source changes:
sensor-based inputs react to state changes, built-in ones react to their own
clock (a schedule boundary, or midnight for the weekday selection) — and it
also reacts immediately to button presses and motion/threshold triggers
you've configured.

## Contributing

Issues and pull requests are welcome. This is a relatively young project —
expect some rough edges, especially around more advanced condition
combinations and additional device types (climate, media_player, etc. are
natural next steps). If you've confirmed a raw-event button profile (e.g.
Shelly gen1) against your own hardware, see
[BUTTON_PROFILES.md](BUTTON_PROFILES.md) for how to add it to the tested-
hardware list.

## Supported languages

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl) —
this README, the card's own UI, and the config flow all follow the same 8
languages. The card picks its language from Home Assistant's language
setting automatically.

## License

MIT — see [LICENSE](LICENSE).
