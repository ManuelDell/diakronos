"""FIX-5 — Gruppen-Detailseite: Abstände, Kartenköpfe, Handy-Überlauf.

Befund DMB-096ae0364b59 (16.10., Route ``#/gruppe/<name>``,
``pages/GruppeDetail.vue``): „Design nicht einheitlich. Gap zwischen den
Kacheln nicht einheitlich." — dazu im Bild unterschiedlich hohe Kartenköpfe
(mit/ohne Knopf) und ein Avatar oben rechts, der über die Kartenkante läuft.
Folgepunkt DEV-1: Die Gruppenkarten (``pages/Gruppen.vue``) laufen am Handy
seitlich über.

Gemessen wird nicht nur ein Bild, sondern der gerenderte Rahmen
(``getBoundingClientRect``):

  * Gruppen-Detail (``#/gruppe/jugendkreis``)
      - ``.grup-grid``           : Abstand zwischen den beiden Spalten
      - ``.grup-spalte > *``     : Abstände INNERHALB einer Spalte und
                                   Abstand der Spalte zum Vollbreiten-Block
                                   (``.grup-breit``) — alle müssen gleich sein
      - ``.dk-ui-card-kopf``     : Höhe der Kartenköpfe der zweispaltigen
                                   Karten (mit und ohne Aktionsknopf)
      - ``.grup-avatar``         : liegt vollständig im Seitenkopf, ohne
                                   Überlappung mit Titel/Badge oder darunter
  * Gruppenliste (``#/gruppen``)
      - ``document.documentElement.scrollWidth`` <= Fensterbreite (kein
        seitlicher Überlauf); zusätzlich die Kacheln selbst.

Je Breite (390, 1366) und Theme (hell, dunkel) entstehen
``<marke>-<breite>-<theme>-<seite>.png``; die Zahlen stehen in
``<marke>-messung.json``.

Aufruf im Wegwerf-Stack (eigenes Compose-Projekt, eigenes Netz)::

    docker run --rm --network fix5t905_default -v "$PWD":/w:ro \\
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \\
        mcr.microsoft.com/playwright/python:v1.49.0-noble \\
        python /w/tools/demo/fix5-gruppendetail.py --marke vorher
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")
GRUPPE = os.environ.get("GRUPPE", "jugendkreis")

BREITEN = [(390, 844), (1366, 800)]
THEMES = ["light", "dark"]

MARKE = "vorher"
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
    """Hell/Dunkel über das Umschalt-Symbol der Seitenleiste."""
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
    """Raster, Spaltenabstände, Kartenköpfe und Avatar."""
    return page.evaluate(
        """() => {
            const r = (el) => { const b = el.getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height, r: b.right, b: b.bottom}; }
            const grid = document.querySelector('.grup-grid')
            if (!grid) return null
            const spalten = [...grid.querySelectorAll(':scope > .grup-spalte')]
            const voll = [...document.querySelectorAll('.grup-breit')]
            const kind = (el) => [...el.children]
            const koepfe = [...document.querySelectorAll('.grup-grid .dk-ui-card .dk-ui-card-kopf')].map((k) => ({
                text: (k.querySelector('.dk-ui-card-titel') || {}).textContent || '',
                hatAktion: !!k.querySelector('.dk-ui-card-aktionen button'),
                h: r(k).h,
            }))
            let spaltenGap = null
            if (spalten.length === 2) spaltenGap = r(spalten[1]).x - r(spalten[0]).r
            const inne = spalten.map((s) => {
                const k = kind(s)
                return k.slice(1).map((el, i) => r(el).y - r(k[i]).b)
            })
            let spalteZuBreit = null
            if (spalten.length && voll.length) {
                const unten = Math.max(...spalten.map((s) => r(s).b))
                spalteZuBreit = r(voll[0]).y - unten
            }
            const kopf = document.querySelector('.dk-ui-pageheader')
            const avatar = document.querySelector('.grup-avatar')
            const titel = document.querySelector('.dk-ui-pageheader-titel')
            const badges = document.querySelector('.dk-ui-pageheader-badges')
            let avatarUeberlappt = false
            let avatarAusserhalb = false
            if (kopf && avatar) {
                const a = r(avatar)
                const k = r(kopf)
                avatarAusserhalb = a.b > k.b + 0.5 || a.y < k.y - 0.5 || a.r > k.r + 0.5
                const schneidet = (el) => {
                    if (!el) return false
                    const e = r(el)
                    return !(a.r <= e.x || a.x >= e.r || a.b <= e.y || a.y >= e.b)
                }
                avatarUeberlappt = schneidet(titel) || schneidet(badges)
            }
            return {spaltenGap, inne, spalteZuBreit, koepfe, avatarUeberlappt, avatarAusserhalb}
        }"""
    )


def messe_liste(page):
    """Seitlicher Überlauf der Gruppenliste.

    Gemessen wird je Raster (``data-raster``) der Rahmen des Streifens und die
    Kacheln darin. Erwartet: keine Kachel ragt über den Streifen hinaus
    (sonst läuft sie am Handy seitlich über die Seite), und die DOKUMENT-
    Breite bleibt die Fensterbreite. Der Streifen selbst darf waagerecht
    scrollen — das ist die gewollte Bedienung.
    """
    return page.evaluate(
        """() => {
            const r = (el) => { const b = el.getBoundingClientRect(); return {x: b.x, w: b.width, r: b.right}; }
            const de = document.documentElement
            const raster = [...document.querySelectorAll('.gr-grid-scroll')].map((s) => {
                const sB = r(s)
                const kacheln = [...s.querySelectorAll(':scope > .gr-kachel')].map(r)
                // FIX-5: Das Raster ordnet spaltenweise (`grid-auto-flow: column`).
                // Gemessen wird je Rasterelement, ob es SEINE Spalte überragt —
                // nur das wäre der Befund „läuft seitlich über“.
                const spalten = getComputedStyle(s).gridAutoColumns
                const spalte = (getComputedStyle(s).gridTemplateColumns || '').split(' ')[0]
                return {
                    marke: s.dataset.raster || '',
                    x: sB.x, w: sB.w, right: sB.r,
                    scrollW: s.scrollWidth, clientW: s.clientWidth,
                    spalten, spalte: spalte ? Math.round(parseFloat(spalte)) : null,
                    ueberSpalte: kacheln.filter((k) => k.w > (parseFloat(spalte) || 1e9) + 1).length,
                    kinderAnzahl: kacheln.length,
                    breiteste: kacheln.length ? Math.max(...kacheln.map((k) => k.w)) : null,
                }
            })
            return {scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, raster}
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

            # ── Gruppen-Detail ────────────────────────────────────────────
            seite.goto(f"{BASE}/#/gruppe/{GRUPPE}", wait_until="domcontentloaded")
            seite.wait_for_timeout(2500)
            seite.wait_for_selector(".grup-grid", timeout=15000)
            daten = messe_detail(seite)
            pfad = os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-gruppendetail.png")
            seite.screenshot(path=pfad, full_page=True)

            eintrag = {"breite": breite, "theme": theme, "istTheme": ist, "detail": daten, "png": pfad}
            if not daten:
                fehler.append(f"{breite}/{theme}: .grup-grid fehlt")
            else:
                werte = [x for reihe in daten["inne"] for x in reihe]
                if daten["spalteZuBreit"] is not None:
                    werte.append(daten["spalteZuBreit"])
                if werte:
                    spanne = max(werte) - min(werte)
                    eintrag["abstandSpanne"] = runde(spanne)
                    if spanne > 1.0:
                        fehler.append(
                            f"{breite}/{theme}: Abstände im Raster laufen auseinander "
                            f"({runde(min(werte))}..{runde(max(werte))} px)"
                        )
                if daten["spaltenGap"] is not None:
                    eintrag["spaltenGap"] = runde(daten["spaltenGap"])
                hoehen = [k["h"] for k in daten["koepfe"]]
                if hoehen:
                    d = max(hoehen) - min(hoehen)
                    eintrag["kopfSpanne"] = runde(d)
                    if d > 0.5:
                        fehler.append(
                            f"{breite}/{theme}: Kartenköpfe unterschiedlich hoch "
                            f"({sorted(set(runde(h) for h in hoehen))})"
                        )
                if daten["avatarUeberlappt"]:
                    fehler.append(f"{breite}/{theme}: Avatar überlappt Titel/Status")
                if daten["avatarAusserhalb"]:
                    fehler.append(f"{breite}/{theme}: Avatar ragt aus dem Seitenkopf")

            # ── Gruppenliste ──────────────────────────────────────────────
            seite.goto(f"{BASE}/#/gruppen", wait_until="domcontentloaded")
            seite.wait_for_timeout(2000)
            liste = messe_liste(seite)
            pfad2 = os.path.join(ZIEL, f"{MARKE}-{breite}-{theme}-gruppenliste.png")
            seite.screenshot(path=pfad2, full_page=True)
            eintrag["liste"] = liste
            eintrag["pngListe"] = pfad2
            if liste["scrollWidth"] > liste["clientWidth"] + 1:
                fehler.append(
                    f"{breite}/{theme}: Gruppenliste läuft seitlich über "
                    f"({liste['scrollWidth']} > {liste['clientWidth']} px)"
                )
            for r in liste["raster"]:
                if r["ueberSpalte"]:
                    fehler.append(
                        f"{breite}/{theme}: {r['ueberSpalte']} Kachel(n) im Raster "
                        f"„{r['marke']}“ sind breiter als ihre Spalte "
                        f"({r['breiteste']} px bei {r['spalte']} px) — sie laufen seitlich über"
                    )
                if r["kinderAnzahl"] and r["scrollW"] <= r["clientW"] and r["breiteste"] and r["breiteste"] > r["w"]:
                    fehler.append(
                        f"{breite}/{theme}: Raster „{r['marke']}“ schiebt die Seite in die Breite "
                        f"(Kachel {r['breiteste']} px bei Streifen {r['w']} px)"
                    )
            # 404 aus Seed-Daten (fehlende Bilder) sind kein Befund dieser Karte.
            konsole = [k for k in konsole if "404" not in k]
            if konsole:
                fehler.append(f"{breite}/{theme}: Konsolenfehler {konsole[:2]}")
            eintrag["konsole"] = konsole[:5]
            messungen.append(eintrag)
            seite.close()
    browser.close()

with open(os.path.join(ZIEL, f"{MARKE}-messung.json"), "w", encoding="utf-8") as fh:
    json.dump({"marke": MARKE, "messungen": messungen, "fehler": fehler}, fh, ensure_ascii=False, indent=2)

print(json.dumps({"marke": MARKE, "fehler": fehler, "messungen": messungen}, ensure_ascii=False, indent=2))
sys.exit(1 if fehler else 0)
