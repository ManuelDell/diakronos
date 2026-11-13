/**
 * MT-2 — Profilbild speichern unter dem Betriebs-Praefix.
 *
 * Befund (Manuel, Live-Test 11.11. auf dev.ecg-hn.de, Konto rebekka.fink):
 * Profilbild hochladen klappte, „Speichern“ antwortete mit 403 „Nur eigene
 * hochgeladene Dateien sind erlaubt.“
 *
 * Ursache war eine Versionsluecke zwischen den beiden Haelften der App:
 *   * `upload_file` gibt `file_url` mit Praefix aus (`base_path.datei_url`,
 *     WEB-5a) — die SPA bekommt `/diakronos/files/<name>`;
 *   * die `File`-Zeile in der Datenbank traegt weiter `/files/<name>`;
 *   * `update_profile_picture` verglich die Client-Adresse zeichengenau mit
 *     der DB-Zeile und fand so NIE einen Treffer — auch bei eigener Datei.
 * Dazu kam: der Antwort-Praefigierer des Routers kennt nur den Schluessel
 * `file_url`. `foto` heisst anders, blieb praefixfrei, und das
 * `<img :src="profile.foto">` lief unter `/diakronos` in ein 404.
 *
 * Geprueft wird hier der Quelltext — die Verhaltenspruefung (eigene Datei ok,
 * fremde 403, Datei abrufbar) steht in `backend/tests/
 * test_mt2_profilbild_praefix.py`. Getrennt, weil Node im Build-Stage laeuft
 * und kein Python startet.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = fileURLToPath(new URL('.', import.meta.url))
const BACKEND = join(HIER, '..', '..', 'backend', 'src', 'diakronos_app')

function backend(datei) {
  return readFileSync(join(BACKEND, datei), 'utf8')
}

function quelle() {
  return backend(join('api', 'profile.py'))
}

/**
 * MT-2c/MT-2d haben die Pruefungen an ihren neuen Ort verlagert. Gelesen wird
 * deshalb nicht mehr nur `profile.py`:
 *
 *   api/profile.py                     — `_eigene_datei_url` (Besitz + Adresse),
 *                                        `foto_mit_praefix` (Ausgabe-Praefix),
 *                                        `update_profile_picture` (Aufrufer)
 *   website/einwilligung.py            — `pruefe_foto_schreibweg` (die Schranke
 *                                        fuer alle generischen Schreibwege)
 *   frappe_compat/api_helpers.py       — `_pruefe_mitglied_schreibzugriff`
 *                                        (ruft die Schranke auf)
 *   base_path.py                       — `datei_url` + `_ABSOLUTE_ADRESSE`
 *
 * Alle vier muessen im Frontend-Stage des Images liegen (Regel 13,
 * `backend/Dockerfile`) — sonst ist dieser Test im Image rot, im Worktree gruen.
 */
const EINWILLIGUNG = join('website', 'einwilligung.py')
const HELFER = join('frappe_compat', 'api_helpers.py')
const BASIS = 'base_path.py'

