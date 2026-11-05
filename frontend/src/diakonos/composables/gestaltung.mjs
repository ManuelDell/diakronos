/**
 * UX1k — Prüfbare Regeln der Einstellungen-Seite „Gestaltung“ (ohne Vue).
 *
 * Warum eine eigene Datei: Sichtbarkeit, Live-Prüfung beim Tippen, Änderungs-
 * stand und Rückgängig-Meldung sind FACHLOGIK. Ein Test kann sie hier
 * AUSFÜHREN; in der Komponente wären sie nur als Quelltext lesbar
 * (`assert.match`) und damit nicht nachweisbar. Dieselbe Aufteilung wie bei
 * `website.mjs`, `anzeigename.mjs` oder `eingabeart.mjs`.
 *
 * WARUM HIER KEINE TOKEN-LISTE STEHT
 * ----------------------------------
 * Die einzige Quelle der einstellbaren Maße ist der Server
 * (`gestaltung.lesen` → `felder[]` mit `token`, `standard`, `min`, `max`,
 * `schritt`, `gruppe`, `wert`; UX1j). Diese Datei liest die Felder und prüft
 * gegen die GELIEFERTEN Grenzen. Eine zweite Liste im Frontend könnte driften
 * und würde etwas anbieten, das der Server ablehnt (Prinzip I4: Ungültiges
 * gar nicht erst anbieten).
 *
 * Der Server bleibt verbindlich: er prüft Bereich UND die aufsteigende
 * Abstands-Skala (`gestaltung/tokens.py`). Die Prüfung hier ist die
 * Live-Rückmeldung beim Tippen — sie sagt dasselbe, bevor jemand absendet.
 */

/** Rolle, die den Bereich sieht — dieselbe wie im Server (`gestaltung/api.py`). */
export const GESTALTUNG_ROLLE = 'System Manager'

/** Einheit aller Maße (der Server liefert sie mit; hier nur der Rückfall). */
const EINHEIT = 'px'

/**
 * Darf dieser Benutzer die Gestaltung einstellen?
 *
 * Grundlage ist die Rollenliste der Sitzung (`window.__DIakonosBOOT.roles`,
 * dieselbe Quelle wie bei `darfWebsite`). Nur Komfort: der Server verweigert
 * jedem anderen mit 403, und die Oberfläche blendet den Bereich zusätzlich aus.
 *
 * @param {{rollen?: string[]|null}} [optionen]
 * @returns {boolean}
 */
export function darfGestaltung({ rollen = null } = {}) {
  const vorhanden = new Set(
    (Array.isArray(rollen) ? rollen : []).map(r => String(r || '').trim()),
  )
  return vorhanden.has(GESTALTUNG_ROLLE)
}

/** Zahl aus einer Eingabe lesen — `null`, wenn es keine ganze Zahl ist. */
export function zahl(wert) {
  // Zahl ODER Text: das Formular liefert Text (`"40"`), die Serverantwort
  // Zahlen. Beides ist hier gültig (im Browser gefunden: `pruefeFeld` lehnte
  // die Textform ab, `pruefeSkala` behandelte gültige Eingaben dann als
  // „unbrauchbar“ und prüfte gegen die Standards).
  if (typeof wert === 'number') {
    if (!Number.isFinite(wert)) return null
    return Number.isInteger(wert) ? wert : null
  }
  const text = String(wert ?? '').trim()
  // Erlaubt „16“ und „16px“ — dieselbe Form wie der Server (`zahl_aus`).
  const treffer = /^(\d{1,4})(?:\s*px)?$/i.exec(text)
  return treffer ? Number(treffer[1]) : null
}

/**
 * Ein Feld des Servers prüfen.
 *
 * @param {{token: string, min: number, max: number}} feld
 * @param {unknown} eingabe  Text oder Zahl aus dem Eingabefeld
 * @returns {{ok: boolean, wert: number|null, text: string}} `text` sagt, was
 *   jetzt zu tun ist (leer, wenn alles stimmt) — Prinzip I4.
 */
