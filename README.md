<img width="1353" height="440" alt="Diakronos" src="https://github.com/user-attachments/assets/df0d3c84-bf23-4bfe-bf23-7014b2e6333b" />

# Diakronos (v2.0.0)

**Diakronos** ist eine kostenlose, selbst gehostete Software für Gemeinden: Mitglieder, Gruppen, Termine, Dienste, Lieder und Beiträge an einer Stelle. Die Daten bleiben auf dem eigenen Server. Keine monatlichen Kosten, keine Cloud, kein Datenschutz-Kompromiss.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/manueldell)

Gedacht für Freikirchen und kleinere Gemeinden, die eine überschaubare, nachvollziehbare Lösung suchen.

---

> ### Diese Version ist eine Neuentwicklung
>
> Diakronos v2 ist **eigenständig neu gebaut**: FastAPI + PostgreSQL + Vue-SPA, ausgeliefert als Docker-Compose-Stack, **ohne Frappe**. Die frühere Frappe-App wird nicht mehr weiterentwickelt, ihre Geschichte bleibt aber erhalten: alle ihre Branches tragen den Präfix `legacy/` (`legacy/frappe-main` = letzter Stand der Frappe-App, außerdem `legacy/frappe-develop`, `legacy/frappe-v16`), zusätzlich gibt es den Tag `v1-frappe-legacy`.

---

## Inhalt

