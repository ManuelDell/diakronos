/**
 * CHAT-7a-UI — „Nachricht schreiben“ und Direktgespräche in der Oberfläche.
 *
 * Karte: Personenprofil bekommt den Knopf, Personensuche öffnet vorhandene
 * Gespräche direkt, die Liste zeigt 1:1 wie Gruppen (Titel, Bild, ungelesen —
 * im 1:1 „gelesen“ statt Zahl), gesperrtes Senden weicht einem ruhigen
 * Hinweis. Grundlage: `docs/konzepte/CHAT-KONZEPT.md` 10.1 Punkt 4, Karte
 * CHAT-R2c.
 *
 * Geprüft wird in DREI Stufen:
 *
 *   1. Die Regeln (`composables/nachrichtenDirekt.mjs`): Knopf-Zustand aus
 *      der Serverantwort (sichtbar/ausgegraut/fehlt), Ziel eines Treffers,
 *      „gelesen“ im 1:1, Sendesperre samt Fehlereinordnung.
 *   2. Die Bausteine am echten Quelltext (Vorlagen): die Eingabe weicht dem
 *      Hinweis, die Liste trägt „Neue Nachricht“, das Profil trägt den Knopf
 *      mit `direkt_oeffnen`.
 *   3. Das Personenprofil gemountet (SFC → ES-Modul, wie
 *      `chat3a3-nachrichten-nacharbeit.test.mjs`): Klick ruft
 *      `chat.direkt_oeffnen` per POST und stellt die Adresse auf das Gespräch.
 *
 * KEINE Rechtelogik im Frontend: alle Zusagen kommen aus der Serverantwort —
 * der Test hält genau das fest (ein falsches `darf_schreiben` erzeugt keinen
 * Knopf, ein fehlendes Feld ebenso wenig).
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat7-direkt-ui.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

import {
  KEIN_KONTO_TEXT, NEUE_NACHRICHT, NICHT_ERREICHBAR,
  NOCH_KEIN_GESPRAECH, PROFIL_KNOPF, PROFIL_NICHT_MOEGLICH, SUCHE, UNBEKANNTE_PERSON,
  beginntMit, chatAdresse, direktTitel, istDirekt, profilAdresse, profilZustand, sendbar,
  sendeFehlerZustand, sucheAdresse, verlaufUnterzeile, zeilenKontoText,
} from '../src/diakonos/composables/nachrichtenDirekt.mjs'
import {
  abschnittVon, gruppierteListe, listenZeile, lesestandText, verlaufsZeile,
} from '../src/diakonos/composables/nachrichtenLogik.mjs'
import {
  OHNE_KONTO_TEXT, personTreffer, personenAusAntwort, personenOhneGespraech, suchAbschnitte,
} from '../src/diakonos/composables/nachrichtenSuche.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

// ══════════════════════════════════════════════════════════════════════════════
// 1 · Die Regeln (ohne DOM)
// ══════════════════════════════════════════════════════════════════════════════

test('CHAT-7a · Knopf am Profil: sichtbar nur mit Zusage des Servers', () => {
  // Der Server sagt „du darfst schreiben, es gibt noch kein Gespräch“.
  const neu = profilZustand({ mitglied: 'M-1', darf_schreiben: true, hat_konto: true, gespraech: null })
  assert.equal(neu.sichtbar, true, 'die Zusage des Servers macht den Knopf sichtbar')
  assert.equal(neu.deaktiviert, false)
  assert.equal(neu.hatGespraech, false)
  assert.equal(neu.text, PROFIL_KNOPF.normal)
  assert.equal(neu.text, 'Nachricht schreiben')
  assert.equal(neu.hinweis, NOCH_KEIN_GESPRAECH, 'der erste Klick legt das Gespräch an — das steht da')

  // Es gibt schon ein 1:1 → „Zum Gespräch“ statt „neu anfangen“.
  const da = profilZustand({ mitglied: 'M-1', darf_schreiben: true, hat_konto: true, gespraech: 'CHAT-D-1' })
  assert.equal(da.sichtbar, true)
  assert.equal(da.hatGespraech, true)
  assert.equal(da.text, PROFIL_KNOPF.gespraech)
  assert.equal(da.text, 'Zum Gespräch')
  assert.equal(da.gespraech, 'CHAT-D-1', 'die Kennung des vorhandenen Gesprächs reist mit')
  assert.equal(da.hinweis, '', 'kein „leg es an“-Satz, wenn es das Gespräch schon gibt')
})

test('CHAT-7a · Knopf am Profil: ohne Konto ausgegraut, ohne Zusage gar nicht da', () => {
  // Person ohne Konto: auffindbar, Hinweis, Knopf gesperrt (Konzept Punkt 3).
  const ohneKonto = profilZustand({ darf_schreiben: false, hat_konto: false, gespraech: null })
  assert.equal(ohneKonto.sichtbar, true, 'sie bleibt sichtbar — keine Auskunftssperre')
  assert.equal(ohneKonto.deaktiviert, true, 'aber der Knopf ist ausgegraut')
  assert.equal(ohneKonto.hinweis, KEIN_KONTO_TEXT)
  assert.equal(KEIN_KONTO_TEXT, 'hat kein Konto', 'der Wortlaut steht im Konzept')

  // Der Server verweigert das Schreiben (ausgetreten, kein Recht, Gast).
  assert.equal(profilZustand({ darf_schreiben: false, hat_konto: true }).sichtbar, false,
    'ohne darf_schreiben gibt es KEINEN Knopf — keine eigene Rechtelogik im Frontend')

  // Fail closed: gar keine Antwort / fehlende Felder.
  for (const leer of [null, undefined, {}, { mitglied: 'M-1' }, { hat_konto: true }]) {
    const zustand = profilZustand(leer)
    assert.equal(zustand.sichtbar, false, `ohne Serverzusage kein Knopf (${JSON.stringify(leer)})`)
  }
  // `darf_schreiben` muss WAHR sein — „1“ oder “ja“ ist keine Zusage.
  assert.equal(profilZustand({ darf_schreiben: 'true', hat_konto: true }).sichtbar, false)
})

test('CHAT-7a · Treffer: vorhandenes Gespräch öffnet den Chat, sonst ins Profil', () => {
  // Die Zielregel lebt seit Review R1 an der EINEN Suche (`personTreffer` in
  // `nachrichtenSuche.mjs`, geprüft im Test darunter). Hier stehen die
  // Adressen, aus denen sie gebaut wird.
  assert.equal(chatAdresse('CHAT-D-1'), '#/nachrichten/CHAT-D-1')
  assert.equal(chatAdresse(''), '#/nachrichten')
  assert.equal(chatAdresse('a b'), '#/nachrichten/a%20b', 'die Kennung wird kodiert')
  assert.equal(profilAdresse('M-1'), '#/mitglied/M-1')
  // CHAT-R2d: ohne Kennung gibt es kein halbes Profil — der Weg führt in die
  // Personensuche (vorher `#/personen`, seit CHAT-R2a nur noch eine Umleitung).
  assert.equal(profilAdresse(''), '#/nachrichten/suche', 'ohne Kennung gibt es kein halbes Profil')
})

test('CHAT-7a · Liste: Direktgespräch steht mit Titel; kein „gelesen“ in der Liste', () => {
  const direkt = {
    name: 'CHAT-D-1', art: 'direkt', gruppe: null, untergruppe: null,
    titel: 'Erika Muster', mitglied: 'M-1', bild: '', teilnehmer: 2,
    stumm: false, geoeffnet: true, ungelesen: 0, letzte_nachricht: 'Bis morgen',
    letzte_am: '2026-11-18T10:00:00',
  }
  assert.equal(istDirekt(direkt), true)
  assert.equal(istDirekt({ art: 'gruppe' }), false)

  const zeile = listenZeile(direkt, new Date(2026, 10, 18, 12, 0, 0))
  assert.equal(zeile.titel, 'Erika Muster', 'der Titel ist der Name des Gegenübers')
  assert.equal(zeile.abschnitt, 'direkt', 'die Zeile gehört in den Abschnitt „Direktnachrichten“')
  assert.equal(zeile.ungelesen, 0)
  assert.equal(zeile.letzte, 'Bis morgen')

  // Die Liste trägt den Abschnitt, hinter den Gruppen.
  const gruppen = gruppierteListe([
    { ...direkt },
    { name: 'G-1', art: 'gruppe', gruppe: 'chor', titel: 'Chor', teilnehmer: 12,
      geoeffnet: true, ungelesen: 1, letzte_am: '2026-11-18T09:00:00' },
  ], new Date(2026, 10, 18, 12, 0, 0))
  assert.deepEqual(gruppen.map((g) => g.label), ['Gruppen', 'Direktnachrichten'])

  // CHAT-7a-UI-2 Punkt 1: im 1:1 steht in der Liste GAR NICHTS neben der Zeit —
  // „gelesen“ war MEIN Lesestand und gehört an die Nachricht.
  assert.equal(zeilenKontoText(direkt), '')
  assert.equal(zeilenKontoText(zuletztVerbessert(direkt)), '')
  assert.equal(zeilenKontoText({ art: 'gruppe', teilnehmer: 12 }), '12 im Gespräch')
  assert.equal(zeilenKontoText({ art: 'gruppe', teilnehmer: 0 }), '')
  function zuletztVerbessert(e) { return { ...e, ungelesen: 3 } }
})

test('CHAT-7a · Senden: nur der Server sperrt — nicht die Anzeigefelder', () => {
  const direkt = { name: 'CHAT-D-1', art: 'direkt', mitglied: 'M-1', titel: 'Erika Muster' }
  assert.equal(sendbar(direkt), true, 'im offenen 1:1 darf geschrieben werden')
  assert.equal(sendbar(direkt, { gesperrt: true }), false, 'die Server-Sperre gilt')
  // CHAT-7a-UI-2 Punkt 2: `mitglied` ist laut Backend NUR Anzeige — ein leeres
  // Feld sagt nichts über das Recht, es nimmt niemandem die Eingabe.
  assert.equal(sendbar({ ...direkt, mitglied: '' }), true,
    'ein leeres `mitglied` sperrt NICHT (keine Rechtelogik aus Anzeigefeldern)')
  // Ein Gruppen-Chat ist schreibbar, auch wenn er (noch) nicht in der Liste
  // steht — die Liste kann schlicht nicht geladen sein.
  assert.equal(sendbar({ art: 'gruppe', teilnehmer: 5 }), true, 'Gruppen bleiben schreibbar')
  assert.equal(sendbar({ name: '', art: 'gruppe' }), true)
  // CHAT-5-UI: Das Serverfeld `darf_senden` sperrt (dieselbe Aktion wie
  // „Umfrage starten“); fehlt es, bleibt es beim bisherigen „ja“.
  assert.equal(sendbar({ ...direkt, darf_senden: false }), false,
    'der Server verneint das Senden im 1:1')
  assert.equal(sendbar({ name: 'G-9', art: 'gruppe', darf_senden: false }), false)
  assert.equal(sendbar({ ...direkt, darf_senden: true }), true)
  assert.equal(sendbar({ ...direkt, darf_senden: undefined }), true, 'ohne Feld „ja“')
  assert.equal(sendbar(null), false, 'ohne Gespräch keine Eingabe')

  // 403 beim Senden heißt im 1:1 „nicht mehr erreichbar“ — NICHT „kein Zugriff“.
  const lage403 = sendeFehlerZustand({ status: 403 }, { direkt: true })
  assert.equal(lage403.gesperrt, true)
  assert.equal(lage403.titel, NICHT_ERREICHBAR.titel)
  assert.equal(NICHT_ERREICHBAR.titel, 'Diese Person ist nicht mehr erreichbar.')
  assert.match(NICHT_ERREICHBAR.text, /Verlauf/)
  // In einer Gruppe bleibt 403 der gewöhnliche Rechte-Hinweis.
  assert.equal(sendeFehlerZustand({ status: 403 }, { direkt: false }).gesperrt, false)
  // Andere Fehler sperren nicht — ein Netzfehler ist keine Auskunft über Rechte.
  const netz = sendeFehlerZustand({ message: 'Keine Verbindung' }, { direkt: true })
  assert.equal(netz.gesperrt, false)
  assert.equal(netz.titel, 'Die Nachricht ging nicht raus')
})

test('CHAT-7a · Adressen: Suche und Einstieg sind benannt', () => {
  assert.equal(SUCHE, '#/nachrichten/suche', 'die Personensuche hat ihre Adresse (Konzept 10.2)')
  assert.equal(sucheAdresse(), SUCHE)
  assert.equal(sucheAdresse('  Erika '), '#/nachrichten/suche?q=Erika')
  assert.equal(NEUE_NACHRICHT, 'Neue Nachricht')
  assert.equal(SUCHE, '#/nachrichten/suche', 'der Einstieg führt in die eine Suche')
  // Der Abschnitt „direkt“ ist eine eigene Art — Gruppen bleiben Gruppen.
  assert.equal(abschnittVon({ art: 'direkt' }), 'direkt')
  assert.equal(abschnittVon({ art: 'gruppe' }), 'gruppe')
  assert.equal(abschnittVon({ art: 'untergruppe' }), 'untergruppe')
})

// ══════════════════════════════════════════════════════════════════════════════
// 2 · Die Bausteine am Quelltext
// ══════════════════════════════════════════════════════════════════════════════

/** Template-/Skript-/Stilteil einer .vue-Datei. */
function teile(quelle) {
  const tpl = quelle.slice(quelle.indexOf('<template>'), quelle.lastIndexOf('</template>'))
  const skript = quelle.slice(quelle.indexOf('<script setup>'), quelle.indexOf('</script>'))
  const stil = quelle.slice(quelle.lastIndexOf('<style'))
  return { tpl, skript, stil }
}