export function pruefeFeld(feld, eingabe) {
  const name = String(feld?.token || '')
  const wert = zahl(eingabe)
  if (wert === null) {
    return {
      ok: false, wert: null,
      text: `${name}: Bitte eine ganze Zahl in Pixeln angeben (${feld?.min} bis ${feld?.max}).`,
    }
  }
  if (wert < Number(feld.min) || wert > Number(feld.max)) {
    return {
      ok: false, wert,
      text: `${name}: ${wert} ${EINHEIT} liegt außerhalb des erlaubten Bereichs `
        + `(${feld.min} bis ${feld.max} ${EINHEIT}).`,
    }
  }
  return { ok: true, wert, text: '' }
}

/**
 * Die Abstands-Skala prüfen: streng aufsteigend entlang der Kette, die der
 * SERVER vorgibt (wie `pruefe_skala` im Server).
 *
 * Geprüft werden NUR die Token aus `ordnung` (UX1j2: `--sp-1 … --sp-8`), in
 * genau dieser Reihenfolge. Es gibt keine eigene Tokenliste und keinen Filter
 * nach `gruppe`: `--pad`, `--abstand-*` und `--karte-innen` stehen zwar in
 * derselben Anzeigegruppe, sind aber keine Kettenglieder. Token aus `ordnung`,
 * zu denen kein Feld geliefert wurde, werden übersprungen.
 *
 * Ist eine Eingabe unbrauchbar (keine ganze Zahl, außerhalb des Bereichs),
 * zählt der Standard des Feldes — dieselbe Regel wie im Server
 * (`wert_oder_standard`).
 *
 * @param {Array<{token: string, gruppe: string, standard: number, min: number, max: number}>} felder
 * @param {Record<string, unknown>} eingaben  Token -> Text aus dem Feld
 * @param {string[]} ordnung  Kettenglieder in aufsteigender Reihenfolge, vom
 *   Server (`stand.skala_ordnung`); leer = nichts zu prüfen.
 * @returns {{ok: boolean, text: string, paare: Array<[string, string]>}}
 *   `paare` nennt das erste Token-Paar, das die Ordnung bricht (für die
 *   Markierung am Feld); `text` sagt, was jetzt zu tun ist.
 */
export function pruefeSkala(felder, eingaben = {}, ordnung = []) {
  // UX1j2: Die Kette kommt vom Server (`stand.skala_ordnung`, Quelle
  // `gestaltung/tokens.py` SKALA_TOKEN = --sp-1 … --sp-8). KEINE Tokenliste und
  // KEIN Filter nach `gruppe`: `--pad`, `--abstand-*` und `--karte-innen` stehen
  // in derselben Anzeigegruppe, sind aber keine Kettenglieder (sonst galt
  // „--sp-8 (64 px) muss kleiner sein als --pad (16 px)“).
  const reihenfolge = Array.isArray(ordnung) ? ordnung : []
  const nachToken = new Map(
    (Array.isArray(felder) ? felder : []).filter(Boolean).map(f => [f.token, f]))
  const werte = reihenfolge
    .filter(token => nachToken.has(token))
    .map(token => {
      const feld = nachToken.get(token)
      const geprueft = pruefeFeld(feld, eingaben[token])
      return { token, wert: geprueft.ok ? geprueft.wert : Number(feld.standard) }
    })
  for (let i = 0; i < werte.length - 1; i += 1) {
    const a = werte[i]
    const b = werte[i + 1]
    if (b.wert > a.wert) continue
    return {
      ok: false,
      paare: [[a.token, b.token]],
      text: `Die Abstände müssen aufsteigend bleiben: ${a.token} (${a.wert} `
        + `${EINHEIT}) muss kleiner sein als ${b.token} (${b.wert} ${EINHEIT}). `
        + `Bitte zuerst ${a.token} verkleinern oder ${b.token} vergrößern.`,
    }
  }
  return { ok: true, paare: [], text: '' }
}

