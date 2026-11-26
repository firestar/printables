#!/usr/bin/env python3
"""Build the release image for ESP Web Tools and write it with its manifest.

Builds the firmware, merges bootloader, partition table, boot_app0 and app into
one image flashed at offset 0, checks it for secrets, then writes
speaker-<version>.bin and manifest.json to lumen-house/public/firmware/speaker/.
Nothing is written if a check fails. Nothing is committed.

PlatformIO comes from <repo>/.pydeps, with its data in <repo>/.pio-core:

    pip3 install --target .pydeps platformio
    python3 smart_speaker/firmware/tools/build_release.py

Options: --skip-build reuses the last build, --check-only writes nothing, and
--forbid TEXT also fails if TEXT is in the image (your SSID, say; repeatable).
"""
import argparse
import json
import os
import pathlib
import re
import struct
import subprocess
import sys

FIRMWARE = pathlib.Path(__file__).resolve().parent.parent
REPO = FIRMWARE.parent.parent
PYDEPS = REPO / ".pydeps"
CORE_DIR = REPO / ".pio-core"
BUILD = FIRMWARE / ".pio" / "build" / "esp32dev"
DEFAULT_OUT = REPO / "lumen-house" / "public" / "firmware" / "speaker"
BOOT_APP0 = CORE_DIR / "packages" / "framework-arduinoespressif32" / "tools" / "partitions" / "boot_app0.bin"
ESPTOOL = CORE_DIR / "packages" / "tool-esptoolpy" / "esptool.py"

# Flash layout of the esp32dev board with min_spiffs.csv. check_layout() confirms
# these against the partition table that was actually built.
BOOTLOADER_OFFSET = 0x1000
PARTITIONS_OFFSET = 0x8000
BOOT_APP0_OFFSET = 0xE000
APP_OFFSET = 0x10000
FLASH_ARGS = ["--flash_mode", "dio", "--flash_freq", "40m", "--flash_size", "4MB"]

# A credential written into the source as a quoted literal.
SOURCE_SECRET = re.compile(
    r"""(?ix)
    \b(?:password|passwd|pass|psk|ssid|token|secret|api_?key|auth_?key)\w*\s*=\s*"[^"]+"
    | WiFi\.begin\(\s*"
    | -D\s*\w*(?:PASS|PSK|SSID|TOKEN|SECRET|KEY)\w*
    """
)
# Shapes of real credentials in the image.
IMAGE_SECRETS = {
    "private key": rb"-----BEGIN [A-Z ]*PRIVATE KEY",
    "AWS access key": rb"AKIA[0-9A-Z]{16}",
    "GitHub token": rb"gh[pousr]_[A-Za-z0-9]{30,}",
    "Slack token": rb"xox[abprs]-[A-Za-z0-9-]{10,}",
    "API key": rb"sk-[A-Za-z0-9_-]{20,}",
    "assigned credential": rb"(?i)(?:password|passwd|psk|token|secret)[\"']?\s*[=:]\s*[\"'][^\"'\s]{4,}[\"']",
}
SECRET_ENV_NAME = re.compile(r"(?i)token|passw|secret|api_?key|credential|psk")


def fail(msg):
    sys.exit(f"build_release: {msg}")


def define(name):
    config = (FIRMWARE / "include" / "config.h").read_text()
    m = re.search(rf'^#define {name} "([^"]+)"', config, re.M)
    if not m:
        fail(f"{name} not found in config.h")
    return m.group(1)


def tool_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PYDEPS)
    env["PLATFORMIO_CORE_DIR"] = str(CORE_DIR)
    env["PLATFORMIO_SETTING_ENABLE_TELEMETRY"] = "no"
    return env


def build():
    if not (PYDEPS / "platformio").exists():
        fail(f"PlatformIO not found: pip3 install --target {PYDEPS} platformio")
    subprocess.run(
        [sys.executable, "-m", "platformio", "run", "-e", "esp32dev", "-d", str(FIRMWARE)],
        env=tool_env(),
        check=True,
    )


def read_partitions():
    """Returns {label: (type, offset, size)} from the built partition table."""
    data = (BUILD / "partitions.bin").read_bytes()
    table = {}
    for pos in range(0, len(data), 32):
        magic, ptype, _subtype, offset, size, label, _flags = struct.unpack_from("<HBBII16sI", data, pos)
        if magic != 0x50AA:
            break
        table[label.split(b"\0")[0].decode()] = (ptype, offset, size)
    return table


