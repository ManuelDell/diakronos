"""WEB-1 — API des optionalen Website-Moduls (Primo-Anbindung).

Drei Endpunkte, alle ueber den normalen Methoden-Router erreichbar
(`/api/method/<pfad>`, `allow_guest=False` — die Anmeldung prueft der Router
schon):

    diakronos_app.api.website.status             (GET)  -> Zustand der Anbindung
    diakronos_app.api.website.login_uebergabe    (POST) -> Browser-URL mit Token
    diakronos_app.api.website.rollen             (GET)  -> Rollen-Auskunft

Kurzpfade ueber das Register: `website.status`, `website.login_uebergabe`,
`website.rollen`.

S3 — Rollen-Gate
----------------
Zugriff haben NUR `System Manager`, `Administrator` und `Website-Moderator`.
Alle anderen bekommen **403** (`PermissionError` der Compat-Schicht, also
HTTP 403 mit `exc_type=PermissionError`). Die Pruefung steht VOR jedem Aufruf
nach Primo: eine Rolle, die in Diakronos entzogen wird, sperrt den Zugang
sofort — auch wenn in Primo noch ein Konto mit Serverrolle liegt.

CSRF
----
`login_uebergabe` ist ein POST und laeuft damit durch die CSRF-Middleware
(`X-Frappe-CSRF-Token` gegen die Sitzung). Ein Aufruf ohne gueltiges Token
endet mit 417 `CSRFTokenError` — das ist gewollt und wird im Test festgehalten.

Secrets
-------
Der Endpunkt gibt AUSSCHLIESSLICH die Browser-URL zurueck (Token im
Fragment). Superuser-Zugang, Passwoerter und das Superuser-Token bleiben im
Prozess und tauchen in keiner Antwort und keiner Log-Zeile auf.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakronos.api.website"

import logging

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DienstNichtVerfuegbarError,
    DoesNotExistError,
    KonfliktError,
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.session import session
from diakronos_app.website import primo

logger = logging.getLogger("diakronos_app.api.website")

#: Rollen mit Zugriff auf die Website-Funktionen (S3). EINE Wahrheit steht
#: im Adapter (`primo.WEBSITE_ROLLEN`); hier nur der sprechende Alias.
#: `Website-Moderator` steht bewusst NICHT in `VERANTWORTLICHE.ZUGANGS_ROLLEN`
#: (Vergabe bleibt System-Manager-Sache, WEB-1b).
WEBSITE_ROLLEN = primo.WEBSITE_ROLLEN


def _aktuelle_rollen() -> list[str]:
    return list(get_roles())


def _im_thread(fn, *args):
    """Fuehrt einen blockierenden Aufruf in einem eigenen Thread aus.

    Der Methoden-Router ruft Endpunkte SYNCHRON auf (er laeuft im
    Starlette-Threadpool), deshalb ist `async`/`run_in_threadpool` hier kein
    Weg. Ein eigener Thread mit hartem Zeitlimit haelt den Worker trotzdem
    frei: Primo ist ein Fremdsystem, und dessen Zeitlimit
    (`PRIMO_TIMEOUT_SEKUNDEN`) gilt je Aufruf, nicht fuer den ganzen Weg.
    """
    from concurrent.futures import ThreadPoolExecutor

    from diakronos_app.settings import settings

    limit = max(
        5.0,
        float(settings.primo_timeout_sekunden or 5.0) * 4 + 5.0,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fn, *args).result(timeout=limit)


def _require_website_rolle() -> list[str]:
    """Weist alles ab, was keine Website-Rolle hat (403, fail closed)."""
    if session.user in ("", "Guest"):
        throw("Zugriff verweigert.", FrappePermissionError)
    rollen = _aktuelle_rollen()
    if not primo.darf_website(rollen):
        throw(
            "Nur für Systemmanager, Administratoren und Website-Moderatoren.",
            FrappePermissionError,
        )
    return rollen


def _email_des_benutzers() -> str:
    """E-Mail des angemeldeten Benutzers (Konto-Mail, nicht die Mitgliedsmail).

    Primo konten sind an der E-Mail identifiziert (`identityFields: [email]`).
    Ohne Adresse gibt es keinen Zugang — und keine erfundene Ersatzadresse.
    """
    from diakronos_app.frappe_compat.query import get_value

    user = session.user
    email = ""
    try:
        email = str(get_value("User", user, "email") or "").strip()
    except Exception:  # noqa: BLE001 — fehlende Zeile darf nicht 500 ergeben
        email = ""
    if not email:
        email = str(user or "").strip()
    if "@" not in email:
        throw(
            "Dein Benutzerkonto hat keine E-Mail-Adresse für die Website-Anmeldung.",
            FrappePermissionError,
        )
    return email


@whitelist(allow_guest=False)
def status():
    """Zustand der Primo-Anbindung (S2) — nur fuer berechtigte Rollen.

    Rueckgabe:

        {"status": "nicht_konfiguriert" | "nicht_erreichbar" | "verbunden",
         "version": str|null, "site_count": int|null, "url": str|null}

    Wirft nie wegen Primo: ein nicht erreichbarer Server ist der Zustand
    "nicht_erreichbar", keine Ausnahme.
    """
    _require_website_rolle()
    return primo.status()


@whitelist(allow_guest=False)
def rollen():
    """Auskunft fuer die Oberflaeche: darf dieser Benutzer Websites verwalten?

    Rueckgabe: `{"berechtigt": bool, "rollen": [...], "primo_rolle": str|null}`

    `primo_rolle` ist die Primo-Serverrolle, die beim naechsten Login gesetzt
    wird (`developer`/`editor`) — oder `null`, wenn keine Rolle passt.
    """
    _require_website_rolle()
    aktuelle = _aktuelle_rollen()
    return {
        "berechtigt": True,
        "rollen": aktuelle,
        "primo_rolle": primo.primaere_primo_rolle(aktuelle),
    }


@whitelist(methods=["POST"], allow_guest=False)
def login_uebergabe(request=None):
    """Uebergabe in Primo (S4) — gibt die Browser-URL zurueck.

    Rueckgabe: `{"url": "{PRIMO_PUBLIC_URL}/diakronos-sso.html#token=…&record=…"}`

    Ablauf: Rollen-Gate -> Superuser-Login -> Konto **per Zuordnung**
    sicherstellen (WEB-1b) -> Impersonate-Token -> Fragment-URL.

    (B2) NUR POST. Der Endpunkt stellt einen fremden Zugang aus; per GET
    (`<img src="…">`, geteilter Link, Vorabruf durch einen Proxy) waere das
    ohne Willen des Benutzers ausloesbar. Frappe liest Argumente zwar auch aus
    dem Query-String — deshalb steht die Methodenpruefung hier und nicht erst
    im Router, der GET/PUT/PATCH fuer alle Endpunkte offen laesst. Ergebnis
    ist 403 `PermissionError` (Frappe-Konvention fuer "darfst du nicht"), und
    Primo wird dabei NICHT angesprochen.

    Fehlerbilder (bewusst ohne Interna):
      * keine Berechtigung / andere Methode als POST -> 403 `PermissionError`
      * Zuordnung unklar (Adresse schon in Primo, Mail weicht ab, Systemkonto)
        -> 409 `ValidationError`
      * Primo nicht eingerichtet          -> 503 (`DienstNichtVerfuegbarError`)
      * Primo nicht erreichbar/Fehler     -> 503 (`DienstNichtVerfuegbarError`)

    Nach SEC-8 geht der Klassenname nur noch nach Allowlist nach aussen —
    `DienstNichtVerfuegbarError` erscheint dort als `exc_type = "Error"`. Die
    Oberflaeche unterscheidet am **HTTP-Status 503**, nicht am Namen.
    """
    from diakronos_app.frappe_compat.router import _ist_browser_navigation

    if str(getattr(request, "method", "POST") or "POST").upper() != "POST":
        logger.info(
            "Website-Uebergabe per %s abgewiesen (nur POST).",
            getattr(request, "method", "?"),
        )
        if request is not None and _ist_browser_navigation(request):
            # Ein Browser, der die Adresse als Seite aufruft, bekommt die
            # SPA statt rohem JSON — dieselbe Behandlung wie beim Login.
            from starlette.responses import RedirectResponse

            antwort = RedirectResponse("/", status_code=303)
            antwort.headers["Cache-Control"] = "no-store"
            return antwort
        throw(
            "Diese Adresse darf nur per POST aufgerufen werden.",
            FrappePermissionError,
        )

    rollen_liste = _require_website_rolle()
    if primo.primaere_primo_rolle(rollen_liste) is None:
        # Theoretisch unerreichbar: `darf_website` und die Zuordnung teilen
        # sich die Rollenliste. Fail closed statt stillschweigend "editor".
        throw(
            "Für dieses Konto ist in Primo keine Rolle hinterlegt.",
            FrappePermissionError,
        )

    benutzer = str(session.user or "").strip()
    email = _email_des_benutzers()
    try:
        # Synchroner Netz-/DB-Aufruf: in einem eigenen Thread, damit ein
        # langsamer Primo nicht den Worker blockiert.
        url = _im_thread(primo.login_uebergabe, benutzer, email, rollen_liste)
    except primo.PrimoKontoKonflikt as exc:
        # WEB-1b/B1: die Zuordnung ist nicht eindeutig — nichts wurde
        # geaendert. 409, damit die Oberflaeche "Verknuepfung noetig" zeigen
        # kann (ValidationError ist Frappes Standard fuer diesen Status).
        logger.info("Primo-Uebergabe: Zuordnungskonflikt.")
        throw(exc.meldung, KonfliktError)
    except primo.PrimoNichtKonfiguriert:
        # 503: die Anbindung ist nicht eingeschaltet — kein Fehler des
        # Benutzers, sondern eine fehlende Voraussetzung der Installation.
        throw(
            "Die Website-Anbindung (Primo) ist auf dieser Installation nicht eingerichtet.",
            DienstNichtVerfuegbarError,
        )
    except primo.PrimoAbgelehnt as exc:
        # Grund ohne Interna weitergeben: Statuscode + Kurztext von Primo.
        logger.warning("Primo-Uebergabe abgelehnt: HTTP %s", exc.status)
        throw(
            "Die Anmeldung an der Website ist gerade nicht möglich "
            "(Primo hat den Zugang abgelehnt).",
            DienstNichtVerfuegbarError,
        )
    except primo.PrimoNichtErreichbar:
        logger.warning("Primo-Uebergabe: Server nicht erreichbar.")
        throw(
            "Die Website ist gerade nicht erreichbar.",
            DienstNichtVerfuegbarError,
        )
    # B2: das Nachziehen laeuft NACH der Antwort (Hintergrundaufgabe), nicht
    # davor. Zwei Gruende: (1) die Anmeldung wartet nicht auf einen
    # Bibliotheksschreibvorgang, (2) ein Fehler dort kann die bereits
    # zugestellte Uebergabe nicht mehr kippen. Ueber den Methoden-Router
    # (dict-Rueckgabe) geht das nicht — deshalb nimmt der Endpunkt dafuer
    # ausdruecklich den Response-Weg, wenn ein `request` vorliegt.
    return _mit_nachziehen({"url": url}, request)


def _mit_nachziehen(daten: dict, request) -> dict | object:
    """Antwortdaten plus Hintergrundaufgabe „Bausteine nachziehen" (B2).

    Ohne `request` (direkter Python-Aufruf, z. B. im Test) bleibt es bei den
    Daten — der Router verpackt sie wie ueberall. Mit `request` entsteht eine
    JSON-Antwort mit `BackgroundTask`; der Router reicht eine fertige Response
    unveraendert durch. **Der Aufruf darf nie scheitern**; die Aufgabe faengt
    alles (`_bausteine_nachziehen`).
    """
    if request is None:
        return daten
    from starlette.background import BackgroundTask
    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=200,
        content={"message": daten},
        background=BackgroundTask(_bausteine_nachziehen),
        headers={"Cache-Control": "no-store"},
    )


def _bausteine_nachziehen() -> None:
    """BS-2a (B2): Bibliothek nachziehen, wenn sie aelter ist als mitgeliefert.

    Laeuft NACH der fertigen Uebergabe-URL. **Ein Fehler hier darf die
    Anmeldung nicht verhindern** (Kartenvorgabe): jede Ausnahme wird gefangen
    und nur als Typname protokolliert — keine Inhalte, keine Adressen, keine
    Token. Der Stand wird vorher gelesen; nur wenn ``installiert <
    mitgeliefert`` ist, wird ueberhaupt geschrieben (der Normalfall nach dem
    ersten Lauf kostet damit nur den Lesevorgang).

    BS-2a2 (F2): Ist die mitgelieferte Version in DIESEM Prozess bereits
    bestaetigt, entfaellt schon der Lesevorgang — kein Superuser-Auth und kein
    vollstaendiger Bibliotheks-Export bei jedem Login. Der Merker ist reiner
    Speicher (``bausteine.bestaetigte_version``); nach einem Neustart wird neu
    geprueft.
    """
    from diakronos_app.website import bausteine as bibliothek

    try:
        if bibliothek.steht_bereit():
            return
        stand = bibliothek.bibliothek_stand()
        if not stand.erreichbar or not stand.veraltet:
            return
        bibliothek.sync()
        logger.info(
            "Bausteine nachgezogen (%s -> %s).",
            stand.installiert,
            stand.mitgeliefert,
        )
    except Exception as exc:  # noqa: BLE001 — darf den Login NIE verhindern
        logger.info("Bausteine nicht nachgezogen (%s).", type(exc).__name__)


# ═══════════════════════════════════════════════════════════════════════════
# BS-1a — Website-Freigaben (Verwaltung)
#
# Fuenf Endpunkte, alle angemeldet und alle ueber DASSELBE Rollen-Gate wie die
# Primo-Anbindung (`_require_website_rolle`: System Manager, Administrator,
# Website-Moderator — alle anderen 403, Gast 403). Die POST-Endpunkte laufen
# durch die CSRF-Middleware (`X-Frappe-CSRF-Token` gegen die Sitzung; ohne
# gueltiges Token 417) — wie `login_uebergabe`.
#
#   website.freigaben_lesen        (GET)  -> Kalender, Gruppen, Beitragszahl,
#                                            Postfaecher, Kategorien
#   website.freigabe_setzen        (POST) -> art in kalender|gruppe
#   website.beitrag_auf_website    (POST) -> Beitrag auf die Website stellen
#   website.postfach_speichern     (POST) -> Postfach anlegen/aendern
#   website.postfach_loeschen      (POST) -> Postfach entfernen
#   website.kategorie_oeffentlich  (POST) -> Eventkategorie oeffentlich ja/nein
#
# NUR POST (BS-1a2/F2): Die schreibenden Endpunkte pruefen die Methode SELBST
# als erste Anweisung (`_nur_post`) — Frappe liest Argumente auch aus dem
# Query-String, und ein GET traegt keinen Origin, laeuft also nicht durch die
# CSRF-Middleware. `freigaben_lesen` bleibt GET.
#
# WARUM KEIN STANDARDWEG FUER DIE SCHALTER: `kalender_verwaltung.update_kalender`
# und `beitraege.update_beitrag` haben feste Parameterlisten ohne diese Felder;
# die Verwaltungs-SPA ruft sie ausschliesslich mit genau diesen Parametern auf.
# Ein Zusatzparameter waere ein zweiter halber Weg (und im Fall von
# `update_beitrag` ein stiller Verlust, weil die SPA das Feld nie mitschickt).
# Deshalb ein eigener, eng begrenzter Endpunktsatz — er schreibt NUR die
# Freigabe-Felder, kein Titel, keine Farbe, kein Inhalt.
# ═══════════════════════════════════════════════════════════════════════════

#: Frappe-DocType je Freigabe-Art (Anzeigename und Tabelle).
_DOCTYPE = {"kalender": "Kalender", "gruppe": "Gruppe"}
#: Anzeigename der Zeile, wenn das jeweilige Titelfeld leer ist.
_TITELFELD = {"kalender": "calendar_name", "gruppe": "gruppenname"}


def _pruefe(pruefung, wert):
    """Fuehrt eine Regel-Pruefung aus und uebersetzt ihren Fehler nach Frappe.

    Die Regeln in `website/freigaben.py` sind reines Python (`ValueError`/
    `SlugUngueltig`): sie muessen auch ohne HTTP benutzbar sein. Der Endpunkt
    macht daraus `ValidationError` — nur so wird die Verletzung zur
    Antwort mit `exc_type = "ValidationError"` und deutscher Meldung statt zum
    500 (gleiches Muster wie `ocr`/`planrahmen`: Regel im Fachmodul,
    Uebersetzung am Rand). Der Status bleibt Frappes 417 — die SPA und alle
    anderen Endpunkte kennen nur diesen einen Code fuer Eingabefehler.
    """
    from diakronos_app.website.freigaben import SlugUngueltig

    try:
        return pruefung(wert)
    except SlugUngueltig as exc:
        throw(str(exc), ValidationError)


def _ist_wahr(wert) -> bool:
    """Check-Werte aus JSON/Formular streng lesen (``1``/``"true"``/``true``).

    Frappe-uebliche ``0``/``1`` sind erlaubt; alles andere ist ein Fehler und
    wird NICHT still als ``False`` gewertet (ein Tippfehler darf kein
    versehentliches Freigeben auslösen, aber auch keine stille Ablehnung
    erzeugen, die niemand bemerkt).
    """
    if isinstance(wert, bool):
        return wert
    if isinstance(wert, (int, float)) and wert in (0, 1):
        return bool(wert)
    text = str(wert).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    throw("Bitte einen Wahrheitswert angeben (an/aus).", ValidationError)


def _freigaben_sitzung():
    """Sitzung fuer die Verwaltungs-Endpunkte (Request-Sitzung oder eigene)."""
    from diakronos_app.db import sitzung_fuer_lesen

    return sitzung_fuer_lesen()


def _kalender_zeilen() -> list[dict]:
    from diakronos_app.frappe_compat.query import get_all

    return get_all(
        "Kalender",
        fields=[
            "name",
            "calendar_name",
            "website_freigabe",
            "website_slug",
            "website_nur_oeffentliche_kategorien",
        ],
        order_by="calendar_name asc",
    ) or []


def _gruppen_zeilen() -> list[dict]:
    from diakronos_app.frappe_compat.query import get_all

    return get_all(
        "Gruppe",
        fields=["name", "gruppenname", "website_freigabe", "website_slug"],
        order_by="gruppenname asc",
    ) or []


def _kategorie_zeilen() -> list[dict]:
    from diakronos_app.frappe_compat.query import get_all

    return get_all(
        "Eventkategorie",
        fields=["name", "event_category_name", "oeffentlich"],
        order_by="event_category_name asc",
    ) or []


def _slug_frei(slug: str, art: str, ausser: str) -> bool:
    """Ist ``slug`` in derselben Art noch nicht an eine ANDERE Zeile vergeben?"""
    from diakronos_app.frappe_compat.query import get_all

    treffer = get_all(
        _DOCTYPE[art],
        filters={"website_slug": slug},
        fields=["name"],
        limit_page_length=5,
    ) or []
    return all(str(t.get("name")) == ausser for t in treffer)


def _zeile(art: str, name: str) -> dict:
    """Eine Kalender-/Gruppenzeile oder 404 (`DoesNotExistError`)."""
    from diakronos_app.frappe_compat.query import get_value

    schluessel = str(name or "").strip()
    if not schluessel:
        throw("Bitte einen Namen angeben.", ValidationError)
    felder = ["name", _TITELFELD[art], "website_freigabe", "website_slug"]
    if art == "kalender":
        felder.append("website_nur_oeffentliche_kategorien")
    zeile = get_value(_DOCTYPE[art], schluessel, felder, as_dict=True)
    if not zeile:
        throw("Eintrag nicht gefunden.", DoesNotExistError)
    return zeile


def _anzeige(art: str, zeile: dict) -> str:
    return str(zeile.get(_TITELFELD[art]) or zeile.get("name") or "")


def _geliefert(wert) -> bool:
    """Wurde der Parameter ueberhaupt mitgeschickt (nicht ``None``)?"""
    return wert is not None


#: Endpunkte, die ETWAS SCHREIBEN. Frappe liest Argumente auch aus dem
#: Query-String — ein GET taegt aber keinen ``Origin`` und laeuft deshalb
#: nicht durch die CSRF-Middleware: `<img src="/api/method/…freigabe_setzen?
#: name=…&freigabe=1">` oder ein geteilter Link wuerde ohne Willen des
#: Benutzers freigeben (BS-1a2/F2).
_NUR_POST = frozenset(
    {
        "freigabe_setzen",
        "beitrag_auf_website",
        "postfach_speichern",
        "postfach_loeschen",
        "kategorie_oeffentlich",
        # BS-2a: schreibt in Primo (Bibliothek anlegen/aktualisieren).
        "bausteine_installieren",
    }
)


def _nur_post(request):
    """Weist jede Methode ausser POST mit 405 ab — VOR Rollen-Gate und DB.

    SEC-11 (``whitelist(methods=…)``) gibt es im Router dieser App nicht;
    deshalb steht die Pruefung hier, in jedem schreibenden Endpunkt als erste
    Anweisung. Ein Aufruf ohne ``request`` (direkt aus Python, z. B. in einem
    Test) gilt als POST-Aufruf: der Router reicht den Request immer durch.

    Antwort: 405 mit ``Allow: POST`` und ``exc_type = "MethodNotAllowed"``;
    es wird nichts gelesen und nichts geschrieben.
    """
    if request is None:
        return
    methode = str(getattr(request, "method", "POST") or "POST").upper()
    if methode == "POST":
        return
    from starlette.responses import JSONResponse

    logger.info("Website-Verwaltung per %s abgewiesen (nur POST).", methode)
    return JSONResponse(
        status_code=405,
        content={
            "exc_type": "MethodNotAllowed",
            "message": "Diese Adresse darf nur per POST aufgerufen werden.",
        },
        headers={"Allow": "POST", "Cache-Control": "no-store"},
    )


@whitelist(allow_guest=False)
def freigaben_lesen():
    """Stand aller Website-Freigaben (BS-1a) — nur berechtigte Rollen.

    Rueckgabe::

        {"kalender": [{"name", "titel", "freigabe", "slug",
                       "nur_oeffentliche_kategorien"}, …],
         "gruppen":  [{"name", "titel", "freigabe", "slug"}, …],
         "beitraege_anzahl": int,      # Beitraege mit auf_website=1
         "beitraege": [{"name", "titel", "veroeffentlicht"}, …],
         "postfaecher": [{"slug", "bezeichnung", "email", "aktiv"}, …],
         "postfach_fallback": {"aktiv": bool, "bezeichnung": str},
         "kategorien": [{"name", "titel", "oeffentlich"}, …]}

    ``beitraege`` und ``kategorien`` sind Zusaetze fuer die Verwaltung:
    ``beitrag_auf_website`` und ``kategorie_oeffentlich`` brauchen eine
    Auswahlliste, sonst muesste die Oberflaeche raten. Sie enthalten KEINE
    Personendaten (nur Kennung, Titel, Schalter).
    """
    _require_website_rolle()
    from diakronos_app.frappe_compat.query import get_all
    from diakronos_app.settings import settings
    from diakronos_app.website import freigaben as regeln

    sess, eigene = _freigaben_sitzung()
    try:
        beitraege = get_all(
            "Beitrag",
            filters={"auf_website": 1},
            fields=["name", "titel", "veroeffentlicht"],
            order_by="datum desc",
            limit_page_length=500,
            session=sess,
        ) or []
        postfaecher = [p.als_dict() for p in regeln.postfaecher_lesen(sess)]
        oeffentlich = regeln.postfaecher_oeffentlich(
            sess, settings.website_kontakt_empfaenger
        )
    finally:
        if eigene:
            sess.close()

    return {
        "kalender": [
            {
                "name": str(z.get("name")),
                "titel": _anzeige("kalender", z),
                "freigabe": bool(z.get("website_freigabe")),
                "slug": z.get("website_slug") or "",
                "nur_oeffentliche_kategorien": bool(
                    z.get("website_nur_oeffentliche_kategorien")
                ),
            }
            for z in _kalender_zeilen()
        ],
        "gruppen": [
            {
                "name": str(z.get("name")),
                "titel": _anzeige("gruppe", z),
                "freigabe": bool(z.get("website_freigabe")),
                "slug": z.get("website_slug") or "",
            }
            for z in _gruppen_zeilen()
        ],
        "beitraege_anzahl": len(beitraege),
        "beitraege": [
            {
                "name": str(b.get("name")),
                "titel": str(b.get("titel") or ""),
                "veroeffentlicht": bool(b.get("veroeffentlicht")),
            }
            for b in beitraege
        ],
        "postfaecher": postfaecher,
        # Rueckfall (WEB-10): ohne Zeile in der Tabelle gilt
        # WEBSITE_KONTAKT_EMPFAENGER als Postfach „standard“.
        "postfach_fallback": {
            "aktiv": bool(oeffentlich) and not postfaecher,
            "bezeichnung": regeln.POSTFACH_STANDARD_BEZEICHNUNG,
        },
        "kategorien": [
            {
                "name": str(k.get("name")),
                "titel": str(k.get("event_category_name") or k.get("name")),
                "oeffentlich": bool(k.get("oeffentlich")),
            }
            for k in _kategorie_zeilen()
        ],
    }


@whitelist(methods=["POST"], allow_guest=False)
def freigabe_setzen(request=None, art=None, name=None, freigabe=None, slug=None,
                    nur_oeffentliche_kategorien=None):
    """Schaltet die Website-Freigabe eines Kalenders oder einer Gruppe (BS-1a).

    Argumente:
      ``art``    ``"kalender"`` oder ``"gruppe"`` (Pflicht)
      ``name``   Kennung des Eintrags (Pflicht)
      ``freigabe`` an/aus (Pflicht)
      ``slug``   optional; ohne Angabe wird beim FREIGEBEN aus dem
                 Anzeigenamen abgeleitet (bestehender Slug bleibt stehen).
                 Ist der abgeleitete Slug schon vergeben, kommt ``-2``/``-3``
                 … dazu (BS-1a2/F3); ein EINGEGEBENER Slug bleibt ein Konflikt.
      ``nur_oeffentliche_kategorien`` optional, nur ``art="kalender"``

    Rueckgabe: ``{"art", "name", "titel", "freigabe", "slug",
    "nur_oeffentliche_kategorien"}`` (bei Gruppen ohne das letzte Feld).

    Fehler: andere Methode als POST -> 405 (`MethodNotAllowed`, ohne Wirkung,
    BS-1a2/F2); unbekannte Art/unbekannter Eintrag -> 404
    (`DoesNotExistError`); ungueltiger oder bereits verwendeter Slug, falscher
    Wahrheitswert -> 417 (`ValidationError`); ein Wettlauf auf den
    Unique-Index endet ebenfalls in 417 „bereits vergeben“ (BS-1a2/F4).
    Nach SEC-8 geht der Klassenname nur nach Allowlist nach aussen: der Client
    sieht `exc_type = "Error"` und eine deutsche, generische Meldung — Status
    417/404 unterscheidet die Faelle. Es wird NICHTS geschrieben, wenn eine
    Pruefung scheitert.
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    from sqlalchemy.exc import IntegrityError

    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.website import freigaben as regeln

    art_wert = str(art or "").strip().lower()
    if art_wert not in _DOCTYPE:
        throw("Unbekannte Art. Erlaubt sind Kalender und Gruppe.", ValidationError)

    zeile = _zeile(art_wert, name)
    kennung = str(zeile.get("name"))
    an = _ist_wahr(freigabe)

    werte: dict = {"website_freigabe": an}

    # Slug: ausdruecklich gesetzt > bestehender Slug > beim Freigeben ableiten.
    # Ein EINGEGEBENER Slug wird nie umbenannt (Konflikt bleibt Fehler); ein
    # ABGELEITETER weicht auf -2/-3 aus (BS-1a2/F3, zwei gleichnamige Zeilen
    # sind im Bestand normal).
    neuer_slug = None
    if _geliefert(slug) and str(slug).strip():
        neuer_slug = _pruefe(regeln.slug_pruefen, slug)
        if not _slug_frei(neuer_slug, art_wert, kennung):
            throw(
                "Dieser Kürzel ist bereits vergeben. Bitte einen anderen wählen.",
                ValidationError,
            )
    elif an and not str(zeile.get("website_slug") or "").strip():
        neuer_slug = _pruefe(
            lambda text: regeln.slug_verfuegbar(
                regeln.slug_aus_text(text),
                lambda kandidat: not _slug_frei(kandidat, art_wert, kennung),
            ),
            _anzeige(art_wert, zeile),
        )
    if neuer_slug is not None:
        werte["website_slug"] = neuer_slug

    if _geliefert(nur_oeffentliche_kategorien):
        if art_wert != "kalender":
            throw(
                "Die Kategorie-Einschränkung gibt es nur für Kalender.",
                ValidationError,
            )
        werte["website_nur_oeffentliche_kategorien"] = _ist_wahr(
            nur_oeffentliche_kategorien
        )

    try:
        _update_doc(_DOCTYPE[art_wert], kennung, werte)
    except IntegrityError:
        # Wettlauf (BS-1a2/F4): zwei Aufrufe sind an der Vorpruefung
        # vorbeigekommen, der Unique-Index hat den zweiten gestoppt. Dieselbe
        # Meldung und derselbe Status wie bei der Vorpruefung — kein 500 und
        # keine Spur des Indexnamens nach aussen.
        logger.info("Website-Freigabe: Slug im Wettlauf vergeben.")
        throw(
            "Dieser Kürzel ist bereits vergeben. Bitte einen anderen wählen.",
            ValidationError,
        )

    antwort = {
        "art": art_wert,
        "name": kennung,
        "titel": _anzeige(art_wert, zeile),
        "freigabe": an,
        "slug": werte.get("website_slug", zeile.get("website_slug") or ""),
    }
    if art_wert == "kalender":
        antwort["nur_oeffentliche_kategorien"] = bool(
            werte.get(
                "website_nur_oeffentliche_kategorien",
                zeile.get("website_nur_oeffentliche_kategorien"),
            )
        )
    logger.info("Website-Freigabe geändert (%s).", art_wert)
    return antwort


