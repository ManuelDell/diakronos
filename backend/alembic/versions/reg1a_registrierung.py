"""REG-1a: Startdatum am Registrierungslink + Bilder am Anmeldeformular.

Revision ID: reg1a_registrierung
Revises: id1_mitglied_kennungen
Create Date: 2026-10-23

Karte REG-1a (Manuel 23.10.), zwei Ergaenzungen — beide nur ADDITIVE Spalten,
keine Datenwanderung:

  1. ``registrierungslink.gueltig_ab`` (DATE, NULL = sofort gueltig) —
     „gueltig ab“ als Gegenstueck zu ``gueltig_bis``. Vor diesem Tag ist der
     Link fuer Besucher nicht nutzbar; die Verwaltung sieht ihn weiter
     (``validate_token`` unterscheidet ueber ``admin=True``).
  2. ``anmeldeformular.bannerbild`` und ``anmeldeformular.hintergrundbild``
     (VARCHAR(140), NULL = kein Bild) — optionale Bilder des Formulars.
     Gespeichert wird der DATEINAME unter ``settings.files_dir``; ausgeliefert
     werden die Bilder ausschliesslich ueber den oeffentlichen Formular-Endpunkt
     (``/public/registrierung/<token>/bild/<rolle>``), nie ueber ``/files/…``.
     Frappe fuehrt an dieser Stelle absolute URLs — der Port speichert bewusst
     nur den Dateinamen (ueberlebt einen Wechsel von Ablage/Host).

Idempotenz (Regel „Migration laeuft bei JEDEM Start“): Vor dem ``ALTER TABLE``
wird geprueft, ob die Spalte schon existiert (``sa.inspect``). Ein zweiter Lauf
aendert damit nichts; das gilt auch fuer Bestands-DBs, in denen eine der
Spalten bereits von Hand angelegt wurde.

``downgrade`` nimmt die drei Spalten wieder weg. Das ist gefahrlos: es gibt
keine Fremdschluessel darauf, und die Bildpfade stehen in derselben Tabelle wie
der Rest des Formulars (kein Verweis von aussen).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "reg1a_registrierung"
down_revision: Union[str, None] = "id1_mitglied_kennungen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (Tabelle, Spalte, Typ) — die vollstaendige Ergaenzung dieser Migration.
NEUE_SPALTEN: tuple[tuple[str, str, sa.types.TypeEngine], ...] = (
    ("registrierungslink", "gueltig_ab", sa.Date()),
    ("anmeldeformular", "bannerbild", sa.String(length=140)),
    ("anmeldeformular", "hintergrundbild", sa.String(length=140)),
)


def _spalten(bind, tabelle: str) -> set[str]:
    """Spaltennamen einer Tabelle — leer, wenn es die Tabelle (noch) nicht gibt."""
    insp = sa.inspect(bind)
    if not insp.has_table(tabelle):
        return set()
    return {c["name"] for c in insp.get_columns(tabelle)}


def upgrade() -> None:
    bind = op.get_bind()
    for tabelle, spalte, typ in NEUE_SPALTEN:
        vorhanden = _spalten(bind, tabelle)
        if not vorhanden:
            # Tabelle fehlt (z. B. Teil-Datenbank) — nichts zu ergaenzen.
            continue
        if spalte in vorhanden:
            continue
        op.add_column(tabelle, sa.Column(spalte, typ, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for tabelle, spalte, _typ in NEUE_SPALTEN:
        if spalte not in _spalten(bind, tabelle):
            continue
        op.drop_column(tabelle, spalte)
