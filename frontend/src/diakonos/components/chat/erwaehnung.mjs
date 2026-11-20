/**
 * erwaehnung — „@Name“ im Chat schreiben, senden und anzeigen (CHAT-9b).
 *
 * Grundlage: Konzept `docs/konzepte/CHAT-KONZEPT.md`, S4 („Erwähnungen“). Der
 * Server (CHAT-9a) parst KEINEN Text: die zu erwähnenden Personen kommen als
 * AUSDRÜCKLICHE Liste von MITGLIED-Kennungen mit `chat.senden` (`erwaehnt`),
 * höchstens `ERWAEHNUNGEN_MAX` zählen. Jede Nachrichtenzeile trägt die
 * gespeicherte Liste als `erwaehnt: [{mitglied, anzeigename}]` — schon
 * serverseitig auf Sichtbarkeit gefiltert (hier wird NICHT nachgefiltert).
 *
 * Diese Datei ist DOM-frei (Node-Tests ohne Browser): sie kennt die Auswahl
 * hinter dem „@“, die Bereinigung vor dem Senden und die Stücke, in die eine
 * Blase ihren Text zerlegt, damit „@Name“ hervorgehoben werden kann — ohne
 * `v-html` und ohne HTML aus Nutzertext.
 *
 * WARUM DIE KENNUNG AM TEXT HÄNGT (und nicht an einem Zustand)
 * Wer „@Anna“ tippt und den Namen danach wieder löscht oder verändert, hat
 * niemanden mehr erwähnt. Deshalb wird beim SENDEN neu entschieden: geschickt
 * wird nur, wessen „@Anzeigename“ dann noch im Text steht (`auswahlBereinigen`).
 * Gemerkt wird je Zeile, WELCHE Kennung hinter dem eingesetzten Namen stand —
 * `merker` ist eine Liste von `{mitglied, anzeigename}`.
 *
 * WO DIE BETEILIGTEN HERKOMMEN (Operator-Entscheidung R1)
 * Für ALLE Gesprächsarten aus EINER Abfrage: `chat.gespraech_mitglieder`
 * (GET) → `{art, mitglieder: [{mitglied, anzeigename}], mehr?}`. Der Server
 * liefert den VOLLEN Namen (dieselbe Quelle wie `erwaehnt[].anzeigename`) und
 * lässt die lesende Person weg. Deshalb gibt es hier KEINE zweite Namensquelle
 * (kein `titel` aus `meine_gespraeche`, keine Runden-Mitglieder): zwei Quellen
 * hießen zwei Schreibweisen, und der Name im Text müsste den Namen im Server
 * treffen. `{mitglied, anzeigename}` ist die einzige Form, die diese Datei
 * kennt — die Herkunft entscheidet die Seite.
 */

import { suchNormal } from '../../composables/bf1Anzeige.js'

/** So viele Erwähnungen zählt der Server höchstens (gleiche Zahl wie im Backend). */
export const ERWAEHNUNGEN_MAX = 20

