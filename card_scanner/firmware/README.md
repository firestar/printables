# Card scanner motion controller firmware (ESP32-S3)

PlatformIO / Arduino firmware for the motion side of the trading-card scanner, penny-sleever
and 3-bin sorter.

- **Raspberry Pi 5** (host) runs the cameras and recognition, and decides each card's bin.
- **ESP32-S3-DevKitC-1** (this firmware) owns every moving or blowing part:
  - 4 steppers on TMC2209s: elevator, pick arm, feed rollers, tongue
  - 3 servos: lift cup, pusher, diverter
  - vacuum pump, air pump and 5 solenoid valves
  - scan lights and all sensors

The two talk newline-delimited JSON over the ESP32's native USB port.

- Protocol (the host contract): [`PROTOCOL.md`](PROTOCOL.md)
- Wiring, pin table, power, BOM, driver currents: [`../electronics/WIRING.md`](../electronics/WIRING.md)
- No hardware yet? [`tools/mcu_sim.py`](tools/mcu_sim.py) runs this firmware's sequencer on a
  physics model behind a pseudo-terminal

## Layout

| Path | What |
|---|---|
| `include/config.h` | Pin map, sensor polarity, steps/mm, TMC addresses, vacuum sensor scaling |
| `lib/cs_proto` | Flat JSON parser/writer (no heap), error codes |
| `lib/cs_motion` | `Hal` interface, settings table (NVS keys), `Scanner`: command handling + the non-blocking job sequencer |
| `lib/cs_sim` | `SimHal`: physics model behind `Hal` (tests + simulator) |
| `src/esp32` | Board glue: `Esp32Hal` (FastAccelStepper, TMCStepper, LEDC, MCP23017, ADC), NVS store, USB line reader |
| `src/sim` | Simulator main: `Scanner` + `SimHal` on stdin/stdout |
| `test/test_json` | JSON parse/write |
| `test/test_scanner` | Every command and error path, in simulated time |
| `tools/cs_host.py` | Reference host client + bench CLI (`cycle`, `status`, `set`, ...) |
| `tools/mcu_sim.py` | Simulator behind a pty |
| `tools/run_native_tests.py` | Tests + simulator with plain g++ (no PlatformIO) |
| `tools/test_cs_host.py` | End-to-end: `cs_host.Link` against the simulator |

## Build, test, flash

```bash
cd card_scanner/firmware
pio test -e native                 # unit tests (real Unity)
pio run -e esp32s3                 # firmware
pio run -e esp32s3 -t upload       # flash over the USB port
pio run -e sim                     # simulator -> .pio/build/sim/program

# without PlatformIO (g++ only):
python3 tools/run_native_tests.py --sim
python3 -m unittest tools/test_cs_host.py
```

The DevKitC-1 has two USB-C ports. Use **"USB"** (native, GPIO19/20) for both flashing and
the host link. The **"UART"** port (CP2102 on GPIO43/44) is not used.

The host sees the board as `/dev/ttyACM0`. A udev rule gives it a stable name:
```
# /etc/udev/rules.d/99-card-scanner.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", SYMLINK+="card_scanner"
```

## How the firmware works

`loop()` does three things, each pass, never blocking:
1. `hal.poll()`: reads the input expander every 1 ms, filters the vacuum ADC every 2 ms.
2. Reads host bytes into a line buffer and hands complete lines to `Scanner::handleLine`.
3. `Scanner::tick()`:
   - debounces e-stop, lid and magazine-low (20 ms) and raises events
   - advances the running job by one phase check

There is no `delay()` anywhere in the motion path:
- Steps are generated in hardware: FastAccelStepper on the S3's RMT channels, 4 axes.
- Servo and valve dwell times are phase timers.
- Each phase has its own timeout, and a timeout ends the job with an error reply.

