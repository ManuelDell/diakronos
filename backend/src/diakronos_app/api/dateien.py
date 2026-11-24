"""DATEIEN-3: Gruppendateien — Liste, Hochladen, Ausliefern, Papierkorb.

Konzept ``DATEIEN-KONZEPT.md`` (Abschnitte 1/S1, 2, 3, 4) und die
Entscheidungen Manuel 23.11.2026:

* **F3** Untergruppen haben EIGENE Dateien (``untergruppe`` gesetzt).
* **F4** HV/MV (in der Untergruppe auch GL) dürfen FREMDE Dateien löschen; die
  eigene darf jede hochladende Person löschen. Die Rückfrage ist Sache der
  Oberfläche.
* **F5** Löschen = Papierkorb (``geloescht_am``/``geloescht_von``),
  Wiederherstellen möglich; ENDGÜLTIG löscht der Job aus DATEIEN-5.
* **F8** Alle Dokumentarten außer Ausführbarem — ``ablage.RICHTLINIE_SPERR``.
* **F9** Größengrenze wie im Chat (``chat_anhanggrenze.anhang_max_bytes``),
  KEIN Tageslimit.

RECHTE: Es gibt EIN Rechtesystem. Jede Frage geht über
``rechte.kern.darf/pruefe`` mit ``typ="gruppe_datei"`` — LESEN (Liste,
Ausliefern), ANLEGEN (Hochladen), ANPINNEN (anpinnen/lösen), SCHREIBEN
(umbenennen/löschen, ``besitzer`` = ``angelegt_von`` IMMER mitgegeben) und
MODERIEREN (Papierkorb-LISTE und Wiederherstellen — wer dort wegräumen darf).
Untergruppen-Dateien geben ``untergruppe=<UG>`` UND ``gruppe=<Hauptgruppe>`` mit.
Ist das Modul ``dateien`` in der Gruppe aus, sagt der Kern NEIN und der Endpunkt
antwortet mit der normalen Rechte-Meldung.

AUSLIEFERN: JEDE Fehlerart (gibt es nicht / darf nicht / im Papierkorb /
Ablage weg) ergibt DIESELBE 404 — der Endpunkt verrät nicht, ob es eine Datei
gibt. Dieselbe 404 gilt auch für anpinnen/umbenennen/löschen/wiederherstellen:
zuerst wird geprüft, ob die Datei für den Aufrufer überhaupt SICHTBAR ist
(LESEN am Raum); erst danach entscheidet die eigentliche Aktion (403).

KEIN ``RechteObjekt`` je Datei (Review DATEIEN-3/R1): der Kern geht für
``gruppe_datei`` direkt in ``_darf_raum`` und fragt nie nach einem Eintrag —
ein Eintrag je Datei würde nur Waisen hinterlassen. Alle Rechte kommen aus den
Argumenten (``gruppe``/``untergruppe``/``besitzer``).

BESITZER: ``angelegt_von`` ist der Besitzer. Ist es NULL (Konto gelöscht oder
anonymisiert), gibt es KEINEN Besitzer — der Kern liest das als „fremd“ (Leitung
JA, Mitglied NEIN, ``besitzer_fehlt``). Die Datei gehört damit weiter der
Gruppe und bleibt pflegbar.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from diakronos_app import ablage
from diakronos_app import rechte
#: Die Sitzungs-Factory wird über das MODUL ``db`` benutzt (``dbmod.SessionLocal``),
#: NICHT als gebundener Name: die Test-Fixture ``patched_db`` biegt das Modul-
#: Attribut um, ein ``from … import SessionLocal`` bliebe auf der Betriebs-DB
#: stehen (dasselbe Muster wie ``api/chat.py``).
from diakronos_app import db as dbmod
from diakronos_app.chat_anhanggrenze import anhang_max_bytes
from diakronos_app.db import als_aktuelle_sitzung
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.dateien import (
    GDT_DATEI_PRAEFIX,
    GDT_NAME_MAX,
    GDT_SPEICHER_PRAEFIX,
    GruppeDatei,
    GruppeDateiEntsorgung,
)

logger = logging.getLogger(__name__)

#: Die eine Meldung für einen nicht auslieferbaren Eintrag (alle Fehlerarten).
NICHT_GEFUNDEN = "Datei nicht gefunden."

#: Höchstzahl der Aufträge, die ein Request nach einem Löschen selbst versucht
#: (wie ``api.chat.ENTSORGUNG_JE_ANFRAGE``).
ENTSORGUNG_JE_ANFRAGE = 3
#: Zeitlimit für den Sofort-Versuch (nur Ablagen mit Netz kennen eines).
ENTSORGUNG_ZEITLIMIT_SEKUNDEN = 2.0

__all__ = [
    "ENTSORGUNG_JE_ANFRAGE",
    "ENTSORGUNG_ZEITLIMIT_SEKUNDEN",
    "NICHT_GEFUNDEN",
    "anpinnen",
    "datei",
    "einstellung_setzen",
    "einstellungen",
    "hochladen",
    "liste",
    "loeschen",
    "papierkorb",
    "umbenennen",
    "wiederherstellen",
]


# ── Kleine Helfer ───────────────────────────────────────────────────────────


def _jetzt() -> datetime:
    """Jetzt als Wandzeit der Gemeinde, OHNE Zeitzone (wie ``api.chat``)."""
    from diakronos_app.zeit import jetzt_wanduhr

    return jetzt_wanduhr()


def _benutzer() -> str:
    return str(session.user or "")


def _kennung() -> str:
    from uuid import uuid4

    return f"{GDT_DATEI_PRAEFIX}{uuid4().hex}"


def _wahr(wert: Any) -> bool:
    """Formular-/JSON-Wahrheitswert (``true``, ``1``, ``"true"``)."""
    if isinstance(wert, bool):
        return wert
    return str(wert or "").strip().lower() in ("1", "true", "ja", "yes", "on")


def _nicht_gefunden():
    """Dieselbe 404 für JEDE Fehlerart (unbekannt, kein Recht, Papierkorb)."""
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    return DoesNotExistError(NICHT_GEFUNDEN)


def _pruefe(benutzer: str, aktion: str, *, gruppe: str | None,
            untergruppe: str | None = None, besitzer: str | None = None) -> None:
    """DIE Rechtefrage — immer über den Kern, nie eine eigene Regel.

    ``besitzer`` MUSS bei SCHREIBEN mitgegeben werden (``angelegt_von``); ohne
    Besitzer sagt der Kern NEIN (fail closed).
    """
    rechte.pruefe(benutzer, aktion, "gruppe_datei", None,
                  gruppe=gruppe or None, untergruppe=untergruppe or None,
                  besitzer=besitzer)


def _raum(gruppe: str, untergruppe: str | None) -> tuple[str, str | None]:
    """Geprüfter (Gruppe, Untergruppe) eines Aufrufs — Untergruppe muss passen.

    Der Kern prüft das Zusammenpassen selbst (``untergruppe_passt_nicht``); hier
    wird nur eindeutig gemacht, WAS gefragt ist.
    """
    g = str(gruppe or "").strip()
    u = str(untergruppe or "").strip() or None
    return g, u


def _zeile_eintrag(z: GruppeDatei, benutzer: str, *, darf_anpinnen: bool,
                   darf_loeschen: bool) -> dict[str, Any]:
    """Eine Datei für die Oberfläche — ohne technischen Schlüssel."""
    return {
        "name": z.name,
        "dateiname": z.dateiname,
        "mime": z.mime,
        "groesse": int(z.groesse or 0),
        "angelegt_am": z.angelegt_am.isoformat(sep=" ") if z.angelegt_am else "",
        "angelegt_von": z.angelegt_von or "",
        "eigene": bool(z.angelegt_von) and z.angelegt_von == benutzer,
        "angepinnt": bool(z.angepinnt),
        "angepinnt_am": z.angepinnt_am.isoformat(sep=" ") if z.angepinnt_am else "",
        "darf_anpinnen": bool(darf_anpinnen),
        "darf_bearbeiten": bool(darf_loeschen),
    }


def _kopfzeile(benutzer: str, gruppe: str, untergruppe: str | None,
               s) -> dict[str, Any]:
    """Der Kopf der Liste: was der Aufrufer hier darf + die geltende Grenze.

    ``s`` ist die LESESITZUNG: die Grenze kommt aus derselben Einstellung wie
    im Chat (``anhang_max_bytes(session)`` — F9, eine Zahl).
    """
    return {
        "darf_hochladen": bool(rechte.darf(benutzer, rechte.ANLEGEN, "gruppe_datei",
                                          gruppe=gruppe, untergruppe=untergruppe)),
        "darf_anpinnen": bool(rechte.darf(benutzer, rechte.ANPINNEN, "gruppe_datei",
                                          gruppe=gruppe, untergruppe=untergruppe)),
        "max_bytes": int(anhang_max_bytes(s)),
    }


def _entsorgung_vormerken(s, schluessel: list[str]) -> list[str]:
    """Speicher-Schlüssel vormerken — EIN Auftrag je Schlüssel (idempotent).

    Rückgabe: die Schlüssel, die DIESER Aufruf gerade angelegt hat (nur die
    versucht der Request danach einmal selbst).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    liste_ = sorted({str(k) for k in schluessel or () if str(k).strip()})
    if not liste_:
        return []
    jetzt = _jetzt()
    einfuegen = pg_insert if s.get_bind().dialect.name == "postgresql" else sqlite_insert
    angelegte = s.execute(
        einfuegen(GruppeDateiEntsorgung).values([
            {"schluessel": wert, "versuche": 0, "naechster_versuch_am": jetzt,
             "belegt_bis": None, "angelegt_am": jetzt}
            for wert in liste_
        ]).on_conflict_do_nothing(index_elements=["schluessel"])
        .returning(GruppeDateiEntsorgung.schluessel)
    ).scalars().all()
    return [str(w) for w in angelegte]


