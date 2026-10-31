/**
 * WEB-4 — Wächter: der Gemeinde-Eingang routet jede Pfadgruppe richtig.
 *
 * Der Eingang (`deploy/eingang/nginx.conf.template`) verteilt EINE Domain auf
 * zwei Systeme. Ein Fehler hier ist nicht kosmetisch: landet /api/ bei
 * Diakronos statt bei Primo (oder umgekehrt), schlägt jede Anmeldung fehl und
 * die Redaktion kommt nicht in den Editor.
 *
 * Dieser Test liest die ECHTE Vorlage (keine Kopie) und prüft die Zusagen aus
 * der Vorgabe Manuel 2026-10-30:
 *
 *   /diakronos, /diakronos/…  -> Diakronos, Pfad UNVERÄNDERT (kein Strippen)
 *   /api/…, /admin/…,         -> Primo
 *   /diakronos-sso.html
 *   /primo, /primo/           -> 302 /admin/
 *   /login                    -> 302 ${EINGANG_LOGIN_PFAD}
 *   /_/                       -> 404
 *   Rest inkl. /              -> Primo; / ohne Site -> 302 LOGIN
 *
 * Er prüft außerdem die Dinge, die man beim Aufräumen versehentlich kaputt
 * macht: WebSocket/SSE (pufferndes Proxy = toter Realtime-Kanal), Host-Header
 * für die Site-Wahl von Primo, keine doppelten Security-Header und keine
 * Platzhalter, die der Entrypoint nicht ersetzt.
 *
 * Der Laufzeit-Beweis (nginx -t + echte HTTP-Matrix gegen zwei Echo-Upstreams)
 * steht in `tools/web4_eingang_matrix.py` und läuft im Image.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const VORLAGE = join(REPO, 'deploy', 'eingang', 'nginx.conf.template')
const COMPOSE = join(REPO, 'deploy', 'eingang', 'compose.yml')
const ENTRYPOINT = join(REPO, 'deploy', 'eingang', '15-vorlage.sh')
const ENV_BEISPIEL = join(REPO, 'deploy', 'eingang', '.env.example')

const conf = readFileSync(VORLAGE, 'utf8')

/** Alle location-Blöcke (Name + Rumpf) aus der Vorlage. */
function locations(text) {
  const aus = []
  // `location = /pfad {` -> exakt; `location /pfad {` -> Praefix.
  // WEB-6: zusätzlich `location ^~ /pfad {` (Sperren/Streng-Praefix gewinnen in
  // nginx gegen jeden normalen Praefix-Block). Die Form wird in `typ` geführt,
  // `exakt` bleibt für die bestehenden Prüfungen wahr/falsch.
  // Zwei Fallen, die der Ausdruck abfangen muss:
  //   * "location" muss ein WORT sein — sonst wird auch
  //     `map $upstream_http_location $ohne_site {` als Block gelesen;
  //   * der Pfad darf ${PLATZHALTER} enthalten — ein einfaches [^\s{]+
  //     bricht an der schliessenden Klammer des Platzhalters ab.
  const re = /(?:^|[\s;}])location\s+(=\s+|\^~\s+)?((?:\$\{[A-Z_]+\}|[^\s{])+)\s*\{/g
  let m
  while ((m = re.exec(text)) !== null) {
    // Rumpf bis zur passenden schließenden Klammer (Blöcke sind hier flach).
    let tiefe = 1
    let i = re.lastIndex
    while (i < text.length && tiefe > 0) {
      if (text[i] === '{') tiefe += 1
      else if (text[i] === '}') tiefe -= 1
      i += 1
    }
    aus.push({
      exakt: Boolean(m[1] && m[1].startsWith('=')),
      typ: m[1] ? m[1].trim() : '',
      pfad: m[2],
      rumpf: text.slice(re.lastIndex, i - 1),
    })
  }
  return aus
}

const LOC = locations(conf)
const finde = (pfad, exakt = true) =>
  LOC.find((l) => l.pfad === pfad && l.exakt === exakt)

test('WEB-4: die Vorlage und ihre Begleitdateien liegen im Repo', () => {
  for (const datei of [VORLAGE, COMPOSE, ENTRYPOINT, ENV_BEISPIEL]) {
    assert.ok(existsSync(datei), `${datei} fehlt`)
  }
})

test('WEB-4: /diakronos geht an Diakronos — exakt und als Präfix', () => {
  for (const [pfad, exakt] of [
    ['${EINGANG_DIAKRONOS_PRAEFIX}', true],
    ['${EINGANG_DIAKRONOS_PRAEFIX}/', false],
  ]) {
    const block = finde(pfad, exakt)
    assert.ok(block, `location ${exakt ? '= ' : ''}${pfad} fehlt`)
    assert.match(
      block.rumpf,
      /proxy_pass\s+http:\/\/\$\{EINGANG_DIAKRONOS_UPSTREAM\};/,
      `${pfad} muss an den Diakronos-Upstream gehen`,
    )
  }
})

test('WEB-4: Diakronos-Pfad wird NICHT umgeschrieben (kein Präfix-Strippen)', () => {
  const praefix = finde('${EINGANG_DIAKRONOS_PRAEFIX}/', false)
  // proxy_pass mit URI-Teil (z. B. `proxy_pass http://upstream/;`) würde den
  // Pfad ersetzen. Genau das darf hier nicht passieren.
  assert.doesNotMatch(
    praefix.rumpf,
    /proxy_pass\s+http:\/\/[^;\s]+\//,
    'proxy_pass darf keine URI enthalten — sonst wird /diakronos/… abgeschnitten',
  )
  assert.doesNotMatch(praefix.rumpf, /\brewrite\b/, 'kein rewrite im Präfix-Block')
  assert.doesNotMatch(praefix.rumpf, /\b(alias|root)\b/, 'kein alias/root im Präfix-Block')
})

test('WEB-4: /api/, /admin/ und die Übergabeseite gehen an Primo', () => {
  for (const [pfad, exakt] of [
    ['/api/', false],
    ['/admin/', false],
    ['/diakronos-sso.html', true],
  ]) {
    const block = finde(pfad, exakt)
    assert.ok(block, `location ${exakt ? '= ' : ''}${pfad} fehlt`)
    assert.match(
      block.rumpf,
      /proxy_pass\s+http:\/\/\$\{EINGANG_PRIMO_UPSTREAM\};/,
      `${pfad} muss an den Primo-Upstream gehen`,
    )
  }
})

test('WEB-4: /primo und /primo/ leiten auf /admin/ um', () => {
  for (const pfad of ['/primo', '/primo/']) {
    const block = finde(pfad)
    assert.ok(block, `location = ${pfad} fehlt`)
    assert.match(block.rumpf, /return\s+302\s+\/admin\/;/, `${pfad} -> 302 /admin/`)
  }
})

test('WEB-4: /login leitet auf den Anmeldepfad um (302)', () => {
  const block = finde('/login')
  assert.ok(block, 'location = /login fehlt')
  assert.match(block.rumpf, /return\s+302\s+\$\{EINGANG_LOGIN_PFAD\};/)
})

test('WEB-4: die PocketBase-Superuser-UI ist auf der Domain gesperrt', () => {
  const block = finde('/_/', false)
  assert.ok(block, 'location /_/ fehlt')
  // 404 statt 403: ein 403 würde die Existenz der Oberfläche bestätigen.
  assert.match(block.rumpf, /return\s+404;/, '/_/ muss mit 404 antworten')
})

test('WEB-4: alles andere geht an Primo — / inklusive', () => {
  const block = finde('/', false)
  assert.ok(block, 'location / fehlt')
  assert.match(block.rumpf, /proxy_pass\s+http:\/\/\$\{EINGANG_PRIMO_UPSTREAM\};/)

  const wurzel = finde('/', true)
  assert.ok(wurzel, 'location = / fehlt')
  assert.match(wurzel.rumpf, /proxy_pass\s+http:\/\/\$\{EINGANG_PRIMO_UPSTREAM\};/)
  // Die Auswertung "keine Site" darf NICHT global hängen: ein error_page auf
  // Server-Ebene würde auch /login und /primo umbiegen (Regression im Bau).
  assert.match(wurzel.rumpf, /proxy_intercept_errors\s+on;/)
  assert.match(wurzel.rumpf, /error_page\s+301\s+302\s+303\s+307\s+308\s+=\s+@eingang_redirect;/)
  assert.doesNotMatch(
    conf,
    /\n {4}error_page\s+30/,
    'error_page gehört in den location-Block, nicht auf die Server-Ebene',
  )
})

test('WEB-4: "keine Website für diesen Host" führt in die Anmeldung', () => {
  assert.match(
    conf,
    /map\s+\$upstream_http_location\s+\$ohne_site\s*\{[^}]*"~\*\^\(https\?:\/\/\[\^\/\]\+\)\?\/admin\/\?\$"\s+1;/,
    'map $ohne_site muss den Primo-Fallback auf /admin erkennen (relativ UND absolut)',
  )
  const ziel = LOC.find((l) => l.pfad === '@eingang_redirect')
  assert.ok(ziel, 'location @eingang_redirect fehlt')
  assert.match(ziel.rumpf, /if\s+\(\$ohne_site\s*=\s*1\)\s*\{\s*return\s+302\s+\$\{EINGANG_LOGIN_PFAD\};/)
})

test('WEB-4: Host-Header geht unverändert an beide Upstreams', () => {
  // Primo wählt die Site am Host (serve.go: sites.host); Diakronos prüft ihn.
  assert.match(conf, /proxy_set_header\s+Host\s+\$http_host;/)
  assert.doesNotMatch(
    conf,
    /proxy_set_header\s+Host\s+(\$proxy_host|\$host;)/,
    'der Host darf nicht auf den Upstream-Namen umgeschrieben werden',
  )
  // Hinter NPM/TLS muss das urspruengliche Schema durchgereicht werden (sonst
  // Sitzungs-Cookie ohne Secure-Flag, Vorfall 30.10.); Fallback auf $scheme.
  assert.match(conf, /proxy_set_header\s+X-Forwarded-Proto\s+\$weitergabe_schema;/)
  assert.match(conf, /map \$http_x_forwarded_proto \$weitergabe_schema \{[^}]*""\s+\$scheme;/)
  assert.match(conf, /proxy_set_header\s+X-Forwarded-For\s+\$remote_addr;/)
})

test('WEB-4: WebSocket und SSE werden durchgereicht (kein Puffern)', () => {
  assert.match(conf, /proxy_http_version\s+1\.1;/)
  assert.match(conf, /proxy_set_header\s+Upgrade\s+\$http_upgrade;/)
  assert.match(conf, /proxy_set_header\s+Connection\s+\$verbindung_upgrade;/)
  assert.match(conf, /proxy_buffering\s+off;/)
  assert.match(conf, /proxy_read_timeout\s+3600s;/)
  // Die Upgrade-Abbildung muss leer -> close abbilden (sonst hängt jede
  // normale Anfrage mit "Connection: upgrade").
  assert.match(conf, /map\s+\$http_upgrade\s+\$verbindung_upgrade\s*\{[^}]*default\s+upgrade;[^}]*''\s+close;/)
})

test('WEB-4: keine doppelten Security-Header (Diakronos setzt seine eigenen)', () => {
  const verboten = [
    'Strict-Transport-Security',
    'Content-Security-Policy',
    'X-Frame-Options',
    'X-Content-Type-Options',
    'Referrer-Policy',
    'Permissions-Policy',
  ]
  // Kopfzeilen zählen nur als echtes add_header, nicht im Kommentar.
  const aktiv = conf
    .split('\n')
    .filter((z) => !z.trim().startsWith('#'))
    .join('\n')
  for (const name of verboten) {
    assert.doesNotMatch(
      aktiv,
      new RegExp(`add_header\\s+${name}`),
      `${name} darf der Eingang nicht setzen — sonst zwei Werte auf einer Antwort`,
    )
  }
})

test('WEB-4: jeder Platzhalter der Vorlage wird vom Entrypoint ersetzt', () => {
  const platzhalter = new Set()
  for (const m of conf.matchAll(/\$\{(EINGANG_[A-Z_]+)\}/g)) platzhalter.add(m[1])
  assert.ok(platzhalter.size >= 4, `zu wenige Platzhalter: ${[...platzhalter]}`)

  const entry = readFileSync(ENTRYPOINT, 'utf8')
  const liste = entry.match(/envsubst\s+'([^']+)'/)
  assert.ok(liste, 'envsubst-Aufruf mit ausdrücklicher Liste fehlt')
  const ersetzt = new Set([...liste[1].matchAll(/\$\{(EINGANG_[A-Z_]+)\}/g)].map((m) => m[1]))

  for (const name of platzhalter) {
    assert.ok(
      ersetzt.has(name),
      `${name} steht in der Vorlage, aber nicht in der envsubst-Liste`,
    )
  }
})

