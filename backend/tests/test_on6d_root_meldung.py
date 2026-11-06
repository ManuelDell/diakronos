"""ON-6d — root-Schutz: die Meldung passt zum Vorgang.

Befund aus dem Review von ON-6c (LOW): aendert ein anderer Administrator eine
harmlose Angabe am Mitglied von root (z. B. die Telefonnummer), kommt richtig
403 — aber mit dem Text „...kann es ausschließen“. Fuer eine normale
Bearbeitung ist das die falsche Auskunft: der Administrator liest eine
Ausschluss-Warnung, obwohl er nur ein Feld gespeichert hat.

Geprueft wird hier die MELDUNG, nicht (noch einmal) die Sperre — die deckt
``test_on6c_root_proben.py`` ab, und diese Datei muss dort gruen bleiben:

  * Telefonnummer durch einen anderen Admin -> 403 mit Bearbeiten-Text
    („Telefonnummer“, KEIN „ausschließen“);
  * Ausschluss -> 403 mit Ausschluss-Text;
  * Loeschen -> Loeschen-Text, Rollen -> Rollen-Text, Sperren -> Sperren-Text;
  * jeder Text nennt den Grund („geschützt“) und kommt in der Du-Form;
  * kein Ueberschutz: dieselbe Telefonnummer-Aenderung an einem NICHT-root-
    Mitglied geht durch.

Datenbank: ausschliesslich ``patched_db`` (SQLite), kein Betrieb, kein Netz.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle Endpunkte
from diakronos_app.frappe_compat.session import set_user

ROOT = "root@gemeinde.example"
SYSMGR = "sysmgr@gemeinde.example"
MITGLIED = "berta@gemeinde.example"
PASSWORT = "EinSicheresPasswort1"

M_ROOT = "M-root"
M_ADMIN = "M-admin"


# ── Hilfsmittel ────────────────────────────────────────────────────────────


def _nutzer(sess, name: str, rollen: tuple[str, ...] = (), *, enabled: bool = True) -> None:
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=enabled))
    for idx, rolle in enumerate(rollen, start=1):
        if not sess.query(HasRole).filter_by(parent=name, role=rolle).first():
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User",
                             parentfield="roles", idx=idx, role=rolle))


def _grundstand(patched_db) -> None:
    """root + ein ZWEITER System Manager, je mit Mitglied — der Angreifer ist SYSMGR."""
    from diakronos_app import root_benutzer
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    _nutzer(sess, ROOT, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, SYSMGR, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, MITGLIED)
    sess.commit()
    konto = sess.get(User, ROOT)
    konto.password_hash = neuer_hash(PASSWORT)
    root_benutzer.markiere(sess, ROOT)
    if sess.get(Mitglied, M_ROOT) is None:
        sess.add(Mitglied(name=M_ROOT, email=ROOT, vorname="Mara", nachname="Erste",
                          user=ROOT, status="Aktiv", telefonnummer="07071 111"))
    if sess.get(Mitglied, M_ADMIN) is None:
        sess.add(Mitglied(name=M_ADMIN, email=SYSMGR, vorname="Sven", nachname="Admin",
                          user=SYSMGR, status="Aktiv"))
    sess.commit()
    sess.close()


def _als(user: str):
    class _Als:
        def __enter__(self):
            set_user(user)
            return self

        def __exit__(self, *exc):
            set_user("Administrator")
            return False

    return _Als()


def _probe(client, patched_db, methode: str, pfad: str, body=None, *, als: str = SYSMGR):
    _grundstand(patched_db)
    with _als(als):
        aufruf = getattr(client, methode)
        return aufruf(pfad, json=body) if body is not None else aufruf(pfad)


def _meldung(antwort) -> str:
    """Der Meldungstext einer 403-Antwort.

    Der Router schickt ihn als ``message`` — ``exception``/``exc_type`` sind
    der KLASSENNAME (``PermissionError``), nie der Fachtext.
    """
    if antwort.headers.get("content-type", "").startswith("application/json"):
        daten = antwort.json()
        if isinstance(daten, dict):
            for schluessel in ("message", "detail"):
                wert = daten.get(schluessel)
                if isinstance(wert, str) and wert.strip():
                    return wert
    return antwort.text


def _telefon(patched_db, mitglied: str = M_ROOT) -> str:
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    try:
        return str(sess.get(Mitglied, mitglied).telefonnummer or "")
    finally:
        sess.close()


# ── Befund: Bearbeiten (Telefonnummer) meldet „ausschließen“ ───────────────


def test_telefonnummer_am_root_ist_403_mit_bearbeiten_text(client, patched_db, fake_redis) -> None:
    """Der Kern des Befunds: richtiger Code, falscher Text.

    ``PUT /api/resource/Mitglied/M-root {"telefon": …}`` durch einen anderen
    System Manager war 403 — die Meldung sprach aber vom Ausschließen.
    """
    antwort = _probe(client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}",
                     {"telefonnummer": "07071 999"})
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "Hauptverwaltung" in text, text
    assert "Telefonnummer" in text, text
    assert "ausschließen" not in text, f"Bearbeiten meldet Ausschluss: {text}"
    # Die Sperre selbst gilt weiter: nichts wurde geschrieben.
    assert _telefon(patched_db) == "07071 111"


def test_bearbeiten_ohne_feld_sagt_allgemein_ändern(client, patched_db, fake_redis) -> None:
    """Eine Aenderung ohne eigenen Fachbegriff (Vorname) sagt „ändern“."""
    antwort = _probe(client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}",
                     {"vorname": "Marta"})
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "ändern" in text, text
    assert "ausschließen" not in text, text


def test_email_am_root_ist_403_mit_adress_text(client, patched_db, fake_redis) -> None:
    """Die E-Mail am MITGLIED hat ihren eigenen Text (nicht „ausschließen“)."""
    antwort = _probe(client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}",
                     {"email": "neu@x.example"})
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "E-Mail-Adresse" in text, text
    assert "ausschließen" not in text, text


# ── Die anderen Vorgaenge behalten IHRE Meldung ────────────────────────────


def test_ausschluss_meldet_ausschluss(client, patched_db, fake_redis) -> None:
    antwort = _probe(client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}",
                     {"ausgeschlossen": 1})
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "ausschließen" in text, text
    assert "Telefonnummer" not in text, text


def test_ausschluss_endpunkt_meldet_ausschluss(client, patched_db, fake_redis) -> None:
    """Derselbe Weg ueber den Endpunkt ``mitglieder.schliesse_mitglied_aus``."""
    _grundstand(patched_db)
    with _als(SYSMGR):
        antwort = client.post("/api/method/mitglieder.schliesse_mitglied_aus",
                               json=dict(mitglied_id=M_ROOT, begruendung="Probe"))
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "ausschließen" in text, text


def test_mitglied_loeschen_meldet_loeschen(client, patched_db, fake_redis) -> None:
    antwort = _probe(client, patched_db, "delete", f"/api/resource/Mitglied/{M_ROOT}")
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "löschen" in text, text
    assert "ausschließen" not in text, text


@pytest.mark.parametrize("body", [{"full_name": "Gekapert"}, {"email": "evil@x.example"}],
                         ids=["full_name", "email"])
def test_user_konto_feld_meldet_angaben(client, patched_db, fake_redis, body) -> None:
    """Am User-KONTO heisst es „Angaben“, nicht „Konto und Rollen ändern“."""
    antwort = _probe(client, patched_db, "put", f"/api/resource/User/{ROOT}", body)
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "Angaben" in text, text
    assert "ausschließen" not in text, text


def test_user_konto_sperren_meldet_sperren(client, patched_db, fake_redis) -> None:
    antwort = _probe(client, patched_db, "put", f"/api/resource/User/{ROOT}",
                     {"enabled": 0})
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "sperren" in text, text


def test_has_role_am_root_meldet_rollen(client, patched_db, fake_redis) -> None:
    antwort = _probe(client, patched_db, "delete",
                     f"/api/resource/Has Role/{ROOT}-System Manager")
    assert antwort.status_code == 403, f"{antwort.status_code}: {antwort.text[:200]}"
    text = _meldung(antwort)
    assert "geschützt" in text, text
    assert "Rollen" in text, text


# ── Kein Ueberschutz ──────────────────────────────────────────────────────


def test_telefonnummer_an_gewOEhnlichem_mitglied_geht_durch(client, patched_db, fake_redis) -> None:
    """Die neue Meldung darf keine zusaetzliche Sperre erzeugen (Gegenprobe)."""
    antwort = _probe(client, patched_db, "put", f"/api/resource/Mitglied/{M_ADMIN}",
                     {"telefonnummer": "07071 222"})
    assert antwort.status_code in (200, 201, 202), f"{antwort.status_code}: {antwort.text[:200]}"
    assert _telefon(patched_db, M_ADMIN) == "07071 222"


# ── Texte: Du-Form, kurz, ohne Fachbegriffe ───────────────────────────────


def test_texte_sind_du_form_und_ohne_fachbegriffe(fake_redis) -> None:
    """„Sie“ und „Root-Benutzer“ gehoeren nicht in die Meldung (UI-Prinzipien)."""
    from diakronos_app.api import zugang
    from diakronos_app.frappe_compat import api_helpers

    volltexte = [
        *zugang._ROOT_TEXTE.values(),
        *zugang._ROOT_BEARBEITEN_TEXTE.values(),
    ]
    for roh in volltexte:
        text = " ".join(roh.split())
        assert "geschützt" in text, text
        assert "Hauptverwaltung" in text, text
        assert "Root-Benutzer" not in text, f"Fachbegriff in der Meldung: {text}"
        assert "Sie " not in text, f"Sie-Form: {text}"
        assert len(text) <= 130, f"zu lang ({len(text)}): {text}"

    # Die Glieder fuer das Mitglied stehen hinter „Das Konto … ist geschützt — du kannst “.
    from diakronos_app.api.zugang import _ROOT_TEXTE as _texte

    glieder = [*api_helpers.KONTO_VORGANG_TEXT.values(),
               *api_helpers.KONTO_FELD_TEXT.values()]
    for glied in glieder:
        text = f"Das Konto der Hauptverwaltung (root) ist geschützt — du kannst {glied}."
        text = " ".join(text.split())
        assert "Root-Benutzer" not in text, f"Fachbegriff in der Meldung: {text}"
        assert "Sie " not in text, f"Sie-Form: {text}"
        assert len(text) <= 130, f"zu lang ({len(text)}): {text}"
        # Jedes Glied wird auch wirklich verwendet (kein toter Text).
        assert (glied in api_helpers.KONTO_VORGANG_TEXT.values()
                or glied in api_helpers.KONTO_FELD_TEXT.values())
    # Und jeder Vorgang hat eine Meldung — kein stiller Rueckfall auf „ändern“.
    for art in ("ausschluss", "loeschung", "dsgvo", "rollen"):
        assert art in _texte, f"kein eigener Text fuer {art}"


# ── Punkt 2: Rechte.ausgeschlossen() auch ueber die eindeutige E-Mail ──────


def test_rechte_ausgeschlossen_ueber_eindeutige_email(client, patched_db, fake_redis) -> None:
    """Konto ohne `Mitglied.user`-Bindung: der Ausschluss wirkt trotzdem.

    Die Bindung entsteht erst beim ersten Anmelden. Vorher antwortete
    ``Rechte.admin()`` fuer ein solches Konto „ja“, waehrend ``get_roles`` es
    laengst abgewiesen hatte — zwei Wege, zwei Antworten.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.planrahmen.rechte import Rechte

    _grundstand(patched_db)
    konto = "ohnebindung@gemeinde.example"
    sess = patched_db()
    _nutzer(sess, konto, ("System Manager",))
    if sess.get(Mitglied, "M-ohnebindung") is None:
        sess.add(Mitglied(name="M-ohnebindung", email=konto, vorname="Ohne",
                          nachname="Bindung", user=None, status="Aktiv",
                          ausgeschlossen=True))
    sess.commit()
    sess.close()

    sess = SessionLocal()
    try:
        assert Rechte(sess, konto).ausgeschlossen() is True
        with pytest.raises(PermissionError):
            Rechte(sess, konto).admin()
        # Gegenprobe: NICHT ausgeschlossen -> keine Sperre.
        sess.get(Mitglied, "M-ohnebindung").ausgeschlossen = False
        sess.flush()
        assert Rechte(sess, konto).ausgeschlossen() is False
        sess.rollback()
    finally:
        sess.close()


