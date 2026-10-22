"""Darf dieser Benutzer ueberhaupt eine Sitzung halten? — Karte B1.

DER BEFUND
----------
`frappe_compat/auth_middleware.py` hat aus einem `sid` schlicht
`session.user` gemacht. Weder `User.enabled` noch die Frage, ob der
Benutzer ueberhaupt noch in der `user`-Tabelle steht, wurden geprueft. Ein
deaktivierter oder geloeschter Benutzer blieb deshalb so lange angemeldet,
wie seine Sitzung im Redis lag — auf **jedem** Geraet. Und
`api/profile.py::delete_my_data` raeumte nur die *aktuelle* Sitzung ab, obwohl
sein Docstring "SOFORT raus" versprach.

DIE REGEL — EINMAL, HIER
------------------------
Ein Benutzer hat genau dann eine gueltige Sitzung, wenn

  1. es eine `user`-Zeile mit diesem Namen gibt, **und**
  2. `enabled` daran wahr ist.

Beide Anmeldewege benutzen dieselbe Regel, aber nicht dieselbe Messung:

  * **Sitzungs-Cookie** (`SessionMiddleware`): kennt nur den Namen, muss die
    Zeile selbst holen → `ist_aktiv(name)`. Das ist der heisse Pfad, deshalb
    mit kurzem Redis-Cache.
  * **CalDAV / Login** (`caldav/auth.py::_check_credentials`,
    `api/auth.py::login`): haben die Zeile schon geladen (fuer den Hash
    bzw. fuer den Vergleich) → `konto_ist_aktiv(doc)`. Kein zweiter
    Query pro Versuch — der Zeitangleichungstest aus A1c1/A1c2 misst
    Antwortzeiten, und ein zweiter DB-Rundgang waere dort genau das
    Rauschen, das die Messung beschaedigt.

WER DIE SITZUNGEN WIDERRUFT
---------------------------
`api/profile.py::delete_my_data` (deaktiviert den eigenen Account) und jede
kuenftige Stelle, die `enabled` auf 0 setzt, rufen
`widerrufe_sitzungen(user)`. Das ist der **aktive** Widerruf: sofort, ohne
Cache-Frist. Wer `enabled` per Hand in der Datenbank umstellt, umgeht ihn —
dafuer ist der Cache in `ist_aktiv` da, und dessen Frist ist die einzige
Luecke, die diese Karte bewusst zulaesst (siehe unten).

DER CACHE UND SEINE FRIST
-------------------------
`ist_aktiv` fragt die Datenbank **nicht** bei jedem Request. Gemessen am
laufenden Stack (Postgres, PK-Lookup auf `user`): 0,407 ms pro Query, ein
Redis-`GET` 0,130 ms. Bei einem Client, der alle paar Sekunden einen
Aufruf macht, waere die Abfrage der teuerste Teil des Requests — fuer eine
Tatsache, die sich alle paar Sekunden aendert.

Also ein Cache je Benutzer, TTL aus `settings.benutzerstatus_ttl` —
**Default 30 Sekunden**. Das ist die *gesamte* zulaessige Verzoegerung
eines Widerrufs von aussen:

  * Weg von **aussen** (Direktabfrage in der DB, SQL-Admin, andere
    Anwendung): hoechstens 30 s, danach faellt der naechste Aufruf auf die
    Wahrheit zurueck.
  * Weg von **innen** (`delete_my_data`, Admin-Deaktivierung): 0 s, weil
    `widerrufe_sitzungen` den Cache-Eintrag mit loescht, bevor die
    Sitzungen rausfliegen. Beide Wege laufen ueber dieselbe Funktion, damit
    es keinen "fast sofort"-Zweig gibt.

Warum ueberhaupt cachen und nicht einfach jedes Mal fragen: 30 Sekunden ist
die Frist, die die Karte erlaubt — 0 Sekunden (immer fragen) waere nur
teurer, ohne strenger zu sein. Die andere Richtung — `enabled` faellt unter
einem gemeinsamen Cache-Schluessel zusammen — waere strenger und waere ein
Fehler; die Schluessel sind je Benutzer, ein Benutzer kann nie another's
Status lesen.

FAIL CLOSED
-----------
Ein Fehler beim Nachsehen heisst **nicht angemeldet**, nicht "wissen wir
nicht, machen wir mal". Ein Benutzer, dessen Status sich nicht pruefen
laesst, wird wie `Guest` behandelt und seine Sitzung wird geloescht. Das
ist aufwendig, wenn die Datenbank gerade wackelt — und genau das ist der
Preis, den ein Mitgliederverwaltungssystem mit Personendaten zahlen muss.
Der Login-Zugang ist davon **nicht** betroffen: dort wird die Zeile ohnehin
geladen, und ein Fehler dort ist ein 500 wie bei jeder anderen Fachfunktion.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from diakronos_app.frappe_compat.session import GUEST
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.auth")

__all__ = [
    "STATUS_PRAEFIX",
    "ist_aktiv",
    "konto_ist_aktiv",
    "vergiss",
    "widerrufe_sitzungen",
    "wirksame_konten",
    "ausgetretene_konten",
    "_client",
]

# Eigener Namensraum, neben den Sitzungen (`sitzungen.py`) und den
# Anmeldesperren (`loginversuche.py`). Der Wert ist ein Flag, kein Datum —
# `1` heisst "gueltig", `0` heisst "existiert nicht oder ist deaktiviert".
STATUS_PRAEFIX = "diakronos:benutzerstatus:"

_AKTIV = "1"
_INAKTIV = "0"

def _client():
    """Redis-Client des Status-Caches (patchbar, siehe `tests/conftest.py`).

    Bewusst ein eigener Zugriff wie in `sitzungen.py`: die Test-Fixture
    `fake_redis` haengt **jeden** dieser Clients an einen In-Memory-Stub.
    Ein Modul, das sich den Client aus `sitzungen` borgt, umginge das
    stillschweigend und schriebe in den Store des laufenden Stacks.
    """
    from redis import Redis

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _ttl() -> int:
    return max(1, int(settings.benutzerstatus_ttl))


def _key(user: str) -> str:
    return f"{STATUS_PRAEFIX}{user.strip().lower()}"


def _pseudonym(user: str) -> str:
    """Log-taugliches Kuerzel eines Benutzernamens — nie der Name selbst.

    Gesalzen mit `secret_key`, gekuerzt auf 12 Hex-Zeichen. Damit kann der
    Betreiber zwei Logzeilen desselben Kontos zusammenfuehren, ohne dass
    das Serverlog zur Adressliste wird (dieselbe Form wie
    `api/auth.py::_pseudo`).
    """
    salz = str(getattr(settings, "secret_key", "") or "")
    return hashlib.sha256(f"{salz}|{user.strip().lower()}".encode()).hexdigest()[:12]


def _aus_db(name: str) -> bool:
    """Existiert der Benutzer **und** ist er aktiv? — die ungecachte Wahrheit.

    Nur die eine Spalte wird gelesen: `enabled`. Ein Benutzer, den es nicht
    gibt, liefert keine Zeile und damit `False` — dieselbe Antwort wie bei
    einem deaktivierten. Das ist Absicht: die Regel kennt keinen Unterschied
    zwischen "weg" und "aus" (beides heisst: keine Sitzung).

    P1-8 (Nachtrag R-P1-9b): ZUSÄTZLICH gilt ein Benutzer als inaktiv, wenn
    das zu ihm gehörende Mitglied `ausgeschlossen` ist. Der Ausschluss setzt
    den Status auf „Passiver Gast“, ließ das Login-Konto aber bisher
    unberührt — eine ausgeschlossene Person konnte sich weiter anmelden und
    behielt ihre Rollen und Sichtbarkeit. Die Ausschluss-Markierung ist der
    stärkere Wille der Gemeinde und wird hier an derselben Stelle geprüft,
    damit BEIDE Wege (Sitzungs-Cookie und Login) dieselbe Regel sehen.

    Der Import von `SessionLocal` steht **im** Rumpf, damit die Test-Fixture
    `patched_db` greift (sie setzt `diakronos_app.db.SessionLocal`). So
    laeuft die Messung auch im Test gegen die Test-Datenbank.
    """
    from sqlalchemy import select

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        zeile = sess.execute(
            select(User.enabled).where(User.name == name)
        ).first()
    finally:
        sess.close()
    if not (bool(zeile[0]) if zeile is not None else False):
        return False
    return not _mitglied_ausgeschlossen(name)


def _kontozustand() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Zuordnung aus derselben Aufruf-Transaktion lesen (auch Import-Batches)."""
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    with lesesitzung() as sess:
        mitglieder = [dict(r) for r in sess.execute(select(
            Mitglied.name, Mitglied.user, Mitglied.email, Mitglied.ausgeschlossen,
            Mitglied.status, Mitglied.austritt_datum,
        )).mappings()]
        konten = [dict(r) for r in sess.execute(select(
            User.name, User.email, User.enabled,
        )).mappings()]
    return mitglieder, konten


