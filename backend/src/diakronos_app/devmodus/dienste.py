"""Fachlogik des Dev-Modus: Sitzungen, Ereignisse, Befunde, Bilder, Audio.

Alle Funktionen laufen in der Sitzung des Aufrufers (die API-Schicht oeffnet
sie) und committen NICHT selbst.

Der Dev-Modus kennt keine Szenarien und keine Punkte mehr: der Kern ist der
BEFUND. Ein Befund traegt Text, Art, Wichtigkeit, Status, den Ort (URL/Route/
Seite) und automatisch erfassten Kontext (Umgebung, Element, Fehlerumfeld)
sowie Bilder und optional eine Sprachaufnahme. Das Fehlerumfeld (die letzten
60 s dieser Nutzersitzung) wird beim Anlegen automatisch beigelegt.
"""

from __future__ import annotations

import base64
import binascii
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from diakronos_app.files import binary_content_type
from diakronos_app.models.devmodus import DevBefund, DevEreignis, DevSitzung
from diakronos_app.settings import settings
from diakronos_app.devmodus.einstellungen import (
    ARTEN,
    AUDIO_TYPEN,
    BILD_TYPEN,
    FEHLER_ARTEN,
    FENSTER_SEKUNDEN,
    MAX_AUDIO_BYTES,
    MAX_BEFUND_TEXT,
    MAX_BILD_BYTES,
    MAX_BILDER,
    MAX_PFAD,
    MAX_TEXT,
    STATUS_GUELTIG,
    WICHTIGKEITEN,
)
from diakronos_app.devmodus.redaktion import redigiere, redigiere_felder

#: Wie lange eine Dev-Sitzung ohne Herzschlag als abgelaufen gilt. Danach
#: sammelt die Ueberwachung fuer diesen Nutzer nichts mehr.
SITZUNG_TTL_SEKUNDEN = 900


class DevFehler(Exception):
    """Fachfehler mit Meldungsliste fuer die Oberflaeche."""

    def __init__(self, meldung: str, feld: str = ""):
        super().__init__(meldung)
        self.meldungen = [{"pfad": feld or "/", "code": "ungueltig", "meldung": meldung,
                           "hinweis": ""}]


def jetzt() -> datetime:
    return datetime.now()


