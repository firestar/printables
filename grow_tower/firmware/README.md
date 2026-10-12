# Grow tower firmware (ESP32)

PlatformIO / Arduino firmware for the outdoor rotating aeroponic grow tower:
- ESP32-WROOM-32 30-pin devkit, powered from 12 V through a 12 V → 5 V buck
- 12 V submersible pump (5–10 W) on a logic-level MOSFET module
- 28BYJ-48 **12 V** geared stepper on a ULN2003 board. Its 15T pinion drives the 128T ring gear
- Fog mode (optional, Gyroid Mist Shell): ultrasonic fogger (12/24 V, ~1 A)
  and 12 V 80 mm duct fan (~0.2 A), each on its own MOSFET module
- Low-water float switch (dry-run protection)
- Optional reed/hall switch, one pulse per tower revolution (homing + stall detection)
- Optional DS18B20 water temperature probe

It runs the pump on a day/night cycle (or, in fog mode, the fogger and fan with
short pump flushes) and turns the tower in small steps. It stops pump, fogger
and fan on low water and the stepper on a stall. You can see and
change everything from a small web page at `http://growtower.local/`. The
schedule keeps running without Wi-Fi.

## Wiring

| ESP32 pin | Goes to | Notes |
|---|---|---|
| VIN (5V) | Buck converter 5 V out | Set the buck to 5.0 V **before** connecting. 12 V in from the main supply. |
| GND | Buck GND, MOSFET module GND, ULN2003 GND, sensor grounds | One common ground |
| GPIO25 | Pump MOSFET module `SIG`/`PWM` | Active HIGH |
| GPIO26 | Fogger MOSFET module `SIG`/`PWM` | Active HIGH. Fog mode only |
| GPIO27 | Fan MOSFET module `SIG`/`PWM` | Active HIGH. Fog mode only |
| GPIO16 | ULN2003 `IN1` | |
| GPIO17 | ULN2003 `IN2` | |
| GPIO18 | ULN2003 `IN3` | |
| GPIO19 | ULN2003 `IN4` | |
| GPIO32 | Float switch → GND | Internal pull-up. Default: contact **closed = water OK** (see below) |
| GPIO33 | Reed / hall switch → GND | Internal pull-up. Optional. 100 nF to GND near the ESP32 helps on long cables |
| GPIO4 | DS18B20 data (yellow) | **4.7 kΩ pull-up to 3V3**. Red → 3V3, black → GND. Optional |
| GPIO2 | Onboard LED | Status, see below |

Power side:

| From | To | Notes |
|---|---|---|
| 12 V PSU − | MOSFET modules `VIN−`, ULN2003 `−`, buck IN− | |
| 12 V PSU − | MOSFET module `VIN−`, ULN2003 `−`, buck IN− | |
| Pump MOSFET `OUT+`/`OUT−` | Pump | Low-side switch: `OUT−` is the switched negative |
| Fogger MOSFET `OUT+`/`OUT−` | Fogger | Same low-side wiring as the pump |
| Fan MOSFET `OUT+`/`OUT−` | 80 mm fan | Red to `OUT+`, black to `OUT−`. Flyback diode, see below |
| ULN2003 5-pin socket | 28BYJ-48 plug | Keyed. Red is the common +12 V |

The ULN2003 board must be fed **12 V** for the 12 V motor. Remove the 5 V
jumper if your board has one, or feed its `+` pin straight from 12 V. The
ULN2003 has its own flyback diodes, so the stepper needs nothing extra.
Draw is about 0.2 A while moving and zero when idle, because the firmware
switches all coils off between moves.

Stepper direction: the firmware only turns one way. If the tower turns the
wrong way, swap `PIN_STEP_IN1`↔`PIN_STEP_IN4` and `PIN_STEP_IN2`↔`PIN_STEP_IN3`
in `include/config.h`. Gearing (`STEPPER_HALF_STEPS_PER_REV`, `PINION_TEETH`,
`RING_TEETH`) lives there too. One tower revolution is 4096 × 128 / 15 ≈ 34953
half-steps, about 70 s at the default 500 half-steps/s.

