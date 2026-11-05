/**
 * UX2d3a · Zustände Teil A: Ladetexte ersetzt der Platzhalter, nicht die Prosa.
 *
 * BEFUND (Review UX2d, Manuel 2026-10-22): „Lade …“ stand als Satz in 20
 * Vorlagen. Zwei Folgen:
 *
 *   1. „Lade…“ ist Prosa, die den Bildschirm überschreibt: springt der Inhalt
 *      später auf, springt das Layout mit. Das gemeinsame Ladeskelett
 *      (DkSkelett, erst nach 300 ms über `useLadeSkelett`) und der ruhige
 *      Ladezustand der UI-Bibliothek zeigen die FORM des kommenden Inhalts,
 *      ohne Text zu behaupten.
 *   2. Ein Fehlerzustand daneben bot „Nochmal“ ohne Bezug — oder gar keinen
 *      Weg zurück. Jeder Fehlerzustand braucht die echte Meldung und
 *      „Erneut versuchen“, gebunden an einen EXISTIERENDEN Handler.
 *
 * GEPRÜFT WIRD:
 *   (1) Wächter: in Vorlagen (template-Abschnitt) steht kein Ladeprosatext
 *       mehr — ausser an den Stellen der ERLAUBT-Liste unten (dort begründet).
 *   (2) Die geänderten Seiten nutzen den gemeinsamen Baustein.
 *   (3) Jeder „Erneut versuchen“-Knopf der geänderten Flächen hängt an einem
 *       Handler, den das `<script setup>` der Datei wirklich erklärt — ein
 *       ungebundener Bezeichner wäre ein toter Knopf.
 *
 * Lauf: node --test tests/ux2d3a-ladetexte.test.mjs   (cwd = frontend/)
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, posix } from 'node:path'

import { parse, compileScript } from 'vue/compiler-sfc'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src', 'diakonos')

/**
 * ERLAUBT-Liste — Ladeprosatext, der BLEIBEN darf, mit Begründung.
 *
 * Der Maßstab: ein Platzhalter ersetzt FLÄCHEN, die gleich mit Inhalt gefüllt
 * werden. Steht der Text in einem BEDIENELEMENT (Knopf, Feld) und beschreibt
 * eine laufende HANDLUNG, ist er eine Rückmeldung und bleibt — das Skelett
 * kann keinen Knopf ersetzen.
 */
const ERLAUBT = [
  // Knopfbeschriftung während einer schon laufenden Aktion („mehr laden“).
  { datei: 'pages/planrahmen/Plan.vue', grund: 'Knopf „Wird geladen …“ während „Neu laden“ läuft' },
  // Dateiauswahl: der Text steht IM Feld und sagt, dass die Datei hochgeladen wird.
  { datei: 'pages/einstellungen/Gemeinde.vue', grund: 'Dateifeld „Wird geladen …“ während des Uploads' },
  { datei: 'components/einrichtung/SchrittGemeinde.vue', grund: 'Dateifeld „Wird geladen …“ während des Uploads' },
]

/** Muster, die einen Ladeprosatext in einer VORLAGE erkennen. */
const LADETEXT = /(^|[^A-Za-zÄÖÜäöüß])(Lade|Lädt|lädt|Wird geladen|wird geladen)\b(?!\s+(?:die|der|das|den|dem)\b)/

const DATEIEN = [
  'App.vue',
  'components/AppTopbar.vue',
  'components/VerantwortlicheKarte.vue',
  'components/WartendeKontenKarte.vue',
  'components/ZugangKarte.vue',
  'components/gruppen/OrganigrammAnsicht.vue',
  'components/kronos/KronosDayEventsDialog.vue',
  'components/kronos/ModerationBoard.vue',
  'components/kronos/ModerationModals.vue',
  'components/planrahmen/PrEditor.vue',
  'pages/Dienstplan.vue',
  'pages/LiedgruppeDetail.vue',
  'pages/Liedgruppen.vue',
  'pages/MitgliedDetail.vue',
  'pages/planrahmen/Einrichten.vue',
  'pages/planrahmen/MeineDienste.vue',
  'pages/planrahmen/Plan.vue',
  'pages/planrahmen/PlantypEditor.vue',
  'pages/planrahmen/Stammdaten.vue',
  'pages/planrahmen/Uebersicht.vue',
]

function lies(relativ) {
  return readFileSync(join(SRC, relativ), 'utf8')
}

/** Nur der Vorlagen-Abschnitt: Skript und Stil dürfen „Lade…“ zitieren. */
function vorlage(quelle) {
  const start = quelle.indexOf('<template>')
  if (start < 0) return ''
  // Der schließende Tag liegt am Zeilenanfang — so schneidet die Suche nicht
  // in einen verschachtelten <template>-Block.
  const ende = quelle.search(/\n<\/template>/)
  return ende < 0 ? quelle.slice(start) : quelle.slice(start, ende)
}

