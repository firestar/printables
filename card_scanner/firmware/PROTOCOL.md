# Host ↔ motion controller protocol

The Raspberry Pi 5 (host) talks to the ESP32-S3 (motion controller) over the
ESP32's native USB port (USB CDC, `/dev/ttyACM*` on the Pi). The host owns
the cameras and recognition. The MCU owns every motor, valve, servo and sensor.

The implementation is `lib/cs_motion/src/cs_scanner.cpp`. It is unit-tested in `test/`. A
reference client is [`tools/cs_host.py`](tools/cs_host.py). The simulator
[`tools/mcu_sim.py`](tools/mcu_sim.py) runs the same code without hardware.

## Framing

- 115200 8N1 (nominal: USB CDC ignores the baud rate).
- UTF-8 **newline-delimited JSON**: one object per line, `\n` terminated. A `\r` before
  the `\n` is ignored. Blank lines are ignored.
- Host → MCU lines may be up to **256 bytes**. Longer lines are dropped and answered with
  `{"id":-1,"ok":false,"err":"bad_cmd","msg":"line too long"}`.
- Requests are **flat** objects: values are numbers, strings, `true`/`false`/`null`.
  Nested objects/arrays, duplicate keys, keys over 15 chars, strings over 39 chars and
  more than 8 fields are rejected as `bad_cmd`.
- MCU → host lines are at most 640 bytes. Replies may contain nested objects (`status`).

## Messages

| Direction | Shape |
|---|---|
| Host → MCU request | `{"id":<int>,"cmd":"<name>", ...args}` |
| MCU → host success | `{"id":<int>,"ok":true, ...data}` |
| MCU → host failure | `{"id":<int>,"ok":false,"err":"<code>","msg":"<text>"}` |
| MCU → host event | `{"evt":"<name>", ...}` |

- `id` is a 32-bit signed integer chosen by the host and echoed in the reply. Use a
  counter. The MCU does not check that ids are unique.
- A line that is not valid JSON, or has no integer `id`, gets a reply with `"id":-1`.
- `msg` is free text for logs and UIs. Programs should branch on `err` only.
- Field order in replies is fixed (`id`, `ok`, then the rest), but parse them as JSON
  anyway.

### Quick vs motion commands

- **Quick commands** reply at once: `ping`, `status`, `lights`, `set`, `get`, `estop`, `reset`.
- **Motion commands** start a **job** and reply **when the job ends**: `home`, `feed`, `sleeve`,
  `sort`, `eject_reject`. This can take seconds; a first `feed` after `home` raises the
  elevator for up to ~25 s.
- Only one job runs at a time. Another motion command during a job gets `busy` at
  once. Quick commands keep working during a job: poll `status`, change lights, or `estop`.
- Every motion command gets exactly one reply: success, its error, or `estop` if
  aborted.

Suggested host timeouts, with margin over the MCU's own step timeouts: home 60 s, feed 60 s,
sleeve 30 s, sort 15 s, eject_reject 20 s, everything else 2 s.

## Commands

### `ping`
`{"id":1,"cmd":"ping"}` → `{"id":1,"ok":true,"fw":"0.1.0"}`

The simulator reports `"fw":"0.1.0-sim"`.

### `status`
`{"id":2,"cmd":"status"}` →
```json
{"id":2,"ok":true,"state":"idle","homed":true,"hopper_empty":false,"magazine_empty":false,
 "sleeved_card":false,
 "sensors":{"stack_top":true,"double_feed":false,"scan_stop":false,"sleeve_mouth":false,
            "sleeve_present":false,"exit":false,"elev_home":false,"elev_limit":false,
            "pick_home":true,"tongue_home":true,"mag_low":false,"mag_empty":false,"estop":false,
            "lid_open":false},
 "vacuum_kpa":0.4,"lights":{"top":0,"bottom":0}}
```

