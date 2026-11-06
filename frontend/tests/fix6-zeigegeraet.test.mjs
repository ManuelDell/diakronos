/**
 * FIX-6 — Touch-Gerät mit Maus/Desktop-Breite zeigt Desktop-Elemente
 * (Befund DMB-d446e449ba22, Rest nach der unteren Leiste).
 *
 * Befund: Auf einem Zeigegerät, das Touch KANN, dessen primärer Zeiger aber
 * grob ist (Notebook mit Touchscreen, Convertible, Tablet im Querformat),
 * erschienen bei Desktop-Breite (gemessen: Viewport 1410×755, Route #/)
 * mobile Bedienelemente.
 *
 * Kriterien dieser Karte (Operator-Entscheidung 27.10., EINE Stelle im Code:
 * `composables/eingabeart.mjs`):
 *
 *   LAYOUT (Seitenleiste vs. Mobil-Layout inkl. unterer Leiste, einspaltige
 *   Raster, Desktop-Kopfzeile): NUR `Breite <= 720 px`, egal welches
 *   Zeigegerät. Ein schmales Fenster MIT Maus bekommt Mobil-Layout, ein
 *   Touch-Laptop mit 1410 px Desktop.
 *
 *   TOUCH (16-px-Felder gegen den iOS-Zoom, Tippziel-Mindestgrößen): NUR
 *   `(pointer: coarse)`, unabhängig von der Breite (iPad quer behält sie).
 *
 *   Nie Kriterium: die bloße Touch-Fähigkeit (`any-pointer`, maxTouchPoints,
 *   ontouchstart) — und auch nicht `any-pointer: fine`.
 *
 * FIX-6c: Die Logiktests für `istMobilLayout` / `istTouch` / `lageImBrowser`
 * sind entfallen — diese Helfer waren toter Code (keine Komponente nutzte
 * sie) und sind entfernt; `tests/fix6c-toter-code.test.mjs` wacht darüber.
 * Was hier bleibt, ist die EINE Grenze und die Prüfung der Quellen.
 *
 * Geprüft wird:
 *   1. Die eine Mobilgrenze und ihre Abfrage (720 px, inklusive).
 *   2. Layout-Stellen (FAB, Fußabstand, untere Leiste, Kopfzeile,
 *      Monatszeile, Raster) hängen NUR an der Breite.
 *   3. Touch-Stellen (16-px-Felder, Tippziele, Datumsfeld) hängen NUR am
 *      groben Zeiger.
 *   4. Keine Altregel (`hover: none`, `any-pointer`, `maxTouchPoints`) in den
 *      Quelldateien.
 *   5. PrTabelle nutzt die eine Breitengrenze der App (720 px) statt 640 px.
 *
 * Nicht hier geprüft (im Frontend-Build-Stage liegen diese Dateien nicht):
 * die Login-Masken in spa.py / routen.py — das übernehmen der Python-Test
 * `backend/tests/test_fix6_zeigegeraet.py` und der Syntaxwächter
 * `tests/fix6-keine-zeiger-syntax.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
    MOBIL_GRENZE_PX,
} from '../src/diakonos/composables/eingabeart.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

/** Erwartete CSS-Fassungen. */
const LAYOUT_CSS = '(max-width: 720px)'
const TOUCH_CSS = '(pointer: coarse)'

/** Kommentare entfernen, damit Kommentartext nicht als Regel zählt. */
function ohneKommentare(text) {
    return text
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
}

/** Nur der <style>-Teil einer .vue-Datei (sonst zählt Template-Text mit). */
function stilTeil(quelle) {
    const start = quelle.search(/<style[^>]*>/)
    if (start < 0) return quelle
    return quelle.slice(start).replace(/<\/?style[^>]*>/g, '')
}

/**
 * Alle Regeln (Bedingung + Selektor + Rumpf), in Reihenfolge.
 * `bedingung` ist null bei Regeln außerhalb eines @media-Blocks.
 */
