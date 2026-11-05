"""UX3a2 — Nachweis: Gäste-Sicht (untere Leiste + aufgeklapptes „Mehr“-Blatt).

Kleiner Zusatz zu ux3a2-screenshots.py: öffnet das „Mehr“-Blatt und klappt die
Gruppe „Navigation“ auf, sodass ALLE Ziele des Gastes im Bild stehen. Damit ist
belegbar, dass „Dienste“ fehlt (UX3a2 F4).

Aufruf im eigenen Stack (nie der Betrieb)::

    docker run --rm --network ux3a2_pruefnetz \
        -v "<repo>/tools":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 \
        -e GAST_EMAIL=... -e GAST_PASS=... \
        diakronos-ux3a2-pw:test python /w/demo/ux3a2-gast.py
"""

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
GAST_EMAIL = os.environ["GAST_EMAIL"]
GAST_PASS = os.environ["GAST_PASS"]
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")

fehler: list[str] = []


def anmelden(page, benutzer, passwort) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('#dk-usr, input[name="usr"]', benutzer)
    page.fill('#dk-pwd, input[name="pwd"]', passwort)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_load_state("networkidle")


def main() -> int:
    ordner = os.path.join(ZIEL, MARKER, "mobil", "hell")
    os.makedirs(ordner, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            has_touch=True, is_mobile=True, locale="de-DE",
        )
        page = context.new_page()
        page.on("pageerror", lambda e: fehler.append(str(e)))
        anmelden(page, GAST_EMAIL, GAST_PASS)
        page.goto(f"{BASE}/#/", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # Untere Leiste: welche Tabs stehen dort?
        tabs = [t.strip() for t in page.locator(".dk-bn-tab").all_inner_texts()]
        print(f"[ux3a2] untere Leiste (Gast): {tabs}")
        if any("Dienste" in t for t in tabs):
            fehler.append("untere Leiste zeigt „Dienste“ für Gäste")
        page.screenshot(path=os.path.join(ordner, "07-gast-untere-leiste.png"))

        # „Mehr“-Blatt öffnen und die Gruppe „Navigation“ aufklappen.
        mehr = page.locator(".dk-bn-tab", has_text="Mehr").first
        if mehr.count():
            mehr.click()
            page.wait_for_timeout(400)
            auf = page.locator(".dk-sheet, [role='dialog']").last
            knopf = page.get_by_text("Navigation", exact=False).first
            if knopf.count():
                knopf.click()
                page.wait_for_timeout(400)
            sichtbar = page.locator(".dk-sheet, [role='dialog']").last
            text = sichtbar.inner_text() if sichtbar.count() else ""
            print("[ux3a2] Mehr-Blatt (Gast):", " | ".join(
                t.strip() for t in text.splitlines() if t.strip()))
            if "Dienste" in text:
                fehler.append("Mehr-Blatt zeigt „Dienste“ für Gäste")
            page.screenshot(path=os.path.join(ordner, "08-gast-mehr-blatt-offen.png"))
        context.close()
        browser.close()
    if fehler:
        print("[ux3a2] Befund:", *fehler, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