/** Zeichen, hinter denen ein „@“ ein WORTANFANG ist. */
const WORTANFANG = /[\s([{„"'›«/,;:!?–—-]/

/** Zeichen, die einen Namen im Text beenden (danach steht kein Name mehr). */
const NAMENSENDE = /[\s.,;:!?)\]}<>„"'«»›\/\\–—@]/

/**
 * Was steht unmittelbar vor dem „@“ an Position `pos`?
 *
 * Wortanfang heißt: Textanfang oder ein Trennzeichen. „E-Mail an@example“ ist
 * damit KEIN Beginn einer Erwähnung (und ein Wort wie „Test@Anna“ auch nicht).
 */
export function istWortanfang(text, pos) {
  const t = String(text ?? '')
  const p = Number(pos)
  if (!Number.isInteger(p) || p < 0 || p > t.length) return false
  if (p === 0) return true
  return WORTANFANG.test(t[p - 1])
}

/**
 * Der offene Auswahlzustand hinter dem „@“ — oder `null`.
 *
 * `text` ist der GANZE Text der Eingabe, `pos` die Stelle des Cursors (hinter
 * dem zuletzt Getippten). Gesucht wird das LETZTE „@“ vor dem Cursor, das am
 * Wortanfang steht und zwischen sich und dem Cursor keine Leerzeile/Zeilenhöhe
 * hat (ein Name enthält keine Leerzeichen — der Anzeigename wird beim Einsetzen
 * zusammengehalten).
 *
 * Rückgabe: `{ start, ende, begriff }` — `start` zeigt auf das „@“, `ende` auf
 * das Ende des getippten Fragments (gleich `pos`), `begriff` ist das Getippte
 * ohne „@“ (leer direkt nach dem „@“).
 */
export function offeneErwaehnung(text, pos) {
  const t = String(text ?? '')
  const p = Number.isInteger(Number(pos)) ? Number(pos) : t.length
  const vorne = t.slice(0, Math.max(0, Math.min(p, t.length)))
  const at = vorne.lastIndexOf('@')
  if (at < 0) return null
  if (!istWortanfang(vorne, at)) return null
  const begriff = vorne.slice(at + 1)
  // Ein Name ist EIN Wort: Leerzeichen oder Umbruch beenden die Auswahl.
  if (/[\s\r\n]/.test(begriff)) return null
  return { start: at, ende: at + 1 + begriff.length, begriff }
}

/**
 * Die Vorschläge zur Auswahl: Beteiligte des Gesprächs, gefiltert nach dem
 * Getippten, OHNE die eigene Person.
 *
 * `beteiligte` ist die Serverform `[{mitglied, anzeigename}]`. Verglichen wird
 * umlaut-/groß-klein-unabhängig über `suchNormal` (dieselbe Normalisierung wie
 * die Mitgliedersuche) und an JEDEM Wortanfang des Namens: „b“ trifft
 * „Bert Brandner“ und „Anna B.“ gleichermaßen.
 */
export function vorschlaege(beteiligte, begriff, { ich = '' } = {}) {
  const eigen = String(ich || '').trim()
  const nadel = suchNormal(String(begriff ?? '').trim())
  const liste = Array.isArray(beteiligte) ? beteiligte : []
  const gesehen = new Set()
  const treffer = []
  for (const eintrag of liste) {
    const mitglied = String(eintrag?.mitglied || '').trim()
    const name = String(eintrag?.anzeigename || '').trim()
    if (!mitglied || !name) continue
    if (eigen && mitglied === eigen) continue // nie mich selbst anbieten
    if (gesehen.has(mitglied)) continue
    if (nadel && !trifftWortanfang(name, nadel)) continue
    gesehen.add(mitglied)
    treffer.push({ mitglied, anzeigename: name })
  }
  return treffer
}

/**
 * R1/1: Trifft der (normalisierte) Begriff den Namen an einem WORTANFANG?
 *
 * Dieselbe Regel wie der Server (CHAT-9c-2): Vorname, Nachname oder der ganze
 * Name beginnt mit `q` — gefaltet wie `suchNormal` („b“ trifft „Bert
 * Brandner“ und „Anna B.“, „an“ NICHT „Bert Brandner“). Ein Zeichen genügt.
 *
 * Das ist die LOKALE Vorwegnahme derselben Suche: sie filtert zwischen zwei
 * Antworten (kein Flackern) und ist für die gemerkte Antwort dasselbe Ergebnis
 * wie der Server. Ein Teilwort-Treffer mitten im Namen („brand“ → „Bert
 * Brandner“) ist bewusst NICHT dabei — der Server liefert ihn nicht, und die
 * Liste darf nicht mehr zeigen, als der Server zu dieser Frage gesagt hat.
 */
export function trifftWortanfang(name, nadel) {
  const begriff = String(nadel ?? '')
  if (!begriff) return true
  const gefaltet = suchNormal(name)
  if (gefaltet.startsWith(begriff)) return true
  return gefaltet.split(/\s+/).some((wort) => wort.startsWith(begriff))
}

/**
 * Eine Auswahl einsetzen: „@Anzeigename “ an die Stelle des offenen „@…“.
 *
 * Der Anzeigename wird von Leerraum befreit (Folgen aus Leerzeichen/Tabs/
 * Umbrüchen werden zu EINEM Leerzeichen, außen wird getrimmt) und behält sonst
 * seine Zeichen — Text bleibt Text. CHAT-9b-2: „muss EIN Wort bleiben“ war
 * falsch — ein Name wie „Anna Müller“ bleibt „Anna Müller“ und steht im Text
 * mit Leerzeichen; nur MEHRFACHER Leerraum wird zusammengefasst. Was zählt,
 * ist die Wiederfindbarkeit: `offeneErwaehnung` beendet die Auswahl am
 * Leerzeichen, `auswahlBereinigen`/`hervorheben` finden „@Anna Müller“
 * dennoch, weil sie den eingesetzten Namen als Ganzes suchen.
 * Rückgabe: `{ text, pos, merker }` — `pos` ist die
 * Cursorstelle hinter dem eingesetzten Leerzeichen, `merker` die neue Liste
 * mit diesem Eintrag (ein bereits gemerkter Eintrag wird nicht verdoppelt).
 */
export function einsetzen(text, stelle, eintrag, merker = []) {
  const t = String(text ?? '')
  const start = Math.max(0, Number(stelle?.start) || 0)
  const ende = Math.max(start, Number(stelle?.ende) || start)
  const kennung = String(eintrag?.mitglied || '').trim()
  const name = String(eintrag?.anzeigename || '').replace(/\s+/g, ' ').trim()
  const liste = Array.isArray(merker) ? merker.slice() : []
  if (!kennung || !name) return { text: t, pos: ende, merker: liste }
  const stueck = `@${name} `
  const neu = t.slice(0, start) + stueck + t.slice(ende)
  // R1/6: Wird derselbe ANZEIGENAME erneut gesetzt, ersetzt er den alten
  // Eintrag, statt einen zweiten mit anderer Kennung daneben zu legen — sonst
  // schickte das Senden beim zweiten Tippen an jemanden, den der Text nicht
  // mehr nennt (und die Liste wüchse bei jedem Versuch). Die STELLE im Merker
  // bleibt dabei erhalten (die Reihenfolge ist die Auswahlreihenfolge).
  const gleich = (m) => {
    const alt = String(m?.anzeigename || '').replace(/\s+/g, ' ').trim()
    return alt !== '' && alt === name
  }
  const stelleImMerker = liste.findIndex((m) => String(m?.mitglied || '') === kennung || gleich(m))
  const neuEintrag = { mitglied: kennung, anzeigename: name }
  if (stelleImMerker >= 0) liste.splice(stelleImMerker, 1, neuEintrag)
  else liste.push(neuEintrag)
  return { text: neu, pos: start + stueck.length, merker: liste }
}

/**
 * Was beim SENDEN übrig bleibt: nur Kennungen, deren „@Anzeigename“ noch im
 * Text steht — höchstens `ERWAEHNUNGEN_MAX`, in der Reihenfolge des Merkers.
 *
 * R1/6: Verbraucht wird der LÄNGSTE Name zuerst — dieselbe Reihenfolge wie in
 * `hervorheben`. Sonst „verbrauchte“ „@Anna“ die Stelle von „@Anna Müller“:
 * stand die längere Person einmal da, galt die kürzere als erwähnt, obwohl ihr
 * Name im Text nicht mehr vorkommt. Jede Textstelle zählt EINMAL (wer sie
 * belegt hat, nimmt sie den anderen weg).
 */
export function auswahlBereinigen(text, merker = [], { ich = '' } = {}) {
  const t = String(text ?? '')
  const eigen = String(ich || '').trim()
  const liste = (Array.isArray(merker) ? merker : [])
    .map((e) => ({
      mitglied: String(e?.mitglied || '').trim(),
      anzeigename: String(e?.anzeigename || '').replace(/\s+/g, ' ').trim(),
    }))
    .filter((e) => e.mitglied && e.anzeigename && !(eigen && e.mitglied === eigen))
  // Reihenfolge des Merkers bleibt die Ausgabereihenfolge; geprüft wird nach
  // Länge (längster zuerst), verbucht wird über die Position in `liste`.
  const reihenfolge = liste
    .map((e, i) => i)
    .sort((a, b) => liste[b].anzeigename.length - liste[a].anzeigename.length)
  const belegt = new Set()
  const trifft = new Set()
  for (const i of reihenfolge) {
    const name = liste[i].anzeigename
    const start = freieStelle(t, name, belegt)
    if (start < 0) continue
    for (let k = start; k < start + 1 + name.length; k += 1) belegt.add(k)
    trifft.add(i)
  }
  const kennungen = []
  for (let i = 0; i < liste.length; i += 1) {
    if (!trifft.has(i)) continue
    if (kennungen.includes(liste[i].mitglied)) continue
    kennungen.push(liste[i].mitglied)
    if (kennungen.length >= ERWAEHNUNGEN_MAX) break
  }
  return kennungen
}

/**
 * Die erste noch freie Fundstelle von „@Name“ (Wortanfang vorn, Namensende
 * hinten) — oder `-1`. `belegt` sind die Textstellen, die ein längerer Name
 * schon für sich beansprucht hat.
 */
function freieStelle(text, name, belegt) {
  const muster = `@${name}`
  let ab = 0
  for (;;) {
    const i = text.indexOf(muster, ab)
    if (i < 0) return -1
    const danach = text[i + muster.length]
    let kollision = false
    for (let k = i; k < i + muster.length; k += 1) {
      if (belegt.has(k)) { kollision = true; break }
    }
    if (!kollision && (danach === undefined || NAMENSENDE.test(danach)) && istWortanfang(text, i)) return i
    ab = i + 1
  }
}

/**
 * Die Stücke, in die eine Blase ihren Text zerlegt:
 * `[{ text, erwaehnung: true|false, meine: true|false }]`.
 *
 * Hervorgehoben wird NUR, was zu einem Eintrag in `erwaehnt` passt — ein
 * „@irgendwas“ ohne Server-Eintrag bleibt gewöhnlicher Text. `meine` markiert
 * die Erwähnung der LESENDEN Person (Grundlage der dezenten Markierung der
 * ganzen Blase). Die Stücke sind reiner Text; die Blase setzt sie mit `{{ }}`
 * ins DOM (`v-html` wäre hier ein XSS-Weg, sobald ein Anzeigename „<b>“ trägt).
 *
 * Sortiert wird nach LÄNGE des Namens (längster zuerst): sonst zerschneidet
 * „@Anna“ die Erwähnung „@Annalena“.
 */
export function hervorheben(text, erwaehnt, { ich = '' } = {}) {
  const t = String(text ?? '')
  const eigen = String(ich || '').trim()
  const liste = (Array.isArray(erwaehnt) ? erwaehnt : [])
    .map((e) => ({
      mitglied: String(e?.mitglied || '').trim(),
      anzeigename: String(e?.anzeigename || '').replace(/\s+/g, ' ').trim(),
    }))
    .filter((e) => e.anzeigename)
    .sort((a, b) => b.anzeigename.length - a.anzeigename.length)
  if (!t || !liste.length) return t ? [{ text: t, erwaehnung: false, meine: false }] : []
  const stuecke = []
  let i = 0
  let puffer = ''
  const puffern = (stueck) => { puffer += stueck }
  const leeren = () => {
    if (puffer) stuecke.push({ text: puffer, erwaehnung: false, meine: false })
    puffer = ''
  }
  while (i < t.length) {
    const treffer = t[i] === '@'
      ? liste.find((e) => passtAn(t, i, e.anzeigename))
      : null
    if (!treffer) {
      puffern(t[i])
      i += 1
      continue
    }
    leeren()
    const roh = t.slice(i + 1, i + 1 + treffer.anzeigename.length)
    stuecke.push({
      text: `@${roh}`,
      erwaehnung: true,
      meine: Boolean(eigen) && treffer.mitglied === eigen,
    })
    i += 1 + roh.length
  }
  leeren()
  return stuecke
}

/** Passt die Erwähnung `name` an die Stelle `i` („@“) des Textes? */
function passtAn(text, i, name) {
  if (text.slice(i + 1, i + 1 + name.length) !== name) return false
  if (!istWortanfang(text, i)) return false
  const danach = text[i + 1 + name.length]
  return danach === undefined || NAMENSENDE.test(danach)
}

/**
 * Ist die LESENDE Person in dieser Nachricht erwähnt? (dezente Markierung der
 * Blase). Ohne eigene Kennung: nein — nie raten.
 */
export function binErwaehnt(nachricht, { ich = '' } = {}) {
  const eigen = String(ich || '').trim()
  if (!eigen) return false
  const liste = Array.isArray(nachricht?.erwaehnt) ? nachricht.erwaehnt : []
  return liste.some((e) => String(e?.mitglied || '').trim() === eigen)
}

/**
 * Die Namen der Erwähnten für den Vorlesetext („erwähnt: Anna Beispiel, Bert B.“).
 * Leer, wenn niemand erwähnt ist — dann gibt es auch nichts anzusagen.
 */
export function erwaehnteNamen(erwaehnt) {
  const liste = Array.isArray(erwaehnt) ? erwaehnt : []
  return liste
    .map((e) => String(e?.anzeigename || '').trim())
    .filter(Boolean)
}

/** Die Taste im Auswahlfeld: wohin bewegt sie die Auswahl? (DOM-frei) */
export function auswahlTaste({ key, schift = false, offen = false, anzahl = 0, aktiv = 0 } = {}) {
  if (!offen || anzahl <= 0) return 'sonst'
  if (key === 'ArrowDown') return 'weiter'
  if (key === 'ArrowUp') return 'zurueck'
  if (key === 'Enter') return 'waehlen'
  if (key === 'Escape') return 'schliessen'
  if (key === 'Tab' && !schift) return 'waehlen'
  return 'sonst'
}

/**
 * R1/3: Läuft gerade eine Eingabemethode (IME)?
 *
 * Beim Tippen mit einem IME (chinesisch, japanisch, koreanisch …) ist `Enter`
 * die Bestätigung der Zeichenauswahl und `Escape` ihr Abbruch — beides darf
 * NICHT die Erwähnungs-Liste bedienen. `keyCode === 229` ist der Rückfall für
 * Browser, die `isComposing` beim `keydown` noch nicht setzen.
 */
export function istEingabemethode(ereignis) {
  if (!ereignis || typeof ereignis !== 'object') return false
  return ereignis.isComposing === true || Number(ereignis.keyCode) === 229
}

/**
 * R1/1: Tasten, die NUR die Auswahl bedienen — ein `keyup` danach darf die
 * Liste nicht wieder öffnen. Escape schließt, ↑/↓/Enter/Tab wählen; alle vier
 * ändern den Text nicht, `offeneErwaehnung` fände danach aber wieder ein „@“
 * und die Liste spränge auf.
 */
export function nurAuswahlTaste(taste) {
  return taste === 'Escape' || taste === 'ArrowUp' || taste === 'ArrowDown'
    || taste === 'Enter' || taste === 'Tab'
}

/** Die nächste Auswahlstelle (`umlaufend` zwischen 0 und `anzahl - 1`). */
export function naechsteStelle(aktiv, schritt, anzahl) {
  const n = Number(anzahl) || 0
  if (n <= 0) return 0
  return ((Number(aktiv) || 0) + Number(schritt) + n) % n
}

/** Die Optionskennung der Auswahlliste (EINE Stelle für `aria-activedescendant`). */
export function optionKennung(basis, i) {
  return `${basis || 'dk-erwaehnung'}-${i}`
}

// ── CHAT-9b-2: fragen statt Vollliste ──────────────────────────────────────

/**
 * So viele Personen fragt die Auswahl je Namensanfang (`limit`, Karte).
 * Dieselbe Zahl wie im Backend (CHAT-9c-2); `mehr: true` sagt, dass es
 * weitere gäbe.
 */
export const ERWAEHNUNG_ANZAHL = 20

/**
 * Wartezeit nach dem letzten Tastendruck, bevor der Server gefragt wird
 * (Karte: „entprellt ~200 ms“). Der Entpreller ist der BESTEHENDE aus
 * `composables/nachrichtenSuche.mjs` (`entpreller`) — hier steht nur die Zahl.
 */
export const ERWAEHNUNG_ENTPRELLUNG_MS = 200

/** Höchstens so lang darf `q` werden (Karte: „bis 40 Zeichen“). */
export const ERWAEHNUNG_Q_MAX = 40

/**
 * Der Text hinter dem „@“ als Frage an den Server: getrimmt und auf
 * `ERWAEHNUNG_Q_MAX` gekürzt. Leer heißt leer — der Server liefert dann die
 * ersten `limit` („@“ allein).
 */
export function erwaehnungFrage(begriff) {
  return String(begriff ?? '').trim().slice(0, ERWAEHNUNG_Q_MAX)
}

/**
 * Der Schlüssel, unter dem die Antwort zu `(gespraech, q)` gemerkt wird.
 *
 * Verglichen wird FALT-GLEICH (`suchNormal`, dieselbe Normalisierung wie die
 * Suche): „Anna“ und „anna“ sind dieselbe Frage — sonst fragte jeder
 * Groß-/Kleinschreibwechsel erneut, und die gemerkte Antwort läge unter einem
 * Schlüssel, den niemand mehr sucht. `NUL` trennt die beiden Teile, weil es in
 * keiner Kennung und keinem Namen vorkommt.
 *
 * WICHTIG: Im Schlüssel steht die REGEL für „dieselbe Frage“; GEFRAGT wird der
 * Text so, wie er hinter dem „@“ steht (`erwaehnungFrage`, nur getrimmt und
 * gekürzt). Der Server sucht selbst umlaut-/groß-klein-unabhängig.
 */
export function erwaehnungSchluessel(gespraech, begriff) {
  return `${String(gespraech ?? '').trim()}\u0000${suchNormal(erwaehnungFrage(begriff))}`
}

/** Zerlegt einen Schlüssel wieder — nur für die Abfrage. */
export function erwaehnungSchluesselTeile(schluessel) {
  const text = String(schluessel ?? '')
  const i = text.indexOf('\u0000')
  if (i < 0) return { gespraech: '', q: '' }
  return { gespraech: text.slice(0, i), q: text.slice(i + 1) }
}

/**
 * Die Antwort des Servers lesen: `{art, mitglieder: [{mitglied, anzeigename}],
 * mehr}` (GET `chat.gespraech_mitglieder`, CHAT-9c-2).
 *
 * Was NICHT passt, fällt still weg (kein Rat, kein erfundener Name); die
 * eigene Person wird nie angeboten (der Server lässt sie schon weg — diese
 * Prüfung ist der Gürtel zum Hosenträger). `mehr` ist NUR `true`, wenn der
 * Server es ausdrücklich sagt.
 */
export function erwaehnungAntwort(antwort, { ich = '' } = {}) {
  const eigen = String(ich || '').trim()
  const roh = Array.isArray(antwort?.mitglieder) ? antwort.mitglieder : []
  const gesehen = new Set()
  const mitglieder = []
  for (const eintrag of roh) {
    const mitglied = String(eintrag?.mitglied || '').trim()
    const name = String(eintrag?.anzeigename || '').trim()
    if (!mitglied || !name) continue
    if (eigen && mitglied === eigen) continue
    if (gesehen.has(mitglied)) continue
    gesehen.add(mitglied)
    mitglieder.push({ mitglied, anzeigename: name })
  }
  return { mitglieder, mehr: antwort?.mehr === true }
}

/**
 * Gilt diese Antwort noch? Nur die Antwort zum AKTUELLEN `q` zählt (Karte:
 * „veraltete Antworten verwerfen“). Verglichen wird der Schlüssel — also
 * dieselbe falt-gleiche Frage, nach der gefragt wurde.
 */
export function istAktuelleFrage(gefragtSchluessel, standSchluessel) {
  return Boolean(standSchluessel) && String(gefragtSchluessel) === String(standSchluessel)
}

/**
 * R1/2: Welche Antwort zeigt die Auswahl, solange die neue noch läuft?
 *
 * `gefragt` ist der Schlüssel des AKTUELLEN Namensanfangs, `zuletzt` der des
 * zuletzt BEANTWORTETEN (beide `erwaehnungSchluessel`). Die Antwort zum
 * aktuellen `q` gewinnt; fehlt sie noch, bleibt die zuletzt beantwortete
 * desselben Gesprächs stehen und wird lokal auf den neuen Begriff gefiltert —
 * sonst ginge die Liste bei jedem Tastendruck zu und gleich wieder auf.
 *
 * `null` heißt: es gibt hier nichts zu zeigen (noch nie geantwortet, anderes
 * Gespräch, oder die Antwort zum aktuellen `q` war leer — dann gilt sie und
 * niemand kommt mit dem alten Stand zurück).
 */
export function antwortSchluessel(gefragt, zuletzt, antworten) {
  const gefragtText = String(gefragt ?? '')
  if (!gefragtText) return null
  const gemerkt = antworten && typeof antworten === 'object' ? antworten : {}
  if (gemerkt[gefragtText]) return gefragtText
  const alt = String(zuletzt ?? '')
  if (!alt || !gemerkt[alt]) return null
  const hier = erwaehnungSchluesselTeile(gefragtText).gespraech
  return erwaehnungSchluesselTeile(alt).gespraech === hier ? alt : null
}

/**
 * Wie viele Zeilen hat die Auswahl? Die Vorschläge — der „mehr“-Hinweis zählt
 * NICHT mit: er ist keine Wahl (steht außerhalb der Listbox, R1/3), also
 * trifft ↑/↓/Enter/Tab ihn nie.
 */
export function auswahlAnzahl(treffer) {
  const liste = Array.isArray(treffer) ? treffer : []
  return liste.length
}
