/**
 * UX1f — Alt-Knopf nach Baustein: welche `variant`/`size` ein Element des
 * Personen-/Gruppen-/Registrierungs-/Gast-Bereichs im gemeinsamen Knopf-System
 * (`DkButton`) bekommt.
 *
 * WARUM HIER UND NICHT NEBEN DEM KALENDER
 * UX1e hat die Zuordnung „alte Klasse -> neue Variante“ für den Kalender
 * einmal festgeschrieben (`components/kronos/knopfvarianten.mjs`). UX1f baut
 * dieselben Regeln für die übrigen Bereiche; damit es nicht zwei Fassungen
 * gibt, die auseinanderlaufen, wohnt die Regel jetzt in `diakonos/` und der
 * Kalender reicht sie weiter. Wer eine Regel ändert, ändert sie EINMAL hier.
 *
 * REGELN (Karten UX1e/UX1f, „gleiche Funktion, gleiche Beschriftung, kein
 * Verhaltenswechsel“):
 *   * `.btn-primary`, `.btn-success`                      -> `primary`
 *   * `.btn-danger`                                       -> `danger`
 *   * `.btn-warning`                                      -> `secondary`
 *     „Warn“ ist keine eigene Knopfart: das System kennt genau
 *     primary/secondary/ghost/danger. Eine gefahrlose Zwischenaktion
 *     („Trotzdem speichern“, „Vorschlagen“) ist ein SEKUNDÄRER Knopf; die
 *     Warnung traegt der Text und das Symbol, nicht die Knopf-Farbe.
 *   * `.btn`, `.btn-secondary`, ohne Variante              -> `secondary`
 *   * `.btn-ghost`, Textknopf (`.…-link`)                  -> `ghost`
 *   * `.btn-xs`/`.btn-sm`                                  -> `sm` (kleinste
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
 * Textknöpfe in einem Satz („Bitte die vorhandene Person **öffnen** statt …“).
 * Sie sind keine Aktion der Ansicht, sondern ein Weg im Fließtext — im System
 * also `ghost`, nie ein gefüllter Knopf (S1: genau EIN Primärknopf), und sie
 * entstehen im Umbau aus den alten `*-btn`-Eigenklassen.
 *
 * Bewusst NICHT erfasst:
 *   * `*-(btn|button)` ohne Zusatz — das ist die Sammel-Familie der
 *     Bausteine (`.add-row-btn`, `.sidebar-import-btn`); deren Zuordnung
 *     entscheidet die Klasse daneben (btn-primary/btn-warning …).
 *   * `*-link` — `grup-link` ist ein Verweis im Fließtext, kein Knopf. Wer
 *     einen Weg im Satz auf DkButton umstellt, gibt ihm `ghost` ausdrücklich
 *     (so in MitgliedHinzufuegenDialog.vue), statt es zu raten.
 */
const TEXTKNOPF = /(?<![\w-])[\w-]*-(?:btn|button)(?![\w-])/

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
  // Kein Klassenname der Knopfreihe, aber ein Textknopf: `ghost`.
  if (variant === 'secondary' && !VARIANTEN_REIHENFOLGE.some(([, s]) => s.some(hat))) {
    if (liste.some((k) => TEXTKNOPF.test(k))) variant = 'ghost'
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
 * Begriffsliste (ux-gemeinsam, Manuel): Beschriftungen, die in den Bereichen
 * dieser Karte umbenannt werden. Beschriftungen, die das Verhalten aendern
 * wuerden, werden benannt, nicht stillschweigend getauscht.
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
  // UX1f: Anlegen · Löschen (dauerhaft) · Entfernen (aus etwas) ·
  // Erneut versuchen · Schließen (ohne Änderung) · Abbrechen (Eingabe
  // verwerfen). Ein „abbrechen“, das eine Eingabe verwirft, bleibt also
  // „Abbrechen“; ein Weg ohne Änderung heisst „Schließen“.
  //
  // „Speichern“ bleibt „Speichern“: bei einer Änderung ist das die
  // Hauptaktion, nicht das Anlegen.
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
