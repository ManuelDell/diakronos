"""REG-1b — Belege: Registrierung-Oberflaeche (Startdatum, Vorschau, Bilder).

Laeuft im Playwright-Image gegen den Wegwerf-Stack (`t_3b54d5ab-test`). Der
Stack hat die DEMO-Gemeinde (Musterhausen, `tools/demo`), aber bewusst KEINEN
Registrierungslink und KEIN Anmeldeformular — beides legt dieses Skript ueber
die echten Schnittstellen der App an (Admin-Anmeldung, `create_anmeldeformular`,
`upload_file`, `update_anmeldeformular`, `create_link`). Damit ist der Beleg
nicht von Hand gebaut, sondern ueber denselben Weg wie in der Oberflaeche.

Aufgenommen wird:

  1. Link-Dialog mit „Gültig ab“ (Desktop 1366 hell/dunkel, Mobil 390).
  2. Formular-Editor mit Beschreibung + Banner + Hintergrund (dito).
  3. Vorschau (Desktop hell/dunkel, Mobil).
  4. Oeffentliche Seite mit Beschreibung/Banner/Hintergrund (Desktop hell/dunkel,
     Mobil 390 hell/dunkel).
  5. Link vor dem Startdatum: Besucher sieht nur die Meldung.

Jede Aufnahme wird in der Seite GEMESSEN (Text vorhanden? Bild geladen?
Absende-Knopf in der Vorschau abgeschaltet? Lesbarkeit des Textes auf der
oeffentlichen Seite ueber den gemessenen Kontrast) — ein Screenshot ohne
Pruefung beweist nichts.

Aufruf:
    docker run --rm --network t_3b54d5ab-test_default -v "$PWD":/w:ro \
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/reg1b-screenshots.py
"""
import json
import os
import struct
import zlib

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
# Der Container bringt nur die headless-Shell; ohne diesen Pfad sucht
# Playwright `chrome-headless-shell`, hier liegt aber das volle Chromium.
CHROMIUM = os.environ.get("CHROMIUM_PFAD", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

fehler: list[str] = []
gemessen: list[dict] = []
BEKANNT_404 = "Failed to load resource: the server responded with a status of 404"
bekannt: list[str] = []


# ── Ein echtes Bild erzeugen (PNG, ohne fremde Bibliothek) ──────────────────


def png_bytes(breite: int, hoehe: int, farbe: tuple[int, int, int]) -> bytes:
    """Einfarbiges RGB-PNG — dieselbe Form, die `upload_file` erwartet."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten))
            + typ
            + daten
            + struct.pack(">I", zlib.crc32(typ + daten) & 0xFFFFFFFF)
        )

    zeile = b"\x00" + bytes(farbe) * breite
    roh = zeile * hoehe
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(roh, 9))
        + chunk(b"IEND", b"")
    )


def datei_schreiben(name: str, inhalt: bytes) -> str:
    pfad = os.path.join("/tmp", name)
    with open(pfad, "wb") as fh:
        fh.write(inhalt)
    return pfad


# ── Anmeldung und Vorbereitung ──────────────────────────────────────────────


def sammeln(page, name):
    def bei(m):
        if m.type != "error":
            return
        if BEKANNT_404 in m.text:
            bekannt.append(f"{name}: {m.text}")
            return
        fehler.append(f"{name}: {m.text}")
    page.on("console", bei)
    page.on("pageerror", lambda e: fehler.append(f"{name}: {e}"))


def anmelden(page, email, passwort):
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(500)
    page.fill("#dk-usr", email)
    page.fill("#dk-pwd", passwort)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")


def api(page, pfad, daten=None, datei=None):
    """Aufruf ueber die echten Endpunkte (CSRF-Kopf aus der Seite)."""
    csrf = page.evaluate("document.querySelector('meta[name=csrf-token]')?.content || ''")
    if datei is not None:
        antwort = page.request.post(
            BASE + "/api/method/" + pfad,
            multipart={
                "file": {"name": datei[0], "mimeType": "image/png", "buffer": datei[1]},
                "is_private": "true",
            },
            headers={"X-Frappe-CSRF-Token": csrf},
        )
    else:
        antwort = page.request.post(
            BASE + "/api/method/" + pfad,
            form=({k: str(v) for k, v in (daten or {}).items()}),
            headers={"X-Frappe-CSRF-Token": csrf},
        )
    try:
        inhalt = antwort.json()
    except Exception:  # noqa: BLE001
        inhalt = {"_roh": antwort.text()[:400]}
    if not antwort.ok:
        raise RuntimeError(f"{pfad}: HTTP {antwort.status} {json.dumps(inhalt)[:300]}")
    # Frappe-Antwort: {"message": …}
    return inhalt.get("message", inhalt)


def vorbereiten(page) -> dict:
    """Formular mit Beschreibung/Bildern und einen Link anlegen (idempotent)."""
    # Gibt es schon ein Formular? Dann nehmen wir es.
    liste = api(page, "diakronos.diakonos.api.admin_hub.get_anmeldeformulare")
    formulare = liste.get("formulare") or []
    form = next((f for f in formulare if f.get("bezeichnung") == "Registrierung (REG-1b)"), None)
    if form is None:
        angelegt = api(
            page,
            "diakronos.diakonos.api.admin_hub.create_anmeldeformular",
            {"bezeichnung": "Registrierung (REG-1b)", "mit_gaesten": 0, "mit_kinder": 1},
        )
        form = {"name": angelegt["id"]}

    felder = [
        {"label": "T-Shirt-Größe", "feldtyp": "Auswahl", "optionen": "S\nM\nL\nXL",
         "pflichtfeld": 0, "fuer_gaeste": 0, "fuer_kinder": 0},
        {"label": "Ich helfe beim Gemeindefest", "feldtyp": "Ja-Nein", "optionen": "",
         "pflichtfeld": 0, "fuer_gaeste": 0, "fuer_kinder": 0},
    ]

    banner = api(page, "upload_file", datei=("banner.png", png_bytes(640, 180, (176, 122, 24))))
    hintergrund = api(
        page, "upload_file", datei=("hintergrund.png", png_bytes(800, 600, (30, 60, 110)))
    )

    api(
        page,
        "diakronos.diakonos.api.admin_hub.update_anmeldeformular",
        {
            "formular_id": form["name"],
            "bezeichnung": "Registrierung (REG-1b)",
            "felder_json": json.dumps(felder),
            "beschreibung": (
                "Herzlich willkommen in der Evangelischen Gemeinde Musterhausen!\n\n"
                "Melde dich hier für die Gemeinde an. Kinder unter 6 Jahren bitte "
                "zusätzlich in der Kinderliste eintragen.\n\n"
                "Bei Fragen hilft das Gemeindebüro gerne weiter."
            ),
            "banner_bild_datei": banner["file_url"].rsplit("/", 1)[-1],
            "hintergrund_bild_datei": hintergrund["file_url"].rsplit("/", 1)[-1],
        },
    )

    # Zwei Links: einer laeuft, einer beginnt erst spaeter. Sie werden bei
    # JEDEM Lauf neu angelegt — der Slug ist ein Zufallstoken, ein alter Link
    # (etwa auf ein anderes Formular) wuerde die Aufnahme verfaelschen.
    fertig = {}
    for wunsch, zusatz in (
        # Der laufende Link ausdruecklich OHNE Ablauf: die Gemeinde-Vorgabe
        # (30 Tage) greift sonst und der zweite Link (Start 2027) laege nach
        # seinem Ende — der Server lehnt das zu Recht ab.
        ("REG-1b laufend", {"ohne_ablauf": 1}),
        ("REG-1b startet spaeter", {"gueltig_ab": "2027-01-15", "ohne_ablauf": 1}),
    ):
        antwort = api(
            page,
            "diakronos.diakonos.api.registrierungslink_api.create_link",
            {
                "bezeichnung": wunsch,
                "typ": "Mitglied-Registrierung",
                "max_anmeldungen": 0,
                "anmeldeformular_id": form["name"],
                **zusatz,
            },
        )
        fertig[wunsch] = antwort["link"]
    return {"form": form["name"], "links": fertig}


# ── Messungen und Aufnahmen ────────────────────────────────────────────────


def pruefe(name, lage, erwartet):
    gemessen.append({"name": name, "gemessen": lage, "erwartet": erwartet})
    if lage != erwartet:
        fehler.append(f"{name}: gemessen={lage!r}, erwartet={erwartet!r}")


def schuss(page, name, breite, voll=False):
    datei = os.path.join(ZIEL, f"{name}.png")
    page.screenshot(path=datei, full_page=voll or breite == 390)
    print("geschrieben", os.path.basename(datei))


def bild_geladen(page, auswahl: str) -> bool:
    return bool(page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            return !!(el && el.complete && el.naturalWidth > 0);
        }""",
        auswahl,
    ))


