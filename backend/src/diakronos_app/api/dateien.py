"""DATEIEN-3: Gruppendateien — Liste, Hochladen, Ausliefern, Papierkorb.

Konzept ``DATEIEN-KONZEPT.md`` (Abschnitte 1/S1, 2, 3, 4) und die
Entscheidungen Manuel 23.11.2026:

* **F3** Untergruppen haben EIGENE Dateien (``untergruppe`` gesetzt).
* **F4** HV/MV (in der Untergruppe auch GL) dürfen FREMDE Dateien löschen; die
  eigene darf jede hochladende Person löschen. Die Rückfrage ist Sache der
  Oberfläche.
* **F5** Löschen = Papierkorb (``geloescht_am``/``geloescht_von``),
  Wiederherstellen möglich; ENDGÜLTIG löscht der Job aus DATEIEN-5.
* **F8** Alle Dokumentarten außer Ausführbarem — ``ablage.RICHTLINIE_SPERR``.
* **F9** Größengrenze wie im Chat (``chat_anhanggrenze.anhang_max_bytes``),
  KEIN Tageslimit.

RECHTE: Es gibt EIN Rechtesystem. Jede Frage geht über
``rechte.kern.darf/pruefe`` mit ``typ="gruppe_datei"`` — LESEN (Liste,
Ausliefern), ANLEGEN (Hochladen), ANPINNEN (anpinnen/lösen), SCHREIBEN
(umbenennen/löschen, ``besitzer`` = ``angelegt_von`` IMMER mitgegeben) und
MODERIEREN (Papierkorb-LISTE und Wiederherstellen — wer dort wegräumen darf).
Untergruppen-Dateien geben ``untergruppe=<UG>`` UND ``gruppe=<Hauptgruppe>`` mit.
Ist das Modul ``dateien`` in der Gruppe aus, sagt der Kern NEIN und der Endpunkt
antwortet mit der normalen Rechte-Meldung.

AUSLIEFERN: JEDE Fehlerart (gibt es nicht / darf nicht / im Papierkorb /
Ablage weg) ergibt DIESELBE 404 — der Endpunkt verrät nicht, ob es eine Datei
gibt. Dieselbe 404 gilt auch für anpinnen/umbenennen/löschen/wiederherstellen:
zuerst wird geprüft, ob die Datei für den Aufrufer überhaupt SICHTBAR ist
(LESEN am Raum); erst danach entscheidet die eigentliche Aktion (403).

KEIN ``RechteObjekt`` je Datei (Review DATEIEN-3/R1): der Kern geht für
``gruppe_datei`` direkt in ``_darf_raum`` und fragt nie nach einem Eintrag —
ein Eintrag je Datei würde nur Waisen hinterlassen. Alle Rechte kommen aus den
Argumenten (``gruppe``/``untergruppe``/``besitzer``).

BESITZER: ``angelegt_von`` ist der Besitzer. Ist es NULL (Konto gelöscht oder
anonymisiert), gibt es KEINEN Besitzer — der Kern liest das als „fremd“ (Leitung
JA, Mitglied NEIN, ``besitzer_fehlt``). Die Datei gehört damit weiter der
Gruppe und bleibt pflegbar.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select, update

from diakronos_app import ablage
from diakronos_app import rechte
#: Die Sitzungs-Factory wird über das MODUL ``db`` benutzt (``dbmod.SessionLocal``),
#: NICHT als gebundener Name: die Test-Fixture ``patched_db`` biegt das Modul-
#: Attribut um, ein ``from … import SessionLocal`` bliebe auf der Betriebs-DB
#: stehen (dasselbe Muster wie ``api/chat.py``).
from diakronos_app import db as dbmod
from diakronos_app.chat_anhanggrenze import anhang_max_bytes
from diakronos_app.db import als_aktuelle_sitzung
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.dateien import (
    GDT_DATEI_PRAEFIX,
    GDT_NAME_MAX,
    GDT_SPEICHER_PRAEFIX,
    GruppeDatei,
    GruppeDateiEntsorgung,
)

logger = logging.getLogger(__name__)

#: Die eine Meldung für einen nicht auslieferbaren Eintrag (alle Fehlerarten).
NICHT_GEFUNDEN = "Datei nicht gefunden."

#: Höchstzahl der Aufträge, die ein Request nach einem Löschen selbst versucht
#: (wie ``api.chat.ENTSORGUNG_JE_ANFRAGE``).
ENTSORGUNG_JE_ANFRAGE = 3
#: Zeitlimit für den Sofort-Versuch (nur Ablagen mit Netz kennen eines).
ENTSORGUNG_ZEITLIMIT_SEKUNDEN = 2.0

# ── DATEIEN-5: Aufräum-Job (Papierkorb + Entsorgungsliste) ──────────────────
#: Höchstzahl der Entsorgungs-Aufträge je Job-Lauf (wie ``api.chat``).
AUFRAEUMEN_BATCH = 100
#: Belegung: so lange gilt ein Auftrag als „in Arbeit“ (Doppellauf-Schutz).
AUFRAEUMEN_BELEGUNG_MINUTEN = 60
#: Wartezeit nach dem n-ten Fehlschlag (Index ab dem ERSTEN Fehlschlag; der
#: letzte Wert bleibt stehen) — dieselben Zahlen wie bei den Chat-Anhängen.
AUFRAEUMEN_BACKOFF_MINUTEN = (1, 5, 30, 6 * 60)
#: Ab dieser Anzahl Versuche steht EINMAL ein ``logger.error`` im Protokoll
#: (wie ``api.chat.ENTSORGUNG_WARNUNG_AB``). Der Auftrag bleibt trotzdem stehen
#: bzw. wird nur verschoben — es geht um DSGVO-Dateien.
AUFRAEUMEN_WARNUNG_AB = 20
#: Wartezeit, wenn ein Auftrag wegen noch benutztem Schlüssel übersprungen wird
#: (Review R1/1): Stufe 4 des Backoffs (6 Stunden) — ein Wiederherstellen wird
#: nicht im Minutentakt gegen die Ablage gehalten.
AUFRAEUMEN_BENUTZT_WARTEZEIT = 4

__all__ = [
    "AUFRAEUMEN_BACKOFF_MINUTEN",
    "AUFRAEUMEN_BATCH",
    "AUFRAEUMEN_BELEGUNG_MINUTEN",
    "AUFRAEUMEN_BENUTZT_WARTEZEIT",
    "AUFRAEUMEN_WARNUNG_AB",
    "ENTSORGUNG_JE_ANFRAGE",
    "ENTSORGUNG_ZEITLIMIT_SEKUNDEN",
    "NICHT_GEFUNDEN",
    "anpinnen",
    "aufraeumen",
    "datei",
    "einstellung_setzen",
    "einstellungen",
    "entsorgung_abarbeiten",
    "entsorgung_wartezeit",
    "gruppe_datei_papierkorb_leeren",
    "hochladen",
    "liste",
    "loeschen",
    "papierkorb",
    "umbenennen",
    "wiederherstellen",
]


# ── Kleine Helfer ───────────────────────────────────────────────────────────


def _jetzt() -> datetime:
    """Jetzt als Wandzeit der Gemeinde, OHNE Zeitzone (wie ``api.chat``)."""
    from diakronos_app.zeit import jetzt_wanduhr

    return jetzt_wanduhr()


def _benutzer() -> str:
    return str(session.user or "")


def _kennung() -> str:
    from uuid import uuid4

    return f"{GDT_DATEI_PRAEFIX}{uuid4().hex}"


def _wahr(wert: Any) -> bool:
    """Formular-/JSON-Wahrheitswert (``true``, ``1``, ``"true"``)."""
    if isinstance(wert, bool):
        return wert
    return str(wert or "").strip().lower() in ("1", "true", "ja", "yes", "on")


def _nicht_gefunden():
    """Dieselbe 404 für JEDE Fehlerart (unbekannt, kein Recht, Papierkorb)."""
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    return DoesNotExistError(NICHT_GEFUNDEN)


def _pruefe(benutzer: str, aktion: str, *, gruppe: str | None,
            untergruppe: str | None = None, besitzer: str | None = None) -> None:
    """DIE Rechtefrage — immer über den Kern, nie eine eigene Regel.

    ``besitzer`` MUSS bei SCHREIBEN mitgegeben werden (``angelegt_von``); ohne
    Besitzer sagt der Kern NEIN (fail closed).
    """
    rechte.pruefe(benutzer, aktion, "gruppe_datei", None,
                  gruppe=gruppe or None, untergruppe=untergruppe or None,
                  besitzer=besitzer)


def _raum(gruppe: str, untergruppe: str | None) -> tuple[str, str | None]:
    """Geprüfter (Gruppe, Untergruppe) eines Aufrufs — Untergruppe muss passen.

    Der Kern prüft das Zusammenpassen selbst (``untergruppe_passt_nicht``); hier
    wird nur eindeutig gemacht, WAS gefragt ist.
    """
    g = str(gruppe or "").strip()
    u = str(untergruppe or "").strip() or None
    return g, u


def _zeile_eintrag(z: GruppeDatei, benutzer: str, *, darf_anpinnen: bool,
                   darf_loeschen: bool) -> dict[str, Any]:
    """Eine Datei für die Oberfläche — ohne technischen Schlüssel."""
    return {
        "name": z.name,
        "dateiname": z.dateiname,
        "mime": z.mime,
        "groesse": int(z.groesse or 0),
        "angelegt_am": z.angelegt_am.isoformat(sep=" ") if z.angelegt_am else "",
        "angelegt_von": z.angelegt_von or "",
        "eigene": bool(z.angelegt_von) and z.angelegt_von == benutzer,
        "angepinnt": bool(z.angepinnt),
        "angepinnt_am": z.angepinnt_am.isoformat(sep=" ") if z.angepinnt_am else "",
        "darf_anpinnen": bool(darf_anpinnen),
        "darf_bearbeiten": bool(darf_loeschen),
    }


def _kopfzeile(benutzer: str, gruppe: str, untergruppe: str | None,
               s) -> dict[str, Any]:
    """Der Kopf der Liste: was der Aufrufer hier darf + die geltende Grenze.

    ``s`` ist die LESESITZUNG: die Grenze kommt aus derselben Einstellung wie
    im Chat (``anhang_max_bytes(session)`` — F9, eine Zahl).
    """
    return {
        "darf_hochladen": bool(rechte.darf(benutzer, rechte.ANLEGEN, "gruppe_datei",
                                          gruppe=gruppe, untergruppe=untergruppe)),
        "darf_anpinnen": bool(rechte.darf(benutzer, rechte.ANPINNEN, "gruppe_datei",
                                          gruppe=gruppe, untergruppe=untergruppe)),
        "max_bytes": int(anhang_max_bytes(s)),
    }


def _entsorgung_vormerken(s, schluessel: list[str]) -> list[str]:
    """Speicher-Schlüssel vormerken — EIN Auftrag je Schlüssel (idempotent).

    Rückgabe: die Schlüssel, die DIESER Aufruf gerade angelegt hat (nur die
    versucht der Request danach einmal selbst).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    liste_ = sorted({str(k) for k in schluessel or () if str(k).strip()})
    if not liste_:
        return []
    jetzt = _jetzt()
    einfuegen = pg_insert if s.get_bind().dialect.name == "postgresql" else sqlite_insert
    angelegte = s.execute(
        einfuegen(GruppeDateiEntsorgung).values([
            {"schluessel": wert, "versuche": 0, "naechster_versuch_am": jetzt,
             "belegt_bis": None, "angelegt_am": jetzt}
            for wert in liste_
        ]).on_conflict_do_nothing(index_elements=["schluessel"])
        .returning(GruppeDateiEntsorgung.schluessel)
    ).scalars().all()
    return [str(w) for w in angelegte]


