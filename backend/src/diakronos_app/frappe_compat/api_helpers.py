"""Geteilte Schreib-/Kind-/Koerzierungs-Helfer der API-Ports (P4b, P8).

Liegt bewusst in `frappe_compat/`, NICHT mehr in `api/kronos/`: die Helfer
werden inzwischen moduluebergreifend benutzt — `api/ressourcen.py`,
`api/dienstplan.py`, `api/beitraege.py`, `api/wiki.py`, `api/audit.py`,
`api/mitglieder.py`, `api/psalmos/musik.py` und die Kronos-Module. Der Inhalt
ist eine Frappe-Emulation, kein Kronos-Fachmodul; im Kronos-Paket war er
fehlplatziert.

Die ORIGINAL-Pfade der SPA (`diakronos.kronos.api.<modul>.<fn>`) entstehen
ueber die Konstante `FRAPPE_MODULE` je Modul, die der Compat-Registry
auswertet (main 33c296a). Gemeinsame Helfer leben hier, damit es EINE
Umsetzung gibt — analog zum P4a-Muster in `diakronos_app/api/gruppen.py`.

Die Typ-Koerzierung sitzt ZUSAETZLICH zentral in `frappe_compat/query.py`
(`_spaltenwert`), weil dort der gemeinsame Engpass ALLER Filterformen liegt
(dict, Tripel-Liste, `or_filters`). `_coerce_filters` hier ist nur noch der
Eingang fuer die oeffentlichen API-Module, die ihre Filter vor dem Aufruf
konvertieren; er setzt auf demselben `_coerce` auf.

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.session.user            -> session.user
    frappe.get_roles(user)         -> permissions.get_roles(user)
    frappe.get_all(...)            -> query.get_all(...)
    frappe.get_doc(...)            -> query.get_doc(...) -> Document
    frappe.db.get_value(...)       -> query.get_value(...)
    frappe.db.count(...)           -> db.count(...)
    frappe.db.sql(...)             -> query.get_all(...) + Python-Aggregation
    frappe.db.commit()             -> no-op (die Ports committen je Session)
    frappe.new_doc(...)            -> new_doc(...) (Document ohne append)
    doc.append(feld, row)          -> _child_insert(...) / _child_replace(...)
    frappe.delete_doc(...)         -> _delete_doc(...)
    frappe.throw(msg, exc)         -> exceptions.throw(...)
    frappe.generate_hash(len=n)    -> _generate_hash(n)
    frappe.flags.*                 -> _Flags (Attribut-Halter)
    frappe.log_error(...)          -> log_error(...) (stderr, kein Request-Kontext)
"""

from __future__ import annotations

import secrets
import string
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any

from diakronos_app.frappe_compat import db as _db
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    FrappeCompatError,
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.registry_gen import column_names, is_known, model_for
from diakronos_app.frappe_compat.session import session
from diakronos_app.frappe_compat.permissions import ist_user_zeile
from diakronos_app.email_belegung import belegung, enthaelt_unsichtbare, ist_platzhalter, normalisiere

__all__ = [
    "FrappePermissionError",
    "ValidationError",
    "_Flags",
    "_child_delete",
    "_child_insert",
    "_child_replace",
    "_child_rows",
    "_coerce",
    "_count",
    "_create",
    "_delete_doc",
    "_bulk_update_by_field",
    "_generate_hash",
    "_new_name",
    "_now",
    "_parenttype_for",
    "_rethrow",
    "_today",
    "_update_doc",
    "column_names",
    "flags",
    "get_all",
    "get_doc",
    "get_value",
    "is_known",
    "log_error",
    "model_for",
    "session",
    "throw",
]


class _Flags:
    """`frappe.flags` — nur ein Attribut-Halter (Original nutzt `allow_series_edit`).

    Die Flag wird im Altcode von einem `Element`-Hook gelesen, den es im
    Standalone-Backend nicht (mehr) gibt. Sie wird trotzdem gesetzt, damit das
    Verhalten des Aufrufers identisch bleibt und ein spaeterer Hook sie findet.
    """

    __slots__ = ("allow_series_edit",)

    def __init__(self) -> None:
        self.allow_series_edit = False


flags = _Flags()


def log_error(message: str, title: str | None = None) -> None:
    """`frappe.log_error` -> stderr.

    Der Altcode loggt Fehler und wirft danach weiter; im Standalone-Backend gibt
    es keine Error-Log-Tabelle. Der Log landet daher auf stderr, die Funktion
    selbst bleibt still (sie darf den Ablauf nie veraendern).
    """
    label = f"[{title}] " if title else ""
    print(f"kronos error: {label}{message}", file=sys.stderr)


# Text, den ein Client bei einem unerwarteten Datenbankfehler sieht.
# Bewusst ohne Schema, Spaltenlisten, Parameter oder SQL — der Fehler geht an
# OFT UNANGEMELDETE Clients (oeffentliche Registrierung, OP-ADMIN-9).
#
# Befund 10 (P0-4b) — bekannte Grenze: diese Neutralisierung gilt fuer ALLE
# Schreibpfade, also auch fuer Administratoren. Ein Administrator sieht damit
# bei einer Dublette/einem zu langen Wert nur den allgemeinen Satz und nicht
# mehr den konkreten Constraint-Hinweis. Das ist fuer die oeffentlichen Wege
# gewollt (nichts darf nach aussen lecken) und fuer Admin-Bereiche bewusst in
# Kauf genommen: im Server-Log steht nur die Fehlerklasse. Wer die
# Admin-Seite wieder konkret machen will, uebersetzt die Constraint-Faelle in
# `_db_fehler` gezielt (z. B. "zu lang", "doppelt") — statt den rohen Text
# durchzureichen.
_NEUTRALER_DB_FEHLER = (
    "Die Anfrage konnte nicht gespeichert werden. Bitte prüfe die Eingaben; "
    "bleibt der Fehler, wende dich an die Gemeindeleitung."
)


def _db_fehler(exc: Exception, kontext: str | None = None) -> ValidationError:
    """Datenbankausnahme -> neutrale Meldung, Details NUR ins Log (OP-ADMIN-9).

    Vorher reichte `raise ValidationError(str(exc))` den rohen Treibertext samt
    `INSERT INTO`, Spaltenliste, Parametern und interner IP an den Client durch.
    Auch im Log steht nur die Fehlerklasse — niemals SQL, Parameter oder PII.

    Ausnahme: verletzt der Schreibvorgang den Eindeutigkeits-Index der
    E-Mail-Adresse (`uq_mitglied_email_normalisiert`), ist das ein FACHLICHER
    Fehler — hier steht bereits eine Person mit dieser Adresse. Der Text nennt
    den Grund in Klartext (Fachentscheidung 19.10.), ohne die Adresse zu
    wiederholen.

    SEC-d (W3): Die Meldung nennt bewusst KEINE Person. Der Datenbankfehler
    nennt nur den Index, nicht die Zeile; die frueher befragte
    „_erste_email_dublette“ holte das erste Mitglied mit irgendeiner Adresse
    und damit regelmaessig eine UNBETEILIGTE Person (Probe X2) — falsch und
    nebenbei eine Preisgabe eines fremden Namens. Wer die Adresse kennt, nennt
    die Person vorher schon selbst: `_email_belegung_meldung` auf dem Weg ueber
    `_pruefe_mitglied_email_belegung` (create_mitglied, update_mitglied,
    `_create`, Schranke). Hier bleibt es bei „einer anderen Person“.
    """
    log_error(f"{kontext or 'DB-Schreibfehler'}: {type(exc).__name__}")
    if _ist_email_eindeutigkeit(exc):
        return ValidationError(
            "Diese E-Mail-Adresse gehört bereits zu einer anderen Person. "
            "Jede Person braucht eine eigene Adresse."
        )
    return ValidationError(_NEUTRALER_DB_FEHLER)


#: Name des partiellen Unique-Index aus der SEC-Migration.
EMAIL_UNIQUE_INDEX = "uq_mitglied_email_normalisiert"


def _ist_email_eindeutigkeit(exc: Exception) -> bool:
    """Ist das die Verletzung des E-Mail-Eindeutigkeits-Index? (SEC)

    Geprueft wird der Fehlertext der Datenbank — bewusst nur auf den
    Indexnamen, nicht auf den rohen SQL-Text (der nicht in die Meldung darf).
    """
    text = str(getattr(exc, "orig", exc) or exc)
    return EMAIL_UNIQUE_INDEX in text


def _mitglied_anzeigename(mitglied_id: str) -> str:
    """„Vorname Nachname“ eines Mitglieds (leer, wenn nicht lesbar)."""
    try:
        doc = get_doc("Mitglied", mitglied_id)
        name = " ".join(p for p in (doc.get("vorname"), doc.get("nachname")) if p).strip()
    except Exception as exc:  # noqa: BLE001 — die Meldung darf nie am Zusatz scheitern
        log_error(f"Anzeigename nicht lesbar: {type(exc).__name__}", "email_vergeben_meldung")
        return ""
    return name


