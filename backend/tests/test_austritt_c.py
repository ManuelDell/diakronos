"""AUSTRITT-c — Kontozustand beim Reaktivieren (M1) und Kuerzung nur fuer Ausgetretene (N3).

Die beiden Zusagen des Pakets AUSTRITT-c:

* **M1** — „Reaktivieren“ stellt den Kontozustand VOR dem Austritt her. Wer
  vorher gesperrt war, bleibt nach dem Austritt UND nach dem Reaktivieren
  gesperrt (``vor_austritt_konto_aktiv`` am Mitglied).
* **N3** — Gekuerzt wird nur, wer AUSGETRETEN ist. Ein Ausschluss („Passiver
  Gast“) laesst die Person fuer Nicht-Admins voll sichtbar, wie in ``main``.
  Zuteilbarkeit bleibt davon getrennt: Ausgetretene UND Ausgeschlossene sind
  niemandem mehr als Kandidat angeboten.

Gegen den Stand vor der Nacharbeit sind diese Proben ROT: die
Spalte ``vor_austritt_konto_aktiv`` fehlt, das Reaktivieren schaltet jedes
Konto ein, und ``personen_anzeige.ist_ausgeschieden`` prueft die Marke
``ausgeschlossen`` statt des Austrittsmerkmals.
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

MA = "Mitgliederadministrator"

ADMIN = "verwaltung@x.org"
LESER = "leser@x.org"
#: Die Person, die austritt (der Ersteller der Zeile, ohne „M-“-Praefix: die
#: Fixture legt die Zeile als ``M-<kennung>`` an, wie das Betriebsformat) —
#: ihr Konto heisst ``ziel@x.org`` wie im Betrieb.
ZIEL = "ziel"
ZIEL_KONTO = "ziel@x.org"


def _konto(sess, kennung: str, rolle: str | None = None, *,
           vorname: str = "Lena", nachname: str = "Leser",
           konto: str | None = None, enabled: bool = True) -> None:
    konto = konto or kennung
    sess.add(User(name=konto, email=konto, full_name=konto, enabled=enabled))
    if rolle:
        sess.add(HasRole(name=f"HR-{kennung}-{rolle}", parent=konto,
                         parenttype="User", parentfield="roles", role=rolle,
                         docstatus=0, idx=1))
    sess.add(Mitglied(
        name=f"M-{kennung}", vorname=vorname, nachname=nachname,
        email=konto, status="Mitglied", user=konto,
        ausgeschlossen=0, docstatus=0, idx=0,
    ))
    sess.commit()


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    _konto(sess, ADMIN, MA, vorname="Anna", nachname="Admin", konto=ADMIN)
    _konto(sess, LESER, vorname="Lena", konto=LESER)
    _konto(sess, ZIEL, vorname="Elvira", nachname="Dorn",
           konto=ZIEL_KONTO, enabled=False)
    # Derselbe Pfad wie beim Leser — er gehoert zur Sichtbarkeitsregel, nicht
    # zur Kuerzung (siehe `_detail_von`).
    sess.flush()
    for name in (f"M-{ADMIN}", f"M-{LESER}", f"M-{ZIEL}"):
        sess.get(Mitglied, name).ancestor_path = "/gemeinde/|"
    sess.commit()
    yield sess
    sess.close()
    set_user("Administrator")


def _konto_an(sess, name: str) -> bool:
    """Frischer Enabled-Zustand (die Session cacht sonst die alte Zeile)."""
    sess.expire_all()
    return bool(sess.get(User, name).enabled)


def _zeile(sess):
    """Die Mitgliedszeile des Ziels (frische Sicht)."""
    sess.expire_all()
    return sess.get(Mitglied, f"M-{ZIEL}")


def _austritt() -> None:
    from diakronos_app.api.austritt import mitglied_austritt

    set_user(ADMIN)
    mitglied_austritt(f"M-{ZIEL}", "Austritt auf eigenen Wunsch", "2026-10-01")


def _detail_von(wer: str) -> dict:
    """Detailantwort des Nicht-Admin/Admin — mit derselben Sichtbarkeit.

    Die Rechtepruefung von ``get_mitglied_detail`` ist hier nicht der Pruefstand
    (die Karte deckt die Sichtbarkeitsregel ueber die LISTE ab, siehe
    ``test_n3_liste_…``). Die Pfad-Pruefung liest dafuer ``ancestor_path`` in
    einer frischen Sitzung; in der Testdatenbank (SQLite) ist der Pfad-Zustand
    nicht zuverlaessig gesetzt. Deshalb wird die Permission-Map mit demselben
    ``vollstaendig``-Sinn wie im Endpunkt vorbelegt: Admin = alles, Leser =
    ``can_view`` ohne ``can_view_sensitive``.
    """
    from diakronos_app.api import mitglieder as m

    set_user(wer)
    perms = {
        "can_view": True,
        "can_edit": False,
        "can_delete": False,
        "can_view_sensitive": wer == ADMIN,
        "reason": "test",
    }
    original = m.permissions.mitglied_permissions
    m.permissions.mitglied_permissions = lambda *a, **k: dict(perms)
    try:
        return m.get_mitglied_detail(f"M-{ZIEL}")["data"]
    finally:
        m.permissions.mitglied_permissions = original


def _reaktivieren() -> None:
    from diakronos_app.api.austritt import mitglied_reaktivieren

    set_user(ADMIN)
    mitglied_reaktivieren(f"M-{ZIEL}")


# ── M1: Kontozustand vor dem Austritt merken ────────────────────────────────


def test_m1_aktives_konto_bleibt_nach_reaktivieren_aktiv(welt) -> None:
    """(a) aktiv → Austritt → Reaktivieren = aktiv."""
    from diakronos_app.frappe_compat import benutzer_status

    sess = welt
    sess.get(User, ZIEL_KONTO).enabled = True
    sess.commit()

    _austritt()
    # Beim Austritt gemerkt: das Konto WAR aktiv.
    assert sess.get(Mitglied, f"M-{ZIEL}").vor_austritt_konto_aktiv == {
        ZIEL_KONTO: True,
    }
    assert _konto_an(sess, ZIEL_KONTO) is False, "Austritt schaltet das Konto aus"

    _reaktivieren()
    assert _konto_an(sess, ZIEL_KONTO) is True
    assert sess.get(Mitglied, f"M-{ZIEL}").vor_austritt_konto_aktiv is None
    benutzer_status.vergiss(ZIEL_KONTO)
    assert benutzer_status.ist_aktiv(ZIEL_KONTO) is True


def test_m1_gesperrtes_konto_bleibt_nach_reaktivieren_gesperrt(welt) -> None:
    """(b) gesperrt → Austritt → Reaktivieren = gesperrt.

    Der Austritt ist NICHT das Aufheben einer Kontosperre: wer vorher gesperrt
    war, ist danach gesperrt. Sonst waere „Austritt + Reaktivieren“ ein
    Seiteneingang an ``konto_sperren`` vorbei — samt Schranken
    (``_verweigere_letzten_admin_verlust``) und Protokoll.
    """
    from diakronos_app.api.zugang import konto_sperren
    from diakronos_app.frappe_compat import benutzer_status

    sess = welt
    # Ein einfaches Mitglied kann gesperrt werden — kein Verwaltungskonto.
    set_user(ADMIN)
    # `konto_sperren` nimmt die MITGLIEDS-Kennung, nicht den Kontonamen.
    konto_sperren(f"M-{ZIEL}", True)
    sess.expire_all()
    assert _konto_an(sess, ZIEL_KONTO) is False

    _austritt()
    assert sess.get(Mitglied, f"M-{ZIEL}").vor_austritt_konto_aktiv == {
        ZIEL_KONTO: False,
    }, (
        "das gesperrte Konto muss als gesperrt gemerkt werden")
    assert _konto_an(sess, ZIEL_KONTO) is False

    _reaktivieren()
    assert _konto_an(sess, ZIEL_KONTO) is False, (
        "die Sperre von vor dem Austritt bleibt bestehen")
    assert sess.get(Mitglied, f"M-{ZIEL}").ausgeschlossen is False
    benutzer_status.vergiss(ZIEL_KONTO)
    assert benutzer_status.ist_aktiv(ZIEL_KONTO) is False


def test_m1_altdaten_ohne_gemerkten_wert_werden_wieder_aktiv(welt) -> None:
    """(c) Altdaten ohne gemerkten Wert → aktiv.

    Begruendung: Die Spalte entsteht mit dieser Migration; ein Austritt, der
    VOR ihr erfasst wurde, hat keinen Wert. Sein Konto wurde nach der alten
    Regel ausgeschaltet — der Austritt selbst kann es also nicht schon vorher
    gesperrt haben. Die einzige Aussage, die die Altdaten tragen, ist damit
    „war aktiv, wurde durch den Austritt ausgeschaltet“; alles andere waere
    geraten. Bleibt die Sperre wirklich gewollt, setzt ein Administrator sie
    nach dem Reaktivieren neu (der Hinweis in der Oberflaeche sagt das).
    """
    from diakronos_app.frappe_compat import benutzer_status

    sess = welt
    # Altbestand: ausgetreten, ohne gemerkten Kontozustand.
    set_user(ADMIN)
    _austritt()
    zeile = _zeile(sess)
    zeile.vor_austritt_konto_aktiv = None
    sess.commit()
    assert _konto_an(sess, ZIEL_KONTO) is False

    _reaktivieren()
    assert _konto_an(sess, ZIEL_KONTO) is True
    benutzer_status.vergiss(ZIEL_KONTO)
    assert benutzer_status.ist_aktiv(ZIEL_KONTO) is True


def test_m1_merkt_je_konto_den_eigenen_zustand(welt) -> None:
    """Gemerkt wird je wirksamem Konto — nicht ein Wert fuer alle.

    Konten wirken ueber ``user``-Link UND eindeutige E-Mail. Ein zweites Konto
    mit derselben Adresse (Altbestand) kann anders stehen; es darf durch den
    Austritt nicht dauerhaft anders werden als es war.
    """
    sess = welt
    sess.add(User(name="zweitzugang@x.org", email=ZIEL_KONTO,
                  full_name="Elvira Dorn", enabled=True))
    sess.get(User, ZIEL_KONTO).enabled = False
    sess.commit()

    _austritt()
    assert sess.get(Mitglied, f"M-{ZIEL}").vor_austritt_konto_aktiv == {
        "zweitzugang@x.org": True, ZIEL_KONTO: False,
    }
    assert _konto_an(sess, "zweitzugang@x.org") is False
    assert _konto_an(sess, ZIEL_KONTO) is False

    _reaktivieren()
    assert _konto_an(sess, "zweitzugang@x.org") is True
    assert _konto_an(sess, ZIEL_KONTO) is False


# ── N3: Gekuerzt wird nur der AUSGETRETENE ──────────────────────────────────


def _ausschluss() -> None:
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    set_user(ADMIN)
    schliesse_mitglied_aus(f"M-{ZIEL}")


def test_n3_ausgeschlossener_zeigt_dem_nicht_admin_den_klarnamen(welt) -> None:
    """Ausschluss („Passiver Gast“) kuerzt NICHT — wie in ``main``.

    Der Weg zum Aufheben ist „Status im Profil ändern“; wer die Person nicht
    mehr erkennt, findet sie und diesen Weg nicht.

    AUSTRITT-e (NR1): Die Probe steht wieder auf BEIDEN Rollen. Der Umbau in
    AUSTRITT-d hatte nur noch den Admin geprueft und damit verdeckt, dass die
    Detailansicht Ausgeschlossene fuer Nicht-Admins kuerzte. Gekuerzt wird das
    Austrittsmerkmal, nicht die Marke (Fachentscheidung).
    """
    sess = welt
    _ausschluss()
    sess.expire_all()
    assert sess.get(Mitglied, f"M-{ZIEL}").status == "Passiver Gast"

    daten = _detail_von(LESER)
    # Der Leser sieht die Ausgeschlossene ungekuerzt — vorname, nachname und
    # Adresse (die Adressbuch-Maskierung bleibt davon unberuehrt).
    assert daten["vorname"] == "Elvira"
    assert daten["nachname"] == "Dorn"
    assert "Dorn" in repr(daten), "der Nicht-Admin sieht den Klarnamen"
    # Die ART kommt vom Server und trennt die Faelle (NB3).
    assert daten["austritt"]["art"] == "ausschluss"
    assert daten["austritt"]["grund"] is None
    admin = _detail_von(ADMIN)
    assert admin["vorname"] == "Elvira"
    assert admin["nachname"] == "Dorn"


def test_n3_ausgetretener_zeigt_dem_nicht_admin_die_kurzform(welt) -> None:
    """Gegenprobe: der Austritt kuerzt — „Elvira D.“ und maskierte Adresse."""
    _austritt()
    daten = _detail_von(LESER)
    assert daten["vorname"] == "Elvira D."
    assert daten["nachname"] is None
    assert daten["email"] == "zie*******.org"
    assert "Dorn" not in repr(daten)

    admin = _detail_von(ADMIN)
    assert admin["vorname"] == "Elvira"
    assert admin["nachname"] == "Dorn"


def test_n3_ist_ausgeschieden_meint_das_austrittsmerkmal() -> None:
    """Die Kuerzungsentscheidung haengt am Austritt, nicht an der Marke.

    Die Marke ``ausgeschlossen`` traegt beide Faelle (Austritt und
    Ausschluss); das Austrittsmerkmal ist der Status „Ausgetreten“ oder ein
    ``austritt_datum`` — genau die Merkmale, die der Austritt setzt und der
    Ausschluss nicht.
    """
    from diakronos_app.frappe_compat.personen_anzeige import ist_ausgeschieden

    assert ist_ausgeschieden({"ausgeschlossen": True, "status": "Ausgetreten"})
    assert ist_ausgeschieden({"ausgeschlossen": True,
                              "austritt_datum": "2026-10-01"})
    assert not ist_ausgeschieden({"ausgeschlossen": True,
                                  "status": "Passiver Gast"})
    assert not ist_ausgeschieden({"ausgeschlossen": False,
                                  "status": "Mitglied"})


def test_n3_ausgeschiedene_bleiben_unzuteilbar(welt) -> None:
    """Zuteilbarkeit getrennt von der Anzeige: beide Faelle sind raus."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    sess = welt
    _ausschluss()
    sess.expire_all()

    set_user(ADMIN)
    s = SessionLocal()
    try:
        kandidaten = {p.kennung for p in DBDatenquelle(s).personen()}
    finally:
        s.close()
    assert f"M-{ZIEL}" not in kandidaten, (
        "ein Ausgeschlossener darf niemandem zugeteilt werden — auch wenn "
        "sein Name voll sichtbar ist")


