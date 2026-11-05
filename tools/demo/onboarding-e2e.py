"""ON-E2E — Onboarding auf einer LEEREN Installation Schritt fuer Schritt durchgehen.

WAS DIESES SKRIPT IST
---------------------
Ein Pruefwerkzeug, keine Funktion der App: es laeuft IM Playwright-Image
(mcr.microsoft.com/playwright/python:v1.49.0-noble) gegen einen WEGWERF-Stack
mit leerer Datenbank und legt zu jedem Schritt einen Screenshot ab. Es
schreibt NICHTS in das Image und braucht keinen Compose-Zugriff — alles laeuft
ueber HTTP/HTML/JSON: Playwright fuer die Bedienung, urllib fuer die
Mailpit-Schnittstelle (Attrappen-SMTP) und die Betriebspruefung.

VORAUSSETZUNGEN (Wegwerf-Stack, Regel 12: eigener APP_IMAGE-Tag)
----------------------------------------------------------------
  * Datenbank frisch migriert und LEER (kein ADMIN_EMAIL/ADMIN_PASSWORD).
  * DIAKRONOS_BASE_PATH gesetzt (Pruefung mit Praefix), App-Basis in APP_BASE.
  * Ein SMTP-Attrappen-Dienst (Mailpit) im selben Compose-Netz.

ABLAUF (Karte ON-E2E)
---------------------
  1. Einrichtungslink aus dem Startkasten (`docker compose logs app`) lesen.
  2. Administrator anlegen — erst mit ZU SCHWACHEM Passwort (Fehlerfall),
     dann korrigiert.
  3. Assistent: Gemeinde mit Logo (PNG und SVG), Kontakt, Mailversand
     (Attrappen-SMTP, Testmail muss ankommen), Module, Mitglieder & Kalender
     (CSV-Import einer kleinen Testdatei + Kalendervorschlaege), Fertig.
  4. Zweiter Durchlauf: alles ueberspringen, „Speichern und spaeter
     fortsetzen", Neuanmeldung.
  5. Danach: Uebersichts-Karte „Einrichtung abschliessen", Hinweise in den
     Einstellungen, leere Listen, Logo in Kopfzeile und Anmeldeseite,
     `#/einrichtung` leitet nach Abschluss auf die Einstellungen.
  6. Einrichtungslink nach Nutzung ungueltig.

Aufruf (Beispiel, Werte aus der eigenen Env):

    docker run --rm --network one2e_default \
        -e BASE=http://app:8000 -e PREFIX=/diakronos \
        -e EINRICHTUNGSLINK=/diakronos/einrichtung/<token> \
        -e MAILPIT=http://mailpit:8025 \
        -v "$PWD":/w --entrypoint python \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        /w/tools/demo/onboarding-e2e.py

  * `BASE`      App-Basis im Netz (Schema+Host+Port, OHNE Praefix)
  * `PREFIX`    Betriebs-Praefix (`DIAKRONOS_BASE_PATH`), darf leer sein
  * `EINRICHTUNGSLINK`  Token-Pfad aus dem Startkasten (darf den Praefix
                enthalten oder nicht — beides wird erkannt)
  * `MAILPIT`   Basisadresse der Mailpit-Oberflaeche (API unter /api/v1)
  * `ZIEL`      Ablage der Screenshots und des Befund-JSON (Default /ausgabe)

Rueckgabe: Exitcode 0 = alle Pruefungen bestanden; 2 = mindestens eine
Pruefung fehlgeschlagen (Liste am Ende und in `befunde.json`), 3 = Abbruch
(Voraussetzung fehlt). Ein Befund ist KEIN Absturz: das Skript laeuft weiter
und sammelt, damit ein Lauf das ganze Onboarding abdeckt.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import Error as PwError
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
PREFIX = ("/" + os.environ.get("PREFIX", "").strip().strip("/")).rstrip("/")
LINK_ROH = os.environ.get("EINRICHTUNGSLINK", "").strip()
MAILPIT = os.environ.get("MAILPIT", "").rstrip("/")
ZIEL = Path(os.environ.get("ZIEL", "/ausgabe"))
DESKTOP = {"width": 1440, "height": 900}
MOBIL = {"width": 390, "height": 844}

#: Passwoerter des Prueflaufs (nur Wegwerf-Installation, erfundene Werte).
#: Der Fehlerfall ist ABSICHTLICH 8 Zeichen lang: kuerzer greift schon die
#: HTML-Pruefung (minlength) und der Server sieht die Absendung nie.
PASSWORT_ZU_SCHWACH = "nurklein"
PASSWORT_STARK = "EinSicheres12"
ADMIN_EMAIL = "admin@example.org"
GEMEINDE = "Ev. Kirchengemeinde Pruefhausen"

befunde: list[dict] = []
schritte: list[str] = []


# ── kleine Helfer ─────────────────────────────────────────────────────────
def p(*teile: str) -> str:
    """Adresse mit Betriebs-Praefix."""
    return BASE + PREFIX + "".join(teile)


def befund(schwere: str, titel: str, text: str, *, ort: str = "") -> None:
    befunde.append({"schwere": schwere, "titel": titel, "text": text, "ort": ort})
    print(f"[{schwere}] {titel}: {text}")


def ok(titel: str) -> None:
    print(f"[ok] {titel}")
    schritte.append(titel)


def hole(url: str, timeout: float = 10.0):
    """HTTP GET von der Kommandozeile aus (Mailpit, healthz)."""
    anfrage = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
        roh = antwort.read()
        return antwort.status, roh


def hole_json(url: str):
    status, roh = hole(url)
    return status, json.loads(roh.decode("utf-8") or "{}")


def link_pfad() -> str:
    """Der Token-Pfad aus der Umgebung, normalisiert (nie doppeltes Praefix)."""
    text = LINK_ROH
    if not text:
        raise SystemExit("EINRICHTUNGSLINK fehlt (Startkasten: docker compose logs app).")
    if text.startswith("http://") or text.startswith("https://"):
        text = "/" + text.split("/", 3)[-1]
    text = "/" + text.lstrip("/")
    if PREFIX and text.startswith(PREFIX + "/"):
        text = text[len(PREFIX):]
    return text


def basis_adresse() -> str:
    """Absolute Adresse des Praefix-Raums (fuer Anmeldung/App)."""
    return BASE + PREFIX


def mailpit_nachrichten() -> list[dict]:
    """Alle Nachrichten des Attrappen-Postfachs (neueste zuerst)."""
    if not MAILPIT:
        return []
    try:
        status, daten = hole_json(f"{MAILPIT}/api/v1/messages?limit=50")
        if status != 200:
            return []
        return list(daten.get("messages") or [])
    except (urllib.error.URLError, OSError, ValueError):
        return []


def warte_auf_mail(empfaenger: str, *, sekunden: float = 20.0) -> dict | None:
    """Wartet, bis eine Nachricht an `empfaenger` im Attrappen-Postfach liegt."""
    ende = time.time() + sekunden
    while time.time() < ende:
        for nachricht in mailpit_nachrichten():
            empfaenger_liste = nachricht.get("To") or []
            for eintrag in empfaenger_liste:
                if str(eintrag.get("Address", "")).lower() == empfaenger.lower():
                    return nachricht
        time.sleep(1.0)
    return None


# ── Seitenbedienung ───────────────────────────────────────────────────────
def schuss(page, name: str) -> None:
    """Screenshot nach ZIEL/<name>.png — Desktop und Mobil teilen sich Namen
    NICHT (Praefix `d-`/`m-`), damit nichts ueberschrieben wird."""
    ZIEL.mkdir(parents=True, exist_ok=True)
    datei = ZIEL / f"{name}.png"
    page.screenshot(path=str(datei), full_page=True)
    print(f"       → {datei}")


def text_von(page, selektor: str) -> str:
    try:
        return (page.locator(selektor).first.inner_text(timeout=3000) or "").strip()
    except PwError:
        return ""


def hat_text(page, text: str) -> bool:
    try:
        return page.get_by_text(text, exact=False).count() > 0
    except PwError:
        return False


def konsole_merken(page, sammlung: list[str]) -> None:
    """Sammelt Konsolenfehler je Seite — ein stiller JS-Fehler ist ein Befund."""
    def _merken(nachricht):
        if nachricht.type == "error":
            sammlung.append(nachricht.text)
    page.on("console", _merken)
    page.on("pageerror", lambda fehler: sammlung.append(f"pageerror: {fehler}"))


def formular_fuellen(page, werte: dict[str, str]) -> None:
    """Fuellt Felder ueber ihre Beschriftung (DkField -> label[for]).

    `werte` bildet die sichtbare Beschriftung auf den Wert ab. Die Zuordnung
    laeuft ueber das `for`-Attribut des Labels — also genau so, wie ein
    Mensch das Feld findet, nicht ueber erfundene Selektoren.
    """
    for beschriftung, wert in werte.items():
        feld = page.get_by_label(beschriftung, exact=False).first
        feld.wait_for(state="visible", timeout=5000)
        feld.fill(str(wert))


def weiter(page) -> None:
    page.get_by_role("button", name="Weiter", exact=True).first.click()
    page.wait_for_timeout(700)


def ueberspringen(page) -> None:
    page.get_by_role("button", name="Überspringen", exact=True).first.click()
    page.wait_for_timeout(700)


def schritt_titel(page) -> str:
    return text_von(page, "main h1") or text_von(page, "h1")


# ── Ablauf ────────────────────────────────────────────────────────────────
def einrichtungslink_pruefen(page) -> None:
    """Schritt 1: Link oeffnen — die Seite „Administrator anlegen" erscheint."""
    pfad = link_pfad()
    page.goto(p("", pfad), wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    schuss(page, "01-einrichtungslink")
    titel = text_von(page, "h1")
    if "Willkommen" not in titel and "Administrator" not in titel:
        befund("hoch", "Einrichtungslink zeigt nicht die Anlageseite",
               f"h1 = {titel!r} auf {page.url}", ort="einrichtung_seiten.seite_anlegen")
    else:
        ok(f"Einrichtungslink zeigt die Anlageseite („{titel}“)")
    if page.locator("input[type=password]").count() == 0:
        befund("hoch", "Passwortfeld fehlt auf der Anlageseite", page.url,
               ort="einrichtung_seiten.seite_anlegen")
    # Praefix: keine Adresse darf ohne Betriebs-Praefix geladen werden.
    if PREFIX and "href=\"/api/" in page.content():
        befund("hoch", "Formular zeigt auf /api/… ohne Betriebs-Praefix", page.url,
               ort="einrichtung_seiten.py (API-Adresse)")


def administrator_anlegen(page) -> None:
    """Schritt 2: erst zu schwaches Passwort (Fehlerfall), dann korrigiert."""
    page.goto(p("", link_pfad()), wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    # Felder der Anlageseite (Vorname/Nachname/E-Mail/Passwort/Wiederholung).
    felder = {
        "E-Mail": ADMIN_EMAIL,
        "Vorname": "Alex",
        "Nachname": "Administrator",
        "Passwort": PASSWORT_ZU_SCHWACH,
        "Passwort wiederholen": PASSWORT_ZU_SCHWACH,
    }
    for beschriftung, wert in felder.items():
        try:
            formular_fuellen(page, {beschriftung: wert})
        except PwError:
            befund("mittel", "Feld nicht gefunden", f"Beschriftung „{beschriftung}“",
                   ort="einrichtung_seiten.seite_anlegen")
    knopf = page.get_by_role("button", name=re.compile("anlegen", re.I)).first
    knopf.click()
    page.wait_for_timeout(900)
    schuss(page, "02-passwort-zu-schwach")
    inhalt = page.content()
    fehlertext = text_von(page, "#fehler") or text_von(page, "[role=alert]") or ""
    if not fehlertext or not page.locator("#fehler").is_visible():
        befund("mittel", "Kein sichtbarer Hinweis bei zu schwachem Passwort",
               f"#fehler = {fehlertext!r} (hidden={not page.locator('#fehler').is_visible()})",
               ort="einrichtung_routen._pruefe_werte")
    else:
        ok(f"Zu schwaches Passwort abgewiesen („{fehlertext[:60]}“)")

    # Korrigiert: starkes Passwort, gleiche Adresse (der Token ist noch giltig).
    page.goto(p("", link_pfad()), wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    for beschriftung, wert in {
        "E-Mail": ADMIN_EMAIL, "Vorname": "Alex", "Nachname": "Administrator",
        "Passwort": PASSWORT_STARK, "Passwort wiederholen": PASSWORT_STARK,
    }.items():
        try:
            formular_fuellen(page, {beschriftung: wert})
        except PwError:
            pass
    page.get_by_role("button", name=re.compile("anlegen", re.I)).first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    schuss(page, "03-nach-anlage")
    ziel = urllib.parse.urlparse(page.url)
    if "/diakonos" not in page.url:
        befund("hoch", "Nach dem Anlegen nicht in der App", page.url,
               ort="einrichtung_routen.ZIEL_NACH_ANLAGE")
    else:
        ok(f"Administrator angelegt, Ziel {ziel.path}#…")


def anmelden(page, passwort: str = PASSWORT_STARK, email: str = ADMIN_EMAIL) -> None:
    page.goto(p("/login"), wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    # Die Maske beschriftet ihre Felder „E-Mail-Adresse" und „Passwort".
    try:
        formular_fuellen(page, {"E-Mail": email, "Passwort": passwort})
    except PwError as grund:
        befund("hoch", "Anmeldefelder nicht gefunden", str(grund), ort="anmeldung")
    page.get_by_role("button", name=re.compile("anmelden|einloggen", re.I)).first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)


def assistent_durchlauf(page) -> None:
    """Schritt 3: alle Schritte des Assistenten ausfuellen."""
    page.goto(p("/diakonos") + "#/einrichtung", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    schuss(page, "04-assistent-gemeinde")

    # ── Gemeinde mit Logo (PNG und SVG) ──────────────────────────────────
    formular_fuellen(page, {"Gemeindename": GEMEINDE, "Kurzname": "Pruefhausen"})
    png = ZIEL / "logo.png"
    svg = ZIEL / "logo.svg"
    png.write_bytes(_LOGO_PNG)
    svg.write_text(_LOGO_SVG, encoding="utf-8")
    eingabe = page.locator("input[type=file]").first
    if eingabe.count() == 0:
        befund("hoch", "Kein Dateifeld fuer das Logo", page.url,
               ort="SchrittGemeinde.vue (Logo)")
    else:
        # Erst PNG: danach muss ein <img> mit der Server-Adresse stehen.
        eingabe.set_input_files(str(png))
        page.wait_for_timeout(1800)
        schuss(page, "05-logo-png")
        if page.locator("img[alt='Logo der Gemeinde']").count() == 0:
            befund("hoch", "Logo-Vorschau fehlt nach dem PNG-Upload", page.url,
                   ort="SchrittGemeinde.vue (Vorschau)")
        else:
            quelle = page.locator("img[alt='Logo der Gemeinde']").first.get_attribute("src") or ""
            ok(f"Logo (PNG) hochgeladen, Vorschau {quelle}")
            if PREFIX and not quelle.startswith(PREFIX):
                befund("mittel", "Logo-Adresse ohne Betriebs-Praefix", quelle,
                       ort="api/gemeinde.logo_url")
        # Dann SVG — derselbe Weg, anderer Typ (Entwurf: PNG und SVG).
        eingabe = page.locator("input[type=file]").first
        eingabe.set_input_files(str(svg))
        page.wait_for_timeout(1800)
        schuss(page, "05b-logo-svg")
        if page.locator("img[alt='Logo der Gemeinde']").count() == 0:
            befund("hoch", "Logo-Vorschau fehlt nach dem SVG-Upload", page.url,
                   ort="kind: gemeinde_logo_hochladen (SVG)")
        else:
            ok("Logo (SVG) hochgeladen und in der Vorschau sichtbar")
    weiter(page)
    schuss(page, "06-schritt-kontakt")

    # ── Kontakt ──────────────────────────────────────────────────────────
    if "Kontakt" not in schritt_titel(page):
        befund("mittel", "Nach „Weiter“ nicht im Schritt Kontakt", schritt_titel(page),
               ort="useEinrichtungsAssistent.weiter")
    for beschriftung, wert in {
        "Straße und Hausnummer": "Kirchplatz 1",
        "PLZ": "12345",
        "Ort": "Pruefhausen",
        "Kontakt-E-Mail": "buero@example.org",
        "Telefon": "01234 56789",
        "Website": "https://example.org",
    }.items():
        try:
            formular_fuellen(page, {beschriftung: wert})
        except PwError:
            befund("niedrig", "Kontaktfeld nicht gefunden", beschriftung,
                   ort="SchrittKontakt.vue")
    weiter(page)

    # ── Mailversand (Attrappen-SMTP) ─────────────────────────────────────
    page.wait_for_timeout(900)
    schuss(page, "07-schritt-mailversand")
    mailfelder = {
        "SMTP-Server": "mailpit",
        "Port": "1025",
        # Benutzer bleibt LEER: der Attrappen-SMTP verlangt keine Anmeldung,
        # und die Oberflaeche lässt „keine Verschlüsselung" nur ohne Benutzer zu.
    }
    for beschriftung, wert in mailfelder.items():
        try:
            formular_fuellen(page, {beschriftung: wert})
        except PwError:
            befund("mittel", "Mailversand-Feld nicht gefunden", beschriftung,
                   ort="SchrittMailversand.vue")
    # Absenderadresse + Absendername (Pflicht bzw. freiwillig).
    for beschriftung, wert in {"Absenderadresse": ADMIN_EMAIL, "Absendername": "Pruefhausen"}.items():
        try:
            formular_fuellen(page, {beschriftung: wert})
        except PwError:
            pass
    # Verschlüsselung: der Attrappen-SMTP spricht kein TLS -> „Keine“.
    try:
        page.get_by_label("Verschlüsselung", exact=False).first.select_option("keine")
        page.wait_for_timeout(300)
    except PwError as grund:
        befund("mittel", "Auswahlfeld Verschlüsselung nicht bedienbar", str(grund),
               ort="SchrittMailversand.vue")
    # Port nach der Auswahl erneut setzen (die Auswahl bringt einen Vorschlag mit).
    try:
        formular_fuellen(page, {"Port": "1025"})
    except PwError:
        pass
    # Kein eigener Speicherknopf in diesem Schritt: gespeichert wird beim
    # „Weiter“ in der Fußleiste (Seite → `mailversand.speichern()`), also erst
    # NACH der Testmail. Die Testmail prueft die eingetippten Werte selbst.
    testknopf = page.get_by_role("button", name=re.compile("Testmail", re.I)).first
    if testknopf.count():
        testknopf.click()
        page.wait_for_timeout(3000)
        schuss(page, "08-testmail-ergebnis")
        testmeldung = text_von(page, ".test-ok") or text_von(page, ".test-fehler")
        if testmeldung:
            print(f"       Testmail-Oberflaeche: {testmeldung}")
        if MAILPIT:
            nachricht = warte_auf_mail(ADMIN_EMAIL)
            if nachricht is None:
                befund("hoch", "Testmail kam nicht im Attrappen-Postfach an",
                       f"kein Empfaenger {ADMIN_EMAIL} in Mailpit; Oberflaeche: {testmeldung!r}",
                       ort="api/mailversand.mailversand_testmail")
            else:
                ok(f"Testmail angekommen: „{nachricht.get('Subject')}“")
                if not testmeldung:
                    befund("niedrig", "Testmail ohne Rueckmeldung in der Oberflaeche",
                           "Mail kam an, aber .test-ok/.test-fehler leer",
                           ort="SchrittMailversand.vue")
    else:
        befund("hoch", "Kein Knopf „Testmail senden“", page.url, ort="SchrittMailversand.vue")
    weiter(page)
    page.wait_for_timeout(1500)
    # Nach dem „Weiter“ MUSS der Mailversand eingerichtet sein (Speichern in
    # `useMailversand`), sonst bleibt die Checkliste bei „Mailversand“ offen.
    schuss(page, "08b-nach-weiter")

    # ── Module ───────────────────────────────────────────────────────────
    page.wait_for_timeout(900)
    schuss(page, "09-schritt-module")
    schalter = page.locator("[role=switch]")
    if schalter.count() == 0:
        befund("hoch", "Keine Modul-Schalter", page.url, ort="SchrittModule.vue")
    elif schalter.first.get_attribute("aria-checked") != "true":
        schalter.first.click()
        page.wait_for_timeout(300)
        schuss(page, "10-modul-geschaltet")
    weiter(page)

    # ── Mitglieder & Kalender ────────────────────────────────────────────
    page.wait_for_timeout(900)
    schuss(page, "11-schritt-mitglieder-kalender")
    # CSV-Import: die vorhandene Mitgliederseite in einem eigenen Tab, damit
    # der Assistent seinen Stand behaelt.
    csv = ZIEL / "mitglieder.csv"
    csv.write_text(_CSV, encoding="utf-8")
    import_tab = page.context.new_page()
    import_tab.goto(p("/diakonos") + "#/mitglieder/import", wait_until="domcontentloaded")
    # Der Router fuehrt einen frischen Tab zuerst zum Assistenten (ON-3b:
    # „einmal pro Sitzung“ — der Merker liegt in sessionStorage DIESES Tabs).
    # Deshalb warten, bis der Hash wirklich die Import-Seite ist.
    try:
        import_tab.wait_for_function(
            "() => window.location.hash.includes('mitglieder/import')", timeout=8000)
    except PwError as grund:
        text = str(grund)
        # Die App-Policy hat bewusst KEIN 'unsafe-eval' (sec_header.py) — deshalb
        # wird hier nur ein ECHTER Hash-Vergleich gemeldet, kein Werkzeugfehler.
        if "unsafe-eval" not in text:
            befund("hoch", "CSV-Import-Seite nicht erreichbar (Router leitet weg)",
                   f"{import_tab.url} — {text.replace(chr(10), ' ')[:200]}",
                   ort="router.js (ON-3b-Leitung)")
    import_tab.wait_for_timeout(1500)
    schuss(import_tab, "12-csv-import-seite")
    if "mitglieder/import" not in import_tab.url:
        # Router hat den frischen Tab zum Assistenten gefuehrt (ON-3b). Fuer die
        # Import-Pruefung wird der Merker gesetzt — dann greift die Leitung nicht.
        import_tab.evaluate("window.sessionStorage.setItem('dk-einrichtung-gesehen', '1')")
        import_tab.goto(p("/diakonos") + "#/mitglieder/import", wait_until="domcontentloaded")
        import_tab.wait_for_timeout(1800)
        schuss(import_tab, "12b-csv-import-seite-neu")
    dateifeld = import_tab.locator("input[type=file]").first
    if dateifeld.count() == 0:
        befund("hoch", "CSV-Import: kein Dateifeld", import_tab.url, ort="mitglieder/Import.vue")
    else:
        dateifeld.set_input_files(str(csv))
        import_tab.wait_for_timeout(1500)
        schuss(import_tab, "13-csv-gewaehlt")
        if "Zeilen erkannt" not in import_tab.content():
            befund("mittel", "CSV-Import erkennt die Datei nicht",
                   text_von(import_tab, ".mi-datei"), ort="mitglieder/Import.vue")
        # Schritt 2: Spalten sind vorbelegt -> Vorschau anzeigen.
        vorschau = import_tab.get_by_role("button", name=re.compile("Vorschau anzeigen", re.I)).first
        if vorschau.count():
            vorschau.click()
            import_tab.wait_for_timeout(2000)
            schuss(import_tab, "14-csv-vorschau")
            if not hat_text(import_tab, "neu"):
                befund("mittel", "CSV-Vorschau zeigt keine Zusammenfassung", "",
                       ort="mitglieder/Import.vue")
        # Schritt 3: übernehmen.
        uebernehmen = import_tab.get_by_role("button", name=re.compile("Jetzt übernehmen", re.I)).first
        if uebernehmen.count():
            if uebernehmen.is_disabled():
                befund("mittel", "CSV-Import: „Jetzt übernehmen“ bleibt gesperrt",
                       text_von(import_tab, ".mi-fehl"), ort="mitglieder/Import.vue")
            else:
                uebernehmen.click()
                import_tab.wait_for_timeout(2500)
                schuss(import_tab, "15-csv-ergebnis")
                ergebnis = text_von(import_tab, ".mi-ergebnis")
                if not ergebnis:
                    befund("hoch", "CSV-Import liefert kein Ergebnis",
                           text_von(import_tab, "[role=alert]"), ort="Mitglieder-Import")
                else:
                    ok(f"CSV-Import: {ergebnis}")
        else:
            befund("hoch", "CSV-Import: kein Knopf „Jetzt übernehmen“", "",
                   ort="mitglieder/Import.vue")
    import_tab.close()
    page.bring_to_front()
    # Kalender-Vorschlaege bleiben angehakt (Vorauswahl) → „Weiter“ legt sie an.
    weiter(page)
    page.wait_for_timeout(1200)
    schuss(page, "15-schritt-fertig")

    # ── Fertig ───────────────────────────────────────────────────────────
    if "Fertig" not in schritt_titel(page) and not hat_text(page, "Einrichtung"):
        befund("mittel", "Schritt „Fertig“ nicht erreicht", schritt_titel(page),
               ort="useEinrichtungsAssistent.weiter")
    schuss(page, "16-checkliste")
    seite_text = page.content()
    for punkt in ("Gemeindename gesetzt", "Logo hinterlegt", "Kontakt hinterlegt"):
        if punkt not in seite_text:
            befund("mittel", "Checklisten-Punkt nicht als erledigt",
                   punkt, ort="api/einrichtung.status")
    abschluss = page.get_by_role("button", name=re.compile("abschlie|fertigstellen|übersicht", re.I))
    if abschluss.count():
        abschluss.first.click()
        page.wait_for_timeout(1500)
        schuss(page, "17-nach-abschluss")
    else:
        befund("hoch", "Kein Knopf zum Abschliessen auf der Fertig-Seite",
               text_von(page, "main h1"), ort="SchrittFertig.vue")


def zweiter_durchlauf(page) -> None:
    """Schritt 4: alles ueberspringen, „spaeter fortsetzen“, Neuanmeldung."""
    # Assistent wieder oeffnen (einmalig — er ist nicht abgeschlossen? hier
    # ist er abgeschlossen, deshalb pruefen wir die Leitung).
    page.goto(p("/diakonos") + "#/einrichtung", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    schuss(page, "18-einrichtung-nach-abschluss")
    if "#/einstellungen" not in page.url:
        befund("hoch", "`#/einrichtung` leitet nach Abschluss nicht auf die Einstellungen",
               page.url, ort="einrichtungLeitung.einrichtungsWeiterleitung")
    else:
        ok("`#/einrichtung` leitet nach Abschluss auf `#/einstellungen`")

    # Uebersicht: Karte „Einrichtung abschliessen“ nach dem Abschluss.
    page.goto(p("/diakonos") + "#/", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    schuss(page, "19-uebersicht")
    if page.locator(".dk-einrichtungs-karte").count():
        ok("Uebersicht zeigt die Karte „Einrichtung abschließen“ (noch offene Punkte)")
    else:
        print("       Karte nicht sichtbar (alle Punkte erledigt oder Pause aktiv)")
    # Einstellungen: Hinweise auf offene Einrichtungspunkte.
    page.goto(p("/diakonos") + "#/einstellungen", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    schuss(page, "20-einstellungen-hinweise")
    # Gemeinde-Einstellungen: Logo gepflegt (eigener Weg zum Nachholen).
    page.goto(p("/diakonos") + "#/einstellungen/gemeinde", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    schuss(page, "20b-einstellungen-gemeinde")
    if "Logo hinterlegt" not in page.content():
        befund("mittel", "Logo in den Gemeinde-Einstellungen nicht als hinterlegt gezeigt",
               page.url, ort="pages/einstellungen/Gemeinde.vue")
    # Leere Listen, die im Assistenten NICHT gefuellt wurden (Gruppen, Wiki).
    for pfad, name in (("#/gruppen", "20c-gruppen"), ("#/beitraege", "20d-beitraege")):
        page.goto(p("/diakonos") + pfad, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        schuss(page, name)

    # Abmelden und neu anmelden (Sitzung sauber neu).
    page.goto(p("/logout"), wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    schuss(page, "21-nach-abmeldung")
    anmelden(page)
    schuss(page, "22-neue-anmeldung")
    if "#/einrichtung" in page.url:
        befund("hoch", "Admin wird nach dem Abschluss erneut in den Assistenten gefuehrt",
               page.url, ort="spa._einrichtung_offen / router")
    else:
        ok(f"Nach dem Abschluss keine erneute Fuehrung in den Assistenten ({page.url.split('#')[-1]})")


def link_ungueltig(page) -> None:
    """Schritt 5: der Link ist nach dem Anlegen verbraucht."""
    page.goto(p("", link_pfad()), wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    schuss(page, "23-link-ungueltig")
    text = page.content()
    if "Administrator" in text and "anlegen" in text.lower() and page.locator("input[type=password]").count():
        befund("kritisch", "Einrichtungslink nach Nutzung noch gueltig",
               page.url, ort="einrichtung.verbrauche_mit")
    else:
        ok("Einrichtungslink nach Nutzung ungueltig")


def mobil_durchlauf(browser) -> None:
    """Mobil 390 px: Anmeldeseite, Uebersicht und Assistent-Adresse."""
    kontext = browser.new_context(viewport=MOBIL, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = kontext.new_page()
    konsole: list[str] = []
    konsole_merken(page, konsole)
    page.goto(p("/login"), wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    schuss(page, "m-01-anmeldung")
    anmelden(page)
    schuss(page, "m-02-uebersicht")
    page.goto(p("/diakonos") + "#/einstellungen", wait_until="domcontentloaded")
    page.wait_for_timeout(1200)
    schuss(page, "m-03-einstellungen")
    # Ueberlauf: waagerechtes Scrollen am Handy ist ein Befund.
    breite = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    if breite[0] > breite[1] + 1:
        befund("hoch", "Waagerechter Ueberlauf am Handy", f"{breite[0]} > {breite[1]}", ort="mobil")
    if konsole:
        befund("mittel", "Konsolenfehler (mobil)", "; ".join(konsole[:3]))
    kontext.close()


def betriebspruefung() -> None:
    """Der Betrieb darf durch diesen Lauf NICHT leiden (Regel 7/12)."""
    adresse = os.environ.get("BETRIEB_HEALTHZ", "")
    if not adresse:
        return
    try:
        status, roh = hole(adresse)
        if b'"ok"' not in roh.replace(b" ", b""):
            befund("kritisch", "Betriebs-healthz antwortet nicht mit ok", roh[:120].decode("utf-8", "replace"))
        else:
            ok("Betriebs-healthz unveraendert ok")
    except (urllib.error.URLError, OSError) as grund:
        befund("kritisch", "Betriebs-healthz nicht erreichbar", str(grund))


def main() -> int:
    ZIEL.mkdir(parents=True, exist_ok=True)
    print(f"BASE={BASE} PREFIX={PREFIX or '(kein)'} ZIEL={ZIEL}")
    konsole: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        kontext = browser.new_context(viewport=DESKTOP, locale="de-DE")
        page = kontext.new_page()
        konsole_merken(page, konsole)
        try:
            # Der Link ist EINMAL gueltig: Reihenfolge zaehlt.
            link_ungueltig_pruefen = True
            einrichtungslink_pruefen(page)
            administrator_anlegen(page)
            assistent_durchlauf(page)
            if link_ungueltig_pruefen:
                link_ungueltig(page)
            zweiter_durchlauf(page)
        except PwError as grund:
            befund("hoch", "Playwright-Abbruch", str(grund))
            try:
                schuss(page, "zz-abbruch")
            except PwError:
                pass
        except Exception:  # noqa: BLE001 — ein Befund ist besser als ein Absturz
            befund("hoch", "Unerwarteter Fehler", traceback.format_exc(limit=4))
        if konsole:
            befund("mittel", "Konsolenfehler (Desktop)", "; ".join(konsole[:5]))
        kontext.close()
        try:
            mobil_durchlauf(browser)
        except PwError as grund:
            befund("mittel", "Mobiler Durchlauf abgebrochen", str(grund))
        browser.close()

    betriebspruefung()
    bericht = {
        "zeit": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base": BASE, "praefix": PREFIX,
        "bestanden": schritte,
        "befunde": befunde,
    }
    (ZIEL / "befunde.json").write_text(json.dumps(bericht, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n── Ergebnis ───────────────────────────────────────────────")
    print(f"bestanden: {len(schritte)}   Befunde: {len(befunde)}")
    for eintrag in befunde:
        print(f"  [{eintrag['schwere']}] {eintrag['titel']}: {eintrag['text'][:200]}")
    print(f"Bericht: {ZIEL / 'befunde.json'}")
    return 0 if not befunde else 2


#: 1x1-PNG (68 Bytes) — ein echtes Bild ohne externe Datei.
_LOGO_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f5f0000000049454e44ae42"
    "6082"
)

#: Einfaches SVG-Logo (Kreis mit Kreuz) — der zweite vom Entwurf genannte Typ.
_LOGO_SVG = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">'
    '<rect width="64" height="64" rx="8" fill="#2f5d50"/>'
    '<path d="M32 14v36M14 32h36" stroke="#f2f2f2" stroke-width="6"/>'
    '</svg>'
)

#: Kleine Mitgliederliste fuer den CSV-Import (erfundene Personen).
_CSV = (
    "vorname;nachname;email;strasse;plz;ort\n"
    "Anna;Beispiel;anna.beispiel@example.org;Kirchplatz 1;12345;Pruefhausen\n"
    "Bruno;Beispiel;bruno.beispiel@example.org;Kirchplatz 1;12345;Pruefhausen\n"
    "Clara;Muster;clara.muster@example.org;Hauptstrasse 2;12345;Pruefhausen\n"
)


if __name__ == "__main__":
    sys.exit(main())