def _normalisiere_mitglied_email(
    data: dict[str, Any], name: str | None = None
) -> dict[str, Any]:
    """E-Mail eines Mitglieds an EINER Stelle normalisieren und pruefen (SEC-c).

    DIE LUECKE (B1): die Fachentscheidung „eine Adresse je
    Person“ galt nur auf den Fachendpunkten (`create_mitglied`,
    `update_mitglied`). Alle generischen Wege (`PUT/POST /api/resource/Mitglied`,
    `frappe.client.insert`, `_create`, `_update_doc`, `Document.db_set`,
    Import, Registrierung → `genehmige_anmeldung`) verliessen sich auf den
    Unique-Index, und der vergleicht `lower(trim(email))`. `trim` kennt weder
    Tab noch Zeilenende noch NBSP, und NFKC kennt die Datenbank gar nicht —
    „\tanna@x.org“ und „anna@x.org“ waren damit zwei Personen mit derselben
    Adresse. Fuer die Rechtepruefung (`wirksame_konten`, das ueber die
    Adresse mehrere Mitglieder buendelt) wirkte der Ausschluss der einen
    Person auf das Konto der anderen — genau der Zustand, den die
    Fachentscheidung abschaffen wollte.

    DESHALB HIER, in der Schranke durch die JEDER Schreibweg laeuft:

      1. unsichtbare Zeichen (ZWNJ/ZWJ/BOM/weicher Trennstrich …) -> ablehnen,
         statt sie still zu entfernen (eine Adresse wird nicht „repariert“);
      2. Platzhalter wie „-“ sind keine Adresse (K-b) -> leer/NULL;
      3. gespeicherter Wert = `normalisiere` (NFKC, Leerraum weg, klein) —
         damit meint der Index dieselbe Adresse wie der Anwendungscode;
      4. Eindeutigkeit in Python pruefen, mit der Meldung „gehört bereits zu
         <Person>“ — nicht erst als Datenbankfehler.

    Rueckgabe sind die zu schreibenden Felder (ggf. mit `email=None`).
    """
    if "email" not in data:
        return data
    wert = data.get("email")
    if wert is None:
        return data
    if not isinstance(wert, str):
        wert = str(wert)
    if enthaelt_unsichtbare(wert):
        raise ValidationError(
            "Die E-Mail-Adresse enthält unsichtbare Zeichen. Bitte die "
            "Adresse neu eintippen."
        )
    email = normalisiere(wert)
    if ist_platzhalter(email):
        # K-b: KEINE Datenmigration — nur beim Schreiben. Der Betrieb hat ein
        # Mitglied mit „-“; das bleibt stehen (siehe Abschlussbericht).
        data = {**data, "email": None}
        return data
    data = {**data, "email": email}
    return data


def _email_belegung_gleich(a, b) -> bool:
    """Zwei E-Mail-Adressen gleich? (dieselbe Normalisierung wie beim Schreiben)

    „Unveraendert mitgesendet“ heisst hier: normalisiert gleich. Die SPA schickt
    die Adresse oft in anderer Schreibweise zurueck („ Anna@X.ORG “); das ist
    keine Aenderung, die die Eindeutigkeit pruefen muesste.
    """
    from diakronos_app.email_belegung import normalisiere

    return normalisiere(a) == normalisiere(b)


def _pruefe_mitglied_email_eindeutig(
    values: dict[str, Any], name: str | None, *, loeschen: bool = False,
    bestand_email: Any = None, eigenes_konto: Any = None,
) -> None:
    """Ist die Adresse schon vergeben? (fachliche Meldung, KEINE Rechtepruefung)

    Eigener Schritt, weil die REICHTEFRAGE davor gehoert: ein Mitgliederadmin,
    der ein Mitglied auf die Adresse eines Verwaltungskontos umhaengen will,
    muss die Rechte-Meldung bekommen („nur ein System Manager …“, P1-8d) und
    nicht „Adresse gehört bereits zu …“. Beide Texte sind fachlich richtig —
    aber der Rechtegrund ist der wichtigere und war der Vertrag der Karte
    P1-8d.

    Geprueft wird ausschliesslich: gleiche Adresse bei einer ANDEREN Person,
    normalisiert verglichen (SEC-c, B1). Eine Adresse, die der Datensatz schon
    fuehrt (`bestand_email`, normalisiert gleich), ist keine neue Belegung —
    sonst wuerde jedes Speichern des unveraenderten Formulars scheitern.
    """
    if loeschen or not values or not values.get("email"):
        return
    from diakronos_app.email_belegung import _belegung_aus_sitzung as _belegung_fuer
    from diakronos_app.email_belegung import normalisiere

    if bestand_email is not None and _email_belegung_gleich(values["email"], bestand_email):
        return
    # Die Adresse des EIGENEN Kontos ist keine fremde Belegung:
    # `M.mitglied = "sm@x.org"; save()` legt die Person an IHREM Konto an
    # (SEC-c, Regression P1-8d — sonst scheitert jedes Speichern des
    # unveraenderten Formulars an seiner eigenen Adresse).
    eigenes_konto = normalisiere(eigenes_konto)
    if eigenes_konto and normalisiere(values["email"]) == eigenes_konto:
        return
    # `Mitglied.user` im selben Payload: der Link kommt gleich mit, das Konto
    # ist dann per Definition das des Datensatzes.
    if name is None and "user" in values and values.get("user"):
        if normalisiere(values["user"]) == normalisiere(values["email"]):
            return
    from diakronos_app.db import lesesitzung

    with lesesitzung() as sess:
        treffer = _belegung_fuer(sess, str(values["email"]), ohne_mitglied=name,
                                 ohne_mitglied_konto=eigenes_konto)
    # Nur die Adresse eines ANDEREN MITGLIEDS ist eine Dublette. Ein blosses
    # Benutzerkonto (ohne Mitglied, ohne Verwaltungsrolle) ist kein
    # Rechte-Risiko und wird als Hinweis behandelt, nicht als Fehler — so
    # bleibt der Weg für ein wartendes Konto offen (W-b, Regression G2).
    if treffer and treffer.get("doctype") == "Mitglied":
        raise ValidationError(_email_belegung_meldung(treffer))


def _email_belegung_meldung(treffer) -> str:
    """Klartext, WEM die Adresse schon gehoert (Fachentscheidung 19.10.)."""
    if not treffer:
        return "Diese E-Mail-Adresse ist bereits vergeben."
    if treffer.get("doctype") == "Mitglied":
        anzeige = _mitglied_anzeigename(str(treffer["name"]))
    else:
        anzeige = str(treffer.get("full_name") or treffer.get("name") or "").strip()
    if not anzeige:
        return ("Diese E-Mail-Adresse gehört bereits zu einer anderen Person. "
                "Jede Person braucht eine eigene Adresse.")
    return f"Diese E-Mail-Adresse gehört bereits zu {anzeige}."


# ── Zeit / Namen ────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today() -> str:
    """`frappe.utils.today()` -> ISO-Datum."""
    return date.today().isoformat()


_HASH_ALPHABET = string.ascii_lowercase + string.digits


def _generate_hash(length: int = 12) -> str:
    """`frappe.generate_hash(length=n)` — Frappe liefert Kleinbuchstaben+Ziffern."""
    return "".join(secrets.choice(_HASH_ALPHABET) for _ in range(length))


def _new_name() -> str:
    """Ersatz fuer Frappe-Autonamen (kurz, eindeutig, nicht erratbar).

    Form `xxxxxxxx-x` (8 Hexziffern, Bindestrich, 1 Hexziffer). Diese Form
    ist Teil der Zusage aus ID-1d: eine Mitglied-Kennung ist IMMER
    serverseitig vergeben und an der Form erkennbar — eine vom Client
    gewaehlte Kennung („Max Muster“) kommt nie in die Datenbank.
    """
    return f"{uuid.uuid4().hex[:8]}-{uuid.uuid4().hex[:1]}"


#: DocTypes, deren `name` eine PERSONEN-Kennung ist. Bei ihnen wird eine vom
#: Client gelieferte `name` verworfen und immer `_new_name()` vergeben:
#: `Mitglied` (die Person) und `Anmeldung` (die Anmeldung einer Person, aus
#: der per `genehmige_anmeldung` ein Mitglied wird).
PERSONEN_KENNUNGEN = ("Mitglied", "Anmeldung")


def _ist_personen_kennung(doctype: str) -> bool:
    """Ist `name` dieses DocTypes eine Personenkennung (ID-1d)?"""
    return doctype in PERSONEN_KENNUNGEN


# ── Werte an Spaltentypen anpassen ──────────────────────────────────────────


