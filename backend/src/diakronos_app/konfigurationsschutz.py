"""SEC-DEF1 — Pruefung auf unsichere Standardwerte.

Hintergrund: Secret-Scan der oeffentlichen Repos (10.11.). `settings.py`
hatte einen einkompilierten Platzhalter-Schluessel (`insecure-dev-key`) und
eine `DATABASE_URL` mit bekanntem Passwort (`diakronos:diakronos`). Wer ohne
`.env` startet, bekommt damit faelschbare Sitzungs-Cookies/Tokens und eine
Datenbank mit oeffentlich bekanntem Passwort — und merkt es nicht.

Die Pruefung laeuft ZWEIMAL, mit Absicht:

  * **beim Anlegen der Settings** (`Settings.keine_unsicheren_standardwerte`,
    Modellpruefung) — damit kein Prozess mit den Werten ueberhaupt entsteht,
    auch nicht ein Worker oder ein Scheduler;
  * **in der Startpruefung des Entrypoints**
    (`diakronos_app.anmeldung.startup`), die daraus eine klare deutsche
    Meldung mit Exit-Code 1 macht, statt eines pydantic-Validierungsfehlers.

Erlaubt bleiben die Platzhalter, wenn ausdruecklich eine Entwicklungs- oder
Testumgebung gesetzt ist: `APP_ENV=development`, `APP_ENV=test` oder
`APP_ENV=dev` (Gross-/Kleinschreibung und Leerzeichen egal). Alles andere —
`prod`, `production`, `staging` und **auch ein fehlendes `APP_ENV`** — ist
Betrieb und wird hart abgewiesen.

SEC-DEF2 (26.11.): Die Ausnahme haengt an einem AUSDRUECKLICH gesetzten Wert.
Fehlt `APP_ENV`, gilt Betrieb — vorher war der Default `development`, damit war
die Pruefung in jeder Standardinstallation wirkungslos (wer ohne `.env`
startet, startet ohne Pruefung).

Keine Werte in der Meldung: das Passwort wird nur als „das bekannte
Standard-Passwort\" benannt, nie ausgedruckt.
"""

from __future__ import annotations

# Der einkompilierte Platzhalter aus `settings.py`. Bleibt dort stehen, damit
# lokale Laeufe ohne `.env` funktionieren — er ist ab hier aber nur noch in
# `development`/`test` zulaessig.
PLATZHALTER_SECRET_KEY = "insecure-dev-key"

# Das Passwort des Default-Datenbankbenutzers (oeffentlich im Repo).
DEFAULT_DB_PASSWORT = "diakronos"

# Ab hier gilt ein Schluessel als stark genug (32 Zeichen = 128 Bit bei
# base64/hex-Ausgabe; kuerzere Werte sind fuer HMAC-Sitzungscookies zu duenn).
MINDESTLAENGE_SECRET_KEY = 32

# Umgebungen, in denen die unsicheren Defaults erlaubt bleiben — nur wenn
# APP_ENV AUSDRUECKLICH so gesetzt ist. Ein fehlender Wert ist NICHT dabei:
# dann gilt Betrieb (SEC-DEF2).
ENTWICKLUNGS_UMGEBUNGEN = frozenset({"development", "test", "dev"})


def ist_entwicklung(app_env: str) -> bool:
    """True, wenn `APP_ENV` AUSDRUECKLICH eine Entwicklungs-/Testumgebung bezeichnet.

    Ein fehlender/leerer Wert ist Betrieb (SEC-DEF2) — vorher galt der Default
    `development` und die Pruefung war in jeder Standardinstallation wirkungslos.
    """
    return str(app_env or "").strip().lower() in ENTWICKLUNGS_UMGEBUNGEN


def secret_key_ist_ein_wiederholtes_zeichen(secret_key: str) -> bool:
    """True, wenn der Schluessel aus EINEM einzigen, wiederholten Zeichen besteht.

    M3 (ABN-1b): ``"a" * 32`` oder ``"0" * 64`` besteht die Laengenpruefung,
    ist aber kein Geheimnis — so sieht ein Wert aus, den jemand „auf 32 Zeichen
    aufgefuellt" hat. Erlaubt bleiben alle Schluessel mit mindestens zwei
    verschiedenen Zeichen (auch ein echter Hex-Schluessel mit zufaelligen
    Wiederholungen).
    """
    wert = str(secret_key or "").strip()
    return bool(wert) and len(set(wert)) == 1


