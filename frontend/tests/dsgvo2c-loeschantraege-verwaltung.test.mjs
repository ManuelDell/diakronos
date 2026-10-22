/**
 * DSGVO-2c — Oberfläche der Verwaltung: Liste „Löschanträge“ mit Freigeben und
 * Ablehnen.
 *
 * Geprüft werden die Zusagen der Karte, die man ohne Browser prüfen kann:
 *
 *  1. Die Liste steht in der Mitgliederverwaltung, hat eine eigene Adresse und
 *     einen Reiter; ohne Anmeldung als Administrator kommt niemand dorthin.
 *  2. Je Antrag stehen Name, Datum und Stand. Ein Zähler nennt die offenen
 *     Anträge (Reiter, Übersicht, „Zu erledigen“).
 *  3. „Löschung freigeben“ verlangt das ABTIPPEN des vollständigen Namens und
 *     sagt deutlich „endgültig, nicht rückgängig“ — kein `confirm()`.
 *  4. „Ablehnen“ braucht eine Begründung (Pflicht), längstens `GRUND_MAX`.
 *  5. Erfolgsmeldung und Fehlertexte sind die der Karte; „Mail nicht
 *     eingerichtet“ nennt den Weg zur Mailversand-Seite.
 *  6. Gerufen werden ausschließlich die drei Verwaltungsendpunkte — aber nur
 *     mit Ziel-ID, mit `bestaetigt: true` und NIE ohne Begründung.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  ANTRAG_FILTER, ANTRAG_STATUS, BEGRUENDUNG_MAX, antragsStatusText, beantragtText,
  begruendungFehler, datumDeutsch, freigabeFehlerText, freigabeVollstaendig,
  istMailNichtEingerichtet, nameFuerAntrag,
} from '../src/diakonos/components/mitglieder/loeschantraege.mjs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const seite = lies('pages/mitglieder/Loeschantraege.vue')
const liste = lies('components/mitglieder/LoeschantraegeListe.vue')
const freigabe = lies('components/mitglieder/FreigabeDialog.vue')
const ablehnen = lies('components/mitglieder/AblehnenDialog.vue')
const api = lies('composables/useLoeschantraege.js')
const router = lies('router.js')
const menue = lies('menue.js')
const bereich = lies('pages/mitglieder/Bereich.vue')
const uebersicht = lies('pages/mitglieder/Uebersicht.vue')

/** Nur AUSFÜHRBARER Code: Kommentare dürfen Wege benennen, geprüft wird was läuft. */
function skript(vue) {
  const marker = '<script setup>'
  const start = vue.indexOf(marker)
  const teil = start === -1 ? vue : vue.slice(start + marker.length)
  return teil
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n').map((z) => z.replace(/\/\/.*$/, '')).join('\n')
}

/** Quelltext ohne Kommentare (für „es gibt kein X“). */
function ohneKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

// ── 1. Ort der Liste ────────────────────────────────────────────────────────

test('DSGVO-2c · eigene Adresse, Reiter und Admin-Guard', () => {
  assert.match(router, /'#\/mitglieder\/loeschantraege': 'MitgliederLoeschantraege'/)
  assert.match(router, /MitgliederLoeschantraege: \(\) => import\('\.\/pages\/mitglieder\/Bereich\.vue'\)/)
  // Direktaufruf ohne Administrator landet auf dem Dashboard.
  const guard = router.slice(router.indexOf('const ADMIN_ONLY_PAGES'))
  assert.match(guard.slice(0, guard.indexOf('])')), /'MitgliederLoeschantraege'/)
  // Reiter + Menü (Seitenleiste bleibt bei „Mitglieder“ markiert).
  assert.match(menue, /\{ id: 'loeschantraege', label: 'Löschanträge', href: '#\/mitglieder\/loeschantraege', seite: 'MitgliederLoeschantraege', rolle: 'admin' \}/)
  assert.match(menue, /'MitgliederDatenschutz', 'MitgliederLoeschantraege'/)
  // Der Mitglieder-Rahmen zeigt die Seite als Reiterinhalt.
  assert.match(bereich, /import\('\.\/Loeschantraege\.vue'\)/)
  assert.match(bereich, /case 'loeschantraege': return LOESCHANTRAEGE/)
})

