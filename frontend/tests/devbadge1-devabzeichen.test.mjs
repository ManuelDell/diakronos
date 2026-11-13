/**
 * DEVBADGE-1 — Wächter: das Dev-Abzeichen („Dev-Modus an“) verdeckt am Handy
 * kein Bedienelement mehr und drängt den Seitentitel nicht weg
 * (Karte t_2df971b3, Nacharbeit nach Review 11.11.).
 *
 * BEFUND (Live dev.ecg-hn.de 10.11., Review A10-N3): In der Handy-Lage
 * (`.dk-app--handy`) stand das Abzeichen unten rechts auf dem Knopf „Termin
 * anlegen“ (FAB, Kalender) bzw. über der unteren Leiste. Ein Versuch in
 * A10-N3 (unten links / oben 44 px) brachte NEUE Kollisionen (Kopfzeile
 * 56 px, Avatar in Listen, Desktop über dem Benutzer-Avatar) und einen
 * 8×8-px-Treffer.
 *
 * ENTSCHEIDUNG NACH MESSUNG (tools/demo/devbadge1-abnahme.mjs, 360/375/390
 * hell und dunkel, Seiten Start · Mitglieder · Gruppen · Kalender): die in
 * der Karte zuerst vorgeschlagene Plakette „oben rechts unter der Kopfzeile“
 * war NICHT frei — auf dem Kalender liegt dort der Kopf des Mobil-Kalenders
 * (`.dk-mobilkopf`, Werkzeuge rechts bis 382 px). Gewählt wurde deshalb die
 * zweite von der Karte erlaubte Form: „als Eintrag im Kopf/Menü (dann kein
 * schwebendes Element)“. Der Knopf steht in der Handy-Lage im Slot
 * `dev-knopf` der App-Kopfzeile — als 44×44-px-Feld mit Punkt, ohne Wort
 * (Review Punkt 2: die Wortform quetschte den Titel auf „Kaler…“). Desktop
 * bleibt unten rechts mit dem vollen Text „Dev-Modus an“ (main).
 *
 * Geprüft wird in drei Schritten:
 *
 *   A  Quelltext: Desktop-Grundlage (DevStart.vue), die Kopfzeilen-Form
 *      (`dk-dev-start--kopf`), die Verankerung in App.vue/AppTopbar, den
 *      Vorlesename (enthält den sichtbaren Text) und die Sichtbarkeits-
 *      Bedingung (kein Einschaltknopf neben laufender Sitzung).
 *
 *   B  Rechnung: in der Handy-Lage ist der Knopf ein ELEMENT DER KOPFZEILE
 *      (kein fixed/absolute) — er kann per Konstruktion kein Bedienelement
 *      überdecken. Deshalb wird gerechnet, was die Karte verlangt: 44 px
 *      Treffer, kein `position: fixed`, und der Desktop bleibt unten rechts
 *      mit 26 px Höhe (main).
 *
 *   B4/B5 (DEVBADGE-1b, Review Opus): Die Kopfzeilen- und FAB-Anpassungen,
 *      die es NUR wegen des Dev-Eintrags gibt, hängen an `.dk-app--dev`
 *      (App.vue setzt die Klasse nur bei sichtbarem Dev-Eintrag). Ohne
 *      Dev-Modus ist die Oberfläche der main-Stand.
 *
 *   C  Layout-Messung (optional, `DEVBADGE1_BASE=http://127.0.0.1:15980`):
 *      im echten Browser werden die Trefferflächen (Knöpfe, Links, Felder)
 *      der Seiten Start, Mitglieder, Gruppen, Kalender bei 360, 375 und 390
 *      hell/dunkel gegen das Abzeichen gemessen; JEDE Überschneidung ist ein
 *      Fehler, und der Seitentitel muss mit „…“ kürzen (nicht hart
 *      abschneiden). Ohne Umgebungsvariable wird dieser Teil mit Begründung
 *      übersprungen — der Build läuft ohne laufenden Server.
 *
 * Läuft im Frontend-Stage des Docker-Builds (siehe `tests/testliste.txt`).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const QUELLE = path.join(HIER, '..', 'src', 'diakonos', 'components', 'devmodus', 'DevStart.vue')

function lies() {
  return readFileSync(QUELLE, 'utf8')
}

/** Den CSS-Block zu einem Wähler holen (erste Fundstelle, bis zur schließenden Klammer). */
function regel(css, waehler) {
  const start = css.indexOf(waehler + ' {')
  assert.ok(start >= 0, `Regel ${waehler} fehlt`)
  const ende = css.indexOf('}', start)
  return css.slice(start, ende + 1)
}

