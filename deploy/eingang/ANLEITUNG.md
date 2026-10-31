# Gemeinde-Eingang — eine Domain für Website, App und Editor

Der Eingang ist ein schlanker nginx, der **eine** Gemeinde-Domain (z. B.
`dev.ecg-hn.de`) auf zwei Systeme verteilt: die **Website** (Primo) und die
**Gemeinde-App** (Diakronos). Davor steht der zentrale Reverse-Proxy (Nginx
Proxy Manager) mit TLS; dahinter die beiden Upstreams.

```
                    ┌──────────────────────────┐
Besucher ──TLS──▶   │ Nginx Proxy Manager      │
                    └───────────┬──────────────┘
                                │ http, Host bleibt
                    ┌───────────▼──────────────┐
                    │ Gemeinde-Eingang (nginx) │
                    └───┬──────────────────┬───┘
        /diakronos/…    │                  │   /api/ /admin/ /diakronos-sso.html
                        │                  │   alles andere inkl. /
              ┌─────────▼────────┐  ┌──────▼─────────────────┐
              │ Diakronos        │  │ Primo-Vorbau           │
              │ (App, Login,     │  │ (Website, Editor, API, │
              │  API, Dateien)   │  │  /_/ gesperrt)         │
              └──────────────────┘  └────────────────────────┘
```

## 1. Was hier liegt

| Datei | Zweck |
|---|---|
| `nginx.conf.template` | **Die** Routing-Vorlage (Platzhalter in `${…}`) |
| `15-vorlage.sh` | schreibt beim Containerstart die fertige Config (`envsubst` + `nginx -t`) |
| `compose.yml` | der Stack: nginx 1.27-alpine, gepinnt, nur ein veröffentlichter Port |
| `.env.example` | Upstreams, Bind-Adresse, Pfade — **keine Geheimnisse** |

Die echte `.env` gehört **nicht** ins Repository (steht in `.gitignore`).

## 2. Routing — was wohin gehört

| Anfrage | Geht an | Verhalten |
|---|---|---|
| `/diakronos`, `/diakronos/…` | Diakronos | Pfad **unverändert** durchgereicht |
| `/api/…`, `/admin/…`, `/diakronos-sso.html` | Primo | unverändert |
| `/primo`, `/primo/` | — | 302 → `/admin/` |
| `/login` | — | 302 → `/diakronos/login` |
| `/_/` (PocketBase-Superuser) | — | **404**, für Seitenaufrufe 302 → `/` (WEB-6; im LAN über den Primo-Port) |
| alles andere, inkl. `/` | Primo | Website per Host-Header |
| unbekannte Adresse (404) | — | 302 → `/`, wenn GET/HEAD mit `Accept: text/html` (§5a) |
| `/`, wenn der Host **keine** Site hat | — | 302 → `/diakronos/login` |

**Kein Präfix-Strippen:** Diakronos bekommt `/diakronos/…` so zu sehen, wie es
ankommt, und hört selbst unter diesem Präfix (`DIAKRONOS_BASE_PATH`, Karten
WEB-5a/5b). Der Eingang schneidet nichts ab — ein `proxy_pass` mit URI im
Präfix-Block wäre genau dieser Fehler und ist per Test verboten.

## 3. Starten

```bash
cd deploy/eingang
cp .env.example .env && chmod 600 .env
$EDITOR .env                  # Upstreams + Port eintragen
docker compose -p diakronos-eingang --env-file .env up -d
docker compose -p diakronos-eingang logs -f eingang
```

Der Container prüft die erzeugte Config selbst (`nginx -t`) und startet nicht,
wenn ein Platzhalter leer geblieben ist. Das ist Absicht: ein Eingang mit
`${EINGANG_PRIMO_UPSTREAM}` als Hostname wäre stumm kaputt.

