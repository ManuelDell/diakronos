"""Portierung von `diakronos.caldav.auth` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/caldav/auth.py` (24 LOC)

Original: HTTP Basic Auth gegen die Frappe-Nutzerdatenbank
(`frappe.utils.password.check_password`), Rueckgabe des Frappe-Usernamens
(E-Mail) oder `None`.

Seit Karte A1b3 ist die Passwortpruefung ECHT: `_check_credentials` liest den
Benutzer aus derselben `user`-Tabelle wie die SPA und prueft das Passwort mit
`frappe_compat.passwoerter.pruefe` — Frappe-`pbkdf2-sha256`-Hashes (importiert)
und Argon2 (neu gesetzt) unter einer Schnittstelle.

Der frueher hier stehende Zwischenstand (Dev-Modus ueber
`DIAKRONOS_CALDAV_AUTH_MODE` / `DIAKRONOS_CALDAV_DEV_PASSWORDS`) ist ERSATZLOS
ENTFALLEN. Es gibt keinen Schalter mehr, der CalDAV ohne echte Anmeldedaten
oeffnet.

Regel der Karte: **fail closed.** Ein offener CalDAV-Endpunkt gaebe saemtliche
Gemeindetermine ohne Login heraus. Deshalb gilt:

  * Ohne/mit ungueltigem Authorization-Header -> `None` -> 401.
  * Unbekannter Benutzer, kein hinterlegtes Passwort oder deaktiviertes Konto
    -> `None` -> 401 (identische Antwortform, kein Unterschied nach aussen).
  * Client-/Admin-Platzhalter (`guest`, `administrator`, `root`, `test`)
    bleiben gesperrt; sie sind keine anmeldbaren Kalender-Nutzer.

BRUTE-FORCE-SPERRE (Karte A1c2). CalDAV ist der **zweite** Zugang zu
denselben Konten, also galt hier bis A1c2 kein Limit: `curl -u` genuegte.
`get_authenticated_user` haengt sich deshalb in
`frappe_compat.loginversuche` ein — nicht in eine eigene Zaehlerlogik,
sondern in denselben Store:

  * **Eigene Zaehler, gemeinsame Sperre.** CalDAV zaehlt im Bereich
    `"caldav"` (`BEREICH_CALDAV`), der Login im Bereich `"login"`. Wer sich
    dreimal im Browser vertippt, sperrt damit seinen Kalender nicht (und
    umgekehrt). Die **Sperre** dagegen liegt unter `diakronos:anmeldesperre:`
    und gilt bereichsuebergreifend: wer dieselbe IP+Kennung durchprobiert,
    ist auch beim anderen Zugang durch — der zweite Weg ist keine Luecke an
    der ersten Sperre. Begruendung im Docstring von `loginversuche.py`.

  * **Gesperrt heisst 401 wie immer.** `unauthorized_response()` — gleiche
    Realm, gleicher Body, gleiche Kopfzeilen. Kein 429, kein `Retry-After`,
    kein Wort "gesperrt". Sichtbarkeit kostet die Sperre ihren Nutzen.

  * **Zeitangleichung vor der Passwortpruefung.** Gesperrt wird *vor*
    `_benutzer_aus_db`/`pruefe` geprueft, aber *nach* der Header-Formatpruefung
    (ein nicht dekodierbares `Authorization` zaehlt nicht — das ist kein
    Versuch, sondern ein kaputter Client). Damit der gesperrte Zweig nicht an
    der Antwortzeit erkennbar ist, verbraucht er dieselbe Zeit wie eine echte
    Pruefung: `_zeitleiche()` verifiziert einen echten Argon2-Dummy-Hash und
    verwirft das Ergebnis. **Alle drei** relevanten Faelle kosten damit
    dieselbe teure Ableitung und sind an der Zeit nicht unterscheidbar:
    gesperrt, unbekannter Benutzer (kein Hash zum Pruefen) und bekannter
    Benutzer mit falschem Passwort. Gemessen im Container: pbkdf2-falsch
    98,0 ms, Argon2-falsch 105,2 ms, unbekannt 102,8 ms, gesperrt 99,4 ms —
    Verhaeltnisse 0,94 bis 1,05.

  * **IP nur aus `request.client.host`**, bzw. aus `X-Forwarded-For` nur bei
    gesetztem `BEHIND_PROXY` — siehe `request_context.zaehler_client_ip()`.

Der Frappe-Username ist die E-Mail-Adresse: `diakronos_app.frappe_compat`
spricht Dokumente ueber `email`/`name` an (siehe `User`-Modell und
`permissions.get_roles`), das Original nutzt denselben Schluessel.
"""

from __future__ import annotations

import base64
import binascii
import logging

from starlette.requests import Request

