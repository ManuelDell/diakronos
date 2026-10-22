"""N9: Gemeinde- und Datenschutz-Einstellungen (Handmodell, kein Frappe-DocType).

Der Gemeindename und die Modul-Sichtbarkeit liegen weiter in der portierten
Frappe-Single ``diakronos_einstellungen`` (models/diakronos.py) — dort schreibt
der Endpunkt ``gemeinde_speichern`` nur die vorhandenen Spalten.

Alles, was es in der Frappe-Vorlage NICHT gab (Kontakt-E-Mail, öffentliche
Adresse, Willkommenstext, Standardwerte für neue Registrierungslinks und die
pflegbaren Datenschutz-/Einwilligungstexte), bekommt hier bewusst eigene
Single-Zeilen-Tabellen. So bleibt das generierte Modell unangetastet und das
neue Zeug klar abgegrenzt — dasselbe Vorgehen wie bei ``datenschutz.py`` und
``passwortzugang.py``.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

# Feste Namen der Single-Zeilen (wie ``ANMELDEEINSTELLUNGEN_NAME``).
GEMEINDE_EINSTELLUNGEN_NAME = "Gemeinde Einstellungen"
DATENSCHUTZ_TEXT_NAME = "Datenschutz Texte"
# N9b (M-2): eigene Single-Zeile fuer die VEROEFFENTLICHTE Fassung. Der
# bearbeitbare Entwurf liegt in ``datenschutz_text``; erst das Speichern mit
# Haken kopiert ihn hierher. Nur aus dieser Zeile liest die oeffentliche Seite
# ihren Wortlaut — so vernichtet ein unveroeffentlichter Entwurf nie den
# geltenden Text (Art. 7 DSGVO: angezeigt == belegt).
DATENSCHUTZ_VEROEFFENTLICHT_NAME = "Datenschutz Texte veroeffentlicht"

# Laufzeit und Platzzahl, die ein neuer Registrierungs-Link vorschlägt, wenn
# der Administrator nichts anderes wählt. Sie sind nur Vorschläge — die Link-
# Karte in „Mitglieder → Anfragen“ darf weiter abweichen.
STANDARD_LAUFZEIT_TAGE = 30
STANDARD_MAX_ANMELDUNGEN = 0  # 0 = ohne Limit


class GemeindeEinstellungen(Base):
    """Single-Zeile: Kontakt, öffentliche Adresse, Willkommenstext, Link-Vorgaben."""

    __tablename__ = "gemeinde_einstellungen"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    kontakt_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oeffentliche_adresse: Mapped[str | None] = mapped_column(String(255), nullable=True)
    willkommenstext: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_laufzeit_tage: Mapped[int] = mapped_column(
        Integer, nullable=False, default=STANDARD_LAUFZEIT_TAGE,
        server_default=str(STANDARD_LAUFZEIT_TAGE),
    )
    link_max_anmeldungen: Mapped[int] = mapped_column(
        Integer, nullable=False, default=STANDARD_MAX_ANMELDUNGEN,
        server_default=str(STANDARD_MAX_ANMELDUNGEN),
    )
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class DatenschutzText(Base):
    """Single-Zeile: der bearbeitbare ENTWURF der Einwilligungs-/Datenschutztexte.

    ``aufbewahrung``, ``datenschutzerklaerung`` und ``einwilligung`` sind
    Freitexte. ``version`` zählt jede inhaltliche Änderung des Entwurfs hoch.
    ``veroeffentlicht`` ist nur ein Merker, was zuletzt veroeffentlicht wurde —
    die geltende Fassung steht in ``DatenschutzTextVeroeffentlicht``.
    """

    __tablename__ = "datenschutz_text"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    einwilligung: Mapped[str | None] = mapped_column(Text, nullable=True)
    datenschutzerklaerung: Mapped[str | None] = mapped_column(Text, nullable=True)
    aufbewahrung: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    veroeffentlicht: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)


class DatenschutzTextVeroeffentlicht(Base):
    """Single-Zeile: die VEROEFFENTLICHTE Fassung (M-2).

    Wird ausschliesslich beim Speichern mit Haken aus dem Entwurf kopiert und
    ist die einzige Quelle fuer die oeffentliche Registrierungsseite und den
    Einwilligungs-Beleg (``dsgvo_text_snapshot``). ``version`` ist die Fassung
    dieser veroeffentlichten Fassung.
    """

    __tablename__ = "datenschutz_text_veroeffentlicht"

    name: Mapped[str] = mapped_column(String(140), primary_key=True)
    einwilligung: Mapped[str | None] = mapped_column(Text, nullable=True)
    datenschutzerklaerung: Mapped[str | None] = mapped_column(Text, nullable=True)
    aufbewahrung: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(140), nullable=True)
