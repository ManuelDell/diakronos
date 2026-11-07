"""UX2c-N2 — Listenfelder `bild` / `calender_details`.

Nacharbeit 2 zu UX2c (Re-Review Opus, 07.11.). Die Frontend-Pruefung
`vollstaendig()` (`rueckgaengigWeg.mjs:154/156`) entscheidet, ob ein
Loeschen ein VOLLSTAENDIGES „Rueckgaengig“ bekommt oder eine Rueckfrage.
Sie greift nur, wenn die LISTEN der Verwaltungsseite die Felder liefern —
vorher taten sie es nicht (`bild` fehlte, `calender_details` fehlte), die
Pruefung war also wirkungslos: eine Ressource mit Bild bzw. ein Kalender aus
dem Google-Import haette ein unvollstaendiges „Rueckgaengig“ angeboten.

Die Tests halten fest, dass beide Listen-Endpunkte die Felder fuehren — und
zwar in der Form, die die Seite weiterreicht (leerer Text statt `null`, Zahl
statt Wahrheitswert bei `wartung`). Gesetzt werden die Felder direkt am
Modell: `create_ressource` und `create_kalender` nehmen sie nicht an (das
Bild setzt der Upload, `calender_details` der Google-Import) — genau deshalb
sind sie nicht wiederherstellbar.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.session import set_user


# ── Fixtures (Muster wie test_p25_verwaltung.py) ────────────────────────────


def _nutzer(sess, name, rollen=()):
    """Benutzer mit echten `Has Role`-Zeilen — dieselbe Quelle wie im Betrieb."""
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=True,
                      password_hash="x"))
    for i, rolle in enumerate(rollen, start=1):
        sess.add(HasRole(name=f"{name}-{i}", parent=name, parenttype="User",
                         parentfield="roles", role=rolle, docstatus=0, idx=i))
    sess.flush()


@pytest.fixture()
def db(patched_db):
    sess = patched_db()
    yield sess
    sess.close()


@pytest.fixture()
def ressourcen_moderator(db):
    _nutzer(db, "ressourcen@test.local", ["Ressourcenmoderator"])
    db.commit()
    set_user("ressourcen@test.local")
    return "ressourcen@test.local"


@pytest.fixture()
def kalender_admin(db):
    _nutzer(db, "kalenderadmin@test.local", ["Administrator", "Kalenderadministrator"])
    db.commit()
    set_user("kalenderadmin@test.local")
    return "kalenderadmin@test.local"


# ── Ressourcenverwaltung: `bild` ────────────────────────────────────────────


def test_ux2c_n2_ressourcenliste_liefert_bild(db, ressourcen_moderator):
    """Eine Ressource MIT Bild zeigt es in der Liste — leer wird zu `""`."""
    from diakronos_app.api import ressourcen
    from diakronos_app.models.kronos import Ressource

    assert ressourcen.create_ressource(name="Gemeindesaal", typ="Raum")["success"]
    assert ressourcen.create_ressource(name="Bus", typ="Fahrzeug")["success"]

    db.expire_all()
    doc = db.get(Ressource, "Gemeindesaal")
    assert doc is not None
    doc.bild = "/files/gemeindesaal.jpg"
    db.commit()

    liste = ressourcen.get_ressourcen_verwaltung()["ressourcen"]
    mit_bild = next(r for r in liste if r["id"] == "Gemeindesaal")
    ohne_bild = next(r for r in liste if r["id"] == "Bus")

    # Der Wert, den die Seite fuer `vollstaendig('ressource', …)` liest.
    assert mit_bild["bild"] == "/files/gemeindesaal.jpg"
    # Kein `null`: die Seite reicht den Wert nur als Text weiter.
    assert ohne_bild["bild"] == ""


def test_ux2c_n2_ressourcenliste_bild_ist_nicht_wiederherstellbar(db, ressourcen_moderator):
    """`create_ressource` kennt `bild` nicht — das Feld darf nicht als Argument wandern.

    Gegenprobe zur Anforderung: die Liste liefert das Feld, damit die Seite
    die Rueckfrage waehlen kann; wiederherstellen laesst es sich nicht.
    """
    import inspect

    from diakronos_app.api import ressourcen

    parameter = inspect.signature(ressourcen.create_ressource).parameters
    assert "bild" not in parameter


# ── Kalenderverwaltung: `calender_details` ──────────────────────────────────


def test_ux2c_n2_kalenderliste_liefert_calender_details(db, kalender_admin):
    """Ein Kalender aus dem Google-Import traegt seinen Vermerk in der Liste."""
    from diakronos_app.api.kronos import kalender_verwaltung
    from diakronos_app.models.kronos import Kalender

    kalender_verwaltung.create_kalender(titel="Gottesdienste")
    kalender_verwaltung.create_kalender(titel="Eigener")

    db.expire_all()
    doc = db.get(Kalender, "Gottesdienste")
    assert doc is not None
    doc.calender_details = "Importiert aus Google Kalender"
    db.commit()

    liste = kalender_verwaltung.get_kalender_verwaltung()["kalender"]
    importiert = next(k for k in liste if k["name"] == "Gottesdienste")
    eigener = next(k for k in liste if k["name"] == "Eigener")

    # Der Wert, den die Seite fuer `vollstaendig('kalender', …)` liest.
    assert importiert["calender_details"] == "Importiert aus Google Kalender"
    # Kein `null`: die Seite reicht den Wert nur als Text weiter.
    assert eigener["calender_details"] == ""


def test_ux2c_n2_kalender_eintrag_bietet_das_feld_immer(db, kalender_admin):
    """Auch ein frisch angelegter Kalender fuehrt den Schluessel (Form ist stabil)."""
    from diakronos_app.api.kronos import kalender_verwaltung

    kalender_verwaltung.create_kalender(titel="Neu")

    eintrag = next(k for k in kalender_verwaltung.get_kalender_verwaltung()["kalender"]
                   if k["name"] == "Neu")
    assert "calender_details" in eintrag
    assert eintrag["calender_details"] == ""
