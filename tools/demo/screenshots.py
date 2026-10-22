"""Screenshots der Demo-Gemeinde „Musterhausen“ mit Playwright.

Laeuft im Playwright-Image (mcr.microsoft.com/playwright/python:v1.49.0-noble)
gegen einen Wegwerf-Stack mit den Demo-Daten (`musterhausen.py`). Die Bilder
landen in `docs/bilder/v2/`.

Aufruf (aus dem Projektverzeichnis; der Demo-Stack laeuft unter einem
eigenen Compose-Projekt, hier ``demo`` — der Name geht per ``DEMO_PROJEKT``
in Netznamen und Host des App-Containers ein):

    docker run --rm --network demo_default -v "$PWD":/w \
        -e BASE=http://app:8000 -e ZIEL=/w/docs/bilder/v2 \
        -e ADMIN_PASS=musterhausen-demo -e MITGLIED_PASS=musterhausen-demo \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/screenshots.py

Desktop 1366x800, Mobil 390x844, Dunkelmodus nur fuer die Uebersicht. Der
Lauf endet mit Rueckgabewert 1 und einer Liste, sobald eine Seite einen
Konsolenfehler wirft — so faellt ein stiller Regress beim Nachziehen auf.

ACHTUNG: Die Bilder gehen in ein OEFFENTLICHES Repository. Auf jeder Seite
darf kein echter Name, keine interne Adresse und kein Platzhalter wie
`undefined` stehen — nach dem Lauf pruefen.
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
# Compose-Projektname des Demo-Stacks — nur fuer Netznamen in Meldungen; der
# Zugriff laeuft ueber ``BASE`` (Default: der App-Dienst im eigenen Netz).
PROJEKT = os.environ.get("DEMO_PROJEKT", "demo")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ["ADMIN_PASS"]
ZIEL = os.environ.get("ZIEL", "/ausgabe")

PLAN_ABLAUF = ""   # wird beim Start per API ermittelt
PLAN_CHOR = ""

fehler: list[str] = []

def seiten(prefix: str) -> list[tuple[str, str | None, str | None]]:
    return [
        ("01-anmeldung", None, None),
        ("02-uebersicht", "#/", None),
        # Die Demo-Termine beginnen am 02.11.2026 — der Kalender startet auf dem
        # heutigen Monat, deshalb vor dem Schuss einmal „weiter“ blaettern.
        ("03-kalender-monat", "#/kalender", "monat_weiter"),
        ("04-kalender-woche", "#/kalender", "woche"),
        ("05-mitglieder-liste", "#/mitglieder/liste", None),
        ("06-mitglied-detail", "#/mitglied/Anna Beispiel", None),
        ("07-gruppen", "#/gruppen", None),
        ("08-organigramm", "#/gruppen/organigramm", None),
        ("09-dienstplan", "#/dienstplan", None),
        ("09c-meine-dienste", "#/planrahmen/meine-dienste", None),
        ("10-planrahmen-uebersicht", "#/planrahmen", None),
        # B4: geoeffneter, BESETZTER Plan (Tabellenansicht) und der
        # Gottesdienst-Ablauf mit Liedern — die beiden veroeffentlichten Plaene.
        ("11-plan-gottesdienst-ablauf", "#/planrahmen/plan/" + PLAN_ABLAUF, "plan_tabelle"),
        ("12-plan-chorplan-besetzt", "#/planrahmen/plan/" + PLAN_CHOR, "plan_tabelle"),
        # B5: Beitraege und Wiki mit erfundenen Eintraegen.
        ("13-beitraege", "#/beitraege", None),
        ("14-wiki", "#/wiki", None),
        ("15-lieder", "#/lieder", None),
        ("16-ressourcen", "#/ressourcen", None),
        ("17-einstellungen-datensicherung", "#/einstellungen/datensicherung", None),
        ("18-profil", "#/profile", None),
    ] if not prefix else [
        ("01-anmeldung", None, None),
        ("02-uebersicht", "#/", None),
        ("03-kalender-monat", "#/kalender", "monat_weiter"),
        ("05-mitglieder-liste", "#/mitglieder/liste", None),
        ("07-gruppen", "#/gruppen", None),
        ("09-dienstplan", "#/dienstplan", None),
        # B4 mobil: derselbe besetzte Plan wie am Desktop.
        ("11-plan-chorplan-besetzt", "#/planrahmen/plan/" + PLAN_CHOR, "plan_tabelle"),
        ("13-beitraege", "#/beitraege", None),
        ("15-lieder", "#/lieder", None),
    ]


def plan_ids_holen(page) -> None:
    """Die Plan-Kennungen der Demo per API holen (sie sind je Seed neu)."""
    global PLAN_ABLAUF, PLAN_CHOR
    daten = page.evaluate(
        "async () => (await (await fetch('/api/method/diakronos_app.api.planrahmen.plaene_liste'))"
        ".json()).message")
    for plan in daten:
        if plan.get("plantyp_name") == "Gottesdienst-Ablauf":
            PLAN_ABLAUF = plan["id"]
        if plan.get("plantyp_name") == "Chorplan":
            PLAN_CHOR = plan["id"]
    print("Plan-Kennungen:", PLAN_ABLAUF, PLAN_CHOR)


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(
        viewport={"width": breite, "height": hoehe},
        device_scale_factor=1,

        locale="de-DE",
        color_scheme="dark" if dunkel else "light",
    )
    ctx.set_default_timeout(20000)
    return ctx


def anmelden(page, benutzer=None, passwort=None):
    page.goto(BASE + "/", wait_until="domcontentloaded")
    seite = page
    if seite.locator("input[type=password]").count():
        seite.fill("input[type=email], input[name=usr], input[autocomplete=username]",
                   benutzer or BENUTZER)
        seite.fill("input[type=password]", passwort or PASSWORT)
        seite.locator("button[type=submit], button:has-text('Anmelden')").first.click()
        seite.wait_for_load_state("networkidle")


def sammeln(page, name):
    """Sammelt Konsolenfehler — der Dev-Modus-Endpunkt ist ausgenommen.

    Bei abgeschaltetem Dev-Modus antwortet `/api/method/diakronos.devmodus.api.uebersicht`
    mit 404; das ist laut `composables/useDevmodus.js` der Normalfall (die
    Antwort wird im Frontend abgefangen). Der Browser protokolliert die
    fehlgeschlagene Anfrage trotzdem als Konsolenfehler — fuer oeffentliche
    Bilder ist er irrelevant und wird deshalb nicht als Fehler gezaehlt.
    Jeder andere Konsolenfehler bleibt ein Fehler.
    """
    def meldung(msg):
        text = msg.text
        if msg.type != "error":
            return
        if "devmodus.api.uebersicht" in text or (
                "Failed to load resource" in text and "404" in text):
            return
        fehler.append(f"{name}: {text}")
    page.on("console", meldung)
    page.on("pageerror", lambda exc: fehler.append(f"{name}: {exc}"))


def schuss(page, name, pfad, extra=None):
    seite = page
    seite.goto(BASE + "/" + pfad, wait_until="networkidle")
    seite.wait_for_timeout(900)
    if extra == "woche":
        seite.select_option("select", "timeGridWeek")
        seite.wait_for_timeout(900)
    if extra == "monat_weiter":
        _monat_weiter(seite)
    if extra == "plan_tabelle":
        # Der Plan-Koerper steht unterhalb des Kopfbereichs — fuer ein
        # aussagekraeftiges Bild dorthin scrollen.
        _zum_plan_scrollen(seite)
    ziel = os.path.join(ZIEL, name + ".png")
    os.makedirs(ZIEL, exist_ok=True)
    seite.screenshot(path=ziel, full_page=False)
    print("geschrieben", ziel, os.path.getsize(ziel))


def _monat_weiter(page, schritte: int = 1) -> None:
    """Im Kalender so viele Monate vorblaettern, bis ein Termin sichtbar ist."""
    for _ in range(schritte):
        knopf = page.locator("button[aria-label='Nächster Monat']")
        if knopf.count() == 0:
            print("WARNUNG: kein Weiter-Knopf im Kalender gefunden")
            return
        knopf.first.click()
        page.wait_for_timeout(1200)


def _zum_plan_scrollen(page) -> None:
    """Bis zur Plantabelle scrollen (der Kopfbereich fuellt sonst das Bild)."""
    for text in ("Zeichen in diesem Plan erklärt", "Druckansicht (A4 hoch)"):
        knopf = page.get_by_text(text)
        if knopf.count():
            knopf.first.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            break
    page.mouse.wheel(0, 900)
    page.wait_for_timeout(800)


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])

        # Anmeldeseite (ohne Konto)
        ctx = kontext(browser, 1366, 800)
        page = ctx.new_page()
        sammeln(page, "01-anmeldung")
        page.goto(BASE + "/", wait_until="networkidle")
        page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(ZIEL, "01-anmeldung.png"))
        print("geschrieben 01-anmeldung.png")
        ctx.close()

        for breite, hoehe, praefix in ((1366, 800, ""), (390, 844, "mobil-")):
            ctx = kontext(browser, breite, hoehe)
            page = ctx.new_page()
            anmelden(page)
            if not praefix:
                plan_ids_holen(page)
            for name, route, extra in seiten(praefix):
                if route is None:
                    continue
                sammeln(page, praefix + name)
                schuss(page, praefix + name, route, extra)
            ctx.close()

        # Dienstplan aus Sicht des MITGLIEDER-Kontos: die Seite zeigt „Deine
        # nächsten Vorbereitungen und Einsätze“ — für ein Konto ohne eigene
        # Einteilung ist sie zwangsläufig leer. „Anna Beispiel“ ist in der Demo
        # eingeteilt und zeigt deshalb den echten Stand.
        ctx = kontext(browser, 1366, 800)
        page = ctx.new_page()
        anmelden(page, os.environ.get("MITGLIED_EMAIL", "anna.beispiel@example.org"),
                 os.environ.get("MITGLIED_PASS", PASSWORT))
        sammeln(page, "09b-dienstplan-mitglied")
        schuss(page, "09b-dienstplan-mitglied", "#/dienstplan")
        ctx.close()

        # Dunkle Uebersicht (nur Desktop)
        ctx = kontext(browser, 1366, 800, dunkel=True)
        page = ctx.new_page()
        anmelden(page)
        sammeln(page, "02-uebersicht-dunkel")
        schuss(page, "02-uebersicht-dunkel", "#/")
        ctx.close()
        browser.close()

    if fehler:
        print("KONSOLENFEHLER (Projekt %s):" % PROJEKT, file=sys.stderr)
        for f in sorted(set(fehler)):
            print(" -", f, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