@whitelist(methods=["POST"], allow_guest=False)
def beitrag_auf_website(request=None, name=None, wert=None):
    """Stellt einen Beitrag auf die Website oder nimmt ihn herunter (BS-1a).

    Argumente: ``name`` (Kennung des Beitrags, Pflicht), ``wert`` (an/aus).

    Wirksam oeffentlich ist ein Beitrag nur, wenn ``veroeffentlicht`` UND
    ``auf_website`` gesetzt sind — dieser Endpunkt schaltet ausschliesslich
    ``auf_website``. Rueckgabe: ``{"name", "titel", "auf_website",
    "veroeffentlicht"}``. Ein ``auf_website`` ohne ``veroeffentlicht`` ist
    erlaubt (Vorbereitung), aber wirkungslos.

    Andere Methode als POST -> 405 ohne Wirkung (BS-1a2/F2).
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.frappe_compat.query import get_value

    kennung = str(name or "").strip()
    if not kennung:
        throw("Bitte einen Beitrag angeben.", ValidationError)
    zeile = get_value(
        "Beitrag", kennung, ["name", "titel", "veroeffentlicht", "auf_website"],
        as_dict=True,
    )
    if not zeile:
        throw("Beitrag nicht gefunden.", DoesNotExistError)

    an = _ist_wahr(wert)
    _update_doc("Beitrag", kennung, {"auf_website": an})
    return {
        "name": str(zeile.get("name")),
        "titel": str(zeile.get("titel") or ""),
        "auf_website": an,
        "veroeffentlicht": bool(zeile.get("veroeffentlicht")),
    }


def _email_pruefen(wert) -> str:
    """Empfaengeradresse: genau EIN @, kein Leerzeichen/Steuerzeichen.

    Steuerzeichen heisst: ``ord(c) < 32`` ODER ``0x7f`` (DEL, BS-1a2/F7) —
    DEL ist kein druckbares Zeichen und hat in einer Adresse nichts zu suchen;
    ``str.isspace()`` erkennt es nicht.
    """
    from email.headerregistry import Address

    from diakronos_app.website import freigaben as freigaben_regeln

    text = str(wert or "").strip()
    if not text:
        throw("Bitte eine E-Mail-Adresse angeben.", ValidationError)
    if len(text) > freigaben_regeln.EMAIL_MAX:
        throw("Die E-Mail-Adresse ist zu lang.", ValidationError)
    fehler = "Bitte eine gültige E-Mail-Adresse angeben."
    if "@" not in text or any(
        c.isspace() or ord(c) < 32 or ord(c) == 0x7F for c in text
    ):
        throw(fehler, ValidationError)
    try:
        parsed = Address(addr_spec=text)
    except Exception:  # noqa: BLE001 — jede Unpuenktlichkeit ist eine Meldung
        throw(fehler, ValidationError)
    if not parsed.username or not parsed.domain or "." not in parsed.domain:
        throw(fehler, ValidationError)
    return text


def _bezeichnung_pruefen(wert) -> str:
    """Anzeigename des Postfachs: Pflicht, hoechstens BEZEICHNUNG_MAX Zeichen."""
    from diakronos_app.website import freigaben as freigaben_regeln

    text = str(wert or "").strip()
    if not text:
        throw("Bitte eine Bezeichnung angeben.", ValidationError)
    if len(text) > freigaben_regeln.BEZEICHNUNG_MAX:
        throw(
            "Die Bezeichnung ist zu lang (höchstens "
            f"{freigaben_regeln.BEZEICHNUNG_MAX} Zeichen).",
            ValidationError,
        )
    return text


@whitelist(methods=["POST"], allow_guest=False)
def postfach_speichern(request=None, slug=None, bezeichnung=None, email=None,
                       aktiv=None, sortierung=None):
    """Legt ein Kontakt-Postfach an oder aendert es (BS-1a).

    Argumente: ``slug`` (Pflicht, ``[a-z0-9-]``, nicht reserviert),
    ``bezeichnung`` und ``email`` (Pflicht), ``aktiv`` (Default an),
    ``sortierung`` (Default: hinter das letzte Postfach).

    ``sortierung`` wird VOR beiden Zweigen geprueft (BS-1a2/F5): ein
    unbrauchbarer Wert legt kein Postfach an und aendert kein bestehendes.

    Rueckgabe: ``{"postfaecher": [...], "postfach": {...}}`` — die ganze
    Liste, damit die Oberflaeche nicht nachladen muss.

    Anmerkung: ``standard`` ist reserviert (Rueckfall-Postfach WEB-10, siehe
    ``website/freigaben.py``) und wird auch hier abgelehnt. Andere Methode als
    POST -> 405 ohne Wirkung (BS-1a2/F2).
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    from sqlalchemy import func, select

    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach
    from diakronos_app.website import freigaben as regeln

    schluessel = _pruefe(regeln.slug_pruefen, slug)
    name_wert = _bezeichnung_pruefen(bezeichnung)
    adresse = _email_pruefen(email)
    wert_sortierung = None
    if _geliefert(sortierung) and str(sortierung).strip():
        try:
            wert_sortierung = int(str(sortierung).strip())
        except (TypeError, ValueError):
            throw("Die Sortierung muss eine Zahl sein.", ValidationError)
    elif _geliefert(sortierung):
        # Ein leerer Wert ist „nicht gesetzt“ (Formularfeld leer gelassen).
        wert_sortierung = None

    sess, eigene = _freigaben_sitzung()
    try:
        zeile = sess.get(WebsiteKontaktPostfach, schluessel)
        if zeile is None:
            hoechste = sess.execute(
                select(func.max(WebsiteKontaktPostfach.sortierung))
            ).scalar()
            zeile = WebsiteKontaktPostfach(
                slug=schluessel,
                bezeichnung=name_wert,
                email=adresse,
                aktiv=True if aktiv is None else _ist_wahr(aktiv),
                sortierung=wert_sortierung
                if wert_sortierung is not None
                else int(hoechste or 0) + 10,
            )
            sess.add(zeile)
        else:
            zeile.bezeichnung = name_wert
            zeile.email = adresse
            if _geliefert(aktiv):
                zeile.aktiv = _ist_wahr(aktiv)
            if wert_sortierung is not None:
                zeile.sortierung = wert_sortierung
        sess.commit()
        postfaecher = [p.als_dict() for p in regeln.postfaecher_lesen(sess)]
    except Exception:
        sess.rollback()
        raise
    finally:
        if eigene:
            sess.close()

    return {
        "postfach": next(p for p in postfaecher if p["slug"] == schluessel),
        "postfaecher": postfaecher,
    }


