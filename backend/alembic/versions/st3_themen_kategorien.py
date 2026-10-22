"""ST3: Themen-Vereinheitlichung — pr_merkmal_wert-Werte 'thema' auf Kategorien

Revision ID: st3_themen_kategorien
Revises: st2_lied_material
Create Date: 2026-10-09

ST3 vereinheitlicht die beiden Themen-Systeme: Plan-Merkmal ``thema`` der
Liste ``lieder`` UND die Psalmos-Liedkategorien (``liedkategorie`` +
``lied_kategorie``). Ab jetzt ist fuer Merkmale mit ``quelle='psalmos.kategorie'``
die Psalmos-Kategorie die EINE Wahrheit (Lese- und Pfadweg in
``planrahmen/datenquelle_db.py`` / ``planrahmen/dienste.py``).

Diese Migration uebernimmt die bestehenden Werte: fuer jedes Merkmal
``ziel='sammlung:lieder'``, ``schluessel='thema'`` werden die Werte der
vorhandenen ``pr_merkmal_wert``-Zeilen (skalarer String oder Liste) je Lied in
``lied_kategorie`` abgebildet. Fehlende Kategorien werden im Katalog
``liedkategorie`` angelegt (mit einer frischen UUID als ``name``, weil der
Katalog ueber den Anzeigenamen ``kategoriename`` angesprochen wird).

Bewusst NICHT loeschend: die alten ``pr_merkmal_wert``-Zeilen bleiben stehen
(Sicherheitsnetz; der Lese-Weg ignoriert sie fuer Kategorie-Merkmale ohnehin).
"""

from __future__ import annotations

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "st3_themen_kategorien"
down_revision: Union[str, None] = "st2_lied_material"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _werte(roh: object) -> list[str]:
    """Merkmalswert zu einer Liste nicht-leerer Strings normalisieren."""
    if isinstance(roh, str):
        try:
            geladen = json.loads(roh)
        except (TypeError, ValueError):
            geladen = roh
    else:
        geladen = roh
    if isinstance(geladen, list):
        kandidaten = geladen
    else:
        kandidaten = [geladen]
    return [str(w).strip() for w in kandidaten if isinstance(w, (str, int, float)) and str(w).strip()]


def upgrade() -> None:
    bind = op.get_bind()
    # Alle thema-Werte der eingebauten Lied-Sammlung lesen.
    zeilen = bind.execute(sa.text(
        "SELECT mw.ziel_id AS lied, mw.wert AS wert "
        "FROM pr_merkmal_wert mw "
        "JOIN pr_merkmal m ON mw.merkmal = m.id "
        "WHERE m.ziel = 'sammlung:lieder' AND m.schluessel = 'thema'")).fetchall()

    vorhandene_kat: dict[str, str] = {}
    for kategorie, in bind.execute(sa.text(
            "SELECT kategoriename FROM liedkategorie WHERE kategoriename IS NOT NULL")).fetchall():
        vorhandene_kat[kategorie] = kategorie

    def katalog_id(name: str) -> str:
        """Kennung der Kategorie im Katalog; legt sie bei Bedarf an."""
        if name in vorhandene_kat:
            return vorhandene_kat[name]
        neu = str(uuid.uuid4())
        bind.execute(sa.text(
            "INSERT INTO liedkategorie (name, kategoriename, docstatus, idx) "
            "VALUES (:n, :k, 0, 0)"), {"n": neu, "k": name})
        vorhandene_kat[name] = neu
        return neu

    for lied, wert in zeilen:
        for kategorie in _werte(wert):
            kat_id = katalog_id(kategorie)
            vorhanden = bind.execute(sa.text(
                "SELECT name FROM lied_kategorie WHERE parent = :p "
                "AND parentfield = 'kategorien' AND kategorie = :k"),
                {"p": lied, "k": kat_id}).first()
            if vorhanden is None:
                bind.execute(sa.text(
                    "INSERT INTO lied_kategorie (name, parent, parenttype, parentfield, docstatus, idx, kategorie) "
                    "VALUES (:n, :p, 'Lied', 'kategorien', 0, 0, :k)"),
                    {"n": f"{lied}-st3-{uuid.uuid4().hex[:6]}", "p": lied, "k": kat_id})


def downgrade() -> None:
    """Nichts zuruecknehmen: die Zuordnungen bleiben nutzbar (idempotent)."""
    pass
