/**
 * UX-C3b — Plantyp-Editor: Auswahllisten statt Freitext (Befund DMB-674355ec0e2b).
 *
 * Befund (16.10.): „wo man bestimmte dinge exakt referenzieren muss, soll
 * keine freitexteingabe sondern auswahl über dropdown geschehen“.
 *
 * Was hier ohne Browser geprüft wird:
 *
 *  1. ALTWERT-REGEL — ein gespeicherter Wert, den die Liste nicht kennt, geht
 *     beim Öffnen NICHT verloren: er steht als eigene Option da und wird als
 *     „unbekannter Wert“ benannt (Optionsliste UND Warnhinweis).
 *  2. QUELLEN — die Auswahllisten kommen aus der Definition bzw. vom Server
 *     (Felder, Feldpfade, Sammlungen, Merkmale, Anlässe, Varianten, Gruppen,
 *     fremde Planvorlagen) und enthalten den gespeicherten Wert immer.
 *  3. MARKUP — die Komponenten nutzen die Auswahl statt Freitext: PrAuswahl
 *     an Baustein/Stufe/Sammlung/Gruppe/Bezugsfeld/Knoten/Rolle/Format,
 *     keine `datalist`-Notlösung mehr.
 *  4. HAUSREGELN — nur Tokens (keine harten Farbwerte), keine erfundenen
 *     Kataloge: die Bausteine/Stufen kommen aus Registry/Editor.
 *  5. SPRUNGZIEL „Felder“ (Operator-Zusatz aus Review UX-C3a) — bei mehreren
 *     Terminreihen sitzt die Kennung an der Feld-Überschrift der ersten Reihe,
 *     damit der Klick auf „Felder“ nicht ins Leere läuft.
 *  6. TEST IST IM IMAGE — die neue Datei steht in der node-Testliste der
 *     backend/Dockerfile.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ERKLAERUNGEN, erklaerung, zielId,
} from '../src/diakonos/components/planrahmen/abschnitte.mjs'
import {
  ANDERER_WERT, ANDERER_WERT_TEXT, UNBEKANNT, anlassOptionen, auswahlMitAltwert,
  bekannteWerte, bezugOptionen, feldOptionen, feldPfadOptionen, gruppenOptionen,
  istUnbekannt, mitAnderemWert, nameZu, option, personenMerkmalOptionen,
  plantypOptionen, sammlungOptionen, unbekanntAmPfad, varianteOptionen, wertAuswahl,
} from '../src/diakonos/components/planrahmen/auswahl.mjs'
import {
  feldPfadListe, jsonText, jsonUebernehmen,
} from '../src/diakonos/components/planrahmen/editor.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')
const datei = (p) => new URL(p, root)

const AUSWAHL = lies('components/planrahmen/auswahl.mjs')
const KOMPONENTE = lies('components/planrahmen/PrAuswahl.vue')
const REGELN = lies('components/planrahmen/PrRegelnEditor.vue')
const FELDER = lies('components/planrahmen/PrFelderEditor.vue')
const KNOTEN = lies('components/planrahmen/PrKnotenEditor.vue')
const DEKLARATIONEN = lies('components/planrahmen/PrDeklarationenEditor.vue')
const ANSICHTEN = lies('components/planrahmen/PrAnsichtenEditor.vue')
const REIHEN = lies('components/planrahmen/PrReihenEditor.vue')
const SEITE = lies('pages/planrahmen/PlantypEditor.vue')
const INFO = lies('components/planrahmen/PrInfo.vue')
const ABSCHNITTE = lies('components/planrahmen/abschnitte.mjs')

// Im Image liegt nur frontend/ (/build) — die Dockerfile steht dort NICHT.
// Geprüft wird der Eintrag, wo die Datei erreichbar ist (Worktree); im Image
// ist der Nachweis, dass dieser Test ÜBERHAUPT läuft.
const DOCKERFILE_PFAD = new URL('../../backend/Dockerfile', import.meta.url)
const DOCKERFILE = existsSync(DOCKERFILE_PFAD) ? readFileSync(DOCKERFILE_PFAD, 'utf8') : ''

/** Eine Beispiel-Definition mit zwei Terminreihen (der schwierige Fall). */
function definition() {
  return {
    schema: 'diakronos/plantyp@1',
    id: 'chorplan',
    name: 'Chorplan',
    parameter: [
      { id: 'zeitraum', name: 'Zeitraum', art: 'zeitraum' },
      { id: 'themenreihe', name: 'Themenreihe', art: 'auswahl', werte: ['psalmen', 'gebet'] },
    ],
    sammlungen: [{ id: 'bibelarbeiten', name: 'Bibelarbeiten', umfang: 'gemeinde' }],
    merkmale: {
      person: [{ id: 'dirigent', name: 'dirigiert', art: 'tag' }],
      lieder: [{ id: 'thema', name: 'Thema', art: 'text' }],
    },
    termine: {},
    // KEIN `felder` auf oberster Ebene: Reihenfelder tragen dann das Präfix
    // `<reihe>:` (ein leeres Array heißt Kurzform und schließt Reihen aus).
    anlaesse: [{ id: 'abendmahl', name: 'Abendmahl' }],
    terminreihen: [
      {
        id: 'standard',
        name: 'Hauptreihe',
        termine: {},
        felder: [
          {
            id: 'lieder', name: 'Lieder', art: 'eintrag', sammlung: 'lieder', anzahl: '1..*',
            inhalt: [{ id: 'zugabe', name: 'Zugabe', art: 'text' }],
          },
          { id: 'team', name: 'Team', art: 'team', teams: { gruppe_unter: 'Musikteams' } },
        ],
      },
      {
        id: 'probe',
        name: 'Probe',
        termine: {},
        felder: [
          { id: 'einueben', name: 'Einüben', art: 'eintrag', sammlung: 'lieder' },
          { id: 'variante_wetter', name: 'Wetter', art: 'gruppe', inhalt: [], varianten: [{ id: 'sonne', name: 'Sonne' }] },
        ],
      },
    ],
    regeln: [{ baustein: 'mindestabstand', feld: 'lieder', wochen: 8 }],
    ansichten: [{ art: 'tabelle', name: 'Aushang', spalten: ['lieder'] }],
  }
}

