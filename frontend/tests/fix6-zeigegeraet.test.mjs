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
 * DEV-B6 (Manuel 09.11., Befund DMB-3a7d335074cc): Der LAYOUT-Satz oben ist
 * AUSDRÜCKLICH GEÄNDERT — „Auf einem Laptop darf nie die Handyleiste kommen.“
 * Gerüst-Stellen hängen jetzt am Token `--layout-mobil` (tokens.css):
 *
 *   (pointer: coarse) and (max-width: 720px),
 *   (max-height: 480px) and (orientation: landscape)
 *
 * Breiten-Regeln bleiben nur dort, wo sie dieselbe Ansicht verdichten statt
 * ein anderes Gerüst zu bauen (Kachel-Raster, Monatszeile, Monatstitel) —
 * siehe `INHALT_STELLEN`. Der Test wurde angepasst, nicht gelöscht
 * (Regel 19); die Begründung steht im Kartenkommentar DEV-B6.
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
// DEV-B6: Handy-GERÜST hängt an der Handy-Lage aus `--layout-mobil`
// (tokens.css, maschinenlesbare Quelle), und zwar als KLASSE
// `.dk-app--handy`, die `App.vue` aus `composables/handyLage.mjs` setzt
// (Review-Nacharbeit 10.11., Punkt 3: „Gerüst-CSS hängt an der Klasse statt
// an ~12 kopierten Media-Strings“). Die GERÜST-Prüfung unten sucht deshalb
// den Klassenselektor; den Token/Zeichenketten-Abgleich prüft
// `tests/dev-b6-*.test.mjs`.
const LAYOUT_TOKEN = '.dk-app--handy'

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

/**
 * Gerüst-Stellen mit eigener Ansicht: sie hängen seit DEV-B6 am Token
 * `--layout-mobil` (Handy-Gerüst nur bei grobem Zeiger und Breite) — nie an
 * einer nackten Breite.
 */
const LAYOUT_STELLEN = [
    ['index.css', '.dk-app', null, 'App-Gerüst (einspaltig)'],
    ['index.css', '.dk-sidebar', null, 'Seitenleiste'],
    ['index.css', '.dk-content', 'padding', 'Fußabstand des Inhalts'],
    ['pages/Home.vue', '.dk-widget-edit-fab', null, 'Bearbeiten-FAB der Startseite'],
    ['pages/Kalender.vue', '.kronos-page-content', 'padding-bottom', 'Fußabstand der Kalenderseite'],
    ['components/kronos/KronosTopbar.vue', '.header-right', null, 'Werkzeugzeile der Kalender-Kopfzeile'],
    ['components/AppBottomNav.vue', '.dk-bottom-nav', null, 'untere Leiste'],
    // DEV-B6: Selektor mit zwei Klassen — sonst verliert die Grundregel
    // `display: none` gegen die eigene `display: inline-flex` des DkButton.
    ['index.css', '.dk-topbar-symbol.dk-menue-knopf', null, 'Menü-Knopf im schmalen Fenster'],
    ['pages/Kalender.vue', '.kal-karte-titel', null, 'Monatstitel im Kartenkopf (mit der Karte)'],
]

/**
 * INHALTS-Stellen: dieselbe Ansicht wird nur dichter (mehr/weniger Spalten,
 * kürzere Beschriftung) — kein anderes Gerüst. Sie bleiben Breiten-Regeln,
 * damit ein 702-px-Mausfenster eine sinnvolle Anordnung behält (DEV-B6).
 */
const INHALT_STELLEN = [
    ['pages/planrahmen/MeineDienste.vue', '.pr-md-monat-zeile', 'Umbruch der Monatszeile'],
]
// DEV-B6b (Review-Nacharbeit 10.11., Punkt 4): `.dk-grid-cols-*` und
// `.dk-widget-*` (und `.dk-stats-row`/`.dk-quick-row`, Toast-Position) sind
// wieder INHALTS-Stellen: ein Einspalten-Umbruch ist Dichte, kein Gerüst.
// Der Laptop bekommt keine untere Leiste (das ist das Gerüst), aber bei
// 400 px Breite passen zwei Spalten schlicht nicht mehr nebeneinander. Sie
// stehen deshalb wieder in DIESER Liste und hängen an der BREITE (≤ 720 px).
// (`.kal-karte-titel` steht seit DEV-B6 bei den GERÜST-Stellen: der Kartenkopf
// verschwindet mit der Karte — das ist der leistenlose Rahmen, nicht Dichte.)

