/**
 * CHAT-3a — Bereich „Nachrichten“: Gesprächsliste, Verlauf, Eingabe.
 *
 * Der Test hält die Karte am ECHTEN Code fest. Geprüft wird, wo Verhalten
 * prüfbar ist (die Logik-Module), und Quelltext nur dort, wo es keine
 * aufrufbare Funktion gibt (SFC-Vorlagen, Verdrahtung in App.vue).
 *
 *   1. Die Logik (`composables/nachrichtenLogik.mjs`,
 *      `composables/nachrichtenReaktionen.mjs`): Adresse, Gruppierung und
 *      Sortierung, Zeitformate, Zähler, Nachladen (nach oben/unten), Polling
 *      samt Aufräumen, Textprüfung, Tastatur, Lesestand-Summe, gelöschte
 *      Nachrichten, Fehlerzustände.
 *   2. Die Bausteine: ChatBlase (eigene rechts, Zitat, Reaktionen,
 *      „bearbeitet“, Summe statt Namensliste), ChatListe (Abschnitte, Zähler,
 *      Stumm), Nachrichten.vue (role="log", aria-live, Enter/Shift+Enter,
 *      Fokus nach Wechsel, Nachladen beim Scrollen, keine harten Farben).
 *   3. Die Handy-Leiste: fünf Plätze, „Mehr“ öffnet die Schublade, Zähler am
 *      Tab „Nachrichten“ (Chat-Konzept 10.1/10.2 — die Regel „kein Mehr in der
 *      Leiste“ vom 03.11. ist damit abgelöst).
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat3a-nachrichten.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ABSCHNITTE, BEARBEITEN_MINUTEN, BEREICH, LISTE_LEER, MODUL_AUS, NACHRICHT_MAX,
  REAKTIONEN, SENDEN_TEXT, TAKT_MS, VERLAUF_LEER, VORSCHAU_MAX, aelterStand,
  backoffMs, BACKOFF_MAX_MS, fremdeNeue, istAeltereSeite, lesestandFaellig,
  zeilenAdresse, zeilenSchluessel, eintragZuSchluessel,
  darfAbfragen, eingabePlatzhalter, fehlerZustand, gespraechAusHash,
  gespraechHash, gruppierteListe, hinweisText, innerhalbFrist, listenZeit,
  listenZeile, lesestandText, mitTagesmarken, pruefeText, seiteEinordnen,
  taktGeber, tasteImFeld, tagesUeberschrift, ungelesenSumme, verlaufsZeile,
} from '../src/diakonos/composables/nachrichtenLogik.mjs'
import { SEITE as SEITENGROESSE } from '../src/diakonos/composables/nachrichtenLogik.mjs'
import {
  istReaktion, naechsteReaktion, reaktionsAuswahl, reaktionsZeile,
} from '../src/diakonos/composables/nachrichtenReaktionen.mjs'
import { FUSSTAB_TABS, fusstabs, tabZaehler } from '../src/diakonos/components/fusstabs.mjs'
import { ICON_PFADE } from '../src/diakonos/menue.js'
import {
  MEHR_TEXT, istTabAktiv, tabArt,
} from '../src/diakonos/components/handyMenue.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const ohneKommentare = (text) => text
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')

/** Template-/Skript-/Stilteil einer .vue-Datei. */
function teile(quelle) {
  const tpl = quelle.slice(quelle.indexOf('<template>'), quelle.lastIndexOf('</template>'))
  const skript = quelle.slice(quelle.indexOf('<script setup>'), quelle.indexOf('</script>'))
  const stil = quelle.slice(quelle.lastIndexOf('<style'))
  return { tpl, skript, stil }
}

/** Serverzeit ⇒ Date (Wandzeit = Ortszeit), damit „jetzt“ fest ist. */
const JETZT = new Date(2026, 10, 18, 12, 0, 0) // 18.11.2026, 12:00 Ortszeit
const zeit = (tag, stunde, minute = 0) => `${tag}T${String(stunde).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`

function gespraech(überschreiben = {}) {
  return {
    name: `chat-gespraech-${Math.random().toString(16).slice(2, 8)}`,
    art: 'gruppe',
    gruppe: 'chor',
    untergruppe: null,
    titel: 'Chor',
    teilnehmer: 28,
    stumm: false,
    geoeffnet: true,
    ungelesen: 0,
    letzte_nachricht: 'Hallo',
    letzte_am: zeit('2026-11-18', 10, 8),
    ...überschreiben,
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// 1 · Adresse
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · Adresse: Liste und Gespräch sind zwei Formen, „suche“ ist keine Kennung', () => {
  assert.equal(gespraechAusHash('#/nachrichten'), null)
  assert.equal(gespraechAusHash('#/nachrichten/'), null)
  assert.equal(gespraechAusHash('#/nachrichten/chat-gespraech-abc'), 'chat-gespraech-abc')
  assert.equal(gespraechAusHash('#/nachrichten/chat-gespraech-abc/'), 'chat-gespraech-abc')
  // Abfrageteil gehört nicht zur Kennung (die Palette hängt `?q=` an).
  assert.equal(gespraechAusHash('#/nachrichten/chat-gespraech-abc?q=1'), 'chat-gespraech-abc')
  // Die Personensuche (CHAT-3c) ist KEIN Gespräch — sonst stünde dort ein
  // leerer Verlauf statt der Suche.
  assert.equal(gespraechAusHash('#/nachrichten/suche?q=Roth'), null)
  // Fremde Bereiche bleiben fremd.
  assert.equal(gespraechAusHash('#/gruppen'), null)
  assert.equal(gespraechAusHash('#/nachrichten2'), null)

  // Der Rückweg erzeugt genau diese Form (und kodiert Sonderzeichen).
  assert.equal(gespraechHash('chat-gespraech-abc'), '#/nachrichten/chat-gespraech-abc')
  assert.equal(gespraechHash(''), BEREICH)
  assert.equal(gespraechAusHash(gespraechHash('a b')), 'a b')
})

// ══════════════════════════════════════════════════════════════════════════════
// 2 · Zeit
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · Zeit in der Liste: heute Uhrzeit, gestern „gestern“, älter Datum', () => {
  assert.equal(listenZeit(zeit('2026-11-18', 9, 12), JETZT), '09:12')
  assert.equal(listenZeit(zeit('2026-11-17', 19, 31), JETZT), 'gestern')
  assert.equal(listenZeit(zeit('2026-11-10', 8, 0), JETZT), '10.11.')
  // Anderes Jahr: das Jahr wird angehängt (zweistellig, wie in der Liste).
  assert.equal(listenZeit(zeit('2025-12-24', 8, 0), JETZT), '24.12.25')
  // Unlesbares bleibt leer — NIE „Invalid Date“ auf dem Bildschirm.
  assert.equal(listenZeit('', JETZT), '')
  assert.equal(listenZeit('unsinn', JETZT), '')
})

test('CHAT-3a · Tages-Marken im Verlauf: Heute, Gestern, Wochentag, Datum', () => {
  assert.equal(tagesUeberschrift(zeit('2026-11-18', 9), JETZT), 'Heute')
  assert.equal(tagesUeberschrift(zeit('2026-11-17', 22), JETZT), 'Gestern')
  // Innerhalb der letzten sieben Tage: der Wochentag (18.11.2026 ist ein
  // Mittwoch — der 15.11. ein Sonntag).
  assert.equal(tagesUeberschrift(zeit('2026-11-15', 10), JETZT), 'Sonntag')
  // Älter: das volle Datum mit Monatsnamen.
  assert.equal(tagesUeberschrift(zeit('2026-10-03', 10), JETZT), '3. Oktober 2026')
})

test('CHAT-3a · Tages-Marken: genau EINE Marke je Tageswechsel, alt → neu', () => {
  const nachrichten = [
    { name: 'a1', erstellt_am: zeit('2026-11-16', 9) },
    { name: 'a2', erstellt_am: zeit('2026-11-16', 10) },
    { name: 'b1', erstellt_am: zeit('2026-11-17', 9) },
    { name: 'c1', erstellt_am: zeit('2026-11-18', 9) },
    { name: 'c2', erstellt_am: zeit('2026-11-18', 11) },
  ]
  const mit = mitTagesmarken(nachrichten, JETZT)
  assert.equal(mit[0].tag, 'Montag', 'die erste Nachricht des Verlaufs bekommt ihren Tag')
  assert.equal(mit[1].tag, null, 'gleicher Tag → keine zweite Marke')
  assert.equal(mit[2].tag, 'Gestern')
  assert.equal(mit[3].tag, 'Heute')
  assert.equal(mit[4].tag, null)
  // Die Reihenfolge bleibt (alt → neu) — Marken sortieren nicht um.
  assert.deepEqual(mit.map((n) => n.name), ['a1', 'a2', 'b1', 'c1', 'c2'])
})

