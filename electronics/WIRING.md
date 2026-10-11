# Round smart speaker – wiring

Voice-assistant node (Echo Dot / HomePod mini / Nest style) for the round
folded-port enclosure in `../round_sub/`. It talks to the (future) custom hub
over Wi-Fi; nothing here assumes a particular hub protocol.

Diagram: [`wiring.svg`](wiring.svg) (regenerate with `python3 wiring.py`).

## Parts (dimensions verified against the listings)

| Part | ASIN | Qty | Size used in the enclosure |
|---|---|---|---|
| Hosyond ESP32-WROOM-32 devkit, **30-pin**, CP2102, USB-C | B0F1MS5S8R | 1 | 51 x 28 mm, pins pre-soldered pointing down; sits on 20 mm ledges (room for Dupont plugs underneath) |
| MAX98357A I2S 3 W class-D amp (Teyleten) | B0B4GK5R1R | 1 | 18.0 x 20.1 mm; 7-pin header + screw terminal; sits on a 10 mm platform with the header edge hanging off |
| INMP441 I2S MEMS mic, round | B0C1C64R8S | 2 | 14 mm diameter (listing drawing); sound hole centred |
| WS2812B 5 V strip, 60 LED/m, IP67 | B0CFTLZTHR | ~642 mm (39 LEDs) | ~12 mm wide tube in a 13 mm channel; JST-SM lead passes a 12 x 7 mm slot |
| Gikfun 2" 4 ohm 3 W driver EK1725 | B01CHYIU26 | 1 | 52.6 mm square frame, holes on a 42 mm square, 50.8 mm surround, 30 mm deep, 39.5 mm magnet (listing drawing) |
| 5 V 3 A supply (barrel jack or USB-C PD trigger) | - | 1 | |
| 330 ohm resistor (LED data) | - | 1 | |
| 100 kohm resistor (mic SD pull-down) | - | 1 | |
| 1000 uF >=10 V electrolytic (LED supply) | - | 1 | |
| 74AHCT125 level shifter (only if LEDs flicker) | - | optional | |

Collision check of all of the above against the printed parts:
`cd ../round_sub && PYTHONPATH=../.pydeps python3 check_fit.py`

## Pin map

| ESP32 | Goes to | Notes |
|---|---|---|
| VIN / 5V | 5 V rail: amp VIN, LED +5V, supply + | power the board through VIN from the 5 V supply |
| 3V3 | both INMP441 VDD, right mic L/R | 3.3 V only – never 5 V to the mics |
| GND | everything's GND | one common ground |
| GPIO25 | MAX98357A LRC | I2S0 (speaker) word select |
| GPIO26 | MAX98357A BCLK | I2S0 bit clock |
| GPIO22 | MAX98357A DIN | I2S0 data out |
| GPIO32 | both INMP441 SCK | I2S1 (mics) bit clock |
| GPIO33 | both INMP441 WS | I2S1 word select |
| GPIO35 | both INMP441 SD | I2S1 data in (input-only pin), 100 kΩ to GND |
| GPIO27 | 330 Ω → WS2812B DIN | LED data |

No strapping pins (0, 2, 5, 12, 15) are used, so the board always boots cleanly.

### Mics

| INMP441 pin | Left mic | Right mic |
|---|---|---|
| VDD | 3V3 | 3V3 |
| GND | GND | GND |
| SCK | GPIO32 | GPIO32 |
| WS | GPIO33 | GPIO33 |
| SD | GPIO35 | GPIO35 |
| L/R | **GND** (left slot) | **3V3** (right slot) |

Both mics share one I2S bus; each drives SD only in its own half of the frame.
Read the bus as 32-bit stereo to get both channels (useful for beamforming /
noise suppression), or as mono-left to use just one.

### Amp

| MAX98357A pin | Connect |
|---|---|
| VIN | 5 V |
| GND | GND |
| LRC / BCLK / DIN | GPIO25 / GPIO26 / GPIO22 |
| GAIN | leave unconnected = 9 dB |
| SD | leave unconnected = mono (L+R)/2 |
| OUT+ / OUT− | speaker + / − |

At 5 V into 4 Ω the amp gives ~3 W, matching the driver. Never connect either
speaker output to GND.

## Power budget (5 V)

| Load | Typical | Peak |
|---|---|---|
| ESP32 (Wi-Fi active) | 0.15 A | 0.35 A |
| MAX98357A + driver | 0.2 A | 0.8 A |
| 39× WS2812B | 0.05 A (dim) | 2.3 A (full white) |
| **Total** | **~0.4 A** | **~3.4 A** |

- **Recommended:** a 5 V 3 A supply into the 5 V rail, with LED brightness
  capped at about 60% in firmware.
- **USB-C only:** works if LED brightness is capped at about 25%. Most devkits
  have a diode on USB 5 V, so plugging USB in for flashing while the external
  supply is on is safe. Check yours.
- Put the 1000 µF capacitor at the strip's +5V/GND entry.

## Routing through the enclosure

| Cable | Path |
|---|---|
| Speaker leads | chamber → 8 mm hole in the body floor centre → bay. Seal the hole with hot glue after wiring. |
| LED strip lead | halo band under the cone → 12 x 7 mm slot in the base wall (200°, JST-SM plug fits through) → bay |
| Mics | live in the side-wall pockets (90° / 270°), wires go straight into the bay |
| 5 V input | 8 mm aux hole in the base wall (150°) |
| USB-C | ESP32 USB end faces the slot at 0° (points down when wall mounted) |

Keep the mic wires away from the amp output and LED data. Twist each mic's
SCK/WS/SD with a ground wire if any lead is longer than ~15 cm.

## LED data level

GPIO27 outputs 3.3 V, but WS2812B at 5 V expects a high level of about 3.5 V.
Most strips still work with a short lead and the 330 Ω resistor. If the first
LED flickers or shows wrong colours, add a 74AHCT125 powered from 5 V between
GPIO27 and DIN.
