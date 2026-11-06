"""ON-6f — root: Planrahmen-Ausschluss wie `get_roles`, einheitliche Wortwahl.

Drei Befunde der Planrahmen-Karte ON-6f, je mit einer Probe:

1. ``planrahmen.rechte.Rechte.ausgeschlossen`` erkannte den Ausschluss nur
   ueber ``Mitglied.user``. ``get_roles`` (die EINE Rechtequelle) prueft
   dagegen seit jeher zusaetzlich die E-Mail OHNE Gross-/Kleinschreibung
   (``benutzer_status.wirksame_konten`` → ``wirksame_konten`` +
   ``normalisiere``). Ein Konto, dessen Mitglied-Zeile (noch) keinen
   ``user``-Link traegt, war damit im Planrahmen NICHT ausgeschlossen,
   obwohl jede andere Rollenpruefung es abwies. Hier wird die Reihenfolge
   aus der Karte festgehalten: **was get_roles sieht, sieht Rechte auch —
   nie schwächer.**

2. Wortwahl in Nutzertexten: „Root-Benutzer“/„Root-Konto“ gibt es in
   Meldungen nicht mehr (ON-6d/ON-6f: „Konto der Hauptverwaltung (root)“,
   Du-Form).

3. ``api_helpers``: der „sperren“-Text kommt NUR, wenn wirklich gesperrt
   wird — nicht bei ``enable`` und nicht bei einem Payload ohne jede
   Wirkung.

Datenbank: ausschliesslich ``patched_db`` (SQLite), kein Betrieb, kein Netz.
"""

from __future__ import annotations

import pytest

ROOT = "root@gemeinde.example"
SYSMGR = "sysmgr@gemeinde.example"
PERSON = "berta@gemeinde.example"
M_ROOT = "M-root"
M_ADMIN = "M-admin"
M_PERSON = "M-berta"


# ── Hilfsmittel ────────────────────────────────────────────────────────────


def _nutzer(sess, name: str, rollen: tuple[str, ...] = ()) -> None:
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=True))
    for idx, rolle in enumerate(rollen, start=1):
        if not sess.query(HasRole).filter_by(parent=name, role=rolle).first():
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User",
                             parentfield="roles", idx=idx, role=rolle))


def _grundstand(patched_db) -> None:
    """root + ein zweiter System Manager + eine gewoehnliche Person."""
    from diakronos_app import root_benutzer
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    _nutzer(sess, ROOT, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, SYSMGR, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, PERSON)
    sess.commit()
    root_benutzer.markiere(sess, ROOT)
    for name, mail, user, vorname in (
        (M_ROOT, ROOT, ROOT, "Mara"),
        (M_ADMIN, SYSMGR, SYSMGR, "Sven"),
        (M_PERSON, PERSON, PERSON, "Berta"),
    ):
        if sess.get(Mitglied, name) is None:
            sess.add(Mitglied(name=name, email=mail, user=user, vorname=vorname,
                              nachname="Test", status="Aktiv"))
    sess.commit()
    sess.close()


def _ausschluss_setzen(patched_db, mitglied: str, *, email: str | None = None,
                       user: str | None = "") -> None:
    """Setzt den Ausschluss direkt auf der Mitglied-Zeile (Altdaten-Zustand)."""
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    zeile = sess.get(Mitglied, mitglied)
    if email is not None:
        zeile.email = email
    if user is not None:
        zeile.user = user or None
    zeile.ausgeschlossen = True
    sess.commit()
    sess.close()


def _rechte(patched_db, benutzer: str):
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.rechte import Rechte

    sess = SessionLocal()
    try:
        return Rechte(sess, benutzer).ausgeschlossen()
    finally:
        sess.close()


def _get_roles(patched_db, benutzer: str):
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.frappe_compat.permissions import get_roles

    benutzer_status.vergiss(benutzer)
    return get_roles(benutzer)


# ── 1. Ausschluss: dieselbe Regel wie get_roles ────────────────────────────


def test_gebundene_zeile_schliesst_aus(patched_db) -> None:
    _grundstand(patched_db)
    assert _rechte(patched_db, PERSON) is False
    _ausschluss_setzen(patched_db, M_PERSON, user=None)  # Link bleibt, Flag neu
    assert _rechte(patched_db, PERSON) is True


