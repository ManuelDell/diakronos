/**
 * UI-R8 — „Was bewirkt welche Rolle?“: EINE Lesehilfe für die ⓘ-Knöpfe und die
 * Seite „Rollen & Rechte“.
 *
 * Die TEXTE stehen NICHT hier: sie kommen ausschließlich aus
 * `api.rechte.get_rollen_erklaerung()` (Backend `rechte/erklaerung.py`, neben
 * dem Rechte-Kern). Das gilt seit R-12 auch für die ÜBERSCHRIFTEN
 * (`modul_titel`, `stufen_titel`), die Reihenfolge (`systemrollen_reihenfolge`)
 * und die Einleitungen der fünf Abschnitte (`einleitungen`) — das Frontend
 * führt KEINE eigene Fassung mehr.
 *
 * Dieses Modul formt die Antwort nur in die Form, die die Oberfläche zeigt:
 *
 *   1. Welche Erklärung gehört zu diesem Rollennamen? (`erklaerungFuer`)
 *   2. In welcher Reihenfolge erscheinen die Abschnitte? (`abschnitte`)
 *   3. Was sagt die Oberfläche, wenn die Quelle fehlt? (`hinweisOhneQuelle`)
 *
 * Grundsatz der Oberfläche: sie entscheidet NIE über Rechte. Fehlt ein Text
 * oder die ganze Quelle, wird das gesagt — nicht erfunden.
 */

/** Leerform einer Erklärung, damit die Anzeige nie auf `undefined` läuft. */
export const LEER = Object.freeze({ titel: '', kurz: '', darf: [], darf_nicht: [] })

/**
 * Reihenfolge der Gruppenrollen. Die ist KEIN Rollenwissen, sondern die
 * Darstellungsreihenfolge dieser vier Zeilen (Leitung zuerst, dann Leserolle) —
 * das Backend liefert sie nicht. Alles andere (Systemrollen, Module, Stufen)
 * kommt ausschließlich aus der Quelle: UI-R8b hat die drei Not-Listen
 * `SYSTEMROLLEN_REIHENFOLGE`, `MODULE_REIHENFOLGE` und `STUFEN_REIHENFOLGE`
 * entfernt — sie waren eine zweite Kopie von Rollenwissen und überstimmten
 * den Server.
 */
export const GRUPPENROLLEN_REIHENFOLGE = Object.freeze(['HV', 'MV', 'GL', 'Mitglied'])

/** Die fünf Abschnitte der Seite — Kennungen wie `einleitungen` im Backend. */
export const ABSCHNITTE = Object.freeze(['systemrollen', 'gast', 'gruppenrollen', 'module', 'stufen'])

/** Text, wenn die Quelle (noch) fehlt — sagt, was los ist, statt zu raten. */
export const HINWEIS_OHNE_QUELLE =
  'Die Erklärungen konnten nicht geladen werden. Die Rollen selbst gelten '
  + 'unverändert — es fehlt nur die Beschreibung, was sie bewirken.'

/**
 * Der Text, den die Seite bei einem Ladefehler zeigt (UI-R8b).
 *
 * Review R8-7: der Satz „die Rollen gelten unverändert“ steht IMMER da — ein
 * nacktes „HTTP 500“ erklärt niemandem, dass die Rollen trotzdem gelten. Ein
 * Grund des Servers hängt ergänzend dahinter, ersetzt den Satz aber nie.
 *
 * @param {unknown} fehler  das geworfene Etwas (Error, String, null)
 * @returns {string}
 */
export function ladefehlerText(fehler) {
  const grund = String(fehler?.message ?? fehler ?? '').trim()
  return grund ? `${HINWEIS_OHNE_QUELLE} (${grund})` : HINWEIS_OHNE_QUELLE
}

/** Länge eines Feldes sicher lesen (immer ein Array aus Zeichenketten). */
function liste(wert) {
  if (!Array.isArray(wert)) return []
  return wert.map((e) => String(e ?? '').trim()).filter(Boolean)
}