test('CHAT-7a · Vorlage Nachrichten.vue: Eingabe weicht dem Hinweis, Einstieg in die Suche', () => {
  const { tpl, skript } = teile(lies('pages/Nachrichten.vue'))

  // Die gesperrte Eingabe: der Hinweis steht DA, wo die Eingabe sonst steht.
  assert.match(tpl, /v-if="!darfSenden"[\s\S]{0,200}NICHT_ERREICHBAR\.titel/,
    'bei gesperrtem Senden ersetzt der Hinweis die Eingabe')
  assert.match(tpl, /<form v-else[\s\S]{0,120}class="dk-chat-eingabe"[\s\S]{0,80}@submit\.prevent="senden"/,
    'sonst steht die gewohnte Eingabe (v-else — nie beides)')
  assert.match(tpl, /dk-chat-gesperrt-text[\s\S]{0,80}NICHT_ERREICHBAR\.text/)

  // Der Verlauf bleibt lesbar: die Sperre sitzt UNTER der Log-Region.
  const logStelle = tpl.indexOf('role="log"')
  const sperrStelle = tpl.indexOf('!darfSenden')
  assert.ok(logStelle > 0 && sperrStelle > logStelle,
    'die Sperre steht hinter dem Verlauf — nichts wird verdeckt')

  // Einstieg „Neue Nachricht“ führt in die VORHANDENE Suche (CHAT-3c) —
  // es gibt nur EINE Suche, keine zweite PersonenSuche-Komponente.
  assert.match(tpl, /NEUE_NACHRICHT/, 'der Einstieg ist benannt')
  assert.match(tpl, /:href="SUCHE"/, 'und führt in die eine Suche')
  assert.doesNotMatch(tpl, /PersonenSuche/, 'die zweite Suche (Review R1) ist weg')
  assert.match(tpl, /<ChatSuche/, 'die 3c-Suche trägt die Treffer')

  // Karte UI-2 Punkt 5: im 1:1 ist die Kopfzeile LEER (`verlaufUnterzeile`),
  // und „gelesen“ steht dort nicht mehr (Punkt 1).
  assert.match(tpl, /v-if="unterKopf"/, 'der Kopf trägt die Zeile nur, wenn es etwas zu sagen gibt')
  assert.match(skript, /verlaufUnterzeile\(\{ istDirekt: istOffenesDirekt\.value, teilnehmer: teilnehmerZahl\.value \}\)/,
    'die Unterzeile kommt aus der gemeinsamen Regel')
  assert.doesNotMatch(skript, /kontoText[^\n]*zeilenKontoText/,
    'kein „gelesen“ über `zeilenKontoText` im Verlaufskopf')
  // Punkt 1: `direkt` geht an jede Blase — sonst steht dort „gelesen von 1“.
  assert.match(tpl, /<ChatBlase[\s\S]{0,120}:direkt="istOffenesDirekt"/,
    'die Blase weiß, dass sie in einem 1:1 steht')

  // Keine eigene Rechtelogik: nur die Serveraussage.
  assert.match(skript, /sendbar\(offenesGespraech\.value, \{ gesperrt: sendenVonServerGesperrt\.value \}\)/,
    'die Sendesperre kommt aus der Serveraussage, nicht aus einer Rollenabfrage')
  assert.doesNotMatch(skript, /ist_admin|roles\.includes|module_sichtbar\.includes\('chat'\)/,
    'die Seite prüft keine Rechte selbst')
})