def test_email_ohne_kontobindung_schliesst_aus_wie_get_roles(patched_db) -> None:
    """DER BEFUND: `user`-Link fehlt (Bindung entsteht erst beim Anmelden).

    `get_roles` weist das Konto ueber die Adresse ab — der Planrahmen muss
    dieselbe Antwort geben, sonst haette eine ausgeschlossene Person dort
    weiter Planrechte.
    """
    _grundstand(patched_db)
    _ausschluss_setzen(patched_db, M_PERSON, user=None, email=PERSON)
    # Vorbedingung: get_roles sieht den Ausschluss (keine leeren Rollen).
    assert _get_roles(patched_db, PERSON) == (), "get_roles-Vorbedingung verletzt"
    assert _rechte(patched_db, PERSON) is True, (
        "Rechte.ausgeschlossen ist schwächer als get_roles (keine E-Mail-Auflösung)"
    )


def test_email_grossschreibung_ist_egal(patched_db) -> None:
    """„Berta@Gemeinde.Example“ im Mitglied, klein im Konto — dieselbe Person."""
    _grundstand(patched_db)
    _ausschluss_setzen(patched_db, M_PERSON, user=None,
                       email="  Berta@Gemeinde.Example ")
    assert _get_roles(patched_db, PERSON) == (), "get_roles-Vorbedingung verletzt"
    assert _rechte(patched_db, PERSON) is True, (
        "E-Mail-Vergleich ohne Groß-/Kleinschreibung fehlt"
    )


def test_doppelte_zeilen_schliessen_aus_wenn_get_roles_es_tut(
    patched_db, altbestand_dublette,
) -> None:
    """ZWEI Mitglied-Zeilen mit derselben Adresse (Altbestand), nur EINE markiert.

    Die Fixture `altbestand_dublette` nimmt den Eindeutigkeits-Index fuer die
    Dauer des Tests heraus — eine Dublette entsteht heute sonst nicht mehr.
    ``wirksame_konten`` sperrt dann ALLE Konten dieser Adresse („hoechstens zu
    viel, nie zu wenig“); der Planrahmen darf nicht milder sein.
    """
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.models.diakonos import Mitglied

    _grundstand(patched_db)
    sess = patched_db()
    try:
        sess.add(Mitglied(name="M-berta-zweit", email=PERSON, user=None,
                          vorname="Berta", nachname="Zweit", status="Aktiv"))
        sess.flush()
        sess.get(Mitglied, M_PERSON).ausgeschlossen = True
        sess.commit()
    finally:
        sess.close()

    mitglieder, konten = benutzer_status._kontozustand()
    assert PERSON in benutzer_status._ausgeschlossene_konten(mitglieder, konten), (
        "Vorbedingung: die Konto-Auflösung (get_roles) sperrt die Adresse nicht"
    )
    assert _rechte(patched_db, PERSON) is True, (
        "der Planrahmen sieht weniger Ausschluss als get_roles"
    )


def test_andere_adresse_schliesst_nicht_aus(patched_db, altbestand_dublette) -> None:
    """Gegenprobe: die E-Mail-Aufloesung sperrt nicht blind alles."""
    from diakronos_app.frappe_compat import benutzer_status
    from diakronos_app.models.diakonos import Mitglied

    _grundstand(patched_db)
    sess = patched_db()
    try:
        # Berta ist unter FREMDER Adresse ausgeschlossen; ein zweites Mitglied
        # traegt IHRE Adresse, ist aber aktiv. Ihr Konto verliert den
        # `user`-Link — sonst sperrte die Bindung sie (richtig) ueber das
        # Konto, und die Adressauflösung waere gar nicht im Spiel.
        sess.get(Mitglied, M_PERSON).user = None
        sess.get(Mitglied, M_PERSON).email = "jemand.anderes@gemeinde.example"
        sess.get(Mitglied, M_PERSON).ausgeschlossen = True
        sess.add(Mitglied(name="M-berta-zweit", email=PERSON, user=None,
                          vorname="Andere", nachname="Person", status="Aktiv"))
        sess.commit()
    finally:
        sess.close()

    mitglieder, konten = benutzer_status._kontozustand()
    assert PERSON not in benutzer_status._ausgeschlossene_konten(mitglieder, konten), (
        "Vorbedingung: die Konto-Auflösung sperrt eine fremde Adresse"
    )
    assert _rechte(patched_db, PERSON) is False


# ── 2. Wortwahl in Nutzertexten ────────────────────────────────────────────


@pytest.mark.parametrize("datei", [
    "api/datenschutz.py",
    "api/root.py",
    "api/zugang.py",
    "dsgvo_anonymisierung.py",
    "frappe_compat/api_helpers.py",
])
def test_keine_root_benutzer_texte_im_code(datei: str) -> None:
    """„Root-Benutzer“/„Root-Konto“ als ANGEZEIGTER Text ist verboten.

    Kommentare/Programmnamen (ROOT_ROLLE, „Root-Rechte“) bleiben erlaubt —
    geprueft wird jeder String-Literal mit den alten Fachbegriffen.
    """
    import ast
    from pathlib import Path

    import diakronos_app

    pfad = Path(diakronos_app.__file__).parent / datei
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    treffer = [
        knoten.value for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str)
        and ("Root-Benutzer" in knoten.value or "Root-Konto" in knoten.value)
    ]
    assert not treffer, f"{datei}: alte Wortwahl in Meldungen: {treffer}"


