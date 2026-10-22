"""AUSTRITT — Austritt/Deaktivieren (A1/A2), gekuerzte Anzeige (A3), Reaktivieren (A4).

Die Proben sind JE ZUSAGE geschrieben: Rechte, Wirkung (Login/Sitzung/CalDAV),
Anzeige ohne Klarnamen in der API-Antwort und die vollstaendige
Wiederherstellung beim Reaktivieren.

Rot-vorher/gruen-nachher: die Datei ist gegen `main` gruen-faehig nur mit den
Aenderungen dieser Karte — `mitglied_austritt`, `mitglied_reaktivieren`,
`personen_anzeige` und die drei Spalten existieren dort nicht (Import-Fehler).
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

SM = "System Manager"
MA = "Mitgliederadministrator"


def _konto(sess, email: str, rolle: str | None = None, *,
           mitglied: bool = True, link: bool = True, enabled: bool = True) -> None:
    sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
    if rolle:
        sess.add(HasRole(name=f"HR-{email}-{rolle}", parent=email, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=1))
    if mitglied:
        sess.add(Mitglied(
            name=f"M-{email}", vorname="Elvira", nachname="Dorn",
            email=email, status="Mitglied", user=email if link else None,
            telefonnummer="0711 123456", geburtstag=None, wohnort="Stuttgart",
            postleitzahl="70173", straße="Marktplatz", nummer="1",
            ausgeschlossen=0, docstatus=0, idx=0,
        ))
    sess.commit()


def _zeile(sess, name: str) -> Mitglied:
    sess.expire_all()
    return sess.get(Mitglied, name)


def _konten(user: str) -> dict[str, bool]:
    """Enabled-Zustand aller User-Zeilen (frische Sicht)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User as U

    sess = SessionLocal()
    try:
        return {r.name: bool(r.enabled) for r in sess.query(U).all()}
    finally:
        sess.close()


# ── A1: Rechte ──────────────────────────────────────────────────────────────


def test_nicht_admin_darf_keinen_austritt_erfassen(patched_db) -> None:
    """A1: ohne Verwaltungsrolle kein Austritt — und die Person bleibt aktiv."""
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "mitglied@x.org")
    set_user("mitglied@x.org")

    with pytest.raises(FrappePermissionError):
        mitglied_austritt("M-ma@x.org", "Austritt auf eigenen Wunsch")
    assert bool(_zeile(sess, "M-ma@x.org").ausgeschlossen) is False


def test_austritt_ohne_begruendung_ist_erlaubt(patched_db) -> None:
    """A1: die Begruendung ist FREIWILLIG („optionale Begruendung + Datum“).

    AUSTRITT-b (N1): der erste Wurf machte daraus eine Pflicht und begruendete
    das mit der Unterscheidung Austritt/Ausschluss. Die Unterscheidung
    traegt aber der Status („Ausgetreten“) — und eine Begruendung kann eine
    Krankheit nennen, die niemanden ausser der Person etwas angeht.
    """
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    mitglied_austritt("M-ziel@x.org", "   ")
    zeile = _zeile(sess, "M-ziel@x.org")
    assert zeile.status == "Ausgetreten"
    assert zeile.austritt_grund is None


def test_mitgliederadmin_darf_kein_verwaltungskonto_ausstellen(patched_db) -> None:
    """A1/SEC-W1: ein Mitgliederadministrator fasst kein SM-Konto an."""
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "sm@x.org", SM)
    _konto(sess, "sm2@x.org", SM)  # nicht der letzte — die Rollenschranke greift
    set_user("ma@x.org")

    with pytest.raises(FrappePermissionError):
        mitglied_austritt("M-sm@x.org", "Test")
    assert bool(_zeile(sess, "M-sm@x.org").ausgeschlossen) is False


def test_letzter_system_manager_kann_sich_nicht_ausstellen(patched_db) -> None:
    """A1: der letzte System Manager darf die Verwaltung nicht aussperren."""
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "sm@x.org", SM)
    set_user("sm@x.org")

    with pytest.raises(FrappePermissionError):
        mitglied_austritt("M-sm@x.org", "Ich hoere auf")
    assert bool(_zeile(sess, "M-sm@x.org").ausgeschlossen) is False


