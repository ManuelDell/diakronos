"""PLAN-M1 — Belege: Hinweis am Handy („Pläne am Desktop bearbeiten“).

Laeuft im Playwright-Image gegen den Wegwerf-Stack (Projekt
``t_9fc69db4-test``). Aufgenommen wird je Rolle (Planer = admin@example.org,
Betrachter = betrachter@example.org) derselbe Planrahmen-Plan:

  * Planer 390 px  : Hinweis sichtbar (hell + dunkel), nach „Schließen“ weg,
                     nach Reload weiterhin weg (localStorage, je Benutzer).
  * Betrachter 390 : KEIN Hinweis (kein Bearbeitungsrecht).
  * Planer 1366 px : KEIN Hinweis (kein schmaler Bildschirm).

Zusaetzlich die beiden anderen Plan-Rahmen-Seiten (Planvorlage, Stammdaten)
bei 390 px als Planer. Jeder Zustand wird ueber die DOM tatsaechlich geprueft
(Messung in der Seite) — ein reiner Screenshot ohne Pruefung beweist nichts.

Aufruf:
    docker run --rm --network t_9fc69db4-test_default -v "$PWD":/w:ro \
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/plan-m1-screenshots.py
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
PLANER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PLANER_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")
MITGLIED = os.environ.get("MITGLIED_EMAIL", "betrachter@example.org")
MITGLIED_PASS = os.environ.get("MITGLIED_PASS", PLANER_PASS)

HINWEIS = '[data-test="pr-hinweis-handy"]'
ZUSCHLIESSEN = '[data-test="pr-hinweis-handy-schliessen"]'
TEXT = ("Pläne bearbeitest du am besten an einem Desktop oder Tablet im "
        "Querformat. Ansehen geht auch hier.")

fehler: list[str] = []
gemessen: list[dict] = []


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              locale="de-DE", ignore_https_errors=True)
    if dunkel:
        ctx.add_init_script(
            "try { localStorage.setItem('dk-theme', 'dark') } catch (e) {}")
    return ctx


# Bekannter Basis-Befund der Demo: eine optionale Ressource fehlt und der
# Browser meldet sie als Konsolenfehler. Er gehoert nicht zu dieser Karte —
# er wird gezaehlt und ausgewiesen, nicht als Regress gewertet.
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
    page.wait_for_timeout(400)
    page.fill("#dk-usr", email)
    page.fill("#dk-pwd", passwort)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")


def sichtbar(page):
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }""", HINWEIS)


def pruefe(name, lage, erwartet, breite):
    eintrag = {"name": name, "sichtbar": lage, "erwartet": erwartet, "breite": breite}
    gemessen.append(eintrag)
    if lage != erwartet:
        fehler.append(f"{name}: Hinweis sichtbar={lage}, erwartet={erwartet}")


def schuss(page, name, breite):
    datei = os.path.join(ZIEL, f"{name}.png")
    page.screenshot(path=datei, full_page=(breite == 390))
    print("geschrieben", os.path.basename(datei))