@whitelist(methods=["POST"], allow_guest=False)
def postfach_loeschen(request=None, slug=None):
    """Entfernt ein Kontakt-Postfach (BS-1a). Rueckgabe: die verbleibende Liste.

    Ein unbekannter Slug ist ein 404 (`DoesNotExistError`) — kein stiller
    Erfolg, sonst bemerkt niemand einen Tippfehler. Wird die LETZTE Zeile
    entfernt, gilt wieder der Rueckfall auf ``WEBSITE_KONTAKT_EMPFAENGER``
    (WEB-10). Andere Methode als POST -> 405 ohne Wirkung (BS-1a2/F2).
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach
    from diakronos_app.website import freigaben as regeln

    schluessel = str(slug or "").strip()
    if not schluessel:
        throw("Bitte ein Postfach angeben.", ValidationError)

    sess, eigene = _freigaben_sitzung()
    try:
        zeile = sess.get(WebsiteKontaktPostfach, schluessel)
        if zeile is None:
            throw("Postfach nicht gefunden.", DoesNotExistError)
        sess.delete(zeile)
        sess.commit()
        postfaecher = [p.als_dict() for p in regeln.postfaecher_lesen(sess)]
    except Exception:
        sess.rollback()
        raise
    finally:
        if eigene:
            sess.close()

    logger.info("Kontakt-Postfach entfernt.")
    return {"postfaecher": postfaecher}


@whitelist(methods=["POST"], allow_guest=False)
def kategorie_oeffentlich(request=None, name=None, wert=None):
    """Setzt ``Eventkategorie.oeffentlich`` (BS-1a).

    Die Eventkategorie ist die EINE Stelle, an der „diese Terminart darf
    oeffentlich erscheinen“ steht; ein Kalender kann mit
    ``nur_oeffentliche_kategorien`` darauf einschraenken. Es gibt bisher
    keine Kategorienpflege in der Oberflaeche (per grep geprueft: kein
    Endpunkt schreibt ``Eventkategorie``), deshalb dieser eigene Endpunkt.

    Rueckgabe: ``{"name", "titel", "oeffentlich"}``. Andere Methode als POST
    -> 405 ohne Wirkung (BS-1a2/F2).
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    from diakronos_app.frappe_compat.api_helpers import _update_doc
    from diakronos_app.frappe_compat.query import get_value

    kennung = str(name or "").strip()
    if not kennung:
        throw("Bitte eine Kategorie angeben.", ValidationError)
    zeile = get_value(
        "Eventkategorie", kennung, ["name", "event_category_name", "oeffentlich"],
        as_dict=True,
    )
    if not zeile:
        throw("Kategorie nicht gefunden.", DoesNotExistError)

    an = _ist_wahr(wert)
    _update_doc("Eventkategorie", kennung, {"oeffentlich": an})
    return {
        "name": str(zeile.get("name")),
        "titel": str(zeile.get("event_category_name") or zeile.get("name")),
        "oeffentlich": an,
    }


