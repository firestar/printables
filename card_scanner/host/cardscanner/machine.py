"""Orchestrator: the per-card state machine + retry policy.

  feed -> lights on, capture front/back, lights off -> [sleeve || recognise] -> sort(bin)

Retry policy
  double_feed                 -> eject_reject (bin 2, unsleeved), card logged as rejected
  sleeve_open_fail/insert     -> retry once, then PAUSE (operator); on resume: retry sleeve, then sort
  hopper_empty/magazine_empty -> PAUSE; on resume continue
  pick_fail                   -> retry feed once, then PAUSE
  jam / exit_timeout          -> PAUSE with error; on resume retry the failed step
  not_homed                   -> home, retry once
  busy                        -> wait 200 ms, retry
  estop (reply or event)      -> ESTOP state until reset()
  lid_open event              -> PAUSE
"""

import logging
import threading
import time
from collections import deque
from pathlib import Path

import cv2

from .protocol import McuError, McuTimeout
from .rules import RulesEngine

log = logging.getLogger(__name__)

PAUSE_MESSAGES = {
    "operator": "Paused by operator.",
    "hopper_empty": "Input hopper is empty. Refill and resume.",
    "magazine_empty": "Sleeve magazine is empty. Reload sleeves and resume.",
    "sleeve_open_fail": "Sleeve failed to open twice. Clear the sleever, then resume to retry.",
    "sleeve_insert_fail": "Card did not enter the sleeve. Check the sleever, then resume to retry.",
    "pick_fail": "Feeder could not pick a card twice. Check the hopper, then resume.",
    "jam": "Card jam reported by the controller. Clear it and resume.",
    "exit_timeout": "Card did not reach the bin sensor. Check the sorter and resume.",
    "lid_open": "Lid is open. Close it and resume.",
    "mcu_timeout": "Controller did not answer. Check the USB link, then resume.",
    "camera": "Camera capture failed. Check the cameras, then resume.",
}


