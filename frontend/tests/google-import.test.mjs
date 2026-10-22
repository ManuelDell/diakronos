import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = () => fs.readFileSync(new URL('../src/diakonos/pages/KalenderImport.vue', import.meta.url), 'utf8')
function setup({ status = {}, fail = '', search = '', socketReady = true } = {}) {
  const calls = [], handlers = {}, mounted = [], unmounted = [], history = []
  let ioOptions = null
  const socket = { connected: socketReady === true, on: (event, fn) => { handlers[event] = fn }, once: (event, fn) => { handlers[event] = fn }, connect: () => { if (socketReady === 'error') handlers.connect_error(); else { socket.connected = true; handlers.connect() } }, off: (event) => { delete handlers[event] }, disconnect: () => { socket.connected = false } }
  const context = { ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }), onMounted: fn => mounted.push(fn), onBeforeUnmount: fn => unmounted.push(fn), io: options => { assert.equal(options.extraHeaders?.['X-Frappe-CSRF-Token'], 'csrf-test'); ioOptions = options; return socket }, navigate: () => {}, URL, URLSearchParams, setTimeout, clearTimeout, btoa, Uint8Array,
    window: { __DIakonosBOOT: { is_admin: true, csrf_token: 'csrf-test' }, location: { origin: 'https://example.org', href: `https://example.org/diakonos${search}#/kalender/import`, search, assign: () => {} }, history: { replaceState: (...args) => history.push(args) } },
    apiCall: async (method, args) => { calls.push({ method, args }); if (fail && method.endsWith(fail)) throw Error('SECRET sensitive server error'); if (method.endsWith('get_credentials_status')) return status; if (method.endsWith('get_google_calendars')) return [{ id: 'one', summary: 'Gemeinde', backgroundColor: '#ff0000' }]; if (method.includes('get_list')) assert.fail('Desk get_list RPC does not exist in standalone'); if (method.endsWith('get_writable_calendars')) return [{ name: 'Bestand', calendar_name: 'Bestand' }]; if (method.endsWith('start_import')) return { queued: true }; if (method.endsWith('upload_ical')) return { imported: 1, skipped: 0, kalender: 'Neu' }; return { success: true } }
  }
  const script = source().match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.createContext(context)
  vm.runInContext(script + '\nthis.state = { tab, step, error, busy, clientSecret, clientId, redirectUri, calendars, result, progress, importing, icalMode, icalName, icalTarget, icalFile, saveCredentials, startGoogleImport, importIcal, loadStatus };', context)
  return { ...context.state, calls, handlers, mounted, unmounted, history, socket, ioOptions: () => ioOptions }
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
  const s = setup({ status: { configured: true, authorized: true } })
  await s.mounted[0]()
  assert.equal(s.step.value, 3)
  assert.equal(s.error.value, '')
  assert.ok(s.calls.some(c => c.method === 'diakronos.kronos.api.permissions.get_writable_calendars'))
  await s.startGoogleImport()
  const call = s.calls.find(c => c.method.endsWith('start_import'))
  assert.equal(JSON.parse(call.args.mappings_json)[0].create_new, true)
  assert.equal(s.importing.value, true)
  s.handlers.gcal_import_progress({ status: 'done', total_imported: 3, total_skipped: 1, calendars: [] })
  assert.equal(s.importing.value, false)
  assert.equal(s.result.value.total_imported, 3)
  s.unmounted[0]()
  assert.equal(s.socket.connected, false)
})
test('progress socket uses websocket-only transport for multiple workers', async () => {
  // Befund W2: mit mehreren Uvicorn-Arbeitern ohne Sticky Sessions zerfallen
  // Engine.IO-Polling-Anfragen einer sid auf verschiedene Arbeiter. Der Client
  // verbindet deshalb ausschliesslich per WebSocket (bleibt bei einem Arbeiter).
  const s = setup({ status: { configured: true, authorized: true } })
  await s.mounted[0]()
  await s.startGoogleImport()
  const options = s.ioOptions()
  assert.ok(options, 'io() wurde aufgerufen')
  // Cross-vm-Array: per join vergleichen, nicht per deepEqual (Prototyp-Insel).
  assert.equal(options.transports.join(','), 'websocket')
  // Import laeuft noch: Timer/Verbindung sauber beenden, sonst haelt der
  // Test-Runner den Prozess offen (offener Deadline-Timer).
  s.unmounted[0]()
})
test('socket failure prevents queuing and never exposes server errors', async () => {
  const s = setup({ status: { configured: true, authorized: true }, socketReady: 'error' })
  await s.mounted[0]()
  await s.startGoogleImport()
  assert.ok(!s.calls.some(c => c.method.endsWith('start_import')))
  assert.equal(s.importing.value, false)
  assert.ok(s.error.value)
})
test('connection completes before queueing; selected mappings and partial failure', async () => {
  const s = setup({ status: { configured: true, authorized: true }, socketReady: false })
  await s.mounted[0]()
  s.calendars.value.push({ id: 'unselected', selected: false })
  s.calendars.value[0].target = 'Bestand'
  await s.startGoogleImport()
  assert.equal(s.socket.connected, true)
  const mappings = JSON.parse(s.calls.find(c => c.method.endsWith('start_import')).args.mappings_json)
  assert.equal(mappings.length, 1)
  assert.equal(mappings[0].create_new, false)
  assert.equal(mappings[0].target_kalender, 'Bestand')
  s.handlers.gcal_import_progress({ status: 'done', error: 'SECRET', total_imported: 2 })
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
