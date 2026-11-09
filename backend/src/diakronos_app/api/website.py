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


def _im_thread(fn, *args, limit: float | None = None):
    """Fuehrt einen blockierenden Aufruf in einem eigenen Thread aus.

    Der Methoden-Router ruft Endpunkte SYNCHRON auf (er laeuft im
    Starlette-Threadpool), deshalb ist `async`/`run_in_threadpool` hier kein
    Weg. Ein eigener Thread mit hartem Zeitlimit haelt den Worker trotzdem
    frei: Primo ist ein Fremdsystem, und dessen Zeitlimit
    (`PRIMO_TIMEOUT_SEKUNDEN`) gilt je Aufruf, nicht fuer den ganzen Weg.

    `limit` ueberschreibt die Vorgabe — der schreibende Bibliotheks-Import
    braucht mehr als die vierfache Lesezeit (siehe
    `bausteine.import_timeout_sekunden`). Nach Ablauf wird der Thread NICHT
    abgewartet (`shutdown(wait=False)`): sonst haenge die Anfrage trotz
    Zeitlimit, bis der Schreibvorgang von selbst endet (BS-2d3-Nacharbeit).
    """
    from concurrent.futures import ThreadPoolExecutor

    from diakronos_app.settings import settings

    grenze = limit if limit is not None else max(
        5.0,
        float(settings.primo_timeout_sekunden or 5.0) * 4 + 5.0,
    )
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn, *args).result(timeout=grenze)
    finally:
        pool.shutdown(wait=False)


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
            "Für dieses Konto ist im Website-Baukasten keine Rolle hinterlegt.",
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
            "Die Anbindung an den Website-Baukasten ist auf dieser Installation "
            "nicht eingerichtet.",
            DienstNichtVerfuegbarError,
        )
    except primo.PrimoAbgelehnt as exc:
        # Grund ohne Interna weitergeben: Statuscode + Kurztext von Primo.
        logger.warning("Primo-Uebergabe abgelehnt: HTTP %s", exc.status)
        throw(
            "Die Anmeldung an der Website ist gerade nicht möglich "
            "(der Website-Baukasten hat den Zugang abgelehnt).",
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
        # UX2b2 (F3): die Freigabeliste zeigt keine geloeschte Gruppe an —
        # sonst liesse sich eine Freigabe fuer etwas setzen, das es nicht mehr
        # gibt (und der Slug bliebe auf der Website belegt).
        filters=[["geloescht_am", "is", "not set"]],
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
            # UX2b2 (F3): die Beitrags-Freigabeliste ohne Papierkorb.
            filters={"auf_website": 1, "geloescht_am": ["is", "not set"]},
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
    from diakronos_app.settings import settings
    from diakronos_app.website import bausteine as bibliothek
    from diakronos_app.website import primo as primo_adapter

    # Grenze der Anfrage aus dem Schreib-Budget ableiten (BS-2d3-Nacharbeit):
    # die Vorgabe `primo_timeout * 4 + 5` (= 25 s) lag UNTER dem Budget des
    # Imports (30 s+) und haette den Schreibvorgang abgeschnitten, obwohl er
    # noch lief. Dazu je ein Lese-Timeout fuer Revision und Antwort.
    grenze = (
        bibliothek.import_timeout_sekunden()
        + 2.0 * float(settings.primo_timeout_sekunden or 5.0)
        + 5.0
    )
    try:
        ergebnis = _im_thread(bibliothek.sync, limit=grenze)
    except TimeoutError:
        # Die Zeit ist hier wirklich um: kein Internum, aber ehrlich.
        logger.warning("Bausteine: Einspielen nach %.0f s abgebrochen (Zeitlimit).", grenze)
        throw(
            "Das Einspielen hat zu lange gedauert und wurde beendet. "
            "Bitte erneut versuchen — die Bausteine können bereits übernommen sein.",
            DienstNichtVerfuegbarError,
        )
    except primo_adapter.PrimoNichtKonfiguriert:
        throw(
            "Die Anbindung an den Website-Baukasten ist auf dieser Installation "
            "nicht eingerichtet.",
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


# ═══════════════════════════════════════════════════════════════════════════
# BS-3a — Einwilligung der Person selbst + Auswahl der Ansprechpartner-Bereiche
#
# ZWEI verschiedene Zuständigkeiten, bewusst getrennt (Kartenvorgabe P1/P2):
#
#   website.meine_einwilligung_lesen   (GET)  — die PERSON selbst
#   website.meine_einwilligung_setzen  (POST) — die PERSON selbst (CSRF)
#   website.ansprechpartner_bereiche_lesen  (GET)  — Verwaltung (Rollen BS-1a)
#   website.ansprechpartner_bereiche_setzen (POST) — Verwaltung (CSRF)
#
# WARUM DIE TRENNUNG SO HART IST
# ------------------------------
# Eine Einwilligung, die ein Administrator setzen kann, ist keine Einwilligung
# (Art. 4 Nr. 11, Art. 7 DSGVO). Deshalb taucht KEIN Einwilligungsfeld in der
# Parameterliste eines Verwaltungs-Endpunkts auf — auch nicht als Zusatz zu
# `freigabe_setzen`. Die Verwaltung entscheidet nur, WELCHE Funktionen
# erscheinen dürfen; ob eine Person erscheint, entscheidet sie selbst.
#
# Das Rollen-Gate der Einwilligungs-Endpunkte ist „angemeldet und ein eigenes
# Mitglied" — NICHT `_require_website_rolle()`: die Website-Rolle darf man
# nicht verlangen, sonst könnten normale Mitglieder nicht zustimmen.
# ═══════════════════════════════════════════════════════════════════════════

#: Frappe-üblich: Argumente, die ein Verwaltungs-Endpunkt NIE annimmt.
EINWILLIGUNGS_FELDER = (
    "website_einwilligung",
    "website_einwilligung_am",
    "website_einwilligung_foto",
    "website_anzeigename",
)


def _eigenes_mitglied() -> str:
    """Mitglied-Kennung des angemeldeten Benutzers — oder 417/403.

    Es wird KEINE zweite Zuordnungslogik gebaut: `profile._get_my_mitglied`
    ist die eine Stelle, an der „Benutzer -> Mitglied" entschieden wird
    (zwei Stufen, Mehrdeutigkeit ist ein Fehler). Ein Gast bekommt 403, ein
    angemeldetes Konto ohne Mitglied die deutsche Meldung aus `profile`
    (417, wie das Profil selbst — die SPA zeigt sie unverändert an).
    """
    if session.user in ("", "Guest"):
        throw("Nicht angemeldet", FrappePermissionError)
    from diakronos_app.api.profile import _get_my_mitglied

    return _get_my_mitglied()


def _einwilligung_stand(mid: str) -> dict:
    """Der Einwilligungsstand EINER Person (nur an sie selbst)."""
    from diakronos_app.frappe_compat.api_helpers import get_doc
    from diakronos_app.website import einwilligung as regel

    doc = get_doc("Mitglied", mid)
    return {
        "website_einwilligung": bool(doc.get("website_einwilligung") or False),
        "website_einwilligung_am": regel.zeitstempel(doc.get("website_einwilligung_am")),
        # Die Foto-Zustimmung ist ohne die Einwilligung wirkungslos; sie wird
        # trotzdem roh angezeigt (die Person sieht, was gespeichert ist) —
        # die Anzeige der SPA darf daraus keinen „aktiv"-Eindruck ableiten,
        # dafür steht `foto_erlaubt` daneben.
        "website_einwilligung_foto": bool(doc.get("website_einwilligung_foto") or False),
        "website_anzeigename": str(doc.get("website_anzeigename") or ""),
        "foto_erlaubt": regel.foto_erlaubt(doc),
        "oeffentlich": regel.ist_oeffentlich(doc),
    }


@whitelist(allow_guest=False)
def meine_einwilligung_lesen():
    """Stand der EIGENEN Website-Einwilligung (BS-3a, P1).

    Rueckgabe::

        {"website_einwilligung": bool,
         "website_einwilligung_am": "2026-11-08 10:12:33" | null,
         "website_einwilligung_foto": bool,
         "website_anzeigename": str,
         "foto_erlaubt": bool,      # Einwilligung UND Foto-Zustimmung
         "oeffentlich": bool}       # erscheint gerade als Ansprechpartner

    Keine fremden Daten: die Funktion liest ausschliesslich das Mitglied des
    angemeldeten Benutzers. Ein Administrator bekommt hier SEINEN eigenen
    Stand, nicht den eines anderen — es gibt keinen Parameter dafür.
    """
    return _einwilligung_stand(_eigenes_mitglied())


@whitelist(methods=["POST"], allow_guest=False)
def meine_einwilligung_setzen(request=None, einwilligung=None, foto=None,
                            anzeigename=None):
    """Setzt die EIGENE Website-Einwilligung (BS-3a, P1) — nur die Person selbst.

    Argumente (jedes optional — nur was mitgeschickt wird, ändert sich):

      ``einwilligung``  true/false; true setzt ``website_einwilligung`` UND den
                        Zeitstempel, false ist der WIDERRUF und löscht den
                        Zeitstempel (die Person erscheint sofort nicht mehr).
      ``foto``          true/false — eigene Zustimmung zum Bild. Wird ohne
                        bestehende Einwilligung abgelehnt (417): eine
                        Foto-Zustimmung ohne Namens-Zustimmung wäre ein
                        Schalter ohne Wirkung.
      ``anzeigename``    z. B. nur der Vorname. Leerer Wert löscht ihn
                        (dann gilt der volle Name). Höchstens 140 Zeichen.

    Der Widerruf wirkt SOFORT: die öffentliche Ausgabe liest die Schalter bei
    jeder Anfrage, es gibt keinen Zwischenspeicher.

    DSGVO: jede Änderung erzeugt einen Eintrag in ``DSGVO Einwilligung``
    (``log_einwilligung``, typ ``website``) — er überlebt eine spätere
    Datenlöschung, weil er nur die technische Kennung nennt.

    Fehler: andere Methode als POST -> 405; nicht angemeldet -> 403;
    unbrauchbarer Anzeigename/kein Wahrheitswert -> 417 mit deutscher
    Meldung; ohne eigenes Mitglied -> 417 (Meldung aus ``profile``).
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    mid = _eigenes_mitglied()

    from diakronos_app.api.dsgvo_log import log_einwilligung
    from diakronos_app.frappe_compat.api_helpers import get_doc
    from diakronos_app.website import einwilligung as regel

    doc = get_doc("Mitglied", mid)

    def _wahr(wert) -> bool:
        return _ist_wahr(wert)

    werte: dict = {}
    if _geliefert(einwilligung):
        an = _wahr(einwilligung)
        werte["website_einwilligung"] = an
        if an:
            from diakronos_app.frappe_compat.api_helpers import _now

            werte["website_einwilligung_am"] = _now()
        else:
            # Widerruf: kein Datum stehen lassen (ein Datum ohne Einwilligung
            # wäre ein Nachweis für etwas, das nicht mehr gilt). Wiederrufen
            # wird auch die Foto-Zustimmung: sie war Teil derselben Sache.
            werte["website_einwilligung_am"] = None
            werte["website_einwilligung_foto"] = False
    if _geliefert(foto):
        an_foto = _wahr(foto)
        if an_foto:
            neu = werte.get("website_einwilligung", bool(doc.get("website_einwilligung")))
            if not neu:
                throw(
                    "Ohne Einwilligung zur Nennung des Namens gibt es kein Foto."
                    " Bitte zuerst der Nennung zustimmen.",
                    ValidationError,
                )
        werte["website_einwilligung_foto"] = an_foto
    if _geliefert(anzeigename):
        try:
            werte["website_anzeigename"] = regel.anzeigename_pruefen(anzeigename)
        except ValueError as exc:
            throw(str(exc), ValidationError)

    if not werte:
        throw(
            "Es wurde nichts zum Ändern angegeben.",
            ValidationError,
        )

    # `db_set` statt `save()`: derselbe Weg wie `profile.update_einwilligung`
    # — kein zweiter Schreibpfad, der an einer Policy hängen bleibt.
    #
    # BS-3a (Datenschutz-Review, KRITISCH 1): `db_set` läuft seit der
    # Nacharbeit durch `_pruefe_mitglied_schreibzugriff` — und die lehnt
    # Einwilligungsfelder ab, ausser das Zeitfenster dieser Funktion steht
    # offen. Genau das ist gewollt: DIESE Funktion ist der einzige Weg, auf
    # dem eine Einwilligung entstehen oder enden kann. Das Fenster nennt
    # ausdrücklich nur die Felder, die hier wirklich geschrieben werden.
    with regel.zustimmungs_fenster(tuple(werte)):
        for feld, wert in werte.items():
            doc.db_set(feld, wert)

    if "website_einwilligung" in werte:
        log_einwilligung(
            mid,
            "website",
            "erteilt" if werte["website_einwilligung"] else "widerrufen",
        )
    # Review BS-3a (Punkt 9) + NACHTRAG 2 (MITTEL 3): je geändertem Feld
    # GENAU EIN Eintrag — keine `elif`-Kette. Die Kette protokollierte in
    # „einwilligung=true, foto=false“ das Foto nicht, warf es im Widerruf
    # aber mit hinein (der Widerruf setzt `website_einwilligung_foto` selbst
    # auf False); und ein Aufruf mit allen drei Feldern erzeugte für den
    # Anzeigenamen zwei Einträge. Jetzt steht jedes Feld für sich:
    #
    #   website_einwilligung   -> typ "website"            erteilt/widerrufen
    #   website_einwilligung_foto -> typ "website_foto"    erteilt/widerrufen
    #   website_anzeigename    -> typ "website_anzeigename" gesetzt/entfernt
    #
    # Der Widerruf der Namens-Einwilligung zählt bewusst als FOTO-Widerruf
    # mit: er setzt die Foto-Zustimmung zurück, sonst bliebe im Protokoll
    # eine Zustimmung stehen, die nicht mehr gilt (Art. 7 Abs. 1 DSGVO).
    if werte.get("website_einwilligung_foto") is not None:
        log_einwilligung(
            mid,
            "website_foto",
            "erteilt" if werte["website_einwilligung_foto"] else "widerrufen",
        )
    if "website_anzeigename" in werte:
        log_einwilligung(
            mid,
            "website_anzeigename",
            "gesetzt" if werte["website_anzeigename"] else "entfernt",
        )

    return _einwilligung_stand(mid)


#: Arten eines Ansprechpartner-Bereichs — die zwei Knotenarten des
#: Organigramms (`api/orgchart_api`: Dienstbereich, Gruppe).
BEREICH_ARTEN = ("dienstbereich", "gruppe")


def _bereich_oeffentlich(zeile) -> dict:
    """Eine gespeicherte Auswahlzeile für die Verwaltung (nur Verwaltungsfelder)."""
    return {
        "art": zeile.art,
        "funktion": zeile.funktion,
        "bezeichnung": zeile.bezeichnung or "",
        "postfach": zeile.postfach or "",
        "sortierung": int(zeile.sortierung or 0),
    }


def _bereiche_sitzung():
    """DB-Sitzung für die Auswahl der Bereiche — ``(session, eigene)``.

    Über das MODUL gelesen, nicht über eine frühere Bindung: ``patched_db``
    (Tests) ersetzt ``SessionLocal`` — eine eingefrorene Bindung ginge daran
    vorbei und fasste die echte ``database_url`` an.
    """
    from diakronos_app import db as dbmod

    return dbmod.sitzung_fuer_lesen()


def _auswahl_lesen() -> list[dict]:
    from sqlalchemy import select

    from diakronos_app.models.website_ansprechpartner import WebsiteAnsprechpartner

    sess, eigene = _bereiche_sitzung()
    try:
        zeilen = sess.execute(
            select(WebsiteAnsprechpartner).order_by(
                WebsiteAnsprechpartner.sortierung, WebsiteAnsprechpartner.funktion
            )
        ).scalars().all()
        return [_bereich_oeffentlich(z) for z in zeilen]
    finally:
        if eigene:
            sess.close()


def _funktionskatalog() -> dict[str, dict[str, dict]]:
    """Alle auswählbaren Funktionen/Positionen je Art (aus dem Organigramm).

    ``{"dienstbereich": {name: {bezeichnung}}, "gruppe": {name: {bezeichnung}}}``
    — gelesen aus DENSELBEN Tabellen, die das Organigramm zeigt
    (``api/orgchart_api``): ``dienstbereich`` und ``gruppe`` (nur aktive,
    nicht gelöschte Gruppen — dieselbe Regel wie dort).
    """
    from diakronos_app.frappe_compat.query import get_all

    bereiche: dict[str, dict[str, dict]] = {"dienstbereich": {}, "gruppe": {}}
    for zeile in get_all(
        "Dienstbereich",
        fields=["name", "ministry", "sortierung"],
        order_by="sortierung asc, ministry asc",
    ) or []:
        bereiche["dienstbereich"][str(zeile.get("name"))] = {
            "bezeichnung": str(zeile.get("ministry") or zeile.get("name") or "")
        }
    for zeile in get_all(
        "Gruppe",
        filters={"status": "Aktiv", "geloescht_am": ["is", "not set"]},
        fields=["name", "gruppenname"],
        order_by="gruppenname asc",
    ) or []:
        bereiche["gruppe"][str(zeile.get("name"))] = {
            "bezeichnung": str(zeile.get("gruppenname") or zeile.get("name") or "")
        }
    return bereiche


@whitelist(allow_guest=False)
def ansprechpartner_bereiche_lesen():
    """Auswahl der Ansprechpartner-Bereiche (BS-3a, P2) — nur Verwaltung.

    Rueckgabe::

        {"bereiche": [{"art", "funktion", "bezeichnung", "postfach",
                       "sortierung"}, …],
         "auswahl": {"dienstbereich": [{"funktion", "bezeichnung"}, …],
                     "gruppe": [{"funktion", "bezeichnung"}, …]},
         "postfaecher": [{"slug", "bezeichnung"}, …]}

    ``bereiche`` ist die gespeicherte Auswahl, ``auswahl`` der Katalog der
    möglichen Funktionen (Organigramm), ``postfaecher`` die aktiven
    Postfach-Slugs aus BS-1a (nur Slug und Bezeichnung — keine Adresse).

    Enthält KEINE Einwilligung und KEINE Personendaten: wer eine Funktion
    ausfüllt, steht in der Mitgliederverwaltung, und ob diese Person erscheint,
    entscheidet allein ihre eigene Einwilligung.
    """
    _require_website_rolle()
    from sqlalchemy import select

    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach
    from diakronos_app.settings import settings
    from diakronos_app.website import freigaben as regeln

    katalog = _funktionskatalog()
    sess, eigene = _bereiche_sitzung()
    try:
        zeilen = sess.execute(
            select(WebsiteKontaktPostfach)
            .where(WebsiteKontaktPostfach.aktiv.is_(True))
            .order_by(WebsiteKontaktPostfach.sortierung, WebsiteKontaktPostfach.slug)
        ).scalars().all()
        postfaecher = [
            {"slug": z.slug, "bezeichnung": z.bezeichnung} for z in zeilen
        ]
        if not postfaecher:
            # WEB-10-Rückfall wie im Kontaktformular: ohne Zeile gilt die
            # Einstellung als Postfach „standard" (nur der Slug wird gezeigt).
            postfaecher = [
                {"slug": p.slug, "bezeichnung": p.bezeichnung}
                for p in regeln.postfaecher_oeffentlich(
                    sess, settings.website_kontakt_empfaenger
                )
            ]
    finally:
        if eigene:
            sess.close()

    return {
        "bereiche": _auswahl_lesen(),
        "auswahl": {
            art: [
                {"funktion": name, "bezeichnung": wert["bezeichnung"]}
                for name, wert in sorted(eintraege.items(),
                                        key=lambda e: (e[1]["bezeichnung"].lower(), e[0]))
            ]
            for art, eintraege in katalog.items()
        },
        "postfaecher": postfaecher,
        "einwilligungen_verwaltbar": False,
    }


@whitelist(methods=["POST"], allow_guest=False)
def ansprechpartner_bereiche_setzen(request=None, bereiche=None, **kwargs):
    """Setzt die Auswahl der Ansprechpartner-Bereiche (BS-3a, P2) — Verwaltung.

    ``bereiche`` ist die VOLLE Liste (JSON-String oder Liste), jeder Eintrag::

        {"art": "dienstbereich"|"gruppe",
         "funktion": "<Kennung aus dem Organigramm>",
         "bezeichnung": "<optional, leer = Anzeigename des Datensatzes>",
         "postfach": "<Slug aus BS-1a oder leer>",
         "sortierung": <optional, Zahl; ohne Angabe die Listenposition>}

    Ersetzt die Auswahl vollständig („delete-and-replace", dieselbe
    Entscheidung wie bei den Kalender-Importen). Eine leere Liste schaltet
    die Ausgabe ab.

    **Eine Einwilligung nimmt dieser Endpunkt NICHT an.** Frappe reicht bei
    einer Funktion mit ``**kwargs`` ALLE Request-Argumente durch — deshalb
    gibt es den Sammler hier: er ist die Stelle, an der ein mitgeschicktes
    Einwilligungsfeld ERKANNT und mit 403 abgelehnt wird, statt still
    verworfen zu werden (Kartenvorgabe P1, Test „Admin kann Einwilligung
    NICHT setzen"). Unbekannte andere Argumente werden ignoriert.

    Fehler: andere Methode als POST -> 405; keine Website-Rolle -> 403;
    Einwilligungsfeld im Aufruf -> 403; unbekannte Art/Funktion, doppelter
    Eintrag, unbekanntes Postfach, unbrauchbare Liste -> 417 mit deutscher
    Meldung. Es wird NICHTS geschrieben, wenn eine Prüfung scheitert (erst
    prüfen, dann schreiben).
    """
    abweisung = _nur_post(request)
    if abweisung is not None:
        return abweisung
    _require_website_rolle()
    _weise_einwilligungsfelder_ab(kwargs)

    from sqlalchemy import delete, select

    from diakronos_app.models.website_ansprechpartner import WebsiteAnsprechpartner
    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

    eintraege = _bereichsliste(bereiche)
    katalog = _funktionskatalog()

    sess, eigene = _bereiche_sitzung()
    try:
        bekannte_postfaecher = {
            str(z.slug)
            for z in sess.execute(select(WebsiteKontaktPostfach)).scalars().all()
        }
        geprueft: list[dict] = []
        gesehen: set[tuple[str, str]] = set()
        for stelle, eintrag in enumerate(eintraege):
            art = str(eintrag.get("art") or "").strip().lower()
            if art not in BEREICH_ARTEN:
                throw(
                    "Unbekannte Art. Erlaubt sind Dienstbereich und Gruppe.",
                    ValidationError,
                )
            funktion = str(eintrag.get("funktion") or "").strip()
            if not funktion:
                throw("Bitte für jeden Bereich eine Funktion angeben.", ValidationError)
            if funktion not in katalog[art]:
                throw(
                    "Diese Funktion gibt es im Organigramm nicht mehr. "
                    "Bitte die Liste neu laden.",
                    ValidationError,
                )
            if (art, funktion) in gesehen:
                throw(
                    "Jede Funktion darf nur einmal ausgewählt werden.",
                    ValidationError,
                )
            gesehen.add((art, funktion))

            bezeichnung = str(eintrag.get("bezeichnung") or "").strip()
            if len(bezeichnung) > 140:
                throw(
                    "Die Bezeichnung darf höchstens 140 Zeichen lang sein.",
                    ValidationError,
                )
            postfach = str(eintrag.get("postfach") or "").strip() or None
            if postfach is not None and postfach not in bekannte_postfaecher:
                throw(
                    "Dieses Postfach gibt es nicht. Bitte eines aus der Liste wählen.",
                    ValidationError,
                )
            try:
                sortierung = int(eintrag.get("sortierung", stelle))
            except (TypeError, ValueError):
                sortierung = stelle
            geprueft.append(
                {
                    "art": art,
                    "funktion": funktion,
                    "bezeichnung": bezeichnung or None,
                    "postfach": postfach,
                    "sortierung": sortierung,
                }
            )

        # Ab hier wird geschrieben — alles geprüft.
        sess.execute(delete(WebsiteAnsprechpartner))
        for werte in geprueft:
            sess.add(WebsiteAnsprechpartner(**werte))
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if eigene:
            sess.close()

    logger.info("Ansprechpartner-Bereiche gesetzt (%s).", len(geprueft))
    return {"bereiche": _auswahl_lesen()}


def _weise_einwilligungsfelder_ab(argumente) -> None:
    """403, wenn der Aufruf ein Einwilligungsfeld mitschickt (P1, fail closed).

    Frappe reicht bei einer Funktion mit ``**kwargs`` ALLE Request-Argumente
    durch (JSON-Body, Formular, Query-String). Dieser Endpunkt kennt keine
    Einwilligungsfelder; sie still zu verwerfen wäre ein stiller Fehlschlag
    genau dort, wo es um Datenschutz geht. Deshalb: klare Ablehnung.
    """
    vorhanden = {str(k) for k in (argumente or {})}
    treffer = sorted(vorhanden.intersection(EINWILLIGUNGS_FELDER))
    if treffer:
        throw(
            "Die Einwilligung kann nur die Person selbst erteilen oder widerrufen.",
            FrappePermissionError,
        )


def _bereichsliste(wert) -> list[dict]:
    """``bereiche`` als Liste von Dicts (JSON-String, Liste, ``None``)."""
    import json

    if wert is None or wert == "":
        return []
    daten = wert
    if isinstance(wert, (str, bytes)):
        try:
            daten = json.loads(wert)
        except (TypeError, ValueError):
            throw("Die Liste der Bereiche ist unbrauchbar.", ValidationError)
    if not isinstance(daten, (list, tuple)):
        throw("Die Liste der Bereiche ist unbrauchbar.", ValidationError)
    liste = []
    for eintrag in daten:
        if isinstance(eintrag, (str, bytes)):
            try:
                eintrag = json.loads(eintrag)
            except (TypeError, ValueError):
                throw("Die Liste der Bereiche ist unbrauchbar.", ValidationError)
        if not isinstance(eintrag, dict):
            throw("Die Liste der Bereiche ist unbrauchbar.", ValidationError)
        liste.append(eintrag)
    return liste


# Kurzpfade, die die Karte so nennt (`website.meine_einwilligung_lesen|_setzen`,
# `website.ansprechpartner_bereiche_setzen`) zusätzlich zur Frappe-Bahn. Die
# abgeleiteten Kurzformen (`website.website_ansprechpartner_bereiche_setzen`)
# sind unschön, aber harmlos — die Karte spricht die hier eingetragenen an.
# DIESELBEN Funktionen: Optionen (`allow_guest`, `methods`) gehen mit.
def _registriere_kurzpfade() -> None:
    from diakronos_app.frappe_compat.registry import register_with_frappe_module

    for kurz, fn in (
        ("meine_einwilligung_lesen", meine_einwilligung_lesen),
        ("meine_einwilligung_setzen", meine_einwilligung_setzen),
        ("ansprechpartner_bereiche_lesen", ansprechpartner_bereiche_lesen),
        ("ansprechpartner_bereiche_setzen", ansprechpartner_bereiche_setzen),
    ):
        register_with_frappe_module("website", kurz, fn)


_registriere_kurzpfade()
