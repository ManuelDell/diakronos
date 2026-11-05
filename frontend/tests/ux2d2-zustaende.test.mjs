/**
 * UX2d2 · Zustände: echte Handlung, dauerhafte Live-Region, kein Flackern.
 *
 * BEFUND (Review UX2d, Manuel):
 *   1. „Erneut versuchen" stand als TEXT in der Fläche, ohne Ziel. Die Seiten
 *      reichten `erneut-versuchen` durch; es gab nichts, worauf der Klick
 *      zeigen konnte.
 *   2. Die Erfolgsmeldung hing an einem `v-if`. Damit entstand die
 *      `aria-live`-Fläche ERST mit dem Text — Screenreader lesen eine neu
 *      eingefügte Region nicht zuverlässig vor.
 *   3. Das Lade-Skelett erschien sofort; bei schnellen Antworten blitzte es.
 *
 * GEPRÜFT WIRD DAS VERHALTEN, nicht der Quelltext: die Bausteine werden
 * WIRKLICH gerendert (`createSSRApp` + `renderToString`, SFC über
 * `vue/compiler-sfc` kompiliert). Ein Kommentar im Quelltext kann einen
 * Befund hier nicht „grün machen".
 *
 * Lauf: node --test tests/ux2d2-zustaende.test.mjs   (cwd = frontend/)
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, posix } from 'node:path'

import * as VUE from 'vue'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

import { VERZOEGERUNG_MS, ladeSkelett } from '../src/diakonos/composables/ladeSkelett.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src', 'diakonos')

// ── Ein kleiner SFC-Lader für die Bausteine der UI-Bibliothek ─────────────
/**
 * Die Bausteine (DkEmpty, DkErfolgsmeldung) sind `<script setup>`-Dateien mit
 * Vorlage und Stil. Dieser Lader kompiliert sie mit `vue/compiler-sfc` und
 * baut daraus eine echte Komponente — ohne Vite, ohne Browser.
 *
 * Abhängigkeiten des Bausteins (andere Dk-Komponenten) werden ERST beim
 * Rendern aufgelöst, damit kein Ringschluss entsteht. Fehlt eine Abhängigkeit,
 * nennt der Test sie beim Namen.
 */
function vueLaden(relativ, zwischenlager = new Map()) {
  if (zwischenlager.has(relativ)) return zwischenlager.get(relativ)
  const quelle = readFileSync(join(SRC, relativ), 'utf8')
  const id = relativ.replace(/[^\w]/g, '_')
  const { descriptor, errors } = parse(quelle, { filename: relativ })
  assert.deepEqual(errors, [], `${relativ}: SFC-Struktur`)
  assert.ok(descriptor.scriptSetup, `${relativ}: kein <script setup>`)

  // `inlineTemplate` erzeugt EINE Komponente mit Vorlage im `setup` — der
  // Renderer sieht damit alle Bindungen aus `<script setup>`, ohne dass der
  // Test die Vue-Signatur nachbauen müsste.
  const kompiliert = compileScript(descriptor, {
    id,
    inlineTemplate: true,
    templateOptions: { compilerOptions: { bindingMetadata: undefined } },
  })

  // Bausteine aus Nachbardateien werden über `components` gereicht: der
  // erzeugte Code referenziert sie als freie Namen (DkButton …). Node löst
  // keine relativen .vue-Importe — deshalb kommen sie als Parameter herein.
  const importe = [...quelle.matchAll(/^import\s+(\w+)\s+from\s+'\.\/([\w.-]+\.vue)'/gm)]
  const namen = importe.map(([, name]) => name)
  const dateien = importe.map(([, , datei]) => posix.join(posix.dirname(relativ), datei))

  // ALLE vue-Importe des erzeugten Codes (Renderer-Aliase UND die Importe
  // des `<script setup>`, z. B. `computed`) werden zu Parametern.
  const paare = []
  for (const zeile of kompiliert.content.match(
    /^import\s*\{([^}]*)\}\s*from\s*["']vue["']\s*;?$/gm,
  ) || []) {
    const inhalt = /\{([^}]*)\}/.exec(zeile)[1]
    for (const teil of inhalt.split(',')) {
      const s = teil.trim()
      if (!s) continue
      const [original, alias] = s.split(/\s+as\s+/).map((x) => x && x.trim())
      const eintrag = { original, lokal: alias || original }
      if (!paare.some((p) => p.lokal === eintrag.lokal)) paare.push(eintrag)
    }
  }
  assert.ok(paare.length, `${relativ}: keine vue-Importe im erzeugten Code`)
  const fehlend = paare.filter(({ original }) => !(original in VUE)).map(({ original }) => original)
  assert.deepEqual(fehlend, [], `${relativ}: unbekannte Vue-Helfer`)

  // ALLE Import-Zeilen fallen weg — vue-Helfer kommen als Parameter, die
  // Bausteine ebenfalls (der erzeugte Code referenziert sie als freie Namen).
  // Bausteine werden rekursiv geladen — als FERTIGE Komponenten, nicht als
  // Import im Rumpf. Der erzeugte Code referenziert sie im `setup`-Rückruf;
  // deshalb kommen sie als Parameter herein und der Import fällt weg.
  const bausteinWerte = dateien.map((datei) => vueLaden(datei, zwischenlager))
  const rumpf = kompiliert.content
    .replace(/^import\s[^;]*?from\s*["'][^"']+["']\s*;?\s*$/gm, '')
    .replace(/^export default/m, 'return')
  const baue = new Function(
    ...paare.map(({ lokal }) => lokal),
    ...namen,
    `${rumpf}`,
  )
  const komponente = baue(...paare.map(({ original }) => VUE[original]), ...bausteinWerte)
  zwischenlager.set(relativ, komponente)
  return komponente
}

