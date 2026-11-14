/**
 * UI-R7 — Personen: „Daten anfragen“ (R-9, Manuel 11.11.).
 *
 * Regel: Alle sehen Vor- und Nachnamen aller Mitglieder. Weitere Daten nur,
 * wenn die Person sie freigegeben hat — sonst bietet die Zeile „Daten
 * anfragen“ an, und die Person bekommt eine Meldung zum Freigeben.
 *
 * Geprüft wird in drei Stufen:
 *   A) die reine Logik (`composables/datenAnfrage.mjs`) — läuft überall,
 *   B) die QUELLE der Bausteine (Zeile/Tabelle/Karte/Verwaltung) — ohne
 *      node_modules,
 *   C) das GERENDERTE DOM (mounten von Personen.vue, PersonenListe.vue und
 *      AppTopbar.vue mit @vue/compiler-sfc + jsdom), inklusive Klick auf
 *      „Daten anfragen“, Meldung im Glocken-Panel und Profil-Sprung.
 *      Fehlt `vue` lokal, wird C sauber übersprungen (wie in den bestehenden
 *      Mount-Tests).
 *
 * Läuft in der Node-Testliste: `tests/uir7-*.test.mjs` (frontend/tests/testliste.txt).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  ANFRAGBAR_FELD, ANGEFRAGT_TEXT, BEREITS, GESENDET, KNOPF_TEXT, NICHT_FREIGEGEBEN,
  NICHT_GESENDET, PROFIL_SICHTBARKEIT, anfrageHinweis, antwortText,
  bereichAusAdresse, fragendePerson, istAnfragbar, istDatenanfrage,
  ohneKontaktdaten, profilAdresse,
} from '../src/diakonos/composables/datenAnfrage.mjs'
import {
  AKTIONEN_SPALTE, freigabeSpalten, verwaltungSpalten,
} from '../src/diakonos/composables/personenVerwaltung.mjs'
import { zeileAusAdressbuch } from '../src/diakonos/composables/personenZeilen.mjs'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRC = path.join(FRONTEND, 'src')
const lies = (rel) => readFileSync(path.join(SRC, rel), 'utf8')
const QUELLE = {
  liste: lies('diakonos/components/personen/PersonenListe.vue'),
  personen: lies('diakonos/pages/Personen.vue'),
  topbar: lies('diakonos/components/AppTopbar.vue'),
  profil: lies('diakonos/pages/Profile.vue'),
}

// ═══ A) reine Logik ════════════════════════════════════════════════════════

test('UI-R7 A1: das Feld des Servers ist `daten_anfragbar`, fail closed', () => {
  assert.equal(ANFRAGBAR_FELD, 'daten_anfragbar')
  assert.equal(istAnfragbar({ daten_anfragbar: true }), true)
  assert.equal(istAnfragbar({ daten_anfragbar: false }), false)
  // Ohne Feld NICHT anfragbar — die Oberfläche rät nicht.
  assert.equal(istAnfragbar({}), false)
  assert.equal(istAnfragbar(null), false)
  // Nur der ausdrückliche Wahrheitswert zählt (kein „1“, kein „true“).
  assert.equal(istAnfragbar({ daten_anfragbar: 'true' }), false)
})

test('UI-R7 A2: die Zeile trägt `daten_anfragbar` aus der Antwort', () => {
  const zeile = zeileAusAdressbuch({
    name: 'M-1', vorname: 'Anna', nachname: 'Beispiel', daten_anfragbar: true,
  })
  assert.equal(zeile.datenAnfragbar, true)
  // Zeilen der Mitgliederliste (Admin) kennen das Feld nicht — false.
  const ohne = zeileAusAdressbuch({ name: 'M-2', vorname: 'B', nachname: 'C' })
  assert.equal(ohne.datenAnfragbar, false)
})

test('UI-R7 A3: „Kontaktdaten nicht freigegeben“ nur, wenn nichts da ist', () => {
  assert.equal(NICHT_FREIGEGEBEN, 'Kontaktdaten nicht freigegeben')
  // Nichts freigegeben (Server maskiert mit null) → eine Zeile statt „—“-Wüste.
  // Seit dem Review (Punkt 5) gilt das nur noch für Zeilen, die der Server als
  // anfragbar meldet — sonst unterstellte der Satz ein Verbergen.
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, email: null, telefonnummer: null, wohnort: null }), true)
  // Ein einziger sichtbarer Wert genügt — dann stehen die Felder normal da.
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, email: 'a@b.de', telefonnummer: null }), false)
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, telefonnummer: '07071 1' }), false)
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, wohnort: 'Tübingen' }), false)
  // Leere Texte zählen wie null (nichts zu sehen).
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, email: '', telefonnummer: '  ' }), true)
})

test('UI-R7b A3b: der freigegebene ORT zählt als sichtbarer Wert (Feldname `ort`)', () => {
  // Review UI-R7b, Punkt 6: Die Ansichtszeile (`personenZeilen.mjs`) trägt den
  // Ort als `ort` („72070 Tübingen“), NICHT als `wohnort`. Vorher prüfte nur
  // `wohnort` — ein freigegebener Ort galt damit als „nichts da“, und die Karte
  // zeigte „Kontaktdaten nicht freigegeben“ statt des Ortes.
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, email: null, telefonnummer: null, ort: '72070 Tübingen' }), false,
    'der Ort aus der Ansichtszeile ist ein sichtbarer Wert')
  assert.equal(ohneKontaktdaten({ datenAnfragbar: true, email: null, ort: 'Tübingen' }), false,
    'auch in der Zeilenform (`datenAnfragbar`)')
  // Die ROHE Serverzeile trägt weiter `wohnort` — beide Namen zählen.
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, wohnort: 'Tübingen' }), false)
  // Beides leer → der Satz steht da.
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, email: null, telefonnummer: null, ort: '', wohnort: ' ' }), true)
  // Der Weg von der Server-Antwort zur Zeile bleibt gedeckt (Feld `ort`).
  const zeile = zeileAusAdressbuch({
    name: 'M-1', vorname: 'Anna', nachname: 'Beispiel', postleitzahl: '72070',
    wohnort: 'Tübingen', email: null, telefonnummer: null, daten_anfragbar: true,
  })
  assert.equal(zeile.ort, '72070 Tübingen')
  assert.equal(ohneKontaktdaten(zeile), false,
    'die Zeile der Ansicht zeigt einen Ort — also NICHT „Kontaktdaten nicht freigegeben“')
})

test('UI-R7 A4: Antwort des Servers wird Klartext', () => {
  assert.deepEqual(antwortText({ success: true, gesendet: true }),
    { text: GESENDET, art: 'gesendet' })
  assert.deepEqual(antwortText({ success: true, gesendet: false, bereits: true }),
    { text: BEREITS, art: 'bereits' })
  // Angenommen, aber nichts verschickt (kein Konto): ehrlich sagen, was gilt.
  assert.deepEqual(antwortText({ success: true, gesendet: false }),
    { text: NICHT_GESENDET, art: 'nicht-gesendet' })
  // Keine Antwort (Test/Server-Stille) → wie „nicht gesendet“.
  assert.equal(antwortText(undefined).art, 'nicht-gesendet')
  // Die Texte behaupten keine Zahlen, die der Server nicht liefert.
  assert.ok(!/\d/.test(BEREITS), '„schon angefragt“ ohne erfundene Tage')
})

test('UI-R7 A5: Meldung „Datenanfrage“ — Typ, Fragende und Ziel', () => {
  const meldung = {
    type: 'Datenanfrage',
    subject: 'Samuel Fink möchte deine Kontaktdaten sehen',
    email_content: 'Samuel Fink bittet dich, deine Kontaktdaten im Adressbuch freizugeben.',
    document_type: 'Mitglied',
  }
  assert.equal(istDatenanfrage(meldung), true)
  assert.equal(istDatenanfrage({ type: 'Alert' }), false)
  assert.equal(fragendePerson(meldung), 'Samuel Fink')
  assert.match(anfrageHinweis(meldung), /^Samuel Fink möchte deine Kontaktdaten sehen\./)
  // Ohne Namen kein erfundener Name, aber der Hinweis bleibt verständlich.
  assert.equal(fragendePerson({ subject: 'Etwas anderes' }), '')
  assert.match(anfrageHinweis({ subject: 'Etwas anderes' }), /Jemand möchte deine Kontaktdaten sehen/)
})

test('UI-R7 A6: Adresse Profil → Sichtbarkeit (eine Schreibweise)', () => {
  // `#/profile` ist die Route der Seite (router.js, Seitenname `Profile`) —
  // `#/profil` gibt es nicht (der Router antwortet mit „Seite nicht gefunden“).
  assert.equal(profilAdresse(), '#/profile?bereich=sichtbarkeit')
  assert.equal(profilAdresse('sichtbarkeit'), '#/profile?bereich=sichtbarkeit')
  assert.equal(PROFIL_SICHTBARKEIT, '#/profile?bereich=sichtbarkeit')
  assert.equal(bereichAusAdresse('#/profile?bereich=sichtbarkeit'), 'sichtbarkeit')
  assert.equal(bereichAusAdresse('#/profile'), '')
  assert.equal(bereichAusAdresse('#/profile?bereich='), '')
  assert.equal(bereichAusAdresse(''), '')
})

// ═══ R) Review-Nacharbeit (Operator, Punkte 1–7) ═══════════════════════════

test('UI-R7 R1: Kopf und Zellen der Tabelle kommen aus EINER Spaltenliste', () => {
  // Review Punkt 1: Der Kopf hatte 4 Überschriften, die Zeile 5 Zellen —
  // „72070 Tübingen“ stand unter „Telefon“, der Knopf hatte gar keine
  // Überschrift. Jetzt steht die Reihenfolge in `personenVerwaltung.mjs`.
  const ohne = freigabeSpalten()
  assert.deepEqual(ohne.map((s) => s.key), ['name', 'email', 'telefon', 'ort'])
  const mit = freigabeSpalten({ anfrage: true })
  assert.deepEqual(mit.map((s) => s.key), ['name', 'email', 'telefon', 'ort', 'aktion'])
  // Die Aktionsspalte ist als solche gekennzeichnet (DkTable: Umbruch statt
  // Überlauf) und ihre Überschrift ist der Klartext für Vorlesehilfen.
  const aktion = mit.at(-1)
  assert.equal(aktion.aktion, true)
  assert.equal(aktion.label, AKTIONEN_SPALTE)
  assert.equal(AKTIONEN_SPALTE, 'Aktionen')
  // Die Verwaltungssicht bleibt, wie sie war (7 Spalten mit persönlichen Daten).
  assert.deepEqual(verwaltungSpalten({ persoenlich: true }).map((s) => s.key),
    ['name', 'status', 'gruppen', 'telefon', 'email', 'adresse', 'geburtstag', 'dabei'])
})

test('UI-R7 R2: „Kontaktdaten nicht freigegeben“ nur, wenn es etwas zu fragen gibt', () => {
  // Review Punkt 5: Wer alles freigegeben hat, aber nichts hinterlegt hat,
  // wurde als „nicht freigegeben“ beschriftet — und gelöschte Personen auch.
  const allesFreiAberLeer = { daten_anfragbar: false, email: null, telefonnummer: null, wohnort: null }
  assert.equal(ohneKontaktdaten(allesFreiAberLeer), false)
  const geloescht = { name: 'geloescht-1', daten_anfragbar: false, email: '', telefonnummer: '', wohnort: '' }
  assert.equal(ohneKontaktdaten(geloescht), false)
  // Nichts freigegeben UND anfragbar → der Satz steht da.
  assert.equal(ohneKontaktdaten({ daten_anfragbar: true, email: null, telefonnummer: null }), true)
  // Feldform der Ansicht zählt genauso (`datenAnfragbar`).
  assert.equal(ohneKontaktdaten({ datenAnfragbar: true, email: null }), true)
  assert.equal(ohneKontaktdaten({ datenAnfragbar: false, email: null }), false)
})

test('UI-R7 R3: „nicht zugestellt“ nennt keinen Grund, den der Server verschweigt', () => {
  // Review Punkt 4: „hat kein Konto für Meldungen“ war erfunden — der Server
  // verschweigt den Grund (ausgeschlossen, gesperrt, Zustellfehler …).
  assert.ok(!/Konto/i.test(NICHT_GESENDET), `kein Konto behauptet: ${NICHT_GESENDET}`)
  assert.ok(!/kein\b/i.test(NICHT_GESENDET), `keine Ursachen-Behauptung: ${NICHT_GESENDET}`)
  assert.match(NICHT_GESENDET, /nicht zugestellt werden/i)
  // Der Weg für den Menschen bleibt: selbst fragen.
  assert.match(NICHT_GESENDET, /direkt/i)
})

test('UI-R7 R4: „Angefragt“ ist ein eigener Zustand, kein zweiter Aufforderungstext', () => {
  assert.equal(ANGEFRAGT_TEXT, 'Angefragt')
  assert.notEqual(ANGEFRAGT_TEXT, KNOPF_TEXT)
})

test('UI-R7 R5: PersonenListe sperrt den Knopf nach angenommener Anfrage', () => {
  const q = QUELLE.liste
  // Es gibt einen gemerkten Zustand je Person (Set) …
  assert.ok(/ergangen/.test(q), 'die Liste merkt sich angefragte Personen')
  assert.ok(/ANGEFRAGT_TEXT/.test(q), 'die Beschriftung wechselt auf „Angefragt“')
  // … und `fertig(ok)` kommt von der Seite (Fehler gibt den Knopf wieder frei).
  assert.match(q, /fertig\(angenommen\)|fertig`?\(ok/,
    'Personen.vue meldet zurück, ob die Anfrage angenommen wurde')
  // Personen.vue gibt das Ergebnis weiter (Vorher: immer `fertig()`).
  assert.match(QUELLE.personen, /fertig\(angenommen\)/,
    'Personen.vue ruft `fertig` mit dem Ergebnis auf')
})

test('UI-R7 R6: Profile.vue meldet den hashchange-Listener wieder ab', () => {
  const q = QUELLE.profil
  // Review Punkt 6: eine benannte Referenz (sonst greift removeEventListener
  // nicht) und das Abmelden in onBeforeUnmount.
  assert.match(q, /onBeforeUnmount/, 'Profile.vue räumt beim Verlassen auf')
  assert.match(q, /removeEventListener\('hashchange'/, 'der Listener wird abgemeldet')
  assert.match(q, /addEventListener\('hashchange', amHashchange\)/,
    'angemeldet und abgemeldet mit DERSELBEN Referenz')
  // Bei fehlender Meldung bleibt der allgemeine Satz stehen (wie zugesagt).
  assert.match(q, /catch[\s\S]{0,400}anfrageHinweis\(null\)/,
    'im Fehlerfall steht der allgemeine Satz')
})

test('UI-R7 R7: dauerhaft sichtbarer Knopf, keine Zeiger-Abfrage im Stil', () => {
  // Nur der STIL-Teil zählt: Kommentare dürfen `(hover: none)` erwähnen
  // (sie erklären, warum es verboten ist) — ausgelieferter CSS-Code nie.
  const stil = QUELLE.liste.slice(QUELLE.liste.indexOf('<style'))
    .replace(/\/\*[\s\S]*?\*\//g, '')
  // UI-R7c, Punkt 2: `transition: opacity` animierte nichts mehr (der stille
  // Zustand ist weg) und ist samt `prefers-reduced-motion`-Sonderfall entfernt.
  assert.ok(!/transition:\s*opacity/.test(stil),
    'keine Bewegung mehr am Anfrage-Knopf (animiert nichts)')
  assert.ok(!/prefers-reduced-motion/.test(stil),
    'kein Bewegung-Sonderfall mehr für einen Knopf ohne Bewegung')
  // Nacharbeit Punkt 1 (Operator-Entscheidung): der stille Zustand ist GANZ
  // weg. `opacity: 0` bei `pointer-events: auto` war ein blinder Klick, und
  // „erst beim Überfahren sichtbar“ gibt es am Tablet nicht. Der Knopf ist
  // dauerhaft sichtbar; die SICHTBARKEIT selbst prüft das DOM (R7-DOM unten).
  assert.ok(!/pz-anfrage--still/.test(stil),
    'kein stiller Knopf-Zustand mehr (dauerhaft sichtbar)')
  assert.ok(!/dk-touch-offen/.test(QUELLE.liste),
    'die Tablet-Klasse ist entfernt (sie hing an der Zeiger-Messung)')
  assert.ok(!/\bopacity:\s*0\b/.test(stil),
    'kein unsichtbarer, aber klickbarer Knopf (blinder Klick, Punkt 1)')
  assert.ok(!/GROBER_ZEIGER_ABFRAGE/.test(QUELLE.liste),
    'die Zeigerart wird NICHT abgefragt (FIX-6c: nur istHandyLage)')
  assert.match(QUELLE.liste, /useHandyLage/, 'die Handy-Lage kommt aus der EINEN Quelle')
  // FIX-6: die Zeiger-ART bleibt in den Quellen verboten (`hover: none`,
  // `any-pointer`) — eigener Wächter: tests/fix6-*.test.mjs.
  assert.ok(!/\(hover:\s*none\)|any-pointer/.test(stil), 'keine verbotene Zeiger-Abfrage im CSS')
  assert.ok(!/\(hover:\s*none\)|any-pointer/.test(QUELLE.liste), 'auch nicht im Skript — FIX-6')
})

test('UI-R7c: Kontaktzellen schneiden ab, `title` trägt den vollen Wert', () => {
  const stil = QUELLE.liste.slice(QUELLE.liste.indexOf('<style'))
    .replace(/\/\*[\s\S]*?\*\//g, '')
  // Die Spalte schneidet ab — mit Aktionsspalte steht die Tabelle auf
  // `table-layout: fixed`, sonst schob sich die Adresse in die Nachbarspalte.
  assert.match(stil, /\.pz-zelle-kontakt\s*\{[^}]*overflow:\s*hidden/,
    'die Kontaktzelle schneidet ab')
  assert.match(stil, /text-overflow:\s*ellipsis/, 'der Wert bekommt eine Ellipse')
  assert.match(stil, /\.pz-zelle-kontakt[^{]*\{[^}]*white-space:\s*nowrap/,
    'der Wert bricht nicht um')
  // `title` = der VOLLE Wert (nicht mehr „E-Mail schreiben: Name“).
  assert.match(QUELLE.liste, /:title="z\.email"/, 'die E-Mail-Zelle trägt die volle Adresse als title')
  assert.match(QUELLE.liste, /:title="z\.telefonnummer"/, 'die Telefon-Zelle trägt die volle Nummer als title')
  assert.ok(!/'E-Mail schreiben: '\s*\+/.test(QUELLE.liste),
    'der alte Titel „E-Mail schreiben: Name“ ist weg')
  // Die Zelle steht inline in der Liste (kein eigener Baustein): `<td>` trägt
  // beide Klassen-Hälften, damit Spalten-Schlüssel und Stil greifen.
  assert.match(QUELLE.liste, /<td v-else-if="key === 'email'" class="pz-zelle-kontakt pz-zelle-email">/,
    'die E-Mail-Zelle steht inline mit beiden Spalten-Klassen')
})

test('UI-R7c: keine Reste im Stil (Stille-Klasse, Bewegung ohne Wirkung)', () => {
  // UI-R7c, Punkt 2: der Kommentar versprach eine „Stille-Klasse“, die es
  // nicht mehr gibt; die Bewegung animierte nichts (Zustand ist weg).
  assert.ok(!/Stille-Klasse/.test(QUELLE.liste), 'kein Verweis auf eine Stille-Klasse')
  assert.match(QUELLE.liste, /gesperrt wird er über `disabled`/,
    'der gesperrte Knopf ist als gesperrt beschrieben, nicht als „bedienbar“')
  assert.ok(!/sichtbar und bedienbar/.test(QUELLE.liste), 'die falsche Formulierung ist korrigiert')
})

// ═══ B) Quelle der Bausteine ═══════════════════════════════════════════════

test('UI-R7 B1: PersonenListe bietet „Daten anfragen“ je anfragbarer Zeile an', () => {
  const q = QUELLE.liste
  // Der Knopf hängt an `istAnfragbar` — nicht an einer eigenen Rechte-Annahme.
  assert.ok(/istAnfragbar/.test(q), 'PersonenListe.vue prüft `istAnfragbar`')
  assert.ok(q.includes('datenAnfrage'), 'PersonenListe.vue meldet die Anfrage nach oben')
  // EINE Beschriftung aus dem Modul (keine zweite Formulierung im Markup).
  assert.ok(/KNOPF_TEXT/.test(q), 'PersonenListe.vue nutzt die Beschriftung aus dem Modul')
  // Die Knöpfe stehen nur außerhalb der Zeilen-Verlinkung, sonst schluckt sie
  // der Profil-Link (Web-1-Muster: eigener Klick gewinnt über `.pz-zeilenziel`).
  assert.match(q, /@click\.stop/, 'der Knopf hält den Zeilenklick an')
})

test('UI-R7 B2: Desktop dauerhaft sichtbar, Handy im Zeilenmenü', () => {
  const q = QUELLE.liste
  // Nacharbeit Punkt 1 (Operator-Entscheidung): der Knopf ist außerhalb der
  // Handy-Lage DAUERHAFT sichtbar — kein `:hover`-Zustand mehr, weil ein
  // solcher Knopf am Tablet (kein Überfahren) gar nicht existiert und weil
  // `opacity: 0` + `pointer-events: auto` ein blinder Klick wäre.
  // Die SICHTBARKEIT selbst prüft R7-DOM im echten DOM (ohne Überfahren).
  assert.match(q, /class="pz-anfrage/, 'die Anfrage hat eine eigene Klasse')
  assert.ok(!/pz-anfrage--still/.test(q), 'kein stiller Knopf mehr')
  // Handy: eigenes Zeilenmenü (DkAktionen) statt „hover“.
  assert.ok(/DkAktionen/.test(q), 'Handy-Zeilenmenü ist DkAktionen')
  assert.ok(/handyLage|istHandyLage/.test(q), 'die Handy-Lage kommt aus istHandyLage')
  assert.ok(!/max-width:\s*720px\)\s*\{\s*\.pz-anfrage\s*\{\s*display:\s*none/.test(q),
    'der Knopf wird am Handy NICHT per CSS versteckt (er lebt im Menü)')
  // Sichtbarkeit NUR über opacity: `visibility: hidden`/`display: none` nehmen
  // den Knopf aus dem Tab-Strom — dann wäre er per Tastatur unerreichbar
  // (im Browser gemessen: der Fokus landete nie auf ihm).
  assert.ok(!/^\s*visibility:\s*hidden/m.test(q),
    'PersonenListe.vue versteckt den Anfrage-Knopf per visibility (unfokussierbar)')
  assert.ok(!/\.pz-anfrage\s*\{[^}]*display:\s*none/.test(q),
    'PersonenListe.vue versteckt den Anfrage-Knopf per display: none (unfokussierbar)')
})

test('UI-R7 B3: eine Zeile „Kontaktdaten nicht freigegeben“ statt „—“-Wüste', () => {
  const q = QUELLE.liste
  assert.ok(/NICHT_FREIGEGEBEN|ohneKontaktdaten/.test(q),
    'PersonenListe.vue nutzt die gemeinsame Regel')
  // Genau EINE Zeile — nicht je Feld eine.
  assert.ok((q.match(/NICHT_FREIGEGEBEN/g) || []).length >= 1)
})

test('UI-R7 B4: Personen reicht Antwort und Zurücksetzen an die Liste', () => {
  const q = QUELLE.personen
  assert.ok(/mitglieder\.daten_anfragen/.test(q), 'Personen.vue ruft `daten_anfragen` auf')
  assert.ok(/antwortText/.test(q), 'die Antwort wird über `antwortText` in Klartext übersetzt')
  assert.ok(/@daten-anfrage/.test(q), 'Personen.vue hört das Ereignis der Liste')
  // Serverfehler (403/417) als verständliche Meldung, nicht als Floskel.
  assert.ok(/aktionsfehler/.test(q), 'Fehler laufen über den Textkatalog')
})

test('UI-R7 B5: AppTopbar macht aus einer „Datenanfrage“ einen Weg ins Profil', () => {
  const q = QUELLE.topbar
  assert.ok(/istDatenanfrage/.test(q), 'die Glocke erkennt den Typ')
  assert.ok(/PROFIL_SICHTBARKEIT|profilAdresse/.test(q), 'das Ziel kommt aus dem Modul')
  // Ganze Zeile klickbar (K4) — und nur bei einer Datenanfrage.
  assert.match(q, /dk-notify-eintrag-knopf/, 'der Eintrag ist die Klickfläche (Knopf)')
})

test('UI-R7 B6: Profile.vue führt `?bereich=sichtbarkeit` zu den Schaltern', () => {
  const q = QUELLE.profil
  assert.ok(/bereichAusAdresse/.test(q), 'Profile.vue liest den Bereichs-Wunsch')
  assert.ok(/anfrageHinweis|datenAnfrage/.test(q), 'der Hinweis kommt aus dem Modul')
  assert.match(q, /anker="profil-sichtbarkeit"/, 'der Abschnitt trägt eine Sprungmarke')
  assert.match(q, /dk-sprung-profil-sichtbarkeit/,
    'der Sprung zielt auf die Kennung aus pages/sprung.mjs')
})

// ═══ C) gerendertes DOM ════════════════════════════════════════════════════

const VUE_DA = existsSync(path.join(FRONTEND, 'node_modules', 'vue'))
const JSDOM_DA = existsSync(path.join(FRONTEND, 'node_modules', 'jsdom'))

test('UI-R7 C: gerendertes DOM (vue + jsdom nötig)', { skip: !(VUE_DA && JSDOM_DA) }, async (t) => {
  const { mkdtempSync, writeFileSync, rmSync } = await import('node:fs')
  const { pathToFileURL } = await import('node:url')
  const { JSDOM } = await import('jsdom')
  const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://x/#/personen/liste' })
  for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'SVGElement',
    'MouseEvent', 'navigator', 'location', 'getComputedStyle', 'requestAnimationFrame',
    'cancelAnimationFrame', 'hashchange']) {
    try { globalThis[k] = dom.window[k] } catch { /* egal */ }
  }
  globalThis.requestAnimationFrame ||= (f) => setTimeout(f, 0)
  dom.window.addEventListener ||= dom.window.addEventListener.bind(dom.window)
  // `window` MUSS dieselbe Instanz sein: `useHandyLage` liest `window.matchMedia`
  // (die Handy-Lage-Regel der App), und der Stummel in C4 hängt an DIESEM Objekt.
  globalThis.window = dom.window

  const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
  const TMP = mkdtempSync(path.join(FRONTEND, '.zz-uir7-'))
  t.after(() => { try { rmSync(TMP, { recursive: true, force: true }) } catch { /* egal */ } })
  const VUE_URL = import.meta.resolve('vue')

  // ── Stummel: keine Servergespräche ───────────────────────────────────────
  const stubs = {}
  const stub = (rel, inhalt) => {
    const datei = path.join(TMP, rel.replace(/[/.]/g, '_') + '.mjs')
    writeFileSync(datei, inhalt)
    stubs[path.join(SRC, rel)] = datei
  }
  stub('diakonos/composables/useApi.js',
    `export async function apiCall(m, a){ return globalThis.__api(m, a) }
export async function apiGet(m, a){ return globalThis.__api(m, a) }
export const AuditConfirmationRequired = class extends Error {}
export default { apiCall, apiGet }`)
  stub('diakonos/composables/useSession.js',
    `import { computed } from '${VUE_URL}'
export function useSession(){ return { isAdmin: computed(() => globalThis.__isAdmin === true), istMitgliederverwaltung: computed(() => globalThis.__isAdmin === true) } }`)
  stub('diakonos/router.js',
    `export function navigate(h){ globalThis.__nav = h }
export const currentPageName = { value: 'Personen' }
export function setPage(){}`)
  stub('diakonos/composables/useToast.js',
    `export function showToast(text, art){ (globalThis.__toasts ||= []).push([text, art]) }`)
  stub('diakonos/composables/useVerwaltung.js',
    `import { ref } from '${VUE_URL}'
export const anfragenZaehler = ref(0)`)
  // Der Stummel ist ein MODUL (kein .vue-Quelltext): die Umschreibung schreibt
  // den Inhalt unverändert als .mjs — ein `<template>` darin wäre HTML im
  // JS-Modul („Unexpected token '<'“).
  stub('diakonos/components/WartendeKontenKarte.vue',
    `import { h } from '${VUE_URL}'
export default { name: 'WartendeKontenKarteStummel', render: () => h('div', { class: 'wartende-stub' }) }`)

  let n = 0
  const cache = new Map()

  function baue(abs) {
    if (stubs[abs]) return stubs[abs]
    if (cache.has(abs)) return cache.get(abs)
    const ziel = path.join(TMP, `m${n++}.mjs`)
    cache.set(abs, ziel)
    let code
    if (abs.endsWith('.vue')) {
      const datei = path.basename(abs)
      const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: datei })
      const s = compileScript(descriptor, { id: datei, inlineTemplate: false })
      const templ = compileTemplate({
        source: descriptor.template.content, filename: datei, id: datei,
        compilerOptions: { bindingMetadata: s.bindings },
      })
      code = s.content.replace(/\nexport default /, '\nconst __sfc__ = ')
        + '\n' + templ.code.replace(/^export function render/m, 'function render')
        + '\n__sfc__.render = render\nexport default __sfc__\n'
    } else {
      code = readFileSync(abs, 'utf8')
    }
    writeFileSync(ziel, code.replace(/(from\s+|import\s*\(\s*)(['"])([^'"]+)\2/g, (all, pre, q, spez) => {
      if (spez === 'vue') return `${pre}'${VUE_URL}'`
      if (!spez.startsWith('.')) return all
      return `${pre}'${pathToFileURL(baue(path.resolve(path.dirname(abs), spez))).href}'`
    }).replace(/^import\s+['"][^'"]+\.css['"];?$/gm, ''))
    return ziel
  }

  const Vue = await import('vue')
  const Personen = (await import(pathToFileURL(baue(path.join(SRC, 'diakonos/pages/Personen.vue'))).href)).default
  const tick = (ms = 0) => new Promise(r => setTimeout(r, ms))

  const fehler = []
  const pruefe = (bedingung, text) => { if (!bedingung) fehler.push(text) }

  /**
   * Adressbuch-Antwort wie der Server sie liefert (R-9). 25 Zeilen, weil die
   * Liste erst ab 20 Personen die TABELLE zeigt (Entwurf A3) — darunter sind
   * es Karten, und am Laptop gibt es dort keinen Zellknopf.
   */
  const adressbuch = [
    { name: 'M-Anna', vorname: 'Anna', nachname: 'Beispiel', email: null,
      telefonnummer: null, postleitzahl: null, wohnort: null, geburtstag: null,
      foto: '', daten_anfragbar: true },
    { name: 'M-Rebekka', vorname: 'Rebekka', nachname: 'Fink', email: 'rebekka@example.org',
      telefonnummer: '07071 2', postleitzahl: '72070', wohnort: 'Tübingen',
      geburtstag: '1980-01-02', foto: '', daten_anfragbar: false },
    ...Array.from({ length: 23 }, (_, i) => ({
      name: `M-${i + 3}`, vorname: `Vorname${i + 3}`, nachname: `Nachname${i + 3}`,
      email: null, telefonnummer: null, postleitzahl: null, wohnort: null,
      geburtstag: null, foto: '', daten_anfragbar: false,
    })),
  ]

  async function starte({ admin = false, breite = 1280, antwort = { success: true, gesendet: true }, adressbuch: zeilen = adressbuch } = {}) {
    const calls = []
    globalThis.__isAdmin = admin
    globalThis.__toasts = []
    globalThis.__nav = null
    dom.window.innerWidth = breite
    globalThis.innerWidth = breite
    try { dom.window.location.hash = '#/personen/liste' } catch { /* egal */ }
    globalThis.__api = async (modul, argumente) => {
      calls.push([String(modul).split('.').pop(), argumente || {}])
      const name = String(modul)
      if (name.endsWith('get_adressbuch')) return { data: zeilen }
      if (name.endsWith('daten_anfragen')) {
        if (antwort instanceof Error) throw antwort
        return antwort
      }
      if (name.endsWith('get_gruppen_page_data')) return { gruppen_auswahl: [] }
      return { data: [], total: 0, gesamt_alle: 0, status_zaehler: {} }
    }
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = Vue.createApp(Personen)
    const warns = []
    app.config.warnHandler = (m) => warns.push(String(m).slice(0, 160))
    const vm = app.mount(host)
    await tick(60)
    return { host, app, vm, calls, warns }
  }
  const aufraeumen = (ctx) => {
    try { ctx.app.unmount() } catch { /* egal */ }
    ctx.host.remove()
    // Handy-Lage-Stummel je Abschnitt zurücksetzen (sonst gälte er weiter).
    delete dom.window.matchMedia
  }
  const knopf = (root, text) => [...root.querySelectorAll('button')]
    .find(b => b.textContent.trim().includes(text))
  const zeile = (host, name) => host.querySelector(`[data-name="${name}"]`)
  /**
   * Die KARTE einer Person am Handy. `zeile()` liefert die Tabellenzeile — die
   * steht auch am Handy im DOM (CSS blendet sie nur aus), und in ihrer Zelle
   * sitzt kein „⋯“ (das Menü gehört zur Handy-Lage, nicht zur Tabelle).
   */
  const karte = (host, name) => host.querySelector(`li.pz-karte[data-name="${name}"]`)

  // ── C1: Desktop — Knopf je anfragbarer Zeile, „Kontaktdaten nicht freigegeben“
  {
    const ctx = await starte()
    const { host, warns } = ctx
    pruefe(warns.length === 0, `C1: Vue-Warnungen ${JSON.stringify(warns)}`)
    pruefe(Boolean(host.querySelector('.pz-tabelle')),
      `C1: 25 Personen → Tabelle (Entwurf A3, sonst steht kein Zellknopf da)`)

    const anna = zeile(host, 'M-Anna')
    pruefe(Boolean(anna), 'C1: Zeile der Person ohne Freigabe steht da')
    pruefe(Boolean(zeile(host, 'M-Rebekka')), 'C1: Zeile der Person MIT Freigabe steht da')
    // Person ohne Freigabe: der Knopf ist da, die Felder sind eine Zeile.
    const anfrage = anna && [...anna.querySelectorAll('button')]
      .find(b => b.textContent.includes(KNOPF_TEXT))
    pruefe(Boolean(anfrage), `C1: „${KNOPF_TEXT}“ steht in der Zeile ohne Freigabe`)
    pruefe(anna?.textContent.includes(NICHT_FREIGEGEBEN),
      `C1: „${NICHT_FREIGEGEBEN}“ statt „—“-Wüste (Text: ${anna?.textContent?.replace(/\s+/g, ' ')})`)
    // „—“ für die leeren Felder gibt es in DIESER Zeile nicht mehr.
    pruefe(!/–\s*–/.test(anna?.textContent || ''),
      `C1: keine Gedankenstrich-Kette (Text: ${anna?.textContent?.replace(/\s+/g, ' ')})`)
    // Person MIT Freigabe: kein Anfrage-Knopf (dort ist nichts zu fragen).
    const rebekka = zeile(host, 'M-Rebekka')
    pruefe(![...(rebekka?.querySelectorAll('button') || [])]
      .some(b => b.textContent.includes(KNOPF_TEXT)),
      'C1: keine Anfrage bei einer Person, die freigegeben hat')
    pruefe(rebekka?.textContent.includes('rebekka@example.org'),
      'C1: freigegebene Daten stehen normal in der Zeile')

    // ── Klick: Anfrage geht an den Server, Antwort wird Klartext
    anfrage?.click()
    await tick(40)
    const aufruf = ctx.calls.find(c => c[0] === 'daten_anfragen')
    pruefe(Boolean(aufruf), `C1: der Klick ruft daten_anfragen (Aufrufe: ${JSON.stringify(ctx.calls.map(c => c[0]))})`)
    pruefe(aufruf?.[1]?.mitglied === 'M-Anna',
      `C1: angefragt wird die geklickte Person (war ${JSON.stringify(aufruf?.[1])})`)
    const toast = (globalThis.__toasts || []).at(-1)
    pruefe(toast?.[0] === GESENDET, `C1: „Anfrage gesendet“ als Rückmeldung (war ${JSON.stringify(toast)})`)
    aufraeumen(ctx)
  }

  // ── C2: zweite Anfrage innerhalb der Woche → „Du hast schon angefragt“
  {
    const ctx = await starte({ antwort: { success: true, gesendet: false, bereits: true } })
    const anfrage = [...zeile(ctx.host, 'M-Anna').querySelectorAll('button')]
      .find(b => b.textContent.includes(KNOPF_TEXT))
    anfrage?.click()
    await tick(40)
    const toast = (globalThis.__toasts || []).at(-1)
    pruefe(toast?.[0] === BEREITS, `C2: „Du hast schon angefragt“ (war ${JSON.stringify(toast)})`)
    aufraeumen(ctx)
  }

  // ── C3: Server verweigert (403) → verständliche Meldung, kein Absturz
  {
    const ctx = await starte({
      antwort: Object.assign(new Error('Kein Zugriff'), { status: 403, exc_type: 'PermissionError' }),
    })
    const anfrage = [...zeile(ctx.host, 'M-Anna').querySelectorAll('button')]
      .find(b => b.textContent.includes(KNOPF_TEXT))
    anfrage?.click()
    await tick(60)
    const toast = (globalThis.__toasts || []).at(-1)
    pruefe(Boolean(toast) && toast[1] === 'error', `C3: Fehler wird als Fehler gemeldet (war ${JSON.stringify(toast)})`)
    pruefe(Boolean(toast?.[0]) && !/undefined|\[object/i.test(toast[0]),
      `C3: der Fehlertext ist Klartext (war ${JSON.stringify(toast?.[0])})`)
    pruefe(Boolean(zeile(ctx.host, 'M-Anna')), 'C3: die Liste bleibt stehen')
    aufraeumen(ctx)
  }

  // ── C4: Handy (390 px) — die Anfrage steht im Zeilenmenü, nicht als Knopf
  {
    // 390 px UND grober Zeiger = Handy-Lage (die EINE Regel aus
    // `handyLage.mjs`; jsdom kennt `matchMedia` nicht, deshalb hier gesetzt).
    dom.window.matchMedia = (abfrage) => ({
      matches: /pointer:\s*coarse/.test(String(abfrage)),
      media: String(abfrage), addEventListener() {}, removeEventListener() {},
    })
    const ctx = await starte({ breite: 390 })
    const anna = karte(ctx.host, 'M-Anna')
    pruefe(Boolean(anna?.querySelector('.dk-ui-aktionen-ausloeser')),
      `C4: die Zeile hat am Handy ein „⋯“-Menü (Zeile: ${anna?.textContent?.replace(/\s+/g, ' ').slice(0, 160)})`)
    const ausloeser = anna?.querySelector('.dk-ui-aktionen-ausloeser')
    ausloeser?.click()
    await tick(60)
    const menue = document.querySelector('.dk-ui-aktionen-menue')
    pruefe(Boolean(menue), 'C4: das Menü öffnet am Handy')
    const eintrag = menue && [...menue.querySelectorAll('button')]
      .find(b => b.textContent.includes(KNOPF_TEXT))
    pruefe(Boolean(eintrag), `C4: „${KNOPF_TEXT}“ steht im Zeilenmenü (Einträge: ${menue?.textContent?.trim()})`)
    eintrag?.click()
    await tick(60)
    pruefe(Boolean(ctx.calls.find(c => c[0] === 'daten_anfragen')),
      'C4: der Menüeintrag fragt an')
    const toast = (globalThis.__toasts || []).at(-1)
    pruefe(toast?.[0] === GESENDET, `C4: Rückmeldung wie am Laptop (war ${JSON.stringify(toast)})`)
    aufraeumen(ctx)
  }

  // ── C5: am Laptop KEIN Zeilenmenü (DEV-B6: Handy-Lage nur via istHandyLage)
  {
    const ctx = await starte({ breite: 1440 })
    pruefe(!karte(ctx.host, 'M-Anna')?.querySelector('.dk-ui-aktionen-ausloeser'),
      'C5: am Laptop steht kein Handy-Menü in der Zeile')
    aufraeumen(ctx)
  }

  /** Zellen einer Zeile in der Reihenfolge des DOM, colspan eingerechnet. */
  const zellen = (tr) => [...(tr?.children || [])]
    .map((el) => (el.tagName === 'TD' ? el : el.querySelector?.(':scope > td')))
    .filter(Boolean)
    .flatMap((td) => Array.from({ length: Number(td.getAttribute('colspan') || 1) }, () => td))
  const kopf = (host) => [...host.querySelectorAll('.dk-ui-table thead th')]

  // ── C6 (Review 1): Kopf und JEDE Zeile haben dieselbe Spaltenzahl
  {
    const ctx = await starte({ breite: 1440 })
    const koepfe = kopf(ctx.host)
    pruefe(koepfe.length === 5,
      `C6: Kopf hat 5 Spalten Name/E-Mail/Telefon/Ort/Aktionen (war ${koepfe.map(t => t.textContent.trim()).join('|')})`)
    pruefe(koepfe.at(-1)?.textContent.trim() === AKTIONEN_SPALTE,
      `C6: die Knopfspalte hat eine Überschrift (war „${koepfe.at(-1)?.textContent.trim()}“)`)
    pruefe(koepfe[2]?.textContent.trim() === 'Telefon', 'C6: dritte Überschrift ist „Telefon“')
    let alleGleich = true
    for (const tr of ctx.host.querySelectorAll('tr.pz-zeile')) {
      const n = zellen(tr).length
      if (n !== koepfe.length) {
        alleGleich = false
        fehler.push(`C6: Zeile ${tr.dataset.name} hat ${n} Zellen, Kopf ${koepfe.length}`)
      }
    }
    pruefe(alleGleich, 'C6: jede Zeile hat so viele Zellen wie der Kopf')
    // Der Ort steht in der ORT-Spalte (nicht unter „Telefon“).
    const rebekka = zellen(zeile(ctx.host, 'M-Rebekka'))
    pruefe(rebekka[2]?.textContent.trim() === '07071 2',
      `C6: Telefonspalte trägt die Nummer (war „${rebekka[2]?.textContent.trim()}“)`)
    pruefe(rebekka[3]?.textContent.trim() === '72070 Tübingen',
      `C6: Ortsspalte trägt den Ort (war „${rebekka[3]?.textContent.trim()}“)`)
    aufraeumen(ctx)
  }

  // ── C7 (Review 2): Kartenansicht am Laptop hat den Knopf
  {
    // Unter 20 Personen → Karten (Entwurf A3), KEINE Handy-Lage (Maus, breit).
    const ctx = await starte({ breite: 1280, adressbuch: adressbuch.slice(0, 3) })
    const anna = karte(ctx.host, 'M-Anna')
    const knopfInKarte = anna && [...anna.querySelectorAll('button')]
      .find(b => b.textContent.trim() === KNOPF_TEXT)
    pruefe(Boolean(knopfInKarte),
      `C7: die Karte trägt „${KNOPF_TEXT}“ (Karte: ${anna?.textContent?.replace(/\\s+/g, ' ').slice(0, 160)})`)
    // … und er ist nicht für das Auge versteckt (keine Stille-Klasse).
    pruefe(knopfInKarte && !knopfInKarte.classList.contains('pz-anfrage--still'),
      'C7: der Knopf der Karte ist sichtbar, nicht „still“')
    knopfInKarte?.click()
    await tick(40)
    pruefe(Boolean(ctx.calls.find(c => c[0] === 'daten_anfragen')),
      'C7: der Kartenknopf fragt an')
    // Person MIT Freigabe: KEIN Knopf (Review UI-R7b, Punkt 5 — dieselbe
    // Regel wie in der Tabelle: keine anfragbare Person, kein Knopf). Vorher
    // stand hier ein gesperrter Knopf mit falschem Tooltip und `aria-hidden`.
    const rebekka = karte(ctx.host, 'M-Rebekka')
    const gesperrt = rebekka && [...rebekka.querySelectorAll('button')]
      .find(b => b.textContent.trim() === KNOPF_TEXT)
    pruefe(!gesperrt,
      `C7: bei Freigabe steht KEIN Anfrage-Knopf in der Karte (war „${gesperrt?.textContent?.trim()}“)`)
    pruefe(!/Die Person hat ihre Kontaktdaten freigegeben/.test(rebekka?.innerHTML || ''),
      'C7: der falsche Tooltip ist weg')
    aufraeumen(ctx)
  }

  // ── C8 (Review 3): nach der Anfrage steht „Angefragt“ und der Knopf ist zu
  {
    const ctx = await starte({ breite: 1440 })
    const anna = () => zeile(ctx.host, 'M-Anna')
    const knopfJetzt = () => [...anna().querySelectorAll('button')]
      .find(b => /Angefragt|Daten anfragen/.test(b.textContent))
    knopfJetzt()?.click()
    await tick(60)
    const danach = knopfJetzt()
    pruefe(danach?.textContent.trim() === ANGEFRAGT_TEXT,
      `C8: Beschriftung wechselt auf „${ANGEFRAGT_TEXT}“ (war „${danach?.textContent.trim()}“)`)
    pruefe(danach?.disabled === true, 'C8: der Knopf ist nach der Anfrage gesperrt')
    // Ein weiterer Klick darf KEINE zweite Anfrage schicken.
    const vorher = ctx.calls.filter(c => c[0] === 'daten_anfragen').length
    danach?.click()
    await tick(40)
    const nachher = ctx.calls.filter(c => c[0] === 'daten_anfragen').length
    pruefe(nachher === vorher, `C8: kein zweiter Serveraufruf (vorher ${vorher}, nachher ${nachher})`)
    aufraeumen(ctx)
  }

  // ── C9 (Review 3): auch bei „bereits“ bleibt der Knopf gesperrt
  {
    const ctx = await starte({ breite: 1440, antwort: { success: true, gesendet: false, bereits: true } })
    const knopf = () => [...zeile(ctx.host, 'M-Anna').querySelectorAll('button')]
      .find(b => /Angefragt|Daten anfragen/.test(b.textContent))
    knopf()?.click()
    await tick(60)
    pruefe(knopf()?.textContent.trim() === ANGEFRAGT_TEXT,
      `C9: „schon angefragt“ setzt denselben Zustand (war „${knopf()?.textContent.trim()}“)`)
    aufraeumen(ctx)
  }

  // ── C10 (Review 3): nach einem FEHLER bleibt der Knopf benutzbar
  {
    const ctx = await starte({
      breite: 1440,
      antwort: Object.assign(new Error('Kein Zugriff'), { status: 403, exc_type: 'PermissionError' }),
    })
    const knopf = () => [...zeile(ctx.host, 'M-Anna').querySelectorAll('button')]
      .find(b => /Angefragt|Daten anfragen/.test(b.textContent))
    knopf()?.click()
    await tick(80)
    pruefe(knopf()?.textContent.trim() === KNOPF_TEXT,
      `C10: nach einem Fehler steht wieder „${KNOPF_TEXT}“ (war „${knopf()?.textContent.trim()}“)`)
    pruefe(knopf()?.disabled === false, 'C10: nach einem Fehler ist der Knopf wieder frei')
    aufraeumen(ctx)
  }

  // ── C11 (UI-R7b, Punkt 3): Kopf und Zeilen aus DERSELBEN Bedingung
  //   Fall A — jemand ist anfragbar: fünf Überschriften und fünf Zellen.
  //   Fall B — niemand ist anfragbar: vier Überschriften, KEINE Aktionsspalte,
  //   und die Zeilen haben ebenfalls vier Zellen. Vorher stand der Kopf an
  //   `fragenMoeglich`, die Zelle aber an `!zeilenMenue` — die Zeile hatte eine
  //   leere Zelle zuviel.
  {
    const ctx = await starte({ breite: 1440 })
    const koepfe = kopf(ctx.host)
    pruefe(koepfe.length === 5, `C11a: 5 Überschriften (war ${koepfe.length})`)
    for (const tr of ctx.host.querySelectorAll('tr.pz-zeile')) {
      pruefe(zellen(tr).length === koepfe.length,
        `C11a: Zeile ${tr.dataset.name} hat ${zellen(tr).length} Zellen, Kopf ${koepfe.length}`)
    }
    aufraeumen(ctx)
  }
  {
    // KEINE anfragbare Person: `daten_anfragbar: false` in allen Zeilen.
    const niemand = adressbuch.map((z) => ({ ...z, daten_anfragbar: false }))
    const ctx = await starte({ breite: 1440, adressbuch: niemand })
    const koepfe = kopf(ctx.host)
    pruefe(koepfe.length === 4,
      `C11b: ohne anfragbare Person 4 Überschriften, KEINE Aktionsspalte (war ${koepfe.map(t => t.textContent.trim()).join('|')})`)
    pruefe(!koepfe.some((t) => t.textContent.trim() === AKTIONEN_SPALTE),
      'C11b: die Überschrift „Aktionen“ fehlt, wenn niemand anfragbar ist')
    for (const tr of ctx.host.querySelectorAll('tr.pz-zeile')) {
      pruefe(zellen(tr).length === koepfe.length,
        `C11b: Zeile ${tr.dataset.name} hat ${zellen(tr).length} Zellen, Kopf ${koepfe.length}`)
      pruefe(!tr.querySelector('.pz-zelle-anfrage'),
        `C11b: Zeile ${tr.dataset.name} hat keine leere Aktionszelle`)
    }
    aufraeumen(ctx)
  }

  // ── C12 (UI-R7b, Punkt 5): NICHT anfragbare Karten ohne Knopf
  {
    // Unter 20 Personen → Karten, Desktop-Breite (keine Handy-Lage).
    const ctx = await starte({ breite: 1280, adressbuch: adressbuch.slice(0, 3) })
    for (const name of ['M-Rebekka', 'M-3']) {
      const k = karte(ctx.host, name)
      const knopfInKarte = k && [...k.querySelectorAll('button')]
        .find(b => b.textContent.trim() === KNOPF_TEXT)
      pruefe(!knopfInKarte, `C12: Karte ${name} (nicht anfragbar) hat KEINEN Anfrage-Knopf`)
    }
    const anna = karte(ctx.host, 'M-Anna')
    pruefe(Boolean(anna && [...anna.querySelectorAll('button')]
      .find(b => b.textContent.trim() === KNOPF_TEXT)),
      'C12: die anfragbare Karte behält ihren Knopf')
    aufraeumen(ctx)
  }

  // ── C13 (UI-R7b, Punkt 4): Handy QUER (844 px, Handy-Lage) → Tabelle MIT
  //   Aktionszelle, Inhalt das ⋯-Menü. Vorher entfiel die Zelle wegen
  //   `zeilenMenue` und das Menü steckte nur in den versteckten Karten:
  //   0 sichtbare Knöpfe.
  {
    // 844 px breit, flaches Fenster (390 hoch) + grober Zeiger = Handy-Lage
    // über die ZWEITE Alternative der einen Regel (Querformat, OP-HANDY-10).
    dom.window.matchMedia = (abfrage) => ({
      matches: /pointer:\s*coarse/.test(String(abfrage)) && String(abfrage).includes('orientation: landscape'),
      media: String(abfrage), addEventListener() {}, removeEventListener() {},
    })
    dom.window.innerHeight = 390
    const ctx = await starte({ breite: 844 })
    const koepfe = kopf(ctx.host)
    pruefe(koepfe.length === 5,
      `C13: Handy quer hat die Aktionsspalte im Kopf (war ${koepfe.map(t => t.textContent.trim()).join('|')})`)
    const tr = zeile(ctx.host, 'M-Anna')
    pruefe(Boolean(tr), 'C13: die Tabellenzeile steht da')
    const zelleAnfrage = tr?.querySelector('.pz-zelle-anfrage')
    pruefe(Boolean(zelleAnfrage), 'C13: die Tabellenzeile hat eine Aktionszelle (nicht mehr leer)')
    pruefe(Boolean(zelleAnfrage?.querySelector('.dk-ui-aktionen-ausloeser')),
      `C13: in der Handy-Lage steht das ⋯-Menü IN der Tabelle (Zelle: ${zelleAnfrage?.innerHTML?.replace(/\s+/g, ' ').slice(0, 120)})`)
    // Das Menü ist bedienbar: es öffnet und der Eintrag fragt an.
    zelleAnfrage?.querySelector('.dk-ui-aktionen-ausloeser')?.click()
    await tick(60)
    const menue = document.querySelector('.dk-ui-aktionen-menue')
    pruefe(Boolean(menue), 'C13: das Menü der Tabelle öffnet')
    const eintrag = menue && [...menue.querySelectorAll('button')]
      .find(b => b.textContent.includes(KNOPF_TEXT))
    pruefe(Boolean(eintrag), `C13: der Eintrag „${KNOPF_TEXT}“ steht im Menü`)
    eintrag?.click()
    await tick(60)
    pruefe(Boolean(ctx.calls.find(c => c[0] === 'daten_anfragen')),
      'C13: der Menüeintrag der Tabelle fragt an')
    delete dom.window.innerHeight
    aufraeumen(ctx)
  }

  // ── C14 (UI-R7b, Punkt 7): „nicht zugestellt“ sperrt NICHT als „Angefragt“
  {
    const ctx = await starte({ breite: 1440, antwort: { success: true, gesendet: false } })
    const knopf = () => [...zeile(ctx.host, 'M-Anna').querySelectorAll('button')]
      .find(b => /Angefragt|Daten anfragen/.test(b.textContent))
    knopf()?.click()
    await tick(60)
    const toast = (globalThis.__toasts || []).at(-1)
    pruefe(toast?.[0] === NICHT_GESENDET,
      `C14: der Toast sagt „nicht zugestellt“ (war ${JSON.stringify(toast)})`)
    pruefe(knopf()?.textContent.trim() === KNOPF_TEXT,
      `C14: der Knopf bleibt bei „${KNOPF_TEXT}“ (widerspricht dem Toast nicht) — war „${knopf()?.textContent.trim()}“`)
    pruefe(knopf()?.disabled === false, 'C14: und er bleibt bedienbar')
    aufraeumen(ctx)
  }

  // ── R7-DOM (Nacharbeit Punkt 1): der Knopf ist OHNE Überfahren sichtbar,
  //   und es gibt keinen unsichtbaren, aber klickbaren Zustand.
  //   Gemessen wird am gerenderten Element: keine Stille-Klasse, kein
  //   Inline-`opacity`, kein `dk-touch-offen` am Flächen-Container. Die
  //   Zeigerart wird dabei NICHT abgefragt (kein `matchMedia`-Stummel).
  {
    const ctx = await starte({ breite: 1440 })
    const anna = zeile(ctx.host, 'M-Anna')
    const knopfCelle = anna && [...anna.querySelectorAll('button')]
      .find(b => b.textContent.includes(KNOPF_TEXT))
    pruefe(Boolean(knopfCelle), `R7-DOM: der Knopf steht in der Zeile ohne Freigabe`)
    pruefe(knopfCelle && !knopfCelle.classList.contains('pz-anfrage--still'),
      'R7-DOM: der Knopf ist NICHT still — sichtbar ohne Überfahren')
    pruefe(knopfCelle && !/opacity/i.test(knopfCelle.getAttribute('style') || ''),
      'R7-DOM: kein unsichtbarer, aber klickbarer Zustand am Knopf')
    const flaeche = ctx.host.querySelector('.pz-flaeche')
    pruefe(!flaeche?.classList.contains('dk-touch-offen'),
      'R7-DOM: keine Zeiger-Klasse an der Fläche (FIX-6c)')
    // Karte (unter 20 Personen, Desktop) genauso: sichtbar, ohne Überfahren.
    aufraeumen(ctx)

    const klein = await starte({ breite: 1280, adressbuch: adressbuch.slice(0, 3) })
    const annaKarte = karte(klein.host, 'M-Anna')
    const knopfKarte = annaKarte && [...annaKarte.querySelectorAll('button')]
      .find(b => b.textContent.trim() === KNOPF_TEXT)
    pruefe(Boolean(knopfKarte), 'R7-DOM: der Kartenknopf steht da')
    pruefe(knopfKarte && !knopfKarte.classList.contains('pz-anfrage--still'),
      'R7-DOM: auch der Kartenknopf ist dauerhaft sichtbar')
    const karteFlaeche = klein.host.querySelector('.pz-flaeche')
    pruefe(!karteFlaeche?.classList.contains('dk-touch-offen'),
      'R7-DOM: auch die Kartenansicht trägt keine Zeiger-Klasse')
    aufraeumen(klein)
  }

  // ── C15 (UI-R7c, Punkt 1): KEIN Überlauf der E-Mail in die Telefon-Spalte
  //   Eine lange Adresse (≥ 35 Zeichen) steht in der Zelle, die Zelle trägt
  //   die Überlauf-Klasse, und der Link trägt den vollen Wert als `title`.
  //   Das Aussehen misst der Beleg im echten Browser (kein Layout in jsdom);
  //   hier zählt das DOM: Klasse + vollständiger `title`.
  {
    const lang = 'rebekka.langefamilienname@beispiel-gemeinde.example.org'
    const zeilen = adressbuch.map((z) => (z.name === 'M-Rebekka'
      ? { ...z, email: lang, daten_anfragbar: false }
      : z))
    const ctx = await starte({ breite: 1440, adressbuch: zeilen })
    const zeilenR = zellen(zeile(ctx.host, 'M-Rebekka'))
    const emailZelle = zeilenR[1]
    pruefe(Boolean(emailZelle?.classList.contains('pz-zelle-kontakt')),
      `C15: die E-Mail-Zelle trägt die Überlauf-Klasse (Klassen: ${emailZelle?.className})`)
    const link = emailZelle?.querySelector('a.pz-kontakt')
    pruefe(link?.getAttribute('title') === lang,
      `C15: der title trägt die VOLLE Adresse (war „${link?.getAttribute('title')}“)`)
    pruefe(link?.textContent.trim() === lang, 'C15: der Inhalt bleibt die volle Adresse (CSS kürzt)')
    const tel = zeilenR[2]?.querySelector('a.pz-kontakt')
    pruefe(tel?.getAttribute('title') === '07071 2',
      `C15: auch die Telefon-Zelle nennt den vollen Wert (war „${tel?.getAttribute('title')}“)`)
    // Der zugängliche Name des ZIELS bleibt: der Link ist per Text benannt,
    // das Profil-Ziel trägt seinen aria-label unverändert.
    pruefe(zeile(ctx.host, 'M-Rebekka')?.querySelector('.pz-zeilenziel')
      ?.getAttribute('aria-label') === 'Rebekka Fink öffnen',
      'C15: der Name für die Vorlesehilfe am Zeilen-Ziel bleibt')
    aufraeumen(ctx)
  }

  if (fehler.length) assert.fail('UI-R7 C:\n- ' + fehler.join('\n- '))
})
