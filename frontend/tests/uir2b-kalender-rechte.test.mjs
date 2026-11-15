/**
 * UI-R2b — Folgekarte zu UI-R2: „Moderieren“, Sperren, Wettlauf, Tabelle, Namen.
 *
 * Die Karte ist ein Review-Befund (Opus) an der Oberfläche. Jeder Punkt ist
 * hier EINE Regel, die gegen die ECHTE Quelldatei läuft — die reine Logik
 * (`kalenderRechte.mjs`) direkt, die Bausteine über ihren Quelltext:
 *
 *   P1   Ohne `darf_moderieren_vergeben` fährt der bisherige Moderieren-Wert
 *        UNVERÄNDERT mit (Umschalten von „Schreiben“, „Entfernen“, Hinzufügen);
 *        Moderieren steht nur als ANZEIGE da.
 *   P2   „Moderieren“ gilt für Personen UND Gruppen (der Server prüft den
 *        Eintrag, nicht die Art).
 *   P3   EIN Schlüsselformat für laufende Aktionen — Baustein und Karte.
 *   P4   Wettlauf: nur die jüngste Antwort je Kalender schreibt.
 *   P5   Tabelle: Kopf und Zeilen haben dieselbe Spaltenzahl.
 *   P6   Keine Karte in der Karte, kein Titel doppelt.
 *   P7   Ja/Nein-Frage ist eine echte Radiogruppe (nie „nichts gewählt“).
 *   P8   Kein `canManage` als Moderationsrecht — allein der Server entscheidet.
 *   P9   Namen kommen vom Server (`name`), nie die Kontokennung.
 *   P11  Die Stufe „gruppe“ prüfen HV/MV der Gruppe, nicht die Gruppenleitung.
 *   P12  Die Erfolgsmeldung nennt das Ziel.
 *   P13  Der Hinweis „nur HV und MV“ steht nur ohne Vergaberecht.
 *   P14  `nurAnzeigen` sperrt ALLES, nicht nur das Hinzufügen-Feld.
 *   P15  Fehlerzustand heißt „Freigaben nicht geladen“; toter Kommentar weg.
 *   P16  403 aus `get_kalender_verwaltung` blendet die Karte aus.
 *
 * Lauf: node --test tests/uir2b-kalender-rechte.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  FREIGABE_STUFEN,
  anfrageZaehler,
  busySchluessel,
  freigabeAnfrage,
  freigabeFelder,
  freigabeKnoepfe,
  freigabeZeilen,
  freigabeZeilenLage,
  sichtbarkeitLage,
  sichtbarkeitMeldung,
} from '../src/diakonos/components/gruppen/kalenderRechte.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
/** Nur Skript-Kommentare (Template-Kommentare gehören zum geprüften Markup). */
const ohneKommentare = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

const RECHTE = lies('components/gruppen/KalenderRechte.vue')
/** Nur der `<script>`-Teil, ohne Kommentare (Markup-Kommentare sind Inhalt). */
const skriptVon = (text) => text.slice(text.indexOf('<script'), text.indexOf('</script>'))
  .replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
const KALENDERDATEI = lies('components/gruppen/KalenderEinstellungen.vue')
const KARTE = lies('components/gruppen/GruppenEinstellungen.vue')
const GRUPPENSEITE = lies('pages/GruppeDetail.vue')

/** Ausschnitt aus `freigaben_des_objekts` — SO, wie der Server ihn liefert. */
const OBJEKT = {
  typ: 'kalender', objekt: 'Kinderchor', gruppe: 'G-Chor', untergruppe: 'UG-K',
  standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
  darf_moderieren_vergeben: false,
  freigaben: [
    { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: true, moderieren: true },
    { benutzer: null, gruppe: 'G-Chor', name: 'Chor', lesen: true, schreiben: true, moderieren: true },
  ],
}

