/**
 * PLAN-M1 — Hinweis am Handy: „Pläne bearbeitest du am besten an einem
 * Desktop oder Tablet im Querformat. Ansehen geht auch hier.“
 * (Manuel 2026-10-23)
 *
 * Der Befund: Auf dem Handy ist das Bearbeiten von Plänen mühsam. Der Hinweis
 * darf deshalb NUR dort erscheinen, wo er etwas nützt:
 *
 *   * schmale Bildschirme (dieselbe 720-px-Grenze wie die Mobil-Umschaltung
 *     der App — index.css `@media (max-width: 720px)`),
 *   * nur mit Bearbeitungsrecht (`darf_bearbeiten` vom Server),
 *   * und nur, solange der Benutzer ihn nicht geschlossen hat
 *     (localStorage, je Benutzer, 30 Tage).
 *
 * Ansehen bleibt vollständig möglich — nichts wird gesperrt — und reine
 * Betrachter sehen den Hinweis nie. Die Bedingungen stehen als reine
 * Funktionen in `composables/handyHinweis.mjs` (hier ohne Browser geprüft);
 * die drei Plan-Rahmen-Seiten setzen sie über den Baustein `PrHandyHinweis`
 * um.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  HANDY_HINWEIS_PRAEFIX, HANDY_HINWEIS_PX, HANDY_HINWEIS_TAGE, HANDY_HINWEIS_TEXT,
  handyHinweisKern, handyHinweisSchluessel, hinweisZeigen, istSchmal,
  istHandyHinweisLage, handyHinweisLage, SEHR_SCHMAL_PX,
} from '../src/diakonos/composables/handyHinweis.mjs'
import { MOBIL_GRENZE_PX } from '../src/diakonos/composables/eingabeart.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const PLAN = lies('pages/planrahmen/Plan.vue')
const EDITOR = lies('pages/planrahmen/PlantypEditor.vue')
const STAMM = lies('pages/planrahmen/Stammdaten.vue')
const BAUSTEIN = lies('components/planrahmen/PrHandyHinweis.vue')
const SEITEN = [
  ['Plan.vue', PLAN],
  ['PlantypEditor.vue', EDITOR],
  ['Stammdaten.vue', STAMM],
]

/** Storage-Attrappe wie window.localStorage. */
function speicher() {
  const daten = new Map()
  return {
    getItem: (k) => (daten.has(k) ? daten.get(k) : null),
    setItem: (k, v) => { daten.set(k, String(v)) },
    removeItem: (k) => { daten.delete(k) },
    get length() { return daten.size },
    key: (i) => [...daten.keys()][i] ?? null,
    _daten: daten,
  }
}

const TAG = 24 * 60 * 60 * 1000

// ── Die Bedingungen (Kern, ohne Browser) ───────────────────────────────────

test('PLAN-M1: der Wortlaut ist der der Karte', () => {
  assert.equal(HANDY_HINWEIS_TEXT,
    'Pläne bearbeitest du am besten an einem Desktop oder Tablet im Querformat. Ansehen geht auch hier.')
  assert.equal(HANDY_HINWEIS_TAGE, 30)
  // Der Baustein nimmt genau diesen Wortlaut als Vorgabe (kein zweiter Text,
  // der auseinanderlaufen kann).
  assert.match(BAUSTEIN, /import \{ HANDY_HINWEIS_TEXT, hinweisZeigen \}/)
  assert.match(BAUSTEIN, /text: \{ type: String, default: HANDY_HINWEIS_TEXT \}/)
  assert.match(BAUSTEIN, /\{\{ text \}\}/)
})

