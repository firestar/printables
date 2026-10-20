# Reader ↔ controller link protocol

The outdoor reader and the indoor controller talk over one RS-485 pair
(half duplex, 115200 8N1 by default, `LINK_BAUD` in `include/config.h`).
Every frame is authenticated with HMAC-SHA256 and carries a counter that
must keep going up, so frames cannot be forged or replayed from the cable.

This link exists only in split mode (`reader` / `reader_nofp` + `controller`). The all-in-one
builds have no RS-485 link.

The protocol code is platform independent: `lib/mb_protocol` (C++, used by
both firmwares and the native tests) and `tools/mbproto.py` (Python, same
rules). `tools/gen_vectors.py` writes `test/test_protocol/vectors.h` from the
Python encoder; the C++ test must produce the same bytes.

## Frame

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 1 | `SOF` | `0xA5` |
| 1 | 1 | `LEN` | payload length, 0–32 |
| 2 | 1 | `SRC` | sender: `'R'` (0x52) reader, `'C'` (0x43) controller |
| 3 | 1 | `TYPE` | message type, below |
| 4 | 4 | `CTR` | sender's counter, little endian |
| 8 | LEN | payload | little endian fields |
| 8+LEN | 16 | `TAG` | first 16 bytes of HMAC-SHA256(key, bytes 0 … 8+LEN−1) |

Frame size is 24–56 bytes (2–5 ms on the wire at 115200).

The key is 32 random bytes shared by both boards (`LINK_KEY_HEX` in
`include/secrets.h`, written by `tools/provision.py`). Tags are compared in
constant time.

### Receiving

1. Bytes go into a streaming decoder. If byte 0 isn't `SOF`, skip to the next `0xA5`.
2. `LEN > 32`: drop one byte and rescan.
3. Wait for `8 + LEN + 16` bytes. Then check the tag. On a bad tag, drop one byte and rescan.
   So a stray `0xA5` in noise, or inside another frame, cannot eat a real frame.
4. If the line is quiet for more than 20 ms in the middle of a frame, the partial frame is dropped.
5. `SRC` must be the peer. Our own `SRC` means an echo or reflection, and the frame is rejected.
6. Counter check: accept only if `last < CTR <= last + 2^20`.
   - `CTR <= last` is a **replay**.
   - A jump of more than 2^20 is **out of window**.
   - Rejected frames are counted. The controller publishes the count as `link_errors`.
     `LINK_ERROR_ALERT` (20) or more rejections in a minute raises the tamper sensor.

### Counters

Each direction has its own counter, stored in NVS namespace `mblink`.

| Key | Owner | Meaning |
|---|---|---|
| `tx_r` / `tx_c` | reader / controller | Upper bound already reserved for its own frames |
| `rx_c` / `rx_r` | reader / controller | Highest counter accepted from the peer |
| `kfp` | both | Fingerprint of the key; a new key clears the namespace |

- **TX:** the sender saves a reservation 1024 ahead (`TX_RESERVE_BLOCK`). It writes flash once per
  1024 frames, which is about every 17 min at 1 Hz. After a reboot it carries on above the
  reservation, so it never reuses a value.
- **RX:** scans, results and commands are saved at once. Heartbeats are saved every 256
  (`RX_PERSIST_STEP`). After a power cut, only heartbeats newer than the last save could be
  replayed, and replaying a heartbeat does nothing.
- **Resync:** each `HELLO` carries `lastSeen`, the highest counter received from the peer. On an
  authentic, fresh `HELLO`, the receiver moves its TX counter past `lastSeen`. If one board's
  flash is erased, or it is swapped for a spare with the same key, it recovers within one
  heartbeat. No one can force this without the key.

### Bus access

There are two nodes on a half-duplex bus, with DE and /RE tied to one GPIO (HIGH = transmit).

- **Listen before talk:** wait until the bus has been idle for 3 ms (`BUS_IDLE_MS`), then add
  0.2–1.5 ms of random jitter. Frames that arrive during the wait are queued, not lost. If the
  bus stays busy for 50 ms, send anyway.
- **Reader retries:** every reader event (`BAND_SCAN`, `FINGER_*`, `ENROLL_RESULT`) expects a
  `FEEDBACK`. If none arrives within 1.5 s, the reader sends the same payload again as a new
  frame with a new counter, up to 2 times. After that it shows ERROR.
- **Controller dedup:** a repeat of the same type and payload within 1 s (`EVENT_DEDUP_MS`) is
  not evaluated again. The controller just resends its last `FEEDBACK`. So a lost `FEEDBACK`
  never causes a double grant or a double failure count.

## Messages

| Type | Name | Dir | Payload |
|---|---|---|---|
| `0x01` | `HELLO` | both, every 1 s | `u8 proto=2, u8 fwMajor, u8 fwMinor, u8 flags, u32 uptimeS, u32 lastSeen, u8 caps` (13 B) |
| `0x10` | `BAND_SCAN` | R→C | `u8 uidLen (4–10), uid[uidLen]` |
| `0x11` | `FINGER_MATCH` | R→C | `u16 page, u16 score` (R503 template page + confidence) |
| `0x12` | `FINGER_NOMATCH` | R→C | `u8 reason`: 0 no match, 1 bad image, 2 sensor error |
| `0x13` | `TAMPER` | R→C | `u8 open` (also mirrored in `HELLO.flags` bit 0) |
| `0x14` | `ENROLL_RESULT` | R→C | `u16 page, u8 status`: 0 ok, 1 timeout, 2 mismatch, 3 sensor error, 4 store fail |
| `0x20` | `FEEDBACK` | C→R | `u8 state, u16 holdMs`: show `state`, return to IDLE after `holdMs` (0 = stay) |
| `0x21` | `ENROLL_FINGER` | C→R | `u16 page`: run the two-touch R503 enrollment and store into `page` |
| `0x22` | `SET_CONFIG` | C→R | `u8 brightness (0–255, reader caps it), u8 volume (0–100)` |
| `0x23` | `DELETE_FINGER` | C→R | `u16 page`, `0xFFFF` = empty the whole R503 library |

