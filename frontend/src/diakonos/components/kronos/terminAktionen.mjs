/**
 * UX2e5 — Terminliste: das „⋯" je Termin.
 *
 * Die Bibliothek @event-calendar/build besitzt ihre Knoten: nach jedem
 * `refetchEvents()` (auch nach dem Löschen eines Termins) baut sie die
 * `<article class="ec-event">`-Zeilen NEU. Alles, was wir in eine Zeile
 * hineinschreiben, ist danach fort; eingerichtete Klick-Haken (die Bibliothek
 * meldet für einen Knopf in der Zeile nur „noAction") und Maße gelten für
 * einen Knoten, den es nicht mehr gibt.
 *
 * Deshalb ist der „⋯"-Knopf ein UNABHÄNGIGER Knoten aus dem Bauteil:
 *
 *   - Er ist ein GESCHWISTER seiner Zeile: `article` direkt dahinter, im
 *     `.ec-day`-Container (Tageskopf über alle Spalten, der Knopf sitzt in
 *     Zeilenhöhe). Es wird NIE ein Knoten der Bibliothek verschoben oder in
 *     eine fremde Hülle gesteckt (Vorgabe aus dem Review UX2e3).
 *   - `zuordnen()` ist ein idempotenter Abgleich, den `eventDidMount` UND
 *     `eventWillUnmount` anstoßen: Knöpfe per Termin-Kennung den Artikeln
 *     zuordnen, direkt dahinter setzen, Waisen entfernen. Kein
 *     ResizeObserver (nie einer je Knopf; die Maße prüft `passt()` beim
 *     Anstoßen — der Abgleich läuft beim Einbau, bei jedem Neuladen und beim
 *     Ansichtswechsel, also immer dann, wenn sich etwas geändert haben KANN).
 *   - Im `article` selbst steht kein Knopf (das `article` ist selbst ein
 *     Knopf — verschachtelte interaktive Elemente sind unzulässig).
 *
 * Die Regeln funktionieren auf jedem Knoten, der `querySelectorAll`/
 * `children` kennt — deshalb prüft sie der Node-Test MIT der echten
 * Bibliothek in jsdom, und der Browser prüft dasselbe DOM.
 */

/** Klasse des Halters, der EINEN „⋯"-Knopf an SEINE Zeile bindet. */
export const HALTER_KLASSE = 'kronos-liste-aktionen-halter'
/** Kennung des Halters (`data-termin` = Termin-Kennung). */
export const KENNUNG_ATTRIBUT = 'data-termin'
/** Container der Liste: je Tag ein `.ec-day`, darin die `article.ec-event`. */
export const TAGES_SELECTOR = '.ec-day'
export const ZEILEN_SELECTOR = 'article.ec-event'
/** Kennung einer Zeile — setzt `eventDidMount` im Bauteil (die Bibliothek
 *  selbst führt ihre Kennung nur intern und schreibt sie nicht ans Element). */
export const ZEILEN_KENNUNG_ATTRIBUT = 'data-event-id'

/**
 * Kennung einer Zeile: `data-event-id` setzt der Einbau des Bauteils
 * (`eventDidMount`), BEVOR der Abgleich läuft. Fehlt sie, bleibt die Zeile
 * unzugeordnet (dann gibt es für sie keinen Knopf).
 */
export function zeilenKennung(zeile) {
  if (!zeile) return ''
  return zeile.getAttribute?.(ZEILEN_KENNUNG_ATTRIBUT) || ''
}

/** Die Zeilen eines Tages — direkte Kinder zuerst, sonst irgendwo darin. */
export function zeilenImTag(tag) {
  if (!tag) return []
  const direkt = Array.from(tag.children || []).filter((k) => k.matches?.(ZEILEN_SELECTOR))
  if (direkt.length) return direkt
  return Array.from(tag.querySelectorAll?.(ZEILEN_SELECTOR) || [])
}

/** Ist der Knopf dort, wo er hingehört?
 *   - steht er direkt hinter SEINER Zeile (nächstes Element-Geschwister)?
 *   - sitzt er im selben Tages-Container wie diese Zeile?
 *   - hat er genau die Breite des Termins (die Zeilen sind Geschwister, ohne
 *     gemeinsame Hülle — die Breite muss also ausdrücklich gesetzt sein)?
 * Ohne Layout (jsdom) sind die Breiten 0; dann zählt allein die Lage im DOM.
 */
export function passt(knopf, zeile) {
  if (!knopf || !zeile) return false
  if (knopf.previousElementSibling !== zeile) return false
  if (!knopf.parentElement || knopf.parentElement !== zeile.parentElement) return false
  const zeilenBreite = zeile.getBoundingClientRect?.().width || 0
  const knopfBreite = knopf.getBoundingClientRect?.().width || 0
  if (zeilenBreite > 0 && Math.abs(zeilenBreite - knopfBreite) > 1) return false
  return true
}

/** Alle Halter unterhalb eines Knotens (der Wurzel-Knoten zählt mit). */
export function knoepfeUnter(wurzel) {
  if (!wurzel) return []
  const gefunden = Array.from(wurzel.querySelectorAll?.(`.${HALTER_KLASSE}`) || [])
  if (wurzel.classList?.contains(HALTER_KLASSE)) gefunden.unshift(wurzel)
  return gefunden
}

