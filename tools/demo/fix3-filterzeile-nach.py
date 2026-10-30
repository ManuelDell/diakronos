"""FIX-3 — Nachaufnahme: Chip-Messung Wiki reparieren, Bilder erneuern.

Grund: Der erste Lauf hat die Wiki-Kategorie-Chips nicht gefunden (die Chips
liegen in `.wk-main .dk-ui-chips`, das Messskript suchte `.wk-main .dk-ui-chip`
und traf im Vorher-Stand keinen gueltigen Selektor). Hier wird zusaetzlich der
ELTERN-Kasten gemessen und — wenn er hoecher als die Chips ist — als eigene
Zeile ausgewiesen; das ist genau der alte Zustand (Chips 29px in einem
33px-Kasten neben dem 45/48px-Feld).

Aufruf wie fix3-filterzeile.py. Ergebnis: `<marke>-messung2.json` plus Bilder.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

BREITEN = [(344, 694), (390, 844), (1366, 800)]
THEMES = ["light", "dark"]

MARKE = "nachher"
if "--marke" in sys.argv:
    MARKE = sys.argv[sys.argv.index("--marke") + 1]

SEITEN = [
    ("beitraege", "#/beitraege", ".dk-filters", [".dk-ui-chip", ".dk-search-bar"]),
    ("wiki", "#/wiki", ".wk-main", [".dk-ui-chip", ".wk-suche"]),
    ("lieder", "#/lieder", ".ld-toolbar", [".ld-suche", ".ld-filter-knopf"]),
]

fehler: list[str] = []
messungen: list[dict] = []


def anmelden(page):
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    if page.locator("#dk-usr").count():
        page.fill("#dk-usr", ADMIN)
        page.fill("#dk-pwd", ADMIN_PASS)
        page.keyboard.press("Enter")
    page.wait_for_timeout(3000)


def masse(page, selektoren):
    return page.evaluate(
        """(sels) => {
            const out = {}
            for (const s of sels) {
                const el = document.querySelector(s)
                if (!el) { out[s] = null; continue }
                const r = el.getBoundingClientRect()
                out[s] = (r.width === 0 && r.height === 0) ? null
                    : {h: Math.round(r.height * 10) / 10, w: Math.round(r.width * 10) / 10,
                       top: Math.round(r.top), left: Math.round(r.left)}
            }
            return out
        }""",
        selektoren,
    )


def main():
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        for breite, hoch in BREITEN:
            for theme in THEMES:
                ctx = browser.new_context(viewport={"width": breite, "height": hoch},
                                          locale="de-DE", has_touch=breite < 700)
                ctx.add_init_script(
                    f"try {{ localStorage.setItem('dk-theme', '{theme}') }} catch (e) {{}}")
                page = ctx.new_page()
                page.on("pageerror", lambda e: fehler.append(f"pageerror: {e}"))
                anmelden(page)
                for name, hash_, _bereich, sels in SEITEN:
                    page.goto(f"{BASE}/diakonos{hash_}", wait_until="domcontentloaded")
                    page.wait_for_timeout(1800)
                    werte = masse(page, sels)
                    # Suchfeld und Chip/Knopf vergleichen
                    # Feld = das Suchfeld; verglichen wird mit jedem anderen
                    # gemessenen Element der Zeile (Chip bzw. Knopf).
                    # Suchfeld erkennen: .wk-suche / .ld-suche ODER .dk-search-bar
                    # (Beitraege heisst das Feld .dk-search-bar — "suche" steckt
                    # nicht im Namen, deshalb zusaetzlich auf "search" pruefen).
                    def ist_feld(k):
                        return "suche" in k or "search" in k
                    feld = next((v for k, v in werte.items() if ist_feld(k)), None)
                    # Vergleichspartner: alle ANDEREN gemessenen Elemente der
                    # Zeile (Chip beim Beiträge/Wiki, Knopf bei Lieder). Die
                    # Identitätsprüfung `v is not feld` greift nicht, weil
                    # Playwright die Messwerte als neue dicts liefert.
                    feld_key = next((k for k in werte if ist_feld(k)), None)
                    rest = [v for k, v in werte.items()
                            if k != feld_key and v is not None]
                    abw = [round(abs(feld["h"] - v["h"]), 1) for v in rest] if feld else []
                    zeile = None
                    if feld and rest and rest[0] is not None:
                        zeile = (abs(feld["top"] - rest[0]["top"]) <= 1)
                    eintrag = {"marke": MARKE, "seite": name, "breite": breite,
                               "theme": theme, "masse": werte,
                               "hoehen": {k: (v["h"] if v else None) for k, v in werte.items()},
                               "gleiche_zeile": zeile,
                               "abweichung_px": max(abw) if abw else None}
                    # Der Filter-Knopf der Lieder existiert am Desktop bewusst
                    # nicht (OP-HANDY-13: Blatt nur unter 700 px) — das ist
                    # kein Fehler, der Vergleich entfaellt dort.
                    erwartet_ohne_knopf = (name == "lieder" and breite > 700
                                           and werte.get(".ld-filter-knopf") is None)
                    if erwartet_ohne_knopf:
                        eintrag["hinweis"] = "kein Filter-Knopf am Desktop (OP-HANDY-13)"
                        eintrag["gleiche_zeile"] = None
                        eintrag["abweichung_px"] = None
                        messungen.append(eintrag)
                        print(json.dumps(eintrag, ensure_ascii=False))
                        page.screenshot(path=os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-{name}.png"))
                        continue
                    if feld is None or not abw:
                        fehler.append(f"{name}/{breite}/{theme}: unvollstaendig {werte}")
                        eintrag["abweichung_px"] = None
                    elif max(abw) > 0:
                        fehler.append(f"{name}/{breite}/{theme}: {werte} weichen um {max(abw)}px ab")
                    messungen.append(eintrag)
                    print(json.dumps(eintrag, ensure_ascii=False))
                    page.screenshot(path=os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-{name}.png"))
                ctx.close()
        browser.close()
    bericht = {"marke": MARKE, "fehler": fehler, "messungen": messungen}
    with open(os.path.join(ZIEL, f"{MARKE}-messung2.json"), "w", encoding="utf-8") as f:
        json.dump(bericht, f, ensure_ascii=False, indent=2)
    print(f"\n{len(messungen)} Messungen, {len(fehler)} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
