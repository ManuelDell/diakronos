/**
 * UI-R10b (Review, Punkt 2) — die ECHTE Verwaltungsregel für Router-VMs.
 *
 * `router.js` führt seit UI-R10b keine eigene Fassung der Regel mehr: es
 * importiert `verwaltungZutreffend` aus `menue.js`, und sein Rückfall ist
 * `false` (fail closed). Test-Harnesse, die `router.js` in einer vm ausführen
 * und dabei die `import`-Zeilen streichen, bekommen ohne diesen Helfer NUR
 * noch gesperrte Verwaltungsseiten — richtig für den Betrieb, aber die
 * Harnesse wollen ja die Seiten öffnen.
 *
 * Deshalb holen sie die Regel EINMAL von hier (aus `menue.js`, nicht
 * nachgebaut) und setzen sie in ihrer vm als `const verwaltungZutreffend`
 * VOR dem Router-Quelltext ein. Keine zweite Wahrheit: der Test misst die
 * Regel, die im Betrieb gilt.
 *
 * CHAT-R2d-2: dasselbe gilt für die ADRESSEN des umgezogenen Personenbereichs.
 * Der Router bildet seine Ziele seit dieser Karte direkt über
 * `PERSONENVERWALTUNG_BASIS`, `anfragenUnterbereichHref` und
 * `personenReiterHref` — der frühere Rückfall im Router ist entfallen (er war
 * eine zweite Kopie der Adressregel). Ohne die drei Namen liefe eine Harness
 * in einen ReferenceError. Sie kommen ebenfalls aus `menue.js`.
 */
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

/** Die menue.js-Quelle, importfrei gemacht (nur die Website-Rollen ersetzt). */
function menueQuelle() {
  return readFileSync(new URL('../../src/diakonos/menue.js', import.meta.url), 'utf8')
    .replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
      "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
    .replace(/^export /gm, '')
}

/** @returns {(stufe: string, rechte?: {istAdmin?: boolean, istMitgliederverwaltung?: boolean}) => boolean} */
export function echteVerwaltungsregel() {
  const context = { console }
  vm.createContext(context)
  vm.runInContext(`${menueQuelle()}\nglobalThis.__regel = verwaltungZutreffend;`, context)
  return context.__regel
}

/**
 * Die drei Adress-Namen aus `menue.js` für eine Router-vm —
 * `PERSONENVERWALTUNG_BASIS`, `anfragenUnterbereichHref`, `personenReiterHref`.
 * Sie werden als `const`-Zeilen VOR den Router-Quelltext gesetzt (die VM
 * streicht dessen `import`-Zeilen).
 *
 * @returns {{PERSONENVERWALTUNG_BASIS: string,
 *            anfragenUnterbereichHref: (bereich?: string, eingebettet?: boolean) => string,
 *            personenReiterHref: (id: string, eingebettet?: boolean) => string}}
 */
export function echtePersonenAdressen() {
  const context = { console }
  vm.createContext(context)
  vm.runInContext(`${menueQuelle()}
globalThis.__adressen = {
  PERSONENVERWALTUNG_BASIS, anfragenUnterbereichHref, personenReiterHref,
};`, context)
  return context.__adressen
}

/**
 * Die Zeilen, die eine Router-vm VOR dem Quelltext braucht: die echte
 * Verwaltungsregel und die echten Personen-Adressen. EIN Aufruf, damit keine
 * Harness eine der beiden Attrappen vergisst.
 *
 * @returns {{regel: Function, adressen: object, vorspann: string}}
 */
export function routerAttrappen() {
  const regel = echteVerwaltungsregel()
  const adressen = echtePersonenAdressen()
  const vorspann = [
    `const verwaltungZutreffend = globalThis.__regel`,
    `const PERSONENVERWALTUNG_BASIS = ${JSON.stringify(adressen.PERSONENVERWALTUNG_BASIS)}`,
    `const anfragenUnterbereichHref = globalThis.__adressen.anfragenUnterbereichHref`,
    `const personenReiterHref = globalThis.__adressen.personenReiterHref`,
  ].join('\n')
  return { regel, adressen, vorspann }
}
