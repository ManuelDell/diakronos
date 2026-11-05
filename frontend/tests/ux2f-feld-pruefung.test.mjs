import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// UX2f · Feld mit Prüfung — Node-Tests der Prüfregeln UND der Komponente.
//
// Die Regeln sind reines JavaScript (composables/feldPruefung.mjs); hier wird
// jede Regel einzeln geprüft, inklusive der MELDUNGSTEXTE: die Karte verlangt
// „was fehlt + Beispiel" — eine Meldung ohne Beispiel wäre ein Befund.
//
// Die Komponente wird über den vue-compiler geprüft (wie dkbutton-icon):
// Vorlage und Skript müssen übersetzen, die geforderten Merkmale (aria,
// Prüfung beim Verlassen, danach beim Tippen) müssen im Quelltext stehen.
// Das Verhalten im Browser zeigt die Playwright-Abnahme.

const QUELLE = new URL('../src/diakonos/composables/feldPruefung.mjs', import.meta.url)
const FELD = new URL('../src/diakonos/components/ui/DkField.vue', import.meta.url)
const feldQuelle = readFileSync(FELD, 'utf8')

const {
  MELDUNGEN, email, url, plz, laenge, pflicht, eigene, regeln, pruefeAlle,
} = await import(QUELLE.href)

// ── 1 · Pflicht ────────────────────────────────────────────────────────────
test('UX2f: pflicht — leere Werte werden beanstandet, gefüllte nicht', () => {
  const r = pflicht('einen Vornamen')
  for (const leer of ['', '   ', null, undefined, '\t\n']) {
    assert.equal(r(leer), 'Bitte einen Vornamen angeben.', `leer: ${JSON.stringify(leer)}`)
  }
  assert.equal(r('Maria'), '')
  assert.equal(r('  Maria  '), '', 'Leerzeichen außen zählen nicht')
  assert.equal(r(0), '', 'die Ziffer 0 ist ein Wert')
})

// ── 2 · E-Mail ─────────────────────────────────────────────────────────────
test('UX2f: email — nimmt gültige Adressen an', () => {
  const r = email()
  for (const gut of [
    'maria.lang@example.org',
    'maria@example.org',
    'm.lang+news@example.co.uk',
    'erste-letzte@sub.example.de',
    'maria_lang@example.org',
    'müller@example.de',
  ]) {
    assert.equal(r(gut), '', `gültig: ${gut}`)
  }
})

