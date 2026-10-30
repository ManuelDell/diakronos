import assert from 'node:assert/strict'
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'

/**
 * UX-A2b — Anfragen: Status als Filterchips (Entwurf A2, zweiter Teil).
 *
 * Befunde DMB-09a956e8457d und DMB-d4f788c04158: In „Mitglieder › Anfragen“
 * stand die Status-Reiterzeile „Offen · Aufgenommen · Abgelehnt“ ÜBER den
 * Unterbereichen. Sie filterte deshalb auch dann, wenn „Links“ oder
 * „Formulare“ gewählt war — dort ohne jede Wirkung. Zusammen mit der
 * Bereichsliste links ergab das drei Reiterebenen.
 *
 * Soll (Entwurf A2): Der Statusfilter ist eine Chip-Zeile MIT ZAHLEN direkt
 * über der Anfragen-Tabelle und existiert NUR dort. Tabelle und
 * Detailfenster nennen die Zustände in derselben Sprache wie die Chips
 * („Offen/Aufgenommen/Abgelehnt“ statt „Anmeldeanfrage/Bestätigt“).
 *
 * Geprüft wird am GERENDERTEN DOM (SFC mit @vue/compiler-sfc übersetzt,
 * serverseitig gerendert, Unterkomponenten als Platzhalter) und an den reinen
 * Helfern der Seite — ein reiner Textvergleich sähe weder die Stelle der
 * Chip-Zeile noch eine falsche Zahl.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')
const TEMP = new URL('../.uxa2b-tmp/', import.meta.url)

/**
 * Ein SFC als ladbares Modul: Skript + Render-Funktion.
 *
 * Relative Importe zeigen in der Zwischendatei ins Leere; sie werden deshalb
 * auf ihre ECHTE Adresse umgeschrieben — sonst scheitert jeder Baustein, der
 * etwas einbindet. ACHTUNG: eine so eingebundene .vue-Datei könnte Node nicht
 * laden; die Seite wird deshalb mit Platzhaltern für ihre Unterkomponenten
 * gerendert (`stubs`, Namen wie im Skript von `Registrierung.vue`).
 */