test('DSGVO-2c · die Daten-Schutz-Seite führt auf die neue Arbeitsliste', () => {
  const datenschutz = lies('pages/mitglieder/Datenschutz.vue')
  assert.match(datenschutz, /href="#\/mitglieder\/loeschantraege"/)
  // Kein zweiter Freigabe-Weg über den alten Knopf. (Der Dialogtitel
  // „Löschantrag prüfen“ bleibt für den Alt-bestand `anonymisieren` stehen —
  // gesucht wird der Knopf, der früher direkt bestätigt hat.)
  assert.doesNotMatch(ohneKommentare(datenschutz), /@click="oeffnen\(a, true\)"/)
  assert.doesNotMatch(ohneKommentare(datenschutz), />Löschantrag prüfen</)
})

test('DSGVO-2c · Zähler bei offenen Anträgen (Liste, Übersicht, Aufgaben)', () => {
  assert.match(liste, /Anträge warten/)
  assert.match(liste, /Antrag wartet/)
  assert.match(uebersicht, /get_loeschantraege/)
  assert.match(uebersicht, /label: 'Löschanträge'/)
  assert.match(uebersicht, /auf Freigabe/)
})

// ── 2. Zeile je Antrag: Name, Datum, Stand ──────────────────────────────────

test('DSGVO-2c · Stand wird in deutsche Worte übersetzt', () => {
  assert.equal(antragsStatusText({ status: 'offen', beantragt_am: '2026-10-22T08:00:00' }).text, 'offen')
  assert.equal(antragsStatusText({ status: 'abgelehnt', abgelehnt_am: '2026-10-23' }).text, 'abgelehnt')
  assert.equal(antragsStatusText({ status: 'ausgefuehrt', anonymisiert_am: '2026-10-24' }).text, 'gelöscht')
  assert.equal(antragsStatusText({ status: 'zurueckgezogen' }).text, 'zurückgezogen')
  // Das Datum gehört zum Stand, nicht zum Antrag: abgelehnt am Tag der Ablehnung.
  assert.equal(antragsStatusText({ status: 'abgelehnt', beantragt_am: '2026-10-01', abgelehnt_am: '2026-10-09' }).am, '09.10.2026')
  // Bestandszeilen ohne Status: `erledigt_am` entscheidet (wie im Server).
  assert.equal(antragsStatusText({ erledigt_am: '2026-01-02' }).stand, 'ausgefuehrt')
  // Unbekannt wird nicht erfunden.
  assert.equal(antragsStatusText({ status: 'quatsch' }).stand, 'offen')
  assert.deepEqual(Object.keys(ANTRAG_STATUS).sort(),
    ['abgelehnt', 'ausgefuehrt', 'offen', 'zurueckgezogen'])
  assert.deepEqual(ANTRAG_FILTER.map(f => f.wert), ['offen', 'abgelehnt', 'zurueckgezogen', 'ausgefuehrt', 'alle'])
})

test('DSGVO-2c · „Beantragt am …“ steht in jeder Zeile', () => {
  assert.equal(beantragtText({ beantragt_am: '2026-10-22T08:00:00' }), 'Beantragt am 22.10.2026')
  assert.equal(beantragtText({}), 'Beantragt (Datum fehlt)')
  assert.equal(datumDeutsch('2026-10-22'), '22.10.2026')
  assert.equal(datumDeutsch(null), '')
  assert.match(liste, /beantragtText\(a\)/)
})

test('DSGVO-2c · Name, sonst „Gelöschte Person“ — nie eine Kennung', () => {
  assert.equal(nameFuerAntrag({ vorname: 'Anna', nachname: 'Beispiel' }), 'Anna Beispiel')
  assert.equal(nameFuerAntrag({ vorname: 'Anna', nachname: '' }), 'Anna')
  assert.equal(nameFuerAntrag({ mitglied: 'geloescht-3f9a1c' }), 'Gelöschte Person')
  assert.equal(nameFuerAntrag({ mitglied: 'D2a-anna' }), 'D2a-anna')
  assert.equal(nameFuerAntrag({}), 'Gelöschte Person')
  assert.match(liste, /nameFuerAntrag\(a\)/)
})

// ── 3. Freigeben: Name abtippen, endgültig ─────────────────────────────────

