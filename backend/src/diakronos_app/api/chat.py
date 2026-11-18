"""CHAT-2 (S1): Gespräche, Verlauf, Senden, Bearbeiten, Löschen, Reaktion, Lesestand.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` (Abschnitt 1/S1, 2, 3.3, 3.4, 4.3,
4.5, 9, 10; Entscheidungen Manuel 17.11.2026) und Karte CHAT-2.

WAS HIER STEHT (nur Backend, nur Gruppen-/Untergruppen-Gespräche)
----------------------------------------------------------------
* **Ein Gespräch je Gruppe/Untergruppe**, LAZY beim ersten Zugriff angelegt
  (``gespraech``) — kein Massen-Insert über alle Gruppen.
* **Lesen** seitenweise: rückwärts („vor X“ = ältere) und vorwärts
  („seit X“ = neuere, zugleich der Polling-Abruf aus 3.1). Beide laufen über
  den Index ``(gespraech, erstellt_am)``.
* **Senden**: nur Text, ≤ 4 000 Zeichen, Zeilenumbrüche bleiben (kein
  Trimmen des Textes, nur der Rand wird geprüft). Antwort auf GENAU EINE
  Nachricht desselben Gesprächs.
* **Bearbeiten**: eigene Nachricht, 15 Minuten (``BEARBEITEN_MINUTEN``),
  Kennzeichen ``bearbeitet_am``. Danach ``ValidationError``.
* **Löschen**: Soft-Delete — die Zeile bleibt, die Lücke bleibt sichtbar.
  Eigene jederzeit; fremde nur mit Moderationsrecht (der Rechte-Kern
  entscheidet, s. unten).
* **Reaktion**: festes Set (``REAKTIONEN``), EINE je Person und Nachricht.
  Der Endpunkt setzt (``reaktion`` gesetzt) oder entfernt (leer) sie.
* **Lesestand**: je Person ein Zeitstempel + Kennung. Sichtbar ist NUR die
  Summe „gelesen von N“ an EIGENEN Nachrichten (F2, 4.5) — nie eine Liste
  „wer hat was gelesen“; an fremden Nachrichten steht ``None``.

RECHTE: NICHTS SELBST GEBAUT
----------------------------
Jeder Endpunkt fragt ``rechte.darf(...)`` — LESEN/ANLEGEN für jedes Mitglied
der Einheit, SCHREIBEN mit ``besitzer=<Konto des Autors>`` für die eigene
Nachricht, MODERIEREN für die Leitung (HV/MV, in der Untergruppe auch GL). Das
Modul ``chat`` muss in der Gruppe an sein (``modul_aktiv``, im Kern enthalten).
Die Besitzfrage vergleicht KONTEN: ``chat_nachricht.autor_benutzer`` trägt das
Konto, ``chat_nachricht.autor`` die Anzeige (Mitglied-Kennung).
Ablehnung → 403 OHNE Inhalt (``throw("", PermissionError)``): der Grund
(Rollenstring) bleibt im Server, nicht in der Antwort.

SITZUNG
-------
Gelesen und geschrieben wird in der Sitzung des Aufrufs
(``dbmod.SessionLocal.begin()`` + ``als_aktuelle_sitzung``). Der Rechte-Kern liest
dadurch denselben Stand (er benutzt ``db.lesesitzung``); der Merker des Kerns
leert sich bei jedem Flush (``db.py``), ein Rechtewechsel wirkt also sofort.

CHAT-R2b: PERSONENSUCHE (``personen_suchen``)
--------------------------------------------
„Personen“ verschwindet als Menüpunkt; alle Personen findet man unter
„Nachrichten“ (Konzept 10.1 Punkt 2–4). Die Suche ist die EINE Fundstelle und
ist rein lesend: `q` ist der Name (Vor-/Nachname, Teilstring, ab 2 Zeichen),
das Ergebnis ist auf 20 Treffer begrenzt (max 50), sortiert nach Nachname,
Vorname.

ZWEI STUFEN, zwei getrennte Aufgaben:
1. **Vorfilter (SQL)** — aktive Mitglieder, deren Name den Begriff enthält.
   Das ist eine Vorfilterung, KEINE Entscheidung: `m.nachname`/`m.vorname`
   und der Name als Phrase („Anna Beispiel“). Der Vorfilter ist bewusst
   grosszügig (er darf zu viel liefern, nie zu wenig), die Grenze auf
   ``SUCHE_MAX`` Zeilen gilt erst nach der Rechteprüfung.
2. **Entscheidung** — JEDER Treffer läuft durch ``rechte.darf_person_finden``
   (und ``darf_direktnachricht`` für ``darf_schreiben``). Im API-Code steht
   KEINE eigene Status- oder Rollenlogik; wer auffindbar ist, entscheidet
   allein der Rechte-Kern.

FAIL CLOSED, ohne Unterscheidung: Gast, Fehler, nicht angemeldetes Konto →
leere Liste. „Gibt es nicht“ und „darfst du nicht“ sind in der Antwort NICHT
unterscheidbar (dieselbe Regel wie beim Registrierungslink, Konzept 2.4).

FELDER: ``mitglied``, ``anzeigename``, ``bild``, ``hat_konto``,
``darf_schreiben`` und die Kontaktfelder, die
``frappe_compat.mitglied_sichtbarkeit.maskiere_datensatz`` freigibt. Ein
NICHT freigegebenes Feld fehlt GANZ (Schlüssel nicht vorhanden, nicht
``null``) — die Suche liefert absichtlich WENIGER Felder als das Profil, und
zwar über DENSELBEN Maskierer wie Adressbuch/Liste (kein zweiter
Auslieferungsweg).

WAS HIER BEWUSST FEHLT (spätere Karten): Umfragen (CHAT-5), Meldungen
(CHAT-6), Direktnachrichten (CHAT-7), Löschfristen (CHAT-8), Push (CHAT-10),
Anhänge/Chatverlaufssuche (CHAT-9). Kein WebSocket: Zustellung ist der
„seit X“-Abruf (3.1, Empfehlung A).
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timedelta
from typing import Any, NoReturn

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("diakronos_app.api.chat")

#: Original-Frappe-Pfad ist leer: dieses Modul ist NEU (kein Altcode-Port).
FRAPPE_MODULE = "diakronos.diakronos.api.chat"

from diakronos_app import rechte
#: Die Sitzungs-Factory wird ueber das MODUL `db` benutzt (`db.SessionLocal()`),
#: NICHT als gebundener Name: `from diakronos_app.db import SessionLocal` friert
#: die Factory beim Import ein, und die Test-Fixture `patched_db` (die auf die
#: Test-Engine umbiegt) erreicht sie dann nicht mehr — der Test liefe gegen die
#: Betriebs-Datenbank. `api.mitglieder` macht es genauso (`_db.SessionLocal`).
from diakronos_app import db as dbmod
from diakronos_app.db import als_aktuelle_sitzung
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.chat import (
    ART_GRUPPE,
    ART_UNTERGRUPPE,
    BEARBEITEN_MINUTEN,
    NACHRICHT_MAX,
    REAKTIONEN,
    ChatGespraech,
    ChatNachricht,
    ChatReaktion,
    ChatTeilnehmer,
)
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied

#: Seitengröße des Verlaufs. 50 Nachrichten sind ~ eine Bildschirmseite am
#: Handy und am Desktop (Konzept 3.4: ~300 Nachrichten am Tag in einer
#: Gemeinde — 50 ist ein Sechstel davon).
SEITE = 50
#: Obergrenze für einen Aufruf (die Oberfläche fragt nie mehr an; ein Skript
#: soll die Datenbank nicht in einem Rutsch leeren können).
SEITE_MAX = 200
#: Höchstlänge eines Titels (Spalte ``chat_gespraech.titel``).
TITEL_MAX = 140


# ── Grundlagen ──────────────────────────────────────────────────────────────


def _h(ktion: str = "") -> NoReturn:
    """Ablehnung OHNE Inhalt: der Grund bleibt im Server (Karte: 403 ohne Inhalt).

    ``rechte.darf`` liefert den Grund als Rollen-/Regelnamen
    (``chat_leitung_hv``, ``modul_aus`` …). Der darf NICHT in die Antwort —
    er verrät Mitgliedschaften und Modulstand. Deshalb ein leerer Text und der
    Fehlerklasse, die der Router als 403 übersetzt.
    """
    raise PermissionError(ktion)


def _jetzt() -> datetime:
    """Jetzt als Wandzeit der Gemeinde, OHNE Zeitzone.

    Dieselbe Quelle wie überall in der App (``zeit.jetzt_wanduhr``): die
    Spalten sind ``DateTime`` ohne Zeitzone, und ein ``tzinfo``-Wert würde auf
    PostgreSQL als Wandzeit abgelegt, aber in Python anders verglichen.
    """
    from diakronos_app.zeit import jetzt_wanduhr

    return jetzt_wanduhr()


def _kennung(präfix: str) -> str:
    """Technische Kennung (Frappe-Namensreihe), z. B. ``chat-n-<uuid>``.

    Die Zeichen sind auf ``[a-z0-9-]`` begrenzt: keine Klammern, keine
    Leerzeichen — die Kennung reist als Parameter in der Adresse mit.
    """
    from uuid import uuid4

    return f"{präfix}-{uuid4().hex}"


def _benutzer() -> str:
    """Der angemeldete Benutzer (``frappe.session.user``)."""
    return str(session.user or "")


def _meine_kennung() -> str:
    """Mitglied-Kennung der angemeldeten Person — die Spalte ``autor`` traegt SIE.

    Dieselbe Aufloesung wie im Rechte-Kern (``mitglied.user``, sonst eindeutige
    E-Mail). Fehlt sie (Administrator, HV ueber eine RechteGruppenrolle), bleibt
    der ANZEIGE-Autor leer: der BESITZ steht in ``autor_benutzer`` (Konto) und
    traegt dann allein die Rechtefrage.
    """
    return str(rechte.eigenes_mitglied(_benutzer()) or "")


def _nicht_von(benutzer: str):
    """SQL-Bedingung „nicht von DIESER Person“ — verglichen wird das KONTO.

    ``autor_benutzer`` traegt den Besitz. NULL ist dabei NICHT „fremd“, sondern
    „Konto unbekannt/entfernt“ (z. B. nach einer Anonymisierung) — die Zeile
    bleibt lesbar, und „fremd“ ist keine Aussage mehr, die man treffen kann.
    ``or_(…, is_(None))`` macht das in EINER Bedingung: eine Zeile ohne Konto
    bleibt im Ungelesen-Zaehler, eine eigene faellt heraus.
    """
    return or_(ChatNachricht.autor_benutzer.is_(None),
               ChatNachricht.autor_benutzer != benutzer)


def _personen(s, kennungen) -> dict[str, str]:
    """Anzeigename je MITGLIED-Kennung („Vorname Nachname“, sonst die Kennung)."""
    namen = {str(k) for k in kennungen if k}
    if not namen:
        return {}
    zeilen = s.execute(
        _anzeigename_select().where(Mitglied.name.in_(namen))
    ).all()
    ergebnis: dict[str, str] = {}
    for kennung, anzeige in zeilen:
        text = str(anzeige or "").strip()
        ergebnis[str(kennung)] = text or str(kennung)
    for kennung in namen - set(ergebnis):
        ergebnis[kennung] = kennung
    return ergebnis


def _konto_namen(s, konten) -> dict[str, str]:
    """Anzeigename je KONTO (``user.full_name``, sonst die Adresse).

    NUR fuer Nachrichten ohne Mitgliedsdatensatz (Administrator, HV ueber eine
    RechteGruppenrolle): dort gibt es keine Mitglied-Kennung fuer ``autor``,
    und die Anzeige kommt aus dem Konto. Mehr als der Name wird nicht gelesen.
    """
    namen = {str(k) for k in konten if k}
    if not namen:
        return {}
    zeilen = s.execute(
        select(User.name, User.full_name).where(User.name.in_(namen))
    ).all()
    ergebnis: dict[str, str] = {}
    for konto, anzeige in zeilen:
        text = str(anzeige or "").strip()
        ergebnis[str(konto)] = text or str(konto)
    return ergebnis


def _anzeigename_select():
    """``(mitglied.name, „Vorname Nachname“)`` — dieselbe Anzeige wie überall.

    Kein eigener Personenbestand: der Name kommt aus ``mitglied`` (vorname +
    nachname). Konten OHNE Mitgliedsdatensatz haben keine Kennung zum Anzeigen —
    fuer die gibt es ``_konto_namen``.
    """
    return select(Mitglied.name, (func.trim(Mitglied.vorname + " " + Mitglied.nachname)))


# ── Gespräch (lazy) ─────────────────────────────────────────────────────────


def _gespraech_holen(s, gruppe: str, untergruppe: str | None = None) -> ChatGespraech:
    """Das Gespräch der Einheit; legt es beim ERSTEN Zugriff an (lazy).

    Der Schlüssel ist ``(art, gruppe, untergruppe)`` — in der Datenbank sichern
    ihn zwei PARTIELLE Unique-Indizes (Review Punkt 2: ein Constraint über die
    drei Spalten greift bei ``untergruppe IS NULL`` nicht). Zwei gleichzeitige
    Anfragen können deshalb beide anlegen wollen; der Index lässt nur eine
    durch, der zweite Aufruf faengt den ``IntegrityError`` im SAVEPOINT ab und
    liest die vorhandene Zeile. Ohne das Abfangen bliebe die Sitzung nach dem
    Fehler unbrauchbar (PostgreSQL bricht die Transaktion ab) und jeder weitere
    Aufruf liefe in einen 500er.
    """
    art = ART_UNTERGRUPPE if untergruppe else ART_GRUPPE
    vorhanden = _gespraech_suchen(s, art, gruppe, untergruppe)
    if vorhanden is not None:
        return vorhanden
    neu = ChatGespraech(
        name=_kennung("chat-gespraech"),
        art=art,
        gruppe=gruppe,
        untergruppe=untergruppe,
        angelegt_von=_benutzer() or None,
        angelegt_am=_jetzt(),
    )
    try:
        with s.begin_nested():
            s.add(neu)
            s.flush()
    except IntegrityError:
        # Ein paralleler Aufruf war schneller: der Savepoint ist zurueckgerollt,
        # die aeussere Transaktion lebt weiter — jetzt die vorhandene Zeile.
        vorhanden = _gespraech_suchen(s, art, gruppe, untergruppe)
        if vorhanden is None:
            raise
        return vorhanden
    return neu


def _gespraech_suchen(s, art: str, gruppe: str, untergruppe: str | None) -> ChatGespraech | None:
    """Die EINE Zeile der Einheit — ``scalar_one_or_none`` statt ``one``.

    Bleibt trotzdem eine zweite Zeile stehen (Altbestand aus der Zeit vor den
    partiellen Indizes), wird die aelteste genommen statt eines 500ers: der
    Verlauf ist dann nicht verloren, und der Betrieb kann die Doppelung
    aufraeumen.
    """
    return s.execute(
        select(ChatGespraech).where(
            ChatGespraech.art == art,
            ChatGespraech.gruppe == gruppe,
            ChatGespraech.untergruppe == untergruppe,
        ).order_by(ChatGespraech.name)
    ).scalars().first()


def _teilnahme(s, gespraech: str, benutzer: str) -> ChatTeilnehmer:
    """Teilnahme-Zeile der Person; wird beim ersten Zugriff angelegt.

    Die Teilnahme ist die eine Wahrheit über „wer ist im Gespräch“ (3.3) und
    trägt den Lesestand. Sie entsteht für JEDEN, der den Verlauf öffnet — ohne
    sie gäbe es keinen Lesestand und keinen Ungelesen-Zähler.
    """
    zeile = s.get(ChatTeilnehmer, (gespraech, benutzer))
    if zeile is not None:
        return zeile
    zeile = ChatTeilnehmer(
        gespraech=gespraech, benutzer=benutzer, stumm=False, hinzugefuegt_am=_jetzt()
    )
    s.add(zeile)
    s.flush()
    return zeile


# ── Nachricht als Antwortform ───────────────────────────────────────────────


def _reaktionen(s, nachrichten: list[str], benutzer: str) -> dict[str, list[dict[str, Any]]]:
    """Reaktionen je Nachricht: ``[{"reaktion": "👍", "anzahl": 3, "von_mir": True}]``.

    Der Zähler je Zeichen, nicht die Namen (F2/4.5: kein Verhaltensprofil).
    ``von_mir`` sagt der Oberfläche, welches Zeichen die eigene Person gesetzt
    hat — daraus ergibt sich „erneut klicken = entfernen“.
    """
    if not nachrichten:
        return {}
    zeilen = s.execute(
        select(ChatReaktion.nachricht, ChatReaktion.reaktion, ChatReaktion.benutzer)
        .where(ChatReaktion.nachricht.in_(nachrichten))
    ).all()
    gesammelt: dict[str, dict[str, dict[str, Any]]] = {}
    for nachricht, reaktion_text, konto in zeilen:
        eimer = gesammelt.setdefault(str(nachricht), {})
        eintrag = eimer.setdefault(str(reaktion_text), {"reaktion": str(reaktion_text),
                                                         "anzahl": 0, "von_mir": False})
        eintrag["anzahl"] += 1
        if str(konto) == benutzer:
            eintrag["von_mir"] = True
    # Feste Reihenfolge (das Set aus REAKTIONEN), damit die Oberfläche nicht
    # bei jedem Abruf anders sortiert.
    reihenfolge = {zeichen: i for i, zeichen in enumerate(REAKTIONEN)}
    ergebnis: dict[str, list[dict[str, Any]]] = {}
    for nachricht, eimer in gesammelt.items():
        ergebnis[nachricht] = sorted(
            eimer.values(),
            key=lambda e: (reihenfolge.get(str(e["reaktion"]), len(reihenfolge)),
                           -int(e["anzahl"])),
        )
    return ergebnis


def _gelesen_von(s, nachrichten, gespraech: str | None, benutzer: str) -> dict[str, int | None]:
    """„Gelesen von N“ — die SUMME, nie eine Namensliste (F2), NUR an eigenen.

    Konzept 1/S1 und 4.5: die Summe steht an der EIGENEN Nachricht („wer liest
    mit?“). An einer fremden Nachricht ist sie ``None`` — sonst waere sie ein
    Verhaltensprofil der anderen fuer jeden, der mitliest (Review Punkt 3).

    Gezählt wird eine Leserschaft, wenn ihr Lesestand (Zeitstempel + Kennung)
    HINTER dieser Nachricht liegt oder sie an einer SPAETEREN Nachricht gelesen
    hat (kumulativ). Gezaehlt werden:
      * nur AKTUELLE Angehoerige der Einheit — Teilnahmezeilen ehemaliger
        Mitglieder bleiben stehen (der Kern raeumt sie nicht ab) und wuerden die
        Zahl sonst dauerhaft aufblaehen;
      * ohne den Autor selbst — „gelesen“ heisst „von anderen gelesen“.
    """
    offen = [n for n in nachrichten if n is not None]
    if not offen or not gespraech or not benutzer:
        return {}
    staende = s.execute(
        select(ChatTeilnehmer.benutzer,
               ChatTeilnehmer.letzter_lesestand,
               ChatTeilnehmer.letzter_lesestand_nachricht)
        .where(ChatTeilnehmer.gespraech == gespraech,
               ChatTeilnehmer.letzter_lesestand.is_not(None))
    ).all()
    ergebnis: dict[str, int | None] = {}
    for n in offen:
        eigene = str(n.autor_benutzer or "") == benutzer
        if not eigene:
            ergebnis[str(n.name)] = None
            continue
        zaehler = 0
        for stand_benutzer, stand_am, stand_nachricht in staende:
            konto = str(stand_benutzer or "")
            if not konto or konto == benutzer:
                continue  # der Autor zaehlt sich nicht selbst
            if stand_am is None or not _darf_lesen(s, konto, n.gespraech):
                continue  # ehemaliges Mitglied (oder Konto weg) zaehlt nicht
            if stand_am > n.erstellt_am:
                zaehler += 1
            elif stand_am == n.erstellt_am and str(stand_nachricht or "") >= str(n.name):
                zaehler += 1
        ergebnis[str(n.name)] = zaehler
    return ergebnis


def _darf_lesen(s, benutzer: str, gespraech: str) -> bool:
    """Darf ``benutzer`` dieses Gespraech JETZT lesen? — ueber den Rechte-Kern.

    Die Frage entscheidet ``rechte.darf`` (Mitgliedschaft + Modul), nicht eine
    eigene Rollenlogik. Sie wird nur fuer die Zaehlung gebraucht: eine
    Teilnahmezeile allein sagt nichts ueber den heutigen Stand.
    """
    g = s.get(ChatGespraech, gespraech)
    if g is None or g.geloescht_am is not None:
        return False
    return bool(rechte.darf(benutzer, rechte.LESEN, "chat_gespraech", g.name,
                            gruppe=g.gruppe, untergruppe=g.untergruppe))


def _zeile(s, n: ChatNachricht, *,
           lesestand: dict[str, int | None] | None = None,
           reaktionen: dict[str, list[dict[str, Any]]] | None = None,
           antwort_auf: str | None = None,
           namen: dict[str, str] | None = None,
           konto_namen: dict[str, str] | None = None,
           ich: str = "") -> dict[str, Any]:
    """Eine Nachricht als flache Antwortzeile.

    ``text`` ist bei einer gelöschten Nachricht ``None`` — der Platz bleibt
    („Nachricht gelöscht“), der Inhalt geht nicht nach außen. ``bearbeitet``
    ist das Kennzeichen aus S1. ``gelesen_von`` ist ``None`` an fremden
    Nachrichten (Review Punkt 3).
    """
    geloescht = n.geloescht_am is not None
    return {
        "name": n.name,
        "gespraech": n.gespraech,
        # Anzeige (Mitglied-Kennung -> Name), sonst der Name des Kontos — ein
        # Konto OHNE Mitgliedsdatensatz (Administrator, HV ueber eine
        # RechteGruppenrolle) hat keinen ``autor``. In der Antwort steht
        # BEIDES: `autor` fuer die Anzeige, `autor_mitglied` fuer den Vergleich
        # „ist das meine Nachricht“ (Konten sind nicht stabil, die
        # Mitglied-Kennung ist es).
        "autor": ((namen or {}).get(str(n.autor or ""), n.autor)
                  or (konto_namen or {}).get(str(n.autor_benutzer or ""))),
        "autor_mitglied": n.autor,
        "eigene": bool(n.autor_benutzer) and str(n.autor_benutzer) == str(ich or ""),
        "text": None if geloescht else n.text,
        "geloescht": geloescht,
        "bearbeitet": n.bearbeitet_am is not None,
        "bearbeitet_am": _isoopt(n.bearbeitet_am),
        "erstellt_am": _isoopt(n.erstellt_am),
        "antwort_auf": n.antwort_auf,
        "antwort_auf_text": antwort_auf,
        "reaktionen": (reaktionen or {}).get(n.name, []),
        "gelesen_von": (lesestand or {}).get(n.name),
    }


def _isoopt(wert: datetime | None) -> str | None:
    return wert.isoformat() if wert else None


def _zitat(s, n: ChatNachricht) -> str | None:
    """Eine Zeile des zitierten Textes („die Antwort zitiert eine Zeile“).

    Gelöscht → ``None`` (kein Inhalt nach außen). Sonst die erste nicht-leere
    Zeile, auf 140 Zeichen gekürzt — die Oberfläche zeigt sie klein über der
    Antwort.
    """
    if n.geloescht_am is not None:
        return None
    for zeile in str(n.text or "").splitlines():
        if zeile.strip():
            return zeile.strip()[:140]
    return None


def _zitate(s, nachrichten: list[ChatNachricht]) -> dict[str, str | None]:
    ids = {n.antwort_auf for n in nachrichten if n.antwort_auf}
    if not ids:
        return {}
    ziele = s.execute(select(ChatNachricht).where(ChatNachricht.name.in_(ids))).scalars().all()
    return {str(n.name): _zitat(s, n) for n in ziele}


def _seite_antwort(s, gespraech: str, zeilen: list[ChatNachricht], *,
                   richtung: str, benutzer: str) -> dict[str, Any]:
    """Die Antwortform des Verlaufs — für beide Leserichtungen EINE Form."""
    kennungen = [n.name for n in zeilen]
    zitate = _zitate(s, zeilen)
    reakt = _reaktionen(s, kennungen, benutzer)
    stand = _gelesen_von(s, zeilen, gespraech, benutzer)
    namen = _personen(s, {n.autor for n in zeilen if n.autor})
    konten = _konto_namen(s, {n.autor_benutzer for n in zeilen if n.autor_benutzer})
    posten = [_zeile(s, n, lesestand=stand, reaktionen=reakt, antwort_auf=zitate.get(n.name),
                     namen=namen, konto_namen=konten, ich=benutzer)
              for n in zeilen]
    return {
        "gespraech": gespraech,
        "richtung": richtung,
        "nachrichten": posten,
        # Für den nächsten Abruf: die älteste und die neueste Kennung dieser
        # Seite (die Oberfläche fragt damit weiter bzw. pollt).
        "vor": posten[0]["name"] if posten else None,
        "seit": posten[-1]["name"] if posten else None,
    }


# ── Endpunkte: Gespräche ────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)  # legt Gespraech + Teilnahme an (SEC-11)
def gespraech_anlegen(gruppe=None, untergruppe=None):
    """Das Gespräch einer Gruppe/Untergruppe holen (legt es lazy an).

    Recht: LESEN in der Einheit (jedes Mitglied; Untergruppe = eigener Raum,
    F4). Antwort: ``{name, art, gruppe, untergruppe, titel}`` — die Kennung
    braucht die Oberfläche für Verlauf/Senden.

    ``gruppe`` darf auch WEGGELASSEN werden, wenn ``untergruppe`` angegeben ist:
    die Hauptgruppe wird dann aus ``untergruppe.gruppe`` gelesen.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g, u = _einheit(s, gruppe, untergruppe)
        _erlaube(benutzer, rechte.LESEN, gruppe=g, untergruppe=u)
        zeile = _gespraech_holen(s, g, u)
        _teilnahme(s, zeile.name, benutzer)
        return {
            "name": zeile.name,
            "art": zeile.art,
            "gruppe": zeile.gruppe,
            "untergruppe": zeile.untergruppe,
            "titel": zeile.titel,
        }


