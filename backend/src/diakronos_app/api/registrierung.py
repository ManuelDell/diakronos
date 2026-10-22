"""Portierung von `diakronos.diakonos.api.registrierung` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/registrierung.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    validate_token          submit_registrierung          submit_gast

**OEFFENTLICHE ENDPUNKTE.** Alle drei tragen im Original
`@frappe.whitelist(allow_guest=True)` — Token-Link-Validierung und
Selbstregistrierung laufen VOR dem Login. Die Flags werden 1:1 uebernommen.
Bewusst NICHT oeffentlich ist
`_validate_name` (Original: private Hilfsfunktion ohne Whitelist).

Frappe-Aufruf -> Compat-Schicht:

    frappe.db.get_value(...)       -> get_value(...)
    frappe.get_doc("Anmeldeformular", x) -> get_doc(...) -> Document
    form.felder                    -> _child_rows("Anmeldeformular Feld", ...)
    frappe.get_doc({...}).insert() -> _create(...)
    doc.append("antworten", {...}) -> _child_insert(...)
    doc.append("kinder", {...})    -> _child_insert(...)
    frappe.db.set_value(..., update_modified=False) -> _update_doc(..., skip_modified)
    frappe.db.commit()             -> no-op (Compat committet je Operation)
    frappe.throw(msg, exc)         -> throw(msg, exc)
    frappe.request.environ         -> request_ip()/request_user_agent() (Request-Kontext)
    now_datetime()                 -> _now()
    nowdate()/getdate()            -> _today()/date.fromisoformat

Schema-Hinweis (gegen `Spaltenabzug der Betriebs-DB` geprueft): `tabAnmeldung`
hat `anmeldungstyp`, `status`, `registrierungslink`, `dsgvo_zustimmung`,
`dsgvo_text_snapshot`, `ip_adresse` — alle im Modell vorhanden.
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.registrierung"

import json as _json
import logging
from datetime import date
from typing import Any

from sqlalchemy import func, or_, update

from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _child_insert,
    _child_rows,
    _create,
    _now,
    get_doc,
    get_value,
    throw,
)
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat.session import session as compat_session
from diakronos_app import request_context

# Einwilligungstext der Mitglieder-Registrierung (Original: `_DSGVO_TEXT`).
# Er ist der FALLBACK: pflegt die Gemeinde unter Einstellungen → Datenschutz-Texte
# einen eigenen Text (N9), gilt dieser. Der Vorfall bleibt unveraendert gueltig,
# damit eine Installation ohne gepflegten Text sich exakt wie bisher verhaelt.
_DSGVO_TEXT = (
    "Ich willige ein, dass meine personenbezogenen Daten (Name, Kontaktdaten) "
    "zum Zweck der Mitgliederverwaltung gemäß Art. 6 Abs. 1 lit. a DSGVO "
    "gespeichert und verarbeitet werden. Die Einwilligung kann jederzeit "
    "widerrufen werden."
)


def _dsgvo_text_aktuell() -> str:
    """Der wirksame Einwilligungstext (N9) oder der feste Standardtext.

    N9b (M-2): massgeblich ist der **veroeffentlichte** gepflegte Text
    (`gemeinde.wirksame_texte`). Ein Entwurf gilt NICHT fuer neue Anmeldungen
    — sonst belegte die Anmeldung einen Wortlaut, den die Person nie gesehen
    hat. Die Standardtexte sind zugleich der Rueckfall dieser Funktion.

    Nie eine Exception: eine fehlende/lesbare Einstellung darf die oeffentliche
    Registrierung nicht wegkaufen — dann gilt der Standardtext.
    """
    try:
        from diakronos_app.api.gemeinde import wirksame_einwilligung

        return wirksame_einwilligung() or _DSGVO_TEXT
    except Exception:  # noqa: BLE001 — Registrierung darf nicht scheitern
        return _DSGVO_TEXT


def _dsgvo_beleg() -> str:
    """Baut den Einwilligungs-Beleg mit Fassungsnummer und Kennung (N-1).

    Der vorangestellte Kopf ``Fassung <nr> (<kennung>)`` belegt, WELCHE Fassung
    der angezeigte Text hatte. Belegt wird immer die GELTENDE Fassung: dass die
    Person dieselbe gesehen hat, stellt ``_pruefe_dsgvo_fassung`` vorher sicher
    — der Aufrufer laesst bei einer Abweichung gar nicht erst speichern.

    Rueckgabe: der komplette Beleg-Text (Kopf + Wortlaut) fuer
    ``Anmeldung.dsgvo_text_snapshot``.

    Wirft nicht. Der frueher uebergebene Parameter ``angezeigte_fassung`` wurde
    hier nie gelesen (Befund R-N12, klein); die Pruefung sitzt in
    ``_pruefe_dsgvo_fassung``, damit Lesen und Bauen des Belegs nicht
    auseinanderlaufen.
    """
    from diakronos_app.api.gemeinde import wirksame_fassung

    try:
        fassung = wirksame_fassung()
    except Exception:  # noqa: BLE001 — wie oben: Standardtext gilt
        fassung = {"version": 1, "text": _DSGVO_TEXT, "kennung": ""}
    kennung = fassung.get("kennung") or ""
    kopf = f"Fassung {fassung.get('version', 1)}"
    if kennung:
        kopf += f" ({kennung})"
    text = fassung.get("text") or _DSGVO_TEXT
    return f"{kopf}\n\n{text}"


def _pruefe_dsgvo_fassung(angezeigte_fassung: Any) -> None:
    """Verlangt, dass die angezeigte Fassung noch die geltende ist (N-1).

    Die Person bestaetigt einen konkreten Wortlaut. Aendert die Gemeinde die
    Fassung waehrend des Ausfuellens, belegt ein stilles Speichern den neuen
    Text — die Person haette etwas anderes zugestimmt (Art. 7 DSGVO). Deshalb
    wird die Abgabe abgelehnt und die Seite neu geladen.

    Fehlt die Angabe (Altformular/Altaufrufer), wird NICHT abgelehnt — der
    Beleg traegt dann die geltende Fassung (Rueckwaertskompatibilitaet).
    """
    if angezeigte_fassung in (None, ""):
        return
    try:
        nummer = int(angezeigte_fassung)
    except (TypeError, ValueError):
        raise ValidationError("Ungültige Fassung der Einwilligung.") from None
    from diakronos_app.api.gemeinde import wirksame_fassung

    try:
        aktuell = int(wirksame_fassung().get("version", 1))
    except Exception:  # noqa: BLE001 — im Zweifel nicht blockieren
        return
    if nummer != aktuell:
        throw(
            "Die Einwilligung wurde zwischenzeitlich geändert. Bitte die Seite "
            "neu laden und erneut bestätigen.",
            ValidationError,
        )


# Felder des Registrierungslink, die `_validate_token` liest (Original: get_value-Liste).
_LINK_FIELDS = (
    "name",
    "typ",
    "gueltig_bis",
    "max_anmeldungen",
    "anmeldungen_count",
    "anmeldeformular",
)

# Kind-Felder des Antwort-Speichers (Original: `doc.append("antworten", {...})`).
_ANTWORT_FIELDS = ("feldlabel", "antwort")

# Kind-Felder des Kinder-Speichers (Original: `doc.append("kinder", {...})`).
_KIND_FIELDS = ("vorname", "nachname", "geburtstag")

logger = logging.getLogger(__name__)


def _geburtsdatum_oder_none(wert):
    """Datum aus dem Formular -> `date` oder `None` (OP-ADMIN-9).

    Das Formular schickt einen String; ein unsinniger Wert ("1990-02-31")
    liess bisher die Datenbank die Ausnahme werfen und der Client bekam das
    rohe SQL samt Spaltenliste. Hier wird vorab geprueft und im Fehlerfall
    eine verstaendliche Meldung geworfen.
    """
    if not wert:
        return None
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert)[:10])
    except ValueError as exc:
        raise ValidationError(
            "Das Geburtsdatum ist kein gueltiges Datum (Format JJJJ-MM-TT)."
        ) from exc


def _kinddatum_oder_none(wert):
    """Wie `_geburtsdatum_oder_none`, aber OHNE zu werfen (Kindzeilen).

    Ein einzelnes fehlerhaftes Kind darf die ganze Registrierung nicht
    abbrechen (Original schluckt hier bewusst); der Datensatz wird verworfen
    und die Ursache geloggt (BLD-R3).
    """
    if not wert:
        return None
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert)[:10])
    except ValueError:
        # Befund 3 (P0-4b): KEIN Rohwert im Log. Ein Geburtsdatum ist ein
        # personenbezogener Wert; die Zeile genuegt fuer die Fehlersuche.
        logger.warning(
            "Kind-Geburtsdatum ungueltig — Kindzeile ohne Datum gespeichert."
        )
        return None



def _als_ja(wert) -> bool:
    """Wahrheitswert einer Formulareingabe ("1"/"true"/"on"/True).

    Das Formular schickt Checkboxen als Text; ein direkter API-Aufruf kann
    alles senden. Nur echte Zustimmung zaehlt (Befund 6, P0-4b).
    """
    if isinstance(wert, bool):
        return wert
    return str(wert or "").strip().lower() in ("1", "true", "on", "yes", "ja")


def _pruefe_bremse(token) -> dict:
    """Adressgrenze vor DB, Linkgrenze erst nach erfolgreicher Tokenprüfung.

    Ungültige Tokens dürfen keinen eigenen Redis-Schlüssel erzeugen. Jeder
    Versuch zählt aber vor der DB gegen die Adresse (XFF nur bei BEHIND_PROXY).
    Der geprüfte Link wird an beide Absendewege weitergereicht.
    """
    from diakronos_app.anmeldung import registrierungsbremse

    def pruefen(ip, gepruefter_token=None):
        erlaubt, grund = registrierungsbremse.pruefe(ip, gepruefter_token)
        if not erlaubt:
            logger.warning("Registrierung gebremst (Grund=%s).", grund or "unbekannt")
            throw(registrierungsbremse.fehlermeldung(), ValidationError)

    pruefen(request_context.zaehler_client_ip())
    link = _validate_token(token)
    pruefen(None, token)
    return link


def _gib_platz_frei(link_name: str) -> None:
    """Gibt einen atomar reservierten Platz zurueck (Fehlpfad, Befund 2).

    Scheitert das Anlegen der Anmeldung NACH der Reservierung, darf der Link
    nicht dauerhaft ein Kontingent verlieren. Nur subtrahieren, wenn der Wert
    > 0 ist — so kann kein Unterlauf entstehen.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    sess = SessionLocal()
    try:
        sess.execute(
            update(Registrierungslink)
            .where(Registrierungslink.name == link_name)
            .where(Registrierungslink.anmeldungen_count > 0)
            .values(anmeldungen_count=Registrierungslink.anmeldungen_count - 1)
        )
        sess.commit()
    except Exception as exc:  # noqa: BLE001 — Aufraeumen darf nie lauter sein
        sess.rollback()
        logger.warning("Platzfreigabe fuer Link fehlgeschlagen (%s).", type(exc).__name__)
    finally:
        sess.close()


