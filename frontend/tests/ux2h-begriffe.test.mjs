/**
 * UX2h — Begriffe vereinheitlichen (Wächter mit Sperrliste).
 *
 * Manuel 2026-11-04 (Konzept-Entscheidungen) und Paket UX2h legen EINE
 * Knopf- und Menüsprache fest:
 *
 *   Anlegen · Löschen (dauerhaft) · Entfernen (aus etwas) ·
 *   Erneut versuchen · Schließen (ohne Änderung) · Abbrechen (Eingabe
 *   verwerfen) · Termin (nie Element/Event) · Prüfen (statt Moderation) ·
 *   Website-Baukasten (statt Primo in der Oberfläche)
 *
 * Dieser Test ist der WÄCHTER. Er liest die SICHTBAREN Texte:
 *
 *   - Frontend (`src/diakonos/**`, .vue/.js/.mjs/.mts): Textknoten,
 *     Lesetext-Attribute und Anzeige-Strings im Skript — dieselbe Lesart wie
 *     der Glossar-Wächter p3-1b. Kommentare, CSS, Code-Bezeichner und
 *     Kennungen bleiben draußen. `.test.mjs` sind keine Oberfläche.
 *   - Server-Seiten (`backend/src/diakronos_app/**`, .py): NUR die
 *     String-Literale, die HTML erzeugen (`<…>` im Literal) — Docstrings und
 *     Log-Meldungen sind keine Oberfläche.
 *
 * Ausnahmen sind EINZELN begründet (AUSNAHMEN unten) — keine pauschalen
 * Freibriefe je Datei. Gegengeprobe: die eingesetzte Probe MUSS die
 * gesperrten Wörter enthalten, sonst prüft der Test nichts.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, extname, resolve } from 'node:path'

import { sichtbarerText } from './p3-1b-glossar-waechter.test.mjs'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')

/** Repo-Wurzel suchen (im Image-Build liegt `backend/` nicht daneben). */
function findeRepo() {
    let dir = FRONTEND
    for (let i = 0; i < 4; i += 1) {
        if (existsSync(join(dir, 'backend', 'src', 'diakronos_app'))) return dir
        dir = dirname(dir)
    }
    return null
}

/**
 * Die server-seitigen HTML-Seiten — zwei Fundorte, damit derselbe Test im
 * Worktree UND im Image läuft (Muster UX1j, Dockerfile-Regel 13):
 *
 *   1. Worktree: `backend/src/diakronos_app/` neben `frontend/`.
 *   2. Image:    die Kopien, die der Frontend-Stage nach `/ux2h-backend/`
 *                legt (backend/Dockerfile, COPY-Zeilen mit Kommentar „UX2h“).
 *
 * Fehlt beides, prüft der Test den Server-Teil nicht — der Abschnitt ist dann
 * ausdrücklich übersprungen, nicht stillschweigend grün.
 */
const BILD_BACKEND = '/ux2h-backend/'

function serverDateien() {
    const repo = findeRepo()
    if (repo) return sammle(join(repo, 'backend', 'src', 'diakronos_app'), new Set(['.py']))
    return sammle(BILD_BACKEND, new Set(['.py']))
}

const OBERFLAECHEN_ENDUNGEN = new Set(['.vue', '.js', '.mjs', '.mts'])

function sammle(dir, endungen, gefunden = []) {
    if (!existsSync(dir)) return gefunden
    for (const eintrag of readdirSync(dir)) {
        const pfad = join(dir, eintrag)
        if (statSync(pfad).isDirectory()) sammle(pfad, endungen, gefunden)
        else if (endungen.has(extname(eintrag))) gefunden.push(pfad)
    }
    return gefunden
}

/**
 * Die Sperrliste: gesperrte Wendung → erlaubte Wendung + Grund.
 * Gesucht wird als WORT im Text; die Groß-/Kleinschreibung des ersten
 * Buchstabens entscheidet nicht („Erstellen“ = „erstellen“). Steht das Wort
 * in einem zusammengesetzten Wort („Terminmoderation“), gilt es ebenfalls.
 */
