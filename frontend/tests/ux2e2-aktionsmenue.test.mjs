/**
 * UX2e2 — Nachtrag zu UX2e: Lieder über den Papierkorb, Terminliste repariert.
 *
 * Die Karte behebt sechs Befunde aus dem Review von UX2e. Der Test prüft sie
 * am QUELLTEXT (die Seiten hängen an Vue, der API und der Kalender-Bibliothek
 * — im Node-Lauf ohne Browser gibt es sie nicht) und hält die REGELN fest,
 * die beim nächsten Umbau sonst wieder verloren gehen:
 *
 *   1. Lied „In den Papierkorb legen" = bestaetigen(loeschFrage) →
 *      musik.delete_lied → papierkorbMeldung mit „Rückgängig" →
 *      wiederherstellen('lied', …).  NICHT mehr save_lied {aktiv:false}.
 *   2. Terminliste: UX2e3 hat das „⋯" AN DER ZEILE wieder herausgenommen
 *      (Bibliothek setzt ihre Knoten bei jedem Neubau neu ein). Die Wächter
 *      prüfen jetzt, dass weder Seite noch Widget es zurückbringen.
 *   3. Enter/Space am Auslöser: preventDefault, damit der Klick nicht doppelt
 *      auslöst.
 *   4. resize-Listener wird mit DENSELBEN Optionen an- und abgemeldet.
 *   5. Gruppen-Hover hängt an der Hülle (`.gr-kachel-huelle:hover`).
 *
 * Lauf: node --test tests/ux2e2-aktionsmenue.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (name) => readFileSync(new URL(name, SRC), 'utf8')

/** Ohne Kommentare — ein Kommentar darf keinen Befund „belegen". */
const ohneKommentare = (quelle) => quelle
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/(^|[^:])\/\/[^\n]*/g, '$1')

/* ── 1 · Lieder laufen über den Papierkorb ─────────────────────────────── */

test('UX2e2 · Lied löschen: Löschfrage → delete_lied → Meldung mit Rückgängig', () => {
  const quelle = ohneKommentare(lies('pages/Lieder.vue'))
  const anfang = quelle.indexOf('async function inPapierkorb')
  assert.ok(anfang > -1, 'Lieder.vue hat inPapierkorb')
  const rumpf = quelle.slice(anfang, quelle.indexOf('\nfunction aktionenFuer', anfang))
  assert.match(rumpf, /bestaetigen\(loeschFrage\(l\.titel, 'Lied'\)\)/,
    'Rückfrage kommt aus der einen Quelle (loeschFrage), nicht handgeschrieben')
  assert.match(rumpf, /musik\.delete_lied['"]?\s*,\s*\{\s*lied:\s*l\.name\s*\}/,
    'der Server legt das Lied in den Papierkorb (delete_lied)')
  assert.doesNotMatch(rumpf, /save_lied/, 'save_lied {aktiv:false} ist der alte, falsche Weg')
  assert.doesNotMatch(rumpf, /aktiv:\s*false/, 'kein „aktiv: false" mehr')
  assert.match(rumpf, /papierkorbMeldung\(/, 'die Meldung sagt, was passiert ist')
  assert.match(rumpf, /text:\s*'Rückgängig'/, 'die Meldung bietet „Rückgängig" an')
  assert.match(rumpf, /wiederherstellen\('lied',\s*l\.name\)/,
    '„Rückgängig" holt das Lied wirklich zurück (wiederherstellen_lied)')
  // Die Importe stehen wirklich in der Datei (keine erfundene Funktion).
  assert.match(quelle, /import \{[^}]*loeschFrage[^}]*\} from '\.\.\/composables\/papierkorb\.mjs'/,
    'loeschFrage/papierkorbMeldung/wiederherstellen sind eingebunden')
})

test('UX2e2 · Lied: Weg und Wortlaut stimmen mit Beiträgen überein (eine Meldung)', () => {
  // Prinzip S4: dieselbe Wirkung, derselbe Text — geprüft am Beitrag, dem
  // Vorbild, das die Karte nennt.
  const beitrag = ohneKommentare(lies('pages/Beitraege.vue'))
  assert.match(beitrag, /bestaetigen\(loeschFrage\(post\.title, 'Beitrag'\)\)/)
  assert.match(beitrag, /text:\s*'Rückgängig'/)
  const lied = ohneKommentare(lies('pages/Lieder.vue'))
  assert.match(lied, /text:\s*'Rückgängig'/)
})