// ══════════════════════════════════════════════════════════════════════════
// P1 · Moderieren bleibt UNVERÄNDERT, wenn man es nicht vergeben darf
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P1: „Schreiben“ umschalten lässt den Moderieren-Wert unverändert', () => {
  const zeile = freigabeZeilen(OBJEKT.freigaben)[0]
  assert.equal(zeile.moderieren, true, 'Vorbedingung: die Zeile trägt Moderieren')

  // Genau der Befund: wer „Schreiben“ anfasst, schickte vorher moderieren=false
  // mit → der Server sah eine ENTZIEHUNG und antwortete 403.
  const felder = freigabeFelder(zeile, { lesen: true, schreiben: false, moderieren: false },
    { darf_moderieren_vergeben: false })
  assert.equal(felder.moderieren, true, 'Moderieren wurde still entzogen')
  assert.equal(felder.lesen, true)
  assert.equal(felder.schreiben, false)

  const entfernen = freigabeFelder(zeile, { lesen: false, schreiben: false, moderieren: false },
    { darf_moderieren_vergeben: false })
  assert.equal(entfernen.moderieren, true, '„Entfernen“ entzöge das Prüfrecht')
})

test('UI-R2b/P1: MIT Vergaberecht gilt die gewünschte Änderung', () => {
  const zeile = freigabeZeilen(OBJEKT.freigaben)[0]
  const entzogen = freigabeFelder(zeile, { lesen: true, schreiben: true, moderieren: false },
    { darf_moderieren_vergeben: true })
  assert.equal(entzogen.moderieren, false, 'Entziehen muss mit Recht möglich sein')

  const vergeben = freigabeFelder({ lesen: true, schreiben: true, moderieren: false },
    { lesen: true, schreiben: true, moderieren: true }, { darf_moderieren_vergeben: true })
  assert.equal(vergeben.moderieren, true)

  // „Moderieren“ ohne „Lesen“ gibt es nicht (wer prüft, sieht den Kalender).
  const ohneLesen = freigabeFelder({ lesen: true, moderieren: false },
    { lesen: false, schreiben: false, moderieren: true }, { darf_moderieren_vergeben: true })
  assert.equal(ohneLesen.moderieren, false)
})

test('UI-R2b/P1: die Anfrage trägt Moderieren auch ohne Vergaberecht (unverändert)', () => {
  const zeile = freigabeZeilen(OBJEKT.freigaben)[0]
  const felder = freigabeFelder(zeile, { lesen: true, schreiben: false }, { darf_moderieren_vergeben: false })
  const anfrage = freigabeAnfrage({ objekt: 'Kinderchor', art: zeile.art, kennung: zeile.kennung, ...felder })
  assert.equal(anfrage.moderieren, true, 'der Rumpf entzöge das Prüfrecht')
  assert.equal(anfrage.benutzer, 'anna.beispiel@example.org')
})