export const SPERRLISTE = [
    { weg: 'Erstellen', hin: 'Anlegen', grund: 'Konzept: EIN Wort für „etwas Neues erzeugen“.',
      nicht: ['wiederherstellen'] },
    { weg: 'Hinzufügen', hin: 'Anlegen', grund: 'Konzept: kein zweites Wort für „neu erzeugen“.' },
    { weg: '+ Neue', hin: 'Anlegen', grund: 'Konzept: Knopftexte sind Verben, kein „+“ vor Substantiven.' },
    { weg: 'Nochmal', hin: 'Erneut versuchen', grund: 'Konzept: EIN Wort für den zweiten Versuch.' },
    { weg: 'Erneut laden', hin: 'Erneut versuchen', grund: 'Konzept: EIN Wort für den zweiten Versuch (auch beim Laden).' },
    { weg: 'Liste aktualisieren', hin: 'Erneut versuchen', grund: 'Konzept: kein eigener Knopftext für denselben Vorgang.' },
    { weg: 'Moderation', hin: 'Prüfen / Zu prüfen', grund: 'Konzept: der Vorgang heißt „Prüfen“, die Ablage „Zu prüfen“.',
      nicht: ['moderationCount', 'zurModeration', 'moderation-btn', 'Terminmoderation'] },
    // „Element“ ist gesperrt, wo es ein Termin/Eintrag ist. Die DOM-Sprache
    // (createElement, documentElement), die Dev-Modus-Kennungen (data-dk-dev,
    // Dev-Element), XML-Parser-Namen (ElementTree) und Kennungsfelder
    // (element_name, element_id) sind Technik, keine Oberfläche — sie werden
    // über `nicht`/`naechstes` ausgeblendet. Wer Einträge meint, schreibt
    // „Eintrag“, wer Termine meint, „Termin“.
    { weg: 'Element', hin: 'Termin (Kalender) bzw. Eintrag (Planrahmen)',
      grund: 'Konzept: „Termin“ ist das Wort der Oberfläche, nie „Element“ oder „Event“.',
      nicht: ['parentElement', 'documentElement', 'activeElement', 'createElement', 'ElementTree',
        'Elemente', 'element_name', 'element_id', 'element_start', 'element_end',
        'element_calendar', 'data-dk-dev', 'elementUnterPunkt', 'Dev-Element',
        'Element-Ausschnitt', 'Elemente', 'Element sichtbar', 'element.png',
        'Element-Typ', 'type=Element', 'element, position', 'element ? markiere(element)',
        'renderer, element, aufraeumen'],
      naechstes: /^element/i },
    { weg: 'Primo', hin: 'Website-Baukasten', grund: 'Konzept: in der Oberfläche „Website-Baukasten“; die Technik-Erklärung darf Primo nennen.' },
]

/** Steht das Wort im Text? (jedes Vorkommen, Groß-/Kleinschreibung egal.) */
export function findet(text, weg, nicht = [], naechstes = null) {
    // Gesperrt ist JEDES Vorkommen — auch im zusammengesetzten Wort
    // („Terminmoderation“) und in Bindestrich-Verbindungen („Primo-Stack“).
    // `nicht` blendet Wörter aus, die das gesperrte Wort nur als TEIL einer
    // Kennung tragen (CSS-Klasse, Variable, Attributname) — vor der Suche
    // werden sie durch ein neutrales Zeichen ersetzt, nicht durch Leerraum
    // (sonst würde „Erstellen“ in „Wiederherstellen“ freigestellt).
    let pruef = text
    for (const wort of nicht) pruef = pruef.split(wort).join('#')
    // `naechstes`: Das Wort muss ALLEIN stehen. „Element“ ist gesperrt,
    // „Elementtyp“/„Elemente“ sind eigene Begriffe — wer sie meint, schreibt
    // sie aus („Art des Eintrags“).
    const gesucht = weg.toLowerCase()
    if (naechstes) {
        let von = 0
        for (;;) {
            const i = pruef.toLowerCase().indexOf(gesucht, von)
            if (i < 0) return false
            if (!naechstes.test(pruef.slice(i + weg.length))) return true
            von = i + 1
        }
    }
    return pruef.toLowerCase().includes(gesucht)
}