def _entsorgung_sofort(schluessel: list[str]) -> int:
    """Die EIGENEN Aufträge EINMAL versuchen — nie eine Ausnahme nach außen.

    Die Zeile ist in derselben Transaktion gefallen: verschwindet die Datei
    jetzt nicht, holt es der Aufräum-Job (DATEIEN-5) nach. Ein Fehler hier darf
    den Request nicht kippen (der Löschvorgang ist bereits gültig).
    """
    from diakronos_app.speicher import AblageFehler
    from diakronos_app.speicher import NichtGefunden as SpeicherNichtGefunden
    from diakronos_app.speicher import hole_speicher

    eigene = [str(k) for k in schluessel or () if str(k).strip()][:ENTSORGUNG_JE_ANFRAGE]
    if not eigene:
        return 0
    weg: list[str] = []
    try:
        speicher = hole_speicher()
    except Exception as fehler:  # noqa: BLE001 — Auftrag bleibt, Job wiederholt
        logger.warning("Gruppendatei-Entsorgung: Ablage nicht verfügbar: %s", fehler)
        return 0
    for wert in eigene:
        try:
            noch_da = speicher.loeschen_mit_zeitlimit(wert, sekunden=ENTSORGUNG_ZEITLIMIT_SEKUNDEN)
        except (SpeicherNichtGefunden, AblageFehler):
            # „war schon weg“ liest die Ablage als Erfolg (``loeschen`` ->
            # ``False``); wirft sie doch, bleibt der Auftrag für den Job.
            logger.info("Gruppendatei %r nicht gelöscht (Job holt es nach).", wert)
            continue
        except Exception as fehler:  # noqa: BLE001 — nie nach außen
            logger.warning("Gruppendatei %r nicht gelöscht: %s", wert, fehler)
            continue
        if noch_da is not False:
            # Review R1/4: JEDER Schlüssel für sich — entfernt wird nur, was
            # dieser Aufruf wirklich gelöscht hat (Muster ``api.chat``).
            weg.append(wert)
    if weg:
        # Erst NACH dem Lauf in EINER eigenen Transaktion — die Auftragsliste
        # nie während des Löschens anfassen.
        _auftraege_entfernen(weg)
    return len(weg)


