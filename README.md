<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

🌍 **English** | [Svenska](README.sv.md) | [Norsk](README.no.md) | [Suomi](README.fi.md) | [Dansk](README.da.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

> ⚠️ **Early days:** this integration is under active development — expect
> some rough edges and occasional breaking changes between releases.
> Requires Home Assistant 2024.7.0 or newer.

Control lights and outlets per room based on time of day — with weekend/away
overrides, physical buttons (including raw Zigbee/Shelly-style events with no
backing entity), motion/threshold triggers, and per-room custom conditions.
Everything is configured from one companion Lovelace card; the integration
itself has nothing to fill in.

## Why

Most "time of day" lighting setups end up as a pile of separate automations
that are painful to adjust — one for the schedule, one per motion sensor, one
per button, all fighting each other when you make a manual change. RoomFlow
gives you one place to say, per room and per device: *what should this
light/outlet do in the morning, during the day, in the evening, at night —
and does that change on weekends, while nobody's home, or when a specific
condition in this room is true?* Then layers physical buttons and
motion/sensor triggers on top, so all of it stays in sync with the same
schedule instead of quietly overriding each other.

## At a glance

- **As many independent schedules as you want** — most rooms share one, but
  e.g. outdoor lighting can follow its own simple dusk-to-dawn schedule
  without cluttering everyone else's period list.
- **Periods built from a condition list** — time, sun position, a numeric
  sensor threshold, a sensor's state, weekday/weekend, home/away — combined
  with AND/OR, priority-ordered.
- **Weekend, away, and per-room custom condition overrides**, each with their
  own per-device behavior, checked in a fixed precedence order.
- **A device-wide "while away" default**, so you don't have to configure away
  behavior period by period unless one period actually needs to differ.
- **Per-period control mode** — schedule-driven, motion-driven, or
  button/manual-only, chosen independently for every device and period.
- **Motion sensors as a shared, reusable library** — build a trigger once,
  point as many devices as you want at it, in any room.
- **Buttons as a shared, reusable library too** — including raw
  Zigbee/Shelly-style hardware events with no backing entity at all, click-type
  awareness (single/double/long), and copy/paste sharing of a working button
  setup.
- **A manual change sticks** — turning something on/off by hand doesn't get
  silently reverted a minute later; it's respected until the schedule's own
  target actually changes.
- **Live status, activity logs, and a button-specific event log** for
  answering "did this actually do what I expected" without guessing.
- **Card UI for everything** — nothing is configured through Home Assistant's
  native integration setup beyond a single confirmation click.

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

### First-time setup

**Settings → Devices & services → Add integration → RoomFlow** — there's
nothing to fill in, just confirm. RoomFlow serves its own card and registers
it automatically: no `config/www` copy, no manual **Settings → Dashboards →
Resources** entry, and it adds itself as its own page in the sidebar. You can
still add the card to any dashboard manually too, if you'd rather:

```yaml
type: custom:roomflow-card
```

Everything from here on happens inside the card. Every change autosaves
(about half a second after you stop typing/clicking) and applies live —
nothing to reload.

## Guide

### Rooms and devices

A **room** holds one or more **devices** (any `light.*` or `switch.*`
entity — the same entity can be added to more than one room if you want).
Add a room from the **+ Room** tab, either linked to an existing Home
Assistant Area (its lights/switches are added automatically) or with a plain
name. Add more devices to a room any time from the **+ Add device** picker at
the bottom of that room's tab.

Each device is collapsible; open it to see its period tabs (one per period
in whichever schedule the room follows) and, below those, its control mode,
its away-default, and its own bound buttons.

### Schedules and periods

A **schedule** is a named, priority-ordered list of **periods** (Morning,
Day, Afternoon, Evening, Night by default, but you can rename, reorder, add,
or remove freely). You can have more than one schedule — most homes only need
one shared indoor schedule, but something like outdoor lighting usually wants
its own simple window instead of being squeezed into the same
morning/day/afternoon/evening/night shape. Manage schedules from **⚙
Settings → Schedules**; pick which schedule a room follows when you add the
room (skipped if you only have one).

Each period is built from a **condition list**: pick a condition type from a
menu to add it, and freely combine as many as you want using two levels of
logic — **AND** within a group (all must be true), **OR** between groups (any
group being fully true is enough). The available condition types:

- **Time** — before/after a fixed clock time.
- **Sun position** — before/after a solar event (dawn, sunrise, solar noon,
  sunset, dusk), with an optional +/- minute offset, and optional
  earliest/latest clamps so a solar event never resolves before or after a
  fixed clock time on any given day (useful for keeping "evening" sane
  through both midsummer and midwinter).
- **Numeric sensor** — above/below/equals a threshold against any sensor's
  state (this is how you'd express "dark outside" using a lux sensor, or any
  other numeric condition).
- **Sensor state** — is/is not a specific state value, against any entity —
  works with a `binary_sensor`, `input_boolean`, or any other entity in any
  language, since you type the exact state value yourself.
- **Weekday/weekend** and **Home/away** — reuse whatever you've configured
  under Weekday/weekend and Home/away (see below) directly inside a period's
  own conditions, if you want a period to only ever apply on weekdays, say.

Once you've built each period's condition groups, order matters: **the first
period in the list whose conditions are currently true wins** — so put more
specific/overriding periods above more general ones (a manual "goodnight"
override above the normal evening/night split, for example).

Every schedule also has its own **default transition time** per period (how
long a light fades to its new value), overridable per device/period if one
light should transition differently than the rest.

### How a device picks its behavior

For every period, a device can have up to four behavior variants — each with
its own on/off, brightness, and color temperature — checked in this order,
top wins:

1. Any of this **room's own custom conditions** that's currently true (see
   below), in that room's priority order.
2. This **period's own "Away" override**, if you've turned it on for this
   period specifically.
3. The **device-wide away default** (see next paragraph) — used only when
   this period doesn't have its own Away override turned on.
4. This **period's own "Weekend" override**, if you've turned it on.
5. The plain **Default** behavior for this period.

The **device-wide away default** sits next to a device's period tabs (not
inside any one of them) and defines one on/off/brightness/color value that
applies while you're away, across *every* period at once — so you don't have
to configure "off while away" five separate times unless one specific period
genuinely needs different away behavior, in which case that period's own
Away override (item 2 above) simply takes priority over it.

