"""ON-1 — Einrichtungs-Token: erzeugen, pruefen, verbrauchen.

WARUM DIESES MODUL
------------------
Bis ON-1 gab es zum ersten Administrator nur ``ADMIN_EMAIL``/``ADMIN_PASSWORD``
in der ``.env``. Das ist kopflos, aber fuer eine Gemeinde die falsche
Voreinstellung: das Passwort steht im Klartext in einer Datei. ON-1 ergaenzt
deshalb den Weg ueber einen EINMAL-Link.
 
Sicherheitszusage (Vertrag der Karte)
-------------------------------------
  * Der Token entsteht aus ``secrets.token_urlsafe(32)`` (43 Zeichen, ~256 Bit).
    Er ist fuer Menschen nicht tippbar und wird nur kopiert.
  * In der Datenbank steht NUR ``sha256(<Token>)`` (Hex). Ein Datenbank-Dump
    enthaelt damit keinen benutzbaren Link.
  * Ablauf: :data:`GUELTIG_TAGE` Tage. Ein Token ohne Ablauf gaebe es nicht.
  * Ein NEUER Token macht den alten ungueltig: es gibt genau EINE Zeile
    (``EINRICHTUNG_TOKEN_NAME``), ein neuer Token ueberschreibt Hash und Ablauf.
  * Verglichen wird konstantzeitig: die Suche laeuft ueber den Hash-Index
    (``SELECT … WHERE token_hash = :digest``) und die Pruefung danach ueber
    ``hmac.compare_digest``. Der Vergleich ist damit nicht von der Uhr, sondern
    von der Laenge abhaengig — kein Byte-weiser Kurzschluss.
  * Nach dem Anlegen des Administrators wird die Zeile GELOESCHT (verbraucht).
  * Der Klartext-Token wird NIRGENDS geloggt — ausser in dem einen Kasten, den
    der Start bewusst ausgibt (``erstinstallation``/``__main__``).

ABLAUF UND WETTLAUF
-------------------
``verbrauche_mit`` sperrt die Zeile (``with_for_update``) und prueft Hash und
Ablauf INNERHALB der Transaktion des Aufrufers. Zwei parallele Absendungen
desselben Links koennen deshalb nicht beide durchkommen: die zweite sieht die
Zeile entweder nicht mehr (sie ist weg) oder einen anderen Hash.

Aufrufer
--------
  * ``erstinstallation.bootstrap_erstinstallation`` — beim Start
  * ``einrichtung.routen`` — die Seiten (GET/POST)
  * ``python -m diakronos_app.einrichtung link`` — Neuerzeugen von Hand
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from diakronos_app.models.einrichtung import EINRICHTUNG_TOKEN_NAME, EinrichtungToken

__all__ = [
    "EINRICHTUNG_TOKEN_NAME",
    "GUELTIG_TAGE",
    "TOKEN_LAENGE",
    "neuer_token",
    "hash_von",
    "link_pfad",
    "link_anzeige",
    "erzeuge_token",
    "pruefe_token",
    "gueltiger_token_vorhanden",
    "verbrauche_mit",
    "entferne_token",
]

#: Gueltigkeit eines Einrichtungslinks. 7 Tage wie im freigegebenen Entwurf
#: (Frame 01/03): lang genug fuer eine Gemeinde, die den Server heute
#: installiert und den Administrator naechste Woche anlegt.
GUELTIG_TAGE = 7

#: Laenge von ``secrets.token_urlsafe(32)`` — als pruefbare Zahl, nicht als
#: Absicht (dieselbe Zusage wie in ``registrierungslink.TOKEN_LAENGE``).
TOKEN_LAENGE = 43

#: App-eigener Pfad der Einrichtungsseite. Der Betriebs-Praefix kommt beim
#: Bauen der Adresse davor (``base_path.pfad``).
_SEITEN_PFAD = "/einrichtung"


def _jetzt() -> datetime:
    """Jetzt in UTC, ohne Zeitzone — wie ``passwortzugang._jetzt()``.

    Die Spalte ist ``DateTime`` ohne Zeitzone; PostgreSQL und SQLite speichern
    beide naive Werte. Eine zeitzonenbewusste Zeit an dieser Stelle haette auf
    SQLite einen Vergleich gegen naive Werte gefuehrt (Ablauf unzuverlaessig).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def neuer_token() -> str:
    """Ein frischer Einrichtungs-Token (43 Zeichen base64url, ~256 Bit)."""
    return secrets.token_urlsafe(32)


