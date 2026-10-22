"""ST2 — Lieder pflegen: Titel/Buch/Seite, Material (Noten/Audio/Notensatz), Tags.

Diese Bausteine arbeiten auf den **Psalmos**-Tabellen (``Lied``, ``Liedfassung``,
``Lied Material``) und den gemeindeweiten Merkmalen (``pr_merkmal`` /
``pr_merkmal_wert``). Es entstehen bewusst KEINE Doppelstrukturen: ein Lied hat
genau eine Wahrheit (Psalmos), Material haengt an der Standardfassung, Tags sind
deklarierte Merkmalswerte der Sammlung ``lieder``.

Die Datei enthaelt nur reine Hilfsfunktionen ohne Session-/Rechte-Zugriff; die
Dienste in ``dienste.py`` setzen Kontext (Rechte, Plantyp) und rufen sie auf.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.settings import settings

# ── Material-Arten ─────────────────────────────────────────────────────────

#: Erlaubte Material-Arten mit ihren zulaessigen Dateiendungen. ``audio`` hat
#: ein eigenes, hoeheres Groessenlimit (siehe ``settings.max_upload_bytes_audio``).
MATERIAL_ARTEN: dict[str, tuple[str, ...]] = {
    "noten_pdf": (".pdf",),
    "audio": (".mp3", ".m4a", ".ogg", ".wav"),
    "musescore": (".mscz", ".mscx"),
    "musicxml": (".musicxml", ".mxl"),
}

#: MIME-Typen je Art (fuer ``SichererAnhang.dateityp`` und die Auslieferung).
MATERIAL_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".mscz": "application/zip",   # MuseScore 4 = ZIP-Container
    ".mscx": "application/xml",   # MuseScore 3 = XML
    ".musicxml": "application/xml",
    ".mxl": "application/zip",    # komprimiertes MusicXML
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def material_art_pruefen(art: Any) -> str:
    """Material-Art validieren — unbekannte Arten sind ein Fachfehler."""
    if not isinstance(art, str) or art not in MATERIAL_ARTEN:
        raise ValidationError(
            "Unbekannte Material-Art. Erlaubt: " + ", ".join(sorted(MATERIAL_ARTEN)) + ".")
    return art


def dateiname_saeubern(name: str) -> str:
    """Dateinamen saeubern (kein Pfadanteil, keine Sonderzeichen)."""
    base = os.path.basename((name or "").replace("\\", "/")).strip().lstrip(".")
    base = _SAFE_NAME.sub("_", base).strip("._")
    return (base or "datei")[:180]


def endung_von(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()


def datei_pruefen(art: str, name: str, raw: bytes) -> str:
    """Endung UND Inhalt pruefen; liefert den MIME-Typ.

    - Die Endung muss zur Art passen (z. B. ``.mp3`` bei ``audio``).
    - Wo ein eindeutiger Magic-Header existiert, muss er stimmen:
      PDF ``%PDF-``, WAV ``RIFF…WAVE``, OGG ``OggS``, ZIP-basiert
      (``.mscz``/``.mxl``) ``PK\\x03\\x04``. MP3/M4A/XML haben mehrere
      zulaessige Kopfdaten — dort genuegt eine plausible Grundform.
    """
    art = material_art_pruefen(art)
    if not raw:
        raise ValidationError("Leere Datei.")
    endung = endung_von(name)
    if endung not in MATERIAL_ARTEN[art]:
        raise ValidationError(
            f"Dateiendung {endung or '(keine)'!r} passt nicht zur Material-Art {art!r}.")

    if endung == ".pdf" and not raw.startswith(b"%PDF-"):
        raise ValidationError("Kein gültiges PDF (Kopfzeile %PDF- fehlt).")
    if endung == ".wav" and not (raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"):
        raise ValidationError("Keine gültige WAV-Datei (RIFF/WAVE fehlt).")
    if endung == ".ogg" and not raw.startswith(b"OggS"):
        raise ValidationError("Keine gültige Ogg-Datei (OggS fehlt).")
    if endung in (".mscz", ".mxl") and raw[:2] != b"PK":
        raise ValidationError("Notensatz-Datei ist kein ZIP-Container (PK fehlt).")
    if endung == ".mp3" and raw[:3] != b"ID3" and raw[:2] not in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\xff\xfa"):
        raise ValidationError("Keine gültige MP3-Datei (ID3/Frame fehlt).")
    if endung == ".m4a":
        # MP4-Container: '....ftyp' in den ersten 12 Bytes.
        if len(raw) < 12 or raw[4:8] != b"ftyp":
            raise ValidationError("Keine gültige M4A-Datei (ftyp fehlt).")
    if endung == ".mscx" and b"<" not in raw[:512]:
        raise ValidationError("Keine gültige MuseScore-XML-Datei.")
    if endung == ".musicxml" and b"<" not in raw[:512]:
        raise ValidationError("Keine gültige MusicXML-Datei.")
    return MATERIAL_MIME[endung]


def max_bytes(art: str) -> int:
    """Groessenlimit je Art: Audio konfigurierbar, sonst allgemeines Limit."""
    if art == "audio":
        return int(getattr(settings, "max_upload_bytes_audio", 0)
                   or settings.max_upload_bytes)
    return settings.max_upload_bytes


def speicher_name(original: str) -> str:
    return f"{uuid.uuid4().hex}-{dateiname_saeubern(original)}"


# ── LN1: Quelle eines Liedes (Liederbuch / Kopie / ohne Angabe) ─────────────

#: Erlaubte Quellen-Werte. EINE Wahrheit fuer die Anzeige:
#:   'buch'  = Liederbuch/Heft (mit Nummer und/oder Seite)
#:   'kopie' = Kopie/Einzelblatt (lose, KEINE Nummer)
#:   'ohne'  = ohne Angabe (noch nichts gepflegt)
QUELLEN: tuple[str, ...] = ("buch", "kopie", "ohne")

#: Lesbare Beschriftungen fuer Meldungen/Tests (UI nutzt eigene Texte).
QUELLE_TEXTE: dict[str, str] = {
    "buch": "Liederbuch",
    "kopie": "Kopie / Einzelblatt",
    "ohne": "Ohne Angabe",
}

#: Werte, die als "lose Kopie / Einzelblatt" gelten (case-insensitiv).
_KOPIE_WERTE = {"kop", "kopie", "kopien", "einz", "einzelblatt", "blatt"}

_NR = re.compile(r"\bnr\.?\s*([0-9]+[a-zA-Z]?)\b", re.IGNORECASE)
_SEITE = re.compile(r"\bs\.?\s*([0-9]+[a-zA-Z]?)\b", re.IGNORECASE)


def quelle_pruefen(quelle: Any) -> str:
    """Quelle validieren — unbekannte Werte sind ein Fachfehler."""
    if not isinstance(quelle, str) or quelle not in QUELLEN:
        raise ValidationError(
            "Unbekannte Quelle. Erlaubt: " + ", ".join(QUELLEN) + ".")
    return quelle


def zerlege_quelle(roh: Any) -> dict[str, str]:
    """Zerlegt einen Alt-Wert der ``gesangbuch_nummer`` in seine Bestandteile.

    Liefert ein Dict ``{"quelle", "buch", "nummer", "seite"}``. Regeln
    (case-insensitiv, führende/abschliessende Leerzeichen ignoriert):

      * ``KOP``/``Kop``/``Kopie`` …                     -> quelle 'kopie', alles leer
      * ``BUCH Nr. 123``                                -> quelle 'buch', buch 'BUCH', nummer '123'
      * ``BUCH S. 150``                                 -> quelle 'buch', buch 'BUCH', seite '150'
      * reines ``WH`` (kein Nr./S.)                     -> quelle 'buch', buch 'WH', ohne Nummer/Seite
      * leer                                            -> quelle 'ohne'
      * sonst (z. B. ``Nr. 42`` ohne Buch, ``WH 1297``) -> quelle 'buch',
        originaltext als Buch uebernommen (nichts verlieren).

    Der Originaltext wird NIE verworfen: was nicht sauber zuzuordnen ist,
    landet als Buch und bleibt so sichtbar.
    """
    text = ("" if roh is None else str(roh)).strip()
    if not text:
        return {"quelle": "ohne", "buch": "", "nummer": "", "seite": ""}

    # Lose Kopie / Einzelblatt: reiner KOP-Wert oder "KOP Nr. x" (Nr. entfaellt
    # hier bewusst — eine Kopie hat keine Buchnummer).
    klein = text.lower()
    if klein in _KOPIE_WERTE:
        return {"quelle": "kopie", "buch": "", "nummer": "", "seite": ""}

    m_nr = _NR.search(text)
    m_seite = _SEITE.search(text)
    if m_nr or m_seite:
        # Alles vor dem ersten "Nr."/"S." ist der Buch-/Heftname. Fehlt er
        # (z. B. nur "Nr. 42"), bleibt das Buch leer.
        schnitt = min([m.start() for m in (m_nr, m_seite) if m])
        buch = text[:schnitt].strip(" ,;/|-")
        return {
            "quelle": "buch",
            "buch": buch,
            "nummer": m_nr.group(1) if m_nr else "",
            "seite": m_seite.group(1) if m_seite else "",
        }

    # "KOP" mit Zusatz (z. B. "KOP Nr. 16" faellt oben schon als buch durch —
    # das ist gewollt: eine Nummer macht es zu einem Buch-Eintrag). Hier nur
    # der reine Kopie-Fall ueber Teilstring-Erkennung.
    if klein in _KOPIE_WERTE or klein.startswith(("kop ", "kopie ")):
        return {"quelle": "kopie", "buch": "", "nummer": "", "seite": ""}

    # Reiner Buchname ohne Nummer/Seite (z. B. "WH").
    return {"quelle": "buch", "buch": text, "nummer": "", "seite": ""}


def anzeige_text(quelle: Any, buch: Any, nummer: Any, seite: Any,
                 titel: Any = "") -> str:
    """Kurze, menschenlesbare Kennung eines Liedes (ohne "Nr." wo es keine gibt).

      * Kopie            -> "Kopie"
      * Buch + Nr.       -> "JN 1297"
      * Buch + Seite     -> "WH S. 150"
      * ohne Angabe      -> "" (Aufrufer zeigt den Titel)
    """
    q = quelle if quelle in QUELLEN else "ohne"
    buch = ("" if buch is None else str(buch)).strip()
    nummer = ("" if nummer is None else str(nummer)).strip()
    seite = ("" if seite is None else str(seite)).strip()
    if q == "kopie":
        return "Kopie"
    if q == "ohne":
        return ""
    teile = [buch] if buch else []
    if nummer:
        teile.append(nummer)
    if seite:
        teile.append(f"S. {seite}")
    if not teile:
        return ""
    # Nur Buch + Nummer ohne "Nr."-Praefix: "JN 1297", "WH S. 150".
    if seite and len(teile) >= 2 and not nummer:
        return f"{teile[0]} S. {seite}"
    return " ".join(teile)


# ── Tags / Auswahlwerte ─────────────────────────────────────────────────────

#: Merkmals-Arten mit frei pflegbaren Auswahl-/Tag-Werten.
WERT_ARTEN = ("auswahl", "tag")


def wert_hinzufuegen(definition: dict[str, Any], wert: str) -> dict[str, Any]:
    """Auswahl-/Tag-Wert zur Merkmals-Definition hinzufuegen (idempotent)."""
    wert = (wert or "").strip()
    if not wert:
        raise ValidationError("Der Wert darf nicht leer sein.")
    neu = dict(definition or {})
    werte = list(neu.get("werte") or [])
    if wert in werte:
        return neu
    werte.append(wert)
    neu["werte"] = werte
    return neu


def wert_umbenennen(definition: dict[str, Any], alt: str, neu: str) -> dict[str, Any]:
    """Wert umbenennen; blosse Umbenennung — Zuordnungen bleiben gueltig.

    Die Zuordnungen liegen als **Wert** in ``pr_merkmal_wert.wert``; die
    Aufrufer aktualisieren sie mit (``werte_umbenennen``), damit vorhandene
    Lieder den neuen Namen tragen.
    """
    neu = (neu or "").strip()
    if not neu:
        raise ValidationError("Der neue Wert darf nicht leer sein.")
    d = dict(definition or {})
    werte = list(d.get("werte") or [])
    if alt not in werte:
        raise ValidationError(f"Der Wert {alt!r} ist nicht vorhanden.")
    if neu != alt and neu in werte:
        raise ValidationError(f"Der Wert {neu!r} ist bereits vorhanden.")
    d["werte"] = [neu if w == alt else w for w in werte]
    return d


def wert_entfernen(definition: dict[str, Any], wert: str) -> dict[str, Any]:
    """Wert entfernen; die Aufrufer loeschen/bereinigen Zuordnungen mit."""
    d = dict(definition or {})
    werte = list(d.get("werte") or [])
    if wert not in werte:
        raise ValidationError(f"Der Wert {wert!r} ist nicht vorhanden.")
    d["werte"] = [w for w in werte if w != wert]
    return d