### Control mode: schedule, motion, or button

For every device, every period, you choose **how it's controlled** — this
doesn't change the behavior values themselves, just whether the schedule (or
motion) is allowed to apply them automatically:

- **Schedule** — the normal case: RoomFlow keeps this device in sync with
  whichever behavior variant currently applies, automatically, whenever
  anything relevant changes.
- **Motion sensor** — this device is left alone by the ordinary schedule and
  instead driven by a motion-sensor definition you pick right there (see
  below), with independent toggles for whether it should turn **on** when
  motion starts and/or turn **off** when motion stops — so a device can react
  to only one side if that's what you want.
- **Button / manual only** — the plain per-period behavior is never applied
  automatically; this device only changes when you press a bound physical
  button (or explicitly hit "Test now"). Away/Weekend/custom-condition
  overrides still apply automatically if you've turned them on for this
  period — only the plain Default value is left for manual control. This is
  the natural choice for a device you always want to control by hand, but
  where you still want the *brightness it comes on to* to depend on time of
  day — see [Buttons](#buttons) below, a button press resolves the real
  current behavior, not a blind on/off.

### Motion sensors

Motion sensors live in their own **Motion sensors** tab as a shared,
reusable library, independent of any one room. Add a definition, give it a
name, and add one or more triggers to it:

- **Motion sensor** — a `binary_sensor` (or similar) that's "on" when
  motion's detected.
- **Threshold** — any numeric sensor above a value you set (e.g. humidity, so
  a bathroom fan/light can react to a shower instead of only PIR motion).

A definition is "active" whenever *any* of its triggers is true. Set its
off-delay (how long after the last trigger clears before turning off) and,
optionally, a **dim-as-a-warning** stage — dim to a chosen brightness first,
wait a few more minutes, and only then turn off fully; motion returning
during either wait restores the device to its normal current behavior
instead.

Then, per device and period, set control mode to **Motion sensor** and pick
which definition it should react to. The same definition can be used by as
many devices as you like, in as many rooms as you like — build the trigger
once (e.g. "Bathroom PIR + humidity") and point every light that should react
to it at that one definition, rather than redefining the same sensors
repeatedly.

### Buttons

Like motion sensors, buttons live in their own **Buttons** tab as a shared
library of reusable **triggers**, separate from *what* they do — you attach
a trigger to an action from the room or device it should control, and the
same trigger can be attached in more than one place at once (e.g. one
physical channel both dimming a specific light *and* toggling a whole room,
from two separate attachments to the same trigger).

Adding a trigger, you choose between two kinds:

- **Entity** — the common case: point it at any entity that changes state on
  a press (an `event.*` entity from Zigbee2MQTT/ZHA, a plain `binary_sensor`,
  or a derived "click status" sensor if your integration exposes one).
- **Device event** — for hardware that fires a raw Home Assistant event with
  **no backing entity at all** (Shelly gen1 relays/inputs are the built-in
  example: they fire a `shelly.click` event, not any entity state change).
  Pick a device profile (Shelly gen1 is built in) and fill in the fields that
  identify your specific physical device/channel — see
  [BUTTON_PROFILES.md](BUTTON_PROFILES.md) for exactly how to find those
  values for your hardware, and how to contribute a profile for hardware
  that isn't built in yet.

Either kind can optionally be scoped to a **click type** — any press
(default), single, double, or long — so one physical button can back
several different triggers that each do something different depending on
how it's pressed, if your hardware reports that distinction.

Got a trigger working and want to reuse the same physical setup elsewhere
(another install, or just documenting it for yourself)? Use the **copy**
icon on a trigger to copy it as a small text snippet, and **paste trigger**
to recreate it from that snippet.

**Attaching** a trigger:

- **On a device** (in that device's own card, below its period tabs) —
  Toggle, Turn off, or (for lights) step brightness Up/Down by a fixed
  amount per press. A toggle/on press resolves the device's real
  currently-active behavior (right brightness/color for the time of day,
  including away/weekend if relevant) — not a blind on, so a button-only
  device still dims correctly through the day.
- **On a room** (that room's own tab, "Room buttons") — Toggle or turn off
  every device in the room together, run the room's scheduled behavior right
  now, or force the room into a specific period regardless of the actual
  time (handy for a walkthrough/demo, or a "party mode" override).

If a physical button doesn't seem to do anything, check the **Button
activity** log at the bottom of the Buttons tab before assuming it's
misconfigured — see [Diagnosing a button that "does nothing"](#diagnosing-a-button-that-does-nothing)
below.

### Custom conditions per room

Beyond the house-wide Weekend/Away overrides, each room can define its own
ordered list of conditions from that room's own tab — a name, an entity, and
the state that means it's active. These are checked *first*, above
Away/Weekend/Default (see [How a device picks its behavior](#how-a-device-picks-its-behavior)),
in the room's own priority order. Each condition gets its own per-period
behavior per device, exactly like Weekend/Away — useful for anything specific
to that room rather than the whole house (a particular person's presence, a
manual "cleaning mode" toggle, a TV/media-player state, and so on).

### Weekday/weekend and home/away

Configured once, globally, from **⚙ Settings**, and used everywhere
Weekend/Away overrides and period conditions reference them:

- **Weekday/weekend** — "not used" (always weekday), an existing sensor (any
  polarity, any language — you tell RoomFlow which value means weekend), or
  a built-in weekday checklist (pick which days count as weekend).
- **Home/away** — "not used" (always home), an existing sensor, or a
  built-in option: pick one or more `person.*` entities, and it's "away"
  only once *all* of them report away.

### A manual change sticks

If you turn a light on or off yourself (app, voice, or a bound button) while
it's normally schedule-controlled, RoomFlow doesn't fight you for it: an
ambient recheck only reapplies a device when the schedule's *own* target
actually changes (a new period starts, a condition flips, weekend/away
state changes) — not on every routine tick. Your manual change sticks until
that next real change, instead of silently reverting within a minute.
Explicit actions — "Test now"/"Test all", or a button's "run now"/"force
period" — always apply regardless, since those are explicit requests to
reassert the schedule.

### Overview tab and activity logs

The **Overview** tab shows, at a glance: every room's current period and a
row of live status icons for its devices, plus two logs — every device
change RoomFlow itself applied (which room/device, what it did, which
period, and *why* — schedule, motion, a specific button, etc.) and every
time a schedule's resolved period actually changed. The **Buttons** tab has
its own dedicated log, described next.

#### Diagnosing a button that "does nothing"

The **Button activity** log (Buttons tab) records *every* recognized press
of a bound trigger, whether or not it ended up doing anything — so you can
tell exactly where it's failing:

- **Nothing appears in the log at all**, even after several presses → Home
  Assistant isn't seeing the press as the entity/event you configured. For
  raw hardware events (Shelly and similar), double-check the device
  profile's fields via Developer Tools → Events against what your physical
  device actually sends — see [BUTTON_PROFILES.md](BUTTON_PROFILES.md).
- **"Ignored (click type didn't match)"** → detection works, but your
  chosen click type (single/double/long) doesn't match what this press
  actually reported — try "Any press" to confirm, then narrow it down.
- **"Not attached to anything"** → detection and click type are both fine;
  this trigger just isn't attached to any device or room action yet — add
  one from a device's or room's own tab.
- **"Ran"** → everything worked; if the device still didn't visibly change,
  the problem is downstream of RoomFlow (the light entity itself, not the
  button).

### Settings tab

Everything that isn't specific to one room, button, or motion definition:
Weekday/weekend and Home/away sourcing (above), managing schedules, and
RoomFlow's own device name/Area (used to group its own Day type/Home state
sensors — see below).

### Entities RoomFlow creates

All ordinary Home Assistant entities, usable in your own automations and
dashboards like any other:

- **Day type** and **Home state** sensors, grouped under RoomFlow's own
  device (named/placed via Settings).
- Per room, a **status sensor** (grouped under that room's own Area) showing
  the winning custom condition, "Away"/"Weekend", or the current period name.
- Per schedule, a **Current period** sensor plus one `binary_sensor` per
  period ("on" exactly when that period is the currently resolved one) —
  scoped per schedule so two schedules can each have a period called
  "morning" without colliding.

### Diagnostics

**Settings → Devices & services → RoomFlow → Download diagnostics** gives you
a structural snapshot (counts, condition/trigger types, timeouts, precedence
settings) for bug reports, without including your specific device
`entity_id`s, custom-condition targets, or button-trigger entities/event
data.

## Contributing

Issues and pull requests are welcome. This is a relatively young project —
expect some rough edges, especially around more advanced condition
combinations and additional device types (climate, media_player, etc. are
natural next steps). If you've confirmed a raw-event button profile (e.g.
Shelly gen1) against your own hardware, or want to add a new one, see
[BUTTON_PROFILES.md](BUTTON_PROFILES.md).

## Supported languages

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl) —
this README, the card's own UI, and the config flow all follow the same 8
languages. The card picks its language from Home Assistant's language
setting automatically.

## License

MIT — see [LICENSE](LICENSE).
