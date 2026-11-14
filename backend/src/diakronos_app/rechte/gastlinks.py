"""R-8: Gast-Links — Wiki und Beitraege fuer Gaeste (Plan Abschnitt 1 und 6).

Manuel 11.11.: Ein **Gast** kommt nur per Passwort-Link hinein, immer mit
Ablauf — Standard **3 Tage**, einstellbar. Freigeben darf, wer den Inhalt
verwalten darf (Rechte-Kern ``verwalten``: HV/MV der Gruppe, bei
Gemeinde-Inhalten der Admin).

Sicherheit:
  * Das Token (32 Byte Zufall) wird NUR einmal beim Anlegen zurueckgegeben;
    gespeichert ist sein SHA-256. Das Passwort liegt als argon2-Hash vor
    (``frappe_compat.passwoerter``).
  * Falsche Passwoerter bremst ein Fensterzaehler je Link (Redis); faellt
    Redis aus, wird gebremst (fail closed).
  * Ungueltig, abgelaufen, widerrufen oder Inhalt geloescht: dieselbe Antwort.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from diakronos_app.db import lesesitzung
from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError, throw
from diakronos_app.rechte import kern
from diakronos_app.rechte.verwaltung import _audit_objekt, _jetzt, _schreibsitzung

logger = logging.getLogger("diakronos_app.rechte.gastlinks")

GAST_TYPEN = ("wiki", "beitrag")
STANDARD_TAGE = 3
MAX_TAGE = 30
#: R-11f: so lange bleibt ein abgelaufener/widerrufener Link in der Liste
#: sichtbar, danach entfernt ihn der taegliche Job (``aufraeumen``).
AUFBEWAHRUNG_TAGE = 30
MIN_PASSWORT = 8
#: Fehlversuche je Link und Fenster, danach gesperrt bis zum Fensterende.
MAX_FEHLVERSUCHE = 5
FENSTER_SEKUNDEN = 15 * 60
SCHLUESSEL_PRAEFIX = "diakronos:gastlink:"


class GastLinkUngueltig(Exception):
    """Link unbekannt, abgelaufen, widerrufen oder Inhalt weg (eine Antwort)."""


class GastLinkGesperrt(Exception):
    """Zu viele falsche Passwoerter fuer diesen Link (vorerst)."""


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode()).hexdigest()


def _redis():
    from redis import Redis

    from diakronos_app.settings import settings

    return Redis.from_url(settings.redis_url, decode_responses=True)


def _gesperrt(token_hash: str, zaehlen: bool) -> bool:
    """Fensterzaehler je Link. ``zaehlen``: einen Fehlversuch mitzaehlen."""
    from redis.exceptions import RedisError

    schluessel = f"{SCHLUESSEL_PRAEFIX}{token_hash[:32]}"
    try:
        client = _redis()
        if zaehlen:
            pipe = client.pipeline(transaction=True)
            pipe.incr(schluessel)
            pipe.expire(schluessel, FENSTER_SEKUNDEN, nx=True)
            anzahl, _ = pipe.execute()
        else:
            anzahl = client.get(schluessel) or 0
    except RedisError:
        logger.warning("gastlinks: Redis-Bremse nicht erreichbar — gesperrt")
        return True
    return int(anzahl) >= MAX_FEHLVERSUCHE


def erstellen(ausfuehrender: str, typ: str, objekt: str, passwort: str,
              tage: int | None = None) -> dict:
    """Gast-Link anlegen. Liefert das Token GENAU EINMAL (danach nur der Hash)."""
    from diakronos_app.frappe_compat import passwoerter
    from diakronos_app.models.rechte import RechteGastlink

    if typ not in GAST_TYPEN:
        throw("Gast-Links gibt es nur für Wiki-Artikel und Beiträge.", ValidationError)
    kern.pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    if len(str(passwort or "")) < MIN_PASSWORT:
        throw(f"Das Passwort braucht mindestens {MIN_PASSWORT} Zeichen.", ValidationError)
    try:
        tage = STANDARD_TAGE if tage in (None, "") else int(tage)
    except (TypeError, ValueError):
        throw("Ungültige Gültigkeitsdauer.", ValidationError)
    if not 1 <= tage <= MAX_TAGE:
        throw(f"Ein Gast-Link gilt 1 bis {MAX_TAGE} Tage.", ValidationError)
    token = secrets.token_urlsafe(32)
    ablauf = _jetzt() + timedelta(days=tage)
    with _schreibsitzung() as sess:
        zeile = RechteGastlink(typ=typ, objekt=objekt, token_hash=_token_hash(token),
                               passwort_hash=passwoerter.neuer_hash(str(passwort)),
                               ablauf=ablauf, erstellt_von=ausfuehrender, erstellt_am=_jetzt())
        sess.add(zeile)
        sess.flush()
        kennung = zeile.id
    _audit_objekt(typ, objekt, f"Gast-Link angelegt (gültig bis {ablauf:%d.%m.%Y %H:%M})")
    return {"success": True, "id": kennung, "token": token, "ablauf": ablauf.isoformat(sep=" ")}


def liste(ausfuehrender: str, typ: str, objekt: str) -> list[dict]:
    """Gast-Links eines Inhalts (ohne Token) — fuer wen ihn verwalten darf."""
    from diakronos_app.models.rechte import RechteGastlink

    kern.pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    jetzt = _jetzt()
    with lesesitzung() as sess:
        zeilen = sess.execute(select(RechteGastlink).where(
            RechteGastlink.typ == typ, RechteGastlink.objekt == objekt
        ).order_by(RechteGastlink.erstellt_am.desc())).scalars().all()
        return [{
            "id": z.id, "ablauf": z.ablauf.isoformat(sep=" "),
            "erstellt_am": z.erstellt_am.isoformat(sep=" ") if z.erstellt_am else None,
            "widerrufen": z.widerrufen_am is not None,
            "aktiv": z.widerrufen_am is None and z.ablauf > jetzt,
        } for z in zeilen]


def widerrufen(ausfuehrender: str, link_id: int) -> dict:
    """Gast-Link sofort ungueltig machen (verwalten am Inhalt)."""
    from diakronos_app.models.rechte import RechteGastlink

    with _schreibsitzung() as sess:
        zeile = sess.get(RechteGastlink, int(link_id))
        if zeile is None:
            throw("Gast-Link nicht gefunden.", ValidationError)
        kern.pruefe(ausfuehrender, kern.VERWALTEN, zeile.typ, zeile.objekt)
        if zeile.widerrufen_am is None:
            zeile.widerrufen_am = _jetzt()
        typ, objekt = zeile.typ, zeile.objekt
    _audit_objekt(typ, objekt, "Gast-Link widerrufen")
    return {"success": True}


def aufraeumen(tage: int = AUFBEWAHRUNG_TAGE) -> int:
    """R-11f: abgelaufene und widerrufene Gast-Links nach ``tage`` Tagen
    endgueltig entfernen (taeglicher Job). Idempotent; liefert die Anzahl."""
    from sqlalchemy import delete, or_

    from diakronos_app.models.rechte import RechteGastlink

    grenze = _jetzt() - timedelta(days=int(tage))
    with _schreibsitzung() as sess:
        ergebnis = sess.execute(delete(RechteGastlink).where(or_(
            RechteGastlink.ablauf < grenze,
            RechteGastlink.widerrufen_am < grenze,
        )))
        return int(ergebnis.rowcount or 0)


def oeffnen(token: str, passwort: str) -> tuple[str, str]:
    """Token + Passwort pruefen -> (typ, objekt). Wirft GastLinkUngueltig /
    GastLinkGesperrt / PermissionError (falsches Passwort)."""
    from diakronos_app.frappe_compat import passwoerter
    from diakronos_app.models.rechte import RechteGastlink, RechteObjekt

    th = _token_hash(token)
    if not token or _gesperrt(th, zaehlen=False):
        if token:
            raise GastLinkGesperrt()
        raise GastLinkUngueltig()
    with lesesitzung() as sess:
        zeile = sess.execute(select(RechteGastlink).where(RechteGastlink.token_hash == th)).scalar_one_or_none()
        if zeile is None or zeile.widerrufen_am is not None or zeile.ablauf <= datetime.utcnow():
            raise GastLinkUngueltig()
        if zeile.typ not in GAST_TYPEN or sess.execute(select(RechteObjekt.id).where(
                RechteObjekt.typ == zeile.typ, RechteObjekt.objekt == zeile.objekt)).first() is None:
            raise GastLinkUngueltig()
        typ, objekt, hash_ = zeile.typ, zeile.objekt, zeile.passwort_hash
    if not passwoerter.pruefe(str(passwort or ""), hash_):
        _gesperrt(th, zaehlen=True)
        throw("Das Passwort stimmt nicht.", PermissionError)
    return typ, objekt


__all__ = [
    "GAST_TYPEN", "GastLinkGesperrt", "GastLinkUngueltig", "MAX_TAGE", "STANDARD_TAGE",
    "erstellen", "liste", "oeffnen", "widerrufen",
]
