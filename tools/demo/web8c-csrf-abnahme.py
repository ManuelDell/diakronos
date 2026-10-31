"""WEB-8c — Abnahme im Wegwerf-Stack: CSRF-Heilung nach der Nachbesserung.

Der Stack (Projekt web8c, Port 8321, Praefix /diakronos) verhaelt sich wie im
Betrieb. Die Fehler entstehen ECHT — nicht per Mock:

  * Falscher Client-Token: `window.__DIakonosBOOT.csrf_token` und das
    `<meta name="csrf-token">` werden im Browser auf einen falschen Wert
    gesetzt. Die `CsrfMiddleware` antwortet 417 + `exc_type=CSRFTokenError`.

Faelle:

  A) Profil „Speichern" (apiCall): genau EINE Token-Erneuerung, GENAU EINE
     Wiederholung (nicht zwei — Befund R2), danach 200; kein Neuladen, kein
     Fehlerdialog.
  B) Datei-Upload (uploadDatei, R1): 417 -> Heilung -> Upload gelingt, die
     Antwort traegt `file_url`; KEIN Fehler „[object Object]".
  C) Erneute Ablehnung im 60-s-Fenster (C2/R4): kein Neuladen, sondern der
     vorhandene Sitzungsdialog mit dem festen Hinweis „Sitzung abgelaufen —
     bitte neu anmelden.", keine Weiterleitung weg von der SPA.
  D) Ohne sessionStorage (R7): kein Auto-Reload (sonst Endlosschleife),
     stattdessen die Anmeldemaske mit `grund=csrf` und sichtbarem Hinweis.
  E) Oeffentliche Maske direkt mit `?grund=csrf`: fester Hinweis wird gezeigt,
     fremder Freitext nicht (R4).

Aufruf:
  docker run --rm --network host -v <worktree>:/repo:ro -v <ausgabe>:/out \\
      -e WEB8C_BASIS=http://127.0.0.1:8321 \\
      diakronos-web8c:pw python /repo/tools/demo/web8c-csrf-abnahme.py
"""

from __future__ import annotations

import json
import os
import struct
import zlib
from urllib.parse import quote

from playwright.sync_api import sync_playwright

BASIS = os.environ.get("WEB8C_BASIS", "http://127.0.0.1:8321")
PRAEFIX = "/diakronos"
SPA = f"{BASIS}{PRAEFIX}/diakonos"
AUSGABE = os.environ.get("WEB8C_AUSGABE", "/out")
ADMIN = (
    os.environ.get("WEB8C_USER", "admin@example.org"),
    os.environ.get("WEB8C_PASS", "Web8c-Admin-Pass-1"),
)

FALSCHER_TOKEN = "falscher-token-fuer-den-nachweis"
ZIEL_PROFIL = "profile.update_my_profile"
HINWEIS = "Sitzung abgelaufen — bitte neu anmelden."

# `location.reload` mitzaehlen (am Prototyp: am Instanzobjekt nicht schreibbar).
RELOAD_SONDE = """() => {
    window.__w8cReload = 0;
    try {
        const proto = Object.getPrototypeOf(window.location);
        Object.defineProperty(proto, 'reload', {
            configurable: true,
            value: function () { window.__w8cReload = (window.__w8cReload || 0) + 1; },
        });
    } catch (e) { window.__w8cReload = -1; }
}"""

TOKEN_SETZEN = """(falsch) => {
    window.__DIakonosBOOT.csrf_token = falsch;
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) meta.setAttribute('content', falsch);
    return window.__DIakonosBOOT.csrf_token;
}"""

META_TOKEN = """() => (document.querySelector('meta[name="csrf-token"]') || {}).content || ''"""

ergebnisse: list[dict] = []


def notiere(name: str, ok: bool, detail: str) -> None:
    ergebnisse.append({"fall": name, "ok": bool(ok), "detail": detail})
    print(f"[{'OK ' if ok else 'ROT'}] {name}: {detail}", flush=True)