// ── 1 · Altwert-Regel ──────────────────────────────────────────────────────

test('UX-C3b: ein unbekannter Altwert bleibt als Option sichtbar', () => {
  const optionen = [option('chor', 'Chor'), option('solo', 'Solo')]
  const liste = auswahlMitAltwert(optionen, 'posaunenchor')
  const alt = liste.find((o) => o.unbekannt)
  assert.ok(alt, 'Altwert fehlt in der Liste — er wäre beim Öffnen verloren')
  assert.equal(alt.wert, 'posaunenchor')
  assert.match(alt.text, /unbekannter Wert/)
  // Der gespeicherte Wert ist wählbar (die Auswahl zeigt ihn an).
  assert.ok(liste.some((o) => o.wert === 'posaunenchor'))
  // Bekannte Werte bleiben unverändert.
  assert.deepEqual(liste.filter((o) => !o.unbekannt).map((o) => o.wert), ['chor', 'solo'])
})

test('UX-C3b: bekannter Wert erzeugt KEINE Altwert-Zeile', () => {
  const optionen = [option('chor', 'Chor'), option('solo', 'Solo')]
  const liste = auswahlMitAltwert(optionen, 'chor')
  assert.equal(liste.filter((o) => o.unbekannt).length, 0)
  assert.equal(istUnbekannt(optionen, 'chor'), false)
  assert.equal(istUnbekannt(optionen, 'posaunenchor'), true)
  assert.equal(istUnbekannt(optionen, ''), false)
  assert.equal(istUnbekannt(optionen, undefined), false)
})

test('UX-C3b: leere Option nur mit leerName, Altwert trotzdem sichtbar', () => {
  const optionen = [option('chor', 'Chor')]
  const mitLeer = auswahlMitAltwert(optionen, 'gospel', { leerName: '— keinen Bereich —' })
  assert.equal(mitLeer[0].wert, '')
  assert.equal(mitLeer[0].text, '— keinen Bereich —')
  assert.ok(mitLeer.some((o) => o.unbekannt && o.wert === 'gospel'))
  const ohneLeer = auswahlMitAltwert(optionen, '')
  assert.equal(ohneLeer.length, 1)
  assert.equal(bekannteWerte(ohneLeer).has(''), false)
})

test('UX-C3b: der Altwert-Text ist verständlich, nicht die nackte Kennung', () => {
  const liste = auswahlMitAltwert([option('a', 'A')], 'kaputt', { unbekanntName: 'nicht in dieser Vorlage' })
  const alt = liste.find((o) => o.unbekannt)
  assert.equal(alt.text, 'kaputt (nicht in dieser Vorlage)')
  assert.equal(alt.hinweis, 'kaputt (nicht in dieser Vorlage)')
})

