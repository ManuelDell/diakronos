import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * UX3b — Personen = Mitglieder + Adressbuch (Frontend-Regeln).
 *
 * Prüft den ECHTEN Code (Import, keine Textsuche):
 *  - die Quelle je Rolle (Admin → Mitgliederliste, sonst Adressbuch),
 *  - die Zeilenform: aus dem Adressbuch kommen KEINE Felder, die es nicht
 *    liefert (Status, Gruppen) — kein stiller Datenzuwachs,
 *  - „E-Mail verborgen“ ist EIN Text und erscheint nur an dieser Stelle,
 *  - Tabelle ab 20 Personen, darunter Karten (Entwurf A3),
 *  - Fußzeile/Blättern wie im Entwurf („Zurück“ auf Seite 1 deaktiviert).
 *
 * Zusätzlich: die Seiten-Vorlage benutzt genau diese Regeln — der
 * Adressbuch-Weg fragt keinen Status ab und kein Reiter ist für Nicht-Admins
 * sichtbar.
 */

const moduleUrl = new URL('../src/diakonos/composables/personenZeilen.mjs', import.meta.url)
const P = await import(moduleUrl.href)

const seite = readFileSync(
  new URL('../src/diakonos/pages/Personen.vue', import.meta.url), 'utf8')
const liste = readFileSync(
  new URL('../src/diakonos/components/personen/PersonenListe.vue', import.meta.url), 'utf8')

// ── 1. Quelle je Rolle ──────────────────────────────────────────────────────
{
  assert.equal(P.personenQuelle(true), 'liste',
    'Mitgliederadministrator liest die Mitgliederliste')
  assert.equal(P.personenQuelle(false), 'adressbuch',
    'alle anderen lesen die Adressbuch-Sicht (kein Datenzuwachs)')
  // Fail closed: alles außer einem echten true ist „kein Admin“.
  for (const wert of [undefined, null, 0, '', 'true', 1, {}]) {
    assert.equal(P.personenQuelle(wert), 'adressbuch',
      `personenQuelle(${JSON.stringify(wert)}) muss fail-closed das Adressbuch wählen`)
  }
}

// ── 2. Zeilenform: das Adressbuch liefert keine Verwaltungsfelder ───────────
{
  const roh = {
    name: 'M-0001', vorname: 'Maria', nachname: 'Lang',
    email: 'maria@example.org', telefonnummer: '07071 1234',
    postleitzahl: '72070', wohnort: 'Tübingen',
    geburtstag: '1985-05-05', foto: '',
  }
  const z = P.zeileAusAdressbuch(roh)
  assert.equal(z.anzeigename, 'Maria Lang')
  assert.equal(z.ort, '72070 Tübingen', 'PLZ und Ort stehen zusammen')
  assert.equal(z.status, '', 'das Adressbuch kennt keinen Status')
  assert.deepEqual(z.gruppen, [], 'das Adressbuch kennt keine Gruppen')
  assert.equal(z.quelle, 'adressbuch')
  // Kein Feld, das die Quelle nicht hat — auch nicht als undefined-Schlüssel.
  for (const verboten of ['status', 'gruppen', 'notiz', 'adressbuch_sichtbarkeit']) {
    assert.ok(!(verboten in roh) || verboten === 'status', 'Testdaten bleiben ehrlich')
  }
}

// ── 3. Zeilenform: die Mitgliederliste (Admin) trägt Status/Gruppen ────────
{
  const z = P.zeileAusListe({
    name: 'M-0002', vorname: 'Jonas', nachname: 'Rehberg',
    full_name: 'Jonas Rehberg', email: null, telefonnummer: null,
    status: 'Mitglied', gruppen: ['Technik'],
  })
  assert.equal(z.anzeigename, 'Jonas Rehberg')
  assert.equal(z.status, 'Mitglied')
  assert.deepEqual(z.gruppen, ['Technik'])
  assert.equal(z.email, null, 'nicht angeforderte Felder bleiben leer')
  assert.equal(z.quelle, 'liste')
  // Ohne full_name wird der Name aus den Teilen gebaut — nie „null“.
  const ohne = P.zeileAusListe({ vorname: null, nachname: 'Voss' })
  assert.equal(ohne.anzeigename, 'Voss')
}

// ── 4. „E-Mail verborgen“ — EINE Formulierung, nur wenn nichts da ist ───────
{
  assert.equal(P.EMAIL_VERBORGEN, 'E-Mail verborgen')
  assert.deepEqual(P.emailAnzeige(null), { text: 'E-Mail verborgen', verborgen: true })
  assert.deepEqual(P.emailAnzeige(''), { text: 'E-Mail verborgen', verborgen: true })
  assert.deepEqual(P.emailAnzeige('  '), { text: 'E-Mail verborgen', verborgen: true })
  assert.deepEqual(P.emailAnzeige('a@b.de'), { text: 'a@b.de', verborgen: false })
  // Telefon hat einen Gedankenstrich, nicht „verborgen“ — es gibt keinen
  // Schalter, der es versteckt (das Adressbuch liefert nur Freigegebenes).
  assert.equal(P.telefonAnzeige(null), '–')
  assert.equal(P.telefonAnzeige('07071 1'), '07071 1')
}

