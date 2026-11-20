/**
 * CHAT-7b-UI — die Regeln der RUNDEN in „Nachrichten“, ohne DOM und ohne Vue.
 *
 * Grundlage: `docs/konzepte/CHAT-KONZEPT.md` S3 („Runden — 3–8 benannte
 * Beteiligte, Hinzufügen nur mit Zustimmung der Runde“), Karte CHAT-7b-UI-a.
 * Die Entscheidungen (wer darf, wer stimmt ab, was ist offen) trifft
 * AUSSCHLIESSLICH der Server (`rechte.darf_runde_anlegen` /
 * `darf_runde_erweitern`, `chat.py`). Hier wird nur gezeichnet, was er
 * zugesagt hat — und was aus seiner Antwort folgt:
 *
 *   * der Zustand des Dialogs „Neue Runde“ (`rundeAnlegenZustand`: Name,
 *     2–7 andere, Anlegen-Knopf erst bei gültiger Auswahl),
 *   * die Auswahlzeile je Suchtreffer (`rundenKandidat`: wählbar NUR mit
 *     `darf_schreiben === true`, sonst ausgegraut mit Hinweis),
 *   * was die Gesprächsliste an einer Runde zeigt (`istRunde`,
 *     `rundenZeilenText`),
 *   * was im Rundenkopf steht — auch „bis 8“ (`rundenKopf`, `darfVorschlagen`),
 *   * die Vorschlags-Systemzeile (`vorschlagZeile`: Satz des Servers,
 *     Zustimmen/Ablehnen nur solange offen und nie am eigenen Vorschlag),
 *   * der Hinweis für neu Eingetretene (`EINTRITT_HINWEIS`).
 *
 * KEINE Rechtelogik: eine Runde, die der Server nicht zulässt, bleibt im
 * Frontend einfach unangeklickt — es gibt hier keine zweite Sperrprüfung.
 *
 * Ohne DOM prüfbar: `tests/chat7bui-a-runden.test.mjs`.
 */

import { RUNDE_TITEL, UNBEKANNTE_PERSON } from './nachrichtenLogik.mjs'

// ── Grenzen und Texte (eine Stelle) ─────────────────────────────────────────

/** Mindestens so viele ANDERE Beteiligte (ich + 2). Konzept S3 / Server. */
export const ANDERE_MIN = 2
/** Höchstens so viele ANDERE Beteiligte (ich + 7 = 8). Konzept S3 / Server. */
export const ANDERE_MAX = 7
/** Höchstzahl Beteiligter — ab hier schlägt niemand mehr etwas vor. */
export const TEILNEHMER_MAX = ANDERE_MAX + 1

/** Grenzen zusammen — für den Zähler im Dialog („2–7 Personen auswählen“). */
export const AUSWAHL = Object.freeze({ min: ANDERE_MIN, max: ANDERE_MAX })

/** Höchstlänge des Rundennamens — dieselbe Zahl wie `RUNDE_TITEL_MAX` im Server. */
export const RUNDE_TITEL_MAX = 140

/** Einstieg neben „Neue Nachricht“ (Karte Punkt 1). */
export const NEUE_RUNDE = 'Neue Runde'

/** Abschnitt der Gesprächsliste (Konzept-Entwurf B-desktop: RUNDEN zuerst). */
export const ABSCHNITT_RUNDEN = 'Runden'

/**
 * Titel einer Runde ohne Namen — nie eine leere Zeile, nie „None“. Der
 * Wortlaut steht in `nachrichtenLogik.mjs` (`RUNDE_TITEL`, dieselbe Stelle wie
 * `UNBEKANNTE_PERSON`) und wird hier nur weitergegeben.
 */
export const OHNE_NAMEN = RUNDE_TITEL

/** Knopf im Rundenkopf (Karte Punkt 3). */
export const VORSCHLAG_KNOPF = 'Person vorschlagen'
/** Knopf im Rundenkopf (Karte Punkt 3) — fragt vorher nach (`gefahr`). */
export const VERLASSEN_KNOPF = 'Runde verlassen'
/** Wortlaut der Rückfrage — er steht so in der Karte. */
export const VERLASSEN_TEXT = 'Du siehst die Runde danach nicht mehr. Offene Vorschläge enden.'

/** Hinweis oben im Verlauf für neu Eingetretene (Karte Punkt 5). */
export const EINTRITT_HINWEIS = 'Du siehst Nachrichten ab deinem Eintritt.'

/**
 * Die Art einer Vorschlags-Systemzeile im Verlauf (Server: `system.art`).
 * Dieselbe Kennung wie `_zeile` in `api/chat.py` (`{"art": "runde_vorschlag"}`).
 */
export const SYSTEM_VORSCHLAG = 'runde_vorschlag'

