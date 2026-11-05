/**
 * UX1e — Alt-Knopf nach Baustein: welche `variant`/`size` ein Element des
 * Kalender-/Moderationsbereichs im gemeinsamen Knopf-System (`DkButton`) bekommt.
 *
 * WARUM ALS FUNKTION
 * Der Umbau ersetzt ~50 Alt-Knöpfe (`.btn.btn-primary`, `.btn.btn-warning`,
 * `.dk-mcard-resolve-btn`, `.sidebar-import-btn` …) durch `<DkButton>`. Die
 * Zuordnung „alte Klasse -> neue Variante“ darf nicht in jedem der neun
 * Bausteine neu geraten werden — sie steht hier EINMAL, und der Node-Test
 * (`frontend/tests/ux1e-knopf-system.test.mjs`) fuehrt sie wirklich aus.
 *
 * REGELN (Karte UX1e, „gleiche Funktion, gleiche Beschriftung, kein
 * Verhaltenswechsel“):
 *   * `.btn-primary`, `.dk-btn-primary`, `.btn-success` -> `primary`
 *   * `.btn-danger`, `.dk-btn-danger`                     -> `danger`
 *   * `.btn-warning`, `.dk-btn-warning`                   -> `secondary`
 *     „Warn“ ist keine eigene Knopfart: das System kennt genau
 *     primary/secondary/ghost/danger. Eine gefahrlose Zwischenaktion
 *     („Trotzdem speichern“, „Vorschlagen“) ist ein SEKUNDÄRER Knopf; die
 *     Warnung traegt der Text und das Symbol, nicht die Knopf-Farbe.
 *   * `.btn-secondary`, `.dk-btn-secondary`, ohne Variante -> `secondary`
 *   * `.dk-btn-ghost`                                      -> `ghost`
 *   * `.btn-xs`/`.btn-sm`/`.dk-btn-sm`                     -> `sm` (kleinste
 *     Groesse des Systems; ein eigenes `xs` wird nicht erfunden)
 *   * alles andere                                         -> `md`
 */

/** Reihenfolge zaehlt: gefaehrlich vor auffaellig vor ruhig. */
const VARIANTEN_REIHENFOLGE = [
  ['danger', ['btn-danger', 'dk-btn-danger']],
  ['primary', ['btn-primary', 'dk-btn-primary', 'btn-success', 'dk-btn-success']],
  ['secondary', ['btn-warning', 'dk-btn-warning', 'btn-secondary', 'dk-btn-secondary']],
  ['ghost', ['dk-btn-ghost', 'btn-ghost']],
]

/**
 * Groessen des Systems: `DkButton` kennt genau `sm` und `md`. Das alte
 * `.btn-xs` gibt es dort nicht — es wird `sm` (die kleinste vorhandene
 * Groesse), nicht neu erfunden.
 */
const GROESSEN_REIHENFOLGE = [
  ['sm', ['btn-xs', 'dk-btn-xs', 'btn-sm', 'dk-btn-sm']],
]

/**
 * Klassenliste (`class="…"`) in ihre Einzelklassen zerlegen.
 * @param {string} klassen
 * @returns {string[]}
 */
export function klassenListe(klassen) {
  return String(klassen || '')
    .split(/\s+/)
    .map((k) => k.trim())
    .filter(Boolean)
}

/**
 * Alte Knopfklassen -> `{ variant, size }` fuer `DkButton`.
 * Die Variante gewinnt nach VARIANTEN_REIHENFOLGE (danger schlaegt primary),
 * die Groesse ist ohne Angabe `md`.
 *
 * @param {string} klassen  z. B. `'btn btn-warning'`
 * @returns {{ variant: string, size: string }}
 */
export function knopfAusKlassen(klassen) {
  const liste = klassenListe(klassen)
  const hat = (name) => liste.includes(name)
  let variant = 'secondary'
  for (const [name, synonyme] of VARIANTEN_REIHENFOLGE) {
    if (synonyme.some(hat)) {
      variant = name
      break
    }
  }
  let size = 'md'
  for (const [name, synonyme] of GROESSEN_REIHENFOLGE) {
    if (synonyme.some(hat)) {
      size = name
      break
    }
  }
  return { variant, size }
}

/**
 * Knopfarten, die es im System gibt. Der Test prueft, dass jede Zuordnung
 * nur diese Werte liefert — ein „warning“ im Knopf faellt damit sofort auf.
 */
export const VARIANTEN = ['primary', 'secondary', 'ghost', 'danger']
export const GROESSEN = ['sm', 'md']

/**
 * Begriffsliste (ux-gemeinsam, Manuel): Beschriftungen, die im Kalender- und
 * Moderationsbereich aus dem Bestand umbenannt werden. Beschriftungen, die
 * das Verhalten aendern wuerden („Löschen“ im Sinne von „aus der Serie
 * entfernen“), werden benannt, nicht stillschweigend getauscht.
 */
export const BESCHRIFTUNGEN = {
  // „Element“ ist Fachjargon, das Wort ist „Termin“ (Begriffsliste).
  termin: { alt: ['Element', 'Event'], neu: 'Termin' },
  // „Bestätigen“ ist in BEGRIFFE.freigeben verboten; im Kalender heisst der
  // Vorgang ohne Planbezug „Sichern“ (andere Beschriftung, gleiche Aktion).
  sichern: { alt: ['Ja, Sicher'], neu: 'Sichern' },
  // „Trotzdem speichern“ sagt nur „es wird gespeichert“ — die Folge der
  // Entscheidung (Liste bleibt mit Ueberschneidung) muss am Knopf stehen.
  trotzUeberschneidung: { alt: ['Trotzdem speichern'], neu: 'Mit Überschneidung speichern' },
}

/**
 * Ersetzt verbotene Alt-Begriffe in einem sichtbaren Text.
 * Nur ganze Woerter — „Elemente“ in „Elementname“ bleibt unberuehrt.
 * @param {string} text
 * @returns {string}
 */
export function beschriftung(text) {
  let out = String(text == null ? '' : text)
  for (const def of Object.values(BESCHRIFTUNGEN)) {
    for (const alt of def.alt) {
      out = out.replace(new RegExp(`\\b${alt.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g'), def.neu)
    }
  }
  return out
}