// ══════════════════════════════════════════════════════════════════════════
// A · Quelltext
// ══════════════════════════════════════════════════════════════════════════
test('DEVBADGE-1 · A1: Desktop bleibt unten rechts (Grundlage main)', () => {
  const css = lies()
  const block = regel(css, '.dk-dev-start')
  assert.match(block, /position:\s*fixed/, 'schwebend')
  assert.match(block, /right:\s*10px/, 'Desktop unten rechts (main)')
  assert.match(block, /bottom:\s*10px/, 'Desktop unten rechts (main)')
  // Keine unsichtbare Zone über dem Knopf (der Befund aus A10-N3).
  assert.ok(!/pointer-events:\s*none/.test(block), 'keine unsichtbare Trefferzone')
  assert.ok(!/dk-app--handy/.test(block), 'Grundblock trägt keine Handy-Regel')
})

test('DEVBADGE-1 · A2: Handy — Eintrag im Kopf, 44-px-Treffer, kein schwebendes Element', () => {
  const css = lies()
  const block = regel(css, '.dk-dev-start--kopf')
  assert.match(block, /position:\s*static/, 'kein schwebendes Element (Karte: Eintrag im Kopf)')
  assert.match(block, /min-width:\s*var\(--treffer-handy\)/, '44 px breit (K4)')
  assert.match(block, /min-height:\s*var\(--treffer-handy\)/, '44 px hoch (K4)')
  // Review 11.11. Punkt 2: feste 44-px-Kante — der Platz in der Kopfzeile ist
  // genau die Trefferfläche, kein wachsender Text (der Titel braucht den Platz).
  assert.match(block, /width:\s*var\(--treffer-handy\)/, 'feste Breite 44 px')
  assert.match(block, /height:\s*var\(--treffer-handy\)/, 'feste Höhe 44 px')
  assert.match(block, /right:\s*auto/, 'fester Anker aufgehoben')
  assert.match(block, /bottom:\s*auto/, 'fester Anker aufgehoben')
  assert.ok(!/pointer-events:\s*none/.test(block), 'keine unsichtbare Zone')
  const tokens = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'tokens.css'), 'utf8')
  assert.match(tokens, /--treffer-handy:\s*44px/, '--treffer-handy ist 44 px')
})