MOSFET module for the pump: a D4184 or IRLZ44N-based module turns fully on
from 3.3 V. Plain IRF520 modules do **not** (they need about 10 V on the gate)
and will run hot. If you build your own, use a logic-level MOSFET with a 100 Ω
gate resistor and a 10 kΩ gate pull-down, so the pump stays off while the
ESP32 boots.

**Flyback diode on the pump:** put a 1N5819 (Schottky) or 1N4007 across the
pump, cathode (stripe) to +12 V, right at the pump or the module output. Many
modules leave this out. Without it, the switch-off spike kills the MOSFET.

**Fan and fogger:** use the same kind of logic-level module (with a 10 kΩ gate
pull-down) for each. GPIO26/27 are not strapping pins but float while the
ESP32 boots, so the pull-down is what keeps them off. Put a **1N5819 or
1N4007 across the fan** too, cathode to +12 V: it is a brushless motor and
kicks back on switch-off like the pump. The fogger's driver board needs no

diode. A 24 V fogger needs its own 24 V supply: feed its module `VIN+` from
24 V and join the 24 V negative to the common ground. The fogger has its own
low-water cut-off. The firmware still switches it off on low water.
Float switch polarity: `WATER_OK_WHEN_CLOSED 1` in `include/config.h`.
Mount the float so its contact is **closed while there is enough water**.
That way a broken wire, corroded contact or unplugged float reads as "low
water" and the pump stays off. If your float closes when the water is low
instead, set it to `0`, but then a cut cable is no longer detected.

Reed switch: glue a magnet to the ring gear or tower so it passes the reed
switch once per revolution. Turn on "Sensor fitted" in the web UI to enable
homing, the tower angle readout and stall detection.

## Outdoor notes

- Put the ESP32, buck, MOSFET module and ULN2003 board in an **IP65 junction
  box**. Bring every cable in through a **cable gland** (PG7/PG9) from below.
  Add a drip loop before each gland.
- The 28BYJ-48 is not waterproof. Mount it under a printed hood with the shaft
  pointing down, or seal the case seam and cable exit with silicone.
- Mount the box above the reservoir, never under the tower.
- Use a **conformal coat** (acrylic or silicone, e.g. MG Chemicals 422B) on
  the boards. Mask the USB port, buttons and headers first.
- Put a small silica gel pack inside the box. A Gore-style vent plug stops
  condensation pumping in when the box heats and cools.
- Use outdoor-rated cable (UV-stable jacket) and waterproof connectors
  (e.g. SP13) to the pump, motor and sensors so parts can be swapped.
- The 12 V PSU should be outdoor-rated, or stay indoors on a GFCI/RCD outlet.
- The ESP32 runs warm in direct sun. Use a light-colored box, shaded if possible.

## Build and flash

```bash
pip install platformio
cd grow_tower/firmware
pio test -e native          # scheduler unit tests on the PC
pio run -t upload           # first flash over USB
pio device monitor          # 115200 baud
```

Later updates can go over Wi-Fi:

```bash
pio run -t upload --upload-port growtower.local
```

If you set `OTA_PASSWORD` in `include/config.h`, add `--upload-flags --auth=<password>`.
The pump, fogger, fan and stepper switch off during an OTA update.

## First boot

1. All outputs start off. With no saved Wi-Fi, the ESP32 opens an access point
   named `growtower-setup`. Connect to it and the setup page opens. Pick
   your network. The pump and rotation schedule already runs during this,
   using the day cycle until the clock is set.
2. Once connected, open `http://growtower.local/` (or the IP printed on the
   serial log). Set your **time zone** first, because the day window uses local time.
3. If saved Wi-Fi is unreachable at boot, the setup AP opens for 3 minutes,
   then it closes and the ESP32 keeps retrying the saved network every 30 s.

Status LED:

| LED | Meaning |
|---|---|
| fast blink | low water or stepper stall, look at the web UI |
| slow blink | no Wi-Fi (the schedule still runs) |
| solid | pump or fogger on |
| short blip every 3 s | idle, all OK |