/* ── 2 · Terminliste ───────────────────────────────────────────────────── */

test('UX2e4 · Kalender: gar kein ⋯-Menü mehr (auch nicht ohne Auslöser)', () => {
  const quelle = lies('pages/Kalender.vue')
  // UX2e2 hatte das freistehende „⋯" mit `ohneAusloeser` versteckt; UX2e4 hat
  // die Terminliste ganz herausgenommen, weil das Menü an der Zeile bei jedem
  // Neubau der Bibliothek kaputtging.
  assert.doesNotMatch(quelle, /listenAktionen/, 'kein Menü-Zustand mehr in der Seite')
  assert.doesNotMatch(quelle, /@terminAktionen/, 'kein Zeilen-Ereignis mehr')
})

test('UX2e2 · DkAktionen: ohneAusloeser blendet NUR den Knopf aus, das Menü bleibt', () => {
  const quelle = lies('components/ui/DkAktionen.vue')
  assert.match(quelle, /v-if="!ohneAusloeser"/, 'der ⋯-Knopf hängt an ohneAusloeser')
  assert.match(quelle, /ohneAusloeser:\s*Boolean/, 'das Merkmal ist deklariert')
  // Das Menü selbst (Teleport) darf NICHT an der Bedingung hängen.
  const teleport = quelle.slice(quelle.indexOf('<Teleport'), quelle.indexOf('</Teleport>'))
  assert.match(teleport, /class="dk-ui-aktionen-menue"/, 'das Menü existiert weiter')
  assert.doesNotMatch(teleport, /v-if="!ohneAusloeser"/, 'das Menü bleibt bei ohneAusloeser erhalten')
})

test('UX2e2 · DkAktionen: Anker wird gemerkt und wiederverwendet (Menü an der Zeile)', () => {
  const quelle = ohneKommentare(lies('components/ui/DkAktionen.vue'))
  const oeffnen = quelle.slice(quelle.indexOf('function oeffnenBei'), quelle.indexOf('function lageWaehlen'))
  assert.match(oeffnen, /anker\s*=\s*rechteck/, 'oeffnenBei merkt das Ankerrechteck')
  const watchAnfang = quelle.indexOf('watch(offen')
  const watchBlock = quelle.slice(watchAnfang, quelle.indexOf('\n})', watchAnfang) + 3)
  assert.match(watchBlock, /lageWaehlen\(anker\)/,
    'die zweite Messung läuft am gemerkten Anker, nicht am (fehlenden) ⋯-Knopf')
  assert.doesNotMatch(quelle, /function ankerRechteck/,
    'der alte Weg über den eigenen Auslöser ist entfernt')
})

test('UX2e4 · Terminzeile: KEIN „⋯" an der Zeile (Bibliothek setzt ihre Knoten neu ein)', () => {
  const quelle = ohneKommentare(lies('components/kronos/KronosCalendar.vue'))
  // Befund UX2e3 mit echter @event-calendar/build 5.18.0: nach
  // `refetchEvents()` (auch nach Löschen) setzt die Bibliothek ihre Artikel
  // neu ein; die Hüllen aus UX2e3 landeten dann bei den falschen Zeilen.
  assert.doesNotMatch(quelle, /eventDidMount/, 'kein afterRender-Eingriff mehr in der Liste')
  assert.doesNotMatch(quelle, /eventWillUnmount/, 'auch kein Abbau-Haken mehr')
  assert.doesNotMatch(quelle, /kronos-liste-termin|kronos-liste-aktionen/,
    'keine eigenen Hüllen/Knöpfe in den Bibliotheks-Knoten')
  assert.doesNotMatch(quelle, /ResizeObserver/, 'kein Beobachter, der hängen bleiben kann')
  assert.doesNotMatch(quelle, /'terminAktionen'/, 'das Ereignis an die Seite ist weg')
  assert.doesNotMatch(quelle, /aktionenZustand/, 'die Zustandsführung der Zeile ist weg')
  // Die Liste bleibt bedienbar wie auf main: Klick auf die Zeile kommt an.
  assert.match(quelle, /eventClick:\s*\(info\)\s*=>/, 'eventClick ist weiter gemeldet')
})