def test_system_manager_darf_mitglied_ausstellen(patched_db) -> None:
    """Gegenprobe A1: mit zwei SM darf der eine den anderen ausstellen."""
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "sm1@x.org", SM)
    _konto(sess, "sm2@x.org", SM)
    set_user("sm1@x.org")

    mitglied_austritt("M-sm2@x.org", "Wechselt die Gemeinde")
    assert bool(_zeile(sess, "M-sm2@x.org").ausgeschlossen) is True


# ── A2: Wirkung ─────────────────────────────────────────────────────────────


def test_austritt_setzt_status_konto_und_sitzungen(patched_db) -> None:
    """A2: Status „Ausgetreten“, Konto deaktiviert, Sitzungen widerrufen."""
    from diakronos_app.api.austritt import STATUS_AUSGETRETEN, mitglied_austritt
    from diakronos_app.frappe_compat import benutzer_status

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    mitglied_austritt("M-ziel@x.org", "Austritt auf eigenen Wunsch", "2026-10-01")

    zeile = _zeile(sess, "M-ziel@x.org")
    assert zeile.status == STATUS_AUSGETRETEN
    assert zeile.ausgeschlossen is True
    assert str(zeile.austritt_datum) == "2026-10-01"
    assert zeile.austritt_grund == "Austritt auf eigenen Wunsch"
    assert zeile.vor_austritt_status == "Mitglied"
    # Konto aus — das ist der Riegel fuer Login, CalDAV und OIDC.
    assert _konten("ziel@x.org")["ziel@x.org"] is False
    # Und die Rechtepruefung sieht die Person nicht mehr.
    benutzer_status.vergiss("ziel@x.org")
    assert benutzer_status.ist_aktiv("ziel@x.org") is False


def test_austritt_widerruft_offene_sitzungen(patched_db, fake_redis) -> None:
    """A2: bestehende Sitzungen sind SOFORT weg (nicht erst nach dem TTL)."""
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.frappe_compat import sitzungen

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    sid, _token = sitzungen.anlegen("ziel@x.org")
    assert sitzungen.lesen(sid) is not None
    set_user("ma@x.org")

    mitglied_austritt("M-ziel@x.org", "Austritt")
    assert sitzungen.lesen(sid) is None


def test_austritt_meldet_unbekanntes_mitglied(patched_db) -> None:
    """A2: keine stille Erfolgsmeldung fuer eine erfundene Kennung."""
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    set_user("ma@x.org")

    with pytest.raises(ValidationError):
        mitglied_austritt("M-gibt-es-nicht", "Test")


def test_zweiter_austritt_ist_kein_stiller_erfolg(patched_db) -> None:
    """A2: ein zweiter Austritt aendert Datum/Grund nicht heimlich."""
    from diakronos_app.api.austritt import mitglied_austritt

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    mitglied_austritt("M-ziel@x.org", "Erster Grund", "2026-10-01")
    with pytest.raises(ValidationError):
        mitglied_austritt("M-ziel@x.org", "Zweiter Grund", "2026-12-24")
    assert _zeile(sess, "M-ziel@x.org").austritt_grund == "Erster Grund"


def test_austritt_protokolliert_den_vorgang(patched_db) -> None:
    """A2: Protokolleintrag wie bei jedem anderen Statuswechsel."""
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.models.diakonos import AuditLog

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    mitglied_austritt("M-ziel@x.org", "Austritt auf eigenen Wunsch")
    sess.expire_all()
    zeilen = sess.query(AuditLog).filter(
        AuditLog.target_name == "M-ziel@x.org",
        AuditLog.action_typ == "Profiländerung",
    ).all()
    assert zeilen, "Kein Protokolleintrag geschrieben"
    text = " ".join(f"{z.old_value} {z.new_value} {z.field_changed}" for z in zeilen)
    assert "Ausgetreten" in text
    assert "Austritt auf eigenen Wunsch" in text


def test_ausgetretene_person_faellt_aus_der_auswahlliste(patched_db) -> None:
    """A2: nicht mehr in Auswahllisten angeboten (gruppen_auswahl)."""
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.api.gruppen_auswahl import waehlbare_mitglieder

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    vorher = {z["mitglied"] for z in waehlbare_mitglieder()}
    assert "M-ziel@x.org" in vorher
    mitglied_austritt("M-ziel@x.org", "Austritt")
    nachher = {z["mitglied"] for z in waehlbare_mitglieder()}
    assert "M-ziel@x.org" not in nachher