1. [Was ist Diakronos](#was-ist-diakronos)
2. [Ein Blick hinein](#ein-blick-hinein)
3. [Schnellstart](#schnellstart)
4. [HTTPS und Reverse-Proxy](#https-und-reverse-proxy)
5. [Konfiguration](#konfiguration)
6. [Datensicherung und Wiederherstellung](#datensicherung-und-wiederherstellung)
7. [Update](#update)
8. [Architektur](#architektur)
9. [Entwicklung und Tests](#entwicklung-und-tests)
10. [Datenschutz-Hinweis](#datenschutz-hinweis)
11. [Mitwirkende](#mitwirkende)
12. [Haftungsausschluss](#haftungsausschluss)
13. [Lizenz](#lizenz)

---

## Was ist Diakronos

| Bereich | Was vorhanden ist |
|---|---|
| **Mitglieder** | Mitgliederliste mit Suche, Detailseite, Status (aktiv, Gast, ausgetreten), Konten, Rollen, Adressbuch mit einstellbarer Sichtbarkeit |
| **Familien und Gruppen** | Gruppen und Dienste mit Mitgliedschaften, Gruppenrechte, Organigramm als zweite Ansicht der Gruppenseite |
| **Kalender** | Monats-, Wochen- und Tagesansicht, mehrere Kalender mit Farben und Zugriffsrechten, wiederkehrende Termine, Raumbelegung, Moderations-Workflow für Terminvorschläge, Suche |
| **CalDAV** | Kalenderabruf für Apple Kalender, Thunderbird, DAVx⁵ und andere über `/dav/` (nur lesend) |
| **Kalender-Import** | iCal-Datei hochladen; Google Kalender anbinden und im Hintergrund importieren |
| **Ressourcen** | Räume und Ressourcen verwalten, Buchungen mit Doppelbuchungs-Prüfung |
| **Dienste und Dienstplan** | Dienstrollen, Dienstpläne je Zeitraum, „Meine Dienste“ für jedes Mitglied |
| **Plan-Rahmen** | Terminpläne (z. B. Gottesdienst-Ablauf, Chorplan) mit Feldern je Termin, Entwurf und Veröffentlichung, Vorlagen aus einem Kochbuch |
| **Lieder** | Lieder und Liedgruppen, Liedzuteilung in Plänen, Noten- und Audiodateien |
| **Registrierung und Anmeldung** | Selbstregistrierung mit Prüfweg, Registrierungslinks, Profilseite, optionale Anmeldung über einen externen OIDC-Anbieter |
| **Austritt** | Austritt/Deaktivieren durch einen Administrator, umkehrbar über „Reaktivieren“ |
| **Mailversand** | SMTP-Postfach wird vom System Manager in der Oberfläche eingerichtet (Passwort verschlüsselt gespeichert, Testmail); genutzt u. a. für die Löschung auf Antrag |
| **Datenschutz** | Einwilligungen, Auskunft als JSON-Ausfuhr, Löschung auf Antrag, Nachweis der Löschung |
| **Datensicherung** | Automatische tägliche Sicherung von Datenbank und Dateiablage, Aufbewahrungsfrist, Wiederherstellung über die Kommandozeile |

Jeder sieht nur, was für ihn freigegeben ist: Ansichten und Aktionen hängen an Rollen (System Manager, Mitgliederadministrator, Kalenderadministrator, Kalender-Moderator, Mitglied) und an der Sichtbarkeitseinstellung der Person.

## Ein Blick hinein

Alle Bilder zeigen die erfundene Demo-Gemeinde „Musterhausen“; es sind keine echten Personen, Adressen oder Zugangsdaten abgebildet. Die Aufnahmen entstehen aus `tools/demo/musterhausen.py` (siehe [Entwicklung und Tests](#entwicklung-und-tests)).

**Anmeldung:** Die Anmeldeseite liefert der Server selbst aus, sie funktioniert also auch dann, wenn das JavaScript der Oberfläche nicht lädt.

![Anmeldung](docs/bilder/v2/01-anmeldung.png)

**Übersicht:** Kacheln zu den nächsten Terminen, Diensten, Mitgliedern, Gruppen und Beiträgen.

![Übersicht](docs/bilder/v2/02-uebersicht.png)

**Kalender:** Monats- und Wochenansicht, mehrere Kalender nebeneinander, Farben je Kalender.

![Kalender, Monatsansicht](docs/bilder/v2/03-kalender-monat.png)

![Kalender, Wochenansicht](docs/bilder/v2/04-kalender-woche.png)

**Mitglieder:** Liste mit Suche, Detailseite mit Stammdaten, Kontakten, Gruppen und Diensten.

![Mitgliederliste](docs/bilder/v2/05-mitglieder-liste.png)

![Mitglied, Detailseite](docs/bilder/v2/06-mitglied-detail.png)

**Gruppen und Organigramm:**

![Gruppen](docs/bilder/v2/07-gruppen.png)

![Organigramm](docs/bilder/v2/08-organigramm.png)

**Dienstplan und „Meine Dienste“:**

![Dienstplan](docs/bilder/v2/09-dienstplan.png)

![Meine Dienste](docs/bilder/v2/09c-meine-dienste.png)

**Plan-Rahmen:** Übersicht der Pläne, ein ausgefüllter Gottesdienst-Ablaufplan und ein besetzter Chorplan.

![Plan-Rahmen, Übersicht](docs/bilder/v2/10-planrahmen-uebersicht.png)

![Gottesdienst-Ablaufplan](docs/bilder/v2/11-plan-gottesdienst-ablauf.png)

![Chorplan, besetzt](docs/bilder/v2/12-plan-chorplan-besetzt.png)

**Beiträge, Wiki, Lieder, Ressourcen:**

![Beiträge](docs/bilder/v2/13-beitraege.png)

![Wiki](docs/bilder/v2/14-wiki.png)

![Lieder](docs/bilder/v2/15-lieder.png)

![Ressourcen](docs/bilder/v2/16-ressourcen.png)

**Einstellungen und Profil:**

![Einstellungen, Datensicherung](docs/bilder/v2/17-einstellungen-datensicherung.png)

![Profil](docs/bilder/v2/18-profil.png)

**Auf dem Handy** (die Oberfläche ist für kleine Bildschirme gebaut):

![Übersicht auf dem Handy](docs/bilder/v2/mobil-02-uebersicht.png)

![Kalender auf dem Handy](docs/bilder/v2/mobil-03-kalender-monat.png)

![Dienstplan auf dem Handy](docs/bilder/v2/mobil-09-dienstplan.png)

Die übrigen Mobilaufnahmen liegen unter `docs/bilder/v2/mobil-*.png`.

---

## Schnellstart

### Voraussetzungen

- Docker Engine mit `docker compose` **ab 2.20** (die Compose-Dateien nutzen `include`), Linux-Server oder ein Rechner im eigenen Netz
- Git (oder ein ZIP des Repositories)
- rund 2 GB freier Plattenplatz für Images und Daten
- `make` ist optional, alle Schritte gehen auch mit `docker compose` direkt

### 1. Repository holen und `.env` anlegen

```bash
git clone <repo-url> diakronos
cd diakronos
cp .env.example .env
```

In der `.env` **zwei Werte zwingend setzen** — ohne sie startet der Stack nicht:

| Variable | Bedeutung |
|---|---|
| `POSTGRES_PASSWORD` | Passwort der Datenbank. Ein eigenes, starkes Passwort, z. B. `openssl rand -base64 24`. |
| `SECRET_KEY` | Schlüssel für die Signatur der Sitzungs-Cookies, z. B. `openssl rand -hex 32`. Später **nicht mehr ändern** (sonst sind alle Sitzungen ungültig) und zusammen mit der Sicherung aufbewahren. |

`DATABASE_URL` setzt Compose selbst aus `POSTGRES_PASSWORD` zusammen — nur anfassen, wenn eine **externe** Datenbank verwendet wird.

### 2. Ersten Administrator anlegen

Eine frische Installation hat keine Benutzer. Deshalb **einmalig** in der `.env`:

| Variable | Bedeutung |
|---|---|
| `ADMIN_EMAIL` | E-Mail des ersten Administrators, zugleich der Anmeldename |
| `ADMIN_PASSWORD` | Sein Passwort (wird als Argon2-Hash gespeichert, nie im Klartext) |

Angelegt wird der Benutzer nur, **solange die Benutzertabelle leer ist**; ein gesetztes `ADMIN_PASSWORD` kann eine bestehende Installation also nicht verändern. Ist nur einer der beiden Werte gesetzt, passiert nichts (Warnung im Log).

### 3. Bauen und starten

```bash
make build        # oder: docker compose build
make up           # oder: docker compose up -d
```

Der `app`-Dienst **migriert die Datenbank beim Start automatisch** (`alembic upgrade head` im Container-Entrypoint), legt danach bei Bedarf den ersten Administrator an und startet die Anwendung. Ein frisches `docker compose up -d` ergibt damit sofort eine benutzbare Installation.

### 4. Erreichbarkeit prüfen

Die mitgelieferte `.env.example` startet im HTTPS-Modus mit selbstsigniertem Zertifikat (Profil `https`, `TLS_MODE=selfsigned`):

```bash
curl -ksS https://localhost/healthz
# erwartet: {"status":"ok","db":true,"redis":true}

curl -ksS -o /dev/null -w '%{http_code}\n' https://localhost/diakonos
# erwartet: 200  (Anmeldeseite / SPA)
```

`-k` gilt nur für die Prüfung des selbstsignierten Zertifikats. Danach im Browser `https://localhost/` öffnen (die Warnung ist in diesem Modus normal) und mit den Zugangsdaten aus Schritt 2 anmelden.

Ohne HTTPS-Profil (HTTP-Betrieb im eigenen Netz) ist die App unter `http://<server>:8100/healthz` erreichbar; `APP_BIND_ADDR` (Vorgabe `127.0.0.1`) muss dafür auf eine erreichbare Adresse gesetzt werden.

---

## HTTPS und Reverse-Proxy

Für den Betrieb aus dem Internet gehört TLS davor. Drei Wege:

1. **Eingebauter nginx (Vorgabe in `.env.example`).** `COMPOSE_PROFILES=https` aktiviert einen nginx-Container, Port 80 leitet auf 443 um. `TLS_MODE=selfsigned` erzeugt ein persistentes Zertifikat (Browserwarnung ist normal), `TLS_MODE=letsencrypt` mit `ACME_EMAIL` holt ein echtes Zertifikat (öffentliche Ports 80/443 und eine DNS-Domain nötig), `TLS_MODE=custom` verwendet eigene Dateien aus `./certs`. Mit `DOMAIN=gemeinde.example.org` beantwortet der Server **nur** diesen Host, fremde Host-Kopfzeilen werden geschlossen; ohne `DOMAIN` sind IP und beliebige Hostnamen erlaubt.
2. **Eigener Reverse-Proxy davor (z. B. ein weiterer nginx).** Stack-nginx mit `COMPOSE_PROFILES=` abschalten, `BEHIND_PROXY=1` setzen und `APP_BIND_ADDR=127.0.0.1`, damit nur der Proxy die App erreicht.
3. **Direktes HTTP im eigenen Netz** ohne TLS — nur für ein abgeschlossenes Netz gedacht, nicht für das Internet.

Für einen vorgeschalteten Proxy gilt immer:

- **`Host` durchreichen** (`proxy_set_header Host $http_host`) — die Anwendung bildet ihre eigene Herkunft aus `Host` und `X-Forwarded-Proto` und weist Anfragen mit fremdem `Origin` ab.
- **`X-Forwarded-Proto: https` setzen**, damit das Anmelde-Cookie als `Secure` gesetzt wird und Weiterleitungen auf `https://` zeigen.
- **`X-Forwarded-For` überschreiben**, niemals anhängen; sonst lässt sich die Adresssperre der Anmeldung mit einem selbst gesetzten Kopfzeilenwert umgehen. Nur mit `BEHIND_PROXY=1` wird der Kopfzeilenwert überhaupt ausgewertet.
- **`Upgrade`/`Connection` durchreichen** für `/socket.io/` (Fortschrittsanzeige des Kalender-Imports); ohne Sticky Sessions verbindet sich der Fortschrittskanal ausschließlich per WebSocket.
- **`client_max_body_size`** im Proxy an `MAX_UPLOAD_BYTES` (Standard 10 MiB) bzw. `MAX_UPLOAD_BYTES_AUDIO` (Standard 50 MiB) anpassen, sonst bricht der Proxy Uploads mit 413 ab.

Einzelheiten, Umschaltprozedur und Fehlertabelle: [Betriebsanleitung, Abschnitt 10](docs/BETRIEBSANLEITUNG.md#10-https-und-domain-betrieb).

---

## Konfiguration

Alles wird über die `.env` gesteuert (Vorlage: `.env.example`, jede Variable dort kommentiert). Die wichtigsten:

| Variable | Bedeutung |
|---|---|
| `POSTGRES_PASSWORD` | Datenbank-Passwort (Pflicht) |
| `SECRET_KEY` | Signatur-Schlüssel der Sitzungen (Pflicht) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | erster Administrator, nur bei leerer Benutzertabelle |
| `COMPOSE_PROFILES` | `https` (eingebauter nginx) oder leer (HTTP direkt) |
| `DOMAIN`, `TLS_MODE`, `ACME_EMAIL`, `BIND_ADDR`, `HTTP_PORT`, `HTTPS_PORT` | HTTPS-Betrieb |
| `APP_BIND_ADDR`, `APP_PORT` | Adresse/Port im HTTP-Betrieb (Vorgabe `127.0.0.1:8100`) |
| `BEHIND_PROXY` | `1`, wenn ein eigener Reverse-Proxy die Herkunft bestimmt |
| `MAX_UPLOAD_BYTES`, `MAX_UPLOAD_BYTES_AUDIO` | Dateigrenzen für Uploads bzw. Audio-/Notenmaterial |
| `SESSION_TTL_SECONDS` | Lebensdauer einer Sitzung (Standard 24 h) |
| `LOGIN_MAX_VERSUCHE`, `LOGIN_MAX_VERSUCHE_IP`, `LOGIN_SPERRE_SEKUNDEN`, `LOGIN_SPERRE_MAX_FAKTOR` | Anmeldesperre je Konto und je Adresse |
| `WEB_CONCURRENCY` | Anzahl der Uvicorn-Arbeiten (Standard 2) |
| `BACKUP_AUTOMATISCH`, `BACKUP_UHRZEIT`, `BACKUP_AUFBEWAHRUNG_TAGE`, `BACKUP_DIR` | Datensicherung (Erstbelegung; danach gilt die Oberfläche) |
| `AUTH_OIDC_*`, `AUTH_PROXY_*` | Anmeldung über einen externen Anbieter (optional, aus per Vorgabe) |

Änderungen an der `.env` wirken nach `docker compose up -d` (Compose erkennt geänderte Variablen und erstellt die betroffenen Container neu).

Vollständig, mit Begründungen und Betriebsabläufen: [docs/BETRIEBSANLEITUNG.md](docs/BETRIEBSANLEITUNG.md). Einstieg in alle Dokumente: [docs/README.md](docs/README.md).

### Anmeldesperre

Die Anmeldung ist gegen Durchprobieren gesperrt: 5 Fehlversuche je Konto, 25 je Adresse, danach eine Sperre, die sich bei weiteren Versuchen verdoppelt. Eigene Adressen (Loopback, private Netze nach RFC 1918, link-local) werden nicht gezählt. Ein gesperrtes Konto gibt ein Administrator in der Oberfläche frei; wenn niemand mehr hineinkommt, geht es über die Konsole:

```bash
docker compose exec app python -m diakronos_app.loginversuche --entsperren name@example.org --status
docker compose exec app python -m diakronos_app.loginversuche --entsperren name@example.org
```

Der Befehl setzt **kein** Passwort, er hebt nur die Sperre auf, und er ist idempotent.

---

## Datensicherung und Wiederherstellung

Die Anwendung sichert sich **selbst**: täglich zu einer einstellbaren Uhrzeit (Standard 03:00) entsteht in `data/sicherungen/<JJJJ-MM-TT_HHMMSS>/` ein Datenbank-Dump (`db.dump`), ein Archiv der Dateiablage (`files.tar.gz`), Prüfsummen (`SHA256SUMS`) und eine Fertig-Markierung (`FERTIG`). Aufbewahrung, Uhrzeit und Ein/Aus stehen unter **Einstellungen → Datensicherung** (nur System Manager); die neueste erfolgreiche Sicherung bleibt immer erhalten. Ein Ordner ohne `FERTIG` ist unvollständig und wird als fehlgeschlagen geführt.

Die Sicherungen enthalten **alle Personendaten** — sie gehören behandelt wie die Mitgliederliste selbst: Ordner `0700`, Dateien `0600`, nicht auf einen geteilten Datenträger.

Wiederherstellen (ersetzt den aktuellen Inhalt, alles seit der Sicherung geht verloren):

```bash
# 1. Prüfsummen kontrollieren
cd data/sicherungen/<JJJJ-MM-TT_HHMMSS>
sha256sum -c SHA256SUMS

# 2. Dienste anhalten
docker compose stop app worker scheduler

# 3. Datenbank ersetzen
docker compose exec -T db psql -U diakronos -d postgres \
  -c "DROP DATABASE IF EXISTS diakronos WITH (FORCE)"
docker compose exec -T db psql -U diakronos -d postgres \
  -c "CREATE DATABASE diakronos OWNER diakronos"
docker compose exec -T db pg_restore -U diakronos -d diakronos \
  --no-owner --role=diakronos < data/sicherungen/<JJJJ-MM-TT_HHMMSS>/db.dump

# 4. Dateiablage zurückholen
tar -xzf data/sicherungen/<JJJJ-MM-TT_HHMMSS>/files.tar.gz -C data/files

# 5. Starten und prüfen
docker compose start app worker scheduler
curl -sk https://localhost/healthz
```

Im Standardbetrieb (HTTPS, `COMPOSE_PROFILES=https`) antwortet der eingebaute nginx auf Port 443; das `-k` trägt der Selbstsignierung des ersten Starts Rechnung. Nur im HTTP-Betrieb (ohne HTTPS-Profil) lautet die Prüfung `curl -s http://localhost:8100/healthz`.

Achtung: Eine Sicherung bringt auch Personen zurück, die nach ihr auf Antrag gelöscht wurden — die Löschungen sind danach erneut auszuführen. Dasselbe gilt für Austritte. Anleitung mit allen Randfällen: [Betriebsanleitung, Abschnitt 14](docs/BETRIEBSANLEITUNG.md#14-datensicherung-backup-1).

---

## Update

```bash
# vorher sichern (Oberfläche: "Jetzt sichern", oder Abschnitt oben)
git pull                      # neue Fassung holen
docker compose up -d --build  # Images neu bauen, Container ersetzen
```

Die Migrationen laufen beim Start des neuen `app`-Containers automatisch (`alembic upgrade head`). Vorher eine Sicherung anlegen; sie ist der Rückweg, wenn eine Migration nicht passen sollte. Datenbank und Dateiablage liegen in `data/` (Bind-Mount) und bleiben beim Neu-Bauen und beim Ersetzen der Container erhalten. `docker compose down -v` löscht Volumes — beim Update nicht verwenden.

---

## Architektur

| Dienst | Aufgabe |
|---|---|
| `app` | FastAPI-Backend und die ausgelieferte Vue-SPA unter `/diakonos` (`/healthz` prüft Datenbank und Redis wirklich) |
| `worker` | Hintergrundaufträge (RQ), z. B. Kalender-Import und Mailversand |
| `scheduler` | periodische Aufgaben (APScheduler), u. a. die tägliche Datensicherung |
| `db` | PostgreSQL |
| `redis` | Sitzungen, Anmelde-Sperren, Job-Queue und Realtime-Kanal |
| `nginx` / `certbot` | nur im Profil `https`: TLS-Terminierung, Umleitung, Zertifikate |

CalDAV ist **im Backend** umgesetzt (`/dav/`, `/.well-known/caldav`), es läuft kein zweiter Kalenderdienst — ein zweiter Terminspeicher wäre eine zweite Quelle der Wahrheit. Der Zugriff ist HTTP-Basic-geschützt und prüft gegen dieselbe Benutzertabelle wie die Oberfläche; über CalDAV ist der Kalender **nur lesbar**.

Ordnerstruktur:

```
backend/
  src/diakronos_app/    Anwendung: api/ (Endpunkte), models/, caldav/, planrahmen/, anmeldung/
    planrahmen/doku/    Handbuch des Plan-Rahmens (Leitfaden, Konzept, Kochbuch, Referenz)
  alembic/              Migrationen
  tests/                pytest-Suite (läuft im Image)
  Dockerfile            zweistufig: Node baut die SPA, Python liefert sie aus
frontend/               Vue-3-SPA (Vite, Tailwind) samt Node-Tests
compose/                Compose-Fragmente (stack.yml, http.yml, https.yml)
nginx/                  TLS-Terminierung, Zertifikats-Sync
tools/                  Import-, Generator- und Prüfwerkzeuge, Demo-Daten
docs/                   Betriebsanleitung, Fach- und Entwicklerdokumente, Bilder
```

---

## Entwicklung und Tests

Voraussetzungen: Docker (für die Backend-Suite), Node 22 (für die Frontend-Tests).

```bash
# Backend: die Suite läuft IM app-Container, weil /healthz echte Verbindungen prüft
make test                 # oder: docker compose exec app python -m pytest -q

# Frontend
cd frontend
npm ci --legacy-peer-deps --no-audit --no-fund
node --test src/diakonos/components/planrahmen/*.test.mjs tests/planrahmen-*.test.mjs
npm run build
```

Reine Unit-Tests ohne laufenden Stack:

```bash
docker run --rm --entrypoint bash <app-image> -c 'cd /app && python -m pytest -q -o timeout_method=signal'
```

**Demo-Daten.** `tools/demo/musterhausen.py` füllt eine **leere** Datenbank mit einer vollständig erfundenen Gemeinde „Musterhausen“: Mitglieder, Familien, Gruppen, Räume, Kalender mit Terminen, Lieder, Dienst- und Ablaufpläne, zwei Konten (Administrator und Mitglied). Das Skript arbeitet über die echten Modelle und Dienste der Anwendung und verweigert eine Datenbank, die bereits Mitglieder enthält — es kann also nicht versehentlich in einen Betriebsbestand schreiben.

```bash
docker compose exec app python tools/demo/musterhausen.py             # anlegen (idempotent)
docker compose exec app python tools/demo/musterhausen.py --pruefen   # prüfen
docker compose exec app python tools/demo/musterhausen.py --entfernen # entfernen
```

Die Bilder in dieser README entstehen aus genau diesem Bestand (`tools/demo/screenshots.py`).

**Migrationen** liegen in `backend/alembic`; manuell anwenden mit `make migrate` bzw. `docker compose exec app alembic -c /app/alembic.ini upgrade head`.

Aufbau, Code-Regeln und Arbeitsweise im Detail: [docs/ENTWICKLER-README.md](docs/ENTWICKLER-README.md).

---

## Datenschutz-Hinweis

Diakronos verarbeitet personenbezogene Daten von Gemeindemitgliedern und Angehörigen. **Verantwortlicher im Sinne der DSGVO ist die betreibende Gemeinde**, nicht der Entwickler. Wer die Software einsetzt, muss die Rechtsgrundlagen, Aufbewahrungsfristen und die Rechte der Betroffenen selbst sicherstellen.

Was die Software dabei unterstützt:

- **Sichtbarkeiten:** Adressbuch und Profilangaben sind je Person einstellbar; jede Ansicht prüft die Rolle.
- **Einwilligungen:** Erteilung und Widerruf sind dokumentiert, mit Zeitpunkt und Nachweis.
- **Auskunft:** eine JSON-Ausfuhr der zur Person gespeicherten Daten für Mitgliederadministratoren.
- **Löschung auf Antrag:** Die Person kann die Löschung im Profil beantragen; ein Administrator prüft und anonymisiert anschließend (zweistufige Bestätigung). Historie, technische Kennungen und Aufbewahrungspflichten bleiben dabei erhalten und sind vorher manuell zu prüfen.
- **Sicherungen:** Die tägliche Sicherung enthält weiterhin alles bis zum Ablauf der Aufbewahrungsfrist. Eine kürzere Frist verkürzt diese Zeitspanne.
- **Anmeldung:** Passwörter werden als Argon2-Hash gespeichert, Anmeldeversuche sind begrenzt, Sitzungs-Cookies sind `HttpOnly` und bei TLS `Secure`.

Fachliche Beschreibung: [N6-DATENSCHUTZ.md](docs/N6-DATENSCHUTZ.md) (Verwaltung) und [N7-DATENSCHUTZ.md](docs/N7-DATENSCHUTZ.md) (Profilsicht der Mitglieder). Was die Software bewusst **nicht** leistet, steht in der Betriebsanleitung, [Abschnitt 9](docs/BETRIEBSANLEITUNG.md#9-nicht-vorhanden--bewusst-offen).

---

## Mitwirkende

**Manuel Dell** — Idee und Herkunft des Projekts, Konzept, Planung, fachliche Entscheidungen, Testing (Live-Tests und Abnahme).

**Transparenz zur KI-Unterstützung:** Diese Version wurde mit Hilfe von KI-Modellen entwickelt.

- **Claude** — Orchestrierung der Entwicklung, Architektur- und Umsetzungsentscheidungen im Detail, Code-Reviews.
- **DeepSeek** — Implementierung (Programmier-Agenten) und unabhängige Prüfung.
- **GPT-6.1 Sol** — Implementierung (Programmier-Agent).

Jede Änderung wurde mit Tests und Reviews geprüft und von Manuel Dell live getestet; die Verantwortung für das Projekt liegt bei Manuel Dell.


Siehe [CONTRIBUTORS.md](CONTRIBUTORS.md).

---

## Haftungsausschluss

Diakronos ist ein Hilfswerkzeug, das Gemeinden bei der Organisation und Verwaltung unterstützen soll. Es ersetzt keine rechtliche, steuerliche oder datenschutzrechtliche Beratung.

**Die Verantwortung für die rechtskonforme Nutzung liegt ausschließlich bei der betreibenden Gemeinde**, insbesondere:

- **DSGVO:** Die Gemeinde ist Verantwortliche im Sinne der DSGVO und muss die rechtmäßige Verarbeitung personenbezogener Daten sicherstellen — einschließlich Aufbewahrungsfristen, Löschkonzept und der Sicherheit des Servers.
- **Betrieb:** Updates, Sicherungen und Zugriffsrechte auf den Server liegen bei der Gemeinde. Ein Sicherungsordner gehört nicht auf einen geteilten Datenträger.
- **Inhalte:** Für Texte, Lieder, Noten und Tondateien, die in Diakronos abgelegt werden, ist die Gemeinde für die nötigen Rechte verantwortlich (z. B. Urheber-, Verlags- und Aufführungsrechte). Die Software kann diese Prüfung nicht ersetzen: Sie führt je Lied einen Rechte-Status mit (Freitext, z. B. Kopie erlaubt, CCLI-Nummer, gesperrt) und eine Angabe, ob Streaming erlaubt ist — daraus sperrt sie Audio-Dateien für nicht berechtigte Nutzer. Diese Felder sind ein **Verwaltungshinweis, kein Nachweis**: was eingetragen wird und ob es zutrifft, prüft und verantwortet die Gemeinde.

Der Entwickler übernimmt keine Haftung für Schäden oder rechtliche Folgen aus der Nutzung dieser Software.

---

## Lizenz

MIT License — siehe [LICENSE](LICENSE).