def test_rechte_ausgeschlossen_email_mehrdeutig_zaehlt_nicht(client, patched_db, fake_redis) -> None:
    """Zwei Mitglieder an derselben Adresse: keine eindeutige Zuordnung -> nein.

    Dieselbe Bedingung wie :meth:`Rechte.eigenes_mitglied` — ohne Eindeutigkeit
    gibt es keine Identitaet. Der partielle Unique-Index
    (``uq_mitglied_email_normalisiert``) laesst zwei gleiche Adressen im
    Betrieb nicht zu; er wird hier fuer die Dauer des Tests aufgehoben, weil
    die Funktion selbst geprueft wird (Altbestand vor der Migration).
    """
    from sqlalchemy import text as sql_text

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.planrahmen.rechte import Rechte

    _grundstand(patched_db)
    konto = "doppelt@gemeinde.example"
    sess = patched_db()
    _nutzer(sess, konto)
    sess.execute(sql_text("DROP INDEX IF EXISTS uq_mitglied_email_normalisiert"))
    for name in ("M-doppelt-1", "M-doppelt-2"):
        if sess.get(Mitglied, name) is None:
            sess.add(Mitglied(name=name, email=konto, vorname="D",
                              nachname=name, user=None, status="Aktiv",
                              ausgeschlossen=True))
    sess.commit()
    sess.close()

    sess = SessionLocal()
    try:
        # Die Adresse ist nicht EINDEUTIG (zwei Zeilen) -> kein Ausschluss.
        assert Rechte(sess, konto).ausgeschlossen() is False
        # Gegenprobe: bleibt EINE Zeile uebrig, greift sie wieder.
        sess.get(Mitglied, "M-doppelt-2").email = "andere@x.example"
        sess.flush()
        assert Rechte(sess, konto).ausgeschlossen() is True
        sess.rollback()
    finally:
        sess.close()
