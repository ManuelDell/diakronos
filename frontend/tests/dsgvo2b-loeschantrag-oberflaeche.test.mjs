/**
 * DSGVO-2b — Oberfläche „Meine Daten löschen lassen“ im eigenen Profil.
 *
 * Geprüft werden die Zusagen der Karte, die man ohne Browser prüfen kann:
 *
 *  1. Der Bereich erklärt VOR dem Antrag, was passiert: endgültig, nicht
 *     rückgängig, Name und Mail verschwinden, alte Pläne zeigen „Gelöschte
 *     Person“, vorher kommt eine Mail.
 *  2. Der Antrag geht nur mit ausdrücklicher Bestätigung im EIGENEN Dialog
 *     (Kontrollkästchen + abgetipptes Wort) — kein `confirm()`, kein `alert()`.
 *  3. Die vier Stände werden angezeigt: offen („Antrag gestellt am … — wartet
 *     auf Bearbeitung“ + „Antrag zurückziehen“), abgelehnt (Begründung +
 *     „Erneut beantragen“), zurückgezogen, ausgeführt (nur Nachweis).
 *  4. Gerufen werden ausschließlich die drei Selbstbedienungs-Endpunkte; ohne
 *     Ziel-ID (die Person kommt aus der Sitzung). Bestätigen/Ablehnen sind
 *     Verwaltungssachen und kommen hier nicht vor.
 *  5. Serverfehler werden verständlich angezeigt (strukturierte Meldungen).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  ANTRAG_STAND, BESTAETIGUNG_WORT, ERKLAERUNG, antragsStand, bestaetigungVollstaendig,
  darfBeantragen, darfZurueckziehen, datumDeutsch,
} from '../src/diakonos/composables/loeschantrag.mjs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const karte = lies('components/mitglieder/LoeschantragKarte.vue')
const api = lies('composables/useLoeschantrag.js')
const profil = lies('pages/Profile.vue')
/** Nur AUSFÜHRBARER Code: Kommentare dürfen alte Wege benennen (wie in
 *  `austritt-oberflaeche.test.mjs`), geprüft wird was läuft. */
function skript(vue) {
  const marker = '<script setup>'
  const start = vue.indexOf(marker)
  const teil = start === -1 ? vue : vue.slice(start + marker.length)
  return teil
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n').map((z) => z.replace(/\/\/.*$/, '')).join('\n')
}

// ── 1. Erklärung ────────────────────────────────────────────────────────────

test('DSGVO-2b · die Erklärung nennt Endgültigkeit, Name/Mail, „Gelöschte Person“ und die Mail', () => {
  const text = ERKLAERUNG.join(' ')
  assert.match(text, /endgültig/)
  assert.match(text, /nicht rückgängig/)
  assert.match(text, /E-Mail-Adresse/)
  assert.match(text, /Gelöschte Person/)
  assert.match(text, /E-Mail/)
  // Zwei bis drei Sätze — kein Roman, aber vollständig.
  assert.ok(ERKLAERUNG.length >= 2 && ERKLAERUNG.length <= 3, `${ERKLAERUNG.length} Sätze`)
  // Und die Karte zeigt genau diesen Text (keine zweite Wahrheit).
  assert.match(karte, /ERKLAERUNG/)
  assert.match(karte, /Meine Daten löschen lassen/)
})

// ── 2. Bestätigung im eigenen Dialog ────────────────────────────────────────

