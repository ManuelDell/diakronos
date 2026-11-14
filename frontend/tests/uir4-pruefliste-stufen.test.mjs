/**
 * UI-R4 — Node-Test: Moderationsstufen in der Prüfliste.
 *
 * Die Regeln aus `freigabeStufen.mjs` werden AUSGEFÜHRT (keine Quelltext-
 * Muster): Stufennamen aus der Server-Quelle, „darf prüfen“ fail-closed,
 * Warteline, ehrliche Freigabe-Meldung (aus der SERVER-Antwort abgeleitet),
 * verständliche Verweigerung und die Zeilen der Freigabe-Anträge.
 *
 * Der Test liest nur Dateien innerhalb von frontend/ und braucht kein Netz.
 * Die Stufen-Titel holt er aus einem nachgebauten `get_rollen_erklaerung`
 * (genau die Felder, die R-12 liefert).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const F = await import(pathToFileURL(join(SRC, 'components/kronos/freigabeStufen.mjs')).href)

// Die Titel, die der Server liefert (`rechte/erklaerung.py`, R-12).
const SERVER_TITEL = {
  untergruppe: 'Untergruppe',
  gruppe: 'Gruppe',
  gemeinde: 'Alle Mitglieder der Gemeinde',
}

/** Nachgebauter `apiCall` — liefert nur die Rollen-Erklärung. */
function fakeApi(antwort = { stufen_titel: SERVER_TITEL }) {
  const aufrufe = []
  const fn = async (pfad, args) => {
    aufrufe.push({ pfad, args })
    if (pfad !== F.STUFEN_TITEL_ENDPUNKT) throw new Error(`unerwarteter Aufruf: ${pfad}`)
    return antwort
  }
  fn.aufrufe = aufrufe
  return fn
}

// Einmal laden — wie die Bauteile es in `onMounted` tun.
await F.ladeStufenTitel(fakeApi())

// ══════════════════════════════════════════════════════════════════════════
// 1 · Stufennamen — EINE Quelle: der Server
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: Stufen heißen wie die Server-Titel (`get_rollen_erklaerung`)', () => {
  assert.equal(F.stufenName('untergruppe'), 'Untergruppe')
  assert.equal(F.stufenName('gruppe'), 'Gruppe')
  assert.equal(F.stufenName('gemeinde'), 'Alle Mitglieder der Gemeinde')
  // Unbekannt/leer: neutral, nie eine erfundene Stufe.
  assert.equal(F.stufenName(''), F.STUFE_UNBEKANNT)
  assert.equal(F.stufenName(null), F.STUFE_UNBEKANNT)
  assert.equal(F.stufenName('quatsch'), F.STUFE_UNBEKANNT)
})

test('UI-R4: die Oberfläche führt keine eigenen Stufen-/Begriffslisten', () => {
  const quelle = lies('components/kronos/freigabeStufen.mjs')
  // Exportierte Tabellen (Code), nicht bloß Kommentare prüfen.
  assert.doesNotMatch(quelle, /export const STUFEN_NAME/, 'kein eigener Anzeigenamen-Katalog')
  assert.doesNotMatch(quelle, /export const STUFEN_KURZ/, 'keine eigene Kurzform-Liste')
  // Kein Stufenname als TEXTWERT im Code (Strings mit „Moderation“/„Leitung“).
  const ohneKommentare = quelle.split('\n')
    .filter((z) => !/^\s*(\*|\/\*\*|\/\/)/.test(z))
    .join('\n')
  assert.doesNotMatch(ohneKommentare, /Gemeinde-Moderation/, 'kein festgeschriebener Stufenname')
  assert.doesNotMatch(ohneKommentare, /Gruppenleitung/, 'kein festgeschriebener Stufenname')
  assert.match(quelle, /get_rollen_erklaerung/, 'die Titel kommen vom Server')
  assert.match(quelle, /stufen_titel/, 'gelesen wird das Serverfeld `stufen_titel`')
})

