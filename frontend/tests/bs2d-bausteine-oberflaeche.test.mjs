/**
 * BS-2d — Oberfläche „Bausteine“: Statusanzeige-Logik und Anbindung.
 *
 * Der Test prüft die FACHLOGIK aus `src/shared/website-bausteine.mjs`
 * (Stand, Zustand, Zeilen, Meldungen) mit echten Serverantworten in der Form
 * von BS-2a — nicht die Optik (die belegen die Screenshots der Abnahme):
 *
 *   1. Rollen: nur die drei Website-Rollen sehen den Bereich.
 *   2. Stand: Zahlen, „veraltet“, nicht erreichbar, unbrauchbare Werte.
 *   3. Zustand: fünf Zustände mit Ton, Titel und der EINEN Knopfaktion —
 *      „aktuell“ hat KEINEN Knopf (kein toter Knopf).
 *   4. Zeilen: „mitgeliefert“ vs. „installiert“ vs. „ältere Fassung“,
 *      höchste Fassung gewinnt, nichts wird erfunden.
 *   5. Freigaben je Baustein (Feld-Positivliste, G1) und ihre Anzeige.
 *   6. Ergebnis-Meldung im Klartext.
 *   7. Anbindung: Status per GET, Einspielen NUR per POST (`apiCall`), die
 *      Kennungen stimmen mit dem Server überein.
 *   8. Bauteil: nur DkButton, genau EIN Primärknopf, keine festen Farben/
 *      Abstände, keine hartkodierte Bausteinliste, Anleitung vorhanden.
 *
 * Läuft im Docker-Build (`node --test`); die Datei liegt in `frontend/tests/`
 * und liest nur `frontend/**` (Regel 13).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  BAUSTEIN_ROLLEN,
  WERKZEUG,
  bausteinFreigaben,
  bausteineAnleitung,
  bausteineStand,
  bausteinZeilen,
  bausteineZustand,
  bausteinZeileStand,
  darfBausteineSehen,
  freigabenText,
  installationsMeldung,
} from '../src/shared/website-bausteine.mjs'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')

function lies(rel) {
  const abs = path.join(FRONTEND, rel)
  assert.ok(existsSync(abs), `Datei fehlt: ${rel}`)
  return readFileSync(abs, 'utf8')
}

/** Kommentare entfernen — Prüfungen gelten dem Code, nicht der Erklärung. */
function ohneKommentare(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

/** Antwort von `bausteine_status` mit zwei Bausteinen (Form BS-2a). */
function statusAntwort(teil = {}) {
  return {
    erreichbar: true,
    mitgeliefert_version: 2,
    installiert_version: 2,
    veraltet: false,
    revision: 'v2:abc',
    hinweis: '',
    bausteine: [
      { kennung: 'kontakt', name: 'diakronos/kontakt@v2', version: 2 },
      { kennung: 'termine-liste', name: 'diakronos/termine-liste@v2', version: 2 },
    ],
    ...teil,
  }
}

// ── 1. Rollen ──────────────────────────────────────────────────────────────

test('BS-2d: den Bereich sehen nur die drei Website-Rollen', () => {
  assert.deepEqual(BAUSTEIN_ROLLEN, ['System Manager', 'Administrator', 'Website-Moderator'])
  assert.equal(darfBausteineSehen({ rollen: ['Administrator'] }), true)
  assert.equal(darfBausteineSehen({ rollen: ['Website-Moderator'] }), true)
  assert.equal(darfBausteineSehen({ rollen: ['System Manager'] }), true)
  // Fail closed: ohne Rolle, mit fremder Rolle, mit Unsinn.
  assert.equal(darfBausteineSehen({ rollen: [] }), false)
  assert.equal(darfBausteineSehen({ rollen: ['Mitglied'] }), false)
  assert.equal(darfBausteineSehen({ rollen: null }), false)
  assert.equal(darfBausteineSehen(), false)
})

// ── 2. Stand ───────────────────────────────────────────────────────────────

test('BS-2d: der Stand rechnet aus den Serverzahlen, nicht aus dem Flag', () => {
  const stand = bausteineStand(statusAntwort({ veraltet: true }))
  assert.equal(stand.erreichbar, true)
  assert.equal(stand.mitgeliefert, 2)
  assert.equal(stand.installiert, 2)
  // Flag sagt „veraltet“, die Zahlen sagen „aktuell“ — die Zahlen gewinnen.
  assert.equal(stand.veraltet, false)
  assert.equal(bausteineStand(statusAntwort({ mitgeliefert_version: 3 })).veraltet, true)
  assert.equal(bausteineStand(statusAntwort({ installiert_version: 0 })).veraltet, true)
  assert.equal(bausteineStand(statusAntwort({ installiert_version: 0, mitgeliefert_version: 0 })).veraltet, false)
})

test('BS-2d: unbrauchbare Werte zählen als 0 und sind nicht erreichbar', () => {
  assert.deepEqual(bausteineStand(null), {
    erreichbar: false, mitgeliefert: 0, installiert: 0, veraltet: false, hinweis: '', revision: '',
  })
  const kaputt = bausteineStand({
    erreichbar: 'true', mitgeliefert_version: 'viele', installiert_version: -3, hinweis: '  ',
  })
  assert.equal(kaputt.erreichbar, false, 'nur echtes true zählt')
  assert.equal(kaputt.mitgeliefert, 0)
  assert.equal(kaputt.installiert, 0)
  assert.equal(kaputt.veraltet, false)
  // Ein nicht erreichbares Werkzeug ist NIE „veraltet“.
  assert.equal(bausteineStand({ erreichbar: false, mitgeliefert_version: 5 }).veraltet, false)
})

// ── 3. Zustand (fünf Fälle) ────────────────────────────────────────────────

test('BS-2d: „aktuell“ bietet KEINEN Knopf an', () => {
  const z = bausteineZustand(statusAntwort())
  assert.equal(z.ton, 'ok')
  assert.equal(z.titel, 'Aktuell')
  assert.equal(z.aktion, '', 'bei aktuellem Stand gibt es nichts einzuspielen')
  assert.match(z.text, /Fassung 2/)
})

test('BS-2d: „nichts eingespielt“ bietet „einspielen“ an', () => {
  const z = bausteineZustand(statusAntwort({ installiert_version: 0, bausteine: [] }))
  assert.equal(z.ton, 'info')
  assert.equal(z.titel, 'Noch nicht eingespielt')
  assert.match(z.aktion, /einspielen/)
})

test('BS-2d: „veraltet“ bietet „aktualisieren“ an und nennt beide Fassungen', () => {
  const z = bausteineZustand(statusAntwort({ mitgeliefert_version: 7, installiert_version: 5 }))
  assert.equal(z.ton, 'warn')
  assert.equal(z.titel, 'Aktualisierung verfügbar')
  assert.match(z.aktion, /aktualisieren/)
  assert.match(z.text, /Fassung 5/)
  assert.match(z.text, /Fassung 7/)
})

test('BS-2d: nicht erreichbar und „nichts mitgeliefert“ sperren den Knopf', () => {
  const weg = bausteineZustand({ erreichbar: false, hinweis: 'Die Bibliothek ist derzeit nicht abrufbar.' })
  assert.equal(weg.ton, 'warn')
  assert.equal(weg.aktion, '')
  assert.equal(weg.text, 'Die Bibliothek ist derzeit nicht abrufbar.')

  const leer = bausteineZustand(statusAntwort({ mitgeliefert_version: 0, installiert_version: 0, bausteine: [] }))
  assert.equal(leer.ton, 'err')
  assert.equal(leer.titel, 'Nichts mitgeliefert')
  assert.equal(leer.aktion, '')
})

test('BS-2d: alle Texte sprechen vom Website-Baukasten (Begriff UX3a)', () => {
  assert.equal(WERKZEUG, 'Website-Baukasten')
  for (const antwort of [
    statusAntwort(),
    statusAntwort({ installiert_version: 0, bausteine: [] }),
    statusAntwort({ mitgeliefert_version: 9 }),
    { erreichbar: false },
    statusAntwort({ mitgeliefert_version: 0, installiert_version: 0, bausteine: [] }),
  ]) {
    const z = bausteineZustand(antwort)
    assert.doesNotMatch(z.text, /\bPrimo\b/, `„Primo“ ist der Anbietername, nicht der Knopf: ${z.text}`)
    assert.doesNotMatch(z.aktion, /\bPrimo\b/, z.aktion)
  }
})

// ── 4. Zeilen ──────────────────────────────────────────────────────────────

test('BS-2d: Zeilen-Sstand „mitgeliefert“ / „installiert“ / „ältere Fassung“', () => {
  assert.deepEqual(bausteinZeileStand(null, 2), {
    installiert: false, veraltet: false, ton: 'neutral', text: 'mitgeliefert',
  })
  assert.deepEqual(bausteinZeileStand({ version: 2 }, 2), {
    installiert: true, veraltet: false, ton: 'ok', text: 'installiert (2)',
  })
  const alt = bausteinZeileStand({ version: 1 }, 3)
  assert.equal(alt.installiert, true)
  assert.equal(alt.veraltet, true)
  assert.equal(alt.ton, 'warn')
  assert.match(alt.text, /ältere Fassung \(1\)/)
})

test('BS-2d: die Zeilen kommen AUS DER SERVERANTWORT — nichts ist erfunden', () => {
  const zeilen = bausteinZeilen(statusAntwort())
  assert.deepEqual(zeilen.map((z) => z.kennung), ['kontakt', 'termine-liste'])
  assert.ok(zeilen.every((z) => z.stand.installiert))
  // Kein Name/Beschreibung im Serververtrag → leer, NICHT ausgedacht.
  assert.equal(zeilen[0].name, '')
  assert.equal(zeilen[0].beschreibung, '')

  // Das Werkzeug ist leer: die Liste ist LEER, nicht „alle mitgelieferten“.
  assert.deepEqual(bausteinZeilen(statusAntwort({ installiert_version: 0, bausteine: [] })), [])
  assert.deepEqual(bausteinZeilen(null), [])

  // Ein künftiger Server darf Name und Beschreibung mitliefern (BS-2b):
  // hat das Werkzeug den Eintrag noch nicht, stehen sie trotzdem da.
  const mitText = bausteinZeilen(statusAntwort({
    installiert_version: 0,
    bausteine: [],
    mitgeliefert: [
      { kennung: 'kontakt', name: 'Diakronos: Kontaktformular', version: 2,
        beschreibung: 'Kontaktformular für die Website.' },
    ],
  }))
  assert.equal(mitText.length, 1)
  assert.equal(mitText[0].beschreibung, 'Kontaktformular für die Website.')
  assert.equal(mitText[0].stand.installiert, false)
  assert.equal(mitText[0].stand.text, 'mitgeliefert')
})

test('BS-2d: alte und neue Fassung derselben Kennung ergeben EINE Zeile (höchste zählt)', () => {
  const zeilen = bausteinZeilen(statusAntwort({
    mitgeliefert_version: 3,
    bausteine: [
      { kennung: 'kontakt', name: 'diakronos/kontakt@v1', version: 1 },
      { kennung: 'kontakt', name: 'diakronos/kontakt@v3', version: 3 },
      { kennung: 'gruppen', name: 'diakronos/gruppen@v2', version: 2 },
    ],
  }))
  assert.deepEqual(zeilen.map((z) => z.kennung), ['kontakt', 'gruppen'])
  assert.equal(zeilen[0].fassung, 3)
  assert.equal(zeilen[0].stand.veraltet, false)
  assert.equal(zeilen[1].stand.veraltet, true, 'gruppen v2 < mitgeliefert v3')
})

test('BS-2d: Einträge ohne Kennung werden übergangen', () => {
  const zeilen = bausteinZeilen(statusAntwort({
    bausteine: [{ kennung: '', version: 2 }, { version: 2 }, { kennung: 'kontakt', version: 2 }],
  }))
  assert.deepEqual(zeilen.map((z) => z.kennung), ['kontakt'])
})

// ── 5. Freigaben ───────────────────────────────────────────────────────────

test('BS-2d: jeder Baustein nennt die Freigaben, auf denen er aufsetzt', () => {
  // Vorhandene Bausteine aus BS-2a/BS-2c — die Zuordnung folgt ihrem
  // Datenabruf (`/website/oeffentlich/…`).
  assert.deepEqual(bausteinFreigaben('kontakt'), ['Kontakt-Postfächer'])
  assert.deepEqual(bausteinFreigaben('termine-liste'), ['Termine'])
  assert.deepEqual(bausteinFreigaben('gruppen'), ['Gruppen'])
  assert.deepEqual(bausteinFreigaben('neuigkeiten'), ['Beiträge'])
  assert.ok(bausteinFreigaben('gruppe-steckbrief').includes('Gruppen'))
  assert.ok(bausteinFreigaben('anmeldung').length >= 1)
  // Unbekannte Kennung: leere Liste, keine erfundene Freigabe.
  assert.deepEqual(bausteinFreigaben('gibt-es-nicht'), [])
  assert.deepEqual(bausteinFreigaben(null), [])
  // Die Liste ist eine Kopie — niemand ändert die Zuordnung von aussen.
  bausteinFreigaben('kontakt').push('Unsinn')
  assert.deepEqual(bausteinFreigaben('kontakt'), ['Kontakt-Postfächer'])
})

test('BS-2d: Freigaben als Satz, lange Listen werden gezählt', () => {
  assert.equal(freigabenText([]), '')
  assert.equal(freigabenText(null), '')
  assert.equal(freigabenText(['Gruppen']), 'Gruppen')
  assert.equal(freigabenText(['Gruppen', ' Termine ']), 'Gruppen, Termine')
  assert.equal(freigabenText(['a', 'b', 'c', 'd', 'e', 'f']), 'a, b, c, d und 2 weitere')
})

// ── 6. Ergebnis-Meldung ────────────────────────────────────────────────────

test('BS-2d: nach dem Einspielen nennt die Meldung die Anzahl im Klartext', () => {
  const einer = installationsMeldung({ version: 6, bausteine: ['kontakt'], revision: 'v6:x', weg: 'zip' })
  assert.equal(einer.ton, 'ok')
  assert.equal(einer.text, `1 Baustein (Fassung 6) im ${WERKZEUG} eingespielt.`)

  const viele = installationsMeldung({ version: 6, bausteine: ['kontakt', 'gruppen', 'neuigkeiten'] })
  assert.match(viele.text, /^3 Bausteine \(Fassung 6\)/)

  const nichts = installationsMeldung({ version: 6, bausteine: [] })
  assert.equal(nichts.ton, 'warn')
  assert.doesNotMatch(nichts.text, /^0 /, 'keine „0 Bausteine eingespielt“-Erfolgsmeldung')

  // Kein Jargon in der Meldung.
  for (const m of [einer, viele, nichts]) {
    assert.doesNotMatch(m.text, /ZIP|Revision|import-library|einzeln/, m.text)
  }
})

// ── 7. Anbindung ───────────────────────────────────────────────────────────

test('BS-2d: Status per GET, Einspielen NUR per POST (apiCall)', () => {
  const quelle = ohneKommentare(lies('src/diakonos/composables/useWebsiteBausteine.js'))
  assert.match(quelle, /diakronos\.diakronos\.api\.website\.bausteine_status/, 'Status-Kennung fehlt')
  assert.match(quelle, /diakronos\.diakronos\.api\.website\.bausteine_installieren/, 'Installieren-Kennung fehlt')
  assert.match(quelle, /apiGet\(API\.status\)/, 'Status geht nicht über apiGet')
  assert.match(quelle, /apiCall\(API\.installieren/, 'Einspielen geht nicht über apiCall (POST/CSRF)')
  // Kein zweiter HTTP-Weg an der Zentrale vorbei.
  assert.doesNotMatch(quelle, /\bfetch\(/, 'kein fetch — apiGet/apiCall tragen Präfix und CSRF')
  assert.doesNotMatch(quelle, /['"`]\/api\//, 'kein fester /api/-Pfad (WEB-5b)')
  // Nach dem Einspielen wird der Stand neu gelesen (Serverstand, nicht Vermutung).
  const einspielen = quelle.slice(quelle.indexOf('async function einspielen'))
  assert.match(einspielen, /await laden\(\)/, 'nach dem Einspielen wird der Stand nicht neu gelesen')
  // Doppelklick-Schutz.
  assert.match(einspielen, /if \(spieltEin\.value\)/, 'kein Schutz gegen den zweiten Klick')
})

test('BS-2d: nur berechtigte Rollen sehen den Bereich (Server weist zusätzlich ab)', () => {
  const seite = ohneKommentare(lies('src/diakonos/pages/Website.vue'))
  // Der Bereich steht im geschützten Zweig (v-else von `!darfVerwalten`).
  const geschuetzt = seite.slice(seite.indexOf('v-else class="wf-bereich"'))
  assert.match(geschuetzt, /<BausteineBereich\s*\/>/, 'Bausteine stehen nicht im geschützten Bereich')
  assert.match(seite, /darfFreigabenVerwalten\(\{ rollen: rollen\.value \}\)/, 'Rollenprüfung an der Seite fehlt')
  assert.match(
    lies('src/shared/website-bausteine.mjs'),
    /export function darfBausteineSehen/,
    'darfBausteineSehen fehlt'
  )
})

// ── 8. Bauteil ─────────────────────────────────────────────────────────────

test('BS-2d: die Importpfade zeigen auf vorhandene Dateien (Build-Gegenprobe)', () => {
  // Im Worktree liefen die Node-Tests grün, der Vite-Build brach an drei
  // falsch gezählten `../` (Bauteil liegt eine Ebene tiefer). Genau das
  // prüft dieser Test jetzt: jeder relative Import existiert auf der Platte.
  const datei = 'src/diakonos/components/website/BausteineBereich.vue'
  const quelle = lies(datei)
  const treffer = [...quelle.matchAll(/from\s+'(\.\.?\/[^']+)'/g)].map((m) => m[1])
  assert.ok(treffer.length >= 5, 'keine Importe gefunden')
  for (const pfad of treffer) {
    const abs = path.resolve(path.dirname(path.join(FRONTEND, datei)), pfad)
    assert.ok(existsSync(abs), `${datei}: Import ${pfad} zeigt ins Leere`)
  }
  // … und die Datei, die das Komposabel einbindet, ebenso.
  const seite = lies('src/diakonos/pages/Website.vue')
  for (const pfad of [...seite.matchAll(/from\s+'(\.\.?\/[^']+)'/g)].map((m) => m[1])) {
    const abs = path.resolve(path.dirname(path.join(FRONTEND, 'src/diakonos/pages/Website.vue')), pfad)
    assert.ok(existsSync(abs), `pages/Website.vue: Import ${pfad} zeigt ins Leere`)
  }
})

test('BS-2d: das Komposabel bindet nur Funktionen ein, die es auch gibt', () => {
  // Der Vite-Build meldete `bausteineZeilen is not exported` — die Node-Tests
  // waren grün, weil das Komposabel dort nie geladen wird. Dieser Test zieht
  // die Namen aus dem Quelltext und vergleicht sie mit den echten Exporten.
  const quelle = ohneKommentare(lies('src/diakonos/composables/useWebsiteBausteine.js'))
  const importe = [...quelle.matchAll(/import\s*\{([^}]+)\}\s*from\s*'[^']*website-bausteine\.mjs'/g)]
    .flatMap((m) => m[1].split(',').map((n) => n.trim()).filter(Boolean))
  assert.ok(importe.length >= 3, 'kein Import aus shared/website-bausteine.mjs')
  const modul = lies('src/shared/website-bausteine.mjs')
  for (const name of importe) {
    assert.match(modul, new RegExp(`export function ${name}\\(`), `${name} wird exportiert? Nein.`)
  }
})

test('BS-2d: das Bauteil zeichnet nur — keine hartkodierte Bausteinliste', () => {
  const bauteil = lies('src/diakonos/components/website/BausteineBereich.vue')
  const vorlage = ohneKommentare(bauteil.split('<script')[0])
  // Kein Bausteinname des Auslieferungssatzes im Markup.
  for (const kennung of ['kontakt', 'termine-liste', 'gruppen', 'neuigkeiten', 'anmeldung', 'gruppe-steckbrief']) {
    assert.doesNotMatch(vorlage, new RegExp(`["'\`]${kennung}["'\`]`), `Baustein ${kennung} ist im Bauteil verdrahtet`)
  }
  // Die Zeilen kommen aus dem Komposabel.
  assert.match(bauteil, /from '\.\.\/\.\.\/composables\/useWebsiteBausteine\.js'/, 'Komposabel fehlt')
  assert.match(bauteil, /v-for="z in zeilen"/, 'Liste zeichnet keine Serverzeilen')
  // Anleitung und Knopf-Beschriftung kommen aus der Logik-Datei.
  assert.match(bauteil, /bausteineAnleitung\(\)/, 'Kurzanleitung fehlt')
  assert.match(vorlage, /zustand\.aktion/, 'die Knopf-Beschriftung ist fest statt aus dem Zustand')
})

test('BS-2d: Knöpfe nur über DkButton, genau EIN Primärknopf', () => {
  const bauteil = lies('src/diakonos/components/website/BausteineBereich.vue')
  const vorlage = ohneKommentare(bauteil.split('<script')[0])
  assert.doesNotMatch(vorlage, /<button\b/, 'roher <button> (UX1g)')
  const primaer = vorlage.match(/variant="primary"/g) || []
  assert.equal(primaer.length, 1, 'genau ein gefüllter Knopf je Bereich (UX1h)')
  // Das „Stand neu laden“ ist secondary.
  assert.match(vorlage, /<DkButton variant="secondary"[\s\S]{0,200}Stand neu laden/, 'zweiter Knopf nicht secondary')
})

test('BS-2d: keine festen Farben und Abstände im Bauteil (Tokens)', () => {
  const bauteil = lies('src/diakonos/components/website/BausteineBereich.vue')
  const stil = bauteil.slice(bauteil.indexOf('<style'), bauteil.indexOf('</style>'))
  assert.doesNotMatch(stil, /#[0-9a-fA-F]{3,8}\b/, 'feste Farbe im Stil')
  assert.doesNotMatch(stil, /\b\d+px\b/, 'fester Abstand im Stil')
  // Abstände ausschließlich über die Skala.
  assert.match(stil, /var\(--sp-\d\)/, 'keine Abstands-Tokens benutzt')
})

test('BS-2d: die Kurzanleitung nennt Bibliothek, Diakronos und die Site-Stile', () => {
  const saetze = bausteineAnleitung()
  assert.ok(saetze.length >= 3, 'zu wenig Schritte')
  const zusammen = saetze.join(' ')
  assert.match(zusammen, /Website-Baukasten/, 'Werkzeug fehlt')
  assert.match(zusammen, /Bibliothek/i, '„Bibliothek“ fehlt')
  assert.match(zusammen, /Diakronos/, 'Gruppe „Diakronos“ fehlt')
  assert.match(zusammen, /Felder/, '„Felder anpassen“ fehlt')
  assert.match(zusammen, /--dk-\*/, 'Hinweis auf die Site-Stile (--dk-*) fehlt')
})

test('BS-2d: alle fünf Zustände sind gestaltet (Prinzip I5)', () => {
  const bauteil = ohneKommentare(lies('src/diakonos/components/website/BausteineBereich.vue'))
  // Zustand (Badge + Satz), Aktion, Lauf, Erfolg/Fehler, leer, gefüllt.
  assert.match(bauteil, /wb-zustand/, 'Standzeile fehlt')
  assert.match(bauteil, /wb-aktionen/, 'Aktionszeile fehlt')
  assert.match(bauteil, /<DkHint v-if="ergebnisMeldung"/, 'Erfolgs-/Fehlermeldung fehlt')
  assert.match(bauteil, /<DkHint v-if="ladehinweis"/, 'Ladezustand fehlt')
  assert.match(bauteil, /<DkEmpty[\s\S]{0,120}title="Keine Bausteine"/, 'Leerzustand fehlt')
  assert.match(bauteil, /wb-liste/, 'Listen-Zustand fehlt')
  // Fehler- und Ladehinweis sind für Vorlesehilfen markiert.
  assert.match(bauteil, /role="alert"/, 'Fehlermeldung ohne role=alert')
  assert.match(bauteil, /role="status"/, 'Ladezustand ohne role=status')
})

test('BS-2d: der Test steht in der Frontend-Testliste (FE-TEST-1)', () => {
  const liste = lies('tests/testliste.txt')
  assert.match(liste, /^tests\/bs2d-\*\.test\.mjs$/m, 'bs2d fehlt in der Frontend-Testliste')
})
