/**
 * ON-4 — Einrichtungs-Hinweise (Übersicht, Einstellungen, leere Listen, Logo).
 *
 * DIESER TEST FÜHRT DIE LOGIK AUS, ER LIEST SIE NICHT NUR
 * Eine Leiste, die auch dem Nicht-Admin erscheint, eine Karte, die nach
 * „Später erinnern“ noch steht, oder ein Leerzustand, der bei aktiver Suche
 * „Noch keine Mitglieder“ behauptet — alles davon ist im Browser still falsch.
 * Geprüft wird deshalb das Modul, das die Komponenten WIRKLICH benutzen
 * (`src/diakonos/composables/einrichtungsHinweise.mjs`) — keine Nachbildung.
 * Der einzige Ersatz ist `vue` (nur `ref`), wie ihn `node --test` ohne
 * `node_modules` braucht.
 *
 * Zweiter Teil (Wächter): die geänderten Oberflächen tragen keinen festen
 * Farb-, Schrift- oder Radiuswert (CSS-SSOT, `tokens.css` bleibt die einzige
 * Quelle), die Wege im Leerzustand sind die VORHANDENEN, und die Seite
 * „Einstellungen“ hat einen Abschnitt „Einrichtung“ mit Adresse `#/einrichtung`.
 */
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { dirname } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

const HIER = dirname(fileURLToPath(import.meta.url))

/**
 * Datei aus dem Repo ODER aus dem Image-Frontend-Stage lesen (Regel 13).
 * Im Repo liegt dieser Test unter `<wurzel>/frontend/tests/`, im
 * Frontend-Stage des Images unter `<wurzel>/tests/`. Deshalb stufenweise nach
 * oben laufen und in JEDER Stufe beide Formen probieren — sonst finden die
 * Prüfungen im Image nichts (grün im Worktree, rot im Image).
 */
