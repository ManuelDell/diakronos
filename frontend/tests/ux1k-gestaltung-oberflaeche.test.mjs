/**
 * UX1k — Test: Regeln der Einstellungen-Seite „Gestaltung“ (ohne Vue).
 *
 * Geprüft wird, was die Karte verlangt und was ein Bild-Test NICHT beweisen
 * kann:
 *
 *   1. Sichtbarkeit: NUR System Manager (nicht Mitgliederadministrator —
 *      das ist die Rolle, die der Server ebenfalls verweigert).
 *   2. Live-Prüfung: ganze px-Zahl, erlaubter Bereich, aufsteigende Skala —
 *      mit Meldungen, die sagen, was jetzt zu tun ist (Prinzip I4).
 *   3. „Speichern“ sendet die GEPRÜFTEN Werte, ein ungültiges Feld den
 *      Standard (der Server lehnt sonst alles ab).
 *   4. „Auf Standard zurücksetzen“ nennt Ziel und Standardwert und sagt, dass
 *      die Oberfläche die alten Werte neu lädt (bis UX2a „Rückgängig“ kann).
 *   5. Die Vorschau setzt GENAU die gelieferten Token als CSS-Variablen —
 *      keine eigene Token-Liste im Frontend (sonst driftet sie vom Server).
 *   6. Die Seite ist erreichbar (#/einstellungen/gestaltung), im Router
 *      angemeldet und der Bau (tokens.css) bleibt die einzige CSS-Quelle.
 *
 * Der Test liest nur Dateien INNERHALB von frontend/ — backend/Dockerfile
 * braucht für ihn keine zusätzliche COPY-Zeile (Regel 13).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import {
  darfGestaltung,
  pruefeFeld,
  pruefeSkala,
  werteFuerServer,
  geaenderteFelder,
  rueckgaengigMeldung,
  frischeCssAdresse,
  GESTALTUNG_ROLLE,
  zahl,
} from '../src/diakonos/composables/gestaltung.mjs'

const lies = (rel) => readFileSync(fileURLToPath(new URL('../' + rel, import.meta.url)), 'utf8')
const gibtEs = (rel) => existsSync(fileURLToPath(new URL('../' + rel, import.meta.url)))

// ── 1. Sichtbarkeit ───────────────────────────────────────────────────────

test('UX1k: nur System Manager sehen die Gestaltung', () => {
  assert.equal(darfGestaltung({ rollen: ['System Manager'] }), true)
  assert.equal(darfGestaltung({ rollen: [' Mitglieder leiten ', 'System Manager'] }), true)
  // Mitgliederadministrator ist Administrator, aber NICHT System Manager —
  // genau diesen Unterschied prüft der Server (403).
  assert.equal(darfGestaltung({ rollen: ['Mitgliederadministrator'] }), false)
  assert.equal(darfGestaltung({ rollen: ['Mitglied'] }), false)
  assert.equal(darfGestaltung({ rollen: [] }), false)
  assert.equal(darfGestaltung({ rollen: null }), false)
  assert.equal(darfGestaltung(), false)
  assert.equal(GESTALTUNG_ROLLE, 'System Manager')
})

test('UX1k: die Textform des Formulars ist gültig (Befund aus der Abnahme)', () => {
  // Das Formular liefert TEXT (`"40"`), die Serverantwort Zahlen. `pruefeFeld`
  // (über `zahl`) muss beides annehmen — sonst gilt jede getippte Eingabe als
  // unbrauchbar und die Skala wird gegen die Standards geprüft (im Browser
  // gefunden: „--pad auf 40“ blieb unmöglich).
  assert.equal(zahl('40'), 40)
  assert.equal(zahl(40), 40)
  assert.equal(zahl('40px'), 40)
  assert.equal(zahl(40.5), null)
  assert.equal(zahl(Number.NaN), null)
  assert.equal(zahl(''), null)
  // Und die Skala nimmt die Textform genauso: `--sp-8` auf 20 (Text) bricht die
  // Ordnung zu `--pad` (Standard 16) — im Server ist es derselbe Satz.
  const felder = [
    { token: '--sp-7', standard: 48, min: 8, max: 96, gruppe: 'skala' },
    { token: '--sp-8', standard: 64, min: 8, max: 160, gruppe: 'skala' },
    // `--pad` liegt in derselben Anzeigegruppe, ist aber KEIN Kettenglied
    // (UX1j2) — es darf die Ordnung nicht brechen.
    { token: '--pad', standard: 16, min: 4, max: 160, gruppe: 'skala' },
  ]
  const KETTE = ['--sp-7', '--sp-8']
  assert.match(pruefeSkala(felder, { '--sp-8': '40' }, KETTE).text, /--sp-8 \(40 px\)/)
  // Textform ohne Bruch (aufsteigend) ist in Ordnung.
  assert.equal(pruefeSkala(felder, { '--sp-8': '56' }, KETTE).ok, true)
  assert.deepEqual(pruefeSkala(felder, { '--sp-8': '40' }, KETTE).paare,
    [['--sp-7', '--sp-8']])
  // Und `--pad` bricht NICHTS, egal wie klein es ist.
  assert.equal(pruefeSkala(felder, { '--sp-8': '64', '--pad': '4' }, KETTE).ok, true)
})

// ── 2. Live-Prüfung ───────────────────────────────────────────────────────

const SP4 = { token: '--sp-4', min: 8, max: 64, standard: 16, gruppe: 'skala' }

test('UX1k: Feld-Prüfung nimmt ganze px-Zahlen im Bereich an', () => {
  assert.deepEqual(pruefeFeld(SP4, '16'), { ok: true, wert: 16, text: '' })
  assert.deepEqual(pruefeFeld(SP4, 20), { ok: true, wert: 20, text: '' })
  assert.deepEqual(pruefeFeld(SP4, '24px'), { ok: true, wert: 24, text: '' })
  assert.equal(pruefeFeld(SP4, ' 32 ').wert, 32)
})

test('UX1k: ungültige Eingabe wird benannt, nichts erfunden', () => {
  // Kommazahl, negativ, leer, Unsinn, fremde Einheit — alle unbrauchbar.
  for (const unsinn of ['16.5', '-4', '', '   ', 'abc', '1rem', 'var(--x)', 'calc(1px)']) {
    const r = pruefeFeld(SP4, unsinn)
    assert.equal(r.ok, false, `"${unsinn}" hätte abgelehnt werden müssen`)
    assert.equal(r.wert, null)
    assert.match(r.text, /ganze Zahl/)
    assert.match(r.text, /--sp-4/)
    assert.match(r.text, /8 bis 64/)
  }
})

test('UX1k: Bereich verletzt -> Meldung nennt Wert und Grenzen', () => {
  const zuGross = pruefeFeld(SP4, '65')
  assert.equal(zuGross.ok, false)
  assert.equal(zuGross.wert, 65)
  assert.match(zuGross.text, /65 px/)
  assert.match(zuGross.text, /8 bis 64 px/)
  assert.equal(pruefeFeld(SP4, '7').ok, false)
  assert.equal(pruefeFeld(SP4, '8').ok, true)
  assert.equal(pruefeFeld(SP4, '64').ok, true)
})

test('UX1k: die Abstands-Skala muss aufsteigend bleiben', () => {
  const felder = [
    { token: '--sp-1', standard: 4, min: 1, max: 32, gruppe: 'skala' },
    { token: '--sp-2', standard: 8, min: 2, max: 40, gruppe: 'skala' },
    { token: '--sp-3', standard: 12, min: 4, max: 48, gruppe: 'skala' },
    // Abstands-Feld wie der Server es liefert (Anzeigegruppe `skala`) — es ist
    // aber KEIN Kettenglied und darf die Ordnung nicht beeinflussen (UX1j2).
    { token: '--pad', standard: 16, min: 4, max: 48, gruppe: 'skala' },
    // Rundung: keine Abstandsreihe — darf die Ordnung NICHT beeinflussen.
    { token: '--radius', standard: 8, min: 0, max: 24, gruppe: 'radius' },
  ]
  const KETTE = ['--sp-1', '--sp-2', '--sp-3']
  assert.equal(pruefeSkala(felder, { '--sp-1': '4', '--sp-2': '8', '--sp-3': '12' }, KETTE).ok, true)
  // Gleichstand ist auch ein Bruch (streng aufsteigend).
  const gleich = pruefeSkala(felder, { '--sp-2': '4' }, KETTE)
  assert.equal(gleich.ok, false)
  assert.deepEqual(gleich.paare, [['--sp-1', '--sp-2']])
  assert.match(gleich.text, /aufsteigend/)
  assert.match(gleich.text, /--sp-1/)
  assert.match(gleich.text, /--sp-2/)
  // Umgedreht: 32 < 8 ist falsch.
  assert.equal(pruefeSkala(felder, { '--sp-1': '32' }, KETTE).ok, false)
  // Ein ungültiges Feld zählt für die Ordnung mit seinem STANDARD (wie im
  // Server: `wert_oder_standard`) — es macht die Skala nicht kaputt.
  assert.equal(pruefeSkala(felder, { '--sp-2': 'abc' }, KETTE).ok, true)
  // `--radius` und `--pad` sind keine Kettenglieder — egal wie klein.
  assert.equal(pruefeSkala(felder, { '--radius': '0', '--pad': '4' }, KETTE).ok, true)
})

test('UX1j2: nur die Server-Kette zählt — --pad ist kein Kettenglied', () => {
  // Befund aus der Browser-Abnahme: Die Oberfläche prüfte die ganze Gruppe
  // `skala` und damit auch `--pad` (16 px < `--sp-8` 64 px). Ergebnis: JEDE
  // Skalenstufe über 14 px war gesperrt, und „Speichern“ zeigte bei jeder
  // Eingabe die Grundsatzmeldung. Die Kette kommt deshalb vom SERVER
  // (`skala_ordnung`), hier übergeben — keine Tokenliste im Frontend.
  const felder = [
    { token: '--sp-8', standard: 64, min: 8, max: 160, gruppe: 'skala' },
    { token: '--pad', standard: 16, min: 4, max: 48, gruppe: 'skala' },
    { token: '--abstand-gruppe', standard: 24, min: 8, max: 64, gruppe: 'skala' },
  ]
  const KETTE = ['--sp-8']
  // `--pad` und `--abstand-gruppe` sind keine Kettenglieder: kein Bruch.
  assert.equal(pruefeSkala(felder, { '--pad': '14' }, KETTE).ok, true)
  assert.deepEqual(pruefeSkala(felder, {}, KETTE).paare, [])
  // Ohne Kette vom Server wird nichts geprüft (keine erfundene Reihenfolge).
  assert.equal(pruefeSkala(felder, { '--sp-8': '8' }, []).ok, true)
  // Ein echter Bruch INNERHALB der Kette wird weiter gemeldet.
  const zwei = [felder[0], { token: '--sp-7', standard: 48, min: 8, max: 96, gruppe: 'skala' }]
  assert.equal(pruefeSkala(zwei, { '--sp-8': '20' }, ['--sp-7', '--sp-8']).ok, false)
})

test('UX1k: die Skalen-Kette kommt vom Server (skala_ordnung), nicht aus dem Frontend', () => {
  const quelle = lies('src/diakonos/composables/useGestaltung.js')
  assert.match(quelle, /skalaOrdnung/)
  assert.match(quelle, /s\.skala_ordnung/)
  assert.match(quelle, /pruefeSkala\(felder\.value, eingaben\.value, skalaOrdnung\.value\)/)
  // Kein Filter mehr nach der Anzeigegruppe im Regel-Modul.
  assert.doesNotMatch(lies('src/diakonos/composables/gestaltung.mjs'), /SKALA_GRUPPEN/)
})

test('UX1k: die Skala gilt auch, wenn nur EIN Wert getippt wird', () => {
  // Beim Tippen im Feld --sp-2 prüft die Oberfläche immer die GANZE Skala.
  const felder = [
    { token: '--sp-1', standard: 4, min: 1, max: 32, gruppe: 'skala' },
    { token: '--sp-2', standard: 8, min: 2, max: 40, gruppe: 'skala' },
  ]
  const r = pruefeSkala(felder, { '--sp-1': '4', '--sp-2': '4' }, ['--sp-1', '--sp-2'])
  assert.equal(r.ok, false)
})

test('UX1k: eine am Feld scheiternde Prüfung sagt es AUCH oben', () => {
  // Im Browser gefunden: „Speichern“ mit einem Wert außerhalb des Bereichs
  // zeigte nur den Fehler am Feld — die Hinweisfläche blieb leer, und der
  // Knopf wirkte wirkungslos (kein Netzaufruf). `pruefeAlles` liefert jetzt
  // den ersten Grund mit (`einzeln`), `speichern` zeigt ihn auch oben.
  const aufrufe = lies('src/diakonos/composables/useGestaltung.js')
  assert.match(aufrufe, /einzeln:\s*erster/)
  assert.match(aufrufe, /fehler\.value = pruefung\.text \|\| pruefung\.einzeln/)
})

// ── 3. Was gesendet wird ──────────────────────────────────────────────────

test('UX1k: Speichern sendet geprüfte Werte, ungültige fallen auf den Standard', () => {
  const felder = [
    { token: '--sp-1', standard: 4, min: 1, max: 32, gruppe: 'skala' },
    { token: '--pad', standard: 16, min: 4, max: 48, gruppe: 'abstand' },
  ]
  assert.deepEqual(
    werteFuerServer(felder, { '--sp-1': '6', '--pad': '20' }),
    { '--sp-1': 6, '--pad': 20 },
  )
  assert.deepEqual(
    werteFuerServer(felder, { '--sp-1': '6', '--pad': '999' }),
    { '--sp-1': 6, '--pad': 16 },
  )
})

test('UX1k: „Speichern“ erscheint nur bei echter Änderung', () => {
  const felder = [
    { token: '--sp-1', standard: 4, min: 1, max: 32, gruppe: 'skala', wert: 4 },
    { token: '--pad', standard: 16, min: 4, max: 48, gruppe: 'abstand', wert: 16 },
  ]
  assert.deepEqual(geaenderteFelder(felder, { '--sp-1': '4', '--pad': '16px' }), [])
  assert.deepEqual(geaenderteFelder(felder, { '--sp-1': '6', '--pad': '16' }), ['--sp-1'])
  // Ein ungültiger Wert zählt als Änderung — der Speichern-Knopf bleibt
  // erreichbar, damit die Meldung am Feld gesehen werden kann.
  assert.deepEqual(geaenderteFelder(felder, { '--sp-1': 'x', '--pad': '16' }), ['--sp-1'])
})

// ── 4. Rückgängig-Meldung ─────────────────────────────────────────────────

test('UX1k: Zurücksetzen nennt alten und neuen Wert und den nächsten Schritt', () => {
  const feld = rueckgaengigMeldung({ ziel: 'feld', token: '--pad', alt: 20, standard: 16 })
  assert.match(feld.text, /--pad/)
  assert.match(feld.text, /16 px/)
  assert.match(feld.text, /20 px/)
  assert.match(feld.text, /erneut ein und speichere/)
  const alle = rueckgaengigMeldung({ ziel: 'alle' })
  assert.match(alle.text, /Standardwerten/)
  assert.match(alle.text, /Rückgängig/)
})

// ── 5. Vorschau und Neuladen der CSS ──────────────────────────────────────

test('UX1k: frische CSS-Adresse umgeht den Zwischenspeicher', () => {
  const a = frischeCssAdresse('/diakronos/gestaltung.css', 'abc123')
  assert.equal(a, '/diakronos/gestaltung.css?v=abc123')
  // Ein alter `?v=`-Teil wird ersetzt, nicht angehängt.
  assert.equal(
    frischeCssAdresse('/diakronos/gestaltung.css?v=alt', 'neu'),
    '/diakronos/gestaltung.css?v=neu',
  )
  // Zwei Aufrufe ohne Stand ergeben ZWEI verschiedene Adressen (sonst läse
  // der Browser die alte Datei aus dem Zwischenspeicher).
  assert.notEqual(frischeCssAdresse('/gestaltung.css'), frischeCssAdresse('/gestaltung.css'))
})

test('UX1k: die Seite setzt die gelieferten Token als CSS-Variablen (keine eigene Liste)', () => {
  const quelle = lies('src/diakonos/pages/einstellungen/Gestaltung.vue')
  // Die Vorschau bindet Token aus den Server-Feldern (Regel `vorschauSetzen`).
  assert.match(quelle, /vorschauSetzen\(/)
  const regeln = lies('src/diakonos/composables/useGestaltung.js')
  assert.match(regeln, /setProperty\(feld\.token/)
  assert.match(lies('src/diakonos/composables/gestaltung.mjs'), /frischeCssAdresse/)
  // Kein fest verdrahteter Token-Name mit Wert im Vorschau-Code.
  assert.doesNotMatch(quelle, /--sp-[1-8]'\s*,\s*'/)
  // Und keine eigene Einstellungs-Liste: die Felder kommen vom Server.
  assert.doesNotMatch(quelle, /const\s+TOKEN\s*=/)
  const rules = lies('src/diakonos/composables/gestaltung.mjs')
  assert.doesNotMatch(rules, /'--sp-\d'/)
  assert.doesNotMatch(rules, /"([^"]*\d+)px"/)
})

// ── 6. Einbau in die App ──────────────────────────────────────────────────

test('UX1k: Gestaltung ist ein Einstellungs-Abschnitt mit eigener Adresse', () => {
  const seite = lies('src/diakonos/pages/Einstellungen.vue')
  assert.match(seite, /einstellungen\/Gestaltung\.vue/)
  assert.match(seite, /id: 'gestaltung'/)
  assert.match(seite, /#\/einstellungen\/gestaltung/)
  assert.match(seite, /EinstellungenGestaltung/)

  const router = lies('src/diakonos/router.js')
  assert.match(router, /EinstellungenGestaltung:\s*\(\)\s*=>\s*import\('\.\/pages\/Einstellungen\.vue'\)/)
  assert.match(router, /'#\/einstellungen\/gestaltung':\s*'EinstellungenGestaltung'/)
  // Der Router-Guard hält Fremde auf — der Server verweigert zusätzlich (403).
  assert.match(router, /'EinstellungenGestaltung'/)
  const menue = lies('src/diakonos/menue.js')
  assert.match(menue, /'EinstellungenGestaltung'/)
})

test('UX1k: der Abschnitt steht unter „Erweitert“ und nur für System Manager', () => {
  const seite = lies('src/diakonos/pages/Einstellungen.vue')
  assert.match(seite, /gruppe: 'Erweitert'/)
  // Sichtbarkeit über die Rollenliste — nicht über `is_admin`.
  assert.match(seite, /nurSystemManager: true/)
  assert.match(seite, /rollen\.includes\('System Manager'\)/)
  const komponente = lies('src/diakonos/pages/einstellungen/Gestaltung.vue')
  assert.match(komponente, /sichtbar\(\)/)
  assert.match(lies('src/diakonos/composables/useGestaltung.js'), /darfGestaltung/)
  // Der Server entscheidet: `lesen`, `speichern`, `zuruecksetzen` werden
  // aufgerufen (die drei Endpunkte der Karte, UX1j). Verglichen wird Stück für
  // Stück — so bleibt der Test lesbar und unabhängig von der Schreibweise.
  const aufrufe = lies('src/diakonos/composables/useGestaltung.js')
  for (const teil of ['API + ', 'lesen', 'speichern', 'zuruecksetzen']) {
    assert.ok(aufrufe.includes(teil), `Aufruf-Teil ${teil} fehlt`)
  }
  assert.match(aufrufe, /diakronos[.]api[.]g/)
})

test('UX1k: die Vorschau bringt Karte, Liste, Knöpfe und Formular', () => {
  const komponente = lies('src/diakonos/pages/einstellungen/Gestaltung.vue')
  for (const teil of ['vorschau-karte', 'vorschau-liste', 'vorschau-knoepfe', 'vorschau-formular']) {
    assert.ok(komponente.includes(teil), `Vorschau-Teil ${teil} fehlt`)
  }
  // Genau EIN Primärknopf (Prinzip S1) — auch in der Musteransicht ist der
  // gezeigte Primärknopf der einzige gefüllte; die Zurücksetz-Knöpfe sind
  // klein und zweitrangig.
  // GENAU EIN gefüllter Knopf: der Hauptknopf der Aktionsleiste. Die
  // Musteransicht zeigt ihre Knöpfe zweitrangig (Prinzip S1).
  const primaer = komponente.match(/gs-hauptknopf/g) || []
  assert.ok(primaer.length >= 2, 'der Hauptknopf ist gestaltet (Klasse + CSS)')
  assert.equal((komponente.match(/class="gs-hauptknopf"/g) || []).length, 1,
    'genau EIN gefüllter Knopf')
  assert.match(komponente, /class="gs-hauptknopf"[\s\S]{0,400}?Speichern/)
  // Und er ist mindestens 40 px hoch (bei Touch 44).
  assert.match(komponente, /min-height: var\(--control-h\)/)
  assert.match(komponente, /pointer: coarse[\s\S]{0,120}44px/)
})

test('UX1k: keine festen Farben in der neuen Oberfläche (Wächter-Regel)', () => {
  for (const datei of [
    'src/diakonos/pages/einstellungen/Gestaltung.vue',
    'src/diakonos/composables/gestaltung.mjs',
  ]) {
    const text = lies(datei).replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ')
    assert.doesNotMatch(text, /#[0-9a-fA-F]{3,8}\b/, `${datei} enthält eine feste Farbe`)
    assert.doesNotMatch(text, /\brgba?\s*\(|\bhsla?\s*\(/, `${datei} enthält eine feste Farbe`)
  }
  assert.ok(gibtEs('src/diakonos/tokens.css'))
})

test('UX1k: die Seitenlogik ist BAUFÄHIG — kein Bezeichner mit Umlaut', async () => {
  // Im Browser gefunden: `if (!prüfung.ok)` statt `pruefung` — die Seite
  // ließ sich bauen, warf beim Klick aber „prüfung is not defined“, und
  // „Speichern“ tat sichtbar NICHTS (kein Netzaufruf, keine Meldung). Ein
  // Test, der den Quelltext nur liest, merkt das nicht — deshalb hier:
  // alle Bezeichner sammeln und gegen den JS-Parser prüfen.
  const dateien = [
    'src/diakonos/composables/gestaltung.mjs',
    'src/diakonos/composables/useGestaltung.js',
  ]
  for (const datei of dateien) {
    const text = lies(datei)
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/^\s*\/\/.*$/gm, ' ')
      .replace(/`(?:\\[\s\S]|[^`\\])*`/g, '``')
      .replace(/'(?:\\.|[^'\\])*'/g, "''")
      .replace(/"(?:\\.|[^"\\])*"/g, '""')
    const bezeichner = new Set(text.match(/[A-Za-z_$][\w$]*/g) || [])
    const mitUmlaut = [...bezeichner].filter(n => /[^\x00-\x7F]/.test(n))
    assert.deepEqual(mitUmlaut, [], `${datei}: Bezeichner mit Umlaut (Tippfehler-Klasse)`)
  }
  // Gegenprobe: Node ÜBERSETZT die Module wirklich (der Umlaut-Fehler war ein
  // Laufzeitfehler und blieb beim reinen Lesen unsichtbar).
  await import('../src/diakonos/composables/gestaltung.mjs')
  assert.match(lies('src/diakonos/composables/useGestaltung.js'), /if \(!pruefung\.ok\)/)
})