from diakronos_app.frappe_compat import benutzer_status, loginversuche

logger = logging.getLogger("diakronos_app.auth")

# Original-Modulpfad (Dokumentation; nicht ueber `/api/method/*` erreichbar).
FRAPPE_MODULE = "diakronos.caldav.auth"

# Realm in der `WWW-Authenticate`-Kopfzeile — identisch zum Original.
REALM = 'Basic realm="Diakronos CalDAV"'

# Gesperrte Konten: `test` ist ein Frappe-Client-Platzhalter, `Root` und `Guest`
# sind keine anmeldbaren Benutzer, `Administrator` ist der Frappe-Superuser und
# KEIN Kalender-Personenkonto. Ein importierter Administrator-Hash darf CalDAV
# nicht oeffnen.
_BLOCKED_USERS = {"test", "root", "guest", "administrator"}

# Dummy-Hash fuer die Zeitangleichung. Er MUSS echt sein: ein von Hand
# geschriebener Hash wird vom Verifizierer sofort verworfen, ohne die teure
# Schluesselableitung zu durchlaufen — die Zeitangleichung waere dann
# wirkungslos (gemessen in A1c1: 0,025 ms gegen 86,7 ms). Er entsteht
# deshalb beim ersten Bedarf aus einem Zufallswert; das Klartextpasswort wird
# nie aufbewahrt. Er wird NICHT beim Import erzeugt, das wuerde jeden
# Prozessstart um ~90 ms verzoegern.
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    """Erzeugt den Dummy-Hash beim ersten Bedarf (nicht beim Import)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        import secrets

        from diakronos_app.frappe_compat.passwoerter import neuer_hash

        _DUMMY_HASH = neuer_hash(secrets.token_hex(16))
    return _DUMMY_HASH


def _zeitleiche() -> None:
    """Verbraucht die Zeit einer echten Argon2-Pruefung. Ergebnis verworfen.

    Damit ein gesperrter (und ein unbekannter) Versuch nicht daran erkennbar
    ist, dass er schneller antwortet als ein bekannter Benutzer mit falschem
    Passwort. Gleiche Idee wie `api/auth.py::_pruefe_dummy`.
    """
    from diakronos_app.frappe_compat.passwoerter import pruefe

    pruefe("zeitangleichung", _dummy_hash())



def _benutzer_aus_db(username: str):
    """Sucht `User` ueber `name` ODER `email` (Frappe akzeptiert beides).

    Rueckgabe ist das ORM-Objekt oder `None`. Reine Lesefunktion ohne
    Seiteneffekte; die Session wird hier geschlossen, das Ergebnis ist ein
    getrennter (`detached`) Datensatz, der nur noch gelesen wird.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        doc = sess.get(User, username)
        if doc is None and "@" in username:
            doc = sess.query(User).filter(User.email == username).one_or_none()
        if doc is None:
            return None
        # In einfache Werte entkoppeln, damit die Session gefahrlos schliessen
        # kann (kein Lazy-Load nach `close`).
        #
        # B1: `enabled` wird mitgeliefert, aber **nicht ausgewertet** — die
        # Regel, was ein aktives Konto ist, lebt an EINER Stelle
        # (`frappe_compat/benutzer_status.py::konto_ist_aktiv`). Diese Zeile
        # ist nur die Datengrundlage fuer diese Regel, nicht eine zweite.
        return {
            "name": doc.name,
            "email": doc.email,
            "enabled": bool(doc.enabled),
            "password_hash": doc.password_hash,
        }
    finally:
        sess.close()