def _normalisiere_leere_links(doctype: str, data: dict[str, Any]) -> dict[str, Any]:
    """Leere optionale FK sind NULL, Freitext bleibt unveraendert.

    Nur fuer Schreibwerte: Filter auf leere historische Werte duerfen durch
    die Normalisierung nicht still ihre Bedeutung aendern.
    """
    cols = model_for(doctype).__table__.columns
    return {k: None if v == "" and k in cols and cols[k].nullable and cols[k].foreign_keys
            else v for k, v in data.items()}


def _coerce(doctype: str, data: dict[str, Any]) -> dict[str, Any]:
    """Werte an die Spaltentypen anpassen (HTTP liefert Strings/Zahlen).

    Angefasst werden `Date`/`DateTime`-Spalten (ISO-Strings) und
    `Boolean`-Spalten. Letztere sind in PostgreSQL echte `boolean`-Spalten:
    der Altcode uebergibt dort Frappe-uebliche `0`/`1`-Werte, was PostgreSQL
    mit `operator does not exist: boolean = integer` abbricht (SQLite
    vergleicht tolerant — genau dieser Unterschied ist in P4c1 schon einmal
    aufgetreten, dort fuer timestamp). `0`/`"0"`/`False` -> `False`, alles
    andere aus `{1, "1", True, "true", "True"}` -> `True`.
    """
    from sqlalchemy import Boolean, Date, DateTime

    model = model_for(doctype)
    cols = {c.name: c for c in model.__table__.columns}
    out = dict(data)
    if doctype == "Mitglied" and "ausgeschlossen" in out:
        out["ausgeschlossen"] = _ist_ausgeschlossen(out["ausgeschlossen"])
    for key, value in list(out.items()):
        if value is None:
            continue
        col = cols.get(key)
        if col is None:
            continue
        typ = col.type
        if isinstance(typ, Boolean):
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                out[key] = bool(value)
            elif isinstance(value, str):
                s = value.strip().lower()
                if s in {"1", "true", "t", "yes", "y", "on"}:
                    out[key] = True
                elif s in {"0", "false", "f", "no", "n", "off", ""}:
                    out[key] = False
            continue
        if not isinstance(value, str):
            continue
        is_date = isinstance(typ, Date) and not isinstance(typ, DateTime)
        is_dt = isinstance(typ, DateTime)
        if is_date:
            try:
                out[key] = date.fromisoformat(value[:10])
            except ValueError:
                pass
        elif is_dt:
            try:
                out[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
    return out


def _coerce_filters(doctype: str, filters: dict[str, Any]) -> dict[str, Any]:
    """Filterwerte an die echten Spaltentypen anpassen.

    Frappe-Filter kommen als `{"feld": wert}` oder `{"feld": [op, wert]}`.
    Der Altcode schreibt dort die Frappe-ueblichen `0`/`1`-Werte; in
    PostgreSQL sind Check-Felder aber echte `boolean`-Spalten, und
    `WHERE veroeffentlicht = 1` scheitert mit
    `operator does not exist: boolean = integer`. Ebenso bei Datums-/Zeit-
    spalten (`timestamp without time zone <= character varying`). SQLite
    (Test-Fixture) vergleicht tolerant — der Unterschied faellt nur gegen
    die echte Datenbank auf.

    Operatoren bleiben unangetastet, nur der Wert wird ueber `_coerce`
    umgewandelt. Siehe auch `kronos/kalender.py` (P4c1) fuer denselben Fix.
    """
    plain: dict[str, Any] = {}
    ops: dict[str, str] = {}
    for feld, spec in filters.items():
        if isinstance(spec, (list, tuple)) and len(spec) == 2 and isinstance(spec[0], str):
            ops[feld] = spec[0]
            plain[feld] = spec[1]
        else:
            plain[feld] = spec

    coerced = _coerce(doctype, plain)

    out: dict[str, Any] = {}
    for feld, wert in coerced.items():
        out[feld] = [ops[feld], wert] if feld in ops else wert
    return out


def _meta_fields() -> dict[str, Any]:
    """Die Metafelder, die Frappe beim Speichern selbst setzt."""
    return {
        "docstatus": 0,
        "owner": session.user,
        "modified_by": session.user,
        "creation": _now(),
        "modified": _now(),
    }


# ── Schreiben ───────────────────────────────────────────────────────────────


def _abschluss(sess: Any, eigene: bool) -> None:
    """Schreibung festmachen: eigene Sitzung committen, geliehene nur flushen.

    Im Request-Rahmen (``_endpunkt``: ``with SessionLocal.begin() as s``) ist
    ``eigene=False``; die geliehene Sitzung gehoert dem Aufruf und wird dort
    EINMAL committet. Eine eigene Sitzung committet selbst.
    """
    if eigene:
        sess.commit()
    else:
        sess.flush()


def _ruecknahme(sess: Any, eigene: bool) -> None:
    """Fehlerfall: eigene Sitzung zurueckrollen; geliehene dem Aufruf ueberlassen.

    Eine geliehene Sitzung darf NICHT zurueckgerollt werden — sie traegt ggf.
    die Aenderungen des gesamten Aufrufs; die Ausnahme reist weiter und der
    Request-Rahmen entscheidet (er rollt beim Verlassen zurueck, weil die
    Ausnahme den ``with``-Block verlaesst).
    """
    if eigene:
        sess.rollback()


def _create(doctype: str, values: dict[str, Any]) -> str:
    """`frappe.new_doc(doctype).save()` + commit. Gibt den `name` zurueck.

    Unbekannte Felder werden verworfen (Frappe ignoriert sie ebenfalls).
    """
    if not is_known(doctype):
        raise ValidationError(f"DocType {doctype!r} nicht gefunden")

    from diakronos_app.db import sitzung_fuer_lesen

    model = model_for(doctype)
    cols = column_names(doctype)
    data = {k: v for k, v in values.items() if k in cols}
    data = _coerce(doctype, _normalisiere_leere_links(doctype, data))
    if doctype == "Mitglied":
        # ID-1d: Die Kennung einer Person wird IMMER serverseitig vergeben.
        # Ein vom Client gelieferter `name` („Max Muster“) wird verworfen —
        # sonst bestimmte der Client die Kennung, auf die Rechte, Verweise
        # und Anonymisierung zeigen. Das geschieht VOR der Schranke, damit
        # diese den geplanten Zustand der NEUEN Zeile sieht (ohne `name`
        # gaebe es sonst einen Bestandsnamen, den es nicht gibt).
        data.pop("name", None)
        data["name"] = _new_name()
        # SEC-c: E-Mail zuerst normalisieren (und Eindeutigkeit in Python
        # pruefen) — die Schranke darunter sieht danach den gespeicherten Wert.
        data = _normalisiere_mitglied_email(data)
        _pruefe_mitglied_schreibzugriff(data)
    elif doctype in _VERWALTUNGS_DOCTYPES:
        # N12b: derselbe Weg wie `/api/resource` — auch beim Anlegen kann
        # `name` einen bestehenden Platz ueberschreiben (Frappe-Save mit
        # gesetztem `name` ist ein Update).
        _pruefe_konto_schreibzugriff(doctype, str(data.get("name") or "") or None, data)
        if not data.get("name"):
            data["name"] = _new_name()
    elif not data.get("name"):
        data["name"] = _new_name()
    for key, value in _meta_fields().items():
        if key in cols:
            data.setdefault(key, value)
    if "idx" in cols:
        data.setdefault("idx", 0)

    sess, eigene = sitzung_fuer_lesen()
    try:
        obj = model(**data)
        sess.add(obj)
        _abschluss(sess, eigene)
        return data["name"]
    except FrappeCompatError:
        _ruecknahme(sess, eigene)
        raise
    except Exception as exc:  # noqa: BLE001 — fachlicher Fehler zurueckgeben
        _ruecknahme(sess, eigene)
        raise _db_fehler(exc, doctype) from exc
    finally:
        if eigene:
            sess.close()


# ── Zentrale Schranke fuer Mitglied-Schreibzugriffe (R-P1-8b/B-neu) ─────────
#
# DER BEFUND (B-neu)
# -----------------------------------
# Die Pruefungen lagen bisher in EINZELNEN Endpunkten
# (`schliesse_mitglied_aus`, `zugang.*`). Damit liess sich der Aussperrschutz
# umgehen, weil es weitere Wege gibt, dieselbe Wirkung zu erzielen:
#
#   * `PUT /api/resource/Mitglied/<id>` mit `{"ausgeschlossen": 1}`
#   * `_apply_resource_write("Mitglied", ...)` (derselbe Weg ohne HTTP)
#   * `frappe.client.insert("Mitglied", {...})` bzw. generische Saves
#   * `Mitglied.user` auf ein Verwaltungskonto verbiegen und dieses dann
#     ausschliessen/sperren
#
# Diese Wirkung ist immer dieselbe: ein Verwaltungskonto verliert Rollen,
# Sitzung und Zugang. Also sitzt die Schranke hier, in der Schicht, durch die
# JEDER Schreibweg laeuft — nicht in den Endpunkten. Wer eine neue
# Schreibroute baut, kann sie damit nicht mehr vergessen.
#
# DIE REGELN (Karte P1-8c, Pflicht 1)
# -----------------------------------
#   (a) Ein Mitglied mit Verwaltungskonto (System Manager/Mitgliederadmin)
#       darf NUR ein System Manager ausschliessen.
#   (b) Der LETZTE aktive System Manager darf nicht ausgeschlossen werden —
#       auch nicht durch sich selbst.
#   (c) `Mitglied.user` auf ein Konto umbiegen, das schon einem anderen
#       Mitglied gehoert oder Verwaltungsrollen traegt, darf NUR ein
#       System Manager — und nie, wenn dabei der letzte System Manager
#       aussperrbar wuerde.
#
# `ausgeschlossen` und `user` sind ausserdem eine Einheit: ein
# `update_mitglied`-Payload kennt `ausgeschlossen` gar nicht (Feld-Whitelist),
# ueber den generischen Weg aber schon — beide Felder laufen durch dieselbe
# Pruefung.
_ADMIN_ROLLEN = ("System Manager", "Mitgliederadministrator")


def _ist_system_manager() -> bool:
    """Traegt der angemeldete Benutzer die Rolle System Manager?"""
    from diakronos_app.frappe_compat.permissions import get_roles

    return "System Manager" in get_roles()


def _verweigere_geloeschtes_mitglied(name: str) -> None:
    """H2: an einer geloeschten Person ist JEDE Aenderung verweigert.

    Gelesen wird ueber die Sitzung des Aufrufers (`get_value` nutzt die
    aktuelle Sitzung, s. `db.sitzung_fuer_lesen`) — keine zweite Verbindung
    mitten in der Loeschtransaktion.
    """
    from diakronos_app.frappe_compat.query import get_value

    status = str(get_value("Mitglied", name, "status") or "")
    if status != "geloescht":
        return
    raise FrappePermissionError(
        "Diese Person wurde auf Antrag gelöscht — die Löschung ist endgültig "
        "und lässt sich nicht rückgängig machen. Anlegen ist mit derselben "
        "E-Mail-Adresse jederzeit möglich."
    )


def _pruefe_mitglied_schreibzugriff(
    values: dict[str, Any], name: str | None = None, *, loeschen: bool = False
) -> None:
    """Zentrale Schranke fuer Anlegen, Aendern und Loeschen eines Mitglieds.

    `values` sind die zu schreibenden Felder (bereits auf Spalten gefiltert),
    `name` die Mitglied-Kennung (None beim Anlegen). `loeschen=True` entfernt
    den Datensatz aus dem geplanten Bestand, statt ihn zu ersetzen. Wirft
    `FrappePermissionError`, wenn der Zugriff nicht erlaubt ist.

    P1-8d (Pflicht b): Die Wirkung eines Schreibvorgangs wird auf dem Zustand
    NACH der Aenderung bewertet. Ein Mitglied „wirkt“ auf alle Konten aus
    `wirksame_konten` (user-Link UND eindeutige E-Mail) — dieselbe Aufloesung
    wie in der Rechtepruefung. Geprueft wird, sobald eines der wirksamen Konten
    (VORHER oder NACHHER) eine Verwaltungsrolle traegt und

      (a) ein Mitgliederadministrator am Werk ist (nur System Manager), oder
      (b) dadurch kein aktiver, nicht ausgeschlossener System Manager uebrig
          bliebe (immer abgelehnt — auch fuer den System Manager selbst).

    Damit sind insert, update, `Mitglied.user`- und `email`-Aenderungen und der
    Zwei-Schritt (A schliesst B aus, dann sich selbst) derselbe Weg.
    """
    from diakronos_app.api.zugang import _aktive_system_manager, _rollen_von
    from diakronos_app.frappe_compat.benutzer_status import (
        _ausgeschlossene_konten, _kontozustand, wirksame_konten,
    )

    # SEC-c: DIE Schranke ist der eine Ort, den jeder Schreibweg passiert.
    # Deshalb wird die E-Mail hier normalisiert — auch fuer Aufrufer, die die
    # Normalisierung vergessen (`Document.db_set`, `frappe.client.insert`,
    # neue Routen). Idempotent, ein schon normalisierter Wert bleibt gleich.
    if "email" in (values or {}):
        values = _normalisiere_mitglied_email(values, name)

    # H2 (R-DSGVO-1): „geloescht“ ist ein ENDSTATUS. Die Loeschung auf Antrag
    # ist laut Fachentscheidung NICHT rueckgaengig zu machen — jede Aenderung
    # an einer solchen Zeile wird verweigert, auch fuer einen System Manager.
    # Diese Pruefung steht hier und nicht in den Endpunkten, damit ALLE Wege
    # sie passieren: `update_mitglied`, `PUT /api/resource`, `frappe.client`,
    # der Import und Austritt/Reaktivieren. Ausnahme ist die Anonymisierung
    # selbst: sie schreibt ueber die Kennung `geloescht-<hex>` (kein
    # Bestandsname) und traegt `status="geloescht"` in `values` — daran
    # erkennt die Schranke den rechtmaessigen Weg.
    if name and not loeschen and (values or {}).get("status") != "geloescht":
        _verweigere_geloeschtes_mitglied(name)

    if ("email" in (values or {}) or "user" in (values or {})) and not _ist_system_manager():
        # P1-8c (Pflicht 1c): `Mitglied.user` auf ein Konto umbiegen, das schon
        # einem anderen Mitglied gehoert, bleibt dem System Manager vorbehalten.
        #
        # SEC-c: `_pruefe_mitglied_schreibzugriff` prueft eine Adresse bisher nur
        # bei KONTEN mit Verwaltungsrolle. Eine Adresse, die schon zu einem
        # anderen Mitglied gehoert, ist aber in JEDEM Fall eine zweite Person
        # mit derselben Adresse — der Zustand, den die Fachentscheidung
        # ausschliesst. Nur ECHTE Aenderungen zaehlen: Link und Adresse, die
        # unveraendert mitgesendet werden, bleiben erlaubt (Regression `G2`).
        from diakronos_app.api.zugang import _konto_mitglieder
        from diakronos_app.frappe_compat.benutzer_status import _kontozustand
        from diakronos_app.email_belegung import belegung as _belegung

        # Die Bestandsauskunft (Konto, Rollen, Adresse) laeuft in der AKTUELLEN
        # Sitzung — in der Regel die des Aufrufers, im Import die Sitzung des
        # Laufs. KEINE eigene Sitzung: die haelt auf PostgreSQL eine zweite
        # Verbindung bis zum Aufraeumen des Garbage Collectors (SEC-d, W1), und
        # auf einer Datenbank mit EINER Verbindung je Engine reisst ihr
        # `close()` die offene Transaktion des Aufrufers mit (SEC-c, „no such
        # savepoint“). Die Auskunft ist ein Leseschritt auf demselben Stand.
        mitglieder, _ = _kontozustand()
        bestand = next((m for m in mitglieder if m["name"] == name), {})
        geprueft: set[str] = set()
        if "user" in values:
            link = str(values.get("user") or "").strip()
            if link and link != str(bestand.get("user") or "").strip():
                _verweigere_fremdes_konto_verknuepfung(link, mitglied=name)
                geprueft.add(link)
        email = values.get("email")
        if email and not _email_belegung_gleich(email, bestand.get("email")):
            treffer = _belegung(str(email), ohne_mitglied=name)
            if treffer and treffer.get("doctype") == "User":
                konto = str(treffer["name"])
                if konto in geprueft:
                    pass  # schon oben mit derselben Regel geprueft
                elif _konto_mitglieder(konto):
                    raise ValidationError(
                        "Diese E-Mail-Adresse gehört bereits zu einem "
                        "Mitglied. Jede Person braucht eine eigene Adresse."
                    )
                elif _rollen_von(konto) & set(_ADMIN_ROLLEN):
                    # Konto MIT Verwaltungsrolle ohne eigenes Mitglied: nur der
                    # System Manager darf eine Person darauf anlegen (P1-8d).
                    # Ein Konto mit der Rolle „Mitglied“ ist kein Rechte-Risiko
                    # (W-b, Regression G2) — die Zeile wird angelegt.
                    raise FrappePermissionError(
                        "Diese Adresse gehört zu einem Verwaltungskonto — nur "
                        "ein System Manager darf ein Mitglied damit anlegen."
                    )

    mitglieder, konten = _kontozustand()
    alt = next((m for m in mitglieder if m["name"] == name), {}) if name else {}
    neu = {**alt, **values}
    neu["ausgeschlossen"] = _ist_ausgeschlossen(neu.get("ausgeschlossen"))
    if loeschen:
        # R1: Entfernen einer Dublette kann die E-Mail eines ausgeschlossenen
        # ANDEREN Mitglieds eindeutig machen. Kein künstlicher Ersatzdatensatz.
        nachher = [m for m in mitglieder if m["name"] != name]
    else:
        nachher = [neu if name and m["name"] == name else m for m in mitglieder]
        if not alt:
            nachher.append(neu)

    konten_alt = wirksame_konten(alt, _mitglieder=mitglieder, _konten=konten)
    konten_neu = set() if loeschen else wirksame_konten(neu, _mitglieder=nachher, _konten=konten)
    ausgeschlossen_alt = _ausgeschlossene_konten(mitglieder, konten)
    ausgeschlossen_neu = _ausgeschlossene_konten(nachher, konten)
    # Auch eine aufgehobene Mehrdeutigkeit kann ein ANDERES, bereits
    # ausgeschlossenes Mitglied wirksam machen. Deshalb den Gesamtzustand prüfen.
    neu_gesperrt = ausgeschlossen_neu - ausgeschlossen_alt
    # SEC (W1, Befund): dieselbe Pruefung fuer die GEGENrichtung. Ein
    # Konto mit Verwaltungsrolle, das aus dem Zustand "ausgeschlossen" in
    # "aktiv" wechselt, ist genauso eine Rechteaenderung wie das Sperren —
    # vorher prueften nur neu GESPERRTE Konten. Betroffen ist jedes Konto, das
    # nach dieser Aenderung frei ist: neu wirksam ueber user-Link/E-Mail ODER
    # nicht mehr ausgeschlossen (Ausschluss aufgehoben). Ohne den zweiten Teil
    # blieb `_update_doc({"ausgeschlossen": 0})` als Weg offen (Review-Probe V2).
    neu_freigegeben = (konten_neu - konten_alt) | (ausgeschlossen_alt - ausgeschlossen_neu)
    verknuepfung_geaendert = any(
        k in values and str(values[k] or "") != str(alt.get(k) or "")
        for k in ("user", "email")
    )
    if "user" in values:
        link = str(neu.get("user") or "").strip()
        if link and link != str(alt.get("user") or "").strip():
            _verweigere_fremdes_konto_verknuepfung(link)
    betroffen = set(neu_gesperrt) | neu_freigegeben
    if not loeschen and (neu["ausgeschlossen"] or verknuepfung_geaendert):
        betroffen |= konten_alt | konten_neu
    for konto in betroffen:
        if _rollen_von(konto) & set(_ADMIN_ROLLEN):
            _verweigere_fremdes_admin_konto_mitglied(
                konto,
                entsperren=konto in neu_freigegeben,
                vorgang=_vorgang_fuer(values, loeschen=loeschen),
            )

    aktive = _aktive_system_manager()
    if aktive and not _aktive_system_manager(_mitglieder=nachher, _konten=konten):
        raise FrappePermissionError(
            "Der letzte aktive System Manager kann nicht ausgeschlossen "
            "werden — sonst ist die Verwaltung ausgesperrt. Bitte zuerst "
            "einen weiteren System Manager benennen."
        )

    # SEC-c: erst NACH der Rechtefrage die Eindeutigkeit — wer ein
    # Verwaltungskonto umhaengen will, soll den Rechtegrund lesen (P1-8d),
    # nicht „Adresse gehört bereits zu …“. Ein Platzhalter („-“) ist beim
    # Normalisieren zu NULL geworden und belegt nichts.
    _pruefe_mitglied_email_eindeutig(values, name, loeschen=loeschen,
                                     bestand_email=alt.get("email"),
                                     eigenes_konto=alt.get("user"))


# ── Zentrale Schranke fuer Konto-/Rollen-Schreibzugriffe (W1, R-P1-8e) ──────
#
# DER BEFUND (W1)
# --------------------------------
# Der Aussperrschutz galt nur auf der Mitglied-Ebene. Ueber die generischen
# Wege liess sich der letzte aktive System Manager trotzdem aussperren:
#
#   * `DELETE /api/resource/Has Role/<eigene SM-Rolle>` -> 202, Rollen danach ()
#   * `PUT  /api/resource/User/<sm>` mit `{enabled: 0}` -> Konto inaktiv
#   * `DELETE /api/resource/User/<sm>` -> Konto weg
#
# Nur ein System Manager kommt an diese Wege (Mitgliederadministrator bekommt
# 403), also kein Eskalationspfad — aber die Zusage „der letzte aktive System
# Manager verliert nie seine Rolle/das Konto“ galt nur ueber die
# Zugang-Endpunkte. Die Schranke sitzt deshalb in der Schicht, durch die JEDER
# generische Schreibweg laeuft.
#
# DIE REGEL
# ---------
# Nach der geplanten Aenderung muss mindestens EIN aktives Konto die Rolle
# `System Manager` tragen (dieselbe Aufloesung wie `zugang._aktive_system_manager`:
# `enabled` UND nicht ueber ein wirksames Mitglied ausgeschlossen). Sonst
# verweigert `_pruefe_konto_schreibzugriff` mit `FrappePermissionError`.

_VERWALTUNGS_DOCTYPES = ("User", "Has Role")

# N12b (W1): Felder, die den Platz einer bestehenden Zeile bestimmen. Bei
# `Has Role` ist `parent` das Konto, `parenttype`/`parentfield` die Einordnung
# als Benutzer-Rolle; bei `User` ist `name` der Primaerschluessel (in dieser
# Installation die E-Mail-Adresse). Sie sind nach dem Anlegen unveraenderlich:
# jede Aenderung verschiebt oder entzieht stillschweigend eine Rolle. Ein
# Rollenwechsel gehoert ueber `role`, ein Kontowechsel ueber eine neue Zeile.
_UNVERAENDERLICHE_FELDER: dict[str, tuple[str, ...]] = {
    "Has Role": ("parent", "parenttype", "parentfield"),
    "User": ("name",),
}


def _has_role_alt(name: str) -> tuple[str, str]:
    """Der BESTEHENDE `(parent, role)` einer `Has Role`-Zeile (nicht `values`).

    Fuer den Aussperrschutz ist der Altstand massgeblich, wenn eine Zeile
    verschoben wird (W-a): der Befund nutzte `values["parent"]` als Zielkonto
    und verlor damit das alte Konto aus dem Blick. Rueckgabe `("", "")`, wenn
    die Zeile nicht existiert.
    """
    konto = str(get_value("Has Role", name, "parent") or "")
    rolle = str(get_value("Has Role", name, "role") or "")
    return konto, rolle


def _ist_letzter_system_manager(
    doctype: str, name: str | None, values: dict[str, Any], *, loeschen: bool
) -> bool:
    """Wuerde diese Aenderung den LETZTEN aktiven System Manager aussperren?

    Gilt fuer `User` (Konto sperren/loeschen) und `Has Role` (eine
    System-Manager-Rolle entfernen). `loeschen=True` entfernt die Zeile/das
    Konto. Rueckgabe `False`, wenn die Aenderung die Verwaltungsfaehigkeit
    nicht antastet.
    """
    if not name:
        return False
    from diakronos_app.api.zugang import _aktive_system_manager

    if doctype == "Has Role":
        alt_konto, alt_rolle = _has_role_alt(name)
        # W-a (R-N10): `values` darf `parent`/`role` ueberschreiben. Ein
        # verschobenes `parent` nahm der Schranke bisher das alte Konto aus
        # dem Blick (die Zeile wandert auf ein anderes Konto, das
        # urspruengliche Konto verliert seine SM-Rolle still).
        neu_konto = str((values or {}).get("parent") or alt_konto or "")
        neu_rolle = str((values or {}).get("role") or alt_rolle or "")
        # W1 (N12b): `parenttype` entscheidet, ob die Zeile ueberhaupt eine
        # Benutzer-Rolle ist (`permissions.ist_user_zeile`). Eine Zeile, die
        # auf einen Fremdtyp umgebogen wird, entzieht dem Konto die Rolle —
        # auf main war dieser Weg dicht, N12 hat ihn durch den
        # parenttype-Filter der Rollenleser geoeffnet.
        alt_user_zeile = ist_user_zeile(str(get_value("Has Role", name, "parenttype") or ""))
        neu_parenttype = (values or {}).get("parenttype")
        neu_user_zeile = (
            alt_user_zeile if neu_parenttype is None
            else ist_user_zeile(str(neu_parenttype))
        )
        if loeschen:
            if alt_rolle != "System Manager" or not alt_user_zeile:
                return False
            ziele = {k for k in (alt_konto, neu_konto) if k}
        else:
            # Entweder die Rolle wird von SM weggeaendert (alt==SM, neu!=SM)
            # ODER die Zeile wandert auf ein ANDERES Konto (parent aendert
            # sich) ODER sie ist nach der Aenderung keine Benutzer-Rolle mehr
            # — alles entzieht dem Altkonto die SM-Rolle.
            verliert_alt = alt_rolle == "System Manager" and (
                neu_rolle != "System Manager"
                or neu_konto != alt_konto
                or not neu_user_zeile
            )
            if not verliert_alt:
                return False
            # Das verlierende Konto ist der Alt-Parent (die Zeile wandert weg
            # oder wird umgerollt); ein NEUES Konto bringt keine Rolle.
            ziele = {k for k in (alt_konto, neu_konto) if k}
        aktive_sm = _aktive_system_manager()
        for ziel in ziele:
            if ziel in aktive_sm and len(aktive_sm) <= 1:
                return True
        return False
    ziel = str(name)

    aktive_sm = _aktive_system_manager()
    if ziel not in aktive_sm:
        return False
    # Nur wenn der Zielaccount der EINZIGE aktive SM ist, droht die Aussperrung.
    return len(aktive_sm) <= 1


def _pruefe_bestand_unveraenderlich(doctype: str, name: str | None, values: dict[str, Any]) -> None:
    """N12b (W1/P5): Platz einer BESTEHENDEN Zeile darf sich nicht aendern.

    `parent`, `parenttype`, `parentfield` einer `Has Role`-Zeile und `name`
    eines Kontos bestimmen, WEM eine Rolle gehoert. Werden sie still
    umgebogen, wandert oder verschwindet eine Rolle, ohne dass irgendwo ein
    Rollenwechsel sichtbar waere — inklusive der Aussperrung des letzten
    System Managers. Der Aussperrschutz allein faengt nur den letzten Fall;
    hier wird die Ursache geschlossen. Ungueltige `User`-Rollentypen legt
    bereits `_resource_denied`/`frappe.client.insert` ab, hier nicht.

    Unveraendert gesendete Werte (z.B. das ganze Dokument beim Speichern)
    bleiben erlaubt — verglichen wird mit dem Bestand.
    """
    felder = _UNVERAENDERLICHE_FELDER.get(doctype)
    if not felder or not name:
        return
    gesetzt = {f: (values or {}).get(f) for f in felder if f in (values or {})}
    if not gesetzt:
        return
    # N12b: die Zeile selbst muss existieren — bei einer NEUEN Zeile (Anlegen)
    # ist der `name` frei waehlbar, und es gibt nichts, was still verschoben
    # werden koennte. Nur der Bestand ist unveraenderlich.
    if get_value(doctype, str(name), "name") in (None, ""):
        return
    for feld, wert in gesetzt.items():
        alt = get_value(doctype, name, feld)
        # `alt is None` heisst hier: das Feld ist leer (Altdaten) — ein Wechsel
        # von NULL nach irgendetwas ist eine Aenderung und wird geprueft.
        # R-N12b: exakt vergleichen — " sm@x.org" ist ein anderer Wert (Leerraum-Luecke).
        if str(alt or "") != str(wert or ""):
            raise FrappePermissionError(
                f"Das Feld „{feld}“ einer bestehenden {doctype}-Zeile kann nicht "
                "geändert werden — bitte eine neue Zeile anlegen bzw. die Rolle "
                "über „role“ wechseln."
            )


def _ist_aktiv_flag(wert: Any) -> bool:
    """`enabled`-Wert normalisieren (`0`/`False` = nicht aktiv)."""
    if wert is None:
        return False
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    return str(wert).strip().lower() not in {"", "0", "false", "nein", "no", "none", "off"}


def _pruefe_konto_schreibzugriff(
    doctype: str, name: str | None, values: dict[str, Any], *, loeschen: bool = False
) -> None:
    """Zentrale Schranke fuer generische Schreibwege auf `User`/`Has Role` (W1).

    Sitzt in derselben Schicht wie `_pruefe_mitglied_schreibzugriff`: JEDER
    generische Weg (`/api/resource/...`, `frappe.client.insert`, direkt
    `_update_doc`/`_delete_doc`) laeuft hier hindurch. Ohne diese Schranke
    konnte sich der letzte System Manager ueber `Has Role`/`User` selbst
    aussperren (R-P1-8e, W1).

    Zwei Wirkungen werden erkannt:
      * `User.<name>` mit `enabled=0` oder das Konto selbst geloescht;
      * `Has Role.<zeile>` mit der System-Manager-Rolle entfernt/umgerollt.

    N12b (W1/P5): Zusaetzlich ist der Platz einer bestehenden Zeile
    unveraenderlich (`_pruefe_bestand_unveraenderlich`) — daran haengt, WEM
    eine Rolle gehoert.

    `values` sind die zu schreibenden Felder (bereits auf Spalten gefiltert),
    `name` ist die Kennung der Zeile (None beim Anlegen — dann kein Risiko).
    """
    if doctype not in _VERWALTUNGS_DOCTYPES or not name:
        return
    _pruefe_bestand_unveraenderlich(doctype, str(name), values or {})
    if doctype == "User" and not loeschen:
        if "enabled" not in (values or {}) or _ist_aktiv_flag((values or {}).get("enabled")):
            return
    if not _ist_letzter_system_manager(doctype, str(name), values or {}, loeschen=loeschen):
        return
    raise FrappePermissionError(
        "Der letzte aktive System Manager kann nicht gesperrt oder seiner "
        "Rolle enthoben werden — sonst ist die Verwaltung ausgesperrt. Bitte "
        "zuerst einen weiteren System Manager benennen."
    )


def _ist_ausgeschlossen(wert: Any) -> bool:
    """Flag-Wert normalisieren (P1-8d, Pflicht d).

    `'0'`/`0`/`False`/`None` heissen NICHT ausgeschlossen; `'1'`/`1`/`True`/
    `'true'` heissen ausgeschlossen. Ein `bool('0')` waere `True` und wuerde
    eine harmlose Aufhebung als Ausschluss behandeln — deshalb diese eine
    Normalisierung statt `bool(...)` an den Aufrufstellen.
    """
    if wert is None:
        return False
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)):
        return bool(wert)
    return str(wert).strip().lower() not in {"", "0", "false", "nein", "no", "none"}


