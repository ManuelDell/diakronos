/**
 * REG-1c — Nacharbeit Registrierung (Oberflaechen-Teil).
 *
 * Geprueft wird, was die Karte verlangt und was ein Tester sonst erst im
 * Betrieb merkt:
 *
 *   (1) Dateizuordnung : Der Bild-Upload nennt `doctype`/`docname`
 *                       (`Anmeldeformular`/Formular-Kennung). Der Server nimmt
 *                       ein Bild nur noch an, wenn der `File`-Datensatz an
 *                       GENAU DIESES Formular angehaengt ist — ohne die beiden
 *                       Felder entstuende eine Datei ohne Bezug. Ein NEUES
 *                       Formular wird deshalb VOR dem Upload angelegt.
 *   (4) Groessenpruefung: Die gewaehlte Datei wird VOR dem Upload gegen die
 *                       Server-Grenze geprueft, die Meldung nennt „max. X MB“
 *                       und der Wert kommt aus dem Boot-Objekt
 *                       (`bild_upload_max_bytes`) — also aus derselben Quelle
 *                       wie die Grenze des Servers.
 *
 * Der Test kompiliert die SFC echt (vue/compiler-sfc) und fuehrt die
 * betroffenen Funktionen mit Attrappen aus, statt am Quelltext zu raten.
 * Laeuft im Docker-Build ueber `node --test`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from 'vue/compiler-sfc'

const seite = new URL('../src/diakonos/', import.meta.url)
const regQuelle = readFileSync(new URL('pages/Registrierung.vue', seite), 'utf8')
const reg = parse(regQuelle, { filename: 'Registrierung.vue' })
assert.deepEqual(reg.errors, [], 'Registrierung.vue: SFC-Struktur')
const regSkript = compileScript(reg.descriptor, { id: 'reg1c-reg' }).content

// ════════════════════════════════════════════════════════════════════════════
// (1) Dateizuordnung — Upload nennt das Formular
// ════════════════════════════════════════════════════════════════════════════

const uploadBlock = regSkript.slice(
  regSkript.indexOf('async function uploadBild'),
  regSkript.indexOf('// ── Details'),
)
assert.ok(uploadBlock.length > 0, 'REG-1c: `uploadBild` nicht gefunden')
assert.match(
  uploadBlock,
  /form\.append\('doctype',\s*'Anmeldeformular'\)/,
  'REG-1c: der Upload nennt den Bezugstyp (doctype=Anmeldeformular) nicht',
)
assert.match(
  uploadBlock,
  /form\.append\('docname',\s*formularId\)/,
  'REG-1c: der Upload nennt die Formular-Kennung (docname) nicht',
)
assert.match(
  regSkript,
  /async function uploadBild\(datei,\s*formularId\)/,
  'REG-1c: `uploadBild` nimmt die Formular-Kennung nicht an',
)
// Ein NEUES Formular muss vor dem Upload existieren — sonst gaebe es keine
// Kennung, an die die Datei gehaengt werden koennte.
const createBlock = regSkript.slice(
  regSkript.indexOf('async function createFormular'),
  regSkript.indexOf('/**\n * REG-1b: Datei ueber den vorhandenen Weg hochladen'),
)
assert.ok(createBlock.length > 0, 'REG-1c: `createFormular` nicht gefunden')
assert.ok(
  createBlock.indexOf('create_anmeldeformular') < createBlock.indexOf('uploadBild('),
  'REG-1c: das Formular wird erst NACH dem Upload angelegt (keine Kennung fuer die Datei)',
)
assert.match(
  createBlock,
  /formularBearbeitet\.value\s*=\s*res\.id/,
  'REG-1c: die neue Formular-Kennung wird nicht uebernommen',
)
assert.match(
  createBlock,
  /await uploadBild\(datei,\s*formularId\)/,
  'REG-1c: der Upload bekommt die Formular-Kennung nicht',
)

// Die Funktion wirklich ausfuehren: FormData-Attrappe sammelt die Felder.
{
  // `uploadBlock` beginnt mit `async function uploadBild(datei, formularId) {`.
  const quelle = uploadBlock.slice(uploadBlock.indexOf('{') + 1)
  const ende = quelle.lastIndexOf('}')
  const rumpf = `async function uploadBild(datei, formularId) {${quelle.slice(0, ende)}}`
  const gesendet = []
  const apparat = new Function(
    'document', 'window', 'formularMeldung', 'fetch', 'FormData',
    `${rumpf}\nreturn uploadBild;`,
  )
  const formDataAttrappe = class {
    constructor() { this.felder = [] }
    append(schluessel, wert) { this.felder.push([schluessel, wert]) }
  }
  const document_ = { querySelector: () => null }
  const window_ = { __DIakonosBOOT: { csrf_token: 'csrf-test' } }
  const uploadBild = await apparat(
    document_, window_, (e, f) => f,
    async (url, optionen) => {
      gesendet.push({ url, felder: optionen.body.felder })
      return { ok: true, json: async () => ({ message: { file_url: '/files/abc-bild.png' } }) }
    },
    formDataAttrappe,
  )
  const antwort = await uploadBild({ name: 'banner.png' }, 'AF-REG1C')
  assert.equal(antwort.file_url, '/files/abc-bild.png', 'REG-1c: Upload-Antwort wird durchgereicht')
  assert.equal(gesendet.length, 1, 'REG-1c: der Upload wurde nicht abgeschickt')
  assert.equal(gesendet[0].url, '/api/method/upload_file', 'REG-1c: falscher Endpunkt')
  const felder = Object.fromEntries(gesendet[0].felder)
  assert.equal(felder.doctype, 'Anmeldeformular', 'REG-1c: doctype fehlt im Aufruf')
  assert.equal(felder.docname, 'AF-REG1C', 'REG-1c: docname fehlt im Aufruf')
}

// ════════════════════════════════════════════════════════════════════════════
// (4) Groessenpruefung vor dem Upload, Meldung mit „max. X MB“
// ════════════════════════════════════════════════════════════════════════════

assert.match(
  regSkript,
  /return Number\(window\.__DIakonosBOOT\?\.bild_upload_max_bytes\) \|\| 0/,
  'REG-1c: die Groessengrenze kommt nicht aus dem Boot-Objekt (Server-Quelle)',
)
assert.match(
  regSkript,
  /function bildMaxBytes\(\)/,
  'REG-1c: die Grenze wird nicht als Zahl gelesen',
)
assert.match(
  regSkript,
  /datei\.size > grenze/,
  'REG-1c: die gewaehlte Datei wird nicht gegen die Grenze geprueft',
)
assert.match(
  regSkript,
  /max\. \$\{bildMaxText\(grenze\)\}/,
  'REG-1c: die Meldung nennt die Grenze nicht als „max. X MB“',
)
// Die Pruefung steht VOR dem Hochladen (im Auswahl-Zweig, nicht im Speichern).
assert.ok(
  regSkript.indexOf('datei.size > grenze') < regSkript.indexOf("fetch('/api/method/upload_file'"),
  'REG-1c: die Groessenpruefung liegt nicht vor dem Upload',
)

// Und sie wirkt: zu grosse Datei -> Meldung, keine Datei gemerkt, kein Upload.
{
  const start = regSkript.indexOf('/** Grenze eines Formularbildes in Bytes')
  const ende = regSkript.indexOf('/**\n * REG-1b: Datei ueber den vorhandenen Weg hochladen')
  const block = regSkript.slice(start, ende)

  // Die drei kleinen Helfer WOERTLICH aus der Seite uebernehmen — so prueft
  // der Test den echten Code und keine Nachbildung.
  const hole = (von, bis) => block.slice(block.indexOf(von), block.indexOf(bis))
  const rumpfBytes = hole('function bildMaxBytes()', 'function bildMaxText')
  const rumpfText = hole('function bildMaxText', 'function bildGewaehlt')
  const funktion = block.slice(block.indexOf('function bildGewaehlt'))
  // Der Rumpf endet an der ERSTEN Zeile, die wieder auf Spalte 0 schliesst
  // (verschachtelte Bloecke enden eingerueckt).
  const rumpfGewaehlt = funktion.slice(funktion.indexOf('{') + 1, funktion.indexOf('\n}\n') + 1)

  const apparat = new Function(
    'window', 'bildDateien', 'bildFehler', 'bilderEntfernen', 'formularBilder', 'URL',
    `${rumpfBytes}
     ${rumpfText}
     function bildGewaehlt(rolle, ereignis) {${rumpfGewaehlt}}
     return { bildGewaehlt, bildMaxText, bildMaxBytes }`,
  )

  const bildDateien = { value: { banner: null, hintergrund: null } }
  const bildFehler = { value: '' }
  const bilderEntfernen = { value: [] }
  const formularBilder = { value: { banner: '', hintergrund: '' } }
  const grenze = 10 * 1024 * 1024
  const s = apparat(
    { __DIakonosBOOT: { bild_upload_max_bytes: grenze } },
    bildDateien, bildFehler, bilderEntfernen, formularBilder,
    { createObjectURL: () => 'blob:x' },
  )

  // Die Grenze kommt wirklich aus dem Boot-Objekt und wird lesbar genannt.
  assert.equal(s.bildMaxBytes(), grenze, 'REG-1c: Grenze nicht aus dem Boot-Objekt')
  assert.equal(s.bildMaxText(grenze), '10 MB', 'REG-1c: Grenze wird nicht als „10 MB“ genannt')
  assert.equal(s.bildMaxText(1536 * 1024), '1,5 MB', 'REG-1c: krumme Grenze ohne Nachkommastelle')

  // Zu gross: Meldung mit Grenze, Datei verworfen.
  const ziel = { value: 'banner.png' }
  s.bildGewaehlt('banner', {
    target: { files: [{ name: 'gross.png', type: 'image/png', size: grenze + 1 }], value: 'x' },
  })
  assert.match(bildFehler.value, /zu groß/, 'REG-1c: zu grosse Datei wird nicht bemaengelt')
  assert.match(bildFehler.value, /max\. 10 MB/, 'REG-1c: die Meldung nennt die Grenze nicht')
  assert.equal(bildDateien.value.banner, null, 'REG-1c: zu grosse Datei bleibt gemerkt')
  assert.equal(ziel.value, 'banner.png', 'REG-1c: fremdes Objekt wurde veraendert')

  // Genau an der Grenze: erlaubt (der Server zieht dieselbe Grenze).
  s.bildGewaehlt('banner', {
    target: { files: [{ name: 'passt.png', type: 'image/png', size: grenze }], value: '' },
  })
  assert.equal(bildFehler.value, '', 'REG-1c: Datei an der Grenze wurde abgelehnt')
  assert.ok(bildDateien.value.banner, 'REG-1c: passende Datei wird nicht gemerkt')
  assert.equal(formularBilder.value.banner, 'blob:x', 'REG-1c: keine Vorschau fuer passende Datei')

  // Falscher Typ: bleibt abgelehnt (unveraendert).
  s.bildGewaehlt('hintergrund', {
    target: { files: [{ name: 'x.svg', type: 'image/svg+xml', size: 10 }], value: '' },
  })
  assert.match(bildFehler.value, /Nur PNG, JPEG, GIF oder WebP/, 'REG-1c: Typpruefung fehlt')

  // Ohne Angabe im Boot-Objekt (aeltere Installation): 0 = Server entscheidet.
  const ohne = apparat({}, bildDateien, bildFehler, bilderEntfernen, formularBilder, {})
  assert.equal(ohne.bildMaxBytes(), 0, 'REG-1c: fehlende Angabe muss 0 sein, nicht NaN')
}

console.log('REG-1c: alle Prüfungen bestanden')