def check_layout(partitions, app_size):
    for label in ("nvs", "otadata", "app0"):
        if label not in partitions:
            fail(f"no {label} partition in the partition table")
    if partitions["app0"][1] != APP_OFFSET:
        fail(f"app0 is at {partitions['app0'][1]:#x}, expected {APP_OFFSET:#x}")
    if partitions["otadata"][1] != BOOT_APP0_OFFSET:
        fail(f"otadata is at {partitions['otadata'][1]:#x}, expected {BOOT_APP0_OFFSET:#x}")
    if app_size > partitions["app0"][2]:
        fail(f"app is {app_size} bytes but its slot holds {partitions['app0'][2]}")


def merge(out):
    for path in (BUILD / "bootloader.bin", BUILD / "partitions.bin", BOOT_APP0, BUILD / "firmware.bin", ESPTOOL):
        if not path.exists():
            fail(f"missing {path}")
    subprocess.run(
        [sys.executable, str(ESPTOOL), "--chip", "esp32", "merge_bin", "-o", str(out), *FLASH_ARGS,
         hex(BOOTLOADER_OFFSET), str(BUILD / "bootloader.bin"),
         hex(PARTITIONS_OFFSET), str(BUILD / "partitions.bin"),
         hex(BOOT_APP0_OFFSET), str(BOOT_APP0),
         hex(APP_OFFSET), str(BUILD / "firmware.bin")],
        env=tool_env(),
        check=True,
    )


def check_source():
    """Credentials written into the code or build flags."""
    problems = []
    files = [FIRMWARE / "platformio.ini"]
    files += sorted((FIRMWARE / "src").glob("*")) + sorted((FIRMWARE / "include").glob("*"))
    for path in files:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if SOURCE_SECRET.search(line):
                problems.append(f"{path.relative_to(FIRMWARE)}:{number}: looks like a hardcoded credential")
    return problems


def check_image(image, forbidden, partitions):
    """Secrets in the built image. Messages never print the matched value."""
    problems = []
    for what, pattern in IMAGE_SECRETS.items():
        count = len(re.findall(pattern, image))
        if count:
            problems.append(f"image contains {count} match(es) for: {what}")
    # A secret in this machine's environment must not have leaked in through the
    # build. Reported by variable name only.
    checked = 0
    for name, value in os.environ.items():
        if SECRET_ENV_NAME.search(name) and len(value) >= 8:
            checked += 1
            if value.encode() in image:
                problems.append(f"image contains the value of ${name}")
    print(f"secrets check: compared against {checked} secret-looking environment variable(s)")
    for text in forbidden:
        if text.encode() in image:
            problems.append("image contains a string passed with --forbid")
    # Saved settings and Wi-Fi live in NVS, which must be blank in a release.
    _, nvs_offset, nvs_size = partitions["nvs"]
    region = image[nvs_offset:nvs_offset + nvs_size]
    if region.strip(b"\xff"):
        problems.append("the NVS region of the image isn't blank: it may hold saved settings or Wi-Fi")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.skip_build:
        build()

    version = define("FW_VERSION")
    name = define("FW_NAME")
    partitions = read_partitions()
    app_size = (BUILD / "firmware.bin").stat().st_size
    check_layout(partitions, app_size)

    scratch = BUILD / "merged.bin"
    merge(scratch)
    image = scratch.read_bytes()

    problems = check_source() + check_image(image, args.forbid, partitions)
    if problems:
        fail("secrets check FAILED, nothing written:\n  " + "\n  ".join(problems))
    print("secrets check: passed")

    slot = partitions["app0"][2]
    print(f"app: {app_size} bytes, {100 * app_size / slot:.1f}% of its {slot} byte slot")
    print(f"merged image: {len(image)} bytes, to flash at offset 0")

    if args.check_only:
        print("--check-only: nothing written")
        return

    filename = f"speaker-{version}.bin"
    manifest = {
        "name": name,
        "version": version,
        # Only offered on a new install. The image overwrites NVS either way, so
        # this is about clearing leftovers from whatever firmware was there before.
        "new_install_prompt_erase": True,
        "builds": [{"chipFamily": "ESP32", "parts": [{"path": filename, "offset": 0}]}],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("speaker-*.bin"):
        if old.name != filename:
            old.unlink()
    (args.out / filename).write_bytes(image)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.out / filename}")
    print(f"wrote {args.out / 'manifest.json'}")


if __name__ == "__main__":
    main()