test('DSGVO-2c · Freigeben nur mit vollständig abgetipptem Namen', () => {
  assert.equal(freigabeVollstaendig({ name: 'Anna Beispiel', eingabe: 'Anna Beispiel' }), true)
  assert.equal(freigabeVollstaendig({ name: 'Anna Beispiel', eingabe: 'anna beispiel' }), true,
    'Groß-/Kleinschreibung darf nicht scheitern lassen')
  assert.equal(freigabeVollstaendig({ name: 'Anna Beispiel', eingabe: '  Anna   Beispiel ' }), true,
    'doppelte Leerzeichen am Rand dürfen nicht scheitern lassen')
  assert.equal(freigabeVollstaendig({ name: 'Anna Beispiel', eingabe: 'Anna' }), false)
  assert.equal(freigabeVollstaendig({ name: 'Anna Beispiel', eingabe: '' }), false)
  assert.equal(freigabeVollstaendig({ name: '', eingabe: '' }), false, 'ohne Namen keine Freigabe')
  assert.equal(freigabeVollstaendig({ name: 'Anna Beispiel', eingabe: 'Anna Beispiel', laeuft: true }), false)
  // Der Dialog hängt den Knopf daran UND verlangt den Namen im Text.
  assert.match(freigabe, /:disabled="!freigabeVollstaendig\(\{ name, eingabe, laeuft \}\) \|\| !mailEingerichtet"/)
  assert.match(freigabe, /vollständigen Namen eintippen/)
  assert.match(freigabe, /endgültig/)
  assert.match(freigabe, /nicht rückgängig/)
  assert.match(freigabe, /Löschung freigeben/)
})

