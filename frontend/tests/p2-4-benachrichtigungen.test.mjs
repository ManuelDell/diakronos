/**
 * OP-HANDY-6 — Benachrichtigungen: Zaehler, Liste, erst-dann-gelesen.
 *
 * Nachtpruefung: die Glocke zeigte nie ein Abzeichen, weil
 * `useNotifications` `res.count` las, die API aber `unread_count` liefert;
 * ein Klick setzte ungesehen alles auf gelesen. Dieser Test laeuft gegen die
 * echten Quelldateien (kein Mock der Logik):
 *
 *   1. `fetchUnread` liest `unread_count` (nicht `count`).
 *   2. Der Klick auf die Glocke oeffnet ZUERST die Liste (get_my_notifications),
 *      erst danach wird markiert.
 *   3. `mark_notifications_read` wird nicht mehr beim reinen Anzeigen gerufen.
 *
 * Die Composable wird als data:-URL geladen, damit die Vue-Importe nicht
 * aufloesen muessen (Muster aus planrahmen-composable.test.mjs).
 */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const WURZEL = new URL('../src/diakonos/', import.meta.url)

// ── 1. Composable: unread_count statt count ────────────────────────────────

const aufrufe = []
globalThis.__notifyGet = async (name, args) => {
  aufrufe.push({ art: 'get', name, args })
  if (name.endsWith('get_unread_notifications')) return { success: true, unread_count: 3 }
  if (name.endsWith('get_my_notifications')) {
    return { success: true, data: [{ name: 'N-1', subject: 'Plan geändert', read: 0 }] }
  }
  return {}
}
globalThis.__notifyCall = async (name, args) => {
  aufrufe.push({ art: 'call', name, args })
  return { success: true }
}

let quelle = await readFile(new URL('composables/useNotifications.js', WURZEL), 'utf8')
const vueStub = 'const ref = v => ({value: v}); const onMounted = () => {}; const onUnmounted = () => {}'
quelle = quelle.replace("import { ref, onMounted, onUnmounted } from 'vue'", vueStub)
quelle = quelle.replace("import { apiGet, apiCall } from './useApi.js'",
                        'const apiGet = globalThis.__notifyGet; const apiCall = globalThis.__notifyCall')
const mod = await import('data:text/javascript;base64,' + Buffer.from(quelle).toString('base64'))

const n = mod.useNotifications()
await n.fetchUnread()
// Vertrag der API ist `unread_count`; vorher stand hier `count` -> immer 0.
assert.equal(n.unreadCount.value, 3, 'Zaehler liest nicht unread_count')

// Liste laden darf NICHT als gelesen markieren.
await n.ladeListe()
assert.equal(n.notifications.value.length, 1)
assert.ok(!aufrufe.some(a => a.art === 'call' && a.name.endsWith('mark_notifications_read')),
  'Laden der Liste hat ungesehen als gelesen markiert')
assert.equal(n.unreadCount.value, 3, 'Laden der Liste hat den Zaehler vorschnell geleert')

// Erst der ausdrueckliche Aufruf markiert.
await n.markAsRead()
assert.ok(aufrufe.some(a => a.art === 'call' && a.name.endsWith('mark_notifications_read')),
  'markAsRead ruft den Endpunkt nicht')
assert.deepEqual(aufrufe.find(a => a.art === 'call').args, { names: ['N-1'] },
  'Nur die angezeigte Nachricht darf gelesen werden')
assert.equal(n.unreadCount.value, 3, 'Zaehler muss erneut vom Server kommen (ungesehene Eintraege bleiben)')
assert.equal(n.notifications.value[0].read, 1)

// ── 2. Topbar: Klick oeffnet die Liste, markiert erst danach ───────────────

const topbar = await readFile(new URL('components/AppTopbar.vue', WURZEL), 'utf8')
assert.match(topbar, /@click="toggleListe"/, 'Glocke oeffnet die Liste nicht (toggleListe fehlt)')
assert.match(topbar, /ladeListe\(\)/, 'Topbar laedt die Liste nicht')
assert.match(topbar, /await ladeListe\(\)[\s\S]*?await nextTick\(\)[\s\S]*?await markAsRead\(eintraege\)/,
  'Topbar markiert nicht erst NACH dem Laden als gelesen')
assert.doesNotMatch(topbar, /@click="markAsRead"/,
  'Glocke markiert weiterhin direkt als gelesen (ohne Liste)')
assert.match(topbar, /dk-notify-panel/, 'Keine Benachrichtigungs-Liste im Markup')

// ── 3. „geändert am“-Marker in Plan und Meine Dienste ─────────────────────

const plan = await readFile(new URL('pages/planrahmen/Plan.vue', WURZEL), 'utf8')
assert.match(plan, /geaendertText/, 'Plan zeigt keinen „geändert am“-Marker')

const md = await readFile(new URL('pages/planrahmen/MeineDienste.vue', WURZEL), 'utf8')
assert.match(md, /plan_geaendert/, 'Meine Dienste nutzt den Aenderungszeitpunkt nicht')
assert.match(md, /Stand:/, 'Meine Dienste zeigt keinen Stand-Hinweis')

const css = await readFile(new URL('index.css', WURZEL), 'utf8')
assert.match(css, /@media[^}]+\.dk-notify-panel\s*\{[^}]*position:\s*fixed[^}]*right:\s*12px/s,
  'Mobile Liste muss am Viewport statt an der eingerueckten Glocke ausgerichtet sein')

console.log('OP-HANDY-6 Frontend: OK')