test('UX2f: email — die Meldung nennt den ERSTEN fehlenden Teil mit Beispiel', () => {
  const r = email()
  // UX2f2a: Ein LEERES Feld beanstandet nur `pflicht` — email() sagt hier ''.
  assert.equal(r(''), '')
  assert.match(r('maria.lang'), /fehlt das @.*z\. B\. maria\.lang@example\.org/)
  assert.match(r('maria@'), /Teil nach dem @.*z\. B\. example\.org/)
  assert.match(r('@example.org'), /Teil vor dem @.*z\. B\. maria\.lang@example\.org/)
  // UX2f (Befund der Abnahme): das Beispiel nennt den GANZEN Aufbau, nicht nur
  // die Domain — sonst zeigt es genau den Teil, der schon dasteht.
  assert.match(r('maria@example'), /Endung.*z\. B\. maria\.lang@example\.org/)
  assert.match(r('maria@@example.org'), /mehr als ein @/)
  assert.match(r('maria lang@example.org'), /Leerzeichen/)
  assert.match(r('maria@exa mple.org'), /Leerzeichen/)
  assert.match(r('maria<lang>@example.org'), /„<"/)
})

test('UX2f: email — jede Meldung trägt ein Beispiel (Fehlerkatalog-Muster)', () => {
  const r = email()
  const faelle = ['maria.lang', 'maria@', '@example.org', 'maria@example', 'a@@b.de', 'a b@c.de', 'a@b..de']
  for (const fall of faelle) {
    const meldung = r(fall)
    assert.ok(meldung, `kein Fehler bei ${JSON.stringify(fall)}`)
    assert.match(meldung, /z\. B\.|– /, `Meldung ohne Beispiel: ${meldung}`)
    assert.match(meldung, /[.!]$/, `Meldung ohne Satzende: ${meldung}`)
  }
})

// ── 3 · URL ────────────────────────────────────────────────────────────────
test('UX2f: url — nimmt gültige Website-Adressen an', () => {
  const r = url()
  for (const gut of [
    'https://www.example.org',
    'https://example.org',
    'https://example.org/pfad/zur/seite',
    'https://sub.example.co.uk/a?b=1#c',
    'https://example.org:8443/x',
  ]) {
    assert.equal(r(gut), '', `gültig: ${gut}`)
  }
})

test('UX2f: url — beanstandet fehlendes Schema und fehlenden Namen, mit Beispiel', () => {
  const r = url()
  // UX2f2a: leer ist kein Fehler (nur `pflicht`), und http:// ist wieder
  // erlaubt — LAN-Instanzen und gespeicherte Websites.
  assert.equal(r(''), '')
  assert.equal(r('http://example.org'), '')
  assert.match(r('www.example.org'), /muss mit http:\/\/ oder https:\/\/ beginnen/)
  assert.match(r('https://'), /fehlt der Name.*z\. B\. www\.example\.org/)
  assert.match(r('https://example'), /Endung des Namens – z\. B\. www\.example\.org/)
  assert.match(r('https://exa<mple.org'), /unerlaubtes Zeichen/)
  assert.equal(r('HTTPS://example.org'), '', 'Großschreibung ist erlaubt')
})

// ── 4 · Postleitzahl ───────────────────────────────────────────────────────
test('UX2f: plz — fünf Ziffern, Meldung nennt die erreichte Zahl und das Beispiel', () => {
  const r = plz()
  assert.equal(r('71638'), '')
  assert.equal(r('71638 '), '', 'Leerzeichen außen zählen nicht')
  assert.match(r('7163'), /hat 4 Stellen, nötig sind 5 – z\. B\. 71638/)
  assert.match(r('716388'), /hat 6 Stellen, nötig sind 5/)
  assert.match(r('7163a'), /nur aus Ziffern – z\. B\. 71638/)
  // UX2f2a: leer ist kein Fehler — das meldet nur `pflicht`.
  assert.equal(r(''), '')
})

test('UX2f: plz — andere Stellenzahl (z. B. 4) ist einstellbar', () => {
  const r = plz(4)
  assert.equal(r('1015'), '')
  assert.match(r('10150'), /hat 5 Stellen, nötig sind 4 – z\. B\. 1015/)
})

// ── 5 · Länge ──────────────────────────────────────────────────────────────
test('UX2f: laenge — zu kurz und zu lang nennen die Zahl und die Grenze', () => {
  // ohne min: ein leeres Feld bleibt in Ruhe
  const nurMax = laenge({ max: 10, name: 'Der Name' })
  assert.equal(nurMax(''), '', 'ohne min bleibt ein leeres Feld in Ruhe')
  const kurz = laenge({ min: 8, name: 'Das Passwort' })
  assert.equal(kurz('geheim123'), '')
  assert.match(kurz('geheim'), /mit 6 Zeichen zu kurz – nötig sind mindestens 8/)

  const lang = laenge({ max: 10, name: 'Der Name' })
  assert.equal(lang('1234567890'), '')
  assert.match(lang('12345678901'), /mit 11 Zeichen zu lang – erlaubt sind höchstens 10.*Bitte 1 Zeichen kürzen/)
  assert.match(lang('1234567890123'), /Bitte 3 Zeichen kürzen/)
})

test('UX2f: laenge — min > 0 macht das Feld zur Pflicht', () => {
  const r = laenge({ min: 3, name: 'Der Ort' })
  assert.match(r(''), /Bitte Der Ort angeben|Bitte einen Text angeben/)
})

test('UX2f: laenge — zählt Zeichen, nicht Bytes (Umlaute)', () => {
  assert.equal(laenge({ max: 3 })('äöü'), '')
  assert.match(laenge({ min: 5 })('äöü'), /mit 3 Zeichen zu kurz/)
})

// ── 6 · Eigene Funktion ────────────────────────────────────────────────────
test('UX2f: eigene — eigene Funktionen liefern Meldung, true/null heißt gut', () => {
  assert.equal(eigene(() => true)('x'), '')
  assert.equal(eigene(() => null)('x'), '')
  assert.equal(eigene(() => '')('x'), '')
  assert.equal(eigene(() => 'Bitte eine Zahl größer als 0 angeben.')('x'), 'Bitte eine Zahl größer als 0 angeben.')
  assert.equal(eigene(() => false)('x'), 'Bitte diesen Wert prüfen.')
  // Die eigene Funktion bekommt das ganze Formular (Feldvergleiche).
  const gleich = eigene((wert, form) => (wert === form.passwort ? '' : 'Die Passwörter stimmen nicht überein.'))
  assert.equal(gleich('a', { passwort: 'a' }), '')
  assert.match(gleich('a', { passwort: 'b' }), /stimmen nicht überein/)
})

// ── 7 · Zusammenfassen und Sammelprüfung ───────────────────────────────────
test('UX2f: regeln — die erste Regel mit Meldung gewinnt', () => {
  const r = regeln(pflicht('eine E-Mail-Adresse'), email())
  assert.match(r(''), /Bitte eine E-Mail-Adresse angeben/)
  assert.match(r('maria'), /fehlt das @/)
  assert.equal(r('maria@example.org'), '')
  assert.equal(regeln()('egal'), '', 'ohne Regeln ist alles in Ordnung')
})

test('UX2f: pruefeAlle — beanstandet nur die fehlerhaften Felder', () => {
  const felder = {
    vorname: ['', pflicht('einen Vornamen')],
    email: ['maria@', email()],
    plz: ['71638', plz()],
  }
  const fehler = pruefeAlle(felder, {})
  assert.deepEqual(Object.keys(fehler).sort(), ['email', 'vorname'])
  assert.match(fehler.email, /Teil nach dem @/)
  assert.equal(fehler.plz, undefined, 'gültiges Feld erzeugt keinen Eintrag')
})

// ── 8 · Die Komponente DkField ─────────────────────────────────────────────
test('UX2f: DkField kompiliert (Vorlage und Skript)', () => {
  const { descriptor, errors } = parse(feldQuelle, { filename: 'DkField.vue' })
  assert.deepEqual(errors, [], 'SFC-Struktur')
  const script = compileScript(descriptor, { id: 'DkField.vue' })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename: 'DkField.vue',
    id: 'DkField.vue',
    compilerOptions: { bindingMetadata: script.bindings || {} },
  })
  assert.deepEqual(template.errors.map(e => e.message || String(e)), [], 'Vorlage kompiliert')
})

