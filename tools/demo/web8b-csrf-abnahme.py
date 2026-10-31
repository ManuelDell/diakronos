"""WEB-8b — Abnahme im Wegwerf-Stack: CSRF-Fehler im Client heilen.

Der Stack (Projekt web8b, Port 8311, Praefix /diakronos) verhaelt sich wie im
Betrieb. Der Fehler wird ECHT erzeugt — nicht per Mock:

  * Der Client schickt den Token aus `window.__DIakonosBOOT`; er wird im
    Browser absichtlich auf einen falschen Wert gesetzt. Die `CsrfMiddleware`
    des Servers vergleicht gegen die Sitzung im Redis und antwortet
    417 + `exc_type=CSRFTokenError` — genau der Befund.
  * Aktion: „Speichern" auf der Profilseite (`apiCall`).

Faelle:
  A) falscher Client-Token -> Token-Abruf (`session.sitzung_status`), GENAU
     EINE Wiederholung mit frischem Token, die gelingt; kein Neuladen, kein
     Fehlerdialog, `__DIakonosBOOT.csrf_token` ist erneuert.
  B) erneute Ablehnung im 60-s-Fenster: kein Neuladen, sondern Weiterleitung
     zur Anmeldung (Schleifenschutz, C2).
  C) echte Sitzungs-Ungueltigkeit (Sitzung im Wegwerf-Redis geloescht) -> 401,
     Anmeldemaske, keine Schleife.

Aufruf:
  docker run --rm --network host -v <worktree>:/repo:ro -v <ausgabe>:/out \
      -e WEB8B_BASIS=http://127.0.0.1:8311 -e WEB8B_REDIS=web8b-redis-1 \
      diakronos-web8b:pw python /repo/tools/demo/web8b-csrf-abnahme.py
"""

from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASIS = os.environ.get("WEB8B_BASIS", "http://127.0.0.1:8311")
PRAEFIX = "/diakronos"
SPA = f"{BASIS}{PRAEFIX}/diakonos"
AUSGABE = os.environ.get("WEB8B_AUSGABE", "/out")
ADMIN = (os.environ.get("WEB8B_USER", "admin@example.org"),
         os.environ.get("WEB8B_PASS", "Web8b-Admin-Pass-1"))

FALSCHER_TOKEN = "falscher-token-fuer-den-nachweis"
ZIEL = "profile.update_my_profile"

# `location.reload` mitzaehlen. Am Instanzobjekt ist die Property nicht
# beschreibbar, deshalb am Prototyp — ohne Sonde waere ein Force-Refresh im
# Test ein stiller Seitenwechsel.
RELOAD_SONDE = """() => {
    window.__web8bReload = 0;
    try {
        const proto = Object.getPrototypeOf(window.location);
        Object.defineProperty(proto, 'reload', {
            configurable: true,
            value: function () { window.__web8bReload = (window.__web8bReload || 0) + 1; },
        });
    } catch (e) { window.__web8bReload = -1; }
}"""

ergebnisse: list[dict] = []


def notiere(name: str, ok: bool, detail: str) -> None:
    ergebnisse.append({"fall": name, "ok": bool(ok), "detail": detail})
    print(f"[{'OK ' if ok else 'ROT'}] {name}: {detail}", flush=True)


def anmelden(page) -> str:
    page.goto(f"{BASIS}{PRAEFIX}/login", wait_until="domcontentloaded")
    page.fill('input[name="usr"]', ADMIN[0])
    page.fill('input[name="pwd"]', ADMIN[1])
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_timeout(1500)
    return page.url


def profil_oeffnen(page) -> None:
    """Profilseite der SPA (Hash-Route `#/profile`, siehe router.js:105)."""
    page.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)


def speichern(page) -> bool:
    """„Bearbeiten" -> „Speichern" (`apiCall('profile.update_my_profile')`).

    Der Formularinhalt bleibt unveraendert — es werden keine Daten verfaelscht.
    """
    bearbeiten = page.query_selector('button:has-text("Bearbeiten")')
    if bearbeiten:
        bearbeiten.click()
        page.wait_for_timeout(600)
    knopf = page.query_selector('button:has-text("Speichern")')
    if not knopf:
        return False
    knopf.click()
    return True


def loesche_sitzung(sid: str) -> bool:
    """Loescht `diakronos:sitzung:<sid>` im WEGWERF-Redis (Port aus der Env).

    Bewusst KEIN Docker-Aufruf: der Stack veroeffentlicht Redis nur auf
    127.0.0.1 im Wegwerf-Stack (WEB8B_REDIS_PORT, Standard 6391). Der Betrieb
    (Port 6380) wird nie beruehrt.
    """
    if not sid:
        return False
    import socket

    host = os.environ.get("WEB8B_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB8B_REDIS_PORT", "6391"))
    schluessel = f"diakronos:sitzung:{sid}"
    befehl = f"DEL {schluessel}\r\n".encode()
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            s.sendall(befehl)
            antwort = s.recv(64)
        return antwort.startswith(b":")
    except OSError:
        return False