test('DEVBADGE-1 · A2b: verankert in App.vue (Slot `dev-knopf`) und AppTopbar', () => {
  const app = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'App.vue'), 'utf8')
  // EIN Knopf, zwei Orte: am Handy im Kopf-Slot, am Desktop im festen Rahmen.
  assert.match(app, /<template #dev-knopf>\s*<DevStart :im-kopf="true" \/>\s*<\/template>/,
    'Knopf steht im Kopf-Slot und SAGT es sich selbst (`im-kopf`)')
  // Review 11.11. Punkt 1: BEIDE Stellen hängen an derselben Bedingung —
  // nicht an `devmodusVerfuegbar` allein (sonst stand der Knopf neben dem
  // laufenden Dev-Rahmen und ein Klick startete die Sitzung erneut).
  // DEVBADGE-1b (Review Opus, Punkt 3): In der Einrichtung (Vollbild ohne
  // Kopfzeile, also ohne Kopf-Slot) behält der Knopf die schwebende Form —
  // sonst wäre er am Handy dort gar nicht erreichbar (main hatte ihn).
  assert.match(app, /<DevStart v-if="devStartZeigen && \(!istHandyLage \|\| isVollbildMode\)" \/>/,
    'Desktop und Einrichtung behalten den festen Knopf, an `devStartZeigen` gebunden')
  assert.match(app, /:dev-knopf="devStartZeigen && istHandyLage"/,
    'der Platz in der Kopfzeile entsteht nur mit Knopf')
  assert.match(app, /const devStartZeigen = computed\(\(\) => devmodusVerfuegbar\.value && !devmodusAn\.value\)/,
    'eine gemeinsame Bedingung: verfügbar UND keine laufende Sitzung')
  assert.ok(!/:dev-knopf="devmodusVerfuegbar/.test(app),
    'kein zweiter Weg an der Bedingung vorbei')
  assert.ok(!/<DevStart v-if="devmodusVerfuegbar/.test(app),
    'kein zweiter Weg an der Bedingung vorbei')
  // `istHandyLage` ist dieselbe Quelle wie die Gerüst-Klasse (DEV-B6).
  assert.match(app, /const \{ istHandyLage \} = useHandyLage\(\)/, 'eine Quelle der Handy-Lage')
  // Der Knopf steht als EIGENES Element mit eigenem `v-if` und ist nicht an
  // eine `v-else-if`-Kette des Rahmens gebunden: `devStartZeigen` schließt
  // die laufende Sitzung aus, damit sind Knopf und Dev-Rahmen ohnehin nie
  // gleichzeitig sichtbar. (Ein pauschales „Slot-Inhalt rendert in einem
  // `v-else-if`-Zweig nicht“ wäre unbelegt und steht hier deshalb NICHT als
  // Begründung — Review Opus, Punkt 4.)
  assert.ok(!/<DevStart v-else-if/.test(app),
    'kein DevStart in einem v-else-if-Zweig (eigene Bedingung statt Kette)')
  const topbar = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'components', 'AppTopbar.vue'), 'utf8')
  assert.match(topbar, /<div v-if="devKnopf" class="dk-topbar-dev">\s*<slot name="dev-knopf" \/>\s*<\/div>/,
    'AppTopbar hat den Platz am Ende der Kopfzeile, über `devKnopf` geschaltet')
  assert.match(topbar, /devKnopf: \{ type: Boolean, default: false \}/, 'Eigenschaft `devKnopf` deklariert')
})

test('DEVBADGE-1 · A2c: die Kopfzeilen-Form hängt an einer KLASSE, nicht am eigenen CSS-Zweig', () => {
  // Die Komponente steht an zwei Orten (App.vue und AppTopbar.vue). Welche
  // Regeln eines Bausteins Vite ein- oder ausklammert, ist von hier aus nicht
  // eindeutig zu belegen — ein Lage-Raten im CSS wäre also unsicher. Die Form
  // hängt deshalb an einer Klasse, die der Aufrufer setzt (nachprüfbar).
  const dev = lies()
  assert.match(dev, /defineProps\(\{\s*imKopf: \{ type: Boolean, default: false \},?\s*\}\)/,
    'Eigenschaft `imKopf` deklariert')
  assert.match(dev, /:class="\{ 'dk-dev-start--kopf': imKopf \}"/, 'Klasse folgt der Eigenschaft')
  // Nur das SKRIPT prüfen (Kommentare dürfen `matchMedia` erwähnen).
  const skript = dev.slice(dev.indexOf('<script setup>'), dev.indexOf('</script>'))
  assert.ok(!/matchMedia/.test(skript), 'die Komponente rät die Lage nicht selbst (kein matchMedia)')
})

test('DEVBADGE-1 · A3: „Dev-Modus an“ erscheint, wo Platz ist (Text-Knoten statt none)', () => {
  const css = lies()
  const vorlage = css.slice(0, css.indexOf('<style'))
  assert.match(vorlage, /<span class="dk-dev-start-text">Dev-Modus an<\/span>/,
    'Text steht im Knopf')
  // Der alte Fehler: `.dk-dev-start-text { display: none }` im Grundblock —
  // ein späterer Block konnte ihn nicht mehr aufheben.
  const textBlock = regel(css, '.dk-dev-start-text')
  assert.ok(!/display:\s*none/.test(textBlock),
    'kein display:none am Text im Grundblock')
  // Am Handy steht nur der Punkt (Review Punkt 2: Platz für den Titel) …
  const kopfText = regel(css, '.dk-dev-start--kopf .dk-dev-start-text')
  assert.match(kopfText, /display:\s*none/, 'am Handy steht die Wortform nicht')
  // … und es gibt keine zweite Kurzform-Plakette, die den Titel breit macht.
  assert.ok(!/dk-dev-start-kurz/.test(vorlage), 'keine Kurzform-Plakette mehr (Review Punkt 2)')
})