def hash_von(token: str) -> str:
    """``sha256(<token>)`` als Hex — der EINZIGE bleibende Wert des Tokens."""
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def link_pfad(token: str) -> str:
    """Der app-eigene Pfad des Einrichtungslinks (ohne Praefix, ohne Host)."""
    return f"{_SEITEN_PFAD}/{token}"


def link_anzeige(token: str) -> str:
    """Die vollstaendige Adresse des Einrichtungslinks.

    Mit gesetztem ``APP_BASE_URL`` absolut (``https://gemeinde.example.org/
    diakronos/einrichtung/<token>``) — das ist der Wert, den der Startkasten
    zeigt. Ohne Basis bleibt es der PRAEFIXBEWUSSTE Pfad
    (``/diakronos/einrichtung/<token>``); der Start nennt dann ausdruecklich,
    dass der Host fehlt.
    """
    from diakronos_app import base_path
    from diakronos_app.settings import settings

    # ON-1b: der Praefix kommt aus den Einstellungen, wenn der Prozess ihn
    # noch nicht gesetzt hat. Die CLI (`diakronos einrichtungslink`) und der
    # Entrypoint sind EIGENE Prozesse — dort lief `main.create_app()` nie, und
    # `base_path.pfad` lieferte den Link OHNE `DIAKRONOS_BASE_PATH` (im
    # Wegwerf-Stack mit `/diakronos` als 404 nachgewiesen).
    if not base_path.aktiver_praefix():
        base_path.setze_praefix(str(getattr(settings, "diakronos_base_path", "") or ""))

    pfad = base_path.pfad(link_pfad(token))
    basis = str(getattr(settings, "app_base_url", "") or "").strip().rstrip("/")
    return f"{basis}{pfad}" if basis else pfad


def erzeuge_token(*, jetzt: datetime | None = None) -> tuple[str, datetime]:
    """Legt einen NEUEN Einrichtungs-Token an (der alte wird ungueltig).

    Rueckgabe ``(token, gueltig_bis)`` — der KLARTEXT nur hier, fuer den einen
    Kasten beim Start. Der Aufrufer schreibt ihn nicht in Log oder DB.

    Die Zeile ist eine Single-Zeile: ein vorhandener Token wird ueberschrieben,
    nicht ergaenzt. Ein zweiter gueltiger Link waere ein zweiter Generalschluessel.
    """
    from diakronos_app.db import SessionLocal

    token = neuer_token()
    angelegt = jetzt or _jetzt()
    bis = angelegt + timedelta(days=GUELTIG_TAGE)

    with SessionLocal() as sess:
        zeile = sess.get(EinrichtungToken, EINRICHTUNG_TOKEN_NAME, with_for_update=True)
        if zeile is None:
            zeile = EinrichtungToken(name=EINRICHTUNG_TOKEN_NAME)
            sess.add(zeile)
        zeile.token_hash = hash_von(token)
        zeile.gueltig_bis = bis
        zeile.angelegt_am = angelegt
        zeile.aufrufe = 0
        sess.commit()
    return token, bis


def _gueltige_zeile(sess, digest: str, jetzt: datetime) -> EinrichtungToken | None:
    """Die Zeile zu ``digest``, wenn sie zum Zeitpunkt ``jetzt`` noch gilt.

    Erst der Hash-INDEX (eine Zeile per Schluessel), dann der konstante
    Vergleich der Digests und die Ablaufspruefung. Der Vergleich ueber
    ``compare_digest`` ist Absicht, obwohl beide Werte aus derselben Zeile
    stammen: die Regel der Karte lautet „konstantzeitig", und sie soll auch
    dann gelten, wenn hier spaeter einmal anders gesucht wird.
    """
    zeile = sess.scalar(
        select(EinrichtungToken).where(EinrichtungToken.token_hash == digest)
    )
    if zeile is None:
        return None
    if not hmac.compare_digest(str(zeile.token_hash or ""), digest):
        return None
    if zeile.gueltig_bis is None or zeile.gueltig_bis <= jetzt:
        return None
    return zeile


def pruefe_token(token: str, *, jetzt: datetime | None = None, zaehle: bool = True) -> bool:
    """Gilt dieser Token gerade? (schreibfrei, ausser dem Aufruf-Zaehler)

    ``zaehle=False`` laesst den Diagnose-Zaehler unberuehrt (Tests, Vorpruefung).
    Der Zaehler ist KEIN Verbrauch: ein mehrfach geladener Link bleibt gueltig,
    solange er nicht abgelaufen ist oder ersetzt wurde.
    """
    from diakronos_app.db import SessionLocal

    wert = str(token or "").strip()
    if not wert:
        return False
    digest = hash_von(wert)
    with SessionLocal() as sess:
        zeile = _gueltige_zeile(sess, digest, jetzt or _jetzt())
        if zeile is None:
            return False
        if zaehle:
            zeile.aufrufe = int(zeile.aufrufe or 0) + 1
            sess.commit()
    return True


