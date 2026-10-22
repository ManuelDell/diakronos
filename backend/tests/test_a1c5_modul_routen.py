"""A1c5 — Modul-Routen zeigen nicht mehr ins Leere.

BEFUND (gemessen am laufenden Stack, mit gueltiger Sitzung)
----------------------------------------------------------
`get_accessible_modules()` lieferte die Original-Routen aus
`MODULE_ROUTES` (`/app/kronos`, `/kronos`, `/psalmos`) bzw. den Fallback
`/app/<modul>`. Diese Pfade sind echte Frappe-www-Seiten; der Standalone-Stack
liefert nur die SPA unter `/diakonos`. Jeder Klick auf eine Modul-Route
landete deshalb auf einem nackten 404:

    /app/kronos   -> 404      /kronos   -> 404
    /app/diakonos -> 404      /psalmos  -> 404
    /diakonos     -> 200 (SPA)

Die Werte waren allerdings LATENT: `boot.modules` wird in `frontend/src`
nirgends angesteuert (`useSession.js:14/46` ist der einzige Leser, keine
Komponente rendert `route`). Sichtbar wird es erst, wenn das Modulmenue gebaut
wird. Der Wert war trotzdem falsch — er beschrieb eine Deployment-Form, die
dieser Stack nicht hat.

WAS DIESE TESTS FESTNAGELN
--------------------------
1. `route` zeigt in die SPA (`#/kalender`, `#/mitglieder`, `#/lieder`) — belegt
   aus `MODULE_PAGES` des Referenz-Repos, nicht erfunden. Form ist
   hash-relativ, damit `navigate(route)` und `<a :href>` beide tragen.
2. Module ohne SPA-Entsprechung (`Diakronos`, `Seelsorge`) bekommen den
   Schluessel `route` GAR NICHT — kein `null`, kein toter Link.
3. Die Altpfade liefern mit Sitzung 307 auf die SPA (kein 404 mehr) und ohne
   Sitzung die Login-Maske (kein 404, keine Existenz-Auskunft).
4. `/app/kronos` bleibt 404 — es ist der Workspace-Pfad des Originals, fuer den
   dieser Stack keine Seite hat. Bewusste Ausnahme, im Code kommentiert.
5. Kein `/app/*`-Blanket: `/app/google-kalender-import` (hart verlinkt im
   Kronos-Sidebar) wird NICHT umgebogen, sonst wuerde ein echter Fehler still
   repariert.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diakronos_app.api.kronos.permissions import (
    KNOWN_MODULES,
    MODULE_ROUTES,
    MODUL_ZIEL_SPA,
)
from diakronos_app.main import app
from diakronos_app.spa import _altpfad_redirects

# Dieselbe Konstante, die `test_a1b2_rest_boot_login.py` benutzt: das
# Passwort-Feld der Maske. Bewusst nicht neu erfunden — ein zweiter Marker
# waere eine zweite Wahrheit darueber, was die Login-Maske ist.
LOGIN_MASKEN_MARKER = 'name="pwd"'


@pytest.fixture()
def angemeldet(patched_db, fake_redis):
    """Client MIT gueltiger Sitzung — sieht die SPA.

    `Diakronos Einstellungen` (Single) wird hier geschrieben: `get_accessible_modules()`
    liefert OHNE diese Zeile `[]` (`permissions.py:306`), und ein leeres
    Modul-Array wuerde jeden Route-Test still bestehen lassen, ohne etwas zu
    pruefen. Dieselbe Quelle wie im Betrieb.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    sess = patched_db()
    zeile = sess.get(DiakronosEinstellungen, "Diakronos Einstellungen")
    if zeile is None:
        zeile = DiakronosEinstellungen(
            name="Diakronos Einstellungen", docstatus=0, idx=0
        )
        sess.add(zeile)
    # Alle fuenf Module sichtbar, damit der Rueckfall-Pfad (`/app/<modul>`)
    # und der Sonderfall `Seelsorge` mitgetestet werden.
    for prefix in ("diakronos", "kronos", "diakonos", "psalmos", "seelsorge"):
        setattr(zeile, f"{prefix}_sichtbar", 1)
    sess.commit()
    # B1: `Administrator` braucht eine `user`-Zeile, sonst ist die Sitzung
    # nach der neuen Regel im `Guest` (die Middleware prueft das jetzt).
    if sess.get(User, "Administrator") is None:
        sess.add(User(
            name="Administrator", email="Administrator",
            full_name="Administrator", enabled=True,
        ))
        sess.commit()
    sess.close()

    sid, csrf = sitzungen.anlegen("Administrator")
    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        # Echter CSRF-Token der Sitzung — ein POST ohne ihn wird mit 417
        # abgelehnt (CsrfMiddleware), das waere ein Fehlbefund im Test.
        c.headers["X-Frappe-CSRF-Token"] = csrf
        yield c


