/**
 * UX2c — Rückfragen durch „Rückgängig“ ersetzen + Endgültig-Dialog.
 *
 * Prinzip I2 der UI-Prinzipien: „Rückgängig statt Rückfrage — Bestätigungs-
 * dialog nur für Unumkehrbares und dann mit konkreter Folge.“ GRUNDSATZ der
 * Nacharbeit (Review 06.11.): Ein „Rückgängig“ gibt es NUR, wenn es den
 * Zustand VOLLSTÄNDIG wiederherstellt; sonst bleibt die Rückfrage.
 *
 * Der Test hält beides fest, ohne Browser:
 *
 *  1. Die Gegenrichtungen (`rueckgaengigWeg.mjs`) nennen ECHTE Server-Endpunkte
 *     — geprüft gegen `backend/src/diakronos_app/api/` UND gegen die
 *     Aufrufstelle im Frontend (`useVerwaltung.js`, `useWebsiteFreigaben.js`):
 *     dort steht der volle whitelist-Name, nicht nur der Funktionsname.
 *  2. Verhalten je Rückweg mit REALISTISCHEN Listendaten (so wie die echten
 *     Endpunkte sie liefern, inkl. `wartung` als 1 | 0) — nicht nur Idealdaten.
 *  3. `wiederherstellen()` behandelt `{success: false}` als Fehler.
 *  4. Was NICHT vollständig zurückkommt, hat kein „Rückgängig“ (Buchung
 *     stornieren, Mitglied aus Gruppe entfernen) — Rückfrage stattdessen.
 *  5. Die Seiten, deren Aktion umkehrbar ist, fragen nicht mehr nach, sondern
 *     melden die Aktion am Rückgängig-Stapel an (Wächter über den Quelltext).
 *  6. Die Seiten, deren Aktion endgültig ist, benutzen den EINEN
 *     Endgültig-Dialog (`DkEndgueltig`) statt einer eigenen Rückfrage.
 *  7. Der Endgültig-Dialog selbst: Frage als Titel, Folge im Text (und per
 *     `aria-describedby` verknüpft), Wort-Abfrage beim Schwersten, gefährlicher
 *     Knopf, „Schließen“ als Ausstieg ohne Eingabe.
 *
 * Läuft im Docker-Build (`node --test`, Muster `tests/ux2c-*.test.mjs` in
 * `frontend/tests/testliste.txt`).
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

import {
  RUECKGAENGIG_WEGE, MELDUNGEN, VOLLSTAENDIG,
  abbildung, meldung, undoText, vollstaendig,
} from '../src/diakonos/composables/rueckgaengigWeg.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const QUELLE = resolve(HIER, '..', 'src', 'diakonos')
// Das Frontend-Stage des Image-Builds legt die Backend-Quellen nach
// /backend (backend/Dockerfile). Im Worktree liegen sie unter backend/src.
// Beides wird gesucht — der Test soll in BEIDEN Lagen dasselbe prüfen.
const BACKEND_KANDIDATEN = [
  // IM IMAGE: das Frontend-Stage legt die gelesenen Server-Dateien flach nach
  // /backend/api/... (eigene COPY-Zeilen in backend/Dockerfile, Regel 13).
  resolve(HIER, '..', '..', 'backend'),
  // Im Worktree: die normalen Paketpfade.
  resolve(HIER, '..', '..', 'backend', 'src', 'diakronos_app'),
]
const BACKEND = BACKEND_KANDIDATEN.find(
  p => existsSync(resolve(p, 'api', 'gruppen.py')),
) || BACKEND_KANDIDATEN[1]

function lies(relativ) {
  return readFileSync(resolve(QUELLE, relativ), 'utf8')
}

function backendQuelle(relativ) {
  const pfad = resolve(BACKEND, relativ)
  return existsSync(pfad) ? readFileSync(pfad, 'utf8') : ''
}

/** Quelltext ohne Kommentare — Aussagen über „es gibt kein X“ prüfen den CODE. */
function ohneKommentare(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '')
}

const apiCallIn = (datei) => backendQuelle(datei)

// ── 1. Die Wege sind echt: Endpunkt existiert, Felder stimmen ──────────────

/**
 * Server-Endpunkt → Datei + Parameter, die die Funktion verlangt.
 *
 * Die Zuordnung ist ABSICHTLICH ausgeschrieben (nicht abgeleitet): sie sagt,
 * wo im Backend nachgesehen wurde. Ändert der Server eine Signatur, fällt es
 * hier auf, bevor die Oberfläche ins Leere ruft.
 *
 * Nacharbeit 06.11.: `gruppenmitglied` und `buchung` sind ENTFALLEN — ihre
 * Gegenrichtung stellt den Zustand nicht vollständig her (Beitrittsdatum/
 * Rolle/Notiz bzw. Zeitraum/Status/Notizen). Sie stehen jetzt als Rückfrage
 * in den Seiten (siehe Abschnitt 4).
 */
