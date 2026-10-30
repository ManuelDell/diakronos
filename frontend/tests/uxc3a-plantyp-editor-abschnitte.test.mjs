/**
 * UX-C3a — Plantyp-Editor: Sprungleiste links, Erklärspalte rechts
 * (Entwurf C3, Manuel 2026-10-23; Befund DMB-674355ec0e2b).
 *
 * Der Editor ist sehr lang. Statt zu scrollen springt man über die
 * Abschnittsliste (Grunddaten · Termine · Felder · Anlässe · Regeln ·
 * Ansichten); rechts erklärt eine feste Spalte die Begriffe, deshalb braucht
 * es keine Info-Symbole mehr.
 *
 * Geprüft wird hier:
 *   1. gegenstandsLOS  die Sprungziele: sechs Abschnitte in der Reihenfolge
 *                      der Seite, jede Kennung steht GENAU EINMAL im Markup
 *                      (Dubletten-IDs brechen den Sprung).
 *   2. die Regel des aktiven Abschnitts (Lesekante, vor dem ersten, hinter
 *      dem letzten).
 *   3. die Erklärspalte: Texte stammen aus der Doku (Quelle je Begriff),
 *      jeder Abschnitt hat Erklärungen, keine Lücke ohne Platzhalter.
 *   4. das Markup der Seite: Raster dreispaltig ab 1200 px, darunter ohne
 *      Erklärspalte, unter 900 px waagerechte Leiste (Entwurf C3).
 *   5. Hausregeln: nur Tokens (keine harten Farbwerte), kein „Plantyp“ in
 *      neuen Texten (Glossar S15), Test in der Dockerfile-Liste.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ABSCHNITTE, BAND_PX, ENDE_PUFFER, ERSTER_ABSCHNITT, ERKLAERUNGEN, ERKLAERSPALTE_AB_PX, LESEKANTE, PLATZHALTER,
  SCHMAL_AB_PX, aktiverAbschnitt, erklaerung, erklaerungenFuer, erklaerspalteZeigen, istMessbar, lesekanteFuer, zaehler, zielId,
} from '../src/diakonos/components/planrahmen/abschnitte.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const SEITE = lies('pages/planrahmen/PlantypEditor.vue')
const SPRUNG = lies('components/planrahmen/PrSprungleiste.vue')
const ERKLAERUNG = lies('components/planrahmen/PrErklaerung.vue')
const REIHEN = lies('components/planrahmen/PrReihenEditor.vue')

// ── 1 · Sprungziele ────────────────────────────────────────────────────────

test('UX-C3a: sechs Abschnitte in der Reihenfolge des Auftrags', () => {
  assert.deepEqual(ABSCHNITTE.map((a) => a.id),
    ['grunddaten', 'termine', 'felder', 'anlaesse', 'regeln', 'ansichten'])
  assert.deepEqual(ABSCHNITTE.map((a) => a.name),
    ['Grunddaten', 'Termine', 'Felder', 'Anlässe', 'Regeln', 'Ansichten'])
  assert.equal(ERSTER_ABSCHNITT, 'grunddaten')
})

test('UX-C3a: jede Sprungkennung steht genau einmal im Markup', () => {
  // Fünf Abschnitte tragen ihre Kennung als Abschnittsüberschrift der Seite;
  // „Felder“ trägt sie an der Zwischenüberschrift im Baustein (PrReihenEditor).
  for (const a of ABSCHNITTE) {
    // Gezählt wird das Setzen der ID, nicht jede Erwähnung: `zielId('x')`
    // steht im :id UND im :data-abschnitt.
    const inSeite = SEITE.match(new RegExp(`:id="zielId\\('${a.id}'\\)"`, 'g')) || []
    // Das alte, von Hand gesetzte Ziel darf nicht stehen bleiben.
    assert.ok(!SEITE.includes(`id="pr-pe-${a.id}"'`))
    if (a.id !== 'felder') {
      assert.equal(inSeite.length, 1, `${a.id}: erwartet 1 Sprungziel, gefunden ${inSeite.length}`)
    }
  }
  // Die alte ID des Bausteins „Termine und Felder“ stand von Hand im Markup.
  assert.ok(SEITE.includes(`:id="zielId('termine')"`))
  // „Felder“ hat sein Sprungziel im Baustein, nicht in der Seite selbst —
  // sonst gäbe es zwei Elemente mit derselben Kennung.
  assert.equal((SEITE.match(/:id="zielId\('felder'\)"/g) || []).length, 0)
  assert.match(REIHEN, /:id="felderAnker \|\| undefined"/)
})

test('UX-C3a: „Felder“ springt in den Feld-Teil, nicht hinter den Block', () => {
  // Review 24.10.: der Anker stand als leeres div HINTER „Termine und Felder“
  // — der Sprung landete bei „Anlässe“. Jetzt trägt die Zwischenüberschrift
  // „Felder pro Termin“ im Baustein die Kennung, gespeist aus derselben Quelle
  // wie die Sprungliste.
  assert.ok(!SEITE.includes('pr-pe-anker'), 'toter Anker-Halt steht noch im Markup')
  assert.match(SEITE, /:felder-anker="zielId\('felder'\)"/)
  // Im Baustein sitzt die Kennung an der Zwischenüberschrift, und zwar nur,
  // wenn sie von außen kommt (`undefined` sonst — kein leeres id="").
  assert.match(REIHEN, /<h4 class="pr-re-titel" :id="felderAnker \|\| undefined" :data-abschnitt="felderAnker \|\| undefined">Felder pro Termin<\/h4>/)
  assert.match(REIHEN, /felderAnker: \{ type: String, default: '' \}/)
  // Der Anker steht INNERHALB des Abschnitts „Termine“.
  const abschnitt = SEITE.slice(SEITE.indexOf(`:id="zielId('termine')"`), SEITE.indexOf(`:id="zielId('anlaesse')"`))
  assert.ok(abschnitt.includes(':felder-anker="zielId(\'felder\')"'),
    'Felder-Anker liegt nicht mehr im Abschnitt „Termine“')
})

test('UX-C3a: das Band der Sprungleiste zählt zur Lesekante', () => {
  // Klick auf „Felder“ landet bei `scrollIntoView(block:'start')`: die
  // Überschrift steht an der Oberkante des Behälters (top = 0) — also HINTER
  // dem klebenden Band und damit im Bild nicht als „Felder“ erkennbar. Mit der
  // alten Regel galt sie trotzdem als erreicht; nach dem Nachmessen fiel die
  // Markierung deshalb auf den nächsten Abschnitt.
  const amZiel = [
    { id: 'grunddaten', top: -1400 },
    { id: 'termine', top: -700 },
    { id: 'felder', top: 0 },
    { id: 'anlaesse', top: 600 },
    { id: 'regeln', top: 1400 },
    { id: 'ansichten', top: 2100 },
  ]
  assert.equal(aktiverAbschnitt(amZiel, LESEKANTE), 'felder')
  // Bleiben alle erreichten hinter dem Band (weit gescrollt), gilt der
  // zuletzt erreichte — beim Öffnen der erste Abschnitt, sonst der letzte
  // passierte. Ein Sprung auf einen unsichtbaren Abschnitt gibt es nicht.
  const alle = ABSCHNITTE.map((a) => ({ id: a.id, top: -BAND_PX - 5 }))
  assert.equal(aktiverAbschnitt(alle, LESEKANTE), ABSCHNITTE[ABSCHNITTE.length - 1].id)
  // Senkrechte Leiste (ab 900 px): Lesekante unverändert.
  assert.equal(lesekanteFuer(1366), LESEKANTE)
  assert.equal(lesekanteFuer(SCHMAL_AB_PX), LESEKANTE)
  // Waagerechte Leiste unter 900 px: das Band liegt über der Seite, die
  // Lesekante wächst entsprechend.
  assert.equal(lesekanteFuer(899), LESEKANTE + BAND_PX)
  assert.equal(lesekanteFuer(390), LESEKANTE + BAND_PX)
  assert.ok(BAND_PX > 0 && BAND_PX < LESEKANTE)
})

test('UX-C3a: ausgeblendete Abschnitte liefern keine Position', () => {
  // JSON/Probelauf-Reiter: die Abschnitte sind `display:none` und liefern
  // Rechtecke der Größe 0. Ein 0 darf nicht als „ganz oben“ gelten.
  assert.equal(istMessbar({ top: 500, width: 0, height: 0 }), false)
  assert.equal(istMessbar({ top: 500, width: 500, height: 0 }), false)
  assert.equal(istMessbar({ top: 500, width: 500, height: 40 }), true)
  assert.equal(istMessbar(null), false)
  assert.match(SEITE, /istMessbar\(kasten\) \? kasten\.top - oben : Number\.POSITIVE_INFINITY/)
})

test('UX-C3a: die Sprungliste führt alle Abschnitte und markiert den aktiven', () => {
  assert.match(SPRUNG, /v-for="a in abschnitte"/)
  assert.match(SPRUNG, /:class="\{ 'is-aktiv': a\.id === aktiv \}"/)
  assert.match(SPRUNG, /:aria-current="a\.id === aktiv \? 'true' : undefined"/)
  assert.match(SPRUNG, /:href="'#' \+ zielId\(a\.id\)"/)
  assert.match(SPRUNG, /@click\.prevent="\$emit\('springen', a\.id\)"/)
  assert.match(SPRUNG, /defineEmits\(\['springen'\]\)/)
})

test('UX-C3a: Zähler nur wo eine Zahl etwas aussagt', () => {
  assert.equal(zaehler('grunddaten', { felder: [1, 2] }), null)
  assert.equal(zaehler('termine', { anlaesse: [1] }), null)
  assert.equal(zaehler('felder', { felder: [1, 2, 3] }), 3)
  assert.equal(zaehler('anlaesse', { anlaesse: [{}, {}] }), 2)
  assert.equal(zaehler('regeln', { regeln: [] }), 0)
  assert.equal(zaehler('ansichten', {}), 0)
})

// ── 2 · Aktiver Abschnitt ──────────────────────────────────────────────────

test('UX-C3a: vor dem ersten Abschnitt gilt der erste', () => {
  // Seite ganz oben: der erste Abschnitt steht UNTER der Lesekante, der
  // letzte ist weit weg — es bleibt beim ersten.
  const p = ABSCHNITTE.map((a, i) => ({ id: a.id, top: 40 + i * 600 }))
  assert.equal(aktiverAbschnitt(p, 120), 'grunddaten')
  // Auch wenn der letzte Abschnitt zufällig knapp unter der Kante steht, darf
  // der Seitenende-Puffer NICHT greifen, solange die Seite noch weitergeht —
  // sonst wäre beim Öffnen schon der letzte Eintrag markiert (im Bild gefunden).
  const kurz = [{ id: 'grunddaten', top: 40 }, { id: 'termine', top: 260 }]
  assert.equal(aktiverAbschnitt(kurz, 120), 'grunddaten')
})

test('UX-C3a: die Lesekante entscheidet, nicht die Oberkante', () => {
  const p = [
    { id: 'grunddaten', top: -400 },   // längst vorbei
    { id: 'termine', top: 20 },        // 20 - 120 <= 0 -> aktiv
    { id: 'felder', top: 260 },        // 260 - 120 > 0 -> noch nicht
  ]
  // Kein Seitenende (hinter „felder“ ginge es weiter) -> es bleibt bei „termine“.
  const q = [...p, { id: 'anlaesse', top: 2000 }]
  assert.equal(aktiverAbschnitt(q, 120), 'termine')
  // Mit einer Lesekante weit oben gilt der erste Abschnitt.
  assert.equal(aktiverAbschnitt(q, 10), 'grunddaten')
})

test('UX-C3a: am Seitenende gilt der letzte Abschnitt', () => {
  // Am Seitenende stehen die unteren Abschnitte schon im Bild, der letzte
  // knapp über oder nur wenig unter der Lesekante.
  const p = ABSCHNITTE.map((a, i) => ({ id: a.id, top: -2200 + i * 460 }))
  assert.ok(p[p.length - 1].top - LESEKANTE <= ENDE_PUFFER)
  assert.equal(aktiverAbschnitt(p, LESEKANTE), 'ansichten')
  // Ein einzelner Abschnitt, der die Kante nicht erreicht, gilt trotzdem.
  assert.equal(aktiverAbschnitt([{ id: 'grunddaten', top: 60 }], LESEKANTE), 'grunddaten')
  // Steht der letzte weiter als der Puffer unter der Kante, bleibt der
  // zuletzt erreichte Abschnitt.
  const q = p.slice(0, -1).concat([{ id: 'ansichten', top: 600 }])
  assert.equal(aktiverAbschnitt(q, LESEKANTE), 'regeln')
})

test('UX-C3a: fehlende oder unbrauchbare Messwerte kippen nichts', () => {
  assert.equal(aktiverAbschnitt([], 120), ERSTER_ABSCHNITT)
  assert.equal(aktiverAbschnitt(null, 120), ERSTER_ABSCHNITT)
  assert.equal(aktiverAbschnitt([{ id: 'grunddaten', top: Number.POSITIVE_INFINITY }], 120), 'grunddaten')
  assert.equal(aktiverAbschnitt([{ id: 'termine', top: 0 }, { top: 5 }], 120), 'termine')
})

test('UX-C3a: die Seite misst am scrollenden Behälter und drosselt', () => {
  // Die App scrollt in .dk-content, nicht im Fenster — sonst rechnet die
  // Lesekante gegen den falschen Nullpunkt.
  assert.match(SEITE, /document\.querySelector\('\.dk-content'\)/)
  assert.match(SEITE, /requestAnimationFrame/)
  assert.match(SEITE, /addEventListener\('scroll', beiScroll, \{ passive: true \}\)/)
  assert.match(SEITE, /removeEventListener\('scroll', beiScroll\)/)
  // Nach dem Sprung wird nachgemessen (sonst springt die Markierung zurück).
  assert.match(SEITE, /setTimeout\(aktivenAbschnittMessen, \d+\)/)
  // Und das Sprungziel bleibt markiert, bis man selbst weiterscrollt.
  assert.match(SEITE, /if \(sprungZiel\) \{\s*aktiverAbschnittId\.value = sprungZiel/)
  assert.match(SEITE, /sprungZiel = id/)
  assert.match(SEITE, /if \(sprungZiel && \+\+sprungMessungen > 1\)/)
  // Die Messung nutzt die Lesekante der aktuellen Breite (Band der Leiste).
  assert.match(SEITE, /aktiverAbschnitt\(abschnittPositionen\(\), lesekanteFuer\(breiteAmFenster\.value\)\)/)
})

test('UX-C3a: beim Verlassen wird derselbe Behälter abgemeldet', () => {
  // Review 24.10. (NIEDRIG): `scrollBehaelter()` lieferte beim Abbau einen
  // anderen Knoten (bzw. null) als beim Aufbau — die Anmeldung blieb stehen.
  assert.match(SEITE, /gemerkterBehaelter = scrollBehaelter\(\)/)
  assert.match(SEITE, /gemerkterBehaelter\?\.addEventListener\('scroll', beiScroll, \{ passive: true \}\)/)
  assert.match(SEITE, /gemerkterBehaelter\?\.removeEventListener\('scroll', beiScroll\)/)
  assert.ok(!/^\s*scrollBehaelter\(\)\?\.removeEventListener/m.test(SEITE),
    'Abbau fragt den Behälter erneut ab statt den gemerkten zu nutzen')
  // Und der Sprung-Zeitgeber wird gelöscht (er schrieb sonst nach dem Abbau).
  const abbau = SEITE.slice(SEITE.indexOf('onUnmounted('))
  assert.match(abbau, /clearTimeout\(sprungZielTimer\)/)
  assert.match(abbau, /sprungZiel = ''/)
})

// ── 3 · Erklärspalte ───────────────────────────────────────────────────────

test('UX-C3a: jeder Begriff nennt seine Quelle in der Doku', () => {
  assert.ok(ERKLAERUNGEN.length >= 12)
  for (const e of ERKLAERUNGEN) {
    assert.ok(e.id && e.begriff && e.text, `unvollständig: ${e.id}`)
    assert.match(e.quelle, /^(LEITFADEN|REFERENZ|GLOSSAR)\.md/, `${e.id}: Quelle fehlt`)
    assert.ok(e.text.length >= 40, `${e.id}: Erklärung zu kurz`)
    // Kein Fachjargon ohne Erklärung, kein „Plantyp“ (Glossar S15).
    assert.ok(!/Plantyp/.test(e.text), `${e.id}: „Plantyp“ statt „Planvorlage“`)
  }
  const ids = ERKLAERUNGEN.map((e) => e.id)
  assert.equal(new Set(ids).size, ids.length, 'Begriff doppelt erklärt')
})

test('UX-C3a: jeder Abschnitt hat Erklärungen, Lücken stehen als Platzhalter', () => {
  for (const a of ABSCHNITTE) {
    const liste = erklaerungenFuer(a.id)
    assert.ok(liste.length >= 2, `${a.id}: zu wenige Erklärungen`)
    for (const e of liste) assert.ok(e.text && e.text !== PLATZHALTER, `${a.id}/${e.id}: Platzhalter offen`)
  }
  // Ein unbekannter Abschnitt erklärt alles (nichts bleibt unerklärt).
  assert.equal(erklaerungenFuer('gibtesnicht').length, ERKLAERUNGEN.length)
  assert.equal(erklaerung('kennung').begriff, 'Kennung')
  assert.equal(erklaerung('gibtesnicht'), null)
})

test('UX-C3a: die Spalte zeigt die Begriffe des Abschnitts und blendet sich schmal aus', () => {
  assert.match(ERKLAERUNG, /Was bedeutet das\?/)
  assert.match(ERKLAERUNG, /:aria-hidden="sichtbar \? undefined : 'true'"/)
  assert.match(ERKLAERUNG, /@media \(max-width: 1199px\)/)
  assert.equal(ERKLAERSPALTE_AB_PX, 1200)
  assert.equal(erklaerspalteZeigen(1366), true)
  assert.equal(erklaerspalteZeigen(1200), true)
  assert.equal(erklaerspalteZeigen(1199), false)
  assert.equal(erklaerspalteZeigen(390), false)
  // Die Begriffe des aktiven Abschnitts stehen zuerst (Reihenfolge des Textes).
  const grunddaten = erklaerungenFuer('grunddaten').map((e) => e.id)
  assert.deepEqual(grunddaten, ['kennung', 'anzeigename', 'dienstbereich', 'personenpool'])
})

// ── 3b · Quellenangaben gegen die Doku prüfen ──────────────────────────────

/** Die Doku liegt im Python-Paket (kein docs/ im Image) — Pfad wie im Backend. */
const DOKU = new URL('../../backend/src/diakronos_app/planrahmen/doku/', import.meta.url)

