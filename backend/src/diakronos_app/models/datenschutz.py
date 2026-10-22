"""Löschanträge: ein dauerhafter, idempotenter Vorgang je Person.

DSGVO-1 (Art. 17): Der Antrag ist ein eigener Datensatz und überlebt als
NACHWEIS die Anonymisierung. Deshalb steht hier personenbezogen nur die
technische Mitglied-Kennung (`mitglied`, Primärschlüssel) — genau wie in
`dsgvo_log` und im Audit-Log. Nach der Ausführung trägt die Zeile zusätzlich
`anonymisiert_am`; Name und Mail der Person sind dann nirgends mehr.

NEU in DSGVO-1 (Migration `dsgvo1_loeschantrag_freigabe`):

* `status` — ``offen`` / ``zurueckgezogen`` / ``ausgefuehrt``. Vorher war der
  Zustand aus `erledigt_am` ablesbar; „zurückgezogen“ gab es gar nicht.
* `zurueckgezogen_am` — Zeitpunkt des Widerrufs durch die Person selbst.
* `freigegeben_am` / `freigegeben_von` — wer die Löschung bestätigt hat (der
  ausführende Administrator). `erledigt_am`/`erledigt_von` bleiben als
  Altfelder erhalten (Bestandsdaten, Oberfläche) und werden mitgeschrieben.
* `benachrichtigt_am` — wann die Meldung an die Person rausging (D4: die Mail
  geht VOR der Anonymisierung; dieses Feld belegt die Reihenfolge).
* `anonymisiert_am` — gesetzt in derselben Transaktion, in der die Person
  anonymisiert wird. Ein Antrag ohne dieses Feld ist kein abgeschlossener
  Nachweis.

NEU in DSGVO-2a (Migration `dsgvo2a_antrag_ablehnung`):

* `status` kennt zusätzlich ``abgelehnt`` — die Verwaltung hat den Antrag
  geprüft und ihn nicht bestätigt. Die Person behält alle Daten, wird per Mail
  begründet informiert und darf danach erneut beantragen.
* `abgelehnt_am` / `abgelehnt_von` — Zeitpunkt und Konto des ablehnenden
  Administrators.
* `ablehnung_grund` — die Begründung im Wortlaut. Sie steht am Antrag, weil die
  PERSON sie lesen können muss (`mein_loeschantrag`); ins Audit-Log kommt sie
  NICHT, weil sie Gesundheitsdaten enthalten kann (Art. 9 DSGVO).

`mitglied` ist bewusst KEIN `ondelete="CASCADE"`: die Mitglied-zeile bleibt
auch nach der Löschung bestehen (nur anonymisiert), und ein Nachweis, der mit
der Person verschwindet, wäre keiner.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from diakronos_app.models.base import Base

#: Zulässige Antragsstände — die eine Wahrheit für Modell, Migration und API.
STATUS_OFFEN = "offen"
STATUS_ZURUECKGEZOGEN = "zurueckgezogen"
STATUS_AUSGEFUEHRT = "ausgefuehrt"
#: DSGVO-2a: Die Verwaltung hat den Antrag geprüft und nicht bestätigt.
STATUS_ABGELEHNT = "abgelehnt"
STATUS_WERTE = (STATUS_OFFEN, STATUS_ZURUECKGEZOGEN, STATUS_AUSGEFUEHRT, STATUS_ABGELEHNT)

#: Höchstlänge der Begründung (Zeichen). Die Oberfläche zählt mit, und
#: `api/datenschutz._pruefe_begruendung` LEHNT eine längere Begründung ab
#: (deutsche Meldung mit den Zeichenzahlen) — nichts wird still abgeschnitten:
#: eine gekürzte Begründung ginge an die Person und wäre nicht mehr das, was
#: die Verwaltung entschieden hat.
GRUND_MAX = 2000



class Loeschantrag(Base):
    __tablename__ = "loeschantrag"
    __table_args__ = (
        # Die Verwaltung listet offene Anträge, älteste zuerst; die Person
        # fragt ihren eigenen Stand über den Primärschlüssel ab.
        Index("ix_loeschantrag_status_beantragt", "status", "beantragt_am"),
    )

    mitglied: Mapped[str] = mapped_column(String(140), ForeignKey("mitglied.name"), primary_key=True)
    beantragt_am: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_OFFEN)
    zurueckgezogen_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    freigegeben_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    freigegeben_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    benachrichtigt_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    anonymisiert_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # DSGVO-2a: Ablehnung durch die Verwaltung — die Person behält alle Daten.
    abgelehnt_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    abgelehnt_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
    ablehnung_grund: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Altfelder aus N6 — bleiben, weil `api/datenschutz.py` und die Oberfläche
    # sie lesen. Sie werden zusammen mit den neuen Feldern geschrieben.
    erledigt_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    erledigt_von: Mapped[str | None] = mapped_column(String(140), nullable=True)