test('UI-R2b/P1: KalenderRechte.vue baut JEDE Freigabe-Anfrage über `senden`/`freigabeFelder`', () => {
  const skript = skriptVon(RECHTE)
  assert.match(skript, /\nfunction freigabeFelder\(|\bfreigabeFelder\(/, 'die eine Regel fehlt im Baustein')
  // JEDE Anfrage geht durch `senden` — dort entscheidet `freigabeFelder`, was
  // aus „Moderieren“ wird. Ein Weg, der direkt `emit('freigabe-setzen')` mit
  // eigenem Rumpf aufruft, umginge die Regel.
  const senden = skript.slice(skript.indexOf('function senden'), skript.indexOf('/** Ein Kästchen umschalten'))
  assert.match(senden, /freigabeFelder\(/, 'senden entscheidet den Moderieren-Wert nicht über freigabeFelder')
  assert.match(senden, /\.\.\.felder/, 'senden gibt die Felder nicht weiter')
  // Genau DREI Aufrufer, alle über `senden` (Kästchen, Entfernen, Hinzufügen).
  assert.match(skript, /function stufeSetzen[\s\S]{0,600}senden\(zeile, nachher\)/)
  assert.match(skript, /function freigabeEntfernen[\s\S]{0,260}senden\(zeile,/)
  // Und der Wert, der dort steht, ist der BISHERIGE (kein festes false): die
  // eine Regel (`freigabeFelder`) entscheidet ihn.
  assert.match(skript, /function senden[\s\S]{0,220}freigabeFelder\(zeile, stufen/)
})

// ══════════════════════════════════════════════════════════════════════════
// P2 · Moderieren für Personen UND Gruppen
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P2: Gruppenzeilen bekommen „Moderieren“ genauso wie Personen', () => {
  const person = freigabeKnoepfe({ darf_moderieren_vergeben: true, art: 'person' })
  const gruppe = freigabeKnoepfe({ darf_moderieren_vergeben: true, art: 'gruppe' })
  assert.deepEqual(gruppe.stufen, person.stufen)
  assert.equal(gruppe.modus, true)
  assert.deepEqual(FREIGABE_STUFEN, ['lesen', 'schreiben', 'moderieren'])
})

test('UI-R2b/P2: der falsche Kommentar „kein Moderieren für Gruppen“ ist weg', () => {
  const quelle = lies('components/gruppen/kalenderRechte.mjs')
  assert.ok(!/Für\s*\n?\s*\*\s*Gruppen-Einträge gibt es kein „Moderieren“/.test(quelle),
    'der falsche Kommentar steht noch da')
  assert.ok(!/art === 'person'\s*$/.test(quelle.split('export function freigabeKnoepfe')[1]?.split('}')[0] || ''),
    'Moderieren hängt noch an der Art')
})

test('UI-R2b/P2: eine Gruppe MIT Moderieren zeigt die Stufe (Server erlaubt es)', () => {
  const [, gruppe] = freigabeZeilen(OBJEKT.freigaben)
  assert.equal(gruppe.art, 'gruppe')
  const lage = freigabeZeilenLage(gruppe, { darf_moderieren_vergeben: false })
  assert.deepEqual(lage.sichtbareStufen, ['lesen', 'schreiben', 'moderieren'],
    'die Moderieren-Spalte fehlt bei einer Gruppe')
  assert.equal(lage.moderierenFest, true, 'ohne Recht ist sie nur Anzeige')
})

// ══════════════════════════════════════════════════════════════════════════
// P3 · EIN Schlüsselformat für die Sperre
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P3: Baustein und Karte benutzen DENSELBEN busy-Schlüssel', () => {
  const zeile = freigabeZeilen(OBJEKT.freigaben)[0]
  const erwartet = 'freigabe-Kinderchor-person-anna.beispiel@example.org'
  assert.equal(busySchluessel('freigabe', 'Kinderchor', 'person', zeile.kennung), erwartet)
  assert.equal(busySchluessel('standard', 'Kinderchor'), 'standard-Kinderchor')
  assert.equal(busySchluessel('sichtbarkeit', 'Kinderchor', 'gemeinde'), 'sichtbarkeit-Kinderchor-gemeinde')

  // Keine der beiden Dateien baut einen Schlüssel von Hand (Template-Literal
  // mit `freigabe-` bzw. `standard-`), sonst liefen sie wieder auseinander.
  for (const [name, quelle] of [['KalenderRechte.vue', ohneKommentare(RECHTE)],
    ['KalenderEinstellungen.vue', ohneKommentare(KALENDERDATEI)]]) {
    assert.ok(!/`freigabe-\$\{|'freigabe-' \+|`standard-\$\{|'standard-' \+/.test(quelle),
      `${name}: Schlüssel von Hand gebaut`)
  }
  assert.match(ohneKommentare(RECHTE), /busySchluessel\(/, 'der Baustein nutzt den Baukasten')
  assert.match(ohneKommentare(KALENDERDATEI), /busySchluessel\(/, 'die Karte nutzt den Baukasten')
})

test('UI-R2b/P3: während einer offenen Aktion ist die Zeile gesperrt (kein Doppelversand)', () => {
  const quelle = ohneKommentare(RECHTE)
  assert.match(quelle, /function zeileGesperrt/, 'es gibt keine Sperrprüfung')
  assert.match(quelle, /busy === freigabeSchluessel\(z\)/, 'die Zeile prüft ihren eigenen Schlüssel')
  // Und der Handler selbst bricht ab — ein programmatischer Klick kann nicht
  // doch zweimal senden.
  assert.match(quelle, /function stufeSetzen[\s\S]{0,160}zeileGesperrt\(zeile, stufe\)\) return/,
    'stufeSetzen prüft die Sperre nicht')
  // Die Karte sendet während einer laufenden Aktion nicht noch einmal.
  assert.match(ohneKommentare(KALENDERDATEI), /async function freigabeSetzen[\s\S]{0,320}if \(busy\.value\) return/,
    'die Karte sendet während einer offenen Aktion erneut')
})

// ══════════════════════════════════════════════════════════════════════════
// P4 · Wettlauf: nur die jüngste Antwort schreibt
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P4: der Anfragezähler lässt nur die jüngste Antwort durch', () => {
  const zaehler = anfrageZaehler()
  const erste = zaehler.starten('Proben')
  const zweite = zaehler.starten('Proben')
  assert.equal(zaehler.aktuell('Proben', erste), false, 'die ältere Antwort schriebe')
  assert.equal(zaehler.aktuell('Proben', zweite), true)
  // Ein anderer Kalender ist unabhängig.
  const fremd = zaehler.starten('Kinderchor')
  assert.equal(zaehler.aktuell('Kinderchor', fremd), true)
})

test('UI-R2b/P4: die Karte prüft den Zähler NACH dem Ersetzen (Speichern + Nachladen)', () => {
  const quelle = ohneKommentare(KALENDERDATEI)
  assert.match(quelle, /const zaehler = anfrageZaehler\(\)/, 'kein Zähler je Kalender')
  assert.match(quelle, /const nr = zaehler\.starten\(name\)/, 'die Anfrage wird nicht gezählt')
  const ab = quelle.indexOf('async function rechteLaden')
  const laden = quelle.slice(ab, quelle.indexOf('function umschalten('))
  // Das ERSTE Schreiben steht im try-Zweig (das `laedt: true` davor ist der
  // Ladezustand, kein Ergebnis).
  const erstesSchreiben = laden.indexOf('rechte[name] = { daten: daten')
  assert.ok(laden.indexOf('zaehler.aktuell(name, nr)') < erstesSchreiben,
    'die Antwort schreibt, bevor sie geprüft wird')
  assert.match(laden, /get_objekt_rechte[\s\S]{0,200}zaehler\.aktuell\(name, nr\)\) return[\s\S]{0,120}rechte\[name\] = \{ daten/,
    'zwischen Antwort und Schreiben fehlt die Zählerprüfung')
})

// ══════════════════════════════════════════════════════════════════════════
// P5 · Tabelle: Kopf und Zeilen, gleiche Spaltenzahl
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P5: die Spalten kommen aus derselben Quelle wie die Zellen', () => {
  const quelle = ohneKommentare(RECHTE)
  // Kopf: Name + eine Spalte JE GEZEIGTER STUFE + Aktion.
  assert.match(quelle, /for \(const stufe of gezeigteStufen\.value\) liste\.push\(/, 'der Kopf zählt die Stufen nicht')
  // UI-R2c: die Zeile läuft über DIESELBE Liste — sonst standen bei gemischten
  // Zeilen fünf Kopfspalten über Zeilen mit vier Zellen. Je Stufe entscheidet
  // `stufeDerZeile`, ob ein Kästchen oder ein Platzhalter erscheint.
  assert.match(quelle, /v-for="stufe in gezeigteStufen"/, 'die Zeile zeichnet andere Stufen als der Kopf')
  assert.match(quelle, /stufeDerZeile\(z, stufe\)/, 'die Zeile prüft nicht, ob sie die Stufe trägt')
  // Zusatz-Kopfzeile (die 3-Zellen-Zeile) ist weg.
  assert.ok(!/kr-stufen-kopf/.test(RECHTE), 'die alte Zusatz-Kopfzeile steht noch da')
  // `aktion: true` schaltet DkTable auf `table-layout: fixed`.
  assert.match(quelle, /key: 'aktion', label: 'Aktion', aktion: true/, 'die Aktionsspalte fehlt')
})

