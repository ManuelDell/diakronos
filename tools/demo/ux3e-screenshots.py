"""UX3e — Abnahme-Screenshots der Handy-Navigation (Leiste unten + Menü oben links).

Läuft im Playwright-Image gegen einen EIGENEN Wegwerf-Stack mit den Demo-Daten
(Musterhausen). Aufgenommen wird Mobil 390×844 (Entwurf A8/A9) in hell und
dunkel, plus Desktop 1440×900 als Gegenprobe (dort muss das Menü-Symbol weg und
die Seitenleiste da sein).

    docker run --rm --network <projekt>_default \
        -v "<worktree>":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe -e MARKER=vorher \
        -e ADMIN_EMAIL=admin@example.org -e ADMIN_PASS=musterhausen-demo \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux3e-screenshots.py

Gemessen wird zusätzlich (Ausgabe in der Konsole, exit 1 bei Befund):
  * Zahl der Tabs in der unteren Leiste (soll 5, kein „Mehr“),
  * Sichtbarkeit des Menü-Knopfs (Mobil: sichtbar, Desktop: nicht),
  * Trefferfläche jedes Tabs und jedes Schubladenpunkts (>= 44 px),
  * Schublade: Esc schließt, Wischen nach links schließt, sie geht auf.

Die Bilder sind Abnahme-Belege (erfundene Demo-Daten), keine Veröffentlichung.
"""

import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "jetzt")

MOBIL = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 900}

fehler: list[str] = []


