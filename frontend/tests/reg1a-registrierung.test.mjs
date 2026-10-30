/**
 * REG-1a — Registrierung: Startdatum, Beschreibung, Bilder (Frontend-Teil).
 *
 * Geprueft wird, was die OEFFENTLICHE Anmeldeseite aus den Serverangaben macht
 * (`window.__diakronos`, Quelle `registrierung.validate_token` bzw.
 * `spa._oeffentliche_daten`):
 *
 *   Startdatum : die Meldung „Anmeldung ab …“ erscheint auf der Fehlerseite
 *                (der Server schickt sie als `linkFehler`), das Formular bleibt
 *                aus — der Besucher sieht also keine Eingabemaske, die er
 *                ohnehin nicht absenden koennte.
 *   Beschreibung: erscheint als REINER Text (kein `v-html`, kein HTML-Bau).
 *   Bilder      : Banner als `<img>`, Hintergrund als dekoratives Bild mit
 *                 `aria-hidden`; ohne Bild kein leeres Element im Layout.
 *
 * REG-1b: Die beiden Teile liegen jetzt an ZWEI Stellen, und das ist Absicht:
 *
 *   * `registrierung/App.vue` — der Seitenrahmen: Hintergrundbild, Fehler-
 *     und Erfolgsseite, Durchreichen der Serverangaben.
 *   * `registrierung/components/DkAnmeldeformular.vue` — die Anzeige des
 *     Formulars selbst (Banner, Beschreibung, Felder). Dieselbe Komponente
 *     zeigt die Vorschau im Editor, damit die Vorschau nicht driften kann.
 *
 * Der Test kompiliert die SFCs echt (vue/compiler-sfc) statt am Quelltext zu
 * raten. Laeuft im Docker-Build ueber `node --test`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const wurzel = new URL('../src/registrierung/', import.meta.url)
const quelle = readFileSync(new URL('App.vue', wurzel), 'utf8')
const formularQuelle = readFileSync(new URL('components/DkAnmeldeformular.vue', wurzel), 'utf8')

const { descriptor, errors } = parse(quelle, { filename: 'App.vue' })
assert.deepEqual(errors, [], 'App.vue: SFC-Struktur')
compileScript(descriptor, { id: 'reg1a-app' })

const formular = parse(formularQuelle, { filename: 'DkAnmeldeformular.vue' })
assert.deepEqual(formular.errors, [], 'DkAnmeldeformular.vue: SFC-Struktur')
compileScript(formular.descriptor, { id: 'reg1a-formular' })

const skript = descriptor.scriptSetup.content
const vorlage = descriptor.template.content
const stil = descriptor.styles.map(s => s.content).join('\n')

const formularSkript = formular.descriptor.scriptSetup.content
const formularVorlage = formular.descriptor.template.content
const formularStil = formular.descriptor.styles.map(s => s.content).join('\n')

// ── Startdatum: die Meldung des Servers wird angezeigt ──────────────────────

assert.match(
  vorlage,
  /v-if="linkFehler"/,
  'REG-1a: die Fehlerseite haengt an linkFehler (dort steht „Anmeldung ab …“)',
)
assert.match(
  vorlage,
  /\{\{\s*linkFehler\s*\}\}/,
  'REG-1a: der Text des Servers wird unveraendert angezeigt (kein eigener Wortlaut)',
)
// Das Formular steht im `v-else`-Zweig: bei gesetztem linkFehler gibt es keine
// Eingabemaske (und damit auch keinen Absende-Knopf).
const formularZweig = vorlage.split('<!-- Formular')[1] || ''
assert.ok(
  formularZweig.includes('v-else'),
  'REG-1a: das Formular liegt im v-else-Zweig (bei linkFehler nicht sichtbar)',
)
assert.ok(
  formularZweig.includes('<DkAnmeldeformular'),
  'REG-1a: das Formular kommt aus der gemeinsamen Anzeige (REG-1b)',
)

// ── Beschreibung: reiner Text, niemals HTML ─────────────────────────────────

assert.match(skript, /window\.__diakronos\?\.beschreibung/, 'REG-1a: Beschreibung kommt vom Server')
assert.match(vorlage, /:beschreibung="beschreibung"/, 'REG-1a: Beschreibung wird an die Anzeige gereicht')
assert.match(formularVorlage, /v-if="beschreibung"/, 'REG-1a: ohne Beschreibung kein leerer Absatz')
assert.match(formularVorlage, /\{\{\s*beschreibung\s*\}\}/, 'REG-1a: Beschreibung als Text-Interpolation')
// Kommentare duerfen das Wort nennen („bewusst kein v-html“) — entscheidend
// ist, dass keine echte Direktive im Template steht.
const ohneKommentare = formularVorlage.replace(/<!--[\s\S]*?-->/g, '')
assert.ok(
  !/\sv-html\b/.test(ohneKommentare),
  'REG-1a: die Seite baut NIE HTML aus Serverangaben (kein v-html)',
)
// Operator-Review REG-1a, Punkt 2: Der Server speichert KLARTEXT ('Kinder < 6').
// Damit die spitzen Klammern als Zeichen erscheinen, MUSS die Anzeige escapen —
// genau das tut die Interpolation `{{ }}` (und nur sie).
assert.match(
  formularVorlage,
  /\{\{\s*beschreibung\s*\}\}/,
  'REG-1a: die Beschreibung wird interpoliert (dort escapet Vue den Klartext)',
)
assert.match(formularStil, /\.dk-pub-beschreibung/, 'REG-1a: eigener Stil fuer die Beschreibung')
assert.match(
  formularStil,
  /\.dk-pub-beschreibung[\s\S]*white-space:\s*pre-line/,
  'REG-1a: Zeilenumbrueche der Beschreibung bleiben erhalten',
)

// ── Bilder: Banner und Hintergrund ──────────────────────────────────────────

assert.match(skript, /window\.__diakronos\?\.bannerBild/, 'REG-1a: Bannerpfad vom Server')
assert.match(skript, /window\.__diakronos\?\.hintergrundBild/, 'REG-1a: Hintergrundpfad vom Server')
assert.match(vorlage, /:banner-bild="bannerBild"/, 'REG-1a: Banner wird an die Anzeige gereicht')
assert.match(formularVorlage, /v-if="bannerBild"/, 'REG-1a: Banner nur, wenn vorhanden')
assert.match(formularVorlage, /:src="bannerBild"/, 'REG-1a: Banner wird wirklich geladen')
assert.match(vorlage, /:src="hintergrundBild"/, 'REG-1a: Hintergrund wird wirklich geladen')
assert.match(
  vorlage,
  /dk-pub-hintergrund"\s+aria-hidden="true"/,
  'REG-1a: der Hintergrund ist dekorativ (aria-hidden)',
)
assert.ok(
  /alt=""/.test(vorlage),
  'REG-1a: die Bilder sind Dekoration (leerer alt-Text), kein Inhalt',
)
assert.ok(
  /alt=""/.test(formularVorlage),
  'REG-1a: auch das Banner ist Dekoration (leerer alt-Text)',
)
assert.match(stil, /\.dk-pub-hintergrund\b/, 'REG-1a: Stil des Hintergrunds')

// Keine neuen Farbwerte: nur Tokens (`var(--…)`) fuer Farben/Hintergruende.
const farben = (stil + formularStil).match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g) || []
assert.deepEqual(farben, [], 'REG-1a: keine hart codierten Farbwerte im neuen Stil')

// ── Template kompiliert (faengt Tippfehler in Bindungen) ────────────────────

assert.doesNotThrow(
  () => compileTemplate({ source: vorlage, filename: 'App.vue', id: 'reg1a-app' }),
  'REG-1a: Template der Seite kompiliert',
)
assert.doesNotThrow(
  () => compileTemplate({
    source: formularVorlage, filename: 'DkAnmeldeformular.vue', id: 'reg1a-formular',
  }),
  'REG-1a: Template der Anzeige kompiliert',
)

// Der Skript-Teil der Anzeige nennt das globale Objekt NICHT (REG-1b: die
// Vorschau im Editor setzt die Werte als Eigenschaften).
const formularSkriptOhneKommentare = formularSkript
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .split('\n').filter(z => !/^\s*(\/\/|\*)/.test(z)).join('\n')
assert.ok(
  !/window\.__diakronos/.test(formularSkriptOhneKommentare),
  'REG-1a: die Anzeige liest die Angaben als Eigenschaften, nicht global',
)
