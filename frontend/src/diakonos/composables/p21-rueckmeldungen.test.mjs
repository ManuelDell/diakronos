import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { showToast } from './useToast.js'

class Element {
  children = []; attrs = {}; listeners = {}; style = {}; classList = { add() {}, remove() {} }
  setAttribute(k, v) { this.attrs[k] = v }
  appendChild(el) { this.children.push(el); el.parentNode = this }
  addEventListener(k, fn) { this.listeners[k] = fn }
  remove() { this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1) }
}

// MT-3 (Manuel 11.11.): Fehler bleiben schließbar und werden vorgelesen —
// die Anzeigedauer ist aber nicht mehr 0 („bis zum Schließen“): JEDE Meldung
// blendet nach `ANZEIGE_MS` (10 s) aus. Die alte Erwartung „Fehler darf nicht
// automatisch verschwinden“ wird durch die Kartenentscheidung ersetzt.
test('OP-UI-10: Fehler sind schließbar, werden vorgelesen und blenden nach 10 s aus (MT-3)', () => {
  const container = new Element()
  globalThis.document = { querySelector: () => container, createElement: () => new Element() }
  globalThis.requestAnimationFrame = fn => fn()
  const timer = []
  const alt = globalThis.setTimeout
  globalThis.setTimeout = (fn, ms) => { timer.push(ms); return 1 }
  try {
    showToast('Speichern fehlgeschlagen', 'error')
    const toast = container.children[0]
    assert.equal(toast.attrs.role, 'alert')
    // Review-Nacharbeit (A11y): Der Name nennt zusätzlich den schnellen Weg
    // (Esc) — die Fläche steht am Ende von `<body>`.
    assert.ok(toast.children.some(el => el.attrs['aria-label'] === 'Meldung schließen (Esc)'))
    assert.ok(timer.includes(10000), `Fehler blendet nach 10 s aus; gefunden: ${timer.join(', ')}`)
    timer.length = 0
    showToast('Gespeichert', 'success')
    assert.equal(container.children[1].attrs.role, 'status')
    assert.ok(timer.includes(10000), 'Erfolg: dieselbe Anzeigedauer')
  } finally { globalThis.setTimeout = alt }
})

test('OP-UI-2/23: Dialoge schließen nicht beim Fehlklick und fokussieren Inhalt statt Kreuz', async () => {
  const dialog = await readFile(new URL('../components/ui/DkDialog.vue', import.meta.url), 'utf8')
  const modal = await readFile(new URL('../components/DkModal.vue', import.meta.url), 'utf8')
  assert.match(dialog, /closeOnOverlay:.*default: false/)
  assert.doesNotMatch(modal, /@click\.self="close"/)
  assert.match(dialog, /useDialogFokus/)
})

test('OP-UI-3/UXD-R22: Wiki behandelt Schreibfehler und leeren Titel sichtbar', async () => {
  const wiki = await readFile(new URL('../pages/Wiki.vue', import.meta.url), 'utf8')
  assert.match(wiki, /maxlength="140"/)
  assert.match(wiki, /Bitte gib einen Titel ein/)
  assert.ok((wiki.match(/catch \(e\)/g) || []).length >= 2)
})
