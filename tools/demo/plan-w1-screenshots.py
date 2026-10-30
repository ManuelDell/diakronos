"""PLAN-W1 — Screenshots: Warnungen im Plan nur fuer Planer, einklappbar.

Laeuft im Playwright-Image gegen den Wegwerf-Stack (Projekt ``plan-w1``).
Aufgenommen wird je Rolle (Planer = admin@example.org, Betrachter = das
Mitgliedskonto) derselbe veroeffentlichte Planrahmen-Plan, Desktop 1366x800
und Mobil 390x844, hell und (Planer) dunkel:

  * betrachter-*: KEIN Warnblock, keine Zeilen-Warnungen.
  * planer-*: Warnblock sichtbar; danach eingeklappt (Zustand im localStorage
    je Benutzer) und nach einem Reload immer noch eingeklappt.

Aufruf (aus dem Worktree):

    docker run --rm --network plan-w1_default -v "$PWD":/w:ro \
        -v <ziel>:/ausgabe -e BASE=http://app:8000 -e ZIEL=/ausgabe \
        -e ADMIN_PASS=... -e MITGLIED_PASS=... \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/plan-w1-screenshots.py
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
PLANER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PLANER_PASS = os.environ["ADMIN_PASS"]
MITGLIED = os.environ.get("MITGLIED_EMAIL", "betrachter@example.org")
MITGLIED_PASS = os.environ.get("MITGLIED_PASS", PLANER_PASS)

fehler: list[str] = []


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              locale="de-DE", ignore_https_errors=True)
    if dunkel:
        ctx.add_init_script(
            "try { localStorage.setItem('dk-theme', 'dark') } catch (e) {}")
    return ctx


def sammeln(page, name):
    def bei(msg):
        if msg.type == "error":
            fehler.append(f"{name}: {msg.text}")
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


def api(page, methode, daten=None, csrf=""):
    """Whitelist-Aufruf mit dem CSRF-Token der Sitzung (kein Cookie, nur Header)."""
    treffer = page.evaluate(
        """async ([methode, daten, csrf]) => {
            const r = await fetch('/api/method/diakronos.planrahmen.api.' + methode, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf},
                body: JSON.stringify(daten || {})});
            return [r.status, await r.text()];
        }""", [methode, daten or {}, csrf])
    return treffer[0], treffer[1]


def csrf_holen(page):
    """CSRF-Token der Sitzung aus dem Boot-Objekt (die SPA nutzt denselben Weg)."""
    token = page.evaluate("window.__DIakonosBOOT?.csrf_token || ''")
    if not token:
        fehler.append("CSRF-Token fehlt im Boot-Objekt")
    return token


def plan_waehlen(page):
    """Ersten veroeffentlichten Planrahmen-Plan oeffnen, der Warnungen traegt.

    Der Planer-Sichtbarkeitscheck laeuft ueber die API (Datenstrom mit
    `meldungen`) — dadurch ist der Screenshot nicht vom Zufall der
    Reihenfolge abhaengig.
    """
    csrf = csrf_holen(page)
    stand, txt = api(page, "plaene_liste", csrf=csrf)
    if stand != 200:
        fehler.append(f"plaene_liste {stand}: {txt[:120]}")
        return None
    plaene = json.loads(txt).get("message") or []
    ids = [p.get("id") for p in plaene if isinstance(p, dict) and p.get("status") == "veroeffentlicht"]
    ids = ids or [p.get("id") for p in plaene if isinstance(p, dict)]
    for pid in ids:
        stand, txt = api(page, "plan_holen", {"plan": pid}, csrf)
        if stand != 200:
            continue
        msg = json.loads(txt).get("message") or {}
        if any(e.get("meldungen") for e in (msg.get("eintraege") or [])):
            print("Plan mit Pruef-Meldungen:", pid)
            return pid
    return ids[0] if ids else None


def schuss(page, name, route, breite):
    page.goto(BASE + "/" + route, wait_until="networkidle")
    page.wait_for_timeout(1500)
    datei = os.path.join(ZIEL, f"{name}.png")
    page.screenshot(path=datei, full_page=(breite == 390))
    print("geschrieben", os.path.basename(datei))


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])

        for breite, hoehe, mobil in ((1366, 800, False), (390, 844, True)):
            # ── Planer: Block sichtbar, einklappbar, Zustand gemerkt ────────
            ctx = kontext(browser, breite, hoehe)
            page = ctx.new_page()
            sammeln(page, f"planer-{breite}")
            anmelden(page, PLANER, PLANER_PASS)
            pid = plan_waehlen(page)
            if not pid:
                print("kein Plan gefunden", file=sys.stderr)
                return 2
            route = f"#/planrahmen/plan/{pid}"
            schuss(page, f"planer-offen-{breite}", route, breite)
            block = page.locator("details.pr-meldungen-uebersicht")
            if not block.count():
                fehler.append(f"planer-{breite}: Warnblock fehlt (Planer ohne Pruef-Meldungen)")
            else:
                # Einklappen ueber den Kopf des Blocks.
                block.first.locator("summary.pr-meldungen-kopf").click()
                page.wait_for_timeout(700)
                schuss(page, f"planer-eingeklappt-{breite}", route, breite)
                page.reload(wait_until="networkidle")
                page.wait_for_timeout(1200)
                offen = page.evaluate(
                    "document.querySelector('details.pr-meldungen-uebersicht')?.open ?? null")
                if offen is not False:
                    fehler.append(f"planer-{breite}: Einklapp-Zustand nach Reload nicht gemerkt")
                schuss(page, f"planer-nach-reload-eingeklappt-{breite}", route, breite)
                schluessel = page.evaluate(
                    "Object.keys(localStorage).filter(k => k.startsWith('pr-warnblock:'))")
                print("gemerkt:", json.dumps(schluessel))
            ctx.close()

            # ── Betrachter: nie Warnungen ──────────────────────────────────
            ctx = kontext(browser, breite, hoehe)
            page = ctx.new_page()
            sammeln(page, f"betrachter-{breite}")
            anmelden(page, MITGLIED, MITGLIED_PASS)
            schuss(page, f"betrachter-{breite}", route, breite)
            hat = page.evaluate(
                "!!document.querySelector('details.pr-meldungen-uebersicht, .pr-meldungen-inter')")
            if hat:
                fehler.append(f"betrachter-{breite}: Warnblock sichtbar")
            ctx.close()

        # ── Dunkelmodus (Planer, Desktop) ────────────────────────────────
        ctx = kontext(browser, 1366, 800, dunkel=True)
        page = ctx.new_page()
        sammeln(page, "planer-dunkel")
        anmelden(page, PLANER, PLANER_PASS)
        schuss(page, "planer-dunkel-1366", route, 1366)
        ctx.close()
        browser.close()

    if fehler:
        print("BEFUNDE:", file=sys.stderr)
        for f in sorted(set(fehler)):
            print(" -", f, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