def _entsorgung_sofort(schluessel: list[str]) -> int:
    """Die EIGENEN Aufträge EINMAL versuchen — nie eine Ausnahme nach außen.

    Die Zeile ist in derselben Transaktion gefallen: verschwindet die Datei
    jetzt nicht, holt es der Aufräum-Job (DATEIEN-5) nach. Ein Fehler hier darf
    den Request nicht kippen (der Löschvorgang ist bereits gültig).
    """
    from diakronos_app.speicher import AblageFehler
    from diakronos_app.speicher import NichtGefunden as SpeicherNichtGefunden
    from diakronos_app.speicher import hole_speicher

    eigene = [str(k) for k in schluessel or () if str(k).strip()][:ENTSORGUNG_JE_ANFRAGE]
    if not eigene:
        return 0
    weg: list[str] = []
    try:
        speicher = hole_speicher()
    except Exception as fehler:  # noqa: BLE001 — Auftrag bleibt, Job wiederholt
        logger.warning("Gruppendatei-Entsorgung: Ablage nicht verfügbar: %s", fehler)
        return 0
    for wert in eigene:
        try:
            noch_da = speicher.loeschen_mit_zeitlimit(wert, sekunden=ENTSORGUNG_ZEITLIMIT_SEKUNDEN)
        except (SpeicherNichtGefunden, AblageFehler):
            # „war schon weg“ liest die Ablage als Erfolg (``loeschen`` ->
            # ``False``); wirft sie doch, bleibt der Auftrag für den Job.
            logger.info("Gruppendatei %r nicht gelöscht (Job holt es nach).", wert)
            continue
        except Exception as fehler:  # noqa: BLE001 — nie nach außen
            logger.warning("Gruppendatei %r nicht gelöscht: %s", wert, fehler)
            continue
        if noch_da is not False:
            # Review R1/4: JEDER Schlüssel für sich — entfernt wird nur, was
            # dieser Aufruf wirklich gelöscht hat (Muster ``api.chat``).
            weg.append(wert)
    if weg:
        # Erst NACH dem Lauf in EINER eigenen Transaktion — die Auftragsliste
        # nie während des Löschens anfassen.
        _auftraege_entfernen(weg)
    return len(weg)