test('UI-R4: ohne Server-Titel wird kein Name erfunden (fail neutral)', async () => {
  // Frisches Modul, Titel NICHT geladen.
  const frisch = await import(
    pathToFileURL(join(SRC, 'components/kronos/freigabeStufen.mjs')).href
      + `?leer=${Date.now()}`
  )
  assert.equal(frisch.stufenName('gruppe'), frisch.STUFE_UNBEKANNT)
  // Ein Fehler beim Laden bleibt folgenlos.
  const kaputt = async () => { throw new Error('500') }
  await frisch.ladeStufenTitel(kaputt)
  assert.equal(frisch.stufenName('gemeinde'), frisch.STUFE_UNBEKANNT)
  // Ohne brauchbares Feld ebenfalls nichts.
  await frisch.ladeStufenTitel(async () => ({ systemrollen: {} }))
  assert.equal(frisch.stufenName('gruppe'), frisch.STUFE_UNBEKANNT)
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · „darf prüfen“ entscheidet NUR der Server — fail closed
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: ohne echtes darf_pruefen keine Freigabe-Knöpfe', () => {
  for (const eintrag of [
    null,
    undefined,
    {},
    { stufe: 'gruppe' },                    // Feld fehlt (alte Antwort)
    { darf_pruefen: 'true' },               // nur echtes true zählt
    { darf_pruefen: 1 },
    { darf_pruefen: false },
  ]) {
    assert.equal(F.darfPruefen(eintrag), false,
      `fail closed für ${JSON.stringify(eintrag)}`)
  }
  assert.equal(F.darfPruefen({ darf_pruefen: true }), true)
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Warteline: „wartet auf Freigabe für: …“ nur, wenn wirklich etwas wartet
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: Warteline nennt die Stufe, die dran ist', () => {
  // UI-R4d (Punkt 5): „wartet auf Freigabe für: …“ — der Server-Titel ist eine
  // STUFE, kein Empfänger. Die frühere Form „wartet auf: <Titel>“ las sich wie
  // „wartet auf Alle Mitglieder der Gemeinde“.
  assert.equal(F.wartetAufText({ stufe: 'untergruppe', darf_pruefen: false }),
    'wartet auf Freigabe für: Untergruppe')
  assert.equal(F.wartetAufText({ stufe: 'gruppe', darf_pruefen: false }),
    'wartet auf Freigabe für: Gruppe')
  assert.equal(F.wartetAufText({ stufe: 'gemeinde', darf_pruefen: true }),
    'wartet auf Freigabe für: Alle Mitglieder der Gemeinde')
})

test('UI-R4: nichts Wartendes bekommt keine Warteline', () => {
  assert.equal(F.wartetAufText({ stufe: null, darf_pruefen: false }), null)
  assert.equal(F.wartetAufText(null), null)
  assert.equal(F.wartetNoch({ stufe: '' }), false)
  // Termin ohne Stufe, den man nicht prüfen darf: die Zeile bleibt weg —
  // der Server hat keine Stufe genannt, also wird keine erfunden.
  assert.equal(F.wartetAufText({ darf_pruefen: false }), null)
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Zählung „Zu prüfen“ zählt NUR das Erlaubte
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: „Zu prüfen“ zählt nur, was der Nutzer prüfen darf', () => {
  const eintraege = [
    { id: 'a', status: 'Vorschlag', stufe: 'gruppe', darf_pruefen: true },
    { id: 'b', status: 'Vorschlag', stufe: 'gemeinde', darf_pruefen: false },
    { id: 'c', status: 'Konflikt', stufe: 'gemeinde', darf_pruefen: true },
    { id: 'd', status: 'Vorschlag', stufe: 'gemeinde' },   // ohne Feld
  ]
  assert.equal(F.zaehleZuPruefen(eintraege), 2,
    'nur a und c — die fremden Stufen zählen nicht mit')
  assert.equal(F.zaehleZuPruefen(null), 0)
  assert.equal(F.zaehleZuPruefen([{ darf_pruefen: true, status: 'Festgelegt' }]), 0,
    'erledigte Termine bleiben draußen (alte Antwort nach dem Freigeben)')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Freigabe-Antwort: „Stufe freigegeben — geht jetzt an …“
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: wartet_weiter wird als „Stufe freigegeben“ gemeldet, nicht als „übernommen“', () => {
  const antwort = { success: true, wartet_weiter: true,
    meldung: 'Stufe freigegeben — die Änderung geht jetzt an Gruppe.' }
  const m = F.freigabeMeldung(antwort, { art: 'aenderung', stufe: 'gruppe' })
  assert.equal(m.weiter, true)
  assert.equal(m.ton, 'warning', 'es ist noch NICHT fertig — kein grüner Haken')
  assert.match(m.text, /Stufe freigegeben/)
  assert.doesNotMatch(m.text, /übernommen/)
})

test('UI-R4: TERMIN — `new_status` „Vorschlag“ heißt „wartet weiter“ (kein wartet_weiter im Server)', () => {
  // `resolve_conflict` liefert seit R-12d zusätzlich `offen` und
  // `naechste_stufe` (UI-R4b: die Oberfläche rechnet die Stufe NICHT mehr
  // selbst — die Kette kann untergruppe → gemeinde lauten).
  const nachErsterStufe = {
    id: 'EV-1', new_status: 'Vorschlag', action: 'festlegen',
    offen: ['gruppe'], naechste_stufe: 'gruppe',
  }
  const m = F.freigabeMeldung(nachErsterStufe, { art: 'termin', stufe: 'untergruppe' })
  assert.equal(m.weiter, true, 'Vorschlag = es ist noch eine Stufe offen')
  assert.equal(m.ton, 'warning')
  assert.match(m.text, /Stufe freigegeben/)
  assert.match(m.text, /geht jetzt an die Freigabe der Stufe „Gruppe“/, 'nennt die NÄCHSTE Stufe als Stufe')
  assert.doesNotMatch(m.text, /Termin freigegeben/)
})