@whitelist(allow_guest=False)
def meine_gespraeche():
    """Alle Gruppen-/Untergruppen-Chats, die der Benutzer LESEN darf.

    Entscheidung Operator im Review (Punkt 5): die Liste zeigt AUCH noch nie
    geöffnete Gespräche (ungelesen = 0, ``geoeffnet: false``) und legt dafür
    KEINE Zeilen an — weder Gespräch noch Teilnahme. Grundlage sind die
    MITGLIEDSCHAFTEN des Benutzers (eine Abfrage für Gruppen, eine für
    Untergruppen), nicht alle Gespräche des Systems: die Rechtefrage stellt
    danach ``rechte.darf`` je Kandidat.

    Ungelesen: Nachrichten ANDERER (``autor_benutzer``) nach dem eigenen
    Lesestand, gelöschte zählen nicht. Ohne Lesestand zählt alles, was seit
    dem Beitritt geschrieben wurde (ohne Beitrittsdatum: alles) — die Anzeige
    darf kappen, der Zähler bleibt die Wahrheit.

    ``teilnehmer`` zählt nur AKTUELLE Angehörige der Einheit (nicht jede
    stehengebliebene Teilnahmezeile eines ehemaligen Mitglieds).

    Antwort: ``{gespraeche: [{name, art, gruppe, untergruppe, titel,
    teilnehmer, stumm, geoeffnet, ungelesen, letzte_nachricht, letzte_am}]}``.
    """
    benutzer = _benutzer()
    ergebnis: list[dict[str, Any]] = []
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        if not rechte.ist_gemeindemitglied(benutzer):
            _h()
        for g in _lesbare_gespraeche(s, benutzer):
            ergebnis.append(_gespraech_kopf(s, g, benutzer))
    ergebnis.sort(key=lambda e: (str(e["letzte_am"] or ""), str(e["titel"])), reverse=True)
    return {"gespraeche": ergebnis}


