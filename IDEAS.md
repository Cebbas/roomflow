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

## Continuous hold-to-dim button action

Button bindings (`_handle_button_press` in `__init__.py`) only support
discrete, one-shot actions (`toggle`, `off`, `apply_now`, `force_period`)
triggered by a single state-change event. There's no way to bind a
press-and-hold gesture to continuous brightness ramping (repeatedly
stepping `brightness_step` up/down at a fixed interval for as long as the
button is held, reversing direction near the brightness extremes) - a
common wall-switch pattern for dimmable lights that today has to be built
as a bespoke automation outside RoomFlow entirely.

Possible approach: a new action type (e.g. `hold_dim`) bound to a
press/hold-capable event entity rather than a plain state-change trigger,
starting a repeating timer (e.g. `async_track_time_interval` at ~50ms)
that calls `light.turn_on` with a small `brightness_step_pct` on the
target device until a corresponding release event fires, alternating
direction each time the hold starts based on the device's current
brightness. Can reuse a button binding's existing `target_entity_id`
field (added for per-device toggle/off targeting) to pick which device to
dim, since dimming a whole room in lockstep is rarely what's wanted - but
is still a meaningfully different trigger model than every other button
action today.

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

Each type also needs a plain "off" alternative per period, not just a
target-value state - mirroring how light/switch already toggle between a
target state and `state: "off"` (`target.state = field.checked ? "on" :
"off"`, handled in the card's field-change handler and applied via
`light.turn_off`/`switch.turn_off` in `_apply_behavior`). E.g. a climate
device's period behavior should be choosable as either a target
temperature/hvac_mode *or* fully off (`hvac_mode: "off"`), and same for
media_player (a target source/volume *or* `media_player.turn_off`) -
not every period necessarily wants the device actively doing something.

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

## Explicit pause/resume for a room or device

`_apply_single_device` in `__init__.py` now skips an ambient re-apply
(`respect_manual_override=True`, only set by `apply_current_period`)
whenever the resolved behavior's signature (`_behavior_signature`) hasn't
changed since the last time RoomFlow itself set it - so a manual change
(app, voice, physical button/toggle) is left alone until the *schedule's
own target* actually moves, instead of being stomped on the next tick.
That passively covers the common "I dimmed a light and it snapped back a
minute later" frustration without needing any explicit toggle.

What's still missing: there's no way to deliberately take a room/device
out of RoomFlow's control *even across a real period change* - e.g.
"leave the kitchen alone for the next hour, I'm doing something" should
survive the schedule's target actually moving, which today's passive
signature-diff does not (a genuine period/condition/away-state change
still re-asserts control immediately, by design). Possible approach: a
per-room or per-device explicit "pause" state (toggle from the card, or
exposed as a service for automations/voice assistants) checked in
`_apply_to_rooms` ahead of the signature-diff check, skipping that room/
device unconditionally until explicitly resumed or a fixed expiry (end of
day, next period change, or a chosen duration) - a deliberate override on
top of the automatic one, not a replacement for it.

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

## Walk-through test button (cycle every period on real devices)

Today's per-room "Test now" button (`test_now` in the card, `ws_apply_now`/
`apply_room` in websocket_api.py/`__init__.py`) only re-applies whatever
period is currently active - it's a "run scheduled behavior now" action,
not a way to actually *see* every period's behavior on the real devices.
Same for the "Force a specific period" button action (`force_period`,
`_apply_to_rooms(..., forced_period=...)` in `__init__.py`) - it forces one
period and stays there, not a walkthrough. Unlike the read-only simulate
idea above, the goal here is to actually see it happen on the physical
devices, one period at a time.

Possible approach: a second room-level button (next to "Test now") that
steps through every configured period in order, holding each one for a
short fixed duration (e.g. 10s) via `_apply_to_rooms([room],
forced_period=period.id)`, then moving to the next - and clearly surfaces
which period is currently being demoed (e.g. a highlighted/pulsing period
label on the room card, or a toast), so it's obvious which lighting
belongs to which period while watching. Needs a new websocket command
(e.g. `roomflow/preview_day`) that runs the loop server-side with
`async_call_later`/`async_track_point_in_time` and pushes the current
period back to the card (event or subscribed state) rather than the card
itself trying to time it client-side. Should restore the room's real
current-period behavior when the walkthrough finishes or is cancelled
early.

## Finish moving the card's UI to native HA components

v0.0.7 switched form fields to native `<ha-textfield>`/`<ha-switch>` (see
the `textField`/`switchEl` helpers and the `.rf-root ha-textfield`/
`ha-switch` CSS rules in `roomflow-card.js`), but that only covered
text/number inputs and toggles. Buttons (`class="rf-btn"`), dropdowns
(plain `<select>`), and the period tabs (`rf-tab`) are still hand-rolled
HTML elements styled with the card's own CSS instead of Home Assistant's
native components (`ha-button`/`mwc-button`, `ha-icon-button`, `ha-select`,
`ha-tab`/`mwc-tab-bar` or similar) - meaning the card mostly matches HA's
look today, but drifts from it whenever HA's own theme/design system
changes (spacing, ripple effects, color tokens), and won't automatically
pick up an HA visual refresh the way a card built entirely on native
components would.