// ══════════════════════════════════════════════════════════════════════════════
// 3 · Gesprächsliste
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · Liste: Gruppen vor Untergruppen, neueste Nachricht oben', () => {
  const liste = [
    gespraech({ name: 'g-chor', titel: 'Chor', letzte_am: zeit('2026-11-18', 10, 8) }),
    gespraech({ name: 'g-jugend', titel: 'Jugend', letzte_am: zeit('2026-11-17', 8, 40) }),
    gespraech({
      name: 'g-noten', titel: 'Notenausschuss', art: 'untergruppe', untergruppe: 'noten',
      letzte_am: zeit('2026-11-18', 11, 30), ungelesen: 2,
    }),
    gespraech({ name: null, titel: 'Bläserkreis', geoeffnet: false, letzte_am: null, letzte_nachricht: null }),
  ]
  const gruppen = gruppierteListe(liste, JETZT)
  assert.deepEqual(gruppen.map((g) => g.label), ['Gruppen', 'Untergruppen'])
  assert.deepEqual(gruppen[0].eintraege.map((e) => e.titel), ['Chor', 'Jugend', 'Bläserkreis'])
  assert.deepEqual(gruppen[1].eintraege.map((e) => e.titel), ['Notenausschuss'])
  // Das nie geöffnete Gespräch hat KEINE Kennung — die Oberfläche legt es beim
  // Tippen an (`geoeffnet: false`).
  const blasen = gruppen[0].eintraege.find((e) => e.titel === 'Bläserkreis')
  assert.equal(blasen.geoeffnet, false)
  assert.equal(blasen.name, null)
  assert.equal(blasen.letzte, '')
  // Zeit und Zähler sind fertig gerechnet.
  assert.equal(gruppen[1].eintraege[0].zeit, '11:30')
  assert.equal(gruppen[1].eintraege[0].ungelesen, 2)
  // Leere Abschnitte fallen weg (kein „Untergruppen“-Kopf über nichts).
  assert.deepEqual(gruppierteListe([gespraech()], JETZT).map((g) => g.label), ['Gruppen'])
  assert.deepEqual(gruppierteListe([], JETZT), [])
  // CHAT-7a: Direktgespräche haben einen EIGENEN Abschnitt (hinter den
  // Gruppen) — er erscheint nur, wenn es welche gibt. Er heißt
  // „Direktnachrichten“ wie der Betreff der Glocke (CHAT-7a-UI-2, Punkt 7).
  // CHAT-7b (S3): Runden stehen als ERSTER Abschnitt — benannte Gespräche
  // zwischen Menschen, vor den Orten (Entwurf B-desktop). Sie erscheinen nur,
  // wenn es welche gibt.
  assert.deepEqual(ABSCHNITTE.map((a) => a.label),
    ['Runden', 'Gruppen', 'Untergruppen', 'Direktnachrichten'])
  const mitDirekt = gruppierteListe([
    gespraech({ name: 'g-chor', titel: 'Chor', letzte_am: zeit('2026-11-18', 10, 8) }),
    gespraech({ name: 'd-erika', art: 'direkt', gruppe: null, titel: 'Erika Muster',
      mitglied: 'M-1', teilnehmer: 2, letzte_am: zeit('2026-11-18', 11, 0) }),
  ], JETZT)
  assert.deepEqual(mitDirekt.map((g) => g.label), ['Gruppen', 'Direktnachrichten'],
    'der Abschnitt steht hinter den Gruppen und nur bei Treffern')
  assert.equal(mitDirekt[1].eintraege[0].titel, 'Erika Muster')
})

test('CHAT-3a · Liste: Zähler-Summe und leere/ungültige Werte', () => {
  assert.equal(ungelesenSumme([{ ungelesen: 2 }, { ungelesen: 3 }, { ungelesen: 0 }]), 5)
  assert.equal(ungelesenSumme([]), 0)
  // Unbekannte Werte zählen nicht und ergeben keine „NaN“-Anzeige.
  assert.equal(ungelesenSumme([{ ungelesen: null }, {}, { ungelesen: 'x' }]), 0)
  assert.equal(ungelesenSumme([{ ungelesen: -4 }]), 0)
  // Negative Zähler aus einer alten Antwort werden auf 0 gekappt.
  assert.equal(listenZeile(gespraech({ ungelesen: -3 }), JETZT).ungelesen, 0)
  assert.equal(listenZeile(null), null)
})

test('CHAT-3a · Liste: Untergruppe wird am `art` erkannt, nicht am Titel', () => {
  const ug = listenZeile(gespraech({ art: 'untergruppe', untergruppe: 'noten', titel: 'Notenausschuss' }), JETZT)
  assert.equal(ug.abschnitt, 'untergruppe')
  // Ohne `art` (alte Antwort) entscheidet die Untergruppe selbst.
  const alt = listenZeile({ gruppe: 'chor', untergruppe: 'noten', titel: 'Noten' }, JETZT)
  assert.equal(alt.abschnitt, 'untergruppe')
  assert.equal(listenZeile({ gruppe: 'chor', titel: 'Chor' }, JETZT).abschnitt, 'gruppe')
})

// ══════════════════════════════════════════════════════════════════════════════
// 4 · Nachrichten und Verlauf
// ══════════════════════════════════════════════════════════════════════════════

/** Eine Server-Nachricht in der Form von `_zeile` (api/chat.py). */
function nachrichtFeld(überschreiben = {}) {
  return {
    name: 'chat-n-1',
    gespraech: 'chat-gespraech-1',
    autor: 'Miriam Berg',
    autor_mitglied: 'm-miriam',
    eigene: false,
    text: 'Am Samstag um 14 Uhr.',
    geloescht: false,
    bearbeitet: false,
    bearbeitet_am: null,
    erstellt_am: zeit('2026-11-18', 9, 12),
    antwort_auf: null,
    antwort_auf_text: null,
    reaktionen: [],
    gelesen_von: null,
    ...überschreiben,
  }
}

test('CHAT-3a · Lesestand: NUR Summe an eigenen Nachrichten (F2)', () => {
  const eigene = verlaufsZeile(nachrichtFeld({ eigene: true, gelesen_von: 6 }), { ich: 'konto-ich', jetzt: JETZT })
  assert.equal(eigene.gelesen_von, 6)
  assert.equal(lesestandText(eigene), 'gelesen von 6')
  // Fremde Nachricht: der Server schickt `null` — die Oberfläche zeigt nichts,
  // auch wenn versehentlich eine Zahl ankäme (kein Verhaltensprofil).
  const fremd = verlaufsZeile(nachrichtFeld({ gelesen_von: 6 }), { ich: 'konto-ich', jetzt: JETZT })
  assert.equal(fremd.gelesen_von, null)
  assert.equal(lesestandText(fremd), '')
  // Null Leser: keine Zeile (kein „gelesen von 0“).
  assert.equal(lesestandText(verlaufsZeile(nachrichtFeld({ eigene: true, gelesen_von: 0 }), { jetzt: JETZT })), '')
  // Es gibt KEIN Feld mit Namen — die Antwort trägt nur die Zahl.
  assert.ok(!('gelesen_von_liste' in eigene))
})

test('CHAT-3a · Verlauf: eigene rechts, Zitat, „bearbeitet“, Reaktionen', () => {
  const zitat = verlaufsZeile(nachrichtFeld({
    eigene: true,
    autor_mitglied: 'm-ich',
    antwort_auf: 'chat-n-0',
    antwort_auf_text: 'Kann ich die Mappen holen?',
    bearbeitet: true,
    reaktionen: [{ reaktion: '👍', anzahl: 4, von_mir: false }],
    erstellt_am: zeit('2026-11-18', 9, 15),
  }), { ich: 'm-ich', jetzt: JETZT })
  assert.equal(zitat.eigene, true)
  assert.equal(zitat.zeit, '09:15')
  assert.equal(zitat.antwortText, 'Kann ich die Mappen holen?')
  assert.equal(zitat.bearbeitet, true)
  assert.deepEqual(zitat.reaktionen, [{ reaktion: '👍', anzahl: 4, von_mir: false }])
  // Ein Konto, dessen Mitglied-Kennung fehlt: der Server sagt `eigene`.
  assert.equal(verlaufsZeile(nachrichtFeld({ eigene: true, autor_mitglied: null }), { ich: '' }).eigene, true)
})

test('CHAT-3a · Gelöschte Nachricht: Hinweiszeile, NIE der Text', () => {
  const eigene = verlaufsZeile(nachrichtFeld({ eigene: true, geloescht: true, text: null }), { jetzt: JETZT })
  assert.equal(eigene.geloescht, true)
  assert.equal(eigene.text, '', 'kein Inhalt einer gelöschten Nachricht')
  assert.equal(eigene.hinweis, 'Du hast diese Nachricht gelöscht.')
  // Fremde Löschung (Moderation) mit Grund: der Grund steht dabei.
  const moderiert = verlaufsZeile(nachrichtFeld({ geloescht: true, text: null, entfernt_grund: 'Beleidigung' }), { jetzt: JETZT })
  assert.equal(moderiert.hinweis, 'Von der Leitung entfernt: Beleidigung')
  // Ohne bekannten Grund bleibt die neutrale Zeile (CHAT-6 liefert den Grund).
  assert.equal(
    verlaufsZeile(nachrichtFeld({ geloescht: true, text: null }), { jetzt: JETZT }).hinweis,
    'Diese Nachricht wurde gelöscht.',
  )
  // Auch wenn ein Text ANKÄME: er wird nicht angezeigt.
  assert.equal(verlaufsZeile(nachrichtFeld({ geloescht: true, text: 'geheim' }), { jetzt: JETZT }).text, '')
  assert.equal(hinweisText({ geloescht: false }), '')
})

test('CHAT-3a · Bearbeiten: nur eigene, nur innerhalb von 15 Minuten', () => {
  assert.equal(BEARBEITEN_MINUTEN, 15)
  const frisch = zeit('2026-11-18', 11, 50) // 10 Minuten vor JETZT
  const alt = zeit('2026-11-18', 11, 40)    // 20 Minuten vor JETZT
  const meine = verlaufsZeile(nachrichtFeld({ eigene: true, erstellt_am: frisch }), { jetzt: JETZT })
  assert.equal(meine.bearbeitbar, true)
  const zuAlt = verlaufsZeile(nachrichtFeld({ eigene: true, erstellt_am: alt }), { jetzt: JETZT })
  assert.equal(zuAlt.bearbeitbar, false)
  const fremd = verlaufsZeile(nachrichtFeld({ eigene: false, erstellt_am: frisch }), { jetzt: JETZT })
  assert.equal(fremd.bearbeitbar, false)
  // Gelöscht: nicht mehr bearbeitbar.
  assert.equal(innerhalbFrist(frisch, JETZT), true)
  assert.equal(innerhalbFrist('', JETZT), false)
  assert.equal(verlaufsZeile(nachrichtFeld({ eigene: true, geloescht: true, erstellt_am: frisch }), { jetzt: JETZT }).bearbeitbar, false)
})

// ══════════════════════════════════════════════════════════════════════════════
// 5 · Nachladen (seitenweise)
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Eine Seite des Servers. `ids` steht in Anzeige-Reihenfolge alt → neu; die
 * Zeitstempel wachsen mit. Der Server liefert `neueste` und `vor` von neu nach
 * alt (`seit` von alt nach neu) — die Seite bildet das nach. Die Reihenfolge
 * der Antwort ist für die Regel egal (sie sortiert selbst), aber der Test soll
 * nicht versehentlich von ihr abhängen.
 */
function seite(ids, tag = '2026-11-18', startStunde = 9, ab = 0, richtung = 'neueste') {
  const zeilen = ids.map((id, i) => nachrichtFeld({
    name: id,
    text: `Text ${id}`,
    erstellt_am: zeit(tag, startStunde + ab + Math.floor(i / 60), i % 60),
  }))
  return { richtung, nachrichten: richtung === 'seit' ? zeilen : zeilen.slice().reverse() }
}

