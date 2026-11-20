"""CHAT-10b — `/sw.js` an der Wurzel ausliefern (Service Worker, CSP).

Die Karte verlangt drei Dinge vom Server:

  1. `/sw.js` an der WURZEL (nicht unter `/diakonos/`), damit der Geltungs-
     bereich des Workers die ganze Seite ist — auch unter einem Betriebs-
     Praefix (dann `/gemeinde/sw.js`, dieselbe Adresse, die die Oberflaeche
     ueber `mitBasis('/sw.js')` bildet),
  2. `Content-Type: application/javascript`, `Cache-Control: no-cache` und
     `Service-Worker-Allowed: /`,
  3. fehlt die Datei im Build -> 404 (kein 200 mit leerem Inhalt, keine
     SPA-`index.html` an dieser Stelle).

Die Berechtigungs-Policy (`sec_header.APP_CSP`) deckt den Worker bereits mit
`worker-src 'self'` ab — er wird geprueft, nicht gelockert.

`--network none` genuegt: kein Test hier spricht mit einem fremden Dienst.
"""
from __future__ import annotations

import pytest

from diakronos_app import base_path, sec_header, spa


def _client():
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    return TestClient(app)


def _mit_build(monkeypatch, tmp_path, inhalt: str = "self.addEventListener('push', () => {});\n"):
    """Lenkt `SPA_DIST` auf einen Build-Ordner mit genau einer `sw.js`."""
    (tmp_path / "sw.js").write_text(inhalt, encoding="utf-8")
    monkeypatch.setattr(spa, "SPA_DIST", tmp_path)
    return tmp_path


def test_sw_wird_an_der_wurzel_geliefert(monkeypatch, tmp_path):
    """`/sw.js` antwortet mit dem Build-Inhalt und den drei Kopfzeilen."""
    quelle = "/* CHAT-10b */\nself.addEventListener('push', () => {});\n"
    _mit_build(monkeypatch, tmp_path, quelle)

    with _client() as c:
        r = c.get("/sw.js")

    assert r.status_code == 200, r.text
    assert r.text == quelle, "die Datei wird unveraendert ausgeliefert"
    assert r.headers["content-type"].startswith("application/javascript")
    # Fester Name -> kein Zwischenspeicher; ETag bleibt fuer 304.
    assert r.headers["cache-control"] == "no-cache"
    # Der Worker darf ueber sein Verzeichnis hinaus bedienen (Scope '/', auch
    # unter einem Praefix wie `/gemeinde/sw.js`).
    assert r.headers["service-worker-allowed"] == "/"


def test_fehlende_datei_ergibt_404(monkeypatch, tmp_path):
    """Ohne `sw.js` im Build gibt es KEIN 200 — und keine SPA-Seite."""
    monkeypatch.setattr(spa, "SPA_DIST", tmp_path)

    with _client() as c:
        r = c.get("/sw.js")

    assert r.status_code == 404, r.text
    assert "text/html" not in (r.headers.get("content-type") or "")


def test_ohne_build_ergibt_404(monkeypatch):
    """Auch ohne Build-Verzeichnis (`SPA_DIST is None`) ist es ein 404."""
    monkeypatch.setattr(spa, "SPA_DIST", None)

    with _client() as c:
        r = c.get("/sw.js")

    assert r.status_code == 404, r.text


def test_sw_pfad_datei_findet_nur_eine_echte_datei(monkeypatch, tmp_path):
    """`_sw_pfad` ist die EINE Stelle, die „gibt es die Datei?“ beantwortet."""
    monkeypatch.setattr(spa, "SPA_DIST", tmp_path)
    assert spa._sw_pfad() is None, "leerer Build -> keine Datei"

    (tmp_path / "sw.js").mkdir()  # Verzeichnis statt Datei
    assert spa._sw_pfad() is None, "ein Verzeichnis ist keine Datei"

    (tmp_path / "sw.js").rmdir()
    (tmp_path / "sw.js").write_text("x", encoding="utf-8")
    assert spa._sw_pfad() == tmp_path / "sw.js"

    monkeypatch.setattr(spa, "SPA_DIST", None)
    assert spa._sw_pfad() is None, "kein Build -> keine Datei"


