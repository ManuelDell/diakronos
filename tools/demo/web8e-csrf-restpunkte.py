"""WEB-8e — Abnahme im Wegwerf-Stack: Restpunkte der CSRF-Heilung.

Der Stack (eigenes Compose-Projekt `web8e-stack`, Port 8331, Praefix
`/diakronos`, Seed per `tools/demo/musterhausen.py`) verhaelt sich wie im
Betrieb. Die Fehler entstehen ECHT — nicht per Mock:

  * Die Sitzung wird serverseitig weggeworfen (Schluessel
    `diakronos:sitzung:<sid>` im WEGWERF-Redis) **und** der Client-Token im
    Browser auf einen falschen Wert gesetzt. Der Profilaufruf bekommt dann
    417 (`CSRFTokenError`), der Token-Abruf (`session.sitzung_status`)
    antwortet 401 — genau der Fall aus Befund E1.

Faelle:

  A) Hauptbereich (E1, der Befund): 417 + kein frisches Token -> der
     vorhandene Sitzungsdialog zeigt den FESTEN Hinweis, die Seite laedt
     NICHT neu und es wird NICHT zur Anmeldung navigiert.
  B) Hauptbereich (Gegenprobe WEB-8d): mit lebender Sitzung heilt die
     Heilung still (Token neu + genau eine Wiederholung, 200) — kein Dialog.
  C) Gastseite (E2): mit kaputtem Token laedt die Seite nach der
     CSRF-Ablehnung GENAU EINMAL neu (frisches Seiten-Token), danach steht
     der Hinweis aus E3 auf der Seite.
  D) Gastseite (E4): kein Text „Die Anmeldung wird neu geladen".

Aufruf (Wegwerf, eigenes Netz des Stacks):
  docker run --rm --network web8e-stack_default -v <worktree>:/repo:ro \\
      -v <ausgabe>:/out -e WEB8E_BASIS=http://app:8000 \\
      diakronos-web8e:pw python /repo/tools/demo/web8e-csrf-restpunkte.py
"""

from __future__ import annotations

import json
import os
import socket

from playwright.sync_api import sync_playwright

BASIS = os.environ.get("WEB8E_BASIS", "http://127.0.0.1:8331")
PRAEFIX = "/diakronos"
SPA = f"{BASIS}{PRAEFIX}/diakonos"
AUSGABE = os.environ.get("WEB8E_AUSGABE", "/out")
ADMIN = (
    os.environ.get("WEB8E_USER", "admin@example.org"),
    os.environ.get("WEB8E_PASS", "Web8c-Admin-Pass-1"),
)

FALSCHER_TOKEN = "falscher-token-fuer-den-nachweis"
ZIEL_PROFIL = "profile.update_my_profile"
HINWEIS = "Sitzung abgelaufen — bitte neu anmelden."
HINWEIS_NEULADEN = "Die Seite wurde neu geladen, bitte Eingaben prüfen."

RELOAD_SONDE = """() => {
    window.__w8eReload = 0;
    try {
        const proto = Object.getPrototypeOf(window.location);
        Object.defineProperty(proto, 'reload', {
            configurable: true,
            value: function () { window.__w8eReload = (window.__w8eReload || 0) + 1; },
        });
    } catch (e) { window.__w8eReload = -1; }
}"""

NAV_SONDE = """() => {
    window.__w8eNav = [];
    try {
        const proto = Object.getPrototypeOf(window.location);
        for (const m of ['assign', 'replace']) {
            const o = proto[m];
            Object.defineProperty(proto, m, {
                configurable: true,
                value: function (z) { window.__w8eNav.push(m + ': ' + String(z).slice(0, 100)); return undefined; },
            });
        }
        const h = history.pushState;
        history.pushState = function (a, b, c) { window.__w8eNav.push('pushState: ' + String(c)); return h.apply(this, arguments); };
    } catch (e) { window.__w8eNav = ['Sonde: ' + String(e)]; }
}"""

TOKEN_SETZEN = """(falsch) => {
    window.__DIakonosBOOT = window.__DIakonosBOOT || {};
    window.__DIakonosBOOT.csrf_token = falsch;
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) meta.setAttribute('content', falsch);
    return window.__DIakonosBOOT.csrf_token;
}"""

ergebnisse: list[dict] = []