test('WEB-4: nginx-Variablen bleiben vor envsubst geschützt', () => {
  const entry = readFileSync(ENTRYPOINT, 'utf8')
  // Ohne Liste würde envsubst auch $http_host/$upstream_http_location leeren.
  assert.match(entry, /envsubst\s+'/, 'envsubst braucht eine ausdrückliche Variablenliste')
  assert.doesNotMatch(entry, /envsubst\s*<\s*"\$VORLAGE"/, 'envsubst ohne Liste ist verboten')
  assert.match(entry, /nginx -t/, 'der Entrypoint muss die Config vor dem Start prüfen')
})

test('WEB-4: Compose veröffentlicht nur Loopback und pinnt nginx', () => {
  const compose = readFileSync(COMPOSE, 'utf8')
  assert.match(compose, /image:\s+nginx:1\.27-alpine/)
  assert.match(
    compose,
    /- "\$\{EINGANG_BIND_ADDR:-127\.0\.0\.1\}:\$\{EINGANG_PORT:-8120\}:80"/,
    'Bind-Adresse muss per Env steuerbar und standardmäßig Loopback sein',
  )
  // Kein fremd benanntes Image bauen/taggen (Regel 12 der Karte).
  assert.doesNotMatch(compose, /^\s*build:/m, 'der Eingang baut kein Image')
  assert.doesNotMatch(compose, /diakronos-standalone-app/, 'nie das Betriebs-Image referenzieren')
})

test('WEB-4: Beispiel-Env nennt alle Stellschrauben', () => {
  const env = readFileSync(ENV_BEISPIEL, 'utf8')
  for (const name of [
    'EINGANG_BIND_ADDR',
    'EINGANG_PORT',
    'EINGANG_DIAKRONOS_UPSTREAM',
    'EINGANG_PRIMO_UPSTREAM',
    'EINGANG_DIAKRONOS_PRAEFIX',
    'EINGANG_LOGIN_PFAD',
  ]) {
    assert.match(env, new RegExp(`^${name}=`, 'm'), `${name} fehlt in .env.example`)
  }
  assert.match(env, /^EINGANG_DIAKRONOS_PRAEFIX=\/diakronos$/m)
  assert.match(env, /^EINGANG_LOGIN_PFAD=\/diakronos\/login$/m)
})

// ── WEB-6: unbekannte Adressen fuehren auf die Hauptseite statt 404 ──────────
//
// Vorgabe Manuel 2026-10-30: "Alle nicht registrierten Links sollen auf die
// Hauptseite fuehren und nicht 404 geben." Die Faelle, die dabei NICHT
// umgebogen werden duerfen, sind der eigentliche Fehlerherd (API, Dateien,
// Editor, Superuser-Sperren) — sie werden hier am Aufbau der Vorlage geprueft.
//
// Der Laufzeit-Beweis (echte HTTP-Matrix im nginx) steht zwischen den Zeilen
// von `tools/web4_eingang_matrix.py`; dieser Waechter haelt die STRUKTUR fest.

/** Alle Locations, deren Rumpf 404 abfaengt (WEB-6). */
const abfaenger = LOC.filter((l) => /error_page\s+404/.test(l.rumpf))
const pfade = abfaenger.map((l) => l.pfad)

test('WEB-6 (R1): Seiten-Locations fangen den 404 ab und fuehren auf "/"', () => {
  // Website (Praefix /), Diakronos (Praefix + exakt), Editor, Superuser-UI.
  for (const pfad of [
    '/',
    '${EINGANG_DIAKRONOS_PRAEFIX}',
    '${EINGANG_DIAKRONOS_PRAEFIX}/',
    '/admin/',
    '/_/',
  ]) {
    const block = LOC.find((l) => l.pfad === pfad && /error_page\s+404\s+=\s+@eingang_unbekannt;/.test(l.rumpf))
    assert.ok(block, `location ${pfad} faengt den 404 nicht ab (WEB-6, R1)`)
  }
})

test('WEB-6 (R2): als Seitenaufruf gilt nur GET/HEAD mit Accept text/html', () => {
  assert.match(
    conf,
    /map\s+\$http_accept\s+\$eingang_seitenaufruf\s*\{[^}]*default\s+0;[^}]*"~\*text\/html"\s+1;/,
    'Accept ohne text/html muss als "kein Seitenaufruf" gelten',
  )
  assert.match(
    conf,
    /map\s+"\$request_method:\$eingang_seitenaufruf"\s+\$eingang_seitenabruf\s*\{[^}]*default\s+0;[^}]*"\~\*\^\(GET\|HEAD\):1\$"\s+1;/,
    'nur GET und HEAD duerfen als Seitenaufruf gelten',
  )
  // Der Handler entscheidet: kein Seitenaufruf -> 404, Seitenaufruf -> 302 "/".
  const handler = LOC.find((l) => l.pfad === '@eingang_unbekannt')
  assert.ok(handler, 'location @eingang_unbekannt fehlt')
  assert.match(
    handler.rumpf,
    /if\s*\(\$eingang_seitenabruf\s*=\s*0\)\s*\{\s*rewrite\s+\^\s+\/_eingang_unbekannt\s+last;\s*\}/,
    'ohne Seitenaufruf muss der 404 bleiben (kein 302)',
  )
  assert.match(handler.rumpf, /return\s+302\s+\/;/, 'Seitenaufruf -> 302 auf "/"')
  // Die 404-Antwort liegt in einem INTERNEN Block (von aussen nicht adressierbar).
  const intern = LOC.find((l) => l.pfad === '/_eingang_unbekannt')
  assert.ok(intern, 'location = /_eingang_unbekannt fehlt')
  assert.match(intern.rumpf, /\binternal;/, 'der 404-Zielblock muss internal sein')
  assert.match(intern.rumpf, /return\s+404;/, 'der 404-Zielblock muss 404 liefern')
})