def _mitglied_user(mitglied_id: str) -> str:
    """Der `user`-Link eines Mitglieds (leer, wenn keiner gesetzt ist)."""
    return str(get_value("Mitglied", mitglied_id, "user") or "")


#: Vorgangsnamen fuer die Meldung der Mitglied-Schranke (K1, SEC-c/SEC-d).
#: Die Schranke kennt nur die zu schreibenden Felder; der Vorgang wird dort
#: abgeleitet, wo er bekannt ist, und hier in Klartext uebersetzt. Jeder Text
#: ist ein praedikatives Satzglied — er passt ohne Adressbezug hinter
#: „darf ein Mitglied mit Verwaltungskonto nur ein System Manager …“.
VORGANG_TEXT = {
    "ausschluss": "ausschließen",
    "freigabe": "wieder freigeben",
    "status": "in seinem Status ändern",
    "bearbeitung": "bearbeiten",
    "anlage": "anlegen",
    "verknuepfung": "mit einem Konto verknüpfen",
    "email": "mit dieser Adresse führen",
}


def _vorgang_fuer(values: dict[str, Any], *, loeschen: bool) -> str:
    """Welcher Vorgang ist das? (K1: der Text soll zum Tun passen)

    `ausgeschlossen=1` ist ein Ausschluss, seine Aufhebung eine Freigabe, eine
    reine Statusaenderung ein Statuswechsel. Die Reihenfolge ist wichtig: ein
    Payload mit Status UND Ausschluss ist ein Ausschluss.
    """
    if loeschen:
        return "anlage"
    werte = values or {}
    if "ausgeschlossen" in werte:
        return "ausschluss" if _ist_ausgeschlossen(werte["ausgeschlossen"]) else "freigabe"
    if "status" in werte:
        return "status"
    if "user" in werte or "email" in werte:
        return "verknuepfung"
    return "bearbeitung"


