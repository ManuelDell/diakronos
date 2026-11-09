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
cd frontend && npm ci && npm test
```

Welche Node-Tests laufen, steht in **`frontend/tests/testliste.txt`** (ein
Glob-Muster pro Zeile, `#` = Kommentar). Neue Testdatei = eine Zeile
anhängen; die `backend/Dockerfile` liest die Liste über
`ARG NODE_TESTLISTE=tests/testliste.txt` (Vorgabe) und führt
`node --test <Muster> --test && npm run build` aus. `.gitattributes` führt
die Datei mit `merge=union` zusammen — neue Zeilen kollidieren also nicht
mehr bei jedem Merge. Der Wächter `frontend/tests/fetest1-testliste.test.mjs`
meldet sowohl Testdateien ohne Muster als auch Muster ohne Datei.

Gezielt bauen (schneller Lauf, z. B. für eine Karte): eine eigene Datei
`frontend/tests/.auswahl.txt` (in `.gitignore`) mit wenigen Mustern anlegen
und `--build-arg NODE_TESTLISTE=tests/.auswahl.txt` übergeben. Eine leere
Auswahl bricht ab — `node --test` ohne Argumente würde sonst selbst alle
Tests suchen.

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

### Gestaltung: eine Quelle

Farben, Schriften, Radien, Abstände und Schatten stehen **ausschließlich** in
`frontend/src/diakonos/tokens.css` (CSS-Custom-Properties). Kein `.vue`, keine
serverseitig gerenderte Seite und kein gemeinsames Stylesheet trägt einen
eigenen Hex-/`rgb()`-Wert, eine feste Schriftfamilie oder eine feste
Radius-Zahl. Fehlt ein Wert, wird er **als Token ergänzt** — mit
Dunkel-Gegenstück unter `[data-theme="dark"]`, sofern der Wert
themenabhängig ist (Schriftfamilien sind es nicht).

**Die drei Ebenen**

| Ebene | Datei | Inhalt |
|---|---|---|
| Tokens | `frontend/src/diakonos/tokens.css` | Rohskala + semantische Tokens, hell und dunkel |
| Grund-Stylesheet für Server-Seiten | `frontend/src/ssot/seiten.css` | Karte, Felder, Knöpfe, Hinweis-/Fehlerboxen — nur `var(--…)` |
| SPA-Design-System | `frontend/src/diakonos/index.css` | Komponenten der Vue-Oberfläche |

**Wie Server-Seiten sie einbinden.** Der Frontend-Build schreibt beide Dateien
unter festen Namen ins Build-Verzeichnis:

```
frontend/src/diakonos/tokens.css  ->  dist/diakronos-tokens.css
frontend/src/ssot/seiten.css      ->  dist/diakronos-seiten.css
```

Die Adressen baut **eine** Stelle,
`backend/src/diakronos_app/anmeldung/seitenrahmen.py`:

```python
seitenrahmen.head_block()   # -> zwei <link rel="stylesheet">, präfixbewusst
seitenrahmen.tokens_url()   # -> {Präfix}/diakonos/assets/diakronos-tokens.css
seitenrahmen.seiten_url()   # -> {Präfix}/diakonos/assets/diakronos-seiten.css
seitenrahmen.schrift_url(n) # -> {Präfix}/diakonos/assets/schriften/<n>.woff2
seitenrahmen.versions_hash() # -> Inhalts-Hash für ?v=… (Cache-Busting)
```

Jede neue serverseitig gerenderte Seite schreibt `{seitenrahmen.head_block()}`
in den `<head>` — keine eigene `<style>`-Block, keine eigene Farbe. Die
Klassen des Grund-Stylesheets (`.dk-seite`, `.dk-karte`, `.dk-feld`,
`.dk-knopf`, `.dk-hinweis`, `.dk-meldung`, `.dk-formular`) sind der Vertrag.

**Schrift (ON-0b, F3).** `tokens.css` bindet „Inter“ über `@fontsource/inter`
ein (lokal, keine fremde Anfrage). Der Build setzt die `@import`-Zeilen
wörtlich ein UND schreibt jede `url()`-Angabe auf den festen Ordner
`schriften/` um — die Dateien werden unter dem **Namen aus der Quelle**
ausgegeben:

```
dist/diakronos-tokens.css       -> url(./schriften/inter-latin-400-normal.woff2)
dist/schriften/inter-latin-*.woff2|woff
```

`spa.py` liefert sie mit `font/woff2` bzw. `font/woff` und `no-cache`, **vor**
der Anmeldeschranke. Die Passwort-Seite trägt in ihrer CSP zusätzlich
`font-src 'self'` (ohne diese Quelle blockt `default-src 'none'` die Schrift).

