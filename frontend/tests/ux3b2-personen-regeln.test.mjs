import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * UX3b2 — Personen: Admin-Funktionen zurück, Blättern, Rest (Review UX3b).
 *
 * Die Befunde dieser Karte, als Regeln am ECHTEN Code:
 *  1. Die Liste hat die Verwaltungsfunktionen der früheren Mitgliederseite
 *     wieder: Statusfilter, „persönliche Daten zeigen“, Status-/Gruppen-
 *     spalten, Sortierung, Karten/Tabelle, wartende Konten — und sie fordert
 *     persönliche Daten erst auf ausdrückliche Anforderung an.
 *  2. Die Form der Liste hängt an der GESAMTZAHL, nicht an der aktuellen
 *     Seite: die letzte, kurze Seite schaltete sonst auf Karten und die
 *     Fußzeile („Zurück“/„Weiter“) verschwand.
 *  3. Die Fußzeile steht AUSSERHALB der Tabelle — sie war am Handy
 *     (< 720 px, Tabelle ausgeblendet) nicht erreichbar.
 *  4. Das Adressbuch hat kein serverseitiges Blättern: keine erfundene
 *     Seitenzahl, keine wirkungslosen Knöpfe.
 *  5. Ein Profil-Link entsteht nur, wo `darfProfilLink` ihn erlaubt
 *     (gelöschte Person, DSGVO-2d).
 *  6. Die alten Adressbuch-Adressen leiten dauerhaft auf die Liste; der
 *     Fehlerzustand ist gestaltet (DkEmpty + „Erneut versuchen“).
 *  7. Die Schrift-Regeln der UX1b (Gewichte/Tabellenziffern aus Tokens).
 *
 * Lauf: node --test tests/ux3b2-personen-regeln.test.mjs   (cwd = frontend/)
 */

const dateiUrl = (relativ) => new URL(relativ, import.meta.url).href
const V = await import(dateiUrl('../src/diakonos/composables/personenVerwaltung.mjs'))
const Z = await import(dateiUrl('../src/diakonos/composables/personenZeilen.mjs'))

const seite = readFileSync(new URL('../src/diakonos/pages/Personen.vue', import.meta.url), 'utf8')
const liste = readFileSync(
  new URL('../src/diakonos/components/personen/PersonenListe.vue', import.meta.url), 'utf8')
const router = readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')

// ── 1. Verwaltungsrecht: nur ein echtes true (fail closed) ─────────────────
{
  assert.equal(V.verwaltungSichtbar(true), true)
  for (const wert of [undefined, null, 0, '', 'true', 1, {}]) {
    assert.equal(V.verwaltungSichtbar(wert), false,
      `verwaltungSichtbar(${JSON.stringify(wert)}) muss fail-closed false sein`)
  }
}

// ── 2. Persönliche Daten: nur Verwaltung MIT Schalter ─────────────────────
{
  assert.equal(V.persoenlicheDatenAnfordern(true, true), true)
  for (const [admin, schalter] of [[true, false], [true, undefined], [true, 'true'],
    [false, true], [undefined, true], [null, true], ['true', true]]) {
    assert.equal(V.persoenlicheDatenAnfordern(admin, schalter), false,
      `persoenlicheDatenAnfordern(${JSON.stringify(admin)}, ${JSON.stringify(schalter)}) muss false sein`)
  }
  assert.equal(V.datenschalterText(false), 'Persönliche Daten anzeigen')
  assert.equal(V.datenschalterText(true), 'Persönliche Daten verbergen')
}

// ── 3. Statusfilter: echte Status, „Alle“, keine erfundene Null ────────────
{
  const optionen = V.statusFilterOptionen({
    statusZaehler: { Mitglied: 42, Gast: 0, Ausgetreten: 3 },
    gesamtAlle: 45,
  })
  assert.equal(optionen[0].value, '', 'die erste Wahl ist „Alle“')
  assert.equal(optionen[0].label, 'Alle 45')
  assert.equal(optionen[1].label, 'Mitglied 42')
  assert.ok(!optionen.some(o => o.value === 'geloescht'),
    'der Endstatus „geloescht“ erscheint nur, wenn es solche Zeilen gibt')
  const werte = optionen.map(o => o.value).filter(Boolean)
  for (const status of ['Mitglied', 'Gast', 'Passives Mitglied', 'Passiver Gast', 'Ausgetreten']) {
    assert.ok(werte.includes(status), `Statusfilter kennt „${status}“`)
  }
  // Ohne Serverzahl kein „0“: eine unbekannte Zahl wird nicht behauptet.
  const ohne = V.statusFilterOptionen({})
  assert.equal(ohne[0].label, 'Alle')
  assert.ok(ohne.every(o => !/\d/.test(o.label)), 'ohne Serverzahlen stehen keine Zahlen da')
  // Löschungen: Chip ja, aber mit Anzeigewort statt Speicherwert.
  const mitLoeschung = V.statusFilterOptionen({ statusZaehler: { geloescht: 2 }, gesamtAlle: 2 })
  assert.equal(mitLoeschung.at(-1).label, 'Gelöschte Person 2',
    'der Speicherwert „geloescht“ erscheint nie als Wort')
}

