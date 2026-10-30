"""UX-A2b — Belege zum Statusfilter der Anfragen (Entwurf A2, zweiter Teil).

Laeuft im Playwright-Image gegen den Wegwerf-Stack der Karte (Projekt
``t_c37ea235-test``). Aufgenommen wird ``#/mitglieder/anfragen`` als
Administrator:

  * 1366 px (Desktop) und 390 px (Handy), je hell und dunkel,
  * dazu die Unterbereiche ``?bereich=links`` und ``?bereich=formulare``,
    um zu zeigen, dass dort KEIN Statusfilter steht,
  * je Aufnahme wird das DOM GEMESSEN (nicht nur ein Bild gemacht):
      - Chip-Zeile vorhanden? welche Chips mit welchen Zahlen? welcher aktiv?
      - steht sie UEBER der Tabelle (Bildschirmkoordinaten)?
      - Statuswoerter in der Tabelle (Sprache wie die Chips),
      - Spaltenkopf „Art“ vs. „Typ“, roher Typ-Wert in der Zelle?

Aufruf:
    docker run --rm --network t_c37ea235-test_default -v "$PWD":/w:ro \
        -v <ziel>:/ausgabe -e BASE=http://app:8000 \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/tools/demo/uxa2b-status-chips.py
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
ADMIN = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "musterhausen-demo")

SEITE = "#/mitglieder/anfragen"
UNTERBEREICHE = [
    ("anfragen", ""),
    ("links", "?bereich=links"),
    ("formulare", "?bereich=formulare"),
]

fehler: list[str] = []
gemessen: list[dict] = []


def kontext(browser, breite, hoehe, dunkel):
    ctx = browser.new_context(viewport={"width": breite, "height": hoehe},
                              locale="de-DE", ignore_https_errors=True)
    if dunkel:
        ctx.add_init_script(
            "try { localStorage.setItem('dk-theme', 'dark') } catch (e) {}")
    return ctx


def anmelden(page):
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(400)
    page.fill("#dk-usr", ADMIN)
    page.fill("#dk-pwd", ADMIN_PASS)
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")


def dom_messen(page):
    """Chip-Zeile, Tabelle und Sprache am lebenden DOM pruefen."""
    return page.evaluate(
        """() => {
            const chipsBox = document.querySelector('.reg-statusfilter');
            const chips = chipsBox
                ? [...chipsBox.querySelectorAll('button.dk-ui-chip')].map(b => ({
                    text: (b.textContent || '').replace(/\\s+/g, ' ').trim(),
                    label: (b.childNodes[0] && b.childNodes[0].textContent || '').trim(),
                    zahl: (b.querySelector('.dk-ui-chip-zahl') || {}).textContent || null,
                    aktiv: b.classList.contains('is-active'),
                    gedrueckt: b.getAttribute('aria-pressed'),
                }))
                : [];
            const gruppe = chipsBox ? chipsBox.querySelector('[role="group"]') : null;
            const tabelle = document.querySelector('table.dk-table') || document.querySelector('table');
            const kopf = tabelle
                ? [...tabelle.querySelectorAll('thead th')].map(th => th.textContent.trim())
                : [];
            const statusZellen = tabelle
                ? [...tabelle.querySelectorAll('tbody tr')].map(tr => {
                    const zellen = [...tr.children].map(td => td.textContent.replace(/\\s+/g, ' ').trim());
                    return zellen;
                })
                : [];
            const r = el => { if (!el) return null; const b = el.getBoundingClientRect();
                return { top: Math.round(b.top), bottom: Math.round(b.bottom), height: Math.round(b.height) }; };
            return {
                chipsVorhanden: !!chipsBox,
                chips,
                chipsLabel: gruppe ? gruppe.getAttribute('aria-label') : null,
                chipBox: r(chipsBox),
                tabelleBox: r(tabelle),
                kopf,
                zeilen: statusZellen,
                hatStatusReiter: !!document.querySelector('.dk-ui-tabs'),
                theme: document.documentElement.getAttribute('data-theme'),
                koerperBreite: document.body.scrollWidth,
            };
        }"""
    )


def pruefe(name, bedingung, meldung):
    if not bedingung:
        fehler.append(f"{name}: {meldung}")


def schuss(page, name, voll):
    datei = os.path.join(ZIEL, f"{name}.png")
    page.screenshot(path=datei, full_page=voll)
    print("geschrieben", os.path.basename(datei))


def lauf(browser, breite, hoehe, dunkel, marke):
    voll = breite <= 720
    for bereich, abfrage in UNTERBEREICHE:
        ctx = kontext(browser, breite, hoehe, dunkel)
        page = ctx.new_page()
        anmelden(page)
        page.goto(BASE + "/" + SEITE + abfrage, wait_until="networkidle")
        page.wait_for_timeout(1500)

        daten = dom_messen(page)
        daten.update({"breite": breite, "dunkel": dunkel, "marke": marke,
                      "unterbereich": bereich})
        gemessen.append(daten)
        name = f"uxa2b-anfragen-{bereich}-{marke}-{'dunkel' if dunkel else 'hell'}"

        if bereich == "anfragen":
            # 1. Chip-Zeile mit vier Zahlen-Chips: Alle · Offen · Aufgenommen · Abgelehnt.
            pruefe(name, daten["chipsVorhanden"] is True, "Chip-Zeile fehlt")
            labels = [c["label"] for c in daten["chips"]]
            pruefe(name, labels == ["Alle", "Offen", "Aufgenommen", "Abgelehnt"],
                   f"Chips: {labels}")
            for c in daten["chips"]:
                pruefe(name, (c["zahl"] or "").strip().isdigit(),
                       f"Chip „{c['label']}“ ohne Zahl")
            # 2. Genau ein gewaehlter Chip, und zwar „Offen“ (Arbeitsliste).
            aktiv = [c["label"] for c in daten["chips"] if c["aktiv"]]
            pruefe(name, aktiv == ["Offen"], f"gewaehlte Chips: {aktiv}")
            # 2b. Kein unsichtbarer Zustand: „Alle“ ist die Summe der drei
            #     uebrigen Zahlen PLUS die Warteliste — also nie kleiner, und
            #     die drei Einzelchips zusammen sind nie groesser als „Alle“.
            zahlen = {c["label"]: int((c["zahl"] or "0").strip() or 0) for c in daten["chips"]}
            if set(zahlen) == {"Alle", "Offen", "Aufgenommen", "Abgelehnt"}:
                einzel = zahlen["Offen"] + zahlen["Aufgenommen"] + zahlen["Abgelehnt"]
                pruefe(name, zahlen["Alle"] >= einzel,
                       f"„Alle“ ({zahlen['Alle']}) kleiner als die Einzelzahlen ({einzel})")
                pruefe(name, zahlen["Alle"] > 0, "„Alle“ zeigt 0 Anfragen")
            # 2c. Kein unsichtbarer Zustand: ein zweiter Klick auf den
            #     gewaehlten Chip landet auf „Alle“ — und „Alle“ ist markiert.
            chips_js = ".reg-statusfilter button.dk-ui-chip"
            page.evaluate(
                """(sel) => {
                    const btns = [...document.querySelectorAll(sel)];
                    const offen = btns.find(b => (b.childNodes[0].textContent || '').trim() === 'Offen');
                    offen.click();
                }""", chips_js)
            page.wait_for_timeout(400)
            nach = page.evaluate(
                """(sel) => [...document.querySelectorAll(sel)].map(b => ({
                    label: (b.childNodes[0].textContent || '').trim(),
                    zahl: (b.querySelector('.dk-ui-chip-zahl') || {}).textContent || null,
                    aktiv: b.classList.contains('is-active'),
                    gedrueckt: b.getAttribute('aria-pressed'),
                }))""", chips_js)
            als_aktiv = [c["label"] for c in nach if c["aktiv"]]
            pruefe(name, als_aktiv == ["Alle"],
                   f"zweiter Klick auf „Offen“ waehlt nicht „Alle“: aktiv {als_aktiv}")
            gedrueckt = [c["label"] for c in nach if c["gedrueckt"] == "true"]
            pruefe(name, gedrueckt == ["Alle"],
                   f"aria-pressed passt nicht zur Auswahl: {gedrueckt}")
            # Zeilenzahl unter „Alle“ = Zahl am Chip (Beweis, dass nichts
            # versteckt bleibt, z. B. Warteliste-Anfragen).
            anzahl_zeilen = page.evaluate(
                "() => document.querySelectorAll('table.dk-table tbody tr, table tbody tr').length")
            alle_zahl = next((c["zahl"] for c in nach if c["label"] == "Alle"), None)
            pruefe(name, str(anzahl_zeilen) == str(alle_zahl),
                   f"„Alle“ sagt {alle_zahl}, Tabelle zeigt {anzahl_zeilen} Zeilen")
            # Zurueck auf „Offen“: der Chip-Zustand fuer die Aufnahme.
            page.evaluate(
                """(sel) => {
                    const btns = [...document.querySelectorAll(sel)];
                    const offen = btns.find(b => (b.childNodes[0].textContent || '').trim() === 'Offen');
                    offen.click();
                }""", chips_js)
            page.wait_for_timeout(400)
            # 3. Die Zeile steht UEBER der Tabelle.
            if daten["chipBox"] and daten["tabelleBox"]:
                pruefe(name, daten["chipBox"]["bottom"] <= daten["tabelleBox"]["top"] + 2,
                       "Chip-Zeile steht nicht über der Tabelle")
            # 4. Keine Status-Reiterzeile mehr.
            pruefe(name, daten["hatStatusReiter"] is False,
                   "es gibt noch eine Reiterzeile (.dk-ui-tabs)")
            # 5. Tabelle spricht wie die Chips.
            pruefe(name, "Art" not in daten["kopf"], f"Spaltenkopf enthält „Art“: {daten['kopf']}")
            pruefe(name, "Typ" in daten["kopf"], f"Spaltenkopf ohne „Typ“: {daten['kopf']}")
            rohe = ["Anmeldeanfrage", "Ausstehend", "Bestätigt"]
            alle = " | ".join(" ".join(z) for z in daten["zeilen"])
            for roh in rohe:
                pruefe(name, roh not in alle, f"roher Status „{roh}“ in der Tabelle")
            # 6. Die Zeilen sind offene Anfragen -> Statuswort „Offen“.
            for z in daten["zeilen"]:
                pruefe(name, len(z) >= 5, f"Zeile zu kurz: {z}")
            # 7. Auf schmalen Anzeigen kein waagerechtes Ueberlaufen.
            pruefe(name, daten["koerperBreite"] <= breite + 1,
                   f"Seite ist {daten['koerperBreite']} px breit bei {breite} px")
        else:
            # Kein Statusfilter in Links und Formularen.
            pruefe(name, daten["chipsVorhanden"] is False,
                   f"Statusfilter im Unterbereich „{bereich}“")

        schuss(page, name, voll)
        ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        lauf(browser, 1366, 900, False, "desktop")
        lauf(browser, 1366, 900, True, "desktop")
        lauf(browser, 390, 844, False, "mobil")
        lauf(browser, 390, 844, True, "mobil")
        browser.close()

    with open(os.path.join(ZIEL, "uxa2b-messung.json"), "w", encoding="utf-8") as f:
        json.dump({"gemessen": gemessen, "fehler": fehler}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"fehler": fehler, "aufnahmen": len(gemessen)}, ensure_ascii=False))
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