def _auftraege_entfernen(schluessel: list[str]) -> None:
    """Erledigte Aufträge aus der Entsorgungsliste nehmen (eigene Transaktion)."""
    if not schluessel:
        return
    try:
        with dbmod.SessionLocal() as s, s.begin():
            s.execute(delete(GruppeDateiEntsorgung).where(
                GruppeDateiEntsorgung.schluessel.in_(schluessel)))
    except Exception as fehler:  # noqa: BLE001 — Aufräumen ist nachrangig
        logger.warning("Gruppendatei-Entsorgungsaufträge nicht entfernt: %s", fehler)


# ── DATEIEN-5: Aufräum-Job (Papierkorb 30 Tage + Entsorgungsliste) ──────────
#
# Muster und Begründungen wörtlich von ``api.chat.chat_anhang_entsorgung_abarbeiten``
# (Review R1/3, CHAT-12a-2/3, SPEICHER-3): Auswählen+Belegen in EINER
# Transaktion, kein Ablage-Aufruf unter einer Zeilensperre, Fehler zählen
# ``versuche`` hoch und bleiben als Auftrag stehen, „war schon weg“ ist Erfolg.
# Der Job läuft im Minutentakt (``scheduler.MINUTEN_JOBS``).


def entsorgung_wartezeit(versuche: int) -> timedelta:
    """Wartezeit bis zum nächsten Versuch nach ``versuche`` Fehlschlägen.

    Index 0 (1 Minute) gilt nach dem ERSTEN Fehlschlag, der letzte Eintrag
    (6 Stunden) ab dem vierten und bleibt stehen. Reine Funktion — ohne Uhr
    prüfbar.
    """
    stelle = min(max(int(versuche or 0), 1), len(AUFRAEUMEN_BACKOFF_MINUTEN)) - 1
    return timedelta(minutes=AUFRAEUMEN_BACKOFF_MINUTEN[stelle])


def _noch_benutzt(s, schluessel: list[str]) -> set[str]:
    """Welche dieser Speicher-Schlüssel hängt noch an einer ``gruppe_datei``-Zeile?

    Sicherheitsnetz (Kartenanforderung 2): gelöscht wird KEINE Datei, deren
    Schlüssel noch von einer Zeile benutzt wird. Im Normalbetrieb kann das nicht
    vorkommen (der Auftrag entsteht in derselben Transaktion, in der die Zeile
    fällt), aber ein Wiederherstellen nach einem Fehlversuch oder ein
    Bestandsfehler darf keine Datei unter einer lebenden Zeile wegziehen.
    """
    if not schluessel:
        return set()
    return {str(k) for k in s.execute(
        select(GruppeDatei.schluessel).where(GruppeDatei.schluessel.in_(schluessel))
    ).scalars().all() if k}


def gruppe_datei_papierkorb_leeren(jetzt: datetime | None = None,
                                   tage: int | None = None) -> int:
    """Papierkorb leeren: Zeilen nach ``PAPIERKORB_TAGE`` endgültig entfernen.

    F5 (Manuel): eine gelöschte Datei bleibt 30 Tage wiederherstellbar, danach
    ist sie weg. Die Frist steht als Konstante im Modell
    (``models.dateien.PAPIERKORB_TAGE``) — kein Admin-Schalter.

    Je Zeile mit ``geloescht_am <= jetzt - PAPIERKORB_TAGE``:

    * die Zeile fällt, und
    * der Speicher-Schlüssel wird per
      ``dsgvo_anonymisierung._datei_entsorgung_vormerken`` vorgemerkt (der EINE
      Weg in die Liste, ``INSERT … ON CONFLICT DO NOTHING``)
      — in DERSELBEN Transaktion (Auftrag und Zeile entstehen bzw. verschwinden
      zusammen: entweder es gibt die Zeile mit ihrem Schlüssel oder den Auftrag,
      nie ein Verweis ins Leere).

    Review R1/2: ``DELETE … RETURNING schluessel`` statt „erst SELECT, dann
    DELETE“ — zwischen beiden Anweisungen durfte ein Wiederherstellen die Zeile
    aus dem Papierkorb holen; der Auftrag hätte dann eine lebende Datei
    entsorgt (das Sicherheitsnetz ``_noch_benutzt`` fing es erst im nächsten
    Schritt). Jetzt sind die vorgemerkten Schlüssel GENAU die gelöschten
    Zeilen. ``RETURNING`` verlangt SQLite ≥ 3.35 / PostgreSQL — beides liegt
    vor.

    Die Datei selbst löscht ``entsorgung_abarbeiten`` — NACH dem Commit: ein
    Rollback darf keine Datei gelöscht haben. F6: NICHT gelöschte Dateien
    (``geloescht_am IS NULL``) werden nie angefasst — die Bedingung steht in der
    Abfrage, nicht in einer Schleife danach.

    Rückgabe: Zahl der entfernten Zeilen. Idempotent — ein zweiter Lauf findet
    nichts mehr.
    """
    from diakronos_app.dsgvo_anonymisierung import _datei_entsorgung_vormerken
    from diakronos_app.models.dateien import PAPIERKORB_TAGE

    jetzt = jetzt or _jetzt()
    grenze = jetzt - timedelta(days=PAPIERKORB_TAGE if tage is None else int(tage))
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        faellig = [str(k) for k in s.execute(
            delete(GruppeDatei)
            .where(GruppeDatei.geloescht_am.is_not(None),
                   GruppeDatei.geloescht_am <= grenze)
            .returning(GruppeDatei.schluessel)
        ).scalars().all() if k]
        if not faellig:
            return 0
        _datei_entsorgung_vormerken(s, faellig)
    return len(faellig)


