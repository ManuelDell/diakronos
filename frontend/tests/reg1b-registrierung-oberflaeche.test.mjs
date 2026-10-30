/**
 * REG-1b — Registrierung Oberflaeche: Startdatum, Vorschau, Bilder, Beschreibung.
 *
 * Geprueft wird der Frontend-Teil der Karte:
 *
 *   (1) Link-Dialog   : Feld „Gültig ab“ steht neben Enddatum/Limit, die
 *                       Linkkarte zeigt es, der Zustand „bevorstehend“ wird
 *                       angezeigt (nicht als „aktiv“ verschwiegen).
 *   (2) Formular-Editor: Beschreibung, Banner und Hintergrund — inklusive
 *                       Upload über den vorhandenen Weg (`upload_file`) und
 *                       dem Entfernen (`bilder_entfernen`).
 *   (3) Vorschau      : Knopf im Editor, gezeigt wird DIESELBE Komponente wie
 *                       auf der oeffentlichen Seite (`DkAnmeldeformular.vue`),
 *                       ohne Absenden.
 *   (4) Oeffentliche Seite: Beschreibung/Banner/Hintergrund kommen vom Server;
 *                       das Bild macht den Text nicht unlesbar (deckende
 *                       Karte + Schleier, keine hart codierten Farben).
 *
 * Der Test kompiliert die SFCs echt (vue/compiler-sfc) statt am Quelltext zu
 * raten. Laeuft im Docker-Build ueber `node --test`.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const seite = new URL('../src/diakonos/', import.meta.url)
const oeffentlich = new URL('../src/registrierung/', import.meta.url)
const lies = (wurzel, p) => readFileSync(new URL(p, wurzel), 'utf8')

// ── Gemeinsame Anzeige: eine Komponente fuer beide Seiten ──────────────────

const formularQuelle = lies(oeffentlich, 'components/DkAnmeldeformular.vue')
const formular = parse(formularQuelle, { filename: 'DkAnmeldeformular.vue' })
assert.deepEqual(formular.errors, [], 'DkAnmeldeformular.vue: SFC-Struktur')
compileScript(formular.descriptor, { id: 'reg1b-formular' })

const formularSkript = formular.descriptor.scriptSetup.content
const formularVorlage = formular.descriptor.template.content
const formularStil = formular.descriptor.styles.map(s => s.content).join('\n')

// Vorschau-Modus: abgeschaltet absenden, sichtbarer Hinweis.
assert.match(formularSkript, /vorschau:\s*\{\s*type:\s*Boolean/, 'REG-1b: `vorschau` ist eine Eigenschaft')
assert.match(formularVorlage, /dk-pub-vorschau-hinweis/, 'REG-1b: Hinweis im Vorschau-Modus fehlt')
assert.match(
  formularVorlage,
  /:disabled="vorschau"/,
  'REG-1b: der Absende-Knopf ist in der Vorschau abgeschaltet',
)
assert.match(
  formularSkript,
  /function absenden\(\)[\s\S]{0,120}if \(props\.vorschau\) return/,
  'REG-1b: in der Vorschau wird nie abgeschickt',
)
// Die Anzeige liest NICHT selbst aus dem globalen Objekt — sonst zeigte die
// Vorschau die Werte der oeffentlichen Seite statt die des Editors. Nur der
// Code zaehlt, nicht der erklaerende Kommentar.
const formularSkriptOhneKommentare = formularSkript
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .split('\n').filter(z => !/^\s*(\/\/|\*)/.test(z)).join('\n')
assert.ok(
  !/window\.__diakronos/.test(formularSkriptOhneKommentare),
  'REG-1b: die Anzeige liest nicht aus window.__diakronos (Daten als Eigenschaften)',
)
// Beschreibung bleibt reiner Text.
const formularOhneKommentare = formularVorlage.replace(/<!--[\s\S]*?-->/g, '')
assert.ok(!/\sv-html\b/.test(formularOhneKommentare), 'REG-1b: kein v-html in der Anzeige')
assert.match(formularVorlage, /\{\{\s*beschreibung\s*\}\}/, 'REG-1b: Beschreibung als Text-Interpolation')
assert.match(formularVorlage, /v-if="beschreibung"/, 'REG-1b: ohne Beschreibung kein leerer Absatz')
assert.match(formularVorlage, /v-if="bannerBild"/, 'REG-1b: Banner nur, wenn vorhanden')
assert.match(formularVorlage, /:src="bannerBild"/, 'REG-1b: Banner wird geladen')

assert.doesNotThrow(
  () => compileTemplate({ source: formularVorlage, filename: 'DkAnmeldeformular.vue', id: 'reg1b-formular' }),
  'REG-1b: Template der gemeinsamen Anzeige kompiliert',
)

// Keine hart codierten Farbwerte (nur Tokens).
const farben = formularStil.match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g) || []
assert.deepEqual(farben, [], 'REG-1b: keine hart codierten Farbwerte in der Anzeige')

// ── (4) Oeffentliche Seite benutzt genau diese Komponente ─────────────────

const oeffQuelle = lies(oeffentlich, 'App.vue')
const oeff = parse(oeffQuelle, { filename: 'App.vue' })
assert.deepEqual(oeff.errors, [], 'App.vue: SFC-Struktur')
compileScript(oeff.descriptor, { id: 'reg1b-app' })
const oeffSkript = oeff.descriptor.scriptSetup.content
const oeffVorlage = oeff.descriptor.template.content
const oeffStil = oeff.descriptor.styles.map(s => s.content).join('\n')

assert.ok(
  oeffSkript.includes("from './components/DkAnmeldeformular.vue'"),
  'REG-1b: die oeffentliche Seite laedt die gemeinsame Anzeige',
)
assert.ok(oeffVorlage.includes('<DkAnmeldeformular'), 'REG-1b: die gemeinsame Anzeige wird eingebunden')
assert.ok(
  !oeffVorlage.includes('<DkAnmeldeformular\n                vorschau'),
  'REG-1b: die oeffentliche Seite zeigt die Anzeige NICHT im Vorschau-Modus',
)
// Angaben kommen weiterhin vom Server (window.__diakronos).
assert.match(oeffSkript, /window\.__diakronos\?\.beschreibung/, 'REG-1b: Beschreibung kommt vom Server')
assert.match(oeffSkript, /window\.__diakronos\?\.bannerBild/, 'REG-1b: Bannerpfad vom Server')
assert.match(oeffSkript, /window\.__diakronos\?\.hintergrundBild/, 'REG-1b: Hintergrundpfad vom Server')
assert.match(oeffVorlage, /:src="hintergrundBild"/, 'REG-1b: Hintergrund wird wirklich geladen')
assert.match(
  oeffVorlage,
  /dk-pub-hintergrund"\s+aria-hidden="true"/,
  'REG-1b: der Hintergrund ist dekorativ (aria-hidden)',
)
assert.match(oeffVorlage, /alt=""/, 'REG-1b: die Bilder sind Dekoration (leerer alt-Text)')
assert.match(oeffVorlage, /:beschreibung="beschreibung"/, 'REG-1b: Beschreibung wird durchgereicht')
assert.match(oeffVorlage, /:banner-bild="bannerBild"/, 'REG-1b: Banner wird durchgereicht')

// Bild darf den Text nicht unlesbar machen: deckende Karte + Schleier.
assert.match(oeffStil, /\.dk-pub-card\s*\{[\s\S]*?background:\s*var\(--surface\)/, 'REG-1b: Karte bleibt deckend')
assert.match(oeffStil, /\.dk-pub-page--mit-bild::before/, 'REG-1b: Schleier ueber dem Hintergrundbild fehlt')
assert.match(
  oeffStil,
  /\.dk-pub-page--mit-bild::before\s*\{[\s\S]*?color-mix\(in oklch, var\(--bg\)/,
  'REG-1b: der Schleier nutzt einen Token (kein neuer Farbwert)',
)
const oeffFarben = oeffStil.match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g) || []
assert.deepEqual(oeffFarben, [], 'REG-1b: keine hart codierten Farbwerte in der Seite')

// ── (1) Startdatum: Link-Dialog und Linkkarte ─────────────────────────────

const regQuelle = lies(seite, 'pages/Registrierung.vue')
const reg = parse(regQuelle, { filename: 'Registrierung.vue' })
assert.deepEqual(reg.errors, [], 'Registrierung.vue: SFC-Struktur')
compileScript(reg.descriptor, { id: 'reg1b-reg' })
const regVorlage = reg.descriptor.template.content
const regSkript = reg.descriptor.scriptSetup.content
const dialogLink = regVorlage.slice(regVorlage.indexOf('reg-link-form'), regVorlage.indexOf('Dialog: Formular erstellen'))
assert.ok(dialogLink.length > 0, 'REG-1b: Link-Dialog nicht gefunden')
// „Gültig ab“ steht im Dialog — vor „Gültig bis“ (Anfang vor Ende).
assert.ok(dialogLink.includes('label="Gültig ab"'), 'REG-1b: Feld „Gültig ab“ fehlt im Link-Dialog')
assert.ok(
  dialogLink.indexOf('label="Gültig ab"') < dialogLink.indexOf('label="Gültig bis"'),
  'REG-1b: „Gültig ab“ steht vor „Gültig bis“ (Zeitraum in Leserichtung)',
)
assert.ok(dialogLink.includes('newLink.gueltig_ab'), 'REG-1b: „gültig ab“ ist an das Formular gebunden')
assert.match(regSkript, /gueltig_ab:\s*''/, 'REG-1b: leeres „gültig ab“ = sofort (Vorbelegung)')
// Der Server bekommt es mitgeschickt (create_link kennt `gueltig_ab`).
assert.match(regSkript, /create_link[\s\S]{0,200}nutzlast/, 'REG-1b: der Link-Dialog sendet die Eingaben')

// Linkkarte zeigt den Zeitraum und den Zustand „bevorstehend“.
assert.ok(regVorlage.includes('Gültig ab:'), 'REG-1b: die Linkkarte zeigt „Gültig ab“')
assert.ok(regVorlage.includes('Gültig bis:'), 'REG-1b: die Linkkarte zeigt „Gültig bis“')
assert.match(regSkript, /case 'bevorstehend':\s*return 'Startet später'/, 'REG-1b: Zustand „bevorstehend“ fehlt')
assert.match(regSkript, /case 'bevorstehend':\s*return 'info'/, 'REG-1b: Farbe des Zustands fehlt')

// ── (2) Formular-Editor: Beschreibung, Banner, Hintergrund ────────────────

const dialogFormular = regVorlage.slice(
  regVorlage.indexOf('reg-formular-form'),
  regVorlage.indexOf('Dialog: Link verlaengern'),
)
assert.ok(dialogFormular.length > 0, 'REG-1b: Formular-Dialog nicht gefunden')
assert.ok(
  dialogFormular.includes('data-test="reg-formular-beschreibung"'),
  'REG-1b: Feld „Beschreibung“ fehlt im Formular-Editor',
)
assert.match(dialogFormular, /v-model="newFormular\.beschreibung"/, 'REG-1b: Beschreibung ist gebunden')
// Banner und Hintergrund kommen aus EINER Schleife ueber `bildFelder`; die
// Kennungen der beiden Felder entstehen also dynamisch aus der Rolle.
assert.match(dialogFormular, /v-for="bild in bildFelder"/, 'REG-1b: Bildfelder fehlen im Editor')
for (const rolle of ['banner', 'hintergrund']) {
  assert.ok(
    dialogFormular.includes(`data-test="\`reg-formular-\${bild.rolle}-datei\`"`),
    `REG-1b: Kennung der Dateiauswahl („${rolle}“) fehlt`,
  )
}
assert.ok(
  dialogFormular.includes('-entfernen`"'),
  'REG-1b: Entfernen-Knopf fuer die Bilder fehlt',
)
assert.match(
  regSkript,
  /rolle: 'banner'[\s\S]{0,900}rolle: 'hintergrund'/,
  'REG-1b: die beiden Bildrollen (Banner/Hintergrund) sind nicht angelegt',
)
// Upload laeuft ueber DENSELBEN Weg wie ueberall (upload_file, Multipart) und
// nur erzeugte Dateinamen sind zuordenbar (Backend: `pruefe_bilddatei`).
assert.match(regSkript, /fetch\('\/api\/method\/upload_file'/, 'REG-1b: Upload nutzt den vorhandenen Endpunkt')
assert.match(regSkript, /X-Frappe-CSRF-Token/, 'REG-1b: Upload ohne CSRF-Kopf')
assert.ok(regSkript.includes('banner_bild_datei'), 'REG-1b: Banner-Dateiname wird nicht mitgegeben')
assert.ok(regSkript.includes('hintergrund_bild_datei'), 'REG-1b: Hintergrund-Dateiname wird nicht mitgegeben')
assert.ok(regSkript.includes('bilder_entfernen'), 'REG-1b: Entfernen wird dem Server nicht gemeldet')
// Beschreibung und Bilder werden beim Bearbeiten geladen — sonst waeren sie
// beim Speichern leer und wuerden stillschweigend geloescht.
assert.match(
  regSkript,
  /formularBearbeiten[\s\S]{0,1200}beschreibung: daten\?\.beschreibung/,
  'REG-1b: Bearbeiten laedt die Beschreibung nicht',
)
assert.match(
  regSkript,
  /formularBearbeiten[\s\S]{0,1600}daten\?\.banner_bild_url/,
  'REG-1b: Bearbeiten laedt das Banner nicht',
)

// ── (3) Vorschau: Knopf, Dialog, gleiche Komponente, kein Absenden ────────

assert.ok(regSkript.includes("from '../../registrierung/components/DkAnmeldeformular.vue'"),
  'REG-1b: der Editor laedt nicht die gemeinsame Anzeige')
assert.ok(dialogFormular.includes('data-test="reg-formular-vorschau"'), 'REG-1b: Vorschau-Knopf fehlt')
assert.match(regSkript, /function vorschauOeffnen\(\)/, 'REG-1b: Vorschau wird nicht geoeffnet')
assert.ok(
  regSkript.includes('registrierung_vorschau.get_formular_vorschau'),
  'REG-1b: die Vorschau holt ihre Daten nicht vom Server',
)
const vorschauBlock = regVorlage.slice(regVorlage.indexOf('reg-vorschau-overlay'))
assert.ok(vorschauBlock.length > 0, 'REG-1b: Vorschau-Bereich fehlt im Template')
assert.ok(vorschauBlock.includes('<DkAnmeldeformular'), 'REG-1b: die Vorschau zeigt nicht die gemeinsame Anzeige')
assert.match(vorschauBlock, /\n\s+vorschau\n/, 'REG-1b: die Vorschau steht nicht im Vorschau-Modus')
assert.match(
  vorschauBlock,
  /:beschreibung="vorschauDaten\.beschreibung/,
  'REG-1b: die Vorschau zeigt die Beschreibung nicht',
)
assert.match(
  vorschauBlock,
  /:banner-bild="vorschauDaten\.banner_bild/,
  'REG-1b: die Vorschau zeigt das Banner nicht',
)
// Die Vorschau muss auch ungespeicherte Eingaben zeigen (Editor schickt sie mit).
assert.match(
  regSkript,
  /vorschauOeffnen[\s\S]{0,900}beschreibung: newFormular\.value\.beschreibung/,
  'REG-1b: die Vorschau ignoriert ungespeicherte Angaben',
)

// ── Importpfad wirklich aufloesen (der Build hat ihn gebraucht) ───────────
{
  const treffer = regSkript.match(/from '([^']*DkAnmeldeformular\.vue)'/)
  assert.ok(treffer, 'REG-1b: Import der gemeinsamen Anzeige fehlt')
  const ziel = new URL(treffer[1], new URL('pages/Registrierung.vue', seite))
  assert.ok(existsSync(ziel), `REG-1b: Importpfad zeigt ins Leere: ${treffer[1]}`)
}

// ── Verdrahtung der Bild-/Vorschau-Stile (nur Tokens) ─────────────────────

const regStil = reg.descriptor.styles.map(s => s.content).join('\n')
const neueStile = regStil.slice(regStil.indexOf('REG-1b'))
assert.ok(neueStile.length > 0, 'REG-1b: Stile fehlen')
const neueFarben = neueStile.match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g) || []
assert.deepEqual(neueFarben, [], 'REG-1b: keine hart codierten Farbwerte in den neuen Stilen')

console.log('REG-1b: alle Prüfungen bestanden')
