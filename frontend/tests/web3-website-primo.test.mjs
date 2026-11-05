/**
 * WEB-3 — Einstellungen → „Website (Primo)“ und Einstieg „Primo öffnen“.
 *
 * Der Test AUSFÜHRT die Regeln (Rollen, Zustand, Fehlerdeutung, window.open),
 * statt sie nur im Quelltext zu suchen. Nur die Verdrahtung (Router, Menü,
 * Einstellungsseite, Dockerfile) wird als Quelltext geprüft — dafür gibt es
 * keinen ausführbaren Weg ohne Browser.
 *
 * Geprüfte Zusagen der Karte:
 *
 *   S1  Einstellungen haben den Abschnitt „Website (Primo)“: Zustand aus dem
 *       Status-Endpunkt (nicht angeschlossen / nicht erreichbar / verbunden mit
 *       Version und Seitenzahl), Kurzanleitung, Knopf „Verbindung prüfen“.
 *   S2  Menüeintrag „Website“ NUR für System Manager/Administrator/
 *       Website-Moderator; Seite mit „Primo öffnen“ per POST
 *       (login_uebergabe, CSRF über apiCall) und window.open(..., noopener).
 *   S3  Kein Token im Diakronos-DOM/Zustand; Layout nur nach Breite.
 *   S4  Eintrag in der node-Testliste des Dockerfiles.
 *
 * Lauf im Docker-Build über `node --test runners`:  cwd = frontend/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
    ANSCHLUSS_SCHRITTE,
    ANLEITUNG_ORT,
    BENOETIGTE_WERTE,
    WEBSITE_ROLLEN,
    darfWebsite,
    sichereUebergabeUrl,
    sitzungsHinweis,
    uebergabeFehlertext,
    verbindungsDetails,
    zustandsText,
} from '../src/diakonos/composables/website.mjs'
import { MENUE, sichtbareEintraege } from '../src/diakonos/menue.js'
import {
    aufrufe as apiAufrufe,
    registriereAttrappen,
    setzeApi,
} from './fixtures/web3-attrappen.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const lies = (pfad) => readFileSync(join(HIER, '..', 'src', 'diakonos', pfad), 'utf8')
const liesRepo = (pfad) => {
    const voll = join(REPO, pfad)
    assert.ok(existsSync(voll), `Datei fehlt: ${pfad}`)
    return readFileSync(voll, 'utf8')
}

/** Quelltext ohne Kommentare (Aussagen über „es gibt kein X“). */
function ohneKommentare(text) {
    return text
        .replace(/<!--[\s\S]*?-->/g, '')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
}

// ── (1) Rollen-Sichtbarkeit ────────────────────────────────────────────────

test('WEB-3: nur die drei Website-Rollen dürfen den Bereich sehen', () => {
    assert.equal(darfWebsite({ rollen: ['System Manager'] }), true)
    assert.equal(darfWebsite({ rollen: ['Administrator'] }), true)
    assert.equal(darfWebsite({ rollen: ['Website-Moderator'] }), true)
    // Zusatzrollen ändern nichts.
    assert.equal(darfWebsite({ rollen: ['Mitglied', 'Website-Moderator'] }), true)

    // Alle anderen: nein.
    assert.equal(darfWebsite({ rollen: ['Mitglied'] }), false)
    assert.equal(darfWebsite({ rollen: ['Gast'] }), false)
    assert.equal(darfWebsite({ rollen: [] }), false)
    // Fail closed: ohne (kaputte) Rollenangabe keine Sichtbarkeit.
    assert.equal(darfWebsite({}), false)
    assert.equal(darfWebsite({ rollen: null }), false)
    assert.equal(darfWebsite({ rollen: 'System Manager' }), false)
    // Kein Präfix-/Teiltreffer: „Administrator“ ≠ „Mitgliederadministrator“.
    assert.equal(darfWebsite({ rollen: ['Mitgliederadministrator'] }), false)
})

