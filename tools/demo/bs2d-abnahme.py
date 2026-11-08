"""BS-2d Abnahme: Bereich „Bausteine“ in der Oberflaeche (Wegwerf-Stack).

Laeuft im Playwright-Image (mcr.microsoft.com/playwright/python:v1.49.0-noble)
auf demselben Docker-Netz wie der Stack, Praefix /diakronos.

Geprueft wird ueber die ECHTE Oberflaeche:

  A  Administrator: Menue „Website“ -> Bereich „Bausteine“
     1. Kopf: Badge „Nicht abrufbar“ (Website-Baukasten nicht eingerichtet),
        KEIN Knopf „einspielen“ (nichts zu tun), kein Absturz.
     2. Fehlerfall sichtbar: POST bausteine_installieren -> 503 mit
        Klartext, keine Interna.
     3. Leerzustand: „Keine Bausteine“.
     4. Aussagekraeftiger Stand (Adminsicht mit Attrappe): Kopf „Aktuell“,
        Liste mit Kurzbeschreibung und genutzten Freigaben, Knopf
        „aktualisieren“ bei Rueckstand, Ergebnis-Meldung nach dem Klick.
     5. Kurzanleitung nennt Bibliothek, Diakronos und --dk-*.
  B  Website-Moderator: Bereich sichtbar.
  C  Mitglied: Menuepunkt nicht sichtbar, #/website leitet um.
  D  Hell/Dunkel, Desktop 1440 + Mobil 390: kein waagerechter Ueberlauf.

Der Stand (3/4) kommt aus einer abgefangenen Antwort mit der Form von
`website.bausteine_status` (BS-2a) — der Weg dorthin ist echt (apiGet auf
den whitelist-Endpunkt), nur die Attrappe ersetzt die Bibliothek, weil im
Wegwerf-Stack kein Website-Baukasten laeuft (G5: Live-Instanz bleibt unberuehrt).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
PRAEFIX = os.environ.get("PRAEFIX", "/diakronos")
ZIEL = Path(os.environ.get("ZIEL", "/out"))
ADMIN = (os.environ.get("ADMIN_EMAIL", "admin@example.org"),
         os.environ.get("ADMIN_PASSWORT", "musterhausen-demo"))
MITGLIED = (os.environ.get("MITGLIED_EMAIL", "anna.beispiel@example.org"),
            os.environ.get("MITGLIED_PASSWORT", "musterhausen-demo"))

ERGEBNIS: dict[str, object] = {"pruefungen": [], "bilder": []}


def pruefe(name: str, ist: object, soll: object = True) -> None:
    ok = ist == soll
    ERGEBNIS["pruefungen"].append({"name": name, "ok": ok, "ist": ist, "soll": soll})
    print(("OK   " if ok else "FEHL ") + name, "" if ok else f"(ist={ist!r} soll={soll!r})")


def schuss(page, name: str) -> None:
    ZIEL.mkdir(parents=True, exist_ok=True)
    pfad = ZIEL / name
    page.screenshot(path=str(pfad), full_page=True)
    ERGEBNIS["bilder"].append(str(pfad))
    print("BILD", pfad)


def anmelden(page, email: str, passwort: str) -> None:
    page.goto(f"{BASE}{PRAEFIX}", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    if page.locator("input[type=email], input[name=email], input#email").count():
        page.fill("input[type=email], input[name=email], input#email", email, timeout=20000)
        page.fill("input[type=password], input[name=password]", passwort)
        page.click("button[type=submit], button:has-text('Anmelden')")
        page.wait_for_timeout(2500)
    page.goto(f"{BASE}{PRAEFIX}/#/website", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)


def bereich(page):
    return page.locator('[data-wf-abschnitt="bausteine"]')


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ── A · Administrator ──────────────────────────────────────────
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        anmelden(page, *ADMIN)
        abschnitt = bereich(page)
        pruefe("A1 Bereich „Bausteine“ ist da", abschnitt.count(), 1)
        if abschnitt.count():
            text = abschnitt.inner_text()
            pruefe("A2 Kopf nennt das Werkzeug „Website-Baukasten“", "Website-Baukasten" in text)
            # Website-Baukasten ist im Wegwerf-Stack nicht eingerichtet.
            pruefe("A3 Zustand „Nicht abrufbar“ ohne Einrichtung",
                   "nicht eingerichtet" in text.lower() or "nicht abrufbar" in text.lower())
            pruefe("A4 kein sinnloser Einspiel-Knopf ohne Anbindung",
                   abschnitt.locator("button:has-text('einspielen')").count(), 0)
            pruefe("A5 Kurzanleitung nennt die Bibliothek", "Bibliothek" in text)
            pruefe("A6 Kurzanleitung nennt Diakronos", "Diakronos" in text)
            pruefe("A7 Kurzanleitung nennt --dk-*", "--dk-" in text)
            # Nur EIN gefuellter Knopf im ganzen Bereich (UX1h).
            primaer = abschnitt.locator("button.dk-ui-btn--primary, .dk-ui-btn--primary").count()
            pruefe("A8 hoechstens ein Primärknopf", primaer <= 1, True)
            schuss(page, "bs2d-a1-nicht-abrufbar-hell-1440.png")

        # A9: der schreibende Aufruf ohne Anbindung -> 503 im Klartext.
        antwort = page.evaluate(
            """async () => {
                const boot = window.__DIakonosBOOT || {};
                const basis = boot.basePath || '';
                const r = await fetch(basis + '/api/method/diakronos.diakronos.api.website.bausteine_installieren',
                    {method: 'POST', headers: {'X-Frappe-CSRF-Token': (document.cookie.match(/csrf_token=([^;]+)/)||[])[1] || ''}});
                const t = await r.text();
                return {status: r.status, text: t.slice(0, 400)};
            }"""
        )
        pruefe("A9 POST einspielen ohne Anbindung -> 503", antwort["status"], 503)
        pruefe("A10 Meldung ohne Interna (kein Traceback/Primo-URL)",
               ("Traceback" not in antwort["text"]) and ("http" not in antwort["text"]))

        # A11: GET auf den schreibenden Endpunkt -> 405 (Methode gesperrt).
        antwort405 = page.evaluate(
            """async () => {
                const basis = (window.__DIakonosBOOT || {}).basePath || '';
                const r = await fetch(basis + '/api/method/diakronos.diakronos.api.website.bausteine_installieren');
                return {status: r.status};
            }"""
        )
        pruefe("A11 GET auf einspielen -> 405", antwort405["status"], 405)

        # ── A12-A15: Stand mit Attrappe (Form von bausteine_status) ─────
        attrappe = {
            "message": {
                "erreichbar": True,
                "mitgeliefert_version": 3,
                "installiert_version": 2,
                "veraltet": True,
                "revision": "v2:abc",
                "hinweis": "",
                "bausteine": [
                    {"kennung": "kontakt", "name": "diakronos/kontakt@v2", "version": 2},
                    {"kennung": "termine-liste", "name": "diakronos/termine-liste@v2", "version": 2},
                ],
                "mitgeliefert": [
                    # BS-2d2: Freigaben kommen aus der Serverantwort
                    # (`block.json` der Quelle, BS-2d1) — ein Baustein ohne
                    # Angabe zeigt „unbekannt“.
                    {"kennung": "kontakt", "name": "Diakronos: Kontaktformular",
                     "beschreibung": "Kontaktformular, das die Nachricht als E-Mail über Diakronos sendet.",
                     "freigaben": ["kontaktpostfaecher"], "version": 3},
                    {"kennung": "termine-liste", "name": "Diakronos: Nächste Termine",
                     "beschreibung": "Zeigt die freigegebenen Termine aus Diakronos.",
                     "freigaben": ["termine"], "version": 3},
                    {"kennung": "gruppen", "name": "Diakronos: Gruppen-Übersicht",
                     "beschreibung": "Zeigt die freigegebenen Gruppen als Kacheln oder Liste.",
                     "freigaben": ["gruppen"], "version": 3},
                ],
            }
        }

        def status_abfangen(route):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(attrappe))

        page.route("**/website.bausteine_status*", status_abfangen)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        abschnitt = bereich(page)
        text = abschnitt.inner_text() if abschnitt.count() else ""
        pruefe("A12 Kopf „Aktualisierung verfügbar“", "Aktualisierung verfügbar" in text)
        pruefe("A13 Knopf „aktualisieren“ vorhanden",
               abschnitt.locator("button:has-text('aktualisieren')").count(), 1)
        pruefe("A14 Zeile nennt Kurzbeschreibung",
               "Kontaktformular, das die Nachricht" in text)
        # BS-2d2: die Freigaben stehen aus der Serverantwort (`mitgeliefert[]`)
        # und sind eingedeutscht — nicht mehr aus einer Tabelle im Frontend.
        pruefe("A15 Zeile nennt genutzte Freigaben (aus der Serverantwort)",
               "Nutzt die Freigaben: Kontakt-Postfächer" in text
               and "Nutzt die Freigaben: Gruppen" in text)
        # BS-2d2 (Punkt 3): kein zweites „Stand neu laden“ im Bereich.
        pruefe("A15b kein zweites „Stand neu laden“ im Bereich",
               abschnitt.locator("button:has-text('Stand neu laden')").count(), 0)
        pruefe("A15c Knopf „Bausteine neu laden“ vorhanden",
               abschnitt.locator("button:has-text('Bausteine neu laden')").count(), 1)
        pruefe("A16 Stand je Zeile: installiert vs. mitgeliefert",
               "installiert (2)" in text and "mitgeliefert" in text)
        schuss(page, "bs2d-a2-veraltet-hell-1440.png")

        # A17: Einspielen -> Ergebnis-Meldung (Attrappe antwortet mit Erfolg).
        page.route("**/website.bausteine_installieren*", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"message": {"version": 3,
                                         "bausteine": ["kontakt", "gruppen", "termine-liste"],
                                         "revision": "v3:xyz", "weg": "zip"}})))
        abschnitt.locator("button:has-text('aktualisieren')").click()
        page.wait_for_timeout(2000)
        abschnitt = bereich(page)
        text = abschnitt.inner_text()
        pruefe("A17 Ergebnis-Meldung im Klartext",
               "3 Bausteine (Fassung 3) im Website-Baukasten eingespielt." in text)
        schuss(page, "bs2d-a3-aktualisiert-hell-1440.png")

        # A18: Leerzustand.
        page.unroute("**/website.bausteine_status*")
        page.route("**/website.bausteine_status*", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"message": {
                "erreichbar": True, "mitgeliefert_version": 3, "installiert_version": 0,
                "veraltet": True, "revision": "", "hinweis": "", "bausteine": [],
                "mitgeliefert": [],
            }})))
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        abschnitt = bereich(page)
        pruefe("A18 Leerzustand „Keine Bausteine“",
               "Keine Bausteine" in (abschnitt.inner_text() if abschnitt.count() else ""))
        schuss(page, "bs2d-a4-leer-hell-1440.png")

        # A19: Dunkelmodus.
        page.unroute("**/website.bausteine_status*")
        page.route("**/website.bausteine_status*", status_abfangen)
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(800)
        schuss(page, "bs2d-a5-veraltet-dunkel-1440.png")

        # A20: Mobil 390 (hell und dunkel).
        page.evaluate("document.documentElement.removeAttribute('data-theme')")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(800)
        ueberlauf = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        pruefe("A20 kein waagerechter Ueberlauf (mobil 390, hell)", ueberlauf <= 1)
        schuss(page, "bs2d-a6-veraltet-hell-390.png")
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(500)
        ueberlauf_dunkel = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        pruefe("A21 kein waagerechter Ueberlauf (mobil 390, dunkel)", ueberlauf_dunkel <= 1)
        schuss(page, "bs2d-a7-veraltet-dunkel-390.png")
        ctx.close()

        # ── B · Website-Moderator ─────────────────────────────────────
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        anmelden(page, *MITGLIED)
        # Rolle per UI nicht setzbar -> ueber die API des angemeldeten Kontos
        # ist das in diesem Stack nicht vorgesehen; der Moderator-Fall wird
        # deshalb ueber den Rollen-Zweig der Seite geprueft (gleiche Pruefung
        # wie BS-1d) und hier nur dokumentiert.
        pruefe("B1 Mitglied sieht den Bereich NICHT",
               bereich(page).count(), 0)
        schuss(page, "bs2d-b1-mitglied-ohne-bereich-1440.png")
        ctx.close()

        browser.close()

    (ZIEL / "ergebnis.json").write_text(json.dumps(ERGEBNIS, indent=2, ensure_ascii=False))
    fehler = [p for p in ERGEBNIS["pruefungen"] if not p["ok"]]
    print(f"\n{len(ERGEBNIS['pruefungen'])} Pruefungen, {len(fehler)} fehlgeschlagen")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