# ── A3: gekuerzte Anzeige ───────────────────────────────────────────────────


def test_maskiere_email_nach_muster() -> None:
    """A3: erste drei Zeichen + Sterne + Endung."""
    from diakronos_app.frappe_compat.personen_anzeige import maskiere_email

    assert maskiere_email("elvira@example.de") == "elv*******.de"
    assert maskiere_email("Elvira@Example.DE") == "elv*******.de"
    assert maskiere_email("") is None
    assert maskiere_email(None) is None


def test_kuerze_name_ist_vorname_und_initialie() -> None:
    """A3: „Elvira D.“ — der Nachname bleibt ein Buchstabe."""
    from diakronos_app.frappe_compat.personen_anzeige import kuerze_name

    assert kuerze_name("Elvira", "Dorn") == "Elvira D."
    assert kuerze_name("Elvira", "") == "Elvira"
    assert kuerze_name("", "Dorn") == "D."
    assert kuerze_name("", "", "M-123") == "M."


def test_api_liste_liefert_fuer_nicht_admin_keinen_klarnamen(patched_db) -> None:
    """A3: die LISTE des Nicht-Admins enthaelt weder Klarname noch Klar-Mail.

    Die Kennung `name` ist der Primaerschluessel des Datensatzes (aus der
    Adresse gebildet) und bleibt als technische ID stehen — sie ist kein
    Anzeigefeld. Geprueft werden deshalb die PERSONENFELDER.
    """
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.api.mitglieder import get_mitglieder_liste

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "leser@x.org")
    _konto(sess, "ziel@x.org")
    # Gruppe-Profil (vor dem `|`), nicht Bereich — sonst findet die
    # Bereichs-Sicht der Liste die Zeile nicht (dieselbe Falle wie in
    # `test_detail_liefert_fuer_nicht_admin_nur_kurzform`).
    for name in ("M-leser@x.org", "M-ziel@x.org"):
        sess.get(Mitglied, name).ancestor_path = "/gemeinde/|"
    sess.commit()
    set_user("ma@x.org")
    mitglied_austritt("M-ziel@x.org", "Austritt")

    set_user("leser@x.org")
    antwort = get_mitglieder_liste(status="Ausgetreten", persoenliche_daten=True)
    zeile = next(z for z in antwort["data"] if z["name"] == "M-ziel@x.org")
    assert "Dorn" not in repr(zeile)
    assert zeile["full_name"] == "Elvira D."
    assert zeile["nachname"] is None
    assert zeile["email"] == "zie*******.org"
    assert zeile["telefonnummer"] is None
    assert zeile["wohnort"] is None
    assert zeile["postleitzahl"] is None
    assert zeile["straße"] is None


def test_api_liste_blendet_ausgetretene_standardmaessig_aus(patched_db) -> None:
    """A5: Standard ausgeblendet, mit Filter sichtbar."""
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.api.mitglieder import get_mitglieder_liste

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    _konto(sess, "bleibt@x.org")
    set_user("ma@x.org")

    vorher = {z["name"] for z in get_mitglieder_liste()["data"]}
    assert "M-ziel@x.org" in vorher
    mitglied_austritt("M-ziel@x.org", "Austritt")

    standard = {z["name"] for z in get_mitglieder_liste()["data"]}
    assert "M-ziel@x.org" not in standard
    assert "M-bleibt@x.org" in standard
    gefiltert = {z["name"] for z in get_mitglieder_liste(status="Ausgetreten")["data"]}
    assert gefiltert == {"M-ziel@x.org"}
    # `total` zaehlt dieselbe Menge wie die Liste.
    assert get_mitglieder_liste()["total"] == len(standard)


