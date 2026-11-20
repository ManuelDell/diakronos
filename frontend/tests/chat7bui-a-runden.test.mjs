/**
 * CHAT-7b-UI-a — Runden in „Nachrichten“ (Frontend).
 *
 * Karte: „Neue Runde“ als Einstieg, Runden in der Gesprächsliste (Titel,
 * Teilnehmerzahl, ungelesen, eigenes Symbol), Rundenkopf mit Teilnehmenden,
 * „Person vorschlagen“ (bis 8) und „Runde verlassen“, die
 * Vorschlags-Systemzeile mit Zustimmen/Ablehnen und der Eintritts-Hinweis.
 * Grundlage: `docs/konzepte/CHAT-KONZEPT.md` S3, API in
 * `backend/src/diakronos_app/api/chat.py` (runde_anlegen, runde_vorschlagen,
 * runde_zustimmen, runde_ablehnen, runde_verlassen).
 *
 * Geprüft wird VERHALTEN, nicht nur Klassen:
 *
 *   A  Die Regeln (`composables/nachrichtenRunden.mjs`, ohne DOM): Gültigkeit
 *      der Auswahl (2–7, Name Pflicht), wählbar nur mit `darf_schreiben`,
 *      „bis 8“, der Satz/Stand einer Vorschlagszeile (Zustimmen/Ablehnen nur
 *      offen und nie am eigenen Vorschlag), der Eintritts-Hinweis NUR mit dem
 *      Serverfeld.
 *   B  Die Bausteine gemountet (echte jsdom + Attrappen): der Dialog schickt
 *      `chat.runde_anlegen(titel, mitglieder)` mit genau den gewählten
 *      Kennungen, der Anlegen-Knopf erscheint erst bei gültiger Auswahl, ein
 *      Server-Fehler steht als role="alert"; die Vorschlagszeile zeigt den
 *      Satz des Servers und schickt Zustimmen/Ablehnen; die LISTE trägt
 *      „Neue Runde“ und das Rundensymbol.
 *   C  Die SEITE „Nachrichten“ gemountet: „Neue Runde“ öffnet den Dialog, der
 *      Rundenkopf trägt Teilnehmende + beide Aktionen und der Verlauf zeigt
 *      den Eintritts-Hinweis; „Person vorschlagen“ ruft
 *      `chat.runde_vorschlagen` mit der gewählten Person.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat7bui-a-runden.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

import {
  ABSCHNITT_RUNDEN, ANDERE_MAX, AUSWAHL, EINTRITT_HINWEIS, NEUE_RUNDE, OHNE_NAMEN,
  STAND_ANGENOMMEN, STAND_BEENDET, STAND_OFFEN, TEILNEHMER_MAX, VERLASSEN_TEXT,
  auswahlGueltig, auswahlUmschalten, darfVorschlagen, eintrittsHinweis, istVorschlagZeile,
  kandidatenAusAntwort, rundeAnlegenRumpf, rundeAnlegenZustand, rundenKandidat, rundenKopf,
  rundenMitglieder as rundenMitgliederAus,
  rundenTitel, rundenZeilenText, stimmeRumpf, verlassenFrage, verlassenRumpf, vorschlagOhne,
  vorschlagZeile,
  zaehlerText,
} from '../src/diakonos/composables/nachrichtenRunden.mjs'
import {
  ABSCHNITTE, UNBEKANNTE_PERSON, gruppierteListe, listenZeile,
  seiteEinordnen,
} from '../src/diakonos/composables/nachrichtenLogik.mjs'

// ════════════════════════════════════════════════════════════════════════════
// A · Die Regeln (ohne DOM)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-7b-UI · Auswahl: 2–7 andere, Name Pflicht — der Knopf hängt daran', () => {
  // Die Grenzen sind die des Servers (RUNDE_MIN = 3 = ich + 2, RUNDE_MAX = 8).
  assert.deepEqual(AUSWAHL, { min: 2, max: 7 })
  assert.equal(ANDERE_MAX, 7)
  assert.equal(TEILNEHMER_MAX, 8)

  // Ohne Namen: keine Runde — auch mit gültiger Personenwahl.
  assert.deepEqual(rundeAnlegenZustand({ titel: '', auswahl: ['M-1', 'M-2'] }), {
    anzahl: 2, gueltig: false, zaehler: '2 von 2–7 Personen auswählen', anlegen: false, laeuft: false,
  })
  assert.equal(auswahlGueltig({ titel: '   ', auswahl: ['M-1', 'M-2'] }), false,
    'ein Name aus Leerzeichen ist kein Name')

  // Eine Person zu wenig (ich + 1 wäre keine Runde).
  assert.equal(auswahlGueltig({ titel: 'Deko', auswahl: ['M-1'] }), false)
  const zwei = rundeAnlegenZustand({ titel: 'Deko', auswahl: ['M-1', 'M-2'] })
  assert.equal(zwei.gueltig, true, 'ich + 2 andere = eine Runde')
  assert.equal(zwei.anlegen, true, 'erst jetzt steht der Anlegen-Knopf')
  assert.equal(zwei.zaehler, '2 von 2–7 Personen auswählen', 'der Zähler sagt die Grenzen')

  // Acht andere wären neun Beteiligte — die Grenze des Servers.
  const zuViel = ['M-1', 'M-2', 'M-3', 'M-4', 'M-5', 'M-6', 'M-7', 'M-8']
  assert.equal(auswahlGueltig({ titel: 'Deko', auswahl: zuViel }), false)
  assert.equal(auswahlGueltig({ titel: 'Deko', auswahl: zuViel.slice(0, 7) }), true, '7 andere gehen')
  // Doppelte zählen nicht als zwei.
  assert.equal(auswahlGueltig({ titel: 'Deko', auswahl: ['M-1', 'M-1'] }), false)
})

test('CHAT-7b-UI · Auswahl umschalten: hinzufügen, entfernen, nie über die Grenze', () => {
  let liste = auswahlUmschalten([], 'M-1')
  assert.deepEqual(liste, ['M-1'])
  liste = auswahlUmschalten(liste, 'M-2')
  assert.deepEqual(liste, ['M-1', 'M-2'])
  liste = auswahlUmschalten(liste, 'M-1')
  assert.deepEqual(liste, ['M-2'], 'ein zweiter Klick nimmt heraus')
  // Voll: ein weiterer Klick ändert nichts (nicht „einer fliegt raus“).
  const voll = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
  assert.deepEqual(auswahlUmschalten(voll, 'H'), voll, 'bei 7 ist Schluss — nichts wird verdrängt')
  assert.equal(auswahlUmschalten([], '').length, 0, 'leere Kennung zählt nicht')
  assert.equal(zaehlerText({ anzahl: 0 }), '0 von 2–7 Personen auswählen')
})

test('CHAT-7b-UI · Personenauswahl: wählbar NUR mit darf_schreiben, ohne erfundenen Grund', () => {
  const ok = rundenKandidat({ mitglied: 'M-1', anzeigename: 'Anna Beispiel', darf_schreiben: true, hat_konto: true })
  assert.equal(ok.waehlbar, true)
  assert.equal(ok.hinweis, '', 'wer wählbar ist, braucht keinen Grund')
  assert.equal(ok.name, 'Anna Beispiel')

  // Ohne Zusage des Servers: sichtbar, aber ausgegraut — und der Grund bleibt
  // allgemein (der Server unterscheidet „gesperrt“ und „nicht erreichbar“ nicht).
  for (const treffer of [
    { mitglied: 'M-2', anzeigename: 'Bert', darf_schreiben: false, hat_konto: true },
    { mitglied: 'M-3', anzeigename: 'Cem', darf_schreiben: false, hat_konto: false },
    { mitglied: 'M-4', anzeigename: 'Dana' },
    { mitglied: 'M-5', anzeigename: 'Eva', darf_schreiben: 'true', hat_konto: true },
  ]) {
    const k = rundenKandidat(treffer)
    assert.equal(k.waehlbar, false, `nicht wählbar: ${JSON.stringify(treffer)}`)
    assert.equal(k.hinweis, 'nicht auswählbar')
  }
  assert.doesNotMatch(JSON.stringify(kandidatenAusAntwort({ treffer: [{ mitglied: 'M-9', darf_schreiben: false }] })),
    /gesperrt|erreichbar/i, 'die Oberfläche erfindet keinen Grund')
  assert.equal(rundenKandidat(null), null)
  assert.equal(rundenKandidat({ anzeigename: 'ohne Kennung' }), null)
  assert.deepEqual(kandidatenAusAntwort({}).length, 0, 'ohne Antwort keine Zeilen (fail closed)')
})

test('CHAT-7b-UI · Anlegen-Rumpf: titel + die ANDEREN als mitglieder', () => {
  assert.deepEqual(
    rundeAnlegenRumpf({ titel: '  Samstag-Deko ', auswahl: ['M-1', 'M-1', ' M-2 ', ''], ich: 'M-0' }),
    { titel: 'Samstag-Deko', mitglieder: ['M-1', 'M-2'] },
    'getrimmt, ohne Doppelte, ohne Leere',
  )
  // Die eigene Person steht NIE in der Liste (der Server lehnt das ab).
  assert.deepEqual(
    rundeAnlegenRumpf({ titel: 'Deko', auswahl: ['M-0', 'M-1', 'M-2'], ich: 'M-0' }).mitglieder,
    ['M-1', 'M-2'],
  )
})

test('CHAT-7b-UI · Liste: Runde mit eigenem Abschnitt, Titel und Beteiligten', () => {
  // Vertrag (Review R1 c): `mitglieder: [{mitglied, anzeigename}]`, nur bei Runden.
  const runde = {
    name: 'CHAT-R-1', art: 'runde', gruppe: null, untergruppe: null, titel: 'Samstag-Deko',
    teilnehmer: 4, mitglieder: [
      { mitglied: 'M-1', anzeigename: 'Anna Voss' },
      { mitglied: 'M-2', anzeigename: 'Bert Klein' },
      { mitglied: 'M-3', anzeigename: 'Cem Yilmaz' },
      { mitglied: 'M-0', anzeigename: 'Ich Selber' },
    ], stumm: false, geoeffnet: true,
    ungelesen: 2, letzte_nachricht: 'Bis Samstag', letzte_am: '2026-11-18T10:00:00',
  }
  const zeile = listenZeile(runde, new Date(2026, 10, 18, 12, 0))
  assert.equal(zeile.abschnitt, 'runde', 'Runden stehen in ihrem eigenen Abschnitt')
  assert.equal(zeile.titel, 'Samstag-Deko')
  assert.equal(zeile.ungelesen, 2)
  assert.equal(zeile.stumm, false)

  const gruppen = gruppierteListe([
    runde,
    { name: 'CHAT-G-1', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor', teilnehmer: 9, geoeffnet: true, ungelesen: 0 },
    { name: 'CHAT-D-1', art: 'direkt', titel: 'Erika Muster', teilnehmer: 2, geoeffnet: true, ungelesen: 0 },
  ], new Date(2026, 10, 18, 12, 0))
  const reihenfolge = gruppen.map((a) => a.id)
  assert.ok(reihenfolge.includes('runde'), 'der Abschnitt „Runden“ steht da')
  assert.equal(gruppen.find((a) => a.id === 'runde').label, ABSCHNITT_RUNDEN)
  // Der Abschnitt steht VOR „Direktnachrichten“ (Entwurf B-desktop: RUNDEN oben).
  assert.ok(reihenfolge.indexOf('runde') < reihenfolge.indexOf('direkt'))

  // Eine Runde ohne Namen heißt „Runde“ — nie eine leere Zeile.
  assert.equal(rundenTitel({ titel: '' }), OHNE_NAMEN)
  assert.equal(rundenTitel({ titel: '   ' }), 'Runde')
  assert.equal(listenZeile({ art: 'runde', titel: '' }).titel, 'Runde')
  // Die Beteiligten-Zeile nennt die Zahl — „1 Person“, nicht „1 Beteiligte“
  // (Review R1 Punkt 7).
  assert.equal(rundenZeilenText({ teilnehmer: 4 }), '4 Personen')
  assert.equal(rundenZeilenText({ teilnehmer: 1 }), '1 Person')
  assert.equal(rundenZeilenText({}), '')
  assert.equal(rundenKopf({ teilnehmer: 3 }), '3 Personen')
  // Die Abschnittsliste kennt die Runde (EINE Stelle für Reihenfolge/Label) —
  // sie steht OBEN, vor Gruppen/Untergruppen/Direkt (Entwurf B-desktop).
  assert.deepEqual(ABSCHNITTE.map((a) => a.id), ['runde', 'gruppe', 'untergruppe', 'direkt'])
})

test('CHAT-7b-UI · „Person vorschlagen“ nur unter 8 Beteiligten', () => {
  const basis = { art: 'runde', teilnehmer: 3 }
  assert.equal(darfVorschlagen(basis), true)
  assert.equal(darfVorschlagen({ ...basis, teilnehmer: 7 }), true)
  assert.equal(darfVorschlagen({ ...basis, teilnehmer: 8 }), false, 'bei 8 ist Schluss (Server: „unter 8“)')
  assert.equal(darfVorschlagen({ ...basis, teilnehmer: 9 }), false)
  // Keine Zahl (Antwort unvollständig): der Knopf bleibt — der Server entscheidet.
  assert.equal(darfVorschlagen({ art: 'runde' }), true)
  // Kein Gruppen-Chat, kein 1:1.
  assert.equal(darfVorschlagen({ art: 'gruppe', teilnehmer: 3 }), false)
  assert.equal(darfVorschlagen(null), false)
})

test('CHAT-7b-UI · Runde verlassen: Rückfrage mit gefahr und dem Wortlaut der Karte', () => {
  const frage = verlassenFrage()
  assert.equal(frage.gefahr, true, 'eine gefährliche Aktion fragt nach')
  assert.equal(frage.text, VERLASSEN_TEXT)
  assert.equal(VERLASSEN_TEXT, 'Du siehst die Runde danach nicht mehr. Offene Vorschläge enden.')
  assert.match(frage.titel, /Runde verlassen/)
  assert.equal(frage.aktion, 'Runde verlassen')
  assert.deepEqual(verlassenRumpf(' CHAT-R-1 '), { gespraech: 'CHAT-R-1' })
})

test('CHAT-7b-UI · Vorschlagszeile: Satz vom Server, Knöpfe nur offen und nie am eigenen', () => {
  // Vertrag (Review R1 a): `system = {art, stand, vorschlag, eigene}`.
  const zeile = {
    name: 'N-7', gespraech: 'CHAT-R-1', ident: 'N-7',
    text: 'Anna möchte Bert hinzufügen.',
    system: { art: 'runde_vorschlag', stand: STAND_OFFEN, vorschlag: 'V-1', eigene: false },
  }
  assert.equal(istVorschlagZeile(zeile), true)
  const offen = vorschlagZeile(zeile)
  assert.equal(offen.satz, 'Anna möchte Bert hinzufügen.', 'der Satz kommt vom Server, nicht aus einer Kopie')
  assert.equal(offen.abstimmbar, true, 'offen → die Runde stimmt ab')
  assert.equal(offen.standText, '', 'offen braucht keine Stand-Zeile')
  assert.equal(offen.vorschlag, 'V-1', 'die Kennung des VORSCHLAGS kommt aus system.vorschlag')

  // Der eigene Vorschlag: keine Knöpfe (der Server würde 417 antworten).
  const eigen = vorschlagZeile({ ...zeile, system: { ...zeile.system, eigene: true } })
  assert.equal(eigen.eigene, true)
  assert.equal(eigen.abstimmbar, false, 'über den eigenen Vorschlag stimmt die Runde ab')

  // Ohne Kennung kein Knopf — ein Aufruf ohne `vorschlag` könnte nichts tun.
  const ohneKennung = vorschlagZeile({ ...zeile, system: { art: 'runde_vorschlag', stand: STAND_OFFEN } })
  assert.equal(ohneKennung.abstimmbar, false, 'ohne system.vorschlag keine Zustimmung')
  // Das alte, erfundene Feld zählt NICHT mehr.
  assert.equal(vorschlagZeile({ ...zeile, vorgeschlagen_von_eigene: true }).eigene, false)

  // Entschieden: ruhiger Stand, keine Knöpfe.
  for (const [stand, text] of [
    [STAND_ANGENOMMEN, 'Angenommen.'],
    ['abgelehnt', 'Abgelehnt.'],
    [STAND_BEENDET, 'Beendet.'],
  ]) {
    const lage = vorschlagZeile({ ...zeile, system: { ...zeile.system, stand } })
    assert.equal(lage.offen, false, `${stand}: nicht mehr offen`)
    assert.equal(lage.abstimmbar, false, `${stand}: keine Knöpfe`)
    assert.equal(lage.standText, text, `${stand}: der Stand steht ruhig da`)
  }
  // Keine Systemzeile → `null` (die Seite zeichnet dann die normale Blase).
  assert.equal(vorschlagZeile({ text: 'Hallo' }), null)
  assert.equal(vorschlagZeile({ system: { art: 'umfrage' } }), null)
  // Ohne Satz nie eine leere Zeile.
  assert.ok(vorschlagZeile({ system: { art: 'runde_vorschlag', stand: STAND_OFFEN } }).satz.length > 0)
  assert.deepEqual(stimmeRumpf(' N-7 '), { vorschlag: 'N-7' })
})

test('CHAT-7b-UI · Teilnehmerliste kommt aus `mitglieder: [{mitglied, anzeigename}]`', () => {
  // Vertrag (Review R1 c) — nur Runden tragen das Feld, und es wird NICHTS
  // nachgeschlagen: kein Name aus einer Suche, keine rohe Kennung in der Liste.
  const runde = {
    art: 'runde',
    mitglieder: [
      { mitglied: 'M-1', anzeigename: 'Anna Voss' },
      { mitglied: 'M-2', anzeigename: '  ' },
      { mitglied: 'M-1', anzeigename: 'Anna Voss' },
      { mitglied: '', anzeigename: 'Niemand' },
    ],
  }
  assert.deepEqual(rundenMitgliederAus(runde), [
    { mitglied: 'M-1', name: 'Anna Voss' },
    { mitglied: 'M-2', name: UNBEKANNTE_PERSON },
  ], 'doppelte und leere fallen raus, ein Name fehlt nie ganz')
  // Ein anderes Gespräch trägt das Feld nicht → leere Liste, keine Erfindung.
  assert.deepEqual(rundenMitgliederAus({ art: 'gruppe', mitglieder: ['M-1'] }), [])
  assert.deepEqual(rundenMitgliederAus(null), [])
})

test('CHAT-7b-UI · „Person vorschlagen“ schließt mich und die Beteiligten aus', () => {
  const runde = {
    art: 'runde',
    mitglieder: [{ mitglied: 'M-1', anzeigename: 'Anna' }, { mitglied: 'M-0', anzeigename: 'Ich' }],
  }
  assert.deepEqual(vorschlagOhne(runde, 'M-0').sort(), ['M-0', 'M-1'])
  assert.deepEqual(vorschlagOhne({ art: 'runde' }, 'M-0'), ['M-0'])
  assert.deepEqual(vorschlagOhne({ art: 'runde' }, ''), [])
})

test('CHAT-7b-UI · Eintritts-Hinweis NUR, wenn der Server das Feld schickt', () => {
  assert.equal(eintrittsHinweis({ ab_eintritt: true }), EINTRITT_HINWEIS)
  assert.equal(EINTRITT_HINWEIS, 'Du siehst Nachrichten ab deinem Eintritt.')
  assert.equal(eintrittsHinweis({ ab_eintritt: false }), '', 'ohne Feld keine Behauptung')
  assert.equal(eintrittsHinweis({}), '')
  assert.equal(eintrittsHinweis(null), '')
  assert.equal(eintrittsHinweis({ ab_eintritt: 'true' }), '', 'nur WAHR ist ein Ja')
})

// ════════════════════════════════════════════════════════════════════════════
// B · Bausteine gemountet
// ════════════════════════════════════════════════════════════════════════════

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/#/nachrichten' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))

const Vue = await import('vue')
const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat7bui-'))
test.after(() => { if (!process.env.CHAT7B_BEHALTEN) rmSync(TMP, { recursive: true, force: true }) })

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

const umleitung = new Map()
const cache = new Map()
// Umweg über das Ziel-Modul: der Import der eingebauten `path`-Funktionen
// läuft in dieser Datei über die Bindung — `dirname`/`resolve` werden hier
// festgehalten (ein gleichnamiges lokales `const` in anderen Tests würde die
// Modulbindung sonst verdecken).
const knotenPfad = await import('node:path')
const pfadVerzeichnis = (p) => knotenPfad.dirname(p)
const pfadAufloesen = (...teile) => knotenPfad.resolve(...teile)

/**
 * Ein Baum SFCs/Module ab `seite` übersetzen — nach dem Muster der
 * bestehenden Chat-Tests (`chat7-direkt-ui`): jede Datei bekommt eine FLACHE
 * Zieldatei im TEMP-Ordner, und ihre `.`-Importe werden gegen die QUELLE
 * aufgelöst und auf andere Zieldateien umgeschrieben (Attrappen über
 * `umleitung`). `ordner` wählt den Ablageort (dort liegen auch die Attrappen).
 */
