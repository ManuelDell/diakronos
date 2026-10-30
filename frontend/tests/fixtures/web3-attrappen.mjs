/**
 * WEB-3 — Test-Hilfe: `composables/useWebsite.js` ausführbar machen, ohne
 * `node_modules`.
 *
 * Das Komposit importiert `vue` (ref) und die API-Schicht (`./useApi.js`).
 * Beide werden hier durch Attrappen ersetzt — aber nur die IMPORTE, nicht der
 * Code: der Test führt den echten Aufrufpfad aus (Pfadname, Methode,
 * window.open). Ein Nachbau der Logik im Test wäre wertlos.
 *
 * Weg: ein Loader-Hook (`--import`-frei, direkt über `module.register`), der
 * für `vue` und `./useApi.js` kleine ES-Module aus `data:`-URLs liefert. Die
 * Attrappen lesen ihre Antworten aus `globalThis.__WEB3_API`.
 */

import { register } from 'node:module'

/** Attrappen-Quellen; werden vom Hook als ES-Modul ausgeliefert. */
export const VUE_STUB = `
    export function ref(wert) { return { value: wert } }
    export function computed(fn) { return { get value() { return fn() } } }
    export function watch() {}
    export function onMounted() {}
    export function onUnmounted() {}
`

export const API_STUB = `
    export async function apiGet(pfad) {
        const lage = globalThis.__WEB3_API || {}
        ;(globalThis.__WEB3_AUFRUFE ||= []).push({ art: 'GET', pfad })
        if (lage.getFehler) throw Object.assign(new Error('get'), lage.getFehler)
        return lage.getAntwort ?? null
    }
    export async function apiCall(pfad, args) {
        const lage = globalThis.__WEB3_API || {}
        ;(globalThis.__WEB3_AUFRUFE ||= []).push({ art: 'POST', pfad, args })
        if (lage.postFehler) throw Object.assign(new Error('post'), lage.postFehler)
        return lage.postAntwort ?? null
    }
    export class AuditConfirmationRequired extends Error {}
`

let registriert = false

/**
 * Registriert den Hook EINMAL pro Prozess. Node liefert Module aus `data:`-
 * URLs unverändert an den Aufrufer — damit lässt sich `vue`/`useApi` ersetzen,
 * ohne Dateien anzufassen.
 */
export function registriereAttrappen() {
    if (registriert) return
    registriert = true
    const quelle = `
        const VUE = ${JSON.stringify(VUE_STUB)}
        const API = ${JSON.stringify(API_STUB)}
        export async function resolve(specifier, context, next) {
            if (specifier === 'vue') {
                return { url: 'data:text/javascript,' + encodeURIComponent(VUE), shortCircuit: true }
            }
            if (specifier.endsWith('/useApi.js')) {
                return { url: 'data:text/javascript,' + encodeURIComponent(API), shortCircuit: true }
            }
            return next(specifier, context)
        }
    `
    register('data:text/javascript,' + encodeURIComponent(quelle), import.meta.url)
}

/**
 * Setzt die Attrappen-Antworten und leert den Aufrufzähler.
 * @param {{getAntwort?: any, getFehler?: any, postAntwort?: any, postFehler?: any}} lage
 */
export function setzeApi(lage) {
    globalThis.__WEB3_API = lage || {}
    globalThis.__WEB3_AUFRUFE = []
}

/** Die bisherigen Aufrufe (`{art, pfad, args}`). */
export function aufrufe() {
    return globalThis.__WEB3_AUFRUFE || []
}
