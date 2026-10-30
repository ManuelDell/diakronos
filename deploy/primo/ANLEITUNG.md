# Primo an Diakronos anschließen

Kurzanleitung für den Betrieb. Sie richtet den Primo-Stack aus diesem
Verzeichnis ein, legt das Integrationskonto an und beschreibt, welche Werte
Diakronos braucht.

Diakronos und Primo bleiben **zwei getrennte Systeme**. Primo ist der
Redaktions- und Baukasten für die statischen Gemeinde-Seiten; Diakronos ist die
Verwaltung, die Primo ansteuert und Redakteure dorthin weiterleitet.

---

## 1. Was hier liegt

| Datei | Zweck |
|---|---|
| `compose.yml` | Primo (gepinnt per Digest) + nginx-Vorbau, Volume `primo_pb_data` |
| `nginx.conf` | liefert `/diakronos-sso.html` aus, reicht alles andere an Primo durch |
| `diakronos-sso.html` | Übergabeseite für die Anmeldung (gleicher Origin wie `/admin/`) |
| `.env.example` | Beispielwerte; **ohne echte Kennwörter** |

Alles davon gehört ins Repository. Die echte `.env` **nicht** — sie ist über
`.gitignore` ausgeschlossen.

---

## 2. Stack starten

```bash
cd deploy/primo
cp .env.example .env
chmod 600 .env
$EDITOR .env                 # vier Kennwörter + ggf. Port eintragen
docker compose -p diakronos-primo --env-file .env up -d
```

Prüfen:

```bash
curl -s http://127.0.0.1:8095/api/primo/info
# {"id":"…","version":"v3.3.1","telemetry_enabled":false,…}
```

`telemetry_enabled` muss `false` sein (steht in `compose.yml` fest). Der Port
kommt aus `PRIMO_HTTP_PORT`; veröffentlicht wird er **nur auf 127.0.0.1**.
Von außen kommt man ausschließlich über den zentralen Reverse-Proxy (NPM) heran
— dort TLS einrichten und auf `127.0.0.1:<PRIMO_HTTP_PORT>` zeigen lassen.

> **Erststart:** `PRIMO_SUPERUSER_*` und `PRIMO_USER_*` wirken **nur beim ersten
> Start mit leerem `pb_data`**. Ändert man sie später, passiert nichts mehr.

---

## 3. Superuser anlegen

Im Browser `http://<host>:<port>/_/` öffnen (PocketBase-Backend). Ist noch kein
Superuser vorhanden, erscheint dort die Anlage-Maske; sonst hilft
`/admin/setup` weiter. Die Zugangsdaten stammen aus `PRIMO_SUPERUSER_EMAIL` /
`PRIMO_SUPERUSER_PASSWORD` der `.env`.

Der Superuser ist **nur für Verwaltung und Notfälle** gedacht. Das
Tagesgeschäft läuft über das Integrationskonto (nächster Schritt).

---

## 4. Integrationskonto für Diakronos

Diakronos legt Primo-Nutzer und Site-Zuordnungen per PocketBase-REST an. Das
darf in Primo **nur** ein Konto mit der Server-Rolle `developer` — die Regeln
der Collections `users` und `sites` verlangen `serverRole != ""`.

1. Im Admin (`/<admin>/`) bzw. im PocketBase-Backend unter `users` den Benutzer
   aus `PRIMO_USER_EMAIL` prüfen oder anlegen.
2. Diesem Benutzer die Server-Rolle **`developer`** geben (Feld `serverRole`).
3. Anmelden und den Auth-Token abholen:

```bash
curl -s http://127.0.0.1:8095/api/collections/users/auth-with-password \
  -H 'Content-Type: application/json' \
  -d '{"identity":"<PRIMO_USER_EMAIL>","password":"<PRIMO_USER_PASSWORD>"}'
# {"token":"eyJ…","record":{…}}
```

Der `token` ist das, was Diakronos als Zugang zu Primo braucht.

**Warum kein eigenes Primo-Kennwort je Redakteur:** Diakronos provisioniert die
Konten und verlinkt in den Editor. Die Anmeldung selbst übernimmt die
Übergabeseite (Abschnitt 6). Wer den Editor direkt aufruft, landet auf der
Primo-Anmeldemaske — dafür braucht jedes Konto ein eigenes Kennwort.

---

## 5. Werte in Diakronos eintragen

| Wert in Diakronos | Inhalt | Beispiel |
|---|---|---|
| `PRIMO_URL` | interne Adresse, wie Diakronos Primo erreicht | `http://127.0.0.1:8095` |
| `PRIMO_PUBLIC_URL` | Adresse, die der **Browser** des Redakteurs nutzt | `https://website.example.org` |
| Token des Integrationskontos | `token` aus Abschnitt 4 | `eyJ…` |