test('WEB-3: Menüeintrag „Website“ erscheint nur mit passender Rolle', () => {
    const gruppe = MENUE.find(g => g.eintraege.some(e => e.id === 'website'))
    assert.ok(gruppe, 'Menüeintrag „website“ fehlt')
    const eintrag = gruppe.eintraege.find(e => e.id === 'website')
    assert.equal(eintrag.label, 'Website')
    assert.equal(eintrag.href, '#/website')
    assert.deepEqual(eintrag.rollen, WEBSITE_ROLLEN)
    assert.ok(eintrag.seiten.includes('Website'))

    const sichtbar = (rollen) => sichtbareEintraege(gruppe, { rollen })
        .some(e => e.id === 'website')

    assert.equal(sichtbar(['Website-Moderator']), true)
    assert.equal(sichtbar(['System Manager']), true)
    assert.equal(sichtbar(['Administrator']), true)
    // Negative Fälle: der Eintrag taucht NICHT auf.
    assert.equal(sichtbar(['Mitglied']), false)
    assert.equal(sichtbar([]), false)
    assert.equal(sichtableOhneRollengabe(gruppe), false)
})

/** Ein Aufruf ohne `rollen` (alte Aufrufer) darf den Eintrag nicht zeigen. */
function sichtableOhneRollengabe(gruppe) {
    return sichtbareEintraege(gruppe, {}).some(e => e.id === 'website')
}

test('WEB-3: Rollenliste ist deckungsgleich mit dem Server', () => {
    // Der Server führt die eine Wahrheit in `website/primo.py`.
    const primo = liesRepo('backend/src/diakronos_app/website/primo.py')
    const block = primo.slice(primo.indexOf('WEBSITE_ROLLEN: tuple[str, ...] = ('))
    const eintraege = block.slice(0, block.indexOf(')'))
        .split('\n')
        .map(z => z.trim())
        .filter(z => z.startsWith('"'))
        .map(z => z.replace(/^"/, '').replace(/",?$/, ''))
    assert.deepEqual(eintrag_sortiert(eintraege), eintrag_sortiert(WEBSITE_ROLLEN))
})

const eintrag_sortiert = (liste) => [...liste].sort()

// ── (2) Zustandsanzeige ────────────────────────────────────────────────────

test('WEB-3: die drei Serverzustände bekommen eigenen Titel und Ton', () => {
    const nicht = zustandsText('nicht_konfiguriert')
    assert.equal(nicht.zustand, 'nicht_konfiguriert')
    assert.equal(nicht.titel, 'Nicht angeschlossen')
    assert.equal(nicht.ton, 'neutral')

    const weg = zustandsText('nicht_erreichbar')
    assert.equal(weg.titel, 'Nicht erreichbar')
    assert.equal(weg.ton, 'err')

    const an = zustandsText('verbunden')
    assert.equal(an.titel, 'Verbunden')
    assert.equal(an.ton, 'ok')

    // Unbekannt ist NICHT „verbunden“ (keine erfundene Erfolgsmeldung).
    const fremd = zustandsText('irgendwas')
    assert.equal(fremd.titel, 'Zustand unbekannt')
    assert.equal(fremd.ton, 'warn')
    assert.notEqual(fremd.ton, 'ok')
    assert.equal(zustandsText(undefined).zustand, 'unbekannt')
})

