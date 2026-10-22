"""Statische Auslieferung der Diakonos-SPA durch FastAPI + Anmeldung.

Die Vue-3-SPA wurde mit Vite gebaut (`frontend/`). Ihr Build-Ergebnis liegt in
`frontend/dist/`. Dieses Modul liefert es unter dem Praefix `/diakonos` aus und
injiziert das Boot-Objekt `window.__DIakonosBOOT` in die index.html.

Wichtig: Der Catch-all fuer das SPA-Routing darf `/healthz` und spaetere
`/api/*`-Routen NICHT schlucken. Die Registrierung passiert daher NACH allen
API-Routen und schliesst diese Praefixe explizit aus.

A1b2-rest — was sich hier geaendert hat
--------------------------------------
1. **Boot-Objekt ist echt** (`boot_fuer_request`). Vorher stand hier ein
   `DUMMY_BOOT` mit `is_admin: True` und "Test Nutzer": jeder Besucher der
   SPA war Administrator. Jetzt wird der Name aus der `user`-Tabelle, die
   Admin-Rolle aus `permissions.get_roles()` (echte `Has Role`-Abfrage) und
   der CSRF-Token aus der laufenden Sitzung geholt — 1:1 nach
   `referenz/diakronos-frappe/diakronos/www/diakonos/index.py:20-56`.
2. **Ohne Sitzung liefert `/diakonos` die Login-Maske** statt der SPA. Der
   Quellcode in `referenz/.../diakonos/www/diakonos/index.py:16-18` macht
   genau das (`frappe.local.flags.redirect_location = "/login?redirect-to=
   /diakonos"`). Die SPA hat keine eigene Anmeldeseite, deshalb serviert der
   Stack sie hier.
3. **`index.html` und die Maske werden mit `Cache-Control: no-store`
   ausgeliefert**, die hash-benannten Assets bleiben `immutable`. Grund: das
   HTML traegt das sitzungsabhaengige Boot-Objekt; ein dauerhaft gecachter
   Stand wuerde nach dem Logout weiter den alten Namen zeigen.

Die Spitzenvorgaenge sind bewusst 1:1 aus dem Original uebernommen, damit
`referenz/` und `standalone` nicht auseinanderlaufen:

  Original                                hier
  --------------------------------------   ---------------------------------
  `frappe.db.get_value("User", user, …)`   `_user_zeile()`  (user-Tabelle)
  `frappe.db.get_value("Mitglied", {email})`  `_mitglied_zeile()`
  `frappe.get_roles(user)`                 `permissions.get_roles(user)`
  `frappe.sessions.get_csrf_token()`       `sitzungen.lesen(sid)["csrf_token"]`
  `context.no_cache = 1`                   `Cache-Control: no-store`
"""

from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from diakronos_app.frappe_compat.session import GUEST, session
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.spa")

# Pfad zum Vite-Build. Standard: <repo>/frontend/dist (Worktree-/Dev-Betrieb).
# Im Container wird das Verzeichnis per COPY nach /app/frontend/dist gelegt;
# beide Kandidaten werden geprueft.
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[3] / "frontend" / "dist",   # <repo>/frontend/dist  (src/diakronos_app/spa.py)
    Path("/app/frontend/dist"),               # Container-Layout
]
SPA_DIST: Path | None = next((p for p in _CANDIDATES if p.is_dir()), None)

# Praefixe, die NIEMALS vom SPA-Catch-all geschluckt werden duerfen.
RESERVED_PREFIXES = ("/healthz", "/api", "/docs", "/redoc", "/openapi.json")

# Praefix, unter dem die SPA ausgeliefert wird.
SPA_PREFIX = "/diakonos"


# ──────────────────────────────────────────────────────────────────────────
# Boot-Objekt
# ──────────────────────────────────────────────────────────────────────────
# Das Boot-Objekt traegt die Felder, die der SPA-Quellcode liest
# (frontend/BOOT_VERTRAG.md). Es wird pro Request serverseitig gebaut — es
# darf KEIN statisches Objekt mehr sein: Name, Rolle und CSRF-Token haengen
# an der Sitzung.

# Rollen mit Vollzugriff: DIE Wahrheit ist `frappe_compat/permissions.py`
# (ADMIN_ROLES). Hier stand bis A1c3 eine eigene, identische Kopie — eine
# stille Falle, kein Fehler: wer eine der beiden Listen erweitert, bekommt ein
# Boot-Objekt mit falschem `is_admin`, ohne dass irgendwo etwas aufraeumt.
# `boot_fuer_request()` benutzt deshalb direkt `permissions.ADMIN_ROLES`.
#
# Die portierten Fachmodule unter `api/` fuehren aus dem Original
# (`diakonos/api/session.py`, `api/_permissions.py`) ebenfalls lokale Listen;
# die bleiben unangetastet — sie sind der Originaltreue geschuldet. Die
# Kompat-Schicht ist der Ort, an dem eine Liste fuer den gesamten Stack steht.

# Gemeindename ohne hinterlegten Wert. Identisch zum Fallback in
# `api/orgchart_api.py:37`, damit die Sidebar und die Login-Maske nicht
# verschiedene Namen zeigen.
DEFAULT_CHURCH_NAME = "Meine Gemeinde"

# Seiten unter /diakonos, die im Altcode OEFFENTLICH sind und deshalb KEINE
# Anmeldung verlangen. Quelle (READ-ONLY):
#   referenz/.../diakronos/www/diakonos/registrierung.py:5  allow_guest = True
#   referenz/.../diakronos/www/diakonos/gast.py:5           allow_guest = True
# `diakonos` selbst (index.py:16) und `organigramm` (organigramm.py:14)
# leiten im Altcode ohne Sitzung zur Anmeldung weiter.
OEFFENTLICHE_EINTRAEGE = ("registrierung", "gast")

# ── Altpfade der Frappe-www-Module (A1c5) ───────────────────────────────────
# `boot.modules[].route` zeigte im Original auf echte www-Seiten (`/kronos`,
# `/psalmos`, `/app/kronos`, …). Dieser Stack liefert nur `/diakonos`. Damit ein
# alter Lesezeichen- oder Mail-Link nicht auf einem nackten 404 landet, leiten
# wir die Altpfade auf die SPA um.
#
# WICHTIG: Die Zuordnung ist KEINE zweite Tabelle. Sie wird aus genau einem
# Ort gebildet: `perms.MODUL_ZIEL_SPA` + `perms.MODULE_ROUTES` in
# `api/kronos/permissions.py`. Wer dort ein Modul ergaenzt, bekommt den
# Redirect automatisch — zwei Listen wären die A1c3-Falle `ADMIN_ROLES` in
# neuer Kleidung.
#
# Jeder Pfad laeuft durch DASSELBE Anmeldegate wie `/diakonos` (unten, Schritt
# 3 der `spa_catch_all`): ohne Sitzung kommt die Login-Maske und NICHT ein 404
# mit Hinweis auf die Existenz des Moduls.
def _altpfad_redirects() -> dict[str, str]:
    """Altpfad -> SPA-Ziel. Wird einmal gelesen und gecacht."""
    global _ALTPFAD_REDIRECTS
    if _ALTPFAD_REDIRECTS is None:
        _ALTPFAD_REDIRECTS = _baue_altpfad_redirects()
    return _ALTPFAD_REDIRECTS


