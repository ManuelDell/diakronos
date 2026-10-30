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
| `/_/` (PocketBase-Superuser) | — | **404** (nur im LAN über den Primo-Port) |
| alles andere, inkl. `/` | Primo | Website per Host-Header |
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

**Routing-Matrix** (31 Fälle gegen zwei Echo-Upstreams, inkl. WebSocket-Upgrade,
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