test('UX-C3b: nameZu nennt den Anzeigenamen, sonst die Kennung', () => {
  const optionen = [{ kennung: 'a', name: 'Anlass A' }, { kennung: 'b', name: 'Anlass B' }]
  assert.equal(nameZu(optionen, 'b'), 'Anlass B')
  assert.equal(nameZu(optionen, 'x'), 'x')
  assert.equal(nameZu(optionen, 'x', 'unbekannt'), 'unbekannt')
})

// ── 2 · Quellen aus der Definition ────────────────────────────────────────

test('UX-C3b: Felder beider Terminreihen sind wählbar, zweite Reihe mit Präfix', () => {
  const optionen = feldOptionen(definition())
  const werte = optionen.map((o) => o.wert)
  assert.ok(werte.includes('lieder'), 'Feld der Hauptreihe fehlt')
  assert.ok(werte.includes('probe:einueben'), 'Feld der zweiten Reihe fehlt ohne Präfix — der Verweis wäre mehrdeutig')
  // Die Hauptreihe trägt kein Präfix (der Server prüft beide Formen).
  assert.ok(!werte.includes('standard:lieder'))
})

test('UX-C3b: Feldpfade enthalten Unterfelder („Feld dort“/Format)', () => {
  const optionen = feldPfadOptionen(definition(), feldPfadListe)
  const werte = optionen.map((o) => o.wert)
  assert.ok(werte.includes('lieder'))
  assert.ok(werte.includes('lieder.zugabe'), 'Unterfeldpfad fehlt (Formatvorlage/„nicht gleichzeitig“)')
  assert.ok(werte.includes('probe:einueben'))
})

test('UX-C3b: Sammlungen nennen „lieder“ eingebaut und die eigenen Listen', () => {
  const optionen = sammlungOptionen(definition())
  assert.equal(optionen[0].wert, 'lieder')
  assert.ok(optionen.some((o) => o.wert === 'bibelarbeiten'))
  // Eine Definition ohne eigene Listen bietet trotzdem „lieder“ an.
  assert.deepEqual(sammlungOptionen({}).map((o) => o.wert), ['lieder'])
})

test('UX-C3b: Personen-Merkmale, Anlässe und Varianten als Auswahl', () => {
  const def = definition()
  assert.deepEqual(personenMerkmalOptionen(def).map((o) => o.wert), ['dirigent'])
  assert.deepEqual(anlassOptionen(def).map((o) => o.wert), ['abendmahl'])
  assert.deepEqual(varianteOptionen(def).map((o) => o.wert), ['sonne'])
})

test('UX-C3b: fremde Planvorlagen ohne die eigene', () => {
  const typen = [
    { id: 'chorplan', schluessel: 'chorplan', name: 'Chorplan' },
    { id: 'freizeit', schluessel: 'freizeit', name: 'Freizeit' },
    { name: 'ohne Kennung' },
  ]
  const optionen = plantypOptionen(typen, 'chorplan')
  assert.deepEqual(optionen.map((o) => o.wert), ['freizeit'])
  assert.match(optionen[0].text, /Freizeit/)
})

test('UX-C3b: Gruppen aus einrichten_rechte, Bezugsfelder aus Merkmalen und Pfaden', () => {
  assert.deepEqual(gruppenOptionen([{ kennung: 'Musikteams', name: 'Musikteams' }]).map((o) => o.wert), ['Musikteams'])
  const bezug = bezugOptionen(definition()).map((o) => o.wert)
  assert.ok(bezug.includes('eintrag.thema'), 'Eigenschaft des Listeneintrags fehlt')
  assert.ok(bezug.includes('lieder'), 'Feldpfad als Bezug fehlt')
  assert.ok(bezug.includes('bezug.lieder'))
})

test('UX-C3b: unbekannte Prüfcodes werden am Pfad erkannt', () => {
  const meldungen = [
    { pfad: '/regeln/0/feld', code: 'unbekanntes_regel_feld', stufe: 'fehler' },
    { pfad: '/felder/0/sammlung', code: 'unbekannte_sammlung', stufe: 'fehler' },
    { pfad: '/regeln/0/feld', code: 'regel_parameter', stufe: 'fehler' },
  ]
  assert.equal(unbekanntAmPfad(meldungen, 'regeln/0/feld').length, 1)
  assert.equal(unbekanntAmPfad(meldungen, '/regeln/0/feld').length, 1)
  assert.equal(unbekanntAmPfad(meldungen, 'felder/0/sammlung')[0].code, 'unbekannte_sammlung')
  assert.equal(unbekanntAmPfad(meldungen, 'anderer/pfad').length, 0)
})

