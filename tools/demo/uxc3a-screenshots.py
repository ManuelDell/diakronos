"""UX-C3a (t_cfcb17b2) — Aufnahme Plantyp-Editor: Sprungleiste + Erklärspalte.

Laeuft im Playwright-Image gegen den eigenen Wegwerf-Stack. Aufgenommen werden
1366 (drei Spalten), 1200 (Erklärspalte gerade noch da) und 390 (waagerechte
Sprungleiste) — je hell und dunkel. Dazu Messwerte, damit der Nachweis nicht
nur aus Bildern besteht: Spaltenzahl, Lage der Sprungleiste (senkrecht/
waagerecht), Sichtbarkeit der Erklärspalte, ob die Markierung beim Scrollen
mitwandert und ob ein Klick auf einen Eintrag wirklich zum Abschnitt springt.

Aufruf (Beispiel steht im Kopf von tools/demo/uxb2-screenshots.py):
    docker run --rm --network <eigenes-netz> -v "$PWD":/w -e ZIEL=/ausgabe \
        --name uxc3a-shots mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/uxc3a-screenshots.py
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("UXC3A_BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")
SEITE = os.environ.get("UXC3A_SEITE", "/diakonos#/planrahmen/einrichten/chorplan")

ANSICHTEN = [
    ("1366-hell", 1366, 900, "hell"),
    ("1366-dunkel", 1366, 900, "dunkel"),
    ("1200-hell", 1200, 900, "hell"),
    ("1200-dunkel", 1200, 900, "dunkel"),
    ("390-hell", 390, 844, "hell"),
    ("390-dunkel", 390, 844, "dunkel"),
]

fehler: list = []


def anmelden(page) -> None:
    page.goto(BASE + "/diakonos", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    for text in ("E-Mail", "E-Mail-Adresse", "Benutzername", "Kennung"):
        feld = page.get_by_label(text, exact=False)
        if feld.count():
            feld.first.fill(ADMIN_EMAIL)
            break
    else:
        eingabe = page.locator("input[type=email], input[name=email], input[autocomplete=username]")
        if eingabe.count():
            eingabe.first.fill(ADMIN_EMAIL)
    pw = page.locator("input[type=password]")
    if not pw.count():
        raise SystemExit("Anmeldemaske nicht gefunden")
    pw.first.fill(ADMIN_PASS)
    page.locator("button[type=submit], button:has-text('Anmelden'), button:has-text('Einloggen')").first.click()
    page.wait_for_timeout(2500)


def messen(page) -> dict:
    return page.evaluate(
        """() => {
          const raster = document.querySelector('[data-test=pr-pe-raster]');
          const sprung = document.querySelector('[data-test=pr-pe-sprung]');
          const erklaerung = document.querySelector('[data-test=pr-pe-erklaerung]');
          const punkte = [...document.querySelectorAll('[data-abschnitt-sprung]')];
          const aktiv = document.querySelector('.pr-sprung-punkt.is-aktiv');
          const st = el => el ? getComputedStyle(el) : null;
          const rs = st(raster);
          const sp = st(sprung);
          const sichtbar = (el) => { const s = st(el); return !!s && s.display !== 'none' && s.visibility !== 'hidden' && el.getBoundingClientRect().width > 0; };
          return {
            theme: document.documentElement.getAttribute('data-theme'),
            reiterRaster: !!raster,
            spalten: rs ? rs.gridTemplateColumns : '',
            sprungRichtung: sp ? sp.flexDirection : '',
            sprungSichtbar: sichtbar(sprung),
            sprungLage: sp ? sp.position : '',
            erklaerungSichtbar: sichtbar(erklaerung),
            erklaerungTitel: erklaerung ? (erklaerung.querySelector('.pr-erklaerung-titel') || {}).textContent || '' : '',
            erklaerungBegriffe: erklaerung ? [...erklaerung.querySelectorAll('dt')].map(e => e.textContent.trim()) : [],
            punkte: punkte.map(e => e.textContent.trim()),
            aktiv: aktiv ? aktiv.textContent.trim() : '',
            abschnitte: [...document.querySelectorAll('[data-abschnitt]')].map(e => e.id),
            seitenfarbe: getComputedStyle(document.body).backgroundColor,
          };
        }"""
    )


def reiter_messen(page, reiter: str) -> dict:
    '''Breite der Flaeche des Reiters JSON/Probelauf — sie darf NICHT in der
    190-px-Spalte des Rasters landen (Review 24.10., Punkt 1).'''
    return page.evaluate(
        """(reiter) => {
          const sel = reiter === 'json' ? '.pr-pe-json' : '.pr-pe-probe';
          const el = document.querySelector(sel);
          const raster = document.querySelector('[data-test=pr-pe-raster]');
          const form = document.querySelector('.pr-pe-form');
          if (!el) return { vorhanden: false };
          const r = el.getBoundingClientRect();
          return {
            vorhanden: true,
            breite: Math.round(r.width),
            links: Math.round(r.left),
            rasterVorhanden: !!raster,
            rasterSpalten: raster ? getComputedStyle(raster).gridTemplateColumns : '',
            formLinks: form ? Math.round(form.getBoundingClientRect().left) : null,
            // Ein Kind des Rasters waere deutlich schmaler als die Seite.
            volleBreite: r.width > (document.querySelector('.dk-screen') || {}).clientWidth - 120,
          };
        }""",
        reiter,
    )


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    messungen: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, breite, hoehe, thema in ANSICHTEN:
            kontext = browser.new_context(viewport={"width": breite, "height": hoehe}, device_scale_factor=1)
            page = kontext.new_page()
            page.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: fehler.append(str(e)))
            # Theme VOR dem Aufbau setzen (wie die App beim gespeicherten
            # Dunkelmodus) — sonst startet die Seite hell und das erste Maß
            # des aktiven Abschnitts verfällt an die alte Geometrie.
            page.add_init_script(f"localStorage.setItem('dk-theme', '{'dark' if thema == 'dunkel' else 'light'}');")
            anmelden(page)
            page.goto(BASE + SEITE, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            page.evaluate(
                "(dunkel) => localStorage.setItem('dk-theme', dunkel ? 'dark' : 'light')",
                thema == "dunkel",
            )
            page.wait_for_timeout(400)
            # Prüfstand abwarten (die Definition wird gegen den Server geprüft).
            page.wait_for_selector("[data-test=pr-pe-raster]", timeout=30000)

            # Beim Öffnen steht man oben — gemessen wird der Zustand NACH dem
            # Nachmessen (die Seite misst einmal je Bild), damit das Bild den
            # gleichen Stand zeigt wie die Zahlen.
            page.wait_for_timeout(300)
            daten = messen(page)
            pfad = os.path.join(ZIEL, f"plantyp-editor-{name}.png")
            page.screenshot(path=pfad, full_page=True)

            # Scrollen: die Markierung muss mitwandern.
            vorher = daten["aktiv"]
            page.evaluate(
                """() => {
                  const el = document.getElementById('pr-pe-regeln') || document.querySelector('[data-abschnitt="pr-pe-regeln"]');
                  const c = document.querySelector('.dk-content');
                  if (el && c) c.scrollTop += el.getBoundingClientRect().top - c.getBoundingClientRect().top - 40;
                  else if (el) el.scrollIntoView();
                }"""
            )
            page.wait_for_timeout(1200)
            nachher = messen(page)
            pfad2 = os.path.join(ZIEL, f"plantyp-editor-{name}-gescrollt.png")
            page.screenshot(path=pfad2, full_page=False)

            # Sprung: Klick auf „Anlässe“ muss zum Abschnitt führen und ihn markieren.
            sprungziel = page.locator('[data-abschnitt-sprung="anlaesse"]')
            geklickt = False
            if sprungziel.count():
                sprungziel.first.click()
                page.wait_for_timeout(1500)
                geklickt = True
            nach_klick = messen(page)

            # Sprung auf „Felder“ (Review 24.10., Punkt 2): die Markierung muss
            # WIRKLICH „Felder“ zeigen — vorher fiel sie auf „Anlässe“.
            felder_punkt = page.locator('[data-abschnitt-sprung="felder"]')
            felder_klick = False
            felder_marke = ''
            felder_sichtbar_oben = None
            if felder_punkt.count():
                felder_punkt.first.click()
                page.wait_for_timeout(1800)
                felder_klick = True
                felder_marke = page.evaluate(
                    "() => { const a = document.querySelector('.pr-sprung-punkt.is-aktiv'); return a ? a.textContent.trim() : ''; }"
                )
                # Steht die Ueberschrift wirklich im Bild (nicht hinter dem Band)?
                felder_sichtbar_oben = page.evaluate(
                    """() => {
                      const el = document.getElementById('pr-pe-felder');
                      const c = document.querySelector('.dk-content');
                      if (!el || !c) return null;
                      const oben = c.getBoundingClientRect().top;
                      return Math.round(el.getBoundingClientRect().top - oben);
                    }"""
                )
            felder_bild = None
            if breite >= 1200:
                felder_bild = os.path.join(ZIEL, f"plantyp-editor-{name}-felder.png")
                page.screenshot(path=felder_bild, full_page=False)

            # Reiter JSON und Probelauf (Review 24.10., Punkt 1): sie muessen
            # ueber die volle Breite gehen, nicht in der 190-px-Spalte stehen.
            reiter_daten = {}
            if breite >= 1200:
                for wert, beschriftung in (("json", "JSON"), ("probelauf", "Probelauf")):
                    reiter_knopf = page.locator(f'.dk-tab:has-text("{beschriftung}")').first
                    if not reiter_knopf.count():
                        continue
                    reiter_knopf.click()
                    page.wait_for_timeout(1200)
                    m = reiter_messen(page, wert)
                    reiter_daten[wert] = m
                    reiter_daten[wert]["bild"] = os.path.join(ZIEL, f"plantyp-editor-{name}-{wert}.png")
                    page.screenshot(path=reiter_daten[wert]["bild"], full_page=False)
                # Zurueck ins Formular, damit die Seite wie beim Oeffnen endet.
                formular_knopf = page.locator('.dk-tab:has-text("Formular")').first
                if formular_knopf.count():
                    formular_knopf.click()
                    page.wait_for_timeout(800)

            daten.update(
                marke_vorher=vorher,
                marke_nach_scrollen=nachher["aktiv"],
                marke_nach_klick=nach_klick["aktiv"],
                sprung_geklickt=geklickt,
                gedrueckt_anlass_vorhanden=geklickt,
                felder_geklickt=felder_klick,
                felder_marke=felder_marke,
                felder_ueberschrift_oben_px=felder_sichtbar_oben,
                felder_bild=felder_bild,
                reiter=reiter_daten,
                bild=pfad,
                bild_gescrollt=pfad2,
            )
            messungen[name] = daten
            reiter_kurz = {k: f"{v.get('breite')}px/volleBreite={v.get('volleBreite')}" for k, v in reiter_daten.items()}
            print(f"[uxc3a] {pfad} spalten={daten['spalten']} erklaerung={daten['erklaerungSichtbar']} "
                  f"sprung={daten['sprungRichtung']} aktiv {vorher} -> {nachher['aktiv']} -> {nach_klick['aktiv']} "
                  f"| Felder-Klick: {felder_marke} (oben {felder_sichtbar_oben}px) | Reiter: {reiter_kurz}")
            page.close()
            kontext.close()
        browser.close()

    protokoll = os.path.join(ZIEL, "messungen-uxc3a.json")
    with open(protokoll, "w", encoding="utf-8") as f:
        json.dump(messungen, f, ensure_ascii=False, indent=1)
    print(f"[uxc3a] Messungen: {protokoll}")
    if fehler:
        print("[uxc3a] Konsolenfehler:", *fehler, sep="\n   ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