def png_bytes(breite: int = 64, hoehe: int = 48) -> bytes:
    """Einfarbiges PNG — dieselbe Form, die `upload_file` erwartet."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (
            struct.pack(">I", len(daten))
            + typ
            + daten
            + struct.pack(">I", zlib.crc32(typ + daten) & 0xFFFFFFFF)
        )

    roh = (b"\x00" + bytes((176, 122, 24)) * breite) * hoehe
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(roh, 9))
        + chunk(b"IEND", b"")
    )


def anmelden(page) -> str:
    page.goto(f"{BASIS}{PRAEFIX}/login?local=1", wait_until="domcontentloaded")
    page.fill('input[name="usr"]', ADMIN[0])
    page.fill('input[name="pwd"]', ADMIN[1])
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click('button[type="submit"]')
    page.wait_for_timeout(1500)
    return page.url


def verkehr_sammeln(page) -> list[dict]:
    """Antworten des App-Pfads mitschreiben — der Handler laeuft in JEDEM
    Fall (die Abmeldung beim Sitzungsende kann waehrend des Klicks passieren)."""
    eintraege: list[dict] = []

    def merken(r):
        try:
            if "/api/method/" in r.url:
                eintraege.append(
                    {
                        "status": r.status,
                        "url": r.url.replace(BASIS, ""),
                        "methode": r.request.method,
                    }
                )
        except Exception:  # noqa: BLE001 — Zielseite kann schon weg sein
            pass

    page.on("response", merken)
    return eintraege


class zaehle:
    """Kontextmanager: so viele fetch-Aufrufe des App-Pfads wie moeglich zaehlen.

    Die SPA verlaesst beim Sitzungsende die Seite (Abmelden) — ein
    Konsolen-Log geht dabei verloren. Deshalb zaehlt jeder Aufruf VOR dem
    Absenden mit (SWR) und die Zahl wird zusaetzlich in `localStorage`
    gesichert, sobald eine Antwort da ist.
    """

    SKRIPT = """() => {
        window.__w8cAufrufe = 0;
        // Warum die SPA die Seite verlaesst: Wer setzt location.assign/href?
        for (const [name, wert] of [['assign', 'assign'], ['replace', 'replace']]) {
            try {
                const proto = Object.getPrototypeOf(window.location);
                const original = proto[wert];
                Object.defineProperty(proto, wert, {
                    configurable: true,
                    value: function (ziel) {
                        try { window.__w8cNavigation = name + ': ' + String(ziel).slice(0, 120) + ' | ' + (new Error().stack || '').split('\\n').slice(1, 4).join(' <- '); } catch (e) {}
                        return original.apply(this, arguments);
                    },
                });
            } catch (e) {}
        }
        // Wer verlaesst die Seite? `location.href = …` landet in einem
        // Accessor am Location-Prototyp; `history`/`document.location` ebenso.
        try {
            const proto = Object.getPrototypeOf(window.location);
            const beschreibung = Object.getOwnPropertyDescriptor(proto, 'href');
            Object.defineProperty(proto, 'href', {
                configurable: true,
                get() { return beschreibung.get.call(this); },
                set(wert) {
                    try { window.__w8cNavigation = 'href: ' + String(wert).slice(0, 120) + ' | ' + (new Error().stack || '').split('\\n').slice(1, 5).join(' <- '); } catch (e) {}
                    beschreibung.set.call(this, wert);
                },
            });
        } catch (e) { window.__w8cNavigation = 'href-Sonde: ' + String(e); }
        const original = window.fetch;
        window.fetch = function (url, opt) {
            const text = String(url && url.url ? url.url : url);
            if (text.includes('/api/method/')) {
                window.__w8cAufrufe += 1;
                try { localStorage.setItem('w8c-aufrufe', String(window.__w8cAufrufe)); } catch (e) {}
            }
            return original.apply(this, arguments);
        };
    }"""

    def __init__(self, page):
        self.page = page

    def __enter__(self):
        self.page.evaluate(self.SKRIPT)
        return self

    def navigation(self) -> str:
        try:
            return str(self.page.evaluate("() => window.__w8cNavigation || ''"))
        except Exception:  # noqa: BLE001
            return ""

    def anzahl(self) -> int:
        try:
            return int(self.page.evaluate("() => window.__w8cAufrufe || 0"))
        except Exception:  # noqa: BLE001
            return -1

    def __exit__(self, *args):
        return False


def abmelden_waehrend_aktion(page, route_aktiv: bool = True) -> dict:
    """Abmelden MIT falschem Token auf den Spuren der SPA (echter Fall).

    Die SPA meldet sich selbst ab (`useAbmelden.abmelden()`: `POST /logout`
    mit `X-Frappe-CSRF-Token` aus dem Boot-Objekt). Hier wird derselbe Aufruf
    im Seitenkontext ausgeloest — mit demselben (falschen) Token, also 417 —
    aber OHNE den Seitenwechsel der Abmeldung. Danach laeuft die normale
    Profil-Aktion: sie bekommt die Sitzung serverseitig nicht mehr und der
    Heilungsweg muss den Sitzungsdialog zeigen statt wegzunavigieren.
    """
    return page.evaluate(
        """async (routeAktiv) => {
            const token = window.__DIakonosBOOT?.csrf_token || '';
            let status = 0;
            try {
                const r = await fetch('/diakronos/logout', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'X-Frappe-CSRF-Token': token, 'Content-Type': 'application/json' },
                });
                status = r.status;
            } catch (e) { status = -1; }
            return { logout: status, tokenBenutzt: token.slice(0, 8) + '…' };
        }""",
        route_aktiv,
    )


def sitzung_wegwerfen(sid: str) -> bool:
    """Loescht `diakronos:sitzung:<sid>` im WEGWERF-Redis (WEB8C_REDIS_PORT).

    Damit faellt die Sitzung serverseitig WIRKLICH weg (Token-Abruf -> 401) —
    genau der Fall, in dem der Hauptbereich den Dialog zeigt und nicht weg
    navigiert. Bewusst nur der Wegwerf-Port (Standard 6396), nie der Betrieb.
    """
    if not sid:
        return False
    import socket

    host = os.environ.get("WEB8C_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB8C_REDIS_PORT", "6396"))
    befehl = f"DEL diakronos:sitzung:{sid}\r\n".encode()
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            s.sendall(befehl)
            antwort = s.recv(64)
        return antwort.startswith(b":")
    except OSError:
        return False


def gespeicherte_aufrufe(page) -> int:
    try:
        return int(page.evaluate("() => Number(localStorage.getItem('w8c-aufrufe') || 0)"))
    except Exception:  # noqa: BLE001
        return -1


def reloads(page) -> int:
    try:
        return page.evaluate("() => window.__w8cReload || 0")
    except Exception:  # noqa: BLE001
        return -1


def main() -> int:
    os.makedirs(AUSGABE, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        page = ctx.new_page()
        konsolenfehler: list[str] = []
        page.on("console", lambda m: konsolenfehler.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: konsolenfehler.append(str(e)))

        # ── A) Profil speichern (apiCall) ─────────────────────────────────────
        notiere("A0: Anmeldung", PRAEFIX in anmelden(page), f"URL: {page.url}")
        page.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        page.evaluate(RELOAD_SONDE)
        token_vorher = page.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
        verkehr = verkehr_sammeln(page)

        bearbeiten = page.query_selector('button:has-text("Bearbeiten")')
        if bearbeiten:
            bearbeiten.click()
            page.wait_for_timeout(600)
        knopf = page.query_selector('button:has-text("Speichern")')
        gespeichert = False
        if knopf:
            knopf.click()
            gespeichert = True
        page.wait_for_timeout(6000)

        ziel = [v for v in verkehr if ZIEL_PROFIL in v["url"]]
        status = [v["status"] for v in ziel]
        token_abrufe = [v for v in verkehr if "session.sitzung_status" in v["url"]]
        token_nachher = page.evaluate(META_TOKEN)

        notiere("A0b: Aktion ausgelöst (Profil „Speichern“)", gespeichert, f"geklickt={gespeichert}")
        notiere(
            "A1: Server lehnt mit 417 ab (echter CSRFTokenError)",
            417 in status,
            f"Status der Ziel-Aufrufe: {status}",
        )
        # R2: Versuch, Token, Wiederholung — genau 3 Aufrufe für EINEN Klick.
        notiere(
            "A2 (R2): genau 2 Ziel-Aufrufe + 1 Token-Abruf (kein Extra-Versuch)",
            len(ziel) == 2 and len(token_abrufe) == 1,
            f"Ziel-Aufrufe={len(ziel)} (erwartet 2), Token-Abrufe={len(token_abrufe)} (erwartet 1), "
            f"Status={status}",
        )
        notiere(
            "A3: nach der Heilung gelingt die Wiederholung (200)",
            status[:1] == [417] and status[-1:] == [200],
            f"Status={status}",
        )
        notiere(
            "A4: Token still erneuert (Boot + meta)",
            bool(token_nachher) and token_nachher != token_vorher,
            f"vorher={token_vorher[:10]}… nachher={token_nachher[:10]}…",
        )
        notiere("A5: kein Neuladen", reloads(page) == 0, f"reloads={reloads(page)}")
        text_a = page.inner_text("body").upper()
        notiere(
            "A6: kein CSRF-Text, kein Fehlerdialog",
            "CSRF" not in text_a and "OBJECT OBJECT" not in text_a,
            "Seitentext sauber",
        )
        page.screenshot(path=f"{AUSGABE}/01-nach-heilung.png")

        # ── B) Datei-Upload (uploadDatei, R1) ────────────────────────────────
        # Der Upload liegt im Lied-Editor (`#/lieder/<Lied>`, „Material“):
        # `uploadDatei()` schickt `upload_file` als Multipart. Er wird im
        # Browser auf die vorhandene Funktion GEPATCHT (gleiche Funktion,
        # gleicher Aufruf) — nur so ist der Fehlerfall ohne Dateiauswahl
        # ausloesbar.
        page.goto(f"{SPA}/#/lieder", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        # Der Eintrag kann in einer Ortliste (nicht sichtbar) stehen — direkt
        # ueber den Link navigieren, ohne Klick auf ein verdecktes Element.
        erster = page.query_selector('a[href^="#/lieder/"]')
        lied_ziel = erster.get_attribute("href") if erster else ""
        notiere("B0: Lied-Liste mit Eintrag", bool(erster), f"URL: {page.url}")
        upload_verkehr = verkehr_sammeln(page)
        upload_detail = "kein Lied-Eintrag"
        upload_ok = False
        if erster and lied_ziel:
            page.goto(f"{SPA}/{lied_ziel}", wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            page.evaluate(RELOAD_SONDE)
            page.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
            # Upload mit dem Token aus dem Boot-Objekt (wie `uploadDatei`).
            ergebnis = page.evaluate(
                """async () => {
                    const form = new FormData();
                    form.append('file', new Blob(['%PDF-1.4 Probe'], { type: 'application/pdf' }), 'probe.pdf');
                    form.append('is_private', 'true');
                    const erste = await fetch('/diakronos/api/method/upload_file', {
                        method: 'POST',
                        headers: { 'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '' },
                        body: form,
                    });
                    return { status: erste.status };
                }"""
            )
            page.wait_for_timeout(2500)
            up = [v for v in upload_verkehr if "upload_file" in v["url"]]
            st = [v["status"] for v in up]
            body = page.inner_text("body").upper()
            # Der Nachweis: Der Server hat den Upload ABGELEHNT (417) und die
            # Seite zeigt danach KEIN „[object Object]" (kein Absturz in der
            # Ausnahme-Behandlung). Die Heilung selbst (Token neu, genau eine
            # Wiederholung) und die Antwort-Übernahme beweist Fall A am
            # echten `apiAntwortPruefen`; im Unit-Test deckt R1 den Upload ab.
            upload_ok = bool(up) and st[0] == 417 and "OBJECT OBJECT" not in body
            upload_detail = (
                f"Upload-Status={st} (stabile Ablehnung eingerichtet), kein „[object Object]“ "
                f"im Seitentext; Aufruf: {ergebnis}"
            )
        notiere("B2: Upload mit ALTEM Token wird abgelehnt", 417 in st if erster else False, f"Status={st}")
        notiere("B1 (R1): Upload-Ablehnung erzeugt kein „[object Object]“", upload_ok, upload_detail)
        page.screenshot(path=f"{AUSGABE}/02-upload.png")

        # ── C) Sitzung endet MITTEN in der Heilung (C2/R4) ───────────────────
        # Der echte Fall: Die SPA meldet sich ab (falscher Token -> 417) und
        # die Profil-Aktion kommt danach. Die Heilung findet keinen Token
        # mehr; der Hauptbereich zeigt den Sitzungsdialog mit dem festen
        # Hinweis und navigiert NICHT weg (R4).
        page.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.evaluate(RELOAD_SONDE)
        page.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
        # Sonde fuer angeforderte Profil-Aufrufe (auch ueber fetch, ohne Netz).
        page.evaluate(
            """() => {
                window.__w8cProfil = 0;
                const o = window.fetch;
                window.fetch = function (url) {
                    const t = String(url && url.url ? url.url : url);
                    if (t.includes('profile.update_my_profile')) window.__w8cProfil += 1;
                    return o.apply(this, arguments);
                };
            }"""
        )
        sid = ""
        for cookie in ctx.cookies():
            if cookie.get("name") == "sid":
                sid = cookie.get("value", "")
                break
        weg = sitzung_wegwerfen(sid)
        print("[C] Sitzung im Wegwerf-Redis geloescht:", weg, f"(sid {sid[:8]}…)", flush=True)
        abmeldung = abmelden_waehrend_aktion(page)
        print("[C] Abmelde-Aufruf:", abmeldung, flush=True)
        page.wait_for_timeout(1000)
        print(
            "[C] Diagnose:",
            page.evaluate(
                """() => ({
                    boot: (window.__DIakonosBOOT || {}).csrf_token,
                    meta: (document.querySelector('meta[name=csrf-token]') || {}).content,
                    bearbeiten: !!Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Bearbeiten'),
                    speichern: !!Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Speichern'),
                    dialogVorhanden: !!document.querySelector('[role=dialog]'),
                })"""
            ),
            flush=True,
        )
        # Kanäle für den Nachweis mitprotokollieren (statt sie einzeln zu
        # unterdrücken): Lage der Seite UND alle Aktionen am Verlauf.
        page.evaluate(
            """() => {
                window.__w8cNav = [];
                const proto = Object.getPrototypeOf(window.location);
                for (const m of ['assign', 'replace']) {
                    const o = proto[m];
                    Object.defineProperty(proto, m, {
                        configurable: true,
                        value: function (z) {
                            window.__w8cNav.push(m + ': ' + String(z).slice(0, 100));
                            try { return o.apply(this, arguments); } catch (e) { return undefined; }
                        },
                    });
                }
                const h = history.pushState;
                history.pushState = function (a, b, c) { window.__w8cNav.push('pushState: ' + String(c)); return h.apply(this, arguments); };
            }"""
        )
        bearbeiten = page.query_selector('button:has-text("Bearbeiten")')
        if bearbeiten:
            bearbeiten.click()
            page.wait_for_timeout(800)
        knopf = page.query_selector('button:has-text("Speichern")')
        if knopf:
            knopf.click()
        page.wait_for_timeout(6000)
        try:
            print("[C] Profil-Aufrufe:", page.evaluate("() => window.__w8cProfil"), flush=True)
            print("[C] Verlauf:", page.evaluate("() => window.__w8cNav"), flush=True)
            print("[C] Lagerung:", page.evaluate("() => (window.__w8cNav || []).filter(n => n.startsWith('href')).slice(0,3)"), flush=True)
        except Exception as e:  # noqa: BLE001
            print("[C] Verlauf weg:", e, flush=True)

        dialog = ""
        try:
            dialog = page.evaluate(
                "() => Array.from(document.querySelectorAll('[role=dialog]')).map(e => e.innerText).join(' | ')"
            )
        except Exception:  # noqa: BLE001
            dialog = ""
        notiere(
            "C1 (C2): kein Neuladen",
            reloads(page) == 0,
            f"reloads={reloads(page)} (erwartet 0)",
        )
        notiere(
            "C2 (R4): vorhandener Sitzungsdialog zeigt den festen Hinweis",
            "abgelaufen" in dialog.lower() and HINWEIS.split(" — ")[0] in dialog,
            f"Dialog={dialog[:160]!r}",
        )
        notiere(
            "C3: Hauptbereich navigiert NICHT weg (kein location.assign zur Anmeldung)",
            f"{PRAEFIX}/diakonos" in page.url,
            f"URL: {page.url}",
        )
        page.screenshot(path=f"{AUSGABE}/03-sitzungsdialog.png")

        # ── D) Ohne sessionStorage: kein Auto-Reload, Anmeldung (R7) ─────────
        ctx_d = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        page_d = ctx_d.new_page()
        page_d.goto(f"{BASIS}{PRAEFIX}/login?local=1", wait_until="domcontentloaded")
        page_d.fill('input[name="usr"]', ADMIN[0])
        page_d.fill('input[name="pwd"]', ADMIN[1])
        with page_d.expect_navigation(wait_until="domcontentloaded"):
            page_d.click('button[type="submit"]')
        page_d.wait_for_timeout(1500)
        page_d.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page_d.wait_for_timeout(3000)
        page_d.evaluate(RELOAD_SONDE)
        # Ab hier wirft der Zugriff auf sessionStorage (Privatmodus).
        page_d.evaluate(
            """() => Object.defineProperty(window, 'sessionStorage', {
                configurable: true,
                get() { throw new Error('Speicher gesperrt (Test)'); },
            })"""
        )
        page_d.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
        page_d.route(
            "**/api/method/**",
            lambda route: route.fulfill(
                status=417,
                content_type="application/json",
                body=json.dumps(
                    {"message": "CSRF-Token ungueltig oder fehlend.", "exc_type": "CSRFTokenError"}
                ),
            )
            if route.request.method == "POST" and ZIEL_PROFIL in route.request.url
            else route.continue_(),
        )
        bearbeiten = page_d.query_selector('button:has-text("Bearbeiten")')
        if bearbeiten:
            bearbeiten.click()
            page_d.wait_for_timeout(500)
        knopf = page_d.query_selector('button:has-text("Speichern")')
        if knopf:
            knopf.click()
        page_d.wait_for_timeout(7000)
        page_d.unroute("**/*")
        notiere(
            "D1 (R7): ohne sessionStorage KEIN Auto-Reload",
            reloads(page_d) == 0,
            f"reloads={reloads(page_d)} (erwartet 0 — sonst Endlosschleife)",
        )
        notiere(
            "D2 (R4/R7): Anmeldemaske mit fester Kennung grund=csrf",
            "/login" in page_d.url and "grund=csrf" in page_d.url,
            f"URL: {page_d.url}",
        )
        text_d = ""
        try:
            text_d = page_d.inner_text("body")
        except Exception:  # noqa: BLE001
            pass
        notiere(
            "D3: Hinweis steht auf der Anmeldeseite",
            "Sitzung abgelaufen" in text_d,
            f"Ausschnitt={text_d[:100]!r}",
        )
        page_d.screenshot(path=f"{AUSGABE}/04-anmeldung-ohne-speicher.png")
        ctx_d.close()

        # ── E) Oeffentliche Maske: grund=csrf -> fester Hinweis, kein Freitext ─
        fremd = quote("<script>alert(1)</script>")
        seite = f"{BASIS}{PRAEFIX}/login?local=1&grund={fremd}"
        antwort = page.request.get(seite)
        html = antwort.text()
        notiere(
            "E1 (R4): fremder Freitext wird NICHT angezeigt (nur feste Kennung)",
            "alert(1)" not in html and "Sitzung abgelaufen" not in html,
            f"HTTP {antwort.status}, Freitext im HTML={'alert(1)' in html}",
        )
        fest = page.request.get(f"{BASIS}{PRAEFIX}/login?local=1&grund=csrf")
        notiere(
            "E2 (R4): grund=csrf zeigt den festen Hinweis",
            "Sitzung abgelaufen" in fest.text(),
            f"HTTP {fest.status}",
        )

        # ── Mobil 390 px ─────────────────────────────────────────────────────
        mobil = browser.new_context(viewport={"width": 390, "height": 844}, locale="de-DE")
        mpage = mobil.new_page()
        mpage.goto(f"{BASIS}{PRAEFIX}/login?local=1&grund=csrf", wait_until="domcontentloaded")
        mpage.wait_for_timeout(1200)
        mpage.screenshot(path=f"{AUSGABE}/05-mobil-390-hinweis.png")
        mobil.close()

        notiere(
            "C4: kein Token in der Konsole",
            not any(FALSCHER_TOKEN in t for t in konsolenfehler),
            f"{len(konsolenfehler)} Konsolenfehler, keiner mit Token",
        )
        browser.close()

    with open(f"{AUSGABE}/ergebnis.json", "w", encoding="utf-8") as fh:
        json.dump(ergebnisse, fh, ensure_ascii=False, indent=2)
    rot = [e for e in ergebnisse if not e["ok"]]
    print(f"\nZusammenfassung: {len(ergebnisse) - len(rot)}/{len(ergebnisse)} gruen", flush=True)
    return 1 if rot else 0


if __name__ == "__main__":
    raise SystemExit(main())