/** Die Stände eines Vorschlags (Server: `chat_runde_vorschlag.stand`). */
export const STAND_OFFEN = 'offen'
export const STAND_ANGENOMMEN = 'angenommen'
export const STAND_ABGELEHNT = 'abgelehnt'
export const STAND_BEENDET = 'beendet'

/** Ruhige Stand-Zeile einer Vorschlagszeile (`''` = nichts anzuzeigen). */
export const STAND_TEXTE = Object.freeze({
  [STAND_ANGENOMMEN]: 'Angenommen.',
  [STAND_ABGELEHNT]: 'Abgelehnt.',
  [STAND_BEENDET]: 'Beendet.',
})

// ── Runden erkennen ─────────────────────────────────────────────────────────

/** Ist der Eintrag eine Runde? (`art: 'runde'` aus `meine_gespraeche`) */
export function istRunde(eintrag) {
  return Boolean(eintrag) && String(eintrag.art || '') === 'runde'
}

/** Der Name einer Runde — leer heißt „Runde“ (der Server lässt keinen leeren zu). */
export function rundenTitel(eintrag) {
  const roh = String(eintrag?.titel || '').trim()
  return roh || OHNE_NAMEN
}

/**
 * Die Zeile unter dem Titel einer Runde in der Liste: „4 Personen“.
 * (Bei einer Person heißt das nicht „im Gespräch“ — die Runde hat keinen Ort,
 * sondern Menschen; „1 Beteiligte“ war falsch, Review R1 Punkt 7.)
 */
export function rundenZeilenText(eintrag) {
  const zahl = Math.max(0, Number(eintrag?.teilnehmer) || 0)
  if (!zahl) return ''
  return zahl === 1 ? '1 Person' : `${zahl} Personen`
}

/** Die Unterzeile des Verlaufskopfs einer Runde — dieselbe Zahl, dieselbe Vokabel. */
export function rundenKopf(eintrag) {
  return rundenZeilenText(eintrag)
}

// ── „Neue Runde“: Dialog und Auswahl ────────────────────────────────────────

/**
 * Ein Suchtreffer aus `chat.personen_suchen`, wie die Auswahl ihn braucht.
 *
 * Wählbar ist NUR, was der Server beschreibbar nennt (`darf_schreiben ===
 * true`). Alles andere steht da, ist aber ausgegraut — „nicht auswählbar“ ist
 * hier ein WAHRHEITSWERT, keine geprüfte Bedingung im Zeichner (wie bei
 * `personTreffer` in `nachrichtenSuche.mjs`).
 *
 * Der Hinweis nennt den GRUND NICHT: der Server unterscheidet „gesperrt“ und
 * „nicht erreichbar“ nicht (`personen_suchen` → `hat_konto`/`darf_schreiben`),
 * und die Oberfläche erfindet nichts dazu.
 */
export function rundenKandidat(treffer) {
  if (!treffer || typeof treffer !== 'object') return null
  const mitglied = String(treffer.mitglied || '').trim()
  if (!mitglied) return null
  const name = String(treffer.anzeigename || '').trim() || mitglied
  const waehlbar = treffer.darf_schreiben === true
  return {
    mitglied,
    name,
    bild: String(treffer.bild || '').trim(),
    waehlbar,
    hinweis: waehlbar ? '' : 'nicht auswählbar',
  }
}

/** Alle wählbaren Kandidaten einer Server-Antwort (`{treffer: [...]}`). */
export function kandidatenAusAntwort(antwort) {
  const roh = Array.isArray(antwort?.treffer) ? antwort.treffer : []
  return roh.map(rundenKandidat).filter(Boolean)
}

/** Steht diese Kennung in der Auswahl? */
export function istGewaehlt(auswahl, mitglied) {
  const k = String(mitglied || '').trim()
  if (!k) return false
  return (Array.isArray(auswahl) ? auswahl : []).some((m) => String(m) === k)
}

/**
 * Ein Klick auf einen Treffer: hinzufügen oder herausnehmen — nie über die
 * Grenze hinaus. Ist die Auswahl voll, ändert ein weiterer Klick NICHTS
 * (die Kandidatenzeile ist dann ohnehin gesperrt; hier steht die Regel für
 * den Aufrufer an einer Stelle).
 */
export function auswahlUmschalten(auswahl, mitglied, { max = ANDERE_MAX } = {}) {
  const liste = (Array.isArray(auswahl) ? auswahl : []).map(String)
  const k = String(mitglied || '').trim()
  if (!k) return liste
  if (liste.includes(k)) return liste.filter((m) => m !== k)
  if (liste.length >= max) return liste
  return [...liste, k]
}

/** Der Zähler des Dialogs („2–7 Personen auswählen“ — Wortlaut der Karte). */
export function zaehlerText({ anzahl = 0, min = ANDERE_MIN, max = ANDERE_MAX } = {}) {
  const zahl = Math.max(0, Number(anzahl) || 0)
  return `${zahl} von ${min}–${max} Personen auswählen`
}