Possible approach: continue the v0.0.7 work by replacing the remaining
`rf-btn`/`<select>`/`rf-tab` elements with their `ha-*` equivalents one
category at a time (buttons first, then selects, then tabs), the same way
switches/textfields were done - checking `customElements.get(...)` with a
plain-HTML fallback where a given HA frontend version might not have the
element registered, and trimming the corresponding hand-written CSS rules
once each category is fully native.

## Standalone schedules for individual devices (e.g. outdoor lighting)

Periods are configured once, globally (`CONF_PERIODS` in `const.py`, read
via `infer_periods` and shared by every room through `_apply_to_rooms` in
`__init__.py`) - every room picks behavior against the *same*
morning/day/afternoon/evening/night list. That fits indoor rooms that
broadly follow the same day well, but not something like outdoor lighting,
which usually just needs its own simple on/off window (e.g. "on from
sunset to 23:00", or "on from dusk to dawn") unrelated to the indoor
period breakdown. Today the only way to express that is either reusing
existing periods loosely, or adding a new global period just for one
device - which then also shows up as an option for every other room,
cluttering everyone else's period list for something only relevant to one
device.

Possible approach: let a device (or a whole room) opt out of the shared
period list and instead define its own simple standalone on/off
schedule - one or more sun/clock/sensor-driven windows, similar in shape
to a period's existing sources, but scoped to that single device/room
rather than added to the global list. Could double as a plain exposed
binary_sensor (like today's per-period ones) so it's also directly usable
in other automations, not just within RoomFlow.

## Entity health as a real notification, not just a log warning

When a bound entity's service call fails (`_apply_single_device` in
`__init__.py`, `except Exception as err: _LOGGER.warning("RoomFlow: could
not apply behavior to %s: %s", ...)`), and similarly for the turn-off/
toggle/motion-warning call sites that follow the same pattern, the only
trace is a warning line in Home Assistant's log - nothing surfaces in the
UI. A device that's been unavailable or misconfigured for weeks (e.g. an
entity_id that no longer exists after a Zigbee re-pair) can go unnoticed
indefinitely unless someone happens to be reading the log.

Possible approach: register these as Home Assistant "repair" issues
(`homeassistant.helpers.issue_registry.async_create_issue`) keyed by
room/device, created on first failure and cleared automatically once a
call for that device succeeds again - so a broken binding shows up in HA's
own Settings > System > Repairs list instead of only the log, without
RoomFlow needing its own notification/alerting system.

## Linked/synced rooms (shared open-plan spaces)

Every room in the config store (`cfg.get("rooms", [])`, each with its own
`devices`/`motion`/period behavior) is independent - there's no way to say
two rooms are really one physical space, e.g. an open-plan kitchen +
living room where you want both to always be in the same period and react
to either room's motion sensors together, rather than configuring the
same schedule twice and hoping they stay in sync.

Possible approach: an optional "linked room" reference so one room follows
another's resolved period/motion-active state instead of computing its
own from its own custom conditions and triggers (while still keeping its
own device list, since the two spaces likely have different lights) -
checked in `_apply_to_rooms`/`_handle_motion_change` by resolving the
period/motion state from the room it's linked to before applying behavior
to its own devices.

## Continuous adaptive curve (sun-elevation-based), not just discrete periods

Periods are always a fixed list of named blocks (`CONF_PERIODS`, resolved
by `infer_periods`) - a device's target brightness/color_temp jumps (or,
per the scheduled-ramping idea above, ramps over a fixed window) between
whatever two adjacent periods define, not a smooth curve driven directly
by where the sun actually is. That's a different, more continuous
alternative to periods entirely, closer to how the popular Adaptive
Lighting integration works: brightness/color temperature computed straight
from sun elevation at every moment, with no period boundaries at all -
useful for a room where someone doesn't want to think in named periods,
just "warmer and dimmer as the sun goes down, brighter and cooler at
midday."

Possible approach: an opt-in per-room (or per-device) mode that replaces
period-based resolution with a formula driven by `sun.sun`'s elevation
attribute, interpolating between configured min/max brightness and
color_temp - likely sharing the same recompute/timer-tick machinery the
scheduled-ramping idea would need, but replacing "which period" with "what
elevation" as the input.

## Per-user permissions on the card