/** Zeilenbereich einer Funktion `def <name>(` bis zum naechsten Top-Level-Def. */
function funktion(text, name) {
  const start = text.indexOf(`def ${name}(`)
  assert.notEqual(start, -1, `${name} nicht gefunden`)
  const rest = text.slice(start + 1)
  const ende = rest.search(/\n(?=def |@router|@whitelist|# ──)/)
  return ende === -1 ? rest : rest.slice(0, ende)
}

// ── 1. Adressmuster ─────────────────────────────────────────────────────────

test('MT-2b: das Adressmuster kennt die erlaubten Formen und weist Pfade ab', () => {
  const text = quelle()
  // MT-2b: aus `_DATEI_URL` (fest einkompiliert, `match` + `$`) wurde
  // `_datei_url_muster()` — das Muster wird je Aufruf aus `aktiver_praefix()`
  // gebaut, verglichen wird mit `fullmatch`. Ein beliebiges `/x/y/files/…`
  // ist seither KEINE Adresse dieser Installation mehr.
  assert.match(text, /def _datei_url_muster\(\)/,
    'das Adressmuster muss aus dem aktiven Praefix gebaut werden (MT-2b)')
  assert.match(text, /fullmatch\(str\(file_url or ''\)\)/,
    '`match` + `$` schluckt in Python ein abschliessendes Zeilenende — `fullmatch` noetig')
  assert.doesNotMatch(text, /_DATEI_URL\s*=\s*re\.compile\(/,
    'die fest einkompilierte `_DATEI_URL` mit beliebigem Praefix-Segment ist ersetzt')

  // Dasselbe Muster wie im Backend, hier als JS-Literal — Verhalten statt Text.
  // Erlaubt: praefixfrei oder mit dem AKTIVEN Praefix (`/diakronos`).
  const muster = /^(?:\/diakronos)?\/(?:private\/)?files\/([A-Za-z0-9._-]+)$/

  for (const gut of [
    '/files/abc-anna.jpg',
    '/private/files/abc-anna.jpg',
    '/diakronos/files/abc-anna.jpg',
    '/diakronos/private/files/abc-anna.jpg',
  ]) {
    assert.match(gut, muster, `gueltige Adresse abgelehnt: ${gut}`)
  }
  for (const boese of [
    '/diakronos/files/../files/x.jpg',
    '/diakronos/files/./x.jpg',
    '/diakronos/files/.../x.jpg',
    '/diakronos/files/sub/x.jpg',
    'https://fremd.example.org/files/x.jpg',
    'files/x.jpg',
    '/files/',
    '/files/a%2fb.jpg',
    '/files/x.jpg\n',
    '/x/y/files/x.jpg',
    '/gemeinde/unter/diakronos/files/x.jpg',
    '',
  ]) {
    assert.doesNotMatch(boese, muster, `ungueltige Adresse akzeptiert: ${boese}`)
  }
})

// ── 2. Speichern des Profilbilds ────────────────────────────────────────────

test('MT-2: update_profile_picture vergleicht Dateinamen, nicht die Client-URL', () => {
  // Der Endpunkt prueft nicht mehr selbst, sondern ruft `_eigene_datei_url`
  // (MT-2c). Die Zusicherung „Dateiname statt Client-String“ gilt deshalb an
  // ZWEI Stellen: der Aufruf hier und die Pruefung im Helfer.
  const koerper = funktion(quelle(), 'update_profile_picture')
  const helfer = funktion(quelle(), '_eigene_datei_url')

  assert.match(koerper, /file_url = _eigene_datei_url\(file_url\)/,
    'der Endpunkt muss die Besitz-/Formatpruefung ueber den gemeinsamen Helfer fuehren (MT-2c)')
  assert.match(helfer, /_dateiname_aus_file_url\(file_url\)/,
    'der Dateiname muss aus der Adresse gelesen werden (Praefix darf davorstehen)')
  assert.match(helfer, /FileModel\.file_url\.in_\(/,
    'beide DB-Formen (/files/…, /private/files/…) muessen abgefragt werden')
  assert.doesNotMatch(helfer, /FileModel\.file_url == file_url/,
    'ein zeichengenauer Vergleich mit der Client-URL ist genau der Fehler (unter /diakronos immer 403)')
  assert.doesNotMatch(koerper + helfer, /file_url not in \('\/files\//,
    'die alte Positivliste verglich die Client-Adresse zeichengenau')
})

test('MT-2: die Besitzpruefung bleibt bestehen (fremde Datei = 403)', () => {
  // DIE eine Besitzpruefung steht seit MT-2c in `_eigene_datei_url`
  // (`profile.py`) — nicht mehr im Endpunkt. Der Endpunkt darf sie nicht
  // umgehen, und `website/einwilligung.pruefe_foto_schreibweg` fuehrt die
  // generischen Schreibwege auf dieselbe Pruefung.
  const koerper = funktion(quelle(), 'update_profile_picture')
  const helfer = funktion(quelle(), '_eigene_datei_url')
  const schranke = funktion(backend(EINWILLIGUNG), 'pruefe_foto_schreibweg')
  const zugriff = funktion(backend(HELFER), '_pruefe_mitglied_schreibzugriff')

  assert.match(helfer, /FileModel\.owner == session\.user/,
    'die Datei muss dem Aufrufer gehoeren — die Pruefung wird NICHT entfernt')
  assert.match(helfer, /stored_path\(filename\) is None/,
    'eine DB-Zeile ohne Datei auf dem Datentraeger ist kein Eigentumsnachweis')
  assert.match(helfer, /Nur eigene hochgeladene Dateien sind erlaubt\./,
    'die Meldung bleibt')
  assert.match(koerper, /file_url = _eigene_datei_url\(file_url\)/,
    'update_profile_picture muss durch dieselbe Pruefung (kein zweiter Weg)')

  // Generic schreibwege (PUT /api/resource, frappe.client, doc.save/db_set):
  // `pruefe_foto_schreibweg` ruft `_eigene_datei_url` auf und wird aus der
  // zentralen Schranke heraus aufgerufen — ohne diese Kette waere `/foto`
  // ueber die generischen Wege ungeprueft.
  assert.match(schranke, /from diakronos_app\.api\.profile import _eigene_datei_url/,
    'die Schranke benutzt DIESELBE Besitzpruefung, keine zweite Regel')
  assert.match(schranke, /werte\["foto"\] = _eigene_datei_url\(wert\)/,
    'die Schranke entscheidet ueber die Besitzpruefung und schreibt die DB-Form zurueck')
  assert.match(zugriff, /pruefe_foto_schreibweg\(values, name\)/,
    'jeder generische Schreibweg laeuft durch die zentrale Schranke')
})

test('MT-2: `foto` wird praefigiert ausgegeben, aber praefixfrei gespeichert', () => {
  const text = quelle()
  const lesen = funktion(text, 'get_my_profile')
  const schreiben = funktion(text, 'update_profile_picture')
  const ausgabe = funktion(text, 'foto_mit_praefix')
  const adresse = funktion(backend(BASIS), 'datei_url')

  // MT-2c: `get_my_profile` ruft `foto_mit_praefix`; das ist der EINE
  // Praefigierer und laeuft ueber `base_path.datei_url` (MT-2b/MT-2d).
  // Ohne Praefix an `foto` liefert das <img :src="profile.foto"> unter
  // /diakronos ein 404 — der Router praefigiert nur den Schluessel `file_url`.
  assert.match(lesen, /"foto": foto_mit_praefix\(doc\.foto\)/,
    'ohne Praefix an `foto` liefert das <img :src="profile.foto"> unter /diakronos ein 404')
  assert.match(ausgabe, /_datei_mit_praefix\(wert\)/,
    'der Ausgabe-Praefigierer muss `foto` wirklich praefigieren')
  assert.match(text, /from diakronos_app\.base_path import datei_url/,
    'die eine Praefix-Quelle ist base_path.datei_url (WEB-5a)')
  // MT-2d: `datei_url` praefigiert direkt und erkennt absolute Adressen am
  // ANFANG (`_ABSOLUTE_ADRESSE`); ein Teilstring-Test `"://" in wert` waere
  // wieder der Fehler aus MT-2b.
  assert.match(adresse, /_ABSOLUTE_ADRESSE\.match\(wert\)/,
    'absolute Adressen werden am Anfang erkannt, nicht per Teilstring')
  assert.match(adresse, /return _AKTIV \+ wert/,
    '`datei_url` setzt den aktiven Praefix direkt davor')

  assert.match(schreiben, /file_url = _eigene_datei_url\(file_url\)/,
    'gespeichert wird nur, was die Besitzpruefung durchlaufen hat')
  assert.match(schreiben, /doc\.db_set\("foto", file_url or None\)/,
    'gespeichert wird die praefixfreie DB-Form (DB wird nicht migriert) — die Ausgabe-Form darf nicht in die Spalte wandern')
  assert.match(funktion(text, '_eigene_datei_url'), /return str\(file_doc\.file_url\)/,
    'zurueck kommt die DB-Form der File-Zeile (`/files/…`), nicht die praefigierte Client-Adresse')
})

test('MT-2: Praefixierung kommt aus base_path, nicht aus einer zweiten Regel', () => {
  const text = quelle()

  assert.match(text, /from diakronos_app\.base_path import datei_url/,
    'die eine Praefix-Quelle ist base_path.datei_url (WEB-5a)')
  assert.doesNotMatch(text, /("|\')\/diakronos\/files/,
    'der Praefix darf nirgends fest im Code stehen')
})