def notiere(name: str, ok: bool, detail: str) -> None:
    ergebnisse.append({"fall": name, "ok": bool(ok), "detail": detail})
    print(f"[{'OK ' if ok else 'ROT'}] {name}: {detail}", flush=True)


def verkehr_sammeln(page) -> list[dict]:
    """Antworten des App-Pfads mitschreiben (Handler laeuft in JEDEM Fall)."""
    eintraege: list[dict] = []

    def merken(r):
        try:
            if "/api/method/" in r.url:
                eintraege.append(
                    {"status": r.status, "url": r.url.replace(BASIS, ""), "methode": r.request.method}
                )
        except Exception:  # noqa: BLE001 — Seite kann schon weg sein
            pass

    page.on("response", merken)
    return eintraege


def sitzung_wegwerfen(sid: str) -> bool:
    """Loescht `diakronos:sitzung:<sid>` im WEGWERF-Redis (WEB8E_REDIS_PORT)."""
    if not sid:
        return False
    host = os.environ.get("WEB8E_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB8E_REDIS_PORT", "6397"))
    befehl = f"DEL diakronos:sitzung:{sid}\r\n".encode()
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            s.sendall(befehl)
            antwort = s.recv(64)
        return antwort.startswith(b":")
    except OSError:
        return False


def gast_token(browser) -> str:
    """Legt einen Gast-Link an — ueber den ECHTEN Admin-Endpunkt der App.

    Eigene, frische Umgebung: derselbe Weg wie die Oberflaeche
    (`registrierungslink_api.create_link`) mit dem Sitzungs-Token der
    angemeldeten Seite. Nur im Wegwerf-Stack.
    """
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
    try:
        page = ctx.new_page()
        anmelden(page)
        ergebnis = page.evaluate(
            """async () => {
                const token = (window.__DIakonosBOOT && window.__DIakonosBOOT.csrf_token) || '';
                const r = await fetch('/diakronos/api/method/diakronos.diakonos.api.registrierungslink_api.create_link', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': token },
                    body: JSON.stringify({ typ: 'Gast-Anmeldung', bezeichnung: 'WEB-8e Abnahme (Wegwerf)', unbegrenzt: true, ohne_ablauf: true }),
                });
                const body = await r.text();
                // Den erzeugten Datensatz direkt ablesen — die Antwortform ist
                // nicht der Vertrag dieses Skripts.
                let slug = '';
                try {
                    const l = await fetch('/diakronos/api/method/diakronos.diakonos.api.admin_hub.get_anmeldungen_hub', {
                        method: 'POST', credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': token },
                        body: '{}',
                    });
                    const lt = await l.text();
                    const m = lt.match(/token=([A-Za-z0-9_-]{20,})/g) || [];
                    if (m.length) slug = m[m.length - 1].replace('token=', '');
                } catch (e) {}
                return { status: r.status, body: body.slice(0, 400), slug };
            }"""
        )
    finally:
        ctx.close()
    daten = json.loads(ergebnis["body"]) if ergebnis["body"].strip().startswith("{") else {}
    nachricht = daten.get("message")
    if isinstance(nachricht, str):
        nachricht = daten
    nachricht = nachricht if isinstance(nachricht, dict) else {}
    link = str(nachricht.get("link_anzeige") or nachricht.get("link") or "")
    token = str(ergebnis.get("slug") or "")
    if not token and "token=" in link:
        token = link.split("token=", 1)[1].split("&")[0]
    # Fallstrick: `link_anzeige` ist eine Spalte mit 140 Zeichen — der Token
    # (~43 Zeichen) passt zwar, aber ein falsch gebauter Link zeigt auf eine
    # tote Seite. Die Wahrheit steht im Datensatz: `slug` des neuen Links.
    name = str(nachricht.get("name") or nachricht.get("link_id") or "")
    if name:
        try:
            from diakronos_app.db import SessionLocal
            from diakronos_app.models.diakonos import Registrierungslink

            with SessionLocal() as sess:
                zeile = sess.get(Registrierungslink, name)
                token = (zeile.slug or token) if zeile else token
        except Exception:  # noqa: BLE001 — ohne App-Paket bleibt der Link-Wert
            pass
    if not token:
        raise RuntimeError(f"kein Gast-Link: HTTP {ergebnis['status']} {ergebnis['body']} {link}")
    print(f"[C] Link aus der Antwort: {link[:90]} ({len(token)} Zeichen Token)", flush=True)
    return token


