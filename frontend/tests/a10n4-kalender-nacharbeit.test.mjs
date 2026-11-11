/**
 * A10-N4 — Review-Nacharbeit zum Handy-Kalender (Karte t_89694811).
 *
 * Die Karte verlangt fünf Dinge; jedes wird hier GEPRÜFT, nicht behauptet:
 *
 *  A. MINI-MONAT (hell): Der Punkt unter dem GEWÄHLTEN Tag ist sichtbar. Er
 *     lag unter dem Kreis (top = 32 + 4), die Sonderregel „gewählt → Weiß“
 *     färbte ihn deshalb weiß auf weiß. Die Sonderfarben (Weiß und Prüf-Gold)
 *     sind gestrichen — der Punkt behält seine normale Farbe.
 *  B. WOCHEN-SPRUNG: Höhe einer Stunde = `--ec-slot-height` ×
 *     `--ec-slot-label-periodicity` (Slot 30 min, Beschriftung alle 2 Slots);
 *     Vorrang hat der Offset der Ziel-Beschriftung. Startstunde ist die
 *     FRÜHESTE UHRZEIT der Woche (nicht der chronologisch erste Termin).
 *  C. datesSet-Race: Das Sprung-Flag schließt erst bei Terminen, fertig
 *     geladener Quelle oder Nutzer-Scroll — nicht nach dem ersten Frame.
 *  D. DEV-ABZEICHEN: komplett auf main-Stand (unten rechts); die Kollision am
 *     Handy folgt in einer EIGENEN Karte.
 *  E. DECKENDE TOKENS: `--heute-flaeche` und `--heute-zelle` sind in hell UND
 *     dunkel deckend (kein rgba, kein transparent, kein Alpha).
 *
 * Der Test liest nur Dateien innerhalb von frontend/ (Regel 13), braucht kein
 * Netz und rechnet `.mjs`-Logik wirklich (A, B, C).
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

// ══════════════════════════════════════════════════════════════════════════
// A · Mini-Monat: Punkt am gewählten Tag sichtbar
// ══════════════════════════════════════════════════════════════════════════
test('A10-N4 · A: Punkt am gewählten Tag behält seine normale Farbe (kein Weiß auf Weiß)', () => {
  // Nur die CSS-Regeln zählen — der erklärende Kommentar nennt die gestrichenen
  // Werte absichtlich (damit niemand sie „zurückbringt“).
  const mini = lies('components/kronos/KalenderMiniMonat.vue')
  const miniCss = mini
    .replace(/\/\*[\s\S]*?\*\//g, '')  // Kommentare raus: hier steht nur CSS
  // KEINE Sonderregel mehr, die den Punkt am gewählten Tag umfärbt.
  assert.ok(!/\.is-gewaehlt\s+\.dk-minimonat-punkt(\s|,|\{|\.)/.test(miniCss),
    'keine Sonderfarbe für den Punkt am gewählten Tag')
  assert.ok(!/--dk-gold-300/.test(miniCss),
    'das Prüf-Gold für den gewählten Tag ist gestrichen (Punkt bleibt --warn)')
  // Seine normale Farbe bleibt: Kalenderfarbe, bei „Zu prüfen“ die Warnfarbe.
  const punkt = miniCss.slice(miniCss.indexOf('.dk-minimonat-punkt {'))
  assert.match(punkt.slice(0, punkt.indexOf('}')), /background:\s*var\(--tag-flaeche, var\(--primary\)\)/,
    'Punkt trägt die Kalenderfarbe')
  assert.match(miniCss, /\.dk-minimonat-punkt\.ist-pruef\s*\{\s*background:\s*var\(--warn\)/,
    'Prüf-Punkt trägt die Warnfarbe — auch am gewählten Tag')

  // ── Nachgerechnet: warum die gestrichene Regel unsichtbar machte ────────
  // Der Punkt ist absolut zur Zelle verankert (top = Kreis 32 + 4 = 36 px).
  // Er liegt damit UNTER dem 32-px-Kreis, nicht darauf — die weiße Schrift-
  // fläche des gewählten Tages kann ihn gar nicht abdecken.
  const kreis = 32, luecke = 4
  const punktOben = kreis + luecke
  assert.ok(punktOben >= kreis, 'Punkt beginnt unterhalb des Kreises (kein Überdecken)')
  const miniStyle = miniCss.slice(miniCss.indexOf('.dk-minimonat-tag.is-gewaehlt .dk-minimonat-zahl'))
  assert.match(miniStyle.slice(0, miniStyle.indexOf('}')), /background:\s*var\(--marke-flaeche\)/,
    'gewählter Tag: Fläche nur am KREIS (Zahl), nicht an der Zelle')
  // Weiß (--marke-ink) auf der weißen Karte wäre unsichtbar: der alte Wert.
  const weiss = '#ffffff', karteHell = '#ffffff'
  assert.equal(kontrast(weiss, karteHell), 1, 'Beleg: Weiß auf Weiß = 1:1 (unsichtbar)')
  // Die Kalenderfarbe (--primary hell = Navy) ist auf Weiß klar sichtbar.
  assert.ok(kontrast('#1c2850', karteHell) >= 3, 'Beleg: Navy-Punkt auf Weiß ≥ 3:1')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Wochen-Sprung: Stundenhöhe und Ziel-Beschriftung
// ══════════════════════════════════════════════════════════════════════════
test('A10-N4 · B: eine Stunde = slot-height × Beschriftungs-Periodizität', () => {
  // Bibliothek: slotDuration 30 min, slotHeight 24 → Stunde 48 px (nicht 24).
  assert.equal(W.stundenHoehe(24, 2), 48, '24 px × 2 = 48 px je Stunde')
  // Ohne Periodizität gilt 1 (Slot = Stunde) — nie stillschweigend ×2.
  assert.equal(W.stundenHoehe(48, undefined), 48, 'ohne Angabe bleibt der Slot die Stunde')
  assert.equal(W.stundenHoehe(48, '0'), 48, 'ungültige Periodizität (0) fällt auf 1 zurück')
  assert.equal(W.stundenHoehe('36px', '2'), 72, 'px-Suffix wird gelesen')
  assert.equal(W.stundenHoehe('', 2), 0, 'ohne Messwert keine Höhe (nichts raten)')
  assert.equal(W.stundenHoehe(0, 2), 0)
  assert.equal(W.stundenHoehe(-24, 2), 0)
  // Der alte Weg (Slot-Höhe als Stunden-Höhe) landet genau auf dem Befund:
  // Ziel 8:00, Raster 6:00 → 2 Slots-Stunden × 24 = 48 px statt 96 px →
  // der Blick stand bei 7:00 … und mit halbem Versatz bei „~7:15“.
  const alt = 2 * 24            // index * slot-height (der Fehler)
  const neu = W.stundenHoehe(24, 2) * 2
  assert.equal(alt, 48, 'Beleg: alte Rechnung 48 px')
  assert.equal(neu, 96, 'neue Rechnung 96 px (2 Stunden à 48)')
  assert.notEqual(alt, neu, 'die alte Rechnung war um Faktor 2 zu klein')
})

test('A10-N4 · B: Scroll-Ziel nimmt den Offset der Ziel-Beschriftung (Vorrang)', () => {
  // Gemessene Werte aus dem Wegwerf-Stack (390×844): `.ec-slot` „9:00“ hat
  // `offsetTop` 422 (8 × 48 px Stunden + halbe Beschriftungszeile), halbe
  // Zeilenhöhe 9 → scrollTop 413. Die Beschriftung steht dann oben.
  assert.equal(W.scrollZiel({ offsetTop: 422, index: 8, stundenHoehe: 48, versatz: 9 }), 413,
    'Offset − halber Zeilenversatz')
  // Ohne Offset wird gerechnet — und zwar mit der richtigen Stundenhöhe.
  assert.equal(W.scrollZiel({ offsetTop: null, index: 2, stundenHoehe: 48, versatz: 9 }), 87)
  assert.equal(W.scrollZiel({ offsetTop: null, index: 2, stundenHoehe: 24, versatz: 9 }), 39,
    'der alte (falsche) Weg: 2 × 24 = 48 − 9 = 39 → Blick bei ~6:45 statt 8:00')
  assert.equal(W.scrollZiel({ offsetTop: null, index: 2, stundenHoehe: 24, versatz: 0 }), 48,
    'ohne Versatz wäre es die 48-px-Rechnung — genau der Befund')
  // Nie negativ, ganzzahlig, robust gegen Unsinn.
  assert.equal(W.scrollZiel({ offsetTop: 0, index: 0, stundenHoehe: 0, versatz: 9 }), 0)
  assert.equal(W.scrollZiel({ offsetTop: null, index: 0, stundenHoehe: 48, versatz: 9 }), 0)
  assert.equal(W.scrollZiel({ offsetTop: -50, index: 2, stundenHoehe: 48, versatz: 0 }), 96,
    'negativer Offset ist kein Messwert → Rechnung')
  assert.equal(W.scrollZiel({}), 0)
})

test('A10-N4 · B: Startstunde = FRÜHESTE Uhrzeit der Woche (nicht erster Termin)', () => {
  const stunden = Array.from({ length: 24 }, (_, i) => i)
  // Mittwoch 09:00 ist chronologisch der ERSTE Termin, aber Sonntag 08:00 ist
  // die FRÜHESTE Uhrzeit → Ziel 8:00, also 7 als Startstunde.
  const woche = [
    { start: new Date(2026, 10, 11, 9, 0), allDay: false },   // Mi 09:00 (zuerst)
    { start: new Date(2026, 10, 15, 8, 0), allDay: false },   // So 08:00 (früheste Uhrzeit)
    { start: new Date(2026, 10, 12, 19, 30), allDay: false }, // Do 19:30
  ]
  assert.equal(W.startStunde({ termine: woche, stunden }), 7,
    'früheste Uhrzeit 8:00 → eine Stunde Vorlauf = 7 (vorher: 8)')
  // Gegenprobe: der chronologisch erste Termin am Abend darf NICHT gewinnen.
  const spatZuerst = [
    { start: new Date(2026, 10, 10, 19, 0), allDay: false },  // Di 19:00 (zuerst)
    { start: new Date(2026, 10, 12, 10, 0), allDay: false },  // Do 10:00 (frühest)
  ]
  assert.equal(W.startStunde({ termine: spatZuerst, stunden }), 9,
    'früheste Uhrzeit 10:00 → 9 (nicht 18)')
})

// ══════════════════════════════════════════════════════════════════════════
// C · datesSet-Race: das Flag wartet auf Termine bzw. die Quelle
// ══════════════════════════════════════════════════════════════════════════
test('A10-N4 · C: Sprung wartet auf Termine oder fertig geladene Quelle', () => {
  // Erster Frame, Quelle noch unterwegs: NICHT springen, NICHT schließen —
  // sonst bliebe die Woche bei „jetzt − 1 h“ hängen (Befund).
  assert.equal(W.sprungEntscheidung({ offen: true, termine: false, geladen: false, nutzerScroll: false }),
    'warten', 'kein Termin, Quelle lädt → warten')
  // Termine stehen im Raster → Ziel ist belastbar.
  assert.equal(W.sprungEntscheidung({ offen: true, termine: true, geladen: false, nutzerScroll: false }),
    'springen', 'Termine da → springen')
  // Quelle fertig, aber 0 Termine → „jetzt − 1 h“ gilt zu Recht.
  assert.equal(W.sprungEntscheidung({ offen: true, termine: false, geladen: true, nutzerScroll: false }),
    'springen', 'Quelle fertig (0 Termine) → jetzt − 1 h')
  // Nutzer-Scroll gewinnt immer.
  assert.equal(W.sprungEntscheidung({ offen: true, termine: true, geladen: true, nutzerScroll: true }),
    'schliessen', 'Nutzer-Scroll → kein Sprung mehr')
  assert.equal(W.sprungEntscheidung({ offen: true, termine: false, geladen: false, nutzerScroll: true }),
    'schliessen', 'Nutzer-Scroll auch ohne Termine')
  // Flag zu → nichts mehr tun.
  assert.equal(W.sprungEntscheidung({ offen: false, termine: true, geladen: true }), 'schliessen')
  assert.equal(W.sprungEntscheidung(), 'schliessen')

  // Die Gegenprobe zum alten Verhalten: der Kalender muss die Entscheidung
  // BENUTZEN — nicht mehr „springen und sofort schließen“.
  const kal = lies('components/kronos/KronosCalendar.vue')
  assert.match(kal, /const entscheidung = sprungEntscheidung\(/, 'KronosCalendar fragt die Entscheidung')
  assert.match(kal, /if \(entscheidung === 'warten'/, 'bei „warten“ wird nachgelaufen')
  assert.ok(!/_startScrollOffen\) \{\s*wochenStartHerrichten\(\)\s*_startScrollOffen = false/.
    test(kal.replace(/\n/g, ' ').replace(/\s+/g, ' ')),
  'das alte „springen und blind schließen“ ist fort')
  // Die Quelle meldet ihr Ende an genau dieser Stelle.
  assert.match(kal, /const aufbau = _aufbauNr/, 'Antwort wird dem Aufbau zugeordnet (alte Antwort zählt nicht)')
  assert.match(kal, /_quelleGeladen = true\s*\n\s*_sprungVersuchen\(\)/, 'Quellen-Ende startet den Sprung neu')
  // Nutzer-Scroll im Raster schließt den Sprung.
  // Review A10-N4: erkannt wird die EINGABE, nicht das scroll-Ereignis — das
  // feuert auch beim Bibliotheks-Scroll (scrollTime) und hätte den wartenden
  // Sprung als „Nutzer-Scroll“ geschlossen.
  assert.match(kal, /\['wheel', 'touchmove', 'keydown', 'pointerdown'\]/,
    'Nutzer-Eingabe am .ec-main zählt als Nutzer-Scroll')
  assert.match(kal, /closest\?\.\('\.ec-main'\)/, 'nur Eingaben im Scroller der Bibliothek')
  assert.ok(!/addEventListener\('scroll'/.test(kal), 'kein scroll-Ereignis als Nutzer-Signal')
  // Nachziehen respektiert den Nutzer.
  assert.match(kal, /if \(!_nutzerScroll\) scroller\.scrollTop = ziel/, 'kein Nachziehen nach Nutzer-Eingriff')
})

test('A10-N4 · C: Sprung-Flag bleibt offen, solange kein Wochenraster steht', () => {
  // BEFUND im Abnahmelauf (390×844): Beim Öffnen stand erst der MONAT; der
  // Sprung wurde abgearbeitet, fand kein `.ec-week-view` und schloss das Flag.
  // Beim Umschalten auf „Woche“ lief er dann nie — es blieb beim
  // Bibliotheks-Scroll (276 px), der Termin lag unter dem Rand.
  const kal = lies('components/kronos/KronosCalendar.vue')
  const fn = kal.slice(kal.indexOf('function _sprungVersuchen'),
                      kal.indexOf("function _nutzerScrollMerken"))
  assert.match(fn, /if \(!calendarEl\.value\?\.querySelector\('\.ec-week-view'\)\) return/,
    'ohne Wochenraster wird NICHTS geschlossen (Flag bleibt offen)')
  // und der Aufbauplaner stößt den Sprung selbst an (der Anstoß aus
  // `datesSet`/`eventDidMount` fehlt beim Umschalten Monat → Woche).
  const planer = kal.slice(kal.indexOf('function _tagesPunktePlanen'),
                          kal.indexOf('const SPRUNG_NACHLAUF_MS'))
  assert.match(planer, /_sprungVersuchen\(\)/, 'der Aufbauplaner stößt den Sprung an')
})

// ══════════════════════════════════════════════════════════════════════════
// D · Dev-Abzeichen wieder wie auf main
// ══════════════════════════════════════════════════════════════════════════
test('A10-N4 · D: Dev-Start komplett auf main-Stand (unten rechts, keine Handy-Regel)', () => {
  const dev = lies('components/devmodus/DevStart.vue')
  const block = dev.slice(dev.indexOf('.dk-dev-start {'), dev.indexOf('.dk-dev-start-punkt {'))
  assert.match(block, /position:\s*fixed/)
  assert.match(block, /right:\s*10px/, 'unten rechts (main)')
  assert.match(block, /bottom:\s*10px/, 'unten rechts (main)')
  assert.ok(!/--treffer-handy/.test(dev), 'keine 44-px-Trefferzone mehr (main)')
  assert.ok(!/pointer-events:\s*none/.test(block), 'kein Durchlassen mehr (main)')
  assert.ok(!/dk-app--handy/.test(dev), 'keine Handy-Sonderregel (eigene Karte)')
  assert.ok(!/dk-dev-start-text/.test(dev), 'kein getrennter Text-Knoten mehr (main)')
  assert.match(dev, /@media \(max-width: 480px\)/, 'Handy-Abstand wie main')
  // Der Punkt ist wieder der schlichte main-Punkt (8 px, rund, ohne Ringe).
  const punkt = dev.slice(dev.indexOf('.dk-dev-start-punkt {'))
  const punktBlock = punkt.slice(0, punkt.indexOf('}'))
  assert.match(punktBlock, /border-radius:\s*50%/, 'Punkt wie main')
  assert.ok(!/box-shadow/.test(punktBlock), 'kein eigener Ring (main)')
})

// ══════════════════════════════════════════════════════════════════════════
// E · Heute-Flächen in hell UND dunkel deckend
// ══════════════════════════════════════════════════════════════════════════
/**
 * Ist ein CSS-Farbwert DECKEND? Geprüft wird der Quelltext-Wert aus tokens.css:
 * kein `rgba(...)`/`rgb(... / …)`, kein `hsla`, kein `transparent`, kein
 * Prozent-Alpha in `color-mix`, und bei `color-mix` höchstens zwei deckende
 * Farben ohne Prozent-Angaben (Prozent = Mischungsanteil, kein Alpha — hier
 * steht die Prozentzahl auf der FORM, nicht als Deckkraft).
 */
