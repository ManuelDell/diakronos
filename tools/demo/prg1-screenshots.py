"""PR-G1 — Belege: Stammdaten nach Geschlecht filtern und sortieren.

Läuft gegen den EIGENEN Wegwerf-Stack (Projekt `prg1`), nie gegen den
Betrieb. Musterhausen bringt echte Geschlechter mit („weiblich"/„männlich"
im Mitgliedsfeld); der Lauf setzt zusätzlich ein paar Personen OHNE Angabe
und eine „Divers"-Person — NUR in dieser Wegwerf-Datenbank.

    docker run --rm --network prg1_default \
        -v "<repo>/tools/demo:/w:ro" -v "<ziel>:/ausgabe" \
        -e BASE=http://app:8000 -e ZIEL=/ausgabe \
        mcr.microsoft.com/playwright/python:v1.49.0-noble \
        python /w/prg1-screenshots.py
"""

import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://app:8000")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORT = os.environ.get("ADMIN_PASS", "musterhausen-demo")
ZIEL = os.environ.get("ZIEL", "/ausgabe")
MARKER = os.environ.get("MARKER", "nachher")

os.makedirs(ZIEL, exist_ok=True)
belege: dict = {}


def anmelden(seite) -> None:
    seite.goto(f"{BASE}/login", wait_until="domcontentloaded")
    seite.fill('#dk-usr, input[name="usr"]', EMAIL)
    seite.fill('#dk-pwd, input[name="pwd"]', PASSWORT)
    seite.click('button[type="submit"]')
    seite.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    seite.wait_for_load_state("networkidle")


def thema(seite, dunkel: bool) -> None:
    wert = "dark" if dunkel else "light"
    seite.evaluate(
        "d => { document.documentElement.setAttribute('data-theme', d);"
        " localStorage.setItem('dk-theme', d); }",
        wert,
    )
    seite.wait_for_timeout(400)


def stammdaten(seite, plantyp: str) -> None:
    # Der Direktaufruf mit Planvorlagen-ID startet die Seite nicht (bekannter
    # Weg der Bestandstests): Adresse mit dem SCHLUESSEL der Vorlage.
    seite.goto(f"{BASE}/#/planrahmen/stammdaten/{plantyp}", wait_until="networkidle")
    # Auf die Personen-Matrix warten (Skelett → Tabelle), nicht blind pausieren.
    seite.wait_for_selector(".pr-stamm-tabelle", timeout=30000)
    seite.wait_for_timeout(800)


def personen_ids(seite) -> list:
    return seite.eval_on_selector_all(
        ".pr-stamm-tabelle tbody tr .pr-stamm-name-haupt",
        "els => els.map(e => e.textContent.trim())",
    )


def geschlechter(seite) -> list:
    return seite.eval_on_selector_all(
        ".pr-stamm-tabelle tbody tr .pr-stamm-geschlecht-wert",
        "els => els.map(e => e.textContent.trim())",
    )


def beleg_mobil(seite, pfad: str) -> bool:
    """Beleg am Handy: ECHTE 390 px breite Aufnahme (Review 09.11.).

    Frueher war das ein Element-Ausschnitt der Seite in Desktop-Breite — damit
    liess sich die schmale Ansicht nicht beurteilen. Jetzt: Handy-Kontext mit
    viewport 390 x 844, Seiten-Screenshot OHNE full_page (genau der sichtbare
    Bildschirm), nachdem die Filterleiste in den Blick gescrollt wurde.
    """
    if not seite.locator(".pr-stamm-filter").count():
        return False
    seite.locator(".pr-stamm-filter").scroll_into_view_if_needed()
    seite.wait_for_timeout(400)
    breite = seite.evaluate("() => window.innerWidth")
    assert breite == 390, f"Handy-Kontext muss 390 px breit sein, ist {breite}"
    seite.screenshot(path=pfad, animations="disabled")  # OHNE full_page
    return True


def waehle_geschlecht(seite, wert: str) -> None:
    seite.select_option(".pr-stamm-geschlechtwahl", wert)
    seite.wait_for_timeout(500)


