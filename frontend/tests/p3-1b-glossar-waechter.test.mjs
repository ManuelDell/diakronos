/**
 * P3-1b (W1) / P3-1c (C): Der Glossar-Wächter wendet die verbotenen Begriffe
 * WIRKLICH an — case-insensitiv, an allen sichtbaren Stellen.
 *
 * Nachtprüfung P3-1: `begriffe.mjs` nannte die verbotenen Wörter, aber nichts
 * prüfte sie gegen die Oberfläche — sichtbar standen weiter „Vorschlag
 * erzeugen“, „Alle festlegen“, „Festlegen“, „Dashboard“ und „Genehmigt“ da.
 *
 * Opus-Review P3-1b (W1 TEILWEISE / klein 1): Der Wächter reichte nicht.
 * Er lief nur über `.vue` (kein `.js`/`.mjs`), prüfte nur das Template ohne
 * Attributwerte und ohne `<script>`, und verglich case-sensitiv. Dadurch
 * rutschte „Freischalten“ in WartendeKontenKarte.vue durch, während
 * Anmeldung.vue „Zulassen“ sagte. Hier ist der Wächter vollständig:
 *
 *   - alle Oberflächendateien: `.vue`, `.js`, `.mjs`, `.mts`,
 *   - Template-markup INKLUSIVE Attributwerte (`title`/`placeholder`/
 *     `aria-label`/`label=…` — dort steht Lesetext), aber ohne Kommentare,
 *   - `<script>`-Blöcke: sichtbare String-Literale (Toasts, Labels, title/
 *     placeholder-Zuweisungen), Kommentare und Code-Bezeichner bleiben weg,
 *   - Vergleich CASE-INSENSITIV.
 *
 * Ausgenommen sind weiterhin:
 *   - Kommentare (dürfen die Befund-ID und den Altbegriff nennen),
 *   - `begriffe.mjs` selbst (dort stehen die Wörter als Daten),
 *   - der interne Kern (nicht Teil dieser Karte).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, extname } from 'node:path'

import { BEGRIFFE } from '../src/diakonos/components/ui/begriffe.mjs'

const hier = dirname(fileURLToPath(import.meta.url))
const SRC = join(hier, '..', 'src', 'diakonos')

const OBERFLAECHEN_ENDUNGEN = new Set(['.vue', '.js', '.mjs', '.mts'])

/** Alle Oberflächendateien unter `src/diakonos` (rekursiv). */
function oberflaechenDateien(dir = SRC, gefunden = []) {
    for (const eintrag of readdirSync(dir)) {
        const pfad = join(dir, eintrag)
        if (statSync(pfad).isDirectory()) oberflaechenDateien(pfad, gefunden)
        else if (OBERFLAECHEN_ENDUNGEN.has(extname(eintrag))) gefunden.push(pfad)
    }
    return gefunden.filter((p) => !p.endsWith('components/ui/begriffe.mjs'))
}

