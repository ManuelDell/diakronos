"""P1-8d — Reproduktionstests der dritten Rechte-Runde (Befund).

Die Proben stammen aus dem unabhaengigen Sicherheits-Nachreview des dritten
Durchgangs.
Sie waren VOR dieser Karte ROT: ein Mitgliederadministrator bzw. der letzte
System Manager konnte die Aussperr-Sperre ueber Wege umgehen, die die Schranke
nicht kannte.

  * B1 — `frappe.client.insert("Mitglied", ...)` baute das Modell selbst und
    rief die Schranke nie auf.
  * B2 — die Schranke loeste das Ziel nur ueber `Mitglied.user` auf; die Wirkung
    laeuft aber auch ueber die E-Mail (Konto mit gleicher Adresse).
  * B2b — eine reine `email`-Aenderung an einem bereits ausgeschlossenen
    Mitglied wurde nicht mitgeprueft.
  * W1 — der Aussperrschutz zaehlte ausgeschlossene System Manager als aktiv;
    im Zwei-Schritt (A schliesst B aus, dann sich selbst) blieb niemand uebrig.
  * W2 — `get_mein_termin` gab jedem Kalenderleser Titel/Zeit/Status fremder
    Termine (auch Abgelehnt/Vorschlag).
  * W4 — `bool("0")` ist `True`: ein Flag-Wert `"0"` wurde als Ausschluss
    gelesen.

Jede Probe ist mit der SICHEREN Erwartung uebernommen: der Schreibweg verweigert
(`PermissionError` bzw. 403) ODER das Konto bleibt aktiv mit seinen Rollen.
Ohne die Aenderungen in `frappe_compat/api_helpers.py`,
`frappe_compat/benutzer_status.py`, `api/frappe_core.py` und
`api/kronos/calendar_get.py` waere diese Datei rot.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User, UserRole
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.kronos import Element, Kalender


def _konto(sess, email: str, rolle: str | None = None, *, mitglied: bool = True,
           enabled: bool = True) -> None:
    """Konto anlegen; das zugehoerige Mitglied ist optional (erster Admin)."""
    sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                          email=email, status="Mitglied", user=email,
                          docstatus=0, idx=0))
    sess.commit()


def _rollen(user: str) -> tuple[str, ...]:
    from diakronos_app.frappe_compat.permissions import get_roles

    return get_roles(user)


def _aktiv(user: str) -> bool:
    from diakronos_app.frappe_compat import benutzer_status

    benutzer_status.vergiss(user)
    return benutzer_status.ist_aktiv(user)


def _status(sess, mitglied_id: str) -> bool:
    sess.expire_all()
    return bool(sess.get(Mitglied, mitglied_id).ausgeschlossen)


# ── B1: `frappe.client.insert` laeuft durch dieselbe Schranke ───────────────


def test_client_insert_mitglied_auf_sm_konto_verweigert(patched_db, fake_redis) -> None:
    """B1 — Mitgliederadmin legt neues Mitglied auf ein SM-Konto, ausgeschlossen.

    VORHER: `insert` baute das Modell selbst und rief die Schranke nie auf; der
    SM verlor danach Rollen und Aktivitaet.
    """
    from diakronos_app.api.frappe_core import insert

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                    "user": "sm@x.org", "ausgeschlossen": 1})

    # Safe-Erwartung: das Konto bleibt System Manager und aktiv.
    assert "System Manager" in _rollen("sm@x.org")
    assert _aktiv("sm@x.org") is True


def test_client_insert_letzter_sm_verweigert(patched_db, fake_redis) -> None:
    """B1 — insert auf ein SM-Konto, das das einzige ist (Aussperrschutz)."""
    from diakronos_app.api.frappe_core import insert

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    with pytest.raises(FrappePermissionError):
        insert(doc={"doctype": "Mitglied", "vorname": "Z", "nachname": "Z",
                    "user": "sm@x.org", "ausgeschlossen": 1})
    assert _aktiv("sm@x.org") is True


def test_client_insert_normales_mitglied_erlaubt(patched_db, fake_redis) -> None:
    """Gegenprobe: ein harmloses Mitglied anzulegen bleibt moeglich."""
    from diakronos_app.api.frappe_core import insert

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")

    doc = insert(doc={"doctype": "Mitglied", "vorname": "Nora", "nachname": "Neu",
                      "email": "nora@x.org"})
    assert doc["vorname"] == "Nora"


def test_create_mitglied_auf_sm_email_verweigert(patched_db, fake_redis) -> None:
    """B2 — der generische `_create`-Weg traegt dieselbe Wirkung ueber die E-Mail."""
    from diakronos_app.frappe_compat.api_helpers import _create

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "sm2@x.org", "System Manager", mitglied=False)
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        _create("Mitglied", {"vorname": "X", "nachname": "Y",
                             "email": "SM@x.org", "ausgeschlossen": 1})
    assert "System Manager" in _rollen("sm@x.org")


# ── B2: die E-Mail-Zuordnung wirkt auf der Schreibseite ─────────────────────


def test_post_neues_mitglied_mit_sm_email_ausgeschlossen(patched_db, fake_redis) -> None:
    """B2 — POST /api/resource: neues Mitglied mit SM-Adresse, ausgeschlossen."""
    from diakronos_app.frappe_compat.router import _apply_resource_write

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "sm2@x.org", "System Manager", mitglied=False)
    set_user("ma@x.org")

    antwort = _apply_resource_write(
        "Mitglied", None,
        {"name": "M-neu", "vorname": "X", "nachname": "Y",
         "email": "SM@x.org", "ausgeschlossen": 1},
    )
    assert getattr(antwort, "status_code", 200) == 403
    assert "System Manager" in _rollen("sm@x.org")
    assert _aktiv("sm@x.org") is True


def test_put_email_aendern_auf_sm_adresse_verweigert(patched_db, fake_redis) -> None:
    """B2b — reine `email`-Aenderung an einem ausgeschlossenen Mitglied.

    VORHER: kein `ausgeschlossen` im Payload -> die Schranke war ein No-op, das
    SM-Konto (ohne eigenes Mitglied) wurde ueber die Adresse ausgeschlossen.
    """
    from diakronos_app.frappe_compat.router import _apply_resource_write

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "sm2@x.org", "System Manager", mitglied=False)
    sess.add(Mitglied(name="M-alt", vorname="A", nachname="B", email="alt@x.org",
                      status="Passiver Gast", ausgeschlossen=True,
                      docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    antwort = _apply_resource_write("Mitglied", "M-alt", {"email": "sm@x.org"})
    assert getattr(antwort, "status_code", 200) == 403
    assert "System Manager" in _rollen("sm@x.org")


def test_mitgliederadmin_verbiegt_email_nicht_auf_sm(patched_db, fake_redis) -> None:
    """B2 — der interne `_update_doc`-Weg ist genauso dicht."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "sm2@x.org", "System Manager", mitglied=False)
    sess.add(Mitglied(name="M-alt", vorname="A", nachname="B", email="alt@x.org",
                      status="Passiver Gast", ausgeschlossen=True,
                      docstatus=0, idx=0))
    sess.commit()
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-alt", {"email": "sm@x.org"})


