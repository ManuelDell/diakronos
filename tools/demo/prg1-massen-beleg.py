"""PR-G1 Nacharbeit — Live-Beleg: Auswahl folgt dem Filterwechsel.

Ablauf: Stammdaten öffnen, „alle sichtbaren auswählen", dann Filter
„Männlich" setzen und prüfen, ob die Massenzeile nur noch die sichtbaren
Personen zählt. Danach NIEMALS anwenden (kein Schreiben in die Demo-Daten).

    docker run --rm --network prg1_default -v "<repo>/tools/demo:/w:ro" \
        -v "<ziel>:/ausgabe" -e BASE=http://app:8000 -e ZIEL=/ausgabe \
        playwright-py-bs2d3:1.49.0 python /w/prg1-massen-beleg.py
"""

import sys
import json
import os

from playwright.sync_api import sync_playwright

# SEC-DEF2: KEIN eingebauter Standard-Zugang. Fehlt die Variable (oder ist sie
# leer), bricht das Skript mit erklaerender Meldung und Exit-Code 2 ab. Der
# oeffentliche Musterhausen-Demo-Standard steht in ``tools/demo/TESTKONTEN.md``,
# wird aber nicht stillschweigend eingesetzt: ein Skript, das versehentlich auf
# einer ECHTEN Instanz laeuft, soll nicht mit bekannten Zugangsdaten weiterlaufen.
# Absichtlich INLINE (kein Import aus ``tools/demo/zugang.py``): viele dieser
# Skripte laufen als EINZELNE Datei in einen Container eingehaengt, andere
# liegen ausserhalb von ``tools/demo`` — ein Nachbarmodul waere dort nicht da.
def wert_oder_abbruch(name: str, hinweis: str = "") -> str:
    wert = os.environ.get(name, "")
    if str(wert).strip():
        return wert
    zusatz = f" {hinweis.strip()}" if hinweis.strip() else ""
    print(
        f"[abbruch] Umgebungsvariable {name} ist nicht gesetzt.{zusatz} "
        "Die Demo-Skripte haben absichtlich KEINEN eingebauten Standard-Zugang "
        "(SEC-DEF2): der oeffentliche Musterhausen-Demo-Standard steht in "
        "tools/demo/TESTKONTEN.md, muss aber ausdruecklich uebergeben werden.",
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(2)


BASE = os.environ.get("BASE", "http://app:8000")
EMAIL = wert_oder_abbruch("ADMIN_EMAIL")
PASSWORT = wert_oder_abbruch("ADMIN_PASS")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
PLANTYP = os.environ.get("PLANTYP", "chorplan")
os.makedirs(ZIEL, exist_ok=True)
beleg = {}

with sync_playwright() as p:
    browser = p.chromium.launch()
    seite = browser.new_page(viewport={"width": 1440, "height": 1000})
    seite.goto(f"{BASE}/login", wait_until="domcontentloaded")
    seite.fill('#dk-usr, input[name="usr"]', EMAIL)
    seite.fill('#dk-pwd, input[name="pwd"]', PASSWORT)
    seite.click('button[type="submit"]')
    seite.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    seite.wait_for_load_state("networkidle")

    seite.goto(f"{BASE}/#/planrahmen/stammdaten/{PLANTYP}", wait_until="networkidle")
    seite.wait_for_selector(".pr-stamm-tabelle", timeout=30000)
    seite.wait_for_timeout(800)

    kopf = seite.locator(".pr-stamm-tabelle thead input[type=checkbox]").first
    kopf.check()
    seite.wait_for_timeout(400)
    beleg["vor_filter"] = seite.locator(".pr-stamm-masse-zahl").first.text_content().strip()

    seite.select_option(".pr-stamm-geschlechtwahl", "m")
    seite.wait_for_timeout(600)
    beleg["nach_filter"] = seite.locator(".pr-stamm-masse-zahl").first.text_content().strip()
    beleg["sichtbar"] = seite.eval_on_selector_all(
        ".pr-stamm-tabelle tbody tr .pr-stamm-geschlecht-wert",
        "els => els.map(e => e.textContent.trim())")
    beleg["sichtbar_namen"] = seite.eval_on_selector_all(
        ".pr-stamm-tabelle tbody tr .pr-stamm-name-haupt",
        "els => els.map(e => e.textContent.trim())")

    seite.screenshot(path=f"{ZIEL}/nachher2-desktop-1440-massnahme-nach-filterwechsel.png")
    browser.close()

with open(f"{ZIEL}/nachher2-massen-beleg.json", "w", encoding="utf-8") as fh:
    json.dump(beleg, fh, ensure_ascii=False, indent=2)
print("Massen-Beleg:", json.dumps(beleg, ensure_ascii=False))