`HELLO.flags`:
- Reader: bit 0 tamper open, bit 1 PN532 ok, bit 2 R503 ok.
- Controller: bit 0 door open.

### Capabilities (protocol 2)

`HELLO.caps` says what the sender was **built** with. `flags` says what is working right now.

| Bit | Name | Reader sets it when |
|---|---|---|
| 0 (`0x01`) | `CAP_FINGERPRINT` | built with `HAS_FINGERPRINT=1` (`reader`). Not set by `reader_nofp` |
| 1 (`0x02`) | `CAP_NFC` | always (PN532) |
| 2–7 | – | reserved, send 0, ignore |

The controller sends `caps = 0`.

- **Compatibility.**
  - A 12-byte v1 `HELLO` (`proto=1`, no caps byte) is read as `caps = CAP_FINGERPRINT | CAP_NFC`.
    Every v1 reader had an R503.
  - Receivers accept `LEN >= 12` and ignore bytes past the ones they know. A v1 controller still
    works with a v2 reader.
- **Controller rules without `CAP_FINGERPRINT`:**
  - Users with policy `band_and_finger` or `finger_only` are **denied**, with reason `no_fp_hw`.
    The controller never silently falls back to band-only.
    - This doesn't count toward the lockout, because it is a configuration problem.
    - `binary_sensor.fingerprint_configuration_problem` (`magicband/fp_problem`) turns ON while any
      enabled user has such a policy.
  - `FINGER_MATCH` / `FINGER_NOMATCH` from such a reader are denied (`no_fp_hw`).
  - "Enroll finger" is refused: `magicband/enroll` = `no_fingerprint_hw`, nothing is sent to the reader.
    A pending finger enrollment is cancelled if the capability disappears.
  - New users are created `band_only`, not `band_and_finger`.
- **Until the first `HELLO`**, the controller assumes a fingerprint reader. The reader counts as
  offline then, so `TAMPER_DENIES_ACCESS` refuses scans anyway.

The **all-in-one** builds (`reader_aio`, `reader_aio_nofp`) have no link. They apply the same
rules from their own `HAS_FINGERPRINT`, through the same `DoorCore` (`lib/mb_access/src/mb_door.h`).

### Feedback states

| # | State | Reader shows |
|---|---|---|
| 0 | `IDLE` | soft white halo breathing, Mickey dim white |
| 1 | `READING` | blue comet chasing round the halo (also set locally the moment a band is read) |
| 2 | `NEED_FINGER` | halo slow pale-blue pulse, R503 ring breathing blue, short double blip |
| 3 | `GRANTED` | halo + Mickey solid green, rising chime |
| 4 | `DENIED` | alternating blue / red pulses, two low tones |
| 5 | `ERROR` | amber blink, three low beeps |
| 6 | `OFFLINE` | amber blink. Reader-local, set when no controller frame has arrived for 3.5 s |
| 7 | `ENROLL_BAND` | purple comet |
| 8 | `ENROLL_FINGER` | purple breathing, R503 ring purple (set by the reader during `ENROLL_FINGER`) |
| 9 | `ENROLL_OK` | purple/green flash, two-note chime |
| 10 | `ENROLL_FAIL` | purple/red flash, low beeps |
| 11 | `LOCKOUT` | slow red breathing |

## Typical exchanges

Band + finger (policy `BAND_AND_FINGER`):

```
R→C  BAND_SCAN uid=04A1B2C3D4E5F6
C→R  FEEDBACK NEED_FINGER hold=8000        (engine waits up to FINGER_TIMEOUT_MS)
R→C  FINGER_MATCH page=3 score=143
C→R  FEEDBACK GRANTED hold=1500            (strike pulsed, MQTT access event "granted")
```

If the finger belongs to another user, or no finger arrives within 8 s:
`FEEDBACK DENIED hold=2000`. A `FINGER_NOMATCH` inside the window gets
`NEED_FINGER` again (retry). Each one still counts toward the lockout.

Finger enrollment:

```
(HA button "Enroll finger for selected user")
C→R  ENROLL_FINGER page=4
     reader: ring purple, touch, lift, touch again (50 s limit)
R→C  ENROLL_RESULT page=4 status=0
C→R  FEEDBACK ENROLL_OK hold=2000          (page 4 bound to the user in NVS)
```

If the result arrives after the controller gave up (60 s), the controller sends
`DELETE_FINGER page`, so no template is left on the sensor without an owner.

## Known limits

- **Delayed delivery.** Someone with access to the cable could capture a frame, block it, and
  deliver it later. The counter is still fresh because nothing newer has been accepted yet.
  Heartbeats every second limit this: any later heartbeat makes the held frame a replay. So the
  attacker must also block heartbeats, and that marks the reader offline. While offline,
  `TAMPER_DENIES_ACCESS` refuses scans.
- **No encryption.** UIDs and page ids cross the cable in clear text. The cable is inside your
  wall, and the UID is broadcast by the band anyway.
- **Key on the reader.** The key sits in the reader's flash. Someone who steals the reader can
  read it out unless flash encryption is enabled (see README, security notes). Re-provision both
  boards if a reader goes missing.