test('UI-R4: TERMIN — letzte Stufe meldet ehrlich „Termin freigegeben“', () => {
  const m = F.freigabeMeldung({ id: 'EV-1', new_status: 'Festgelegt', action: 'festlegen' },
    { art: 'termin', stufe: 'gemeinde' })
  assert.deepEqual([m.ton, m.weiter], ['success', false])
  assert.equal(m.text, 'Termin freigegeben.')
})

test('UI-R4: Konflikt-Termin bleibt „wartet weiter“ (Status Konflikt)', () => {
  const m = F.freigabeMeldung({ new_status: 'Konflikt' }, { art: 'termin', stufe: 'gruppe' })
  assert.equal(m.weiter, true)
})

test('UI-R4: letzte Stufe einer Änderung = wirklich übernommen', () => {
  const m = F.freigabeMeldung({ success: true }, { art: 'aenderung' })
  assert.deepEqual([m.ton, m.weiter], ['success', false])
  assert.equal(m.text, 'Änderung übernommen.')
})

test('UI-R4: fehlt die Meldung, nennt die Oberfläche die nächste Stufe aus den Server-Titeln', () => {
  const m = F.freigabeMeldung(
    { success: true, wartet_weiter: true, offen: ['gruppe'], naechste_stufe: 'gruppe' },
    { art: 'termin', stufe: 'untergruppe' },
  )
  assert.equal(m.text, 'Stufe freigegeben — der Termin geht jetzt an die Freigabe der Stufe „Gruppe“.')
  // UI-R4c (Punkt 1): kein „an Gruppe“ — der Titel ist eine STUFE, kein Empfänger.
  assert.doesNotMatch(m.text, /geht jetzt an (?!die Freigabe der Stufe)/)
})

// UI-R4b (Punkt 2): Die Kette kommt vom Server — sie kann eine Stufe
// ÜBERSPRINGEN. Die frühere eigene Folge (untergruppe → gruppe → gemeinde)
// hätte hier fälschlich „Gruppe“ gesagt.
test('UI-R4b: die Stufen-Kette kommt vom Server (untergruppe → gemeinde überspringt die Gruppe)', () => {
  // Der Server sagt: nach der Untergruppe ist die GEMEINDE dran.
  const antwort = {
    id: 'EV-9', new_status: 'Vorschlag', action: 'festlegen',
    offen: ['gemeinde'], naechste_stufe: 'gemeinde',
  }
  assert.deepEqual(F.offeneStufen(antwort), ['gemeinde'])
  assert.equal(F.naechsteStufe(antwort), 'gemeinde')
  const m = F.freigabeMeldung(antwort, { art: 'termin', stufe: 'untergruppe' })
  assert.equal(m.text, 'Stufe freigegeben — der Termin geht jetzt an die Freigabe der Stufe „Alle Mitglieder der Gemeinde“.')
  assert.doesNotMatch(m.text, /an Gruppe\./, 'die übersprungene Stufe darf nicht genannt werden')

  // Die letzte Stufe: nichts mehr offen → fertig.
  const fertig = { id: 'EV-9', new_status: 'Festgelegt', action: 'festlegen', offen: [], naechste_stufe: null }
  assert.deepEqual(F.offeneStufen(fertig), [])
  assert.equal(F.naechsteStufe(fertig), null)
  assert.equal(F.freigabeMeldung(fertig, { art: 'termin' }).text, 'Termin freigegeben.')
})

test('UI-R4b: ohne `naechste_stufe` wird KEINE Stufe geraten', () => {
  // Alte Antwort ohne Ketten-Auskunft: der Satz bleibt ohne Stufennamen.
  assert.equal(F.naechsteStufe({ success: true, wartet_weiter: true }), null)
  assert.equal(F.naechsteStufeName({ success: true, wartet_weiter: true }), null)
  const m = F.freigabeMeldung({ success: true, wartet_weiter: true }, { art: 'aenderung' })
  assert.equal(m.text, 'Stufe freigegeben — die Änderung wartet auf die nächste Stufe.')
  // Und die reine Regel kennt keine eigene Stufenfolge mehr.
  assert.doesNotMatch(
    lies('components/kronos/freigabeStufen.mjs'),
    /export const STUFEN\s*=/,
    'keine feste Stufenfolge in der Oberfläche',
  )
})

