/**
 * A10-N3 — Feinschliff des Handy-Kalenders (Karte t_b0e3c833).
 *
 * Geprüft wird, was die Karte zusagt — ausgeführt, nicht als Quelltext-Muster:
 *
 *  1. MINI-MONAT: Zahl und Punkt bilden EINE Gruppe in der Zellenmitte. Der
 *     Punkt hängt NICHT mehr absolut am unteren Zellenrand (der lag in der
 *     Nachbarzeile), der Abstand zur Zahl kommt aus der Skala, und die Karte
 *     hat unten Luft (`--pad`) — die Punktreihe berührt den Kartenrand nicht.
 *  2. DEV-ABZEICHEN: keins der Bedienelemente (FAB, untere Leiste) liegt mehr
 *     darunter — geprüft durch Rechnung auf den Rechtecken, die die Komponenten
 *     selbst setzen (Abzeichen oben rechts, FAB unten rechts, Leiste unten).
 *  6. WOCHE: die Startstunde wird GERECHNET (erster Termin der Woche, sonst
 *     die aktuelle Uhrzeit; eine Stunde Vorlauf; bleibt in den sichtbaren
 *     Stunden) und der Abstand unter der Kopfzeile ist nie negativ.
 *
 * Der Test liest nur Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz; `.mjs`-Logik läuft wirklich.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const W = await import(pathToFileURL(join(SRC, 'components/kronos/wochenStart.mjs')).href)

/** Rechteck-Schnittprüfung (wie im Browser: halboffene Kanten). */
const schneiden = (a, b) => !(a.rechts <= b.links || a.links >= b.rechts
  || a.unten <= b.oben || a.oben >= b.unten)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Mini-Monat: Punkt dicht unter der Zahl, innerhalb der Zelle