test('DEVBADGE-1 · A4: Vorlesename enthält den sichtbaren Text (WCAG 2.5.3)', () => {
  // Review 11.11. Punkt 3: aria-label „Dev-Modus einschalten“ überschrieb den
  // sichtbaren Text „Dev-Modus an“ — der Vorlesename MUSS ihn enthalten.
  const dev = lies()
  const vorlage = dev.slice(0, dev.indexOf('<style'))
  const treffer = /const VORLESENAME = '([^']+)'/.exec(dev)
  assert.ok(treffer, 'Vorlesename ist eine Konstante')
  assert.ok(treffer[1].startsWith('Dev-Modus an'),
    `Vorlesename beginnt mit dem sichtbaren Text (ist: „${treffer[1]}“)`)
  assert.match(vorlage, /:aria-label="VORLESENAME"/, 'Vorlesename am Knopf')
  // Kein festes aria-label mehr, das den sichtbaren Text überschreibt.
  assert.ok(!/aria-label="Dev-Modus einschalten"/.test(vorlage), 'altes Label ersetzt')
})

// ══════════════════════════════════════════════════════════════════════════
// A (Fortsetzung) · Quelltext: Sichtbarkeits-Bedingung, Ladezustand
// ══════════════════════════════════════════════════════════════════════════
test('DEVBADGE-1 · A5: kein Einschaltknopf, solange eine Dev-Sitzung läuft (Review Punkt 1)', () => {
  // Befund: der Knopf hing nur an `devmodusVerfuegbar`; bei laufender Sitzung
  // standen Dev-Rahmen UND Knopf gleichzeitig da (Desktop unten rechts, Handy
  // in der Kopfzeile) und ein zweiter Klick rief `sitzungStarten` erneut auf.
  const app = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'App.vue'), 'utf8')
  // Die Bedingung nennt BEIDE Teile: verfügbar und NICHT an.
  assert.match(app, /devmodusVerfuegbar\.value && !devmodusAn\.value/,
    '`devStartZeigen` schließt die laufende Sitzung aus')
  // … und beide Knopf-Stellen benutzen sie (kein `devmodusVerfuegbar` mehr).
  const vorlagenTeil = app.slice(0, app.indexOf('<script setup>'))
  const alle = [...vorlagenTeil.matchAll(/(?:v-if|:dev-knopf)="([^"]*)"/g)].map((m) => m[1])
  const knopfBedingungen = alle.filter((wert) => /devStartZeigen/.test(wert))
  assert.deepEqual(knopfBedingungen,
    ['devStartZeigen && istHandyLage', 'devStartZeigen && (!istHandyLage || isVollbildMode)'],
    'beide Knopf-Stellen hängen an `devStartZeigen`')
  assert.ok(!alle.some((wert) => /^devmodusVerfuegbar/.test(wert)),
    'keine Stelle hängt noch direkt an `devmodusVerfuegbar`')
  // Der Dev-Rahmen hängt weiter an `devmodusAn` (unverändert main).
  assert.match(app, /<DevRahmen v-if="devmodusAn" \/>/, 'Rahmen bei laufender Sitzung')
})