def test_csp_erlaubt_den_worker_aus_der_eigenen_herkunft():
    """`worker-src 'self'` deckt `/sw.js` ab — die Policy wird nicht gelockert.

    Ein Worker der eigenen Herkunft braucht kein eigenes Token; ohne `worker-src`
    fiele er auf `default-src 'none'` zurueck und der Browser verweigerte die
    Registrierung. Geprueft wird beides: `worker-src 'self'` steht da, und
    `default-src` bleibt `'none'` (nichts wurde aufgeweitet).
    """
    policy = sec_header.APP_CSP
    assert "worker-src 'self'" in policy
    assert "default-src 'none'" in policy
    # Keine pauschale Freigabe fuer Skripte fremder Herkunft.
    assert "'unsafe-eval'" not in policy


@pytest.mark.parametrize("praefix", ["", "/gemeinde"])
def test_sw_antwortet_unter_dem_betriebspraefix(monkeypatch, tmp_path, praefix):
    """Unter einem Praefix liegt der Worker an `{Praefix}/sw.js`.

    Der Praefix haengt die GANZE Anwendung unter ein Mount (`base_path.
    praefigiere`), er wird beim Bauen der App festgelegt (`erstelle_app`).
    Deshalb wird hier eine eigene App mit diesem Praefix gebaut — und die
    Adresse geprueft, die die Oberflaeche baut (`mitBasis('/sw.js')` =
    `base_path.pfad(SW_PFAD)`). Ein fester Pfad `/sw.js` waere unter dem
    Praefix ein 404, und der Browser koennte den Worker nie holen.
    """
    from fastapi.testclient import TestClient

    from diakronos_app.main import erstelle_app
    from diakronos_app.settings import settings

    (tmp_path / "sw.js").write_text("/* sw */\n", encoding="utf-8")
    monkeypatch.setattr(spa, "SPA_DIST", tmp_path)
    monkeypatch.setattr(settings, "diakronos_base_path", praefix, raising=False)

    try:
        app = erstelle_app()
        pfad = base_path.pfad(spa.SW_PFAD)
        assert pfad == f"{praefix}/sw.js"

        with TestClient(app) as c:
            r = c.get(pfad)

        assert r.status_code == 200, r.text
        assert r.text == "/* sw */\n"
        assert r.headers["service-worker-allowed"] == "/"
        assert r.headers["cache-control"] == "no-cache"
    finally:
        # Der Praefix ist Prozesszustand — zurueck auf „kein Praefix“, damit
        # die naechsten Tests dieselbe Welt sehen wie vorher.
        base_path.setze_praefix("")


def test_sw_ist_nicht_der_spa_catch_all(monkeypatch, tmp_path):
    """`/sw.js` ist eine EIGENE Route — der Catch-all haengt unter `/diakonos`.

    Dadurch kann der Worker nicht versehentlich die index.html der SPA
    ausliefern (die einen CSRF-Token traegt und `no-store` verlangt).
    """
    (tmp_path / "sw.js").write_text("/* sw */\n", encoding="utf-8")
    monkeypatch.setattr(spa, "SPA_DIST", tmp_path)

    with _client() as c:
        direkt = c.get("/sw.js")
        # Die SPA-Adresse liefert weiterhin eine Seite (kein Worker):
        spa_pfad = c.get("/diakonos/sw.js")

    assert direkt.status_code == 200
    assert direkt.text == "/* sw */\n"
    assert direkt.headers.get("service-worker-allowed") == "/"
    # `/diakonos/sw.js` ist NICHT die Worker-Route (der Catch-all greift).
    assert spa_pfad.headers.get("service-worker-allowed") is None