def plan_route(page):
    """Ersten Plan der Uebersicht oeffnen (ueber die Liste der Seite)."""
    page.goto(BASE + "/#/planrahmen", wait_until="networkidle")
    page.wait_for_timeout(1500)
    link = page.evaluate(
        """() => {
            const a = document.querySelector('a.pr-ue-zeile[href*="/planrahmen/plan/"]');
            return a ? a.getAttribute('href') : '';
        }""")
    return link or ""


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])

        # ── Planer 390 px, hell ────────────────────────────────────────────
        for dunkel in (False, True):
            marke = "dunkel" if dunkel else "hell"
            ctx = kontext(browser, 390, 844, dunkel)
            page = ctx.new_page()
            sammeln(page, f"planer-390-{marke}")
            anmelden(page, PLANER, PLANER_PASS)
            route = plan_route(page)
            if not route:
                fehler.append("kein Plan in der Uebersicht gefunden")
                return 2
            page.goto(BASE + "/" + route, wait_until="networkidle")
            page.wait_for_timeout(1800)
            lage = sichtbar(page)
            pruefe(f"plan-390-{marke}", lage, True, 390)
            if lage:
                text = page.inner_text(HINWEIS).replace("\n", " ")
                if TEXT.split(".")[0] not in text:
                    fehler.append(f"plan-390-{marke}: Wortlaut abweichend: {text[:120]}")
            schuss(page, f"planer-plan-390-{marke}", 390)

            if not dunkel:
                # Schliessen -> weg, und nach Reload weiterhin weg.
                page.click(ZUSCHLIESSEN)
                page.wait_for_timeout(500)
                pruefe("plan-390-geschlossen", sichtbar(page), False, 390)
                schuss(page, "planer-plan-390-geschlossen", 390)
                page.reload(wait_until="networkidle")
                page.wait_for_timeout(1500)
                pruefe("plan-390-nach-reload", sichtbar(page), False, 390)
                schluessel = page.evaluate(
                    "Object.keys(localStorage).filter(k => k.startsWith('pr-handy-hinweis:'))")
                print("gemerkt:", json.dumps(schluessel))
                if not schluessel:
                    fehler.append("Schliessen wurde nicht gemerkt (kein localStorage-Eintrag)")
                # Ansehen bleibt moeglich: die Seite selbst ist vollstaendig da.
                inhalt = page.evaluate("!!document.querySelector('.dk-screen-title')")
                if not inhalt:
                    fehler.append("nach dem Schliessen fehlt der Seiteninhalt")

                # Die anderen beiden Plan-Rahmen-Seiten (Planer, 390 px).
                # Erst OHNE Merkung (Hinweis muss kommen), dann MIT der
                # Merkung aus dem Plan (der Zustand gilt je Benutzer ueber
                # alle drei Seiten).
                for name, pfad in (("planvorlage", "#/planrahmen/einrichten/chorplan"),
                                   ("stammdaten", "#/planrahmen/stammdaten/chorplan")):
                    page.evaluate("() => localStorage.clear()")
                    page.goto(BASE + "/" + pfad, wait_until="networkidle")
                    page.wait_for_timeout(1800)
                    pruefe(f"{name}-390", sichtbar(page), True, 390)
                    schuss(page, f"planer-{name}-390", 390)
                    # Merkung setzen wie am Plan und erneut laden.
                    page.evaluate("""() => {
                        const bis = Date.now() + 30 * 24 * 60 * 60 * 1000;
                        localStorage.setItem('pr-handy-hinweis:' + (window.__DIakonosBOOT?.user_email || 'anon'),
                                             JSON.stringify({ bis }));
                    }""")
                    page.reload(wait_until="networkidle")
                    page.wait_for_timeout(1500)
                    pruefe(f"{name}-390-gemerkt", sichtbar(page), False, 390)
            ctx.close()

        # ── Betrachter 390 px: nie ein Hinweis ─────────────────────────────
        ctx = kontext(browser, 390, 844)
        page = ctx.new_page()
        sammeln(page, "betrachter-390")
        anmelden(page, MITGLIED, MITGLIED_PASS)
        page.goto(BASE + "/" + route, wait_until="networkidle")
        page.wait_for_timeout(1800)
        pruefe("betrachter-plan-390", sichtbar(page), False, 390)
        schuss(page, "betrachter-plan-390", 390)
        ctx.close()

        # ── Planer 1366 px: kein Hinweis (kein schmaler Bildschirm) ────────
        ctx = kontext(browser, 1366, 800)
        page = ctx.new_page()
        sammeln(page, "planer-1366")
        anmelden(page, PLANER, PLANER_PASS)
        page.goto(BASE + "/" + route, wait_until="networkidle")
        page.wait_for_timeout(1800)
        pruefe("planer-plan-1366", sichtbar(page), False, 1366)
        schuss(page, "planer-plan-1366", 1366)
        ctx.close()

        browser.close()

    with open(os.path.join(ZIEL, "messung.json"), "w", encoding="utf-8") as f:
        json.dump({"messungen": gemessen, "fehler": sorted(set(fehler)),
                   "bekannte_konsolen_404": sorted(set(bekannt))}, f,
                  ensure_ascii=False, indent=2)
    if fehler:
        print("BEFUNDE:", file=sys.stderr)
        for f_ in sorted(set(fehler)):
            print(" -", f_, file=sys.stderr)
        return 1
    print("alle Pruefungen bestanden:", len(gemessen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