const SERVER = {
  'diakronos.planrahmen.api.sammlungsmerkmal_werte_pflegen': {
    datei: 'api/planrahmen.py',
    pflicht: ['plantyp', 'schluessel', 'aktion', 'wert'],
    optional: ['neu', 'plan'],
  },
  'diakronos.kronos.api.kalender_verwaltung.create_kalender': {
    datei: 'api/kronos/kalender_verwaltung.py',
    pflicht: ['titel'],
    optional: ['farbe', 'selbstverwaltet', 'leserechte', 'schreibrechte', 'moderatoren'],
  },
  'diakronos.diakonos.api.ressourcen.create_ressource': {
    datei: 'api/ressourcen.py',
    pflicht: ['name'],
    optional: ['typ', 'kapazitaet', 'beschreibung', 'tags', 'wartung'],
  },
  // Der Server nimmt zusätzlich `request` (FastAPI-Rumpf) — kein Feld, das
  // die Oberfläche setzt; deshalb hier nicht aufgeführt.
  'diakronos.diakronos.api.website.postfach_speichern': {
    datei: 'api/website.py',
    // Der Server verlangt neben dem Kürzel Bezeichnung UND Adresse (BS-1a).
    pflicht: ['slug', 'bezeichnung', 'email'],
    optional: ['aktiv', 'sortierung'],
    serverZusatz: ['request'],
  },
}

test('jede Gegenrichtung zeigt auf einen vorhandenen Server-Endpunkt', () => {
  for (const [vorgang, weg] of Object.entries(RUECKGAENGIG_WEGE)) {
    const stelle = SERVER[weg.aufruf]
    assert.ok(stelle, `${vorgang}: kein geprüfter Endpunkt für ${weg.aufruf}`)
    const text = backendQuelle(stelle.datei)
    assert.ok(text, `${vorgang}: ${stelle.datei} fehlt im Backend`)
    // Der Funktionsname ist das letzte Stück des whitelist-Namens, das
    // Modulpräfix steht als FRAPPE_MODULE in derselben Datei — beides wird
    // geprüft, damit ein falsches Präfix nicht durchrutscht.
    const [modul, name] = [weg.aufruf.slice(0, weg.aufruf.lastIndexOf('.')), weg.aufruf.split('.').pop()]
    assert.match(
      text,
      new RegExp(`FRAPPE_MODULE\\s*=\\s*"${modul.replace(/\./g, '\\.')}"`),
      `${vorgang}: ${stelle.datei} meldet nicht das Modul ${modul}`,
    )
    assert.match(
      text,
      new RegExp(`def\\s+${name}\\s*\\(`),
      `${vorgang}: ${name} steht nicht in ${stelle.datei}`,
    )
    // Und die Funktion nimmt die Felder an, die die Abbildung schickt.
    const kopf = text.slice(text.indexOf(`def ${name}(`)).split('\n\n')[0]
    for (const feld of stelle.pflicht) {
      assert.match(kopf, new RegExp(`\\b${feld}\\b`), `${vorgang}: ${name} ohne ${feld}`)
    }
  }
})

/**
 * Punkt 6 der Nacharbeit: der VOLLE Pfad, nicht nur der Funktionsname — und er
 * muss mit dem übereinstimmen, was die Aufrufstelle im Frontend benutzt (dort
 * wird der whitelist-Name aus Modulpräfix + Funktion zusammengesetzt). Der
 * frühere Fallback über `registriere_originalpfad` hat einen falschen Pfad
 * verdeckt; hier steht der Vergleich deshalb ausgeschrieben.
 */
test('die Endpunktpfade stimmen mit den Aufrufstellen im Frontend überein', () => {
  // Kalender: Modulpräfix als Konstante, Funktion als Template.
  const verwaltung = lies('composables/useVerwaltung.js')
  assert.match(verwaltung, /const KALENDER = 'diakronos\.kronos\.api\.kalender_verwaltung'/,
    'useVerwaltung.js: Kalender-Modulpräfix hat sich geändert')
  assert.match(verwaltung, /apiCall\(`\$\{KALENDER\}\.create_kalender`, daten\)/,
    'useVerwaltung.js: create_kalender wird anders gerufen')
  assert.equal(
    RUECKGAENGIG_WEGE.kalender.aufruf,
    'diakronos.kronos.api.kalender_verwaltung.create_kalender',
  )
  // Ressource: Modulpräfix als Konstante, Funktion als Template.
  assert.match(verwaltung, /const RESSOURCEN = 'diakronos\.diakonos\.api\.ressourcen'/,
    'useVerwaltung.js: Ressourcen-Modulpräfix hat sich geändert')
  assert.match(verwaltung, /apiCall\(`\$\{RESSOURCEN\}\.create_ressource`, daten\)/,
    'useVerwaltung.js: create_ressource wird anders gerufen')
  assert.equal(
    RUECKGAENGIG_WEGE.ressource.aufruf,
    'diakronos.diakonos.api.ressourcen.create_ressource',
  )
  // Postfach: Endpunkt steht als Wert in der Konstanten ENDPUNKTE.
  const freigaben = lies('composables/useWebsiteFreigaben.js')
  assert.match(freigaben,
    /postfachSpeichern: 'diakronos\.diakronos\.api\.website\.postfach_speichern'/,
    'useWebsiteFreigaben.js: postfach_speichern wird anders gerufen')
  assert.equal(
    RUECKGAENGIG_WEGE.postfach.aufruf,
    'diakronos.diakronos.api.website.postfach_speichern',
  )
  // Kein Pfad entsteht „irgendwie“: jeder Name trägt sein Modulpräfix.
  for (const [vorgang, weg] of Object.entries(RUECKGAENGIG_WEGE)) {
    assert.match(weg.aufruf, /^diakronos\.[\w.]+\.api\.[\w.]+$/,
      `${vorgang}: ${weg.aufruf} ist kein vollständiger whitelist-Name`)
  }
})

