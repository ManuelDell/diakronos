"""DATEIEN-5: Aufräum-Job der Gruppendateien (Papierkorb 30 Tage + Entsorgung).

Geprüft wird die Fachlogik aus ``api/dateien.py`` (``aufraeumen``,
``gruppe_datei_papierkorb_leeren``, ``entsorgung_abarbeiten``) mit der
Test-Engine aus ``conftest`` (In-Memory-SQLite) und einer Ablage im
``tmp_path`` — kein Netz, keine laufende Instanz.

Kartenanforderungen:

* 29 Tage bleibt / 31 Tage geht (F5, ``PAPIERKORB_TAGE`` = 30),
* Untergruppen-Dateien werden erfasst (F3-Erbe: die Zeile trägt
  ``untergruppe``, die Frist gilt trotzdem),
* nicht gelöschte Dateien nie (F6),
* Auftrag bleibt bei Speicherfehler mit ``versuche`` + 1,
* ``belegt_bis`` verhindert den Doppellauf,
* ein Schlüssel, der noch von einer ``gruppe_datei``-Zeile benutzt wird, wird
  nicht gelöscht,
* der Scheduler registriert den Job im Minuten-Takt.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.api import dateien as D
from diakronos_app.models.dateien import (
    PAPIERKORB_TAGE,
    GruppeDatei,
    GruppeDateiEntsorgung,
)

JETZT = datetime(2026, 11, 24, 12, 0)


# ── Helfer ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def ablage(tmp_path):
    """Die Ablage nur für diesen Test (``tmp_path``, kein Netz)."""
    from diakronos_app.speicher import Lokal, setze_speicher, vergiss_speicher

    ordner = tmp_path / "files"
    ordner.mkdir()
    speicher = Lokal(ordner)
    setze_speicher(speicher)
    try:
        yield speicher
    finally:
        vergiss_speicher()


def _datei(speicher, schluessel: str, inhalt: bytes = b"inhalt") -> None:
    speicher.schreiben(schluessel, inhalt)


def _zeile(s, name: str, schluessel: str, *, gruppe: str = "Chor",
           untergruppe: str | None = None, geloescht_vor_tagen: float | None = None,
           geloescht_am: datetime | None = None,
           angelegt_vor_tagen: int = 1) -> GruppeDatei:
    """Eine ``gruppe_datei``-Zeile anlegen — ``geloescht_am``/``geloescht_vor_tagen``
    setzen den Papierkorb (``geloescht_am`` hat Vorrang: Tests legen Zeilen
    bewusst AUF die 30-Tage-Grenze, nicht nur „irgendwann danach“)."""
    if geloescht_am is None and geloescht_vor_tagen is not None:
        geloescht_am = JETZT - timedelta(days=geloescht_vor_tagen)
    zeile = GruppeDatei(
        name=name,
        gruppe=gruppe,
        untergruppe=untergruppe,
        schluessel=schluessel,
        dateiname="noten.pdf",
        mime="application/pdf",
        groesse=12,
        angelegt_am=JETZT - timedelta(days=angelegt_vor_tagen),
        angelegt_von=None,
        angepinnt=False,
        angepinnt_am=None,
        angepinnt_von=None,
        geloescht_am=geloescht_am,
        geloescht_von=None,
    )
    s.add(zeile)
    s.commit()
    return zeile


def _auftrag(s: GruppeDateiEntsorgung | None = None, schluessel: str = "",
             **kw) -> None:
    """Eine Entsorgungs-Zeile anlegen (``versuche``/``naechster_versuch_am``)."""
    zeile = GruppeDateiEntsorgung(
        schluessel=schluessel,
        versuche=kw.get("versuche", 0),
        naechster_versuch_am=kw.get("naechster_versuch_am", JETZT - timedelta(minutes=1)),
        belegt_bis=kw.get("belegt_bis"),
        angelegt_am=kw.get("angelegt_am", JETZT - timedelta(days=1)),
    )
    s.add(zeile)
    s.commit()


def _stand() -> tuple[list[str], list[GruppeDateiEntsorgung]]:
    """(Zeilen der Tabelle, Aufträge der Entsorgungsliste) aus der Test-DB."""
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        zeilen = [z.name for z in s.query(GruppeDatei).order_by(GruppeDatei.name).all()]
        auftraege = [(a.schluessel, int(a.versuche),
                      a.naechster_versuch_am, a.belegt_bis)
                     for a in s.query(GruppeDateiEntsorgung)
                     .order_by(GruppeDateiEntsorgung.schluessel).all()]
    return zeilen, auftraege


# ── 1) Frist: 29 Tage bleibt, 31 Tage geht ──────────────────────────────────


def test_papierkorb_29_tage_bleibt(patched_db, ablage):
    """Knapp INNERHALB der Frist: Zeile und Datei bleiben, kein Auftrag."""
    # 30 Tage minus eine Stunde: noch INNERHALB der Frist.
    _datei(ablage, "datei-29")
    with patched_db() as s:
        _zeile(s, "gdatei-29", "datei-29",
               geloescht_am=JETZT - timedelta(days=PAPIERKORB_TAGE) + timedelta(hours=1))

    ergebnis = D.aufraeumen(JETZT)

    assert PAPIERKORB_TAGE == 30
    assert ergebnis["papierkorb"] == 0
    zeilen, auftraege = _stand()
    assert zeilen == ["gdatei-29"]
    assert auftraege == []
    assert ablage.loeschen("datei-29") is True  # Datei war nie angetastet


def test_papierkorb_31_tage_geht_zeile_und_datei_weg(patched_db, ablage):
    """Knapp AUSSERHALB der Frist: Zeile fällt, Datei verschwindet im SELBEN Lauf."""
    # Genau auf der Grenze (``<=``): die Frist ist abgelaufen.
    _datei(ablage, "datei-31")
    _datei(ablage, "datei-neu")
    with patched_db() as s:
        _zeile(s, "gdatei-31", "datei-31",
               geloescht_am=JETZT - timedelta(days=PAPIERKORB_TAGE))
        _zeile(s, "gdatei-neu", "datei-neu", geloescht_vor_tagen=2)

    ergebnis = D.aufraeumen(JETZT)

    assert ergebnis["papierkorb"] == 1
    assert ergebnis["entsorgung"]["abgearbeitet"] == 1
    zeilen, auftraege = _stand()
    assert zeilen == ["gdatei-neu"]
    assert auftraege == []          # Auftrag angelegt UND wieder abgearbeitet
    assert ablage.auflisten("") == ["datei-neu"]


def test_papierkorb_loescht_zeile_wenn_die_ablage_klemmt(patched_db, ablage, monkeypatch):
    """Zeile fällt in der Transaktion; klemmt die Ablage, steht der Auftrag danach."""
    from diakronos_app.speicher import AblageFehler

    _datei(ablage, "datei-40")
    with patched_db() as s:
        _zeile(s, "gdatei-40", "datei-40", geloescht_vor_tagen=40)

    def klemmt(*_a, **_kw):
        raise AblageFehler("Netz weg")

    monkeypatch.setattr(ablage, "loeschen", klemmt)

    nur_papierkorb = D.gruppe_datei_papierkorb_leeren(JETZT)

    assert nur_papierkorb == 1
    zeilen, auftraege = _stand()
    assert zeilen == []
    assert [a[0] for a in auftraege] == ["datei-40"]
    assert ablage.pfad("datei-40") is not None  # Datei liegt noch da


# ── 2) Untergruppen-Dateien werden erfasst ──────────────────────────────────


def test_untergruppen_dateien_werden_erfasst(patched_db, ablage):
    """F3: eine Datei der UNTERGRUPPE ist eine eigene Zeile — dieselbe Frist."""
    _datei(ablage, "datei-ug")
    with patched_db() as s:
        _zeile(s, "gdatei-ug", "datei-ug", gruppe="Chor",
               untergruppe="UG-Noten",
               geloescht_am=JETZT - timedelta(days=PAPIERKORB_TAGE, minutes=5))

    ergebnis = D.aufraeumen(JETZT)

    assert ergebnis["papierkorb"] == 1
    assert ergebnis["entsorgung"]["abgearbeitet"] == 1
    zeilen, auftraege = _stand()
    assert zeilen == []
    assert auftraege == []
    assert ablage.auflisten("") == []


# ── 3) F6: nicht gelöschte Dateien haben keine Frist ────────────────────────


def test_nicht_geloeschte_dateien_werden_nie_angefasst(patched_db, ablage):
    """F6: auch eine uralte Datei ohne ``geloescht_am`` bleibt für immer.

    Zwei Zeilen, damit der Fall nicht an einer einzelnen Zeile hängt: beide
    ``angelegt_am`` 4000 Tage alt, ``geloescht_am`` NULL. Die ``IS NOT NULL``
    Bedingung ist in SQL streng genommen redundant (``NULL <= x`` ist NULL, also
    nicht wahr) — sie steht trotzdem da, damit F6 in der Abfrage LESBAR ist und
    nicht von SQLs dreiwertiger Logik abhängt.
    """
    _datei(ablage, "datei-alt")
    _datei(ablage, "datei-nie")
    with patched_db() as s:
        _zeile(s, "gdatei-alt", "datei-alt", geloescht_vor_tagen=None,
               angelegt_vor_tagen=4000)
        _zeile(s, "gdatei-nie", "datei-nie", geloescht_vor_tagen=None,
               angelegt_vor_tagen=4000)

    for _ in range(3):
        ergebnis = D.aufraeumen(JETZT)
        assert ergebnis["papierkorb"] == 0

    zeilen, auftraege = _stand()
    assert zeilen == ["gdatei-alt", "gdatei-nie"]
    assert auftraege == []
    assert sorted(ablage.auflisten("")) == ["datei-alt", "datei-nie"]


# ── 4) Entsorgungsliste: Fehler, Backoff, Belegung, Sicherheitsnetz ─────────


def test_auftrag_bleibt_bei_speicherfehler_mit_versuche_plus_eins(
        patched_db, ablage, monkeypatch):
    """Ein Ablage-Fehler löscht den Auftrag NICHT: ``versuche`` + 1, Backoff gesetzt."""
    from diakronos_app.speicher import AblageFehler

    _datei(ablage, "datei-kaputt")
    with patched_db() as s:
        _auftrag(s, "datei-kaputt")

    def klemmt(*_a, **_kw):
        raise AblageFehler("Quota voll")

    monkeypatch.setattr(ablage, "loeschen", klemmt)

    ergebnis = D.entsorgung_abarbeiten(JETZT)

    assert ergebnis == {"abgearbeitet": 0, "fehler": 1, "offen": 1}
    _zeilen, auftraege = _stand()
    assert len(auftraege) == 1
    schluessel, versuche, naechster, belegt_bis = auftraege[0]
    assert schluessel == "datei-kaputt"
    assert versuche == 1
    # Backoff nach dem ERSTEN Fehlschlag: 1 Minute.
    assert naechster == JETZT + timedelta(minutes=1)
    assert belegt_bis is None          # Belegung freigegeben, nächster Lauf darf
    assert ablage.pfad("datei-kaputt") is not None


def test_zweiter_fehler_erhoeht_weiter_und_wartezeit_waechst(patched_db, ablage,
                                                             monkeypatch):
    """Backoff-Reihe 1, 5, 30, 360 Minuten — und bleibt bei 360 stehen."""
    with patched_db() as s:
        _auftrag(s, "datei-kaputt", versuche=1,
                 naechster_versuch_am=JETZT - timedelta(minutes=1))

    def klemmt(*_a, **_kw):
        raise OSError("Platte weg")

    monkeypatch.setattr(ablage, "loeschen", klemmt)
    D.entsorgung_abarbeiten(JETZT)

    _zeilen, auftraege = _stand()
    _schluessel, versuche, naechster, _belegt = auftraege[0]
    assert versuche == 2
    assert naechster == JETZT + timedelta(minutes=5)

    assert D.entsorgung_wartezeit(1) == timedelta(minutes=1)
    assert D.entsorgung_wartezeit(2) == timedelta(minutes=5)
    assert D.entsorgung_wartezeit(3) == timedelta(minutes=30)
    assert D.entsorgung_wartezeit(4) == timedelta(minutes=360)
    assert D.entsorgung_wartezeit(99) == timedelta(minutes=360)


def test_belegung_verhindert_den_doppellauf(
        patched_db, ablage, monkeypatch):
    """``belegt_bis``/``naechster_versuch_am`` halten einen zweiten Lauf ab.

    Review R1/3: der Rückbau im ``finally`` verglich das Modulobjekt mit einem
    String und war damit wirkungslos. Jetzt umschließt ``monkeypatch.context()``
    NUR den ersten Lauf — danach ist ``hole_speicher`` wieder der echte Weg und
    ``patched_db`` bleibt unangetastet.
    """
    problem = RuntimeError("Ablage kaputt")

    class Klemme:
        """Ablage, die jedes Löschen verweigert — nach dem Rückbau wieder normal."""

        def __init__(self, echt):
            self.echt = echt

        def __getattr__(self, name):
            raise problem

    _datei(ablage, "datei-laeuft")
    with patched_db() as s:
        _auftrag(s, "datei-laeuft")

    # Erster Lauf: Auswahl und Belegung klappen, das Löschen nicht.
    with monkeypatch.context() as m:
        m.setattr("diakronos_app.speicher.hole_speicher", lambda: Klemme(ablage))
        D.entsorgung_abarbeiten(JETZT)

    _zeilen, auftraege = _stand()
    assert auftraege[0][1] == 1

    # Zweiter Lauf im SELBEN Moment: der Auftrag ist belegt (bzw. erst in einer
    # Minute fällig) — er wird nicht gewählt, nichts zählt doppelt.
    zweiter = D.entsorgung_abarbeiten(JETZT)

    assert zweiter == {"abgearbeitet": 0, "fehler": 0, "offen": 1}
    _zeilen, auftraege = _stand()
    assert auftraege[0][1] == 1
    assert ablage.pfad("datei-laeuft") is not None


def test_belegung_wird_gesetzt_und_verhindert_die_zweite_auswahl(patched_db, ablage):
    """Nach dem Belegen sieht die Auswahl den Auftrag bis ``belegt_bis`` nicht."""
    _datei(ablage, "datei-belegt")
    with patched_db() as s:
        _auftrag(s, "datei-belegt")

    belegung = JETZT + timedelta(minutes=D.AUFRAEUMEN_BELEGUNG_MINUTEN)
    gewaehlt = D._entsorgung_waehlen_und_belegen(JETZT, 100, belegung)
    assert gewaehlt == ["datei-belegt"]

    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        zeile = s.get(GruppeDateiEntsorgung, "datei-belegt")
        assert zeile.belegt_bis == belegung
        assert zeile.naechster_versuch_am == belegung

    # Ein zweiter Lauf in derselben Minute belegt nichts mehr.
    assert D._entsorgung_waehlen_und_belegen(JETZT, 100, belegung) == []
    # Und die Abarbeitung nimmt ihn auch nicht.
    assert D.entsorgung_abarbeiten(JETZT) == {"abgearbeitet": 0, "fehler": 0, "offen": 1}


def test_schluessel_noch_in_benutzung_wird_nicht_geloescht(patched_db, ablage):
    """Sicherheitsnetz: lebt noch eine ``gruppe_datei``-Zeile, bleibt die Datei."""
    _datei(ablage, "datei-geteilt")
    with patched_db() as s:
        # Eine ZEILE benutzt den Schlüssel weiter (z. B. Wiederherstellen nach
        # einem Fehlversuch) UND es steht ein Auftrag dazu in der Liste.
        _zeile(s, "gdatei-geteilt", "datei-geteilt", geloescht_vor_tagen=5)
        _auftrag(s, "datei-geteilt")

    ergebnis = D.entsorgung_abarbeiten(JETZT)

    assert ergebnis == {"abgearbeitet": 0, "fehler": 0, "offen": 1}
    assert ablage.auflisten("") == ["datei-geteilt"]
    _zeilen, auftraege = _stand()
    assert auftraege[0][0] == "datei-geteilt"


def test_uebersprungener_auftrag_wird_verschoben_nicht_jede_minute_gewaehlt(
        patched_db, ablage):
    """Review R1/1: Überspringen zählt ``versuche`` hoch und schiebt den Termin.

    Vorher blieb ``naechster_versuch_am`` in der Vergangenheit: der Minuten-Job
    hätte denselben Auftrag 1440-mal am Tag gewählt und ab ``AUFRAEUMEN_BATCH``
    solcher Aufträge das Kontingent blockiert. Datei unangetastet, Auftrag bleibt.
    """
    _datei(ablage, "datei-haengt")
    with patched_db() as s:
        _zeile(s, "gdatei-haengt", "datei-haengt", geloescht_vor_tagen=5)
        _auftrag(s, "datei-haengt")

    assert D.entsorgung_abarbeiten(JETZT) == {
        "abgearbeitet": 0, "fehler": 0, "offen": 1}

    _zeilen, auftraege = _stand()
    schluessel, versuche, naechster, belegt_bis = auftraege[0]
    assert schluessel == "datei-haengt"
    assert versuche == 1
    # Lange Stufe (6 h), nicht der 1-Minuten-Takt: ``AUFRAEUMEN_BENUTZT_WARTEZEIT``
    # zeigt auf die LETZTE Backoff-Stufe (Gegenprobe M3: ohne diese Kopplung
    # überlebte eine verkürzte Wartezeit).
    assert D.AUFRAEUMEN_BENUTZT_WARTEZEIT == len(D.AUFRAEUMEN_BACKOFF_MINUTEN)
    assert naechster == JETZT + timedelta(
        minutes=D.AUFRAEUMEN_BACKOFF_MINUTEN[-1])
    assert naechster - JETZT >= timedelta(hours=6)
    assert naechster > JETZT
    assert belegt_bis is None
    assert ablage.auflisten("") == ["datei-haengt"]   # Datei unangetastet

    # Zweiter Lauf im SELBEN Moment: nicht mehr in der Auswahl.
    assert D.entsorgung_abarbeiten(JETZT) == {
        "abgearbeitet": 0, "fehler": 0, "offen": 1}
    _zeilen, auftraege = _stand()
    assert auftraege[0][1] == 1          # nicht doppelt gezählt
    assert ablage.auflisten("") == ["datei-haengt"]


def test_uebersprungener_auftrag_escaliert_einmal_ab_warnung_ab(
        patched_db, ablage, caplog):
    """Review R1/6: bei ``AUFRAEUMEN_WARNUNG_AB`` steht EINMAL ``logger.error``."""
    import logging

    _datei(ablage, "datei-ewig")
    with patched_db() as s:
        _zeile(s, "gdatei-ewig", "datei-ewig", geloescht_vor_tagen=5)
        _auftrag(s, "datei-ewig", versuche=D.AUFRAEUMEN_WARNUNG_AB - 1)

    with caplog.at_level(logging.WARNING, logger=D.__name__):
        D.entsorgung_abarbeiten(JETZT)

    assert [r for r in caplog.records if r.levelno == logging.ERROR], caplog.text
    _zeilen, auftraege = _stand()
    assert auftraege[0][1] == D.AUFRAEUMEN_WARNUNG_AB

    # Nächster Lauf (nach der Wartezeit): KEIN zweites ``logger.error``.
    caplog.clear()
    spaeter = JETZT + timedelta(hours=7)
    with caplog.at_level(logging.WARNING, logger=D.__name__):
        D.entsorgung_abarbeiten(spaeter)
    assert not [r for r in caplog.records if r.levelno == logging.ERROR], caplog.text


def test_papierkorb_leeren_nutzt_delete_returning(patched_db, ablage):
    """Review R1/2: Zeile fällt per ``DELETE … RETURNING`` — kein SELECT davor.

    Geprüft wird der CODE (``inspect.getsource``) und das Ergebnis: die
    vorgemerkten Schlüssel sind genau die gelöschten Zeilen, ein zweiter Lauf
    findet nichts.
    """
    import inspect

    from sqlalchemy import delete
    from sqlalchemy.dialects import postgresql, sqlite

    quelle = inspect.getsource(D.gruppe_datei_papierkorb_leeren)
    assert "returning(" in quelle, quelle
    assert "select(GruppeDatei.schluessel)" not in quelle, quelle

    # Und das SQL selbst trägt RETURNING (beide Dialekte).
    anweisung = (
        delete(GruppeDatei)
        .where(GruppeDatei.geloescht_am.is_not(None))
        .returning(GruppeDatei.schluessel)
    )
    assert "RETURNING" in str(anweisung.compile(dialect=sqlite.dialect())).upper()
    assert "RETURNING" in str(anweisung.compile(dialect=postgresql.dialect())).upper()

    _datei(ablage, "datei-r")
    with patched_db() as s:
        _zeile(s, "gdatei-r", "datei-r", geloescht_vor_tagen=45)

    assert D.gruppe_datei_papierkorb_leeren(JETZT) == 1
    zeilen, auftraege = _stand()
    assert zeilen == []
    assert [a[0] for a in auftraege] == ["datei-r"]
    assert D.gruppe_datei_papierkorb_leeren(JETZT) == 0


def test_auswahl_mit_sperre_kompiliert_skip_locked():
    """Review R1/4: der PG-Zweig der Auswahl trägt ``FOR UPDATE SKIP LOCKED``."""
    from sqlalchemy.dialects import postgresql

    sql = str(D._entsorgung_auswahl_mit_sperre(JETZT, 100)
              .compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql.upper(), sql


def test_schon_weg_zaehlt_als_erledigt(patched_db, ablage):
    """Datei war schon weg: der Auftrag fällt trotzdem (Zweck erreicht)."""
    with patched_db() as s:
        _auftrag(s, "datei-weg")

    ergebnis = D.entsorgung_abarbeiten(JETZT)

    assert ergebnis == {"abgearbeitet": 1, "fehler": 0, "offen": 0}
    _zeilen, auftraege = _stand()
    assert auftraege == []


def test_nicht_faelliger_auftrag_wird_nicht_gewaehlt(patched_db, ablage):
    """Backoff wird eingehalten: ``naechster_versuch_am`` in der Zukunft = warten."""
    _datei(ablage, "datei-spaeter")
    with patched_db() as s:
        _auftrag(s, "datei-spaeter",
                 naechster_versuch_am=JETZT + timedelta(hours=5))

    assert D.entsorgung_abarbeiten(JETZT) == {
        "abgearbeitet": 0, "fehler": 0, "offen": 1}
    assert ablage.auflisten("") == ["datei-spaeter"]


# ── 5) Scheduler ────────────────────────────────────────────────────────────


def test_scheduler_registriert_den_job_im_minutentakt():
    """``job_gruppe_datei_aufraeumen`` steht in ``MINUTEN_JOBS`` — wie der Chat."""
    from diakronos_app import scheduler

    ids = {job_id for _minuten, _fn, job_id in scheduler.MINUTEN_JOBS}
    assert "gruppe_datei_aufraeumen" in ids
    assert "chat_anhang_entsorgung" in ids
    eintraege = {job_id: (minuten, fn) for minuten, fn, job_id in scheduler.MINUTEN_JOBS}
    minuten, fn = eintraege["gruppe_datei_aufraeumen"]
    assert fn is scheduler.job_gruppe_datei_aufraeumen
    assert minuten == eintraege["chat_anhang_entsorgung"][0]  # gleicher Takt

    sched = scheduler.build_scheduler()
    job = sched.get_job("gruppe_datei_aufraeumen")
    assert job is not None
    assert getattr(job.trigger, "interval", None) == timedelta(minutes=minuten)
    # Nicht gestartet: kein Aufräumen nötig (``shutdown`` würde werfen).


def test_scheduler_job_loggt_fehler_statt_zu_werfen(monkeypatch):
    """Ein Fehler im Aufräumen tötet den Scheduler nicht."""
    from diakronos_app import scheduler

    def platzt(*_a, **_kw):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(D, "aufraeumen", platzt)
    scheduler.job_gruppe_datei_aufraeumen()  # darf nicht werfen
