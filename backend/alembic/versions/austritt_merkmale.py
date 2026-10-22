"""AUSTRITT: Merkmale fuer „Austritt / Deaktivieren“ am Mitglied

Revision ID: austritt_merkmale
Revises: sec2_email_eindeutig
Create Date: 2026-10-20

Die Karte AUSTRITT braucht drei neue Spalten an `mitglied`:

  * `austritt_grund`      — Begruendung des Austritts (OPTIONAL in der API,
                            AUSTRITT-b/N1). Sie UNTERSCHEIDET Austritt und
                            Ausschluss NICHT: beide setzen `ausgeschlossen`,
                            und ein Austritt ohne Begruendung laesst dieses Feld
                            leer. Die Unterscheidung traegt der Status
                            („Ausgetreten“) bzw. `austritt_datum`
                            (`personen_anzeige.ist_ausgeschieden`); die API
                            liefert die Art als `austritt.art` aus
                            (AUSTRITT-d/NB3).
  * `austritt_datum`      — das vom Administrator angegebene Austrittsdatum
                            (unabhaengig von `ausgeschlossen_seit`, das der
                            Ausschluss setzt).
  * `vor_austritt_status` — der Status VOR dem Austritt, in den
                            „Reaktivieren“ zurueckfuehrt (A4).
  * `vor_austritt_konto_aktiv` — der Kontozustand (`User.enabled`) je
                            wirksamem Konto VOR dem Austritt (AUSTRITT-c, M1).
                            Ohne ihn schaltete „Reaktivieren“ jedes Konto ein
                            — auch eines, das der Administrator VOR dem
                            Austritt gesperrt hatte. Aufbau als JSON-Objekt
                            „Kontoname -> true/false“: ein Mitglied kann
                            mehrere wirksame Konten haben (user-Link UND
                            eindeutige E-Mail), und ein einzelner Wahrheitswert
                            muesste raten, welches gemeint ist.

Alle vier sind NULL-faehig: bestehende Zeilen bleiben unveraendert, und eine
Person ohne Austritt traegt hier nichts. Es werden KEINE Daten umgeschrieben —
die Migration legt nur Spalten an (keine Datenwanderung; der Punkt
„Datenmigration gegen Betriebs-Dump“ greift daher nicht, der Lauf wird
trotzdem gegen eine Kopie des Betriebs-Dumps geprueft).

Idempotent: `upgrade` und `downgrade` pruefen zuerst, ob die Spalte schon
existiert bzw. noch fehlt.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "austritt_merkmale"
down_revision: Union[str, None] = "sec2_email_eindeutig"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "mitglied"

SPALTENLAENGE_STATUS = 140


def _spalten_vorhanden() -> set[str]:
    """Welche Spalten traegt `mitglied` bereits?"""
    bind = op.get_bind()
    zeilen = bind.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t"
    ), {"t": TABELLE}).scalars().all()
    return {str(z) for z in zeilen}


def _tabelle_vorhanden() -> bool:
    bind = op.get_bind()
    return bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t"
    ), {"t": TABELLE}).first() is not None


def upgrade() -> None:
    if not _tabelle_vorhanden():
        return
    vorhanden = _spalten_vorhanden()
    # Reihenfolge und Typen wie in `models/diakonos.py::Mitglied`.
    # BEWUSST OHNE Spaltenkommentar: die Modelle deklarieren keinen, und
    # `alembic check` meldete den Unterschied sonst dauerhaft als
    # „modify_comment“ (die Erklaerung steht im Docstring und im Code).
    neu = (
        ("austritt_grund", sa.Text()),
        ("austritt_datum", sa.Date()),
        ("vor_austritt_status", sa.String(SPALTENLAENGE_STATUS)),
        # AUSTRITT-c (M1): Kontozustand je Konto VOR dem Austritt.
        ("vor_austritt_konto_aktiv", sa.JSON()),
    )
    for name, typ in neu:
        if name in vorhanden:
            continue
        op.add_column(TABELLE, sa.Column(name, typ, nullable=True))


def downgrade() -> None:
    if not _tabelle_vorhanden():
        return
    vorhanden = _spalten_vorhanden()
    for name in ("vor_austritt_konto_aktiv", "vor_austritt_status",
                 "austritt_datum", "austritt_grund"):
        if name in vorhanden:
            op.drop_column(TABELLE, name)
