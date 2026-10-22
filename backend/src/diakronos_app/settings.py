"""Konfiguration — liest alle Werte aus Umgebungsvariablen / .env."""

from functools import lru_cache

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://diakronos:diakronos@db:5432/diakronos"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "insecure-dev-key"

    # Existing calendar CRUD/read/UI use offsetless local wall times. Imports
    # convert aware instants to this zone, never the container's OS timezone.
    calendar_timezone: str = "Europe/Berlin"

    @field_validator("calendar_timezone")
    @classmethod
    def valid_calendar_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("CALENDAR_TIMEZONE must be a valid IANA timezone") from None
        return value

    # Healthcheck-Zeitbudget in Sekunden fuer die einzelnen Verbindungstests.
    healthcheck_timeout: float = 5.0

    # P2c: Ablage der hochgeladenen Dateien (Dateisystem, NICHT die DB).
    # Im Container zeigt das auf das Volume /data/files.
    files_dir: str = "/data/files"
    # ── BACKUP-1: eigene Datensicherung ─────────────────────────────────────
    # Ablage der Sicherungen. MUSS unterhalb eines Bind-Mounts liegen (Default
    # `/data/sicherungen`, also im selben Datenbaum wie `files_dir`) — sonst
    # landet der Dump im Image-Dateisystem und ist beim naechsten Container
    # verloren (NACHTRAG DOCKER Punkt 4). Wird beim Sichern geprueft.
    backup_dir: str = "/data/sicherungen"
    # Aufbewahrung, solange in der Oberflaeche nichts anderes eingestellt ist.
    # Der geltende Wert steht in der Datenbank (Tabelle
    # `sicherungseinstellungen`); das hier ist nur die Erstbelegung.
    backup_aufbewahrung_tage: int = Field(
        30,
        validation_alias=AliasChoices(
            "BACKUP_AUFBEWAHRUNG_TAGE", "backup_aufbewahrung_tage"
        ),
    )
    backup_uhrzeit: str = Field(
        "03:00",
        validation_alias=AliasChoices("BACKUP_UHRZEIT", "backup_uhrzeit"),
    )
    backup_automatisch: bool = Field(
        True,
        validation_alias=AliasChoices("BACKUP_AUTOMATISCH", "backup_automatisch"),
    )
    # Zeitbudget eines Sicherungslaufs in Sekunden. Danach gilt der Lauf als
    # fehlgeschlagen; ein haengender `pg_dump` darf die Sperre nicht ewig
    # halten. 0 = kein eigenes Limit (nur das des Aufrufers).
    backup_timeout_sekunden: int = Field(
        1800,
        validation_alias=AliasChoices(
            "BACKUP_TIMEOUT_SEKUNDEN", "backup_timeout_sekunden"
        ),
    )
    # Verbindung des Dumps, wenn der laufende Dienst die Datenbank NICHT unter
    # dem Namen aus DATABASE_URL erreicht. Leer = Name aus DATABASE_URL.
    #
    # Gruende fuer die eigenen Variablen: der dump laeuft in app UND scheduler,
    # und beide haengen am Compose-Netz — `db` ist also aufloesbar (im Teststack
    # am 2026-10-20 geprueft). Fuer abweichende Verdrahtungen (Datenbank
    # ausserhalb des Compose-Netzes) lassen sich Host/Port/Name/Benutzer/
    # Passwort hier unabhaengig von DATABASE_URL stellen. Compose setzt
    # dieselben Werte wie `DATABASE_URL` (Host/Port/Benutzer/Passwort/
    # Datenbank heissen hier nur anders). Das Passwort bleibt ein einziges:
    # es kommt aus derselben Quelle (${POSTGRES_PASSWORD}) und steht nirgends
    # doppelt in der .env.
    backup_db_host: str = Field(
        "", validation_alias=AliasChoices("BACKUP_DB_HOST", "backup_db_host")
    )
    backup_db_port: int = Field(
        0, validation_alias=AliasChoices("BACKUP_DB_PORT", "backup_db_port")
    )
    backup_db_name: str = Field(
        "", validation_alias=AliasChoices("BACKUP_DB_NAME", "backup_db_name")
    )
    backup_db_user: str = Field(
        "", validation_alias=AliasChoices("BACKUP_DB_USER", "backup_db_user")
    )
    backup_db_password: str = Field(
        "", validation_alias=AliasChoices(
            "BACKUP_DB_PASSWORD", "backup_db_password"
        ),
    )
    # Groessenlimit fuer `/api/method/upload_file` in Bytes (Default 10 MB).
    max_upload_bytes: int = 10 * 1024 * 1024
    # ST2: eigenes, hoeheres Limit fuer Audio-Material (Notenbeispiele,
    # Aufnahmen) in Bytes. Default 50 MB — Musikdateien sprengen das
    # allgemeine 10-MB-Limit. Achtung: ein vorgelagerter Reverse-Proxy
    # (NPM/Nginx) braucht ein passendes `client_max_body_size`.
    max_upload_bytes_audio: int = 50 * 1024 * 1024

    # ── DM1: Dev-Modus ─────────────────────────────────────────────────────
    # Schalter des Dev-Modus (roter Rahmen, Element-Auswahl, Befunde,
    # Backend-Ueberwachung, Bericht). **Default AUS**: ohne diesen Wert
    # existieren weder Endpunkte noch Middleware noch Overlay — eine normale
    # Installation bekommt nichts davon zu sehen.
    # Beim Einschalten: Rolle "Tester" vergeben (oder Administrator sein) und
    # `DEVMODE_ENABLED=1` in `.env` setzen (siehe BETRIEBSANLEITUNG.md).
    devmode_enabled: bool = False

    # ── A1b1: Sitzungs-Schicht ──────────────────────────────────────────────
    # `Secure`-Flag am Session-Cookie. Der Stack laeuft ohne TLS-Terminator
    # Drei Zustaende, Default `auto`:
    #   "auto"  — `Secure` genau dann, wenn der Request ueber HTTPS kam
    #             (`X-Forwarded-Proto: https` bzw. das Request-Schema).
    #   "true"  — immer `Secure`. Nur sinnvoll, wenn TLS garantiert ist.
    #   "false" — nie `Secure`. Nur fuer reine HTTP-Testaufbauten.
    # Warum nicht schlicht an oder aus: mit `true` verwirft der Browser das
    # `sid`-Cookie auf dem internen HTTP-Stack, der Login waere STILL kaputt.
    # Mit `false` als Dauerzustand ginge das Sitzungs-Cookie bei einer fremden
    # Gemeinde hinter TLS unverschluesselt ueber die Leitung. `auto` trifft in
    # beiden Faellen die richtige Wahl, ohne dass jemand etwas einstellen muss.
    session_cookie_secure: str = "auto"
    # Lebensdauer einer Sitzung in Sekunden (24 h); Redis-TTL beim Anlegen
    # und beim Verlaengern.
    session_ttl_seconds: int = 86400
    # Startbenutzer fuer die Erstinstallation. Beide Werte leer -> es wird
    # KEIN Benutzer angelegt (die App bleibt beim Administrator-Platzhalter,
    # siehe Karte A1b2).
    admin_email: str | None = None
    admin_password: str | None = None

    # ── B1: Frist, bis zu der ein gesperrtes Konto noch durchkommt ─────────
    # TTL des Redis-Caches, in dem `frappe_compat/benutzer_status.py` das
    # Ergebnis von "existiert der Benutzer noch und ist er `enabled`"
    # haelt. Solange eine Sitzung aus dem Cookie aufgeloest wird, ist das
    # die **gesamte** Verzoegerung, mit der eine Deaktivierung von aussen
    # (Direktabfrage in der DB) durchschlaegt.
    #
    # Der Weg von innen ist davon nicht betroffen: `delete_my_data` und
    # jede andere Stelle, die `enabled` schreibt, ruft
    # `benutzer_status.widerrufe_sitzungen()` — das vergisst den Cache UND
    # loescht die Sitzungen, also 0 Sekunden (siehe Modulkopf dort).
    #
    # **Fail closed, und das ist hier eine Zahl mit einer Richtung:** die
    # Frist darf nicht verlaengert werden, um Abfragen zu sparen. Sie ist
    # das, was die Karte als "~30 s" erlaubt. Default 30.
    #
    # Zusaetzlich klemmt `benutzer_status._ttl()` den Wert auf mindestens
    # 1 Sekunde: `ex=0` waere in Redis "sofort abgelaufen", `ex=-1` ein
    # dauerhaftes Aufheben der Frist. Beides waere eine Frist, die nicht
    # aussieht wie eine. Ein Wert > 30 ist bewusst moeglich (der Betreiber
    # darf entscheiden) — aber `test_der_status_cache_hat_die_dokumentierte_frist`
    # laeuft dann rot, und das ist der Moment, in dem es auffaellt.
    benutzerstatus_ttl: int = Field(
        30,
        validation_alias=AliasChoices(
            "BENUTZERSTATUS_TTL", "benutzerstatus_ttl"
        ),
    )

    # ── A1c1: Brute-Force-Sperre fuer die Login ─────────────────────────────
    # Fehlversuche, nach denen der Versuch fuer `login_sperre_sekunden`
    # gesperrt ist. Gilt je Benutzer UND je Client-IP; sperrt, sobald EINE
    # der beiden Schwellen erreicht ist.
    #
    # Warum der Default nicht grosszuegiger ist: 5 Versuche sind fuer einen
    # Menschen mit Vertippern reichlich, und ein Angreifer, der es auf 5
    # Versuche anlegt (statt 1000), verliert seine Rate. Wer haeufiger
    # danebenliegt, soll den Wert in `.env` erhoehen — die Sperre ist
    # BEGRENZT (Backoff), eine zu niedrige Schwelle bestraft am Ende
    # nur ehrliche Benutzer.
    login_max_versuche: int = 5
    # ── A1c10: Zwei Schwellen statt einer — und die Proxy-Regel ─────────────
    # Fehlversuche je **Adresse**, bis die Adresse gesperrt wird (Default 25).
    #
    # Warum 25 und nicht 5: fuenf Fehlversuche sind am **Konto** genau
    # richtig — sie treffen den, der sich vertippt hat. An einer **Adresse**
    # ist dieselbe Zahl eine Katastrophe: eine Gemeinde hat typischerweise
    # einen Internetanschluss, hinter einem Reverse-Proxy ist die Adresse die
    # des Proxies, im LAN die des Routers. Fuenf Fehlversuche einer Person
    # sperren dort **alle** — und der Zustand laesst sich nicht einmal einem
    # Benutzer zuordnen.
    #
    # 25 ist die Sammelsperre gegen jemanden, der **viele Konten**
    # durchprobiert (Credential Stuffing). Fuer einen Angreifer kostet das
    # fast nichts, fuer Menschen hinter einem gemeinsamen Anschluss praktisch
    # nie — und die Kontosperre (5) greift in jedem Fall.
    # Die Aliase sind hier nicht Dekoration, sondern Pflicht — dieselbe
    # Lehre wie bei `werkzeuglimit_entsperren` (A1c3, gemessen):
    # `pydantic-settings` findet eine ENV ueber den **Feldnamen**, und
    # `case_sensitive=False` vergleicht dabei nur die Schreibweise, es setzt
    # kein Trennzeichen dazwischen. `LOGIN_MAX_VERSUCHE` trifft
    # `login_max_versuche` (reines underscore), `WERKZEUGLIMIT_ENTSPRERREN`
    # traf `werkzeuglimit_entsperren` **nicht**. Ohne Aliases waere eine
    # gesetzte ENV still unwirksam — und der Betreiber haelt sie fuer
    # gesetzt, weil die Doku sie erwaehnt. Genau das ist der schlimmste Fall.
    login_max_versuche_ip: int = Field(
        25,
        validation_alias=AliasChoices(
            "LOGIN_MAX_VERSUCHE_IP", "login_max_versuche_ip"
        ),
    )
    # Ausnahme von der Proxy-Regel (A1c10): **eigene** Adressen (Loopback,
    # privat, link-local, unspecified) werden nie gesperrt und nicht mal
    # gezaehlt. Auf 1 stellt man das nur, wenn man die eigene Infrastruktur
    # bewusst sperren will — und das trifft dann **alle** Benutzer hinter
    # dieser Adresse, also praktisch das ganze Buero. Begruendung ausfuehrlich
    # in `frappe_compat/loginversuche.py` (`_ist_eigene_adresse`).
    login_ip_sperre_auch_privat: bool = Field(
        False,
        validation_alias=AliasChoices(
            "LOGIN_IP_SPERRE_AUCH_PRIVAT", "login_ip_sperre_auch_privat"
        ),
    )
    # Grunddauer der Sperre in Sekunden (5 min).
    login_sperre_sekunden: int = 300
    # Backoff-Deckel: nach der Sperre waechst die Sperrzeit mit jedem weiteren
    # Versuch exponentiell (2x, 4x, 8x, ...) bis zu diesem Faktor der
    # Grunddauer. Ohne das reicht ein Rhythmus von `login_sperre_sekunden`
    # fuer einen endlosen Durchlauf — 12 Versuche/Stunde sind ein vollstaendiger
    # Zahllisten-Durchlauf ueber Nacht. 16 x 5 min = 80 min Hoechstdauer.
    login_sperre_max_faktor: int = 16

    # ── A1c2: Reverse-Proxy als Voraussetzung ───────────────────────────────
    # Steht hinter der App ein Reverse-Proxy (Nginx, Traefik, Caddy …), ist
    # `request.client.host` fuer ALLE Benutzer dieselbe Proxy-Adresse. Der
    # IP-Zaehler der Anmeldesperre waere dann nach fuenf Fehlversuchen
    # eines Menschen fuer die ganze Gemeinde tot.
    #
    # Nur wenn dieser Schalter an ist, wird `X-Forwarded-For` fuer den
    # IP-Zaehler ausgewertet. Default ist `false` — **fail closed**: ohne den
    # Schalter vertrauen wir dem Header nicht, weil ihn jeder Client selbst
    # setzen darf und die IP-Sperre sonst per Kopfzeile aufzuheben waere.
    # Die Kehrseite ist bewusst gewaehlt: hinter einem nicht markierten Proxy
    # ist die IP-Sperrung schaerfer als noetig (sie trifft alle), aber sie
    # wird nicht umgehbar. Das ist die richtige Richtung.
    behind_proxy: bool = False

    # ── A1c6: Rate-Limit des Entschperr-Werkzeugs ─────────────────────────
    # Das manuelle Freigeben ist ein Verwaltungsakt. Ohne Begrenzung waere ein
    # uebernommenes Administrator-Konto der Knopfdruck fuer die Wiederfreigabe
    # eines beliebigen Kontos — also genau die Sperre, die A1c1 gebaut hat,
    # nur mit dem falschen Vorzeichen.
    #
    # 10 Freigaben je 10 Minuten: reicht fuer den Betrieb (die wenigen echten
    # Faelle am Tag) und ist fuer einen Durchlauf zu teuer. Gilt je
    # Administrator-KONTO, nicht je Sitzung — ein Relog setzt es sonst zurueck,
    # und genau das waere der Umweg, den ein Angreifer nimmt.
    #
    # **Fail closed**: 0 bedeutet "keine Grenze" und ist hier der bewusst
    # schlechtere Wert. Wer eine bestehende Installation hochfaehrt, bekommt die
    # Begrenzung also automatisch, ohne etwas tun zu muessen.
    #
    # WICHTIG — `validation_alias` ist hier nicht Dekoration, sondern Pflicht.
    # `pydantic-settings` findet eine Umgebungsvariable ueber den
    # **Feldnamen**. `case_sensitive=False` vergleicht dabei nur
    # Gross-/Kleinschreibung, es setzt kein Trennzeichen dazwischen. Manche
    # Felder treffen ihre Schreibweise trotzdem, andere nicht — und das ist
    # nicht vorhersehbar. **An dieser Klasse gemessen**, nicht geraten:
    #     LOG_LEVEL=DEBUG             -> log_level == "DEBUG"                (trifft)
    #     LOGIN_MAX_VERSUCHE=9        -> login_max_versuche == 9            (trifft)
    #     WERKZEUGLIMIT_ENTSPRERREN=7 -> werkzeuglimit_entsperren == 10     (GREIFT NICHT)
    # Der dritte Fall ist der Grund fuer die Aliasse hier: ohne sie waere die
    # von der Karte geforderte ENV-Schaltbarkeit still unwirksam, und ein
    # Betreiber, der das Limit schaerfen will, haelt es fuer gesetzt — der
    # schlimmste Fall, weil er nicht auffaellt. `AliasChoices` nimmt beide
    # Schreibweisen an; die Kleinschreibung bleibt als zweite Wahl erhalten,
    # damit `.env` und direkter Python-Zugriff weiter funktionieren.
    werkzeuglimit_entsperren: int = Field(
        10,
        validation_alias=AliasChoices(
            "WERKZEUGLIMIT_ENTSPRERREN", "werkzeuglimit_entsperren"
        ),
    )
    werkzeuglimit_entsperren_fenster: int = Field(
        600,
        validation_alias=AliasChoices(
            "WERKZEUGLIMIT_ENTSPRERREN_FENSTER", "werkzeuglimit_entsperren_fenster"
        ),
    )

    # ── P0-4b: Ratenbegrenzung der OEFFENTLICHEN Registrierung ──────────────
    # Dieselbe Bauform wie die Loginbremse (A1c1/A1c10), aber eigene Schwellen:
    # die anonymen Endpunkte `validate_token`, `submit_registrierung` und
    # `submit_gast` hatten KEINE Bremse — ein Skript konnte die
    # Admin-Warteschlange fluten und einen Link leerlaufen lassen. Begruendung
    # ausfuehrlich in `anmeldung/registrierungsbremse.py`.
    #
    #   registrierung_max_ip    Absendeversuche je Adresse und Fenster
    #   registrierung_max_link  Absendeversuche je Link und Fenster
    #   registrierung_max_validierung  Tokenpruefungen (Seitenaufruf) je Adresse
    #   registrierung_fenster_sekunden  Laenge des Fensters (fest, laeuft nicht mit)
    #
    # `validation_alias` ist wie bei den uebrigen Feldern Pflicht: ohne Alias
    # findet pydantic-settings eine ENV nur zufaellig (gemessen, siehe oben).
    # `0` heisst ausdruecklich "unbegrenzt" — der Default ist die Grenze.
    registrierung_max_ip: int = Field(
        10,
        validation_alias=AliasChoices("REGISTRIERUNG_MAX_IP", "registrierung_max_ip"),
    )
    registrierung_max_link: int = Field(
        20,
        validation_alias=AliasChoices("REGISTRIERUNG_MAX_LINK", "registrierung_max_link"),
    )
    registrierung_max_validierung: int = Field(
        60,
        validation_alias=AliasChoices(
            "REGISTRIERUNG_MAX_VALIDIERUNG", "registrierung_max_validierung"
        ),
    )
    registrierung_fenster_sekunden: int = Field(
        3600,
        validation_alias=AliasChoices(
            "REGISTRIERUNG_FENSTER_SEKUNDEN", "registrierung_fenster_sekunden"
        ),
    )

    # ── Mailversand (DSGVO-1 D3, seit MAIL-1 in der Datenbank) ─────────────
    # Bis MAIL-1 standen die SMTP-Werte hier in der Umgebung (SMTP_*). Manuel
    # hat entschieden, dass das Postfach bei der Einrichtung in der Oberfläche
    # bestimmt wird — die Einstellungen liegen jetzt verschlüsselt in
    # `smtp_einstellungen` und `mailversand.py` liest NUR dort (S4). Es gibt
    # absichtlich keine ENV-Reste: kein zweiter halber Weg.

    # ── N-2: Aufbewahrungsfrist abgelehnter Anbieter-Zuordnungen ────────────
    # `auth_zuordnung_ablehnung` macht abgelehnte OIDC-Zuordnungen fuer die
    # Verwaltung sichtbar (R-N8). Die Zeilen sind kein Nachweis einer
    # Einwilligung, sondern nur ein Arbeitshinweis — sie brauchen eine Frist.
    # Default 90 Tage; ein taeglicher Job raeumt aeltere Zeilen ab.
    # `0` schaltet die Aufbewahrung ausdruecklich ab (unbegrenzt).
    auth_zuordnung_ablehnung_tage: int = Field(
        90,
        validation_alias=AliasChoices(
            "AUTH_ZUORDNUNG_ABLEHNUNG_TAGE", "auth_zuordnung_ablehnung_tage"
        ),
    )

    # ── SEC1: Anmeldung ueber Authentik ─────────────────────────────────────
    # Der vorgeschaltete Anmelde-Anbieter (OIDC) ist OPTIONAL und standardmaessig
    # AUS. Ohne `AUTH_OIDC_ENABLED=1` verhaelt sich der Stack exakt wie heute
    # (lokales Formular, keine Weiterleitung) — Bestandsschutz.
    #
    # Alle Werte kommen NUR aus .env/ENV; Secrets werden nie geloggt.
    # `validation_alias` ist aus demselben Grund wie oben Pflicht: ohne Alias
    # findet pydantic-settings eine ENV wie `AUTH_OIDC_ENABLED` nur zufaellig.
    auth_oidc_enabled: bool = Field(
        False,
        validation_alias=AliasChoices("AUTH_OIDC_ENABLED", "auth_oidc_enabled"),
    )
    # Issuer-URL des Anbieters, z. B.
    #   https://auth.example.org/application/o/diakronos/
    # Grundlage der Discovery (`.well-known/openid-configuration`).
    auth_oidc_issuer: str = Field(
        "",
        validation_alias=AliasChoices("AUTH_OIDC_ISSUER", "auth_oidc_issuer"),
    )
    auth_oidc_client_id: str = Field(
        "",
        validation_alias=AliasChoices("AUTH_OIDC_CLIENT_ID", "auth_oidc_client_id"),
    )
    # Client-Secret. Entweder direkt (AUTH_OIDC_CLIENT_SECRET) oder als Pfad auf
    # eine Docker-Secret-Datei (AUTH_OIDC_CLIENT_SECRET_FILE). Ist _FILE gesetzt,
    # hat es Vorrang und der Dateiinhalt wird beim Start gelesen.
    auth_oidc_client_secret: str = Field(
        "",
        validation_alias=AliasChoices("AUTH_OIDC_CLIENT_SECRET", "auth_oidc_client_secret"),
    )
    auth_oidc_client_secret_file: str = Field(
        "",
        validation_alias=AliasChoices(
            "AUTH_OIDC_CLIENT_SECRET_FILE", "auth_oidc_client_secret_file"
        ),
    )
    # Leerzeichengetrennte Scopes. `openid` ist Pflicht fuer OIDC.
    auth_oidc_scopes: str = Field(
        "openid email profile groups",
        validation_alias=AliasChoices("AUTH_OIDC_SCOPES", "auth_oidc_scopes"),
    )
    # Ruecksprung-Adresse. Leer -> aus der Basis-URL abgeleitet
    # (`<APP_BASE_URL>/auth/oidc/callback`).
    auth_oidc_redirect_url: str = Field(
        "",
        validation_alias=AliasChoices("AUTH_OIDC_REDIRECT_URL", "auth_oidc_redirect_url"),
    )
    # Basis-URL der Anwendung hinter dem Proxy, fuer die Ableitung der
    # Redirect-URL, z. B. https://dev.example.org
    app_base_url: str = Field(
        "",
        validation_alias=AliasChoices("APP_BASE_URL", "app_base_url"),
    )
    # RP-initiated Logout an den `end_session_endpoint` des Anbieters.
    auth_oidc_logout: bool = Field(
        True,
        validation_alias=AliasChoices("AUTH_OIDC_LOGOUT", "auth_oidc_logout"),
    )
    # Anzeigename des Anbieters (Login-Knopf/Weiterleitungshinweis).
    auth_oidc_anbietername: str = Field(
        "Authentik",
        validation_alias=AliasChoices("AUTH_OIDC_ANBIETERNAME", "auth_oidc_anbietername"),
    )
    # Discovery-/JWKS-Cache in Sekunden.
    auth_oidc_metadata_ttl: int = Field(
        3600,
        validation_alias=AliasChoices("AUTH_OIDC_METADATA_TTL", "auth_oidc_metadata_ttl"),
    )
    # Erlaubte Uhrenabweichung bei exp/iat/nonce in Sekunden (klein halten).
    auth_oidc_leeway: int = Field(
        30,
        validation_alias=AliasChoices("AUTH_OIDC_LEEWAY", "auth_oidc_leeway"),
    )
    # Lokaler Login trotz aktivem OIDC:
    #   "an"    -> Formular bleibt erreichbar (Anbieter-Knopf ist der Hauptweg)
    #   "aus"   -> kein Formular, nur OIDC
    #   "nur-admin" -> Formular nur als Notzugang fuer bestehende Administratoren
    #
    # LOGIN-2/S1: Die Einstellung wird seit LOGIN-2 SERVERSEITIG in
    # `api/auth.py::_lokaler_login_erlaubt` durchgesetzt — vorher galt sie nur
    # fuer die Anzeige der Anmeldeseite, und `/api/method/login` (JSON- wie
    # Formularweg) nahm jedes Konto an. "nur-admin" heisst: Rolle "System
    # Manager" ODER "Mitgliederadministrator" (dieselbe Definition wie
    # `frappe_compat/permissions.ADMIN_ROLES`). Ein abgewiesenes Konto bekommt
    # die Antwort des falschen Passworts; der Fehlversuch zaehlt in der
    # Brute-Force-Bremse.
    #
    # Die Schranke greift NUR bei aktivem Anbieter (AUTH_OIDC_ENABLED=1):
    # ohne OIDC ist der lokale Login der einzige Weg, und "aus" wuerde jede
    # Gemeinde aussperren.
    #
    # LOGIN-3/M-1: CalDAV ist von `AUTH_LOCAL_LOGIN` NICHT betroffen — aber
    # nicht, weil es eigene Kalender-Zugangsdaten gaebe (die gibt es NICHT).
    # `caldav/auth.py::_check_credentials` prueft `user.password_hash`, also
    # dasselbe KONTOPASSWORT wie die SPA. Folge: wer `AUTH_LOCAL_LOGIN=aus`
    # setzt, sperrt den Browser-Login — ein Kalender-Client mit gueltigem
    # Kontopasswort kommt weiterhin durch. Ob das so bleiben soll, ist eine
    # offene Fachentscheidung (nicht in LOGIN-3 geaendert).
    auth_local_login: str = Field(
        "nur-admin",
        validation_alias=AliasChoices("AUTH_LOCAL_LOGIN", "auth_local_login"),
    )

    # ── SEC1 TEIL B: Forward-Auth-Kopfzeilen (AUS per Default) ──────────────
    auth_proxy_header_enabled: bool = Field(
        False,
        validation_alias=AliasChoices(
            "AUTH_PROXY_HEADER_ENABLED", "auth_proxy_header_enabled"
        ),
    )
    # Kommaseparierte CIDR-Liste der vertrauenswuerdigen Proxy-Adressen.
    # PFLICHT, wenn Header aktiv: ohne sie werden die Header verworfen.
    auth_proxy_trusted_ips: str = Field(
        "",
        validation_alias=AliasChoices("AUTH_PROXY_TRUSTED_IPS", "auth_proxy_trusted_ips"),
    )
    # Gemeinsames Geheimnis, das der Proxy in einem Kopfzeilenfeld mitschickt.
    # PFLICHT, wenn Header aktiv; Vergleich in konstanter Zeit.
    auth_proxy_shared_secret: str = Field(
        "",
        validation_alias=AliasChoices(
            "AUTH_PROXY_SHARED_SECRET", "auth_proxy_shared_secret"
        ),
    )
    auth_proxy_shared_secret_file: str = Field(
        "",
        validation_alias=AliasChoices(
            "AUTH_PROXY_SHARED_SECRET_FILE", "auth_proxy_shared_secret_file"
        ),
    )
    # Kopfzeilennamen (Authentik-Vorgaben), konfigurierbar.
    auth_proxy_header_secret: str = Field(
        "X-Diakronos-Proxy-Secret",
        validation_alias=AliasChoices(
            "AUTH_PROXY_HEADER_SECRET", "auth_proxy_header_secret"
        ),
    )
    auth_proxy_header_username: str = Field(
        "X-authentik-username",
        validation_alias=AliasChoices(
            "AUTH_PROXY_HEADER_USERNAME", "auth_proxy_header_username"
        ),
    )
    auth_proxy_header_email: str = Field(
        "X-authentik-email",
        validation_alias=AliasChoices(
            "AUTH_PROXY_HEADER_EMAIL", "auth_proxy_header_email"
        ),
    )
    auth_proxy_header_uid: str = Field(
        "X-authentik-uid",
        validation_alias=AliasChoices(
            "AUTH_PROXY_HEADER_UID", "auth_proxy_header_uid"
        ),
    )
    auth_proxy_header_groups: str = Field(
        "X-authentik-groups",
        validation_alias=AliasChoices(
            "AUTH_PROXY_HEADER_GROUPS", "auth_proxy_header_groups"
        ),
    )

    @property
    def oidc_client_secret_effektiv(self) -> str:
        """Client-Secret: `_FILE` (Docker-Secret) hat Vorrang vor dem Klartext.

        Eine nicht lesbare Datei fuehrt NICHT zum stillen Fallback auf ein leeres
        Secret — das waere eine Anmeldung, die scheitert, ohne zu sagen warum.
        """
        return _secret_aus_datei(
            self.auth_oidc_client_secret_file, self.auth_oidc_client_secret
        )

    @property
    def proxy_shared_secret_effektiv(self) -> str:
        """Proxy-Geheimnis: `_FILE` (Docker-Secret) hat Vorrang."""
        return _secret_aus_datei(
            self.auth_proxy_shared_secret_file, self.auth_proxy_shared_secret
        )

    @field_validator("auth_local_login")
    @classmethod
    def valid_auth_local_login(cls, value: str) -> str:
        gueltig = {"an", "aus", "nur-admin"}
        wert = str(value or "").strip().lower()
        if wert not in gueltig:
            raise ValueError(
                "AUTH_LOCAL_LOGIN muss 'an', 'aus' oder 'nur-admin' sein"
            )
        return wert

    @property
    def oidc_scopes_liste(self) -> list[str]:
        """Scopes als Liste; `openid` ist immer dabei (OIDC-Zwang)."""
        teile = [s for s in str(self.auth_oidc_scopes or "").split() if s]
        if "openid" not in teile:
            teile.insert(0, "openid")
        return teile

    @property
    def oidc_redirect_ziel(self) -> str:
        """Effektive Ruecksprung-Adresse (explizit oder aus APP_BASE_URL)."""
        if self.auth_oidc_redirect_url.strip():
            return self.auth_oidc_redirect_url.strip()
        basis = self.app_base_url.strip().rstrip("/")
        if basis:
            return f"{basis}/auth/oidc/callback"
        return ""


def _secret_aus_datei(pfad: str, rueckfall: str) -> str:
    """Liest ein Secret aus einer Datei (Docker-Secret); sonst Rueckfallwert.

    Fehlt die Datei oder ist sie nicht lesbar, wird der Klartext-Rueckfall
    benutzt. Ein Fehler beim Lesen wird NICHT in den Rueckfall umgebogen, wenn
    ein Pfad gesetzt ist — der Aufrufer (Start-Pruefung) soll das melden.
    """
    datei = (pfad or "").strip()
    if not datei:
        return rueckfall or ""
    try:
        with open(datei, encoding="utf-8") as fh:  # noqa: PTH123
            return fh.read().strip()
    except OSError:
        return rueckfall or ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
