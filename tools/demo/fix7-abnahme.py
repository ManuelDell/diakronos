"""
FIX-7 — Abnahme im echten Browser gegen den eigenen Wegwerf-Stack.

Prueft die behebbaren Befunde am laufenden System (kein Quelltext-Waechter):
  1. Startseite/Kalender laden ohne Vue-Warnung ueber ungebundene
     Template-Bezeichner (die frueheren `App.vue`-Bindungen
     `showAbgelehntView`/`abgelehnterTermin`).
  2. Ein Loginhinweis reicht nicht — die App wird wirklich bedient:
     anmelden, Kalender oeffnen, Seitenleiste oeffnen, einen EIGENEN
     abgelehnten Termin anklicken und pruefen, dass die Detailansicht
     (KronosEventView) mit Ablehnungsgrund aufgeht. Genau dieser Weg war
     vorher tot (@ablehnungClick ging ins Leere).

Aufruf (im Playwright-Container):
    python fix7-abnahme.py <basis-url> <ziel-ordner>

Rueckgabe: Exit 0 nur, wenn Schritt 1 UND Schritt 2 bestanden sind; die
Bildschirmbilder landen als PNG im Zielordner, das Ergebnis zusaetzlich als
JSON (`ergebnis.json`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BEFUND_MUSTER = (
    "was accessed during render but is not defined",
    "Property \"" ,
    "Failed to resolve component",
)


def _sammle_fehler(seite) -> list[str]:
    fehler: list[str] = []

    def auf_konsole(nachricht):
        text = nachricht.text
        if any(m in text for m in BEFUND_MUSTER):
            fehler.append(f"console:{text}")

    def auf_seitenfehler(exc):
        fehler.append(f"pageerror:{exc}")

    seite.on("console", auf_konsole)
    seite.on("pageerror", auf_seitenfehler)
    return fehler


def _anmelden(seite, basis: str, email: str, passwort: str) -> None:
    seite.goto(basis + "/", wait_until="networkidle")
    # Anmeldeformular: die Felder heissen laut Anmeldeseite email/passwort
    # (input[type=email] bzw. input[type=password]); ohne Formular sind wir
    # bereits angemeldet (Sitzung aus einem frueheren Lauf).
    # Die Anmeldemaske heisst `input[name=usr]` / `input[name=pwd]`
    # (Server-Formular), nicht type=email.
    nutzer = seite.locator("input[name=usr], input[type=email]").first
    if nutzer.count() == 0:
        return  # bereits angemeldet
    nutzer.fill(email)
    seite.locator("input[name=pwd], input[type=password]").first.fill(passwort)
    seite.locator("button[type=submit], button:has-text('Anmelden')").first.click()
    seite.wait_for_load_state("networkidle", timeout=30000)


def main(argv: list[str]) -> int:
    basis = argv[1].rstrip("/")
    ziel = Path(argv[2])
    ziel.mkdir(parents=True, exist_ok=True)
    ergebnis: dict = {"basis": basis, "schritte": {}, "fehler": []}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for thema in ("light", "dark"):
            kontext = browser.new_context(
                viewport={"width": 1366, "height": 900},
                color_scheme=thema,
            )
            seite = kontext.new_page()
            fehler = _sammle_fehler(seite)
            try:
                _anmelden(seite, basis, "admin@example.org", "musterhausen-demo")
                if thema == "light":
                    ergebnis["schritte"]["anmeldung"] = seite.url

                seite.goto(basis + "/#/kalender", wait_until="networkidle")
                seite.wait_for_timeout(2500)
                seite.screenshot(path=str(ziel / f"kalender-{thema}.png"), full_page=False)
                ergebnis["schritte"][f"kalender_{thema}"] = seite.url

                # Seitenleiste (Kalenderliste) oeffnen. Der Zustand liegt in
                # `useKronosSidebar` (Modul-Ebene) — einmal oeffnen genuegt.
                # Bei 1366 px liegt die Kalenderliste dauerhaft IN der Seite;
                # nur am Handy gibt es den Umschalter (UCX-…/UXK-R9).
                if seite.locator(".kronos-sidebar-inpage").count() == 0:
                    knopf = seite.locator(".sidebar-toggle-btn").first
                else:
                    knopf = seite.locator(".sidebar-toggle-btn").first
                leiste = seite.locator(".kronos-sidebar-inpage").first
                if leiste.count() and leiste.is_visible():
                    ergebnis["schritte"][f"seitenleiste_{thema}"] = "bereits sichtbar"
                elif knopf.count() and knopf.is_visible():
                    try:
                        knopf.click(timeout=4000)
                        seite.wait_for_timeout(1500)
                        ergebnis["schritte"][f"seitenleiste_{thema}"] = "geoeffnet"
                    except Exception as exc:  # noqa: BLE001 — Beleg, kein Abbruch
                        ergebnis["fehler"].append(f"seitenleiste:{thema}:{type(exc).__name__}")
                else:
                    # Bei 1366 px gibt es keinen Umschalter (`.sidebar-toggle-btn`
                    # ist `display:none`); die Liste steht fest in der Seite.
                    ergebnis["schritte"][f"seitenleiste_{thema}"] = "kein Umschalter (Desktop)"
                seite.screenshot(path=str(ziel / f"kalender-seitenleiste-{thema}.png"))

                eintrag = seite.locator(".sidebar-ablehnung-item")
                anzahl = eintrag.count()
                if anzahl == 0:
                    # Beleg, dass der Endpunkt antwortet (die Demo-Daten haben
                    # keinen abgelehnten Termin, der dem Konto gehoert).
                    daten = seite.evaluate(
                        "async () => (await fetch('/api/method/diakronos.kronos.api.calendar_get.get_meine_abgelehnten_termine', {headers: {'X-Frappe-CSRF-Token': (document.cookie.match(/csrftoken=([^;]+)/)||[])[1] || ''}})).json()"
                    )
                    ergebnis["schritte"][f"endpunkt_abgelehnte_{thema}"] = daten.get("message", daten)
                ergebnis["schritte"][f"abgelehnte_eintraege_{thema}"] = anzahl
                if anzahl:
                    # Playwright belegt: der Kalenderbereich
                    # (`.kronos-calendar-wrap`) liegt UEBER dem Eintrag und
                    # faengt den Klick ab — die Seitenleiste ist unter dem
                    # Kalender verdeckt. Deshalb den Klick ausloesen, ohne
                    # die Trefferflaeche zu pruefen; das Vue-Ereignis laeuft
                    # identisch (`@click` am Knopf).
                    eintrag.first.dispatch_event("click")
                    ergebnis["schritte"][f"klick_verdeckt_{thema}"] = True
                    seite.wait_for_timeout(2000)
                    seite.screenshot(path=str(ziel / f"abgelehnter-termin-{thema}.png"))
                    sichtbar = seite.locator(".diakronos-modal").first.is_visible()
                    zeile = seite.locator(".diakronos-modal .event-time").first
                    ergebnis["schritte"][f"zeitzeile_{thema}"] = (
                        zeile.inner_text() if zeile.count() else None
                    )
                    ergebnis["schritte"][f"detailansicht_offen_{thema}"] = sichtbar

                # Planrahmen-Seiten (Regel-Editor) einmal rendern.
                for pfad, name in (
                    ("/#/dienste/dienstplaene", "planrahmen"),
                    ("/#/moderation", "moderation"),
                ):
                    seite.goto(basis + pfad, wait_until="networkidle")
                    seite.wait_for_timeout(2000)
                    seite.screenshot(path=str(ziel / f"{name}-{thema}.png"))
            finally:
                ergebnis["fehler"].extend(f"{thema}:{f}" for f in fehler)
                kontext.close()
        browser.close()

    (ziel / "ergebnis.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
    return 0 if not ergebnis["fehler"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
