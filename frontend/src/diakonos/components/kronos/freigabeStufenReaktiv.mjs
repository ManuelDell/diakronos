/**
 * UI-R4 — reaktive Ablage der Stufen-Titel für Bauteile.
 *
 * `freigabeStufen.mjs` bleibt bewusst OHNE Vue (reine Regeln, auch von
 * `pruefZeile.mjs` benutzt). Wer die Titel im Template/computed BRAUCHT,
 * nimmt diese Datei: der Stand liegt in einem `shallowRef`, damit Warteline
 * und „Stufe: …“ neu zeichnen, sobald die Antwort eintrifft (vorher blieb
 * „wartet auf: —“ stehen — im Wegwerf-Stack gemessen).
 *
 * Einmal im Modul gehalten: alle Karten derselben Seite teilen den Stand.
 *
 * UI-R4b (Punkt 7b): `get_rollen_erklaerung` ist statisch — es wird EINMAL je
 * Seite geladen, nicht einmal je Karte. Vorher rief jede Karte (und jedes
 * andere Bauteil der Prüfliste) den Endpunkt selbst auf: eine Seite mit 20
 * Karten schickte 20 gleiche Abfragen. `stufenTitelEinmalLaden` merkt sich den
 * laufenden/erledigten Aufruf; ein Fehler wird NICHT gemerkt, damit ein
 * späterer Aufruf es erneut versuchen darf.
 */
import { shallowRef } from 'vue'
import {
  aktuelleStufenTitel,
  ladeStufenTitel,
  stufenName,
} from './freigabeStufen.mjs'

/** Aktueller Stand der Server-Titel (reaktiv). */
export const titelStand = shallowRef(aktuelleStufenTitel())

/** Der eine laufende/erledigte Ladevorgang je Seite (Modul-Lebensdauer). */
let _einmal = null

/**
 * Titel laden und den reaktiven Stand setzen. Fehler bleiben folgenlos —
 * dann steht weiterhin `STUFE_UNBEKANNT`, nie ein erfundenes Wort.
 *
 * @param {(pfad: string, args?: object) => Promise<any>} apiCall
 * @returns {Promise<Record<string, string>>}
 */
export async function stufenTitelLaden(apiCall) {
  const neue = await ladeStufenTitel(apiCall)
  titelStand.value = { ...neue }
  return titelStand.value
}

/**
 * Titel EINMAL je Seite laden — gemeinsamer Lader aller Bauteile.
 *
 * Mehrfachaufrufe (eine Karte je Vorschlag) hängen sich an denselben
 * Ladevorgang; es geht genau eine Abfrage hinaus. Scheitert sie, wird der
 * gemerkte Vorgang verworfen, damit ein späterer Aufruf es erneut versucht.
 *
 * @param {(pfad: string, args?: object) => Promise<any>} apiCall
 * @returns {Promise<Record<string, string>>}
 */
export function stufenTitelEinmalLaden(apiCall) {
  if (_einmal) return _einmal
  const lauf = stufenTitelLaden(apiCall)
    .then((stand) => {
      // Leerer Stand = kalte Antwort: nicht merken, sonst bliebe die Seite
      // für immer ohne Namen.
      if (!stand || !Object.keys(stand).length) _einmal = null
      return stand
    })
    .catch(() => {
      _einmal = null
      return titelStand.value
    })
  _einmal = lauf
  return lauf
}

/**
 * Nur für Tests: den gemerkten Ladevorgang vergessen.
 */
export function stufenTitelMerkerLeeren() {
  _einmal = null
}

/**
 * Nur für Tests: den Titelstand dieser Seite auf „noch nichts geladen“
 * zurücksetzen — inklusive des gemerkten Ladevorgangs.
 *
 * Warum das nötig ist: `titelStand` ist ein Modul-Singleton („je Seite EINE
 * Ablage“). Ein Test, der die Reihenfolge „Anträge VOR Titeln“ prüfen will,
 * muss die Seite frisch öffnen — sonst stehen die Titel des vorigen Tests
 * schon da und der Fall tritt nie ein.
 */
export function stufenTitelZuruecksetzen() {
  _einmal = null
  titelStand.value = {}
}

/**
 * Stufenname für Fließtext — reaktiv (liest `titelStand`).
 *
 * @param {string|null|undefined} stufe
 * @returns {string}
 */
export function stufenNameReaktiv(stufe) {
  // Der Stand wird gelesen, damit das aufrufende computed neu zeichnet.
  void titelStand.value
  return stufenName(stufe)
}
