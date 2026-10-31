"""WEB-8d — Abnahme im Wegwerf-Stack: CSRF-Heilung auf GASTSEITEN (M1).

Der Stack (eigenes Compose-Projekt, eigener Port, Praefix /diakronos)
verhaelt sich wie im Betrieb. Die Fehler entstehen ECHT: `window.__DIakonosBOOT
.csrf_token` und das `<meta name="csrf-token">` werden im Browser auf einen
falschen Wert gesetzt, die `CsrfMiddleware` antwortet 417 +
`exc_type=CSRFTokenError`.

BEFUND (M1): Auf Gast-/Registrierungsseiten hat die Person KEIN Konto. Die
Heilung holte trotzdem über `session.sitzung_status` ein Token — der Endpunkt
verlangt Anmeldung, also 401 -> Weiterleitung auf `/login`, wo ein Gast nichts
kann. Erwartet:

  G1) Der Token-Endpunkt (`session.sitzung_status`) wird vom Gastformular
      NIE aufgerufen.
  G2) Ein einmaliger Fehler lädt die Seite HÖCHSTENS EINMAL neu (frisches
      Seiten-Token über `location.reload()`).
  G3) Bleibt der Fehler, steht die feste Meldung AUF DER SEITE und die Seite
      bleibt auf `/diakonos/gast` — NIE `/login`.
  G4) Der feste Hinweis nennt keine Anmeldung als einzigen Ausweg.

Der Lauf braucht einen gültigen Gast-/Registrierungstoken im Stack (Seed per
`tools/demo/musterhausen.py`). Ohne Token bleibt der Gastlink nach WEB-7 auf
der Hauptseite (`umgeleitet`) — dann meldet der Lauf das als ROT mit Grund.

Aufruf:
  docker run --rm --network host -v <worktree>:/repo:ro -v <ausgabe>:/out \\
      -e WEB8D_BASIS=http://127.0.0.1:<port> \\
      -e WEB8D_GAST_TOKEN=<token> \\
      diakronos-web8d:pw python /repo/tools/demo/web8d-csrf-abnahme.py
"""

from __future__ import annotations

import json
import os

from playwright.sync_api import sync_playwright

BASIS = os.environ.get("WEB8D_BASIS", "http://127.0.0.1:8321")
PRAEFIX = os.environ.get("WEB8D_PRAEFIX", "/diakronos")
SPA = f"{BASIS}{PRAEFIX}/diakonos"
AUSGABE = os.environ.get("WEB8D_AUSGABE", "/out")
GAST_TOKEN = os.environ.get("WEB8D_GAST_TOKEN", "").strip()
#: Eine gueltige `sid` (Wegwerf-Stack) — sie stellt den BEFUND M1 her: Wer im
#: selben Browser einmal angemeldet war, hat eine Sitzung; auf der Gastseite
#: wird dann der CSRF-Kopfzeilen-Token verlangt. Ohne Sitzung prueft die
#: `CsrfMiddleware` gar nicht (kein Token, kein Fehler) — dann gäbe es nichts
#: zu heilen. Gesetzt wird nur der Cookie-Wert, NICHT der CSRF-Token.
GAST_SID = os.environ.get("WEB8D_GAST_SID", "").strip()

FALSCHER_TOKEN = "falscher-token-fuer-den-nachweis"
HINWEIS_KERN = "Die Seite konnte nicht abgeschickt werden"
GAST_SEITE = "gast"

# `location.reload` mitzaehlen (am Prototyp: am Instanzobjekt nicht schreibbar).
# Der Zaehler liegt in `sessionStorage` — so ueberlebt er das echte Neuladen,
# das der Gastweg ausloest (frisches Seiten-Token, WEB-8d M1).
RELOAD_SONDE = """() => {
    try { sessionStorage.setItem('w8d-reloads', '0') } catch (e) {}
    try {
        const proto = Object.getPrototypeOf(window.location);
        Object.defineProperty(proto, 'reload', {
            configurable: true,
            value: function () {
                try { sessionStorage.setItem('w8d-reloads', String(Number(sessionStorage.getItem('w8d-reloads') || 0) + 1)) } catch (e) {}
            },
        });
    } catch (e) {}
}"""

TOKEN_SETZEN = """(falsch) => {
    window.__DIakonosBOOT.csrf_token = falsch;
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) meta.setAttribute('content', falsch);
    return window.__DIakonosBOOT.csrf_token;
}"""

# Zaehlt die Aufrufe des Token-Endpunkts (und alles am App-Pfad) im Browser.
AUFRUF_SONDE = """() => {
    window.__w8dAufrufe = [];
    const original = window.fetch;
    window.fetch = function (url, opt) {
        const text = String(url && url.url ? url.url : url);
        if (text.includes('/api/method/')) window.__w8dAufrufe.push(text);
        return original.apply(this, arguments);
    };
}"""

ergebnisse: list[dict] = []


def notiere(name: str, ok: bool, detail: str) -> None:
    ergebnisse.append({"fall": name, "ok": bool(ok), "detail": detail})
    print(f"[{'OK ' if ok else 'ROT'}] {name}: {detail}", flush=True)


def anfrage_url(page, pfad: str) -> str:
    return f"{BASIS}{PRAEFIX}/{pfad}"


