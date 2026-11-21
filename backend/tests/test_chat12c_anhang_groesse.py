"""CHAT-12c — Anhanggröße in den Admin-Einstellungen (Backend).

Manuel 21.11.: „Lass die Anhanggröße in den Admineinstellungen einstellbar
sein.“ Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 („10 MB je Datei“) und
Entscheidung **F9** („ein Wert“ — später auch Gruppendateien). Vorbild ist der
Weg der Aufbewahrungsfristen (CHAT-8): NULLBARE Spalte an der Gemeinde-Single,
Standard im Code, Prüfung in EINER Funktion für Endpunkt UND Upload.

Geprüft wird gegen den ECHTEN Weg — keine Attrappe:

  * Standard 10 MB ohne Einstellung (Konstante UND wirksame Grenze)
  * Admin setzt 25 → 20-MB-Datei geht durch, 26-MB-Datei abgewiesen mit
    „max. 25 MB“ (die Meldung nennt die EINGESTELLTE Zahl, nicht 10)
  * Lesedeckel richtet sich nach dem Wert: Grenze+1 Byte wird abgewiesen,
    ohne dass mehr als Grenze+1 gelesen wird (Datei-Objekt zählt mit)
  * Nicht-Admin (HV, MV, Mitglied, Gast) darf nicht setzen — 403 ohne Inhalt,
    nichts geschrieben
  * 0 / 51 / „abc“ / „2,5“ / leer werden mit freundlicher Meldung abgewiesen
  * die Chat-Seite (``meine_gespraeche``) trägt ``anhang_max_bytes`` — auch
    eine geänderte Einstellung kommt dort an
  * ein unbrauchbarer Wert in der Datenbank kippt den Upload nicht (Standard)
  * Migration ``chat12c_anhang_groesse``: up/down/up, hinter
    ``r_chat_standard``, genau EIN Kopf

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat12c_anhang_groesse.py
"""

from __future__ import annotations

import importlib
import io
import struct
import zlib
from pathlib import Path

import pytest

from diakronos_app import chat_anhanggrenze as G
from diakronos_app import db as dbmod
from diakronos_app.models.chat import (
    ANHANG_MAX_BYTES,
    ANHANG_MAX_MB_GRENZE,
    ANHANG_MAX_MB_STANDARD,
)

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

#: Dieselbe Welt wie ``test_chat12a_anhang`` (Chor mit Chat-Modul, Untergruppe,
#: HV/MV/GL, Mitglied, Fremder) — Fixture und Konten werden GETELT.
from test_chat2_api import (  # noqa: E402,F401 — Fixture teilen
    ADMIN,
    FREMD,
    GL,
    HV,
    MV,
    NOTEN,
    SAENGER,
    gespraech,
    welt,
)

MB = 1024 * 1024


def _set(konto: str) -> None:
    _session_mod.set_user(konto)


def _png() -> bytes:
    """Ein echtes, minimales PNG (nur Standardbibliothek)."""

    def chunk(typ: bytes, daten: bytes) -> bytes:
        return (struct.pack("!I", len(daten)) + typ + daten
                + struct.pack("!I", zlib.crc32(typ + daten) & 0xFFFFFFFF))

    ihdr = struct.pack("!IIBBBBB", 4, 4, 8, 2, 0, 0, 0)
    roh = b"".join(b"\x00" + b"\xff\x00\x00" * 4 for _ in range(4))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(roh)) + chunk(b"IEND", b""))


PNG = _png()


class _GezaehlterStrom(io.BytesIO):
    """Ein Datenstrom, der MITZÄHLT, wie viel gelesen wurde (Lesedeckel)."""

    def __init__(self, daten: bytes) -> None:
        super().__init__(daten)
        self.gelesen = 0

    def read(self, *args):
        ergebnis = super().read(*args)
        self.gelesen += len(ergebnis or b"")
        return ergebnis


