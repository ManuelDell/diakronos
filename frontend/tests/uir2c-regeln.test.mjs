/**
 * UI-R2c — Folgekarte zu UI-R2b: reine Regeln und Quelltext-Regeln, die der
 * Mount-Test (tests/uir2c-mount.test.mjs) NICHT sehen kann.
 *
 *   P4  Der Kommentar in `stufeSetzen` sagt die Wahrheit: der Server setzt bei
 *       „Moderieren“ immer „Lesen“ mit (Backend `setze_freigabe`, R-12p). Das
 *       Lesen-Häkchen einer moderierenden Zeile ist ohne Vergaberecht gesperrt
 *       — sonst nähme ein Klick das Lesen weg, und der Server setzte es sofort
 *       wieder.
 *   P5  „Gruppe freigeben“ zeigt einen Ladezustand: der Schlüssel, den der
 *       Knopf liest, ist DERSELBE, den die Karte beim Senden setzt.
 *   P6  Mit `nurAnzeigen` steht kein leerer Erklärsatz in der Fläche.
 *   P7  Die toten Reste sind weg (`darfModerieren()` in der Karte, die
 *       Rückfall-Prop `darfModerieren` samt Doku im Baustein).
 *
 * Lauf: TZ=Europe/Berlin node --test tests/uir2c-regeln.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { freigabeFelder } from '../src/diakonos/components/gruppen/kalenderRechte.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const RECHTE = lies('components/gruppen/KalenderRechte.vue')
const KALENDERDATEI = lies('components/gruppen/KalenderEinstellungen.vue')
const REGELN = lies('components/gruppen/kalenderRechte.mjs')
const skriptVon = (text) => text.slice(text.indexOf('<script'), text.indexOf('</script>'))

// ══════════════════════════════════════════════════════════════════════════
// P4 · „Moderieren“ schließt „Lesen“ ein — Kommentar und Sperre
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2c/P4: ein Moderieren ohne Lesen gibt es nicht (Server setzt Lesen mit)', () => {
  // Die Regel des Servers (R-12p, `rechte/verwaltung.py`): bei
  // `moderieren=True` wird `lesen=True` mitgesetzt. Die Oberfläche schickt
  // deshalb nie ein Moderieren mit Lesen=false.
  const ohneLesen = freigabeFelder({ lesen: true, schreiben: false, moderieren: false },
    { lesen: false, schreiben: false, moderieren: true }, { darf_moderieren_vergeben: true })
  assert.equal(ohneLesen.moderieren, false, 'Moderieren fährt mit Lesen=false mit')
  assert.equal(ohneLesen.lesen, false)
})

test('UI-R2c/P4: der Kommentar „die Zeile fiele also ganz weg“ ist richtiggestellt', () => {
  const skript = skriptVon(RECHTE)
  assert.ok(!/fiele also ganz weg/.test(skript),
    'der falsche Kommentar („die Zeile fiele also ganz weg“) steht noch da')
  // Der richtige Grund steht dort: der Server setzt Lesen bei Moderieren mit.
  const ab = skript.indexOf('function stufeSetzen')
  const block = skript.slice(ab, ab + 1400)
  assert.match(block, /Lesen/, 'der Kommentar nennt das Lesen nicht')
  assert.match(block, /setzt|mit/i, 'der Kommentar sagt nicht, dass der Server Lesen mit setzt')
})

test('UI-R2c/P4: das Lesen-Häkchen einer moderierenden Zeile ist ohne Vergaberecht gesperrt', () => {
  const skript = ohneKommentare(skriptVon(RECHTE))
  const sperre = skript.slice(skript.indexOf('function zeileGesperrt'), skript.indexOf('function namenTeile'))
  // `lesen` in einer Zeile MIT Moderieren und OHNE Vergaberecht → gesperrt.
  assert.match(sperre, /stufe === 'lesen'/, 'die Sperre kennt die Stufe „Lesen“ nicht')
  assert.match(sperre, /moderieren/, 'die Sperre kennt das Prüfrecht der Zeile nicht')
})

function ohneKommentare(t) {
  return t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

// ══════════════════════════════════════════════════════════════════════════
// P5 · „Gruppe freigeben“ hat einen echten Ladezustand
// ══════════════════════════════════════════════════════════════════════════
// (verhaltensgeprüft im Mount-Test: tests/uir2c-mount.test.mjs, C4 — der Knopf
//  zeigt „lädt“ und ist gesperrt, sobald die Karte den Schlüssel setzt)

// ══════════════════════════════════════════════════════════════════════════
// P6 · nurAnzeigen: kein leerer Erklärsatz
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2c/P6: mit `nurAnzeigen` rendert kein leeres Erklärungselement', () => {
  const quelle = ohneKommentare(RECHTE)
  // Der Erklärsatz (`kr-grund`) steht im `v-else` eines `v-if`, das `nurAnzeigen`
  // schon ausschließt — dort ist er immer leer. Er braucht eine eigene Bedingung.
  const tabellenZelle = quelle.slice(quelle.indexOf('<td class="kr-aktion">'),
    quelle.indexOf('</td>', quelle.indexOf('<td class="kr-aktion">')))
  assert.match(tabellenZelle, /kr-grund/,
    'Vorbedingung: die Aktionszelle ohne Erklärsatz gefunden')
  const grundZeile = tabellenZelle.split('\n').find((z) => /kr-grund/.test(z)) || ''
  assert.ok(/v-(else-)?if=/.test(grundZeile) && /entfernenHinweis/.test(grundZeile),
    'der Erklärsatz erscheint ohne eigene Bedingung (leer bei nurAnzeigen): ' + grundZeile.trim())
  // Die Handy-Liste ebenso.
  const liBlock = quelle.slice(quelle.indexOf('class="kr-zeilen"'), quelle.indexOf('</ul>'))
  const liGrund = liBlock.split('\n').find((z) => /kr-grund/.test(z)) || ''
  assert.ok(/v-(else-)?if=/.test(liGrund) && /entfernenHinweis/.test(liGrund),
    'der Erklärsatz der Liste erscheint ohne eigene Bedingung: ' + liGrund.trim())
})

// ══════════════════════════════════════════════════════════════════════════
// P7 · tote Reste
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2c/P7: die tote Funktion `darfModerieren()` ist aus der Karte entfernt', () => {
  const skript = skriptVon(KALENDERDATEI)
  assert.ok(!/function darfModerieren\s*\(/.test(skript), 'die tote Funktion steht noch in der Karte')
  assert.ok(!/\bdarfModerieren\s*\(/.test(ohneKommentare(skript)), 'irgendwo wird sie noch gerufen')
})

test('UI-R2c/P7: die Rückfall-Prop `darfModerieren` ist samt Doku entfernt', () => {
  const skript = skriptVon(RECHTE)
  assert.ok(!/darfModerieren:\s*\{/.test(skript), 'die Prop steht noch im Baustein')
  assert.ok(!/props\.darfModerieren/.test(ohneKommentare(skript)), 'die Prop wird noch gelesen')
  assert.ok(!/Rückfall für „Moderieren“/.test(skript), 'die Doku zur Prop steht noch da')
  // Und die Karte reicht sie nicht mehr durch.
  assert.ok(!/darf-moderieren=/.test(KALENDERDATEI), 'die Karte reicht die Prop noch durch')
})

// ══════════════════════════════════════════════════════════════════════════
// P8 (UI-R2d) · der Kommentar zu „Lesen abhaken“ sagt die Wahrheit
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2d/P8: der Kommentar zum Lesen-Häkchen beschreibt die Folge richtig', () => {
  // MUSS 2: der alte Kommentar behauptete, das Lesen einer moderierenden Zeile
  // lasse die Zeile STEHEN. Das ist falsch: `freigabeFelder` (kalenderRechte.mjs)
  // sendet `moderieren = neu.moderieren && lesen` — mit lesen=false fällt
  // „Moderieren“ mit, und alles-false ENTFERNT die Zeile (Serverregel).
  const quelle = RECHTE
  // Der Kommentar steht ÜBER der Funktion — also ab dem Doc-Block davor.
  const skript = quelle.slice(quelle.indexOf('/** Ein Kästchen umschalten'), quelle.indexOf('function freigabeEntfernen'))
  assert.ok(!/lässt die Zeile stehen/.test(skript),
    'der falsche Satz („lässt die Zeile stehen“) steht noch im Kommentar')
  assert.ok(!/entziehen ist eine eigene Handlung/.test(skript),
    'die alte, irreführende Begründung steht noch im Kommentar')
  assert.match(skript, /moderieren = neu\.moderieren && lesen/,
    'der Kommentar nennt die Regel aus `freigabeFelder` nicht')
  // Der Satz bricht im Quelltext um — „// “ steht zwischen den Wörtern.
  assert.match(skript, /GANZE[\s/]+Zeile/,
    'der Kommentar sagt nicht, dass die Zeile dabei ganz wegfällt')

  // Gegenprobe an der QUELLE der Regel: `freigabeFelder` hängt „Moderieren“ an
  // „Lesen“. Bleibt das so, stimmt der Kommentar.
  assert.match(ohneKommentare(REGELN), /moderieren = Boolean\(lage\?\.darf_moderieren_vergeben\)[\s\S]{0,80}&& felder\.lesen/,
    'die Regel `moderieren = neu.moderieren && lesen` ist nicht mehr da — der Kommentar wäre wieder falsch')
})
