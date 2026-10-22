/**
 * P2-2 — Dunkelmodus und Barrierefreiheit (DES-R1, R2, R3, R4, R6, R15, R18,
 * R19, R20, DES-03, DES-06, DES-08, DES-09) plus Nachtrag R-P1-12.
 *
 * Der Test prueft die QUELLE. Die Bedien-Abnahme (Kontrast, Fokus,
 * Screenshots hell/dunkel) laeuft im isolierten Teststack im echten Browser.
 *
 * Alle Asserts waren vor der Behebung rot:
 *   R1  Theme nur am .dk-app  -> Teleports an <body> blieben hell
 *   R2  kein --ec-*-Override
 *   R3  outline:none + feste Markenfarbe als Fokus
 *   R4  --dk-brand-* im Dunkelmodus weiter auf dunkles Navy
 *   R6  DkModal/Eigenbauten ohne Fokusfuehrung
 *   R18 kein Sprunglink
 *   R19 keine verknuepften Beschriftungen
 *   R20 gleichlautende Meldungsnamen
 *   R-P1-12 @media print ohnehin nur die Haelfte der Papierwerte
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')

const app = lies('App.vue')
const tokens = lies('tokens.css')
const index = lies('index.css')
const kronos = lies('kronos.css')
const dkModal = lies('components/DkModal.vue')
const dkWarning = lies('components/DkWarning.vue')
const stammdaten = lies('components/planrahmen/PrStammdatenPanel.vue')
const bottomNav = lies('components/AppBottomNav.vue')
const eventCreate = lies('components/kronos/KronosEventCreate.vue')
const fokus = lies('composables/useDialogFokus.js')
const prAnsicht = lies('components/planrahmen/PrAnsicht.vue')
const prMeldungen = lies('components/planrahmen/PrMeldungen.vue')

// ── DES-R1: Theme am Wurzelelement ─────────────────────────────────────────
assert.match(app, /document\.documentElement\.setAttribute\('data-theme'/,
  'DES-R1: App.vue setzt data-theme nicht am documentElement')
assert.match(app, /watch\(theme,[\s\S]{0,160}immediate: true/,
  'DES-R1: das Theme wird nicht beim Start angewendet (localStorage)')
assert.match(tokens, /:root\[data-theme="dark"\]/,
  'DES-R1: tokens.css kennt :root[data-theme="dark"] nicht')

// ── DES-R2: Terminkalender-Raster ──────────────────────────────────────────
for (const vari of ['--ec-bg-color', '--ec-border-color', '--ec-today-bg-color',
  '--ec-event-bg-color', '--ec-color']) {
  assert.ok(kronos.includes(vari + ':'), `DES-R2: ${vari} fehlt in kronos.css`)
}
// Die Bibliothek setzt ihre eigenen --ec-*-Werte NACH kronos.css mit gleicher
// Spezifitaet; deshalb muss der Override ueber `.ec` hinausgehen, sonst bleibt
// das Raster weiss (heller Text auf weissem Papier).
assert.ok(!/^\.ec\s*\{/m.test(kronos),
  'DES-R2: die Ueberschreibung steht wieder auf .ec (verliert gegen die Bibliothek)')
assert.match(kronos, /html\[data-theme\]\s+\.ec[\s\S]{0,400}--ec-bg-color:\s*var\(--surface\)/,
  'DES-R2: --ec-bg-color zeigt nicht spezifisch auf --surface')

// ── DES-R3: zentraler Fokus ────────────────────────────────────────────────
assert.match(index, /:focus-visible\s*\{[\s\S]{0,160}outline:\s*2px solid var\(--focus-ring\)/,
  'DES-R3: kein zentraler :focus-visible-Ring in index.css')
assert.ok(!/\.dk-form-input:[a-z-]*focus[^{]*\{[^}]*--dk-brand-500/.test(index),
  'DES-R3: Feld-Fokus nutzt weiter die feste Markenfarbe')
assert.ok(!/\.dk-toolbar-search input:focus\s*\{/.test(index),
  'DES-R3: Einzelregel fuer das Suchfeld ist nicht entfernt')
assert.ok(!/\.dk-form-input[^{]*\{[^}]*outline:\s*none/.test(index),
  'DES-R3: Eingabefelder schalten den Fokus weiter mit `outline: none` ab')

// ── DES-R4: Markenfarben im Dunkelmodus ────────────────────────────────────
assert.match(tokens, /\[data-theme="dark"\],\s*\n:root\[data-theme="dark"\]\s*\{[\s\S]{0,400}--dk-brand-500:\s*var\(--dk-navy-200\)/,
  'DES-R4: --dk-brand-500 bleibt im Dunkelmodus auf dunklem Navy')

// ── DES-R15: Kontrast ─────────────────────────────────────────────────────
assert.match(tokens, /--dk-warm-400:\s*#6b7088/, 'DES-R15: --subtle ist nicht abgedunkelt')
for (const token of ['--badge-ink-warn', '--badge-ink-ok', '--badge-ink-info', '--event-ink']) {
  const treffer = tokens.split(new RegExp('\\' + token + ':')).length - 1
  assert.ok(treffer >= 2, `DES-R15: ${token} fehlt in einem der beiden Themes`)
}
assert.match(kronos, /\.ec-event:not\(\.ec-event-dot-style\)\s*\{[\s\S]{0,80}color:\s*var\(--event-ink\)/,
  'DES-R15: Terminkacheln nutzen nicht die lesbare Schriftfarbe')
const dkBadge = lies('components/ui/DkBadge.vue')
assert.match(dkBadge, /dk-ui-badge--akzent\s*\{[^}]*color:\s*var\(--badge-ink-warn\)/,
  'DES-R15: Gold-Abzeichen hat weiter 2,34:1')

// ── DES-R6: Dialoge ───────────────────────────────────────────────────────
assert.match(fokus, /export function useDialogFokus/, 'DES-R6: useDialogFokus fehlt')
assert.match(fokus, /e\.key === 'Escape'/, 'DES-R6: Esc schliesst nicht')
assert.match(fokus, /e\.key !== 'Tab'/, 'DES-R6: keine Tab-Falle')
for (const [name, quelle] of [
  ['DkModal.vue', dkModal], ['DkWarning.vue', dkWarning],
  ['PrStammdatenPanel.vue', stammdaten], ['AppBottomNav.vue', bottomNav],
  ['KronosEventCreate.vue', eventCreate],
]) {
  assert.match(quelle, /useDialogFokus\(/, `DES-R6: ${name} fuehrt den Fokus nicht`)
}
assert.match(eventCreate, /role="dialog"[\s\S]{0,80}aria-modal="true"/,
  'DES-R6: KronosEventCreate hat keine Dialogrolle')

// ── DES-R5: Karten und Zeilen sind Links ──────────────────────────────────
const gruppen = lies('pages/Gruppen.vue')
const mitglieder = lies('pages/Mitglieder.vue')
const lieder = lies('pages/Lieder.vue')
const adressbuch = lies('pages/Adressbuch.vue')
assert.match(gruppen, /<a[\s\S]{0,200}class="gr-kachel"[\s\S]{0,120}:href="'#\/gruppe\/' \+ g\.name"/,
  'DES-R5: Gruppen-Kacheln sind keine Links')
assert.ok(!/@click="\(\) => \{ navigate\('#\/gruppe\/'/.test(gruppen),
  'DES-R5: Klick-Handler der Kacheln ist nicht entfernt')
assert.ok(!/boxShadow=/.test(gruppen), 'DES-03: Inline-Hover-Handler nicht entfernt')
assert.match(index, /a\.gr-kachel:hover\s*\{[^}]*box-shadow:\s*var\(--shadow-md\)/,
  'DES-03: Kachel-Schatten kommt nicht aus dem Theme')
assert.match(mitglieder, /<a[\s\S]{0,120}class="dk-member-card"[\s\S]{0,80}:href="'#\/mitglied\/' \+ m\.name"/,
  'DES-R5: Mitglieder-Karte ist kein Link')
assert.match(lieder, /:href="'#\/lieder\/' \+ encodeURIComponent\(l\.name\)"/,
  'DES-R5: Lieder-Zeile/Karte ist kein Link')
assert.match(adressbuch, /class="dk-zellen-link"[\s\S]{0,80}:href="'#\/mitglied\/' \+ m\.name"/,
  'DES-R5: Adressbuch-Zeile ist kein Link')

// ── DES-09: Gruppenbilder mit Alternativtext ──────────────────────────────
const gruppenBilder = gruppen.split('<img').slice(1)
assert.ok(gruppenBilder.length >= 2, 'DES-09: Gruppenbilder nicht gefunden')
for (const bild of gruppenBilder) {
  assert.match(bild.slice(0, 120), /:alt="g\.gruppenname"/, 'DES-09: Gruppenbild ohne alt')
}

// ── DES-06: Knoepfe mit Namen ─────────────────────────────────────────────
const ressourcen = lies('pages/Ressourcen.vue')
assert.match(ressourcen, /aria-label="Offene Anfragen aktualisieren"/, 'DES-06: Aktualisieren ohne Namen')
assert.match(ressourcen, /aria-label="Detailansicht schliessen"/, 'DES-06: Schliessen ohne Namen')
assert.match(ressourcen, /aria-label="Meine Buchungen schliessen"/, 'DES-06: Schliessen ohne Namen')

// ── DES-08: Initialen-Paare aus Tokens ───────────────────────────────────
assert.match(mitglieder, /--dk-avatar-\d-bg/, 'DES-08: keine Avatar-Paare verwendet')
const sidebar = lies('components/AppSidebar.vue')
// P3-4b/B1: Der Anzeigename (OP-HANDY-25) speist seit P3-4 die Initialen —
// das Kürzel muss unverändert aus den Token-Paaren kommen (DES-08).
assert.match(sidebar, /:style="avatarStil\(anzeigeName \|\| user\.fullname\)"/, 'DES-08: Seitenleiste ohne Paar-Farben')
assert.ok(!/\{ background: avatarColor, color: 'var\(--primary-ink\)' \}/.test(sidebar),
  'DES-08: Initialen nutzen weiter --primary-ink')

// ── DES-R18: Sprunglink ───────────────────────────────────────────────────
assert.match(app, /class="dk-sprunglink"[\s\S]{0,120}Zum Inhalt springen/,
  'DES-R18: Sprunglink fehlt')
assert.match(app, /id="dk-inhalt"[\s\S]{0,120}tabindex="-1"/,
  'DES-R18: Ziel #dk-inhalt ist nicht fokussierbar')
assert.match(index, /\.dk-sprunglink\s*\{[\s\S]{0,600}transform:\s*translateY\(-200%\)/,
  'DES-R18: Sprunglink ist immer sichtbar')
assert.match(index, /\.dk-sprunglink:focus-visible\s*\{\s*transform:\s*translateY\(0\)/,
  'DES-R18: Sprunglink wird bei Fokus nicht eingeblendet')

// ── DES-R19: verknuepfte Beschriftungen ──────────────────────────────────
const liedBearbeiten = lies('components/lieder/LiedBearbeiten.vue')
assert.ok(liedBearbeiten.split('v-slot="feld"').length - 1 >= 8,
  'DES-R19: Liedbearbeiten nutzt die Feld-Kennungen nicht')
assert.match(liedBearbeiten, /:id="feld\.id"/, 'DES-R19: Feld-Kennung nicht gesetzt')
assert.match(lieder, /id="ld-filter-gruppe"[\s\S]{0,60}v-model="filters\.gruppe"/,
  'DES-R19: Filter „Gruppe“ ohne verknuepfte Beschriftung')
assert.match(lieder, /aria-label="Lieder durchsuchen"/, 'DES-R19: Suchfeld ohne Namen')
assert.match(adressbuch, /id="ab-suche"/, 'DES-R19: Adressbuch-Suchfeld ohne Kennung')
const kalenderImport = lies('pages/KalenderImport.vue')
assert.ok(kalenderImport.split('v-slot="feld"').length - 1 >= 5,
  'DES-R19: Kalender-Import nutzt die Feld-Kennungen nicht')
const dkSelect = lies('components/ui/DkSelect.vue')
assert.match(dkSelect, /:id="id \|\| undefined"/, 'DES-R19: DkSelect reicht die Kennung nicht durch')

// ── DES-R20: unterscheidbare Namen ───────────────────────────────────────
assert.match(prMeldungen, /bezeichnung/,
  'DES-R20: die Meldungszeile kennt keine Bezeichnung')
assert.match(prMeldungen, /aria-label="kompaktName"/, 'DES-R20: kompakte Zeile ohne eigenen Namen')
const prTabelle = lies('components/planrahmen/PrTabelle.vue')
assert.match(prTabelle, /:bezeichnung="zeileBezeichnung\(t\)"/,
  'DES-R20: Plan-Tabelle nennt das Datum nicht')
assert.match(lies('components/planrahmen/PrRaster.vue'), /:bezeichnung="datumText\(t\.datum\)"/,
  'DES-R20: Raster nennt das Datum nicht')

// ── Nachtrag R-P1-12: Druck im Dunkelmodus ──────────────────────────────
assert.match(prAnsicht, /html\[data-theme="dark"\][\s\S]{0,400}--text:\s*var\(--druck-text\)/,
  'R-P1-12: @media print erzwingt die hellen Papierwerte nicht')
assert.match(prAnsicht, /\.pr-tabelle td[\s\S]{0,300}background:\s*transparent !important/,
  'R-P1-12: Zellhintergruende sind im Druck nicht transparent')
assert.match(tokens, /--druck-bg:\s*var\(--dk-warm-0\)/, 'R-P1-12: Papier-Token fehlt')

console.log('P2-2 Dunkelmodus/Barrierefreiheit: Regeln vollstaendig verdrahtet')