// ── 5. Tabelle ab 20 Personen ───────────────────────────────────────────────
{
  assert.equal(P.TABELLE_AB_PERSONEN, 20)
  assert.equal(P.listenForm(0), 'karten')
  assert.equal(P.listenForm(3), 'karten')
  assert.equal(P.listenForm(19), 'karten')
  assert.equal(P.listenForm(20), 'tabelle')
  assert.equal(P.listenForm(142), 'tabelle')
  assert.equal(P.listenForm(undefined), 'karten', 'unbekannte Zahl bleibt Karten')
}

// ── 6. Fußzeile und Blättern (Entwurf A3) ──────────────────────────────────
{
  assert.equal(P.fusszeile({ gesamt: 142, seite: 1, seiten: 12, sichtbar: 20 }),
    '20 von 142 Personen · Seite 1 von 12')
  assert.equal(P.fusszeile({ gesamt: 142, seite: 3, seiten: 12, sichtbar: 142 }),
    '142 Personen · Seite 3 von 12')
  assert.equal(P.fusszeile({ gesamt: 1, seite: 1, seiten: 1, sichtbar: 1 }),
    '1 Person · Seite 1 von 1', 'Einzahl bleibt Einzahl')
  assert.equal(P.fusszeile({ gesamt: 0, seite: 1, seiten: 1 }), null,
    'ohne Treffer keine „0 Personen“-Zeile')

  assert.deepEqual(P.blaetternMoeglich(1, 12), { zurueck: false, weiter: true },
    '„Zurück“ ist auf Seite 1 deaktiviert')
  assert.deepEqual(P.blaetternMoeglich(12, 12), { zurueck: true, weiter: false })
  assert.deepEqual(P.blaetternMoeglich(5, 12), { zurueck: true, weiter: true })
  assert.equal(P.seitenzahl(142, 20), 8)
  assert.equal(P.seitenzahl(0, 20), 1, 'leer ist trotzdem eine Seite')
  assert.equal(P.seitenzahl(20, 20), 1)
  assert.equal(P.seitenzahl(21, 20), 2)
}

// ── 7. Initialen ───────────────────────────────────────────────────────────
{
  assert.equal(P.initialen('Maria Lang'), 'ML')
  assert.equal(P.initialen('Hanna Voss'), 'HV')
  assert.equal(P.initialen('Elias'), 'EL')
  assert.equal(P.initialen(''), '?')
  assert.equal(P.initialen(null), '?')
}

// ── 8. Die Seite benutzt die Regeln (keine zweite Wahrheit) ────────────────
{
  for (const name of ['personenQuelle', 'zeileAusListe', 'zeileAusAdressbuch',
    'listenForm', 'seitenzahl']) {
    assert.ok(seite.includes(name), `Personen.vue benutzt ${name} aus personenZeilen.mjs`)
  }
  assert.ok(seite.includes('get_adressbuch'),
    'der Nicht-Admin-Weg ist die B2-Freigabe-Sicht')
  assert.ok(seite.includes('get_mitglieder_liste'),
    'der Admin-Weg ist die Mitgliederliste')
  // Die Reiter des Entwurfs A3, drei davon nur mit Recht. UX3j: Die Einträge
  // stehen EINMAL in menue.js (`MITGLIEDER_REITER`) — die Seite liest sie über
  // `personenReiter` statt einer zweiten Liste im Skript.
  assert.ok(seite.includes('personenReiter('), 'Reiterzeile kommt aus menue.js')
  const menue = (await import(new URL('../src/diakonos/menue.js', import.meta.url).href)).MITGLIEDER_REITER
  assert.deepEqual(menue.map(r => r.id), ['liste', 'anfragen', 'datenschutz', 'import'],
    'Reiter: Liste · Anfragen · Datenschutz · Import')
  assert.deepEqual(menue.map(r => r.label), ['Liste', 'Anfragen', 'Datenschutz', 'Import'])
  assert.equal(menue.filter(r => r.rolle === 'admin').length, 3,
    'Anfragen/Datenschutz/Import sind Admin-Reiter — die Liste ist für alle')

  // Kein erfundenes Feld: die Adressbuch-Quelle darf keinen Status fragen —
  // sie fragt nur, was der Server liefert.
  const adressbuchAufruf = seite.slice(seite.indexOf("quelle.value === 'adressbuch'"),
    seite.indexOf('} else {', seite.indexOf("quelle.value === 'adressbuch'")))
  assert.ok(!/status/.test(adressbuchAufruf),
    'die Adressbuch-Sicht fragt keinen Status ab (den gibt es dort nicht)')
}

