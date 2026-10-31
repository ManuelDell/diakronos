/**
 * Zwischenablage/Bereitstellung des letzten CSRF-Heilungsfehlers (WEB-8c R4).
 *
 * WARUM eine eigene Datei: `useApi.js` und andere Aufrufer müssen ein
 * Sitzungsende im Hauptbereich als DIALOG zeigen, brauchen dafür aber
 * `useSitzungsablauf.js` — und das importiert `usePlanrahmenCache.js` sowie
 * `basis.js`. Zieht `useApi.js` diesen Weg direkt, entsteht ein Ring
 * (`usePlanrahmenCache` → `usePlanrahmen` → `useApi` → …), der im Bundle als
 * `Cannot access 'X' before initialization` endet (im Wegwerf-Stack WEB-8c
 * aufgefallen: jeder Weg über `apiCall` brach ab).
 *
 * Diese Datei hat deshalb KEINE Importe außer `shallowRef` (reiner
 * Vue-Baustein, kein Projektcode): Aufrufer legen den Fehler ab
 * (`mitSitzungsdialog`), die Statusanzeige beobachtet den Stand mit `watch`
 * und liest ihn beim Anzeigen (`SitzungsHinweis.vue` →
 * `useSitzungsablauf.js`). Eine Wahrheit, kein Ring.
 *
 * WEB-8d (M2): Der Stand war ein einfaches Objekt, und `SitzungsHinweis.vue`
 * fragte ihn 4x je Sekunde ab (`setInterval(…, 250)`). Jetzt ist er ein
 * `shallowRef` — die Anzeige wird bei einer Änderung SOFORT benachrichtigt
 * (`sitzungsFehlerBeobachten`) und es gibt keinen Takt mehr. `shallowRef`
 * (nicht `ref`) ist Absicht: der Fehler ist ein `Error`-Objekt mit Zusatzfeldern;
 * eine tiefe Umwandlung würde seine Methoden/Prototypen anfassen.
 */
import { shallowRef, watch } from 'vue'

/** Der zuletzt aufgedeckte Sitzungsfehler im Hauptbereich (`null` = keiner). */
export const sitzungsFehlerStand = shallowRef(null)

/** Fehler ablegen, damit die Statusanzeige den festen Hinweis zeigen kann. */
export function sitzungsFehlerMerken(fehler) {
    sitzungsFehlerStand.value = fehler || null
    return fehler
}

/** Abgelegten Fehler lesen und dabei NICHT löschen (mehrere Leser erlaubt). */
export function sitzungsFehlerLesen() {
    return sitzungsFehlerStand.value
}

/** Nach dem Anzeigen/Schliessen zurücksetzen. */
export function sitzungsFehlerVergessen() {
    sitzungsFehlerStand.value = null
}

/**
 * WEB-8d (M2): Auf Änderungen des Standes hören — das ersetzt die
 * Dauerabfrage in `SitzungsHinweis.vue`.
 *
 * @param {(fehler: Error|null) => void} rueckmeldung
 * @param {{sofort?: boolean}} [optionen] `sofort: true` meldet zusätzlich den
 *   aktuellen Stand (für die Anzeige beim Aufbau, Muster `watch(..., {immediate:true})`).
 * @returns {() => void} Abmeldefunktion (in `onUnmounted` aufrufen).
 */
export function sitzungsFehlerBeobachten(rueckmeldung, { sofort = false } = {}) {
    if (sofort) rueckmeldung(sitzungsFehlerStand.value || null)
    return watch(
        () => sitzungsFehlerStand.value,
        (fehler) => { rueckmeldung(fehler || null) },
    )
}
