"""CHAT-7b: Runden (3–8), Vorschläge, Kontaktsperre.

Revision ID: chat7b_runden
Revises: chat4b_umfrage_erinnerung
Create Date: 2026-11-19

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S3 (Zeilen ~100–122): „Runden mit
3–8 benannten Beteiligten; anlegen darf, wer alle erreichen darf; hinzufügen
nur mit Zustimmung der Runde; blockieren (‚nicht mehr anschreiben lassen')
sofort, ohne Begründung, ohne dass die andere Seite es erfährt“. Karte CHAT-7b.

DREI ÄNDERUNGEN, keine vierte:

  1. ``rechte_kontaktsperre`` (NEUE Tabelle) — das Modell steht seit dem
     Rechte-Kern des Operators (Commit ``04c339b1``) in
     ``models/rechte.py``; die Tabelle selbst fehlte noch. Spalten:
     ``id, benutzer, gesperrt, angelegt_am``, Unique ``(benutzer, gesperrt)``
     (eine Sperre je Richtung) und Index auf ``gesperrt`` (die Gegenrichtung
     beim Löschen eines Kontos findet ihre Zeilen darüber).
  2. ``chat_teilnehmer.verlassen_am`` (NEUE Spalte, nullable) — „ich verlasse
     die Runde“ ist etwas anderes als „das Konto ist gelöscht“. Die Zeile
     bleibt stehen (die Person bleibt für die anderen benannt), gilt aber
     nicht mehr als Teilnahme. Nullable OHNE ``server_default``: jede
     Bestandszeile ist „noch dabei“ und trägt NULL — kein Rewrite.
     Dazu ``chat_teilnehmer.sichtbar_ab`` (nullable, Review R1/SOLL 7): ab
     wann die Person den Verlauf liest — beim ersten Beitritt die Beitrittszeit,
     nach einem Austritt die des Wiedereintritts. Auch ohne ``server_default``:
     NULL heißt für Bestandszeilen „von Anfang an alles“.
  3. ``chat_runde_vorschlag`` (NEUE Tabelle) — „X möchte Y hinzufügen“ mit
     ``gespraech, vorgeschlagen_von, mitglied, stand, entschieden_von,
     entschieden_am, angelegt_am`` plus EINEM partiellen Unique-Index
     (``gespraech, mitglied``) auf ``stand = 'offen'``: je Runde und Person
     höchstens EIN offener Vorschlag, nach einer Entscheidung wieder einer.

     ``stand`` ist ``String(20)`` OHNE CHECK-Constraint/Enum — die vier Werte
     (``offen``, ``angenommen``, ``abgelehnt``, ``beendet``; CHAT-7b-2 fügte
     ``beendet`` hinzu) stehen in ``models/chat.py`` als ``VORSCHLAG_STAENDE``.
     Deshalb braucht CHAT-7b-2 hier KEIN DDL: der partielle Index fragt nur
     ``stand = 'offen'``, und ``beendet`` verhält sich wie jeder andere
     Nicht-``offen``-Wert (kein neuer offener Vorschlag wird blockiert).
     Geprüft: PG 17, up/down/up auf einem Wegwerf-Container.

Die Runden selbst brauchen KEINEN DDL-Schritt: ``chat_gespraech`` trägt die
Art bereits als Text, ``gruppe`` ist seit CHAT-7a nullable (``art = 'runde'``
braucht genau wie ``art = 'direkt'`` keine Gruppe) und ``titel`` ist die
vorhandene Spalte für den Rundennamen. ``uq_chat_gespraech_einheit`` greift
bei Runden nicht (er ist auf ``gruppe`` beschränkt, das bei einer Runde NULL
ist), und ``uq_chat_gespraech_paar`` gilt nur für ``art = 'direkt'``: mehrere
Runden derselben Personen sind ausdrücklich erlaubt.

Revision-Kette: Kopf beim Schreiben war ``chat4b_umfrage_erinnerung`` —
geprüft über ``alembic/versions/*.py`` (alle ``revision``/``down_revision``-
Paare ausgewertet, NICHT angenommen). Der neue Kopf ist diese Revision; es
gibt weiterhin genau EINEN.

Idempotent: jede Änderung prüft zuerst den Ist-Zustand (Tabelle vorhanden?
Spalte vorhanden? Index vorhanden?). Ein zweiter Lauf ändert sachlich nichts.
``downgrade`` entfernt die drei Dinge wieder — laut und früh, wenn Runden
oder Sperren existieren (sie wären danach nicht mehr lesbar bzw. wirkungslos):
eine stille Datenvernichtung gibt es hier nicht.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat7b_runden"
down_revision: Union[str, None] = "chat4b_umfrage_erinnerung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPERRE = "rechte_kontaktsperre"
VORSCHLAG = "chat_runde_vorschlag"
TEILNEHMER = "chat_teilnehmer"
GESPRAECH = "chat_gespraech"
NACHRICHT = "chat_nachricht"
SPALTE_VORSCHLAG = "vorschlag"
SPALTE_VERLASSEN = "verlassen_am"
SPALTE_SICHTBAR = "sichtbar_ab"

INDEX_SPERRE_UNIQUE = "uq_rechte_kontaktsperre"
INDEX_SPERRE_GESPERRT = "ix_rechte_kontaktsperre_gesperrt"
INDEX_VORSCHLAG_UNIQUE = "uq_chat_runde_vorschlag_offen"
INDEX_VORSCHLAG_GESPRAECH = "ix_chat_runde_vorschlag_gespraech"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _spalten(tabelle: str) -> set[str]:
    return {str(c["name"]) for c in sa.inspect(op.get_bind()).get_columns(tabelle)}


def _indizes(tabelle: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    # 1) Kontaktsperre — eine Zeile je Richtung, beide Richtungen wirken im
    #    Rechte-Kern (darf_direktnachricht). Kein FK auf `user`: die Spalten
    #    tragen Login-Namen wie die übrigen Rechte-Tabellen auch (dort steht
    #    `benutzer` in `rechte_gruppenrolle` ebenfalls als Text).
    if not _tabelle_existiert(SPERRE):
        op.create_table(
            SPERRE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("gesperrt", sa.String(length=140), nullable=False),
            sa.Column("angelegt_am", sa.DateTime(), nullable=True),
        )
    indizes = _indizes(SPERRE) if _tabelle_existiert(SPERRE) else set()
    if INDEX_SPERRE_UNIQUE not in indizes:
        op.create_index(INDEX_SPERRE_UNIQUE, SPERRE, ["benutzer", "gesperrt"],
                        unique=True)
    if INDEX_SPERRE_GESPERRT not in indizes:
        op.create_index(INDEX_SPERRE_GESPERRT, SPERRE, ["gesperrt"])

    # 2) `chat_teilnehmer.verlassen_am` — Austritt aus einer Runde, ohne die
    #    Zeile (und damit die Person) zu löschen.
    if _tabelle_existiert(TEILNEHMER):
        vorhandene = _spalten(TEILNEHMER)
        if SPALTE_VERLASSEN not in vorhandene:
            op.add_column(TEILNEHMER,
                          sa.Column(SPALTE_VERLASSEN, sa.DateTime(), nullable=True))
        # Sichtbarkeit des Verlaufs (Review R1/SOLL 7): ab wann liest diese
        # Person mit? Beim ersten Beitritt die Beitrittszeit, nach einem
        # Austritt die des Wiedereintritts. NULL = von Anfang an (Bestand).
        if SPALTE_SICHTBAR not in vorhandene:
            op.add_column(TEILNEHMER,
                          sa.Column(SPALTE_SICHTBAR, sa.DateTime(), nullable=True))

    # 3) Vorschläge der Runde. `gespraech` und die beiden Konten-Spalten sind
    #    echte Fremdschlüssel (eine tote Kennung wäre ein Vorgang ohne Ziel);
    #    `mitglied` ist eine Mitglied-Kennung OHNE FK — dieselbe Form wie
    #    `chat_nachricht.autor` (die Anonymisierung räumt die Zeile ab).
    if not _tabelle_existiert(VORSCHLAG):
        op.create_table(
            VORSCHLAG,
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("gespraech", sa.String(length=140),
                      sa.ForeignKey("chat_gespraech.name"), nullable=False),
            sa.Column("vorgeschlagen_von", sa.String(length=140),
                      sa.ForeignKey("user.name"), nullable=True),
            sa.Column("mitglied", sa.String(length=140), nullable=False),
            sa.Column("stand", sa.String(length=20), nullable=False,
                      server_default=sa.text("'offen'")),
            sa.Column("zustimmende", sa.Text(), nullable=False,
                      server_default=sa.text("''")),
            sa.Column("entschieden_von", sa.String(length=140),
                      sa.ForeignKey("user.name"), nullable=True),
            sa.Column("entschieden_am", sa.DateTime(), nullable=True),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
        )
    indizes = _indizes(VORSCHLAG) if _tabelle_existiert(VORSCHLAG) else set()
    if INDEX_VORSCHLAG_UNIQUE not in indizes:
        op.create_index(INDEX_VORSCHLAG_UNIQUE, VORSCHLAG, ["gespraech", "mitglied"],
                        unique=True,
                        postgresql_where=sa.text("stand = 'offen'"),
                        sqlite_where=sa.text("stand = 'offen'"))
    if INDEX_VORSCHLAG_GESPRAECH not in indizes:
        op.create_index(INDEX_VORSCHLAG_GESPRAECH, VORSCHLAG,
                        ["gespraech", "stand"])

    # 3b) `chat_nachricht.vorschlag` — die Vorschlags-Systemzeile ist ein
    #     VERWEIS auf `chat_runde_vorschlag` (Review R1, SOLL 8), keine Kopie
    #     des Satzes: der Text entsteht beim Lesen. FK auf die Vorschlagszeile,
    #     damit eine gelöschte Vorschlagszeile keine tote Kennung hinterlässt.
    #     Nullable OHNE `server_default`: jede Bestandszeile ist eine normale
    #     Nachricht.
    if _tabelle_existiert(NACHRICHT) and SPALTE_VORSCHLAG not in _spalten(NACHRICHT):
        # SQLite kann keinen FK nachträglich an eine bestehende Tabelle hängen
        # (``ALTER ... ADD CONSTRAINT``); der Batch-Modus baut die Tabelle um
        # und kann es. PostgreSQL macht es direkt.
        if op.get_context().dialect.name == "sqlite":
            with op.batch_alter_table(NACHRICHT) as batch:
                batch.add_column(sa.Column(SPALTE_VORSCHLAG, sa.String(length=140),
                                           nullable=True))
                batch.create_foreign_key("fk_chat_nachricht_vorschlag", VORSCHLAG,
                                         [SPALTE_VORSCHLAG], ["name"])
        else:
            op.add_column(NACHRICHT, sa.Column(SPALTE_VORSCHLAG,
                                               sa.String(length=140), nullable=True))
            op.create_foreign_key("fk_chat_nachricht_vorschlag", NACHRICHT, VORSCHLAG,
                                  [SPALTE_VORSCHLAG], ["name"])


def downgrade() -> None:
    # ZUERST prüfen, DANN anfassen: scheitert die Prüfung, ist nichts
    # zurückgerollt — eine halb abgebaute Migration wäre schlimmer als eine,
    # die gar nicht erst beginnt.
    if _tabelle_existiert(VORSCHLAG):
        anzahl = op.get_bind().execute(
            sa.text(f"SELECT count(*) FROM {VORSCHLAG}")
        ).scalar_one()
        if anzahl:
            raise RuntimeError(
                "Rücknahme nicht möglich: es gibt Vorschläge in Runden "
                f"({anzahl} Zeile(n)). Erst leeren, dann downgrade."
            )
    if _tabelle_existiert(SPERRE):
        anzahl = op.get_bind().execute(
            sa.text(f"SELECT count(*) FROM {SPERRE}")
        ).scalar_one()
        if anzahl:
            raise RuntimeError(
                "Rücknahme nicht möglich: es gibt Kontaktsperren "
                f"({anzahl} Zeile(n)). Erst leeren, dann downgrade."
            )
    # Review R1 (SOLL 12): auch vorhandene RUNDEN halten die Rücknahme auf. Nach
    # dem Abbau gäbe es `verlassen_am`/`sichtbar_ab` und die Vorschlags-Tabelle
    # nicht mehr — eine bestehende Runde verlöre ihren Austritt, ihre
    # Sichtbarkeitsgrenze und ihre offenen Vorschläge, ohne dass es jemand
    # merkte. `art = 'runde'` schreibt kein DDL (die Art ist Text), also ist
    # DAS die einzige Stelle, an der die Rücknahme es bemerken kann.
    if _tabelle_existiert(GESPRAECH) and "art" in _spalten(GESPRAECH):
        anzahl = op.get_bind().execute(
            sa.text(f"SELECT count(*) FROM {GESPRAECH} WHERE art = 'runde'")
        ).scalar_one()
        if anzahl:
            raise RuntimeError(
                "Rücknahme nicht möglich: es gibt Runden "
                f"({anzahl} Zeile(n) mit art = 'runde'). Erst entfernen, dann downgrade."
            )

    if _tabelle_existiert(NACHRICHT) and SPALTE_VORSCHLAG in _spalten(NACHRICHT):
        # ERST die Nachrichtenspalte (sie zeigt auf den Vorschlag), dann die
        # Vorschlags-Tabelle. Der Constraint-Name ist nur auf PostgreSQL
        # gesetzt; SQLite baut die Spalte in einem Tabellenumbau ab und kennt
        # ihn nicht (deshalb kein ``drop_constraint``).
        with op.batch_alter_table(NACHRICHT) as batch:
            batch.drop_column(SPALTE_VORSCHLAG)

    if _tabelle_existiert(VORSCHLAG):
        indizes = _indizes(VORSCHLAG)
        for name in (INDEX_VORSCHLAG_UNIQUE, INDEX_VORSCHLAG_GESPRAECH):
            if name in indizes:
                op.drop_index(name, table_name=VORSCHLAG)
        op.drop_table(VORSCHLAG)

    if _tabelle_existiert(SPERRE):
        indizes = _indizes(SPERRE)
        for name in (INDEX_SPERRE_UNIQUE, INDEX_SPERRE_GESPERRT):
            if name in indizes:
                op.drop_index(name, table_name=SPERRE)
        op.drop_table(SPERRE)

    if _tabelle_existiert(TEILNEHMER):
        vorhandene = _spalten(TEILNEHMER)
        for spalte in (SPALTE_VERLASSEN, SPALTE_SICHTBAR):
            if spalte in vorhandene:
                with op.batch_alter_table(TEILNEHMER) as batch:
                    batch.drop_column(spalte)