test('CHAT-7a · Vorlage ChatListe.vue: „Neue Nachricht“, Bild statt „1:1“-Kennzeichen', () => {
  const { tpl, skript } = teile(lies('components/chat/ChatListe.vue'))
  assert.match(tpl, /:href="SUCHE"/, 'der Einstieg führt in die Personensuche')
  assert.match(tpl, /NEUE_NACHRICHT/, 'er ist benannt')
  // CHAT-7a-UI-2 Punkt 7: kein Kennzeichen „1:1“ mehr — der Abschnitt sagt es.
  assert.doesNotMatch(tpl, /class="dk-chat-direkt"/, 'das Kennzeichen „1:1“ ist entfallen')
  assert.doesNotMatch(tpl, />1:1</, 'und sein Text auch')
  // Punkt 1: kein „gelesen“ in der Liste — nur der Zähler.
  assert.doesNotMatch(tpl, />gelesen</, 'die Liste zeigt kein „gelesen“ mehr')
  assert.match(tpl, /zeile\.ungelesen > 0/, 'der Zähler bleibt')
  // Punkt 4: das Bild des Gegenübers wie in der 3c-Suche, sonst Initialen.
  assert.match(tpl, /dk-chat-av--bild/, 'die Zeile nutzt dieselbe Bildform wie die Suche')
  assert.match(tpl, /<img :src="bildFuer\(zeile\)" alt="" \/>/, 'das Bild kommt aus `bild`')
  assert.match(skript, /from '\.\.\/\.\.\/composables\/nachrichtenDirekt\.mjs'/,
    'die Regeln kommen aus der gemeinsamen Datei')
})

test('CHAT-7a · Vorlage MitgliedDetail.vue: Knopf mit direkt_oeffnen am Profil', () => {
  const { tpl, skript } = teile(lies('pages/MitgliedDetail.vue'))
  assert.match(tpl, /profilKnopf\.sichtbar/, 'der Knopf hängt am Serverzustand')
  assert.match(tpl, /:disabled="profilKnopf\.deaktiviert"/, 'ohne Konto ist er ausgegraut')
  assert.match(tpl, /\{\{ profilKnopf\.text \}\}/, 'der Text kommt aus der Regel')
  assert.match(tpl, /profilKnopf\.hinweis/, 'der Hinweis „hat kein Konto“ steht dabei')
  assert.match(skript, /apiCall\('chat\.direkt_oeffnen', \{ mitglied: mitgliedId\.value \}\)/,
    'der Klick ruft direkt_oeffnen (POST über apiCall)')
  assert.match(skript, /apiGet\('chat\.personen_suchen'/, 'der Zustand kommt aus der Personensuche')
  assert.match(skript, /window\.location\.hash = chatAdresse\(kennung\)/,
    'danach steht die Adresse auf dem Gespräch')
  assert.doesNotMatch(skript, /chat\.gespraech_anlegen/, 'ein 1:1 wird NIE über gespraech_anlegen erzeugt')
})

test('CHAT-7a · Treffer der einen Suche: Gespräch → Chat-Link, sonst Profil-Link', () => {
  // `personTreffer` (CHAT-3c) entscheidet das Ziel — HIER kommt `gespraech` dazu
  // (Konzept 10.1 Punkt 4). Keine zweite Suche, keine zweite Zielregel.
  const mitChat = personTreffer({
    mitglied: 'M-1', anzeigename: 'Erika Muster', hat_konto: true,
    darf_schreiben: true, gespraech: 'CHAT-D-7',
  })
  assert.equal(mitChat.href, '#/nachrichten/CHAT-D-7', 'vorhandenes Gespräch öffnet den Chat')
  assert.equal(mitChat.gespraech, 'CHAT-D-7', 'die Kennung reist mit')
  assert.equal(mitChat.hatKonto, true)
  assert.equal(mitChat.darfSchreiben, true)

  const ohneChat = personTreffer({
    mitglied: 'M-1', anzeigename: 'Erika Muster', hat_konto: true,
    darf_schreiben: true, gespraech: null,
  })
  assert.equal(ohneChat.href, '#/mitglied/M-1', 'ohne Gespräch führt der Treffer ins Profil')
  assert.equal(ohneChat.gespraech, '')

  // Person ohne Konto bleibt sichtbar, aber ohne Link (wie 3c/CHAT-3c-2).
  const ohneKonto = personTreffer({
    mitglied: 'M-2', anzeigename: 'Lea', hat_konto: false, darf_schreiben: false, gespraech: 'X',
  })
  assert.equal(ohneKonto.href, '', 'ohne Konto kein Link')
  assert.equal(ohneKonto.hinweis, OHNE_KONTO_TEXT)
  assert.equal(personTreffer({ gespraech: 'X' }), null, 'ohne Mitglied kein Treffer')
})

test('CHAT-7a · ChatSuche.vue: Treffer ist ein Link, kein totes „treffer“-Ereignis', () => {
  const { tpl, skript } = teile(lies('components/chat/ChatSuche.vue'))
  // Review R1 Punkt 3: das ungenutzte `emit('treffer')` ist entfernt.
  assert.doesNotMatch(skript, /emit\('treffer'/, 'kein totes Ereignis mehr')
  // CHAT-11b: `springen` ist der Weg zu einem Nachrichtentreffer — KEIN
  // zweites Treffer-Ereignis, sondern der Sprung (die Seite lädt nach).
  assert.match(skript, /defineEmits\(\['sucht', 'springen'\]\)/,
    'die Ereignisse sind `sucht` (Adresse) und `springen` (Nachrichtentreffer)')
  assert.doesNotMatch(tpl, /@click="beiTrefferKlick"/, 'kein Klick-Abfangen — der Link springt')
  assert.match(tpl, /<a class="dk-chat-zeile dk-chat-treffer"/, 'die Trefferzeile ist ein <a>')
  // Die 3c-Regel liefert das Ziel (Profil oder Chat) — eine Stelle.
  assert.match(skript, /personTreffer|nachrichtenSuche/, 'die Regeln kommen aus `nachrichtenSuche`')
})

// ══════════════════════════════════════════════════════════════════════════════
// 3 · Das Personenprofil gemountet — der Klick wirklich ausgeführt
// ══════════════════════════════════════════════════════════════════════════════

// ── Browser-Attrappe ───────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/#/mitglied/M-1',
})
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'history']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))

const Vue = await import('vue')
const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat7a-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

/**
 * Ein Baum SFCs/Module ab `seite` übersetzen. `umleitung` biegt Module auf
 * Attrappen um (API, Router, Session …) — die Attrappen liegen in `TMP`.
 */