def _neu(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


def _speicher_wurzel() -> Path:
    return Path(settings.files_dir).resolve()


# ── Dev-Sitzung (Herzschlag) ───────────────────────────────────────────────

def sitzung_starten(sitzung: Session, benutzer: str) -> dict[str, Any]:
    """Schaltet den Dev-Modus fuer diesen Nutzer ein (legt/erneuert die Sitzung)."""
    laufend = sitzung.get(DevSitzung, benutzer)
    if laufend is None:
        laufend = DevSitzung(benutzer=benutzer, aktiv=1, begonnen=jetzt(),
                             herzschlag=jetzt(), creation=jetzt(), modified=jetzt())
        sitzung.add(laufend)
    else:
        laufend.aktiv = 1
        laufend.herzschlag = jetzt()
        laufend.modified = jetzt()
    sitzung.flush()
    return _sitzung_dict(laufend)


def herzschlag(sitzung: Session, benutzer: str) -> dict[str, Any]:
    """Verlaengert die Dev-Sitzung (die SPA meldet sich regelmaessig)."""
    return sitzung_starten(sitzung, benutzer)


def sitzung_beenden(sitzung: Session, benutzer: str) -> dict[str, Any]:
    """Schaltet den Dev-Modus fuer diesen Nutzer aus."""
    laufend = sitzung.get(DevSitzung, benutzer)
    if laufend is not None:
        laufend.aktiv = 0
        laufend.modified = jetzt()
        sitzung.flush()
    return {"benutzer": benutzer, "aktiv": 0}


def sitzung_aktiv(sitzung: Session, benutzer: str) -> dict[str, Any] | None:
    """Die laufende Dev-Sitzung dieses Nutzers (None, wenn keine laeuft)."""
    laufend = sitzung.get(DevSitzung, benutzer)
    if laufend is None or not laufend.aktiv:
        return None
    grenze = jetzt() - timedelta(seconds=SITZUNG_TTL_SEKUNDEN)
    if laufend.herzschlag is not None and laufend.herzschlag < grenze:
        return None
    return _sitzung_dict(laufend)


def _sitzung_dict(laufend: DevSitzung) -> dict[str, Any]:
    return {
        "benutzer": laufend.benutzer,
        "aktiv": int(laufend.aktiv or 0),
        "begonnen": laufend.begonnen.isoformat() if laufend.begonnen else None,
        "herzschlag": laufend.herzschlag.isoformat() if laufend.herzschlag else None,
    }


# ── Ereignisse (Fehlerumfeld) ──────────────────────────────────────────────

def ereignis_speichern(sitzung: Session, *, benutzer: str, art: str,
                       methode: str | None = None, pfad: str | None = None,
                       status: int | None = None, dauer_ms: int | None = None,
                       request_id: str | None = None, meldung: str | None = None,
                       meldungen: list | None = None,
                       traceback_text: str | None = None) -> str:
    """Speichert ein Ereignis. Alle Texte laufen durch die Redaktion."""
    name = _neu("DME")
    sitzung.add(DevEreignis(
        name=name, benutzer=benutzer, art=art, zeitpunkt=jetzt(),
        methode=(methode or None), pfad=redigiere(pfad)[:MAX_PFAD] if pfad else None,
        status=status, dauer_ms=dauer_ms, request_id=request_id,
        meldung=redigiere(meldung)[:MAX_TEXT] if meldung else None,
        meldungen=redigiere_felder(meldungen) if meldungen else None,
        traceback=redigiere(traceback_text)[:8000] if traceback_text else None,
        erzeugt=jetzt(),
    ))
    return name


def ereignisse(sitzung: Session, benutzer: str | None = None, *,
               seit_sekunden: int | None = None, grenze: int = 200) -> list[dict[str, Any]]:
    """Ereignisse eines Nutzers (oder aller), neueste zuletzt."""
    frage = select(DevEreignis)
    if benutzer:
        frage = frage.where(DevEreignis.benutzer == benutzer)
    if seit_sekunden:
        grenze_zeit = jetzt() - timedelta(seconds=max(1, int(seit_sekunden)))
        frage = frage.where(DevEreignis.zeitpunkt >= grenze_zeit)
    zeilen = sitzung.scalars(
        frage.order_by(DevEreignis.zeitpunkt.desc()).limit(max(1, int(grenze)))).all()
    return [_ereignis_dict(e) for e in reversed(zeilen)]


def fehlerumfeld(sitzung: Session, benutzer: str,
                 seit_sekunden: int = FENSTER_SEKUNDEN) -> list[dict[str, Any]]:
    """Die (echten) Fehler der letzten N Sekunden dieser Nutzersitzung."""
    alle = ereignisse(sitzung, benutzer, seit_sekunden=seit_sekunden, grenze=200)
    return [e for e in alle if e["art"] in FEHLER_ARTEN]


def _ereignis_dict(e: DevEreignis) -> dict[str, Any]:
    return {
        "name": e.name, "art": e.art,
        "zeitpunkt": e.zeitpunkt.isoformat() if e.zeitpunkt else None,
        "methode": e.methode, "pfad": e.pfad, "status": e.status,
        "dauer_ms": e.dauer_ms, "request_id": e.request_id,
        "meldung": e.meldung, "meldungen": e.meldungen or [],
        "traceback": e.traceback,
    }


# ── Bilder / Audio ─────────────────────────────────────────────────────────

def _erkannt_bytes(daten: bytes) -> str | None:
    """Erkennt den Inhaltstyp am Inhalt (nicht am gemeldeten Typ)."""
    return binary_content_type(daten)


def bild_speichern(rohdaten: bytes, typ: str | None = None) -> dict[str, Any]:
    """Prueft und speichert ein Bild. Rueckgabe: Pfad RELATIV zu FILES_DIR."""
    if len(rohdaten) > MAX_BILD_BYTES:
        raise DevFehler("Bild ist zu groß (max. 10 MB).", "/bilder")
    erkannt = _erkannt_bytes(rohdaten)
    if erkannt is None or erkannt not in BILD_TYPEN:
        raise DevFehler("Nur PNG, JPG oder WEBP sind erlaubt.", "/bilder")
    if typ and typ != erkannt:
        raise DevFehler("Dateiinhalt passt nicht zum angegebenen Typ.", "/bilder")
    tag = jetzt().strftime("%Y-%m-%d")
    name = secrets.token_hex(8) + "." + BILD_TYPEN[erkannt]
    ziel = _speicher_wurzel() / "devmodus" / tag
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / name).write_bytes(rohdaten)
    return {"pfad": f"devmodus/{tag}/{name}", "typ": erkannt, "bytes": len(rohdaten)}