test('jede Abbildung schickt nur Felder, die der Server kennt', () => {
  const proben = {
    auswahlwert: { plantyp: 'P', schluessel: 'S', wert: 'Alt', plan: null },
    kalender: { titel: 'Gottesdienste', farbe: '#1c2850', selbstverwaltet: false },
    ressource: { name: 'Gemeindesaal', typ: 'Raum', kapazitaet: 80 },
    postfach: { slug: 'kontakt', bezeichnung: 'Kontakt', email: 'a@b.de', aktiv: true },
  }
  for (const [vorgang, weg] of Object.entries(RUECKGAENGIG_WEGE)) {
    const stelle = SERVER[weg.aufruf]
    const befehl = abbildung(vorgang, proben[vorgang])
    assert.ok(befehl, `${vorgang}: Abbildung lieferte nichts`)
    assert.equal(befehl.aufruf, weg.aufruf)
    const erlaubt = new Set([...stelle.pflicht, ...stelle.optional])
    for (const feld of Object.keys(befehl.args)) {
      assert.ok(erlaubt.has(feld), `${vorgang}: Feld ${feld} kennt der Server nicht`)
    }
    for (const feld of stelle.pflicht) {
      assert.ok(feld in befehl.args, `${vorgang}: Pflichtfeld ${feld} fehlt`)
      assert.ok(befehl.args[feld] !== null && befehl.args[feld] !== undefined,
        `${vorgang}: Pflichtfeld ${feld} ist leer`)
    }
  }
})

test('ohne vollständige Angaben wird nicht geraten', () => {
  assert.equal(abbildung('auswahlwert', { plantyp: 'P', schluessel: '', wert: 'x' }), null)
  assert.equal(abbildung('kalender', {}), null)
  assert.equal(abbildung('ressource', { name: '  ' }), null)
  assert.equal(abbildung('postfach', {}), null)
  assert.equal(abbildung('gibtsnicht', { a: 1 }), null, 'unbekannter Vorgang')
  // Entfernte Vorgänge dürfen NICHT wieder auftauchen (siehe Abschnitt 4).
  assert.equal(abbildung('gruppenmitglied', { gruppe_id: 'G', mitglied_id: 'M' }), null)
  assert.equal(abbildung('buchung', {
    ressource_id: 'R', datum_von: 'a', datum_bis: 'b', zweck: 'x',
  }), null)
})

// ── 2. Verhalten je Rückweg mit REALISTISCHEN Listendaten ─────────────────
//
// Die Proben sind wörtlich die Form, die die Endpunkte liefern:
//   * `get_ressourcen_verwaltung` → wartung: 1 | 0, kapazitaet als Zahl/None
//   * `get_kalender_verwaltung`   → titel/farbe/selbstverwaltet + Rechte-Listen
//   * Postfach-Liste der Website  → slug/bezeichnung/email/aktiv/sortierung

/** So sieht eine Zeile aus `get_ressourcen_verwaltung` aus (Wartung an).
 *
 * UX2c-N2: `bild` gehört seit der Nacharbeit dazu — der Endpunkt liefert es
 * (`ressourcen.py`, `get_ressourcen_verwaltung`), leer als `""`. Die Probe
 * ist deshalb die ECHTE Listenform, keine eingespritzten Idealfelder.
 */
const RESSOURCE_AUS_LISTE = {
  id: 'Gemeindesaal',
  name: 'Gemeindesaal',
  typ: 'Raum',
  kapazitaet: 80,
  beschreibung: 'Großer Saal mit Bühne',
  bild: '',
  tags: 'Bühne, Küche',
  wartung: 1,
}

test('Ressource: Wartung 1 aus der Liste wird als Wartung wiederhergestellt', () => {
  const befehl = abbildung('ressource', RESSOURCE_AUS_LISTE)
  assert.deepEqual(befehl.args, {
    name: 'Gemeindesaal',
    typ: 'Raum',
    kapazitaet: 80,
    beschreibung: 'Großer Saal mit Bühne',
    tags: 'Bühne, Küche',
    wartung: true,
  })
})

test('Ressource: Wartung 0 aus der Liste bleibt „keine Wartung“', () => {
  const zeile = { ...RESSOURCE_AUS_LISTE, id: 'Bulli', name: 'Bulli', typ: 'Fahrzeug', wartung: 0 }
  assert.equal(abbildung('ressource', zeile).args.wartung, false)
  // Auch die anderen Schreibweisen, die im Bestand vorkommen.
  assert.equal(abbildung('ressource', { name: 'X', wartung: '1' }).args.wartung, true)
  assert.equal(abbildung('ressource', { name: 'X', wartung: true }).args.wartung, true)
  assert.equal(abbildung('ressource', { name: 'X' }).args.wartung, false)
  assert.equal(abbildung('ressource', { name: 'X', kapazitaet: null }).args.kapazitaet, '')
})