Every websocket command RoomFlow registers (`ws_get_config`,
`ws_save_config`, `ws_apply_now`, `ws_apply_room`, in websocket_api.py)
is reachable by any authenticated Home Assistant user - there's no
distinction today between someone allowed to reconfigure rooms/periods/
devices and someone who should only get the quick actions (the card's
"Test now" button, or a dashboard tile). In a multi-person household,
anyone with card access can currently rewrite anyone else's room
config.

Possible approach: gate `ws_save_config` (and the config-editing parts of
the card UI) behind `connection.user.is_admin` or a configurable allowlist,
while leaving `ws_apply_now`/`ws_apply_room` open to any user - mirroring
how Home Assistant itself treats admin-only settings vs. general
dashboard interaction.

## Undo last automatic change

There's no quick way to revert just the *last* thing RoomFlow did to a
room - e.g. a period boundary was crossed at an awkward moment, or a
custom condition briefly flickered and changed behavior, and the fix
today is only to wait for the next recompute or manually readjust the
device by hand. This is a lighter-weight ask than the manual override/
pause idea above (which is about taking a room out of RoomFlow's control
for a while) - just a single-step "put it back to what it was a moment
ago" action.

Possible approach: keep a small per-room record of the device states
immediately before the last `_apply_to_rooms` call actually changed
anything, and add an "Undo" button (card action + maybe a bound-button
action) that replays those prior states via the same `light`/`switch`
services, clearing the record once used so it can't be replayed twice.

## Native midnight-spanning time condition

A period's `time` condition (`CONDITION_TYPE_TIME` in `const.py`, evaluated
by `_condition_ok` in `__init__.py`) only supports a single `after`/`before`
boundary compared against the current time-of-day - there's no condition
that natively expresses a range like "22:00 to 06:00". Today the only way
to cover a window that crosses midnight is two separate OR'd condition
groups (one `after 22:00`, one `before 06:00`), which is exactly the
pattern `_default_condition_groups` already generates for the last default
period, and works correctly, but has to be built by hand for any
custom period a user adds (e.g. a "Night" period covering 22:00-06:00).

Possible approach: add a `between` operator (or a dedicated condition type)
that takes two clock values and, when the "start" is later than the "end",
treats the range as wrapping past midnight (`now >= start or now < end`)
instead of requiring the user to construct two OR'd groups manually. Purely
a UX simplification over what two condition groups already accomplish -
not a new capability.

## Time-window restriction on a motion/threshold trigger

A trigger in `room.motion.triggers` (`_is_trigger_active` in `__init__.py`)
only ever checks the sensor's own state - a `motion` trigger fires
whenever the entity reports "on", a `threshold_above` trigger whenever the
value clears the threshold, with no notion of *when in the day* that
should count. There's no way to say "only let this sensor activate the
room between 22:00 and 06:00" (e.g. a driveway/hallway sensor that should
only affect lighting at night, ignored the rest of the day) without an
external automation that separately enables/disables the sensor or the
whole room.

This is a different scope than the per-device per-period motion idea
above (which decides whether a *device* reacts once the room is already
counted as active) - this one is about restricting when the *trigger
itself* is allowed to count as active in the first place, as a plain
clock-time window rather than tied to the named period list.

Possible approach: add optional `active_from`/`active_until` clock-time
fields to a trigger, checked in `_is_trigger_active` alongside the
existing state/threshold check (using the same time-of-day comparison,
handling the overnight-wrap case like 22:00-06:00, that period boundaries
already need elsewhere) - so a trigger outside its window is treated as
inactive regardless of the sensor's actual state. The card's trigger row
would need two optional time inputs next to the existing sensor/threshold
fields.

## Restore-on-motion-return for motion_off-only devices

`_handle_motion_change` in `__init__.py` only cancels a device's pending
motion-off timer and re-applies its "on" behavior
(`_cancel_motion_timer`/`_apply_motion_device_on`) for devices in
`_motion_on_devices` (control mode "motion" with `motion_on` enabled) -
when motion becomes active again mid-countdown. A device configured with
`motion_on` off but `motion_off` on (e.g. turned on by a bound button,
then left to the room's motion trigger purely to dim-and-turn-off after
inactivity - the intended replacement for the legacy bathroom/toilet
ceiling-light pattern of "button turns it on, motion governs the
dim/off/restore sequence") never gets that cancel-and-restore: if motion
returns while its off-timer/dim-warning is counting down, the device
still turns off on schedule instead of snapping back to full brightness
like the old hand-built automation did.

Possible approach: in `_handle_motion_change`'s "motion became active"
branch, also check `_motion_off_devices` (not just `_motion_on_devices`)
for any device with a live pending timer (`hass.data[DOMAIN]
["motion_off_timers"]`) and cancel + restore it to the current period's
resolved behavior via `_apply_motion_device_on`, even though `motion_on`
itself is off - the restore is a reaction to an in-progress countdown
being interrupted, not a fresh "motion turned this on" event, so it
should be gated on "has a pending timer" rather than on `motion_on`.
