"""P1-8c — Reproduktionstests der Rechte-Nacharbeit (R-P1-8b, B-neu und Folgepunkte).

Diese Tests stammen aus dem unabhaengigen Sicherheits-Nachreview
(Befund) und waren VOR der Behebung rot:

  * B-neu (1) — ein Mitgliederadministrator schliesst das Mitglied eines
    System Managers aus; der Aussperrschutz sass nur in
    `schliesse_mitglied_aus` und war ueber `PUT /api/resource/Mitglied/<id>`
    bzw. `_apply_resource_write` umgehbar.
  * B-neu (2) — der letzte System Manager schloss sich per generischem
    Schreibweg selbst aus.
  * B-neu (3) — `Mitglied.user` auf ein Verwaltungskonto umbiegen.
  * Punkt 2 — Falsch-Positiv: der einzige System Manager durfte sich keine
    Zusatzrolle geben (der Schutz griff, obwohl „System Manager" gar nicht in
    `ZUGANGS_ROLLEN` steht und damit nie angetastet wurde).
  * Punkt 4 — E-Mail-Zuordnung des Ausschlusses traf bei einem Familienpostfach
    das falsche Mitglied.
  * Punkt 5 — Reproduktionstests fuer `konto_freischalten`, den E-Mail-Pfad,
    die Rollenpruefung ueber `get_roles` (W3), den Auswahl-Leak (W4), W-A und
    K-D/K-A.

Ohne die Aenderungen in `frappe_compat/api_helpers.py`,
`frappe_compat/router.py`, `frappe_compat/benutzer_status.py`, `api/zugang.py`
und `api/kronos/calendar_get.py` waeren die markierten Tests rot.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.kronos import Element, Kalender

from tests.test_permissions import hierarchie  # noqa: F401  (Fixture fuer W4)


def _konto(sess, email: str, rolle: str | None = None, *, enabled: bool = True) -> None:
    """Konto mit optionaler Rolle und verknuepftem Mitglied anlegen."""
    sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.add(Mitglied(name=f"M-{email}", vorname=email, nachname="Test",
                      email=email, status="Mitglied", user=email, docstatus=0, idx=0))
    sess.commit()


def _mitglied(sess, name: str, *, user: str | None = None, email: str | None = None,
              status: str = "Mitglied", ausgeschlossen: int = 0) -> None:
    """Mitglied ohne Konto (fuer Mehrdeutigkeits-/Altimport-Faelle)."""
    sess.add(Mitglied(name=name, vorname=name, nachname="Test", email=email,
                      status=status, user=user, ausgeschlossen=bool(ausgeschlossen),
                      docstatus=0, idx=0))
    sess.commit()


def _kalender(sess, name: str = "K1") -> None:
    """Minimaler Kalender-Datensatz (Element.element_calendar ist ein Link)."""
    sess.add(Kalender(name=name, calendar_name=name, docstatus=0, idx=0))
    sess.commit()


def _element(sess, name: str, *, owner: str, status: str = "Abgelehnt",
             grund: str = "", kalender: str = "K1") -> None:
    sess.add(Element(
        name=name, element_name="Termin", element_calendar=kalender,
        element_start=datetime(2026, 11, 1, 18, 0),
        element_end=datetime(2026, 11, 1, 19, 0),
        status=status, ablehnungs_grund=grund or None, moderiert_von="mod@x.org",
        owner=owner, docstatus=0, idx=0,
    ))
    sess.commit()


# ── B-neu (1a): Ausschluss eines Verwaltungskontos nur durch System Manager ──


def test_mitgliederadmin_darf_system_manager_mitglied_nicht_ausschliessen(patched_db) -> None:
    """(a) Der Ausschluss ueber den Endpunkt prueft die Rolle des Ziels."""
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")  # zwei SM: allein waere es der letzte
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        schliesse_mitglied_aus("M-sm@x.org", "Test")
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm@x.org").ausgeschlossen) is False


def test_generischer_weg_verweigert_ausschluss_durch_mitgliederadmin(patched_db) -> None:
    """(a) DERSELBE Schutz greift im generischen Schreibweg (Route `PUT`)."""
    from diakronos_app.frappe_compat.router import _apply_resource_write

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("ma@x.org")

    antwort = _apply_resource_write("Mitglied", "M-sm@x.org", {"ausgeschlossen": 1})
    assert getattr(antwort, "status_code", 200) == 403
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm@x.org").ausgeschlossen) is False


def test_update_doc_verweigert_ausschluss_durch_mitgliederadmin(patched_db) -> None:
    """(a) Auch der interne Weg (`_update_doc`) ist dicht — die Schranke sitzt dort."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-sm@x.org", {"ausgeschlossen": 1, "status": "Passiver Gast"})
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm@x.org").ausgeschlossen) is False