def _auftraege_entfernen(schluessel: list[str]) -> None:
    """Erledigte Aufträge aus der Entsorgungsliste nehmen (eigene Transaktion)."""
    if not schluessel:
        return
    try:
        with dbmod.SessionLocal() as s, s.begin():
            s.execute(delete(GruppeDateiEntsorgung).where(
                GruppeDateiEntsorgung.schluessel.in_(schluessel)))
    except Exception as fehler:  # noqa: BLE001 — Aufräumen ist nachrangig
        logger.warning("Gruppendatei-Entsorgungsaufträge nicht entfernt: %s", fehler)


def _datei_zeile(s, name: str) -> GruppeDatei | None:
    kennung = str(name or "").strip()
    return s.get(GruppeDatei, kennung) if kennung else None


def _besitzer(z: GruppeDatei) -> str:
    """Der Besitzer-Kennwert für den Kern — bei NULL ausdrücklich ein LEERER Text.

    Review R1/1: hier stand eine Ersatz-Kennung (``"\\x00geloeschtes-konto"``),
    die als „fremder Besitzer“ durchging und die Datei damit in eine falsche
    Rolle schob.

    Der Kern verlangt ``besitzer`` bei ``gruppe_datei`` IMMER
    (``besitzer_fehlt`` sonst) und vergleicht ``besitzer == benutzer`` — ein
    leerer Text ist deshalb die ehrliche Antwort für „niemand“: die Datei eines
    gelöschten Kontos gehört NIEMANDEM, also darf kein Mitglied sie als eigene
    führen, die Leitung (HV/MV, in der Untergruppe GL) sie aber pflegen
    (F4 „fremde Datei“). Die Oberfläche zeigt ``angelegt_von == ""``.
    """
    return str(z.angelegt_von or "").strip()