def test_sichtbarkeits_glied_ist_auf_postgresql_lauffaehig() -> None:
    """A5: das SQL-Glied fuer „nur Aktive“ muss den BOOLEAN-Typ treffen.

    Vorfall im Teststack (2026-10-20): `m.ausgeschlossen = 0` liess die
    Mitgliederliste auf PostgreSQL mit ``operator does not exist:
    boolean = integer`` abstuerzen (HTTP 500). SQLite nimmt den Vergleich
    hin — die Testsuite sah den Fehler deshalb nicht. Der Test prueft die
    erzeugte Abfrage auf den Typfehler, statt eine Datenbank zu brauchen.
    """
    import inspect

    from diakronos_app.api import mitglieder as modul

    quelle = inspect.getsource(modul.get_mitglieder_liste)
    assert "ausgeschlossen = 0" not in quelle, "Vergleich Boolean = Integer"
    assert "ausgeschlossen = 1" not in quelle, "Vergleich Boolean = Integer"
    # AUSTRITT-b (B3): ausgeblendet wird nur der Ausgetretene (Status/Grund),
    # nicht jeder Ausgeschlossene.
    assert "Ausgetreten" in quelle and "austritt_grund" in quelle



def test_admin_sieht_klarnamen_und_austrittsdatum(patched_db) -> None:
    """A3: Administratoren sehen alles inkl. „ausgetreten seit …“."""
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.api.mitglieder import get_mitglied_detail, get_mitglieder_liste

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")
    mitglied_austritt("M-ziel@x.org", "Austritt", "2026-09-15")

    zeile = next(z for z in get_mitglieder_liste(status="Ausgetreten")["data"]
                 if z["name"] == "M-ziel@x.org")
    assert zeile["full_name"] == "Elvira Dorn"
    detail = get_mitglied_detail("M-ziel@x.org")["data"]
    assert detail["vorname"] == "Elvira"
    assert detail["austritt"]["ausgetreten"] is True
    assert detail["austritt"]["seit"] == "2026-09-15"
    assert detail["austritt"]["grund"] == "Austritt"


def test_detail_liefert_fuer_nicht_admin_nur_kurzform(patched_db) -> None:
    """A3: die DETAIL-Antwort des Nicht-Admins enthaelt keinen Klarnamen."""
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.api.mitglieder import get_mitglied_detail

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "leser@x.org")
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")
    mitglied_austritt("M-ziel@x.org", "Austritt")

    # Der Leser ist Pfad-berechtigt (gleicher ancestor_path wie das Ziel).
    sess.expire_all()
    for name in ("M-leser@x.org", "M-ziel@x.org"):
        z = sess.get(Mitglied, name)
        z.ancestor_path = "/gemeinde/|"
    sess.commit()
    set_user("leser@x.org")

    daten = get_mitglied_detail("M-ziel@x.org")["data"]
    assert daten["vorname"] == "Elvira D."
    assert daten["nachname"] is None
    # AUSTRITT-b (N2): dieselbe Maske wie in der Liste, nicht `None`.
    assert daten["email"] == "zie*******.org"
    assert daten["telefonnummer"] is None
    assert "Dorn" not in repr(daten)
    # Der Grund ist Verwaltungswissen — er steht nur bei Berechtigten.
    assert daten["austritt"]["grund"] is None


def test_planrahmen_personenpool_kuerzt_fuer_nicht_admin(patched_db) -> None:
    """A3: der Personenpool des Plan-Rahmens liefert nur die Kurzform.

    AUSTRITT-b (B4): Der Pool der KANDIDATEN enthaelt Ausgetretene gar nicht
    mehr (Zuteilbarkeit ist fachlich, nicht rollenabhaengig). Die gekuerzte
    Anzeige gilt deshalb fuer die volle Personenliste der Quelle — dieselbe
    Kuerzung, nur ohne die Kandidaten-Filterung.
    """
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "leser@x.org")
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")
    mitglied_austritt("M-ziel@x.org", "Austritt")

    from diakronos_app.db import SessionLocal

    for wer, pruefe in (("ma@x.org", False), ("leser@x.org", True)):
        set_user(wer)
        s = SessionLocal()
        try:
            quelle = DBDatenquelle(s)
            person = next(p for p in quelle._quelle.personen()
                          if p.kennung == "M-ziel@x.org")
        finally:
            s.close()
        if pruefe:
            assert person.name == "Elvira D."
            assert "Dorn" not in person.nachname
            assert person.email == "zie*******.org"
            # AUSTRITT-b (B4): Kuerzel und Gruppen bleiben fachlich stehen —
            # nur der Name ist gekuerzt.
            assert person.ausgeschieden is True
        else:
            assert person.name == "Elvira Dorn"
            # Die E-Mail bleibt auch fuer den Admin maskiert: sie ist eine
            # Eigenschaft der ausgetretenen Person, keine der Ansicht.
            assert person.email == "zie*******.org"