| Field | Meaning |
|---|---|
| `state` | `unhomed`, `idle`, `homing`, `feeding`, `sleeving`, `sorting`, `ejecting`, `estop` |
| `homed` | Axes referenced. Cleared by e-stop, lid, and by failures that may leave an axis out of place |
| `hopper_empty` | The last `feed` found no card with the elevator at the top, or the elevator is at its limit with no card at `stack_top`. Cleared by `home` or by a card at `stack_top` |
| `magazine_empty` | Sleeve magazine empty sensor |
| `sleeved_card` | A sleeved card waits on the platen for `sort` |
| `sensors` | Every sensor, `true` = active as named. `estop` true = button pressed (or its wire cut). `lid_open` true = lid open (or the I/O expander is lost) |
| `vacuum_kpa` | Vacuum below ambient in kPa, 1 decimal. 0 = none, positive = suction |
| `lights` | Current scan light levels |

`state`, `hopper_empty`, `magazine_empty`, `sensors` and `vacuum_kpa` are the contract
fields. `homed`, `sleeved_card` and `lights` are extras.

### `home`
`{"id":3,"cmd":"home"}` → `{"id":3,"ok":true}`

1. Turns all valves and pumps off.
2. Moves the servos to rest: lift up, pusher rest, diverter bin 0.
3. Homes the tongue, then the pick arm, then the elevator. For each axis it backs off its
   switch if pressed, then seeks the switch at `home_speed`.
4. Zeroes each axis, clears `hopper_empty` and `sleeved_card`.

Use `home` after power-up, after `reset`, after any error that clears `homed`, and to
lower the elevator for a hopper reload.

Errors: `jam` (switch stuck, or not found within the travel), `estop`, `busy`.

### `feed`
`{"id":4,"cmd":"feed"}` → `{"id":4,"ok":true}`

Takes the top card to the scan station:
1. Raises the elevator until `stack_top`.
2. Pulses the stack air knife (`puff_ms`).
3. Opens the pick cup and waits for grip (vacuum ≥ `vac_grip_kpa`).
4. Strokes the pick arm into the rollers while the feed rollers run.
5. Releases the cup and returns the arm.
6. Stops the rollers the moment `scan_stop` trips.

`double_feed` is sampled the whole time. When it replies `ok`, the card sits at the
scan station: turn on `lights`, capture, then `sleeve` or `eject_reject`.

| err | When | Card is | `homed` after |
|---|---|---|---|
| `hopper_empty` | Elevator reached the top with no card at `stack_top`. Also emits event `hopper_empty` (once until cleared) | In the hopper | kept |
| `pick_fail` | Cup did not reach grip vacuum within `vac_timeout_ms` | In the hopper | kept |
| `double_feed` | The gauge saw more than one card. The cards **are** at the scan station: send `eject_reject` | At the scan station | kept |
| `jam` | Card did not reach `scan_stop` within `feed_max_mm` (kept), or an axis timed out (cleared) | Unknown | see left |
| `bad_cmd` | A card is already at the scan station, or a sleeved card still waits on the platen (the next `sort` runs the shared roller loop) | At the scan station / in the hopper | kept |
| `not_homed`, `busy`, `estop` | Preconditions | | |

### `sleeve`
`{"id":5,"cmd":"sleeve"}` → `{"id":5,"ok":true}`

Sleeves the card at the scan station. Every step has a timeout. Step numbers follow the CAD
sleeving sequence (`cad/README.md`).
0. **Sleeve pick**: checks `mag_empty`, then runs the N20 pick wheels until `sleeve_present`
   trips (at most `sleeve_pick_ms`), keeps them on for `sleeve_push_ms` more, then brakes. The
   bottom sleeve leaves the magazine through the 0.14 mm gate and slides onto the platen, flush
   against the fence (platen vacuum off). Skipped
   when the sleeve picked by an earlier `sleeve` passed step 1 but was not used (e.g. that
   `sleeve` failed at the lift cup).
1. Vacuum pump and platen valve on. Waits for grip: only a sleeve covering every platen hole
   reaches `vac_grip_kpa`, so this is the second "sleeve in place" check after `sleeve_present`.
2. Lift servo down, lift-cup valve on, waits for grip, lift servo up: the sleeve mouth opens.
   Checks the grip again.
