"""Portierung von `diakonos/api/profile.py` (P4n) — 6 whitelists.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/profile.py`

Die SPA ruft die ORIGINAL-Pfade `diakronos.diakonos.api.profile.<fn>` auf
(`frontend/src/diakonos/pages/Profile.vue:322-506` — dort ueber
``apiFetch('profile.<fn>')`` gegen `API = '/api/method/diakronos.diakonos.api'`).

BEFUND ZUM ABNAHME-SKRIPT (P4n, Punkt 5 der Karte): die Abnahme liest die
Aufrufliste des Frappe-Frontends und filtert auf `art == "method"`. Die sechs
Profil-Aufrufe stehen dort **nicht** — `Profile.vue` baut die Pfade per
Template-String (Zeile 326: `` `${API}.${method}` ``), das Inventar fuehrt sie
als `art: "dynamisch"` (`<dynamisch: API.method>`). Die sechs Pfade koennen in
dieser Datei also gar nicht auftauchen; das Skript bleibt unveraendert
bei 106/0. Das ist kein Fortschrittsverlust, sondern eine Luecke des Skripts
selbst: es prueft dynamische Aufrufe prinzipiell nicht. Die Wirkpruefung
fuer diese Karte ist deshalb die Messung aus der Abnahme (anonymer Aufruf
404 -> 403, angemeldet 200 mit Daten), nicht das Skript.

Damit das Inventar nicht zusaetzlich in die Irre fuehrt: dieselben sechs
Endpunkte standen in `inventar/PORTIERUNGSLISTE.md` unter "Verwaiste
Endpunkte" (also "von der SPA NIE gerufen") — das war der Inventory-Fehler,
den diese Karte ausgeraeumt hat. Ein Endpunkt, den die SPA per Template-
String ruft, ist fuer ein Inventar unsichtbar; "nicht gefunden" heisst hier
also "nicht aufloesbar", nicht "ungenutzt".

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user          -> session.user
    frappe.db.get_value(...)     -> get_value(...)
    frappe.get_doc(...)          -> get_doc(...) -> Document
    frappe.db.set_value(...)     -> _update_doc(...) (benoetigte Spalten)
    frappe.db.commit()           -> entfaellt (die Ports committen je Session)
    frappe.throw(msg, exc)       -> throw(msg, exc)
    frappe.local.audit_skip      -> entfaellt (kein Audit-Policy-Hook, s. u.)
    frappe.local.login_manager.logout() -> _widerrufe_sitzungen() (B1: alle
                                          Sitzungen des Benutzers)

SCHARF KANTE — `_get_my_mitglied()`
----------------------------------
Das Profil haengt am `Mitglied`-Datensatz, NICHT am `user`. Diese Funktion ist
der Schluessel des ganzen Moduls und in JEDER der sechs Endpunkte der erste
Aufruf.

Das Original wirft `frappe.throw("Kein Mitglied-Datensatz fuer diesen Nutzer
gefunden.")` — ein **fachlicher Fehler (HTTP 417)**, kein 500. Das Verhalten
ist hier 1:1 uebernommen: `throw()` ohne Exc-Klasse -> `ValidationError` ->
417 mit `exc_type=ValidationError`. Ein angemeldeter Benutzer ohne Mitglied
(z. B. ein frisch angelegter Erst-Admin) bekommt damit die ehrliche, in der
Anzeige sichtbare Antwort "Kein Mitglied-Datensatz fuer diesen Nutzer
gefunden." — und die SPA rendert genau diesen Text (`Profile.vue:16`,
`v-else-if="error"`). Es war nur zu pruefen, dass es kein 500 wird: die
`throw()`-Kette endet beim Router in `_error_response(..., 417)`, und
`get_doc`/`get_value` werfen `DoesNotExistError` (404) statt 500. Beides ist
in `test_p4n_profil.py` festgenagelt.

Die zweite Suchstufe des Originals (Rueckfall von `Mitglied.user` auf
`Mitglied.email` ueber `User.email`) ist uebernommen — sie faengt den Fall,
dass die `user`-Verknuepfung fehlt, der Email-Abgleich aber passt.
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.profile"

import json
import re

from diakronos_app.api.dsgvo_log import log_einwilligung
from diakronos_app.frappe_compat.api_helpers import (
    _today,
    get_doc,
    get_value,
    log_error,
    throw,
)
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError as FrappePermissionError,
    ValidationError,
)
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.query import get_all
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session

# Sichtbarkeits-Defaults, wenn am Mitglied nichts hinterlegt ist.
# 1:1 aus dem Original (profile.py:29) — email/telefonnummer sichtbar,
# adresse/geburtstag NICHT.
_SICHTBARKEIT_DEFAULT = {
    "email": True,
    "telefonnummer": True,
    "adresse": False,
    "geburtstag": False,
}


def _get_my_mitglied() -> str:
    """Der `Mitglied`-Name des angemeldeten Benutzers — Schluessel des Moduls.

    1:1 nach `profile.py:6-14`. Zwei Stufen, wie im Original:

      1. `Mitglied.user == session.user`
      2. Rueckfall ueber die E-Mail: `User.email` (oder der Benutzername
         selbst, wenn die User-Zeile keine E-Mail traegt) auf `Mitglied.email`

    Findet sich nichts, wirft das Original `frappe.throw("Kein Mitglied-
    Datensatz fuer diesen Nutzer gefunden.")` — hier `ValidationError` (417).
    Bewusst KEIN 500 und bewusst KEIN stilles `None`: ein leeres Profil,
    das wie ein Datenfehler aussieht, waere schlimmer als die klare
    Fehlermeldung, die `Profile.vue` anzeigt.
    """
    user = session.user
    names = get_all("Mitglied", filters={"user": user}, pluck="name", limit_page_length=2)
    if len(names) > 1:
        throw("Dein Konto ist mehreren Mitgliedern zugeordnet. Bitte lass dies von der Gemeindeverwaltung prüfen.")
    name = names[0] if names else None
    if not name:
        member = permissions._get_current_user_mitglied()
        name = member["name"] if member else None
    if not name:
        throw("Deinem Konto ist noch kein Mitglied zugeordnet. Bitte wende dich an die Gemeindeverwaltung.")
        raise AssertionError("unreachable — throw() wirft immer")  # noqa: TRY301
    return str(name)


def _sichtbarkeit_lesen(raw) -> dict:
    """B2: zeigt exakt die fail-closed-Auslieferungsregel an.

    Alle vier Schalter kommen zurueck: Object.assign() in Profile.vue darf
    fehlende Schalter nicht mit seinem alten True-Default anzeigen.
    """
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen
    return sichtbarkeit_lesen(raw)


@whitelist(allow_guest=False)
def get_my_profile():
    """Das eigene Profil des angemeldeten Mitglieds.

    Quelle: `profile.py:17-52`. Liefert genau die 19 Felder des Originals —
    die SPA liest sie 1:1 (`Profile.vue:384`, `vorname/nachname/email/foto/
    geburtstag/telefonnummer/postleitzahl/wohnort/strasse/nummer` im Template,
    `adressbuch_sichtbarkeit`, `datenschutz_einwilligung`, `foto_einwilligung`,
    `werbeeinwilligung` in den Schaltern).

    `datenschutz_datum` / `foto_datum` / `werbung_datum` werden zu Strings
    (`str(...)` wie im Original), sonst kaeme ein `date` im JSON-Envelope an.
    """
    mid = _get_my_mitglied()
    doc = get_doc("Mitglied", mid)

    sichtbarkeit = _sichtbarkeit_lesen(doc.get("adressbuch_sichtbarkeit"))

    return {
        "name": doc.name,
        "vorname": doc.vorname or "",
        "nachname": doc.nachname or "",
        "email": doc.email or "",
        "geburtstag": str(doc.geburtstag) if doc.geburtstag else None,
        "telefonnummer": doc.telefonnummer or "",
        "postleitzahl": doc.postleitzahl or "",
        "wohnort": doc.wohnort or "",
        "strasse": doc.get("straße") or "",
        "nummer": doc.nummer or "",
        "foto": _datei_mit_praefix(doc.foto),
        "geschlecht": doc.geschlecht or "",
        "familienstand": doc.familienstand or "",
        "datenschutz_einwilligung": bool(doc.datenschutz_einwilligung),
        "datenschutz_datum": str(doc.datenschutz_datum) if doc.datenschutz_datum else None,
        "foto_einwilligung": bool(doc.get("foto_einwilligung")),
        "foto_datum": str(doc.get("foto_datum")) if doc.get("foto_datum") else None,
        "werbeeinwilligung": bool(doc.get("werbeeinwilligung")),
        "werbung_datum": str(doc.get("werbung_datum")) if doc.get("werbung_datum") else None,
        "adressbuch_sichtbarkeit": sichtbarkeit,
    }


# ── Schreiben ───────────────────────────────────────────────────────────────
#
# WARUM NICHT `_update_doc` (api_helpers): der gemeinsame Helfer verwirft
# `None`-Werte (`{k: v for k, v in values.items() if k in cols and v is not
# None}`). Das Original setzt aber bewusst auf NULL:
#
#   * `update_my_profile`: `doc.geburtstag = geburtstag or None` — ein
#     leeres Geburtsdatumsfeld SOLL den Geburtstag loeschen.
#   * `update_einwilligung`: `foto_datum = heute if erteilt else None` — der
#     Widerruf loescht das Datum.
#
# Mit `_update_doc` waere beides ein stiller 200, der nichts speichert — die
# Abnahme dieser Karte nennt genau das schlimmer als einen Fehler. Deshalb
# die zwei Wege des Originals, 1:1 uebernommen:
#
#   doc.feld = x; doc.save()   -> Document.setattr + Document.save()
#   frappe.db.set_value(...)   -> Document.db_set()
#
# Das ist KEINE zweite Umsetzung: `Document` (frappe_compat/doc.py) ist die
# vorhandene Frappe-Huelle fuer genau diese beiden Faelle.

# `straße` ist ein Attributname mit Umlaut, aber gueltiger Python-Name.
# `getattr(doc, "straße")` waere der Klammer-Weg; das Original nutzt
# `doc.get("straße")`, und das machen wir genauso.
_STRASSE = "straße"


def _cint(value) -> int:
    """`frappe.utils.cint` — tolerant zu int/str/bool.

    1:1 nach `mitglieder.py::_cint` (dort fuer `widerruf_einwilligung`).
    `None` und alles Unparsbare -> 0, `True` -> 1. Wichtig fuer
    `update_einwilligung`: die SPA schickt `erteilt ? 1 : 0`, ein
    Formular koennte aber auch `""` oder `"0"` senden — beides heisst
    "widerrufen", nicht "Fehler".
    """
    if value is None or isinstance(value, bool):
        return 1 if value else 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


_GESCHLECHT_ERLAUBT = ("", "Männlich", "Weiblich")


def _geschlecht_pruefen(neu, alt=None):
    """DEV-B3: Geschlecht nur ''/„Männlich"/„Weiblich" — Altdatum bleibt gültig.

    Nur eine ÄNDERUNG wird geprüft. Wer ein anderes Feld speichert und dabei
    das unveränderte Altdatum (z. B. „divers") mitsendet, wird nicht
    blockiert; die Datenbank wird dabei nicht umgeschrieben.
    """
    wert = "" if neu is None else neu
    if not isinstance(wert, str):
        raise ValidationError("Geschlecht: bitte „Männlich“ oder „Weiblich“ wählen.")
    wert = wert.strip()
    if wert == (alt or ""):
        return wert
    if wert not in _GESCHLECHT_ERLAUBT:
        raise ValidationError("Geschlecht: bitte „Männlich“ oder „Weiblich“ wählen.")
    return wert


@whitelist(methods=["POST"], allow_guest=False)
def update_my_profile(vorname=None, nachname=None, telefonnummer=None,
                      postleitzahl=None, wohnort=None, strasse=None,
                      nummer=None, geburtstag=None, geschlecht=None,
                      familienstand=None):
    """Speichert die eigenen Stammdaten.

    Quelle: `profile.py:55-78`. Jedes Feld wird nur geschrieben, wenn es
    NICHT `None` ist (`if vorname is not None:`) — der Unterschied zwischen
    "nicht mitgeschickt" und "leer" ist Absicht: die SPA schickt beim
    Bearbeiten alle Felder, ein Teildialog also nur einige. `geburtstag` ist
    die einzige Ausnahme: dort ist ein leerer String ein LOESCH-Befehl
    (`geburtstag or None`, s. Original Zeile 70).

    `frappe.local.audit_skip.add(doc.name)` aus dem Original (Zeile 73-75) hat
    hier keine Entsprechung und ist bewusst weggelassen: die Frappe-Audit-
    Policy (`CONFIRM_REQUIRED`), die diesen Skip ueberhaupt noetig macht, ist
    im Standalone-Backend nicht portiert (`api/audit_policy/` enthaelt nur
    `anonymize.py`, der Policy-Decorator fehlt — s. dessen Docstring). Ohne
    die Policy gibt es nichts zu ueberspringen; die Zeile waere ein Halter
    fuer einen Weg, den es hier nicht gibt. Falls die Audit-Policy doch
    portiert wird, gehoert der Skip in diese Karte zurueck.

    Kein Einwilligungsfeld wird hier angefasst — dafuer ist
    `update_einwilligung` da, und laut `referenz/.../AGENTS.md` duerfen die
    sechs Einwilligungsfelder ausschliesslich ueber die whitelisted Funktionen
    mit Log-Eintrag geaendert werden.
    """
    mid = _get_my_mitglied()
    doc = get_doc("Mitglied", mid)

    if vorname is not None:
        doc.vorname = vorname
    if nachname is not None:
        doc.nachname = nachname
    if telefonnummer is not None:
        doc.telefonnummer = telefonnummer
    if postleitzahl is not None:
        doc.postleitzahl = postleitzahl
    if wohnort is not None:
        doc.wohnort = wohnort
    if strasse is not None:
        doc.set(_STRASSE, strasse)
    if nummer is not None:
        doc.nummer = nummer
    if geburtstag is not None:
        doc.geburtstag = geburtstag or None
    if geschlecht is not None:
        # DEV-B3 (Entscheidung Manuel 2026-10-29, DMB-e2a7f41994d7): nur
        # „Männlich"/„Weiblich", leer = nicht angegeben. Ein unveraendert
        # mitgesendetes Altdatum bleibt zulaessig (sonst scheitert das
        # Speichern eines anderen Feldes an Bestandsdaten).
        doc.geschlecht = _geschlecht_pruefen(geschlecht, doc.geschlecht)
    if familienstand is not None:
        doc.familienstand = familienstand

    doc.save()
    return {"ok": True}


@whitelist(methods=["POST"], allow_guest=False)
def update_adressbuch_sichtbarkeit(settings=None):
    """Speichert die Adressbuch-Sichtbarkeit des eigenen Profils.

    Quelle: `profile.py:81-90`. Zwei Sicherungen, beide uebernommen:

    1. `settings` darf ein JSON-String sein (Frappe-Formular) — wird geparst.
    2. Der Allowlist-Filter: nur `email`, `telefonnummer`, `adresse`,
       `geburtstag` duerfen gespeichert werden, und jeder Wert wird auf
       `bool` gecastet. Ein Schreibversuch auf einen anderen Schluessel wird
       also still ignoriert statt gespeichert — genau wie im Original.

    Gespeichert wird der `json.dumps`-Text, weil die Spalte `Text` ist und
    `get_my_profile` ihn wieder als Dict liest. Beide Seiten benutzen
    denselben Text, deshalb kann die Anzeige den Wert nicht verlieren.
    """
    mid = _get_my_mitglied()
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except (ValueError, TypeError):
            settings = {}
    allowed = {"email", "telefonnummer", "adresse", "geburtstag"}
    # B2: nur echtes bool true ist eine Freigabe, niemals String "false"/1.
    settings = settings if isinstance(settings, dict) else {}
    clean = {k: v is True for k, v in settings.items() if k in allowed}

    doc = get_doc("Mitglied", mid)
    doc.db_set("adressbuch_sichtbarkeit", json.dumps(clean))
    return {"ok": True}


# ── Einwilligung ────────────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def update_einwilligung(typ, erteilt):
    """Setzt die Foto- oder Werbeeinwilligung des eigenen Profils.

    Quelle: `profile.py:103-126`. Der Aufruf der SPA fuer den WIDERRUF
    (`Profile.vue:499`) geht ueber denselben Pfad mit `erteilt=0` — es gibt
    kein `delete_mywilligung`, die Portierungsliste nennt nur diese eine
    Funktion fuer beide Richtungen.

    Drei Dinge sind hier nicht verhandelbar und alle drei stammen aus
    `referenz/.../AGENTS.md`:

    1. **Log-Pflicht.** Jede Aenderung erzeugt einen Eintrag in
       `DSGVO Einwilligung` (`aktion="erteilt"` bzw. `"widerrufen"`), und der
       Eintrag wird NACH dem Schreiben geschrieben — so wie im Original
       (Zeile 125, nach `frappe.db.commit()`). Der Log-Eintrag ueberlebt die
       spaetere Datenloeschung, weil er nur `mitglied.name` kennt.
    2. **Kein freier Schreibweg.** `frappe.db.set_value` (nicht
       `doc.save()`) — die Frappe-Audit-Policy (`CONFIRM_REQUIRED`) kann
       einen `doc.save()` abbrechen, und laut AGENTS.md waere das ein
       stiller Fehlschlag. Deshalb wird `Document.db_set()` benutzt, genau
       wie in `api/mitglieder.py::widerruf_einwilligung`.
    3. **Whitelist fuer `typ`.** Nur `foto` und `werbung` sind hier
       aenderbar. `datenschutz` geht ausdruecklich NICHT ueber diesen Weg
       (Original Zeile 123: `frappe.throw("Ungültiger Einwilligungstyp")`),
       sondern ueber `mitglieder.widerruf_einwilligung` (Admin) bzw. die
       Registrierung. Der Wurf kommt VOR jedem Schreibzugriff.

    Das Datum: `heute` bei Erteilung, `None` beim Widerruf. Ein Widerruf
    ohne Datum waere ein Einwilligungs-Eintrag, dem man nicht ansehen kann,
    ob und wann er erfolgte — `frappe.utils.nowdate()` in ISO.
    """
    user = session.user
    if user == "Guest":
        throw("Nicht angemeldet", FrappePermissionError)

    mid = _get_my_mitglied()
    erteilt = _cint(erteilt)
    heute = _today() if erteilt else None

    werte: dict
    if typ == "foto":
        werte = {"foto_einwilligung": erteilt, "foto_datum": heute}
    elif typ == "werbung":
        werte = {"werbeeinwilligung": erteilt, "werbung_datum": heute}
    else:
        # VOR dem Schreiben — ein Log-Eintrag fuer eine nicht stattgefundene
        # Aenderung waere der schlimmere Fehler.
        throw("Ungültiger Einwilligungstyp")
        raise AssertionError("unreachable — throw() wirft immer")  # noqa: TRY301

    doc = get_doc("Mitglied", mid)
    for feld, wert in werte.items():
        doc.db_set(feld, wert)

    log_einwilligung(mid, typ, "erteilt" if erteilt else "widerrufen")
    return {"ok": True}


# ── Datei-Adressen ──────────────────────────────────────────────────────────


#: Erlaubte Adressformen einer hochgeladenen Datei: ein einzelner Name unter
#: `files/` bzw. `private/files/`, optional mit dem AKTIVEN Betriebs-Praefix
#: davor (`/diakronos/files/<name>`, siehe `base_path.datei_url`, WEB-5a).
#: MT-2b: nur noch `aktiver_praefix()` oder gar kein Praefix — ein beliebiges
#: fremdes `/x/y/files/…` ist keine Adresse dieser Installation mehr.
#: `fullmatch` statt `match` + `$`: `$` erlaubt in Python ein abschliessendes
#: Zeilenende (`"…/a.jpg\n"`), `fullmatch` nicht.
#: Die Zeichenklasse des Praefix-Segments verlangt mindestens ein Zeichen
#: ausser `.`, damit `.`, `..` und `...` NIE als Pfadteil durchgehen (MT-2).
def _datei_url_muster() -> re.Pattern[str]:
    from diakronos_app.base_path import aktiver_praefix

    # MT-2b: genau ZWEI Formen — praefixfrei (`/files/<name>`, die DB-Form)
    # oder MIT dem aktiven Praefix (`/diakronos/files/<name>`, die Form aus
    # `upload_file`). Ein beliebiges `/x/y/files/…` ist keine Adresse dieser
    # Installation. Eine Pfad-Segment-Gruppe vor `files/` gibt es bewusst
    # nicht mehr: sie haette jedes Praefix akzeptiert.
    # `re.escape` behaelt den fuehrenden Schraegstrich (`/diakronos`) — er darf
    # NICHT noch einmal davorgesetzt werden, sonst entstuende `//diakronos/…`.
    praefix = re.escape(aktiver_praefix())
    return re.compile(
        rf'(?:{praefix})?/(?:private/)?files/([A-Za-z0-9._-]+)'
    )


def _dateiname_aus_file_url(file_url: str) -> str | None:
    """Dateiname aus einer `file_url` — oder `None`, wenn die Form nicht passt.

    MT-2: `upload_file` gibt die Adresse MIT Betriebs-Praefix aus
    (`/diakronos/files/<name>`), die `File`-Zeile in der Datenbank traegt
    weiter `/files/<name>`. Zeichengenau verglichen fand die Besitzpruefung
    deshalb unter dem Praefix NIE eine Zeile — auch bei eigener Datei (403).
    Verglichen wird jetzt der Dateiname; `stored_path` prueft ihn danach
    erneut gegen das Ablageverzeichnis.

    MT-2b: das Praefix-Segment ist genau der aktive Praefix (oder leer) und
    der Vergleich ist ein `fullmatch`. Zusaetzlich muss der Dateiname im
    Dateinamen-Teil exakt dem Muster entsprechen: `.`/`..` als Name fallen
    durch (die Zeichenklasse `[A-Za-z0-9._-]+` liesse sie sonst zu und
    `stored_path` wuerde erst spaeter ablehnen).
    """
    treffer = _datei_url_muster().fullmatch(str(file_url or ''))
    if treffer and treffer.group(1) not in ('.', '..'):
        return treffer.group(1)
    return None


def _datei_mit_praefix(url: str | None) -> str:
    """`foto`-Adresse fuer die Ausgabe mit Betriebs-Praefix (MT-2, MT-2b).

    In der Datenbank steht `/files/…` (Frappe-Erbe, DB wird nicht migriert).
    Der Router praefigiert nur Schluessel namens `file_url`; `foto` ist ein
    anderer Name, das `<img :src="profile.foto">` liefe ohne diese Stelle unter
    `/diakronos` in ein 404. Ohne Praefix unveraendert (Gegenprobe).

    MT-2b: dieselbe Stelle bedient jetzt ALLE Leser von `foto` — Profil,
    GruppeDetail, Organigramm und Adressbuch rufen `foto_mit_praefix` auf
    (ein Praefigierer, `base_path.datei_url`, idempotent). Der Name
    `_datei_mit_praefix` bleibt als Profil-internes Alias bestehen.
    """
    from diakronos_app.base_path import datei_url

    return datei_url(url) if url else ""


def foto_mit_praefix(url: str | None) -> str:
    """Ausgabe-Adresse eines Profilbilds (`foto`) — der EINE Praefigierer.

    MT-2b: `foto` heisst nicht `file_url`, deshalb greift die
    Router-Praefigierung (`frappe_compat.router._praefixierte_datei_urls`)
    hier nicht. Jeder Leser von `api/*.py`, der `foto` ausgibt, ruft diese
    Funktion — keine zweite Praefix-Logik. `base_path.datei_url` ist
    idempotent (schon praefigierte Werte bleiben unveraendert), ein doppelter
    Aufruf kann also nichts kaputt machen. `None` -> `""` (die SPA prueft
    `v-if="foto"`).

    Verteidigung in der Tiefe (Review MT-2b, MITTEL): absolute Adressen
    (`http(s)://`, `//host`, ein Fremdschema wie `javascript:`) gehen
    unveraendert durch — sie sind kein Pfad dieser Installation, werden aber
    von `sichereBildUrl` im Frontend gefiltert und von Altbestand/CDN
    gebraucht. ALLES andere muss dagegen eine Adresse nach
    `_datei_url_muster()` sein (`[/praefix]/files/<name>` bzw.
    `…/private/files/<name>`); fremde relative Werte (`/etc/passwd`,
    `/files/../../…`, `/x/y/files/…`) werden NICHT ausgeliefert, sondern zu
    `""`. Sonst wuerde ein Altbestand, der vor dem Schreibschutz
    (`update_mitglied`) in die Spalte gelangt ist, weiter an alle Betrachter
    gehen.
    """
    wert = str(url or "").strip()
    if not wert:
        return ""
    # Absolute Adresse: kein Pfad dieser Installation — unangetastet (datei_url
    # laesst sie ohnehin stehen, hier nur die Ausnahme von der Pruefung).
    if "://" in wert or wert.startswith("//"):
        return _datei_mit_praefix(wert)
    if _datei_url_muster().fullmatch(wert) is None:
        return ""
    return _datei_mit_praefix(wert)


# ── Profilbild ──────────────────────────────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def update_profile_picture(file_url=None):
    """Setzt die Profilbild-URL des eigenen Profils.

    Quelle: `profile.py:93-98`. Bewusst ein reiner URL-Schreiber: die SPA
    laedt die Datei vorher ueber `upload_file` hoch (P2c) und schickt nur
    die zurueckgegebene `file_url` (`Profile.vue:465-474`).

    B3: Anders als das Original akzeptieren wir keine ungepruefte Client-URL.
    Sie muss eine eigene File-Zeile und eine vorhandene lokale Datei benennen.
    Ein leerer Wert entfernt das Profilbild weiterhin.
    """
    mid = _get_my_mitglied()
    if file_url:
        if not isinstance(file_url, str):
            throw("Nur eigene hochgeladene Dateien sind erlaubt.", FrappePermissionError)
        # A client URL is not proof of ownership; only our own File row is.
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.core import FileModel
        from diakronos_app.files import stored_path

        # MT-2: Unter dem Betriebs-Praefix liefert `upload_file` die Adresse
        # `/diakronos/files/<name>` (WEB-5a), die DB-Zeile traegt weiter
        # `/files/<name>`. Beide Formen muessen denselben Datensatz treffen,
        # sonst schlaegt das Speichern des eigenen Bildes mit 403 fehl.
        # Verglichen wird NIE der Client-String, sondern der Dateiname, und
        # die DB-Zeile muss dem Aufrufer gehoeren — fremde Dateien bleiben 403.
        filename = _dateiname_aus_file_url(file_url)
        if not filename:
            throw("Nur eigene hochgeladene Dateien sind erlaubt.", FrappePermissionError)
            raise AssertionError("unreachable — throw() wirft immer")  # noqa: TRY301
        with SessionLocal() as db:
            file_doc = db.query(FileModel).filter(
                FileModel.file_url.in_([
                    '/files/' + filename, '/private/files/' + filename,
                ]),
                FileModel.owner == session.user,
            ).first()
            if file_doc is None or stored_path(filename) is None:
                throw("Nur eigene hochgeladene Dateien sind erlaubt.", FrappePermissionError)
                raise AssertionError("unreachable — throw() wirft immer")  # noqa: TRY301
        # Gespeichert wird die DB-Form (praefixfrei) — die Ausgabe praefigiert
        # `get_my_profile` ohnehin; eine praefigierte URL in der Spalte waere
        # bei einem Praefix-Wechsel kaputt.
        file_url = file_doc.file_url
    doc = get_doc("Mitglied", mid)
    doc.db_set("foto", file_url or None)
    return {"ok": True}


# ── Alter Sofortlöschpfad ──────────────────────────────────────────────────

@whitelist(methods=["POST"], allow_guest=False)
def delete_my_data():
    """Alte Clients dürfen den neuen Antrags-/Adminweg nicht umgehen."""
    _get_my_mitglied()
    throw("Bitte im Profil einen Löschantrag stellen. Die Gemeindeverwaltung prüft ihn; es werden nicht sofort Daten gelöscht.")