def audio_speichern(rohdaten: bytes, typ: str | None = None) -> dict[str, Any]:
    """Prueft und speichert eine Sprachaufnahme. Pfad RELATIV zu FILES_DIR."""
    if len(rohdaten) > MAX_AUDIO_BYTES:
        raise DevFehler("Aufnahme ist zu groß (max. 25 MB).", "/audio")
    erkannt = _erkannt_bytes(rohdaten)
    # MediaRecorder liefert je Browser webm/ogg/mp4. Ist die Erkennung
    # unsicher (z. B. webm ohne Magic-Treffer), entscheidet der gemeldete Typ.
    auswahl = erkannt if erkannt in AUDIO_TYPEN else (typ if typ in AUDIO_TYPEN else None)
    if auswahl is None:
        raise DevFehler("Nur WEBM, OGG oder M4A sind erlaubt.", "/audio")
    tag = jetzt().strftime("%Y-%m-%d")
    name = secrets.token_hex(8) + "." + AUDIO_TYPEN[auswahl]
    ziel = _speicher_wurzel() / "devmodus" / tag
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / name).write_bytes(rohdaten)
    return {"pfad": f"devmodus/{tag}/{name}", "typ": auswahl, "bytes": len(rohdaten)}


def aus_base64(daten: str) -> tuple[bytes, str | None]:
    """Zerlegt eine Data-URL oder reines Base64 in Bytes und gemeldeten Typ."""
    roh = daten or ""
    typ = None
    if roh.startswith("data:"):
        kopf, _, rest = roh.partition(",")
        if ";" in kopf:
            typ = kopf[5:].split(";")[0]
        roh = rest
    try:
        return base64.b64decode(roh, validate=True), typ
    except (binascii.Error, ValueError):
        raise DevFehler("Die Daten sind unlesbar.", "/daten") from None


_BILD_PFAD = re.compile(r"devmodus/\d{4}-\d{2}-\d{2}/[0-9a-f]{16}\.(png|jpg|webp)")
_AUDIO_PFAD = re.compile(r"devmodus/\d{4}-\d{2}-\d{2}/[0-9a-f]{16}\.(webm|ogg|m4a)")


def _bilder_pruefen(eintraege: list | None) -> list[str]:
    pfade: list[str] = []
    for eintrag in (eintraege or [])[:MAX_BILDER]:
        pfad = (eintrag or {}).get("pfad") if isinstance(eintrag, dict) else eintrag
        if not pfad:
            continue
        # Nur Pfade, die WIR vergeben haben (kein Pfad aus dem Browser).
        if not _BILD_PFAD.fullmatch(str(pfad)):
            raise DevFehler("Unbekannter Bildpfad.", "/bilder")
        if not (_speicher_wurzel() / pfad).is_file():
            raise DevFehler("Bild wurde nicht gefunden.", "/bilder")
        pfade.append(str(pfad))
    return pfade


def bild_pfad(pfad: str | None) -> Path | None:
    """Wandelt einen von UNS vergebenen Bildpfad in einen Dateipfad um.

    Nur ``devmodus/<datum>/<name>`` mit dem Muster aus ``_BILD_PFAD`` ist
    erlaubt (kein Pfad aus dem Browser, kein Ausbruch aus FILES_DIR). Ist die
    Datei nicht vorhanden, kommt ``None`` zurueck.
    """
    if not pfad or not _BILD_PFAD.fullmatch(str(pfad)):
        return None
    ziel = (_speicher_wurzel() / str(pfad)).resolve()
    if ziel.parent.parent != _speicher_wurzel() / "devmodus" or not ziel.is_file():
        return None
    return ziel


