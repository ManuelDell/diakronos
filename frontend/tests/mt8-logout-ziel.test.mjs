/**
 * MT-8 · WÄCHTER — Abmelden führt NIE zu einer Anbieterseite.
 *
 * BEFUND (Manuel, 11.11.): Der Abmelden-Knopf schickte den Browser auf die
 * Abmeldeseite von Authentik (`end_session_endpoint`, `AUTH_OIDC_LOGOUT`).
 *
 * SOLL (nach Review 12.11.): lokale Sitzung beenden, danach
 *   a) die AUSDRÜCKLICH konfigurierte öffentliche Website (absolute
 *      http/https-Adresse aus der Server-Antwort), sonst
 *   b) der Login-Bildschirm ohne automatische SSO-Weiterleitung
 *      (`/login?sso=0`).
 * NIE eine Seite des Anbieters.
 *
 * Geprüft wird beides:
 *   1. SERVERSICHT (Quelltext von `anmeldung/routen.py`): kein
 *      `end_session_endpoint`, kein `post_logout_redirect_uri`; die Zielregel
 *      (`_oeffentliche_startseite`) liest NUR `PRIMO_PUBLIC_URL` — nicht die
 *      interne `PRIMO_URL` und kein geratenes `/`.
 *   2. CLIENT (Verhalten von `zielOderLogin` in `composables/useAbmelden.js`):
 *      Website-Adresse wird übernommen, `/login` bekommt `?sso=0`, fremde
 *      Schemata und `//host`/`/\host` werden verworfen → Login.
 *
 * Läuft im Image (frontend/tests/testliste.txt) und lokal per
 * `cd frontend && node --test tests/mt8-*.test.mjs`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (p) => readFileSync(new URL('../' + p, import.meta.url), 'utf8')

/**
 * Quelle ohne Kommentare und Docstrings — die Nennung eines abgeschalteten
 * Wegs in einer Erklärung ist kein Code. Geprüft wird, was WIRKLICH läuft.
 */
function codeZeilen(quelle) {
  const ohneBlock = quelle.replace(/"""[\s\S]*?"""/g, '')
  return ohneBlock
    .split('\n')
    .filter((z) => !z.trim().startsWith('#'))
    .join('\n')
}

// ── 1. Serversicht ─────────────────────────────────────────────────────────

test('routen.py: kein RP-initiated Logout mehr', () => {
  const code = codeZeilen(lies('../backend/src/diakronos_app/anmeldung/routen.py'))
  assert.ok(!code.includes('end_session_endpoint'),
            'der end_session_endpoint des Anbieters darf nicht mehr angesteuert werden')
  assert.ok(!code.includes('post_logout_redirect_uri'),
            'kein post_logout_redirect_uri mehr (RP-Logout ist abgeschaltet)')
  assert.ok(!code.includes('cfg.logout'),
            'AUTH_OIDC_LOGOUT wird nicht mehr ausgewertet')
})

test('routen.py: Ziel ist NUR die konfigurierte öffentliche Website', () => {
  const code = codeZeilen(lies('../backend/src/diakronos_app/anmeldung/routen.py'))
  assert.match(code, /def _oeffentliche_startseite\(\)/)
  // Roh-Feld lesen, NICHT `primo_public_url_effektiv` (dessen Default ist die
  // interne PRIMO_URL — Befund 3 des Reviews).
  assert.match(code, /getattr\(settings, "primo_public_url", ""\)/)
  assert.ok(!code.includes('primo_public_url_effektiv'),
            'die effektive Adresse fällt auf die interne PRIMO_URL zurück')
  // Kein geratenes "/" und kein Sonderfall für den Betriebs-Präfix.
  assert.ok(!/aktiver_praefix\(\):\s*\n\s*return "\/"/.test(code),
            'der Präfix darf kein "/"-Ziel mehr erzwingen')
})

test('routen.py: sonst /login?sso=0 (keine automatische SSO-Weiterleitung)', () => {
  const code = codeZeilen(lies('../backend/src/diakronos_app/anmeldung/routen.py'))
  assert.match(code, /def _abgemeldet_adresse\(\)[\s\S]{0,400}?\+ "\?sso=0"/)
  assert.match(code, /def _abmelde_startseite\(\)[\s\S]{0,200}?_abgemeldet_adresse\(\)/)
})

// ── 2. Client: `zielOderLogin` echt ausführen ──────────────────────────────

/**
 * `zielOderLogin` ist nicht exportiert; der Test schneidet die Funktion aus
 * der Quelle und führt sie mit `mitBasis`/`anmeldeUrl`-Stubs aus.
 * So wird echtes Verhalten geprüft und nicht nur ein Textmuster.
 */
