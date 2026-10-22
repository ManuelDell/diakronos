"""Tests fuer die SPA-Auslieferung unter /diakonos.

Diese Tests sichern vier Fehler ab, die beim ersten echten Aufruf auftraten und
ohne Browser/Viewer unsichtbar geblieben waeren:

1. Ein `StaticFiles`-Mount auf `/diakonos/assets/` verschattete alle Dateien,
   die im Build nicht unter `assets/` liegen (Entry-JS im Root, `css/`,
   `chunks/`, Fonts) -> die SPA lud NULL JavaScript.
2. Das globale Stylesheet liegt im Manifest unter dem Schluessel `style.css`,
   NICHT in `css` des Eintrags (das ist bei allen Eintraegen leer). Ohne
   explizites Einbinden kam die SPA voellig ungestylt zurueck.
3. Die Font-URLs im CSS zeigen auf `assets/assets/<font>` (Vite `base`
   '/diakonos/assets/' + Build-Unterordner 'assets/') -> doppelter Praefix.
4. Der Asset-Index war nach Basename verschluesselt, der Abruf erfolgt aber mit
   dem vollen Manifest-Pfad ('chunks/x.js') -> Lookup traf nie.

A1b2-rest — Anpassung dieser Datei
---------------------------------
Seit der Umschaltung liefert `/diakonos` OHNE Sitzung die Anmeldemaske statt
der SPA. Die Tests hier pruefen weiterhin die reine Auslieferung, brauchen
aber eine gueltige Sitzung, damit sie die SPA sehen. Deshalb bekommen sie
ueber `client` (angemeldet) bzw. `gast_client` (ohne Sitzung) zwei Blickwinkel.
Die inhaltlichen Pruefungen des Boot-Objekts (echte Werte, kein Dummy) und
der Login-Maske stehen in `test_a1b2_rest_boot_login.py`.

Die Tests laufen ohne Browser und ohne laufende Abhaengigkeiten (Postgres,
Redis) — sie pruefen die reine Auslieferung.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from diakronos_app.main import app
from diakronos_app.spa import SPA_DIST, _asset_index, _entry_assets, render_index


@pytest.fixture()
def client(patched_db, fake_redis):
    """ANGEMELDETER Client — sieht die SPA.

    Seit A1b2-rest liefert die Route ohne Sitzung die Login-Maske. Fuer die
    Auslieferungs-Pruefungen interessiert aber das HTML der SPA, also wird
    eine echte Sitzung als Cookie gesetzt. (Die Werte des Boot-Objekts sind
    nicht Gegenstand dieser Datei.)

    Funktions-, nicht Modul-Scope: `patched_db`/`fake_redis` aus `conftest.py`
    sind funktions-scoped, und ein Modul-Fixture darf sie nicht anfordern.

    **B1**: Die `user`-Zeile fuer `Administrator` wird hier mitangelegt. Seit
    B1 prueft die `SessionMiddleware` bei jedem Aufruf, ob der Benutzer der
    Sitzung noch in der `user`-Tabelle steht — ohne die Zeile waere der
    Fixture ein `Guest` und wuerde die Loginmaske statt der SPA sehen. Der
    Test prueft die Auslieferung, nicht die Kontoverwaltung; die Zeile zu
    legen ist die kleinste Anpassung, die die Regel nicht aufweicht.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User

    sess = patched_db()
    if sess.get(User, "Administrator") is None:
        sess.add(User(
            name="Administrator", email="Administrator",
            full_name="Administrator", enabled=True,
        ))
        sess.commit()
    sess.close()

    sid, _csrf = sitzungen.anlegen("Administrator")
    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        yield c