# ── B-neu (1b): der letzte System Manager ist ueber keinen Weg aussperrbar ──


def test_letzter_sm_nicht_ueber_generischen_weg_ausschliessbar(patched_db) -> None:
    """(b) Der Selbstausschluss des letzten SM ueber `_apply_resource_write`."""
    from diakronos_app.frappe_compat.router import _apply_resource_write

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    antwort = _apply_resource_write("Mitglied", "M-sm@x.org", {"ausgeschlossen": 1})
    assert getattr(antwort, "status_code", 200) == 403
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm@x.org").ausgeschlossen) is False


def test_letzter_sm_nicht_ueber_update_doc_ausschliessbar(patched_db) -> None:
    """(b) Derselbe Fall ueber den internen Weg."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-sm@x.org", {"ausgeschlossen": 1})
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm@x.org").ausgeschlossen) is False


def test_generischer_weg_erlaubt_ausschluss_bei_zwei_sm(patched_db) -> None:
    """Gegenprobe: mit zwei System Managern darf der eine den anderen ausschliessen."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm1@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    set_user("sm1@x.org")

    _update_doc("Mitglied", "M-sm2@x.org", {"ausgeschlossen": 1})
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm2@x.org").ausgeschlossen) is True


def test_generischer_weg_erlaubt_aufheben_ohne_admin(patched_db) -> None:
    """Gegenprobe: `ausgeschlossen=0` (Aufheben) ist keine Aussperrung."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")

    _update_doc("Mitglied", "M-sm@x.org", {"ausgeschlossen": 0})
    sess.expire_all()
    assert bool(sess.get(Mitglied, "M-sm@x.org").ausgeschlossen) is False


# ── B-neu (1c): `Mitglied.user` umbiegen ────────────────────────────────────


def test_mitgliederadmin_darf_konto_nicht_auf_admin_umbiegen(patched_db) -> None:
    """(c) Ein Mitgliederadministrator verbiegt kein Mitglied auf ein SM-Konto."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-ma@x.org", {"user": "sm@x.org"})
    sess.expire_all()
    assert sess.get(Mitglied, "M-ma@x.org").user == "ma@x.org"


def test_mitgliederadmin_darf_konto_nicht_auf_fremdes_mitglied_umbiegen(patched_db) -> None:
    """(c) Auch ein Konto, das schon einem anderen Mitglied gehoert, ist tabu."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "x@x.org", "Mitglied")
    _mitglied(sess, "M-ohne", email="ohne@x.org")
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        _update_doc("Mitglied", "M-ohne", {"user": "x@x.org"})
    sess.expire_all()
    assert sess.get(Mitglied, "M-ohne").user is None


def test_system_manager_darf_konto_umbiegen(patched_db) -> None:
    """Gegenprobe: ein System Manager darf die Verknuepfung setzen."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "sm2@x.org", "System Manager")
    _mitglied(sess, "M-ohne", email="ohne@x.org")
    set_user("sm@x.org")

    _update_doc("Mitglied", "M-ohne", {"user": "sm2@x.org"})
    sess.expire_all()
    assert sess.get(Mitglied, "M-ohne").user == "sm2@x.org"