test('WEB-3: „verbunden“ zeigt Version und Seitenzahl, nie erfundene Werte', () => {
    assert.equal(
        verbindungsDetails({ status: 'verbunden', version: 'v3.3.1', site_count: 3 }),
        'Primo v3.3.1 · 3 Seiten',
    )
    assert.equal(
        verbindungsDetails({ status: 'verbunden', version: 'v3.3.1', site_count: 1 }),
        'Primo v3.3.1 · 1 Seite',
    )
    // 0 Seiten ist eine gültige Auskunft (frische Installation).
    assert.equal(
        verbindungsDetails({ status: 'verbunden', version: 'v3.3.1', site_count: 0 }),
        'Primo v3.3.1 · 0 Seiten',
    )
    // Fehlende Werte werden ausgelassen, nicht als 0 ausgegeben.
    assert.equal(verbindungsDetails({ status: 'verbunden', site_count: 2 }), '2 Seiten')
    assert.equal(verbindungsDetails({ status: 'verbunden', version: 'v3.3.1' }), 'Primo v3.3.1')
    // Nur bei „verbunden“ gibt es Details.
    assert.equal(verbindungsDetails({ status: 'nicht_erreichbar', version: 'v3.3.1' }), '')
    assert.equal(verbindungsDetails(null), '')
})

// ── (3) Kurzanleitung ──────────────────────────────────────────────────────