def _check_credentials(username: str, password: str) -> bool:
    """Passwortpruefung gegen die `user`-Tabelle — der echte Benutzerspeicher.

    Original: `frappe.utils.password.check_password(username, password)` wirft
    bei falschem Passwort; hier ist das Ergebnis ein bool.

    Kein Passwort, unbekannter Benutzer, deaktiviertes Konto oder fehlender
    Hash -> `False`. Es gibt KEINEN Dev-Schalter mehr, der das umgeht.

    **Zeitangleichung (A1c2)**: Faelle, in denen es keinen Hash zum Pruefen
    gibt (unbekannter Benutzer, Platzhalter, deaktiviertes Konto, Konto ohne
    Passwort), laufen ueber `_zeitleiche()`. Sonst waere die Antwortzeit ein
    Kanal: die hashlosen Faelle antworten in Mikrosekunden, der Normalfall in
    ~100 ms. Der gesperrte Zweig in `get_authenticated_user` nimmt denselben
    Weg — gesperrt, unbekannt und deaktiviert sind damit zeitlich nicht
    unterscheidbar.

    Die Sperre selbst wird hier **nicht** geprueft: das passiert VOR dieser
    Funktion in `get_authenticated_user`, wo die Client-IP vorliegt.
    """
    if not username or not password:
        return False
    user = username.strip().lower()
    if user in _BLOCKED_USERS:
        # Platzhalter: kein DB-Zugriff, aber dieselbe Zeit wie alle anderen
        # Faelle ohne Pruefmöglichkeit.
        _zeitleiche()
        return False

    doc = _benutzer_aus_db(username.strip())
    # B1: Die Regel "existiert das Konto und ist es `enabled`" lebt an EINER
    # Stelle (`frappe_compat/benutzer_status.py`) und nicht hier und im
    # Login-Pfad zweimal. Hier kommt `konto_ist_aktiv` statt eines eigenen
    # `doc["enabled"]`, weil die Zeile ohnehin schon geladen ist — ein zweiter
    # Query pro Versuch waere in der Zeitangleichung oben messbarer Laerm.
    #
    # `_benutzer_aus_db` gibt deshalb ein **Modell-Diktat mit `enabled`**
    # zurueck (nicht die entkoppelten einfachen Werte): `konto_ist_aktiv`
    # braucht die Spalte, und sie darf hier nicht ein zweites Mal entstehen.
    if doc is None or not benutzer_status.konto_ist_aktiv(doc) or not doc["password_hash"]:
        _zeitleiche()
        return False

    from diakronos_app.frappe_compat.passwoerter import (
        muss_neu_gehasht_werden,
        neuer_hash,
        pruefe,
    )

    if not pruefe(password, doc["password_hash"]):
        return False

    from diakronos_app.anmeldung.passwortzugang import wechsel_noetig
    if wechsel_noetig(doc["name"]):
        return False

    # Hebung eines importierten Frappe-Hashes auf Argon2 — identisch zur
    # SPA-Anmeldung (`api/auth.py`), nur nach BESTANDENER Pruefung.
    if muss_neu_gehasht_werden(doc["password_hash"]):
        try:
            _hebe_auf_argon2(doc["name"], password)
        except Exception:  # noqa: BLE001 — Hebung ist optional, nie blockierend
            # Ein fehlgeschlagenes Upgrade darf einen gueltigen Login nicht
            # verhindern (z. B. read-only DB). Passwort wurde bereits geprueft.
            pass
    return True


def _hebe_auf_argon2(name: str, password: str) -> None:
    """Schreibt den Argon2-Hash des Klartexts zurueck (nur nach Pruefung)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        doc = sess.get(User, name)
        if doc is not None:
            doc.password_hash = neuer_hash(password)
            sess.commit()
    finally:
        sess.close()


def get_authenticated_user(request: Request) -> str | None:
    """
    Liest den Authorization-Header, prueft die Sperre (A1c2) und dann die
    Credentials gegen die user-Tabelle. Gibt den Frappe-Username (E-Mail)
    zurueck oder None bei Fehler.

    Reihenfolge — sie ist der Sicherheitskern dieser Funktion:

      1. **Header-Format.** Kein `Basic`, kein Base64, kein Doppelpunkt ->
         `None`, **ohne** zu zaehlen. Das ist kein Versuch, sondern ein
         kaputter Client; ein Angreifer, der zaehlt, indem er Muell schickt,
         wuerde sich selbst sperren (und die Sperre waere dann ein Werkzeug,
         DoS zu legen).
      2. **Sperre** (`loginversuche.pruefe_und_merke(..., bereich="caldav")`).
         Gesperrt -> `_zeitleiche()` (damit es nicht schneller antwortet als
         ein falsches Passwort), Audit-Log **nur** mit Pseudonymen, dann
         `None` -> 401. Auch das **richtige** Passwort hilft hier nicht.
      3. **Passwortpruefung** (`_check_credentials`).
      4. **Erfolg entlastet** den CalDAV-Zaehler (`loginversuche.entlaste`),
         damit ein Benutzer mit zwei Vertippern nicht ausgesperrt bleibt. Der
         Zaehler des **Login**-Bereichs wird dabei *nicht* angefasst — das
         waere ein Loch (wer ein gueltiges Passwort hat, koennte damit die
         Fehlversuche des anderen Zugangs wegraeumen). Und weil die Sperre
         VOR der Passwortpruefung greift, kann sie durch einen Erfolg gar
         nicht fallen: sie endet nur mit der Zeit (oder ueber
         `zuruecksetzen`, den Notfallweg aus dem Store).
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Basic '):
        return None

    try:
        decoded = base64.b64decode(auth[6:], validate=True).decode('utf-8')
        username, password = decoded.split(':', 1)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        # Formatfehler: zaehlt nicht (Schritt 1).
        return None

    benutzer = username.strip()
    client_ip = _client_ip(request)

    # ── A1c2 Schritt 2: Sperre vor der Passwortpruefung ───────────────────
    erlaubt, grund = loginversuche.pruefe_und_merke(
        benutzer or None, client_ip or None, bereich=loginversuche.BEREICH_CALDAV
    )
    if not erlaubt:
        # Zeitangleichung: die Sperre darf nicht daran erkennbar sein, dass
        # sie schneller antwortet als ein falsches Passwort.
        _zeitleiche()
        _audit_gesperrt(grund, benutzer, client_ip)
        return None

    if not _check_credentials(username, password):
        return None

    # Erfolg entlastet den CalDAV-Zaehler (nicht den des Login-Bereichs und
    # nicht die Sperre — die kann es hier gar nicht geben, weil sie vorher
    # geprueft wurde). Derselbe Grund wie im Login-Pfad (`api/auth.py`).
    loginversuche.entlaste(
        benutzer or None, client_ip or None, bereich=loginversuche.BEREICH_CALDAV
    )
    return username


