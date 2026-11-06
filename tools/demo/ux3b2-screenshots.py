#!/usr/bin/env python3
"""UX3b2 — Abnahme-Screenshots „Personen“ (vorher/nachher).

Läuft IM Playwright-Container (mcr.microsoft.com/playwright/python:v1.49.0-noble)
gegen den eigenen Wegwerf-Stack. Aufruf (Beispiel):

    docker run --rm --network ux3b2_default -v <worktree>:/repo:ro \\
        -v /root/.hermes/scratch/diakronos-planrahmen/ui-screens/t_5ba290c0:/bilder \\
        -w /repo/tools/demo mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        python /repo/tools/demo/ux3b2-screenshots.py \\
            --base http://ux3b2-app-1:8000 --prefix /diakronos \\
            --admin admin@example.org:musterhausen-demo \\
            --mitglied anna.beispiel@example.org:musterhausen-demo \\
            --ziel /bilder/<vorher|nachher>

Aufgenommen wird je Rollen-Sicht (Administrator, Mitglied), je Breite
1440 × 900 und 390 × 844, je hell und dunkel:
  • Personen-Liste, Seite 1
  • Personen-Liste, LETZTE Seite (der Befund 2: dort verschwand das Blättern)
  • Handy-Liste (Fußzeile sichtbar? Befund 3)
Dazu die Kennzahlen aus dem DOM (Seitenzahl, Fußzeile, Blätter-Knöpfe) als
JSON neben die Bilder — das sind die Belege, die der Review liest.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

# Konsolenstand ist ein lokales Testsystem; der Zertifikats-Kontext ist
# ausdrücklich egal (der Stack spricht HTTP im eigenen Netz).
BILDER = []


def schuss(page, ziel: str, name: str) -> None:
    pfad = os.path.join(ziel, name + ".png")
    page.screenshot(path=pfad, full_page=True)
    BILDER.append(pfad)
    print("  ·", pfad, flush=True)


def anmelden(page, base: str, prefix: str, email: str, passwort: str) -> None:
    page.goto(base + prefix + "/#/", wait_until="networkidle")
    # Anmeldeformular (die SPA zeigt es, solange keine Sitzung steht).
    if page.locator('input[type="email"], input[name="email"], #anmeldung-email').count():
        page.fill('input[type="email"], input[name="email"], #anmeldung-email', email)
        page.fill('input[type="password"], input[name="passwort"], #anmeldung-passwort', passwort)
        page.locator('button[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)


def zaehlen(page) -> dict:
    """Kennzahlen der Liste aus dem DOM (die Belege des Reviews)."""
    def text(sel):
        loc = page.locator(sel)
        return loc.first.inner_text().strip() if loc.count() else None

    return {
        "fuss": text(".pz-fuss-text"),
        "zeilen": page.locator("tr.pz-zeile").count(),
        "karten": page.locator(".pz-karte").count(),
        "tabelle_da": page.locator(".pz-tabelle").count(),
        "fuss_da": page.locator(".pz-fuss").count(),
        "zurueck": page.locator('.pz-fuss button:has-text("Zurück")').count(),
        "weiter": page.locator('.pz-fuss button:has-text("Weiter")').count(),
        "statusfilter": page.locator('button:has-text("Ausgetreten")').count(),
        "datenschalter": page.locator('button:has-text("Persönliche Daten anzeigen")').count(),
        "ansicht": page.locator('button:has-text("Karten")').count(),
        "markt": page.locator("text=Unbekannt").count(),
    }


def seite_besuchen(page, base: str, prefix: str, hashpfad: str, breite: int, hoehe: int,
                   dunkel: bool, ziel: str, name: str) -> dict:
    page.set_viewport_size({"width": breite, "height": hoehe})
    page.emulate_media(color_scheme="dark" if dunkel else "light")
    page.goto(base + prefix + "/" + hashpfad, wait_until="networkidle")
    page.wait_for_timeout(1500)
    schuss(page, ziel, name)
    return zaehlen(page)


def letzte_seite(page, base, prefix, ziel, breite, hoehe, dunkel, name) -> dict:
    """So oft „Weiter“, bis der Knopf aus ist — dann steht die LETZTE Seite."""
    for _ in range(20):
        weiter = page.locator('.pz-fuss button:has-text("Weiter")')
        if not weiter.count() or weiter.first.is_disabled():
            break
        weiter.first.click()
        page.wait_for_timeout(700)
    page.wait_for_timeout(600)
    schuss(page, ziel, name)
    return zaehlen(page)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--prefix", default="")
    p.add_argument("--admin", required=True, help="email:passwort")
    p.add_argument("--mitglied", required=True, help="email:passwort")
    p.add_argument("--ziel", required=True)
    args = p.parse_args()

    os.makedirs(args.ziel, exist_ok=True)
    belege: dict = {}
    admin_email, admin_pass = args.admin.split(":", 1)
    mitglied_email, mitglied_pass = args.mitglied.split(":", 1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        for rolle, (email, passwort) in (("admin", (admin_email, admin_pass)),
                                         ("mitglied", (mitglied_email, mitglied_pass))):
            kontext = browser.new_context(ignore_https_errors=True)
            page = kontext.new_page()
            anmelden(page, args.base, args.prefix, email, passwort)
            seite_id = page.url
            print(f"[{rolle}] angemeldet auf {seite_id}", flush=True)
            for breite, hoehe, groesse in ((1440, 900, "desktop"), (390, 844, "mobil")):
                for dunkel in (False, True):
                    modus = "dunkel" if dunkel else "hell"
                    name = f"{rolle}-{groesse}-{modus}"
                    daten = seite_besuchen(page, args.base, args.prefix, "#/personen/liste",
                                           breite, hoehe, dunkel, args.ziel, name + "-liste")
                    belege[name + "-liste"] = daten
                    # Befund 2: Blättern auf der letzten Seite.
                    if rolle == "admin" and daten.get("weiter"):
                        belege[name + "-letzte"] = letzte_seite(
                            page, args.base, args.prefix, args.ziel, breite, hoehe, dunkel,
                            name + "-letzte-seite")
                    # Befund 1: persönliche Daten anzeigen (nur Admin).
                    if rolle == "admin":
                        knopf = page.locator('button:has-text("Persönliche Daten anzeigen")')
                        if knopf.count():
                            seite_besuchen(page, args.base, args.prefix, "#/personen/liste",
                                           breite, hoehe, dunkel, args.ziel, name + "-liste")
                            knopf = page.locator('button:has-text("Persönliche Daten anzeigen")')
                            knopf.first.click()
                            page.wait_for_timeout(1500)
                            schuss(page, args.ziel, name + "-persoenliche-daten")
                            belege[name + "-persoenliche-daten"] = zaehlen(page)
            kontext.close()
        browser.close()

    with open(os.path.join(args.ziel, "belege.json"), "w", encoding="utf-8") as fh:
        json.dump(belege, fh, ensure_ascii=False, indent=2)
    print(json.dumps(belege, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
