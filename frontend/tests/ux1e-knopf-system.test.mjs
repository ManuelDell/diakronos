/**
 * UX1e — EIN Knopf-System, Teil 1: Kalender-/Moderationsbereich.
 *
 * Geprüft wird, was die Karte zusagt:
 *
 *   F1  Kein Alt-Knopf mehr im Bereich. Die Fundstellen der alten Klassen
 *       (`.dk-btn*`, `.btn-*`, rohe `<button>` mit Eigenklasse) in
 *       `components/kronos/**`, `pages/Kalender*.vue`, `pages/Moderation.vue`
 *       stehen in `tools/ux1e-knopf-bestand.txt` und dürfen NUR SCHRUMPFEN.
 *
 *   F2  Die Bereiche, die die Karte umstellt, benutzen `<DkButton>` — und
 *       zwar mit einer Variante, die das System kennt (primary/secondary/
 *       ghost/danger) und einer Größe, die es gibt (sm/md). Ein „warning“-
 *       Knopf ist damit unmöglich.
 *
 *   F3  Genau EIN Primärknopf je Dialog/Ansicht im Kalender (S1). Gezählt
 *       werden `variant="primary"` je Knopfleiste; ein zweiter gefüllter
 *       Knopf im selben Fuß wäre ein Verstoß.
 *
 *   F4  Die Zuordnung Alt → Neu ist EINE Regel (`knopfvarianten.mjs`) und
 *       wird hier wirklich ausgeführt (kein Regex-Raten, P1-5c/4/K3).
 *
 *   F5  Kein Alt-Knopf kommt zurück: die alten Klassennamen `.btn`,
 *       `.btn-primary` … und die Eigenknopf-CSS-Regeln der umgestellten
 *       Bausteine sind aus dem Bereich verschwunden.
 *
 *   F6  Keine neuen festen Farben (der Wächter aus ON-0b bleibt unberührt;
 *       hier nur für die Dateien des Bereichs nachgeprüft).
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test) — die
 * Datei liegt in `frontend/tests/` und liest nur `frontend/**`.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import {
  FRONTEND,
  bestand,
  liesBestand,
  verstoesse,
  fundstellen,
  ohneKommentare,
} from '../tools/ux1e-knopf-bestand.mjs'
import {
  VARIANTEN,
  GROESSEN,
  knopfAusKlassen,
  beschriftung,
} from '../src/diakonos/components/kronos/knopfvarianten.mjs'

/** Quelle einer Datei des Bereiches (Pfad ab Repo-Wurzel, `frontend/…`). */
function lies(rel) {
  const abs = path.join(FRONTEND, rel.replace(/^frontend\//, ''))

  assert.ok(existsSync(abs), `Datei fehlt: ${rel}`)
  return readFileSync(abs, 'utf8')
}

const KRONOS = 'frontend/src/diakonos/components/kronos/'
const UMGESTELLT = [
  `${KRONOS}KronosConflictDialog.vue`,
  `${KRONOS}KronosSeriesDialog.vue`,
  `${KRONOS}KronosSidebar.vue`,
  `${KRONOS}KronosTopbar.vue`,
  `${KRONOS}KronosEventCreate.vue`,
  `${KRONOS}KronosEventEdit.vue`,
  `${KRONOS}ModerationCard.vue`,
  `${KRONOS}ModerationModals.vue`,
]

/** Nur der Vorlagen-Teil einer SFC (Skripte zählen nicht als Oberfläche). */
function vorlage(text) {
  const a = text.indexOf('<template>')
  const b = text.lastIndexOf('</template>')
  return ohneKommentare(a >= 0 && b > a ? text.slice(a, b) : '')
}

// ── F1: Bestand einfrieren ─────────────────────────────────────────────────

test('UX1e/F1: der Bestand alter Knopfklassen schrumpft und ist aktuell', () => {
  const jetzt = bestand()
  const frueher = liesBestand()
  const fehler = verstoesse(jetzt, frueher)
  assert.deepEqual(fehler, [],
    'Die Liste tools/ux1e-knopf-bestand.txt passt nicht zum Stand:\n  '
    + fehler.join('\n  ')
    + '\nNach dem Beheben: node tools/ux1e-knopf-bestand.mjs --schreiben')
})

test('UX1e/F1: im Bestand steht keine Datei ausserhalb des Bereichs', () => {
  for (const pfad of bestand().keys()) {
    const imBereich = pfad.startsWith(KRONOS)
      || /frontend\/src\/diakonos\/pages\/(Kalender|Moderation)/.test(pfad)
    assert.ok(imBereich, `${pfad}: ausserhalb des Kartenbereichs eingefroren`)
  }
})

// ── F2: DkButton mit Variante und Groesse ──────────────────────────────────

test('UX1e/F2: umgestellte Bausteine benutzen DkButton', () => {
  for (const datei of UMGESTELLT) {
    const text = lies(datei)
    assert.match(text, /<DkButton\b/, `${datei}: kein einziger DkButton`)
    assert.match(text, /import DkButton from '\.\.\/ui\/DkButton\.vue'/,
      `${datei}: DkButton nicht importiert`)
  }
})

test('UX1e/F2: jede Variante im Bereich ist eine des Systems', () => {
  for (const datei of UMGESTELLT) {
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
  }
})

test('UX1e/F2: „warning“ gibt es als Knopfvariante nicht mehr', () => {
  for (const datei of UMGESTELLT) {
    assert.doesNotMatch(lies(datei), /<DkButton\b[^>]*?\bvariant="warning"/s,
      `${datei}: Warnung gehört in den Text, nicht in die Knopf-Farbe`)
  }
})

// ── F3 (UX1e2): Klickflaechen in der Kopfzeile und auf dunkler Leiste ──────
//
// Review UX1e:
//  * Der Moderations-Link stand mit `size="sm"` (28 px) in der Kopfzeile —
//    kleiner als jede Klickfläche daneben. Seit UX1e2 `size="md"`
//    (--control-h 40 px, bei pointer:coarse 44 px).
//  * Unter 720 px weicht die sichtbare Beschriftung; der zugängliche Name
//    muss trotzdem „Terminmoderation öffnen“ bleiben (aria-label).
//  * Die Ghost-Knöpfe der dunklen Leiste nahmen Farben der HELLEN Fläche
//    (--muted / --surface-hover). Sie müssen die Tokens der Leiste tragen.

/** Der Moderations-Knopf der Kopfzeile (Quelltext von `<DkButton` bis `>`). */
function moderationsKnopf(text) {
  // UX3a hat das Ziel des Reiters umbenannt: „Termine prüfen und freigeben“
  // (#/kalender/pruefen). Der Knopf selbst ist derselbe geblieben.
  const start = text.indexOf('href="#/kalender/pruefen"')
  assert.ok(start >= 0, 'Prüfen-Link gesucht (href="#/kalender/pruefen")')
  const anfang = text.lastIndexOf('<DkButton', start)
  const ende = text.indexOf('>', text.indexOf('aria-label', start) >= 0 ? start : start)
  assert.ok(anfang >= 0, 'Moderations-Link ist ein DkButton')
  return text.slice(anfang, ende + 1)
}

test('UX1e2/F3: der Moderations-Link ist ein Knopf in voller Höhe', () => {
  const text = vorlage(lies(`${KRONOS}KronosTopbar.vue`))
  const knopf = moderationsKnopf(text)
  assert.match(knopf, /\bsize="md"/,
    'Moderations-Link muss size="md" tragen (--control-h 40/44 px), nicht sm (28 px)')
  assert.doesNotMatch(knopf, /\bsize="sm"/)
})

test('UX1e2/F3: der Prüfen-Link hat auch mobil einen festen Namen', () => {
  const quelle = lies(`${KRONOS}KronosTopbar.vue`)
  const knopf = moderationsKnopf(vorlage(quelle))
  assert.match(knopf, /aria-label="Termine prüfen und freigeben"/,
    'aria-label fehlt — unter 720 px ist das Symbol der einzige sichtbare Teil')
  // Die Ausblendung betrifft nur den sichtbaren Text, nie den Namen.
  assert.match(quelle, /@media \(max-width: 720px\)[\s\S]*?\.moderation-btn-label \{\s*display:\s*none/,
    'Beschriftung weicht unter 720 px (FIX-6) — der aria-label trägt den Namen')
})

test('UX1e2/F3: Leistenknöpfe tragen die Farben der dunklen Leiste', () => {
  const quelle = lies(`${KRONOS}KronosSidebar.vue`)
  const start = quelle.indexOf('.sb-navigationsknopf {')
  assert.ok(start > 0, 'Regel .sb-navigationsknopf fehlt')
  const regeln = quelle.slice(start)
  assert.match(regeln, /color:\s*var\(--dk-sb-text\)/,
    'Schriftfarbe muss var(--dk-sb-text) sein (nicht --muted der hellen Fläche)')
  assert.match(regeln, /background:\s*var\(--dk-sb-hover\)/,
    'Hover muss var(--dk-sb-hover) sein (nicht --surface-hover der hellen Fläche)')
  // Jeder Knopf der Leiste traegt die Klasse.
  for (const m of vorlage(quelle).matchAll(/<DkButton\b[^>]*?variant="ghost"[^>]*>/gs)) {
    if (m[0].includes('sb-navigationsknopf')) continue
    assert.fail(`Leistenknopf ohne .sb-navigationsknopf: ${m[0].slice(0, 80)}`)
  }
})

test('UX1e2/F3: Leistenknöpfe sind Block-Flex (Beschriftung wird nicht abgeschnitten)', () => {
  const quelle = lies(`${KRONOS}KronosSidebar.vue`)
  const start = quelle.indexOf('.sb-navigationsknopf {')
  assert.ok(start > 0, 'Regel .sb-navigationsknopf fehlt')
  const block = quelle.slice(start, quelle.indexOf('}', start))
  // Befund im Abnahmelauf: mit `inline-flex` und `width: calc(100% - …)`
  // blieb der Knopf auf Inhaltsbreite (22 px) — nur das Symbol war zu sehen.
  assert.match(block, /display:\s*flex;/,
    '.sb-navigationsknopf braucht display:flex (sonst bleibt width wirkungslos)')
  assert.doesNotMatch(block, /display:\s*inline-flex;/)
})

test('UX1e2/F3: die toten Leisten-Regeln stehen nicht mehr in kronos.css', () => {
  const css = ohneKommentare(lies('frontend/src/diakonos/kronos.css'))
  assert.doesNotMatch(css, /\.sidebar-help-btn/,
    '.sidebar-help-btn ist tote Regel (seit UX1e DkButton) — entfernen')
  assert.doesNotMatch(css, /\.sidebar-import-btn/,
    '.sidebar-import-btn ist tote Regel (seit UX1e DkButton) — entfernen')
})

// ── F3: ein Primaerknopf je Ansicht ────────────────────────────────────────

test('UX1e/F3: jede Sicht des Seriendialogs hat genau einen Primärknopf', () => {
  const text = vorlage(lies(`${KRONOS}KronosSeriesDialog.vue`))
  // Die drei Sichten schliessen sich aus (v-if / v-else-if): verschieben,
  // Auswahl, Löschen bestätigen. Jede hat genau eine Hauptaktion (S1).
  const sichten = [
    ['drag', 'Auswahl'],
    ['edit', 'Bestätigen'],
  ]
  for (const [name] of sichten) {
    const primaries = [...text.matchAll(/<DkButton\b[^>]*?\bvariant="primary"/gs)]
    assert.equal(primaries.length, 2,
      `KronosSeriesDialog (${name}): ${primaries.length} Primärknöpfe — `
      + 'je Sicht ist genau einer erlaubt (verschieben, Auswahl)')
  }
  // Konkret: je Sicht genau ein primary, nie zwei im selben Fuss.
  for (const m of text.matchAll(/<div class="diakronos-modal-footer">([\s\S]*?)<\/div>/g)) {
    const knopfleiste = [...m[1].matchAll(/<DkButton\b[^>]*?\bvariant="primary"/gs)]
    assert.ok(knopfleiste.length <= 1,
      `KronosSeriesDialog: ${knopfleiste.length} Primärknöpfe in EINER Knopfleiste`)
  }
  // Die Auswahlliste „Was möchtest du tun?“ hat genau eine Hauptaktion; die
  // Lösch-Bestätigung daneben keine (dort ist Löschen die einzige Aktion).
  const listen = [...text.matchAll(/<div class="series-option-btns">([\s\S]*?)<\/div>/g)]
  assert.equal(listen.length, 2, 'zwei Auswahllisten erwartet (Auswahl, Lösch-Bestätigung)')
  const primariesImAuswahl = [...listen[1][1].matchAll(/<DkButton\b[^>]*?\bvariant="primary"/gs)]
  assert.equal(primariesImAuswahl.length, 1,
    'series-option-btns: genau eine Hauptaktion je Auswahlliste')
})

// ── F3 (UX1e2): gefuellte Knoepfe je Fuss — Hoechstzahl 1 ──────────────────
//
// Review UX1e: „Löschen“ und „Bearbeiten“ standen als zwei GEFUELLTE Knoepfe
// nebeneinander (Gefahr + Primaer). Gezaehlt wird deshalb nicht mehr nur
// `variant="primary"`, sondern jeder gefuellte Knopf: primary UND danger.
// Je Knopfleiste (Fuss) hoechstens einer.

/** Gefuellte Knoepfe in einem Stueck Vorlage: primary oder danger. */
function gefuellte(text) {
  return [...text.matchAll(/<DkButton\b[^>]*?\bvariant="(primary|danger)"/gs)]
    .map(m => m[1])
}

/** Die Knopfleisten einer SFC-Vorlage: `<div class="…footer…">` bis `</div>`. */
function fussLeisten(text) {
  const leisten = []
  for (const m of text.matchAll(/<div class="([^"]*\bfooter\b[^"]*)">([\s\S]*?)<\/div>/g)) {
    leisten.push([m[1], m[2]])
  }
  return leisten
}

const KNOEPFE_JE_FUSS = [
  `${KRONOS}ModerationModals.vue`,
  `${KRONOS}KronosSeriesDialog.vue`,
]

test('UX1e2/F3: je Fuß höchstens EIN gefüllter Knopf (primary oder danger)', () => {
  for (const datei of KNOEPFE_JE_FUSS) {
    const text = vorlage(lies(datei))
    const leisten = fussLeisten(text)
    assert.ok(leisten.length > 0, `${datei}: keine Knopfleiste gefunden`)
    for (const [klasse, inhalt] of leisten) {
      const voll = gefuellte(inhalt)
      assert.ok(voll.length <= 1,
        `${datei} .${klasse}: ${voll.length} gefüllte Knöpfe (${voll.join(', ')}) — `
        + 'je Fuß ist genau einer erlaubt; die Nebenaktion ist secondary '
        + '(Gefahrenfarbe in der Schrift)')
    }
  }
})

test('UX1e2/F3: der Serienfuß in ModerationModals ist secondary + Schriftfarbe', () => {
  const text = vorlage(lies(`${KRONOS}ModerationModals.vue`))
  // Die beiden „Löschen“-Knöpfe im Serienfuß (Ansicht und Bearbeiten) oeffnen
  // nur die Rueckfrage — sie sind Nebenaktionen.
  const loeschen = [...text.matchAll(/<DkButton\b[^>]*?>[\s\S]{0,10}?Löschen</g)]
  assert.equal(loeschen.length, 2, 'zwei „Löschen“-Knöpfe im Serienfuß erwartet')
  for (const m of loeschen) {
    assert.doesNotMatch(m[0], /variant="(primary|danger)"/,
      '„Löschen“ im Serienfuß darf nicht gefüllt sein')
    assert.match(m[0], /class="dk-mod-loeschen-schrift"/,
      '„Löschen“ trägt die Gefahrenfarbe als Schrift (dk-mod-loeschen-schrift)')
  }
})

test('UX1e2/F3: die beiden Serien-Löschwege sind secondary + Schriftfarbe', () => {
  const text = vorlage(lies(`${KRONOS}KronosSeriesDialog.vue`))
  const liste = [...text.matchAll(/<div class="series-option-btns">([\s\S]*?)<\/div>/g)]
  assert.equal(liste.length, 2, 'zwei Auswahllisten erwartet (Auswahl, Lösch-Bestätigung)')
  const auswahl = liste[1][1]
  assert.equal(gefuellte(auswahl).length, 1,
    'in der Auswahlliste steht genau ein gefüllter Knopf („Bearbeiten als Einzeltermin“)')
  const loeschwege = [...auswahl.matchAll(/<DkButton\b[^>]*?>[\s\S]{0,40}?löschen</g)]
  assert.equal(loeschwege.length, 2, 'zwei Lösch-Wege erwartet')
  for (const m of loeschwege) {
    assert.match(m[0], /^<DkButton\b[^>]*variant="secondary"/,
      'Lösch-Weg ist secondary (öffnet nur die Rückfrage)')
    assert.match(m[0], /class="series-loeschen-schrift"/,
      'Lösch-Weg trägt die Gefahrenfarbe als Schrift (series-loeschen-schrift)')
  }
})

test('UX1e/F3: der Konfliktdialog hat keinen Primaerknopf', () => {
  const text = vorlage(lies(`${KRONOS}KronosConflictDialog.vue`))
  assert.doesNotMatch(text, /<DkButton\b[^>]*?\bvariant="primary"/s,
    'die Entscheidung im Konfliktdialog ist keine Hauptaktion der Seite')
  // Die gefährliche Wahl bleibt als einzige gefüllt-rote Aktion erkennbar.
  assert.match(text, /<DkButton variant="danger"[^>]*>Als Konflikt markieren</,
    '„Als Konflikt markieren“ muss als gefährliche Wahl ein danger-Knopf sein')
})

// ── F4: Zuordnungsregel wird ausgefuehrt ───────────────────────────────────

test('UX1e/F4: alte Klassen werden auf die Knopfvarianten abgebildet', () => {
  const faelle = [
    ['btn btn-primary', 'primary', 'md'],
    ['btn btn-secondary', 'secondary', 'md'],
    ['btn btn-danger', 'danger', 'md'],
    // „Warn“ ist keine Knopfart: gefahrlos -> secondary.
    ['btn btn-warning', 'secondary', 'md'],
    ['dk-btn dk-btn-ghost dk-btn-sm', 'ghost', 'sm'],
    ['dk-btn dk-btn-primary', 'primary', 'md'],
    // danger schlaegt primary, wenn beide dranstehen (nicht schlechter machen).
    ['btn btn-primary btn-danger', 'danger', 'md'],
    // .btn-xs gibt es im System nicht -> kleinste vorhandene Groesse.
    ['btn btn-xs', 'secondary', 'sm'],
    ['', 'secondary', 'md'],
  ]
  for (const [klassen, variant, size] of faelle) {
    assert.deepEqual(knopfAusKlassen(klassen), { variant, size },
      `"${klassen}" falsch zugeordnet`)
  }
})

test('UX1e/F4: die Zuordnung liefert nur vorhandene Werte', () => {
  const proben = ['btn', 'btn-warning', 'dk-btn-xs', 'tx-400 btn-danger btn-sm',
    'btn-primary dk-btn-ghost', 'sidebar-import-btn']
  for (const klassen of proben) {
    const { variant, size } = knopfAusKlassen(klassen)
    assert.ok(VARIANTEN.includes(variant), `${klassen}: variant ${variant}`)
    assert.ok(GROESSEN.includes(size), `${klassen}: size ${size}`)
  }
})

// ── F5: Alt-Klassen und Eigenregeln sind weg ──────────────────────────────

test('UX1e/F5: die alten Knopfklassen stehen nicht mehr in der Vorlage', () => {
  for (const datei of UMGESTELLT) {
    const text = vorlage(lies(datei))
    // Ganze Klassennamen pruefen: `\b` wuerde in `diakronos-close-btn` anschlagen.
    const klassen = [...text.matchAll(/class="([^"]*)"/g)].flatMap((m) => m[1].split(/\s+/))
    for (const name of klassen) {
      assert.ok(!/^(btn|btn-[\w-]+|dk-btn|dk-btn-[\w-]+)$/.test(name),
        `${datei}: Alt-Knopfklasse "${name}" — bitte DkButton`)
    }
  }
})

test('UX1e/F5: fuer die umgestellten Knoepfe gibt es keine Eigenoptik mehr', () => {
  // Diese Regeln malten Knöpfe selbst (Farbe, Rahmen, Radien) statt das
  // System zu fragen. Sie sind mit dem Umbau entfallen.
  const eigenregeln = [
    /\.remove-row-btn\s*\{/,
    /\.add-row-btn\s*\{/,
    /\.dk-mod-btn-inline\s*\{/,
    /\.dk-mod-btn-warn\s*\{/,
    /\.dk-mod-btn-danger-outline\s*\{/,
    /\.dk-mcard-resolve-btn\s*\{[^}]*background:/,
    /\.moderation-btn\s*\{/,
  ]
  for (const datei of UMGESTELLT) {
    const text = lies(datei)
    for (const regel of eigenregeln) {
      assert.doesNotMatch(text, regel,
        `${datei}: Eigenoptik ${regel} ist wieder da — Knöpfe holen ihre Optik aus DkButton`)
    }
  }
})

// ── F6: Begriffe und Farben ───────────────────────────────────────────────

test('UX1e/F6: die umgestellten Bausteine tragen keine festen Farben', () => {
  const farb = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g
  for (const datei of UMGESTELLT) {
    const style = lies(datei).replace(/\/\*[\s\S]*?\*\//g, ' ')
    const treffer = style.match(farb) || []
    assert.deepEqual(treffer, [],
      `${datei}: feste Farbwerte ${treffer.join(', ')} — bitte Token aus tokens.css`)
  }
})

test('UX1e/F6: „Trotzdem speichern“ sagt jetzt die Folge', () => {
  const text = vorlage(lies(`${KRONOS}KronosConflictDialog.vue`))
  assert.match(text, /Mit Überschneidung speichern/)
  assert.doesNotMatch(text, /Trotzdem speichern/,
    '„Trotzdem speichern“ sagt nicht, was danach gilt (I4)')
  assert.equal(beschriftung('Trotzdem speichern'), 'Mit Überschneidung speichern')
})

test('UX1e/F6: „Ja, Sicher“ heisst jetzt „Sichern“', () => {
  const text = vorlage(lies(`${KRONOS}KronosSeriesDialog.vue`))
  assert.match(text, />Sichern</)
  assert.doesNotMatch(text, /Ja, Sicher/)
  assert.equal(beschriftung('Ja, Sicher'), 'Sichern')
})

// ── F7: der Zaehler selbst rechnet richtig ────────────────────────────────

test('UX1e/F7: Kommentare und Nicht-Knopfklassen zaehlen nicht', () => {
  const probe = [
    '<template>',
    '  <!-- <button class="btn btn-secondary">alt</button> -->',
    '  <DkButton variant="primary">Neu</DkButton>',
    '  <span class="moderation-btn-label">Moderation</span>',
    '</template>',
    '<style scoped>',
    '.moderation-btn-label { display: none; }',
    '</style>',
  ].join('\n')
  assert.deepEqual(fundstellen(probe), [],
    'Beschriftung, CSS-Regeln und Kommentare sind keine Knöpfe')
})

test('UX1e/F7: ein alter Knopf wird gezaehlt', () => {
  const probe = '<template><button class="btn btn-warning">Trotzdem</button></template>'
  assert.deepEqual(fundstellen(probe), ['btn', 'btn-warning'])
})