test('DSGVO-2c · kein confirm()/alert() — die Rückfragen sind Dialoge', () => {
  for (const quelle of [skript(seite), skript(liste), skript(freigabe), skript(ablehnen)]) {
    assert.ok(!/(?:window\.)?\bconfirm\(/.test(quelle), 'confirm() im Skript')
    assert.ok(!/\balert\(/.test(quelle), 'alert() im Skript')
  }
  for (const dialog of [freigabe, ablehnen]) {
    assert.match(dialog, /<DkDialog/)
    assert.match(dialog, /:close-on-overlay="false"/)
  }
  assert.match(seite, /<FreigabeDialog/)
  assert.match(seite, /<AblehnenDialog/)
})

// ── 4. Ablehnen: Begründung ist Pflicht ────────────────────────────────────

test('DSGVO-2c · Ablehnen ohne Begründung wird nicht abgeschickt', () => {
  assert.match(begruendungFehler(''), /Begründung/)
  assert.match(begruendungFehler('   \n\t '), /Begründung/)
  assert.equal(begruendungFehler('Die Zustimmung des Vorstands fehlt.'), '')
  assert.equal(begruendungFehler('Absatz eins.\n\nAbsatz zwei\ttabulator'), '', 'Umbrüche und TAB sind erlaubt')
  assert.match(begruendungFehler('x'.repeat(BEGRUENDUNG_MAX + 1)), /zu lang/)
  assert.equal(begruendungFehler('x'.repeat(BEGRUENDUNG_MAX)), '')
  assert.match(begruendungFehler('Kaputt\u0000hier'), /unerlaubte Zeichen/)
  assert.equal(BEGRUENDUNG_MAX, 2000, 'derselbe Wert wie models/datenschutz.GRUND_MAX')
  // Der Dialog prüft vor dem Absenden und der Knopf ist Pflichtfeld-gebunden.
  assert.match(ablehnen, /begruendungFehler\(begruendung\.value\)/)
  assert.match(ablehnen, /if \(begruendungFehler\(begruendung\.value\)\) return/)
  assert.match(ablehnen, /label="Begründung"\s+required/)
  // Der Text der Person muss klar sein, warum die Begründung zählt.
  assert.match(ablehnen, /per E-Mail/)
})

// ── 5. Meldungen ────────────────────────────────────────────────────────────

test('DSGVO-2c · Erfolg meldet genau das, was passiert ist', () => {
  assert.match(seite, /showToast\('Mail versendet, Daten gelöscht\.', 'success'\)/)
  assert.match(seite, /showToast\('Mail versendet, Antrag abgelehnt\.', 'success'\)/)
})

test('DSGVO-2c · Fehler werden verständlich – Mail fehlt führt zur Mailversand-Seite', () => {
  const mailfehlt = { status: 417, message: 'Mailversand ist nicht eingerichtet — ohne ihn kann der Löschantrag nicht bearbeitet werden.' }
  assert.equal(istMailNichtEingerichtet(mailfehlt), true)
  const text = freigabeFehlerText(mailfehlt)
  assert.match(text, /Mailversand ist nicht eingerichtet/)
  assert.match(text, /Mailversand einrichten/)
  // Die Seite verlinkt die Mailversand-Seite in BEIDEN Dialogen.
  for (const dialog of [freigabe, ablehnen]) {
    assert.match(dialog, /href="#\/einstellungen\/mailversand"/)
    assert.match(dialog, /Mailversand einrichten/)
  }
  // Gescheiterter Versand: der Server sagt schon, dass nichts passiert ist.
  const versand = { status: 417, message: 'Der Mailserver hat die Nachricht abgelehnt. Es wurde NICHTS gelöscht — der Antrag bleibt offen, bitte erneut versuchen.' }
  assert.equal(freigabeFehlerText(versand), versand.message)
  // Andere 417-Meldungen bekommen den Zusatz, was NICHT passiert ist.
  assert.match(freigabeFehlerText({ status: 417, message: 'Kein offener Antrag.' }, 'Es wurde nichts gelöscht.'),
    /Kein offener Antrag\. Es wurde nichts gelöscht\./)
  // Rechte: der Satz nennt, an wen man sich wendet.
  assert.match(freigabeFehlerText({ status: 403, message: 'HTTP 403' }), /Recht/)
  assert.match(freigabeFehlerText({ status: 500, message: 'HTTP 500' }), /noch einmal versuchen/)
  assert.match(seite, /freigabeFehlerText/)
})

test('DSGVO-2c · ohne Mailversand sind Freigeben und Ablehnen gesperrt', () => {
  assert.match(freigabe, /!mailEingerichtet/)
  assert.match(ablehnen, /!mailEingerichtet/)
  assert.match(liste, /weder freigegeben noch abgelehnt/)
  assert.match(seite, /mailversandStand\(\)/)
  // Eine fehlende Auskunft sperrt nichts (der Server entscheidet ohnehin).
  assert.match(skript(api), /eingerichtet: antwort\?\.eingerichtet !== false/)
})

// ── 6. API-Grenze ───────────────────────────────────────────────────────────

test('DSGVO-2c · genau die drei Verwaltungsendpunkte, immer mit Ziel und Bestätigung', () => {
  assert.match(api, /const API = 'diakronos\.diakonos\.api\.datenschutz'/)
  const namen = [...new Set([...api.matchAll(/apiCall\(`\$\{API\}\.(\w+)`/g)].map(m => m[1]))].sort()
  assert.deepEqual(namen, ['get_loeschantraege', 'loeschantrag_ablehnen', 'loeschung_bestaetigen'])
  // Freigeben und Ablehnen: Ziel-ID + bestaetigt: true.
  assert.match(api, /loeschung_bestaetigen`, \{ mitglied_id, bestaetigt: true \}/)
  assert.match(api, /loeschantrag_ablehnen`, \{\s*mitglied_id,/)
  assert.match(api, /bestaetigt: true,\n\s*\}\)/)
  // Kein Freigeben/Ablehnen ohne Ziel.
  assert.equal((api.match(/if \(!mitglied_id\) throw/g) || []).length, 2)
  // Die Seite spricht die Endpunkte nicht selbst an.
  assert.doesNotMatch(skript(seite), /datenschutz\.(get_loeschantraege|loeschung_bestaetigen|loeschantrag_ablehnen)/)
  assert.match(seite, /from '\.\.\/\.\.\/composables\/useLoeschantraege\.js'/)
  // Der Selbstbedienungs-Weg (Profil) bleibt unberührt.
  assert.doesNotMatch(skript(api), /loeschung_beantragen|loeschantrag_zurueckziehen|mein_loeschantrag/)
})

test('DSGVO-2c · Ablehnen schickt die Begründung mit, Freigeben keine', () => {
  const ablehnenAufruf = api.slice(api.indexOf('export function antragAblehnen'), api.indexOf('export async function mailversandStand'))
  assert.match(ablehnenAufruf, /begruendung: String\(begruendung \?\? ''\)/)
  const freigabeAufruf = api.slice(api.indexOf('export function loeschungFreigeben'), api.indexOf('export function antragAblehnen'))
  assert.doesNotMatch(freigabeAufruf, /begruendung/)
  // Die Seite reicht die Begründung aus dem Dialog durch.
  assert.match(seite, /antragAblehnen\(ziel\.value\.mitglied, begruendung\)/)
})