def wirksame_konten(
    mitglied_daten: Any, *, _mitglieder=None, _konten=None,
) -> set[str]:
    """Kontowirkung: user-Link UND case-insensitive E-Mail.

    FACHENTSCHEIDUNG (Manuel, 2026-10-19): Jede Person hat eine eigene
    E-Mail-Adresse; eine Adresse gehoert hoechstens zu EINEM Mitglied. Die
    frueher hier noetige Sonderbehandlung „mehrdeutige Adresse" (Familien-
    postfach, P1-8c Punkt 4) ist damit entfallen — und mit ihr der modulweite
    Zustand `_MEHRDEUTIG`, an dem die Rechteentscheidung hing.

    Bleibt eine Adresse trotzdem doppelt (Altbestand vor der Migration), gilt
    die vorsichtige Lesart: dann sind ALLE Konten mit dieser Adresse wirksam.
    Das sperrt hoechstens zu viel, nie zu wenig — die Adresse kann nicht
    benutzt werden, um einen Ausschluss zu umgehen.

    Die optionalen Bestände dienen ausschließlich der Prüfung eines geplanten
    Schreibzustands. Ohne sie wird der aktuelle Transaktionsstand gelesen.
    Datenbankfehler werden nicht als leere (scheinbar sichere) Menge behandelt.
    """
    if mitglied_daten is None:
        return set()
    if not isinstance(mitglied_daten, dict):
        mitglied_daten = {k: getattr(mitglied_daten, k, None) for k in ("user", "email")}
    link = str(mitglied_daten.get("user") or "").strip()
    ergebnis = {link} if link else set()
    adresse = str(mitglied_daten.get("email") or "").strip().lower()
    if not adresse:
        return ergebnis
    if _mitglieder is None or _konten is None:
        _mitglieder, _konten = _kontozustand()
    ergebnis.update(
        str(k["name"]) for k in _konten
        if str(k.get("email") or k["name"]).strip().lower() == adresse
    )
    return ergebnis