function lies(relativ) {
  const ohneFrontend = relativ.replace(/^frontend\//, '')
  // `HIER.split('/')` hat am ANFANG den leeren Teil des absoluten Pfades
  // (`['', 'root', …]`) — `join` würde ihn verschlucken. Deshalb wird das
  // Verzeichnis geschoben wie in `on3-…` und der absolute Pfad selbst gebaut.
  const hoch = HIER.split('/').filter(Boolean)
  for (let stufe = 0; stufe < 3; stufe += 1) {
    for (const form of [relativ, ohneFrontend]) {
      const pfad = ['', ...hoch, ...form.split('/')].join('/')
      if (existsSync(pfad)) return readFileSync(pfad, 'utf8')
    }
    if (hoch.length > 1) hoch.pop()
  }
  throw new Error(`Datei nicht gefunden: ${relativ} (gesucht ab ${HIER})`)
}

/** Wie `lies`, aber als PFAD: überall 3 Stufen hoch den Nachbarn suchen. */
function liesEcht(relativ) {
  const ohneFrontend = relativ.replace(/^frontend\//, '')
  const hoch = HIER.split('/').filter(Boolean)
  for (let stufe = 0; stufe < 3; stufe += 1) {
    for (const form of [relativ, ohneFrontend]) {
      const pfad = ['', ...hoch, ...form.split('/')].join('/')
      if (existsSync(pfad)) return pfad
    }
    if (hoch.length > 1) hoch.pop()
  }
  throw new Error(`Datei nicht gefunden: ${relativ}`)
}

/**
 * Das Modul laden — mit einem STEHENDBILD (`data:`) von `vue`, damit `ref`
 * ohne `node_modules` funktioniert. `useApi.js` wird nicht aufgelöst (es zieht
 * Rechner, Sitzung und Toast nach); die beiden Anfrage-Helfer werden durch
 * Merker ersetzt, die der Test selbst bedient.
 */
const VUE_ERSATZ = 'data:text/javascript,export function ref(w){return {value:w}}'
const zaehler = { status: 0, erinnern: 0, tage: [] }
let antwortStatus = null
let antwortErinnern = null

const modulQuelle = lies('frontend/src/diakonos/composables/einrichtungsHinweise.mjs')
  .replace(/^import\s+\{\s*ref\s*\}\s+from\s+'vue'$/m, `import { ref } from '${VUE_ERSATZ}'`)
  .replace(
    /^import\s+\{\s*apiCall\s*\}\s+from\s+'\.\/useApi\.js'$/m,
    'const apiCall = globalThis.__on4ApiCall',
  )

/**
 * Der Ersatz für `apiCall` MUSS vor der Auswertung des Moduls stehen — sonst
 * bindet `const apiCall = globalThis.__on4ApiCall` das `undefined` ein.
 */
globalThis.__on4ApiCall = async (pfad, rumpf) => {
  if (pfad.endsWith('einrichtung.status')) {
    zaehler.status += 1
    if (antwortStatus instanceof Error) throw antwortStatus
    return { message: antwortStatus }
  }
  if (pfad.endsWith('einrichtung.erinnern_spaeter')) {
    zaehler.erinnern += 1
    zaehler.tage.push(rumpf?.tage)
    if (antwortErinnern instanceof Error) throw antwortErinnern
    return { message: antwortErinnern }
  }
  throw new Error(`unerwarteter Aufruf: ${pfad}`)
}

/**
 * Das umgeschriebene Modul als DATEI im Temp-Verzeichnis ablegen und von dort
 * importieren. Ein `data:`-URL-Import scheitert am relativen `./einrichtung.mjs`
 * (eine `data:`-Adresse ist keine Basis für relative Pfade); aus einer Datei
 * neben dem Original aufgelöst funktioniert es wie im Browser.
 */
const ARBEIT = mkdtempSync(join(tmpdir(), 'on4-'))
const modulDatei = join(ARBEIT, 'einrichtungsHinweise.mjs')
writeFileSync(modulDatei, modulQuelle, 'utf8')
// Der Nachbar `einrichtung.mjs` liegt im selben Verzeichnis wie das Original —
// dorthin verweist der Import. Deshalb das Original-Verzeichnis nachziehen.
writeFileSync(
  join(ARBEIT, 'einrichtung.mjs'),
  readFileSync(liesEcht('frontend/src/diakonos/composables/einrichtung.mjs'), 'utf8'),
  'utf8',
)
const hinweise = await import(`file://${modulDatei}`)

const ADMIN = { is_admin: true }
const MITGLIED = { is_admin: false }

/** Ein Status wie ihn `einrichtung.status` liefert (Frame 10/11). */
function status(werte = {}) {
  const punkte = werte.punkte || [
    { schluessel: 'gemeindename', erledigt: true, titel: 'Gemeindename gesetzt', hinweis: 'Gemeindename ist gesetzt.', ziel: '#/einstellungen/gemeinde' },
    { schluessel: 'logo', erledigt: false, titel: 'Logo', hinweis: 'Logo der Gemeinde fehlt', ziel: '#/einstellungen/gemeinde' },
    { schluessel: 'kontakt', erledigt: true, titel: 'Kontakt hinterlegt', hinweis: 'Kontakt hinterlegt.', ziel: '#/einstellungen/gemeinde' },
    { schluessel: 'mailversand', erledigt: false, titel: 'Mailversand', hinweis: 'Nicht eingerichtet – keine Einladungen möglich', ziel: '#/einstellungen/mailversand' },
    { schluessel: 'module', erledigt: true, titel: 'Module festgelegt', hinweis: 'Module sind festgelegt.', ziel: '#/einstellungen' },
    { schluessel: 'mitglieder', erledigt: false, titel: 'Mitglieder', hinweis: 'Noch keine Mitglieder angelegt', ziel: '#/personen/liste' },
    { schluessel: 'kalender', erledigt: true, titel: 'Kalender angelegt', hinweis: 'Mindestens ein Kalender ist angelegt.', ziel: '#/kalender/verwalten' },
  ]
  const offen = punkte.filter((p) => p.erledigt === false).length
  return {
    assistent_abgeschlossen: true,
    schritte: [],
    punkte,
    offen_anzahl: offen,
    erledigt_anzahl: punkte.length - offen,
    gesamt_anzahl: punkte.length,
    erinnerung_ab: null,
    ...werte,
  }
}

const TAG = new Date(2026, 9, 31) // 31.10.2026 (Entwurfsdatum)

// ── Wann erscheinen Hinweise überhaupt? ─────────────────────────────────────

test('Hinweise erscheinen nur für Admins, nach dem Assistenten und ohne Erinnerung', () => {
  const st = status()
  assert.equal(hinweise.leistenZeigen(st, ADMIN, TAG), true)
  // Nicht-Admins sehen nichts (der Server weist sie ohnehin ab).
  assert.equal(hinweise.leistenZeigen(st, MITGLIED, TAG), false)
  assert.equal(hinweise.leistenZeigen(st, undefined, TAG), false)
  // Solange der Assistent läuft, ist ER die Baustelle.
  assert.equal(hinweise.leistenZeigen(status({ assistent_abgeschlossen: false }), ADMIN, TAG), false)
  // Ohne Status (Ladefehler) wird nichts behauptet.
  assert.equal(hinweise.leistenZeigen(null, ADMIN, TAG), false)
  // Rollenliste (Boot liefert `roles`) zählt ebenfalls.
  assert.equal(hinweise.leistenZeigen(st, ['Mitgliederadministrator'], TAG), true)
  assert.equal(hinweise.leistenZeigen(st, ['Mitglied'], TAG), false)
})

test('„Später erinnern“ blendet auch die Leisten bis einschließlich zum Tag aus', () => {
  const st = status({ erinnerung_ab: '2026-11-01' })
  assert.equal(hinweise.leistenZeigen(st, ADMIN, new Date(2026, 9, 31)), false)
  assert.equal(hinweise.leistenZeigen(st, ADMIN, new Date(2026, 10, 1)), false)
  assert.equal(hinweise.leistenZeigen(st, ADMIN, new Date(2026, 10, 2)), true)
})

test('erinnerungBis rechnet Tage in LOKALER Zeit (nicht UTC-verschoben)', () => {
  // 31.10. + 7 Tage = 07.11.2026
  assert.equal(hinweise.erinnerungBis(new Date(2026, 9, 31), 7), '2026-11-07')
  // Monatsgrenze: 28.02. + 1 Tag
  assert.equal(hinweise.erinnerungBis(new Date(2027, 1, 28), 1), '2027-03-01')
  // Unsinnige Tage fallen auf die Vorgabe zurück (1..365 laut Vertrag).
  assert.equal(hinweise.erinnerungBis(new Date(2026, 9, 31), 0), '2026-11-07')
})

// ── Karte der Übersicht (Frame 10) ──────────────────────────────────────────

test('Kartentitel nennt den Zähler aus dem Server („… — 3 von 7 offen“)', () => {
  assert.equal(
    hinweise.karteTitelMitZahl(status()),
    'Einrichtung abschließen — 3 von 7 offen',
  )
  // Ohne Zahlen bleibt der reine Titel stehen (kein „NaN von undefined“).
  assert.equal(hinweise.karteTitelMitZahl({}), hinweise.TEXTE.karteTitel)
})

test('die Karte zeigt NUR offene Punkte in Serverreihenfolge, jeder mit Ziel', () => {
  const zeilen = hinweise.kartenZeilen(status())
  assert.deepEqual(zeilen.map((z) => z.schluessel), ['logo', 'mailversand', 'mitglieder'])
  assert.equal(zeilen[0].text, 'Logo der Gemeinde fehlt')
  assert.equal(zeilen[0].ziel, '#/einstellungen/gemeinde')
  assert.equal(zeilen[0].zielText, 'Einrichten')
  // Erledigt → keine Zeilen (die Karte wird dann gar nicht gezeigt).
  const fertig = status({
    punkte: status().punkte.map((p) => ({ ...p, erledigt: true })),
  })
  assert.deepEqual(hinweise.kartenZeilen(fertig), [])
})

// ── Einstellungen (Frame 11) ────────────────────────────────────────────────

test('Mailversand-Leiste: Wortlaut aus dem Entwurf, nur solange der Punkt offen ist', () => {
  const leiste = hinweise.hinweisFuer(status(), 'mailversand', ADMIN, TAG)
  assert.ok(leiste, 'Leiste fehlt trotz offenem Punkt')
  assert.equal(leiste.titel, 'Mailversand ist noch nicht eingerichtet.')
  assert.equal(
    leiste.text,
    'Einladungen, Passwort-Links und Benachrichtigungen können derzeit nicht verschickt werden.',
  )
  assert.equal(leiste.ziel, '#/einstellungen/mailversand')
  assert.equal(leiste.zielText, 'Einrichten')
  // Nach dem Einrichten verschwindet sie.
  const eingerichtet = status({
    punkte: status().punkte.map((p) => (p.schluessel === 'mailversand' ? { ...p, erledigt: true } : p)),
  })
  assert.equal(hinweise.hinweisFuer(eingerichtet, 'mailversand', ADMIN, TAG), null)
  // Nicht-Admin sieht sie nie.
  assert.equal(hinweise.hinweisFuer(status(), 'mailversand', MITGLIED, TAG), null)
})

test('Gemeinde-Leiste nennt die fehlenden Angaben (Name, Logo, Kontakt)', () => {
  const leiste = hinweise.hinweisFuer(status(), 'gemeinde', ADMIN, TAG)
  assert.ok(leiste)
  assert.deepEqual(leiste.fehlend.map((f) => f.schluessel), ['logo'])
  const ohneAlles = status({
    punkte: status().punkte.map((p) => (
      ['gemeindename', 'logo', 'kontakt'].includes(p.schluessel) ? { ...p, erledigt: false } : p
    )),
  })
  const alle = hinweise.hinweisFuer(ohneAlles, 'gemeinde', ADMIN, TAG)
  assert.deepEqual(alle.fehlend.map((f) => f.schluessel), ['gemeindename', 'logo', 'kontakt'])
  assert.equal(alle.ziel, '#/einstellungen/gemeinde')
})

test('NACHTRAG 2026-11-03: es gibt keinen Hinweis auf einen Abschnitt „Einrichtung“', () => {
  // Alle Angaben werden NACH der Ersteinrichtung ausschließlich in den
  // Einstellungen geändert — deswegen kein eigener Abschnitt und keine Leiste
  // mit dem Ziel `#/einrichtung`.
  assert.equal(hinweise.hinweisFuer(status(), 'einrichtung', ADMIN, TAG), null)
  // Unbekannte Seite → kein Hinweis (statt eines Hinweises auf nichts).
  assert.equal(hinweise.hinweisFuer(status(), 'gibtsnicht', ADMIN, TAG), null)
})

test('jede Kartenzeile führt auf ihr Server-Ziel (Einstellungen bzw. Listen)', () => {
  const zeilen = hinweise.kartenZeilen(status())
  assert.deepEqual(
    zeilen.map((z) => z.ziel),
    ['#/einstellungen/gemeinde', '#/einstellungen/mailversand', '#/personen/liste'],
  )
  // Auch der Kalenderpunkt führt in die Kalenderverwaltung, nicht in einen
  // zweiten Einrichtungs-Assistenten.
  const mitKalender = status({
    punkte: status().punkte.map((p) => (
      p.schluessel === 'kalender' ? { ...p, erledigt: false } : p
    )),
  })
  const kalender = hinweise.kartenZeilen(mitKalender).find((z) => z.schluessel === 'kalender')
  assert.equal(kalender.ziel, '#/kalender/verwalten')
  // Ohne Ziel vom Server bleibt der Notnagel `#/einstellungen`.
  const ohneZiel = status({
    punkte: [{
      schluessel: 'module', erledigt: false, titel: 'Module', hinweis: 'Module noch nicht festgelegt',
    }],
  })
  assert.equal(hinweise.kartenZeilen(ohneZiel)[0].ziel, '#/einstellungen')
})

// ── Leere Listen (Frame 12) ─────────────────────────────────────────────────

test('Mitglieder-Leerzustand: freundlicher Text nur, wenn WIRKLICH niemand da ist', () => {
  const leer = hinweise.mitgliederLeerzustand({ gesamtAlle: 0, admin: true })
  assert.equal(leer.leer, true)
  assert.equal(leer.titel, 'Noch keine Mitglieder')
  assert.match(leer.text, /Sobald Sie Personen anlegen oder eine CSV importieren/)
  assert.match(leer.fuss, /Vorname, Nachname und E-Mail/)
  assert.equal(leer.zeigeImport, true)
  assert.equal(leer.zeigeAnlegen, true)
  assert.equal(leer.anlegen, true, '„Mitglied anlegen“ muss den vorhandenen Dialog öffnen')

  // Suche/Filter greift → NICHT „Noch keine Mitglieder“.
  const gefiltert = hinweise.mitgliederLeerzustand({ gesamtAlle: 12, admin: true })
  assert.equal(gefiltert.leer, false)
  assert.equal(gefiltert.titel, 'Keine Mitglieder gefunden')
  assert.equal(gefiltert.zeigeAnlegen, false)

  // Unbekannte Zahl → wie „Filter greift“ (nichts Falsches behaupten).
  assert.equal(hinweise.mitgliederLeerzustand({ gesamtAlle: null, admin: true }).leer, false)
  const unbekannt = hinweise.mitgliederLeerzustand({ gesamtAlle: null, admin: true })
  assert.equal(unbekannt.titel, 'Keine Mitglieder gefunden')
  assert.equal(unbekannt.zeigeAnlegen, false)

  // Nicht-Admin: derselbe Text, aber ohne Verwaltungswege.
  const fremd = hinweise.mitgliederLeerzustand({ gesamtAlle: 0, admin: false })
  assert.equal(fremd.leer, true)
  assert.equal(fremd.zeigeImport, false)
  assert.equal(fremd.zeigeAnlegen, false)
})

test('Kalender-Leerzustand folgt demselben Muster (nur Admin legt an)', () => {
  const leer = hinweise.kalenderLeerzustand({ anzahl: 0, gesamt: 0, admin: true })
  assert.equal(leer.leer, true)
  assert.equal(leer.ziel, '#/kalender/verwalten')
  assert.equal(leer.zielText, 'Kalender anlegen')
  // Kalender existieren, sind aber nicht freigegeben → Rechte, nicht Einrichtung.
  const fremd = hinweise.kalenderLeerzustand({ anzahl: 0, gesamt: 3, admin: true })
  assert.equal(fremd.leer, false)
  assert.equal(fremd.titel, 'Keine Kalender freigegeben')
  // Sichtbare Kalender → gar kein Leerzustand.
  assert.equal(hinweise.kalenderLeerzustand({ anzahl: 2, gesamt: 2, admin: true }).zeigen, false)
})

// ── Gemeinsamer Statusabruf ────────────────────────────────────────────────

test('EIN Statusabruf für alle Stellen; Fehler werden still übergangen', async () => {
  hinweise.setzeStatusStand(null)
  zaehler.status = 0
  antwortStatus = status()
  const a = await hinweise.statusLaden()
  const b = await hinweise.statusLaden()
  assert.equal(zaehler.status, 1, 'zweiter Aufruf muss aus dem Stand kommen')
  assert.equal(a, b)
  assert.equal(a.offen_anzahl, 3)

  // Fehler → Stand bleibt null, keine Ausnahme (Seite läuft weiter).
  hinweise.setzeStatusStand(null)
  zaehler.status = 0
  antwortStatus = new Error('403')
  assert.equal(await hinweise.statusLaden({ neu: true }), null)
  assert.equal(zaehler.status, 1)
  antwortStatus = status()
})

test('„Später erinnern“ übernimmt das Datum des Servers in den Stand', async () => {
  hinweise.setzeStatusStand(status())
  zaehler.erinnern = 0
  zaehler.tage = []
  antwortErinnern = { erinnerung_ab: '2026-11-07', tage: 7 }
  const bis = await hinweise.spaeterErinnern(7, new Date(2026, 9, 31))
  assert.equal(bis, '2026-11-07')
  assert.equal(zaehler.erinnern, 1)
  assert.deepEqual(zaehler.tage, [7])
  assert.equal(hinweise.statusStand.value.erinnerung_ab, '2026-11-07')

  // Fehler → die Karte bleibt stehen (der Hinweis ist wichtiger).
  antwortErinnern = new Error('Zeitüberschreitung')
  assert.equal(await hinweise.spaeterErinnern(7), '')
})

// ── Wächter: CSS-SSOT, vorhandene Wege, Menüeintrag ────────────────────────

const NEUE_DATEIEN = [
  'frontend/src/diakonos/components/einrichtung/EinrichtungsKarte.vue',
  'frontend/src/diakonos/components/einrichtung/EinrichtungsLeiste.vue',
  'frontend/src/diakonos/components/einrichtung/LogoMarke.vue',
  'frontend/src/diakonos/components/einrichtung/AnmeldeMarke.vue',
  'frontend/src/diakonos/components/einrichtung/MitgliederLeerzustand.vue',
]

test('CSS-SSOT: keine festen Farben, Schriften oder Radius-Zahlen in den neuen Dateien', () => {
  const farbe = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/
  const schrift = /font(?:-family)?(\s*):(\s+)(?!inherit)/
  const radius = /border-radius\s*:\s*\d+(?:\.\d+)?px/g
  for (const datei of NEUE_DATEIEN) {
    const text = lies(datei)
    assert.doesNotMatch(text, farbe, `${datei}: fester Farbwert`)
    assert.doesNotMatch(text, schrift, `${datei}: feste Schriftfamilie`)
    assert.deepEqual([...text.matchAll(radius)].map((m) => m[0].trim()), [], `${datei}: fester Radius`)
  }
})

test('die Logik trägt keine CSS-Werte (wie einrichtung.mjs)', () => {
  const text = lies('frontend/src/diakonos/composables/einrichtungsHinweise.mjs')
  assert.doesNotMatch(text, /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/)
  assert.doesNotMatch(text, /border-radius/)
})

test('die Marke liefert Logo ODER Monogramm (Entwurf 04: „Ohne Logo … Monogramm“)', () => {
  // Logo hinterlegt: die Server-Adresse wird UNVERÄNDERT durchgereicht.
  const mitLogo = hinweise.markenDaten({
    logo_url: '/diakronos/gemeinde/logo?v=abc123',
    logo_vorhanden: true,
    kurzname: 'Musterstadt',
    gemeindename: 'Ev. Gemeinde Musterstadt',
  })
  assert.equal(mitLogo.logo, '/diakronos/gemeinde/logo?v=abc123')
  assert.equal(mitLogo.buchstabe, 'M')
  // Kein Logo: Monogramm, Kurzname vor Gemeindename.
  const ohneLogo = hinweise.markenDaten({ gemeindename: 'Ökumene Nord', logo_vorhanden: false })
  assert.equal(ohneLogo.logo, null)
  assert.equal(ohneLogo.buchstabe, 'O')
  // Gar nichts: der Produktbuchstabe, kein leeres Kästchen.
  assert.deepEqual(hinweise.markenDaten({}), { logo: null, buchstabe: 'D' })
  assert.deepEqual(hinweise.markenDaten(), { logo: null, buchstabe: 'D' })
})

test('das Logo wird nur per <img> eingebunden (SVG-Schutz aus ON-2)', () => {
  const marke = lies('frontend/src/diakonos/components/einrichtung/LogoMarke.vue')
  assert.match(marke, /:src="quelle"/)
  assert.match(marke, /logoQuelle|quelle/)
  // Kein v-html irgendwo in der Nähe des Logos.
  assert.doesNotMatch(marke, /v-html/)
})

test('Leerzustand benutzt die VORHANDENEN Wege (Import-Reiter, Anlege-Dialog)', () => {
  const leer = lies('frontend/src/diakonos/components/einrichtung/MitgliederLeerzustand.vue')
  assert.match(leer, /IMPORT_ROUTE|#\/mitglieder\/import/)
  assert.match(leer, /\$emit\('anlegen'\)/)
  // Kein zweiter Import- oder Anlege-Weg.
  assert.doesNotMatch(leer, /apiCall\(/)
})

test('Karte der Übersicht fragt den Status ab und bietet „Später erinnern“', () => {
  const karte = lies('frontend/src/diakonos/components/einrichtung/EinrichtungsKarte.vue')
  assert.match(karte, /statusLaden/)
  assert.match(karte, /spaeterErinnern/)
  assert.match(karte, /kartenZeilen|karteTitelMitZahl/)
  assert.match(karte, /fortschrittAnteil/)
  // Sammel-Ziel ist die Einstellungsseite, NICHT ein zweiter Assistent.
  assert.match(karte, /EINSTELLUNGEN_ROUTE/)
  assert.doesNotMatch(karte, /#\/einrichtung/)
})

test('Einstellungen → Gemeinde pflegt die ON-2-Felder (Nachtrag 2026-11-03)', () => {
  const gemeinde = lies('frontend/src/diakonos/pages/einstellungen/Gemeinde.vue')
  for (const feld of ['kurzname', 'strasse', 'plz', 'ort', 'telefon', 'website']) {
    assert.match(gemeinde, new RegExp(`v-model="${feld}"`), `Feld ${feld} fehlt`)
  }
  // Logo: Vorschau + Hochladen/Entfernen über die vorhandenen ON-2-Endpunkte.
  assert.match(gemeinde, /logoHochladen/)
  assert.match(gemeinde, /logoEntfernen/)
  assert.match(gemeinde, /LogoMarke/)
  // Zeitzone nur Anzeige.
  assert.match(gemeinde, /zeitzone/)
  assert.doesNotMatch(gemeinde, /gemeinde_setze_zeitzone/)
  // Gemeinsame Bausteine statt Kopie: Prüfung und Logo-Vorprüfung kommen aus
  // `einrichtungAssistent.mjs`.
  const composable = lies('frontend/src/diakonos/composables/useGemeinde.js')
  assert.match(composable, /pruefeSchritt/)
  assert.match(composable, /logoDateiFehler/)
  assert.match(composable, /gemeinde_logo_hochladen/)
  assert.match(composable, /gemeinde_logo_entfernen/)
})

test('die „Einrichten“-Ziele sind Einstellungs-Unterseiten bzw. Listen', () => {
  const texte = lies('frontend/src/diakonos/composables/einrichtungsHinweise.mjs')
  assert.match(texte, /MAILVERSAND_ROUTE = '#\/einstellungen\/mailversand'/)
  assert.match(texte, /GEMEINDE_ROUTE = '#\/einstellungen\/gemeinde'/)
  assert.match(texte, /EINSTELLUNGEN_ROUTE = '#\/einstellungen'/)
  assert.match(texte, /KALENDER_VERWALTUNG_ROUTE = '#\/kalender\/verwalten'/)
  // Die Leisten der Einstellungen zielen auf ihre eigene Seite.
  assert.equal(hinweise.hinweisFuer(status(), 'mailversand', ADMIN, TAG).ziel,
    '#/einstellungen/mailversand')
  assert.equal(hinweise.hinweisFuer(status(), 'gemeinde', ADMIN, TAG).ziel,
    '#/einstellungen/gemeinde')
})

test('Einstellungen führen NICHT auf einen eigenen Abschnitt „Einrichtung“', () => {
  // Nachtrag Orchestrator 2026-11-03 (verbindlich): kein Unterpunkt
  // „Einrichtung“ in den Einstellungen, kein Link auf `#/einrichtung`.
  const seite = lies('frontend/src/diakonos/pages/Einstellungen.vue')
  assert.doesNotMatch(seite, /href: '#\/einrichtung'/)
  assert.doesNotMatch(seite, /label: 'Einrichtung'/)
  assert.doesNotMatch(seite, /Checkliste\.vue/)
})