/** Enthält der Text die Wendung überhaupt (Gegenprobe der Probe)? */
function enthaelt(text, weg) {
    return new RegExp(weg.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(text)
}

/**
 * Ausnahmen — jede EINZELN begründet. `datei` ist der Pfad ab `frontend/`
 * bzw. ab der Repo-Wurzel (backend/…); geschützt ist nur die Wendung `weg`
 * (und, wenn `stelle` gesetzt ist, nur diese Fundstelle).
 *
 * Grundsatz: Die Sperre gilt für SICHTBARE Texte. Wo ein Wort nur Teil eines
 * Dateipfads, einer Kennung oder einer Erklärung über die Technik ist, steht
 * es hier mit Begründung — nicht als pauschaler Freibrief für die Datei.
 */
export const AUSNAHMEN = [
    {
        datei: 'src/diakonos/components/ui/begriffe.mjs',
        weg: 'Nochmal', stelle: 'früher: „Nochmal“',
        grund: 'Das Glossar nennt die ALTE Schreibweise als Erklärung („früher: Nochmal“) — '
            + 'Daten, kein Bedienknopf. Die Datei steht schon bei p3-1b auf der Ausnahmeliste.',
    },
    {
        datei: 'src/diakonos/components/ui/begriffe.mjs',
        weg: 'Moderation', stelle: 'früher: Moderation',
        grund: 'Glossar-Erklärung zu „Prüfen“ („früher: Moderation“).',
    },
    {
        datei: 'src/diakonos/components/ui/begriffe.mjs',
        weg: 'Primo', stelle: 'früher: Primo',
        grund: 'Glossar-Erklärung zu „Website-Baukasten“ („früher: Primo“).',
    },
    {
        datei: 'src/diakonos/composables/website.mjs',
        weg: 'Primo', stelle: 'PRIMO_URL',
        grund: 'Der Text nennt den ECHTEN Einstellungsnamen aus settings/.env '
            + '(PRIMO_URL, PRIMO_PUBLIC_URL, PRIMO_SUPERUSER_*) — den muss der Betrieb genau '
            + 'so eintragen; eine Umbenennung wäre sachlich falsch. Der sichtbare Satz davor '
            + 'erklärt ihn auf Deutsch („Die interne Adresse …“).',
    },
    {
        datei: 'src/diakonos/composables/website.mjs',
        weg: 'Primo', stelle: 'deploy/primo',
        grund: 'Echter Repository-Pfad (deploy/primo, deploy/primo/ANLEITUNG.md) — der Betrieb muss ihn genau so finden.',
    },
    {
        datei: 'src/diakonos/composables/website.mjs',
        weg: 'Primo', stelle: 'diakronos-primo',
        grund: 'Echter Compose-Projektname (docker compose -p diakronos-primo) — eine Umbenennung startet einen zweiten Stack.',
    },
    {
        datei: 'src/diakonos/composables/website.mjs',
        weg: 'Primo', stelle: '/api/primo/info',
        grund: 'Echter Prüf-Endpunkt des Stacks (backend primo.py, deploy/primo/ANLEITUNG.md) — der Befehl muss so funktionieren.',
    },
    {
        datei: 'src/diakonos/components/registrierung/RegLinkTeilen.vue',
        weg: 'Erstellen', stelle: 'liess sich nicht erstellen',
        grund: 'Fehlermeldung zum QR-BILD: ein Bild wird technisch erzeugt (erstellt), '
            + 'nicht als Datensatz „angelegt“. Kein Bedienknopf.',
    },
    {
        datei: 'src/diakonos/pages/einstellungen/Papierkorb.vue',
        weg: 'Erstellen', stelle: 'Wiederherstellen',
        grund: '„Wiederherstellen“ ist der Knopf des Papierkorbs (Eintrag zurückholen) und '
            + 'enthält „herstellen“, nicht die gesperrte Knopfsprache „Erstellen“. Das Wort '
            + 'steht hier als Teil eines ANDEREN Verbs, nicht als Aufforderung, etwas Neues '
            + 'zu erzeugen.',
    },
]

function ausgenommen(datei, weg, stelle) {
    return AUSNAHMEN.some((a) => a.datei === datei && a.weg === weg
        && (!a.stelle || String(stelle || '').includes(a.stelle)))
}

/**
 * Sichtbare Texte einer Python-Datei: nur String-Literale, die HTML
 * enthalten. Docstrings (Modul-/Funktionsbeschreibungen) und Log-Texte sind
 * keine Oberfläche und werden NICHT geprüft.
 */
function serverSeitenTexte(quelle) {
    const literale = []
    const re = /"""([\s\S]*?)"""|'''([\s\S]*?)'''|f"((?:[^"\\\n]|\\.)*)"|f'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'/g
    for (const m of quelle.matchAll(re)) {
        const docstring = m[1] ?? m[2]
        if (docstring !== undefined) continue // Docstring = Beschreibung, keine Oberfläche
        const wert = m[3] ?? m[4] ?? m[5] ?? m[6] ?? ''
        // Nur HTML-erzeugende Literale: eine Seite, ein Tag, ein Textknoten
        // im Markup. Reine Sätze (Fehlermeldungen an die API) sind keine
        // Server-Seite — sie erscheinen erst über die SPA, die oben geprüft wird.
        if (/<[a-zA-Z/!]/.test(wert)) literale.push(wert)
    }
    return literale.join(' ')
}