class _Upload:
    """``UploadFile``-artig: ``.file``/``.filename``/``.content_type``."""

    def __init__(self, daten: bytes, filename: str = "foto.png",
                 content_type: str = "image/png", strom=None) -> None:
        self.file = strom if strom is not None else io.BytesIO(daten)
        self.filename = filename
        self.content_type = content_type

    def read(self, *args):  # pragma: no cover — der Endpunkt liest ``.file``
        return self.file.read(*args)


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


def _hochladen(g: str, konto: str, datei) -> dict:
    from diakronos_app.api import chat as C

    _set(konto)
    return C.anhang_hochladen(g, datei=datei)


def _setzen(mb):
    """Die Einstellung direkt schreiben (ohne Rechteprüfung — die ist der
    Endpunkt; hier geht es um Werte)."""
    with dbmod.SessionLocal.begin() as s:
        G.setze_einstellungen(s, mb=mb, benutzer=ADMIN)


# ── Standard ───────────────────────────────────────────────────────────────


def test_standard_ist_10_mb_ohne_einstellung(welt):
    """Ohne Einstellung (Spalte NULL) gilt 10 MB — Konstante UND wirksam."""
    assert ANHANG_MAX_MB_STANDARD == 10
    assert ANHANG_MAX_BYTES == 10 * MB
    with dbmod.SessionLocal.begin() as s:
        assert G.anhang_max_mb(s) == 10
        assert G.anhang_max_bytes(s) == 10 * MB
        assert G.holen_einstellungen(s) == {"anhang_max_mb": 10}


def test_ohne_einstellung_geht_10_mb_und_ein_byte_mehr_nicht(gespraech, ablage):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    gerade = PNG + b"\x00" * (10 * MB - len(PNG))
    antwort = _hochladen(gespraech, SAENGER, _Upload(gerade))
    assert antwort["groesse"] == 10 * MB

    with pytest.raises(ValidationError) as fehler:
        _hochladen(gespraech, SAENGER, _Upload(gerade + b"\x00"))
    assert "max. 10 MB" in str(fehler.value)


# ── Einstellung wirkt auf die Prüfung ──────────────────────────────────────


def test_admin_setzt_25_mb_dann_geht_20_mb_und_26_mb_nicht(gespraech, ablage):
    """Kartenfall: 20-MB-Datei geht durch, 26-MB-Datei abgewiesen mit „25 MB“."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set(ADMIN)
    antwort = C.chat_einstellungen_speichern(anhang_max_mb=25)
    _session_mod.reset_user()
    assert antwort["gespeichert"] is True
    assert antwort["anhang_max_mb"] == 25

    zwanzig = PNG + b"\x00" * (20 * MB - len(PNG))
    assert _hochladen(gespraech, SAENGER, _Upload(zwanzig))["groesse"] == 20 * MB

    sechsundzwanzig = PNG + b"\x00" * (26 * MB - len(PNG))
    with pytest.raises(ValidationError) as fehler:
        _hochladen(gespraech, SAENGER, _Upload(sechsundzwanzig))
    # Die Meldung nennt die EINGESTELLTE Zahl — nicht den Standard.
    assert "max. 25 MB" in str(fehler.value)
    assert "max. 10 MB" not in str(fehler.value)


def test_lesedeckel_richtet_sich_nach_dem_wert(gespraech, ablage):
    """Datei = Grenze+1 Byte wird abgewiesen, und es wird NICHT mehr gelesen."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _setzen(3)
    grenze = 3 * MB

    # Genau die Grenze: geht durch, gelesen werden Grenze+1 Byte (Deckel).
    strom = _GezaehlterStrom(PNG + b"\x00" * (grenze - len(PNG)))
    antwort = _hochladen(gespraech, SAENGER, _Upload(b"", strom=strom))
    assert antwort["groesse"] == grenze
    assert strom.gelesen <= grenze + 1

    # Grenze+1 Byte: abgewiesen — und der Decken zählt weiterhin Grenze+1.
    zu_gross = PNG + b"\x00" * (grenze + 1 - len(PNG))
    strom = _GezaehlterStrom(zu_gross + b"\x00" * (4 * MB))  # 4 MB mehr dahinter
    with pytest.raises(ValidationError) as fehler:
        _hochladen(gespraech, SAENGER, _Upload(b"", strom=strom))
    assert "max. 3 MB" in str(fehler.value)
    # Genau Grenze+1 Byte gelesen — der Rest wurde NIE angefasst.
    assert strom.gelesen == grenze + 1
    # Die 10-MB-Konstante spielt hier keine Rolle mehr.
    assert ANHANG_MAX_BYTES == 10 * MB


