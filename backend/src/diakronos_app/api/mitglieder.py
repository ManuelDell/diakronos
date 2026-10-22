"""Portierung von `diakronos.diakonos.api.mitglieder` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/mitglieder.py`

Uebersetzt heisst hier: **dieselbe Signatur, dieselbe Antwortstruktur, dieselbe
Logik.** Portiert:

    P2b:  get_mitglieder_liste(start, limit, suche, status, sort_by, sort_order)
          get_mitglied_detail(mitglied_id)
    P4k:  create_mitglied(...), update_mitglied(...),
          update_mitglied_with_confirmation(...), get_gruppen_for_mitglied(...),
          get_beziehungen_for_mitglied(...), widerruf_einwilligung(...),
          get_adressbuch(...)

Damit ist das Modul vollstaendig (alle `@frappe.whitelist`-Funktionen der
Vorlage sind uebernommen).

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.session.user        -> frappe.session.user
    frappe.get_roles(user)     -> permissions (siehe unten)
    frappe.db.sql(...)         -> db.sql(...)   (parametrisiert, unveraendert)
    frappe.db.get_value(...)   -> frappe.db.get_value(...)
    frappe.get_doc(...)        -> frappe.get_doc(...)
    frappe.get_all(...)        -> frappe.get_all(...)
    frappe.db.get_value(..., "CONCAT_WS(...)") -> _full_name()-Helper (SQLite/PG)
    frappe.local.audit_confirmation -> _Flags-Halter (audit_confirmation)
    log_einwilligung(...)      -> api.dsgvo_log.log_einwilligung(...)

ABWEICHUNG `log_einwilligung`: Die Vorlage importiert
`diakonos.api.dsgvo_log.log_einwilligung` und schreibt damit in NUR EINER
Tabelle `DSGVO Einwilligung` (typ/aktion/quelle/ip/user_agent). Das
Standalone-Modell fuehrt diese Spalten seit P1d — die Portierung schreibt
daher dieselbe Tabelle mit denselben Feldern (Helfer
`api/dsgvo_log.py` weiter unten). Zusaetzlich werden beim Widerruf
`widerrufen`/`widerruf_datum`/`widerruf_begruendung` am Datensatz gesetzt,
weil die Karte das ausdruecklich fordert (Beleg fuer Auskunftsersuchen).

PERMISSION (P3-Logik, siehe `frappe_compat/permissions.py`):
`_is_admin()` prueft die Rolle; `permissions.mitglied_permissions()` liefert
`can_view`/`can_edit` fuer Nicht-Admins. Die Sichtbarkeitslisten
(`get_mitglieder_liste`, `get_adressbuch`) sind per `ancestor_path`-Overlap
bzw. E-Mail-Selbstmatch gefiltert. Die drei P2b-Platzhalter, die in P4l
ersetzt wurden, sind: `_is_admin`, `_user_email` und der Sichtbarkeitsfilter
in `get_mitglieder_liste`. Die Regel selbst stammt weiterhin ausschliesslich
aus `frappe_compat.permissions` (keine zweite Fassung im API-Modul).
"""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata

# Original-Frappe-Modulpfad. Die SPA ruft ausschliesslich diese Form auf;
# die Registry registriert daraus `diakronos.diakonos.api.mitglieder.<funktion>`.
FRAPPE_MODULE = "diakronos.diakonos.api.mitglieder"

from diakronos_app.frappe_compat.api_helpers import (
    _ADMIN_ROLLEN,
    _create,
    _delete_doc,
    _ist_email_eindeutigkeit,
    _ist_system_manager,
    _now,
    _rethrow,
    _today,
    _update_doc,
    column_names,
    log_error,
)
from diakronos_app.api.austritt import STATUS_AUSGETRETEN as _STATUS_AUSGETRETEN
from diakronos_app.api.dsgvo_log import log_einwilligung
from diakronos_app.frappe_compat import db, get_all, get_doc, session, whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.mitglied_sichtbarkeit import (
    eigenes_mitglied_id,
    ist_eigenes_mitglied,
    maskiere_datensatz,
    maskiere_zeilen,
)
from diakronos_app.frappe_compat.query import get_value
from diakronos_app.email_belegung import normalisiere

# Quelle: mitglieder.py:12
ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


def _is_admin() -> bool:
    """Admin-Test wie im Original: `any(r in roles for r in ADMIN_ROLES)`.

    `permissions.has_role()` ist die Compat-Entsprechung von
    `"x" in frappe.get_roles()` und liefert fuer `Guest` sowie unbekannte
    Benutzer `False`.

    Aufrufer, die die Rollen bereits geholt haben, nehmen `_has_admin_role()`
    und vermeiden die zweite DB-Abfrage — so wie das Original die Rollen genau
    einmal in `roles` haelt.
    """
    return any(permissions.has_role(r) for r in ADMIN_ROLES)


def _has_admin_role(user: str, roles) -> bool:
    """`any(r in roles for r in ADMIN_ROLES)` auf bereits geholten Rollen.

    Quelle: `mitglieder.py:24-25` — das Original holt die Rollen einmal
    (`frappe.get_roles(user)`, Zeile 24) und prueft sie danach an beliebig
    vielen Stellen erneut gegen dieselbe Liste. Eine erneute DB-Abfrage je
    Pruefung waere dieselbe Antwort mit mehr Last; dieselbe Antwort ist hier
    Pflicht, keine Optimierung: zwei Rollenquellen in einer Funktion koennten
    auseinanderlaufen und damit Sicht erzeugen.
    """
    if user == "Guest":
        return False
    return any(r in roles for r in ADMIN_ROLES)


def _eigenes_mitglied_ids() -> list[str]:
    """Name des eigenen Mitglieds — die Liste der Namen, die **vollstaendig**
    geliefert werden duerfen.

    B2. Fuer einen Nicht-Admin ist das hoechstens ein Name (der eigene
    Datensatz). Ein Admin kommt hier gar nicht vor: `get_mitglieder_liste`
    ruft die Funktion nur im `not is_admin`-Zweig auf, und `mitglied_permissions`
    wertet Admin ueber die Rollen, nicht ueber diesen Pfad.
    """
    eigene_id = eigenes_mitglied_id()
    return [eigene_id] if eigene_id else []


# ── Liste / Uebersicht ──────────────────────────────────────────────────────