/** Kommentare fallen weg — sie ZITIEREN den Befund und sind kein Text. */
function ohneKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '')
}

/** Sichtbarer Text einer Vorlage: Tags raus, dann prüfen. */
function sichtbarerText(text) {
  const ohneTags = ohneKommentare(text)
    // Attribute sind keine Anzeige. Ein `text="… werden geladen …"` am
    // Skelett ist die VORLESE-Hilfe (aria-label) — nicht sichtbar, deshalb
    // fällt das ganze Tag. Ein echtes Textknoten-„Lade…“ fällt nicht.
    .replace(/<[^>]*>/g, ' ')
  return ohneTags.replace(/\s+/g, ' ').trim()
}

/** Alle .vue-Dateien unter `ordner` (relativ zu src/diakonos). */
function vueDateien(ordner) {
  const treffer = []
  const gehe = (rel) => {
    for (const name of readdirSync(join(SRC, rel)).sort()) {
      const kind = posix.join(rel, name)
      if (statSync(join(SRC, kind)).isDirectory()) gehe(kind)
      else if (name.endsWith('.vue')) treffer.push(kind)
    }
  }
  gehe(ordner)
  return treffer
}

/**
 * Die Bezeichner, die ein SFC in seiner Vorlage verwenden DARF: alles, was
 * `<script setup>` erklärt. `compileScript` hängt am Ende einen
 * `__returned__`-Block an — genau die Namen, die die Vorlage sieht (Variablen,
 * Funktionen UND aus Kompositionen destrukturierte Werte). Das ist die
 * belastbarste Quelle: sie kennt `const { x } = useX()` und `const { a: b }`.
 */
function gebundeneNamen(quelle, relativ) {
  const { descriptor, errors } = parse(quelle, { filename: relativ })
  assert.deepEqual(errors, [], `${relativ}: SFC-Struktur`)
  if (!descriptor.scriptSetup) return null
  const kompiliert = compileScript(descriptor, { id: relativ.replace(/\W/g, '_') })
  const namen = new Set()
  const manifest = kompiliert.content.match(/const __returned__ = \{([\s\S]*?)\n\}/)
  if (manifest) {
    for (const teil of manifest[1].split(',')) {
      // `name`, `get name() {…}`, `set name(v) {…}` — der Bezeichner steht vorn.
      const treffer = teil.trim().match(/^(?:get\s+|set\s+)?([A-Za-z_$][\w$]*)/)
      if (treffer) namen.add(treffer[1])
    }
  }
  // Rückfall (falls der Compiler den Block einmal anders schreibt): die
  // üblichen Deklarationen.
  for (const treffer of kompiliert.content.matchAll(/\b(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)/g)) {
    namen.add(treffer[1])
  }
  return namen
}

// ── (1) Wächter: keine Ladeprosatexte mehr in Vorlagen ────────────────────
test('UX2d3a · keine „Lade…“-Texte mehr in Vorlagen (ausser Erlaubt-Liste)', () => {
  const befunde = []
  for (const ordner of ['pages', 'components']) {
    for (const datei of vueDateien(ordner)) {
      if (ERLAUBT.some((e) => e.datei === datei)) continue
      const text = sichtbarerText(vorlage(lies(datei)))
      if (LADETEXT.test(text)) {
        const stelle = text.match(LADETEXT)
        const umfeld = text.slice(Math.max(0, stelle.index - 40), stelle.index + 60)
        befunde.push(`${datei}: … ${umfeld.trim()} …`)
      }
    }
  }
  befunde.push(
    ...['App.vue'].filter(() => LADETEXT.test(sichtbarerText(vorlage(lies('App.vue')))))
      .map(() => 'App.vue: Ladeprosatext im App-Rahmen'),
  )
  assert.deepEqual(
    befunde,
    [],
    'Ladeprosatext statt Platzhalter (DkSkelett/useLadeSkelett bzw. DkEmpty):\n  ' + befunde.join('\n  '),
  )
})

test('UX2d3a · die Erlaubt-Liste nennt nur Stellen, die es noch gibt', () => {
  const befunde = []
  for (const eintrag of ERLAUBT) {
    const quelle = lies(eintrag.datei)
    const text = sichtbarerText(vorlage(quelle))
    if (!LADETEXT.test(text)) {
      befunde.push(`${eintrag.datei}: Ausnahme ohne Fundstelle — Eintrag entfernen (${eintrag.grund})`)
    }
  }
  assert.deepEqual(befunde, [], befunde.join('\n'))
})