def test_lesedeckel_als_funktion(gespraech):
    """``_anhang_herkunft`` selbst: Deckel = Grenze+1 (nicht Standard+1)."""
    from diakronos_app.api import chat as C

    strom = _GezaehlterStrom(b"\x00" * (5 * MB))
    roh, _ = C._anhang_herkunft(_Upload(b"", strom=strom), grenze=2 * MB)
    assert len(roh) == 2 * MB + 1
    assert strom.gelesen == 2 * MB + 1


# ── Rechte: nur Administration schreibt ────────────────────────────────────


def test_nicht_admin_darf_nicht_setzen(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    for wer in (HV, MV, GL, SAENGER, FREMD, "Guest"):
        _set(wer)
        try:
            with pytest.raises(PermissionError) as fehler:
                C.chat_einstellungen_speichern(anhang_max_mb=25)
            # 403 OHNE Inhalt — der Grund bleibt im Server.
            assert not str(fehler.value or "")
        finally:
            _session_mod.reset_user()

    with dbmod.SessionLocal.begin() as s:
        assert G.holen_einstellungen(s) == {"anhang_max_mb": 10}


def test_nicht_admin_erfaehrt_auch_bei_unsinnigem_wert_nichts_ueber_die_grenzen(welt):
    """Rechteprüfung steht VOR der Wertprüfung (wie bei den Fristen)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError

    _set(HV)
    try:
        # 51 wäre für einen Admin ein ValidationError — hier kommt 403.
        with pytest.raises(PermissionError):
            C.chat_einstellungen_speichern(anhang_max_mb=51)
        with pytest.raises(PermissionError):
            C.chat_einstellungen_speichern(anhang_max_mb="abc")
    finally:
        _session_mod.reset_user()

    # Gegenprobe: der Admin bekommt die Werteprüfung sehr wohl zu sehen.
    _set(ADMIN)
    try:
        with pytest.raises(ValidationError):
            C.chat_einstellungen_speichern(anhang_max_mb=51)
    finally:
        _session_mod.reset_user()


def test_admin_setzt_randwerte_1_und_50(welt):
    from diakronos_app.api import chat as C

    _set(ADMIN)
    try:
        assert C.chat_einstellungen_speichern(anhang_max_mb=1)["anhang_max_mb"] == 1
        assert C.chat_einstellungen_speichern(anhang_max_mb=50)["anhang_max_mb"] == 50
    finally:
        _session_mod.reset_user()


# ── Ungültige Werte ────────────────────────────────────────────────────────


@pytest.mark.parametrize("wert", [0, 51, -1, 1000, "abc", "2,5", "2.5", "", None,
                                  True, False, "  "])
def test_unsinnige_werte_werden_freundlich_abgewiesen(welt, wert):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set(ADMIN)
    try:
        with pytest.raises(ValidationError) as fehler:
            C.chat_einstellungen_speichern(anhang_max_mb=wert)
        text = str(fehler.value)
        assert "Anhanggröße" in text
        # Freundlich: nennt die Grenzen, keinen Stapel/keine Ausnahme.
        assert "zwischen 1 und 50" in text or "ganze Zahl" in text
    finally:
        _session_mod.reset_user()

    with dbmod.SessionLocal.begin() as s:
        assert G.holen_einstellungen(s) == {"anhang_max_mb": 10}


def test_grenze_der_einstellung_ist_50():
    assert ANHANG_MAX_MB_GRENZE == 50
    assert ANHANG_MAX_MB_STANDARD <= ANHANG_MAX_MB_GRENZE


def test_lesen_ist_fuer_mitglieder_erlaubt(welt):
    from diakronos_app.api import chat as C

    _set(SAENGER)
    try:
        daten = C.chat_einstellungen_lesen()
    finally:
        _session_mod.reset_user()
    assert daten["anhang_max_mb"] == 10
    assert daten["standard"] == 10
    assert (daten["minimum"], daten["maximum"]) == (1, 50)


def test_unbrauchbarer_wert_in_der_datenbank_kippt_den_upload_nicht(gespraech, ablage):
    """Ein von Hand gesetzter Wert (z. B. 0) bedeutet Standard, nicht „alles“."""
    with dbmod.SessionLocal.begin() as s:
        G._gemeinde_zeile(s).anhang_max_mb = 0
    with dbmod.SessionLocal.begin() as s:
        assert G.anhang_max_mb(s) == 10
        assert G.anhang_max_bytes(s) == 10 * MB
    # Und der Upload läuft mit dem Standard.
    assert _hochladen(gespraech, SAENGER, _Upload(PNG))["groesse"] == len(PNG)


# ── Chat-Seite: die Vorab-Prüfung kennt die Grenze ─────────────────────────


def test_meine_gespraeche_traegt_anhang_max_bytes(welt, gespraech):
    from diakronos_app.api import chat as C

    _set(SAENGER)
    try:
        daten = C.meine_gespraeche()
    finally:
        _session_mod.reset_user()
    assert daten["anhang_max_bytes"] == 10 * MB

    # Eine geänderte Einstellung kommt in DERSELBEN Antwort an (kein zweiter
    # Rundlauf) — und in BYTES, damit die Oberfläche nicht selbst umrechnet.
    _setzen(25)
    _set(SAENGER)
    try:
        daten = C.meine_gespraeche()
    finally:
        _session_mod.reset_user()
    assert daten["anhang_max_bytes"] == 25 * MB


def test_feldnamen_sind_stabil():
    """Die UI-Karte hängt an diesen Namen — sie stehen an EINER Stelle."""
    assert G.FELD == "anhang_max_mb"
    assert G.FELD_BYTES == "anhang_max_bytes"


def test_keine_zweite_wahrheit_im_endpunkt():
    """``api/chat.py`` nimmt die Grenze aus ``chat_anhanggrenze``."""
    quelle = (BACKEND / "src" / "diakronos_app" / "api" / "chat.py").read_text(
        encoding="utf-8")
    # Die Konstante darf nur noch als Rückfallwert im Deckel stehen (Doku-
    # Zeilen zählen nicht mit).
    treffer = [zeile for zeile in quelle.splitlines()
               if "ANHANG_MAX_BYTES" in zeile and not zeile.strip().startswith("*")
               and "``" not in zeile]
    assert len(treffer) == 2, treffer   # Import + ``deckel``-Rückfallwert
    assert "grenze_bytes" in quelle
    assert "anhanggrenze.anhang_max_bytes(s)" in quelle


# ── Migration ──────────────────────────────────────────────────────────────


def _skripte():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_haengt_hinter_r_chat_standard_und_ist_einziger_kopf():
    skripte = _skripte()
    rev = skripte.get_revision("chat12c_anhang_groesse")
    assert rev is not None
    assert rev.down_revision == "r_chat_standard", rev.down_revision
    assert "Revises: r_chat_standard" in Path(rev.path).read_text(encoding="utf-8")
    # LINEAR: kein Merge-Head, genau EIN Kopf.
    assert skripte.get_heads() == ["chat12c_anhang_groesse"]
    assert len(skripte.get_bases()) == 1


def test_migration_up_down_up(tmp_path):
    """Die Spalte entsteht, verschwindet wieder und entsteht erneut (idempotent)."""
    import importlib.util

    import sqlalchemy as sa

    pfad = BACKEND / "alembic" / "versions" / "chat12c_anhang_groesse.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("chat12c_anhang_groesse", pfad))
    modul.__spec__.loader.exec_module(modul)

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as bind:
        bind.execute(sa.text(
            "CREATE TABLE gemeinde_einstellungen (name VARCHAR(140) PRIMARY KEY)"
        ))

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    def _spalten() -> set[str]:
        return {s["name"] for s in sa.inspect(engine).get_columns("gemeinde_einstellungen")}

    with engine.begin() as bind:
        ctx = MigrationContext.configure(bind)
        with Operations.context(ctx):
            modul.upgrade()
            assert "anhang_max_mb" in _spalten()
            spalte = {s["name"]: s for s in sa.inspect(bind).get_columns(
                "gemeinde_einstellungen")}["anhang_max_mb"]
            assert spalte["nullable"] is True
            # Zweites upgrade ändert nichts (idempotent).
            modul.upgrade()
            assert "anhang_max_mb" in _spalten()
            modul.downgrade()
            assert "anhang_max_mb" not in _spalten()
            modul.upgrade()
            assert "anhang_max_mb" in _spalten()


def test_modell_spalte_ist_nullbar_und_leer_der_standard():
    """Modell und Migration sagen dasselbe: NULLBAR, NULL = Standard."""
    from diakronos_app.models.gemeinde import GemeindeEinstellungen

    spalte = GemeindeEinstellungen.__table__.c["anhang_max_mb"]
    assert spalte.nullable is True
    assert spalte.type.python_type is int
    assert spalte.server_default is None


def test_endpunkte_heissen_chat_einstellungen_und_ohne_merker(welt):
    """R1-Nachbesserung — die Namen und der Weg sind festgehalten.

    1. Die Endpunkte tragen den Modul-Präfix (``chat_einstellungen_lesen`` /
       ``chat_einstellungen_speichern``): die Registry legt auch nackte Pfade
       (``einstellungen_lesen``) und ``api.<name>`` an — ein gleichnamiger
       Endpunkt in einem anderen Modul würde kollidieren.
    2. ``anhang_max_mb`` liest bei JEDEM Aufruf frisch: KEIN Merker über
       ``rechte.kern`` (eine Einstellung ist keine Rechtefrage) — sonst käme
       eine Änderung erst im nächsten Request an.
    """
    from diakronos_app import chat_anhanggrenze as G
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import registry

    assert not hasattr(C, "einstellungen_lesen")
    assert not hasattr(C, "einstellungen_speichern")
    assert "chat_einstellungen_lesen" in C.__all__
    assert "chat_einstellungen_speichern" in C.__all__
    assert registry.methoden_fuer(C.chat_einstellungen_speichern) == ("POST",)
    # Lesend trägt keine Methoden-Beschränkung (None = alle), wie ``fristen_lesen``.
    assert registry.methoden_fuer(C.chat_einstellungen_lesen) is None

    quelle = Path(G.__file__).read_text(encoding="utf-8")
    assert "_gemerkt" not in quelle, "Anhanggröße darf den Rechte-Merker nicht nutzen"

    with dbmod.SessionLocal.begin() as s:
        G.setze_einstellungen(s, mb=7)
    with dbmod.SessionLocal.begin() as s:
        assert G.anhang_max_mb(s) == 7
        G.setze_einstellungen(s, mb=12)
    with dbmod.SessionLocal.begin() as s:
        assert G.anhang_max_mb(s) == 12, "zweiter Aufruf muss den neuen Wert lesen"
