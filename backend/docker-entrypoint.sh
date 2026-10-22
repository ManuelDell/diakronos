#!/bin/sh
# Entrypoint fuer app/worker/scheduler.
#
# Fuehrt VOR dem eigentlichen Kommando `alembic upgrade head` aus, damit ein
# frischer `docker compose up` eine benutzbare Installation ergibt: ohne
# Migrationen ist die Postgres-DB leer und jeder Daten-Endpunkt antwortet 500
# (die SPA laedt zwar, findet aber nichts).
#
# Das ist idempotent: auf einer bereits migrierten DB ist es ein No-op.
# Compose startet worker/scheduler erst nach einer gesunden App, damit nur
# die App eine leere DB migriert und den ersten Administrator anlegt.
# Alembic hat hier KEINEN advisory lock: nicht separat parallel migrieren.
#
# Umschalten per SKIP_MIGRATIONS=1 (z.B. wenn Migrationen separat laufen).
set -e

# Docker creates bind mounts and empty volumes as root. Prepare only the file
# store, then drop privileges before any Python/application code is run.
if [ "$(id -u)" = "0" ]; then
    files_dir="$(printf '%s' "${FILES_DIR:-/data/files}" | sed 's:/*$::')"
    case "$files_dir" in
        /|/app|/etc|/usr|/var|/root|.|'') echo "Unsafe FILES_DIR" >&2; exit 1 ;;
        /*) ;;
        *) echo "FILES_DIR must be absolute" >&2; exit 1 ;;
    esac
    # BACKUP-1: die Sicherungen liegen in einem EIGENEN Bind-Mount. Docker legt
    # ihn root:root an; der Dienst laeuft als appuser und koennte weder den
    # Dump schreiben noch alte Sicherungen loeschen ("nicht beschreibbar").
    # Deshalb dieselbe Vorbereitung wie oben — aber OHNE `chown -R`: der
    # Eigentuemer des Verzeichnisses genuegt, und ein rekursives chown ueber
    # viele Dumps waere bei jedem Start teuer. Rechte 0700: die Dumps enthalten
    # alle Personendaten (B4).
    backup_dir="$(printf '%s' "${BACKUP_DIR:-/data/sicherungen}" | sed 's:/*$::')"
    # `/data` als Sicherungsziel waere die halbe Datenbank samt Anhaengen —
    # und ein Ziel GLEICH der Dateiablage wuerde beim Aufraeumen die Anhaenge
    # treffen. Beides ist eine Fehlkonfiguration, kein Betriebsfall: Abbruch.
    case "$backup_dir" in
        /|/data|/app|/etc|/usr|/var|/root|.|'') echo "Unsafe BACKUP_DIR" >&2; exit 1 ;;
        /*) ;;
        *) echo "BACKUP_DIR must be absolute" >&2; exit 1 ;;
    esac
    # N8 (BACKUP-1c): auch VERSCHACHTELT ist beides falsch. Liegt die Ablage
    # unterhalb der Dateiablage, archiviert files.tar.gz die frueheren
    # Sicherungen mit (jede Sicherung enthaelt alle vorherigen); liegt die
    # Dateiablage unterhalb der Ablage, raeumt die Aufbewahrung im schlimmsten
    # Fall Anhaenge weg. Praefix-Vergleich mit Schraegstrich: `/data/files2`
    # ist NICHT unterhalb von `/data/files`.
    if [ -n "${BACKUP_DIR:-}" ] && [ "$backup_dir" = "$files_dir" ]; then
        echo "BACKUP_DIR must not be FILES_DIR" >&2
        exit 1
    fi
    case "$backup_dir/" in
        "$files_dir"/*) echo "BACKUP_DIR must not be inside FILES_DIR" >&2; exit 1 ;;
    esac
    case "$files_dir/" in
        "$backup_dir"/*) echo "FILES_DIR must not be inside BACKUP_DIR" >&2; exit 1 ;;
    esac
    mkdir -p "$files_dir"
    chown -R appuser:appuser "$files_dir"
    chmod 750 "$files_dir"
    mkdir -p "$backup_dir"
    chown appuser:appuser "$backup_dir"
    chmod 700 "$backup_dir"
    exec gosu appuser "$0" "$@"
fi
umask 027

# SEC1: Anmeldekonfiguration pruefen. Eine AKTIVIERTE, aber unvollstaendig
# konfigurierte Anmeldung (z.B. OIDC an ohne Issuer, Forward-Auth an ohne
# Trusted-IPs) ist gefaehrlicher als eine abgeschaltete — der Start wird
# deshalb VERWEIGERT (Exit 1), statt still falsch weiterzulaufen.
echo "[entrypoint] Anmeldekonfiguration pruefen ..."
python -m diakronos_app.anmeldung.startup

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
    echo "[entrypoint] alembic upgrade head ..."
    alembic -c /app/alembic.ini upgrade head
    echo "[entrypoint] Migrationen aktuell."
fi

# Erstinstallation (A1b3): legt bei LEERER user-Tabelle den Administrator aus
# ADMIN_EMAIL/ADMIN_PASSWORD an. Muss NACH den Migrationen laufen (die Tabelle
# entsteht dort). Idempotent und fehlertolerant: sind die Werte leer oder
# existieren schon Benutzer, passiert nichts; ein Fehler bricht den Start
# NICHT ab (Exitcode bleibt 0).
echo "[entrypoint] Erstinstallation pruefen ..."
python -m diakronos_app.erstinstallation || echo "[entrypoint] Erstinstallation uebersprungen."

# BLD-R2: mehrere Uvicorn-Arbeiten, damit EINE lange Anfrage nicht mehr alle
# Nutzer blockiert. Zahl ueber WEB_CONCURRENCY (Default 2, siehe Dockerfile).
# Nur fuer `uvicorn`-Kommandos und nur, wenn der Aufrufer nicht schon selbst
# --workers setzt; Worker/Scheduler sind davon nicht betroffen.
if [ "$1" = "uvicorn" ]; then
    workers="${WEB_CONCURRENCY:-2}"
    case "$workers" in
        ''|*[!0-9]*) workers=2 ;;
    esac
    if [ "$workers" -lt 1 ]; then workers=1; fi
    schon_gesetzt=0
    for arg in "$@"; do
        case "$arg" in
            --workers|--workers=*) schon_gesetzt=1 ;;
        esac
    done
    if [ "$schon_gesetzt" = "0" ]; then
        echo "[entrypoint] uvicorn mit --workers $workers"
        exec "$@" --workers "$workers"
    fi
fi

exec "$@"