test('UI-R4b: „Alle freigeben“ meldet festgelegt und weitergereicht ehrlich', () => {
  // So antwortet `finalize_staged_events` seit R-12d.
  const antwort = {
    finalized: 3, festgelegt: 2, weitergereicht: 1,
    ergebnisse: {
      'EV-1': { status: 'Festgelegt', offen: [], naechste_stufe: null },
      'EV-2': { status: 'Festgelegt', offen: [], naechste_stufe: null },
      'EV-3': { status: 'Vorschlag', offen: ['gemeinde'], naechste_stufe: 'gemeinde' },
    },
  }
  const m = F.sammelMeldung(antwort)
  assert.match(m.text, /^2 freigegeben, 1 wartet auf die Freigabe der Stufe „Alle Mitglieder der Gemeinde“\.$/)
  assert.equal(m.ton, 'warning', 'solange etwas wartet, gibt es keinen grünen Haken')
  // Der Karten-Link in den Kalender hängt an `festgelegt`, nicht an der Zahl
  // der abgehakten Stufen.
  assert.equal(antwort.festgelegt, 2, 'nur festgelegte Termine stehen im Kalender')

  // Alles festgelegt → ehrlich fertig.
  const alle = F.sammelMeldung({ finalized: 2, festgelegt: 2, weitergereicht: 0, ergebnisse: {} })
  assert.equal(alle.text, '2 Termine freigegeben.')
  assert.equal(alle.ton, 'success')

  // Nur weitergereicht → keine „freigegeben“-Behauptung.
  // UI-R4d (Punkt 4): EIN wartender Termin ohne `ergebnisse` wartet auf „die
  // nächste Stufe“ — „weitere Stufen“ gibt es bei einem nicht.
  const keins = F.sammelMeldung({ finalized: 1, festgelegt: 0, weitergereicht: 1, ergebnisse: {} })
  assert.equal(keins.text, '1 Termin wartet auf die nächste Stufe.')
  assert.equal(keins.ton, 'warning')

  // Mehrere wartende (ohne Stufen-Auskunft) → Mehrzahl „weitere Stufen“.
  const mehrere = F.sammelMeldung({ finalized: 2, festgelegt: 0, weitergereicht: 2, ergebnisse: {} })
  assert.equal(mehrere.text, '2 Termine warten auf weitere Stufen.')
})

test('UI-R4: Überschneidung bleibt eine Warnung mit dem Servertext', () => {
  const m = F.freigabeMeldung({
    success: true,
    meldung: 'Freigegeben — Achtung: der Termin ueberschneidet sich mit einer anderen Belegung.',
  }, { art: 'termin' })
  assert.equal(m.ton, 'warning')
  assert.match(m.text, /ueberschneidet|überschneidet/)
})

test('UI-R4: `wartetWeiter` liest nur die Server-Antwort', () => {
  assert.equal(F.wartetWeiter({ wartet_weiter: true }), true)
  assert.equal(F.wartetWeiter({ new_status: 'Vorschlag' }), true)
  assert.equal(F.wartetWeiter({ new_status: 'Konflikt' }), true)
  assert.equal(F.wartetWeiter({ new_status: 'Festgelegt' }), false)
  assert.equal(F.wartetWeiter({ new_status: 'Abgelehnt' }), false)
  assert.equal(F.wartetWeiter({ success: true }), false)
  assert.equal(F.wartetWeiter(null), false)
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Verweigerung (403/417) verständlich — Servertext bleibt erhalten
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: 403 nennt den Servertext (welche Stufe zuständig ist)', () => {
  const satz = 'Dieser Termin wartet noch auf die Freigabe durch Gruppe.'
  assert.equal(F.verweigerungText({ status: 403, message: satz }, 'gruppe'), satz)
  // Auch ohne Status-Kennung, aber mit dem typischen Klartext.
  assert.equal(F.verweigerungText(new Error(satz), 'gruppe'), satz)
  // Der Satz wird NIE mit einer anderen Stufe überschrieben.
  assert.doesNotMatch(F.verweigerungText({ status: 417, message: satz }, 'gemeinde'),
    /Alle Mitglieder der Gemeinde/)
})

test('UI-R4: ohne brauchbaren Servertext erklärt die Oberfläche die Stufe', () => {
  assert.match(F.verweigerungText({ status: 403, message: '' }, 'gemeinde'),
    /Alle Mitglieder der Gemeinde/)
  assert.equal(F.verweigerungText(null, null), 'Du kannst diesen Vorschlag nicht prüfen.')
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · Freigabe-Anträge in Zeilen (annehmen/ablehnen) — Felder vom Server
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: Antrag nutzt die Server-Felder titel/ziel/gruppe_name', () => {
  const z = F.antragZeile({
    typ: 'kalender', objekt: 'Chor KG', gruppe: 'Kirchenchor', untergruppe: 'Sopran',
    stufe: 'gruppe', titel: 'Chorproben',
    gruppe_name: 'Chor', untergruppe_name: 'Sopran', ziel: 'gemeinde',
  })
  assert.equal(z.typ, 'kalender', 'Entscheid nutzt den Schlüssel')
  assert.equal(z.objekt, 'Chor KG')
  assert.equal(z.titel, 'Chorproben', 'Anzeige nutzt den Server-Titel')
  assert.equal(z.stufe, 'gruppe', 'Entscheid nutzt die OFFENE Stufe')
  // Ziel bleibt „gemeinde“, auch wenn zuerst die Gruppenstufe entscheidet.
  assert.equal(z.ziel, 'gemeinde')
  assert.equal(F.antragSatz(z), 'Kalender „Chorproben“ für alle Mitglieder der Gemeinde')
})

