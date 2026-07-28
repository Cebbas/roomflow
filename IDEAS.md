# Ideas / deferred features

Things identified during development that aren't built yet, kept here so
they don't get lost. Not a roadmap or a promise — just notes for later.

## Threshold-based (numeric) room custom conditions

Room-level custom conditions (`room.custom_conditions` in the config store,
resolved by `_active_room_conditions` in `custom_components/roomflow/
__init__.py`, edited via `_renderCustomConditionsBox` in `www/
roomflow-card.js`) currently only support **exact string equality**:
`entity_id`'s state must equal `state` exactly.

This can't express a numeric/threshold condition — e.g. replicating a
"dark outside" automation based on `sensor.illuminance < 500` isn't
possible today; it only works for equality-style sensors (booleans,
enums, scene names).

Possible approach: extend each condition with an optional comparison
operator (`equals` / `above` / `below`, mirroring the existing motion
trigger's `type: threshold_above` concept in `room.motion.triggers`), and
have `_active_room_conditions` branch on it the same way `_is_trigger_active`
already does for motion triggers. The card's condition-row UI would need an
operator `<select>` alongside the existing state-value `<input>`.

## Button click-type distinction (single / double / long-press)

RoomFlow's button system (`room` bindings in `buttons`, handled by
`_handle_button_press` in `__init__.py`) binds one entity to one fixed
action. It has no concept of click type - a Zigbee/Shelly button that
reports single vs. double vs. long-press (or a press/release `event.*`
entity with hold-duration logic) can't trigger different actions per click
type from a single binding today.

Before building anything here: many real-world setups (including the one
that prompted this note) already expose a *separate* entity/template
sensor per click type (e.g. a "click status" template sensor per channel).
If so, those can likely just be bound as separate RoomFlow buttons already,
with no RoomFlow change needed - worth confirming against a real setup
before adding native click-type support, to avoid building something
already achievable.

If native support turns out to be needed: extend a button binding with an
optional `click_type` field (`single`/`double`/`long`) checked against the
triggering entity's new-state (or `event_type` attribute for `event.*`
entities) before running the action, alongside the existing `entity_id` +
`action` fields.

## Floors

Rooms aren't grouped under anything larger today - there's no notion of a
floor. Adding floors would let the card organize/filter rooms by floor, and
would be a prerequisite for floor-level scenes (see below) and any future
floor-level settings.

## Scenes (house / floor / room level)

No concept of a reusable "scene" exists yet - only per-period device
behavior. Add scenes that can be triggered at three scopes: the whole
house, a single floor (once floors exist, see above), or an individual
room. A scene would capture a target state per device (similar to what a
period already defines) and be triggerable on demand (button binding, card
action, or exposed as a service) independent of the current time-of-day
period.

## Holidays / specific dates and seasons

Today's overrides are limited to away/weekend and per-room custom
conditions driven by entity state - there's no notion of a *date-based*
override, e.g. different behavior on public holidays (Christmas Eve,
Midsummer, etc.), a custom date range (holiday/vacation weeks), or a
recurring season of the year (summer vs. winter lighting).

