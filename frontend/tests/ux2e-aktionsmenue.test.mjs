/**
 * UX2e — Wächter für das Aktionsmenü „⋯" (Entwurf B1, Prinzip N6/K4).
 *
 * Die Karte gibt jedem Listeneintrag ein „⋯"-Menü mit den Aktionen DES
 * Eintrags, entlässt die Zeilen-Knöpfe und verlangt Tastaturbedienung
 * (Menü-Taste/Umschalt+F10, Pfeile, Pos1/Ende, Esc) sowie Rechtsklick auf die
 * Zeile. Der Test prüft beides:
 *
 *   (1) VERHALTEN — die reine Logik `components/ui/aktionen.mjs` wird
 *       ausgeführt: Tastenfolgen, zyklisches Wandern, Buchstabensprung,
 *       Normalisierung (Gefährliches ans Ende, höchstens 8 Einträge).
 *   (2) BESTAND — die Komponente und alle Seiten, die die Karte nennt, werden
 *       am Quelltext geprüft: ⋯ vorhanden, aria-label, role="menu"/menuitem,
 *       Rechtsklick-Verdrahtung, keine Zeilen-Knöpfe mehr, Symbole im Vorrat.
 *
 * Lauf: node --test tests/ux2e-aktionsmenue.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import {
  MAX_EINTRAEGE,
  eintraegeNormalisieren,
  eintraegePruefen,
  ersteGefahr,
  istKontextmenueTaste,
  naechsterIndex,
  springeZuBuchstabe,
  tasteImMenue,
} from '../src/diakonos/components/ui/aktionen.mjs'

const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (name) => readFileSync(new URL(name, SRC), 'utf8')
const gibtEs = (name) => existsSync(fileURLToPath(new URL(name, SRC)))

/** Vorlage einer .vue-Datei ohne HTML-Kommentare (Kommentare dürfen nichts belegen). */
function vorlage(quelle) {
  const anfang = quelle.indexOf('<template>')
  const ende = quelle.lastIndexOf('</template>')
  return quelle.slice(anfang, ende).replace(/<!--[\s\S]*?-->/g, '')
}

const TASTE = (key, extra = {}) => ({ key, preventDefault() {}, stopPropagation() {}, ...extra })

/* ── (1) VERHALTEN ─────────────────────────────────────────────────────── */

test('UX2e · Kontextmenü-Taste: Menü-Taste und Umschalt+F10, aber nicht F10 allein', () => {
  assert.equal(istKontextmenueTaste(TASTE('ContextMenu')), true)
  assert.equal(istKontextmenueTaste(TASTE('F10', { shiftKey: true })), true)
  assert.equal(istKontextmenueTaste(TASTE('F10')), false, 'F10 allein ist die Menüleiste des Browsers')
  assert.equal(istKontextmenueTaste(TASTE('ArrowDown')), false)
  assert.equal(istKontextmenueTaste(null), false)
})

test('UX2e · Pfeile wandern zyklisch, Pos1/Ende springen an die Ränder', () => {
  assert.equal(naechsterIndex(0, 3, 1), 1)
  assert.equal(naechsterIndex(2, 3, 1), 0, 'unten am Ende geht es oben weiter')
  assert.equal(naechsterIndex(0, 3, -1), 2, 'oben am Anfang geht es unten weiter')
  assert.equal(naechsterIndex(-1, 3, 1), 1, 'ohne Auswahl gilt Position 0 als Start')
  assert.equal(naechsterIndex(0, 0, 1), -1, 'ohne Einträge kein Index')

  const unten = tasteImMenue(TASTE('ArrowDown'), { index: 0, anzahl: 3 })
  assert.deepEqual(unten, { aktion: 'fokus', index: 1 })
  const oben = tasteImMenue(TASTE('ArrowUp'), { index: 0, anzahl: 3 })
  assert.deepEqual(oben, { aktion: 'fokus', index: 2 })
  assert.deepEqual(tasteImMenue(TASTE('Home'), { index: 2, anzahl: 3 }), { aktion: 'fokus', index: 0 })
  assert.deepEqual(tasteImMenue(TASTE('End'), { index: 0, anzahl: 3 }), { aktion: 'fokus', index: 2 })
})