def _client_ip(request: Request) -> str:
    """Die IP des Absenders — fail closed bezueglich `X-Forwarded-For`.

    Geht bewusst ueber `request_context.zaehler_client_ip()`, damit BEIDE
    Anmeldewege (Login und CalDAV) dieselbe IP-Bestimmung benutzen — eine
    zweite, abweichende Regel hier waere eine Luecke zwischen den beiden
    Zaehlern.

    Der Aufrufer ist ein `async`-Endpunkt, der Request-Kontext steht also
    ueber die `RequestContextMiddleware`. Fehlt er (Direktaufruf im Test
    ohne Middleware), nehmen wir die Adresse des Clients direkt.
    """
    from diakronos_app import request_context

    return (request_context.zaehler_client_ip() or (request.client.host if request.client else "")).strip()


def _pseudo(roh: str) -> str:
    """Pseudonym eines Bezeichners — `sha256:<hex>`, gesalzen mit `secret_key`.

    Dieselbe Form wie `api/auth.py::_pseudo` (und wie
    `api/audit_policy/anonymize.py::_hash_identifier`): ein Angreifer mit
    Zugriff auf das Audit-Log kann die Liste der Benutzer nicht gegen eine
    E-Mail-Liste testen, und der IP-Eintrag gibt keine Adressen preis.
    """
    if not roh:
        return ""
    import hashlib

    from diakronos_app.settings import settings

    salz = str(getattr(settings, "secret_key", "") or "")
    return "sha256:" + hashlib.sha256(f"{salz}|{roh.strip().lower()}".encode()).hexdigest()


def _audit_gesperrt(grund: str, benutzer: str, client_ip: str) -> None:
    """Audit-Eintrag fuer einen abgewiesenen CalDAV-Versuch — pseudonym.

    Identisch zu `api/auth.py::_audit_gesperrt`: kein Passwort, kein Hash,
    kein Klartextname, keine IP im Klartext. `actor` ist `Guest`, weil der
    Versuch ja ohne Sitzung kam.

    Schlaegt das Schreiben fehl, bleibt der Zugang gesperrt: der
    Audit-Eintrag ist Dokumentation, keine Sperrvoraussetzung.
    """
    try:
        from diakronos_app.frappe_compat.api_helpers import _create, _now

        _create(
            "Audit Log",
            {
                "zeitstempel": _now(),
                "action_typ": "Sonstiges",
                "actor": "Guest",
                "target_doctype": "User",
                "target_name": _pseudo(benutzer) or "unbekannt",
                "begruendung": (
                    "CalDAV-Zugang abgewiesen: Brute-Force-Sperre aktiv "
                    f"(Grund={grund or 'unbekannt'}, "
                    f"Benutzer={_pseudo(benutzer) or 'unbekannt'}, "
                    f"IP={_pseudo(client_ip) or 'unbekannt'})"
                ),
                "ip_address": _pseudo(client_ip) or None,
                "notification_gesendet": 0,
            },
        )
    except Exception as exc:  # noqa: BLE001 — Sperre darf nicht an der Logbuchhaltung haengen
        logger.warning(
            "Audit-Eintrag fuer abgewiesenen CalDAV-Versuch nicht moeglich: %s",
            exc.__class__.__name__,
        )


def unauthorized_response(message: str = "Authentication required"):
    """Antwortform des Originals: 401 + `WWW-Authenticate`.

    `werkzeug.wrappers.Response(..., headers={'WWW-Authenticate': ...})` ->
    `starlette.responses.Response` mit identischem Status, Body und Header.
    """
    from starlette.responses import Response

    return Response(
        message,
        status_code=401,
        headers={"WWW-Authenticate": REALM},
    )


__all__ = [
    "FRAPPE_MODULE",
    "REALM",
    "get_authenticated_user",
    "unauthorized_response",
]