def _sichtbar(benutzer: str, z: GruppeDatei) -> bool:
    """Ist ``z`` für ``benutzer`` sichtbar — dieselbe Frage wie in :func:`liste`?

    Review R1/2: anpinnen/umbenennen/löschen/wiederherstellen antworten auf eine
    nicht sichtbare Datei mit DERSELBEN 404 wie auf eine unbekannte Kennung.
    Sichtbar heißt: LESEN am Raum der Datei — und, bei einer Papierkorb-Zeile,
    MODERIEREN am Raum (nur wer im Papierkorb aufräumen darf, sieht die Zeile;
    genau so zeigt sie :func:`papierkorb`). Erst danach entscheidet die
    eigentliche Aktion und antwortet ggf. mit 403.
    """
    if z.geloescht_am is not None:
        return bool(rechte.darf(benutzer, rechte.MODERIEREN, "gruppe_datei", None,
                                gruppe=z.gruppe, untergruppe=z.untergruppe))
    return bool(rechte.darf(benutzer, rechte.LESEN, "gruppe_datei", None,
                            gruppe=z.gruppe, untergruppe=z.untergruppe))


# ── Liste und Kopf ──────────────────────────────────────────────────────────


@whitelist(allow_guest=False)  # SEC-11: rein lesend
def liste(gruppe: str, untergruppe: str | None = None) -> dict[str, Any]:
    """Die Dateien einer (Unter-)Gruppe — angepinnte zuerst, dann neueste.

    Recht: LESEN am Raum. Je Eintrag stehen die Rechte des Aufrufers
    (``darf_anpinnen``, ``darf_bearbeiten``); der Kopf nennt ``darf_hochladen``,
    ``darf_anpinnen`` und die geltende Grenze in Bytes (F9, dieselbe Zahl wie
    im Chat). Dateien im PAPIERKORB erscheinen hier NICHT.
    """
    benutzer = _benutzer()
    g, u = _raum(gruppe, untergruppe)
    if not g:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("gruppe fehlt.", ValidationError)
    _pruefe(benutzer, rechte.LESEN, gruppe=g, untergruppe=u)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        kopf = _kopfzeile(benutzer, g, u, s)
        bedingung = [GruppeDatei.gruppe == g,
                     GruppeDatei.untergruppe.is_(None) if u is None
                     else GruppeDatei.untergruppe == u,
                     GruppeDatei.geloescht_am.is_(None)]
        zeilen = s.execute(
            select(GruppeDatei).where(*bedingung).order_by(
                GruppeDatei.angepinnt.desc(),
                GruppeDatei.angepinnt_am.desc(),
                GruppeDatei.angelegt_am.desc(),
                GruppeDatei.name.desc(),
            )
        ).scalars().all()
        eintraege = [
            _zeile_eintrag(
                z, benutzer,
                darf_anpinnen=bool(rechte.darf(
                    benutzer, rechte.ANPINNEN, "gruppe_datei", None,
                    gruppe=g, untergruppe=u)),
                darf_loeschen=bool(rechte.darf(
                    benutzer, rechte.SCHREIBEN, "gruppe_datei", None,
                    gruppe=g, untergruppe=u, besitzer=_besitzer(z))),
            )
            for z in zeilen
        ]
    return {"success": True, "gruppe": g, "untergruppe": u,
            "dateien": eintraege, "anzahl": len(eintraege), **kopf}