test('UX2e · ↵ und Leertaste führen den gewählten Eintrag aus, ohne Auswahl nichts', () => {
  assert.deepEqual(tasteImMenue(TASTE('Enter'), { index: 2, anzahl: 4 }), { aktion: 'waehlen', index: 2 })
  assert.deepEqual(tasteImMenue(TASTE(' '), { index: 1, anzahl: 4 }), { aktion: 'waehlen', index: 1 })
  assert.equal(tasteImMenue(TASTE('Enter'), { index: -1, anzahl: 4 }), null)
})

test('UX2e · Esc schließt, Tab lässt das Menü los (kein Fokusgefängnis)', () => {
  assert.deepEqual(tasteImMenue(TASTE('Escape'), { index: 1, anzahl: 3 }), { aktion: 'schliessen' })
  assert.deepEqual(tasteImMenue(TASTE('Tab'), { index: 1, anzahl: 3 }), { aktion: 'schliessen' })
  assert.deepEqual(tasteImMenue(TASTE('Escape'), { index: -1, anzahl: 0 }), { aktion: 'schliessen' },
    'auch ein leeres Menü schließt mit Esc')
})

test('UX2e · Buchstabensprung findet den nächsten Eintrag mit diesem Anfangsbuchstaben', () => {
  const eintraege = [
    { label: 'Bearbeiten' }, { label: 'Dienst zuteilen' }, { label: 'Nachricht senden' },
    { label: 'Drucken' }, { label: 'Löschen' },
  ]
  assert.equal(springeZuBuchstabe(eintraege, 0, 'd'), 1, 'erstes „D" nach dem aktuellen')
  assert.equal(springeZuBuchstabe(eintraege, 1, 'd'), 3, 'mehrmals tippen wandert weiter')
  assert.equal(springeZuBuchstabe(eintraege, 3, 'b'), 0, 'zyklisch zurück')
  assert.equal(springeZuBuchstabe(eintraege, 0, 'x'), 0, 'kein Treffer — Index bleibt')
  assert.equal(springeZuBuchstabe(eintraege, 0, 'L'), 4, 'Groß-/Kleinschreibung egal (deutsche Umschreibung)')
})

test('UX2e · Normalisierung: Gefährliches ans Ende, höchstens 8 Einträge, leere fliegen raus', () => {
  const roh = [
    { label: 'Löschen', gefahr: true },
    { label: 'Bearbeiten' },
    { label: '' },
    { label: 'Teilen' },
    { label: 'Ansehen' },
    { label: 'Entfernen', gefahr: true },
  ]
  const norm = eintraegeNormalisieren(roh)
  assert.deepEqual(norm.map((e) => e.label), ['Bearbeiten', 'Teilen', 'Ansehen', 'Löschen', 'Entfernen'],
    'häufige zuerst in ihrer Reihenfolge, gefährliche ans Ende, leere fallen weg')

  const viele = Array.from({ length: 12 }, (_, i) => ({ label: `Aktion ${i + 1}` }))
  assert.equal(eintraegeNormalisieren(viele).length, MAX_EINTRAEGE)
  assert.equal(MAX_EINTRAEGE, 8, 'Prinzip RICHTWERTE: Kontextmenü 5–8 Einträge')

  assert.equal(ersteGefahr(norm), 3)
  assert.equal(ersteGefahr([{ label: 'A' }]), -1)
})

test('UX2e · Prüfregel meldet Gefährliches in der Mitte und zu viele Einträge', () => {
  assert.deepEqual(eintraegePruefen([
    { label: 'Bearbeiten' }, { label: 'Löschen', gefahr: true },
  ]), [])
  const mitte = eintraegePruefen([
    { label: 'Bearbeiten' }, { label: 'Löschen', gefahr: true }, { label: 'Teilen' },
  ])
  assert.ok(mitte.some((m) => m.includes('nicht am Ende')), 'K4: Gefährliches nie zwischen häufigen Aktionen')
  const neun = eintraegePruefen(Array.from({ length: 9 }, (_, i) => ({ label: `A${i}` })))
  assert.ok(neun.some((m) => m.includes('zu viele')), 'zu viele Einträge werden gemeldet')
})

/* ── (2) BESTAND ───────────────────────────────────────────────────────── */

const KOMPONENTE = lies('components/ui/DkAktionen.vue')