test('FIX-6/DEV-B6: Gerüst-Stellen hängen an der Handy-Lage (Klasse), nicht an der nackten Breite', () => {
    // DEV-B6 (Review-Nacharbeit 10.11.): Das Gerüst steht NICHT mehr in
    // kopierten `@media`-Blöcken, sondern in Regeln mit der Handy-Lage-Klasse
    // `:global(.dk-app--handy) …` (Quelle: `composables/handyLage.mjs`).
    // Geprüft wird deshalb: (a) keine Gerüst-Stelle hängt an einer
    // Media-Breiten-Bedingung, (b) der Klassenselektor steht im Quelltext.
    for (const [pfad, selektor, deklaration, was] of LAYOUT_STELLEN) {
        const text = ohneKommentare(stilTeil(lies(pfad)))
        const kurz = selektor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        // (a) KEINE Gerüst-Regel dieses Selektors in einer Media-Breite
        for (const r of regelnZu(lies(pfad), selektor)) {
            assert.ok(!/max-width|max-height|pointer|hover/.test(r.bedingung || ''),
                `${pfad}/${selektor} (${was}): Gerüst an "${r.bedingung}" — `
                + 'das Gerüst gehört ausschließlich an die Handy-Lage-Klasse (DEV-B6: nie am Laptop)')
        }
        // (b) Der Selektor steht an der Klasse — in `.css` und in den
        // Scoped-Komponenten identisch (`:global` fiel im Vue-Bündel heraus,
        // im Wegwerf-Stack gemessen; die Hüllenklasse ist ein Vorfahre, der
        // Scope-Anhang landet am letzten Selektor im eigenen Markup).
        const praefix = '\\.dk-app--handy'
        const anKlasse = new RegExp(`${praefix}[^{}]*${kurz}`)
        assert.match(text, anKlasse,
            `${pfad}: ${selektor} (${was}) hängt nicht an der Handy-Lage-Klasse`)
        if (deklaration) {
            const bloecke = text.match(new RegExp(`${praefix}[^{}]*\\{[\\s\\S]*?\\}`, 'g')) || []
            assert.ok(bloecke.some((b) => b.includes(deklaration)),
                `${pfad}: ${selektor} (${was}) — Deklaration "${deklaration}" fehlt im Klassen-Block`)
        }
    }
})

test('FIX-6/DEV-B6: Inhalts-Stellen bleiben an der Breite', () => {
    // DEV-B6: Reine Verdichtung derselben Ansicht (Kachel-Raster,
    // Monatszeile) ist KEIN Gerüst — nur dort darf weiter eine Breite
    // entscheiden. `.dk-grid-cols-*` und `.dk-widget-*` sind seit der
    // Nacharbeit Teile des Gerüsts (die App wird in der Handy-Lage
    // einspaltig) und stehen deshalb NICHT mehr in dieser Liste.
    for (const [pfad, selektor, was] of INHALT_STELLEN) {
        const treffer = regelnZu(lies(pfad), selektor)
        assert.ok(treffer.length > 0, `${pfad}: ${selektor} (${was}) steht in keiner @media-Regel`)
        // DEV-B6b: Inhalts-Stellen hängen an der BREITE (≤ 720 px, ohne
        // Zeiger-Teil) — dieselbe Grenze wie das Gerüst, aber ohne Zeiger.
        const engOderLayout = (b) => b === LAYOUT_CSS || /max-width:\s*720px/.test(b || '')
        assert.ok(treffer.some((r) => engOderLayout(r.bedingung)),
            `${pfad}/${selektor} (${was}): erwartet "${LAYOUT_CSS}" oder "(max-width: 720px)" `
            + `(gefunden: ${treffer.map((r) => r.bedingung).join(' | ')})`)
        for (const r of treffer) {
            assert.ok(!/pointer|hover|maxTouchPoints/.test(r.bedingung),
                `${pfad}/${selektor} (${was}): Inhalts-Regel "${r.bedingung}" prüft das Zeigegerät`)
        }
    }
})

