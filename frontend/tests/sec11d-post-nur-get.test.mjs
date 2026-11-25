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
 *      `mitBasis('/api/method/…')`), `PRAEFIX + 'name'`,
 *      `<Konstante>.<schlüssel>`/`<Konstante>['schlüssel']`, ein blosses
 *      `<Konstante>` oder eine per `import { PFADE } from './x.mjs'`
 *      gebrachte Objekt-Tabelle sein — die Konstanten der Datei (und der
 *      importierten Datei) werden aufgelöst.
 *   B  `fetch(…)` mit `method: 'POST'` im selben Optionsblock und einer
 *      Methoden-Adresse im Aufruf (`apiUrl(…)`, `mitBasis('/api/method/…')`,
 *      `/api/method/<name>` als Text) — unabhängig von der Zeilenlage.
 *   C  Wege, deren Methodenname erst zur LAUFZEIT feststeht (`apiCall(methode)`
 *      mit wechselnder Konstante), kann ein Quelltext-Wächter nicht auflösen.
 *      Sie werden als HINWEIS in der Ausgabe genannt, nie still verschluckt.
 *
 * BUG-WEB-VORSCHAU (25.11.) — der Wächter hatte ein Loch und ist es selbst:
 * `useAnsprechpartnerBereiche.js` rief `apiCall(API.oeffentlich, {})` (405,
 * Vorschau immer leer). Weil `apiCall(<Konstante>.<schlüssel>)` nicht aufgelöst
 * wurde, landete der Aufruf unter „nicht auflösbar“ — nur ein HINWEIS, und der
 * Test blieb grün. Seit dieser Karte werden Konstanten, Objekt-Tabellen und
 * Importe aufgelöst (C bleibt für echte Laufzeitnamen); der Selbsttest unten
 * hält genau diesen Befund fest.
 *
 * Fundstellen im Produktivcode werden nicht still stehen gelassen: schlägt der
 * Wächter an, blockt die Karte (Entscheidung Operator).
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
 * Der Inhalt zwischen `apiCall(` und der ZUGEHOERIGEN schliessenden Klammer —
 * oder `null`, wenn dieser Text gar keinen echten Aufruf enthält (abgebrochene
 * Suche bzw. Definition).
 *
 * BUG-WEB-VORSCHAU: Frueher war es „alles nach dem letzten `apiCall(`“. Sobald
 * eine Folgezeile mit angehaengt wurde (mehrzeiliger Aufruf), standen danach
 * noch weitere Anweisungen im Text — `API.setzen` wurde dann nicht mehr
 * erkannt und landete unter „nicht auflösbar“.
 */
