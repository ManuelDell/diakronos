"""UX3c — Screenshots und Messungen des Bereichs „Dienste“.

Läuft im Playwright-Image gegen einen WEGWERF-Stack mit den Demo-Daten
(Musterhausen). Aufgenommen wird, was die Karte berührt:

* A2-Reiterzeile über dem Inhalt: „Meine Dienste“ ist der Start (alle Rollen),
  „Dienstpläne“ nur mit Planungsrecht, „Vorlagen“ nur Administration,
* dieselbe Reiterzeile auf allen drei Reitern und auf einer Unterseite
  (Plan-Detailmarke, Vorlagen-Editor),
* „Planrahmen“ verschwindet aus der Adresse: die alten Adressen leiten
  dauerhaft auf die Reiter weiter (Beleg = Adresszeile nach dem Laden),
* die persönliche Sicht („Meine Dienste“) bleibt unverändert nutzbar.

Messungen im Bild (nicht nur „sieht gut aus“):
  * Knopfhöhe der Reiter ≥ --control-h (40 px), bei 390 px ≥ 44 px,
  * Symbol im Reiter mittig zur Textzeile (Freigabe Manuel 2026-11-04),
  * kein waagerechter Überlauf bei 390 px,
  * genau EINE Reiterzeile je Seite (keine doppelte Leiste).

Aufruf (Netz des eigenen Compose-Projekts, nie der Betrieb)::

    docker run --rm --network ux3c_default \
        -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe -e MARKER=nachher \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux3c-screenshots.py

Die Bilder sind Abnahme-Belege, keine Veröffentlichung: erfundene Demo-Daten.
"""

from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000").rstrip("/")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
MITGLIED_EMAIL = os.environ.get("MITGLIED_EMAIL", "")
MITGLIED_PASS = os.environ.get("MITGLIED_PASS", "")
# Kennungen für die Unterseiten (leer = Schritt entfällt).
PLAN_ID = os.environ.get("PLAN_ID", "")
PLANTYP = os.environ.get("PLANTYP", "")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")

fehler: list[str] = []
notizen: dict[str, dict] = {}

# (Name, Adresse) — Seiten, die UX3c berührt.
SEITEN = [
    ("01-meine-dienste", "#/dienste/meine-dienste"),
    ("02-dienstplaene", "#/dienste/dienstplaene"),
    ("03-vorlagen", "#/dienste/vorlagen"),
    ("04-einstieg-dienste", "#/dienste"),
]

# Alte Adressen → erwartete Zieladresse nach dem Laden (dauerhafte
# Weiterleitung; der Begriff „Planrahmen“ verschwindet aus der Adresse).
WEITERLEITUNGEN = [
    ("05-alt-planrahmen", "#/planrahmen", "#/dienste/dienstplaene"),
    ("06-alt-meine-dienste", "#/planrahmen/meine-dienste", "#/dienste/meine-dienste"),
    ("07-alt-einrichten", "#/planrahmen/einrichten", "#/dienste/vorlagen"),
]


def anmelden(page, benutzer: str, passwort: str) -> None:
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('#dk-usr, input[name="usr"]', benutzer)
    page.fill('#dk-pwd, input[name="pwd"]', passwort)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_load_state("networkidle")


def reiter_messen(page) -> dict:
    """Reiterzeile lesen: Beschriftungen, Höhen, Ausrichtung, Anzahl."""
    return page.evaluate(
        """() => {
      const leisten = Array.from(document.querySelectorAll('.dk-dienste-reiter'));
      const leiste = leisten[0];
      if (!leiste) return {anzahl: 0};
      const punkte = Array.from(leiste.querySelectorAll('.dk-dienste-reiter-punkt')).map(a => {
        const r = a.getBoundingClientRect();
        // Symbol (falls vorhanden) und Textzeile vergleichen.
        const svg = a.querySelector('svg, img');
        const sr = svg ? svg.getBoundingClientRect() : null;
        return {
          label: a.textContent.trim(),
          aktiv: a.classList.contains('is-aktiv'),
          ariaAktuell: a.getAttribute('aria-current'),
          hoehe: Math.round(r.height * 10) / 10,
          links: a.getAttribute('href'),
          symbolMitte: sr ? Math.round((sr.top + sr.height / 2) * 10) / 10 : null,
          textMitte: Math.round((r.top + r.height / 2) * 10) / 10,
        };
      });
      const cs = getComputedStyle(leiste);
      return {
        anzahl: leisten.length,
        labels: punkte.map(p => p.label),
        punkte,
        gap: cs.gap,
        ueberlauf: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    }"""
    )