## Behaviour

- **Pump**: ON/OFF cycle in minutes, day (default 15/15) and night (default
  5/55). The day window defaults to 06:00–20:00 local time (NTP + POSIX TZ).
  Until the clock syncs, the day cycle is used. Each new day/night period,
  and each settings save, restarts the cycle with an ON phase. Set OFF to 0
  for always on, or ON to 0 for always off.
- **Low water**: low for 5 s → pump, fogger and fan off (no fan run-on) and
  the low-water alert is set. The level must read OK for 30 s before they
  resume. The alert stays set until you clear it. Manual ON can't override it.
- **Feed mode** (`feed_mode`):
  - `aero` (default): the pump cycle above. Fogger and fan never run, not
    even on manual ON.
  - `fog`: the fogger runs its own ON/OFF cycle, day (default 10/5 min) and
    night (default 5/15 min), restarting with ON at each day/night change. The
    fan runs whenever the fogger runs, plus `fan_run_on_s` (default 60 s) after
    it stops to clear the duct. The pump only flushes: `flush_on_min` every
    `flush_on_min + flush_off_min` (default 2 min every 2 h), day and night
    alike. The day/night pump cycle is ignored.
  - **Fogger over-temperature**: fogging warms the water. With a DS18B20
    fitted, the fogger stays off while the water is above `fog_max_temp_c`
    (default 28 °C) and resumes at 1 °C below it. Manual ON can't override it.
    Without the probe there is no limit.
- **Rotation**, planned in degrees of tower rotation:
  - `off`
  - `interval` (default): `rot_step_deg` moves that average `rot_deg_per_hour`.
    The default is 15° moves at 360°/h, which is one move every 150 s and one
    revolution per hour. Move sizes add up exactly with no rounding drift:
    24 × 15° is exactly 34953 steps, and 15 revolutions is exactly 524288.
  - `continuous`: turns at `motor_speed` the whole window.

  Rotation only runs in the day window unless "Also rotate at night" is
  ticked. Each move accelerates and decelerates (AccelStepper, 250 half-steps/s²,
  max 500 half-steps/s by default, 800 at most). The coils are switched off
  when the stepper stops.
- **Homing** (sensor needed): turns until the magnet passes, then stops. After
  that, the status shows the tower angle from the magnet. Every pulse re-homes.
- **Stall** (sensor needed): if the stepper makes `stall_pct` % of a
  revolution's steps (default 130 % ≈ 45 400 steps) without a magnet pulse,
  summed across moves, it stops at once and the stall fault latches. This catches
  a jammed gear, a slipping pinion, or a stepper skipping under load. Clear it
  from the UI once the tower turns freely.
- **Manual override**: pump, fogger and fan on/off, tower turn/hold. It always
  times out (default 10 min) and falls back to auto. One-off moves (+15°, +90°,
  +1 rev) run from the UI or API. A manual fan OFF wins over the fogger: only
  use it briefly, or fog pools in the duct.
- **Watchdog**: the task watchdog reboots the ESP32 if `loop()` hangs for 30 s.
  Outputs go low on reset. The ULN2003 inputs and the MOSFET gate
  pull-downs keep everything off while it boots.
- Stepping runs from a 250 µs `esp_timer`, separate from `loop()`, so web
  requests don't make the motor stutter.

## REST API

All JSON. No authentication, so keep it on a trusted LAN.

`GET /api/status`

```json
{"fw":"0.1.0","uptime_s":5123,"time_valid":true,"time":"2026-10-12 14:03:11","is_day":true,
 "pump":{"on":true,"mode":"auto","manual_left_s":0,"phase_left_s":412},
 "feed_mode":"aero",
 "fog":{"on":false,"mode":"auto","manual_left_s":0,"phase_left_s":0,"temp_hold":false},
 "fan":{"on":false,"mode":"auto","manual_left_s":0,"run_on_left_s":0},
 "motor":{"moving":false,"mode":"auto","manual_left_s":0,"steps_to_go":0,
          "homed":true,"homing":false,"angle_deg":105.0,"steps_since_pulse":10195},
 "water_low":false,"alerts":{"low_water":false,"stall":false},"temp_c":18.4,
 "revs":{"sensor":true,"pulses":37,"total":37.29,"today":8.25},
 "rssi":-61,"ip":"192.168.1.50","heap":214000}
```

