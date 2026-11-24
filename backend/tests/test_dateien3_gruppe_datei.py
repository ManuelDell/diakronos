"""DATEIEN-3: Gruppendateien — Datenmodell, Migration und API.

Die Rechte-MATRIX selbst prüft ``test_dateien_r_rechte.py`` (DATEIEN-R) gegen
den Kern; hier wird geprüft, dass die ENDPUNKTE jede Frage an den Kern stellen,
dass Auf- und Abbau der Tabelle stimmen und dass die Fehlerfälle stimmen:

* Liste: angepinnte zuerst, dann neueste; Papierkorb unsichtbar; Kopf mit
  Rechten und Grenze; Untergruppe ist ein eigener Raum (F3).
* Hochladen: Sperrliste (``.sh``/``.exe``), Chat-Größengrenze (F9), kein
  Tageslimit, Waise wird entsorgt, wenn die Zeile scheitert.
* Ausliefern: JEDE Fehlerart dieselbe 404 (unbekannt, kein Recht, Papierkorb,
  Ablage weg) + Kopfzeilen (nosniff, attachment/inline).
* Papierkorb + Wiederherstellen (MODERIEREN) + Unbenennen (SCHREIBEN).
* Schalter: gesperrtes Hochladen/Anpinnen wirkt sofort; Durchreiche an den Kern.
* Modul aus = die normale Rechte-Meldung.
* Gruppenschalter umstellen nur über die Durchreiche (kein eigener Weg).

Stil wie ``test_chat12a_anhang.py``: direkte Aufrufe der Endpunktfunktionen
(``session.set_user``-Naht aus ``conftest``) — ohne HTTP.
"""

from __future__ import annotations

import importlib
import io
import struct
import zlib
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

ADMIN = "admin@x.org"
HV = "hv@x.org"
MV = "mv@x.org"
GL = "gl@x.org"
SAENGER = "saenger@x.org"   # Mitglied Chor (nicht in der Untergruppe)
NOTEN = "noten@x.org"       # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"       # Gemeindemitglied ohne Gruppe
JUGEND_HV = "jhv@x.org"     # HV einer Gruppe OHNE Dateien-Modul


def _set(konto: str) -> None:
    _session_mod.set_user(konto)


# ── Testdaten ───────────────────────────────────────────────────────────────


def _png(breite: int = 2, hoehe: int = 2) -> bytes:
    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (struct.pack("!I", len(daten)) + typ + daten
                + struct.pack("!I", zlib.crc32(typ + daten) & 0xFFFFFFFF))

    ihdr = struct.pack("!IIBBBBB", breite, hoehe, 8, 2, 0, 0, 0)
    roh = b"".join(b"\x00" + b"\xff\x00\x00" * breite for _ in range(hoehe))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(roh)) + chunk(b"IEND", b""))


PNG = _png()
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
TXT = b"Protokoll der Chorprobe\nAlle anwesend.\n"
SH = b"#!/bin/sh\necho hallo\n"
#: Ein ECHTES PE/COFF (``MZ``-Kopf, ``e_lfanew`` -> ``PE\\0\\0``). Der bloße
#: ``MZ``-Kopf ist nur ein Textanfang (Review R1/KANN 4 in ``ablage``).
EXE = (b"MZ" + b"\x00" * 0x3A + struct.pack("<I", 0x80)).ljust(0x80, b"\x00") \
    + b"PE\x00\x00" + b"\x00" * 60


class _Upload:
    """``UploadFile``-artig: ``.read``/``.file``/``.filename``/``.content_type``."""

    def __init__(self, daten: bytes, filename: str, content_type: str = "") -> None:
        self.file = io.BytesIO(daten)
        self.filename = filename
        self.content_type = content_type

    def read(self, *args):  # pragma: no cover — der Endpunkt liest ``.file``
        return self.file.read(*args)


# ── Welt und Ablage ─────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Chor (Dateien AN) mit Untergruppe Notenausschuss; Jugend OHNE Dateien."""
    s = patched_db()
    for konto, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (GL, "Gl"),
                        (SAENGER, "Sa"), (NOTEN, "No"), (FREMD, "Fr"), (JUGEND_HV, "Jh")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=konto, user=konto))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User", role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Notenausschuss", gruppe="Chor"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Sa"))
    s.add(Gruppenmitgliedschaft(name="gm2", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Mv"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-Noten",
                                     parentfield="mitglieder", mitglied="M-No"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer=GL, rolle="GL"),
        RechteGruppenrolle(gruppe="Jugend", benutzer=JUGEND_HV, rolle="HV"),
        RechteModul(gruppe="Chor", modul="dateien"),
        RechteModul(gruppe="Jugend", modul="chat"),
    ])
    s.commit()
    yield s
    s.close()
    _session_mod.reset_user()


@pytest.fixture()
def ablage(tmp_path):
    """Die Ablage NUR für diesen Test auf ein ``tmp_path`` stellen (kein Netz)."""
    from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher

    ordner = tmp_path / "files"
    ordner.mkdir()
    speicher = Lokal(ordner)
    setze_speicher(speicher)
    try:
        yield speicher
    finally:
        vergiss_speicher()