def _entsorgung_auswahl_abfrage(jetzt: datetime, anzahl: int):
    """Die Auswahl-Abfrage des Jobs — EINE Wahrheit für Code und Test.

    Nur Aufträge, die jetzt dran sind (``naechster_versuch_am <= jetzt``), der
    früheste zuerst: ein dauerhaft scheiternder Schlüssel blockiert damit keine
    neueren Aufträge (CHAT-12a-2, „keine Kopfblockade“).
    """
    return (
        select(GruppeDateiEntsorgung)
        .where(GruppeDateiEntsorgung.naechster_versuch_am <= jetzt)
        .order_by(GruppeDateiEntsorgung.naechster_versuch_am,
                  GruppeDateiEntsorgung.schluessel)
        .limit(anzahl)
    )


def _entsorgung_auswahl_mit_sperre(jetzt: datetime, anzahl: int):
    """Dieselbe Auswahl MIT ``FOR UPDATE SKIP LOCKED`` (PostgreSQL-Zweig)."""
    return _entsorgung_auswahl_abfrage(jetzt, anzahl).with_for_update(skip_locked=True)


def _verschiebe_benutzte(s, jetzt: datetime, stand: dict[str, int],
                         noch_benutzt: set[str]) -> None:
    """Aufträge auf noch benutzte Schlüssel verschieben — in der LAUFENDEN Transaktion.

    Review R1/1: der Zweig übersprang solche Aufträge nur, ``naechster_versuch_am``
    blieb in der Vergangenheit. Folge: jeder Minutentakt wählte sie neu (Warnung
    alle 60 s je Schlüssel) und ab ``AUFRAEUMEN_BATCH`` solcher Aufträge war das
    Kontingent dauerhaft voll — neuere, lösbare Aufträge kamen nie dran
    (Kopfblockade). Hier deshalb ``versuche`` + 1 und der nächste Termin um die
    LANGE Backoff-Stufe (``AUFRAEUMEN_BENUTZT_WARTEZEIT`` = 6 h) nach vorn.

    Die Datei wird NICHT angefasst und der Auftrag NICHT gelöscht: lebt die
    Zeile irgendwann nicht mehr, löscht ein späterer Lauf die Datei; bleibt sie
    für immer, bleibt der Auftrag für immer sichtbar (DSGVO, nichts verschwindet
    still).

    ``stand`` ist der Stand, den die Auswahl GELESEN hat — der neue Versuchszähler
    hängt damit an der Belegung dieses Laufs, nicht an einem zweiten Stand. Ab
    ``AUFRAEUMEN_WARNUNG_AB`` Versuchen steht EINMAL ein ``logger.error``
    (Übergang per ``==``, wie bei den Chat-Anhängen).
    """
    for wert in sorted(noch_benutzt):
        versuche = stand.get(wert, 0) + 1
        s.execute(
            update(GruppeDateiEntsorgung)
            .where(GruppeDateiEntsorgung.schluessel == wert)
            .values(versuche=versuche,
                    naechster_versuch_am=jetzt + entsorgung_wartezeit(
                        AUFRAEUMEN_BENUTZT_WARTEZEIT),
                    belegt_bis=None)
        )
        if versuche == AUFRAEUMEN_WARNUNG_AB:
            logger.error(
                "Gruppendatei %r seit %s Versuchen nicht entsorgbar: der "
                "Schlüssel wird noch von einer gruppe_datei-Zeile benutzt "
                "(nächster Versuch in %s).",
                wert, versuche,
                entsorgung_wartezeit(AUFRAEUMEN_BENUTZT_WARTEZEIT),
            )
        else:
            logger.warning(
                "Gruppendatei %r: Schlüssel wird noch von einer "
                "gruppe_datei-Zeile benutzt (Versuch %s) — Datei bleibt, "
                "nächster Versuch in %s.",
                wert, versuche,
                entsorgung_wartezeit(AUFRAEUMEN_BENUTZT_WARTEZEIT),
            )


def _entsorgung_waehlen_und_belegen(jetzt: datetime, anzahl: int,
                                    belegung: datetime) -> list[str]:
    """Auswählen UND belegen in EINER Transaktion — sonst nichts (CHAT-12a-3).

    Scheitert Auswahl oder Belegung, kommt eine LEERE Liste zurück: ohne
    Belegung darf dieser Lauf nichts löschen, sonst machte er die Arbeit eines
    zweiten Laufs doppelt (``versuche`` zählte doppelt, Backoff daneben).

    Wirksam gegen den Doppellauf ist ``naechster_versuch_am`` (die Auswahl
    liest NUR diese Spalte); ``belegt_bis`` wird zusätzlich gesetzt, weil es
    der bleibende Beleg „dieser Auftrag ist in Arbeit“ ist (Review R1/5).
    """
    try:
        return _entsorgung_waehlen_und_belegen_eng(jetzt, anzahl, belegung)
    except Exception as fehler:  # noqa: BLE001 — nie den Scheduler-Job abbrechen
        logger.warning(
            "Gruppendatei: Entsorgungsliste nicht belegt (%s) — dieser Lauf "
            "löscht nichts, der nächste Takt versucht es erneut.", fehler,
        )
        return []


