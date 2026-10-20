# MagicBand door reader firmware (ESP32-S3 + ESP32)

PlatformIO / Arduino firmware for a park-style "touch point" door entry. There are two boards:

- **Reader** (outdoor, wall-mounted ball head). Waveshare ESP32-S3-Zero with:
  - PN532 NFC over I2C (reads MagicBand / ISO14443A UIDs)
  - R503 capacitive fingerprint sensor (templates live on the sensor)
  - WS2812B halo ring (plus an optional Mickey backlight segment)
  - MAX98357A amp and a 40 mm speaker
  - MAX3485 RS-485 transceiver and a tamper switch on the rear hatch

  It has **no Wi-Fi and no authority**. It reports what it reads and shows what it is told.
- **Controller** (indoor). ESP32 devkit with:
  - MAX3485 and the strike MOSFET/relay
  - exit (REX) button, door contact, enroll button

  It keeps the user list in NVS and makes every decision. It talks to Home Assistant over MQTT.
  If Wi-Fi or MQTT is down, the door still works.

The two boards share a 4-core cable: 12 V, GND, RS-485 A/B. Each frame
carries an HMAC-SHA256 tag and a replay counter.

## Build variants

Two build flags pick the variant (`include/config.h`, set per env in `platformio.ini`):
- `HAS_FINGERPRINT`: R503 fitted (1) or not (0)
- `ALL_IN_ONE`: split reader + controller (0), or a single reader that is the whole door (1)