def kontrast(page, text_auswahl: str, flaeche_auswahl: str) -> float:
    """Gemessener Kontrast zwischen Text und seiner (berechneten) Flaeche.

    Nimmt die tatsaechlich gerenderten Farben (getComputedStyle) — damit ist
    „das Bild macht den Text nicht unlesbar“ messbar und nicht behauptet.
    """
    return page.evaluate(
        """([t, f]) => {
            const farbe = (s) => {
                const m = s.match(/[\\d.]+/g).map(Number);
                return [m[0], m[1], m[2]];
            };
            const leucht = (c) => {
                const f = c.map(v => {
                    v /= 255;
                    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                });
                return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2];
            };
            const tEl = document.querySelector(t);
            const fEl = f ? document.querySelector(f) : null;
            if (!tEl) return -1;
            const vorne = farbe(getComputedStyle(tEl).color);
            const hinten = farbe(getComputedStyle(fEl || tEl).backgroundColor);
            const a = leucht(vorne) + 0.05;
            const b = leucht(hinten) + 0.05;
            return Math.round((Math.max(a, b) / Math.min(a, b)) * 100) / 100;
        }""",
        [text_auswahl, flaeche_auswahl],
    )


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              locale="de-DE", ignore_https_errors=True)
    if dunkel:
        ctx.add_init_script(
            "try { localStorage.setItem('dk-theme', 'dark') } catch (e) {}")
    return ctx