def test_planrahmen_meldung_bleibt_geschuetzt_und_du_form() -> None:
    """Die root-Meldung nennt den Grund („geschützt“) und spricht „du“ an."""
    import ast
    from pathlib import Path

    import diakronos_app

    pfad = Path(diakronos_app.__file__).parent / "api" / "zugang.py"
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    texte = [
        knoten.value for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str)
        and knoten.value.startswith("Das Konto der Hauptverwaltung")
    ]
    assert len(texte) >= 5, f"zu wenige root-Meldungen: {len(texte)}"
    for text in texte:
        assert "geschützt" in text, text
        assert "Root-Benutzer" not in text, text
        assert " Sie " not in text, f"Sie-Form statt Du-Form: {text}"


# ── 3. api_helpers: „sperren“ nur beim echten Sperren ──────────────────────


def _root_schreibzugriff(doctype: str, name: str | None, values: dict, *,
                         loeschen: bool = False):
    from diakronos_app.frappe_compat import api_helpers

    return api_helpers._pruefe_root_schreibzugriff(doctype, name, values,
                                                   loeschen=loeschen)


def test_root_sperren_text_nur_beim_sperren(patched_db, fake_redis) -> None:
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.frappe_compat.session import set_user

    _grundstand(patched_db)
    set_user(SYSMGR)
    try:
        with pytest.raises(PermissionError) as fehler:
            _root_schreibzugriff("User", ROOT, {"enabled": 0})
    finally:
        set_user("Administrator")
    assert "sperren" in str(fehler.value)
    assert "Root-Benutzer" not in str(fehler.value)


def test_root_payload_mit_neuem_feld_meldet_angaben(patched_db, fake_redis) -> None:
    """Der Befund: alles ohne eigenes Feld las „…kannst es nicht sperren“.

    Eine ANGABE (auch ein neuer Wert) ist keine Sperre — der Text nennt die
    Angaben. Ein Payload ohne jede Wirkung wird gar nicht abgewiesen.
    """
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.frappe_compat.session import set_user

    _grundstand(patched_db)
    set_user(SYSMGR)
    try:
        _root_schreibzugriff("User", ROOT, {"enabled": 1})   # keine Wirkung
        with pytest.raises(PermissionError) as fehler:
            _root_schreibzugriff("User", ROOT, {"full_name": "Neu"})
    finally:
        set_user("Administrator")
    text = str(fehler.value)
    assert "sperren" not in text, text
    assert "Angaben" in text, text


def test_root_leerer_payload_meldet_nicht_sperren(patched_db, fake_redis) -> None:
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.frappe_compat.session import set_user

    _grundstand(patched_db)
    set_user(SYSMGR)
    try:
        with pytest.raises(PermissionError) as fehler:
            _root_schreibzugriff("User", ROOT, {"full_name": ""})
    finally:
        set_user("Administrator")
    text = str(fehler.value)
    assert "sperren" not in text, text
    assert "Angaben" in text, text


# ── 4. Keine toten Textbausteine mehr ──────────────────────────────────────


def test_konto_text_bausteine_nur_an_einer_stelle() -> None:
    """ON-6f: die Tabelle, die kein Aufrufer las, ist entfernt.

    ``KONTO_FELD_TEXT``/``KONTO_VORGANG_TEXT``/``_text_fuer_konto`` wurden
    von keinem Produktivpfad benutzt (nur der Name existierte). Die
    Vorgangstexte stehen jetzt EINMAL in ``zugang._ROOT_TEXTE``.
    """
    import inspect

    from diakronos_app.api import zugang
    from diakronos_app.frappe_compat import api_helpers

    assert not hasattr(api_helpers, "KONTO_FELD_TEXT")
    assert not hasattr(api_helpers, "KONTO_VORGANG_TEXT")
    assert not hasattr(api_helpers, "_text_fuer_konto")
    assert hasattr(zugang, "_ROOT_TEXTE")
    # Und der Helfer fuer die Feldtexte wird wirklich benutzt.
    quelle = inspect.getsource(api_helpers._pruefe_mitglied_schreibzugriff)
    code = "\n".join(zeile.split("#", 1)[0] for zeile in quelle.splitlines())
    assert "_root_feld(values" in code
    assert "art=root_art" in code