// ── 4. Statussprache: ein Begriff je Konzept ───────────────────────────────
{
  assert.equal(V.statusWort('geloescht'), 'Gelöschte Person')
  assert.equal(V.statusWort('Mitglied'), 'Mitglied')
  assert.equal(V.statusWort(''), 'Unbekannt')
  assert.equal(V.statusVariante('geloescht'), 'neutral', 'Löschung ist kein Fehler')
  assert.equal(V.statusVariante('Ausgetreten'), 'err')
  assert.equal(V.statusVariante('Mitglied'), 'ok')
  assert.equal(V.statusVariante('Gast'), 'warn')
}

// ── 5. Sortierung ──────────────────────────────────────────────────────────
{
  assert.equal(V.naechsteSortierung('asc'), 'desc')
  assert.equal(V.naechsteSortierung('desc'), 'asc')
  // Unbekanntes wird wie die Vorgabe „aufsteigend“ behandelt (der Server
  // setzt ebenfalls nur bei 'desc' absteigend).
  assert.equal(V.naechsteSortierung(undefined), 'desc', 'ohne Wert gilt aufsteigend → Schalter ergibt absteigend')
  assert.equal(V.naechsteSortierung('asc'), 'desc')
  assert.equal(V.sortierBeschriftung('asc'), 'A–Z')
  assert.equal(V.sortierBeschriftung('desc'), 'Z–A')
}

// ── 6. BEFUND 2: Form nach GESAMTZAHL, nicht nach der Seite ────────────────
{
  // Letzte Seite einer großen Liste mit 2 Zeilen: die Ansicht bleibt Tabelle.
  assert.equal(V.listenFormFuer({ gesamt: 42 }), 'tabelle',
    '42 Personen → Tabelle, auch wenn die letzte Seite nur 2 Zeilen hat')
  assert.equal(V.listenFormFuer({ gesamt: 3 }), 'karten')
  assert.equal(V.listenFormFuer({ gesamt: 20 }), 'tabelle')
  assert.equal(V.listenFormFuer({ gesamt: 19 }), 'karten')
  assert.equal(V.listenFormFuer({ gesamt: undefined }), 'karten')
  // Die gewählte Ansicht hat Vorrang — aber nur gültige Werte.
  assert.equal(V.listenFormFuer({ gesamt: 3, wunsch: 'tabelle' }), 'tabelle')
  assert.equal(V.listenFormFuer({ gesamt: 42, wunsch: 'karten' }), 'karten')
  assert.equal(V.listenFormFuer({ gesamt: 42, wunsch: 'quatsch' }), 'tabelle',
    'unbekannte Ansicht fällt auf die Regel nach Gesamtzahl zurück')
  // Die Seite rechnet sie NICHT aus `zeilen.length` (der Befund selbst).
  assert.ok(seite.includes('listenFormFuer'), 'die Seite benutzt die Regel')
  assert.ok(!/listenForm\(\s*zeilen\.value\.length\s*\)/.test(seite),
    'die Form kommt NICHT aus der Zahl der sichtbaren Zeilen (Befund 2)')
  assert.ok(!seite.includes('listenForm('), 'die alte Rechnung auf die Seite ist entfallen')
}

