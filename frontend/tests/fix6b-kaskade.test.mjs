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
 *       DEV-B6 (09.11.): Der Block steht jetzt als Handy-Lage-Block (Bedingung
 *       aus `--layout-mobil`, tokens.css) am
 *       Dateiende (Token aus tokens.css) — gesucht wird deshalb der Block, der
 *       `.dk-app` einspaltig macht, samt seiner Bedingung.
 *   K2  Der Handy-Gerüst-Block mit `.dk-quick-row { grid-template-columns: 1fr }`
 *       steht nach `.dk-quick-row {` (repeat(3, 1fr)) UND nach dem
 *       `@media (max-width: 1100px)`-Block, der es auf repeat(2, 1fr) zieht.
 *       Bedingung seit DEV-B6: grober Zeiger + 720 px (bzw. flaches
 *       Querformat) statt der nackten 720 px.
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

    // ---- K1/K2: Handy-Gerüst (OP-HANDY-10 + 720-px-Layout) -----------------
    // DEV-B6 (Review-Nacharbeit 10.11.): Das Gerüst steht NICHT mehr als
    // `@media`-Block, sondern als Klasse `:global(.dk-app--handy) …` (eine
    // Quelle mit dem Skript, `composables/handyLage.mjs`). Die Kaskaden-Zusage
    // dieses Tests gilt unverändert: die wirkende Regel muss HINTER den
    // Grundregeln stehen, die sie überschreibt — und das FLACHE QUERFORMAT
    // (OP-HANDY-10) muss darin enthalten sein. Der Test wurde angepasst, nicht
    // gelöscht (Regel 19).
    // Hinweis: index.css ist reines CSS — die Klasse steht dort ohne `:global`.
    const geruestKlassen = []
    const klassenRe = /([^{}@]*\.dk-app--handy[^{}]*)\{([^}]*)\}/g
    for (let m = klassenRe.exec(text); m; m = klassenRe.exec(text)) {
        geruestKlassen.push({ selektoren: m[1].trim(), selektoren: m[1].trim(), inhalt: m[2], start: anker + m.index })
    }
    // `.dk-app` einspaltig
    // Die Hülle trägt die Klasse selbst: `.dk-app.dk-app--handy` (App.vue
    // setzt sie an `.dk-app` und an <body>; Leiste/Schublade liegen NEBEN der
    // Hülle, im Wegwerf-Stack gemessen).
    const k1 = geruestKlassen.find((r) => /\.dk-app(\.dk-app--handy)?\s*$/.test(r.selektoren.split(',')[0].trim())
        && /grid-template-columns:\s*1fr/.test(r.inhalt))
    assert.ok(k1, 'K1: Handy-Gerüst-Regel (`.dk-app` einspaltig an der Klasse) fehlt')
    assert.ok(k1.start > grundApp,
        `K1 (${name}): die Gerüst-Regel (${k1.start}) steht VOR der Grundregel .dk-app `
        + `(${grundApp}) — im Bündel gewinnt dann die Grundregel`)
    // Die Seitenleiste wird in derselben Lage abgeschaltet (eigene Regel).
    const seitenleiste = geruestKlassen.find((r) => /\.dk-sidebar\s*$/.test(r.selektoren.split(',')[0].trim())
        && /display:\s*none/.test(r.inhalt))
    assert.ok(seitenleiste, 'K1: Handy-Gerüst schaltet `.dk-sidebar` nicht ab')
    assert.ok(seitenleiste.start > grundSidebar,
        `K1 (${name}): die .dk-sidebar-Abschaltung (${seitenleiste.start}) steht VOR der Grundregel (${grundSidebar})`)
    // `.kronos-sidebar` ist seit OP-UI-11 die einklappbare Kalenderliste —
    // NICHT abschalten (gilt weiterhin für Gerüst-Regeln).
    // DEV-B6b (Review 10.11., Punkt 3): Die Liste als Handy-Overlay
    // (`.dk-app--handy .kronos-sidebar { position: fixed … }`) ist erlaubt; die
    // Zusage dieses Tests bleibt „kein `display: none` an der Liste".
    // Vorher prüfte er den Selektor pauschal und fiel um, sobald das
    // Overlay der Handy-Lage dazukam (Regel 19: Test angepasst, nichts gelöscht).
    assert.ok(!geruestKlassen.some((r) => /\.kronos-sidebar[^,]*$/.test(r.selektoren)
        && /display:\s*none/.test(r.inhalt)),
        'K1: die Kalenderliste (.kronos-sidebar) darf nicht abgeschaltet werden')
    // OP-HANDY-10: das flache Querformat gehört zur Handy-Lage. Belegt über
    // die EINE Quelle (Token + Zeichenkette), nicht über einen zweiten Block.
    const tokens = ohneKommentare(readFileSync(CSS_QUELLE.replace('index.css', 'tokens.css'), 'utf8'))
    assert.match(tokens, /--layout-mobil:[^;]*\(pointer: coarse\) and \(max-height: 480px\) and \(orientation: landscape\)/,
        'K1: das flache Querformat gehört zur Handy-Lage (Zeiger geprüft)')

    // K2: die einspaltige Quick-Reihe.
    // DEV-B6b (Review 10.11., Punkt 4): Die einspaltige Reihe ist ein
    // INHALTS-Umbruch und hängt an der BREITE (≤ 720 px), nicht an der
    // Handy-Lage — die Kaskaden-Zusage bleibt dieselbe: die wirkende Regel
    // steht HINTER der Grundregel und HINTER dem 1100-px-Block.
    const reihenBlaecke = []
    const reihenRe = /@media\s*\(max-width:\s*720px\)\s*\{/g
    for (let m = reihenRe.exec(text); m; m = reihenRe.exec(text)) {
        const b = blockAb(text, m.index)
        if (/\.dk-quick-row/.test(b.inhalt)) reihenBlaecke.push({ ...b, start: anker + m.index })
    }
    const k2 = reihenBlaecke.find((r) => /grid-template-columns:\s*1fr/.test(r.inhalt))
    assert.ok(k2, 'K2: Regel (max-width: 720px) mit .dk-quick-row { grid-template-columns: 1fr } fehlt '
        + '(Befund: .dk-quick-row war bei 390 px zweispaltig)')
    assert.ok(k2.start > grundQuick,
        `K2 (${name}): die .dk-quick-row-Regel (${k2.start}) steht VOR der Grundregel `
        + `.dk-quick-row (${grundQuick}) — sie gewinnt im Bündel`)
    assert.ok(k2.start > b1100.ende,
        `K2 (${name}): die .dk-quick-row-Regel (${k2.start}) steht VOR dem `
        + `@media (max-width: 1100px)-Block mit .dk-quick-row (${b1100.start}) — `
        + 'bei 390 px gewinnt sonst repeat(2, 1fr)')
    // Der Klasse-Block führt .dk-quick-row NICHT mehr (Punkt 4: Breite).
    assert.ok(!geruestKlassen.some((r) => /\.dk-quick-row/.test(r.selektoren)),
        'K2: .dk-quick-row ist ein Inhalts-Umbruch und gehört an die Breite, nicht an die Handy-Lage')

    // Tote Selektoren gehören nicht in den wirksamen Block.
    for (const r of geruestKlassen) {
        assert.doesNotMatch(r.inhalt, /\.dk-topbar-search/,
            'K2: .dk-topbar-search steht in keinem Template — toter Selektor')
        assert.doesNotMatch(r.selektoren, /\.kronos-header\s+\.sidebar-toggle-btn/,
            'K2: .kronos-header .sidebar-toggle-btn regelt KronosTopbar.vue scoped — toter Selektor hier')
    }

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