def _get_client_ip() -> str:
    """IP des Absenders fuer den Einwilligungsnachweis (OP-ADMIN-R1).

    Das Original las `HTTP_X_FORWARDED_FOR` bedingungslos. Der Header ist aber
    von jedem Client frei setzbar — die IP waere damit kein Nachweis mehr,
    sondern ein Feld, das der Einwilligende selbst bestimmt. Deshalb gilt
    dieselbe Regel wie beim Login-Zaehler: nur wenn ein Reverse-Proxy
    ausdruecklich vorausgesetzt ist (`BEHIND_PROXY`), wird die erste
    XFF-Adresse uebernommen; sonst die Verbindungsadresse.
    """
    return request_context.zaehler_client_ip() or ""


def _validate_token(token):
    """Prueft Token und gibt den Registrierungslink-Datensatz zurueck.

    Wirft `PermissionError` bei ungueltigem/abgelaufenem/vollem Link
    (Original: `frappe.throw(..., frappe.PermissionError)`).
    """
    if not token:
        throw("Kein Registrierungstoken angegeben.", FrappePermissionError)

    link = get_value(
        "Registrierungslink",
        {"slug": token, "aktiv": 1},
        list(_LINK_FIELDS),
        as_dict=True,
    )

    if not link:
        throw("Ungültiger oder deaktivierter Registrierungslink.", FrappePermissionError)

    if link.get("gueltig_bis") and _as_date(link["gueltig_bis"]) < date.today():
        throw("Dieser Registrierungslink ist abgelaufen.", FrappePermissionError)

    max_anmeldungen = link.get("max_anmeldungen") or 0
    count = link.get("anmeldungen_count") or 0
    if max_anmeldungen > 0 and count >= max_anmeldungen:
        throw(
            "Die maximale Anzahl an Anmeldungen für diesen Link wurde erreicht.",
            FrappePermissionError,
        )

    return link


