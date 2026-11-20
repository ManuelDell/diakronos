/**
 * SEC-11d · WÄCHTER — kein POST an einen Endpunkt, der nur GET annimmt.
 *
 * Die GEGENRICHTUNG von `sec11-get-schreibend.test.mjs` (SEC-11 C3): dort geht
 * es um GET an einen schreibenden Endpunkt (Security), hier um POST an einen
 * Endpunkt, der laut Inventar POST GAR NICHT annimmt — also um eine KAPUTTE
 * Seite (405, „die Seite lädt nie“).
 *
 * BEFUND (CHAT-7b-UI-b): `apiCall('diakronos_app.api.chat.meine_sperren')`
 * schickt POST (siehe `composables/useApi.js`), der Endpunkt deklariert aber
 * `methods=["GET"]` → 405. Kein Test fiel darauf — C3 prüft nur die andere
 * Richtung.
 *
 * Geprüft wird (Quelle: `tests/sec11-zugriff.mjs`, dieselbe wie bei C3):
 *   A  `apiCall(<pfad>)` — apiCall schickt IMMER POST. Der Pfad darf ein
 *      Literal (`'a.b.c'`), eine Methodenadresse (`apiUrl('…')`,
 *      `mitBasis('/api/method/…')`) oder `PRAEFIX + 'name'` sein; `PRAEFIX`
 *      wird über die Konstanten der Datei aufgelöst.
 *   B  `fetch(…)` mit `method: 'POST'` im selben Optionsblock und einer
 *      Methoden-Adresse im Aufruf (`apiUrl(…)`, `mitBasis('/api/method/…')`,
 *      `/api/method/<name>` als Text) — unabhängig von der Zeilenlage.
 *   C  Wege, deren Methodenname erst zur LAUFZEIT feststeht (`apiCall(methode)`
 *      mit wechselnder Konstante), kann ein Quelltext-Wächter nicht auflösen.
 *      Sie werden als HINWEIS in der Ausgabe genannt, nie still verschluckt.
 *
 * Auf dem heutigen Stand gibt es keinen Fund: der Wächter ist ein Netz für die
 * ZUKUNFT. Der Selbsttest unten belegt, dass die Erkennung den Fehler von
 * CHAT-7b-UI-b wirklich sieht — sonst wäre „0 Funde“ nicht von „schaut nichts
 * an“ zu unterscheiden. Die Fundstellen werden NICHT im Produktivcode
 * korrigiert (Entscheidung Operator); schlägt der Wächter an, blockt die Karte.
 *
 * Lokal:   node --test tests/sec11d-post-nur-get.test.mjs
 * Im Image: backend/Dockerfile über die Zeile `tests/sec11d-*.test.mjs`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  SRC, quellzeilen, nurGetNamen, inventar, INVENTAR_PFAD,
} from './sec11-zugriff.mjs'

/** Kommentarzeile? (Die Wächter von C3 überspringen sie genauso.) */
export function istKommentar(zeile) {
  return /^\s*(\*|\/\/|\/\*)/.test(zeile)
}