def _audio_pruefen(eintrag: dict | None) -> dict | None:
    if not eintrag:
        return None
    pfad = (eintrag or {}).get("pfad")
    if not pfad:
        return None
    if not _AUDIO_PFAD.fullmatch(str(pfad)):
        raise DevFehler("Unbekannter Audiopfad.", "/audio")
    if not (_speicher_wurzel() / pfad).is_file():
        raise DevFehler("Aufnahme wurde nicht gefunden.", "/audio")
    return {"pfad": str(pfad), "typ": (eintrag or {}).get("typ")}


# ── Befunde ────────────────────────────────────────────────────────────────

#: Laenge des Listentitels (UXM-R13): die Liste zeigt eine Zeile.
TITEL_LAENGE = 120


def befund_titel(text: str, *, seite: str | None = None, route: str | None = None,
                 seitentitel: str | None = None) -> str:
    """Listentitel eines Befunds (UXM-R13).

    Reihenfolge: erste Zeile des Kommentars -> „<Element> – <Route>“ -> Seite/
    Fenstertitel -> „Befund“. Der Fenstertitel allein taugt nicht: er ist auf
    jeder Seite „Meine Gemeinde“, die Liste zeigte 23-mal denselben Titel.
    """
    zeile = next((z.strip() for z in (text or "").splitlines() if z.strip()), "")
    if zeile:
        return zeile[:TITEL_LAENGE]
    if seite and route:
        return f"{seite} – {route}"[:TITEL_LAENGE]
    return (seite or seitentitel or route or "Befund")[:TITEL_LAENGE]


def befund_anlegen(sitzung: Session, benutzer: str, *,
                   text: str = "", art: str = "fehler", wichtigkeit: str = "mittel",
                   url: str | None = None, route: str | None = None,
                   seitentitel: str | None = None, seite: str | None = None,
                   viewport: str | None = None, bildschirm: str | None = None,
                   geraet: str | None = None, browser: str | None = None,
                   theme: str | None = None, sprache: str | None = None,
                   element: dict | None = None, bilder: list | None = None,
                   audio: dict | None = None,
                   fehlerumfeld: list | None = None) -> dict[str, Any]:
    """Legt einen Befund an. Das Fehlerumfeld wird automatisch beigelegt."""
    sauber = (text or "").strip()
    if len(sauber) > MAX_BEFUND_TEXT:
        raise DevFehler("Der Kommentar ist zu lang.", "/text")
    if art not in ARTEN:
        raise DevFehler("Unbekannte Art.", "/art")
    if wichtigkeit not in WICHTIGKEITEN:
        raise DevFehler("Unbekannte Wichtigkeit.", "/wichtigkeit")

    pfade = _bilder_pruefen(bilder)
    audio_sauber = _audio_pruefen(audio)

    # Element-Kontext redigieren (Passwort-/versteckte Felder NIE speichern).
    element_sauber = redigiere_felder(element) if element else None
    if isinstance(element_sauber, dict):
        element_sauber.pop("__redigiert", None)

    umfeld = fehlerumfeld if fehlerumfeld is not None else fehlerumfeld_der_letzten(
        sitzung, benutzer)

    titel = befund_titel(sauber, seite=seite, route=route, seitentitel=seitentitel)
    neu = DevBefund(
        name=_neu("DMB"), benutzer=benutzer, text=sauber, art=art,
        wichtigkeit=wichtigkeit, status="offen", titel=titel,
        url=redigiere(url)[:1000] if url else None,
        route=(route or "")[:300] or None,
        seitentitel=(seitentitel or "")[:300] or None,
        seite=(seite or "")[:200] or None,
        viewport=(viewport or "")[:40] or None,
        bildschirm=(bildschirm or "")[:40] or None,
        geraet=(geraet or "")[:300] or None,
        browser=(browser or "")[:300] or None,
        theme=(theme or "")[:20] or None,
        sprache=(sprache or "")[:20] or None,
        element=element_sauber, fehlerumfeld=umfeld,
        bilder=pfade, audio=audio_sauber,
        zeitpunkt=jetzt(), creation=jetzt(), modified=jetzt(),
    )
    sitzung.add(neu)
    sitzung.flush()
    return befund_als_dict(neu)