def schuss(page, ordner: str, name: str, pfad: str) -> str:
    page.goto(f"{BASE}/{pfad}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(700)
    ziel = os.path.join(ordner, f"{name}.png")
    page.screenshot(path=ziel, full_page=False)
    print(f"[ux3c] {os.path.basename(ziel)} ← {pfad} → {page.url}")
    return page.url


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ── Administrator: alle drei Reiter, hell/dunkel, Desktop/Mobil ──────
        for lage, groesse in (("desktop", {"width": 1440, "height": 900}),
                              ("mobil", {"width": 390, "height": 844})):
            for thema in ("hell", "dunkel"):
                ordner = os.path.join(ZIEL, MARKER, lage, thema)
                os.makedirs(ordner, exist_ok=True)
                context = browser.new_context(
                    viewport=groesse,
                    has_touch=(lage == "mobil"),
                    is_mobile=(lage == "mobil"),
                    locale="de-DE",
                )
                page = context.new_page()
                page.on("console", lambda m: fehler.append(f"{lage}/{thema}: {m.text}")
                        if m.type == "error" else None)
                page.on("pageerror", lambda e: fehler.append(f"{lage}/{thema}: {e}"))
                anmelden(page, BENUTZER, PASSWORT)
                if thema == "dunkel":
                    page.evaluate("() => localStorage.setItem('dk-theme','dark')")
                    page.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")

                for name, pfad in SEITEN:
                    schuss(page, ordner, name, pfad)
                    mess = reiter_messen(page)
                    notizen[f"{lage}/{thema}/{name}"] = mess
                    if not mess.get("anzahl"):
                        fehler.append(f"{lage}/{thema}/{name}: keine Reiterzeile")
                        continue
                    if mess["anzahl"] != 1:
                        fehler.append(f"{lage}/{thema}/{name}: {mess['anzahl']} Reiterzeilen "
                                      "(die Seiten dürfen keine eigene zeichnen)")
                    if mess["ueberlauf"] > 0:
                        fehler.append(f"{lage}/{thema}/{name}: waagerechter Überlauf "
                                      f"{mess['ueberlauf']} px")
                    soll = 44 if lage == "mobil" else 40
                    for punkt in mess["punkte"]:
                        if punkt["hoehe"] < soll:
                            fehler.append(f"{lage}/{thema}/{name}: Reiter „{punkt['label']}“ "
                                          f"{punkt['hoehe']} px < {soll} px")
                        if punkt["symbolMitte"] is not None and \
                                abs(punkt["symbolMitte"] - punkt["textMitte"]) > 1.5:
                            fehler.append(f"{lage}/{thema}/{name}: Symbol in "
                                          f"„{punkt['label']}“ sitzt "
                                          f"{abs(punkt['symbolMitte'] - punkt['textMitte'])} px "
                                          "neben der Textzeile")
                    if mess["labels"] != ["Meine Dienste", "Dienstpläne", "Vorlagen"]:
                        fehler.append(f"{lage}/{thema}/{name}: Reiter {mess['labels']} "
                                      "(Administrator sieht A2: drei Reiter)")

                # Start-Reiter ist „Meine Dienste“ — auch über den Einstieg.
                ziel = page.url
                if thema == "hell":
                    if "#/dienste/meine-dienste" not in ziel:
                        fehler.append(f"{lage}/{thema}: Einstieg landete auf {ziel}")
                    aktive = [p2["label"] for p2 in notizen[f"{lage}/{thema}/01-meine-dienste"].get("punkte", [])
                              if p2["aktiv"]]
                    if aktive != ["Meine Dienste"]:
                        fehler.append(f"{lage}/{thema}: aktiver Reiter {aktive}, "
                                      "erwartet „Meine Dienste“")

                    # Alte Adressen: dauerhafte Weiterleitung (Adresszeile).
                    for name, pfad, soll in WEITERLEITUNGEN:
                        url = schuss(page, ordner, name, pfad)
                        if not url.endswith(soll):
                            fehler.append(f"{lage}/{thema}/{name}: {pfad} landete auf {url}, "
                                          f"erwartet …{soll}")
                        if "#/planrahmen" in url:
                            fehler.append(f"{lage}/{thema}/{name}: „planrahmen“ bleibt in der Adresse ({url})")

                    # Unterseiten markieren ihren Reiter (Plan-Detail, Editor).
                    if PLAN_ID:
                        url = schuss(page, ordner, "08-plan-detail",
                                     f"#/dienste/dienstplaene/plan/{PLAN_ID}")
                        if f"/dienste/dienstplaene/plan/{PLAN_ID}" not in url:
                            fehler.append(f"{lage}/{thema}: Plan-Detail landete auf {url}")
                    if PLANTYP:
                        url = schuss(page, ordner, "09-vorlagen-editor",
                                     f"#/dienste/vorlagen/{PLANTYP}")
                        if f"/dienste/vorlagen/{PLANTYP}" not in url:
                            fehler.append(f"{lage}/{thema}: Vorlagen-Editor landete auf {url}")
                context.close()

        # ── Mitglied ohne Planungsrecht: EIN Reiter (Start) ─────────────────
        if MITGLIED_EMAIL and MITGLIED_PASS:
            for lage, groesse in (("desktop", {"width": 1440, "height": 900}),
                                  ("mobil", {"width": 390, "height": 844})):
                ordner = os.path.join(ZIEL, MARKER, lage, "hell")
                os.makedirs(ordner, exist_ok=True)
                context = browser.new_context(
                    viewport=groesse,
                    has_touch=(lage == "mobil"),
                    is_mobile=(lage == "mobil"),
                    locale="de-DE",
                )
                page = context.new_page()
                page.on("pageerror", lambda e: fehler.append(f"mitglied/{lage}: {e}"))
                anmelden(page, MITGLIED_EMAIL, MITGLIED_PASS)
                schuss(page, ordner, "10-mitglied-meine-dienste", "#/dienste/meine-dienste")
                mess = reiter_messen(page)
                notizen[f"mitglied/{lage}/meine-dienste"] = mess
                # Ein Reiter bleibt sichtbar, aber als einzelner Eintrag ist
                # die Leiste nach Entwurf ausgeblendet (v-if > 1) — beides ist
                # richtig; geprüft wird, dass KEIN Planungs-Reiter lockt.
                labels = list(mess.get("labels") or [])
                if "Dienstpläne" in labels or "Vorlagen" in labels:
                    fehler.append(f"mitglied/{lage}: sieht Reiter {labels}")
                # Die Planungsseite bleibt für Nicht-Planer gesperrt.
                page.goto(f"{BASE}/#/dienste/dienstplaene", wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)
                if "#/dienste/dienstplaene" in page.url:
                    fehler.append(f"mitglied/{lage}: „Dienstpläne“ ohne Recht erreichbar")
                context.close()

        browser.close()

    with open(os.path.join(ZIEL, f"{MARKER}-befund.json"), "w", encoding="utf-8") as fh:
        json.dump({"fehler": fehler, "notizen": notizen}, fh, ensure_ascii=False, indent=2)

    if fehler:
        print(f"[ux3c] {len(fehler)} Befund(e):", file=sys.stderr)
        for eintrag in fehler:
            print(f"  - {eintrag}", file=sys.stderr)
        return 1
    print("[ux3c] abgeschlossen ohne Befund")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
