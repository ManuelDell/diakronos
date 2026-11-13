/**
 * P3-1: Begriffe, Anrede, Platzhalter (Glossar S15).
 *
 * Reproduziert zuvor:
 *  - OP-ADMIN-18 Gemischte Anrede (Sie/ihr/du) und „Anmeldung“ doppelt belegt.
 *  - OP-UI-14   Mehrdeutige Fachbegriffe ohne verbindliches Glossar.
 *  - OP-UI-24   Produktname wechselte „Diakonos“/„Diakronos“.
 *  - UXM-R14    Kopfzeile zeigte interne Komponentennamen.
 *  - UXD-R19    „Suchen ⌘K“ war totes Markup (Kopf- und Seitenleiste).
 *  - UXD-R20    Wiki-Artikel-Link führte zum Dashboard.
 *  - UXD-R21    Platzhalter-Kontakt (sekretariat@gemeinde.de) und erfundener
 *               „Gemeinde-Chat“.
 *  - UXD-R23    Gast-Schnellzugriffe führten ins Leere.
 *  - OP-ADMIN-16 „Passwort ändern ↗“ führte auf eine 404-Seite.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { BEGRIFFE, PRODUKTNAME, verboteneBegriffe } from '../src/diakonos/components/ui/begriffe.mjs'

const hier = dirname(fileURLToPath(import.meta.url))
const src = join(hier, '..', 'src', 'diakonos')
const lies = (p) => readFileSync(join(src, p), 'utf8')

test('OP-UI-14: Glossar deckt die strittigen Begriffe verbindlich ab', () => {
    for (const id of ['freigeben', 'anmeldung', 'planvorlage', 'uebersicht',
                      'eigenschaft', 'einteilen', 'auswahl', 'wartet_auf_freigabe']) {
        assert.ok(BEGRIFFE[id], `Begriff fehlt im Glossar: ${id}`)
        assert.ok(BEGRIFFE[id].wort && BEGRIFFE[id].bedeutet, `Wort/Erklärung fehlt: ${id}`)
    }
    // „Vorschlag erzeugen“ ist kein Knopftext mehr — es heißt „Automatisch einteilen“.
    assert.deepEqual(verboteneBegriffe('Vorschlag erzeugen'), [
        { begriff: 'einteilen', variante: 'Vorschlag erzeugen' },
    ])
    assert.deepEqual(verboteneBegriffe('Automatisch einteilen und freigeben'), [])
})

test('OP-UI-24: Produktname ist festgelegt und überall derselbe', () => {
    assert.equal(PRODUKTNAME, 'Diakronos')
    const sidebar = lies('components/AppSidebar.vue')
    assert.match(sidebar, /\{\{ PRODUKTNAME \}\}/, 'Seitenleiste nutzt nicht den festgelegten Namen')
    assert.doesNotMatch(sidebar, />Diakonos</, 'alte Schreibweise „Diakonos“ steht noch in der Seitenleiste')
})

test('UXM-R14: Kopfzeile zeigt Lesetexte statt interner Komponentennamen', () => {
    const topbar = lies('components/AppTopbar.vue')
    assert.match(topbar, /Registrierung:\s*\[/, 'Brotkrumen für „Registrierung“ fehlen (roher Komponentenname)')
    assert.doesNotMatch(topbar, /Anmeldung:\s*\[/,
        'die alte Seite „Anmeldung“ ist entfallen — ihr Brotkrumen-Eintrag darf nicht bleiben')
    assert.match(topbar, /\|\| \['Übersicht'\]/, 'Rückfall liefert keinen Lesetext')
})

test('UXD-R19: der tote „Suchen ⌘K“-Knopf ist in beiden Rahmen entfernt', () => {
    const sidebar = lies('components/AppSidebar.vue')
    const topbar = lies('components/AppTopbar.vue')
    for (const [name, text] of [['Seitenleiste', sidebar], ['Kopfzeile', topbar]]) {
        // Nur das Markup prüfen — Kommentare dürfen die Befund-ID nennen.
        //
        // UX3f: Die Kopfzeile trägt seit der Befehlspalette wieder ein
        // Suchfeld (`.dk-topbar-suche`) — diesmal MIT Ziel: der Klick öffnet
        // die Palette (Strg+K). Der Befund von UXD-R19 war nicht das Suchfeld
        // an sich, sondern ein Knopf OHNE jede Wirkung. Geprüft wird deshalb
        // weiter: kein <kbd> im Markup (das Kürzel ist Text, kein Bedienelement)
        // und nicht das alte, tote Markup.
        assert.doesNotMatch(text, /<kbd>/, `${name}: Tastenkürzel-Anzeige steht noch`)
        assert.doesNotMatch(text, /class="dk-sb-search|class="dk-topbar-search/, `${name}: Such-Markup steht noch`)
    }
    // Wenn die Kopfzeile ein Suchfeld hat, muss es die Palette öffnen.
    if (/class="dk-topbar-suche/.test(topbar)) {
        assert.match(topbar, /\$emit\('suche'\)/,
            'das Suchfeld der Kopfzeile meldet den Klick nicht (toter Knopf wie UXD-R19)')
    }
})

test('UXD-R20: „#/wiki/<kennung>“ ist eine echte Route und öffnet den Artikel', () => {
    const router = lies('router.js')
    // MT-7 (11.11.): Die Route öffnet seit dieser Karte die eigne Leseseite
    // `WikiArtikel` statt der Liste mit Artikel-Fenster. Die Zusage der Karte
    // UXD-R20 (teilbare Adresse öffnet den Artikel) gilt unverändert.
    assert.match(router, /\^#\\\/wiki\\\/\(\.\+\)\$[\s\S]{0,80}page: 'WikiArtikel'/, 'dynamische Wiki-Route fehlt')
    const wiki = lies('pages/WikiArtikel.vue')
    assert.match(wiki, /getRouteParam\('id', 'WikiArtikel'\)/, 'WikiArtikel liest die Kennung nicht aus der Adresse')
    assert.match(wiki, /#\\\/wiki\\\//, 'WikiArtikel kennt den Pfadteil der Adresse nicht (Rückfall beim Durchlaufen)')
})

test('UXD-R21: kein Platzhalter-Kontakt und kein erfundener Gemeinde-Chat', () => {
    const wiki = lies('pages/Wiki.vue')
    assert.doesNotMatch(wiki, /sekretariat@gemeinde\.de/, 'Platzhalter-Adresse steht noch im Wiki')
    assert.doesNotMatch(wiki, /Gemeinde-Chat/, 'erfundener „Gemeinde-Chat“ steht noch im Wiki')
    assert.match(wiki, /hilfeKontakt/, 'Kontakt kommt nicht aus den Einstellungen')
})

test('UXD-R23: Gast-Schnellzugriffe führen nicht ins Leere', () => {
    const widget = lies('components/widgets/QuickLinksWidget.vue')
    assert.match(widget, /istGast/, 'Gast-Fall fehlt im Widget')
    // Im Gast-Zweig darf weder „#/mitglieder“ noch „#/gruppen“ stehen.
    const gastZweig = widget.slice(widget.indexOf('if (istGast.value)'), widget.indexOf('if (isAdmin.value)'))
    assert.doesNotMatch(gastZweig, /#\/mitglieder/)
    assert.doesNotMatch(gastZweig, /#\/gruppen/)
    assert.match(gastZweig, /#\/kalender/)
    assert.match(gastZweig, /#\/profile/)
})

test('OP-ADMIN-16: kein Link auf die 404-Seite „/update-password“', () => {
    const profil = lies('pages/Profile.vue')
    assert.doesNotMatch(profil, /\/update-password/, 'toter Passwort-Link steht noch im Profil')
    assert.match(profil, /Gemeindeleitung/, 'Hinweis auf die Gemeindeleitung fehlt')
})

test('OP-ADMIN-18: keine Sie-Anrede in den Plan- und Kalenderfenstern', () => {
    for (const datei of ['components/kronos/KronosSeriesDialog.vue',
                         'components/lieder/LiedBearbeiten.vue']) {
        const text = lies(datei)
        assert.doesNotMatch(text, /Was möchten Sie tun\?/, `${datei}: Sie-Anrede steht noch`)
    }
})
