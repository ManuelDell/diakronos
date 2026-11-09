/**
 * DEV-B3 — Mitglied-Detail: Kleinfixe (Befunde aus dem Dev-Modus, 29.10.).
 *
 * 1. DMB-e2a7f41994d7 — Geschlecht nur „Männlich"/„Weiblich" (+ leer).
 *    Geprüft an den ECHTEN Auswahlfeldern von `MitgliedDetail.vue` und
 *    `Profile.vue`, an der gemeinsamen Filter-/Sortier-Rechnung der
 *    Stammdaten und an der Server-Validierung (pytest,
 *    `backend/tests/test_dev_b3_*.py`).
 * 2. DMB-2b8262b82c08 — Zugang bearbeitbar ohne Bearbeiten-Modus: die Karte
 *    bekommt `bearbeitbar`, Rollen/Kontozustand/Startpasswort nur dort; der
 *    Passwort-Link bleibt immer erlaubt (nur ein Link, keine Änderung).
 * 3. DMB-c116927ead52 — „Schließen" im Anlege-Dialog ohne Funktion.
 * 4. DMB-d78583647c3a — Passwort-Link ohne Pfad-Präfix (Demo 404).
 *
 * Dies ist ein TEXT-Test (Quelle + Rechnung), kein Mount: die Karte verlangt
 * „TESTS je Punkt", und die Punkte sind Verdrahtung im Markup sowie eine
 * Server-Funktion. Der Mount von ZugangKarte/Dialog steht in keinem
 * bestehenden Test — ein neuer jsdom-Mount wäre für vier Zeilen Markup
 * unverhältnismäßig (und würde die Grenzen von drei Composables stummeln).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, SRC), 'utf8')
/** Vorlagen-Kommentare (`<!-- … -->`) zählen nicht als Verdrahtung. */
const ohneKommentare = (t) => t.replace(/<!--[\s\S]*?-->/g, '')

const DETAIL = lies('pages/MitgliedDetail.vue')
const PROFIL = lies('pages/Profile.vue')
const ZUGANG = lies('components/ZugangKarte.vue')
const DIALOG = lies('components/mitglieder/MitgliedHinzufuegenDialog.vue')
const STAMM = lies('pages/planrahmen/Stammdaten.vue')

// ── 1 · Geschlecht: nur männlich / weiblich ────────────────────────────────

test('DEV-B3/1 · MitgliedDetail bietet nur Männlich/Weiblich an', () => {
  const block = DETAIL.match(/const geschlechtOptionen = \[([\s\S]*?)\n\]/)?.[1] ?? ''
  assert.ok(block, 'geschlechtOptionen vorhanden')
  assert.deepEqual([...block.matchAll(/value: '([^']*)'/g)].map((m) => m[1]),
    ['', 'Männlich', 'Weiblich'], 'leer + genau die beiden Angaben')
  assert.ok(!/Divers/.test(block), 'kein „Divers" in der Mitglieder-Detailansicht')
})

test('DEV-B3/1 · Profile bietet nur Männlich/Weiblich an', () => {
  const block = PROFIL.match(/const geschlechtOptionen = \[([\s\S]*?)\n\]/)?.[1] ?? ''
  assert.ok(block, 'geschlechtOptionen vorhanden')
  assert.deepEqual([...block.matchAll(/value: '([^']*)'/g)].map((m) => m[1]),
    ['', 'Männlich', 'Weiblich'])
  assert.ok(!/Divers/.test(block), 'kein „Divers" im eigenen Profil')
})

test('DEV-B3/1 · gemeinsame Rechnung kennt kein „d" mehr', async () => {
  const m = await import(new URL('pages/planrahmen/stammdaten-geschlecht.mjs', SRC).href)
  assert.deepEqual(m.GESCHLECHT_FILTER.map((o) => o.label),
    ['Alle Geschlechter', 'Männlich', 'Weiblich', 'Nicht angegeben'],
    'Filter: Alle · Männlich · Weiblich · Nicht angegeben')
  assert.deepEqual(m.GESCHLECHT_FILTER.map((o) => o.value), ['', 'm', 'w', 'ohne'])
  // Altdaten „divers"/„inter" gelten als „keine Angabe".
  for (const roh of ['Divers', 'divers', 'd', 'inter', 'intersexuell']) {
    assert.equal(m.geschlechtNormalisieren(roh), '', roh)
    assert.equal(m.geschlechtKurz(roh), '–', roh)
    assert.equal(m.geschlechtLang(roh), 'Nicht angegeben', roh)
  }
  assert.equal(m.geschlechtKurz('Männlich'), 'm')
  assert.equal(m.geschlechtKurz('Weiblich'), 'w')
  // Filter „ohne" trifft Altdaten mit, „d" gibt es nicht mehr.
  const personen = [
    { id: 'a', geschlecht: 'm' }, { id: 'b', geschlecht: 'w' },
    { id: 'c', geschlecht: 'divers' }, { id: 'd', geschlecht: '' },
  ]
  assert.deepEqual(m.personenFiltern(personen, { geschlecht: 'ohne' }).map((p) => p.id), ['c', 'd'])
  assert.deepEqual(m.personenFiltern(personen, { geschlecht: 'd' }).map((p) => p.id), [])
  assert.deepEqual(m.nachGeschlechtSortieren(personen).map((p) => p.id), ['a', 'b', 'c', 'd'],
    'm → w → ohne Angabe (Altdaten am Ende)')
})

