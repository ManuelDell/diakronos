/**
 * BF1-L: Abmelden — EIN Weg fuer alle Stellen (Profil, Sidebar, mobil).
 *
 * Seit PT1 ist der Logout NUR per POST mit `X-Frappe-CSRF-Token` erlaubt
 * (`/api/method/logout`; GET -> 405). Der Nutzer fand bisher KEINEN
 * Abmelden-Knopf — diese Datei bringt ihn an jede noetige Stelle.
 *
 * Zwei serverseitige Wege, beide POST + CSRF:
 *  - `POST /logout` (SEC1-Route): beendet die lokale Sitzung UND baut bei
 *    aktivem OIDC den RP-Logout beim Anbieter. W3: fuer JSON-Aufrufer liefert
 *    sie `{"redirect": <ziel>}` im Koerper (statt einer 303), weil der Browser
 *    einer Weiterleitung im `fetch` mit `redirect: 'manual'` NICHT folgen kann
 *    — er liefert eine undurchsichtige `opaqueredirect`-Antwort (`status 0`,
 *    keine lesbaren Header). Das Server-Ziel wird deshalb gelesen und selbst
 *    per `window.location` gesetzt.
 *  - `POST /api/method/logout`: reiner lokaler Logout (Fallback, falls die
 *    SEC1-Route in einer Installation fehlt).
 *
 * Fehler werden NICHT als Erfolg gewertet: gelingt keine der beiden Routen,
 * kehrt die Funktion mit `{ok:false}` zurueck — es wird nicht auf `/login`
 * gesprungen, waehrend die Serversitzung noch lebt.
 *
 * Vor dem Verlassen wird der PF1-Browser-Cache des Plan-Rahmens geleert
 * (nutzerbezogene Staende duerfen nicht beim naechsten Nutzer auftauchen).
 */
import { cacheLeeren } from './usePlanrahmenCache.js'

function csrfToken() {
    return window.__DIakonosBOOT?.csrf_token || ''
}

/**
 * POST auf eine Abmelde-Route. Liefert `{status, redirect, ok}`:
 *  - `status`  HTTP-Status (0 bei Netzfehler)
 *  - `redirect` vom Server genannter Zielpfad (aus dem JSON-Koerper)
 *  - `ok`      true nur bei 2xx/3xx-Antwort mit bestaetigtem Ziel
 *
 * Bewusst KEIN `redirect: 'manual'`: der Server antwortet JSON-Aufrufern mit
 * 200 + `redirect`-Feld, es gibt also nichts zu folgen. Antwortet eine
 * Installation doch mit 3xx und ist der Header lesbar, wird er genommen.
 */
async function post(pfad) {
    try {
        const res = await fetch(pfad, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': csrfToken(),
            },
            body: JSON.stringify({}),
        })
        let redirect = ''
        if (res.status >= 200 && res.status < 300) {
            try {
                const koerper = await res.clone().json()
                redirect = koerper?.message?.redirect || koerper?.redirect || ''
            } catch { /* kein JSON-Koerper -> lokaler Fallback unten */ }
        } else if (res.status >= 300 && res.status < 400) {
            redirect = res.headers.get('location') || ''
        }
        return { status: res.status, redirect, ok: res.status >= 200 && res.status < 400 }
    } catch {
        return { status: 0, redirect: '', ok: false }
    }
}

/** Leert alle nutzerbezogenen Browser-Staende (W4). */
export function alleBrowserStaendeLeeren() {
    try {
        // Direkt aufrufen statt `cacheNutzerSetzen('')`: Letzteres leert nur,
        // wenn die Nutzerkennung im Modul schon belegt war — beim Abmelden
        // ohne vorherigen Plan-Seitenaufruf blieb der Cache sonst stehen.
        cacheLeeren()
    } catch { /* Cache darf das Abmelden nie verhindern */ }
    try {
        sessionStorage.clear()
    } catch { /* egal */ }
    // W4: auch die uebrigen nutzerbezogenen Staende im localStorage entfernen
    // (Entwuerfe und Impersonationszustand), damit nach dem Abmelden kein
    // naechster Nutzer Reste sieht.
    const PRAEFIXE = ['pr-entwurf:', 'dk-entwurf', 'dk-impersonation', 'dk-imp']
    try {
        const s = window.localStorage
        if (s) {
            const zuLoeschen = []
            for (let i = 0; i < s.length; i += 1) {
                const k = s.key(i)
                if (k && PRAEFIXE.some((p) => k === p || k.startsWith(p))) zuLoeschen.push(k)
            }
            zuLoeschen.forEach((k) => s.removeItem(k))
        }
    } catch { /* Speicher nicht verfuegbar -> egal */ }
}

/** Ziel nach dem Abmelden aus dem Server-Zielpfad bestimmen. */
function zielOderLogin(pfad) {
    const ziel = String(pfad || '').trim()
    // Ein SPA-Ziel ist kein Abmeldeziel: dann lokal auf /login.
    if (!ziel || ziel === '/diakonos' || ziel === '/' || ziel === '#/') return '/login'
    return ziel
}

/**
 * Abmelden inkl. OIDC-RP-Logout, Cache-Leerung und Weiterleitung.
 * Kehrt normalerweise nicht zurueck — die Seite wird verlassen.
 * Liefert `{ok:false, fehler}` zurueck, wenn KEINE Route den Logout bestaetigt
 * hat — der Aufrufer zeigt dann eine Meldung, statt still zu wechseln.
 */
export async function abmelden() {
    // Bevorzugt die SEC1-Route: sie deckt lokalen UND OIDC-Logout ab.
    let res = await post('/logout')
    if (!res.ok && (res.status === 404 || res.status === 405 || res.status === 0)) {
        // Fallback: nur der Frappe-kompatible Pfad ist vorhanden.
        res = await post('/api/method/logout')
    }

    if (!res.ok) {
        // W3: Fehlerantwort (403 CSRF, 500) NICHT als Erfolg werten — die
        // Serversitzung lebt, ein Sprung auf /login waere eine Luege.
        return {
            ok: false,
            fehler: res.status
                ? `Abmelden fehlgeschlagen (HTTP ${res.status}). Bitte erneut versuchen.`
                : 'Abmelden fehlgeschlagen: keine Verbindung zum Server.',
        }
    }

    alleBrowserStaendeLeeren()
    window.location.href = zielOderLogin(res.redirect)
    return { ok: true }
}

export function useAbmelden() {
    return { abmelden }
}