// ── 3 · Markup: Auswahl statt Freitext ────────────────────────────────────

test('UX-C3b: die Auswahlkomponente zeigt den Altwert und warnt darunter', () => {
  assert.match(KOMPONENTE, /import \{ ANDERER_WERT, UNBEKANNT, istUnbekannt, mitAnderemWert \} from '\.\/auswahl\.mjs'/)
  // Der Altwert erscheint als Eintrag „Anderer Wert …“ (wertAuswahl) und steht
  // im Textfeld darunter — beides über die Helfer in auswahl.mjs belegt.
  assert.match(KOMPONENTE, /ANDERER_WERT/)
  assert.match(KOMPONENTE, /v-if="unbekannt"[^>]*role="status"/)
  assert.match(KOMPONENTE, /aria-invalid="unbekannt \? 'true' : undefined"/)
  // Keine harten Farben (Hausregel: nur Tokens).
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(KOMPONENTE), 'feste Farbe in PrAuswahl.vue')
  assert.ok(!/rgb\(/.test(KOMPONENTE))
})

test('UX-C3b: Regeln — Baustein, Stufe, Feld, Sammlung, Planvorlage sind Auswahl', () => {
  assert.match(REGELN, /<PrAuswahl\s+class="pr-rg-baustein"/)
  assert.match(REGELN, /<PrAuswahl\s+class="pr-rg-stufe"/)
  // Feld, Übungsfeld, fremde Plantypen und Feldpfade sind Kennungen.
  assert.match(REGELN, /FELD_PARAMETER = new Set\(\['feld', 'uebungsfeld'\]\)/)
  assert.match(REGELN, /if \(feld\.name === 'auch_in'\) return plantypAuswahl\.value/)
  assert.match(REGELN, /if \(feld\.name === 'felder'\) return pfadAuswahl\.value/)
  // Listen-Referenzen sind Chips; der Altwert bleibt als Zeile sichtbar.
  assert.match(REGELN, /v-for="u in unbekannteListenWerte\(r, feld\)"/)
  assert.match(REGELN, /unbekannter Wert/)
  // Kein Komma-Freitext mehr für Listen (nur noch die freie Restliste).
  assert.match(REGELN, /v-if="!listenOptionen\(feld\)\.length \|\| freieListe\(feld\)"/)
})

test('UX-C3b: Felder — Sammlung, Obergruppe und Bezugsfeld sind Auswahl', () => {
  assert.match(FELDER, /<PrAuswahl\s+:model-value="f\.sammlung"/)
  assert.match(FELDER, /<PrAuswahl\s+:model-value="f\.teams\?\.gruppe_unter \|\| ''"/)
  assert.match(FELDER, /:model-value="f\.aus"/)
  // Die datalist-Notlösung ist weg, der Hinweis auf {parameter.x} bleibt.
  assert.ok(!/datalist id="pr-fb-sammlungen"/.test(FELDER))
  assert.match(FELDER, /\{parameter\.x\}/)
})

test('UX-C3b: Knoten — Anlass, Variante, Merkmal, Gruppe, Parameterwert sind Auswahl', () => {
  for (const key of ['anlass', 'variante', 'feld_gesetzt', 'merkmal', 'gruppe', 'anmeldung']) {
    assert.match(KNOTEN, new RegExp(`key === '${key}'`), `${key} ohne Auswahlquelle`)
  }
  assert.match(KNOTEN, /const auswahlQuelle = computed/)
  assert.match(KNOTEN, /parameterWerte\.length/)
})

test('UX-C3b: Deklarationen und Ansichten — Rollenreferenz und Format-Schlüssel', () => {
  assert.match(DEKLARATIONEN, /<PrAuswahl\s+:model-value="rollenKennung\(m\.rolle\)"/)
  assert.match(DEKLARATIONEN, /rollenAuswahl = computed/)
  assert.match(ANSICHTEN, /<PrAuswahl\s+class="pr-an-schluessel"/)
  assert.match(ANSICHTEN, /unbekannteSpalten\(a\)/)
  assert.ok(!/datalist id="pr-an-feldpfade"/.test(ANSICHTEN))
})

