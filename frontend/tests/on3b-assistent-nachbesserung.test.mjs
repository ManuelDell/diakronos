/**
 * ON-3b — Nachbesserung des Einrichtungs-Assistenten (Opus-Review ON-3).
 *
 * Vier Befunde, vier Prüfungen. Jeder Befund war im Browser STILL: die Seite
 * sah richtig aus, tat aber etwas anderes als sie sagte.
 *
 *   N1  „Speichern und später fortsetzen“ speicherte nichts — ein Klick (oder
 *       ein versehentliches Neuladen der Übersicht) verwarf alle Eingaben.
 *       Jetzt läuft ein echter Speichervorgang, OHNE den Schritt als erledigt
 *       zu markieren.
 *   N2  Der Fertig-Schirm sagte vor „Zur Übersicht“ „Die Ersteinrichtung ist
 *       abgeschlossen.“, auch wenn laut Checkliste Punkte offen waren.
 *   N3  Der Hinweis in Schritt 5 („Der Schritt bleibt offen, bis Mitglieder
 *       angelegt sind“) widersprach dem Verhalten: „Weiter“ setzt den Schritt
 *       auf erledigt.
 *   N4  Der Assistent lief im App-Gerüst (Seitenleiste + App-Kopfzeile +
 *       untere Leiste) statt im Vollbild des Entwurfs 04/09; am Handy verdeckte
 *       die untere Leiste den Knopf „Zur Übersicht“ der Fertig-Seite.
 *
 * Der Test führt den ECHTEN Code aus (`useEinrichtungsAssistent.js`) über
 * data:-URLs, damit die Vue-/API-Importe nicht aufgelöst werden müssen
 * (Muster aus p2-4-benachrichtigungen.test.mjs). Die API-Aufrufe werden
 * aufgezeichnet — geprüft wird, WAS gesendet wird, nicht nur dass etwas
 * gesendet wurde.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (`node --test`).
 * Der Test liest NUR Dateien unter `frontend/` (Regel 13).
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { test } from 'node:test'

const HIER = dirname(fileURLToPath(import.meta.url))

/**
 * Datei aus dem Repo ODER aus dem Image-Frontend-Stage lesen (Regel 13).
 * Im Repo liegt dieser Test unter `<wurzel>/frontend/tests/`, im Frontend-Stage
 * des Images unter `<wurzel>/tests/`. Deshalb stufenweise nach oben und in
 * jeder Stufe beide Formen probieren — sonst findet der Test im Image nichts.
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

/** URL einer Datei, die oben gefunden wurde (für echte Importe). */
function dateiUrl(relativ) {
  const ohneFrontend = relativ.replace(/^frontend\//, '')
  const formen = [relativ, ohneFrontend]
  const hoch = HIER.split('/')
  for (let stufe = 0; stufe < 3; stufe += 1) {
    for (const form of formen) {
      const pfad = [...hoch, form].join('/')
      if (existsSync(pfad)) return pathToFileURL(pfad).href
    }
    if (hoch.length) hoch.pop()
  }
  throw new Error(`Datei nicht gefunden: ${relativ}`)
}

// ── Das Assistenten-Modul mit aufgezeichneten API-Aufrufen laden ────────────

/**
 * Lädt `composables/useEinrichtungsAssistent.js` ausführbar.
 *
 * `vue` wird durch kleine Attrappen ersetzt (ref/reactive/computed) — mehr
 * braucht das Modul nicht. `apiCall` zeichnet auf und antwortet mit einem
 * festen Stand; `apiAntwortPruefen` wird nicht benutzt (nur der Logo-Weg).
 *
 * WICHTIG — der Modulzustand ist ABSICHTLICH modulweit (ON-3): ein zweiter
 * `import` derselben data:-URL liefert die CACHE-KOPIE, inklusive der Eingaben
 * des vorigen Tests. Deshalb hängt an der URL ein Zähler und `setzeZurueck`
 * wird am Anfang gerufen: jeder Test startet mit leeren Feldern.
 */
let ladeZaehler = 0
async function ladeModul(antworten = {}) {
  const aufrufe = []
  globalThis.__on3bApiCall = async (methode, argumente) => {
    aufrufe.push({ methode, argumente })
    const antwort = antworten[methode]
    return antwort === undefined ? {} : antwort
  }
  globalThis.__on3bApiAntwort = async () => ({})

  let quelle = lies('frontend/src/diakonos/composables/useEinrichtungsAssistent.js')
  quelle = quelle.replace(
    "import { computed, reactive, ref } from 'vue'",
    'const ref = (v) => ({ value: v })\n'
      + 'const reactive = (o) => o\n'
      + 'const computed = (fn) => ({ get value() { return fn() } })',
  )
  quelle = quelle.replace(
    "import { apiCall, apiAntwortPruefen } from './useApi.js'",
    'const apiCall = globalThis.__on3bApiCall\nconst apiAntwortPruefen = globalThis.__on3bApiAntwort',
  )
  quelle = quelle.replace(
    /import \{ apiUrl \} from '\.\.\/\.\.\/shared\/basis\.js'/,
    "const apiUrl = globalThis.__on3bApiUrl || ((p) => p)",
  )
  // Die reine Logik bleibt die ECHTE Datei (keine Nachbildung).
  quelle = quelle.replace(
    /from '\.\/einrichtungAssistent\.mjs'/,
    `from '${dateiUrl('frontend/src/diakonos/composables/einrichtungAssistent.mjs')}'`,
  )
  globalThis.window = { __DIakonosBOOT: { csrf_token: '' } }
  ladeZaehler += 1
  const mod = await import('data:text/javascript;base64,'
    + Buffer.from(quelle).toString('base64') + `#on3b-${ladeZaehler}`)
  // Frischer Zustand: die Modulkonstanten sind modulweit (Vue-`ref`).
  mod.setzeAssistentZurueck()
  return { mod, aufrufe }
}

/** Ein Status wie ihn `einrichtung.status` liefert (zwei Punkte offen). */
function status(extra = {}) {
  const schritte = ['gemeinde', 'kontakt', 'mailversand', 'module', 'mitglieder_kalender']
    .map((schluessel) => ({ schluessel, anzeige: schluessel, zustand: 'offen' }))
  return {
    assistent_abgeschlossen: false,
    schritte,
    punkte: [
      { schluessel: 'logo', erledigt: false, titel: 'Logo', hinweis: 'fehlt', ziel: '#/einstellungen/gemeinde' },
      { schluessel: 'mitglieder', erledigt: false, titel: 'Mitglieder', hinweis: 'keine', ziel: '#/mitglieder/liste' },
    ],
    offen_anzahl: 2,
    erledigt_anzahl: 5,
    gesamt_anzahl: 7,
    erinnerung_ab: null,
    ...extra,
  }
}

// ── N1 · „Speichern und später fortsetzen“ speichert ───────────────────────

test('N1: „später fortsetzen“ speichert die Eingaben über gemeinde_speichern', async () => {
  const { mod, aufrufe } = await ladeModul({
    'diakronos.diakonos.api.einrichtung.status': status(),
    'diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen': {
      gemeindename: '', kurzname: '', strasse: '', plz: '', ort: '',
      kontakt_email: '', telefon: '', website: '', willkommenstext: '',
      oeffentliche_adresse: '',
    },
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  assert.equal(a.schritt.value, 'gemeinde')
  a.eingaben.gemeindename = 'Ev. Gemeinde Musterstadt'
  a.eingaben.kurzname = 'Musterstadt'

  const ok = await a.spaeterSichern()
  assert.equal(ok, true, 'spaeterSichern meldet keinen Erfolg')

  const speichern = aufrufe.filter((r) => r.methode.endsWith('gemeinde_speichern'))
  assert.equal(speichern.length, 1, 'gemeinde_speichern wurde nicht gerufen')
  assert.equal(speichern[0].argumente.gemeindename, 'Ev. Gemeinde Musterstadt')
  assert.equal(speichern[0].argumente.kurzname, 'Musterstadt')
  // Der VOLLSTÄNDIGE Satz — der Server löscht leere Felder (ON2-VERTRAG 1).
  for (const feld of ['strasse', 'plz', 'ort', 'kontakt_email', 'telefon', 'website']) {
    assert.equal(feld in speichern[0].argumente, true, `Feld ${feld} fehlt im Speicherrumpf`)
  }
})

test('N1: „später fortsetzen“ setzt den Schritt NICHT auf erledigt', async () => {
  const { mod, aufrufe } = await ladeModul({
    'diakronos.diakonos.api.einrichtung.status': status(),
    'diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen': { gemeindename: '' },
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  a.eingaben.gemeindename = 'Ev. Gemeinde Musterstadt'
  await a.spaeterSichern()

  assert.equal(aufrufe.some((r) => r.methode.endsWith('einrichtung.schritt_setzen')), false,
    'spaeterSichern hat den Prozessstand verändert (Schritt gilt danach als erledigt)')
  assert.equal(aufrufe.some((r) => r.methode.endsWith('einrichtung.abschliessen')), false,
    'spaeterSichern hat den Assistenten abgeschlossen')
  assert.equal(a.schritt.value, 'gemeinde', 'der Schritt ist weitergegangen statt offen zu bleiben')
})

test('N1: „später fortsetzen“ blockiert keinen halben Entwurf, prüft aber Grenzen', async () => {
  const { mod, aufrufe } = await ladeModul({
    'diakronos.diakonos.api.einrichtung.status': status(),
    'diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen': { gemeindename: '' },
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  // Nichts eingetippt: kein Schreibaufruf, aber auch kein Fehler.
  assert.equal(await a.spaeterSichern(), true, 'leerer Entwurf wird als Fehler gemeldet')
  assert.equal(aufrufe.filter((r) => r.methode.endsWith('gemeinde_speichern')).length, 0,
    'ohne Eingaben darf nichts geschrieben werden')

  // Unsinnige Werte werden am Feld gemeldet (Grenzen des Servers).
  a.eingaben.gemeindename = 'Ev. Gemeinde Musterstadt'
  a.eingaben.kurzname = 'x'.repeat(41)
  assert.equal(await a.spaeterSichern(), false, 'zu langer Kurzname wird nicht abgelehnt')
  assert.match(String(a.feldFehler.kurzname || ''), /zu lang/)
  assert.equal(a.schritt.value, 'gemeinde', 'nach einem Feldfehler darf die Seite nicht weitergehen')
})

test('N1: „später fortsetzen“ im Kontakt-Schritt sichert nur den Kontaktsatz', async () => {
  const { mod, aufrufe } = await ladeModul({
    'diakronos.diakonos.api.einrichtung.status': status(),
    'diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen': {
      gemeindename: 'Ev. Gemeinde Musterstadt', strasse: '', ort: '',
    },
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  a.geheZu('kontakt')
  a.eingaben.strasse = 'Kirchplatz 1'
  a.eingaben.ort = 'Heilbronn'
  assert.equal(await a.spaeterSichern(), true)
  const speichern = aufrufe.filter((r) => r.methode.endsWith('gemeinde_speichern'))
  assert.equal(speichern.length, 1)
  assert.equal(speichern[0].argumente.strasse, 'Kirchplatz 1')
  assert.equal(speichern[0].argumente.ort, 'Heilbronn')
  // Der Gemeindename aus dem geladenen Stand darf nicht verloren gehen.
  assert.equal(speichern[0].argumente.gemeindename, 'Ev. Gemeinde Musterstadt')
})

test('N1: die Seite ruft beim Klick wirklich spaeterSichern (kein reines Navigieren)', () => {
  const seite = lies('frontend/src/diakonos/pages/einrichtung/Assistent.vue')
  assert.match(seite, /spaeterSichern\s*\(\s*\)/, 'die Seite ruft spaeterSichern nicht auf')
  assert.match(seite, /async function spaeter\(\)[\s\S]{0,200}spaeterSichern\(\)/,
    'spaeter() speichert nicht vor dem Wechsel')
  assert.match(seite, /if \(!gesichert\) return/, 'ein Fehlschlag wird nicht abgefangen')
})

// ── N2 · Fertig-Seite nennt den echten Stand ───────────────────────────────

/** Die Unterzeilen-Logik der Fertig-Seite ausführen (SCRIPT-Block der Datei). */
async function fertigUnterzeile(propsWerte) {
  const quelle = lies('frontend/src/diakonos/components/einrichtung/SchrittFertig.vue')
  const skript = quelle.match(/<script setup>([\s\S]*?)<\/script>/)
  assert.ok(skript, 'SchrittFertig.vue hat keinen <script setup>-Block')
  const code = skript[1]
    .replace("import { computed } from 'vue'",
      'const computed = (fn) => fn()\n'
      + 'let props = globalThis.__on3bProps\n'
      + 'const defineProps = () => props\n'
      + 'const defineEmits = () => {}')
    .replace(/const props = defineProps\(\{[\s\S]*?\n\}\)/, '')
    .replace(/import DkButton from '[^']*DkButton\.vue'/, 'const DkButton = {}')
    .replace(/import AssistentSymbol from '[^']*AssistentSymbol\.vue'/, 'const AssistentSymbol = {}')
    .concat('\nglobalThis.__on3bUnterzeile = unterzeile\n')
  globalThis.__on3bProps = propsWerte
  ladeZaehler += 1
  const url = 'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
    + `#fertig-${ladeZaehler}`
  await import(url)
  return globalThis.__on3bUnterzeile
}

test('N2: vor dem Abschluss nennt die Unterzeile die offenen Punkte, nicht „abgeschlossen“', async () => {
  const text = await fertigUnterzeile({ offenAnzahl: 3, gesamtAnzahl: 7, abgeschlossen: false })
  assert.doesNotMatch(text, /Ersteinrichtung ist abgeschlossen/,
    'die Unterzeile behauptet weiterhin den Abschluss')
  assert.match(text, /3 Punkte sind noch offen/, 'die Zahl der offenen Punkte fehlt')
  assert.match(text, /lassen sich jederzeit nachholen/, 'der Entwurfssatz (Frame 09) fehlt')
})

test('N2: ein offener Punkt steht im Singular', async () => {
  const text = await fertigUnterzeile({ offenAnzahl: 1, gesamtAnzahl: 7, abgeschlossen: false })
  assert.match(text, /1 Punkt ist noch offen/, `Singular fehlt: ${text}`)
  assert.match(text, /lässt sich jederzeit nachholen/, `Singular des Verbs fehlt: ${text}`)
})

test('N2: ist alles erledigt, steht dort „Alles eingerichtet.“', async () => {
  const text = await fertigUnterzeile({ offenAnzahl: 0, gesamtAnzahl: 7, abgeschlossen: false })
  assert.equal(text, 'Alles eingerichtet.')
  const nachher = await fertigUnterzeile({ offenAnzahl: 0, gesamtAnzahl: 7, abgeschlossen: true })
  assert.equal(nachher, 'Alles eingerichtet.')
})

test('N2: nach dem Abschluss nennt die Unterzeile den Ort zum Nachholen', async () => {
  const text = await fertigUnterzeile({ offenAnzahl: 2, gesamtAnzahl: 7, abgeschlossen: true })
  assert.match(text, /2 Punkte sind noch offen/, 'die Zahl fehlt')
  assert.match(text, /Einstellungen → Einrichtung/, 'der Ort zum Nachholen fehlt')
})

// ── N3 · Hinweis in Schritt 5 stimmt mit dem Verhalten überein ─────────────

test('N3: der Hinweis behauptet nicht mehr, der Schritt bleibe offen', () => {
  const schritt = lies('frontend/src/diakonos/components/einrichtung/SchrittMitgliederKalender.vue')
  // Nur der SICHTBARE Text zählt (der Kommentar erklärt den alten Fehler).
  // Deshalb werden die HTML-Kommentare (`<!-- … -->`) vorher entfernt — sie
  // stehen auch INNERHALB der Vorlage.
  const vorlage = schritt
    .match(/<template>([\s\S]*?)<\/template>/)[1]
    .replace(/<!--[\s\S]*?-->/g, '')
  assert.doesNotMatch(vorlage, /Der Schritt bleibt offen/,
    'der falsche Hinweis steht weiterhin in der Vorlage')
  assert.match(vorlage, /Mitglieder/, 'der Hinweis nennt die Mitglieder nicht mehr')
  assert.match(vorlage, /Checklisten-Punkt/, 'der Hinweis nennt den Checklisten-Punkt nicht')
})

test('N3: „Weiter“ setzt den Schritt erledigt — genau das sagt der Hinweis', async () => {
  // Beweis für den Text: `weiter()` setzt `erledigt`, ohne die Mitgliederzahl
  // zu prüfen. Der Hinweis muss deshalb den Schritt und den Checklisten-Punkt
  // auseinanderhalten.
  const { mod, aufrufe } = await ladeModul({
    'diakronos.diakonos.api.einrichtung.status': status(),
    'diakronos.diakonos.api.gemeinde.gemeinde_get_einstellungen': { gemeindename: 'G' },
    'diakronos.diakonos.api.einrichtung.kalender_vorschlag_anlegen': {},
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  a.geheZu('mitglieder_kalender')
  a.mitgliederWahl.value = 'spaeter'
  assert.equal(await a.weiter(), true)
  const gesetzt = aufrufe.filter((r) => r.methode.endsWith('einrichtung.schritt_setzen'))
  assert.equal(gesetzt.length, 1)
  assert.deepEqual(gesetzt[0].argumente,
    { schluessel: 'mitglieder_kalender', zustand: 'erledigt' },
    'Weiter setzt den Schritt nicht auf erledigt — dann wäre der alte Hinweis richtig')
})

// ── N4 · Vollbild-Rahmen und nicht verdeckte Fußleiste ─────────────────────

test('N4: der App-Rahmen blendet Seitenleiste, Kopfzeile und untere Leiste im Assistenten aus', () => {
  const app = lies('frontend/src/diakonos/App.vue')
  assert.match(app, /const isVollbildMode = computed\(\(\) => currentHash\.value === '#\/einrichtung'\)/,
    'es gibt keine Vollbild-Erkennung für #/einrichtung')
  for (const baustein of ['AppSidebar', 'AppTopbar', 'AppBottomNav']) {
    assert.match(app, new RegExp(`<${baustein}\\s+v-if="!isVollbildMode"`),
      `${baustein} wird im Vollbild weiterhin gerendert`)
  }
  assert.match(app, /'dk-app--vollbild': isVollbildMode/, 'die Vollbild-Klasse am .dk-app fehlt')
  assert.match(app, /'dk-content--vollbild': isVollbildMode/, 'die Vollbild-Klasse am Inhalt fehlt')
})

test('N4: das Vollbild-Gerüst ist einspaltig und schenkt der Seite die volle Höhe', () => {
  const css = lies('frontend/src/diakonos/index.css')
  assert.match(css, /\.dk-app\.dk-app--vollbild\s*\{[^}]*grid-template-columns:\s*1fr/,
    'die Seitenleisten-Spalte bleibt im Vollbild bestehen')
  assert.match(css, /\.dk-content--vollbild\s*\{[^}]*padding:\s*0/,
    'der Innenabstand des App-Inhalts bleibt im Vollbild bestehen')
  assert.match(css, /\.dk-content--vollbild\s*\{[^}]*overflow:\s*hidden/,
    'der App-Inhalt scrollt weiter — die Fußleiste im Assistenten braucht eine feste Höhe')
})

test('N4: die Fußleiste des Assistenten verdeckt „Zur Übersicht“ nicht', () => {
  const seite = lies('frontend/src/diakonos/pages/einrichtung/Assistent.vue')
  // Der Hauptbereich hält unten Platz für die Fußleiste frei — am Desktop und
  // am Handy (eigene Token-Höhen, keine Zahlen).
  // UX1a2 (F1): Die Fußleisten-Höhe wird aus einem FREMDEN Token addiert.
  // Seit der eindeutigen Zuordnung ist das Desktop-Maß die 32-px-Stufe
  // (--sp-6), das Handy-Maß eine Stufe darunter (--sp-alt-20 / --sp-4).
  // Geprüft wird deshalb: irgendein Abstands-Token PLUS die Fußleisten-Höhe —
  // nicht ein bestimmter Token-Name (der hat sich in UX1a2 geändert).
  assert.match(seite, /padding:\s*var\(--sp-[1-8]\)[^;]*calc\(var\(--assistent-fuss\)[^;]*\)/,
    'dem Hauptbereich fehlt der Freiraum für die Fußleiste (Desktop)')
  assert.match(seite, /padding:\s*var\(--sp-[1-8]\)[^;]*calc\(var\(--assistent-fuss-mobil\)[^;]*\)/,
    'dem Hauptbereich fehlt der Freiraum für die Fußleiste (Mobil)')
  // Der Körper ist der Scrollbereich, nicht die Seite: sonst liegt die
  // Klebefußleiste über dem letzten Inhalt.
  assert.match(seite, /\.assistent-koerper\s*\{[^}]*overflow-y:\s*auto/, 'der Körper scrollt nicht')
  assert.match(seite, /\.assistent\s*\{[^}]*height:\s*100%/, 'der Assistent füllt die Höhe nicht')
})

// ── CSS-SSOT der geänderten Dateien ────────────────────────────────────────

test('CSS-SSOT: keine festen Farben, Schriften oder Radius-Zahlen in den geänderten Dateien', () => {
  const dateien = [
    'frontend/src/diakonos/components/einrichtung/SchrittFertig.vue',
    'frontend/src/diakonos/components/einrichtung/SchrittMitgliederKalender.vue',
    'frontend/src/diakonos/pages/einrichtung/Assistent.vue',
  ]
  const farbe = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/
  const schrift = /font(?:-family)?(\s*):(\s+)(?!inherit)/
  const radius = /border-radius\s*:\s*\d+(?:\.\d+)?px/g
  for (const datei of dateien) {
    const text = lies(datei)
    assert.doesNotMatch(text, farbe, `${datei}: fester Farbwert`)
    assert.doesNotMatch(text, schrift, `${datei}: feste Schriftfamilie`)
    assert.deepEqual([...text.matchAll(radius)].map((m) => m[0].trim()), [], `${datei}: fester Radius`)
  }
  // Die neuen Rahmen-Klassen in index.css arbeiten ebenfalls nur mit Tokens.
  const css = lies('frontend/src/diakonos/index.css')
  const block = css.match(/ON-3b \(N4\)[\s\S]*?\.dk-content--vollbild > \* \{[^}]*\}/)
  assert.ok(block, 'der Vollbild-Block in index.css fehlt')
  assert.doesNotMatch(block[0], farbe, 'index.css: fester Farbwert im Vollbild-Block')
})

// ── Orchestrator-Nachtrag: Ersteinrichtung ist kein Dauerzustand ───────────

const {
  EINRICHTUNG_GESEHEN,
  EINRICHTUNG_ROUTE,
  EINRICHTUNG_ZIEL_NACH_ABSCHLUSS,
  einrichtungGesehen,
  einrichtungsWeiterleitung,
  einrichtungSeiteErlaubt,
  merkeEinrichtungGesehen,
} = await import(dateiUrl('frontend/src/diakonos/einrichtungLeitung.mjs'))

/** Einfacher Speicher-Attrappen (sessionStorage-Form). */
function speicher() {
  const daten = new Map()
  return {
    getItem: (k) => (daten.has(k) ? daten.get(k) : null),
    setItem: (k, v) => daten.set(k, String(v)),
    removeItem: (k) => daten.delete(k),
  }
}

test('Nachtrag 1: offene Einrichtung führt den Admin beim Öffnen auf den Assistenten', () => {
  const ziel = einrichtungsWeiterleitung({
    pfad: '#/', hash: '#/', boot: { is_admin: true, einrichtung_offen: true }, gesehen: false,
  })
  assert.equal(ziel, EINRICHTUNG_ROUTE)
  // Auch von einer beliebigen anderen Seite aus.
  assert.equal(einrichtungsWeiterleitung({
    pfad: '#/kalender', hash: '#/kalender',
    boot: { is_admin: true, einrichtung_offen: true }, gesehen: false,
  }), EINRICHTUNG_ROUTE)
})

test('Nachtrag 1: „Speichern und später fortsetzen“ lässt ihn für die Sitzung raus', () => {
  const s = speicher()
  assert.equal(einrichtungGesehen(s), false)
  merkeEinrichtungGesehen(s)
  assert.equal(einrichtungGesehen(s), true)
  assert.equal(s.getItem(EINRICHTUNG_GESEHEN), '1')
  // Mit Merker: keine Leitung mehr — aber die Adresse selbst bleibt nutzbar.
  assert.equal(einrichtungsWeiterleitung({
    pfad: '#/', hash: '#/',
    boot: { is_admin: true, einrichtung_offen: true }, gesehen: true,
  }), null)
  assert.equal(einrichtungsWeiterleitung({
    pfad: EINRICHTUNG_ROUTE, hash: EINRICHTUNG_ROUTE,
    boot: { is_admin: true, einrichtung_offen: true }, gesehen: true,
  }), null, 'die Adresse des Assistenten darf sich nicht selbst weiterleiten')
})

test('Nachtrag 2: nach dem Abschluss gibt es #/einrichtung nicht mehr', () => {
  assert.equal(einrichtungsWeiterleitung({
    pfad: EINRICHTUNG_ROUTE, hash: EINRICHTUNG_ROUTE,
    boot: { is_admin: true, einrichtung_offen: false }, gesehen: false,
  }), EINRICHTUNG_ZIEL_NACH_ABSCHLUSS)
  assert.equal(EINRICHTUNG_ZIEL_NACH_ABSCHLUSS, '#/einstellungen')
  assert.equal(einrichtungSeiteErlaubt({ is_admin: true, einrichtung_offen: false }), false,
    'die Seite würde nach dem Abschluss weiter geladen')
  // Andere Seiten werden nicht angefasst.
  assert.equal(einrichtungsWeiterleitung({
    pfad: '#/einstellungen', hash: '#/einstellungen',
    boot: { is_admin: true, einrichtung_offen: false }, gesehen: false,
  }), null)
})

test('Nachtrag: nur Admin-Rollen werden geleitet', () => {
  for (const boot of [
    { is_admin: false, einrichtung_offen: true },
    { is_admin: false, einrichtung_offen: false },
    {},
  ]) {
    assert.equal(einrichtungsWeiterleitung({
      pfad: '#/', hash: '#/', boot, gesehen: false,
    }), null, `Nicht-Admin wurde geleitet: ${JSON.stringify(boot)}`)
  }
  // Ohne Admin ist die Seite auch nicht ladbar.
  assert.equal(einrichtungSeiteErlaubt({ is_admin: false, einrichtung_offen: true }), false)
})

test('Nachtrag: unbekannter Stand hält niemanden fest', () => {
  // `null`/fehlend = der Server sagt nichts → weder leiten noch sperren.
  assert.equal(einrichtungsWeiterleitung({
    pfad: '#/', hash: '#/', boot: { is_admin: true, einrichtung_offen: null }, gesehen: false,
  }), null)
  assert.equal(einrichtungsWeiterleitung({
    pfad: '#/', hash: '#/', boot: { is_admin: true }, gesehen: false,
  }), null)
  assert.equal(einrichtungSeiteErlaubt({ is_admin: true }), true)
})

test('Nachtrag 3: kein Menüpunkt „Einrichtung“ irgendwo in der App', () => {
  const menue = lies('frontend/src/diakonos/menue.js')
  assert.doesNotMatch(menue, /label:\s*'Einrichtung'/,
    'die Seitenleiste hat weiterhin einen Menüpunkt „Einrichtung“')
  assert.doesNotMatch(menue, /id:\s*'einrichtung'/,
    'der Menüeintrag „einrichtung“ existiert weiterhin')
  assert.doesNotMatch(menue, /href:\s*'#\/einrichtung'/, 'das Menü verlinkt weiterhin auf den Assistenten')
  // Die Seite selbst ist weiterhin als aktiver Einstellungs-Abschnitt erkannt
  // (der Assistent soll in der Leiste nicht als „nichts ausgewählt“ stehen).
  assert.match(menue, /'Einrichtung'/, 'der Seitennamen-Verweis fehlt (Menü-Markierung)')
})

test('Nachtrag: der Server liefert den Einrichtungs-Stand im Boot-Objekt (eine Quelle)', (t) => {
  // Im Image-Frontend-Stage liegt backend/ NICHT vor (Regel 13: dort wird nur
  // gebaut). Der Test prueft den Router immer; die Server-Seite prueft er nur,
  // wenn die Datei da ist — im Worktree und in der Backend-Suite.
  const router = lies('frontend/src/diakonos/router.js')
  assert.match(router, /leitung\.einrichtungsWeiterleitung\(\{/, 'der Router wendet die Regel nicht an')
  assert.match(router, /leitung\.einrichtungGesehen\(window\.sessionStorage\)/,
    'das „einmal pro Sitzung“ wird nicht berücksichtigt')
  assert.match(router, /leitung\.einrichtungSeiteErlaubt\(/,
    'die Seite wird nach dem Abschluss weiter geladen')
  assert.match(router, /from '\.\/einrichtungLeitung\.mjs'/, 'der Router bindet die Leitungsdatei nicht ein')
  assert.match(router, /einrichtung_offen|EINRICHTUNG_ROUTE/, 'der Stand wird im Router nicht benutzt')

  let spa = null
  try {
    spa = lies('backend/src/diakronos_app/spa.py')
  } catch {
    spa = null
  }
  if (spa === null) {
    t.diagnostic('backend/ liegt im Image-Frontend-Stage nicht vor — '
      + 'die Server-Seite prueft backend/tests/test_on3b_einrichtung_leitung.py')
    return
  }
  assert.match(spa, /"einrichtung_offen": _einrichtung_offen\(\)/,
    'das Boot-Objekt nennt den Einrichtungs-Stand nicht')
  assert.match(spa, /def _einrichtung_offen\(\) -> bool:/, 'die Hilfsfunktion fehlt')
  assert.match(spa, /zeile\.assistent_abgeschlossen/, 'der Stand wird nicht aus einrichtung_stand gelesen')
})

test('Nachtrag: die Regel steht in einer importfreien Datei (prüfbar ohne DOM)', () => {
  const quelle = lies('frontend/src/diakonos/einrichtungLeitung.mjs')
  assert.doesNotMatch(quelle, /^\s*import\s/m, 'die Leitungsregel hat Importe (nicht mehr ohne DOM prüfbar)')
  assert.doesNotMatch(quelle, /var\(--|#[0-9a-fA-F]{3,8}\b/, 'CSS-Werte in der Logik')
})

console.log('ON-3b Frontend: OK')