# ── Hochladen ───────────────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def hochladen(gruppe: str, untergruppe: str | None = None, datei=None,
              file=None, dateiname=None) -> dict[str, Any]:
    """Eine Datei HOCHLADEN (F8: alles außer Ausführbarem, F9: Chat-Grenze).

    Ablauf (Muster ``api.chat.anhang_hochladen``):

    1. Recht ANLEGEN am Raum (Schalter ``dateien_hochladen_alle``, Leitung immer).
    2. ``ablage.nimm_upload(datei, grenze, RICHTLINIE_SPERR)`` — Deckel beim
       Lesen, leer/zu groß, Typ per Magie UND Endung (Sperrliste), Viren-Haken.
    3. In die EINE Ablage schreiben (``ablage.lege_ab``) — scheitert das, gibt es
       KEINE Zeile.
    4. Zeile schreiben; scheitert sie, wandert der Schlüssel in die
       Entsorgungsliste (und wird einmal sofort versucht) — nie eine Waise.

    Ein Tageslimit gibt es NICHT (F9).
    """
    vom_aufrufer = file if datei is None else datei
    benutzer = _benutzer()
    g, u = _raum(gruppe, untergruppe)
    if not g:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("gruppe fehlt.", ValidationError)
    _pruefe(benutzer, rechte.ANLEGEN, gruppe=g, untergruppe=u)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        grenze = int(anhang_max_bytes(s))

    info = ablage.nimm_upload(
        vom_aufrufer, grenze=grenze, richtlinie=ablage.RICHTLINIE_SPERR,
        name=dateiname or None)
    try:
        schluessel = ablage.lege_ab(info, GDT_SPEICHER_PRAEFIX)
    except Exception as fehler:  # noqa: BLE001 — Ablage-Fehler ist ein Eingabefehler
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        logger.warning("Gruppendatei nicht abgelegt: %s", fehler)
        throw("Die Datei konnte nicht abgelegt werden. Bitte später erneut versuchen.",
              ValidationError)

    kennung = _kennung()
    try:
        with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
            s.add(GruppeDatei(
                name=kennung,
                gruppe=g,
                untergruppe=u,
                schluessel=schluessel,
                dateiname=info.anzeigename[:GDT_NAME_MAX],
                mime=info.typ,
                groesse=info.groesse,
                angelegt_am=_jetzt(),
                angelegt_von=benutzer or None,
                angepinnt=False,
            ))
            s.flush()
    except Exception:
        # Keine Zeile → der Schlüssel wäre unerreichbar. Erst den Auftrag
        # vormerken, dann einmal sofort versuchen (der Job wiederholt es).
        vorgemerkt: list[str] = []
        try:
            with dbmod.SessionLocal() as s2, s2.begin():
                vorgemerkt = _entsorgung_vormerken(s2, [schluessel])
        except Exception as fehler:  # noqa: BLE001 — das Original zählt
            logger.warning("Gruppendatei %r nicht vorgemerkt: %s", schluessel, fehler)
        entfernt = 0
        try:
            entfernt = _entsorgung_sofort([schluessel])
        except Exception as fehler:  # noqa: BLE001 — das Original zählt
            logger.warning("Gruppendatei %r nicht gelöscht: %s", schluessel, fehler)
        if not vorgemerkt and not entfernt:
            logger.error("Gruppendatei %r ist verwaist (kein Auftrag, Löschen "
                         "gescheitert) — manuelle Nacharbeit nötig.", schluessel)
        raise

    return {"success": True, "name": kennung, "dateiname": info.anzeigename,
            "mime": info.typ, "groesse": info.groesse, "gruppe": g,
            "untergruppe": u}