// ── (2) Die geänderten Flächen nutzen den gemeinsamen Baustein ────────────
test('UX2d3a · jede entworfene Fläche lädt über DkSkelett, DkSpinner oder DkEmpty', () => {
  const befunde = []
  for (const datei of DATEIEN) {
    const quelle = lies(datei)
    const hat = /<(DkSkelett|DkSpinner|DkEmpty)\b/.test(quelle)
    if (!hat) befunde.push(`${datei}: kein gemeinsamer Lade-/Leerzustand`)
    // Wer ein Skelett zeigt, nimmt es über die Verzögerung — sonst blitzte es.
    if (/<DkSkelett\b/.test(quelle) && !/useLadeSkelett\(/.test(quelle)) {
      befunde.push(`${datei}: DkSkelett ohne useLadeSkelett (Blitzgefahr)`)
    }
  }
  assert.deepEqual(befunde, [], befunde.join('\n'))
})

// ── (4) Der Startwert ist ein Ladezustand wie jeder andere ───────────────
test('UX2d3a · useLadeSkelett prüft den STARTWERT, nicht erst Änderungen', async () => {
  // BEFUND bei der Abnahme: Seiten setzen `loading` beim Aufbau auf `true`
  // (ref-Startwert) und ändern es danach nur noch auf `false`. Ein reines
  // `watch` sah deshalb nur den Wechsel nach `false` — es erschien NIE ein
  // Platzhalter. Der Test hält den Startwert fest.
  const quelle = lies('composables/useLadeSkelett.js')
  assert.match(
    quelle,
    /watch\(laedt,[\s\S]{0,200}?\{\s*immediate:\s*true\s*\}\)/,
    'useLadeSkelett prüft den Startwert nicht (`immediate: true` fehlt) — ' +
      'Seiten, die im Ladezustand aufbauen, zeigen dann nie ein Skelett',
  )
  // Und die Regel selbst: erst nach 300 ms, nicht sofort.
  const { ladeSkelett, VERZOEGERUNG_MS } = await import('../src/diakonos/composables/ladeSkelett.mjs')
  assert.equal(VERZOEGERUNG_MS, 300, 'die Verzögerung ist nicht 300 ms')
  const gemeldet = []
  const waechter = ladeSkelett(true, (s) => gemeldet.push(s), {
    timer: { set: (fn) => { setTimeout(fn, 0); return 1 }, clear: () => {} },
  })
  waechter.pruefe(true)
  assert.deepEqual(gemeldet, [], 'der Platzhalter kam sofort statt nach 300 ms')
})

test('UX2d3a · das Skelett zeigt die Form, nicht den Satz (text nur als aria-label)', () => {
  // BEFUND bei der Abnahme: DkSkelett gab `text` ZUSÄTZLICH als <p> aus —
  // jedes Skelett war damit wieder ein „… werden geladen …“-Satz auf dem
  // Bildschirm. Der Text gehört in die Vorlese-Hilfe, nicht ins Bild.
  const quelle = lies('components/ui/DkSkelett.vue')
  const vorlagenText = ohneKommentare(vorlage(quelle))
  assert.match(quelle, /:aria-label="text \|\| /, 'DkSkelett nutzt den Text nicht als Vorlese-Hilfe')
  assert.doesNotMatch(
    vorlagenText,
    /\{\{\s*text\s*\}\}/,
    'DkSkelett gibt `text` als sichtbaren Text aus — das ist Ladeprosatext',
  )
  assert.doesNotMatch(
    vorlagenText,
    /class="dk-ui-skelett-text"/,
    'DkSkelett hat wieder einen sichtbaren Textabsatz',
  )
})

// ── (5) „Erneut versuchen“ hängt an einem echten Handler ──────────────────
test('UX2d3a · jeder „Erneut versuchen“-Knopf hängt an einem erklärten Handler', () => {
  const befunde = []
  for (const datei of DATEIEN) {
    const quelle = lies(datei)
    const vorlagenText = ohneKommentare(vorlage(quelle))
    // Nur die Vorlage zählt: der Ausdruck im Attribut.
    const handler = [...vorlagenText.matchAll(/:erneut-versuchen="\s*([^"]+?)\s*"/g)].map((m) => m[1])
    if (!handler.length) continue

    const namen = gebundeneNamen(quelle, datei)
    if (!namen) {
      befunde.push(`${datei}: kein <script setup> — Handler nicht prüfbar`)
      continue
    }
    for (const ausdruck of handler) {
      // Erlaubt ist ein einfacher Bezeichner oder eine Pfeilfunktion.
      if (ausdruck.includes('=>')) continue
      if (!/^[A-Za-z_$][\w$]*$/.test(ausdruck)) {
        befunde.push(`${datei}: :erneut-versuchen="${ausdruck}" ist kein einfacher Handler`)
        continue
      }
      if (!namen.has(ausdruck)) {
        befunde.push(`${datei}: :erneut-versuchen="${ausdruck}" — dieser Name existiert im Skript nicht`)
      }
    }
  }
  assert.deepEqual(befunde, [], 'tote Wiederhol-Knöpfe:\n  ' + befunde.join('\n  '))
})
