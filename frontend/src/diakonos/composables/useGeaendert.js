import { computed, ref, unref } from 'vue'
import { geaenderteFelder, hatSichGeaendert, standFuerVergleich } from './geaendert.mjs'

/**
 * UX3h3 — „Speichern nur, wenn geändert“.
 *
 * Das Vorbild steht in `useGestaltung` (`kannSpeichern`): dort hieß es schon
 * „es gibt eine Änderung, also darf gespeichert werden“. Diese Datei zieht das
 * Muster in EIN kleines Composable, damit es nicht je Seite abgeschrieben wird:
 *
 *   const stand = useGeaendertStand()
 *   stand.merken({ name: gemeindename.value, ort: ort.value })   // nach dem Laden
 *   const geaendert = stand.geaendert({ name: gemeindename.value, ort: ort.value })
 *   const kannSpeichern = computed(() => geaendert.value)
 *
 * Drei Zusagen, die die Karte verlangt:
 *   - Vor dem ersten `merken` gilt NICHTS als geändert (der Knopf bleibt
 *     gesperrt, solange kein Stand geladen ist — sonst böte die Seite ein
 *     Speichern an, das der Server mangels geladener Werte nicht ausführen darf).
 *   - `merken` nimmt den GESPEICHERTEN Stand auf, nicht den gerade getippten:
 *     nach erfolgreichem Speichern ist der Knopf wieder zu.
 *   - Ein Feld, das wieder auf den geladenen Wert zurückgeht, ist keine
 *     Änderung mehr (Vergleich, kein „einmal getippt“-Merker).
 *
 * Reaktivität: `aktuelle()` wird als Funktion übergeben und bei jeder
 * Auswertung frisch gelesen — deshalb funktionieren `ref`s, `reactive`-Objekte
 * und berechnete Werte gleichermaßen, ohne dass die Seite Aufrufe verteilen muss.
 */
export function useGeaendertStand() {
  /** Der geladene (gespeicherte) Stand, `null` solange nichts geladen ist. */
  const stand = ref(null)

  /** Den gespeicherten Stand aufnehmen (nach dem Laden UND nach dem Speichern). */
  function merken(werte) {
    const quelle = typeof werte === 'function' ? werte() : werte
    stand.value = standFuerVergleich(unref(quelle) || {})
  }

  /** Nach einem fehlgeschlagenen Laden wieder „nichts geladen“ melden. */
  function vergessen() {
    stand.value = null
  }

  /** Die Namen der Felder, die vom geladenen Stand abweichen. */
  function geaenderte(aktuelle) {
    if (!stand.value) return []
    const werte = typeof aktuelle === 'function' ? aktuelle() : aktuelle
    return geaenderteFelder(stand.value, unref(werte) || {})
  }

  /** Darf gespeichert werden? (`computed`, damit die Oberfläche mitzählt.) */
  function geaendert(aktuelle) {
    return computed(() => {
      if (!stand.value) return false
      const werte = typeof aktuelle === 'function' ? aktuelle() : aktuelle
      return hatSichGeaendert(stand.value, unref(werte) || {})
    })
  }

  return { stand, merken, vergessen, geaenderte, geaendert }
}

/**
 * Die Attribute eines „Speichern“-Knopfes bei „nur wenn geändert“.
 *
 * `aria-disabled` steht NEBEN `disabled`: ein ausgegrauter Knopf, den eine
 * Vorlesehilfe trotzdem als bedienbar ansagt, wäre eine falsche Auskunft.
 * `title` nennt den Grund — sonst wirkt der gesperrte Knopf wie ein Fehler.
 *
 * @param {boolean} gesperrt  true = nichts geändert, Knopf zu
 * @param {boolean} [laeuft]  true = gerade am Speichern
 * @returns {{disabled: boolean, 'aria-disabled': string|undefined, title: string}}
 */
export function speichernKnopf(gesperrt, laeuft = false) {
  const zu = Boolean(gesperrt) || Boolean(laeuft)
  return {
    disabled: zu,
    'aria-disabled': zu ? 'true' : undefined,
    title: laeuft ? 'Wird gespeichert …' : (zu ? 'Keine Änderung zum Speichern' : 'Speichern'),
  }
}
