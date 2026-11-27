.PHONY: up down logs test shell build restart ps migrate up-https up-http update rollback betrieb-vorschau betrieb-test

# ABN-3: Update und Rueckweg — EIN Befehl je Richtung.
#
# Projektname und Umgebungsdatei kommen aus der Umgebung, damit dieselben
# Befehle auf jeder Installation und in einer Wegwerf-Instanz laufen:
#
#   make update                                   # Projekt 'diakronos', .env im Repo
#   DIAKRONOS_PROJEKT=abn3 DIAKRONOS_UMGEBUNGSDATEI=/tmp/abn3.env make update
#
# Die Betriebs-Stacks (diakronos-standalone, diakronos-devecg) sind im Skript
# GESPERRT: wer sie wirklich aktualisieren will, setzt
# DIAKRONOS_ICH_WEISS_WAS_ICH_TUE=1 (siehe tools/betrieb/betrieb.sh).
# Ohne Wirkung vorher ansehen: DIAKRONOS_VORSCHAU=1 make update.
DIAKRONOS_REPO ?= $(CURDIR)

update:
	@DIAKRONOS_REPO="$(DIAKRONOS_REPO)" sh tools/betrieb/update.sh

rollback:
	@DIAKRONOS_REPO="$(DIAKRONOS_REPO)" sh tools/betrieb/rollback.sh

# Beleg ohne Wirkung: zeigt, was `make update` taete (kein Bau, kein Tausch).
betrieb-vorschau:
	@DIAKRONOS_REPO="$(DIAKRONOS_REPO)" DIAKRONOS_VORSCHAU=1 sh tools/betrieb/update.sh


# Moduswechsel stoppen das Projekt zuerst (kurze Unterbrechung).
# Dauerhaft den gleichen Wert in .env setzen; normale Ziele lesen diese Datei.
up-https:
	docker compose down --remove-orphans
	COMPOSE_PROFILES=https docker compose up -d --build

up-http:
	docker compose down --remove-orphans
	COMPOSE_PROFILES= docker compose up -d

# Startet den kompletten Stack im Hintergrund.
# Migrationen laufen automatisch im Container-Entrypoint (alembic upgrade head).
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

# ABN-3b/M8: auch der normale Build traegt die Build-Kennung (Kurz-Hash des
# Quellstands). Sie geht als Umgebungsvariable (compose: build.args GIT_COMMIT)
# ins Image und steht danach in „Einstellungen -> Ueber Diakronos". Der Wert
# darf leer sein — der Build bricht NICHT (ARG-Vorgabe "").
#
# Das Stand-Label org.diakronos.alembic_revisionen (Vergleich Sicherung/Image
# fuer den Rueckweg) setzt NUR `make update`: ein Label laesst sich nach dem
# Build nicht anhaengen, nur beim `docker build` mitgeben.
GIT_COMMIT ?= $(shell git rev-parse HEAD 2>/dev/null)

build:
	GIT_COMMIT="$(GIT_COMMIT)" docker compose build

# ABN-3b: die Logik von update/rollback ohne Docker und ohne Datenbank
# (Zettel, Abbruch bei unpassender Sicherung, SKIP_MIGRATIONS). Sekunden.
betrieb-test:
	sh tools/betrieb/test_abn3b_rueckweg.sh

restart:
	docker compose restart

ps:
	docker compose ps

# Migrationen manuell anwenden (im App-Container).
migrate:
	docker compose exec app alembic -c /app/alembic.ini upgrade head

# Tests laufen IM app-Container, weil /healthz echte Verbindungen prueft.
test:
	docker compose exec app python -m pytest -v

shell:
	docker compose exec app bash
