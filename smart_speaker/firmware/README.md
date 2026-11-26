# Round speaker firmware (ESP32)

PlatformIO / Arduino firmware for the round smart speaker:
- ESP32-WROOM-32 30-pin devkit
- MAX98357A amplifier
- 2× INMP441 microphones
- WS2812B halo ring

It is a network voice endpoint for a custom hub. Wake word, speech-to-text
and text-to-speech all run on the hub.

- Wiring: [`../electronics/WIRING.md`](../electronics/WIRING.md)
- Protocols for the hub and the USB settings link: [`PROTOCOL.md`](PROTOCOL.md)
- Test hub: [`tools/hub_test.py`](tools/hub_test.py)
- No hardware yet? [`tools/mock_speaker.py`](tools/mock_speaker.py) implements the same protocol in Python, so you can build the hub against it

## Build and flash

```bash
pip install platformio
cd firmware
pio run -t upload          # first flash over USB-C
pio device monitor         # 115200 baud
```

Later updates can go over Wi-Fi:

```bash
pio run -t upload --upload-port roundspk-xxxx.local
```

If you set a token, add `--upload-flags --auth=<token>`.

A token set while the speaker is running only applies to OTA after a restart.

## Release image for the website

```bash
pip3 install --target .pydeps platformio   # from the repo root
python3 smart_speaker/firmware/tools/build_release.py
```

This builds the firmware, merges it into one image flashed at offset 0, checks
the source and image for secrets, and writes the image with its manifest to
`lumen-house/public/firmware/speaker/`. It doesn't commit anything.

**Installing that image erases the speaker's settings and Wi-Fi, even as an
update.** NVS sits at `0x9000`, between the partition table and `boot_app0`, so a
merged image fills it with `0xFF`. To keep them, update over USB with `pio run -t
upload` or over Wi-Fi with OTA.

## Tests

```bash
python3 tools/run_native_tests.py
```

These run the serial protocol, settings validation and Improv handling on your
PC with g++. No ESP32 is needed, but run `pio pkg install` once first for the
libraries.

## Settings

Settings are stored in flash and are the same firmware for everyone. Set them
from the web page over USB (see [`PROTOCOL.md`](PROTOCOL.md#settings-protocol-v1)),
and from the hub or the setup portal where noted:

| Setting | USB | Hub | Portal | Default |
|---|---|---|---|---|
| Device name | yes | `config` | yes | `roundspk-xxxx` |
| Hub token (write-only) | yes | `config` | set only | none |
| LED count, 1–300 | yes | no | no | 39 |
| LED max brightness | yes | `led_max` | no | 150 |
| Volume | no | `volume` | no | 60 % |

Devices already in use keep their name, token, volume and brightness when
updated over USB or OTA, because the storage keys haven't changed.

## Wi-Fi setup

There are two ways in:

- **USB (Improv):** always available. Use the install page's Wi-Fi step, or any
  Improv Serial client.
- **Phone (portal):** the `roundspk-xxxx-setup` access point described below, open
  when there's no saved network or the saved one can't be reached.

The network code runs from `loop()` and doesn't block, so USB requests keep being
answered while the speaker connects and while the portal waits. The exception is
the portal's own connection attempt after you submit its form. That blocks for up
to 20 s, and USB requests wait in a 2 KB buffer until it ends. A browser opening
Improv in that window may report that it can't detect the device; try again.
Closing the portal also takes about a second.

WiFiManager's `autoConnect()` isn't used, because it blocks during the saved
network attempt. The speaker tries the saved network itself for 20 s, then opens
the portal.

When the portal times out the speaker reboots and tries again, unless the USB
link has been used in the last 60 s. Then it reopens the portal instead, so a
browser session isn't cut off.
## First boot

1. The ring shows a white comet while booting.
2. With no saved Wi-Fi, the ring breathes amber and the ESP32 opens an access
   point named `roundspk-xxxx-setup`. Connect to it and the setup page opens.
   Pick your network, and optionally set a device name and a hub token. The token
   field is always blank and leaving it blank keeps the current token. If
   nothing happens for 3 minutes, it reboots and tries again.
3. Once connected, the ring breathes dim blue (idle). The serial log prints
   `ready: ws://<ip>:8080/`.

## Try it before the hub exists

```bash
pip install websockets zeroconf
cd firmware/tools
python3 hub_test.py discover
python3 hub_test.py tone   --host roundspk-xxxx.local          # speaker check
python3 hub_test.py record --host roundspk-xxxx.local --stereo # writes mic.wav
python3 hub_test.py loop   --host roundspk-xxxx.local          # record, then play back
python3 hub_test.py led    --host roundspk-xxxx.local --mode rainbow
```

In a stereo recording, left is the mic with L/R tied to GND. If both
channels are silent, check the shared SD line and its 100 kΩ pull-down. If one
channel is silent, check that mic's L/R pin.

## Tuning

| Setting | Where | Default |
|---|---|---|
| Mic gain | `mic` command `gain_db` / `MIC_GAIN_DB_DEFAULT` | +12 dB |
| LED power cap | USB `led_max_brightness` / `led_max` command / `LED_MAX_BRIGHTNESS_DEFAULT` | 150 (≈60 %). Use about 64 on USB-only power. |
| LED power budget | `LED_POWER_BUDGET_MA` in `include/config.h` | 1800 mA, which limits brightness to 196 at 39 LEDs and 25 at 300 |
| Volume | `volume` command (saved to flash) | 60 % |
| Number of LEDs | USB `led_count` / `LED_COUNT_DEFAULT` | 39 |
| Pins | `include/config.h` | match `WIRING.md` |

## Design notes

- Mic, speaker and LED rendering each run in their own FreeRTOS task on
  core 1. Wi-Fi runs on core 0. The WebSocket library is only touched from
  `loop()`.
- The mics run at 16 kHz with 24-bit samples and a DC-blocking high-pass
  filter. Output is 16-bit mono (L+R)/2, or stereo for beamforming on the hub.
- Speaker input is mono PCM at 8–48 kHz, with a 32 KB ring buffer and a
  square-law volume curve. On an underrun the I2S output goes silent, so
  there's no buzzing.
- There is no echo cancellation on the device. Use `duck`, or run AEC on the hub.
- Security: on a shared network, set a token. Without one, anyone on the
  LAN can use the mic. The token also protects OTA updates.
- The token and Wi-Fi password can't be read back through any protocol, the portal
  or the logs. They are stored unencrypted in flash, though, so anyone with
  physical USB access can dump them with esptool. The setup portal's access point
  is also open, so a token typed there isn't protected over the air. USB is the
  better way to set one.
