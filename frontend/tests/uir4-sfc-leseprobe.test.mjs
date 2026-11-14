/**
 * UI-R4 — SFC-Leseprobe: alle berührten Einzeldatei-Komponenten werden mit
 * dem ECHTEN Vue-Compiler übersetzt (Script + Template). Fängt
 * Template-Fehler (falscher Attributname, unbekannter Ausdruck, fehlender
 * Import), die ein reiner Texttest nicht sieht — und ist damit ein Ersatz für
 * den vollen `vite build`, wenn dessen esbuild-Binary im Container nicht läuft.
 *
 * Der Test braucht nur `vue/compiler-sfc` aus node_modules und kein Netz.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const SRC = join(resolve(hier, '..'), 'src', 'diakonos')

const DATEIEN = [
  'components/kronos/ModerationCard.vue',
  'components/kronos/ModerationBoard.vue',
  'components/kronos/ModerationAenderungen.vue',
  'components/kronos/ModerationAntraege.vue',
  'components/kronos/KalenderPruefPanel.vue',
  'pages/Moderation.vue',
]

for (const rel of DATEIEN) {
  test(`UI-R4: ${rel} übersetzt mit dem Vue-Compiler`, () => {
    const quelle = readFileSync(join(SRC, rel), 'utf8')
    const { descriptor, errors } = parse(quelle, { filename: rel })
    assert.deepEqual(errors.map(e => e.message), [], `${rel}: SFC nicht lesbar`)

    // Skript (mit allen Imports und defineProps/defineEmits)
    const skript = compileScript(descriptor, { id: rel })
    assert.ok(skript.content.length > 0, `${rel}: kein Skript`)
    assert.match(skript.content, /export default/, `${rel}: kein Komponenten-Export`)

    // Template — Fehler hier waren der eigentliche Anlass (Tippfehler in
    // Attributnamen übersieht ein Textvergleich).
    const tpl = compileTemplate({
      source: descriptor.template.content,
      filename: rel,
      id: rel,
      compilerOptions: { bindingMetadata: skript.bindings },
    })
    assert.deepEqual(tpl.errors.map(e => (e.message || String(e))), [],
      `${rel}: Template-Fehler`)
  })
}

test('UI-R4: die Karte kennt die Eigenschaften, die die Tafel ihr gibt', () => {
  const karte = readFileSync(join(SRC, 'components/kronos/ModerationCard.vue'), 'utf8')
  for (const prop of ['item', 'column', 'notification', 'busy', 'verweigerung']) {
    assert.match(karte, new RegExp(`${prop}:\\s*\\{`), `Prop „${prop}“ fehlt`)
  }
  for (const ereignis of ['click', 'remove', 'resolve-conflict', 'freigeben']) {
    assert.match(karte, new RegExp(`'${ereignis}'`), `Ereignis „${ereignis}“ fehlt`)
  }
})

test('UI-R4: die Tafel reicht Freigabe, busy und Verweigerung an die Karte durch', () => {
  const tafel = readFileSync(join(SRC, 'components/kronos/ModerationBoard.vue'), 'utf8')
  assert.match(tafel, /@freigeben="onFreigeben"/, 'Freigabe-Ereignis nicht verdrahtet')
  assert.match(tafel, /:busy=/, 'busy nicht durchgereicht')
  assert.match(tafel, /:verweigerung="verweigerungFuer\(item\)"/, 'Verweigerung nicht durchgereicht')
  assert.match(tafel, /resolveConflict\(id, 'festlegen'\)/, 'Freigabe nutzt den bestehenden Weg')
  // `resolve_conflict` liefert KEIN `wartet_weiter` — `new_status` wird
  // deshalb in `freigabeStufen.mjs` (`wartetWeiter`) ausgewertet.
  const regeln = readFileSync(join(SRC, 'components/kronos/freigabeStufen.mjs'), 'utf8')
  assert.match(regeln, /new_status/, 'new_status des Servers wird ausgewertet')
})

test('UI-R4: die Zahl „Zu prüfen“ kommt EINMAL vom Server (R-12), nicht aus der Tafel', () => {
  const tafel = readFileSync(join(SRC, 'components/kronos/ModerationBoard.vue'), 'utf8')
  // Kein zweites `zahl`-Ereignis mehr: der Server zählt die offene Stufe.
  assert.doesNotMatch(tafel, /emit\('bereit'/, 'die Tafel meldet keine eigene Zahl mehr')
  const seite = readFileSync(join(SRC, 'pages/Moderation.vue'), 'utf8')
  assert.match(seite, /getModerationCount/, 'Seite holt die Zahl vom Server')
  assert.match(seite, /prüfZahl/, 'Seite nutzt die Zahl für den Reiter')
  assert.doesNotMatch(seite, /@bereit="boardBereit"/, 'keine zweite Zählung über die Tafel')
})
