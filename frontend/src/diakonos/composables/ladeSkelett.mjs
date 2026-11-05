/**
 * UX2d2 — Ladezustand ohne Flackern.
 *
 * BEFUND (UX2d-Abnahme): Das Lade-Skelett erschien sofort und verschwand bei
 * schnellen Antworten nach wenigen Millisekunden wieder. Der Bildschirm
 * „blitzte": ein grauer Balken, weg, Inhalt. Ruhiger ist, den Platzhalter erst
 * zu zeigen, wenn das Laden MERKLICH dauert — unter 300 ms soll niemand etwas
 * sehen, weil die Antwort praktisch sofort da ist.
 *
 * REGEL: `sichtbar` folgt `laedt`, aber erst nach `VERZOEGERUNG_MS`. Endet das
 * Laden vorher, wird der Platzhalter nie gezeigt.
 *
 * Die Vorlesehilfe (`aria-label`) am Skelett bleibt davon unberührt — sie
 * gehört ins Skelett selbst, nicht in diese Funktion.
 *
 * Keine Importe: eigenständig nutzbar und im Node-Test ohne Browser prüfbar.
 */

/** So lange bleibt der Bildschirm ruhig, bevor ein Platzhalter erscheint. */
export const VERZOEGERUNG_MS = 300

/**
 * @param {boolean} laedt     laufender Ladezustand (Wert, keine Ref)
 * @param {(sichtbar: boolean) => void} melden  Rückruf mit dem neuen Stand
 * @param {{verzoegerung?: number, timer?: {set: Function, clear: Function}}} [optionen]
 *   `verzoegerung` überschreibt die 300 ms; `timer` erlaubt dem Test, die Zeit
 *   zu ersetzen.
 * @returns {{pruefe: (laedt: boolean) => void, sofort: () => boolean, beenden: () => void}}
 */
export function ladeSkelett(laedt, melden, optionen = {}) {
  const verzoegerung = Number.isFinite(optionen.verzoegerung) ? optionen.verzoegerung : VERZOEGERUNG_MS
  const timer = optionen.timer || {
    set: (fn, ms) => setTimeout(fn, ms),
    clear: (kennung) => clearTimeout(kennung),
  }
  let laeuft = null
  let steht = false

  function aufraeumen() {
    if (laeuft !== null) {
      timer.clear(laeuft)
      laeuft = null
    }
  }

  function setze(wert) {
    if (steht === wert) return
    steht = wert
    melden(wert)
  }

  /** Bei jeder Änderung des Ladezustands aufrufen. */
  function pruefe(an) {
    aufraeumen()
    if (!an) {
      setze(false)
      return
    }
    laeuft = timer.set(() => {
      laeuft = null
      // Endet das Laden vorher, hat `pruefe(false)` den Timer schon abgeräumt —
      // läuft er ab, wird also noch geladen. (`laedt` ist nur der Startwert;
      // wer mit `false` startete, sah sonst nie einen Platzhalter.)
      setze(true)
    }, verzoegerung)
  }

  /** Steht der Platzhalter gerade? */
  function sofort() {
    return steht
  }

  /** Beim Verlassen der Seite: nichts mehr nachmelden. */
  function beenden() {
    aufraeumen()
    steht = false
  }

  return { pruefe, sofort, beenden }
}