def _entsorgung_waehlen_und_belegen_eng(jetzt: datetime, anzahl: int,
                                        belegung: datetime) -> list[str]:
    """Eingeengter Kern: Auswahl, Sperre, Belegung, Commit — wirft."""
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if s.get_bind().dialect.name == "postgresql":
            abfrage = _entsorgung_auswahl_mit_sperre(jetzt, anzahl)
        else:
            abfrage = _entsorgung_auswahl_abfrage(jetzt, anzahl)
        auftraege = s.execute(abfrage).scalars().all()
        #: ``schluessel -> versuche`` der Zeilen, die dieser Lauf gewählt hat.
        stand = {str(a.schluessel or ""): int(a.versuche or 0)
                 for a in auftraege if str(a.schluessel or "")}
        werte = list(stand)
        if not werte:
            return []
        noch_benutzt = _noch_benutzt(s, werte)
        if noch_benutzt:
            # Review R1/1: der Auftrag wird NICHT nur übersprungen — sonst bliebe
            # ``naechster_versuch_am`` in der Vergangenheit, der nächste Takt
            # wählte ihn erneut (alle 60 s dieselbe Warnung) und ab
            # ``AUFRAEUMEN_BATCH`` solcher Aufträge käme kein neuer Auftrag mehr
            # dran (Kopfblockade). Deshalb in DERSELBEN Transaktion: Versuch
            # zählen und den nächsten Termin auf die lange Stufe schieben. Die
            # DATEI bleibt unangetastet, der Auftrag bleibt stehen (DSGVO).
            _verschiebe_benutzte(s, jetzt, stand, noch_benutzt)
            werte = [w for w in werte if w not in noch_benutzt]
            if not werte:
                return []
        s.execute(
            update(GruppeDateiEntsorgung)
            .where(GruppeDateiEntsorgung.schluessel.in_(werte),
                   GruppeDateiEntsorgung.naechster_versuch_am < belegung)
            .values(naechster_versuch_am=belegung, belegt_bis=belegung)
        )
    return werte


def _auftrag_erledigt(wert: str) -> bool:
    """Auftrag nach gelungenem Löschen entfernen — ``True``, wenn dieser Lauf ihn beendet."""
    try:
        with dbmod.SessionLocal.begin() as s:
            getroffen = s.execute(
                delete(GruppeDateiEntsorgung)
                .where(GruppeDateiEntsorgung.schluessel == wert)
            ).rowcount or 0
    except Exception as fehler:  # noqa: BLE001 — der nächste Lauf wiederholt es
        logger.warning("Gruppendatei %r: Auftrag nicht entfernt: %s", wert, fehler)
        return False
    return bool(getroffen)


def _fehler_verbuchen(wert: str, fehler: Exception, jetzt: datetime) -> None:
    """Einen Fehlschlag am Auftrag verbuchen — ``versuche`` + 1, dann Backoff.

    Läuft in einer eigenen, kurzen Transaktion (der Ablage-Aufruf davor ist
    vorbei). ``versuche`` zählt die DATENBANK hoch; der neue Stand wird danach
    gelesen und bestimmt den nächsten Versuch. Trifft das ``UPDATE`` keine
    Zeile, hat ein anderer Lauf sie erledigt — kein Fehler. Der Auftrag wird
    NIE gelöscht (es geht um DSGVO-Dateien), ``belegt_bis`` wird freigegeben.
    """
    kurz = str(fehler)[:200]
    try:
        with dbmod.SessionLocal.begin() as s:
            stand = s.execute(
                update(GruppeDateiEntsorgung)
                .where(GruppeDateiEntsorgung.schluessel == wert)
                .values(versuche=GruppeDateiEntsorgung.versuche + 1)
                .returning(GruppeDateiEntsorgung.versuche)
            ).scalar_one_or_none()
            if stand is None:
                logger.debug("Gruppendatei %r: Auftrag war schon weg.", wert)
                return
            s.execute(
                update(GruppeDateiEntsorgung)
                .where(GruppeDateiEntsorgung.schluessel == wert)
                .values(naechster_versuch_am=jetzt + entsorgung_wartezeit(stand),
                        belegt_bis=None)
            )
    except Exception as verbuchen:  # noqa: BLE001 — nie den Job abbrechen
        logger.warning("Gruppendatei %r: Fehlversuch nicht verbucht: %s",
                       wert, verbuchen)
        return
    if int(stand) == AUFRAEUMEN_WARNUNG_AB:
        logger.error(
            "Gruppendatei %r seit %s Versuchen nicht entsorgbar (Datei bleibt "
            "offen, nächster Versuch in %s): %s",
            wert, stand, entsorgung_wartezeit(stand), kurz,
        )
    else:
        logger.warning("Gruppendatei %r nicht entsorgt (Versuch %s, nächster "
                       "Versuch in %s): %s",
                       wert, stand, entsorgung_wartezeit(stand), kurz)


def entsorgung_abarbeiten(jetzt: datetime | None = None,
                          grenze: int | None = None) -> dict[str, int]:
    """Offene Entsorgungs-Aufträge abarbeiten (Kartenanforderung 2).

    Drei Schritte je Lauf — kein Ablage-Aufruf unter einer Zeilensperre:

    1. Auswählen und belegen (``_entsorgung_waehlen_und_belegen``),
    2. löschen (``hole_speicher().loeschen`` — die EINE Ablage),
    3. verbuchen: Erfolg → Auftrag fällt; Fehler → ``versuche`` + 1 mit Backoff,
       der Auftrag bleibt stehen.

    „War schon weg“ (``loeschen`` → ``False``, ``NichtGefunden``) zählt als
    erledigt: der Zweck ist erreicht. Ein Schlüssel, der noch von einer
    ``gruppe_datei``-Zeile benutzt wird, wird nicht gelöscht (Sicherheitsnetz,
    ``_noch_benutzt``).

    Rückgabe: ``{"abgearbeitet": n, "fehler": n, "offen": n}`` — ``offen`` ist
    die Zahl der Aufträge am Ende des Laufs.
    """
    from diakronos_app.speicher import NichtGefunden as SpeicherNichtGefunden
    from diakronos_app.speicher import hole_speicher

    ergebnis = {"abgearbeitet": 0, "fehler": 0, "offen": 0}
    anzahl = AUFRAEUMEN_BATCH if grenze is None else max(1, int(grenze))
    jetzt = jetzt or _jetzt()
    belegung = jetzt + timedelta(minutes=AUFRAEUMEN_BELEGUNG_MINUTEN)

    werte = _entsorgung_waehlen_und_belegen(jetzt, anzahl, belegung)

    speicher = None
    for wert in werte:
        try:
            if speicher is None:
                speicher = hole_speicher()
            speicher.loeschen(wert)
        except SpeicherNichtGefunden:
            pass  # „war schon weg“ = Erfolg
        except Exception as fehler:  # noqa: BLE001 — nie den Job abbrechen
            ergebnis["fehler"] += 1
            _fehler_verbuchen(wert, fehler, jetzt)
            continue
        if _auftrag_erledigt(wert):
            ergebnis["abgearbeitet"] += 1

    with dbmod.SessionLocal() as s:
        ergebnis["offen"] = int(s.execute(
            select(func.count()).select_from(GruppeDateiEntsorgung)
        ).scalar_one() or 0)
    return ergebnis