def _suche_normalisieren(text: str) -> str:
    """BF1-J: Suchbegriff fuer den Vergleich normalisieren.

    Kleinbuchstaben, Umlaute und „ß“ aufgeloest (ü -> ue, ß -> ss) — genau wie
    die SPA. Damit findet „weiss“ den Eintrag „Weiß“ und „MUELLER“ den Eintrag
    „Müller“, unabhaengig von der Schreibweise.

    K8: Der Begriff wird zuerst getrimmt und in die zuammengesetzte Form
    (Unicode-NFC) gebracht. Ohne Trim lieferte „müller “ serverseitig nichts,
    waehrend die SPA (deren `suchNormal` trimmt) traf; ohne NFC passte ein
    zerlegtes „u + Trema“ (typisch aus macOS-Eingaben) nicht zur REPLACE-Kette
    und der Treffer fiel aus.
    """
    text = unicodedata.normalize("NFC", str(text or "")).strip()
    return (
        text.lower()
        .replace("ß", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
    )


def _suche_ausdruck(spalte: str) -> str:
    """BF1-J: SQL-Ausdruck, der eine Spalte klein- UND umlautgefaltet liefert.

    `LOWER` allein genuegt nicht: Postgres' `LIKE` ist case-sensitiv, und
    SQLites `LOWER` laesst Nicht-ASCII (Umlaute) unveraendert — ein
    gespeichertes „MÜLLER“ bliebe „mÜller“. Deshalb werden zuerst BEIDE
    Schreibweisen der Umlaute/ß ersetzt und erst danach `LOWER` angewandt.
    Damit stimmen beide Datenbanken ueberein. Der Ausdruck verwendet keine
    Nutzereingabe — `spalte` ist ein fester Bezeichner aus dieser Datei
    (kein Injection-Pfad).
    """
    ausdruck = spalte
    for von, nach in (("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
                      ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        ausdruck = f"REPLACE({ausdruck}, '{von}', '{nach}')"
    return f"LOWER({ausdruck})"


@whitelist(allow_guest=False)
def get_mitglieder_liste(start=0, limit=20, suche="", status="", sort_by="name", sort_order="asc",
                         persoenliche_daten=False, mit_zaehlung=True):
    """
    Gibt paginierte Mitglieder-Liste zurueck.
    Respektiert Permissions: Admin sieht alle, User nur eigene Gruppe/Bereich.

    W7 — persönliche Daten server-seitig (nicht nur in der Anzeige): Mit
    ``persoenliche_daten=False`` (Vorgabe) laesst die Liste die sensiblen
    Felder (Telefon, Adresse, Geburtstag, E-Mail) WEG — sie stehen dann nicht
    einmal im HTTP-Antwortkoerper. ``persoenliche_daten=True`` ist nur fuer
    Admins wirksam; ein Nicht-Admin bleibt bei der maskierten Fassung
    (fail closed). Die Anzeige-Fassung in der SPA koppelt daran denselben
    Schalter, damit Liste und Unterzeile uebereinstimmen.
    """
    user = session.user
    roles = permissions.get_roles(user)

    # Ersetzt den `_is_admin()`-Kurzschluss: das Original wertet die Rollen
    # GENAU EINMAL aus (mitglieder.py:23-25) und benutzt `is_admin` danach nur
    # noch als Variable. `_has_admin_role(user, roles)` ist dieselbe Pruefung auf
    # denselben Rollen — inklusive der `Guest`-Sonderbehandlung der Compat-Schicht.
    is_admin = _has_admin_role(user, roles)

    # W7: persönliche Daten nur fuer Admins UND nur, wenn ausdruecklich
    # angefordert. Die Zeichenkette "0"/"false" aus einem Formularfeld/Query
    # zaehlt als Nein (die SPA sendet echte Booleans, aber der Endpunkt ist
    # auch direkt aufrufbar).
    persoenliche_daten = bool(persoenliche_daten) and str(persoenliche_daten).lower() not in (
        "0", "false", "", "none",
    )
    zeige_persoenliches = bool(is_admin and persoenliche_daten)

    # Sortierung validieren (SQL-Injection-Schutz) — unveraendert aus dem Original.
    allowed_sort_fields = {
        "name", "vorname", "nachname", "email", "status",
        "geburtstag", "wohnort", "postleitzahl", "creation", "modified",
    }
    if not is_admin and sort_by in {"email", "geburtstag", "wohnort", "postleitzahl"}:
        throw("Sortierung nach privaten Mitgliedsfeldern nicht erlaubt.", PermissionError)
    if sort_by not in allowed_sort_fields:
        sort_by = "name"
    sort_order = "desc" if str(sort_order).lower() == "desc" else "asc"

    params = {
        "start": int(start),
        "limit": int(limit),
        # BF1-J: Der Vergleichswert ist klein- und umlautgefaltet (siehe
        # `_suche_normalisieren`). Das Original benutzte `f"%{suche}%"`.
        "suche": f"%{_suche_normalisieren(suche)}%" if suche else "%%",
    }

    # B2: Das Original sucht in `vorname`, `nachname` **und** `email`
    # (mitglieder.py:92-96). `email` ist eines der vier Adressbuch-Felder —
    # wer es nicht freigegeben hat, darf daran nicht auch noch gesucht
    # werden, sonst ist die Maskierung ein Loch: "ich kenne B's E-Mail und
    # frage nach" -> die Zeile erscheint oder nicht, je nachdem was B
    # eingestellt hat. Genau der Seitenkanal, den die Karte verbietet.
    #
    # Fuer berechtigte Leser (Admin) bleibt die Suche unveraendert. Fuer
    # alle anderen wird das E-Mail-Glied **ersatzlos gestrichen** (nicht
    # auf eigene Zeilen umgestellt) — das ist die fail-closed-Variante:
    # ein nicht parsebarer Blob darf nie zu einer zu weiten Suche fuehren.
    # Namen sind kein Adressbuch-Feld und bleiben unberuehrt.
    durchsucht_email = is_admin

    filters_sql = ""
    if status:
        filters_sql += " AND m.status = %(status)s"
        params["status"] = status

    # Permission-Filter — 1:1 aus dem Original (mitglieder.py:47-70).
    # Die Hierarchie-Logik liegt NICHT hier: `_get_current_user_mitglied()` ->
    # `permissions` und `_extract_path_segments()` -> `permissions._extract_segments`,
    # damit es genau EINE Fassung der Pfad-Zerlegung gibt.
    permission_filter_sql = "1=1"
    if not is_admin:
        # Normaler User: nur ueberlappende ancestor_paths
        current_mitglied = _get_current_user_mitglied()
        if not current_mitglied:
            permission_filter_sql = "1=0"
        elif current_mitglied.get("ancestor_path"):
            segments = _extract_path_segments(current_mitglied["ancestor_path"])
            if segments:
                like_clauses = []
                for idx, seg in enumerate(segments):
                    key = f"seg_{idx}"
                    like_clauses.append(
                        f"CONCAT('/', COALESCE(m.ancestor_path, ''), '/') LIKE %({key})s"
                    )
                    params[key] = f"%/{seg}/%"
                permission_filter_sql = "(" + " OR ".join(like_clauses) + ")"
            else:
                # User hat Pfad aber keine Segmente -> Fallback auf eigenes Profil
                permission_filter_sql = "m.email = %(user_email)s"
                params["user_email"] = _user_email()
        else:
            # User ohne ancestor_path: nur eigenes Profil via Email-Match
            permission_filter_sql = "m.email = %(user_email)s"
            params["user_email"] = _user_email()

    eigene_ids = _eigenes_mitglied_ids() if not is_admin else []
    if eigene_ids:
        params["own_mid"] = eigene_ids[0]
        permission_filter_sql = f"({permission_filter_sql} OR m.name = %(own_mid)s)"

    # AUSTRITT A5: „Ausgetretene anzeigen“ ist ein eigener Filter. Er steht als
    # SQL-Glied (nicht als Python-Nachfilter), damit `total` die gleiche Menge
    # zaehlt wie die Liste — sonst zeigte die Liste weniger Zeilen als
    # „geladen von gesamt“ behauptet.
    ausgetreten_gefragt = str(status or "").strip().lower() in AUSGETRETEN_STATUS
    # AUSTRITT-b (B3): Ausgeblendet wird nur der AUSGETRETENE, nicht jeder
    # Ausgeschlossene. Der Branch blendete `ausgeschlossen` aus und nahm damit
    # auch die „Passiven Gäste“ (Ausschluss, Fehlverhalten) aus Liste, Suche,
    # Zaehlung und Export — der Weg zum Aufheben („Status im Profil ändern“)
    # war damit versperrt. Ausgetreten ist, wer den Status „Ausgetreten“
    # traegt ODER einen Austrittsgrund hat (die Marke allein traegt beides).
    sichtbarkeits_glied = (
        "" if ausgetreten_gefragt else
        # AUSTRITT-d (NN5): das `austritt_datum` gehoert dazu — ein Austritt
        # ohne Begruendung (seit N1 moeglich) setzt nur Status und Datum;
        # ohne das Datum zeigte der Chip „Ausgetreten 0“ und der Filter holte
        # die Zeile trotzdem.
        " AND NOT (COALESCE(m.status, '') = 'Ausgetreten'"
        " OR COALESCE(TRIM(m.austritt_grund), '') <> ''"
        " OR m.austritt_datum IS NOT NULL)"
    )
    # LIMIT/OFFSET: OFFSET statt MySQL-`LIMIT start, limit`, damit die Abfrage
    # auf PostgreSQL UND SQLite (Tests) laeuft. Semantik identisch.
    # Das E-Mail-Glied der Suche ist selbst eine Sichtbarkeitsfrage (siehe
    # `durchsucht_email`). Beide Abfragen — Daten und Count — muessen
    # dieselbe Bedingung benutzen, sonst widerspricht `total` der Liste.
    # BF1-J: Die Suche darf Gross-/Kleinschreibung UND die Umlautschreibweise
    # nicht beachten. `LOWER(...)` allein reicht nicht (Postgres' LIKE ist
    # case-sensitiv; SQLites LOWER laesst Umlaute unveraendert) — deshalb der
    # umlautfaltende Ausdruck. Das E-Mail-Glied ist selbst eine
    # Sichtbarkeitsfrage (siehe `durchsucht_email`).
    suchspalten = ["m.vorname", "m.nachname"]
    if durchsucht_email:
        suchspalten.append("m.email")
    suchglieder = []
    for i, wort in enumerate(_suche_normalisieren(suche or "").split()):
        key = f"suche_{i}"
        params[key] = f"%{wort}%"
        suchglieder.append("(" + " OR ".join(
            f"{_suche_ausdruck(spalte)} LIKE %({key})s" for spalte in suchspalten
        ) + ")")
    suche_glied = " AND ".join(suchglieder) or "1=1"

    # W7: Persönliche Werte gibt es nur auf Anforderung und nur für Admins.
    # Die SPALTE wird immer gelesen — die SPA-Struktur (Schlüssel vorhanden,
    # Wert `null`) bleibt damit erhalten (B2-Vertrag), aber ohne Anforderung
    # wird der Wert serverseitig auf `None` gesetzt. Es steht dann kein
    # persönlicher Wert im Antwortkörper, auch nicht für einen Admin.
    spalten_sql = ",\n            ".join([
        "m.name",
        "m.vorname",
        "m.nachname",
        "CONCAT_WS(' ', NULLIF(m.vorname, ''), NULLIF(m.nachname, '')) as full_name",
        "m.email",
        # AUSTRITT A3: die Adresse wird zusaetzlich roh gelesen, damit die
        # maskierte Form („elv*******.de“) auch dann entsteht, wenn die
        # Adressbuch-Sichtbarkeit das Feld `email` auf `None` gesetzt hat.
        # Die Spalte heisst bewusst anders als `email` und wird nach der
        # Kuerzung wieder entfernt — sie verlaesst die Antwort nie.
        'm.email AS "_austritt_email"',
        "m.status",
        "m.ausgeschlossen",
        "m.austritt_datum",
        "m.foto",
        "m.telefonnummer",
        "m.geburtstag",
        "m.postleitzahl",
        "m.wohnort",
        'm."straße"',
        "m.nummer",
        "m.geschlecht",
        "m.familienstand",
        "m.ancestor_path",
        "m.adressbuch_sichtbarkeit",
    ])
    # Felder, die ohne ausdrückliche Anforderung auf `None` gesetzt werden.
    persoenliche_felder = (
        "email", "telefonnummer", "geburtstag", "postleitzahl", "wohnort",
        "straße", "nummer", "geschlecht", "familienstand",
    )

    query = f"""
        SELECT
            {spalten_sql}
        FROM mitglied m
        WHERE 1=1
          AND {suche_glied}
          {sichtbarkeits_glied}
          {filters_sql}
          AND {permission_filter_sql}
        ORDER BY m."{sort_by}" {sort_order}
        LIMIT %(limit)s OFFSET %(start)s
    """

    data = db.sql(query, params, as_dict=True)

    # B2: Adressbuch-Sichtbarkeit durchsetzen. Admin sieht alles; sonst
    # sieht der Aufrufer sein eigenes Mitglied vollstaendig und alle
    # anderen nur die freigegebenen Felder. `adressbuch_sichtbarkeit` wird
    # aus der Antwort entfernt — die Liste hat sie vorher nie geliefert,
    # ein neues Feld in einer Listenzeile waere eine stille
    # Vertragsaenderung.
    if not is_admin:
        data = maskiere_zeilen(
            [dict(z) for z in (data or [])],
            vollstaendig_ids=eigene_ids,
        )
    elif not zeige_persoenliches:
        # W7: Ein Admin, der die persönlichen Daten NICHT angefordert hat,
        # bekommt sie auch nicht — die Schlüssel bleiben (B2: SPA-Struktur),
        # die Werte werden `None`.
        for zeile in data:
            for feld in persoenliche_felder:
                if feld in zeile:
                    zeile[feld] = None

    # Die zusaetzlich gelesene Policy war nie ein Listenfeld, auch nicht
    # fuer eigene/admin Zeilen. Details behalten fuer Berechtigte doc.as_dict().
    for zeile in data:
        zeile.pop("adressbuch_sichtbarkeit", None)

    # AUSTRITT A3/A5: Ausgetretene Personen erscheinen standardmaessig NICHT
    # mehr in der Liste („Ausgetretene anzeigen“ ist ein eigener Filter, der
    # `status=Ausgetreten` setzt). Wer sie ausdruecklich anfordert, sieht sie —
    # und eine gekuerzte Person liefert das Backend ohne Klarname/Klar-Mail
    # (`personen_anzeige`).
    #
    # REIHENFOLGE: Die Kuerzung laeuft NACH der Adressbuch-Maskierung oben.
    # Umgekehrt (vorher) setzte `maskiere_datensatz` die schon gekuerzte
    # Adresse wieder auf `None` — die Liste zeigte dann gar keine Adresse,
    # und die Fachentscheidung „erste drei Zeichen + Sterne“ waere nicht
    # sichtbar.
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, kuerze_zeilen

    alle_zeilen: list[dict] = []
    for z in data or []:
        zeile = z if isinstance(z, dict) else dict(z)
        roh = zeile.get("_austritt_email")
        zeile.pop("_austritt_email", None)
        if roh:
            zeile["_austritt_email_roh"] = roh
        alle_zeilen.append(zeile)
    data = kuerze_zeilen(alle_zeilen, PersonenSicht.aus(), email_feld="_austritt_email_roh")
    for zeile in data:
        zeile.pop("_austritt_email_roh", None)

    # Total-Count fuer Pagination — derselbe Filter wie die Datenabfrage.
    # N11b/K2: Der Export blaettert die Liste in 500er-Schritten ab und braucht
    # die Zaehlung nur einmal (erste Seite). `mit_zaehlung=False` ueberspringt
    # BEIDE Zusatzabfragen (Count und Statuszaehler) fuer die Folgeseiten.
    # Der Vorgabewert bleibt True: die Anzeige verlaesst sich darauf.
    if not bool(mit_zaehlung):
        return {
            "success": True,
            "data": data,
            "total": None,
            "start": int(start),
            "limit": int(limit),
            "status_zaehler": {},
            "gesamt_alle": None,
        }

    count_query = f"""
        SELECT COUNT(*) as total
        FROM mitglied m
        WHERE 1=1
          AND {suche_glied}
          {filters_sql}
          {sichtbarkeits_glied}
          AND {permission_filter_sql}
    """
    total_result = db.sql(count_query, params, as_dict=True)
    total = total_result[0]["total"] if total_result else 0

    # Operator-Nachtrag N11 (Befund 10): Die Statuszahlen im Filter zaehlten
    # vorher die geladenen Zeilen (Seitengroesse 30) — bei mehr Mitgliedern
    # stimmte keine Zahl. Jetzt zaehlt der Server ueber ALLE sichtbaren
    # Mitglieder, mit demselben Sichtbarkeits- und Suchfilter wie die Liste,
    # aber OHNE den Statusfilter selbst (sonst waere jede Zahl 0).
    zaehl_params = {k: v for k, v in params.items() if k != "status"}
    # `LIMIT`/`OFFSET` stehen in `params`, aber nicht in der Zaehlabfrage —
    # schadet nicht, wird nicht referenziert.
    status_zaehler_query = f"""
        SELECT m.status AS status, COUNT(*) AS anzahl
        FROM mitglied m
        WHERE 1=1
          AND {suche_glied}
          {sichtbarkeits_glied}
          AND {permission_filter_sql}
        GROUP BY m.status
    """
    status_zaehler: dict[str, int] = {}
    gesamt_alle = 0
    for zaehl_zeile in db.sql(status_zaehler_query, zaehl_params, as_dict=True) or []:
        schluessel = zaehl_zeile.get("status") or ""
        anzahl = int(zaehl_zeile.get("anzahl") or 0)
        status_zaehler[schluessel] = anzahl
        gesamt_alle += anzahl

    return {
        "success": True,
        "data": data,
        "total": total,
        "start": int(start),
        "limit": int(limit),
        "status_zaehler": status_zaehler,
        "gesamt_alle": gesamt_alle,
    }


# ── CSV-Export (P1-9b) ──────────────────────────────────────────────────────


#: Zellen, die mit einem dieser Zeichen beginnen, werden beim Export
#: entschaerft (CSV-/Formel-Einschleusung). `+` gehoert mit in die Liste:
#: Excel wertet ein fuehrendes `+` als Formelzeichen (OWASP: `= + - @ Tab CR`).
#: Tab und CR stehen bewusst mit in der Liste (Excel wertet sie wie ein
#: fuehrendes Zeichen).
_CSV_FORMELZEICHEN = ("=", "+", "-", "@", "\t", "\r")

#: Zeichen, deren fuehrendes `'` beim Import wieder entfernt wird — so bleibt
#: der Weg Export -> Import verlustfrei (B1, N11b). `'` ist in Tabellen das
#: uebliche Text-Kennzeichen (OWASP) und fuer Menschen nicht sichtbar.
_CSV_ENTSCHEARFUNG = ("'",)

#: Seitengroesse, in der `exportiere_mitglieder_csv` die Liste abblaettert.
#: Als Konstante, damit der Test der Zaehl-Logik (R-N11b K-b) sie verkleinern
#: kann — mit 3 Mitgliedern und Grenze 1 laeuft der Export echt ueber mehrere
#: Seiten und belegt, dass nur die ERSTE zaehlt.
EXPORT_SEITENGROESSE = 500


def _csv_zelle(wert, feld: str | None = None) -> str:
    """Einen CSV-Zellwert einschleusungssicher machen (Befund 2, P1-9b).

    Namen, Telefon und E-Mail stammen aus Selbstanmeldung bzw. CSV-Import.
    Beginnt ein Wert mit `=`, `+`, `-`, `@`, Tab oder CR, deutet Excel/Calc
    ihn als Formel; ein Mitglied koennte so beim Oeffnen der Exportdatei
    Befehle im Rechner der Verwaltung ausloesen. Ein vorangestelltes `'` macht
    daraus Text (das uebliche Vorgehen, z. B. OWASP).

    N11b (B1): Die Ausnahme fuer Telefon/Name nach Neu B ist entfallen. `+`
    ist in Excel ein vollwertiges Formelzeichen: `+HYPERLINK(...)` bzw.
    `+cmd|' /C calc'!A0` liefen ungefiltert durch, und selbst eine harmlose
    Nummer `+49 711 123456` wurde in Excel als (fehlerhafte) Formel gelesen —
    also weder sicher noch sichtbar unveraendert. Alle Textspalten werden
    deshalb vollstaendig entschaerft; das `'` entfernt der Import wieder
    (`_entschaerfung_loesen`).

    `feld` bleibt in der Signatur (Aufrufer uebergeben es), hat aber keinen
    Einfluss mehr auf das Ergebnis.
    """
    text = "" if wert is None else str(wert)
    # R-N11b K-a: auch " =1+1" / "\n=1+1" (Calc mit Leerzeichen-Trimmen).
    if text[:1] in _CSV_FORMELZEICHEN or text.lstrip()[:1] in _CSV_FORMELZEICHEN:
        return "'" + text
    return text


def _entschaerfung_loesen(wert: str | None) -> str:
    """Ein praeventives fuehrendes `'` vor einem Formelzeichen wieder loesen.

    Gegenstueck zu `_csv_zelle`: der CSV-Import legt ein fuehrendes `'` NICHT
    in die Daten, wenn es ein Formelzeichen entschaerft (`'+49 …` -> `+49 …`).
    Andernfalls wanderte das `'` bei jedem Export->Import-Roundtrip in die
    Daten (B1, N11b).

    R-N11b K-a: `_csv_zelle` entschaerft auch `" =1+1"` (Leerraum vor dem
    Formelzeichen, Calc mit „Leerzeichen entfernen“ wertet es sonst aus). Das
    Gegenstueck muss denselben Fall loesen, sonst bleibt das `'` im Wert.
    """
    text = "" if wert is None else str(wert)
    if text[:1] in _CSV_ENTSCHEARFUNG and text[1:2] in _CSV_FORMELZEICHEN:
        return text[1:]
    # Leerraum-Variante: `' =1+1` -> ` =1+1` (das `'` steht VOR dem Leerraum).
    if text[:1] in _CSV_ENTSCHEARFUNG:
        rest = text[1:]
        if rest[:1].isspace() and rest.lstrip()[:1] in _CSV_FORMELZEICHEN:
            return rest
    return text


@whitelist(allow_guest=False)
def exportiere_mitglieder_csv(suche="", status="", persoenliche_daten=False):
    """Alle sichtbaren Mitglieder als CSV (Befund 2, P1-9b).

    Der Export lag vorher im Browser und umfasste nur die geladenen Zeilen
    (Seitengroesse 30) — die Datei „mitglieder.csv“ sah aber nach der
    Gesamtliste aus. Hier wird serverseitig ueber denselben Filter wie
    `get_mitglieder_liste` gelaufen (Suche, Status, Sichtbarkeit), ohne
    Seitengrenze, und jede Zelle entschaerft.

    Nur fuer Administratoren: der Export enthaelt bewusst nur Name, Status
    und Gruppen — personenbezogene Spalten nur mit ``persoenliche_daten=True``
    (dieselbe fail-closed-Regel wie in der Liste).
    """
    user = session.user
    roles = permissions.get_roles(user)
    if not _has_admin_role(user, roles):
        throw("Nur Administratoren dürfen die Mitgliederliste exportieren.", PermissionError)

    alle = []
    start = 0
    gesamt_erwartet = None
    while True:
        seite = get_mitglieder_liste(
            start=start,
            limit=EXPORT_SEITENGROESSE,
            suche=suche,
            status=status,
            sort_by="name",
            sort_order="asc",
            persoenliche_daten=persoenliche_daten,
            # N11b/K2: Zaehlung/Zahlen nur auf der ersten Seite — die Folgeseiten
            # brauchen sie nicht, sparen aber je eine GROUP-BY-Abfrage.
            mit_zaehlung=(start == 0),
        )
        zeilen = seite.get("data") or []
        alle.extend(zeilen)
        if start == 0:
            gesamt_erwartet = seite.get("total")
        start += len(zeilen)
        if not zeilen or (gesamt_erwartet is not None and start >= int(gesamt_erwartet or 0)):
            break

    mit_personen = bool(persoenliche_daten) and str(persoenliche_daten).lower() not in (
        "0", "false", "", "none",
    )

    # Neu A (R-P1-9b-code): Die Datei wird mit dem csv-Modul geschrieben, nicht
    # mit `";".join`. Ein Wert mit Semikolon, Anfuehrungszeichen oder
    # Zeilenumbruch (Gruppenname, Adresse) verschob sonst Spalten bzw. brach
    # die Zeile — und die Datei war beim Wiedereinlesen unbrauchbar.
    # QUOTE_MINIMAL quotet genau diese Zellen; entschaerft wird VORHER, damit
    # das `'` innerhalb der Anfuehrungszeichen steht.
    kopf = [("Name", "full_name"), ("Status", "status"), ("Gruppen", "gruppen")]
    if mit_personen:
        kopf += [
            ("E-Mail", "email"),
            ("Telefon", "telefonnummer"),
            ("Straße", "strasse"),
            ("PLZ", "postleitzahl"),
            ("Ort", "wohnort"),
            ("Geburtstag", "geburtstag"),
        ]

    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", quotechar='"',
                           quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    schreiber.writerow([_csv_zelle(beschriftung) for beschriftung, _ in kopf])

    for m in alle:
        adresse = " ".join(
            x for x in [(m.get("straße") or ""), (m.get("nummer") or "")] if x
        ).strip()
        werte = []
        for _, feld in kopf:
            if feld == "gruppen":
                werte.append(_csv_zelle(", ".join(m.get("gruppen") or []), feld))
            elif feld == "strasse":
                werte.append(_csv_zelle(adresse, feld))
            elif feld == "full_name":
                # N11b (B1): Auch der Name wird voll entschaerft. Ein
                # fuehrendes `+` ist in Excel ein Formelzeichen
                # (`+HYPERLINK(...)`); Namen mit fuehrendem `+` sind praktisch
                # nicht existent, das Risiko wiegt schwerer als der Nutzen.
                werte.append(_csv_zelle(m.get("full_name") or "", "_full_name"))
            else:
                werte.append(_csv_zelle(m.get(feld) or "", feld))
        schreiber.writerow(werte)

    return {
        "success": True,
        "dateiname": "mitglieder.csv",
        "anzahl": len(alle),
        "csv": puffer.getvalue(),
    }


# ── Detail ──────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_mitglied_detail(mitglied_id):
    """
    Gibt vollstaendige Details eines Mitglieds zurueck.
    Inklusive Child-Tables: bereiche, beziehungen, gruppenmitgliedschaften.
    Prueft Permissions via session.get_permissions.mitglied_permissions().

    B2 — ABWEICHUNG vom Original, bewusst: das Original gibt `doc.as_dict()`
    unveraendert zurueck (mitglieder.py:200-234) und wertet
    `adressbuch_sichtbarkeit` nur in `get_adressbuch` aus. Damit zeigt dieser
    Endpunkt Telefon, Geburtstag, Anschrift, `notiz` und alle
    Einwilligungsfelder jedem Nutzer mit `can_view`. Das ist eine Luecke des
    Originals, kein Vertrag — die Einstellung existiert, wird im Profil
    angeboten und hier ignoriert. Nach "im Zweifel verweigern" wird sie hier
    durchgesetzt; die Begruendung steht vollstaendig in
    `frappe_compat/mitglied_sichtbarkeit.py`.

    Wer alles sieht: Admin (`can_view_sensitive`) und das eigene Mitglied.
    `perms` kommt unveraendert in die Antwort — die SPA haengt daran
    (`MitgliedDetail.vue`), und dort aendert sich nichts.
    """
    perms = permissions.mitglied_permissions(mitglied_id)
    eigenes = ist_eigenes_mitglied(mitglied_id)
    if not perms.get("can_view") and not eigenes:
        throw("Kein Zugriff", PermissionError)
    if eigenes:
        perms = {**perms, "can_view": True}

    doc = get_doc("Mitglied", mitglied_id)
    result = doc.as_dict()

    # Verwaltungsdaten nur fuer Admin und das eindeutig eigene Mitglied.
    vollstaendig = bool(perms.get("can_view_sensitive")) or eigenes
    result = maskiere_datensatz(result, mitglied_id=mitglied_id,
                               vollstaendig=vollstaendig) or {}

    # AUSTRITT A3: Nach dem Austritt steht hier NUR noch die Kurzform — fuer
    # alle ausser der Person selbst und den Administratoren. Die Kuerzung
    # laeuft NACH der Adressbuch-Maskierung, weil sie die Adresse als
    # maskierte Form („elv*******.de“) liefern soll und nicht als `None`;
    # der Klarname steht im Antwortkoerper zu keinem Zeitpunkt mehr.
    #
    # AUSTRITT-b (N2): Die Maske kommt aus der UNGEKUERZTEN Adresse. Vorher
    # stand im Detail `email=None` (die Adressbuch-Maskierung hatte das Feld
    # schon geleert), waehrend die Liste „elv*******.de“ zeigte — zwei
    # Antworten auf dieselbe Frage.
    from diakronos_app.frappe_compat.personen_anzeige import (
        PersonenSicht, ist_ausgeschieden, ist_geloescht, kuerze, maskiere_email,
    )

    sicht = PersonenSicht.aus()
    # AUSTRITT-e (NR1): Die KUERZUNG entscheidet das Austrittsmerkmal, nicht
    # die Marke `ausgeschlossen`. Ein Ausschluss laesst die Person voll
    # sichtbar (Fachentscheidung) — die Marke traegt beide Faelle.
    #
    # DSGVO-2d: Eine GELOESCHTE Person wird IMMER gekuerzt — auch fuer einen
    # Administrator. Der Endstatus ist endgueltig; ein „vollstaendiger“ Blick
    # auf die Zeile gibt es nicht mehr.
    geloescht = ist_geloescht(result)
    if geloescht or (ist_ausgeschieden(result) and not sicht.darf_vollstaendig(mitglied_id)):
        rohe_adresse = str(doc.get("email") or "") or None
        # `email_feld="__keins__"` haelt die Maske aus `kuerze` heraus: das
        # Feld `email` wird DANACH gesetzt (aus der rohen Adresse), und ein
        # fehlendes Feld liest `kuerze` nicht nach. Fuer eine geloeschte
        # Person bleibt es leer — es gibt keine Adresse mehr.
        result = kuerze(result, email_feld="__keins__")
        result["email"] = None if geloescht else maskiere_email(rohe_adresse)

    # Der `dsgvo`-Block traegt dieselben Einwilligungsinformationen wie die
    # Einzelfelder. Er darf fuer Fremde **nicht** aus dem `notiz`-/`Foto`-/
    # `Werbung`-Wissen gespeist werden — sonst waere die Maskierung oben
    # nur halb wirksam (gleiche Daten, zweiter Weg). Die Struktur bleibt
    # erhalten, damit `MitgliedDetail.vue` (`if (payload.dsgvo)`) nicht
    # crasht: alle nicht autorisierten Werte sind None (unbekannt), nie
    # eine erfundene Aussage "nicht erteilt". Berechtigte Leser unveraendert.
    if not vollstaendig:
        result["dsgvo"] = {
            "datenschutz": None,
            "datenschutz_datum": None,
            "foto": None,
            "foto_datum": None,
            "werbung": None,
            "werbung_datum": None,
        }
    else:
        result["dsgvo"] = {
            "datenschutz": bool(doc.datenschutz_einwilligung),
            "datenschutz_datum": str(doc.datenschutz_datum) if doc.datenschutz_datum else None,
            "foto": bool(doc.get("foto_einwilligung")),
            "foto_datum": str(doc.get("foto_datum")) if doc.get("foto_datum") else None,
            "werbung": bool(doc.get("werbeeinwilligung")),
            "werbung_datum": str(doc.get("werbung_datum")) if doc.get("werbung_datum") else None,
        }

    # Gruppenmitgliedschaften explizit anreichern (falls nicht in as_dict)
    gruppenmitgliedschaften = get_all(
        "Gruppenmitgliedschaft",
        filters={"mitglied": mitglied_id},
        fields=["name", "parent as gruppe", "rolle", "beitrittsdatum", "status"],
    )
    for g in gruppenmitgliedschaften:
        g["gruppenname"] = get_value("Gruppe", g.get("gruppe"), "gruppenname")
    # AUSTRITT A3: `gruppenname` ist kein Personenname; die Zeilen bleiben.
    result["gruppenmitgliedschaften"] = gruppenmitgliedschaften

    # AUSTRITT A3/A4: Fuer Administratoren der Hinweis „ausgetreten seit …“,
    # fuer alle anderen nur die Auskunft, DASS jemand ausgetreten ist (sie
    # sehen ohnehin nur die Kurzform). Das Feld ist zusaetzlich zu
    # `ausgeschlossen` da, damit die Oberflaeche „Ausschluss“ und „Austritt“
    # unterscheiden kann, ohne den Grund zu zeigen.
    #
    # AUSTRITT-d (NB3): Die ART kommt ausdruecklich vom Server. Vorher leitete
    # die Oberflaeche sie aus der (seit N1 optionalen) Begruendung ab — ein
    # Austritt ohne Begruendung erschien damit als „Ausschluss“.
    #
    # Die ART trennt die Faelle; aus ihr baut die Oberflaeche ihre Knoepfe und
    # Hinweise. Quelle sind die Merkmale des AKTUELL GELESENEN Datensatzes:
    # der Austritt setzt IMMER ``austritt_datum``, der Ausschluss nicht.
    # ``ausgeschlossen_seit`` taugt dafuer NICHT — der Austritt schreibt es aus
    # Kompatibilitaet mit. Ein Altbestand mit Status „Ausgetreten“ OHNE Marke
    # (NN3) ist ebenfalls Austritt („Reaktivieren“ wird dort angeboten).
    #
    # `ausgetreten` bleibt die Marke — daran haengen bestehende Aufrufer.
    if doc.get("ausgeschlossen"):
        art = "austritt" if doc.get("austritt_datum") else "ausschluss"
    elif str(doc.get("status") or "").strip().casefold() == _STATUS_AUSGETRETEN.casefold():
        # Altbestand „Ausgetreten“ ohne Marke (NN3): Die Oberflaeche muss
        # „Reaktivieren“ anbieten. Der Status steht am Doc (nicht in
        # `result`) — die Kuerzung hat ihn fuer Nicht-Admins nicht entfernt.
        art = "austritt"
    else:
        art = ""
    result["austritt"] = {
        "art": art,
        "ausgetreten": bool(doc.get("ausgeschlossen")),
        "seit": (
            str(doc.get("austritt_datum") or doc.get("ausgeschlossen_seit"))
            if doc.get("ausgeschlossen") else None
        ),
        "grund": str(doc.get("austritt_grund") or "") if vollstaendig else None,
        "vorheriger_status": (
            str(doc.get("vor_austritt_status") or "") if vollstaendig else None
        ),
    }

    # Beziehungen anreichern: beziehung_zu -> Name aufloesen
    # Original: frappe.db.get_value("Mitglied", <id>, "CONCAT_WS(' ', ...)").
    # Die Compat-Schicht kann keine SQL-Ausdruecke als Feldnamen auswerten
    # (Feldnamen-Whitelist), daher derselbe Ausdruck als Helfer.
    for b in result.get("beziehungen") or []:
        if b.get("beziehung_zu"):
            b["beziehung_zu_name"] = _full_name(b["beziehung_zu"]) or b["beziehung_zu"]
    # AUSTRITT A3: Ein Beziehungs-Name ist ein ANZEIGENAME einer anderen
    # Person. Ist die Zielperson ausgetreten, steht hier sonst ihr Klarname —
    # dieselbe Kuerzung wie ueberall (`personen_anzeige`).
    if result.get("beziehungen"):
        result["beziehungen"] = _beziehungen_kuerzen(result["beziehungen"], sicht)

    return {
        "success": True,
        "data": result,
        "permissions": perms,
    }


# ── Helpers (Quelle: mitglieder.py:514-534) ─────────────────────────────────


def _beziehungen_kuerzen(zeilen: list[dict], sicht) -> list[dict]:
    """Anzeigenamen ausgetretener Beziehungspartner kuerzen (AUSTRITT A3).

    `beziehung_zu_name` ist der KLARNAME einer anderen Person. Ohne diese
    Stelle waere die Kuerzung ueber die Detailseite zu umgehen: die eigene
    Zeile ist vollstaendig, die Beziehung daneben nennt den Klarnamen einer
    ausgetretenen Person. Eine Abfrage fuer alle Ziele zusammen.

    AUSTRITT-b (M3): Der Kurzname entsteht aus den Daten der ZIELPERSON. Die
    Beziehungszeile traegt weder Vor- noch Nachnamen; vorher kam deshalb nur
    „E." heraus (Initiale der Kennung).
    """
    from diakronos_app.frappe_compat.personen_anzeige import anzeigename

    ziele = [str(z.get("beziehung_zu")) for z in zeilen if z.get("beziehung_zu")]
    if not ziele:
        return zeilen
    daten = get_all(
        "Mitglied",
        filters={"name": ["in", ziele]},
        fields=["name", "vorname", "nachname", "ausgeschlossen", "status",
                "austritt_datum"],
    )
    ziel_daten = {
        str(z.get("name")): z for z in (daten or [])
        if isinstance(z, dict) and z.get("name")
    }
    from diakronos_app.frappe_compat.personen_anzeige import ist_ausgeschieden

    for zeile in zeilen:
        ziel = str(zeile.get("beziehung_zu") or "")
        person = ziel_daten.get(ziel)
        if person and ist_ausgeschieden(person) and not sicht.darf_vollstaendig(ziel):
            zeile["beziehung_zu_name"] = anzeigename(person, sicht=sicht)
    return zeilen


def _user_email() -> str:
    """E-Mail des aktuellen Benutzers, sonst der Benutzername selbst.

    Entspricht `frappe.db.get_value("User", user, "email") or user`.

    Der DocType `User` ist modelliert (`models/core.py`, Quelle
    `inventar/live_schema_ist.tsv`), die Abfrage geht also gegen die echte
    Tabelle. Fehlt der Benutzer oder hat er keine E-Mail, liefert `get_value`
    `None`/`""` und der Fallback greift — das ist 1:1 der `or user`-Zweig des
    Originals (mitglieder.py:63, 68, 519, 561, 564) und damit fail closed:
    findet der E-Mail-Match kein Mitglied, bleibt die Liste leer.
    """
    user = session.user
    try:
        email = get_value("User", user, "email")
    except DoesNotExistError:
        # Kein Benutzer-Datensatz (z.B. "Administrator" hat keine Zeile in
        # `tabUser`, solange kein Login angelegt wurde) -> Fallback wie oben.
        email = None
    return email or user


def _get_current_user_mitglied():
    """Holt den Mitglied-Datensatz des aktuellen Users.

    Quelle: `mitglieder.py:516-524` — **identisch** zu
    `permissions._get_current_user_mitglied()` (`session.py:184-192`,
    dieselbe Funktion noch einmal in `gruppen.py:365-373`), deshalb wird sie
    von dort benutzt statt hier ein zweites Mal gebaut.
    """
    return permissions._get_current_user_mitglied()


def _extract_path_segments(path):
    """Extrahiert alle Gruppen- und Bereichs-Segmente aus einem ancestor_path.

    Quelle: `mitglieder.py:527-534`. Es gibt bereits eine Fassung dieser
    Zerlegung in `frappe_compat.permissions` (`_extract_segments`,
    `session.py:235-240`) — dieselbe Regel fuer dieselben Pfade. Wir liefern
    hier nur die Listenform zurueck, die das Original an dieser Stelle hat
    (`_paths_overlap` braucht Mengen, der Sichtbarkeitsfilter eine Liste).
    """
    gruppen, bereiche = permissions._extract_segments(path)
    return list(gruppen) + list(bereiche)


def _full_name(mitglied_id: str) -> str | None:
    """`CONCAT_WS(' ', NULLIF(vorname,''), NULLIF(nachname,''))` als Helfer."""
    row = get_value("Mitglied", mitglied_id, ["vorname", "nachname"], as_dict=True)
    if not row:
        return None
    parts = [row.get("vorname") or "", row.get("nachname") or ""]
    return " ".join(p for p in parts if p) or None

# ── Audit-/DSGVO-Helfer (Quelle: mitglieder.py + dsgvo_log.py) ──────────────

# `log_einwilligung` lebt in `api/dsgvo_log.py` (P4n) — dort ist die EINE
# Fassung fuer das ganze Projekt. Diese Datei hatte eine private Kopie, die
# an `frappe.local.request` las; dieser Namespace existiert im
# Standalone-Backend nicht, deshalb bekam jeder Eintrag hier eine LEERE IP
# und einen leeren User-Agent. Die gemeinsame Fassung liest stattdessen den
# echten Request-Kontext (`request_context`). Das Verhalten ist damit an
# dieser Stelle VERBESSERT, nicht veraendert — die Pflicht, bei jeder
# Aenderung an den sechs Einwilligungsfeldern einen Eintrag zu schreiben,
# bleibt 1:1 (AGENTS.md Abschnitt 3/4).


def _log_profil_aenderung(mitglied_id, changed_fields):
    """Audit-Log-Eintrag fuer Admin-Aenderungen an Mitglied-Stammdaten.

    1:1 nach `mitglieder.py:_log_profil_aenderung` — schreibt `Audit Log` mit
    action_typ "Profiländerung", alt/neu als JSON. Setzt die Flag
    `audit_policy_logged` waehrend des Schreibens (die Vorlage liest sie in
    ihrer Policy-Dekorator-Schicht; im Standalone bleibt sie als Halter).
    """
    _AUDIT_STATE.audit_policy_logged = True
    try:
        _create(
            "Audit Log",
            {
                "zeitstempel": _now(),
                "action_typ": "Profiländerung",
                "actor": session.user,
                "target_doctype": "Mitglied",
                "target_name": mitglied_id,
                "field_changed": ", ".join(changed_fields.keys()),
                "old_value": json.dumps(
                    {k: v["alt"] for k, v in changed_fields.items()}, ensure_ascii=False
                ),
                "new_value": json.dumps(
                    {k: v["neu"] for k, v in changed_fields.items()}, ensure_ascii=False
                ),
                "notification_gesendet": 0,
            },
        )
    except Exception:  # noqa: BLE001
        log_error("Mitglied Aenderungs-Log Fehler", "log_profil_aenderung")
    finally:
        _AUDIT_STATE.audit_policy_logged = False


# ── Adressbuch ──────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_adressbuch(suche=""):
    """Adressbuch der Gemeinde (Quelle: mitglieder.py:552-599).

    WICHTIG zur Sichtbarkeit: `adressbuch_sichtbarkeit` ist KEIN Boolean,
    sondern ein **JSON-Blob** pro Mitglied mit Schluesseln
    `email`, `telefonnummer`, `adresse`, `geburtstag` (Default: email/telefon
    sichtbar, adresse/geburtstag NICHT). Jedes Feld wird einzeln maskiert —
    ein Mitglied kann damit z.B. nur die E-Mail freigeben.

    Zusaetzlich: Admins sehen alle Mitglieder; Nicht-Admins nur die ueber
    `ancestor_path` ueberlappenden (Gruppen/Bereiche), sonst das eigene Profil
    per E-Mail-Match. Dieselbe fail-closed-Staffelung wie im Original.
    """
    is_admin = _is_admin()

    params = {"suche": f"%{_suche_normalisieren(suche)}%" if suche else "%%"}
    where = "1=1"
    if not is_admin:
        # Dieselbe Staffelung wie `get_mitglieder_liste`: eigenes Mitglied mit
        # ancestor_path -> OR-LIKE ueber die Segmente, sonst E-Mail-Fallback.
        # Die Zerlegung kommt aus `permissions._extract_segments` (eine Wahrheit).
        current = _get_current_user_mitglied()
        if not current:
            where = "1=0"
        elif current.get("ancestor_path"):
            segs = _extract_path_segments(current["ancestor_path"])
            if segs:
                clauses = []
                for i, seg in enumerate(segs):
                    k = f"seg_{i}"
                    clauses.append(
                        "CONCAT('/', COALESCE(m.ancestor_path, ''), '/') LIKE %(" + k + ")s"
                    )
                    params[k] = f"%/{seg}/%"
                where = "(" + " OR ".join(clauses) + ")"
            else:
                where = "m.email = %(ue)s"
                params["ue"] = _user_email()
        else:
            where = "m.email = %(ue)s"
            params["ue"] = _user_email()

    eigenes_name = eigenes_mitglied_id()
    if not is_admin and eigenes_name:
        params["own_mid"] = eigenes_name
        where = f"({where} OR m.name = %(own_mid)s)"

    # B2: Das E-Mail-Glied der Suche ist ein Adressbuch-Feld (siehe
    # `get_mitglieder_liste`). Fuer Nicht-Admins wird es gestrichen, damit
    # "ich kenne B's E-Mail und frage nach" nichts ueber Bs Einstellung
    # verraten kann. In dem Zweig ohne `ancestor_path` ist die E-Mail-Suche
    # durch das `AND m.email = <eigenes>` ohnehin wirkungslos; dort aendert
    # sich also nichts.
    durchsucht_email = is_admin
    # BF1-J: Gross-/Kleinschreibung und Umlautschreibweise egal (siehe Liste).
    suche_where = (
        f"({_suche_ausdruck('m.vorname')} LIKE %(suche)s "
        f"OR {_suche_ausdruck('m.nachname')} LIKE %(suche)s "
        f"OR {_suche_ausdruck('m.email')} LIKE %(suche)s)"
        if durchsucht_email
        else f"({_suche_ausdruck('m.vorname')} LIKE %(suche)s "
        f"OR {_suche_ausdruck('m.nachname')} LIKE %(suche)s)"
    )

    rows = db.sql(
        """
        SELECT m.name, m.vorname, m.nachname, m.email, m.telefonnummer,
               m.postleitzahl, m.wohnort, m."straße", m.nummer,
               m.geburtstag, m.foto, m.adressbuch_sichtbarkeit,
               m.status, m.austritt_datum
        FROM mitglied m
        WHERE """
        + suche_where
        + """
          AND """
        + where
        + """
        ORDER BY m.nachname, m.vorname
        LIMIT 200
        """,
        params,
        as_dict=True,
    )

    # B2: Die zentrale Regel ist fail-closed; get_adressbuch bleibt fuer
    # Admins ebenfalls eine Freigabe-Ansicht wie im Frappe-Original.
    #
    # ID-1: Das Adressbuch war der EINE Auslieferungsweg, der den Klarnamen
    # einer AUSGETRETENEN Person ungekürzt ausgab — `maskiere_datensatz`
    # regelt nur die Felder FREIGABE (Mail, Telefon, Adresse, Geburtstag),
    # nicht den Namen. Seit ID-1 tragen die Kennungen keine Namen mehr; die
    # Kürzung hier schließt dieselbe Lücke für `vorname`/`nachname` — über
    # dieselbe Regel wie Liste, Detail und Kalender (`personen_anzeige`).
    # DSGVO-2d: Eine geloeschte Person steht auch im Adressbuch nur als
    # „Gelöschte Person“ — Name, Kennung und Foto kommen aus der einen Regel
    # (`personen_anzeige`), nicht aus einer zweiten Fassung hier. Sie bleibt in
    # der Liste, weil die Zeile sonst still verschwaende (die Gemeindeliste
    # zaehlt die Menschen, nicht nur die aktiven).
    from diakronos_app.frappe_compat.personen_anzeige import (
        GELOESCHT_ANZEIGE, PersonenSicht, ist_geloescht, kuerze_zeilen,
    )

    result = []
    for row in rows:
        m: dict = dict(row)
        # `straße`/`nummer` fragt der Altcode ab, gibt sie aber nie aus; das
        # bleibt so. `adressbuch_sichtbarkeit` wird gebraucht (Maskierung),
        # aber nicht ausgegeben — wie im Original.
        maskiert = maskiere_datensatz(
            m,
            mitglied_id=m.get("name"),
            vollstaendig=bool(m.get("name")) and str(m.get("name")) == eigenes_name,
        ) or {}

        geloescht = ist_geloescht(m)
        geburtstag = maskiert.get("geburtstag")
        result.append({
            "name": maskiert.get("name"),
            "vorname": GELOESCHT_ANZEIGE if geloescht else (maskiert.get("vorname") or ""),
            "nachname": "" if geloescht else (maskiert.get("nachname") or ""),
            # Kein Bild einer geloeschten Person: `dsgvo_anonymisierung`
            # entfernt die Datei, ein Rest im Feld waere ein toter Verweis.
            "foto": "" if geloescht else (maskiert.get("foto") or ""),
            "email": maskiert.get("email"),
            "telefonnummer": maskiert.get("telefonnummer"),
            "postleitzahl": maskiert.get("postleitzahl"),
            "wohnort": maskiert.get("wohnort"),
            # Altcast `str(geburtstag)` bleibt: das Feld kommt als `date` aus
            # der DB und waere sonst nicht JSON-faehig. `None` bleibt `None`
            # (nie "None" als String) — das Original tut dasselbe.
            "geburtstag": str(geburtstag) if geburtstag else None,
            # ID-1: die Zeile braucht Status/Marke, damit `kuerze_zeilen`
            # den Austritt erkennt (die Rohspalten werden nicht ausgegeben).
            "status": m.get("status"),
            "austritt_datum": m.get("austritt_datum"),
        })
    result = kuerze_zeilen(result, PersonenSicht.aus())
    for zeile in result:
        # DSGVO-2d-Vertrag: eine geloeschte Person hat leeren Nachnamen/Foto
        # (nicht None) — auch nachdem `kuerze_zeilen` sie behandelt hat.
        # G1 (ID-1f): dasselbe fuer AUSGETRETENE. `kuerze` setzt `nachname` und
        # `foto` auf None; das Frontend baut daraus ein aria-label
        # („Anrufen: Elvira null“) und eine sichtbare Zeile. Beides wird ""
        # — die Normalisierung, die `get_mitglieder_liste` schon hat.
        if ist_geloescht(zeile):
            zeile["vorname"] = GELOESCHT_ANZEIGE
            zeile["nachname"] = ""
            zeile["foto"] = ""
        else:
            zeile["nachname"] = zeile.get("nachname") or ""
            zeile["foto"] = zeile.get("foto") or ""
        zeile.pop("status", None)
        zeile.pop("austritt_datum", None)
    return {"data": result}


# ── Erstellen ───────────────────────────────────────────────────────────────

# UXD-R8: Spaltenbreiten im Bestand (`varchar(140)`) — Laengenpruefung mit
# Klartextmeldung statt roher DB-Fehler (StringDataRightTruncation).
MAX_TEXTLAENGE = 140
# UXD-R24: einfache Formatpruefung; leer bleibt erlaubt (E-Mail ist optional).
EMAIL_MUSTER = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Namen der Textfelder, die die 140-Zeichen-Grenze teilen.
_TEXT_FELDER = (
    "vorname", "nachname", "email", "telefonnummer", "postleitzahl",
    "wohnort", "straße", "nummer",
)


def _pruefe_textlaengen(werte: dict) -> None:
    """Uebersetzt zu lange Eingaben in eine verstaendliche Meldung (UXD-R8)."""
    for feld in _TEXT_FELDER:
        if feld not in werte:
            continue
        wert = werte[feld]
        if isinstance(wert, str) and len(wert.strip()) > MAX_TEXTLAENGE:
            throw(
                f"Die Eingabe ist zu lang (höchstens {MAX_TEXTLAENGE} Zeichen).",
                ValidationError,
            )


def _email_vergeben_meldung(treffer) -> str:
    """Klartext, WEM die E-Mail-Adresse schon gehoert (Fachentscheidung 19.10.).

    Jede Person braucht eine eigene Adresse — wer eine zweite Person mit
    derselben Adresse anlegt, muss erfahren, bei wem sie liegt, statt nur
    „bereits vergeben“ zu lesen.
    """
    if not treffer:
        return "Diese E-Mail-Adresse ist bereits vergeben."
    if treffer.get("doctype") == "Mitglied":
        anzeige = _anzeigename_mitglied(str(treffer["name"]))
    else:
        anzeige = str(treffer.get("full_name") or treffer.get("name") or "").strip()
    if not anzeige:
        return "Diese E-Mail-Adresse ist bereits vergeben."
    return f"Diese E-Mail-Adresse gehört bereits zu {anzeige}."


def _anzeigename_mitglied(mitglied_id: str) -> str:
    """„Vorname Nachname“ eines Mitglieds (leer, wenn nicht lesbar)."""
    try:
        doc = get_doc("Mitglied", mitglied_id)
        name = f"{doc.get('vorname') or ''} {doc.get('nachname') or ''}".strip()
    except Exception as exc:  # noqa: BLE001 — die Meldung darf nie am Zusatz scheitern
        log_error(f"Anzeigename nicht lesbar: {exc}", "email_vergeben_meldung")
        return ""
    return name


def _pruefe_email(email: str | None) -> None:
    """E-Mail-Format pruefen, sofern eine Angabe gemacht wurde (UXD-R24).

    K2 (R-SEC-AUSSCHLUSS-code): Zusaetzlich werden unsichtbare Zeichen
    abgewiesen. `strip()` entfernt kein Nullbreiten-Leerzeichen — „max@x.org“
    und „max@x.org​“ sahen damit wie zwei verschiedene Adressen aus, obwohl
    sie keine sind. Und die Normalisierung laeuft VOR der Pruefung: eine
    Vollbreite-Adresse (ｆｕｌｌｗｉｄｔｈ) wird erst dadurch zu der Adresse,
    die sie darstellt.
    """
    from diakronos_app.email_belegung import enthaelt_unsichtbare, normalisiere

    if not email:
        return
    text = str(email)
    if enthaelt_unsichtbare(text):
        throw(
            "Die E-Mail-Adresse enthält unsichtbare Zeichen. Bitte die "
            "Adresse neu eintippen.",
            ValidationError,
        )
    if not EMAIL_MUSTER.match(normalisiere(text)):
        throw("Bitte eine gültige E-Mail-Adresse angeben.", ValidationError)


def _normalisiere_datumsfelder(werte: dict) -> None:
    """Leere Datumsangaben zu `None` wandeln (UXD-R6).

    Die SPA sendet `geburtstag: ''`, wenn das (optionale) Feld leer ist. Ein
    leerer String ist fuer `date` ungueltig (InvalidDatetimeFormat) und liess
    Mitglieder ohne Geburtstag weder speichern noch leeren. Dieselbe Regel wie
    `profile.update_my_profile` (`geburtstag or None`).
    """
    for feld in ("geburtstag",):
        if feld in werte and (werte[feld] is None or str(werte[feld]).strip() == ""):
            werte[feld] = None


def _dubletten_hinweis(vorhanden_id: str, grund: str) -> dict:
    """Einen gefundenen Doppelgaenger als verstaendlichen Hinweis aufbereiten.

    N4: Der Dialog „Mitglied hinzufügen“ fragt beim Tippen nach, ob dieselbe
    Person schon existiert. Der Hinweis nennt Name, Status und Gruppen der
    vorhandenen Person, damit der Planer selbst entscheiden kann (öffnen oder
    trotzdem anlegen). Keine sensiblen Felder — nur, was die Liste ohnehin
    zeigt.
    """
    doc = get_doc("Mitglied", vorhanden_id)
    vorname = doc.get("vorname") or ""
    nachname = doc.get("nachname") or ""
    gruppen: list[str] = []
    try:
        treffer = get_all(
            "Gruppenmitgliedschaft",
            filters={"mitglied": vorhanden_id},
            fields=["parent as gruppe"],
        )
        gruppen = [
            str(get_value("Gruppe", g.get("gruppe"), "gruppenname") or g.get("gruppe"))
            for g in (treffer or [])
            if g.get("gruppe")
        ]
    except Exception as exc:  # noqa: BLE001 — Hinweis darf nie am Zusatz scheitern
        log_error(f"Gruppen zum Dublettenhinweis nicht lesbar: {exc}", "pruefe_mitglied_dublette")
    return {
        "grund": grund,
        "mitglied_id": vorhanden_id,
        "name": f"{vorname} {nachname}".strip(),
        "status": doc.get("status") or "",
        "gruppen": gruppen,
    }


@whitelist(allow_guest=False)
def pruefe_mitglied_dublette(vorname="", nachname="", email=""):
    """Prueft beim Tippen, ob es die Person schon gibt (N4, UXD-R15).

    Rueckgabe ``{"dublette": None}`` oder ``{"dublette": {...}}`` mit
    ``grund`` (``email`` | ``name``), ``mitglied_id`` und den Anzeigefeldern.
    Gleiche E-Mail blockiert spaeter das Speichern; gleicher Name warnt nur.
    Nur ein Hinweis fuer die Oberflaeche — die verbindliche Pruefung macht
    weiterhin ``create_mitglied`` (der Server prueft, die UI blendet nur aus).
    """
    if not _is_admin():
        throw("Nur Administratoren dürfen Mitglieder anlegen.", PermissionError)

    vorname = (vorname or "").strip()
    nachname = (nachname or "").strip()
    # Dieselbe Normalisierung wie beim Anlegen (OP-ADMIN-7): ohne sie blieb
    # eine bereits vergebene E-Mail in anderer Schreibweise unentdeckt.
    email = (email or "").strip().lower()

    if email:
        from diakronos_app.email_belegung import belegung

        treffer = belegung(email)
        if treffer:
            if treffer["doctype"] == "Mitglied":
                return {"dublette": _dubletten_hinweis(treffer["name"], "email")}
            return {"dublette": {"grund": "email", "mitglied_id": None,
                                  "name": treffer["full_name"], "gruppen": [],
                                  "status": "Benutzerkonto"}}

    if vorname and nachname:
        treffer = get_all(
            "Mitglied",
            filters={"vorname": vorname, "nachname": nachname},
            pluck="name",
            limit_page_length=1,
        )
        if treffer:
            return {"dublette": _dubletten_hinweis(str(treffer[0]), "name")}

    return {"dublette": None}


@whitelist(allow_guest=False)
def create_mitglied(vorname, nachname, email="", status="Gast", gruppe_id=None, create_user=False, zugangsart="kein", startpasswort="", request=None):
    """Legt eine Person und optional einen lokalen Zugang an.

    N5: „link“ erzeugt einen einmaligen Passwort-Link, „startpasswort“
    erzwingt den Erstwechsel. „kein“ bleibt der Standard für alte Aufrufer.
    Kontofehler werden als Warnung gemeldet, die Person bleibt erhalten.
    """
    if not _is_admin():
        throw("Nur Administratoren dürfen Mitglieder anlegen.", PermissionError)

    vorname = (vorname or "").strip()
    nachname = (nachname or "").strip()
    email = (email or "").strip().lower()

    if not vorname or not nachname:
        throw("Vor- und Nachname sind Pflichtfelder.", ValidationError)

    # UXD-R8: Laengen vor dem DB-Schreiben pruefen (Klartext statt SQL-Text).
    _pruefe_textlaengen({"vorname": vorname, "nachname": nachname, "email": email})
    # UXD-R24: E-Mail-Format vorab pruefen.
    _pruefe_email(email)

    if zugangsart != "kein" or _cint(create_user):
        from diakronos_app.api.zugang import _nur_post
        _nur_post(request)
    if zugangsart not in ("kein", "link", "startpasswort"):
        throw("Bitte eine gültige Zugangsart wählen.", ValidationError)
    if zugangsart != "kein":
        from diakronos_app.anmeldung.konfiguration import oidc_aktiv
        from diakronos_app.anmeldung.passwortzugang import pruefe_passwort
        if oidc_aktiv():
            throw("Bei Authentik bitte nur einen Eintrag anlegen.", ValidationError)
        if zugangsart == "startpasswort":
            pruefe_passwort(startpasswort)
    if (_cint(create_user) or zugangsart != "kein") and not email:
        throw(
            "Eine E-Mail-Adresse wird benötigt um einen Login-Account anzulegen.",
            ValidationError,
        )

    # UXD-R15/OP-ADMIN-7: Dubletten frueh erkennen — dieselbe E-Mail darf nur
    # einmal vergeben sein (verhindert doppelte Personen mit unklarer Zuordnung).
    # Fachentscheidung 19.10.: jede Person hat eine eigene Adresse; die
    # Meldung nennt, WEM die Adresse schon gehoert.
    if email:
        from diakronos_app.email_belegung import belegung

        bestand = belegung(email)
        if bestand:
            throw(_email_vergeben_meldung(bestand), ValidationError)

    valid_statuses = {"Mitglied", "Gast", "Passiver Gast", "Passives Mitglied"}
    if status not in valid_statuses:
        status = "Gast"

    try:
        name = _create(
            "Mitglied",
            {
                "vorname": vorname,
                "nachname": nachname,
                "email": email or None,
                "status": status,
            },
        )
    except Exception as exc:  # noqa: BLE001
        _rethrow(exc, "create_mitglied")
        raise  # pragma: no cover

    warnungen: list[str] = []
    if gruppe_id:
        try:
            from diakronos_app.api.gruppen import add_mitglied_to_gruppe

            add_mitglied_to_gruppe(
                gruppe_id=gruppe_id, mitglied_id=name, rolle="Mitglied", is_untergruppe=False
            )
        except Exception as e:  # noqa: BLE001
            # BLD-R4: die Zuweisung darf das angelegte Mitglied nicht verwerfen,
            # aber sie darf auch nicht still verschwinden. Vorher entstand bei
            # ungueltiger ID eine verwaiste Gruppenmitgliedschaft; jetzt wird
            # sie abgelehnt UND als Warnung in der Antwort gemeldet.
            log_error(f"Gruppe-Zuweisung fehlgeschlagen: {e}", "create_mitglied")
            warnungen.append(f"Gruppe konnte nicht zugewiesen werden: {e}")

    zugang = None
    if (_cint(create_user) or zugangsart != "kein") and email:
        # P1-8 (OP-ADMIN-2): Frueher stand hier ein Import auf `api/nutzer`,
        # den es nie gab — der ImportError wurde wegloggt und die Antwort
        # meldete trotzdem `success`. Damit sah die Oberflaeche ein angelegtes
        # Konto, das es nicht gab. Jetzt wird das Konto ueber den EINEN Weg
        # angelegt (`api/zugang.py::konto_anlegen`) und ein echtes Scheitern
        # landet als Warnung in der Antwort (wie die Gruppe oben), nie still.
        try:
            from diakronos_app.api.zugang import konto_anlegen

            konto_anlegen(name)
            if zugangsart == "link":
                from diakronos_app.api.zugang import einladungslink
                zugang = einladungslink(name)
            elif zugangsart == "startpasswort":
                from diakronos_app.api.zugang import setze_passwort
                zugang = setze_passwort(name, startpasswort)
        except Exception as e:  # noqa: BLE001
            log_error(f"Konto-Anlage fehlgeschlagen: {e}", "create_mitglied")
            warnungen.append(f"Benutzerkonto konnte nicht angelegt werden: {e}")

    return {
        "success": True,
        "mitglied_id": name,
        "mitglied_name": f"{vorname} {nachname}",
        "zugang": zugang,
        "warnungen": warnungen,
    }


# ── Update ──────────────────────────────────────────────────────────────────


def _validate_email_update(doc, werte):
    """Die E-Mail bindet Berechtigungen: nur Admin, keine fremde Belegung.

    Unveraendert mitgesendete Werte (SPA-Vollformular) bleiben erlaubt.
    Beide Update-Endpunkte benutzen diese Pruefung vor jedem Schreibzugriff.
    """
    if "email" not in werte or _email_belegung_gleich(werte["email"], doc.get("email")):
        return
    email = werte["email"]
    _pruefe_email(email)
    # SEC (Befund W2): getrimmt + kleingeschrieben vergleichen.
    # Ein exakter Vergleich liess „gross@x.org“ am Bestand „Gross@X.org“
    # vorbei — danach stand die Adresse zweimal da, war fuer
    # `wirksame_konten` mehrdeutig und ein Ausschluss ueber die E-Mail wirkte
    # nicht mehr. `ohne_mitglied` laesst den eigenen Datensatz aus.
    if email:
        treffer = _email_belegung(email, ohne_mitglied=doc.name)
        if treffer:
            # Fachentscheidung 19.10.: eine Adresse gehoert hoechstens zu einem
            # Mitglied — die Meldung nennt die Person.
            throw(_email_vergeben_meldung(treffer), ValidationError)
    if not _is_admin():
        throw("Nur Administratoren dürfen die E-Mail-Adresse ändern.", PermissionError)


def _validate_member_update(doc, werte):
    _validate_email_update(doc, werte)
    if "status" in werte and werte["status"] != doc.get("status") and not _is_admin():
        throw("Nur Administratoren dürfen den Status ändern.", PermissionError)
    if "datenschutz_einwilligung" in werte:
        # Check-Felder kommen auch als 0/1 oder String aus der SPA.
        if bool(_cint(werte["datenschutz_einwilligung"])) != bool(doc.get("datenschutz_einwilligung")):
            throw("Einwilligungen dürfen nur über den protokollierten Einwilligungsweg geändert werden.", PermissionError)
        # Unveraenderte Werte nicht schreiben (kein unprotokollierter Weg).
        werte.pop("datenschutz_einwilligung")


@whitelist(allow_guest=False)
def update_mitglied(mitglied_id, data=None, **kwargs):
    """Aktualisiert ein Mitglied (Quelle: mitglieder.py:271-354).

    `data` kann ein Dict ODER ein JSON-String sein (die SPA schickt beides).
    Feld-Whitelist + Alias-Mapping 1:1. Aenderungen an fremden Stammdaten
    werden ueber `_log_profil_aenderung` protokolliert (Audit Log).
    """
    perms = permissions.mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        throw("Kein Zugriff", PermissionError)

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            throw("Ungültiges JSON-Format im Parameter 'data'.", ValidationError)

    doc = get_doc("Mitglied", mitglied_id)
    data = dict(data or {})

    allowed_fields = {
        "vorname", "nachname", "email", "telefonnummer", "geburtstag",
        "postleitzahl", "wohnort", "straße", "nummer", "geschlecht",
        "familienstand", "foto", "datenschutz_einwilligung", "status",
    }
    field_aliases = {
        "telefon": "telefonnummer",
        "strasse": "straße",
        "hausnummer": "nummer",
        "plz": "postleitzahl",
        "ort": "wohnort",
    }
    personal_fields = {
        "vorname", "nachname", "email", "telefonnummer", "geburtstag",
        "postleitzahl", "wohnort", "strasse", "nummer", "geschlecht", "familienstand",
    }

    # strasse statt straße wegen Encoding-Sicherheit beim Vergleich
    old_values = {}
    for f in personal_fields:
        fname = "straße" if f == "strasse" else f
        old_values[f] = doc.get(fname)

    werte = {}
    for key, value in data.items():
        mapped_key = field_aliases.get(key, key)
        if mapped_key in allowed_fields and mapped_key in _mitglied_felder():
            werte[mapped_key] = value

    # UXD-R6: leere Datumsfelder zu None (sonst InvalidDatetimeFormat fuer
    # Mitglieder ohne Geburtstag). UXD-R8/R24: Laenge und E-Mail vorab pruefen.
    hatte_geburtstag = "geburtstag" in werte
    _normalisiere_datumsfelder(werte)
    _pruefe_textlaengen(werte)
    _pruefe_email(werte.get("email"))

    _validate_member_update(doc, werte)
    if werte:
        try:
            # UXD-R6: ein leeres Geburtsdatum soll den Wert LOESCHEN — `None`
            # wird sonst von `_update_doc` uebersprungen (kein stiller 200).
            _update_doc(
                "Mitglied", mitglied_id, werte,
                explizite_null={"geburtstag"} if hatte_geburtstag else None,
            )
        except Exception as exc:  # noqa: BLE001
            _rethrow(exc, "update_mitglied")
            raise  # pragma: no cover

        # Aenderungen loggen — nur wenn ein Admin fremde Daten bearbeitet.
        try:
            from diakronos_app.api.profile import _get_my_mitglied as _own_mid

            is_self = _own_mid() == mitglied_id
        except Exception:  # noqa: BLE001
            is_self = False
        if not is_self:
            changed = {}
            for f in personal_fields:
                fname = "straße" if f == "strasse" else f
                old_v = str(old_values.get(f) or "")
                new_v = str(getattr(doc, fname, None) or "")
                if old_v != new_v:
                    changed[fname] = {"alt": old_v, "neu": new_v}
            if changed:
                _log_profil_aenderung(mitglied_id, changed)

    return {
        "success": True,
        "message": "Mitglied aktualisiert.",
        "mitglied_id": mitglied_id,
    }


@whitelist(allow_guest=False)
def update_mitglied_with_confirmation(mitglied_id, data, audit_confirmation):
    """Aktualisiert ein Mitglied MIT Audit-Bestaetigung (Quelle: mitglieder.py:372-433).

    Setzt `audit_confirmation` vor dem Save, damit der (hier nicht vorhandene)
    Controller die Bestaetigung in `validate()` vorfindet. Die Bestaetigung
    wird exakt uebernommen: `data` und `audit_confirmation` duerfen JSON-Strings
    sein.

    `audit_confirmation` ist **Pflicht** — wie im Original. Ohne sie darf
    kein Schreibzugriff passieren; ein Default wuerde die Bestaetigungsplicht
    still aushebeln.
    """
    perms = permissions.mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        throw("Kein Zugriff", PermissionError)

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            throw("Ungültiges JSON-Format im Parameter 'data'.", ValidationError)

    if isinstance(audit_confirmation, str):
        try:
            audit_confirmation = json.loads(audit_confirmation)
        except json.JSONDecodeError:
            throw(
                "Ungültiges JSON-Format in audit_confirmation.", ValidationError
            )

    # Bestaetigung setzen (wird von Mitglied.validate() gelesen — hier Halter).
    _AUDIT_STATE.audit_confirmation = audit_confirmation

    try:
        allowed_fields = {
            "vorname", "nachname", "email", "telefonnummer", "geburtstag",
            "postleitzahl", "wohnort", "straße", "nummer", "geschlecht",
            "familienstand", "foto", "datenschutz_einwilligung", "status",
        }
        field_aliases = {
            "telefon": "telefonnummer",
            "strasse": "straße",
            "hausnummer": "nummer",
            "plz": "postleitzahl",
            "ort": "wohnort",
        }

        werte = {}
        for key, value in dict(data or {}).items():
            mapped_key = field_aliases.get(key, key)
            if mapped_key in allowed_fields and mapped_key in _mitglied_felder():
                werte[mapped_key] = value

        # Dieselben Vorpruefungen wie `update_mitglied` (UXD-R6/R8/R24).
        hatte_geburtstag = "geburtstag" in werte
        _normalisiere_datumsfelder(werte)
        _pruefe_textlaengen(werte)
        _pruefe_email(werte.get("email"))

        _validate_member_update(get_doc("Mitglied", mitglied_id), werte)
        if werte:
            _update_doc(
                "Mitglied", mitglied_id, werte,
                explizite_null={"geburtstag"} if hatte_geburtstag else None,
            )
    finally:
        _AUDIT_STATE.audit_confirmation = None

    return {
        "success": True,
        "message": "Mitglied aktualisiert.",
        "mitglied_id": mitglied_id,
    }


# ── Gruppen ─────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_gruppen_for_mitglied(mitglied_id):
    """Alle Gruppen, in denen das Mitglied ist (Quelle: mitglieder.py:410-446)."""
    perms = permissions.mitglied_permissions(mitglied_id)
    if not perms.get("can_view"):
        throw("Kein Zugriff", PermissionError)

    # Explizite Gruppenmitgliedschaften
    gruppen = get_all(
        "Gruppenmitgliedschaft",
        filters={"mitglied": mitglied_id},
        fields=["name", "parent as gruppe", "rolle", "beitrittsdatum", "status"],
    )
    for g in gruppen:
        g["gruppenname"] = get_value("Gruppe", g.get("gruppe"), "gruppenname")

    # Zusaetzlich aus ancestor_path parsen (ergaenzend)
    mitglied = get_value("Mitglied", mitglied_id, ["ancestor_path"], as_dict=True)
    if mitglied and mitglied.get("ancestor_path"):
        parts = mitglied["ancestor_path"].split("|")
        gruppen_segmente = [g for g in parts[0].split("/") if g] if parts else []
        for seg in gruppen_segmente:
            if not any(g.get("gruppe") == seg for g in gruppen):
                gruppen.append(
                    {
                        "gruppe": seg,
                        "rolle": None,
                        "source": "ancestor_path",
                    }
                )

    return {"success": True, "data": gruppen}


# ── Beziehungen ─────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_beziehungen_for_mitglied(mitglied_id):
    """Alle Beziehungen eines Mitglieds (Quelle: mitglieder.py:450-467)."""
    perms = permissions.mitglied_permissions(mitglied_id)
    if not perms.get("can_view"):
        throw("Kein Zugriff", PermissionError)

    # Das Original nutzt `fields=["*"]`; die Compat-Schicht loest Felder
    # explizit auf (`frappe_compat.query._field` wirft bei "*" KeyError).
    # Deshalb alle Spalten der Kindtabelle nennen — inkl. der Frappe-
    # Standardfelder, damit sich die Antwort nicht unterscheidet.
    beziehungen = get_all(
        "Mitglied Beziehung",
        filters={"parent": mitglied_id, "parenttype": "Mitglied"},
        fields=[
            "name", "creation", "modified", "modified_by", "owner", "docstatus",
            "idx", "beziehung_zu", "beziehungstyp", "ist_spiegel",
            "parent", "parentfield", "parenttype",
        ],
        order_by="idx asc",
    )

    return {"success": True, "data": beziehungen}


# ── DSGVO ───────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def widerruf_einwilligung(mitglied_id, **kwargs):
    """Widerruft die DSGVO-Einwilligung eines Mitglieds (Quelle: mitglieder.py:473-509).

    Der Altcode widerruft **alle drei** Einwilligungen (datenschutz, foto,
    werbung) am Mitglied und protokolliert NUR diejenigen, die vorher
    gesetzt waren — je eine Zeile in `DSGVO Einwilligung` mit
    `aktion="widerrufen"`, `quelle="admin"`.

    Ein optionales `__audit_confirmation` (aus dem Frontend) wird uebernommen.
    Kein `quelle`-Parameter des Aufrufers: das Original schreibt immer "admin"
    (der Endpunkt ist admin-/edit-berechtigt). Das ist exakt uebernommen.
    """
    import diakronos_app.frappe_compat as _compat

    perms = permissions.mitglied_permissions(mitglied_id)
    if not perms.get("can_edit"):
        throw("Kein Zugriff", PermissionError)

    # Bestaetigung an den (hier nicht vorhandenen) Controller weitergeben.
    confirmation = kwargs.pop("__audit_confirmation", None)
    if confirmation:
        _AUDIT_STATE.audit_confirmation = confirmation

    doc = get_doc("Mitglied", mitglied_id)
    hatte_datenschutz = bool(doc.get("datenschutz_einwilligung"))
    hatte_foto = bool(doc.get("foto_einwilligung"))
    hatte_werbung = bool(doc.get("werbeeinwilligung"))

    _update_doc(
        "Mitglied",
        mitglied_id,
        {
            "datenschutz_einwilligung": 0,
            "datenschutz_datum": None,
            "foto_einwilligung": 0,
            "foto_datum": None,
            "werbeeinwilligung": 0,
            "werbung_datum": None,
        },
        skip_modified=True,
    )

    if hatte_datenschutz:
        log_einwilligung(mitglied_id, "datenschutz", "widerrufen", quelle="admin")
    if hatte_foto:
        log_einwilligung(mitglied_id, "foto", "widerrufen", quelle="admin")
    if hatte_werbung:
        log_einwilligung(mitglied_id, "werbung", "widerrufen", quelle="admin")

    return {
        "success": True,
        "message": "Einwilligung widerrufen.",
    }


# ── Status / Ausschliessen (P1-9, OP-ADMIN Aufg. 3b/7a) ─────────────────────


#: Zulaessige Mitgliedsstatus (Quelle: create_mitglied/Statistik/Zaehlung).
MITGLIED_STATUS = ("Mitglied", "Gast", "Passives Mitglied", "Passiver Gast")

#: Status einer ausgetretenen Person (AUSTRITT). Steht bewusst NICHT in
#: `MITGLIED_STATUS`: der Status ist kein frei waehlbarer Stammdatenwert,
#: sondern die Folge des Austritts (Rueckweg: `mitglied_reaktivieren`).
#: Aufgenommen in `gruppen_auswahl.AUSGESCHIEDEN` — damit faellt die Person aus
#: jeder Auswahlliste. Die Liste hier ist die kleingeschriebene Filterform.
AUSGETRETEN_STATUS = frozenset({"ausgetreten"})


@whitelist(allow_guest=False)
def set_mitglied_status(mitglied_id, status):
    """Setzt den Status eines Mitglieds (nur Administratoren).

    `update_mitglied` kennt `status` bereits; dieser eigene Endpunkt macht den
    Reiter-/Dialog-Weg aus N4 einfach und prueft den Wert gegen die echten
    Status (ein ungültiger Status wurde bisher still zu „Gast“).
    Schliesst die Statusumgehung: ohne Admin-Recht nicht aufrufbar.
    """
    if not _is_admin():
        throw("Nur Administratoren dürfen den Status ändern.", PermissionError)

    status = (status or "").strip()
    if status not in MITGLIED_STATUS:
        throw(
            "Unbekannter Status. Erlaubt: " + ", ".join(MITGLIED_STATUS) + ".",
            ValidationError,
        )

    doc = get_doc("Mitglied", mitglied_id)
    alter_status = doc.get("status")
    # DSGVO-1/D5: eine gelöschte Person ist endgültig. „Reaktivieren“ über den
    # Status (oder über den Ausschluss) würde eine Person wiederherstellen, die
    # es nicht mehr gibt — die Zeile trägt nur noch die technische ID.
    if str(alter_status or "") == "geloescht":
        throw(
            "Diese Person wurde gelöscht und kann nicht reaktiviert werden.",
            ValidationError,
        )
    # Ein ausgeschlossenes Mitglied, das wieder aktiviert wird, verliert die
    # Ausschluss-Markierung (sonst widersprechen sich Status und Merkmal).
    _update_doc("Mitglied", mitglied_id, {"status": status})
    if doc.get("ausgeschlossen"):
        _update_doc(
            "Mitglied", mitglied_id,
            {"ausgeschlossen": 0, "ausgeschlossen_seit": None},
            explizite_null={"ausgeschlossen_seit"},
        )
        # R-P1-8/Punkt 5: den Negativ-Cache vergessen — sonst bliebe die Person
        # bis zu `benutzerstatus_ttl` weiter ausgesperrt, obwohl der Ausschluss
        # aufgehoben ist.
        _verbinde_ausschluss_mit_konten(mitglied_id, ausgeschlossen=False)

    # Befund 7 (P1-9b): Statusaenderungen waren nirgends protokolliert
    # (`update_mitglied` protokolliert, dieser Weg nicht). Eine
    # Statusaenderung ist ein Rechte-relevanter Eingriff und muss
    # nachvollziehbar sein.
    try:
        _log_profil_aenderung(
            mitglied_id, {"status": {"alt": str(alter_status or ""), "neu": status}}
        )
    except Exception as e:  # noqa: BLE001
        log_error(f"Status-Protokoll fehlgeschlagen: {e}", "set_mitglied_status")

    return {"success": True, "message": "Status geändert.", "status": status}


def _verbinde_ausschluss_mit_konten(mitglied_id: str, ausgeschlossen: bool) -> None:
    """Zugang des Mitglieds sofort schalten: Sitzungen widerrufen (Punkt 5).

    Beim Ausschluss werden die Sitzungen beendet (aktiver Widerruf). Beim
    Aufheben genuegt `vergiss` — der Status wird neu aus der DB gelesen, eine
    ueberlebende Sitzung ist dann wieder gueltig, weil die Negativ-Regel weg ist.
    """
    from diakronos_app.frappe_compat import benutzer_status

    daten = get_value("Mitglied", mitglied_id, ["user", "email"], as_dict=True)
    for user in benutzer_status.wirksame_konten(dict(daten) if daten else None):
        if ausgeschlossen:
            benutzer_status.widerrufe_sitzungen(user)
        else:
            benutzer_status.vergiss(user)


@whitelist(allow_guest=False)
def schliesse_mitglied_aus(mitglied_id, begruendung=""):
    """Schliesst ein Mitglied aus (weiches Entfernen, nur Administratoren).
    Ein Mitglied wird nie geloescht (Art. 17 DSGVO laeuft ueber die
    Anonymisierung, Mitglieder tragen Dienstplan-Historie). „Ausschliessen“
    setzt `ausgeschlossen=1` + `ausgeschlossen_seit` und den Status auf
    `Passiver Gast` — die Person erscheint weiter, hat aber keine Rechte.
    """
    if not _is_admin():
        throw("Nur Administratoren dürfen Mitglieder ausschließen.", PermissionError)

    get_doc("Mitglied", mitglied_id)  # Existenzpruefung (wirft sonst)

    # DSGVO-1/D5: eine gelöschte Person bleibt gelöscht. Ausschließen ist ein
    # Zustand für Menschen, die es noch gibt — hier gäbe es niemanden mehr.
    vorhandener_status = get_value("Mitglied", mitglied_id, "status")
    if str(vorhandener_status or "") == "geloescht":
        throw(
            "Diese Person wurde gelöscht — sie kann nicht ausgeschlossen oder "
            "reaktiviert werden.",
            ValidationError,
        )

    # AUSTRITT-e (NR3): Die Gegenrichtung zu „Austritt nach Ausschluss“ (NH1).
    # Ein Ausschluss einer Ausgetretenen liesse `austritt_datum` stehen; das
    # Detail meldete danach „Austritt“, und „Reaktivieren“ hoebe still den
    # Ausschluss auf. Deshalb erst zuruecknehmen, dann ausschliessen.
    zeile = get_value(
        "Mitglied", mitglied_id, ["status", "austritt_datum"], as_dict=True,
    )
    zeile = dict(zeile or {})
    if (bool(zeile.get("austritt_datum"))
            or str(zeile.get("status") or "").strip().casefold()
            == _STATUS_AUSGETRETEN.casefold()):
        throw(
            "Das Mitglied ist ausgetreten. Reaktiviere es zuerst, bevor du es "
            "ausschließt.",
            ValidationError,
        )

    # P1-8c, Pflicht 1a: ein Mitglied mit Verwaltungskonto darf nur ein System
    # Manager ausschliessen. Dieselbe Regel steht in der generischen Schicht
    # (`frappe_compat.api_helpers._pruefe_mitglied_schreibzugriff`) — hier
    # zusaetzlich, damit der Endpunkt selbst eine verstaendliche Meldung gibt.
    ziel_user = str(get_value("Mitglied", mitglied_id, "user") or "")
    if ziel_user:
        from diakronos_app.api.zugang import _verweigere_fremdes_admin_konto

        _verweigere_fremdes_admin_konto(ziel_user)

    _update_doc(
        "Mitglied",
        mitglied_id,
        {
            "ausgeschlossen": 1,
            "ausgeschlossen_seit": _today(),
            "status": "Passiver Gast",
        },
    )

    # R-P1-8/Punkt 5: der Ausschluss entzieht sofort die Rechte — bestehende
    # Sitzungen widerrufen und den Rechte-Cache vergessen (sonst lebten
    # Sitzung und Cache bis zu `benutzerstatus_ttl` weiter).
    _verbinde_ausschluss_mit_konten(mitglied_id, ausgeschlossen=True)

    # Befund 7 (P1-9b): Der Ausschluss wurde nur MIT Begruendung protokolliert,
    # und dann als „ausgeschlossen alt=0 neu=<Begruendung>“ — das Feld
    # `ausgeschlossen` traegt 0/1, die Begruendung gehoert nicht hinein. Jetzt
    # wird IMMER protokolliert (der Vorgang ist der Eintrag, nicht der Text).
    try:
        eintrag = {"ausgeschlossen": {"alt": "0", "neu": "1"}}
        if begruendung:
            eintrag["ausschlussgrund"] = {"alt": "", "neu": str(begruendung)}
        _log_profil_aenderung(mitglied_id, eintrag)
    except Exception as e:  # noqa: BLE001
        log_error(f"Ausschluss-Protokoll fehlgeschlagen: {e}", "schliesse_mitglied_aus")

    return {"success": True, "message": "Mitglied ausgeschlossen."}


# ── Import (P1-9, OP-ADMIN Aufg. 3a; Oberflaeche in N11) ────────────────────


def _parse_datum(wert: str | None):
    """CSV-Datum -> `date` oder `None`. Formate: ISO, dd.mm.yyyy, d.m.yyyy."""
    if not wert:
        return None
    s = str(wert).strip()
    if not s:
        return None
    from datetime import datetime as _dt

    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return _dt.strptime(s, fmt).date()
        except ValueError:
            continue
    return "FEHLER"


#: Grenzen des CSV-Imports (Befund 3, P1-9b). Vorher gab es KEINE: ein Admin
#: (oder ein gekaperter Admin-Zugang) konnte beliebig grosse Texte einreichen.
#: 1 MB Text und 2000 Datenzeilen reichen fuer jede echte Gemeindeliste und
#: halten Parsen/Antwort in einem vertretbaren Rahmen.
MAX_IMPORT_BYTES = 1_000_000
MAX_IMPORT_ZEILEN = 2000


def _pruefe_importgrenzen(csv_inhalt: str) -> None:
    """Groessen- und Typgrenze fuer den CSV-Text (Befund 3, P1-9b).

    Geprueft wird VOR dem Parsen (Speicher) und VOR jedem Schreiben.
    """
    if csv_inhalt is None:
        throw("Es wurde keine Datei übergeben.", ValidationError)
    if not isinstance(csv_inhalt, str):
        throw("Die Datei muss als Text übergeben werden.", ValidationError)
    if len(csv_inhalt.encode("utf-8")) > MAX_IMPORT_BYTES:
        throw(
            f"Die Datei ist zu groß (höchstens {MAX_IMPORT_BYTES // 1000} kB). "
            "Bitte in kleinere Listen aufteilen.",
            ValidationError,
        )
    if csv_inhalt.count("\n") >= MAX_IMPORT_ZEILEN + 1:
        throw(
            f"Die Datei hat zu viele Zeilen (höchstens {MAX_IMPORT_ZEILEN} "
            "Datenzeilen). Bitte in kleinere Listen aufteilen.",
            ValidationError,
        )


#: Spalten der CSV -> Feldname im Mitglied (Import, P1-9).
_IMPORT_FELDLAENGE = {
    "vorname": "Vorname",
    "nachname": "Nachname",
    "email": "E-Mail",
    "telefon": "Telefon",
    "strasse": "Straße",
    "plz": "Postleitzahl",
    "ort": "Wohnort",
}


def _email_belegung(email: str, *, ohne_mitglied: str | None = None):
    """Wer belegt diese E-Mail-Adresse schon? (getrimmt + kleingeschrieben)

    Der Ort der Wahrheit fuer „diese Adresse ist schon vergeben“ ist
    `email_belegung.belegung` — dieselbe Pruefung wie in `create_mitglied`
    und `pruefe_mitglied_dublette`. SEC (W2, Befund): der Import
    verglich vorher EXAKT und nur gegen `Mitglied`; ein Bestand
    „Gross@X.org“ galt fuer „gross@x.org“ als frei, und die Zeile wurde
    still als zweite Person mit derselben Adresse angelegt. Damit wurde die
    Adresse fuer `wirksame_konten` mehrdeutig — ein Ausschluss ueber die
    E-Mail wirkte nicht mehr.

    `ohne_mitglied` laesst einen Datensatz aus (er findet sich nicht selbst).
    """
    from diakronos_app.email_belegung import belegung

    return belegung(email, ohne_mitglied=ohne_mitglied)


def _email_belegung_gleich(a, b) -> bool:
    """Zwei E-Mail-Adressen gleich? (dieselbe Normalisierung wie beim Schreiben)"""
    from diakronos_app.email_belegung import normalisiere

    return normalisiere(a) == normalisiere(b)


def _mitglieder_mit_email(email: str) -> list[str]:
    """Mitglieder-Kennungen mit dieser Adresse — normalisiert verglichen.

    K3 (R-SEC-AUSSCHLUSS-code): Der fruehere Import verglich hier EXAKT
    (`get_all("Mitglied", filters={"email": email})`). Ein Bestand
    „Gross@X.org“ war damit fuer „gross@x.org“ kein Mitglied — die Zeile
    galt als reines Konto und lief in den Verwaltungskonto-Zweig, obwohl
    `belegung` das Mitglied sieht. Dieselbe Normalisierung wie dort:
    getrimmt + kleingeschrieben (Groessenvergleich in Python, damit die
    Abfrage auf jeder Datenbank gleich arbeitet).
    """
    treffer = get_all("Mitglied", fields=["name", "email"]) or []
    return [
        str(m["name"]) for m in treffer
        if isinstance(m, dict) and _email_belegung_gleich(m.get("email"), email)
    ]


def _mitglied_anzeigename_fuer_import(mitglied_id: str) -> str:
    """„Vorname Nachname“ eines Mitglieds fuer eine Import-Fehlermeldung.

    Faellt auf die Kennung zurueck, wenn der Datensatz nicht lesbar ist — die
    Meldung soll nie an einem Zusatz scheitern (SEC-c, K-c: der Text nennt
    die Person, mit der sich die Adresse ueberschneidet).
    """
    try:
        treffer = get_all("Mitglied", filters={"name": mitglied_id},
                          fields=["vorname", "nachname"], limit_page_length=1) or []
        zeile = treffer[0] if treffer else {}
        anzeige = " ".join(
            p for p in (zeile.get("vorname"), zeile.get("nachname")) if p
        ).strip() if isinstance(zeile, dict) else ""
    except Exception as exc:  # noqa: BLE001 — nur fuer den Meldungstext
        log_error(f"Anzeigename nicht lesbar: {type(exc).__name__}", "import_mitglieder_vorschau")
        anzeige = ""
    return anzeige or mitglied_id


def _konto_des_mitglieds(mitglied_id: str, email: str) -> str:
    """Benutzerkonto hinter einem Mitglied (SEC-c).

    Reihenfolge: `Mitglied.user` (Link), sonst das Konto mit derselben
    Adresse. Leer, wenn keins gefunden wird — dann gibt es auch keine Rolle
    zu pruefen.
    """
    try:
        treffer = get_all("Mitglied", filters={"name": mitglied_id},
                          fields=["user"], limit_page_length=1) or []
        link = str((treffer[0] or {}).get("user") or "").strip() if treffer else ""
    except Exception as exc:  # noqa: BLE001 — Rollenpruefung entscheidet danach
        log_error(f"Mitglied-Link nicht lesbar: {type(exc).__name__}", "import_mitglieder_vorschau")
        link = ""
    return link or (_kontozuordnung(email) or "")


def _kontozuordnung(email: str) -> str | None:
    """`name` des Benutzerkontos, dessen Adresse `email` traegt (SEC-c).

    Nur fuer die Import-Vorschau: sie soll den GEPLANTEN Zustand bewerten,
    also auch die Konten sehen, die eine fruehere Zeile des Laufs gerade
    angelegt hat (Regression P4). Eine Lesesitzung, keine eigene Transaktion.
    """
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.core import User
    from diakronos_app.email_belegung import normalisiere

    ziel = normalisiere(email)
    if not ziel:
        return None
    with lesesitzung() as sess:
        for konto, konto_email in sess.execute(
            select(User.name, User.email).where(User.email.is_not(None))
        ).all():
            if normalisiere(konto_email) == ziel or normalisiere(konto) == ziel:
                return str(konto)
    return None


def _import_zeile(zeile: dict, spalten: dict, datei_emails: dict | None = None,
                  datei_namen: dict | None = None, vorgemerkt=None) -> dict:
    """Eine CSV-Zeile pruefen und in Mitgliedsfelder wandeln.

    `spalten` bildet Feldname -> Spaltenkopf der Datei ab. `datei_emails`
    sammelt die in DIESER Datei bereits gesehenen E-Mail-Adressen (Befund 5,
    P1-9b): vorher wurden nur Dubletten gegen den Bestand erkannt, zwei
    gleiche Zeilen in einer Datei liefen beide durch. `datei_namen` tut
    dasselbe fuer Zeilen OHNE E-Mail (Operator-Nachtrag zur Karte N11):
    derselbe Name zweimal in einer Datei ist genauso eine Dublette, sonst
    legt derselbe Import zwei identische Personen an.
    `vorgemerkt` (SEC-c): Adressen, die fruehere Zeilen dieses Laufs anlegen
    werden (siehe `import_mitglieder_vorschau`) — sie zaehlen wie Bestand.
    Rueckgabe: {felder, fehler:[...], dublette: {grund, vorhanden}}.
    """
    def wert(feld):
        kopf = spalten.get(feld)
        # N11b (B1): Ein praeventives fuehrendes `'` aus dem Export wieder
        # entfernen — Export -> Import bleibt damit verlustfrei.
        return _entschaerfung_loesen(zeile.get(kopf) or "").strip() if kopf else ""

    vorname = wert("vorname")
    nachname = wert("nachname")
    # SEC-c: die EINE Normalisierung (NFKC, ohne jeden Leerraum, klein) — auch
    # die Vorschau muss dieselbe Adresse sehen wie die Schreibschranke.
    email = normalisiere(wert("email"))
    fehler: list[str] = []
    # SEC (W1/W2): Zeile mit der Adresse eines Verwaltungskontos — sie muss den
    # Import als Ganzes scheitern lassen (zentrale Schranke), auch wenn sie
    # schon in der Vorschau als Fehlerzeile erscheint.
    zeile_mit_schranke = False

    if not vorname:
        fehler.append("Vorname fehlt")
    if not nachname:
        fehler.append("Nachname fehlt")
    # Befund 4 (P1-9b): geprueft wurde nur vorname/nachname/email. Eine zu
    # lange Telefon-/Adresszelle liess erst die Datenbank abbrechen —
    # mitten im Lauf, nachdem vorherige Zeilen schon angelegt waren.
    for feld, name in _IMPORT_FELDLAENGE.items():
        if len(wert(feld)) > MAX_TEXTLAENGE:
            fehler.append(f"{name} zu lang (höchstens {MAX_TEXTLAENGE} Zeichen)")
    if email and not EMAIL_MUSTER.match(email):
        fehler.append("E-Mail ungültig")
    if len(vorname) > MAX_TEXTLAENGE:
        fehler.append("Vorname zu lang")
    if len(nachname) > MAX_TEXTLAENGE:
        fehler.append("Nachname zu lang")

    geburtstag = _parse_datum(wert("geburtstag"))
    if geburtstag == "FEHLER":
        fehler.append("Geburtsdatum unlesbar")
        geburtstag = None

    namensschluessel = _namensschluessel(vorname, nachname)
    dublette = None
    # E-Mail gehoert zu einem bestehenden KONTO (kein Mitglied)?
    #
    # SEC (W1/W2): Eine Person mit der Adresse eines Verwaltungskontos
    # anzulegen ist eine neue Verknuepfung — ueber sie kann der Ausschluss
    # des Mitglieds dieses Konto sperren oder freigeben. Das darf nur ein
    # System Manager. Die Pruefung sitzt hier, weil der Import sonst erst
    # beim Schreiben scheitert (dann mit allgemeiner Meldung, K4).
    #
    # W-b (R-SEC-AUSSCHLUSS-code): geprueft wird auf eine VERWALTUNGSROLLE
    # (`_rollen_von(...) & set(_ADMIN_ROLLEN)`), nicht auf „hat irgendeine
    # Rolle". Ein wartendes oder selbst angelegtes Konto mit der Rolle
    # „Mitglied" ist kein Verwaltungskonto — vorher brach daran der GANZE
    # Import ab, waehrend die zentrale Schranke denselben Datensatz erlaubte
    # (Vorschau, Import und Schranke muessen uebereinstimmen).
    #
    # K3 (R-SEC-AUSSCHLUSS-code): dieselbe Normalisierung wie `belegung` —
    # ein Konto-Bestand „Gross@X.org" wird von `belegung` als Belegung des
    # Kontos erkannt; der fruehere exakte `get_all`-Vergleich fand das
    # Mitglied dazu nicht und behandelte es faelschlich als reines Konto.
    konto_ohne_mitglied = None
    if email and not (datei_emails is not None and email in datei_emails):
        belegung_fuer_zeile = _email_belegung(email)
        if belegung_fuer_zeile is not None:
            if belegung_fuer_zeile["doctype"] == "User":
                vorhandene = _mitglieder_mit_email(email)
                if not vorhandene:
                    belegung_fuer_zeile = {**belegung_fuer_zeile, "mitglied": None}
                    konto_ohne_mitglied = belegung_fuer_zeile
                else:
                    # Konto MIT Mitglied auf derselben Adresse: keine neue
                    # Verknuepfung, aber eine zweite Person mit derselben
                    # Adresse — das schliesst die Fachentscheidung aus (K-c).
                    konto_ohne_mitglied = {**belegung_fuer_zeile,
                                           "mitglied": _mitglied_anzeigename_fuer_import(
                                               vorhandene[0])}
            else:
                # Bestehendes MITGLIED mit dieser Adresse: die Fachentscheidung
                # laesst keine zweite Person zu. Gehoert es zu einem
                # Verwaltungskonto, ist es zusaetzlich ein Rechtegrund
                # (`zeile_mit_schranke`, Regression P4 aus SEC-AUSSCHLUSS).
                konto_ohne_mitglied = {"doctype": "Mitglied",
                                       "name": belegung_fuer_zeile["name"]}
    if (konto_ohne_mitglied is not None and not _ist_system_manager()
            and konto_ohne_mitglied.get("name")):
        from diakronos_app.api.zugang import _rollen_von
        from diakronos_app.db import lesesitzung

        # Die Rollen muessen aus einer Lesesitzung kommen: `_rollen_von` oeffnet
        # bei Bedarf eine EIGENE Sitzung, und ein Fehler dort kann die
        # Sitzung eines laufenden Schreibvorgangs mit zurueckrollen (SEC-c:
        # der Import prueft Vorschau und Uebernehmen in derselben Transaktion).
        #
        # Bei einem MITGLIED zaehlen die Rollen seines Kontos: das Mitglied
        # traegt die Adresse, das Konto die Rolle (`Zeile`/`user`-Link oder
        # dieselbe Adresse). Ein Verwaltungskonto ohne `user`-Link wird ueber
        # die Adresse gefunden (`_kontozuordnung`).
        konto_fuer_rollen = str(konto_ohne_mitglied["name"])
        if konto_ohne_mitglied.get("doctype") == "Mitglied":
            konto_fuer_rollen = _konto_des_mitglieds(
                str(konto_ohne_mitglied["name"]), email
            )
        with lesesitzung():
            verwaltungsrolle = bool(
                konto_fuer_rollen
                and _rollen_von(konto_fuer_rollen) & set(_ADMIN_ROLLEN)
            )
        if verwaltungsrolle:
            # Die Zeile ist ein Fehler — UND der Lauf ist als Ganzes
            # abzulehnen. Frueher fiel die Zeile erst beim Schreiben um
            # (`_create` -> zentrale Schranke -> PermissionError ->
            # ValidationError). Genau dieser Vertrag gilt weiter: der Import
            # laeuft durch die zentrale Schranke (Regressionstest
            # `test_p1_8d::test_import_laeuft_durch_zentrale_schranke`).
            # Der Marker `schranke` traegt das nach oben.
            fehler.append(
                "E-Mail gehört zu einem Verwaltungskonto — eine Person mit "
                "dieser Adresse kann nur ein System Manager anlegen."
            )
            zeile_mit_schranke = True
        elif konto_ohne_mitglied.get("doctype") == "Mitglied":
            # Mitglied ohne Verwaltungsrolle: keine Rechtefrage, aber die
            # Fachentscheidung (eine Adresse je Person) laesst keine zweite
            # Person zu. Klartext mit Namen statt Datenbankfehler.
            fehler.append(
                "Diese E-Mail-Adresse gehört bereits zu "
                f"{_mitglied_anzeigename_fuer_import(str(konto_ohne_mitglied['name']))}. "
                "Jede Person braucht eine eigene Adresse."
            )
        elif konto_ohne_mitglied.get("doctype") == "User" and konto_ohne_mitglied.get("mitglied"):
            # Das Konto gehoert schon einem Mitglied: keine neue Verknuepfung,
            # sondern eine zweite Person mit derselben Adresse — genau das
            # schliesst die Fachentscheidung aus (W-b/G1: ein Konto mit der
            # Rolle „Mitglied“ OHNE Mitglied bleibt dagegen erlaubt).
            fehler.append(
                "Diese E-Mail-Adresse gehört bereits zu "
                f"{konto_ohne_mitglied['mitglied']}. Jede Person braucht eine "
                "eigene Adresse."
            )
        else:
            # Konto ohne Verwaltungsrolle (z. B. wartendes Konto): kein
            # Rechte-Risiko. Die Zeile wird angelegt — aber als Hinweis
            # markiert, damit die Oberflaeche es zeigen kann (K4: kein
            # stiller Zustand).
            dublette = {
                "grund": "konto",
                "vorhanden": str(konto_ohne_mitglied["name"]),
                "hinweis": (
                    "Zu dieser Adresse gibt es ein Benutzerkonto ohne "
                    "Verwaltungsrolle."
                ),
            }
    if dublette is None and not zeile_mit_schranke and email:
        if datei_emails is not None and email in datei_emails:
            # K-c (Befund): „anlegen“ legt eine Person mit einer
            # Adresse an, die in DIESER Datei schon vergeben ist. Das ist
            # kein „Dublette, die man bestaetigen koennte“, sondern ein
            # Fehler — die Fachentscheidung (eine Adresse je Person) laesst
            # ihn nicht zu. Vorher lief die Zeile bis zum Schreiben und
            # brach dann den GANZEN Lauf ab („Der Import wurde abgebrochen“),
            # obwohl die Vorschau „Server lehnt Zeilen ab“ verspricht.
            fehler.append(
                f"E-Mail-Adresse ist in der Datei schon vergeben "
                f"({datei_emails[email]})."
            )
        else:
            # SEC (W2, Befund): der Vergleich war exakt — ein Bestand
            # „Gross@X.org“ galt fuer „gross@x.org“ als frei, die Zeile wurde
            # still als ZWEITE Person mit derselben Adresse angelegt. Damit
            # wurde die Adresse mehrdeutig und ein Ausschluss ueber die E-Mail
            # wirkte nicht mehr. `belegung` vergleicht getrimmt + klein
            # (Mitglieder UND Benutzerkonten, wie beim Anlegen).
            bestand = _email_belegung(email)
            if bestand:
                # SEC-c: der Grund traegt BEIDE Angaben — `grund`/`vorhanden`
                # wie bisher (Oberflaeche) und den fertigen Klartext fuer die
                # Fehlerzeile (K-c), damit der Lauf nicht abbricht.
                dublette = {
                    "grund": "email",
                    "vorhanden": str(bestand["name"]),
                    "meldung": _email_vergeben_meldung(bestand),
                }
    if dublette is None and namensschluessel and not email:
        # Operator-Nachtrag N11: gleicher Name OHNE E-Mail — zuerst in der
        # Datei selbst, dann im Bestand. Gross/Klein und Leerraum zaehlen
        # dabei nicht (sonst umgeht "anna " die Erkennung).
        if datei_namen is not None and namensschluessel in datei_namen:
            dublette = {
                "grund": "name_in_datei",
                "vorhanden": datei_namen[namensschluessel],
            }
        else:
            treffer = get_all(
                "Mitglied",
                filters={"vorname": vorname, "nachname": nachname},
                pluck="name",
                limit_page_length=1,
            )
            if treffer:
                dublette = {"grund": "name", "vorhanden": str(treffer[0])}

    felder = {
        "vorname": vorname,
        "nachname": nachname,
        "email": email or None,
        "telefonnummer": wert("telefon") or None,
        "geburtstag": geburtstag,
        "straße": wert("strasse") or None,
        "postleitzahl": wert("plz") or None,
        "wohnort": wert("ort") or None,
    }
    return {"felder": felder, "fehler": fehler, "dublette": dublette,
            "schranke": zeile_mit_schranke}


def _namensschluessel(vorname: str, nachname: str) -> str:
    """Schluessel fuer den Namensvergleich (Operator-Nachtrag zur Karte N11).

    Gross/Klein und umgebender Leerraum zaehlen nicht: „Anna;  Beispiel" und
    „anna;albrecht" sind dieselbe Person. Mehrfacher Leerraum INNEN wird
    ebenfalls zusammengezogen.
    """
    return " ".join(f"{vorname or ''} {nachname or ''}".split()).casefold()


def _leere_import_felder(felder: dict) -> list[str]:
    """Sind Pflichtfelder leer? (letzte Pruefung unmittelbar vor dem Schreiben)"""
    fehlend = []
    if not (felder.get("vorname") or "").strip():
        fehlend.append("Vorname")
    if not (felder.get("nachname") or "").strip():
        fehlend.append("Nachname")
    return fehlend


def _normalisiere_spaltenzuordnung(spalten) -> dict:
    """Feldname -> Spaltenkopf; toleriert JSON-String oder Dict."""
    if isinstance(spalten, str):
        try:
            spalten = json.loads(spalten)
        except json.JSONDecodeError:
            throw("Ungültige Spaltenzuordnung (kein JSON).", ValidationError)
    spalten = dict(spalten or {})
    erlaubt = {
        "vorname", "nachname", "email", "telefon", "geburtstag",
        "strasse", "plz", "ort", "gruppe",
    }
    return {k: v for k, v in spalten.items() if k in erlaubt}


def _csv_zeilen(inhalt: str) -> list[dict]:
    """CSV-Text -> Liste von Zeilen-Dicts (Kopfzeile als Schluessel).

    Toleriert Semikolon ODER Komma als Trennzeichen (deutsche Excel-Dateien
    nutzen Semikolon). BOM wird entfernt.
    """
    text = (inhalt or "").lstrip("\ufeff")
    erste = text.splitlines()[0] if text.splitlines() else ""
    trenner = ";" if erste.count(";") >= erste.count(",") else ","
    leser = csv.DictReader(io.StringIO(text), delimiter=trenner)
    return [{(k or "").strip(): (v or "") for k, v in zeile.items()} for zeile in leser]


@whitelist(allow_guest=False)
def import_mitglieder_vorschau(csv_inhalt, spalten=None, *, _vorgemerkt=None):
    """Vorschau eines Mitglieder-Imports (P1-9; Oberflaeche in N11).

    `csv_inhalt`: der Text der CSV-Datei. `spalten`: Zuordnung
    Feldname -> Spaltenkopf (ohne Zuordnung werden gängige Kopfzeilen
    automatisch erkannt). Gibt je Zeile Felder, Fehler und Dublettenhinweis
    zurueck, OHNE etwas zu schreiben.

    `_vorgemerkt` (SEC-c, nur intern): Mitglieder, die dieser Lauf selbst noch
    anlegen wird. Damit bewertet die Vorschau den GEPLANTEN Zustand — eine
    Zeile mit der Adresse eines Verwaltungskontos bleibt auch dann eine
    Rechte-Frage, wenn eine fruehere Zeile des Laufs sie schon anlegt hat
    (Regression P4: sonst lief die zweite Zeile bis zum Schreiben und riss
    den ganzen Lauf ab, statt als Rechtegrund abgelehnt zu werden).
    """
    if not _is_admin():
        throw("Nur Administratoren dürfen importieren.", PermissionError)

    _pruefe_importgrenzen(csv_inhalt)

    if isinstance(spalten, str):
        try:
            spalten = json.loads(spalten) if spalten else None
        except json.JSONDecodeError:
            throw("Ungültige Spaltenzuordnung (kein JSON).", ValidationError)
    spalten = _normalisiere_spaltenzuordnung(spalten) if spalten else {}

    zeilen = _csv_zeilen(csv_inhalt)
    if not spalten and zeilen:
        spalten = _erkenne_spalten(zeilen[0].keys())

    ergebnis = []
    neu = dubletten = fehlerhaft = 0
    datei_emails: dict[str, str] = {}
    datei_namen: dict[str, str] = {}
    # SEC-c: was dieser Lauf selbst anlegt (Adresse + Konto), damit spaetere
    # Zeilen es wie Bestand behandeln (siehe `_import_zeile`).
    lage_vorgemerkt: list[dict] = list(_vorgemerkt or [])
    for i, zeile in enumerate(zeilen, start=1):
        geprueft = _import_zeile(zeile, spalten, datei_emails, datei_namen,
                                 vorgemerkt=_vorgemerkt or lage_vorgemerkt)
        if geprueft.get("schranke"):
            # Die Zeile traegt die Adresse eines VERWALTUNGSkontos. Der Grund
            # ist ein Rechtegrund (403), kein Eingabefehler — er darf nicht in
            # „Fehler" untergehen (P1-8d/P4).
            pass
        elif geprueft["dublette"] and geprueft["dublette"].get("grund") == "email":
            # K-c: eine vergebene ADRESSE ist keine „vielleicht doppelte
            # Person“, sondern ein Fehler — die Fachentscheidung (eine Adresse
            # je Person) laesst sie nicht zu. Die Vorschau zeigt damit, was der
            # Server beim Uebernehmen tut.
            geprueft["fehler"] = list(geprueft["fehler"]) + [
                geprueft["dublette"].get("meldung")
                or "Diese E-Mail-Adresse ist bereits vergeben."
            ]
            geprueft["dublette"] = None
        if geprueft["fehler"]:
            status = "fehler"
            fehlerhaft += 1
        elif geprueft["dublette"]:
            status = "dublette"
            dubletten += 1
        else:
            status = "neu"
            neu += 1
            # Fuer die Dublettenpruefung INNERHALB der Datei (Befund 5).
            e = (geprueft["felder"].get("email") or "").strip().lower()
            if e:
                datei_emails[e] = f"Zeile {i}"
                # SEC-c: die Zeile wird angelegt — spaetere Zeilen mit einer
                # Adresse dieses Kontos sollen den Rechtegrund sehen.
                email_roh = geprueft["felder"].get("email") or ""
                konto = _kontozuordnung(email_roh)
                if konto:
                    lage_vorgemerkt.append({"email": email_roh, "user": konto})
        # Auch Dubletten-Zeilen werden als gesehen vermerkt: die DRITTE
        # gleiche Zeile ohne E-Mail soll „dublette" bleiben, nicht „neu"
        # werden, nur weil die zweite uebersprungen wurde.
        schluessel = _namensschluessel(
            geprueft["felder"].get("vorname") or "",
            geprueft["felder"].get("nachname") or "",
        )
        if schluessel and not (geprueft["felder"].get("email") or ""):
            datei_namen.setdefault(schluessel, f"Zeile {i}")
        ergebnis.append({"zeile": i, "status": status, **geprueft})

    return {
        "success": True,
        "kopfzeilen": list(zeilen[0].keys()) if zeilen else [],
        "spalten": spalten,
        "zeilen": ergebnis,
        "zusammenfassung": {"neu": neu, "dubletten": dubletten, "fehler": fehlerhaft,
                            "gesamt": len(ergebnis)},
    }


#: Kopfzeilen-Erkennung (klein, ohne Umlaute verglichen).
_IMPORT_KOPF = {
    "vorname": "vorname",
    "nachname": "nachname",
    "e-mail": "email", "email": "email", "mail": "email",
    "telefon": "telefon", "telefonnummer": "telefon",
    "geburtsdatum": "geburtstag", "geburtstag": "geburtstag",
    "straße": "strasse", "strasse": "strasse",
    "plz": "plz", "postleitzahl": "plz",
    "ort": "ort", "wohnort": "ort",
    "gruppe": "gruppe",
}


def _erkenne_spalten(kopfzeilen) -> dict:
    """Spaltenzuordnung aus gängigen Kopfzeilen ableiten."""
    erkannt = {}
    for kopf in kopfzeilen:
        schluessel = str(kopf).strip().lower()
        if schluessel in _IMPORT_KOPF:
            erkannt[_IMPORT_KOPF[schluessel]] = kopf
    return erkannt


class _ZeileAbgelehnt(Exception):
    """Eine Importzeile wurde fachlich abgelehnt — der LAUF geht weiter (K-c).

    SEC-d (B2): Die Ausnahme wird ausschliesslich VOR dem Schreiben erhoben —
    die Schranke (`_pruefe_mitglied_schreibzugriff`) prueft die Adresse, bevor
    `sess.add()` laeuft. Eine abgelehnte Zeile hat deshalb nichts
    rueckgaengig zu machen; der Importlauf braucht keinen Zeilen-Speicherpunkt.
    Wer sie nach einem Schreibversuch erhebt, macht aus einer abgelehnten
    Zeile einen Abbruch (der Import prueft das: haengt noch etwas in der
    Sitzung, wird der ganze Lauf zurueckgerollt).

    Traegt nur den Klartext-Grund fuer die Ergebnisliste; die uebrigen Zeilen
    laufen normal weiter.
    """


def _lege_import_mitglied_an(felder: dict, angelegte_ids: list[str], zeile: int,
                             sess=None) -> str:
    """Legt ein Mitglied aus einer Importzeile an — alles oder nichts.

    Scheitert das Schreiben (z. B. an einer Grenze, die die Vorpruefung nicht
    kennt), wird der Aufruf abgebrochen; die Ruecknahme der bereits angelegten
    Mitglieder macht `_import_abbruch` (N11b/K3, Befund 4 P1-9b).

    N11b/K3: Der Aufrufer haelt den gesamten Lauf in einem Speicherpunkt — die
    Datenbank rollt beim Abbruch selbst zurueck. Ein nachtraegliches
    `_delete_doc` gibt es deshalb nicht mehr (R-N11b K-d).

    N11b/K4: Verweigert die Schranke das Anlegen (z. B. ein Mitgliederadmin
    will ein Mitglied mit der E-Mail eines System-Manager-Kontos anlegen),
    nennt die Meldung diesen GRUND — vorher ging er in „die Zeile ließ sich
    nicht speichern“ unter. Die uebrigen Fehler behalten den allgemeinen Text.
    """
    try:
        return _create("Mitglied", felder)
    except FrappePermissionError as e:
        # `frappe_compat.exceptions.PermissionError` (die Schranke) — eigener
        # Zweig vor `Exception`, sonst landete der Grund in der Sammelmeldung.
        _import_abbruch(zeile, e)
        grund = str(e.args[0]) if e.args else "keine Berechtigung"
        throw(
            f"Der Import wurde abgebrochen und nichts angelegt (Zeile {zeile}): "
            f"{grund}",
            PermissionError,
        )
    except ValidationError as e:
        # SEC-c (K-c): Die Vorschau stuft eine vergebene Adresse als Fehlerzeile
        # ein. Aendert sich der Bestand ZWISCHEN Vorschau und Uebernehmen
        # (zweite Person mit derselben Adresse wird gerade angelegt), meldet
        # die Schranke es fachlich — das ist genauso eine abgelehnte ZEILE und
        # kein Grund, den ganzen Lauf mit „abgebrochen“ zu beenden.
        grund = str(e.args[0]) if e.args else ""
        if "E-Mail-Adresse gehört bereits" in grund:
            raise _ZeileAbgelehnt(grund) from e
        _import_abbruch(zeile, e)
        # REST-3 (R-SEC-d K2): Den Grund, den die Schranke/das Schreiben schon
        # in Klartext kennt, an den Client weiterreichen — sonst hiess eine
        # vergebene Adresse „die Zeile liess sich nicht speichern“.
        if _ist_fachlicher_zeilengrund(grund):
            throw(
                "Der Import wurde abgebrochen und nichts angelegt "
                f"(Zeile {zeile}): {grund}",
                ValidationError,
            )
        raise
    except Exception as e:  # noqa: BLE001
        _import_abbruch(zeile, e)
        # SEC-b (Fachentscheidung 2026-10-19): Lehnt die Zeile ab, weil die
        # Adresse schon zu einer Person gehoert, nennt die Meldung diesen
        # Grund — „ließ sich nicht speichern“ waere hier eine Sackgasse.
        # Der Grund kann aus zwei Quellen kommen: die Datenbank meldet die
        # Indexverletzung (frischer Schreibversuch), oder `_create` hat sie
        # bereits in einen fachlichen Text uebersetzt.
        text = " ".join(str(a) for a in getattr(e, "args", ()) or ())
        if _ist_email_eindeutigkeit(e) or "E-Mail-Adresse gehört bereits" in text:
            throw(
                f"Der Import wurde abgebrochen und nichts angelegt (Zeile {zeile}): "
                "Diese E-Mail-Adresse gehört bereits zu einer anderen Person. "
                "Jede Person braucht eine eigene Adresse.",
                ValidationError,
            )
        throw(
            "Der Import wurde abgebrochen und nichts angelegt (Zeile "
            f"{zeile}): die Zeile ließ sich nicht speichern. Bitte die "
            "Angaben prüfen und erneut versuchen.",
            ValidationError,
        )
    raise AssertionError("unreachable")  # throw() bricht immer ab


def _ist_fachlicher_zeilengrund(grund: str) -> bool:
    """Ist `grund` ein Klartext-Grund, den der Client sehen darf? (REST-3)

    R-SEC-d K2: Beim Index-Rennen im Import hiess die Meldung „die Zeile liess
    sich nicht speichern“, obwohl der Grund („Diese E-Mail-Adresse gehört
    bereits zu einer anderen Person…“) bekannt war. Nur ein Text, den
    `_db_fehler` selbst formuliert hat, wird hier durchgereicht — ein roher
    Treibertext (SQL, Parameter, Adresse) bleibt bei der allgemeinen Meldung.
    """
    text = str(grund or "")
    return (
        "E-Mail-Adresse gehört bereits zu einer anderen Person" in text
        or "und ist bereits einer anderen Person zugeordnet" in text
    )


def _import_abbruch(zeile: int, fehler) -> None:
    """Protokoll fuer einen abgebrochenen Importlauf (N11b/K3/K4).

    Den Ruecklauf uebernimmt der Speicherpunkt des Aufrufers — die Datenbank
    rollt beim Abbruch selbst zurueck. Hier wird nur protokolliert.

    REST-3 (R-SEC-d K1): Ins Log geht NUR die Fehlerklasse. Vorher stand dort
    `str(exc)` — bei einem Datenbankfehler also das rohe SQL samt Parametern,
    darunter die Adresse des Mitglieds. `_db_fehler` (api_helpers) haelt es
    genauso: Fehlerklasse ja, SQL/Parameter/PII nein. Der fachliche Klartext
    (z. B. „E-Mail-Adresse gehört bereits …“) nennt keine Person und darf
    stehen bleiben, damit der Betrieb die Ursache erkennt.
    """
    klasse = type(fehler).__name__
    text = str(fehler.args[0]) if getattr(fehler, "args", None) else ""
    zusatz = ""
    if _ist_fachlicher_zeilengrund(text) or _ist_email_eindeutigkeit(fehler):
        zusatz = " (E-Mail-Adresse bereits vergeben)"
    log_error(
        f"Import abgebrochen in Zeile {zeile}: {klasse}{zusatz}",
        "import_mitglieder_uebernehmen",
    )


@whitelist(allow_guest=False)
def import_mitglieder_uebernehmen(
    csv_inhalt, spalten=None, dubletten_ueberspringen=True, bestaetigt=0
):
    """Uebernimmt einen geprueften Import (P1-9; Oberflaeche in N11).

    Legt nur fehlerfreie Zeilen an. Dubletten werden standardmaessig
    uebersprungen (`dubletten_ueberspringen`); mit `False` werden sie
    angelegt (bewusste Entscheidung des Admins). Rueckgabe nennt je Zeile das
    Ergebnis, damit die Oberflaeche es anzeigen kann.

    `bestaetigt` steht seit N11 auf **0** (Operator-Nachtrag, R-P1-9b-code):
    `dubletten_ueberspringen=False` allein legte Dubletten vorher ohne jede
    Rueckfrage an. Jetzt braucht das Anlegen von Dubletten die ausdrueckliche
    Bestaetigung aus der Oberflaeche (Haken im Vorschauschritt).

    P1-9b (Befund 4/5): Der Lauf ist **alles oder nichts**. Geprueft wird
    vorher vollstaendig; faellt eine Zeile beim Schreiben doch um (z. B.
    Datenbankgrenze, die die Vorpruefung nicht kennt), wird der bis dahin
    angelegte Teil wieder entfernt und der Aufruf scheitert mit Klartext.
    Vorher blieben angelegte Zeilen nach einem Abbruch stehen — ein halber
    Import, den niemand mehr auseinanderhalten konnte. Anlegen von Dubletten
    verlangt ausserdem eine ausdrueckliche Bestaetigung (`bestaetigt=0` +
    `dubletten_ueberspringen=0` wird abgelehnt) und wird protokolliert.
    """
    if not _is_admin():
        throw("Nur Administratoren dürfen importieren.", PermissionError)

    _pruefe_importgrenzen(csv_inhalt)

    ueberspringen = _als_wahr_str(dubletten_ueberspringen)
    vorschau = import_mitglieder_vorschau(csv_inhalt, spalten)
    zeilen = vorschau["zeilen"]

    if not zeilen:
        return {
            "success": True,
            "angelegt": 0,
            "uebersprungen": 0,
            "abgelehnt": 0,
            "zeilen": [],
        }

    # Befund 5: Dubletten OHNE Rueckfrage anzulegen war der Regelfall
    # (`dubletten_ueberspringen=False` genuegte). Jetzt braucht es die
    # ausdrueckliche Bestaetigung — genau der Dialog, den OP-UI-13 verlangt.
    anzahl_dubletten = sum(1 for e in zeilen if e["status"] == "dublette")
    if not ueberspringen and anzahl_dubletten and not _als_wahr_str(bestaetigt):
        throw(
            f"{anzahl_dubletten} Zeile(n) sind Dubletten. Bitte den Import "
            "ausdrücklich bestätigen, wenn sie trotzdem angelegt werden sollen.",
            ValidationError,
        )

    angelegt = uebersprungen = abgelehnt = 0
    ergebnis = []
    angelegte_ids: list[str] = []

    # SEC (W1): Der Import laeuft durch die zentrale Schranke. Eine Zeile mit
    # der Adresse eines Verwaltungskontos wird hier abgelehnt — als GANZER
    # Lauf, mit Klartext (der Vertrag des Regressionstests
    # `test_p1_8d::test_import_laeuft_durch_zentrale_schranke`).
    schranken_zeilen = [e for e in zeilen if e.get("schranke")]
    if schranken_zeilen:
        grund = "; ".join(
            f"Zeile {e['zeile']}: {' '.join(e['fehler'])}" for e in schranken_zeilen
        )
        # K4/N11b: Der Grund wird im Klartext genannt UND der Lauf laeuft durch
        # die zentrale Schranke — also ein Rechte-Fehler (403), kein allgemeiner
        # Eingabefehler. Genau dieses Verhalten verlangt der Regressionstest
        # `test_p1_8d::test_import_laeuft_durch_zentrale_schranke`.
        throw(
            "Der Import wurde abgebrochen und nichts angelegt "
            f"({grund}).",
            PermissionError,
        )

    # N11b/K3: Der Lauf ist eine ECHTE Transaktion. Alle Zeilen werden in EINER
    # Sitzung geschrieben, die zusammen mit einem Speicherpunkt (SAVEPOINT)
    # aufgespannt wird: scheitert eine Zeile, wird der Speicherpunkt
    # zurueckgerollt — es bleibt nichts stehen, auch nicht bei einem
    # Prozessabbruch mitten im Lauf. Vorher lag der Schreibweg ausserhalb
    # (jedes `_create` eigene Sitzung + sofortiger Commit), und die bereits
    # angelegten Datensaetze wurden nachtraeglich per `_delete_doc` entfernt —
    # ein halber Import konnte stehen bleiben.
    #
    # `SessionLocal.begin()` committet beim Verlassen; `als_aktuelle_sitzung`
    # sorgt dafuer, dass `_create` DIESE Sitzung benutzt (nur `flush`) statt
    # einer eigenen. Im Test-Rahmen ist das dieselbe, gepatchte Sitzung.
    #
    # SEC-d (B1/B2): Der Lauf ist EINE Transaktion. Es gibt KEINEN
    # Zeilen-Speicherpunkt mehr: `_lege_import_mitglied_an` lehnt eine Zeile
    # VOR dem Schreiben ab (die Schranke prueft die Adresse, bevor
    # `sess.add()` laeuft) — eine abgelehnte Zeile hat also nichts zu
    # rueckgaengig zu machen. Ein `with _sitzung.begin_nested():` je Zeile war
    # auf SQLite sogar schaedlich: pysqlite sendet `BEGIN` erst vor einem
    # INSERT, ein `RELEASE SAVEPOINT` schliesst dann die ganze Transaktion ab —
    # die Zeile war committet und der Lauf liess sich nicht mehr zuruecknehmen
    # (Test `test_import_ruecknahme_ist_echte_transaktion`). Jeder andere
    # Fehler verlaesst das `SessionLocal.begin()` und rollt den GANZEN Lauf
    # zurueck; „nichts angelegt“ stimmt dann wirklich.
    #
    # Damit das traegt, darf waehrend des Laufs KEIN Lesehelfer eine ZWEITE
    # Sitzung oeffnen oder eine geliehene schliessen: auf einer Datenbank mit
    # EINER Verbindung je Engine rollt schon ein `close()` die offene
    # Transaktion weg („no such savepoint“). `_belegung_aus_sitzung`,
    # `_kontozustand`, `_konto_mitglieder` lesen deshalb ueber die Sitzung des
    # Laufs.
    from diakronos_app import db as _db

    with _db.SessionLocal.begin() as _sitzung:
        with _db.als_aktuelle_sitzung(_sitzung):
            for eintrag in zeilen:
                if eintrag["status"] == "fehler":
                    abgelehnt += 1
                    ergebnis.append({"zeile": eintrag["zeile"], "ergebnis": "abgelehnt",
                                     "fehler": eintrag["fehler"]})
                    continue
                if eintrag["status"] == "dublette" and ueberspringen:
                    uebersprungen += 1
                    ergebnis.append({"zeile": eintrag["zeile"], "ergebnis": "uebersprungen",
                                     "dublette": eintrag["dublette"]})
                    continue
                if (eintrag["status"] == "dublette"
                        and not ueberspringen
                        and eintrag["dublette"].get("grund") == "email"
                        and eintrag["dublette"].get("meldung")):
                    # K-c (Befund): eine vergebene ADRESSE laesst
                    # sich nicht „trotzdem anlegen“. Vorher lief die Zeile
                    # bis zum Schreiben und riss den GANZEN Lauf ab; jetzt
                    # ist es eine abgelehnte Zeile mit Klartext — genau das,
                    # was die Uebersicht „Server lehnt Zeilen ab“ sagt.
                    # MIT `dubletten_ueberspringen` bleibt die Zeile wie
                    # bisher „uebersprungen“ (Anzahl und Zaehlung der
                    # Oberflaeche).
                    abgelehnt += 1
                    ergebnis.append({
                        "zeile": eintrag["zeile"], "ergebnis": "abgelehnt",
                        "fehler": [eintrag["dublette"]["meldung"]],
                    })
                    continue

                felder = {k: v for k, v in eintrag["felder"].items() if v not in (None, "")}
                # Zweite Pruefung unmittelbar vor dem Schreiben: die Vorschau
                # kann zwischenzeitlich veraltete Daten gesehen haben.
                fehlend = _leere_import_felder(felder)
                if fehlend:
                    abgelehnt += 1
                    ergebnis.append({"zeile": eintrag["zeile"], "ergebnis": "abgelehnt",
                                     "fehler": [f"{f} fehlt" for f in fehlend]})
                    continue
                felder["status"] = "Mitglied"
                # K-c: Eine ABGELEHNTE Zeile ist ein Ergebnis, kein Abbruch —
                # sie wurde aber VOR dem Schreiben abgelehnt (Schranke), es
                # gibt also nichts zurueckzunehmen. Jeder ANDERE Fehler bricht
                # den ganzen Lauf ab und rollt die aeussere Transaktion zurueck
                # („nichts angelegt“ muss stimmen, SEC-d/B2).
                try:
                    angelegter_name = _lege_import_mitglied_an(
                        felder, angelegte_ids, eintrag["zeile"], _sitzung)
                except _ZeileAbgelehnt as abgelehnt_fehler:
                    if not _sitzung.is_active or _sitzung.new or _sitzung.dirty:
                        # Es haengt doch eine angefangene Zeile in der
                        # Sitzung: dann ist das KEINE abgelehnte Zeile,
                        # sondern ein Abbruchgrund.
                        _import_abbruch(eintrag["zeile"], abgelehnt_fehler)
                        throw(
                            "Der Import wurde abgebrochen und nichts angelegt "
                            f"(Zeile {eintrag['zeile']}): die Zeile ließ sich "
                            "nicht speichern. Bitte die Angaben prüfen und "
                            "erneut versuchen.",
                            ValidationError,
                        )
                    abgelehnt += 1
                    ergebnis.append({
                        "zeile": eintrag["zeile"], "ergebnis": "abgelehnt",
                        "fehler": [str(abgelehnt_fehler)],
                    })
                    continue
                angelegte_ids.append(angelegter_name)
                angelegt += 1
                ergebnis.append({"zeile": eintrag["zeile"], "ergebnis": "angelegt",
                                 "mitglied_id": angelegter_name})

    # Audit-Log (Befund 7-Muster): ein Massenimport ist eine Datenaenderung
    # und muss nachvollziehbar sein — auch mit Anzahl der Dubletten.
    if angelegt:
        try:
            _log_profil_aenderung(
                angelegte_ids[0],
                {
                    "import": {
                        "alt": "0",
                        "neu": (
                            f"{angelegt} Mitglied(er) aus CSV importiert, "
                            f"{uebersprungen} Dublette(n) übersprungen, "
                            f"{abgelehnt} Zeile(n) abgelehnt"
                        ),
                    }
                },
            )
        except Exception as e:  # noqa: BLE001
            log_error(f"Import-Protokollierung fehlgeschlagen: {e}", "import_mitglieder_uebernehmen")

    return {
        "success": True,
        "angelegt": angelegt,
        "uebersprungen": uebersprungen,
        "abgelehnt": abgelehnt,
        "zeilen": ergebnis,
    }


def _als_wahr_str(wert) -> bool:
    """Toleranter Wahrheitstest (0/1/'0'/'1'/True/False/'true')."""
    if isinstance(wert, bool):
        return wert
    if wert is None:
        return False
    return str(wert).strip().lower() not in {"0", "false", "nein", "no", ""}


# ── Permission-Helfer ───────────────────────────────────────────────────────


class _AuditState:
    """`frappe.local.audit_confirmation` / `audit_policy_logged` als Halter.

    Die Vorlage legt beide Attribute auf `frappe.local`. Im Standalone-Backend
    gibt es diesen Namespace nicht; ein Modul-Halter hat dieselbe Rolle.
    (`_shared._Flags` ist dafuer nicht geeignet: `__slots__` erlaubt nur
    `allow_series_edit`.)
    """

    __slots__ = ("audit_confirmation", "audit_policy_logged")

    def __init__(self) -> None:
        self.audit_confirmation = None
        self.audit_policy_logged = False


_AUDIT_STATE = _AuditState()


def _cint(value) -> int:
    """`frappe.utils.cint` — tolerant zu int/str/bool."""
    if value is None or isinstance(value, bool):
        return 1 if value else 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


_MITGLIED_FELDER: set[str] | None = None


def _mitglied_felder() -> set[str]:
    """Spaltennamen von `Mitglied` (Feld-Whitelist fuer Schreibzugriffe).

    Quelle der Wahrheit ist die echte DB (`Spaltenabzug der Betriebs-DB`) —
    `_update_doc` schreibt ohnehin nur bekannte Spalten; die Whitelist hier
    verhindert zusaetzlich, dass Aufrufer fachfremde Felder setzen.
    """
    global _MITGLIED_FELDER
    if _MITGLIED_FELDER is None:
        _MITGLIED_FELDER = set(column_names("Mitglied"))
    return _MITGLIED_FELDER