# ── Anpinnen, Umbenennen ────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def anpinnen(name: str, an: Any = True) -> dict[str, Any]:
    """Eine Datei anpinnen bzw. den Pin lösen (Aktion ANPINNEN)."""
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    wert = _wahr(an)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.ANPINNEN, gruppe=z.gruppe, untergruppe=z.untergruppe)
        if wert:
            if not z.angepinnt:
                z.angepinnt = True
                z.angepinnt_am = _jetzt()
                z.angepinnt_von = benutzer or None
        else:
            z.angepinnt = False
            z.angepinnt_am = None
            z.angepinnt_von = None
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name, "angepinnt": bool(z.angepinnt)}
    rechte.merker_leeren()
    return antwort


@whitelist(methods=["POST"], allow_guest=False)
def umbenennen(name: str, dateiname: str) -> dict[str, Any]:
    """Den Anzeigenamen ändern (SCHREIBEN, ``besitzer`` = ``angelegt_von``).

    Bereinigt wird mit derselben Regel wie beim Upload
    (``ablage.dateiname``): kein Pfad, keine Steuerzeichen, ≤ 120 Zeichen. Die
    Sperrliste gilt auch hier — ein Name, der auslieferbar wäre
    (``.exe``/``.html``), wird abgewiesen. Name, Typ und Ablage bleiben.
    """
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    neu = ablage.dateiname(str(dateiname or ""), "")
    if not neu:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("Bitte einen Dateinamen angeben.", ValidationError)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.SCHREIBEN, gruppe=z.gruppe,
                untergruppe=z.untergruppe, besitzer=_besitzer(z))
        ablage.pruefe_endungen(neu)
        z.dateiname = neu[:GDT_NAME_MAX]
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name, "dateiname": z.dateiname}
    rechte.merker_leeren()
    return antwort


# ── Löschen (Papierkorb), Wiederherstellen, Papierkorb-Liste ────────────────


