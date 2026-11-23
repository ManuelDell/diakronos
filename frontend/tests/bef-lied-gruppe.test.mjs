/**
 * BEF-LIED-GRUPPE — Lied-Detail: „In Liedgruppen“ zeigt den Gruppennamen.
 *
 * Befund Manuel 23.11. (DMB-df8b): Die Karte „In Liedgruppen“ auf
 * #/lieder/<lied> listete Eintraege wie `fe722a20-2  129` — also die
 * technische Kennung der Liedgruppe (gekuerzt dargestellt) und eine nackte
 * Zahl statt des Namens.
 *
 * Geprueft wird:
 *  1. Angezeigt wird der Klartext-Titel (`titel` / `gruppenname`) mit der
 *     Kennung nur als Ersatz — nicht mehr `g.liedgruppe` als Text.
 *  2. Der Eintrag verlinkt weiter auf die Gruppe (#/lieder/gruppen/<id>).
 *  3. Die Zahl traegt eine Beschriftung („Nr.“), weil sie die Nummer des
 *     Liedes INNERHALB der Gruppe ist — keine Anzahl.
 *  4. Nur Tokens, keine festen px-Werte (Waechter ux1a / waechter-tokens).
 *
 * Die SFC wird echt kompiliert (wie p1-10-lieder-material.test.mjs), damit
 * ein Vorlagenfehler auffaellt.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const wurzel = new URL('../src/', import.meta.url)
const lesen = (rel) => readFileSync(new URL(rel, wurzel), 'utf8')

function kompiliere(rel) {
  const quelle = lesen(rel)
  const { descriptor, errors } = parse(quelle, { filename: rel })
  assert.deepEqual(errors, [], rel + ': SFC-Struktur')
  const skript = compileScript(descriptor, { id: rel })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: rel,
    id: rel,
    compilerOptions: { bindingMetadata: skript.bindings || {} },
  })
  assert.deepEqual(tpl.errors.map((e) => e.message || String(e)), [], rel + ': Vue-Vorlage')
  return { quelle, template: descriptor.template.content, skriptText: descriptor.scriptSetup.content }
}

const { quelle, template, skriptText } = kompiliere('diakonos/pages/LiedDetail.vue')

// ── 1. Klartext statt Kennung ───────────────────────────────────────────────

assert.match(
  template,
  /\{\{\s*g\.titel\s*\|\|\s*g\.gruppenname\s*\|\|\s*g\.liedgruppe\s*\}\}/,
  'Gruppenname wird angezeigt (titel/gruppenname), Kennung nur als Ersatz'
)
assert.doesNotMatch(
  template,
  /<span class="ld-group-name">\{\{\s*g\.liedgruppe\s*\}\}<\/span>/,
  'kein reines `g.liedgruppe` mehr als Anzeigetext'
)

// ── 2. Verlinkung bleibt ────────────────────────────────────────────────────

assert.match(
  template,
  /:href="'#\/lieder\/gruppen\/'\s*\+\s*encodeURIComponent\(g\.liedgruppe\)"/,
  'Eintrag verlinkt auf die Liedgruppe'
)

// ── 3. Die Zahl ist beschriftet (Nr. innerhalb der Gruppe) ──────────────────

assert.match(
  template,
  /<span class="ld-group-num-label">Nr\.<\/span>/,
  'die Nummer traegt die Beschriftung „Nr.“'
)
assert.doesNotMatch(
  template,
  /<span v-if="g\.nummer" class="ld-group-num">\{\{\s*g\.nummer\s*\}\}<\/span>/,
  'keine nackte Zahl mehr ohne Beschriftung'
)

// ── 4. Datenherkunft: Feld kommt aus get_lied_detail ────────────────────────

assert.match(skriptText, /get_lied_detail/, 'Detail kommt vom Server')
assert.match(skriptText, /liedgruppen\.value\s*=\s*data\?\.liedgruppen/, 'Liedgruppen aus der Antwort')

// ── 5. Keine festen px-Werte in den neuen Regeln ────────────────────────────

const stil = quelle.slice(quelle.indexOf('<style'))
const gruppenRegeln = stil
  .split('\n')
  .filter((z) => /\.ld-group-/.test(z) && !/^\s*\/[/*]/.test(z))
  .join('\n')
assert.ok(gruppenRegeln.length > 0, 'Liedgruppen-Regeln vorhanden')
assert.doesNotMatch(gruppenRegeln, /\b\d+px\b/, 'keine festen px-Werte in den Liedgruppen-Regeln')