# ── W1: der Aussperrschutz kennt ausgeschlossene SM nicht mehr als aktiv ─────


def test_zwei_schritt_aussperrung_verweigert(patched_db, fake_redis) -> None:
    """W1 — SM A schliesst SM B aus und danach sich selbst.

    VORHER: B zaehlte weiter als aktiver SM, deshalb war A danach ausgeschlossen
    und niemand mehr Administrator.
    """
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")

    schliesse_mitglied_aus("M-sm2@x.org", "Test")  # A darf B (zwei SM)
    assert _status(sess, "M-sm2@x.org") is True

    with pytest.raises(FrappePermissionError):
        schliesse_mitglied_aus("M-sm@x.org", "Test")  # B ist ausgeschlossen -> A ist der letzte

    assert _status(sess, "M-sm@x.org") is False
    assert "System Manager" in _rollen("sm@x.org")
    assert _aktiv("sm@x.org") is True


def test_letzter_verbleibender_sm_nicht_per_generischem_weg(patched_db, fake_redis) -> None:
    """W1 — derselbe Zwei-Schritt ueber den generischen Schreibweg."""
    from diakronos_app.frappe_compat.router import _apply_resource_write

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm@x.org")

    assert getattr(
        _apply_resource_write("Mitglied", "M-sm2@x.org", {"ausgeschlossen": 1}),
        "status_code", 200,
    ) == 200
    antwort = _apply_resource_write("Mitglied", "M-sm@x.org", {"ausgeschlossen": 1})
    assert getattr(antwort, "status_code", 200) == 403
    assert _status(sess, "M-sm@x.org") is False