function baueZielOderLogin(basePath = '') {
  const quelle = lies('src/diakonos/composables/useAbmelden.js')
  const start = quelle.indexOf('function zielOderLogin(')
  assert.ok(start > 0, 'zielOderLogin nicht gefunden')
  const ende = quelle.indexOf('\n}\n', start)
  assert.ok(ende > start, 'Ende von zielOderLogin nicht gefunden')
  const rumpf = quelle.slice(start, ende + 2)
  const mitBasis = (p) => (basePath && p !== '/' ? basePath + p : p)
  const anmeldeUrl = () => (basePath ? basePath + '/login' : '/login')
  // eslint-disable-next-line no-new-func
  const fabrik = new Function('mitBasis', 'anmeldeUrl', `${rumpf}\nreturn zielOderLogin`)
  return fabrik(mitBasis, anmeldeUrl)
}

test('Client: die konfigurierte Website-Adresse des Servers wird übernommen', () => {
  const ziel = baueZielOderLogin()
  assert.equal(ziel('https://gemeinde.example.org/'), 'https://gemeinde.example.org/')
  assert.equal(ziel('http://gemeinde.example.org/'), 'http://gemeinde.example.org/')
})

test('Client: Login-Ziel des Servers wird übernommen (mit sso=0)', () => {
  assert.equal(baueZielOderLogin()('/login?sso=0'), '/login?sso=0')
  assert.equal(baueZielOderLogin('/diakronos')('/diakronos/login?sso=0'),
               '/diakronos/login?sso=0')
  // Ein Login-Ziel OHNE sso=0 (älteren Antwort) wird ergänzt — sonst wäre das
  // Abmelden bei nur-admin/aus sofort wieder eine Anbieter-Weiterleitung.
  assert.equal(baueZielOderLogin()('/login'), '/login?sso=0')
  assert.equal(baueZielOderLogin('/diakronos')('/diakronos/login'), '/diakronos/login?sso=0')
})

test('Client: Anbieter- und fremde Adressen → nur http/https, sonst Login', () => {
  const ziel = baueZielOderLogin()
  // Eine absolute http/https-Adresse ist genau das, was die Server-Antwort
  // (aus der Konfiguration) liefert oder eben nicht — ein Anbieter-Ziel kommt
  // dort nicht mehr an.
  assert.equal(ziel('https://auth.example.org/application/o/diakronos/end-session/'),
               'https://auth.example.org/application/o/diakronos/end-session/')
  assert.equal(ziel('//auth.example.org/end-session'), '/login?sso=0')
  assert.equal(ziel('/\\auth.example.org/end-session'), '/login?sso=0')
  assert.equal(ziel('javascript:alert(1)'), '/login?sso=0')
  assert.equal(ziel('data:text/html,<script>alert(1)</script>'), '/login?sso=0')
})

test('Client: Positivliste — `\\\\host`, `\\/host`, Steuerzeichen im Pfad → Login', () => {
  const ziel = baueZielOderLogin()
  // Zwei fuehrende Backslashes: Chrome normalisiert `\\host` zu `//host` und
  // behaelt die Herkunft NICHT — der Pfad-Test verbietet ihn deshalb.
  assert.equal(ziel('\\\\auth.example.org/end'), '/login?sso=0')
  assert.equal(ziel('\\\\auth.example.org'), '/login?sso=0')
  // Backslash als erster Pfad-Teil nach dem Slash (`/\host`).
  assert.equal(ziel('\\/auth.example.org/end'), '/login?sso=0')
  assert.equal(ziel('/\\/auth.example.org'), '/login?sso=0')
  // Steuerzeichen (Tab/CR/LF) in einem relativen Ziel: Browser und
  // Zwischenspeicher zerlegen die Adresse an solchen Stellen.
  assert.equal(ziel('/\tauth.example.org'), '/login?sso=0')
  assert.equal(ziel('/diakonos\t/kalender'), '/login?sso=0')
  assert.equal(ziel('/diakonos\r\nX: y'), '/login?sso=0')
  assert.equal(ziel('/login\t?sso=0'), '/login?sso=0', 'Login-Ziel bleibt Login (sso=0 gesetzt)')
  // Gegenprobe: ein normaler relativer Pfad wird uebernommen.
  assert.equal(ziel('/diakonos/kalender'), '/diakonos/kalender')
  assert.equal(ziel('/olb?tag=1&x=2'), '/olb?tag=1&x=2')
})

test('Client: leeres Ziel, "/" und SPA-Wurzel fallen auf den Login zurück', () => {
  const ziel = baueZielOderLogin()
  assert.equal(ziel(''), '/login?sso=0')
  // Review-Befund 1: "/" ist NICHT die Website.
  assert.equal(ziel('/'), '/login?sso=0')
  assert.equal(ziel('#/'), '/login?sso=0')
  assert.equal(ziel('/diakonos'), '/login?sso=0')
  assert.equal(baueZielOderLogin('/diakronos')('/diakronos/diakonos'), '/diakronos/login?sso=0')
})