test('UX-C3b: die Seite liefert den Bausteinen die Auswahlquellen', () => {
  assert.match(SEITE, /definition: definition\.value/)
  assert.match(SEITE, /gruppen: gruppenAuswahl\.value/)
  assert.match(SEITE, /plantypen: plantypAuswahl\.value/)
  assert.match(SEITE, /eigenerPlantyp: definition\.value\.id \|\| ''/)
  assert.match(SEITE, /import \{ plantypOptionen \} from '\.\.\/\.\.\/components\/planrahmen\/auswahl\.mjs'/)
})

// ── 4 · Sprungziel „Felder“ bei mehreren Terminreihen ────────────────────

test('UX-C3b: „Felder“-Sprungziel hängt bei mehreren Reihen an der ersten', () => {
  // Die Kennung darf GENAU EINMAL vergeben sein (Dubletten brechen den Sprung)
  // und sie muss auch ohne Kurzform existieren.
  assert.match(REIHEN, /:id="ri === 0 && felderAnker \? felderAnker : undefined"/)
  assert.match(REIHEN, /:data-abschnitt="ri === 0 && felderAnker \? felderAnker : undefined"/)
  // Die Kurzform behält ihr Ziel an „Felder pro Termin“.
  assert.match(REIHEN, /<h4 class="pr-re-titel" :id="felderAnker \|\| undefined"/)
  // Kein zweites Element mit derselben Kennung in der Seite selbst.
  assert.equal((SEITE.match(/:id="zielId\('felder'\)"/g) || []).length, 0)
  assert.match(SEITE, /:felder-anker="zielId\('felder'\)"/)
  // Sprungziel braucht den Abstand zur Lesekante (sonst klebt es am Band).
  const css = REIHEN.slice(REIHEN.indexOf('<style scoped>'))
  assert.match(css, /\.pr-re-unter-titel \{[^}]*scroll-margin-top/)
})

// ── 5 · Hausregeln ────────────────────────────────────────────────────────

test('UX-C3b: keine harten Farben in den geänderten Bausteinen', () => {
  for (const [name, text] of Object.entries({ REGELN, FELDER, KNOTEN, DEKLARATIONEN, ANSICHTEN, REIHEN })) {
    const stil = text.slice(text.indexOf('<style scoped>'))
    assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(stil), `${name}: feste Farbe im Stil`)
    assert.ok(!/\brgba?\(/.test(stil), `${name}: rgb()-Farbe im Stil`)
  }
})

test('UX-C3b: Kataloge kommen aus Editor/Registry, nicht aus der Seite', () => {
  // Bausteine: Registry (x-regel-bausteine), Stufen: editor.mjs STUFEN.
  assert.match(REGELN, /Object\.keys\(props\.bausteine \|\| \{\}\)/)
  assert.match(REGELN, /STUFEN\.map\(\(s\) => option\(s\.wert, s\.name\)\)/)
  assert.ok(!/\[.?mindestabstand.?\]/.test(REIHEN))
})

// ── 6 · ⓘ am Feld (Befund: „info button zum drüberhovern“) ──────────────

test('UX-C3b: ⓘ erklärt das Feld und holt den Text aus dem Glossar', () => {
  // Der Knopf nennt seinen Begriff, ist für Tastatur erreichbar und zeigt den
  // Text beim Überfahren UND bei Fokus (kein reines Hover-Wissen).
  assert.match(INFO, /aria-describedby="hilfeId"/)
  assert.match(INFO, /aria-expanded="offen \? 'true' : 'false'"/)
  assert.match(INFO, /@keydown\.escape="offen = false"/)
  assert.match(INFO, /import \{ erklaerung, PLATZHALTER \} from '\.\/abschnitte\.mjs'/)
  const css = INFO.slice(INFO.indexOf('<style scoped>'))
  assert.match(css, /\.pr-info:hover \.pr-info-text/)
  assert.match(css, /\.pr-info:focus-within \.pr-info-text/)
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(css), 'feste Farbe in PrInfo.vue')
})