/** Halter zu einer Kennung im gesamten Kalender (für den Einbau: vorhandenen weiterverwenden). */
export function knopfZuKennung(wurzel, kennung) {
  if (!wurzel || !kennung) return null
  return wurzel.querySelector(`.${HALTER_KLASSE}[${KENNUNG_ATTRIBUT}="${kennung}"]`)
}

/**
 * Idempotenter Abgleich des Kalenders:
 *   1. Halter OHNE lebende Zeile (Termin gelöscht/aus dem Zeitraum gefallen)
 *      entfernen.
 *   2. Je Zeile: DEN Halter mit ihrer Kennung nehmen; fehlt er, den ersten
 *      freien einer gleichnamigen Zeile (die Bibliothek kann eine Zeile beim
 *      Neubau durch ein neues Element ersetzen) oder einen neuen erzeugen.
 *      Dann direkt hinter die Zeile setzen (`passt` ungleich falsch) und die
 *      Kennung am Halter fortschreiben.
 *   3. Übrige Halter (doppelt, ohne Kennung) entfernen — es bleibt höchstens
 *      EIN Halter je Termin.
 *
 * `neuerKnopf(zeile, kennung)` liefert einen frisch gebauten Halter (ohne
 * Elternknoten); er darf `null` liefern (dann bleibt die Zeile ohne Knopf).
 * `entfernenErlaubt(halter)` entscheidet, ob ein Halter aus dem DOM genommen
 * werden darf (das Bauteil baut nur seine eigene Ware ab). Wird ER nicht
 * gefragt, ruft der Abgleich `abgebaut(halter)` — so erfährt der Aufrufer
 * von jedem Halter, den er nicht behält (sein Vue-Rahmen muss weg, sonst
 * bleibt er samt Menü im Speicher).
 *
 * Rückgabe: die Halter in der Reihenfolge der Zeilen (für Belege/Tests).
 */
export function zuordnen(wurzel, neuerKnopf, entfernenErlaubt = null, abgebaut = null) {
  if (!wurzel) return []
  const melde = (halter) => {
    if (typeof entfernenErlaubt !== 'function' || entfernenErlaubt(halter)) {
      if (typeof abgebaut === 'function') abgebaut(halter)
    }
  }
  // Zeilen des Kalenders — die Halter sind deren GESCHWISTER, gesucht wird
  // deshalb dort, wo die Zeilen stehen (nicht im ganzen Dokument: ein zweiter
  // Kalender auf derselben Seite bleibt unberührt).
  const zeilen = Array.from(wurzel.querySelectorAll?.(ZEILEN_SELECTOR) || [])
  const tag = zeilen[0]?.parentElement || wurzel
  const knopfListe = knoepfeUnter(tag)
  const vergeben = new Set()
  const reihenfolge = []

  // Die Zeilen, die JETZT in der Liste stehen — eine Zeile, die die
  // Bibliothek beim Neubau fortgeworfen hat, ist keine Zuordnung mehr wert.
  const lebendeZeilen = new Set(zeilen)

  // 1. Waisen zuerst: kein lebendiger Termin mehr hinter dem Knopf.
  for (const knopf of knopfListe) {
    if (lebendeZeilen.has(knopf.previousElementSibling)) continue
    vergeben.add(knopf)
    melde(knopf)
    knopf.remove?.()
  }

  for (const zeile of zeilen) {
    const kennung = zeilenKennung(zeile)
    let knopf = null
    // Genau der Halter DIESER Kennung, der noch niemandem zugeteilt ist.
    for (const kandidat of knopfListe) {
      if (vergeben.has(kandidat)) continue
      if ((kandidat.getAttribute?.(KENNUNG_ATTRIBUT) || '') !== kennung) continue
      knopf = kandidat
      break
    }
    if (!knopf) {
      // Gleichnamige Zeile ohne Halter (Neubau eines Elements): ihren nehmen.
      for (const kandidat of knopfListe) {
        if (vergeben.has(kandidat)) continue
        const vorbesitzer = kandidat.previousElementSibling
        if (vorbesitzer?.matches?.(ZEILEN_SELECTOR) && zeilenKennung(vorbesitzer) === kennung) {
          knopf = kandidat
          break
        }
      }
    }
    if (!knopf && typeof neuerKnopf === 'function' && kennung) {
      knopf = neuerKnopf(zeile, kennung) || null
      if (knopf) knopfListe.push(knopf)
    }
    if (!knopf) continue
    vergeben.add(knopf)
    knopf.setAttribute?.(KENNUNG_ATTRIBUT, kennung)
    if (!passt(knopf, zeile) && zeile.parentElement) {
      zeile.parentElement.insertBefore(knopf, zeile.nextSibling)
    }
    reihenfolge.push(knopf)
  }

  // 3. Rest (doppelt, ohne Kennung): weg — nur eigene Ware.
  for (const knopf of knoepfeUnter(tag)) {
    if (vergeben.has(knopf)) continue
    vergeben.add(knopf)
    melde(knopf)
    knopf.remove?.()
  }
  return reihenfolge
}

/** Alle Halter im Kalender (Beleg für „0 Knöpfe übrig"). */
export function anzahlKnoepfe(wurzel) {
  return knoepfeUnter(wurzel).length
}

export default { HALTER_KLASSE, KENNUNG_ATTRIBUT, zuordnen, passt, zeilenKennung, anzahlKnoepfe }
