"""LN1: Lied bekommt eine klare QUELLE (Liederbuch / Kopie / ohne Angabe)

Revision ID: ln1_lied_quelle
Revises: st3_themen_kategorien
Create Date: 2026-10-09

LN1 — „Lieder ohne Nummer" (Manuel 2026-10-09: „Lieder brauchen die Option:
hat Nummer? Denn Nr. KOP (Kopie) macht keinen Sinn.").

Die Quelle ist die EINE Wahrheit eines Liedes:
``buch``  = Liederbuch/Heft (Nummer und/oder Seite)
``kopie`` = Kopie/Einzelblatt (lose, KEINE Nummer)
``ohne``  = ohne Angabe

Die Migration

1. ergaenzt die Spalte ``lied.quelle`` (String(140), nullable),
2. zerlegt die bestehenden ``gesangbuch_nummer``-Werte in Buch/Nummer/Seite
   und leitet daraus die Quelle ab (idempotent — ein erneuter Lauf aendert
   nichts, weil bereits migrierte Zeilen an ``quelle`` erkannt werden),
3. sichert den Original-Zeichenketten in ``notiz`` (nur einmal, mit Marker),
   damit **nichts verloren geht**, auch wenn die Zerlegung unsicher war.

Der Parser spiegelt ``diakronos_app.planrahmen.lieder_pflege.zerlege_quelle``
(hier bewusst als eingefrorene Kopie, weil Migrationen nicht von der sich
weiterentwickelnden Anwendung abhaengen duerfen).
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ln1_lied_quelle"
down_revision: Union[str, None] = "st3_themen_kategorien"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Marker im Notizfeld, damit der Originaltext genau einmal gesichert wird.
MARKER = "[LN1 Original-Nummer]"

_KOPIE_WERTE = {"kop", "kopie", "kopien", "einz", "einzelblatt", "blatt"}
_NR = re.compile(r"\bnr\.?\s*([0-9]+[a-zA-Z]?)\b", re.IGNORECASE)
_SEITE = re.compile(r"\bs\.?\s*([0-9]+[a-zA-Z]?)\b", re.IGNORECASE)


def _zerlege(roh: object) -> dict[str, str]:
    """Eingefrorene Kopie von ``lieder_pflege.zerlege_quelle`` (siehe dortige Doku)."""
    text = ("" if roh is None else str(roh)).strip()
    if not text:
        return {"quelle": "ohne", "buch": "", "nummer": "", "seite": ""}
    klein = text.lower()
    if klein in _KOPIE_WERTE:
        return {"quelle": "kopie", "buch": "", "nummer": "", "seite": ""}
    m_nr = _NR.search(text)
    m_seite = _SEITE.search(text)
    if m_nr or m_seite:
        schnitt = min([m.start() for m in (m_nr, m_seite) if m])
        buch = text[:schnitt].strip(" ,;/|-")
        return {
            "quelle": "buch",
            "buch": buch,
            "nummer": m_nr.group(1) if m_nr else "",
            "seite": m_seite.group(1) if m_seite else "",
        }
    if klein in _KOPIE_WERTE or klein.startswith(("kop ", "kopie ")):
        return {"quelle": "kopie", "buch": "", "nummer": "", "seite": ""}
    return {"quelle": "buch", "buch": text, "nummer": "", "seite": ""}


def upgrade() -> None:
    op.add_column("lied", sa.Column("quelle", sa.String(length=140), nullable=True))

    bind = op.get_bind()
    # Nur Zeilen OHNE Quelle migrieren -> idempotent.
    zeilen = bind.execute(sa.text(
        "SELECT name, gesangbuch_nummer, buch, seite, notiz FROM lied "
        "WHERE quelle IS NULL"
    )).mappings().all()

    for zeile in zeilen:
        roh = zeile["gesangbuch_nummer"]
        zerlegt = _zerlege(roh)
        buch = zerlegt["buch"] or (zeile["buch"] or "")
        nummer = zerlegt["nummer"]
        seite = zerlegt["seite"] or (zeile["seite"] or "")
        original = ("" if roh is None else str(roh)).strip()
        notiz = zeile["notiz"] or ""
        # Originaltext sichern, wenn es einen gab und noch kein Marker steht.
        if original and MARKER not in notiz:
            zusatz = f"{MARKER} {original}"
            notiz = f"{notiz}\n{zusatz}".strip() if notiz else zusatz
        bind.execute(sa.text(
            "UPDATE lied SET quelle = :quelle, buch = :buch, "
            "gesangbuch_nummer = :nummer, seite = :seite, notiz = :notiz "
            "WHERE name = :name"
        ), {
            "quelle": zerlegt["quelle"],
            "buch": buch or None,
            "nummer": nummer or None,
            "seite": seite or None,
            "notiz": notiz or None,
            "name": zeile["name"],
        })


def downgrade() -> None:
    """Stellt den Original-Zeichenketten aus der Notiz wieder her, dann Spalte weg.

    Der Zustand vor LN1 entspricht ``gesangbuch_nummer`` = Originaltext,
    ``buch``/``seite`` wie vorher (das Original aus der Notiz ist die einzige
    verlaessliche Quelle), ``quelle`` existiert nicht.
    """
    bind = op.get_bind()
    zeilen = bind.execute(sa.text(
        "SELECT name, gesangbuch_nummer, notiz FROM lied WHERE notiz LIKE :m"
    ), {"m": f"%{MARKER}%"}).mappings().all()

    for zeile in zeilen:
        notiz = zeile["notiz"] or ""
        original = None
        for zeile_text in notiz.splitlines():
            if zeile_text.strip().startswith(MARKER):
                original = zeile_text.strip()[len(MARKER):].strip()
                break
        if original is None:
            continue
        # Markerzeile aus der Notiz entfernen.
        rest = "\n".join(
            z for z in notiz.splitlines() if not z.strip().startswith(MARKER)
        ).strip()
        bind.execute(sa.text(
            "UPDATE lied SET gesangbuch_nummer = :nr, notiz = :notiz WHERE name = :name"
        ), {"nr": original or None, "notiz": rest or None, "name": zeile["name"]})

    op.drop_column("lied", "quelle")