def _ausgeschlossene_konten(mitglieder, konten) -> set[str]:
    """Tatsächlicher Ausschluss ohne Sonderausnahme für Verwaltungsrollen.

    Der Ausschluss eines Mitglieds sperrt dessen wirksame Konten
    (`wirksame_konten`: `user`-Link UND Konto mit derselben, seit der
    Fachentscheidung eindeutigen E-Mail).

    Die Marke ``ausgeschlossen`` traegt BEIDE Faelle (Austritt und
    Ausschluss). Wer nur den Austritt meint, fragt ``ausgetretene_konten``.
    """
    ergebnis: set[str] = set()
    for m in mitglieder:
        if m.get("ausgeschlossen"):
            ergebnis.update(wirksame_konten(m, _mitglieder=mitglieder, _konten=konten))
    return ergebnis


def ausgetretene_konten(mitglieder, konten) -> set[str]:
    """Konten, deren Mitglied AUSGETRETEN ist (nicht ausgeschlossen).

    AUSTRITT-d (NM2): ``_ausgeschlossene_konten`` nimmt die Marke und trifft
    damit beide Faelle. Die Kuerzung gilt aber nur dem Austritt (N3) — und die
    Entscheidung faellt an einer Stelle: ``personen_anzeige.ist_ausgeschieden``.
    """
    from .personen_anzeige import ist_ausgeschieden

    ergebnis: set[str] = set()
    for m in mitglieder:
        if ist_ausgeschieden(m):
            ergebnis.update(wirksame_konten(m, _mitglieder=mitglieder, _konten=konten))
    return ergebnis


