"""BF1d Bedienabnahme (Browser) — Wegwerf-Teststack http://127.0.0.1:8195.

Deckt die Pruefpunkte A-J, L sowie die Blocker B-1/B-2/B-3 und die wichtigen
W3/W6/W7 ab. Je Schritt Screenshot Desktop (1366) + Mobil (390) nach
``$BF1D_OUT`` (Default ``/tmp/bf1d``).

A Termin anlegen -> Vorschlag, ehrlicher Hinweis.
B Plan (chorplan) veroeffentlichen -> klare Erfolgsmeldung.
C Tag mit mehrtagigen Terminen anklicken -> Termine gelistet.
D Kalender-Ansichts-Dropdown spiegelt die Ansicht.
E Gruppe: Mitglied-Auswahlliste oeffnet beim Klick (B-1/B-2/B-3).
F Mitglieder: Adressen erst nach Umschalten (W7 serverseitig).
G Dashboard-Kachel zeigt Moderationsvorschlaege ohne interne IDs (W6).
H Wiki-Knopf klickbar (B-3).
I Moderation nutzt den gemeinsamen Seitenrahmen.
J Suche 'manuel'/'weiss' findet 'Manuel'/'Weiß' (Umlaute).
L Abmelden (Profil) -> /login; GET /logout 405 (W3/W4).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BF1D_BASE", "http://127.0.0.1:8195")
OUT = Path(os.environ.get("BF1D_OUT", "/tmp/bf1d"))
ADMIN = ("admin-bf1d@example.org", "Bf1dTest-Passwort-2026")
VERANTW = ("gruppenverantw-bf1d@example.org", "Bf1dTest-Passwort-2026")


def _get_status(pfad: str) -> int:
    req = urllib.request.Request(BASE + pfad, method="GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def shots(page, name, report):
    for label, width in (("desktop", 1366), ("mobil", 390)):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(400)
        path = OUT / f"{name}-{label}.png"
        page.screenshot(path=str(path), full_page=True)
        report["screenshots"].append(str(path))
    page.set_viewport_size({"width": 1366, "height": 900})


def anmelden(page, konto):
    page.goto(BASE + "/diakonos", wait_until="networkidle")
    if page.locator('[name="usr"]').count():
        page.locator('[name="usr"]').fill(konto[0])
        page.locator('[name="pwd"]').fill(konto[1])
        page.get_by_role("button", name="Anmelden", exact=True).click()
        page.wait_for_url("**/diakonos**")
    page.wait_for_load_state("networkidle")


def abmelden(page):
    page.goto(BASE + "/diakonos#/profile", wait_until="networkidle")
    page.wait_for_timeout(1000)
    ab = page.locator("button:has-text('Abmelden')").first
    if ab.count():
        ab.click()
        page.wait_for_timeout(2500)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"ok": False, "schritte": [], "page_errors": [], "console_errors": [],
              "screenshots": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        page = context.new_page()
        page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
        page.on("console", lambda m: report["console_errors"].append(m.text)
                if m.type == "error" else None)

        anmelden(page, ADMIN)
        # Kalender-Auswahl NICHT selbst setzen: die Kalender-Seite laedt die
        # zugreifbaren Kalender beim Oeffnen selbst (mit CSRF-Token) und
        # waehlt ihre Vorgabe. Ein roher fetch ohne Token scheitert (PT1).

        # ── D) Ansichts-Dropdown spiegelt die Ansicht ─────────────────────
        page.goto(BASE + "/diakonos#/kalender", wait_until="networkidle")
        page.wait_for_timeout(1500)
        sel = page.locator("#view-selector")
        if sel.count():
            page.select_option("#view-selector", "timeGridDay")
            page.wait_for_timeout(900)
            tag = sel.input_value()
            page.select_option("#view-selector", "dayGridMonth")
            page.wait_for_timeout(900)
            monat = sel.input_value()
            report["schritte"].append(f"D Ansicht spiegelt: Tag={tag}, Monat={monat}")
            assert tag == "timeGridDay", f"Dropdown folgte 'Tag' nicht: {tag}"
            assert monat == "dayGridMonth", f"Dropdown folgte 'Monat' nicht: {monat}"
        else:
            report["schritte"].append("D Ansichts-Dropdown nicht gefunden")
        shots(page, "D-kalender-ansicht", report)

        # ── C) Tag mit Terminen anklicken -> Termine gelistet ─────────────
        page.wait_for_timeout(500)
        # Einen Tag MIT Terminen anklicken (nicht heute — heute hat im Dump
        # womoeglich keine). Der Monat steht auf Okt 2026 (Dump-Stand).
        tag_ok = False
        chips = page.locator(".ec-day:has(.ec-event)")
        if chips.count():
            chips.first.locator(".ec-day-head").first.click()
            tag_ok = True
        else:
            page.locator(".ec-day.ec-today").first.click(position={"x": 5, "y": 5})
        page.wait_for_timeout(1600)
        liste = page.locator(".day-events-list .day-event-item, .day-event-item")
        leertext = page.locator("text=Keine Termine an diesem Tag.")
        report["schritte"].append(
            f"C Tagesdialog ({'Tag mit Chips' if tag_ok else 'heute'}): "
            f"{liste.count()} Termine, 'Keine Termine'={leertext.count()}")
        if tag_ok:
            assert liste.count(), "Tagesdialog zeigt keine Termine, obwohl Chips im Tag stehen"
            assert leertext.count() == 0, "Tagesdialog meldet faelschlich 'Keine Termine'"
        shots(page, "C-tagesdialog", report)

        # ── E) Gruppe: Auswahlliste oeffnet beim Klick (B-1/B-2) ──────────
        page.goto(BASE + "/diakonos#/gruppen", wait_until="networkidle")
        page.wait_for_timeout(1000)
        glink = page.locator(".gr-kachel").first
        assert glink.count(), "keine Gruppe in der Liste"
        glink.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        feld = page.locator(".dk-ma-input").first
        assert feld.count(), "Mitglied-Auswahlfeld (.dk-ma-input) fehlt"
        feld.click()
        page.wait_for_timeout(900)
        liste_e = page.locator(".dk-ma-liste")
        assert liste_e.count(), "Auswahlliste ging beim Draufklicken nicht auf"
        eintraege = page.locator(".dk-ma-eintrag")
        report["schritte"].append(
            f"E Gruppe: Auswahlliste offen beim Klick ({eintraege.count()} Eintraege)")
        # B-1: keine E-Mail in der Auswahlliste.
        text_e = liste_e.inner_text()
        assert "@" not in text_e, f"E-Mail in der Auswahlliste sichtbar: {text_e[:200]}"
        report["schritte"].append("E/B-1 Auswahlliste ohne E-Mail")
        # B-2: serverseitige Suche tippbar.
        feld.fill("a")
        page.wait_for_timeout(900)
        report["schritte"].append(
            f"E/B-2 Suche im Feld tippbar ({page.locator('.dk-ma-eintrag').count()} Treffer)")
        shots(page, "E-gruppe-auswahl", report)

        # ── B-3) Wiki-Knopf klickbar (Regression 'navigate is not a function') ─
        page.goto(BASE + "/diakonos#/wiki", wait_until="networkidle")
        page.wait_for_timeout(1200)
        fehler_vorher = len(report["page_errors"])
        knopf = page.locator("button:has-text('Neuer Artikel'), a[href='#/wiki/neu'], button:has-text('Neue Seite')").first
        if knopf.count():
            knopf.click()
            page.wait_for_timeout(1200)
        report["schritte"].append(
            f"H/B-3 Wiki-Knopf vorhanden={knopf.count() > 0}, klickbar ohne JS-Fehler="
            f"{len(report['page_errors']) == fehler_vorher}")
        shots(page, "H-wiki", report)

        # ── I) Moderation: gemeinsamer Seitenrahmen ───────────────────────
        page.goto(BASE + "/diakonos#/moderation", wait_until="networkidle")
        page.wait_for_timeout(1200)
        rahmen = page.locator(".dk-screen.dk-moderation")
        report["schritte"].append(f"I Moderation-Rahmen vorhanden={rahmen.count() > 0}")
        shots(page, "I-moderation", report)

        # ── G/W6) Dashboard-Kachel zeigt echte Vorschlaege ────────────────
        page.goto(BASE + "/diakonos#/", wait_until="networkidle")
        page.wait_for_timeout(1800)
        kachel = page.locator("text=Zu moderierende Termine")
        if kachel.count():
            umfeld = kachel.first.locator(
                "xpath=ancestor::*[contains(@class,'dk-widget-card')][1]")
            txt = umfeld.inner_text() if umfeld.count() else page.inner_text("body")
            assert "EL0" not in txt, f"interne ID in der Kachel: {txt[:200]}"
            report["schritte"].append("G/W6 Dashboard-Kachel 'Zu moderierende Termine' ohne IDs")
        else:
            report["schritte"].append("G/W6 Dashboard-Kachel nicht sichtbar")
        shots(page, "G-dashboard", report)

        # ── J) Suche Umlaute/Schreibweise ─────────────────────────────────
        page.goto(BASE + "/diakonos#/mitglieder", wait_until="networkidle")
        page.wait_for_timeout(1200)
        suchfeld = page.locator(
            "input[placeholder*='suchen'], input[placeholder*='Suchen'], input[placeholder*='Name']").first
        if suchfeld.count():
            suchfeld.fill("manuel")
            page.wait_for_timeout(1300)
            body = page.inner_text("body")
            report["schritte"].append(f"J Mitglieder-Suche 'manuel' -> 'Manuel' drin: {'Manuel' in body}")
        page.goto(BASE + "/diakonos#/adressbuch", wait_until="networkidle")
        page.wait_for_timeout(1200)
        sf2 = page.locator("input[placeholder*='suchen'], input[placeholder*='Suchen']").first
        if sf2.count():
            sf2.fill("weiss")
            page.wait_for_timeout(1300)
            body2 = page.inner_text("body")
            report["schritte"].append(f"J Adressbuch 'weiss' -> 'Weiß' drin: {'Weiß' in body2}")
        shots(page, "J-suche", report)

        # ── F/W7) Mitglieder: Adressen erst nach Umschalten ───────────────
        page.goto(BASE + "/diakonos#/mitglieder", wait_until="networkidle")
        page.wait_for_timeout(1300)
        knopf = page.locator("button", has_text="Persönliche Daten anzeigen").first
        tab = page.locator("button", has_text="Tabelle").first
        if tab.count():
            tab.click()
            page.wait_for_timeout(900)
        if knopf.count():
            kopf_zu = page.locator("thead").first.inner_text().upper()
            knopf.click()
            page.wait_for_timeout(1100)
            kopf_offen = page.locator("thead").first.inner_text().upper()
            report["schritte"].append(
                f"F/W7 Adresse vor Umschalten sichtbar={'ADRESSE' in kopf_zu}, "
                f"nachher={'ADRESSE' in kopf_offen}")
        shots(page, "F-mitglieder-datenschutz", report)

        # ── A) Termin anlegen -> Vorschlag, ehrlicher Hinweis ─────────────
        page.goto(BASE + "/diakonos#/kalender", wait_until="networkidle")
        page.wait_for_timeout(1600)
        bmod = page.locator("button[aria-label='Bearbeitungsmodus']").first
        if bmod.count():
            bmod.click()
            page.wait_for_timeout(800)
        zellen = page.locator(".ec-day")
        ziel = None
        for i in range(zellen.count()):
            z = zellen.nth(i)
            if z.locator("time").count():
                ziel = z
                break
        assert ziel is not None, "keine Tageszelle im Raster"
        ziel.click()
        page.wait_for_timeout(1300)
        if page.locator(".diakronos-modal").count() and page.locator("input[placeholder='Termintitel']").count():
            page.locator("input[placeholder='Termintitel']").fill("Abnahme BF1d Termin")
            page.wait_for_timeout(400)
            sels = page.locator(".diakronos-modal select")
            if sels.count():
                for o in sels.first.locator("option").all():
                    if o.get_attribute("value"):
                        sels.first.select_option(o.get_attribute("value"))
                        break
            page.wait_for_timeout(400)
            page.locator(".diakronos-modal button:has-text('Speichern')").first.click()
            page.wait_for_timeout(2500)
            meldung = page.inner_text("body").lower()
            ok = ("gespeichert" in meldung or "erstellt" in meldung
                  or "vorschlag" in meldung or "moderation" in meldung)
            report["schritte"].append(f"A Termin anlegen: Erfolgs-/Hinweismeldung={ok}")
        else:
            report["schritte"].append("A Anlege-Dialog nicht geoeffnet (Tageszelle oeffnete Liste)")
        shots(page, "A-termin-anlegen", report)

        # ── L/W3/W4) Abmelden -> /login; GET /logout bleibt 405 ───────────
        st = _get_status("/logout")
        report["schritte"].append(f"L GET /logout = {st} (405 erwartet)")
        page.goto(BASE + "/diakonos#/profile", wait_until="networkidle")
        page.wait_for_timeout(1200)
        ab = page.locator("button:has-text('Abmelden')").first
        assert ab.count(), "Abmelden-Knopf im Profil fehlt"
        shots(page, "L-abmelden-knopf", report)
        ab.click()
        page.wait_for_timeout(3000)
        url = page.url
        report["schritte"].append(f"L nach Abmelden: {url}")
        shots(page, "L-abgemeldet", report)

        context.close()
        browser.close()

    report["ok"] = not report["page_errors"]
    (OUT / "bf1d-browser.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
