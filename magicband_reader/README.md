# Home MagicBand reader

A Disney-park-style MagicBand touchpoint for a front door: a 150 mm ball head
with a light ring and Mickey face, on a cast-style arm with a fingerprint pod.
It's wall-mounted outdoors.

```
MagicBand / finger -> outdoor READER (ESP32-S3, PN532, R503, LEDs, speaker)
                   -- 4-core cable: 12 V + RS-485, HMAC-signed frames -->
                      indoor CONTROLLER (ESP32, allowlist, relay) -> strike / maglock
                                                                  -> Home Assistant (MQTT)
```

The reader has no authority. The controller is indoors and decides who gets
in, so prying the reader open or shorting its cable can't open the door.
The default policy is **band + finger**, because MagicBand UIDs can be cloned.

| Folder | What's in it |
|---|---|
| [`cad/`](cad/README.md) | 23 printable parts (ASA outdoor, TPU gaskets, translucent halo/inlay, PETG controller box), viewer, sections, fit checks |
| [`firmware/`](firmware/README.md) | PlatformIO `reader` / `controller` / `native` envs, protocol, Home Assistant setup, key provisioning |
| [`indoor/`](indoor/README.md) | Indoor variants: fingerprint pod / blank pod / ball only on a wall, tabletop or freestanding-post mount (9 combos), split or all-in-one electronics |
| [`electronics/WIRING.md`](electronics/WIRING.md) | Pin tables, wiring diagram, BOM, cable spec, power budget, strike wiring |

## Quick start

1. Print the parts (`cad/README.md` has orientation, material and hardware).
2. Wire per `electronics/WIRING.md`. Put the 4-pin inline connector in the
   wall cavity behind the bracket so the head can come off for service.
3. Provision the shared key: `python3 firmware/tools/provision.py`. Then flash
   `reader` and `controller` (`firmware/README.md`).
4. In Home Assistant, the lock and enroll buttons appear through MQTT
   discovery. Enroll a band, then a finger for that user.

## Known limits

- The LED count (42) is fixed by the CAD ring. `LED_HALO_COUNT` in
  `firmware/include/config.h` must match it.
- Water can get into the light box through the speaker holes. Use an IP65 LED
  strip and seal the speaker rim.
- The Mickey inlay is lit only by spill from the ring, so it glows weakly.
- MQTT runs without TLS, and flash encryption is off (see
  `firmware/README.md`, Security).
- The Mickey logo is a Disney trademark. It's for personal use only. Share
  `face_disc_blank` instead.
- Nothing has been tested on real hardware yet.