// ── 7. BEFUND 4: Adressbuch kennt kein Blättern ────────────────────────────
{
  assert.equal(V.kenntSeiten('liste'), true)
  assert.equal(V.kenntSeiten('adressbuch'), false)
  assert.equal(V.fusszeileFuer({ quelle: 'adressbuch', gesamt: 25, sichtbar: 25, seite: 1, seiten: 2 }),
    '25 Personen', 'das Adressbuch nennt nur die Anzahl — keine erfundene Seitenzahl')
  assert.equal(V.fusszeileFuer({ quelle: 'liste', gesamt: 42, sichtbar: 20, seite: 1, seiten: 3 }),
    '20 von 42 Personen · Seite 1 von 3')
  assert.equal(V.fusszeileFuer({ quelle: 'liste', gesamt: 42, sichtbar: 2, seite: 3, seiten: 3 }),
    '2 von 42 Personen · Seite 3 von 3')
  assert.equal(V.fusszeileFuer({ quelle: 'adressbuch', gesamt: 0 }), null,
    'ohne Treffer keine „0 Personen“-Zeile')
  // Knöpfe: ohne Blättern beide aus UND nicht sichtbar.
  assert.deepEqual(V.blaetterKnopfZustand({ quelle: 'adressbuch', seite: 1, seiten: 2 }),
    { zurueck: false, weiter: false, sichtbar: false })
  assert.deepEqual(V.blaetterKnopfZustand({ quelle: 'liste', seite: 1, seiten: 3 }),
    { zurueck: false, weiter: true, sichtbar: true })
  assert.deepEqual(V.blaetterKnopfZustand({ quelle: 'liste', seite: 3, seiten: 3 }),
    { zurueck: true, weiter: false, sichtbar: true })
}

// ── 8. Blättern: Ziel geprüft, keine Sprünge ins Leere ─────────────────────
{
  assert.equal(V.zielSeite(1, 2, 3), 2)
  assert.equal(V.zielSeite(1, 0, 3), null, 'keine Seite 0')
  assert.equal(V.zielSeite(1, 4, 3), null, 'keine Seite hinter der letzten')
  assert.equal(V.zielSeite(1, 1, 3), null, 'die aktuelle Seite lädt nicht neu')
  assert.equal(V.zielSeite(2, 'kaputt', 3), null)
  assert.ok(seite.includes('zielSeite'), 'die Seite prüft das Blätter-Ziel')
}

// ── 9. Spalten der Verwaltung ──────────────────────────────────────────────
{
  const ohne = V.verwaltungSpalten({ persoenlich: false }).map(s => s.key)
  const mit = V.verwaltungSpalten({ persoenlich: true }).map(s => s.key)
  assert.deepEqual(ohne, ['name', 'status', 'gruppen', 'dabei'],
    'ohne persönliche Daten stehen die Kernspalten (Status, Gruppen)')
  assert.deepEqual(mit,
    ['name', 'status', 'gruppen', 'telefon', 'email', 'adresse', 'geburtstag', 'dabei'])
  // Die Zellen der Tabelle halten dieselbe Reihenfolge: Status · Gruppen ·
  // Telefon · E-Mail · Adresse · Geburtstag · dabei. Vorher stand die E-Mail
  // (erste Kontaktzelle) unter der Überschrift „Telefon“.
  const tabelle = liste.slice(liste.indexOf('class="pz-tabelle"'), liste.indexOf('<ul v-show'))
  const reihenfolge = [...tabelle.matchAll(/pz-zelle-(status|gruppen|telefon|email|kontakt|adresse|geburtstag|dabei)\b/g)]
    .map(m => m[1])
  // `kontakt` ist die gemeinsame Klassenhälfte jeder Kontaktzelle; die
  // eigene Hälfte (telefon/email) sagt, welche es ist.
  assert.deepEqual(reihenfolge.slice(0, 6), ['status', 'gruppen', 'kontakt', 'telefon', 'kontakt', 'email'],
    'Telefon steht VOR der E-Mail (eigene Zellen-Klassen statt dreimal „kontakt“)')
  assert.ok(reihenfolge.includes('geburtstag') && reihenfolge.includes('dabei'),
    'Geburtstag und „dabei seit“ stehen im Verwaltungssatz')
}

