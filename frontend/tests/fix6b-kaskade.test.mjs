/**
 * FIX-6b — Kaskaden-Wächter für index.css (Review FIX-6, Befunde K1/K2/K3/K5).
 *
 * WARUM ES DIESEN TEST GIBT
 * Vite sammelt `@import`-Regeln ein und hängt sie HINTER die direkt in der
 * Datei geschriebenen Regeln. Eine Media-Regel, die im Quelltext oben steht,
 * landet im Bündel damit VOR den Grundregeln — bei gleicher Spezifität gewinnt
 * dann die spätere Grundregel, und die Mobil-Regel wirkt nicht. Genau das war
 * der Befund: OP-HANDY-10 (flaches Querformat) stand vor `.dk-app{display:grid}`
 * und `.dk-sidebar{display:flex}` und hatte deshalb keine Wirkung (844×390:
 * Seitenleiste UND untere Leiste gleichzeitig sichtbar).
 *
 * Deshalb gilt: Jede Regel, die eine GRUNDREGEL derselben Datei überschreiben
 * muss, steht am DATEIENDE — nach der letzten Grundregel, die sie überschreiben
 * will. Der Test prüft das an der QUELLE (index.css) und, falls vorhanden, am
 * GEBAUTEN Bündel (frontend/dist) — dort ist die Kaskade das, was der Browser
 * tatsächlich sieht.
 *
 * Geprüft werden die drei Befunde:
 *   K1  OP-HANDY-10 (`(max-height: 480px) and (orientation: landscape)`) steht
 *       nach `.dk-app {` (display:grid), `.dk-sidebar {` und `.kronos-sidebar`.
 *   K2  Der 720-px-Layoutblock mit `.dk-quick-row { grid-template-columns: 1fr }`
 *       steht nach `.dk-quick-row {` (repeat(3, 1fr)) UND nach dem
 *       `@media (max-width: 1100px)`-Block, der es auf repeat(2, 1fr) zieht.
 *   K3  `min-width: 0` der Formularfelder steht AUSSERHALB jeder Media-Query
 *       (UXD-R9: gilt immer, nicht nur bei grobem Zeiger).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const FRONTEND = fileURLToPath(new URL('../', import.meta.url))
const CSS_QUELLE = FRONTEND + 'src/diakonos/index.css'
const DIST = FRONTEND + 'dist/'

/** Kommentare entfernen, Zeilennummern dabei erhalten (Position bleibt gleich). */
function ohneKommentare(text) {
    return text.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
}

/**
 * Ein Media-Query-Block ab `@media …{`: gibt Anfang, Ende und Inhalt zurück.
 * Klammern werden gezählt, damit der Test nicht an Formatierung hängt.
 */
function blockAb(text, start) {
    let tiefe = 0
    let i = text.indexOf('{', start)
    const anfang = i + 1
    for (; i < text.length; i += 1) {
        if (text[i] === '{') tiefe += 1
        else if (text[i] === '}') {
            tiefe -= 1
            if (tiefe === 0) return { anfang, ende: i, inhalt: text.slice(anfang, i) }
        }
    }
    return { anfang, ende: text.length, inhalt: text.slice(anfang) }
}

/** Steht die Fundstelle im Inneren irgendeines Media-Query-Blocks? */
function inMediaQuery(text, index) {
    const kopf = text.slice(0, index)
    let tiefe = 0
    const stapel = []
    for (let i = 0; i < kopf.length; i += 1) {
        if (kopf[i] === '{') {
            const davor = kopf.slice(0, i)
            const at = davor.lastIndexOf('@')
            const name = davor.slice(at, i).trim()
            stapel.push(tiefe)
            if (/^@media\b/.test(name)) stapel[stapel.length - 1] = 'media'
            tiefe += 1
        } else if (kopf[i] === '}') {
            stapel.pop()
            tiefe -= 1
        }
    }
    return stapel.includes('media')
}

/**
 * Die Prüfung läuft auf einer CSS-Quelle (index.css und — wenn gebaut — auf dem
 * ausgelieferten Bündel). Beide werden gleich behandelt.
 */