def test_n3_liste_zeigt_ausgeschlossene_mit_klarnamen(welt) -> None:
    """Die Mitgliederliste folgt derselben Regel (kein zweiter Weg)."""
    from diakronos_app.api.mitglieder import get_mitglieder_liste

    sess = welt
    _ausschluss()
    sess.expire_all()

    set_user(LESER)
    zeile = next(z for z in get_mitglieder_liste()["data"] if z["name"] == f"M-{ZIEL}")
    assert zeile["full_name"] == "Elvira Dorn"

    # AUSTRITT-d (NH1): „Ausschluss → Austritt“ ist gesperrt (der Weg haette
    # den Ausschluss beim Reaktivieren still aufgehoben). Fuer diesen Test —
    # es geht um die ANZEIGE nach einem Austritt — wird der Ausschluss vorher
    # ueber den Statusweg aufgehoben.
    sess.get(Mitglied, f"M-{ZIEL}").ausgeschlossen = 0
    sess.get(Mitglied, f"M-{ZIEL}").status = "Mitglied"
    sess.commit()
    _austritt()
    sess.expire_all()
    set_user(ADMIN)
    mitglieder = {z["name"]: z for z in get_mitglieder_liste(status="Ausgetreten")["data"]}
    assert mitglieder[f"M-{ZIEL}"]["full_name"] == "Elvira Dorn", (
        "der Admin sieht den Klarnamen der Ausgetretenen")
    set_user(LESER)
    mitglieder = {z["name"]: z for z in get_mitglieder_liste(status="Ausgetreten")["data"]}
    assert mitglieder[f"M-{ZIEL}"]["full_name"] == "Elvira D."