/** Zeile `nr` (1-basiert) einer Doku-Datei — `null`, wenn es sie nicht gibt. */
function dokuZeile(datei, nr) {
  const pfad = new URL(datei, DOKU)
  if (!existsSync(pfad)) return null
  return readFileSync(pfad, 'utf8').split('\n')[nr - 1] ?? null
}

test('UX-C3a: die Quellenangaben zeigen auf die richtigen Doku-Zeilen', () => {
  // Review 24.10. (NIEDRIG): vier Angaben waren ungenau. Sie werden hier an
  // der echten Datei festgenagelt, damit sie nicht wieder abrutschen. Im Image
  // liegt die Doku unter backend/src/... nicht — dort entfällt die Prüfung,
  // der Nachweis läuft dann im Repo (Makefile/CI) und beim Bau.
  if (!existsSync(new URL('REFERENZ.md', DOKU))) {
    assert.ok(ERKLAERUNGEN.every((e) => e.quelle), 'Quelle fehlt')
    return
  }
  const erwartet = [
    // [Begriff, Datei, Zeile, Muster in der Zeile]
    ['kennung', 'REFERENZ.md', 11, /`id`/],
    ['anzeigename', 'REFERENZ.md', 14, /`name`/],
    ['personenpool', 'REFERENZ.md', 27, /`gruppen`/],
    ['stufe', 'REFERENZ.md', 316, /`stufe`/],
  ]
  for (const [id, datei, nr, muster] of erwartet) {
    const zeile = dokuZeile(datei, nr)
    assert.ok(zeile !== null, `${datei}: Zeile ${nr} fehlt`)
    assert.match(zeile, muster, `${datei}:${nr} ist nicht ${id}`)
    assert.ok(erklaerung(id).quelle.includes(`${datei}:${nr}`),
      `${id}: Quelle nennt nicht ${datei}:${nr}`)
  }
})