# ═══════════════════════════════════════════════════════════════════════════
# BS-2a — Baustein-Bibliothek (Verwaltung)
#
#   website.bausteine_status        (GET)  -> {mitgeliefert_version,
#                                              installiert_version, bausteine:[…]}
#   website.bausteine_installieren  (POST) -> Bibliothek in Primo einspielen
#
# Rollen wie BS-1a (`_require_website_rolle`: System Manager, Administrator,
# Website-Moderator). `bausteine_installieren` ist in `_NUR_POST` eingetragen
# und prueft die Methode als erste Anweisung — Frappe liest Argumente auch aus
# dem Query-String, und ein GET traegt keinen Origin (also keine CSRF-Pruefung).
#
# Der Stand kommt aus Primo selbst (Blocknamen samt Versionsvermerk, BS-0 F2b:
# Primo hat keine Versionierung) — es gibt bewusst KEINE neue Tabelle und
# damit keine Migration fuer BS-2a.
# ═══════════════════════════════════════════════════════════════════════════


@whitelist(allow_guest=False)
def bausteine_status():
    """Stand der Baustein-Bibliothek (BS-2a).

    Rueckgabe::

        {"erreichbar": bool,
         "mitgeliefert_version": int,   # was Diakronos mitbringt
         "installiert_version": int,    # was in Primo liegt (0 = keine)
         "veraltet": bool,              # installiert < mitgeliefert
         "revision": str,               # Revisionskopf des Bibliotheks-Exports
         "hinweis": str,                # Klartext, wenn nicht abrufbar
         "bausteine": [{"kennung", "name", "version"}, …]}

    Wirft nie wegen Primo: ein nicht erreichbares oder nicht berechtigtes
    Primo ist der Zustand ``erreichbar = false`` mit einem Hinweis, keine 500.
    """
    _require_website_rolle()
    from diakronos_app.website import bausteine as bibliothek

    return bibliothek.bibliothek_stand().als_dict()