def fehlerumfeld_der_letzten(sitzung: Session, benutzer: str) -> list[dict[str, Any]]:
    """Fehlerumfeld ohne die eigene Befund-Anlage (siehe Middleware-Ausnahme)."""
    return fehlerumfeld(sitzung, benutzer)


def befunde(sitzung: Session, *, status: str | None = None,
            seite: str | None = None, art: str | None = None,
            benutzer: str | None = None, grenze: int = 200) -> list[dict[str, Any]]:
    frage = select(DevBefund)
    if status and status != "alle":
        frage = frage.where(DevBefund.status == status)
    if seite:
        frage = frage.where(DevBefund.seite == seite)
    if art:
        frage = frage.where(DevBefund.art == art)
    if benutzer:
        frage = frage.where(DevBefund.benutzer == benutzer)
    zeilen = sitzung.scalars(
        frage.order_by(DevBefund.zeitpunkt.desc()).limit(max(1, int(grenze)))).all()
    return [befund_als_dict(b) for b in zeilen]


def befund_holen(sitzung: Session, name: str) -> dict[str, Any]:
    befund = sitzung.get(DevBefund, name)
    if befund is None:
        raise DevFehler("Befund nicht gefunden.", "/name")
    return befund_als_dict(befund)


def befund_status(sitzung: Session, name: str, status: str) -> dict[str, Any]:
    if status not in STATUS_GUELTIG:
        raise DevFehler("Unbekannter Status.", "/status")
    befund = sitzung.get(DevBefund, name)
    if befund is None:
        raise DevFehler("Befund nicht gefunden.", "/name")
    befund.status = status
    befund.modified = jetzt()
    sitzung.flush()
    return {"name": befund.name, "status": befund.status}


def befund_loeschen(sitzung: Session, name: str) -> dict[str, Any]:
    """Loescht einen Befund samt Bildern/Audio von der Platte."""
    befund = sitzung.get(DevBefund, name)
    if befund is None:
        raise DevFehler("Befund nicht gefunden.", "/name")
    entfernt = 0
    for pfad in (befund.bilder or []) + ([befund.audio["pfad"]] if befund.audio else []):
        ziel = _speicher_wurzel() / pfad
        try:
            if ziel.is_file():
                ziel.unlink()
                entfernt += 1
        except OSError:
            pass
    sitzung.delete(befund)
    sitzung.flush()
    return {"name": name, "dateien": entfernt}


def befund_als_dict(b: DevBefund) -> dict[str, Any]:
    return {
        "name": b.name, "benutzer": b.benutzer, "text": b.text, "art": b.art,
        "wichtigkeit": b.wichtigkeit, "status": b.status, "titel": b.titel,
        "url": b.url, "route": b.route, "seitentitel": b.seitentitel, "seite": b.seite,
        "viewport": b.viewport, "bildschirm": b.bildschirm, "geraet": b.geraet,
        "browser": b.browser, "theme": b.theme, "sprache": b.sprache,
        "element": b.element or {}, "fehlerumfeld": b.fehlerumfeld or [],
        "bilder": b.bilder or [], "audio": b.audio,
        "zeitpunkt": b.zeitpunkt.isoformat() if b.zeitpunkt else None,
        "creation": b.creation.isoformat() if b.creation else None,
        "modified": b.modified.isoformat() if b.modified else None,
    }


def zaehle(sitzung: Session) -> dict[str, int]:
    """Kennzahlen fuer die Uebersicht der Dev-Befunde."""
    alle = sitzung.scalars(select(DevBefund)).all()
    return {
        "gesamt": len(alle),
        "offen": len([b for b in alle if b.status == "offen"]),
        "an_claude": len([b for b in alle if b.status == "an_claude"]),
        "behoben": len([b for b in alle if b.status == "behoben"]),
        "verworfen": len([b for b in alle if b.status == "verworfen"]),
        "bilder": sum(len(b.bilder or []) for b in alle),
    }