/**
 * Einen Eingabewert für den Server lesbar machen: ganzzahlig, sonst Standard.
 * Der Server prüft erneut und lehnt ab — hier wird nichts geschönt.
 *
 * @param {Array<{token: string, standard: number}>} felder
 * @param {Record<string, unknown>} eingaben
 * @returns {Record<string, number>}
 */
export function werteFuerServer(felder, eingaben = {}) {
  const rumpf = {}
  for (const feld of (Array.isArray(felder) ? felder : [])) {
    const geprueft = pruefeFeld(feld, eingaben[feld.token])
    rumpf[feld.token] = geprueft.ok ? geprueft.wert : Number(feld.standard)
  }
  return rumpf
}

/**
 * Welche Felder weichen vom gespeicherten Stand ab? (für „Speichern“
 * freischalten und den Abweichungs-Hinweis)
 */
export function geaenderteFelder(felder, eingaben = {}) {
  const geaendert = []
  for (const feld of (Array.isArray(felder) ? felder : [])) {
    const geprueft = pruefeFeld(feld, eingaben[feld.token])
    if (!geprueft.ok) {
      geaendert.push(feld.token)
      continue
    }
    if (geprueft.wert !== Number(feld.wert)) geaendert.push(feld.token)
  }
  return geaendert
}

/**
 * Stand einer Rückgängig-Meldung (Prinzip I2: rückgängig MACHEN statt fragen).
 *
 * Bis UX2a ein echtes „Rückgängig“ in der Oberfläche hat, ist die Meldung der
 * Ersatz: sie nennt, WAS zurückgesetzt wurde, und wie es weitergeht. Nach ihr
 * lädt die Oberfläche die alten Werte erneut vom Server — der Stand in den
 * Feldern ist dann wieder der gespeicherte, nicht der gehoffte.
 *
 * @param {{ziel: 'feld'|'alle', token?: string, alt?: number, standard?: number}} vorgang
 * @returns {{text: string, art: string}}
 */
export function rueckgaengigMeldung({ ziel, token = '', alt = 0, standard = 0 } = {}) {
  if (ziel === 'feld') {
    return {
      text: `${token} steht wieder auf dem Standard von ${standard} ${EINHEIT} `
        + `(vorher ${alt} ${EINHEIT}). Rückgängig geht das nicht in der Oberfläche — `
        + `tippe den alten Wert erneut ein und speichere.`,
      art: 'info',
    }
  }
  return {
    text: 'Alle Abweichungen wurden entfernt; die Oberfläche steht wieder auf den '
      + 'Standardwerten. Rückgängig geht das nicht in der Oberfläche — wer eigene Werte '
      + 'braucht, stellt sie erneut ein und speichert.',
    art: 'info',
  }
}

/**
 * Adresse von `gestaltung.css` mit Zähler — für das Neuladen NACH dem
 * Speichern, ohne die Seite neu zu laden.
 *
 * Der Abfrageteil (`?v=`) ist der einzige Weg, den Browser-Zwischenspeicher zu
 * umgehen, ohne die Datei umzubenennen; er wird bei jedem Aufruf neu gewählt.
 * Der Pfad kommt vom Server (`window.__DIakonosBOOT`/`basis.js`), hier nur die
 * Ergänzung.
 *
 * @param {string} pfad  fertige Adresse (z. B. `/diakronos/gestaltung.css`)
 * @param {string|number} stand  beliebiger Zähler (Hash oder Zeitstempel)
 * @returns {string}
 */
export function frischeCssAdresse(pfad, stand) {
  const basis = String(pfad || '').split('?')[0]
  const wert = String(stand ?? '').trim() || String(neuGezaehlt())
  return `${basis}?v=${encodeURIComponent(wert)}`
}

let zaehler = 0
function neuGezaehlt() {
  zaehler += 1
  return `${zaehler}`
}
