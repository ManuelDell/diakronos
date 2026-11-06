/**
 * UX1f — EIN Knopf-System, Teil 2: Personen, Gruppen, Registrierung, Gast.
 *
 * Geprüft wird, was die Karte zusagt:
 *
 *   F1  Kein Alt-Knopf mehr im Bereich. Die Fundstellen der alten Klassen
 *       (`.dk-btn*`, `.btn-*`) und der rohen `<button>`-Elemente in
 *       `pages/mitglieder/**`, `components/mitglieder/**`,
 *       `pages/Registrierung.vue`, `components/registrierung/**`,
 *       `pages/Gruppe*.vue`, `pages/gruppen/**`, `components/gruppen/**`,
 *       `gast/**`, `registrierung/**`, `organigramm/**` stehen in
 *       `tools/ux1f-knopf-bestand.txt` und dürfen NUR SCHRUMPFEN.
 *
 *   F2  Die Bereiche benutzen `<DkButton>` mit einer Variante, die das System
 *       kennt (primary/secondary/ghost/danger) und einer Größe, die es gibt
 *       (sm/md). Ein „warning“-Knopf ist damit unmöglich.
 *
 *   F3  Genau EIN gefüllter Knopf (primary oder danger) je Knopfleiste und je
 *       Ansicht (S1). Gezählt werden die Knöpfe im `#footer` eines Dialogs und
 *       die sichtbaren Knöpfe einer Ansicht; ein zweiter gefüllter Knopf wäre
 *       ein Verstoß.
 *
 *   F4  Die Zuordnung Alt → Neu ist EINE Regel (`diakonos/knopfvarianten.mjs`)
 *       und wird hier wirklich ausgeführt. Die Kalender-Fassung
 *       (`components/kronos/knopfvarianten.mjs`) reicht nur weiter — zwei
 *       Fassungen wären zwei Wahrheiten.
 *
 *   F5  Die alten Klassennamen und die Eigenoptik der umgestellten Knöpfe
 *       sind aus den Vorlagen verschwunden.
 *
 *   F6  Wortliste: „Abbrechen“ verwirft eine Eingabe (secondary, volle Höhe),
 *       „Schließen“ ändert nichts; im Satz stehen Textknöpfe (ghost) statt
 *       roher `<button>`; der Textknopf im Anlege-Dialog heißt „Öffnen“.
 *
 *   F7  Der Zähler selbst rechnet richtig (Kommentare, Beschriftungs-Klassen
 *       und Baustein-Klassen zählen nicht).
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test) — die
 * Datei liegt in `frontend/tests/` und liest nur `frontend/**`.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import {
  FRONTEND,
  LISTE,
  bestand,
  imBereich,
  liesBestand,
  verstoesse,
  fundstellen,
  ohneKommentare,
} from '../tools/ux1f-knopf-bestand.mjs'
import {
  VARIANTEN,
  GROESSEN,
  BESCHRIFTUNGEN,
  knopfAusKlassen,
  beschriftung,
} from '../src/diakonos/knopfvarianten.mjs'
import * as kronosFassung from '../src/diakonos/components/kronos/knopfvarianten.mjs'

/** Quelle einer Datei des Bereiches (Pfad ab Repo-Wurzel, `frontend/…`). */
function lies(rel) {
  const abs = path.join(FRONTEND, rel.replace(/^frontend\//, ''))
  assert.ok(existsSync(abs), `Datei fehlt: ${rel}`)
  return readFileSync(abs, 'utf8')
}

/** Nur der Vorlagen-Teil einer SFC (Skripte zählen nicht als Oberfläche). */
function vorlage(text) {
  const a = text.indexOf('<template>')
  const b = text.lastIndexOf('</template>')
  return ohneKommentare(a >= 0 && b > a ? text.slice(a, b) : '')
}

const P = 'frontend/src/diakonos/'
const BEREICH_DATEIEN = [
  `${P}pages/mitglieder/Uebersicht.vue`,
  `${P}pages/mitglieder/Datenschutz.vue`,
  `${P}pages/mitglieder/Import.vue`,
  `${P}pages/mitglieder/Loeschantraege.vue`,
  `${P}pages/mitglieder/Bereich.vue`,
  `${P}components/mitglieder/MitgliedHinzufuegenDialog.vue`,
  `${P}components/mitglieder/LoeschantraegeListe.vue`,
  `${P}components/mitglieder/LoeschantragKarte.vue`,
  `${P}components/mitglieder/AblehnenDialog.vue`,
  `${P}components/mitglieder/FreigabeDialog.vue`,
  `${P}components/mitglieder/PasswortLink.vue`,
  `${P}pages/Registrierung.vue`,
  `${P}components/registrierung/RegLinkTeilen.vue`,
  `${P}pages/gruppen/Bereich.vue`,
  `${P}pages/Gruppen.vue`,
  `${P}pages/GruppeDetail.vue`,
  `${P}components/gruppen/GruppeAnlegenDialog.vue`,
  `${P}components/gruppen/OrganigrammAnsicht.vue`,
  'frontend/src/gast/App.vue',
  'frontend/src/registrierung/App.vue',
  'frontend/src/registrierung/components/DkAnmeldeformular.vue',
]

// ── F1: Bestand einfrieren ─────────────────────────────────────────────────

test('UX1f/F1: der Bestand alter Knopfklassen schrumpft und ist aktuell', () => {
  const jetzt = bestand()
  const frueher = liesBestand()
  const fehler = verstoesse(jetzt, frueher)
  assert.deepEqual(fehler, [],
    'Die Liste tools/ux1f-knopf-bestand.txt passt nicht zum Stand:\n  '
    + fehler.join('\n  ')
    + '\nNach dem Beheben: node tools/ux1f-knopf-bestand.mjs --schreiben')
})

test('UX1f/F1: im Bestand steht keine Datei ausserhalb des Bereichs', () => {
  for (const pfad of bestand().keys()) {
    assert.ok(imBereich(pfad), `${pfad}: ausserhalb des Kartenbereichs eingefroren`)
  }
})

test('UX1f/F1: die Kalenderliste (UX1e) bleibt unberuehrt', () => {
  const kalender = readFileSync(path.join(FRONTEND, 'tools', 'ux1e-knopf-bestand.txt'), 'utf8')
  assert.doesNotMatch(kalender, /mitglieder|gruppen|registrierung|gast|organigramm/,
    'die UX1e-Liste haelt nur den Kalenderbereich fest; fremde Bereiche gehoeren '
    + 'in tools/ux1f-knopf-bestand.txt')
  assert.ok(existsSync(LISTE), 'tools/ux1f-knopf-bestand.txt fehlt')
})

// ── F2: DkButton mit Variante und Groesse ──────────────────────────────────

test('UX1f/F2: jede Variante im Bereich ist eine des Systems', () => {
  for (const datei of BEREICH_DATEIEN) {
    const text = lies(datei)
    for (const m of text.matchAll(/<DkButton\b[^>]*?\bvariant="([^"]+)"/gs)) {
      // Gebundene Variante (`:variant="a ? 'primary' : 'secondary'"`): jede
      // darin genannte Möglichkeit muss es im System geben.
      const genannt = m[1].includes("'") || m[1].includes('"')
        ? [...m[1].matchAll(/'([^']+)'|"([^"]+)"/g)].map((x) => x[1] || x[2])
        : [m[1]]
      for (const variante of genannt) {
        assert.ok(VARIANTEN.includes(variante),
          `${datei}: variant="${variante}" gibt es im Knopf-System nicht `
          + `(erlaubt: ${VARIANTEN.join(', ')})`)
      }
    }
    for (const m of text.matchAll(/<DkButton\b[^>]*?\bsize="([^"]+)"/gs)) {
      assert.ok(GROESSEN.includes(m[1]),
        `${datei}: size="${m[1]}" gibt es im Knopf-System nicht `
        + `(erlaubt: ${GROESSEN.join(', ')})`)
    }
    assert.doesNotMatch(text, /<DkButton\b[^>]*?\bvariant="warning"/s,
      `${datei}: Warnung gehört in den Text, nicht in die Knopf-Farbe`)
  }
})

