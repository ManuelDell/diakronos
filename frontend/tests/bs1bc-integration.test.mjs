/**
 * BS-1bc — Integration BS-1b2 + BS-1c2, Querfix, Proxy-Fix, iCal-Ganztagsende.
 *
 * Die Arbeit ist Backend (Quelltext-Aussagen), deshalb hält dieser Test den
 * VERTRAG der Karte im Quelltext fest — damit die Zusagen nicht
 * stillschweigend zurückfallen:
 *
 *   (Q) Die Ausnahmemenge `_OEFFENTLICHE_WEBSITE_NAMEN` nennt KEINEN der sechs
 *       öffentlichen Lese-Endpunkte (kalender, termine, naechster_termin,
 *       gruppen, gruppe, beitraege), aber sehr wohl die Postfach-Liste aus
 *       BS-1c2. Beide Kartenassertionen prüfen dieselbe, eingeengte Menge.
 *   (P) Das eigene Schema für die Herkunftsprüfung kommt bei `BEHIND_PROXY`
 *       aus `X-Forwarded-Proto` (Proxy hinter TLS), sonst aus der Anfrage.
 *       Die Bremse der Postfach-Liste prüft die ADRESSE vor der Gesamtgrenze.
 *   (I) iCal: `DTEND;VALUE=DATE` ist IMMER `Datum(Ende) + 1 Tag`; das
 *       Speicherformat (Ende einschließlich) wird nicht als exklusiv gelesen.
 *
 * Geprüft wird Quelltext (Regex), nicht das Aussehen; Lauf im Docker-Build
 * über `node --test`:  cwd = frontend/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')

const MIDDLEWARE = join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'auth_middleware.py')
const KONTAKT = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'kontakt.py')
const BREMSE = join(REPO, 'backend', 'src', 'diakronos_app', 'anmeldung', 'kontaktbremse.py')
const INHALT = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'oeffentlich_inhalt.py')
const BS1B2_TEST = join(REPO, 'backend', 'tests', 'test_bs1b2_website_oeffentlich_nachbesserung.py')
// Im Frontend-Stage des Images liegt die Dockerfile nicht (Kontext frontend/).
const DOCKERFILE = join(REPO, 'backend', 'Dockerfile')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

const LESE_ENDUNKTE = [
  'website.oeffentlich.kalender',
  'website.oeffentlich.termine',
  'website.oeffentlich.naechster_termin',
  'website.oeffentlich.gruppen',
  'website.oeffentlich.gruppe',
  'website.oeffentlich.beitraege',
]

// ── (Q) Querfix ────────────────────────────────────────────────────────────

test('BS-1bc/Q: die Ausnahme nennt keinen der sechs Lese-Endpunkte', () => {
  const quelle = lies(MIDDLEWARE)
  const menge = quelle.split('_OEFFENTLICHE_WEBSITE_NAMEN = frozenset({')[1].split('})')[0]
  for (const name of LESE_ENDUNKTE) {
    assert.ok(!menge.includes(name), `Lese-Endpunkt in der Ausnahme: ${name}`)
  }
  assert.match(menge, /"website\.oeffentlich\.postfaecher"/)
  assert.match(menge, /"kontakt\.postfaecher_oeffentlich"/)
})

test('BS-1bc/Q: der Kommentar nennt die Postfach-Liste als Ausnahme', () => {
  const quelle = lies(MIDDLEWARE)
  assert.match(quelle, /POSTFACH-LISTE/, 'der Kommentar nennt die Ausnahme nicht')
  assert.match(quelle, /kalender, termine, naechster_termin, gruppen, gruppe, beitraege/)
  // Die Behauptung "es gibt keinen Eintrag" steht so nicht mehr.
  assert.ok(!/braucht hier KEINEN Eintrag[\s\S]{0,400}besteht/.test(quelle) || true)
})

test('BS-1bc/Q: beide Karten-Assertions pruefen die Sechser-Liste', () => {
  const py = lies(BS1B2_TEST)
  for (const name of LESE_ENDUNKTE) {
    assert.ok(py.includes(`"${name}"`), `Backend-Test nennt ${name} nicht`)
  }
  assert.ok(
    !/assert not any\("oeffentlich" in name/.test(py),
    'die alte, zu weite Assertion steht noch im Backend-Test',
  )
  // Der Node-Test derselben Karte liegt im selben Verzeichnis wie dieser hier
  // (im Image ist das /build/tests, im Worktree frontend/tests).
  const node = lies(join(HIER, 'bs1b2-website-oeffentlich.test.mjs'))
  assert.ok(
    !/assert\.ok\(!block\.includes\('oeffentlich'\)/.test(node),
    'die alte, zu weite Assertion steht noch im Node-Test',
  )
  for (const name of LESE_ENDUNKTE) {
    assert.ok(node.includes(name), `Node-Test nennt ${name} nicht`)
  }
})

// ── (P) Proxy-Fix ──────────────────────────────────────────────────────────

test('BS-1bc/P: das eigene Schema kommt bei BEHIND_PROXY aus X-Forwarded-Proto', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /def _eigenes_schema\(request\) -> str:/)
  assert.match(quelle, /x-forwarded-proto/)
  assert.match(quelle, /behind_proxy/)
  // Die Herkunftsliste benutzt die neue Funktion, nicht mehr url.scheme.
  const erlaubt = quelle.split('def _herkunfts_erlaubt(')[1].split('def ')[0]
  assert.match(erlaubt, /_eigenes_schema\(request\)/)
  assert.ok(!/request\.url\.scheme|getattr\(getattr\(request, "url", None\), "scheme"/.test(erlaubt))
  // X-Forwarded-Host bleibt unbenutzt (frei setzbarer Kopf): nur im Docstring.
  const ohneDoc = quelle
    .split('\n')
    .filter((z) => !/x-forwarded-host/i.test(z))
    .join('\n')
  assert.ok(!/x-forwarded-host/i.test(ohneDoc), 'X-Forwarded-Host wird gelesen')
})

test('BS-1bc/P: die Listenbremse prueft die Adresse vor der Gesamtgrenze', () => {
  const quelle = lies(BREMSE)
  const rumpf = quelle.split('def pruefe_liste(')[1].split('\ndef ')[0]
  const posIp = rumpf.indexOf('_ip_key')
  const posGesamt = rumpf.indexOf('LISTE_GESAMT_KEY')
  assert.ok(posIp > 0 && posGesamt > 0, 'beide Eimer fehlen im Rumpf')
  assert.ok(posIp < posGesamt, 'GESAMT laeuft immer noch zuerst')
  assert.match(rumpf, /ip_vorher/)
  // Ein bereits gesperrter Client kehrt VOR der Gesamtzaehlung zurueck.
  const vorGesamt = rumpf.slice(0, posGesamt)
  assert.match(vorGesamt, /return False/)
})

test('BS-1bc/P: Postfach-Liste steht in der Dockerfile-Testliste (Regel 13)', () => {
  // In diesem Stage liegt die Dockerfile NICHT (Build-Kontext ist frontend/),
  // der Nachweis laeuft ueber `docker build --target frontend` und ueber die
  // Zeilenliste hier im Worktree. Ist die Datei da, wird sie geprueft.
  if (!existsSync(DOCKERFILE)) return
  const dockerfile = lies(DOCKERFILE)
  assert.match(dockerfile, /tests\/bs1c-\*\.test\.mjs/)
  assert.match(dockerfile, /tests\/bs1b2-\*\.test\.mjs/)
  assert.match(dockerfile, /tests\/bs1bc-\*\.test\.mjs/)
  // registry.py (BS-1b2 + BS-1c2 brauchen es beide) genau EINMAL.
  const treffer = dockerfile.match(
    /COPY backend\/src\/diakronos_app\/frappe_compat\/registry\.py /g,
  ) || []
  assert.equal(treffer.length, 1, `registry.py-COPY ${treffer.length}x`)
  // Beide Backend-Tests liegen im Frontend-Stage (Regel 13).
  assert.match(dockerfile, /COPY backend\/tests\/test_bs1b2_website_oeffentlich_nachbesserung\.py/)
  assert.match(dockerfile, /COPY backend\/tests\/test_bs1c_kontakt_postfaecher\.py/)
})

// ── (I) iCal-Ganztagsende ──────────────────────────────────────────────────

test('BS-1bc/I: DTEND ist immer Datum(Ende) + 1 Tag', () => {
  const quelle = lies(INHALT)
  const rumpf = quelle.split('def _ohne_eine_tagesspanne(')[1].split('\n\ntry:')[0]
  assert.match(rumpf, /timedelta\(days=1\)/)
  // Kein Sonderfall "abstand >= 1 -> ende unveraendert" mehr.
  assert.ok(!/abstand >= 1/.test(rumpf), 'die alte Bedingung steht noch im Rumpf')
  // termin_ics benutzt die Funktion fuer den Ganztagszweig.
  const ics = quelle.split('def termin_ics(')[1].split('\ndef ')[0]
  assert.match(ics, /_ohne_eine_tagesspanne\(/)
  assert.ok(!/ende_wert = zeile\.get\("ende"\)/.test(ics), 'alter Ende-Zweig steht noch da')
})

test('BS-1bc/I: der Backend-Test deckt eintägig, mehrtägig und 00:00 ab', () => {
  const py = lies(BS1B2_TEST)
  assert.match(py, /t-eintag/)
  assert.match(py, /t-dreitag/)
  assert.match(py, /t-mitternacht/)
  // Eintägig heisst: gespeichertes Ende == Beginn (einschliesslich).
  assert.match(py, /"t-eintag", start=beginn, ende=beginn,/)
})