/** Ist die Auswahl gültig? (Name da, 2–7 andere, keine Doppelten.) */
export function auswahlGueltig({ titel = '', auswahl = [] } = {}) {
  const name = String(titel || '').trim()
  if (!name) return false
  if (name.length > RUNDE_TITEL_MAX) return false
  const liste = (Array.isArray(auswahl) ? auswahl : []).map((m) => String(m || '').trim()).filter(Boolean)
  if (new Set(liste).size !== liste.length) return false
  return liste.length >= ANDERE_MIN && liste.length <= ANDERE_MAX
}

/**
 * Der ganze Zustand des Dialogs „Neue Runde“ — EINE Stelle für Knopf, Zähler
 * und Hinweis (die Seite zeichnet nur).
 *
 * `anlegen` ist der Anlegen-Knopf: er steht erst, wenn die Auswahl gültig ist
 * (Karte Punkt 1) — und er ist gesperrt, solange ein Aufruf läuft.
 */
export function rundeAnlegenZustand({ titel = '', auswahl = [], laeuft = false } = {}) {
  const anzahl = (Array.isArray(auswahl) ? auswahl : []).length
  const gueltig = auswahlGueltig({ titel, auswahl })
  return {
    anzahl,
    gueltig,
    zaehler: zaehlerText({ anzahl }),
    anlegen: gueltig,
    laeuft: laeuft === true,
  }
}

/**
 * Der Rumpf des Aufrufs `chat.runde_anlegen(titel, mitglieder)` — exakt die
 * Felder des Servers. `mitglieder` sind die ANDEREN (2–7), getrimmt und ohne
 * Doppelte; die eigene Person steht NICHT darin (der Server lehnt das ab).
 */
export function rundeAnlegenRumpf({ titel = '', auswahl = [], ich = '' } = {}) {
  const eigene = String(ich || '').trim()
  const mitglieder = [...new Set((Array.isArray(auswahl) ? auswahl : [])
    .map((m) => String(m || '').trim())
    .filter((m) => m && m !== eigene))]
  return { titel: String(titel || '').trim(), mitglieder }
}

// ── Rundenkopf: Vorschlagen, Verlassen ──────────────────────────────────────

/**
 * Die Beteiligten einer Runde für den Kopf (Karte Punkt 3, Review R1 Punkt 4).
 *
 * Vertrag: `chat.meine_gespraeche` liefert NUR bei Runden
 * `mitglieder: [{mitglied, anzeigename}]` — aktive Teilnehmende inklusive mir.
 * Hier wird NICHTS nachgeschlagen: keine Kennung wird zu einem Namen
 * „gesucht“ (der alte Weg über `personen_suchen` ist gestrichen), und eine
 * Kennung ohne Namen erscheint als `UNBEKANNTE_PERSON`, nie roh.
 */
export function rundenMitglieder(eintrag) {
  const liste = Array.isArray(eintrag?.mitglieder) ? eintrag.mitglieder : []
  const gesehen = new Set()
  const raus = []
  for (const roh of liste) {
    const mitglied = String(roh?.mitglied || '').trim()
    if (!mitglied || gesehen.has(mitglied)) continue
    gesehen.add(mitglied)
    const name = String(roh?.anzeigename || '').trim()
    raus.push({ mitglied, name: name || UNBEKANNTE_PERSON })
  }
  return raus
}

/**
 * Die Kennungen, die „Person vorschlagen“ NICHT anbieten darf: ich selbst und
 * alle aktiven Beteiligten (Review R1 Punkt 5) — für `RundePersonenAuswahl`
 * als `:ohne`.
 */
export function vorschlagOhne(eintrag, ich = '') {
  const eigene = String(ich || '').trim()
  const liste = rundenMitglieder(eintrag).map((m) => m.mitglied)
  if (eigene) liste.push(eigene)
  return [...new Set(liste)]
}

/**
 * Darf „Person vorschlagen“ jetzt dastehen?
 *
 * Der Server lässt einen Vorschlag nur zu, solange die Runde unter 8
 * Beteiligten steht (`rechte.darf_runde_erweitern`, „nur unter 8 Beteiligte“).
 * Das ist hier KEINE zweite Rechteprüfung, sondern eine Zahl aus der Antwort
 * von `meine_gespraeche` (`teilnehmer`) — sie sagt, ob der Knopf überhaupt
 * einen Sinn hat. `teilnehmer` fehlt/ist 0 → der Knopf bleibt (der Server
 * entscheidet, nicht eine fehlende Zahl).
 */
export function darfVorschlagen(eintrag) {
  if (!istRunde(eintrag)) return false
  const zahl = Number(eintrag?.teilnehmer)
  if (!Number.isInteger(zahl) || zahl <= 0) return true
  return zahl < TEILNEHMER_MAX
}

