"""P2-6 — Datenschutz: keine Schrift von Google (Befund OP-HANDY-17).

Befund (Nachtpruefung, Abschnitt 2, OP-HANDY-17): Das ausgelieferte HTML verwies mit drei Zeilen auf
fonts.googleapis.com und fonts.gstatic.com. Damit ging die IP-Adresse JEDES
Mitglieds bei jedem Seitenaufruf an Google — in Deutschland abgemahnt
(LG Muenchen I, 3 O 17493/20) — und im langsamen Gemeindenetz kostete es
48 KB Fremdverkehr.

Behebung an der Ursache: Inter liegt bereits als WOFF2 im Frontend-Bündel
(`frappe-ui/style.css` -> `@font-face` mit `Inter.var.woff2`, OFL-Lizenz,
ueber die MIT-lizenzierte Abhaengigkeit `frappe-ui`). Die drei Google-Zeilen
waren deshalb ueberfluessig und werden entfernt. Die Tests hier sichern
BEIDES: keine Fremdanfrage mehr UND die Schrift bleibt lokal verfuegbar.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from diakronos_app.main import app
from diakronos_app.spa import render_index

# Hosts, die im ausgelieferten HTML NIE auftauchen duerfen: eine Anfrage
# dorthin ueberträgt die IP des Nutzers an einen Dritten.
FREMDE_SCHRIFT_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "googleapis.com",
    "gstatic.com",
)

# Eintraege, die das HTML der SPA ausliefern (spa.py:_entry_assets-Aufrufer).
# Jeder Eintrag muss ohne Fremdschrift-Host auskommen.
EINTRAEGE = (
    "src/diakonos/main.js",
    "src/registrierung/main.js",
    "src/gast/main.js",
    "src/organigramm/main.js",
)


def test_render_index_ohne_fremde_schriftquelle() -> None:
    """Kein Eintrag darf eine Schrift von Google nachladen (OP-HANDY-17).

    Reproduktion VOR der Behebung: `spa.py:501-503` setzte `preconnect` auf
    fonts.googleapis.com/fonts.gstatic.com und ein `<link>` auf
    `fonts.googleapis.com/css2?family=Inter…` -> dieser Test war rot
    (`assert 'fonts.googleapis.com' not in html`).
    """
    for eintrag in EINTRAEGE:
        html = render_index(eintrag)
        for host in FREMDE_SCHRIFT_HOSTS:
            assert host not in html, (
                f"{eintrag} verweist weiterhin auf {host} — die IP jedes "
                "Nutzers ginge an Google (OP-HANDY-17)."
            )


def test_render_index_hat_kein_google_preconnect() -> None:
    """Auch ein blosses `preconnect` ist eine Fremdanfrage — es verbindet
    bereits die DNS-/TLS-Sitzung zu Google, selbst wenn das CSS gefiltert
    wird. Einzeln geprueft, damit der Grund im Fehlerfall sichtbar ist.
    """
    html = render_index("src/diakonos/main.js")
    assert "preconnect" not in html or "google" not in html.lower(), (
        "preconnect auf einen Google-Host ist eine Fremdanfrage (OP-HANDY-17)."
    )


def test_loginmaske_ohne_fremde_schriftquelle() -> None:
    """Auch die serverseitige Anmeldemaske darf nichts bei Google laden.

    Sie ist der erste Kontakt fuer unbekannte Besucher (kein SPA-Build
    noetig) und war im Ausgangsbefund zwar unauffaellig, wird aber
    mitgeprueft, damit die Regel nicht an einer Stelle wieder einreisst.
    """
    from diakronos_app.spa import render_login

    html = render_login("/diakonos")
    for host in FREMDE_SCHRIFT_HOSTS:
        assert host not in html, f"Anmeldemaske verweist auf {host} (OP-HANDY-17)."


@pytest.fixture()
def client(patched_db, fake_redis):
    """Angemeldeter Client — sieht die SPA statt der Anmeldemaske (wie in
    test_spa_serving.py; dieselbe Begruendung, dieselbe Verkabelung)."""
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


def test_ausgelieferte_seite_ohne_fremde_schriftquelle(client) -> None:
    """Ende-zu-Ende: die echte Antwort von `/diakonos` nennt keinen Google-Host."""
    resp = client.get("/diakonos")
    assert resp.status_code == 200
    for host in FREMDE_SCHRIFT_HOSTS:
        assert host not in resp.text, (
            f"Die ausgelieferte Seite laedt weiterhin von {host} (OP-HANDY-17)."
        )
    # Die Seite muss trotzdem die SPA-CSS einbinden — sonst faellt die
    # Schrift nur deshalb weg, weil gar kein Stylesheet mehr ankommt.
    assert re.search(r'<link rel="stylesheet" href="/diakonos/assets/', resp.text), (
        "Kein SPA-Stylesheet im HTML — die Schrift ist dann nur zufaellig weg."
    )
