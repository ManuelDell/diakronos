/**
 * WEB-2 — Login-Uebergabeseite Diakronos -> Primo (deploy/primo/diakronos-sso.html).
 *
 * Warum dieser Test: die Seite schreibt eine Anmeldung in den Browser-Speicher
 * einer FREMDEN Anwendung (Primo/Admin). Ein Tippfehler im Speicherschluessel
 * oder in der Wertform faellt im Betrieb nicht als Fehler auf — Primo zeigt
 * dann einfach wieder das Anmeldeformular, und niemand weiss, warum. Genauso
 * still waere ein Token in der Adresszeile oder in der Konsole.
 *
 * Geprueft wird der AUSGELIEFERTE Code, nicht eine Nachbildung: der Block
 * zwischen DKRECHEN-ANFANG und DKRECHEN-ENDE wird aus der HTML-Datei gelesen,
 * mit node ausgewertet und gegen die Faelle aus dem Kartentext geprueft.
 *
 * Abgedeckt:
 *   1. Speicherschluessel/-form exakt wie in Primo v3.3.1 belegt
 *      (localStorage['pocketbase_auth'] = {token, record}),
 *   2. Fragment mit gueltigem Token+Record wird angenommen,
 *   3. base64url-Record inkl. Umlauten wird entschluesselt,
 *   4. Fehlerfaelle: fehlender/kaputter Token, falscher type, abgelaufen,
 *      Record ohne id/email, Token/Record widerspruechlich, fehlender Record,
 *   5. kein Token-Leak: keine console-Ausgabe, kein Token im DOM-Text,
 *   6. keine externen Quellen (src/href auf fremde Hosts),
 *   7. Fragment wird per history.replaceState entfernt und danach nach
 *      /admin/ weitergeleitet (Reihenfolge geprueft),
 *   8. die Seite funktioniert auch dort, wo `escape` fehlt (strenger Modus
 *      bzw. strikte CSP-Umgebung) — Entschluesselung ohne escape().
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const hier = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(hier, '..', '..')
const seite = path.join(repo, 'deploy', 'primo', 'diakronos-sso.html')
const html = fs.readFileSync(seite, 'utf8')

function rohblock(anfang, ende) {
  const a = html.indexOf(anfang)
  const e = html.indexOf(ende)
  assert.ok(a >= 0 && e > a, `Marker ${anfang}/${ende} fehlen in ${seite}`)
  return [html.slice(a + anfang.length, e), a]
}

function block(anfang, ende) {
  // Zurueck kommt der CODE zwischen den Markern; reine Kommentarzeilen fallen
  // weg (sonst stuende der Erklaerungstext des Markers als nackter Text im
  // ausgewerteten Code).
  return rohblock(anfang, ende)[0]
    .split('\n')
    .filter((z) => !z.trim().startsWith('//'))
    .join('\n')
}

const skriptRoh = rohblock('<script id="dk-sso-uebergabe">', '</script>')[0]
assert.ok(skriptRoh.includes('DKRECHEN-ANFANG') && skriptRoh.includes('DKRECHEN-ENDE'),
  'Rechenteil-Marker fehlen im Skript')
// Nur im Skript schneiden: die HTML-Kopfzeile nennt dieselben Stichworte.
// Beginn ist der Zeilenanfang VOR dem Marker (die Markerzeile selbst ist ein
// Kommentar und faellt unten mit weg).
const vonZeile = skriptRoh.lastIndexOf('\n', skriptRoh.indexOf('DKRECHEN-ANFANG'))
const bisZeile = skriptRoh.lastIndexOf('\n', skriptRoh.indexOf('DKRECHEN-ENDE'))
const rechenteil = 'var SPEICHER_SCHLUESSEL, ZIEL;\n'
  + skriptRoh.slice(vonZeile, bisZeile)
    .split('\n')
    .filter((z) => !z.trim().startsWith('//'))
    .join('\n')
const skript = block('<script id="dk-sso-uebergabe">', '</script>')

// Rechenteil in eine Umgebung laden, die NUR atob kennt — kein window, kein
// localStorage, kein document. So faellt auf, wenn dort doch DOM-Code landet.
const log = []
const kontext = {
  atob: (s) => Buffer.from(s, 'base64').toString('latin1'),
  console: {
    log: (...a) => log.push(['log', ...a]),
    warn: (...a) => log.push(['warn', ...a]),
    error: (...a) => log.push(['error', ...a]),
    info: (...a) => log.push(['info', ...a]),
    debug: (...a) => log.push(['debug', ...a]),
  },
}
vm.createContext(kontext)
vm.runInContext(rechenteil + '\n;globalThis.__pruefe = pruefe;', kontext)
const pruefe = kontext.__pruefe

// ── Hilfen fuer Testdaten ────────────────────────────────────────────────
const b64url = (text) => Buffer.from(text, 'utf8').toString('base64')
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

function jwt(nutzlast, signatur = 'c2lnbmF0dXJl') {
  return [b64url('{"alg":"HS256","typ":"JWT"}'), b64url(JSON.stringify(nutzlast)), signatur].join('.')
}

const JETZT = Date.parse('2026-10-30T12:00:00Z')
const gueltig = () => jwt({
  id: 'k7x2m9p1q4r8s3t',
  type: 'auth',
  collectionId: 'pbc_users_0001',
  collectionName: 'users',
  exp: Math.floor(JETZT / 1000) + 3600,
})
// Fuer den Browser-Ablauf: dort laeuft Date.now() wirklich, also weit in der
// Zukunft ablaufen lassen (sonst pruefte der Test versehentlich "abgelaufen").
const gueltigJetzt = () => jwt({
  id: 'k7x2m9p1q4r8s3t',
  type: 'auth',
  collectionId: 'pbc_users_0001',
  collectionName: 'users',
  exp: Math.floor(Date.now() / 1000) + 86400,
})
const gueltigerRecord = {
  id: 'k7x2m9p1q4r8s3t',
  email: 'redaktion@example.org',
  collectionId: 'pbc_users_0001',
  collectionName: 'users',
  serverRole: 'editor',
}
const fragment = (token, record) => {
  const teile = ['token=' + encodeURIComponent(token)]
  if (record !== undefined) {
    teile.push('record=' + encodeURIComponent(Buffer.from(JSON.stringify(record), 'utf8').toString('base64url')))
  }
  return teile.join('&')
}

// ── 1. Speicherort belegt ────────────────────────────────────────────────
test('Speicherschluessel und -form entsprechen Primo v3.3.1 (LocalAuthStore)', () => {
  assert.match(html, /var SPEICHER_SCHLUESSEL = 'pocketbase_auth'/,
    'Schluessel muss literal "pocketbase_auth" sein (PocketBase LocalAuthStore-Default)')
  assert.match(html, /window\.localStorage\.setItem\(SPEICHER_SCHLUESSEL/,
    'Anmeldung gehoert in localStorage (dort liest Primo), nicht in sessionStorage')
  assert.doesNotMatch(html, /sessionStorage/,
    'sessionStorage kaeme einer anderen Sitzung nicht zugute — Primo liest localStorage')

  const r = pruefe(fragment(gueltig(), gueltigerRecord), JETZT, kontext.atob)
  assert.equal(r.ok, true)
  assert.deepEqual(Object.keys(r.eintrag).sort(), ['record', 'token'],
    'Wertform ist {"token","record"} — nicht {"token","model"}')
  assert.equal(typeof r.eintrag.token, 'string')
  assert.equal(r.eintrag.record.id, gueltigerRecord.id)
})

// ── 2. Ziel und Weiterleitung ────────────────────────────────────────────
test('leitet auf /admin/ weiter, nicht auf eine andere Seite', () => {
  assert.match(html, /var ZIEL = '\/admin\/'/)
  assert.match(html, /window\.location\.replace\(ZIEL\)/)
  assert.doesNotMatch(html, /location\.href = /, 'replace() statt href: der Token-Aufruf bleibt nicht im Verlauf')
})

// ── 3. Gutfall + Umlaute ─────────────────────────────────────────────────
test('gueltige Uebergabe wird angenommen, Umlaute im Record bleiben erhalten', () => {
  const record = { ...gueltigerRecord, email: 'grüße@example.org', name: 'Jürgen Ölschläger' }
  const r = pruefe(fragment(gueltig(), record), JETZT, kontext.atob)
  assert.equal(r.ok, true, JSON.stringify(r))
  assert.equal(r.eintrag.record.email, 'grüße@example.org')
  assert.equal(r.eintrag.record.name, 'Jürgen Ölschläger')
})

test('record ohne collectionId/collectionName wird aus dem Token ergaenzt', () => {
  const r = pruefe(fragment(gueltig(), { id: gueltigerRecord.id, email: 'a@example.org' }), JETZT, kontext.atob)
  assert.equal(r.ok, true)
  assert.equal(r.eintrag.record.collectionName, 'users')
  assert.equal(r.eintrag.record.collectionId, 'pbc_users_0001')
})

// ── 4. Fehlerfaelle ──────────────────────────────────────────────────────
test('Fehlerfaelle liefern eine verstaendliche Meldung und keinen Eintrag', () => {
  const faelle = [
    ['leeres Fragment', '', /Keine Anmeldedaten/],
    ['nur record', 'record=' + b64url('{"id":"x"}'), /Anmeldeparameter fehlt/],
    ['Token kein JWT', fragment('nicht-ein-jwt'), /unbekanntes Format/],
    ['JWT mit zwei Teilen', fragment('aaa.bbb'), /unbekanntes Format/],
    ['JWT mit Sonderzeichen', fragment('aa$.bb.cc'), /unbekanntes Format/],
    ['type != auth', fragment(jwt({ id: 'x', type: 'file' }), gueltigerRecord), /kein Anmeldetoken/],
    ['abgelaufen', fragment(jwt({ id: gueltigerRecord.id, type: 'auth', exp: Math.floor(JETZT / 1000) - 1 }), gueltigerRecord), /abgelaufen/],
    ['Record kaputt', fragment(gueltig()) + '&record=' + encodeURIComponent('%%%'), /nicht lesbar/],
    ['Record ohne id', fragment(gueltig(), { email: 'a@example.org' }), /keine gültige Kennung/],
    ['Record ohne @', fragment(gueltig(), { id: 'k7x2m9p1q4r8s3t', email: 'kaputt' }), /keine gültige Kennung/],
    ['Record-Array', fragment(gueltig(), [1, 2]), /nicht lesbar/],
    ['Token/Record widerspruechlich', fragment(gueltig(), { ...gueltigerRecord, id: 'anderer0000000' }), /gehören nicht zusammen/],
    ['Record fehlt, Token hat id', fragment(gueltig()), /Kontodaten fehlen/],
  ]
  for (const [name, roh, muster] of faelle) {
    const r = pruefe(roh, JETZT, kontext.atob)
    assert.equal(r.ok, false, `${name}: haette abgelehnt werden muessen`)
    assert.equal(r.eintrag, undefined, `${name}: kein Eintrag bei Fehler`)
    assert.match(r.titel + ' ' + r.text, muster, `${name}: Meldung unerwartet`)
    // Meldungen duerfen keine Teile des Tokens enthalten.
    assert.ok(!r.text.includes('eyJ') && !r.titel.includes('eyJ'), `${name}: Token in Meldung`)
  }
})

test('sehr langer Token wird beschnitten statt unbegrenzt durchgereicht', () => {
  const lang = 'a'.repeat(20000) + '.' + 'b'.repeat(10) + '.' + 'c'.repeat(10)
  const r = pruefe(fragment(lang), JETZT, kontext.atob)
  assert.equal(r.ok, false, 'ein 20-kB-"Token" ist kein gueltiges JWT')
})

// ── 5. Kein Token-Leak ───────────────────────────────────────────────────
test('kein console-Aufruf und keine Token-Ausgabe im Dokument', () => {
  assert.doesNotMatch(skript, /console\./,
    'Die Seite darf nichts protokollieren — jeder Log koennte den Token enthalten')
  assert.equal(log.length, 0, 'beim Pruefen wurde etwas protokolliert')

  const sichtbar = html
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/<!--[\s\S]*?-->/g, '')
  assert.doesNotMatch(sichtbar, /eyJ[A-Za-z0-9_-]{10,}/, 'JWT-Muster im sichtbaren Text')
  assert.doesNotMatch(skript, /innerHTML|outerHTML|insertAdjacentHTML/,
    'Token-/Record-Inhalte nur per textContent einsetzen (XSS-Flaeche)')
  assert.match(skript, /textContent/, 'Meldungen werden per textContent gesetzt')
})

// ── 6. Keine externen Quellen ────────────────────────────────────────────
test('laedt keine externen Skripte, Stile, Schriften oder Bilder', () => {
  const extern = [...html.matchAll(/\b(?:src|href)\s*=\s*"([^"]*)"/gi)]
    .map((m) => m[1])
    .filter((z) => /^(?:https?:)?\/\//i.test(z) || z.startsWith('data:'))
  assert.deepEqual(extern, [], 'keine externen oder eingebetteten Quellen erlaubt')
  assert.doesNotMatch(html, /@import/i, 'kein CSS-Nachladen')
  const css = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map((m) => m[1]).join('\n')
  assert.doesNotMatch(css, /url\s*\(/i, 'keine Hintergrundbilder/Schriften aus dem Netz')
  assert.equal((html.match(/<script/gi) || []).length, 1, 'genau ein Inline-Skript')
})

// ── 7. Fragment wird entfernt, DANN weitergeleitet ───────────────────────
test('Fragment wird entfernt (replaceState), bevor weitergeleitet wird', () => {
  const iReplace = skript.indexOf('window.history.replaceState(')
  const iPruefen = skript.indexOf('var ergebnis = pruefe(')
  const iWeiter = skript.indexOf('window.location.replace(ZIEL)')
  assert.ok(iReplace >= 0, 'replaceState fehlt')
  assert.ok(iPruefen > iReplace, 'Fragment muss VOR dem Auswerten entfernt werden')
  assert.ok(iWeiter > iReplace, 'Weiterleitung erst nach dem Entfernen')
  // Solange replaceState nicht sicher geklappt hat, wird nicht weitergeleitet.
  assert.match(skript, /if \(!entfernt\)[\s\S]{0,300}return;/,
    'ohne entferntes Fragment darf nicht weitergeleitet werden')
  assert.doesNotMatch(skript, /history\.pushState/, 'pushState wuerde den Token im Verlauf behalten')
})

// ── 8. Browser-Ablauf in einer Attrappe ─────────────────────────────────
function browser(roh) {
  const ereignisse = []
  const speicher = new Map()
  const elemente = []
  const wurzel = {
    className: '',
    firstChild: null,
    removeChild() {},
    appendChild(el) { elemente.push(el); this.firstChild = el },
  }
  const doc = {
    title: 'Anmeldung',
    getElementById: (id) => (id === 'inhalt' ? wurzel : null),
    createElement: (tag) => ({ tag, textContent: '', href: '' }),
  }
  const location = {
    hash: '#' + roh,
    pathname: '/diakronos-sso.html',
    search: '',
    replace(ziel) { ereignisse.push(['replace', ziel]) },
  }
  const win = {
    document: doc,
    location,
    history: {
      replaceState(_s, _t, url) { ereignisse.push(['replaceState', url]); location.hash = '' },
      pushState() { throw new Error('pushState ist verboten') },
    },
    localStorage: {
      getItem: (k) => (speicher.has(k) ? speicher.get(k) : null),
      setItem: (k, v) => { speicher.set(k, String(v)) },
      removeItem: (k) => { speicher.delete(k) },
    },
    atob: (s) => Buffer.from(s, 'base64').toString('latin1'),
  }
  win.window = win
  const ctx = vm.createContext({ window: win, document: doc, location, history: win.history, localStorage: win.localStorage, atob: win.atob, Date, JSON, Object, Array, String, Number, RegExp, console: kontext.console, decodeURIComponent, encodeURIComponent })
  return { ereignisse, speicher, elemente, ctx, win }
}

test('Browser-Ablauf: Speicher wird geschrieben, Fragment weg, dann /admin/', () => {
  const token = gueltigJetzt()
  const b = browser(fragment(token, gueltigerRecord))
  vm.runInContext(skript, b.ctx)

  const gespeichert = JSON.parse(b.speicher.get('pocketbase_auth'))
  assert.equal(gespeichert.token, token, 'genau der uebergebene Token wird gespeichert')
  assert.equal(gespeichert.record.id, gueltigerRecord.id)
  assert.equal(gespeichert.record.collectionName, 'users')

  assert.deepEqual(b.ereignisse.map((e) => e[0]), ['replaceState', 'replace'],
    'erst Fragment entfernen, dann weiterleiten')
  assert.equal(b.ereignisse[0][1], '/diakronos-sso.html', 'Query bleibt, Fragment faellt weg')
  assert.equal(b.ereignisse[1][1], '/admin/')
})

test('Browser-Ablauf: kaputtes Fragment schreibt nichts in den Speicher', () => {
  const b = browser('token=quatsch')
  vm.runInContext(skript, b.ctx)
  assert.equal(b.speicher.size, 0, 'bei Fehler darf keine Anmeldung entstehen')
  assert.equal(b.ereignisse.filter((e) => e[0] === 'replace').length, 0, 'keine Weiterleitung bei Fehler')
  assert.ok(b.elemente.some((el) => el.tag === 'a' && el.href === '/admin/'),
    'Fehlerseite bietet einen Link zurueck zur Anmeldung')
  assert.ok(b.elemente.some((el) => el.tag === 'h1' && el.textContent.length > 0),
    'Fehlerseite hat eine Ueberschrift')
})

test('Browser-Ablauf: gesperrter Speicher fuehrt zu Meldung, nicht zu Weiterleitung', () => {
  const b = browser(fragment(gueltig(), gueltigerRecord))
  b.win.localStorage.setItem = () => { throw new Error('QuotaExceededError') }
  vm.runInContext(skript, b.ctx)
  assert.equal(b.ereignisse.filter((e) => e[0] === 'replace').length, 0)
  assert.ok(b.win.document.getElementById('inhalt').className === 'fehler')
})