/** Der Rumpf von `chat.runde_vorschlagen(gespraech, mitglied)`. */
export function vorschlagRumpf(gespraech, mitglied) {
  return {
    gespraech: String(gespraech || '').trim(),
    mitglied: String(mitglied || '').trim(),
  }
}

/**
 * Die Rückfrage vor „Runde verlassen“ — `gefahr: true` und der Wortlaut der
 * Karte. Die Seite reicht sie unverändert an `bestaetigen(...)` (der eine
 * Rückfragedialog des Hauses, CHAT-3a).
 */
export function verlassenFrage() {
  return {
    titel: `${VERLASSEN_KNOPF}?`,
    text: VERLASSEN_TEXT,
    aktion: VERLASSEN_KNOPF,
    gefahr: true,
  }
}

/** Der Rumpf von `chat.runde_verlassen(gespraech)`. */
export function verlassenRumpf(gespraech) {
  return { gespraech: String(gespraech || '').trim() }
}

// ── Vorschlags-Systemzeile im Verlauf ───────────────────────────────────────

/** Ist diese Verlaufszeile eine Vorschlags-Systemzeile? */
export function istVorschlagZeile(zeile) {
  return String(zeile?.system?.art || '') === SYSTEM_VORSCHLAG
}

/**
 * Eine Vorschlags-Systemzeile, wie die Oberfläche sie zeichnet.
 *
 * Der SATZ kommt vom Server (Feld `text` der Verlaufszeile, dort beim Lesen aus
 * der Vorschlagszeile gebildet — `_vorschlag_verlaufszeile` in `api/chat.py`).
 * Hier wird er nicht nachgebaut, nur durchgereicht; fehlt er, steht ein
 * neutraler Satz da (nie eine leere Zeile).
 *
 * Zustimmen/Ablehnen stehen NUR, solange der Vorschlag offen ist, und NIE am
 * eigenen Vorschlag — „der Vorschlagende stimmt nicht mit“ (Server: eigene
 * Zustimmung → 417 „Über den eigenen Vorschlag stimmt die Runde ab“). Ob es
 * der eigene ist, sagt `system.eigene` aus der Antwort; fehlt das
 * Feld, gilt „nicht meiner“ und der Server entscheidet (er lehnt ab).
 *
 * Status: `angenommen` / `abgelehnt` / `beendet` stehen ruhig als Text daneben
 * (`STAND_TEXTE`), ohne Knöpfe.
 *
 * Vertrag (Review R1): `system = {art, stand, vorschlag, eigene}` —
 * `vorschlag` ist die Kennung für `runde_zustimmen`/`runde_ablehnen` (NICHT
 * die Kennung der Zeile), `eigene` sagt, ob die LESENDE Person vorgeschlagen
 * hat. Fehlt `eigene`, gilt „nicht meiner“ und der Server entscheidet.
 */
export function vorschlagZeile(zeile) {
  if (!istVorschlagZeile(zeile)) return null
  const stand = String(zeile?.system?.stand || '').trim()
  const offen = stand === STAND_OFFEN
  const eigene = zeile?.system?.eigene === true
  const vorschlag = String(zeile?.system?.vorschlag || '').trim()
  const satz = String(zeile?.text || '').trim() || 'Ein Vorschlag, jemanden hinzuzufügen.'
  return {
    satz,
    stand,
    standText: STAND_TEXTE[stand] || '',
    offen,
    eigene,
    vorschlag,
    // Ohne Kennung kein Knopf: ein Aufruf ohne `vorschlag` könnte nichts tun.
    abstimmbar: offen && !eigene && Boolean(vorschlag),
  }
}

/** Der Rumpf von `chat.runde_zustimmen(vorschlag)` / `runde_ablehnen(vorschlag)`. */
export function stimmeRumpf(vorschlag) {
  return { vorschlag: String(vorschlag || '').trim() }
}

// ── Eintritt ────────────────────────────────────────────────────────────────

/**
 * Steht der Eintritts-Hinweis oben im Verlauf? (Karte Punkt 5)
 *
 * NUR, wenn der Server das Feld mitbringt (`ab_eintritt: true` an der Antwort
 * von `chat.verlauf` — die Sichtbarkeit ab Eintritt gilt dort lückenlos, siehe
 * `_sichtbar_ab`/`CHAT-7b-2`). Fehlt das Feld, wird NICHTS behauptet.
 */
export function eintrittsHinweis(antwort) {
  return antwort?.ab_eintritt === true ? EINTRITT_HINWEIS : ''
}

/** Anzeigename eines Vorschlagsziels — der Server liefert ihn (`anzeigename`). */
export function vorschlagName(vorschlag) {
  const roh = String(vorschlag?.anzeigename || '').trim()
  return roh || UNBEKANNTE_PERSON
}