test('UX1f/F2: die umgestellten Bausteine holen ihren Knopf aus ui/', () => {
  const bausteine = BEREICH_DATEIEN.filter((d) => /mitglieder\/(MitgliedHinzufuegenDialog|LoeschantraegeListe|LoeschantragKarte|AblehnenDialog|FreigabeDialog|PasswortLink)\.vue$/.test(d)
    || /gruppen\/(GruppeAnlegenDialog|OrganigrammAnsicht)\.vue$/.test(d)
    || /registrierung\/components\/DkAnmeldeformular\.vue$/.test(d))
  for (const datei of bausteine) {
    assert.match(lies(datei), /import DkButton from '[^']*ui\/DkButton\.vue'/,
      `${datei}: DkButton wird nicht aus ui/DkButton.vue importiert`)
  }
})

// ── F3: ein gefuellter Knopf je Fuss ───────────────────────────────────────

/** Gefuellte Knoepfe in einem Stueck Vorlage: primary oder danger. */
function gefuellte(text) {
  return [...text.matchAll(/<DkButton\b[^>]*?\bvariant="(primary|danger)"/gs)].map((m) => m[1])
}

/**
 * Die Knopfleisten eines Dialogfusses: `<template #footer>` bis zum Ende des
 * Dialoges, zerlegt an den Sichten.
 *
 * Ein Fuß kann zwei Sichten haben (`v-if` / `v-else`, z. B. „angelegt“ oder
 * „ausfüllen“); sie schliessen sich aus, also darf jede ihren eigenen
 * gefüllten Knopf haben. Ein INNERES `</template>` beendet deshalb nicht die
 * Zählung (sonst blieben genau diese Knöpfe ungezählt) — gezählt wird je
 * Sicht, und zwei gefüllte Knöpfe in DERSELBEN Sicht sind der Verstoß.
 */