def _hochladen(konto: str, daten: bytes = PNG, filename: str = "foto.png",
               *g: str | None, **kw) -> dict:
    from diakronos_app.api import dateien as D

    _set(konto)
    return D.hochladen(*g, datei=_Upload(daten, filename), **kw)


def _db() -> tuple:
    """(Modul ``db``, Modell) — das Modul trägt die GEPATCHTE Test-Factory."""
    from diakronos_app import db as dbmod
    from diakronos_app.models.dateien import GruppeDatei

    return dbmod, GruppeDatei


def _zeilen() -> list:
    dbmod, GruppeDatei = _db()
    with dbmod.SessionLocal() as s:
        return s.query(GruppeDatei).order_by(GruppeDatei.name).all()


# ── 1) Modell und Migration ─────────────────────────────────────────────────


def test_modelle_sind_exportiert_und_haben_die_konzeptspalten():
    from diakronos_app.models import GruppeDatei, GruppeDateiEntsorgung

    assert {"name", "gruppe", "untergruppe", "schluessel", "dateiname", "mime",
            "groesse", "angelegt_am", "angelegt_von", "angepinnt", "angepinnt_am",
            "angepinnt_von", "geloescht_am", "geloescht_von"} <= set(
        GruppeDatei.__table__.columns.keys())
    assert GruppeDatei.__table__.c.name.primary_key
    assert {"schluessel", "versuche", "naechster_versuch_am", "belegt_bis",
            "angelegt_am"} == set(GruppeDateiEntsorgung.__table__.columns.keys())
    assert GruppeDateiEntsorgung.__table__.c.schluessel.primary_key
    # F9: KEINE Hochlade-Marken-Tabelle (kein Tageslimit).
    from diakronos_app.models.base import Base

    assert "gruppe_datei_hochladung" not in Base.metadata.tables


def test_modell_indizes_stehen():
    from diakronos_app.models.dateien import GruppeDatei, GruppeDateiEntsorgung

    indizes = {i.name for i in GruppeDatei.__table__.indexes}
    assert {"ix_gruppe_datei_raum", "ix_gruppe_datei_angepinnt"} <= indizes
    entsorgung = {i.name for i in GruppeDateiEntsorgung.__table__.indexes}
    assert {"ix_gruppe_datei_entsorgung_am",
            "ix_gruppe_datei_entsorgung_naechster"} <= entsorgung


def test_migration_haengt_an_dateien_r_und_es_gibt_genau_einen_kopf():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    skripte = ScriptDirectory.from_config(cfg)
    rev = skripte.get_revision("dateien3_gruppe_datei")
    assert rev is not None
    assert rev.down_revision == "dateien_r_gruppeneinstellung", rev.down_revision
    assert "Revises: dateien_r_gruppeneinstellung" in Path(rev.path).read_text(encoding="utf-8")
    heads = skripte.get_heads()
    assert list(heads) == ["dateien3_gruppe_datei"], heads
    assert len(heads) == 1


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine MIT allen Modelltabellen — die neuen Tabellen fehlen."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    with eng.begin() as verbindung:
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "gruppe_datei"')
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "gruppe_datei_entsorgung"')
    yield eng
    eng.dispose()


def _migration():
    import importlib.util

    pfad = BACKEND / "alembic" / "versions" / "dateien3_gruppe_datei.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("dateien3_gruppe_datei", pfad))
    modul.__spec__.loader.exec_module(modul)
    return modul


def test_migration_upgrade_downgrade_upgrade(fresh_engine):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    modul = _migration()
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.upgrade()  # idempotent
        insp = inspect(verbindung)
        assert insp.has_table("gruppe_datei")
        assert insp.has_table("gruppe_datei_entsorgung")
        assert insp.get_pk_constraint("gruppe_datei")["constrained_columns"] == ["name"]
        namen = {i["name"] for i in insp.get_indexes("gruppe_datei")}
        assert {"ix_gruppe_datei_raum", "ix_gruppe_datei_angepinnt"} <= namen
        ziele = {fk["referred_table"] for fk in insp.get_foreign_keys("gruppe_datei")}
        assert ziele == {"user"}
        entsorgung = {i["name"] for i in insp.get_indexes("gruppe_datei_entsorgung")}
        assert {"ix_gruppe_datei_entsorgung_am",
                "ix_gruppe_datei_entsorgung_naechster"} <= entsorgung

    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
        insp = inspect(verbindung)
        assert not insp.has_table("gruppe_datei")
        assert not insp.has_table("gruppe_datei_entsorgung")
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
        assert inspect(verbindung).has_table("gruppe_datei")


