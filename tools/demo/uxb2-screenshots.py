"""UX-B2 (t_3db059a3) — Aufnahme von „Meine Dienste" in vier Ansichten.

Laeuft im Playwright-Image gegen den eigenen Wegwerf-Stack (Port aus UXB2_BASE).
Zwei Zustaende:
    --rolle admin     Konto admin@example.org (Gemeindeleitung, mehrere Rollen)
    --rolle mitglied  Konto der Demo-Mitgliedsperson
Aufgenommen werden Desktop 1366 (hell/dunkel) und Mobil 390 (hell/dunkel).
Ausserdem: Zaehlungen und die Farbwerte der Rollenzeichen landen in einer
JSON-Datei daneben — so ist der Nachweis nicht nur ein Bild.

Aufruf:
    docker run --rm --network t_3db059a3-test_default \
        -v "$PWD":/w -v /root/.hermes/scratch/diakronos-planrahmen/ui-screens/t_3db059a3:/ausgabe \
        -e UXB2_BASE=http://app:8000 -e ZIEL=/ausgabe --name uxb2-shots \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/uxb2-screenshots.py --rolle admin --marke vorher
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("UXB2_BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")
MITGLIED_EMAIL = os.environ.get("MITGLIED_EMAIL", "anna@example.org")
MITGLIED_PASS = os.environ.get("MITGLIED_PASS", "musterhausen-demo")
SEITE = "/diakonos#/planrahmen/meine-dienste"

ANSICHTEN = [
    ("1366-hell", 1366, 900, "hell"),
    ("1366-dunkel", 1366, 900, "dunkel"),
    ("390-hell", 390, 844, "hell"),
    ("390-dunkel", 390, 844, "dunkel"),
]

fehler: list[str] = []


def anmelden(page, email: str, passwort: str) -> None:
    page.goto(BASE + "/diakonos", wait_until="domcontentloaded")
    page.wait_for_timeout(800)
    # Die Anmeldemaske im SPA (Dk*-Formular) — Beschriftungen wie im Betrieb.
    for text in ("E-Mail", "E-Mail-Adresse", "Benutzername", "Kennung"):
        feld = page.get_by_label(text, exact=False)
        if feld.count():
            feld.first.fill(email)
            break
    else:
        eingabe = page.locator("input[type=email], input[name=email], input[autocomplete=username]")
        if eingabe.count():
            eingabe.first.fill(email)
    pw = page.locator("input[type=password]")
    if not pw.count():
        raise SystemExit("Anmeldemaske nicht gefunden")
    pw.first.fill(passwort)
    page.locator("button[type=submit], button:has-text('Anmelden'), button:has-text('Einloggen')").first.click()
    page.wait_for_timeout(2500)


def zaehlen(page) -> dict:
    """Messwerte der Seite — misst beide Staende: Karten (nachher) und die
    alte Gruppenliste (vorher), damit derselbe Lauf vergleichbar bleibt."""
    return page.evaluate("""() => {
      const karten = [...document.querySelectorAll('.pr-md-monat')];
      const zeichen = [...document.querySelectorAll('.pr-md-rolle-zeichen')];
      const farben = {};
      for (const z of zeichen) {
        const st = getComputedStyle(z);
        const key = (z.textContent || '').trim();
        farben[key] = { farbe: st.backgroundColor, schrift: st.color };
      }
      const legende = [...document.querySelectorAll('.pr-md-legende-punkt')].map(el => el.textContent.trim());
      const altZeilen = [...document.querySelectorAll('.pr-md-zeile')];
      const zeilen = karten.length
        ? [...document.querySelectorAll('.pr-md-monat-zeile')].length
        : altZeilen.length;
      return {
        karten: karten.length,
        kartentitel: karten.map(k => (k.querySelector('.pr-md-monat-titel')||{}).textContent || '').map(s => s.trim()),
        alteGruppen: [...document.querySelectorAll('.pr-md-gruppe-titel')].map(el => el.textContent.trim()),
        zeilen,
        zeichen: zeichen.length,
        farben,
        legende,
        // Kontrast der Seitenflaeche (Dunkelmodus-Pruefung).
        seitenfarbe: getComputedStyle(document.body).backgroundColor,
        theme: document.documentElement.getAttribute('data-theme'),
        titel: (document.querySelector('.dk-screen-title')||{}).textContent || '',
      };
    }""")


def thema_setzen(page, dunkel: bool) -> None:
    """Theme ueber den App-Schalter (localStorage 'dk-theme'), wie der Nutzer es tut."""
    page.evaluate(
        """(dunkel) => {
            localStorage.setItem('dk-theme', dunkel ? 'dark' : 'light');
        }""",
        dunkel,
    )
    page.wait_for_timeout(200)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rolle", choices=["admin", "mitglied"], default="admin")
    ap.add_argument("--marke", default="nachher")
    args = ap.parse_args()

    email, passwort = (ADMIN_EMAIL, ADMIN_PASS) if args.rolle == "admin" else (MITGLIED_EMAIL, MITGLIED_PASS)
    os.makedirs(ZIEL, exist_ok=True)
    messungen: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, breite, hoehe, thema in ANSICHTEN:
            kontext = browser.new_context(viewport={"width": breite, "height": hoehe},
                                          device_scale_factor=1)
            page = kontext.new_page()
            page.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: fehler.append(str(e)))
            if thema == "dunkel":
                page.add_init_script("localStorage.setItem('dk-theme', 'dark');")
            anmelden(page, email, passwort)
            page.goto(BASE + SEITE, wait_until="domcontentloaded")
            page.wait_for_timeout(1800)
            if thema == "dunkel":
                thema_setzen(page, True)
            else:
                thema_setzen(page, False)
            page.wait_for_timeout(500)
            pfad = os.path.join(ZIEL, f"meine-dienste-{args.rolle}-{name}-{args.marke}.png")
            page.screenshot(path=pfad, full_page=True)
            daten = zaehlen(page)
            daten["bild"] = pfad
            messungen[f"{args.rolle}-{name}"] = daten
            print(f"[uxb2] {pfad}  karten={daten['karten']} zeilen={daten['zeilen']} "
                  f"zeichen={daten['zeichen']} theme={daten['theme']}")
            kontext.close()
        browser.close()

    protokoll = os.path.join(ZIEL, f"messungen-{args.rolle}-{args.marke}.json")
    with open(protokoll, "w", encoding="utf-8") as f:
        json.dump(messungen, f, ensure_ascii=False, indent=1)
    print(f"[uxb2] Messungen: {protokoll}")
    if fehler:
        print("[uxb2] Konsolenfehler:")
        for f_ in fehler:
            print("   " + f_)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
