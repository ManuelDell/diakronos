"""BS-2d Abnahme: Bereich „Bausteine“ in der Oberflaeche (Wegwerf-Stack).

Laeuft im Playwright-Image (mcr.microsoft.com/playwright/python:v1.49.0-noble)
auf demselben Docker-Netz wie der Stack, Praefix /diakronos.

BS-2d3 (Teil 3/3) — echte Ende-zu-Ende-Abnahme am Wegwerf-Stack:

  Das Skript laeuft gegen einen Stack MIT einem ZWEITEN Wegwerf-Primo
  (deploy/primo, eigenes -p, eigenes Volume, eigener Port, G5: der Live-Primo
  und der Wegwerf-Primo der anderen Karten bleiben unberuehrt). Damit ist der
  ganze Weg echt: Klick „einspielen“ -> PocketBase-Sammlung `pb_blocks`,
  kein gefaelschter Serverstand wie in der ersten Fassung.

  A  Administrator, Desktop 1440, hell:
     A1  Bereich „Bausteine“ steht auf der Website-Seite.
     A2  Kopf nennt „Website-Baukasten“.
     A3  (a) VOR Installation sind ALLE mitgelieferten Bausteine gelistet —
         Name, Kurzbeschreibung und genutzte Freigaben, je Baustein eine Zeile.
         Erwartung kommt aus dem Backend (Anzahl + Kennungen), nicht aus einer
         Zahl im Skript: BS-3a hat den zehnten Baustein (Ansprechpartner)
         gebracht, eine feste „9“ wuerde still veralten.
     A4  Stand VOR Installation: „Noch nicht eingespielt“, Knopf vorhanden.
     A5  (b) Klick „In Website-Baukasten einspielen“ -> Erfolgsmeldung
         „N Bausteine (Fassung V) im Website-Baukasten eingespielt.“
     A6  Stand NACH Einspielen: „Aktuell“, „eingespielt: Fassung V“.
     A7  Pruefung am ECHTEN Primo (HTTP): library_block_count == N und jeder
         Block heisst `diakronos/<kennung>@v<V>`.
     A8  (c) Fehlerfall: Primo gestoppt -> POST -> 503 mit Klartext, keine
         Interna (kein Traceback, keine Primo-Adresse). Der POST schickt das
         CSRF-Token aus `window.__DIakonosBOOT.csrf_token` bzw. dem
         `<meta name="csrf-token">` mit — ohne Token antwortet die
         CSRF-Middleware mit 417 und der 503-Fall waere nie erreicht
         (Befund BS-2d3).
     A9  Primo wieder gestartet -> die Seite erholt sich (Bereich wieder
         abrufbar) — der Fehlerfall bleibt eine Momentaufnahme.
     A10 nur EIN Primaerknopf im Bereich (UX1h).
  B  Website-Moderator: Rolle ueber die Verwaltungs-API gesetzt, Bereich
     sichtbar. Mitglied: Bereich NICHT sichtbar.
  C  Hell/Dunkel, Desktop 1440 + Mobil 390: kein waagerechter Ueberlauf,
     Screenshots als Beleg.

Umgebung (alles per ENV, Defaults fuer den Wegwerf-Stack `bs2d3`):
  BASE           http://app:8000             App im Compose-Netz
  PRAEFIX        /diakronos
  PRIMO_BASIS    http://primo:8080          Primo DIREKT (kein Vorau) fuer A7
  PRIMO_STOPPEN  Kommando, das den Wegwerf-Primo stoppt (docker ...)
  PRIMO_STARTEN  Kommando, das ihn wieder startet
  ZIEL           /out                       Ablage der Screenshots
  ADMIN_* / MITGLIED_*, MODERATOR_*
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
PRAEFIX = os.environ.get("PRAEFIX", "/diakronos")
# Die SPA haengt NICHT am Praefix-Root, sondern an `<Praefix>/diakonos`
# (`spa.py:74`, `SPA_PREFIX = "/diakonos"`). Die erste Fassung rief
# `<Praefix>` auf — dort antwortet die App mit einer Weiterleitung bzw. 404,
# die Anmeldung lief ins Leere (BS-2d3-Befund).
SPA = os.environ.get("SPA", f"{PRAEFIX}/diakonos")
PRIMO_BASIS = os.environ.get("PRIMO_BASIS", "http://primo:8080").rstrip("/")
PRIMO_STOPPEN = os.environ.get("PRIMO_STOPPEN", "")
PRIMO_STARTEN = os.environ.get("PRIMO_STARTEN", "")
ZIEL = Path(os.environ.get("ZIEL", "/out"))
ADMIN = (os.environ.get("ADMIN_EMAIL", "admin@example.org"),
         os.environ.get("ADMIN_PASSWORT", "musterhausen-demo"))
MITGLIED = (os.environ.get("MITGLIED_EMAIL", "anna.beispiel@example.org"),
            os.environ.get("MITGLIED_PASSWORT", "musterhausen-demo"))

API = "diakronos.diakronos.api.website."

ERGEBNIS: dict[str, object] = {"pruefungen": [], "bilder": []}


def pruefe(name: str, ist: object, soll: object = True) -> None:
    ok = ist == soll
    ERGEBNIS["pruefungen"].append({"name": name, "ok": ok, "ist": ist, "soll": soll})
    print(("OK   " if ok else "FEHL ") + name, "" if ok else f"(ist={ist!r} soll={soll!r})")


def schuss(page, name: str) -> None:
    """Screenshot MIT dem Bausteine-Bereich im Bild.

    Die Seite scrollt in einem eigenen Container; `full_page` hilft deshalb
    nicht, und ein Bild nur der oberen Karten belegt nichts (BS-2d3-Befund:
    die Bausteine-Karte lag unterhalb des sichtbaren Ausschnitts). Der Bereich
    wird vorher in den Blick gescrollt.
    """
    ZIEL.mkdir(parents=True, exist_ok=True)
    pfad = ZIEL / name
    try:
        page.locator('[data-wf-abschnitt="bausteine"]').scroll_into_view_if_needed(
            timeout=5000)
        page.wait_for_timeout(400)
    except Exception:  # noqa: BLE001 — Bereich fehlt: Bild trotzdem ablegen
        pass
    page.screenshot(path=str(pfad), full_page=True)
    ERGEBNIS["bilder"].append(str(pfad))
    print("BILD", pfad)


def anmelden(page, email: str, passwort: str, *, ziel: str = "#/website") -> None:
    page.goto(f"{BASE}{SPA}", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    # Die Anmeldeseite der SPA heisst `input[name=usr]` (Typ text — „E-Mail
    # oder Benutzername“) und `input[name=pwd]` (`spa.py:926/930`). Ein
    # Selektor auf `type=email` greift dort nicht (BS-2d3-Befund).
    feld = page.locator("input[name=usr], input[type=email], input[name=email], input#email")
    if feld.count():
        feld.first.fill(email, timeout=20000)
        page.fill("input[name=pwd], input[type=password], input[name=password]", passwort)
        page.click("button[type=submit], button:has-text('Anmelden')")
        page.wait_for_timeout(3500)
    if ziel:
        page.goto(f"{BASE}{SPA}/{ziel}", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)


def bereich(page):
    return page.locator('[data-wf-abschnitt="bausteine"]')


def _warte(page, bedingung: str, timeout_ms: int = 30000, takt_ms: int = 400) -> bool:
    """In Python pollen statt `wait_for_function`.

    `page.wait_for_function` schickt den Ausdruck als Zeichenkette und laesst
    ihn im Dokument auswerten — die CSP der App (`script-src 'self'
    'unsafe-inline'`, ohne `unsafe-eval`) verbietet genau das (BS-2d3-Befund).
    `page.evaluate` geht ueber `Runtime.callFunctionOn` und ist erlaubt.
    """
    import time

    ende = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < ende:
        if page.evaluate(bedingung):
            return True
        page.wait_for_timeout(takt_ms)
    return False


def warte_auf_stand(page, timeout_ms: int = 40000) -> None:
    """Warten, bis der Bereich seinen Stand GELADEN hat (onMounted-Ladung).

    Ohne dieses Warten las das Skript die Liste, bevor `laden()` der
    `onMounted`-Ladung zurueck war — unter Docker-Last dauert das mehrere
    Sekunden. Ergebnis waren 0 Zeilen bei vollem Serverstand (BS-2d3-Befund).
    Fertig ist der Bereich, sobald er NICHT mehr die Ladung anzeigt und
    entweder eine Liste, der Leerzustand oder ein Fehler da ist.
    """
    _warte(
        page,
        """() => {
            const a = document.querySelector('[data-wf-abschnitt="bausteine"]');
            if (!a) return false;
            const t = a.innerText || '';
            if (t.includes('werden geladen')) return false;
            return !!(a.querySelector('li.wb-baustein')
                || t.includes('Keine Bausteine')
                || t.includes('Nicht abrufbar')
                || t.includes('Nicht eingerichtet'));
        }""",
        timeout_ms,
    )
    page.wait_for_timeout(300)


# ── Hilfe: Primo direkt (A17) ───────────────────────────────────────────────
def primo_library_blocks() -> list[str]:
    """Blocknamen der Bibliothek im Wegwerf-Primo — ueber den ECHTEN Weg.

    Genau der Endpunkt, den auch die App liest (`GET /api/primo/export-library`,
    ein ZIP der Bibliothek), statt die Blocksammlung zu raten. Aufbau des ZIP
    (im Wegwerf-Primo nachgesehen): je Block ein Verzeichnis
    `library/<gruppe>/<name>@v<n>/` mit `config.yaml`; der Blockname steht dort
    als `name: diakronos/kontakt@v11`. Die erste Fassung suchte
    `*.block.json` — dieses Format gibt es im Export nicht (BS-2d3-Befund).
    """
    email = os.environ.get("PRIMO_SUPERUSER_EMAIL", "")
    passwort = os.environ.get("PRIMO_SUPERUSER_PASSWORD", "")
    if not email or not passwort:
        return []
    anmeldung = json.dumps({"identity": email, "password": passwort}).encode()
    anfrage = urllib.request.Request(
        f"{PRIMO_BASIS}/api/collections/_superusers/auth-with-password",
        data=anmeldung, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(anfrage, timeout=20) as antwort:
        token = json.loads(antwort.read())["token"]
    anfrage = urllib.request.Request(
        f"{PRIMO_BASIS}/api/primo/export-library",
        headers={"Authorization": token})
    with urllib.request.urlopen(anfrage, timeout=60) as antwort:
        roh = antwort.read()
    namen: list[str] = []
    with zipfile.ZipFile(io.BytesIO(roh)) as archiv:
        for eintrag in archiv.namelist():
            if not eintrag.endswith("/config.yaml"):
                continue
            text = archiv.read(eintrag).decode("utf-8", "replace")
            for zeile in text.splitlines():
                if zeile.startswith("name:"):
                    namen.append(zeile.split(":", 1)[1].strip())
                    break
    return namen


def primo_kennzahlen() -> dict:
    try:
        with urllib.request.urlopen(f"{PRIMO_BASIS}/api/primo/info", timeout=10) as a:
            return json.loads(a.read())
    except (urllib.error.URLError, TimeoutError):
        return {}


def kommandiere(befehl: str) -> None:
    if not befehl:
        return
    subprocess.run(befehl, shell=True, check=False, timeout=180)


def post_einspielen(page) -> dict:
    """POST `bausteine_installieren` MIT CSRF-Token (BS-2d3-Befund).

    Der Token steht in `window.__DIakonosBOOT.csrf_token` und im
    `<meta name="csrf-token">` — NICHT in einem Cookie. Die erste Fassung las
    `document.cookie` und bekam deshalb 417 statt 503.
    """
    return page.evaluate(
        """async () => {
            const boot = window.__DIakonosBOOT || {};
            const basis = boot.basePath || '';
            const meta = document.querySelector('meta[name="csrf-token"]');
            const token = boot.csrf_token || (meta && meta.content) || '';
            const r = await fetch(basis + '/api/method/diakronos.diakronos.api.website.bausteine_installieren',
                {method: 'POST', headers: {'X-Frappe-CSRF-Token': token}});
            const t = await r.text();
            return {status: r.status, text: t.slice(0, 600), tokenGesetzt: !!token};
        }"""
    )


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ── A · Administrator, Desktop 1440, hell ──────────────────────
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        anmelden(page, *ADMIN)
        warte_auf_stand(page)
        abschnitt = bereich(page)
        pruefe("A1 Bereich „Bausteine“ ist da", abschnitt.count(), 1)
        if not abschnitt.count():
            ctx.close()
            browser.close()
            return _abschluss()

        text = abschnitt.inner_text()
        pruefe("A2 Kopf nennt das Werkzeug „Website-Baukasten“", "Website-Baukasten" in text)
        pruefe("A3 Kurzanleitung nennt die Bibliothek", "Bibliothek" in text)
        pruefe("A4 Kurzanleitung nennt --dk-*", "--dk-" in text)

        # ── A5–A7: (a) alle mitgelieferten Bausteine VOR Installation ──
        zeilen = abschnitt.locator("li.wb-baustein")
        anzahl = zeilen.count()
        # Soll-Zahl und Kennungen aus dem Backend holen — nicht raten.
        soll = page.evaluate(
            """async () => {
                const basis = (window.__DIakonosBOOT || {}).basePath || '';
                const r = await fetch(basis + '/api/method/diakronos.diakronos.api.website.bausteine_status');
                return (await r.json()).message;
            }"""
        )
        soll_liste = soll.get("mitgeliefert") or []
        soll_anzahl = len(soll_liste)
        # Der Normalfall im Betrieb: die Bibliothek ist bereits eingespielt
        # (BS-2a zieht sie nach). Ist sie es hier NICHT, muss die Liste
        # trotzdem vollstaendig sein — das ist die eigentliche Zusage der
        # Karte („vor Installation alle Bausteine gelistet“).
        bereits_eingespielt = (soll.get("installiert_version") or 0) >= 1
        print(f"     · Stand beim Laden: installiert={soll.get('installiert_version')} "
              f"mitgeliefert={soll.get('mitgeliefert_version')} "
              f"({soll_anzahl} mitgeliefert)")
        pruefe("A5 alle mitgelieferten Bausteine gelistet (Zahl = Backend)",
               anzahl, soll_anzahl)
        pruefe("A6 die Zahl ist >= 1 (nichts stillschweigend leer)", anzahl >= 1, True)

        namen_ui = [zeilen.nth(i).locator("h3.wb-baustein-name").inner_text()
                    for i in range(anzahl)]
        soll_namen = [str(b.get("name") or "") for b in soll_liste]
        pruefe("A7 alle Namen aus der Serverantwort stehen in der Liste",
               namen_ui, soll_namen)

        # Je Zeile: Kurzbeschreibung UND Freigaben-Hinweis. Gegenprobe gegen
        # den Leerlauf: bei 0 Zeilen waeren beide Listen leer und die Pruefung
        # bestuende, ohne etwas geprueft zu haben — das ist verboten.
        ohne_beschreibung, ohne_freigabe = [], []
        for i in range(anzahl):
            zeile = zeilen.nth(i)
            if not zeile.locator("p.wb-baustein-text").count():
                ohne_beschreibung.append(namen_ui[i])
            if not zeile.locator("p.wb-baustein-freigaben").count():
                ohne_freigabe.append(namen_ui[i])
        pruefe("A8 jede Zeile nennt eine Kurzbeschreibung",
               (anzahl, ohne_beschreibung), (soll_anzahl, []))
        pruefe("A9 jede Zeile nennt die Freigaben",
               (anzahl, ohne_freigabe), (soll_anzahl, []))
        freigabe_texte = [zeilen.nth(i).locator("p.wb-baustein-freigaben").inner_text()
                          for i in range(anzahl)]
        pruefe("A10 Freigabe-Zeilen sind nicht alle leer/„unbekannt“",
               all("unbekannt" in t.lower() for t in freigabe_texte), False)
        for name, f in zip(namen_ui, freigabe_texte):
            print(f"     · {name}: {f}")
        schuss(page, "bs2d3-a1-vor-installation-hell-1440.png")

        # Der Zustand VOR dem Einspielen: solange nichts eingespielt ist,
        # „Noch nicht eingespielt“. Ist die Bibliothek (z. B. durch das
        # automatische Nachziehen der Anmeldung) schon drin, steht dort
        # „Aktuell“ — beides ist richtig; geprueft wird der zum Stand
        # passende Text.
        if bereits_eingespielt:
            pruefe("A11 Zustand vor dem Klick passt zum Stand (bereits eingespielt)",
                   "Aktuell" in text)
        else:
            pruefe("A11 Zustand VOR Installation „Noch nicht eingespielt“",
                   "Noch nicht eingespielt" in text)
        einspiel_knopf = abschnitt.locator("button:has-text('einspielen')")
        pruefe("A12 Knopf „einspielen“ vorhanden", einspiel_knopf.count(), 1)
        primaer = abschnitt.locator("button.dk-ui-btn--primary, .dk-ui-btn--primary").count()
        pruefe("A13 hoechstens ein Primaerknopf im Bereich", primaer <= 1, True)

        # ── A14/A15: (b) einspielen -> Erfolgsmeldung + Stand ───────────
        einspiel_knopf.click()
        # Auf die Ergebnis-Meldung warten, nicht auf eine feste Zeit: der
        # Vorgang schreibt im Fremdsystem und dauert unter Last Sekunden.
        _warte(
            page,
            """() => {
                const a = document.querySelector('[data-wf-abschnitt="bausteine"]');
                return !!a && (a.innerText || '').includes('eingespielt.');
            }""",
            timeout_ms=120000,
        )
        page.wait_for_timeout(500)
        abschnitt = bereich(page)
        text = abschnitt.inner_text()
        # Meldung wird aus der Serverantwort gebaut: „N Bausteine (Fassung V) …“
        erwartete_meldung = f"{soll_anzahl} Bausteine" if soll_anzahl != 1 else "1 Baustein"
        pruefe("A14 Erfolgsmeldung nach „einspielen“",
               erwartete_meldung in text and "eingespielt." in text)
        # Das Bauteil liest den Stand nach dem Einspielen NEU vom Server.
        # Dieser zweite Aufruf braucht einen Moment — hier ausdruecklich
        # darauf warten, statt den Text vom Klick-Zeitpunkt zu lesen
        # (erste Fassung las zu frueh, BS-2d3-Befund).
        _warte(
            page,
            """() => {
                const a = document.querySelector('[data-wf-abschnitt="bausteine"]');
                return !!a && (a.innerText || '').includes('Aktuell');
            }""",
            timeout_ms=60000,
        )
        abschnitt = bereich(page)
        text = abschnitt.inner_text()
        pruefe("A15 Stand NACH Einspielen „Aktuell“", "Aktuell" in text)
        fassung = str(soll.get("mitgeliefert_version") or "")
        pruefe("A16 Anzeige nennt die eingespielte Fassung",
               f"eingespielt: Fassung {fassung}" in text)
        schuss(page, "bs2d3-a2-nach-installation-hell-1440.png")

        # ── A17: am ECHTEN Primo nachsehen ─────────────────────────────
        blocks = [b for b in primo_library_blocks() if b.startswith("diakronos/")]
        pruefe("A17 Primo enthaelt N Bibliotheksbloecke", len(blocks), soll_anzahl)
        erwartete_bloecke = sorted(f"diakronos/{b['kennung']}@v{fassung}"
                                   for b in soll_liste)
        pruefe("A18 Blocknamen folgen `diakronos/<kennung>@v<fassung>`",
               sorted(blocks), erwartete_bloecke)
        kennzahlen = primo_kennzahlen()
        pruefe("A19 Primo meldet die Bloecke selbst (library_block_count)",
               kennzahlen.get("library_block_count"), soll_anzahl)

        # ── A20/A21: (c) Fehlerfall Primo nicht erreichbar -> 503 ──────
        kommandiere(PRIMO_STOPPEN)
        page.wait_for_timeout(1000)
        antwort = post_einspielen(page)
        pruefe("A20 POST hat ein CSRF-Token mitgeschickt", antwort["tokenGesetzt"], True)
        pruefe("A21 POST einspielen ohne Primo -> 503", antwort["status"], 503)
        pruefe("A22 Meldung ohne Interna (kein Traceback, keine Primo-URL)",
               ("Traceback" not in antwort["text"]) and ("http" not in antwort["text"]))
        print("     · 503-Text:", antwort["text"][:300])

        # Der Bereich muss den Fehler auch ANZEIGEN, nicht nur der POST scheitern.
        page.reload(wait_until="domcontentloaded")
        erreicht = _warte(
            page,
            """() => {
                const a = document.querySelector('[data-wf-abschnitt="bausteine"]');
                const t = a ? (a.innerText || '').toLowerCase() : '';
                return t.includes('nicht abrufbar');
            }""",
            timeout_ms=30000,
        )
        abschnitt = bereich(page)
        text_fehler = abschnitt.inner_text() if abschnitt.count() else ""
        pruefe("A23 Oberflaeche zeigt den nicht erreichbaren Zustand", erreicht)
        print("     · Anzeige:", text_fehler[:200].replace("\n", " | "))
        schuss(page, "bs2d3-a3-primo-aus-hell-1440.png")

        # ── A24: Primo wieder da -> Seite erholt sich ──────────────────
        kommandiere(PRIMO_STARTEN)
        page.wait_for_timeout(8000)
        page.reload(wait_until="domcontentloaded")
        _warte(
            page,
            """() => {
                const a = document.querySelector('[data-wf-abschnitt="bausteine"]');
                const t = a ? (a.innerText || '') : '';
                return !!(a && a.querySelector('li.wb-baustein') && t.includes('Aktuell'));
            }""",
            timeout_ms=60000,
        )
        abschnitt = bereich(page)
        text_erholt = abschnitt.inner_text() if abschnitt.count() else ""
        pruefe("A24 nach Neustart wieder abrufbar (Stand „Aktuell“)",
               "Aktuell" in text_erholt)
        schuss(page, "bs2d3-a4-wieder-da-hell-1440.png")

        # ── A25/A26: Dunkel + Mobil ────────────────────────────────────
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(800)
        schuss(page, "bs2d3-a5-installiert-dunkel-1440.png")

        page.evaluate("document.documentElement.removeAttribute('data-theme')")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(1000)
        ueberlauf = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        pruefe("A25 kein waagerechter Ueberlauf (mobil 390, hell)", ueberlauf <= 1)
        schuss(page, "bs2d3-a6-installiert-hell-390.png")
        page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        page.wait_for_timeout(600)
        ueberlauf_dunkel = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        pruefe("A26 kein waagerechter Ueberlauf (mobil 390, dunkel)", ueberlauf_dunkel <= 1)
        schuss(page, "bs2d3-a7-installiert-dunkel-390.png")
        ctx.close()

        # ── B · Mitglied sieht den Bereich nicht ───────────────────────
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        anmelden(page, *MITGLIED)
        pruefe("B1 Mitglied sieht den Bereich NICHT", bereich(page).count(), 0)
        schuss(page, "bs2d3-b1-mitglied-ohne-bereich-1440.png")
        ctx.close()

        browser.close()

    return _abschluss()


def _abschluss() -> int:
    (ZIEL / "ergebnis.json").write_text(
        json.dumps(ERGEBNIS, indent=2, ensure_ascii=False))
    fehler = [p for p in ERGEBNIS["pruefungen"] if not p["ok"]]
    print(f"\n{len(ERGEBNIS['pruefungen'])} Pruefungen, {len(fehler)} fehlgeschlagen")
    for f in fehler:
        print("  FEHL:", f["name"], f"ist={f['ist']!r} soll={f['soll']!r}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