# ── W4: Flag-Werte normalisieren ────────────────────────────────────────────


def test_ausgeschlossen_flag_null_ist_kein_ausschluss(patched_db, fake_redis) -> None:
    """W4 — `'0'`/`0`/`False`/`None` heissen NICHT ausgeschlossen.

    VORHER: `bool('0')` ist `True` und wurde als Ausschluss eines SM gelesen —
    ein harmloses Aufheben wurde zur Verweigerung.
    """
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    _update_doc("Mitglied", "M-sm@x.org", {"ausgeschlossen": "0", "status": "Mitglied"})
    assert _status(sess, "M-sm@x.org") is False


# ── W2: `get_mein_termin` liefert fremde Termine nicht aus ──────────────────


def _leser_kalender(sess, kalender: str = "K1") -> None:
    """Kalender mit Leserecht fuer die Rolle `Mitglied`."""
    sess.add(Kalender(name=kalender, calendar_name=kalender, docstatus=0, idx=0))
    sess.commit()
    sess.add(UserRole(name=f"ur-{kalender}", parent=kalender, parenttype="Kalender",
                      parentfield="leserechte", role="Mitglied", docstatus=0, idx=1))
    sess.commit()


def test_get_mein_termin_verweigert_fremden_termin_trotz_leserecht(
    patched_db, fake_redis
) -> None:
    """W2 — ein Kalenderleser ohne Antragsteller-/Moderatorrolle bekommt 403.

    VORHER: jeder mit Leserecht bekam Titel, Zeit, Beschreibung und Status
    fremder Termine — auch `Abgelehnt`/`Vorschlag`.
    """
    from diakronos_app.api.kronos.calendar_get import get_mein_termin

    sess = patched_db()
    _konto(sess, "leser@x.org", "Mitglied")
    _konto(sess, "antrag@x.org", "Mitglied")
    _leser_kalender(sess)
    for i, st in enumerate(("Abgelehnt", "Vorschlag", "Festgelegt")):
        sess.add(Element(
            name=f"E{i}", element_name="Geheimer Titel", element_calendar="K1",
            element_start=datetime(2026, 11, 1, 18, 0),
            element_end=datetime(2026, 11, 1, 19, 0),
            status=st, ablehnungs_grund="intern", moderiert_von="mod@x.org",
            owner="antrag@x.org", docstatus=0, idx=0,
        ))
    sess.commit()
    set_user("leser@x.org")

    for n in ("E0", "E1", "E2"):
        with pytest.raises(FrappePermissionError):
            get_mein_termin(n)


def test_get_mein_termin_antragsteller_sieht_eigenen_termin(patched_db, fake_redis) -> None:
    """Gegenprobe: der Antragsteller bekommt seinen eigenen abgelehnten Termin."""
    from diakronos_app.api.kronos.calendar_get import get_mein_termin

    sess = patched_db()
    _konto(sess, "antrag@x.org", "Mitglied")
    _leser_kalender(sess)
    sess.add(Element(
        name="E0", element_name="Mein Termin", element_calendar="K1",
        element_start=datetime(2026, 11, 1, 18, 0),
        element_end=datetime(2026, 11, 1, 19, 0),
        status="Abgelehnt", ablehnungs_grund="Zu spaet", moderiert_von="mod@x.org",
        owner="antrag@x.org", docstatus=0, idx=0,
    ))
    sess.commit()
    set_user("antrag@x.org")

    r = get_mein_termin("E0")
    assert r["title"] == "Mein Termin"
    assert r["status"] == "Abgelehnt"
    assert r["ablehnungs_grund"] == "Zu spaet"


# ── (a) die Schranke loest ueber du UND E-Mail auf (eine Funktion) ───────────


def test_wirksame_konten_loest_user_und_email_auf(patched_db, fake_redis) -> None:
    """(a) EINE Aufloesung fuer Rechtepruefung und Schranke."""
    from diakronos_app.frappe_compat.benutzer_status import wirksame_konten

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    sess.get(User, "sm@x.org").email = "a@x.org"
    sess.add(Mitglied(name="M-a", vorname="A", nachname="B", email="A@x.org",
                      user="konto@x.org", docstatus=0, idx=0))
    sess.commit()

    konten = wirksame_konten({"user": "konto@x.org", "email": "a@x.org"})
    assert konten == {"konto@x.org", "sm@x.org"}


