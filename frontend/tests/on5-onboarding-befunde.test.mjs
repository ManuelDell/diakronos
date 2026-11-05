/**
 * ON-5 — Befunde aus dem Onboarding-Durchlauf (ON-E2E).
 *
 * DREI BEFUNDE, DREI PRÜFUNGEN. Alle drei waren im Browser STILL: die Seite
 * sah richtig aus, tat aber etwas anderes, als sie sagte.
 *
 *   E2-3  Der Kalender-Vorschlag im Schritt „Mitglieder & Kalender“ wurde
 *         nicht angelegt — `weiter()` fing den Fehler und setzte den Schritt
 *         trotzdem auf „erledigt“. Die Checkliste blieb danach stumm auf
 *         „Noch kein Kalender angelegt“.
 *   E2-5  Das Logo erschien in der Seitenleiste erst nach einem Neuladen
 *         (das Boot-Objekt ist ein Startwert).
 *   Klein Der Einstellungs-Abschnitt „Dev-Modus“ fragte
 *         `devmodus.api.uebersicht` auch bei AUSGESCHALTETEM Dev-Modus —
 *         der Server antwortet (richtig) mit 404, in der Konsole stand ein
 *         Fehler.
 *
 * Der Test führt den ECHTEN Code aus (`useEinrichtungsAssistent.js`) über
 * data:-URLs (Muster aus on3b-assistent-nachbesserung.test.mjs) und liest die
 * beiden .vue-Dateien als Text — es wird nichts nachgebaut.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (`node --test`).
 * Der Test liest NUR Dateien unter `frontend/` (Regel 13, keine COPY-Zeile).
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { test } from 'node:test'

const HIER = dirname(fileURLToPath(import.meta.url))

/**
 * Datei aus dem Repo ODER aus dem Image-Frontend-Stage lesen (Regel 13).
 * Im Repo liegt dieser Test unter `<wurzel>/frontend/tests/`, im
 * Frontend-Stage des Images unter `<wurzel>/tests/`.
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

let ladeZaehler = 0
async function ladeModul(antworten = {}, fehler = {}) {
  const aufrufe = []
  globalThis.__on5ApiCall = async (methode, argumente) => {
    aufrufe.push({ methode, argumente })
    if (fehler[methode]) throw fehler[methode]
    const antwort = antworten[methode]
    return antwort === undefined ? {} : antwort
  }
  // Der Multipart-Weg des Logos läuft über `apiAntwortPruefen` (echte Datei
  // `useApi.js`): sie liest den Rumpf und hängt `dkAntwort` an. Hier wird nur
  // der Sitzungs-/CSRF-Teil durchgereicht — mehr braucht der Upload nicht.
  globalThis.__on5ApiAntwort = async (antwort) => {
    const rumpf = await antwort.text()
    return JSON.parse(rumpf)
  }

  let quelle = lies('frontend/src/diakonos/composables/useEinrichtungsAssistent.js')
  quelle = quelle.replace(
    "import { computed, reactive, ref } from 'vue'",
    'const ref = (v) => ({ value: v })\n'
      + 'const reactive = (o) => o\n'
      + 'const computed = (fn) => ({ get value() { return fn() } })',
  )
  quelle = quelle.replace(
    "import { apiCall, apiAntwortPruefen } from './useApi.js'",
    'const apiCall = globalThis.__on5ApiCall\nconst apiAntwortPruefen = globalThis.__on5ApiAntwort',
  )
  quelle = quelle.replace(
    /import \{ apiUrl \} from '\.\.\/\.\.\/shared\/basis\.js'/,
    "const apiUrl = globalThis.__on5ApiUrl || ((p) => p)",
  )
  quelle = quelle.replace(
    /from '\.\/einrichtungAssistent\.mjs'/,
    `from '${dateiUrl('frontend/src/diakonos/composables/einrichtungAssistent.mjs')}'`,
  )
  // ON-5 (E2-5): das Marken-Modul ist inzwischen eine eigene, reine Datei
  // (auch von `useGemeinde` benutzt) — hier die ECHTE Datei laden.
  quelle = quelle.replace(
    /from '\.\/gemeindeMarke\.mjs'/,
    `from '${dateiUrl('frontend/src/diakonos/composables/gemeindeMarke.mjs')}'`,
  )
  // Boot-Objekt als Attrappe: hier wird geprüft, ob `merkeMarke` es mitzieht
  // UND das Ereignis für die Neuzeichnung meldet.
  globalThis.__on5Ereignisse = []
  globalThis.window = {
    __DIakonosBOOT: { csrf_token: '', logo_url: null },
    dispatchEvent: (ereignis) => globalThis.__on5Ereignisse.push(ereignis.type),
  }
  globalThis.__on5Boot = globalThis.window.__DIakonosBOOT
  ladeZaehler += 1
  const mod = await import('data:text/javascript;base64,'
    + Buffer.from(quelle).toString('base64') + `#on5-${ladeZaehler}`)
  mod.setzeAssistentZurueck()
  return { mod, aufrufe, boot: globalThis.__on5Boot }
}

/** Ein Status wie ihn `einrichtung.status` liefert. */
function status(extra = {}) {
  const schritte = ['gemeinde', 'kontakt', 'mailversand', 'module', 'mitglieder_kalender']
    .map((schluessel) => ({ schluessel, anzeige: schluessel, zustand: 'offen' }))
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

const EINRICHTUNG = 'diakronos.diakonos.api.einrichtung.'
const GEMEINDE = 'diakronos.diakonos.api.gemeinde.'

/** Assistent im Schritt „Mitglieder & Kalender“, beide Vorschläge angehakt. */
async function imKalenderSchritt(antworten, fehler) {
  const geladen = await ladeModul({
    [EINRICHTUNG + 'status']: status(),
    [GEMEINDE + 'gemeinde_get_einstellungen']: { gemeindename: 'Pruefhausen' },
    ...antworten,
  }, fehler)
  const a = geladen.mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  a.geheZu('mitglieder_kalender')
  a.mitgliederWahl.value = 'spaeter'
  return { ...geladen, a }
}

// ── E2-3 · Kalender-Vorschlag: „erledigt“ nur, wenn die Kalender da sind ────

test('E2-3: angelegte Kalender — der Schritt wird erledigt und es geht weiter', async () => {
  const { a, aufrufe } = await imKalenderSchritt({
    [EINRICHTUNG + 'kalender_vorschlag_anlegen']: {
      message: { angelegt: ['Gottesdienste', 'Gemeindekalender'], uebersprungen: [] },
    },
  })
  assert.equal(await a.weiter(), true)
  const anlegen = aufrufe.filter((r) => r.methode === EINRICHTUNG + 'kalender_vorschlag_anlegen')
  assert.equal(anlegen.length, 1, 'der Vorschlag wurde nicht gesendet')
  assert.deepEqual(anlegen[0].argumente.namen, ['Gottesdienste', 'Gemeindekalender'],
    'die Auswahl geht nicht vollständig an den Server')
  assert.equal(a.schritt.value, 'fertig', 'der Schritt ist nicht weitergelaufen')
  assert.equal(a.fehler.value, '', 'es steht ein Fehler, obwohl alles geklappt hat')
})

test('E2-3: bereits vorhandene Kalender (uebersprungen) gelten als angelegt', async () => {
  const { a } = await imKalenderSchritt({
    [EINRICHTUNG + 'kalender_vorschlag_anlegen']: {
      message: { angelegt: ['Gottesdienste'], uebersprungen: ['Gemeindekalender'] },
    },
  })
  assert.equal(await a.weiter(), true, 'ein Duplikat darf den Schritt nicht blockieren')
  assert.equal(a.schritt.value, 'fertig')
})

test('E2-3: Serverfehler — sichtbare Meldung, Schritt bleibt stehen, Auswahl bleibt', async () => {
  // Der Fehler trägt die Meldung, die `apiCall` bei einem 417/403 liefert.
  const grund = new Error('Kein Zugriff auf Kalender.')
  const { a, aufrufe } = await imKalenderSchritt({}, {
    [EINRICHTUNG + 'kalender_vorschlag_anlegen']: grund,
  })
  // ZUERST: der Befund (der Schritt darf NICHT stillschweigend weiterlaufen) —
  // diese Prüfung schlägt im alten Stand an, dort wurde der Fehler geschluckt.
  assert.equal(await a.weiter(), false, 'weiter() meldet Erfolg, obwohl das Anlegen scheiterte')
  assert.equal(a.schritt.value, 'mitglieder_kalender', 'der Schritt ist trotz Fehler weitergelaufen')
  // Und die Meldung steht am Schritt (der alte Stand hat sie nach dem
  // verschluckten Fehler wieder weggeworfen).
  assert.match(a.fehler.value, /Kein Zugriff auf Kalender/, 'die Servermeldung fehlt')
  // KEIN stilles „erledigt“: der Prozessstand wurde nicht gesetzt.
  const gesetzt = aufrufe.filter((r) => r.methode === EINRICHTUNG + 'schritt_setzen')
  assert.deepEqual(gesetzt, [], 'der Schritt wurde trotz Fehler als erledigt gemeldet')
  // Der Fehler steht NICHT an einem Feld — er gilt dem Schritt.
  assert.deepEqual(Object.keys(a.feldFehler), [])
  // Die Eingaben bleiben stehen (man kann es erneut versuchen oder abwählen).
  assert.equal(a.kalenderAuswahl.Gottesdienste, true)
  assert.equal(a.kalenderAuswahl.Gemeindekalender, true)
})

test('E2-3: nicht bestätigte Namen — Meldung nennt, was fehlt (Fehlerkatalog-Muster)', async () => {
  // Der Server antwortet 200, bestätigt aber nur einen Namen. Genau das war
  // der stille Fall: die Antwort kam, angelegt wurde nichts.
  const { a } = await imKalenderSchritt({
    [EINRICHTUNG + 'kalender_vorschlag_anlegen']: {
      message: { angelegt: [], uebersprungen: [] },
    },
  })
  assert.equal(await a.weiter(), false)
  assert.equal(a.schritt.value, 'mitglieder_kalender')
  // was: beide Namen; warum: nicht bestätigt; was jetzt: erneut/abwählen.
  assert.match(a.fehler.value, /Gottesdienste, Gemeindekalender wurden nicht angelegt/)
  assert.match(a.fehler.value, /nicht bestätigt/, 'die Ursache fehlt')
  assert.match(a.fehler.value, /erneut versuchen|abhäkchen|abwählen/, 'der nächste Schritt fehlt')
})

test('E2-3: alle Vorschläge abgewählt — kein Aufruf, der Schritt wird erledigt', async () => {
  const { a, aufrufe } = await imKalenderSchritt({})
  a.kalenderAuswahl.Gottesdienste = false
  a.kalenderAuswahl.Gemeindekalender = false
  assert.equal(await a.weiter(), true)
  const anlegen = aufrufe.filter((r) => r.methode === EINRICHTUNG + 'kalender_vorschlag_anlegen')
  assert.deepEqual(anlegen, [], 'ohne Auswahl darf kein Kalender angelegt werden')
  assert.equal(a.schritt.value, 'fertig')
})

// ── E2-5 · Logo sofort in der Seitenleiste ─────────────────────────────────

test('E2-5: nach dem Upload steht die Server-Adresse im Boot-Objekt (mit ?v=)', async () => {
  const { mod, boot } = await ladeModul({
    [EINRICHTUNG + 'status']: status(),
    [GEMEINDE + 'gemeinde_get_einstellungen']: { gemeindename: 'Pruefhausen' },
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  assert.equal(boot.logo_url, null, 'Vorbedingung: ohne Logo ist der Boot-Wert leer')

  // Form einer echten fetch-Antwort: `apiAntwortPruefen` liest den Rumpf über
  // `res.text()` (datenVon → liesAntwort), nicht über `json()`.
  const rumpf = JSON.stringify({
    message: {
      logo_vorhanden: true,
      logo_url: '/diakronos/gemeinde/logo?v=abc123',
    },
  })
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    text: async () => rumpf,
  })
  const datei = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'logo.png',
    { type: 'image/png' })
  assert.equal(await a.ladeLogoHoch(datei), true, 'der Upload meldet keinen Erfolg')
  assert.equal(boot.logo_url, '/diakronos/gemeinde/logo?v=abc123',
    'das Boot-Objekt trägt die neue Marke nicht — die Seitenleiste bleibt auf dem Monogramm')
  assert.ok(globalThis.__on5Ereignisse.includes('dk-marke-geaendert'),
    'es wird keine Marken-Aenderung gemeldet — die Seitenleiste zeichnet nicht neu')
  // Die Adresse wird NICHT nachgebaut: Präfix und ?v= kommen vom Server.
  assert.equal(a.logoQuelle.value, '/diakronos/gemeinde/logo?v=abc123')
})