/** Sichtbare Texte einer Datei (Frontend oder Server-Seite). */
function texte(datei, endung, quelle) {
    if (endung === '.py') return serverSeitenTexte(quelle)
    return sichtbarerText(quelle, endung)
}

const repo = findeRepo()
const frontendDateien = sammle(SRC, OBERFLAECHEN_ENDUNGEN)
    .filter((p) => !p.endsWith('.test.mjs'))
const serverMitHtml = serverDateien()
    .filter((p) => /<[a-zA-Z/!]/.test(readFileSync(p, 'utf8')))

/** Alle Befunde der Sperrliste über eine Dateiliste. */
export function befunde(dateien, liesDatei, kurzPfad = (p) => p) {
    const treffer = []
    for (const pfad of dateien) {
        const endung = extname(pfad)
        const text = texte(pfad, endung, liesDatei(pfad))
        const datei = pfad.replace(/^.*\/src\/diakonos\//, 'src/diakonos/')
        for (const eintrag of SPERRLISTE) {
            if (!findet(text, eintrag.weg, eintrag.nicht, eintrag.naechstes)) continue
            const kurz = text.replace(/\s+/g, ' ')
            // Fundstelle an einem Vorkommen zeigen, das NICHT zu einer Kennung
            // gehört (sonst zeigt der Befund auf „moderationCount“).
            let i = -1
            let such = 0
            for (;;) {
                const k = text.toLowerCase().indexOf(eintrag.weg.toLowerCase(), such)
                if (k < 0) break
                const probe = text.slice(Math.max(0, k - 20), k + 40)
                if (!(eintrag.nicht || []).some((w) => probe.includes(w))) { i = k; break }
                such = k + 1
            }
            const ii = kurz.toLowerCase().indexOf(eintrag.weg.toLowerCase())
            const stelle = kurz.slice(Math.max(0, (ii >= 0 ? ii : 0) - 60), (ii >= 0 ? ii : 0) + 100).trim()
            if (ausgenommen(datei, eintrag.weg, stelle)) continue
            treffer.push(`„${eintrag.weg}“ → „${eintrag.hin}“ in ${kurzPfad(pfad)} — …${stelle}…`)
        }
    }
    return treffer
}

// ── 1. Gegenprobe: die eingesetzte Probe enthält wirklich alle Wörter ──────
const PROBE = `<template>
  <DkButton>Erstellen</DkButton>
  <DkButton>Hinzufügen</DkButton>
  <DkButton>+ Neue Gruppe</DkButton>
  <DkButton>Nochmal</DkButton>
  <DkButton>Erneut laden</DkButton>
  <DkButton>Liste aktualisieren</DkButton>
  <span>Zur Terminmoderation</span>
  <span>Primo v3.3.1</span>
  <span>Element auswählen</span>
  <div ref="erstelleListe" v-if="primoKonflikt">kein Text</div>
</template>`

test('UX2h C: der Wächter findet jede gesperrte Wendung in einer Probe', () => {
    const text = sichtbarerText(PROBE, '.vue')
    for (const eintrag of SPERRLISTE) {
        assert.ok(enthaelt(text, eintrag.weg), `Probe enthält „${eintrag.weg}“ nicht — Test prüft nichts`)
        assert.ok(findet(text, eintrag.weg), `Wächter findet „${eintrag.weg}“ nicht`)
    }
    // Zusammengesetztes Wort zählt mit („Terminmoderation“); Kleinschreibung
    // ebenfalls („erneut laden“).
    assert.ok(findet('Zur Terminmoderation', 'Moderation'), 'Kompositum wird nicht erkannt')
    assert.ok(findet('Bitte erneut laden', 'Erneut laden'), 'Wendung in Kleinschreibung fehlt')
    // Code ist kein Lesetext: ein Bezeichner in einem Attribut wird nicht als
    // sichtbarer Text gelesen (kein Textknoten, kein Lesetext-Attribut).
    const nurCode = '<template><div ref="erstelleListe" :class="primoKonflikt">kein Text</div></template>'
    const codeText = sichtbarerText(nurCode, '.vue')
    assert.ok(!enthaelt(codeText, 'Erstellen'), 'Bezeichner „erstelleListe“ gilt als Text')
    assert.ok(!enthaelt(codeText, 'Primo'), 'Bezeichner „primoKonflikt“ gilt als Text')
})

// ── 2. Die Oberfläche hält die Sperrliste ein ──────────────────────────────
test('UX2h: kein gesperrtes Wort im sichtbaren Text der Oberfläche', () => {
    const gefunden = befunde(frontendDateien, (p) => readFileSync(p, 'utf8'),
        (p) => p.replace(`${FRONTEND}/`, ''))
    assert.deepEqual(gefunden, [], 'Sperrliste verletzt:\n' + gefunden.join('\n'))
})

// ── 3. Die server-seitigen HTML-Seiten halten sie ein ──────────────────────
test('UX2h: kein gesperrtes Wort in den server-seitigen HTML-Seiten', (t) => {
    // Im Image-Build ohne `backend/` und ohne `/ux2h-backend/` gibt es keine
    // Server-Seite zu prüfen — der Abschnitt ist dann ausdrücklich
    // übersprungen (nicht stillschweigend bestanden).
    if (serverMitHtml.length === 0) {
        t.skip('keine server-seitige HTML-Seite im Zugriff (Wegwerf-Container ohne backend/)')
        return
    }
    const gefunden = befunde(serverMitHtml, (p) => readFileSync(p, 'utf8'),
        (p) => (repo ? relative(repo, p) : p.replace(BILD_BACKEND, 'backend/src/diakronos_app/')))
    assert.deepEqual(gefunden, [], 'Sperrliste verletzt (Server-Seiten):\n' + gefunden.join('\n'))
})

// ── 4. Die neuen Wörter stehen da, wo sie hingehören ──────────────────────
test('UX2h: „Zu prüfen“ und „Website-Baukasten“ sind die Wörter der Oberfläche', () => {
    const lies = (p) => readFileSync(join(SRC, p), 'utf8')
    assert.match(lies('menue.js'), /label:\s*'Zu prüfen'/,
        'Kalender-Reiter heißt nicht „Zu prüfen“')
    assert.match(lies('pages/Website.vue'), /Website-Baukasten/,
        'Website-Seite nennt den Baukasten nicht beim neuen Namen')
})

// ── 5. Ausnahmen sind begründet (keine stillen Freibriefe) ────────────────
test('UX2h: jede Ausnahme ist begründet und benennt eine Datei der Oberfläche', () => {
    const geprueft = [...frontendDateien, ...serverMitHtml]
    for (const a of AUSNAHMEN) {
        assert.ok(a.grund && a.grund.length > 20, `Ausnahme „${a.weg}“ ohne Begründung`)
        assert.ok(SPERRLISTE.some((s) => s.weg === a.weg), `Ausnahme „${a.weg}“ steht nicht in der Sperrliste`)
        assert.ok(geprueft.some((p) => p.replace(/^.*\/src\/diakonos\//, 'src/diakonos/') === a.datei),
            `Ausnahme verweist auf keine geprüfte Datei: ${a.datei}`)
    }
})

console.log('UX2h Begriffe: Sperrliste (Oberfläche + Server-Seiten) eingehalten: bestanden')