/**
 * Eine Erklärung aus der Serverantwort normalisieren.
 *
 * @param {{titel?: string, kurz?: string, darf?: string[], darf_nicht?: string[]}|null|undefined} roh
 * @returns {{titel: string, kurz: string, darf: string[], darf_nicht: string[]}}
 */
export function normalisiereErklaerung(roh) {
  if (!roh || typeof roh !== 'object') return { ...LEER, darf: [], darf_nicht: [] }
  return {
    titel: String(roh.titel ?? '').trim(),
    kurz: String(roh.kurz ?? '').trim(),
    darf: liste(roh.darf),
    darf_nicht: liste(roh.darf_nicht),
  }
}

/**
 * Die Erklärung zu einem Rollennamen — auch dann, wenn die Oberfläche den
 * Namen anders schreibt als das Backend.
 *
 * „Systemmanager“ (so steht die Rolle im Menü- und Rechtekatalog) und
 * „System Manager“ (so heißt sie in `Has Role`) meinen dieselbe Rolle; ein
 * ⓘ darf daran nicht scheitern.
 *
 * @param {Record<string, object>|null|undefined} quelle  `systemrollen` der Antwort
 * @param {string} name
 * @returns {object|null} normalisierte Erklärung oder null (dann KEIN Knopf)
 */
export function erklaerungFuer(quelle, name) {
  const gesucht = schluessel(name)
  if (!gesucht || !quelle || typeof quelle !== 'object') return null
  for (const [rollenname, roh] of Object.entries(quelle)) {
    if (schluessel(rollenname) === gesucht) return normalisiereErklaerung(roh)
  }
  return null
}

/** Vergleichsform eines Rollennamens: Kleinbuchstaben, ohne Trennzeichen. */
function schluessel(name) {
  return String(name ?? '').toLowerCase().replace(/[\s_\-]+/g, '')
}

/**
 * Einträge in der Reihenfolge der Anzeige.
 *
 * @param {Record<string, object>|null|undefined} quelle
 * @param {readonly string[]|null|undefined} reihenfolge  die des BACKENDS, sonst die Not-Liste
 * @returns {Array<{schluessel: string, erklaerung: object}>} nur vorhandene
 */
export function inReihenfolge(quelle, reihenfolge) {
  if (!quelle || typeof quelle !== 'object') return []
  const namen = Object.keys(quelle)
  const sortiert = []
  for (const name of liste(reihenfolge)) if (!sortiert.includes(name)) sortiert.push(name)
  for (const name of namen) if (!sortiert.includes(name)) sortiert.push(name)
  return sortiert
    .filter((name) => namen.includes(name))
    .map((name) => ({ schluessel: name, erklaerung: normalisiereErklaerung(quelle[name]) }))
}

/** Objekt (Kennung → Text) als geordnete Liste mit Überschrift aus der QUELLE. */
function texte(quelle, reihenfolge, titel) {
  if (!quelle || typeof quelle !== 'object') return []
  const namen = Object.keys(quelle)
  const gegeben = liste(reihenfolge)
  const sortiert = [...gegeben.filter((n) => namen.includes(n)),
    ...namen.filter((n) => !gegeben.includes(n))]
  return sortiert
    .map((n) => ({
      schluessel: n,
      // Die Überschrift kommt aus `modul_titel`/`stufen_titel` des Backends;
      // fehlt sie, steht die Kennung da — kein erfundener Titel.
      titel: String(titel?.[n] ?? n).trim(),
      text: String(quelle[n] ?? '').trim(),
    }))
    .filter((e) => e.text)
}

/**
 * Die Einleitung zu einem Abschnitt — wörtlich aus `einleitungen` des
 * Backends. Fehlt sie, bleibt sie LEER: die Seite schreibt keinen eigenen Text.
 *
 * @param {object|null|undefined} antwort
 * @param {'systemrollen'|'gast'|'gruppenrollen'|'module'|'stufen'} abschnitt
 * @returns {string}
 */