/** Kommentare aus einem JS-Teil entfernen (Zeilen- und Block-Kommentare). */
function ohneJsKommentare(text) {
    text = text.replace(/\/\*[\s\S]*?\*\//g, ' ')
    return text.split('\n').map((zeile) => {
        const i = zeile.indexOf('//')
        if (i < 0) return zeile
        const links = zeile.slice(0, i)
        // Steht links eine ungerade Zahl Anführungszeichen, ist // Textinhalt.
        if ((links.match(/["'`]/g) || []).length % 2 === 1) return zeile
        return links
    }).join('\n')
}

/**
 * Die String-Literale eines JS-Teils (Inhalt von '…', "…", `…`).
 * `mitPos` liefert zusätzlich die Zeile (für Kontext-Regeln wie `console.*`).
 */
function stringLiterale(text, mitPos = false) {
    const treffer = [...text.matchAll(/'([^']*)'|"([^"]*)"|`([^`]*)`/g)]
    const werte = treffer.map((m) => m[1] ?? m[2] ?? m[3] ?? '')
    if (!mitPos) return werte.join(' ')
    return treffer.map((m) => ({
        wert: m[1] ?? m[2] ?? m[3] ?? '',
        zeile: text.slice(0, m.index).split('\n').pop() + text.slice(m.index).split('\n')[0],
    }))
}

/**
 * Aus einem `<script>`-Block NUR die Lesetexte: Toasts, Labels und
 * Zuweisungen wie `label: 'Übersicht'`/`title: '…'`.
 *
 * Code bleibt draußen (Opus-Review P3-1b, W1): Bezeichner, API-Endpunkte
 * (`'plantyp_versionen_liste'`), Schema-Kennungen (`'diakronos/plantyp@1'`),
 * Import-Pfade, Store-Namen und `console.*`-Präfixe sind KEIN sichtbarer
 * Text — ein pauschaler String-Grep meldete sie fälschlich. Geprüft wird
 * deshalb nur, was eine Wendung ist (enthält ein Leerzeichen) oder der Wert
 * einer Beschriftungs-Eigenschaft (`label|labelText|title|titel|placeholder|
 * ariaLabel|aria-label|meldung|hinweis|nachricht|beschriftung`) — genau die
 * Stellen, an denen Oberflächentext im Skript steht.
 */
const BESCHRIFTUNGS_EIGENSCHAFT = '(label|labelText|titel|title|placeholder|ariaLabel|aria-label|meldung|hinweis|nachricht|beschriftung)'
/**
 * P3-1d (K1): Einzelwort-Toasts (`showToast('Freischalten')`) wurden nicht
 * gesehen, weil nur Literale MIT Leerzeichen als Lesetext zählten. Ein Literal
 * ist auch dann Lesetext, wenn es Argument einer Anzeige-Funktion ist:
 * `showToast(…)`, `toast(…)`, `bestaetigen({… aktion: …})` stehen immer im
 * sichtbaren Text. Bezeichner, API-Kennungen und Pfade bleiben draußen (sie
 * stehen in `apiCall(…)`, `import`, `console.*`).
 */
const ANZEIGE_FUNKTION = /(?:\b(?:showToast|toast|zeigeToast|zeigeMeldung|warnen)\s*\(|\b(?:aktion|abbrechen|beschriftung|label|labelText|titel|title|placeholder|ariaLabel)\s*:\s*)['"`]([^'"`]*)['"`]/g
function skriptLesetexte(js) {
    const sauber = ohneJsKommentare(js)
    const lesetext = []
    // 1) Beschriftungs-Eigenschaft: `label: '…'` / `title: '…'` (auch `?`/`=`
    //    und doppelte Anführungszeichen). `name` gehört NICHT dazu — `name:`
    //    trägt in Code (`group.name`, `field.name`) Kennungen, keinen Lesetext
    //    (Review: ModerationBoard `group: { name: 'festlegen' }`).
    const eigenschaft = new RegExp(`\\b${BESCHRIFTUNGS_EIGENSCHAFT}\\s*[:=]\\s*['"\`]([^'"\`]*)['"\`]`, 'g')
    for (const m of sauber.matchAll(eigenschaft)) lesetext.push(m[m.length - 1])
    // 2) Wendungen (Leerzeichen im Literal) — Toasts, Sätze, Aufrufe.
    for (const { wert, zeile } of stringLiterale(sauber, true)) {
        if (!wert.includes(' ')) continue
        // console.* ist Entwicklerausgabe, kein Lesetext.
        if (/\bconsole\s*\./.test(zeile)) continue
        lesetext.push(wert)
    }
    // 3) K1: Einwort-Lesetexte an Anzeige-Funktionen und Beschriftungsfeldern.
    for (const m of ohneJsKommentare(js).matchAll(ANZEIGE_FUNKTION)) {
        if (m[1]) lesetext.push(m[1])
    }
    return [...new Set(lesetext)].join(' ')
}

/**
 * Attribute, deren Wert KEIN Lesetext ist, auch wenn er wie ein Wort aussieht:
 * Bezeichner (`ref`, `id`, `key`, `class`, `style`, `name`, `type` …) und
 * Direktiven (`v-if`, `v-for`, `v-model`, `@click`, `:key`).
 */
const KEIN_LESETEXT_ATTRIBUT = new Set([
    'ref', 'id', 'key', 'class', 'style', 'name', 'type', 'value', 'for',
    'v-if', 'v-else', 'v-else-if', 'v-for', 'v-model', 'v-show', 'v-slot',
    'v-html', 'v-text', 'is', 'slot', 'to', 'href', 'src', 'role', 'tabindex',
])

/** Ist der Attributname ein gebundener Ausdruck (`:x`, `v-bind:x`, `@x`)? */
function istAusdruck(name) {
    return name.startsWith(':') || name.startsWith('v-bind:') || name.startsWith('@')
        || name.startsWith('#')
}

/** Attribute, deren gebundener Ausdruck (auch einzelne Wörter) Lesetext ist. */
const TEXT_ATTRIBUT = new Set(['title', 'titel', 'placeholder', 'aria-label', 'ariaLabel', 'label'])

/**
 * Lesetext aus den Attributen EINES Tags.
 *
 * Literale Attribute zählen nur, wenn ihr Wert wie Lesetext aussieht (enthält
 * ein Leerzeichen: `title="Konto wieder zulassen?"`). Einzelwort-Attribute
 * (`ref="sortFestlegen"`, `column="festlegen"`) sind Code und bleiben draußen.
 * Gebundene Attribute (`:title="…"`) tragen nur dann Text, wenn ihr Ausdruck
 * String-Literale enthält; ein einzelnes Wort zählt nur bei einem echten
 * Text-Attribut (`:aria-label="'Festlegen'"`) — `@click="f('festlegen')"`
 * dagegen ist ein Aufruf mit Kennung und bleibt draußen.
 */
function tagLesetext(tag) {
    const teile = []
    const re = /([:@a-zA-Z_][\w:.\-]*)\s*=\s*"([^"]*)"|([:@a-zA-Z_][\w:.\-]*)\s*=\s*'([^']*)'/g
    for (const m of tag.matchAll(re)) {
        const name = m[1] ?? m[3]
        const wert = m[2] ?? m[4] ?? ''
        if (!name || KEIN_LESETEXT_ATTRIBUT.has(name)) continue
        if (istAusdruck(name)) {
            const basis = name.replace(/^(:|v-bind:|@|#)/, '')
            if (TEXT_ATTRIBUT.has(basis)) teile.push(stringLiterale(wert))
            else {
                // Nur echte Wendungen (mit Leerzeichen), keine Kennungen.
                teile.push([...wert.matchAll(/'([^']*)'|"([^"]*)"|`([^`]*)`/g)]
                    .map((x) => x[1] ?? x[2] ?? x[3] ?? '').filter((s) => s.includes(' ')).join(' '))
            }
        } else if (wert.includes(' ')) teile.push(wert)
    }
    return teile.join(' ')
}

/**
 * Sichtbarer Text einer Oberflächendatei.
 *
 * `.vue`: Lesetext des `<template>` (Textknoten, sichtbare Attributwerte,
 * String-Literale aus `{{ … }}` und gebundenen Attributen) PLUS die
 * Lesetexte des `<script>`-Teils (Toasts, Labels). Kommentare, CSS und
 * Code-Bezeichner bleiben draußen.
 * `.js`/`.mjs`/`.mts`: nur die Lesetexte des Skripts (siehe
 * `skriptLesetexte`) — kein roher String-Grep.
 */
export function sichtbarerText(quelle, endung) {
    if (endung === '.vue') {
        const teile = []
        const tmpl = quelle.match(/<template[\s\S]*?<\/template>/g) || []
        for (const block of tmpl) {
            let text = block.replace(/<!--[\s\S]*?-->/g, ' ')
            // {{ … }} -> nur die String-Literale des Ausdrucks.
            text = text.replace(/\{\{([\s\S]*?)\}\}/g,
                (_t, ausdruck) => ' ' + stringLiterale(ausdruck) + ' ')
            // Tags: nur Lesetext-Attribute behalten; Tag selbst weg.
            text = text.replace(/<[^>]+>/g, (tag) => ' ' + tagLesetext(tag) + ' ')
            teile.push(text)
        }
        const skripte = quelle.match(/<script[\s\S]*?<\/script>/g) || []
        for (const block of skripte) {
            teile.push(skriptLesetexte(block.replace(/<\/?script[^>]*>/g, ' ')))
        }
        return teile.join(' ')
    }
    return skriptLesetexte(quelle)
}

/**
 * Erlaubte Wendungen: Stellen, an denen ein verbotenes Wort in einer ANDEREN,
 * im Glossar ausdrücklich zugelassenen Bedeutung steht. Jede Wendung nennt das
 * Wort, die Wendung und den Glossar-Begriff, der sie deckt — keine pauschalen
 * Freibriefe.
 */
const ERLAUBTE_WENDUNGEN = [
    {
        variante: 'Festlegen',
        wendung: /festgelegt/i,
        begriff: 'festgelegt',
        grund: 'Kleingeschrieben „festgelegt“ ist der Pin-Fachbegriff '
             + '(„von Hand festgelegt“) und der Server-Statuswert im Vergleich; '
             + 'verboten ist die Ablage/Knopf-Beschriftung „Festlegen“.',
    },
    {
        variante: 'freischalten',
        wendung: /freischaltung/i,
        begriff: 'freigeben',
        grund: '„Freischaltung“ als Substantiv (der Vorgang des Zulassens) ist '
             + 'keine Knopf-/Ablage-Beschriftung; verboten ist das Verb '
             + '„freischalten“/„Freischalten“ auf sichtbaren Bedienelementen.',
    },
]

/** Wörter, die ein verbotener Begriff ist — mit Ausnahme der Ausnahmen. */
const VERBOTEN = Object.entries(BEGRIFFE).flatMap(([id, def]) =>
    def.verboten.map((variante) => ({ begriff: id, variante })))

/**
 * Steht der Begriff im Text nur in erlaubten Wendungen? Dann zählt er nicht.
 * Geprüft wird zeilenweise: eine Zeile, die ausschließlich die erlaubte
 * Wendung trägt, ist in Ordnung; eine zweite Zeile ohne sie bleibt ein Befund.
 */
function nurErlaubteWendung(text, variante) {
    const ausnahmen = ERLAUBTE_WENDUNGEN.filter(
        (e) => e.variante.toLowerCase() === variante.toLowerCase())
    if (!ausnahmen.length) return false
    const klein = variante.toLowerCase()
    const zeilen = text.split('\n').filter((z) => z.toLowerCase().includes(klein))
    if (!zeilen.length) return false
    return zeilen.every((zeile) => ausnahmen.some((e) => e.wendung.test(zeile)))
}

test('W1: das Glossar kennt die strittigen Wörter überhaupt', () => {
    const varianteAlle = new Set(VERBOTEN.map((v) => v.variante))
    for (const wort of ['Vorschlag erzeugen', 'Festlegen', 'Dashboard', 'Genehmigen', 'freischalten']) {
        assert.ok(varianteAlle.has(wort), `Glossar kennt „${wort}“ nicht`)
    }
})

test('W1: kein sichtbarer Text (auch Attribute und Skript-Strings) verwendet einen verbotenen Begriff', () => {
    const befunde = []
    for (const pfad of oberflaechenDateien()) {
        const rel = relative(SRC, pfad)
        const endung = extname(pfad)
        const text = sichtbarerText(readFileSync(pfad, 'utf8'), endung)
        const klein = text.toLowerCase()
        for (const { begriff, variante } of VERBOTEN) {
            // CASE-INSENSITIV (Opus-Review P3-1b, klein 1): „Freischalten“
            // fiel durch, weil „freischalten“ klein geschrieben war.
            if (!klein.includes(variante.toLowerCase())) continue
            if (nurErlaubteWendung(text, variante)) continue
            befunde.push(`${rel}: „${variante}“ (Glossar ${begriff}) steht im sichtbaren Text`)
        }
    }
    assert.deepEqual(befunde, [], 'Glossar-Verstöße:\n' + befunde.join('\n'))
})

test('W1: jede erlaubte Wendung ist begründet und deckt sich mit dem Glossar', () => {
    for (const e of ERLAUBTE_WENDUNGEN) {
        assert.ok(e.grund && e.grund.length > 20, `Wendung „${e.variante}“ ohne Begründung`)
        assert.ok(BEGRIFFE[e.begriff], `Wendung „${e.variante}“ verweist auf kein Glossar: ${e.begriff}`)
        // Eine Wendung darf nur eine Variante freistellen, die im Glossar
        // ueberhaupt verboten ist — sonst waere sie wirkungslos.
        const verboten = new Set(VERBOTEN.filter(
            (v) => v.variante.toLowerCase() === e.variante.toLowerCase()).map((v) => v.variante))
        assert.ok([...verboten].some((v) => v.toLowerCase() === e.variante.toLowerCase()),
            `Wendung „${e.variante}“ stellt nichts frei`)
    }
})

test('C: der Wächter sieht Attribute und Skript-Strings wirklich', () => {
    // Gegenprobe (Review klein 1): der Wächter muss sichtbaren Text aus
    // (a) Textknoten, (b) literalen Attributen mit Lesetext, (c) gebundenen
    // Attributen (nur deren String-Literale) und (d) Skript-Strings sehen —
    // und Code (Bezeichner/API/ref) NICHT als Text zählen.
    const probeVue = `<template>
      <button title="Vorschlag erzeugen" :aria-label="aktiv ? 'Festlegen' : 'Genehmigen'">
        Dashboard
      </button>
      <div ref="sortFestlegen" class="pr-ed-tagfilter" v-if="inFestlegen">ok</div>
    </template>
    <script setup>
    showToast('Alle festlegen')
    const label = 'Plantyp speichern'
    apiCall('plan_generieren')
    console.warn('[DashboardConfig] Laden fehlgeschlagen:', e)
    </script>`
    const text = sichtbarerText(probeVue, '.vue')
    for (const wort of ['Vorschlag erzeugen', 'Festlegen', 'Genehmigen', 'Dashboard',
        'Alle festlegen', 'Plantyp speichern']) {
        assert.ok(text.includes(wort), `Wächter sieht „${wort}“ nicht (Template/Lesetext)`)
    }
    // Code darf NICHT als Lesetext gelten.
    for (const code of ['sortFestlegen', 'inFestlegen', 'plan_generieren',
        'dashboardConfig', 'pr-ed-tagfilter']) {
        assert.ok(!text.includes(code), `Wächter zählt Code „${code}“ als Lesetext`)
    }
})

test('C: der Wächter vergleicht case-insensitiv', () => {
    const probe = '<template><button>FREISCHALTEN</button></template>'
    const text = sichtbarerText(probe, '.vue')
    assert.ok(VERBOTEN.some((v) => v.variante.toLowerCase() === 'freischalten'))
    assert.ok(text.toLowerCase().includes('freischalten'),
        'Wächter findet „FREISCHALTEN“ nicht case-insensitiv')
})

test('W1: die verbotenen Begriffe sind nicht nur dokumentiert, sondern ersetzt', () => {
    const lies = (p) => readFileSync(join(SRC, p), 'utf8')
    const text = (p) => sichtbarerText(lies(p), extname(p))
    // OP-UI-14 / OP-ADMIN-18: die vier sichtbaren Stellen der Nachtprüfung.
    for (const [datei, alt, neu] of [
        ['pages/planrahmen/Plan.vue', 'Vorschlag erzeugen', 'Automatisch einteilen'],
        ['components/planrahmen/PrErststart.vue', 'Vorschlag erzeugen', 'Automatisch einteilen'],
        ['pages/Moderation.vue', 'Alle festlegen', 'Alle freigeben'],
        ['components/kronos/ModerationBoard.vue', 'Festlegen', 'Freigeben'],
    ]) {
        assert.doesNotMatch(text(datei), new RegExp(alt), `${datei}: „${alt}“ steht noch`)
        assert.match(text(datei), new RegExp(neu), `${datei}: „${neu}“ fehlt`)
    }
    // Registrierung: das Status-Label steht im <script>, nicht im Template.
    const registrierung = lies('pages/Registrierung.vue')
    assert.doesNotMatch(registrierung, /label: 'Genehmigt'/,
        'Registrierung.vue: Status „Genehmigt“ steht noch')
    assert.match(registrierung, /label: 'Aufgenommen'/, 'Registrierung.vue: „Aufgenommen“ fehlt')
    for (const datei of ['App.vue', 'pages/NichtGefunden.vue', 'pages/Home.vue']) {
        assert.doesNotMatch(text(datei), /Dashboard/, `${datei}: „Dashboard“ steht noch`)
    }
})

test('C: WartendeKontenKarte lässt zu statt freischalten (Glossar freigeben)', () => {
    // Opus-Review P3-1b, klein 1: hier stand sichtbar „Freischalten“.
    const text = sichtbarerText(
        readFileSync(join(SRC, 'components/WartendeKontenKarte.vue'), 'utf8'), '.vue')
    assert.doesNotMatch(text, /Freischalten/i, 'WartendeKontenKarte.vue: „Freischalten“ steht noch')
    assert.match(text, /Zulassen/, 'WartendeKontenKarte.vue: „Zulassen“ fehlt')
})

test('OP-ADMIN-18: über der Moderationstafel steht ein Erklärsatz', () => {
    const moderation = readFileSync(join(SRC, 'pages/Moderation.vue'), 'utf8')
    assert.match(moderation, /data-test="moderation-erklaerung"/,
        'Erklärsatz über der Moderationstafel fehlt')
    assert.match(moderation, /Freigeben/, 'Erklärsatz nennt die Ablage „Freigeben“ nicht')
})