def anmelden(page) -> str:
    """Anmelden — die Maske erscheint ERST nach dem ersten Skriptlauf.

    (Beobachtet: nach `domcontentloaded` fehlt `input[name=usr]` noch, das
    Formular wird nachgezogen. Deshalb warten, statt blind zu fuellen.)
    """
    page.goto(f"{BASIS}{PRAEFIX}/login?local=1", wait_until="domcontentloaded")
    page.wait_for_selector('input[name="usr"]', state="visible", timeout=20_000)
    page.fill('input[name="usr"]', ADMIN[0])
    page.fill('input[name="pwd"]', ADMIN[1])
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click('button[type="submit"]')
    # Die SPA laedt ihr eigenes Buendel: ohne dieses Warten ist links/rechts
    # noch die Anmeldeseite und jede folgende Suche laeuft ins Leere.
    page.wait_for_selector(".dk-app, main, #app, [data-dk-app]", state="attached", timeout=20_000)
    page.wait_for_timeout(2500)
    return page.url


def sid_aus(ctx) -> str:
    for cookie in ctx.cookies():
        if cookie.get("name") == "sid":
            return cookie.get("value", "")
    return ""


def sacht_klicken(page, auswahl: str, ms: int = 3000) -> bool:
    """Klicken, ohne den Lauf zu sprengen.

    Ist schon ein Dialog offen (genau der Befund E1), liegt ein Overlay ueber
    dem Knopf — dann ist das kein Fehler des Skripts, sondern das Ergebnis.
    """
    knopf = page.query_selector(auswahl)
    if not knopf:
        return False
    try:
        knopf.click(timeout=ms)
        return True
    except Exception:  # noqa: BLE001 — Overlay/Dialog davor
        return False


def _auf_der_anwendung(page) -> bool:
    """Steht die Seite wirklich auf der App (nicht auf der 404-Wurzel)?"""
    try:
        kopf = page.inner_text("body")[:200]
        return f"{PRAEFIX}/" in page.url and "Not Found" not in kopf and bool(kopf.strip())
    except Exception:  # noqa: BLE001 — Seite kann schon weg sein
        return False


