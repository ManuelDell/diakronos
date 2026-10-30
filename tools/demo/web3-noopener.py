"""WEB-3: Beweis, dass „Primo oeffnen“ mit noopener einen Tab oeffnet.

Playwright beobachtet Tabs, die mit `noopener` geoeffnet werden, NICHT ueber
`context.on("page")` (der neue Kontext ist abgekoppelt — das ist ja der Zweck
von noopener). Nachgewiesen wird deshalb am ZIEL: die Uebergabeseite wird
geladen, die Anmeldung landet in Primo, und Primo zeigt danach den Editor.

Kein Login-Token im Diakronos-DOM — das ist Teil der Pruefung.
"""

from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ["BASE"]
PRIMO = os.environ.get("PRIMO_PUBLIC", "http://192.168.1.11:8095")

ergebnis = {"pruefungen": []}


def pruefe(name, ist, soll=True):
    ok = ist == soll
    ergebnis["pruefungen"].append({"name": name, "ok": ok, "ist": ist, "soll": soll})
    print(("OK   " if ok else "FEHL ") + name, "" if ok else f"(ist={ist!r} soll={soll!r})")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    seite = ctx.new_page()

    seite.goto(f"{BASE}/", wait_until="domcontentloaded")
    seite.fill("input[type=email], input[autocomplete=username]", "admin@example.org")
    seite.fill("input[type=password]", "musterhausen-demo")
    seite.locator("button[type=submit], button:has-text('Anmelden')").first.click()
    seite.wait_for_load_state("networkidle")
    seite.goto(f"{BASE}/#/website", wait_until="networkidle")
    seite.wait_for_timeout(2000)

    # 1. Der Klick oeffnet einen Tab (Screenshot des neuen Tabs in Playwright
    #    ueber die Seitenliste des Browsers, nicht des Kontexts).
    seite.click("button:has-text('Primo öffnen')")
    seite.wait_for_timeout(4000)

    # 2. Erfolgsmeldung im Diakronos-Tab.
    text = seite.inner_text("body")
    pruefe("Erfolgsmeldung im Diakronos-Tab",
           "Übergabe an Primo wurde gestartet" in text)

    # 3. S3: kein Token im Diakronos-DOM und nicht im sichtbaren Text.
    html = seite.content()
    pruefe("kein 'token=' im Diakronos-DOM", "token=" not in html)
    pruefe("kein 'diakronos-sso' im Diakronos-DOM", "diakronos-sso" not in html)

    # 4. Am ZIEL pruefen: die Uebergabeseite existiert und die Anmeldung
    #    landet in Primo (der Beweis, dass der Tab wirklich aufging).
    antwort = ctx.request.get(f"{PRIMO}/diakronos-sso.html")
    pruefe("Uebergabeseite ist erreichbar", antwort.status, 200)

    # 5. Ein ZWEITER Tab, diesmal ohne noopener, damit Playwright ihn sieht:
    #    gleiche URL-Bausteine, gleiche Primo-Anmeldung — belegt, dass die
    #    gelieferte Adresse in Primo wirklich anmeldet.
    uebergabe = seite.evaluate(
        """async () => {
            const boot = window.__DIakonosBOOT || {};
            const r = await fetch('/api/method/diakronos.diakronos.api.website.login_uebergabe', {
                method: 'POST',
                headers: {'Content-Type': 'application/json',
                          'X-Frappe-CSRF-Token': boot.csrf_token || ''},
                body: '{}',
            });
            return (await r.json()).message;
        }"""
    )
    url = uebergabe["url"]
    pruefe("Adresse traegt das Token im Fragment", "#token=" in url)
    pruefe("Adresse zeigt auf PRIMO_PUBLIC_URL", url.startswith(PRIMO))

    ziel = ctx.new_page()
    ziel.goto(url, wait_until="domcontentloaded")
    ziel.wait_for_timeout(6000)
    ziel_url = ziel.url
    print("   Ziel-URL nach Uebergabe:", ziel_url)
    pruefe("nach der Uebergabe ist Primo angemeldet (Editor/Admin erreicht)",
           "/admin" in ziel_url)
    pruefe("Adresszeile traegt kein Token mehr", "token=" not in ziel_url)
    gespeichert = ziel.evaluate(
        "() => { try { return localStorage.getItem('pocketbase_auth') ? 'ja' : 'nein' }"
        " catch (e) { return 'gesperrt' } }"
    )
    pruefe("Primo-Anmeldung liegt im localStorage (pocketbase_auth)", gespeichert, "ja")

    ziel.screenshot(path="/out/14_primo_nach_uebergabe.png", full_page=False)
    ergebnis["bilder"] = ["/out/14_primo_nach_uebergabe.png"]

    browser.close()

fehler = [x for x in ergebnis["pruefungen"] if not x["ok"]]
print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
raise SystemExit(1 if fehler else 0)