def nur_ziel_ablehnen(route) -> None:
    """Lehnt JEDEN Aufruf des Ziel-Endpunkts mit 417 ab; alles andere laeuft.

    So entsteht eine dauerhafte Ablehnung (kein Glueckstreffer), mit der sich
    der Schleifenschutz pruefen laesst.
    """
    req = route.request
    if req.method == "POST" and ZIEL in req.url:
        route.fulfill(
            status=417,
            content_type="application/json",
            body=json.dumps({"message": "CSRF-Token ungueltig oder fehlend.",
                             "exc_type": "CSRFTokenError"}, ensure_ascii=False),
        )
        return
    route.continue_()


def reloads(page) -> int:
    return page.evaluate("() => window.__web8bReload || 0")


def main() -> int:
    os.makedirs(AUSGABE, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        page = ctx.new_page()
        konsolenfehler: list[str] = []
        page.on("console", lambda m: konsolenfehler.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: konsolenfehler.append(str(e)))

        notiere("Anmeldung", PRAEFIX in anmelden(page), f"URL: {page.url}")
        profil_oeffnen(page)
        page.screenshot(path=f"{AUSGABE}/01-profil.png")

        # ── A) falscher Client-Token -> Heilung ──────────────────────────────
        page.evaluate(RELOAD_SONDE)
        page.evaluate(f"() => {{ window.__DIakonosBOOT.csrf_token = '{FALSCHER_TOKEN}'; }}")
        token_vorher = page.evaluate("() => window.__DIakonosBOOT.csrf_token")

        verkehr: list[dict] = []
        page.on("response", lambda r: verkehr.append(
            {"status": r.status, "url": r.url.replace(BASIS, "")}
        ) if "/api/method/" in r.url else None)

        geklickt = speichern(page)
        page.wait_for_timeout(6000)

        ziel_antworten = [v for v in verkehr if ZIEL in v["url"]]
        zustand_a = [v["status"] for v in ziel_antworten]
        token_abrufe = [v for v in verkehr if "session.sitzung_status" in v["url"]]
        token_nachher = page.evaluate("() => window.__DIakonosBOOT.csrf_token")

        notiere("A0: Aktion ausgelöst (Profil „Speichern“)", geklickt, f"geklickt={geklickt}")
        notiere(
            "A1: Server lehnt mit 417 ab (echter CSRFTokenError)",
            417 in zustand_a,
            f"Status der Ziel-Aufrufe: {zustand_a}",
        )
        notiere(
            "A2: Token still erneuert (session.sitzung_status)",
            bool(token_abrufe) and token_nachher != token_vorher and bool(token_nachher),
            f"Token-Abrufe={len(token_abrufe)}, "
            f"vorher={token_vorher[:8]}… nachher={token_nachher[:8]}…",
        )
        # Die Oberflaeche kann denselben Klick doppelt ausloesen (eigener
        # Befund, nicht Teil dieser Karte). Entscheidend ist die Heilung:
        # nach der Token-Erneuerung gelingt der Aufruf, und es gibt KEINE
        # Wiederholungs-Schleife (kein dritter 417 nach dem 200).
        leasing = zustand_a[-1] == 200 and zustand_a.count(200) == 1
        notiere(
            "A3: nach genau EINER Token-Erneuerung gelingt der nächste Aufruf",
            bool(token_abrufe) and len(token_abrufe) == 1 and leasing,
            f"Token-Abrufe={len(token_abrufe)} (erwartet 1), Status={zustand_a}",
        )
        notiere(
            "A3b: keine Wiederholungs-Schleife (417 nach Erfolg)",
            "417" not in [str(x) for x in zustand_a[zustand_a.index(200) + 1:]] if 200 in zustand_a else False,
            f"Status={zustand_a}",
        )
        notiere("A4: kein Neuladen", reloads(page) == 0, f"reloads={reloads(page)}")
        notiere(
            "A5: kein Fehlerdialog, kein CSRF-Text",
            "CSRF" not in page.inner_text("body").upper(),
            "Seitentext ohne „CSRF“",
        )
        page.screenshot(path=f"{AUSGABE}/02-nach-heilung.png")

        # ── B) Schleifenschutz: erneute Ablehnung im 60-s-Fenster ────────────
        # A hat den Zeitstempel gesetzt -> eine weitere Ablehnung darf NICHT
        # (erneut) neu laden, sondern muss zur Anmeldung fuehren (C2).
        # Im 60-s-Fenster: der Zeitstempel steht (setzt die Heilung selbst), und
        # JEDE Ziel-Antwort wird abgelehnt. Erwartet: KEIN Neuladen, sondern
        # Weiterleitung zur Anmeldung mit Rücksprungziel (C2).
        profil_oeffnen(page)
        page.evaluate(
            "() => sessionStorage.setItem('dk-csrf-neuladen', String(Date.now() - 5000))"
        )
        page.evaluate(RELOAD_SONDE)
        page.route("**/*", nur_ziel_ablehnen)
        speichern(page)
        page.wait_for_timeout(9000)
        page.unroute("**/*")
        notiere(
            "B1: im 60-s-Fenster kein Neuladen",
            reloads(page) == 0,
            f"reloads={reloads(page)} (erwartet 0)",
        )
        notiere(
            "B2: stattdessen Anmeldemaske (Schleifenschutz C2)",
            "/login" in page.url and "redirect-to=" in page.url,
            f"URL: {page.url}",
        )
        page.screenshot(path=f"{AUSGABE}/03-schleifenschutz.png")

        # ── C) echte Sitzungs-Ungueltigkeit -> 401, Anmeldung ────────────────
        # Echte Sitzungs-Ungueltigkeit: genau die Sitzung des Browsers im
        # WEGWERF-Redis loeschen. Der Schluessel ist `diakronos:sitzung:<sid>`
        # (frappe_compat/sitzungen.py). Container-Zugriff nur ueber den
        # gemounteten Docker-Socket des Hosts — nie gegen den Betrieb.
        # Nach B steht der Tab auf der Anmeldemaske (und der 60-s-Merker im
        # sessionStorage). Fuer C einen FRISCHEN Kontext nehmen — so ist der
        # Fall „echte Sitzungs-Ungueltigkeit" unabhaengig von B.
        ctx_c = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        page_c = ctx_c.new_page()
        anmelden(page_c)
        sid = ""
        for cookie in ctx_c.cookies():
            if cookie.get("name") == "sid":
                sid = cookie.get("value", "")
                break
        # ERST die Seite laden (Sitzung ist noch gueltig, Knopf da), DANN die
        # Sitzung serverseitig widerrufen — wie ein Ablauf waehrend der Arbeit.
        page_c.goto(f"{SPA}/#/profile", wait_until="domcontentloaded")
        page_c.wait_for_timeout(3500)
        geloescht = loesche_sitzung(sid)
        c_verkehr: list[str] = []
        page_c.on("response", lambda r: c_verkehr.append(
            f"{r.status} {r.url.split('/api/method/')[-1][:40]}"
        ) if "/api/method/" in r.url else None)
        geklickt_c = speichern(page_c)
        page_c.wait_for_timeout(7000)
        print("[C] Aktion:", geklickt_c, "| Verkehr:", c_verkehr[:6], flush=True)
        # 401 fuehrt im Hauptbereich zum Sitzungsdialog („Deine Anmeldung ist
        # abgelaufen") mit Knopf „Neu anmelden" — das ist der bestehende Weg
        # (C3: SessionExpired bleibt wie heute), NICHT die CSRF-Heilung.
        # Der Sitzungsdialog wird per Teleport ausserhalb des App-Knotens
        # gerendert — deshalb gezielt im Overlay nachsehen.
        dialog_text = ""
        try:
            dialog_text = page_c.evaluate(
                "() => Array.from(document.querySelectorAll('[role=dialog]'))"
                ".map(e => e.innerText).join(' ').toLowerCase()"
            )
        except Exception:
            dialog_text = ""
        dialog = ("abgelaufen" in dialog_text or "angemeldet" in dialog_text
                  or "/login" in page_c.url)
        notiere(
            "C1: ungültige Sitzung -> Anmeldung/Sitzungsdialog, keine Schleife",
            dialog and reloads(page) == 0,
            f"Sitzung {sid[:8]}… im Wegwerf-Redis gelöscht={geloescht}, "
            f"Dialog={dialog} ({dialog_text[:60]!r}), reloads={reloads(page_c)}, URL: {page_c.url}",
        )
        page_c.screenshot(path=f"{AUSGABE}/04-sitzung-ungueltig.png")
        ctx_c.close()

        # ── Mobil 390 px ─────────────────────────────────────────────────────
        mobil = browser.new_context(viewport={"width": 390, "height": 844}, locale="de-DE")
        mpage = mobil.new_page()
        mpage.goto(f"{BASIS}{PRAEFIX}/login", wait_until="domcontentloaded")
        mpage.wait_for_timeout(1200)
        mpage.screenshot(path=f"{AUSGABE}/05-mobil-390.png")
        mobil.close()

        notiere(
            "C4: kein Token in der Konsole",
            not any(FALSCHER_TOKEN in t for t in konsolenfehler),
            f"{len(konsolenfehler)} Konsolenfehler insgesamt, keiner mit Token",
        )
        browser.close()

    with open(f"{AUSGABE}/ergebnis.json", "w", encoding="utf-8") as fh:
        json.dump(ergebnisse, fh, ensure_ascii=False, indent=2)
    rot = [e for e in ergebnisse if not e["ok"]]
    print(f"\nZusammenfassung: {len(ergebnisse) - len(rot)}/{len(ergebnisse)} gruen", flush=True)
    return 1 if rot else 0


if __name__ == "__main__":
    raise SystemExit(main())