function fuesse(text) {
  const leisten = []
  for (const m of text.matchAll(/<template #footer>([\s\S]*?)<\/DkDialog>/g)) {
    const inhalt = m[1]
    const sichten = [...inhalt.matchAll(/<template v-(?:if|else-if|else)\b[^>]*>([\s\S]*?)<\/template>/g)]
      .map((s) => s[1])
    leisten.push(...(sichten.length ? sichten : [inhalt]))
  }
  return leisten
}

const MIT_FUSS = [
  `${P}pages/mitglieder/Datenschutz.vue`,
  `${P}components/mitglieder/MitgliedHinzufuegenDialog.vue`,
  `${P}components/mitglieder/LoeschantragKarte.vue`,
  `${P}components/mitglieder/AblehnenDialog.vue`,
  `${P}components/mitglieder/FreigabeDialog.vue`,
  `${P}components/gruppen/GruppeAnlegenDialog.vue`,
  `${P}components/gruppen/OrganigrammAnsicht.vue`,
]

test('UX1f/F3: je Fuß höchstens EIN gefüllter Knopf (primary oder danger)', () => {
  for (const datei of MIT_FUSS) {
    const leisten = fuesse(vorlage(lies(datei)))
    assert.ok(leisten.length > 0, `${datei}: kein Dialogfuß gefunden`)
    for (const inhalt of leisten) {
      const voll = gefuellte(inhalt)
      assert.ok(voll.length <= 1,
        `${datei}: ${voll.length} gefüllte Knöpfe (${voll.join(', ')}) in EINEM Fuß — `
        + 'je Fuß ist genau einer erlaubt; die Nebenaktion ist secondary')
    }
  }
})

test('UX1f/F3: „Abbrechen“ und „Schließen“ sind secondary in voller Höhe', () => {
  // UX1f: Abbrechen verwirft eine Eingabe, Schließen ändert nichts — beides
  // sind Nebenaktionen und dürfen weder gefüllt noch klein (sm) sein. Vorher
  // standen sie als ghost in 28 px neben einem primary in 40 px.
  const stellen = [
    [`${P}components/mitglieder/MitgliedHinzufuegenDialog.vue`, 'Abbrechen'],
    [`${P}components/mitglieder/AblehnenDialog.vue`, 'Abbrechen'],
    [`${P}components/mitglieder/FreigabeDialog.vue`, 'Abbrechen'],
    [`${P}components/mitglieder/LoeschantragKarte.vue`, 'Abbrechen'],
    [`${P}pages/mitglieder/Datenschutz.vue`, 'Abbrechen'],
    [`${P}components/gruppen/OrganigrammAnsicht.vue`, 'Abbrechen'],
    [`${P}components/gruppen/OrganigrammAnsicht.vue`, 'Schließen'],
    [`${P}pages/GruppeDetail.vue`, 'Abbrechen'],
  ]
  for (const [datei, wort] of stellen) {
    const text = vorlage(lies(datei))
    const treffer = [...text.matchAll(new RegExp(`<DkButton\\b[^>]*>\\s*${wort}\\s*<`, 'gs'))]
    assert.ok(treffer.length > 0, `${datei}: kein „${wort}“-Knopf gefunden`)
    for (const m of treffer) {
      assert.match(m[0], /\bvariant="secondary"/,
        `${datei}: „${wort}“ ist secondary (Nebenaktion), nicht ghost oder gefüllt`)
      assert.doesNotMatch(m[0], /\bsize="sm"/,
        `${datei}: „${wort}“ in voller Höhe (--control-h), nicht sm`)
    }
  }
})

test('UX1f/F3: „Person anlegen“ ist nur dort der Primärknopf, wo Anlegen die Hauptsache ist', () => {
  const text = lies(`${P}pages/mitglieder/Bereich.vue`)
  // Die Betonung kommt aus dem sichtbaren Eintrag (S1), nicht aus einer
  // zweiten Tätigkeit: es gibt weiterhin GENAU EINEN Anlege-Knopf im Kopf.
  const anlegen = [...vorlage(text).matchAll(/<DkButton\b[^>]*>[\s\S]{0,600}?Person anlegen/gs)]
  assert.equal(anlegen.length, 1, 'genau ein „Person anlegen“ im Kopf erwartet')
  assert.match(anlegen[0][0], /:variant="anlegenIstHauptaktion \? 'primary' : 'secondary'"/,
    'die Betonung folgt dem Eintrag (anlegenIstHauptaktion)')
  assert.match(text, /const ANLEGEN_NEBENACHLICH = new Set\(\['import', 'datenschutz'\]\)/,
    'Import und Datenschutz tragen ihre eigene Hauptaktion')
})

test('UX1f/F3: Datenschutz und Löschanträge haben ihre eigene Hauptaktion', () => {
  // Datenschutz: jede Personenzeile trägt zwei Aktionen — eine Liste mit je
  // zwei GEFÜLLTEN Knöpfen pro Zeile wäre eine Wand aus Hauptaktionen (S1).
  // Darum sind beide umrandet (secondary); das Anonymisieren zeigt seine
  // Gefahr nur über die Fehlerschrift (wie „Löschen“ in der Registrierung).
  const dsDatei = lies(`${P}pages/mitglieder/Datenschutz.vue`)
  const ds = vorlage(dsDatei)
  assert.match(ds, /<DkButton variant="secondary"[^>]*>Auskunft</,
    '„Auskunft“ ist ein umrandeter Zeilenknopf')
  assert.match(ds, /<DkButton variant="secondary" class="ds-anonymisieren-schrift"[^>]*>Anonymisieren</,
    '„Anonymisieren“ ist umrandet, mit Fehlerschrift')
  assert.match(dsDatei, /\.ds-anonymisieren-schrift \{ color: var\(--err\); \}/,
    'die Fehlerschrift kommt aus dem Token --err')
  assert.doesNotMatch(ds.slice(ds.indexOf('class="ds-liste"'), ds.indexOf('</ul>', ds.indexOf('class="ds-liste"'))), /<DkButton\b[^>]*\bvariant="(primary|danger)"/,
    'keine gefüllten Knöpfe in den Personenzeilen')
  // Löschanträge: die Entscheidung „Löschung freigeben“ ist der gefüllte
  // Knopf, „Ablehnen“ die Gegenentscheidung daneben.
  const liste = vorlage(lies(`${P}components/mitglieder/LoeschantraegeListe.vue`))
  assert.match(liste, /<DkButton\s+variant="primary"[\s\S]{0,600}?Löschung freigeben/,
    '„Löschung freigeben“ ist primary')
  assert.doesNotMatch(liste, /variant="danger"/,
    'die Freigabe ist die Entscheidung dieser Liste, nicht die Gefahr — '
    + 'danger bleibt dem Anonymisieren vorbehalten')
})

// ── F4: Zuordnungsregel wird ausgefuehrt ───────────────────────────────────

test('UX1f/F4: alte Klassen werden auf die Knopfvarianten abgebildet', () => {
  const faelle = [
    ['btn btn-primary', 'primary', 'md'],
    ['btn btn-secondary', 'secondary', 'md'],
    ['btn btn-danger', 'danger', 'md'],
    ['btn btn-warning', 'secondary', 'md'],
    ['btn btn-ghost', 'ghost', 'md'],
    ['btn btn-xs', 'secondary', 'sm'],
    // Sammlung der Baustein-Knoepfe (keine Knopfreihe): die ruhigste Form.
    ['sidebar-import-btn', 'ghost', 'md'],
    // Ein Textknopf im Satz (alte Eigenklasse *-btn): ghost.
    ['remove-row-btn', 'ghost', 'md'],
    // Ein Link im Fliesstext ist kein Knopf — und `mh-link` ist der Name,
    // den der umgestellte Textknopf behaelt: die Art sagt die Vorlage.
    ['grup-link', 'secondary', 'md'],
    ['mh-link', 'secondary', 'md'],
    ['la-aktionen', 'secondary', 'md'],
    ['', 'secondary', 'md'],
  ]
  for (const [klassen, variant, size] of faelle) {
    assert.deepEqual(knopfAusKlassen(klassen), { variant, size },
      `"${klassen}" falsch zugeordnet`)
  }
})

test('UX1f/F4: die Zuordnung liefert nur vorhandene Werte', () => {
  const proben = ['btn', 'btn-warning', 'dk-btn-xs', 'tx-400 btn-danger btn-sm',
    'btn-primary dk-btn-ghost', 'reg-aktionen', 'mh-link', 'remove-row-btn']
  for (const klassen of proben) {
    const { variant, size } = knopfAusKlassen(klassen)
    assert.ok(VARIANTEN.includes(variant), `${klassen}: variant ${variant}`)
    assert.ok(GROESSEN.includes(size), `${klassen}: size ${size}`)
  }
})

test('UX1f/F4: die Kalender-Fassung reicht dieselbe Regel weiter', () => {
  // Zwei Fassungen der Regel wuerden auseinanderlaufen: der Kalenderbereich
  // exportiert nur noch, was zentral steht.
  const zentral = { VARIANTEN, GROESSEN, BESCHRIFTUNGEN }
  for (const name of ['VARIANTEN', 'GROESSEN', 'BESCHRIFTUNGEN']) {
    assert.deepEqual(kronosFassung[name], zentral[name],
      `kronos/knopfvarianten.mjs: ${name} weicht von der zentralen Regel ab`)
  }
  const proben = ['btn btn-primary', 'btn btn-warning', 'btn btn-danger', 'dk-btn-ghost']
  for (const klassen of proben) {
    assert.deepEqual(kronosFassung.knopfAusKlassen(klassen), knopfAusKlassen(klassen),
      `kronos/knopfvarianten.mjs: "${klassen}" wird anders zugeordnet`)
  }
})

// ── F5: Alt-Klassen und Eigenoptik sind weg ────────────────────────────────

test('UX1f/F5: die alten Knopfklassen stehen nicht mehr in der Vorlage', () => {
  for (const datei of BEREICH_DATEIEN) {
    const text = vorlage(lies(datei))
    const klassen = [...text.matchAll(/class="([^"]*)"/g)].flatMap((m) => m[1].split(/\s+/))
    for (const name of klassen) {
      assert.ok(!/^(btn|btn-[\w-]+|dk-btn|dk-btn-[\w-]+)$/.test(name),
        `${datei}: Alt-Knopfklasse "${name}" — bitte DkButton`)
    }
  }
})

test('UX1f/F5: für die umgestellten Knöpfe gibt es keine Eigenoptik mehr', () => {
  // Diese Regeln malten Knöpfe selbst (Farbe, Rahmen, Radien) statt das
  // System zu fragen. Sie sind mit dem Umbau entfallen.
  const eigenregeln = [
    [`.mh-link`, /\.mh-link\s*\{[^}]*(background|border|font|color|padding)\s*:/],
    [`.dk-pub-add-btn`, /\.dk-pub-add-btn\s*\{[^}]*(background|border|color|font-weight)\s*:/],
    [`.dk-pub-remove-btn`, /\.dk-pub-remove-btn\s*\{[^}]*(background|border|color|font-size)\s*:/],
  ]
  const dateien = [
    `${P}components/mitglieder/MitgliedHinzufuegenDialog.vue`,
    'frontend/src/registrierung/components/DkAnmeldeformular.vue',
  ]
  for (const datei of dateien) {
    const text = lies(datei)
    for (const [name, regel] of eigenregeln) {
      assert.doesNotMatch(text, regel,
        `${datei}: Eigenoptik ${name} ist wieder da — Knöpfe holen ihre Optik aus DkButton`)
    }
  }
})

// ── F6: Wortliste und Textknoepfe ──────────────────────────────────────────

test('UX1f/F6: im Satz steht ein Textknopf (ghost), kein rohes Knopfelement', () => {
  const text = vorlage(lies(`${P}components/mitglieder/MitgliedHinzufuegenDialog.vue`))
  const treffer = [...text.matchAll(/<DkButton\b[^>]*\bclass="mh-link"[^>]*>(.*?)<\/DkButton>/gs)]
  assert.equal(treffer.length, 2, 'zwei Wege im Satz erwartet (öffnen, Öffnen)')
  for (const m of treffer) {
    assert.match(m[0], /\bvariant="ghost"/, 'ein Weg im Satz ist ein ghost-Knopf')
    assert.match(m[0], /\bsize="sm"/, 'und bleibt klein (sm)')
  }
  // N8: Beschriftung statt Zeichen — beide Wege heißen „Öffnen“.
  const worte = treffer.map((m) => m[1].trim().toLowerCase())
  assert.deepEqual(worte, ['öffnen', 'öffnen'])
})

test('UX1f/F6: Kinder-Zeilen im Anmeldeformular haben benannte Knöpfe', () => {
  const text = lies('frontend/src/registrierung/components/DkAnmeldeformular.vue')
  // I2/N8: „×“ ohne Namen und ohne Klickfläche war der Befund; jetzt
  // „Entfernen“ mit sprechendem aria-label.
  assert.match(text, /<DkButton[\s\S]{0,300}?aria-label="`Kind \$\{idx \+ 1\} entfernen`"/,
    'der Entfernen-Knopf nennt, welches Kind er entfernt')
  assert.match(text, />Entfernen</, 'Beschriftung statt „×“')
  assert.match(text, /\+ Kind hinzufügen/, 'der Hinzufügen-Weg bleibt')
  assert.doesNotMatch(text, /class="dk-pub-remove-btn">×</, 'das stumme „×“ ist weg')
})

test('UX1f/F6: kein nacktes „✕“ mehr als Knopf', () => {
  // N8: ein Zeichen als Beschriftung sagt nicht, was passiert. In der
  // Aufgabenleiste der Gruppe heißt der Knopf jetzt „Abbrechen“.
  const text = vorlage(lies(`${P}pages/GruppeDetail.vue`))
  assert.doesNotMatch(text, />\s*✕\s*</, '„✕“ ohne Wort ist keine Beschriftung')
})

test('UX1f/F6: die Begriffsliste kennt Abbrechen und Schließen', () => {
  // Abbrechen = Eingabe verwerfen, Schließen = ohne Änderung zu — beide
  // Wörter bleiben stehen (nichts wird stillschweigend getauscht).
  for (const wort of ['Abbrechen', 'Schließen']) {
    assert.equal(beschriftung(wort), wort)
  }
})

// ── F7: der Zaehler selbst rechnet richtig ────────────────────────────────

test('UX1f/F7: Kommentare, Beschriftungs- und Baustein-Klassen zaehlen nicht', () => {
  const probe = [
    '<template>',
    '  <!-- <button class="btn btn-secondary">alt</button> -->',
    '  <DkButton variant="primary" class="mh-link">Neu</DkButton>',
    '  <div class="la-aktionen"><a class="grup-link" href="#">x</a></div>',
    '  <div class="reg-aktionen">x</div>',
    '</template>',
    '<style scoped>',
    '.dk-ui-btn { display: inline-flex; }',
    '</style>',
  ].join('\n')
  assert.deepEqual(fundstellen(probe), [],
    'Kommentare, Baustein- und System-Klassen sind keine Knöpfe')
})

test('UX1f/F7: Alt-Klassen und rohe Knoepfe werden gezaehlt', () => {
  assert.deepEqual(fundstellen('<template><button class="btn btn-warning">Trotzdem</button></template>'),
    ['btn', 'btn-warning'])
  assert.deepEqual(fundstellen('<template><button @click="x">Los</button></template>'),
    ['<button>'])
})