/** Rendert eine Komponente zu HTML (echtes SSR). */
async function rendere(komponente, props = {}, slots = {}) {
  const app = createSSRApp({ render: () => h(komponente, props, slots) })
  return renderToString(app)
}

// ── Wächter über die Quellen ──────────────────────────────────────────────
function vueDateien(ordner) {
  const treffer = []
  const gehe = (rel) => {
    for (const name of readdirSync(join(SRC, rel))) {
      const kind = posix.join(rel, name)
      if (statSync(join(SRC, kind)).isDirectory()) gehe(kind)
      else if (name.endsWith('.vue')) treffer.push(kind)
    }
  }
  gehe(ordner)
  return treffer
}

function ohneKommentare(quelle) {
  return String(quelle)
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^[ \t]*\/\/.*$/gm, '')
}

function lies(relativ) {
  return readFileSync(join(SRC, relativ), 'utf8')
}

/** Eine stellbare Uhr: keine echten Timer, kein Warten im Test. */
function uhr() {
  let jetzt = 0
  const offen = new Map()
  let kennung = 0
  return {
    timer: {
      set: (fn, ms) => { kennung += 1; offen.set(kennung, { fn, faellig: jetzt + ms }); return kennung },
      clear: (k) => { offen.delete(k) },
    },
    weiter(ms) {
      jetzt += ms
      for (const [k, eintrag] of [...offen]) {
        if (eintrag.faellig <= jetzt) { offen.delete(k); eintrag.fn() }
      }
    },
  }
}

// ── (1) DkEmpty: der Knopf ist die Handlung ──────────────────────────────
test('UX2d2 · DkEmpty baut aus dem Handler einen echten Knopf (SSR)', async () => {
  const komponente = vueLaden('components/ui/DkEmpty.vue')

  const mit = await rendere(komponente, {
    title: 'Nicht geladen',
    text: 'Der Server antwortet gerade nicht.',
    erneutVersuchen: () => {},
  })
  assert.ok(mit.includes('Nicht geladen'), `Titel fehlt: ${mit}`)
  assert.ok(mit.includes('Der Server antwortet gerade nicht.'), `Erklärung fehlt: ${mit}`)
  // Der gemeinsame Knopf (DkButton) trägt die Aufforderung — als Element,
  // nicht als Satz.
  assert.match(mit, /<button[^>]*class="[^"]*dk-ui-btn/, `kein Knopf gerendert: ${mit}`)
  const sichtbarerText = mit.replace(/<!--[\s\S]*?-->/g, '')
  assert.ok(sichtbarerText.includes('Erneut versuchen'), `Knopfbeschriftung fehlt: ${mit}`)

  // Ohne Handler KEIN Knopf. (Der HTML-Kommentar der Vorlage darf den Satz
  // zitieren — geprüft wird das Element, nicht der Kommentar.)
  const ohne = await rendere(komponente, { title: 'Nicht geladen', text: 'Der Server antwortet nicht.' })
  assert.ok(!/<button/.test(ohne), `tote Klickfläche ohne Handler: ${ohne}`)
})

// ── (2) Dauerhafte Live-Region ───────────────────────────────────────────
test('UX2d2 · DkErfolgsmeldung ist eine Region, die auch leer im DOM steht (SSR)', async () => {
  const komponente = vueLaden('components/ui/DkErfolgsmeldung.vue')
  for (const text of ['', 'Einstellungen gespeichert.']) {
    const html = await rendere(komponente, { text })
    assert.match(html, /role="status"/, `keine Live-Region bei text=${JSON.stringify(text)}: ${html}`)
    assert.match(html, /aria-live="polite"/, 'aria-live fehlt')
    assert.match(html, /aria-atomic="true"/, 'atomic fehlt — sonst wird nur die Änderung vorgelesen')
    if (text) assert.ok(html.includes(text), 'der Text steht nicht IN der Region')
  }
})

