# Card scanner — Raspberry Pi 5 host

Host software for the automated trading-card scanner / penny-sleever / 3-bin sorter.
The Pi photographs each card (two Camera Module 3s: top = front, bottom = back through the
glass), identifies it with a perceptual-hash index, prices it, decides a bin from configurable
rules and drives the ESP32-S3 motion controller over USB serial.  Everything runs without
hardware too (mock controller + fake cameras + synthetic index).

```
cardscanner/
  protocol.py     newline-JSON serial client (McuClient) + SerialTransport
  mock_mcu.py     in-process simulated controller (faults, events, tunables)
  camera.py       CameraPair: PiCameraPair (picamera2) / FakeCameraPair (files)
  vision.py       contour -> perspective warp to canonical 630x880, art/name regions
  hashing.py      pHash / dHash + vectorised Hamming
  index.py        SQLite hash index, search (combobox), lookup, back-of-card game check
  sources.py      Scryfall / Pokémon TCG API / YGOPRODeck fetchers, image cache, index build
  recognize.py    crop -> hash lookup -> ORB re-rank -> OCR fallback, confidence
  ocr.py          tesseract name-line / collector-number fallback
  prices.py       TTL price cache (Scryfall usd/usd_foil, TCGplayer via Pokémon API, YGOPRODeck)
  rules.py        ordered bin rules (game, rarity, foil, price, recognized, confidence)
  inventory.py    inventory SQLite + Moxfield / TCGplayer / full CSV export
  machine.py      orchestrator state machine + retry policy
  web/            FastAPI API + static UI (dashboard, review queue, rules editor, tunables)
  cli.py          `cardscanner run | index build | demo | export | mcu`
tests/            pytest suite (protocol, state machine, vision, index, rules, export)
```

## Quick start without hardware (any Linux box)

```bash
cd card_scanner/host
pip install -r requirements.txt           # or: pip install -e .[dev]
python -m cardscanner -c config.demo.yaml demo   # synthetic index + fake photos in data/demo
python -m cardscanner -c config.demo.yaml run    # http://127.0.0.1:8089
python -m pytest                                  # tests
```

`config.demo.yaml` uses the mock controller with scripted faults (a double feed on card 4,
one sleeve-open failure on card 6) and fake cameras that cycle `data/demo/photos/*_front.jpg`
/ `*_back.jpg`.  Three of the fake photos are cards that are not in the index, so the review
queue fills up.  `tools/ui_walkthrough.py` drives the UI with Playwright (`pip install
playwright && playwright install chromium`) — start a batch, resolve a review-queue card through
the combobox, edit a rule, set a tunable — and saves screenshots to `docs/screenshots/`.
queue fills up.

## Raspberry Pi 5 setup

### OS packages

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv python3-numpy python3-yaml python3-serial \
                    tesseract-ocr libcap-dev git
