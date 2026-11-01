/**
 * SEC-9 — Wächter: kein `v-html`/`innerHTML` mit Nutzer- oder Serverdaten.
 *
 * Befund Pentest Runde 3 (R3-B, NIEDRIG): Freitextfelder (z. B.
 * `Mitglied.vorname`) werden roh gespeichert und roh als JSON ausgeliefert.
 * Heute ist das nicht ausnutzbar, weil die SPA alles über `{{ }}` escaped.
 * Die Gefahr ist LATENT: ein künftiger ungeschützter Ausgabepfad (neues
 * `v-html`, `innerHTML`, ein PDF-/Druck-/E-Mail-Export) würde den
 * gespeicherten Code scharf schalten.
 *
 * Dieser Test friert den heutigen SICHEREN Zustand ein. Er liest die echten
 * Quelltexte unter `src/` (keine Kopie) und schlägt rot, sobald jemand
 * Nutzerdaten per `v-html` oder `innerHTML` rendert.
 *
 * Erlaubt sind nur zwei Formen:
 *   (A) `v-html` an einen NAMEN, der nachweislich eine fest einprogrammierte
 *       SVG-Konstante ist (`const ICON_X = \`<svg …\``). Der Wert kommt aus
 *       dem Quelltext, nie aus props/reactive/API.
 *   (B) `v-html` an einen Funktionsaufruf, der das Ergebnis VOR der Ausgabe
 *       durch DOMPurify schickt (`sanitize(…)`), sofern diese Funktion im
 *       selben Bauteil als `DOMPurify.sanitize` belegt ist.
 *
 * Alles andere — `v-html="name"` mit einer Variablen aus `props`/`ref`/
 * `computed`/`reactive`/API, `innerHTML = …`, `insertAdjacentHTML`,
 * `outerHTML = …`, `document.write` — fällt durch.
 *
 * Hintergrund (Manuel-Linie): KEIN pauschales serverseitiges Escaping beim
 * Speichern (das korrumpiert Namen mit `<` `&` `'` `"`). Stattdessen den
 * sicheren Zustand festnageln und die echten Ausgabesenken absichern.
 *
 * Läuft im Docker-Build (`backend/Dockerfile`, node --test).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const SRC = fileURLToPath(new URL('../src/', import.meta.url))

/** Alle .vue und .mjs/.js unter src/ (rekursiv). */
function sammleDateien(verzeichnis = SRC, treffer = []) {
  for (const eintrag of readdirSync(verzeichnis)) {
    const voll = path.join(verzeichnis, eintrag)
    if (statSync(voll).isDirectory()) {
      sammleDateien(voll, treffer)
    } else if (/\.(vue|mjs|js)$/.test(eintrag) && !/\.test\.mjs$/.test(eintrag)) {
      treffer.push(voll)
    }
  }
  return treffer.sort()
}

/** Relative Anzeige (für Fehlermeldungen) — nie absolute Host-Pfade. */
const relativ = (p) => path.relative(SRC, p).split(path.sep).join('/')

/** HTML-Kommentare und JS-Block-/Zeilenkommentare entfernen. */
function ohneKommentare(quelle) {
  return quelle
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^[ \t]*\/\/.*$/gm, '')
}

/**
 * Erlaubte, fest einprogrammierte SVG-Konstanten je Datei.
 * Ermittelt — nicht gepflegt: jede `const NAME = \`…\`` / `= '…'` /
 * `= "…"`, deren Wert mit `<svg` beginnt, gilt als statische Icon-Konstante.
 * Alles andere ist KEINE Konstante und damit nicht erlaubt.
 */