test('WEB-6 (R3): API-, Datei- und Editor-Datenpfade werden NICHT abgefangen', () => {
  // Diese Locations duerfen den Fehler des Upstreams nicht ersetzen: ein 302
  // auf "/" waere fuer einen API-Aufrufer eine Schein-Antwort.
  for (const pfad of [
    '/api/',                              // PocketBase der Website
    '${EINGANG_DIAKRONOS_PRAEFIX}/api/',  // Diakronos-API
    '${EINGANG_DIAKRONOS_PRAEFIX}/files/',
    '${EINGANG_DIAKRONOS_PRAEFIX}/private/files/',
    '${EINGANG_DIAKRONOS_PRAEFIX}/socket.io/',
  ]) {
    const block = LOC.filter((l) => l.pfad === pfad).pop()
    assert.ok(block, `location ${pfad} fehlt (WEB-6, R3)`)
    assert.doesNotMatch(
      block.rumpf,
      /error_page|proxy_intercept_errors/,
      `${pfad} darf keinen 404 abfangen (R3)`,
    )
    assert.match(block.rumpf, /proxy_pass\s+http:\/\//, `${pfad} muss an einen Upstream gehen`)
  }
  // Die Diakronos-Datenpfade muessen den Praefix-Block ueberstimmen, sonst
  // faengt dieser ihre 404 ab (nginx: laengster Praefix gewinnt — `^~` macht
  // das unabhaengig von der Reihenfolge eindeutig).
  for (const pfad of ['${EINGANG_DIAKRONOS_PRAEFIX}/api/', '${EINGANG_DIAKRONOS_PRAEFIX}/files/']) {
    assert.ok(
      LOC.some((l) => l.pfad === pfad && l.typ === '^~'),
      `${pfad} muss ein eigener ^~-Block sein (sonst faengt der Praefix-Block ab)`,
    )
  }
})

test('WEB-6 (R4): gesperrte Pfade verraten nichts und bleiben 404', () => {
  // PocketBase-Superuser-API: unveraendert 404, KEIN Umbiegen auf "/".
  for (const pfad of [
    '/api/collections/_superusers/',
    '/api/settings',
    '/api/backups',
    '/api/logs',
    '/api/crons',
  ]) {
    const block = LOC.filter((l) => l.pfad === pfad).pop()
    assert.ok(block, `Sperre ${pfad} fehlt`)
    assert.match(block.rumpf, /return\s+404;/, `${pfad} muss 404 liefern`)
    assert.doesNotMatch(block.rumpf, /error_page/, `${pfad} darf nicht auf "/" umbiegen`)
  }
  // Die Sperren muessen `^~` tragen: sonst gewinnt der laengere `/`-Block
  // bzw. der Praefix-Block und die Antwort veraendert sich.
  assert.match(conf, /location\s+\^~\s+\/api\/settings\s*\{\s*return\s+404;\s*\}/)
  assert.match(conf, /location\s+\^~\s+\/api\/collections\/_superusers\/\s*\{\s*return\s+404;\s*\}/)
})

test('WEB-6 (R5): kein Umleitungs-Kreis — "/" wird nicht abgefangen', () => {
  const wurzel = LOC.find((l) => l.pfad === '/' && l.exakt)
  assert.ok(wurzel, 'location = / fehlt')
  assert.doesNotMatch(
    wurzel.rumpf,
    /error_page\s+404/,
    '/ ist das Ziel der Umleitung und darf keinen 404 abfangen (Kreis)',
  )
  // Relatives Ziel: absolute_redirect off bleibt gesetzt, sonst nennt nginx
  // hinter NPM/TLS sein eigenes Schema.
  assert.match(conf, /absolute_redirect\s+off;/)
  const handler = LOC.find((l) => l.pfad === '@eingang_unbekannt')
  assert.match(handler.rumpf, /return\s+302\s+\/;/, 'Ziel muss relativ "/" sein')
})

test('WEB-6: unbekannte Website-Adresse fuehrt auf die Hauptseite (Vorgabe)', () => {
  // Der Website-Block (location /) faengt den 404 ab — und zwar MIT
  // `proxy_intercept_errors on`: ohne diese Direktive greift `error_page`
  // nur fuer selbst erzeugte Fehler, der 404 des Upstreams liefe durch.
  const website = LOC.find((l) => l.pfad === '/' && !l.exakt)
  assert.ok(website, 'location / fehlt')
  assert.match(website.rumpf, /proxy_intercept_errors\s+on;/)
  assert.match(website.rumpf, /error_page\s+404\s+=\s+@eingang_unbekannt;/)
  // Diakronos genauso (beide Bloecke).
  for (const pfad of ['${EINGANG_DIAKRONOS_PRAEFIX}', '${EINGANG_DIAKRONOS_PRAEFIX}/']) {
    const block = LOC.find((l) => l.pfad === pfad)
    assert.match(block.rumpf, /proxy_intercept_errors\s+on;/)
    assert.match(block.rumpf, /error_page\s+404\s+=\s+@eingang_unbekannt;/)
  }
})
