"""FIX-5 (Operator-Auflage 2) — Lastfall messen: Handy-Überlauf, Avatar.

Gemessen wird die Gruppen-Detailseite der Lastfall-Gruppe
(``tools/demo/fix5-lastfall.py``: langer Name, sechs Verantwortliche, erste
Person „DS“ ohne Foto) und die Gruppenliste (lange Kachelnamen).

Breiten 344, 390 und 1366 px; Themes hell und dunkel.

Je Lauf wird NICHT nur der Rahmen der Karten gemessen, sondern der gesamte
Dokument-Überlauf in drei Stufen:

  * ``doc``        — ``documentElement.scrollWidth`` vs Fensterbreite
                     (jeder seitliche Überlauf der Seite)
  * ``karten``     — je Karte: ragt sie über ihre Rasterspalte hinaus?
  * ``elemente``   — welches Element ragt am weitesten über den rechten Rand
                     (Name + Breite), damit ein Befund benennbar ist
  * ``avatar``     — liegt der Avatar im Seitenkopf, überlappt er Titel/Badge?

Aufruf im Wegwerf-Stack (eigenes Netz, eigenes Compose-Projekt)::

    docker run --rm --network fix5t905_default -v "$PWD":/w:ro \\
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \\
        mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        sh /w/tools/demo/fix5-lastfall-spielen.sh --marke vorher
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")
GRUPPE = os.environ.get("GRUPPE", "fix5-lastfall-gemeinschaftsteam")

BREITEN = [(344, 812), (390, 844), (1366, 800)]
THEMES = ["light", "dark"]

MARKE = "lastfall"
if "--marke" in sys.argv:
    MARKE = sys.argv[sys.argv.index("--marke") + 1]

fehler: list[str] = []
messungen: list[dict] = []


def anmelden(page):
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(600)
    if page.locator("#dk-usr").count():
        page.fill("#dk-usr", ADMIN)
        page.fill("#dk-pwd", ADMIN_PASS)
        page.keyboard.press("Enter")
    page.wait_for_timeout(3500)
    page.wait_for_load_state("domcontentloaded")


def theme_setzen(page, theme):
    page.evaluate(
        """(t) => {
            const alt = document.documentElement.getAttribute('data-theme')
            const knopf = document.querySelector('[data-dk-theme]')
            if (knopf) knopf.click()
            if (alt !== t) document.documentElement.setAttribute('data-theme', t)
            try { localStorage.setItem('dk-theme', t) } catch (e) {}
        }""",
        theme,
    )
    page.wait_for_timeout(400)
    return page.evaluate("document.documentElement.getAttribute('data-theme')")


def runde(n):
    return None if n is None else round(float(n), 1)


def messe_detail(page):
    return page.evaluate(
        """() => {
            const r = (el) => { const b = el.getBoundingClientRect();
                return {x: b.x, y: b.y, w: b.width, h: b.height, r: b.right, b: b.bottom}; };
            const de = document.documentElement;
            const grid = document.querySelector('.grup-grid');
            if (!grid) return null;
            const spalten = [...grid.querySelectorAll(':scope > .grup-spalte')];
            const voll = [...document.querySelectorAll('.grup-breit')];

            // 1) Welche Elemente ragen über den rechten Fensterrand?
            const fenster = de.clientWidth;
            let ueber = [];
            grid.querySelectorAll('*').forEach((el) => {
                const b = el.getBoundingClientRect();
                const d = b.right - fenster;
                if (d > 0.5) ueber.push({
                    tag: el.tagName.toLowerCase(),
                    cls: (el.className || '').toString().slice(0, 60),
                    text: (el.textContent || '').trim().slice(0, 40),
                    ueber: Math.round(d * 10) / 10,
                    w: Math.round(b.width * 10) / 10,
                });
            });
            ueber.sort((a, b) => b.ueber - a.ueber);

            // 2) Ragen Karten über ihre Spalte hinaus?
            const karten = [];
            spalten.forEach((sp, i) => {
                const sB = r(sp);
                [...sp.querySelectorAll(':scope > .dk-ui-card')].forEach((k) => {
                    const kB = r(k);
                    if (kB.w > sB.w + 0.5 || kB.r > sB.r + 0.5) {
                        karten.push({ spalte: i, titel:
                            (k.querySelector('.dk-ui-card-titel') || {}).textContent || '',
                            breite: Math.round(kB.w * 10) / 10,
                            spalteBreite: Math.round(sB.w * 10) / 10 });
                    }
                });
            });

            // 3) Kartenköpfe (mit / ohne Aktionsknopf)
            const koepfe = [...grid.querySelectorAll('.dk-ui-card-kopf')].map((k) => ({
                text: (k.querySelector('.dk-ui-card-titel') || {}).textContent || '',
                hatAktion: !!k.querySelector('.dk-ui-card-aktionen button'),
                h: r(k).h,
            }));

            // 4) Abstände im Raster
            const kind = (el) => [...el.children];
            let spaltenGap = null;
            if (spalten.length === 2) spaltenGap = r(spalten[1]).x - r(spalten[0]).r;
            const inne = spalten.map((s) => {
                const k = kind(s);
                return k.slice(1).map((el, i) => r(el).y - r(k[i]).b);
            });
            let spalteZuBreit = null;
            if (spalten.length && voll.length) {
                const unten = Math.max(...spalten.map((s) => r(s).b));
                spalteZuBreit = r(voll[0]).y - unten;
            }

            // 5) Avatar im Seitenkopf
            const kopf = document.querySelector('.dk-ui-pageheader');
            const avatar = document.querySelector('.grup-avatar');
            const titel = document.querySelector('.dk-ui-pageheader-titel');
            const badges = document.querySelector('.dk-ui-pageheader-badges');
            let avatarUeberlappt = false, avatarAusserhalb = false, avatarText = null;
            if (kopf && avatar) {
                const a = r(avatar), k = r(kopf);
                avatarAusserhalb = a.b > k.b + 0.5 || a.y < k.y - 0.5 || a.r > k.r + 0.5;
                const schneidet = (el) => {
                    if (!el) return false;
                    const e = r(el);
                    return !(a.r <= e.x || a.x >= e.r || a.b <= e.y || a.y >= e.b);
                };
                avatarUeberlappt = schneidet(titel) || schneidet(badges);
                avatarText = (avatar.textContent || '').trim();
            }

            return {
                docScrollWidth: de.scrollWidth, docClientWidth: de.clientWidth,
                ueberlauf: Math.max(0, de.scrollWidth - de.clientWidth),
                ueber, karten, koepfe, spaltenGap, inne, spalteZuBreit,
                avatarUeberlappt, avatarAusserhalb, avatarText,
                kopfHoehe: kopf ? Math.round(r(kopf).h * 10) / 10 : null,
            };
        }"""
    )


def messe_liste(page):
    return page.evaluate(
        """() => {
            const r = (el) => { const b = el.getBoundingClientRect();
                return {x: b.x, w: b.width, r: b.right}; };
            const de = document.documentElement;
            const raster = [...document.querySelectorAll('.gr-grid-scroll')].map((s) => {
                const sB = r(s);
                const kacheln = [...s.querySelectorAll(':scope > .gr-kachel')].map(r);
                const spalte = (getComputedStyle(s).gridTemplateColumns || '').split(' ')[0];
                const sp = spalte ? Math.round(parseFloat(spalte)) : null;
                return {
                    marke: s.dataset.raster || '',
                    w: Math.round(sB.w), x: Math.round(sB.x),
                    spalte: sp,
                    scrollW: s.scrollWidth, clientW: s.clientWidth,
                    ueberSpalte: kacheln.filter((k) => k.w > (sp || 1e9) + 1).length,
                    breiteste: kacheln.length ? Math.round(Math.max(...kacheln.map((k) => k.w))) : null,
                    kinderAnzahl: kacheln.length,
                };
            });
            return {
                docScrollWidth: de.scrollWidth, docClientWidth: de.clientWidth,
                ueberlauf: Math.max(0, de.scrollWidth - de.clientWidth), raster,
            };
        }"""
    )


with sync_playwright() as p:
    browser = p.chromium.launch()
    for breite, hoehe in BREITEN:
        for theme in THEMES:
            seite = browser.new_page(viewport={"width": breite, "height": hoehe})
            konsole: list[str] = []
            seite.on("console", lambda m: konsole.append(m.text) if m.type == "error" else None)
            anmelden(seite)
            ist = theme_setzen(seite, theme)

            seite.goto(f"{BASE}/#/gruppe/{GRUPPE}", wait_until="domcontentloaded")
            seite.wait_for_timeout(2500)
            seite.wait_for_selector(".grup-grid", timeout=15000)
            daten = messe_detail(seite)
            pfad = os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-gruppendetail.png")
            seite.screenshot(path=pfad, full_page=True)

            eintrag = {"breite": breite, "theme": theme, "istTheme": ist,
                       "detail": daten, "png": pfad}
            if not daten:
                fehler.append(f"{breite}/{theme}: .grup-grid fehlt")
            else:
                if daten["ueberlauf"] > 1:
                    fehler.append(
                        f"{breite}/{theme}: Seite läuft seitlich über "
                        f"({daten['docScrollWidth']} > {daten['docClientWidth']} px, "
                        f"schuld: {daten['ueber'][:2]})")
                if daten["karten"]:
                    fehler.append(f"{breite}/{theme}: Karten breiter als ihre Spalte "
                                  f"{daten['karten']}")
                hoehen = [k["h"] for k in daten["koepfe"]]
                if hoehen:
                    d = max(hoehen) - min(hoehen)
                    eintrag["kopfSpanne"] = runde(d)
                    if d > 0.5:
                        fehler.append(f"{breite}/{theme}: Kartenköpfe unterschiedlich "
                                      f"hoch ({sorted(set(runde(h) for h in hoehen))})")
                werte = [x for reihe in daten["inne"] for x in reihe]
                if daten["spalteZuBreit"] is not None:
                    werte.append(daten["spalteZuBreit"])
                if werte:
                    spanne = max(werte) - min(werte)
                    eintrag["abstandSpanne"] = runde(spanne)
                    if spanne > 1.0:
                        fehler.append(f"{breite}/{theme}: Abstände laufen auseinander "
                                      f"({runde(min(werte))}..{runde(max(werte))} px)")
                if daten["spaltenGap"] is not None:
                    eintrag["spaltenGap"] = runde(daten["spaltenGap"])
                if daten["avatarUeberlappt"]:
                    fehler.append(f"{breite}/{theme}: Avatar überlappt Titel/Status")
                if daten["avatarAusserhalb"]:
                    fehler.append(f"{breite}/{theme}: Avatar ragt aus dem Seitenkopf")

            seite.goto(f"{BASE}/#/gruppen", wait_until="domcontentloaded")
            seite.wait_for_timeout(2000)
            liste = messe_liste(seite)
            pfad2 = os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-gruppenliste.png")
            seite.screenshot(path=pfad2, full_page=True)
            eintrag["liste"] = liste
            eintrag["pngListe"] = pfad2
            if liste["ueberlauf"] > 1:
                fehler.append(f"{breite}/{theme}: Gruppenliste läuft seitlich über "
                              f"({liste['docScrollWidth']} > {liste['docClientWidth']} px)")
            for r in liste["raster"]:
                if r["ueberSpalte"]:
                    fehler.append(f"{breite}/{theme}: {r['ueberSpalte']} Kachel(n) "
                                  f"„{r['marke']}“ breiter als ihre Spalte "
                                  f"({r['breiteste']} px bei {r['spalte']} px)")

            konsole = [k for k in konsole if "404" not in k]
            if konsole:
                fehler.append(f"{breite}/{theme}: Konsolenfehler {konsole[:2]}")
            eintrag["konsole"] = konsole[:5]
            messungen.append(eintrag)
            seite.close()
    browser.close()

with open(os.path.join(ZIEL, f"{MARKE}-lastfall-messung.json"), "w", encoding="utf-8") as fh:
    json.dump({"marke": MARKE, "messungen": messungen, "fehler": fehler},
              fh, ensure_ascii=False, indent=2)

print(json.dumps({"marke": MARKE, "fehler": fehler,
                  "messungen": messungen}, ensure_ascii=False, indent=2))
sys.exit(1 if fehler else 0)