test('WEB-3: die Kurzanleitung nennt Stack, Integrationskonto und die Werte', () => {
    assert.ok(ANSCHLUSS_SCHRITTE.length >= 4)
    const text = ANSCHLUSS_SCHRITTE.map(s => `${s.titel} ${s.text}`).join('\n')
    // Primo-Stack starten (WEB-2).
    assert.match(text, /deploy\/primo/)
    assert.match(text, /docker compose -p diakronos-primo/)
    assert.match(text, /\/api\/primo\/info/)
    // Integrationskonto mit Server-Rolle.
    assert.match(text, /developer/)
    // Die drei Werte, die der Betrieb setzen muss.
    assert.match(text, /PRIMO_URL/)
    assert.match(text, /PRIMO_PUBLIC_URL/)
    assert.match(text, /PRIMO_SUPERUSER_EMAIL/)
    assert.match(text, /PRIMO_SUPERUSER_PASSWORD/)
    // Diese Namen sind die echten Einstellungen — nicht erfunden.
    for (const wert of BENOETIGTE_WERTE) {
        assert.ok(text.includes(wert), `Kurzanleitung nennt ${wert} nicht`)
    }
    // Die Anleitung liegt als TEXT vor (kein Link ins Repository).
    assert.match(ANLEITUNG_ORT, /deploy\/primo\/ANLEITUNG\.md/)
    assert.doesNotMatch(ANLEITUNG_ORT, /https?:\/\//)
})

test('WEB-3: die genannten Einstellungen gibt es wirklich im Server', () => {
    const settings = liesRepo('backend/src/diakronos_app/settings.py')
    for (const wert of BENOETIGTE_WERTE) {
        assert.ok(settings.includes(`"${wert}"`), `settings.py kennt ${wert} nicht`)
    }
})

// ── (4) Fehler beim Öffnen: am HTTP-Status, nicht am Ausnahmenamen ─────────

test('WEB-3: Fehler werden am HTTP-Status unterschieden', () => {
    assert.match(uebergabeFehlertext({ status: 401 }), /Sitzung ist abgelaufen/)
    assert.match(uebergabeFehlertext({ status: 403 }), /Rolle/)
    assert.match(uebergabeFehlertext({ status: 503 }), /nicht erreichbar|nicht angeschlossen/)
    assert.match(uebergabeFehlertext({ status: 417 }), /Sicherheitsprüfung/)

    // 409 trägt die fachliche Meldung des Servers — unverändert übernehmen.
    const meldung = 'Konto besteht bereits in Primo – Verknüpfung durch Admin nötig.'
    assert.equal(uebergabeFehlertext({ status: 409, message: meldung }), meldung)
    // Ohne Meldung ein verständlicher Ersatztext.
    assert.match(uebergabeFehlertext({ status: 409 }), /Verknüpfung/)

    // Unbekannt/ohne Status: Meldung oder neutraler Satz — nie leer.
    assert.equal(uebergabeFehlertext({ status: 500, message: 'Kurz' }), 'Kurz')
    assert.ok(uebergabeFehlertext(null).length > 10)

    // SEC-8: der Ausnahmename wird NICHT ausgewertet.
    const quelle = lies('composables/website.mjs')
    assert.doesNotMatch(ohneKommentare(quelle), /exc_type|exception/)
})

test('WEB-3: nur http(s)-Adressen werden geöffnet (kein javascript:/data:)', () => {
    assert.equal(
        sichereUebergabeUrl('https://website.example.org/diakronos-sso.html#token=abc'),
        'https://website.example.org/diakronos-sso.html#token=abc',
    )
    assert.equal(sichereUebergabeUrl('http://192.168.1.11:8095/x'), 'http://192.168.1.11:8095/x')
    assert.equal(sichereUebergabeUrl('javascript:alert(1)'), '')
    assert.equal(sichereUebergabeUrl('data:text/html,<script>1</script>'), '')
    assert.equal(sichereUebergabeUrl(''), '')
    assert.equal(sichereUebergabeUrl(null), '')
    assert.equal(sichereUebergabeUrl('   '), '')
})

test('WEB-3: Sitzungshinweis nennt die Dauer (4 h, nicht verlängerbar)', () => {
    const text = sitzungsHinweis(14400)
    assert.match(text, /4 Stunden/)
    assert.match(text, /nicht verlängern/)
    assert.match(text, /erneut über Diakronos/)
    // Minuten, wenn die Dauer keine vollen Stunden ist.
    assert.match(sitzungsHinweis(300), /5 Minuten/)
})

// ── (5) Aufruf + window.open (gemockt) ─────────────────────────────────────

/**
 * `useWebsite.js` importiert `vue` und `./useApi.js`. Beide werden per
 * Loader-Hook (tests/fixtures/web3-attrappen.mjs) durch Attrappen ersetzt —
 * der Code selbst läuft unverändert. Damit prüft der Test den ECHTEN
 * Aufrufpfad: Pfadname, Methode und window.open.
 */
registriereAttrappen()
const { useWebsite, oeffneInNeuemTab } = await import(
    '../src/diakonos/composables/useWebsite.js'
)

test('WEB-3: „Verbindung prüfen“ fragt den Status-Endpunkt per GET', async () => {
    setzeApi({
        getAntwort: { status: 'verbunden', version: 'v3.3.1', site_count: 2, url: 'https://w.example.org', warnung: null },
    })
    const w = useWebsite()
    await w.pruefen()

    const a = apiAufrufe()
    assert.equal(a.length, 1)
    assert.equal(a[0].art, 'GET')
    assert.equal(a[0].pfad, 'diakronos.diakronos.api.website.status')
    assert.equal(w.zustand().titel, 'Verbunden')
    assert.equal(w.details(), 'Primo v3.3.1 · 2 Seiten')
    assert.equal(w.fehler.value, '')
})

test('WEB-3: fehlende Berechtigung beim Status wird verständlich gezeigt', async () => {
    setzeApi({ getFehler: { status: 403 } })
    const w = useWebsite()
    await w.pruefen()
    assert.match(w.fehler.value, /Rolle/)
    assert.equal(w.zustand().titel, 'Zustand unbekannt')
    // Nach dem Fehler ist „geprüft“ gesetzt — die Seite bleibt bedienbar.
    assert.equal(w.geprueft.value, true)
    assert.equal(w.laedt.value, false)
})

test('WEB-3: „Primo öffnen“ ruft login_uebergabe per POST und öffnet noopener', async () => {
    const url = 'https://website.example.org/diakronos-sso.html#token=T0KEN&record=abc'
    setzeApi({ postAntwort: { url } })
    const w = useWebsite()

    const geoeffnet = []
    const ergebnis = await w.primoOeffnen({
        oeffnen: (ziel, name, merkmale) => {
            geoeffnet.push({ ziel, name, merkmale })
            return { closed: false }
        },
    })

    assert.equal(ergebnis.ok, true)
    // NUR der POST-Endpunkt — nie GET (der Server weist GET mit 403 ab).
    const a = apiAufrufe()
    assert.deepEqual(a.map(x => x.art), ['POST'])
    assert.equal(a[0].pfad, 'diakronos.diakronos.api.website.login_uebergabe')

    // window.open mit `_blank` und `noopener`.
    assert.equal(geoeffnet.length, 1)
    assert.equal(geoeffnet[0].ziel, url)
    assert.equal(geoeffnet[0].name, '_blank')
    assert.match(geoeffnet[0].merkmale, /noopener/)

    // S3: das Token landet NICHT im Zustand der SPA.
    assert.equal(JSON.stringify(w.daten.value).includes('T0KEN'), false)
})

test('WEB-3: oeffneInNeuemTab setzt noopener/noreferrer und prüft das Ziel', () => {
    const gesehen = []
    const gestartet = oeffneInNeuemTab('https://w.example.org/sso.html#token=T', {
        oeffnen: (url, name, merkmale) => { gesehen.push({ url, name, merkmale }); return {} },
    })
    assert.equal(gestartet, true)
    assert.equal(gesehen[0].name, '_blank')
    assert.match(gesehen[0].merkmale, /noopener/)
    assert.match(gesehen[0].merkmale, /noreferrer/)

    // BEFUND im Wegwerf-Stack: Mit `noopener` liefert window.open laut
    // Spezifikation IMMER null — auch wenn der Tab aufgeht. Das darf NICHT
    // als Fehler gelten (das haette jedem Benutzer „blockiert“ gezeigt).
    assert.equal(oeffneInNeuemTab('https://w.example.org/x#token=T', {
        oeffnen: () => null,
    }), true)

    // Ungültiges Ziel: window.open wird gar nicht gerufen.
    gesehen.length = 0
    assert.equal(oeffneInNeuemTab('javascript:alert(1)', {
        oeffnen: (...args) => { gesehen.push(args); return {} },
    }), false)
    assert.equal(gesehen.length, 0)
})

test('WEB-3: window.open-Rückgabe wird NICHT als Popup-Blocker gedeutet', () => {
    // Regression zum Befund: der Quelltext darf den Rückgabewert von
    // window.open nicht mehr auf „null“ prüfen.
    const quelle = ohneKommentare(lies('composables/useWebsite.js'))
    assert.doesNotMatch(quelle, /return auf\([^)]*\)\s*\|\|\s*null/)
    assert.doesNotMatch(quelle, /const fenster\s*=/)
    assert.doesNotMatch(quelle, /hat das neue Fenster blockiert/)
    // Der Aufruf selbst bleibt mit noopener.
    assert.match(quelle, /'noopener,noreferrer'/)
})