const UMLEITUNGEN = []
const base_name = (u) => u.split('/').pop()
function baum(seite, { ordner = null, frisch = false } = {}) {

  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = frisch ? new Map() : cache
  const quellen = new Map()
  const zielFuer = (quellDatei) => {
    // Der Pfad ab `frontend/` — `../shared/` liegt AUSSERHALB von `src/diakonos/`.
    const relativ = resolve(quellDatei).slice(resolve(SRC_ROOT.pathname, '../').length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    quellen.set(ziel, quellDatei)
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
    // Bereits übersetzte Ziele werden auf ihre QUELLE zurückgeführt — sonst
    // löst eine Kette (A → B → C) ihre relativen Importe im TEMP-Ordner auf.
    const ursprung = quellen.get(abs) || abs
    const quellDatei = aufgeloest(ursprung)
    // Das Ziel VOR dem Übersetzen festlegen und VOR dem Umschreiben der
    // Importe eintragen: ein Ring (A → B → A) bricht damit am schon
    // bekannten Ziel ab, statt endlos weiterzulaufen.
    const ziel = zielFuer(quellDatei)
    NEU.set(abs, ziel)
    NEU.set(quellDatei, ziel)
    let code
    if (quellDatei.endsWith('.vue')) {
      const filename = basename(quellDatei)
      const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
      assert.deepEqual(errors, [], filename + ': SFC-Struktur')
      const script = compileScript(descriptor, { id: filename })
      const tpl = compileTemplate({
        source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      })
      assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
      const scode = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      code = scode + '\n' + tpl.code.replace(/^export function render/m, 'function render')
      code += '\n__sfc__.render = render\nexport default __sfc__\n'
    } else {
      code = readFileSync(quellDatei, 'utf8')
    }
    // Importe umschreiben — ein `from '…'` je Importanweisung. Ein Zitat in
    // einem Kommentar/Text ist KEIN Import: erkannt wird an `from`.
    const mitZiel = (spec) => {
      if (spec === 'vue') return `'${VUE_URL}'`
      if (spec.startsWith('node:')) return null
      if (!spec.startsWith('.')) {
        try { return `'${import.meta.resolve(spec)}'` } catch { return null }
      }
      // Das Zwischenziel liegt FLACH im TEMP-Ordner — der Importpfad gehört
      // zur QUELLE. Aufgelöst wird mit `node:path` gegen den QUELLORDNER (das
      // ist derselbe Weg wie im Betrieb); erst danach entscheidet die
      // Erweiterung, ob es eine Datei ist.
      const zielAbs = (() => {
        try { return aufgeloest(resolve(dirname(quellDatei), spec)) } catch { return '' }
      })()
      if (!zielAbs) return null
      const url = pathToFileURL(zielAbs).href
      const ersatz = umleitung.get(url)
      return `'${ersatz || pathToFileURL(uebersetzen(zielAbs)).href}'`
    }
    code = code.replace(/from\s+(["'])([^"']+)\1/g, (ganz, _q, spec) => {
      const neu = mitZiel(spec)
      return neu ? `from ${neu}` : ganz
    })
    writeFileSync(ziel, code)
    return ziel
  }
  return uebersetzen(new URL(seite, SRC).pathname)
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 12) => { for (let i = 0; i < n; i += 1) await tick() }

async function mounten(komponente, props = {}) {
  const host = dom.window.document.createElement('div')
  dom.window.document.body.appendChild(host)
  const app = Vue.createApp({ render: () => Vue.h(komponente, props) })
  const fehler = []
  app.config.errorHandler = (e) => fehler.push(e)
  app.mount(host)
  // `DkDialog` teleportiert nach `body`: beim Abbau muss auch das weg, sonst
  // sammeln sich die Fenster früherer Tests im selben Fenster an (und eine
  // Suche liefe im falschen Dialog).
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    host.remove()
    for (const kind of [...dom.window.document.body.children]) {
      if (kind !== host) kind.remove()
    }
  }
  return { host, abbaum, fehler }
}

/** Attrappen für Netz und Sitzung; `server` beantwortet `{methode, parameter}`. */
function attrappen(ordner, { server, push = () => {} }) {
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH({ art: "POST", methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH({ art: "GET", methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)
  globalThis.__PUSH = push
  globalThis.__SERVER = server
}

const klick = (el) => {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

/**
 * Ein Kästchen umschalten: jsdom setzt `checked` bei einem erzeugten
 * MouseEvent NICHT und feuert kein `change` — hier wird beides nachgeholt,
 * damit der Weg derselbe ist wie beim Menschen (`@change` der Komponente).
 */
const kaestchen = (el) => {
  assert.ok(el, 'das Kästchen steht im DOM')
  el.checked = !el.checked
  el.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
}

const knopfMit = (host, text) => [...host.querySelectorAll('button')]
  .find((b) => (b.textContent || '').trim().includes(text))

test('CHAT-7b-UI · ChatRundeDialog: Name + 2 Personen → chat.runde_anlegen mit den Kennungen', async () => {
  const ordner = join(TMP, 'dialog-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  attrappen(ordner, {
    push: (e) => aufrufe.push(e),
    server: async ({ methode }) => {
      const kurz = String(methode).split('.').pop()
      if (kurz === 'personen_suchen') {
        return {
          treffer: [
            { mitglied: 'M-1', anzeigename: 'Anna Beispiel', bild: '', hat_konto: true, darf_schreiben: true },
            { mitglied: 'M-2', anzeigename: 'Bert Brandner', bild: '', hat_konto: true, darf_schreiben: true },
            { mitglied: 'M-3', anzeigename: 'Cem Gesperrt', bild: '', hat_konto: true, darf_schreiben: false },
          ],
          limit: 20,
        }
      }
      return {}
    },
  })
  const mod = await import(pathToFileURL(baum('components/chat/ChatRundeDialog.vue', { ordner, frisch: true })).href)
  const gemeldet = []
  const { host, abbaum, fehler } = await mounten(mod.default, {
    modelValue: true,
    'onUpdate:modelValue': (v) => gemeldet.push(v),
    onAnlegen: (daten) => gemeldet.push(daten),
  })
  await warte(10)
  assert.deepEqual(fehler, [], 'der Dialog baut ohne Fehler auf')

  // `DkDialog` teleportiert nach `body` — gesucht wird deshalb dort (der Host
  // ist ein Kind von `body`, das Fenster liegt daneben).
  const fenster = dom.window.document.body
  const anlegen = knopfMit(fenster, NEUE_RUNDE)
  assert.ok(anlegen, 'der Anlegen-Knopf steht da')
  assert.equal(anlegen.disabled, true, 'ohne Name und Personen gesperrt')

  // Namen tippen (v-model über `feldProps`) — Pflichtfeld.
  const felder = [...fenster.querySelectorAll('input')]
  const nameFeld = felder.find((f) => f.type === 'text')
  assert.ok(nameFeld, 'das Namensfeld steht da')
  nameFeld.value = 'Samstag-Deko'
  nameFeld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(6)

  // Personen suchen — die vorhandene Suche (`chat.personen_suchen`), entprellt.
  const suchFeld = felder.find((f) => f.type === 'search')
  assert.ok(suchFeld, 'das Suchfeld steht da')
  suchFeld.value = 'an'
  suchFeld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  // 2 Zeichen = Suchbegriff im Sinne des Servers; der Entpreller wartet
  // `ENTPRELLUNG_MS` (echte Zeit) — deshalb wird hier wirklich gewartet.
  for (let i = 0; i < 100; i += 1) {
    if (fenster.querySelectorAll('.dk-runde-treffer li').length) break
    await new Promise((loese) => setTimeout(loese, 20))
  }
  const suche = aufrufe.find((a) => /personen_suchen$/.test(a.methode))
  assert.ok(suche, 'die Personen wurden gesucht')
  assert.equal(suche.art, 'GET', 'die Suche ist rein lesend (GET)')

  // Erst wenn ALLE drei Zeilen stehen, sind die Kästchen da (die Antwort kann
  // nach dem Abbruch der Schleife noch eintreffen).
  for (let i = 0; i < 100; i += 1) {
    if (fenster.querySelectorAll('.dk-runde-treffer li input[type="checkbox"]').length >= 3) break
    await new Promise((loese) => setTimeout(loese, 20))
  }
  const zeilen = [...fenster.querySelectorAll('.dk-runde-treffer li')]
  assert.equal(zeilen.length, 3, 'alle Treffer stehen da')
  const kaesten = [...fenster.querySelectorAll('.dk-runde-treffer li input[type="checkbox"]')]
  assert.equal(kaesten.length, 3, 'drei Kästchen')
  const kasten = (n) => kaesten[n]
  assert.equal(kasten(2).disabled, true, 'ohne darf_schreiben ist die Zeile ausgegraut')
  assert.match(zeilen[2].textContent, /nicht auswählbar/, 'und nennt den Grund nicht genauer (Server sagt ihn nicht)')

  kaestchen(kasten(0))
  await warte(6)
  kaestchen(kasten(1))
  await warte(6)
  const anlegenJetzt = knopfMit(fenster, NEUE_RUNDE)
  assert.equal(anlegenJetzt.disabled, false, 'zwei Personen + Name = gültig, der Knopf geht')
  assert.match(fenster.textContent, /2 von 2–7 Personen auswählen/, 'der Zähler sagt die Grenzen')

  klick(anlegenJetzt)
  await warte(4)
  const daten = gemeldet.find((g) => g && typeof g === 'object' && Array.isArray(g.auswahl))
  assert.ok(daten, 'die Auswahl geht als Ereignis an die Seite (sie sendet)')
  assert.equal(daten.titel, 'Samstag-Deko')
  assert.deepEqual(daten.auswahl, ['M-1', 'M-2'], 'genau die gewählten Kennungen — die dritte Person ist nicht dabei')
  abbaum()
})

test('CHAT-7b-UI · ChatRundeDialog: Server-Fehler steht ruhig als role="alert"', async () => {
  const ordner = join(TMP, 'dialog-fehler-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  attrappen(ordner, { server: async () => ({ treffer: [], limit: 20 }) })
  const mod = await import(pathToFileURL(baum('components/chat/ChatRundeDialog.vue', { ordner, frisch: true })).href)
  const { host, abbaum } = await mounten(mod.default, {
    modelValue: true,
    fehler: 'Das hat nicht geklappt.',
  })
  await warte(6)
  const meldung = dom.window.document.body.querySelector('.dk-runde-fehler[role="alert"]')
  assert.ok(meldung, 'der Fehler steht als role="alert" da')
  assert.match(meldung.textContent, /Das hat nicht geklappt/)
  abbaum()
})

test('CHAT-7b-UI · ChatVorschlagZeile: Satz, Knöpfe nur offen, Stand ruhig', async () => {
  const ordner = join(TMP, 'vorschlag-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  attrappen(ordner, { server: async () => ({}) })
  const mod = await import(pathToFileURL(baum('components/chat/ChatVorschlagZeile.vue', { ordner, frisch: true })).href)

  const zeile = {
    ident: 'N-7', name: 'N-7', gespraech: 'CHAT-R-1',
    text: 'Anna möchte Bert hinzufügen.',
    system: { art: 'runde_vorschlag', stand: STAND_OFFEN, vorschlag: 'V-1', eigene: false },
  }
  const gemeldet = []
  const offen = await mounten(mod.default, {
    zeile,
    onZustimmen: (e) => gemeldet.push({ art: 'zustimmen', e }),
    onAblehnen: (e) => gemeldet.push({ art: 'ablehnen', e }),
  })
  await warte(4)
  assert.match(offen.host.textContent, /Anna möchte Bert hinzufügen\./, 'der Satz des Servers steht da')
  // Keine Aktionen einer normalen Nachricht an dieser Zeile (Karte Punkt 4).
  assert.equal(offen.host.querySelector('.dk-chat-blase'), null, 'keine Blase — eine Systemzeile')
  assert.equal(offen.host.querySelector('[aria-label="Antworten"]'), null, 'kein Antworten')
  assert.equal(offen.host.querySelector('[aria-label="Löschen"]'), null, 'kein Löschen')
  assert.equal(offen.host.querySelector('[aria-label="Bearbeiten"]'), null, 'kein Bearbeiten')
  assert.doesNotMatch(offen.host.textContent, /Melden/, 'kein Melden')

  klick(knopfMit(offen.host, 'Zustimmen'))
  klick(knopfMit(offen.host, 'Ablehnen'))
  await warte(2)
  assert.deepEqual(gemeldet.map((g) => g.art), ['zustimmen', 'ablehnen'], 'beide Wege melden sich')
  assert.equal(gemeldet[0].e.vorschlag, 'V-1', 'die Kennung des VORSCHLAGS reist mit, nicht die der Zeile')
  offen.abbaum()

  // Der eigene Vorschlag: keine Knöpfe, der Satz bleibt.
  const eigen = await mounten(mod.default, { zeile: { ...zeile, system: { ...zeile.system, eigene: true } } })
  await warte(4)
  assert.equal(knopfMit(eigen.host, 'Zustimmen'), undefined, 'am eigenen Vorschlag stimmt niemand mit')
  assert.match(eigen.host.textContent, /hinzufügen/)
  eigen.abbaum()

  // Entschieden: ruhiger Stand.
  const stand = await mounten(mod.default, {
    zeile: { ...zeile, system: { ...zeile.system, stand: STAND_ANGENOMMEN } },
  })
  await warte(4)
  assert.equal(knopfMit(stand.host, 'Zustimmen'), undefined, 'angenommen → keine Knöpfe')
  assert.match(stand.host.textContent, /Angenommen\./, 'der Stand steht da')
  stand.abbaum()
})

test('CHAT-7b-UI · ChatListe: „Neue Runde“ als Einstieg und das Rundensymbol', async () => {
  const ordner = join(TMP, 'liste-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  attrappen(ordner, { server: async () => ({}) })
  const mod = await import(pathToFileURL(baum('components/chat/ChatListe.vue', { ordner, frisch: true })).href)
  const gemeldet = []
  const { host, abbaum } = await mounten(mod.default, {
    gruppen: gruppierteListe([{
      name: 'CHAT-R-1', art: 'runde', titel: 'Samstag-Deko', teilnehmer: 4,
      mitglieder: [{ mitglied: 'M-1', anzeigename: 'Anna Voss' }],
      geoeffnet: true, ungelesen: 3, letzte_nachricht: 'Bis Samstag', letzte_am: '2026-11-18T10:00:00',
    }], new Date(2026, 10, 18, 12, 0)),
    aktiv: '',
    ungelesen: 3,
    onNeueRunde: () => gemeldet.push('neueRunde'),
  })
  await warte(4)
  const einstieg = knopfMit(host, NEUE_RUNDE)
  assert.ok(einstieg, '„Neue Runde“ steht als eigener Einstieg da')
  klick(einstieg)
  assert.deepEqual(gemeldet, ['neueRunde'], 'der Knopf meldet sich (die Seite öffnet den Dialog)')

  // Die Runde in der Liste: Symbol, Titel, Beteiligte, Zähler.
  assert.ok(host.querySelector('.dk-chat-av--runde svg'), 'die Zeile trägt das Rundensymbol')
  assert.match(host.textContent, /Samstag-Deko/)
  assert.match(host.textContent, /4 Personen/)
  assert.match(host.textContent, /3/, 'der Ungelesen-Zähler steht da')
  assert.match(host.textContent, /Runden/, 'der Abschnitt heißt „Runden“')
  abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · Die Seite „Nachrichten“ gemountet
// ════════════════════════════════════════════════════════════════════════════

const RUNDE = {
  name: 'CHAT-R-1', art: 'runde', gruppe: null, untergruppe: null, titel: 'Samstag-Deko',
  teilnehmer: 3, stumm: false, geoeffnet: true,
  mitglieder: [
    { mitglied: 'M-1', anzeigename: 'Anna Voss' },
    { mitglied: 'M-2', anzeigename: 'Bert Klein' },
    { mitglied: 'M-0', anzeigename: 'Ich Selber' },
  ],
  ungelesen: 0, letzte_nachricht: 'Hallo', letzte_am: '2026-11-18T10:00:00', darf_senden: true,
}

/**
 * Die Seite mit Attrappen mounten. `aufrufe` sammelt JEDEN Aufruf; `hash` ist
 * die Adresse (Liste oder offene Runde); `abEintritt` steuert das Serverfeld.
 */
async function seite({ hash = '#/nachrichten', abEintritt = false, runde = RUNDE, handy = false,
  server = null } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  attrappen(ordner, {
    push: (e) => aufrufe.push(e),
    server: async ({ methode }) => {
      const kurz = String(methode).split('.').pop()
      if (kurz === 'meine_gespraeche') return { gespraeche: [runde] }
      if (kurz === 'verlauf') {
        return {
          richtung: 'neueste',
          ab_eintritt: abEintritt === true,
          nachrichten: [{
            name: 'N-1', gespraech: runde.name, text: 'Hallo', autor: 'M-1', eigene: false,
            erstellt_am: '2026-11-18T10:00:00',
          }, {
            name: 'N-2', gespraech: runde.name, ident: 'N-2',
            text: 'Anna möchte Bert hinzufügen.',
            system: { art: 'runde_vorschlag', stand: STAND_OFFEN, vorschlag: 'V-1', eigene: false },
            erstellt_am: '2026-11-18T10:01:00',
          }],
        }
      }
      if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
      if (kurz === 'personen_suchen') {
        return {
          treffer: [
            { mitglied: 'M-9', anzeigename: 'Zoe Neu', bild: '', hat_konto: true, darf_schreiben: true },
            { mitglied: 'M-10', anzeigename: 'Tim Zweit', bild: '', hat_konto: true, darf_schreiben: true },
          ],
          limit: 20,
        }
      }
      if (kurz === 'runde_vorschlagen') return { vorschlag: { name: 'V-1' }, nachricht: {} }
      if (server) return server({ methode, kurz })
      if (kurz === 'runde_anlegen') {
        return { name: 'CHAT-R-2', art: 'runde', titel: 'Neu', teilnehmer: 3,
          mitglieder: [{ mitglied: 'M-1', anzeigename: 'Anna' }, { mitglied: 'M-2', anzeigename: 'Bert' },
            { mitglied: 'M-0', anzeigename: 'Ich' }] }
      }
      return {}
    },
  })
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash
  // Handy-Lage: `matchMedia` beantwortet die EINE Abfrage der App.
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
  const mod = await import(pathToFileURL(baum('pages/Nachrichten.vue', { ordner, frisch: true })).href)
  const gemountet = await mounten(mod.default, {})
  await warte(30)
  return { ...gemountet, aufrufe }
}

test('CHAT-7b-UI · Seite: Rundenkopf mit Teilnehmenden, Vorschlagen und Verlassen', async () => {
  const s = await seite({ hash: '#/nachrichten/CHAT-R-1' })
  const text = () => s.host.textContent || ''
  assert.deepEqual(s.fehler, [], 'die Seite baut ohne Fehler auf')

  // Titel und Beteiligten-Zahl im Kopf (nicht „im Gespräch“).
  assert.match(text(), /Samstag-Deko/, 'der Rundenname steht im Kopf')
  assert.match(text(), /3 Personen/, 'die Zahl der Beteiligten steht darunter')

  // Teilnehmende: aufklappbar (zu = nur der Knopf, auf = die Namen).
  const teilnehmerKnopf = knopfMit(s.host, 'Teilnehmende')
  assert.ok(teilnehmerKnopf, '„Teilnehmende“ steht im Kopf')
  assert.equal(teilnehmerKnopf.getAttribute('aria-expanded'), 'false')
  // Bis zum Aufklappen ist die Liste zu (v-show) — die Namen stehen trotzdem im
  // DOM, weil sie MIT der Serverantwort kommen (kein Nachschlagen, keine Kennung).
  assert.match(text(), /Anna Voss/, 'die Namen kommen aus `mitglieder` (Vertrag c)')
  const liste = s.host.querySelector('#chat-runde-teilnehmende')
  assert.ok(liste, 'die Teilnehmerliste steht mit ihrer Kennung (aria-controls) da')
  assert.equal(liste.querySelectorAll('li').length, 3, 'drei Beteiligte — aktive, inklusive mir')
  assert.doesNotMatch(liste.textContent, /M-\d/, 'in der Liste steht NIE eine rohe Kennung')
  klick(teilnehmerKnopf)
  await warte(4)
  assert.equal(knopfMit(s.host, 'Teilnehmende').getAttribute('aria-expanded'), 'true',
    'ein Klick klappt die Liste auf (aria-expanded)')
  assert.ok(s.host.querySelector('#chat-runde-teilnehmende'), 'die Liste hat eine Kennung (aria-controls)')

  // Die beiden Aktionen der Karte.
  assert.ok(knopfMit(s.host, 'Person vorschlagen'), '„Person vorschlagen“ steht im Kopf')
  assert.ok(knopfMit(s.host, 'Runde verlassen'), '„Runde verlassen“ steht im Kopf')
  s.abbaum()
})

test('CHAT-7b-UI · Seite: „Person vorschlagen“ ruft chat.runde_vorschlagen', async () => {
  const s = await seite({ hash: '#/nachrichten/CHAT-R-1' })
  klick(knopfMit(s.host, 'Person vorschlagen'))
  await warte(6)
  // `DkDialog` teleportiert nach `body` — das Fenster liegt NEBEN dem Host.
  const fenster = dom.window.document.body
  const dialogTitel = [...fenster.querySelectorAll('h3')].map((h) => h.textContent.trim())
  assert.ok(dialogTitel.includes('Person vorschlagen'), 'der Vorschlags-Dialog ist offen')

  const suchFeld = fenster.querySelector('#runde-personensuche')
  assert.ok(suchFeld, 'die Personenauswahl steht im Dialog')
  suchFeld.value = 'zoe'
  suchFeld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  // Der Entpreller wartet echte Zeit (`ENTPRELLUNG_MS`) — wirklich warten.
  for (let i = 0; i < 100; i += 1) {
    if (fenster.querySelector('.dk-runde-treffer button')) break
    await new Promise((loese) => setTimeout(loese, 20))
  }
  const person = fenster.querySelector('.dk-runde-treffer button')
  assert.ok(person, 'der Treffer ist ein Knopf (eine Person vorschlagen)')
  assert.match(person.textContent, /Zoe Neu/)
  klick(person)
  await warte(10)
  const vorschlag = s.aufrufe.filter((a) => /runde_vorschlagen$/.test(a.methode))
  assert.equal(vorschlag.length, 1, 'genau EIN Vorschlag — kein doppelter Aufruf')
  assert.equal(vorschlag[0].art, 'POST', 'runde_vorschlagen ist ein POST')
  assert.deepEqual(vorschlag[0].parameter, { gespraech: 'CHAT-R-1', mitglied: 'M-9' },
    'die Parameter heißen wie im Server')
  s.abbaum()
})

test('CHAT-7b-UI · Seite: Vorschlagszeile im Verlauf schickt Zustimmen', async () => {
  const s = await seite({ hash: '#/nachrichten/CHAT-R-1' })
  const systemZeile = s.host.querySelector('.dk-chat-system')
  assert.ok(systemZeile, 'die Vorschlagszeile steht im Verlauf')
  assert.match(systemZeile.textContent, /Anna möchte Bert hinzufügen\./, 'der Satz des Servers steht da')
  assert.equal(systemZeile.querySelector('.dk-chat-blase'), null, 'als Systemzeile, nicht als Blase')

  klick(knopfMit(systemZeile, 'Zustimmen'))
  await warte(10)
  const stimmen = s.aufrufe.filter((a) => /runde_zustimmen$/.test(a.methode))
  assert.equal(stimmen.length, 1, 'genau EINE Zustimmung')
  assert.deepEqual(stimmen[0].parameter, { vorschlag: 'V-1' },
    'die Kennung des VORSCHLAGS (system.vorschlag) reist mit, nicht die der Zeile')
  s.abbaum()
})

test('CHAT-7b-UI · Seite: Eintritts-Hinweis erscheint nur mit dem Serverfeld', async () => {
  const mit = await seite({ hash: '#/nachrichten/CHAT-R-1', abEintritt: true })
  assert.match(mit.host.textContent, /Du siehst Nachrichten ab deinem Eintritt\./,
    'der Server sagt „ab Eintritt“ → der Hinweis steht oben')
  mit.abbaum()

  const ohne = await seite({ hash: '#/nachrichten/CHAT-R-1', abEintritt: false })
  assert.doesNotMatch(ohne.host.textContent, /Du siehst Nachrichten ab deinem Eintritt/,
    'ohne das Feld steht NICHTS (die Oberfläche behauptet nichts)')
  ohne.abbaum()
})

test('CHAT-7b-UI · Seite: „Neue Runde“ öffnet den Dialog und legt an', async () => {
  const s = await seite({ hash: '#/nachrichten' })
  const einstieg = knopfMit(s.host, NEUE_RUNDE)
  assert.ok(einstieg, 'der Einstieg steht in der Liste')
  klick(einstieg)
  await warte(6)
  // `DkDialog` teleportiert nach `body` (siehe oben).
  const fenster = dom.window.document.body
  const titel = [...fenster.querySelectorAll('h3')].map((h) => h.textContent.trim())
  assert.ok(titel.includes(NEUE_RUNDE), 'der Dialog ist offen')

  // Name + zwei Personen → der Dialog meldet `anlegen`, die SEITE sendet.
  const nameFeld = [...fenster.querySelectorAll('.dk-runde-dialog input[type="text"]')][0]
  assert.ok(nameFeld, 'das Namensfeld des Dialogs steht da')
  nameFeld.value = 'Samstag-Deko'
  nameFeld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  // Gezielt das Suchfeld des DIALOGS (die Seite hat ihre eigene Suche).
  const suchFeld = fenster.querySelector('#runde-neu-personen')
  suchFeld.value = 'zoe'
  suchFeld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  for (let i = 0; i < 150; i += 1) {
    if (fenster.querySelectorAll('.dk-runde-treffer input[type="checkbox"]').length >= 2) break
    await new Promise((loese) => setTimeout(loese, 20))
  }
  const kaesten = () => [...fenster.querySelectorAll('.dk-runde-treffer input[type="checkbox"]')]
  assert.equal(kaesten().length, 2, 'beide Treffer stehen da')

  // EINE Person: zu wenig — der Knopf bleibt gesperrt, es geht KEIN Aufruf los.
  // Der Anlegen-Knopf des DIALOGS — die Liste trägt denselben Text als
  // Einstieg; gesucht wird deshalb im Fenster mit dem Namensfeld.
  const dialog = () => nameFeld.closest('[role="dialog"]') || nameFeld.closest('.dk-dialog') || fenster
  const anlegenKnopf = () => [...dialog().querySelectorAll('button')]
    .filter((b) => (b.textContent || '').trim() === NEUE_RUNDE).pop()
  assert.ok(anlegenKnopf(), 'der Anlegen-Knopf des Dialogs steht da')

  kaestchen(kaesten()[0])
  await warte(6)
  assert.equal(anlegenKnopf().disabled, true,
    'EINE Person reicht nicht — ich + 2 ist die Grenze')
  assert.equal(s.aufrufe.filter((a) => /runde_anlegen$/.test(a.methode)).length, 0,
    'kein Aufruf, solange die Auswahl nicht gültig ist')

  // ZWEI Personen: gültig — jetzt legt die SEITE an (sie sendet, nicht der Dialog).
  kaestchen(kaesten()[1])
  await warte(6)
  const anlegen = anlegenKnopf()
  assert.equal(anlegen.disabled, false, 'zwei Personen + Name = gültig')
  klick(anlegen)
  await warte(10)
  const anlegenAufrufe = s.aufrufe.filter((a) => /runde_anlegen$/.test(a.methode))
  assert.equal(anlegenAufrufe.length, 1, 'genau EIN Anlegen-Aufruf')
  assert.equal(anlegenAufrufe[0].art, 'POST', 'runde_anlegen ist ein POST')
  assert.deepEqual(anlegenAufrufe[0].parameter,
    { titel: 'Samstag-Deko', mitglieder: ['M-9', 'M-10'] },
    'die Parameter heißen wie im Server: titel + die ANDEREN')
  s.abbaum()
})

test('CHAT-7b-UI · Seite: Runden-Aktionen am Handy im „⋯“-Muster (Punkt 9)', async () => {
  const handy = await seite({ hash: '#/nachrichten/CHAT-R-1', handy: true })
  // Am Handy stehen die zwei Aktionen NICHT als Knöpfe im Kopf, sondern im
  // vorhandenen `DkAktionen`-Menü — sonst läuft der Kopf bei 360 px über.
  assert.equal(knopfMit(handy.host, 'Person vorschlagen'), undefined,
    'am Handy kein eigener Knopf im Kopf')
  const ausloeser = handy.host.querySelector('.dk-chat-verlauf-kopf .dk-ui-aktionen-ausloeser')
  assert.ok(ausloeser, 'der „⋯“-Auslöser steht im Kopf (DkAktionen)')
  assert.equal(ausloeser.getAttribute('aria-haspopup'), 'menu')
  handy.abbaum()

  // Desktop: wie bisher zwei Knöpfe, kein „⋯“ für die Runde.
  const desktop = await seite({ hash: '#/nachrichten/CHAT-R-1' })
  assert.ok(knopfMit(desktop.host, 'Person vorschlagen'), 'am Desktop der Knopf')
  assert.ok(knopfMit(desktop.host, 'Runde verlassen'), 'am Desktop der zweite Knopf')
  assert.equal(desktop.host.querySelector('.dk-ui-aktionen-ausloeser'), null,
    'am Desktop kein zusätzliches „⋯“ am Rundenkopf')
  desktop.abbaum()
})

test('CHAT-7b-UI · Seite: Fehler beim Verlassen steht am Kopf, nicht im Verlauf (Punkt 8)', async () => {
  // Warum nicht über den Klick: `DkBestaetigung` gehört zum Gerüst der App
  // (`App.vue`), die hier allein gemountete Seite reicht die Rückfrage nur an
  // `bestaetigen()` weiter. Geprüft wird deshalb die Zusage, die der Befund
  // verlangt: es gibt eine EIGENE Stelle am Kopf (`role="status"`), und der
  // Verlauf wird bei einem Verlassen-Fehler nicht ersetzt. Die Quelle belegt
  // beides — `verlassenFehler` statt `verlaufFehler`.
  const quelle = readFileSync(join(SRC.pathname, 'pages/Nachrichten.vue'), 'utf8')
  const rumpf = quelle.slice(quelle.indexOf('async function rundeVerlassen'))
  const ende = rumpf.indexOf('// ── Melden')
  const fn = rumpf.slice(0, ende > 0 ? ende : 3000)
  assert.doesNotMatch(fn, /verlaufFehler\.value/, 'ein Verlassen-Fehler überschreibt NICHT den Verlauf')
  assert.match(fn, /verlassenFehler\.value/, 'er geht in die eigene Meldung')
  // Und die Meldung steht als ruhiger Hinweis AM KOPF — vor `verlaufFehler`.
  const vorlage = quelle.slice(0, quelle.indexOf('<p v-if="verlaufFehler"'))
  assert.match(vorlage, /<p v-if="verlassenFehler" class="dk-chat-hinweis" role="status">/,
    'der Hinweis steht am Kopf als role="status"')

  // Verhalten: die Seite baut mit einem scheiternden Verlassen weiter auf, der
  // Verlauf steht da (kein Ersetzen durch eine Fehlerzeile an seiner Stelle).
  const s = await seite({ hash: '#/nachrichten/CHAT-R-1' })
  assert.ok(s.host.querySelector('.dk-chat-nachrichten'), 'der Verlauf steht')
  assert.match(s.host.textContent, /Hallo/, 'mit Inhalt')
  assert.equal(s.host.querySelector('.dk-chat-fehler'), null, 'und ohne Fehlerzeile an seiner Stelle')
  s.abbaum()
})

test('CHAT-7b-UI · Seite: alter Dialogfehler steht beim erneuten Öffnen nicht da (Punkt 6)', async () => {
  // Die Seite öffnet „Neue Runde“ und „Person vorschlagen“ über eigene Wege,
  // die den alten Fehlertext leeren — ein Fehlschlag von vorhin darf nicht in
  // einem neuen Versuch stehen bleiben.
  const quelle = readFileSync(join(SRC.pathname, 'pages/Nachrichten.vue'), 'utf8')
  for (const [fn, feld] of [['rundeDialogOeffnen', 'rundeAnlegenFehler'],
    ['vorschlagDialogOeffnen', 'vorschlagAnlegenFehler']]) {
    const block = quelle.slice(quelle.indexOf(`function ${fn}(`), quelle.indexOf(`function ${fn}(`) + 260)
    assert.match(block, new RegExp(`${feld}\\.value = ''`), `${fn} leert ${feld}`)
  }
  // Jeder Weg in der VORLAGE ruft den Helfer (kein direktes Setzen am Dialog).
  const vorlage = quelle.slice(0, quelle.indexOf('<script'))
  assert.doesNotMatch(vorlage, /rundeDialogOffen = true/, 'die Vorlage setzt den Dialog nicht direkt')
  assert.doesNotMatch(vorlage, /vorschlagDialogOffen = true/, 'die Vorlage setzt den Vorschlags-Dialog nicht direkt')
  assert.equal((vorlage.match(/rundeDialogOeffnen/g) || []).length, 2,
    'beide Einstiege (Liste, Leerzustand) gehen über den Helfer')
  assert.equal((vorlage.match(/vorschlagDialogOeffnen/g) || []).length, 1,
    '„Person vorschlagen“ geht über den Helfer')
})

// ════════════════════════════════════════════════════════════════════════════
// D · Review-Nachbesserung CHAT-7b-UI-a-2: Stand kommt an, Fehler an der Zeile,
//     kein alter Hinweis im nächsten Gespräch
// ════════════════════════════════════════════════════════════════════════════

/** Eine Vorschlags-Systemzeile in der Form, die der Server liefert. */
const vorschlagsZeile = (stand, { eigene = false } = {}) => ({
  name: 'N-2', gespraech: 'CHAT-R-1', ident: 'N-2',
  text: 'Anna möchte Bert hinzufügen.',
  erstellt_am: '2026-11-18T10:01:00',
  system: { art: 'runde_vorschlag', stand, vorschlag: 'chat-vorschlag-V-1', eigene },
})

test('CHAT-7b-UI-a-2 · neuer Vorschlagsstand kommt durch `seiteEinordnen` an', () => {
  // Der Satz ist bei offen/angenommen wörtlich gleich — ohne Vergleich von
  // `system` hielte `zeileGleich` die Zeile für unverändert und die Knöpfe
  // blieben nach dem Zustimmen stehen.
  const offen = seiteEinordnen(
    { richtung: 'neueste', nachrichten: [vorschlagsZeile(STAND_OFFEN)] }, { alt: [] },
  )
  assert.equal(offen.nachrichten.length, 1, 'die Zeile steht da')
  assert.equal(offen.nachrichten[0].system.stand, STAND_OFFEN)
  assert.equal(vorschlagZeile(offen.nachrichten[0]).abstimmbar, true, 'offen → Knöpfe')

  // Der stille Abruf nach dem Zustimmen liefert DENSELBEN Satz, aber angenommen.
  const danach = seiteEinordnen(
    { richtung: 'neueste', nachrichten: [vorschlagsZeile(STAND_ANGENOMMEN)] },
    { alt: offen.nachrichten },
  )
  assert.equal(danach.aktualisiert, 1, 'die bekannte Zeile GILT als geändert (sonst bliebe der alte Stand)')
  assert.equal(danach.neuHinzugefuegt, 0, 'ein Stand ist kein neuer Beitrag')
  assert.equal(danach.nachrichten.length, 1)
  assert.equal(danach.nachrichten[0].system.stand, STAND_ANGENOMMEN, 'der neue Stand steht im Verlauf')
  const lage = vorschlagZeile(danach.nachrichten[0])
  assert.equal(lage.abstimmbar, false, 'angenommen → KEINE Knöpfe mehr')
  assert.equal(lage.standText, 'Angenommen.', 'der Stand steht ruhig da')

  // `system.eigene` hängt am LESENDEN: wird der Vorschlag plötzlich meiner
  // (andere Sicht), sind die Knöpfe ebenfalls weg.
  const meiner = seiteEinordnen(
    { richtung: 'neueste', nachrichten: [vorschlagsZeile(STAND_OFFEN, { eigene: true })] },
    { alt: offen.nachrichten },
  )
  assert.equal(meiner.aktualisiert, 1, 'eigene ist ein Unterschied')
  assert.equal(vorschlagZeile(meiner.nachrichten[0]).abstimmbar, false, 'am eigenen Vorschlag keine Knöpfe')

  // Unverändert heißt unverändert: derselbe Stand zählt NICHT als Neues.
  const gleich = seiteEinordnen(
    { richtung: 'neueste', nachrichten: [vorschlagsZeile(STAND_OFFEN)] },
    { alt: offen.nachrichten },
  )
  assert.equal(gleich.aktualisiert, 0, 'ohne Unterschied keine Änderung')
})

test('CHAT-7b-UI-a-2 · Zustimmen scheitert: Fehler steht an der Zeile, Knopf gesperrt', async () => {
  // Der Server antwortet 417 „bereits entschieden“ (Vertrag: eigene Stimme
  // oder Stand nicht mehr offen). Der Fehler gehört an DIESE Zeile.
  const fehler417 = Object.assign(new Error('bereits entschieden'), {
    status: 417, code: 'bereits_entschieden', titel: 'Bereits entschieden',
    text: 'Über diesen Vorschlag wurde schon abgestimmt.',
  })
  // Die Antwort des Servers wird OFFEN gehalten, bis der Lauf geprüft ist —
  // sonst hinge die Prüfung am Zufall der Zeitachse (der Fehlschlag ist sofort
  // da, der Zwischenstand wäre nie zu sehen).
  let antwort = null
  let loslassen = null
  const s = await seite({
    hash: '#/nachrichten/CHAT-R-1',
    server: async ({ kurz }) => {
      if (kurz === 'runde_zustimmen') {
        antwort = { ok: false }
        await new Promise((loese) => { loslassen = loese })
        throw fehler417
      }
      return null
    },
  })
  const systemZeile = s.host.querySelector('.dk-chat-system')
  assert.ok(systemZeile, 'die Vorschlagszeile steht im Verlauf')
  const zustimmen = knopfMit(systemZeile, 'Zustimmen')
  assert.ok(zustimmen, 'offen → der Knopf steht da')
  assert.equal(zustimmen.disabled, false)
  assert.equal(systemZeile.querySelector('[role="alert"]'), null, 'vorher steht kein Fehler da')

  klick(zustimmen)
  // Während des Laufs: die Knöpfe sind WEG (die Zeile sagt „Wird gesendet …“) —
  // so sperrt die Komponente den zweiten Klick. Vor dem Fix blieb der alte
  // Zustand stehen, weil `vorschlagLaeuft` unter `n.ident` statt
  // `system.vorschlag` gesucht wurde.
  for (let i = 0; i < 100; i += 1) {
    if (!knopfMit(systemZeile, 'Zustimmen')) break
    await new Promise((loese) => setTimeout(loese, 10))
  }
  assert.ok(loslassen, 'der Aufruf ging los')
  assert.equal(knopfMit(systemZeile, 'Zustimmen'), undefined,
    'während des Laufs ist kein Zustimmen-Knopf da (die Kennung ist `system.vorschlag`, nicht `n.ident`)')
  assert.equal(knopfMit(systemZeile, 'Ablehnen'), undefined, 'auch Ablehnen ist gesperrt')
  assert.match(systemZeile.textContent, /Wird gesendet …/, 'die Lade-Anzeige steht an der Zeile')
  assert.ok(antwort, 'der Aufruf läuft')
  // Ein zweiter Klick in dieser Lage löst nichts aus (kein Knopf, kein Aufruf).
  assert.equal(s.aufrufe.filter((a) => /runde_zustimmen$/.test(a.methode)).length, 1,
    'während des Laufs startet kein zweiter Aufruf')

  loslassen()
  await warte(20)
  assert.equal(s.aufrufe.filter((a) => /runde_zustimmen$/.test(a.methode)).length, 1,
    'genau EIN Aufruf — der gesperrte Knopf hat keinen zweiten ausgelöst')
  // Nach dem Fehlschlag: der Text steht als role="alert" AN DER ZEILE,
  // die Knöpfe sind wieder frei (ein zweiter Versuch darf sein).
  const meldung = s.host.querySelector('.dk-chat-system [role="alert"]')
  assert.ok(meldung, 'der Fehler steht an der Vorschlagszeile als role="alert"')
  assert.match(meldung.textContent, /schon abgestimmt|Bereits entschieden|bereits entschieden/i,
    'der Fehlertext des Servers, nicht eine erfundene Meldung')
  assert.equal(s.host.querySelector('.dk-chat-fehler'), null, 'NICHT als Verlaufsfehler (der Verlauf bleibt)')
  const wieder = knopfMit(systemZeile, 'Zustimmen')
  assert.ok(wieder, 'nach dem Lauf stehen die Knöpfe wieder da')
  assert.equal(wieder.disabled, false, 'nach dem Lauf wieder bedienbar (ein zweiter Versuch darf sein)')
  s.abbaum()
})

test('CHAT-7b-UI-a-2 · Gesprächswechsel räumt Verlassen- und Vorschlagsmeldungen weg', async () => {
  // Ein zweites Gespräch, in das gewechselt wird. `runde` ist die Antwort von
  // `meine_gespraeche` — die Attrappe von `seite` beantwortet sie selbst.
  const ZWEITE = { ...RUNDE, name: 'CHAT-R-2', titel: 'Andere Runde' }
  const s = await seite({
    hash: '#/nachrichten/CHAT-R-1',
    runde: [RUNDE, ZWEITE],
    server: ({ kurz }) => {
      if (kurz === 'runde_zustimmen') {
        throw Object.assign(new Error('bereits entschieden'),
          { status: 417, titel: 'Bereits entschieden', text: 'Über diesen Vorschlag wurde schon abgestimmt.' })
      }
      return null
    },
  })
  // 1) Der alte Hinweis: das Zustimmen scheitert, der Text steht an der Zeile.
  klick(knopfMit(s.host.querySelector('.dk-chat-system'), 'Zustimmen'))
  await warte(20)
  const meldung = s.host.querySelector('.dk-chat-system [role="alert"]')
  assert.ok(meldung, 'der Fehler steht zuerst an der Zeile')
  const alterText = meldung.textContent.trim()

  // 2) Gesprächswechsel INNERHALB der Seite: die Adresse zeigt auf das andere
  //    Gespräch, `hashGeaendert` liest sie nach, der Watcher auf
  //    `offeneKennung` öffnet neu (und räumt dabei über `zuruecksetzen` auf).
  dom.window.location.hash = '#/nachrichten/CHAT-R-2'
  dom.window.dispatchEvent(new dom.window.HashChangeEvent('hashchange'))
  await warte(40)
  assert.ok(s.aufrufe.some((a) => a.parameter?.gespraech === 'CHAT-R-2'),
    'das zweite Gespräch wurde wirklich geöffnet')

  // 3) Die Meldung des alten Gesprächs steht NICHT mehr da.
  assert.equal((s.host.textContent || '').includes(alterText), false,
    'der alte Vorschlagsfehler ist mit dem Gespräch gegangen')
  assert.equal(s.host.querySelector('.dk-chat-system [role="alert"]'), null,
    'im neuen Gespräch steht keine Meldung der alten Zeile')
  s.abbaum()
})

test('CHAT-7b-UI-a-2 · `zuruecksetzen` leert die Meldungen des alten Gesprächs', async () => {
  // Die Seite hat keine öffentliche Naht für den Gesprächswechsel mit
  // fehlgeschlagenem Verlassen (`DkBestaetigung` gehört zum Gerüst der App) —
  // geprüft wird deshalb der eine Weg, den der Befund verlangt: `zuruecksetzen`
  // leert `verlassenFehler`, `vorschlagFehler` und klappt die Teilnehmerliste zu.
  const quelle = readFileSync(join(SRC.pathname, 'pages/Nachrichten.vue'), 'utf8')
  const anfang = quelle.indexOf('function zuruecksetzen()')
  assert.ok(anfang > 0, '`zuruecksetzen` steht in der Seite')
  const rumpf = quelle.slice(anfang, quelle.indexOf('/** Gespräch öffnen', anfang))
  assert.match(rumpf, /verlassenFehler\.value = ''/, 'verlassenFehler wird geleert')
  assert.match(rumpf, /vorschlagFehler\.value = \{\}/, 'vorschlagFehler wird geleert')
  assert.match(rumpf, /vorschlagLaeuft\.value = ''/, 'ein hängender Laufzähler wird zurückgesetzt')
  assert.match(rumpf, /teilnehmerOffen\.value = false/, 'die Teilnehmerliste klappt wieder zu')
  // Und der Wechsel geht wirklich durch `zuruecksetzen` (kein zweiter Weg).
  const abOeffnen = quelle.slice(quelle.indexOf('async function oeffnen()'))
  const oeffnen = abOeffnen.slice(0, abOeffnen.indexOf('function verlaufLaden') > 0
    ? abOeffnen.indexOf('\n}\n') : 1200)
  assert.match(oeffnen, /zuruecksetzen\(\)/, 'das Öffnen räumt über `zuruecksetzen` auf')

  // Verhalten: ein Gespräch mit gescheitertem Zustimmen wechselt sauber —
  // im neuen Gespräch steht kein Fehlertext aus dem alten.
  const s = await seite({
    hash: '#/nachrichten/CHAT-R-1',
    server: ({ kurz }) => {
      if (kurz === 'runde_zustimmen') {
        throw Object.assign(new Error('bereits entschieden'),
          { status: 417, titel: 'Bereits entschieden', text: 'Über diesen Vorschlag wurde schon abgestimmt.' })
      }
      return null
    },
  })
  klick(knopfMit(s.host.querySelector('.dk-chat-system'), 'Zustimmen'))
  await warte(20)
  assert.ok(s.host.querySelector('.dk-chat-system [role="alert"]'), 'der Fehler stand da')
  s.abbaum()
})