def main() -> int:
    os.makedirs(AUSGABE, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="de-DE")
        if GAST_SID:
            # BEFUND-LAGE (M1): der Browser bringt eine Sitzung mit — genau wie
            # bei jemandem, der die Gemeinde-Seite schon einmal geöffnet hat.
            ctx.add_cookies([{
                "name": "sid", "value": GAST_SID, "domain": "127.0.0.1", "path": "/",
            }])
        page = ctx.new_page()
        konsolenfehler: list[str] = []
        page.on("console", lambda m: konsolenfehler.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: konsolenfehler.append(str(e)))

        # ── G0) Gastseite überhaupt erreichbar? ──────────────────────────────
        adresse = anfrage_url(page, GAST_SEITE)
        if GAST_TOKEN:
            adresse = f"{adresse}?token={GAST_TOKEN}"
        page.goto(adresse, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        seite_vorher = page.inner_text("body").strip() if page.query_selector("body") else ""
        notiere(
            "G0: Gastseite geladen und Formular sichtbar",
            "Vorname" in seite_vorher and "Anmelden" in seite_vorher,
            f"URL={page.url} Text={seite_vorher[:80]!r}",
        )
        page.screenshot(path=f"{AUSGABE}/01-gast-vorher.png")

        # ── G1/G2/G3) Falscher Token -> Gastweg heilt ohne session_status ────
        page.evaluate(RELOAD_SONDE)
        page.evaluate(AUFRUF_SONDE)

        def absenden() -> None:
            """Formular mit dem FALSCHEN Token absenden (kein `session_status`)."""
            page.evaluate(TOKEN_SETZEN, FALSCHER_TOKEN)
            page.fill('input[autocomplete="given-name"]', "Probe")
            page.fill('input[autocomplete="family-name"]', "Gast")
            box = page.query_selector("input[type=checkbox]")
            if box and not box.is_checked():
                box.check()
            page.click('button[type="submit"]')

        absenden()
        page.wait_for_timeout(4000)
        # Der Gastweg laedt im ersten Fehlerfall die Seite neu (frisches
        # Seiten-Token). Danach steht wieder ein frisches Formular da — erneut
        # mit falschem Token absenden, damit der ZWEITE Fall sichtbar wird
        # (feste Meldung statt Neuladen, kein /login).
        if page.query_selector('input[autocomplete="given-name"]'):
            absenden()
            page.wait_for_timeout(4000)

        aufrufe = page.evaluate("() => window.__w8dAufrufe || []")
        token_abrufe = [u for u in aufrufe if "session.sitzung_status" in u]
        reloads = page.evaluate("() => Number(sessionStorage.getItem('w8d-reloads') || 0)")
        url_nachher = page.url
        text_nachher = page.inner_text("body") if page.query_selector("body") else ""

        notiere(
            "G1 (M1): Gastformular ruft session.sitzung_status NICHT auf",
            not token_abrufe,
            f"Token-Abrufe={len(token_abrufe)} (erwartet 0), Aufrufe im 2. Versuch={len(aufrufe)}",
        )
        notiere(
            "G2 (M1): höchstens EIN Neuladen (frisches Seiten-Token)",
            reloads <= 1,
            f"reloads={reloads} (erwartet 0 oder 1, nie mehr)",
        )
        notiere(
            "G3 (M1): NICHT zur Anmeldung — die Seite bleibt die Gastseite",
            "/login" not in url_nachher and GAST_SEITE in url_nachher,
            f"URL nachher={url_nachher}",
        )
        meldung_da = HINWEIS_KERN in text_nachher
        notiere(
            "G4 (M1): feste Meldung auf der Seite (frisches Seiten-Token half nicht)",
            meldung_da,
            f"Hinweis im Text={meldung_da}, reloads={reloads}, Text={text_nachher.strip()[:100]!r}",
        )
        notiere(
            "G5 (M1): die Meldung schickt den Gast NICHT zum Anmelden",
            "bitte neu anmelden" not in text_nachher.lower(),
            f"Text-Ausschnitt={text_nachher.strip()[:140]!r}",
        )
        notiere(
            "G6: kein Token in der Konsole",
            not any(FALSCHER_TOKEN in t for t in konsolenfehler),
            f"{len(konsolenfehler)} Konsolenfehler, keiner mit Token",
        )
        page.screenshot(path=f"{AUSGABE}/02-gast-nachher.png")

        # ── Mobil 390 px: dieselbe Meldung ist lesbar ────────────────────────
        mobil = browser.new_context(viewport={"width": 390, "height": 844}, locale="de-DE")
        mpage = mobil.new_page()
        mpage.goto(adresse, wait_until="domcontentloaded")
        mpage.wait_for_timeout(1500)
        mpage.screenshot(path=f"{AUSGABE}/03-gast-mobil-390.png", full_page=True)
        mobil.close()

        browser.close()

    with open(f"{AUSGABE}/ergebnis.json", "w", encoding="utf-8") as fh:
        json.dump(ergebnisse, fh, ensure_ascii=False, indent=2)
    rot = [e for e in ergebnisse if not e["ok"]]
    print(f"\nZusammenfassung: {len(ergebnisse) - len(rot)}/{len(ergebnisse)} gruen", flush=True)
    return 1 if rot else 0


if __name__ == "__main__":
    raise SystemExit(main())