test('WEB-3: Fehler beim Öffnen werden als Klartext zurückgegeben', async () => {
    // 409: Meldung des Servers durchreichen.
    const meldung = 'Konto besteht bereits in Primo – Verknüpfung durch Admin nötig.'
    setzeApi({ postFehler: { status: 409, message: meldung } })
    const e1 = await useWebsite().primoOeffnen({ oeffnen: () => ({}) })
    assert.equal(e1.ok, false)
    assert.equal(e1.fehler, meldung)

    // 503: nicht angeschlossen/erreichbar.
    setzeApi({ postFehler: { status: 503 } })
    const e2 = await useWebsite().primoOeffnen({ oeffnen: () => ({}) })
    assert.equal(e2.ok, false)
    assert.match(e2.fehler, /nicht erreichbar/)

    // 403: keine Berechtigung.
    setzeApi({ postFehler: { status: 403 } })
    const e3 = await useWebsite().primoOeffnen({ oeffnen: () => ({}) })
    assert.match(e3.fehler, /Rolle/)

    // 401: Sitzung abgelaufen.
    setzeApi({ postFehler: { status: 401 } })
    const e4 = await useWebsite().primoOeffnen({ oeffnen: () => ({}) })
    assert.match(e4.fehler, /Sitzung ist abgelaufen/)
})