def test_gleiches_konto_nochmal_setzen_ist_erlaubt(patched_db) -> None:
    """Gegenprobe: der unveraenderte `user`-Link loest keine Pruefung aus."""
    from diakronos_app.frappe_compat.api_helpers import _update_doc

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("ma@x.org")

    _update_doc("Mitglied", "M-ma@x.org", {"user": "ma@x.org"})
    sess.expire_all()
    assert sess.get(Mitglied, "M-ma@x.org").user == "ma@x.org"


# ── Punkt 2: Falsch-Positiv in `setze_rollen` ───────────────────────────────


def test_letzter_system_manager_darf_sich_zusatzrolle_geben(patched_db) -> None:
    """Der einzige SM darf sich Zusatzrollen geben (System Manager bleibt)."""
    from diakronos_app.api.zugang import setze_rollen

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    r = setze_rollen("M-sm@x.org", ["Mitglied", "Kalenderadministrator"])
    assert r["success"] is True
    assert "System Manager" in r["konto"]["rollen"]
    assert "Kalenderadministrator" in r["konto"]["rollen"]


def test_letzter_mitgliederadmin_behaelt_rolle_bei_zusatz(patched_db) -> None:
    """Auch der letzte Mitgliederadministrator darf sich Zusatzrollen geben.

    Ein System Manager rollt das Konto um — der Mitgliederadministrator selbst
    darf sein eigenes Verwaltungskonto nach B1 nicht anfassen (bestehende,
    richtige Regel).
    """
    from diakronos_app.api.zugang import setze_rollen

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    set_user("sm@x.org")

    r = setze_rollen("M-ma@x.org", ["Mitgliederadministrator", "Tester"])
    assert r["success"] is True
    assert "Mitgliederadministrator" in r["konto"]["rollen"]
    assert "Tester" in r["konto"]["rollen"]


def test_letzter_sm_verliert_rolle_weiterhin_nicht(patched_db) -> None:
    """Gegenprobe zum Falsch-Positiv: der Falsch-Positiv-Fix kippt den Schutz nicht.

    Der Punkt-2-Fix laesst den letzten System Manager sich Zusatzrollen geben,
    weil „System Manager" gar nicht in `ZUGANGS_ROLLEN` steht und damit nie
    entfernt wird (siehe `test_letzter_system_manager_darf_sich_zusatzrolle_geben`).
    Diese Gegenprobe zeigt, dass die Rolle danach tatsaechlich noch da ist und
    der Aussperrschutz bei einem echten Rollenverlust weiter greift.
    """
    from diakronos_app.api.zugang import konto_sperren, setze_rollen
    from diakronos_app.frappe_compat.exceptions import PermissionError as PE

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    set_user("sm@x.org")

    r = setze_rollen("M-sm@x.org", ["Mitglied"])
    assert "System Manager" in r["konto"]["rollen"]

    # Der harte Weg (Konto sperren) bleibt fuer den letzten SM verweigert.
    with pytest.raises(PE):
        konto_sperren("M-sm@x.org", True)


# ── Punkt 4: Ausschluss-Abgleich ueber E-Mail ───────────────────────────────


def test_ausschluss_ueber_email_auch_bei_doppelter_adresse(
    patched_db, fake_redis, altbestand_dublette,
) -> None:
    """Doppelte Adresse (Altbestand): ein Ausschluss wirkt trotzdem — fail closed.

    Fachentscheidung (Manuel, 2026-10-19): eine Adresse gehoert hoechstens zu
    EINEM Mitglied; neue Dopplungen werden abgelehnt. Bleibt eine Dopplung im
    Altbestand, darf die Adresse den Ausschluss nicht aushebeln — das Konto
    gilt als ausgeschlossen, sobald ein Mitglied der Adresse ausgeschlossen
    ist.
    """
    from diakronos_app.frappe_compat.benutzer_status import _mitglied_ausgeschlossen

    sess = patched_db()
    sess.add(User(name="familie@x.org", email="Familie@X.org", full_name="Familie",
                  enabled=True))
    sess.commit()
    # Zwei Mitglieder mit derselben (nur in der Schreibweise verschiedenen) Adresse.
    _mitglied(sess, "M-kind1", email="familie@x.org", ausgeschlossen=1)
    _mitglied(sess, "M-kind2", email="Familie@X.org", ausgeschlossen=0)

    assert _mitglied_ausgeschlossen("familie@x.org") is True