3. Mouth jet pulse (`jet_ms`).
4. Tongue extends `tongue_depth_mm`.
5. Feed runs until `sleeve_mouth` trips, then `insert_mm` more. The card leaves the entry nip
   ~70 mm into the sleeve; the gravity pawl lifts over it and drops behind its trailing edge.
6. **Seat**: pusher to `pusher_seat_deg` (pawl −20 → +0.3 mm), waits `servo_ms` +
   `pusher_seat_ms`. The card is fully in. The pawl stays there and holds the card while:
7. Tongue retracts.
8. Lift cup, platen and pump off. The sleeved card rests on the platen (`sleeved_card`), pawl
   at the seat angle.

| err | When | `homed` after |
|---|---|---|
| `magazine_empty` | Magazine empty sensor active and no unused sleeve on the platen (checked before the pick wheels run) | kept |
| `sleeve_open_fail` | `sleeve_present` did not trip within `sleeve_pick_ms` (wheels slipped, or misfeed), no platen grip (sleeve askew, or a leak), the lift cup did not seal, or it lost the ply on the way up | kept (card still at the scan station). After a lift-cup failure the sleeve stays on the platen and the next `sleeve` reuses it |
| `sleeve_insert_fail` | Tongue timeout, or `sleeve_mouth` never tripped within `insert_max_mm` | **cleared**: the tongue may be inside the sleeve. Clear the station: the next `sleeve` picks a fresh sleeve |
| `bad_cmd` | No card at the scan station, or a sleeved card still on the platen | kept |
| `not_homed`, `busy`, `estop` | Preconditions | |

### `sort`
`{"id":6,"cmd":"sort","bin":1}` → `{"id":6,"ok":true,"bin":1}`

1. Moves the diverter to the bin (`div<bin>_deg`) and waits `servo_ms`.
2. Swings the pusher out to `pusher_out_deg` (pawl from the seat angle, or rest, to +36 mm: the
   closed end of the sleeve 7 mm into the exit nip) and runs the feed loop, which drives the exit
   rollers (up to `feed_max_mm`).
3. Waits for the `exit` beam to trip, then to clear. Stops the rollers.
4. Parks the pusher (`pusher_rest_deg`).

`bin` must be the integer 0, 1 or 2.

| err | When |
|---|---|
| `exit_timeout` | `exit` did not trip within `exit_timeout_ms` of the push |
| `jam` | `exit` stayed blocked for `exit_timeout_ms` |
| `bad_cmd` | Bad or missing `bin`, or a card at the scan station (the exit rollers share the feed loop and would carry it along: `sleeve` or `eject_reject` it first) |
| `not_homed`, `busy`, `estop` | Preconditions |

`sort` does not require `sleeved_card`. With nothing on the platen it fails with
`exit_timeout`. On failure the pusher is parked again and the rollers stop.

### `eject_reject`
`{"id":7,"cmd":"eject_reject"}` → `{"id":7,"ok":true,"bin":2}`

Sends the card(s) at the scan station to bin 2 **without sleeving**, e.g. after
`double_feed`:
1. Diverter to bin 2.
2. Feed runs `reject_mm`, which carries the card onto the platen.
3. Push and wait for exit, as in `sort`.

Errors:
- `jam`: the card is still on `scan_stop` after the feed, or a feed timeout.
- `exit_timeout`
- `bad_cmd`: no card at the scan station, or a sleeved card on the platen (sort it first).
- `not_homed`, `busy`, `estop`

### `lights`
`{"id":8,"cmd":"lights","top":255,"bottom":120}` → `{"id":8,"ok":true,"top":255,"bottom":120}`

Sets the scan light PWM, integers 0-255. A field left out keeps its current value.
Errors: `bad_cmd`. Works in any state, including e-stop.

### `set` / `get`
`{"id":9,"cmd":"set","key":"feed_speed","value":180}` → `{"id":9,"ok":true,"key":"feed_speed","value":180}`