test('UI-R2b/P5: gezeigteStufen und stufeDerZeile lesen dieselbe Moderieren-Sicht', () => {
  const quelle = ohneKommentare(RECHTE)
  // Der Kopf fragt: Recht ODER irgendeine Zeile trägt es.
  assert.match(quelle, /const gezeigteStufen = computed[\s\S]{0,320}darfModerierenVergeben\.value \|\| zeilen\.value\.some/)
  // Die Zeile fragt dieselbe Lage — sonst driften Kopf und Zelle auseinander
  // (UI-R2c-Befund). UI-R3c: die Regel selbst steht EINMAL in
  // `kalenderRechte.mjs` (`zeileTraegtStufe`, mit `darf_moderieren_vergeben`);
  // Tabelle und Handy-Liste rufen sie mit DERSELBEN Lage auf.
  assert.match(quelle, /function stufeDerZeile\(z, stufe\)[\s\S]{0,260}zeileTraegtStufe\(z, stufe, \{ darf_moderieren_vergeben: darfModerierenVergeben\.value \}\)/)
  assert.match(quelle, /zeileTraegtStufe as |zeileTraegtStufe,/, 'die gemeinsame Regel wird importiert')
})

// ══════════════════════════════════════════════════════════════════════════
// P6 · Keine Karte in der Karte
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P6: GruppenEinstellungen legt keine eigenen DkCard mehr an', () => {
  assert.ok(!/<DkCard|import DkCard/.test(KARTE), 'die Karte in der Karte steht noch')
})

