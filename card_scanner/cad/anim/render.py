#!/usr/bin/env python3
"""Render card_scanner/cad/anim/animate.html to frames + MP4 + GIF.

Serves ../ (the cad folder) over a local http.server in the background, drives the page's deterministic
window.setTime(t) hook with Playwright (chromium, 1280x720) and encodes with ffmpeg.

  python3 render.py                    # full render: frames/ -> card_scanner_cycle.mp4 + .gif
  python3 render.py --stills 3 8 12    # only PNG stills at those times -> stills/t_003.00.png
  python3 render.py --fps 30 --start 0 --end 36
"""
import argparse
import glob
import os
import socket
import subprocess
import sys
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread

HERE = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.dirname(HERE)
W, H = 1280, 720


def serve(root):
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Quiet)
    Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def open_page(pw, port):
    browser = pw.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                       "--ignore-gpu-blocklist"])
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    page.on("console", lambda m: print("  [page]", m.text) if m.type in ("error", "warning") else None)
    page.goto(f"http://127.0.0.1:{port}/anim/animate.html?t=0", wait_until="load")
    page.wait_for_function("window.ready === true", timeout=180_000)
    return browser, page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--stills", type=float, nargs="*", default=None, help="only render stills at these times")
    ap.add_argument("--no-encode", action="store_true")
    ap.add_argument("--frames-only", action="store_true")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    srv, port = serve(CAD)
    try:
        with sync_playwright() as pw:
            browser, page = open_page(pw, port)
            dur = page.evaluate("window.DURATION")
            end = a.end if a.end is not None else dur
            if a.stills is not None:
                out = os.path.join(HERE, "stills")
                os.makedirs(out, exist_ok=True)
                for t in a.stills:
                    page.evaluate(f"setTime({t})")
                    p = os.path.join(out, f"t_{t:06.2f}.png")
                    page.screenshot(path=p)
                    print("still", p)
                browser.close()
                return
            frames = os.path.join(HERE, "frames")
            os.makedirs(frames, exist_ok=True)
            for f in glob.glob(os.path.join(frames, "*.png")):
                os.remove(f)
            n = int(round((end - a.start) * a.fps))
            t0 = time.time()
            for i in range(n):
                t = a.start + i / a.fps
                page.evaluate(f"setTime({t:.4f})")
                page.screenshot(path=os.path.join(frames, f"f{i:05d}.png"))
                if i % 60 == 0:
                    el = time.time() - t0
                    print(f"  frame {i}/{n}  t={t:6.2f}s  {el:5.0f}s elapsed", flush=True)
            browser.close()
            print(f"captured {n} frames in {time.time() - t0:.0f}s")
    finally:
        srv.shutdown()
    if a.no_encode or a.frames_only:
        return
    encode(a.fps)


def encode(fps):
    frames = os.path.join(HERE, "frames", "f%05d.png")
    mp4 = os.path.join(HERE, "card_scanner_cycle.mp4")
    gif = os.path.join(HERE, "card_scanner_cycle.gif")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", frames,
                    "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", mp4], check=True)
    # GIF: 12 fps, 640 px wide, two-pass palette
    vf = "fps=12,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=160:stats_mode=diff[p];" \
         "[s1][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", frames,
                    "-vf", vf, "-loop", "0", gif], check=True)
    for p in (mp4, gif):
        print(f"{os.path.relpath(p, CAD)}  {os.path.getsize(p) / 1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--encode-only":
        encode(float(sys.argv[2]) if len(sys.argv) > 2 else 30)
    else:
        main()