# the rest from pip (system python so picamera2 stays importable)
pip install --break-system-packages fastapi uvicorn httpx pydantic python-multipart pytesseract
```

Use the system Python (`/usr/bin/python3`): `picamera2` is only available from apt and must be
importable by the same interpreter that runs the host.  If you prefer a venv, create it with
`python3 -m venv --system-site-packages ~/cs-venv`.

### Dual CSI cameras

The Pi 5 has two 4-lane CSI connectors (CAM0 / CAM1, 22-pin).  Use the 22-to-15 pin FPC adapter
cables that come with Camera Module 3 for Pi 5.  No `config.txt` change is needed for Camera
Module 3 (auto-detected).  Check with:

```bash
rpicam-hello --list-cameras
# 0 : imx708 [4608x2592] (/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a)   <- CAM0 = top / front
# 1 : imx708 [4608x2592] (/base/axi/pcie@120000/rp1/i2c@80000/imx708@1a)   <- CAM1 = bottom / back
```

If the order is swapped on your build, swap `cameras.front_index` / `back_index` in the config.
Focus: the Camera Module 3 autofocus is left in continuous mode; for a fixed glass height you can
lock it by setting `AfMode` to manual in `camera.py` once you know the lens position.

### Serial link to the ESP32-S3

The controller enumerates as USB-CDC (`/dev/ttyACM0`).  For a stable name add a udev rule:

```
# /etc/udev/rules.d/99-cardsorter.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", SYMLINK+="cardsorter", MODE="0666"
```

then set `serial.port: /dev/cardsorter`.  Add the user to `dialout` (`sudo usermod -aG dialout $USER`).

Protocol (115200 baud, newline-delimited JSON):

```
host -> mcu   {"id": 7, "cmd": "sort", "bin": 1}
reply         {"id": 7, "ok": true}            | {"id": 7, "ok": false, "err": "jam", "msg": "..."}
event         {"evt": "hopper_empty"}
```

Commands: `ping home status feed lights{top,bottom} sleeve sort{bin} eject_reject set{key,value}
get{key} estop reset`.  Error codes: `hopper_empty magazine_empty double_feed pick_fail jam
sleeve_open_fail sleeve_insert_fail exit_timeout estop not_homed busy bad_cmd`.  Events: `estop
lid_open hopper_empty magazine_low`.  Test the link with `python -m cardscanner mcu ping`.

### Build the recognition index

The index is built offline from public card databases.  Images are fetched at the smallest
size the API offers (Scryfall `small` 146x204, Pokémon TCG `small`, YGOPRODeck `image_url_small`)
and cached under `paths.image_cache` so rebuilds are fast and the ORB re-ranker has reference art.

```bash
cd ~/printables/card_scanner/host
cp config.example.yaml config.yaml          # edit port / cameras / rules
python -m cardscanner index build --games mtg,pokemon,ygo
python -m cardscanner index stats
```

Budget roughly: MTG ~95k printings (~1.5 GB of images, a couple of hours at Scryfall's polite
rate), Pokémon ~19k, Yu-Gi-Oh ~13k artworks.  `--limit N` builds a small test index.  A Pokémon
TCG API key (`prices.pokemon_api_key`) raises that API's rate limit.  Re-running `index build`
refreshes the price snapshot; at scan time prices older than `prices.ttl_hours` are refreshed
per card from the APIs (set `prices.offline: true` to never call out while scanning).

Card backs: photograph one real card back per game on the machine and register them so the
bottom camera can confirm the game:

```bash
python -m cardscanner index backs --mtg back_mtg.jpg --pokemon back_pkm.jpg --ygo back_ygo.jpg
```

### Run as a service

```ini
# /etc/systemd/system/cardscanner.service
[Unit]
Description=Card scanner host
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/printables/card_scanner/host
ExecStart=/usr/bin/python3 -m cardscanner -c config.yaml run
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cardscanner
journalctl -fu cardscanner
```

The UI is at `http://<pi>:8080`.  Set `web.host: 127.0.0.1` if you only reach it through a reverse
proxy.

## How a card is processed

1. `feed` — card to the scan station.  `double_feed` → `eject_reject` (bin 2, unsleeved, logged
   as rejected).  `pick_fail` → one retry.  `hopper_empty` / `magazine_empty` → pause.
2. `lights {top,bottom}` → capture front + back → `lights {0,0}`.
3. In parallel: `sleeve` (one retry on `sleeve_open_fail` / `sleeve_insert_fail`, then pause for the
   operator; on resume the sleeve is retried once more, then the card is sorted) and recognition
   (crop/deskew → hash lookup, both orientations → optional ORB re-rank → OCR fallback below
   `recognition.ocr_below`).  The back image picks the game and halves the confidence on a mismatch.
4. Price from the index snapshot / API (foil price when the batch is marked foil or the printing is
   foil-only), rules engine → `sort {bin}`.  `jam` / `exit_timeout` pause; resume retries the sort.
5. Inventory row + `data/sessions/<session>/NNNNN_front.jpg` / `_back.jpg`.  Cards below
   `recognition.review_below` land in the review queue where the operator picks the right card
   from the index with a searchable combobox.

`estop` (reply or event) stops the loop; the UI's **Reset / home** sends `reset` + `home`.

## Bin rules

Rules are an ordered list in `config.yaml` (also editable in the UI, which writes the file back):

```yaml
rules:
  - {name: Valuable,        bin: 0, when: {min_price: 2.0, min_confidence: 0.6}}
  - {name: Foil rares,      bin: 0, when: {foil: true, rarity: [rare, mythic]}}
  - {name: Recognized bulk, bin: 1, when: {recognized: true}}
default_bin: 2
```

Conditions: `game`, `rarity` (lists allowed), `foil`, `recognized`, `min_price`, `max_price`,
`min_confidence`, `max_confidence`.  Price conditions never match a card without a price.

## Export

Dashboard buttons or `python -m cardscanner export --format moxfield|tcgplayer|full --session ID`.
Moxfield columns follow its collection CSV (Count, Name, Edition, Condition, Foil, Collector
Number, Purchase Price…); TCGplayer columns follow its collection import (Quantity, Name, Set,
Card Number, Set Code, Printing, Condition, Rarity…).  Only identified (or operator-resolved)
cards are exported; `full` includes confidence, bin, rule and photo paths.

## API

`GET /api/status`, `POST /api/control/{start|pause|resume|stop|reset|home}`, `GET /api/review`,
`POST /api/review/{id}/resolve {card_id}`, `GET /api/index/search?q=&game=`, `GET|PUT /api/rules`,
`GET|POST /api/tunables`, `GET /api/export.csv?format=&session=`, `GET /files/...` (photos).
