import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = () => fs.readFileSync(new URL('../src/diakonos/pages/KalenderImport.vue', import.meta.url), 'utf8')
function setup({ status = {}, fail = '', search = '', staende = [], staendeFehler = false } = {}) {
  const calls = [], handlers = {}, mounted = [], unmounted = [], history = [], timers = []
  const context = { ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }), onMounted: fn => mounted.push(fn), onBeforeUnmount: fn => unmounted.push(fn), navigate: () => {}, URL, URLSearchParams,
    // DEP-2: setTimeout/clearTimeout werden festgehalten und NICHT ausgefuehrt —
    // sonst haelt der 2-s-Abfragetakt des Imports den Test-Runner offen.
    setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length }, clearTimeout: () => {}, btoa, Uint8Array,
    // WEB-5b: die Seite baut Adressen ueber mitBasis() (Betriebs-Praefix). Der
    // Kontext kennt kein Boot-Objekt -> kein Praefix, also die alte Adresse
    // (das Verhalten von mitBasis pruefen die web5b-Tests).
    mitBasis: (pfad) => '/' + String(pfad || '').replace(/^\/+/, ''),
    window: { __DIakonosBOOT: { is_admin: true, csrf_token: 'csrf-test' }, location: { origin: 'https://example.org', href: `https://example.org/diakonos${search}#/kalender/import`, search, assign: () => {} }, history: { replaceState: (...args) => history.push(args) } },
    __api: async (method, args) => { calls.push({ method, args }); if (fail && method.endsWith(fail)) throw Error('SECRET sensitive server error'); if (method.endsWith('get_credentials_status')) return status; if (method.endsWith('get_google_calendars')) return [{ id: 'one', summary: 'Gemeinde', backgroundColor: '#ff0000' }]; if (method.includes('get_list')) assert.fail('Desk get_list RPC does not exist in standalone'); if (method.endsWith('get_writable_calendars')) return [{ name: 'Bestand', calendar_name: 'Bestand' }]; if (method.endsWith('get_import_progress')) { if (staendeFehler) throw Error('SECRET progress error'); return { state: staende.length ? staende.shift() : null } } if (method.endsWith('start_import')) return { queued: true }; if (method.endsWith('upload_ical')) return { imported: 1, skipped: 0, kalender: 'Neu' }; return { success: true } }
  }
  const script = source().match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.createContext(context)
  vm.runInContext(script + '\nthis.state = { tab, step, error, busy, clientSecret, clientId, redirectUri, calendars, result, progress, importing, icalMode, icalName, icalTarget, icalFile, saveCredentials, startGoogleImport, importIcal, loadStatus };this.pollRunde = pollRunde;', context)
  // Zwei Microtask-Runden nach jeder Antwort: dann sind auch die
  // .then/.finally-Ketten im Quelltext fertig (kein Timer, kein Warten).
  context.apiCall = async (...args) => {
    const r = await context.__api(...args)
    await new Promise(x => setImmediate(x))
    await new Promise(x => setImmediate(x))
    return r
  }
  return { ...context.state, calls, handlers, mounted, unmounted, history, timers,
    // DEP-2: Fortschritt kommt per Abfrage statt Socket.IO. Hier direkt die
    // Abfrage aufrufen, damit der Test nicht auf den 2-s-Takt warten muss.
    // Eine volle Runde: die Runde ausführen und auf ihr Ende warten (der
    // nächste Takt wird nur als Timer gesetzt, nicht ausgeführt).
    poll: async () => {
      context.pollRunde()
      await new Promise(r => setImmediate(r))
      await new Promise(r => setImmediate(r))
    } }
}