test('UI-R4b: Gruppen-Ziel heißt „die ganze Gruppe“ (nicht die Untergruppe)', () => {
  // `ziel='gruppe'` bedeutet: der Inhalt einer UNTERGRUPPE soll für die GANZE
  // Gruppe sichtbar werden. Der Ziel-Satz nennt deshalb die Gruppe — die
  // Untergruppe ist nur die Herkunft.
  const z = F.antragZeile({
    typ: 'kalender', objekt: 'x', stufe: 'gruppe', titel: 'Chorproben',
    untergruppe_name: 'Sopran', gruppe_name: 'Chor', ziel: 'gruppe',
  })
  assert.equal(F.antragSatz(z), 'Kalender „Chorproben“ für die ganze Gruppe Chor')
  assert.doesNotMatch(F.antragSatz(z), /öffentlich/i)
  assert.doesNotMatch(F.antragSatz(z), /Untergruppe/, 'die Untergruppe ist nicht das Ziel')
  // Ohne Untergruppe im Antrag: dieselbe Gruppe, nur ohne „ganze“.
  const ohneU = F.antragZeile({
    typ: 'kalender', objekt: 'x', stufe: 'gruppe', titel: 'Chorproben',
    gruppe_name: 'Chor', ziel: 'gruppe',
  })
  assert.equal(F.antragSatz(ohneU), 'Kalender „Chorproben“ für die Gruppe Chor')
})

test('UI-R4: fehlt `ziel` (alte Antwort), wird kein Ziel erfunden', () => {
  const z = F.antragZeile({ typ: 'kalender', objekt: 'Chor KG', stufe: 'gemeinde' })
  assert.equal(z.ziel, null)
  assert.equal(z.titel, 'Chor KG', 'ohne Titel bleibt der Schlüssel — nie eine leere Zeile')
  assert.equal(F.antragSatz(z), 'Kalender „Chor KG“')
})

test('UI-R4b: `stufeText` kommt aus dem Namensgeber — nachgeladene Titel greifen', () => {
  // Beim Laden der Anträge können die Stufen-Titel noch fehlen; dann stand
  // früher für immer „Stufe: —“. `antragZeilen(antraege, namensgeber)` fragt
  // den Namen bei JEDEM Zeichnen neu ab.
  const antrag = { typ: 'kalender', objekt: 'x', stufe: 'gruppe', titel: 'Chorproben' }
  const ohneTitel = F.antragZeile(antrag, () => F.STUFE_UNBEKANNT)
  assert.equal(ohneTitel.stufeText, F.STUFE_UNBEKANNT)
  const mitTitel = F.antragZeile(antrag, (s) => (s === 'gruppe' ? 'Gruppe' : F.STUFE_UNBEKANNT))
  assert.equal(mitTitel.stufeText, 'Gruppe')
  assert.equal(F.antragZeilen([antrag], () => 'Gruppe')[0].stufeText, 'Gruppe')
  // Ohne Namensgeber gilt der Server-Stand (Standard).
  assert.equal(F.antragZeile(antrag).stufeText, 'Gruppe')
})

test('UI-R4: unvollständige Anträge fallen still heraus', () => {
  const zeilen = F.antragZeilen([
    null,
    { typ: 'kalender' },                                   // ohne Objekt
    { typ: 'kalender', objekt: 'X' },                       // ohne Stufe
    { objekt: 'X', stufe: 'gruppe' },                       // ohne Typ
    { typ: 'kalender', objekt: 'X', stufe: 'gemeinde' },
  ])
  assert.equal(zeilen.length, 1)
  assert.equal(zeilen[0].objekt, 'X')
  assert.deepEqual(F.antragZeilen(null), [])
})

// ══════════════════════════════════════════════════════════════════════════
// 8 · Die Bauteile nutzen diese Regeln (und entscheiden keine Rechte selbst)
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4: Karte zeigt Warteline, Stufenname und Freigabe nur bei darf_pruefen', () => {
  const karte = lies('components/kronos/ModerationCard.vue')
  assert.match(karte, /freigabeStufen\.mjs/, 'Karte nutzt die EINE Stufen-Regel')
  assert.match(karte, /wartetAufText/, 'Karte zeigt „wartet auf Freigabe für: …“')
  assert.match(karte, /darfPruefen/, 'Karte blendet die Freigabe nach darf_pruefen')
  assert.match(karte, /stufenNameReaktiv/, 'Karte nennt die Stufe der Ablage')
  // UI-R4b (Punkt 7b): EIN gemeinsamer Lader je Seite — nicht einer je Karte.
  assert.match(karte, /stufenTitelEinmalLaden/, 'Karte holt die Titel vom Server (einmal je Seite)')
})