def test_ausschluss_ueber_email_trifft_bei_eindeutiger_adresse(patched_db, fake_redis) -> None:
    """Gegenprobe: genau ein Mitglied -> die E-Mail-Zuordnung greift (Altimport)."""
    from diakronos_app.frappe_compat.benutzer_status import _mitglied_ausgeschlossen

    sess = patched_db()
    sess.add(User(name="allein@x.org", email="allein@x.org", full_name="Allein",
                  enabled=True))
    sess.commit()
    _mitglied(sess, "M-allein", email="allein@x.org", ausgeschlossen=1)

    assert _mitglied_ausgeschlossen("allein@x.org") is True


def test_ausschluss_ueber_email_case_insensitiv(patched_db, fake_redis) -> None:
    """Die Adresse wird ohne Ruecksicht auf Gross-/Kleinschreibung verglichen."""
    from diakronos_app.frappe_compat.benutzer_status import _mitglied_ausgeschlossen

    sess = patched_db()
    sess.add(User(name="c@x.org", email="C@X.ORG", full_name="C", enabled=True))
    sess.commit()
    _mitglied(sess, "M-c", email="c@x.org", ausgeschlossen=1)

    assert _mitglied_ausgeschlossen("c@x.org") is True


def test_user_link_entscheidet_auch_bei_mehrdeutigem_postfach(patched_db, fake_redis) -> None:
    """Der `user`-Link gilt weiter — auch wenn die Adresse mehrdeutig ist."""
    from diakronos_app.frappe_compat.benutzer_status import _mitglied_ausgeschlossen

    sess = patched_db()
    sess.add(User(name="familie@x.org", email="familie@x.org", full_name="F",
                  enabled=True))
    sess.commit()
    _mitglied(sess, "M-kind1", email="familie@x.org", ausgeschlossen=1)
    _mitglied(sess, "M-konto", email="konto@x.org", user="familie@x.org",
              ausgeschlossen=1)

    assert _mitglied_ausgeschlossen("familie@x.org") is True


def test_ausgeschlossener_sm_zaehlt_nicht_als_aktiv(patched_db, fake_redis) -> None:
    """P1-8d(c): Auch Altdaten heben einen tatsächlichen Ausschluss nicht auf."""
    from diakronos_app.frappe_compat.benutzer_status import ist_aktiv

    sess = patched_db()
    _konto(sess, "sm@x.org", "System Manager")
    # Markierung direkt in der DB (an der API vorbei, wie ein Altdatenstand).
    sess.expire_all()
    sess.get(Mitglied, "M-sm@x.org").ausgeschlossen = True
    sess.commit()
    set_user("sm@x.org")

    assert ist_aktiv("sm@x.org") is False


# ── Punkt 5: `konto_freischalten` (Backend) ─────────────────────────────────


def test_konto_freischalten_setzt_enabled(patched_db, fake_redis) -> None:
    """Ein wartendes (gesperrtes) Konto laesst sich freischalten."""
    from diakronos_app.api.zugang import get_wartende_konten, konto_freischalten

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "wartend@x.org", "Mitglied", enabled=False)
    set_user("ma@x.org")

    wartende = get_wartende_konten()
    liste = wartende.get("konten") or wartende.get("user") or []
    assert "wartend@x.org" in [
        (w["user"] if isinstance(w, dict) else w) for w in liste
    ]

    r = konto_freischalten("wartend@x.org")
    assert r["konto"]["enabled"] is True


def test_mitgliederadmin_darf_gesperrtes_sm_konto_nicht_freischalten(patched_db, fake_redis) -> None:
    """Der Verwaltungskonto-Schutz gilt auch fuer die Freischaltung (B1)."""
    from diakronos_app.api.zugang import konto_freischalten

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager", enabled=False)
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        konto_freischalten("sm@x.org")


# ── Punkt 5: W3 — Rollenpruefung ueber `get_roles` ──────────────────────────