@pytest.fixture()
def gast(patched_db, fake_redis):
    """Client OHNE Sitzung."""
    with TestClient(app) as c:
        yield c


def _module(modules, name):
    for m in modules:
        if m.get("module_name") == name:
            return m
    return None


def _module_liste(client: TestClient) -> list[dict]:
    """`get_accessible_modules()` ueber die oeffentliche Frappe-kompatible API."""
    resp = client.post(
        "/api/method/diakronos.kronos.api.permissions.get_accessible_modules", json={}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["message"]


# ── 1. Die Route zeigt in die SPA ────────────────────────────────────────────

def test_route_zeigt_in_die_spa(angemeldet):
    """Die Modul-Route ist ein SPA-Hash, kein Frappe-Pfad."""
    ziele = {m["module_name"]: m.get("route") for m in _module_liste(angemeldet)}
    assert ziele.get("Kronos") == "#/kalender", ziele
    assert ziele.get("Diakonos") == "#/mitglieder", ziele


def test_route_ist_hash_relativ_und_nie_absolut(angemeldet):
    """Kein Wert darf ein absoluter Pfad sein — nur so kann er keinen 404 bauen.

    Ein hash-relativer Wert verlaesst das Dokument nie; `/diakonos#/kalender`
    waere zwar ebenfalls keine 404-Quelle, aber `navigate()` (router.js:121-128)
    macht daraus `#/diakonos#/kalender` — die Form waere also nur fuer einen
    der beiden gaengigen Aufrufer richtig.
    """
    for m in _module_liste(angemeldet):
        route = m.get("route")
        if route is None:
            continue
        assert route.startswith("#/"), f"{m['module_name']}: {route!r} ist nicht hash-relativ"
        assert SPA_PREFIX_NOT_IN_ROUTE not in route, f"{m['module_name']}: Praefix im Hash"


SPA_PREFIX_NOT_IN_ROUTE = "/diakonos"


def test_route_stammt_aus_module_pages_des_referenz(angemeldet):
    """Die Zuordnung ist belegt, nicht geraten — hier festgeschrieben.

    `MODULE_PAGES` im Referenz-Repo
    (`diakronos/doctype/diakronos_einstellungen/diakronos_einstellungen.py:52`)
    ist die Liste, aus der auch der Original-Hub seine Seiten nimmt
    (`www/kronos/index.py:47`). Faellt sie auseinander, faellt dieser Test.
    """
    erwartet = {
        "Kronos": ("kalender", "#/kalender"),
        "Diakonos": ("mitglieder", "#/mitglieder"),
        "Psalmos": ("lieder", "#/lieder"),
    }
    assert set(MODUL_ZIEL_SPA) == set(erwartet), MODUL_ZIEL_SPA
    for modul, (_werkzeug, ziel) in erwartet.items():
        assert MODUL_ZIEL_SPA[modul] == ziel, modul


def test_alle_zeit_mit_werkzeug_aus_module_pages_belegbar():
    """Jedes Ziel zeigt auf eine Seite, die der Werkzeug-Liste entspricht.

    Absicht ist der Nachweis, dass kein Ziel frei erfunden ist: die
    Werkzeug-Schluessel sind die, die der Original-Hub anzeigt.
    """
    werkzeug_je_modul = {
        "Kronos": "kalender",
        "Diakonos": "mitglieder",
        "Psalmos": "lieder",
    }
    for modul, ziel in MODUL_ZIEL_SPA.items():
        werkzeug = werkzeug_je_modul[modul]
        assert ziel == f"#/{werkzeug}", f"{modul}: {ziel} passt nicht zu {werkzeug!r}"


# ── 2. Ohne SPA-Entsprechung: kein `route` ───────────────────────────────────

def test_modul_ohne_spa_seite_hat_kein_route_feld(angemeldet):
    """`Diakronos` hat keine SPA-Seite -> der Schluessel fehlt vollstaendig.

    Kein `None`: `href=null` laedt im Browser die Seite neu, `route: null` ist
    also ein Fallstrick. Ein fehlender Schluessel ist ehrlich lesbar.
    """
    m = _module(_module_liste(angemeldet), "Diakronos")
    assert m is not None, "Diakronos sollte als Admin sichtbar sein"
    assert "route" not in m, m
    # Und selbstverstaendlich: kein 404-Wert im Boot-Objekt.
    assert not str(m.get("route", "")).startswith("/app")


def test_route_fehlt_auch_im_boot_objekt(angemeldet):
    """Dieselbe Liste landet im Boot-Objekt — dort darf kein toter Pfad stehen."""
    resp = angemeldet.get("/diakonos")
    assert resp.status_code == 200
    assert '"route":"#/kalender"' in resp.text.replace(" ", ""), (
        "SPA-Ziel fehlt im Boot-Objekt"
    )
    assert "/app/kronos" not in resp.text, "toter Frappe-Pfad im Boot-Objekt"


def test_seelsorge_ohne_spa_seite(angemeldet):
    """`Seelsorge` ist in `MODUL_ZIEL_SPA` gar nicht enthalten — so gewollt."""
    assert "Seelsorge" not in MODUL_ZIEL_SPA


# ── 3. Altpfade: 307 mit Sitzung, Login-Maske ohne ───────────────────────────

def test_altpfad_tabelle_kommt_aus_einer_quelle(angemeldet):
    """Jeder Redirect-Pfad ist eine echte Frappe-Route mit SPA-Ziel.

    Damit kann die Tabelle nicht von `MODULE_ROUTES` weglaufen: ein Modul ohne
    SPA-Ziel erzeugt keinen Redirect (sonst gaebe es eine Route ohne Ziel).
    """
    tabelle = _altpfad_redirects()
    assert tabelle, "keine Altpfade gebaut"
    for pfad, ziel in tabelle.items():
        assert ziel.startswith("#/"), f"{pfad} -> {ziel}"
        assert pfad in MODULE_ROUTES.values() or pfad.startswith("/app/"), pfad
        modul = next(
            (m for m, r in MODULE_ROUTES.items() if r == pfad), None
        )
        if modul is not None:
            assert MODUL_ZIEL_SPA.get(modul) == ziel, f"{modul}: {ziel}"


@pytest.mark.parametrize("altpfad", ["/kronos", "/psalmos", "/app/diakonos"])
def test_altpfad_mit_sitzung_redirectet_in_die_spa(angemeldet, altpfad):
    """MIT Sitzung: 307 auf `/diakonos/<ziel>` — kein 404 mehr."""
    resp = angemeldet.get(altpfad, follow_redirects=False)
    assert resp.status_code == 307, f"{altpfad} -> {resp.status_code}"
    ziel = _altpfad_redirects()[altpfad]
    assert resp.headers["location"] == f"/diakonos/{ziel}", resp.headers["location"]


@pytest.mark.parametrize("altpfad", ["/kronos", "/psalmos", "/app/diakonos"])
def test_altpfad_ohne_sitzung_zeigt_loginmaske(angemeldet, gast, altpfad):
    """OHNE Sitzung: die Maske — nicht 404, nicht die Existenz-Auskunft."""
    resp = gast.get(altpfad)
    assert resp.status_code == 200, f"{altpfad} -> {resp.status_code}"
    assert LOGIN_MASKEN_MARKER in resp.text, "keine Anmeldemaske"
    assert "__DIakonosBOOT" not in resp.text, "SPA ohne Anmeldung ausgegeben"
    assert resp.headers["cache-control"].startswith("no-store")


@pytest.mark.parametrize("altpfad", ["/kronos", "/psalmos", "/app/diakonos"])
def test_altpfad_redirectto_ist_ein_pfad_ohne_fragment(angemeldet, gast, altpfad):
    """Das versteckte Feld traegt den Pfad, NICHT `#/kalender`.

    `_redirect_ziel` (auth.py) laesst nur pfadrelative Ziele durch; ein
    Fragment gehoert nicht in einen Pfad. Steht dort ein `#`, faellt der Wert
    still auf `/diakonos` zurueck und der alte Link verliert sein Ziel.
    """
    resp = gast.get(altpfad)
    import re
    from urllib.parse import unquote

    m = re.search(r'name="redirect-to" value="([^"]*)"', resp.text)
    assert m, "kein redirect-to-Feld"
    wert = unquote(m.group(1))
    assert wert == altpfad, wert
    assert "#" not in wert, f"Fragment im redirect-to: {wert!r}"


def test_altpfad_nach_login_ankommt_man_beim_ziel(angemeldet, gast):
    """Vollstaendige Kette: Maske -> Login -> 307 -> SPA-Seite.

    Der Login-Sprung landet auf dem ALTpfad (siehe Test oben); dass von dort
    die SPA erreicht wird, ist der Punkt der ganzen Kette.
    """
    resp = gast.get("/kronos")
    assert LOGIN_MASKEN_MARKER in resp.text
    # Ab hier ist die Sitzung da (Fixture `angemeldet`).
    folge = angemeldet.get("/kronos", follow_redirects=False)
    assert folge.status_code == 307
    assert folge.headers["location"] == "/diakonos/#/kalender"
    # Und die Zielseite selbst ist die SPA, nicht der 404.
    ziel = angemeldet.get("/diakonos/#/kalender")
    assert ziel.status_code == 200
    assert "__DIakonosBOOT" in ziel.text


# ── 4./5. Bewusste Ausnahme und kein Blanket ────────────────────────────────

def test_app_kronos_bleibt_404_bewusst(angemeldet):
    """/app/kronos hat in der SPA keine Entsprechung — das ist Absicht.

    `MODULE_ROUTES["Diakronos"]` zeigt im Original auf die Frappe-Desk-Seite;
    im Original hat `Diakronos` ein LEERES `MODULE_PAGES` ("kein Hub, direkt
    zu Workspace"). Ein Workspace existiert hier nicht. Ihn auf `#/kalender`
    zu biegen, waere eine erfundene Zuordnung.
    """
    assert MODULE_ROUTES["Diakronos"] == "/app/kronos"
    assert "Diakronos" not in MODUL_ZIEL_SPA
    resp = angemeldet.get("/app/kronos")
    assert resp.status_code == 404, f"/app/kronos -> {resp.status_code}"


def test_kein_blanket_ueber_app(angemeldet):
    """`/app/google-kalender-import` wird NICHT umgebogen.

    Absichtlich KEIN Praefix-Match: der Pfad ist im Kronos-Sidebar hart
    verlinkt und sein 404 ist ein eigener, anders zu loesender Befund. Ein
    Blanket wuerde ihn still "reparieren" und damit zementieren.
    """
    assert "/app/google-kalender-import" not in _altpfad_redirects()
    resp = angemeldet.get("/app/google-kalender-import")
    assert resp.status_code == 404, f"-> {resp.status_code}"


def test_unbekannter_app_pfad_bleibt_404(angemeldet):
    """/app/gibt-es-nicht bleibt 404 — die Tabelle ist exakt, nicht praefixuell."""
    assert angemeldet.get("/app/gibt-es-nicht").status_code == 404


# ── Sonstiges: der Stack bleibt unberuehrt ───────────────────────────────────

def test_gesundheitspfad_bleibt_404(angemeldet):
    """`/kronos/healthz` ist kein Modulpfad — kein Blanket."""
    assert angemeldet.get("/kronos/healthz").status_code == 404


def test_spa_prefix_unveraendert(angemeldet):
    """Der Präfix der SPA bleibt `/diakonos` — diese Karte aendert ihn nicht."""
    assert angemeldet.get("/diakonos").status_code == 200
    assert angemeldet.get("/diakonos/mitglieder").status_code == 200


def test_known_modules_unveraendert():
    """Die Modulliste selbst wird nicht angefasst — nur `route`."""
    assert [name for _prefix, name in KNOWN_MODULES] == [
        "Diakronos",
        "Kronos",
        "Diakonos",
        "Psalmos",
        "Seelsorge",
    ]