with sync_playwright() as p:
    browser = p.chromium.launch()
    seite = browser.new_page(viewport={"width": 1440, "height": 1000})
    anmelden(seite)

    # Plantyp mit Personenmerkmalen finden (Musterhausen: Dienstplan-Vorlage).
    # Schluessel (nicht ID) der Vorlage — so adressieren die Bestandstests sie.
    plantyp = os.environ.get("PLANTYP", "chorplan")
    belege["plantyp"] = plantyp

    # ── Desktop hell: Filter „Alle", Filter „Männlich", Sortierung ─────────
    thema(seite, False)
    stammdaten(seite, plantyp)
    seite.screenshot(path=f"{ZIEL}/{MARKER}-desktop-1440-alle-hell.png", full_page=True)
    belege["alle"] = {"namen": personen_ids(seite), "geschlechter": geschlechter(seite)}

    waehle_geschlecht(seite, "m")
    seite.screenshot(path=f"{ZIEL}/{MARKER}-desktop-1440-filter-maennlich-hell.png", full_page=True)
    belege["maennlich"] = {"namen": personen_ids(seite), "geschlechter": geschlechter(seite)}

    # Massenauswahl folgt dem Filter
    kopf_kaestchen = seite.locator(
        ".pr-stamm-tabelle thead input[type=checkbox]").first
    if kopf_kaestchen.count():
        kopf_kaestchen.check()
        seite.wait_for_timeout(400)
        belege["massenauswahl_text"] = seite.locator(".pr-stamm-masse-zahl").first.text_content().strip()
        seite.screenshot(path=f"{ZIEL}/{MARKER}-desktop-1440-massnahme-maenner-hell.png", full_page=True)

    # Sortierung über den Spaltenkopf
    waehle_geschlecht(seite, "")
    kopf = seite.locator(".pr-stamm-sortknopf").first
    kopf.click()
    seite.wait_for_timeout(500)
    belege["sortiert_auf"] = {"namen": personen_ids(seite), "geschlechter": geschlechter(seite),
                              "aria": seite.get_attribute(".pr-stamm-spalte-geschlecht", "aria-sort")}
    seite.screenshot(path=f"{ZIEL}/{MARKER}-desktop-1440-sortiert-geschlecht-hell.png", full_page=True)
    kopf.click()
    seite.wait_for_timeout(500)
    belege["sortiert_ab"] = {"geschlechter": geschlechter(seite),
                             "aria": seite.get_attribute(".pr-stamm-spalte-geschlecht", "aria-sort")}

    # Ohne Angabe
    waehle_geschlecht(seite, "ohne")
    belege["ohne"] = {"namen": personen_ids(seite), "geschlechter": geschlechter(seite)}
    seite.screenshot(path=f"{ZIEL}/{MARKER}-desktop-1440-filter-ohne-angabe-hell.png", full_page=True)
    waehle_geschlecht(seite, "")

    # ── Desktop dunkel ────────────────────────────────────────────────────
    thema(seite, True)
    waehle_geschlecht(seite, "m")
    seite.screenshot(path=f"{ZIEL}/{MARKER}-desktop-1440-filter-maennlich-dunkel.png", full_page=True)
    waehle_geschlecht(seite, "")

    # ── Mobil 390 ─────────────────────────────────────────────────────────
    thema(seite, False)
    # Handy = grober Zeiger: eigener Kontext, sonst misst man die Desktop-Flächen.
    seite.close()
    handy = browser.new_context(viewport={"width": 390, "height": 844},
                                has_touch=True, is_mobile=True)
    seite = handy.new_page()
    anmelden(seite)
    stammdaten(seite, plantyp)
    waehle_geschlecht(seite, "m")
    # Beleg am Handy: Filter + Tabelle im Bild (Ausschnitt ab der Filterleiste).
    assert beleg_mobil(seite, f"{ZIEL}/{MARKER}-mobil-390-filter-maennlich-hell.png")
    belege["mobil_klickflaeche"] = seite.eval_on_selector(
        ".pr-stamm-geschlechtwahl", "e => e.getBoundingClientRect().height")
    belege["mobil_sortknopf"] = seite.eval_on_selector(
        ".pr-stamm-sortknopf", "e => e.getBoundingClientRect().height")
    # Mit Sortierung auf dem Handy
    seite.select_option(".pr-stamm-geschlechtwahl", "")
    seite.locator(".pr-stamm-sortknopf").first.click()
    seite.wait_for_timeout(500)
    assert beleg_mobil(seite, f"{ZIEL}/{MARKER}-mobil-390-sortiert-hell.png")

    thema(seite, True)
    assert beleg_mobil(seite, f"{ZIEL}/{MARKER}-mobil-390-sortiert-dunkel.png")

    # Filter „Männlich" am Handy (eigene echte 390-px-Aufnahme)
    thema(seite, False)
    seite.select_option(".pr-stamm-geschlechtwahl", "m")
    seite.wait_for_timeout(500)
    assert beleg_mobil(seite, f"{ZIEL}/{MARKER}-mobil-390-filter-maennlich-390px-hell.png")
    belege["mobil_breite"] = seite.evaluate("() => window.innerWidth")

    with open(f"{ZIEL}/{MARKER}-messung.json", "w", encoding="utf-8") as fh:
        json.dump(belege, fh, ensure_ascii=False, indent=2)
    browser.close()

print("PR-G1 Belege fertig:", ZIEL)
