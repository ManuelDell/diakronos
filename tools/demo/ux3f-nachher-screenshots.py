"""UX3f NACHTRAG — Abnahme-Screenshots der Befehlspalette nach der Nacharbeit.

Laeuft im Playwright-Image gegen einen EIGENEN Wegwerf-Stack mit den Demo-Daten
(Musterhausen). Aufgenommen wird Desktop 1440x900 und Mobil 390x844, je hell
und dunkel.

    docker run --rm --network <projekt>_default \
        -v "<worktree>":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe -e MARKER=nachher \
        -e ADMIN_EMAIL=admin@example.org -e ADMIN_PASS=musterhausen-demo \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux3f-nachher-screenshots.py

GEPRUEFT wird zusaetzlich (exit 1 bei Befund), jeweils die Review-Punkte:
  1. DSGVO: der Verlaufsspeicher-Schluessel traegt den Nutzer-Hash; nach
     einer Wahl steht der Eintrag unter DIESEM Schluessel und die
     Nutzerkennung steht NICHT im Klartext im localStorage.
  2. Tastatur: ↑↓/End halten die aktive Zeile im Bild (gemessen: sichtbarer
     Bereich der Liste vs. Rechteck der aktiven Zeile), Esc schliesst.
  3. Fokus: beim Oeffnen liegt der Fokus im Suchfeld, Tab bleibt im Dialog,
     nach Esc steht er wieder auf dem Suchfeld der Kopfzeile.
  4. Kalender: „Termin anlegen“ oeffnet den Dialog AUCH, wenn der Kalender
     schon offen ist (#/kalender -> #/kalender?neu=1).
  5. Abschnitte: role=group mit aria-labelledby.
  6. Kopfzeile 390 px: Suchfeld und Menue-Knopf stehen nebeneinander (UX3f
     + UX3e), kein Ueberlauf.

Die Bilder sind Abnahme-Belege (erfundene Demo-Daten), keine Veroeffentlichung.
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")

MOBIL = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 900}

fehler: list[str] = []


def anmelden(page) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('#dk-usr, input[name="usr"]', BENUTZER)
    page.fill('#dk-pwd, input[name="pwd"]', PASSWORT)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_load_state("networkidle")


def schuss(page, ordner: str, name: str) -> None:
    pfad = os.path.join(ZIEL, MARKER, ordner)
    os.makedirs(pfad, exist_ok=True)
    ziel = os.path.join(pfad, name + ".png")
    page.screenshot(path=ziel)
    print(f"[ux3f] Bild: {ziel}")


def pruefe(was: str, ok: bool, detail: str = "") -> None:
    print(f"[ux3f] {'OK  ' if ok else 'FEHL'} {was}{(' — ' + detail) if detail else ''}")
    if not ok:
        fehler.append(f"{was}{(' — ' + detail) if detail else ''}")


def thema_setzen(page, thema: str) -> str:
    gespeichert = "dark" if thema == "dunkel" else "light"
    page.add_init_script(
        f"try {{ localStorage.setItem('dk-theme', {gespeichert!r}) }} catch (e) {{}}"
    )
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(400)
    ist = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    pruefe(f"Theme {thema} aktiv", ist == gespeichert, f"data-theme={ist!r}")
    return gespeichert


def palette_oeffnen(page) -> None:
    page.keyboard.press("Control+k")
    page.wait_for_selector(".dk-palette", timeout=5000)
    page.wait_for_timeout(250)


def abschnitte(page) -> list[str]:
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('.dk-palette-abschnitt'))
            .map(e => e.textContent.trim())"""
    )


