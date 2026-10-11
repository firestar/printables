# Round speaker firmware (ESP32)

PlatformIO / Arduino firmware for the round smart speaker:
- ESP32-WROOM-32 30-pin devkit
- MAX98357A amplifier
- 2× INMP441 microphones
- WS2812B halo ring

It is a network voice endpoint for a custom hub. Wake word, speech-to-text
and text-to-speech all run on the hub.

- Wiring: [`../electronics/WIRING.md`](../electronics/WIRING.md)
- Protocol for the hub: [`PROTOCOL.md`](PROTOCOL.md)
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

## First boot

1. The ring shows a white comet while booting.
2. With no saved Wi-Fi, the ring breathes amber and the ESP32 opens an access
   point named `roundspk-xxxx-setup`. Connect to it and the setup page opens.
   Pick your network, and optionally set a device name and a hub token. If
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
| LED power cap | `led_max` command / `LED_MAX_BRIGHTNESS_DEFAULT` | 150 (≈60 %). Use about 64 on USB-only power. |
| Volume | `volume` command (saved to flash) | 60 % |
| Number of LEDs | `NUM_LEDS` in `include/config.h` | 39 |
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