def _verweigere_fremdes_admin_konto_mitglied(
    ziel_user: str, *, entsperren: bool = False, vorgang: str | None = None
) -> None:
    """(a) Ein Mitgliederadministrator darf kein Verwaltungskonto sperren.

    `entsperren=True` benennt die Gegenrichtung (SEC, W1):
    ein ausgeschlossenes Verwaltungskonto wieder wirksam machen ist dieselbe
    Rechteaenderung wie das Sperren und ebenfalls dem System Manager
    vorbehalten. Der Text nennt den tatsaechlichen Vorgang — sonst laese ein
    Mitgliederadministrator „ausschliessen“, waehrend er den Status aendert
    oder freigibt (K1, SEC-c).
    """
    from diakronos_app.api.zugang import _rollen_von

    if _ist_system_manager():
        return
    if _rollen_von(ziel_user) & set(_ADMIN_ROLLEN):
        if entsperren:
            raise FrappePermissionError(
                "Mitglieder mit Verwaltungskonto darf nur ein System Manager "
                "wieder freigeben."
            )
        # K1: Der Vorgang steht im Text. Vorher las jede Aenderung
        # „ausschließen“, auch eine reine Statusaenderung.
        was = VORGANG_TEXT.get(vorgang or "", "ändern oder ausschließen")
        if vorgang in ("verknuepfung", "email"):
            # Nur hier geht es um die ADRESSE des Mitglieds.
            raise FrappePermissionError(
                "Diese Adresse gehört zu einem Verwaltungskonto — nur ein "
                f"System Manager darf ein Mitglied damit {was}."
            )
        # Statuswechsel, Ausschluss, Freigabe, Bearbeitung: Subjekt ist die
        # PERSON, nicht ihre Adresse. „…ein Mitglied damit in seinem Status
        # ändern“ war sprachlich schief (K1).
        raise FrappePermissionError(
            "Ein Mitglied mit Verwaltungskonto darf nur ein System Manager "
            f"{was}."
        )