test('E2-5: nach dem Entfernen ist die Marke im Boot-Objekt leer', async () => {
  const { mod, boot } = await ladeModul({
    [EINRICHTUNG + 'status']: status(),
    [GEMEINDE + 'gemeinde_get_einstellungen']: { gemeindename: 'Pruefhausen' },
    [GEMEINDE + 'gemeinde_logo_entfernen']: {
      message: { logo_vorhanden: false, logo_url: '', gespeichert: true },
    },
  })
  const a = mod.useEinrichtungsAssistent()
  await a.ladeAssistent({ start: true })
  boot.logo_url = '/diakronos/gemeinde/logo?v=alt'
  assert.equal(await a.entferneLogo(), true)
  assert.equal(boot.logo_url, null, 'das entfernte Logo steht weiter im Boot-Objekt')
})

test('E2-5: die Seitenleiste hoert auf die Marken-Aenderung (sonst bleibt das alte Logo)', () => {
  const leiste = lies('frontend/src/diakonos/components/AppSidebar.vue')
  // Der Wert kommt weiterhin aus dem Boot-Objekt (kein zweiter Datenweg) …
  assert.match(leiste, /window\.__DIakonosBOOT\?\.logo_url/,
    'die Seitenleiste liest die Marke nicht mehr aus dem Boot-Objekt')
  // … aber er wird bei `dk-marke-geaendert` in eine `ref` nachgezogen. Ohne
  // das blieb im Prueflauf das ALTE Logo stehen (plain JS zeichnet nicht neu).
  assert.match(leiste, /addEventListener\('dk-marke-geaendert'/,
    'die Seitenleiste hoert nicht auf die Marken-Aenderung')
  assert.match(leiste, /const logoQuelleMarke = computed\(\(\) => markeStand\.value\)/,
    'die Anzeige haengt nicht an der reaktiven Marke')
  // Der alte Kommentar behauptete „erst nach dem nächsten Seitenaufbau“ —
  // genau das war der Befund.
  assert.doesNotMatch(leiste, /erst nach einem Neuladen|so gewollt \(kein zweiter Zustand/,
    'der Kommentar behauptet weiterhin das alte Verhalten')
})

// ── Klein · Dev-Modus-Aufruf nur bei eingeschaltetem Dev-Modus ─────────────

test('Dev-Modus: der Abschnitt fragt den Server NUR bei eingeschaltetem Dev-Modus', () => {
  const seite = lies('frontend/src/diakonos/pages/einstellungen/DevModus.vue')
  // Die Sperre steht VOR dem Aufruf (sonst liefe er trotzdem).
  const sperre = seite.indexOf('if (!devmodeAn)')
  const aufruf = seite.indexOf('await devmodusUebersicht()')
  assert.ok(sperre > 0, 'die Sperre `if (!devmodeAn)` fehlt')
  assert.ok(aufruf > sperre,
    '`devmodusUebersicht()` steht VOR der Sperre — der 404 im ausgeschalteten Modus bleibt')
  assert.match(seite, /const devmodeAn = Boolean\(window\.__DIakonosBOOT\?\.devmode\)/,
    'die Boot-Angabe `devmode` wird nicht gelesen')
  // 404/403 bleiben abgefangen (der Server entscheidet, nicht die Oberfläche).
  assert.match(seite, /e\?\.status === 404 \|\| e\?\.status === 403/,
    'der 404/403-Weg ist verloren gegangen')
})

// ── Klein (2) · Dev-Modus-Autostart beim Seitenaufbau ──────────────────────

let devZaehler = 0
async function ladeDevmodul() {
  const aufrufe = []
  globalThis.__on5DevCall = async (methode, argumente) => {
    aufrufe.push({ methode, argumente })
    return { kuerzel: 'Strg+Shift+F', stt: false, sitzung: false }
  }
  let quelle = lies('frontend/src/diakonos/composables/useDevmodus.js')
  quelle = quelle.replace(
    "import { ref } from 'vue'",
    'const ref = (v) => ({ value: v })',
  )
  quelle = quelle.replace(
    "import { apiCall } from '../composables/useApi.js'",
    'const apiCall = globalThis.__on5DevCall',
  )
  quelle = quelle.replace(
    /import \{ apiUrl \} from '\.\.\/\.\.\/shared\/basis\.js'/,
    'const apiUrl = (p) => p',
  )
  quelle = quelle.replace(
    "import { fehlertext } from '../../shared/fehlertexte.js'",
    'const fehlertext = (f) => String(f?.message || f)',
  )
  devZaehler += 1
  return { mod: await import('data:text/javascript;base64,'
    + Buffer.from(quelle).toString('base64') + `#on5dev-${devZaehler}`), aufrufe }
}

test('Dev-Modus: bei AUSGESCHALTETEM Dev-Modus fragt der Seitenaufbau den Server nicht', async () => {
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
  globalThis.window = { __DIakonosBOOT: { devmode: false } }
  const { mod, aufrufe } = await ladeDevmodul()
  assert.equal(await mod.devmodusPruefen(), null)
  assert.equal(await mod.devmodusAutostart(), null)
  assert.deepEqual(aufrufe, [],
    'der 404-Aufruf auf devmodus.api.uebersicht läuft weiter (Konsolenfehler im Prüflauf)')
  assert.equal(mod.devmodusAn.value, false)
})

test('Dev-Modus: bei EINGESCHALTETEM Dev-Modus wird der Zustand geholt', async () => {
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
  globalThis.window = { __DIakonosBOOT: { devmode: true } }
  const { mod, aufrufe } = await ladeDevmodul()
  const daten = await mod.devmodusPruefen()
  assert.ok(daten, 'ohne Prüfung gibt es keinen Zustand')
  assert.equal(aufrufe.length, 1)
  assert.equal(aufrufe[0].methode, 'diakronos.devmodus.api.uebersicht')
})

// ── E2-5 (2) · Auch die EINSTELLUNGEN ziehen die Marke nach ────────────────

test('E2-5: das Marken-Modul ist die eine Stelle (Boot-Objekt + Ereignis)', async () => {
  globalThis.__on5Ereignisse = []
  globalThis.window = {
    __DIakonosBOOT: { logo_url: '/alt.png' },
    dispatchEvent: (e) => globalThis.__on5Ereignisse.push(e.type),
  }
  const mod = await import(dateiUrl('frontend/src/diakonos/composables/gemeindeMarke.mjs')
    + `?on5=${ladeZaehler}-marke`)
  assert.equal(mod.geleseneGemeindeMarke(), '/alt.png')
  assert.equal(mod.merkeGemeindeMarke('/diakronos/gemeinde/logo?v=neu'), '/diakronos/gemeinde/logo?v=neu')
  assert.equal(globalThis.window.__DIakonosBOOT.logo_url, '/diakronos/gemeinde/logo?v=neu',
    'das Boot-Objekt bekommt die neue Adresse nicht')
  assert.deepEqual(globalThis.__on5Ereignisse, ['dk-marke-geaendert'],
    'die Neuzeichnung wird nicht gemeldet')
  // Entfernen: leerer Wert -> kein Logo (Monogramm).
  mod.merkeGemeindeMarke('')
  assert.equal(globalThis.window.__DIakonosBOOT.logo_url, null)
  assert.equal(mod.geleseneGemeindeMarke(), '')
})

test('E2-5: der Logo-Weg der EINSTELLUNGEN ruft das Marken-Modul (useGemeinde)', () => {
  const quelle = lies('frontend/src/diakonos/composables/useGemeinde.js')
  assert.match(quelle, /import \{ merkeGemeindeMarke \} from '\.\/gemeindeMarke\.mjs'/,
    'useGemeinde importiert das Marken-Modul nicht')
  // Hochladen UND Entfernen: nach beiden muss die Marke nachgezogen werden.
  const aufrufe = quelle.match(/merkeGemeindeMarke\(/g) || []
  assert.ok(aufrufe.length >= 2,
    `nur ${aufrufe.length} Aufruf(e) — Hochladen und Entfernen brauchen je einen`)
  assert.match(quelle, /logoUrl\.value = d\?\.logo_url \|\| ''\n\s*\/\/ ON-5 \(E2-5\)[\s\S]{0,200}merkeGemeindeMarke/,
    'nach dem Hochladen fehlt der Aufruf')
})

test('E2-5: der Assistent nutzt DASSELBE Modul (kein zweiter Merker)', () => {
  const quelle = lies('frontend/src/diakonos/composables/useEinrichtungsAssistent.js')
  assert.match(quelle, /import \{ merkeGemeindeMarke \} from '\.\/gemeindeMarke\.mjs'/)
  assert.doesNotMatch(quelle, /function merkeMarke\(/,
    'der Assistent hat wieder einen eigenen Merker — zwei Stellen laufen auseinander')
})
