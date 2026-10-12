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
| `led_max` | `value` 0–255 | power cap on brightness, saved → `state` |
| `config` | `name`, `token` | saved. Changing the token reboots the speaker (the OTA password follows the token) |
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
`led {mode, color, brightness, max, count}`.

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