function deckend(wert) {
  const w = String(wert || '').trim()
  if (!w) return false
  if (/transparent/i.test(w)) return false
  if (/\b(rgba|hsla)\s*\(/i.test(w)) return false
  if (/\b(rgb|hsl)\([^)]*\/[^)]*\)/i.test(w)) return false
  const mix = /^color-mix\(\s*in srgb\s*,(.*)\)$/i.exec(w)
  if (mix) {
    const farben = mix[1].split(',')
    if (farben.length !== 2) return false
    // Beide Anteile müssen deckende Tokens/Farben sein (var(...) oder #hex),
    // mit oder ohne Prozent-Anteil (Reihenfolge ist CSS-frei), kein Alpha.
    return farben.every((f) => /^\s*(\d+%\s*)?(var\(--[\w-]+\)|(?:#[0-9a-f]{3}|#[0-9a-f]{6}))(\s+\d+%)?\s*$/i.test(f))
  }
  // var(--accent-soft) & Co. werden AUFGELÖST geprüft (s. Test unten).
  return /^(var\(--[\w-]+\)|#[0-9a-f]{3}|#[0-9a-f]{6})$/i.test(w)
}

/** Wert eines Tokens im jeweiligen Block (hell = vor dem Dunkelblock). */
function tokenWert(tokens, name) {
  const re = new RegExp('--' + name + ':\\s*([^;]+);')
  const treffer = re.exec(tokens)
  return treffer ? treffer[1].trim() : ''
}

/**
 * Löst `var(--a)` so lange auf, bis eine echte Farbe (#hex) dasteht.
 * Die Primitiv-Tokens (--dk-gold-50 …) stehen im GESAMTEN Block; deshalb wird
 * im vollständigen Quelltext gesucht, nicht nur im Theme-Abschnitt.
 */
function aufloesen(ganz, wert, tiefe = 0) {
  if (tiefe > 10) return wert
  const treffer = /^var\((--[\w-]+)\)$/.exec(String(wert).trim())
  if (!treffer) return String(wert).trim()
  const naechster = tokenWert(ganz, treffer[1].slice(2))
  return naechster ? aufloesen(ganz, naechster, tiefe + 1) : String(wert).trim()
}

test('A10-N4 · E: --heute-flaeche und --heute-zelle deckend in hell und dunkel', () => {
  const tokens = lies('tokens.css')
  const dunkelStart = tokens.indexOf('[data-theme="dark"],')
  assert.ok(dunkelStart > 0, 'Dunkelblock gefunden')
  const hellTeil = tokens.slice(0, dunkelStart)
  // Achtung: der Dunkelblock enthält MEHRERE Blöcke; für die Tokens zählt der
  // erste (semantische Tokens).
  const dunkelTeil = tokens.slice(dunkelStart)

  for (const name of ['heute-flaeche', 'heute-zelle']) {
    const hellWert = tokenWert(hellTeil, name)
    const dunkelWert = tokenWert(dunkelTeil, name)
    assert.ok(hellWert, `${name}: heller Wert vorhanden`)
    assert.ok(dunkelWert, `${name}: dunkler Wert vorhanden`)
    // HELL: --accent-soft → --dk-gold-50 → #hex. Erst AUFLÖSEN, dann prüfen:
    // eine var()-Kette ist kein Alpha, sondern nur ein Verweis.
    const hellFarbe = aufloesen(tokens, hellWert)
    assert.ok(deckend(hellFarbe), `hell: ${name} ist deckend (${hellWert} → ${hellFarbe})`)
    assert.match(hellFarbe, /^#[0-9a-f]{3,8}$/i,
      `hell: ${name} endet auf eine echte Farbe (${hellFarbe})`)
    // DUNKEL: color-mix aus zwei deckenden Farben (kein Alpha). Vorher stand
    // dort rgba(201,149,47,.16) — halbtransparent, und die Bibliothek zeichnete
    // daraus das graue Streifenmuster.
    assert.ok(deckend(dunkelWert), `dunkel: ${name} ist deckend (${dunkelWert})`)
    for (const verboten of [/rgba?\s*\(/i, /transparent/i, /hsla?\s*\(/i, /\/\s*\d*\.?\d+\s*\)/]) {
      assert.ok(!verboten.test(dunkelWert), `dunkel: ${name} ohne ${verboten}`)
    }
    // Die beiden Farben IM color-mix müssen selbst deckend aufgelöst werden.
    const mix = /^color-mix\(\s*in srgb\s*,(.*)\)$/i.exec(dunkelWert)
    if (mix) {
      for (const teil of mix[1].split(',')) {
        const farbe = aufloesen(dunkelTeil + '\n' + tokens, teil.replace(/^\s*\d+%\s*/, '').replace(/\s+\d+%\s*$/, '').trim())
        assert.ok(deckend(farbe), `dunkel: Mischfarbe ${farbe} ist deckend`)
      }
    }
  }
  // Der alte (transparente) Wert ist nachweislich NICHT deckend — der Grund
  // für diese Prüfung (Regel 19: Test ersetzt „kein repeating-“, s. Karte).
  assert.equal(deckend('rgba(201,149,47,.16)'), false, 'Beleg: der alte Wert war halbtransparent')
  // Und die Bibliothek/Seite nimmt genau diese Tokens als Fläche.
  const kronos = readFileSync(join(SRC, 'kronos.css'), 'utf8')
  assert.match(kronos, /--ec-today-bg-color:\s*var\(--heute-flaeche\)/,
    'Tagesspalte (Woche/Tag) nutzt --heute-flaeche')
  const seite = lies('pages/Kalender.vue')
  assert.match(seite, /var\(--heute-zelle\)/,
    'Monatszelle nutzt --heute-zelle')
})

/** Relative Luminanz nach WCAG 2.1. */
function lum(hex) {
  const h = String(hex).replace('#', '')
  const teile = h.length === 3 ? h.split('').map((c) => c + c) : [h.slice(0, 2), h.slice(2, 4), h.slice(4, 6)]
  const [r, g, b] = teile.map((c) => {
    const v = parseInt(c, 16) / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function kontrast(a, b) {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}
