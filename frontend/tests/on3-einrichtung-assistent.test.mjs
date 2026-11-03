/**
 * ON-3 — Einrichtungs-Assistent: Schrittlogik, Fortsetzen, Überspringen.
 *
 * WARUM DIESER TEST DIE LOGIK AUSFÜHRT UND NICHT NUR DEN QUELLTEXT LIEST
 * Ein Assistent kann in jeder Ansicht richtig aussehen und trotzdem falsch
 * laufen: „Zurück“ auf dem ersten Schritt, „Überspringen“ zwei Schritte weit,
 * ein Wiedereinstieg beim falschen Schritt oder ein „Weiter“, das die
 * Anschrift überschreibt, weil der Schritt sie nicht anzeigt (der Server
 * LÖSCHT leere Felder, ON2-VERTRAG Abschnitt 1). Alles davon ist im Browser
 * still. Deshalb prüft dieser Test das Modul, das die Seite WIRKLICH benutzt
 * (`src/diakonos/composables/einrichtungAssistent.mjs`) — keine Nachbildung.
 *
 * Zweiter Teil (Wächter): die neuen .vue-Dateien tragen keinen festen Farb-,
 * Schrift- oder Radiuswert (CSS-SSOT), der Haken sitzt in den Kreisen mittig
 * (ON-3/W5), und jede Rolle im Schritt hat eine Fehlerkennzeichnung
 * (aria-describedby über DkField).
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (`node --test`).
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

import {
  SCHRITTE,
  SCHRITT_ANZAHL,
  naechsterSchritt,
  schrittIndex,
  schrittListe,
  schrittText,
  segmentAnteil,
  startSchritt,
  hatZurueck,
  pruefeSchritt,
  speicherRumpf,
  zeitzoneAnzeige,
  zustandLabel,
  logoDateiFehler,
  logoVorschau,
  vorherigerSchritt,
} from '../src/diakonos/composables/einrichtungAssistent.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))

/**
 * Datei aus dem Repo ODER aus dem Image-Frontend-Stage lesen (Regel 13).
 *
 * Die beiden Lagen sind verschieden: im Repo liegt dieser Test unter
 * `<wurzel>/frontend/tests/`, im Frontend-Stage des Images unter
 * `<wurzel>/tests/` (dort ist `frontend/` der Arbeitsordner). Deshalb wird
 * stufenweise nach oben gelaufen und in JEDER Stufe BEIDE Formen probiert —
 * sonst finden die Prüfungen im Image nichts (Vorfall 30.10.: grün im
 * Worktree, rot im Image).
 */