function regeln(quelle) {
    const text = ohneKommentare(stilTeil(quelle))
    const treffer = []
    const stapel = []
    let puffer = ''
    let seitLetzterKlammer = ''
    for (const zeichen of text) {
        if (zeichen === '{') {
            stapel.push({ kopf: puffer.trim(), rumpfStart: seitLetzterKlammer })
            puffer = ''
            seitLetzterKlammer = ''
        } else if (zeichen === '}') {
            const offen = stapel.pop() || { kopf: '', rumpfStart: '' }
            if (offen.kopf.startsWith('@media')) {
                treffer.push({ bedingung: offen.kopf.slice('@media'.length).trim(), rumpf: '' })
            } else if (!offen.kopf.startsWith('@')) {
                const mediaOffen = stapel.filter((s) => s.kopf.startsWith('@media')).pop()
                treffer.push({
                    bedingung: mediaOffen ? mediaOffen.kopf.slice('@media'.length).trim() : null,
                    selektor: offen.kopf,
                    rumpf: seitLetzterKlammer,
                })
            }
            puffer = ''
            seitLetzterKlammer = ''
        } else {
            puffer += zeichen
            seitLetzterKlammer += zeichen
        }
    }
    return treffer
}

/** Alle @media-Bedingungen einer Quelle (ohne Kommentare). */
function mediaBedingungen(quelle) {
    const text = ohneKommentare(stilTeil(quelle))
    return [...text.matchAll(/@media\s*([^{]+)\{/g)].map((m) => m[1].trim())
}

/** Regeln zu einem Selektor (Komma-Listen einzeln) innerhalb einer @media-Regel. */
function regelnZu(quelle, selektor) {
    return regeln(quelle).filter((r) => r.bedingung
        && (r.selektor || '').split(',').some((s) => s.trim() === selektor))
}

// ── 1. Die eine Grenze ──────────────────────────────────────────────────────

test('FIX-6: die eine Mobilgrenze ist 720 px (Grenze gehört dazu)', () => {
    assert.equal(MOBIL_GRENZE_PX, 720, 'die Mobilgrenze der App ist 720 px')
})

// ── 2. Quellen ──────────────────────────────────────────────────────────────

/** Alle .vue/.css/.mjs unter src/diakonos (rekursiv), ohne Testdateien. */
function quellen(suffixe = ['.vue', '.css', '.mjs']) {
    const wurzel = fileURLToPath(WURZEL)
    const gefunden = []
    const lauf = (dir) => {
        for (const name of readdirSync(dir)) {
            const pfad = dir + '/' + name
            if (statSync(pfad).isDirectory()) { lauf(pfad); continue }
            if (suffixe.some((s) => name.endsWith(s)) && !name.includes('.test.')) gefunden.push(pfad)
        }
    }
    lauf(wurzel)
    return gefunden
}

const LAYOUT_STELLEN = [
    ['index.css', '.dk-app', null, 'App-Gerüst (einspaltig)'],
    ['index.css', '.dk-sidebar', null, 'Seitenleiste'],
    ['index.css', '.dk-grid-cols-2', null, 'Kachel-Raster'],
    ['index.css', '.dk-widget-large', null, 'Widget-Raster'],
    ['pages/Home.vue', '.dk-widget-edit-fab', null, 'Bearbeiten-FAB der Startseite'],
    ['pages/Kalender.vue', '.kronos-page-content', 'padding-bottom', 'Fußabstand der Kalenderseite'],
    ['pages/planrahmen/MeineDienste.vue', '.pr-md-monat-zeile', null, 'Umbruch der Monatszeile'],
    // UX3d: Der Eintrag „Zu prüfen“ ist der vierte Reiter der Kalender-Leiste
    // geworden. Das ist die Stelle, an der früher die Beschriftung des
    // Kopfzeilen-Knopfes am Handy wich — sie hält weiter an der BREITE.
    ['components/kronos/KronosTopbar.vue', '.kronos-reiter', null, 'Reiterleiste des Kalenders'],
    ['components/kronos/KronosTopbar.vue', '.date-year', null, 'Jahreszahl der Kopfzeile'],
    ['components/kronos/KronosTopbar.vue', '.resource-toggle-btn', null, 'Ressourcenplan-Knopf'],
    ['components/AppBottomNav.vue', '.dk-bottom-nav', null, 'untere Leiste'],
]

test('FIX-6: Layout-Stellen hängen an der Breite (720 px), nicht am Zeiger', () => {
    for (const [pfad, selektor, deklaration, was] of LAYOUT_STELLEN) {
        const treffer = regelnZu(lies(pfad), selektor)
            .filter((r) => !deklaration || (r.rumpf || '').includes(deklaration))
        assert.ok(treffer.length > 0, `${pfad}: ${selektor} (${was}) steht in keiner @media-Regel`)
        assert.ok(treffer.some((r) => r.bedingung === LAYOUT_CSS),
            `${pfad}/${selektor} (${was}): erwartet "${LAYOUT_CSS}" (gefunden: ${treffer.map((r) => r.bedingung).join(' | ')})`)
        for (const r of treffer) {
            assert.ok(!/pointer|hover|maxTouchPoints/.test(r.bedingung),
                `${pfad}/${selektor} (${was}): Layout-Regel "${r.bedingung}" prüft noch das Zeigegerät`)
        }
    }
})

const TOUCH_STELLEN = [
    ['index.css', '.dk-btn-icon', 'min-width: 24px', 'Tippziel-Mindestgröße'],
    ['components/ui/DkDatumZeit.vue', '.dk-ui-datumzeit-eingabe', 'min-height: 44px', 'Datums-/Zeitfeld'],
]
// FIX-6b/K3: Die 16-px-Felder (`font-size: 16px`) hängen am groben Zeiger —
// `min-width: 0` derselben Felder dagegen NICHT: UXD-R9 (Felder dürfen unter
// ihre Inhaltsbreite schrumpfen) gilt bei jeder Breite und jedem Zeiger, sonst
// laufen Bearbeiten-Formulare bei feinem Zeiger über den Kartenrand. Die
// unbedingte Regel prüft `fix6b-kaskade.test.mjs` (K3).

test('FIX-6b/K3: `min-width: 0` der Felder steht NICHT im Zeiger-Block', () => {
    const treffer = regeln(lies('index.css'))
        .filter((r) => (r.selektor || '').split(',').some((s) => s.trim() === 'input'))
        .filter((r) => (r.rumpf || '').includes('min-width: 0'))
    for (const r of treffer) {
        assert.ok(!r.bedingung,
            `index.css/input: \`min-width: 0\` steht in der @media-Regel "${r.bedingung}" — `
            + 'UXD-R9 gilt unbedingt (auch bei feinem Zeiger), nicht nur am Touchgerät')
    }
})

test('FIX-6: Touch-Stellen hängen am groben Zeiger, nicht an der Breite', () => {
    for (const [pfad, selektor, deklaration, was] of TOUCH_STELLEN) {
        const treffer = regeln(lies(pfad)).filter((r) => r.bedingung
            && (r.selektor || '').split(',').some((s) => s.trim() === selektor))
            .filter((r) => (r.rumpf || '').includes(deklaration))
        assert.ok(treffer.length > 0, `${pfad}: ${selektor} (${was}) steht in keiner @media-Regel`)
        assert.ok(treffer.some((r) => r.bedingung === TOUCH_CSS),
            `${pfad}/${selektor} (${was}): erwartet "${TOUCH_CSS}" (gefunden: ${treffer.map((r) => r.bedingung).join(' | ')})`)
        for (const r of treffer) {
            assert.ok(!/max-width|min-width:\s*\d+px\)/.test(r.bedingung),
                `${pfad}/${selektor} (${was}): Touch-Regel "${r.bedingung}" hängt an der Breite (iPad quer verlöre sie)`)
        }
    }
})

test('FIX-6: keine Altregel in den Quelldateien', () => {
    for (const pfad of quellen()) {
        const text = ohneKommentare(stilTeil(readFileSync(pfad, 'utf8')))
        assert.ok(!/\(hover:\s*none\)/.test(text), `${pfad}: (hover: none) ist noch aktiv`)
        assert.ok(!/any-pointer/.test(text), `${pfad}: any-pointer ist noch aktiv (Touch-Fähigkeit ist kein Kriterium)`)
        assert.ok(!/maxTouchPoints|ontouchstart/.test(text), `${pfad}: Touch-Fähigkeit wird als Kriterium benutzt`)
    }
})

test('FIX-6: PrTabelle nutzt die eine Breitengrenze der App (720 px)', () => {
    const text = lies('components/planrahmen/PrTabelle.vue')
    const treffer = text.match(/const MOBIL_ABFRAGE = (['"`])(.+?)\1/)
    assert.ok(treffer, 'PrTabelle: MOBIL_ABFRAGE fehlt')
    const abfrage = treffer[2]
    assert.ok(abfrage.includes('MOBIL_GRENZE_PX'),
        `PrTabelle: Abfrage "${abfrage}" soll an MOBIL_GRENZE_PX (720 px) hängen statt an einer eigenen Zahl`)
    assert.ok(!/\b6[0-9]0px\b/.test(abfrage), 'PrTabelle: eigene 640-px-Grenze ist weg')
    assert.ok(!/pointer|hover/.test(abfrage), 'PrTabelle: Layout-Abfrage prüft kein Zeigegerät')
    assert.match(text, /import \{[^}]*MOBIL_GRENZE_PX[^}]*\} from '\.\.\/\.\.\/composables\/eingabeart\.mjs'/,
        'PrTabelle: MOBIL_GRENZE_PX wird nicht importiert')
})

test('FIX-6: KronosTopbar blendet den Seitenleisten-Knopf nicht doppelt', () => {
    // FIX-6b/K2: Der Knopf wird NUR in KronosTopbar.vue geschaltet (768 px,
    // dasselbe Fenster, in dem dort die Kalender-Seitenleiste ausgeblendet
    // wird). Die frühere zweite Regel in index.css (`.kronos-header
    // .sidebar-toggle-btn`, 720 px) war tot: der Selektor erreicht das
    // gescopte Kind-Element der Komponente nicht (scoped-Styles setzen das
    // data-Attribut am Kind, der Selektor verlangt .kronos-header als
    // Vorfahr im SELBEN Element). Zwei Grenzen (720 und 768) waren zusätzlich
    // der Fehler, den dieser Test verhindern soll — jetzt gibt es EINE.
    const tief = ohneKommentare(lies('components/kronos/KronosTopbar.vue'))
    assert.ok(!tief.includes('.sidebar-toggle-btn { display: inline-flex; }\n\n'),
        'KronosTopbar: unerwartete Leerzeile im Umschalter-Block')
    assert.ok(/@media \(max-width: 768px\)[\s\S]*?\.sidebar-toggle-btn \{ display: inline-flex; \}/.test(tief),
        'KronosTopbar: Breiten-Regel (768 px) für den Seitenleisten-Knopf fehlt')
    const css = ohneKommentare(lies('index.css'))
    assert.ok(!css.includes('.kronos-header .sidebar-toggle-btn'),
        'index.css: die tote Regel `.kronos-header .sidebar-toggle-btn` ist wieder da — '
        + 'den Knopf schaltet allein KronosTopbar.vue (eine Grenze, 768 px)')
})

test('FIX-6: index.css trennt Layout- und Touch-Block', () => {
    const bedingungen = mediaBedingungen(lies('index.css'))
    assert.ok(bedingungen.includes(LAYOUT_CSS), 'index.css: Layout-Block (720 px) fehlt')
    assert.ok(bedingungen.includes(TOUCH_CSS), 'index.css: Touch-Block (pointer: coarse) fehlt')
})
