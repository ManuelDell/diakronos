"""Plan-Rahmen — SQLAlchemy-Modelle.

Dieses Modul ist Teil des **generischen** Plan-Rahmens (Konzept:
`backend/src/diakronos_app/planrahmen/doku/KONZEPT.md`):
wenige, frei kombinierbare Bausteine (Plantyp, Plan, Termin, Eintrag, Feld,
Rolle, Merkmal, Sammlung, Regel, Verlauf), aus denen beliebige Gemeinde-Pläne
(Chorplan, Freizeitplan, Predigerplan …) gebaut werden — ohne eigenen Code pro
Planart.

Anders als die übrigen Modelle unter `diakronos_app/models/` sind diese
Tabellen **NICHT** von `tools/gen_models.py` erzeugt und deshalb auch **NICHT**
über den Frappe-Resource-CRUD (`/api/resource/<doctype>`) erreichbar. Sie werden
handgepflegt und in `models/__init__.py` registriert, tauchen aber bewusst nicht
in `models/_mapping.json` auf; zusätzlich sperrt
`frappe_compat/router.py::_private_resource_denied` die generischen
Resource-Endpunkte für diese Tabellen.

Namenskonvention: Tabellenpräfix `pr_`, Primärschlüssel als String-UUID,
Zeitstempel `created`/`modified`, Erfasser `created_by`.

JSON-Spalten sind `JSONB` auf PostgreSQL und fallen für die In-Memory-SQLite
der Testsuite (siehe `tests/conftest.py`, `Base.metadata.create_all` auf SQLite)
auf generisches `JSON` zurück. Die Migration legt auf PostgreSQL echtes JSONB an.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

if TYPE_CHECKING:
    from diakronos_app.models.diakonos import Mitglied


def _jsonb() -> Any:
    """JSONB auf PostgreSQL, generisches JSON sonst (SQLite-Testsuite)."""
    return JSON().with_variant(JSONB(), "postgresql")


def neue_uuid() -> str:
    """Liefert eine frische String-UUID (Primärschlüssel der pr_*-Tabellen)."""
    return str(uuid.uuid4())


class Plantyp(Base):
    """Wiederverwendbarer Plantyp (Vorlage), z. B. „Chorplan“, „Freizeitplan“.

    Beschreibt die *Struktur* (P2), nicht die Einträge. Die konkrete Definition
    liegt versioniert in :class:`PlantypVersion`.
    """

    __tablename__ = "pr_plantyp"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    schluessel: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    bereich: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("dienstbereich.name", ondelete="SET NULL"), nullable=True
    )
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class PlantypVersion(Base):
    """Versionierte Definition eines Plantyps (P4).

    Versionen sind **unveränderlich** nach Anlage: sie werden nie geändert,
    sondern ersetzt (neue Version mit höherer `versionsnummer`). Die Einhaltung
    erzwingt das Repository in `planrahmen/speicher.py`; die neue Version bleibt
    als Datensatz erhalten, damit vergangene Termine ihre Struktur behalten.
    """

    __tablename__ = "pr_plantyp_version"
    __table_args__ = (
        UniqueConstraint("plantyp", "versionsnummer", name="uq_pr_plantyp_version_plantyp_nr"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    plantyp: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_plantyp.id", ondelete="CASCADE"), nullable=False, index=True
    )
    versionsnummer: Mapped[int] = mapped_column(Integer, nullable=False)
    gueltig_ab: Mapped[date] = mapped_column(Date, nullable=False)
    definition: Mapped[dict | list | Any] = mapped_column(_jsonb(), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="1")
    erstellt_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    kommentar: Mapped[str | None] = mapped_column(Text, nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Plan(Base):
    """Instanz eines Plantyps für einen Zeitraum („Chorplan 2026“).

    `veroeffentlichter_stand` (P4/PR4) hält beim Veröffentlichen den
    eingefrorenen Schnappschuss des Plans: die API liefert Nichtberechtigten
    immer diesen Stand, nicht den Live-Entwurf. Ein versionsbasierter
    Schreibversuch auf einem veröffentlichten Plan setzt den Status auf
    `entwurf` zurück (Dienst-Schicht); unveränderlich bleibt nur die
    Plantyp-Version selbst.
    """

    __tablename__ = "pr_plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    plantyp: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_plantyp.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    titel: Mapped[str] = mapped_column(String(280), nullable=False)
    zeitraum_von: Mapped[date | None] = mapped_column(Date, nullable=True)
    zeitraum_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    parameter: Mapped[dict | list | Any] = mapped_column(_jsonb(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="entwurf")
    # Beim Veroeffentlichen eingefrorener Schnappschuss (bis dahin None).
    veroeffentlichter_stand: Mapped[dict | None] = mapped_column(_jsonb(), nullable=True)
    verantwortlich: Mapped[str | None] = mapped_column(
        String(140), ForeignKey("mitglied.name", ondelete="SET NULL"), nullable=True
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Termin(Base):
    """Ein Termin im Zeitraster eines Plans (B2).

    PR4 ergänzt den Engine-Kontext als echte Spalten (konsistent zu
    `planrahmen/engine/modell.py::Termin`): `reihe` ('standard' für die
    Kurzform), `bezug` (Ursprungstermin einer abgeleiteten Reihe,
    Self-FK, ON DELETE SET NULL), `ablauf` sowie `index`/`positionsnr_im_monat`/
    `position_von_hinten` mit denselben Grundwerten wie das Dataclass-Modell.
    `plantyp_version` ist NOT NULL: der beim Anlegen fixierte Snapshot sichert
    vergangenen Terminen ihre Struktur (unveränderlich, P4).
    """

    __tablename__ = "pr_termin"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    plan: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_plan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    datum: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    uhrzeit: Mapped[time | None] = mapped_column(Time, nullable=True)
    titel: Mapped[str | None] = mapped_column(String(280), nullable=True)
    anlaesse: Mapped[list | Any] = mapped_column(_jsonb(), nullable=False, default=list)
    quelle: Mapped[str] = mapped_column(String(40), nullable=False, default="manuell")
    kronos_element: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # Fixiert beim Anlegen (P4): vergangene Termine behalten ihre Struktur.
    plantyp_version: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_plantyp_version.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Engine-Kontext (PR4): Kennung der Terminreihe ('standard' = Kurzform).
    reihe: Mapped[str] = mapped_column(String(140), nullable=False, default="standard", server_default="standard")
    # Ursprungstermin einer abgeleiteten Reihe (None bei eigenständigen Terminen).
    bezug: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pr_termin.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ablauf: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=False, default=dict, server_default=text("'{}'"))
    index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    positionsnr_im_monat: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    position_von_hinten: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    entfaellt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # OP-EVENT-18: die je Termin gueltige Variante (z. B. 'sonne'/'regen').
    # NULL = es gilt die erste deklarierte Variante (bisheriges Verhalten).
    variante: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Eintrag(Base):
    """Ein geplanter Wert an einem Termin (B3), über `feld_pfad` adressiert."""

    __tablename__ = "pr_eintrag"
    __table_args__ = (
        UniqueConstraint("termin", "feld_pfad", name="uq_pr_eintrag_termin_feld"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    termin: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_termin.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feld_pfad: Mapped[str] = mapped_column(Text, nullable=False)
    index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variante: Mapped[str | None] = mapped_column(String(140), nullable=True)
    wert: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=False)
    fixiert: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quelle: Mapped[str] = mapped_column(String(40), nullable=False, default="manuell")
    meldungen: Mapped[list | Any] = mapped_column(_jsonb(), nullable=False, default=list)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Verlauf(Base):
    """Änderungsverlauf — Grundlage für Undo (P4/B10).

    PR4: `plan` wird für globale Schreibdienste (Plantyp/Merkmal/Abwesenheit
    ohne Planbezug) optional; `plantyp` verweist in diesem Fall auf den
    betroffenen Plantyp (ON DELETE SET NULL — die Verlauf-Zeile bleibt
    stehen). `gruppe_id` ist die Undo-Einheit für ALLE Dienste.
    """

    __tablename__ = "pr_verlauf"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    # None bei globalen Schreibdiensten ohne Planbezug (PR4).
    plan: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pr_plan.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Betroffener Plantyp globaler Dienste (PR4); faellt beim Loeschen aus.
    plantyp: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pr_plantyp.id", ondelete="SET NULL"), nullable=True, index=True
    )
    zeitpunkt: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    benutzer: Mapped[str | None] = mapped_column(String(140), nullable=True)
    aktion: Mapped[str] = mapped_column(String(80), nullable=False)
    vorher: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=True)
    nachher: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=True)
    # Zusammenhängige Änderungen teilen sich eine gruppe_id (Undo-Einheit
    # für alle Dienste — planbezogen wie global).
    gruppe_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Merkmal(Base):
    """Deklarierte Eigenschaft einer Person oder eines Sammlungseintrags (B5).

    Merkmale werden über Pläne hinweg geteilt: der `schluessel` ist eindeutig
    je `ziel`, damit z. B. „klavier“ in jedem Plantyp dieselben Daten sieht.
    """

    __tablename__ = "pr_merkmal"
    __table_args__ = (
        UniqueConstraint("ziel", "schluessel", name="uq_pr_merkmal_ziel_schluessel"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    ziel: Mapped[str] = mapped_column(String(140), nullable=False)  # person | sammlung:<key>
    schluessel: Mapped[str] = mapped_column(String(140), nullable=False)
    art: Mapped[str] = mapped_column(String(40), nullable=False)
    definition: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=False, default=dict)
    angelegt_durch_plantyp: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pr_plantyp.id", ondelete="SET NULL"), nullable=True
    )
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class MerkmalWert(Base):
    """Konkreter Merkmalswert (Person/Sammlungseintrag/Lied → Wert)."""

    __tablename__ = "pr_merkmal_wert"
    __table_args__ = (
        UniqueConstraint("merkmal", "ziel_id", name="uq_pr_merkmal_wert_merkmal_ziel"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    merkmal: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_merkmal.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # mitglied.name, sammlung_eintrag.id oder lied.name.
    ziel_id: Mapped[str] = mapped_column(String(140), nullable=False)
    wert: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Sammlung(Base):
    """Beliebige Liste von Dingen (Lieder, Bibelarbeiten, Spiele …) (B5).

    PR4: Sammlungen haben einen **Umfang** — `gemeinde` (Vorgabe, dauerhaft,
    plannuebergreifend) oder `plan` (gehoert zum einzelnen Plan, wird beim
    Vorbereiten befuellt). Der Konsistenz-Check spiegelt das 1:1:
    `umfang='plan'` genau dann, wenn `plan` gesetzt ist. Der fruehere Unique
    auf `schluessel` wird durch Unique `(schluessel, plan)` plus partiellen
    Unique-Index `schluessel WHERE plan IS NULL` ersetzt.
    """

    __tablename__ = "pr_sammlung"
    __table_args__ = (
        UniqueConstraint("schluessel", "plan", name="uq_pr_sammlung_schluessel_plan"),
        CheckConstraint("umfang IN ('gemeinde', 'plan')", name="ck_pr_sammlung_umfang_werte"),
        CheckConstraint("(umfang = 'plan') = (plan IS NOT NULL)", name="ck_pr_sammlung_umfang_plan"),
        Index(
            "uq_pr_sammlung_schluessel_ohne_plan",
            "schluessel",
            unique=True,
            postgresql_where=text("plan IS NULL"),
            sqlite_where=text("plan IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    schluessel: Mapped[str] = mapped_column(String(140), nullable=False)
    name: Mapped[str] = mapped_column(String(280), nullable=False)
    # 'gemeinde' (Vorgabe) oder 'plan' (gehoert zum einzelnen Plan).
    umfang: Mapped[str] = mapped_column(String(40), nullable=False, default="gemeinde", server_default="gemeinde")
    # Nur bei umfang='plan' gesetzt; ON DELETE CASCADE (PR4).
    plan: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pr_plan.id", ondelete="CASCADE"), nullable=True, index=True
    )
    definition: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=False, default=dict)
    eingebaut: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class SammlungEintrag(Base):
    """Ein Eintrag einer Sammlung (B5)."""

    __tablename__ = "pr_sammlung_eintrag"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    sammlung: Mapped[str] = mapped_column(
        String(36), ForeignKey("pr_sammlung.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daten: Mapped[dict | Any] = mapped_column(_jsonb(), nullable=False, default=dict)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Abwesenheit(Base):
    """Abwesenheit eines Mitglieds in einem Zeitraum (P9/B8)."""

    __tablename__ = "pr_abwesenheit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_uuid)
    mitglied: Mapped[str] = mapped_column(
        String(140), ForeignKey("mitglied.name", ondelete="CASCADE"), nullable=False, index=True
    )
    von: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bis: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    grund: Mapped[str | None] = mapped_column(Text, nullable=True)
    nur_plantyp: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    modified: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


__all__ = [
    "Abwesenheit",
    "Eintrag",
    "Merkmal",
    "MerkmalWert",
    "Plan",
    "Plantyp",
    "PlantypVersion",
    "Sammlung",
    "SammlungEintrag",
    "Termin",
    "Verlauf",
]