test('PLAN-M1: schmal heißt höchstens 720 px — dieselbe Grenze wie die App', () => {
  // Die Zahl steht EINMAL in der App (eingabeart.mjs, MOBIL_GRENZE_PX);
  // HANDY_HINWEIS_PX leitet sich davon ab (FIX-6c).
  assert.equal(HANDY_HINWEIS_PX, 720)
  assert.equal(HANDY_HINWEIS_PX, MOBIL_GRENZE_PX, 'Hinweis und Layout teilen die eine Grenze')
  assert.equal(istSchmal(390), true)
  assert.equal(istSchmal(720), true)
  assert.equal(istSchmal(721), false)
  assert.equal(istSchmal(1366), false)
  // Ohne Messwert (0/NaN) nie „schmal“ — lieber kein Hinweis als ein falscher.
  assert.equal(istSchmal(0), false)
  assert.equal(istSchmal(undefined), false)
  assert.equal(istSchmal('kaputt'), false)
  // Und die CSS-Grenze der App ist dieselbe (der Hinweis darf nicht bei einer
  // Breite auftauchen, bei der die Seitenleiste noch sichtbar ist).
  // DEV-B6 (Manuel 09.11.): Die Umschaltung hängt NICHT mehr nur an der Breite
  // — „auf einem Laptop darf nie die Handyleiste kommen“. Der Gerüst-Block
  // ist die Handy-Lage (grob + 720 px, bzw. flaches Querformat; Quelle:
  // `--layout-mobil` in tokens.css); die 720-px-Grenze bleibt darin unverändert.
  // DEV-B6 (Review-Nacharbeit 10.11.): Das Gerüst hängt jetzt an der EINEN
  // Klasse `.dk-app--handy` (Quelle `composables/handyLage.mjs`); die Bedingung
  // steht dort als Zeichenkette und im Token `--layout-mobil`. Geprüft wird
  // beides — die 720-px-Grenze bleibt darin unverändert.
  const css = lies('index.css')
  assert.match(css, /\.dk-app\.dk-app--handy \{ grid-template-columns: 1fr; \}/,
    'index.css: Gerüst hängt an der Handy-Lage-Klasse')
  const tokens = lies('tokens.css')
  assert.match(tokens,
    /--layout-mobil:\s*\(pointer: coarse\) and \(max-width: .*720|--layout-mobil:[^;]*max-width: 720px/,
    'tokens.css: die 720-px-Grenze steht in der Handy-Lage')
})

test('DEV-B6: der Hinweis erscheint nur in der HANDY-Lage (Zeiger + Breite)', () => {
  // grober Zeiger + schmal -> Hinweis; Maus-Laptop bei 702/400 px -> nicht.
  assert.equal(istHandyHinweisLage(390, { grob: true }), true, 'Handy')
  assert.equal(istHandyHinweisLage(720, { grob: true }), true, 'Grenze gehört dazu')
  assert.equal(istHandyHinweisLage(702, { grob: false }), false, 'Laptop 702 px mit Maus (Befund)')
  assert.equal(istHandyHinweisLage(620, { grob: false }), false, 'schmales Mausfenster: Seitenleiste, kein Handy')
  assert.equal(istHandyHinweisLage(1024, { grob: true }), false, 'Tablet quer: nicht schmal')
  // flaches Querformat ist Handy-Lage (OP-HANDY-10)
  assert.equal(istHandyHinweisLage(844, { grob: true, hoehe: 390 }), true, 'Handy quer')
  // sehr schmale Fenster: Planraster auch mit Maus nicht sinnvoll bedienbar
  assert.equal(istHandyHinweisLage(SEHR_SCHMAL_PX, { grob: false }), true, 'sehr schmal (430 px)')
  assert.equal(istHandyHinweisLage(SEHR_SCHMAL_PX + 1, { grob: false }), false)
  // ohne Messwert nie „Handy-Lage“
  assert.equal(istHandyHinweisLage(0, { grob: true }), false)
  assert.equal(istHandyHinweisLage(undefined, { grob: true }), false)
  // Browser-Auskunft: ohne matchMedia (Node/jsdom) bleibt es bei der Breite.
  assert.deepEqual(handyHinweisLage({ matchMedia: null }),
    { grob: false, breite: 0, hoehe: 0 })
  const grobAbfrage = (abfrage) => ({ matches: abfrage === '(pointer: coarse)' })
  const lage = handyHinweisLage({ matchMedia: grobAbfrage, fenster: { innerWidth: 390, innerHeight: 844 } })
  // DEV-B6 (Nacharbeit 10.11.): Die Lage trägt jetzt auch die EINE
  // Handy-Lage-Abfrage der App (dieselbe Zeichenkette wie Token/App.vue) —
  // hier ist sie false, weil die Attrappe nur `(pointer: coarse)` kennt.
  assert.deepEqual(lage, { grob: true, breite: 390, hoehe: 844, handyLage: false })
})

test('PLAN-M1: Hinweis nur schmal UND mit Bearbeitungsrecht', () => {
  // schmal + Recht -> zeigen
  assert.equal(hinweisZeigen({ schmal: true, darfBearbeiten: true }), true)
  // Betrachter (kein Recht) -> nie, auch nicht am Handy
  assert.equal(hinweisZeigen({ schmal: true, darfBearbeiten: false }), false)
  // Desktop -> nie, auch mit Recht
  assert.equal(hinweisZeigen({ schmal: false, darfBearbeiten: true }), false)
  // geschlossen -> nicht mehr zeigen
  assert.equal(hinweisZeigen({ schmal: true, darfBearbeiten: true, geschlossen: true }), false)
  // Vorgaben sind „nichts anzeigen“ (fail closed).
  assert.equal(hinweisZeigen(), false)
})

test('PLAN-M1: Schließen gilt je Benutzer 30 Tage, dann kommt der Hinweis zurück', () => {
  const s = speicher()
  let jetzt = 1_000_000_000_000
  const anna = handyHinweisKern({ speicher: s, benutzer: () => 'anna@example.org', jetzt: () => jetzt })
  const bernd = handyHinweisKern({ speicher: s, benutzer: () => 'bernd@example.org', jetzt: () => jetzt })

  // Vor dem Schließen: nichts gemerkt -> Hinweis erscheint.
  assert.equal(anna.geschlossen(), false)
  assert.equal(anna.schliessen(), true)
  assert.equal(anna.geschlossen(), true)
  // Der andere Benutzer am selben Browser ist unberührt.
  assert.equal(bernd.geschlossen(), false)
  // Der Schlüssel hängt am Benutzer.
  assert.equal(anna.schluessel(), handyHinweisSchluessel('anna@example.org'))
  assert.ok(anna.schluessel().startsWith(HANDY_HINWEIS_PRAEFIX))
  assert.notEqual(anna.schluessel(), bernd.schluessel())

  // 29 Tage später: weiterhin geschlossen …
  jetzt += 29 * TAG
  assert.equal(anna.geschlossen(), true)
  // … nach 30 Tagen abgelaufen -> wieder zeigen, Eintrag ist weg.
  jetzt += 1 * TAG
  assert.equal(anna.geschlossen(), false)
  assert.equal(s.getItem(anna.schluessel()), null)
})

test('PLAN-M1: der geschlossene Zustand ist ein Ablaufdatum, kein Dauerzustand', () => {
  const s = speicher()
  const jetzt = 5_000_000_000_000
  const k = handyHinweisKern({ speicher: s, benutzer: () => 'anna@example.org', jetzt: () => jetzt })
  k.schliessen()
  const eintrag = JSON.parse(s.getItem(k.schluessel()))
  assert.equal(eintrag.bis, jetzt + HANDY_HINWEIS_TAGE * TAG)
  // Zurücksetzen (z. B. „wieder erinnern“) räumt auf.
  assert.equal(k.setzen(false), true)
  assert.equal(s.getItem(k.schluessel()), null)
  assert.equal(k.geschlossen(), false)
})

test('PLAN-M1: verstümmelter oder fehlender Speicher zeigt den Hinweis (still)', () => {
  const s = speicher()
  s.setItem(handyHinweisSchluessel('anna@example.org'), 'kaputt')
  const k = handyHinweisKern({ speicher: s, benutzer: () => 'anna@example.org' })
  assert.equal(k.geschlossen(), false)
  // Ohne Speicher (privater Modus) funktioniert alles still weiter.
  const ohne = handyHinweisKern({ speicher: null, benutzer: () => 'anna@example.org' })
  assert.equal(ohne.geschlossen(), false)
  assert.equal(ohne.setzen(true), false)
  assert.equal(ohne.schliessen(), true)
  // Ein gesperrter Speicher darf nie werfen.
  const gesperrt = handyHinweisKern({
    speicher: {
      getItem() { throw new Error('gesperrt') },
      setItem() { throw new Error('gesperrt') },
      removeItem() { throw new Error('gesperrt') },
    },
    benutzer: () => 'anna@example.org',
  })
  assert.equal(gesperrt.geschlossen(), false)
  assert.doesNotThrow(() => gesperrt.setzen(true))
  assert.doesNotThrow(() => gesperrt.schliessen())
})

// ── Die drei Plan-Rahmen-Seiten ────────────────────────────────────────────

test('PLAN-M1: alle drei Plan-Rahmen-Seiten zeigen den Baustein', () => {
  for (const [name, quelle] of SEITEN) {
    assert.match(quelle, /import PrHandyHinweis from '\.\.\/\.\.\/components\/planrahmen\/PrHandyHinweis\.vue'/,
      `${name}: Baustein nicht eingebunden`)
    assert.match(quelle, /<PrHandyHinweis[\s\S]{0,200}?:sichtbar="handyHinweisZeigen"/,
      `${name}: Sichtbarkeit nicht gebunden`)
    assert.match(quelle, /@geschlossen="handyHinweisSchliessen"/,
      `${name}: Schließen nicht verdrahtet`)
    // Der Hinweis hängt am SERVER-Recht der Seite, nicht an einer Annahme.
    assert.match(quelle, /:darf-bearbeiten="darfBearbeiten"|:darf-bearbeiten="darfVorlageBearbeiten"/,
      `${name}: Bearbeitungsrecht nicht durchgereicht`)
    // Größe wird nachgezogen (Gerät drehen, Fenster ziehen) und beim Abbau
    // abgemeldet.
    assert.match(quelle, /addEventListener\('resize', beiGroessenAenderung\)/, `${name}: resize fehlt`)
    assert.match(quelle, /removeEventListener\('resize', beiGroessenAenderung\)/,
      `${name}: resize nicht abgemeldet`)
    // Der gemerkte Zustand wird beim Aufbau gelesen.
    assert.match(quelle, /handyHinweisGeschlossen\.value = handyHinweis\.geschlossen\(\)/,
      `${name}: gemerkter Zustand wird nicht gelesen`)
  }
  // Die Sichtbarkeit kombiniert Schließen-Zustand UND die Bedingungen
  // (schmal + Recht) — nicht nur eine der beiden.
  for (const [name, quelle] of SEITEN) {
    const block = quelle.slice(quelle.indexOf('const handyHinweisZeigen'), quelle.indexOf('const handyHinweisZeigen') + 400)
    assert.match(block, /handyHinweisGeschlossen\.value/, `${name}: Schließen-Zustand fehlt bei der Sichtbarkeit`)
    // DEV-B6: die Handy-Lage liest Breite UND primären Zeiger.
    assert.match(block,
      /schmal: istHandyHinweisLage\([^)]*(?:breite|breiteAmFenster)\.value, lageAmFenster\.value\)/,
      `${name}: Handy-Lage (Breite + Zeiger) fehlt bei der Sichtbarkeit`)
    assert.match(block, /darfBearbeiten: darf/, `${name}: Recht fehlt bei der Sichtbarkeit`)
  }
})