def test_get_roles_liefert_rollen_des_kontos(patched_db) -> None:
    """W3: `get_roles(user)` liest die Rollen des KONTOS, nicht des Aufrufers."""
    from diakronos_app.frappe_compat.permissions import get_roles

    sess = patched_db()
    _konto(sess, "ma@x.org", "Mitgliederadministrator")
    _konto(sess, "sm@x.org", "System Manager")
    set_user("ma@x.org")

    assert "System Manager" in get_roles("sm@x.org")
    assert "System Manager" not in get_roles()
    assert "Mitgliederadministrator" in get_roles()


# ── Punkt 5: W4 — Auswahl-Leak ──────────────────────────────────────────────


def test_verantwortliche_auswahl_verweigert_nicht_berechtigte(hierarchie) -> None:
    """W4: ein Mitglied ohne Pflegerecht bekommt die Personenauswahl nicht."""
    from diakronos_app.api.verantwortliche import get_verantwortliche_auswahl

    sess = hierarchie
    _konto(sess, "einfach@example.org", "Mitglied")
    set_user("einfach@example.org")

    with pytest.raises(FrappePermissionError):
        get_verantwortliche_auswahl("Gruppe", "G-A1", "")


def test_verantwortliche_auswahl_ohne_email_der_ziele(hierarchie) -> None:
    """W4: die Auswahlliste traegt keine E-Mail-Adressen (kein Adressbuch-Leak)."""
    from diakronos_app.api.verantwortliche import get_verantwortliche_auswahl

    sess = hierarchie
    sess.add_all([
        User(name="mit@example.org", email="mit@example.org", full_name="Mit Konto",
             enabled=True),
        Mitglied(name="M-mit", vorname="Mit", nachname="Konto", email="mit@example.org",
                 status="Mitglied", user="mit@example.org", docstatus=0, idx=0),
    ])
    sess.commit()
    set_user("admin@example.org")

    daten = get_verantwortliche_auswahl("Gruppe", "G-A1", "")
    for person in daten["auswahl"]:
        assert "email" not in person or not person["email"] or \
            person["email"] == person.get("user")


# ── Punkt 5: W-A — abgelehnte Termine bleiben aus den Listen heraus ─────────


def test_abgelehnter_termin_ist_in_keiner_liste(patched_db, fake_redis) -> None:
    """W-A: `get_calendar_events` liefert abgelehnte Termine in keinem Modus."""
    from diakronos_app.api.kronos.calendar_get import get_calendar_events

    sess = patched_db()
    _konto(sess, "mod@x.org", "Kalenderadministrator")
    _kalender(sess)
    _element(sess, "E-abg", owner="mod@x.org", status="Abgelehnt")
    _element(sess, "E-fest", owner="mod@x.org", status="Festgelegt")
    set_user("mod@x.org")

    for modus in (True, False):
        namen = {
            e["extendedProps"]["name"]
            for e in get_calendar_events("2026-10-01", "2026-12-31", view_mode=modus)
        }
        assert "E-abg" not in namen
        assert "E-fest" in namen


# ── Punkt 3/5: K-A — Ablehnungsgrund fuer den Antragsteller ─────────────────


def test_antragsteller_sieht_ablehnungsgrund_seines_termin(patched_db, fake_redis) -> None:
    """K-A: der eigene abgelehnte Termin ist ueber den eigenen Endpunkt sichtbar."""
    from diakronos_app.api.kronos.calendar_get import get_mein_termin

    sess = patched_db()
    _konto(sess, "antrag@x.org", "Mitglied")
    _kalender(sess)
    _element(sess, "E-1", owner="antrag@x.org",
             grund="Termin kollidiert mit dem Gottesdienst")
    set_user("antrag@x.org")

    r = get_mein_termin("E-1")
    assert r["status"] == "Abgelehnt"
    assert r["ist_antwortsteller"] is True
    assert "Gottesdienst" in r["ablehnungs_grund"]


