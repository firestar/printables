"""FastAPI web UI + JSON API served on the Pi."""

import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import GAME_LABELS, GAMES, RARITIES
from ..protocol import McuError
from ..rules import CONDITION_KEYS, validate
from .. import __version__

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


class StartBody(BaseModel):
    notes: str = ""
    foil: bool = False
    condition: str = "NM"


class ResolveBody(BaseModel):
    card_id: str


class RulesBody(BaseModel):
    rules: list
    default_bin: int = 2


class TunableBody(BaseModel):
    key: str
    value: Any


class MockBody(BaseModel):
    hopper: Optional[int] = None
    magazine: Optional[int] = None


def create_app(app):
    """`app` is an app_factory.App; returns the FastAPI instance."""
    api = FastAPI(title="Card Scanner", version=__version__)
    m = app.machine

    api.mount("/files", StaticFiles(directory=str(app.cfg.paths["data_dir"])), name="files")
    api.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    @api.get("/")
    def root():
        return FileResponse(STATIC / "index.html")

    # --- status / control -------------------------------------------------------------
    @api.get("/api/status")
    def status():
        snap = m.snapshot()
        snap["mock"] = bool(app.mock)
        snap["ocr_available"] = app.ocr.enabled
        snap["index_count"] = app.index.count()
        snap["review_queue"] = len(app.inventory.review_queue(limit=10000))
        return snap

    @api.post("/api/control/start")
    def start(body: StartBody = StartBody()):
        try:
            sid = m.start(notes=body.notes, foil=body.foil, condition=body.condition)
        except (RuntimeError, McuError) as e:
            raise HTTPException(409, str(e))
        return {"session_id": sid}

    @api.post("/api/control/{action}")
    def control(action: str):
        try:
            if action == "pause":
                m.pause("operator")
            elif action == "resume":
                m.resume()
            elif action == "stop":
                m.stop(wait=False)
            elif action == "reset":
                m.reset()
            elif action == "home":
                m.home()
            elif action == "estop":
                app.mcu.estop()
            else:
                raise HTTPException(404, "unknown action")
        except (RuntimeError, McuError) as e:
            raise HTTPException(409, str(e))
        return {"ok": True}

    # --- cards / review -------------------------------------------------------------------
    @api.get("/api/cards")
    def cards(session: Optional[str] = None, status: Optional[str] = None, limit: int = 100, offset: int = 0):
        return app.inventory.list_cards(session, status.split(",") if status else None, limit, offset)

    @api.get("/api/sessions")
    def sessions():
        return app.inventory.sessions()

    @api.get("/api/review")
    def review(session: Optional[str] = None):
        return app.inventory.review_queue(session)

    @api.post("/api/review/{row_id}/resolve")
    def resolve(row_id: int, body: ResolveBody):
        row = app.inventory.get_card(row_id)
        if not row:
            raise HTTPException(404, "no such card")
        rec = app.index.get(body.card_id)
        if not rec:
            raise HTTPException(404, "card id not in index")
        price, _ = app.prices.get(rec, foil=bool(row.get("foil")))
        app.inventory.resolve(row_id, rec, price)
        return app.inventory.get_card(row_id)

    @api.post("/api/review/{row_id}/skip")
    def skip(row_id: int):
        app.inventory.skip(row_id)
        return {"ok": True}

    @api.get("/api/index/search")
    def index_search(q: str = "", game: Optional[str] = None, limit: int = Query(20, le=50)):
        return [dict(r.to_dict(), label=r.label) for r in app.index.search(q, game or None, limit)]

    @api.get("/api/index/stats")
    def index_stats():
        return {"count": app.index.count(), "games": {g: app.index.count(g) for g in app.index.games()},
                "backs": sorted(app.index._backs.keys())}

    # --- rules -------------------------------------------------------------------------------
    @api.get("/api/rules")
    def get_rules():
        return {"rules": app.cfg.rules, "default_bin": app.cfg.default_bin, "bins": app.cfg["bins"]}

    @api.get("/api/rules/options")
    def rule_options():
        return {"games": [{"value": g, "label": GAME_LABELS[g]} for g in GAMES], "rarities": RARITIES,
                "conditions": CONDITION_KEYS, "bins": app.cfg["bins"]}

    @api.put("/api/rules")
    def put_rules(body: RulesBody):
        errs = validate(body.rules, len(app.cfg["bins"]))
        if not (0 <= body.default_bin < len(app.cfg["bins"])):
            errs.append("default_bin out of range")
        if errs:
            raise HTTPException(422, "; ".join(errs))
        app.update_rules(body.rules, body.default_bin)
        return get_rules()

    # --- tunables ------------------------------------------------------------------------------
    @api.get("/api/tunables")
    def tunables():
        out = []
        for key in app.cfg["tunables"]:
            try:
                r = app.mcu.get(key)
                out.append({"key": key, "value": r.get("value"), "ok": True})
            except McuError as e:
                out.append({"key": key, "value": None, "ok": False, "error": str(e)})
        return out

    @api.post("/api/tunables")
    def set_tunable(body: TunableBody):
        try:
            r = app.mcu.set(body.key, body.value)
        except McuError as e:
            raise HTTPException(409, str(e))
        if body.key not in app.cfg["tunables"]:
            app.cfg["tunables"].append(body.key)
        return {"key": body.key, "value": r.get("value", body.value)}

    @api.get("/api/mcu/status")
    def mcu_status():
        try:
            return app.mcu.status()
        except McuError as e:
            raise HTTPException(409, str(e))

    # --- export ----------------------------------------------------------------------------------
    @api.get("/api/export.csv")
    def export(format: str = "moxfield", session: Optional[str] = None):
        if format not in ("moxfield", "tcgplayer", "full"):
            raise HTTPException(400, "format must be moxfield|tcgplayer|full")
        csv = app.inventory.export_csv(format, session)
        name = "cards-%s%s.csv" % (format, "-" + session if session else "")
        return Response(csv, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="%s"' % name})

    # --- mock helpers (only with the mock MCU) ----------------------------------------------------------
    @api.post("/api/mock/refill")
    def mock_refill(body: MockBody = MockBody()):
        if not app.mock_mcu:
            raise HTTPException(404, "not running the mock controller")
        app.mock_mcu.refill(body.hopper if body.hopper is not None else 30,
                            body.magazine if body.magazine is not None else None)
        return {"hopper": app.mock_mcu.hopper, "magazine": app.mock_mcu.magazine}

    @api.post("/api/mock/{what}")
    def mock_action(what: str):
        if not app.mock_mcu:
            raise HTTPException(404, "not running the mock controller")
        if what == "estop":
            app.mock_mcu.trip_estop()
        elif what == "lid":
            app.mock_mcu.open_lid(True)
        else:
            raise HTTPException(404, "unknown mock action")
        return {"ok": True}

    @api.get("/healthz", response_class=PlainTextResponse)
    def healthz():
        return "ok"

    return api