def aufraeumen(jetzt: datetime | None = None) -> dict[str, Any]:
    """Scheduler-Job (DATEIEN-5): Papierkorb leeren, dann Aufträge abarbeiten.

    Reihenfolge ist Absicht: erst fallen die abgelaufenen Papierkorb-Zeilen und
    ihre Schlüssel stehen als Auftrag in der Liste, danach wird die Liste
    abgearbeitet — die Dateien dieser Zeilen verschwinden also im SELBEN Lauf,
    nicht erst am nächsten Tag.

    Fehler je Schritt werden gefangen und protokolliert; ein gescheiterter
    Papierkorb-Schritt verhindert das Abarbeiten nicht (und umgekehrt). Der
    Job ist idempotent: was weg ist, ist weg.

    Rückgabe: ``{"papierkorb": n, "entsorgung": {...}}``.
    """
    jetzt = jetzt or _jetzt()
    ergebnis: dict[str, Any] = {"papierkorb": 0, "entsorgung": {}}
    try:
        ergebnis["papierkorb"] = gruppe_datei_papierkorb_leeren(jetzt)
    except Exception:  # noqa: BLE001 — ein Fehler darf den Job nicht kippen
        logger.exception("Gruppendatei: Papierkorb-Leeren fehlgeschlagen")
    try:
        ergebnis["entsorgung"] = entsorgung_abarbeiten(jetzt)
    except Exception:  # noqa: BLE001
        logger.exception("Gruppendatei: Entsorgungsliste fehlgeschlagen")
    return ergebnis


def _datei_zeile(s, name: str) -> GruppeDatei | None:
    kennung = str(name or "").strip()
    return s.get(GruppeDatei, kennung) if kennung else None


def _besitzer(z: GruppeDatei) -> str:
    """Der Besitzer-Kennwert für den Kern — bei NULL ausdrücklich ein LEERER Text.

    Review R1/1: hier stand eine Ersatz-Kennung (``"\\x00geloeschtes-konto"``),
    die als „fremder Besitzer“ durchging und die Datei damit in eine falsche
    Rolle schob.

    Der Kern verlangt ``besitzer`` bei ``gruppe_datei`` IMMER
    (``besitzer_fehlt`` sonst) und vergleicht ``besitzer == benutzer`` — ein
    leerer Text ist deshalb die ehrliche Antwort für „niemand“: die Datei eines
    gelöschten Kontos gehört NIEMANDEM, also darf kein Mitglied sie als eigene
    führen, die Leitung (HV/MV, in der Untergruppe GL) sie aber pflegen
    (F4 „fremde Datei“). Die Oberfläche zeigt ``angelegt_von == ""``.
    """
    return str(z.angelegt_von or "").strip()


def _sichtbar(benutzer: str, z: GruppeDatei) -> bool:
    """Ist ``z`` für ``benutzer`` sichtbar — dieselbe Frage wie in :func:`liste`?

    Review R1/2: anpinnen/umbenennen/löschen/wiederherstellen antworten auf eine
    nicht sichtbare Datei mit DERSELBEN 404 wie auf eine unbekannte Kennung.
    Sichtbar heißt: LESEN am Raum der Datei — und, bei einer Papierkorb-Zeile,
    MODERIEREN am Raum (nur wer im Papierkorb aufräumen darf, sieht die Zeile;
    genau so zeigt sie :func:`papierkorb`). Erst danach entscheidet die
    eigentliche Aktion und antwortet ggf. mit 403.
    """
    if z.geloescht_am is not None:
        return bool(rechte.darf(benutzer, rechte.MODERIEREN, "gruppe_datei", None,
                                gruppe=z.gruppe, untergruppe=z.untergruppe))
    return bool(rechte.darf(benutzer, rechte.LESEN, "gruppe_datei", None,
                            gruppe=z.gruppe, untergruppe=z.untergruppe))


# ── Liste und Kopf ──────────────────────────────────────────────────────────


@whitelist(allow_guest=False)  # SEC-11: rein lesend
def liste(gruppe: str, untergruppe: str | None = None) -> dict[str, Any]:
    """Die Dateien einer (Unter-)Gruppe — angepinnte zuerst, dann neueste.

    Recht: LESEN am Raum. Je Eintrag stehen die Rechte des Aufrufers
    (``darf_anpinnen``, ``darf_bearbeiten``); der Kopf nennt ``darf_hochladen``,
    ``darf_anpinnen`` und die geltende Grenze in Bytes (F9, dieselbe Zahl wie
    im Chat). Dateien im PAPIERKORB erscheinen hier NICHT.
    """
    benutzer = _benutzer()
    g, u = _raum(gruppe, untergruppe)
    if not g:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("gruppe fehlt.", ValidationError)
    _pruefe(benutzer, rechte.LESEN, gruppe=g, untergruppe=u)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        kopf = _kopfzeile(benutzer, g, u, s)
        bedingung = [GruppeDatei.gruppe == g,
                     GruppeDatei.untergruppe.is_(None) if u is None
                     else GruppeDatei.untergruppe == u,
                     GruppeDatei.geloescht_am.is_(None)]
        zeilen = s.execute(
            select(GruppeDatei).where(*bedingung).order_by(
                GruppeDatei.angepinnt.desc(),
                GruppeDatei.angepinnt_am.desc(),
                GruppeDatei.angelegt_am.desc(),
                GruppeDatei.name.desc(),
            )
        ).scalars().all()
        eintraege = [
            _zeile_eintrag(
                z, benutzer,
                darf_anpinnen=bool(rechte.darf(
                    benutzer, rechte.ANPINNEN, "gruppe_datei", None,
                    gruppe=g, untergruppe=u)),
                darf_loeschen=bool(rechte.darf(
                    benutzer, rechte.SCHREIBEN, "gruppe_datei", None,
                    gruppe=g, untergruppe=u, besitzer=_besitzer(z))),
            )
            for z in zeilen
        ]
    return {"success": True, "gruppe": g, "untergruppe": u,
            "dateien": eintraege, "anzahl": len(eintraege), **kopf}