test('UI-R2b/P6: auf der Seite stehen zwei GESCHWISTER-Karten, jeder Titel einmal', () => {
  const treffer = [...GRUPPENSEITE.matchAll(/title="(Rollen der Gruppe|Kalender der Gruppe)"/g)]
    .map((m) => m[1])
  assert.deepEqual(treffer, ['Rollen der Gruppe', 'Kalender der Gruppe'],
    'die Titel stehen nicht je einmal auf der Seite: ' + treffer.join(' | '))
  // Beide Karten liegen im selben Raster — keine ist im Körper der anderen.
  const block = GRUPPENSEITE.slice(GRUPPENSEITE.indexOf('aktiverReiter === \'einstellungen\''),
    GRUPPENSEITE.indexOf('<template v-else>'))
  assert.equal((block.match(/<DkCard/g) || []).length, 2)
  assert.equal((block.match(/<\/DkCard>/g) || []).length, 2, 'eine Karte steckt in der anderen')
  // Jeder Bereich bekommt seinen Teil ausdrücklich (sonst stünde beides zweimal).
  assert.match(block, /teil="rollen"/)
  assert.match(block, /teil="kalender"/)
})

// ══════════════════════════════════════════════════════════════════════════
// P7 · Ja/Nein als Radiogruppe
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P7: die Anlege-Frage ist eine echte Radiogruppe', () => {
  const quelle = ohneKommentare(KALENDERDATEI)
  const block = quelle.slice(quelle.indexOf('role="radiogroup"') - 200)
  const frage = block.slice(0, block.indexOf('</fieldset>'))
  assert.match(frage, /<fieldset/, 'kein fieldset')
  assert.match(frage, /<legend/, 'keine legend')
  assert.match(frage, /role="radiogroup"/, 'kein role=radiogroup')
  assert.match(frage, /type="radio"/, 'keine Radiopunkte')
  assert.ok(!/DkCheckbox|type="checkbox"/.test(frage), 'die Frage besteht noch aus Kästchen')
  // EIN name für beide Punkte: sie schließen sich damit aus.
  const namen = [...frage.matchAll(/name="([^"]+)"/g)].map((m) => m[1])
  assert.equal(new Set(namen).size, 1, 'die Radiopunkte gehören nicht zu einer Gruppe')
})