/** Endname eines Methodenausdrucks: `…api.chat.meine_sperren` → `meine_sperren`. */
export function endName(ausdruck) {
  const sauber = String(ausdruck).replace(/[`'"]/g, '').replace(/[),;]+$/, '')
  const teile = sauber.split(/[.?\s]/).map((t) => t.trim()).filter(Boolean)
  return teile.length ? teile[teile.length - 1].replace(/[^\w]/g, '') : ''
}

/**
 * Name aus einem Adresstext: `apiUrl('a.b.c')` → `c`,
 * `mitBasis('/api/method/a.b.c')` → `c`, `'a.b.c'` (Literal) → `c`.
 * `null`, wenn der Text keine Methode benennt (Route wie `upload_file`,
 * Query, Ressourcenpfad, leeres Ergebnis).
 */
export function nameAusAdresse(text) {
  if (!text) return null
  const apiUrl = String(text).match(/apiUrl\(\s*['"]([^'"]+)['"]/)
  if (apiUrl) return endName(apiUrl[1])
  const methode = String(text).match(/\/api\/method\/([A-Za-z_][\w.]*)/)
  if (methode) return endName(methode[1])
  const literal = String(text).match(/^\s*['"]([A-Za-z_][\w.]*)['"]/)
  if (literal) return endName(literal[1])
  return null
}

/**
 * Der Inhalt hinter dem LETZTEN `apiCall(` — oder `null`, wenn dieser Text
 * gar keinen echten Aufruf enthält (abgebrochene Suche bzw. Definition).
 */
function apiCallArgument(text) {
  const stelle = text.lastIndexOf('apiCall(')
  if (stelle < 0) return null
  // `text.lastIndexOf('apiCall(')` / `indexOf('apiCall(')`: eine Suche nach dem
  // String, kein Aufruf. Erkennbar am geöffneten String davor.
  const davor = text.slice(Math.max(0, stelle - 40), stelle)
  if (/(lastIndexOf|indexOf|includes|match|search)\(\s*$/.test(davor)) return null
  if (/(function|=>)\s*apiCall\s*$/.test(davor)) return null
  return text.slice(stelle + 'apiCall('.length)
}

/**
 * Konstanten einer Datei: `const API = mitBasis('/api/method/a.b.c')`,
 * `const PRAEFIX = 'diakronos.devmodus.api.'`, `const X = 'a.b.c'`.
 * Wert ohne Schlusspunkt, damit `PRAEFIX + 'name'` direkt verkettbar ist.
 */
function konstanten(quellen) {
  const je = new Map()
  for (const { datei, zeile } of quellen) {
    if (istKommentar(zeile)) continue
    const m = zeile.match(/(?:const|let|var)\s+(\w+)\s*=\s*(.+)$/)
    if (!m) continue
    const basis = m[2].match(/mitBasis\(\s*['"]\/api\/method\/([A-Za-z_][\w.]*)['"]\s*\)/)
    const wert = basis ? basis[1]
      : (m[2].match(/['"]([A-Za-z_][\w.]*?)['"]\s*(?:$|[+;,)]|\/\/)/) || [])[1] || ''
    if (!wert) continue
    if (!je.has(datei)) je.set(datei, new Map())
    je.get(datei).set(m[1], String(wert).replace(/\.$/, ''))
  }
  return je
}

/** `PRAEFIX + 'name'` auflösen; `null`, wenn die Konstante unbekannt ist. */
function konstantePlusName(ausdruck, tabelle) {
  const m = String(ausdruck).match(/^\s*([A-Za-z_]\w*)\s*\+\s*['"]?([\w.]*)['"]?/)
  if (!m) return null
  const wert = tabelle?.get(m[1])
  if (!wert) return null
  return endName(m[2] ? `${wert}.${m[2]}` : wert)
}

/**
 * `${KONSTANTE}.name` auflösen (Template-Literal mit FESTEM Endpunktnamen),
 * `null`, wenn Konstante oder Name unbekannt/variabel sind.
 */
function templatePlusName(ausdruck, tabelle) {
  const m = String(ausdruck).match(/^\s*`\$\{([A-Za-z_]\w*)\}\.([A-Za-z_]\w*)`/)
  if (!m) return null
  const wert = tabelle?.get(m[1])
  if (!wert) return null
  return endName(`${wert}.${m[2]}`)
}

/**
 * Der Methodenname eines Ausdrucks, so weit er ohne Ausführung feststeht:
 * Literal, `apiUrl(…)`, `PRAEFIX + 'name'`, `` `${PRAEFIX}.name` ``.
 * `null` = Name erst zur Laufzeit (Variable, wechselnde Konstante).
 */
function nameAusAusdruck(ausdruck, tabelle) {
  return nameAusAdresse(ausdruck)
    || konstantePlusName(ausdruck, tabelle)
    || templatePlusName(ausdruck, tabelle)
}

/** Die Adresse eines fetch-Aufrufs (Klammerinhalt) als Text. */
function fetchAdresse(quellen, i) {
  let text = ''
  let tiefe = 0
  for (let j = i; j < Math.min(i + 12, quellen.length); j++) {
    let zeile = quellen[j].zeile
    if (j === i) zeile = zeile.slice(zeile.indexOf('fetch(') + 'fetch('.length)
    text += zeile + '\n'
    for (const ch of zeile) {
      if ('([{'.includes(ch)) tiefe++
      else if (')]}'.includes(ch)) tiefe--
    }
    if (tiefe <= 0) break
  }
  // Nur der Kopf bis zum Optionsobjekt: `…, { method: …`.
  return text.split(/,\s*\{/)[0]
}

/** Optionsblock eines fetch-Aufrufs (folgende Zeilen), als Text. */
function optionsBlock(quellen, i, spanne = 14) {
  return quellen.slice(i, i + spanne).map((z) => z.zeile).join('\n')
}

function schicktPost(options) {
  return /method:\s*['"`]POST['"`]/i.test(options)
}

/**
 * POST-Aufrufe der SPA, die sich einem ENDPUNKTNAMEN zuordnen lassen.
 * Liefert `{ funde: [{datei, nr, name, adresse, weg}],
 *           offen: [{datei, nr, text}] }`.
 *
 * `quellen` erlaubt den Selbsttest mit eingebettetem Beispieltext.
 */
export function sammlePostAufrufe(quellen, nurGet) {
  const funde = []
  const offen = []
  const stellige = konstanten(quellen)

  // A: apiCall(…) — schickt immer POST.
  for (let i = 0; i < quellen.length; i++) {
    const { datei, nr, zeile } = quellen[i]
    if (istKommentar(zeile) || !/\bapiCall\(/.test(zeile)) continue
    // Definition/Weiterleitung (`function apiCall(…)`, `modul.apiCall(…)`) ist
    // kein Aufruf an einen Endpunkt.
    if (/(export\s+)?(async\s+)?function\s+apiCall\s*\(/.test(zeile)) continue
    if (/\.apiCall\(\.\.\./.test(zeile)) continue
    // Mehrzeilige Aufrufe: `apiCall(` am Zeilenende, Pfad in der nächsten.
    let text = zeile
    if (/apiCall\(\s*$/.test(zeile)) {
      const folge = quellen[i + 1]
      if (folge && folge.datei === datei) text += ' ' + folge.zeile.trim()
    }
    const argument = apiCallArgument(text)
    if (argument === null) continue
    const name = nameAusAusdruck(argument, stellige.get(datei))
    if (name) {
      if (nurGet.has(name)) {
        funde.push({ datei, nr, name, adresse: `apiCall(…${name})`, weg: 'apiCall' })
      }
      continue
    }
    // `apiCall(methode)` / `apiCall(API.setzen, …)`: Methodenname erst zur
    // Laufzeit — ein Quelltext-Wächter kann ihn nicht auflösen.
    offen.push({ datei, nr, text: zeile.trim() })
  }

  // B: fetch(…) mit `method: 'POST'` und Methoden-Adresse im Aufruf.
  for (let i = 0; i < quellen.length; i++) {
    const { datei, nr, zeile } = quellen[i]
    if (istKommentar(zeile) || !/\bfetch\(/.test(zeile)) continue
    if (!schicktPost(optionsBlock(quellen, i))) continue
    const kopf = fetchAdresse(quellen, i)
    const name = nameAusAusdruck(kopf, stellige.get(datei))
    if (name) {
      if (nurGet.has(name)) {
        funde.push({ datei, nr, name, adresse: `fetch(…${name}…)`, weg: 'fetch' })
      }
      continue
    }
    // `fetch(`${API}.${methode}`, { method: 'POST' … })` — Name zur Laufzeit.
    if (/\$\{/.test(kopf)) offen.push({ datei, nr, text: zeile.trim() })
  }

  return { funde, offen }
}

// ── Das Inventar als Grundlage ───────────────────────────────────────────

test('d: das Inventar nennt Endpunkte, die POST NICHT annehmen', () => {
  const daten = inventar()
  const nurGet = nurGetNamen()
  assert.ok(nurGet.size >= 1,
    'kein einziger Endpunkt ohne POST im Inventar — Wächter prüft ins Leere')
  // Benannter Fall der Karte: `chat.meine_sperren` deklariert GET.
  assert.ok(nurGet.has('meine_sperren'),
    'meine_sperren fehlt unter den GET-only-Endpunkten — Inventar veraltet')
  const eintrag = daten.eintraege.find((e) => e.name === 'meine_sperren')
  assert.deepEqual(eintrag.methoden, ['GET'],
    `meine_sperren deklariert ${JSON.stringify(eintrag.methoden)} statt ["GET"]`)
  // Nur Einträge MIT Methodenangabe gehören in die Menge — und keiner davon
  // nimmt POST an.
  for (const e of daten.eintraege) {
    if (!nurGet.has(e.name)) continue
    assert.ok(Array.isArray(e.methoden) && e.methoden.length > 0,
      `${e.funktion}: ohne methoden in der GET-only-Menge`)
    assert.ok(!e.methoden.includes('POST'),
      `${e.funktion}: nimmt POST an, steht aber in der GET-only-Menge`)
  }
})

test('d: apiCall schickt POST (Grundlage des Wächters)', () => {
  const text = readFileSync(new URL('diakonos/composables/useApi.js', SRC), 'utf8')
  const block = text.slice(text.indexOf('export async function apiCall'))
  assert.ok(block.length > 0, 'useApi.js exportiert apiCall nicht mehr')
  assert.match(block.slice(0, 900), /method:\s*'POST'/,
    'apiCall schickt keinen POST mehr — dann prüft dieser Wächter das Falsche')
})

// ── Der eigentliche Wächter ──────────────────────────────────────────────

test('d: kein apiCall/fetch-POST an einen GET-only-Endpunkt', () => {
  const nurGet = nurGetNamen()
  const { funde, offen } = sammlePostAufrufe(quellzeilen(), nurGet)
  const zeilen = funde.map((f) => `${f.datei}:${f.nr} ${f.weg} → ${f.adresse}`)
  if (offen.length) {
    // Nicht still übergehen: diese Aufrufe konnte die Prüfung nicht auflösen.
    console.log(`SEC-11d: ${offen.length} POST-Aufruf(e) nicht auflösbar ` +
      '(Methodenname erst zur Laufzeit):\n  ' +
      offen.map((o) => `${o.datei}:${o.nr} ${o.text}`).join('\n  '))
  }
  assert.deepEqual(zeilen, [],
    'SEC-11d: diese Aufrufer schicken POST an einen Endpunkt, der POST NICHT ' +
    'annimmt (405 — die Seite lädt nie):\n  ' + zeilen.join('\n  '))
})

// ── Selbsttest der Erkennung ─────────────────────────────────────────────

test('d: die Prüfung sieht den Fehler von CHAT-7b-UI-b (Selbsttest)', () => {
  const nurGet = nurGetNamen()
  const probe = [{
    datei: 'probe/Chat.vue', nr: 1,
    zeile: "const sperren = await apiCall('diakronos_app.api.chat.meine_sperren')",
  }]
  const { funde } = sammlePostAufrufe(probe, nurGet)
  assert.equal(funde.length, 1,
    'Selbsttest: der apiCall auf meine_sperren wird nicht erkannt')
  assert.equal(funde[0].name, 'meine_sperren',
    `Selbsttest: falscher Endpunktname (${funde[0].name})`)
  assert.equal(funde[0].nr, 1)
})

test('d: die Prüfung sieht den fetch-POST-Weg (Selbsttest)', () => {
  const nurGet = nurGetNamen()
  const probe = [
    { datei: 'probe/a.js', nr: 1, zeile: "const x = await fetch(apiUrl('diakronos.diakonos.api.suche.global_'), {" },
    { datei: 'probe/a.js', nr: 2, zeile: "  method: 'POST'," },
    { datei: 'probe/a.js', nr: 3, zeile: "  body: JSON.stringify({ q })" },
    { datei: 'probe/a.js', nr: 4, zeile: "})" },
  ]
  const { funde } = sammlePostAufrufe(probe, nurGet)
  assert.equal(funde.length, 1,
    'Selbsttest: POST an einen GET-only-Endpunkt per fetch wird nicht erkannt')
  assert.equal(funde[0].name, 'global_')
})

test('d: die Prüfung löst PRAEFIX + Name auf (Selbsttest)', () => {
  const nurGet = nurGetNamen()
  const probe = [
    { datei: 'probe/c.js', nr: 1, zeile: "const PRAEFIX = 'diakronos.diakonos.api.suche.'" },
    { datei: 'probe/c.js', nr: 2, zeile: "await apiCall(PRAEFIX + 'global_', { q })" },
  ]
  const { funde } = sammlePostAufrufe(probe, nurGet)
  assert.equal(funde.length, 1,
    'Selbsttest: apiCall(PRAEFIX + Name) wird nicht aufgelöst')
  assert.equal(funde[0].name, 'global_')
})

test('d: Gegenprobe — POST an einen POST-Endpunkt bleibt grün (Selbsttest)', () => {
  const nurGet = nurGetNamen()
  // Der Wächter darf nicht jedes `apiCall` melden: `gemeinde_speichern` nimmt
  // POST an (Inventar), der Aufruf ist richtig. Ebenso ein fetch MIT POST auf
  // `upload_file`.
  assert.ok(!nurGet.has('gemeinde_speichern'),
    'gemeinde_speichern nimmt keinen POST mehr an — die Gegenprobe prüft nichts')
  assert.ok(!nurGet.has('upload_file'),
    'upload_file nimmt keinen POST mehr an — die Gegenprobe prüft nichts')
  const probe = [
    { datei: 'probe/b.js', nr: 1, zeile: "const API = 'diakronos.diakonos.api.gemeinde.'" },
    { datei: 'probe/b.js', nr: 2, zeile: "await apiCall(API + 'gemeinde_speichern', daten)" },
    { datei: 'probe/b.js', nr: 3, zeile: "await fetch(apiUrl('upload_file'), {" },
    { datei: 'probe/b.js', nr: 4, zeile: "  method: 'POST'," },
    { datei: 'probe/b.js', nr: 5, zeile: "  body: form," },
    { datei: 'probe/b.js', nr: 6, zeile: "})" },
  ]
  const { funde } = sammlePostAufrufe(probe, nurGet)
  assert.deepEqual(funde, [],
    'Gegenprobe rot: ein erlaubter POST-Aufruf wird als Verstoß gemeldet')
})

test('d: die Prüfung liest die echten Quellen (kein leerer Lauf)', () => {
  // Ohne diesen Fall wäre „0 Funde“ auch bei einem kaputten Leser grün.
  const quellen = quellzeilen()
  assert.ok(quellen.length > 1000,
    `nur ${quellen.length} Quellzeilen gelesen — der Leser greift ins Leere`)
  const apiCallZeilen = quellen.filter(
    (q) => /\bapiCall\(/.test(q.zeile) && !istKommentar(q.zeile))
  assert.ok(apiCallZeilen.length > 100,
    `nur ${apiCallZeilen.length} apiCall-Zeilen gefunden — Erkennung blind`)
  const postZeilen = quellen.filter((q) => /method:\s*['"]POST['"]/.test(q.zeile))
  assert.ok(postZeilen.length > 10,
    `nur ${postZeilen.length} POST-Aufrufe gefunden — Erkennung blind`)
  assert.ok(INVENTAR_PFAD.endsWith('whitelist.json'))
})