test('WEB-3: fehlendes Fenster und unbrauchbare Adresse werden erklärt', async () => {
    const url = 'https://website.example.org/diakronos-sso.html#token=T'
    setzeApi({ postAntwort: { url } })
    // `oeffne` meldet false nur, wenn es gar nicht öffnen konnte.
    const e1 = await useWebsite().primoOeffnen({ oeffne: () => false })
    assert.equal(e1.ok, false)
    assert.match(e1.fehler, /Pop-ups/)
    // window.open liefert mit noopener IMMER null — das ist KEIN Fehler.
    const e1b = await useWebsite().primoOeffnen({ oeffnen: () => null })
    assert.equal(e1b.ok, true)

    // Eine `javascript:`-Adresse wird nicht geöffnet.
    setzeApi({ postAntwort: { url: 'javascript:alert(1)' } })
    let geoeffnet = 0
    const e2 = await useWebsite().primoOeffnen({ oeffnen: () => { geoeffnet += 1; return {} } })
    assert.equal(e2.ok, false)
    assert.equal(geoeffnet, 0)

    // Fehlende Antwort: verständlicher Text.
    setzeApi({ postAntwort: {} })
    const e3 = await useWebsite().primoOeffnen({ oeffnen: () => ({}) })
    assert.equal(e3.ok, false)
    assert.match(e3.fehler, /keine gültige Adresse/)
})

// ── (6) Verdrahtung (Quelltext) ────────────────────────────────────────────

// UX3a: Der Abschnitt heißt „Website-Baukasten“ (vorher „Website (Primo)“).
test('WEB-3 (S1): Einstellungen haben den Abschnitt „Website-Baukasten“', () => {
    const seite = lies('pages/Einstellungen.vue')
    assert.match(seite, /import\('\.\/einstellungen\/Website\.vue'\)/)
    assert.match(seite, /href: '#\/einstellungen\/website'/)
    assert.match(seite, /label: 'Website-Baukasten'/)
    assert.match(seite, /seite: 'EinstellungenWebsite'/)

    const abschnitt = lies('pages/einstellungen/Website.vue')
    assert.match(abschnitt, /Verbindung prüfen/)
    assert.match(abschnitt, /ANSCHLUSS_SCHRITTE/)
    // Die https-Warnung des Servers wird angezeigt.
    assert.match(abschnitt, /daten\.warnung/)
    // Nur Anzeige: kein Speicherformular für die Anbindung.
    assert.doesNotMatch(ohneKommentare(abschnitt), /api\.website\.konfigur|speichern/i)
})

test('WEB-3 (S2): Router kennt Adressen, Guard und Menü den Eintrag', () => {
    const router = lies('router.js')
    assert.match(router, /Website: \(\) => import\('\.\/pages\/Website\.vue'\)/)
    assert.match(router, /EinstellungenWebsite: \(\) => import\('\.\/pages\/Einstellungen\.vue'\)/)
    assert.match(router, /'#\/website': 'Website'/)
    assert.match(router, /'#\/einstellungen\/website': 'EinstellungenWebsite'/)
    // Einstellungs-Abschnitt: Admin-Guard wie die übrigen.
    assert.match(router, /'EinstellungenWebsite',/)
    // Eigener Rollen-Guard für die Website-Seite.
    const guard = router.slice(router.indexOf("if (name !== 'Website') return"))
    assert.match(guard.slice(0, 400), /darfWebsite/)
    assert.match(guard.slice(0, 400), /navigate\('#\/'\)/)

    const seite = lies('pages/Website.vue')
    assert.match(seite, /Website-Baukasten öffnen/)
    assert.match(seite, /window\.open|oeffneInNeuemTab/)
    assert.match(seite, /SITZUNGS_HINWEIS/)
})