def _inkrementiere_zaehler(link_name: str, max_anmeldungen: int) -> bool:
    """Erhoeht `anmeldungen_count` ATOMAR — oder lehnt ab (Befund 2, P0-4b).

    Vorher wurde der Zaehler gelesen, geprueft und dann geschrieben
    (`count = gelesen; if count < max: schreibe count+1`). Bei parallelen
    Anfragen ist das ein Read-Modify-Write ohne Sperre: zwei Aufrufe lesen
    denselben Stand, beide sehen "noch Platz" und beide schreiben — der
    Zaehler verliert Schritte und `max_anmeldungen` wird ueberschritten.

    Hier entscheidet die DATENBANK in EINEM Statement, ob noch Platz ist:

        UPDATE registrierungslink
           SET anmeldungen_count = anmeldungen_count + 1
         WHERE name = :name
           AND (max_anmeldungen IS NULL OR max_anmeldungen = 0
                OR anmeldungen_count < max_anmeldungen)

    Trifft die Bedingung nicht (Spalte voll), aendert das UPDATE 0 Zeilen —
    und genau dann wird abgelehnt. Die Pruefung und das Zaehlen sind damit
    unteilbar, unabhaengig davon, wie viele Worker gleichzeitig laufen.

    `max_anmeldungen` wird hier nur zur Doku mitgegeben (der Aufrufer hat es
    aus `_validate_token`); die massgebliche Grenze steht im WHERE, denn nur
    sie ist gegen Nebenlaeufigkeit geschuetzt. `anmeldungen_count` ist in der
    Datenbank nullable — `COALESCE` verhindert, dass ein NULL-Stand das
    Inkrement verschluckt (`NULL + 1` ist `NULL`, und der Link bliebe fuer
    immer bei 0 stehen).

    Rueckgabe True = gezaehlt (Platz war da), False = Spalte voll.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    sess = SessionLocal()
    try:
        ergebnis = sess.execute(
            update(Registrierungslink)
            .where(Registrierungslink.name == link_name)
            .where(
                or_(
                    Registrierungslink.max_anmeldungen.is_(None),
                    Registrierungslink.max_anmeldungen == 0,
                    func.coalesce(Registrierungslink.anmeldungen_count, 0) < Registrierungslink.max_anmeldungen,
                )
            )
            .values(
                anmeldungen_count=(
                    func.coalesce(Registrierungslink.anmeldungen_count, 0) + 1
                )
            )
        )
        sess.commit()
        return int(ergebnis.rowcount or 0) == 1
    finally:
        sess.close()


def _as_date(value) -> date:
    """`frappe.utils.getdate` — Datum/String -> `date`."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _validate_name(vorname, nachname) -> None:
    """Original: `_validate_name` — Pflichtfelder der Anmeldung."""
    if not (vorname and vorname.strip()):
        throw("Vorname ist erforderlich.", ValidationError)
    if not (nachname and nachname.strip()):
        throw("Nachname ist erforderlich.", ValidationError)


