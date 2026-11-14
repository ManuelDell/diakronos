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
 */
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

/** @returns {(stufe: string, rechte?: {istAdmin?: boolean, istMitgliederverwaltung?: boolean}) => boolean} */
export function echteVerwaltungsregel() {
  const quelle = readFileSync(new URL('../../src/diakonos/menue.js', import.meta.url), 'utf8')
    .replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
      "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
    .replace(/^export /gm, '')
  const context = { console }
  vm.createContext(context)
  vm.runInContext(`${quelle}\nglobalThis.__regel = verwaltungZutreffend;`, context)
  return context.__regel
}
