# Entwickler-README — Diakronos

Diakronos ist eine eigenständige Neuentwicklung: FastAPI + PostgreSQL + Vue-SPA
als Docker-Compose-Stack, ohne Frappe. Dieses Dokument beschreibt Aufbau,
Arbeitsweise und die Regeln im Code.

**Schnellstart** (Einzelheiten in [BETRIEBSANLEITUNG.md](BETRIEBSANLEITUNG.md)):

```
cp .env.example .env          # POSTGRES_PASSWORD und SECRET_KEY setzen
docker compose up -d --build
curl -s http://127.0.0.1:8100/healthz
```

Drei Sätze, die du kennen musst, bevor du irgendetwas anfasst:

1. **Eine Änderung ist erst fertig, wenn sie am laufenden Stack geprüft ist —
   grüne Unit-Tests allein zählen nicht.** Ein Code und Test gemeinsamer
   Tippfehler im Modulpfad kann eine ganze Suite grün lassen, während alle
   Endpunkte 404 liefern. Gegenprobe am laufenden Container ist Pflicht.
2. **Jede Regel hat genau eine Stelle im Code.** Wer sie ändert, ändert sie
   dort — nicht an einer zweiten, kopierten Stelle.
3. **Lücken melden, nicht zudecken.** Eine gemeldete Lücke ist brauchbar, eine
   wegerklärte ist Schaden.

## 1. Aufbau

```
backend/            FastAPI-Anwendung
  src/diakronos_app/  Anwendung (api/, models/, frappe_compat/, caldav/, planrahmen/)
  alembic/            Migrationen
  tests/              pytest-Suite (läuft im Image)
  Dockerfile          zweistufig: Node baut die SPA, Python liefert sie aus
frontend/           Vue-3-SPA (Vite, Tailwind), Sprachverträge in *.md
compose/            Compose-Fragmente (stack.yml, http.yml, https.yml)
nginx/              TLS-Terminierung, Zertifikats-Sync
tools/              Import-, Generator- und Prüfwerkzeuge
docs/               Betriebs- und Fachentwurfsdokumente
```

Fünf Services im Compose-Projekt: `app` (FastAPI, liefert die SPA unter
`/diakonos`), `db` (PostgreSQL 17), `redis` (Job-Queue, Realtime, Sitzungen,
Anmeldesperre), `worker` (RQ) und `scheduler` (APScheduler). `app`, `worker`
und `scheduler` teilen sich **ein** Image und den Umgebungsblock `x-app-env`.
Der Entrypoint migriert beim Start (`alembic upgrade head`) und prüft danach
die Erstinstallation.

Ports sind in `.env` einstellbar (`APP_PORT`, `DB_PORT`, `REDIS_PORT`); die
Vorgaben binden nur an Loopback bzw. an die konfigurierte Adresse.

## 2. Arbeiten

**Inkrementell committen**, nach jedem Teilschritt. Ein Commit pro
zusammenhängendem Punkt, mit einer Zeile Begründung im Text.

**Tests laufen im Container**, ohne `--ignore`:

```
docker compose exec app python -m pytest -v
```

Zwei Gründe: `/healthz` prüft echte Verbindungen, und der Host braucht weder
`fastapi` noch `sqlalchemy`. Zitierst du eine Abnahmezahl, dann die aus dem
Container ohne Zusatzargument. Bei grossen Suiten hilft
`-o timeout_method=signal`, damit ein hängender Unterprozess den Lauf nicht
mitreisst.

**Frontend-Tests ohne Build** (Node ≥ 20):

```
cd frontend && npm ci --legacy-peer-deps && npm test
```

**Migrationen** werden immer gegen eine frische Datenbank **und** gegen eine
Kopie eines Betriebsdumps geprüft (`upgrade`, `downgrade`, `alembic check`).
Leere Testdatenbanken verdecken Fehler, die erst an echten Zeilen auftreten.

**Konfiguration** ausschliesslich über Umgebungsvariablen (`settings.py` mit
sicheren Vorgaben), dokumentiert in `.env.example` und BETRIEBSANLEITUNG.

## 3. Code-Regeln

- **Keine Schreibzugriffe ins Image-Dateisystem.** Alles Schreibbare liegt
  unter den eingebundenen Verzeichnissen (`FILES_DIR`, Sicherungen).
- **Alle Ressourcenpfade** (Schema, Doku, Kochbuch) werden über
  `importlib.resources` aus dem Python-Paket gelesen, nie über Repo-Pfade.
- **Eine Aussage, eine Quelle.** Verhalten wird im Code festgelegt,
  dokumentiert wird, was der Code tut — nicht, was man sich wünscht.
- **Fehlermeldungen nennen Pfad, Grund und Beispiel**, damit ein Agent oder
  Mensch sich im nächsten Versuch korrigieren kann.
- **Sicherheit fällt geschlossen aus.** Fehlt eine Angabe, gilt die
  vorsichtige Annahme (z. B. `BEHIND_PROXY=0` ignoriert `X-Forwarded-For`).
- **CSRF**: ein Synchronizer-Token aus der Redis-Sitzung wird für schreibende
  Anfragen geprüft (`HMAC`, `compare_digest`), Antwort bei Abweichung 417.
  Die Prüfung greift nur, wenn eine Sitzung existiert; Anfragen ohne Sitzung
  sind `Guest` und scheitern an `allow_guest`.
- **Anmeldesperre**: getrennte Schwellen am Konto und an der Adresse, eigene
  und private Adressen werden nicht gezählt. Der Notweg zum Entsperren ist das
  CLI-Werkzeug (`python -m diakronos_app.cli_entsperren`).

## 4. Offene Punkte

Diese Liste ist ehrlich gemeint und gehört gepflegt:

- **Google-Import**: iCal-Import und der Google-Ablauf gegen ein nachgebautes
  Google sind belegt; ein Durchlauf mit echten Google-Zugangsdaten ist offen.
- **CalDAV** prüft das Kontopasswort (keine App-Passwörter). Wer den lokalen
  Login abschaltet, sperrt CalDAV damit **nicht**.
- **HTTPS** ist optional (`COMPOSE_PROFILES=https`); die Terminierung kann
  auch ein vorgelagerter Proxy übernehmen (`BEHIND_PROXY=1`).

## 5. Veröffentlichen

Der Export für ein öffentliches Repo wird intern aus dem Git-Stand (`HEAD`)
erzeugt: Arbeitsstände wie die Übersetzungsvorlage (`referenz/`), das
Arbeitsinventar (`inventar/`) und die Übergabe-/Abnahmeprotokolle bleiben
dabei zurück, und der Rest wird vor der Weitergabe auf Geheimnisse, interne
Infrastruktur und Personendaten geprüft. Ein Treffer bricht ab; behoben wird
der Fund, nicht der Ausschluss.

## 6. Dokumentationsindex

Welche Dokumente es gibt, für wen sie gedacht sind und in welcher Reihenfolge
man sie liest, steht in [README.md](README.md). Die Plan-Rahmen-Dokumentation
liegt **im Python-Paket** (`backend/src/diakronos_app/planrahmen/doku/`), weil
`docs/` nicht im Docker-Image ist — siehe [planrahmen/README.md](planrahmen/README.md).