def _load_list(raw, name: str) -> list[dict]:
    """JSON-String oder Liste -> Liste von dicts (Original parst ebenso)."""
    if isinstance(raw, str):
        try:
            parsed = _json.loads(raw)
        except (ValueError, TypeError):
            return []
    else:
        parsed = raw or []
    return [row for row in parsed if isinstance(row, dict)] if isinstance(parsed, list) else []


# bewusst oeffentlich: Token-Link-Validierung vor dem Login
@whitelist(allow_guest=True)
def validate_token(token):
    """Gibt Typ + Formular-Felder des Links zurueck (Frontend-Initialisierung)."""
    from diakronos_app.anmeldung import registrierungsbremse
    if not registrierungsbremse.zaehle_validierung(request_context.zaehler_client_ip()):
        throw(registrierungsbremse.fehlermeldung(), ValidationError)
    link = _validate_token(token)

    felder = []
    mit_kinder = 0
    mit_gaesten = 0

    if link.get("anmeldeformular"):
        form = get_doc("Anmeldeformular", link["anmeldeformular"])
        # `form.felder` ist eine Kind-Tabelle: `get_doc` liefert kein
        # Kind-Attribut, deshalb ueber `_child_rows`. Die Feldliste wird
        # explizit uebergeben — ohne sie liefert der Helfer nur name/idx.
        for f in _child_rows(
            "Anmeldeformular Feld",
            form.name,
            "felder",
            fields=[
                "label",
                "feldtyp",
                "optionen",
                "pflichtfeld",
                "fuer_gaeste",
                "fuer_kinder",
            ],
        ):
            felder.append(
                {
                    "label": f.get("label"),
                    "feldtyp": f.get("feldtyp"),
                    "optionen": f.get("optionen") or "",
                    "pflichtfeld": f.get("pflichtfeld"),
                    "fuer_gaeste": f.get("fuer_gaeste"),
                    "fuer_kinder": f.get("fuer_kinder"),
                }
            )
        mit_kinder = form.mit_kinder or 0
        mit_gaesten = form.mit_gaesten or 0

    return {
        "typ": link.get("typ"),
        "felder": felder,
        "mit_kinder": mit_kinder,
        "mit_gaesten": mit_gaesten,
    }


