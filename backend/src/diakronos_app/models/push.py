"""CHAT-10a: Web-Push-Abonnements (Handmodell, kein Frappe-DocType).

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 3.2 („Push aufs Handy“) und
die Entscheidung F10: **Web-Push OHNE Inhalt**. Diese Datei legt EINE Tabelle
an:

``push_abonnement``
    EIN Abonnement je Gerät. Ein Gerät ist ein ``endpoint`` des Push-Dienstes
    des Browsers; er ist EINDEUTIG (``uq_push_abonnement_endpoint``) und
    zugleich der Primärschlüssel — derselbe endpoint kann nicht zweimal
    bestehen. Das ist die Regel der Karte: „bei anderem Benutzer: Zeile
    umhängen auf den aktuellen Benutzer — ein Gerät gehört dem, der gerade
    angemeldet ist“. Ein zweiter Primärschlüssel auf ``benutzer`` wäre falsch
    (eine Person hat mehrere Geräte, siehe ``ix_push_abonnement_benutzer``).

``p256dh``/``auth``
    Die beiden Geheimnisse, mit denen der Push-Dienst die Nachricht
    entschlüsselt (Verschlüsselung nach RFC 8291). Sie liegen NUR hier und
    gehen nie in eine Antwort hinaus (die Endpunkte geben kein Abonnement
    aus). ``auth`` ist ein Base64url-Geheimnis, ``p256dh`` ein unkomprimierter
    P-256-Punkt.

``angelegt_am``/``zuletzt_ok_am``/``fehlversuche``
    Buchführung des Versands: ``zuletzt_ok_am`` sagt, wann der Dienst zuletzt
    mit 2xx geantwortet hat, ``fehlversuche`` zählt Fehlschläge in Folge (ab
    ``api.push.MAX_FEHLVERSUCHE`` wird das Abonnement gelöscht). Ein 404/410
    des Dienstes bedeutet „Gerät weg“ und löscht sofort.

DSGVO (Konzept 4.3): die Zeile fällt mit dem Konto — sie ist ein
Verhaltensdatum des Geräts AM KONTO (``ZEILEN_LOESCHEN``/``push_abonnement``).
Ein Push trägt keinen Nachrichteninhalt (Konzept F10); die Zeile enthält
deshalb auch keinen.

Kein FK auf ``user``: eine gelöschte Kontozeile soll die Abonnement-Zeile nicht
per CASCADE mitreißen — die Anonymisierung räumt sie ausdrücklich ab (Schritt
der Person), und ein Versand an ein verwaistes Konto findet ohnehin nicht statt
(der Versand sucht je Konto).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Länge der Push-Endpunkte. Die Dienste (FCM, Mozilla, …) liefern heute um
#: 150–250 Zeichen; 1000 ist die Obergrenze der Karte („Länge begrenzen“) und
#: deckt auch lange Query-Zeichenketten. Ein längerer Wert wird abgewiesen,
#: nicht abgeschnitten: ein abgeschnittener endpoint wäre ein anderes Gerät.
ENDPOINT_MAX = 1000
#: Obergrenze für die beiden Schlüssel (Base64url). 255 ist die Spaltenbreite;
#: ein echter ``p256dh`` hat 87 Zeichen, ein ``auth`` 22.
SCHLUESSEL_MAX = 255
#: Ab so vielen Fehlschlägen IN FOLGE wird das Abonnement gelöscht.
MAX_FEHLVERSUCHE = 5
#: Höchstzahl der Geräte je Konto (Review R1/4). Beim Anlegen eines weiteren
#: Geräts wird das ÄLTESTE (``angelegt_am``) verdrängt; ohne Grenze könnte ein
#: Konto Tabelle und Versandlauf beliebig aufblähen.
MAX_ABOS_JE_KONTO = 10


class PushAbonnement(Base):
    """Ein Web-Push-Abonnement eines Geräts (Konzept 3.2, F10).

    ``endpoint`` ist Primärschlüssel UND eindeutig: dasselbe Gerät kann nicht
    zwei Zeilen haben, und ein Gerätewechsel (andere Person meldet sich auf
    demselben Browser an) ist ein UPDATE der Zeile, kein zweiter Eintrag.
    """

    __tablename__ = "push_abonnement"
    __table_args__ = (
        # „Welche Geräte hat diese Person?“ — EIN Abruf je Versand.
        Index("ix_push_abonnement_benutzer", "benutzer"),
    )

    endpoint: Mapped[str] = mapped_column(String(ENDPOINT_MAX), primary_key=True)
    #: Kontoname (``user.name``). Kein FK — die Zeile fällt über die
    #: Anonymisierung, nicht über einen CASCADE (s. Modul-Docstring).
    benutzer: Mapped[str] = mapped_column(String(140), nullable=False)
    p256dh: Mapped[str] = mapped_column(String(SCHLUESSEL_MAX), nullable=False)
    auth: Mapped[str] = mapped_column(String(SCHLUESSEL_MAX), nullable=False)
    angelegt_am: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    zuletzt_ok_am: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    fehlversuche: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


__all__: list[Any] = [
    "ENDPOINT_MAX",
    "MAX_ABOS_JE_KONTO",
    "MAX_FEHLVERSUCHE",
    "SCHLUESSEL_MAX",
    "PushAbonnement",
]