def test_fremder_sieht_ablehnungsgrund_nicht(patched_db, fake_redis) -> None:
    """K-A: ein Fremder bekommt den Grund nicht (harte Schranke bleibt)."""
    from diakronos_app.api.kronos.calendar_get import get_mein_termin

    sess = patched_db()
    _konto(sess, "fremd@x.org", "Mitglied")
    _kalender(sess)
    _element(sess, "E-2", owner="antrag@x.org", grund="Interner Grund")
    set_user("fremd@x.org")

    with pytest.raises(FrappePermissionError):
        get_mein_termin("E-2")


def test_moderator_sieht_ablehnungsgrund(patched_db, fake_redis) -> None:
    """K-A: ein Moderator des Kalenders sieht den Grund weiterhin."""
    from diakronos_app.api.kronos.calendar_get import get_mein_termin

    sess = patched_db()
    _konto(sess, "mod@x.org", "Kalenderadministrator")
    _kalender(sess)
    _element(sess, "E-3", owner="antrag@x.org", grund="Umbesetzung")
    set_user("mod@x.org")

    r = get_mein_termin("E-3")
    assert r["ist_antwortsteller"] is False
    assert r["ablehnungs_grund"] == "Umbesetzung"


def test_geloeschter_termin_meldet_nicht_gefunden(patched_db, fake_redis) -> None:
    """Gegenprobe: eine unbekannte Kennung ergibt einen fachlichen Fehler."""
    from diakronos_app.api.kronos.calendar_get import get_mein_termin
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    sess = patched_db()
    _konto(sess, "antrag@x.org", "Mitglied")
    set_user("antrag@x.org")

    with pytest.raises(DoesNotExistError):
        get_mein_termin("E-gibtsnicht")


def test_eigene_abgelehnte_termine_liste(patched_db, fake_redis) -> None:
    """K-A: der Antragsteller findet seine eigenen abgelehnten Termine."""
    from diakronos_app.api.kronos.calendar_get import get_meine_abgelehnten_termine

    sess = patched_db()
    _konto(sess, "antrag@x.org", "Mitglied")
    _konto(sess, "fremd@x.org", "Mitglied")
    _kalender(sess)
    _element(sess, "E-mein", owner="antrag@x.org", grund="Mein Grund")
    _element(sess, "E-fremd", owner="fremd@x.org", grund="Fremder Grund")
    _element(sess, "E-offen", owner="antrag@x.org", status="Vorschlag")
    set_user("antrag@x.org")

    daten = get_meine_abgelehnten_termine()
    ids = {t["id"] for t in daten}
    # Nur die EIGENEN abgelehnten Termine — nicht der fremde, nicht der offene.
    assert ids == {"E-mein"}
    assert daten[0]["ablehnungs_grund"] == "Mein Grund"


# ── Punkt 5: K-D — Meldungstyp der Terminmoderation ────────────────────────


def test_terminmoderation_erzeugt_eigenen_meldungstyp(patched_db, fake_redis) -> None:
    """K-D: die Ablehnung meldet sich mit eigenem Typ `Terminmoderation`."""
    from diakronos_app.api.kronos.kanban_api import _benachrichtige_owner
    from diakronos_app.models.core import NotificationLog
    from diakronos_app.db import aktuelle_sitzung, lesesitzung

    sess = patched_db()
    _kalender(sess)
    _element(sess, "E-4", owner="antrag@x.org", grund="Grund")
    set_user("mod@x.org")

    # Der Schreibweg flusht in die Sitzung des Aufrufers (ContextVar). Ohne
    # Request-Rahmen wird hier die Test-Sitzung gestellt, damit die Zeile
    # sichtbar wird, ohne dass etwas committet wird.
    with lesesitzung() as s:
        token = aktuelle_sitzung.set(s)
        try:
            _benachrichtige_owner(
                {"name": "E-4", "element_name": "Termin", "owner": "antrag@x.org"},
                "E-4", "Grund",
            )
            s.flush()
            typen = sorted(
                str(z.type) for z in s.query(NotificationLog).all()
                if z.type is not None
            )
        finally:
            aktuelle_sitzung.reset(token)
    assert typen == ["Terminmoderation"]
