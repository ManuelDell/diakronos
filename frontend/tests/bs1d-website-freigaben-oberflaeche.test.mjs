/**
 * BS-1d — Website-Freigaben: Oberfläche (Regeln + Verdrahtung).
 *
 * Die Oberfläche selbst (Seite „Website“, Bereich „Website-Freigaben“, der
 * Schalter im Beitragseditor) lässt sich nicht in `node --test` bedienen; was
 * sie ENTSCHEIDET, steht deshalb in `src/shared/website-freigaben.mjs` und wird
 * hier ausgeführt. Zusätzlich wird geprüft, dass die Seiten diese Regeln auch
 * BENUTZEN — sonst wäre ein grüner Regeltest nur Zierde:
 *
 *   (1) Rollen-Sichtbarkeit: nur System Manager / Administrator /
 *       Website-Moderator — und dieselben Rollen wie Menü und Router (WEB-3).
 *   (2) Slug-Prüfung: Form, Länge, Ränder, reservierte Werte — deckungsgleich
 *       mit `website/freigaben.py`.
 *   (3) Warnung vor dem Einschalten: nennt Titel, Zeit, Ort und die KOMPLETTE
 *       Beschreibung (Orchestrator-Zusatz 2026-11-02).
 *   (4) Nutzlast an `freigabe_setzen`: ein unveränderter Slug wird NICHT
 *       mitgeschickt (sonst „bereits vergeben“ bei gleichnamigen Zeilen).
 *   (5) Postfach-Prüfung und Rückfall-Hinweis.
 *   (6) Verdrahtung: alle sechs Endpunkte, POST über `apiCall`, der Schalter
 *       im Beitragseditor, die Warnung als Bestätigung, und die Kürzel-Prüfung
 *       im Eingabefeld.
 *
 * Läuft im Frontend-Stage des Docker-Builds (cwd = frontend/). Der Test liest
 * Dateien AUSSERHALB von frontend/ (backend/…) — die COPY-Zeilen für den
 * Build stehen in backend/Dockerfile (Regel 13).
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  BEZEICHNUNG_MAX,
  EMAIL_MAX,
  FREIGABE_ROLLEN,
  RESERVIERTE_SLUGS,
  SLUG_MAX,
  beitraegeAufWebsite,
  darfFreigabenVerwalten,
  freigabeNutzlast,
  freigabeZeile,
  gruppenWarnung,
  kalenderWarnung,
  kategorieHinweis,
  kurzanleitung,
  naechsteSortierung,
  postfachHinweis,
  postfachPruefen,
  slugPruefen,
} from '../src/shared/website-freigaben.mjs'

/**
 * Wo liegt das Repository?
 *
 * Im Worktree liegt der Test unter `<repo>/frontend/tests/` — zwei Ebenen
 * höher ist das Repo. Im Docker-Frontend-Stage wird er mit
 * `COPY frontend/ ./` nach `/build/` gelegt: `/build/tests/` → `/` ist dort
 * NICHT das Repo (nur die ausdrücklich kopierten Dateien liegen dort).
 * Deshalb: gilt die Rechnung nur, wenn `<repo>/frontend/src` wirklich da ist;
 * sonst ist das laufende Verzeichnis (cwd = frontend/) das Frontend-Wurzel.
 */
const HIER = dirname(fileURLToPath(import.meta.url))
const GERECHNET = join(HIER, '..', '..')
const FRONTEND = existsSync(join(GERECHNET, 'frontend', 'src'))
  ? join(GERECHNET, 'frontend')
  : join(process.cwd())
const REPO = dirname(FRONTEND)

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

const SEITE = join(FRONTEND, 'src', 'diakonos', 'pages', 'Website.vue')
const ZEILE = join(FRONTEND, 'src', 'diakonos', 'components', 'website', 'FreigabeZeile.vue')
const BEITRAEGE = join(FRONTEND, 'src', 'diakonos', 'pages', 'Beitraege.vue')
const API_JS = join(FRONTEND, 'src', 'diakonos', 'composables', 'useWebsiteFreigaben.js')
const BACKEND_API = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'website.py')
const BACKEND_REGELN = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'freigaben.py')