test('UX2f: DkField verbindet Label, Eingabe und Meldung (aria-describedby, aria-invalid)', () => {
  // UX2f2a: ZWEI Kennungen — die Meldung und der Hilfetext. Vorher gab es nur
  // `beschreibungId`; bei Hilfe OHNE Meldung nannte `aria-describedby` sie,
  // trug aber niemand im DOM (Review-Befund).
  assert.match(feldQuelle, /meldungId\s*=\s*computed\(/, 'keine abgeleitete Meldungs-ID')
  assert.match(feldQuelle, /hilfeId\s*=\s*computed\(/, 'keine abgeleitete Hilfe-ID')
  // `beschriebenDurch` wählt: Meldung, sonst Hilfe, sonst nichts.
  const beschreibt = feldQuelle.match(/const beschriebenDurch = computed\(\(\) => \{([\s\S]*?)\n\}\)/)
  assert.ok(beschreibt, 'beschriebenDurch fehlt')
  assert.match(beschreibt[1], /if \(angezeigterFehler\.value\) return meldungId\.value/)
  assert.match(beschreibt[1], /if \(hilfeText\.value\) return hilfeId\.value/)
  assert.match(beschreibt[1], /return undefined/)
  // `feldProps` trägt den vollständigen Feldsatz, aria-describedby aber NUR
  // mit einem Ziel (sonst zeigte es ins Leere — Befund der Abnahme).
  assert.match(feldQuelle, /'aria-describedby':\s*beschriebenDurch\.value/,
    'aria-describedby fehlt/bedingungslos in feldProps')
  assert.match(feldQuelle, /'aria-invalid':\s*angezeigterFehler\.value/, 'aria-invalid fehlt in feldProps')
  // Die Meldung trägt die Meldungs-ID und wird vorgelesen.
  assert.match(feldQuelle, /:id="meldungId"[^>]*role="alert"/, 'Fehlertext ohne role=alert oder ohne gleiche ID')
  // Der Hilfetext trägt seine EIGENE Kennung — nicht die der Meldung: sonst
  // läse ein Screenreader bei einem Fehler den Tipp statt der Meldung vor.
  assert.match(feldQuelle, /:id="hilfeId"[^>]*class="dk-ui-field-hilfe"/, 'Hilfetext ohne eigene Kennung')
  assert.doesNotMatch(feldQuelle, /:id="meldungId"[^>]*class="dk-ui-field-hilfe"/)
  // Label zeigt auf die Eingabe.
  assert.match(feldQuelle, /:for="eingabeId"/, 'Label ohne for')
})

test('UX2f: DkField prüft beim Verlassen, danach beim Tippen', () => {
  // Verlassen prüft IMMER und zeigt das Ergebnis — aber nicht schon beim
  // Fokussieren (Befund der Browser-Abnahme: der Fehler blitzte beim zweiten
  // Besuch des Feldes auf, ohne dass etwas verlassen wurde).
  assert.match(feldQuelle, /function verlassen\(ereignis\)\s*\{/)
  assert.match(feldQuelle, /if \(el && typeof el\.matches === 'function' && el === document\.activeElement\) return/)
  assert.match(feldQuelle, /pruefe\(props\.wert, true\)/)
  assert.match(feldQuelle, /onFocus: verlassen/, 'Fokus muss die Prüfung auslösen/abgrenzen')
  assert.match(feldQuelle, /onBlur: verlassen/, 'Blur prüft')
  // Tippen prüft nur, wenn schon ein Fehler gezeigt wird (oder das Feld
  // zuletzt gültig war) — nicht beim ersten Buchstaben.
  const tippen = feldQuelle.match(/function getippt\(wert\)\s*\{([\s\S]*?)\n\}/)
  assert.ok(tippen, 'getippt() fehlt')
  assert.match(tippen[1], /if \(beruehrt\.value && eigenFehler\.value\) pruefe\(wert, true\)/)
  assert.match(tippen[1], /emit\('update:wert', wert\)/, 'Tippen reicht den Wert nicht weiter')
  // Vor dem ersten Verlassen wird kein Fehler gezeigt.
  assert.match(feldQuelle, /angezeigterFehler = computed\(\(\) => props\.error \|\| \(beruehrt\.value \? eigenFehler\.value : ''\)\)/)
})

test('UX2f: DkField schreibt NIE in die Eingabe (Eingaben bleiben erhalten)', () => {
  const skript = feldQuelle.slice(feldQuelle.indexOf('<script setup>'))
  assert.doesNotMatch(skript, /element\.value\s*=/, 'schreibt direkt in das DOM-Feld')
  // `update:wert` kommt ausschließlich vom Tippen des Nutzers — seit UX2f2a
  // reichen onInput UND onUpdate:modelValue des Feldsatzes dorthin, das ist
  // EINE Funktion (`getippt`), die genau einmal emit't. NUR den Code zählen,
  // nicht die Erwähnung im Kommentar oben.
  const code = skript.replace(/\/\*[\s\S]*?\*\//g, '')
  const emitStellen = code.match(/emit\('update:wert'[^)]*\)/g) || []
  assert.equal(emitStellen.length, 1, `update:wert nur an einer Stelle (${emitStellen.length})`)
})

test('UX2f: DkField kennt die Regelformen der Karte', () => {
  const pruefDatei = readFileSync(QUELLE, 'utf8')
  for (const name of ['pflicht', 'email', 'url', 'plz', 'laenge', 'eigene']) {
    assert.match(pruefDatei, new RegExp(`export function ${name}\\(`), `Regel ${name} fehlt`)
  }
})

// BEFUND der Abnahme: DkEingabe deklariert nur ihre eigenen Props und reichte
// fremde Attribute NICHT ans <input> weiter — `onBlur`, `aria-describedby` und
// `id` aus `DkField` gingen damit verloren, die Prüfung war am Feld unsichtbar.
test('UX2f: DkEingabe reicht die Feld-Auszeichnung ans Eingabeelement durch', () => {
  const eingabe = readFileSync(new URL('../src/diakonos/components/ui/DkEingabe.vue', import.meta.url), 'utf8')
  assert.match(eingabe, /v-bind="\$attrs"/, 'DkEingabe bindet $attrs nicht ans <input>')
  assert.match(eingabe, /defineOptions\(\{\s*inheritAttrs:\s*false\s*\}\)/,
    'ohne inheritAttrs:false landet $attrs zusätzlich am Wurzelelement')
})

test('UX2f: DkField nutzt nur Tokens (keine festen Farben)', () => {
  const stil = feldQuelle.slice(feldQuelle.indexOf('<style'))
  assert.doesNotMatch(stil, /#[0-9a-f]{3,8}\b/i, 'fester Farbwert')
  assert.doesNotMatch(stil, /rgba?\(|hsla?\(/, 'feste Farbe')
  // Pflichtzeichen und Meldung kommen aus --err (wechselt mit dem Theme).
  assert.match(stil, /\.dk-ui-field-pflicht\s*\{[^}]*var\(--err\)/)
  assert.match(stil, /\.dk-ui-field-fehler\s*\{[^}]*var\(--err\)/)
})

// ── 9 · Die Slot-Auszeichnung landet AM FELD, nicht als Objekt-Attribut ────
//
// Befund aus der Abnahme im Wegwerf-Stack (UX2f): Wurde das ganze Slot-Objekt
// gebunden (`v-bind="feld"`), standen danach `feldprops="[object Object]"`,
// `ariadescribedby=` und `aria-invalid="false"` am Eingabefeld — Vue schreibt
// ein gebundenes Objekt als Attribute, wenn es keine `v-bind`-Aufteilung ist.
// Seitdem gilt: gebunden wird der Feldsatz (`v-bind="feld.feldProps"`).
test('UX2f: kein Eingabeelement bindet das ganze Slot-Objekt', () => {
  const SRC = new URL('../src/', import.meta.url)
  const treffer = []
  const durchlaufe = (verz) => {
    for (const eintrag of readdirSync(verz, { withFileTypes: true })) {
      const pfad = path.join(verz, eintrag.name)
      if (eintrag.isDirectory()) { durchlaufe(pfad); continue }
      if (!pfad.endsWith('.vue')) continue
      const text = readFileSync(pfad, 'utf8')
      // Erlaubt ist `v-bind="<slot>.feldProps"` (Feldsatz) und die
      // schlanke Form `v-bind="feldProps"` (Slot ohne Bindung an einen
      // eigenen Namen). Verboten ist jede andere Objektbindung.
      // `$attrs` ist die Weiterreichung durchgereichter Attribute (DkEingabe),
      // kein Slot-Objekt.
      const muster = /<(?:input|select|textarea|DkEingabe|DkSelect)\b[^>]*v-bind="(?!(?:[A-Za-z_$][\w$]*\.)?feldProps"|\$attrs")[A-Za-z_$][\w$]*"/g
      for (const m of text.match(muster) || []) treffer.push(`${path.relative(SRC.pathname, pfad)}: ${m}`)
    }
  }
  durchlaufe(SRC.pathname)
  assert.deepEqual(treffer, [], 'Slot-Objekt statt feldsatz gebunden: ' + treffer.join(' | '))
})