def test_migration_downgrade_auf_leerer_datenbank_ist_folgenlos(fresh_engine):
    """Idempotent auch rückwärts: zweimal ``downgrade`` wirft nicht."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    modul = _migration()
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
            modul.downgrade()


# ── 2) Liste ────────────────────────────────────────────────────────────────


def test_liste_leer_mit_kopf(welt):
    from diakronos_app.api import dateien as D

    _set(SAENGER)
    antwort = D.liste("Chor")
    assert antwort["dateien"] == [] and antwort["anzahl"] == 0
    # Mitglied: hochladen ja, anpinnen nein (Vorgabe), Grenze wie im Chat.
    from diakronos_app.chat_anhanggrenze import anhang_max_bytes

    assert antwort["darf_hochladen"] is True
    assert antwort["darf_anpinnen"] is False
    dbmod, _ = _db()
    with dbmod.SessionLocal() as s:
        assert antwort["max_bytes"] == int(anhang_max_bytes(s))


def test_liste_angepinnte_zuerst_dann_neueste(welt, ablage):
    from diakronos_app.api import dateien as D

    a = _hochladen(SAENGER, PNG, "a.png", "Chor")
    b = _hochladen(SAENGER, PDF, "b.pdf", "Chor")
    c = _hochladen(SAENGER, TXT, "c.txt", "Chor")
    _set(HV)
    D.anpinnen(c["name"], True)

    _set(SAENGER)
    dateien = D.liste("Chor")["dateien"]
    assert [e["name"] for e in dateien] == [c["name"], b["name"], a["name"]]
    assert dateien[0]["angepinnt"] is True
    assert [e["name"] for e in dateien[1:]] == [b["name"], a["name"]]
    # Je Eintrag die Rechte des Aufrufers: eigene Datei bearbeitbar, fremdes
    # Anpinnen nicht (Mitglied ohne Schalter).
    assert dateien[0]["darf_bearbeiten"] is True
    assert dateien[0]["darf_anpinnen"] is False
    assert dateien[0]["eigene"] is True
    # Kein technischer Schlüssel in der Antwort.
    assert "schluessel" not in dateien[0]


def test_liste_zeigt_fremde_rechte_und_papierkorb_nicht(welt, ablage):
    from diakronos_app.api import dateien as D

    eig = _hochladen(SAENGER, PNG, "a.png", "Chor")
    fremd = _hochladen(HV, PDF, "b.pdf", "Chor")
    _set(HV)
    assert D.liste("Chor")["dateien"][0]["darf_bearbeiten"] is True  # Leitung
    D.loeschen(eig["name"])
    _set(SAENGER)
    namen = [e["name"] for e in D.liste("Chor")["dateien"]]
    assert eig["name"] not in namen and fremd["name"] in namen
    # Eigenes Anpinnen ist auch für ein Mitglied gesperrt, sein Papierkorb
    # liegt im Papierkorb-Endpunkt (MODERIEREN), nicht in der Liste.
    assert D.liste("Chor")["darf_anpinnen"] is False


def test_untergruppe_ist_ein_eigener_raum(welt, ablage):
    from diakronos_app.api import dateien as D

    haupt = _hochladen(SAENGER, PNG, "a.png", "Chor")
    ug = _hochladen(GL, PDF, "noten.pdf", "Chor", untergruppe="UG-Noten")
    _set(SAENGER)
    assert [e["name"] for e in D.liste("Chor")["dateien"]] == [haupt["name"]]
    # F3: Chor-Mitglied ohne Untergruppe sieht die Datei der Untergruppe nicht.
    from diakronos_app.frappe_compat.exceptions import PermissionError

    with pytest.raises(PermissionError):
        D.liste("Chor", untergruppe="UG-Noten")
    _set(NOTEN)
    assert [e["name"] for e in D.liste("Chor", untergruppe="UG-Noten")["dateien"]] == [ug["name"]]


def test_fremde_gruppe_sieht_nichts(welt):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set(FREMD)
    with pytest.raises(PermissionError):
        D.liste("Chor")


def test_modul_aus_normale_rechte_meldung(welt):
    """Jugend hat kein Dateien-Modul: der Kern sagt NEIN — normaler Fehler."""
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set(JUGEND_HV)
    with pytest.raises(PermissionError) as fehler:
        D.liste("Jugend")
    assert "Berechtigung" in str(fehler.value)
    with pytest.raises(PermissionError):
        D.hochladen("Jugend", datei=_Upload(PNG, "x.png"))


# ── 3) Hochladen ────────────────────────────────────────────────────────────


def test_hochladen_legt_datei_und_zeile_an(welt, ablage):
    antwort = _hochladen(SAENGER, PDF, "protokoll.pdf", "Chor")
    assert antwort["success"] is True
    assert antwort["name"].startswith("gdatei-")
    assert antwort["dateiname"] == "protokoll.pdf"
    assert antwort["mime"] == "application/pdf"
    assert antwort["groesse"] == len(PDF)
    zeilen = _zeilen()
    assert len(zeilen) == 1
    assert zeilen[0].gruppe == "Chor" and zeilen[0].untergruppe is None
    assert zeilen[0].angelegt_von == SAENGER
    assert zeilen[0].angepinnt is False
    assert zeilen[0].geloescht_am is None
    assert ablage.existiert(zeilen[0].schluessel)


def test_hochladen_sperrliste_endungen(welt, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    for name in ("skript.sh", "programm.exe", "bericht.pdf.exe", "seite.html"):
        with pytest.raises(ValidationError):
            _hochladen(SAENGER, TXT, name, "Chor")
    assert _zeilen() == []


def test_hochladen_sperrliste_inhalt_getarnt(welt, ablage):
    """Ein Shebang/ELF als ``.txt`` fällt über den INHALT durch (F8)."""
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        _hochladen(SAENGER, SH, "notizen.txt", "Chor")
    with pytest.raises(ValidationError):
        _hochladen(SAENGER, EXE, "brief.txt", "Chor")


def test_hochladen_grenze_ist_die_chat_grenze(welt, ablage, monkeypatch):
    """F9: dieselbe Grenze wie im Chat — und die Meldung nennt sie."""
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import ValidationError

    monkeypatch.setattr(D, "anhang_max_bytes", lambda *a, **kw: 100)
    with pytest.raises(ValidationError) as fehler:
        _hochladen(SAENGER, b"x" * 101, "zu-gross.txt", "Chor")
    assert "zu groß" in str(fehler.value)
    assert _zeilen() == []
    # Genau an der Grenze ist erlaubt.
    antwort = _hochladen(SAENGER, b"y" * 100, "genau.txt", "Chor")
    assert antwort["groesse"] == 100


def test_hochladen_ohne_tageslimit(welt, ablage):
    """F9: KEIN Tageslimit — die 21. Datei geht durch (Chat hätte gestoppt)."""
    from diakronos_app.models.chat import ANHAENGE_PRO_TAG

    for i in range(ANHAENGE_PRO_TAG + 1):
        _hochladen(SAENGER, TXT, f"notiz-{i}.txt", "Chor")
    assert len(_zeilen()) == ANHAENGE_PRO_TAG + 1


def test_hochladen_schalter_aus_verweigert(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.rechte import verwaltung

    verwaltung.setze_gruppeneinstellung(HV, "Chor", "dateien_hochladen_alle", False)
    _set(SAENGER)
    with pytest.raises(PermissionError):
        D.hochladen("Chor", datei=_Upload(PNG, "x.png"))
    assert _zeilen() == []
    # Die Leitung darf weiter.
    _hochladen(HV, PNG, "y.png", "Chor")
    assert len(_zeilen()) == 1


def test_hochladen_untergruppe_wird_der_untergruppe_zugeordnet(welt, ablage):
    antwort = _hochladen(NOTEN, TXT, "noten.txt", "Chor", untergruppe="UG-Noten")
    zeile = _zeilen()[0]
    assert zeile.untergruppe == "UG-Noten"
    assert zeile.gruppe == "Chor"
    assert antwort["untergruppe"] == "UG-Noten"


def test_hochladen_legt_kein_rechteobjekt_je_datei_an(welt, ablage):
    """Review R1/3: kein ``RechteObjekt`` je Datei.

    Der Kern geht für ``gruppe_datei`` direkt in ``_darf_raum`` und fragt nie
    nach einem Eintrag — ein Eintrag je Datei würde nur Waisen hinterlassen
    (er fiele auch nie mit der Datei).
    """
    from diakronos_app.models.rechte import RechteObjekt

    dbmod, _ = _db()
    antwort = _hochladen(SAENGER, PNG, "a.png", "Chor")
    with dbmod.SessionLocal() as s:
        assert s.query(RechteObjekt).filter_by(typ="gruppe_datei",
                                               objekt=antwort["name"]).count() == 0


class _ZeilenAttrappe:
    """Steht statt ``GruppeDatei`` im Endpunkt und lässt das Schreiben scheitern.

    Ein ``s.add(<Attrappe>)`` lässt SQLAlchemy erst beim ``flush`` auflaufen —
    deshalb wirft die Attrappe dort. KEINE zweite Modell-Klasse: sie bliebe in
    der Metadaten-Registry hängen (``patched_db`` fällt nach jedem Test alle
    Tabellen, eine gleichnamige Waise bräche die folgenden Tests).
    """

    def __init__(self, **felder):
        self.felder = felder


@pytest.fixture()
def zeile_scheitert(monkeypatch):
    """Das Schreiben der ZEILE scheitert (``s.add``/``flush`` werfen).

    Gepatcht werden nur die beiden Schreib-Sitzungen des Endpunkts (``begin``);
    alle LESENDEN Fragen (Rechte, Grenze) laufen unverändert auf der
    Test-Engine.
    """
    from diakronos_app.api import dateien as D

    monkeypatch.setattr(D, "GruppeDatei", _ZeilenAttrappe)
    echte = D.dbmod.SessionLocal

    class Schreibsitzung:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            raise RuntimeError("Zeile kaputt")

        def __exit__(self, *a):
            return False

    class Beginner:
        def __call__(self, *a, **kw):
            return echte(*a, **kw)

        def begin(self):
            return Schreibsitzung()

    monkeypatch.setattr(D.dbmod, "SessionLocal", Beginner())
    yield D


def test_hochladen_entsorgt_die_datei_wenn_die_zeile_scheitert(welt, ablage, zeile_scheitert):
    """Review-Muster von CHAT-12a: keine Waise in der Ablage."""
    D = zeile_scheitert
    dbmod, GruppeDatei = _db()
    from diakronos_app.models.dateien import GruppeDateiEntsorgung

    _set(SAENGER)
    with pytest.raises(RuntimeError):
        D.hochladen("Chor", datei=_Upload(PNG, "a.png"))
    # Datei weg (Sofort-Versuch), Zeile nie entstanden, Auftrag wieder weg.
    assert ablage.auflisten("") == []
    with dbmod.SessionLocal() as s:
        assert s.query(GruppeDatei).count() == 0
        assert s.query(GruppeDateiEntsorgung).count() == 0


def test_hochladen_abgelehnter_typ_legt_nichts_an(welt, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        _hochladen(SAENGER, b"", "leer.txt", "Chor")
    assert _zeilen() == []
    assert ablage.auflisten("") == []


# ── 4) Ausliefern: dieselbe 404 für alle Fehlerarten ────────────────────────


def _inhalt(antwort) -> bytes:
    return b"".join(antwort.body_iterator if hasattr(antwort, "body_iterator")
                    else [antwort.body])


def test_ausliefern_mit_kopfzeilen(welt, ablage):
    from diakronos_app.api import dateien as D

    antwort = _hochladen(SAENGER, PDF, "protokoll.pdf", "Chor")
    _set(SAENGER)
    auslieferung = D.datei(antwort["name"])
    assert auslieferung.status_code == 200
    assert auslieferung.media_type == "application/pdf"
    assert auslieferung.headers["X-Content-Type-Options"] == "nosniff"
    assert auslieferung.headers["Content-Disposition"].startswith("attachment;")
    assert auslieferung.headers["Content-Length"] == str(len(PDF))

    # Bilder gehen inline ausgeliefert.
    bild = _hochladen(SAENGER, PNG, "foto.png", "Chor")
    kopf = D.datei(bild["name"]).headers
    assert kopf["Content-Disposition"].startswith("inline;")


def test_ausliefern_404_fuer_jede_fehlerart(welt, ablage):
    """Unbekannt, kein Recht, Papierkorb, Ablage weg — IMMER dieselbe 404."""
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    d = _hochladen(SAENGER, PDF, "protokoll.pdf", "Chor")

    _set(SAENGER)
    with pytest.raises(DoesNotExistError) as unbekannt:
        D.datei("gdatei-gibtesnicht")
    _set(FREMD)
    with pytest.raises(DoesNotExistError) as fremd:
        D.datei(d["name"])
    _set(HV)
    D.loeschen(d["name"])
    _set(SAENGER)
    with pytest.raises(DoesNotExistError) as papierkorb:
        D.datei(d["name"])

    texte = {str(e.value) for e in (unbekannt, fremd, papierkorb)}
    assert texte == {D.NICHT_GEFUNDEN}

    # Ablage weg: die Zeile steht, das Objekt fehlt.
    e = _hochladen(SAENGER, PDF, "weg.pdf", "Chor")
    zeile = [z for z in _zeilen() if z.name == e["name"]][0]
    ablage.loeschen(zeile.schluessel)
    _set(SAENGER)
    with pytest.raises(DoesNotExistError) as weg:
        D.datei(e["name"])
    assert str(weg.value) == D.NICHT_GEFUNDEN


def test_ausliefern_untergruppe_nur_fuer_ihre_mitglieder(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    ug = _hochladen(GL, PDF, "noten.pdf", "Chor", untergruppe="UG-Noten")
    _set(SAENGER)
    with pytest.raises(DoesNotExistError):
        D.datei(ug["name"])
    _set(NOTEN)
    assert D.datei(ug["name"]).status_code == 200
    _set(HV)
    assert D.datei(ug["name"]).status_code == 200


def test_ausliefern_modul_aus_ist_dieselbe_404(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    # Modul ausschalten: Zeile entfernen (der Kern liest ``rechte_modul``).
    from diakronos_app.models.rechte import RechteModul

    dbmod, _ = _db()

    with dbmod.SessionLocal.begin() as s:
        s.query(RechteModul).filter_by(gruppe="Chor", modul="dateien").delete()
    _set(SAENGER)
    with pytest.raises(DoesNotExistError):
        D.datei(d["name"])


# ── 5) Papierkorb, Wiederherstellen, Umbenennen ─────────────────────────────


def test_loeschen_ist_papierkorb(welt, ablage):
    from diakronos_app.api import dateien as D

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(SAENGER)
    antwort = D.loeschen(d["name"])
    assert antwort["geloescht_am"]
    zeile = _zeilen()[0]
    assert zeile.geloescht_am is not None and zeile.geloescht_von == SAENGER
    # Zeile UND Datei bleiben (F5: endgültig erst der Job aus DATEIEN-5).
    assert ablage.existiert(zeile.schluessel)
    # Zweites Löschen ist dieselbe 404 (schon im Papierkorb).
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    with pytest.raises(DoesNotExistError):
        D.loeschen(d["name"])


def test_fremde_datei_loeschen_nur_leitung(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(NOTEN)   # Untergruppen-Mitglied der Hauptgruppe, aber keine Leitung
    with pytest.raises(PermissionError):
        D.loeschen(d["name"])
    # HV, MV und der Administrator dürfen fremde Dateien löschen (F4).
    for konto in (HV, MV, ADMIN):
        _set(konto)
        D.loeschen(d["name"])
        assert _zeilen()[0].geloescht_von == konto
        D.wiederherstellen(d["name"])


def test_wiederherstellen_ist_moderieren(welt, ablage):
    """F5: Wiederherstellen ist MODERIEREN — aber nur an einer Papierkorb-Zeile.

    Ein Mitglied SIEHT die geloeschte Zeile nicht (Sichtbarkeit im Papierkorb =
    MODERIEREN, Review R1/2) und bekommt deshalb dieselbe 404 wie fuer eine
    unbekannte Kennung — es erfaehrt nicht, dass die Datei im Papierkorb liegt.
    """
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError, PermissionError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(SAENGER)
    D.loeschen(d["name"])
    with pytest.raises(DoesNotExistError):
        D.wiederherstellen(d["name"])
    _set(HV)
    assert D.wiederherstellen(d["name"])["wiederhergestellt"] is True
    assert _zeilen()[0].geloescht_am is None and _zeilen()[0].geloescht_von is None
    _set(SAENGER)
    assert [e["name"] for e in D.liste("Chor")["dateien"]] == [d["name"]]
    # Nicht mehr im Papierkorb: jetzt ist es eine RECHTE-Frage (403), keine 404.
    _set(SAENGER)
    with pytest.raises(PermissionError):
        D.wiederherstellen(d["name"])


def test_papierkorb_liste_nur_fuer_leitung(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    e = _hochladen(SAENGER, PNG, "b.png", "Chor")
    _set(SAENGER)
    D.loeschen(d["name"])
    with pytest.raises(PermissionError):
        D.papierkorb("Chor")
    _set(HV)
    liste = D.papierkorb("Chor")
    assert liste["aufbewahrung_tage"] == 30
    assert [x["name"] for x in liste["dateien"]] == [d["name"]]
    assert liste["dateien"][0]["geloescht_von"] == SAENGER
    assert liste["dateien"][0]["loeschbar_ab"]
    assert e["name"] not in [x["name"] for x in liste["dateien"]]


def test_umbenennen_nur_eigene_oder_leitung(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError

    d = _hochladen(SAENGER, PDF, "alt.pdf", "Chor")
    _set(SAENGER)
    assert D.umbenennen(d["name"], "neu.pdf")["dateiname"] == "neu.pdf"
    # Pfadanteile und Steuerzeichen fliegen raus, die Sperrliste gilt auch hier.
    assert D.umbenennen(d["name"], "../../etc/passwd")["dateiname"] == "passwd"
    with pytest.raises(ValidationError):
        D.umbenennen(d["name"], "boese.exe")
    _set(NOTEN)
    with pytest.raises(PermissionError):
        D.umbenennen(d["name"], "fremd.pdf")
    _set(HV)
    assert D.umbenennen(d["name"], "von-der-leitung.pdf")["dateiname"] == "von-der-leitung.pdf"


def test_umbenennen_im_papierkorb_ist_404(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(SAENGER)
    D.loeschen(d["name"])
    with pytest.raises(DoesNotExistError):
        D.umbenennen(d["name"], "neu.png")


# ── 6) Anpinnen ─────────────────────────────────────────────────────────────


def test_anpinnen_nur_mit_recht(welt, ablage):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.rechte import verwaltung

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(SAENGER)
    with pytest.raises(PermissionError):
        D.anpinnen(d["name"], True)
    _set(HV)
    assert D.anpinnen(d["name"], True)["angepinnt"] is True
    zeile = _zeilen()[0]
    assert zeile.angepinnt is True and zeile.angepinnt_von == HV
    assert zeile.angepinnt_am is not None
    # Schalter „alle dürfen anpinnen“ öffnet es für Mitglieder.
    verwaltung.setze_gruppeneinstellung(HV, "Chor", "dateien_anpinnen_alle", True)
    _set(SAENGER)
    assert D.anpinnen(d["name"], False)["angepinnt"] is False
    assert _zeilen()[0].angepinnt_am is None and _zeilen()[0].angepinnt_von is None


# ── 7) Einstellungen: reine Durchreiche ─────────────────────────────────────


def test_einstellungen_und_setzen_sind_durchreiche(welt):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.rechte import kern

    _set(SAENGER)
    assert D.einstellungen("Chor") == {
        "werte": {"dateien_hochladen_alle": True, "dateien_anpinnen_alle": False},
        "darf_aendern": False,
    }
    with pytest.raises(PermissionError):
        D.einstellung_setzen("Chor", "dateien_anpinnen_alle", True)
    _set(HV)
    D.einstellung_setzen("Chor", "dateien_anpinnen_alle", True)
    assert kern.gruppeneinstellung("Chor", "dateien_anpinnen_alle") is True
    assert D.einstellungen("Chor")["darf_aendern"] is True


def test_unbekannte_einstellung_wird_abgewiesen(welt):
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set(HV)
    with pytest.raises(ValidationError):
        D.einstellung_setzen("Chor", "gibt_es_nicht", True)


# ── 8) DSGVO-Inventar ───────────────────────────────────────────────────────


def test_dsgvo_inventar_nennt_beide_tabellen():
    from diakronos_app import dsgvo_anonymisierung as A

    for spalte in ("angelegt_von", "angepinnt_von", "geloescht_von"):
        assert A.SPALTEN["gruppe_datei"][spalte][0] == "user_null"
    assert A.SPALTEN["gruppe_datei"]["dateiname"][0] == "protokoll"
    # Die Datei gehört der Gruppe: die Zeile wird NICHT gelöscht.
    assert "gruppe_datei" not in {name for name, _ in A.ZEILEN_LOESCHEN}
    assert "gruppe_datei" not in A.KONTO_ZEILEN
    # Die Entsorgungsliste trägt keine Personendaten — wie beim Chat.
    assert A.SPALTEN["gruppe_datei_entsorgung"]["schluessel"][0] == "struktur"
    assert "gruppe_datei_entsorgung" not in {name for name, _ in A.ZEILEN_LOESCHEN}


# ── 9) Review R1: Datei ohne Besitzer ───────────────────────────────────────

def _angelegt_von_nullen(name: str) -> None:
    """``angelegt_von`` auf NULL setzen — Konto gelöscht/anonymisiert."""
    from sqlalchemy import update

    from diakronos_app.models.dateien import GruppeDatei

    dbmod, _ = _db()
    with dbmod.SessionLocal.begin() as s:
        s.execute(update(GruppeDatei).where(GruppeDatei.name == name)
                  .values(angelegt_von=None))


def test_datei_ohne_besitzer_gehoert_niemandem_mehr(welt, ablage):
    """Review R1/1: ``angelegt_von IS NULL`` ist KEIN Ersatzname.

    Die Datei gehört dann niemandem mehr: der Kern liest ``None`` als „fremd“ —
    Leitung darf umbenennen und löschen, ein einfaches Mitglied nicht. Weder
    die Liste (``darf_bearbeiten``) noch die Endpunkte dürfen die Ersatz-Kennung
    als Besitzer ausgeben.
    """
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError

    d = _hochladen(SAENGER, PDF, "alt.pdf", "Chor")
    _angelegt_von_nullen(d["name"])
    assert _zeilen()[0].angelegt_von is None

    # Die Liste nennt niemanden als Eigentümer und sagt: Mitglied NEIN.
    _set(SAENGER)
    eintrag = [e for e in D.liste("Chor")["dateien"] if e["name"] == d["name"]][0]
    assert eintrag["angelegt_von"] == "" and eintrag["eigene"] is False
    assert eintrag["darf_bearbeiten"] is False

    # Ein einfaches Mitglied darf nicht — normale Rechte-Meldung (403).
    with pytest.raises(PermissionError):
        D.umbenennen(d["name"], "meins.pdf")
    with pytest.raises(PermissionError):
        D.loeschen(d["name"])

    # Die Leitung darf weiter (Datei bleibt pflegbar).
    _set(HV)
    assert [e for e in D.liste("Chor")["dateien"] if e["name"] == d["name"]][0][
        "darf_bearbeiten"] is True
    assert D.umbenennen(d["name"], "leitung.pdf")["dateiname"] == "leitung.pdf"
    D.loeschen(d["name"])
    assert _zeilen()[0].geloescht_am is not None


# ── 10) Review R1: einheitliche 404 an den Aktions-Endpunkten ──────────────

def test_aktionsendpunkte_sind_fuer_fremde_unsichtbar(welt, ablage):
    """Review R1/2: ohne Mitgliedschaft DIESELBE 404 wie für eine erfundene Kennung.

    Geprüft für alle vier Endpunkte, je in beiden Lagen (Datei sichtbar bzw.
    im Papierkorb) — und die Antwort ist textgleich mit der einer unbekannten
    Kennung, damit nichts über die Existenz verraten wird.
    """
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    e = _hochladen(SAENGER, PNG, "b.png", "Chor")
    _set(SAENGER)
    D.loeschen(e["name"])          # e liegt im Papierkorb

    _set(FREMD)
    with pytest.raises(DoesNotExistError) as erfunden:
        D.anpinnen("gdatei-gibtesnicht", True)
    assert str(erfunden.value) == D.NICHT_GEFUNDEN

    faelle = [
        ("anpinnen", lambda name: D.anpinnen(name, True)),
        ("umbenennen", lambda name: D.umbenennen(name, "neu.png")),
        ("loeschen", lambda name: D.loeschen(name)),
        ("wiederherstellen", lambda name: D.wiederherstellen(name)),
    ]
    for bezeichnung, ruf in faelle:
        for ziel in (d["name"], e["name"]):
            with pytest.raises(DoesNotExistError) as fehler:
                ruf(ziel)
            assert str(fehler.value) == D.NICHT_GEFUNDEN, (bezeichnung, ziel)

    # Der Fremde hat auch nichts verändert.
    zeilen = {z.name: z for z in _zeilen()}
    assert zeilen[d["name"]].dateiname == "a.png"
    assert zeilen[e["name"]].geloescht_am is not None


def test_wiederherstellen_nicht_geloescht_ist_rechte_frage(welt, ablage):
    """Review R1/2, Abgrenzung: sichtbar + nicht im Papierkorb = 403, nicht 404.

    Das Mitglied SIEHT die Datei — „wiederherstellen“ ist dann eine
    Rechte-Frage (MODERIEREN), keine Sache der Sichtbarkeit.
    """
    from diakronos_app.api import dateien as D
    from diakronos_app.frappe_compat.exceptions import PermissionError

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(SAENGER)
    with pytest.raises(PermissionError):
        D.wiederherstellen(d["name"])


# ── 11) Review R1: Gruppe endgültig löschen räumt die Dateien mit ──────────

def test_endgueltig_gruppe_entfernt_auch_die_dateien(welt, ablage):
    """Review R1/7a: Zeilen weg, Entsorgungsaufträge stehen, andere Gruppe bleibt.

    Die Aufträge entstehen in DERSELBEN Transaktion (Zeile ODER Auftrag — nie
    ein Verweis ins Leere); die Datei selbst löscht der Job aus DATEIEN-5.
    """
    from diakronos_app import papierkorb
    from diakronos_app.models.dateien import GruppeDatei, GruppeDateiEntsorgung

    haupt = _hochladen(SAENGER, PNG, "a.png", "Chor")
    unter = _hochladen(NOTEN, PNG, "b.png", "Chor", untergruppe="UG-Noten")
    # Jugend hat KEIN Dateien-Modul (der Kern verweigert das Hochladen dort —
    # das ist gewollt). Die fremde Zeile wird deshalb direkt gesetzt: geprueft
    # wird hier, dass die Gruppenloeschung sie NICHT anfasst.
    from diakronos_app.zeit import jetzt_wanduhr

    fremd = {"name": "gdatei-fremd", "schluessel": "datei-fremd"}
    dbmod0, GruppeDatei0 = _db()
    with dbmod0.SessionLocal.begin() as s:
        s.add(GruppeDatei0(name=fremd["name"], gruppe="Jugend",
                           schluessel=fremd["schluessel"], dateiname="c.png",
                           mime="image/png", groesse=10, angelegt_von=JUGEND_HV,
                           angepinnt=False, angelegt_am=jetzt_wanduhr()))
    schluessel = {z.name: z.schluessel for z in _zeilen()}

    papierkorb.loeschen("Gruppe", "Chor", von=ADMIN)
    papierkorb.endgueltig_entfernen("Gruppe", "Chor")

    dbmod, _ = _db()
    with dbmod.SessionLocal() as s:
        übrig = {z.name: z for z in s.query(GruppeDatei).all()}
        auftraege = {a.schluessel for a in s.query(GruppeDateiEntsorgung).all()}
    # Beide Räume der Gruppe sind weg — Hauptgruppe UND Untergruppe.
    assert set(übrig) == {fremd["name"]}, "nur die fremde Gruppe darf bleiben"
    assert auftraege == {schluessel[haupt["name"]], schluessel[unter["name"]]}
    assert schluessel[fremd["name"]] not in auftraege
    # Die Dateien selbst räumt erst der Job (DATEIEN-5) — hier noch da.
    assert ablage.existiert(schluessel[haupt["name"]])


# ── 12) Review R1: DSGVO Ende-zu-Ende ──────────────────────────────────────

def test_anonymisierung_nullt_die_kontospalten_und_die_datei_bleibt(welt, ablage):
    """Review R1/7b: Konto anonymisieren -> alle drei Kontospalten NULL.

    Die Zeile und die Datei bleiben (sie gehoeren der Gruppe, Konzept 5.3) — und
    die Leitung darf die Datei danach noch loeschen (deckt R1/1 Ende-zu-Ende).

    Hier steht bewusst NUR EIN Konto (SAENGER): in EINER Aufruf-Sitzung laufen
    die Pruefungen von ``anonymisiere`` (``ist_root``) in der nahtlosen
    Untertransaktion, die ``SessionLocal.begin()`` auf SQLite anlegt — nach dem
    ``rollback()`` der ersten Anonymisierung haengt die Sitzung wieder an der
    AeUSSEREN Transaktion, und deren spaeteres ``commit()`` setzt ALLE
    Schreibungen zurueck. Der Betrieb (PostgreSQL, eine Transaktion je Request)
    kennt diesen Zwischenzustand nicht; zwei Personen in EINEM Aufruf zu
    anonymisieren prueft ``tests/test_dsgvo1_anonymisierung.py``.
    """
    from diakronos_app import dsgvo_anonymisierung as A
    from diakronos_app.api import dateien as D
    from diakronos_app.models.dateien import GruppeDatei

    d = _hochladen(SAENGER, PNG, "a.png", "Chor")
    _set(HV)
    D.anpinnen(d["name"], True)

    dbmod, _ = _db()
    with dbmod.SessionLocal.begin() as s:
        A.anonymisiere(s, "M-Sa", [SAENGER])

    with dbmod.SessionLocal() as s:
        zeilen = {z.name: z for z in s.query(GruppeDatei).all()}
    assert d["name"] in zeilen, "die Zeile selbst bleibt"
    gepinnt = zeilen[d["name"]]
    assert gepinnt.angelegt_von is None            # war SAENGER
    assert gepinnt.angepinnt_von == HV             # HV bleibt (nicht anonymisiert)
    # Die Datei liegt weiter in der Ablage (Inhalt = Daten der Gruppe).
    assert ablage.existiert(gepinnt.schluessel)

    # Und die Leitung kann die verwaiste Datei weiter bearbeiten/loeschen.
    _set(HV)
    assert D.umbenennen(d["name"], "nachher.png")["dateiname"] == "nachher.png"
    D.loeschen(d["name"])
    D.wiederherstellen(d["name"])
