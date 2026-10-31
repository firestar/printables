"""cardscanner command line.

  cardscanner run   --config config.yaml [--mock] [--fake-camera]
  cardscanner index build --config config.yaml --games mtg,pokemon,ygo [--limit N]
  cardscanner index stats --config config.yaml
  cardscanner demo  --config config.demo.yaml       (synthetic index + fake photos)
  cardscanner export --config config.yaml --format moxfield|tcgplayer|full [--session ID] [-o file]
  cardscanner mcu   --config config.yaml ping|status|get KEY|set KEY VALUE|home
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Config


def _cfg(args):
    p = Path(args.config)
    if not p.exists():
        sys.exit("config not found: %s (copy config.example.yaml)" % p)
    return Config.load(p)


def cmd_run(args):
    import uvicorn
    from .app_factory import App
    from .web.app import create_app
    cfg = _cfg(args)
    app = App(cfg, mock=True if args.mock else None, fake_camera=True if args.fake_camera else None)
    api = create_app(app)
    web = cfg["web"]
    host = args.host or web.get("host", "0.0.0.0")
    port = args.port or int(web.get("port", 8080))
    logging.getLogger(__name__).info("index: %d cards; mock=%s", app.index.count(), app.mock)
    try:
        uvicorn.run(api, host=host, port=port, log_level="info")
    finally:
        app.close()


def cmd_index_build(args):
    from .index import CardIndex
    from .sources import build_index
    cfg = _cfg(args)
    games = [g.strip() for g in args.games.split(",") if g.strip()]
    index = CardIndex(cfg.paths["index_db"])

    def progress(game, n):
        print("  %s: %d cards" % (game, n), flush=True)

    build_index(index, games, cfg.paths["image_cache"], cfg["prices"].get("pokemon_api_key", ""),
                limit=args.limit, progress=progress)
    print("index now has %d cards" % index.count())


def cmd_index_stats(args):
    from .index import CardIndex
    cfg = _cfg(args)
    index = CardIndex(cfg.paths["index_db"])
    print(json.dumps({"total": index.count(), "games": {g: index.count(g) for g in index.games()},
                      "backs": sorted(index._backs.keys())}, indent=2))


def cmd_index_backs(args):
    """Register reference card-back images: --mtg back.jpg --pokemon back.jpg --ygo back.jpg"""
    import cv2
    from .index import CardIndex
    from .vision import extract_card, CardNotFound
    cfg = _cfg(args)
    index = CardIndex(cfg.paths["index_db"])
    for game in ("mtg", "pokemon", "ygo"):
        p = getattr(args, game)
        if not p:
            continue
        img = cv2.imread(p)
        try:
            img, _ = extract_card(img)
        except CardNotFound:
            pass
        index.set_back(game, img)
        print("back registered for", game)


def cmd_demo(args):
    from .demo import setup_demo
    cfg = _cfg(args)
    n_cards, n_photos = setup_demo(cfg.paths["index_db"], cfg.paths["image_cache"],
                                   cfg.resolve(cfg["cameras"]["fake_dir"]), n_unknown=args.unknown)
    print("demo ready: %d indexed cards, %d fake photos in %s" % (n_cards, n_photos, cfg["cameras"]["fake_dir"]))


def cmd_export(args):
    from .inventory import Inventory
    cfg = _cfg(args)
    inv = Inventory(cfg.paths["inventory_db"])
    csv = inv.export_csv(args.format, args.session)
    if args.output:
        Path(args.output).write_text(csv)
        print("wrote", args.output)
    else:
        sys.stdout.write(csv)


def cmd_mcu(args):
    from .mock_mcu import MockMcu
    from .protocol import McuClient, McuError, SerialTransport
    cfg = _cfg(args)
    ser = cfg["serial"]
    transport = MockMcu() if (args.mock or ser.get("mock")) else SerialTransport(ser["port"], ser.get("baud", 115200))
    mcu = McuClient(transport, ser.get("timeout_s", 15.0))
    try:
        if args.op == "ping":
            print(mcu.ping())
        elif args.op == "status":
            print(json.dumps(mcu.status(), indent=2))
        elif args.op == "home":
            print(mcu.home())
        elif args.op == "get":
            print(mcu.get(args.args[0]))
        elif args.op == "set":
            val = args.args[1]
            try:
                val = json.loads(val)
            except ValueError:
                pass
            print(mcu.set(args.args[0], val))
        else:
            print(mcu.send(args.op))
    except McuError as e:
        sys.exit("error: %s" % e)
    finally:
        mcu.close()


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="cardscanner", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", "-c", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="start the web UI + orchestrator")
    r.add_argument("--mock", action="store_true", help="use the in-process mock controller")
    r.add_argument("--fake-camera", action="store_true", help="use fake cameras from cameras.fake_dir")
    r.add_argument("--host")
    r.add_argument("--port", type=int)
    r.set_defaults(fn=cmd_run)

    ix = sub.add_parser("index", help="hash index maintenance").add_subparsers(dest="ixcmd", required=True)
    b = ix.add_parser("build")
    b.add_argument("--games", default="mtg,pokemon,ygo")
    b.add_argument("--limit", type=int, help="cards per game (for testing)")
    b.set_defaults(fn=cmd_index_build)
    s = ix.add_parser("stats")
    s.set_defaults(fn=cmd_index_stats)
    bk = ix.add_parser("backs", help="register card-back reference photos")
    for g in ("mtg", "pokemon", "ygo"):
        bk.add_argument("--" + g)
    bk.set_defaults(fn=cmd_index_backs)

    d = sub.add_parser("demo", help="build the synthetic demo index + fake photos")
    d.add_argument("--unknown", type=int, default=3)
    d.set_defaults(fn=cmd_demo)

    e = sub.add_parser("export")
    e.add_argument("--format", default="moxfield", choices=["moxfield", "tcgplayer", "full"])
    e.add_argument("--session")
    e.add_argument("-o", "--output")
    e.set_defaults(fn=cmd_export)

    mc = sub.add_parser("mcu", help="talk to the controller")
    mc.add_argument("op")
    mc.add_argument("args", nargs="*")
    mc.add_argument("--mock", action="store_true")
    mc.set_defaults(fn=cmd_mcu)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
