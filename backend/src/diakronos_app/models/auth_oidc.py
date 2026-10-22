"""Anmelde-Anbieter (SEC1) — SQLAlchemy-Modelle.

Zwei handgepflegte Tabellen (NICHT von `tools/gen_models.py` erzeugt, nicht
ueber den Frappe-Resource-CRUD erreichbar — siehe
`frappe_compat/router.py::_private_resource_denied`):

1. ``auth_oidc_identitaet`` — stabile Zuordnung eines fremden Kontos
   ``(issuer, sub)`` auf einen Diakronos-Benutzer (`user.name`). Der
   ``sub``-Anspruch eines OIDC-Anbieters ist unveraenderlich; die E-Mail kann
   sich aendern, der ``sub`` nicht. Deshalb ist DIES die Wahrheit der
   Zuordnung, nicht die E-Mail (die nur bei der ERSTzuordnung und nur mit
   ``email_verified=true`` herangezogen wird).

2. ``auth_einstellungen`` — ``Single``-Zeile (eine Zeile, fester Name
   ``Anmeldeeinstellungen``) mit dem KONFIGURIERBAREN Verhalten fuer
   **unbekannte Nutzer** (Default sicher = ``abweisen``) sowie einem
   Kind-Baum ``auth_gruppen_rolle`` fuer die Zuordnung Authentik-Gruppe ->
   Diakronos-Rolle.

Sprache: Deutsch (Bezeichner wie im Betrieb). Zeitstempel ``created``/
``modified``, Erfasser ``created_by`` — dieselbe Konvention wie im Plan-Rahmen.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

__all__ = [
    "Anmeldeeinstellungen",
    "GruppenRolleZuordnung",
    "OidcIdentitaet",
    "ZuordnungsAblehnung",
    "UNBEKANNT_MODI",
    "ANMELDEEINSTELLUNGEN_NAME",
]

# Fester Primaerschluessel der Single-Zeile (Frappe-``Single``-Muster).
ANMELDEEINSTELLUNGEN_NAME = "Anmeldeeinstellungen"

# Zulaessige Modi fuer unbekannte Nutzer. Default ist ``abweisen`` (fail safe).
UNBEKANNT_ABWEISEN = "abweisen"
UNBEKANNT_GAST = "als_gast_anlegen"
UNBEKANNT_ANLEGEN = "anlegen_mit_rollen"
UNBEKANNT_MODI = (UNBEKANNT_ABWEISEN, UNBEKANNT_GAST, UNBEKANNT_ANLEGEN)


def _uuid() -> str:
    """Neuer String-Primaerschluessel (UUID4) fuer handgepflegte Tabellen."""
    return str(uuid.uuid4())


class OidcIdentitaet(Base):
    """Zuordnung ``(issuer, sub)`` -> Diakronos-Benutzer.

    ``issuer`` und ``sub`` zusammen sind eindeutig: derselbe ``sub`` bei zwei
    verschiedenen Anbietern sind zwei verschiedene Menschen.
    """

    __tablename__ = "auth_oidc_identitaet"
    __table_args__ = (
        UniqueConstraint("issuer", "sub", name="uq_auth_oidc_identitaet_issuer_sub"),
        Index("ix_auth_oidc_identitaet_user", "user"),
    )

    name: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    sub: Mapped[str] = mapped_column(String(255), nullable=False)
    # Diakronos-Benutzer (`user.name`). Loeschen des Benutzers loescht die
    # Zuordnung mit (CASCADE) — sonst zeigte sie ins Leere.
    user: Mapped[str] = mapped_column(
        String(140), ForeignKey("user.name", ondelete="CASCADE"), nullable=False
    )
    # Anzeige-/Diagnosefelder, nicht autoritativ.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zuletzt_gesehen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class Anmeldeeinstellungen(Base):
    """``Single``-Zeile: Verhalten bei unbekannten Nutzern (in der DB, nicht ENV)."""

    __tablename__ = "auth_einstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    # Einer aus UNBEKANNT_MODI. Default sicher: abweisen.
    unbekannte_nutzer: Mapped[str] = mapped_column(
        String(40), default=UNBEKANNT_ABWEISEN, nullable=False
    )
    # Nur bei Modus ``anlegen_mit_rollen`` relevant. Administrator-Rolle NIE
    # automatisch ueber Gruppen, ausser dieser Schalter ist ausdruecklich an.
    admin_ueber_gruppen: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Ob OIDC ueberhaupt genutzt werden soll (Anzeige/Diagnose; die wirksame
    # Schaltung ist AUTH_OIDC_ENABLED in der .env).
    aktiv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class ZuordnungsAblehnung(Base):
    """Abgelehnte E-Mail-Zuordnung beim Anbieter-Login (R-N8, Punkt 2).

    Wenn ein Anbieter-Konto ueber eine E-Mail auf eine Person trifft, deren
    Zuordnung nicht eindeutig/verifiziert/freigegeben ist, wird der Login
    abgelehnt (`zuordnung.loese_konto_auf` -> grund ``mitglied_zuordnung``).
    Frueher sah das nur der abgewiesene Mensch; die Verwaltung erfuhr nichts.
    Diese Zeile macht den Fall unter „wartende Konten“ sichtbar, mit Grund.

    ``(issuer, sub)`` ist eindeutig: derselbe Anbieter-Account erzeugt bei
    wiederholten Anmeldungen KEINE neuen Zeilen (upsert), nur ``zuletzt`` und
    ``versuche`` wachsen. Kein Fremdschluessel auf ``user`` — es gibt ja
    gerade keinen Benutzer.
    """

    __tablename__ = "auth_zuordnung_ablehnung"
    __table_args__ = (
        UniqueConstraint("issuer", "sub", name="uq_auth_zuordnung_ablehnung_issuer_sub"),
    )

    name: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    sub: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_anzeige: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Fachlicher Grund (``mitglied_zuordnung`` u. a.) und der Text, den der
    # Mensch zu sehen bekam — die Verwaltung entscheidet damit, was zu tun ist.
    grund: Mapped[str] = mapped_column(String(60), nullable=False)
    meldung: Mapped[str | None] = mapped_column(Text, nullable=True)
    versuche: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    zuletzt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    created: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )


class GruppenRolleZuordnung(Base):
    """Kind-Zeile: Authentik-Gruppe -> Diakronos-Rolle.

    Sortierung ueber ``idx`` (wie die uebrigen Child-Tabellen). ``parent`` zeigt
    auf ``auth_einstellungen.name``.
    """

    __tablename__ = "auth_gruppen_rolle"
    __table_args__ = (
        UniqueConstraint(
            "parent", "gruppe", name="uq_auth_gruppen_rolle_parent_gruppe"
        ),
    )

    name: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    parent: Mapped[str | None] = mapped_column(
        String(140), nullable=True, index=True
    )
    parenttype: Mapped[str | None] = mapped_column(String(140), nullable=True)
    parentfield: Mapped[str | None] = mapped_column(String(140), nullable=True)
    idx: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gruppe: Mapped[str] = mapped_column(String(255), nullable=False)
    rolle: Mapped[str] = mapped_column(String(140), nullable=False)
    created: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


def _unbenutzt(_: Any) -> None:  # pragma: no cover — haelt den Text-Import lebendig
    """Platzhalter, damit `Text` bei kuenftigen Erweiterungen importiert bleibt."""
    _ = Text