// ── 10. BEFUND 5: Profil-Link nur für Personen mit Profil ──────────────────
{
  assert.ok(/darfProfilLink/.test(liste), 'die Liste fragt `darfProfilLink` (DSGVO-2d)')
  assert.ok(!/function hatProfil\(z\)\s*\{\s*return Boolean\(String\(z\?\.name/.test(liste),
    'die alte Prüfung „nur Name vorhanden“ ist entfallen')
  // Die Zeile selbst trägt kein festes Sprungziel mehr für Gelöschte.
  assert.match(liste, /function hatProfil\(z\) \{\s*return Boolean\(z\) && darfProfilLink\(z\)/,
    'hatProfil = „hat ein Profil“, nicht „hat einen Namen“')
}

// ── 11. BEFUND 3: Fußzeile außerhalb der Tabelle ───────────────────────────
{
  const tabelleStart = liste.indexOf('class="pz-tabelle"')
  const tabelleEnde = liste.indexOf('<ul v-show="form !== \'tabelle\'')
  const fuss = liste.indexOf('class="pz-fuss"')
  assert.ok(tabelleStart > 0 && tabelleEnde > tabelleStart && fuss > tabelleEnde,
    'die Fußzeile steht NACH dem Tabellenkasten (nicht darin)')
  const kasten = liste.slice(tabelleStart, tabelleEnde)
  assert.ok(!kasten.includes('pz-fuss'), 'im Tabellenkasten steht keine Fußzeile mehr')
}

// ── 12. Fehlerzustand: gestaltet, mit „Erneut versuchen“ ───────────────────
{
  assert.match(liste, /v-else-if="fehler"[\s\S]{0,120}erneut-versuchen="erneutLaden"/,
    'der Fehlerzustand ist ein DkEmpty mit „Erneut versuchen“')
  assert.ok(!/pz-fehler/.test(liste), 'die nackte rote Fehlerzeile ist entfallen')
  assert.ok(seite.includes('@erneut="laden"'), 'die Seite hängt den erneuten Versuch an `laden`')
  // Alle fünf Zustände sind gestaltet: laden, Fehler, leer, Suche ohne Treffer, gefüllt.
  assert.match(liste, /DkSkelett/, 'ladend: Skelett')
  assert.match(liste, /Keine Person gefunden/, 'Suche ohne Treffer ist ein eigener Zustand')
  assert.match(liste, /Noch keine Person/, 'leer ist ein eigener Zustand')
}

// ── 13. BEFUND 6: Adressbuch-Adressen leiten dauerhaft auf die Liste ───────
{
  assert.ok(/'#\/adressbuch':\s*'#\/personen\/liste'/.test(router),
    '#/adressbuch → #/personen/liste')
  assert.ok(/'#\/personen\/adressbuch':\s*'#\/personen\/liste'/.test(router),
    '#/personen/adressbuch → #/personen/liste')
  assert.ok(!/'#\/personen\/adressbuch':\s*'Adressbuch'/.test(router),
    'die alte Adressbuch-Seite ist als Route entfallen')
  // #/mitglieder führt für ALLE auf die Liste (die Übersicht war der Einstieg
  // einer Ansicht, die seit UX3b kein Einstieg mehr ist).
  assert.ok(/'#\/mitglieder':\s*'#\/personen\/liste'/.test(router),
    '#/mitglieder → #/personen/liste')
  assert.ok(!/'#\/mitglieder':\s*'#\/personen\/uebersicht'/.test(router),
    'die alte Weiterleitung auf die Übersicht ist entfallen')
}

// ── 14. BEFUND 7 (UX1b-Schrift): Gewichte und Ziffern aus Tokens ───────────
{
  assert.ok(!/font-weight:\s*600\b/.test(liste), 'kein blankes Gewicht 600 (Token --fw-fett)')
  assert.ok(!/font-weight:\s*550\b/.test(liste), 'kein blankes Gewicht 550 (Token --fw-mittel)')
  assert.ok(!/tabular-nums/.test(liste.replace(/--fs-tabular/, '')),
    'tabellarische Ziffern über das Token --fs-tabular')
  assert.ok(liste.includes('var(--fs-tabular)'), 'die Ziffern-Regel benutzt das Token')
}

// ── 15. „E-Mail verborgen“ nur, wenn wirklich verborgen wurde ──────────────
{
  assert.deepEqual(Z.emailAnzeige(null), { text: 'E-Mail verborgen', verborgen: true })
  assert.deepEqual(Z.emailAnzeige(null, { angefordert: false }),
    { text: Z.NICHT_ANGEFORDERT, verborgen: false, angefordert: false },
    'ohne Anforderung steht NICHT „E-Mail verborgen“ (kein Vorwurf an das Mitglied)')
  assert.equal(Z.NICHT_ANGEFORDERT, 'nicht angefordert')
  assert.deepEqual(Z.emailAnzeige('a@b.de', { angefordert: false }).text, 'a@b.de')
  // Die Liste übergibt die Anforderung an die Anzeige (eine Wahrheit).
  assert.ok(liste.includes('{ angefordert: angefordert }'),
    'die Zellen geben den Anforderungs-Zustand an die Anzeige weiter')
}

// ── 16. Die Seite fordert persönliche Daten NUR bei Verwaltung + Schalter ──
{
  // Der echte Aufruf steht als `apiCall('…get_mitglieder_liste', { … })`; die
  // früheren Nennungen sind Kommentare (Kopf der Datei).
  const aufrufStart = seite.indexOf("apiCall('diakronos.diakonos.api.mitglieder.get_mitglieder_liste'")
  assert.ok(aufrufStart > 0, 'die Seite ruft get_mitglieder_liste auf')
  const aufruf = seite.slice(aufrufStart, aufrufStart + 900)
  assert.ok(/persoenliche_daten:\s*persoenlicheAngefordert\.value/.test(aufruf),
    'persoenliche_daten kommt aus der Regel, nicht aus einem festen false')
  assert.ok(!/persoenliche_daten:\s*false/.test(seite),
    'der feste Wert `persoenliche_daten: false` (Befund 1) ist entfallen')
  // Status, Sortierung und Suche gehen ebenfalls an den Server.
  for (const feld of ['status:', 'sort_by:', 'sort_order:', 'suche:']) {
    assert.ok(aufruf.includes(feld), `die Abfrage schickt ${feld}`)
  }
}

// ── 17. Waertende Konten und Export nur für die Verwaltung ─────────────────
{
  assert.match(seite, /<WartendeKontenKarte v-if="verwaltung"/,
    'die Karte „wartende Konten“ hängt an der Verwaltungsrolle')
  assert.match(seite, /v-if="verwaltung"[\s\S]{0,300}>\{\{ exportLaeuft \? 'Exportiere…' : 'Export' \}\}</,
    'der Export-Knopf hängt an der Verwaltungsrolle')
}

// ── 18. Die Seite spiegelt Admins in die Verwaltung (eine Regel) ───────────
{
  assert.ok(seite.includes('verwaltungSichtbar'), 'die Seite benutzt die Verwaltungsregel')
  assert.ok(seite.includes('persoenlicheDatenAnfordern'), 'die Seite benutzt die Anforderungsregel')
  assert.ok(liste.includes('statusVariante') && liste.includes('statusWort'),
    'Status wird über die gemeinsame Statussprache angezeigt')
}

console.log('UX3b2: alle Regeln grün')

// ── Review-Nachtrag: Statusfilter aus der Adresse (Übersicht-Kachel) ───────
{
  assert.equal(V.statusAusAdresse('#/personen/liste?status=Mitglied'), 'Mitglied')
  assert.equal(V.statusAusAdresse('#/personen/liste?status=Passiver%20Gast'), 'Passiver Gast')
  for (const hash of ['#/personen/liste', '#/personen/liste?status=Hacker', '', null,
    '#/personen/liste?status=', '#/personen/liste?andere=1']) {
    assert.equal(V.statusAusAdresse(hash), '', `unbekannt/leer → Alle: ${hash}`)
  }
  assert.equal(V.adresseMitStatus('#/personen/liste', 'Gast'), '#/personen/liste?status=Gast')
  assert.equal(V.adresseMitStatus('#/personen/liste?status=Gast&x=1', 'Mitglied'),
    '#/personen/liste?status=Mitglied&x=1')
  assert.equal(V.adresseMitStatus('#/personen/liste?status=Gast', ''), '#/personen/liste')
  assert.match(seite, /statusAusAdresse\(window\.location\.hash\)/)
  assert.match(seite, /history\.replaceState\(null, '', adresseMitStatus\(/)
  const kachel = readFileSync(
    new URL('../src/diakonos/pages/mitglieder/Uebersicht.vue', import.meta.url), 'utf8')
  assert.match(kachel, /#\/personen\/liste\?status=Mitglied/)
  assert.equal(V.statusAusAdresse('#/personen/liste?status=Mitglied'), 'Mitglied',
    'die Kachel-Adresse der Übersicht wählt den Filter vor')
}

// ── Review-Nachtrag: Freigabe-Sicht sagt wieder „E-Mail verborgen“ ─────────
{
  assert.match(liste,
    /const angefordert = computed\(\s*\(\) => props\.quelle !== 'liste' \|\| \(verwaltung\.value && props\.persoenlich === true\),?\s*\)/)
}