const TOUCH_STELLEN = [
    // UX1c: die Mindestgröße kommt aus dem Token `--control-h` (40 px, am
    // groben Zeiger 44 px) statt aus einem Literal. UX1g hat die Altklassen
    // (.dk-btn, .dk-btn-sm, .dk-btn-icon) entfernt — die Mindestbreite hängt
    // jetzt an `.dk-ui-btn`/`.dk-icon-btn` (Knopf), NICHT an `button > svg`
    // (Review UX1c 07.11., Punkt 4: Symbole in Textknöpfen wurden 44 px breit).
    ['index.css', '.dk-ui-btn', 'min-width: var(--control-h)', 'Tippziel-Mindestgröße'],
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
        // „MINWIDTH-CONTROL-H“: Das Merkmal steht in einer Selektoren-LISTE
        // (`.dk-btn-icon, button > svg, …`) — geprüft wird die Regel, die die
        // Deklaration trägt, im Zeiger-Block (UX1c).
        if (selektor === 'MINWIDTH-CONTROL-H') {
            // UX1c: Eine DEKLARATION im Zeiger-Block prüfen (der Selektor steht
            // dort in einer Komma-Liste). Gemessen wird am Rumpf des
            // @media-Blocks, nicht über den Regel-Zerleger: der verschachtelte
            // `:root`-Block der Tokens verwirrt ihn bei `{`/`}`-Zählung.
            const quelle = ohneKommentare(lies(pfad))
            const stelle = quelle.indexOf(`@media ${TOUCH_CSS}`)
            assert.ok(stelle >= 0, `${pfad}: kein @media ${TOUCH_CSS}-Block`)
            let tiefe = 0
            let ende = stelle
            for (; ende < quelle.length; ende += 1) {
                if (quelle[ende] === '{') tiefe += 1
                else if (quelle[ende] === '}') { tiefe -= 1; if (tiefe === 0) break }
            }
            const block = quelle.slice(stelle, ende + 1)
            assert.ok(block.includes(deklaration), `${pfad}: ${selektor} (${was}) steht nicht im Zeiger-Block`)
            assert.ok(!/max-width/.test(quelle.slice(stelle, stelle + 40)),
                `${pfad}: der Zeiger-Block hängt an der Breite (iPad quer verlöre ihn)`)
            continue
        }
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
    // FIX-6b/K2: Der Knopf wird NUR in KronosTopbar.vue geschaltet (720 px,
    // dasselbe Fenster, in dem dort die Kalender-Seitenleiste ausgeblendet
    // wird). Die frühere zweite Regel in index.css (`.kronos-header
    // .sidebar-toggle-btn`, 720 px) war tot: der Selektor erreicht das
    // gescopte Kind-Element der Komponente nicht (scoped-Styles setzen das
    // data-Attribut am Kind, der Selektor verlangt .kronos-header als
    // Vorfahr im SELBEN Element). Zwei Grenzen (720 und 768; seit UX3i EINE:
    // 720) waren zusätzlich
    // der Fehler, den dieser Test verhindern soll — jetzt gibt es EINE.
    // DEV-B6 (Nacharbeit 10.11.): Der Umschalter hing an einer nackten
    // Breiten-Regel; er hängt jetzt an der Handy-Lage (Klasse) UND ist in der
    // Vorlage abgeschaltet (`v-if="zeigeListenUmschalter"`, Standard false) —
    // sonst gäbe es neben dem Menü-Knopf einen zweiten Navigationseinstieg.
    const tief = ohneKommentare(lies('components/kronos/KronosTopbar.vue'))
    assert.match(tief, /.dk-app--handy \.sidebar-toggle-btn \{ display: inline-flex; \}/,
        'KronosTopbar: Sichtbarkeit des Seitenleisten-Knopfs hängt an der Handy-Lage')
    assert.ok(!/@media \(max-width: 720px\)[\s\S]{0,200}\.sidebar-toggle-btn \{ display: inline-flex; \}/.test(tief),
        'KronosTopbar: KEINE zweite Breiten-Regel für den Seitenleisten-Knopf')
    assert.match(tief, /v-if="zeigeListenUmschalter"/,
        'KronosTopbar: Listen-Umschalter ist abschaltbar (genau EIN Navigationseinstieg)')
    const css = ohneKommentare(lies('index.css'))
    assert.ok(!css.includes('.kronos-header .sidebar-toggle-btn'),
        'index.css: die tote Regel `.kronos-header .sidebar-toggle-btn` ist wieder da — '
        + 'den Knopf schaltet allein KronosTopbar.vue (eine Grenze, 720 px)')
})