def aufraeumen(sitzung: Session, tage: int = 30) -> dict[str, Any]:
    """Entfernt Ereignisse aelter als ``tage`` (Befunde bleiben erhalten)."""
    grenze = jetzt() - timedelta(days=max(1, int(tage)))
    alle = sitzung.scalars(select(DevEreignis).where(DevEreignis.zeitpunkt < grenze)).all()
    for e in alle:
        sitzung.delete(e)
    sitzung.flush()
    return {"ereignisse": len(alle), "grenze": grenze.isoformat()}


def alte_testsuite_uebernehmen(sitzung: Session) -> dict[str, int]:
    """Uebernimmt ts_befund/ts_kommentar in die Dev-Ablage (falls vorhanden).

    Wird normalerweise von der Migration erledigt; diese Funktion ist fuer den
    Fall vorhanden, dass eine Installation die Tabellen noch traegt.
    """
    from sqlalchemy import inspect as sa_inspect

    namen = set(sa_inspect(sitzung.get_bind()).get_table_names())
    if "ts_befund" not in namen and "ts_kommentar" not in namen:
        return {"befunde": 0, "kommentare": 0}
    from sqlalchemy import text as sa_text

    uebernommen = {"befunde": 0, "kommentare": 0}
    if "ts_befund" in namen:
        for zeile in sitzung.execute(sa_text(
                "SELECT name, seite, titel, meldung, status, gemeldet_von, zeitpunkt "
                "FROM ts_befund")).mappings():
            if sitzung.get(DevBefund, f"alt-{zeile['name']}") is not None:
                continue
            sitzung.add(DevBefund(
                name=f"alt-{zeile['name']}"[:140], benutzer=zeile["gemeldet_von"],
                text=zeile["meldung"], art="fehler", wichtigkeit="mittel",
                status=_status_uebernehmen(zeile["status"]), titel=zeile["titel"],
                url=None, route=None, seitentitel=None, seite=zeile["seite"],
                zeitpunkt=_zeit(zeile["zeitpunkt"]), creation=jetzt(), modified=jetzt(),
            ))
            uebernommen["befunde"] += 1
    if "ts_kommentar" in namen:
        for zeile in sitzung.execute(sa_text(
                "SELECT name, text, seite, route, benutzer, bilder, zeitpunkt "
                "FROM ts_kommentar")).mappings():
            if sitzung.get(DevBefund, f"altk-{zeile['name']}") is not None:
                continue
            sitzung.add(DevBefund(
                name=f"altk-{zeile['name']}"[:140], benutzer=zeile["benutzer"],
                text=zeile["text"], art="frage", wichtigkeit="mittel", status="offen",
                titel=zeile["seite"] or zeile["route"], url=None, route=zeile["route"],
                seitentitel=None, seite=zeile["seite"],
                bilder=[], zeitpunkt=_zeit(zeile["zeitpunkt"]),
                creation=jetzt(), modified=jetzt(),
            ))
            uebernommen["kommentare"] += 1
    sitzung.flush()
    return uebernommen


def _status_uebernehmen(alt: str | None) -> str:
    return alt if alt in STATUS_GUELTIG else "offen"


def _zeit(wert) -> datetime | None:
    if wert is None:
        return None
    if isinstance(wert, datetime):
        return wert
    try:
        return datetime.fromisoformat(str(wert))
    except ValueError:
        return None


__all__ = [
    "DevFehler", "jetzt", "sitzung_starten", "sitzung_beenden", "sitzung_aktiv",
    "herzschlag", "ereignis_speichern", "ereignisse", "fehlerumfeld",
    "bild_speichern", "audio_speichern", "aus_base64", "befund_anlegen",
    "befunde", "befund_holen", "befund_status", "befund_loeschen", "bild_pfad",
    "befund_titel",
    "befund_als_dict", "zaehle", "aufraeumen", "alte_testsuite_uebernehmen",
]
