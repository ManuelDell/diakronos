"""CHAT-7a: Direktgespräche 1:1 — ``chat_gespraech`` wird paar-fähig.

Revision ID: chat7a_direkt
Revises: chat8_fristen
Create Date: 2026-11-19

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S3 (Zeilen ~100–122), 2.4, 2.5, 3.3,
10.1 Punkt 4 („Nachricht schreiben legt das 1:1-Gespräch an ODER setzt das
vorhandene fort — nie ein zweites Gespräch je Personenpaar“). Karte CHAT-7a.

GEÄNDERT WIRD NUR ``chat_gespraech`` — kein neues Tabellenpaar:

  * ``gruppe`` wird NULLABLE. Ein Direktgespräch hat keine Gruppe; der Raum
    sind die Teilnehmenden (``chat_teilnehmer``). Bestandszeilen bleiben
    unangetastet (sie tragen weiter ihren Gruppennamen), der ``NOT NULL``
    fällt ohne Datenverlust — ``ALTER COLUMN … DROP NOT NULL`` prüft die
    vorhandenen Werte und lässt sie stehen.
  * ``paar_schluessel`` kommt NEU hinzu: das sortierte Kontenpaar
    (``kleineres\x1fgroesseres`` — PostgreSQL-Text verbietet NUL), nur bei
    ``art = 'direkt'`` gesetzt. Nullable
    ohne ``server_default``: jede Bestandszeile ist ein Gruppen-Gespräch und
    trägt NULL (Bestandsdaten damit sicher, kein Rewrite).
  * ``uq_chat_gespraech_einheit`` wird auf ``untergruppe IS NULL AND
    paar_schluessel IS NULL`` verengt (drop + create): sonst kollidierten
    alle Direktgespräche, denn ihre ``gruppe`` ist NULL. Die Regel „ein
    Gespräch je Einheit“ bleibt für Gruppe/Untergruppe wortgleich.
  * ``uq_chat_gespraech_paar`` kommt NEU dazu: EIN Gespräch je Personenpaar,
    partiell auf ``art = 'direkt'``.

Revision-Kette: Kopf beim Schreiben war ``chat5_umfrage``, nach dem Nachziehen
von ``main`` (CHAT-4a) ``chat4a_glocke`` und nach dem zweiten Nachziehen
(CHAT-8) ``chat8_fristen`` — geprüft über ``alembic/versions/*.py`` (alle
``revision``/``down_revision``-Paare ausgewertet, NICHT angenommen). Der neue
Kopf ist diese Revision.

Idempotent: jede Änderung prüft zuerst den Ist-Zustand (Spalte/Nullable,
Indexnamen, Indexdefinition). Ein zweiter Lauf ändert SACHlich nichts, er
legt die Indizes aber neu an (``drop`` + ``create`` für
``uq_chat_gespraech_einheit``) — das ist Absicht: das Prädikat muss stimmen,
und ein Vergleich der Teil-Prädikate ist je Dialekt unzuverlässig. Inhalt
und Daten bleiben unberührt.

``downgrade`` stellt exakt den Stand des vorherigen Kopfes (``chat8_fristen``)
wieder her. Die Prüfung „gibt es Direktgespräche?“ steht VOR dem ersten
Index-Drop: scheitert sie, ist noch nichts angefasst (eine halb zurückgerollte
Migration wäre schlimmer als eine, die gar nicht erst beginnt). Sie schlägt
laut fehl, wenn inzwischen Direktgespräche existieren (deren ``gruppe = NULL``
könnte der alte ``NOT NULL`` nicht halten); das ist Absicht, keine stille
Datenvernichtung.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat7a_direkt"
down_revision: Union[str, None] = "chat8_fristen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "chat_gespraech"
INDEX_EINHEIT = "uq_chat_gespraech_einheit"
INDEX_PAAR = "uq_chat_gespraech_paar"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _spalten() -> dict[str, dict]:
    return {str(s["name"]): s for s in sa.inspect(op.get_bind()).get_columns(TABELLE)}


def _index_defs() -> dict[str, str]:
    """``{indexname: definition}`` — roh aus dem Katalog, dialektneutral gelesen.

    ``sa.inspect(...).get_indexes`` liefert das PARTIELLE Prädikat je Dialekt
    unterschiedlich (SQLite gar nicht). Für die Idempotenz genügt der Name
    PLUS die Spaltenliste; für die Formprüfung im PG-Lauf liest der Test
    ``pg_indexes`` selbst.
    """
    insp = sa.inspect(op.get_bind())
    return {str(i["name"]): ",".join(str(c) for c in i.get("column_names") or ())
            for i in insp.get_indexes(TABELLE)}


def upgrade() -> None:
    if not _tabelle_existiert(TABELLE):
        return

    spalten = _spalten()
    # 1) `gruppe` nullable — Direktgespräche haben keine Gruppe.
    if "gruppe" in spalten and not spalten["gruppe"].get("nullable", True):
        with op.batch_alter_table(TABELLE) as batch:
            batch.alter_column("gruppe", existing_type=sa.String(length=140),
                               nullable=True)

    # 2) `paar_schluessel` neu (nullable, ohne server_default).
    if "paar_schluessel" not in spalten:
        with op.batch_alter_table(TABELLE) as batch:
            batch.add_column(sa.Column("paar_schluessel", sa.String(length=300),
                                       nullable=True))

    # 3) Der Einheits-Index darf Direktgespräche nicht mehr erfassen.
    indizes = _index_defs()
    einheit_bedingung = "untergruppe IS NULL AND paar_schluessel IS NULL"
    if INDEX_EINHEIT in indizes:
        op.drop_index(INDEX_EINHEIT, table_name=TABELLE)
    op.create_index(
        INDEX_EINHEIT, TABELLE, ["art", "gruppe"], unique=True,
        postgresql_where=sa.text(einheit_bedingung),
        sqlite_where=sa.text(einheit_bedingung),
    )

    # 4) EIN Gespräch je Personenpaar — nur für `art = 'direkt'`.
    if INDEX_PAAR not in _index_defs():
        op.create_index(
            INDEX_PAAR, TABELLE, ["paar_schluessel"], unique=True,
            postgresql_where=sa.text("art = 'direkt'"),
            sqlite_where=sa.text("art = 'direkt'"),
        )


def downgrade() -> None:
    if not _tabelle_existiert(TABELLE):
        return

    # Prüfung ZUERST — vor dem ersten Drop. Scheitert sie, ist nichts
    # angefasst; eine halb zurückgerollte Migration wäre schlimmer als eine,
    # die gar nicht erst beginnt.
    # Zurück auf den Stand von chat8_fristen: der Einheits-Index gilt wieder
    # ohne die Paar-Ausnahme. Das geht nur, solange es KEINE Direktgespräche
    # gibt — sonst blieben mehrere Zeilen mit `gruppe IS NULL` an derselben
    # Einheit, und der Unique-Index verweigert die Anlage. Lieber ein lauter
    # Fehler als ein stiller Datenverlust.
    anzahl_direkt = op.get_bind().execute(
        sa.text("SELECT count(*) FROM chat_gespraech WHERE art = 'direkt'")
    ).scalar_one()
    if anzahl_direkt:
        raise RuntimeError(
            "Rücknahme nicht möglich: es gibt Direktgespräche "
            f"({anzahl_direkt} Zeile(n)). Erst leeren, dann downgrade."
        )

    indizes = _index_defs()
    if INDEX_PAAR in indizes:
        op.drop_index(INDEX_PAAR, table_name=TABELLE)

    if INDEX_EINHEIT in indizes:
        op.drop_index(INDEX_EINHEIT, table_name=TABELLE)
    op.create_index(
        INDEX_EINHEIT, TABELLE, ["art", "gruppe"], unique=True,
        postgresql_where=sa.text("untergruppe IS NULL"),
        sqlite_where=sa.text("untergruppe IS NULL"),
    )

    spalten = _spalten()
    if "paar_schluessel" in spalten:
        with op.batch_alter_table(TABELLE) as batch:
            batch.drop_column("paar_schluessel")
    if "gruppe" in spalten and spalten["gruppe"].get("nullable", True):
        with op.batch_alter_table(TABELLE) as batch:
            batch.alter_column("gruppe", existing_type=sa.String(length=140),
                               nullable=False)