// ── 1 · Rollen-Sichtbarkeit ─────────────────────────────────────────────────
test('BS-1d: nur die drei Website-Rollen sehen den Freigabe-Bereich', () => {
  assert.deepEqual(FREIGABE_ROLLEN, ['System Manager', 'Administrator', 'Website-Moderator'])
  for (const rollen of [['System Manager'], ['Administrator'], ['Website-Moderator']]) {
    assert.equal(darfFreigabenVerwalten({ rollen }), true, `Rolle ${rollen[0]} muss reichen`)
  }
  for (const rollen of [[], null, ['Mitgliederadministrator'], ['Gast'], ['Mitglied']]) {
    assert.equal(darfFreigabenVerwalten({ rollen }), false, `${JSON.stringify(rollen)} darf nicht reichen`)
  }
  // Leerzeichen und fremde Schreibweise sind kein Freibrief.
  assert.equal(darfFreigabenVerwalten({ rollen: ['website-moderator'] }), false)
  assert.equal(darfFreigabenVerwalten({ rollen: ['  Administrator  '] }), true)
})

test('BS-1d: die Rollenliste der Oberfläche deckt sich mit dem Backend', () => {
  const prima = lies(join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'primo.py'))
  const block = prima.slice(prima.indexOf('WEBSITE_ROLLEN'))
  for (const rolle of FREIGABE_ROLLEN) {
    assert.ok(block.includes(`"${rolle}"`), `WEBSITE_ROLLEN im Backend kennt ${rolle} nicht`)
  }
})

test('BS-1d: die Seite benutzt die Rollenregel statt einer eigenen Liste', () => {
  const seite = lies(SEITE)
  assert.match(seite, /darfFreigabenVerwalten/)
  assert.match(seite, /v-if="!darfVerwalten"/)
  // Keine zweite, hart geschriebene Rollenliste in der Seite.
  assert.doesNotMatch(seite, /'System Manager'.*'Administrator'/)
})

// ── 2 · Slug-Prüfung ────────────────────────────────────────────────────────
test('BS-1d: gültige Kürzel gehen durch', () => {
  for (const slug of ['gemeinde', 'jugend-freizeit', 'a1', 'cafe-2', 'x'.repeat(SLUG_MAX)]) {
    const ergebnis = slugPruefen(slug)
    assert.equal(ergebnis.ok, true, `${slug} müsste gültig sein: ${ergebnis.fehler}`)
    assert.equal(ergebnis.slug, slug)
  }
  // Leerzeichen am Rand werden abgeschnitten (wie im Backend `.strip()`).
  assert.deepEqual(slugPruefen('  gemeinde  '), { ok: true, slug: 'gemeinde', fehler: '' })
})

test('BS-1d: ungültige Kürzel werden mit deutscher Meldung abgelehnt', () => {
  const faelle = [
    ['', /an/i],
    ['   ', /an/i],
    ['Jugend', /Kleinbuchstaben/i],
    ['jugend freizeit', /Kleinbuchstaben/i],
    ['jugend_freizeit', /Kleinbuchstaben/i],
    ['grüße', /Kleinbuchstaben/i],
    ['-gemeinde', /Bindestrich/i],
    ['gemeinde-', /Bindestrich/i],
    ['ju--gend', /Bindestrich/i],
    ['x'.repeat(SLUG_MAX + 1), /Zeichen/i],
  ]
  for (const [slug, muster] of faelle) {
    const ergebnis = slugPruefen(slug)
    assert.equal(ergebnis.ok, false, `${JSON.stringify(slug)} müsste abgelehnt werden`)
    assert.match(ergebnis.fehler, muster, `Meldung für ${JSON.stringify(slug)}`)
  }
})

test('BS-1d: reservierte Kürzel sind dieselben wie im Backend und werden abgelehnt', () => {
  const regeln = lies(BACKEND_REGELN)
  assert.deepEqual(RESERVIERTE_SLUGS, ['diakronos', 'primo', 'admin', 'api', 'login', 'standard'])
  for (const slug of RESERVIERTE_SLUGS) {
    assert.ok(regeln.includes(`"${slug}"`), `Backend kennt den reservierten Kürzel ${slug} nicht`)
    const ergebnis = slugPruefen(slug)
    assert.equal(ergebnis.ok, false, `${slug} ist reserviert`)
    assert.match(ergebnis.fehler, /reserviert/i)
  }
  // Das Backend prüft `text.lower() in RESERVIERTE_SLUGS` — die Oberfläche auch.
  assert.equal(slugPruefen('Standard').ok, false)
})

test('BS-1d: Längengrenzen decken sich mit dem Backend', () => {
  const regeln = lies(BACKEND_REGELN)
  assert.match(regeln, /SLUG_MAX = 140/)
  assert.match(regeln, /BEZEICHNUNG_MAX = 140/)
  assert.match(regeln, /EMAIL_MAX = 320/)
  assert.equal(SLUG_MAX, 140)
  assert.equal(BEZEICHNUNG_MAX, 140)
  assert.equal(EMAIL_MAX, 320)
})