test('FIX-6: index.css trennt Layout- und Touch-Block', () => {
    const bedingungen = mediaBedingungen(lies('index.css'))
    assert.ok(bedingungen.includes(TOUCH_CSS), 'index.css: Touch-Block (pointer: coarse) fehlt')
    // DEV-B6 (Nacharbeit 10.11.): Das Gerüst steht NICHT mehr als eigener
    // `@media`-Block, sondern als Klassen-Regel (`:global(.dk-app--handy) …`,
    // eine Quelle mit dem Skript). Der Test prüft deshalb: die Klasse ist da,
    // und KEIN Gerüst-@media existiert mehr (keine zweite Entscheidung).
    const text = ohneKommentare(lies('index.css'))
    assert.ok(text.includes(LAYOUT_TOKEN), 'index.css: Handy-Lage-Klasse fehlt')
    for (const g of ['.dk-app', '.dk-sidebar']) {
        const kurz = g.replace('.', '\\.')
        const imMedia = text.match(new RegExp(`@media[^{]*\\{[^{}]*${kurz}\\s*\\{[^}]*\\}`, 'g')) || []
        const geruest = imMedia.filter((b) => /max-width|max-height|pointer/.test(b.split('{')[0]))
        assert.equal(geruest.length, 0,
            `index.css: ${g} steht noch in einer Gerüst-@media-Regel: ${geruest.join(' | ')}`)
    }
    // Ein nackter 720-px-Block bleibt nur für Inhalts-Stellen derselben
    // Ansicht — die prüft der Test oben.
    assert.ok(bedingungen.includes(LAYOUT_CSS), 'index.css: Inhalts-Block (720 px) fehlt')
})

// ── UX1c: der Zeiger-Block steht (genau einmal) am Dateiende ───────────────
test('UX1c: der Touch-Block steht am Dateiende, nach allen Grundregeln', () => {
    // Regression UX1c/C3: Stand der Block hinter den Komponenten-Regeln bzw. in
    // einem `@layer`, blieb es bei gemessenen 40/34/42 px statt 44 px. Es darf
    // genau EINEN `(pointer: coarse)`-Block geben (p3-4c), und er muss vor den
    // Grundregeln stehen.
    const text = ohneKommentare(lies('index.css'))
    const alle = [...text.matchAll(/@media\s*\(pointer:\s*coarse\)\s*\{/g)]
    assert.equal(alle.length, 1, 'index.css: genau ein grobe-Zeiger-Block erwartet')
    // Review UX1c 07.11., Punkt 1: Am Dateianfang (vor den `@import`s) ist der
    // Block nach CSS-Spezifikation ungültig und verliert bei gleicher
    // Spezifität gegen die späteren Grundregeln. Er muss HINTER den
    // `@import`-Anweisungen und hinter den Komponenten-Regeln stehen.
    const importEnde = Math.max(
        ...[...text.matchAll(/@import\s+[^;]+;/g)].map((m) => m.index + m[0].length))
    assert.ok(alle[0].index > importEnde,
        'index.css: der Zeiger-Block steht vor den @import-Anweisungen (ungültig)')
    const grundregel = text.indexOf('.dk-ui-btn {')
    if (grundregel >= 0) {
        assert.ok(alle[0].index > grundregel,
            'index.css: der Zeiger-Block steht vor der Knopf-Grundregel (§ Kaskade)')
    }
    assert.ok(text.slice(alle[0].index).includes('min-height: var(--control-h) !important'),
        'index.css: der Zeiger-Block setzt keine Tippziel-Mindestgröße aus dem Token')
})