@whitelist(methods=["POST"], allow_guest=False)
def loeschen(name: str) -> dict[str, Any]:
    """Eine Datei in den PAPIERKORB legen (F5) — nicht endgültig löschen.

    Recht: SCHREIBEN mit ``besitzer`` = ``angelegt_von`` — die eigene Datei
    darf jede hochladende Person löschen, fremde HV/MV (in der Untergruppe auch
    GL). Endgültig entfernt (Zeile + Datei) der Job aus DATEIEN-5.
    """
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.SCHREIBEN, gruppe=z.gruppe,
                untergruppe=z.untergruppe, besitzer=_besitzer(z))
        z.geloescht_am = _jetzt()
        z.geloescht_von = benutzer or None
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name,
                   "geloescht_am": z.geloescht_am.isoformat(sep=" ")}
    rechte.merker_leeren()
    return antwort


@whitelist(methods=["POST"], allow_guest=False)
def wiederherstellen(name: str) -> dict[str, Any]:
    """Eine Datei aus dem Papierkorb holen (F5).

    Wiederherstellen ist Wegräumen FÜR die Gruppe — deshalb die Aktion
    MODERIEREN (dieselbe, die der Kern dem Papierkorb zuordnet); wer sie nicht
    hat, bekommt die normale Rechte-Meldung.

    Sichtbarkeit (Review R1/2): Ein NICHT gelöschter Eintrag ist über LESEN
    sichtbar — eine Aktion darauf ist eine Rechte-Frage (403). Eine Zeile im
    PAPIERKORB sieht nur, wer dort aufräumen darf (MODERIEREN, wie
    :func:`papierkorb`); für alle anderen ist sie unbekannt (404).
    """
    benutzer = _benutzer()
    kennung = str(name or "").strip()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or not _sichtbar(benutzer, z):
            raise _nicht_gefunden()
        _pruefe(benutzer, rechte.MODERIEREN, gruppe=z.gruppe, untergruppe=z.untergruppe)
        if z.geloescht_am is None:
            return {"success": True, "name": z.name, "wiederhergestellt": False}
        z.geloescht_am = None
        z.geloescht_von = None
        s.flush()  # Schreibung im Rumpf sichtbar (SEC-11), Fehler hier statt beim Commit
        antwort = {"success": True, "name": z.name, "wiederhergestellt": True}
    rechte.merker_leeren()
    return antwort


@whitelist(allow_guest=False)  # SEC-11: rein lesend
def papierkorb(gruppe: str, untergruppe: str | None = None) -> dict[str, Any]:
    """Die Dateien im PAPIERKORB einer (Unter-)Gruppe (F5).

    Nur für die, die dort wegräumen dürfen — MODERIEREN am Raum (HV/MV, in der
    Untergruppe auch GL; Administrator immer). Neueste Löschung zuerst, je
    Eintrag ``loeschbar_ab`` = Zeitpunkt, ab dem der Job (DATEIEN-5) endgültig
    entfernt (``models.dateien.PAPIERKORB_TAGE``).
    """
    from datetime import timedelta

    from diakronos_app.models.dateien import PAPIERKORB_TAGE

    benutzer = _benutzer()
    g, u = _raum(gruppe, untergruppe)
    if not g:
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("gruppe fehlt.", ValidationError)
    _pruefe(benutzer, rechte.MODERIEREN, gruppe=g, untergruppe=u)
    aufbewahrung = timedelta(days=PAPIERKORB_TAGE)
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        zeilen = s.execute(
            select(GruppeDatei).where(
                GruppeDatei.gruppe == g,
                GruppeDatei.untergruppe.is_(None) if u is None
                else GruppeDatei.untergruppe == u,
                GruppeDatei.geloescht_am.is_not(None),
            ).order_by(GruppeDatei.geloescht_am.desc(), GruppeDatei.name.desc())
        ).scalars().all()
        eintraege = [
            {
                "name": z.name,
                "dateiname": z.dateiname,
                "mime": z.mime,
                "groesse": int(z.groesse or 0),
                "geloescht_am": z.geloescht_am.isoformat(sep=" ") if z.geloescht_am else "",
                "geloescht_von": z.geloescht_von or "",
                "loeschbar_ab": (z.geloescht_am + aufbewahrung).isoformat(sep=" ")
                if z.geloescht_am else "",
            }
            for z in zeilen
        ]
    return {"success": True, "gruppe": g, "untergruppe": u,
            "aufbewahrung_tage": PAPIERKORB_TAGE,
            "dateien": eintraege, "anzahl": len(eintraege)}