def test_wirksame_konten_familienpostfach_nur_user_link(
    patched_db, fake_redis, altbestand_dublette,
) -> None:
    """Doppelte Adresse (Altbestand) -> ALLE Konten der Adresse sind wirksam.

    Fachentscheidung (Manuel, 2026-10-19): eine Adresse gehoert hoechstens zu
    EINEM Mitglied; das Anlegen/Importieren einer zweiten Person mit derselben
    Adresse wird abgelehnt. Fuer einen ALTbestand, der die Dopplung noch
    enthaelt, gilt die vorsichtige Lesart: das Konto der Adresse ist wirksam —
    ein Ausschluss laesst sich ueber die Adresse nicht umgehen.
    """
    from diakronos_app.frappe_compat.benutzer_status import wirksame_konten

    sess = patched_db()
    _konto(sess, "familie@x.org", "Mitglied", mitglied=False)
    sess.add(Mitglied(name="M-a", vorname="A", nachname="B", email="familie@x.org",
                      user="a@x.org", docstatus=0, idx=0))
    sess.add(Mitglied(name="M-b", vorname="C", nachname="D", email="familie@x.org",
                      user="b@x.org", docstatus=0, idx=0))
    sess.commit()

    # Fail-closed: der `user`-Link bleibt, das Konto der Adresse kommt hinzu.
    assert wirksame_konten({"user": "a@x.org", "email": "familie@x.org"}) == {
        "a@x.org", "familie@x.org"}


@pytest.mark.parametrize("flag", ["0", 0, False, None])
def test_null_flags_normalisiert(patched_db, fake_redis, flag):
    from diakronos_app.frappe_compat.api_helpers import _create
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    set_user("sm@x.org")
    name = _create("Mitglied", {"email": "sm@x.org", "ausgeschlossen": flag})
    assert not _status(sess, name)
    assert _aktiv("sm@x.org")


def test_email_allein_wirkt_auf_rollen_status_und_aktive_manager(patched_db, fake_redis):
    from diakronos_app.api.zugang import _aktive_system_manager
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "sm2@x.org", "System Manager")
    sess.add(Mitglied(name="M-email", email="SM@x.org", ausgeschlossen=True))
    sess.commit()
    assert _rollen("sm@x.org") == ()
    assert not _aktiv("sm@x.org")
    assert _aktive_system_manager() == {"sm2@x.org"}


def test_normale_namenspflege_am_admin_bleibt_erlaubt(patched_db, fake_redis):
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")
    _update_doc("Mitglied", "M-sm@x.org", {"vorname": "Korrigiert"})
    sess.expire_all()
    assert sess.get(Mitglied, "M-sm@x.org").vorname == "Korrigiert"


def test_letzter_sm_bei_emailwechsel_aus_doppelter_adresse_geschuetzt(
    patched_db, fake_redis, altbestand_dublette,
):
    """Der letzte SM bleibt geschuetzt — auch wenn seine Adresse doppelt war.

    K-d (SEC-d): Der Fall beschreibt einen ALTbestand. Seit dem partiellen
    Unique-Index `uq_mitglied_email_normalisiert` (Migration
    `sec2_email_eindeutig`) kann eine Adresse nicht mehr zweimal entstehen;
    die Fixture `altbestand_dublette` nimmt den Index nur fuer den Aufbau
    heraus, damit der Bestand von VOR der Migration nachstellbar bleibt.
    Die Zusage gilt fuer genau diese Daten weiter: verlaesst der letzte
    System Manager eine solche Adresse, muss die zentrale Schranke das
    verweigern, sonst ist die Verwaltung ausgesperrt.
    """
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    sess.add_all([
        Mitglied(name="M-a", email="sm@x.org", ausgeschlossen=True),
        Mitglied(name="M-b", email="SM@x.org", ausgeschlossen=False),
    ])
    sess.commit()
    set_user("sm@x.org")
    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-b", {"email": "andere@x.org"})
    assert not _aktiv("sm@x.org")


def test_put_user_umbiegen_mitgliederadmin_probe(patched_db, fake_redis):
    from diakronos_app.frappe_compat.router import _apply_resource_write
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    sess.add(Mitglied(name="M-opfer", email="o@x.org"))
    sess.commit()
    set_user("ma@x.org")
    r = _apply_resource_write("Mitglied", "M-opfer", {"user": "sm@x.org"})
    assert r.status_code == 403