Prüfen:

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' -H 'Host: dev.ecg-hn.de' http://127.0.0.1:8120/
# 302 http://dev.ecg-hn.de/diakronos/login     (noch keine Website für den Host)
```

## 4. Nginx Proxy Manager einrichten

1. **Proxy Host** für die Gemeinde-Domain anlegen.
2. **Forward Hostname / IP:** die Adresse, unter der der Eingang erreichbar ist
   (`127.0.0.1` bzw. die LAN-IP, wenn NPM auf einem anderen Host läuft).
3. **Forward Port:** `EINGANG_PORT` (Standard `8120`) — **nicht** den
   Primo-Port und **nicht** den Diakronos-Port.
4. **Scheme:** `http`. TLS macht ausschließlich NPM (Let's Encrypt).
5. **Websockets Support: AN.** Ohne das bricht `/diakronos/socket.io/…`
   (Echtzeit-Aktualisierung der App) und Primos `/api/realtime`.
6. **Block Common Exploits: AN** — Ergänzung zum Eingang, kein Ersatz.
7. **Advanced → `client_max_body_size 64m;`** — sonst scheitert der Bild-Upload
   im Editor an der 1-MB-Vorgabe von nginx.

Weitere Domains (`www.…`) zeigen auf **denselben** Eingang; Primo wählt die
Site am Host-Header.

## 5. Reservierte Pfade — so dürfen Website-Seiten NICHT heißen

Diese Pfade gehören dem Eingang, der App oder dem Editor. Eine Primo-Seite mit
diesem Namen wäre unerreichbar (der Eingang fängt die Anfrage vorher ab) oder
würde sogar eine Anmeldung vortäuschen:

```
diakronos            diakronos/…          (gesamter App-Bereich)
api/…                admin/…              diakronos-sso.html
primo                primo/               login
_/                   (PocketBase)         dav, .well-known/caldav
```

Konkret für die Redaktion: keine Seite „Login“, „Admin“, „API“, „Primo“.
Alles andere (`/impressum`, `/gemeinde/…`, `/kontakt`) ist frei und geht an
Primo, das es selbst ausliefert oder mit 404 beantwortet.

Zusätzlich gesperrt (404) auf der öffentlichen Domain: die PocketBase-Superuser-Schnittstellen `/api/collections/_superusers/…`, `/api/settings`, `/api/backups`, `/api/logs`, `/api/crons`. Diakronos nutzt Primo intern über den Vorbau (`:8095`) und braucht sie von außen nicht.

## 5a. Unbekannte Adressen — kein 404 für Besucher (WEB-6)

Ein **Seitenaufruf** auf eine Adresse, die es nicht gibt, landet auf der
Hauptseite statt auf einer Fehlerseite (Vorgabe Manuel 2026-10-30: „Alle nicht
registrierten Links sollen auf die Hauptseite führen und nicht 404 geben").

| Anfrage | Antwort |
|---|---|
| `GET /impressum-gibts-nicht`, Browser (`Accept: text/html`) | **302 → `/`** |
| `GET /diakronos/diakonos/gibtsnicht`, Browser | **302 → `/`** |
| `GET /admin/altes-lesezeichen`, Browser | **302 → `/`** |
| `GET /_/…` (Superuser-UI), Browser | **302 → `/`** (verrät nichts) |
| `GET …` mit `Accept: application/json` (fetch/XHR) | **404** wie bisher |
| `GET …` mit `Accept: image/*` (Bild, Datei) | **404** wie bisher |
| `POST/PUT/DELETE/PATCH` auf unbekannte Adresse | **404** wie bisher |
| `/api/…`, `/diakronos/api/…`, `/diakronos/files/…`, `/diakronos/socket.io/…` | **unverändert** (echter Fehler des Servers) |
| PocketBase-Sperren (`/api/settings`, `/api/backups`, …) | **404**, keine Umleitung |
| `/` selbst (kein Treffer, keine Site) | 302 → `/diakronos/login` (unverändert) |

**Warum die Trennung:** Ein umgeleiteter API-404 wäre eine Schein-Antwort —
jeder `fetch`-Aufrufer muss einen echten 404 auswerten können. Als
Seitenaufruf gilt deshalb nur `GET`/`HEAD` **und** ein `Accept`-Kopf mit
`text/html` (was Browser bei der Navigation schicken).

**Aufbau in `nginx.conf.template`:**

```
map $http_accept          $eingang_seitenaufruf     # enthält text/html? 1 : 0
map "$request_method:…"   $eingang_seitenabruf      # GET/HEAD?          1 : 0

location / {                       # Seiten-Location
    proxy_intercept_errors on;     # PFLICHT — sonst greift error_page nicht
    error_page 404 = @eingang_unbekannt;
}
location @eingang_unbekannt {
    if ($eingang_seitenabruf = 0) { rewrite ^ /_eingang_unbekannt last; }
    return 302 /;                  # relativ
}
location = /_eingang_unbekannt { internal; return 404; }
```

Zwei Eigenheiten von nginx, die den Umweg erklären:

* `error_page` greift bei Proxy-Antworten **nur** mit
  `proxy_intercept_errors on`. Ohne die Direktive läuft der 404 des Upstreams
  unverändert durch (live nachgemessen), und mit `on` **ohne** `error_page`
  setzt nginx seine eigene Fehlerseite ein — beides steht deshalb immer
  zusammen.
* An der Code-Stelle von `error_page` und in `return <code>` nimmt nginx nur
  eine **feste Zahl** (eine Variable ergibt `invalid value`). Die Fallunter-
  scheidung läuft deshalb über `if`/`rewrite` in einen internen Block.

Der Fehler**text** eines abgefangenen 404 stammt dann von nginx (der Rumpf des
Upstreams ist an dieser Stelle verworfen). Status und Kopfzeilen bleiben die
des Upstreams, der Wortlaut der Fehlermeldung nicht — wer den Originalrumpf
braucht, muss den Fehler selbst ausliefern; die Daten-Pfade unter
`/diakronos/api/…` fangen deshalb bewusst nichts ab.

## 6. Nachweise (wie geprüft wird)

**Config-Test im Wegwerf-Container:**

```bash
docker run --rm --network none \
  -v "$PWD/nginx.conf.template:/vorlage/nginx.conf.template:ro" \
  -v "$PWD/15-vorlage.sh:/docker-entrypoint.d/15-eingang-vorlage.sh:ro" \
  -e EINGANG_DIAKRONOS_UPSTREAM=127.0.0.1:8110 \
  -e EINGANG_PRIMO_UPSTREAM=127.0.0.1:8095 \
  nginx:1.27-alpine /bin/sh -c '/docker-entrypoint.d/15-eingang-vorlage.sh'
```

**Routing-Matrix** (58 Fälle gegen zwei Echo-Upstreams, inkl. WebSocket-Upgrade,
SSE und der Gegenprobe „/ mit Site bleibt die Website“):

```bash
python3 tools/web4_eingang_matrix.py --verbose
```

Der Test ersetzt den `listen`-Port und die Pfade selbst; er verändert die
Vorlage nicht. Er braucht `nginx` und `mime.types` — im Container lassen sich
beide per `EINGANG_NGINX` / `EINGANG_MIME_TYPES` setzen.

**Live-Abnahme** gegen die echten Upstreams (Browser, Playwright):

```bash
docker run --rm --network host -v "$PWD:/repo:ro" -w /repo \
  mcr.microsoft.com/playwright/python:v1.49.0-noble \
  python3 tools/web4_eingang_live.py --basis http://127.0.0.1:18120
```

**Struktur-Wächter** (läuft im Image, kein nginx nötig):

```bash
node --test frontend/tests/web4-eingang-routing.test.mjs
```

## 7. Stolperfallen

- **`/` fällt auf `/diakronos/login` nur bei fehlender Site.** Hat der Host eine
  veröffentlichte Website, liefert Primo sie aus und der Eingang lässt sie
  unberührt. Umgebogen wird ausschließlich Primos eigener Fallback-Redirect
  auf `/admin`.
- **Der `error_page`-Block gehört in den `location = /`-Block**, nicht auf die
  Server-Ebene. Auf Server-Ebene würde er auch die eigenen `return 302` von
  `/login` und `/primo` abfangen — beide antworteten dann mit leerem Ziel.
- **Keine Security-Header im Eingang.** Diakronos setzt HSTS/CSP selbst; zwei
  Werte auf einer Antwort sind ein Fehler. Primo-Antworten bleiben unverändert.
- **`/_/` sperren, aber den Primo-Port im LAN erreichbar lassen.** Die
  PocketBase-Verwaltung wird für Betrieb und Notfälle gebraucht — nur eben
  nicht über die öffentliche Domain.
- **Port ändern:** nur `EINGANG_PORT` in der `.env`; die NPM-Weiterleitung
  mitziehen.