test('SPA route and sidebar use the new page, guest route remains restricted', () => {
  const router = fs.readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
  const sidebar = fs.readFileSync(new URL('../src/diakonos/components/kronos/KronosSidebar.vue', import.meta.url), 'utf8')
  assert.match(router, /'#\/kalender\/import':\s*'KalenderImport'/)
  assert.match(sidebar, /href="#\/kalender\/import"/)
  assert.doesNotMatch(router.match(/GAST_ALLOWED_PAGES[^\n]+/)[0], /KalenderImport/)
})
test('callback is cleaned without echoing untrusted errors; status selects step', async () => {
  const s = setup({ status: { configured: true }, search: '?keep=yes&gcal_step=2&gcal_error=SECRET' })
  await s.mounted[0]()
  assert.equal(s.step.value, 2)
  assert.ok(s.history[0][2].includes('keep=yes'))
  assert.ok(!s.history[0][2].includes('gcal_'))
  assert.ok(!s.error.value.includes('SECRET'))
})
test('credentials are never loaded back and secret is cleared after failed save', async () => {
  const s = setup({ fail: 'save_credentials' })
  s.clientId.value = 'client'; s.clientSecret.value = 'SECRET'; s.redirectUri.value = 'https://example.org/google-calendar-callback'
  await s.saveCredentials()
  assert.equal(s.clientSecret.value, '')
  assert.equal(s.busy.value, false)
  assert.ok(!s.error.value.includes('SECRET'))
})
test('Google mapping queues only selected calendars and done releases controls', async () => {
  const s = setup({ status: { configured: true, authorized: true }, staende: [{ status: 'done', total_imported: 3, total_skipped: 1, calendars: [] }] })
  await s.mounted[0]()
  assert.equal(s.step.value, 3)
  assert.equal(s.error.value, '')
  assert.ok(s.calls.some(c => c.method === 'diakronos.kronos.api.permissions.get_writable_calendars'))
  await s.startGoogleImport()
  const call = s.calls.find(c => c.method.endsWith('start_import'))
  assert.equal(JSON.parse(call.args.mappings_json)[0].create_new, true)
  assert.equal(s.importing.value, true)
  await s.poll()
  assert.equal(s.importing.value, false)
  assert.equal(s.result.value.total_imported, 3)
  s.unmounted[0]()
})
test('Fortschritt kommt per RPC-Abfrage, nicht per Socket.IO (DEP-2)', () => {
  // Das Paket socket.io-client war die letzte Nutzung des Clients; der
  // Fortschritt laeuft jetzt ueber `get_import_progress`. Ohne diesen Waechter
  // waere ein Wiedereinbau still: der Balken liefe weiter, das Audit faende
  // das Paket aber wieder.
  const quelle = source()
  // NUR Importe zaehlen: der erklaerende Kommentar im Quelltext darf das
  // Paket nennen, ein `import ... from 'socket.io-client'` nicht.
  assert.doesNotMatch(quelle, /^\s*import\s[^\n]*from\s+['"]socket\.io-client/m,
    'KalenderImport importiert wieder socket.io-client')
  assert.doesNotMatch(quelle, /\bio\(/, 'KalenderImport baut wieder eine Socket.IO-Verbindung auf')
  assert.match(quelle, /get_import_progress/)
  const paket = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'))
  assert.ok(!('socket.io-client' in (paket.dependencies || {})), 'socket.io-client steht wieder in den Abhaengigkeiten')
})
test('Fortschrittsabfrage: Fehler verwerfen den Stand nicht und laufen weiter', async () => {
  const s = setup({ status: { configured: true, authorized: true }, staende: [{ status: 'importing', imported: 5 }], staendeFehler: false })
  await s.mounted[0]()
  await s.startGoogleImport()
  await s.poll()
  assert.equal(s.progress.value.imported, 5)
  assert.equal(s.importing.value, true, 'ein Zwischenstand beendet den Import nicht')
  s.unmounted[0]()
  // Nach dem Verlassen darf keine weitere Abfrage mehr laufen.
  const rufe = s.calls.filter(c => c.method.endsWith('get_import_progress')).length
  await s.poll()
  assert.equal(s.calls.filter(c => c.method.endsWith('get_import_progress')).length, rufe)
})
test('abgebrochener Start laesst die Knoepfe wieder frei und verbirgt Serverfehler', async () => {
  const s = setup({ status: { configured: true, authorized: true }, fail: 'start_import' })
  await s.mounted[0]()
  await s.startGoogleImport()
  assert.equal(s.importing.value, false)
  assert.ok(s.error.value)
  assert.ok(!s.error.value.includes('SECRET'))
})
test('selected mappings and partial failure', async () => {
  const s = setup({ status: { configured: true, authorized: true },
    staende: [{ status: 'done', error: 'SECRET', total_imported: 2 }] })
  await s.mounted[0]()
  s.calendars.value.push({ id: 'unselected', selected: false })
  s.calendars.value[0].target = 'Bestand'
  await s.startGoogleImport()
  const mappings = JSON.parse(s.calls.find(c => c.method.endsWith('start_import')).args.mappings_json)
  assert.equal(mappings.length, 1)
  assert.equal(mappings[0].create_new, false)
  assert.equal(mappings[0].target_kalender, 'Bestand')
  await s.poll()
  assert.equal(s.importing.value, false)
  assert.ok(!s.error.value.includes('SECRET'))
})
test('iCal sends exact UTF-8 bytes and rejects missing target before request', async () => {
  const s = setup()
  s.icalMode.value = 'existing'
  await s.importIcal()
  assert.equal(s.calls.length, 0)
  s.icalMode.value = 'new'; s.icalName.value = 'Neu'
  const bytes = new TextEncoder().encode('BEGIN:VCALENDAR\r\nSUMMARY:Grüße\r\nEND:VCALENDAR')
  s.icalFile.value = { name: 'test.ics', size: bytes.length, arrayBuffer: async () => bytes.buffer }
  await s.importIcal()
  const call = s.calls.find(c => c.method.endsWith('upload_ical'))
  assert.equal(Buffer.from(call.args.file_content_b64, 'base64').toString(), new TextDecoder().decode(bytes))
  assert.equal(s.busy.value, false)
})