function baum(seite, { ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = new Map()
  /** Ziel-Datei → Quell-Datei (die Ersetzung läuft über den QUELLTEXT). */
  const quellen = new Map()
  const zielFuer = (quellDatei) => {
    const relativ = quellDatei.slice(SRC_ROOT.pathname.length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    quellen.set(ziel, quellDatei)
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
    // Bereits übersetzte Ziele werden auf ihre QUELLE zurückgeführt — sonst
    // löst eine Kette (A → B → C) ihre relativen Importe im TEMP-Ordner auf.
    const ursprung = quellen.get(abs) || abs
    const quellDatei = aufgeloest(ursprung)
    let code
    if (quellDatei.endsWith('.vue')) {
      const filename = basename(quellDatei)
      const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
      assert.deepEqual(errors, [], filename + ': SFC-Struktur')
      const script = compileScript(descriptor, { id: filename })
      const tpl = compileTemplate({
        source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      })
      assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
      let scode = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      code = scode + '\n' + tpl.code.replace(/^export function render/m, 'function render')
      code += '\n__sfc__.render = render\nexport default __sfc__\n'
    } else {
      code = readFileSync(quellDatei, 'utf8')
    }
    code = code.replace(
      /from\s+['"]([^'"]+)['"]/g,
      (ganz, spec) => {
        if (spec === 'vue') return `from '${VUE_URL}'`
        if (spec.startsWith('.')) {
          const basis = quellen.get(quellDatei) || quellDatei
          // Ein Import in einem Kommentar („import … from './x.js'“ in einer
          // Erklärung) ist KEIN Import — er lässt sich nicht auflösen und
          // bleibt stehen. Sonst bricht der ganze Baum an einer Doku-Zeile.
          let zielAbs
          try {
            zielAbs = aufgeloest(resolve(dirname(basis), spec))
          } catch {
            return ganz
          }
          const url = pathToFileURL(zielAbs).href
          if (umleitung.has(url)) return `from '${umleitung.get(url)}'`
          return `from '${pathToFileURL(uebersetzen(zielAbs)).href}'`
        }
        if (spec.startsWith('node:')) return ganz
        // Ein Fremdpaket (z. B. `qrcode-generator`) aus dem TEMP-Ordner heraus
        // lässt sich über den Paketnamen nicht auflösen — die Auflösung läuft
        // vom ECHTEN Quellort aus.
        try {
          return `from '${import.meta.resolve(spec)}'`
        } catch {
          return ganz
        }
      },
    )
    const ziel = zielFuer(quellDatei)
    writeFileSync(ziel, code)
    NEU.set(abs, ziel)
    NEU.set(quellDatei, ziel)
    return ziel
  }
  return uebersetzen(new URL(seite, SRC).pathname)
}

const umleitung = new Map()
const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 12) => { for (let i = 0; i < n; i += 1) await tick() }

/** Ein Bauteil in einem jsdom-Element mounten; `abbaum` räumt auf. */
async function mounten(komponente, props = {}) {
  const host = dom.window.document.createElement('div')
  dom.window.document.body.appendChild(host)
  const app = Vue.createApp({ render: () => Vue.h(komponente, props) })
  const fehler = []
  app.config.errorHandler = (e) => fehler.push(e)
  app.mount(host)
  const abbaum = () => { try { app.unmount() } catch { /* egal */ } host.remove() }
  return { host, abbaum, fehler }
}

/** Die Karten-Attrappen: alles, was das Profil außer der Chat-Karte braucht. */
function profilAttrappen(ordner, { server, mitglied }) {
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  const api = join(ordner, 'api.mjs')
  const aufrufe = []
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH({ art: "POST", methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH({ art: "GET", methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const router = join(ordner, 'router.mjs')
  writeFileSync(router, [
    'export const getRouteParam = (name) => globalThis.__PARAM || ""',
    'export const getRouteParams = () => globalThis.__PARAMS || {}',
    'export const currentHash = () => globalThis.__HASH || ""',
    'export const currentPageName = () => globalThis.__PAGE || "MitgliedDetail"',
    'export const currentComponent = () => null',
    'export const navigate = (ziel) => { globalThis.__NAV = ziel }',
    'export const onBeforeEach = () => () => {}',
    'export const routeNeuLaden = () => {}',
    'export const seitenLadend = { value: false }',
    'export const pageLadefehler = { value: null }',
    'export const verwaltungsStufeSeite = () => null',
    'export const verwaltungErlaubt = () => true',
    'export const modulChatErlaubt = () => true',
    'export const BOOT = {}',
    'export default { getRouteParam }',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('router.js'), pathToFileURL(router).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)
  globalThis.__PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__SERVER = server
  globalThis.__PARAM = 'M-1'
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/mitglied/M-1'
  return { aufrufe, mitglied }
}

/** Die Detailantwort des Servers für die Person (nur, was die Seite braucht). */
function detailAntwort(überschreiben = {}) {
  return {
    data: {
      name: 'M-1', vorname: 'Erika', nachname: 'Muster', status: 'Aktiv',
      email: 'erika@example.org', telefon: '', geburtstag: '', geschlecht: 'w',
      familienstand: '', strasse: '', hausnummer: '', plz: '', ort: '',
      gruppen: [], beziehungen: [], austritt: null, dsgvo: {},
      ...überschreiben,
    },
    permissions: { beziehungen_pflegen: false, beziehungen_alle: false },
  }
}

test('CHAT-7a · Profil: Klick ruft direkt_oeffnen per POST und öffnet das Gespräch', async () => {
  const ordner = join(TMP, 'profil-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const server = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'get_mitglied_detail') return detailAntwort()
    if (kurz === 'personen_suchen') {
      return {
        treffer: [{
          mitglied: 'M-1', anzeigename: 'Erika Muster', bild: '', hat_konto: true,
          darf_schreiben: true, gespraech: null,
        }],
        limit: 20,
      }
    }
    if (kurz === 'direkt_oeffnen') {
      return { name: 'CHAT-D-7', art: 'direkt', gruppe: null, untergruppe: null,
        titel: 'Erika Muster', mitglied: 'M-1', bild: '', teilnehmer: 2, stumm: false,
        geoeffnet: true, ungelesen: 0 }
    }
    return {}
  }
  const { aufrufe } = profilAttrappen(ordner, { server })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const { host, abbaum, fehler } = await mounten(mod.default, {})
  await warte(20)

  assert.deepEqual(fehler, [], 'das Profil baut ohne Fehler auf')
  const text = () => host.textContent || ''
  assert.match(text(), /Nachricht schreiben/, 'der Knopf steht am Profil')
  assert.match(text(), new RegExp(NOCH_KEIN_GESPRAECH.slice(0, 24).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
    'und nennt den nächsten Schritt')

  // Der Suchaufruf ging mit dem Namen der Person raus (GET — rein lesend).
  const suche = aufrufe.find((a) => /personen_suchen$/.test(a.methode))
  assert.ok(suche, 'die Personensuche wurde gefragt')
  assert.equal(suche.art, 'GET', 'die Suche ist rein lesend (GET)')
  assert.equal(suche.parameter.q, 'Erika Muster', 'gesucht wird mit dem Namen der Person')

  // Klick auf den Knopf.
  const knopf = [...host.querySelectorAll('button')]
    .find((b) => (b.textContent || '').includes('Nachricht schreiben'))
  assert.ok(knopf, 'der Knopf ist ein echter <button>')
  knopf.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(20)

  const oeffnen = aufrufe.filter((a) => /direkt_oeffnen$/.test(a.methode))
  assert.equal(oeffnen.length, 1, 'genau EIN Aufruf — kein doppeltes Anlegen')
  assert.equal(oeffnen[0].art, 'POST', 'direkt_oeffnen ist ein POST')
  assert.deepEqual(oeffnen[0].parameter, { mitglied: 'M-1' })
  // Die Adresse zeigt danach auf das Gespräch — dort wird es geöffnet.
  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-D-7',
    'der Weg führt in „Nachrichten“, das Gespräch ist offen')
  abbaum()
})

test('CHAT-7a · Profil: Person ohne Konto — Knopf ausgegraut, Klick tut nichts', async () => {
  const ordner = join(TMP, 'kein-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const server = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'get_mitglied_detail') return detailAntwort()
    if (kurz === 'personen_suchen') {
      return {
        treffer: [{
          mitglied: 'M-1', anzeigename: 'Erika Muster', bild: '', hat_konto: false,
          darf_schreiben: false, gespraech: null,
        }],
        limit: 20,
      }
    }
    return {}
  }
  const { aufrufe } = profilAttrappen(ordner, { server })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const { host, abbaum, fehler } = await mounten(mod.default, {})
  await warte(20)
  assert.deepEqual(fehler, [])

  const text = host.textContent || ''
  assert.match(text, /hat kein Konto/, 'der Hinweis steht da (Konzept Punkt 3)')
  const knopf = [...host.querySelectorAll('button')]
    .find((b) => (b.textContent || '').includes('Nachricht schreiben'))
  assert.ok(knopf, 'der Knopf ist sichtbar — die Person ist auffindbar')
  assert.equal(knopf.disabled, true, 'aber ausgegraut')

  knopf.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(10)
  assert.equal(aufrufe.filter((a) => /direkt_oeffnen$/.test(a.methode)).length, 0,
    'ein gesperrter Knopf schickt keinen Aufruf')
  assert.equal(dom.window.location.hash, '#/mitglied/M-1', 'und die Adresse bleibt am Profil')
  abbaum()
})

test('CHAT-7a · Profil: ohne Zusage des Servers gibt es keinen Knopf', async () => {
  const ordner = join(TMP, 'ohne-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const server = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'get_mitglied_detail') return detailAntwort()
    // Person nicht in der Suche (ausgetreten, kein Recht) — leere Liste.
    if (kurz === 'personen_suchen') return { treffer: [], limit: 20 }
    return {}
  }
  profilAttrappen(ordner, { server })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const { host, abbaum } = await mounten(mod.default, {})
  await warte(20)
  const text = host.textContent || ''
  assert.doesNotMatch(text, /Nachricht schreiben/, 'kein Knopf ohne Serverzusage')
  assert.doesNotMatch(text, /hat kein Konto/, 'und kein irreführender Hinweis')
  abbaum()
})

test('CHAT-7a · Profil: vorhandenes Gespräch zeigt „Zum Gespräch"', async () => {
  const ordner = join(TMP, 'da-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const server = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'get_mitglied_detail') return detailAntwort()
    if (kurz === 'personen_suchen') {
      return {
        treffer: [{
          mitglied: 'M-1', anzeigename: 'Erika Muster', bild: '', hat_konto: true,
          darf_schreiben: true, gespraech: 'CHAT-D-1',
        }],
        limit: 20,
      }
    }
    if (kurz === 'direkt_oeffnen') {
      return { name: 'CHAT-D-1', art: 'direkt', titel: 'Erika Muster', mitglied: 'M-1', ungelesen: 0 }
    }
    return {}
  }
  const { aufrufe } = profilAttrappen(ordner, { server })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const { host, abbaum } = await mounten(mod.default, {})
  await warte(20)

  assert.match(host.textContent || '', /Zum Gespräch/, 'die Zeile heißt „Zum Gespräch“')
  const knopf = [...host.querySelectorAll('button')]
    .find((b) => (b.textContent || '').includes('Zum Gespräch'))
  assert.ok(knopf)
  knopf.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(20)
  // Auch beim vorhandenen Gespräch läuft `direkt_oeffnen` (idempotent im
  // Server) und die Adresse steht danach auf DEMSELBEN Gespräch.
  assert.equal(aufrufe.filter((a) => /direkt_oeffnen$/.test(a.methode)).length, 1)
  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-D-1')
  abbaum()
})

// ══════════════════════════════════════════════════════════════════════════════
// 4 · CHAT-7a-UI-2 — die Nachbesserung nach dem Review
// ══════════════════════════════════════════════════════════════════════════════

test('UI-2/MUSS 1: „gelesen“ steht an der EIGENEN Nachricht — im 1:1 ohne „von“', () => {
  // Der Lesestand einer Nachricht: eigener Beitrag, das Gegenüber hat gelesen.
  const eigene = verlaufsZeile({
    name: 'N-1', text: 'Hallo', autor: 'Ich', eigene: true,
    erstellt_am: '2026-11-18T10:00:00', gelesen_von: 1,
  }, { ich: 'M-0', jetzt: new Date(2026, 10, 18, 12, 0, 0) })
  assert.equal(eigene.gelesen_von, 1, 'die Summe kommt an der eigenen Nachricht an')
  // 1:1: EIN Wort, keine Zahl („gelesen von 1“ wäre die Gruppenform).
  assert.equal(lesestandText(eigene, { direkt: true }), 'gelesen')
  assert.equal(lesestandText(eigene), 'gelesen von 1', 'in der Gruppe bleibt die Summe')
  // Ungelesen (0) → GAR NICHTS, auch im 1:1.
  assert.equal(lesestandText({ ...eigene, gelesen_von: 0 }, { direkt: true }), '')
  assert.equal(lesestandText({ ...eigene, gelesen_von: 0 }), '')
  // Fremde Nachricht trägt keinen Lesestand — auch nicht im 1:1.
  const fremd = verlaufsZeile({
    name: 'N-2', text: 'Hi', autor: 'Erika', eigene: false,
    erstellt_am: '2026-11-18T10:01:00', gelesen_von: 1,
  }, { ich: 'M-0', jetzt: new Date(2026, 10, 18, 12, 0, 0) })
  assert.equal(fremd.gelesen_von, null)
  assert.equal(lesestandText(fremd, { direkt: true }), '')

  // Die Blase reicht `direkt` durch (sonst stünde im 1:1 „gelesen von 1“).
  const { tpl, skript } = teile(lies('components/chat/ChatBlase.vue'))
  assert.match(skript, /direkt: \{ type: Boolean, default: false \}/, 'die Blase kennt die 1:1-Lage')
  assert.match(skript, /lesestandText\(props\.nachricht, \{ direkt: props\.direkt === true \}\)/,
    'und gibt sie an die EINE Regel weiter')
  assert.doesNotMatch(tpl, /✓✓ \{\{ lesestand \}\} [^<]*gelesen von/, 'keine zweite Formulierung in der Vorlage')

  // Liste und Verlaufskopf zeigen ihn NICHT (das ist MEIN Stand, nicht seiner).
  assert.equal(zeilenKontoText({ art: 'direkt', teilnehmer: 2 }), '', 'die Liste schweigt')
  assert.equal(verlaufUnterzeile({ istDirekt: true, teilnehmer: 2 }), '', 'der Kopf auch')
  const liste = teile(lies('components/chat/ChatListe.vue'))
  assert.doesNotMatch(liste.tpl, />gelesen</, 'kein „gelesen“ in der Liste')
  const seite = teile(lies('pages/Nachrichten.vue'))
  assert.doesNotMatch(seite.tpl, />gelesen</, 'kein „gelesen“ im Verlaufskopf')
})

test('UI-2/MUSS 2: sendbar folgt NUR der Server-Antwort (403)', () => {
  // Ein 1:1 mit leerem `mitglied` ist sendbar: das Feld ist nur Anzeige.
  assert.equal(sendbar({ name: 'C', art: 'direkt', mitglied: '' }), true)
  assert.equal(sendbar({ name: 'C', art: 'direkt', mitglied: null }), true)
  // Ein Gruppen-Chat ohne Eintrag in der Liste ebenso (die Liste lud nicht).
  assert.equal(sendbar({ name: 'C', art: 'gruppe', teilnehmer: 0 }), true)
  // Die EINE Sperre ist die 403-Antwort des Servers.
  assert.equal(sendbar({ name: 'C', art: 'direkt' }, { gesperrt: true }), false)
  assert.equal(sendbar({ name: 'C', art: 'gruppe' }, { gesperrt: true }), false)
  // CHAT-5-UI: Dazu das Serverfeld `darf_senden` (dieselbe Aktion wie
  // „Umfrage starten“). Es ist eine Serverantwort, keine Ableitung.
  assert.equal(sendbar({ name: 'C', art: 'gruppe', darf_senden: false }), false,
    'der Server verneint das Senden')
  assert.equal(sendbar({ name: 'C', art: 'gruppe', darf_senden: true }), true)
  // Fehlt das Feld (alter Server), bleibt es beim bisherigen „ja“.
  assert.equal(sendbar({ name: 'C', art: 'gruppe' }), true, 'ohne Feld darf gesendet werden')
  // 403 im 1:1 → „Diese Person ist nicht mehr erreichbar.“
  const eins = sendeFehlerZustand({ status: 403 }, { direkt: true })
  assert.equal(eins.gesperrt, true)
  assert.equal(eins.titel, 'Diese Person ist nicht mehr erreichbar.')
  // 403 in der Gruppe → der bestehende Fehlertext, keine Sperre.
  const gruppe = sendeFehlerZustand({ status: 403 }, { direkt: false })
  assert.equal(gruppe.gesperrt, false)
  assert.equal(gruppe.titel, 'Die Nachricht ging nicht raus')

  // Die Seite leitet die Sperre NICHT aus Feldern ab.
  const { skript } = teile(lies('pages/Nachrichten.vue'))
  assert.doesNotMatch(skript, /sendbar\([^)]*mitglied/, 'die Sendesperre liest `mitglied` nicht')
  assert.match(skript, /sendeFehlerZustand\(fehler, \{ direkt: istOffenesDirekt\.value \}\)/,
    'die 403-Einordnung kennt die 1:1-Lage')
  assert.match(skript, /sendenVonServerGesperrt\.value = true/, 'gesperrt wird erst nach der Antwort')
})

test('UI-2/MUSS 3: Profil — 403 lässt die Karte mit Hinweis stehen', () => {
  // Der Server hat abgelehnt (kein Konto, ausgetreten, kein Recht).
  const verweigert = profilZustand({ mitglied: 'M-1', darf_schreiben: true, hat_konto: true }, { verweigert: true })
  assert.equal(verweigert.sichtbar, true, 'die Karte bleibt stehen — sonst verschwände der Hinweis')
  assert.equal(verweigert.deaktiviert, true, 'der Knopf ist ausgegraut')
  assert.equal(verweigert.hinweis, PROFIL_NICHT_MOEGLICH)
  assert.equal(PROFIL_NICHT_MOEGLICH, 'Für diese Person ist keine Nachricht möglich.')
  // Auch ohne Treffer (die Suche schwieg) — die Verweigerung ist eine Antwort.
  assert.equal(profilZustand(null, { verweigert: true }).sichtbar, true)
  // Mit vorhandenem Gespräch bleibt die Zeile „Zum Gespräch“, nur gesperrt.
  const da = profilZustand({ darf_schreiben: true, hat_konto: true, gespraech: 'C-1' }, { verweigert: true })
  assert.equal(da.text, PROFIL_KNOPF.gespraech)
  assert.equal(da.deaktiviert, true)
  // OHNE Verweigerung gilt weiter die Serverzusage (fail closed).
  assert.equal(profilZustand({ darf_schreiben: false, hat_konto: true }).sichtbar, false)

  const { tpl, skript } = teile(lies('pages/MitgliedDetail.vue'))
  assert.match(skript, /profilZustand\(chatTreffer\.value, \{ verweigert: chatVerweigert\.value \}\)/,
    'die Verweigerung ist eine eigene Lage, kein nachgezogenes `darf_schreiben`')
  assert.doesNotMatch(skript, /darf_schreiben: false/, 'die Zusage wird NICHT auf false gesetzt')
  assert.match(skript, /chatFehler\.value = PROFIL_NICHT_MOEGLICH/)
  assert.match(tpl, /:disabled="profilKnopf\.deaktiviert"/, 'der Knopf bleibt sichtbar, aber gesperrt')
})

test('UI-2/SOLL 5+6: Unterzeile im 1:1 leer, ohne Titel „Unbekannte Person“', () => {
  assert.equal(verlaufUnterzeile({ istDirekt: true, teilnehmer: 2 }), '')
  assert.equal(verlaufUnterzeile({ istDirekt: false, teilnehmer: 7 }), '7 im Gespräch')
  assert.equal(verlaufUnterzeile({ istDirekt: false, teilnehmer: 0 }), '')
  assert.equal(UNBEKANNTE_PERSON, 'Unbekannte Person')
  assert.equal(direktTitel({ titel: '' }), UNBEKANNTE_PERSON)
  assert.equal(direktTitel({ titel: '  ' }), UNBEKANNTE_PERSON)
  assert.equal(direktTitel({ titel: 'Erika M.' }), 'Erika M.')
  // Auch die Liste: ein 1:1 aus dem Altbestand ohne Namen.
  const zeile = listenZeile({ name: 'C-9', art: 'direkt', titel: '', letzte_am: null })
  assert.equal(zeile.titel, UNBEKANNTE_PERSON)
  // Eine Gruppe ohne Namen bleibt ohne erfundenen Namen.
  assert.equal(listenZeile({ name: 'G-1', art: 'gruppe', gruppe: '', titel: '' }).titel, '')

  // Der Seitenkopf: im 1:1 LEER (Review R1, SOLL 2) — kein Satz über „wer
  // liest mit“, kein Gruppen-Text.
  const { skript } = teile(lies('pages/Nachrichten.vue'))
  assert.match(skript, /if \(istOffenesDirekt\.value\) return ''/,
    'der Seitenkopf lässt die Unterzeile im 1:1 leer')
  assert.doesNotMatch(skript, /niemand sonst liest mit/,
    'der Satz über die Meldestelle steht nicht mehr da')
  assert.match(skript, /if \(istDirekt\(eintrag\)\) return direktTitel\(eintrag\)/,
    'der Titel eines 1:1 kommt aus der 1:1-Regel (ohne Namen „Unbekannte Person“)')
})

test('UI-2/SOLL 7: Abschnitt heißt „Direktnachrichten“ (wie die Glocke)', () => {
  assert.equal(abschnittVon({ art: 'direkt' }), 'direkt')
  assert.deepEqual(
    gruppierteListe([
      { name: 'G-1', art: 'gruppe', gruppe: 'chor', titel: 'Chor', teilnehmer: 3, letzte_am: '2026-11-18T09:00:00' },
      { name: 'D-1', art: 'direkt', titel: 'Erika M.', letzte_am: '2026-11-18T10:00:00' },
    ], new Date(2026, 10, 18, 12, 0, 0)).map((a) => a.label),
    ['Gruppen', 'Direktnachrichten'],
  )
})

test('UI-2/SOLL 8: eine Person, deren 1:1 schon dasteht, wird nicht doppelt gelistet', () => {
  // Der Server liefert die Person UND die Liste trägt ihr 1:1 (Titel = Name).
  // Verglichen wird über die KENNUNG (`gespraech` ↔ `name`), nicht über den
  // Namen (Review R1, MUSS 1).
  const personen = personenAusAntwort({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel', hat_konto: true, darf_schreiben: true, gespraech: 'C-1' },
    { mitglied: 'M-2', anzeigename: 'Bert Brandner', hat_konto: true, darf_schreiben: true },
  ] })
  const treffer = [{
    id: 'direkt',
    label: 'Direktnachrichten',
    eintraege: [{ name: 'C-1', art: 'direkt', titel: 'Anna Beispiel', letzte_am: '2026-11-18T10:00:00' }],
  }]
  const uebrig = personenOhneGespraech(personen, treffer)
  assert.deepEqual(uebrig.map((p) => p.mitglied), ['M-2'], 'Anna steht schon unter „Gespräche“')

  // Ein Gruppen-Chat mit demselben Namen blendet niemanden aus (kein 1:1).
  const gruppe = [{ id: 'gruppe', label: 'Gruppen',
    eintraege: [{ name: 'G-1', art: 'gruppe', titel: 'Anna Beispiel' }] }]
  assert.equal(personenOhneGespraech(personen, gruppe).length, 2)

  // Ohne Gesprächstreffer bleibt alles stehen.
  assert.equal(personenOhneGespraech(personen, []).length, 2)

  // Und die Abschnittsregel zählt mit der gefilterten Liste: bleibt nichts
  // übrig, steht weder „Personen“ noch ein zweiter Leertext da.
  const nurAnna = personenAusAntwort({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel', hat_konto: true, darf_schreiben: true, gespraech: 'C-1' },
  ] })
  const lage = suchAbschnitte({ gespraeche: treffer, zustand: 'treffer', personen: nurAnna })
  assert.equal(lage.personen, false, 'keine leere „Personen“-Überschrift')
  assert.equal(lage.personenZeilen.length, 0)
  assert.equal(lage.leer, false, 'es gibt ja einen Gesprächstreffer')
  // Bleibt kein Gesprächstreffer übrig, wird auch niemand ausgeblendet — die
  // Personentreffer stehen dann wieder für sich (`personenOhneGespraech` prüft
  // nur gegen tatsächlich gezeigte 1:1-Zeilen, nicht gegen solche, die erst
  // durch den Begriff weggefallen sind).
  const ohneGespraech = suchAbschnitte({ gespraeche: [], zustand: 'treffer', personen: nurAnna })
  assert.equal(ohneGespraech.personen, true, 'ohne Gesprächstreffer bleibt die Person sichtbar')
  assert.equal(ohneGespraech.personenZeilen.length, 1)
  // Der EINE Leertext gehört zu „nichts gefunden“ — hier gab es einen Treffer.
  assert.equal(ohneGespraech.leer, false)
})

test('UI-2/Review R1 MUSS 1: verglichen wird die Kennung, nicht der Namensanfang', () => {
  // Gesprächstreffer „Anna Schmidt“ (C-1). Daneben:
  //  * „Anna Schmidt-Berger“ — ANDERE Person, ohne Gespräch → bleibt.
  //  * „Anna Schmidt“ — gleichnamige Person mit anderem Mitglied, ohne
  //    Gespräch → bleibt ebenfalls (der alte Namensvergleich warf sie weg).
  //  * die Person mit gespraech 'C-1' → fällt weg.
  const personen = personenAusAntwort({ treffer: [
    { mitglied: 'M-1', anzeigename: 'Anna Schmidt', hat_konto: true, darf_schreiben: true, gespraech: 'C-1' },
    { mitglied: 'M-2', anzeigename: 'Anna Schmidt-Berger', hat_konto: true, darf_schreiben: true },
    { mitglied: 'M-3', anzeigename: 'Anna Schmidt', hat_konto: true, darf_schreiben: true },
  ] })
  const treffer = [{
    id: 'direkt',
    label: 'Direktnachrichten',
    eintraege: [{ name: 'C-1', art: 'direkt', titel: 'Anna Schmidt', letzte_am: '2026-11-18T10:00:00' }],
  }]
  const uebrig = personenOhneGespraech(personen, treffer)
  assert.deepEqual(uebrig.map((p) => p.mitglied), ['M-2', 'M-3'],
    'nur die Person mit DIESEM Gespräch fällt weg')
  // Eine Gruppe, deren Kennung zufällig als text irgendwo steht, blendet aus —
  // aber nur die Kennung zählt: dieselbe Kennung als Nicht-1:1 nicht.
  assert.equal(personenOhneGespraech(personen, [{ eintraege: [{ name: 'C-1', art: 'gruppe' }] }]).length, 3)
  assert.equal(beginntMit('mueller', 'mue'), true)
  assert.equal(beginntMit('ann', 'anna'), false)
})

// ══════════════════════════════════════════════════════════════════════════════
// 5 · gemountet — die Nachbesserung wirklich ausgeführt
// ══════════════════════════════════════════════════════════════════════════════

test('UI-2/MUSS 1: Blase im 1:1 zeigt „gelesen“, in der Gruppe „gelesen von 1“', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue')).href)).default
  const nachricht = {
    ident: 'N-1', id: 'N-1', text: 'Hallo', autor: 'Ich', eigene: true,
    zeit: '10:00', erstellt_am: '2026-11-18T10:00:00', gelesen_von: 1,
    geloescht: false, reaktionen: [], antwort_auf: null, bearbeitbar: false,
  }
  const direkt = await mounten(mod, { nachricht, direkt: true })
  await warte(4)
  assert.match(direkt.host.textContent, /gelesen/, 'im 1:1 steht der Lesestand')
  assert.doesNotMatch(direkt.host.textContent, /gelesen von/, 'ohne „von N“')
  direkt.abbaum()

  const gruppe = await mounten(mod, { nachricht, direkt: false })
  await warte(4)
  assert.match(gruppe.host.textContent, /gelesen von 1/, 'in der Gruppe bleibt die Summe')
  gruppe.abbaum()

  const ungelesen = await mounten(mod, { nachricht: { ...nachricht, gelesen_von: 0 }, direkt: true })
  await warte(4)
  assert.doesNotMatch(ungelesen.host.textContent, /gelesen/, 'ungelesen → kein „gelesen“')
  ungelesen.abbaum()
})

test('UI-2/Punkt 4+6+7: Liste zeigt Bild, Initialen und kein „1:1“', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatListe.vue')).href)).default
  const mitBild = {
    name: 'C-1', art: 'direkt', gruppe: null, untergruppe: null, titel: 'Erika M.',
    bild: '/files/erika.jpg', mitglied: 'M-1', teilnehmer: 2, stumm: false,
    geoeffnet: true, ungelesen: 0, letzte: 'Bis morgen', letzte_am: '2026-11-18T10:00:00',
    zeit: '10:00', abschnitt: 'direkt',
  }
  const ohneBild = {
    name: 'C-2', art: 'direkt', gruppe: null, untergruppe: null, titel: '',
    bild: '', mitglied: 'M-2', teilnehmer: 2, stumm: false, geoeffnet: true,
    ungelesen: 0, letzte: '', letzte_am: null, zeit: '', abschnitt: 'direkt',
  }
  const s = await mounten(mod, {
    gruppen: [{ id: 'direkt', label: 'Direktnachrichten', eintraege: [mitBild, ohneBild] }],
  })
  await warte(4)
  const text = s.host.textContent
  const bilder = [...s.host.querySelectorAll('img')]
  assert.equal(bilder.length, 1, 'genau EIN Bild (das 1:1 mit `bild`)')
  assert.equal(bilder[0].getAttribute('src'), '/files/erika.jpg')
  assert.ok(bilder[0].closest('.dk-chat-av--bild'), 'in derselben Bildform wie die Suche')
  assert.match(text, /Erika M\./, 'der Name steht da')
  assert.match(text, /Unbekannte Person/, 'ohne Namen „Unbekannte Person“ (Punkt 6)')
  assert.doesNotMatch(text, /1:1/, 'kein Kennzeichen „1:1“ (Punkt 7)')
  assert.doesNotMatch(text, /gelesen/, 'kein „gelesen“ (Punkt 1)')
  assert.match(text, /Direktnachrichten/, 'der Abschnitt heißt „Direktnachrichten“')
  s.abbaum()
})

test('UI-2/MUSS 3: Profil nach 403 — Knopf bleibt, ausgegraut, Hinweis sichtbar', async () => {
  const ordner = join(TMP, 'verboten-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const verboten = Object.assign(new Error('Kein Zugriff'), { status: 403 })
  const server = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'get_mitglied_detail') return detailAntwort()
    if (kurz === 'personen_suchen') {
      return {
        treffer: [{
          mitglied: 'M-1', anzeigename: 'Erika Muster', bild: '', hat_konto: true,
          darf_schreiben: true, gespraech: null,
        }],
        limit: 20,
      }
    }
    if (kurz === 'direkt_oeffnen') throw verboten
    return {}
  }
  const { aufrufe } = profilAttrappen(ordner, { server })
  const mod = await import(pathToFileURL(baum('pages/MitgliedDetail.vue', { ordner })).href)
  const { host, abbaum, fehler } = await mounten(mod.default, {})
  await warte(20)

  const knopf = [...host.querySelectorAll('button')]
    .find((b) => (b.textContent || '').includes('Nachricht schreiben'))
  assert.ok(knopf, 'der Knopf steht vor dem Klick da')
  knopf.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(20)
  assert.deepEqual(fehler, [])

  const text = host.textContent || ''
  assert.equal(aufrufe.filter((a) => /direkt_oeffnen$/.test(a.methode)).length, 1, 'genau EIN Versuch')
  assert.match(text, /Für diese Person ist keine Nachricht möglich\./,
    'der Hinweis steht da — die Karte ist NICHT verschwunden')
  const danach = [...host.querySelectorAll('button')]
    .find((b) => (b.textContent || '').includes('Nachricht schreiben'))
  assert.ok(danach, 'der Knopf bleibt sichtbar')
  assert.equal(danach.disabled, true, 'und ist ausgegraut')
  assert.equal(dom.window.location.hash, '#/mitglied/M-1', 'die Adresse bleibt am Profil')

  // Ein zweiter Klick schickt nichts mehr.
  danach.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(10)
  assert.equal(aufrufe.filter((a) => /direkt_oeffnen$/.test(a.methode)).length, 1)
  abbaum()
})

test('UI-2/MUSS 2: Gruppen-Chat bleibt schreibbar, wenn die Liste scheitert', async () => {
  const s = await seiteFuerChat({ hash: '#/nachrichten/CHAT-1', listeFehler: true })
  await warte(24)
  const eingabe = s.host.querySelector('textarea#chat-eingabe')
  assert.ok(eingabe, 'die Eingabe steht da — kein „nicht erreichbar“ ohne Serverantwort')
  assert.doesNotMatch(s.host.textContent, /nicht mehr erreichbar/)
  s.abbaum()
})

test('UI-2/MUSS 2: 403 beim Senden im 1:1 → Hinweis; in der Gruppe → Fehlertext', async () => {
  // 1:1: der Server verweigert das Senden.
  const eins = await seiteFuerChat({ hash: '#/nachrichten/CHAT-D-1', sendenFehler: 403 })
  await warte(24)
  const feld = eins.host.querySelector('textarea#chat-eingabe')
  assert.ok(feld, 'vor dem Senden ist die Eingabe offen')
  feld.value = 'Hallo'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(6)
  const formular = eins.host.querySelector('form.dk-chat-eingabe')
  assert.ok(formular, 'das Formular steht da')
  formular.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(16)
  const text = eins.host.textContent || ''
  assert.match(text, /Diese Person ist nicht mehr erreichbar\./, 'der ruhige Hinweis ersetzt die Eingabe')
  assert.equal(eins.host.querySelector('textarea#chat-eingabe'), null, 'die Eingabe ist weg')
  eins.abbaum()

  // Gruppe: derselbe 403 ist ein gewöhnlicher Fehler — die Eingabe bleibt.
  const gruppe = await seiteFuerChat({ hash: '#/nachrichten/CHAT-1', sendenFehler: 403 })
  await warte(24)
  const feld2 = gruppe.host.querySelector('textarea#chat-eingabe')
  feld2.value = 'Hallo'
  feld2.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(6)
  gruppe.host.querySelector('form.dk-chat-eingabe')
    .dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(16)
  assert.doesNotMatch(gruppe.host.textContent || '', /nicht mehr erreichbar/,
    'in der Gruppe gibt es kein „Gegenüber“ — also diesen Satz nicht')
  assert.ok(gruppe.host.querySelector('textarea#chat-eingabe'), 'die Eingabe bleibt stehen')
  gruppe.abbaum()
})

test('UI-2/SOLL 5: im 1:1 steht keine Teilnehmer- oder Gruppenzahl im Kopf', async () => {
  const s = await seiteFuerChat({ hash: '#/nachrichten/CHAT-D-1' })
  await warte(24)
  const kopf = s.host.querySelector('.dk-chat-verlauf-titel')
  assert.ok(kopf, 'der Kopf steht da')
  assert.doesNotMatch(kopf.textContent, /im Gespräch/, 'kein „N im Gespräch“ im 1:1')
  assert.doesNotMatch(kopf.textContent, /gelesen/, 'und kein „gelesen“')
  assert.equal(s.host.querySelector('.dk-chat-verlauf-unter'), null,
    'die Zeile steht gar nicht da (kein leerer Absatz)')
  s.abbaum()
})

test('UI-2/Review R1 SOLL 3: Platzhalter — kein Stumm-Knopf, keine Unterzeile im Verlaufskopf', async () => {
  // Die Liste scheitert, das Gespräch ist trotzdem offen: der Eintrag ist ein
  // PLATZHALTER (`platzhalter: true`). Ob stumm geschaltet ist, weiß niemand;
  // eine Teilnehmerzahl gibt es nicht.
  const s = await seiteFuerChat({ hash: '#/nachrichten/CHAT-D-1', listeFehler: true })
  await warte(24)
  const text = s.host.textContent || ''
  assert.doesNotMatch(text, /stumm/i, 'kein Stumm-Knopf beim Platzhalter')
  assert.equal(s.host.querySelector('.dk-chat-verlauf-unter'), null,
    'keine Unterzeile im Verlaufskopf')
  assert.doesNotMatch(text, /im Gespräch/, 'kein Gruppen-Text beim ersten Laden')
  // Die Skriptseite trägt die Kennzeichnung selbst.
  const { skript } = teile(lies('pages/Nachrichten.vue'))
  assert.match(skript, /platzhalter: true/, 'der Platzhalter ist als solcher markiert')
  assert.match(skript, /!istPlatzhalter/, 'Stumm-Knopf und Unterzeile hängen daran')
  s.abbaum()
})

test('UI-2/Review R1 SOLL 4: der Profil-Hinweis nach 403 wird angesagt (role="status")', () => {
  const { tpl } = teile(lies('pages/MitgliedDetail.vue'))
  assert.match(tpl, /class="md-chat-hinweis" role="status"/,
    'der Hinweis steht als Status da, nicht nur als Text')
})

/**
 * Die SEITE „Nachrichten“ mit Attrappen gemountet (CHAT-7a-UI-2).
 *
 * `listeFehler` lässt `chat.meine_gespraeche` scheitern (die Liste fehlt, das
 * Gespräch ist trotzdem offen), `sendenFehler` lässt `chat.senden` mit diesem
 * HTTP-Stand antworten.
 */
async function seiteFuerChat({ hash = '#/nachrichten', listeFehler = false, sendenFehler = 0 } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__SEITE_PUSH({ art: "POST", methode, parameter })',
    '  return globalThis.__SEITE_SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const gespraeche = [
    { name: 'CHAT-1', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
      teilnehmer: 9, geoeffnet: true, ungelesen: 0, stumm: false,
      letzte_nachricht: 'Moin', letzte_am: '2026-11-18T09:00:00' },
    { name: 'CHAT-D-1', art: 'direkt', gruppe: null, untergruppe: null, titel: 'Erika Muster',
      mitglied: 'M-1', bild: '/files/erika.jpg', teilnehmer: 2, geoeffnet: true,
      ungelesen: 0, stumm: false, letzte_nachricht: 'Bis morgen', letzte_am: '2026-11-18T10:00:00' },
  ]
  const verlauf = { richtung: 'neueste', nachrichten: [
    { name: 'N-1', gespraech: 'CHAT-D-1', text: 'Bis morgen', autor: 'M-0',
      eigene: true, erstellt_am: '2026-11-18T10:00:00', gelesen_von: 1 },
  ] }
  const verboten = Object.assign(new Error('Kein Zugriff'), { status: 403 })
  /**
   * CHAT-7a-UI-2: Wenn die Liste scheitert, liefert der Server KEINE Zeile —
   * dann muss die Seite den Eintrag des offenen Gesprächs selbst herleiten
   * (Ortesschlüssel im Titel), sonst stünde eine Gruppe ohne Eingabe da. Das
   * ist keine Rechtelogik: `sendbar` fragt nur, ob es einen Eintrag gibt.
   */
  const lage = String(hash || '').replace(/^#\/nachrichten\/?/, '')
  const ohneListe = () => gespraeche.filter((e) => String(e.name) === lage)
  const seite = ohneListe().length ? ohneListe() : [{
    name: lage, art: 'gruppe', gruppe: lage, untergruppe: null, titel: lage,
    teilnehmer: 0, geoeffnet: true, ungelesen: 0, stumm: false,
  }]
  /**
   * CHAT-7a-UI-2: Die Liste liest den Server hier aus EINER Quelle; ob sie
   * (scheinbar) scheitert, entscheidet nur der Absender (`listeFehler`).
   */
  globalThis.__SEITE_SCHEITERT = listeFehler === true
  globalThis.__SEITE_PUSH = () => {}
  globalThis.__SEITE_SERVER = async ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') {
      if (globalThis.__SEITE_SCHEITERT) {
        throw Object.assign(new Error('Die Liste ist gerade nicht da.'), { status: 500 })
      }
      return { gespraeche: seite }
    }
    if (kurz === 'verlauf') return verlauf
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'senden') {
      if (sendenFehler) throw Object.assign(new Error('Kein Zugriff'), { status: sendenFehler })
      return { ...verlauf.nachrichten[0], name: 'N-2' }
    }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash
  const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { ordner, frisch: true })).href)).default
  return mounten(mod, {})
}