# ── Hochladen ───────────────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def hochladen(gruppe: str, untergruppe: str | None = None, datei=None,
              file=None, dateiname=None) -> dict[str, Any]:
    """Eine Datei HOCHLADEN (F8: alles außer Ausführbarem, F9: Chat-Grenze).

    Ablauf (Muster ``api.chat.anhang_hochladen``):

    1. Recht ANLEGEN am Raum (Schalter ``dateien_hochladen_alle``, Leitung immer).
    2. ``ablage.nimm_upload(datei, grenze, RICHTLINIE_SPERR)`` — Deckel beim
       Lesen, leer/zu groß, Typ per Magie UND Endung (Sperrliste), Viren-Haken.
    3. In die EINE Ablage schreiben (``ablage.lege_ab``) — scheitert das, gibt es
       KEINE Zeile.
    4. Zeile schreiben; scheitert sie, wandert der Schlüssel in die
       Entsorgungsliste (und wird einmal sofort versucht) — nie eine Waise.

    Ein Tageslimit gibt es NICHT (F9).
    """
    vom_aufrufer = file if datei is None else datei
    benutzer = _benutzer()
    g, u = _raum(gruppe, untergruppe)
    if not g:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("gruppe fehlt.", ValidationError)
    _pruefe(benutzer, rechte.ANLEGEN, gruppe=g, untergruppe=u)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        grenze = int(anhang_max_bytes(s))

    info = ablage.nimm_upload(
        vom_aufrufer, grenze=grenze, richtlinie=ablage.RICHTLINIE_SPERR,
        name=dateiname or None)
    try:
        schluessel = ablage.lege_ab(info, GDT_SPEICHER_PRAEFIX)
    except Exception as fehler:  # noqa: BLE001 — Ablage-Fehler ist ein Eingabefehler
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        logger.warning("Gruppendatei nicht abgelegt: %s", fehler)
        throw("Die Datei konnte nicht abgelegt werden. Bitte später erneut versuchen.",
              ValidationError)

    kennung = _kennung()
    try:
        with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
            s.add(GruppeDatei(
                name=kennung,
                gruppe=g,
                untergruppe=u,
                schluessel=schluessel,
                dateiname=info.anzeigename[:GDT_NAME_MAX],
                mime=info.typ,
                groesse=info.groesse,
                angelegt_am=_jetzt(),
                angelegt_von=benutzer or None,
                angepinnt=False,
            ))
            s.flush()
    except Exception:
        # Keine Zeile → der Schlüssel wäre unerreichbar. Erst den Auftrag
        # vormerken, dann einmal sofort versuchen (der Job wiederholt es).
        vorgemerkt: list[str] = []
        try:
            with dbmod.SessionLocal() as s2, s2.begin():
                vorgemerkt = _entsorgung_vormerken(s2, [schluessel])
        except Exception as fehler:  # noqa: BLE001 — das Original zählt
            logger.warning("Gruppendatei %r nicht vorgemerkt: %s", schluessel, fehler)
        entfernt = 0
        try:
            entfernt = _entsorgung_sofort([schluessel])
        except Exception as fehler:  # noqa: BLE001 — das Original zählt
            logger.warning("Gruppendatei %r nicht gelöscht: %s", schluessel, fehler)
        if not vorgemerkt and not entfernt:
            logger.error("Gruppendatei %r ist verwaist (kein Auftrag, Löschen "
                         "gescheitert) — manuelle Nacharbeit nötig.", schluessel)
        raise

    return {"success": True, "name": kennung, "dateiname": info.anzeigename,
            "mime": info.typ, "groesse": info.groesse, "gruppe": g,
            "untergruppe": u}


# ── Anpinnen, Umbenennen ────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def anpinnen(name: str, an: Any = True) -> dict[str, Any]:
    """Eine Datei anpinnen bzw. den Pin lösen (Aktion ANPINNEN)."""
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    wert = _wahr(an)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.ANPINNEN, gruppe=z.gruppe, untergruppe=z.untergruppe)
        if wert:
            if not z.angepinnt:
                z.angepinnt = True
                z.angepinnt_am = _jetzt()
                z.angepinnt_von = benutzer or None
        else:
            z.angepinnt = False
            z.angepinnt_am = None
            z.angepinnt_von = None
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name, "angepinnt": bool(z.angepinnt)}
    rechte.merker_leeren()
    return antwort


@whitelist(methods=["POST"], allow_guest=False)
def umbenennen(name: str, dateiname: str) -> dict[str, Any]:
    """Den Anzeigenamen ändern (SCHREIBEN, ``besitzer`` = ``angelegt_von``).

    Bereinigt wird mit derselben Regel wie beim Upload
    (``ablage.dateiname``): kein Pfad, keine Steuerzeichen, ≤ 120 Zeichen. Die
    Sperrliste gilt auch hier — ein Name, der auslieferbar wäre
    (``.exe``/``.html``), wird abgewiesen. Name, Typ und Ablage bleiben.
    """
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    neu = ablage.dateiname(str(dateiname or ""), "")
    if not neu:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("Bitte einen Dateinamen angeben.", ValidationError)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.SCHREIBEN, gruppe=z.gruppe,
                untergruppe=z.untergruppe, besitzer=_besitzer(z))
        ablage.pruefe_endungen(neu)
        z.dateiname = neu[:GDT_NAME_MAX]
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name, "dateiname": z.dateiname}
    rechte.merker_leeren()
    return antwort


# ── Löschen (Papierkorb), Wiederherstellen, Papierkorb-Liste ────────────────


@whitelist(methods=["POST"], allow_guest=False)
def loeschen(name: str) -> dict[str, Any]:
    """Eine Datei in den PAPIERKORB legen (F5) — nicht endgültig löschen.

    Recht: SCHREIBEN mit ``besitzer`` = ``angelegt_von`` — die eigene Datei
    darf jede hochladende Person löschen, fremde HV/MV (in der Untergruppe auch
    GL). Endgültig entfernt (Zeile + Datei) der Job aus DATEIEN-5.
    """
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.SCHREIBEN, gruppe=z.gruppe,
                untergruppe=z.untergruppe, besitzer=_besitzer(z))
        z.geloescht_am = _jetzt()
        z.geloescht_von = benutzer or None
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name,
                   "geloescht_am": z.geloescht_am.isoformat(sep=" ")}
    rechte.merker_leeren()
    return antwort