def verbrauche_mit(sess, token: str, *, jetzt: datetime | None = None) -> bool:
    """Prueft UND loescht den Token IN der Transaktion des Aufrufers.

    Gedacht fuer den POST der Einrichtungsseite: Token pruefen, Benutzer +
    Mitglied anlegen, Token loeschen — alles in EINER Transaktion. Scheitert
    das Anlegen, wird zurueckgerollt und der Link bleibt gueltig (niemand
    verliert seinen Zugang, weil ein Feld fehlerhaft war).

    Die Zeile wird dabei gesperrt (``with_for_update``): zwei gleichzeitige
    Absendungen laufen nacheinander, die zweite findet nichts mehr und
    bekommt ``False`` — der Wettlauf endet in „Link ungueltig".
    """
    wert = str(token or "").strip()
    if not wert:
        return False
    digest = hash_von(wert)
    zeile = sess.scalar(
        select(EinrichtungToken)
        .where(EinrichtungToken.token_hash == digest)
        .with_for_update()
    )
    if zeile is None:
        return False
    if not hmac.compare_digest(str(zeile.token_hash or ""), digest):
        return False
    if zeile.gueltig_bis is None or zeile.gueltig_bis <= (jetzt or _jetzt()):
        return False
    sess.delete(zeile)
    sess.flush()
    return True


def gueltiger_token_vorhanden(*, jetzt: datetime | None = None) -> bool:
    """Gibt es gerade einen gueltigen Einrichtungs-Token? (schreibfrei)

    Wird beim Start gebraucht: ein vorhandener Link darf durch einen Neustart
    nicht ungueltig werden. Kein Ablauf-Aufraeumen hier — eine abgelaufene
    Zeile zaehlt als „kein Token", sie wird beim naechsten Erzeugen
    ueberschrieben.
    """
    from diakronos_app.db import SessionLocal

    zeit = jetzt or _jetzt()
    with SessionLocal() as sess:
        zeile = sess.scalar(
            select(EinrichtungToken).where(EinrichtungToken.gueltig_bis > zeit)
        )
    return zeile is not None


def entferne_token() -> None:
    """Loescht den Einrichtungs-Token (z. B. nach dem Anlegen des Admins)."""
    from diakronos_app.db import SessionLocal

    with SessionLocal() as sess:
        zeile = sess.get(EinrichtungToken, EINRICHTUNG_TOKEN_NAME, with_for_update=True)
        if zeile is not None:
            sess.delete(zeile)
            sess.commit()


# ── Kommandozeile (E2) ─────────────────────────────────────────────────────
#
#   python -m diakronos_app.einrichtung link        (im Container)
#   docker compose exec app diakronos einrichtungslink   (Einstiegspunkt
#                                                        backend/bin/diakronos)
#
# Wirksam NUR, solange kein Benutzer existiert. Sonst die Meldung
# „Einrichtung bereits abgeschlossen." und Exitcode 0 (kein Fehler: es ist der
# Normalfall einer eingerichteten Installation).


def _main(argv: list[str] | None = None) -> int:
    import logging
    import sys

    befehl = (list(sys.argv[1:] if argv is None else argv) or ["link"])[0]
    if befehl not in ("link", "einrichtungslink"):
        print(
            "Aufruf: python -m diakronos_app.einrichtung link\n"
            "Erzeugt einen neuen Einrichtungs-Link (nur solange kein "
            "Benutzer existiert) und macht einen alten ungueltig.",
            file=sys.stderr,
        )
        return 2
    # Nur stdout traegt Inhalt (der Kasten); Log-Zeilen wuerden ihn zerstreuen.
    # ZEIT-1: `logging.disable()` ist PROZESSWEIT — es schaltet nicht nur die
    # eigene Ausgabe stumm, sondern jeden Logger danach (im Testlauf: die
    # ganze Suite, `logging.root.manager.disable == CRITICAL`). Deshalb wird
    # der alte Zustand gemerkt und im `finally` zurueckgesetzt; fuer die
    # kurze Laufzeit des Kommandos wirkt es unveraendert.
    alter_zustand = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        from diakronos_app.erstinstallation import neuer_einrichtungslink

        neuer_einrichtungslink(ausgeben=True)
    finally:
        logging.disable(alter_zustand)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