def _verweigere_fremdes_konto_verknuepfung(
    ziel_user: str, *, mitglied: str | None = None
) -> None:
    """(c) `Mitglied.user` umbiegen: nur System Manager bei fremden/Admin-Konten.

    Reproduziert von R-P1-8b: ein Mitgliederadministrator konnte ein beliebiges
    Mitglied auf ein System-Manager-Konto verbiegen — der Ausschluss dieses
    Mitglieds sperrte dann das Verwaltungskonto aus (`_mitglied_ausgeschlossen`
    findet es ueber den `user`-Link).
    """
    from diakronos_app.api.zugang import _konto_mitglieder, _rollen_von

    if _ist_system_manager():
        return
    if _rollen_von(ziel_user) & set(_ADMIN_ROLLEN):
        raise FrappePermissionError(
            "Ein Verwaltungskonto darf nur ein System Manager mit einem "
            "Mitglied verknuepfen."
        )
    andere = [m for m in _konto_mitglieder(ziel_user) if m != mitglied]
    if andere:
        raise FrappePermissionError(
            "Dieses Benutzerkonto gehoert bereits zu einem anderen Mitglied — "
            "das darf nur ein System Manager aendern."
        )


def _update_doc(
    doctype: str,
    name: str,
    values: dict[str, Any],
    skip_modified: bool = False,
    explizite_null: set[str] | None = None,
) -> None:
    """`doc.feld = ...; doc.save()` — nur gesetzte (nicht-None) Felder schreiben.

    `skip_modified=True` entspricht dem `update_modified=False` von
    `frappe.db.set_value` im Altcode: der Zaehler `anmeldungen_count` eines
    Registrierungslink wird dann OHNE Aenderung von `modified`/`modified_by`
    geschrieben (sonst wandert jeder Link bei jeder Anmeldung nach oben).

    `explizite_null` nennt Felder, die ein Aufrufer bewusst auf NULL setzen
    will (UXD-R6: ein leeres Geburtsdatum SOLL den Wert loeschen, wie
    `profile.update_my_profile` mit `geburtstag or None`). Sie werden auch als
    `None` geschrieben; alle anderen None-Werte bleiben wie bisher aussen vor
    (Frappe-Semantik fuer unberuehrte Felder).
    """
    from diakronos_app.db import sitzung_fuer_lesen

    model = model_for(doctype)
    cols = column_names(doctype)
    loeschen = explizite_null or set()
    data = {
        k: v
        for k, v in values.items()
        if k in cols and (v is not None or k in loeschen
                          or (doctype == "Mitglied" and k == "ausgeschlossen"))
    }
    if not data:
        return
    data = _coerce(doctype, _normalisiere_leere_links(doctype, data))
    if doctype == "Mitglied":
        # SEC-c: E-Mail normalisieren + Eindeutigkeit in Python, BEVOR die
        # Schranke den geplanten Zustand bewertet — die Meldung nennt die
        # Person und enthaelt nie SQL.
        data = _normalisiere_mitglied_email(data, name)
        if not data:
            return
        # P1-8c (Pflicht 1): Ausschluss und Konto-Verknuepfung laufen durch die
        # GENERISCHE Schicht — die Pruefung sitzt hier, nicht im Endpunkt.
        _pruefe_mitglied_schreibzugriff(data, name)
    elif doctype in _VERWALTUNGS_DOCTYPES:
        # W1 (R-P1-8e): derselbe Schutz fuer Konten und Rollen.
        _pruefe_konto_schreibzugriff(doctype, name, data)
    if not skip_modified:
        data["modified"] = _now()
        if "modified_by" in cols:
            data["modified_by"] = session.user

    sess, eigene = sitzung_fuer_lesen()
    try:
        obj = sess.get(model, name)
        if obj is None:
            raise DoesNotExistError(f"{doctype} {name!r} existiert nicht")
        for feld, wert in data.items():
            setattr(obj, feld, wert)
        _abschluss(sess, eigene)
    except FrappeCompatError:
        _ruecknahme(sess, eigene)
        raise
    except Exception as exc:  # noqa: BLE001
        _ruecknahme(sess, eigene)
        raise _db_fehler(exc, doctype) from exc
    finally:
        if eigene:
            sess.close()


