"""UX1j — Abweichungen lesen, schreiben, zurücksetzen; CSS der Abweichungen.

DIE EINE REGEL DIESES MODULS
----------------------------
Was die Datenbank verlässt und ins CSS geht, ist IMMER durch die Positivliste
(`tokens.py`) gegangen: nur bekannte Namen, nur ganze Zahlen in px, Text wird
erst hier gebaut (``f"{name}: {zahl}px;"``). Eine Altzeile mit fremdem Token
oder fremdem Wert wird beim Lesen verworfen und beim Ausgeben übergangen — sie
kann also weder CSS einschleusen noch die Oberfläche brechen.

Reihenfolge der Prüfung beim Speichern (``speichern``)
------------------------------------------------------
1. Jeder Name steht in der Liste, jeder Wert ist eine ganze px-Zahl im Bereich
   (`tokens.pruefe_wert`).
2. Die Abstands-Skala bleibt aufsteigend — geprüft über ALLE Token, mit den
   neuen Werten und den Standardwerten für die übrigen
   (`tokens.pruefe_skala`).

Damit ist ein halb gespeicherter Satz ausgeschlossen: entweder alle Werte der
Anfrage gelten, oder keiner (die Transaktion bricht ab). Sonst könnte ein
abgelehnter Skalen-Schritt die erste Hälfte der Änderung hinterlassen.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import delete, select

from diakronos_app import db
from diakronos_app.models.gestaltung import GestaltungAbweichung

from . import tokens as T

__all__ = [
    "abweichungen",
    "geltende_werte",
    "speichern",
    "zuruecksetzen",
    "als_css",
    "css_hash",
]

#: Kopfzeile der ausgelieferten Datei. Bewusst KURZ und ohne Werte, die eine
#: Auskunft über den Bestand geben (kein Benutzername, kein Zeitstempel).
_CSS_KOPF = (
    "/* Diakronos — Gestaltung: vom Standard abweichende Maße.\n"
    "   Erzeugt aus den Einstellungen (System Manager). Aenderungen dort,\n"
    "   nicht in dieser Datei. */\n"
)


def _sitzung():
    """Eine Sitzung für diesen Aufruf (Request-Sitzung, sonst eigene)."""
    return db.sitzung_fuer_lesen()


def _zeilen(sess) -> dict[str, GestaltungAbweichung]:
    return {z.token: z for z in sess.scalars(select(GestaltungAbweichung))}


def _gueltig(zeile: GestaltungAbweichung) -> int | None:
    """Der gespeicherte Wert, wenn Name und Wert durch die Liste kommen."""
    token = T.token_oder_none(zeile.token)
    if token is None:
        return None
    if not isinstance(zeile.wert, int) or isinstance(zeile.wert, bool):
        return None
    if zeile.wert < token.minimum or zeile.wert > token.maximum:
        return None
    return zeile.wert


def abweichungen() -> dict[str, int]:
    """Die geltenden Abweichungen ``{token: wert}`` — nur gültige Zeilen."""
    sess, eigene = _sitzung()
    try:
        ergebnis: dict[str, int] = {}
        for name, zeile in _zeilen(sess).items():
            wert = _gueltig(zeile)
            if wert is not None:
                ergebnis[name] = wert
        return ergebnis
    finally:
        if eigene:
            sess.close()


def geltende_werte() -> dict[str, int]:
    """ALLE Token mit ihrem geltenden Wert (Abweichung oder Standard)."""
    return T.wert_oder_standard(abweichungen())


def speichern(werte: dict, *, benutzer: str, jetzt: datetime | None = None) -> dict[str, int]:
    """Werte prüfen und schreiben. Gibt die Abweichungen NACH der Änderung zurück.

    ``werte`` ist ``{token: wert}``; ein Wert gleich dem Standard LÖSCHT die
    Abweichung („gespeichert wie der Standard“ ist keine Abweichung — sonst
    bliebe nach einem späteren Standardwechsel ein alter Wert stehen).

    Wirft ``ValueError`` (Aufrufer: 417) bei unbekanntem Token, ungültigem
    Wert oder gebrochener Skala. Nichts wird dann geschrieben.
    """
    if not isinstance(werte, dict) or not werte:
        raise ValueError("Es wurde kein Wert zum Speichern übergeben.")
    if len(werte) > len(T.TOKEN_NAMEN):
        raise ValueError("Es wurden mehr Werte übergeben, als es einstellbare Maße gibt.")

    geprueft: dict[str, int] = {}
    for name, wert in werte.items():
        geprueft[str(name).strip()] = T.pruefe_wert(name, wert)

    bisher = abweichungen()
    neu = dict(bisher)
    for name, zahl in geprueft.items():
        if zahl == T.standard_zu(name):
            neu.pop(name, None)
        else:
            neu[name] = zahl
    # Die Skala gilt für den GANZEN Satz — auch wenn nur ein Feld kommt.
    T.pruefe_skala(neu)

    zeitpunkt = jetzt or datetime.now()
    sess, eigene = _sitzung()
    try:
        vorhandene = _zeilen(sess)
        for name, zahl in geprueft.items():
            zeile = vorhandene.get(name)
            if zahl == T.standard_zu(name):
                if zeile is not None:
                    sess.delete(zeile)
                continue
            if zeile is None:
                sess.add(
                    GestaltungAbweichung(
                        token=name,
                        wert=zahl,
                        geaendert_von=benutzer,
                        geaendert_am=zeitpunkt,
                    )
                )
            else:
                zeile.wert = zahl
                zeile.geaendert_von = benutzer
                zeile.geaendert_am = zeitpunkt
        if eigene:
            sess.commit()
        else:
            sess.flush()
    except Exception:
        if eigene:
            sess.rollback()
        raise
    finally:
        if eigene:
            sess.close()

    return abweichungen()


def zuruecksetzen(token: str | None = None, *, benutzer: str = "") -> dict[str, int]:
    """Abweichung(en) entfernen — ein Token oder (``None``) ALLE.

    Wirft ``ValueError`` bei unbekanntem Token. Gibt die Abweichungen NACH dem
    Zurücksetzen zurück.
    """
    if token is None:
        sess, eigene = _sitzung()
        try:
            sess.execute(delete(GestaltungAbweichung))
            if eigene:
                sess.commit()
            else:
                sess.flush()
        except Exception:
            if eigene:
                sess.rollback()
            raise
        finally:
            if eigene:
                sess.close()
        return {}

    name = str(token).strip()
    if T.token_oder_none(name) is None:
        raise ValueError("Dieses Maß lässt sich nicht einstellen.")

    sess, eigene = _sitzung()
    try:
        zeile = sess.scalars(
            select(GestaltungAbweichung).where(GestaltungAbweichung.token == name)
        ).first()
        if zeile is not None:
            sess.delete(zeile)
        if eigene:
            sess.commit()
        else:
            sess.flush()
    except Exception:
        if eigene:
            sess.rollback()
        raise
    finally:
        if eigene:
            sess.close()
    return abweichungen()


def als_css() -> str:
    """Die ausgelieferte Datei: ``:root`` mit NUR den Abweichungen.

    Ohne Abweichungen ist das Ergebnis LEER (nicht einmal der Kopf) — die Karte
    verlangt „leer = leere Datei“. Der Kopf erschiene sonst auf jeder Seite,
    obwohl es nichts zu sagen gibt, und die Datei wäre nie leer zu bekommen.

    Die Reihenfolge ist die der Positivliste (stabil, damit der Inhalt und
    damit der ETag bei gleichen Werten immer gleich ist).
    """
    werte = abweichungen()
    if not werte:
        return ""
    zeilen = [f"  {t.name}: {werte[t.name]}px;" for t in T.TOKENS if t.name in werte]
    return _CSS_KOPF + ":root {\n" + "\n".join(zeilen) + "\n}\n"


def css_hash() -> str:
    """Kurzer Inhalts-Hash der CSS-Ausgabe (ETag / ``?v=``)."""
    return hashlib.sha256(als_css().encode("utf-8")).hexdigest()[:12]