test('UX2e · Die Komponente trägt ⋯, Menü-Rollen und aria-Auszeichnung', () => {
  const v = vorlage(KOMPONENTE)
  assert.ok(v.includes('⋯'), 'der Auslöser zeigt die drei Punkte')
  assert.match(v, /class="dk-ui-aktionen-ausloeser"/, 'eigene Klasse für den Auslöser')
  assert.match(v, /:aria-label="ausloeserLabel"/, 'der Knopf ist beschriftet (aria-label)')
  assert.match(v, /aria-haspopup="menu"/)
  assert.match(v, /role="menu"/, 'das Menü ist ein menu')
  assert.match(v, /role="menuitem"/, 'die Einträge sind menuitems')
  assert.match(v, /@contextmenu\.prevent/, 'Rechtsklick auf den Auslöser öffnet kein Browser-Menü')
})

test('UX2e · Tastatur ist verdrahtet: Kontextmenü-Taste, Pfeile über tasteImMenue, Esc', () => {
  assert.match(KOMPONENTE, /istKontextmenueTaste/, 'Menü-Taste/Shift+F10 wird ausgewertet')
  assert.match(KOMPONENTE, /tasteImMenue/, 'Pfeile/Pos1/Ende/↵/Esc laufen über die geprüfte Logik')
  assert.match(KOMPONENTE, /springeZuBuchstabe/, 'Buchstabensprung (K3)')
  assert.match(KOMPONENTE, /oeffnenFuerZeile/, 'Rechtsklick auf die Zeile öffnet dasselbe Menü')
  assert.match(KOMPONENTE, /schliessen\(\{\s*fokus/, 'Esc gibt den Fokus zurück (S5)')
})

test('UX2e · Keine festen Farben in den neuen Bausteinen (Tokens statt Werte)', () => {
  for (const datei of ['components/ui/DkAktionen.vue', 'components/ui/DkSymbol.vue',
    'components/ui/aktionen.mjs', 'components/ui/symbole.mjs']) {
    const quelle = lies(datei).replace(/<!--[\s\S]*?-->/g, '')
    assert.doesNotMatch(quelle, /#[0-9a-fA-F]{3,8}\b/, `${datei}: kein Hex-Wert`)
    assert.doesNotMatch(quelle, /\brgba?\(/, `${datei}: kein rgb()/rgba()`)
  }
})

test('UX2e · Symbole im Menü kommen aus dem Vorrat (kein erfundenes Symbol)', () => {
  assert.ok(gibtEs('components/ui/symbole.mjs'), 'Vorrat liegt in symbole.mjs')
  const symbol = lies('components/ui/symbole.mjs')
  const vorrat = [...symbol.matchAll(/^\s{2}([a-z]+):\s*\{/gm)].map((m) => m[1])
  assert.ok(vorrat.length >= 10, `Vorrat gefüllt (${vorrat.length} Symbole)`)
  const verwendung = new Set()
  for (const datei of SEITEN) {
    const quelle = lies(datei)
    for (const m of quelle.matchAll(/icon:\s*'([a-z]+)'/g)) verwendung.add(m[1])
  }
  for (const name of verwendung) {
    assert.ok(vorrat.includes(name), `Symbol „${name}" steht im Vorrat (DkSymbol.vue)`)
  }
  assert.ok(verwendung.size >= 5, 'die Seiten nutzen die Symbole wirklich')
})

/**
 * Die Seiten der Karte: Personenliste, Gruppenliste + Gruppenmitglieder,
 * Lieder, Beiträge, Wiki, Ressourcen, Termine in Listenansicht.
 */
const SEITEN = [
  'pages/Mitglieder.vue',
  'pages/Gruppen.vue',
  'pages/GruppeDetail.vue',
  'pages/Lieder.vue',
  'pages/Beitraege.vue',
  'pages/Wiki.vue',
  'pages/RessourcenVerwaltung.vue',
  // UX2e4: Die Terminliste (pages/Kalender.vue) ist WIEDER HERAUS — das „⋯"
  // an den Zeilen ging bei jedem Neubau der Bibliothek kaputt (Befund UX2e3).
  // Termine werden in der Liste wieder per Klick bearbeitet.
]

test('UX2e · Jede genannte Liste trägt das Aktionsmenü und öffnet es per Rechtsklick', () => {
  for (const datei of SEITEN) {
    const quelle = lies(datei)
    assert.match(quelle, /import DkAktionen from '\.\.\/components\/ui\/DkAktionen\.vue'/,
      `${datei}: DkAktionen eingebunden`)
    assert.match(quelle, /<DkAktionen/, `${datei}: Menü im Baum`)
    assert.match(quelle, /:eintraege="(listen)?[aA]ktionen/, `${datei}: Einträge kommen aus der Seite`)
    assert.match(quelle, /:label="`Aktionen für/, `${datei}: Auslöser ist beschriftet`)
    assert.match(quelle, /@contextmenu\.prevent="zeilenKontextmenue/, `${datei}: Rechtsklick auf die Zeile`)
    assert.match(quelle, /oeffnenFuerZeile/, `${datei}: dieselbe Menüinstanz für die Zeile`)
  }
  // UX2e4 hat die Terminliste aus dem Menü-Bauteil herausgenommen; UX2e5
  // bringt das „⋯" am Termin zurück — aber IM Kalender-Widget (Geschwister der
  // Bibliothekszeile, gesteuert über `terminAktion`), nicht in der Seite.
  const kalender = lies('pages/Kalender.vue')
  assert.doesNotMatch(kalender, /DkAktionen/, 'die Seite selbst trägt kein Menü-Bauteil')
  const widget = lies('components/kronos/KronosCalendar.vue')
  assert.match(widget, /eventDidMount/, 'UX2e5: das Widget hängt den Auslöser ein')
  assert.match(widget, /terminAktion/, 'UX2e5: und meldet den Eintrag an die Seite')
})

test('UX2e · Die Zeilenknöpfe sind entfallen (Aktionen nur noch im ⋯)', () => {
  // Gruppenmitglieder: „Entfernen" stand vorher als Knopf in jeder Zeile.
  const gruppe = vorlage(lies('pages/GruppeDetail.vue'))
  assert.doesNotMatch(gruppe, /@click="removeMitglied\(m\)"[^>]*>\s*Entfernen\s*<\/DkButton>/,
    'GruppeDetail: kein Zeilenknopf „Entfernen" mehr')
  // Ressourcen: „Bearbeiten"/„Löschen" standen als zwei Knöpfe in der Zeile.
  const ress = vorlage(lies('pages/RessourcenVerwaltung.vue'))
  assert.doesNotMatch(ress, /@click="bearbeiten\(r\)"[^>]*>\s*Bearbeiten/, 'Ressourcen: kein Zeilenknopf „Bearbeiten"')
  assert.doesNotMatch(ress, /@click="entfernen\(r\)"[^>]*>\s*Löschen/, 'Ressourcen: kein Zeilenknopf „Löschen"')
  // Die Funktionen selbst bleiben — sie werden jetzt aus dem Menü gerufen.
  assert.match(lies('pages/RessourcenVerwaltung.vue'), /aktion: \(\) => entfernen\(r\)/)
  assert.match(lies('pages/GruppeDetail.vue'), /aktion: \(\) => removeMitglied\(m\)/)
})

test('UX2e · Kein „⋯"-Knopf innerhalb eines Links (ungültiges HTML)', () => {
  // Ein <button> in einem <a> ist ungültig und im Browser nicht bedienbar
  // (die Personen-Karten: der Knopf blieb unsichtbar). Aufgeräumt ist es mit
  // einer Hülle neben dem Link — der Test hält das fest.
  for (const datei of SEITEN) {
    const quelle = vorlage(lies(datei))
    // Alle <a …>…</a>-Blöcke ohne Verschachtelung; darin darf kein DkAktionen
    // stehen (die Komponente rendert einen <button>).
    for (const m of quelle.matchAll(/<a\b[^>]*>([\s\S]*?)<\/a>/g)) {
      assert.ok(!m[1].includes('<DkAktionen'),
        `${datei}: DkAktionen steht in einem <a> (ungültiges HTML)`)
    }
  }
})

test('UX2e · Gefährliches steht in jedem Menü einzeln am Ende (K4)', () => {
  for (const datei of SEITEN) {
    const quelle = lies(datei)
    if (!quelle.includes('gefahr: true')) continue
    const from = 'function aktionenFuer'
    const anfang = quelle.indexOf(from)
    assert.notEqual(anfang, -1, `${datei}: Eintrags-Funktion gefunden`)
    const block = quelle.slice(anfang, quelle.indexOf('</script>', anfang))
    const pos = block.indexOf('gefahr: true')
    assert.notEqual(pos, -1, `${datei}: gefährlicher Eintrag vorhanden`)
    const danach = block.slice(pos + 'gefahr: true'.length)
    // Nach dem gefahr-Eintrag darf KEIN weiterer Eintrag (`{ key: '…'`)
    // folgen — Gefährliches bleibt der letzte Punkt (K4).
    assert.equal(danach.match(/\{\s*key:\s*'/g), null,
      `${datei}: nach „gefahr: true" folgt kein weiterer Eintrag`)
  }
})