test('UX2d2 · kein Erfolgsblock hängt mehr an `v-if` (Region entstünde erst mit dem Text)', () => {
  const befunde = []
  for (const ordner of ['pages', 'components']) {
    for (const datei of vueDateien(ordner)) {
      const vorlage = ohneKommentare(lies(datei).split('<script')[0])
      if (/<p\s+v-if="erfolg"/.test(vorlage) || /<DkHint\s+v-if="erfolg"/.test(vorlage)) {
        befunde.push(`${datei}: Erfolgsblock mit v-if`)
      }
    }
  }
  assert.deepEqual(befunde, [], 'Erfolgsmeldung als eingefügte Live-Region: ' + befunde.join(', '))
  // Die Einstellungen nutzen die dauerhafte Region.
  for (const datei of ['pages/einstellungen/Gemeinde.vue', 'pages/einstellungen/Mailversand.vue',
    'pages/einstellungen/Datensicherung.vue', 'pages/einstellungen/RollenRechte.vue']) {
    assert.match(lies(datei), /<DkErfolgsmeldung\b/, `${datei}: keine dauerhafte Vorlese-Region`)
  }
})

// ── (3) Kein Flackern: Platzhalter erst nach 300 ms ──────────────────────
test('UX2d2 · das Skelett erscheint erst nach 300 ms', () => {
  assert.equal(VERZOEGERUNG_MS, 300, 'die Verzögerung ist nicht 300 ms')
  const u = uhr()
  const gemeldet = []
  let laedt = false
  const waechter = ladeSkelett(() => laedt, (s) => gemeldet.push(s), { timer: u.timer })

  laedt = true
  waechter.pruefe(true)
  assert.equal(waechter.sofort(), false, 'der Platzhalter stand sofort — genau das Flackern')
  u.weiter(299)
  assert.equal(waechter.sofort(), false, 'der Platzhalter kam vor 300 ms')
  u.weiter(1)
  assert.equal(waechter.sofort(), true, 'der Platzhalter kam nach 300 ms nicht')

  laedt = false
  waechter.pruefe(false)
  assert.equal(waechter.sofort(), false, 'der Platzhalter blieb nach dem Laden stehen')
  assert.deepEqual(gemeldet, [true, false], `unerwartete Meldungen: ${JSON.stringify(gemeldet)}`)
})

test('UX2d2 · eine schnelle Antwort (unter 300 ms) zeigt NIE einen Platzhalter', () => {
  const u = uhr()
  const gemeldet = []
  let laedt = true
  const waechter = ladeSkelett(() => laedt, (s) => gemeldet.push(s), { timer: u.timer })
  waechter.pruefe(true)
  u.weiter(80)
  laedt = false
  waechter.pruefe(false)
  u.weiter(1000)
  assert.deepEqual(gemeldet, [], `ein Platzhalter blitzte auf: ${JSON.stringify(gemeldet)}`)
  assert.equal(waechter.sofort(), false)
})

// ── (4) Die Seiten reichen den Handler wirklich durch ────────────────────
test('UX2d2 · die Löschanträge-Liste meldet „laden" nach oben, die Seite nimmt es an', () => {
  const liste = lies('components/mitglieder/LoeschantraegeListe.vue')
  assert.match(liste, /defineEmits\(\[[^\]]*'laden'/s, 'die Liste erklärt das Ereignis „laden" nicht')
  assert.match(liste, /@click="emit\('laden'\)"/, 'der Aktualisieren-Knopf meldet „laden" nicht')
  assert.doesNotMatch(
    ohneKommentare(liste.split('<script')[0]),
    /@click="laden"/,
    'der Knopf zeigt wieder auf einen Namen, den es in der Komponente nicht gibt',
  )
  assert.match(lies('pages/mitglieder/Loeschantraege.vue'), /@laden="laden"/,
    'die Seite hört „laden" nicht ab — der Knopf bliebe tot')
})

test('UX2d2 · MitgliedDetail bindet den Fehler an `loadMitglied`', () => {
  const quelle = lies('pages/MitgliedDetail.vue')
  const vorlage = ohneKommentare(quelle.split('<script')[0])
  assert.match(vorlage, /:erneut-versuchen="loadMitglied"/, 'die Fehlerfläche hat keinen Wiederhol-Handler')
  assert.doesNotMatch(vorlage, /:erneut-versuchen="laden"/, '„laden" gibt es in dieser Seite nicht')
  assert.match(quelle, /async function loadMitglied\(\)/, 'loadMitglied fehlt')
})

// ── (5) Die Seiten nutzen die Verzögerung ────────────────────────────────
test('UX2d2 · die Seiten mit Skelett zeigen es über die Verzögerung, nicht sofort', () => {
  const seiten = [
    'pages/Gruppen.vue', 'pages/GruppeDetail.vue', 'pages/Lieder.vue',
    'pages/LiedDetail.vue', 'pages/Ressourcen.vue', 'pages/Adressbuch.vue',
    'pages/Registrierung.vue', 'pages/Beitraege.vue', 'pages/Website.vue',
  ]
  const befunde = []
  for (const datei of seiten) {
    const quelle = lies(datei)
    if (/<DkSkelett[\s\S]{0,200}?v-if="(loading|laedt|postsLaden|loadingLinks|loadingFormulare)"/.test(quelle)) {
      befunde.push(`${datei}: Skelett hängt noch direkt am Ladezustand`)
    }
    if (!/useLadeSkelett\(/.test(quelle)) befunde.push(`${datei}: nutzt die Verzögerung nicht`)
  }
  assert.deepEqual(befunde, [], befunde.join(', '))
})
