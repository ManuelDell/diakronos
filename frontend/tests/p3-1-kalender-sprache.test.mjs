/**
 * P3-1: Texte und Sprache im Kalender (Ursachen an der Quelle).
 *
 * Reproduziert zuvor:
 *  - OP-ADMIN-17 Die Kalenderwoche begann am Sonntag (kein firstDay).
 *  - OP-ADMIN-20 Die CalDAV-Hilfe versprach „euer normales Anmelde-Passwort“
 *               und trug einen Fremdnamen im Fuß.
 *  - UXK-R13     englische Bibliothekstexte „all-day“ / „+2 more“.
 *  - UXK-R14     Mobil überlagerte „W40“ die Tageszahl.
 *  - UXK-R16     Strg+F wurde abgefangen, öffnete aber nichts.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const hier = dirname(fileURLToPath(import.meta.url))
const src = join(hier, '..', 'src', 'diakonos')
const lies = (p) => readFileSync(join(src, p), 'utf8')

test('OP-ADMIN-17: Kalenderwoche beginnt am Montag (firstDay: 1)', () => {
    const kalender = lies('components/kronos/KronosCalendar.vue')
    assert.match(kalender, /firstDay:\s*1/, 'firstDay: 1 fehlt — die Woche beginnt weiter am Sonntag')
})

test('UXK-R13: all-day und +N more sind eingedeutscht', () => {
    const kalender = lies('components/kronos/KronosCalendar.vue')
    assert.match(kalender, /allDayContent:\s*\{\s*text:\s*'ganztägig'\s*\}/)
    assert.match(kalender, /moreLinkContent:\s*\(info\)\s*=>\s*`\+\$\{info\.num\} weitere`/)
})

test('UXK-R14: Wochennummern am Handy abgeschaltet', () => {
    const kalender = lies('components/kronos/KronosCalendar.vue')
    // P3-4b/Restpunkt 9: Nicht mehr per einmaliger Breitenmessung beim Aufbau
    // (die griff beim Drehen/Fenstergroesse nicht), sondern dauerhaft per CSS
    // unter 640 px ausgeblendet — dieselbe Absicht, nur wirksam.
    const css = lies('kronos.css')
    // Spezifitaet beachten: `.ec .ec-day-head span` setzt weiter oben
    // `display: inline-block !important` (gleiche Spezifitaet, spaeter im
    // Blatt) — ein `.ec .ec-week-number` bliebe wirkungslos („W4028“ am Handy).
    assert.match(css, /@media \(max-width: 640px\)\s*\{[^}]*\.ec \.ec-day-head > \.ec-week-number\s*\{\s*display:\s*none/,
      'Wochennummer ist am Handy nicht ausgeblendet')
    assert.match(kalender, /weekNumbers:\s*true/,
      'die Nummer muss gerendert werden, damit CSS sie aus- und einschalten kann')
    assert.doesNotMatch(kalender, /weekNumbers:\s*!istSchmal\(\)/,
      'die einmalige Breitenmessung ist wieder da')
})

test('UXK-R16: kein Strg+F-Handler mehr, Browsersuche bleibt frei', () => {
    const topbar = lies('components/kronos/KronosTopbar.vue')
    assert.doesNotMatch(topbar, /preventDefault\(\)[\s\S]{0,80}'searchOpen'/, 'Strg+F wird weiter abgefangen')
    assert.doesNotMatch(topbar, /onKeyDown/)
    const kalender = lies('pages/Kalender.vue')
    assert.doesNotMatch(kalender, /searchOpen/, 'toter Zustand searchOpen steht noch in Kalender.vue')
})

test('OP-ADMIN-20: CalDAV-Hilfe nennt Authentik-Sonderfall, kein Fremdname im Fuß', () => {
    const sidebar = lies('components/kronos/KronosSidebar.vue')
    assert.match(sidebar, /diakronos-help-note/, 'Hinweis zu Authentik-Konten fehlt')
    assert.match(sidebar, /Authentik/i)
    assert.doesNotMatch(sidebar, /Muster Dienste/, 'Fremdname im Fuß steht noch in der Hilfe')
})

test('OP-ADMIN-18: Kalender-Hilfe duzt durchgehend', () => {
    const sidebar = lies('components/kronos/KronosSidebar.vue')
    for (const sie of ['Ihr könnt', 'euer normales', 'eure Anmelde', 'Öffnet <strong>', 'Tippt auf', 'Tragt ', 'Wählt ']) {
        assert.equal(sidebar.includes(sie), false, `Sie/Ihr-Form steht noch in der Kalenderhilfe: ${sie}`)
    }
})
