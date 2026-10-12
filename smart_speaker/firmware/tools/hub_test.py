#!/usr/bin/env python3
"""Minimal test hub for the round speaker (see ../PROTOCOL.md).

  pip install websockets zeroconf

  python3 hub_test.py discover
  python3 hub_test.py state   --host roundspk-xxxx.local
  python3 hub_test.py record  --host ... --seconds 5 --out mic.wav [--stereo]
  python3 hub_test.py play    --host ... file.wav        (16-bit PCM, mono or stereo)
  python3 hub_test.py tone    --host ... [--freq 440 --seconds 2]
  python3 hub_test.py led     --host ... --mode rainbow [--color "#ff0080"] [--brightness 200]
  python3 hub_test.py volume  --host ... 50
  python3 hub_test.py loop    --host ... --seconds 5     (record, then play it back)

Add --token if the speaker has one set.
"""
import argparse
import asyncio
import json
import math
import struct
import sys
import time
import wave

import websockets

FRAME_MIC, FRAME_SPK = 0x01, 0x02
CHUNK = 4096


class Speaker:
    def __init__(self, host, port=8080, token=""):
        self.url = f"ws://{host}:{port}/"
        self.token = token
        self.ws = None
        self.free = 0
        self.events = asyncio.Queue()
        self.mic = asyncio.Queue()
        self.state = {}

    async def connect(self):
        self.ws = await websockets.connect(self.url, max_size=None)
        hello = json.loads(await self.ws.recv())
        self.state = hello
        await self.send({"type": "hello", "token": self.token})
        asyncio.create_task(self._reader())
        while True:  # ready, or the speaker refuses (bad token) and closes
            msg = await asyncio.wait_for(self.events.get(), 10)
            if msg.get("type") == "error":
                sys.exit(f"speaker refused connection: {msg.get('msg')}")
            if msg.get("type") == "ready":
                break
        self.state = msg
        return msg

    async def _reader(self):
        async for m in self.ws:
            if isinstance(m, bytes):
                if m and m[0] == FRAME_MIC:
                    await self.mic.put(m[1:])
                continue
            msg = json.loads(m)
            if msg.get("type") == "play_buffer":
                self.free = msg["free"]
            if msg.get("type") == "error":
                print("speaker error:", msg.get("msg"), file=sys.stderr)
            await self.events.put(msg)

    async def send(self, obj):
        await self.ws.send(json.dumps(obj))

    async def wait(self, type_, timeout=10):
        end = time.monotonic() + timeout
        while True:
            msg = await asyncio.wait_for(self.events.get(), max(0.1, end - time.monotonic()))
            if msg.get("type") == type_:
                return msg

    async def play_pcm(self, pcm: bytes, rate: int):
        await self.send({"type": "play_start", "rate": rate})
        ready = await self.wait("play_ready")
        self.free = ready["free"]
        await self.send({"type": "led", "mode": "speaking"})
        bytes_per_s = rate * 2
        t0 = time.monotonic()
        sent = 0
        lead = int(0.3 * bytes_per_s)  # stay ~300 ms ahead of the DAC
        while sent < len(pcm):
            played = (time.monotonic() - t0) * bytes_per_s
            if sent - played > lead:
                await asyncio.sleep(0.01)
                continue
            chunk = pcm[sent:sent + CHUNK]
            await self.ws.send(bytes([FRAME_SPK]) + chunk)
            sent += len(chunk)
        await self.send({"type": "play_end"})
        await self.wait("play_done", timeout=len(pcm) / bytes_per_s + 5)
        await self.send({"type": "led", "mode": "idle"})

    async def record(self, seconds, channels=1):
        while not self.mic.empty():
            self.mic.get_nowait()
        await self.send({"type": "mic", "enable": True, "channels": channels})
        await self.send({"type": "led", "mode": "listening"})
        need = int(seconds * 16000 * 2 * channels)
        buf = bytearray()
        while len(buf) < need:
            buf += await asyncio.wait_for(self.mic.get(), 5)
        await self.send({"type": "mic", "enable": False})
        await self.send({"type": "led", "mode": "idle"})
        return bytes(buf[:need])


def to_mono16(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            sys.exit("WAV must be 16-bit PCM")
        rate, ch, frames = w.getframerate(), w.getnchannels(), w.readframes(w.getnframes())
    if ch == 2:
        s = struct.unpack(f"<{len(frames) // 2}h", frames)
        frames = struct.pack(f"<{len(s) // 2}h", *[(s[i] + s[i + 1]) // 2 for i in range(0, len(s), 2)])
    if not 8000 <= rate <= 48000:
        sys.exit("sample rate must be 8000-48000")
    return frames, rate


async def discover():
    from zeroconf import ServiceBrowser, Zeroconf
    found = []

    class L:
        def add_service(self, zc, t, name):
            info = zc.get_service_info(t, name)
            if info:
                props = {k.decode(): v.decode() for k, v in info.properties.items()}
                found.append((info.server, info.parsed_addresses(), info.port, props))

        def update_service(self, *a):
            pass

        def remove_service(self, *a):
            pass

    zc = Zeroconf()
    ServiceBrowser(zc, "_roundspk._tcp.local.", L())
    await asyncio.sleep(3)
    zc.close()
    for server, addrs, port, props in found:
        print(f"{props.get('name')}  {server}  {addrs}  port {port}  {props}")
    if not found:
        print("no speakers found")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "state", "record", "play", "tone", "led", "volume", "loop"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--token", default="")
    ap.add_argument("--seconds", type=float, default=5)
    ap.add_argument("--out", default="mic.wav")
    ap.add_argument("--stereo", action="store_true")
    ap.add_argument("--freq", type=float, default=440)
    ap.add_argument("--mode")
    ap.add_argument("--color")
    ap.add_argument("--brightness", type=int)
    a = ap.parse_args()

    if a.cmd == "discover":
        return await discover()
    if not a.host:
        sys.exit("--host required")

    spk = Speaker(a.host, a.port, a.token)
    ready = await spk.connect()

    if a.cmd == "state":
        print(json.dumps(ready, indent=2))
    elif a.cmd == "record":
        ch = 2 if a.stereo else 1
        pcm = await spk.record(a.seconds, ch)
        with wave.open(a.out, "wb") as w:
            w.setnchannels(ch)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(pcm)
        print(f"wrote {a.out}")
    elif a.cmd == "play":
        pcm, rate = to_mono16(a.arg)
        await spk.play_pcm(pcm, rate)
    elif a.cmd == "tone":
        rate = 16000
        n = int(a.seconds * rate)
        pcm = struct.pack(f"<{n}h", *[int(12000 * math.sin(2 * math.pi * a.freq * i / rate)) for i in range(n)])
        await spk.play_pcm(pcm, rate)
    elif a.cmd == "led":
        cmd = {"type": "led"}
        if a.mode:
            cmd["mode"] = a.mode
        if a.color:
            cmd["color"] = a.color
        if a.brightness is not None:
            cmd["brightness"] = a.brightness
        await spk.send(cmd)
        print(json.dumps((await spk.wait("state"))["led"]))
    elif a.cmd == "volume":
        await spk.send({"type": "volume", "value": int(a.arg)})
        print("volume", (await spk.wait("state"))["volume"])
    elif a.cmd == "loop":
        pcm = await spk.record(a.seconds)
        await spk.play_pcm(pcm, 16000)
    await spk.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