test('UI-R2b/P7: „nichts gewählt“ kann nicht passieren (Vorgabe + echter Wert)', () => {
  const quelle = ohneKommentare(KALENDERDATEI)
  // Die Vorgabe ist ein Wahrheitswert, kein Tri-State.
  assert.match(quelle, /standardGruppeLesen: true/, 'es gibt keine Vorgabe')
  // Der Radiopunkt schreibt den Wert selbst (v-model), kein „nur wenn wahr“.
  assert.match(quelle, /v-model="form\.standardGruppeLesen"/)
  assert.ok(!/if \(wert\) form\.standardGruppeLesen/.test(quelle), 'der alte „nur Ja“-Weg steht noch da')
  // Beide Antworten sind vorhanden.
  assert.match(quelle, /wert: true, text: 'Ja, alle Gruppenmitglieder dürfen lesen'/)
  assert.match(quelle, /wert: false, text: 'Nein, nur mit eigener Freigabe'/)
})

// ══════════════════════════════════════════════════════════════════════════
// P8 · Kein canManage als Moderationsrecht
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P8: allein `darf_moderieren_vergeben` entscheidet — fehlt es, gilt false', () => {
  for (const [name, quelle] of [['GruppeDetail.vue', GRUPPENSEITE],
    ['KalenderEinstellungen.vue', KALENDERDATEI], ['GruppenEinstellungen.vue', KARTE]]) {
    const skript = quelle.slice(quelle.indexOf('<script'), quelle.indexOf('</script>'))
    assert.ok(!/darfModerierenVergeben/.test(skript), `${name}: eigenes Moderationsrecht aus den Rollen`)
    // Kein Moderationsrecht aus `canManage`/`verantwortliche` abgeleitet.
    assert.ok(!/(canManage|verantwortliche)[^\n]{0,80}darf-?[mM]oderieren/i.test(quelle),
      `${name}: canManage steht am Moderationsrecht`)
    assert.ok(!/darf-?[mM]oderieren[^\n]{0,60}(canManage|verantwortliche)/i.test(quelle),
      `${name}: canManage steht am Moderationsrecht`)
  }
  // Der Baustein liest NUR den Serverwert — fail closed, kein Rückfall aus
  // einer Prop (UI-R2c: die Rückfall-Prop `darfModerieren` ist entfernt).
  const baustein = ohneKommentare(RECHTE)
  assert.match(baustein, /Boolean\(props\.objekt\?\.darf_moderieren_vergeben\)/)
  assert.ok(!/props\.darfModerieren/.test(baustein), 'die Rückfall-Prop wird noch gelesen')
})

test('UI-R2b/P8: die Karte liest das Recht aus der Serverantwort, nicht aus den Rollen', () => {
  // UI-R2c: `darfModerieren(name)` der Karte war toter Code (niemand rief sie).
  // Die Entscheidung liegt JETZT allein im Baustein, aus dem Serverfeld.
  const quelle = skriptVon(RECHTE)
  assert.match(quelle, /darf_moderieren_vergeben/, 'der Baustein liest das Serverfeld nicht')
  assert.ok(!/function darfModerieren\s*\(/.test(skriptVon(KALENDERDATEI)),
    'die tote `darfModerieren()` steht noch in der Karte')
  // Und die Karte führt das Recht nicht selbst über eine eigene Weiche.
  assert.ok(!/darfModerieren\s*\(/.test(ohneKommentare(skriptVon(KALENDERDATEI))),
    'die Karte entscheidet selbst über das Moderationsrecht')
})

// ══════════════════════════════════════════════════════════════════════════
// P9/P10 · Namen vom Server
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P9: Zeilen zeigen den Server-Namen, nie die Kontokennung', () => {
  const [person, gruppe] = freigabeZeilen(OBJEKT.freigaben)
  assert.equal(person.anzeige, 'Anna Beispiel')
  assert.ok(!person.anzeige.includes('@'), 'die Kontokennung steht in der Fläche')
  assert.equal(gruppe.anzeige, 'Chor', 'die Gruppen-ID steht in der Fläche')
  assert.notEqual(gruppe.anzeige, 'G-Chor')
})

