/**
 * BF1-L: Abmelden — EIN Weg fuer alle Stellen (Profil, Sidebar, mobil).
 *
 * Seit PT1 ist der Logout NUR per POST mit `X-Frappe-CSRF-Token` erlaubt
 * (`/api/method/logout`; GET -> 405). Der Nutzer fand bisher KEINEN
 * Abmelden-Knopf — diese Datei bringt ihn an jede noetige Stelle.
 *
 * Zwei serverseitige Wege, beide POST + CSRF:
 *  - `POST /logout` (SEC1-Route): beendet die lokale Sitzung. MT-8: es geht
 *    danach NIE zum Anbieter (kein RP-Logout, keine Authentik-Seite), sondern
 *    auf die ausdruecklich konfigurierte oeffentliche Website — sonst auf den
 *    Login-Bildschirm ohne automatische SSO-Weiterleitung (`/login?sso=0`).
 *    W3: fuer JSON-Aufrufer liefert
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
import { verlaufFuerNutzerAufraeumen } from './befehlspalette.mjs'
// A10 (Review 09.11., Punkt 2): die persönliche Standard-Ansicht des Handy-
// Kalenders ist nutzerbezogen und wird beim Abmelden entfernt. Die Regel
// steht in `components/kronos/mobilAnsicht.mjs` (dort geprüft).
import { abmeldenAufraeumen } from '../components/kronos/mobilAnsicht.mjs'
// WEB-5b: Abmelde- und Anmeldeadressen unter dem Betriebs-Praefix.
import { anmeldeUrl, apiUrl, basisPfad, mitBasis } from '../../shared/basis.js'

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
    // UX3f (Review, DSGVO): der Verlauf „Zuletzt verwendet“ der Befehlspalette
    // gehoert dazu — er verraet, wonach dieser Nutzer gesucht hat. Ohne
    // Nutzerkennung (hier: wir melden gerade ab) raeumt die Funktion ALLE
    // Verlaufs-Schluessel weg.
    try {
        verlaufFuerNutzerAufraeumen(window.localStorage, '')
    } catch { /* Speicher nicht verfuegbar -> egal */ }
    // A10 (Review 09.11., Punkt 2): die persönliche Standard-Ansicht des
    // Handy-Kalenders (`dk-kalender-standard-ansicht:<hash>`) hängt am
    // Benutzer und wird hier ebenfalls entfernt — sonst sähe der nächste
    // Nutzer desselben Geräts die Wahl des Vorgängers.
    try {
        abmeldenAufraeumen(window.localStorage)
    } catch { /* Speicher nicht verfuegbar -> egal */ }
    // PLAN-W1: Die Einklapp-Wahl des Warnblocks (`pr-warnblock:<benutzer>`)
    // bleibt BEWUSST stehen — sie haengt am Benutzer und soll beim naechsten
    // Anmelden wieder gelten.
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

/**
 * Ziel nach dem Abmelden aus dem Server-Zielpfad bestimmen (MT-8).
 *
 * SOLL (Manuel 11.11.): Nach dem Abmelden erscheint NIE eine Seite des
 * Anbieters. Der Server nennt entweder die ausdruecklich konfigurierte
 * oeffentliche Website (absolute http/https-Adresse) oder den Login-Bildschirm
 * (`/login?sso=0` — ohne automatische SSO-Weiterleitung).
 *
 * POSITIVLISTE (MT-8b): uebernommen wird NUR, was ausdruecklich erlaubt ist —
 *  - der Login-Bildschirm (`/login`, auch mit Abfrage) IMMER als `sso=0`: der
 *    Server setzt es schon so; ein Rest ohne `sso=0` (aeltere Antwort,
 *    Fallback-Route) bekommt es hier, sonst waere das Abmelden bei
 *    `nur-admin`/`aus` sofort wieder eine Anbieter-Weiterleitung,
 *  - absolute http/https-Adressen (die oeffentliche Website) — sie kommen AUS
 *    DER SERVER-ANTWORT,
 *  - relative Ziele nur, wenn sie mit genau einem `/` beginnen
 *    (`^/(?![/\\])`) und KEINE Steuerzeichen (Tab/CR/LF/NUL) enthalten.
 * Alles andere — leeres Ziel, `/`, SPA-Wurzel, `//host`, `/\host`, jedes
 * fremde Schema (`javascript:`, `data:`) — faellt auf den Login zurueck.
 * Damit kann ein manipuliertes Ziel nie auf eine fremde Herkunft fuehren,
 * die der Server nicht selbst genannt hat.
 */
function zielOderLogin(pfad) {
    // Der Login-Rueckfall traegt IMMER `sso=0`: nach dem Abmelden darf keine
    // automatische SSO-Weiterleitung folgen (sonst waere sie wirkungslos).
    const login = `${anmeldeUrl()}?sso=0`
    const ziel = String(pfad || '').trim()
    // Leeres Ziel oder SPA-Wurzel ist kein Abmeldeziel: dann lokal auf /login.
    // `/` ebenso wenig: Review-Befund 1 — das ist ohne Praefix die App-Wurzel
    // (und mit Praefix 404), NICHT die Website. Die echte Website-Adresse ist
    // absolut (http/https) und wird unten uebernommen.
    if (!ziel || ziel === '/' || ziel === mitBasis('/diakonos') || ziel === '#/') return login
    // Nur echte http/https-Adressen sind "absolute Ziele" — und die duerfen
    // hier stehen, weil der Server sie aus seiner Konfiguration liefert.
    if (/^https?:\/\//i.test(ziel)) return ziel
    // Login-Ziel des Servers: `sso=0` beibehalten bzw. ergaenzen.
    const anmeldePfad = anmeldeUrl()
    if (ziel === anmeldePfad || ziel.startsWith(anmeldePfad + '?')) {
        return /[?&]sso=0(&|$)/.test(ziel) ? ziel : login
    }
    // Positivliste fuer RELATIVE Ziele: genau ein fuehrender Slash (kein
    // `//host`, kein `/\host` — Backslash zaehlt im Browser als Slash) und
    // keine Steuerzeichen (Tab/CR/LF wuerden in Adressleisten zerlegt).
    // eslint-disable-next-line no-control-regex
    if (/^\/(?![/\\])/.test(ziel) && !/[\u0000-\u001f\u007f]/.test(ziel)) {
        return ziel
    }
    return login
}

/**
 * Abmelden: lokale Sitzung beenden (KEIN OIDC-RP-Logout, die Sitzung beim
 * Anbieter bleibt), Cache leeren und weiterleiten.
 * Kehrt normalerweise nicht zurueck — die Seite wird verlassen.
 * Liefert `{ok:false, fehler}` zurueck, wenn KEINE Route den Logout bestaetigt
 * hat — der Aufrufer zeigt dann eine Meldung, statt still zu wechseln.
 */
export async function abmelden() {
    // Bevorzugt die SEC1-Route: sie kennt die Zielregel (oeffentliche Website
    // oder `/login?sso=0`). Sie meldet lokal ab; zum Anbieter geht es nie.
    let res = await post(mitBasis('/logout'))
    if (!res.ok && (res.status === 404 || res.status === 405 || res.status === 0)) {
        // Fallback: nur der Frappe-kompatible Pfad ist vorhanden.
        res = await post(apiUrl('logout'))
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