class Orchestrator:
    def __init__(self, mcu, cameras, recognizer, rules: RulesEngine, inventory, prices, cfg, data_dir,
                 bins=None):
        self.mcu = mcu
        self.cameras = cameras
        self.recognizer = recognizer
        self.rules = rules
        self.inventory = inventory
        self.prices = prices
        self.cfg = cfg
        self.data_dir = Path(data_dir)
        self.bins = bins or [{"id": i, "name": "Bin %d" % i} for i in range(3)]
        self.lights = cfg.get("lights", {"top": 200, "bottom": 200}) if hasattr(cfg, "get") else {"top": 200, "bottom": 200}

        self.state = "idle"       # idle | homing | running | paused | stopping | estop
        self.pause_reason = None
        self.error = None
        self.warning = None
        self.session_id = None
        self.session_opts = {}
        self.stats = self._fresh_stats()
        self.last_card = None
        self.history = deque(maxlen=25)
        self.events = deque(maxlen=50)
        self.mcu_status = {}
        self._pending = None        # {"stage": "sleeve"|"sort", "bin": int, "row_id": int, "attempts": int}
        self._cond = threading.Condition(threading.RLock())
        self._pause_req = None
        self._stop_req = False
        self._thread = None
        self.estopped = False
        mcu.on_event(self._on_event)

    # --- public control ----------------------------------------------------------
    def _fresh_stats(self):
        return {"processed": 0, "ok": 0, "review": 0, "rejected": 0, "errors": 0, "bins": [0, 0, 0],
                "started_at": None, "cards_per_min": 0.0, "elapsed_s": 0}

    def start(self, notes="", foil=False, condition="NM"):
        with self._cond:
            if self.state == "estop":
                raise RuntimeError("E-stop active: reset first")
            if self._thread and self._thread.is_alive():
                if self.state == "paused":
                    return self.resume()
                raise RuntimeError("already running")
            self.session_id = self.inventory.start_session(notes=notes, foil=foil, condition=condition)
            self.session_opts = {"notes": notes, "foil": bool(foil), "condition": condition}
            self.stats = self._fresh_stats()
            self.stats["started_at"] = time.time()
            self.error = None
            self.pause_reason = None
            self._pause_req = None
            self._stop_req = False
            self._pending = None
            self.state = "homing"
            self._thread = threading.Thread(target=self._run, name="orchestrator", daemon=True)
            self._thread.start()
            self._log("info", "session %s started" % self.session_id)
            return self.session_id

    def pause(self, reason="operator", error=None):
        with self._cond:
            self._pause_req = reason
            if error:
                self.error = error
            self._cond.notify_all()

    def resume(self):
        with self._cond:
            if self.state == "estop":
                raise RuntimeError("E-stop active: reset first")
            self._pause_req = None
            self.pause_reason = None
            self.error = None
            self._cond.notify_all()

    def stop(self, wait=True):
        with self._cond:
            self._stop_req = True
            self._pause_req = None
            self._cond.notify_all()
            t = self._thread
        if wait and t and t.is_alive() and t is not threading.current_thread():
            t.join(30)

    def reset(self):
        """Clear e-stop / error: controller reset + home."""
        self.stop()
        self.mcu.reset()
        self.mcu.home()
        with self._cond:
            self.estopped = False
            self.error = None
            self.pause_reason = None
            self._pending = None
            self.state = "idle"
        self._log("info", "controller reset and homed")

    def home(self):
        self.mcu.home()

    # --- status ------------------------------------------------------------------------
    def snapshot(self):
        with self._cond:
            st = dict(self.stats)
            if st["started_at"]:
                el = max(1e-6, time.time() - st["started_at"])
                st["elapsed_s"] = int(el)
                st["cards_per_min"] = round(st["processed"] / (el / 60.0), 1) if el > 5 else 0.0
            return {
                "state": self.state, "pause_reason": self.pause_reason,
                "pause_message": PAUSE_MESSAGES.get(self.pause_reason, self.pause_reason) if self.pause_reason else None,
                "error": self.error, "warning": self.warning, "session_id": self.session_id,
                "session": self.session_opts, "stats": st, "last_card": self.last_card,
                "history": list(self.history), "events": list(self.events)[-10:], "mcu": self.mcu_status,
                "bins": self.bins, "pending": self._pending, "mcu_connected": self.mcu.connected,
            }

    def _log(self, level, msg):
        self.events.append({"ts": time.time(), "level": level, "msg": msg})
        (log.warning if level in ("warn", "error") else log.info)(msg)

    # --- MCU events ---------------------------------------------------------------------
    def _on_event(self, evt):
        name = evt.get("evt")
        if name == "estop":
            with self._cond:
                self.estopped = True
                self.state = "estop"
                self.error = "E-STOP active. Clear the cause, then Reset."
                self._stop_req = True
                self._cond.notify_all()
            self._log("error", "e-stop event")
        elif name == "lid_open":
            self.pause("lid_open")
            self._log("warn", "lid opened")
        elif name == "hopper_empty":
            if self.state in ("running", "homing"):
                self.pause("hopper_empty")
        elif name == "magazine_low":
            self.warning = "Sleeve magazine low (%s left)." % evt.get("magazine", "?")
            self._log("warn", self.warning)

    # --- main loop -------------------------------------------------------------------------
    def _run(self):
        try:
            self._ensure_homed()
            while True:
                with self._cond:
                    while self._pause_req and not self._stop_req:
                        self.state = "paused"
                        self.pause_reason = self._pause_req
                        self._cond.wait(0.5)
                    if self._stop_req:
                        break
                    self.state = "running"
                self._process_one()
            self.state = "stopping"
        except Exception as e:  # pragma: no cover - defensive
            log.exception("orchestrator crashed")
            self.error = "Internal error: %s" % e
        finally:
            try:
                if not self.estopped:
                    self.mcu.lights(0, 0)
            except McuError:
                pass
            if self.session_id:
                self.inventory.end_session(self.session_id)
            with self._cond:
                self.state = "estop" if self.estopped else "idle"
            self._log("info", "session %s ended (%d cards)" % (self.session_id, self.stats["processed"]))

    def _ensure_homed(self):
        try:
            st = self.mcu.status()
            self.mcu_status = st
            if not st.get("homed"):
                self.state = "homing"
                self.mcu.home()
        except McuError as e:
            self._fault(e)

    def _fault(self, e):
        """Map a controller error to a pause/estop."""
        if e.code == "estop":
            with self._cond:
                self.estopped = True
                self._stop_req = True
            self.error = "E-STOP active. Clear the cause, then Reset."
        elif isinstance(e, McuTimeout):
            self.pause("mcu_timeout", "Controller timeout: %s" % e.msg)
        else:
            self.pause(e.code, "%s: %s" % (e.code, e.msg) if e.msg else e.code)
        self.stats["errors"] += 1
        self._log("error", "controller error: %s" % e)

    def _call(self, fn, *a):
        """Call an MCU command, transparently handling busy / not_homed."""
        for attempt in range(3):
            try:
                return fn(*a)
            except McuError as e:
                if e.code == "busy" and attempt < 2:
                    time.sleep(0.2)
                    continue
                if e.code == "not_homed" and attempt == 0:
                    self.mcu.home()
                    continue
                raise
        raise McuError("busy", "controller stayed busy")

    def _process_one(self):
        if self._pending:
            return self._finish_pending()
        # 1. feed -------------------------------------------------------------------
        for attempt in range(2):
            try:
                reply = self._call(self.mcu.feed)
                self.mcu_status.update({k: reply[k] for k in ("hopper",) if k in reply})
                break
            except McuError as e:
                if e.code == "double_feed":
                    self._reject("double_feed")
                    return
                if e.code == "pick_fail" and attempt == 0:
                    self._log("warn", "pick_fail, retrying feed")
                    continue
                return self._fault(e)
        # 2. capture -----------------------------------------------------------------
        try:
            self._call(self.mcu.lights, self.lights.get("top", 200), self.lights.get("bottom", 200))
            front, back = self.cameras.capture()
            self._call(self.mcu.lights, 0, 0)
        except McuError as e:
            return self._fault(e)
        except Exception as e:
            self.stats["errors"] += 1
            self._log("error", "camera: %s" % e)
            self.pause("camera", "Camera error: %s" % e)
            return
        # 3. sleeve || recognise -------------------------------------------------------
        sleeve_result = {}
        t = threading.Thread(target=self._sleeve_with_retry, args=(sleeve_result,), daemon=True)
        t.start()
        foil = bool(self.session_opts.get("foil"))
        try:
            recog = self.recognizer.identify(front, back, foil=foil)
        except Exception as e:  # recognition must never kill the loop
            log.exception("recognizer failed")
            recog = None
        t.join()
        price, price_info = (None, {})
        if recog is not None and recog.card is not None:
            price, price_info = self.prices.get(recog.card, foil=foil)
        facts = RulesEngine.facts_from(recog, price, foil) if recog is not None else \
            {"game": None, "rarity": "unknown", "foil": foil, "price": None, "recognized": False, "confidence": 0.0}
        bin_, rule = self.rules.choose(facts)
        row_id = self._record(recog, front, back, price, price_info, bin_, rule, foil)
        self.stats["processed"] += 1
        # 4. sort -------------------------------------------------------------------------
        err = sleeve_result.get("error")
        if err is not None:
            self._pending = {"stage": "sleeve", "bin": bin_, "row_id": row_id, "attempts": 0}
            return self._fault(err)
        self._sort(bin_, row_id)

    def _sleeve_with_retry(self, out):
        for attempt in range(2):
            try:
                self._call(self.mcu.sleeve)
                out["ok"] = True
                return
            except McuError as e:
                if e.code in ("sleeve_open_fail", "sleeve_insert_fail") and attempt == 0:
                    self._log("warn", "%s, retrying sleeve" % e.code)
                    continue
                out["error"] = e
                return

    def _sort(self, bin_, row_id):
        try:
            self._call(self.mcu.sort, bin_)
        except McuError as e:
            self._pending = {"stage": "sort", "bin": bin_, "row_id": row_id, "attempts": 0}
            return self._fault(e)
        self._pending = None
        self.stats["bins"][bin_] += 1
        return True

    def _finish_pending(self):
        """After a pause caused by a sleeve/sort error: retry the failed step."""
        p = self._pending
        p["attempts"] += 1
        if p["stage"] == "sleeve":
            try:
                self._call(self.mcu.sleeve)
            except McuError as e:
                return self._fault(e)
            p["stage"] = "sort"
        self._sort(p["bin"], p["row_id"])

    def _reject(self, reason):
        try:
            self._call(self.mcu.eject_reject)
        except McuError as e:
            return self._fault(e)
        seq = self.inventory.next_seq(self.session_id)
        self.inventory.add_card(session_id=self.session_id, seq=seq, status="rejected", error=reason, bin=2,
                                rule="reject", foil=int(bool(self.session_opts.get("foil"))))
        self.stats["rejected"] += 1
        self.stats["processed"] += 1
        self.last_card = {"seq": seq, "status": "rejected", "error": reason, "bin": 2, "name": "(double feed)",
                          "ts": time.time()}
        self.history.appendleft(self.last_card)
        self._log("warn", "double feed -> reject bin")

    def _save(self, seq, kind, img):
        if img is None:
            return None
        d = self.data_dir / "sessions" / self.session_id
        d.mkdir(parents=True, exist_ok=True)
        rel = "sessions/%s/%05d_%s.jpg" % (self.session_id, seq, kind)
        cv2.imwrite(str(self.data_dir / rel), img, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return rel

    def _record(self, recog, front, back, price, price_info, bin_, rule, foil):
        seq = self.inventory.next_seq(self.session_id)
        canon_f = recog.canon_front if recog is not None and recog.canon_front is not None else front
        canon_b = recog.canon_back if recog is not None and recog.canon_back is not None else back
        front_path = self._save(seq, "front", canon_f)
        back_path = self._save(seq, "back", canon_b)
        card = recog.card if recog is not None else None
        if recog is None:
            status = "error"
        elif recog.error:
            status = "review"
        else:
            status = "review" if recog.needs_review else "ok"
        if status == "review":
            self.stats["review"] += 1
        elif status == "ok":
            self.stats["ok"] += 1
        else:
            self.stats["errors"] += 1
        row = dict(
            session_id=self.session_id, seq=seq, game=card.game if card else (recog.game_from_back if recog else None),
            card_id=card.id if card else None, name=card.name if card else None,
            set_code=card.set_code if card else None, set_name=card.set_name if card else None,
            collector_number=card.collector_number if card else None, rarity=card.rarity if card else None,
            foil=int(bool(foil or (card and card.foil_only))), price_usd=price,
            confidence=round(recog.confidence, 3) if recog else 0.0, method=recog.method if recog else "none",
            bin=bin_, rule=rule, status=status, error=recog.error if recog else "recognizer crashed",
            front_path=front_path, back_path=back_path,
            candidates=[{"id": c.id, "label": c.label, "distance": round(d, 2)} for c, d in recog.candidates] if recog else [],
        )
        row_id = self.inventory.add_card(**row)
        self.last_card = dict(row, id=row_id, ts=time.time(), label=card.label if card else "Unknown card",
                              price_info=price_info, bin_name=self.bins[bin_]["name"] if bin_ < len(self.bins) else str(bin_))
        self.last_card.pop("candidates", None)
        self.history.appendleft(self.last_card)
        return row_id
