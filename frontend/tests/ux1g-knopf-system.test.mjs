/**
 * UX1g — EIN Knopf-System, Teil 3: der REST, Wächter auf 0.
 *
 * Die Karten UX1e (Kalender/Moderation) und UX1f (Personen/Gruppen/
 * Registrierung/Gast) haben `<DkButton>` in ihren Bereichen durchgesetzt.
 * Diese Karte nimmt, was übrig bleibt: App-Rahmen (Kopfzeile, Seitenleiste),
 * Plan-Rahmen, Lieder, Startseite, Ressourcen, Widgets und Bausteine.
 *
 * Geprüft wird, was die Karte zusagt:
 *
 *   F1  NULL Alt-Knöpfe im Rest. Kein `dk-btn*`, kein `btn*`, keine rohe
 *       Knopfklasse, kein `<button>` ohne Baustein (`tools/ux1g-knopf-bestand.mjs`).
 *
 *   F2  NULL Alt-Knopf-CSS. Die Regeln `.dk-btn`, `.dk-btn-primary` … sind aus
 *       ALLEN Quellen unter `frontend/src` verschwunden (auch als Kopie in
 *       einer Seite) — die Optik trägt `DkButton`.
 *
 *   F3  Was umgestellt wurde, ist wirklich `<DkButton>`: Variante aus dem
 *       System (primary/secondary/ghost/danger), Größe sm/md, und jeder
 *       Baustein importiert den Knopf (kein stiller „Unbekanntes Element").
 *
 *   F4  Die Zuordnung Alt → Neu ist die EINE Regel (`diakonos/knopfvarianten.mjs`)
 *       und wird hier ausgeführt — keine zweite Wahrheit.
 *
 *   F5  Klickflächen (I2/K4): Knöpfe tragen ihre Höhe aus `--control-h`
 *       (40 px, bei `pointer: coarse` 44 px). Die alten 28-px-Knöpfe (sm)
 *       sind aus den umgestellten Stellen verschwunden, wo sie nur
 *       Symbol-Knöpfe in Zeilen waren.
 *
 *   F6  Reine Betrachter: der Zähler übersieht Kommentare, Baustein-Klassen
 *       und die Bereiche von UX1e/UX1f (die führen eigene Listen).
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (`node --test`); die
 * Datei liegt in `frontend/tests/` und liest nur `frontend/**` (Regel 13).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import {
  FRONTEND,
  bestand,
  cssFundstellen,
  fundstellen,
  imBereich,
  imFremdenBereich,
  ohneKommentare,
} from '../tools/ux1g-knopf-bestand.mjs'
import {
  VARIANTEN,
  GROESSEN,
  knopfAusKlassen,
} from '../src/diakonos/knopfvarianten.mjs'

/** Quelle einer Datei (Pfad in Listen-Schreibweise, `frontend/…`). */
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

// ── F1: 0 Alt-Knöpfe ──────────────────────────────────────────────────────

