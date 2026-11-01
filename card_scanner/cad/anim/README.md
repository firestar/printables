# Card scanner – cycle animation

One card cycle (36 s) rendered from the assembled CAD preview (`../preview/`): hopper pick → feed → scan →
transfer → sleeve pick / lift / tongues / insert / seat → pusher → diverter → bin C.

- `animate.html` – three.js scene (same loader as `../viewer.html`), deterministic timeline: `window.setTime(t)`
  poses every part for time `t` and renders one frame. Open over http: `?t=12` for a still, `?play=1` to run live.
- `render.py` – serves `..` on a local port, drives the page with Playwright (chromium, 1280×720) and encodes with
  ffmpeg: `python3 render.py` → `card_scanner_cycle.mp4` (H.264 yuv420p, 30 fps) + `card_scanner_cycle.gif`
  (12 fps, 640 px). `python3 render.py --stills 4.5 12 24` writes PNGs to `stills/`.
- `frames/`, `stills/` are scratch (gitignored).

Motion follows `../README.md` coordinates (track z 125, scan_stop x 244, mouth x 406, pawl −20 → +0.3 → +36,
tongue tips −3 → +15, lift 5.5 (cup at S 22), diverter +42°). Simplifications: the card parks before the entry nip while the
sleeve is prepared (the firmware prepares the sleeve first and feeds through in one go), the elevator raise is
exaggerated to 12 mm, the sleeve is a two-ply surface, the hood is hidden and the lower shroud / pick bridge /
pusher bracket / −y roller blocks are faded for visibility.