test('PLAN-M1: reine Betrachter sehen den Hinweis nicht (zweite Wand im Baustein)', () => {
  // Der Baustein prüft das Recht SELBST noch einmal — ein alter Cache-Stand
  // oder eine Seite, die `sichtbar` falsch setzt, blendet ihn nicht ein.
  assert.match(BAUSTEIN, /darfBearbeiten: \{ type: Boolean, default: false \}/)
  assert.match(BAUSTEIN, /const sichtbar = computed\(\(\) => hinweisZeigen\(\{/)
  assert.match(BAUSTEIN, /darfBearbeiten: props\.darfBearbeiten/)
  assert.match(BAUSTEIN, /v-if="sichtbar"/)
})

test('PLAN-M1: nichts wird gesperrt — kein Sperr- oder Abschaltzustand', () => {
  // Der Hinweis ist reine Auskunft: die Seiten bekommen weder ein
  // `deaktiviert`/`gesperrt` noch wird die Ansicht ersetzt.
  for (const [name, quelle] of SEITEN) {
    assert.doesNotMatch(quelle, /handyHinweis[\s\S]{0,80}(deaktiviert|gesperrt|nurAnsicht)/,
      `${name}: Hinweis sperrt etwas`)
  }
  // Und er sitzt im Inhaltsstrom (kein Overlay/Teleport), damit er keine
  // Daten verdeckt.
  assert.doesNotMatch(BAUSTEIN, /Teleport/)
  assert.match(BAUSTEIN, /role="status"/)
})

test('PLAN-M1: der Baustein trägt keine festen Farben (Wächter-Regel)', () => {
  const farben = BAUSTEIN.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g) || []
  assert.deepEqual(farben, [], `feste Farbwerte im Baustein: ${farben.join(', ')}`)
  // Darstellung aus den vorhandenen Tokens, Knopf aus dem Bausteinsatz.
  assert.match(BAUSTEIN, /var\(--info-soft\)/)
  assert.match(BAUSTEIN, /var\(--text\)/)
  // UX1g: Der Schliessen-Weg ist ein Knopf des Systems (DkButton), nicht
  // mehr die Altklasse `dk-btn …`.
  assert.match(BAUSTEIN, /<DkButton[\s\S]{0,120}variant="ghost"/,
    'der Weg des Hinweises ist ein DkButton (ghost)')
})

test('DEV-B6: der Hinweis folgt der EINEN Handy-Lage (auch flaches Maus-Fenster)', () => {
  // Review-Punkt 2/3: Die Querformat-Alternative prüft den Zeiger mit — ein
  // flaches Maus-Fenster (1280×450) bekommt den Hinweis NICHT mehr.
  assert.equal(istHandyHinweisLage(1280, { grob: false, hoehe: 450, handyLage: false }), false,
    'flaches Maus-Fenster: kein Handy-Hinweis')
  assert.equal(istHandyHinweisLage(1280, { grob: true, hoehe: 450, handyLage: true }), true,
    'flaches Touchgerät: Handy-Hinweis')
  // Sehr schmal bleibt auch mit Maus (dort ist nichts bearbeitbar).
  assert.equal(istHandyHinweisLage(390, { grob: false, handyLage: false }), true)
})