test('UI-R4: Karte — kein aria-label über dem Inhalt, keine Knöpfe im Link', () => {
  const karte = lies('components/kronos/ModerationCard.vue')
  const tpl = karte.slice(0, karte.indexOf('<script setup>'))
  // Ein aria-label am Link/Kartenrahmen überschreibt den vorgelesenen Inhalt.
  assert.doesNotMatch(tpl, /^\s*<a[^>]*aria-label/m, 'kein aria-label am Karten-Link')
  // Kein <DkButton> innerhalb von <a>…</a> (verschachtelte Bedienelemente).
  const links = [...tpl.matchAll(/<a\b[\s\S]*?<\/a>/g)].map(m => m[0])
  for (const l of links) {
    assert.doesNotMatch(l, /<DkButton/, 'Knopf innerhalb eines Links')
  }
  // Der Freigeben-Knopf wird per aria-describedby erklärt.
  assert.match(tpl, /aria-describedby/, 'Freigeben-Knopf braucht eine Beschreibung')
  assert.match(tpl, /dk-nur-vorlesen/, 'die Beschreibung liegt nur für Screenreader vor')
})

test('UI-R4: Tafel lädt nach JEDEM Entscheid neu und meldet keine eigene Zahl', () => {
  const tafel = lies('components/kronos/ModerationBoard.vue')
  assert.match(tafel, /freigabeMeldung/, 'Tafel meldet Freigaben über freigabeMeldung')
  // Nach dem Entscheid wird immer neu geladen — nicht nur, wenn es weitergeht.
  const nachFreigabe = tafel.slice(tafel.indexOf('async function onFreigeben'))
  const ende = nachFreigabe.indexOf('function verweigerungFuer')
  const block = nachFreigabe.slice(0, ende)
  assert.match(block, /await loadBoard\(\)/, 'kein Neuladen nach dem Entscheid')
  assert.doesNotMatch(block, /if \(weiter\)/, 'das Neuladen darf nicht am Status hängen')
  // Die Tafel meldet nur „bitte Zahl nachziehen“ — keine eigene Zahl.
  assert.match(block, /emit\('entschieden'\)/, 'die Seite erfährt vom Entscheid')
  assert.doesNotMatch(tafel, /emit\(['"]bereit['"]/, 'kein eigenes `bereit`-Ereignis mehr')
  assert.doesNotMatch(tafel, /schildZahl/, 'keine eigene Schildzahl mehr')
})

test('UI-R4: nachgeladene Stufen-Titel zeichnen Warteline/Stufe neu (reaktiv)', () => {
  // Ohne reaktive Ablage blieb „wartet auf: —“ stehen (im Wegwerf-Stack
  // gesehen: die zweite Lage zeigte das neutrale „—“).
  const reaktiv = lies('components/kronos/freigabeStufenReaktiv.mjs')
  assert.match(reaktiv, /export const titelStand = shallowRef\(/, 'Stand liegt in einem shallowRef')
  assert.match(reaktiv, /titelStand\.value = \{/, 'das Laden setzt den reaktiven Stand')
  assert.match(reaktiv, /stufenNameReaktiv/, 'reaktiver Name fehlt')
  // UI-R4b (Punkt 7b): der Ladevorgang wird gemerkt — nicht je Bauteil neu.
  assert.match(reaktiv, /export function stufenTitelEinmalLaden/, 'gemeinsamer Lader fehlt')
  // Die Karte/Änderungen holen die Titel über diese Ablage.
  assert.match(lies('components/kronos/ModerationCard.vue'), /stufenTitelEinmalLaden|stufenNameReaktiv/)
  assert.match(lies('components/kronos/ModerationAenderungen.vue'), /stufenNameReaktiv/)
})

test('UI-R4: die reinen Regeln importieren KEIN Vue (sonst bricht jsdom-Mount)', () => {
  // Befund im Lauf: ein `import { shallowRef } from 'vue'` in
  // `freigabeStufen.mjs` zog über `pruefZeile.mjs` ein zweites Vue mit eigenem
  // `document` in die jsdom-Tests — 6 UX3i-Mounttests brachen danach mit
  // „Cannot read properties of null (reading 'createElement')“.
  for (const datei of ['components/kronos/freigabeStufen.mjs', 'components/kronos/pruefZeile.mjs']) {
    assert.doesNotMatch(lies(datei), /from 'vue'/, `${datei} muss Vue-frei bleiben`)
  }
})

test('UI-R4: Seite und Panel zählen über den Server (getModerationCount)', () => {
  const tafel = lies('pages/Moderation.vue')
  assert.match(tafel, /getModerationCount/, 'die Zahl kommt aus der EINEN Server-Abfrage')
  assert.match(tafel, /ModerationAntraege/, 'Abschnitt „Freigabe-Anträge“ existiert')
  assert.doesNotMatch(tafel, /boardBereit|boardZahl/, 'keine zweite, eigene Zählung')
  // Der Erklärsatz verspricht nicht mehr „wird verbindlich“ bei jeder Stufe.
  assert.doesNotMatch(tafel, /wird\s*\n?\s*er verbindlich und erscheint im Kalender/)
  const panel = lies('components/kronos/KalenderPruefPanel.vue')
  assert.match(panel, /darf_pruefen/, 'Panel zeigt nur, was der Aufrufer prüfen darf')
  assert.doesNotMatch(panel, /emit\(['"]bereit['"]/, 'Panel führt keine eigene Zahl mehr')
})

test('UI-R4: die Spaltenzahl ist der Inhalt, „für andere“ steht getrennt', () => {
  const tafel = lies('components/kronos/ModerationBoard.vue')
  assert.match(tafel, /\{\{ vorschlaege\.length \}\}/, 'Vorschlagszahl = Inhalt')
  assert.match(tafel, /\{\{ konflikte\.length \}\}/, 'Konfliktzahl = Inhalt')
  assert.match(tafel, /fremdVorschlaege/, '„für andere“ fehlt')
})

test('UI-R4: der Anträge-Abschnitt fragt vor dem Ablehnen nach (DkDialog, kein confirm())', () => {
  const quelle = lies('components/kronos/ModerationAntraege.vue')
  assert.match(quelle, /get_offene_sichtbarkeits_antraege/)
  assert.match(quelle, /entscheide_sichtbarkeit/)
  // Entscheiden wird NIE clientseitig angenommen: keine erfundene Stufe.
  assert.match(quelle, /stufe: z\.stufe/)
  assert.match(quelle, /annehmen:/)
  assert.match(quelle, /bestaetigen\(/, 'Ablehnen braucht eine Rückfrage')
  // Kein Browser-Dialog (window.confirm/global confirm). Die Kommentare
  // nennen das Wort absichtlich — geprüft wird der Code ohne Kommentare.
  const ohneKommentare = quelle.split('\n')
    .filter((z) => !/^\s*(\*|\/\*\*|\/\/|\/\*)/.test(z))
    .join('\n')
  assert.doesNotMatch(ohneKommentare, /window\.confirm|(?<![.\w])confirm\(/, 'kein Browser-confirm()')
})

// ══════════════════════════════════════════════════════════════════════════
// 9 · UI-R4b (Punkte 3, 5, 6, 7): Seite und Anträge melden ehrlich
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4b: „Alle freigeben“ meldet über sammelMeldung und verlinkt den Kalender nur bei festgelegten', () => {
  const seite = lies('pages/Moderation.vue')
  assert.match(seite, /sammelMeldung\(/, 'die Seite nutzt die ehrliche Sammel-Meldung')
  // Kein festes „N Termine freigegeben“ mehr, das nur die abgehakten Stufen zählt.
  assert.doesNotMatch(seite, /`\$\{zahlWort\(ids\.length/, 'keine erfundene Freigabezahl')
  // Der Kalender-Link hängt an `festgelegt`.
  const block = seite.slice(seite.indexOf('async function finalizeAll'))
  assert.match(block, /meldung\.festgelegt > 0/, '„Im Kalender ansehen“ nur bei festgelegten Terminen')
  assert.match(block, /meldung\.ton/, 'der Ton kommt aus der Meldung (Warnung bleibt Warnung)')
})

test('UI-R4b: der Anträge-Toast behauptet NICHT „für alle Mitglieder der Gemeinde“', () => {
  const quelle = lies('components/kronos/ModerationAntraege.vue')
  // Der feste Text von vorher ist weg; die Meldung kommt aus der Antwort.
  assert.doesNotMatch(quelle, /Freigegeben: \$\{antragSatz\(z\)\}\./,
    'kein pauschales „Freigegeben …“ mehr')
  assert.match(quelle, /const antwort = await apiCall\('diakronos\.api\.rechte\.entscheide_sichtbarkeit'/,
    'die Antwort des Entscheids wird ausgewertet')
  // `entscheide_sichtbarkeit` liefert NUR {success, gruppe_status,
  // gemeinde_status} — also wird genau das gelesen, kein erfundenes Feld.
  assert.match(quelle, /gemeinde_status/, 'der Gemeindestatus kommt aus der Antwort')
  assert.match(quelle, /gruppe_status/, 'der Gruppenstatus kommt aus der Antwort')
  // Kommentare zählen nicht: dort steht der Feldname als Erklärung, warum er
  // NICHT benutzt wird (`entscheide_sichtbarkeit` liefert ihn gar nicht).
  const ohneKommentare = quelle
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n').map((z) => z.replace(/(^|[^:])\/\/.*$/, '$1')).join('\n')
  assert.doesNotMatch(ohneKommentare, /ziel_erreicht/,
    '`ziel_erreicht` gibt es auf dem Server nicht — nicht behaupten')
  assert.match(quelle, /geht jetzt an/, 'Weiterleitung an die nächste Stufe wird genannt')
})

test('UI-R4b: „Stufe: …“ ist reaktiv — Anträge vor den Titeln bleiben nicht bei „—“', () => {
  const quelle = lies('components/kronos/ModerationAntraege.vue')
  // Die Zeilen sind ein computed MIT reaktivem Namensgeber …
  assert.match(quelle, /computed\(\(\) => antragZeilen\(antraege\.value, stufenNameReaktiv\)\)/,
    'die Stufe muss beim Zeichnen neu gelesen werden')
  // Und keinen Ladeprosatext (UX2d3a): bis der Name da ist, steht nichts.
  assert.doesNotMatch(quelle, /wird geladen/,
    'kein Ladeprosatext in der Vorlage (UX2d3a)')
  assert.match(quelle, /stufenTitelEinmalLaden\(apiCall\)/, 'der gemeinsame Lader wird benutzt')
  // … und „—“ steht nur da, wenn wirklich kein Name kommt (kein Dauerzustand).
  assert.match(quelle, /z\.stufeText !== STUFE_UNBEKANNT/)
})

test('UI-R4b: Verweigerungstext und Freigabe schließen sich nicht mehr aus', () => {
  const karte = lies('components/kronos/ModerationCard.vue')
  assert.doesNotMatch(karte, /v-else-if="verweigerung"/,
    'der Verweigerungstext darf nicht am Freigabe-Block hängen')
  assert.match(karte, /<p v-if="verweigerung"/, 'der Verweigerungstext steht als eigener Absatz')
  const tafel = lies('components/kronos/ModerationBoard.vue')
  // Nach einer Verweigerung wird neu geladen (sonst bliebe die Karte mit Knopf).
  const block = tafel.slice(tafel.indexOf('async function onFreigeben'))
  const bis = block.indexOf('function verweigerungFuer')
  assert.match(block.slice(0, bis), /await loadBoard\(\),?\s*\n\s*if \(teilErfolg\)|await loadBoard\(\)/,
    'nach einer Verweigerung fehlt das Neuladen')
})

test('UI-R4b: in der Konfliktspalte gibt es keinen direkten Freigeben-Knopf', () => {
  const karte = lies('components/kronos/ModerationCard.vue')
  assert.match(karte, /if \(props\.column !== 'vorschlaege'\) return false/,
    'Freigabe nur in der Vorschlags-Spalte')
  assert.doesNotMatch(karte, /column !== 'vorschlaege' && props\.column !== 'konflikte'/,
    'die Konfliktspalte darf keinen Freigeben-Knopf bekommen')
})

test('UI-R4: kein „öffentlich“ in den Texten der Stufen-/Antragsregeln', () => {
  const quelle = lies('components/kronos/freigabeStufen.mjs')
  const texte = quelle.split('\n')
    .filter((z) => /'|`/.test(z) && !z.trim().startsWith('*') && !z.trim().startsWith('/**'))
    .join('\n')
  assert.doesNotMatch(texte, /öffentlich/i)
})

// ══════════════════════════════════════════════════════════════════════════
// UI-R4c (Punkt 4) · „Alle freigeben“ nennt eine Stufe nur, wenn alle gleich
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4c: gemischte offene Stufen werden NICHT als eine Stufe gemeldet', () => {
  // Zwei Termine warten: einer auf die Gruppe, einer direkt auf die Gemeinde.
  // Die frühere Meldung nannte nur die ERSTE gefundene Stufe — als warteten
  // alle dort.
  const gemischt = {
    finalized: 2, festgelegt: 0, weitergereicht: 2,
    ergebnisse: {
      'EV-1': { status: 'Vorschlag', offen: ['gruppe'], naechste_stufe: 'gruppe' },
      'EV-2': { status: 'Vorschlag', offen: ['gemeinde'], naechste_stufe: 'gemeinde' },
    },
  }
  assert.deepEqual(F.stufenEintraege(gemischt), ['gemeinde', 'gruppe'])
  assert.equal(F.sammelStufeText(gemischt), null, 'zwei Stufen — keine benennen')
  const m = F.sammelMeldung(gemischt)
  assert.equal(m.text, '2 Termine warten auf weitere Stufen.')
  assert.doesNotMatch(m.text, /Stufe „/, 'keine der beiden Stufen behaupten')
  assert.equal(m.ton, 'warning')
  assert.equal(m.weitergereicht, 2)

  // Dieselbe Stufe bei allen WARTENDEN: sie darf genannt werden.
  const gleich = {
    finalized: 2, festgelegt: 1, weitergereicht: 2,
    ergebnisse: {
      'EV-1': { status: 'Festgelegt', offen: [], naechste_stufe: null },
      'EV-2': { status: 'Vorschlag', offen: ['gemeinde'], naechste_stufe: 'gemeinde' },
      'EV-3': { status: 'Vorschlag', offen: ['gemeinde'], naechste_stufe: 'gemeinde' },
    },
  }
  assert.equal(F.sammelStufeText(gleich), 'die Freigabe der Stufe „Alle Mitglieder der Gemeinde“')
  assert.equal(F.sammelMeldung(gleich).text,
    '1 freigegeben, 2 warten auf die Freigabe der Stufe „Alle Mitglieder der Gemeinde“.')
})