test('UX-C3b: jedes ⓘ-Feld hat einen Glossareintrag', () => {
  const kennungen = new Set(ERKLAERUNGEN.map((e) => e.id))
  for (const id of ['sammlung', 'bezugsfeld', 'baustein', 'anlasswert', 'variante',
    'eingebaute_liste', 'fremde_vorlage', 'dienstbereich']) {
    assert.ok(kennungen.has(id), `Glossareintrag ${id} fehlt`)
    assert.ok(erklaerung(id)?.text?.length > 30, `${id}: Erklärung zu kurz`)
    assert.ok(erklaerung(id)?.quelle, `${id}: Quelle fehlt`)
  }
  // Die Bausteine setzen die Kennungen auch wirklich ein.
  assert.match(REGELN, /info="baustein"/)
  assert.match(REGELN, /info="fremde_vorlage"/)
  assert.match(FELDER, /info="sammlung"/)
  assert.match(FELDER, /info="bezugsfeld"/)
  assert.match(KNOTEN, /:info="auswahlQuelle\.info"/)
  assert.match(SEITE, /<PrInfo id="dienstbereich" \/>/)
  // Die Erklärspalte bleibt dieselbe Quelle (C3a) — kein zweites Glossar.
  assert.match(ABSCHNITTE, /export function erklaerung/)
})

test('UX-C3b: die neue Testdatei steht in der Dockerfile-Testliste', () => {
  assert.ok(existsSync(datei('components/planrahmen/auswahl.mjs')))
  if (!DOCKERFILE) return   // Image: frontend/ allein, keine Dockerfile
  assert.match(DOCKERFILE, /tests\/uxc3b-\*\.test\.mjs/)
})

// ── 7 · Review-Nacharbeit: „Anderer Wert …“ statt leerer Auswahl ─────────
//
// Operator-Entscheidung: eine Auswahl zeigt die bekannten Werte UND den
// Eintrag „Anderer Wert …“, der ein Textfeld öffnet; ist die Liste leer, steht
// direkt das Textfeld da. Nie eine leere, unbedienbare Auswahl.

test('UX-C3b: „Anderer Wert …“ steht in jeder Liste mit bekannten Werten', () => {
  const liste = mitAnderemWert([option('chor', 'Chor'), option('solo', 'Solo')])
  assert.equal(liste.length, 3)
  assert.equal(liste.at(-1).wert, ANDERER_WERT)
  assert.equal(liste.at(-1).text, ANDERER_WERT_TEXT)
  // Die bekannten Werte bleiben unverändert und in ihrer Reihenfolge.
  assert.deepEqual(liste.slice(0, 2).map((o) => o.wert), ['chor', 'solo'])
  // Skalare werden genau wie Objekte behandelt.
  assert.deepEqual(mitAnderemWert(['a']).map((o) => o.wert), ['a', ANDERER_WERT])
})

test('UX-C3b: wertAuswahl — leere Liste zeigt das Textfeld, nie eine leere Auswahl', () => {
  const leer = wertAuswahl([], '')
  assert.equal(leer.modus, 'text')
  assert.equal(leer.leer, true)
  assert.deepEqual(leer.optionen, [])
  // Auch ein gespeicherter Altwert landet im Textfeld und geht nicht verloren.
  const leerMitAlt = wertAuswahl([], 'posaunenchor')
  assert.equal(leerMitAlt.modus, 'text')
  assert.equal(leerMitAlt.text, 'posaunenchor')
  assert.equal(leerMitAlt.altwert, true)
})

test('UX-C3b: wertAuswahl — bekannter Wert = Liste, unbekannter = „Anderer Wert …“', () => {
  const optionen = [option('chor', 'Chor'), option('solo', 'Solo')]
  const bekannt = wertAuswahl(optionen, 'chor')
  assert.equal(bekannt.modus, 'liste')
  assert.equal(bekannt.altwert, false)
  assert.equal(bekannt.text, 'chor')
  assert.ok(bekannt.optionen.some((o) => o.wert === ANDERER_WERT))

  const alt = wertAuswahl(optionen, 'posaunenchor')
  assert.equal(alt.modus, 'anderer', 'Altwert muss „Anderer Wert …“ auswählen')
  assert.equal(alt.altwert, true)
  assert.equal(alt.text, 'posaunenchor', 'der gespeicherte Wert steht im Textfeld')

  // Ohne Wert ist es die Liste (der leere Eintrag kommt über `platzhalter`).
  assert.equal(wertAuswahl(optionen, undefined).modus, 'liste')
  assert.equal(wertAuswahl(optionen, '').modus, 'liste')
})

