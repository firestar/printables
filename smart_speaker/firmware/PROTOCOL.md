# Round speaker protocols

This file has the hub protocol (v1) and, [further down](#usb-serial-improv-and-settings), the USB serial protocols used by the browser.

# Round speaker ↔ hub protocol (v1)

The speaker is a **WebSocket server**; the hub connects to it. One hub at a
time. A new connection replaces the old one.

## Discovery

mDNS service `_roundspk._tcp`, port `8080`. TXT records:

| key | value |
|---|---|
| `id` | `roundspk-xxxx` (stable, from MAC) |
| `name` | friendly name |
| `fw` | firmware version |
| `auth` | `1` if a token is required |

Endpoint: `ws://<ip or roundspk-xxxx.local>:8080/`

## Framing

- **Text frames** carry JSON objects with a `"type"` field.
- **Binary frames**: the first byte is the frame type, and the rest is audio.

| byte 0 | direction | payload |
|---|---|---|
| `0x01` | speaker → hub | mic audio, PCM 16-bit little-endian, 16 kHz, 1 ch (or 2 ch interleaved L,R) |
| `0x02` | hub → speaker | speaker audio, PCM 16-bit little-endian, mono, at the rate set by `play_start` |

Mic frames carry 512 samples per channel (32 ms). Keep speaker frames at
**4096 bytes or less** each.

## Session

1. Hub connects. The speaker sends `hello`.
2. If `hello.auth_required` is true, the hub must send
   `{"type":"hello","token":"…"}` within 5 s. Otherwise the speaker sends
   `error` and disconnects. If no token is set, the hub may still send
   `hello`; it is answered with `ready`.
3. The speaker answers `ready` with its full state.
4. While connected, the speaker sends `status` every 5 s. It also sends WebSocket
   pings; dead connections are dropped after about 20 s.

## Hub → speaker commands

| type | fields | effect / reply |
|---|---|---|
| `hello` | `token` | authenticate → `ready` |
| `ping` | `id`? | → `pong {id, t}` |
| `get_state` | | → `state` |
| `mic` | `enable` bool, `channels` 1/2, `gain_db` −20..40, `duck` bool | start/stop mic streaming. With `duck` set, mic frames are dropped while audio is playing (no echo canceller on the device). → `state` |
| `play_start` | `rate` 8000–48000 | prepare playback (flushes if the rate changes) → `play_ready {rate, free}` |
| *(binary `0x02` frames)* | | audio data |
| `play_end` | | no more data. The speaker plays out its buffer, then sends `play_done {stopped:false}` |
| `stop` | | flush immediately → `play_done {stopped:true}` |
| `volume` | `value` 0–100 | saved to flash → `state` |
| `led` | `mode`, `color` `[r,g,b]` or `"#rrggbb"`, `brightness` 0–255 | → `state` |
| `led_max` | `value` 0–255 | power cap on brightness, saved → `state`. The power budget can lower what's actually applied; see `led.max_effective` |
| `config` | `name` (1–32 bytes), `token` (up to 64 bytes) | saved, all or nothing: printable UTF-8 only, otherwise `error` and no change. Changing the token reboots the speaker (the OTA password follows the token) |
| `wifi_reset` | | forget Wi-Fi and reboot into the setup portal |
| `reboot` | | |

LED modes: `off`, `idle`, `listening` (follows mic level), `thinking`,
`speaking` (follows output level), `error`, `solid`, `rainbow`. The speaker
also uses `boot` and `setup` itself.

## Speaker → hub messages

| type | when | fields |
|---|---|---|
| `hello` | on connect | `auth_required`, state |
| `ready` / `state` / `status` | after auth / on change / every 5 s | state, plus `rssi`, `uptime_s`, `heap`, `spk_overflow` |
| `play_ready` | reply to `play_start` | `rate`, `free` |
| `play_buffer` | every 100 ms while audio is queued | `free`, `queued` (bytes) |
| `play_done` | buffer drained after `play_end`, or `stop` | `stopped` |
| `pong` | reply to `ping` | `id`, `t` (ms since boot) |
| `error` | | `msg` |
| `rebooting` | | |

**State object:** `name`, `id`, `fw`, `volume`,
`mic {enabled, rate, bits, channels, gain_db, duck}`,
`spk {rate, bits, channels, buffer, queued}`,
`led {mode, color, brightness, max, max_effective, count}`. `max` is the stored
cap, and `max_effective` is what the power budget allows at this LED count.

## Playback flow control

The speaker's buffer is 32 KB (about 1 s at 16 kHz). The hub should:

1. Send `play_start {rate}` and wait for `play_ready`.
2. Send chunks of 4096 bytes or less, keeping the total in flight below the last
   reported `free`. Use `play_buffer` to pace. A simple approach is to send in
   real time plus about 300 ms of lead.
3. Send `play_end` and wait for `play_done`.

Data that doesn't fit in the buffer is dropped and counted in `spk_overflow`.

## Typical voice turn (wake word on the hub)

```
hub → {"type":"mic","enable":true}
      {"type":"led","mode":"idle"}
spk → 0x01 frames continuously … hub runs wake word / VAD
hub → {"type":"led","mode":"listening"}            (wake word heard)
      … hub runs STT until end of speech …
hub → {"type":"led","mode":"thinking"}
hub → {"type":"play_start","rate":22050}
spk → {"type":"play_ready",…}
hub → {"type":"led","mode":"speaking"}  + 0x02 frames … {"type":"play_end"}
spk → {"type":"play_done","stopped":false}
hub → {"type":"led","mode":"idle"}
```

There is no echo canceller on the device. Either use `duck` during
playback, or run acoustic echo cancellation on the hub, using the audio it
sent as the reference.

# USB serial: Improv and settings

The USB port runs at **115200 baud, 8N1**. Three things share it: log output,
[Improv Serial](https://www.improv-wifi.com/serial/) for Wi-Fi setup (driven by
ESP Web Tools), and the JSON settings protocol below. Wi-Fi credentials only go
over Improv.

## Sharing the port

**To the device.** Bytes are sorted as they arrive:

- An Improv packet is recognised anywhere by its 7-byte signature, `IMPROV` plus
  version `0x01`. Valid JSON can't contain that sequence, because a raw `0x01`
  isn't allowed in it, so a name like `IMPROV` is safe. Packets are framed by
  their length byte, so newlines and braces inside one are just data.
- Everything else is split into lines on `\n`, with a trailing `\r` removed.
  Lines not starting with `{` are ignored, as are `{` lines with no `lumen` key.
- A partial line or packet is dropped after **1 s** with no bytes, so a truncated
  packet can only swallow what follows for that long. Paste into a terminal
  rather than typing by hand.
- Lines are limited to **1024 bytes**. A longer `{` line gets a `line too long`
  error when its newline arrives; a longer log line is dropped silently.

**From the device.** Every Improv packet and JSON reply has a newline on both
sides, sent in one write. The Improv browser client only recognises a packet at
the start of a line, and the settings form only reads lines starting with `{`.
So after a log line that was cut short, the next packet or reply is still read.

## Settings protocol (v1)

One JSON object per line. Every request has `"lumen":1` and an integer `id`.

| Request | Reply |
|---|---|
| `{"lumen":1,"id":1,"cmd":"info"}` | `{"id":1,"ok":true,"project":"speaker","fw":"0.1.0","schema":1}` |
| `{"lumen":1,"id":2,"cmd":"get"}` | `{"id":2,"ok":true,"settings":{"name":"Kitchen","led_count":39,"led_max_brightness":150,"token_set":true}}` |
| `{"lumen":1,"id":3,"cmd":"set","settings":{"led_count":60}}` | `{"id":3,"ok":true,"restart":false}` or `{"id":3,"ok":false,"error":"led_count out of range"}` |
| `{"lumen":1,"id":4,"cmd":"erase"}` | `{"id":4,"ok":true}`, then it restarts by itself about 1 s later |
| `{"lumen":1,"id":5,"cmd":"restart"}` | `{"id":5,"ok":true}`, then it restarts |

| Setting | Type | Limits | Default | NVS key | Takes effect |
|---|---|---|---|---|---|
| `name` | string | 1–32 bytes | `roundspk-xxxx` | `name` | now |
| `token` | string, write-only | 0–64 bytes; empty clears it | none | `token` | hub auth now; OTA password after a restart |
| `led_count` | integer | 1–300 | 39 | `led_count` | next frame |
| `led_max_brightness` | integer | 0–255 | 150 | `led_max` | next frame |

Rules:

- **The token is never returned**, only `token_set`. It's never logged or
  repeated in an error, either.
- `set` takes any subset of the keys and is all or nothing: one bad value, or an
  unknown key (including `token_set`), rejects the whole request. Numbers must
  be JSON integers and strings must be printable UTF-8. Limits are in bytes, so
  32 `é` won't fit in `name`.
- `restart` is `true` only when the token changed. Nothing is written if nothing
  changed.
- `erase` clears every stored setting (including volume) and the saved Wi-Fi
  network. The speaker restarts by itself because it has no network left, and a
  `restart` sent straight after is still fine.
- Errors: a line that can't be parsed gets `bad json`, with the `id` recovered
  from the text if possible and `null` otherwise. Also `unknown command`,
  `unsupported protocol version`, `id must be an integer`, `line too long`,
  `storage write failed` and `storage erase failed`.
- Saves roll back if a write fails. NVS has no transaction across keys, so a
  power cut in the middle of a save can leave only some keys written. Each one is
  still valid on its own.

The limit in `led_max_brightness` is what you ask for. The firmware also keeps
full white at this LED count inside a 1.8 A budget for the 5 V 3 A supply, so a
higher setting can be stored but not reached: at most 196 at 39 LEDs and 25 at
300. It can't tell what's powering it, so on USB only, set about 64 yourself.

## Improv Serial

Implements Improv Serial v1 with the official C++ SDK.

| RPC | Reply |
|---|---|
| `0x01` Wi-Fi settings | state Provisioning, then state Provisioned and an empty result (there's no URL, because the speaker has no web page), or error `0x03` and state Ready after 20 s |
| `0x02` current state | state; if provisioned, also an empty result |
| `0x03` device info | `Round speaker`, firmware version, `ESP32`, device name |
| `0x04` scan | one result per network (SSID, RSSI, `YES`/`NO`), then an empty result. The list is empty if the scan failed. |
| others | error `0x02`, which the spec allows for optional commands |

Improv works at all times, including while the setup portal is open. New
credentials close the portal. If they fail, the previous network is put back, or
the portal reopens if there wasn't one. See [README.md](README.md#wi-fi-setup).
