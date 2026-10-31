#!/usr/bin/env python3
"""Drive the running web UI with Playwright and save screenshots as proof.

  python -m cardscanner -c config.demo.yaml demo
  python -m cardscanner -c config.demo.yaml run &
  python tools/ui_walkthrough.py --url http://127.0.0.1:8089 --out docs/screenshots

Steps: start a batch, wait until the hopper runs dry, open the review queue, use the
combobox to assign a card, edit a bin rule and save, open the tunables page.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def status(url):
    with urllib.request.urlopen(url + "/api/status") as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8089")
    ap.add_argument("--out", default="docs/screenshots")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    shots = []

    def shot(page, name, full=False):
        p = out / (name + ".png")
        page.screenshot(path=str(p), full_page=full)
        shots.append(p)
        print("saved", p)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860})
        page.goto(a.url + "/")
        page.wait_for_selector("#btn-start:not([disabled])", timeout=15000)
        shot(page, "01_dashboard_idle")

        # --- run a batch until the mock hopper is empty ----------------------------
        page.click("#btn-start")
        page.wait_for_function("document.querySelector('#state-badge').textContent === 'running'", timeout=15000)
        time.sleep(6)
        shot(page, "02_dashboard_running")
        t0 = time.time()
        while time.time() - t0 < 90:
            s = status(a.url)
            if s["state"] == "paused" and s["pause_reason"] == "hopper_empty":
                break
            time.sleep(1)
        time.sleep(1.2)
        shot(page, "03_dashboard_hopper_empty")
        assert s["stats"]["processed"] >= 10, s["stats"]
        assert s["stats"]["rejected"] >= 1, "expected the scripted double feed"

        # --- review queue + combobox ------------------------------------------------------
        page.click("button.tab[data-tab=review]")
        page.wait_for_selector(".review-item", timeout=10000)
        n_before = page.locator(".review-item").count()
        assert n_before >= 1
        first = page.locator(".review-item").first
        combo = first.locator(".combo-input")
        combo.click()
        combo.type("volt", delay=40)
        page.wait_for_selector(".combo-list li[data-i]", timeout=5000)
        shot(page, "04_review_combobox_open")
        first.locator(".combo-list li[data-i]").first.click()
        page.wait_for_function("document.querySelector('.review-item .rv-assign') && !document.querySelector('.review-item .rv-assign').disabled")
        shot(page, "05_review_option_selected")
        first.locator(".rv-assign").click()
        page.wait_for_function("document.querySelectorAll('.review-item').length === %d" % (n_before - 1), timeout=5000)
        shot(page, "06_review_after_assign")
        resolved = [c for c in json.load(urllib.request.urlopen(a.url + "/api/cards?status=resolved"))]
        assert resolved and resolved[0]["name"] == "Voltmouse", resolved

        # --- rules editor -------------------------------------------------------------------
        page.click("button.tab[data-tab=rules]")
        page.wait_for_selector("#rules-table tbody tr", timeout=10000)
        shot(page, "07_rules_editor")
        row = page.locator("#rules-table tbody tr").first
        row.locator(".r-minp").fill("3.5")
        row.locator(".r-game").select_option("mtg")
        row.locator(".r-rarity").select_option(["rare", "mythic"])
        page.click("#rule-add")
        new = page.locator("#rules-table tbody tr").last
        new.locator(".r-name").fill("Pokémon holo")
        new.locator(".r-game").select_option("pokemon")
        new.locator(".r-foil").select_option("yes")
        new.locator(".r-bin").select_option("0")
        page.click("#rules-save")
        page.wait_for_function("document.querySelector('#rules-msg').textContent.startsWith('Saved')", timeout=5000)
        shot(page, "08_rules_saved")
        rules = json.load(urllib.request.urlopen(a.url + "/api/rules"))["rules"]
        assert rules[0]["when"]["min_price"] == 3.5 and rules[0]["when"]["game"] == "mtg"
        assert rules[0]["when"]["rarity"] == ["rare", "mythic"]
        assert rules[-1]["name"] == "Pokémon holo" and rules[-1]["when"]["foil"] is True

        # --- tunables -------------------------------------------------------------------------
        page.click("button.tab[data-tab=tunables]")
        page.wait_for_selector("#tunables-table tbody tr", timeout=10000)
        trow = page.locator("#tunables-table tbody tr").first
        trow.locator(".t-val").fill("75")
        trow.locator(".t-set").click()
        page.wait_for_function("document.querySelector('#tun-msg').textContent.includes('75')", timeout=5000)
        shot(page, "09_tunables")

        # --- mobile layout ----------------------------------------------------------------------
        page.set_viewport_size({"width": 420, "height": 860})
        page.click("button.tab[data-tab=dashboard]")
        time.sleep(0.5)
        shot(page, "10_dashboard_mobile")
        browser.close()
    print("OK: %d screenshots" % len(shots))


if __name__ == "__main__":
    main()