@whitelist(methods=["POST"], allow_guest=False)
def bausteine_installieren(request=None):
    """Spielt die mitgelieferte Bibliothek in Primo ein (BS-2a, B2).

    Idempotent: Blockname ist ``diakronos/<kennung>@v<version>``; ein zweiter
    Lauf derselben Version aendert nichts (Primo fuehrt ueber den Namen
    zusammen, im Wegwerf-Primo belegt).

    **Bereits in Primo-Sites eingesetzte Kopien werden NICHT angefasst.** Primo
    kopiert einen Bibliotheksblock beim Einsetzen; die Kopie gehoert danach dem
    Redakteur. Das ist Absicht (BS-0 F2c): eine automatische Uebernahme
    wuerde jede Anpassung ueberschreiben.

    Rueckgabe: ``{"version": int, "bausteine": [kennung, …], "revision": str,
    "weg": "zip"|"einzeln"}``.

    Fehler (ohne Interna):
      * andere Methode als POST      -> 405 (`MethodNotAllowed`, ohne Wirkung)
      * Primo nicht eingerichtet     -> 503 (`DienstNichtVerfuegbarError`)
      * Primo lehnt ab / nicht da    -> 503, Protokoll nur mit Statuscode
      * Quellen unvollstaendig       -> 500 (Auslieferungsfehler, Build)
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    # BS-2a2: `Error` heisst in der Compat-Schicht `FrappeCompatError` — der
    # alte Import scheiterte beim ERSTEN Fehlerfall mit ImportError und die
    # Antwort war ein 500 mit Interna statt der generischen Meldung.
    from diakronos_app.frappe_compat.exceptions import FrappeCompatError
    from diakronos_app.website import bausteine as bibliothek
    from diakronos_app.website import primo as primo_adapter

    try:
        ergebnis = _im_thread(bibliothek.sync)
    except primo_adapter.PrimoNichtKonfiguriert:
        throw(
            "Die Website-Anbindung (Primo) ist auf dieser Installation nicht eingerichtet.",
            DienstNichtVerfuegbarError,
        )
    except bibliothek.BausteinQuelleFehler:
        # Ein Fehler der AUSLIEFERUNG (Datei fehlt/ist unbrauchbar), nicht des
        # Benutzers. Der Betrieb sieht ihn im Log, der Client nur den Status.
        logger.error("Bausteine: mitgelieferte Quellen unbrauchbar.")
        throw(
            "Die mitgelieferten Bausteine sind unvollständig. Bitte den Support informieren.",
            FrappeCompatError,
        )
    except bibliothek.PrimoSyncAbgelehnt as exc:
        logger.warning("Bausteine: Primo hat den Import abgelehnt (HTTP %s).", exc.status)
        throw(
            "Die Bausteine konnten nicht in die Website übernommen werden "
            "(die Website hat den Zugriff abgelehnt).",
            DienstNichtVerfuegbarError,
        )
    except Exception as exc:  # noqa: BLE001 — Fremdsystem: nie 500 mit Interna
        logger.warning("Bausteine: Einspielen fehlgeschlagen (%s).", type(exc).__name__)
        throw(
            "Die Bausteine konnten gerade nicht übernommen werden.",
            DienstNichtVerfuegbarError,
        )
    return ergebnis.als_dict()