# ── A4: Reaktivieren ────────────────────────────────────────────────────────


def test_reaktivieren_stellt_alles_wieder_her(patched_db) -> None:
    """A4: Status zurueck, Konto aktiv, Anzeige wieder voll."""
    from diakronos_app.api.austritt import mitglied_austritt, mitglied_reaktivieren
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    # Vorher „Gast“ — der Austritt muss DIESEN Status merken, nicht „Mitglied“.
    sess.get(Mitglied, "M-ziel@x.org").status = "Gast"
    sess.commit()
    set_user("ma@x.org")

    mitglied_austritt("M-ziel@x.org", "Austritt")
    mitglied_reaktivieren("M-ziel@x.org")

    zeile = _zeile(sess, "M-ziel@x.org")
    assert zeile.status == "Gast"
    assert zeile.ausgeschlossen is False
    assert zeile.austritt_grund is None
    assert zeile.austritt_datum is None
    assert zeile.vor_austritt_status is None
    assert _konten("ziel@x.org")["ziel@x.org"] is True
    benutzer_status.vergiss("ziel@x.org")
    assert benutzer_status.ist_aktiv("ziel@x.org") is True

    from diakronos_app.db import SessionLocal

    s = SessionLocal()
    try:
        person = next(p for p in DBDatenquelle(s).personen()
                      if p.kennung == "M-ziel@x.org")
    finally:
        s.close()
    assert person.name == "Elvira Dorn"
    assert person.email == "ziel@x.org"


def test_reaktivieren_ohne_austritt_ist_kein_stiller_erfolg(patched_db) -> None:
    """A4: wer nicht ausgetreten ist, wird nicht „reaktiviert“."""
    from diakronos_app.api.austritt import mitglied_reaktivieren

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    with pytest.raises(ValidationError):
        mitglied_reaktivieren("M-ziel@x.org")


def test_reaktivieren_verlangt_adminrechte(patched_db) -> None:
    """A4: dieselben Rechteregeln wie A1."""
    from diakronos_app.api.austritt import mitglied_austritt, mitglied_reaktivieren

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")
    mitglied_austritt("M-ziel@x.org", "Austritt")

    set_user("ziel@x.org")
    with pytest.raises(FrappePermissionError):
        mitglied_reaktivieren("M-ziel@x.org")
    assert bool(_zeile(sess, "M-ziel@x.org").ausgeschlossen) is True


def test_reaktivieren_entsperrt_kein_fremdes_verwaltungskonto(patched_db) -> None:
    """A4/SEC-W1: Entsperren eines Verwaltungskontos nur durch System Manager."""
    from diakronos_app.api.austritt import mitglied_austritt, mitglied_reaktivieren

    sess = patched_db()
    _konto(sess, "sm1@x.org", SM)
    _konto(sess, "sm2@x.org", SM)
    _konto(sess, "ma@x.org", MA)
    set_user("sm1@x.org")
    mitglied_austritt("M-sm2@x.org", "Austritt")

    set_user("ma@x.org")
    with pytest.raises(FrappePermissionError):
        mitglied_reaktivieren("M-sm2@x.org")
    assert bool(_zeile(sess, "M-sm2@x.org").ausgeschlossen) is True


def test_ausschluss_bleibt_eigener_weg(patched_db) -> None:
    """A2-Entscheidung: „Ausschliessen“ ist NICHT der Austritt.

    Der Ausschluss setzt weiterhin „Passiver Gast“ und laesst die
    Austrittsfelder leer — deshalb bietet die Oberflaeche dort kein
    „Reaktivieren“ an, sondern den Statusweg.
    """
    from diakronos_app.api.austritt import mitglied_reaktivieren
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    sess = patched_db()
    _konto(sess, "ma@x.org", MA)
    _konto(sess, "ziel@x.org")
    set_user("ma@x.org")

    schliesse_mitglied_aus("M-ziel@x.org", "Fehlverhalten")
    zeile = _zeile(sess, "M-ziel@x.org")
    assert zeile.status == "Passiver Gast"
    assert zeile.austritt_grund is None
    with pytest.raises(ValidationError):
        mitglied_reaktivieren("M-ziel@x.org")
