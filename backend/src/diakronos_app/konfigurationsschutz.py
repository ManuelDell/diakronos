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

Erlaubt bleiben die Platzhalter in `APP_ENV=development` und `APP_ENV=test`:
lokale Entwicklung und die Testsuite starten ohne `.env` und brauchen die
Werte. Alles andere (`prod`, `production`, `staging`, …) ist Betrieb und wird
hart abgewiesen.

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

# Umgebungen, in denen die unsicheren Defaults erlaubt bleiben.
ENTWICKLUNGS_UMGEBUNGEN = frozenset({"development", "test", "dev"})


def ist_entwicklung(app_env: str) -> bool:
    """True, wenn `APP_ENV` eine Entwicklungs-/Testumgebung bezeichnet."""
    return str(app_env or "").strip().lower() in ENTWICKLUNGS_UMGEBUNGEN


def secret_key_ist_unsicher(secret_key: str) -> bool:
    """True fuer den Platzhalter, leere Werte und alles kuerzer als 32 Zeichen."""
    wert = str(secret_key or "").strip()
    if wert == PLATZHALTER_SECRET_KEY:
        return True
    return len(wert) < MINDESTLAENGE_SECRET_KEY


def database_url_hat_default_passwort(database_url: str) -> bool:
    """True, wenn die Verbindung das bekannte Standard-Passwort benutzt.

    Geprueft wird die Passwort-Angabe der Verbindung (`…://benutzer:PASSWORT@…`).
    Es zaehlt das PASSWORT, nicht der Benutzer. URL-kodierte Varianten (`%6F`)
    werden dekodiert.

    Absichtlich OHNE `urlsplit`: (a) den Treiber-Zusatz
    `postgresql+psycopg://` kennt es nicht und liefert `netloc=""` — die
    Pruefung waere dann STILL wirkungslos, genau der Fehler, den sie
    verhindern soll; (b) die Zerlegung ist so kurz, dass sie hier offen im
    Code steht.
    """
    from urllib.parse import unquote

    roh = str(database_url or "").strip()
    if not roh or "://" not in roh:
        return False
    autoritaet = roh.split("://", 1)[1].split("/", 1)[0]
    # Benutzerinfo = alles vor dem LETZTEN `@` (ein Passwort darf `@` kodiert
    # enthalten; unkodiert waere die URL ohnehin ungueltig).
    if "@" not in autoritaet:
        return False
    benutzerinfo = autoritaet.rsplit("@", 1)[0]
    if ":" not in benutzerinfo:
        return False
    passwort = unquote(benutzerinfo.split(":", 1)[1])
    return passwort.strip() == DEFAULT_DB_PASSWORT


def unsichere_standardwerte(
    app_env: str, secret_key: str, database_url: str
) -> list[str]:
    """Liefert die Beanstandungen (leer = in Ordnung).

    In `development`/`test` wird NICHTS beanstandet — dort sind die Defaults
    gewollt.
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