test('UX2e4 · Kalender-Seite: kein Termin-Menü mehr, Klick öffnet den Dialog', () => {
  const kalender = ohneKommentare(lies('pages/Kalender.vue'))
  assert.doesNotMatch(kalender, /DkAktionen/, 'kein DkAktionen-Bauteil mehr in der Seite')
  assert.doesNotMatch(kalender, /terminAktionen/, 'kein ⋯-Ereignis mehr verdrahtet')
  assert.doesNotMatch(kalender, /listenAktionen/, 'kein Listenmenü-Zustand mehr')
  assert.doesNotMatch(kalender, /terminMenueZustand|aktionenAnker/, 'kein Anker/Zustand mehr')
  // Klick auf die Zeile → derselbe Weg wie auf main (Dialog).
  const klick = kalender.slice(kalender.indexOf('function onEventClick'), kalender.indexOf('function onDateClick'))
  assert.match(klick, /showView\.value = true/, 'Ansicht-Modus: Termin ansehen')
  assert.match(klick, /showEdit\.value = true/, 'Bearbeiten-Modus: Termin bearbeiten')
  assert.match(klick, /showEditOptions/, 'Serientermine fragen wie bisher nach dem Umfang')
})

test('UX2e4 · kronos.css führt keine Regeln für Zeilen-Knöpfe mehr', () => {
  const css = lies('kronos.css')
  assert.doesNotMatch(css, /kronos-liste-aktionen|kronos-liste-termin/,
    'die Regeln der entfernten Zeilen-Knöpfe sind mitgegangen')
  assert.doesNotMatch(css, /--kronos-aktionen-breite/, 'auch die gemessene Breite entfällt')
  // Was bleibt, ist die List-View-Lage selbst (Tages-Container nicht clippen).
  assert.match(css, /\.ec-list \.ec-day \{ overflow: visible !important;/,
    'die Listen-Regeln der Bibliothek bleiben unberührt')
})

test('UX2e2 · DkAktionen meldet seinen Zustand (offenGeaendert) — Seiten können ihn führen', () => {
  // Die Meldung selbst bleibt im Menü-Bauteil (andere Listen nutzen sie).
  const menue = ohneKommentare(lies('components/ui/DkAktionen.vue'))
  assert.match(menue, /defineEmits\(\['aktion', 'offenGeaendert'\]\)/, 'das Menü kündigt die Meldung an')
  const oeffnen = menue.slice(menue.indexOf('function oeffnenBei'), menue.indexOf('function lageWaehlen'))
  assert.match(oeffnen, /emit\('offenGeaendert', true\)/, 'beim Öffnen: true')
  const schliessen = menue.slice(menue.indexOf('function schliessen'), menue.indexOf('function ausserhalb'))
  assert.match(schliessen, /emit\('offenGeaendert', false\)/, 'beim Schließen: false')
  // UX2e4: In der TERMINLISTE gibt es den Zustand nicht mehr — der Zeilenknopf
  // ist fort (Befund UX2e3).
  const kalender = ohneKommentare(lies('pages/Kalender.vue'))
  assert.doesNotMatch(kalender, /terminMenueZustand|aktionenAnker|aktionenZustand/,
    'kein aria-expanded-Zustand der Terminzeile mehr')
  const widget = ohneKommentare(lies('components/kronos/KronosCalendar.vue'))
  assert.doesNotMatch(widget, /aktionenZustand/, 'und das Widget führt ihn nicht mehr')
  assert.equal((widget.match(/defineExpose\(/g) || []).length, 1,
    'defineExpose steht genau einmal (Vue erlaubt keinen zweiten Aufruf)')
})

test('UX2e4 · „Termin löschen" führt in der Terminliste nicht mehr über das Menü', () => {
  // Der Weg über `terminLoeschen` war nur über das (entfernte) Listenmenü
  // erreichbar. Gelöscht wird wieder wie auf main: Klick auf die Zeile →
  // Bearbeiten-Fenster (dort auch „Löschen" mit Serien-Rückfrage).
  const quelle = ohneKommentare(lies('pages/Kalender.vue'))
  assert.equal(quelle.indexOf('async function terminLoeschen'), -1,
    'die Menü-Löschfunktion ist mit dem Menü entfallen')
  assert.equal(quelle.indexOf('async function onTerminAktionen'), -1,
    'und ihr Einstieg (⋯-Klick) ebenso')
  const klick = quelle.slice(quelle.indexOf('function onEventClick'), quelle.indexOf('function onDateClick'))
  assert.match(klick, /showEditOptions/, 'Serientermine werden weiter gefragt (wie auf main)')
})

/* ── 3 · Enter/Space am Auslöser ───────────────────────────────────────── */

test('UX2e2 · Enter und Leertaste öffnen, ohne den Klick ein zweites Mal auszulösen', () => {
  const quelle = ohneKommentare(lies('components/ui/DkAktionen.vue'))
  const block = quelle.slice(quelle.indexOf('function amAusloeser'), quelle.indexOf('function oeffnenFuerZeile'))
  assert.match(block, /const oeffnend/, 'die öffnenden Tasten stehen zusammen')
  assert.match(block, /ereignis\.preventDefault\(\)/, 'preventDefault gilt für ALLE öffnenden Tasten')
  // Vorher nur für ArrowDown/Kontextmenü — Enter/Space schickten zusätzlich
  // einen Klick und schlossen das Menü sofort wieder.
  assert.doesNotMatch(block, /if \(ereignis\.key === 'ArrowDown' \|\| istKontextmenueTaste\(ereignis\)\) ereignis\.preventDefault\(\)/,
    'das alte, zu enge preventDefault ist ersetzt')
})

/* ── 4 · Listener-Optionen ─────────────────────────────────────────────── */

test('UX2e2 · Listener werden mit identischen Optionen an- und abgemeldet', () => {
  const quelle = ohneKommentare(lies('components/ui/DkAktionen.vue'))
  // Optionen einmal als Konstante — An- und Abmelden können nicht auseinanderlaufen.
  assert.match(quelle, /const RESIZE_OPTIONEN = \{[^}]*\}/, 'resize-Optionen sind eine Konstante')
  assert.match(quelle, /const SCROLL_OPTIONEN = \{[^}]*capture: true[^}]*\}/, 'scroll-Optionen mit capture')
  const anmeldungen = [...quelle.matchAll(/addEventListener\('(resize|scroll)', ([^,]+), ([^)]+)\)/g)]
    .map((m) => [m[1], m[3].trim()])
  const abmeldungen = [...quelle.matchAll(/removeEventListener\('(resize|scroll)', ([^,]+), ([^)]+)\)/g)]
    .map((m) => [m[1], m[3].trim()])
  assert.ok(anmeldungen.length >= 2, 'resize und scroll werden angemeldet')
  for (const [art, optionen] of anmeldungen) {
    const passend = abmeldungen.filter(([a2, o2]) => a2 === art && o2 === optionen)
    assert.ok(passend.length >= 1,
      `${art}: Abmelden mit denselben Optionen (${optionen}) — sonst bleibt der Listener stehen`)
  }
  // Insbesondere NICHT mehr das alte `{ capture: true }` gegen `{ passive: true }`.
  assert.doesNotMatch(quelle, /removeEventListener\('resize', onScroll, \{ capture: true \}\)/,
    'das Leck ({capture:true} gegen {passive:true}) ist behoben')
})

/* ── 5 · Gruppen-Hover ─────────────────────────────────────────────────── */

test('UX2e2 · Gruppenkachel: Hover/Fokus hängen an der Hülle', () => {
  const quelle = ohneKommentare(lies('pages/Gruppen.vue'))
  assert.match(quelle, /\.gr-kachel-huelle:hover \.gr-kachel-aktionen/,
    'Hover an der Hülle (der ⋯-Knopf ist ein Geschwister des Links)')
  assert.match(quelle, /\.gr-kachel-huelle:focus-within \.gr-kachel-aktionen/,
    'Fokus ebenso an der Hülle')
  assert.doesNotMatch(quelle, /\.gr-kachel:hover \.gr-kachel-aktionen/,
    'die wirkungslose Regel am Link ist ersetzt')
})