`{"id":10,"cmd":"get","key":"feed_speed"}` → `{"id":10,"ok":true,"key":"feed_speed","value":180}`

- `value` must be a JSON number within the key's range. Integer keys reject fractions.
- `set` writes NVS immediately, and the value survives reboots.
- `cur_*` keys are applied to the drivers at once.
- `set` is allowed during a job. Most keys take effect at the next phase or the next job.

Errors: `bad_cmd` for an unknown key, a non-number value, or a value out of range.

| Key | Default | Range | Unit | What |
|---|---|---|---|---|
| `accel` | 1500 | 50-20000 | mm/s² | All axes |
| `home_speed` | 10 | 1-50 | mm/s | Homing seek, all axes |
| `elev_speed` | 6 | 0.5-30 | mm/s | Stack raise |
| `elev_max_mm` | 150 | 10-400 | mm | Elevator travel |
| `pick_speed` | 120 | 5-400 | mm/s | |
| `pick_travel_mm` | 30 | 5-150 | mm | Pick stroke: stack → roller nip (leading edge 8 mm into the feed nip) |
| `feed_speed` | 150 | 5-600 | mm/s | Feed + reject |
| `feed_max_mm` | 220 | 20-600 | mm | `feed` → `jam` if `scan_stop` not hit |
| `insert_speed` | 80 | 5-400 | mm/s | Sleeve insert |
| `insert_mm` | 70 | 0-200 | mm | Feed past `sleeve_mouth` |
| `insert_max_mm` | 200 | 10-400 | mm | `sleeve_insert_fail` if `sleeve_mouth` not hit (scan stop → mouth sensor is 168 mm) |
| `reject_mm` | 240 | 10-400 | mm | `eject_reject` feed distance: the trailing edge must pass the sleeve entry nip (232 mm) so the pawl drops behind it |
| `tongue_speed` | 60 | 2-200 | mm/s | |
| `tongue_depth_mm` | 18 | 1-80 | mm | Tongue stroke (tips −3 → +15) |
| `cur_elev` `cur_pick` `cur_feed` `cur_tongue` | 800 / 600 / 600 / 500 | 100-1800 | mA RMS, integer | TMC2209 run current (hold = 50 %) |
| `vac_grip_kpa` | 25 | 0-95 | kPa | Grip threshold. **0 = no sensor: skip grip checks** |
| `cup_dwell_ms` | 250 | 0-5000 | ms, integer | Minimum cup-open time before checking |
| `vac_timeout_ms` | 1500 | 50-20000 | ms, integer | Grip timeout (at least `cup_dwell_ms` + 100) |
| `puff_ms` | 150 | 0-5000 | ms, integer | Stack air knife pulse, 0 = off |
| `jet_ms` | 120 | 0-5000 | ms, integer | Mouth jet pulse |
| `sleeve_pick_ms` | 400 | 20-5000 | ms, integer | Max sleeve pick wheel run while waiting for `sleeve_present`. Too short: `sleeve_open_fail` before a slow sleeve arrives |
| `sleeve_push_ms` | 60 | 0-2000 | ms, integer | Pick wheels keep running this long after `sleeve_present` (it trips 1.5–3.4 mm short of the fence) |
| `servo_ms` | 350 | 50-5000 | ms, integer | Servo settle time |
| `lift_down_deg` `lift_up_deg` | 35 / 110 | 0-180 | deg, integer | Lift servo |
| `pusher_rest_deg` `pusher_out_deg` | 10 / 160 | 0-180 | deg, integer | Pusher servo: pawl −20 mm (rest) / +36 mm (sort: into the exit nip) |
| `pusher_seat_deg` | 65 | 0-180 | deg, integer | Pusher at pawl +0.3 mm: seats the card in the sleeve (`sleeve` step 6). Keep below the out angle |
| `pusher_seat_ms` | 400 | 0-5000 | ms, integer | Dwell at the seat angle (after `servo_ms`) before the tongues retract |
| `div0_deg` `div1_deg` `div2_deg` | 48 / 90 / 132 | 0-180 | deg, integer | Diverter per bin (tray on the servo spline, CAD −42° / 0° / +42°) |
| `exit_timeout_ms` | 3000 | 100-60000 | ms, integer | Push → exit trip, and trip → clear |