test('UX-C3b: PrAuswahl bietet „Anderer Wert …“ und bei leerer Liste ein Textfeld', () => {
  const template = KOMPONENTE.slice(0, KOMPONENTE.indexOf('<script setup>'))
  assert.match(KOMPONENTE, /andererWert: Boolean/)
  // WICHTIG (im Image bemerkt): der Eintrag muss das `<select>` auch
  // RENDERN. Über `props.optionen` allein erschien er nirgends — die
  // Liste kam aus der Definition, „Anderer Wert …“ fehlte im Betrieb.
  assert.match(KOMPONENTE, /<option v-for="o in optionenMitEigenem"/)
  assert.match(KOMPONENTE, /const optionenMitEigenem = computed\(\(\) => \(mitEigenem\.value/)
  assert.match(KOMPONENTE, /\? mitAnderemWert\(props\.optionen\) : props\.optionen/)
  // Leere Liste → Eingabefeld statt `<select>`.
  assert.match(template, /v-if="textModus"[\s\S]{0,220}class="dk-form-input/)
  assert.match(template, /<select[\s\S]{0,80}v-else/)
  // Eigener Wert erscheint nach Wahl von „Anderer Wert …“ bzw. bei Altwert.
  assert.match(template, /v-if="andererEingabe"[\s\S]{0,200}pr-auswahl-eigener/)
  // Die Auswahl zeigt bei Altwert den Eintrag „Anderer Wert …“.
  assert.match(KOMPONENTE, /andererEingabe\.value \? ANDERER_WERT : gespeichert\.value/)
  // Keine harten Farben (Hausregel).
  const css = KOMPONENTE.slice(KOMPONENTE.indexOf('<style scoped>'))
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(css), 'feste Farbe in PrAuswahl.vue')
  assert.ok(!/\brgba?\(/.test(css))
})

test('UX-C3b: keine Auswahl im Editor bleibt ohne „anderer-wert“ (leere Liste bedienbar)', () => {
  // Jede PrAuswahl der drei Baukästen, deren Liste leer sein KANN (fremde
  // Felder, Obergruppen ohne Gruppen, {parameter.x}), bietet „Anderer Wert …“.
  for (const [name, text] of Object.entries({ REGELN, FELDER, KNOTEN })) {
    const stellen = text.match(/<PrAuswahl[\s\S]*?\/>/g) || []
    for (const stelle of stellen) {
      assert.match(stelle, /anderer-wert/, `${name}: PrAuswahl ohne „anderer-wert“:\n${stelle.slice(0, 160)}`)
    }
  }
})

// ── 8 · Review Punkt 1: String-Kennungen sind Auswahl, kein Freitext ─────

test('UX-C3b: feld, uebungsfeld und merkmal sind auch als String Auswahl', () => {
  // Die Registry deklariert diese Parameter als `type: string` (ohne enum) —
  // der Editor muss sie trotzdem als Auswahl aus der Definition darstellen.
  assert.match(REGELN, /FELD_PARAMETER = new Set\(\['feld', 'uebungsfeld'\]\)/)
  assert.match(REGELN, /MERKMAL_PARAMETER = new Set\(\['merkmal'\]\)/)
  assert.match(REGELN, /function istKennung\(feld\)/)
  assert.match(REGELN, /feld\?\.typ === 'text' && \(FELD_PARAMETER\.has\(feld\.name\) \|\| MERKMAL_PARAMETER\.has\(feld\.name\)\)/)
  assert.match(REGELN, /function kennungOptionen\(feld\)/)
  assert.match(REGELN, /if \(FELD_PARAMETER\.has\(feld\.name\)\) return feldAuswahl\.value/)
  assert.match(REGELN, /if \(MERKMAL_PARAMETER\.has\(feld\.name\)\) return merkmalAuswahl\.value/)
  // Der Zweig steht VOR dem Freitext-Feld (v-else), sonst gewinnt `<input>`.
  const kennung = REGELN.indexOf("v-else-if=\"kennungOptionen(feld).length || istKennung(feld)\"")
  const freitext = REGELN.indexOf('<!-- Freier Text -->')
  assert.ok(kennung > 0 && freitext > kennung, 'Kennungs-Auswahl muss vor dem Freitext stehen')
  // Gesetzt wird die Kennung als Text; leer entfernt den Parameter.
  assert.match(REGELN, /function kennungSetzen\(regel, name, wert\)/)
})

test('UX-C3b: Review Punkt 4 — aria-label der Auswahl ist der Parametername', () => {
  // Kein generisches „Auswahl“ mehr; der Name kommt aus PARAM_NAMEN.
  assert.ok(!/aria-label="Auswahl"/.test(REGELN), 'generisches aria-label „Auswahl“ in PrRegelnEditor')
  assert.match(REGELN, /:aria-label="paramName\(feld\)"/)
  assert.match(REGELN, /function paramName\(feld\) \{ return PARAM_NAMEN\[feld\.name\] \|\| feld\.name \}/)
  assert.match(REGELN, /PARAM_NAMEN = \{[\s\S]*feld: 'Feld'/)
  assert.match(REGELN, /merkmal: 'Angabe des Eintrags'/)
  // Knoten: das Label nennt das Kriterium, nicht den Platzhaltertext.
  assert.match(KNOTEN, /:aria-label="wertName"/)
  assert.match(KNOTEN, /const wertName = computed/)
})

// ── 9 · Review Punkt 3: echter Round-Trip mit unbekanntem Altwert ────────
//
// Regex-Prüfungen reichen nicht: die Definition wird geladen, die Formulare
// werden an allen Stellen angefasst, die einen Altwert darstellen, und danach
// serialisiert — der Altwert muss unverändert wieder herauskommen.

test('UX-C3b: unbekannte Altwert-Definition übersteht Laden und Serialisieren', () => {
  const alt = {
    schema: 'diakronos/plantyp@1',
    id: 'altplan',
    name: 'Alter Plan',
    parameter: [{ id: 'themenreihe', name: 'Themenreihe', art: 'auswahl', werte: ['psalmen'] }],
    sammlungen: [],
    merkmale: { person: [{ id: 'dirigent', name: 'dirigiert', art: 'tag' }] },
    anlaesse: [{ id: 'abendmahl', name: 'Abendmahl' }, { id: 'taufe', name: 'Taufe' }],
    felder: [{ id: 'lieder', name: 'Lieder', art: 'eintrag', sammlung: 'posaunenarchiv' }],
    regeln: [
      // Altwert im Einzel-Feld (String-Variante, Review Punkt 1).
      { baustein: 'mindestabstand', feld: 'gibtsnicht', wochen: 8 },
      // Altwert im Einzel-Merkmal.
      { baustein: 'passend_zum_anlass', feld: 'lieder', merkmal: 'altmerkmal' },
      // Altwert in einer Liste und ein bekannter Wert daneben.
      { baustein: 'nicht_gleichzeitig', felder: ['gibtsnicht', 'lieder'] },
      // Altwert im planübergreifenden Verweis.
      { baustein: 'vorher_geuebt', feld: 'lieder', uebung: { plantyp: 'altvorlage', feld: 'altfeld' } },
      // Altwert im Auswahl-Parameter (Bedingung).
      { baustein: 'max_pro_zeitraum', anzahl: 2, zeitraum: 'quartal' },
    ],
  }
  // 1) Laden: der Rohstand ist nach dem Parsen unverändert.
  const geladen = jsonUebernehmen(jsonText(alt))
  assert.equal(geladen.ok, true)
  assert.deepEqual(geladen.definition, alt)

  // 2) Darstellen: jede Auswahl nimmt den Altwert mit (statt ihn zu verwerfen).
  const felderAus = feldOptionen(geladen.definition)
  assert.equal(wertAuswahl(felderAus, 'gibtsnicht').modus, 'anderer')
  assert.equal(wertAuswahl(felderAus, 'gibtsnicht').text, 'gibtsnicht')
  assert.equal(wertAuswahl(personenMerkmalOptionen(geladen.definition), 'altmerkmal').modus, 'anderer')
  assert.equal(wertAuswahl(sammlungOptionen(geladen.definition), 'posaunenarchiv').modus, 'anderer')
  assert.equal(wertAuswahl(plantypOptionen([], 'altplan'), 'altvorlage').modus, 'text')
  // Bekannte Werte bleiben in der Liste (kein falsches „unbekannt“).
  assert.equal(wertAuswahl(felderAus, 'lieder').modus, 'liste')
  assert.equal(wertAuswahl(sammlungOptionen(geladen.definition), 'lieder').modus, 'liste')

  // 3) Serialisieren: Byte-gleich — nichts geht verloren, nichts wird erfunden.
  assert.equal(jsonText(geladen.definition), jsonText(alt))
  assert.deepEqual(JSON.parse(jsonText(geladen.definition)), alt)
})