# ── Endpunkte: Personensuche (CHAT-R2b) ─────────────────────────────────────


@whitelist(allow_guest=False)
def personen_suchen(q=None, limit=None):
    """Personen für „Nachrichten“ suchen — rein lesend (GET), fail closed.

    ``q`` ist der NAME (Vor- oder Nachname, Teilstring, ab 2 Zeichen; leer →
    leere Liste). ``limit`` ist die Trefferzahl: Vorgabe ``SUCHE``, höchstens
    ``SUCHE_MAX`` — ein grösserer Wunsch wird gekappt, kein Fehler (ein
    ``limit=1000`` soll die Datenbank nicht in einem Rutsch leeren können).

    Antwort: ``{treffer: [...], limit: <tatsächliche Grenze>}``. Je Treffer
    ``mitglied``, ``anzeigename``, ``bild``, ``hat_konto``, ``darf_schreiben``
    und die per ``mitglied_sichtbarkeit`` freigegebenen Kontaktfelder. Nicht
    freigegebene Felder sind GAR NICHT im Treffer (nicht ``None``).

    Rechte: nur ``rechte.darf_person_finden`` (auffindbar) und
    ``rechte.darf_direktnachricht`` (schreibbar). KEINE eigene Status- oder
    Rollenlogik hier — der Vorfilter unten ist Suche, nicht Entscheidung.
    Gast, nicht angemeldetes Konto oder ein Fehler beim Auswerten → leere
    Liste, ohne Unterschied zwischen „gibt es nicht“ und „darfst du nicht“.
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import maskiere_datensatz
    from diakronos_app.rechte import darf_direktnachricht, darf_person_finden

    grenze = _suche_grenze(limit)
    leer: dict[str, Any] = {"treffer": [], "limit": grenze}
    try:
        benutzer = _benutzer()
        begriff = _suche_begriff(q)
        if not begriff or not rechte.ist_gemeindemitglied(benutzer):
            return leer
        treffer: list[dict[str, Any]] = []
        kandidaten: list = []
        with dbmod.SessionLocal() as s:
            for seite in range(_VORFILTER_SEITEN):
                teil = _suche_kandidaten(s, begriff, seite * _VORFILTER_MAX)
                kandidaten.extend(teil)
                # Genug Rohtreffer fuer die Grenze ODER keine weiteren Zeilen.
                if len(teil) < _VORFILTER_MAX or len(kandidaten) >= grenze * 8:
                    break
        for zeile in kandidaten:
            # `Row` -> dict ueber `_mapping` (ein `dict(Row)` scheitert: ein Row
            # ist eine Folge, kein Schlüssel/Wert-Paar).
            m = dict(zeile._mapping) if hasattr(zeile, "_mapping") else dict(zeile)
            kennung = str(m.get("name") or "")
            # Die EINE Entscheidung: der Rechte-Kern, nicht dieser Code.
            if not kennung or not darf_person_finden(benutzer, kennung):
                continue
            # Derselbe Maskierer wie Liste/Adressbuch. `Weglassen` (nicht
            # `None`) macht `_nur_freigegebene_felder` daraus.
            maskiert = maskiere_datensatz(m, mitglied_id=kennung) or {}
            treffer.append(_suche_treffer(
                kennung=kennung,
                roh=m,
                maskiert=maskiert,
                darf_schreiben=bool(darf_direktnachricht(benutzer, kennung)),
            ))
            if len(treffer) >= grenze:
                break
        return {"treffer": treffer, "limit": grenze}
    except Exception as fehler:  # noqa: BLE001 — fail closed: JEDER Fehler ⇒ keine Treffer
        # Fail closed, aber nicht stumm: protokolliert wird die FEHLERKLASSE
        # (kein Suchbegriff, kein Treffer, keine Kennung). Ein kaputter
        # Endpunkt soll in den Logs auffallen, ohne Namen preiszugeben.
        logger.warning("personen_suchen: Suche fehlgeschlagen (%s) — leere Liste",
                       type(fehler).__name__)
        return leer


#: Vorgabe und Obergrenze der Trefferzahl (Konzept 10.1, Karte Punkt 3).
SUCHE = 20
SUCHE_MAX = 50
#: Kürzeste Sucheingabe — ein einzelnes Zeichen fände fast die ganze Gemeinde.
SUCHE_MIN_ZEICHEN = 2
#: So viele Vorfilter-Zeilen holt die Datenbank je Suche. Der Vorfilter ist
#: absichtlich grosszügig (er muss Treffer finden, deren Auffindbarkeit erst
#: der Rechte-Kern bejaht), aber nicht unbegrenzt: 8 × die Höchstzahl deckt
#: auch eine Gemeinde ab, in der die ersten Treffer wegfallen. Die endgültige
#: Grenze ist ``SUCHE_MAX`` NACH der Rechteprüfung.
_VORFILTER_MAX = SUCHE_MAX * 8

#: Felder, die ein Treffer ausliefern darf — ausschliesslich Kontaktfelder,
#: für die ``mitglied_sichtbarkeit`` einen Schalter kennt. Alles andere
#: (``notiz``, Einwilligungen, ``angelegt_von`` …) kommt hier gar nicht erst
#: in Frage; Verwaltungsfelder wirft zusätzlich der Maskierer weg.
_SUCHE_FELDER = ("email", "telefonnummer", "postleitzahl", "wohnort",
                 "straße", "nummer", "geburtstag")


def _suche_grenze(limit) -> int:
    """Tatsächliche Trefferzahl: Vorgabe ``SUCHE``, gekappt auf ``SUCHE_MAX``.

    Unlesbare/negative Angaben fallen auf die Vorgabe zurück (kein Fehler) —
    eine Suche soll an einem kaputten ``limit`` nicht scheitern.
    """
    if limit is None or limit == "":
        return SUCHE
    try:
        wert = int(str(limit).strip())
    except (TypeError, ValueError):
        return SUCHE
    return max(1, min(SUCHE_MAX, wert))


def _suche_begriff(q) -> str:
    """Suchbegriff normalisieren (Kleinschreibung, Umlaute aufgelöst, getrimmt).

    Dieselbe Faltung wie die Mitgliederliste (``api.mitglieder``): „weiss“
    findet „Weiß“, „MUELLER“ findet „Müller“. Zu kurze Eingaben → ``""``.
    """
    text = unicodedata.normalize("NFC", str(q or "")).strip().lower()
    for von, nach in (("ß", "ss"), ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(von, nach)
    text = " ".join(text.split())
    return text if len(text) >= SUCHE_MIN_ZEICHEN else ""


def _suche_faltung(spalte: str) -> str:
    """SQL-Ausdruck, der eine Spalte klein- UND umlautgefaltet liefert.

    Gleiche Bauart wie ``api.mitglieder._suche_ausdruck`` (dort ist sie privat,
    ein Import über Modulgrenzen wäre eine stille Kopplung): erst BEIDE
    Schreibweisen der Umlaute/ß ersetzen, dann ``LOWER`` — PostgreSQLs ``LIKE``
    ist case-sensitiv, SQLites ``LOWER`` lässt Nicht-ASCII unverändert.
    ``spalte`` ist ein fester Bezeichner aus dieser Datei, keine Nutzereingabe.
    """
    ausdruck = spalte
    for von, nach in (("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
                      ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        ausdruck = f"REPLACE({ausdruck}, '{von}', '{nach}')"
    return f"LOWER({ausdruck})"


def _like_muster(begriff: str) -> str:
    """``%begriff%`` mit maskierten Platzhaltern (``\\``, ``%``, ``_``).

    Ohne Maskierung faende ``__`` oder ``%%`` die ganze Gemeinde und hebelte
    die Mindestlaenge aus. Escape-Zeichen ist ``\\`` (``ESCAPE '\\'`` in
    jeder LIKE-Klausel — SQLite kennt keinen Standard, PostgreSQL schon).
    """
    for zeichen in ("\\", "%", "_"):
        begriff = begriff.replace(zeichen, "\\" + zeichen)
    return f"%{begriff}%"


def _suche_kandidaten(s, begriff: str, versatz: int = 0) -> list:
    """Vorfilter: Mitglieder, deren Name den Begriff enthält — EINE Seite.

    Sucht in ``vorname``, ``nachname`` UND in der Phrase „Vorname Nachname“
    (damit „anna bei“ auch „Anna Beispiel“ trifft). Der Vorfilter entscheidet
    NICHTS: er schliesst nur ``geloescht-*`` aus; ob eine Person auffindbar
    ist (Status, Austritt, Ausschluss), sagt allein
    ``rechte.darf_person_finden`` je Treffer. Sortiert nach Nachname,
    Vorname (Karte Punkt 3). Der Aufrufer blaettert mit ``versatz`` weiter,
    bis genug Treffer bestaetigt sind — sonst schnitte eine Seite voller
    Ausgetretener berechtigte Treffer ab (Review 18.11.).
    """
    muster = _like_muster(begriff)
    vorname = _suche_faltung("m.vorname")
    nachname = _suche_faltung("m.nachname")
    phrase_vor = _suche_faltung(
        "COALESCE(m.vorname, '') || ' ' || COALESCE(m.nachname, '')")
    # Die umgekehrte Reihenfolge wird ebenfalls gesucht: „Brandner Bert“ ist
    # genauso ein Name wie „Bert Brandner“.
    phrase_nach = _suche_faltung(
        "COALESCE(m.nachname, '') || ' ' || COALESCE(m.vorname, '')")
    spalten = ", ".join(
        ["m.name", "m.vorname", "m.nachname", "m.foto", "m.user",
         "m.adressbuch_sichtbarkeit", "m.status"]
        + [f'm."{feld}"' if feld == "straße" else f"m.{feld}" for feld in _SUCHE_FELDER]
    )
    like = " LIKE :muster ESCAPE '\\'"
    sql = (
        "SELECT " + spalten + " FROM mitglied m WHERE ("
        + f"{vorname}{like} OR {nachname}{like}"
        + f" OR {phrase_vor}{like} OR {phrase_nach}{like}"
        + ") AND m.name NOT LIKE 'geloescht-%'"
        " ORDER BY m.nachname, m.vorname, m.name LIMIT :grenze OFFSET :versatz"
    )
    try:
        return s.execute(text(sql), {"muster": muster, "grenze": _VORFILTER_MAX,
                                     "versatz": int(versatz)}).all()
    except Exception as fehler:  # noqa: BLE001 — fail closed, aber nicht stumm
        logger.warning("personen_suchen: Vorfilter fehlgeschlagen (%s) — leere Liste",
                       type(fehler).__name__)
        return []


#: Hoechstzahl Vorfilter-Seiten je Suche (Schutz gegen Endlosblaettern).
_VORFILTER_SEITEN = 10


def _nur_freigegebene_felder(maskiert: dict[str, Any],
                             sicht: dict[str, bool]) -> dict[str, Any]:
    """Kontaktfelder, die die Person freigegeben hat — sonst Schlüssel WEG.

    Grundlage ist das Ergebnis von ``maskiere_datensatz`` (der eine
    Auslieferungsweg). Dieses setzt nicht freigegebene Felder auf ``None``;
    die Suche liefert sie stattdessen GAR NICHT (Konzept 10.4: „die Suche
    liefert weniger Felder als das Profil“). Zusätzlich muss der zugehörige
    Schalter stehen — ein Wert, der trotz fehlender Freigabe im Datensatz
    steht, wird damit nicht durchgereicht (fail closed).
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import FELD_AN_SCHALTER

    felder: dict[str, Any] = {}
    for feld in _SUCHE_FELDER:
        schalter = FELD_AN_SCHALTER.get(feld)
        if not schalter or not sicht.get(schalter):
            continue
        wert = maskiert.get(feld)
        if wert in (None, ""):
            continue
        if isinstance(wert, str):
            wert = wert.strip()
            if not wert:
                continue
        felder[feld] = wert.isoformat() if hasattr(wert, "isoformat") else wert
    return felder


