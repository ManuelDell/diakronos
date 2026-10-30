/**
 * DEV-7b — Nacharbeit Moderation-Freigabe (Karte t_ede5c173).
 *
 * Zwei Befunde des Opus-Reviews, als Quelltext-Waechter festgehalten:
 *
 *   1) MITTEL Layout: Die Basisregel `.dk-mod-footer { display:flex;
 *      justify-content:flex-end; … }` war beim Umbau der Knopfleiste
 *      geloescht worden (Commit 6033c69) — nur der @media(max-width:480px)-
 *      Block blieb. Auf dem Desktop brach „Ablehnen…“ dadurch in eine eigene
 *      Zeile. Sie muss wieder da sein, UND der Mobil-Block muss bleiben.
 *
 *   2) Konflikt-Dialog: „Freigeben“ gibt einen Termin MIT Ueberschneidung
 *      bewusst frei (Operator-Entscheidung). Dann muss der Konflikt als
 *      bewusst uebergangen gelten — der Dialog schickt `ueberschneidung: 1`,
 *      der Server setzt zusaetzlich `ignore_conflict=1`. Neben dem Knopf
 *      steht der Hinweis, was die Aktion bedeutet.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const MODALS = lies('components/kronos/ModerationModals.vue')
const KANBAN_API = lies('api/kanbanApi.js')

/** Der Konflikt-Dialog als eigener Abschnitt (zwischen seinen Kommentarmarken). */
function konfliktDialog() {
  const anfang = MODALS.indexOf('<!-- Conflict Modal -->')
  assert.ok(anfang > 0, 'Konflikt-Dialog nicht gefunden')
  return MODALS.slice(anfang, MODALS.indexOf('<!-- Series Modal -->'))
}

/** Der <style>-Block der Komponente. */
function stilBlock() {
  const i = MODALS.lastIndexOf('<style scoped>')
  assert.ok(i > 0, '<style scoped> fehlt')
  return MODALS.slice(i)
}

// ── 1) Fussleiste: Basisregel wiederhergestellt, Mobil-Block erhalten ───────

test('DEV-7b: Basisregel .dk-mod-footer ist wieder da (Desktop-Zeile)', () => {
  const stil = stilBlock()
  // Die Regel muss ausserhalb des @media-Blocks stehen — erkannt daran, dass
  // sie VOR dem @media(max-width:480px)-Block notiert ist.
  const mobile = stil.indexOf('@media (max-width: 480px)')
  assert.ok(mobile > 0, 'Mobil-Block fehlt')
  const basis = stil.slice(0, mobile)
  assert.match(
    basis,
    /\.dk-mod-footer\s*\{[^}]*display:\s*flex;/,
    '`.dk-mod-footer` braucht wieder `display: flex`',
  )
  assert.match(
    basis,
    /\.dk-mod-footer\s*\{[^}]*justify-content:\s*flex-end;/,
    '`.dk-mod-footer` braucht wieder `justify-content: flex-end`',
  )
  assert.match(
    basis,
    /\.dk-mod-footer\s*\{[^}]*padding-top:\s*var\(--sp-2\);/,
    '`.dk-mod-footer` braucht wieder `padding-top: var(--sp-2)`',
  )
})

test('DEV-7b: Mobil-Block der Fussleiste bleibt erhalten', () => {
  const stil = stilBlock()
  assert.match(stil, /@media \(max-width: 480px\) \{\s*\.dk-mod-footer \{ flex-wrap: wrap;/)
  assert.match(stil, /\.dk-mod-footer > \* \{ flex: 0 0 auto; \}/)
})

test('DEV-7b: alle drei Dialoge nutzen die Fussleistenklasse', () => {
  // Z. 43/93/135 des Befunds: Bearbeiten, Ablehnen, Abgelehnter Termin.
  const treffer = MODALS.match(/class="dk-mod-footer"/g) || []
  assert.ok(treffer.length >= 3, `nur ${treffer.length} Fussleisten gefunden`)
})

// ── 2) Konflikt-Freigabe: bewusst uebergangen ──────────────────────────────

test('DEV-7b: Konflikt-Dialog schickt beim Freigeben ueberschneidung=1', () => {
  const rumpf = MODALS.slice(MODALS.indexOf('async function resolveAction'))
  const ende = rumpf.indexOf('// ── Series Modal')
  const code = rumpf.slice(0, ende)
  assert.match(code, /if \(action === 'festlegen'\) werte\.ueberschneidung = 1/)
  assert.match(code, /resolveConflict\(conflictEvent\.value\.id, action, werte\)/)
})

test('DEV-7b: Vorschlagsdialog setzt KEIN ueberschneidung', () => {
  // Dort gibt es keine Ueberschneidung zu uebergehen — der Vermerk bleibt
  // unberuehrt (sonst wuerde jede Freigabe Konflikte stillschweigend abhaken).
  const freigeben = MODALS.slice(MODALS.indexOf('async function submitFreigeben'))
  const rumpf = freigeben.slice(0, freigeben.indexOf('// ── OP-EVENT-12'))
  assert.doesNotMatch(rumpf, /ueberschneidung/)
})

test('DEV-7b: Hinweis neben dem Freigeben-Knopf im Konflikt-Dialog', () => {
  const dialog = konfliktDialog()
  assert.match(dialog, /data-testid="dk-mod-freigeben-konflikt"/)
  assert.match(dialog, /Gibt den Termin trotz Überschneidung frei/)
  assert.match(dialog, /dk-mod-konflikt-hinweis/)
})

test('DEV-7b: API-Schicht dokumentiert ueberschneidung', () => {
  assert.match(KANBAN_API, /ueberschneidung: 1/)
  assert.match(KANBAN_API, /ignore_conflict=1/)
})

// ── 3) Regression: DEV-7-Freigabeweg bleibt unberuehrt ─────────────────────

test('DEV-7b: „Freigeben“ im Vorschlagsdialog bleibt festlegen', () => {
  assert.match(
    MODALS,
    /resolveConflict\(editEvent\.value\.id, 'festlegen', getEditFormData\(editForm\.value\)\)/,
  )
})