def secret_key_ist_unsicher(secret_key: str) -> bool:
    """True fuer den Platzhalter, leere Werte, zu kurze Werte und aufgefuellte
    Schluessel aus einem einzigen wiederholten Zeichen (M3)."""
    wert = str(secret_key or "").strip()
    if wert == PLATZHALTER_SECRET_KEY:
        return True
    if secret_key_ist_ein_wiederholtes_zeichen(wert):
        return True
    return len(wert) < MINDESTLAENGE_SECRET_KEY


def database_url_hat_default_passwort(database_url: str) -> bool:
    '''True, wenn die Verbindung kein oder das bekannte Standard-Passwort benutzt.

    Geprueft wird das Passwort in BEIDEN Formen, in denen es in einer
    Verbindungszeichenfolge stehen kann:

      * in der Benutzerinfo  ``…://benutzer:PASSWORT@…``
      * als Abfrage-Parameter ``…?password=PASSWORT`` (auch ``passwd``/``pwd``)

    Es zaehlt das PASSWORT, nicht der Benutzer. URL-kodierte Varianten (``%6F``)
    werden dekodiert. Gross-/Kleinschreibung wird NICHT unterschieden
    (``DIAKRONOS`` ist dasselbe oeffentlich bekannte Passwort).

    M3 (ABN-1b) — drei Luecken geschlossen:

      * ``…://benutzer@db/x`` (Benutzer OHNE Doppelpunkt) ist ein
        Datenbankbenutzer ohne Passwort und war vorher unbeanstandet; er zaehlt
        jetzt wie ein leeres Passwort. Eine URL ganz OHNE Benutzerinfo
        (``…://db/x``) hat dagegen weder Benutzer noch Passwort — der Server
        verlangt dann selbst Authentifizierung — und bleibt unbeanstandet.
      * ``…?password=diakronos`` wurde vorher gar nicht angesehen.
      * ``DIAKRONOS``/``Diakronos`` ging durch, weil nur exakt verglichen wurde.

    Absichtlich OHNE ``urlsplit``: (a) den Treiber-Zusatz
    ``postgresql+psycopg://`` kennt es nicht und liefert ``netloc=""`` — die
    Pruefung waere dann STILL wirkungslos, genau der Fehler, den sie
    verhindern soll; (b) die Zerlegung ist so kurz, dass sie hier offen im
    Code steht.

    Eine leer gelassene Benutzerinfo (``…://benutzer:@db/…``) gilt wie das
    Standard-Passwort: Compose setzt ``DATABASE_URL`` aus
    ``POSTGRES_PASSWORD`` zusammen; ist das Passwort leer, entsteht genau
    derselbe Datenbankbenutzer mit genau demselben (bekannten) Passwort.
    '''
    from urllib.parse import parse_qsl, unquote

    roh = str(database_url or "").strip()
    if not roh or "://" not in roh:
        return False
    rest = roh.split("://", 1)[1]
    autoritaet, _, nach = rest.partition("/")
    _, _, abfrage = nach.partition("?")
    gefunden: list[str] = []

    # 1) Passwort in der Benutzerinfo (alles vor dem LETZTEN `@`; ein Passwort
    #    darf `@` kodiert enthalten, unkodiert waere die URL ohnehin ungueltig).
    if "@" in autoritaet:
        benutzerinfo = autoritaet.rsplit("@", 1)[0]
        if ":" in benutzerinfo:
            gefunden.append(unquote(benutzerinfo.split(":", 1)[1]))
        else:
            # Benutzer ohne Passwort (`diakronos@db`): kein Passwort gesetzt.
            gefunden.append("")

    # 2) Passwort als Abfrage-Parameter. `parse_qsl` ist hier zulaessig — ob ein
    #    Treiber-Zusatz davorsteht, ist fuer die Abfrage egal.
    for name, wert in parse_qsl(abfrage, keep_blank_values=True):
        if name.strip().lower() in ("password", "passwd", "pwd"):
            gefunden.append(wert)

    if not gefunden:
        return False
    # Ein mitgegebener Wert, der weder leer ist noch das Standard-Passwort, ist
    # ein eigenes Geheimnis — auch wenn an anderer Stelle `diakronos` steht.
    for w in gefunden:
        eigenes = bool(w.strip()) and w.strip().lower() != DEFAULT_DB_PASSWORT
        if eigenes:
            return False
    return True