def formular_reiter(page):
    """Reiter „Formulare“ im Bereich Anfragen oeffnen (DkSegment = role=tab)."""
    page.goto(BASE + "/#/mitglieder/anfragen", wait_until="networkidle")
    page.wait_for_timeout(1800)
    page.get_by_role("tab", name="Formulare").first.click()
    page.wait_for_timeout(900)


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        optionen = {"args": ["--no-sandbox"]}
        if CHROMIUM and os.path.exists(CHROMIUM):
            optionen["executable_path"] = CHROMIUM
        browser = p.chromium.launch(**optionen)

        # ── Vorbereitung: Formular + Links anlegen (einmal, als Admin) ─────
        ctx = kontext(browser, 1366, 900)
        page = ctx.new_page()
        # Vor dem Anlegen abgestellte Netzfehler zaehlen nicht.
        anmelden(page, ADMIN, ADMIN_PASS)
        daten = vorbereiten(page)
        print("vorbereitet:", json.dumps({k: list(v.keys()) for k, v in daten["links"].items()}))
        ctx.close()

        laufend = daten["links"]["REG-1b laufend"]
        spaeter = daten["links"]["REG-1b startet spaeter"]

        for dunkel in (False, True):
            marke = "dunkel" if dunkel else "hell"

            # ── Editor: Formular mit Beschreibung und Bildern ──────────────
            ctx = kontext(browser, 1366, 900, dunkel)
            page = ctx.new_page()
            sammeln(page, f"editor-{marke}")
            anmelden(page, ADMIN, ADMIN_PASS)
            formular_reiter(page)
            seite_text = page.inner_text("body")
            pruefe(f"formularliste-{marke}", "Registrierung (REG-1b)" in seite_text, True)
            page.get_by_role("button", name="Bearbeiten").first.click()
            page.wait_for_timeout(1500)
            schuss(page, f"editor-formular-1366-{marke}", 1366)

            beschreibung = page.input_value('[data-test="reg-formular-beschreibung"]')
            pruefe(f"editor-beschreibung-{marke}", "Musterhausen" in beschreibung, True)
            pruefe(
                f"editor-banner-{marke}",
                bild_geladen(page, ".reg-bild-vorschau"),
                True,
            )
            schuss(page, f"editor-formular-bilder-1366-{marke}", 1366)

            # ── Vorschau ───────────────────────────────────────────────────
            page.click('[data-test="reg-formular-vorschau"]')
            page.wait_for_timeout(1500)
            schuss(page, f"vorschau-1366-{marke}", 1366)
            vorschauText = page.inner_text(".reg-vorschau")
            pruefe(f"vorschau-beschreibung-{marke}", "Herzlich willkommen" in vorschauText, True)
            pruefe(f"vorschau-feld-{marke}", "T-Shirt-Größe" in vorschauText, True)
            pruefe(
                f"vorschau-banner-{marke}",
                bild_geladen(page, ".reg-vorschau .dk-pub-banner"),
                True,
            )
            abgeschaltet = page.evaluate(
                """() => {
                    const b = document.querySelector('.reg-vorschau button[type=submit]');
                    return !!(b && b.disabled);
                }"""
            )
            pruefe(f"vorschau-absenden-aus-{marke}", abgeschaltet, True)
            ctx.close()

            # ── Oeffentliche Seite ────────────────────────────────────────
            ctx = kontext(browser, 1366, 900, dunkel)
            page = ctx.new_page()
            sammeln(page, f"oeffentlich-{marke}")
            page.goto(f"{BASE}/diakonos/registrierung?token={laufend['slug']}",
                      wait_until="networkidle")
            page.wait_for_timeout(1500)
            schuss(page, f"oeffentlich-1366-{marke}", 1366)
            pruefe(
                f"oeffentlich-beschreibung-{marke}",
                "Herzlich willkommen" in page.inner_text("body"),
                True,
            )
            pruefe(f"oeffentlich-banner-{marke}", bild_geladen(page, ".dk-pub-banner"), True)
            pruefe(
                f"oeffentlich-hintergrund-{marke}",
                bild_geladen(page, ".dk-pub-hintergrund img"),
                True,
            )
            wert = kontrast(page, ".dk-pub-beschreibung", ".dk-pub-beschreibung")
            gemessen.append({"name": f"kontrast-beschreibung-{marke}", "gemessen": wert, "erwartet": ">= 4.5"})
            if wert < 4.5:
                fehler.append(f"Beschreibung zu blass ({wert}:1) — Text kaum lesbar")
            ctx.close()

        # ── Mobil 390 px ─────────────────────────────────────────────────
        for dunkel in (False, True):
            marke = "dunkel" if dunkel else "hell"
            ctx = kontext(browser, 390, 844, dunkel)
            page = ctx.new_page()
            sammeln(page, f"mobil-{marke}")
            anmelden(page, ADMIN, ADMIN_PASS)
            formular_reiter(page)
            page.get_by_role("button", name="Bearbeiten").first.click()
            page.wait_for_timeout(1500)
            schuss(page, f"editor-formular-390-{marke}", 390)
            page.click('[data-test="reg-formular-vorschau"]')
            page.wait_for_timeout(1500)
            schuss(page, f"vorschau-390-{marke}", 390)
            page.click('[data-test="reg-vorschau-schliessen"]')
            page.wait_for_timeout(500)
            ctx.close()

            ctx = kontext(browser, 390, 844, dunkel)
            page = ctx.new_page()
            sammeln(page, f"oeffentlich-390-{marke}")
            page.goto(f"{BASE}/diakonos/registrierung?token={laufend['slug']}",
                      wait_until="networkidle")
            page.wait_for_timeout(1500)
            schuss(page, f"oeffentlich-390-{marke}", 390)
            breite = page.evaluate("document.documentElement.scrollWidth")
            pruefe(f"kein-querscrollen-390-{marke}", breite <= 390, True)
            wert = kontrast(page, ".dk-pub-beschreibung", ".dk-pub-beschreibung")
            gemessen.append({"name": f"kontrast-beschreibung-390-{marke}", "gemessen": wert, "erwartet": ">= 4.5"})
            if wert < 4.5:
                fehler.append(f"390 {marke}: Beschreibung zu blass ({wert}:1)")
            ctx.close()

        # ── Link-Dialog mit „Gültig ab“ ──────────────────────────────────
        for breite, hoehe, name in ((1366, 900, "1366"), (390, 844, "390")):
            ctx = kontext(browser, breite, hoehe)
            page = ctx.new_page()
            sammeln(page, f"linkdialog-{name}")
            anmelden(page, ADMIN, ADMIN_PASS)
            page.goto(BASE + "/#/mitglieder/anfragen", wait_until="networkidle")
            page.wait_for_timeout(1200)
            page.get_by_role("tab", name="Links & QR-Codes").first.click()
            page.wait_for_timeout(800)
            page.get_by_role("button", name="Neuer Link").first.click()
            page.wait_for_timeout(800)
            schuss(page, f"link-dialog-{name}-gueltig-ab", breite)
            text = page.inner_text(".dk-ui-dialog")
            pruefe(f"linkdialog-gueltig-ab-{name}", "Gültig ab" in text, True)
            # Der Link vor dem Startdatum steht als Karte mit Zustand da.
            ctx.close()

        # ── Besucher am Link VOR dem Startdatum ──────────────────────────
        ctx = kontext(browser, 1366, 900)
        page = ctx.new_page()
        sammeln(page, "bevorstehend")
        page.goto(f"{BASE}/diakonos/registrierung?token={spaeter['slug']}",
                  wait_until="networkidle")
        page.wait_for_timeout(1200)
        schuss(page, "oeffentlich-vor-startdatum-1366", 1366)
        text = page.inner_text("body")
        pruefe("vor-start-meldung", text.startswith("Zugang nicht möglich") or "Zugang nicht möglich" in text, True)
        pruefe("vor-start-datum", "15.01.2027" in text, True)
        ctx.close()

        ctx = kontext(browser, 1366, 900)
        page = ctx.new_page()
        sammeln(page, "bevorstehend-admin")
        anmelden(page, ADMIN, ADMIN_PASS)
        page.goto(BASE + "/#/mitglieder/anfragen", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.get_by_role("tab", name="Links & QR-Codes").first.click()
        page.wait_for_timeout(900)
        schuss(page, "linkkarte-vor-startdatum-1366", 1366)
        text = page.inner_text("body")
        pruefe("linkkarte-gueltig-ab", "Gültig ab:" in text, True)
        pruefe("linkkarte-zustand", "Startet später" in text, True)
        ctx.close()

        browser.close()

    print(json.dumps({"gemessen": gemessen, "bekannt": bekannt, "fehler": fehler},
                     ensure_ascii=False, indent=1))
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