test('UX1g/F1: im Rest steht kein Alt-Knopf mehr', () => {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}: ${zahl}`)
  assert.deepEqual(zeilen, [],
    'Alt-Knöpfe im Rest der Anwendung — bitte <DkButton> benutzen '
    + '(components/ui/DkButton.vue):\n  ' + zeilen.join('\n  '))
})

test('UX1g/F1: der Bereich dieser Karte ist der Rest, nicht UX1e/UX1f', () => {
  // Die beiden früheren Knopf-Karten führen eigene Bestandslisten; ein Pfad
  // darf nie in BEIDEN Bereichen liegen (sonst wäre „0" unerfüllbar).
  for (const pfad of [
    'frontend/src/diakonos/components/kronos/KronosSidebar.vue',
    'frontend/src/diakonos/pages/Moderation.vue',
    'frontend/src/registrierung/components/DkAnmeldeformular.vue',
    'frontend/src/diakonos/pages/Registrierung.vue',
    'frontend/src/diakonos/pages/planrahmen/Plan.vue',
    'frontend/src/diakonos/pages/Ressourcen.vue',
  ]) {
    const fremd = imFremdenBereich(pfad)
    const meins = imBereich(pfad)
    assert.ok(!(fremd && meins), `${pfad}: in beiden Bereichen eingetragen`)
  }
  assert.ok(!imBereich('frontend/src/diakonos/pages/Moderation.vue'))
  assert.ok(!imBereich('frontend/src/registrierung/components/DkAnmeldeformular.vue'))
  assert.ok(imBereich('frontend/src/diakonos/pages/planrahmen/Plan.vue'))
  assert.ok(imBereich('frontend/src/diakonos/pages/Ressourcen.vue'))
})

// ── F2: 0 Alt-Knopf-CSS ───────────────────────────────────────────────────

test('UX1g/F2: die CSS-Regeln der Alt-Knöpfe sind weg', () => {
  const treffer = cssFundstellen()
  assert.deepEqual(treffer, [],
    'Die alten Knopf-Regeln (.dk-btn …) stehen noch in:\n  '
    + treffer.map((t) => `${t.pfad}: ${t.zahl}`).join('\n  ')
    + '\n— DkButton trägt seine Optik in der Komponente (tokens.css + scoped).')
})

test('UX1g/F2: die Komponente selbst heißt nicht .dk-btn', () => {
  // `DkButton` rendert `dk-ui-btn`. Ein `.dk-btn`-Selektor würde den
  // Baustein stillschweigend mitgestalten — genau das soll aufhören.
  const dk = lies('frontend/src/diakonos/components/ui/DkButton.vue')
  assert.doesNotMatch(dk, /\.dk-btn(?![\w-])/, 'DkButton trägt die Altklasse')
  assert.match(dk, /\.dk-ui-btn/, 'DkButton braucht seine eigene Klasse')
})

test('UX1g/F2: es gibt keine zweite Knopf-Optik in index.css', () => {
  const css = ohneKommentare(lies('frontend/src/diakonos/index.css'))
  for (const regel of ['.btn {', '.btn-primary', '.btn-secondary', '.btn-sm']) {
    assert.ok(!css.includes(regel), `index.css definiert ${regel} — eine Optik genügt`)
  }
})

// ── F3: DkButton mit Systemwerten ─────────────────────────────────────────

/** Die Stellen, die diese Karte umgestellt hat (Stichprobe + alle Dateien). */
const UMGESTELLT = [
  'frontend/src/diakonos/App.vue',
  'frontend/src/diakonos/components/AppSidebar.vue',
  'frontend/src/diakonos/components/AppTopbar.vue',
  'frontend/src/diakonos/components/AuditConfirmModal.vue',
  'frontend/src/diakonos/components/GruppenItem.vue',
  'frontend/src/diakonos/components/SitzungsHinweis.vue',
  'frontend/src/diakonos/components/lieder/LiedgruppeBearbeiten.vue',
  'frontend/src/diakonos/components/widgets/BaseWidgetCard.vue',
  'frontend/src/diakonos/components/widgets/PendingRegistrationsWidget.vue',
  'frontend/src/diakonos/pages/Home.vue',
  'frontend/src/diakonos/pages/Lieder.vue',
  'frontend/src/diakonos/pages/Ressourcen.vue',
  'frontend/src/diakonos/components/planrahmen/BedarfDialog.vue',
  'frontend/src/diakonos/pages/planrahmen/Einrichten.vue',
  'frontend/src/diakonos/pages/planrahmen/MeineDienste.vue',
  'frontend/src/diakonos/pages/planrahmen/Plan.vue',
  'frontend/src/diakonos/pages/planrahmen/PlantypEditor.vue',
  'frontend/src/diakonos/pages/planrahmen/Stammdaten.vue',
  'frontend/src/diakonos/pages/planrahmen/Uebersicht.vue',
]

test('UX1g/F3: die umgestellten Dateien benutzen DkButton', () => {
  for (const datei of UMGESTELLT) {
    const text = lies(datei)
    assert.match(text, /<DkButton\b/, `${datei}: kein einziger DkButton`)
    assert.match(text, /import DkButton from '[^']*ui\/DkButton\.vue'/,
      `${datei}: DkButton wird nicht importiert (dann bliebe er ein unbekanntes Element)`)
  }
})

test('UX1g/F3: jede Variante und Größe ist eine des Systems', () => {
  const dateien = [...UMGESTELLT, ...bestand().keys()]
  for (const datei of new Set(dateien)) {
    if (!existsSync(path.join(FRONTEND, datei.replace(/^frontend\//, '')))) continue
    const text = lies(datei)
    for (const m of text.matchAll(/<DkButton\b[^>]*?\bvariant="([^"]+)"/gs)) {
      const genannt = m[1].includes("'") || m[1].includes('"')
        ? [...m[1].matchAll(/'([^']+)'|"([^"]+)"/g)].map((x) => x[1] || x[2])
        : [m[1]]
      for (const variante of genannt) {
        assert.ok(VARIANTEN.includes(variante),
          `${datei}: variant="${variante}" gibt es nicht (erlaubt: ${VARIANTEN.join(', ')})`)
      }
    }
    for (const m of text.matchAll(/<DkButton\b[^>]*?\bsize="([^"]+)"/gs)) {
      assert.ok(GROESSEN.includes(m[1]),
        `${datei}: size="${m[1]}" gibt es nicht (erlaubt: ${GROESSEN.join(', ')})`)
    }
    assert.doesNotMatch(text, /<DkButton\b[^>]*?\bvariant="warning"/s,
      `${datei}: Warnung gehört in den Text, nicht in die Knopf-Farbe`)
  }
})

test('UX1g/F3: die Kopfzeile einer Ansicht hat EINEN gefüllten Knopf je Sicht', () => {
  // S1: genau ein gefüllter Knopf je Ansicht. Eine Ansicht kann mehrere
  // Sichten haben, die sich ausschliessen (archiviert / nicht archiviert,
  // Dialog offen / zu) — sie zaehlen einzeln, wie in UX1e/UX1f.
  //
  // Die Vorlage wird dafür in ihre Sichten zerlegt: `<template v-if|v-else>`
  // beginnt eine neue, ein `</template>` auf gleicher Tiefe beendet sie.
  const leisten = [
    'frontend/src/diakonos/pages/planrahmen/Plan.vue',
    'frontend/src/diakonos/pages/planrahmen/PlantypEditor.vue',
    'frontend/src/diakonos/pages/planrahmen/Uebersicht.vue',
  ]
  for (const datei of leisten) {
    const text = vorlage(lies(datei))
    const start = text.indexOf('class="dk-screen-actions"')
    if (start < 0) continue
    // Die Leiste endet mit ihrem <div>; der Inhalt ist bis zum Gegenstueck.
    const leiste = text.slice(start, text.indexOf('</div>', start))
    // Sichten: alles zwischen <template v-if/v-else-if/v-else> und </template>
    // bzw. der Rest ohne Sicht-Grenzen.
    const sichten = [...leiste.matchAll(/<template v-(?:if|else-if|else)\b[^>]*>([\s\S]*?)<\/template>/g)]
      .map((m) => m[1])
    const rest = leiste.replace(/<template v-(?:if|else-if|else)\b[^>]*>[\s\S]*?<\/template>/g, '')
    for (const [i, sicht] of [...sichten, rest].entries()) {
      const voll = [...sicht.matchAll(/variant="(primary|danger)"/g)].length
      assert.ok(voll <= 1,
        `${datei}: Sicht ${i + 1} der Kopfzeile hat ${voll} gefüllte Knöpfe — `
        + 'je Ansicht ist EINER erlaubt (S1)')
    }
  }
})

// ── F4: eine Regel ────────────────────────────────────────────────────────

test('UX1g/F4: die Zuordnung Alt → Neu ist die eine Regel', () => {
  const faelle = [
    ['dk-btn dk-btn-primary dk-btn-sm', 'primary', 'sm'],
    ['dk-btn dk-btn-secondary dk-btn-sm', 'secondary', 'sm'],
    ['dk-btn dk-btn-ghost dk-btn-sm', 'ghost', 'sm'],
    ['dk-btn dk-btn-ghost dk-btn-xs', 'ghost', 'sm'],
    ['dk-btn dk-btn-secondary', 'secondary', 'md'],
    ['dk-btn dk-btn-warning', 'secondary', 'md'],
    ['dk-btn dk-btn-primary pr-plan-gefahr', 'primary', 'md'],
    ['', 'secondary', 'md'],
  ]
  for (const [klassen, variant, size] of faelle) {
    assert.deepEqual(knopfAusKlassen(klassen), { variant, size },
      `"${klassen}" falsch zugeordnet`)
  }
})

// ── F5: Klickflächen ──────────────────────────────────────────────────────

test('UX1g/F5: die Knopfhöhe kommt aus --control-h, am Finger aus 44 px', () => {
  const dk = lies('frontend/src/diakonos/components/ui/DkButton.vue')
  assert.match(dk, /height:\s*var\(--filter-h\)/,
    'DkButton „md“ muss seine Höhe aus dem Höhen-Token holen (--filter-h zeigt auf --control-h)')
  const tokens = lies('frontend/src/diakonos/tokens.css')
  assert.match(tokens, /--control-h:\s*40px/, '--control-h ist 40 px')
  // Die 44 px bei grobem Zeiger setzt der Zeiger-Block am Ende von
  // index.css (dort stehen alle pointer:coarse-Regeln, FIX-6/OP-HANDY-14).
  const css = lies('frontend/src/diakonos/index.css')
  const block = css.slice(css.lastIndexOf('@media (pointer: coarse)'))
  assert.match(block, /--control-h:\s*var\(--control-h-lg\)|--control-h:\s*44px/,
    'bei grobem Zeiger sind es 44 px (K4) — der Block setzt --control-h neu')
})

test('UX1g/F5: die Symbol-Knöpfe der Kopfzeile sind nicht mehr 28 px', () => {
  const css = lies('frontend/src/diakonos/index.css')
  const block = css.slice(css.indexOf('.dk-widget-griff {'))
  assert.match(block.slice(0, 200), /width:\s*var\(--control-h\)/,
    'Widget-Griffe brauchen die Knopfhöhe aus dem Token, nicht 28 px')
  assert.doesNotMatch(block.slice(0, 200), /(width|height):\s*28px/)
})

// ── F6: der Zähler rechnet richtig ────────────────────────────────────────

test('UX1g/F6: Kommentare und Baustein-Klassen zählen nicht', () => {
  const probe = [
    '<template>',
    '  <!-- <button class="dk-btn dk-btn-primary">alt</button> -->',
    '  <DkButton variant="primary" class="pr-plan-gefahr">Neu</DkButton>',
    '  <span class="pr-meldungen-anzeigen">Anzeigen</span>',
    '</template>',
    '<style scoped>',
    '.pr-meldungen-anzeigen { color: var(--muted); }',
    '</style>',
  ].join('\n')
  assert.deepEqual(fundstellen(probe), [],
    'Kommentare und Baustein-Klassen sind keine Knöpfe')
})

test('UX1g/F6: Alt-Klassen und rohe Knöpfe werden gezählt', () => {
  assert.deepEqual(
    fundstellen('<template><button class="dk-btn dk-btn-sm">x</button></template>'),
    ['dk-btn', 'dk-btn-sm'])
  assert.deepEqual(fundstellen('<template><button @click="x">Los</button></template>'),
    ['<button>'])
})

test('UX1g/F6: die Zuordnungsregel selbst zählt nicht als Fundstelle', () => {
  assert.ok(!imBereich('frontend/src/diakonos/knopfvarianten.mjs'),
    'die Regel nennt die alten Klassen absichtlich — sie ist keine Fundstelle')
})