### `estop`
`{"id":11,"cmd":"estop"}` → `{"id":11,"ok":true}`

Software e-stop:
- Stops all axes without ramps and disables the drivers.
- Turns all valves and pumps off. Servos stay where they are.
- A running job replies `estop` first, then this command gets its `ok`.
- Emits `{"evt":"estop","source":"cmd"}`.
- `state` becomes `estop` and `homed` false. Motion commands get `estop` until `reset`.

### `reset`
`{"id":12,"cmd":"reset"}` → `{"id":12,"ok":true,"state":"unhomed"}`

Leaves the e-stop state once the hardware is safe, and re-enables the drivers. Then `home`.
Outside e-stop it just reports the state.

| err | When |
|---|---|
| `estop` | The e-stop button is still pressed (`msg` "e-stop button still pressed"), or the lid is open (`msg` "lid open") |
| `busy` | A job is running. Use `estop` to abort it |

`reset` does not reboot the MCU.

## Events

| Event | When |
|---|---|
| `{"evt":"estop","source":"input"}` | E-stop input went active (debounced 20 ms). Also at boot if it is pressed |
| `{"evt":"estop","source":"cmd"}` | `estop` command |
| `{"evt":"lid_open"}` | Lid opened (debounced 20 ms). Same effect as an e-stop: state `estop`, `reset` needed after closing |
| `{"evt":"hopper_empty"}` | `feed` found the hopper empty. Once until `home` or a card is found |
| `{"evt":"magazine_low"}` | Magazine-low sensor went active. Once per transition |

Events can arrive at any time, including between a request and its reply. Match replies
by `id`, never by order.

## Error codes

| `err` | Meaning |
|---|---|
| `hopper_empty` | No card to pick |
| `magazine_empty` | No sleeves |
| `double_feed` | More than one card at the scan station |
| `pick_fail` | Pick cup could not grip |
| `jam` | A card or axis did not arrive in time, or a home switch is wrong |
| `sleeve_open_fail` | Could not hold/open the sleeve |
| `sleeve_insert_fail` | Could not insert the card |
| `exit_timeout` | Card did not pass the exit beam |
| `estop` | E-stop/lid active, or the job was aborted by it |
| `not_homed` | Send `home` first |
| `busy` | A job is running |
| `bad_cmd` | Malformed line, unknown command/key, bad argument, wrong machine state for the command |

On any job failure the MCU stops all axes, turns all valves and pumps off and parks the
pusher.

## Typical host loop

```
home
lights {top,bottom}
loop:
  feed
    ok           -> capture, recognise -> sleeve -> sort {bin}
    double_feed  -> eject_reject
    hopper_empty -> tell the user; lights off; wait; home (lowers the elevator) to reload
    pick_fail    -> retry feed (a few times), then ask the user
  sleeve
    sleeve_open_fail   -> retry sleeve once, else eject_reject
    sleeve_insert_fail -> home, ask the user to clear the station
  sort
    exit_timeout / jam -> ask the user to clear the chute, then home
any `estop` reply/event -> stop the loop; after the user clears it: reset, home
```

## Simulator control (sim only)

`tools/mcu_sim.py` accepts extra lines starting with `#`, for host fault-injection tests.
They are acknowledged on the sim's stderr, never on the protocol stream:

| Line | Effect |
|---|---|
| `#estop 1` / `#estop 0` | Press / release the e-stop |
| `#lid 1` / `#lid 0` | Open / close the lid |
| `#hopper N` | Cards in the hopper |
| `#sleeves N` | Sleeves in the magazine |
| `#double P` `#pick-fail P` `#lift-fail P` `#exit-miss P` `#sleeve-pick-fail P` | Fault probabilities, 0-1 |
| `#state` | Print the sim counters (bins, sleeves, hopper) to stderr |

The real firmware treats these lines as malformed JSON (`bad_cmd`, id -1).