@whitelist(methods=["POST"], allow_guest=False)
def wiederherstellen(name: str) -> dict[str, Any]:
    """Eine Datei aus dem Papierkorb holen (F5).

    Wiederherstellen ist Wegräumen FÜR die Gruppe — deshalb die Aktion
    MODERIEREN (dieselbe, die der Kern dem Papierkorb zuordnet); wer sie nicht
    hat, bekommt die normale Rechte-Meldung.

    Sichtbarkeit (Review R1/2): Ein NICHT gelöschter Eintrag ist über LESEN
    sichtbar — eine Aktion darauf ist eine Rechte-Frage (403). Eine Zeile im
    PAPIERKORB sieht nur, wer dort aufräumen darf (MODERIEREN, wie
    :func:`papierkorb`); für alle anderen ist sie unbekannt (404).
    """
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.MODERIEREN, gruppe=z.gruppe, untergruppe=z.untergruppe)
        if z.geloescht_am is None:
            return {"success": True, "name": z.name, "wiederhergestellt": False}
        z.geloescht_am = None
        z.geloescht_von = None
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name, "wiederhergestellt": True}
    rechte.merker_leeren()
    return antwort


@whitelist(allow_guest=False)  # SEC-11: rein lesend
def papierkorb(gruppe: str, untergruppe: str | None = None) -> dict[str, Any]:
    """Die Dateien im PAPIERKORB einer (Unter-)Gruppe (F5).

    Nur für die, die dort wegräumen dürfen — MODERIEREN am Raum (HV/MV, in der
    Untergruppe auch GL; Administrator immer). Neueste Löschung zuerst, je
    Eintrag ``loeschbar_ab`` = Zeitpunkt, ab dem der Job (DATEIEN-5) endgültig
    entfernt (``models.dateien.PAPIERKORB_TAGE``).
    """
    from datetime import timedelta

    from diakronos_app.models.dateien import PAPIERKORB_TAGE

    benutzer = _benutzer()
    g, u = _raum(gruppe, untergruppe)
    if not g:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("gruppe fehlt.", ValidationError)
    _pruefe(benutzer, rechte.MODERIEREN, gruppe=g, untergruppe=u)
    aufbewahrung = timedelta(days=PAPIERKORB_TAGE)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        zeilen = s.execute(
            select(GruppeDatei).where(
                GruppeDatei.gruppe == g,
                GruppeDatei.untergruppe.is_(None) if u is None
                else GruppeDatei.untergruppe == u,
                GruppeDatei.geloescht_am.is_not(None),
            ).order_by(GruppeDatei.geloescht_am.desc(), GruppeDatei.name.desc())
        ).scalars().all()
        eintraege = [
            {
                "name": z.name,
                "dateiname": z.dateiname,
                "mime": z.mime,
                "groesse": int(z.groesse or 0),
                "geloescht_am": z.geloescht_am.isoformat(sep=" ") if z.geloescht_am else "",
                "geloescht_von": z.geloescht_von or "",
                "loeschbar_ab": (z.geloescht_am + aufbewahrung).isoformat(sep=" ")
                if z.geloescht_am else "",
            }
            for z in zeilen
        ]
    return {"success": True, "gruppe": g, "untergruppe": u,
            "aufbewahrung_tage": PAPIERKORB_TAGE,
            "dateien": eintraege, "anzahl": len(eintraege)}


# ── Ausliefern ──────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)  # GET und HEAD (Download); SEC-11: rein lesend
def datei(name: str):
    """Eine Gruppendatei AUSLIEFERN — gestreamt, mit Rechteprüfung.

    Recht: LESEN am Raum der Datei. JEDE Fehlerart ergibt DIESELBE 404:
    unbekannte Kennung, kein Leserecht, Datei im Papierkorb, Objekt in der
    Ablage weg. Kopfzeilen aus dem Baustein (``ablage.ausliefer_kopf``):
    geprüfter Typ, ``nosniff``, ``inline`` nur für erkannte Bilder.
    """
    from fastapi.responses import StreamingResponse

    from diakronos_app.speicher import AblageFehler, NichtGefunden, hole_speicher
    from diakronos_app.speicher import NichtGefunden as SpeicherNichtGefunden

    benutzer = _benutzer()
    kennung = str(name or "").strip()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None:
            raise _nicht_gefunden()
        if not rechte.darf(benutzer, rechte.LESEN, "gruppe_datei", None,
                           gruppe=z.gruppe, untergruppe=z.untergruppe):
            raise _nicht_gefunden()
        typ = str(z.mime or ablage.UNBEKANNTER_TYP)
        dateiname = str(z.dateiname or "")
        schluessel = str(z.schluessel or "")

    if not schluessel:
        raise _nicht_gefunden()
    try:
        bloecke, anfang, ende = hole_speicher().strom(schluessel, von=0, bis=None)
    except (SpeicherNichtGefunden, NichtGefunden, AblageFehler):
        raise _nicht_gefunden() from None

    kopf = ablage.ausliefer_kopf(typ, dateiname)
    if ende < anfang:
        return StreamingResponse(iter(()), status_code=200,
                                 media_type=ablage.sicherer_typ(typ),
                                 headers={**kopf, "Content-Length": "0"})
    # Review R1/8: die Länge kommt aus dem BEREICH, den die Ablage wirklich
    # liefert (``ende - anfang + 1``, Grenzen wie ``speicher.strom`` sie
    # ausgibt) — ``z.groesse`` ist der Stand beim Hochladen und kann abweichen.
    laenge = int(ende) - int(anfang) + 1
    return StreamingResponse(bloecke, status_code=200,
                             media_type=ablage.sicherer_typ(typ),
                             headers={**kopf, "Content-Length": str(max(laenge, 0))})


# ── Einstellungen: reine Durchreiche an den Kern ────────────────────────────


@whitelist(allow_guest=False)
def einstellungen(gruppe: str) -> dict[str, Any]:
    """Die Gruppenschalter (``dateien_hochladen_alle``/``dateien_anpinnen_alle``).

    Reine Durchreiche an ``rechte.verwaltung.gruppeneinstellungen`` — kein
    eigener Weg, keine eigene Vorgabe.
    """
    from diakronos_app.rechte import verwaltung

    return verwaltung.gruppeneinstellungen(_benutzer(), str(gruppe or "").strip())


@whitelist(methods=["POST"], allow_guest=False)
def einstellung_setzen(gruppe: str, schluessel: str, wert: Any = None) -> dict[str, Any]:
    """Einen Gruppenschalter setzen (HV/MV/Administrator) — Durchreiche."""
    from diakronos_app.rechte import verwaltung

    return verwaltung.setze_gruppeneinstellung(
        _benutzer(), str(gruppe or "").strip(), str(schluessel or "").strip(),
        _wahr(wert))