def anmelden(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('#dk-usr, input[name="usr"]', BENUTZER)
    page.fill('#dk-pwd, input[name="pwd"]', PASSWORT)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_load_state("networkidle")


def schuss(page, ordner: str, name: str) -> None:
    pfad = os.path.join(ZIEL, MARKER, ordner)
    os.makedirs(pfad, exist_ok=True)
    ziel = os.path.join(pfad, name + ".png")
    page.screenshot(path=ziel)
    print(f"[ux3e] Bild: {ziel}")


def pruefe(was: str, ok: bool, detail: str = "") -> None:
    print(f"[ux3e] {'OK  ' if ok else 'FEHL'} {was}{(' — ' + detail) if detail else ''}")
    if not ok:
        fehler.append(f"{was}{(' — ' + detail) if detail else ''}")


def thema_setzen(page, thema: str) -> None:
    """Theme über den ECHTEN Weg setzen: die App liest beim Aufbau
    `localStorage['dk-theme']` (composables/theme.mjs), sonst die
    Systemeinstellung. Ein `data-theme` am <html> VON HAND zu setzen hilft
    nicht — die Hash-Navigation baut die App nicht neu auf, und ein
    Seitenaufruf setzt den Wert aus dem Speicher erneut (im Test gemessen:
    localStorage 'dark', aber data-theme blieb 'light').

    Deshalb VOR dem Laden setzen — so wie der Umschalter es tut."""
    # ACHTUNG: Der gespeicherte Wert heißt 'light'/'dark' (startTheme in
    # composables/theme.mjs) — NICHT 'hell'/'dunkel'. Ein deutscher Wert wird
    # beim Start verworfen, die Aufnahme wäre hell (im Test gemessen).
    gespeichert = "dark" if thema == "dunkel" else "light"
    page.add_init_script(f"try {{ localStorage.setItem('dk-theme', {gespeichert!r}) }} catch (e) {{}}")
    # Echte Adresse laden (kein reiner Hash-Wechsel): erst dadurch baut sich
    # die App mit dem gespeicherten Theme auf.
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(500)
    ist = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    pruefe(f"Theme {thema} aktiv", ist == gespeichert, f"data-theme={ist!r}")


def mobil_aufnahmen(page, thema: str) -> None:
    thema_setzen(page, thema)
    ordner = f"mobil/{thema}"

    # 1) Übersicht: Leiste unten + Menü oben links
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(400)
    schuss(page, ordner, "01-uebersicht-leiste")

    tabs = page.locator("nav.dk-bottom-nav a.dk-bn-tab")
    anzahl = tabs.count()
    texte = [tabs.nth(i).inner_text().strip() for i in range(anzahl)]
    pruefe("Leiste hat fünf Tabs", anzahl == 5, f"{anzahl}: {texte}")
    pruefe("kein 'Mehr' in der Leiste", not any(t.lower().startswith("mehr") for t in texte), str(texte))
    for i in range(anzahl):
        box = tabs.nth(i).bounding_box() or {"height": 0}
        if box["height"] < 44:
            pruefe(f"Tab {texte[i]!r} >= 44 px", False, f"{box['height']:.0f} px")

    knopf = page.locator("button.dk-menue-knopf")
    pruefe("Menü-Knopf oben links sichtbar (Mobil)", knopf.is_visible())
    box = knopf.bounding_box() or {"width": 0, "height": 0}
    pruefe("Menü-Knopf >= 44 px", box["width"] >= 44 and box["height"] >= 44,
           f"{box['width']:.0f}x{box['height']:.0f}")

    # 2) Schublade offen
    knopf.click()
    page.wait_for_timeout(350)
    schublade = page.locator(".dk-schublade")
    pruefe("Schublade offen", schublade.is_visible())
    schuss(page, ordner, "02-menue-offen")

    punkte = page.locator(".dk-schublade-punkt")
    zu_klein = []
    for i in range(punkte.count()):
        b = punkte.nth(i).bounding_box() or {"height": 0}
        if b["height"] < 44:
            zu_klein.append(f"{punkte.nth(i).inner_text().strip()}: {b['height']:.0f}px")
    pruefe("alle Schubladenpunkte >= 44 px", not zu_klein, "; ".join(zu_klein))

    # 3) Esc schließt
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    pruefe("Esc schließt die Schublade", not page.locator(".dk-schublade").is_visible())

    # 4) Wischen nach links schließt
    knopf.click()
    page.wait_for_timeout(300)
    box = schublade.bounding_box() or {"x": 0, "y": 0, "width": 300, "height": 600}
    start_x = box["x"] + box["width"] * 0.7
    mitte_y = box["y"] + box["height"] * 0.5
    page.evaluate(
        """([sx, sy, ex]) => {
            const el = document.querySelector('.dk-schublade');
            const t = (x) => new Touch({ identifier: 1, target: el, clientX: x, clientY: sy });
            el.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, touches: [t(sx)], changedTouches: [t(sx)] }));
            el.dispatchEvent(new TouchEvent('touchend', { bubbles: true, touches: [], changedTouches: [t(ex)] }));
        }""",
        [start_x, mitte_y, start_x - 120],
    )
    page.wait_for_timeout(350)
    pruefe("Wischen nach links schließt die Schublade",
           not page.locator(".dk-schublade").is_visible())

    # 5) Kalender (Leiste markiert) und Bereichsseite mit Markierung
    page.goto(f"{BASE}/#/kalender", wait_until="networkidle")
    page.wait_for_timeout(600)
    schuss(page, ordner, "03-kalender-leiste")
    page.locator("button.dk-menue-knopf").click()
    page.wait_for_timeout(350)
    schuss(page, ordner, "04-menue-im-kalender")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    page.goto(f"{BASE}/#/personen/liste", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.locator("button.dk-menue-knopf").click()
    page.wait_for_timeout(350)
    schuss(page, ordner, "05-menue-personen")


def desktop_aufnahme(page, thema: str) -> None:
    thema_setzen(page, thema)
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(400)
    schuss(page, f"desktop/{thema}", "01-uebersicht")
    pruefe("Menü-Knopf am Desktop unsichtbar",
           not page.locator("button.dk-menue-knopf").is_visible())
    pruefe("Seitenleiste am Desktop sichtbar", page.locator("aside.dk-sidebar").is_visible())


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for thema in ("hell", "dunkel"):
            ctx = browser.new_context(viewport=MOBIL, is_mobile=True, has_touch=True,
                                      device_scale_factor=2)
            page = ctx.new_page()
            anmelden(page)
            mobil_aufnahmen(page, thema)
            ctx.close()

            ctx = browser.new_context(viewport=DESKTOP)
            page = ctx.new_page()
            anmelden(page)
            desktop_aufnahme(page, thema)
            ctx.close()
        browser.close()

    if fehler:
        print("\n[ux3e] BEFUNDE:")
        for f in fehler:
            print("  - " + f)
        return 1
    print("\n[ux3e] alle Prüfungen grün")
    return 0


if __name__ == "__main__":
    sys.exit(main())