def _suche_treffer(*, kennung: str, roh: dict[str, Any],
                   maskiert: dict[str, Any], darf_schreiben: bool) -> dict[str, Any]:
    """Ein Treffer in der Form, die „Nachrichten“ zeichnet.

    ``anzeigename`` läuft durch ``personen_anzeige.kuerze`` (EINE Regel für
    gekürzte Namen) — bei einer gelöschten Person steht dort „Gelöschte
    Person“, nie die Kennung. ``hat_konto`` (aktives Konto) und
    ``darf_schreiben`` kommen beide aus dem Rechte-Kern — eine Person mit
    deaktiviertem Konto ist auffindbar, gilt aber als „hat kein Konto“.

    Kontaktfelder kommen aus ``maskiert`` (dem Ergebnis von
    ``maskiere_datensatz``) und nur, wenn die Person sie freigegeben hat. Was
    nicht freigegeben ist, steht NICHT im Treffer — auch nicht als ``None``.
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen
    from diakronos_app.frappe_compat.personen_anzeige import kuerze
    from diakronos_app.frappe_compat.personen_anzeige import ist_geloescht

    geloescht = ist_geloescht(dict(roh, name=kennung))
    kurz = kuerze(dict(roh, name=kennung))
    anzeige = str(kurz.get("vorname") or "").strip() or kennung
    if not geloescht:
        # `kuerze` kürzt ausgetretene Personen; sie sind in der Suche ohnehin
        # weg (Rechte-Kern). Der Normalfall trägt den vollen Namen.
        anzeige = " ".join(p for p in (str(roh.get("vorname") or "").strip(),
                                       str(roh.get("nachname") or "").strip()) if p) or kennung
    treffer: dict[str, Any] = {
        "mitglied": kennung,
        "anzeigename": anzeige,
        "bild": _suche_bild(roh.get("foto"), geloescht),
        # Konto-Frage beantwortet der Rechte-Kern (aktives Konto, Review 18.11.).
        "hat_konto": rechte.person_hat_konto(kennung),
        "darf_schreiben": bool(darf_schreiben),
    }
    treffer.update(_nur_freigegebene_felder(
        maskiert, sichtbarkeit_lesen(roh.get("adressbuch_sichtbarkeit"))))
    return treffer


def _suche_bild(foto, ist_geloescht: bool) -> str:
    """Bildadresse eines Treffers — präfigiert wie überall (``foto_mit_praefix``).

    Kein Bild einer gelöschten Person (die Datei ist entfernt, ein Rest im
    Feld wäre ein toter Verweis) — dieselbe Regel wie in der Mitgliederliste.
    """
    if ist_geloescht or not foto:
        return ""
    from diakronos_app.api.profile import foto_mit_praefix

    return foto_mit_praefix(foto)


# ── Endpunkte: Verlauf ──────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def verlauf(gespraech, vor=None, seit=None, limit=None):
    """Verlauf seitenweise: ``vor`` = ältere, ``seit`` = neuere Nachrichten.

    ``vor=<name>``   die Seite VOR dieser Nachricht (älter; beim Scrollen nach
                     oben), sortiert von alt nach neu.
    ``seit=<name>``  alle Nachrichten NACH dieser (neuer; das ist der
                     Polling-Abruf aus 3.1) — ohne Angabe die neueste Seite.

    Recht: LESEN im Gespräch. Antwort siehe ``_seite_antwort``.
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    grenze = SEITE
    if limit not in (None, ""):
        try:
            grenze = max(1, min(int(limit), SEITE_MAX))
        except (TypeError, ValueError):
            throw("limit muss eine Zahl sein.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        # Rein lesend (SEC-11): die Teilnahme entsteht beim Oeffnen
        # (`gespraech_anlegen`), Senden oder Lesestand-Setzen.
        if vor:
            anker = _nachricht(s, str(vor), g.name)
            zeilen = s.execute(
                select(ChatNachricht).where(
                    ChatNachricht.gespraech == g.name,
                    or_(ChatNachricht.erstellt_am < anker.erstellt_am,
                        (ChatNachricht.erstellt_am == anker.erstellt_am)
                        & (ChatNachricht.name < anker.name)),
                ).order_by(ChatNachricht.erstellt_am.desc(),
                           ChatNachricht.name.desc()).limit(grenze)
            ).scalars().all()
            zeilen.reverse()  # alt -> neu anzeigen
            return _seite_antwort(s, g.name, zeilen, richtung="vor", benutzer=benutzer)
        if seit:
            anker = _nachricht(s, str(seit), g.name)
            zeilen = s.execute(
                select(ChatNachricht).where(
                    ChatNachricht.gespraech == g.name,
                    or_(ChatNachricht.erstellt_am > anker.erstellt_am,
                        (ChatNachricht.erstellt_am == anker.erstellt_am)
                        & (ChatNachricht.name > anker.name)),
                ).order_by(ChatNachricht.erstellt_am, ChatNachricht.name).limit(grenze)
            ).scalars().all()
            return _seite_antwort(s, g.name, zeilen, richtung="seit", benutzer=benutzer)
        zeilen = s.execute(
            select(ChatNachricht).where(ChatNachricht.gespraech == g.name)
            .order_by(ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc())
            .limit(grenze)
        ).scalars().all()
        zeilen.reverse()
        return _seite_antwort(s, g.name, zeilen, richtung="neueste", benutzer=benutzer)


# ── Endpunkte: Senden / Bearbeiten / Löschen ────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def senden(gespraech, text, antwort_auf=None):
    """Nachricht senden (nur Text, ≤ 4 000 Zeichen, Absätze bleiben).

    Recht: ANLEGEN in der Einheit — jedes Mitglied darf senden (Konzept 2.2),
    Gäste nie (der Kern gibt Gästen kein Modul).

    Der Text wird NICHT getrimmt: Zeilenumbrüche und Einrückungen sind Inhalt.
    Geprüft wird nur, dass am Rand etwas steht und die Länge passt — gezählt
    werden ZEICHEN, nicht Bytes.

    ``antwort_auf`` muss eine Nachricht DESSELBEN Gesprächs sein (sonst könnte
    man fremde Gespräche zitieren).
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    inhalt = _pruefe_text(text)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.ANLEGEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        ziel = None
        if antwort_auf not in (None, ""):
            ziel = _nachricht(s, str(antwort_auf), g.name)
        zeile = ChatNachricht(
            name=_kennung("chat-n"),
            gespraech=g.name,
            # Besitz = das KONTO (Rechte, Ungelesen-Zaehlung); Anzeige = die
            # Mitglied-Kennung, die bei einer Loeschung umgehaengt wird.
            autor_benutzer=benutzer or None,
            autor=_meine_kennung() or None,
            text=inhalt,
            antwort_auf=ziel.name if ziel else None,
            erstellt_am=_jetzt(),
        )
        s.add(zeile)
        _teilnahme(s, g.name, benutzer)
        s.flush()
        return _zeile(s, zeile, antwort_auf=_zitat(s, ziel) if ziel else None,
                      namen=_personen(s, {zeile.autor}),
                      konto_namen=_konto_namen(s, {zeile.autor_benutzer}), ich=benutzer)


@whitelist(methods=["POST"], allow_guest=False)
def aendern(nachricht, text):
    """Eigene Nachricht bearbeiten — nur innerhalb von 15 Minuten.

    Recht: SCHREIBEN mit ``besitzer=Autor``. Die Leitung darf eine fremde
    Nachricht NICHT bearbeiten (SCHREIBEN mit fremdem Besitzer verlangt im
    Kern Leitung — hier wird zusätzlich geprüft, dass es die EIGENE ist:
    Bearbeiten ist keine Moderationshandlung; fremde Nachrichten entfernt man,
    man schreibt sie nicht um).

    Nach ``BEARBEITEN_MINUTEN`` → ``ValidationError``. ``bearbeitet_am`` wird
    gesetzt (Kennzeichen „bearbeitet“).
    """
    benutzer = _benutzer()
    inhalt = _pruefe_text(text)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        # Die Besitzfrage entscheidet der Rechte-KERN — durchgereicht wird das
        # KONTO der Nachricht. Bearbeiten ist keine Moderationshandlung: eine
        # fremde Nachricht entfernt man, man schreibt sie nicht um (der Kern
        # liesse es der Leitung durchgehen, deshalb zusaetzlich die Pruefung
        # „ist es meine“).
        if not _ist_meine(n, benutzer):
            _h()
        _erlaube(benutzer, rechte.SCHREIBEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 besitzer=n.autor_benutzer, gespraech=g.name)
        if n.geloescht_am is not None:
            throw("Eine gelöschte Nachricht kann nicht bearbeitet werden.")
        jetzt = _jetzt()
        if n.erstellt_am is None or jetzt - n.erstellt_am > timedelta(minutes=BEARBEITEN_MINUTEN):
            throw("Nachrichten lassen sich nur in den ersten 15 Minuten bearbeiten.")
        n.text = inhalt
        n.bearbeitet_am = jetzt
        s.flush()
        return _zeile(s, n, namen=_personen(s, {n.autor}),
                      konto_namen=_konto_namen(s, {n.autor_benutzer}), ich=benutzer)


@whitelist(methods=["POST"], allow_guest=False)
def loeschen(nachricht):
    """Nachricht löschen (Soft-Delete — die Lücke bleibt sichtbar).

    Eigene jederzeit (SCHREIBEN mit eigenem Besitzer), fremde nur mit
    Moderationsrecht (MODERIEREN; HV/MV, in der Untergruppe auch GL). Der
    Rechte-Kern entscheidet, welcher der beiden Wege greift.

    Der Text bleibt in der Datenbank (Widerspruchsfälle, CHAT-6/8), wird aber
    nicht mehr ausgeliefert: ``text=None``, ``geloescht=True``. Zweites Löschen
    ist kein Fehler (idempotent) — der Zeitpunkt des ersten bleibt stehen.
    """
    benutzer = _benutzer()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        eigene = _ist_meine(n, benutzer)
        if eigene:
            _erlaube(benutzer, rechte.SCHREIBEN, gruppe=g.gruppe,
                     untergruppe=g.untergruppe, besitzer=n.autor_benutzer,
                     gespraech=g.name)
        else:
            _erlaube(benutzer, rechte.MODERIEREN, gruppe=g.gruppe,
                     untergruppe=g.untergruppe, gespraech=g.name)
        if n.geloescht_am is None:
            n.geloescht_am = _jetzt()
            n.geloescht_von = benutzer
        s.flush()
        return _zeile(s, n, namen=_personen(s, {n.autor}),
                      konto_namen=_konto_namen(s, {n.autor_benutzer}), ich=benutzer)


# ── Endpunkte: Reaktion, Lesestand, Stumm ───────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def reaktion_setzen(nachricht, reaktion=None):
    """Reaktion setzen, wechseln oder entfernen — EINE je Person und Nachricht.

    ``reaktion`` eines der sechs Zeichen → gesetzt (ein vorhandenes Zeichen
    wird ersetzt, es entsteht KEINE zweite Zeile: der Primärschlüssel ist
    ``(nachricht, benutzer)``). Leer/``None`` → entfernt.

    Recht: LESEN im Gespräch (wer mitlesen darf, darf auch reagieren) — und
    die Nachricht muss existieren, auch wenn sie gelöscht ist: die Reaktionen
    bleiben an der Lücke stehen.
    """
    benutzer = _benutzer()
    zeichen = str(reaktion or "").strip()
    if zeichen and zeichen not in REAKTIONEN:
        throw("Unbekannte Reaktion.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        n = _nachricht(s, str(nachricht or "").strip(), None)
        g = _gespraech_lesen(s, n.gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        vorhanden = s.get(ChatReaktion, (n.name, benutzer))
        if not zeichen:
            if vorhanden is not None:
                s.execute(delete(ChatReaktion).where(
                    ChatReaktion.nachricht == n.name, ChatReaktion.benutzer == benutzer))
        elif vorhanden is None:
            s.add(ChatReaktion(nachricht=n.name, benutzer=benutzer,
                               reaktion=zeichen, erstellt_am=_jetzt()))
        else:
            vorhanden.reaktion = zeichen
        s.flush()
        return {"nachricht": n.name,
                "reaktionen": _reaktionen(s, [n.name], benutzer).get(n.name, [])}


@whitelist(methods=["POST"], allow_guest=False)
def lesestand_setzen(gespraech, nachricht=None):
    """Lesestand setzen — „bis hierhin gelesen“.

    Ohne ``nachricht``: bis zur NEUESTEN Nachricht des Gesprächs. Mit
    ``nachricht``: bis zu dieser (sie muss im Gespräch liegen; ein
    Zurücksetzen auf eine ältere Nachricht ist erlaubt — der Stand geht
    vorwärts wie rückwärts, sonst bliebe ein versehentlicher Klick endgültig).

    Recht: LESEN. Antwort: ``{gespraech, ungelesen}`` — der neue Zähler.
    Eine NAMENSLISTE „wer hat gelesen“ gibt es bewusst nicht (F2).
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        teilnahme = _teilnahme(s, g.name, benutzer)
        if nachricht not in (None, ""):
            ziel = _nachricht(s, str(nachricht), g.name)
        else:
            ziel = s.execute(
                select(ChatNachricht).where(ChatNachricht.gespraech == g.name)
                .order_by(ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc())
                .limit(1)
            ).scalar_one_or_none()
        if ziel is not None:
            teilnahme.letzter_lesestand = ziel.erstellt_am
            teilnahme.letzter_lesestand_nachricht = ziel.name
        s.flush()
        return {"gespraech": g.name, "bis": ziel.name if ziel else None,
                "ungelesen": _ungelesen(s, g.name, benutzer)}


@whitelist(methods=["POST"], allow_guest=False)
def stumm_setzen(gespraech, an=True):
    """Gespräch für SICH stumm schalten (F3: jede Person für sich).

    Recht: LESEN. ``an`` als Wahrheitswert (``true``/``false``, „1“/„0“).
    Wirkung auf die Glocke kommt mit CHAT-4 — hier steht nur der Schalter.
    """
    benutzer = _benutzer()
    gespraech = str(gespraech or "").strip()
    if not gespraech:
        throw("gespraech fehlt.")
    wert = _wahr(an)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        g = _gespraech_lesen(s, gespraech)
        _erlaube(benutzer, rechte.LESEN, gruppe=g.gruppe, untergruppe=g.untergruppe,
                 gespraech=g.name)
        teilnahme = _teilnahme(s, g.name, benutzer)
        teilnahme.stumm = wert
        s.flush()
        return {"gespraech": g.name, "stumm": wert}


# ── Innen: lesen, prüfen, zählen ────────────────────────────────────────────


def _einheit(s, gruppe, untergruppe) -> tuple[str, str | None]:
    """``(Hauptgruppe, Untergruppe)`` aus den Parametern — OHNE Rateweg.

    Review CHAT-2, Punkt 1: die Hauptgruppe einer Untergruppe ist IMMER
    ``untergruppe.gruppe``. Eine mitgegebene, ABWEICHENDE ``gruppe`` wird
    abgewiesen (403 ohne Inhalt): sonst umginge ``gespraech(gruppe=A,
    untergruppe=U)`` den Modulschalter von B (der Kern prueft ``modul_aktiv``
    in der Hauptgruppe) und legte ein Gespraech unter falscher Gruppe an.
    Gleiche Hauptgruppe oder keine Angabe: es gilt die aus der Untergruppe.

    Unbekannte Untergruppe → 403 ohne Inhalt (nicht 404: das verriete, dass es
    die Kennung nicht gibt).
    """
    from diakronos_app.models.diakonos import Untergruppe

    g = str(gruppe or "").strip()
    u = str(untergruppe or "").strip() or None
    if not g and not u:
        throw("gruppe fehlt.")
    if not u:
        return g, None
    haupt = s.execute(
        select(Untergruppe.gruppe).where(Untergruppe.name == u)
    ).scalar_one_or_none()
    haupt = str(haupt or "").strip()
    if not haupt:
        _h()
    if g and g != haupt:
        _h()
    return haupt, u


def _erlaube(benutzer: str, aktion: str, *, gruppe: str | None,
             untergruppe: str | None = None, besitzer: str | None = None,
             gespraech: str | None = None) -> None:
    """DIE Rechtefrage — ``rechte.darf``, nichts Eigenes (Kartenauflage).

    ``besitzer`` wird in der Form des Kerns uebergeben: eine KONTO-Kennung
    (``user.name``), verglichen gegen ``benutzer`` (``_darf_chat``:
    ``besitzer is None or besitzer == benutzer``). Deshalb traegt
    ``chat_nachricht.autor_benutzer`` den Besitz — die Mitglied-Kennung in
    ``autor`` waere nie gleich dem Konto, und der Kern saehe jede eigene
    Nachricht als fremd an.
    """
    entscheidung = rechte.darf(
        benutzer, aktion, "chat_gespraech", gespraech,
        gruppe=gruppe, untergruppe=untergruppe, besitzer=besitzer,
    )
    if not entscheidung:
        _h()


def _ist_meine(n: ChatNachricht, benutzer: str) -> bool:
    """Gehoert die Nachricht DIESER Person? — verglichen wird das KONTO."""
    return bool(n.autor_benutzer) and str(n.autor_benutzer) == str(benutzer or "")


def _gespraech_lesen(s, gespraech: str) -> ChatGespraech:
    """Gespräch per Kennung; unbekannt → 404 (nichts über seine Existenz raten)."""
    if not gespraech:
        throw("gespraech fehlt.")
    zeile = s.get(ChatGespraech, gespraech)
    if zeile is None or zeile.geloescht_am is not None:
        raise DoesNotExistError("Gespräch nicht gefunden.")
    return zeile


def _nachricht(s, nachricht: str, gespraech: str | None) -> ChatNachricht:
    """Nachricht per Kennung; ``gespraech`` grenzt sie auf EIN Gespräch ein.

    Die Eingrenzung ist die Zusage aus der Karte: „Antwort auf genau eine
    Nachricht“ — und zwar aus DEMSELBEN Verlauf. Ohne sie könnte man eine
    Nachricht aus einem fremden Gespräch zitieren oder daran reagieren.
    """
    if not nachricht:
        throw("nachricht fehlt.")
    zeile = s.get(ChatNachricht, nachricht)
    if zeile is None or (gespraech is not None and zeile.gespraech != gespraech):
        raise DoesNotExistError("Nachricht nicht gefunden.")
    return zeile


def _pruefe_text(text) -> str:
    """Text einer Nachricht: nicht leer am Rand, ≤ 4000 ZEICHEN, Absätze bleiben.

    Getrimmt wird nur, um „leer“ zu erkennen — gespeichert wird der Text
    unverändert (Einrückungen, Zeilenumbrüche und Leerzeilen sind Inhalt).
    """
    if text is None:
        throw("Bitte einen Text eingeben.")
    inhalt = str(text)
    if not inhalt.strip():
        throw("Bitte einen Text eingeben.")
    if len(inhalt) > NACHRICHT_MAX:
        throw(f"Eine Nachricht darf höchstens {NACHRICHT_MAX} Zeichen lang sein "
              f"(eingegeben: {len(inhalt)}).")
    return inhalt


def _wahr(wert) -> bool:
    """Wahrheitswert aus JSON/Formular (``true``/``1``/``ja``)."""
    if isinstance(wert, bool):
        return wert
    if wert is None or wert == "":
        return True
    text = str(wert).strip().casefold()
    if text in ("false", "0", "nein", "no", "aus"):
        return False
    if text in ("true", "1", "ja", "yes", "an"):
        return True
    throw("Bitte true oder false angeben.")


def _ungelesen(s, gespraech: str, benutzer: str) -> int:
    """Ungelesen-Zähler eines Gesprächs (gleiche Regel wie ``meine_gespraeche``)."""
    teilnahme = s.get(ChatTeilnehmer, (gespraech, benutzer))
    return _ungelesen_zaehlen(s, gespraech, benutzer, teilnahme)


def _ungelesen_zaehlen(s, gespraech: str, benutzer: str,
                       teilnahme: ChatTeilnehmer | None) -> int:
    """Fremde, nicht gelöschte Nachrichten nach dem eigenen Lesestand.

    ``_nicht_von`` vergleicht das KONTO (``autor_benutzer``) — eine Nachricht
    ohne Konto (anonymisiert) gilt als fremd. Ohne Teilnahme/ohne Lesestand
    zählt ALLES seit dem Beitritt (``hinzugefuegt_am``; ohne Datum: alles).
    """
    bedingung = [ChatNachricht.gespraech == gespraech,
                 ChatNachricht.geloescht_am.is_(None),
                 _nicht_von(benutzer)]
    if teilnahme is not None and teilnahme.letzter_lesestand is not None:
        stand = teilnahme.letzter_lesestand
        bedingung.append(or_(
            ChatNachricht.erstellt_am > stand,
            (ChatNachricht.erstellt_am == stand)
            & (ChatNachricht.name > str(teilnahme.letzter_lesestand_nachricht or "")),
        ))
    elif teilnahme is not None and teilnahme.hinzugefuegt_am is not None:
        bedingung.append(ChatNachricht.erstellt_am >= teilnahme.hinzugefuegt_am)
    return int(s.execute(select(func.count()).select_from(ChatNachricht)
                         .where(*bedingung)).scalar_one())


def _teilnahme_konten(s, gespraech: str) -> list[str]:
    """Konten mit Teilnahmezeile in diesem Gespraech (nur Kennungen)."""
    return [str(k) for k in s.execute(
        select(ChatTeilnehmer.benutzer).where(ChatTeilnehmer.gespraech == gespraech)
    ).scalars().all() if k]


def _lesbare_gespraeche(s, benutzer: str) -> list[ChatGespraech]:
    """Die Gespraeche, die ``benutzer`` LESEN darf — aus SEINEN Mitgliedschaften.

    Review Punkt 5: NICHT alle Gespraeche des Systems laden und je
    ``darf`` fragen, sondern zwei Abfragen (Gruppen, Untergruppen) auf den
    Mitgliedschaften des Benutzers aufsetzen. Je Kandidat entscheidet danach
    ``rechte.darf`` (Mitgliedschaft + Modul ``chat``) — keine eigene
    Rollenlogik. Ein Gespraech, das es (noch) nicht gibt, wird hier NICHT
    angelegt; es erscheint mit ``geoeffnet: false`` und ``name=None``.
    """
    from diakronos_app.models.diakonos import (
        Gruppenmitgliedschaft,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )

    einheiten: list[tuple[str, str | None]] = []
    mitglied = _meine_kennung()
    if mitglied:
        einheiten += [(str(g), None) for g in s.execute(
            select(Gruppenmitgliedschaft.parent)
            .where(Gruppenmitgliedschaft.mitglied == mitglied)).scalars().all() if g]
        einheiten += [("", str(u)) for u in s.execute(
            select(Untergruppenmitgliedschaft.parent)
            .where(Untergruppenmitgliedschaft.mitglied == mitglied)).scalars().all() if u]
    # Rollen OHNE Mitgliedsdatensatz (HV/MV/GL ueber RechteGruppenrolle,
    # Administrator) — dieselbe Quelle, aus der `rechte.darf` die Rolle liest.
    from diakronos_app.models.rechte import RechteGruppenrolle
    for gruppe, untergruppe in s.execute(
        select(RechteGruppenrolle.gruppe, RechteGruppenrolle.untergruppe)
        .where(RechteGruppenrolle.benutzer == benutzer)
    ).all():
        einheiten.append((str(gruppe or ""), str(untergruppe or "") or None))

    # Review 18.11.: Hauptgruppe einer Untergruppen-Mitgliedschaft ergaenzen
    # (Untergruppenmitglieder lesen den Gruppenchat) und zu jeder Hauptgruppe
    # ihre Untergruppen (HV/MV lesen sie geerbt). Ob wirklich gelesen werden
    # darf, entscheidet unten weiter allein `rechte.darf`.
    normiert: list[tuple[str, str | None]] = []
    for gruppe, untergruppe in einheiten:
        if untergruppe:
            haupt = s.execute(select(Untergruppe.gruppe).where(
                Untergruppe.name == untergruppe)).scalar_one_or_none()
            gruppe = str(haupt or "").strip()
            normiert += [(gruppe, untergruppe), (gruppe, None)]
        else:
            normiert.append((gruppe, None))
    hauptgruppen = sorted({g for g, u in normiert if g and u is None})
    if hauptgruppen:
        normiert += [(str(g), str(u)) for u, g in s.execute(
            select(Untergruppe.name, Untergruppe.gruppe)
            .where(Untergruppe.gruppe.in_(hauptgruppen))).all() if u and g]

    gesehen: set[tuple[str, str | None]] = set()
    ergebnis: list[ChatGespraech] = []
    for gruppe, untergruppe in normiert:
        if not gruppe or (gruppe, untergruppe) in gesehen:
            continue
        gesehen.add((gruppe, untergruppe))
        if not rechte.modul_aktiv(gruppe, "chat"):
            continue  # Modul aus = kein Eintrag (und kein Rechte-Aufruf je Zeile)
        art = ART_UNTERGRUPPE if untergruppe else ART_GRUPPE
        zeile = _gespraech_suchen(s, art, gruppe, untergruppe)
        if not rechte.darf(benutzer, rechte.LESEN, "chat_gespraech",
                           zeile.name if zeile else None,
                           gruppe=gruppe, untergruppe=untergruppe):
            continue
        ergebnis.append(zeile if zeile is not None else ChatGespraech(
            name=None, art=art, gruppe=gruppe, untergruppe=untergruppe))
    return ergebnis


def _gespraech_kopf(s, g: ChatGespraech, benutzer: str) -> dict[str, Any]:
    """Ein Eintrag der Gespraechsliste — auch fuer ein noch nie geoeffnetes."""
    teilnahme = s.get(ChatTeilnehmer, (g.name, benutzer)) if g.name else None
    if g.name:
        ungelesen = _ungelesen_zaehlen(s, g.name, benutzer, teilnahme)
        letzte = s.execute(select(ChatNachricht)
                           .where(ChatNachricht.gespraech == g.name)
                           .order_by(ChatNachricht.erstellt_am.desc(),
                                     ChatNachricht.name.desc())
                           .limit(1)).scalar_one_or_none()
    else:
        ungelesen, letzte = 0, None
    titel = str(g.titel or "").strip() or (g.untergruppe or g.gruppe)
    return {
        "name": g.name,
        "art": g.art,
        "gruppe": g.gruppe,
        "untergruppe": g.untergruppe,
        "titel": titel,
        "teilnehmer": _teilnehmer_aktuelle(s, g),
        "stumm": bool(teilnahme.stumm) if teilnahme is not None else False,
        # `geoeffnet: false` heisst: es gibt noch keine Gespraechszeile. Die
        # Oberflaeche holt sie beim Tipp auf den Eintrag ueber `gespraech(...)`.
        "geoeffnet": bool(g.name),
        "ungelesen": ungelesen,
        "letzte_nachricht": _zitat(s, letzte) if letzte else None,
        "letzte_am": _isoopt(letzte.erstellt_am) if letzte else None,
    }


def _teilnehmer_aktuelle(s, g: ChatGespraech) -> int:
    """Wie viele AKTUELLE Angehoerige hat die Einheit? (nicht: Teilnahmezeilen)

    Review Punkt 3: eine stehengebliebene Teilnahmezeile eines ausgetretenen
    Mitglieds ist kein Teilnehmer mehr. Gezaehlt wird daher ueber den
    Rechte-Kern (``darf`` LESEN je Konto) — und nur unter den Konten, die eine
    Teilnahmezeile haben. Neu hinzugekommene Mitglieder ohne Teilnahmezeile
    zaehlen NICHT mit: die Zahl beschreibt das Gespraech, nicht die Einheit.
    """
    if not g.name:
        return 0
    return sum(1 for konto in _teilnahme_konten(s, g.name)
               if _darf_lesen(s, konto, g.name))


__all__ = [
    "FRAPPE_MODULE",
    "SEITE",
    "SEITE_MAX",
    "TITEL_MAX",
    "aendern",
    "gespraech_anlegen",
    "lesestand_setzen",
    "loeschen",
    "meine_gespraeche",
    "reaktion_setzen",
    "senden",
    "stumm_setzen",
    "verlauf",
]