def _baue_altpfad_redirects() -> dict[str, str]:
    """Baut die Altpfad-Tabelle aus EINER Quelle (siehe Kommentar oben).

    ABSICHTLICH OHNE `/app/kronos`: das ist `MODULE_ROUTES["Diakronos"]`, und
    `Diakronos` hat in `MODUL_ZIEL_SPA` bewusst kein Ziel (`MODULE_PAGES` im
    Original ist fuer dieses Modul LEER — "kein Hub, direkt zu Workspace").
    Ein Workspace existiert in diesem Stack nicht. Dieser Pfad bleibt deshalb
    404; ihn auf `#/kalender` zu biegen, waere eine erfundene Zuordnung, weil
    der Original-Pfad auf die Frappe-Desk-Seite zeigt und nicht auf den
    Kalender. Gemeldet statt geflickt (A1c5).
    """
    from diakronos_app.api.kronos import permissions as perms

    ziele: dict[str, str] = {}
    for modul, frappe_route in perms.MODULE_ROUTES.items():
        ziel = perms.MODUL_ZIEL_SPA.get(modul)
        if ziel and ziel.startswith("#/"):
            ziele["/" + frappe_route.lstrip("/")] = ziel
    # Der generische Fallback des Originals (`/app/<modul>`) deckt auch Module
    # ab, die nicht in `MODULE_ROUTES` stehen. Er wird nur aufgenommen, wenn die
    # SPA dafuer ein Ziel hat — sonst wuerde er auf die Startseite zeigen und
    # damit vortaeuschen, es gabe eine Modulseite.
    for modul, ziel in perms.MODUL_ZIEL_SPA.items():
        if modul in perms.MODULE_ROUTES:
            continue
        ziele[f"/app/{modul.lower()}"] = ziel
    return ziele


_ALTPFAD_REDIRECTS: dict[str, str] | None = None


def _settings_zeile() -> dict[str, Any]:
    """`Diakronos Einstellungen` (Single) — Gemeindename und Logo.

    Gefaellt aus: fehlende Tabelle, fehlende Zeile, nicht gesetzter Name. Der
    Aufrufer bekommt immer ein brauchbares dict zurueck, nie eine Exception —
    eine fehlende Gemeindeangabe darf die Seite nicht wegkaufen.
    """
    from diakronos_app.frappe_compat.query import get_all, get_value

    felder = ["organisationsname", "diakonos_icon", "diakonos_anzeige_name"]
    try:
        row = get_value("Diakronos Einstellungen", "Diakronos Einstellungen", felder, as_dict=True)
        if not row:
            rows = get_all("Diakronos Einstellungen", fields=felder, limit_page_length=1)
            row = rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001 — Einstellungen sind optional
        logger.warning("Diakronos Einstellungen nicht lesbar: %s", exc)
        row = None
    return dict(row) if row else {}


