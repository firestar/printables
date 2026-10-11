#!/usr/bin/env python3
"""Software stand-in for the speaker: implements PROTOCOL.md so the hub can
be developed without hardware.  Mic frames are a 300 Hz tone + noise;
played audio is consumed in real time (optionally saved to a WAV).

  pip install websockets
  python3 mock_speaker.py [--port 8080] [--token secret] [--save played.wav]
"""
import argparse
import asyncio
import json
import math
import random
import struct
import time
import wave

import websockets

FRAME_MIC, FRAME_SPK = 0x01, 0x02
SPK_BUF = 32 * 1024
MIC_RATE, MIC_FRAME = 16000, 512


class Mock:
    def __init__(self, token, save):
        self.token, self.save = token, save
        self.state = {
            "name": "mock-speaker", "id": "roundspk-mock", "fw": "mock",
            "volume": 60,
            "mic": {"enabled": False, "rate": MIC_RATE, "bits": 16, "channels": 1, "gain_db": 12.0, "duck": False},
            "spk": {"rate": 16000, "bits": 16, "channels": 1, "buffer": SPK_BUF, "queued": 0},
            "led": {"mode": "idle", "color": "#0060FF", "brightness": 200, "max": 150, "count": 39},
        }
        self.queued = 0
        self.play_end = False
        self.played = bytearray()

    def full(self, t, **extra):
        return json.dumps({"type": t, **self.state, **extra})

    async def handler(self, ws):
        authed = not self.token
        await ws.send(self.full("hello", auth_required=bool(self.token)))
        tasks = [asyncio.create_task(self.mic_loop(ws)), asyncio.create_task(self.spk_loop(ws))]
        try:
            async for m in ws:
                if isinstance(m, bytes):
                    if authed and m and m[0] == FRAME_SPK:
                        n = len(m) - 1
                        room = SPK_BUF - self.queued
                        take = min(n, room)
                        self.queued += take
                        self.played += m[1:1 + take]
                    continue
                c = json.loads(m)
                t = c.get("type")
                if t == "hello":
                    if self.token and c.get("token") != self.token:
                        await ws.send(json.dumps({"type": "error", "msg": "bad token"}))
                        return
                    authed = True
                    await ws.send(self.full("ready"))
                elif not authed:
                    await ws.send(json.dumps({"type": "error", "msg": "not authenticated"}))
                elif t == "ping":
                    await ws.send(json.dumps({"type": "pong", "id": c.get("id"), "t": int(time.monotonic() * 1000)}))
                elif t == "get_state":
                    await ws.send(self.full("state"))
                elif t == "mic":
                    for k in ("enable", "channels", "gain_db", "duck"):
                        if k in c:
                            self.state["mic"]["enabled" if k == "enable" else k] = c[k]
                    await ws.send(self.full("state"))
                elif t == "play_start":
                    self.state["spk"]["rate"] = c.get("rate", self.state["spk"]["rate"])
                    self.play_end = False
                    await ws.send(json.dumps({"type": "play_ready", "rate": self.state["spk"]["rate"],
                                              "free": SPK_BUF - self.queued}))
                elif t == "play_end":
                    self.play_end = True
                elif t == "stop":
                    self.queued, self.play_end = 0, False
                    await ws.send(json.dumps({"type": "play_done", "stopped": True}))
                elif t == "volume":
                    self.state["volume"] = max(0, min(100, int(c.get("value", 60))))
                    await ws.send(self.full("state"))
                elif t == "led":
                    for k in ("mode", "color", "brightness"):
                        if k in c:
                            v = c[k]
                            if k == "color" and isinstance(v, list):
                                v = "#%02X%02X%02X" % tuple(v)
                            self.state["led"][k] = v
                    print("LED ->", self.state["led"])
                    await ws.send(self.full("state"))
                else:
                    await ws.send(json.dumps({"type": "error", "msg": "unknown command"}))
        finally:
            for t in tasks:
                t.cancel()
            if self.save and self.played:
                with wave.open(self.save, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(self.state["spk"]["rate"])
                    w.writeframes(bytes(self.played))
                print(f"saved {len(self.played)} bytes to {self.save}")

    async def mic_loop(self, ws):
        phase, period = 0, MIC_FRAME / MIC_RATE
        next_t = time.monotonic()
        while True:
            next_t += period
            await asyncio.sleep(max(0, next_t - time.monotonic()))
            if not self.state["mic"]["enabled"]:
                continue
            ch = self.state["mic"]["channels"]
            s = []
            for i in range(MIC_FRAME):
                v = int(6000 * math.sin(2 * math.pi * 300 * (phase + i) / MIC_RATE) + random.gauss(0, 300))
                s += [v] * ch
            phase += MIC_FRAME
            await ws.send(bytes([FRAME_MIC]) + struct.pack(f"<{len(s)}h", *s))

    async def spk_loop(self, ws):
        last = time.monotonic()
        report = 0.0
        while True:
            await asyncio.sleep(0.02)
            now = time.monotonic()
            self.queued = max(0, self.queued - int((now - last) * self.state["spk"]["rate"] * 2))
            last = now
            if (self.queued or self.play_end) and now - report > 0.1:
                report = now
                await ws.send(json.dumps({"type": "play_buffer", "free": SPK_BUF - self.queued,
                                          "queued": self.queued}))
            if self.play_end and self.queued == 0:
                self.play_end = False
                await ws.send(json.dumps({"type": "play_done", "stopped": False}))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--token", default="")
    ap.add_argument("--save")
    a = ap.parse_args()
    mock = Mock(a.token, a.save)
    async with websockets.serve(mock.handler, "0.0.0.0", a.port, max_size=None):
        print(f"mock speaker on ws://0.0.0.0:{a.port}/")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
