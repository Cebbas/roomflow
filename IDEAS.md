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