test('UI-R2b/P9: die Matrix rendert `anzeige` (aus `name`), nicht `kennung`', () => {
  const quelle = ohneKommentare(RECHTE)
  const treffer = [...quelle.matchAll(/z\.anzeige/g)]
  assert.ok(treffer.length >= 3, 'die Zeilen lesen den Anzeigenamen nicht')
  assert.ok(!/\{\{\s*z\.kennung\s*\}\}/.test(quelle), 'die Zeile zeigt die Kennung')
})

// ══════════════════════════════════════════════════════════════════════════
// P11 · Die Stufe „gruppe“ prüfen HV/MV der Gruppe
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P11: „wartet auf HV/MV der Gruppe“ — nicht auf die Gruppenleitung', () => {
  const lage = sichtbarkeitLage('beantragt', 'gruppe', { untergruppe: 'UG-K' })
  assert.match(lage.erlaeuterung, /HV\/MV der Gruppe/)
  assert.ok(!/Gruppenleitung/i.test(JSON.stringify(lage)), '„Gruppenleitung“ steht in der Fläche')
})

// ══════════════════════════════════════════════════════════════════════════
// P12 · Erfolgsmeldung nach Ziel
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P12: die Erfolgsmeldung nennt das Ziel', () => {
  const gruppe = sichtbarkeitMeldung({ ziel: 'gruppe' }, 'beantragt', 'beantragen')
  const gemeinde = sichtbarkeitMeldung({ ziel: 'gemeinde' }, 'beantragt', 'beantragen')
  assert.equal(gruppe, 'Antrag eingetragen — er wartet auf HV/MV der Gruppe.')
  assert.equal(gemeinde, 'Antrag eingetragen — er wartet auf die Prüfung durch die Gemeinde.')
  assert.equal(gruppe !== gemeinde, true, 'beide Ziele tragen dieselbe Meldung')

  assert.equal(sichtbarkeitMeldung({ ziel: 'gruppe' }, 'aktiv', 'beantragen'),
    'Freigegeben — die ganze Gruppe sieht den Kalender jetzt.')
  assert.equal(sichtbarkeitMeldung({ ziel: 'gemeinde' }, 'aktiv', 'beantragen'),
    'Freigegeben — alle Mitglieder der Gemeinde sehen den Kalender jetzt.')
  assert.equal(sichtbarkeitMeldung({ ziel: 'gruppe' }, 'aus', 'zuruecknehmen'),
    'Freigabe für die ganze Gruppe zurückgenommen — gilt sofort.')
  assert.equal(sichtbarkeitMeldung({ ziel: 'gemeinde' }, 'aus', 'zuruecknehmen'),
    'Freigabe für alle Mitglieder der Gemeinde zurückgenommen — gilt sofort.')
  // Und die Karte benutzt sie (keine eigene Meldung daneben).
  assert.match(skriptVon(KALENDERDATEI), /sichtbarkeitMeldung\(/)
})

// ══════════════════════════════════════════════════════════════════════════
// P13 · Hinweis nur ohne Vergaberecht
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P13: „Das Prüfrecht vergeben nur HV und MV“ nur ohne Vergaberecht', () => {
  const quelle = skriptVon(RECHTE)
  const ab = quelle.indexOf('const moderierenHinweis')
  const block = quelle.slice(ab, ab + 300)
  assert.match(block, /darfModerierenVergeben\.value/, 'der Hinweis liest das Recht nicht')
  assert.ok(/darfModerierenVergeben\.value[\s\S]{0,40}\n?\s*\? ''/.test(block),
    'der Hinweis hängt nicht am Recht: ' + block.slice(0, 160))
})

