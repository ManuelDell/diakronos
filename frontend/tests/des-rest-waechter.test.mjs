/**
 * DES-REST · WÄCHTER — Filterchips und Inline-Stile (DES-01, DES-02).
 *
 * DES-01: Filterknöpfe dürfen nur noch über `components/ui/DkFilterChips.vue`
 * und `composables/filterChips.mjs` entstehen. Rohe `<button class="dk-filter-chip">`
 * in Seiten waren der Befund (28 Zeilen in 12 Seiten, zwei Aussehen).
 *
 * DES-02: `style="…"`-Attribute in `.vue`-Dateien sind reiner Code-Stil ohne
 * sichtbare Folge — aber sie umgehen Tokens und Dunkelmodus. Der Zählerstand
 * wird deshalb FESTGEHALTEN (Ratsche): er darf sinken, nie steigen. Neue
 * Stellen fallen so sofort auf, ohne dass ein Schlag alle 120 Altstellen
 * gleichzeitig umgebaut werden müssen.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'

const WURZEL = new URL('../src/', import.meta.url)

function alleVue(verzeichnis) {
  const pfad = new URL(verzeichnis, WURZEL)
  if (!existsSync(pfad)) return []
  const ergebnis = []
  for (const name of readdirSync(pfad)) {
    if (name === 'node_modules') continue
    const kind = new URL(name, pfad)
    if (statSync(kind).isDirectory()) ergebnis.push(...alleVue(verzeichnis + name + '/'))
    else if (name.endsWith('.vue')) ergebnis.push(verzeichnis + name)
  }
  return ergebnis
}

const dateien = alleVue('')

/** DES-01: Stellen, an denen Filterknöpfe noch von Hand gebaut werden. */
test('DES-01 · keine handgebauten Filterchips mehr in Seiten', () => {
  const treffer = []
  for (const datei of dateien) {
    if (datei.endsWith('components/ui/DkFilterChips.vue')) continue
    const text = readFileSync(new URL(datei, WURZEL), 'utf8')
    text.split('\n').forEach((zeile, i) => {
      // Nur Template-Zeilen mit Attribut zählen; Kommentare und CSS bleiben aussen vor.
      if (!/class="[^"]*dk-filter-chip/.test(zeile)) return
      if (/^\s*[/*]/.test(zeile) || /\.dk-filter-chip/.test(zeile)) return
      treffer.push(`${datei}:${i + 1}  →  ${zeile.trim()}`)
    })
  }
  assert.deepEqual(
    treffer, [],
    'Filterchips nur noch über DkFilterChips bauen (DES-01):\n' + treffer.join('\n'),
  )
})

/**
 * DES-02: Ratsche über die Zahl der `style="…"`-Attribute.
 * Die Werte sind der Stand nach diesem Paket; sie dürfen nur kleiner werden.
 */
const INLINE_STIL_DECKEL = {
  'diakonos/pages/Gruppen.vue': 0,
  'diakonos/pages/Ressourcen.vue': 0,
  'diakonos/pages/Lieder.vue': 0,
  'diakonos/pages/Liedgruppen.vue': 0,
  'diakonos/pages/Home.vue': 0,
  'diakonos/pages/Adressbuch.vue': 0,
  'diakonos/components/kronos/ModerationModals.vue': 0,
  'diakonos/components/DkWarning.vue': 0,
}
const INLINE_STIL_GESAMT_DECKEL = 47

test('DES-02 · umgestellte Seiten tragen keine style-Attribute mehr', () => {
  const verstoesse = []
  for (const [datei, deckel] of Object.entries(INLINE_STIL_DECKEL)) {
    const pfad = new URL(datei, WURZEL)
    if (!existsSync(pfad)) continue
    const text = readFileSync(pfad, 'utf8')
    const zahl = (text.match(/\sstyle="/g) || []).length
    if (zahl > deckel) verstoesse.push(`${datei}: ${zahl} style-Attribute (erlaubt ${deckel})`)
  }
  assert.deepEqual(verstoesse, [], 'Inline-Stile gehören in Klassen (DES-02):\n' + verstoesse.join('\n'))
})

test('DES-02 · Gesamtzahl der style-Attribute steigt nicht', () => {
  let gesamt = 0
  for (const datei of dateien) {
    const text = readFileSync(new URL(datei, WURZEL), 'utf8')
    gesamt += (text.match(/\sstyle="/g) || []).length
  }
  assert.ok(
    gesamt <= INLINE_STIL_GESAMT_DECKEL,
    `style-Attribute: ${gesamt} (Deckel ${INLINE_STIL_GESAMT_DECKEL}). ` +
    'Neue Stellen als Klasse im <style scoped>-Block anlegen (DES-02).',
  )
  console.log(`  DES-02: ${gesamt} style-Attribute in .vue-Dateien (Deckel ${INLINE_STIL_GESAMT_DECKEL})`)
})