export function einleitung(antwort, abschnitt) {
  const texte = antwort && typeof antwort === 'object' ? antwort.einleitungen : null
  if (!texte || typeof texte !== 'object') return ''
  return String(texte[abschnitt] ?? '').trim()
}

/**
 * Die Antwort des Servers in die fünf Abschnitte der Seite bringen.
 *
 * `systemrollen` und `gruppenrollen` sind Objekte (Rollenname → Erklärung);
 * `gast` ist EIN Eintrag; `module` und `stufen` sind Objekt (Kennung → Text).
 * Jeder Abschnitt trägt seine Einleitung aus der Quelle. Fehlt ein Abschnitt,
 * ist die Liste leer — die Seite zeigt dann nichts Erfundenes.
 *
 * @param {object|null|undefined} antwort
 * @returns {{
 *   systemrollen: Array<{schluessel: string, erklaerung: object}>,
 *   gast: object|null,
 *   gruppenrollen: Array<{schluessel: string, erklaerung: object}>,
 *   module: Array<{schluessel: string, titel: string, text: string}>,
 *   stufen: Array<{schluessel: string, titel: string, text: string}>,
 *   einleitungen: Record<string, string>,
 *   leer: boolean,
 * }}
 */
export function abschnitte(antwort) {
  const quelle = antwort && typeof antwort === 'object' ? antwort : {}
  // Reihenfolge NUR vom Server (UI-R8b): `systemrollen_reihenfolge`, sonst die
  // Schlüsselreihenfolge der Antwort — keine Not-Liste im Frontend. Module und
  // Stufen haben keine eigene Reihenfolge in der Antwort; sie stehen in der
  // Reihenfolge, in der der Server sie liefert.
  const systemrollen = inReihenfolge(quelle.systemrollen, quelle.systemrollen_reihenfolge)
  const gruppenrollen = inReihenfolge(quelle.gruppenrollen, GRUPPENROLLEN_REIHENFOLGE)
  const gast = quelle.gast ? normalisiereErklaerung(quelle.gast) : null
  const module = texte(quelle.module, null, quelle.modul_titel)
  const stufen = texte(quelle.stufen, null, quelle.stufen_titel)
  return {
    systemrollen,
    gast,
    gruppenrollen,
    module,
    stufen,
    einleitungen: Object.fromEntries(ABSCHNITTE.map((a) => [a, einleitung(quelle, a)])),
    leer: !systemrollen.length && !gruppenrollen.length && !gast && !module.length && !stufen.length,
  }
}

/**
 * Rollen aus der festen Zugangsliste, zu denen es eine Erklärung gibt.
 * Für die ⓘ neben jeder Zeile in der Rollenauswahl.
 *
 * @param {string[]|null|undefined} rollen  z. B. `rollen_waehlbar`
 * @param {Record<string, object>|null|undefined} quelle  `systemrollen`
 * @returns {Array<{name: string, erklaerung: object}>}
 */
export function erklaerteRollen(rollen, quelle) {
  if (!Array.isArray(rollen)) return []
  const gesehen = new Set()
  const ergebnis = []
  for (const name of rollen) {
    const erklaerung = erklaerungFuer(quelle, name)
    if (!erklaerung || gesehen.has(name)) continue
    gesehen.add(name)
    ergebnis.push({ name, erklaerung })
  }
  return ergebnis
}

/**
 * Hat das Backend für diese Rolle KEINE Erklärung, obwohl die Rolle wählbar
 * ist? Dann bleibt die Stelle leer und die Oberfläche sagt es — statt einen
 * Text zu erfinden.
 */
export function fehlendeErklaerung(rollen, quelle) {
  if (!Array.isArray(rollen)) return []
  return rollen.filter((name) => !erklaerungFuer(quelle, name))
}