test('CHAT-3a · Verlauf: die neueste Seite füllt den leeren Verlauf', () => {
  const lage = seiteEinordnen(seite(['a', 'b', 'c']), { ich: '', jetzt: JETZT })
  assert.deepEqual(lage.nachrichten.map((n) => n.ident), ['a', 'b', 'c'])
  assert.equal(lage.vor, 'a')
  assert.equal(lage.seit, 'c')
  assert.equal(lage.nachrichten[0].ident, "a", "die Kennung steht im gedeuteten Feld")
  // MUSS 1: Die neueste Seite sagt über „ältere gibt es“ NICHTS (`null`) —
  // erst ein voller älterer Abruf entscheidet das (`aelterStand`).
  assert.equal(lage.aelterMoeglich, null)
  assert.equal(lage.neuHinzugefuegt, 3)
  // Leere Antwort: kein Nachladen mehr möglich, nichts erfunden.
  const leer = seiteEinordnen({ richtung: 'vor', nachrichten: [] }, { jetzt: JETZT })
  assert.deepEqual(leer.nachrichten, [])
  assert.equal(leer.aelterMoeglich, false, 'leere ältere Seite = Anfang erreicht')
})

test('CHAT-3a · Verlauf: ältere Seite wird OBEN angehängt (ohne Doppel)', () => {
  // Bekannt: d (09:01) und e (09:02) — die neueste Seite des Gesprächs.
  const alt = seiteEinordnen(seite(['d', 'e'], '2026-11-18', 9, 1), { jetzt: JETZT }).nachrichten
  // Ältere Seite davor: a, b, c (`richtung: 'vor'` — so meldet es der Server).
  const aeltere = seiteEinordnen(seite(['a', 'b', 'c'], '2026-11-18', 9, 0, 'vor'), { alt, jetzt: JETZT })
  assert.deepEqual(aeltere.nachrichten.map((n) => n.ident), ['a', 'b', 'c', 'd', 'e'])
  assert.equal(aeltere.vor, 'a', 'der neue Anker ist die älteste Zeile')
  assert.equal(aeltere.seit, 'e')
  assert.equal(aeltere.neuHinzugefuegt, 0, 'nach oben kommt nichts „Neues“ für das Auto-Scroll')
  // Eine Seite, die die bekannte Zeile MITBRINGT (Naht), erzeugt keine Kopie.
  const naht = seiteEinordnen(seite(['c', 'd'], '2026-11-18', 9, 1, 'vor'), { alt, jetzt: JETZT })
  assert.deepEqual(naht.nachrichten.map((n) => n.ident), ['c', 'd', 'e'], 'keine doppelte „d“')
  // Ohne `richtung` entscheidet die Kennung: die Seite beginnt NICHT mit „d“ →
  // sie gilt als ältere.
  const ohneRichtung = seiteEinordnen({ nachrichten: seite(['a', 'b', 'c']).nachrichten }, { alt, jetzt: JETZT })
  assert.deepEqual(ohneRichtung.nachrichten.map((n) => n.ident), ['a', 'b', 'c', 'd', 'e'])
})

test('CHAT-3a · MUSS 1: nur richtung "vor" ist älter — sonst wird ERSETZT und ANGEHÄNGT', () => {
  // Bekannt sind 50 Zeilen (n0 … n49, volle Seite). Der nächste Abruf kommt als
  // `neueste` und ist um eins verschoben: n0 fällt heraus, n50 kommt dazu —
  // ZUSÄTZLICH ist n10 bearbeitet. Die Seite beginnt also NICHT mit der ersten
  // bekannten Zeile; nach der Kennung allein wäre sie „älter“. Die Richtung
  // des Servers entscheidet: jünger.
  const ids = Array.from({ length: 50 }, (_, i) => `n${i}`)
  const alt = ids.map((id, i) => nachrichtFeld({
    name: id, text: `Text ${id}`, erstellt_am: zeit('2026-11-18', 9 + Math.floor(i / 60), i % 60),
  }))
  assert.equal(alt.length, 50)

  // `neueste` kommt beim Server von neu nach alt (er dreht sie erst danach um) —
  // die Seite hier ist entsprechend geordnet.
  const verschoben = ids.slice(1).concat('n50')
  const antwort = {
    richtung: 'neueste',
    nachrichten: verschoben.map((id) => (
      id === 'n10'
        ? nachrichtFeld({
          name: id,
          text: 'Text n10 (bearbeitet)',
          bearbeitet: true,
          erstellt_am: zeit('2026-11-18', 9, 10),
        })
        : nachrichtFeld({
          name: id,
          text: `Text ${id}`,
          erstellt_am: zeit('2026-11-18', 9 + Math.floor(Number(id.slice(1)) / 60), Number(id.slice(1)) % 60),
        })
    )).reverse(),
  }
  const lage = seiteEinordnen(antwort, { alt, jetzt: JETZT })
  assert.deepEqual(lage.nachrichten.map((n) => n.ident), ids.concat('n50'),
    'n0 bleibt (nicht gelöscht), n50 hängt hinten an, keine Doppel')
  assert.equal(lage.nachrichten.find((n) => n.ident === 'n10').text, 'Text n10 (bearbeitet)',
    'die bearbeitete Nachricht wird ERSETZT, nicht verworfen')
  assert.equal(lage.nachrichten.find((n) => n.ident === 'n10').bearbeitet, true)
  assert.equal(lage.neuHinzugefuegt, 1, 'nur n50 ist NEU (die Bearbeitung ist kein neuer Beitrag)')
  assert.equal(lage.aktualisiert, 1,
    'NUR die wirklich geänderte Zeile zählt — nicht die 49 unveränderten der vollen Seite')
  assert.equal(lage.vor, 'n0', 'der Anker bleibt die älteste bekannte Zeile')
  assert.equal(lage.seit, 'n50')
  assert.equal(lage.aelterMoeglich, null, 'der Poll schaltet das Nachladen NICHT wieder an')
  // Dieselbe Antwort als Poll (`richtung: 'seit'`) — gleiches Ergebnis.
  const poll = seiteEinordnen({ ...antwort, richtung: 'seit' }, { alt, jetzt: JETZT })
  assert.deepEqual(poll.nachrichten.map((n) => n.ident), ids.concat('n50'))
  assert.equal(poll.neuHinzugefuegt, 1)
  // Und nach dem Nachladen ÄLTERER Seiten bleibt es dabei: der Poll davor
  // ändert die Richtung nicht (richtung entscheidet, nicht die Kennung).
  const aelter = seiteEinordnen(seite(['m1', 'm2'], '2026-11-17', 9, 0, 'vor'), { alt, jetzt: JETZT })
  assert.equal(aelter.aelterMoeglich, false, 'kurze ältere Seite = Anfang erreicht')
  const danach = seiteEinordnen(antwort, { alt: aelter.nachrichten, jetzt: JETZT })
  assert.equal(danach.neuHinzugefuegt, 1, 'auch nach dem Nachladen zählt nur das wirklich Neue')
  assert.deepEqual(danach.nachrichten.map((n) => n.ident), ['m1', 'm2', ...ids, 'n50'])
  assert.equal(aelterStand(true, danach.aelterMoeglich), true, 'der Poll lässt den Stand stehen')
})

test('CHAT-3a · MUSS 1: eine VOLLE ältere Seite hält das Nachladen an, eine kurze beendet es', () => {
  const alt = seiteEinordnen(seite(['n0', 'n1']), { jetzt: JETZT }).nachrichten
  const voll = Array.from({ length: 50 }, (_, i) => `m${String(i).padStart(2, '0')}`)
  const lage = seiteEinordnen(seite(voll, '2026-11-17', 9, 0, 'vor'), { alt, jetzt: JETZT })
  assert.equal(lage.aelterMoeglich, true, '50 = Seitengröße → weiter nachladen')
  const kurz = seiteEinordnen(seite(voll.slice(0, 49), '2026-11-17', 9, 0, 'vor'), { alt, jetzt: JETZT })
  assert.equal(kurz.aelterMoeglich, false, `${SEITENGROESSE - 1} < ${SEITENGROESSE} → Anfang erreicht`)
  assert.equal(SEITENGROESSE, 50, 'die Seitengröße ist die des Servers')
  assert.equal(aelterStand(true, kurz.aelterMoeglich), false)
  assert.equal(aelterStand(false, null), false)
})

test('CHAT-3a · Verlauf: Polling hängt NEUE Zeilen hinten an und ersetzt Bekanntes', () => {
  const alt = seiteEinordnen(seite(['a', 'b']), { jetzt: JETZT }).nachrichten
  // Neuer Abruf: b (jetzt mit Reaktion) und c sind neu. `richtung: 'seit'` ist
  // die Angabe des Servers für den Polling-Abruf.
  const antwort = {
    richtung: 'seit',
    nachrichten: [
      nachrichtFeld({ name: 'b', erstellt_am: zeit('2026-11-18', 9, 1), reaktionen: [{ reaktion: '❤', anzahl: 1, von_mir: true }] }),
      nachrichtFeld({ name: 'c', erstellt_am: zeit('2026-11-18', 9, 2) }),
    ],
  }
  const lage = seiteEinordnen(antwort, { alt, jetzt: JETZT })
  assert.deepEqual(lage.nachrichten.map((n) => n.ident), ['a', 'b', 'c'])
  assert.equal(lage.nachrichten[1].reaktionen[0].reaktion, '❤', 'die bekannte Zeile wird ersetzt')
  assert.equal(lage.neuHinzugefuegt, 1, 'nur „c“ ist wirklich neu')
  assert.equal(lage.seit, 'c')
  assert.equal(lage.nachrichten.length, 3, 'keine Doppel')
  // Derselbe Fall OHNE `richtung`: die Kennung der ersten Zeile entscheidet.
  const ohneRichtung = seiteEinordnen({ nachrichten: antwort.nachrichten }, { alt, jetzt: JETZT })
  assert.deepEqual(ohneRichtung.nachrichten.map((n) => n.ident), ['a', 'b', 'c'])
})