test('Ressource: nur ohne Bild ist das Löschen vollständig umkehrbar', () => {
  assert.equal(vollstaendig('ressource', RESSOURCE_AUS_LISTE), true)
  // Mit Bild: `create_ressource` kennt das Feld nicht → kein „Rückgängig“.
  assert.equal(vollstaendig('ressource', { ...RESSOURCE_AUS_LISTE, image: '/files/a.jpg' }), false)
  assert.equal(vollstaendig('ressource', { ...RESSOURCE_AUS_LISTE, bild: '/files/a.jpg' }), false)
})

// ── 1b. Die Felder, an denen `vollstaendig()` hängt, stehen im Endpunkt ───
//
// Re-Review 07.11.: `vollstaendig()` griff NIE, weil die Listen die Felder
// gar nicht lieferten — jede Ressource galt als „ohne Bild“, jeder Kalender
// als „ohne Google-Vermerk“. Der Test prüft deshalb nicht nur die Probe,
// sondern auch, dass der Endpunkt das Feld WIRKLICH ausgibt.

test('get_ressourcen_verwaltung liefert `bild` (sonst greift vollstaendig() nie)', () => {
  const quelle = ohneKommentare(apiCallIn('api/ressourcen.py'))
  const start = quelle.indexOf('def get_ressourcen_verwaltung')
  assert.ok(start > -1, 'get_ressourcen_verwaltung nicht gefunden')
  const rumpf = quelle.slice(start, quelle.indexOf('\ndef ', start + 1))
  assert.match(rumpf, /fields=\[[^\]]*"bild"/,
    'das Feld muss in `fields` stehen, sonst kommt es aus der Datenbank nicht mit')
  assert.match(rumpf, /"bild":\s*r\.get\("bild"\)\s*or\s*""/,
    'der Eintrag muss `bild` als Text liefern (leer = ""), nicht als null')
})

test('get_kalender_verwaltung liefert `calender_details`', () => {
  const quelle = ohneKommentare(apiCallIn('api/kronos/kalender_verwaltung.py'))
  const start = quelle.indexOf('def _kalender_eintrag')
  assert.ok(start > -1, '_kalender_eintrag nicht gefunden')
  const rumpf = quelle.slice(start, quelle.indexOf('\ndef ', start + 1))
  assert.match(rumpf, /"calender_details":\s*doc\.get\("calender_details"\)\s*or\s*""/,
    'der Eintrag muss `calender_details` als Text liefern (leer = ""), nicht als null')
})

test('Ressource mit Bild aus der Liste → Rückfrage, nicht Rückgängig', () => {
  // Form WÖRTLICH wie der Endpunkt sie liefert (bild gesetzt, wartung 0).
  const mitBild = { ...RESSOURCE_AUS_LISTE, bild: '/files/gemeindesaal.jpg', wartung: 0 }
  assert.equal(vollstaendig('ressource', mitBild), false,
    'das Bild käme nicht zurück → die Seite muss die Rückfrage wählen')
})

test('Kalender aus dem Google-Import aus der Liste → Rückfrage, nicht Rückgängig', () => {
  // Form WÖRTLICH wie `get_kalender_verwaltung` sie liefert.
  const importiert = {
    name: 'Gottesdienste',
    titel: 'Gottesdienste',
    farbe: '#1c2850',
    selbstverwaltet: false,
    calender_details: 'Importiert aus Google Kalender',
    leserechte: ['Mitglied'],
    schreibrechte: [],
    moderatoren: [],
  }
  assert.equal(vollstaendig('kalender', importiert), false,
    'der Vermerk käme nicht zurück → die Seite muss die Rückfrage wählen')
  // Ein selbst angelegter Kalender trägt das Feld leer und ist umkehrbar.
  assert.equal(vollstaendig('kalender', { ...importiert, calender_details: '' }), true)
})

test('Kalender: Rechte und Moderatoren kommen mit, Google-Import nicht', () => {
  /** So sieht eine Zeile aus `get_kalender_verwaltung` aus. */
  const zeile = {
    name: 'Gottesdienste',
    titel: 'Gottesdienste',
    farbe: '#1c2850',
    selbstverwaltet: false,
    leserechte: ['Mitglied'],
    schreibrechte: ['Pfarrer'],
    moderatoren: ['maria@example.org'],
  }
  const befehl = abbildung('kalender', zeile)
  assert.deepEqual(befehl.args, {
    titel: 'Gottesdienste',
    farbe: '#1c2850',
    selbstverwaltet: false,
    leserechte: ['Mitglied'],
    schreibrechte: ['Pfarrer'],
    moderatoren: ['maria@example.org'],
  })
  assert.equal(vollstaendig('kalender', zeile), true)
  // Ein Kalender aus dem Google-Import trägt `calender_details`; die Anlage
  // nimmt das Feld nicht an → kein vollständiges Zurück.
  const importiert = { ...zeile, calender_details: 'Importiert aus Google Kalender' }
  assert.equal(vollstaendig('kalender', importiert), false)
  assert.equal(abbildung('kalender', importiert).args.calender_details, undefined,
    'die Anlage bekommt kein Feld, das der Server nicht kennt')
})