# bewusst oeffentlich: Mitglied-Registrierung via Token-Link ohne Login
@whitelist(allow_guest=True)
def submit_registrierung(
    token,
    vorname,
    nachname,
    email="",
    telefon="",
    geburtstag="",
    kommentar="",
    antworten="[]",
    kinder="[]",
    dsgvo=None,
    dsgvo_fassung=None,
):
    """Mitglied-Registrierung via Token-Link."""
    link = _pruefe_bremse(token)

    if link.get("typ") != "Mitglied-Registrierung" and link.get("typ") != "Veranstaltung":
        throw(
            "Dieser Link ist nicht für die Mitglied-Registrierung freigegeben.",
            FrappePermissionError,
        )

    # Befund 6 (P0-4b): die Einwilligung wurde serverseitig IMMER auf 1
    # gesetzt — ein direkter API-Aufruf erzeugte damit "eingewilligt"-
    # Datensaetze, ohne dass der Client zugestimmt hat. Ein Einwilligungs-
    # nachweis, der ohne Einwilligung entsteht, ist keiner. Der Parameter ist
    # deshalb Pflicht (die SPA sendet ihn aus dem Formular-Kaestchen).
    if not _als_ja(dsgvo):
        throw(
            "Bitte stimme der Verarbeitung deiner Daten zu.",
            ValidationError,
        )

    # N-1: Die Person bestaetigt einen KONKRETEN Wortlaut. Weicht die auf der
    # Seite angezeigte Fassung von der geltenden ab, wurde sie stillschweigend
    # geaendert — dann abbrechen und neu laden lassen.
    _pruefe_dsgvo_fassung(dsgvo_fassung)

    _validate_name(vorname, nachname)

    # SEC-c: E-Mail der Gast-Eingabe normalisieren (die EINE Regel aus
    # `email_belegung`). Unsichtbare Zeichen werden abgewiesen, statt still
    # entfernt zu werden — die Adresse ist eine Angabe des Gastes.
    from diakronos_app.email_belegung import enthaelt_unsichtbare, normalisiere

    if enthaelt_unsichtbare(email):
        throw(
            "Die E-Mail-Adresse enthält unsichtbare Zeichen. Bitte die "
            "Adresse neu eintippen.",
            ValidationError,
        )
    email = normalisiere(email)

    # Befund 2 (P0-4b): Platz atomar reservieren, BEVOR die Anmeldung
    # angelegt wird. Zwei parallele Anfragen koennen so `max_anmeldungen`
    # nicht mehr ueberschreiten (siehe `_inkrementiere_zaehler`).
    if not _inkrementiere_zaehler(link["name"], link.get("max_anmeldungen") or 0):
        throw(
            "Die maximale Anzahl an Anmeldungen für diesen Link wurde erreicht.",
            FrappePermissionError,
        )

    try:
        name = _create(
            "Anmeldung",
            {
                "anmeldungstyp": "Mitglied-Registrierung"
                if link.get("typ") == "Mitglied-Registrierung"
                else "Veranstaltung",
                "vorname": vorname.strip(),
                "nachname": nachname.strip(),
                "email": email,
                "telefon": (telefon or "").strip(),
                "geburtstag": _geburtsdatum_oder_none(geburtstag),
                "kommentar": (kommentar or "").strip(),
                "dsgvo_zustimmung": 1,
                "dsgvo_text_snapshot": _dsgvo_beleg(),
                "ip_adresse": _get_client_ip(),
                "anmeldedatum": _now(),
                "status": "Anmeldeanfrage",
                "registrierungslink": link["name"],
            },
        )
    except Exception:
        # Der reservierte Platz wird zurueckgegeben, sonst waere der Link
        # nach einem Fehlversuch dauerhaft ein Kontingent los.
        _gib_platz_frei(link["name"])
        raise

    # Antworten speichern. Original schluckt Fehler hier bewusst (der
    # Registrierungsvorgang darf daran nicht scheitern). BLD-R3: ein stilles
    # `pass` machte ungueltige Zeilen unsichtbar — statt dessen wird geloggt.
    try:
        for a in _load_list(antworten, "antworten"):
            row = {feld: a.get(feld) for feld in _ANTWORT_FIELDS}
            row["feldlabel"] = a.get("label", "") or ""
            row["antwort"] = str(a.get("wert", ""))
            _child_insert("Anmeldung Antwort", name, "antworten", row)
    except Exception as exc:  # noqa: BLE001 — wie Original: Vorgang laeuft weiter
        # Befund 3 (P0-4b): OHNE `exc_info` — der volle Treibertext traegt die
        # SQL-Parameter (Name, E-Mail, Telefon, IP des Anmeldenden). Ins Log
        # gehoert nur die Fehlerklasse, nicht der Inhalt der Zeile.
        logger.warning(
            "Registrierung %s: Antwortzeilen unvollstaendig gespeichert (%s).",
            name, type(exc).__name__,
        )

    # Kinder speichern (ebenfalls bewusst fehlertolerant, aber mit Logzeile).
    try:
        for k in _load_list(kinder, "kinder"):
            _child_insert(
                "Anmeldung Kind",
                name,
                "kinder",
                {
                    "vorname": k.get("vorname", ""),
                    "nachname": k.get("nachname", ""),
                    "geburtstag": _kinddatum_oder_none(k.get("geburtstag")),
                },
            )
    except Exception as exc:  # noqa: BLE001
        # Befund 3: wie oben — nur die Fehlerklasse, keine Parameter.
        logger.warning(
            "Registrierung %s: Kinderzeilen unvollstaendig gespeichert (%s).",
            name, type(exc).__name__,
        )

    return {"success": True, "anmeldung": name}