test('CHAT-3a · `aktualisiert` zählt NUR wirklich geänderte bekannte Zeilen', () => {
  // Review R1, Punkt 3: eine volle Seite mit EINER Bearbeitung darf nicht 49
  // melden. Gezählt wird der Unterschied zum bisherigen Stand — unveränderte
  // Zeilen (auch wenn der Server sie mitschickt) zählen nicht mit.
  const ids = Array.from({ length: 50 }, (_, i) => `n${i}`)
  const feld = (id, extra = {}) => nachrichtFeld({
    name: id,
    text: `Text ${id}`,
    erstellt_am: zeit('2026-11-18', 9, Number(id.slice(1)) % 60),
    ...extra,
  })
  const alt = seiteEinordnen({ richtung: 'neueste', nachrichten: ids.map((id) => feld(id)) },
    { jetzt: JETZT }).nachrichten
  assert.equal(alt.length, 50)

  // Dieselbe Seite, nichts geändert → 0 (vorher: 49).
  const ruhig = seiteEinordnen({ richtung: 'seit', nachrichten: ids.map((id) => feld(id)) },
    { alt, jetzt: JETZT })
  assert.equal(ruhig.aktualisiert, 0, 'unveränderte Zeilen zählen nicht')
  assert.equal(ruhig.neuHinzugefuegt, 0)

  // Eine Bearbeitung → genau 1.
  const eins = seiteEinordnen({
    richtung: 'seit',
    nachrichten: ids.map((id) => (id === 'n7' ? feld(id, { text: 'neu', bearbeitet: true }) : feld(id))),
  }, { alt, jetzt: JETZT })
  assert.equal(eins.aktualisiert, 1, 'eine geänderte Zeile = 1')
  assert.equal(eins.neuHinzugefuegt, 0)
  assert.equal(eins.nachrichten.find((n) => n.ident === 'n7').text, 'neu')

  // Reaktion und Lesestand zählen ebenfalls als Änderung (sie stehen in der Blase).
  const reaktion = seiteEinordnen({
    richtung: 'seit',
    nachrichten: ids.map((id) => (id === 'n3' ? feld(id, { reaktionen: [{ reaktion: '❤', anzahl: 2 }] }) : feld(id))),
  }, { alt, jetzt: JETZT })
  assert.equal(reaktion.aktualisiert, 1, 'eine neue Reaktion ist eine Änderung')

  // Die Uhr-Verschiebung allein (späterer Betrachtungszeitpunkt, gleicher
  // Serverstand) ist KEINE Änderung — sonst zählte jeder Poll alles mit.
  const spaeter = seiteEinordnen({ richtung: 'seit', nachrichten: ids.map((id) => feld(id)) },
    { alt, jetzt: new Date(JETZT.getTime() + 3 * 86_400_000) })
  assert.equal(spaeter.aktualisiert, 0, 'nur die Anzeigezeit verschiebt sich, kein Inhalt')

  // Keine Debug-Reste im ausgelieferten Modul (Review R1, Punkt 2).
  const QUELLE = lies('composables/nachrichtenLogik.mjs')
  assert.doesNotMatch(QUELLE, /rohProbe|zProbe|arrProbe/, 'keine Fehlersuche-Reste')
})

test('CHAT-3a · Verlauf: gleiche Zeit → die Kennung entscheidet (stabile Ordnung)', () => {
  const gleich = zeit('2026-11-18', 9, 0)
  const antwort = { nachrichten: [
    nachrichtFeld({ name: 'chat-n-b', erstellt_am: gleich }),
    nachrichtFeld({ name: 'chat-n-a', erstellt_am: gleich }),
  ] }
  const lage = seiteEinordnen(antwort, { jetzt: JETZT })
  assert.deepEqual(lage.nachrichten.map((n) => n.ident), ['chat-n-a', 'chat-n-b'])
})

// ══════════════════════════════════════════════════════════════════════════════
// 6 · Polling und Aufräumen
// ══════════════════════════════════════════════════════════════════════════════

/** Attrappen: Timer, Sichtbarkeit, Uhr — kein echter Timer im Test. */
function umgebung({ sichtbar = true } = {}) {
  const stand = { timer: [], sichtbar: sichtbar, beobachter: 0, abgemeldet: 0, uhr: 1_000_000 }
  return {
    stand,
    jetzt: () => stand.uhr,
    timer: (fn, ms) => { const id = { fn, ms, weg: false }; stand.timer.push(id); return id },
    timerAus: (id) => { if (id) id.weg = true },
    sichtbar: () => stand.sichtbar,
    sichtbarkeitBeobachten: (fn) => {
      stand.beobachter += 1
      stand.aendern = fn
      return () => { stand.abgemeldet += 1 }
    },
  }
}

test('CHAT-3a · Polling: nur bei sichtbarem Tab, nie zwei Abrufe gleichzeitig', () => {
  assert.equal(TAKT_MS, 10_000)
  assert.equal(darfAbfragen({ sichtbar: true, laeuft: false, jetzt: 10_000, takt: TAKT_MS }), true)
  assert.equal(darfAbfragen({ sichtbar: false, jetzt: 10_000 }), false, 'verborgen: kein Abruf')
  assert.equal(darfAbfragen({ sichtbar: true, laeuft: true, jetzt: 10_000 }), false, 'kein Stau')
  // Zu früh nach dem letzten Abruf (9,9 s) → warten.
  assert.equal(darfAbfragen({ sichtbar: true, letzterAbruf: 10_000, jetzt: 10_000 + TAKT_MS - 100 }), false)
  assert.equal(darfAbfragen({ sichtbar: true, letzterAbruf: 10_000, jetzt: 10_000 + TAKT_MS }), true)
})

test('CHAT-3a · Polling: der Takt fragt erst nach Ablauf, wartet auf die Antwort', async () => {
  const um = umgebung()
  let abrufe = 0
  let aufloesen = null
  const takt = taktGeber({
    ...um,
    abfragen: () => { abrufe += 1; return new Promise((r) => { aufloesen = r }) },
  })
  assert.equal(takt.takt(um.stand.uhr), true)
  assert.equal(abrufe, 1)
  // Solange die Antwort läuft, startet kein zweiter Abruf — auch nach 30 s.
  um.stand.uhr += 3 * TAKT_MS
  assert.equal(takt.takt(um.stand.uhr), false)
  assert.equal(abrufe, 1, 'kein Stau bei langsamem Server')
  aufloesen()
  await new Promise((r) => setImmediate(r))
  assert.equal(takt.stand().laeuft, false)
  // Jetzt wieder fällig.
  assert.equal(takt.takt(um.stand.uhr), true)
  assert.equal(abrufe, 2)
})

test('CHAT-3a · Polling: verborgener Tab fragt nicht — und holt beim Zurückkommen EINMAL nach', async () => {
  const um = umgebung({ sichtbar: false })
  let abrufe = 0
  const takt = taktGeber({ ...um, abfragen: () => { abrufe += 1; return Promise.resolve() } })
  takt.starten()
  // Verborgen wird KEIN Termin gesetzt (der Beobachter weckt uns) — kein Timer,
  // der im Hintergrund weiterläuft.
  assert.equal(um.stand.timer.length, 0, 'verborgen: kein Timer')
  assert.equal(abrufe, 0)
  // Wieder sichtbar → sofort EIN Abruf (nicht der ganze Rückstand).
  um.stand.sichtbar = true
  um.stand.uhr += 5 * TAKT_MS
  um.stand.aendern()
  assert.equal(um.stand.timer.length, 1, 'genau EIN Termin nach dem Zurückkommen')
  assert.equal(um.stand.timer[0].ms, 0, 'sofort, nicht erst nach dem Takt')
  um.stand.timer[0].fn()
  await new Promise((r) => setImmediate(r))
  assert.equal(abrufe, 1)
  // Danach läuft der normale Takt weiter (EIN geplanter Termin).
  assert.equal(um.stand.timer.length, 2)
  assert.equal(um.stand.timer[1].ms, TAKT_MS)
})

test('CHAT-3a · Polling: „anhalten“ räumt Timer UND Beobachter ab (idempotent)', () => {
  const um = umgebung()
  const takt = taktGeber({ ...um, abfragen: () => {} })
  // Zweimal starten erzeugt KEINEN zweiten Timer und keinen zweiten Beobachter.
  takt.starten()
  takt.starten()
  assert.equal(um.stand.timer.length, 1, 'ein Timer')
  assert.equal(um.stand.beobachter, 1, 'ein Beobachter')
  assert.equal(takt.istGestartet(), true)
  takt.anhalten()
  assert.equal(um.stand.timer[0].weg, true, 'Timer angehalten')
  assert.equal(um.stand.abgemeldet, 1, 'Sichtbarkeit abgemeldet')
  assert.equal(takt.istGestartet(), false)
  // Ein zweites Anhalten ist harmlos (kein doppeltes Abmelden).
  takt.anhalten()
  assert.equal(um.stand.abgemeldet, 1)
  // MUSS 3 (Timer-Leck): ein spät eintreffendes `starten()` nach dem Anhalten
  // öffnet KEINEN zweiten Timer — die Seite ist abgebaut.
  assert.equal(takt.starten(), null, 'nach anhalten kein Neustart von selbst')
  assert.equal(takt.istGestartet(), false)
  assert.equal(um.stand.timer.length, 1, 'kein zweiter Timer')
  // Nur der ausdrückliche Neustart weckt ihn wieder.
  takt.starten({ wieder: true })
  assert.equal(takt.istGestartet(), true)
  assert.equal(um.stand.timer.length, 2)
})

test('CHAT-3a · Polling: ein Fehler der Abfrage beendet den Takt nicht', async () => {
  const um = umgebung()
  let versuche = 0
  const takt = taktGeber({
    ...um,
    abfragen: () => {
      versuche += 1
      if (versuche === 1) throw new Error('weg')
      return Promise.resolve()
    },
  })
  takt.starten()
  assert.equal(takt.takt(um.stand.uhr), false, 'ein geworfener Fehler wird gefangen')
  assert.equal(takt.stand().laeuft, false, 'der Takt bleibt benutzbar')
  um.stand.uhr += TAKT_MS
  assert.equal(takt.takt(um.stand.uhr), true)
  await new Promise((r) => setImmediate(r))
  assert.equal(versuche, 2, 'der nächste Takt läuft wieder')
})

test('CHAT-3a · Polling: eine abgelehnte Abfrage erzeugt keine unbehandelte Ablehnung', async () => {
  const um = umgebung()
  const takt = taktGeber({ ...um, abfragen: () => Promise.reject(new Error('kaputt')) })
  takt.takt(um.stand.uhr)
  await new Promise((r) => setImmediate(r))
  assert.equal(takt.stand().laeuft, false)
})

