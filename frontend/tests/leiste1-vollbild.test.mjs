/**
 * LEISTE-1 — Nachrichten im Vollbild (Manuel 23.11., Befund DMB-4971 + Handy-Foto,
 * Entwurf Variante A).
 *
 * Befund: Auf dem Handy stand „Nachrichten“ zweimal (App-Kopfzeile + Seitenkopf)
 * und „Alle Gespräche“ zweimal („Alle Gespräche an einem Ort.“ + Listenkopf);
 * am Desktop zusätzlich ein Kartenrahmen um Liste und Verlauf.
 *
 * Geprüft:
 *   V1  EINE Stelle (router.js) entscheidet, welche Adresse Vollbild läuft —
 *       Nachrichten ja (mit Seitenleiste), Assistent ja (ohne), alles andere nein.
 *   V2  App.vue: App-Kopfzeile nur außerhalb des Vollbilds; Seitenleiste trägt
 *       die Glocke genau dann, wenn die Kopfzeile fehlt (nie zwei Glocken).
 *   V3  Nachrichten.vue: kein Seitenkopf, keine der doppelten Zeilen mehr.
 *   V4  Je Lage genau EIN Suchfeld (Handy: Kopfzeile der Seite, Desktop: Liste).
 *   V5  ChatListe ohne Kopf rendert „Alle Gespräche“ nicht (echte Logik).
 *   V6  Strg+K bleibt global (Befehlspalette hört am Fenster, nicht am Feld).
 *
 * Lauf: node --test tests/leiste1-*.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')
const ohneKommentare = (t) => t.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

// ── V1 · router.js: die eine Liste ─────────────────────────────────────────
function vollbildLogik() {
  const quelle = lies('router.js')
  const a = quelle.indexOf('const VOLLBILD_MUSTER')
  const b = quelle.indexOf('export function darfSeitenleiste')
  assert.ok(a > 0 && b > a, 'router.js: VOLLBILD_MUSTER / darfSeitenleiste fehlen')
  const ende = quelle.indexOf('\n}\n', b) + 3
  const code = quelle.slice(a, ende).replace(/^export /gm, '')
  const ctx = {}
  vm.createContext(ctx)
  vm.runInContext(`${code}\nthis.vollbildRoute = vollbildRoute; this.darfSeitenleiste = darfSeitenleiste`, ctx)
  return ctx
}

test('LEISTE-1 · V1: router.js entscheidet Vollbild und Seitenleiste an EINER Stelle', () => {
  const { vollbildRoute, darfSeitenleiste } = vollbildLogik()
  for (const h of ['#/nachrichten', '#/nachrichten/chat-gespraech-1', '#/nachrichten/suche?q=x', '#/einrichtung']) {
    assert.equal(vollbildRoute(h), true, `${h} läuft nicht im Vollbild`)
  }
  for (const h of ['#/', '#/gruppen', '#/beitraege', '#/wiki', '#/nachrichtenarchiv']) {
    assert.equal(vollbildRoute(h), false, `${h} läuft fälschlich im Vollbild`)
  }
  assert.equal(darfSeitenleiste('#/nachrichten'), true, 'Nachrichten verliert die Seitenleiste')
  assert.equal(darfSeitenleiste('#/nachrichten/chat-gespraech-1'), true)
  assert.equal(darfSeitenleiste('#/einrichtung'), false, 'der Assistent bekommt eine Seitenleiste')
})

// ── V2 · App.vue: Rahmen und Glocke ───────────────────────────────────────
test('LEISTE-1 · V2: App-Kopfzeile nur außerhalb des Vollbilds, Glocke nie doppelt', () => {
  const app = ohneKommentare(lies('App.vue'))
  assert.match(app, /<AppTopbar\s+v-if="!isVollbildMode"/, 'die App-Kopfzeile steht im Vollbild')
  assert.match(app, /<AppSidebar v-if="!vollbildRahmenLos" :glocke="isVollbildMode"/,
    'die Seitenleiste trägt die Glocke nicht genau dann, wenn die Kopfzeile fehlt')
  assert.match(app, /'dk-app--vollbild': vollbildRahmenLos/,
    'das einspaltige Gerüst gilt auch dort, wo die Seitenleiste stehen bleibt (Seitenleiste über volle Breite)')
  assert.doesNotMatch(app, /sidebarCollapsed\.value = true/,
    'Nachrichten klappt die Seitenleiste ungefragt ein (der Entwurf zeigt sie offen)')
  const leiste = ohneKommentare(lies('components/AppSidebar.vue'))
  assert.match(leiste, /<Glocke v-if="glocke" knopf="eintrag"/, 'die Glocke der Seitenleiste hängt nicht an `glocke`')
  assert.match(leiste, /glocke:\s*\{\s*type:\s*Boolean,\s*default:\s*false/, '`glocke` ist nicht standardmäßig aus')
})

// ── V3 · Nachrichten.vue: keine doppelten Überschriften ───────────────────
test('LEISTE-1 · V3: Nachrichten hat keinen Seitenkopf und keine doppelten Zeilen', () => {
  const seite = ohneKommentare(lies('pages/Nachrichten.vue'))
  assert.doesNotMatch(seite, /<DkPageHeader/, 'der Seitenkopf „Nachrichten“ ist zurück')
  assert.doesNotMatch(seite, /Alle Gespräche an einem Ort/, 'die Unterzeile „Alle Gespräche an einem Ort.“ ist zurück')
  assert.match(seite, /<ChatListe[\s\S]*?:kopf="false"/, 'der Listenkopf „Alle Gespräche“ ist an')
})

// ── V4 · je Lage genau ein Suchfeld ───────────────────────────────────────
test('LEISTE-1 · V4: je Lage genau EIN Suchfeld (gleiche ref nie doppelt im DOM)', () => {
  const seite = ohneKommentare(lies('pages/Nachrichten.vue'))
  const tpl = seite.slice(0, seite.indexOf('<script'))
  const suchen = [...tpl.matchAll(/<ChatSuche\b[^>]*>/g)].map((m) => m[0])
  assert.equal(suchen.length, 2, 'erwartet: Handy-Kopf + Listenkopf')
  // Die Kopfzeile der Seite steht nur am Handy und nur ohne offenes Gespräch.
  assert.match(tpl, /class="dk-chat-leiste"/)
  assert.match(tpl, /v-if="modulAn && istHandyLage && !offeneKennung"\s*\n\s*class="dk-chat-leiste"/,
    'die Handy-Kopfzeile steht auch am Desktop oder über dem offenen Gespräch')
  assert.ok(suchen.some((s) => /v-if="!istHandyLage"/.test(s)), 'das Suchfeld der Liste steht auch am Handy')
})

// ── V5 · ChatListe ohne Kopf (echte Logik) ────────────────────────────────
test('LEISTE-1 · V5: ohne Kopf keine Überschrift, Zähler-Zeile nur bei Ungelesenem', async () => {
  const { listenkopfSichtbar } = await import('../src/diakonos/composables/nachrichtenLogik.mjs')
  assert.equal(listenkopfSichtbar({ kopf: false, ungelesen: 0 }), false, 'leere Kopfzeile ohne Inhalt')
  assert.equal(listenkopfSichtbar({ kopf: false, ungelesen: 3 }), true, 'der Zähler „3 neu“ verliert seine Zeile')
  assert.equal(listenkopfSichtbar({}), true, 'Standard (andere Aufrufer) verliert den Kopf')
  const liste = ohneKommentare(lies('components/chat/ChatListe.vue'))
  assert.match(liste, /<h2 v-if="kopf" class="dk-chat-liste-titel">Alle Gespräche<\/h2>/,
    '„Alle Gespräche“ hängt nicht am Schalter `kopf`')
})

// ── V6 · Strg+K bleibt global ─────────────────────────────────────────────
test('LEISTE-1 · V6: Strg+K hört am Fenster (auch ohne App-Kopfzeile)', () => {
  const palette = lies('components/Befehlspalette.vue')
  assert.match(palette, /window\.addEventListener\('keydown', beiKuerzel\)/,
    'die Befehlspalette hängt am Suchfeld der Kopfzeile statt am Fenster')
  const app = ohneKommentare(lies('App.vue'))
  assert.match(app, /<Befehlspalette\b/, 'die Befehlspalette ist nicht mehr in der App')
  assert.doesNotMatch(app, /<Befehlspalette[^>]*v-if="!isVollbildMode"/, 'die Befehlspalette fehlt im Vollbild')
})