def _beitrag_kommentare_loeschen(sess, name: str) -> None:
    """API und generischer CRUD loeschen Kinder in derselben Transaktion."""
    child_model = model_for("Beitrag Kommentar")
    sess.execute(child_model.__table__.delete().where(
        child_model.parent == name,
        child_model.parenttype == "Beitrag",
    ))


def _delete_doc(doctype: str, name: str) -> None:
    """`frappe.delete_doc(doctype, name, force=True)` — Zeile loeschen.

    Kind-Zeilen werden mitgeloescht (Frappe tut das ueber `on_trash` /
    Link-Cleanup); im Standalone-Backend gibt es keine DB-Fremdschluessel-
    Kaskade, deshalb raeumt die Portierung die zugehoerigen Kind-Tabellen
    fuer `Element` selbst auf.
    """
    from diakronos_app.db import sitzung_fuer_lesen

    model = model_for(doctype)
    sess, eigene = sitzung_fuer_lesen()
    try:
        obj = sess.get(model, name)
        if obj is None:
            return
        if doctype == "Mitglied":
            _pruefe_mitglied_schreibzugriff({}, name, loeschen=True)
        elif doctype in _VERWALTUNGS_DOCTYPES:
            # W1 (R-P1-8e): Loeschen eines Kontos oder einer Rolle darf den
            # letzten aktiven System Manager nicht aussperren.
            _pruefe_konto_schreibzugriff(doctype, name, {}, loeschen=True)
        if doctype == "Element":
            for child_doctype, parentfield in _ELEMENT_CHILD_TABLES.items():
                child_model = model_for(child_doctype)
                sess.execute(
                    child_model.__table__.delete().where(
                        child_model.parent == name,
                        child_model.parentfield == parentfield,
                    )
                )
        if doctype == "Beitrag":
            _beitrag_kommentare_loeschen(sess, name)
        sess.delete(obj)
        _abschluss(sess, eigene)
    except FrappeCompatError:
        _ruecknahme(sess, eigene)
        raise
    except Exception as exc:  # noqa: BLE001
        _ruecknahme(sess, eigene)
        raise _db_fehler(exc, doctype) from exc
    finally:
        if eigene:
            sess.close()


# ── Kind-Tabellen ───────────────────────────────────────────────────────────

# Kind-Tabellen von `Element` und das jeweilige Elternfeld.
_ELEMENT_CHILD_TABLES: dict[str, str] = {
    "Element Ressource": "zusaetzliche_ressourcen",
    "Element Mitarbeiter": "mitarbeiter",
}

# Kind-Tabelle -> Eltern-DocType (Frappe-Konvention `parenttype`). Die Liste
# hing frueher als literales Dict in `_parenttype_for` und wuchs nur mit, wenn
# jemand daran dachte: `Anmeldeformular Feld` fehlte, und die Zeilen landeten
# mit `parenttype = "Anmeldeformular Feld"` in der Datenbank (OP-ADMIN-19).
# Frappe schreibt dort IMMER den Eltern-DocType — eine Zeile, die
# `parenttype != "Anmeldeformular"` traegt, ist fuer jede Kind-Tabellen-Abfrage
# unsichtbar, obwohl sie existiert. Die Tabelle ist deshalb genau eine
# Zuordnung je Kind-DocType (siehe `_parenttype_for`).
_PARENTTYPE: dict[str, str] = {
    "Element Ressource": "Element",
    "Element Mitarbeiter": "Element",
    "Kalender Moderator": "Kalender",
    "User Role": "Kalender",
    "Ablaufplan Position": "Ablaufplan",
    "Anmeldeformular Feld": "Anmeldeformular",
    "Anmeldeformular Dokument": "Anmeldeformular",
}


