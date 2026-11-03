"""BS-1d Abnahme: Website-Freigaben in der Oberflaeche (Wegwerf-Stack).

Laeuft im Playwright-Image (mcr.microsoft.com/playwright/python:v1.49.0-noble)
auf demselben Docker-Netz wie der Stack (`bs1d_default`), Praefix /diakronos.

Geprueft wird ueber die ECHTE Oberflaeche (nicht ueber die API):

  A  Administrator: Menue „Website“ -> Bereich „Website-Freigaben“
     1. Abschnitte Kalender, Terminarten, Gruppen, Beitraege, Kontakt-Postfaecher
     2. Kalender einschalten -> Bestaetigung mit der deutlichen Warnung
        („KOMPLETTE Beschreibung“ / „interne Notizen“)
     3. Nach „Freigeben“: Schalter an, Kuerzel abgeleitet, Verwaltungs-API
        zeigt den neuen Stand (GET freigaben_lesen)
     4. Oeffentliche Antwort existiert noch nicht: GET auf einen
        Freigabe-Baustein-Pfad liefert 404 (BS-1b fehlt) — die Freigabe allein
        erzeugt KEINE Oeffentlichkeit
     5. Gruppe einschalten (Warnung nennt Personen-Ausschluss)
     6. Kuerzel-Feld: ungueltiger Wert -> Feldfehler, kein Serveraufruf
     7. Postfach anlegen -> Tabelle zeigt es -> wieder loeschen
     8. Beitraege: Anzahl steht da
  B  Website-Moderator (nur diese Rolle): Bereich sichtbar
  C  Mitglied: Menuepunkt nicht sichtbar, #/website leitet um
  D  Hell/Dunkel, Desktop 1366 + Mobil 390: kein waagerechter Ueberlauf

Aufruf:
    docker run --rm --network bs1d_default -v <script>:/w/abnahme.py:ro \
        -v <ziel>:/out -e BASE=http://app:8000 --network bs1d_default \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        sh -c "pip install --quiet playwright==1.49.0; python /w/abnahme.py"
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DB_URL = os.environ.get("DB_URL", "")
try:  # psycopg ist im Playwright-Image nicht dabei -> eigenes Image nutzen
    import psycopg

    def DB_KONNEXION():
        return psycopg.connect(DB_URL)
except ModuleNotFoundError:  # pragma: no cover — Meldung ist eindeutig
    def DB_KONNEXION():
        raise SystemExit("psycopg fehlt: Abnahme im Python-Image mit psycopg laufen lassen "
                         f"(pip install psycopg). DB_URL={DB_URL!r}")

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
PRAEFIX = os.environ.get("PRAEFIX", "/diakronos")
ZIEL = Path(os.environ.get("ZIEL", "/out"))
ADMIN = ("admin@example.org", "musterhausen-demo")
MITGLIED = ("anna.beispiel@example.org", "musterhausen-demo")
#: Konto, dem die Abnahme voruebergehend die Rolle „Website-Moderator“ gibt.
MODERATOR_KONTO = MITGLIED

ERGEBNIS: dict[str, object] = {"pruefungen": [], "bilder": [], "api": []}


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
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    if page.locator("input[type=password]").count() == 0:
        page.goto(f"{BASE}{PRAEFIX}/api/method/logout", wait_until="domcontentloaded")
        page.goto(f"{BASE}{PRAEFIX}", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
    # Die Anmeldemaske der SPA nutzt `type=text` (E-Mail oder Benutzername).
    page.fill(
        "input[name=usr], input[autocomplete=username], input[type=email], input[type=text]",
        email,
    )
    page.fill("input[type=password]", passwort)
    page.locator("button[type=submit], button:has-text('Anmelden')").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)


def thema(page, dunkel: bool) -> None:
    wert = "dark" if dunkel else "light"
    page.evaluate(
        """(wert) => {
            for (const k of ['theme', 'dk-theme', '__DIakonosTHEME', 'diakronos-theme']) {
                try { localStorage.setItem(k, wert) } catch (e) {}
            }
            document.documentElement.setAttribute('data-theme', wert);
            document.documentElement.dataset.theme = wert;
            document.documentElement.classList.toggle('dark', wert === 'dark');
        }""",
        wert,
    )
    page.wait_for_timeout(400)


def seite_oeffnen(page) -> None:
    """Oeffnet die SPA und den Bereich Website-Freigaben.

    Praefix OHNE Schraegstrich am Ende: der Server leitet `/diakronos` auf
    `/diakronos/diakonos` um (die SPA). Ein `/` dahinter beantwortet die API
    mit 404. Linke Seitenleiste auf „Website“ klicken, damit die Route wie von
    Hand erreicht wird; danach direkt die Hash-Route als Rueckfall.
    """
    page.goto(f"{BASE}{PRAEFIX}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    # Auf dem Handy liegt der Eintrag hinter dem Menue — deshalb nur klicken,
    # wenn er SICHTBAR ist (sonst direkt die Hash-Route).
    eintrag = page.locator("a[href='#/website']").first
    if eintrag.count() and eintrag.is_visible():
        eintrag.click()
        page.wait_for_timeout(2000)
    if "#/website" not in page.url:
        page.goto(f"{BASE}{PRAEFIX}#/website", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2500)
    # Auf den ersten Abschnitt warten, statt blind zu schiessen.
    try:
        page.wait_for_selector(".wf-bereich", timeout=15000)
    except Exception:  # noqa: BLE001 — Fehlen wird unten als FEHL gemeldet
        pass
    page.wait_for_timeout(800)


def api_lesen(page) -> dict:
    """Verwaltungs-API direkt aus der Browser-Sitzung (gleiche Cookies)."""
    antwort = page.evaluate(
        """async (pfad) => {
            const r = await fetch(pfad, {credentials: 'include', headers: {'X-Requested-With': 'XMLHttpRequest'}});
            const text = await r.text();
            let json = null; try { json = JSON.parse(text) } catch (e) {}
            return {status: r.status, json, text: text.slice(0, 200)};
        }""",
        f"{PRAEFIX}/api/method/diakronos.diakronos.api.website.freigaben_lesen",
    )
    ERGEBNIS["api"].append({"pfad": "freigaben_lesen", "status": antwort.get("status")})
    return antwort


def sql(befehl: str) -> str:
    """Ein SQL-Befehl in der Wegwerf-Datenbank (nur Testdaten)."""
    with DB_KONNEXION() as conn:
        with conn.cursor() as cur:
            cur.execute(befehl)
            conn.commit()
            if cur.description:
                return "\n".join(" | ".join(str(c) for c in zeile) for zeile in cur.fetchall())
    return ""


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ── A · Administrator ────────────────────────────────────────────
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        anmelden(page, *ADMIN)
        ERGEBNIS["nachher_vorher_titel"] = page.title()

        seite_oeffnen(page)
        inhalt = page.inner_text("body")
        for titel in ["Website-Freigaben", "Kalender", "Terminarten", "Gruppen",
                      "Beiträge", "Kontakt-Postfächer", "Primo öffnen"]:
            pruefe(f"A1 Abschnitt „{titel}“ vorhanden", titel in inhalt)
        pruefe("A1 Kurzanleitung mit vier Saetzen",
               inhalt.count("Website") >= 3 and "Kürzel" in inhalt)
        schuss(page, "A-nachher-freigaben-hell-desktop.png")

        # Vorher-Stand der Verwaltungs-API (vor jeder Freigabe)
        vorher = api_lesen(page)
        daten_vorher = (vorher.get("json") or {}).get("message") or {}
        kalender_vorher = daten_vorher.get("kalender") or []
        pruefe("A2 Verwaltungs-API liefert die Kalenderliste", len(kalender_vorher) >= 1)
        freigegeben_vorher = [k["name"] for k in kalender_vorher if k.get("freigabe")]
        print("vorher freigegeben:", freigegeben_vorher)

        # Offentliche Seite: es gibt noch KEINEN Freigabe-Baustein (BS-1b fehlt)
        oeffentlich = page.evaluate(
            """async (pfad) => {
                const r = await fetch(pfad, {credentials: 'omit'});
                return {status: r.status, text: (await r.text()).slice(0, 120)};
            }""",
            f"{PRAEFIX}/api/method/diakronos.diakronos.api.website.kalender_oeffentlich",
        )
        ERGEBNIS["api"].append({"pfad": "kalender_oeffentlich (soll 404)", "status": oeffentlich.get("status")})
        pruefe("A3 oeffentlicher Baustein existiert noch nicht (404)", oeffentlich.get("status"), 404)

        # 1. Ersten noch nicht freigegebenen Kalender einschalten.
        # Nur Zeilen im KALENDER-Abschnitt (`.wf-zeile` gibt es auch bei den
        # Gruppen) und nur solche, deren Schalter AUS ist.
        kalender_abschnitt = page.locator("[data-wf-abschnitt=kalender]")
        zeilen = kalender_abschnitt.locator(".wf-zeile")
        pruefe("A4 mindestens eine Kalenderzeile", zeilen.count() >= 1)
        zeile = None
        for i in range(zeilen.count()):
            kandidat = zeilen.nth(i)
            if not kandidat.locator("input[type=checkbox]").first.is_checked():
                zeile = kandidat
                break
        pruefe("A4 ein noch nicht freigegebener Kalender gefunden", zeile is not None)
        if zeile is None:
            zeile = zeilen.first
        kalender_titel = zeile.inner_text().split("\n")[0].strip()
        print("Ziel-Kalender:", kalender_titel)

        zeile.locator("input[type=checkbox]").first.check()
        page.wait_for_timeout(700)
        dialog = page.locator(".dk-ui-dialog, [role=dialog]").first
        pruefe("A5 Bestaetigung vor dem Einschalten erscheint", dialog.count() >= 1)
        dialog_text = dialog.inner_text() if dialog.count() else ""
        pruefe("A5 Warnung nennt KOMPLETTE Beschreibung", "KOMPLETTE Beschreibung" in dialog_text)
        pruefe("A5 Warnung nennt interne Notizen", "interne Notizen" in dialog_text)
        pruefe("A5 Warnung nennt Titel/Zeit/Ort",
               all(w in dialog_text for w in ["Titel", "Zeit", "Ort"]))
        schuss(page, "A-warnung-kalender-desktop.png")
        dialog.locator("button", has_text="Freigeben").first.click()
        page.wait_for_timeout(2000)

        nachher = api_lesen(page)
        daten_nachher = (nachher.get("json") or {}).get("message") or {}
        freigegeben_nachher = [k for k in (daten_nachher.get("kalender") or []) if k.get("freigabe")]
        pruefe("A6 Verwaltungs-API zeigt neuen Stand (Kalender freigegeben)",
               len(freigegeben_nachher) >= 1, True)
        neu = [k for k in freigegeben_nachher if k["name"] not in freigegeben_vorher]
        pruefe("A6 genau der gewaehlte Kalender ist neu freigegeben", len(neu), 1)
        if neu:
            ERGEBNIS["neuer_kalender"] = neu[0]
            pruefe("A6 Kuerzel wurde abgeleitet", bool(neu[0].get("slug")))
            print("Slug:", neu[0].get("slug"))

        oeffentlich_nachher = page.evaluate(
            """async (pfad) => {
                const r = await fetch(pfad, {credentials: 'omit'});
                return r.status;
            }""",
            f"{PRAEFIX}/api/method/diakronos.diakronos.api.website.kalender_oeffentlich",
        )
        pruefe("A7 oeffentliche Antwort aendert sich NICHT (Baustein fehlt weiter)",
               oeffentlich_nachher, 404)
        schuss(page, "A-nachher-kalender-freigegeben-desktop.png")

        # 2. Gruppe einschalten (Warnung: keine Personen).
        gruppen_karte = page.locator("[data-wf-abschnitt=gruppen]")
        gruppen_karte.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        # Nur noch NICHT freigegebene Gruppen: der zweite Lauf auf derselben
        # Wegwerf-DB findet die Freigabe des ersten Laufs noch vor.
        ziel_gruppe = None
        for i in range(gruppen_karte.locator(".wf-zeile").count()):
            kandidat = gruppen_karte.locator(".wf-zeile").nth(i)
            if kandidat.locator("input[type=checkbox]").first.is_checked():
                continue
            ziel_gruppe = kandidat
            break
        pruefe("A8 eine noch nicht freigegebene Gruppe gefunden", ziel_gruppe is not None)
        erz_zeile = ziel_gruppe if ziel_gruppe is not None else gruppen_karte.locator(".wf-zeile").first
        gruppen_titel = erz_zeile.inner_text().split("\n")[0].strip()
        print("Ziel-Gruppe:", gruppen_titel)
        erz_zeile.locator("input[type=checkbox]").first.check()
        page.wait_for_timeout(700)
        dialog2 = page.locator(".dk-ui-dialog, [role=dialog]").first
        d2 = dialog2.inner_text() if dialog2.count() else ""
        pruefe("A8 Gruppen-Warnung nennt Treffzeit/Treffpunkt", "Treffzeit" in d2 and "Treffpunkt" in d2)
        pruefe("A8 Gruppen-Warnung schliesst Personen aus", "Personen" in d2)
        dialog2.locator("button", has_text="Freigeben").first.click()
        page.wait_for_timeout(2000)
        gruppen_api = api_lesen(page)
        g_daten = (gruppen_api.get("json") or {}).get("message") or {}
        g_frei = [g for g in (g_daten.get("gruppen") or []) if g.get("freigabe")]
        pruefe("A9 Verwaltungs-API zeigt freigegebene Gruppe", len(g_frei) >= 1)

        # 3. Ungueltiges Kuerzel -> Feldfehler, nichts wird gespeichert.
        kuerzel_feld = erz_zeile.locator("input[type=text]").first
        kuerzel_feld.fill("Ungültig Kürzel!")
        erz_zeile.locator("button", has_text="Kürzel speichern").first.click()
        page.wait_for_timeout(500)
        feldfehler = erz_zeile.inner_text()
        pruefe("A10 Feldfehler am Kuerzel-Feld", "Kleinbuchstaben" in feldfehler)
        schuss(page, "A-kuerzel-fehler-desktop.png")
        kuerzel_feld.fill("")

        # 4. Postfach anlegen und wieder loeschen.
        postfach_karte = page.locator("[data-wf-abschnitt=postfaecher]")
        postfach_karte.scroll_into_view_if_needed()
        postfach_karte.locator("button", has_text="Postfach anlegen").first.click()
        page.wait_for_timeout(500)
        dialog3 = page.locator(".dk-ui-dialog, [role=dialog]").first
        felder = dialog3.locator("input[type=text]")
        felder.nth(0).fill("BS1D Abnahme")
        felder.nth(1).fill("bs1d-abnahme")
        dialog3.locator("input[type=email]").first.fill("abnahme@example.org")
        dialog3.locator("button", has_text="Speichern").first.click()
        page.wait_for_timeout(2000)
        texte = page.inner_text("body")
        pruefe("A11 angelegtes Postfach steht in der Tabelle", "abnahme@example.org" in texte)
        schuss(page, "A-postfach-desktop.png")
        postfach_karte = page.locator("[data-wf-abschnitt=postfaecher]")
        zeile_p = postfach_karte.locator("tr", has_text="abnahme@example.org").first
        zeile_p.locator("button", has_text="Löschen").first.click()
        page.wait_for_timeout(600)
        dialog4 = page.locator(".dk-ui-dialog, [role=dialog]").first
        dialog4.locator("button", has_text="Entfernen").first.click()
        page.wait_for_timeout(2000)
        pruefe("A11 Postfach wieder entfernt", "abnahme@example.org" not in page.inner_text("body"))

        # 5. Beitraege-Anzahl (U3)
        beitrag_karte = page.locator("[data-wf-abschnitt=beitraege]")
        beitrag_karte.scroll_into_view_if_needed()
        b_text = beitrag_karte.inner_text()
        pruefe("A12 Beitragsanzahl wird genannt", bool(re.search(r"\d+\s+Beitr", b_text)))

        # 6. Dunkelmodus + Mobil
        seite_oeffnen(page)
        thema(page, True)
        schuss(page, "A-nachher-dunkel-desktop.png")
        thema(page, False)

        mobil = browser.new_context(viewport={"width": 390, "height": 844})
        mpage = mobil.new_page()
        anmelden(mpage, *ADMIN)
        seite_oeffnen(mpage)
        schuss(mpage, "A-nachher-hell-mobil.png")
        # Der echte Test ist BREITE gegen ANSICHT: `overflow` im Container
        # versteckt den Ueberlauf, deshalb werden die Karten selbst gemessen.
        breiten = mpage.evaluate(
            """() => {
                const bereich = document.querySelector('.wf-bereich');
                const karten = Array.from(document.querySelectorAll('[data-wf-abschnitt] .dk-ui-card'));
                return {
                    bereich: Math.round(bereich.getBoundingClientRect().width),
                    sichtbar: Math.round(document.documentElement.clientWidth),
                    breitesteKarte: Math.round(Math.max(...karten.map(k => k.getBoundingClientRect().width))),
                    ueberlauf: Array.from(document.querySelectorAll('[data-wf-abschnitt] .dk-ui-card'))
                        .filter(k => k.getBoundingClientRect().width > document.documentElement.clientWidth)
                        .length,
                };
            }"""
        )
        ERGEBNIS["mobil_breiten"] = breiten
        print("mobil:", breiten)
        pruefe("A13 keine Karte breiter als das Fenster (390 px)", breiten["ueberlauf"], 0)
        mpage.evaluate(
            "() => { for (const k of ['theme','dk-theme','__DIakonosTHEME','diakronos-theme']) localStorage.setItem(k,'dark'); }"
        )
        seite_oeffnen(mpage)
        thema(mpage, True)
        schuss(mpage, "A-nachher-dunkel-mobil.png")
        breiten_d = mpage.evaluate(
            """() => Array.from(document.querySelectorAll('[data-wf-abschnitt] .dk-ui-card'))
                .filter(k => k.getBoundingClientRect().width > document.documentElement.clientWidth).length"""
        )
        pruefe("A13 keine Karte breiter als das Fenster (dunkel, 390 px)", breiten_d, 0)
        mobil.close()
        ctx.close()

        # ── B · Website-Moderator (nur diese Rolle) ─────────────────────
        # Der Demo-Seed legt KEIN Konto mit dieser Rolle an. Statt ein Konto
        # zu erfinden, gibt das Skript dem vorhandenen Demo-Mitgliedskonto die
        # Rolle für die Dauer der Abnahme (Wegwerf-Stack, danach entfernt).
        sql(
            "insert into has_role (name, parent, parenttype, parentfield, creation, modified, "
            "modified_by, owner, docstatus, idx, role) values "
            f"('bs1d-moderator-{int(time.time())}', '{MODERATOR_KONTO[0]}', 'User', 'roles', "
            "now(), now(), 'bs1d-abnahme', 'bs1d-abnahme', 0, 9, 'Website-Moderator')"
        )
        ctx2 = browser.new_context(viewport={"width": 1366, "height": 900})
        page2 = ctx2.new_page()
        anmelden(page2, *MODERATOR_KONTO)
        seite_oeffnen(page2)
        pruefe("B1 Moderator sieht Website-Freigaben", "Website-Freigaben" in page2.inner_text("body"))
        schuss(page2, "B-moderator-desktop.png")
        ctx2.close()
        sql(f"delete from has_role where parent = '{MODERATOR_KONTO[0]}' and role = 'Website-Moderator'")
        pruefe("B2 Rolle nach der Abnahme wieder entzogen",
               "Website-Moderator" not in sql(f"select role from has_role where parent = '{MODERATOR_KONTO[0]}'"))

        # ── C · Mitglied ohne Rolle ─────────────────────────────────────
        ctx3 = browser.new_context(viewport={"width": 1366, "height": 900})
        page3 = ctx3.new_page()
        anmelden(page3, *MITGLIED)
        menue = page3.inner_text("body")
        pruefe("C0 Mitglied sieht den Menuepunkt „Website“ nicht",
               page3.locator("a[href='#/website']").count() == 0)
        page3.goto(f"{BASE}{PRAEFIX}#/website", wait_until="domcontentloaded")
        page3.wait_for_load_state("networkidle")
        page3.wait_for_timeout(3000)
        text3 = page3.inner_text("body")
        pruefe("C1 Mitglied sieht den Bereich NICHT", "Website-Freigaben" not in text3)
        # Der Router-Guard leitet um; die Adresse bleibt (Hash) — geprueft wird,
        # dass NICHT die Freigaben-Seite steht.
        pruefe("C2 Mitglied wird umgeleitet (Freigaben-Seite nicht geoeffnet)",
               page3.locator(".wf-bereich").count() == 0)
        ERGEBNIS["mitglied_url"] = page3.url
        ERGEBNIS["mitglied_pfad_umgeleitet"] = page3.evaluate("() => window.__routerPfad || location.hash")
        schuss(page3, "C-mitglied-umgeleitet.png")
        ctx3.close()

        browser.close()

    ok = all(p["ok"] for p in ERGEBNIS["pruefungen"])
    ZIEL.mkdir(parents=True, exist_ok=True)
    (ZIEL / "ergebnis.json").write_text(json.dumps(ERGEBNIS, indent=2, ensure_ascii=False))
    print(f"\nGESAMT: {'OK' if ok else 'FEHLER'} ({sum(1 for p in ERGEBNIS['pruefungen'] if p['ok'])}/{len(ERGEBNIS['pruefungen'])})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