function statischeIconKonstanten(quelle) {
  const namen = new Set()
  const muster = /(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(`|')([\s\S]*?)\2/g
  let treffer
  while ((treffer = muster.exec(quelle)) !== null) {
    const [, name, , wert] = treffer
    if (/^\s*<svg[\s>]/.test(wert)) namen.add(name)
  }
  return namen
}

/**
 * Wird `wert` in dieser Datei als `DOMPurify.sanitize` belegt? Nur dann ist
 * ein `v-html="sanitize(…)"` ein echtes Desinfektions-Tor und kein Alibi.
 */
function hatDompurify(quelle) {
  return /\bimport\s+DOMPurify\s+from\s+['"]dompurify['"]/.test(quelle)
    && /\bDOMPurify\.sanitize\s*\(/.test(quelle)
}

/** Ist `ausdruck` ein Aufruf der Desinfektionsfunktion dieser Datei? */
function istDesinfizierenderAufruf(ausdruck, quelle) {
  if (!hatDompurify(quelle)) return false
  const aufruf = ausdruck.match(/^\s*([A-Za-z_$][\w$]*)\s*\(/)
  if (!aufruf) return false
  const [, fn] = aufruf
  // Genau die Funktion, die im Bauteil mit DOMPurify.sanitize belegt ist.
  return new RegExp(`function\\s+${fn}\\s*\\([^)]*\\)\\s*\\{|const\\s+${fn}\\s*=\\s*\\(?[^=]*=>`).test(quelle)
}

/**
 * Ist `ausdruck` ein Zugriff auf eine fest einprogrammierte Symbol-Tabelle?
 * `ICONS[link.icon]` ist erlaubt, wenn
 *   - die Tabelle `const ICONS = { … }` NUR aus statischen SVG-Konstanten
 *     gebaut ist (also selbst kein Fremdwert hineingerät), und
 *   - der Schlüssel ein LITERAL ist (`ICONS['ICON_KALENDER']`). Ein Ausdruck
 *     wie `ICONS[serverWert]` fällt durch: dann entscheidet ein Fremdwert,
 *     was gerendert wird.
 */
function istStatischeTabelle(ausdruck, quelle, konstanten) {
  // Form A: LITERAL-Schlüssel — `ICONS['ICON_KALENDER']`
  // Form B: Feld-Schlüssel   — `SYMBOLE[link.symbol]`
  const liter = ausdruck.trim().match(/^([A-Za-z_$][\w$]*)\s*\[\s*(['"])([^'"]*)\2\s*\]$/)
  const feld = ausdruck.trim().match(/^([A-Za-z_$][\w$]*)\s*\[\s*[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)\s*\]$/)
  const m = liter || feld
  if (!m) return false
  const tabelle = m[1]

  const def = quelle.match(new RegExp(`const\\s+${tabelle}\\s*=\\s*\\{([\\s\\S]*?)\\n?\\}`))
  if (!def) return false
  const eintraege = def[1].split(',').map((s) => s.trim()).filter(Boolean)
  if (eintraege.length === 0) return false
  // Jeder Eintrag ist `'schluessel': NAME` oder `NAME` (Kurzform). Der WERT
  // muss in ALLEN Fällen eine statische SVG-Konstante sein — sonst käme ein
  // Fremdwert in die Tabelle.
  const schluessel = new Set()
  const nurKonstanten = eintraege.every((e) => {
    if (e.includes(':')) {
      const [links, ...rest] = e.split(':')
      schluessel.add(links.trim().replace(/^['"]|['"]$/g, ''))
      return konstanten.has(rest.join(':').trim())
    }
    schluessel.add(e)
    return konstanten.has(e)
  })
  if (!nurKonstanten) return false

  if (liter) return schluessel.has(m[3])

  // Form B: der Schlüssel ist ein Feld der Schleifendaten (`link.symbol`).
  // Sicher ist das nur, wenn ALLE Zuweisungen dieses Feldes im Quelltext
  // String-LITERALE sind und jedes Literal in der Tabelle steht. Sobald ein
  // Serverwert (`link.symbol = antwort.icon`) dazukommt, fällt der Test durch.
  const feldName = m[2]
  const zuweisungen = [...quelle.matchAll(new RegExp(`\\b${feldName}\\s*:\\s*([^,}\\n]+)`, 'g'))]
  if (zuweisungen.length === 0) return false
  return zuweisungen.every((z) => {
    const wert = z[1].trim()
    const lit = wert.match(/^(['"])([^'"]*)\1$/)
    return Boolean(lit && schluessel.has(lit[2]))
  })
}

/** Sammelt `v-html`-Bindungen (auch `:inner-html` gibt es in Vue nicht). */
function vHtmlBindungen(quelle) {
  const treffer = []
  const muster = /\sv-html\s*=\s*("([^"]*)"|'([^']*)')/g
  let m
  while ((m = muster.exec(quelle)) !== null) {
    treffer.push(m[2] !== undefined ? m[2] : m[3])
  }
  return treffer
}

// ── 1. v-html nur an statische Icons oder durch DOMPurify ───────────────────

test('SEC-9 (S1): `v-html` ist nirgends an Nutzer-/Serverdaten gebunden', () => {
  const verstoesse = []
  const erlaubt = []

  for (const datei of sammleDateien()) {
    const roh = readFileSync(datei, 'utf8')
    const quelle = ohneKommentare(roh)
    if (!/\sv-html\s*=/.test(quelle)) continue

    const konstanten = statischeIconKonstanten(quelle)

    for (const ausdruck of vHtmlBindungen(quelle)) {
      const wert = ausdruck.trim()
      if (konstanten.has(wert)) {
        erlaubt.push(`${relativ(datei)}: v-html="${wert}" (statische SVG-Konstante)`)
        continue
      }
      if (istDesinfizierenderAufruf(wert, quelle)) {
        erlaubt.push(`${relativ(datei)}: v-html="${wert}" (durch DOMPurify belegt)`)
        continue
      }
      if (istStatischeTabelle(wert, quelle, konstanten)) {
        erlaubt.push(`${relativ(datei)}: v-html="${wert}" (Schlüssel in statischer Symbol-Tabelle)`)
        continue
      }
      verstoesse.push(`${relativ(datei)}: v-html="${wert}"`)
    }
  }

  assert.deepEqual(
    verstoesse,
    [],
    'SEC-9 (S1): v-html darf NUR an eine fest einprogrammierte SVG-Konstante '
      + 'oder an einen mit DOMPurify belegten Sanitizer-Aufruf gebunden sein. '
      + 'Gefundene Verstöße (Nutzerdaten würden roh als HTML gerendert): '
      + verstoesse.join(' | '),
  )
  // Der Wächter muss überhaupt etwas sehen — sonst prüft er ins Leere.
  assert.ok(erlaubt.length > 0, 'SEC-9 (S1): keine einzige erlaubte v-html-Stelle gefunden — Muster greift nicht mehr')
})

// ── 2. Kein innerHTML & Co. mit Fremdwerten ─────────────────────────────────

test('SEC-9 (S1): kein innerHTML/insertAdjacentHTML/outerHTML-Schreiben', () => {
  const verstoesse = []

  for (const datei of sammleDateien()) {
    const quelle = ohneKommentare(readFileSync(datei, 'utf8'))
    const zeilen = quelle.split('\n')
    zeilen.forEach((zeile, i) => {
      // Zuweisung in innerHTML/outerHTML
      if (/\.(innerHTML|outerHTML)\s*(\+?=)/.test(zeile)) {
        verstoesse.push(`${relativ(datei)}:${i + 1}: ${zeile.trim()}`)
      }
      // insertAdjacentHTML(...) baut immer Markup aus einem String
      if (/\.insertAdjacentHTML\s*\(/.test(zeile)) {
        verstoesse.push(`${relativ(datei)}:${i + 1}: ${zeile.trim()}`)
      }
    })
  }

  assert.deepEqual(
    verstoesse,
    [],
    'SEC-9 (S1): Markup darf niemals über innerHTML/insertAdjacentHTML/'
      + 'outerHTML gebaut werden. Gefunden: ' + verstoesse.join(' | '),
  )
})

// ── 3. Druckfenster: jede Fremdwert-Stelle ist escaped (S2-Beleg) ───────────

test('SEC-9 (S2): `document.write`-Ausnahmen sind ausnahmslos escaped', () => {
  const ERLAUBT = new Set(['diakonos/components/registrierung/RegLinkTeilen.vue'])
  const verstoesse = []
  let geprueft = 0

  for (const datei of sammleDateien()) {
    const quelle = ohneKommentare(readFileSync(datei, 'utf8'))
    if (!/\bdocument\.write\s*\(/.test(quelle)) continue
    geprueft += 1
    if (!ERLAUBT.has(relativ(datei))) {
      verstoesse.push(`${relativ(datei)}: document.write ohne Eintrag in ERLAUBT`)
      continue
    }
    // Jede Interpolation im geschriebenen String muss escapeHtml(...) sein.
    // `daten` ist ein `data:`-Bild (aus dem eigenen QR-Renderer) und steht in
    // einem `src`-Attribut — dort ist Escape nicht nötig, aber auch nicht
    // schädlich; es wird deshalb mitgeprüft und ist ebenfalls escaped.
    // ON-0b: `cssWert('--x')` liefert einen Wert aus `tokens.css` und escaped
    // ihn in der Funktion selbst (dieselbe Regel wie escapeHtml) — deshalb ist
    // auch dieser Aufruf eine geschützte Stelle.
    const aufrufe = quelle.match(/document\.write\(([\s\S]*?)\n\s*\)/g) || []
    for (const aufruf of aufrufe) {
      const stellen = aufruf.match(/\$\{([^}]*)\}/g) || []
      for (const stelle of stellen) {
        const innen = stelle.slice(2, -1)
        // `daten` ist das selbst erzeugte `data:`-Bild — keine Nutzereingabe.
        if (/^\s*daten\s*$/.test(innen)) continue
        if (/(^|[^\w$.])escapeHtml\s*\(/.test(innen)) continue
        // ON-0b: Token-Wert, in der Funktion selbst escaped.
        if (/(^|[^\w$.])cssWert\s*\(/.test(innen)) continue
        verstoesse.push(`${relativ(datei)}: ungeschützte Stelle ${stelle}`)
      }
    }
  }

  assert.ok(geprueft > 0, 'SEC-9 (S2): kein document.write gefunden — Ausnahme-Liste ist veraltet')
  assert.deepEqual(verstoesse, [], 'SEC-9 (S2): ' + verstoesse.join(' | '))
})
