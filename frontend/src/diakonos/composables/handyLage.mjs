/**
 * DEV-B6 — EINE Quelle für die Handy-Lage der App (Review-Nacharbeit 10.11.).
 *
 * ENTSCHEIDUNG MANUEL (09.11.): „Auf einem Laptop darf nie die Handyleiste
 * kommen.“ Damit ist die Layout-Hälfte der FIX-6-Regel („der Zeiger ist nie
 * Layout-Kriterium“) bewusst GEÄNDERT — Layout hängt jetzt an Breite UND
 * primärem Zeiger:
 *
 *   layout == mobil  ⇔  (pointer: coarse) and (max-width: 720px)
 *                    ∨  (pointer: coarse) and (max-height: 480px)
 *                                             and (orientation: landscape)
 *
 * Die zweite Alternative prüft den Zeiger AUSDRÜCKLICH mit: ein flaches
 * Fenster mit MAUS (Laptop, halber Bildschirm 1280×450 — Review-Punkt 2)
 * bekommt keine Handy-Leiste.
 *
 * Leser dieser Datei (EINE Quelle, keine Kopien der Zeichenkette):
 *
 *   * `App.vue` — setzt die Klasse `.dk-app--handy` an die App-Hülle und
 *     blendet die Menü-Schublade dort ein; das CSS-Gerüst (untere Leiste,
 *     Seitenleiste, Fußabstand, Kopfzeile, Kalender-Mobil-Bau, Overlay-Listen)
 *     hängt an dieser Klasse. Ein `@media`-String fürs Gerüst gibt es NICHT
 *     mehr — vorher entschieden ein Dutzend Kopien und das Skript getrennt.
 *   * `pages/Kalender.vue` — A10-Mobil-Bau (`istSchmal`).
 *   * `components/kronos/KronosCalendar.vue` — Klickziel (Tagesliste/Blatt).
 *   * `composables/handyHinweis.mjs` / Plan-Seiten — PLAN-M1-Hinweis.
 *
 * Maschinenlesbare Form: Token `--layout-mobil` in `tokens.css` (identischer
 * Text). Der Node-Test `tests/dev-b6-*.test.mjs` vergleicht beide Wort für
 * Wort; `tests/fix6-zeigegeraet.test.mjs` prüft, dass keine Gerüst-Regel
 * mehr an einer nackten Breite hängt.
 *
 * Bewusst KEIN `@media (--layout-mobil)` im CSS: CSS-Variablen sind keine
 * Custom Media und werden in `@media` nicht aufgelöst (im Browser gemessen:
 * die Regeln blieben wirkungslos).
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { MOBIL_GRENZE_PX } from './eingabeart.mjs'
// Die Zeichenkette steht in `handyLageAbfrage.mjs` (ohne Vue) — damit auch
// Module ohne Oberfläche sie lesen können; hier nur weitergereicht.
import { FLACH_QUER_PX, HANDY_LAGE_ABFRAGE } from './handyLageAbfrage.mjs'

export { FLACH_QUER_PX, HANDY_LAGE_ABFRAGE }

/** Sehr schmal: darunter ist auch mit Maus kein Desktop-Gerüst darstellbar. */
export const SEHR_SCHMAL_PX = 430

/** Die EINE Gerüst-Klasse, die `App.vue` an `.dk-app` hängt. */
export const HANDY_KLASSE = 'dk-app--handy'

/**
 * Ist die Handy-Lage aktiv? Reine Rechnung, ohne Browser.
 *
 * @param {number} breite Fensterbreite in CSS-Pixeln
 * @param {{grob?: boolean, hoehe?: number, quer?: boolean}} [lage]
 *        `grob` = primärer Zeiger ist ein Finger, `hoehe` = Fensterhöhe,
 *        `quer` = Fenster ist breiter als hoch (orientation: landscape).
 *        Ohne `quer` gilt „flach und höher als breit“ NICHT als Querformat.
 * @returns {boolean}
 */
export function istHandyLage(breite, { grob = false, hoehe = 0, quer = null } = {}) {
    const b = Number(breite)
    const h = Number(hoehe)
    if (!Number.isFinite(b) || b <= 0) return false
    // Der grobe Zeiger ist in JEDER Alternative Bedingung (Review-Punkt 2).
    if (!grob) return false
    if (b <= MOBIL_GRENZE_PX) return true
    const istQuer = quer === null ? (Number.isFinite(h) && h > 0 && h < b) : quer === true
    return Number.isFinite(h) && h > 0 && h <= FLACH_QUER_PX && istQuer
}

/**
 * Reaktive Handy-Lage für Komponenten.
 *
 * Hört auf `matchMedia(HANDY_LAGE_ABFRAGE).change` UND auf `resize` — der
 * Zeigerwechsel (Maus angeschlossen/abgezogen) und das Fensterziehen lösen
 * unterschiedliche Ereignisse aus; in mehreren Seiten fehlte das `change`
 * (Befund der Nacharbeit: der PLAN-M1-Hinweis hing nur an `resize`).
 *
 * Ohne `window`/`matchMedia` (Node, jsdom-Attrappe fehlt) bleibt der Wert
 * `false`: Desktop-Gerüst, keine Leiste ohne Nachweis (fail safe).
 *
 * @param {{fenster?: object}} [umgebung] für Tests
 * @returns {{istHandyLage: import('vue').Ref<boolean>}}
 */
export function useHandyLage(umgebung = {}) {
    const fenster = umgebung.fenster || (typeof window !== 'undefined' ? window : null)
    const lesen = () => (fenster && typeof fenster.matchMedia === 'function'
        ? !!fenster.matchMedia(HANDY_LAGE_ABFRAGE).matches
        : false)
    const istHandyLage = ref(lesen())
    let abfrage = null
    const nachziehen = () => { istHandyLage.value = lesen() }
    onMounted(() => {
        if (!fenster) return
        if (typeof fenster.matchMedia === 'function') {
            abfrage = fenster.matchMedia(HANDY_LAGE_ABFRAGE)
            if (abfrage && typeof abfrage.addEventListener === 'function') {
                abfrage.addEventListener('change', nachziehen)
            } else if (abfrage && typeof abfrage.addListener === 'function') {
                // Safari < 14 kennt nur addListener.
                abfrage.addListener(nachziehen)
            }
        }
        fenster.addEventListener?.('resize', nachziehen)
        nachziehen()
    })
    onBeforeUnmount(() => {
        if (!fenster) return
        if (abfrage && typeof abfrage.removeEventListener === 'function') {
            abfrage.removeEventListener('change', nachziehen)
        } else if (abfrage && typeof abfrage.removeListener === 'function') {
            abfrage.removeListener(nachziehen)
        }
        fenster.removeEventListener?.('resize', nachziehen)
    })
    return { istHandyLage }
}

/**
 * Schmale Fenster: Seitenleiste einklappen. 256 px Seitenleiste in 702 px
 * Fenster ließen keine Inhaltsfläche (Befund DMB-3a7d335074cc).
 */
export const SEITENLEISTE_SCHMAL_ABFRAGE = '(max-width: 1100px)'

/**
 * Flaches Fenster: dort braucht die Kopfzeile den Menü-Knopf auch dann, wenn
 * keine Leisten-Lage herrscht (DEV-B6: ein flacher Maus-Laptop bekommt keine
 * Leiste, aber die Kopfzeile ist knapp). Zeiger-unabhängig.
 */
export const FLACH_ABFRAGE = `(max-height: ${FLACH_QUER_PX}px)`