# bewusst oeffentlich: Gast-Anmeldung via Token-Link ohne Login
@whitelist(allow_guest=True)
def submit_gast(token, vorname, nachname, dsgvo=None, dsgvo_fassung=None):
    """Gast-Anmeldung via Token-Link."""
    link = _pruefe_bremse(token)

    if link.get("typ") != "Gast-Anmeldung":
        throw(
            "Dieser Link ist nicht für die Gast-Anmeldung freigegeben.",
            FrappePermissionError,
        )

    if not _als_ja(dsgvo):
        throw(
            "Bitte stimme der Verarbeitung deiner Daten zu.",
            ValidationError,
        )

    # N-1: dieselbe Fassungspruefung wie bei der Mitglied-Registrierung.
    _pruefe_dsgvo_fassung(dsgvo_fassung)

    _validate_name(vorname, nachname)

    # Befund 2 (P0-4b): Platz atomar reservieren (wie `submit_registrierung`).
    if not _inkrementiere_zaehler(link["name"], link.get("max_anmeldungen") or 0):
        throw(
            "Die maximale Anzahl an Anmeldungen für diesen Link wurde erreicht.",
            FrappePermissionError,
        )

    try:
        name = _create(
            "Anmeldung",
            {
                "anmeldungstyp": "Gast-Anmeldung",
                "vorname": vorname.strip(),
                "nachname": nachname.strip(),
                "dsgvo_zustimmung": 1,
                "dsgvo_text_snapshot": _dsgvo_beleg(),
                "ip_adresse": _get_client_ip(),
                "anmeldedatum": _now(),
                "status": "Anmeldeanfrage",
                "registrierungslink": link["name"],
            },
        )
    except Exception:
        _gib_platz_frei(link["name"])
        raise

    return {"success": True, "anmeldung": name}