| Env | Board | Mode | R503 | Flash with |
|---|---|---|---|---|
| `reader` | ESP32-S3-Zero | split, outdoor pod | yes | + `controller` |
| `reader_nofp` | ESP32-S3-Zero | split, outdoor pod | no (band only) | + `controller` |
| `controller` | ESP32 devkit | split, indoor: decisions, strike, HA | (from the reader's `HELLO`) | + `reader` / `reader_nofp` |
| `reader_aio` | ESP32-S3-Zero | all-in-one | yes | alone |
| `reader_aio_nofp` | ESP32-S3-Zero | all-in-one | no (band only) | alone |

**Which mode?**
- **Split.** Use it when the reader faces an **unsecured side**: outdoors, a hallway, anywhere a
  stranger can reach it. The reader holds no relay and no user list. Ripping it off the wall
  gives nothing that opens the door (see Security notes).
- **All-in-one.** Only when the reader is on the **secure side** of the door: inside the flat,
  a lab or office wall that is already behind another locked door, a cupboard or gate inside the
  house. One board then does everything the controller does:
  - access engine and NVS users
  - relay/MOSFET strike output, exit (REX) button, door contact
  - Wi-Fi/MQTT with the **same Home Assistant entities**
  - local lights and sound, with no `FEEDBACK` frames

  There is no RS-485 cable and no link key. The strike wire is inside the reader, so anyone who
  can open the reader can open the door.

**Without an R503** (`*_nofp`):
- Users with policy `band_only` work as usual.
- Users with `band_and_finger` or `finger_only` are **denied** (reason `no_fp_hw`). They are
  never let in on the band alone.
- `binary_sensor.fingerprint_configuration_problem` turns on while such users exist. Fix it by
  setting them to `band_only`, or by fitting an R503 and flashing the FP build.
- New users default to `band_only`.
- *Enroll finger* is refused, and `sensor.enrollment` shows `no_fingerprint_hw`.

In split mode the controller learns this from the reader's `HELLO` capability bits
([`PROTOCOL.md`](PROTOCOL.md#capabilities-protocol-2)). The same `controller` firmware works
with either reader.

- Wiring, BOM, power budget: [`../electronics/WIRING.md`](../electronics/WIRING.md)
- Link protocol: [`PROTOCOL.md`](PROTOCOL.md)
- No reader yet? [`tools/reader_sim.py`](tools/reader_sim.py) plays the reader over a USB-RS485 adapter

## Layout

| Path | What |
|---|---|
| `include/config.h` | Variant flags, pins for every board / mode, every tunable |
| `include/secrets.h` | Link key + OTA password. Generated, git-ignored |
| `lib/mb_crypto` | Portable SHA-256 / HMAC. Uses mbedtls on the ESP32 |
| `lib/mb_protocol` | Framing, tags, replay window, counters, payloads |
| `lib/mb_access` | User store interface, access policy engine, enrollment state machine, event log, `DoorCore` (event → unlock / feedback / log actions, shared by controller and all-in-one) |
| `src/common` | RS-485 port + NVS counter store (split mode, both boards) |
| `src/reader` | Reader (all four reader envs): NFC, R503, LEDs, chime synth; link or local door app |
| `src/door` | Door app (controller + all-in-one): strike, inputs, NVS users, MQTT / Home Assistant |
| `src/controller` | Controller: RS-485 link to the reader, feeds `src/door` |
| `test/` | Unity tests for `lib/` (`native` env) |
| `tools/` | Python protocol module, vector generator, key provisioning, reader simulator |

`lib/` has no Arduino headers, so the policy and protocol code that matters
is tested on the PC.

## Build and flash

```bash
pip install platformio
cd magicband_reader/firmware
pio test -e native                 # 83 unit tests: crypto, protocol + capabilities, access policy, door core
python3 tools/provision.py         # writes include/secrets.h with a random 32-byte key

# split mode: flash both boards from the same secrets.h
pio run -e controller -t upload    # ESP32 devkit over USB
pio run -e reader -t upload        # ESP32-S3-Zero over USB-C (hold BOOT while plugging in the first time)
pio run -e reader_nofp -t upload   # ...or the reader without R503

# all-in-one: one board, no link key needed (secrets.h still sets OTA_PASSWORD if present)
pio run -e reader_aio -t upload       # with R503
pio run -e reader_aio_nofp -t upload  # without R503

pio device monitor -e controller   # 115200 baud (or -e reader_aio ...)
```

In this repo PlatformIO lives in `.pydeps` / `.pio-core`, so run it like this:
`PYTHONPATH=$PWD/../../.pydeps PLATFORMIO_CORE_DIR=$PWD/../../.pio-core python3 -m platformio test -e native`.

After the first flash, controller updates can go over Wi-Fi with
`pio run -e controller -t upload --upload-port magicband.local`. Pass the OTA
password from `secrets.h` with `--upload-flags --auth=<password>`. The reader
has no radio, so update it over USB through the rear hatch. Opening the hatch
trips the tamper switch, and that's expected.

The all-in-one has Wi-Fi and OTA too:
`pio run -e reader_aio -t upload --upload-port magicband.local`.

### Provisioning the key

- `tools/provision.py` makes a random key. **Flash both boards from the same `secrets.h`.**
  Save the key in your password manager: `python3 tools/provision.py --show`.
- A new key (`--force`) resets the link counters on each board the first time it boots with that
  key. Re-flash both boards.
- With mismatched keys, every frame fails the tag check. You'll see:
  - the reader blinking amber (OFFLINE)
  - `binary_sensor.reader_link` off
  - `link_errors` counting up
- Building without `secrets.h` stops with an error. `-DMB_ALLOW_DEV_KEY` builds with a public
  test key. Use it for bench tests only.

## First boot

1. **Controller.** With no saved Wi-Fi, it opens an access point `magicband_xxxxxx-setup`. Join
   it and enter your Wi-Fi plus the MQTT broker host, port, user and password. The portal closes
   after 3 minutes. The door works the whole time.

   To open the portal again later, hold the **enroll button while powering up**.
2. **Reader.** It breathes soft white once it hears the controller, and blinks amber while it
   doesn't. The controller's onboard LED is on while the reader is online.
3. **Home Assistant.** The device "MagicBand door" appears by MQTT discovery.
4. **All-in-one.** It behaves like the controller: same setup portal and same HA device. To
   reopen the portal, hold the **exit button** (or the optional enroll button on GPIO17) while
   powering up. The halo breathes white as soon as it boots, because there is no link to wait for.

## Enrolling

The default policy for new users is **band + finger**. Without an R503 (`*_nofp`, or a split
reader whose `HELLO` lacks `CAP_FINGERPRINT`) it is **band only**.

1. In HA, set **New user name**, then press **Enroll next band (new user)**. You can also
   short-press the enroll button on the controller. The halo shows a purple comet.
2. Tap the band within 30 s. The user is created, the chime plays, and the new user becomes the
   **Selected user**.
3. Press **Enroll finger for selected user**. The ring turns purple. Touch, lift, touch again
   within 50 s. The R503 stores the template and the controller binds its page id to the user.
4. Optional:
   - Set **Selected user policy** (`band_only`, `band_and_finger`, `finger_only`)
   - Toggle **Selected user enabled**
   - **Add band to selected user**: up to 4 bands and 4 fingers per user, 16 users
   - **Delete selected user**: also deletes that user's templates on the R503

To cancel enrollment, press **Cancel enrollment** or long-press the enroll button (3 s).

A band that already belongs to someone is never moved to another user.

## Home Assistant

### Entities

| Entity | Topic | Notes |
|---|---|---|
| `lock.door` | `magicband/lock/set`, `magicband/lock/state` | `UNLOCK` pulses the strike (Unlock time). `LOCK` ends the pulse early |
| `sensor.last_scan_user`, `sensor.last_scan_band`, `sensor.last_scan_result` | `magicband/scan` (JSON, retained) | `result`: granted / denied / need_finger / locked_out, plus `reason`, `method`, `ts` |
| `event.access` | `magicband/access` | `event_type`: granted / denied / need_finger / locked_out, plus `user`, `method`, `reason` |
| `binary_sensor.door` | `magicband/door` | Door contact, ON = open |
| `binary_sensor.reader_tamper` | `magicband/tamper` | ON if the hatch is open, the reader is offline, or a burst of forged/replayed frames arrives |
| `binary_sensor.reader_link` | `magicband/reader` | Connectivity (diagnostic). Always ON on the all-in-one |
| `binary_sensor.fingerprint_configuration_problem` | `magicband/fp_problem` | ON = enabled users need a finger but the reader has no R503: they are denied (`no_fp_hw`) |
| `sensor.enrollment` | `magicband/enroll` | idle / waiting_band / waiting_finger / user_created / finger_added / timeout / full / no_fingerprint_hw … |
| `sensor.link_rejected_frames` | `magicband/link_errors` | Bad tag + replay + out of window |
| text / selects / switch / buttons / numbers | `magicband/<name>/set`, `magicband/cmd` | Enrollment and settings, see above |

Every decision is also published to `magicband/log`. The last 32 events are
kept in a ring buffer: publish `{"cmd":"dump_log"}` to `magicband/cmd` to
replay it. `magicband/users` (retained) lists the users. Band UIDs there are
masked to first/last byte unless `SHOW_FULL_UID` is set.

JSON commands on `magicband/cmd`, for scripts:

```json
{"cmd":"unlock"}
{"cmd":"enroll_band","name":"Alex"}
{"cmd":"add_band","user":"Alex"}
{"cmd":"enroll_finger","user":"Alex"}
{"cmd":"set_policy","user":"Alex","policy":"band_only"}
{"cmd":"rename","user":"Alex","new_name":"Alexandra"}
{"cmd":"delete_user","user":"Alex"}
{"cmd":"clear_lockout"}
{"cmd":"cancel"}
{"cmd":"list_users"}
{"cmd":"dump_log"}
```

### Unlock your existing smart lock on "granted"

If the door already has a smart lock (instead of, or as well as, the strike),
let HA open it whenever the controller grants access:

```yaml
automation:
  - alias: "MagicBand: open front door smart lock"
    mode: single
    trigger:
      - platform: state
        entity_id: event.magicband_door_access
    condition:
      - condition: template
        value_template: >
          {{ trigger.to_state.attributes.event_type == 'granted'
             and trigger.to_state.attributes.method in ['band', 'finger'] }}
    action:
      - service: lock.unlock
        target:
          entity_id: lock.front_door        # your existing smart lock
      - service: notify.mobile_app_phone
        data:
          message: "Front door opened by {{ trigger.to_state.attributes.user }}"
```

The `method` filter matters:
- It leaves out `exit_button`, so pressing REX from inside doesn't also unlock the smart lock.
- It leaves out `remote`, so an HA unlock doesn't loop back.

Check your entity ids under *Settings → Devices → MagicBand door*.

## Tuning

| Setting | Where | Default |
|---|---|---|
| Strike type | `STRIKE_ENERGIZE_TO_UNLOCK` | 1 = fail-secure strike. Set 0 for a maglock (energised = locked) |
| Unlock time | HA number / `UNLOCK_PULSE_MS` | 5 s. Relocks early once the door has opened and closed again |
| Finger window | `FINGER_TIMEOUT_MS` | 8 s |
| Lockout | `MAX_FAILURES`, `LOCKOUT_MS`, `LOCKOUT_MAX_MS` | 5 failures → 30 s. Doubles each time, up to 15 min. The exit button always works |
| Deny while tampered | `TAMPER_DENIES_ACCESS` | 1 |
| No tamper switch (indoor housing) | `HAS_TAMPER_SWITCH` | 1. Set 0 if GPIO16 has no switch, or it reads as "hatch open" and denies every scan |
| LED count | `LED_HALO_COUNT`, `LED_MICKEY_COUNT` | 42 + 0 (matches the CAD ring) |
| LED power cap | `LED_MAX_BRIGHTNESS`, `LED_CURRENT_LIMIT_MA` | 128/255 and 1.2 A (see WIRING.md) |
| Brightness / volume | HA numbers (sent to the reader with `SET_CONFIG`) | 96 / 60 % |
| Pins | `include/config.h` | Must match WIRING.md |

## Sounds and lights

| State | Lights | Sound |
|---|---|---|
| Idle | halo breathes soft white, Mickey dim white | – |
| Reading | blue comet chases round the halo | tiny tick |
| Need finger | halo pulses slowly, R503 ring breathes blue | double blip |
| Granted | everything solid green (1.5 s) | chime |
| Denied | blue/red pulses ("see a cast member" blue) | two low tones |
| Error / offline | amber blink | three low beeps |
| Enroll | purple | – |

The chime is an original rising C-major arpeggio (C6–E6–G6–C7). It is
synthesised in code from sine partials with an exponential decay. The
firmware contains no recorded or copied audio, and it doesn't imitate the
park sound.

## Security notes

**MagicBand UIDs can be cloned.** The reader only uses the band's ISO14443A UID. It can't do
more, because Disney's keys are not public. That UID:
- is sent in the clear to any NFC phone within a few cm
- can be copied to a "magic" Gen1a/CUID card, or emulated by a Flipper / Proxmark / Chameleon,
  in seconds

So the default policy is **band + finger**:
- the band says who you claim to be
- the R503 finger match has to belong to *that same user*, within 8 s

Use `band_only` only where a copied band is an acceptable risk. Capacitive sensors can be fooled
by good fake fingerprints too, so two factors are what you actually rely on.

Most MagicBands (original, 2.0, MagicBand+) answer with a fixed 7-byte UID. If the serial log or
`sensor.last_scan_band` shows a different UID on every tap, that band (or phone) uses random UIDs
and can't be enrolled.

**Relay and logic stay indoors.** Pulling the reader off the wall only gives access to:
- 12 V and GND
- an RS-485 pair carrying authenticated frames

There is no relay or "unlock" wire to short. A replacement board without the key can't produce a
valid tag. Replayed frames fail the counter check.

This applies to **split mode only**. The all-in-one has the strike output inside the reader, so it
belongs on the secure side of the door (see Build variants).

**Tamper.** The tamper sensor turns on when any of these happens:
- the rear hatch switch opens
- the reader goes quiet (cable cut or unplugged)
- forged or replayed frames arrive (`LINK_ERROR_ALERT` per minute)

With `TAMPER_DENIES_ACCESS` the controller refuses scans while tampered. The exit button still
works. Automate a notification on `binary_sensor.reader_tamper`.

**Key and flash.** The link key is compiled into both firmwares.
- Keep `secrets.h` out of git (it is ignored).
- The reader hangs outside. Turn on ESP32-S3 **flash encryption** (and ideally secure boot) once
  it works, so a stolen reader doesn't give up the key. See Espressif's docs. It is one-way on
  production settings.
- If a reader is lost, run `provision.py --force` and re-flash both boards.

**MQTT is part of the lock.** Anyone who can publish to `magicband/lock/set` or `magicband/cmd`
can open the door or enrol themselves.
- Give the controller its own MQTT user.
- Use broker ACLs.
- Keep the broker off the internet.

PubSubClient has no TLS here. Rely on the LAN.

**Fail-secure / fail-safe.**
- The default is a fail-secure strike: it stays locked without power, and the inside handle
  always opens the door.
- A maglock is fail-safe and opens on power loss. Building and fire codes usually require a
  REX sensor, a manual release and a fire-alarm interlock with it. Check your local rules.

**Offline behaviour.** Users, policy and lockout all live on the controller. Access keeps
working with Wi-Fi or MQTT down. Events made while MQTT is down are only in the 32-entry ring
buffer.