// ══════════════════════════════════════════════════════════════════════════════
// 7 · Eingabe und Tastatur
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · Eingabe: leerer Text wird abgewiesen, Absätze bleiben', () => {
  assert.equal(NACHRICHT_MAX, 4000)
  assert.deepEqual(pruefeText(''), { ok: false, text: '', fehler: 'Bitte einen Text eingeben.' })
  assert.equal(pruefeText('   \n  ').ok, false, 'nur Leerraum ist leer')
  // Der Text wird NICHT getrimmt (Zeilenumbrüche und Einrückung sind Inhalt).
  const mehrzeilig = '  Erste Zeile\n\nZweite Zeile  '
  const geprueft = pruefeText(mehrzeilig)
  assert.equal(geprueft.ok, true)
  assert.equal(geprueft.text, mehrzeilig)
  assert.equal(geprueft.fehler, '')
  // ZU lang: die Grenze nennt die Zahl (wie der Server).
  const zuLang = 'x'.repeat(NACHRICHT_MAX + 1)
  const abgelehnt = pruefeText(zuLang)
  assert.equal(abgelehnt.ok, false)
  assert.match(abgelehnt.fehler, /4000/)
  assert.match(abgelehnt.fehler, new RegExp(String(NACHRICHT_MAX + 1)))
  // Genau die Grenze ist erlaubt.
  assert.equal(pruefeText('x'.repeat(NACHRICHT_MAX)).ok, true)
  assert.equal(pruefeText(null).ok, false)
})

test('CHAT-3a · Tastatur: Enter sendet, Shift+Enter macht einen Absatz', () => {
  assert.equal(tasteImFeld({ key: 'Enter' }), 'senden')
  assert.equal(tasteImFeld({ key: 'Enter', shiftKey: true }), 'umbruch')
  assert.equal(tasteImFeld({ key: 'a' }), 'sonst')
  assert.equal(tasteImFeld({ key: 'Enter', isComposing: true }), 'sonst', 'IME nicht stören')
  assert.equal(SENDEN_TEXT, 'Nachricht senden')
  assert.equal(eingabePlatzhalter('Chor'), 'Nachricht an Chor …')
  assert.equal(eingabePlatzhalter(''), 'Nachricht schreiben …')
})

// ══════════════════════════════════════════════════════════════════════════════
// 8 · Reaktionen
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · Reaktionen: dasselbe Set wie der Server, EINE je Person', () => {
  // Die Zeichen stehen im Model (`REAKTIONEN` in models/chat.py) — eine andere
  // Liste hier hieße: der Server lehnt das angebotene Zeichen mit 417 ab.
  assert.deepEqual(REAKTIONEN, ['👍', '❤', '🙏', '✅', '😀', '😢'])
  assert.equal(istReaktion('👍'), true)
  assert.equal(istReaktion('🙈'), false)
  const vorhanden = [{ reaktion: '❤', anzahl: 1, von_mir: true }]
  assert.equal(naechsteReaktion(vorhanden, '❤'), '', 'mein Zeichen erneut → entfernen')
  assert.equal(naechsteReaktion(vorhanden, '👍'), '👍', 'anderes Zeichen → wechseln')
  assert.equal(naechsteReaktion([], '👍'), '👍')
  assert.equal(naechsteReaktion(vorhanden, '🙈'), '', 'unbekannt → nichts senden')

  // Die Zeile unter der Blase zeigt nur GESETZTE Zeichen, in fester Reihenfolge.
  const zeile = reaktionsZeile([
    { reaktion: '✅', anzahl: 1, von_mir: false },
    { reaktion: '❤', anzahl: 1, von_mir: true },
  ])
  assert.deepEqual(zeile.map((e) => e.reaktion), ['❤', '✅'])
  // Das Menü bietet ALLE sechs Zeichen an, mit Vermerk „meines“.
  const auswahl = reaktionsAuswahl([{ reaktion: '❤', anzahl: 2, von_mir: true }])
  assert.equal(auswahl.length, 6)
  assert.equal(auswahl.find((e) => e.reaktion === '❤').meines, true)
  assert.equal(auswahl.find((e) => e.reaktion === '❤').anzahl, 2)
  assert.equal(auswahl.find((e) => e.reaktion === '👍').meines, false)
})

// ══════════════════════════════════════════════════════════════════════════════
// 9 · Fehler und Leerzustände
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · 403 heißt „kein Zugriff“ (der Server antwortet ohne Inhalt)', () => {
  const zustand = fehlerZustand({ status: 403 })
  assert.equal(zustand.art, 'kein-zugriff')
  assert.match(zustand.titel, /Kein Zugriff/)
  // Auch die Fehlerklasse allein genügt (ohne Status).
  assert.equal(fehlerZustand({ exc_type: 'PermissionError' }).art, 'kein-zugriff')
  // Nicht gefunden: eigenes Gespräch gelöscht.
  assert.equal(fehlerZustand({ status: 404 }).art, 'weg')
  // Eingabefehler: der Satz des Servers („nur in den ersten 15 Minuten …“).
  const eingabe = fehlerZustand({ status: 417, message: 'Nachrichten lassen sich nur in den ersten 15 Minuten bearbeiten.' })
  assert.equal(eingabe.art, 'eingabe')
  assert.match(eingabe.text, /15 Minuten/)
  // Alles andere gehört dem Fehlerkatalog (`fehlertext`) — hier `null`.
  assert.equal(fehlerZustand({ status: 500 }), null)
  assert.equal(fehlerZustand(null), null)
})

test('CHAT-3a · Leerzustände und Modul-Hinweis benennen den nächsten Schritt', () => {
  for (const text of [LISTE_LEER, VERLAUF_LEER, MODUL_AUS]) {
    assert.ok(text.titel.length > 3)
    assert.ok(text.text.length > 20, `„${text.titel}“ erklärt nichts`)
  }
  assert.match(MODUL_AUS.text, /Leitung|eingeschaltet/)
  assert.ok(VORSCHAU_MAX >= 80, 'die Vorschau einer Nachricht ist lang genug für einen Satz')
})

// ══════════════════════════════════════════════════════════════════════════════
// 10 · Die Bausteine (Quelltext, weil es keine aufrufbare Funktion gibt)
// ══════════════════════════════════════════════════════════════════════════════

const SEITE = lies('pages/Nachrichten.vue')
const BLASE = lies('components/chat/ChatBlase.vue')
const LISTE = lies('components/chat/ChatListe.vue')
const APP = lies('App.vue')