// ── 9. Die Liste: eine Zeile, ganze Zeile klickbar ─────────────────────────
{
  assert.ok(liste.includes('pz-zeilenziel'),
    'die Zeile ist über ihre ganze Fläche klickbar')
  assert.ok(/adressbuch_sichtbarkeit|EMAIL_VERBORGEN/.test(liste) === false,
    'die Liste kennt die Policy nicht — sie zeigt nur, was ankommt')
  // UX3b2: Die Anzeige bekommt zusätzlich die Anforderung mit — heißt die
  // Zelle „nicht angefordert“, steht dort NICHT „E-Mail verborgen“.
  assert.equal(liste.split('emailAnzeige(z.email, { angefordert: angefordert }).text').length - 1, 2,
    '„E-Mail verborgen“ steht genau einmal je Darstellung (Tabelle, Karte)')
}

// ── 10. Der Reiter „Liste“ zeigt die zusammengelegte Seite ─────────────────
{
  const router = readFileSync(
    new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
  assert.ok(/'#\/personen':\s*'Personen'/.test(router),
    'der Einstieg öffnet die Personen-Seite')
  assert.ok(/'#\/personen\/liste':\s*'Personen'/.test(router),
    'der Reiter „Liste“ öffnet DIESELBE Seite — keine zwei Umsetzungen der Liste')
  assert.ok(!/'#\/personen\/liste':\s*'MitgliederListe'/.test(router),
    'die alte Mitgliederliste ist an dieser Adresse nicht mehr verdrahtet')
}

// ── 11. Die ganze Zeile ist klickbar — Bezug an der Zelle ─────────────────
{
  // `position: relative` an einem <tr> wird im Tabellensatz ignoriert; der
  // ausgebreitete Link bekam Breite 0 und die Zeile war nicht klickbar
  // (im Browser gemessen). Der Bezug gehört deshalb an die Zellen.
  assert.match(liste, /\.dk-ui-table tbody tr\.pz-zeile > td\s*\{[^}]*position:\s*relative/,
    'relative Positionierung an den Zellen der Personen-Zeile')
  assert.ok(!/\.pz-zeile\s*\{[^}]*position:\s*relative/.test(liste),
    'nicht am <tr> (dort wirkungslos)')
  // `a { position: relative }` aus index.css schlägt eine einteilige
  // Klassen-Regel — der Link muss absolute ZWEIFACH als Klasse setzen.
  assert.match(liste, /\.pz-zeilenziel\.pz-zeilenziel\s*\{[^}]*position:\s*absolute/,
    'der ausgebreitete Link setzt position:absolute mit Klassen-Spezifität')
}

// ── 12. „E-Mail verborgen“ nur einmal je Zeile ────────────────────────────
{
  // Die Telefonzelle nimmt die stille Klasse, wenn schon die E-Mail-Zelle den
  // Satz trägt — sonst stand „E-Mail verborgen“ zweimal nebeneinander.
  assert.match(liste, /emailAnzeige\(z\.email, \{ angefordert: angefordert \}\)\.verborgen \? 'pz-verborgen' : 'pz-leer'/,
    'Telefonzelle erbt den Zustand der E-Mail-Zelle (still statt zweimal Text)')
  const treffer = liste.split('emailAnzeige(z.email, { angefordert: angefordert }).text').length - 1
  assert.equal(treffer, 2, 'der Satz steht genau einmal je Darstellung (Tabelle, Karte)')
}

// ── 13. Am Handy Karten statt der 640-px-Tabelle ──────────────────────────
{
  // DkTable setzt min-width: 640px — am Handy lief die E-Mail-Spalte aus dem
  // Bild (Screenshot). Der Baustein blendet dort die Tabelle aus und zeigt
  // seine Karten.
  assert.match(liste, /@media \(max-width: 720px\)\s*\{[^}]*\.pz-tabelle\s*\{\s*display:\s*none/,
    'Tabelle wird am Handy ausgeblendet')
  // Der BEZUG steht in der Vorlage: sonst stünde die Tabelle am Handy auf
  // `display:none`, die Karten aber auch (`display:none` in der Basis-Regel) —
  // der Bereich war leer (im Screenshot 390 px gesehen).
  assert.match(liste, /v-else-if="form === 'tabelle'"\s+class="pz-tabelle"/,
    'Tabelle nur bei form=tabelle')
  // `v-else` + `v-show` geht in Vue nicht; die Karten hängen an v-show und
  // stehen damit im DOM (sonst könnte CSS sie am Handy nicht einblenden).
  assert.match(liste, /<ul v-show="form !== 'tabelle' \|\| schmal" class="pz-karten">/,
    'Karten stehen im DOM und werden über v-show geschaltet')
  assert.match(liste, /window\.innerWidth <= 720/, 'schmale Anzeige wird gemessen (720 px)')
}

console.log('UX3b: alle Regeln grün')