def _mitglied_ausgeschlossen(user: str) -> bool:
    """Die Rechteprüfung verwendet dieselbe Vorwärtsauflösung wie die Schranke.

    K2 (R-P1-8e, bekannte Grenze): Diese Frage wird in heissen Pfaden gestellt
    (`get_roles` ruft sie je Aufruf), und der Zustand ist ein Volllauf ueber
    `Mitglied`/`User`. Ein Merker waere hier FALSCH: derselbe Aufrufkontext
    darf innerhalb einer Anfrage/Transaktion denselben Datensatz aendern
    (Ausschluss setzen und sofort pruefen) — ein Cache je Anfrage gaebe dann
    einen veralteten Wert zurueck und braeche die Zusage „im Zweifel
    verweigern“. Deshalb bleibt die Frage ungecacht; die Optimierung waere
    eine eigene, sorgfaeltig abzusichernde Aenderung an der Cacheschicht
    (`ist_aktiv`-Muster mit Invalidierung bei jedem Schreibweg).
    """
    mitglieder, konten = _kontozustand()
    return user in _ausgeschlossene_konten(mitglieder, konten)


def _ist_letzter_system_manager(user: str) -> bool:
    """Das letzte Netz zählt nur enabled UND nicht ausgeschlossene Konten."""
    from diakronos_app.api.zugang import _aktive_system_manager

    aktiv = _aktive_system_manager()
    return user in aktiv and len(aktiv) == 1


def _cache_setze(name: str, aktiv: bool) -> None:
    try:
        _client().set(_key(name), _AKTIV if aktiv else _INAKTIV, ex=_ttl())
    except Exception as exc:  # noqa: BLE001 — Cache ist Optimierung, nie Bedingung
        logger.warning(
            "Benutzerstatus nicht gecacht (Kuerzel %s): %s", _pseudonym(name), type(exc).__name__
        )


def ist_aktiv(user: str) -> bool:
    """Existiert `user` und ist `enabled`? — mit kurzem Redis-Cache.

    `Guest` ist nie ein Sitzungstraeger: eine Sitzung, die auf `Guest`
    laeuft, wird hier fuer ungueltig erklaerlt und geloescht. Das ist die
    Regel "im Zweifel verweigern" — es gibt keinen Grund, `Guest` als
    angemeldeten Namen in einer Sitzung zuzulassen.

    **Fail closed**: schlaegt das Nachsehen fehl (Datenbank nicht
    erreichbar, Redis nicht erreichbar), ist das Ergebnis `False` und die
    Sitzung wird ungueltig. Nicht `True` und nicht "unbekannt, weitermachen".
    """
    name = str(user or "").strip()
    if not name or name == GUEST:
        return False

    try:
        roh = _client().get(_key(name))
    except Exception as exc:  # noqa: BLE001 — siehe Modulkopf
        logger.warning(
            "Benutzerstatus nicht lesbar (Kuerzel %s), Sitzung ungueltig: %s",
            _pseudonym(name), type(exc).__name__,
        )
        return False
    if roh is not None:
        return roh == _AKTIV

    try:
        aktiv = _aus_db(name)
    except Exception as exc:  # noqa: BLE001 — fail closed, siehe Modulkopf
        logger.warning(
            "Benutzerstatus nicht pruefbar (Kuerzel %s), Sitzung ungueltig: %s",
            _pseudonym(name), type(exc).__name__,
        )
        return False

    _cache_setze(name, aktiv)
    return aktiv