Possible approach: a new override tier (checked in precedence alongside/
above weekend, similar to how away/weekend/default already stack) driven
by either a `calendar.*` entity (Home Assistant's built-in calendar
integrations, including holiday calendars, already expose "is today an
event" as entity state) or a built-in date-range/recurring-date picker in
the card, so it works without requiring a separate calendar integration.
Each period's behavior would need its own holiday variant, mirroring how
weekend/away overrides are defined per device/period today.

## More device types (climate, media_player, cover)

RoomFlow only controls `light` and `switch` entities today - `_device_domain`
in `__init__.py` hardcodes the choice (`"light" if device.get("type") ==
DEVICE_TYPE_LIGHT else "switch"`), and `_apply_behavior` only knows how to
call `light.turn_on`/`light.turn_off` or `switch.turn_on`/`switch.turn_off`.
The README's Contributing section already flags climate and media_player as
natural next steps, but no concrete plan exists yet.

Each new type needs its own `DEVICE_TYPE_*` constant, its own per-period
behavior shape (climate: target temperature/hvac_mode instead of
brightness/color_temp; cover: target position instead of on/off; fan: speed
percentage), and card UI for editing that shape per device/period. Motion
triggers, buttons, and transitions would need to decide which of these make
sense per device type (a transition time is meaningful for a light or cover,
less so for a climate mode switch).

## Presence simulation while away

Today's away override (see weekend/away overrides above) sets one fixed
behavior for the whole "away" duration. A common complementary use case:
while home/away reports "away", randomize on/off timing for selected lights
(varying by a few minutes each day) to make the house look occupied for
security, instead of a static on/off state or none at all.

Possible approach: an optional per-device "presence simulation" flag,
usable only when an away override is defined, that replaces the fixed
away behavior with a randomized on/off schedule generated within a
configurable window (e.g. "on sometime between 19:00-19:30, off sometime
between 22:30-23:15"), re-rolled once a day.

## Manual override / pause automation per room or device

There's no way to temporarily take a room or device out of RoomFlow's
control. If someone manually dims a light to something specific, the next
period change or triggered recompute (`SIGNAL_RECOMPUTE`) overwrites it -
a common frustration in "smart lighting" setups where automation fights
manual adjustments.

Possible approach: a per-room or per-device "pause" state (toggle from the
card, or exposed as a service for automations/voice assistants) that skips
that room/device in `_apply_to_rooms` until explicitly resumed, or until a
fixed expiry (end of day, next period change, or a chosen duration).

## Scheduled ramping between periods

Transition times today are just the `transition` parameter passed straight
through to `light.turn_on` (`_apply_behavior` in `__init__.py`) - a smooth
fade at the moment a period boundary is crossed, not a ramp that happens
*before* the boundary. There's no way to, say, have brightness/color
temperature gradually drift from the morning target to the day target over
the 30 minutes leading up to the switch, the way a sunrise/sunset alarm
clock does.

Possible approach: an optional per-period "ramp duration" that, instead of
snapping to the next period's behavior at its boundary, interpolates
brightness/color_temp between the current and next period's target values
over that window, recomputing on a timer tick rather than only on the
period-change event.

## Config export / import

There's no way to back up or move a RoomFlow configuration other than the
existing diagnostics download (which intentionally strips entity_ids) or
manually recreating every room/device/period/button/condition through the
card. Useful both for backups and for migrating to a new Home Assistant
instance.

Possible approach: a "download config" / "upload config" pair in the
card's Settings tab that reads/writes the same config-store shape
diagnostics already partially exposes, but with entity_ids intact -
essentially a raw dump/restore of the integration's config entry data.

## Room templates / duplicate room

Setting up several similar rooms (e.g. multiple bedrooms with the same
period/device layout) means rebuilding the whole structure - periods,
devices, transitions, buttons, motion triggers - from scratch each time.

Possible approach: a "duplicate room" action in the card that copies an
existing room's full configuration (devices, per-period behavior,
overrides, buttons, motion triggers) into a new room with a new name,
leaving entity_ids blank/unset for the user to fill in per device rather
than pointing at the same physical entities.

## Expose actions as Home Assistant services

`apply_now` and `force_period` (the same two actions a physical button can
be bound to, handled in `_handle_button_press` in `__init__.py`) are only
reachable via a bound button entity or the card's own websocket commands
(`ws_apply_now`/`ws_apply_room` in `websocket_api.py`) - there's no
`roomflow.*` service registered, so scripts, automations, and Home
Assistant's Assist voice pipeline can't trigger "run room X's scheduled
behavior now" or "force room X into period Y" directly.

Possible approach: register these as real services (`roomflow.apply_now`,
`roomflow.force_period`, and similarly a `roomflow.pause`/`roomflow.resume`
pair once the manual-override idea above exists) via
`hass.services.async_register`, targeting a room by area or entity, so
they compose with the rest of Home Assistant instead of being locked
inside button bindings and the card.

## Preview / simulate resolved behavior

There's no way to see what RoomFlow *would* do without actually waiting
for or forcing a real state change - e.g. "what would the living room do
at 22:00 on a weekend while away?" has to be checked by manually adjusting
the underlying sensors/clock, or forcing the period and losing the current
real state. Useful for verifying a config change in a room with many
conditions before it actually matters.

Possible approach: a read-only "simulate" panel in the card that takes a
chosen time, day-type, home-state, and active custom conditions, runs them
through the same resolution logic `_apply_to_rooms` already uses to pick a
behavior per device, and displays the result - without calling any
`light`/`switch` service.

## Decision / audit log

Today "a failing device logs a warning instead of blocking the rest of
the room" (per the README), but there's no log of RoomFlow's *successful*
decisions either - which override tier won (away/weekend/default/custom
condition) and why, for a given room at a given time. When behavior looks
wrong, there's currently no way to answer "why did it do that" other than
re-deriving it by hand from the config.

Possible approach: an in-memory ring buffer (surfaced in the card, e.g. a
"History" tab per room) recording each resolved decision - timestamp,
room, period, which override tier applied, and which condition/source
triggered it - independent of Home Assistant's own logbook/history, which
only shows the resulting entity state changes, not RoomFlow's reasoning.