# ── Ausliefern ──────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)  # GET und HEAD (Download); SEC-11: rein lesend
def datei(name: str):
    """Eine Gruppendatei AUSLIEFERN — gestreamt, mit Rechteprüfung.

    Recht: LESEN am Raum der Datei. JEDE Fehlerart ergibt DIESELBE 404:
    unbekannte Kennung, kein Leserecht, Datei im Papierkorb, Objekt in der
    Ablage weg. Kopfzeilen aus dem Baustein (``ablage.ausliefer_kopf``):
    geprüfter Typ, ``nosniff``, ``inline`` nur für erkannte Bilder.
    """
    from fastapi.responses import StreamingResponse

    from diakronos_app.speicher import AblageFehler, NichtGefunden, hole_speicher
    from diakronos_app.speicher import NichtGefunden as SpeicherNichtGefunden

    benutzer = _benutzer()
    kennung = str(name or "").strip()
    with dbmod.SessionLocal.begin() as s, als_aktuelle_sitzung(s):
        z = _datei_zeile(s, kennung)
        if z is None or z.geloescht_am is not None:
            raise _nicht_gefunden()
        if not rechte.darf(benutzer, rechte.LESEN, "gruppe_datei", None,
                           gruppe=z.gruppe, untergruppe=z.untergruppe):
            raise _nicht_gefunden()
        typ = str(z.mime or ablage.UNBEKANNTER_TYP)
        dateiname = str(z.dateiname or "")
        schluessel = str(z.schluessel or "")

    if not schluessel:
        raise _nicht_gefunden()
    try:
        bloecke, anfang, ende = hole_speicher().strom(schluessel, von=0, bis=None)
    except (SpeicherNichtGefunden, NichtGefunden, AblageFehler):
        raise _nicht_gefunden() from None

    kopf = ablage.ausliefer_kopf(typ, dateiname)
    if ende < anfang:
        return StreamingResponse(iter(()), status_code=200,
                                 media_type=ablage.sicherer_typ(typ),
                                 headers={**kopf, "Content-Length": "0"})
    # Review R1/8: die Länge kommt aus dem BEREICH, den die Ablage wirklich
    # liefert (``ende - anfang + 1``, Grenzen wie ``speicher.strom`` sie
    # ausgibt) — ``z.groesse`` ist der Stand beim Hochladen und kann abweichen.
    laenge = int(ende) - int(anfang) + 1
    return StreamingResponse(bloecke, status_code=200,
                             media_type=ablage.sicherer_typ(typ),
                             headers={**kopf, "Content-Length": str(max(laenge, 0))})


# ── Einstellungen: reine Durchreiche an den Kern ────────────────────────────


@whitelist(allow_guest=False)
def einstellungen(gruppe: str) -> dict[str, Any]:
    """Die Gruppenschalter (``dateien_hochladen_alle``/``dateien_anpinnen_alle``).

    Reine Durchreiche an ``rechte.verwaltung.gruppeneinstellungen`` — kein
    eigener Weg, keine eigene Vorgabe.
    """
    from diakronos_app.rechte import verwaltung

    return verwaltung.gruppeneinstellungen(_benutzer(), str(gruppe or "").strip())


@whitelist(methods=["POST"], allow_guest=False)
def einstellung_setzen(gruppe: str, schluessel: str, wert: Any = None) -> dict[str, Any]:
    """Einen Gruppenschalter setzen (HV/MV/Administrator) — Durchreiche."""
    from diakronos_app.rechte import verwaltung

    return verwaltung.setze_gruppeneinstellung(
        _benutzer(), str(gruppe or "").strip(), str(schluessel or "").strip(),
        _wahr(wert))