test('DEVBADGE-1b · A6: der Ladezustand ist sichtbar (kein toter Knoten)', () => {
  // Review Opus, Punkt 5: `.dk-dev-start-laeuft` stand mit `display: none` im
  // CSS — der Ladezustand `laeuft` war nie zu sehen. Jetzt trägt der PUNKT
  // den Zustand (hohl + Puls), `aria-busy` meldet ihn der Vorlesehilfe.
  const dev = lies()
  // Nur die Vorlage/CSS zaehlen — der Kommentar oben nennt den alten Namen.
  const ohneKommentar = dev.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.ok(!/dk-dev-start-laeuft/.test(ohneKommentar), 'der immer unsichtbare Knoten ist weg')
  const vorlage = dev.slice(0, dev.indexOf('<style'))
  assert.match(vorlage, /:aria-busy="laeuft \? 'true' : 'false'"/, 'Ladezustand am Knopf gemeldet')
  const punkt = regel(dev, '.dk-dev-start[aria-busy="true"] .dk-dev-start-punkt')
  assert.match(punkt, /background:\s*transparent/, 'Punkt wird hohl (sichtbarer Ladezustand)')
  assert.match(punkt, /outline:\s*2px solid var\(--dev-rot\)/, 'Ring statt Füllung (kein Verschieben)')
  assert.match(punkt, /animation:\s*dk-dev-start-puls/, 'Puls als Rückmeldung')
  // Doppelklick-Schutz bleibt (ein zweiter Klick startet nichts erneut).
  const skript = dev.slice(dev.indexOf('<script setup>'), dev.indexOf('</script>'))
  assert.match(skript, /if \(laeuft\.value\) return/, 'Doppelklick-Schutz unverändert')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Rechnung: kein schwebendes Element am Handy, Desktop wie main
//     (B4/B5 stehen bewusst VOR C — C misst optional im Browser)
// ══════════════════════════════════════════════════════════════════════════
const BASIS = process.env.DEVBADGE1_BASE || ''
const BREITEN = [360, 375, 390]
test('DEVBADGE-1 · B1: Handy — der Knopf fließt im Kopf, überdeckt nichts (auch nicht den FAB)', () => {
  const css = lies()
  const grund = regel(css, '.dk-dev-start')
  const kopf = regel(css, '.dk-dev-start--kopf')
  // Grundform ist schwebend (Desktop) …
  assert.match(grund, /position:\s*fixed/)
  // … die Kopfzeilen-Form ausdrücklich NICHT. Damit gibt es am Handy kein
  // Rechteck mehr, das über dem Inhalt liegen könnte — die Lösung des
  // Befunds ist strukturell, nicht durch Abstandsrechnung.
  assert.match(kopf, /position:\s*static/)
  assert.ok(!/z-index:\s*2\d{6}/.test(kopf), 'kein Overlay-Stapel mehr am Handy')
  // DEVBADGE-1b (Review Opus, Punkt 6): Der frühere Handy-Abstand der festen
  // Form war toter Code und ist entfernt — es gibt ihn nicht mehr, auch nicht
  // als Leichnam. (Der Kommentar oben NENNT die alte Regel, deshalb Kommentare
  // vor der Suche entfernen.) Die feste Form steht am Handy seit DEVBADGE-1b
  // nur noch in der EINRICHTUNG (Vollbild, ohne Kopfzeile und ohne untere
  // Leiste, Punkt 3) — dort gilt der main-Abstand `bottom: 10px`.
  const cssPutz = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.ok(!/\.dk-dev-start:not\(\.dk-dev-start--kopf\)\s*\{/.test(cssPutz),
    'tote Handy-Regel der festen Form ist entfernt (Review Punkt 6)')
  assert.ok(!/@media \(max-width: 480px\)/.test(css),
    'keine reine Breiten-Regel mehr (Review Punkt 7)')
})

test('DEVBADGE-1 · B2: Desktop 1440 — main-Lage unten rechts, 26 px hoch', () => {
  const css = lies()
  const grund = regel(css, '.dk-dev-start')
  const rechts = Number(grund.match(/right:\s*(\d+)px/)[1])
  const unten = Number(grund.match(/bottom:\s*(\d+)px/)[1])
  assert.equal(rechts + unten, 20, 'unten rechts wie auf main (10 px Abstand)')
  // Höhe ergibt sich aus Polsterung 5 + Zeile 16 = 26 px (main, gemessen).
  assert.match(grund, /padding:\s*5px 9px/)
  assert.match(grund, /box-shadow:\s*var\(--dev-flaeche-schatten\)/, 'Plakette mit Schatten (main)')
})

test('DEVBADGE-1 · B3: am 1440-Desktop überdeckt das Abzeichen den Bearbeiten-Knopf nicht', () => {
  // Im Wegwerf-Stack gemessen (1440, hell und dunkel): das Dev-Abzeichen
  // (118×26 bei 10/10 unten rechts) schnitt den Bearbeiten-FAB der Übersicht
  // (48×48 bei 24/24) auf 48×12 px — der Punkt lag über dem Knopf. Dessen
  // Abstand nach oben wächst deshalb um die Werkzeug-Höhe — ABER nur, wenn
  // das Dev-Abzeichen da ist (`.dk-app--dev`, DEVBADGE-1b Review Punkt 2);
  // die Lage des Abzeichens bleibt die main-Lage (Karte: „Desktop unten
  // rechts bleibt“).
  const css = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'index.css'), 'utf8')
  // OHNE Dev-Eintrag: main-Stand (24 px Rand).
  const fab = regel(css, '.dk-widget-edit-fab')
  assert.match(fab, /bottom:\s*24px/, 'ohne Dev-Eintrag main-Stand (24 px)')
  assert.match(fab, /right:\s*24px/, 'ohne Dev-Eintrag main-Stand (24 px)')
  // MIT Dev-Eintrag: der Knopf weicht dem Abzeichen aus.
  const fabDev = regel(css, '.dk-app--dev .dk-widget-edit-fab')
  assert.match(fabDev, /bottom:\s*calc\(var\(--sp-5\) \+ var\(--control-h\) - var\(--sp-1\)\)/,
    'Bearbeiten-Knopf weicht dem Abzeichen aus (nur im Dev-Modus)')
  assert.match(fabDev, /right:\s*var\(--sp-5\)/, 'rechter Rand als Token (UX1a)')
  // 24 + 40 − 4 = 60 px: Abzeichen 26 px hoch bei 10 px Rand → oben 36 px.
  // Der Knopf endet bei 60 px — 24 px Luft, keine Überschneidung.
  const unten = 24 + 40 - 4
  assert.ok(unten > 10 + 26, `Knopf-Unterkante (${unten} px) liegt über dem Abzeichen`)
})

// ══════════════════════════════════════════════════════════════════════════
// B (Fortsetzung) · Kopfzeile: mit Dev-Eintrag weicht die Rolle, ohne Dev main
// ══════════════════════════════════════════════════════════════════════════
test('DEVBADGE-1 · B4: am Handy weicht nicht der Seitentitel, sondern das Rollen-Abzeichen', () => {
  // Gemessen (390 px, Kalender mit „Moderator“): Titel braucht 62 px, bekam 39.
  // Ursache war nicht nur der Dev-Eintrag, sondern die volle Rollen-Plakette
  // (78 px). Deshalb: knapper Kopf-Rand, knappe Plakette, und unter 390 px
  // weicht das Abzeichen ganz (dort passt beides nicht).
  // DEVBADGE-1b (Review Opus, Punkt 1): Alles davon gilt NUR mit sichtbarem
  // Dev-Eintrag (`.dk-app--dev`) — ohne ihn ist das der main-Stand.
  const css = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'index.css'), 'utf8')
  assert.match(css, /\.dk-app--dev\.dk-app--handy \.dk-topbar \{ padding: 0 var\(--sp-3\); \}/,
    'MIT Dev-Eintrag: Handy-Kopf hat 12 px Rand (statt 20 px)')
  // UX1a (DEVBADGE-1c): der 2-px-Wert ist jetzt ein Tokens-Ausdruck (gleicher
  // Wert) — die Zeichenkette ist deshalb ein Muster aus `calc(var(--sp-1) / 2)`.
  assert.match(css, /\.dk-app--dev\.dk-app--handy \.dk-topbar-rolle \.dk-ui-badge \{\s*font-size: var\(--fs-12\);\s*padding: calc\(var\(--sp-1\) \/ 2\) var\(--sp-1\);/,
    'MIT Dev-Eintrag: Rollen-Plakette in knapper Form (12 px statt 14 px)')
  assert.match(css, /@media \(max-width: 389\.98px\) \{\s*\.dk-app--dev\.dk-app--handy \.dk-topbar-rolle \{ display: none; \}/,
    'MIT Dev-Eintrag: unter 390 px weicht das Abzeichen ganz (kein halbes Wort)')
  // Der Titel kürzt mit „…“ — ABER nur mit Dev-Eintrag (Review Opus, 2. Runde:
  // ohne Dev-Modus war `text-overflow` an ALLE vergeben).
  assert.match(css, /\.dk-app--dev\.dk-app--handy \.dk-crumb-current \{[\s\S]*?text-overflow: ellipsis;/,
    'MIT Dev-Eintrag kürzt der Titel mit „…“ statt hart abzuschneiden')
})

test('DEVBADGE-1b · B5: ohne Dev-Eintrag bleibt der Handy-Kopf der main-Stand', () => {
  // Review Opus, Punkt 1 (zweite Runde): Rand 20→12 px, knappe Rollen-Plakette
  // und das Ausblenden unter 390 px galten für ALLE Handy-Nutzer. Dazu kamen
  // `.dk-crumbs { flex: 0 1 auto; overflow: hidden }` und
  // `.dk-crumb-current { nowrap/ellipsis/min-width: 0 }` — gemessen blieb damit
  // ohne Dev-Modus die Plakette an der Suche kleben und der Titel bekam
  // „…“, während main die Plakette hinter dem Titel setzt. Alle fünf
  // Regeln hängen jetzt an `.dk-app--dev`; die Gegenprobe belegt, dass keine
  // Regel ohne diese Klasse übrig bleibt (sonst wäre main still verändert).
  // Kommentare fliegen raus — sie NENNEN die alten Regeln (Begruendung).
  const css = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'index.css'), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
  for (const [was, muster] of [
    // Anker `(^|[\n;{}])` + optionaler Einrueckung: die Regel muss als
    // EIGENER Waehler beginnen. Ohne Anker traefe die Suche auch die
    // gewollte `.dk-app--dev.dk-app--handy …` (die Zeichenkette steckt darin).
    ['Kopf-Rand', /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-topbar \{/],
    ['Krumen-Kasten (schrumpfend)', /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-crumbs \{[^}]*flex: 0 1 auto/],
    ['Titel-Beschnitt', /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-crumb-current \{[^}]*ellipsis/],
    ['Rollen-Plakette (knapp)', /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-topbar-rolle \.dk-ui-badge \{/],
    ['Rollen-Plakette (aus)', /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-topbar-rolle \{ display: none; \}/],
    ['Rollen-Plakette (schrumpfend)', /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-topbar-rolle \{ flex: 0 0 auto/],
  ]) {
    assert.ok(!muster.test(css), `${was}: Regel ohne Dev-Bedingung gefunden (main würde verändert)`)
  }
  // Und main-Stand ist POSITIV nachweisbar: der Kasten ist `flex: 1 1 auto`
  // (Beschnitt und `nowrap` bleiben dem Dev-Fall vorbehalten).
  assert.match(css, /(?:^|[;{}\n])\s*\.dk-app--handy \.dk-crumbs \{ gap: var\(--sp-1\); flex: 1 1 auto; min-width: 0; \}/,
    'ohne Dev: Krumen-Kasten wie main (flex: 1 1 auto)')
  // Die Klasse hängt NUR am sichtbaren Dev-EINTRAG (Einschaltknopf) — nicht am
  // laufenden Rahmen (dann gibt es keinen Eintrag in Kopf/unten rechts) und
  // nicht an der bloßen Verfügbarkeit (die bleibt bei laufender Sitzung wahr).
  const app = readFileSync(path.join(HIER, '..', 'src', 'diakonos', 'App.vue'), 'utf8')
  assert.match(app, /'dk-app--dev': devStartZeigen/, "die Gerüst-Klasse hängt an `devStartZeigen`")
  assert.ok(!/devSichtbar/.test(app),
    'kein Zwischen-computed, das den laufenden Rahmen mitzählt (Review Punkt 2)')
  assert.ok(!/'dk-app--dev': (devmodusVerfuegbar|devmodusAn)/.test(app),
    'nicht an Verfügbarkeit/laufendem Rahmen')
  // Die Einrichtungs-Seite (#/einrichtung) hat keine Kopfzeile — dort muss der
  // feste Knopf bleiben, sonst fehlt der Dev-Einstieg am Handy ganz
  // (Review Punkt 3).
  assert.match(app, /<DevStart v-if="devStartZeigen && \(!istHandyLage \|\| isVollbildMode\)" \/>/,
    'in der Einrichtung ist der Dev-Knopf wieder erreichbar')
})

// ══════════════════════════════════════════════════════════════════════════
// C · Layout-Messung im Browser (optional)
// ══════════════════════════════════════════════════════════════════════════
test('DEVBADGE-1 · C: Abzeichen schneidet auf Start/Mitglieder/Gruppen/Kalender kein Bedienelement',
  { skip: BASIS ? false : 'kein laufender Stack (DEVBADGE1_BASE nicht gesetzt)' },
  async () => {
    const { chromium } = await import('playwright')
    const browser = await chromium.launch()
    const bericht = []
    try {
      for (const breite of BREITEN) {
        for (const thema of ['light', 'dark']) {
          for (const [seite, pfad] of [
            ['start', '/#/'], ['mitglieder', '/#/mitglieder'],
            ['gruppen', '/#/gruppen'], ['kalender', '/#/kalender'],
          ]) {
            const ctx = await browser.newContext({
              viewport: { width: breite, height: 844 }, isMobile: true, hasTouch: true,
              deviceScaleFactor: 2, colorScheme: thema,
            })
            const page = await ctx.newPage()
            await page.goto(BASIS + '/login', { waitUntil: 'domcontentloaded' })
            await page.fill('#dk-usr, input[name="usr"]', process.env.DEVBADGE1_USER || 'admin@example.org')
            await page.fill('#dk-pwd, input[name="pwd"]', process.env.DEVBADGE1_PASS || 'musterhausen-demo')
            await page.click('button[type="submit"]')
            await page.waitForURL((u) => !String(u).includes('/login'), { timeout: 60000 })
            await page.goto(BASIS + pfad, { waitUntil: 'domcontentloaded' })
            await page.waitForTimeout(2500)
            const treffer = await page.evaluate(() => {
              const badge = document.querySelector('.dk-dev-start')
              if (!badge) return { fehlt: true, kollisionen: [] }
              const a = badge.getBoundingClientRect()
              const kollisionen = []
              for (const el of document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]')) {
                if (el === badge || badge.contains(el) || el.contains(badge)) continue
                const st = getComputedStyle(el)
                if (st.display === 'none' || st.visibility === 'hidden' || st.pointerEvents === 'none') continue
                const b = el.getBoundingClientRect()
                if (b.width < 1 || b.height < 1) continue
                if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) {
                  kollisionen.push({
                    el: el.tagName.toLowerCase() + '.' + (el.className || '').toString().split(' ')[0],
                    text: (el.innerText || el.value || '').trim().slice(0, 40),
                    rect: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
                  })
                }
              }
              // Review Punkt 2: der Seitentitel darf nicht HART abgeschnitten
              // werden — er kürzt mit „…“ (scrollWidth ≤ clientWidth + 1).
              const titel = document.querySelector('.dk-crumb-current')
              let titelAbschnitt = null
              if (titel) {
                titelAbschnitt = {
                  text: titel.textContent.trim(),
                  breite: Math.round(titel.getBoundingClientRect().width),
                  passt: titel.scrollWidth <= titel.clientWidth + 1,
                  ellipsis: getComputedStyle(titel).textOverflow,
                }
              }
              return {
                rect: [Math.round(a.left), Math.round(a.top), Math.round(a.width), Math.round(a.height)],
                handy: document.querySelector('.dk-app').classList.contains('dk-app--handy'),
                text: badge.innerText.trim(),
                kollisionen,
                titel: titelAbschnitt,
              }
            })
            bericht.push({ breite, seite, thema, ...treffer })
            assert.ok(!treffer.fehlt, `${breite}/${seite}: Abzeichen fehlt`)
            assert.ok(treffer.handy, `${breite}/${seite}: Handy-Lage nicht aktiv`)
            assert.equal(treffer.rect[2], 44, `${breite}/${seite}/${thema}: Trefferfläche nicht 44 px breit`)
            assert.equal(treffer.rect[3], 44, `${breite}/${seite}/${thema}: Trefferfläche nicht 44 px hoch`)
            assert.deepEqual(treffer.kollisionen, [], `${breite}/${seite}/${thema}: Überschneidung mit Bedienelement`)
            if (treffer.titel) {
              assert.equal(treffer.titel.ellipsis, 'ellipsis', `${breite}/${seite}: Titel kürzt mit „…“`)
            }
            await ctx.close()
          }
        }
      }
    } finally {
      await browser.close()
      console.log(JSON.stringify(bericht, null, 2))
    }
  })