function apiCallArgument(text) {
  const stelle = text.lastIndexOf('apiCall(')
  if (stelle < 0) return null
  // `text.lastIndexOf('apiCall(')` / `indexOf('apiCall(')`: eine Suche nach dem
  // String, kein Aufruf. Erkennbar am geöffneten String davor.
  const davor = text.slice(Math.max(0, stelle - 40), stelle)
  if (/(lastIndexOf|indexOf|includes|match|search)\(\s*$/.test(davor)) return null
  if (/(function|=>)\s*apiCall\s*$/.test(davor)) return null
  const rest = text.slice(stelle + 'apiCall('.length)
  let tiefe = 1
  for (let i = 0; i < rest.length; i++) {
    const ch = rest[i]
    if ('([{'.includes(ch)) tiefe++
    else if (')]}'.includes(ch)) {
      tiefe--
      if (tiefe === 0) return rest.slice(0, i)
    }
  }
  // Klammer nie geschlossen (Textende): das ist kein auswertbarer Aufruf.
  return null
}

/**
 * Konstanten einer Datei: `const API = mitBasis('/api/method/a.b.c')`,
 * `const PRAEFIX = 'diakronos.devmodus.api.'`, `const X = 'a.b.c'`,
 * `const API = { setzen: 'a.b.c', oeffentlich: 'x.y.z' }` (Objekt-Tabelle,
 * je Schluessel ein Eintrag `API.setzen` — auch `Object.freeze({ … })`).
 * Wert ohne Schlusspunkt, damit `PRAEFIX + 'name'` direkt verkettbar ist.
 *
 * Zwei Durchgaenge ueber die Zeilen (Objekt-Tabellen, dann einfache
 * Konstanten): die Zeilen werden EINMAL je Datei gebuendelt — sonst waere die
 * Suche quadratisch (Befund: das erste Muster lief minutenlang).
 *
 * BUG-WEB-VORSCHAU: vorher waren nur Literale, `apiUrl(…)` und
 * `PRAEFIX + '…'` auflösbar. Genau der Befund (`apiCall(API.oeffentlich, {})`)
 * landete damit unter „nicht auflösbar“ und wurde nur als HINWEIS ausgegeben —
 * der Waechter war still gruen, obwohl der Aufruf 405 liefert.
 */
function konstanten(quellen) {
  // Zeilen je Datei (einmal aufbauen, nicht je Zeile neu suchen).
  const jeDatei = new Map()
  for (const { datei, zeile } of quellen) {
    if (!jeDatei.has(datei)) jeDatei.set(datei, [])
    jeDatei.get(datei).push(zeile)
  }
  const je = new Map()
  const tabelle = (datei) => {
    if (!je.has(datei)) je.set(datei, new Map())
    return je.get(datei)
  }

  // ── 1. Objekt-Tabellen ──────────────────────────────────────────────────
  const objektNamen = new Set()
  for (const [datei, zeilen] of jeDatei) {
    for (let i = 0; i < zeilen.length; i++) {
      // `const API = {` / `const API = { lesen: '…',` / `… = Object.freeze({`.
      const start = zeilen[i].match(
        /(?:const|let|var)\s+(\w+)\s*=\s*(?:\w+(?:\.\w+)*\(\s*)?\{(.*)$/)
      if (!start) continue
      const name = start[1]
      objektNamen.add(`${datei}\u0000${name}`)
      let block = start[2]
      // Block bis zur schliessenden Klammer — mehrzeilig ODER einzeilig.
      if (!/\}\s*\)*\s*;?\s*(\/\/.*)?$/.test(start[2])) {
        for (let j = i + 1; j < Math.min(i + 40, zeilen.length); j++) {
          block += '\n' + zeilen[j]
          if (/^\s*\}\s*\)*\s*;?\s*(\/\/.*)?$/.test(zeilen[j])) break
        }
      }
      for (const roh of block.split('\n')) {
        // Kommentarzeilen enthalten Beispieltext in Backticks — der sieht wie
        // ein Eintrag aus (`// … aus \`shared/x.mjs\``).
        const ohne = istKommentar(roh) ? '' : roh.replace(/\/\/.*$/, '')
        for (const m of ohne.matchAll(/(?:^|[,{\s])(\w+)\s*:\s*([^,\n}]+)/g)) {
          // Nur ein reiner Zeichenketten-Wert zaehlt.
          const wert = (m[2].match(/^\s*['"]([A-Za-z_][\w.]*)['"]\s*$/) || [])[1]
          if (!wert) continue
          tabelle(datei).set(`${name}.${m[1]}`, wert.replace(/\.$/, ''))
        }
      }
    }
  }

  // ── 2. Einfache Konstanten ──────────────────────────────────────────────
  for (const { datei, zeile } of quellen) {
    if (istKommentar(zeile)) continue
    const m = zeile.match(/(?:const|let|var)\s+(\w+)\s*=\s*(.+)$/)
    if (!m) continue
    // Objekt-Tabellen liefen oben schon.
    if (objektNamen.has(`${datei}\u0000${m[1]}`)) continue
    if (/^\s*(?:\w+(?:\.\w+)*\(\s*)?\{/.test(m[2])) continue
    const basis = m[2].match(/mitBasis\(\s*['"]\/api\/method\/([A-Za-z_][\w.]*)['"]\s*\)/)
    const wert = basis ? basis[1]
      : (m[2].match(/['"]([A-Za-z_][\w.]*?)['"]\s*(?:$|[+;,)]|\/\/)/) || [])[1] || ''
    if (!wert) continue
    tabelle(datei).set(m[1], String(wert).replace(/\.$/, ''))
  }

  // ── 3. Importierte Namen ────────────────────────────────────────────────
  // `import { PFADE } from './x.mjs'` -> Einträge der Quelldatei unter dem
  // lokalen Namen. Ohne das bliebe `apiCall(PFADE.liste, …)` „nicht
  // auflösbar“, obwohl der Pfad feststeht. Die Quelldatei liegt im selben
  // Lauf (`quellzeilen()` liest ganz `src/`).
  for (const [datei, zeilen] of jeDatei) {
    const eigen = tabelle(datei)
    for (let i = 0; i < zeilen.length; i++) {
      if (istKommentar(zeilen[i]) || !/^\s*import\s*\{/.test(zeilen[i])) continue
      let block = zeilen[i]
      let kopf = zeilen[i].match(/^\s*import\s*\{([^}]*)\}?\s*(?:from\b|$)/)
      if (!kopf || zeilen[i].trim().endsWith('{')) {
        for (let j = i + 1; j < Math.min(i + 40, zeilen.length); j++) {
          block += '\n' + zeilen[j]
          kopf = block.match(/^\s*import\s*\{([^}]*)\}\s*from\b/s)
          if (kopf) break
        }
      }
      if (!kopf) continue
      // Die `from`-Zeile steht beim mehrzeiligen Import am ENDE.
      const spez = block.match(/^\s*\}\s*from\s*['"](\.[^'"]+)['"]/m)
        || block.match(/from\s*['"](\.[^'"]+)['"]/)
      if (!spez) continue
      const ziel = relativerPfad(datei, spez[1])
      // Nach Dateinamen suchen (Endung `.js`/`.mjs` ist beliebig).
      const quelle = ziel ? (je.get(ziel) || je.get(`${ziel}.mjs`) || je.get(`${ziel}.js`)) : null
      if (!quelle) continue
      for (const roh of kopf[1].split(',')) {
        const name = roh.trim().split(/\s+as\s+/).pop().trim()
        if (!name) continue
        for (const [schluessel, wert] of quelle) {
          if (schluessel === name || schluessel.startsWith(`${name}.`)) {
            eigen.set(schluessel, wert)
          }
        }
      }
    }
  }
  return je
}

/** `./x.mjs` von `datei` aus als Pfad (ohne `.js`/`.mjs`-Unterschied). */
function relativerPfad(datei, spez) {
  const teile = datei.split('/')
  teile.pop()
  for (const stueck of spez.split('/')) {
    if (stueck === '.' || stueck === '') continue
    if (stueck === '..') teile.pop()
    else teile.push(stueck)
  }
  return teile.join('/').replace(/\.(m?js)$/, '')
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
 * Literal, `apiUrl(…)`, `PRAEFIX + 'name'`, `` `${PRAEFIX}.name` ``,
 * `API.setzen` / `API['setzen']` und ein blosses `API` — beide ueber die
 * Konstanten der Datei aufgeloest.
 * `null` = Name erst zur Laufzeit (Variable, wechselnde Konstante).
 *
 * BUG-WEB-VORSCHAU: die beiden letzten Wege fehlten. Genau der Befund
 * (`apiCall(API.oeffentlich, {})` in `useAnsprechpartnerBereiche.js`) fiel
 * damit unter „nicht auflösbar“ und wurde nur als HINWEIS ausgegeben — der
 * Waechter war still gruen, obwohl der Aufruf 405 liefert.
 */
function nameAusAusdruck(ausdruck, tabelle) {
  const direkt = nameAusAdresse(ausdruck)
    || konstantePlusName(ausdruck, tabelle)
    || templatePlusName(ausdruck, tabelle)
  if (direkt) return direkt
  const kopf = String(ausdruck).trim().replace(/^await\s+/, '')
  // `API.setzen` / `API['setzen']` — der Eintrag heisst `<KONSTANTE>.<key>`.
  const glied = kopf.match(/^([A-Za-z_]\w*)\s*(?:\.\s*([A-Za-z_]\w*)|\[\s*['"]([A-Za-z_]\w*)['"]\s*\])/)
  if (glied) {
    const schluessel = glied[2] || glied[3]
    const wert = tabelle?.get(`${glied[1]}.${schluessel}`)
    if (wert) return endName(wert)
    // Der Wert der Konstante ist selbst der Endpunkt (`mitBasis('…/<name>')`).
    const basis = tabelle?.get(glied[1])
    if (basis) return endName(`${basis}.${schluessel}`)
    return null
  }
  // Blosses `API` (die Konstante ist selbst ein Endpunktname)
  const bloss = kopf.match(/^([A-Za-z_]\w*)\s*(?:[,)]|$)/)
  if (bloss) {
    const wert = tabelle?.get(bloss[1])
    if (wert) return endName(wert)
  }
  return null
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
    // Steht der Aufruf KOMPLETT in der Zeile (der Normalfall), bleibt es bei
    // dieser Zeile — sonst zoege die Fortsetzung die Folgezeile mit herein.
    let text = zeile
    let tiefe = 0
    for (const ch of text.slice(text.indexOf('apiCall(') + 'apiCall('.length)) {
      if ('([{'.includes(ch)) tiefe++
      else if (')]}'.includes(ch)) tiefe--
    }
    if (tiefe > 0) {
      // Bis zu 10 Folgezeilen, bis die Klammer zugeht (Argumente und das
      // schliessende `)` duerfen untereinander stehen).
      for (let j = i + 1; j < Math.min(i + 10, quellen.length) && tiefe > 0; j++) {
        const folge = quellen[j]
        if (!folge || folge.datei !== datei) break
        text += ' ' + folge.zeile.trim()
        for (const ch of folge.zeile) {
          if ('([{'.includes(ch)) tiefe++
          else if (')]}'.includes(ch)) tiefe--
        }
      }
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

test('d: die Prüfung löst eine Objekt-Tabelle und ein blosses `API` auf (Selbsttest)', () => {
  const nurGet = nurGetNamen()
  const probe = [
    { datei: 'probe/d.js', nr: 1, zeile: 'const API = {' },
    { datei: 'probe/d.js', nr: 2, zeile: "  lesen: 'diakronos_app.api.chat.meine_sperren'," },
    { datei: 'probe/d.js', nr: 3, zeile: "  setzen: 'diakronos_app.api.chat.gespraech_mitglieder'," },
    { datei: 'probe/d.js', nr: 4, zeile: '}' },
    { datei: 'probe/d.js', nr: 5, zeile: 'await apiCall(API.lesen, {})' },
    // BUG-WEB-VORSCHAU: genau dieser Aufruf war 405 und wurde nicht erkannt.
    { datei: 'probe/d.js', nr: 6, zeile: 'const antwort = await apiCall(API.setzen, {})' },
  ]
  const { funde } = sammlePostAufrufe(probe, nurGet)
  assert.deepEqual(funde.map((f) => `${f.nr}:${f.name}`),
    ['5:meine_sperren', '6:gespraech_mitglieder'],
    'apiCall(<Objekt-Tabelle>.<schlüssel>) muss aufgelöst werden')
})

test('d: die Prüfung löst importierte Konstanten-Tabellen auf (Selbsttest)', () => {
  const nurGet = nurGetNamen()
  const probe = [
    { datei: 'probe/m.mjs', nr: 1, zeile: 'export const PFADE = Object.freeze({' },
    { datei: 'probe/m.mjs', nr: 2, zeile: "  sperren: 'diakronos_app.api.chat.meine_sperren'," },
    { datei: 'probe/m.mjs', nr: 3, zeile: '})' },
    { datei: 'probe/v.vue', nr: 1, zeile: 'import {' },
    { datei: 'probe/v.vue', nr: 2, zeile: '  PFADE,' },
    { datei: 'probe/v.vue', nr: 3, zeile: "} from './m.mjs'" },
    { datei: 'probe/v.vue', nr: 4, zeile: 'await apiCall(PFADE.sperren, {})' },
  ]
  const { funde, offen } = sammlePostAufrufe(probe, nurGet)
  assert.deepEqual(funde.map((f) => f.name), ['meine_sperren'],
    'eine per import gebrachte Objekt-Tabelle muss aufgelöst werden')
  assert.deepEqual(offen, [], 'nichts bleibt „nicht auflösbar“')
})

test('d: der Aufruf von BUG-WEB-VORSCHAU wird gemeldet (Selbsttest)', () => {
  // Der Befund vom 25.11.: `useAnsprechpartnerBereiche.js` holte den
  // öffentlichen Stand per `apiCall` (POST) — 405, die Vorschau blieb leer.
  const nurGet = nurGetNamen()
  assert.ok(nurGet.has('ansprechpartner'),
    'ansprechpartner nimmt keinen POST mehr an — Selbsttest prüft Falsches')
  const probe = [
    { datei: 'probe/use.js', nr: 1, zeile: 'const API = {' },
    { datei: 'probe/use.js', nr: 2, zeile: "  oeffentlich: 'website.oeffentlich.ansprechpartner'," },
    { datei: 'probe/use.js', nr: 3, zeile: '}' },
    { datei: 'probe/use.js', nr: 4, zeile: 'const antwort = await apiCall(API.oeffentlich, {})' },
  ]
  const { funde } = sammlePostAufrufe(probe, nurGet)
  assert.equal(funde.length, 1, 'der 405-Aufruf von BUG-WEB-VORSCHAU wird nicht erkannt')
  assert.equal(funde[0].name, 'ansprechpartner')
  assert.equal(funde[0].nr, 4)
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