test('CHAT-3a · die Seite zeichnet Liste und Verlauf (kein Platzhalter mehr)', () => {
  const { tpl, skript } = teile(SEITE)
  const t = ohneKommentare(tpl)
  // Der Platzhalter der CHAT-R2a-Karte ist weg.
  assert.ok(!/Nachrichten kommen in Kürze/.test(t), 'kein Platzhaltertext mehr')
  // Beide Bausteine werden benutzt.
  assert.match(skript, /import ChatListe from '\.\.\/components\/chat\/ChatListe\.vue'/)
  assert.match(skript, /import ChatBlase from '\.\.\/components\/chat\/ChatBlase\.vue'/)
  assert.match(t, /<ChatListe/)
  assert.match(t, /<ChatBlase/)
  // Die Adresse entscheidet, was gezeigt wird (Liste / Gespräch) — sie wird
  // EINMAL gelesen (`hash`) und daraus die Kennung abgeleitet (CHAT-3c-2: die
  // Seite liest aus derselben Adresse auch Begriff und `&offen=`).
  assert.match(skript, /const hash = typeof window === 'undefined' \? '' : window\.location\.hash/,
    'die Adresse wird gelesen')
  assert.match(skript, /kennung\.value = gespraechAusHash\(hash\)/,
    'daraus die Gesprächskennung')
  // Die Seite benutzt die vorhandenen API-Helfer (keine eigene fetch-Kette).
  assert.match(skript, /apiGet\('chat\.meine_gespraeche'\)/)
  assert.match(skript, /apiGet\('chat\.verlauf'/)
  assert.match(skript, /apiCall\('chat\.senden'/)
  assert.match(skript, /apiCall\('chat\.reaktion_setzen'/)
  assert.match(skript, /apiCall\('chat\.lesestand_setzen'/)
  assert.match(skript, /apiCall\('chat\.aendern'/)
  assert.match(skript, /apiCall\('chat\.loeschen'/)
  assert.match(skript, /apiCall\('chat\.stumm_setzen'/)
  // Der Rückweg in die Liste steht im Markup (Zurück-Taste am Handy). Seit
  // CHAT-3c-2 ist das Ziel berechnet: Liste — oder die Suche, wenn sie das
  // Gespräch überdeckt (`zurueckZiel`).
  assert.match(t, /class="dk-chat-zurueck"[^>]*:href="zurueckZiel"/,
    'der Zurück-Pfeil führt auf das berechnete Ziel')
  assert.match(skript, /const zurueckZiel = computed/, 'und das Ziel ist berechnet')
})

test('CHAT-3a · Barrierefreiheit: role="log" + aria-live="polite", Fokus nach Wechsel', () => {
  const { tpl, skript } = teile(SEITE)
  const t = ohneKommentare(tpl)
  assert.match(t, /role="log"/, 'der Verlauf ist eine Log-Region')
  assert.match(t, /aria-live="polite"/, 'neue Nachrichten werden höflich angesagt')
  assert.match(t, /aria-relevant="additions"/)
  assert.match(t, /:aria-label="`Verlauf von \$\{titel\}`"/, 'die Region ist benannt')
  assert.match(t, /tabindex="-1"/, 'der Verlauf ist fokussierbar')
  // Fokus nach Gesprächswechsel (Karte Punkt 5).
  assert.match(skript, /verlaufEl\.value\.focus\(\)/)
  // Das Eingabefeld hat ein Label (nicht nur einen Platzhalter).
  assert.match(t, /<label[^>]*for="chat-eingabe"[^>]*>Nachricht schreiben<\/label>/)
  // Der Sende-Knopf trägt Text (N8) — kein nacktes Symbol.
  assert.match(t, /\{\{ SENDEN_TEXT \}\}/)
  // Die Tastatur ist verdrahtet: Enter sendet (keydown), Shift+Enter nicht.
  assert.match(t, /@keydown="beimTasten"/)
  assert.match(skript, /tasteImFeld\(\{[\s\S]{0,200}shiftKey: ereignis\.shiftKey/)
  assert.match(skript, /if \(absicht !== 'senden'\) return/)
})

test('CHAT-3a · der Verlauf ist eine LISTE in der Log-Region (<ul> statt <li> direkt)', () => {
  // Review R1: `role="log"` trägt keine <li> — die Blasen sind <li> und
  // brauchen ein <ul>. Ohne den Test könnte eine spätere Aufräumrunde das
  // <ul> wieder herausnehmen (DOM bliebe sichtbar gleich, die Struktur nicht).
  const { tpl } = teile(SEITE)
  const t = ohneKommentare(tpl)
  const logStart = t.indexOf('role="log"')
  assert.ok(logStart > 0, 'die Log-Region existiert')
  // Das <div> endet mit dem schließenden Tag NACH dem letzten Kind — gesucht
  // wird also ab dem Listenanfang bis zum Ende der Region (die Eingabe folgt).
  const logEnde = t.indexOf('dk-chat-eingabe', logStart)
  const region = t.slice(logStart, logEnde)
  assert.match(region, /<ul[^>]*class="dk-chat-verlaufsliste"/, 'die Zeilen stehen in einer Liste')
  assert.match(region, /<\/ul>/, 'die Liste wird geschlossen')
  // Zwischen <ul> und </ul> steht KEIN nacktes <li> außerhalb der Blase:
  // Tag-Zeilen und Blasen sind die einzigen <li>.
  const liste = region.slice(region.indexOf('<ul'), region.indexOf('</ul>'))
  assert.ok(liste.includes('<li v-if="n.tag"'), 'die Tages-Marke ist ein Listeneintrag')
  assert.match(liste, /<ChatBlase/, 'die Blase steht in der Liste')
  // Und die Blase selbst ist ein <li> (nicht ein <div> in einem <ul>).
  const BLASE = lies('components/chat/ChatBlase.vue')
  const blaseTpl = ohneKommentare(teile(BLASE).tpl)
  assert.match(blaseTpl, /<li\s[\s\S]{0,200}class="dk-chat-beitrag"/,
    'die Wurzel der Blase ist ein <li>')
})

test('CHAT-3a · Nachladen nach oben ist verdrahtet (Scroll an den Anfang)', () => {
  const { tpl, skript } = teile(SEITE)
  assert.match(tpl, /@scroll\.passive="beimScrollen"/)
  assert.match(skript, /if \(el\.scrollTop <= 24\) aeltereLaden\(\)/)
  // Der Abruf nutzt `vor` (ältere Seite) und hält die Scrollposition.
  assert.match(skript, /apiGet\('chat\.verlauf', \{ gespraech: offen, vor: anker \}\)/)
  assert.match(skript, /scrollTop = verlaufEl\.value\.scrollHeight - scrollVorher/)
})

test('CHAT-3a · MUSS 2: nach dem stillen Poll wird der Lesestand gesetzt (sichtbarer Tab)', () => {
  const s = ohneKommentare(teile(SEITE).skript)
  // Der stille Verlauf meldet den Lesestand, wenn fremde Neue da sind bzw.
  // ungelesen > 0 und der Tab sichtbar ist.
  assert.match(s, /lesestandFaellig\(\{/)
  assert.match(s, /neueFremde: fremdeNeue\(vorher, lage\.nachrichten\)/)
  assert.match(s, /sichtbar: tabSichtbar\(\)/)
  assert.match(s, /await lesestandSetzen\(\)/)
  // Und die Regel selbst sagt: nur bei sichtbarem Tab.
  assert.equal(lesestandFaellig({ neueFremde: 1, sichtbar: false }), false)
  assert.equal(lesestandFaellig({ neueFremde: 1, sichtbar: true }), true)
  assert.equal(lesestandFaellig({ neueFremde: 0, ungelesen: 3, sichtbar: true }), true)
  assert.equal(lesestandFaellig({ neueFremde: 0, ungelesen: 0, sichtbar: true }), false)
  // Eigene Nachrichten zählen nicht: wer selbst schreibt, hat nichts zu lesen.
  const fremd = [{ ident: 'a', eigene: false }, { ident: 'b', eigene: true }]
  assert.equal(fremdeNeue([], fremd), 1)
  assert.equal(fremdeNeue(fremd, fremd), 0, 'nichts Neues → 0')
})

test('CHAT-3a · Backoff nach Fehlern: verdoppeln bis 60 s, der erste Erfolg setzt zurück', async () => {
  assert.equal(backoffMs(0), 0, 'kein Fehler → Grundtakt')
  assert.equal(backoffMs(1), 2 * TAKT_MS)
  assert.equal(backoffMs(2), 4 * TAKT_MS)
  assert.equal(backoffMs(3), BACKOFF_MAX_MS, '40 s wird auf 60 s gekappt — die Obergrenze gilt immer')
  assert.equal(backoffMs(6), BACKOFF_MAX_MS)
  assert.equal(backoffMs(50), BACKOFF_MAX_MS, 'nie über eine Minute')
  // Der Takt übernimmt die gemeldete Wartezeit (`dauer`) für den nächsten Termin.
  const um = umgebung()
  let laeufe = 0
  const takt = taktGeber({
    ...um,
    abfragen: () => { laeufe += 1; return Promise.resolve({ dauer: laeufe < 2 ? backoffMs(laeufe) : TAKT_MS }) },
  })
  takt.starten()
  um.stand.timer[0].fn()
  await new Promise((r) => setImmediate(r))
  assert.equal(um.stand.timer[1].ms, 2 * TAKT_MS, 'nach dem Fehler doppelt so lange')
  um.stand.uhr += um.stand.timer[1].ms
  um.stand.timer[1].fn()
  await new Promise((r) => setImmediate(r))
  assert.equal(um.stand.timer[2].ms, TAKT_MS, 'der Erfolg setzt auf den Grundtakt zurück')
})

test('CHAT-3a · MUSS 4: meine_gespraeche EINMAL je Takt, Summe im Ereignis, App pausiert', () => {
  const s = ohneKommentare(teile(SEITE).skript)
  // Die Summe reist im Ereignis mit (`ungelesen`) — kein zweiter Abruf in der
  // App-Wurzel. Sie wird aus der EINEN Liste gerechnet (`ungelesenSumme`).
  assert.match(s, /new CustomEvent\('dk-chat-ungelesen', \{\s*detail: \{[^}]*ungelesen: zahl/)
  assert.match(s, /ungelesenSumme\(gespraeche\.value\)/)
  const app = ohneKommentare(teile(APP).skript)
  assert.match(app, /chatZaehler\.uebernehmen\(ereignis\?\.detail\?\.ungelesen\)/)
  assert.ok(!/chatZaehler\.holen\(\)\.catch/.test(app),
    'die App-Wurzel holt meine_gespraeche NICHT ein zweites Mal')
  // Der App-Zähler pausiert, solange die Nachrichten-Seite offen ist, und
  // fragt nur in der Handy-Lage (dort ist die Leiste sichtbar).
  assert.match(app, /seiteOffen: \(\) => currentPageName\.value === 'Nachrichten'/)
  assert.match(app, /handyLage: \(\) => istHandyLage\.value/)
  // Und die Seite MELDET sich selbst — so pausiert der App-Takt schon im
  // Fenster zwischen Aufbau der Seite und dem Wechsel des Seitennamens.
  assert.match(s, /new CustomEvent\('dk-chat-seite', \{\s*detail: \{ offen:/)
  assert.match(app, /window\.addEventListener\('dk-chat-seite', seitenMeldung\)/)
  assert.match(app, /chatZaehler\.seiteMeldet\(ereignis\?\.detail\?\.offen\)/)
  assert.match(app, /removeEventListener\('dk-chat-seite', seitenMeldung\)/,
    'der Beobachter wird beim Abbau abgemeldet')
})

test('CHAT-3a · MUSS 4: die Eigenmeldung der Seite pausiert den App-Takt sofort', async () => {
  const { useChatZaehler } = await import('../src/diakonos/composables/useChatZaehler.js')
  let abrufe = 0
  // Der Router kennt den Seitennamen noch NICHT (Fenster beim Aufbau) — allein
  // die Eigenmeldung der Seite verhindert den doppelten Abruf.
  const zaehler = useChatZaehler({
    aktiv: () => true,
    seiteOffen: () => false,
    handyLage: () => true,
    abfragen: () => { abrufe += 1; return Promise.resolve({ gespraeche: [{ ungelesen: 4 }] }) },
  })
  zaehler.seiteMeldet(true)
  assert.equal(zaehler.darfFragen(), false, 'die Seite führt den Zähler')
  const vorher = abrufe
  await new Promise((r) => setImmediate(r))
  assert.equal(abrufe, vorher, 'kein Abruf, solange die Seite meldet')
  // Gibt die Seite den Zähler zurück, fragt der App-Takt wieder.
  zaehler.seiteMeldet(false)
  assert.equal(zaehler.darfFragen(), true)
  // Und die fertige Zahl der Seite steht sofort, ohne Abruf.
  zaehler.uebernehmen(9)
  assert.equal(zaehler.ungelesen.value, 9)
  zaehler.anhalten()
})

test('CHAT-3a · MUSS 4: der App-Zähler fragt pausiert und nur im 60-s-Takt', async () => {
  const { TAKT_LANG_MS, useChatZaehler } = await import('../src/diakonos/composables/useChatZaehler.js')
  assert.equal(TAKT_LANG_MS, 60_000, 'am Handy höchstens eine Minute')
  let abrufe = 0
  const zaehler = useChatZaehler({
    aktiv: () => true,
    seiteOffen: () => true,
    handyLage: () => true,
    abfragen: () => { abrufe += 1; return Promise.resolve({ gespraeche: [] }) },
  })
  assert.equal(abrufe, 0, 'bei offener Seite fragt der App-Zähler NICHT')
  assert.equal(zaehler.darfFragen(), false)
  // Die fertige Zahl aus dem Ereignis wird übernommen (kein Abruf).
  zaehler.uebernehmen(7)
  assert.equal(zaehler.ungelesen.value, 7)
  zaehler.uebernehmen('kaputt')
  assert.equal(zaehler.ungelesen.value, 7, 'unbrauchbare Werte ändern nichts')
  assert.equal(abrufe, 0, 'weiterhin kein Abruf')
  zaehler.anhalten()
})

test('CHAT-3a · geloescht_grund (CHAT-6): „Von der Leitung entfernt“ mit Grund', () => {
  // Der Verlauf trägt bei einer Entfernung durch die Leitung `geloescht_grund`
  // — NUR dann. Eine eigene Löschung hat keinen Grund.
  const entfernt = verlaufsZeile({
    name: 'n1', text: null, geloescht: true, eigene: false,
    geloescht_grund: 'Beleidigung', erstellt_am: zeit('2026-11-18', 9),
  }, { jetzt: JETZT })
  assert.equal(entfernt.text, '', 'der Text wird NIE gezeigt')
  assert.equal(entfernt.hinweis, 'Von der Leitung entfernt: Beleidigung')
  // Ohne Grund (alte Antwort): neutrale Zeile, kein erfundenes Wort.
  const ohne = verlaufsZeile({ name: 'n2', text: null, geloescht: true, eigene: false }, { jetzt: JETZT })
  assert.equal(ohne.hinweis, 'Diese Nachricht wurde gelöscht.')
  // Eigene Löschung: eigener Satz, auch wenn ein Grund ankäme.
  const eigene = verlaufsZeile({ name: 'n3', text: null, geloescht: true, eigene: true,
    geloescht_grund: 'egal' }, { jetzt: JETZT })
  assert.equal(eigene.hinweis, 'Du hast diese Nachricht gelöscht.')
})

test('CHAT-3a · misslungener Poll: letzte gute Liste bleibt, nur ein kleiner Hinweis', () => {
  const { tpl, skript } = teile(SEITE)
  const s = ohneKommentare(skript)
  const t = ohneKommentare(tpl)
  // Der stille Abruf schreibt KEINEN großen Fehler, solange etwas da ist.
  assert.match(s, /if \(still \|\| gespraeche\.value\.length\) \{/)
  assert.match(s, /listeHinweis\.value = 'Die Liste konnte gerade nicht aktualisiert werden\.'/)
  assert.match(s, /verlaufHinweis\.value = 'Der Verlauf konnte gerade nicht aktualisiert werden\.'/)
  // Der Hinweis ist eine ruhige Zeile (`dk-chat-hinweis`), kein Alarm.
  assert.match(t, /class="dk-chat-hinweis"/)
  assert.ok(!/class="dk-chat-hinweis"[^>]*role="alert"/.test(t), 'der kleine Hinweis schreit nicht')
})

test('CHAT-3a · Polling der Seite wird beim Verlassen aufgeräumt', () => {
  const { skript } = teile(SEITE)
  const s = ohneKommentare(skript)
  assert.match(s, /const takt = taktGeber\(\{/, 'der Takt kommt aus dem Logik-Modul')
  assert.match(s, /takt\.starten\(\)/)
  assert.match(s, /takt\.anhalten\(\)/)
  // `onUnmounted` enthält BEIDES: Hash-Beobachter weg und Takt anhalten.
  const ab = s.slice(s.indexOf('onUnmounted('), s.indexOf('onUnmounted(') + 400)
  assert.match(ab, /removeEventListener\('hashchange'/)
  assert.match(ab, /takt\.anhalten\(\)/)
  // Kein eigener setInterval in der Seite (EIN Takt, eine Stelle).
  assert.ok(!/setInterval\(/.test(s), 'kein zweiter Timer neben dem Takt')
  // Nur bei sichtbarem Tab: der Takt bekommt die Sichtbarkeit.
  assert.match(s, /document\.hidden !== true/)
  assert.match(s, /visibilitychange/)
})

test('CHAT-3a · die Seite trägt keine harten Farbwerte und keine neuen Farbtöne', () => {
  for (const [name, quelle] of [['Nachrichten.vue', SEITE], ['ChatBlase.vue', BLASE], ['ChatListe.vue', LISTE]]) {
    const stil = teile(quelle).stil
    const farben = stil.match(/(^|[;{\s])(color|background|background-color|border-color|box-shadow|outline)\s*:\s*([^;]+)/g) || []
    for (const f of farben) {
      assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(f) && !/\b(rgba?|hsla?)\(/.test(f),
        `${name}: harter Farbwert: ${f.trim()}`)
    }
    // Auch die Vorlage trägt keine Inline-Farbe (keine Ausnahme für „nur hier“).
    assert.ok(!/style="[^"]*(color|background)/i.test(ohneKommentare(teile(quelle).tpl)),
      `${name}: Inline-Farbe im Markup`)
  }
})

test('CHAT-3a · Blase: eigene rechts, fremde links, Zitat, Summe statt Namen', () => {
  const { tpl } = teile(BLASE)
  const t = ohneKommentare(tpl)
  // Eigene Nachricht als Klasse (CSS dreht die Zeile) — nicht als Farbe im Markup.
  assert.match(t, /'is-ich': nachricht\.eigene/)
  assert.match(t, /is-ich' : 'is-andere/)
  // Das Zitat steht über der Blase, eine Zeile.
  assert.match(t, /nachricht\.antwort_auf && nachricht\.antwortText/)
  assert.match(t, /\{\{ nachricht\.antwortText \}\}/)
  // „bearbeitet“ als Kennzeichen (Konzept 1/S1).
  assert.match(t, /nachricht\.bearbeitet && !nachricht\.geloescht/)
  assert.match(t, />bearbeitet</)
  // Gelöschte Nachricht als Hinweiszeile — und NICHT der Text.
  assert.match(t, /v-if="nachricht\.geloescht" class="dk-chat-geloescht"/)
  assert.match(t, /\{\{ nachricht\.hinweis \}\}/)
  // CHAT-5-UI: Der Text steht im ELSE-Zweig — und nur, wenn KEINE Karte im
  // Slot steht (eine Umfrage erscheint als Karte statt der Blase).
  assert.match(t, /v-else-if="!\$slots\.karte"[\s\S]{0,80}class="dk-chat-blase"/, 'der Text steht nur im else-Zweig (ohne Karte)')
  // Lesestand kommt aus `lesestandText` (Summe, nie Namen).
  assert.match(t, /\{\{ lesestand \}\}/)
  // Reaktionen: gesetzte Zeichen + „+“; das Menü bietet das feste Set.
  assert.match(t, /v-for="r in reaktionen"/)
  assert.match(t, /v-for="z in alleZeichen"/)
  assert.match(t, /'is-meine': r\.meines/)
  // Eigene Nachricht: Bearbeiten nur innerhalb der Frist — zur ANZEIGEZEIT
  // geprüft (`bearbeitbar` der Blase), Löschen immer.
  //
  // CHAT-3a-5 (A): Am Handy stehen diese beiden NICHT mehr als eigene Knöpfe,
  // sondern im „⋯“-Menü. Die Desktop-Knöpfe sind deshalb um die Handy-Lage
  // ergänzt (`!handyLage && …`); die Handy-Fassung kommt aus `menueEintraege`
  // (dort mit denselben Bedingungen) — beides wird hier geprüft.
  assert.match(t, /v-if="!handyLage && bearbeitbar"/)
  assert.match(t, /v-if="!handyLage && nachricht\.eigene"/)
  assert.match(t, /:eintraege="menueEintraege"/, 'am Handy steht EIN „⋯“-Menü')
  // Antworten darf JEDER — auch auf die eigene Nachricht (Review R1).
  assert.ok(!/v-if="!nachricht\.eigene"[\s\S]{0,120}@click="\$emit\('antworten'/.test(t),
    'kein Ausschluss eigener Nachrichten beim Antworten')
})

test('CHAT-3a · Liste: Abschnitte, Vorschau, Zeit, Zähler, Stumm-Symbol', () => {
  const { tpl } = teile(LISTE)
  const t = ohneKommentare(tpl)
  assert.match(t, /v-for="abschnitt in gruppen"/, 'die Abschnitte kommen fertig aus dem Modul')
  assert.match(t, /\{\{ abschnitt\.label \}\}/)
  assert.match(t, /v-for="zeile in abschnitt\.eintraege"/)
  // CHAT-7a-UI-2: der Name kommt aus `nameFuer` (im 1:1 „Unbekannte Person“
  // ohne Namen), Punkt 6.
  assert.match(t, /\{\{ nameFuer\(zeile\) \}\}/)
  assert.match(t, /\{\{ zeile\.zeit \}\}/)
  assert.match(t, /v-if="zeile\.ungelesen > 0"/)
  assert.match(t, /zeile\.ungelesen > 99 \? '99\+' : zeile\.ungelesen/)
  assert.match(t, /v-if="zeile\.stumm"/, 'Stumm-Symbol je Gespräch (F3)')
  assert.match(t, /:aria-current="istAktiv\(zeile\) \? 'page' : undefined"/)
  // Ein nie geöffnetes Gespräch bleibt ein Link — auf den Bereich.
  assert.match(t, /:href="hrefFuer\(zeile\)"/)
  // Der Zähler bekommt einen Satz für die Vorlesehilfe, nicht die nackte Zahl.
  assert.match(t, /\{\{ zeile\.ungelesen \}\} ungelesen/)
})

test('CHAT-3a · ein nie geöffnetes Gespräch wird beim Öffnen angelegt', () => {
  const { skript } = teile(SEITE)
  const s = ohneKommentare(skript)
  // Die Liste kennt solche Gespräche mit `name: null` (+ Titel, Gruppe).
  assert.match(s, /apiCall\('chat\.gespraech_anlegen'/)
  assert.match(s, /gruppe: neu\.gruppe/)
  assert.match(s, /untergruppe: neu\.untergruppe \|\| undefined/)
  // Danach steht die Adresse auf der ECHTEN Kennung (ersetzt den Platzhalter).
  assert.match(s, /const zielHash = gespraechHash\(kennungNeu\)/)
  assert.match(s, /window\.location\.replace\(zielHash\)/)
  // Ein Abfrageteil (`?…`) verhindert den Adresswechsel nicht.
  assert.match(s, /String\(window\.location\.hash \|\| ''\)\.split\('\?'\)\[0\]/)
  assert.match(s, /if \(e\.name \|\| e\.geoeffnet !== false\) return false/,
    'ein nie geöffnetes Gespräch wird über seinen ORT gefunden (nicht über den Titel)')
  // CHAT-3a-3/C1 (Review Runde 2): die Adresse nennt GENAU eine Einheit —
  // eine HAUPTGRUPPE (`!e.untergruppe && e.gruppe === a`) darf die Untergruppe
  // derselben Gruppe nicht treffen (der Server sortiert ungeöffnete nach Titel
  // absteigend, „Jugend – Leiter“ stünde sonst vor „Jugend“). Verhalten:
  // `tests/chat3a3-nachrichten-nacharbeit.test.mjs`.
  assert.match(s, /if \(unter\) return unter === a \|\| `\$\{gruppe\}\/\$\{unter\}` === a/,
    'Untergruppe: nur der eigene Name (oder die Pfadform) trifft')
  assert.match(s, /return gruppe === a/,
    'Hauptgruppe: nur der Eintrag OHNE Untergruppe trifft')
  // Der Aufruf passiert VOR dem Verlad — sonst liefe er ins Leere.
  const oeffnen = s.slice(s.indexOf('async function oeffnen()'), s.indexOf('async function oeffnen()') + 2200)
  // CHAT-11b (R1/1): der Aufbau liegt in `oeffnenJetzt` (die Hülle gibt ihn als
  // Zusage heraus, damit der Sprung auf den echten Verlauf warten kann) — der
  // Ablauf ist unverändert: erst anlegen, dann laden.
  const rumpf = oeffnen.slice(oeffnen.indexOf('async function oeffnenJetzt()'))
  assert.match(rumpf, /if \(!\(await sicherstellen\(\)\)\) return/)
  assert.match(rumpf, /const daten = await verlaufLaden\(\)/)
  // Die Zeile der Liste führt über ihren ORT in den Bereich (kein toter Klick,
  // kein Titel als Adresse).
  const liste = ohneKommentare(teile(LISTE).skript)
  assert.match(liste, /gespraechHash\(zeilenAdresse\(zeile\)\)/)
})

// ══════════════════════════════════════════════════════════════════════════════
// 11 · Handy-Leiste: fünf Plätze, „Mehr“, Zähler
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-3a · Handy-Leiste: Start · Nachrichten · Gruppen · Kalender · Mehr', () => {
  // Chat-Konzept 10.1/10.2 (Manuel 17.11.): fünf Plätze, „Mehr“ öffnet die
  // bestehende Menü-Schublade. Die Regel „kein Mehr in der Leiste“ vom 03.11.
  // ist damit abgelöst — der Platz ist ausdrücklich gewollt.
  assert.deepEqual(FUSSTAB_TABS.map((t) => t.label),
    ['Start', 'Nachrichten', 'Gruppen', 'Kalender', 'Mehr'])
  assert.deepEqual(FUSSTAB_TABS.map((t) => t.href),
    ['#/', '#/nachrichten', '#/gruppen', '#/kalender', ''])
  assert.equal(FUSSTAB_TABS.length, 5, 'fünf Plätze (N5)')
  // „Mehr“ ist ein KNOPF, kein eigener Seitenbaum: keine Adresse, keine Seiten.
  const mehr = FUSSTAB_TABS.at(-1)
  assert.equal(tabArt(mehr), 'schublade')
  assert.equal(mehr.href, '')
  assert.deepEqual(mehr.seiten, [])
  assert.equal(MEHR_TEXT, 'Mehr — Menü öffnen')
  // Alle anderen bleiben echte Links.
  for (const tab of FUSSTAB_TABS.slice(0, -1)) assert.equal(tabArt(tab), 'link')
  // Gäste: weiterhin Start und Kalender — die „Nachrichten“-Seite verlangt das
  // Modul `chat` (fail closed), „Gruppen“ ist `nurMitglied`. „Mehr“ bleibt als
  // Platz stehen: es öffnet die Schublade, die für Gäste genau deren
  // Seitenleiste zeigt (kein neues Ziel, keine Sackgasse).
  assert.deepEqual(fusstabs({ istGast: true, module: ['chat'] }).map((t) => t.label),
    ['Start', 'Kalender', 'Mehr'])
})

test('CHAT-3a · GENAU EIN Leisten-Platz aktiv: bei offener Schublade nur „Mehr“', () => {
  // Review R1: „Mehr aktiv nur bei offener Schublade, dann der andere nicht“.
  // Geprüft wird die Regel über ALLE Plätze und beide Schubladen-Lagen — die
  // Markierung der Route darf die Markierung der Schublade nicht verdoppeln.
  const mehr = FUSSTAB_TABS.at(-1)
  assert.equal(istTabAktiv(mehr, { seite: 'Home' }), false)
  assert.equal(istTabAktiv(mehr, { seite: 'Home', schubladeOffen: true }), true)

  const SEITEN = ['Home', 'Nachrichten', 'GruppenBereich', 'GruppeDetail', 'Kalender',
    'KalenderVerwaltung', 'Moderation', 'Lieder', 'Profil', 'Dienste', 'Wiki']

  for (const schubladeOffen of [false, true]) {
    for (const seite of SEITEN) {
      const aktiv = FUSSTAB_TABS.filter((tab) => istTabAktiv(tab, { seite, schubladeOffen }))
      if (schubladeOffen) {
        assert.deepEqual(aktiv.map((t) => t.label), ['Mehr'],
          `Schublade offen auf ${seite} → NUR „Mehr“ ist markiert (nicht ${aktiv.map((t) => t.label).join(' + ')})`)
      } else {
        assert.ok(aktiv.length <= 1,
          `Schublade zu auf ${seite} → höchstens ein Platz markiert (${aktiv.map((t) => t.label).join(' + ')})`)
        assert.ok(!aktiv.includes(mehr), `„Mehr“ ist ohne offene Schublade nie markiert (${seite})`)
      }
    }
  }
  // Der Platz der Route ist ohne Schublade der richtige (Gegenprobe, damit die
  // Regel oben nicht alles auf „nichts aktiv“ abkürzt).
  const nachrichten = FUSSTAB_TABS.find((t) => t.href === '#/nachrichten')
  assert.equal(istTabAktiv(nachrichten, { seite: 'Nachrichten' }), true)
  assert.equal(istTabAktiv(nachrichten, { seite: 'Nachrichten', schubladeOffen: true }), false)
  assert.equal(istTabAktiv(FUSSTAB_TABS[0], { seite: 'Home' }), true)
  assert.equal(istTabAktiv(FUSSTAB_TABS[0], { seite: 'Home', schubladeOffen: true }), false)

  // Und die Komponente baut KEINE zweite Fassung der Regel: der Zeichner fragt
  // `istTabAktiv` und markiert das Ergebnis — nicht zusätzlich selbst.
  const LEISTE = ohneKommentare(teile(lies('components/AppBottomNav.vue')).skript)
  assert.match(LEISTE, /const istAktiv = \(tab\) => istTabAktiv\(tab, \{ seite: props\.seite, schubladeOffen: props\.menueOffen \}\)/)
  assert.doesNotMatch(LEISTE, /props\.menueOffen && !tab\.schublade/,
    'die Schubladen-Sonderregel steht nur in istTabAktiv, nicht nochmal hier')
})

test('CHAT-3a · Zähler am Tab „Nachrichten“ (Summe aus meine_gespraeche)', () => {
  const nachrichten = FUSSTAB_TABS.find((t) => t.href === '#/nachrichten')
  assert.equal(nachrichten.badge, 'nachrichten', 'die Badge-Quelle steht am Tab')
  assert.equal(tabZaehler(nachrichten, { nachrichten: 7 }), '7')
  assert.equal(tabZaehler(nachrichten, { nachrichten: 0 }), '')
  assert.equal(tabZaehler(nachrichten, { nachrichten: null }), '', 'noch nichts geladen → kein Zähler')
  assert.equal(tabZaehler(nachrichten, { nachrichten: 128 }), '99+', 'dreistellig wird gekappt')
  // Ein Tab ohne Badge-Quelle trägt nie einen Zähler.
  const kalender = FUSSTAB_TABS.find((t) => t.href === '#/kalender')
  assert.equal(tabZaehler(kalender, { nachrichten: 7 }), '')
})

test('CHAT-3a · „Mehr“ trägt ein echtes Drei-Punkte-Symbol (⋯), kein Zahnrad', () => {
  // Review R1: der Platz zeigt „⋯“ — drei Punkte in derselben Strichfamilie
  // wie die übrigen Symbole. Geprüft wird die GEOMETRIE: drei Punkte auf einer
  // Höhe, und sie sind als Strich lang genug, um mit runden Enden sichtbar zu
  // sein (die erste Fassung `h.01` zeichnete je nach Browser nichts).
  const pfad = ICON_PFADE.mehr
  assert.equal(typeof pfad, 'string', 'ICON_PFADE kennt `mehr`')
  const punkte = [...pfad.matchAll(/M(\d+(?:\.\d+)?) (\d+(?:\.\d+)?)h(\.?\d+(?:\.\d+)?)/g)]
  assert.equal(punkte.length, 3, 'genau drei Punkte')
  const ys = new Set(punkte.map((p) => p[2]))
  assert.equal(ys.size, 1, 'alle drei auf einer Höhe (waagerecht, kein Zahnrad)')
  assert.equal([...ys][0], '12', 'Mitte des 24er-Rasters')
  for (const p of punkte) {
    assert.ok(Number(p[3]) > 0, `Punkt ${p[1]} hat eine sichtbare Länge (h${p[3]})`)
  }
  const xs = punkte.map((p) => Number(p[1])).sort((a, b) => a - b)
  assert.deepEqual(xs, [6, 12, 18], 'gleichmäßig verteilt')
  // Und der Platz benutzt es (kein eigenes Pfad-Literal in der Leiste).
  const LEISTE = lies('components/AppBottomNav.vue')
  assert.match(LEISTE, /ICON_PFADE\[tab\.icon\]/)
  assert.equal(FUSSTAB_TABS.at(-1).icon, 'mehr')
})

test('CHAT-3a · die Leiste verdrahtet „Mehr“ mit der Schublade und den Zähler', () => {
  const LEISTE = lies('components/AppBottomNav.vue')
  const { tpl, skript } = teile(LEISTE)
  const t = ohneKommentare(tpl)
  const s = ohneKommentare(skript)
  // Der Platz „Mehr“ ist ein <button>, der das Menü öffnet (kein Blatt).
  assert.match(t, /v-if="tabArt\(tab\) === 'schublade'"/)
  assert.match(t, /@click="\$emit\('open-menu'\)"/)
  assert.match(t, /aria-haspopup="dialog"/)
  assert.match(t, /:aria-expanded="menueOffen \? 'true' : 'false'"/)
  assert.match(s, /defineEmits\(\['open-menu'\]\)/)
  // Der Zähler steht am Tab und kommt aus der EINEN Quelle (`tabZaehler`).
  assert.match(t, /v-if="zaehlerFuer\(tab\)"/)
  assert.match(s, /tabZaehler\(tab, \{ nachrichten: props\.ungelesen \}\)/)

  // App.vue gibt den Zustand und den Takt durch (eine Zahl, ein Timer).
  const app = ohneKommentare(teile(APP).tpl)
  assert.match(app, /<AppBottomNav[\s\S]{0,200}:menue-offen="menueOffen"/)
  assert.match(app, /<AppBottomNav[\s\S]{0,300}:ungelesen="nachrichtenUngelesen"/)
  assert.match(app, /<AppBottomNav[\s\S]{0,400}@open-menu="menueOeffnen"/)
  const appSkript = ohneKommentare(teile(APP).skript)
  assert.match(appSkript, /useChatZaehler\(\{/)
  assert.match(appSkript, /dk-chat-ungelesen/, 'die Seite zieht den Zähler auf Zuruf nach')
})