test('UX-C3a: „unbekannter Bereich“ ist belegt, nicht behauptet', () => {
  // Der alte Satz sprach von einer „Warnung“. Belegt ist ein FEHLER beim
  // Speichern/Probelauf (dienste.py: „Dienstbereich nicht gefunden.“). Diese
  // Prüfung hängt die Aussage an den Code, damit sie nicht wieder abdriftet.
  const text = erklaerung('dienstbereich').text
  assert.ok(!/Warnung/.test(text), '„Warnung“ ist im Code nicht belegt')
  assert.match(text, /Fehler/)
  const dienste = new URL('../../backend/src/diakronos_app/planrahmen/dienste.py', import.meta.url)
  if (!existsSync(dienste)) return
  const quelle = readFileSync(dienste, 'utf8')
  assert.ok(quelle.includes('Dienstbereich nicht gefunden.'),
    'dienste.py meldet einen unbekannten Bereich nicht (mehr)')
})

// ── 4 · Raster und Umbruch ─────────────────────────────────────────────────

test('UX-C3a: ab 1200 px drei Spalten, unter 900 px waagerechte Leiste', () => {
  const css = SEITE.slice(SEITE.indexOf('<style'))
  assert.match(css, /\.pr-pe-raster--mit-erklaerung \{ grid-template-columns: 190px minmax\(0, 1fr\) 300px; \}/)
  assert.match(css, /@media \(max-width: 1199px\) \{\s*\.pr-pe-raster \{ grid-template-columns: 170px minmax\(0, 1fr\); \}/)
  assert.match(css, /@media \(max-width: 900px\) \{\s*\.pr-pe-raster \{ grid-template-columns: 1fr;/)
  const sprungCss = SPRUNG.slice(SPRUNG.indexOf('<style'))
  assert.match(sprungCss, /@media \(max-width: 900px\)[\s\S]*?flex-direction: row;/)
  // Die Erklärspalte sitzt im Raster und nur im Formular-Reiter.
  assert.match(SEITE, /'pr-pe-raster--mit-erklaerung': erklaerungZeigen/)
})

test('UX-C3a: das Raster gilt nur für den Formular-Reiter', () => {
  // Review 24.10. (HOCH): das Raster umschloss auch JSON und Probelauf — beide
  // landeten in der 190-px-Spalte. Jetzt trägt das Raster selbst das v-if, und
  // die beiden anderen Reiter stehen als Geschwister daneben.
  assert.match(SEITE, /<div\s+v-if="reiter === 'formular'"\s+class="pr-pe-raster"/)
  assert.match(SEITE, /<div v-else-if="reiter === 'json'" class="pr-pe-json">/)
  assert.match(SEITE, /<div v-else-if="reiter === 'probelauf'" class="pr-pe-probe" id="pr-pe-probelauf">/)
  // Die Erklärspalte steht INNERHALB des Rasters (vor dessen Schluss), JSON
  // und Probelauf dahinter — sonst wären sie wieder Rasterkinder.
  const rumpf = SEITE.slice(SEITE.indexOf('<div\n        v-if="reiter === \'formular\''))
  const rasterEnde = rumpf.indexOf('<div v-else-if="reiter === \'json\'"')
  const erklaerungPos = rumpf.indexOf('<PrErklaerung')
  const formPos = rumpf.indexOf('<div class="pr-pe-form">')
  assert.ok(formPos > -1 && erklaerungPos > formPos && erklaerungPos < rasterEnde,
    'Reihenfolge im Raster stimmt nicht (Formular · Erklärung · Ende)')
  // Die Sprungleiste hängt nicht mehr an einem eigenen v-if (das Raster ist
  // jetzt der Reiter-Filter) — sonst stünde `reiter === 'formular'` doppelt.
  assert.equal((SEITE.match(/v-if="reiter === 'formular'"/g) || []).length, 1)
  // Der Sonderfall aus dem alten CSS ist mit dem Raster entfallen.
  assert.ok(!/.pr-pe-raster--mit-erklaerung > .pr-pe-form/.test(SEITE))
})

test('UX-C3a: der Felder-Anker hat seinen Scroll-Abstand im Kind-Baustein', () => {
  // Scoped-CSS der Seite erreicht keine Elemente im Kind (das Scoped-Attribut
  // fehlt dort) — `.pr-pe-abschnitt [data-abschnitt]` lief ins Leere und die
  // Überschrift klebte mit scroll-margin 0 unter dem Band. Der Abstand steht
  // deshalb in PrReihenEditor.vue, wo die Überschrift wohnt.
  const reiterCss = REIHEN.slice(REIHEN.indexOf('<style'))
  assert.match(reiterCss, /\.pr-re-titel \{ scroll-margin-top: 90px;/)
  assert.ok(!/\.pr-pe-abschnitt \[data-abschnitt\]/.test(SEITE),
    'toter Selektor für das Kind-Element steht noch in der Seite')
})

// ── 5 · Hausregeln ─────────────────────────────────────────────────────────

test('UX-C3a: keine harten Farbwerte in den neuen Bausteinen', () => {
  for (const [name, text] of [['PrSprungleiste.vue', SPRUNG], ['PrErklaerung.vue', ERKLAERUNG]]) {
    const stil = text.slice(text.indexOf('<style'))
    const farben = stil.match(/#[0-9a-fA-F]{3,8}\b|rgba?\(/g) || []
    assert.deepEqual(farben, [], `${name}: harte Farbwerte ${farben.join(', ')}`)
  }
})

test('UX-C3a: die Testdatei steht in der Node-Liste des Images', () => {
  // Im Image liegt nur frontend/ (/build) — die Dockerfile steht dort NICHT.
  // Im Repo wird der Eintrag geprüft; im Image ist der Nachweis, dass dieser
  // Test ÜBERHAUPT läuft (er steht in der Liste, sonst gäbe es ihn nicht).
  const dockerfile = new URL('../../backend/Dockerfile', import.meta.url)
  if (!existsSync(dockerfile)) return
  assert.ok(readFileSync(dockerfile, 'utf8').includes('tests/uxc3a-*.test.mjs'),
    'backend/Dockerfile: uxc3a fehlt in der Node-Testliste')
})