test('DEV-B3/1 · Stammdaten-Spalte zeigt und filtert weiter über die gemeinsame Rechnung', () => {
  assert.match(STAMM, /GESCHLECHT_FILTER/, 'Filteroptionen aus der gemeinsamen Liste')
  assert.match(STAMM, /geschlechtKurz\(p\.geschlecht\)/, 'Spalte über geschlechtKurz')
  assert.ok(!/Divers/.test(STAMM), 'kein „Divers" in der Stammdatenseite')
})

// ── 2 · Zugang nur im Bearbeiten-Modus ────────────────────────────────────

test('DEV-B3/2 · MitgliedDetail reicht den Bearbeitungszustand an die Zugangskarte', () => {
  const tag = ohneKommentare(DETAIL).match(/<ZugangKarte[\s\S]*?\/>/)?.[0] ?? ''
  assert.ok(tag, 'ZugangKarte eingebunden')
  assert.match(tag, /:bearbeitbar="isEditing"/,
    'die Karte weiß, ob die Seite gerade bearbeitet wird')
})

test('DEV-B3/2 · ZugangKarte deklariert `bearbeitbar` (Vorgabe: nur anzeigen)', () => {
  assert.match(ZUGANG, /bearbeitbar: \{ type: Boolean, default: false \}/,
    'fehlt der Prop, ist die Karte in der Ansicht — nicht im Bearbeiten')
})

test('DEV-B3/2 · Rollen, Kontozustand und Startpasswort nur im Bearbeiten', () => {
  const t = ohneKommentare(ZUGANG)
  assert.match(t, /<DkField v-if="bearbeitbar" label="Rollen">/,
    'Rollen-Kontrollkästchen nur im Bearbeiten')
  assert.match(t, /<div v-else class="zug-feld">[\s\S]*?Rollen[\s\S]*?<\/div>/,
    'sonst: Rollen als Text')
  assert.match(t, /<div v-if="bearbeitbar" class="zug-aktionen">/,
    '„Rollen speichern"/„Konto sperren" nur im Bearbeiten')
  assert.match(t, /v-if="!oidcAnmeldung && bearbeitbar" label="Startpasswort setzen"/,
    'Startpasswort nur im Bearbeiten')
  const hinweis = t.split('\n').find((z) => z.includes('Startpasswort ändern sich über'))
  assert.ok(hinweis, 'im Ansichtsmodus steht, wo man ändert')
  assert.match(hinweis, /Bearbeiten\u201c/)
})

test('DEV-B3/2 · Passwort-/Einladungslink bleibt auch ohne Bearbeiten erlaubt', () => {
  const t = ohneKommentare(ZUGANG)
  // Konto vorhanden: der Knopf trägt KEINE Bearbeiten-Bedingung.
  const linkZeile = t.split('\n').find((z) => z.includes('Passwort-Link neu erzeugen'))
  assert.ok(linkZeile, 'Knopf vorhanden')
  assert.match(linkZeile, /v-if="!oidcAnmeldung"/)
  assert.ok(!/bearbeitbar/.test(linkZeile), 'nicht an den Bearbeiten-Modus gebunden')
  // Kein Konto: der Einladungslink legt serverseitig ein Konto an
  // (`konto_anlegen`) — also NUR im Bearbeiten-Modus; ansonsten ein Hinweis.
  assert.match(t, /v-else-if="bearbeitbar"[\s\S]*?Zugang mit Einladungslink einrichten/,
    'primärer Knopf im Bearbeiten-Modus')
  assert.ok(!/Einladungslink erzeugen/.test(t),
    'kein Einladungs-Knopf im Ansichtsmodus (er würde ein Konto anlegen)')
  assert.match(t, /<p v-else class="zug-hinweis">\s*Ein Zugang wird über „Bearbeiten“ eingerichtet\./,
    'Ansichtsmodus ohne Konto zeigt, wo man den Zugang einrichtet')
})

// ── 3 · Schließen/Abbrechen im Anlege-Dialog ──────────────────────────────

test('DEV-B3/3 · „Schließen" und „Abbrechen" schließen den Dialog wirklich', () => {
  const t = ohneKommentare(DIALOG)
  assert.match(t, /@click="schliessen\(false\)">Schließen</,
    'Knopf übergibt false statt des Klick-Events')
  assert.match(t, /@click="schliessen\(false\)">Abbrechen</,
    'Abbrechen ebenso')
  const offene = t.split('\n').filter((z) => /@click="schliessen"/.test(z))
  assert.deepEqual(offene, [], 'kein Knopf ruft `schliessen` ohne Argument')
  // DkDialog meldet weiterhin den neuen Wert — die Meldung bleibt verdrahtet.
  assert.match(t, /@update:model-value="schliessen"/,
    'Schließen über die Dialog-Bausteine (Esc, Überlappung, ✕) bleibt')
})
