"""SEC-11c (R5) — die Anmeldemaske unter `/diakonos` traegt KEINE Daten.

KARTE
=====
„Pruefen: `/diakonos` liefert 200 + Login-Maske — Boot-Nutzlast ohne Anmeldung
darf keine Daten enthalten (Test)."

WAS HIER GEPRUEFT WIRD (und warum es nicht dasselbe ist wie in A1b2-rest)
--------------------------------------------------------------------------
`test_a1b2_rest_boot_login.py` prueft, DASS ohne Sitzung die Maske kommt
(`name="pwd"` da, `id="app"` und `window.__DIakonosBOOT` nicht). Das ist eine
Aussage ueber das MARKUP. Diese Datei prueft den INHALT:

  (1) Status und Form: `/diakonos` antwortet 200, liefert die Maske, KEIN
      Boot-Objekt und keine SPA-Wurzel.
  (2) Kein Datenleck im Rumpf: die gelieferte Seite enthaelt keinen der
      angelegten Mitgliedsnamen, keine E-Mail, keinen Ort, keinen Status —
      und keine der Kennungen (M-0001 …). Geprueft wird gegen WIRKLICH
      vorhandene Zeilen (`seed_mitglieder`), nicht gegen erfundene: ein Test
      gegen eine leere Datenbank waere immer gruen (dieselbe Falle wie bei den
      Datenmigrationen, Kartenregel 6).
  (3) Kein Sitzungs-Token in der Maske: kein `csrf_token`, kein `sid`, kein
      `DUMMY_BOOT`-Rest. Die Maske hat genau ein geheimes Feld (`_csrf` der
      Maske, SEC-4) — und das ist ein frischer, signierter Masken-Token, kein
      Sitzungs-Token.
  (4) Gegenprobe: MIT Sitzung liefert dieselbe Route die SPA samt Boot-Objekt.
      Damit ist belegt, dass die Pruefung in (2) die Seite trifft, die sie
      treffen soll — und nicht eine Route, die ohnehin nichts liefert. Ohne
      diese Gegenprobe koennte `/diakonos` dauerhaft 404 liefern und alle
      Tests oben blieben gruen.

Netz: `--network none`, DB ueber `patched_db` (SQLite), Redis ueber
`fake_redis` (Kartenregel 11).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from diakronos_app.main import app

MASKE = "/diakonos"
MARKER_PASSWORTFELD = 'name="pwd"'
MARKER_BOOT = "window.__DIakonosBOOT"
MARKER_SPA_WURZEL = 'id="app"'


@pytest.fixture()
def gast(patched_db, fake_redis):
    """Client OHNE Sitzung — jeder Aufruf ist `Guest`."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def angemeldet(patched_db, fake_redis):
    """Client MIT gueltiger Sitzung (Gegenprobe zu (4))."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.models.core import User

    sess = patched_db()
    if sess.get(User, "Administrator") is None:
        sess.add(User(name="Administrator", email="admin@example.org",
                      enabled=True))
    sess.commit()
    sess.close()
    sid, _csrf = sitzungen.anlegen("Administrator")
    with TestClient(app) as c:
        c.cookies.set("sid", sid)
        yield c


def _boot(html: str) -> dict:
    treffer = re.search(r"window\.__DIakonosBOOT\s*=\s*(\{.*?\});", html, re.DOTALL)
    assert treffer, "Kein __DIakonosBOOT im HTML gefunden"
    import json

    return json.loads(treffer.group(1))


# ── (1) Status und Form ────────────────────────────────────────────────────


def test_diakonos_ohne_anmeldung_ist_200_und_zeigt_die_maske(gast) -> None:
    antwort = gast.get(MASKE)
    assert antwort.status_code == 200, antwort.text[:300]
    assert MARKER_PASSWORTFELD in antwort.text, "Login-Maske fehlt"
    assert MARKER_BOOT not in antwort.text, (
        "Boot-Nutzlast ohne Anmeldung — die SPA darf erst nach dem Login kommen")
    assert MARKER_SPA_WURZEL not in antwort.text, "SPA-Wurzel ohne Anmeldung"


# ── (2) Kein Datenleck ─────────────────────────────────────────────────────


def test_diakonos_ohne_anmeldung_enthaelt_keine_mitgliedsdaten(
    gast, seed_mitglieder,
) -> None:
    """Die Seite darf keine Zeile aus `Mitglied` verraten.

    Geprueft wird gegen die TATSAECHLICH angelegten Werte (Vorname, Nachname,
    E-Mail, Ort, PLZ, Status, Kennung) — eine leere Datenbank wuerde hier
    nichts beweisen (Kartenregel 6).
    """
    antwort = gast.get(MASKE)
    assert antwort.status_code == 200, antwort.text[:300]
    seite = antwort.text

    sess = seed_mitglieder
    from diakronos_app.models.diakonos import Mitglied

    gefunden = []
    for mitglied in sess.query(Mitglied).all():
        for wert in (mitglied.name, mitglied.vorname, mitglied.nachname,
                     mitglied.email, mitglied.wohnort, mitglied.postleitzahl):
            if not wert:
                continue
            # Kennungen wie `M-0001` stehen im HTML nur, wenn die Seite Daten
            # liefert — genau das soll auffallen.
            if str(wert) in seite:
                gefunden.append(f"{mitglied.name}: {wert!r}")
    assert not gefunden, (
        "SEC-11c/R5: die Anmeldemaske verraet Mitgliedsdaten:\n  "
        + "\n  ".join(gefunden))


def test_diakonos_ohne_anmeldung_hat_kein_boot_objekt_und_keinen_token(gast) -> None:
    """Kein `csrf_token`, kein `sid` — die Maske hat nur ihren eigenen Token.

    Der Masken-Token (`_csrf`) ist ein signierter, kurzlebiger Wert der Maske
    (SEC-4); er ist KEIN Sitzungs-Token. Geprueft wird deshalb auf die
    Boot-Felder und den Cookie-Namen, nicht auf das Wort `csrf` — das steht
    legitim im Maskenformular.
    """
    antwort = gast.get(MASKE)
    seite = antwort.text
    for feld in ("csrf_token", "dummy-csrf-token", "iteration", "is_admin",
                 "mitglied_id", "user_id"):
        assert feld not in seite, f"Boot-Feld {feld!r} ohne Anmeldung im HTML"
    assert "window.__DIakonosBOOT" not in seite
    # Kein Sitzungs-Cookie wird gesetzt, solange man sich nicht anmeldet.
    assert "sid" not in antwort.cookies, "Ohne Anmeldung darf kein sid gesetzt werden"


# ── (3) Gegenprobe: mit Sitzung kommt die SPA ──────────────────────────────


def test_mit_anmeldung_liefert_dieselbe_route_die_spa_mit_boot(angemeldet) -> None:
    """Ohne diese Gegenprobe waere (2) blind: eine Route, die immer 404 gibt,
    bestuende jeden „darf nichts enthalten"-Test.
    """
    antwort = angemeldet.get(MASKE)
    assert antwort.status_code == 200, antwort.text[:300]
    assert MARKER_BOOT in antwort.text, "Mit Sitzung fehlt das Boot-Objekt"
    boot = _boot(antwort.text)
    assert boot, "Das Boot-Objekt ist leer"
    # Und die Maske ist dann NICHT mehr da (sonst waeren beide Wege offen).
    assert MARKER_PASSWORTFELD not in antwort.text


def test_der_gemeinsame_client_fixture_ist_ANGEMELDET_kein_gast(
    client, seed_mitglieder,
) -> None:
    """Abgrenzung, damit (1)-(3) nicht falsch gelesen werden.

    Der gemeinsame Fixture `client` in `conftest.py` ist **`Administrator`**
    (Sitzung + CSRF-Header, s. dortige Dokumentation). Dass `/diakonos` ihm die
    SPA mit Boot-Objekt und `csrf-token` liefert, ist deshalb RICHTIG und kein
    Leck — genau diese Verwechslung lag beim Schreiben dieser Datei vor.

    Der Test haelt beides fest: der angemeldete Client bekommt die SPA, der
    Gast (ohne jedes Cookie) bekommt die Maske. Nur der Gast ist der Fall, den
    R5 meint.
    """
    assert MARKER_SPA_WURZEL in client.get(MASKE).text, (
        "Der gemeinsame `client`-Fixture ist als Administrator angemeldet und "
        "muss die SPA sehen — sonst prueft (2) versehentlich den Gastpfad")
    gast = TestClient(app)  # bewusst OHNE Fixture: wirklich kein Cookie
    try:
        assert MARKER_PASSWORTFELD in gast.get(MASKE).text
        assert MARKER_SPA_WURZEL not in gast.get(MASKE).text
    finally:
        gast.close()
