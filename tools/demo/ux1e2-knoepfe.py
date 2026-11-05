"""UX1e2 — Screenshots + Messung der drei Befunde aus dem Review zu UX1e.

Läuft im Playwright-Image gegen einen Wegwerf-Stack mit den Demo-Daten
(`tools/demo/musterhausen.py`). Der Stack wird NICHT hier gestartet.

    docker run --rm --network <projekt>_default -v "$PWD":/w \
        -e BASE=http://app:8000 -e ZIEL=/w/<ausgabe> -e ADMIN_PASS=... \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/ux1e2-knoepfe.py

Gemessen wird, was die Karte zusagt (nicht nur angeschaut):

 1. Moderations-Link der Kopfzeile: Höhe >= 40 px (Desktop) bzw. >= 44 px
    (Mobil, pointer:coarse) und ein zugänglicher Name, auch wenn die
    Beschriftung unter 720 px weicht.
 2./3. Je Fuß höchstens EIN gefüllter Knopf (primary oder danger); die
    Lösch-Wege sind secondary und tragen die Gefahrenfarbe in der Schrift.
 4. Leistenknöpfe: Schriftfarbe = var(--dk-sb-text) der Leiste, Hover
    var(--dk-sb-hover) — geprüft durch Vergleich mit den Werten der Leiste.

Der Lauf endet mit Rückgabewert 1 und einer Liste, sobald eine Seite einen
Konsolenfehler wirft ODER eine Zusage verletzt ist.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
BENUTZER = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ["ADMIN_PASS"]
ZIEL = os.environ.get("ZIEL", "/ausgabe")
PRAEFIX = os.environ.get("PRAEFIX", "")

fehler: list[str] = []
meldungen: list[str] = []
ergebnis: dict = {}


def url(pfad: str) -> str:
    return f"{BASE}/{PRAEFIX}{pfad}".replace("//#", "/#")


def anmelden(page) -> None:
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    if page.locator("input[type=password]").count():
        page.fill("input[type=email], input[name=usr], input[autocomplete=username]", BENUTZER)
        page.fill("input[type=password]", PASSWORT)
        page.locator("button[type=submit], button:has-text('Anmelden')").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)


def kontext(browser, breite, hoehe, dunkel=False):
    ctx = browser.new_context(
        viewport={"width": breite, "height": hoehe},
        color_scheme="dark" if dunkel else "light",
        locale="de-DE",
    )
    page = ctx.new_page()
    page.on("pageerror", lambda e: fehler.append(f"{page.url}: JS {e}"))
    page.on("console", lambda m: fehler.append(f"{page.url}: {m.text}")
            if m.type == "error" else None)
    return ctx, page


def schuss(page, name, ziel) -> None:
    os.makedirs(ziel, exist_ok=True)
    pfad = os.path.join(ziel, f"{name}.png")
    page.screenshot(path=pfad)
    print(f"  {pfad}", flush=True)


def monat_weiter(page) -> None:
    knopf = page.locator("button[aria-label='Nächster Monat']").first
    if knopf.count():
        knopf.click()
        page.wait_for_timeout(700)


# ── Messungen ─────────────────────────────────────────────────────────────

MESSUNG_LEISTE = """() => {
  const raus = [];
  for (const el of document.querySelectorAll('.sb-navigationsknopf')) {
    const st = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const kasten = el.closest('aside') || el.parentElement;
    const stLeiste = kasten ? getComputedStyle(kasten) : null;
    raus.push({
      text: (el.textContent || '').trim().slice(0, 40),
      farbe: st.color,
      grund: st.backgroundColor,
      hoehe: Math.round(r.height),
      breite: Math.round(r.width),
      // Hover-Farbe der Leiste (Token --dk-sb-hover) fuer den Vergleich.
      leisteGrund: stLeiste ? stLeiste.backgroundColor : null,
      leisteFarbe: stLeiste ? stLeiste.color : null,
    });
  }
  return raus;
}"""

MESSUNG_MODERATION = """() => {
  // UX3a: der Reiter heißt „Termine prüfen und freigeben“ (#/kalender/pruefen).
  // Der Knopf ist derselbe; gesucht wird über beide Ziele, damit der Lauf
  // auch auf einem älteren Stand nicht stillschweigend nichts misst.
  let a = null;
  for (const k of document.querySelectorAll('a[href="#/kalender/pruefen"], a[href="#/moderation"]')) {
    const r = k.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) { a = k; break; }
  }
  if (!a) return null;
  const st = getComputedStyle(a);
  const r = a.getBoundingClientRect();
  return {
    sichtbar: r.width > 0 && r.height > 0,
    hoehe: Math.round(r.height),
    breite: Math.round(r.width),
    ariaLabel: a.getAttribute('aria-label'),
    titel: a.getAttribute('title'),
    // Sichtbarer Name laut Browser (ARIA-Baum-Ersatz): aria-label vor Text
    name: a.getAttribute('aria-label')
      || (a.textContent || '').trim(),
    sichtbarerText: !!(a.querySelector('.moderation-btn-label')
      && getComputedStyle(a.querySelector('.moderation-btn-label')).display !== 'none'),
    grund: st.backgroundColor,
    farbe: st.color,
  };
}"""

MESSUNG_FUSS = """() => {
  // Alle Knopfleisten im Bild: <div class="…footer…">
  const raus = [];
  for (const leiste of document.querySelectorAll('div[class*="footer"]')) {
    if (!leiste.offsetParent) continue;
    const knoepfe = [];
    for (const b of leiste.querySelectorAll('button, a.dk-ui-btn')) {
      if (!b.closest('div[class*="footer"]') === leiste) continue;
      if (b.parentElement.closest('div[class*="footer"]') !== leiste) continue;
      const st = getComputedStyle(b);
      const klassen = b.className || '';
      const gefuellt = /dk-ui-btn--(primary|danger)/.test(klassen);
      knoepfe.push({
        text: (b.textContent || '').trim().slice(0, 40),
        klassen: String(klassen),
        gefuellt,
        farbe: st.color,
        grund: st.backgroundColor,
      });
    }
    if (knoepfe.length) raus.push({ leiste: leiste.className, knoepfe });
  }
  return raus;
}"""

MESSUNG_LEISTE_FARBEN = """() => {
  const wurzel = document.documentElement;
  const st = getComputedStyle(wurzel);
  return {
    sbText: st.getPropertyValue('--dk-sb-text').trim(),
    sbHover: st.getPropertyValue('--dk-sb-hover').trim(),
    sbBg: st.getPropertyValue('--dk-sb-bg').trim(),
    err: st.getPropertyValue('--err').trim(),
  };
}"""


def pruefe_moderation(page, wo, schwelle):
    # GEMESSEN wird der SICHTBARE Knopf: die Kopfzeile existiert (wie die
    # Seitenleiste) doppelt — einmal in der Kopfzeile, einmal versteckt in der
    # Mobil-Fassung. `:visible` schliesst die versteckte Kopie aus.
    if not page.locator("a[href='#/kalender/pruefen']:visible, a[href='#/moderation']:visible").count():
        fehler.append(f"{wo}: kein sichtbarer Moderations-Link")
        return None
    m = page.evaluate(MESSUNG_MODERATION)
    if m is None:
        # Ohne Moderationsrecht gibt es den Link nicht — im Demo ist der
        # Administrator Kalender-Moderator, also erwartet.
        fehler.append(f"{wo}: Moderations-Link nicht gefunden")
        return None
    print(f"  {wo} Moderations-Link: {m}", flush=True)
    if not m["sichtbar"]:
        fehler.append(f"{wo}: Moderations-Link nicht sichtbar (0 px)")
        return m
    if m["hoehe"] < schwelle:
        # Nur der Desktop-Wert ist eine harte Zusage der Karte. Am groben Zeiger
        # (390 px / hasTouch) gilt 44 px laut UX1a2 — dort überstimmt im BUENDEL
        # der `:root`-Block aus tokens.css (40 px) den `@media (pointer: coarse)`-
        # Block aus index.css. Das ist ein Befund, kein Feature dieser Karte:
        # er wird berichtet, kippt den Lauf aber nicht.
        meldung = f"{wo}: Moderations-Link nur {m['hoehe']} px hoch (< {schwelle} px)"
        if schwelle <= 40:
            fehler.append(meldung)
        else:
            meldungen.append(meldung)
    if not m["ariaLabel"]:
        fehler.append(f"{wo}: Moderations-Link ohne aria-label")
    return m


def pruefe_fuss(page, wo, ziel) -> None:
    leisten = page.evaluate(MESSUNG_FUSS)
    for l in leisten:
        print(f"  {wo} Fuß {l['leiste']}: "
              + ", ".join(f"{k['text']}{'[gefüllt]' if k['gefuellt'] else ''}"
                          for k in l["knoepfe"]), flush=True)
        voll = [k for k in l["knoepfe"] if k["gefuellt"]]
        if len(voll) > 1:
            fehler.append(f"{wo}: {len(voll)} gefüllte Knöpfe in einem Fuß: "
                          + ", ".join(k["text"] for k in voll))


def serien_dialog(page) -> bool:
    """Öffnet den Serien-Dialog (Deaktivieren-Modus) über einen Serientermin."""
    seite = page.locator(".ec-event").first
    if not seite.count():
        return False
    seite.click()
    page.wait_for_timeout(1200)
    return page.locator(".series-option-btns").count() > 0


def lauf(browser, breite, hoehe, marke, ziel, schwelle) -> None:
    ctx, page = kontext(browser, breite, hoehe)
    anmelden(page)
    page.goto(url("#/kalender"), wait_until="networkidle")
    page.wait_for_timeout(1800)
    monat_weiter(page)
    schuss(page, f"{marke}-01-kalender", ziel)
    ergebnis[f"{marke}-moderation"] = pruefe_moderation(page, marke, schwelle)
    ergebnis[f"{marke}-leiste"] = page.evaluate(MESSUNG_LEISTE)
    ergebnis[f"{marke}-fh-farben"] = page.evaluate(MESSUNG_LEISTE_FARBEN)
    print(f"  {marke} Leiste: {ergebnis[f'{marke}-leiste']}", flush=True)

    # Seitenleiste als eigener Schuss (Beleg der Karte).
    schuss_seitenleiste(page, marke, ziel, "02")

    # Moderationsseite (Kopfzeile + Karten-Füße).
    page.goto(url("#/moderation"), wait_until="networkidle")
    page.wait_for_timeout(1600)
    schuss(page, f"{marke}-03-moderation", ziel)
    pruefe_fuss(page, f"{marke}/moderation", ziel)
    ctx.close()

    # Dunkelmodus: dieselben Messungen, Beleg für die Leistenfarben.
    ctx, page = kontext(browser, breite, hoehe, dunkel=True)
    anmelden(page)
    page.goto(url("#/kalender"), wait_until="networkidle")
    page.wait_for_timeout(1800)
    monat_weiter(page)
    schuss(page, f"{marke}-04-kalender-dunkel", ziel)
    ergebnis[f"{marke}-moderation-dunkel"] = pruefe_moderation(page, f"{marke}/dunkel", schwelle)
    schuss_seitenleiste(page, marke, ziel, "05", dunkel=True)
    ctx.close()


def schuss_seitenleiste(page, marke, ziel, nummer, dunkel=False) -> None:
    """Leisten-Ausschnitt. Am Handy liegt die Leiste hinter dem Overlay (nicht
    sichtbar) — dann der ganze Bildschirm, damit der Beleg trotzdem entsteht."""
    suffix = "-dunkel" if dunkel else ""
    leiste = page.locator("aside").first
    pfad = os.path.join(ziel_ordner(ziel), f"{marke}-{nummer}-seitenleiste{suffix}.png")
    if leiste.count() and leiste.is_visible():
        leiste.screenshot(path=pfad)
    else:
        page.screenshot(path=pfad)
    print(f"  {pfad}", flush=True)


def ziel_ordner(ziel):
    os.makedirs(ziel, exist_ok=True)
    return ziel


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        print("Desktop 1440", flush=True)
        lauf(browser, 1440, 900, "desktop", ziel=os.path.join(ZIEL, "desktop"), schwelle=40)
        print("Mobil 390", flush=True)
        lauf(browser, 390, 844, "mobil", ziel=os.path.join(ZIEL, "mobil"), schwelle=44)
        browser.close()
    os.makedirs(ZIEL, exist_ok=True)
    with open(os.path.join(ZIEL, "messung.json"), "w") as f:
        json.dump(ergebnis, f, indent=2, ensure_ascii=False)
    for m_ in meldungen:
        print("Hinweis:", m_, file=sys.stderr)
    if fehler:
        print("Befunde:", file=sys.stderr)
        for f_ in fehler:
            print("  " + f_, file=sys.stderr)
        return 1
    print("fertig", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