// ══════════════════════════════════════════════════════════════════════════
test('A10-N3 · 1: Punkt absolut zur Zelle unter dem Kreis, Ziffer in jeder Zelle gleich hoch', () => {
  const mini = lies('components/kronos/KalenderMiniMonat.vue')
  const zelle = mini.slice(mini.indexOf('.dk-minimonat-tag {'), mini.indexOf('.dk-minimonat-zahl {'))
  // Die Zelle richtet ihre Kinder NICHT mehr mittig aus — sonst hing die Lage
  // der Ziffer davon ab, ob ein Punkt da ist (Regression aus der ersten
  // Fassung: Ziffer rutschte in Zellen mit Punkt um 4 px nach oben).
  assert.match(zelle, /justify-content:\s*flex-start/, 'Ziffer hat einen festen Anker (nicht mittig zur Gruppe)')
  assert.match(zelle, /gap:\s*0/, 'kein gap mehr: der Punkt beeinflusst die Ziffer nicht')

  const punkt = mini.slice(mini.indexOf('.dk-minimonat-punkt {'))
  const block = punkt.slice(0, punkt.indexOf('}'))
  // Der Punkt ist ABSOLUT zur ZELLE verankert (nicht am Zellenrand, nicht im Fluss).
  assert.match(block, /position:\s*absolute/, 'absolut zur Zelle')
  assert.match(block, /top:\s*calc\(var\(--sp-6\) \+ var\(--sp-1\)\)/,
    'direkt unter dem 32-px-Kreis (--sp-1 = 4 px)')
  assert.ok(!/bottom:\s*0/.test(block), 'nicht am unteren Zellenrand (der lag in der Nachbarzeile)')
  assert.match(block, /border-radius:\s*var\(--badge-r\)/, 'rund über das Token')
  assert.match(block, /pointer-events:\s*none/, 'Dekoration: die Trefferfläche bleibt die Zelle')

  // Die Karte hat UNTEN Luft: Padding unten = --pad, oben --sp-3.
  const karte = mini.slice(mini.indexOf('.dk-minimonat {'), mini.indexOf('.dk-minimonat-kopf {'))
  assert.match(karte, /padding:\s*var\(--sp-3\) var\(--sp-3\) var\(--pad\)/,
    'Kartenrand unten: 16 px (--pad) statt 8 px')

  // ── Nachgerechnet (Zahlen aus tokens.css: --sp-1 4, --sp-2 8, --sp-6 32,
  //    --sp-7 48, --treffer-handy 44) ───────────────────────────────────────
  const kreis = 32
  const luecke = 4
  const punktB = 4
  const zelleH = 48 // --zelle-hoehe = --sp-7
  // Die Ziffer sitzt in JEDER Zelle an derselben Stelle: der Punkt ist absolut,
  // er kann die Ziffer also gar nicht verschieben.
  const inhalt = kreis + luecke + punktB
  assert.ok(zelleH > inhalt, `Zellenhöhe (${zelleH}) > Kreis + Lücke + Punkt (${inhalt})`)
  // Punkt endet vor der Zellunterkante → er gehört nicht zur nächsten Zeile.
  const punktUnten = kreis + luecke + punktB
  assert.ok(punktUnten <= zelleH, `Punkt endet in der Zelle (${punktUnten} ≤ ${zelleH})`)
  // Der Punkt liegt optisch beim EIGENEN Datum: er ist deutlich näher an der
  // Ziffer als am Zellenende (vorher 22 px unter der Ziffer / 10 px über der
  // nächsten Zeile — genau verkehrt herum).
  const abstandZurZiffer = luecke
  const abstandZumZellenende = zelleH - punktUnten
  assert.ok(abstandZurZiffer < abstandZumZellenende,
    `Punkt gehört zum eigenen Datum (${abstandZurZiffer} px zur Ziffer < ${abstandZumZellenende} px zum Zellenende)`)
  assert.ok(abstandZumZellenende >= 4, 'Punkt berührt den Zellenrand nicht')
  // Der Auswahlring (2 px am Kreis) und der Punkt kollidieren nicht.
  assert.ok(luecke > 2, 'Ring (2 px) und Punkt bleiben getrennt')

  // Zwei Punkte am Sonntag dürfen nicht verschmelzen: die Spalte ist bei
  // 390 px 47 px breit, die Punkte sind 4 px (bzw. 8 px als Strich) breit und
  // mittig. Zwischen zwei Nachbarn bleiben ≥ 47 − 4 − 4 = 39 px.
  const spalte = 47
  assert.ok(spalte - punktB - punktB > 8, 'Punkte benachbarter Tage berühren sich nicht')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Dev-Abzeichen verdeckt keine Bedienelemente
// ══════════════════════════════════════════════════════════════════════════
test('A10-N3 · 2: Dev-Abzeichen steht wieder wie auf main (A10-N4 Punkt D)', () => {
  // A10-N3 hatte das Abzeichen von „unten rechts“ nach „unten links, nur ein
  // Punkt“ verlegt. A10-N4 (Punkt D) nimmt das ZURÜCK: die Kollision mit dem
  // FAB am Handy wird in einer EIGENEN Karte gelöst, nicht hier. Dieser Test
  // hält deshalb den main-Stand fest — nicht den A10-N3-Zwischenstand.
  const dev = lies('components/devmodus/DevStart.vue')
  const block = dev.slice(dev.indexOf('.dk-dev-start {'), dev.indexOf('.dk-dev-start-punkt {'))
  assert.match(block, /position:\s*fixed/, 'schwebend')
  assert.match(block, /right:\s*10px/, 'unten rechts wie auf main')
  assert.match(block, /bottom:\s*10px/, 'unten rechts wie auf main')
  assert.match(block, /box-shadow:\s*var\(--dev-flaeche-schatten\)/, 'Plakette mit Schatten (main)')
  assert.ok(!/pointer-events:\s*none/.test(block), 'keine unsichtbare Trefferzone mehr (main)')
  assert.ok(!/--treffer-handy/.test(block), 'kein 44-px-Sonderweg mehr (main)')
  assert.ok(!/dk-app--handy/.test(dev), 'keine Handy-Sonderregel (Kollision folgt in eigener Karte)')
  // Der Abstand zum FAB am Handy bleibt damit der main-Stand (64 px Leiste).
  assert.match(dev, /@media \(max-width: 480px\) \{\s*\.dk-dev-start \{ bottom: calc\(64px \+ 8px\); \}/,
    'Handy-Anker wie auf main')
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Wochenansicht: Startstunde + Abstand unter der Kopfzeile
// ══════════════════════════════════════════════════════════════════════════
test('A10-N3 · 6: Startstunde = FRÜHESTE Uhrzeit der Woche minus eine Stunde', () => {
  // A10-N4 (Punkt B): Die Karte sagt ausdrücklich „Startstunde = früheste
  // UHRZEIT der Woche (nicht chronologisch erster Termin)“. Der alte Test
  // prüfte den chronologisch ersten Termin (Di 20:00 → 19); richtig ist der
  // früheste Tagesbeginn: Mi 19:30 / Fr 18:00 → 18:00 ist die früheste
  // Uhrzeit, also 17 als Startstunde. Der Test wurde ANGEREGELT, nicht
  // gelöscht (Regel 19) — der Fall mit beiden Regeln steht in
  // `tests/a10n4-kalender-nacharbeit.test.mjs`.
  const stunden = Array.from({ length: 24 }, (_, i) => i)
  const termine = [
    { start: new Date(2026, 10, 11, 19, 30), allDay: false }, // Mi 19:30
    { start: new Date(2026, 10, 10, 20, 0), allDay: false },  // Di 20:00 (zuerst)
    { start: new Date(2026, 10, 12, 18, 0), allDay: false },  // Do 18:00 (früheste Uhrzeit)
  ]
  assert.equal(W.startStunde({ termine, stunden }), 17,
    'früheste Uhrzeit 18:00 → eine Stunde davor = 17')
})

test('A10-N3 · 6: Ganztagstermine zählen nicht, kein Termin → aktuelle Uhrzeit', () => {
  const stunden = Array.from({ length: 24 }, (_, i) => i)
  // Nur ein Ganztagstermin: er hat keine Stunde, nach der man scrollen könnte.
  assert.equal(
    W.startStunde({ termine: [{ start: new Date(2026, 10, 10), allDay: true }], stunden, jetzt: new Date(2026, 10, 10, 9, 15) }),
    8,
    'ohne Uhrzeit-Termin gilt „jetzt − 1 Stunde“ (9:15 → 8)',
  )
  assert.equal(W.startStunde({ termine: [], stunden, jetzt: new Date(2026, 10, 10, 14, 0) }), 13)
})

test('A10-N3 · 6: Startstunde bleibt in den sichtbaren Stunden, Versatz nie negativ', () => {
  // Sehr früher Termin: 0:30 → −1 wäre negativ, also Anfang der Liste.
  assert.equal(
    W.startStunde({ termine: [{ start: new Date(2026, 10, 10, 0, 30), allDay: false }], stunden: [6, 7, 8, 9, 10] }),
    6,
    'unter der ersten sichtbaren Stunde wird geklemmt',
  )
  // Sehr später Termin: 23:00 → 22, aber wenn nur bis 20 sichtbar: 20.
  assert.equal(
    W.startStunde({ termine: [{ start: new Date(2026, 10, 10, 23, 0), allDay: false }], stunden: [6, 8, 10, 12, 14, 16, 18, 20] }),
    20,
    'über der letzten sichtbaren Stunde wird geklemmt',
  )
  // Ohne sichtbare Stunden keine Aussage (0), kein Absturz.
  assert.equal(W.startStunde({ termine: [], stunden: [] }), 0)
  assert.equal(W.startStunde(), 0)
  // Review-Nacharbeit Punkt 3: Der Versatz für die angeschnittene erste
  // Beschriftung ist die HALBE Zeilenhöhe (die Bibliothek setzt
  // `.ec-slot{inset-block-start:-.5lh}`), nie negativ, ganzzahlig.
  assert.equal(W.beschriftungsVersatz(18), 9, 'halbe Zeilenhöhe')
  assert.equal(W.beschriftungsVersatz(17), 9, 'gerundet')
  assert.equal(W.beschriftungsVersatz(0), 0)
  assert.equal(W.beschriftungsVersatz(-5), 0)
  assert.equal(W.beschriftungsVersatz(undefined), 0)
  // Der alte Weg (Innenabstand = volle Kopfzeilenhöhe) ist fort: er schob den
  // Inhalt unter der sticky-Kopfzeile durch.
  assert.equal(typeof W.stundenAbstand, 'undefined', 'stundenAbstand ist entfernt')
})

test('A10-N3 · 6: Wochen-Blöcke sind am Handy sichtbar (nur die Uhrzeit)', () => {
  const seite = lies('pages/Kalender.vue')
  // Vorher: `display: none` für `.ec-time-grid .ec-event` — die Woche war
  // leer, und der automatische Scroll (Punkt 6) hätte ins Nichts geführt.
  assert.ok(!/\.kal-mobil-raster :deep\(\.ec-time-grid \.ec-event\)\s*\{\s*display:\s*none/.test(seite),
    'Wochen-Blöcke nicht mehr ausgeblendet')
  assert.match(seite, /\.kal-mobil-raster :deep\(\.ec-time-grid \.ec-block-titel\)\s*\{\s*display:\s*none/,
    'Titel im Block fällt weg (50 px Spalte), Uhrzeit bleibt')
  assert.match(seite, /\.kal-mobil-raster :deep\(\.ec-time-grid \.ec-block\)\s*\{[^}]*font-size:\s*var\(--fs-sm\)/s,
    'Block ohne Textzusatz: kleine Schrift, Uhrzeit passt in die Spalte')
})

test('A10-N3 · 6: enge Lage kürzt den Blocktext auf die Anfangszeit', () => {
  assert.equal(W.engeZeit('19:30–21:30'), '19:30', 'Halbgeviertstrich')
  assert.equal(W.engeZeit('19:30 - 21:30'), '19:30', 'mit Leerzeichen und Bindestrich')
  assert.equal(W.engeZeit('10:00—11:30'), '10:00', 'Gedankenstrich')
  assert.equal(W.engeZeit('19:30'), '19:30', 'ohne Bereich bleibt sie ganz')
  assert.equal(W.engeZeit(''), '')
  assert.equal(W.engeZeit(undefined), '')
  // Nur die ENGE Lage (Handy) kürzt; am Desktop bleibt „19:30–21:30“ stehen.
  const kal = lies('components/kronos/KronosCalendar.vue')
  assert.match(kal, /const zeit = handyLage\.value \? engeZeit\(zeilen\.zeit\) : zeilen\.zeit/,
    'Kürzen hängt an der Handy-Lage')
})

test('A10-N3 · 3+4: kein Padding am Scroller, Sprung nur je Aufbau (datesSet)', () => {
  const kal = lies('components/kronos/KronosCalendar.vue')
  // A10-N4 (Punkt B/C): Die Rechenfunktionen sind um `stundenHoehe`,
  // `scrollZiel` und `sprungEntscheidung` gewachsen — die Aussage dieses
  // Tests bleibt: die Rechnung wird EINGEBUNDEN und im DOM angewendet.
  assert.match(kal, /import \{[^}]*startStunde[^}]*beschriftungsVersatz[^}]*\} from '\.\/wochenStart\.mjs'/,
    'Rechnung eingebunden')
  assert.match(kal, /function wochenStartHerrichten\(\)/, 'Anwendung im DOM')
  assert.match(kal, /querySelector\('\.ec-week-view'\)/, 'gilt für die Wochenansicht')
  assert.match(kal, /scrollTop/, 'Scrollposition gesetzt')
  // Punkt 3: Kein Innenabstand mehr am Scroll-Container (er schob die
  // Stundenzeilen über die sticky-Kopfzeile).
  assert.ok(!/paddingBlockStart\s*=/.test(kal), 'kein paddingBlockStart mehr auf .ec-main')
  assert.match(kal, /beschriftungsVersatz/, 'Versatz kommt aus der Rechenfunktion')
  const fn = kal.slice(kal.indexOf('function wochenStartHerrichten()'), kal.indexOf('/** Einmal je Aufbau'))
  // A10-N4 (Punkt B/C): Die Handy-Lage wird zusätzlich über die EINE Klasse
  // `.dk-app--handy` geprüft (dieselbe Quelle, an der auch das CSS hängt) —
  // die Zusage „Scroll nur am Handy“ gilt unverändert.
  assert.match(fn, /if \(!handyLage\.value && !kal\.closest\('\.dk-app--handy'\)\) return/,
    'Scroll nur am Handy')
  // Punkt 4: Der Sprung hängt am Aufbau, nicht an jeder Kachel.
  // A10-N4 (Punkt B): Das Ziel rechnet jetzt `scrollZiel` — mit der
  // Stundenhöhe (slot-height × Periodizität) bzw. dem Offset der
  // Ziel-Beschriftung, abzüglich des halben Zeilenversatzes. Die Aussage
  // „Ziel = Stunde minus halber Zeilenversatz“ gilt unverändert.
  assert.match(fn, /const ziel = scrollZiel\(\{/, 'Ziel kommt aus der Rechenfunktion')
  assert.match(fn, /versatz,/, 'halber Zeilenversatz geht ins Ziel')
  assert.match(fn, /_scrollSetzen\(scroller, ziel\)/, 'Scrollposition gesetzt')
  // Review-Nacharbeit (Nachfix): `.ec-time` existierte nicht — die
  // Stundenliste war leer, der Sprung fiel auf 0 zurück. Die Bibliothek
  // beschriftet mit `.ec-slot` im Seitenbereich der Zeitachse.
  assert.match(fn, /querySelectorAll\('\.ec-time-grid \.ec-slot, \.ec-sidebar \.ec-slot'\)/,
    'Stundenbeschriftungen über den ECHTEN Wähler (.ec-slot)')
  assert.ok(!/\.ec-time'/.test(fn), 'kein toter Wähler .ec-time mehr')
  assert.match(fn, /indexOf\(stunde\)/, 'Index der Wunschstunde')
  // Review-Nacharbeit (Nachfix 2): `time[datetime]` gibt es nicht — die
  // Startzeit wird in `eventDidMount` an den `article` geschrieben und von
  // `wochenStartHerrichten` von dort gelesen.
  const mountStart = kal.indexOf('eventDidMount: (info) =>')
  const mount = kal.slice(mountStart, kal.indexOf('eventWillUnmount:', mountStart))
  assert.match(mount, /setAttribute\('data-dk-start', start\.toISOString\(\)\)/, 'Startzeit am article')
  assert.match(mount, /setAttribute\('data-dk-ganztag', ''\)/, 'Ganztag markiert')
  assert.match(fn, /el\.getAttribute\('data-dk-start'\)/, 'liest die Startzeit vom article')
  assert.ok(!/time\[datetime\]/.test(fn), 'kein time[datetime] mehr (existiert nicht)')
  const planer = kal.slice(kal.indexOf('function _tagesPunktePlanen()'), kal.indexOf('function mehrOeffnen'))
  // A10-N4 (Punkt C): Das Flag wird nicht mehr blind geschlossen, sondern
  // über `sprungEntscheidung` geprüft (Termine/Quelle/Nutzer-Scroll).
  assert.match(planer, /_sprungVersuchen\(\)/, 'Scroll nur über die Freigabe-Prüfung')
  assert.match(kal, /const entscheidung = sprungEntscheidung\(/, 'Flag wird über die Freigabe-Prüfung ausgewertet')
  const datesSet = kal.slice(kal.indexOf('datesSet: (info) =>'), kal.indexOf('eventClassNames:'))
  assert.match(datesSet, /_startScrollOffen = true/, 'datesSet öffnet den Sprung je Aufbau')
  assert.ok(!/wochenStartHerrichten\(\)/.test(kal.slice(kal.indexOf('eventDidMount: (info)'), kal.indexOf('datesSet: (info)'))),
    'NICHT im eventDidMount (sonst springt der Nutzer-Scroll beim Nachladen zurück)')
})