test('DSGVO-2b · Antrag nur mit Kontrollkästchen UND abgetipptem Wort', () => {
  assert.equal(BESTAETIGUNG_WORT, 'LÖSCHEN')
  assert.equal(bestaetigungVollstaendig({ kaestchen: false, wort: 'LÖSCHEN' }), false)
  assert.equal(bestaetigungVollstaendig({ kaestchen: true, wort: '' }), false)
  assert.equal(bestaetigungVollstaendig({ kaestchen: true, wort: 'BEANTRAGEN' }), false)
  assert.equal(bestaetigungVollstaendig({ kaestchen: true, wort: 'LÖSCHEN', laeuft: true }), false)
  assert.equal(bestaetigungVollstaendig({ kaestchen: true, wort: ' löschen ' }), true,
    'Kleinschreibung und Leerzeichen am Rand dürfen nicht scheitern lassen')
  // Der Knopf ist gesperrt, solange die Bestätigung fehlt.
  assert.match(karte, /:disabled="!bestaetigungVollstaendig\(\{ kaestchen: verstanden, wort, laeuft \}\)"/)
  assert.match(karte, /<DkCheckbox v-model="verstanden"/)
  assert.match(karte, /Ich habe verstanden/)
})

test('DSGVO-2b · kein confirm()/alert() — die Rückfrage ist ein Dialog', () => {
  for (const quelle of [skript(karte), skript(profil)]) {
    assert.ok(!/(?:window\.)?\bconfirm\(/.test(quelle), 'confirm() im Skript')
    assert.ok(!/\balert\(/.test(quelle), 'alert() im Skript')
  }
  assert.match(karte, /<DkDialog/)
  assert.match(karte, /:close-on-overlay="false"/)
  assert.match(karte, /emit\('beantragen'\)/)
})

// ── 3. Die Stände ───────────────────────────────────────────────────────────

test('DSGVO-2b · Stand wird in genau einen von fünf Fällen übersetzt', () => {
  assert.equal(antragsStand(null), ANTRAG_STAND.OHNE)
  assert.equal(antragsStand(undefined), ANTRAG_STAND.OHNE)
  assert.equal(antragsStand({ status: 'offen' }), ANTRAG_STAND.OFFEN)
  assert.equal(antragsStand({ status: ' OFFEN ' }), ANTRAG_STAND.OFFEN)
  assert.equal(antragsStand({ status: 'zurueckgezogen' }), ANTRAG_STAND.ZURUECKGEZOGEN)
  assert.equal(antragsStand({ status: 'abgelehnt' }), ANTRAG_STAND.ABGELEHNT)
  assert.equal(antragsStand({ status: 'ausgefuehrt' }), ANTRAG_STAND.AUSGEFUEHRT)
  // Unbekannt/leer: der Server entscheidet — die Oberfläche zeigt den Antragsweg.
  assert.equal(antragsStand({ status: '' }), ANTRAG_STAND.OHNE)
  assert.equal(antragsStand({ status: 'quatsch' }), ANTRAG_STAND.OHNE)
})

test('DSGVO-2b · Knöpfe hängen am Stand (beantragen / zurückziehen)', () => {
  assert.equal(darfBeantragen(null), true)
  assert.equal(darfBeantragen({ status: 'zurueckgezogen' }), true)
  assert.equal(darfBeantragen({ status: 'abgelehnt' }), true)
  assert.equal(darfBeantragen({ status: 'offen' }), false)
  assert.equal(darfBeantragen({ status: 'ausgefuehrt' }), false)
  assert.equal(darfZurueckziehen({ status: 'offen' }), true)
  assert.equal(darfZurueckziehen({ status: 'abgelehnt' }), false)
  assert.equal(darfZurueckziehen({ status: 'ausgefuehrt' }), false)
  assert.equal(darfZurueckziehen(null), false)
})

test('DSGVO-2b · offener Antrag zeigt Datum, Wartestatus und Zurückziehen', () => {
  assert.match(karte, /Antrag gestellt am \{\{ daten\.beantragt_am \}\} — wartet auf Bearbeitung/)
  assert.match(karte, /Antrag zurückziehen/)
  assert.match(karte, /@click="\$emit\('zurueckziehen'\)"/)
  // Abgelehnt: Begründung sichtbar + erneut beantragen (nicht „neu“).
  assert.match(karte, /Erneut beantragen/)
  assert.match(karte, /<strong>Begründung:<\/strong> \{\{ daten\.ablehnung_grund \}\}/)
  // Ausgeführt: nur Nachweis, kein Knopf.
  assert.match(karte, /Deine Löschung wurde am/)
  const ausgefuehrt = karte.slice(karte.indexOf('ANTRAG_STAND.AUSGEFUEHRT'))
  assert.ok(!/Löschung beantragen<\/DkButton>/.test(ausgefuehrt.split('</template>')[0].slice(0, 600)))
})

test('DSGVO-2b · leere Datumsfelder bleiben leer (kein „Invalid Date“)', () => {
  assert.equal(datumDeutsch('2026-10-22T01:11:31'), '22.10.2026')
  assert.equal(datumDeutsch('2026-10-22 01:11:31'), '22.10.2026')
  assert.equal(datumDeutsch('2026-10-22'), '22.10.2026')
  assert.equal(datumDeutsch(''), '')
  assert.equal(datumDeutsch(null), '')
  assert.equal(datumDeutsch('kein Datum'), '')
})

// ── 4. API-Grenze ───────────────────────────────────────────────────────────

test('DSGVO-2b · nur die drei Selbstbedienungs-Endpunkte, ohne Ziel-ID', () => {
  const aufrufe = [...api.matchAll(/apiCall\(`[^`]*\.(\w+)`/g)].map((m) => m[1])
  assert.deepEqual(aufrufe.sort(), ['loeschantrag_zurueckziehen', 'loeschung_beantragen', 'mein_loeschantrag'])
  assert.match(api, /const API = 'diakronos\.diakonos\.api\.datenschutz'/)
  assert.equal((api.match(/bestaetigt: true/g) || []).length, 2, 'stellen und zurückziehen bestätigen')
  // Nur ausführbarer Code: der Kommentarkopf NENNT die Verwaltungsendpunkte,
  // gerade um zu sagen, dass sie hier nicht vorkommen.
  const apiCode = skript(api)
  assert.doesNotMatch(apiCode, /mitglied_id|loeschung_bestaetigen|loeschantrag_ablehnen/)
  // Die Seite spricht die Endpunkte nicht selbst an.
  assert.doesNotMatch(skript(profil), /datenschutz\.(mein_loeschantrag|loeschung_beantragen|loeschantrag_zurueckziehen)/)
  assert.match(profil, /from '\.\.\/composables\/useLoeschantrag\.js'/)
})

test('DSGVO-2b · Fehler werden verständlich angezeigt (strukturierte Meldungen)', () => {
  assert.match(api, /serverFehlerText/)
  assert.match(api, /err\?\.status === 403/)
  // 417 vom Server (z. B. „Bitte den Löschantrag bestätigen.“) kommt durch.
  const quelle = skript(api)
    .replace(/^\s*import .*$/gm, '')
    .replace(/^export /gm, '')
    .concat('\nreturn antragFehlerText')
  const modul = new Function('serverFehlerText', quelle)(
    (err, fallback) => {
      const meldungen = Array.isArray(err?.meldungen) ? err.meldungen : []
      if (meldungen.length) {
        const teile = meldungen.map((m) => m?.meldung || m?.hinweis || '').filter(Boolean)
        if (teile.length) return teile.join(' ')
      }
      const text = String(err?.message || '').trim()
      if (!text || /^HTTP \d+$/.test(text)) return fallback
      return text
    },
  )
  assert.equal(modul({ status: 417, message: 'Bitte den Löschantrag bestätigen.' }),
    'Bitte den Löschantrag bestätigen.')
  assert.equal(modul({ status: 417, meldungen: [{ pfad: 'status', meldung: 'Antrag läuft bereits.' }] }),
    'Antrag läuft bereits.')
  assert.equal(modul({ status: 403, message: 'Forbidden' }),
    'Zu deinem Zugang ist keine Person hinterlegt. Bitte wende dich an die Gemeindeverwaltung.')
  assert.equal(modul({ status: 500, message: 'HTTP 500' }, 'Ersatzsatz'), 'Ersatzsatz')
})