Sensor-stopped moves use a hard stop (`forceStop`) from the loop. The loop runs at tens of
kHz, so at 150 mm/s the card overshoots `scan_stop` by well under 0.1 mm. Keep `loop()`
free of blocking calls (Wi-Fi, long prints) to keep it that way.

Job sequences (details and error mapping in `PROTOCOL.md`):

| Job | Phases |
|---|---|
| `home` | servos rest → tongue → pick → elevator. Each axis: back off its switch if pressed, seek, hard stop, zero |
| `feed` | raise until `stack_top` → air-knife puff → pick cup + grip check → pick stroke while the rollers run → release + return the arm → stop on `scan_stop` (double-feed gauge sampled throughout) |
| `sleeve` | `mag_empty` check → N20 sleeve pick until `sleeve_present` (max `sleeve_pick_ms`) → platen vacuum (2nd sleeve-in-place check) → lift servo down → lift cup + grip → lift up (re-check grip) → mouth jet → tongue in → feed to `sleeve_mouth` + `insert_mm` (card ~70 mm in) → pusher to seat angle (pawl seats the card) → tongue out → release |
| `sort` | diverter → pusher out (seat → +36) + exit rollers → `exit` trip → `exit` clear → rollers stop, pusher rest |
| `eject_reject` | diverter to bin 2 → feed `reject_mm` onto the platen → as `sort` |

### Fail-safe behaviour

| Event | What the firmware does |
|---|---|
| Any job error | All axes hard-stop, every valve and pump off, pusher parked, error reply. `homed` is cleared when an axis may be out of place (homing, tongue, axis timeouts) |
| E-stop input, lid open, or `estop` | The above, plus the drivers are disabled (EN high). State `estop` until `reset`. E-stop and lid **also cut 24 V in hardware**: the firmware is not the safety circuit (see WIRING.md) |
| Input expander lost (I2C error) | Reads as lid open, so the machine e-stops. The firmware retries the expander every second |
| Reset / brown-out | EN has a pull-up, so the drivers are off. MOSFET gates have pull-downs, so the valves close and the pumps stop |

## Tuning on the bench

1. Use `python3 tools/cs_host.py /dev/ttyACM0 status` to check every sensor by hand: block
   each beam, press each switch.
2. Before mounting any servo horn, set the angles: `set lift_down_deg ...`, `pusher_out_deg`,
   `div0_deg` to `div2_deg`.
3. `home`, then `feed` with a few cards. Adjust:
   - `pick_travel_mm` so the card is well into the nip
   - `feed_speed`
   - `vac_grip_kpa`: check `status.vacuum_kpa` with the cup sealed against a card, then set
     the threshold to about half of that
4. Calibrate `STEPS_PER_MM_FEED` in `config.h`: command a long feed, measure, scale.
5. Sleeving: tune in this order:
   - `lift_down_deg` until the cup just seals
   - `lift_up_deg` until the mouth opens about 3 mm
   - `jet_ms`
   - `tongue_depth_mm`
   - `insert_mm`, so the card ends fully inside the sleeve
6. Driver currents (`cur_*`): the lowest values that do not skip at your speeds.
   See WIRING.md for the Vref table.
7. `python3 tools/cs_host.py /dev/ttyACM0 cycle -n 20` for a soak test.

All tunables survive reboots (NVS namespace `cs`). To restore the defaults, erase flash:
`pio run -e esp32s3 -t erase`.

## Simulator

```bash
python3 tools/mcu_sim.py --link /tmp/card_scanner -- --speed 5 --double 0.05
python3 tools/cs_host.py /tmp/card_scanner cycle -n 10
```

The simulator is the real `Scanner` on `SimHal`. Its physics model covers:
- a 50-card hopper, a 100-sleeve magazine, the card path, a first-order vacuum
- seeded fault injection: double feed, pick fail, lift fail, exit miss
- run-time control lines (`#estop 1`, `#lid 1`, ...), listed in PROTOCOL.md

`--speed` scales time, so a host test suite can run a full cycle in under a second.