def _parenttype_for(child_doctype: str, parent: str | None = None) -> str:
    """Eltern-DocType zu einer Kind-Tabelle (Frappe-Konvention `parenttype`).

    Frappe schreibt dort IMMER den DocType des ELTERNTEILS ab (nie den der
    Kind-Tabelle). Zwei Quellen, in dieser Reihenfolge:
      1. die gepflegte Zuordnung `_PARENTTYPE` (kennt den echten Eltern-DocType
         auch dort, wo der Name der Kind-Tabelle nicht darauf schliesst),
      2. die Ableitung aus dem Mapping (`child_doctype_parent`).
    Ohne Treffer bleibt der Kind-Name stehen — so wie vorher.
    """
    from diakronos_app.frappe_compat.registry_gen import child_doctype_parent

    return (
        _PARENTTYPE.get(child_doctype)
        or child_doctype_parent(child_doctype)
        or child_doctype
    )


def _child_insert(
    child_doctype: str,
    parent: str,
    parentfield: str,
    values: dict[str, Any],
    parenttype: str | None = None,
) -> str:
    """`doc.append(parentfield, {...})` einer Kind-Tabelle + Speichern.

    `Document` kennt bewusst kein `append`; Kind-Zeilen werden daher direkt
    geschrieben — mit derselben Dreiteilung parent/parenttype/parentfield wie
    in Frappe und `idx` als naechste Position im Elternfeld.
    """
    if not is_known(child_doctype):
        raise ValidationError(f"DocType {child_doctype!r} nicht gefunden")

    from sqlalchemy import func, select

    from diakronos_app.db import sitzung_fuer_lesen

    model = model_for(child_doctype)
    cols = column_names(child_doctype)

    sess, eigene = sitzung_fuer_lesen()
    try:
        max_idx = sess.execute(
            select(func.max(model.idx)).where(
                model.parent == parent, model.parentfield == parentfield
            )
        ).scalar()
        data = dict(values)
        # ID-1d: Kind-Zeilen einer PERSON (Antworten/Kinder einer Anmeldung,
        # Bereiche/Beziehungen eines Mitglieds) tragen ebenfalls nur
        # serverseitige Kennungen. Andere Kind-Tabellen behalten die bisherige
        # Regel (eine mitgegebene Kennung bleibt stehen).
        eltern = parenttype or _parenttype_for(child_doctype, parent)
        if _ist_personen_kennung(eltern):
            data.pop("name", None)
        data["name"] = data.get("name") or _new_name()
        data["parent"] = parent
        data["parenttype"] = eltern
        data["parentfield"] = parentfield
        data["idx"] = (int(max_idx) + 1) if max_idx is not None else 1
        for key, value in _meta_fields().items():
            data.setdefault(key, value)
        data = {k: v for k, v in data.items() if k in cols}
        data = _coerce(child_doctype, _normalisiere_leere_links(child_doctype, data))
        obj = model(**data)
        sess.add(obj)
        _abschluss(sess, eigene)
        return data["name"]
    except FrappeCompatError:
        _ruecknahme(sess, eigene)
        raise
    except Exception as exc:  # noqa: BLE001
        _ruecknahme(sess, eigene)
        raise _db_fehler(exc, child_doctype) from exc
    finally:
        if eigene:
            sess.close()


def _child_delete(child_doctype: str, parent: str, parentfield: str, filters: dict[str, Any] | None = None) -> int:
    """Kind-Zeilen eines Elternfeldes entfernen. Gibt die Anzahl zurueck."""
    from diakronos_app.db import sitzung_fuer_lesen

    model = model_for(child_doctype)
    sess, eigene = sitzung_fuer_lesen()
    try:
        conditions = [model.parent == parent, model.parentfield == parentfield]
        for feld, wert in (filters or {}).items():
            conditions.append(getattr(model, feld) == wert)
        result = sess.execute(model.__table__.delete().where(*conditions))
        _abschluss(sess, eigene)
        return int(result.rowcount or 0)
    except FrappeCompatError:
        _ruecknahme(sess, eigene)
        raise
    except Exception as exc:  # noqa: BLE001
        _ruecknahme(sess, eigene)
        raise _db_fehler(exc, child_doctype) from exc
    finally:
        if eigene:
            sess.close()


def _child_replace(child_doctype: str, parent: str, parentfield: str, rows: list[dict[str, Any]]) -> None:
    """`doc.<feld> = []` + `doc.append(...)` je Zeile — Kind-Tabelle ersetzen.

    Entspricht exakt `_apply_additional_resources` / `_apply_mitarbeiter` des
    Originals: erst alles loeschen, dann die validen Zeilen in Reihenfolge
    neu anlegen (idx 1..n).
    """
    _child_delete(child_doctype, parent, parentfield)
    for row in rows:
        _child_insert(child_doctype, parent, parentfield, row)


# ── Lese-Helfer ─────────────────────────────────────────────────────────────


def _child_rows(
    child_doctype: str,
    parent: str,
    parentfield: str,
    fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Kind-Zeilen eines Elternfeldes, nach `idx` sortiert."""
    cols = column_names(child_doctype)
    wanted = [f for f in (fields or []) if f in cols]
    if not wanted:
        wanted = [c for c in ("name", "parent", "idx") if c in cols]
    return list(
        get_all(
            child_doctype,
            filters={"parent": parent, "parentfield": parentfield},
            fields=wanted,
            order_by="idx asc",
        )
        or []
    )  # type: ignore[return-value]


def _count(doctype: str, filters: dict[str, Any] | None = None) -> int:
    return int(_db.count(doctype, filters) or 0)


def _bulk_update_by_field(
    doctype: str,
    where_field: str,
    where_value: Any,
    updates: dict[str, Any],
    ausschluss_status: str | None = None,
) -> int:
    """`UPDATE <doctype> SET <updates> WHERE <where_field> = <value>` (Massenupdate).

    Ersetzt das rohe `frappe.db.sql("UPDATE ... WHERE series_id = %s", ...)` aus
    dem Altcode. Die Compat-Schicht (`db.sql`) versteht nur `%(name)s`-Platzhalter,
    Positional-`%s` waere ein stiller Fehlschlag — deshalb geht der Massenupdate
    ueber die SQLAlchemy-Tabelle. Feldnamen stammen weiterhin aus der Whitelist
    des Aufrufers; die Spaltennamen werden gegen das Modell geprueft.

    `ausschluss_status` (W-A, R-P1-8): Zeilen mit diesem Status bleiben
    unveraendert. Der Serien-Batch schliesst damit `Abgelehnt` aus — ein
    abgelehnter Termin ist erledigt und wird nicht mehr mitgeaendert.
    """
    from sqlalchemy import update as sa_update

    from diakronos_app.db import sitzung_fuer_lesen

    model = model_for(doctype)
    cols = column_names(doctype)
    if where_field not in cols:
        raise ValidationError(f"Unbekanntes Feld: {doctype}.{where_field}")
    clean = {k: v for k, v in updates.items() if k in cols}
    if not clean:
        return 0
    if "modified" in cols:
        clean["modified"] = _now()

    sess, eigene = sitzung_fuer_lesen()
    try:
        column = getattr(model, where_field)
        # `series_id` ist nullable; `IS NULL` fuer leere Serien-IDs nicht noetig,
        # der Aufrufer uebergibt immer eine konkrete Serien-ID.
        bedingung = column == where_value
        if ausschluss_status is not None and "status" in cols:
            bedingung = bedingung & (model.status != ausschluss_status)
        result = sess.execute(sa_update(model).where(bedingung).values(**clean))
        _abschluss(sess, eigene)
        return int(result.rowcount or 0)
    except FrappeCompatError:
        _ruecknahme(sess, eigene)
        raise
    except Exception as exc:  # noqa: BLE001
        _ruecknahme(sess, eigene)
        raise _db_fehler(exc, doctype) from exc
    finally:
        if eigene:
            sess.close()



def _require(condition: bool, message: str, exc: type[FrappeCompatError] = FrappePermissionError) -> None:
    """`frappe.throw(msg, exc)` als Guard."""
    if not condition:
        throw(message, exc)


def _rethrow(e: Exception, context: str) -> None:
    """Fehler aus dem Fachcode weiterreichen, OHNE den Typ zu verlieren.

    Die Original-Endpunkte hatten `except Exception as e: frappe.throw(str(e))`.
    In Frappe bleibt der Original-Typ dabei erhalten (der Request endet mit dem
    passenden HTTP-Status). Beim Portieren wuerde `throw(str(e))` einen
    PermissionError in einen generischen ValidationError (HTTP 500/417)
    verwandeln — der Router braucht aber 403. Deshalb: Compat-Fehler
    unveraendert erneut werfen, alles andere loggen und fachlich melden.
    """
    if isinstance(e, FrappeCompatError):
        raise e
    from sqlalchemy.exc import SQLAlchemyError
    if isinstance(e, SQLAlchemyError):
        raise _db_fehler(e, context) from e
    log_error(f"{context}: {e}", context)
    throw(str(e))
