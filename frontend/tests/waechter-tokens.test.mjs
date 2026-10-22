/**
 * WÄCHTER-TEST — keine festen Farbwerte in den neuen Bereichen.
 *
 * Zweck: `tokens.css` ist die einzige Quelle für Farben. Komponenten und
 * Seiten dürfen deshalb keine festen Farbwerte (#hex, rgb(), hsl()) mehr
 * tragen, sondern nur `var(--…)`.
 *
 * Geprüft werden .vue-Dateien unter:
 *   - src/diakonos/pages/planrahmen/
 *   - src/diakonos/components/planrahmen/
 *   - src/diakonos/components/ui/
 *   - HARTE_DATEIEN (siehe unten): Bereiche, die DS2 auf das Design-System
 *     umgestellt hat (Kronos-Kalender/Termine/Moderation + Dienstplan,
 *     Kalenderimport, Ressourcen sowie DS2b: Diakonos-Rest, Musik, Verwaltung,
 *     App-Rahmen und die Public-Apps Gast/Registrierung/Organigramm).
 *
 * Ausnahmen (mit Begründung) stehen in AUSNAHMEN. Dateien ausserhalb dieser
 * Bereiche werden NUR GEZÄHLT und im Bericht ausgegeben (den Abbau
 * übernimmt DS2) — sie brechen diesen Test nicht.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test).
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
// Die eigenständigen Oberflächen (Verwaltung + Public-Apps) liegen NICHT unter
// src/diakonos/, nutzen aber dasselbe Token-System. Eigene Wurzel für sie.
const WURZEL_SRC = new URL('../src/', import.meta.url)
const GEPRUEFTE_BEREICHE = ['pages/planrahmen/', 'components/planrahmen/', 'components/ui/']

// Dateien ausserhalb der Bereiche, die DS2 bereits HART umgestellt hat.
// (Ziel am Ende beider DS2-Karten: 0 Altdateien im Bericht.)
const HARTE_DATEIEN = [
  // DS2a (Kronos-Kalender/Termine/Moderation + Dienstplan/Kalenderimport/Ressourcen)
  'components/kronos/KronosEventCreate.vue',
  'components/kronos/KronosEventEdit.vue',
  'components/kronos/KronosEventView.vue',
  'components/kronos/KronosMiniCalendar.vue',
  'components/kronos/KronosSidebar.vue',
  'components/kronos/KronosTopbar.vue',
  'components/kronos/ModerationCard.vue',
  'components/kronos/ModerationModals.vue',
  'components/kronos/ModerationSidebar.vue',
  'pages/Dienstplan.vue',
  'pages/KalenderImport.vue',
  'pages/Moderation.vue',
  'pages/Ressourcen.vue',

  // DS2b (Diakonos-Rest, Musik, Verwaltung, App-Rahmen) — relativ zu src/diakonos/
  'components/AppBottomNav.vue',
  'components/AppSidebar.vue',
  'pages/Beitraege.vue',
  'pages/GruppeDetail.vue',
  'pages/LiedDetail.vue',
  'pages/LiedgruppeDetail.vue',
  'pages/MitgliedDetail.vue',
  'pages/Mitglieder.vue',
  'components/gruppen/OrganigrammAnsicht.vue',
  'pages/Profile.vue',
  'pages/Registrierung.vue',
  'pages/Wiki.vue',
]

// DS2b-Dateien AUSSERHALB von src/diakonos/ (relativ zu src/) — Verwaltung und
// die eigenständigen Public-Apps (Gast/Registrierung/Organigramm) mit eigenem Entry.
const HARTE_DATEIEN_SRC = [
  'gast/App.vue',
  'organigramm/App.vue',
  'registrierung/App.vue',
]

// Feste Farbe: #rgb/#rrggbb/#rrggbbaa, rgb()/rgba(), hsl()/hsla()
// (auch die Kurzform rgb(255,255,255) innerhalb color-mix()).
const FARB_MUSTER = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g

// Dateien, die feste Farben tragen dürfen — mit Begründung.
const AUSNAHMEN = new Map([
  // `<input type="color">` verlangt einen rohen Hex-Wert; ein Token
  // (`var(--…)`) wäre dort kein gültiger Feldwert. Die Google-Blau-Vorgabe
  // '#4285F4' ist nur der Startwert des Farbwählers und wird von der
  // Server-Antwort (cal.backgroundColor) überschrieben, sobald vorhanden.
  // Bewusste, begründete Ausnahme (DS3).
  ['pages/KalenderImport.vue', 'Google-Farbwähler braucht Hex-Startwert (#4285F4)'],
])

function quelldateien(verzeichnis) {
  const pfad = new URL(verzeichnis, WURZEL)
  if (!existsSync(pfad)) return []
  const ergebnis = []
  for (const name of readdirSync(pfad)) {
    if (name === 'node_modules') continue
    const kind = new URL(name, pfad)
    if (statSync(kind).isDirectory()) ergebnis.push(...quelldateien(verzeichnis + name + '/'))
    else if (name.endsWith('.vue')) ergebnis.push(verzeichnis + name)
  }
  return ergebnis
}

function findeFarben(text) {
  const treffer = []
  const zeilen = text.split('\n')
  for (let i = 0; i < zeilen.length; i++) {
    const zeile = zeilen[i]
    FARB_MUSTER.lastIndex = 0
    let m
    while ((m = FARB_MUSTER.exec(zeile)) !== null) {
      treffer.push({ zeile: i + 1, wert: m[0].trim() })
    }
  }
  return treffer
}

// ── Geprüfte Bereiche: hier MUSS es sauber sein ────────────────────────────
const verstoesse = []
let geprueft = 0
const zuPruefen = [
  ...GEPRUEFTE_BEREICHE.flatMap(quelldateien).map(d => [WURZEL, d]),
  ...HARTE_DATEIEN.map(d => [WURZEL, d]),
  ...HARTE_DATEIEN_SRC.map(d => [WURZEL_SRC, d]),
]
for (const [wurzel, datei] of zuPruefen) {
  if (AUSNAHMEN.has(datei)) continue
  geprueft++
  const text = readFileSync(new URL(datei, wurzel), 'utf8')
  for (const f of findeFarben(text)) {
    verstoesse.push(`${datei}:${f.zeile}  →  ${f.wert}`)
  }
}

assert.ok(geprueft > 0, 'Es wurden Dateien gefunden, die geprüft werden können')
assert.deepEqual(
  verstoesse, [],
  'Feste Farbwerte verboten — bitte var(--…) aus tokens.css verwenden:\n' +
    verstoesse.join('\n'),
)

// ── Bericht: Altdateien ausserhalb der neuen Bereiche ─────────────────────
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

const hartGesetzt = new Set([...GEPRUEFTE_BEREICHE.flatMap(quelldateien), ...HARTE_DATEIEN])
const altdateienMitFarbe = []
let altdateienGesamt = 0
for (const datei of [...alleVue('pages/'), ...alleVue('components/')]) {
  if (hartGesetzt.has(datei)) continue
  altdateienGesamt++
  const text = readFileSync(new URL(datei, WURZEL), 'utf8')
  if (findeFarben(text).length) altdateienMitFarbe.push(datei)
}

console.log('Wächter-Tokens: bestanden')
console.log(`  geprüfte .vue-Dateien (neu/DS2-hart): ${geprueft}`)
console.log(`  Verstöße: ${verstoesse.length}`)
console.log(`  Bericht Altdateien ausserhalb (DS2): ${altdateienMitFarbe.length} von ${altdateienGesamt} tragen feste Farben`)

// ── DS3 · SINGLE SOURCE OF TRUTH: keine Token-WERT-Kopien ────────────────
// tokens.css ist die einzige Quelle für Farbwerte. Deshalb darf AUSSERHALB
// von tokens.css keine CSS-Variable einen rohen Farbwert (#hex, rgb(), hsl())
// direkt zugewiesen bekommen (`--x: #fafaf8`). Erlaubt sind nur Verweise
// (`--x: var(--y)`) und bewusst begründete Ausnahmen (INPUT_FARBWERTE).
// Die Public-Entries Gast/Registrierung/Organigramm importieren tokens.css —
// auch dort sind Wert-Kopien verboten.
const WERT_MUSTER = /--[\w-]+\s*:\s*(#[0-9a-fA-F]{3,8}\b|rgba?\s*\(|hsla?\s*\()/
// Dateien mit einem echten `<input type="color">`-Startwert (roher Hex nötig).
const INPUT_FARBWERTE = new Set(['diakonos/pages/KalenderImport.vue'])
const QUELLDATEIEN = /\.(vue|js|mjs|css)$/

function alleQuellen(verzeichnis) {
  const pfad = new URL(verzeichnis, WURZEL_SRC)
  if (!existsSync(pfad)) return []
  const ergebnis = []
  for (const name of readdirSync(pfad)) {
    if (name === 'node_modules') continue
    const kind = new URL(name, pfad)
    if (statSync(kind).isDirectory()) ergebnis.push(...alleQuellen(verzeichnis + name + '/'))
    else if (QUELLDATEIEN.test(name)) ergebnis.push(verzeichnis + name)
  }
  return ergebnis
}

const tokWertVerstoesse = []
let tokWertGeprueft = 0
for (const datei of alleQuellen('')) {
  if (datei === 'diakonos/tokens.css') continue           // die einzige Quelle
  if (INPUT_FARBWERTE.has(datei)) continue                // begründete Ausnahme
  tokWertGeprueft++
  const text = readFileSync(new URL(datei, WURZEL_SRC), 'utf8')
  text.split('\n').forEach((zeile, i) => {
    if (WERT_MUSTER.test(zeile)) tokWertVerstoesse.push(`${datei}:${i + 1}  →  ${zeile.trim()}`)
  })
}

assert.ok(tokWertGeprueft > 0, 'Es wurden Quellen für die Wert-Kopie-Prüfung gefunden')
assert.deepEqual(
  tokWertVerstoesse, [],
  'Token-WERT-Kopien verboten — tokens.css ist die einzige Quelle ' +
    '(nur var(--…) verwenden):\n' + tokWertVerstoesse.join('\n'),
)

console.log(`  Token-Wert-Kopien (Single Source): ${tokWertVerstoesse.length} Verstöße in ${tokWertGeprueft} Dateien`)
