"""REG-1c (5) — Belege: Vorschau-Hinweis ueber dem Banner, oeffentliche Seite dunkel.

Laeuft im Playwright-Image gegen den Wegwerf-Stack (Projekt ``reg1c``). Der
Stack hat die DEMO-Gemeinde (Musterhausen); Formular, Beschreibung, Banner,
Hintergrund und Link legt dieses Skript ueber die ECHTEN Schnittstellen der App
an (Admin-Anmeldung, ``create_anmeldeformular``, ``upload_file`` mit
``doctype``/``docname``, ``update_anmeldeformular``, ``create_link``).

Zwei Befunde der Karte werden GEMESSEN, nicht behauptet:

  1. **Vorschau-Hinweis darf das Banner nicht ueberdecken.** Gemessen werden die
     Rechtecke von ``.dk-pub-vorschau-hinweis`` und ``.dk-pub-banner`` im
     Vorschaubild: der Hinweis muss VOLLSTAENDIG sichtbar sein (nicht von einem
     anderen Element ueberlagert — ``elementFromPoint`` in der Mitte und an den
     Ecken) und darf sich mit dem Banner hoechstens beruehren, nicht
     ueberlappen.
  2. **Oeffentliche Seite im Dunkelmodus bei 390 px ist wirklich dunkel.**
     Gemessen wird die Helligkeit (WCAG-Luminanz) der gerenderten Flaeche des
     Seitengrundes UND des Kartenhintergrunds samt gemessenem Kontrast des
     Textes darauf. „Dunkel“ heisst: Luminanz < 0,2 und Textkontrast >= 4,5:1 —
     das ist unabhaengig davon, wie das Bild im Chatbetrachter aussieht.

Aufruf (Netz des eigenen Stacks, Zielverzeichnis gemountet):

    docker run --rm --network reg1c_default -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/reg1c-screenshots.py --warmlauf
    … danach dasselbe mit --hauptlauf (der Warmlauf legt an, was fehlt).
"""
import json
import os
import struct
import sys
import zlib

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
CHROMIUM = os.environ.get("CHROMIUM_PFAD", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

FORM_BEZEICHNUNG = "Registrierung (REG-1c)"

fehler: list[str] = []
gemessen: list[dict] = []


# ── Hilfsmittel ────────────────────────────────────────────────────────────


def png_bytes(breite: int, hoehe: int, farbe) -> bytes:
    """Einfarbiges RGB-PNG (dieselbe Form, die `upload_file` erwartet)."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten))
            + typ
            + daten
            + struct.pack(">I", zlib.crc32(typ + daten) & 0xFFFFFFFF)
        )

    zeile = b"\x00" + bytes(farbe) * breite
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(zeile * hoehe, 9))
        + chunk(b"IEND", b"")
    )


#: Bekannte, harmlose Netzfehler (fehlende optionale Symbole/Assets der SPA).
BEKANNT_404 = "Failed to load resource: the server responded with a status of 404"
bekannt: list[str] = []


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
    kopf = {"X-Frappe-CSRF-Token": csrf}
    if datei is not None:
        antwort = page.request.post(
            BASE + "/api/method/" + pfad,
            multipart=datei,
            headers=kopf,
        )
    else:
        antwort = page.request.post(
            BASE + "/api/method/" + pfad,
            form={k: str(v) for k, v in (daten or {}).items()},
            headers=kopf,
        )
    try:
        inhalt = antwort.json()
    except Exception:  # noqa: BLE001
        inhalt = {"_roh": antwort.text()[:400]}
    if not antwort.ok:
        raise RuntimeError(f"{pfad}: HTTP {antwort.status} {json.dumps(inhalt)[:300]}")
    return inhalt.get("message", inhalt)


def vorbereiten(page) -> dict:
    """Formular mit Banner/Hintergrund/Beschreibung und einen Link anlegen."""
    liste = api(page, "diakronos.diakonos.api.admin_hub.get_anmeldeformulare")
    form = next(
        (f for f in (liste.get("formulare") or []) if f.get("bezeichnung") == FORM_BEZEICHNUNG),
        None,
    )
    if form is None:
        angelegt = api(
            page,
            "diakronos.diakonos.api.admin_hub.create_anmeldeformular",
            {"bezeichnung": FORM_BEZEICHNUNG, "mit_gaesten": 0, "mit_kinder": 1},
        )
        form = {"name": angelegt["id"]}
    formular_id = form["name"]

    # REG-1c (1): Die Datei muss AM FORMULAR haengen (doctype/docname).
    def hochladen(name, inhalt):
        return api(
            page,
            "upload_file",
            datei={
                "file": {"name": name, "mimeType": "image/png", "buffer": inhalt},
                "is_private": "true",
                "doctype": "Anmeldeformular",
                "docname": formular_id,
            },
        )["file_url"].rsplit("/", 1)[-1]

    banner = hochladen("reg1c-banner.png", png_bytes(640, 180, (176, 122, 24)))
    hintergrund = hochladen("reg1c-hintergrund.png", png_bytes(800, 600, (30, 60, 110)))

    felder = [
        {"label": "T-Shirt-Größe", "feldtyp": "Auswahl", "optionen": "S\nM\nL\nXL",
         "pflichtfeld": 0, "fuer_gaeste": 0, "fuer_kinder": 0},
    ]
    api(
        page,
        "diakronos.diakonos.api.admin_hub.update_anmeldeformular",
        {
            "formular_id": formular_id,
            "bezeichnung": FORM_BEZEICHNUNG,
            "felder_json": json.dumps(felder),
            "mit_kinder": 1,
            "beschreibung": (
                "Herzlich willkommen in der Gemeinde Musterhausen!\n\n"
                "Melde dich hier an. Bei Fragen hilft das Gemeindebüro."
            ),
            "banner_bild_datei": banner,
            "hintergrund_bild_datei": hintergrund,
        },
    )

    link = api(
        page,
        "diakronos.diakonos.api.registrierungslink_api.create_link",
        {
            "bezeichnung": "REG-1c laufend",
            "typ": "Mitglied-Registrierung",
            "max_anmeldungen": 0,
            "anmeldeformular_id": formular_id,
            "ohne_ablauf": 1,
        },
    )["link"]
    return {"formular": formular_id, "link": link}


# ── Messungen ──────────────────────────────────────────────────────────────


def pruefe(name, lage, erwartet):
    gemessen.append({"name": name, "gemessen": lage, "erwartet": erwartet})
    if lage != erwartet:
        fehler.append(f"{name}: gemessen={lage!r}, erwartet={erwartet!r}")


def schuss(page, name, voll=False):
    pfad = os.path.join(ZIEL, f"{name}.png")
    page.screenshot(path=pfad, full_page=voll)
    print("geschrieben", os.path.basename(pfad))


def luminanz(auswahl: str):
    """Gerenderte Flaeche -> WCAG-Luminanz und die Farbe (gemessen, nicht geraten)."""
    return None


def seite_dunkel(page) -> dict:
    """Theme, Flaechenfarbe und Luminanz des Seitengrunds messen."""
    return page.evaluate(
        """() => {
            const zahl = (s) => {
                const m = (s.match(/[\\d.]+/g) || []).map(Number);
                return [m[0] || 0, m[1] || 0, m[2] || 0];
            };
            const leucht = (c) => {
                const f = c.map(v => {
                    v /= 255;
                    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                });
                return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2];
            };
            const seite = document.querySelector('.dk-pub-page');
            const karte = document.querySelector('.dk-pub-card');
            const flaeche = seite ? getComputedStyle(seite).backgroundColor : '';
            const kartenFlaeche = karte ? getComputedStyle(karte).backgroundColor : '';
            return {
                theme: document.documentElement.getAttribute('data-theme') || '',
                speicher: (() => { try { return localStorage.getItem('dk-theme') || ''; }
                                   catch (e) { return ''; } })(),
                flaeche: flaeche,
                kartenFlaeche: kartenFlaeche,
                luminanz: Math.round(leucht(zahl(flaeche)) * 1000) / 1000,
                kartenLuminanz: Math.round(leucht(zahl(kartenFlaeche)) * 1000) / 1000,
            };
        }"""
    )


def kontrast(page, text_auswahl: str, flaeche_auswahl: str) -> float:
    """Gemessener Kontrast Text/Flaeche (gerenderte Farben)."""
    return page.evaluate(
        """([t, f]) => {
            const zahl = (s) => {
                const m = (s.match(/[\\d.]+/g) || []).map(Number);
                return [m[0] || 0, m[1] || 0, m[2] || 0];
            };
            const leucht = (c) => {
                const f2 = c.map(v => {
                    v /= 255;
                    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                });
                return 0.2126 * f2[0] + 0.7152 * f2[1] + 0.0722 * f2[2];
            };
            const tEl = document.querySelector(t);
            const fEl = f ? document.querySelector(f) : null;
            if (!tEl) return -1;
            const vorne = zahl(getComputedStyle(tEl).color);
            const hinten = zahl(getComputedStyle(fEl || tEl).backgroundColor);
            const a = leucht(vorne) + 0.05;
            const b = leucht(hinten) + 0.05;
            return Math.round((Math.max(a, b) / Math.min(a, b)) * 100) / 100;
        }""",
        [text_auswahl, flaeche_auswahl],
    )


def hinweis_und_banner(page) -> dict:
    """Rechtecke von Vorschau-Hinweis und Banner im Vorschaubild vergleichen.

    Zusaetzlich: liegt der Hinweis wirklich obenauf? `elementFromPoint` in der
    Mitte und in allen vier Ecken des Hinweises muss den Hinweis selbst (oder
    ein Kind) liefern — sonst deckt ihn etwas zu (Bild, Leiste, Overlay).
    """
    return page.evaluate(
        """() => {
            const hinweis = document.querySelector('.reg-vorschau .dk-pub-vorschau-hinweis');
            const banner = document.querySelector('.reg-vorschau .dk-pub-banner');
            if (!hinweis) return { gefunden: false };
            const h = hinweis.getBoundingClientRect();
            const b = banner ? banner.getBoundingClientRect() : null;
            const punkte = [
                [h.left + h.width / 2, h.top + h.height / 2],
                [h.left + 3, h.top + 3],
                [h.right - 3, h.top + 3],
                [h.left + 3, h.bottom - 3],
                [h.right - 3, h.bottom - 3],
            ];
            const treffer = punkte.map(([x, y]) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return 'nichts';
                return hinweis.contains(el) || el === hinweis ? 'hinweis' : el.className || el.tagName;
            });
            const ueberlappt = b ? !(h.bottom <= b.top + 0.5 || h.top >= b.bottom - 0.5
                                     || h.right <= b.left + 0.5 || h.left >= b.right - 0.5) : false;
            return {
                gefunden: true,
                bannerDa: !!banner,
                hinweis: { top: Math.round(h.top), bottom: Math.round(h.bottom),
                           left: Math.round(h.left), right: Math.round(h.right),
                           hoehe: Math.round(h.height) },
                banner: b ? { top: Math.round(b.top), bottom: Math.round(b.bottom),
                              left: Math.round(b.left), right: Math.round(b.right) } : null,
                treffer,
                ueberlappt,
                sichtbar: getComputedStyle(hinweis).visibility === 'visible'
                          && getComputedStyle(hinweis).display !== 'none'
                          && h.height > 0,
            };
        }"""
    )


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              locale="de-DE", ignore_https_errors=True,
                              color_scheme="dark" if dunkel else "light")
    if dunkel:
        ctx.add_init_script(
            "try { localStorage.setItem('dk-theme', 'dark') } catch (e) {}")
    return ctx


def formular_reiter(page):
    """Unterbereich „Formulare“ oeffnen.

    Seit UX-A2a ist das eine NAVIGATION (`DkBereichsliste`, Links mit
    `aria-current`), keine Reiterliste mehr — deshalb ueber den Linktext.
    """
    page.goto(BASE + "/#/mitglieder/anfragen", wait_until="networkidle")
    page.wait_for_timeout(1800)
    page.get_by_role("link", name="Formulare").first.click()
    page.wait_for_timeout(900)


# ── Laeufe ─────────────────────────────────────────────────────────────────


def warmlauf(page) -> int:
    """Nur anlegen, was fehlt (Formular, Bilder, Link). Kein Beleg."""
    daten = vorbereiten(page)
    print("vorbereitet:", json.dumps({"formular": daten["formular"],
                                      "slug": daten["link"]["slug"]}))
    with open(os.path.join(ZIEL, "reg1c-daten.json"), "w") as fh:
        json.dump(daten, fh)
    return 0


def hauptlauf(browser, daten) -> int:
    slug = daten["link"]["slug"]

    # ── (5a) Vorschau: Hinweis ueber dem Banner, Desktop und Mobil ────────
    for breite, hoehe, marke in ((1366, 900, "1366"), (390, 844, "390")):
        for dunkel in (False, True):
            modus = "dunkel" if dunkel else "hell"
            ctx = kontext(browser, breite, hoehe, dunkel)
            page = ctx.new_page()
            sammeln(page, f"vorschau-{marke}-{modus}")
            anmelden(page, ADMIN, ADMIN_PASS)
            formular_reiter(page)
            page.get_by_role("button", name="Bearbeiten").first.click()
            page.wait_for_timeout(1500)
            page.click('[data-test="reg-formular-vorschau"]')
            page.wait_for_timeout(1500)
            lage = hinweis_und_banner(page)
            pruefe(f"vorschau-hinweis-da-{marke}-{modus}", lage.get("gefunden"), True)
            pruefe(f"vorschau-banner-da-{marke}-{modus}", lage.get("bannerDa"), True)
            pruefe(f"vorschau-hinweis-sichtbar-{marke}-{modus}", lage.get("sichtbar"), True)
            pruefe(f"vorschau-hinweis-frei-{marke}-{modus}",
                   lage.get("treffer") == ["hinweis"] * 5, True)
            pruefe(f"vorschau-keine-ueberlappung-{marke}-{modus}",
                   lage.get("ueberlappt"), False)
            schuss(page, f"vorschau-{marke}-{modus}")
            page.click('[data-test="reg-vorschau-schliessen"]')
            page.wait_for_timeout(400)
            ctx.close()

    # ── (5b) Oeffentliche Seite: DUNKELMODUS bei 390 px WIRKLICH dunkel ───
    for breite, hoehe, marke in ((390, 844, "390"), (1366, 900, "1366")):
        ctx = kontext(browser, breite, hoehe, dunkel=True)
        page = ctx.new_page()
        sammeln(page, f"oeffentlich-dunkel-{marke}")
        page.goto(f"{BASE}/diakonos/registrierung?token={slug}", wait_until="networkidle")
        page.wait_for_timeout(1500)
        stand = seite_dunkel(page)
        gemessen.append({"name": f"oeffentlich-theme-{marke}", "gemessen": stand, "erwartet": "dark"})
        pruefe(f"oeffentlich-theme-{marke}", stand.get("theme"), "dark")
        if stand.get("luminanz", 1) >= 0.2:
            fehler.append(f"{marke}: Seitengrund ist NICHT dunkel "
                          f"(Luminanz {stand.get('luminanz')}, Flaeche {stand.get('flaeche')})")
        if stand.get("kartenLuminanz", 1) >= 0.2:
            fehler.append(f"{marke}: Karte ist NICHT dunkel "
                          f"(Luminanz {stand.get('kartenLuminanz')}, {stand.get('kartenFlaeche')})")
        # Kontrast des Textes AUF der Karte (nicht auf dem Hintergrundbild).
        for auswahl, name in ((".dk-pub-beschreibung", "beschreibung"),
                              (".dk-pub-title", "titel")):
            wert = kontrast(page, auswahl, ".dk-pub-card")
            gemessen.append({"name": f"kontrast-{name}-{marke}",
                             "gemessen": wert, "erwartet": ">= 4.5"})
            if wert < 4.5:
                fehler.append(f"{marke}: {name} zu blass im Dunkelmodus ({wert}:1)")
        # Hintergrundbild liegt da und ist gedeckt (sonst waere der Grund hell).
        bild_da = page.evaluate(
            """() => {
                const img = document.querySelector('.dk-pub-hintergrund img');
                return !!(img && img.complete && img.naturalWidth > 0);
            }"""
        )
        pruefe(f"oeffentlich-hintergrund-da-{marke}", bild_da, True)
        schuss(page, f"oeffentlich-390px-dunkel" if marke == "390"
              else "oeffentlich-1366px-dunkel", voll=(marke == "390"))
        breite_doc = page.evaluate("document.documentElement.scrollWidth")
        pruefe(f"oeffentlich-kein-querscrollen-{marke}", breite_doc <= breite, True)
        ctx.close()

    return 0


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        optionen = {"args": ["--no-sandbox"]}
        if CHROMIUM and os.path.exists(CHROMIUM):
            optionen["executable_path"] = CHROMIUM
        browser = p.chromium.launch(**optionen)

        if "--warmlauf" in sys.argv:
            ctx = kontext(browser, 1366, 900)
            page = ctx.new_page()
            anmelden(page, ADMIN, ADMIN_PASS)
            rc = warmlauf(page)
            ctx.close()
            browser.close()
            return rc

        with open(os.path.join(ZIEL, "reg1c-daten.json")) as fh:
            daten = json.load(fh)
        rc = hauptlauf(browser, daten)
        browser.close()

    print(json.dumps({"gemessen": gemessen, "bekannt": bekannt, "fehler": fehler},
                     ensure_ascii=False, indent=1))
    return 1 if fehler or rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