test('Wert wird über die Pflege-Funktion wieder hinzugefügt (nicht über eine Liste)', () => {
  const befehl = abbildung('auswahlwert', {
    plantyp: 'gottesdienst', schluessel: 'instrument', wert: ' Orgel ',
  })
  assert.equal(befehl.args.aktion, 'hinzufuegen')
  assert.equal(befehl.args.wert, 'Orgel', 'Leerraum wird abgeschnitten')
  assert.equal(befehl.args.plan, null)
  assert.equal(vollstaendig('auswahlwert', {}), true)
})

test('Postfach behält Kürzel, Adresse und Reihenfolge', () => {
  /** So sieht eine Zeile der Postfach-Liste aus (BS-1c). */
  const zeile = {
    slug: 'kontakt', bezeichnung: 'Kontakt', email: 'buero@example.org',
    aktiv: true, sortierung: 2,
  }
  const befehl = abbildung('postfach', zeile)
  assert.equal(befehl.args.slug, 'kontakt')
  assert.equal(befehl.args.email, 'buero@example.org')
  assert.equal(befehl.args.sortierung, 2)
  // Ohne Bezeichnung bleibt das Kürzel der Name (der Server verlangt einen).
  assert.equal(abbildung('postfach', { slug: 'kontakt', email: 'a@b.de' }).args.bezeichnung, 'kontakt')
  // Ohne Adresse wird NICHT geraten — der Server lehnt das Postfach ab.
  assert.equal(abbildung('postfach', { slug: 'kontakt' }), null)
  assert.equal(vollstaendig('postfach', zeile), true)
  assert.equal(vollstaendig('postfach', { slug: 'kontakt' }), false)
})

test('vollstaendig(): unbekannter Vorgang ist nie vollständig umkehrbar', () => {
  assert.equal(vollstaendig('gibtsnicht', {}), false)
  assert.equal(vollstaendig('ressource', null), true,
    'ohne Bild ist eine Ressource vollständig umkehrbar (null = keine Angaben)')
  assert.equal(vollstaendig('kalender', null), true,
    'ohne calender_details ist ein Kalender vollständig umkehrbar')
  assert.equal(vollstaendig('postfach', null), false,
    'ohne Kürzel/Adresse kommt kein Postfach zurück')
  assert.deepEqual(Object.keys(VOLLSTAENDIG).sort(), Object.keys(RUECKGAENGIG_WEGE).sort(),
    'jeder Rückweg braucht eine Vollständigkeits-Prüfung')
})

// ── 3. Meldungstexte: die AUSGEFÜHRTE Aktion, ein Begriff je Konzept ───────

test('Meldungstexte nennen die Aktion und (wenn bekannt) den Namen', () => {
  assert.equal(meldung('ressource', 'Gemeindesaal'), '„Gemeindesaal“ gelöscht')
  assert.equal(meldung('kalender', 'Jugend'), 'Kalender „Jugend“ gelöscht')
  assert.equal(meldung('auswahlwert', 'Orgel'), '„Orgel“ entfernt')
  assert.equal(meldung('gibtsnicht', 'x'), 'Rückgängig möglich')
  // Nie ein leerer Text, nie „undefined“.
  for (const vorgang of Object.keys(MELDUNGEN)) {
    const text = meldung(vorgang)
    assert.ok(text && !/undefined|null/.test(text), `${vorgang}: unbrauchbarer Text „${text}“`)
  }
})

test('undoText hängt den Namen nur an, wenn es einen gibt', () => {
  assert.equal(undoText('Aus Gruppe entfernt'), 'Aus Gruppe entfernt')
  assert.equal(undoText('Aus Gruppe entfernt', '  '), 'Aus Gruppe entfernt')
  assert.equal(undoText('Aus Gruppe entfernt', 'Erika'), 'Aus Gruppe entfernt: Erika')
  assert.equal(undoText('', ''), 'Erledigt')
})

// ── 4. Was NICHT vollständig zurückkommt, hat keine Rücknahme ─────────────

/**
 * Diese Aktionen sehen umkehrbar aus, sind es aber nicht — deshalb steht dort
 * eine Rückfrage (`bestaetigen`) statt `mitRueckgaengig`. Der Test hält BEIDES
 * fest: die Rückfrage ist da UND der falsche Rückgängig-Weg ist weg.
 */
const RUECKFRAGE_STATT_UMKEHR = [
  {
    datei: 'pages/Ressourcen.vue',
    titel: 'Buchung stornieren?',
    grund: 'Liste liefert keinen Zeitraum/Status/Notizen; neuer Eintrag wäre eine andere Buchung',
  },
  {
    datei: 'pages/GruppeDetail.vue',
    titel: 'Aus der Gruppe entfernen?',
    grund: 'Beitrittsdatum, Status und Notiz gehen beim Wiederaufnehmen verloren',
  },
]