// ── 3 · Warnung beim Einschalten ────────────────────────────────────────────
test('BS-1d: die Kalender-Warnung nennt Titel, Zeit, Ort und die KOMPLETTE Beschreibung', () => {
  const text = kalenderWarnung('Gottesdienste')
  assert.match(text, /Titel/)
  assert.match(text, /Zeit/)
  assert.match(text, /Ort/)
  assert.match(text, /KOMPLETTE Beschreibung/)
  assert.match(text, /interne Notizen/)
  assert.match(text, /Gottesdienste/, 'der Anzeigename gehört in den Text')
  // Ohne Namen bleibt der Satz vollständig.
  assert.match(kalenderWarnung(''), /dieses Kalenders/)
})

test('BS-1d: die Gruppen-Warnung nennt die Felder und schließt Personen aus', () => {
  const text = gruppenWarnung('Jugend & Freizeit')
  for (const feld of ['Name', 'Typ', 'Beschreibung', 'Treffzeit', 'Treffpunkt', 'Bild']) {
    assert.match(text, new RegExp(feld), `${feld} fehlt in der Warnung`)
  }
  assert.match(text, /Personen/)
  assert.match(text, /nicht/)
})

test('BS-1d: die Seite fragt vor dem Einschalten nach (Kalender und Gruppe)', () => {
  const seite = lies(SEITE)
  assert.match(seite, /kalenderWarnung\(zeile\.titel\)/)
  assert.match(seite, /gruppenWarnung\(zeile\.titel\)/)
  assert.match(seite, /bestaetigen\(\{/)
  // Die Bestätigung steht VOR dem Schreiben.
  const kalBlock = seite.slice(seite.indexOf('async function kalenderFreigabe'))
  assert.ok(
    kalBlock.indexOf('bestaetigen(') < kalBlock.indexOf('freigabeSetzen('),
    'die Warnung muss vor dem Aufruf kommen',
  )
})

// ── 4 · Nutzlast an freigabe_setzen ────────────────────────────────────────
test('BS-1d: ein unveränderter Kürzel wird nicht mitgeschickt', () => {
  const gleich = freigabeNutzlast({
    art: 'kalender', name: 'KAL-1', freigabe: true, slug: 'gemeinde', gespeicherterSlug: 'gemeinde',
  })
  assert.deepEqual(gleich, { art: 'kalender', name: 'KAL-1', freigabe: true })

  const neu = freigabeNutzlast({
    art: 'gruppe', name: 'GRP-1', freigabe: true, slug: 'jugend', gespeicherterSlug: '',
  })
  assert.deepEqual(neu, { art: 'gruppe', name: 'GRP-1', freigabe: true, slug: 'jugend' })

  // Leer heißt „nicht gesetzt“: der Server leitet selbst ab.
  const leer = freigabeNutzlast({
    art: 'gruppe', name: 'GRP-1', freigabe: true, slug: '   ', gespeicherterSlug: '',
  })
  assert.equal('slug' in leer, false)
})

test('BS-1d: der Kategorie-Schalter geht nur bei Kalendern mit', () => {
  const kal = freigabeNutzlast({
    art: 'kalender', name: 'K', freigabe: false, nurOeffentlicheKategorien: true,
  })
  assert.equal(kal.nur_oeffentliche_kategorien, true)
  const grp = freigabeNutzlast({
    art: 'gruppe', name: 'G', freigabe: true, nurOeffentlicheKategorien: true,
  })
  assert.equal('nur_oeffentliche_kategorien' in grp, false)
  // Nicht gesetzt (`null`) heißt: nicht mitgeschickt.
  const ohne = freigabeNutzlast({ art: 'kalender', name: 'K', freigabe: true })
  assert.equal('nur_oeffentliche_kategorien' in ohne, false)
})

test('BS-1d: der Kategorie-Hinweis warnt vor „kein Termin erscheint“', () => {
  assert.match(kategorieHinweis(0), /KEIN Termin/)
  assert.match(kategorieHinweis(1), /einen|einen als öffentlich/)
  assert.match(kategorieHinweis(3), /3/)
  assert.match(kategorieHinweis(Number.NaN), /KEIN Termin/)
})

// ── 5 · Postfächer und Beiträge ────────────────────────────────────────────
test('BS-1d: Postfach-Eingaben werden vor dem Aufruf geprüft', () => {
  const gut = postfachPruefen({ slug: 'allgemein', bezeichnung: 'Allgemein', email: 'post@example.org' })
  assert.equal(gut.ok, true)

  const leer = postfachPruefen({ slug: '', bezeichnung: '', email: '' })
  assert.equal(leer.ok, false)
  assert.match(leer.felder.slug, /Kürzel/i)
  assert.match(leer.felder.bezeichnung, /Bezeichnung/i)
  assert.match(leer.felder.email, /E-Mail/)

  for (const email of ['ohne-at.example.org', 'a@b', 'a b@example.org', 'a@@example.org', 'a@example']) {
    assert.equal(postfachPruefen({ slug: 'x1', bezeichnung: 'X', email }).ok, false, `${email} ist ungültig`)
  }
  const lang = postfachPruefen({
    slug: 'x1', bezeichnung: 'x'.repeat(BEZEICHNUNG_MAX + 1), email: 'a@example.org',
  })
  assert.match(lang.felder.bezeichnung, /zu lang/)

  // Reservierter Kürzel wird auch hier abgelehnt (Rückfall-Postfach).
  assert.match(postfachPruefen({ slug: 'standard', bezeichnung: 'X', email: 'a@example.org' }).felder.slug, /reserviert/i)
})

test('BS-1d: der Rückfall-Hinweis unterscheidet drei Fälle', () => {
  const ohne = postfachHinweis({ postfaecher: [], postfach_fallback: { aktiv: true, bezeichnung: 'Allgemein' } })
  assert.equal(ohne.ton, 'info')
  assert.match(ohne.text, /Konfiguration/)

  const aus = postfachHinweis({ postfaecher: [{ aktiv: false }], postfach_fallback: { aktiv: false } })
  assert.equal(aus.ton, 'warn')
  assert.match(aus.text, /NICHT/)

  const an = postfachHinweis({ postfaecher: [{ aktiv: true }, { aktiv: false }] })
  assert.equal(an.ton, 'ok')
  assert.match(an.text, /Ein Postfach/)

  const zwei = postfachHinweis({ postfaecher: [{ aktiv: true }, { aktiv: true }] })
  assert.match(zwei.text, /^2 Postfächer/)
})

test('BS-1d: die Sortierung schlägt den nächsten Zehner-Schritt vor', () => {
  assert.equal(naechsteSortierung([]), 10)
  assert.equal(naechsteSortierung(null), 10)
  assert.equal(naechsteSortierung([{ sortierung: 10 }, { sortierung: 30 }]), 40)
  assert.equal(naechsteSortierung([{ sortierung: '20' }]), 30)
  assert.equal(naechsteSortierung([{ sortierung: null }, {}]), 10)
})

test('BS-1d: Freigabe-Zeilen werden ohne Wert nicht als freigegeben gedeutet (G1)', () => {
  const zeile = freigabeZeile({ name: 'GRP-1', titel: '', freigabe: undefined })
  assert.equal(zeile.freigabe, false, 'fehlende Freigabe ist AUS')
  assert.equal(zeile.titel, 'GRP-1', 'ohne Titel steht die Kennung da')
  assert.equal(zeile.slug, '')
  assert.equal(zeile.nurOeffentlicheKategorien, false)
  // Nur echtes `true` zählt — auch keine „1“ aus einem Formular.
  assert.equal(freigabeZeile({ name: 'X', freigabe: 'true' }).freigabe, false)
  assert.equal(freigabeZeile({ name: 'X', freigabe: true }).freigabe, true)
})

test('BS-1d: die Beitragszahl kommt vom Server, sonst aus der Liste', () => {
  assert.equal(beitraegeAufWebsite({ beitraege_anzahl: 3, beitraege: [{}, {}] }), 3)
  assert.equal(beitraegeAufWebsite({ beitraege: [{}, {}] }), 2)
  assert.equal(beitraegeAufWebsite({ beitraege_anzahl: 0, beitraege: [{}] }), 0)
  assert.equal(beitraegeAufWebsite(null), 0)
})

test('BS-1d: die Kurzanleitung hat zwei bis vier Sätze', () => {
  const saetze = kurzanleitung()
  assert.ok(Array.isArray(saetze))
  assert.ok(saetze.length >= 2 && saetze.length <= 4, `erwartet 2–4 Sätze, sind ${saetze.length}`)
  for (const satz of saetze) assert.ok(String(satz).trim().length > 10)
})

// ── 6 · Verdrahtung ────────────────────────────────────────────────────────
test('BS-1d: alle sechs Verwaltungs-Endpunkte werden angesprochen — schreibend per apiCall', () => {
  const quelle = lies(API_JS)
  const BACKEND = 'diakronos.diakronos.api.website.'
  for (const name of [
    'freigaben_lesen',
    'freigabe_setzen',
    'beitrag_auf_website',
    'postfach_speichern',
    'postfach_loeschen',
    'kategorie_oeffentlich',
  ]) {
    assert.ok(quelle.includes(BACKEND + name), `Endpunkt ${name} fehlt im Composable`)
  }
  // Lesen per apiGet, alles Schreibende per apiCall (POST + CSRF).
  assert.match(quelle, /apiGet\(API\.lesen\)/)
  for (const name of ['freigabe', 'beitrag', 'postfachSpeichern', 'postfachLoeschen', 'kategorie']) {
    assert.match(quelle, new RegExp(`apiCall\\(API\\.${name}`), `${name} muss per apiCall laufen`)
  }
  assert.doesNotMatch(quelle, /apiGet\(API\.(freigabe|beitrag|postfach|kategorie)/)
})

test('BS-1d: die Endpunkte gibt es wirklich im Backend', () => {
  const api = lies(BACKEND_API)
  for (const name of [
    'freigaben_lesen',
    'freigabe_setzen',
    'beitrag_auf_website',
    'postfach_speichern',
    'postfach_loeschen',
    'kategorie_oeffentlich',
  ]) {
    assert.match(api, new RegExp(`def ${name}\\(`), `Backend-Endpunkt ${name} fehlt`)
  }
})

test('BS-1d: die Seite deckt U1–U5 ab', () => {
  const seite = lies(SEITE)
  for (const titel of ['Website-Freigaben', 'Kalender', 'Terminarten', 'Gruppen', 'Beiträge', 'Kontakt-Postfächer']) {
    assert.ok(seite.includes(`title="${titel}"`), `Abschnitt „${titel}“ fehlt`)
  }
  // U1: Schalter, Kürzel, Kategorie-Einschränkung.
  assert.match(lies(ZEILE), /Auf Website zeigen:/)
  assert.match(lies(ZEILE), /Nur öffentliche Terminarten zeigen/)
  assert.match(lies(ZEILE), /Kürzel speichern/)
  // U2: Gruppen-Hinweis nennt die öffentlichen Felder.
  assert.match(seite, /Personen \(Mitglieder,\s*\n?\s*Mitarbeiter, Leitung\) erscheinen nicht/)
  // U3: Anzahl + Weg in die Beiträge.
  assert.match(seite, /beitraegeZahl/)
  assert.match(seite, /#\/beitraege/)
  // U4: Tabelle und Dialog.
  assert.match(seite, /DkTable/)
  assert.match(seite, /postfachNeu/)
  assert.match(seite, /postfachBearbeiten/)
  assert.match(seite, /postfachEntfernen/)
  // U5: „Primo öffnen“ und die Kurzanleitung.
  assert.match(seite, /Primo öffnen/)
  assert.match(seite, /kurzanleitung\(\)/)
})

test('BS-1d: das Kürzel-Feld prüft beim Speichern und zeigt den Fehler am Feld', () => {
  const zeile = lies(ZEILE)
  assert.match(zeile, /slugPruefen\(/)
  assert.match(zeile, /slugFehlerLokal/)
  assert.match(zeile, /:error="slugFehler"/)
  // Der Fehler des Servers (z. B. „vergeben“) bleibt sichtbar, bis er behoben ist.
  assert.match(zeile, /props\.fehler/)
})

test('BS-1d: der Beitragseditor hat den Schalter „Auf Website“ (U3)', () => {
  const seite = lies(BEITRAEGE)
  assert.match(seite, /Auf Website zeigen/)
  assert.match(seite, /websiteUmschalten/)
  assert.match(seite, /beitragSetzen\(/)
  // Der Schalter läuft NICHT über update_beitrag (dort fehlt das Feld bewusst).
  const backend = lies(join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'beitraege.py'))
  assert.doesNotMatch(
    backend.slice(backend.indexOf('def update_beitrag'), backend.indexOf('def delete_beitrag')),
    /auf_website/,
    'update_beitrag darf die Website-Freigabe nicht mitschreiben',
  )
  // Der Stand kommt aus der Liste, damit der Schalter richtig vorbelegt.
  assert.match(backend, /"auf_website": bool\(b\.get\("auf_website"\)\)/)
})

test('BS-1d: die Freigabe-Schalter schreiben nur nach Bestätigung und nie still', () => {
  const seite = lies(SEITE)
  // Kein Fehler wird verschluckt: jede Aktion setzt Zeilenfehler oder Toast.
  assert.match(seite, /setzeZeilenFehler\(schluessel, ergebnis\.ok \? '' : ergebnis\.fehler\)/)
  assert.match(seite, /showToast\(ergebnis\.fehler, 'error'\)/)
  // Ausschalten ohne Rückfrage, Einschalten mit.
  assert.match(seite, /if \(an\) \{/)
})
