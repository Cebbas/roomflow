# Button device profiles

RoomFlow's button triggers can bind directly to a **raw Home Assistant
event**, for hardware that doesn't expose any entity at all (the "Device
event" option in the card's Buttons tab, alongside the existing "Entity"
option). A *device profile* (`EVENT_DEVICE_PROFILES` in
`custom_components/roomflow/const.py`) tells RoomFlow which event type to
listen for, which fields in the event data identify one specific physical
device/channel, and which field carries the click type (single/double/
long).

This file documents the built-in profiles and is where reports of tested
hardware live, so other users can trust a profile works with their exact
device before trying it themselves.

## Built-in profiles

### Shelly (gen1) button — `shelly_gen1_click`

Gen1 Shelly relays/inputs fire a `shelly.click` event with no backing
entity at all:

```yaml
event_type: shelly.click
event_data:
  device_id: <Home Assistant device registry ID - not the Shelly's own MQTT/cloud ID>
  channel: 1          # 2, 3... for a multi-channel/multi-input device
  click_type: single  # or "double" / "long"
```

To find your own `device_id`/`channel`: Home Assistant → Developer Tools
→ Events → listen for `shelly.click` → press the physical button once →
read the values off the event shown, then enter them in the card's "Add
button trigger" form under "Device event".

**Tested against:**

| Model | Firmware | Channels used | Notes | Reported by |
|---|---|---|---|---|
| _add yours here_ | | | | |

If you've confirmed this profile works with your Shelly device, please
open a PR adding a row above (model, firmware version, which channel(s)
you used, any quirks worth knowing) - or open an issue and a maintainer
will add it for you.

## Adding a new device profile

Every entry in `EVENT_DEVICE_PROFILES` (`custom_components/roomflow/
const.py`) is a small dict:

```python
"my_vendor_click": {
    "event_type": "my_vendor.click",           # the raw HA bus event type this device fires
    "match_fields": ["device_id", "channel"],  # event.data keys used to pick one physical device/channel
    "click_type_field": "click_type",          # event.data key whose value is compared against single/double/long
},
```

- `match_fields` become one text input each in the card's "Device event"
  form (Channel renders as a number input, everything else as text) - a
  field left blank when adding a trigger means "match any value", though
  the UI form requires all of them filled in to avoid accidentally
  creating an overly-broad trigger by mistake.
- `click_type_field`'s value is compared against the trigger's own
  click_type ("single"/"double"/"long"/"any") the same way an entity-based
  trigger's state is - a case-insensitive substring match, so the vendor's
  own vocabulary ("single"/"1_single"/"single_push"/etc.) doesn't need to
  match RoomFlow's exactly.

New profiles also need a display name string (`event_profile_<id>`) added
to each of the 8 language blocks in `custom_components/roomflow/www/
roomflow-card.js`, and the same `id`/`match_fields`/`event_type` mirrored
into that file's `EVENT_DEVICE_PROFILES` constant (used client-side only
to render the right inputs - the actual matching stays backend-side).

## Sharing a configured trigger

Any button trigger (entity- or device-event-based) can be copied from the
card's Buttons tab (the copy icon on each trigger row) as a small JSON
snippet, and pasted back in via "Paste trigger" on another RoomFlow
install - handy for sharing a working Shelly/Zigbee button setup with
someone else who has the same physical hardware, without them having to
find their own `device_id`/`channel` from scratch if they can adapt yours.