test('nicht vollständig umkehrbar: Rückfrage statt Rückgängig', () => {
  for (const { datei, titel, grund } of RUECKFRAGE_STATT_UMKEHR) {
    const text = lies(datei)
    const code = ohneKommentare(text)
    assert.match(text, new RegExp(`titel: '${titel.replace(/[?]/g, '\\?')}'`),
      `${datei}: Rückfrage „${titel}“ fehlt (${grund})`)
    assert.match(code, /(^|[^.\w])bestaetigen\s*\(/m,
      `${datei}: die Rückfrage wird nicht gestellt (${grund})`)
    assert.equal(/mitRueckgaengig\(/.test(code), false,
      `${datei}: bietet noch „Rückgängig“ an, obwohl nicht vollständig (${grund})`)
    assert.equal(/useRueckgaengigAktion/.test(code), false,
      `${datei}: bindet den Rückgängig-Helfer noch ein (${grund})`)
  }
})

test('die Rückfragen nennen die Folge konkret (Prinzip I2)', () => {
  const ressourcen = lies('pages/Ressourcen.vue')
  assert.match(ressourcen, /lässt sich nicht zurücknehmen/)
  assert.match(ressourcen, /gefahr: true/)
  const gruppe = lies('pages/GruppeDetail.vue')
  assert.match(gruppe, /nicht wiederherstellbar/)
  assert.match(gruppe, /gefahr: true/)
})

// ── 5. Wächter: umkehrbare Aktionen fragen NICHT mehr ─────────────────────

/**
 * Rückfragen, die auf diesen Seiten BLEIBEN (Prinzip I2: eine Rückfrage ohne
 * Folge ist erlaubt, aber nicht für Umkehrbares). Schlüssel: Datei, Wert: die
 * Titel, die weiterhin `bestaetigen()` benutzen dürfen.
 */
const ERLAUBTE_RUECKFRAGEN = {
  // Freigabe auf der Website: das Schalten ist eine öffentliche Veröffentlichung;
  // der Verbund (Titel + Vorschautext) wird konkret genannt, bevor es passiert.
  'pages/Beitraege.vue': ['Beitrag auf der Website zeigen?'],
  // Freigaben auf der Website: Einschalten veröffentlicht (Titel, Zeiten,
  // Beschreibungen werden öffentlich). Das ist keine umkehrbare Aktion im
  // Sinne von I2 — die Rückfrage bleibt und nennt die Folge konkret.
  'pages/Website.vue': ['Kalender auf der Website zeigen?', 'Gruppe auf der Website zeigen?'],
  // Review 06.11.: MIT Bild ist das Löschen einer Ressource nicht umkehrbar
  // (`create_ressource` nimmt `bild` nicht an) — dann Rückfrage.
  'pages/RessourcenVerwaltung.vue': ['Ressource löschen?'],
  // Review 06.11.: Kalender aus dem Google-Import (`calender_details`) kommt
  // nicht vollständig zurück — dann Rückfrage.
  'pages/KalenderVerwaltung.vue': ['Kalender löschen?'],
}

/**
 * Je Seite: die Aktion ist umkehrbar → sofort ausführen, `mitRueckgaengig`
 * anmelden, und `bestaetigen(`/`loeschFrage(` kommen im Quelltext nicht mehr
 * vor (ein Rest wäre eine doppelte Rückfrage vor einer umkehrbaren Aktion).
 */
const UMKEHRBAR = [
  { datei: 'pages/Beitraege.vue', was: 'Beitrag löschen' },
  { datei: 'pages/Wiki.vue', was: 'Artikel löschen' },
  { datei: 'pages/Lieder.vue', was: 'Lied in den Papierkorb' },
  { datei: 'pages/KalenderVerwaltung.vue', was: 'Kalender löschen (ohne Google-Import)' },
  { datei: 'pages/RessourcenVerwaltung.vue', was: 'Ressource löschen (ohne Bild)' },
  { datei: 'pages/Website.vue', was: 'Postfach entfernen' },
]

test('umkehrbare Aktionen: sofort ausgeführt, am Stapel angemeldet, keine Rückfrage', () => {
  for (const { datei, was } of UMKEHRBAR) {
    const text = lies(datei)
    assert.match(text, /useRueckgaengigAktion/, `${datei}: ${was} meldet sich nicht am Stapel an`)
    assert.match(text, /mitRueckgaengig\(/, `${datei}: ${was} nutzt den Helfer nicht`)
    // Kein Bestätigen-Kommentar-Rest: `bestaetigen(` als Aufruf darf nicht mehr da sein.
    // Kommentare (Block und Zeile, auch mitten in der Zeile) zählen nicht als
    // Aufruf — der Wächter prüft den CODE, nicht die Erklärung.
    // Die ERLAUBTEN Rückfragen dieser Seite (Rückfrage ohne Folge, z. B.
    // „Beitrag auf der Website zeigen?“): sie sind nicht das Löschen. Die
    // Aufrufe werden VOR dem Kommentar-Strippen entfernt — ein Titel kann in
    // einem Blockkommentar stehen.
    const titre = ERLAUBTE_RUECKFRAGEN[datei] || []
    let code = text
    for (const titel of titre) {
      code = code.split(`bestaetigen({\n    titel: '${titel}`, `ERLAUBT({\n    titel: '${titel}`).join('')
    }
    code = ohneKommentare(code)
    const aufruf = /(^|[^.\w])bestaetigen\s*\(/m.test(code)
    assert.equal(aufruf, false, `${datei}: ${was} fragt noch nach, obwohl umkehrbar`)
  }
})

test('Seiten mit Bedingung fragen nur im nicht-umkehrbaren Fall nach', () => {
  // Beide Seiten prüfen ZUERST die Vollständigkeit und fragen nur dann nach;
  // sonst bleibt der Weg über den Stapel.
  for (const { datei, vorgang } of [
    { datei: 'pages/RessourcenVerwaltung.vue', vorgang: 'ressource' },
    { datei: 'pages/KalenderVerwaltung.vue', vorgang: 'kalender' },
  ]) {
    const code = ohneKommentare(lies(datei))
    assert.match(code, new RegExp(`if \\(!vollstaendig\\('${vorgang}'`),
      `${datei}: prüft die Vollständigkeit nicht vor der Rückfrage`)
    assert.match(code, new RegExp(`gegenrichtung\\('${vorgang}'`),
      `${datei}: ruft die Gegenrichtung nicht (mehr)`)
  }
})

test('Papierkorb-Löschungen melden die Frist des Servers (UX2b bleibt die Quelle)', () => {
  for (const datei of ['pages/Beitraege.vue', 'pages/Wiki.vue', 'pages/Lieder.vue']) {
    const text = lies(datei)
    assert.match(text, /papierkorbMeldung\(/, `${datei}: Frist wird nicht genannt`)
    assert.match(text, /wiederherstellen\(/, `${datei}: kein Weg zurück zum Server`)
  }
})

// ── 6. Wächter: endgültige Aktionen nutzen den EINEN Dialog ───────────────

/**
 * Je Seite: die Aktion ist endgültig → `DkEndgueltig` mit `titel` (Frage) und
 * `text` (Folge). Der alte Weg (`DkDialog` + eigener Bestätigungsknopf) darf
 * nicht mehr daneben stehen.
 */
const ENDGUELTIG = [
  { datei: 'pages/einstellungen/Datensicherung.vue', was: 'Sicherung löschen' },
  { datei: 'pages/devmodus/Befunde.vue', was: 'Befund löschen' },
  { datei: 'pages/Registrierung.vue', was: 'Link/Formular löschen' },
  { datei: 'components/planrahmen/LiederPflege.vue', was: 'Wert entfernen' },
]

test('endgültige Aktionen: der EINE Endgültig-Dialog, mit Frage und Folge', () => {
  for (const { datei, was } of ENDGUELTIG) {
    const text = lies(datei)
    assert.match(text, /import DkEndgueltig from/, `${datei}: ${was} nutzt DkEndgueltig nicht`)
    assert.match(text, /<DkEndgueltig/, `${datei}: ${was} rendert den Dialog nicht`)
    assert.match(text, /titel=/, `${datei}: ${was} ohne Frage als Titel`)
    assert.match(text, /:text=|text="/, `${datei}: ${was} ohne konkrete Folge`)
  }
})

test('RessourcenVerwaltung: Löschen ist umkehrbar — kein toter Endgültig-Import', () => {
  // UX2c-N2 (Klein): Die Seite braucht DkEndgueltig nicht mehr (Bild-Fall geht
  // über `bestaetigen()`); ein ungenutzter Import wäre toter Ballast.
  const text = lies('pages/RessourcenVerwaltung.vue')
  assert.equal(/import DkEndgueltig from/.test(text), false,
    'DkEndgueltig wird in RessourcenVerwaltung nicht mehr benutzt')
  assert.equal(/<DkEndgueltig/.test(text), false)
})

test('der Endgültig-Dialog selbst hält die Regeln ein', () => {
  const text = lies('components/ui/DkEndgueltig.vue')
  // Titel als Frage: der Standardtitel fragt.
  assert.match(text, /default: 'Wirklich endgültig\?'/)
  // Beim Schwersten Namenseingabe: Wort-Abfrage, Vergleich ohne Groß/Klein.
  assert.match(text, /bestaetigungswort/)
  assert.match(text, /toLowerCase\(\)/)
  // Gefährlicher Knopf, gesperrt bis die Eingabe stimmt.
  assert.match(text, /variant="danger"/)
  assert.match(text, /:disabled="!bereit"/)
  // Ausstieg links: ohne Eingabe heißt er „Schließen“ (Begriffe), Esc schließt
  // nicht während des Laufs.
  assert.match(text, /abbrechen: \{ type: String, default: 'Schließen' \}/)
  assert.match(text, /:dismissible="!laeuft"/)
  // Die Folge ist für die Sprachausgabe verknüpft (Review 06.11.).
  // UX2c-N2: der Bezug steht am Dialog-ELEMENT (`role="dialog"`) — an einem
  // rollenlosen <div> wird `aria-describedby` nicht vorgelesen.
  assert.match(text, /:beschrieben="beschrieben \? textId : ''"/,
    'DkEndgueltig muss die Kennung als `beschrieben` an DkDialog weiterreichen')
  assert.equal(/<div[^>]*aria-describedby/.test(text), false,
    'aria-describedby gehört nicht an ein rollenloses div im Körper')
  assert.match(text, /:id="textId"/)
  const dialog = lies('components/ui/DkDialog.vue')
  assert.match(dialog, /role="dialog"/)
  assert.match(dialog, /:aria-describedby="beschrieben \|\| undefined"/,
    'DkDialog muss aria-describedby am Element mit role="dialog" setzen')
  assert.match(dialog, /beschrieben: \{ type: String, default: '' \}/,
    'DkDialog braucht die Prop `beschrieben`')
  // Nur Tokens, keine festen Farbwerte (Wächter-Tokens-Regel).
  const stil = text.slice(text.indexOf('<style scoped>'))
  assert.equal(/#[0-9a-fA-F]{3,8}\b/.test(stil), false, 'feste Farbe im Stil')
  // Zeilenhöhe kommt aus dem Token, nicht als Literal (Review 06.11.).
  assert.equal(/line-height:\s*[\d.]/.test(stil), false,
    'line-height steht als Zahl im Stil statt var(--lh-text)')
  assert.match(stil, /line-height: var\(--lh-text\)/)
  const tokens = readFileSync(resolve(QUELLE, 'tokens.css'), 'utf8')
  assert.match(tokens, /--lh-text:\s*[\d.]+;/, 'tokens.css: --lh-text fehlt')
})

test('DkBestaetigung und DkEndgueltig sind zwei klar getrennte Bausteine', () => {
  // Die Ein-Zeilen-Rückfrage bleibt für Rückfragen OHNE Folge (z. B. eine
  // Freigabe einschalten) — sie darf nicht in den Endgültig-Dialog wandern.
  const kurz = lies('components/ui/DkBestaetigung.vue')
  assert.match(kurz, /bestaetigungAntwort/)
  assert.equal(/bestaetigungswort/.test(kurz), false)
  const lang = lies('components/ui/DkEndgueltig.vue')
  assert.match(lang, /export default|\bprops\b/)
})

// ── 7. wiederherstellen(): fachliche Ablehnung ist ein Fehler ─────────────

/**
 * `apiCall` wirft nicht bei jeder Ablehnung: ein whitelist-Endpunkt antwortet
 * auch mit `{success: false, message: '…'}`. Ohne Prüfung meldete die Seite
 * „wieder da“, obwohl nichts angelegt wurde — deshalb steht die Prüfung im
 * Modul und wird hier am Quelltext festgehalten (das Modul lädt `useApi.js`
 * erst bei Gebrauch, damit es ohne `node_modules` ladbar bleibt).
 */
test('wiederherstellen behandelt {success:false} als Fehler', () => {
  const text = readFileSync(
    resolve(QUELLE, 'composables/rueckgaengigWeg.mjs'), 'utf8')
  const rumpf = text.slice(text.indexOf('export async function wiederherstellen'))
  assert.match(rumpf, /antwort\.success === false/,
    'wiederherstellen prüft die fachliche Ablehnung nicht')
  assert.match(rumpf, /ok: false,\s*\n\s*fehler: antwort\.message/,
    'die Servermeldung wird nicht weitergegeben')
  assert.match(rumpf, /catch/, 'Netz-/Serverfehler werden nicht abgefangen')
})

test('Termin löschen und Gruppe löschen: schon ohne Rückfrage (Begründung im Test)', () => {
  // Review-Punkt 8: beide Stellen stehen NICHT in der Liste der 26
  // Rückfrage-Stellen, weil sie nie eine hatten — hier wird das festgehalten,
  // damit es nicht unbemerkt anders wird.
  //
  //  * Termin löschen (`KronosEventEdit.doDelete`): landet im Papierkorb
  //    (7 Tage). Der Bestätigungsschritt ist ein EINGEBAUTER Zustand im
  //    Fußbereich („Wirklich löschen? Ja/Nein") — kein `bestaetigen()`-Dialog,
  //    keine eigene Seite. Die Meldung nennt die Frist des Servers.
  //  * Gruppe löschen: in der Oberfläche gibt es KEINE Löschaktion für eine
  //    Gruppe (es gibt `delete_gruppe` im Server, aber keine Schaltfläche) —
  //    damit auch keine Rückfrage zu ersetzen. Bleibt so, bis eine Karte das
  //    Löschen in die Oberfläche bringt (dann: Papierkorb/Rückgängig prüfen).
  const edit = lies('components/kronos/KronosEventEdit.vue')
  assert.match(edit, /papierkorbMeldung\(/, 'Termin-Löschung nennt die Papierkorb-Frist nicht')
  assert.equal(/(^|[^.\w])bestaetigen\s*\(/m.test(ohneKommentare(edit)), false,
    'Termin-Löschung darf keine Rückfrage über bestaetigen() haben')
  const gruppen = lies('pages/Gruppen.vue') + lies('pages/GruppeDetail.vue')
  assert.equal(/delete_gruppe/.test(ohneKommentare(gruppen)), false,
    'Gruppen-Löschen ist in der Oberfläche (noch) nicht vorhanden — Erwartung anpassen, wenn es kommt')
})

test('der Helfer zeigt den Fehler als Meldung und lädt danach neu', () => {
  const text = lies('composables/useRueckgaengigAktion.js')
  assert.match(text, /showToast\(ergebnis\?\.fehler \|\| 'Das Zurücknehmen hat nicht geklappt\.', 'error'\)/)
  assert.match(text, /if \(typeof danach === 'function'\) await danach\(\)/)
})