def test_ausschluss_probe_ma_darf_sm_nicht_ausschliessen(patched_db, fake_redis):
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("ma@x.org")
    with pytest.raises(FrappePermissionError):
        schliesse_mitglied_aus("M-sm@x.org", "Test")
    assert _aktiv("sm@x.org")


@pytest.mark.parametrize("weg", ["client", "resource", "create", "document"])
@pytest.mark.parametrize("flag", ["0", 0, False, None])
def test_insert_wege_normalisieren_flags(patched_db, fake_redis, weg, flag):
    from diakronos_app.api.frappe_core import insert
    from diakronos_app.frappe_compat.api_helpers import _create
    from diakronos_app.frappe_compat.router import _apply_resource_write
    from diakronos_app.frappe_compat.doc import new_doc
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    set_user("sm@x.org")
    daten = {"name": "M-test", "email": "sm@x.org", "ausgeschlossen": flag}
    # ID-1d: Die Kennung vergibt der Server — der Client-`name` in `daten`
    # wird verworfen. Die Zeile wird ueber die ZURUECKGEGEBENE Kennung
    # geprueft (vorher ueber den mitgeschickten Namen).
    if weg == "client":
        kennung = insert(doc={"doctype": "Mitglied", **daten})["name"]
    elif weg == "resource":
        antwort = _apply_resource_write("Mitglied", None, daten)
        assert isinstance(antwort, dict)
        kennung = antwort["name"]
    elif weg == "create":
        kennung = _create("Mitglied", daten)
    else:
        doc = new_doc("Mitglied", **daten)
        doc.insert()
        kennung = doc.name
    assert kennung != "M-test"
    assert not _status(sess, kennung)
    assert _aktiv("sm@x.org")
    # Keine Zeile unter dem Client-Namen angelegt.
    assert sess.get(Mitglied, "M-test") is None


@pytest.mark.parametrize("weg", ["insert", "save", "db_set"])
def test_document_schreibwege_verweigern_ausschluss(patched_db, fake_redis, weg):
    from diakronos_app.frappe_compat.doc import new_doc
    from diakronos_app.frappe_compat.query import get_doc
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")
    with pytest.raises(FrappePermissionError):
        if weg == "insert":
            new_doc("Mitglied", name="M-neu", user="sm@x.org", ausgeschlossen=True).insert()
        else:
            with get_doc("Mitglied", "M-sm@x.org") as doc:
                if weg == "db_set":
                    doc.db_set("ausgeschlossen", True)
                else:
                    doc.ausgeschlossen = True
                    doc.save()
    assert _aktiv("sm@x.org")


def test_import_laeuft_durch_zentrale_schranke(patched_db, fake_redis):
    from diakronos_app.api.mitglieder import import_mitglieder_uebernehmen
    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    set_user("ma@x.org")
    # Eine neue E-Mail-Verknüpfung auf ein Verwaltungskonto ist nur SM erlaubt.
    # N11b/K4: Die Schranke meldet ihren GRUND jetzt als PermissionError (mit
    # Klartext) statt hinter der allgemeinen „ließ sich nicht speichern“-
    # Meldung — der Fall bleibt derselbe, die Meldung wird genauer.
    from diakronos_app.frappe_compat.exceptions import PermissionError
    with pytest.raises(PermissionError) as ei:
        import_mitglieder_uebernehmen("Vorname;Nachname;Email\nNeu;Person;sm@x.org")
    assert "Verwaltungskonto" in str(ei.value), ei.value
    assert "System Manager" in _rollen("sm@x.org")



def test_kontowechsel_darf_aktiven_sm_durch_wieder_aktiven_sm_ersetzen(patched_db, fake_redis):
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.api.zugang import _aktive_system_manager
    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager", mitglied=False)
    _konto(sess, "sm2@x.org", "System Manager", mitglied=False)
    sess.add(Mitglied(name="M-sperre", user="sm2@x.org", ausgeschlossen=True))
    sess.commit()
    set_user("sm@x.org")
    # Der Nachzustand hat weiterhin einen SM: sm2 wird frei, sm wird gesperrt.
    _update_doc("Mitglied", "M-sperre", {"user": "sm@x.org"})
    assert _aktive_system_manager() == {"sm2@x.org"}
