"""Wire the components together from a Config (shared by CLI + web)."""

import logging
from pathlib import Path

from .camera import make_cameras
from .config import Config
from .index import CardIndex
from .inventory import Inventory
from .machine import Orchestrator
from .mock_mcu import MockMcu
from .ocr import Ocr
from .prices import PriceService
from .protocol import McuClient, SerialTransport
from .recognize import Recognizer
from .rules import RulesEngine
from .sources import ImageCache

log = logging.getLogger(__name__)


class App:
    def __init__(self, cfg: Config, mock=None, fake_camera=None):
        self.cfg = cfg
        paths = cfg.paths
        for p in (paths["data_dir"], paths["image_cache"]):
            Path(p).mkdir(parents=True, exist_ok=True)
        self.index = CardIndex(paths["index_db"])
        self.inventory = Inventory(paths["inventory_db"])
        self.cache = ImageCache(paths["image_cache"])
        rc = cfg["recognition"]
        self.ocr = Ocr(enabled=rc.get("ocr", True))
        self.recognizer = Recognizer(self.index, rc, image_loader=self.cache.load, ocr=self.ocr)
        pc = cfg["prices"]
        self.prices = PriceService(self.index, pc.get("ttl_hours", 24), pc.get("pokemon_api_key", ""),
                                   pc.get("offline", False))
        self.rules = RulesEngine(cfg.rules, cfg.default_bin, len(cfg["bins"]))
        ser = cfg["serial"]
        self.mock = ser.get("mock", False) if mock is None else mock
        if self.mock:
            mo = ser.get("mock_options", {}) or {}
            self.mock_mcu = MockMcu(hopper=mo.get("hopper", 30), magazine=mo.get("magazine", 100),
                                    delays=mo.get("delays", True), faults=mo.get("faults") or {})
            transport = self.mock_mcu
        else:
            self.mock_mcu = None
            transport = SerialTransport(ser["port"], ser.get("baud", 115200))
        self.mcu = McuClient(transport, default_timeout=ser.get("timeout_s", 15.0))
        if fake_camera:
            from .camera import FakeCameraPair
            self.cameras = FakeCameraPair(cfg.resolve(cfg["cameras"].get("fake_dir", "data/demo/photos")))
        else:
            self.cameras = make_cameras(cfg)
        self.machine = Orchestrator(self.mcu, self.cameras, self.recognizer, self.rules, self.inventory,
                                    self.prices, cfg, paths["data_dir"], bins=cfg["bins"])

    def update_rules(self, rules, default_bin):
        engine = RulesEngine(rules, default_bin, len(self.cfg["bins"]))  # validates
        self.rules = engine
        self.machine.rules = engine
        self.cfg.rules = rules
        self.cfg.data["default_bin"] = int(default_bin)
        if self.cfg.path:
            self.cfg.save()

    def close(self):
        self.machine.stop()
        self.mcu.close()
        self.cameras.close()
        self.index.close()
        self.inventory.close()
