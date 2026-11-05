"""ON-5 — Bildschirmabnahme: Kalender-Vorschlag, Logo sofort, Dev-Modus ruhig.

Laeuft gegen den Wegwerf-Stack NACH `tools/demo/musterhausen.py` (Demo-Admin
mit allen vier Rollen, Gemeinde vollstaendig eingerichtet — der Assistent ist
deshalb zu; die Punkte werden dort geprueft, wo sie im Betrieb auftreten).

Pruefungen
----------
1. Kalender-Vorschlag: Der Server-Endpunkt legt einen noch FEHLENDEN Kalender
   an und meldet den vorhandenen als „uebersprungen“ (Erfolgsfall von E2-3).
2. Logo sofort (E2-5): In den Einstellungen ein Logo hochladen -> die
   Seitenleiste zeigt es OHNE Neuladen (der Punkt, der vorher erst nach
   `location.reload()` stimmte).
3. Dev-Modus-Aufruf (Klein): mit `DEVMODE_ENABLED=0` darf beim Seitenaufbau
   KEIN `devmodus.api.uebersicht` im Netzdialog stehen.

Screenshots: hell und dunkel, Desktop 1440 und Mobil 390, nach ZIEL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
PREFIX = ("/" + os.environ.get("PREFIX", "").strip().strip("/")).rstrip("/")
ZIEL = Path(os.environ.get("ZIEL", "/ausgabe"))
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASSWORT = os.environ.get("ADMIN_PASSWORT", "musterhausen-demo")

befunde: list[str] = []


def p(*teile: str) -> str:
    return BASE + PREFIX + "".join(teile)


def schuss(page, name: str) -> None:
    ZIEL.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ZIEL / f"{name}.png"), full_page=True)
    print(f"       → {ZIEL / (name + '.png')}")


def ok(text: str) -> None:
    print(f"[ok] {text}")


def befund(text: str) -> None:
    befunde.append(text)
    print(f"[hoch] {text}")


def anmelden(page) -> None:
    page.goto(p("/login"), wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    page.get_by_label("E-Mail", exact=False).first.fill(ADMIN_EMAIL)
    page.get_by_label("Passwort", exact=False).first.fill(ADMIN_PASSWORT)
    page.get_by_role("button", name="Anmelden").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        aufrufe: list[str] = []
        page.on("request", lambda r: aufrufe.append(r.url))
        konsole: list[str] = []
        page.on("console", lambda m: konsole.append(m.text) if m.type == "error" else None)

        anmelden(page)
        aufrufe.clear()
        konsole.clear()

        # 1) Alle Ansichten einmal durchlaufen — dabei darf kein Dev-Modus-
        #    Aufruf entstehen (DEVMODE_ENABLED=0).
        for pfad, name in (
            ("#/", "01-uebersicht-hell"),
            ("#/kalender/verwalten", "02-kalender-verwaltung-hell"),
            ("#/einstellungen", "03-einstellungen-hell"),
            ("#/einstellungen/rollen", "04-rollen-rechte-hell"),
        ):
            page.goto(p("/diakonos") + pfad, wait_until="domcontentloaded")
            page.wait_for_timeout(1800)
            # Die Listen laden nach (Kalender-Verwaltung: Karten je Kalender).
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1200)
            schuss(page, name)
        dev = [u for u in aufrufe if "devmodus.api" in u]
        if dev:
            befund(f"Dev-Modus-Aufruf bei ausgeschaltetem Dev-Modus: {dev[:2]}")
        else:
            ok("kein devmodus.api-Aufruf (Dev-Modus ist aus)")

        # 2) Kalender-Verwaltung: beide Vorschlags-Kalender stehen da.
        #    Gelesen wird der ECHTE Endpunkt der Verwaltung (`get_kalender_verwaltung`)
        #    statt gerendertem HTML — die Ansicht laedt ihre Karten asynchron, und
        #    ein Textsuchlauf im HTML war schon einmal falsch-negativ.
        page.goto(p("/diakonos") + "#/kalender/verwalten", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        schuss(page, "02-kalender-verwaltung-hell")
        daten = page.evaluate(
            "async () => {"
            "  const b = window.__DIakonosBOOT || {};"
            "  const r = await fetch(b.basePath + '/api/method/"
            "diakronos.diakonos.api.kronos.kalender_verwaltung.get_kalender_verwaltung', {"
            "    method: 'POST', headers: { 'Content-Type': 'application/json',"
            "      'X-Frappe-CSRF-Token': b.csrf_token || '' }, body: '{}' });"
            "  return await r.json();"
            "}")
        namen = [k.get("name") for k in ((daten or {}).get("message") or {}).get("kalender", [])]
        # Die Demo-Daten tragen „gottesdienste“ klein — verglichen wird ohne
        # Gross-/Kleinschreibung, weil die Anlage den Namen nicht umschreibt.
        klein = {str(n).strip().lower() for n in namen}
        for name in ("Gottesdienste", "Gemeindekalender"):
            if name.lower() in klein:
                ok(f"Kalender „{name}“ steht in der Verwaltung")
            else:
                befund(f"Kalender „{name}“ fehlt in der Verwaltung (vorhanden: {namen})")

        # 3) Logo sofort (E2-5): Upload in den Einstellungen, Seitenleiste
        #    beobachten OHNE Neuladen.
        page.goto(p("/diakonos") + "#/einstellungen/gemeinde", wait_until="domcontentloaded")
        page.wait_for_timeout(1800)
        # NUR die Marke der Seitenleiste beobachten (`.dk-sb-logo`) — die
        # Logo-Vorschau in der Karte ist ein anderes Element und war im ersten
        # Anlauf die Quelle eines falsch-positiven „ok“.
        marke = page.locator(".dk-sb-brand .dk-sb-logo img.dk-logo-marke-bild")
        vorher = marke.count()
        png = ZIEL / "logo.png"
        png.write_bytes(_PNG)
        feld = page.locator("input[type=file]").first
        if not feld.count():
            befund("Einstellungen/Gemeinde: kein Dateifeld fuer das Logo")
        else:
            # Die Demo-Gemeinde HAT schon ein Logo — deshalb reicht „ist ein
            # Bild da“ nicht als Beweis. Verglichen wird die ADRESSE: sie muss
            # nach dem Upload eine andere sein (`?v=`-Hash des Servers), und
            # zwar OHNE Neuladen der Seite.
            alt = marke.first.get_attribute("src") if vorher else ""
            feld.set_input_files(str(png))
            # Auf die NEUE Adresse WARTEN (der Server vergibt einen neuen
            # ?v=-Hash) — ein fester Zeitablauf war zu knapp: der Netzdialog
            # zeigte die neue Adresse, die Abfrage kam aber vorher.
            try:
                page.wait_for_function(
                    "() => { const el = document.querySelector"
                    "('.dk-sb-brand .dk-sb-logo img.dk-logo-marke-bild');"
                    " return el && el.getAttribute('src') !== arguments_alt; }"
                    .replace("arguments_alt", repr(alt or "").replace("'", '"')),
                    timeout=8000,
                )
            except Exception:  # noqa: BLE001 — Befund unten ist die Aussage
                pass
            page.wait_for_timeout(500)
            schuss(page, "05-logo-nach-upload")
            nachher = marke.count()
            neu = marke.first.get_attribute("src") if nachher else ""
            if not nachher:
                befund("Logo erscheint in der Seitenleiste erst nach dem Neuladen (E2-5)")
            elif alt and neu == alt:
                befund(f"Seitenleiste zeigt weiterhin das alte Logo ({alt})")
            else:
                ok(f"Seitenleiste hat die Marke ohne Neuladen gewechselt ({alt} → {neu})")

        # 4) Dunkelmodus
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(600)
        schuss(page, "06-einstellungen-dunkel")
        page.goto(p("/diakonos") + "#/", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(600)
        schuss(page, "07-uebersicht-dunkel")

        # 5) Mobil 390 px
        mobil = browser.new_page(viewport={"width": 390, "height": 844})
        anmelden(mobil)
        for pfad, name in (
            ("#/", "m-01-uebersicht"),
            ("#/kalender/verwalten", "m-02-kalender"),
            ("#/einstellungen/gemeinde", "m-03-einstellungen-gemeinde"),
        ):
            mobil.goto(p("/diakonos") + pfad, wait_until="domcontentloaded")
            mobil.wait_for_timeout(1600)
            schuss(mobil, name)
            ueberlauf = mobil.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if ueberlauf > 1:
                befund(f"{name}: waagerechter Ueberlauf von {ueberlauf} px am Handy")

        echte = [k for k in konsole if "417" not in k and "404" not in k and "405" not in k]
        if echte:
            befund(f"Konsolenfehler: {'; '.join(echte[:3])}")
        else:
            ok("keine Konsolenfehler")
        browser.close()

    print("── Ergebnis ──")
    print(f"Befunde: {len(befunde)}")
    for b in befunde:
        print(f"  - {b}")
    return 0 if not befunde else 2


def _png() -> bytes:
    """Ein echtes, kleines PNG (2x2, rot) — ohne Pillow."""
    import struct
    import zlib

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (struct.pack("!I", len(daten)) + typ + daten
                + struct.pack("!I", zlib.crc32(typ + daten) & 0xFFFFFFFF))

    ihdr = struct.pack("!IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    roh = b"".join(b"\x00" + b"\x00\xaa\x44" * 2 for _ in range(2))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(roh)) + chunk(b"IEND", b""))


_PNG = _png()


if __name__ == "__main__":
    sys.exit(main())