**Cache.** Feste Dateinamen → `spa.py` liefert sie mit `Cache-Control:
no-cache` plus ETag (nicht `immutable` wie die hash-benannten SPA-Artefakte).
Zusätzlich hängen die `<link>`-Adressen einen Inhalts-Hash an
(`?v=<12 Zeichen>`, ON-0b F7). Der Hash deckt Tokens, Grundregeln und
Schriften ab: eine Änderung → neue Adresse, auch für Zwischenspeicher, die
`no-cache` nicht beantworten.

**Hash-Namen aus Unterordnern.** Vite legt gebündelte Dateien in `css/`,
`chunks/`, `assets/` ab und benennt sie nach Inhalt. `spa.py` liefert solche
Dateien nur unter ihrer Unterordner-Adresse aus (`/diakonos/assets/css/…`)
und leitet eine Anfrage ohne Unterordner dorthin um (307). Sonst lösten die
relativen `url()` im CSS (z. B. `./<font>-<hash>.woff2`) falsch auf.

**Kein Build.** Fehlt `dist/` (oder eines der beiden Stylesheets), warnen
beim Start BEIDE Stellen: `spa.mount_spa` (Warnung im Log) und der
Entrypoint über `python -m diakronos_app.frontend_build`
(„Frontend-Build fehlt — Server-Seiten ohne Gestaltung (npm run build in
frontend/ ausfuehren)“). Der Exitcode bleibt 0: eine ungestaltete Anmeldung
ist bedienbar, ein Startverbot wäre härter als der Befund.

**Der Wächter.** Vier Tests, alle laufen im Image:

- `backend/tests/test_on0a_css_ssot.py` — Fundstellen in den Python-HTML-Vorlagen
  unter `backend/src/` (jede Zeichenkette mit HTML-Merkmalen einschließlich
  `style=`, nicht nur ganze Seiten), plus die Auslieferung beider Dateien. Der
  Bestand steht in `tools/css-ssot-bestand.txt` und darf **nur schrumpfen**;
  wird eine Stelle behoben, muss die Zahl dort gesenkt werden, sonst wird der
  Test rot.
- `frontend/tests/on0b-css-ssot.test.mjs` (ON-0b, F1+F2) — gilt für ALLE
  `frontend/src/**` (außer `tokens.css`): keine Farben, keine
  `font-family`/`font:`-Kurzform mit Schriftnamen, auch nicht in Inline-Stilen.
  Der Bestand steht in `frontend/tools/css-ssot-bestand.txt` (Rechner:
  `frontend/tools/css-ssot-bestand.mjs`, `--schreiben`); Maßstab ist die im
  Test hinterlegte Obergrenze — höher oder neu = rot. Datendaten-Farben
  (Google-, Kalender-, Kachelfarben) sind dort als Ausnahmen dokumentiert.
- `frontend/tests/on0a-css-ssot.test.mjs` — `seiten.css` frei von Farben,
  Schriften und Radien; der Build erzeugt beide festen Namen; das Backend nutzt
  den Helfer.
- `backend/tests/test_on0b_schriften.py` — jede `url()` der ausgelieferten
  Server-Stylesheets liefert 200 mit `font/*` (mit und ohne Präfix), die
  SPA-Schriften lösen auf, die Passwort-CSP erlaubt `font-src`, ohne Build
  wird gewarnt, und die Schriftgrößen der Anmeldung (13/14/15/12 px) werden
  nicht kleiner.

Neue Ausnahmen sind **nicht** vorgesehen. Ein unvermeidbarer Sonderfall (etwa
ein eigenes Druckfenster-Dokument ohne Token-Geltungsbereich) wird im Test mit
Begründung eingetragen — nicht durch Abschalten der Regel.

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

Die Protokolle mit dauerhaftem Wert liegen gesammelt unter
[`docs/abnahmen/`](abnahmen/README.md) (und sind im Export ausgeschlossen);
Übergabe-Notizen (`*-UEBERGABE.md`) gehören gar nicht ins Repo — der Wächter
`backend/tests/test_aufr1_uebergabe_waechter.py` verbietet sie in der Wurzel.

## 6. Dokumentationsindex

Welche Dokumente es gibt, für wen sie gedacht sind und in welcher Reihenfolge
man sie liest, steht in [README.md](README.md). Die Plan-Rahmen-Dokumentation
liegt **im Python-Paket** (`backend/src/diakronos_app/planrahmen/doku/`), weil
`docs/` nicht im Docker-Image ist — siehe [planrahmen/README.md](planrahmen/README.md).