`revs.total` and `revs.today` are computed from steps, so they work without the
sensor. `angle_deg` is `null` until homed. `temp_c` is `null` when no DS18B20 is
found. `time` is `null` until NTP has synced.

`GET /api/config` returns the current settings. `POST /api/config`
accepts any subset of them, then saves to flash and returns the full config:

```json
{"day_on_min":15,"day_off_min":15,"night_on_min":5,"night_off_min":55,
 "feed_mode":"aero","fog_day_on_min":10,"fog_day_off_min":5,"fog_night_on_min":5,
 "fog_night_off_min":15,"fan_run_on_s":60,"fog_max_temp_c":28,"flush_on_min":2,
 "flush_off_min":118,
 "day_start":"06:00","day_end":"20:00","tz":"CET-1CEST,M3.5.0,M10.5.0/3",
 "rot_mode":"interval","rot_step_deg":15,"rot_deg_per_hour":360,"rot_at_night":false,
 "rev_sensor":false,"stall_pct":130,"motor_speed":500,"manual_timeout_min":10,
 "steps_per_rev":34953}
```

`rot_mode` is one of `off|interval|continuous`, `feed_mode` one of `aero|fog`.
`steps_per_rev` is read-only (it comes from the gearing in `config.h`).
Numbers out of range are clamped: `rot_step_deg` 1–360, `rot_deg_per_hour`
1–3600, `stall_pct` 110–300, `motor_speed` 50–800, `fan_run_on_s` 0–600 and
`fog_max_temp_c` 15–40. A bad `day_start`/`day_end`/`rot_mode`/`feed_mode`
returns HTTP 400.

`POST /api/manual` returns the status:

```bash
curl -X POST growtower.local/api/manual -d '{"target":"pump","state":"on","minutes":5}'
curl -X POST growtower.local/api/manual -d '{"target":"fog","state":"off","minutes":30}'
curl -X POST growtower.local/api/manual -d '{"target":"fan","state":"on"}'
curl -X POST growtower.local/api/manual -d '{"target":"motor","state":"on"}'   # turn continuously
curl -X POST growtower.local/api/manual -d '{"target":"motor","state":"off"}'  # hold still
curl -X POST growtower.local/api/manual -d '{"action":"rotate","degrees":90}'
curl -X POST growtower.local/api/manual -d '{"action":"home"}'
curl -X POST growtower.local/api/manual -d '{"action":"clear_faults"}'
```

`target` is `pump|motor|fog|fan`, `state` is `on|off|auto`. `minutes` is
optional (1–240), and the default is `manual_timeout_min`. `fog`/`fan` ON
returns HTTP 409 unless `feed_mode` is `fog`. `rotate` takes 1–3600 degrees.
`rotate` and `home` return HTTP 409 while the stall fault is set, and `home`
also returns 409 without the sensor.

## Code layout

| File | What |
|---|---|
| `include/config.h` | Pins, gearing, stepper speed, polarity, network, timing constants |
| `include/scheduler.h`, `src/scheduler.cpp` | Pure schedule logic (pump / fogger / fan cycles, rotation in degrees → steps, low water, over-temp, homing, stall, manual) |
| `include/motor.h`, `src/motor.cpp` | AccelStepper driver on an `esp_timer`, coils off when idle |
| `src/main.cpp` | Hardware I/O, NVS settings, Wi-Fi/NTP/mDNS/OTA, watchdog |
| `src/web.cpp` | Web UI (PROGMEM page) and REST API |
| `test/test_scheduler/` | Unity tests with a simulated stepper + tower, `pio test -e native` |
