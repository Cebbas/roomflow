# Migration notes

Room-by-room notes from migrating the legacy YAML packages (`filler från
HA/`) into RoomFlow - decisions made, things intentionally left out, and
oddities found in the old config along the way. Not a roadmap (see
`IDEAS.md` for that) - this is a log to check back against once a room is
actually live, and a place to point at when something behaves differently
than the old automations did.

## Cross-room bug found and fixed: button-mode periods with an "off" default (2026-09-11)

Reported: pressing the physical button couldn't turn Nadines rum's
takbelysning on. Root cause wasn't the button trigger (it fired
correctly every time, confirmed via RoomFlow's own button activity log)
- it was how every "button" control-mode period had been set up. A
period with control mode "button" is left alone by ambient schedule
ticks, so it seemed safe to leave its "default" tier at a placeholder
`off` value for periods the source never actually defined a behavior for
(mirroring the old YAML's "no scene entry = untouched" pattern). But
`_resolve_manual_on_behavior` in `__init__.py` deliberately ignores
control mode and always reads the real default tier - by design, so a
manual button press can reach the device's actual configured brightness/
color instead of a bare on/off (see its docstring). An `off` placeholder
there means a button press meant to turn the light *on* instead resolves
to - and applies - `off`, silently. Confirmed via the button log: every
press logged `outcome: ran` (the trigger fired, the attachment executed)
even though the light never turned on - "ran" only means the button
mechanism worked, not that the resolved behavior was correct.

Affected 6 devices across every room migrated tonight, 20 period
instances total - **including kök's `takbelysning`/`bordslampa`, which
already had this exact shape before this session touched them**, so it
wasn't introduced by tonight's work alone, just repeated by following the
same pattern: `kok_takbelysning` (morning/afternoon/day/evening),
`kok_bordslampa` (morning/afternoon/day/evening), `vardagsrum_taklampa`
(morning/afternoon/evening), `entre_takbelysning` (morning/afternoon/
evening), `naomis_rum_takbelysning` (morning/afternoon/evening),
`nadines_rum_takbelysning` (morning/afternoon/evening).

Fixed by changing all 20 to `state: "on", brightness: 255` - full
brightness is the only sensible "the button just turns this on" value
when the source never specified anything more precise for that period.
Verified: re-read the live config afterward, zero button-mode periods
with an `off` default remain anywhere; no errors logged; no light states
changed unexpectedly (button-mode periods are still left alone by
ambient ticks either way - only what a *future* button press resolves to
changed).

## Badrum (upstairs bathroom) - not in the local export at all

Discovered by accident while investigating toa's mystery automations
(2026-09-11): a **complete second bathroom room** exists live
(`data/packages/hus/vaning/overvaning/rum/badrum/` in the real HA
config) with the exact same package shape as toa (scener/knappar/
rörelsevakt/status) - but it isn't in this repo's local `filler från
HA/` export at all, so every prior room's "check the local file first"
approach wasn't available here. Read directly from a targeted,
homeassistant-config-only backup (`backup/generate` → download →
extract just the `badrum` folder → **backup deleted from the instance
and all extracted files, including `secrets.yaml`, removed from local
disk immediately after** - nothing retained beyond what's written here).

### What's there

Structurally almost identical to toa, confirming they share a common
origin (very likely one was built by copying the other, unrenamed
internal bits and all):

- Time-of-day scener system **entirely commented out**, same as toa -
  only "Ingen Hemma" and "Städning" are live. `light.badrum_golvlampa`
  (referenced only by those dead/Städning scenes) doesn't exist live -
  excluded, nothing to migrate for it.
- Real devices: `light.badrum_takbelysning` (button-triggered on/dim-
  warn/restore-on-motion sequence, near character-for-character the same
  automation as toa's - variable names, comments, structure all match)
  and `light.badrum_spegelbelysning` (plain motion on/off, same shape as
  toa's).
- **Same humidity entity-name bug as toa's, but worse here**: the
  combined motion-or-humidity binary sensor checks
  `sensor.badrum_termostat_luftfuktighet` - which, like toa's
  `..._termostat_...` reference, doesn't exist. Unlike toa though,
  **neither** the `termostat` nor a `termometer` variant exists live for
  badrum - there's no real humidity sensor here at all (toa at least has
  a working one under the differently-misspelled name). Badrum's
  RoomFlow motion definition below is motion-only, no threshold trigger.
- **A second, untested physical button**: `event.badrum_spegelbelysning_2`
  exists (a click-status classifier template references it) but has
  never fired (`state: unknown`) - unlike `event.badrum_spegelbelysning`
  (confirmed real and used). Not wired to anything in RoomFlow - no
  evidence of what it's meant to control.
- **Four more dormant, unexplained automations** - the same pattern as
  toa's mystery three, same resolution (never fired, not found in *any*
  config file across the whole instance, disabled anyway for hygiene now
  that RoomFlow owns these lights): `badrum_knapp_1_taklampa`,
  `badrum_knapp_2_taklampa`, `badrum_komplett_belysningssystem`
  ("Badrum Rörelsevakt Belysning"), `badrum_takbelysning_knapp_och_rorelse`.

### What's live now

New shared motion_sensors definition **"Badrum"** (motion-only, 10 min
timeout, 3 min warn at ~10% brightness - no humidity trigger, per above).
`light.badrum_spegelbelysning` (motion_on + motion_off, plain on/off) and
`light.badrum_takbelysning` (motion_off only - button turns it on,
benefits from the same restore-on-motion-return fix as toa once v0.0.21
is actually running after restart; on/255 default, on/13 at night,
matching the source's night-dim behavior exactly). Button:
`event.badrum_spegelbelysning`, click type `press` → toggle takbelysning
(mirrors toa's "press the mirror light's button to control the ceiling
light" pattern exactly). Disabled the three confirmed-real legacy
automations (`badrum_scener`, `badrum_stang_av_scener`,
`badrum_rorelsevakt_spegelbelysning`, `badrum_takbelysning_knapptryck_spegelbelysning`)
plus the four dormant ones above. Verified live - no errors, both lights
correctly off.

## Sovrum (bedroom)

Source reviewed: `filler från HA/hus/vaning/overvaning/rum/sovrum/`,
2026-09-11. Cleanest room shape so far (no cross-room id collisions this
time) but a genuinely non-functional secondary button setup, plus a
second, unexplained light entity.

### Found while auditing

- **A real button that currently does nothing.** `sovrum_pled_knapp_test.yaml`
  (note the filename) sets up a Plejd button (`event.sovrum_knapp`,
  automation `sovrum_plejd_knapp_1`) that only ever writes "long"/"idle"
  into `input_text.sovrum_knapp_1_press_sensor` on a long-press - pulled
  its exact current config from a trace to be sure: a plain `press` with
  a release inside 600ms is a genuine no-op (the whole `if` block that
  would set anything is skipped), and nothing else in the house reads
  that input_text at all, unlike vardagsrum's equivalent setup where a
  second automation consumes it for a toggle+dim sequence. So this Plejd
  button is currently fully cosmetic - confirmed live (`state: unknown`,
  but the `event_type: press` attribute is real, so the entity itself
  works, there's just no consumer). Left alone - not migrated, since
  there's no confirmed intended action to give it.
- **The same file also contains an unrelated dead test automation**
  (`sovrum_taklampa_brightness_adjustment`, "Bulb Brightness") that
  references `binary_sensor.office_motion`/`sensor.office_light_brightness`
  - entities that don't exist anywhere in this house. Clearly a
  copy-pasted tutorial/blueprint example, never adapted. Harmless (its
  triggers never fire), not touched.
- **A second, unexplained ceiling-light-shaped entity.**
  `light.sovrum_taklampa` exists live (real, responsive) alongside
  `light.sovrum_takbelysning` (the one every scene/automation actually
  targets) - and unlike takbelysning (Shelly Dimmer 2, no color_temp),
  `light.sovrum_taklampa` supports color_temp, so it's genuinely a
  different physical fixture, not a duplicate registration. Not mentioned
  anywhere in the source. Left out of RoomFlow, same reasoning as
  vardagsrum's bordslampa/Nadine's banklampa - flag if this should
  actually be brought in.
- **A dormant duplicate button automation**: `automation.ov_sovrum_knapp_golvlampa`
  (unique_id `1743964474772`) exists live, never fired, not in the local
  YAML mirror at all - same "unexplained, inert, leave alone" pattern as
  `vardagsrum_knapp_1`-`6`/`kok_scener` found earlier. The channel-1
  ceiling automation (`ov_sovrum_knapp_taklampa`) has also never fired,
  but its config matches the local file exactly (plain `light.toggle` by
  device_id, no copy-paste red flags) - migrated anyway on the strength
  of the config, not usage history.
- Confirmed via trace (not just the local file, given the staleness
  pattern found elsewhere) that `automation.sovrum_knapp_2_taklampa`
  (despite its name) genuinely targets `light.sovrum_golvlampa`, matching
  this repo's local copy exactly - one room, at least, where the local
  export wasn't stale.

### What's live now

`light.sovrum_takbelysning` (button-mode morning/afternoon/evening with
an "on"/255 default from the start - the cross-room bug above was
already fixed before this room was built - schedule+off day/night,
Städning on 100%, away off) and `light.sovrum_golvlampa` (full schedule
control: off day/night, on 80%/20% afternoon/evening, button-mode
morning with the same on/255 default, Städning on, away off). Both
Shelly channels wired as RoomFlow triggers (channel 1 → takbelysning,
channel 2 → golvlampa). Old `automation.sovrum_scener`,
`automation.sovrum_stang_av_scener`, `automation.ov_sovrum_knapp_taklampa`,
and `automation.sovrum_knapp_2_taklampa` disabled. Verified live - no
errors, both lights correctly off (current period Day).

## Naomis rum

Source reviewed: `filler från HA/hus/vaning/overvaning/rum/naomis_rum/`,
2026-09-11.

### Found while auditing - the scener automation-id mess

- **RESOLVED** (see Nadines rum below): two live automations both traced
  back to unique_id `202507061001` territory, neither unambiguously
  "Naomi's" at first read. `automation.naomis_rum_scener` (no suffix,
  unique_id `naomi_1743885102347`) has **never fired** (0 traces) - still
  can't inspect its real config remotely (YAML-based, 404 on the
  automation config API, no trace to read a config snapshot from) -
  disabled anyway on the reasoning that RoomFlow now owns takbelysning's
  schedule regardless of what this dormant automation would have done.
  `automation.naomis_rum_scener_2` (unique_id `202507061001` - the id
  this repo's local `naomis_rum_scener_automations.yaml` file has,
  aliased "Naomis Rum Scener" in that file) turned out to be **actually,
  currently, correctly Nadine's room's real scener automation** - its
  traces fire on `sensor.nadines_rum_status`, and pulling its config
  straight from a trace (`trace/get`, since the config-editor REST
  endpoint 404s on YAML automations) confirmed it's a proper Dag/
  Eftermiddag/Kväll/Natt/Ingen-Hemma chooser for Nadine's room, structurally
  identical to Naomi's own file. Best read: this id's package file got
  repurposed/duplicated for Nadine's room at some point and this repo's
  local export was never refreshed - so `naomis_rum_scener_automations.yaml`
  here actually describes what is now Nadine's automation, not Naomi's.
  Migrated Nadine's room using the trace-derived real config (not the
  stale local file) and disabled this automation as part of that - see
  below. RoomFlow's own takbelysning behavior here was built directly
  from the scene *definitions'* declared values either way (which don't
  depend on which automation calls them), so none of this blocked
  migrating what was already confirmed.
- **The "bollar" light group is currently broken.** `light.naomis_rum_bollar`
  (group of `light.naomis_rum_bollar_fonster` + `_sangen`) reports
  `unavailable` live - `_fonster` doesn't exist as an entity at all,
  `_sangen` exists but is unavailable (device offline). Left out of
  RoomFlow entirely for now, same as other broken/nonexistent devices
  found elsewhere - nothing to point a schedule at until the hardware
  side is sorted out. This also means button channel 2 (which toggles
  `light.naomis_rum_bollar`) has no RoomFlow equivalent yet - its
  original automation (`automation.naomis_rum_knapp_2_taklampa`, despite
  the name, actually targets bollar) was **left running**, so channel 2
  still does exactly what it always did (toggle a currently-broken
  light).
- Same orphaned per-room "Natt" helper pattern as kök's
  (`input_boolean.naomis_rum_scener_natt` defined, never read anywhere).
- Confirmed the copy-paste device_id bug from entré/kök's notes at the
  source: `device_id: 75ad8fd20b8ce34319060278cad869ca` genuinely belongs
  here (Shelly Dimmer 2, "Naomis rum knappar") - this room's own
  `naomis_rum_knappar_automations.yaml` is the one correct, original
  copy; every other room's reference to that same id was the mistake.

### What's live now

`light.naomis_rum_takbelysning` only - "button" control mode for
morning/afternoon/evening (no source value for those), "schedule" with an
explicit off default for day/night (matches `scene.naomis_rum_dag`/`scene.naomis_rum_natt`),
Städning condition (on 100%, matches the scene), away off. Button channel
1 (`75ad8fd20b8ce34319060278cad869ca`, single click) now toggles it via a
RoomFlow trigger; the old `automation.naomis_rum_knapp_1_taklampa` is
disabled. Verified live - no errors, light state unaffected (was already
off, current period Day).

## Nadines rum

Source reviewed: `filler från HA/hus/vaning/overvaning/rum/nadines_rum/`
plus the real scener config recovered from a trace (see Naomis rum's
notes above), 2026-09-11. Confirms the staleness warning flagged there -
and adds two more real bugs of its own.

### Found while auditing

- **Knapp 2 is wired to Naomi's physical button, not Nadine's own.**
  `nadines_rum_knappar_automations.yaml`'s "Knapp 2" automation
  (`nadine_1743964577875`) triggers on `device_id: 75ad8fd20b8ce34319060278cad869ca`
  channel 2 - Naomi's Shelly Dimmer 2, confirmed by the live device
  registry (same id already confirmed as Naomi's own device in her
  notes). This is a live, currently-active duplicate-trigger bug (unlike
  the dormant ones found elsewhere): pressing Naomi's physical channel-2
  button fires **both** her own automation (toggling `light.naomis_rum_bollar`)
  **and** this one (toggling `light.nadines_rum_bollar`) simultaneously.
  Currently invisible in practice only because both target broken/missing
  light groups (see next point) - would become a real cross-room bug the
  moment either girl's string lights get fixed. Nadine's own physical
  button device (a 4-input Shelly Plus I4, "Nadines rum knappar",
  `device_id 15497c0de3932fe3e80506e76ca852dc`) has three more real,
  currently-unused inputs of its own
  (`event.nadines_rum_knappar_input_1/2/3`) - one of those is almost
  certainly what "Knapp 2" was actually meant to be wired to, but nothing
  in the source or live automations says which, so not guessed here.
  Left the existing (buggy) automation running rather than disable a
  button binding with no confirmed correct replacement - flag for a
  decision once it's known which input is the real "knapp 2".
- **The "bollar" light group is broken, but the two bulbs underneath it
  work fine** - a real fix, not just an exclusion this time. The group
  definition in `nadines_rum_lampor.yaml` lists the same entity twice
  (`light.ov_nadines_rum_boll_sangen`, `light.ov_nadines_rum_boll_sangen`)
  instead of both bulbs, so `light.nadines_rum_bollar` itself is
  `unavailable` live - but `light.nadines_rum_bollar_sangen` and
  `light.nadines_rum_bollar_fonster` (the two individual bulbs the group
  should have wrapped) are both real, responsive, on/off-only lights.
  Added both as separate RoomFlow devices with identical behavior
  (mirroring what the single "bollar" scene wanted) rather than waiting
  on the group entity to be fixed.
- `light.nadines_rum_bollar_fonster` is assigned to area **`naomis_rum`**
  in the entity registry, not `nadines_rum` - a real area-assignment slip
  (didn't block adding it to this RoomFlow room directly by entity_id,
  which doesn't depend on area membership).
- **A new, completely unaccounted-for device**: `light.nadines_rum_banklampa`
  (a bench/dresser lamp, brightness+color_temp capable) - not mentioned
  anywhere in the source YAML, currently reporting `unavailable`
  (offline). No known intended behavior to migrate from - left out,
  same reasoning as vardagsrum's bordslampa. Flag if this should be
  brought in once it's back online and its intended behavior is known.
- Same orphaned per-room "Natt" helper pattern as elsewhere
  (`input_boolean.nadines_rum_scener_natt`, never read).
- **Continuous hold-to-dim, a third confirmed instance.** Knapp 1's
  `long_push` drives a full alternating-direction brightness ramp
  (`automation.nadines_rum_knapp_1_dimmer_taklampa`,
  `brightness_step`/50ms loop, direction flips based on current % and a
  5-minute reset window) - same `IDEAS.md` gap as vardagsrum's Plejd
  button and Naomi's own knapp 1, different hardware/protocol
  (`event.nadines_rum_knappar_input_0`'s native `long_push`/`btn_up`
  vocabulary rather than Plejd's raw press/release). Left running,
  untouched - only the plain `single_push` toggle moved to RoomFlow.

### What's live now

`light.nadines_rum_takbelysning` (button-mode morning/afternoon/evening,
schedule+off day/night, Städning on 100%, away off - same shape as
Naomi's) plus `light.nadines_rum_bollar_sangen`/`_fonster` (full schedule
control: off day/night/morning, on afternoon/evening, Städning on, away
off - both on/off only). Button: `event.nadines_rum_knappar_input_0`,
click_type `single` (substring-matches the real `single_push` event
type) → toggle takbelysning. Old `automation.nadines_rum_knapp_1_taklampa`
disabled, along with the real (trace-recovered) Nadine's scener
automation and Naomi's dormant one (see above). Verified live - no
errors, all three lights correctly off (current period Day).

## Toa (bathroom/toilet)

Source reviewed: `filler från HA/hus/vaning/undervaning/rum/toa/`,
2026-09-11. A genuinely different room shape from every other one so far
- no time-of-day schedule at all, purely motion + button driven.

### Found while auditing

- **The entire time-of-day scene system for toa is dead.** Every branch
  in `toa_scener_automations.yaml` for Morgon/Dag/Eftermiddag/Kväll/Natt
  is commented out - only "Ingen Hemma" and "Städning" are live. Worse,
  the scenes those dead branches would have activated
  (`toa_scenes_tid_pa_dygnet.yaml`, and the live "Städning" scene in
  `toa_scenes_rum.yaml`) target `light.toa_golvlampa`/`_hogtalare`/
  `_skapsbelysning`/`_fonsterlampor` - the exact same device-name pattern
  as vardagsrum's real devices, not toilet fixtures. Confirmed live: none
  of those four entities exist. This whole scener/status subtree is a
  copy-paste leftover, unrelated to what the toa actually contains -
  nothing to migrate from it.
- **The real devices** are `light.toa_takbelysning` (ceiling) and
  `light.toa_spegelbelysning` (mirror, on/off only - confirmed no
  brightness/color_temp support), plus a real Plejd press/release button
  on the mirror light (`event.toa_spegelbelysning_1`) that toggles the
  ceiling light.
- **A humidity entity name typo.** `toa_rorelse_luftfuktighet.yaml`'s
  motion-or-humidity binary sensor checks `sensor.toa_termostat_luftfuktighet`
  (doesn't exist) instead of `sensor.toa_termometer_luftfuktighet` (the
  real one, confirmed live, and what the RoomFlow motion_sensors "Toa"
  definition's threshold trigger already correctly uses). The humidity
  half of that specific derived sensor has silently never worked - motion
  alone still did.
- **More live automations exist than this repo's local YAML mirror shows
  - again** (same pattern as kök's button and entré's outdoor light).
  Beyond what's in the local files, the live instance also has
  `automation.toa_rorelsevakt_automations`, `automation.toa_takbelysning_automations`
  ("Toa Takbelysning styrs av spegelbelysning och rörelse/luftfuktighet"),
  `automation.toa_takbelysning_auto_dimming`, and
  `automation.toa_takbelysning_restore_brightness` - none of which appear
  anywhere in the exported files. Checked traces: **all four have never
  fired** - dormant, likely work-in-progress, same pattern as
  `vardagsrum_knapp_1`-`6`/`kok_scener` found earlier. Not touched.

### What's live now

`light.toa_spegelbelysning` only - standard RoomFlow "motion" control
mode (`motion_on`/`motion_off` both true) on the existing shared "Toa"
motion_sensors definition (already built before this session, just never
attached to a room: motion + >60% humidity, 10 min timeout, 3 min warn at
~10% brightness). The one live, confirmed-duplicate legacy automation
(`automation.toa_rorelsevakt_spegelbelysning`) is disabled. Verified after
- no errors, light state unaffected (was already off).

### Deliberately not touched - `light.toa_takbelysning`

This is the room the "Restore-on-motion-return for motion_off-only
devices" `IDEAS.md` entry was written about - button turns the ceiling
light on, motion alone governs the dim-warning/off/restore sequence.
Asked whether to migrate now and accept the (until this session) known
restore-on-return gap, or leave the working hand-built automation alone -
**the answer was to build the missing RoomFlow feature instead**. Done:
see `_handle_motion_change` in `__init__.py`, released as **v0.0.21**.

Not yet wired up as a RoomFlow device, on purpose:

1. **The release isn't deployed to the live house yet** - this session
   only has API/websocket access to the running Home Assistant instance,
   not filesystem access to install the updated integration. Until
   v0.0.21 is actually installed (HACS update or manual copy) and Home
   Assistant restarted/reloaded, the old motion_off restore gap still
   applies live - migrating `takbelysning` to RoomFlow before that would
   genuinely reproduce the exact regression this feature was built to
   avoid, for real, in the room actively in use while this was written
   (`light.toa_takbelysning` was `on` the whole time).
2. **The live automation picture for takbelysning turned out messier than
   the local YAML mirror suggested** (see the four unknown/dormant
   automations above) - worth understanding before disabling anything
   real, even though none of the four have ever actually fired.

Next step once v0.0.21 is confirmed installed and running: add
`light.toa_takbelysning` with control mode "motion" on the same "Toa"
definition, `motion_on` off / `motion_off` on (button turns it on,
motion only governs dim/off/restore) - then disable
`automation.toa_takbelysning_knapptryck_spegelbelysning` and replace its
toggle with a RoomFlow button trigger on `event.toa_spegelbelysning_1`
(press → toggle), same pattern as vardagsrum's Plejd button.

### Update - takbelysning migrated, and a log-labeling bug found/fixed (2026-09-11)

`light.toa_takbelysning` is now live in RoomFlow on the "Toa" motion
definition exactly as planned above - `motion_on: False`, `motion_off:
True` on every period, button turns it on, motion only governs the
dim-warning/off/restore sequence.

User flagged (correctly, worth double-checking) that the device_log
showed `source: motion_on` entries for takbelysning despite `motion_on`
being disabled - looked like motion was turning it on from cold in
violation of the config. Investigated via the log timestamps: each
`motion_on` entry was directly preceded by a `motion_warn` entry a few
seconds earlier (e.g. `20:03:14` warn-dim to 10%, `20:03:36` "motion_on"
back to 100%) - that's the restore-on-motion-return path added in
v0.0.21 firing correctly (motion paused mid-session → dim warning →
motion came back before the off-timeout → restored to full), not a
fresh motion-triggers-on event. Behavior was correct; the log label
wasn't. `_apply_motion_device_on` hardcoded `source="motion_on"` for
every caller, so the restore path (line ~1486 in `_handle_motion_change`)
was indistinguishable in the log from the genuine motion_on branch
(line ~1469). Fixed by giving the restore call site its own
`source="motion_restored"`, released as **v0.0.25**. No behavior
change, log clarity only - see `CHANGELOG.md`.

User then asked for explicit confirmation that takbelysning is "on by
button, off by motion, with dim-down etc." - re-verified the live
config directly (not just the earlier plan): button (the physical
spegelbelysning switch, `event.toa_spegelbelysning_1`, press) toggles
takbelysning, motion is `motion_on: false` / `motion_off: true` on every
period with warn-dim to 25 (~10%) at 3 min inactivity and off at 10 min,
restoring on return. Confirmed already exactly as wanted - no config
change needed.

While checking, found two YAML automations in
`toa_rorelse_takbelysning_automations.yaml` still showing as *enabled*
in the entity registry - `toa_takbelysning_auto_off` and
`toa_takbelysning_restore_on_motion` - unlike every other legacy
automation for this room, which had already been disabled. Turned out
to be harmless: both were already neutered at the source (their own
trigger/condition point at `binary_sensor.never_exists_dummy`, a sensor
that doesn't exist, so they can never actually fire - the original
author's way of "soft-disabling" them without touching the entity
registry). No real conflict with RoomFlow ever existed. Disabled them
properly via the entity registry anyway for tidiness/consistency with
every other legacy automation in this migration -
`automation.toa_takbelysning_auto_slackning_vid_inaktivitet` and
`automation.toa_takbelysning_aterstall_ljus_vid_aktivitet` are now both
`disabled_by: user`.

### motion_on enabled for Dag/Eftermiddag (2026-09-11)

User wants takbelysning also turned *on* by motion (not just off) during
Dag and Eftermiddag specifically - morning/evening/night stay
button-only-on. Both periods' `default` behavior was already `on,
brightness 255`, so no behavior change was needed, just flipping
`control.day.motion_on` and `control.afternoon.motion_on` to `true`
(morning/evening/night left at `false`). Saved live and verified.

## Utomhusbelysning (outdoor lighting)

Source reviewed: `filler från HA/hus/vaning/ute/`, 2026-09-11. Unlike the
rooms above, this one was already live in RoomFlow too (`light.entre_belysning`
on a dedicated "Uterbelysning" schedule) - and had a real, live bug.

### Found and fixed - inverted period condition

The live "Uterbelysning" schedule modeled on/off with 4 illuminance-threshold
periods (morgon/dag/kväll/natt), but **"kväll"'s condition required
illuminance *above* 500 lux to activate** - backwards for a period meant to
turn the light on as it gets dark. In practice this mostly went unnoticed
because "morgon" (illuminance *below* 500, checked first/highest priority,
no upper time bound) would incorrectly re-trigger every evening once
illuminance dropped again, accidentally producing roughly the right on/off
outcome through the wrong period. Root cause: this schedule was built as a
from-scratch illuminance re-implementation instead of using what the source
YAML already had - a real, working `binary_sensor.morkt_ute` ("dark
outside") entity. `ute_scener_automations.yaml`'s `entre_morker_belysning`
automation was simple and correct: on when `morkt_ute`, off when not,
forced off regardless at Natt or away.

**Rebuilt the schedule to match that directly**: two periods, "På"
(`binary_sensor.morkt_ute` is `on`) above a catch-all "Av", instead of
four illuminance-derived ones. Added a room-level "Natt" custom condition
(`input_boolean.hus_scen_natt`, the same global switch used everywhere
else) ranked above both periods, and enabled `away_default` (off) - it was
disabled before, another live gap next to the inverted condition. Verified
after saving: current period resolves correctly (currently daytime/light
outside → "Av" → light stays off, matching reality), no errors logged.

Once confirmed working, disabled `automation.entre_morker_belysning`
(persistently, entity registry) - the same real conflict flagged in
entré's notes, now resolved the same way as the other rooms.

### Also found - no real device to migrate

`ute_knappar_automations.yaml` defines a button toggling `light.ute_taklampa`
via `event.ute_taklampa` (Plejd-style press) - neither entity exists in the
live registry. No known working hardware behind it; left alone, nothing to
migrate. `ute_lampor.yaml`'s window-lamp light group is entirely commented
out in the source - never built.

### Open - a real physical button exists, not wired to anything yet

`light.entre_belysning` is itself a **Plejd** device (`platform: plejd`,
device_id `00390e9fd2a9d3c75a9edb9ddf3eec7a`) with two of its own
press/release event entities on the same physical unit -
`event.entre_belysning` ("1 pressed", has actually fired) and
`event.entre_belysning_2` ("2 pressed", never fired) - not mentioned in
any source YAML at all, and not currently attached to anything in
RoomFlow. **Not wired up yet** - asked what the two buttons should do
(both toggle the light, like kök's two-channel Shelly, vs. only button 1,
vs. neither) and the answer was uncertain whether the second button is
even real/physically connected to anything. Sebastian is checking in
person and will follow up. Revisit once confirmed - if both are real,
the kök two-channel pattern (both attached to `toggle` on
`light.entre_belysning`) is the natural default.

## Legacy automations disabled (2026-09-11)

RoomFlow now runs some behavior in parallel with what the old per-room
automations were already doing, which risked both systems fighting over
the same lights. Disabled the confirmed-superseded ones persistently via
the entity registry (`config/entity_registry/update`, `disabled_by:
"user"` - survives restarts, not just a runtime `automation.turn_off`),
verified after: `automation.vardagsrum_scener`,
`automation.vardagsrum_stang_av_scener`,
`automation.vardagsrum_knapp_1_single_press_toggle`,
`automation.entre_scener`, `automation.entre_stang_av_scener`,
`automation.entre_knapp_1_taklampa`, `automation.entre_knapp_2_taklampa`,
`automation.hall_scener`, `automation.hall_knapp_1_taklampa`,
`automation.hall_knapp_2`, `automation.kok_rum_scener`,
`automation.kok_stang_av_scener`, `automation.kok_takbelysning_knapptryck`
(replaced by a proper RoomFlow button trigger on kök's own Shelly,
`cc0090dc1ca368146a9218e2e5f07ca1` - both physical channels, not Naomi's
device - see the Kök section below), and `automation.entre_morker_belysning`
(replaced by the fixed Utomhusbelysning schedule - see that section).

**Deliberately left running** - not replicated by RoomFlow yet, would
lose real functionality if disabled: `automation.vardagsrum_knapp_1_long_press_dimma`
+ `automation.plejd_knapp_vardagsrum` (continuous hold-to-dim, see
`IDEAS.md`), `automation.hall_scener_stang_av_stadning_scen_automatiskt`
(auto-expires Hall's Städning after 2h - RoomFlow has no equivalent),
`automation.vardagsrum_tittar_pa_tv_delay_on`/`_off` (the debounce bridge
the vardagsrum "Tittar på tv" condition reads from).

**Found but not touched - unknown content, flag for follow-up**: three
automations exist live that aren't in this repo's local YAML mirror at
all (stale/incomplete export) and have never fired (no trace history, so
their config couldn't be inspected remotely either) -
`automation.kok_scener` (`kok_scener_1` - possibly an unused duplicate of
`kok_rum_scener`), `automation.vardagsrum_knapp_1` through `_6`
(`_20251101` series), `automation.plejd_knapp_vardagsrum_enkel_test`.

## Kök (kitchen)

Source reviewed: `filler från HA/hus/vaning/undervaning/rum/kok/`, 2026-09-11.
Unlike the rooms above, Kök was **already live in RoomFlow** before this
review (3 devices, real brightness values already tuned through the card)
- so this is an audit of what's already there against the legacy YAML,
not a from-scratch migration. The live brightness numbers for
`kok_fonsterlampor` (101/119/76 for morning/afternoon/evening) don't match
the YAML's (153/204/51) at all - almost certainly real manual tuning done
through the card after the initial migration, not a stale copy. Treated
the live config as the more authoritative source everywhere the two
disagree, and only flagged actual defects below rather than "fixing"
brightness numbers back to what the old YAML says.

### Correction (2026-09-11, after user testing)

Both Shelly channels were originally wired to toggle `kok_takbelysning`
(assumed two-way switch, same physical light from two locations - the
pattern confirmed correct for hall/sovrum). Wrong for kök: one channel
actually operates a separate physical switch for `light.kok_bordslampa`,
not a second switch for the ceiling light. First attempt moved channel 1
to bordslampa/left channel 2 on takbelysning - user corrected that it's
the other way around. **Final, confirmed-correct mapping**: channel 1
(trigger `hi0clx5u`) → `kok_takbelysning`, channel 2 (trigger `q7l0ui7o`)
→ `kok_bordslampa`. Verified live both times - no errors, lights
unaffected (attachment-only changes, no behavior values touched).

### Hold-to-dim added (2026-09-11, after building the feature)

Tracked down `kok_takbelysning_knapptryck`'s content via a targeted
backup on the way to answering "what about dimming" - turned out to be a
dead example (`data/exempel_kok_automation.yaml`, referencing
`event.kok_vaggswtich_1`/`binary_sensor.kok_rorelse`, neither of which
exist live) rather than the real button+motion system it looked like -
see the top-level note on RoomFlow's new hold_dim feature (`IDEAS.md`'s
former "Continuous hold-to-dim button action" entry, now built and
released as v0.0.22/v0.0.23). Wired both real Shelly channels to it,
matching their existing toggle targets: channel 1's own
`binary_sensor.kok_takbelysning_channel_1_input` → hold-dims
`kok_takbelysning`, channel 2's → hold-dims `kok_bordslampa`. Verified
live - no errors, light unaffected. Like every RoomFlow code change this
session, won't actually do anything until v0.0.23 is installed and Home
Assistant is restarted.

### Found while auditing - a real, live bug (not RoomFlow-related)

- **`kok_knappar_automations.yaml` (the file in this repo's local mirror)
  is a dead, erroneous copy - but the kitchen's real button was already
  fine.** It defines two automations (`id: naomi_1743964577785` /
  `naomi_1743964577875`, both literally aliased "Naomis Rum Knapp 1/2
  Taklampa") triggered by Shelly `device_id: 75ad8fd20b8ce34319060278cad869ca`
  toggling `light.kok_takbelysning` / `light.kok_bollar` - the *exact
  same* `id:` values exist in `naomis_rum/knappar/naomis_rum_knappar_automations.yaml`
  with the same trigger but toggling Naomi's own lights, and the live
  device registry confirms that Shelly (`75ad8fd2...`, "Naomis rum
  knappar", Shelly Dimmer 2) is genuinely installed in Naomi's room. Same
  copy-paste root cause as the dead `click_status` template flagged in
  entré's notes. **Correction to this file's first read of this bug**:
  the live instance actually has a *separate*, correctly-configured
  automation for the kitchen's own button - `automation.kok_takbelysning_knapptryck`
  (`kok_takbelysning_knapp`) - which isn't in this repo's local YAML
  mirror at all (a stale/incomplete export, not the live truth). So the
  kitchen's physical button was never actually broken in practice; only
  the leftover copy-pasted file was dead weight. That file should still
  be deleted from the real YAML config since it's inert, duplicate-ID
  config either way.
- **`sensor.kok_status` has the same wrong-floor fallback as entré's**
  (`sensor.ov_status` instead of `sensor.uv_status` - see entré's notes)
  - confirms this is a repeated copy-paste pattern, not a one-off.
- **A third orphaned per-room helper**: `input_boolean.kok_scener_natt`
  ("Kök Natt") is defined in `kok_scener_hjalpare.yaml` but never read
  anywhere - `kok_status_scener.yaml` only checks `kok_scener_stadning`.
  Looks like an abandoned attempt at a per-room night override, never
  wired up. Not used in the RoomFlow plan below either.
- **`light.kok_bollar` (Twinkly festoon string lights) has no schedule
  behavior in the source at all** - it only ever appears as the (broken)
  button's toggle target, never in any scene. No known target behavior to
  migrate, and no working physical trigger to bind now either (see above)
  - left out of RoomFlow, same reasoning as excluded devices in other
  rooms.
- `light.kok_adventsljusstake` (advent candlestick) is the concrete
  kitchen example already cited in `IDEAS.md`'s Holidays/seasons entry -
  confirmed by this reading, already correctly absent from the live
  config.

### Live discrepancies - checked and fixed (2026-09-11)

Confirmed `light.kok_bollar` doesn't exist at all - no such entity, no
matching device anywhere in the `kok` area (the `phu:twinkly-festoon` icon
in `kok_lampor.yaml`'s customize block suggests Twinkly string lights were
planned at some point, but nothing was ever actually installed/registered
under that entity_id). Confirms it should stay excluded from RoomFlow -
there's nothing to add.

All four items below were confirmed and applied directly to the live
config (not just this file) via `roomflow/save_config`, verified by
reading the config back and checking real entity states afterward - no
errors in the log, `light.kok_takbelysning`/`light.kok_bordslampa` both
correctly `off` post-save (current period is Day, home state away):

- Removed `kok_bordslampa`'s dangling button attachment
  (`trigger_id: sfl1jo73`, pointing at nothing).
- Added the Städning custom condition (`input_boolean.kok_scener_stadning`),
  takbelysning on 100% - scoped to takbelysning only, since bollar doesn't
  exist to include.
- Enabled `kok_takbelysning`'s `away_default` (off) - now matches every
  other migrated ceiling light.
- `kok_bordslampa`'s night period switched from "button" control mode to
  "schedule" with an explicit off default - now forced off at night,
  matching `scene.kok_natt`.

## Live status (2026-09-11)

Vardagsrum, Entré, and Hall are now actually saved into RoomFlow's live
config (via direct websocket access - `roomflow/get_config`/`save_config`
against the real Home Assistant instance, not just the plans below) -
confirmed by re-reading the config back and checking real entity states
after the save. All three ended up on the shared `main` schedule (same
morning/day/afternoon/evening/night periods kök already uses, driven by
illuminance + clock + day-type, not the sun-event periods the plans below
were originally built around) rather than a new per-room sun-based
schedule - reusing what's already live and proven rather than forking a
second period philosophy. One consequence: **"Natt" ended up as `main`'s
existing built-in "night" period** (it already triggers off the same
`input_boolean.hus_scen_natt`, OR 22:00-06:00 while away, and sits at top
priority in `main`'s period list) rather than a fourth custom room
condition as originally planned below - simpler, and exactly what "make
sure it lines up with the earlier schedule" meant in practice. The
Vardagsrum/Entré plan artifacts (published earlier) still describe the
original sun-based-schedule version; this note is the authoritative
record of what's actually live.

Also found live (not visible from the YAML alone): `light.vardagsrum_taklampa`
is currently reporting `unavailable` (device offline/unreachable) -
unrelated to the config, worth a physical check.

## Hall

Source reviewed: `filler från HA/hus/vaning/overvaning/rum/hall/`,
2026-09-11.

### Found while auditing

- **Two scenes were defined but never wired up.** `hall_scener_automations.yaml`'s
  `choose` block has no branch for "Morgon" or "Städning" at all, even
  though `scene.hall_morgon` (60% brightness) and `scene.hall_stadning`
  (100%) both exist with real values in `hall_scenes_tid_pa_dygnet.yaml`/
  `hall_scenes_rum.yaml` - `sensor.hall_status_scener` even computes
  "Städning" as a valid state, the automation just never checks for it.
  Net effect in the legacy config: mornings and cleaning mode have never
  actually done anything automatically in the hall. Unlike the
  weekend-Morgon omission in vardagsrum (which looked like a deliberate
  choice - no scene existed at all) or the orphaned scenes noted elsewhere
  (dead but harmless), this looked like a plain oversight with real,
  ready-to-use values sitting right there - so **RoomFlow's version fixes
  it**: Morgon (60% → 153/255) and Städning (100% → 255/255) are both
  wired up and live. Flagging clearly in case that's not wanted - it's a
  real behavior change from what the house has actually been doing, not a
  faithful bug-for-bug migration.
- **Entity_id mismatch.** The YAML/automations target
  `light.hall_takbelysning` throughout, but the real registered entity is
  `light.hall_taklampa` (confirmed via the live entity registry) - a
  second, independent reason (besides the `DEVICE_ID_HÄR` placeholder
  already flagged from entré's notes) the physical Shelly buttons never
  actually toggled anything through this automation.
- **More live devices in the `hall` area than the YAML folder knows
  about**: a window lamp ("Hall Fönsterlampa", IKEA TRADFRI bulb) and two
  individual star lights ("Hall Stjärna" x2, IKEA TRADFRI candle bulbs,
  not grouped into one light entity the way vardagsrum's stjärnor are).
  None are mentioned anywhere in the hall YAML folder - no known prior
  automated behavior to migrate. Left out of RoomFlow for now, same
  reasoning as vardagsrum's bordslampa - flag if any of these should
  actually be brought in.
- Same **area-wide away turn-off** and **orphaned-scene** patterns as
  vardagsrum/entré (away turns off the whole `hall` area directly rather
  than activating a scene).

### Found on a follow-up pass (2026-09-11) - hall's own physical button

Missed on the first pass (which only had entré's Shelly channel 2
attached, borrowed from entré's notes). Checked properly this time:
hall's own Shelly Dimmer 2 device (`11eb9e3112badb51381a276b945a1988`,
"OV Hall Taklampa"/"Hall Taklampa") has two real, physically wired switch
channels of its own -
`binary_sensor.ov_hall_taklampa_channel_1_input`/`_channel_2_input` both
exist live, same evidence pattern used to confirm kök's own Shelly. This
is exactly what the dead `hall_knappar` click-status template
(extensionless file, `DEVICE_ID_HÄR` placeholder never filled in) was
clearly trying to build, just never finished. Added both channels as new
RoomFlow triggers (`shelly_gen1_click`, device_id
`11eb9e3112badb51381a276b945a1988`, channels 1 and 2, both toggle) -
`light.hall_taklampa` now has three working button attachments total:
entré's shared channel 2, and hall's own channels 1 and 2. Verified live,
no errors. Checked the hall area for anything else button-like too (the
window lamp and 2 star lights are all plain IKEA TRADFRI bulbs, no
companion remote device in the area) - nothing further found.

### What's live now

`light.hall_taklampa` - full schedule control every period (no
button-only periods needed; unlike vardagsrum/entré's ceiling lights, the
source defines an explicit target for every period), Städning condition,
away off, three button triggers (see above).

## Entré (entryway)

Source reviewed: `filler från HA/hus/vaning/undervaning/rum/entre/` plus the
shared status chain it falls through, 2026-09-11. No open decisions needed
here - the source is internally complete (unlike vardagsrum's missing Natt
scene) and hits no new RoomFlow gaps, so the plan below was built straight
through without stopping to ask.

### Found while auditing

- **`sensor.entre_status` falls back to the wrong floor's status sensor.**
  It reads `sensor.ov_status` (**ö**vervåning/upper floor) when it should
  read `sensor.uv_status` (**u**ndervåning/lower floor) - entré is
  physically on the ground floor, under `hus/vaning/undervaning/rum/`, same
  as vardagsrum/kök/tvättstuga/toa, all of which correctly fall back to
  `uv_status`. Near-certainly a copy-paste artifact (entré's package looks
  cloned from an upper-floor room's, with one `uv`→`ov` left unchanged).
  Doesn't corrupt the actual time-of-day value in practice (`ov_status` and
  `uv_status` both fall through to the same `hus_status`/
  `hus_tid_pa_dygnet` root when their own floor-level Städning boolean is
  off) - the real effect is that entré listens to the *upper* floor's
  Städning toggle (`input_boolean.ov_scener_stadning`, whatever that
  actually is) instead of the lower floor's, and is deaf to the lower
  floor's. Irrelevant to the RoomFlow migration below either way, since
  that only wires up the room-level Städning toggle (see vardagsrum's notes
  on why floor/house-level Städning isn't migrated) - flagging purely as a
  live bug in the current YAML, independent of RoomFlow.
- **A device-classifier template package is duplicated across (at least)
  four rooms with the exact same hardcoded Shelly `device_id`.** The
  extensionless file `entre/knappar/entre_knappar` defines two template
  sensors (`OV Entre Takbelysning Click Status 1/2`) that classify
  single/double/long/idle/release from raw `shelly.click` events matching
  `device_id: 75ad8fd20b8ce34319060278cad869ca`. The *same* device_id,
  verbatim, also appears in `kok/knappar/kok_knappar.yaml`,
  `nadines_rum/knappar/nadines_rum_knappar.yaml`, and
  `naomis_rum/knappar/naomis_rum_knappar.yaml` - four different rooms
  can't share one physical Shelly button, so this is a template that was
  copy-pasted per room without ever being filled in with each room's real
  device_id. Confirms it's dead: entré's *actual* working button automation
  (`entre_knappar_automations.yaml`) uses a completely different, correct
  device_id (`c27a840c7bdbdc1a55eda05a707f810e`) and doesn't reference
  `sensor.entre_takbelysning_click_status_1/2` or
  `binary_sensor.ov_entre_takbelysning_channel_1/2_input` at all - nothing
  in the entré folder consumes what this file produces. Worth the same
  check in kök/Nadine's room/Naomi's room when those get migrated: don't
  build a RoomFlow trigger from this template's device_id, and don't
  assume its presence means those rooms have a second, real button.
- **Two orphan scenes**, same pattern as vardagsrum's unused
  `scene.vardagsrum_ingen_hemma`: `scene.entre_stadning_av` ("Entre
  Städning av", turns takbelysning off) and, functionally,
  `scene.entre_ingen_hemma` - `entre_scener_automations.yaml`'s away branch
  calls `light.turn_off` on `area_id: entre` directly instead of activating
  either scene. Same area-wide-vs-tracked-device-list caveat as vardagsrum
  applies: the real away action reaches everything in the `entre` area, RoomFlow's
  away override will only reach the 3 devices actually added below.

### Design notes

- **Cross-room button: entré's Shelly's second channel isn't entré's.**
  The single physical 2-channel Shelly (`c27a840c7bdbdc1a55eda05a707f810e`)
  has channel 1 toggling entré's own `light.entre_takbelysning` and channel
  2 toggling `light.hall_taklampa` - a different room's ceiling light,
  presumably because the physical switch plate sits at the entré/hall
  boundary. `hall_taklampa` isn't referenced anywhere else in the filler
  tree, so hall's own migration (whenever that happens) shouldn't add a
  second trigger for it - it's owned here. The plan below wires up both
  channels as one shared button-trigger definition (channel 2 attached as a
  plain device-level toggle on `light.hall_taklampa`, independent of
  whether "Hall" exists as a RoomFlow room yet).
- **takbelysning is button-controlled outside Dag**, same per-period
  control-mode pattern as vardagsrum's taklampa: no source behavior in
  Morgon/Eftermiddag/Kväll (left to the button), explicit `off` only in
  Dag, and off again under both the Mys and Natt conditions regardless of
  period/control mode.
- **Natt is the same global manual toggle as vardagsrum's**
  (`input_boolean.hus_scen_natt` - not an automatic time period), but
  unlike vardagsrum, entré's `scene.entre_natt` actually exists in the
  source, so its target behavior (everything off) came straight from the
  scene definition, no decision needed.
- **No weekday/weekend distinction at all** for this room - every period
  in `entre_scener_automations.yaml` maps identically for its "Vardag" and
  "Helg" state (including Morgon, unlike vardagsrum which omits a weekend
  Morgon scene entirely) - so periods below don't need any day-type
  condition, simpler than vardagsrum.

## Vardagsrum (living room)

Source reviewed: `filler från HA/hus/vaning/undervaning/rum/vardagsrum/`
plus the shared `filler från HA/hus/status/` and `filler från HA/hus/vaning/
undervaning/status/` chain it falls back through, 2026-09-11.

### Decisions made (asked, answered)

- **Natt**: not defined anywhere in the source (`scene.vardagsrum_natt` is
  referenced by `vardagsrum_scener_automations.yaml` but never actually
  created - see "Found while auditing" below). Built fresh for RoomFlow as
  its own room custom condition, all managed devices off - deliberately
  *not* reusing the away/"Ingen Hemma" behavior, even though both resolve
  to the same off state today, in case they diverge later (e.g. away gets
  a dimmed night-light behavior at some point).
- **Bordslampa** (`light.vardagsrum_bordslampa`): excluded from RoomFlow
  for now. Only ever appears in the legacy "Mys" scene (turned off) -
  never in Morgon/Dag/Eftermiddag/Kväll/Ingen Hemma - so there's no known
  behavior to give it for the other periods RoomFlow would require. Stays
  manually controlled / outside RoomFlow until there's a reason to define
  the rest of its schedule.

### Found while auditing (not asked about, flagged here for later)

- **`scene.vardagsrum_natt` doesn't exist.** `vardagsrum_scener_automations.yaml`
  has a full `choose` branch for `sensor.vardagsrum_status == "Natt"` that
  calls `scene.turn_on` on `scene.vardagsrum_natt`, but no scene with that
  id/name is defined anywhere under `vardagsrum/scener/` (or anywhere else
  in the filler tree). If this automation is still live in the real
  Home Assistant instance, that branch has presumably been a silent no-op
  (unknown service call target) for as long as it's existed. Worth
  checking whether the same gap exists for other rooms' Natt scenes.
- **`scene.vardagsrum_ingen_hemma` is defined but never called.** The away
  branch in the same automation checks `'Ingen Hemma' in
  states('sensor.vardagsrum_status')` and, when true, calls `light.turn_off`
  directly on `area_id: vardagsrum` - it never activates
  `scene.vardagsrum_ingen_hemma` (defined in `vardagsrum_scenes_tid_pa_dygnet.yaml`)
  at all. That scene is dead config. Also, as defined, it sets
  `brightness: 51` alongside `state: 'off'` on three lights - harmless
  (brightness is ignored when state is off) but dead data either way.
- **Area-wide vs. device-list mismatch on away.** Because the real away
  action is `light.turn_off` on the whole `vardagsrum` area rather than a
  scene with an explicit entity list, it turns off *everything* in that
  area - including `light.vardagsrum_stjarnor` (Christmas lights) and
  `light.vardagsrum_bordslampa`, neither of which RoomFlow will be
  managing. RoomFlow's away override only ever touches devices you've
  explicitly added to the room, so once this migrates, away will turn off
  golvlampa/högtalare/skåpsbelysning/fönsterlampor/taklampa but will
  *not* reach the Christmas lights or the table lamp the way the old
  automation did. Worth knowing before assuming "away" behaves identically
  post-migration.
- **Städning exists at three different scopes** for this room:
  `input_boolean.vardagsrum_scener_stadning` (room), `input_boolean.uv_scener_stadning`
  (floor), `input_boolean.hus_scener_stadning` (house) - each one overriding
  at its own scope, checked in that order as a fallback chain
  (`vardagsrum_status` → `uv_status` → `hus_status`). RoomFlow's plan below
  only wires up the room-level one (`vardagsrum_scener_stadning`) as a
  custom condition, since that's the one someone would actually flip when
  cleaning specifically the living room. The floor/house-level toggles
  aren't migrated - flipping only those (without also flipping the room
  one) will no longer do anything to this room once RoomFlow takes over.
- **"Bortrest" (away-with-return-date) isn't just "away".** When
  `input_boolean.hus_scener_bortrest` is on, `hus_status` reports
  `"Bortrest (hemma ...)"` - a string that matches *none* of
  `vardagsrum_scener_automations.yaml`'s `choose` branches (not a period
  name, not the `'Ingen Hemma'` substring match, not a room scene). Net
  effect in the old config: while marked as away-on-vacation, the living
  room's lights are left completely alone - no scene, no turn-off, nothing
  - unlike a normal "nobody's home right now" away, which does turn
  everything off. RoomFlow has no equivalent tri-state (see "Explicit
  pause/resume for a room or device" in `IDEAS.md`) - its away override is
  binary. The plan below treats RoomFlow's away the same for both cases
  (always turns things off), which is a real behavior change specifically
  for the vacation case. Flag if that's not wanted.
- **"Tittar på tv" only ever touches one light.** The legacy scene turns
  off `light.vardagsrum_golvlampa` and nothing else - högtalare,
  skåpsbelysning, fönsterlampor, and taklampa are left exactly as they
  were. RoomFlow condition tiers can do the same thing (a device with no
  "Tittar på tv" behavior defined just falls through to the room's normal
  away/weekend/default for that period), so this isn't a gap - just noting
  it so nobody "fixes" the other four devices into also reacting to TV
  state, thinking it was an oversight.

### Known RoomFlow gaps this room actually hits

- **Continuous hold-to-dim on long-press is not built.** The Plejd
  ceiling-light button (`event.vardagsrum_taklampa`) both toggles on a
  plain press *and* ramps brightness continuously while held (alternating
  direction, reversing near 20%/80%) via
  `vardagsrum_knapp_1_dimmer`/`vardagsrum_plejd_knapp_1` +
  the `input_text.vardagsrum_knapp_1_press_sensor`/
  `input_boolean.vardagsrum_knapp_1_dim_direction` helpers. RoomFlow button
  triggers only support discrete one-shot actions - no repeating
  hold-to-dim action type exists yet (see "Continuous hold-to-dim button
  action" in `IDEAS.md`). **Keep the existing Plejd blueprint automation
  and its two helpers running** - only the plain toggle-on-press half
  moves to RoomFlow (a `press` click-type trigger → toggle taklampa);
  removing the legacy toggle automation once that's wired up avoids a
  double-toggle on every press, but the dimmer automation stays.
- **Christmas star lights are out of scope.** `light.vardagsrum_stjarnor`
  (a light group over 3 individual star lights) is folded directly into
  the regular Morgon/Dag/Eftermiddag scenes in the source, with no
  date-based gating in the YAML itself (presumably enabled/disabled by
  hand each year). RoomFlow has no holiday/date/season override yet (see
  "Holidays / specific dates and seasons" in `IDEAS.md`) - same reason
  this was already left out of the kitchen migration. Left out of the
  RoomFlow plan below; keep controlling it manually or via the existing
  YAML during the season until that feature exists.

### Design notes for anyone extending this later

- **taklampa's control mode varies by period, and that's supported.**
  RoomFlow's `device.control[period].mode` is per-period, not a single
  device-wide setting - condition-tier behaviors (Mys, Natt, Städning)
  still apply even when a period's control mode is "button" (only the
  plain default tier is skipped). That's what makes it possible to match
  the source exactly: taklampa is "button" (schedule leaves it alone) for
  Morgon/Eftermiddag/Kväll, "schedule" with an explicit off default only
  for Dag, and off under the Mys condition regardless of period/control
  mode.
- **Dag/Eftermiddag/Kväll's "sunrise/sunset, but never before/after a
  fixed clock time" logic doesn't need AND-groups** - a sun-position period
  condition's `earliest`/`latest` clamp fields (`_clamp_time` in
  `__init__.py`) cover it directly: Dag = sunrise clamped to `earliest:
  08:00`, Kväll = sunset clamped to `earliest: 20:00`. Eftermiddag needs no
  clamp of its own - it's correctly superseded the moment Kväll's own
  condition becomes true, as long as Kväll is listed above it in the
  period priority list.
- **Weekend-morning "do nothing" was simplified.** The source only defines
  a weekday Morgon scene call - weekend mornings intentionally get no
  automatic scene at all (whatever was active overnight just continues).
  The plan below instead gives Morgon the same 06:00 start on both weekday
  and weekend, for simplicity. The more faithful version is possible (make
  Morgon's period condition require weekday via an AND-group, so on
  weekends no period matches at all at that hour and RoomFlow skips the
  room entirely) but wasn't the default - revisit if the "nothing changes
  on weekend mornings" behavior turns out to matter in practice.

## Vardagsrum taklampa/fönsterlampor not turning off at night, and a real integration bug (2026-09-12)

User reported taklampa and fönsterlampor not turning off at night despite
the new Natt-condition config. Investigation turned up two independent
problems, both now fixed:

1. **A stuck legacy automation was fighting RoomFlow for taklampa.**
   `automation.plejd_knapp_vardagsrum` (blueprint-based click-type
   generator) and `automation.vardagsrum_knapp_1_long_press_dimma` (its
   hand-built hold-to-dim consumer) were still enabled from before
   RoomFlow's own toggle+hold_dim triggers were added for
   `event.vardagsrum_taklampa` - and a trace showed the dimmer stuck
   `running` since a button press at 20:17:54, still calling
   `light.turn_on` in a 50ms loop hours later because the shared
   `input_text.vardagsrum_knapp_1_press_sensor` helper never left its
   "long" state. That's what kept re-lighting taklampa every time
   RoomFlow tried to turn it off. Also found a third redundant duplicate,
   `automation.vardagsrum_knapp_1` (unique_id `vardagsrum_knapp_1_20251101`,
   a stray file directly under `/config` with no `.yaml` extension, not
   in the local export at all) directly toggling taklampa on the same
   button. Stopped the stuck automation (`automation.turn_off`, which
   cancels a running instance) and disabled all three via the entity
   registry. Left `vardagsrum_knapp_2/4/5/6` (golvlampa/högtalare/mys
   toggle/skåpsbelysning) and `vardagsrum_knapp_3` (fönsterlampor) alone -
   RoomFlow has no button trigger for any of those yet, so disabling them
   would kill real, currently-only, physical control.

2. **A real RoomFlow bug, found while chasing why the device log kept
   claiming success that didn't happen live**: every device-mutating
   `hass.services.async_call` in `__init__.py` (schedule/condition apply,
   toggle, off, dim, motion-off, motion dim-warning) used Home Assistant's
   default non-blocking dispatch - so a genuine execution failure (a
   Zigbee link that briefly dropped, which is exactly what the system log
   showed happening in this window: a `zigpy.application` "Watchdog
   failure" and several "Error executing service" errors for other
   lights) never reached RoomFlow's own try/except, and it logged a
   success entry anyway. Fixed by adding `blocking=True` to every one of
   those calls except the 50ms hold-to-dim ramp tick (deliberately kept
   non-blocking so a slow device can't stall the ramp - it never logged
   success either, so lower stakes). Released as **v0.0.26** - this is
   the fix that actually makes the device log trustworthy again; the
   Zigbee blip itself was a separate, real hardware event, not something
   RoomFlow caused.

## Toa spegelbelysning not turning on for real motion, after a HA restart (2026-09-12)

After installing v0.0.26 (HACS had already pulled it; needed an actual
`homeassistant.restart` to load the new code, confirmed via HACS's
`installed_version`/`pending_upgrade` fields), live-tested it. Two of
three retested devices matched log-vs-reality perfectly this time
(`badrum_takbelysning`, `toa_takbelysning`), confirming v0.0.26 itself
works.

`vardagsrum_taklampa` still looked wrong after a real button press (log
said "off", light stayed on, brightness even drifted up on its own in
exact +10 steps at a slowing cadence) - traced to leftover backlog:
the old stuck-dimmer bug from the day before had spent hours calling
`light.turn_on` in a 50ms loop with a step of exactly 10, and this was
that queue still draining through the mesh/gateway on its own, unrelated
to any currently-running code. Expected to stop once the backlog empties
(around brightness 255) - no code fix applicable here, it's a hardware
queue artifact from yesterday's incident, not a new bug.

Then a real, live report: user walked into Toa, `light.toa_spegelbelysning`
did not turn on despite `binary_sensor.toa_rorelsesensor` genuinely
firing off→on. Root cause: Toa's motion definition is "motion OR
`sensor.toa_termometer_luftfuktighet` > 60" (so the light stays on
through a shower after motion stops), and the humidity had been sitting
at 62-63% continuously since before the restart - so the *combined*
active flag never went back to false, and `_handle_motion_change`'s
edge-gate (`if new_active == previous_active: return`) meant the real
motion pulse looked like "nothing changed" and did nothing, even though
`spegelbelysning` had gone off in the meantime (most likely as a side
effect of the messy restart-time re-apply, several rooms had near-
simultaneous log entries right at HA startup). Not a config or hardware
issue - a genuine architectural gap: only the aggregate's own transition
edge caused a re-apply, so a sticky secondary trigger could permanently
swallow every later real motion pulse.

Fixed in **v0.0.27**: `_handle_motion_change` now also recognizes an
actual motion-type trigger's own on-transition (via the raw
`state_changed` event, checked against the definition's trigger list -
`threshold_above` triggers don't count) independent of whether the
combined flag flipped, and re-lights any `motion_on` device that's
currently off in that case. Threshold-only re-activity (humidity
fluctuating while already above threshold) still does nothing on its
own, by design - only a genuine motion pulse gets this self-heal.

Also could not manually turn `light.toa_spegelbelysning` on directly (two
timed-out attempts, no HA-level error, no recent `last_reported` at all) -
same category of live hardware/mesh unresponsiveness as
`light.kok_takbelysning` earlier, not something fixable via the API.

## Zigbee/Plejd mesh instability escalated to continuous ghost button-presses (2026-09-12, later same day)

User reported all lights "blinking" and buttons "not working" broadly.
Checked the button entities directly (not just the lights):
`event.vardagsrum_taklampa`, `event.toa_spegelbelysning_1`, and
`event.badrum_spegelbelysning` were all cycling
`unavailable -> press -> unavailable -> press -> ...` in near-perfect
lockstep (within milliseconds of each other, roughly every 20-90s) - a
mesh/coordinator repeatedly dropping and reconnecting these three
devices, each reconnect re-sending the last button state as a "fresh"
press. RoomFlow was reacting correctly to what looked like real presses
(logging real `button_toggle` entries) - this is the same root event as
the morning's `zigpy.application` "Watchdog failure", now happening
continuously rather than as a one-off.

Per user request, removed `light.vardagsrum_taklampa`'s button
attachments as a stopgap: first the press->toggle one (`4ddzl6n7`, since
that was the one visibly making the ceiling light flip back on right
after being turned off), then also the hold->hold_dim one (`5ul8lgnv`)
on a follow-up request, once it became clear the toggle removal *didn't*
stop the flickering by itself. Confirmed via the device log staying
completely silent for `vardagsrum_taklampa` while the light kept
flipping on/off every 2-3 seconds in the live entity state/logbook -
proof this specific rapid flicker is not RoomFlow, not the button
config, not even Home Assistant, but the physical device/mesh itself
(a genuinely dying driver, loose connection, or radio module is more
consistent with a 2-3s cadence than a network-level dropout). Toa's and
Badrum's button triggers were left as-is (not asked to remove them) -
same ghost-press pattern applies to them too if it comes up again.

**Next step is physical, not software**: check/power-cycle the Zigbee
coordinator (SkyConnect) and the Plejd gateway, and inspect
`vardagsrum_taklampa`'s own wiring/driver directly - nothing left to
chase in RoomFlow's config for this specific symptom.

## Root cause found and fixed: Proxmox USB passthrough, plus a RoomFlow hardening (2026-09-12/13)

The actual root cause turned out to be at the Proxmox host level, not
RoomFlow, not the legacy automations, not even really the Plejd mesh
itself in the way first suspected:

- **Diagnosis**: Plejd's own per-device diagnostic entities (`sensor.rssi_*`,
  `binary_sensor.is_gateway_*`) showed every Plejd device in the house at
  -78 to -104 dBm - uniformly weak, pointing at the shared USB Bluetooth
  adapter (Realtek ASUS USB-BT500) rather than any one device. All three
  affected buttons (`event.vardagsrum_taklampa`, `event.toa_spegelbelysning_1`,
  `event.badrum_spegelbelysning`) were found cycling
  `unavailable -> <stale cached timestamp> -> unavailable` in near-perfect
  millisecond lockstep across rooms - proof of one shared cause
  (the adapter/mesh dropping and reconnecting as a whole), not three
  independent flaky buttons. System log confirmed real driver-level
  errors (`habluetooth.scanner: Error stopping scanner`, `hci0: Failed to
  load conn params: status=17`, `pyplejd.ble.connection: ... Failed to
  connect to PlejdHardware(BLEaddress=F96114400813...)`).
- **Real root cause**: Home Assistant runs as a Proxmox VM (`haos15.1`,
  vmid 101) with the Bluetooth adapter passed through by **USB bus/port
  path** (`usb1: host=3-2`) instead of by persistent vendor:product ID -
  the classic Proxmox USB-passthrough footgun. A full host/VM reboot can
  re-enumerate USB ports in a different order, so the VM loses the
  device entirely (confirmed live: `bluetooth` integration went to
  `setup_retry` with reason `"Bluetooth adapter None with address
  A0:AD:9F:73:CC:9D not found"` right after a `hassio.host_reboot`).
- **Fix**: found the adapter's real vendor:product ID via `lsusb` on the
  Proxmox host (`0b05:190e`, ASUS USB-BT500) and changed the VM config
  (`qm set 101 -usb1 host=0b05:190e,usb3=1`) - stable regardless of which
  physical port/enumeration order applies on any future reboot. Verified
  through both a soft guest reboot and a full `qm shutdown`/`qm start`
  cycle - `bluetooth`/`plejd` came back `loaded` both times, and the
  ghost-press pattern stopped entirely (~8.5 hours clean overnight, one
  isolated 10-second self-recovering blip, nothing like the old
  every-1-3-minutes pattern).
- **Also found and fixed while in there**: the Proxmox host itself was
  memory-overcommitted (15GB total, ~14GB already claimed by the two
  running VMs, 3.2GB of 8GB swap actively in use) - likely a contributing
  factor to timing-sensitive USB/Bluetooth flakiness under load, on top
  of the passthrough bug. Enabled memory ballooning on the HA VM
  (`balloon: 0` -> `balloon: 4096`, needed a real VM restart to attach
  the balloon device) and lowered host `vm.swappiness` from the default
  60 to 10 (`/etc/sysctl.d/99-swappiness.conf`). Available host memory
  went from 2.2GB to 5.8GB immediately after.
- **RoomFlow hardening, v0.0.28**: even with the hardware fixed, a
  transient reconnect blip is still possible in principle (BLE is BLE) -
  and does nothing to protect the **legacy automations**, which have no
  equivalent guard and would still fire on a reconnect echo if one ever
  recurs. Added a general defense in RoomFlow itself: an `event.*`
  entity's state is always the ISO timestamp of when it last fired, so a
  re-announced timestamp more than 10 seconds old, arriving right after
  the entity was `unavailable`, is now recognized as a stale reconnect
  echo and ignored (logged as `stale_reconnect`) rather than treated as a
  real press - doesn't affect genuine presses at all, since those always
  report a fresh timestamp. This only protects rooms once they're back
  on RoomFlow, not while running the legacy automations.
- Vardagsrum's own button (both toggle and hold_dim) is still
  deliberately unattached in both RoomFlow and the legacy automations
  from the troubleshooting session - re-enable once confirmed stable for
  longer, now that the actual root cause is fixed rather than just
  worked around.

## Back on RoomFlow: v0.0.28 released, then a live Day-period design fix (2026-09-13)

Switched fully back to RoomFlow: re-enabled the integration, disabled
all 41 legacy automations again, re-attached vardagsrum taklampa's
toggle + hold_dim button triggers. Verified `bluetooth`/`plejd` both
`loaded` with v0.0.28 running, no errors.

While testing, a synthetic REST-injected "press" on `event.vardagsrum_taklampa`
(no matching "release") left the entity's cached state contaminated,
producing a repeating false "held" signal for a couple minutes -
resolved by reloading the Plejd config entry (forces a clean re-sync
from the real mesh). Not a real bug, just a limitation of testing a
platform-owned entity via raw state POSTs instead of a real physical
press - noted here so it's not mistaken for a returning ghost-press
issue if seen again in a future test.

Then a real report: button only ever turned the light *off*, never on.
Root cause: current period was "Day", and taklampa's Day-period
`default` tier was `state: off` (control mode "schedule") - the one
period, unlike morning/afternoon/evening/night, with no "on" default at
all (intentionally set early in the migration to mirror the source's
`scene.vardagsrum_dag`, lamp off during actual daylight). A manual-on
press always reads the real default tier regardless of control mode (by
design, see the button-mode/off-default bug fix above) - so during Day
specifically, a press correctly-per-that-config resolved to "off".
Asked whether that should stay as designed or whether the button should
be able to override it - answer: button should always be able to turn
it on. Fixed by giving Day the same shape every other period already
has: control mode `button` (schedule leaves it alone, so it doesn't
auto-turn-on every day) with `default: {state: "on", brightness: 255}`
(so a press resolves to something sensible). Confirmed working live by
the user pressing the physical button during Day.

## Room-by-room live testing round (2026-09-13)

Same Day-period off-default bug recurred twice more, found live: entré's
`light.entre_takbelysning` (fixed identically, confirmed live), then
found and fixed proactively on vardagsrum's `golvlampa`,
`fonsterlampor`, `hogtalare`, `skapsbelysning` while wiring up their
physical buttons (channels 2-6) into RoomFlow for the first time -
these had never been attached to anything working before (the legacy
YAML file for them, `data/vardagsrum_knappar_automations`, had no
`.yaml` extension and was never `!include`d by `configuration.yaml`,
so they'd been silently dead the whole time regardless of which system
was "live").

Added a genuine RoomFlow feature at the user's request rather than a
one-off automation: a room-level button action **"Toggle a condition"**
(`toggle_condition`, v0.0.31) that flips one of the room's own custom
conditions' helper entity directly. Used to wire vardagsrum's "Knapp 5"
to toggle *only* `input_boolean.vardagsrum_scener_mys` - deliberately
room-scoped, unlike the original legacy automation which toggled both
vardagsrum's and entré's Mys booleans together. (A standalone automation
for this was tried first and never fired even once despite a correct
trigger/entity match and a successful `automation.reload` - concluded
reload doesn't reliably re-attach a *brand-new* automation's trigger the
way it does for edits to an existing one. Deleted once the RoomFlow
feature was confirmed working instead.)

**Found, not yet fixed**: Naomi's physical "Knapp 2" currently controls
Nadine's star-lights group live (`automation.naomis_rum_knapp_2_taklampa`,
unique_id `naomi_1743964577875`) - harmless before because Nadine's
group entity was itself broken/unavailable, now live since the light
group fix above (see the `nadines_rum_lampor.yaml` fix in the file
history) made it actually respond. Needs the user to identify which of
Nadine's other unused Shelly Plus I4 inputs is her *real* "Knapp 2"
before this can be corrected.

## Nadine's-room button investigation - root cause was config, not code (2026-09-13)

Live report: pressing Nadine's room's button never turned on/off her
ceiling light. A Shelly Plus I4 input produces 3 rapid state changes per
physical press (`btn_down`, `btn_up`, `single_push`) - the first two
correctly logged as `click_type_mismatch` (they don't match the
trigger's configured `click_type: "single"`), but the third
(`single_push`, which *does* match) appeared - across three independent
reproductions - to produce no button_log entry at all, and the light
genuinely never changed. No warnings/errors in `system_log` for any of
these presses; deep review of the click-type-matching and event-listener
code found no logical flaw that would explain dropping specifically the
third event.

Added a temporary unconditional diagnostic log line at the top of
`_handle_button_press` (v0.0.32) to determine empirically whether the
handler was even being invoked for that third event, deployed directly
to the live filesystem via the SMB config share (bypassing HACS, which
was still stuck two versions behind) since a full HA restart is required
for Python changes to take effect. After the restart, re-querying the
button_log turned up the answer directly - **the "ran" outcome had been
there all along** for all three original test presses; the earlier
investigation's read of the log was incomplete, not the log itself.

That "ran" outcome, with the light's history showing zero state changes
across the whole window, pointed straight at the same Day-period
off-default bug as vardagsrum/entré above: `light.nadines_rum_takbelysning`'s
Day-period `default` was `state: off`, so the button's toggle-on
resolved right back to off with nothing visibly changing - not a dropped
event, just a manual-on resolving to a period default that happened to
be off. Fixed the same way as before (Day default -> on). A config-wide
sweep for the same pattern (Day default off, every other period's
default on, on a device with a button attached) turned up four more
affected devices - Hall's `taklampa`, Naomi's rum's `takbelysning`,
Sovrum's `takbelysning` and `golvlampa` - fixed identically with the
user's explicit go-ahead, none of them previously reported as broken
(the bug is silent: the button "works" per the log, it just doesn't
visibly do anything on the one period where the default is wrong).
Confirmed fixed live: Nadine's light toggled off in response to a real
press, matching a fresh `last_changed` timestamp. Removed the temporary
diagnostic logging afterward (v0.0.33) since the code itself was never
at fault.

**Takeaway worth remembering**: this Day-period off-default bug has now
been found independently four separate times (vardagsrum, entré, then
this sweep's four more) across the migration. It's worth treating any
new "button doesn't do anything" report as this bug first, before
assuming a code-level regression - check the device's Day-period
`default.state` before spending time on event-listener debugging.
