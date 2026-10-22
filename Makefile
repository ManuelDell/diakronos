.PHONY: up down logs test shell build restart ps migrate up-https up-http

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

build:
	docker compose build

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