def demo_schalter_im_betrieb(
    app_env: str, devmode_enabled: bool, doku_oeffentlich: bool
) -> list[str]:
    """SEC-DEF2: Demo-/Diagnose-Schalter, die im Betrieb aus sein muessen.

    `DEVMODE_ENABLED` (roter Rahmen, Element-Auswahl, Befunde, Backend-
    Ueberwachung) und `SEC_DOKU_OEFFENTLICH` (Swagger/ReDoc/OpenAPI) sind
    Entwicklungs-Werkzeuge. Sie sind standardmaessig AUS und schalten sich
    NICHT selbst ab — wer sie einschaltet, meint es. Deshalb ist das eine
    Warnung und KEIN Startverbot: eine bestehende Installation mit
    eingeschaltetem Dev-Modus soll nach dem Update weiter starten.

    Es gibt weiterhin keinen Schalter `TESTSUITE_ENABLED`/`DEVMODE`, der die
    Startpruefung umginge (im Repo am 26.11. geprueft: kein solcher Name).
    """
    if ist_entwicklung(app_env):
        return []
    hinweise: list[str] = []
    if devmode_enabled:
        hinweise.append(
            "DEVMODE_ENABLED=1 ist im BETRIEB eingeschaltet — das liefert "
            "Entwicklungs-Endpunkte und ein Overlay an alle Tester. Fuer den "
            "Betrieb ausschalten (DEVMODE_ENABLED=0)."
        )
    if doku_oeffentlich:
        hinweise.append(
            "SEC_DOKU_OEFFENTLICH=1 ist im BETRIEB eingeschaltet — /docs, "
            "/redoc und /openapi.json legen alle Pfade offen. Fuer den "
            "Betrieb ausschalten (SEC_DOKU_OEFFENTLICH=0)."
        )
    return hinweise


def unsichere_standardwerte(
    app_env: str, secret_key: str, database_url: str
) -> list[str]:
    """Liefert die Beanstandungen (leer = in Ordnung).

    Nur bei AUSDRUECKLICH gesetztem `development`/`test`/`dev` wird nichts
    beanstandet — dort sind die Defaults gewollt. Ein fehlendes `APP_ENV` ist
    Betrieb (SEC-DEF2) und wird geprueft.
    """
    if ist_entwicklung(app_env):
        return []

    probleme: list[str] = []
    wert = str(secret_key or "").strip()
    if wert == PLATZHALTER_SECRET_KEY:
        probleme.append(
            "SECRET_KEY ist noch der einkompilierte Platzhalter. "
            "Einen eigenen Schluessel erzeugen (openssl rand -hex 32) und in "
            ".env eintragen."
        )
    elif secret_key_ist_ein_wiederholtes_zeichen(wert):
        probleme.append(
            "SECRET_KEY besteht aus einem einzigen wiederholten Zeichen — das "
            "ist kein Geheimnis (so sieht ein aufgefuellter Platzhalter aus). "
            "Einen eigenen Schluessel erzeugen (openssl rand -hex 32) und in "
            ".env eintragen."
        )
    elif len(wert) < MINDESTLAENGE_SECRET_KEY:
        probleme.append(
            f"SECRET_KEY ist zu kurz ({len(wert)} Zeichen, mindestens "
            f"{MINDESTLAENGE_SECRET_KEY} noetig). "
            "Einen eigenen Schluessel erzeugen (openssl rand -hex 32) und in "
            ".env eintragen."
        )

    if database_url_hat_default_passwort(database_url):
        probleme.append(
            "DATABASE_URL enthaelt das bekannte Standard-Passwort der "
            "Datenbank. Ein eigenes Passwort setzen (POSTGRES_PASSWORD, "
            "z. B. openssl rand -base64 24)."
        )

    return probleme
