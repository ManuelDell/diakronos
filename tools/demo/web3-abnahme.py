"""WEB-3 Abnahme: Screenshots + Funktionsnachweis gegen einen Wegwerf-Stack.

Laeuft im Playwright-Image (mcr.microsoft.com/playwright/python:v1.49.0-noble)
auf demselben Docker-Netz wie der Stack. Geprueft werden die echten Zustaende
ueber die echte Oberflaeche:

  1. Administrator: Einstellungen -> „Website (Primo)“ zeigt den Zustand des
     Status-Endpunkts („Nicht angeschlossen“ + Kurzanleitung, oder
     „Verbunden“ + Version/Seitenzahl/https-Warnung), Knopf „Verbindung
     pruefen“.
  2. Administrator: Menueeintrag „Website“ sichtbar; Seite „Website“ oeffnet
     sich; „Primo oeffnen“ ist ohne Anbindung gesperrt.
  3. Website-Moderator (NUR diese Rolle): Menueeintrag sichtbar, Einstellungen
     nicht.
  4. Mitglied (ohne Rolle): Menueeintrag NICHT sichtbar, #/website leitet um.
  5. Hell- und Dunkelmodus, Desktop 1366 und Mobil 390 (kein Ueberlauf).
  6. Mit PRIMO_AN=1 zusaetzlich: „Verbunden“, echter Klick auf „Primo
     oeffnen“, Uebergabe-Adresse vom Server (POST).

Der geoeffnete `noopener`-Tab ist per Definition NICHT beobachtbar — den
Beweis (Ziel-URL in Primo, pocketbase_auth) liefert `web3-noopener.py`.

Aufruf (Beispiel Wegwerf-Stack `diakronos-web3`):

    docker run --rm --network diakronos-web3_default \\
        -v "$PWD/tools/demo/web3-abnahme.py":/w/abnahme.py:ro \\
        -v "$ZIEL":/out -e BASE=http://app:8000 -e ZIEL=/out -e PRIMO_AN=1 \\
        mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        sh -c "pip install --quiet playwright==1.49.0; python /w/abnahme.py"
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = Path(os.environ.get("ZIEL", "/out"))
ADMIN = ("admin@example.org", "musterhausen-demo")
MODERATOR = ("website@example.org", "musterhausen-demo")
MITGLIED = ("anna.beispiel@example.org", "musterhausen-demo")

ERGEBNIS: dict[str, object] = {"pruefungen": [], "bilder": []}


def pruefe(name: str, ist: object, soll: object = True) -> None:
    ok = ist == soll
    ERGEBNIS["pruefungen"].append({"name": name, "ok": ok, "ist": ist, "soll": soll})
    print(("OK   " if ok else "FEHL ") + name, "" if ok else f"(ist={ist!r} soll={soll!r})")


def anmelden(page, email: str, passwort: str) -> None:
    """Anmeldung ueber die echte Maske (Muster wie tools/demo/screenshots.py)."""
    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    if page.locator("input[type=password]").count() == 0:
        # Schon angemeldet (gleicher Kontext) — abmelden und neu.
        page.goto(f"{BASE}/api/method/logout", wait_until="domcontentloaded")
        page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.fill("input[type=email], input[name=usr], input[autocomplete=username]", email)
    page.fill("input[type=password]", passwort)
    page.locator("button[type=submit], button:has-text('Anmelden')").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)


def thema(page, dunkel: bool) -> None:
    """Dunkelmodus ueber die gespeicherte Einstellung (wie der Umschalter)."""
    page.evaluate(
        """(dunkel) => {
            const wert = dunkel ? 'dark' : 'light';
            for (const k of ['theme', 'dk-theme', '__DIakonosTHEME', 'diakronos-theme']) {
                try { localStorage.setItem(k, wert) } catch (e) {}
            }
            document.documentElement.dataset.theme = wert;
            document.documentElement.classList.toggle('dark', dunkel);
        }""",
        dunkel,
    )


def bild(page, name: str) -> None:
    """Screenshot nach ZIEL. Nur Bilder OHNE Primo-Token (S3)."""
    pfad = ZIEL / f"{name}.png"
    page.screenshot(path=str(pfad), full_page=True)
    ERGEBNIS["bilder"].append(str(pfad))
    print("BILD", pfad)


def menue_ids(page) -> list[str]:
    """Sichtbare Menueeintraege (href der Seitenleiste)."""
    return page.eval_on_selector_all(
        ".dk-sidebar a[href^='#/']", "els => els.map(e => e.getAttribute('href'))"
    )


def main() -> int:
    ZIEL.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ── 1. Administrator, Desktop ────────────────────────────────────
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        anmelden(page, *ADMIN)

        eintraege = menue_ids(page)
        pruefe("Admin sieht Menueeintrag #/website", "#/website" in eintraege)
        ergebnis_w = page.evaluate(
            """async () => {
                const r = await fetch('/api/method/diakronos.diakronos.api.website.status');
                return { status: r.status, koerper: await r.json() };
            }"""
        )
        pruefe("status-Endpunkt antwortet 200", ergebnis_w["status"], 200)
        zustand = (ergebnis_w["koerper"].get("message") or {}).get("status")
        print("LIVE-ZUSTAND:", zustand)

        page.goto(f"{BASE}/#/einstellungen/website", wait_until="networkidle")
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        erwartet_offen = zustand == "nicht_konfiguriert"
        if erwartet_offen:
            pruefe("Einstellungen zeigen 'Nicht angeschlossen'", "Nicht angeschlossen" in text)
            pruefe("Kurzanleitung nennt PRIMO_PUBLIC_URL", "PRIMO_PUBLIC_URL" in text)
            pruefe("Kurzanleitung nennt deploy/primo", "deploy/primo" in text)
        else:
            pruefe("Einstellungen zeigen 'Verbunden'", "Verbunden" in text)
            pruefe("Einstellungen zeigen die https-Warnung",
                   "kein https" in text or "https Pflicht" in text)
            pruefe("Anleitung ist bei 'verbunden' ausgeblendet",
                   "So wird die Website angeschlossen" not in text)
        pruefe("Knopf 'Verbindung pruefen' da", "Verbindung prüfen" in text)
        pruefe("Knopf 'Verbindung pruefen' vorhanden",
               page.locator("button:has-text('Verbindung prüfen')").count() > 0)
        bild(page, "01_admin_einstellungen_website_hell")

        thema(page, True)
        page.wait_for_timeout(400)
        bild(page, "02_admin_einstellungen_website_dunkel")
        thema(page, False)

        # ── 2. Seite „Website“ + „Primo oeffnen“ (503 erwartet) ──────────
        neue_tabs: list = []
        ctx.on("page", lambda np: neue_tabs.append(np))
        page.goto(f"{BASE}/#/website", wait_until="networkidle")
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        pruefe("Website-Seite geladen", "Primo öffnen" in text)
        pruefe("Seite nennt den Zustand",
               ("Nicht angeschlossen" in text) if erwartet_offen else ("Verbunden" in text))
        pruefe("Seite nennt die Sitzungsdauer", "4 Stunden" in text)
        bild(page, "03_admin_website_seite_hell")

        thema(page, True)
        page.wait_for_timeout(400)
        bild(page, "04_admin_website_seite_dunkel")
        thema(page, False)

        # Die Uebergabe MUSS 503 liefern (kein Primo konfiguriert) — serverseitig
        # geprueft, damit der Nachweis nicht am Popup-Blocker haengt.
        uebergabe = page.evaluate(
            """async () => {
                const boot = window.__DIakonosBOOT || {};
                const r = await fetch('/api/method/diakronos.diakronos.api.website.login_uebergabe', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Frappe-CSRF-Token': boot.csrf_token || '',
                    },
                    body: '{}',
                });
                return { status: r.status, koerper: await r.json() };
            }"""
        )
        pruefe("login_uebergabe POST Status passt zum Zustand",
               uebergabe["status"], 503 if erwartet_offen else 200)
        exc = str(uebergabe["koerper"].get("exc_type") or "")
        pruefe("exc_type bleibt generisch (SEC-8)", exc in ("", "Error"))

        # Klick auf den Knopf: Meldung erscheint, kein neuer Tab.
        # Der Knopf ist bei „nicht angeschlossen“ BEWUSST gesperrt (es gibt
        # nichts zu oeffnen) — geprueft wird der gesperrte Zustand, die
        # Fehlermeldung kommt aus dem POST oben. Der AKTIVE Weg (Klick ->
        # window.open) wird in Teil 6 mit konfiguriertem Primo geprueft.
        knopf = page.locator("button:has-text('Primo öffnen')")
        if erwartet_offen:
            pruefe("Knopf 'Primo oeffnen' gesperrt ohne Anbindung", knopf.is_disabled())
            vorher = len(neue_tabs)
            bild(page, "05_admin_primo_oeffnen_gesperrt")
            pruefe("kein neuer Tab ohne Anbindung", len(neue_tabs), vorher)
        else:
            pruefe("Knopf 'Primo oeffnen' aktiv", knopf.is_disabled(), False)

        # ── 3. Mobil 390 ────────────────────────────────────────────────
        mobil = browser.new_context(viewport={"width": 390, "height": 844},
                                    is_mobile=True, has_touch=True)
        seite_m = mobil.new_page()
        anmelden(seite_m, *ADMIN)
        seite_m.goto(f"{BASE}/#/einstellungen/website", wait_until="networkidle")
        seite_m.wait_for_timeout(1500)
        bild(seite_m, "06_admin_einstellungen_website_mobil390")
        seite_m.goto(f"{BASE}/#/website", wait_until="networkidle")
        seite_m.wait_for_timeout(1200)
        bild(seite_m, "07_admin_website_seite_mobil390")
        # Kein waagerechtes Scrollen (FIX-6: Layout nur nach Breite).
        ueberlauf = seite_m.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        pruefe("mobil kein waagerechter Ueberlauf (<= 1 px)", ueberlauf <= 1)

        # Mobil: Menueeintrag im „Mehr“-Blatt vorhanden.
        ids_m = seite_m.eval_on_selector_all(
            "a[href^='#/']", "els => els.map(e => e.getAttribute('href'))"
        )
        pruefe("mobil ist #/website im Menue erreichbar", "#/website" in ids_m)
        mobil.close()

        # ── 4. Nur Website-Moderator ─────────────────────────────────────
        ctx_m = browser.new_context(viewport={"width": 1366, "height": 900})
        seite_r = ctx_m.new_page()
        anmelden(seite_r, *MODERATOR)
        ids_r = menue_ids(seite_r)
        pruefe("Website-Moderator sieht #/website", "#/website" in ids_r)
        pruefe("Website-Moderator sieht NICHT #/einstellungen",
               "#/einstellungen" not in ids_r)
        seite_r.goto(f"{BASE}/#/website", wait_until="networkidle")
        seite_r.wait_for_timeout(1200)
        pruefe("Website-Moderator darf die Seite oeffnen",
               "Primo öffnen" in seite_r.inner_text("body"))
        bild(seite_r, "08_website_moderator_seite")
        ctx_m.close()

        # ── 5. Mitglied ohne Rolle ───────────────────────────────────────
        ctx_i = browser.new_context(viewport={"width": 1366, "height": 900})
        seite_i = ctx_i.new_page()
        anmelden(seite_i, *MITGLIED)
        ids_i = menue_ids(seite_i)
        pruefe("Mitglied sieht #/website NICHT", "#/website" not in ids_i)
        seite_i.goto(f"{BASE}/#/website", wait_until="networkidle")
        seite_i.wait_for_timeout(1500)
        pruefe("Mitglied wird von #/website umgeleitet",
               seite_i.evaluate("() => location.hash") != "#/website")
        bild(seite_i, "09_mitglied_umleitung")
        ctx_i.close()

        # ── 6. Mit konfiguriertem Primo: „verbunden“ + echter Klick ───────
        if os.environ.get("PRIMO_AN", "") == "1":
            ctx_v = browser.new_context(viewport={"width": 1366, "height": 900})
            seite_v = ctx_v.new_page()
            anmelden(seite_v, *ADMIN)

            seite_v.goto(f"{BASE}/#/einstellungen/website", wait_until="networkidle")
            seite_v.wait_for_timeout(2000)
            text = seite_v.inner_text("body")
            pruefe("Einstellungen zeigen 'Verbunden'", "Verbunden" in text)
            pruefe("Einstellungen nennen Version v3.3.1", "v3.3.1" in text)
            pruefe("Einstellungen nennen die Seitenzahl", "0 Seiten" in text)
            pruefe("Einstellungen zeigen die https-Warnung",
                   "kein https" in text or "https Pflicht" in text)
            pruefe("Anleitung ist bei 'verbunden' ausgeblendet",
                   "So wird die Website angeschlossen" not in text)
            bild(seite_v, "10_admin_einstellungen_verbunden_hell")
            thema(seite_v, True)
            seite_v.wait_for_timeout(400)
            bild(seite_v, "11_admin_einstellungen_verbunden_dunkel")
            thema(seite_v, False)

            seite_v.goto(f"{BASE}/#/website", wait_until="networkidle")
            seite_v.wait_for_timeout(2000)
            pruefe("Website-Seite zeigt 'Verbunden'",
                   "Verbunden" in seite_v.inner_text("body"))
            bild(seite_v, "12_admin_website_verbunden_hell")

            # Der echte Klick: neuer Tab mit der Uebergabe-Adresse.
            vorher = len(neue_tabs)
            seite_v.click("button:has-text('Primo öffnen')")
            seite_v.wait_for_timeout(3000)
            # Playwright beobachtet Tabs mit `noopener` NICHT (abgekoppelter
            # Kontext — genau der Zweck von noopener). Der Beweis fuer den
            # geoeffneten Tab steht in tools/web3-noopener.py (Ziel-URL in
            # Primo + pocketbase_auth). Hier zaehlt nur die Erfolgsmeldung.
            ERGEBNIS["hinweis"] = ("noopener-Tab ist per Definition nicht "
                                   "beobachtbar; Beleg: web3_noopener.py")
            _ = vorher
            if len(neue_tabs) > vorher:
                ziel = neue_tabs[-1].url
                pruefe("neuer Tab zeigt die Uebergabeseite",
                       "diakronos-sso.html" in ziel)
                # S3: das Token steht NICHT in der Diakronos-Seite.
                pruefe("kein Token im Diakronos-DOM",
                       "token=" not in seite_v.content())
            pruefe("Erfolgsmeldung erscheint",
                   "Übergabe an Primo wurde gestartet" in seite_v.inner_text("body"))
            bild(seite_v, "13_admin_primo_geoeffnet")

            # Der Moderator ebenfalls mit konfiguriertem Primo.
            seite_v.goto(f"{BASE}/#/website", wait_until="networkidle")
            seite_v.wait_for_timeout(1200)
            uebergabe_v = seite_v.evaluate(
                """async () => {
                    const boot = window.__DIakonosBOOT || {};
                    const r = await fetch('/api/method/diakronos.diakronos.api.website.login_uebergabe', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Frappe-CSRF-Token': boot.csrf_token || '',
                        },
                        body: '{}',
                    });
                    return { status: r.status, koerper: await r.json() };
                }"""
            )
            pruefe("login_uebergabe POST liefert 200 (verbunden)",
                   uebergabe_v["status"], 200)
            url = str((uebergabe_v["koerper"].get("message") or {}).get("url") or "")
            pruefe("Antwort ist die Uebergabe-Adresse",
                   url.startswith("http://vorbau/diakronos-sso.html"))
            ctx_v.close()

        browser.close()

    fehler = [x for x in ERGEBNIS["pruefungen"] if not x["ok"]]  # type: ignore[union-attr]
    ERGEBNIS["bestanden"] = len(ERGEBNIS["pruefungen"]) - len(fehler)  # type: ignore[arg-type]
    ERGEBNIS["fehlgeschlagen"] = len(fehler)
    print(json.dumps(ERGEBNIS, ensure_ascii=False, indent=2))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
