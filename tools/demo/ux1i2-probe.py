"""
UX1i2 — Gegenprobe zum Messfehler „0 Verstöße trotz 28-px-Knopf“.

Baut im Browser eine Seite mit BEKANNT zu kleinen Trefferflächen und BEKANNT
schlechtem Kontrast, lässt das echte Mess-Skript (`uiux-pruefung.MESS_SKRIPT`)
über den echten Mobil-Kontext (`uiux-pruefung.neuer_kontext`) darauf laufen
und vergleicht Soll gegen Ist.

    python3 tools/demo/ux1i2-probe.py            # Ist-Stand: muss gruen sein
    python3 tools/demo/ux1i2-probe.py --falsch   # alter Fehler nachgestellt: muss rot sein

`--falsch` ruft das Mess-Skript mit ZWEI Einzelparametern auf — so, wie es die
Fassung vor UX1i2 tat. Dann kommt `minTreffer` als `undefined` an, der Lauf
meldet 0 Verstöße und die Probe schlägt fehl. Läuft im Playwright-Image
(mcr.microsoft.com/playwright/python:v1.49.0-noble) und lokal, sofern
`playwright` samt Chromium da ist.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

QUELLE = Path(__file__).with_name("uiux-pruefung.py")

# Testseite: 2× 28 px (Knopf + Link, genau der Befund), 1× 44 px (sauber,
# darf NICHT gemeldet werden), 1 Absatz mit Kontrast 1,9:1, 1 Absatz sauber,
# 1 absichtlich unsichtbarer Knopf (darf nicht als Fläche zählen).
SEITE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><style>
  body { margin: 0; font: 14px/1.4 sans-serif; background: #fff; color: #111 }
  .knopf-klein { display: inline-block; width: 28px; height: 28px; padding: 0;
                 border: 0; background: #e5e7eb; color: #111 }
  .knopf-gross { display: inline-block; width: 44px; height: 44px; padding: 0;
                 border: 0; background: #e5e7eb; color: #111 }
  .schlecht { color: #b9bcc2 }
  .gut { color: #111 }
  .weg { display: none }
</style></head>
<body>
  <p class="gut" id="gut">Sauberer Text mit ausreichendem Kontrast im Fliesstext.</p>
  <p class="schlecht" id="schlecht">Dieser Text ist zu hell und muss als Verstoss erscheinen.</p>
  <button class="knopf-klein" id="klein" aria-label="klein">+</button>
  <button class="knopf-gross" id="gross" aria-label="gross">+</button>
  <button class="weg" id="unsichtbar" aria-label="unsichtbar">+</button>
  <a href="#z" class="knopf-klein" id="kleiner-link" aria-label="kleiner Link">+</a>
</body></html>
"""

# Soll: genau die beiden 28-px-Flächen, genau der eine helle Absatz.
SOLL_IDS_KLEIN = {"klein", "kleiner-link"}
SOLL_ID_KONTRAST = "schlecht"


def lade_werkzeug():
    spec = importlib.util.spec_from_file_location("uiux_pruefung", QUELLE)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def messe(falsch: bool = False, breite: int = 390, hoehe: int = 844):
    """Misst die Testseite. `falsch=True` stellt den alten Aufruffehler nach."""
    m = lade_werkzeug()
    from playwright.sync_api import sync_playwright

    mit_browser = sync_playwright().start()
    try:
        browser = mit_browser.chromium.launch(args=["--no-sandbox", "--no-proxy-server"])
        ctx = m.neuer_kontext(browser, breite, hoehe, True, False)
        seite = ctx.new_page()
        seite.set_content(SEITE, wait_until="load")
        grob = seite.evaluate("() => matchMedia('(pointer: coarse)').matches")
        if falsch:
            # ALTE Fassung: zwei Einzelparameter. Playwright 1.62 legt den
            # ganzen Wert in den ersten Parameter — der zweite bleibt leer.
            altes_skript = m.MESS_SKRIPT.replace("([minKontrast, minTreffer]) => {",
                                                 "(minKontrast, minTreffer) => {", 1)
            messung = seite.evaluate(altes_skript, [m.KONTRAST_MIN, m.TREFFER_MIN])
        else:
            messung = seite.evaluate(m.MESS_SKRIPT, [m.KONTRAST_MIN, m.TREFFER_MIN])
        ctx.close()
        browser.close()
    finally:
        mit_browser.stop()
    return {"grob": grob, "messung": messung}


def auswerten(ergebnis: dict) -> list[str]:
    """Abweichungen von der Soll-Liste (leer = alles wie erwartet)."""
    ms = ergebnis["messung"]
    klein = {k["selektor"].split("#")[-1] for k in ms["treffer"]["zu_klein"]}
    kontrast = {k["selektor"].split("#")[-1] for k in ms["kontrast"]["verstoesse"]}
    abweichungen = []
    if klein != SOLL_IDS_KLEIN:
        abweichungen.append(f"zu kleine Flächen: {sorted(klein)} statt {sorted(SOLL_IDS_KLEIN)}")
    if kontrast != {SOLL_ID_KONTRAST}:
        abweichungen.append(f"Kontrast-Verstöße: {sorted(kontrast)} statt ['{SOLL_ID_KONTRAST}']")
    if ms["treffer"].get("grenze") != 44.0:
        abweichungen.append(f"Treffer-Grenze im Browser: {ms['treffer'].get('grenze')!r}")
    if ms["kontrast"].get("grenze") != 4.5:
        abweichungen.append(f"Kontrast-Grenze im Browser: {ms['kontrast'].get('grenze')!r}")
    return abweichungen


def main(argv) -> int:
    falsch = "--falsch" in argv
    ergebnis = messe(falsch)
    ms = ergebnis["messung"]
    print(f"pointer:coarse im Kontext = {ergebnis['grob']}")
    print(f"Treffer geprüft           = {ms['treffer']['geprueft']}")
    print(f"zu klein (<44 px)         = {len(ms['treffer']['zu_klein'])}")
    for k in ms["treffer"]["zu_klein"]:
        print("   ", k["selektor"], f"{k['breite']}×{k['hoehe']}", k["text"])
    print(f"Kontrast < 4,5:1          = {len(ms['kontrast']['verstoesse'])}")
    for k in ms["kontrast"]["verstoesse"]:
        print("   ", k["selektor"], f"{k['kontrast']}:1", k["text"])
    abweichungen = auswerten(ergebnis)
    if abweichungen:
        for a in abweichungen:
            print("ABWEICHUNG:", a)
        print("ERGEBNIS: ROT — Messung findet die bekannten Stellen nicht (Messfehler)")
        return 1
    print("ERGEBNIS: GRÜN — Messung findet genau die bekannten Stellen")
    print("Werte:", json.dumps({"klein": len(ms["treffer"]["zu_klein"]),
                              "kontrast": len(ms["kontrast"]["verstoesse"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