// ══════════════════════════════════════════════════════════════════════════
// P14 · nurAnzeigen sperrt alles
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P14: `nurAnzeigen` macht die ganze Matrix schreibgeschützt', () => {
  const quelle = ohneKommentare(RECHTE)
  const sperre = quelle.slice(quelle.indexOf('function zeileGesperrt'), quelle.indexOf('function namenTeile'))
  assert.match(sperre, /if \(props\.nurAnzeigen\) return true/, 'nurAnzeigen sperrt die Zeile nicht')
  // Standard-Schalter, Beantragen/Zurücknehmen, Suche und Gruppe sind weg.
  assert.match(quelle, /v-if="!nurAnzeigen"[\s\S]{0,200}kr-aendern/, 'der Standard-Schalter bleibt bedienbar')
  assert.equal((quelle.match(/k\.beantragen && !nurAnzeigen/g) || []).length, 1, 'Beantragen bleibt bedienbar')
  assert.equal((quelle.match(/k\.zuruecknehmen && !nurAnzeigen/g) || []).length, 1, 'Zurücknehmen bleibt bedienbar')
  assert.match(quelle, /function standardUmschalten\(\) \{\s*if \(props\.nurAnzeigen\) return/,
    'der Handler sendet trotz nurAnzeigen')
})

// ══════════════════════════════════════════════════════════════════════════
// P15 · Fehlerzustand und toter Kommentar
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P15: der Fehlerzustand heißt „Freigaben nicht geladen“', () => {
  assert.match(RECHTE, /title="Freigaben nicht geladen"/)
  assert.ok(!/title="Kalender nicht geladen"/.test(RECHTE), 'der alte Titel steht noch da')
  assert.ok(!/@aendern/.test(RECHTE), 'der tote `@aendern`-Kommentar steht noch da')
})

// ══════════════════════════════════════════════════════════════════════════
// P16 · 403 blendet die Karte aus
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/P16: 403 aus get_kalender_verwaltung blendet die Karte aus', () => {
  const quelle = ohneKommentare(KALENDERDATEI)
  assert.match(quelle, /const gesperrt = ref\(false\)/, 'es gibt keinen Ausblende-Zustand')
  assert.match(quelle, /Number\(e\?\.status\) === 403[\s\S]{0,220}gesperrt\.value = true/,
    'ein 403 gilt weiter als Fehler')
  assert.match(quelle, /v-else-if="!gesperrt && antwortDa"/,
    'die Karte wird bei 403 nicht ausgeblendet (und nicht vor der Antwort gezeigt)')
})

test('UI-R2b/Tokens: die neuen Stellen bleiben bei Tokens', () => {
  const farbe = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/
  for (const [name, text] of [['KalenderRechte.vue', RECHTE], ['KalenderEinstellungen.vue', KALENDERDATEI],
    ['GruppenEinstellungen.vue', KARTE]]) {
    const stil = text.includes('<style') ? text.slice(text.indexOf('<style')) : text
    assert.ok(!farbe.test(stil), `${name}: feste Farbwerte`)
  }
  const abstand = /(margin|padding|gap|row-gap|column-gap|border|border-radius|inset|top|right|bottom|left)[\w-]*\s*:\s*[^;]*\d+(px|rem|em)/g
  for (const [name, text] of [['KalenderRechte.vue', RECHTE], ['KalenderEinstellungen.vue', KALENDERDATEI],
    ['GruppenEinstellungen.vue', KARTE]]) {
    const stil = text.slice(text.indexOf('<style'))
    const treffer = [...stil.matchAll(abstand)].filter((m) => !m[0].includes('var(--'))
    assert.deepEqual(treffer.map((m) => m[0]), [], `${name}: Maße aus Tokens`)
  }
})
