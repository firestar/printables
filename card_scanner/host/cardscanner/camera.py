"""Camera abstraction: a pair (front = top camera, back = bottom camera).

PiCameraPair   two Pi Camera Module 3 on CAM0/CAM1 via picamera2
FakeCameraPair cycles *_front.jpg / *_back.jpg files from a directory
"""

import logging
import time
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


class CameraPair:
    def capture(self):
        """Return (front_bgr, back_bgr); back may be None."""
        raise NotImplementedError

    def close(self):
        pass


class FakeCameraPair(CameraPair):
    def __init__(self, directory=None, pairs=None, loop=True):
        self.loop = loop
        self.i = 0
        if pairs is not None:
            self.pairs = list(pairs)
        else:
            d = Path(directory)
            fronts = sorted(d.glob("*_front.*"))
            self.pairs = []
            for f in fronts:
                stem = f.name.rsplit("_front", 1)[0]
                backs = list(d.glob(stem + "_back.*"))
                self.pairs.append((f, backs[0] if backs else None))
        if not self.pairs:
            raise FileNotFoundError("no *_front.* images in %s" % directory)

    def capture(self):
        if self.i >= len(self.pairs):
            if not self.loop:
                raise RuntimeError("fake camera exhausted")
            self.i = 0
        f, b = self.pairs[self.i]
        self.i += 1
        front = f if isinstance(f, np.ndarray) else cv2.imread(str(f))
        back = None
        if b is not None:
            back = b if isinstance(b, np.ndarray) else cv2.imread(str(b))
        return front, back

    def reset(self):
        self.i = 0


class PiCameraPair(CameraPair):
    """Two Camera Module 3s.  Lazy-imports picamera2 so the rest of the app
    works on a desktop."""

    def __init__(self, front_index=0, back_index=1, size=(2304, 1296), settle_ms=120, autofocus=True):
        from picamera2 import Picamera2  # type: ignore
        self.settle_ms = settle_ms
        self.cams = []
        for idx in (front_index, back_index):
            cam = Picamera2(idx)
            cfg = cam.create_still_configuration(main={"size": tuple(size), "format": "RGB888"}, buffer_count=2)
            cam.configure(cfg)
            if autofocus:
                try:
                    from libcamera import controls  # type: ignore
                    cam.set_controls({"AfMode": controls.AfModeEnum.Continuous})
                except Exception:  # pragma: no cover
                    log.warning("autofocus control unavailable on cam %d", idx)
            cam.start()
            self.cams.append(cam)
        time.sleep(0.5)

    def capture(self):
        time.sleep(self.settle_ms / 1000.0)
        front = self.cams[0].capture_array("main")
        back = self.cams[1].capture_array("main")
        # picamera2 RGB888 is actually BGR byte order for OpenCV purposes
        return front, back

    def close(self):
        for c in self.cams:
            try:
                c.stop()
                c.close()
            except Exception:  # pragma: no cover
                pass


def make_cameras(cfg):
    cam = cfg["cameras"]
    if cam.get("backend", "fake") == "picamera2":
        return PiCameraPair(cam.get("front_index", 0), cam.get("back_index", 1), tuple(cam.get("size", [2304, 1296])),
                            cam.get("settle_ms", 120))
    return FakeCameraPair(cfg.resolve(cam.get("fake_dir", "data/demo/photos")))