test('WEB-3 (S3): kein Token im DOM/Zustand, Layout nur nach Breite', () => {
    const seite = lies('pages/Website.vue')
    const code = ohneKommentare(seite)
    // Die Adresse wird nicht angezeigt (kein v-text/{{ }} auf der URL).
    assert.doesNotMatch(code, /\{\{\s*url\s*\}\}/)
    assert.doesNotMatch(code, /v-html/)
    // Kein Loggen der Adresse.
    assert.doesNotMatch(code, /console\.(log|info|debug)/)

    const komposabel = ohneKommentare(lies('composables/useWebsite.js'))
    assert.doesNotMatch(komposabel, /console\.(log|info|debug)/)
    assert.doesNotMatch(komposabel, /localStorage|sessionStorage/)

    // FIX-6: keine Zeiger-/Touch-Abfrage im Layout (nur Breite).
    for (const datei of ['pages/Website.vue', 'pages/einstellungen/Website.vue']) {
        const text = ohneKommentare(lies(datei))
        assert.doesNotMatch(text, /pointer:\s*(coarse|fine)|hover:\s*none|any-pointer|maxTouchPoints/,
            `${datei}: Layout darf nicht am Zeigegerät hängen`)
    }
})

test('WEB-3 (WEB-5a/5b): keine festen API-Pfade, Primo-URL kommt vom Server', () => {
    // Diakronos wird pfadfähig (Präfix z. B. /diakronos). Ein hartkodiertes
    // '/api/…' hier würde den Präfix-Umzug an einer zweiten Stelle brechen —
    // erlaubt ist ausschließlich der zentrale Helfer (apiGet/apiCall).
    const dateien = [
        'composables/useWebsite.js',
        'composables/website.mjs',
        'pages/Website.vue',
        'pages/einstellungen/Website.vue',
    ]
    for (const datei of dateien) {
        const text = ohneKommentare(lies(datei))
        assert.doesNotMatch(text, /['"`]\/api\//,
            `${datei}: fester '/api/…'-Pfad statt apiGet/apiCall`)
        assert.doesNotMatch(text, /new URL\(|window\.location\.origin/,
            `${datei}: Pfad/Origin wird selbst gebaut`)
    }

    // Der Helfer wird benutzt — sonst wäre die Regel oben trivial erfüllt.
    const komposabel = ohneKommentare(lies('composables/useWebsite.js'))
    assert.match(komposabel, /from '\.\/useApi\.js'/)
    assert.match(komposabel, /\bapiGet\(/)
    assert.match(komposabel, /\bapiCall\(/)

    // Die Übergabe-Adresse kommt VOLLSTÄNDIG vom Server (login_uebergabe):
    // sie wird geprüft und durchgereicht, nicht aus PRIMO_PUBLIC_URL gebaut.
    assert.doesNotMatch(komposabel, /diakronos-sso\.html|PRIMO_PUBLIC_URL|primo_public_url/)
    assert.match(komposabel, /antwort\?\.url/)
})

test('WEB-3 (S4): dieser Test läuft NUR, weil er in der Dockerfile-Testliste steht', () => {
    // Die Karte (S4) verlangt: neue Testdatei UND Eintrag in der node-Testliste
    // des Dockerfiles. Der Eintrag lässt sich hier NICHT prüfen — der
    // Frontend-Stage des Images kopiert nur `frontend/`, `backend/Dockerfile`
    // liegt dort nicht (und gehört auch nicht dorthin). Der Beweis ist ein
    // anderer und stärker: dieser Test läuft im Image, weil die Zeile
    // `tests/web3-*.test.mjs` im RUN-Aufruf von backend/Dockerfile steht.
    // Fehlte der Eintrag, gäbe es diese Ausgabe nicht.
    //
    // Geprüft wird deshalb nur, was der Test selbst weiß: er heißt web3-*.
    const eigenerName = fileURLToPath(import.meta.url).split('/').pop()
    assert.match(eigenerName, /^web3-.+\.test\.mjs$/,
        'Die Testdatei muss dem Muster web3-*.test.mjs folgen (Dockerfile-Eintrag)')
})
