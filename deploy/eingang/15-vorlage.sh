#!/bin/sh
# WEB-4 — Vorlage -> nginx-Config.
#
# Laeuft im Container VOR dem nginx-Start (alle ausfuehrbaren *.sh unter
# /docker-entrypoint.d/ werden vom offiziellen nginx-Image der Reihe nach
# gestartet). Ergebnis: /etc/nginx/conf.d/default.conf.
#
# Warum envsubst mit ausdruecklicher Liste: ohne Liste ersetzt envsubst JEDE
# ${…}-Form — auch die nginx-eigenen Variablen ($http_host, $upstream_http_…).
# Mit Liste bleiben alle nginx-Variablen unangetastet, ersetzt werden nur die
# vier Konfigurationswerte. Ein leeres Environment ergibt damit KEINE kaputte,
# sondern eine unveraenderte Datei — das setzt die Fehlerpruefung unten durch.
set -eu

VORLAGE="${EINGANG_VORLAGE:-/vorlage/nginx.conf.template}"
ZIEL="${EINGANG_ZIEL:-/etc/nginx/conf.d/default.conf}"

for name in EINGANG_DIAKRONOS_UPSTREAM EINGANG_PRIMO_UPSTREAM \
            EINGANG_DIAKRONOS_PRAEFIX EINGANG_LOGIN_PFAD; do
    eval "wert=\${$name:-}"
    if [ -z "$wert" ]; then
        echo "FEHLER: $name ist leer — der Eingang hat ohne Upstream keine Aufgabe." >&2
        exit 1
    fi
done

# Praefix muss mit "/" beginnen und darf nicht auf "/" enden (er wird im
# Template als `${PRAEFIX}/` verwendet — ein Schraegstrich am Ende ergaebe
# `//`, und nginx vergleicht Pfade exakt).
case "$EINGANG_DIAKRONOS_PRAEFIX" in
    /?*) : ;;
    *) echo "FEHLER: EINGANG_DIAKRONOS_PRAEFIX muss mit / beginnen." >&2; exit 1 ;;
esac
case "$EINGANG_DIAKRONOS_PRAEFIX" in
    */) echo "FEHLER: EINGANG_DIAKRONOS_PRAEFIX darf nicht auf / enden." >&2; exit 1 ;;
esac

# EINGANG_ACCESS_LOG hat einen Default im Container (nginx schreibt dort, wo
# das Image es erwartet) und ist NICHT in der Pflichtliste oben — der Test
# ersetzt denselben Platzhalter mit seinem Arbeitsordner.
: "${EINGANG_ACCESS_LOG:=/var/log/nginx/access.log}"
export EINGANG_ACCESS_LOG

envsubst '${EINGANG_DIAKRONOS_UPSTREAM} ${EINGANG_PRIMO_UPSTREAM} ${EINGANG_DIAKRONOS_PRAEFIX} ${EINGANG_LOGIN_PFAD} ${EINGANG_ACCESS_LOG}' \
    < "$VORLAGE" > "$ZIEL"

# Restplatzhalter = Vorlage/Ersetzung passen nicht zusammen. Lieber laut
# abbrechen als mit einem "${EINGANG_…}" als Upstream-Host starten.
if grep -q '\${EINGANG_' "$ZIEL"; then
    echo "FEHLER: unersetzte Platzhalter in $ZIEL:" >&2
    grep -o '\${EINGANG_[A-Z_]*}' "$ZIEL" | sort -u >&2
    exit 1
fi

nginx -t
echo "Eingang: Konfiguration aus $VORLAGE geschrieben ($ZIEL)."