test('UX1j2: ein Bruch im Bestand kann nicht mehr entstehen (Backend regelt die Kette)', () => {
  // Der frühere Umweg `nurBestand` in useGestaltung.js ist entfallen: Sobald
  // die Kette vom Server kommt und `--pad` kein Kettenglied mehr ist, kann
  // „--sp-8 (64) muss kleiner sein als --pad (16)“ gar nicht mehr auftreten.
  // Der Quelltext darf den Umweg nicht wieder einführen (er verdeckte einen
  // echten Fehler, statt ihn zu beheben).
  const quelle = lies('src/diakonos/composables/useGestaltung.js')
  assert.doesNotMatch(quelle, /nurBestand/)
  const felder = [
    { token: '--sp-8', standard: 16, wert: 64, min: 1, max: 64, einheit: 'px', gruppe: 'skala' },
    { token: '--pad', standard: 16, wert: 16, min: 1, max: 96, einheit: 'px', gruppe: 'skala' },
  ]
  assert.equal(pruefeSkala(felder, {}, ['--sp-1', '--sp-8']).ok, true)
})

test('UX1k: Zurücksetz-Knöpfe sind am Handy 44 px hoch (K4)', () => {
  // Im Browser gefunden: DkButton „sm“ setzt seine Höhe FEST auf 28 px — die
  // global angehobene Klickfläche (--control-h 44 px bei pointer: coarse)
  // erreichte die kleinen Knöpfe dieser Seite nicht. Die Seite zieht sie
  // deshalb selbst auf das Klickflächen-Token; kein fester Pixelwert.
  const komponente = lies('src/diakonos/pages/einstellungen/Gestaltung.vue')
  assert.match(komponente,
    /@media \(pointer: coarse\) \{\s*\.gs-feld-zeile :deep\(\.dk-ui-btn\) \{ min-height: var\(--control-h\); \}/)
})

test('UX1k: die Erfolgsmeldung ist SICHTBAR und ihre Live-Region steht fest im DOM', () => {
  // Zwei Anforderungen, die sich widersprechen können: die Vorlese-Region darf
  // nicht an `erfolg` hängen (UX2d2 — sonst entsteht sie erst mit dem Text und
  // bleibt stumm), der Satz muss aber GESEHEN werden. Im Browser gefunden:
  // nach dem Umbau auf DkErfolgsmeldung war der Erfolg nur noch unsichtbar
  // vorhanden. Die sichtbare Fläche hängt deshalb am ZUSTAND (`gespeichert`),
  // nicht am Text.
  const komponente = lies('src/diakonos/pages/einstellungen/Gestaltung.vue')
  assert.match(komponente, /<DkErfolgsmeldung\s+:text="erfolg"\s*\/>/,
    'dauerhafte Live-Region fehlt')
  assert.match(komponente, /<DkHint v-if="gespeichert" variant="ok">/,
    'keine sichtbare Erfolgsmeldung')
  // Die alte, stumme Form darf nicht zurückkehren.
  assert.doesNotMatch(komponente, /<DkHint\s+v-if="erfolg"/)
  const composable = lies('src/diakonos/composables/useGestaltung.js')
  assert.match(composable, /const gespeichert = ref\(false\)/)
  assert.match(composable, /gespeichert\.value = true/)
})

test('UX1k: eine behobene Skalen-Kette räumt ALLE alten Meldungen ab (Review-Befund)', async () => {
  // Repro: Bruch an --sp-3, dann --sp-8 tippen, dann --sp-3 beheben. Früher
  // merkte sich `alterSkalenSatz` nur das zuletzt getippte Feld — der
  // Skalen-Satz blieb an --sp-3/--sp-4 stehen, obwohl die Kette wieder stimmt.
  const { useGestaltung } = await import('../src/diakonos/composables/useGestaltung.js')
  const g = useGestaltung()
  const standard = [4, 8, 12, 16, 24, 32, 48, 64]
  g.felder.value = standard.map((wert, i) => ({
    token: `--sp-${i + 1}`, standard: wert, wert, min: 0, max: 200, gruppe: 'skala',
  }))
  g.skalaOrdnung.value = g.felder.value.map(f => f.token)
  g.eingaben.value = Object.fromEntries(g.felder.value.map(f => [f.token, String(f.wert)]))

  g.eingaben.value = { ...g.eingaben.value, '--sp-3': '20' }
  g.pruefeLive('--sp-3')
  assert.match(g.feldFehler.value['--sp-3'], /aufsteigend/)

  g.eingaben.value = { ...g.eingaben.value, '--sp-8': '70' }
  g.pruefeLive('--sp-8')
  assert.equal(g.feldFehler.value['--sp-8'], '')

  g.eingaben.value = { ...g.eingaben.value, '--sp-3': '12' }
  g.pruefeLive('--sp-3')
  for (const t of g.skalaOrdnung.value) {
    assert.equal(g.feldFehler.value[t] || '', '', `${t} trägt noch eine alte Meldung`)
  }
  assert.deepEqual(g.skalaPaare.value, [])
})