`PRIMO_URL` und `PRIMO_PUBLIC_URL` dürfen auseinanderfallen (internes Netz vs.
öffentlicher Name) — sie müssen es oft sogar. Beide zeigen auf **denselben**
Vorbau; `PRIMO_PUBLIC_URL` entscheidet, unter welchem Origin der Browser den
Login ablegt.

---

## 6. Verbindung prüfen und Anmeldung testen

**Verbindung:** Diakronos fragt `GET /api/primo/info` ab. Antwortet Primo mit
`version` und `id`, ist die Verbindung in Ordnung. `site_count` sagt, wie viele
Seiten angelegt sind (`0` bei frischer Installation).

**Anmeldung:** Diakronos schickt den Redakteur auf

```
{PRIMO_PUBLIC_URL}/diakronos-sso.html#token=<pocketbase-token>&record=<base64url(json)>
```

Die Seite

1. entfernt den Parameter **sofort** aus der Adresszeile,
2. prüft Token (JWT-Form, `type: "auth"`, nicht abgelaufen) und Kontodaten
   (`id`, `email`),
3. schreibt die Anmeldung als `localStorage["pocketbase_auth"]` im Format
   `{"token": …, "record": {…}}` — genau so liest Primo v3.3.1 sie,
4. leitet nach `/admin/` weiter.

Schlägt einer der Schritte fehl, erscheint eine Meldung mit Link zur
Primo-Anmeldung; der Token wird nie angezeigt oder protokolliert.

**Wichtig:** Die Seite muss unter **demselben Origin** laufen wie `/admin/`.
Der Vorbau in `compose.yml` sorgt dafür. Liegt dazwischen ein Umleitungsschritt
auf einen anderen Host (z. B. `www.` → `example.org`), verliert der Browser das
Fragment; dann in Diakronos `PRIMO_PUBLIC_URL` auf den Host setzen, unter dem
auch `/admin/` liegt.

---

## 7. Sicherung

`pb_data` enthält die SQLite-Datenbank **und** die veröffentlichten Builds.
Primo sichert selbst täglich (`PRIMO_BACKUP_CRON`, Standard `0 3 * * *`,
Ortszeit `TZ`). Zusätzlich das Volume `diakronos-primo_primo_pb_data` in die
allgemeine Sicherung aufnehmen — eine Sicherung, die nur im selben Container
liegt, hilft beim Verlust des Volumes nicht.

---

## 8. Primo aktualisieren

Das Image ist per **Digest** gepinnt, nicht per Tag: ein Tag wie `:latest` kann
auf dem Registry-Server verschoben werden, ein Digest nicht.

```bash
docker pull ghcr.io/primocms/primo:v3.4.0   # neue Version holen
docker inspect --format '{{index .RepoDigests 0}}' ghcr.io/primocms/primo:v3.4.0
# ghcr.io/primocms/primo@sha256:…
```

Diesen Digest in `compose.yml` eintragen, vorher `pb_data` sichern, dann

```bash
docker compose -p diakronos-primo --env-file .env up -d
```

Nach dem Update `/api/primo/info` prüfen (neue `version`) **und** die Anmeldung
aus Abschnitt 6 erneut testen: Schreibweise und Speicherort des Auth-Stores
sind Eigenschaften der mitgelieferten PocketBase-Version. Ändert Primo sie,
muss `diakronos-sso.html` nachgezogen werden — deshalb steht der Beleg dazu im
Kopf der Datei.

---

## 9. Wenn etwas nicht klappt

| Beobachtung | Ursache / Abhilfe |
|---|---|
| `/api/primo/info` antwortet nicht | Stack läuft nicht: `docker compose -p diakronos-primo --env-file .env ps`, Logs mit `logs primo` |
| Primo zeigt nach der Übergabe wieder die Anmeldemaske | Origin von `/diakronos-sso.html` und `/admin/` unterscheidet sich, oder der Token ist abgelaufen (Diakronos erneut starten) |
| „Speicher nicht verfügbar" auf der Übergabeseite | Browser blockiert Website-Daten (privater Modus, gesperrte Cookies) |
| Diakronos bekommt `401`/`403` von Primo | Integrationskonto ohne Server-Rolle `developer`, oder Token abgelaufen (Abschnitt 4 wiederholen) |
| Veröffentlichte Seite zeigt alten Inhalt | Der Build wurde nicht aktiviert — Publikation in Primo erneut anstoßen |

Stack anhalten, ohne Daten zu verlieren:

```bash
docker compose -p diakronos-primo --env-file .env down      # Volume bleibt
docker compose -p diakronos-primo --env-file .env down -v   # LÖSCHT pb_data
```