def konto_ist_aktiv(doc) -> bool:
    """Dieselbe Regel an einer **bereits geladenen** User-Zeile.

    fuer `caldav/auth.py::_check_credentials` und `api/auth.py::login`:
    beide holen die Zeile ohnehin (Hash bzw. Vergleich), da waere ein
    zweiter Query pro Versuch Verschwendung — und in der Zeitangleichung
    aus A1c1/A1c2 sogar messbarer Lärm. `None` heisst "kein solches
    Konto" und ist damit `False`, genau wie in `ist_aktiv`.

    P1-8 (Nachtrag R-P1-9b): hier gilt zusätzlich der Ausschluss des
    Mitglieds (`_mitglied_ausgeschlossen`) — dieselbe Regel wie in
    `ist_aktiv`, sonst könnten sich ausgeschlossene Personen per Login
    weiter anmelden, während die Sitzungsprüfung sie bereits abweist.
    """
    if doc is None:
        return False
    name = doc.get("name") if isinstance(doc, dict) else getattr(doc, "name", None)
    aktiv = bool(doc.get("enabled")) if isinstance(doc, dict) else bool(
        getattr(doc, "enabled", False)
    )
    if not aktiv:
        return False
    if not name:
        return True
    return not _mitglied_ausgeschlossen(str(name))


def vergiss(user: str) -> None:
    """Wirft den Cache-Eintrag eines Benutzers weg.

    Nach jeder Stelle, die `enabled` schreibt. Ohne das wuerde ein
    wieder aktiviertes Konto noch bis zum TTL abgewiesen — und die
    Deaktivierung waere nur *zusaetzlich* sofort, nicht ausschliesslich.
    Fehler werden geschluckt: der Cache-Eintrag ist dann hoechstens zu alt,
    und der naechste Aufruf fragt einfach wieder nach.
    """
    if not user:
        return
    try:
        _client().delete(_key(user), _key(user) + ':erstwechsel')
    except Exception as exc:  # noqa: BLE001 — Vergessen ist nie zwingend
        logger.warning(
            "Benutzerstatus nicht vergessbar (Kuerzel %s): %s",
            _pseudonym(str(user)), type(exc).__name__,
        )


def widerrufe_sitzungen(user: str) -> int:
    """Der **aktive** Widerruf: Cache vergessen + alle Sitzungen weg.

    Rueckgabe: Anzahl geloeschter Sitzungen. Genau diese Funktion — und
    nicht ein eigenes `sitzungen.loeschen` je Aufrufer — ist der einzige
    Weg, auf dem der Code eine Sitzung *beendet*, weil der Benutzer nicht
    mehr (aktiv) existiert. Sie macht beides in dieser Reihenfolge:

      1. `vergiss(user)` — ab hier ist der Status wieder aus der DB wahr.
      2. `sitzungen.loesche_alle_von(user)` — der Benutzer-Index weiss
         danach, dass er leer ist.

    Fehler beim Redis-Zugriff werden **nicht** geschluckt: der Aufrufer
    steht in einer Sicherheitsfunktion (Widerruf, Deaktivierung). Ein
    still verschluckter Fehler hiesse "Konto aus, Sitzungen offen" — genau
    der Zustand, den diese Karte beseitigt. Wer das nicht haben will,
    faengt die Ausnahme bewusst ab; der Aufrufer in `api/profile.py` tut das
    und loggt es.
    """
    from diakronos_app.frappe_compat import sitzungen

    name = str(user or "").strip()
    if not name:
        return 0
    vergiss(name)
    geloescht = sitzungen.loesche_alle_von(name)
    if geloescht:
        logger.info(
            "Sitzungen eines Benutzers widerrufen: %s (Kuerzel %s)",
            geloescht, _pseudonym(name),
        )
    return geloescht