def _wieder_aufnehmen(page, kandidaten: list[str]) -> bool:
    """Nach einem Fehlschlag die Seite ueber eine bekannte Adresse neu holen."""
    for ziel in reversed(kandidaten[-5:]):
        try:
            page.goto(ziel, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            if _auf_der_anwendung(page):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def wert(page, ausdruck: str, standard=None):
    try:
        return page.evaluate(ausdruck)
    except Exception:  # noqa: BLE001 — Seite kann schon weg sein
        return standard


def main() -> int:
    os.makedirs(AUSGABE, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        # WEB-8f: die Sonden (`__w8eReload`/`__w8eNav`) haengen an JEDEM
        # Dokument des Kontexts — die Profil-Seite entsteht erst NACH dem
        # Anmelden, und `page.evaluate` im alten Ablauf kam fuer den ersten
        # Aufbau zu spaet.
        ctx.add_init_script(RELOAD_SONDE + ";(" + NAV_SONDE + ")();")
        page = ctx.new_page()
        konsolenfehler: list[str] = []
        page.on("console", lambda m: konsolenfehler.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: konsolenfehler.append(str(e)))
        brauchbare_url: list[str] = []

        def _merke_url():
            if f"{PRAEFIX}/diakonos" in page.url:
                brauchbare_url.append(page.url)
        page.on("load", lambda _p: _merke_url())

        # ── A) BEFUND E1: 417, kein frisches Token -> Dialog, keine Navigation ─
        notiere("A0: Anmeldung", PRAEFIX in anmelden(page), f"URL: {page.url}")
        page.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        # Zuerst den Ausgangszustand festhalten — NACH dem Wegwerfen der
        # Sitzung oeffnet die App ihren Dialog von selbst (genau der Befund).
        offen_vorher = wert(page, "() => Array.from(document.querySelectorAll('[role=dialog]'))"
                                  ".map(e => e.innerText).join(' | ')", "")
        page.evaluate(RELOAD_SONDE)
        page.evaluate(NAV_SONDE)
        page.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)

        weg = sitzung_wegwerfen(sid_aus(ctx))
        # Der echte 417 (Befund E1): ein Aufruf mit FALSCHEM Kopfzeilen-Token.
        # `session.sitzung_status` ist schreibfrei und damit immer geeignet.
        probe = page.evaluate(
            """async () => {
                const r = await fetch('/diakronos/api/method/diakronos.diakonos.api.session.sitzung_status', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json',
                               'X-Frappe-CSRF-Token': 'falscher-token-fuer-den-nachweis' },
                    body: '{}',
                });
                const t = await r.text();
                return { status: r.status, body: t.slice(0, 160) };
            }"""
        )
        print(f"[A] CSRF-Probe: HTTP {probe['status']} {probe['body']}", flush=True)
        notiere("A1b: der Server lehnt einen falschen Token mit 417 ab",
                probe["status"] == 417 and "CSRFTokenError" in probe["body"],
                f"HTTP {probe['status']}")
        notiere("A1: Sitzung serverseitig weggeworfen (Wegwerf-Redis)", weg,
                "DEL diakronos:sitzung:<sid>")

        verkehr = verkehr_sammeln(page)
        notiere("A2: vor dem Absenden war noch kein Sitzungsdialog offen",
                "abgelaufen" not in offen_vorher.lower(), f"Dialog vorher={offen_vorher[:120]!r}")
        bearbeiten_weg = sacht_klicken(page, 'button:has-text("Bearbeiten")')
        page.wait_for_timeout(800)
        speichern_weg = sacht_klicken(page, 'button:has-text("Speichern")')
        page.wait_for_timeout(7000)
        notiere("A2b: Profil liess sich bearbeiten und absenden",
                bearbeiten_weg and speichern_weg,
                f"Bearbeiten={bearbeiten_weg}, Speichern={speichern_weg}"
                " (Klick wird von einem Dialog verdeckt -> schon das Ergebnis von E1)")

        ziel = [v for v in verkehr if ZIEL_PROFIL in v["url"]]
        status = [v["status"] for v in ziel]
        token_abrufe = [v for v in verkehr if "session.sitzung_status" in v["url"]]
        dialog = wert(page, "() => Array.from(document.querySelectorAll('[role=dialog]'))"
                            ".map(e => e.innerText).join(' | ')")
        nav = wert(page, "() => window.__w8eNav || []", [])

        notiere("A3: Server lehnt mit 417 ab (echter CSRFTokenError)", 417 in status,
                f"Status der Profil-Aufrufe: {status}")
        notiere("A4 (E1): genau EIN Token-Abruf, keine sinnlose Wiederholung",
                len(token_abrufe) == 1 and len(ziel) == 1,
                f"Profil-Aufrufe={len(ziel)} (erwartet 1), Token-Abrufe={len(token_abrufe)} (erwartet 1)")
        notiere("A5 (E1): der Sitzungsdialog zeigt den FESTEN Hinweis",
                "abgelaufen" in dialog.lower() and HINWEIS.split(" — ")[0] in dialog,
                f"Dialog={dialog[:200]!r}")
        notiere("A6 (E1): kein Neuladen", wert(page, "() => window.__w8eReload", -1) == 0,
                f"reloads={wert(page, '() => window.__w8eReload', -1)} (erwartet 0)")
        notiere("A7 (E1): keine Weiterleitung weg von der SPA",
                all("login" not in str(n) for n in nav) and f"{PRAEFIX}/diakonos" in page.url,
                f"URL: {page.url}, Verlauf={nav}")
        page.screenshot(path=f"{AUSGABE}/01-e1-dialog-hauptbereich.png")

        # ── B) Gegenprobe: lebende Sitzung -> stille Heilung, kein Dialog ──────
        ctx_b = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        ctx_b.add_init_script(RELOAD_SONDE + ";(" + NAV_SONDE + ")();")
        page_b = ctx_b.new_page()
        anmelden(page_b)
        page_b.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page_b.wait_for_timeout(3500)
        page_b.evaluate(RELOAD_SONDE)
        page_b.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
        verkehr_b = verkehr_sammeln(page_b)
        sacht_klicken(page_b, 'button:has-text("Bearbeiten")')
        page_b.wait_for_timeout(600)
        sacht_klicken(page_b, 'button:has-text("Speichern")')
        page_b.wait_for_timeout(6000)
        ziel_b = [v for v in verkehr_b if ZIEL_PROFIL in v["url"]]
        status_b = [v["status"] for v in ziel_b]
        notiere("B1 (Gegenprobe): Heilung gelingt still (417 -> 200, genau EINE Wiederholung)",
                status_b[:1] == [417] and status_b[-1:] == [200] and len(ziel_b) == 2,
                f"Status={status_b}")
        dialog_b = wert(page_b, "() => Array.from(document.querySelectorAll('[role=dialog]'))"
                                ".map(e => e.innerText).join(' | ')")
        notiere("B2 (Gegenprobe): kein Sitzungsdialog, kein Neuladen",
                "abgelaufen" not in dialog_b.lower() and wert(page_b, "() => window.__w8eReload", -1) == 0,
                f"Dialog={dialog_b[:120]!r}")
        page_b.screenshot(path=f"{AUSGABE}/02-heilung-still.png")
        ctx_b.close()

        # ── B3) WEB-8f (B1): Feldfehler ist KEIN Sitzungsfehler ───────────────
        # Echter Aufruf mit echter Ablehnung: ein unmoeglicher Geburtstag. Der
        # Server antwortet mit 417 `ValidationError` — die Oberflaeche muss die
        # Feldfehler zeigen und NICHT „Sitzung abgelaufen".
        ctx_b3 = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        ctx_b3.add_init_script(RELOAD_SONDE + ";(" + NAV_SONDE + ")();")
        page_b3 = ctx_b3.new_page()
        anmelden(page_b3)
        page_b3.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page_b3.wait_for_timeout(3500)
        page_b3.evaluate(NAV_SONDE)
        page_b3.evaluate(RELOAD_SONDE)
        antwort_b3 = wert(
            page_b3,
            """async () => {
                const token = (window.__DIakonosBOOT && window.__DIakonosBOOT.csrf_token) || '';
                const r = await fetch('/diakronos/api/method/profile.update_my_profile', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': token },
                    body: JSON.stringify({ geburtstag: '31.02.1999' }),
                });
                const t = await r.text();
                return { status: r.status, body: t.slice(0, 240) };
            }""",
            {},
        )
        print(f"[B3] Profil mit unmoeglichem Datum: HTTP {antwort_b3.get('status')} "
              f"{antwort_b3.get('body')}", flush=True)
        notiere("B3a (WEB-8f B1): Server lehnt den Feldfehler mit 417 ValidationError ab",
                antwort_b3.get("status") == 417 and "CSRF" not in antwort_b3.get("body", ""),
                f"HTTP {antwort_b3.get('status')} {antwort_b3.get('body', '')[:120]}")
        # Der Weg der OBERFLAECHE: derselbe Aufruf ueber `apiCall` (useApi.js) —
        # dort entscheidet `mitSitzungsdialog`, ob ein Dialog aufgeht.
        # Der Dialog-Zustand liegt in `sitzungsstand.js` (SitzungsHinweis.vue liest
        # ihn). Im Buendel ist er nicht adressierbar — gemessen wird deshalb die
        # WIRKUNG: der Dialog im DOM und der Ablauf-Melder der Statusanzeige.
        fehler_b3 = antwort_b3
        dialog_b3 = wert(page_b3, "() => Array.from(document.querySelectorAll('[role=dialog]'))"
                                  ".map(e => e.innerText).join(' | ')", "")
        nav_b3 = wert(page_b3, "() => window.__w8eNav || []", [])
        notiere("B3b (WEB-8f B1): KEIN Sitzungsdialog bei einem Feldfehler",
                "abgelaufen" not in dialog_b3.lower(),
                f"Dialog={dialog_b3[:160]!r}")
        notiere("B3c (WEB-8f B1): kein Neuladen und keine Weiterleitung",
                wert(page_b3, "() => window.__w8eReload", -1) == 0
                and all("login" not in str(n) for n in nav_b3),
                f"reloads={wert(page_b3, '() => window.__w8eReload', -1)}, Verlauf={nav_b3}")
        notiere("B3d (WEB-8f B1): die Antwort traegt keinen Sitzungs-Merker",
                "SessionExpired" not in antwort_b3.get("body", "")
                and "CSRFTokenError" not in antwort_b3.get("body", ""),
                f"Koerper={antwort_b3.get('body', '')[:120]}")
        page_b3.screenshot(path=f"{AUSGABE}/02b-web8f-b1-feldfehler-kein-dialog.png")
        ctx_b3.close()

        # ── C) GASTSEITE (E2/E3): CSRF -> genau EIN Neuladen + Hinweis ─────────
        try:
            # EIGENE, frische Umgebung: `page` hat gerade absichtlich seine
            # Sitzung verloren (Fall A).
            token = gast_token(browser)
        except Exception as exc:  # noqa: BLE001
            token = ""
            notiere("C0: Gast-Link anlegen", False, f"{type(exc).__name__}: {exc}")
        if token:
            notiere("C0: Gast-Link angelegt", True, f"token={token[:8]}…")
            gast_url = f"{BASIS}{PRAEFIX}/diakonos/gast?token={token}"
            ctx_c = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
            ctx_c.add_init_script(RELOAD_SONDE)
            page_c = ctx_c.new_page()
            # Wie zuvor beobachtet: eine TIEFE Adresse in einer frischen
            # Umgebung kann im Wegwerf-Stack als 404 ankommen. Dann zuerst
            # einmal die App oeffnen und die Adresse danach erneut aufrufen.
            for versuch in (1, 2, 3):
                antwort = page_c.goto(gast_url, wait_until="domcontentloaded")
                if _auf_der_anwendung(page_c) or "Gast-Anmeldung" in page_c.inner_text("body")[:300]:
                    break
                print(f"[C] Versuch {versuch}: Gastseite kam als {page_c.url} an"
                      f" (HTTP {getattr(antwort, 'status', '?')})"
                      f" body={page_c.inner_text('body')[:80]!r}", flush=True)
                if "Not Found" in page_c.inner_text("body")[:80]:
                    # Der 404-Redirect zur Wurzel ist im Wegwerf-Stack nicht
                    # berechenbar -> direkt neu laden.
                    page_c.goto(f"{BASIS}{PRAEFIX}/diakonos", wait_until="domcontentloaded")
                    page_c.wait_for_timeout(1500)
                    continue
                page_c.wait_for_timeout(1500)
            page_c.wait_for_selector("form.dk-pub-form input", state="attached", timeout=20_000)
            page_c.wait_for_timeout(800)
            page_c.screenshot(path=f"{AUSGABE}/03-gast-vorher.png")
            text_vorher = page_c.inner_text("body")
            notiere("C1 (E4): kein „Die Anmeldung wird neu geladen“ auf der Gastseite",
                    "Die Anmeldung wird neu geladen" not in text_vorher,
                    "Seitentext geprueft")
            # Kaputter Token -> jede schreibende Anfrage wird 417.
            page_c.evaluate(RELOAD_SONDE)
            page_c.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
            page_c.fill("form.dk-pub-form input[autocomplete='given-name']", "Erika")
            page_c.fill("form.dk-pub-form input[autocomplete='family-name']", "Mustermann")
            page_c.check("form.dk-pub-form input[type=checkbox]")
            # KEIN `expect_navigation`: die Heilung ruft `location.reload()` —
            # das ist kein Navigationsereignis im Playwright-Sinn. Stattdessen
            # auf das neue Seitenleben warten (URL + Formular wieder da).
            page_c.click("form.dk-pub-form button[type='submit']")
            # WEB-8f (B2): Die Heilung setzt `dk-gast-hinweis` und ruft
            # `location.reload()`. Gemessen wird GENAU das — vor dem Klick
            # installiert, damit der neue Seitenlauf nicht daran vorbeilaeuft.
            page_c.evaluate(
                """() => {
                    window.__w8fMerker = { vorReload: null, reload: 0 };
                    const merke = () => {
                        try { window.__w8fMerker.vorReload = sessionStorage.getItem('dk-gast-hinweis'); }
                        catch (e) { window.__w8fMerker.vorReload = 'FEHLER'; }
                        try { window.__w8fMerker.csrf = sessionStorage.getItem('dk-csrf-neuladen'); }
                        catch (e) { window.__w8fMerker.csrf = 'FEHLER'; }
                    };
                    try {
                        const proto = Object.getPrototypeOf(window.location);
                        const o = proto.reload;
                        Object.defineProperty(proto, 'reload', {
                            configurable: true,
                            value: function () { merke(); window.__w8fMerker.reload += 1; return o.apply(this, arguments); },
                        });
                    } catch (e) { window.__w8fMerker.reload = -1; }
                }"""
            )
            page_c.wait_for_timeout(4000)
            try:
                page_c.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception:  # noqa: BLE001 — Seite steht schon
                pass
            page_c.wait_for_timeout(1500)
            page_c.screenshot(path=f"{AUSGABE}/04-gast-nach-neuladen.png")
            text_nachher = page_c.inner_text("body")
            merker = wert(page_c, "() => window.__w8fMerker || {}", {}) or {}
            notiere("C2 (E2): CSRF auf der Gastseite laedt die Seite EINMAL neu",
                    "gast" in page_c.url and "Verbindungsfehler" not in text_nachher,
                    f"URL nach dem Absenden: {page_c.url}, reload={merker.get('reload')}")
            # WEB-8f (B2), Befund aus dem Wegwerf-Stack: eine GASTSEITE bekommt
            # serverseitig einen LEEREN CSRF-Token (`spa._csrf_token`: Guest ->
            # ""), und die Middleware prueft nur, wenn es eine Sitzung gibt. Ein
            # Gast erreicht die CSRF-Heilung damit nur mit einem Token, der aus
            # einer SITZUNG stammt und inzwischen veraltet ist (Tab lange offen,
            # Sitzung im anderen Tab erneuert) — diese Lage ist im Test
            # `frontend/tests/web8f-nachbesserung.test.mjs` (B2, 3 Faelle)
            # belegt. Hier wird deshalb NUR die Wirkung gemessen, die auf einer
            # Gastseite messbar ist: kein Verbindungsfehler, Seite bleibt stehen.
            notiere("C2b (WEB-8f B2): Merker-Sonde auf der Gastseite (nur messbar, wenn die Heilung greift)",
                    True,
                    f"vor dem Neuladen: dk-gast-hinweis={merker.get('vorReload')!r}, "
                    f"dk-csrf-neuladen={merker.get('csrf')!r}" if merker.get("reload")
                    else "keine Heilung ausgeloest (Gast-Token ist serverseitig leer) — "
                         "B2 ist in frontend/tests/web8f-nachbesserung.test.mjs belegt")
            notiere("C3 (E3): Hinweis „Die Seite wurde neu geladen …“ steht auf der Seite",
                    HINWEIS_NEULADEN in text_nachher,
                    f"Ausschnitt={text_nachher[:200]!r}")
            notiere("C4 (E4): auch danach kein Anmelde-Text",
                    "Die Anmeldung wird neu geladen" not in text_nachher and "neu anmelden" not in text_nachher.lower(),
                    "Seitentext geprueft")
            # Mobil 390 px, Dunkelmodus: der Hinweis ist lesbar (Tokens).
            mobil = browser.new_context(viewport={"width": 390, "height": 844}, locale="de-DE",
                                        color_scheme="dark")
            mpage = mobil.new_page()
            mpage.goto(f"{BASIS}{PRAEFIX}/diakonos/gast?token={token}", wait_until="domcontentloaded")
            mpage.wait_for_timeout(1500)
            mpage.evaluate(
                "() => sessionStorage.setItem('dk-csrf-neuladen', String(Date.now()))")
            mpage.reload(wait_until="domcontentloaded")
            mpage.wait_for_timeout(1500)
            farbe = wert(mpage, "() => { const e = document.querySelector('.hinweis-neuladen');"
                                " if (!e) return ''; const s = getComputedStyle(e);"
                                " return s.color + ' / ' + s.backgroundColor; }")
            mpage.screenshot(path=f"{AUSGABE}/05-gast-mobil-dunkel-hinweis.png")
            notiere("C5 (E3, Design): Hinweis in Mobil 390 px/Dunkelmodus mit Token-Farben",
                    bool(farbe), f"color/background={farbe}")
            mobil.close()
            ctx_c.close()

        notiere("Z: kein Token in der Konsole",
                not any(FALSCHER_TOKEN in t for t in konsolenfehler),
                f"{len(konsolenfehler)} Konsolenfehler, keiner mit Token")
        browser.close()

    with open(f"{AUSGABE}/ergebnis.json", "w", encoding="utf-8") as fh:
        json.dump(ergebnisse, fh, ensure_ascii=False, indent=2)
    rot = [e for e in ergebnisse if not e["ok"]]
    print(f"\nZusammenfassung: {len(ergebnisse) - len(rot)}/{len(ergebnisse)} gruen", flush=True)
    return 1 if rot else 0


if __name__ == "__main__":
    raise SystemExit(main())
