"""ON-1/ON-2 — Tabellen der Ersteinrichtung.

Zwei Tabellen, zwei Zwecke
--------------------------
1. :class:`EinrichtungToken` (ON-1) — der EINMAL-Link zum ersten Administrator.
2. :class:`EinrichtungStand` (ON-2) — Stand des Einrichtungs-Assistenten.

Beide standen urspruenglich in je einer eigenen Datei; sie liegen hier
zusammen, weil sie zum selben Vorgang „Einrichtung" gehoeren und die
Migrationen ``on1_einrichtung``/``on2_einrichtung`` beide hierauf zeigen.

ON-1 (``einrichtung_token``)
----------------------------
Bis ON-1 gab es genau EINEN Weg zum ersten Administrator: ``ADMIN_EMAIL`` und
``ADMIN_PASSWORD`` in der ``.env``. Der ist kopflos (gut fuer Automatisierung),
aber fuer eine Gemeinde unsicher: das Passwort steht als Klartext in einer
Datei, und wer die Datei liest, kennt das Adminpasswort.

ON-1 ergaenzt den Weg ueber einen EINMAL-Link: ist die Benutzertabelle leer und
sind die beiden Werte NICHT gesetzt, erzeugt der Start einen Token, gibt ihn auf
stdout aus und legt hier NUR seinen SHA-256-Hash ab. Wer den Link oeffnet, legt
den Administrator selbst an — das Passwort kennt nur er.

Regeln, die dieses Modell traegt
* **Kein Klartext in der DB.** Gespeichert wird ``sha256(token)`` (64 Hex-
  Zeichen). Ein Dump der Datenbank enthaelt damit keinen benutzbaren Link.
* **Hoechstens EINE Zeile.** Der fachliche Zustand ist „es gibt einen
  gueltigen Einrichtungs-Token oder keinen". Ein neuer Token macht den alten
  ungueltig, indem er dieselbe Zeile ueberschreibt.
* **Ablauf ist Pflicht.** ``gueltig_bis`` ist gesetzt; ein Token ohne Ablauf
  waere ein dauerhafter Generalschluessel.
* **Verbraucht = geloescht.** Nach dem Anlegen des Administrators wird die
  Zeile entfernt; es gibt keinen Zustand „verbraucht, aber noch da".

ON-2 (``einrichtung_stand``)
----------------------------
Warum eine EIGENE Single-Zeilen-Tabelle und keine Spalten in
``gemeinde_einstellungen``:

* Der Assistent speichert **Prozess**-Zustand („Schritt uebersprungen“,
  „Assistent abgeschlossen“, „erst am … wieder erinnern“), nicht Fachdaten der
  Gemeinde. Ein ``DELETE``/Neuaufsetzen der Gemeinde-Angaben soll den
  Assistentenstand nicht mitreissen und umgekehrt.
* Die Punkte selbst (Gemeindename, Logo, Kontakt, Mailversand, Module,
  Mitglieder, Kalender) werden bei JEDEM Aufruf aus den echten Daten
  berechnet — hier steht KEIN „erledigt“-Haken, der veralten koennte. Damit
  gilt: was in der Oberflaeche als erledigt erscheint, ist es auch.

Ein Vorbild ist ``passwortzugang.py`` / ``datenschutz.py`` (dieselbe Bauform:
eine Zeile, ``name`` als Primaerschluessel, ``created``/``modified``).

Handmodelle wie ``models/passwortzugang.py`` — kein Frappe-DocType. Angelegt von
den Migrationen ``on1_einrichtung`` und ``on2_einrichtung``.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

# ── ON-1: Einrichtungs-Token ───────────────────────────────────────────────

#: Fester Schluessel der einzigen Zeile. Wie ``SMTP_EINSTELLUNGEN_NAME``: es
#: gibt genau einen Einrichtungs-Token, und der Aufrufer muss ihn nicht suchen.
EINRICHTUNG_TOKEN_NAME = "Ersteinrichtung"


class EinrichtungToken(Base):
    """Hash + Ablauf des Einrichtungslinks (eine Zeile, Name fest)."""

    __tablename__ = "einrichtung_token"
    # ON-1: der Hash ist eindeutig — er ist der Suchschluessel (`SELECT … WHERE
    # token_hash = :digest`). Als TABLE-CONSTRAINT deklariert, weil die
    # Migration sie so anlegt (`create_table`): ein `unique=True` am Feld
    # erzeugte einen INDEX, und `alembic check` meldete dauerhaft
    # „remove_index + add_constraint" (im Rundlauf gegen PostgreSQL gesehen).
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_einrichtung_token_hash"),
    )

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: ``sha256(<Token>)`` als Hex — nie der Token selbst.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: Ablaufzeitpunkt (naive UTC, wie ``passwortzugang.gueltig_bis``).
    gueltig_bis: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    #: Anlagezeitpunkt — nur fuer Betrieb/Diagnose, nie angezeigt.
    angelegt_am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    #: Wie oft ein Link mit diesem Token aufgerufen wurde (Diagnose). Ein
    #: Verbrauch ist es NICHT — gueltig bleibt er bis ``gueltig_bis`` oder bis
    #: ein neuer erzeugt wird.
    aufrufe: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


# ── ON-2: Stand des Assistenten ────────────────────────────────────────────

#: Fester Name der Single-Zeile (wie ``GEMEINDE_EINSTELLUNGEN_NAME``).
EINRICHTUNG_STAND_NAME = "Einrichtung Stand"

#: Die Schritte des Assistenten in Anzeigereihenfolge (Entwurf 04–09).
#: ``fertig`` ist kein Schritt mit eigenem Zustand — er zeigt nur die
#: Checkliste (Frame 09).
SCHRITT_SCHLUESSEL = (
    "gemeinde",
    "kontakt",
    "mailversand",
    "module",
    "mitglieder_kalender",
)

#: Erlaubte Zustaende eines Schritts. ``uebersprungen`` ist NUR hier gespeichert;
#: die Punkte in ``einrichtung.status`` bleiben davon unberuehrt (sie werden
#: aus echten Daten berechnet).
SCHRITT_ZUSTAENDE = ("offen", "erledigt", "uebersprungen")


class EinrichtungStand(Base):
    """Single-Zeile: Assistentenstand und Erinnerung."""

    __tablename__ = "einrichtung_stand"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    assistent_abgeschlossen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: Ein Zustand je Schritt als Spalte (``schritt_gemeinde`` …). Bewusst
    #: Spalten und keine Kindtabelle: die Zahl der Schritte ist fest (Entwurf),
    #: und ein ``status``-Aufruf soll die Zeile ohne Join lesen koennen.
    schritt_gemeinde: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_kontakt: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_mailversand: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_module: Mapped[str | None] = mapped_column(String(20), nullable=True)
    schritt_mitglieder_kalender: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    #: „Spaeter erinnern“: bis zu diesem Tag bleibt die Karte auf der Uebersicht
    #: ausgeblendet. Ein Datum, kein Schalter — es laeuft von selbst ab.
    erinnerung_ab: Mapped[date | None] = mapped_column(Date, nullable=True)
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