def _user_zeile(user: str) -> dict[str, Any]:
    """`user`-Tabelle: Anzeigename, E-Mail, Avatar. `{}` wenn unbekannt."""
    from diakronos_app.frappe_compat.query import get_value

    try:
        return dict(
            get_value("User", user, ["full_name", "user_image", "email"], as_dict=True) or {}
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("User %r nicht lesbar: %s", user, exc)
        return {}


def _mitglied_zeile(email: str) -> dict[str, Any] | None:
    """Mitglied-Datensatz ueber die E-Mail des Users, sonst `None`.

    `None` ist ein echtes Ergebnis: `router.js:148` faellt dann bewusst auf
    "kein Guard" zurueck (BOOT_VERTRAG.md Punkt 4).
    """
    from diakronos_app.frappe_compat.query import get_value

    if not email:
        return None
    try:
        row = get_value(
            "Mitglied", {"email": email},
            ["name", "vorname", "nachname", "status"],
            as_dict=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mitglied zu %r nicht lesbar: %s", email, exc)
        return None
    return dict(row) if row else None


def _module_liste() -> list:
    """`get_accessible_modules()` — im Fehlerfall `[]`, nie `None`.

    Genau die Fehlerbehandlung des Originals (index.py:39-44): ein Fehler beim
    Laden der Modulliste darf die Seite nicht verhindern.
    """
    try:
        from diakronos_app.api.kronos.permissions import get_accessible_modules

        return list(get_accessible_modules() or [])
    except Exception as exc:  # noqa: BLE001 — 1:1 wie das Original
        logger.warning("get_accessible_modules(): %s", exc)
        return []


def _csrf_token(user: str) -> str:
    """CSRF-Token der laufenden Sitzung.

    Der Token liegt im Server-Zustand (Synchronizer-Token, `CsrfMiddleware`).
    `frappe.sessions.get_csrf_token()` im Original entspricht genau diesem
    Wert. Ohne gueltige Sitzung gibt es keinen Token — dann ist der Wert leer
    und NICHT erfunden: ein geratener Token wuerde jeden schreibenden Aufruf
    mit 417 beantworten und so tun, als waere alles in Ordnung.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.request_context import get_header

    if user == GUEST:
        return ""
    sid = sid_aus_headers_from(get_header("Cookie"))
    if not sid:
        return ""
    daten = sitzungen.lesen(sid)
    if not daten or daten.get("user") != user:
        return ""
    return str(daten.get("csrf_token") or "")


def sid_aus_headers_from(cookie_header: str) -> str | None:
    """`sid` aus einem einzelnen Cookie-Kopfzeilenwert (ohne Request-Objekt)."""
    if not cookie_header:
        return None
    for teil in cookie_header.split(";"):
        name, _, wert = teil.strip().partition("=")
        if name == "sid" and wert:
            return wert
    return None


def boot_fuer_request() -> dict[str, Any]:
    """Baut das echte Boot-Objekt der SPA fuer den laufenden Request.

    Aufrufer: `render_index()` ueber die Route in `mount_spa()`. Der
    `SessionMiddleware` hat `session.user` zu diesem Zeitpunkt bereits aus dem
    `sid`-Cookie gesetzt; `User`/`Mitglied`/Rollen werden daraus abgeleitet,
    nicht geraten.
    """
    user = session.user
    user_doc = _user_zeile(user) if user != GUEST else {}
    email = user_doc.get("email") or ("" if user == GUEST else user)
    einstellungen = _settings_zeile()

    # A1c3: DIE Admin-Rollenliste kommt aus der Kompat-Schicht, nicht aus
    # einer Kopie in diesem Modul. Importiert wird das Modul (nicht der
    # Einzelname), damit ein spaeteres Erweitern von `permissions.ADMIN_ROLES`
    # hier automatisch durchschlaegt — das war der Zweck der Aenderung.
    from diakronos_app.frappe_compat import permissions

    rollen = permissions.get_roles(user)
    return {
        "user": user,
        "user_fullname": user_doc.get("full_name") or ("" if user == GUEST else user),
        "user_email": email,
        "user_image": user_doc.get("user_image") or "",
        "csrf_token": _csrf_token(user),
        # KEIN Flag im Boot: die Admin-Rolle kommt aus `Has Role`.
        "is_admin": any(r in permissions.ADMIN_ROLES for r in rollen),
        # MAIL-1b (N3): Die Startseite haelt die DSGVO-Kachel fuer System
        # Manager sichtbar — wer den Mailversand einstellen darf, muss die
        # Warnung „Mailversand ist noch nicht eingerichtet“ sehen. Die Liste
        # ist reine Anzeige; jede Aenderung entscheidet der Server erneut.
        "roles": list(rollen),
        # DM1: der Dev-Modus-Eintrag erscheint nur fuer Admins und Tester.
        # Die Entscheidung bleibt serverseitig (dieselbe Rolle wird dort
        # geprueft) — hier wird nur ausgeblendet, was verweigert wird.
        "ist_tester": any(r in permissions.ADMIN_ROLES for r in rollen)
                      or "Tester" in rollen,
        "devmode": bool(getattr(settings, "devmode_enabled", False)),
        # K1 (R-P1-8): `MitgliedDetail.vue` blendet den Hinweis „Über Authentik
        # verwalten" nur ein, wenn `window.__DIakonosBOOT.oidc_aktiv` gesetzt
        # ist. Der Schluessel fehlte im Boot-Objekt — der Hinweis war nie
        # sichtbar, obwohl der Server korrekt verweigert.
        "oidc_aktiv": _oidc_aktiv(),
        "mitglied": _mitglied_zeile(email) if user != GUEST else None,
        "modules": _module_liste() if user != GUEST else [],
        "church_name": einstellungen.get("organisationsname") or DEFAULT_CHURCH_NAME,
        # `diakonos_icon` ist ein Freitextfeld (Pfad oder URL), kein Anhang —
        # `diakronos_einstellungen.json` fieldtype "Data".
        "logo_url": einstellungen.get("diakonos_icon") or None,
        # N9: die oeffentliche Adresse der Gemeinde. Die Oberflaeche baut damit
        # vollstaendige Links (Registrierung/Passwort) — ist sie leer, faellt sie
        # auf `window.location.origin` zurueck. So stimmt der geteilte Link auch
        # dann, wenn die Verwaltung ueber eine andere Adresse arbeitet.
        "oeffentliche_adresse": _oeffentliche_adresse(),
        # UXD-R21: Kontaktadresse der Gemeindeleitung. Die Wiki-Hilfe zeigt
        # sie nur, wenn sie gepflegt ist — sonst bleibt der Hinweis weg.
        "gemeinde_kontakt_email": _gemeinde_kontakt_email(),
    }


def _gemeinde_kontakt_email() -> str:
    """Die in den Einstellungen gepflegte Kontaktadresse (oder ``""``).

    Gleiche Regel wie ``_oeffentliche_adresse``: nie eine Exception, eine
    fehlende Einstellung darf das Boot-Objekt nicht wegkaufen.
    """
    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            return (zeile.kontakt_email or "").strip() if zeile else ""
    except Exception as exc:  # noqa: BLE001 — Einstellungen sind optional
        logger.warning("Gemeinde-Kontakt nicht lesbar: %s", exc)
        return ""


def _oeffentliche_adresse() -> str:
    """Die in den Einstellungen gepflegte Gemeinde-Adresse (oder ``""``).

    Nie eine Exception: eine fehlende Einstellung darf das Boot-Objekt nicht
    wegkaufen (dieselbe Regel wie ``_settings_zeile``).
    """
    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            return (zeile.oeffentliche_adresse or "").strip() if zeile else ""
    except Exception as exc:  # noqa: BLE001 — Einstellungen sind optional
        logger.warning("Oeffentliche Adresse nicht lesbar: %s", exc)
        return ""


def _willkommenstext() -> str:
    """Der gepflegte Willkommenstext fuer die oeffentliche Seite (M-1).

    Kommt aus der Single ``gemeinde_einstellungen``. Nie eine Exception:
    eine fehlende Einstellung darf die oeffentliche Seite nicht wegkaufen.
    """
    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            return (zeile.willkommenstext or "").strip() if zeile else ""
    except Exception as exc:  # noqa: BLE001 — Einstellungen sind optional
        logger.warning("Willkommenstext nicht lesbar: %s", type(exc).__name__)
        return ""


def _oeffentliche_texte() -> dict[str, Any]:
    """Die Texte fuer die oeffentliche Registrierungsseite (N9b, H-1).

    Kommt aus ``api/gemeinde.wirksame_texte`` — derselben Quelle, aus der
    ``submit_registrierung``/``submit_gast`` den Beleg-Snapshot bilden. So
    kann der angezeigte Wortlaut nicht vom gespeicherten abweichen.

    Nie eine Exception: die oeffentliche Seite darf nicht an einer fehlenden
    Einstellung scheitern (dieselbe Regel wie ``_oeffentliche_adresse``).
    """
    try:
        from diakronos_app.api.gemeinde import wirksame_fassung, wirksame_texte

        texte = wirksame_texte()
        # N-1: die geltende FASSUNG mitgeben, damit die Seite sie mitsenden
        # kann (angezeigt = bestaetigt).
        try:
            texte["einwilligung_fassung"] = int(wirksame_fassung().get("version", 1))
        except Exception:  # noqa: BLE001 — Fassung ist Beiwerk der Anzeige
            texte["einwilligung_fassung"] = 1
        return texte
    except Exception as exc:  # noqa: BLE001 — Texte sind optional
        logger.warning("Oeffentliche Texte nicht lesbar: %s", type(exc).__name__)
        return {}


def _oidc_aktiv() -> bool:
    """Ist die Anmeldung ueber Authentik/OIDC aktiv? — fuer das Boot-Objekt (K1).

    Kapselt den Import und faengt Fehler: das Boot-Objekt darf nie an einer
    nicht konfigurierten Anmeldung scheitern. Ohne OIDC ist das Ergebnis
    `False` (der Hinweis in der Oberflaeche bleibt dann aus).
    """
    try:
        from diakronos_app.anmeldung.konfiguration import oidc_aktiv

        return bool(oidc_aktiv())
    except Exception:  # noqa: BLE001 — Boot darf nie scheitern
        return False


def ist_angemeldet() -> bool:
    """True, wenn der laufende Request eine gueltige Sitzung hat.

    Quelle ist das Cookie, NICHT `session.user`: die Test-Naht
    `set_user()` setzt zwar `session.user`, ist aber keine Sitzung — fuer die
    Frage "darf ich die SPA sehen?" zaehlt nur ein echtes `sid`.
    """
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.request_context import get_header

    sid = sid_aus_headers_from(get_header("Cookie"))
    if not sid:
        return False
    daten = sitzungen.lesen(sid)
    return bool(daten and daten.get("user"))


def _load_manifest() -> dict[str, Any]:
    """Liest das vite-manifest.json aus dem Build-Output."""
    if SPA_DIST is None:
        return {}
    manifest = SPA_DIST / ".vite" / "manifest.json"
    if not manifest.is_file():
        manifest = SPA_DIST / "manifest.json"
    if not manifest.is_file():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — Manifest darf nie den Request killen
        logger.warning("vite-manifest unlesbar: %s", exc)
        return {}


def _asset_index() -> dict[str, Path]:
    """Bildet jede im Manifest genannte Datei auf ihren echten Pfad ab.

    Hintergrund: Vite `base` ist '/diakonos/assets/', die Dateien landen aber in
    verschiedenen Unterverzeichnissen (Root, css/, chunks/, assets/). Aus dem
    Manifest laesst sich der Basename jeder emittierten Datei gewinnen; wir
    suchen ihn in allen bekannten Unterverzeichnissen. Ergebnis: Basename ->
    echter Pfad. Ein Lookup per Basename ist eindeutig (Vite-Hashes).
    """
    manifest = _load_manifest()
    if not manifest or SPA_DIST is None:
        return {}
    subdirs = ["", "css", "chunks", "assets"]
    index: dict[str, Path] = {}

    def _add(rel: str) -> None:
        for sub in subdirs:
            cand = (SPA_DIST / sub / rel) if sub else (SPA_DIST / rel)
            if cand.is_file():
                index[rel] = cand
                return

    for rec in manifest.values():
        f = rec.get("file")
        if f:
            _add(f)
        for c in rec.get("css") or []:
            _add(c)
        for a in rec.get("assets") or []:
            _add(a)
    return index


def _entry_assets(entry: str) -> tuple[str | None, list[str]]:
    """Liefert (js_url, [css_urls]) fuer einen Vite-Eintrag.

    Die Vite-Config setzt `base: '/diakonos/assets/'`, die Dateinamen im
    Manifest sind dagegen RELATIV zum Build-Root ('diakonos-abc.js',
    'chunks/x.js', 'css/style-abc.css'). Der Catch-all loest deshalb jeden
    Namen ueber `_asset_index()` gegen SPA_DIST auf.

    WICHTIG — globales Stylesheet: Vite schreibt das gebuendelte CSS unter dem
    Manifest-Schluessel 'style.css' (nicht in `css` des Eintrags!). `css` ist bei
    ALLEN Eintraegen leer, weil das Projekt eine einzige globale `style.css`
    nutzt. Ohne explizites Einbinden von 'style.css' liefert die Seite die SPA
    voellig UNGESTYLT aus (Tailwind/Theme fehlen).
    """
    manifest = _load_manifest()
    rec = manifest.get(entry)
    if not rec:
        return None, []
    js_file = rec.get("file")
    js_url = f"{SPA_PREFIX}/assets/{js_file}" if js_file else None

    css_files: list[str] = []
    style_rec = manifest.get("style.css")
    if style_rec and style_rec.get("file"):
        css_files.append(style_rec["file"])
    css_files.extend(rec.get("css") or [])

    css_urls = [f"{SPA_PREFIX}/assets/{c}" for c in css_files]
    return js_url, css_urls


def _boot_json(boot_data: dict[str, Any]) -> str:
    """Boot-Objekt als JS-Literal, HTML-sicher gegen `</script>`.

    BOOT_VERTRAG.md Punkt 8: die Werte kommen jetzt aus der Datenbank, nicht
    mehr aus einer Konstante. `json.dumps` escaped Anfuehrungszeichen, aber
    nicht `</` — ein `</script>` im Anzeigenamen wuerde das Script-Tag
    schliessen und den Rest der Seite als HTML ausfuehren (XSS).

    Geloest ueber JSON-eigene Unicode-Escapes (`<` -> `\\u003c`): die sind im
    JSON gueltig, ergeben im Browser exakt dasselbe Zeichen und koennen keine
    HTML-Sonderzeichen mehr bilden.

    Wichtig: die Backslashes werden NICHT noch einmal verdoppelt — `json.dumps`
    hat sie schon escaped; ein zweites Verdoppeln wuerde aus einem Pfad
    `a\\b` den Wert `a\\\\b` machen. Geprueft werden deshalb ausschliesslich
    die Zeichen, die in der JSON-Struktur gar nicht vorkommen, sondern nur in
    Werten: `<`, `>`, `&` sowie U+2028/U+2029 (die gelten in JavaScript als
    Zeilenumbruch und wuerden ein sonst gueltiges Script zerlegen).

    Die letzten beiden werden ueber ihre Codepoint-Schreibweise benannt, damit
    sie in der Quelldatei nicht unsichtbar als Leerzeichen erscheinen.
    """
    raw = json.dumps(boot_data, ensure_ascii=False)
    for codepoint, ersatz in (
        (0x3C, "\\u003c"),  # <
        (0x3E, "\\u003e"),  # >
        (0x26, "\\u0026"),  # &
        (0x2028, "\\u2028"),  # LINE SEPARATOR
        (0x2029, "\\u2029"),  # PARAGRAPH SEPARATOR
    ):
        raw = raw.replace(chr(codepoint), ersatz)
    return raw


def render_index(
    entry: str = "src/diakonos/main.js",
    boot: dict | None = None,
    oeffentlich: dict | None = None,
) -> str:
    """Baut die index.html mit injiziertem __DIakonosBOOT.

    Der Name `__DIakonosBOOT` ist KEIN Tippfehler: die SPA liest exakt diesen
    Bezeichner (grosses 'I' nach 'DI'). Siehe frontend/BOOT_VERTRAG.md.

    `boot=None` holt das echte Boot-Objekt des laufenden Requests
    (`boot_fuer_request`). Das ist der Normalfall der Route; ein explizit
    uebergebenes Objekt dient den Tests.

    `oeffentlich` (UXD-R1): die oeffentlichen Seiten `registrierung` und
    `gast` stammen aus dem Frappe-Original und lesen ihre Daten aus
    `window.__diakronos` — dem Jinja-Kontext der damaligen `www`-Seite. Diesen
    Kontext setzte im Standalone NIE jemand, deshalb war `token` immer leer und
    jedes Absenden lief in HTTP 403 "Kein Registrierungstoken angegeben".
    Ist das Objekt uebergeben, wird es als `window.__diakronos` VOR dem
    Entry-Script eingefuegt (die SPA liest es synchron beim Modul-Import).
    """
    boot_data = boot_fuer_request() if boot is None else boot
    js_url, css_urls = _entry_assets(entry)

    if js_url is None:
        # Fallback: kein Manifest vorhanden (Build fehlt). Klarer Hinweis statt
        # stiller 404 — erleichtert die Fehlersuche.
        logger.error("Kein Vite-Manifest fuer Eintrag %s gefunden (%s)", entry, SPA_DIST)
        js_tag = "<!-- FEHLER: kein Vite-Manifest gefunden — SPA wurde nicht gebaut. -->"
    else:
        js_tag = f'<script type="module" src="{js_url}"></script>'

    css_tags = "\n    ".join(
        f'<link rel="stylesheet" href="{u}">' for u in css_urls
    )
    # Die SPA liest window.__DIakonosBOOT synchron beim Modul-Import, daher
    # muss das Objekt VOR dem Entry-Script stehen (BOOT_VERTRAG.md Punkt 2).
    boot_json = _boot_json(boot_data)
    # UXD-R1: derselbe Schutz (`</script>`-Neutralisierung) gilt fuer die
    # oeffentlichen Daten — der Token kommt aus der URL, die Feldlabels aus
    # der Datenbank.
    oeffentlich_tag = ""
    if oeffentlich is not None:
        oeffentlich_tag = (
            "\n    <script>\n"
            f"        window.__diakronos = {_boot_json(oeffentlich)};\n"
            "    </script>"
        )
    # `organigramm/App.vue:50`, `registrierung/App.vue:202` und
    # `Profile.vue:325` lesen den Token aus diesem meta-Tag.
    csrf_meta = html.escape(str(boot_data.get("csrf_token") or ""), quote=True)
    title = html.escape(str(boot_data.get("church_name") or "Diakonos"), quote=True)

    # OP-HANDY-17: Hier standen drei Google-Fonts-Zeilen (zwei `preconnect` auf
    # fonts.googleapis.com/fonts.gstatic.com und ein `<link>` auf
    # `fonts.googleapis.com/css2?family=Inter…`). Damit ging die IP-Adresse
    # JEDES Mitglieds bei jedem Seitenaufruf an Google (in Deutschland
    # abgemahnt, LG Muenchen I, 3 O 17493/20) und kostete 48 KB Fremdverkehr
    # im Gemeindenetz. Inter liegt schon lokal im Buendel: `index.css` zieht
    # `frappe-ui/style.css`, das ein `@font-face` mit `Inter.var.woff2`
    # (OFL-Lizenz) deklariert — die Fremdanfrage war deshalb ueberfluessig.
    # Waechter: `backend/tests/test_p2_6_google_fonts.py`.
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>{title}</title>
    <meta name="csrf-token" content="{csrf_meta}">
    {css_tags}
</head>
<body>
    <div id="app"></div>

    <script>
        window.__DIakonosBOOT = {boot_json};
    </script>{oeffentlich_tag}
    {js_tag}
</body>
</html>
"""



def render_login(next_url: str = SPA_PREFIX, *, meldung: str = "", email: str = "") -> str:
    """Serverseitige Anmeldemaske (deutsch, ohne JavaScript).

    Die SPA hat keine eigene Anmeldeseite und wird nicht angetastet. Das
    Formular geht an `/api/method/login` (Frappe-kompatibel, Karte A1b1) und
    laesst den Browser danach auf `next_url` zurueckkehren.

    Bewusst kein eigenes POST-Handling: derselbe Endpunkt bedient spaeter auch
    die SPA, und zwei Anmeldewege waeren zwei Wahrheiten. Was ein
    **fehlgeschlagener** Formular-POST zurueckgibt, entscheidet der
    Compat-Router (`api/auth.py::login_formular_fehler`): 303 auf `/login`
    mit einem kurzlebigen Flash-Cookie.

    LOGIN-1 — `meldung` und `email` kommen aus genau diesem Flash-Cookie
    (`anmeldung/flash.py`) und werden hier angezeigt bzw. vorausgefuellt:

      * `meldung` steht in einem `role="alert"`-Block UEBER dem Formular —
        fuer Screenreader eine Ansage, fuer alle anderen ein sichtbarer Satz.
      * `email` landet im Feld `usr`. NIE das Passwort.
      * Beides wird escaped; der Cookie ist zusaetzlich signiert. Ein
        manipulierter Cookie kann deshalb weder Markup einschleusen noch eine
        andere Meldung als die zwei vorgesehenen erzeugen.

    Sicherheit: `next_url` und der Gemeindename werden escaped — beide kommen
    aus der Anfrage bzw. der Datenbank. Es wird nichts in ein
    `javascript:`-Schema oder ein verstecktes Feld geschrieben.
    """
    from urllib.parse import quote

    # `quote` fuer das versteckte Feld: der Browser sendet den Wert als
    # URL-kodierten Text, den wir serverseitig dekodieren.
    ziel_kodiert = html.escape(quote(next_url, safe=""), quote=True)
    gemeinde = html.escape(_settings_zeile().get("organisationsname") or DEFAULT_CHURCH_NAME, quote=True)
    meldung_html = html.escape(meldung, quote=True)
    email_html = html.escape(email, quote=True)
    meldung_block = (
        f'\n        <p class="dk-meldung" role="alert">{meldung_html}</p>'
        if meldung
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anmelden — {gemeinde}</title>
    <style>
        :root {{ color-scheme: light dark; }}
        body {{
            margin: 0; min-height: 100vh; display: flex; align-items: center;
            justify-content: center; padding: 1.5rem;
            font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
            background: #f5f6f8; color: #1f2430;
        }}
        .dk-login {{
            width: 100%; max-width: 24rem; background: #fff; padding: 2rem;
            border-radius: .75rem; box-shadow: 0 1px 3px rgba(16,24,40,.1),
            0 12px 32px rgba(16,24,40,.08);
        }}
        .dk-login h1 {{ margin: 0 0 .25rem; font-size: 1.25rem; font-weight: 600; }}
        .dk-login p.sub {{ margin: 0 0 1.5rem; color: #5b6474; font-size: .875rem; }}
        label {{ display: block; font-size: .8125rem; font-weight: 500; margin-bottom: .375rem; }}
        input {{
            width: 100%; box-sizing: border-box; padding: .625rem .75rem; margin-bottom: 1rem;
            font-size: .9375rem; font-family: inherit; color: inherit; background: #fff;
            border: 1px solid #d3d8e0; border-radius: .5rem;
        }}
        input:focus {{ outline: 2px solid #3b6ea5; outline-offset: 1px; border-color: #3b6ea5; }}
        button {{
            width: 100%; padding: .6875rem 1rem; font-size: .9375rem; font-weight: 600;
            font-family: inherit; color: #fff; background: #2f5d8a; cursor: pointer;
            border: 0; border-radius: .5rem;
        }}
        button:hover {{ background: #274c72; }}
        .hinweis {{ margin: 1rem 0 0; font-size: .75rem; color: #5b6474; }}
        /* LOGIN-1: Meldung ueber dem Formular. Rot nur als Rand + Text, kein
           Vollton — die Seite bleibt ruhig, der Satz ist trotzdem sofort zu
           finden. `role="alert"` steht im Markup (Screenreader-Ansage). */
        .dk-meldung {{
            margin: 0 0 1rem; padding: .625rem .75rem; font-size: .875rem;
            color: #8a1f1f; background: #fdecec; border: 1px solid #f3c7c7;
            border-left: 3px solid #b03030; border-radius: .5rem;
        }}
        .dk-meldung:empty {{ display: none; }}
        /* OP-HANDY-14: iOS-Safari zoomt beim Antippen in Felder unter 16 px
           (hier 15 px) und laesst den Ausschnitt verschoben stehen. Im groben
           Zeiger deshalb 16 px — dieselbe Regel wie im SPA-Stylesheet. */
        @media (hover: none) and (pointer: coarse) {{
            input, select, textarea {{ font-size: 16px; }}
        }}
        @media (prefers-color-scheme: dark) {{
            body {{ background: #14171d; color: #e8eaee; }}
            .dk-login {{ background: #1d212a; box-shadow: none; border: 1px solid #2a2f3a; }}
            p.sub, .hinweis {{ color: #9aa3b2; }}
            input {{ background: #14171d; border-color: #333a47; }}
            .dk-meldung {{
                color: #ffc9c9; background: #3a1d1d; border-color: #5a2a2a;
                border-left-color: #d06060;
            }}
        }}
    </style>
</head>
<body>
    <main class="dk-login">
        <h1>{gemeinde}</h1>
        <p class="sub">Bitte melde dich an, um fortzufahren.</p>{meldung_block}
        <form method="post" action="/api/method/login" accept-charset="utf-8">
            <input type="hidden" name="redirect-to" value="{ziel_kodiert}">
            <label for="dk-usr">E-Mail oder Benutzername</label>
            <input id="dk-usr" name="usr" type="text" autocomplete="username"
                   autocapitalize="none" autocorrect="off" spellcheck="false" required
                   value="{email_html}">
            <label for="dk-pwd">Passwort</label>
            <input id="dk-pwd" name="pwd" type="password"
                   autocomplete="current-password" required{" autofocus" if meldung else ""}>
            <button type="submit">Anmelden</button>
        </form>
        <p class="hinweis">Anmeldelinks fuer Registrierung und Gastzugriff
            findest du in der Nachricht der Gemeindeleitung.</p>
    </main>
    <script>
        // PF1: Beim Anmelden ist IMMER niemand angemeldet — ein hier
        // liegender nutzerbezogener Browser-Cache (stale-while-revalidate der
        // Planrahmen-Arbeitsseiten) muss weg, sonst bliebe nach dem Abmelden
        // der Stand des vorigen Nutzers auf einem geteilten Geraet liegen.
        // Nur der eigene Praefix; keine Auswirkung ohne localStorage.
        try {{
            var weg = [];
            for (var i = 0; i < localStorage.length; i += 1) {{
                var k = localStorage.key(i);
                if (k && k.indexOf('dk-pr-swr:') === 0) {{ weg.push(k); }}
            }}
            for (var j = 0; j < weg.length; j += 1) {{ localStorage.removeItem(weg[j]); }}
        }} catch (e) {{ /* kein Speicher -> nichts zu tun */ }}

        // OP-CHOR-4: Der Hash erreicht den Server NIE (Browser senden ihn
        // nicht mit). Ein geteilter Deeplink `#/planrahmen/plan/…` ging
        // dadurch bei der Anmeldung verloren — das Mitglied landete auf dem
        // Dashboard. Hier wird der aktuelle Hash an das Feld `redirect-to`
        // angehaengt; `_redirect_ziel` (auth.py) laesst ein Fragment zu und
        // weist fremde Ziele weiterhin ab.
        try {{
            var hash = window.location.hash || '';
            var feld = document.querySelector('input[name="redirect-to"]');
            if (hash && feld) {{
                var ziel = decodeURIComponent(feld.value || '');
                if (ziel.indexOf('#') === -1) {{
                    feld.value = encodeURIComponent(ziel + hash);
                }}
            }}
        }} catch (e) {{ /* Formular bleibt ohne Hash nutzbar */ }}
    </script>
</body>
</html>
"""


def _login_maske(request, next_url: str) -> Response:
    """Anmeldemaske ausliefern — ohne Meldung/Flash.

    LOGIN-2/K: Hier stand bis LOGIN-1 das Lesen und Loeschen des
    Flash-Cookies. Der Cookie hat `Path=/login` und kommt auf den SPA-Pfaden
    (`/diakonos`, Altpfade) **nie** an — der Zweig war tot, schickte aber auf
    jeder Anmelde-Antwort ein Loesch-`Set-Cookie` mit. Die Meldung gehoert
    ausschliesslich auf die Anmeldeseite `/login`
    (`anmeldung/routen.py::login_route`), wo der Cookie tatsaechlich ankommt.
    """
    return _no_store(HTMLResponse(render_login(next_url)))


def _no_store(response: Response) -> Response:
    """`Cache-Control: no-store` setzen (1:1 zu `context.no_cache = 1`).

    Das HTML traegt das sitzungsabhaengige Boot-Objekt. Ohne diese Kopfzeile
    koennte ein Browser nach dem Logout noch die Seite mit dem alten Namen
    aus dem Cache anzeigen.
    """
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def _asset_response(pfad: Path) -> FileResponse:
    """Hash-benanntes Build-Artefakt — `immutable` gecacht.

    Die Dateinamen enthalten einen Inhalts-Hash (`diakonos-CNOeSrea.js`).
    Beim Aendern des Quellcodes aendert sich der Name, also kann ein Browser
    das Ergebnis dauerhaft halten: `Cache-Control: public, max-age=31536000,
    immutable`. Genau das ist der Unterschied zum HTML, das `no-store`
    bekommen MUSS, weil es den CSRF-Token des Benutzers enthaelt.
    """
    return FileResponse(
        str(pfad),
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


def _ist_oeffentlich(full_path: str) -> bool:
    """True fuer Seiten, die im Altcode ohne Anmeldung erreichbar sind."""
    if not full_path:
        return False
    m = re.match(r"^(registrierung|gast|organigramm)\b", full_path)
    return bool(m and m.group(1) in OEFFENTLICHE_EINTRAEGE)


def _public_entry(full_path: str) -> str | None:
    """Eintragsname (`registrierung`/`gast`) einer oeffentlichen Seite."""
    if not full_path:
        return None
    m = re.match(r"^(registrierung|gast)\b", full_path)
    return m.group(1) if m else None


def _oeffentliche_daten(seite: str, token: str) -> dict[str, Any]:
    """Werte fuer `window.__diakronos` der oeffentlichen Seiten (UXD-R1).

    Das Frappe-Original reichte den Jinja-Kontext der `www`-Seite durch
    (`token`, `linkFehler`, `felder`, `mitKinder`, `dokumente`). Im Standalone
    gibt es diese Seite nicht — die Werte werden hier aus dem Token gebildet,
    ueber genau dieselbe Fachpruefung, die auch das Absenden benutzt
    (`registrierung._validate_token`). Damit kann die Anzeige nicht von der
    Pruefung abweichen.

    Ein ungueltiger, abgelaufener oder voller Link ist KEIN Serverfehler: die
    Seite bleibt HTTP 200 und traegt `linkFehler` ("Zugang nicht moeglich").
    """
    daten: dict[str, Any] = {
        "token": "",
        "linkFehler": "",
        "felder": [],
        "mitKinder": 0,
        "dokumente": [],
        # N9b (H-1/M-1/M-2): die Texte, die der Person angezeigt werden — aus
        # derselben Quelle, aus der `submit_*` den Beleg-Snapshot bildet
        # (`gemeinde.wirksame_texte`). Angezeigt = gespeichert (Art. 7 DSGVO).
        "texte": _oeffentliche_texte(),
        # M-1: der gepflegte Willkommenstext erscheint ueber dem Formular.
        "willkommenstext": _willkommenstext(),
    }
    if not token:
        daten["linkFehler"] = "Kein Registrierungstoken angegeben."
        return daten

    # validate_token prüft die Adressgrenze selbst. Genau einmal zählen;
    # auch ein Redis-Ausfall wird hier zur lesbaren öffentlichen Fehlerseite.
    try:
        from diakronos_app.api.registrierung import validate_token as _validate

        antwort = _validate(token=token) or {}
    except Exception as exc:  # noqa: BLE001 — jede Verweigerung wird zur Linkmeldung
        # Eine Verweigerung (falscher/abgelaufener/voller Link) ist Normalfall
        # und bleibt still. Ein PROGRAMMIERfehler (fehlende Tabelle, kaputte
        # Abfrage) sieht fuer den Besucher gleich aus, darf aber nicht
        # unsichtbar sein — deshalb ins Log.
        from diakronos_app.frappe_compat.exceptions import (
            PermissionError as _FrappePermissionError,
        )

        if not isinstance(exc, _FrappePermissionError):
            # Befund 3 (P0-4b): KEIN Token im Log und KEIN `exc_info` — der
            # volle Treibertext kann den Token als SQL-Parameter tragen, und
            # ein gueltiger Token waere damit im Klartext protokolliert.
            # Ins Log gehoert nur die Fehlerklasse, nicht der Inhalt.
            logger.warning(
                "Registrierungslink konnte nicht geprueft werden (%s).",
                type(exc).__name__,
            )
        daten["linkFehler"] = _link_fehlermeldung(exc)
        return daten

    daten["token"] = token
    daten["felder"] = antwort.get("felder") or []
    daten["mitKinder"] = antwort.get("mit_kinder") or 0
    return daten


def _link_fehlermeldung(exc: Exception) -> str:
    """Verstaendlicher Text fuer einen abgelehnten Link (nie SQL/Stacktrace)."""
    text = str(exc or "").strip()
    if not text:
        return "Zugang nicht möglich."
    # Frappe-Exceptions tragen teils eine JSON-Huelle; nur die Meldung zeigen.
    if text.startswith("{") and '"message"' in text:
        try:
            geladen = json.loads(text)
            text = str(geladen.get("message") or text)
        except (TypeError, ValueError):
            pass
    return text



def _loese_build_datei(full_path: str) -> Path | None:
    """Loest einen URL-Pfad gegen das Build-Verzeichnis auf.

    `None` heisst: es gibt KEINE Datei zu diesem Pfad. Das ist die wichtige
    Aussage dieser Funktion — sie entscheidet, ob ein Pfad ein echtes
    Build-Artefakt ist oder eine (unbekannte) Seite der SPA.

    Vite `base` ist /diakonos/assets/, die Dateien liegen aber flach
    (Root, css/, chunks/, assets/). Aufloesung in zwei Stufen:
      a) Manifest-Index ueber den Basename (deckt alle Build-Artefakte,
         unabhaengig vom Unterverzeichnis ab).
      b) direkter Pfad (falls die Datei nicht im Manifest steht).
    """
    if not full_path or SPA_DIST is None:
        return None
    dist_root = SPA_DIST.resolve()

    index = _asset_index()
    # Der URL-Pfad ist relativ zu `base` (/diakonos/assets/); der Index ist
    # mit den Manifest-Namen (relativ zum Build-Root) verschluesselt. Beide
    # Schluesselformen probieren:
    #   - volle Manifest-Form:  'chunks/Home-x.js', 'assets/Inter.woff2'
    #   - blanker Dateiname:    'Home-x.js'
    for key in (full_path, full_path.rsplit("/", 1)[-1]):
        indexed = index.get(key)
        if indexed is not None:
            return indexed

    candidates = [dist_root / full_path]
    # Vite base ist '/diakonos/assets/', das Build-Root enthaelt aber selbst
    # ein Verzeichnis 'assets/' (Fonts). Dadurch entsteht die doppelte Form
    # 'assets/assets/<font>' -> einmal 'assets/' entfernen.
    if full_path.startswith("assets/"):
        rest = full_path[len("assets/"):]
        candidates.append(dist_root / rest)
        # css/ und chunks/ werden ebenfalls unter dem base-Praefix
        # /diakonos/assets/ referenziert.
        candidates.append(dist_root / "css" / rest)
        candidates.append(dist_root / "chunks" / rest)
        # 'assets/assets/<font>' -> dist/assets/<font>
        if rest.startswith("assets/"):
            candidates.append(dist_root / rest[len("assets/"):])
    for candidate in candidates:
        try:
            candidate.resolve().relative_to(dist_root)
        except ValueError:
            continue  # Path-Traversal-Versuch -> ignorieren
        if candidate.is_file():
            return candidate
    return None


def mount_spa(app: FastAPI) -> None:
    """Registriert die SPA-Auslieferung unter /diakonos.

    MUSS nach allen API-Routen aufgerufen werden: der Catch-all wuerde sonst
    spaeter registrierte Routen verdecken.
    """
    if SPA_DIST is None:
        logger.warning(
            "SPA-Build nicht gefunden (%s) — /diakonos liefert 503.",
            " | ".join(str(p) for p in _CANDIDATES),
        )

    # WICHTIG: KEIN staticfiles-Mount unter /diakonos/assets/.
    # Die Vite-Config setzt `base: '/diakonos/assets/'`, das Build-Ergebnis
    # legt die Dateien aber flach ab (Root: <entry>-<hash>.js, css/<name>.css,
    # chunks/<name>.js, assets/<font>). Ein Mount auf ein einzelnes
    # Unterverzeichnis (assets/) wuerde die uebrigen Pfade unter demselben
    # Praefix verschatten (Starlette probiert den Mount VOR dem Catch-all und
    # antwortet 404, statt an den Catch-all durchzureichen).
    # Stattdessen loest der Catch-all unten JEDEN Pfad gegen SPA_DIST auf —
    # inklusive Root-Dateien, css/ und chunks/. Das deckt alle Faelle ab und
    # behaelt die Sicherheitspruefung (kein Path-Traversal) an einer Stelle.

    # ── Altpfade der Frappe-www-Module (A1c5) ──────────────────────────────
    # Eigene Routen, KEIN Blanket ueber `/app` — siehe `_ist_altpfad`. Sie
    # werden VOR dem SPA-Catch-all registriert (beide stehen in dieser
    # Funktion, Reihenfolge = Prioritaet in Starlette).
    #
    # Das Anmeldegate ist hier ausdruecklich dieselbe Bedingung wie in
    # `spa_catch_all`: erst die Login-Maske, dann der Redirect. Wer ohne
    # Sitzung kommt, bekommt die Maske mit `redirect-to` auf den Altpfad
    # (das Formular in `render_login` nimmt den Pfad entgegen) — und NICHT
    # einen 404, der die Existenz des Moduls verraten wuerde.
    for _altpfad in sorted(_altpfad_redirects()):
        def _altpfad_view(
            request: Request,
            _altpfad: str = _altpfad,
            _ziel: str = _altpfad_redirects()[_altpfad],
        ) -> Response:
            if not ist_angemeldet():
                # Als `redirect-to` bekommt die Anmeldung den ALTpfad, nicht das
                # `#…`-Ziel: `_redirect_ziel` (auth.py) laesst nur pfadrelative
                # Ziele durch, und ein Fragment gehoert nicht in einen Pfad.
                # Nach dem Login steht die Sitzung fest, also greift derselbe
                # Aufruf erneut und leitet auf die SPA-Seite weiter.
                # SEC1: Mit OIDC fuehrt der Weg ueber /login (EIN Login); ohne
                # OIDC bleibt die Inline-Maske (Bestandsschutz).
                from diakronos_app.anmeldung.konfiguration import oidc_aktiv

                if oidc_aktiv():
                    from urllib.parse import quote

                    return RedirectResponse(
                        f"/login?redirect-to={quote(_altpfad, safe='')}", status_code=303
                    )
                return _login_maske(request, _altpfad)
            return RedirectResponse(
                f"{SPA_PREFIX}/{_ziel}", status_code=307
            )

        app.get(_altpfad, include_in_schema=False)(_altpfad_view)

    # ── Oeffentliche Altpfade (UXD-R3) ─────────────────────────────────────
    # Das Frappe-Original lieferte die Registrierungsseite unter `/registrierung`
    # aus; die in Altdaten gespeicherten `link_anzeige`-Werte zeigen genau
    # darauf. Der Standalone liefert nur `/diakonos/*` — ein kopierter Altlink
    # lief deshalb in einen 404. Diese beiden Routen leiten den Altpfad auf die
    # oeffentliche SPA-Seite um und BEHALTEN die Abfrage (`?token=…`); kein
    # Anmeldegate, denn die Ziele sind selbst oeffentlich.
    for _alt_oeff, _neu in (("/registrierung", "registrierung"), ("/gast", "gast")):
        def _oeff_alt_view(
            request: Request,
            _neu: str = _neu,
        ) -> Response:
            ziel = f"{SPA_PREFIX}/{_neu}"
            query = str(request.url.query or "")
            if query:
                ziel = f"{ziel}?{query}"
            return RedirectResponse(ziel, status_code=307)

        app.get(_alt_oeff, include_in_schema=False)(_oeff_alt_view)

    @app.get(f"{SPA_PREFIX}", include_in_schema=False)
    @app.get(f"{SPA_PREFIX}/{{full_path:path}}", include_in_schema=False)
    def spa_catch_all(request: Request, full_path: str = "") -> Response:
        # 1. Reservierte Praefixe NIE ausliefern (Sicherheitsnetz; die Routen
        #    oben greifen bereits, weil sie zuerst registriert sind).
        if full_path == "healthz" or full_path.startswith(
            ("api/", "docs", "redoc", "openapi.json")
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        # 2. Reale Build-Datei? Vite `base` ist /diakonos/assets/, die Dateien
        #    liegen aber flach (Root, css/, chunks/, assets/). Aufloesung in
        #    zwei Stufen:
        #    a) Manifest-Index ueber den Basename (deckt alle Build-Artefakte,
        #       unabhaengig vom Unterverzeichnis ab).
        #    b) direkter Pfad (falls Datei nicht im Manifest steht).
        #
        #    A1b2-rest Review: die Aufloesung laeuft BEWUSST VOR der
        #    Anmeldepflicht (Schritt 3), und nur was hier WIRKLICH aufloesbar
        #    ist, wird geliefert. Vorher entschied ein Regex ueber die
        #    Dateiendung (`_ist_asset_pfad`), ob die Sperre greift, und die
        #    SPA-Datei lieferte danach trotzdem index.html, wenn es keine
        #    Datei gab — `/diakonos/x.js` war ein anonymer Weg an der
        #    Anmeldepflicht vorbei. Jetzt gilt: eine echte Datei wird immer
        #    geliefert (wegen `SameSite=Lax` beim Nachladen der Assets darf
        #    sie nicht von der Sitzung abhaengen), alles andere ist eine
        #    Seite und faellt unter das Gate.
        if SPA_DIST is None:
            raise HTTPException(
                status_code=503,
                detail="SPA-Build nicht vorhanden — 'npm run build' in frontend/ ausfuehren.",
            )
        if full_path:
            # `_loese_build_datei` gibt None zurueck, wenn es die Datei nicht
            # gibt — dann ist der Pfad eine Seite und faellt an das Gate.
            echte_datei = _loese_build_datei(full_path)
            if echte_datei is not None:
                return _asset_response(echte_datei)

        # 3. Anmeldepflicht fuer die geschuetzten Seiten.
        #
        #    Quelle: referenz/.../diakonos/www/diakonos/index.py:16-18 (ohne
        #    Sitzung -> `redirect_location = "/login?redirect-to=/diakonos"`)
        #    und organigramm.py:14-16 (dasselbe ohne `redirect-to`).
        #    `registrierung` und `gast` sind dort `allow_guest = True` und
        #    bleiben deshalb oeffentlich — sonst waere der Anmeldelink aus der
        #    E-Mail der Gemeindeleitung tot, und niemand koennte sich
        #    ueberhaupt erst registrieren.
        #
        #    Hierher kommt nur, was KEINE Build-Datei ist. Deshalb ist die
        #    Entscheidung belastbar: es gibt keine Dateiendung mehr, die
        #    entscheidet, sondern nur noch die Frage "Seite oder Datei?".
        if not _ist_oeffentlich(full_path) and not ist_angemeldet():
            # SEC1: Ist OIDC aktiv (oder der lokale Login abgeschaltet), fuehrt
            # der Weg ueber die zentrale Anmeldung /login — EIN Login, bei
            # aktivem OIDC direkt zum Anbieter. OHNE OIDC bleibt alles wie
            # bisher: die Maske wird inline ausgeliefert (Bestandsschutz).
            from diakronos_app.anmeldung.konfiguration import oidc_aktiv

            ziel = f"{SPA_PREFIX}/{full_path}".rstrip("/") or SPA_PREFIX
            if oidc_aktiv():
                from urllib.parse import quote

                return RedirectResponse(
                    f"/login?redirect-to={quote(ziel, safe='')}", status_code=303
                )
            return _login_maske(request, ziel)

        # 4. Sonst: index.html (SPA-Hash-Routing)
        entry = "src/diakonos/main.js"
        # Unterseiten der SPA (registrierung/gast/organigramm) nutzen
        # eigene Entry-Punkte.
        m = re.match(r"^(registrierung|gast|organigramm)\b", full_path)
        if m:
            entry = f"src/{m.group(1)}/main.js"

        # UXD-R1: nur die OEFFENTLICHEN Seiten brauchen `window.__diakronos` —
        # die uebrigen lesen das Boot-Objekt. Der Token kommt aus `?token=`.
        oeffentlich = None
        seite = _public_entry(full_path)
        if seite is not None:
            oeffentlich = _oeffentliche_daten(seite, request.query_params.get("token") or "")
            antwort = _no_store(HTMLResponse(render_index(entry, oeffentlich=oeffentlich)))
            # Befund 11 (P0-4b): der Token steht in der URL. Ohne `no-referrer`
            # schickt der Browser ihn im `Referer` an JEDE fremde Ressource,
            # die die Seite laedt (Schriften, Bilder, Links). Die Kopfzeile
            # unterbindet genau das.
            antwort.headers["Referrer-Policy"] = "no-referrer"
            return antwort

        return _no_store(HTMLResponse(render_index(entry, oeffentlich=oeffentlich)))