@pytest.fixture()
def gast_client(patched_db, fake_redis):
    """Client OHNE Sitzung — sieht die Login-Maske, aber keine SPA."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def manifest() -> dict:
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden — 'npm run build' in frontend/ ausfuehren.")
    path = SPA_DIST / ".vite" / "manifest.json"
    if not path.is_file():
        pytest.skip(f"Kein Vite-Manifest unter {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_und_manifest_vorhanden() -> None:
    """Der Build muss existieren, sonst ist jeder weitere Test sinnlos."""
    assert SPA_DIST is not None, "SPA_DIST nicht gefunden — 'npm run build' in frontend/"
    assert (SPA_DIST / ".vite" / "manifest.json").is_file()


def test_index_liefert_html(client: TestClient) -> None:
    resp = client.get("/diakonos")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert 'id="app"' in resp.text


def test_boot_objekt_hat_alle_vom_spa_gelesenen_felder(client: TestClient) -> None:
    """Die SPA liest genau diese Felder (siehe frontend/BOOT_VERTRAG.md)."""
    resp = client.get("/diakonos")
    assert "window.__DIakonosBOOT" in resp.text
    # Alle Felder, die die SPA tatsaechlich konsumiert.
    for feld in (
        "user_fullname",
        "user_email",
        "user_image",
        "csrf_token",
        "is_admin",
        "church_name",
        "logo_url",
        "mitglied",
        "modules",
    ):
        assert f"&quot;{feld}&quot;" in resp.text or f'"{feld}"' in resp.text, (
            f"Boot-Feld {feld} fehlt im injizierten Objekt"
        )


def test_boot_steht_vor_dem_entry_script(client: TestClient) -> None:
    """Die SPA liest __DIakonosBOOT synchron beim Modul-Import."""
    html = client.get("/diakonos").text
    assert html.index("__DIakonosBOOT") < html.index('type="module"')


def test_globales_stylesheet_wird_verlinkt(client: TestClient) -> None:
    """Regression: 'style.css' steht NICHT in `css` des Eintrags.

    Ohne explizite Behandlung fehlt das <link rel="stylesheet"> komplett und die
    SPA rendert ungestylt.
    """
    resp = client.get("/diakonos")
    assert 'rel="stylesheet"' in resp.text, "Kein Stylesheet-Link — SPA bleibt ungestylt"
    assert ".css" in resp.text


def test_entry_assets_liefert_css(client: TestClient, manifest: dict) -> None:
    """_entry_assets muss das globale Stylesheet mitliefern."""
    if "src/diakonos/main.js" not in manifest:
        pytest.skip("Eintrag src/diakonos/main.js nicht im Manifest")
    js_url, css_urls = _entry_assets("src/diakonos/main.js")
    assert js_url is not None
    assert css_urls, "Keine CSS-URLs — globales 'style.css' wird ignoriert"


@pytest.mark.parametrize(
    "route",
    ["diakonos", "admin", "gast", "registrierung", "organigramm"],
)
def test_alle_eintraege_liefern_script_tag(client: TestClient, route: str) -> None:
    """Jeder der fuenf Eintraege muss ein eigenes Modul-Script ausliefern."""
    resp = client.get(f"/diakonos/{route}")
    assert resp.status_code == 200
    assert 'type="module"' in resp.text
    assert "/diakonos/assets/" in resp.text


def test_jede_asset_url_aus_dem_manifest_ist_abrufbar(
    client: TestClient, manifest: dict
) -> None:
    """Der Kern-Regressionstest.

    Jede im Manifest referenzierte Datei muss ueber den URL-Pfad erreichbar
    sein, den die SPA bzw. das CSS tatsaechlich anfragt. Deckt die Bug-Klassen
    1 (Mount verschattet), 3 (doppelter assets/-Praefix) und 4 (Basename-Index)
    in einem Rutsch ab.
    """
    geprueft = 0
    fehler: list[str] = []
    for rec in manifest.values():
        dateien = []
        if rec.get("file"):
            dateien.append(rec["file"])
        dateien.extend(rec.get("css") or [])
        dateien.extend(rec.get("assets") or [])
        for f in dateien:
            urls = [f"/diakonos/assets/{f}"]
            # Fonts werden im CSS mit doppeltem 'assets/' referenziert.
            if f.startswith("assets/"):
                urls.append(f"/diakonos/assets/{f}")
                urls.append(f"/diakonos/assets/assets/{f[len('assets/'):]}")
            for u in urls:
                resp = client.get(u)
                if resp.status_code != 200:
                    fehler.append(f"{resp.status_code} {u}")
                geprueft += 1
    assert geprueft > 0, "Keine Assets im Manifest gefunden"
    assert not fehler, "Nicht abrufbare Assets:\n" + "\n".join(fehler[:20])


def test_asset_index_deckt_alle_manifest_eintraege() -> None:
    """Jede Manifest-Referenz muss im Index aufloesbar sein."""
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    man = json.loads((SPA_DIST / ".vite" / "manifest.json").read_text(encoding="utf-8"))
    index = _asset_index()
    assert index, "Asset-Index ist leer"
    fehlend: list[str] = []
    for rec in man.values():
        for f in [rec.get("file")] + list(rec.get("css") or []) + list(rec.get("assets") or []):
            if f and f not in index:
                fehlend.append(f)
    assert not fehlend, f"Nicht im Index aufloesbar: {fehlend}"


def test_css_und_chunks_werden_ausgeliefert(client: TestClient) -> None:
    """Regression: Dateien unter css/ und chunks/ waren durch den Mount 404."""
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    css = list((SPA_DIST / "css").glob("*.css"))
    chunks = list((SPA_DIST / "chunks").glob("*.js"))
    assert css, "Kein CSS im Build"
    assert chunks, "Keine Chunks im Build"
    assert client.get(f"/diakonos/assets/css/{css[0].name}").status_code == 200
    assert client.get(f"/diakonos/assets/chunks/{chunks[0].name}").status_code == 200


def test_reservierte_praefixe_werden_nicht_ausgeliefert(client: TestClient) -> None:
    """/diakonos/healthz und /diakonos/api/* duerfen NICHT die SPA liefern."""
    for pfad in ("diakonos/healthz", "diakonos/api/method/x", "diakonos/docs"):
        assert client.get(f"/{pfad}").status_code == 404, pfad
    # Die echte Route bleibt erreichbar (Catch-all verschattet sie nicht).
    assert client.get("/healthz").status_code == 200


@pytest.mark.parametrize(
    "boese",
    [
        "../../../../etc/passwd",
        "..%2f..%2f..%2fetc%2fpasswd",
        "assets/../../../etc/passwd",
        "....//....//etc/passwd",
    ],
)
def test_kein_path_traversal(client: TestClient, boese: str) -> None:
    """Traversal darf niemals Dateien ausserhalb des Build-Verzeichnisses liefern.

    Erwartet wird der SPA-Fallback (HTML), aber NIEMALS der Inhalt von
    /etc/passwd.
    """
    resp = client.get(f"/diakonos/{boese}")
    assert "root:x:0:0" not in resp.text


def test_render_index_ohne_boot_holt_das_echte_objekt() -> None:
    """`render_index()` ohne uebergebenes Boot holt es selbst.

    Seit A1b2-rest gibt es kein `DUMMY_BOOT` mehr: `boot=None` bedeutet
    "bau es aus der laufenden Sitzung". Ausserhalb eines Requests (hier) ist
    der Benutzer `Guest`, also muss trotzdem ein vollstaendiges Objekt mit
    allen Feldern der SPA herauskommen — mit leeren Werten, aber mit der
    richtigen Struktur. Ein Exception waere hier ein Bug: die Route ruft
    `render_index` in jedem Fall auf.
    """
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    html = render_index("src/diakonos/main.js")
    assert "__DIakonosBOOT" in html
    m = re.search(r"window\.__DIakonosBOOT\s*=\s*(\{.*?\});", html, re.DOTALL)
    assert m, "Boot-Objekt nicht injiziert"
    boot = json.loads(m.group(1))
    for feld in (
        "user_fullname", "user_email", "user_image", "csrf_token",
        "is_admin", "church_name", "logo_url", "mitglied", "modules",
    ):
        assert feld in boot, f"Boot-Feld {feld} fehlt"
    # Ohne Sitzung: nichts erfunden.
    assert boot["is_admin"] is False
    assert boot["csrf_token"] == ""
    assert boot["mitglied"] is None


def test_render_index_unbekannter_eintrag_meldet_kein_manifest() -> None:
    """Ein unbekannter Eintrag darf nicht still ein leeres Script-Tag liefern."""
    if SPA_DIST is None:
        pytest.skip("Kein SPA-Build vorhanden")
    html = render_index("src/gibt-es-nicht/main.js")
    assert "FEHLER" in html or "type=\"module\"" not in html