def aufnahmen(page, ordner: str) -> None:
    # 0) Kopfzeile allein
    page.goto(BASE + "/#/", wait_until="networkidle")
    page.wait_for_timeout(400)
    schuss(page, ordner, "01-kopfzeile")

    # 1) Palette, Startzustand (Zuletzt verwendet · Seiten · Aktionen)
    palette_oeffnen(page)
    schuss(page, ordner, "02-palette-start")
    liste = abschnitte(page)
    pruefe(f"{ordner}: Startzustand hat Seiten und Aktionen",
           "SEITEN" in [s.upper() for s in liste] and "AKTIONEN" in [s.upper() for s in liste],
           str(liste))

    # 2) Treffer (Abschnitte Personen/Termine/Lieder)
    page.fill(".dk-palette-feld", "be")
    page.wait_for_timeout(900)
    schuss(page, ordner, "03-palette-treffer")
    liste = abschnitte(page)
    pruefe(f"{ordner}: Treffer zeigen Abschnitte ohne leere Ueberschrift",
           all(s.strip() for s in liste), str(liste))

    # 3) Review 2 — Tastatur: End springt ans Listenende und bleibt IM BILD
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(120)
    schuss(page, ordner, "04-pfeil-runter")
    page.keyboard.press("End")
    page.wait_for_timeout(200)
    sichtbar = page.evaluate(
        """() => {
            const liste = document.querySelector('.dk-palette-liste')
            const aktiv = document.querySelector('.dk-palette-zeile.is-aktiv')
            if (!liste || !aktiv) return null
            const l = liste.getBoundingClientRect()
            const a = aktiv.getBoundingClientRect()
            return {listeOben: l.top, listeUnten: l.bottom, zeileOben: a.top,
                    zeileUnten: a.bottom, scroll: liste.scrollTop}
        }"""
    )
    pruefe(f"{ordner}: aktive Zeile bleibt nach „End“ im Bild",
           bool(sichtbar) and sichtbar["zeileOben"] >= sichtbar["listeOben"] - 1
           and sichtbar["zeileUnten"] <= sichtbar["listeUnten"] + 1,
           json.dumps(sichtbar))
    schuss(page, ordner, "05-ende-im-bild")

    # 4) Review 5 — Abschnitte sind Gruppen mit Namen
    gruppen = page.evaluate(
        """() => Array.from(document.querySelectorAll('.dk-palette-abschnitt[role="group"]'))
            .map(e => [e.getAttribute('aria-labelledby'),
                       document.getElementById(e.getAttribute('aria-labelledby'))?.textContent.trim()])"""
    )
    pruefe(f"{ordner}: Abschnitte role=group mit aria-labelledby",
           bool(gruppen) and all(g[0] and g[1] for g in gruppen), json.dumps(gruppen))

    # 5) Review 1 — DSGVO: Schluessel je Nutzer, keine E-Mail im Klartext
    page.fill(".dk-palette-feld", "personen")
    page.wait_for_timeout(700)
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    speicher = page.evaluate(
        """() => {
            const raus = {}
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i)
                if (k && k.startsWith('dk-befehlspalette-zuletzt')) raus[k] = localStorage.getItem(k)
            }
            return {schluessel: Object.keys(raus), roh: JSON.stringify(raus)}
        }"""
    )
    schluessel = speicher["schluessel"]
    pruefe(f"{ordner}: Verlauf haengt am Nutzer (Hash-Schluessel)",
           len(schluessel) == 1 and schluessel[0].startswith("dk-befehlspalette-zuletzt:"),
           str(schluessel))
    pruefe(f"{ordner}: Nutzerkennung steht nicht im Klartext im Verlauf",
           "@" not in speicher["roh"] and BENUTZER not in speicher["roh"],
           speicher["roh"][:160])
    pruefe(f"{ordner}: „Zuletzt verwendet“ ist nach der Wahl gefuellt",
           "personen" in speicher["roh"].lower(), speicher["roh"][:160])

    # 6) Review 3 — Fokus: im Suchfeld, Tab bleibt im Dialog, Esc gibt zurueck
    page.goto(BASE + "/#/", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.click(".dk-topbar-suche")
    page.wait_for_selector(".dk-palette", timeout=5000)
    page.wait_for_timeout(250)
    im_feld = page.evaluate("() => document.activeElement?.classList.contains('dk-palette-feld')")
    pruefe(f"{ordner}: Fokus liegt im Suchfeld", im_feld is True, str(im_feld))
    schuss(page, ordner, "06-zuletzt-verwendet")
    for _ in range(6):
        page.keyboard.press("Tab")
        page.wait_for_timeout(40)
    im_dialog = page.evaluate("() => !!document.activeElement?.closest('.dk-palette')")
    pruefe(f"{ordner}: Tab bleibt im Dialog (Fokusfalle)", im_dialog is True, str(im_dialog))
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    zurueck = page.evaluate(
        "() => !!document.activeElement?.classList.contains('dk-topbar-suche')"
    )
    pruefe(f"{ordner}: Esc schliesst und gibt den Fokus zurueck", zurueck is True, str(zurueck))
    schuss(page, ordner, "07-nach-esc")

    # 7) Review 4 — „Termin anlegen“ bei SCHON offenem Kalender
    page.goto(BASE + "/#/kalender", wait_until="networkidle")
    page.wait_for_timeout(900)
    schuss(page, ordner, "08-kalender-offen")
    palette_oeffnen(page)
    page.fill(".dk-palette-feld", "termin anlegen")
    page.wait_for_timeout(700)
    schuss(page, ordner, "09-aktion-termin")
    page.keyboard.press("Enter")
    page.wait_for_timeout(1200)
    dialog = page.evaluate(
        """() => {
            const text = document.body.innerText || ''
            const neu = document.querySelector('.kronos-modal, .dk-dialog, [role="dialog"]')
            return {dialog: !!neu, hash: location.hash,
                    titel: text.includes('Termin anlegen') || text.includes('Neuer Termin')}
        }"""
    )
    pruefe(f"{ordner}: „Termin anlegen“ wirkt bei offenem Kalender",
           dialog["dialog"] is True, json.dumps(dialog))
    schuss(page, ordner, "10-nach-aktion-termin")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def kopfzeile_mobil(page, ordner: str) -> None:
    page.goto(BASE + "/#/", wait_until="networkidle")
    page.wait_for_timeout(500)
    masse = page.evaluate(
        """() => {
            const suche = document.querySelector('.dk-topbar-suche')
            const menue = document.querySelector('.dk-menue-knopf')
            const leiste = suche ? suche.closest('header') : null
            const r = (e) => e ? e.getBoundingClientRect() : null
            return {suche: r(suche), menue: r(menue), leiste: r(leiste),
                    breite: window.innerWidth,
                    scrollB: document.documentElement.scrollWidth}
        }"""
    )
    s, m, l = masse["suche"], masse["menue"], masse["leiste"]
    pruefe(f"{ordner}: Suchfeld und Menue-Knopf stehen beide in der Kopfzeile",
           bool(s) and bool(m), json.dumps({k: v for k, v in masse.items() if k != 'suche'}))
    if s and m and l:
        ueberlappt = s["left"] < m["right"] and m["left"] < s["right"]
        drin = s["right"] <= l["right"] + 1 and m["left"] >= l["left"] - 1
        pruefe(f"{ordner}: kein Ueberlauf/keine Ueberlappung der beiden Knoepfe",
               not ueberlappt and drin,
               f"suche={s['left']:.0f}-{s['right']:.0f} menue={m['left']:.0f}-{m['right']:.0f} leiste={l['left']:.0f}-{l['right']:.0f}")
    pruefe(f"{ordner}: kein waagerechtes Scrollen (390 px)",
           masse["scrollB"] <= masse["breite"] + 1,
           f"scrollWidth={masse['scrollB']} innerWidth={masse['breite']}")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for geraet, groesse in (("desktop", DESKTOP), ("mobil", MOBIL)):
            for thema in ("hell", "dunkel"):
                context = browser.new_context(
                    viewport=groesse, device_scale_factor=1,
                    has_touch=(geraet == "mobil"),
                    is_mobile=(geraet == "mobil"),
                )
                page = context.new_page()
                anmelden(page)
                thema_setzen(page, thema)
                ordner = f"{geraet}-{thema}"
                aufnahmen(page, ordner)
                if geraet == "mobil":
                    kopfzeile_mobil(page, ordner)
                context.close()
        browser.close()

    if fehler:
        print(f"[ux3f] {len(fehler)} Befund(e):")
        for f in fehler:
            print(f"  - {f}")
        return 1
    print("[ux3f] alle Pruefungen gruen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