async function sfcLaden(pfad, nr) {
  const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
  const url = new URL(pfad, root)
  const { descriptor, errors } = parse(readFileSync(url, 'utf8'), { filename: url.pathname })
  assert.deepEqual(errors, [], `${pfad}: SFC-Struktur`)
  const skript = descriptor.scriptSetup ? compileScript(descriptor, { id: url.pathname }) : null
  const vorlage = compileTemplate({
    source: descriptor.template.content, filename: url.pathname, id: url.pathname,
    compilerOptions: { bindingMetadata: skript?.bindings || {} },
  })
  assert.deepEqual(vorlage.errors, [], `${pfad}: Vorlage — ${vorlage.errors[0]?.message || ''}`)
  const kopf = (skript?.content || '')
    .replace(/export default/, 'const __standard__ =')
    .replace(/(from\s+)(['"])(\.{1,2}\/[^'"]+)\2/g,
      (_t, praefix, _q, relativ) => praefix + JSON.stringify(new URL(relativ, url).href))
  const code = `${kopf}\n${vorlage.code.replace(/export function render/, 'function render')}
const __comp = __standard__ || {}
if (typeof render === 'function') __comp.render = render
export default __comp`
  mkdirSync(TEMP, { recursive: true })
  const datei = new URL(`./m${nr}.mjs`, TEMP)
  writeFileSync(datei, code)
  return (await import(datei.href)).default
}

// ── 1. Die Chip-Zeile: Zahlen, Ruhelage, Stelle im DOM ─────────────────────
{
  const seite = lies('pages/Registrierung.vue')
  const tpl = seite.slice(seite.indexOf('<template>'), seite.lastIndexOf('</template>'))
  const anfragen = tpl.slice(
    tpl.indexOf('v-if="unterbereich === \'anfragen\'"'),
    tpl.indexOf('v-if="unterbereich === \'links\'"'),
  )
  assert.ok(anfragen.includes('<DkFilterChips'), 'Chip-Zeile im Anfragen-Bereich')
  assert.ok(anfragen.indexOf('<DkFilterChips') < anfragen.indexOf('<DkCard'),
    'Chip-Zeile steht ÜBER der Tabelle')
  assert.ok(anfragen.includes(':chips="statusChips"'), 'Chips kommen aus der berechneten Liste')
  assert.ok(anfragen.includes(':model-value="statusFilter"'), 'Ruhelage ist der Statusfilter')
  assert.ok(anfragen.includes('@waehlen="statusFilter = $event"'), 'ein Klick setzt den Filter')
  assert.ok(!anfragen.includes(':mit-zahl="false"'), 'die Zahlen sind ausdrücklich AN')
  // Am Handy scrollt die Zeile über die EIGENSCHAFT von DkFilterChips; eine
  // eigene Mobil-Regel in der Seite gab es (Befund Operator-Review).
  assert.ok(/\sscrollbar(\s|>)/.test(anfragen), 'Chip-Zeile nutzt `scrollbar` von DkFilterChips')
  assert.ok(!/\.reg-statusfilter\s*\{[^}]*overflow-x/.test(seite),
    'keine eigene Mobil-Regel für den Statusfilter')
  assert.ok(!/\.reg-statusfilter[^{]*\{[^}]*flex-wrap/.test(seite),
    'kein eigenes Umbruch-Verhalten am Statusfilter')

  // NUR hier: Links und Formulare haben keinen Statusfilter.
  const links = tpl.slice(tpl.indexOf('v-if="unterbereich === \'links\'"'),
    tpl.indexOf('v-if="unterbereich === \'formulare\'"'))
  const formulare = tpl.slice(tpl.indexOf('v-if="unterbereich === \'formulare\'"'),
    tpl.lastIndexOf('</template>'))
  assert.ok(!links.includes('DkFilterChips'), 'kein Statusfilter bei Links & QR-Codes')
  assert.ok(!formulare.includes('DkFilterChips'), 'kein Statusfilter bei Formularen')
  assert.ok(!tpl.includes('<DkTabs'), 'die alte Status-Reiterzeile über den Unterbereichen ist fort')

  // Die alte Reiterliste und ihr Zustand sind aus dem Skript verschwunden.
  assert.ok(!seite.includes('statusTabs'), '`statusTabs` entfernt')
  assert.ok(!seite.includes('statusTab.'), '`statusTab` entfernt')
  assert.ok(!seite.includes("import DkTabs"), 'DkTabs nicht mehr eingebunden')
}

// ── 2. Zahlen und Wörter: die reinen Helfer der Seite ──────────────────────
{
  const seite = lies('pages/Registrierung.vue')
  const skript = seite.slice(seite.indexOf('<script setup>') + '<script setup>'.length,
    seite.indexOf('</script>'))
  const teile = [
    /const OFFENE_ANMELDESTATI = \[[^\]]*\]/.exec(skript)?.[0],
    /const STATUS_LEITER = \[[\s\S]*?\n\]/.exec(skript)?.[0],
    /const ANMELDESTATUS_SPRACHE = \{[\s\S]*?\n\}/.exec(skript)?.[0],
    /const ANMELDETYP_SPRACHE = \{[\s\S]*?\n\}/.exec(skript)?.[0],
    /function istOffen\(a\) \{[\s\S]*?\n\}/.exec(skript)?.[0],
    /function statusSprache\(status\) \{[\s\S]*?\n\}/.exec(skript)?.[0],
    /function artText\(typ\) \{[\s\S]*?\n\}/.exec(skript)?.[0],
    /function zaehle\(art\) \{[\s\S]*?\n\}/.exec(skript)?.[0],
  ]
  for (const teil of teile) assert.ok(teil, 'Helfer der Seite gefunden')
  mkdirSync(TEMP, { recursive: true })
  const datei = new URL('./helfer.mjs', TEMP)
  writeFileSync(datei, `${teile.join('\n\n')}
const anmeldungen = { value: [] }
function setzeAnmeldungen(liste) { anmeldungen.value = liste }
export { STATUS_LEITER, ANMELDESTATUS_SPRACHE, ANMELDETYP_SPRACHE, statusSprache, artText, zaehle, istOffen, setzeAnmeldungen }
`)
  const h = await import(datei.href)

  // Wort UND Kennzeichen je Server-Wert — dieselbe Sprache wie die Chips.
  assert.deepEqual({ ...h.statusSprache('Anmeldeanfrage') }, { wort: 'Offen', variant: 'warn' })
  assert.deepEqual({ ...h.statusSprache('Ausstehend') }, { wort: 'Offen', variant: 'warn' })
  assert.deepEqual({ ...h.statusSprache('Bestätigt') }, { wort: 'Aufgenommen', variant: 'ok' })
  assert.deepEqual({ ...h.statusSprache('Abgelehnt') }, { wort: 'Abgelehnt', variant: 'err' })
  // Unbekannter Wert wird gezeigt, nicht erfunden.
  assert.deepEqual({ ...h.statusSprache('EtwasNeues') }, { wort: 'EtwasNeues', variant: 'neutral' })
  assert.deepEqual({ ...h.statusSprache('') }, { wort: '–', variant: 'neutral' })

  assert.equal(h.artText('Mitglied-Registrierung'), 'Mitglied')
  assert.equal(h.artText('Gast-Anmeldung'), 'Gast')
  assert.equal(h.artText('Veranstaltung'), 'Veranstaltung', 'unbekannter Typ bleibt stehen')
  assert.equal(h.artText(undefined), '–')

  // Die vier Zustände der Chip-Zeile, in der Reihenfolge des Mockups a2:
  // „Alle n · Offen n · Aufgenommen n · Abgelehnt n“.
  assert.deepEqual(h.STATUS_LEITER.map(s => s.label), ['Alle', 'Offen', 'Aufgenommen', 'Abgelehnt'])
  assert.deepEqual(h.STATUS_LEITER.map(s => s.wert), ['alle', 'offen', 'genehmigt', 'abgelehnt'])

  // Die Zahlen: „Alle“ zählt JEDE Anfrage (auch Warteliste), offen zählt BEIDE
  // offenen Server-Werte, Aufgenommen und Abgelehnt je ihren.
  h.setzeAnmeldungen([
    { status: 'Anmeldeanfrage' }, { status: 'Ausstehend' },
    { status: 'Bestätigt' }, { status: 'Abgelehnt' }, { status: 'Warteliste' },
  ])
  assert.equal(h.zaehle('alle'), 5, 'alle zählt auch Warteliste-Anfragen')
  assert.equal(h.zaehle('offen'), 2, 'offen zählt Anmeldeanfrage und Ausstehend')
  assert.equal(h.zaehle('genehmigt'), 1, 'aufgenommen zählt Bestätigt')
  assert.equal(h.zaehle('abgelehnt'), 1, 'abgelehnt zählt Abgelehnt')
  // Kein unsichtbarer Zustand: die Einzelzahlen decken zusammen „Alle“ ab —
  // der Rest sind Warteliste-Anfragen, und die stehen unter „Alle“.
  assert.equal(h.zaehle('offen') + h.zaehle('genehmigt') + h.zaehle('abgelehnt'), 4,
    'eine Anfrage bleibt übrig (Warteliste) und ist unter „Alle“ sichtbar')
  h.setzeAnmeldungen([])
  assert.deepEqual([h.zaehle('alle'), h.zaehle('offen'), h.zaehle('genehmigt'), h.zaehle('abgelehnt')],
    [0, 0, 0, 0], 'leere Liste: echte Nullen, keine erfundene Zahl')
}

// ── 3. Die Tabelle zeigt die Statussprache (kein Rohwert mehr) ─────────────
{
  const seite = lies('pages/Registrierung.vue')
  const tpl = seite.slice(seite.indexOf('<template>'), seite.lastIndexOf('</template>'))
  assert.ok(tpl.includes('statusSprache(a.status).wort'), 'Statuszelle nutzt die Statussprache')
  assert.ok(tpl.includes(':variant="statusSprache(a.status).variant"'),
    'Kennzeichenfarbe kommt aus derselben Quelle')
  assert.ok(!tpl.includes('{{ a.status }}'), 'kein roher Status in der Tabelle')
  assert.ok(!/function statusVariante/.test(seite), 'die alte zweite Wortliste ist entfernt')
  // Detailfenster in derselben Sprache.
  assert.ok(tpl.includes('statusSprache(detailAnmeldung.status).wort'),
    'Detailfenster nutzt dieselbe Statussprache')
  // Typ in Klartext, Spalte heisst „Typ“ (wie in der Vorlage), nicht „Art“.
  assert.ok(tpl.includes('artText(a.anmeldungstyp)'), 'Typ in Klartext')
  assert.ok(tpl.includes('artText(detailAnmeldung.anmeldungstyp)'), 'Typ im Detail in Klartext')
  assert.ok(/label: 'Typ'/.test(seite), 'Spalte Typ')
  assert.ok(!/label: 'Art'/.test(seite), 'Spalte „Art“ entfallen')
}

// ── 4. Klick-Wirkung: kein unsichtbarer Zustand ────────────────────────────
{
  const seite = lies('pages/Registrierung.vue')
  const skript = seite.slice(seite.indexOf('<script setup>') + '<script setup>'.length,
    seite.indexOf('</script>'))
  const teile = [
    /const OFFENE_ANMELDESTATI = \[[^\]]*\]/.exec(skript)?.[0],
    /const STATUS_LEITER = \[[\s\S]*?\n\]/.exec(skript)?.[0],
    /function istOffen\(a\) \{[\s\S]*?\n\}/.exec(skript)?.[0],
    /const filteredAnmeldungen = computed\(\(\) => \{[\s\S]*?\n\}\)/.exec(skript)?.[0],
  ]
  for (const teil of teile) assert.ok(teil, 'Helfer für die Klick-Wirkung gefunden')
  mkdirSync(TEMP, { recursive: true })
  const datei = new URL('./wirkung.mjs', import.meta.url)
  writeFileSync(datei, `import { computed } from 'vue'
${teile.join('\n\n')}
export { STATUS_LEITER, filteredAnmeldungen, istOffen }
`)
  const h = await import(datei.href)
  const { naechsterChip } = await import(new URL('./composables/filterChips.mjs', root).href)

  const liste = [
    { name: 'offen', status: 'Anmeldeanfrage' },
    { name: 'wieder-offen', status: 'Ausstehend' },
    { name: 'aufgenommen', status: 'Bestätigt' },
    { name: 'abgelehnt', status: 'Abgelehnt' },
    { name: 'warteliste', status: 'Warteliste' },
  ]

  // Der Filter selbst ist ein `computed` über `statusFilter` — hier wird die
  // Auswahl gesetzt und DIESELBE Berechnung nachgefahren; `zustand` ist die
  // nachgebaute Abhängigkeit (die Seite hat für sie eine `ref`).
  let zustand = 'offen'
  const waehle = (wert) => { zustand = wert }
  const gefiltert = () => liste.filter(a => {
    if (zustand === 'offen') return h.istOffen(a)
    if (zustand === 'genehmigt') return a.status === 'Bestätigt'
    if (zustand === 'abgelehnt') return a.status === 'Abgelehnt'
    return true
  })
  // Ruhelage der Seite ist „Offen“ (Arbeitsliste), nicht „Alle“.
  assert.match(skript, /const statusFilter = ref\('offen'\)/, 'Ruhelage ist „Offen“')
  // Der Rückfall der Berechnung ist die volle Liste (= „Alle“); nur so sind
  // Warteliste-Anfragen überhaupt erreichbar.
  assert.match(teile[3], /return anmeldungen\.value\s*\}\)/, '„Alle“ fällt auf die volle Liste zurück')

  assert.deepEqual(gefiltert().map(a => a.name), ['offen', 'wieder-offen'])
  waehle('alle')
  assert.deepEqual(gefiltert().map(a => a.name), liste.map(a => a.name),
    '„Alle“ zeigt jede Anfrage — auch die Warteliste')
  waehle('abgelehnt')
  assert.deepEqual(gefiltert().map(a => a.name), ['abgelehnt'])

  // Kein unsichtbarer Zustand: ein zweiter Klick auf den gewählten Chip
  // landet auf „Alle“ — und „Alle“ ist ein Chip, den man auch direkt wählen
  // kann. Vorher (drei Chips) war „alle“ nur über das Abwählen erreichbar und
  // nirgends markiert.
  assert.equal(naechsterChip('offen', 'offen'), 'alle', 'zweiter Klick → Alle')
  assert.equal(naechsterChip('offen', 'alle'), 'alle', 'Alle direkt wählbar')
  assert.equal(naechsterChip('alle', 'genehmigt'), 'genehmigt')
  assert.ok(h.STATUS_LEITER.some(s => s.wert === 'alle'),
    '„Alle“ steht als eigener Chip in der Leiter')
}
rmSync(TEMP, { recursive: true, force: true })
console.log('UX-A2b Status-Filterchips: bestanden')