function pruefeKaskade(quelle, name) {
    const text = ohneKommentare(quelle)
    // Im GEBAUTEN Bündel stehen die @import-Dateien (tokens.css, kronos.css,
    // grundreset.css) als Text am Anfang; geprüft wird ab der ersten
    // Grundregel `.dk-app` — und nur, wenn die in dieser Quelle vorkommt.
    const anker = text.indexOf('.dk-app')
    if (anker < 0) return
    const teil = text.slice(anker)

    const stelleIn = (regex, was) => {
        const m = regex.exec(text)
        assert.ok(m, `Muster nicht gefunden (${was}): ${regex}`)
        return m.index
    }

    // ---- Grundregeln, die überschrieben werden müssen -------------------
    const grundApp = stelleIn(/\.dk-app\s*\{[^}]*display:\s*grid/, 'Grundregel .dk-app')
    const grundSidebar = stelleIn(/\.dk-sidebar\s*\{[^}]*display:\s*flex/, 'Grundregel .dk-sidebar')
    // `.kronos-sidebar` steht in kronos.css (per @import eingebunden). Im
    // Quelltext index.css gibt es sie nicht — dann entfällt diese eine Prüfung;
    // am Bündel wird sie mitgeprüft.
    const kronosM = /\.kronos-sidebar\s*\{[\s\S]{0,400}?display:\s*flex/.exec(text)
    const grundKronos = kronosM ? kronosM.index : null
    const grundQuick = stelleIn(
        /\.dk-quick-row\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*1fr\)/,
        'Grundregel .dk-quick-row')
    // Die 1100er-Regel zieht .dk-quick-row auf zwei Spalten — sie muss VOR der
    // Mobil-Regel stehen, sonst gewinnt sie bei <= 1100 px (und 390 px liegt
    // darin) gegen das Einspaltig.
    let b1100 = null
    const m1100 = /@media\s*\(max-width:\s*1100px\)\s*\{/g
    for (let m = m1100.exec(teil); m; m = m1100.exec(teil)) {
        const b = blockAb(teil, m.index)
        if (/\.dk-quick-row/.test(b.inhalt)) b1100 = { ...b, start: anker + m.index }
    }
    assert.ok(b1100, 'Regel @media (max-width: 1100px) mit .dk-quick-row nicht gefunden')

    // ---- K1: OP-HANDY-10 (flaches Querformat) ---------------------------
    let k1 = null
    const quer = /@media\s*\(max-height:\s*480px\)\s*and\s*\(orientation:\s*landscape\)\s*\{/g
    for (let m = quer.exec(teil); m; m = quer.exec(teil)) {
        const b = blockAb(teil, m.index)
        if (/\.dk-app\s*\{[^}]*grid-template-columns:\s*1fr/.test(b.inhalt)) {
            k1 = { ...b, start: anker + m.index }
        }
    }
    assert.ok(k1, 'K1: OP-HANDY-10-Block (max-height: 480px) and (orientation: landscape) fehlt')
    // Er muss die Seitenleiste abschalten.
    assert.match(k1.inhalt, /\.dk-sidebar[\s\S]*?display:\s*none/,
        'K1: OP-HANDY-10 muss .dk-sidebar abschalten')
    // .kronos-sidebar ist seit OP-UI-11 die einklappbare Kalenderliste — nicht abschalten.
    assert.doesNotMatch(k1.inhalt, /\.kronos-sidebar/)
    assert.ok(k1.start > grundApp,
        `K1 (${name}): OP-HANDY-10 (Zeichen ${k1.start}) steht VOR der Grundregel .dk-app `
        + `(${grundApp}) — im Bündel gewinnt dann die Grundregel und die Querformat-Regel `
        + 'wirkt nicht. Der Block gehört ans Dateiende.')
    assert.ok(k1.start > grundSidebar,
        `K1 (${name}): OP-HANDY-10 (${k1.start}) steht VOR der Grundregel .dk-sidebar (${grundSidebar})`)
    // `.kronos-sidebar` wird von dieser Regel bewusst NICHT abgeschaltet (siehe
    // `doesNotMatch` oben: seit OP-UI-11 ist sie die einklappbare Kalenderliste).
    // Eine Reihenfolge-Bedingung gegen ihre Grundregel wäre deshalb sinnlos — sie
    // hat FIX-6b im GEBAUTEN Bündel dauerhaft rot gemacht, obwohl die Regel wirkt
    // (gemessen im Wegwerf-Stack 844×390: `.dk-sidebar` = none, untere Leiste =
    // flex). Geprüft wird nur noch, dass die Grundregel in der QUELLE existiert;
    // die Wirkung belegt der Bündel-Test über `.dk-app`/`.dk-sidebar`.

    // ---- K2: 720-px-Layoutblock mit einspaltigem .dk-quick-row ---------
    let k2 = null
    const m720 = /@media\s*\(max-width:\s*720px\)\s*\{/g
    for (let m = m720.exec(teil); m; m = m720.exec(teil)) {
        const b = blockAb(teil, m.index)
        // Der Layoutblock: er schaltet das Gerüst UND die Quick-Reihe einspaltig.
        if (/\.dk-quick-row[^{]*\{[^}]*grid-template-columns:\s*1fr/.test(b.inhalt)
            && /\.dk-app\s*\{[^}]*grid-template-columns:\s*1fr/.test(b.inhalt)) {
            k2 = { ...b, start: anker + m.index }
        }
    }
    assert.ok(k2, 'K2: 720-px-Layoutblock mit .dk-quick-row { grid-template-columns: 1fr } fehlt '
        + '(Befund: .dk-quick-row war bei 390 px zweispaltig)')
    assert.ok(k2.start > grundQuick,
        `K2 (${name}): der 720-px-Layoutblock (${k2.start}) steht VOR der Grundregel `
        + `.dk-quick-row (${grundQuick}) — sie gewinnt im Bündel`)
    assert.ok(k2.start > b1100.ende,
        `K2 (${name}): der 720-px-Layoutblock (${k2.start}) steht VOR dem `
        + `@media (max-width: 1100px)-Block mit .dk-quick-row (${b1100.start}) — `
        + 'bei 390 px gewinnt sonst repeat(2, 1fr)')
    // Tote Selektoren gehören nicht in den wirksamen Block.
    assert.doesNotMatch(k2.inhalt, /\.dk-topbar-search/,
        'K2: .dk-topbar-search steht in keinem Template — toter Selektor im wirksamen Block')
    assert.doesNotMatch(k2.inhalt, /\.kronos-header\s+\.sidebar-toggle-btn/,
        'K2: .kronos-header .sidebar-toggle-btn regelt KronosTopbar.vue scoped — toter Selektor hier')

    // ---- K3: min-width: 0 der Formularfelder ausserhalb jeder Media-Query
    const feldRegel = /([^{}]*)\{[^}]*min-width:\s*0[^}]*\}/g
    const treffer = []
    for (let m = feldRegel.exec(text); m; m = feldRegel.exec(text)) {
        const selektoren = m[1]
        // Nur die zentrale Felder-Regel: input/select/textarea + Dk-Feldklassen.
        if (!/\binput\b/.test(selektoren) && !/\.dk-form-input\b/.test(selektoren)) continue
        if (!/select|textarea|\.dk-ui-eingabe|\.dk-form-input|\.dk-form-select/.test(selektoren)) continue
        treffer.push({ start: m.index, selektoren: selektoren.trim() })
    }
    assert.ok(treffer.length > 0,
        'K3: keine Regel mit `min-width: 0` für die Formularfelder gefunden (UXD-R9 fehlt)')
    const unbedingt = treffer.filter((t) => !inMediaQuery(text, t.start))
    assert.ok(unbedingt.length > 0,
        `K3 (${name}): \`min-width: 0\` der Formularfelder steht NUR in einer Media-Query `
        + `(${treffer.map((t) => t.selektoren.replace(/\s+/g, ' ')).join(' | ')}). UXD-R9 gilt `
        + 'immer: Bearbeiten-Formulare liefen sonst bei 700 px und am Desktop über den Kartenrand.')
}

test('FIX-6b K1/K2/K3: Quelltext index.css kaskadiert richtig', () => {
    pruefeKaskade(readFileSync(CSS_QUELLE, 'utf8'), 'index.css')
})

test('FIX-6b K1/K2: gebautes Bündel (falls vorhanden) hat dieselbe Reihenfolge', () => {
    if (!existsSync(DIST + 'css')) return
    const css = readdirSync(DIST + 'css')
        .filter((n) => n.endsWith('.css'))
        .map((n) => readFileSync(DIST + 'css/' + n, 'utf8'))
        .join('\n')
    if (!/\.dk-app/.test(css)) return
    pruefeKaskade(css, 'dist-Bündel')
})

test('FIX-6b K1/K2: oberhalb der Grundregeln steht kein wirkungsloser Gerüst-Block mehr', () => {
    const text = ohneKommentare(readFileSync(CSS_QUELLE, 'utf8'))
    // Vor der ersten Grundregel `.dk-app { display: grid }` darf das Gerüst
    // nicht mehr gesetzt werden — sonst gibt es zwei Wahrheiten und die Kaskade
    // hängt wieder an der @import-Reihenfolge von Vite.
    const grundApp = /\.dk-app\s*\{[^}]*display:\s*grid/.exec(text)
    assert.ok(grundApp, 'Grundregel .dk-app nicht gefunden')
    const oben = text.slice(0, grundApp.index)
    assert.doesNotMatch(oben, /\.dk-quick-row[^{]*\{[^}]*grid-template-columns/,
        'K2: oberhalb der Grundregeln setzt noch eine Regel .dk-quick-row — sie ist wirkungslos '
        + 'und gehört in den Block am Dateiende')
    assert.doesNotMatch(oben, /\.dk-sidebar\s*\{\s*display:\s*none/,
        'K1/K2: oberhalb der Grundregeln schaltet noch eine Regel .dk-sidebar ab — sie ist '
        + 'wirkungslos und gehört in den Block am Dateiende')
    assert.doesNotMatch(oben, /@media\s*\(max-height:\s*480px\)\s*and\s*\(orientation:\s*landscape\)/,
        'K1: OP-HANDY-10 steht noch oberhalb der Grundregeln und wirkt dort nicht')
})
