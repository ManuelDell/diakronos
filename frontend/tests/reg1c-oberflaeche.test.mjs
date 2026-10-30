/**
 * REG-1c (5) — Zwei Befunde der Oberflaeche, am Code und am Verhalten geprueft.
 *
 *   (a) **Vorschau-Hinweis darf das Banner nicht ueberdecken.** Das Banner
 *       zieht mit negativem Rand nach oben (`-40px`, am Handy `-24px`) und lag
 *       damit ueber der Unterkante des Hinweises (in der Abnahme gemessen:
 *       Hinweis 163–215 px, Banner ab 191 px). Der Hinweis bekommt jetzt genau
 *       diesen Zuschlag als Abstand — nur im Vorschau-Modus.
 *
 *   (b) **Die oeffentliche Seite ist im Dunkelmodus wirklich dunkel.**
 *       `tokens.css` kennt die dunklen Werte nur unter `[data-theme="dark"]`.
 *       Der Einstieg der oeffentlichen Seite setzte das Merkmal nie — die
 *       Anmeldung blieb auch bei dunkler Systemeinstellung hell. Geprueft wird
 *       die Regel (Speicher -> System -> hell) und ihre Verdrahtung in BEIDEN
 *       oeffentlichen Einstiegen (`registrierung`, `gast`).
 *
 * Der Test kompiliert die SFCs echt (vue/compiler-sfc) und fuehrt die
 * Theme-Regel mit Attrappen aus. Laeuft im Docker-Build ueber `node --test`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from 'vue/compiler-sfc'

import { startTheme, themeSetzen } from '../src/diakonos/composables/oeffentliches-theme.mjs'

const src = (p) => readFileSync(new URL(`../src/${p}`, import.meta.url), 'utf8')

// ════════════════════════════════════════════════════════════════════════════
// (a) Vorschau-Hinweis: Abstand gegen den negativen Rand des Banners
// ════════════════════════════════════════════════════════════════════════════

const appQuelle = src('registrierung/App.vue')
const app = parse(appQuelle, { filename: 'App.vue' })
assert.deepEqual(app.errors, [], 'App.vue: SFC-Struktur')
const appStil = app.descriptor.styles.map((s) => s.content).join('\n')

// Der negative Rand des Banners ist die Ursache — er bleibt (das Bild soll bis
// an die Kartenkanten gehen), aber der Hinweis bekommt ihn als Abstand zurueck.
// Die Banner-Regel steht in der gemeinsamen Anzeige (`DkAnmeldeformular.vue`),
// die Hinweis-Regel im Seitenrahmen (`App.vue`) — beide muessen zusammenpassen.
const formularParse = parse(src('registrierung/components/DkAnmeldeformular.vue'),
  { filename: 'DkAnmeldeformular.vue' })
assert.deepEqual(formularParse.errors, [], 'DkAnmeldeformular.vue: SFC-Struktur')
const formularStil = formularParse.descriptor.styles.map((s) => s.content).join('\n')
const bannerRand = formularStil.match(/\.dk-pub-banner\s*\{[\s\S]*?margin:\s*-(\d+)px/)
assert.ok(bannerRand, 'die Regel `.dk-pub-banner` mit negativem Rand fehlt')
const bannerZug = Number(bannerRand[1])

const hinweisRegel = appStil.match(
  /\.dk-pub-koerper\[data-vorschau\]\s+\.dk-pub-vorschau-hinweis\s*\{([^}]*)\}/,
)
assert.ok(hinweisRegel, 'REG-1c: kein eigener Abstand fuer den Vorschau-Hinweis')
assert.match(
  hinweisRegel[1],
  new RegExp(`margin-bottom:\\s*calc\\(\\s*var\\(--sp-4\\)\\s*\\+\\s*${bannerZug}px\\s*\\)`),
  `REG-1c: der Hinweis bekommt nicht die ${bannerZug}px des Banners als Abstand`,
)
// Am Handy zieht das Banner weniger weit nach oben — der Zuschlag muss mitgehen.
const mobil = formularStil.slice(formularStil.indexOf('@media (max-width: 640px)')) + appStil.slice(appStil.indexOf('@media (max-width: 640px)'))
const mobilBanner = mobil.match(/\.dk-pub-banner\s*\{[\s\S]*?margin:\s*-(\d+)px/)
assert.ok(mobilBanner, 'die Handy-Regel des Banners fehlt')
const mobilRegel = mobil.match(
  /\.dk-pub-koerper\[data-vorschau\]\s+\.dk-pub-vorschau-hinweis\s*\{([^}]*)\}/,
)
assert.ok(mobilRegel, 'REG-1c: kein Handy-Abstand fuer den Vorschau-Hinweis')
assert.match(
  mobilRegel[1],
  new RegExp(`calc\\(\\s*var\\(--sp-4\\)\\s*\\+\\s*${mobilBanner[1]}px\\s*\\)`),
  'REG-1c: der Handy-Abstand folgt nicht dem Handy-Rand des Banners',
)
// Nur im Vorschau-Modus — die oeffentliche Seite hat keinen Hinweis, und ein
// globaler Abstand wuerde dort den Kopf nach unten schieben.
assert.match(
  appStil,
  /\.dk-pub-koerper\[data-vorschau\]/,
  'REG-1c: die Regel gilt nicht ausschliesslich in der Vorschau',
)
assert.ok(
  !/(^|\n)\.dk-pub-vorschau-hinweis\s*\{[^}]*margin-bottom:\s*calc/.test(appStil),
  'REG-1c: der Zuschlag steht faelschlich in der allgemeinen Regel',
)
// Und das Merkmal, an dem die Regel haengt, setzt die Anzeige wirklich.
assert.match(
  src('registrierung/components/DkAnmeldeformular.vue'),
  /:data-vorschau="vorschau \? '' : null"/,
  'REG-1c: `data-vorschau` wird nicht am Formularkoerper gesetzt',
)

// ════════════════════════════════════════════════════════════════════════════
// (b) Dunkelmodus der oeffentlichen Seite
// ════════════════════════════════════════════════════════════════════════════

// Startwert: bewusste Wahl -> System -> hell (wie in der App).
assert.equal(startTheme({ speicher: { getItem: () => 'dark' }, system: 'light' }), 'dark')
assert.equal(startTheme({ speicher: { getItem: () => 'light' }, system: 'dark' }), 'light')
assert.equal(startTheme({ speicher: { getItem: () => null }, system: 'dark' }), 'dark')
assert.equal(startTheme({ speicher: null, system: 'dark' }), 'dark')
assert.equal(startTheme({}), 'light')
assert.equal(
  startTheme({ speicher: { getItem: () => { throw new Error('gesperrt') } }, system: 'dark' }),
  'dark',
  'gesperrter Speicher (Privatmodus) muss auf die Systemeinstellung zurueckfallen',
)

// Und der Wert kommt wirklich ans Wurzelelement.
{
  const gesetzt = []
  const wert = themeSetzen({
    dokument: { documentElement: { setAttribute: (k, v) => gesetzt.push([k, v]) } },
    speicher: { getItem: () => null },
    abfrage: () => ({ matches: true }),
  })
  assert.equal(wert, 'dark')
  assert.deepEqual(gesetzt, [['data-theme', 'dark']],
    'REG-1c: `data-theme` wird nicht am <html> gesetzt')
}

// Ohne DOM (Test/Server) darf nichts fliegen.
assert.doesNotThrow(() => themeSetzen({}))
assert.equal(themeSetzen({}), 'light')

// Systemwechsel wird nur verfolgt, wenn keine Wahl gespeichert ist.
{
  const gesetzt = []
  const hoerer = []
  themeSetzen({
    dokument: { documentElement: { setAttribute: (k, v) => gesetzt.push(v) } },
    speicher: { getItem: () => 'light' },
    abfrage: () => ({ matches: false, addEventListener: (_, f) => hoerer.push(f) }),
  })
  assert.equal(hoerer.length, 0, 'REG-1c: eine gespeicherte Wahl darf nicht ueberschrieben werden')

  const gesetzt2 = []
  const hoerer2 = []
  themeSetzen({
    dokument: { documentElement: { setAttribute: (k, v) => gesetzt2.push(v) } },
    speicher: { getItem: () => null },
    abfrage: () => ({ matches: false, addEventListener: (_, f) => hoerer2.push(f) }),
  })
  assert.equal(hoerer2.length, 1, 'REG-1c: der Systemwechsel wird nicht verfolgt')
  hoerer2[0]({ matches: true })
  assert.deepEqual(gesetzt2, ['light', 'dark'], 'REG-1c: der Wechsel wirkt nicht')
}

// Beide oeffentlichen Einstiege setzen das Theme (und laden die Tokens).
for (const eintrag of ['registrierung/main.js', 'gast/main.js']) {
  const quelle = src(eintrag)
  assert.match(quelle, /themeSetzen\(/, `${eintrag}: REG-1c — Theme wird nicht gesetzt`)
  assert.match(
    quelle,
    /from '\.\.\/diakonos\/composables\/oeffentliches-theme\.mjs'/,
    `${eintrag}: REG-1c — falscher/kein Import der Theme-Regel`,
  )
  // Vor dem Mounten: sonst blitzt die helle Flaeche kurz auf.
  assert.ok(
    quelle.indexOf('themeSetzen(') < quelle.indexOf('createApp('),
    `${eintrag}: REG-1c — Theme wird erst nach dem Mounten gesetzt (helles Aufblitzen)`,
  )
}

// `tokens.css` liefert die dunklen Werte nur unter diesem Merkmal — die
// Voraussetzung der ganzen Reparatur bleibt damit festgehalten.
assert.match(
  src('diakonos/tokens.css'),
  /\[data-theme="dark"\]/,
  'tokens.css: die dunklen Tokens haengen an [data-theme="dark"]',
)

console.log('REG-1c (5): alle Prüfungen bestanden')
