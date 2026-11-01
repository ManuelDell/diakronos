# ── Stage 1: SPA bauen ────────────────────────────────────────────────────
# Die Vue-3-SPA wird nach /app/frontend/dist gebaut; genau dort sucht
# diakronos_app/spa.py im Container (siehe _CANDIDATES).
# Der Build-Kontext ist ./backend — auf den Projekt-Root erweitern, damit
# frontend/ erreichbar ist (docker-compose: context: .., dockerfile: backend/Dockerfile).
FROM node:22-alpine AS frontend
WORKDIR /build
# Nur Manifeste zuerst -> Docker-Cache fuer node_modules bleibt erhalten.
COPY frontend/package.json frontend/package-lock.json* ./
# Kein --legacy-peer-deps mehr (Review DEP-2, Punkt 4): die Ursache war
# frappe-ui mit vue-router ^4 (DEP-1 hat das Paket entfernt). Seit
# @vitejs/plugin-vue ^6 passt der Peer-Bereich zu vite 7, `npm ci` loest den
# Baum ohne den Schalter auf — geprueft ohne Flag.
RUN if [ -f package-lock.json ]; then \
        npm ci --no-audit --no-fund; \
    else \
        npm install --no-audit --no-fund; \
    fi
COPY frontend/ ./
# DM1: die Kochbuch-Instanzen des Plan-Rahmens werden zur Testzeit gelesen.
# P3-1b (K4): ebenso der erzeugte Feiertags-Katalog (Vergleich Oberfläche/Server).
COPY backend/src/diakronos_app/planrahmen/doku/kochbuch/ /backend/src/diakronos_app/planrahmen/doku/kochbuch/
# WEB-1/WEB-1b: die Vertragstests (tests/web1-*.test.mjs, tests/web1b-*.test.mjs)
# lesen Backend-Quelltext, um den Server-Vertrag der Primo-Anbindung
# festzuhalten. Vorher fehlte er im Build-Kontext dieses Stages und der
# Image-Build brach an „Datei fehlt" ab — nur die beiden Dateien, kein
# komplettes backend/src (der Stage bleibt ein Frontend-Build).
COPY backend/src/diakronos_app/api/website.py /backend/src/diakronos_app/api/website.py
COPY backend/src/diakronos_app/website/primo.py /backend/src/diakronos_app/website/primo.py
COPY backend/src/diakronos_app/settings.py /backend/src/diakronos_app/settings.py
COPY backend/src/diakronos_app/models/website.py /backend/src/diakronos_app/models/website.py
# ON-0a: der Frontend-Waechter (tests/on0a-*.test.mjs) haelt fest, dass das
# Backend Tokens + Grund-Stylesheet ueber GENAU diesen Helfer einbindet.
COPY backend/src/diakronos_app/anmeldung/seitenrahmen.py /backend/src/diakronos_app/anmeldung/seitenrahmen.py
COPY backend/src/diakronos_app/api/verantwortliche.py /backend/src/diakronos_app/api/verantwortliche.py
COPY backend/src/diakronos_app/frappe_compat/exceptions.py /backend/src/diakronos_app/frappe_compat/exceptions.py
COPY backend/src/diakronos_app/frappe_compat/router.py /backend/src/diakronos_app/frappe_compat/router.py
COPY backend/alembic/versions/web1b_primo_konto.py /backend/alembic/versions/web1b_primo_konto.py
# BS-1a: der Vertragstest (tests/bs1a-website-freigaben.test.mjs) liest die
# Freigabe-Regeln, das Postfach-Modell und die Migration. Wie oben nur die
# genannten Dateien, kein komplettes backend/src.
COPY backend/src/diakronos_app/website/freigaben.py /backend/src/diakronos_app/website/freigaben.py
COPY backend/src/diakronos_app/models/website_kontakt.py /backend/src/diakronos_app/models/website_kontakt.py
COPY backend/src/diakronos_app/models/kronos.py /backend/src/diakronos_app/models/kronos.py
COPY backend/src/diakronos_app/models/diakonos.py /backend/src/diakronos_app/models/diakonos.py
COPY backend/alembic/versions/bs1a_website_freigaben.py /backend/alembic/versions/bs1a_website_freigaben.py
# BS-1a2 (F1/F2/F3/F4/F5/F7): der Nachbesserungs-Vertragstest
# (tests/bs1a2-website-freigaben.test.mjs) liest ZUSAETZLICH das Frappe-Drift-
# Overlay (inventar/) und den Drift-Waechter (backend/tests/). Beides liegt
# ausserhalb von frontend/ und fehlte diesem Stage sonst — der Image-Build
# braeche an „Datei fehlt" ab (Vorfall SEC-10/WEB-2/WEB-4).
COPY inventar/schema_overlay.json /inventar/schema_overlay.json
COPY backend/tests/test_schema_drift.py /backend/tests/test_schema_drift.py
# SEC-10 / WEB-2 / WEB-4: Struktur-Waechter lesen Dev-Modus-Quellen und die
# Betriebsdateien unter deploy/ (Vorbau, Eingang). Nur diese, kein komplettes backend/src.
COPY backend/src/diakronos_app/devmodus/ /backend/src/diakronos_app/devmodus/
COPY deploy/ /deploy/
# (WEB-10 will hier `docs/BETRIEBSANLEITUNG.md` ins Bild legen — diese Datei
# steht aber in `.dockerignore` (`docs/`), also gibt es sie im
# Build-Kontext nicht. Der Test `test_web10_kontakt.py` laeuft deshalb wie
# bisher nur im Repo, nicht im Image. Ob die Anleitung ins Image soll, ist
# eine Betreiberentscheidung (Bildgroesse vs. Doku im Container) und nicht
# Teil dieser Karte.)
# SEC-11 (C3): der Waechter `tests/sec11-get-schreibend.test.mjs` liest die
# Liste der schreibenden Endpunkte aus dem Inventar (Regel 13: Dateien
# ausserhalb von frontend/ brauchen eine ausdrueckliche COPY-Zeile). `docs/`
# steht in .dockerignore, deshalb liegt das Inventar im Python-Paket.
COPY backend/src/diakronos_app/frappe_compat/inventar/ /backend/src/diakronos_app/frappe_compat/inventar/
# SEC-11b (F4): `tests/sec11b-inventar-rumpf.test.mjs` haelt die exakte
# C4-Ausnahmemenge der Herkunftsschranke am Quelltext fest — nur diese Datei.
COPY backend/src/diakronos_app/frappe_compat/auth_middleware.py /backend/src/diakronos_app/frappe_compat/auth_middleware.py
# WEB-5b (S4): die neuen Web5b-Tests stehen am ENDE der Liste (siehe unten).
# ON-0b: Rechner und Bestandsliste des Frontend-Waechters liegen IN frontend/
# (frontend/tools/) und kommen mit `COPY frontend/ ./` mit — keine zusaetzliche
# COPY-Zeile noetig (Regel 13 bleibt erfuellt: nichts ausserhalb von frontend/).
RUN node --test tests/web1-*.test.mjs tests/web1b-*.test.mjs src/diakonos/components/planrahmen/*.test.mjs src/diakonos/components/lieder/*.test.mjs src/diakonos/components/ui/*.test.mjs src/diakonos/components/devmodus/*.test.mjs src/diakonos/composables/*.test.mjs tests/planrahmen-*.test.mjs tests/devmodus-*.test.mjs tests/dm2-*.test.mjs tests/dm3-*.test.mjs tests/dm3b-*.test.mjs tests/p0-4*.test.mjs tests/waechter-tokens.test.mjs tests/dkbutton-icon.test.mjs tests/organigramm-xss-farbe.test.mjs tests/google-*.test.mjs tests/p1-9-*.test.mjs tests/p1-10-*.test.mjs tests/p1-11-*.test.mjs tests/p1-12-*.test.mjs tests/n0-*.test.mjs tests/n1-*.test.mjs tests/p1-1-*.test.mjs tests/p1-1b-*.test.mjs tests/n2-*.test.mjs tests/n3-*.test.mjs tests/p1-2-*.test.mjs tests/p1-3-*.test.mjs tests/p1-4-*.test.mjs tests/p1-4b-*.test.mjs tests/n4-*.test.mjs tests/p1-13-*.test.mjs tests/p1-5-*.test.mjs tests/p1-6-*.test.mjs tests/p1-5c-*.test.mjs tests/p2-2-*.test.mjs tests/p2-6-*.test.mjs tests/p2-4-*.test.mjs tests/p1-8-*.test.mjs tests/n5-*.test.mjs tests/n6-*.test.mjs tests/n7-*.test.mjs tests/n8-*.test.mjs tests/p21-*.test.mjs tests/n9-*.test.mjs tests/n9b-*.test.mjs tests/p2-3-*.test.mjs tests/p2-3b-*.test.mjs tests/n10-*.test.mjs tests/p2-5-*.test.mjs tests/p3-1-*.test.mjs tests/n11-*.test.mjs tests/p3-1b-*.test.mjs tests/p3-4-*.test.mjs tests/p3-4b-*.test.mjs tests/n12-*.test.mjs tests/p3-1c-*.test.mjs tests/p3-1d-*.test.mjs tests/p3-4c-*.test.mjs tests/rest1-*.test.mjs tests/des-rest-*.test.mjs tests/rest3-*.test.mjs tests/austritt-*.test.mjs tests/bk1-*.test.mjs tests/dsgvo2b-*.test.mjs tests/dsgvo2c-*.test.mjs tests/dsgvo2c2-*.test.mjs tests/dsgvo2d-*.test.mjs tests/ma1-*.test.mjs tests/ma1b-*.test.mjs tests/dev7-*.test.mjs tests/dev7b-*.test.mjs tests/dev1-*.test.mjs tests/dev3-*.test.mjs tests/dev5-*.test.mjs tests/dev6-*.test.mjs tests/dev8-*.test.mjs tests/dev4-*.test.mjs tests/dev4b-*.test.mjs tests/dep1-*.test.mjs tests/plan-w1-*.test.mjs tests/plan-m1-*.test.mjs tests/dep2-build-kette.test.mjs tests/dep2-review.test.mjs tests/dep2b-*.test.mjs tests/reg1a-*.test.mjs tests/uxa2a-*.test.mjs tests/uxa2a2-*.test.mjs tests/uxa2b-*.test.mjs tests/org-1-*.test.mjs tests/reg1b-*.test.mjs tests/reg1c-*.test.mjs tests/uxb2b-*.test.mjs tests/uxc3a-*.test.mjs tests/uxc3b-*.test.mjs tests/fix1-*.test.mjs tests/fix3-*.test.mjs tests/fix2-*.test.mjs tests/fix5-*.test.mjs tests/fix6-*.test.mjs tests/fix6b-*.test.mjs tests/fix4-*.test.mjs tests/fix6c-*.test.mjs tests/fix6d-*.test.mjs tests/sec3-*.test.mjs tests/sec7-*.test.mjs tests/sec8-*.test.mjs tests/sec9-*.test.mjs tests/web3-*.test.mjs tests/web4-*.test.mjs tests/web2-*.test.mjs tests/sec10-*.test.mjs tests/web5b-*.test.mjs tests/web7-*.test.mjs tests/web8b-*.test.mjs tests/web8c-*.test.mjs tests/web8d-*.test.mjs tests/sec11-*.test.mjs tests/bs1a-*.test.mjs tests/bs1a2-*.test.mjs tests/on0a-*.test.mjs tests/on0b-*.test.mjs tests/sec11b-*.test.mjs tests/web8e-*.test.mjs tests/web8f-*.test.mjs --test \
 && npm run build


# ── Stage 2: Anwendung ────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # BLD-R2: Zahl der Uvicorn-Arbeiten. 1 = wie bisher (ein Prozess).
    # Mehrere Arbeiten verhindern, dass EINE lange Anfrage alle anderen
    # Nutzer blockiert (in der Nachtpruefung blockierte ein einziger
    # haengender Request den gesamten Dienst). Default 2: auf einem
    # Gemeinde-Server unauffaellig, aber schon ein Puffer.
    WEB_CONCURRENCY=2

WORKDIR /app

# Systemabhaengigkeiten (psycopg[binary] bringt libpq mit, aber curl wird fuer
# den Compose-Healthcheck des app-Service gebraucht). redis-server ist wie
# die dev-Python-Gruppe fuer Tests im Container da; kein Dienst wird gestartet.
#
# BACKUP-1: `pg_dump` und `pg_restore` fuer die eigene Datensicherung
# (Sicherung/scheduler) und fuer die Wiederherstellung von der Kommandozeile.
# Die MAJOR-Version muss zum Betriebs-PostgreSQL passen (pg_dump kann nur
# Server <= seiner eigenen Version dumpen): im Betrieb laeuft
# `postgres:17-alpine` (`postgres --version` -> 17.11, gelesen am 2026-10-20 im
# DB-Container). Das Basis-Image `python:3.12-slim` ist Debian TRIXIE und
# liefert `postgresql-client-17` selbst (`apt-cache policy` -> 17.11-0+deb13u1)
# — das PGDG-Repository, sein Schlüssel per curl zur Build-Zeit und gnupg sind
# damit unnoetig (Lieferkette). Siehe BACKUP-1b (M3).
#
# Nur die beiden Programme werden ins Laufzeit-Image uebernommen, nicht das
# Paket: `postgresql-client-17` zoege perl samt `perl-modules` mit (+68 MB fuer
# zwei Kommandos). Der Perl-Wrapper `/usr/bin/pg_dump` entfaellt, deshalb
# ruft `sicherung/dump.py` die Programme unter `/usr/lib/postgresql/17/bin`
# zuerst; die Wiederherstellung in BETRIEBSANLEITUNG 14.4 nimmt ohnehin den
# `pg_restore` des db-Containers.
FROM python:3.12-slim AS pgwerkzeuge
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-17 \
 && rm -rf /var/lib/apt/lists/*

# Das Laufzeit-Image: der Kommentar oben gilt ab hier.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # BLD-R2: Zahl der Uvicorn-Arbeiten. 1 = wie bisher (ein Prozess).
    # Mehrere Arbeiten verhindern, dass EINE lange Anfrage alle anderen
    # Nutzer blockiert (in der Nachtpruefung blockierte ein einziger
    # haengender Request den gesamten Dienst). Default 2: auf einem
    # Gemeinde-Server unauffaellig, aber schon ein Puffer.
    WEB_CONCURRENCY=2

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl redis-server gosu ca-certificates libpq5 \
 && rm -rf /var/lib/apt/lists/*

# pg_dump/pg_restore aus der Werkzeug-Stage: nur die Programme, das Paket samt
# perl bleibt draussen. libpq5 (und die wenigen libs) liefert das Laufzeit-Repo.
COPY --from=pgwerkzeuge \
     /usr/lib/postgresql/17/bin/pg_dump \
     /usr/lib/postgresql/17/bin/pg_restore \
     /usr/lib/postgresql/17/bin/

# Non-root User
RUN groupadd --gid 1000 appuser \
 && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

# Code kopieren: Anwendung, Tests und Alembic-Umgebung.
# Kontext ist der Projekt-Root (siehe docker-compose.yml) -> Praefix backend/.
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/src /app/src
COPY backend/tests /app/tests
# P3-2: Importwerkzeuge werden ebenfalls im Image regressionstestet.
COPY tools/import_aus_frappe.py tools/import_pruefung.py /app/tools/
# SEC-11 (C2) / SEC-11b (F2,F3): die Inventarwerkzeuge selbst. Das Inventar
# wird von `tools/whitelist_inventar.py` aus dem Register erzeugt und die
# Rumpfpruefung (`tools/whitelist_lesen.py`) von ihm UND vom Waechter-Test
# `tests/test_sec11_methoden.py` benutzt — im Image liegen sie sonst nirgends.
COPY tools/whitelist_inventar.py tools/whitelist_lesen.py /app/tools/
# PUB-2: Die Demo-Daten (Seed-Skript + Beispieldaten) werden im Image
# getestet (`make test` laeuft IM Container; tests/test_demo_musterhausen.py
# importiert `musterhausen`). Sie werden NICHT vom Entrypoint ausgefuehrt.
COPY tools/demo /app/tools/demo
# tests/test_demo_musterhausen.py macht `tools/demo` importierbar. Je nach
# Lauf ist die pytest-Wurzel das Backend (Repo: `backend/conftest.py`) oder
# /app (Image) — deshalb hier dieselbe Zeile.
RUN printf '%s\n' \
      '"""Wurzel-Conftest des Image-Testlaufs (PUB-2).' \
      'Macht `tools/demo` fuer `tests/test_demo_musterhausen.py` importierbar."""' \
      'import sys' \
      'for _p in ("/app/tools/demo",):' \
      '    if _p not in sys.path:' \
      '        sys.path.insert(0, _p)' > /app/conftest.py
# Guarded disposable acceptance scripts (never run by the entrypoint).
COPY backend/scripts /app/scripts

# Editable install der Anwendung selbst. Die `dev`-Gruppe mitinstallieren:
# der Testlauf findet laut Makefile IM Container statt (`make test` ->
# `docker compose exec app python -m pytest`), also muessen die Test-Abhaengigkeiten
# (u.a. requests fuer den socketio-Client) im Image vorhanden sein.
RUN pip install --upgrade pip \
 && pip install -e ".[dev]" \
 && chown -R appuser:appuser /app

# SPA-Build aus Stage 1 — Pfad muss /app/frontend/dist sein (spa.py).
COPY --from=frontend --chown=appuser:appuser /build/dist /app/frontend/dist
# TS1: nur der Routen-Quellstand (router.js), nicht die ganze Frontend-Quelle.
# Der Testkatalog liest daraus Seiten und Routen; `dist` allein genügt nicht.
COPY --from=frontend --chown=appuser:appuser /build/src/diakonos/router.js /app/frontend/dist/router.js

# Entrypoint: migriert die DB (alembic upgrade head) und startet dann CMD.
# Notwendig, damit ein frischer `docker compose up` eine benutzbare DB hat.
COPY --chown=root:root backend/docker-entrypoint.sh /usr/local/bin/diakronos-entrypoint
RUN chmod 755 /usr/local/bin/diakronos-entrypoint

# Only the volume bootstrap runs as root; entrypoint drops to UID 1000 before
# migrations, bootstrap Python or the application command is executed.
USER root

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/diakronos-entrypoint"]
# Ein Worker-Prozess je WEB_CONCURRENCY (Default 2). Das CMD bleibt ohne
# --workers; der Entrypoint ergaenzt es fuer `uvicorn`-Kommandos, damit die
# Zahl ueber die Umgebung steuerbar ist (BLD-R2) und der Healthcheck des
# app-Service auf demselben Port antwortet.
CMD ["uvicorn", "diakronos_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