function lies(relativ) {
  const ohneFrontend = relativ.replace(/^frontend\//, '')
  const formen = [relativ, ohneFrontend]
  const hoch = HIER.split('/')
  for (let stufe = 0; stufe < 3; stufe += 1) {
    for (const form of formen) {
      const pfad = [...hoch, form].join('/')
      if (existsSync(pfad)) return readFileSync(pfad, 'utf8')
    }
    if (hoch.length) hoch.pop()
  }
  throw new Error(`Datei nicht gefunden: ${relativ} (gesucht ab ${HIER})`)
}

/** Ein Status wie ihn `einrichtung.status` liefert. */
function status(zustaende = {}, extra = {}) {
  const schritte = SCHRITTE
    .filter((s) => s.schluessel !== 'fertig')
    .map((s) => ({ schluessel: s.schluessel, anzeige: s.anzeige, zustand: zustaende[s.schluessel] || 'offen' }))
  return {
    assistent_abgeschlossen: false,
    schritte,
    punkte: [],
    offen_anzahl: 0,
    erledigt_anzahl: 7,
    gesamt_anzahl: 7,
    erinnerung_ab: null,
    ...extra,
  }
}

// ── Schrittfolge ────────────────────────────────────────────────────────────

test('sechs Schritte in der Reihenfolge des Entwurfs (04–09, 14)', () => {
  assert.deepEqual(SCHRITTE.map((s) => s.schluessel),
    ['gemeinde', 'kontakt', 'mailversand', 'module', 'mitglieder_kalender', 'fertig'])
  assert.deepEqual(SCHRITTE.map((s) => s.anzeige), [
    'Gemeinde', 'Kontakt', 'Mailversand', 'Module', 'Mitglieder & Kalender', 'Fertig',
  ])
  assert.equal(SCHRITT_ANZAHL, 6)
})

test('„Schritt n von 6“ und der Segmentanteil folgen dem Entwurf', () => {
  assert.equal(schrittText('gemeinde'), 'Schritt 1 von 6')
  assert.equal(schrittText('fertig'), 'Schritt 6 von 6')
  // Entwurf 14: 58 von 350 px auf Schritt 1 → ein Sechstel.
  assert.equal(Math.round(segmentAnteil('gemeinde') * 350), 58)
  assert.equal(segmentAnteil('fertig'), 1)
})

test('Weiter/Zurück bleiben in der Kette, „Fertig“ hat kein Weiter', () => {
  assert.equal(naechsterSchritt('gemeinde'), 'kontakt')
  assert.equal(naechsterSchritt('mitglieder_kalender'), 'fertig')
  assert.equal(naechsterSchritt('fertig'), null)
  assert.equal(vorherigerSchritt('gemeinde'), null)
  assert.equal(vorherigerSchritt('kontakt'), 'gemeinde')
  assert.equal(vorherigerSchritt('fertig'), 'mitglieder_kalender')
  // W5: „Zurück“ darf auf dem ersten Schritt nicht angeboten werden.
  assert.equal(hatZurueck('gemeinde'), false)
  assert.equal(hatZurueck('kontakt'), true)
})

// ── Leiste und Zustände ─────────────────────────────────────────────────────

test('die Leiste zeigt fehlende Server-Schritte als offen, nie als erledigt', () => {
  const liste = schrittListe({ schritte: [{ schluessel: 'gemeinde', zustand: 'erledigt' }] })
  const nach = Object.fromEntries(liste.map((s) => [s.schluessel, s.zustand]))
  assert.equal(nach.gemeinde, 'erledigt')
  assert.equal(nach.kontakt, 'offen')
  assert.equal(nach.mitglieder_kalender, 'offen')
  assert.equal(nach.fertig, 'offen')
})

test('ein unbekannter Zustand gilt als offen (keine falsche Auskunft)', () => {
  const liste = schrittListe({ schritte: [{ schluessel: 'kontakt', zustand: 'quatsch' }] })
  assert.equal(liste.find((s) => s.schluessel === 'kontakt').zustand, 'offen')
})

test('übersprungene Schritte tragen „Übersprungen“, erledigte nicht', () => {
  const liste = schrittListe(status({ mailversand: 'uebersprungen', gemeinde: 'erledigt' }))
  assert.equal(zustandLabel(liste.find((s) => s.schluessel === 'mailversand').zustand), 'Übersprungen')
  assert.equal(zustandLabel(liste.find((s) => s.schluessel === 'gemeinde').zustand), '')
})

test('„Fertig“ ist erst mit abgeschlossenem Assistenten erledigt', () => {
  assert.equal(schrittListe(status({}, { assistent_abgeschlossen: true })).at(-1).zustand, 'erledigt')
  assert.equal(schrittListe(status()).at(-1).zustand, 'offen')
})

// ── Wiedereinstieg (W3/W4) ──────────────────────────────────────────────────

test('Wiedereinstieg setzt beim ERSTEN offenen Schritt fort', () => {
  assert.equal(startSchritt(status()), 'gemeinde')
  assert.equal(startSchritt(status({ gemeinde: 'erledigt' })), 'kontakt')
  assert.equal(startSchritt(status({ gemeinde: 'erledigt', kontakt: 'erledigt' })), 'mailversand')
})

test('übersprungen zählt als offen — der Wiedereinstieg holt den Schritt zurück', () => {
  // Bewusst: „übersprungen“ heisst, die Entscheidung ist offen (ON-2b/F2).
  assert.equal(startSchritt(status({ gemeinde: 'erledigt', kontakt: 'uebersprungen' })), 'kontakt')
})

test('alles erledigt oder abgeschlossen → Fertig-Übersicht (W4)', () => {
  const alle = status({ gemeinde: 'erledigt', kontakt: 'erledigt', mailversand: 'erledigt',
    module: 'erledigt', mitglieder_kalender: 'erledigt' })
  assert.equal(startSchritt(alle), 'fertig')
  assert.equal(startSchritt(status({}, { assistent_abgeschlossen: true })), 'fertig')
  // Ein abgeschlossener Assistent bleibt auch mit offenen Schritten bei Fertig.
  assert.equal(startSchritt(status({ gemeinde: 'offen' }, { assistent_abgeschlossen: true })), 'fertig')
  // Ohne Status (Ladefehler) beginnt der Assistent vorn.
  assert.equal(startSchritt(null), 'gemeinde')
  void schrittIndex
})

// ── Prüfung und Speicherrumpf ───────────────────────────────────────────────

test('Gemeindename ist Pflicht, Kurzname hat 40 Zeichen', () => {
  assert.match(pruefeSchritt('gemeinde', {}).gemeindename, /Gemeindenamen/)
  assert.deepEqual(pruefeSchritt('gemeinde', { gemeindename: 'Ev. Gemeinde Musterstadt' }), {})
  assert.match(pruefeSchritt('gemeinde', { gemeindename: 'x', kurzname: 'a'.repeat(41) }).kurzname, /zu lang/)
})

test('Kontakt: PLZ nur Ziffern, Website nur http(s), E-Mail plausibel', () => {
  assert.match(pruefeSchritt('kontakt', { plz: '74A72' }).plz, /Ziffern/)
  assert.deepEqual(pruefeSchritt('kontakt', { plz: '74072' }), {})
  assert.match(pruefeSchritt('kontakt', { website: 'gemeinde.example' }).website, /http/)
  assert.deepEqual(pruefeSchritt('kontakt', { website: 'https://gemeinde.example' }), {})
  assert.match(pruefeSchritt('kontakt', { kontakt_email: 'keine-adresse' }).kontakt_email, /E-Mail/)
})

test('der Speicherrumpf enthält den VOLLSTÄNDIGEN Satz (der Server löscht Leeres)', () => {
  const geladen = {
    gemeindename: 'Alt', kontakt_email: 'buero@example.org', oeffentliche_adresse: '',
    willkommenstext: 'Hallo', kurzname: 'Alt', strasse: 'Kirchplatz 1', plz: '74072',
    ort: 'Heilbronn', telefon: '+49 1', website: 'https://example.org',
  }
  // Schritt „Gemeinde“ speichert Name/Kurzname — die Anschrift darf NICHT
  // verloren gehen, nur weil dieser Schritt sie nicht zeigt.
  const rumpf = speicherRumpf('gemeinde', geladen, { gemeindename: 'Neu', kurzname: 'N' })
  assert.equal(rumpf.gemeindename, 'Neu')
  assert.equal(rumpf.kurzname, 'N')
  assert.equal(rumpf.strasse, 'Kirchplatz 1')
  assert.equal(rumpf.plz, '74072')
  assert.equal(rumpf.ort, 'Heilbronn')
  assert.equal(rumpf.kontakt_email, 'buero@example.org')
  assert.equal(rumpf.willkommenstext, 'Hallo')
  // Die Zeitzone ist KEIN Parameter (nur Anzeige, ON2-VERTRAG).
  assert.equal('zeitzone' in rumpf, false)
})

test('Schritt „Kontakt“ überschreibt nur seine Felder', () => {
  const rumpf = speicherRumpf('kontakt', { gemeindename: 'G', strasse: 'Alt 1', ort: 'A' },
    { strasse: 'Neu 2', plz: '74072' })
  assert.equal(rumpf.gemeindename, 'G')
  assert.equal(rumpf.strasse, 'Neu 2')
  assert.equal(rumpf.plz, '74072')
  assert.equal(rumpf.ort, 'A')
})

// ── Zeitzone (nur Anzeige) ──────────────────────────────────────────────────

test('die Zeitzone wird angezeigt, nie geschrieben', () => {
  const text = zeitzoneAnzeige('Europe/Berlin')
  assert.match(text, /^Europe\/Berlin/)
  assert.equal(zeitzoneAnzeige(''), '')
  assert.equal(zeitzoneAnzeige('Nirgendwo/Zone'), 'Nirgendwo/Zone')
})

// ── Logo ────────────────────────────────────────────────────────────────────

test('Logo-Datei wird vor dem Hochladen geprüft (Typ und 2 MB)', () => {
  assert.match(logoDateiFehler({ name: 'logo.exe', size: 10 }), /Dateityp/)
  assert.match(logoDateiFehler({ name: 'logo.png', size: 3 * 1024 * 1024 }), /2 MB/)
  assert.equal(logoDateiFehler({ name: 'logo.svg', size: 1024 }), '')
  assert.equal(logoDateiFehler({ name: 'wappen.JPEG', size: 1024 }), '')
})

test('die Logo-Vorschau nutzt die Serveradresse unverändert', () => {
  assert.equal(logoVorschau({ logo_url: '/diakronos/gemeinde/logo?v=abc', logo_vorhanden: true }),
    '/diakronos/gemeinde/logo?v=abc')
  assert.equal(logoVorschau({ logo_url: '/diakronos/gemeinde/logo', logo_vorhanden: false }), null)
  assert.equal(logoVorschau({}), null)
})

// ── Wächter: CSS-SSOT und Barrierefreiheit der neuen Dateien ───────────────

const NEUE_DATEIEN = [
  'frontend/src/diakonos/pages/einrichtung/Assistent.vue',
  'frontend/src/diakonos/components/einrichtung/AssistentSymbol.vue',
  'frontend/src/diakonos/components/einrichtung/AssistentSchritte.vue',
  'frontend/src/diakonos/components/einrichtung/SchrittGemeinde.vue',
  'frontend/src/diakonos/components/einrichtung/SchrittKontakt.vue',
  'frontend/src/diakonos/components/einrichtung/SchrittMailversand.vue',
  'frontend/src/diakonos/components/einrichtung/SchrittModule.vue',
  'frontend/src/diakonos/components/einrichtung/SchrittMitgliederKalender.vue',
  'frontend/src/diakonos/components/einrichtung/SchrittFertig.vue',
]

test('CSS-SSOT: keine festen Farben, Schriften oder Radius-Zahlen in den neuen Dateien', () => {
  const farbe = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/
  // `font: inherit` / `font-family: inherit` ERBEN die Schrift — das ist die
  // richtige Lösung, keine zweite Wahrheit. Verboten ist eine NAMENSANGABE;
  // deshalb muss auf `inherit` ein Trenner folgen (`;` oder Zeilenende).
  // `(\s+)` wird KONSUMIERT und die Prüfung beginnt danach — so steht der
  // Blick nicht vor dem trennenden Leerzeichen (sonst meckert er über
  // `inherit` selbst, weil `\s*` im Blickfeld zurücklaufen kann).
  const schrift = /font(?:-family)?(\s*):(\s+)(?!inherit)/
  // `50%` ist ein KREIS (Kreisform), kein Radius-Maß — genau wie
  // `var(--badge-r)` (999px) für die Pille. Verboten sind Pixel-Zahlen.
  const radius = /border-radius\s*:\s*\d+(?:\.\d+)?px/g
  for (const datei of NEUE_DATEIEN) {
    const text = lies(datei)
    assert.doesNotMatch(text, farbe, `${datei}: fester Farbwert`)
    assert.doesNotMatch(text, schrift, `${datei}: feste Schriftfamilie`)
    const treffer = [...text.matchAll(radius)].map((m) => m[0].trim())
    assert.deepEqual(treffer, [], `${datei}: fester Radius`)
  }
})

test('die neue Logik traegt keine CSS-Variablen oder Farben (wie einrichtung.mjs)', () => {
  const text = lies('frontend/src/diakonos/composables/einrichtungAssistent.mjs')
  assert.doesNotMatch(text, /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/)
  assert.doesNotMatch(text, /var\(--/)
})

test('Häkchen in den Kreisen sind mittig gesetzt (ON-3/W5, Entwurf hatte Versatz)', () => {
  const schritte = lies('frontend/src/diakonos/components/einrichtung/AssistentSchritte.vue')
  assert.match(schritte, /place-items:\s*center/, 'Schrittkreis ohne place-items: center')
  const fertig = lies('frontend/src/diakonos/components/einrichtung/SchrittFertig.vue')
  assert.match(fertig, /place-items:\s*center/, 'Fertig-Kreis ohne place-items: center')
  // Kein von Hand gerechneter Versatz mehr (kein negativer Rand/translate am Symbol).
  assert.doesNotMatch(fertig, /translateY\((?!1px)/, 'Symbol wird verschoben statt zentriert')
})

test('Pflichtfeld und Fehlertexte sind an Felder gebunden (W5)', () => {
  const gemeinde = lies('frontend/src/diakonos/components/einrichtung/SchrittGemeinde.vue')
  assert.match(gemeinde, /label="Gemeindename"\s+required/, 'Gemeindename ohne Pflichtkennzeichnung')
  assert.match(gemeinde, /:aria-describedby="ariaDescribedby"/, 'Gemeindename ohne aria-describedby')
  assert.match(gemeinde, /:aria-invalid="ariaInvalid \|\| undefined"/, 'Gemeindename ohne aria-invalid')
  const kontakt = lies('frontend/src/diakonos/components/einrichtung/SchrittKontakt.vue')
  assert.match(kontakt, /:aria-describedby="ariaDescribedby"/, 'Kontaktfelder ohne aria-describedby')
})

test('der Einrichtungs-Schritt „Mitglieder & Kalender“ benutzt die VORHANDENEN Wege', () => {
  const seite = lies('frontend/src/diakonos/pages/einrichtung/Assistent.vue')
  assert.match(seite, /#\/mitglieder\/import/, 'kein Verweis auf den vorhandenen Import')
  assert.match(seite, /#\/mitglieder\/liste/, 'kein Verweis auf die vorhandene Mitgliederliste')
  const schritt = lies('frontend/src/diakonos/components/einrichtung/SchrittMitgliederKalender.vue')
  assert.match(schritt, /#\/gruppen/, 'kein Verweis auf die Gruppenseite')
})

test('die Module des Schritts kommen aus dem SERVER (keine zweite Aufzählung)', () => {
  const schritt = lies('frontend/src/diakonos/components/einrichtung/SchrittModule.vue')
  assert.match(schritt, /props\.module|module\.value|module\b/, 'Modulliste fehlt')
  assert.doesNotMatch(schritt, /schluessel:\s*'(kronos|diakonos|psalmos)'/, 'Module im Browser fest aufgezählt')
  // Der Satz aus dem Entwurf steht am Schlüssel — Wortlaut Frame 07.
  assert.match(schritt, /Gottesdienste, Termine und Räume/, 'Sat des Entwurfs fehlt')
})
