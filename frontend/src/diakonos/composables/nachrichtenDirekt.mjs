/**
 * CHAT-7a — Regeln für „Nachricht schreiben“ und Direktgespräche (1:1).
 *
 * Grundlage: `docs/konzepte/CHAT-KONZEPT.md` 10.1 Punkt 4, Tabelle ~Z. 731,
 * Karte CHAT-R2c (nur der Teil „Nachricht schreiben“), Entwürfe
 * `chat-entwurf/B-profil.html`, `B-desktop.html`, `B-handy.html`.
 * CHAT-7b-UI-b: dazu die Kontaktsperre („Nicht mehr anschreiben lassen“,
 * Konzept S3) — Texte, Rückfrage, Aufheben-Link und die Liste der eigenen
 * Sperren (`sperrListe`, `sperrStand`).
 *
 * WAS HIER STEHT UND WAS NICHT
 * Hier stehen NUR Entscheidungen, die aus einer SERVER-ANTWORT folgen:
 *
 *   * der Zustand des Knopfes „Nachricht schreiben“ am Personenprofil
 *     (`profilZustand`) — gespeist aus `darf_schreiben` / `hat_konto` /
 *     `gespraech` der Personensuche,
 *   * was die Liste im 1:1 zeigt (`istDirekt`, `zeilenKontoText`,
 *     `verlaufUnterzeile`, `direktTitel`),
 *   * ob die Eingabe ersetzt wird (`sendbar`, `NICHT_ERREICHBAR`) und wie
 *     sich ein Server-Fehler des Sendens einordnet (`sendeFehlerZustand`).
 *
 * Der Lesestand („gelesen“ / „gelesen von N“) steht NICHT hier, sondern an
 * der EIGENEN Nachricht (`lesestandText(n, { direkt })` in
 * `nachrichtenLogik.mjs`) — im 1:1 heißt er dort „gelesen“. In der Liste und
 * im Verlaufskopf hat er nichts zu suchen (Karte CHAT-7a-UI-2, Punkt 1).
 *
 * Wohin ein Suchtreffer führt, steht NICHT hier: das entscheidet
 * `personTreffer()` in `composables/nachrichtenSuche.mjs` (CHAT-3c) an der
 * einen Suche — mit `gespraech` öffnet er den Chat, sonst das Profil.
 * Zwei Suchen und zwei Zielregeln nebeneinander wären ein Fehler (CHAT-7a-UI,
 * Review R1).
 *
 * KEINE Rechtelogik: `darf_schreiben` und `hat_konto` kommen vom Server
 * (`rechte.darf_direktnachricht` / `rechte.person_hat_konto`) — hier wird nur
 * gezeichnet, was der Server zugesagt hat. Fehlt die Zusage (Feld fehlt,
 * `null`, Wahrheitswert falsch), gilt „nein“ (fail closed).
 *
 * Ohne DOM prüfbar: `tests/chat7-direkt-ui.test.mjs`,
 * `tests/chat7bui-b-sperren.test.mjs`.
 */
import { fehlertext } from '../../shared/fehlertexte.js'
import { BEREICH, UNBEKANNTE_PERSON, beginntMit } from './nachrichtenLogik.mjs'

export { UNBEKANNTE_PERSON, beginntMit }

// ── Texte ───────────────────────────────────────────────────────────────────

/** Knopf am Personenprofil (Konzept 10.1 Punkt 4). */
export const PROFIL_KNOPF = {
  normal: 'Nachricht schreiben',
  gespraech: 'Zum Gespräch',
  keinKonto: 'Nachricht schreiben',
}

/** Hinweis, warum der Knopf nicht geht (Person ohne Konto, Konzept Punkt 3). */
export const KEIN_KONTO_TEXT = 'hat kein Konto'

/** Zeile unter dem Knopf, wenn es das 1:1-Gespräch noch nicht gibt. */
export const NOCH_KEIN_GESPRAECH = 'Ihr habt noch kein Gespräch — der erste Klick legt es an.'

/**
 * Hinweis am Profil, nachdem der Server das Öffnen mit 403 verweigert hat
 * (Karte UI-2, Punkt 3). Die Karte BLEIBT stehen und der Knopf bleibt sichtbar,
 * nur ausgegraut — sie zu entfernen ließe den Hinweis mitverschwinden; die
 * Person sähe dann nur einen stummen, nicht mehr erklärten Weg.
 */
export const PROFIL_NICHT_MOEGLICH = 'Für diese Person ist keine Nachricht möglich.'

/**
 * Die ruhige Zeile im Verlauf eines 1:1-Gesprächs, wenn Senden nicht mehr
 * geht (Server 403 / Gegenüber ausgetreten). Der Verlauf bleibt lesbar —
 * ersetzt wird NUR die Eingabe (Karte Punkt 3).
 */
export const NICHT_ERREICHBAR = {
  titel: 'Diese Person ist nicht mehr erreichbar.',
  text: 'Den bisherigen Verlauf kannst du weiter lesen.',
}

/** Beschriftung des Einstiegs in die Personensuche. */
export const NEUE_NACHRICHT = 'Neue Nachricht'

/** Adresse der Personensuche (Router: `#/nachrichten/suche`, Chat-Konzept 10.2). */
export const SUCHE = `${BEREICH}/suche`

/** Adresse eines bestehenden Gesprächs (`#/nachrichten/<gespraech>`). */
export function chatAdresse(gespraech) {
  const kennung = String(gespraech || '').trim()
  if (!kennung) return BEREICH
  return `${BEREICH}/${encodeURIComponent(kennung)}`
}

/** Adresse des Personenprofils (`#/mitglied/<id>`, Konzept 10.2 — unverändert). */
export function profilAdresse(mitglied) {
  const kennung = String(mitglied || '').trim()
  if (!kennung) return '#/personen'
  return `#/mitglied/${encodeURIComponent(kennung)}`
}

/** Adresse der Personensuche; mit Begriff eingetragen (`?q=…`). */
export function sucheAdresse(begriff = '') {
  const text = String(begriff || '').trim()
  return text ? `${SUCHE}?q=${encodeURIComponent(text)}` : SUCHE
}

// ── Personenprofil ──────────────────────────────────────────────────────────

/**
 * Der Zustand des Knopfes „Nachricht schreiben“ — AUSSCHLIESSLICH aus der
 * Serverantwort.
 *
 * Quelle ist der Treffer der Personensuche (`personen_suchen`): er trägt
 * `darf_schreiben`, `hat_konto` und `gespraech` (Kennung des BESTEHENDEN
 * 1:1-Gesprächs oder leer). Der Server hat dort schon entschieden, ob das
 * Schreiben erlaubt ist (`rechte.darf_direktnachricht`) — das Frontend
 * entscheidet nichts nach.
 *
 * Regeln (Karte Punkt 1):
 *   * keine Antwort / Person nicht in der Suche → `sichtbar: false`
 *     (fail closed: ohne Zusage gibt es keinen Knopf),
 *   * Person ohne Konto → `deaktiviert: true`, Hinweis „hat kein Konto“
 *     (der Server verweigert `direkt_oeffnen` für sie ohnehin mit 403),
 *   * `gespraech` gesetzt → die Zeile „Zum Gespräch“ statt „neu anfangen“,
 *   * `verweigert: true` (der Server hat das Öffnen mit 403 abgelehnt, Karte
 *     UI-2 Punkt 3) → der Knopf BLEIBT stehen, ist aber ausgegraut, und der
 *     Hinweis „Für diese Person ist keine Nachricht möglich.“ tritt an die
 *     Stelle von „leg es an“,
 *   * alles andere (darf schreiben, kein Gespräch) → der normale Knopf.
 *
 * Der Fall `verweigert` steht VOR `darf_schreiben`: der Server hat gerade
 * Nein gesagt, da hilft die alte Zusage nicht mehr. Fehlt dagegen jede Antwort
 * UND liegt keine Verweigerung vor, gibt es keinen Knopf — aber eine
 * Verweigerung ist eine Antwort, und die wird gezeigt.
 *
 * @param {{darf_schreiben?: boolean, hat_konto?: boolean, gespraech?: string|null}|null} treffer
 * @param {{verweigert?: boolean}} [lage]
 * @returns {{sichtbar: boolean, deaktiviert: boolean, hatGespraech: boolean,
 *            text: string, hinweis: string, gespraech: string}}
 */
export function profilZustand(treffer, { verweigert = false } = {}) {
  const leer = {
    sichtbar: false,
    deaktiviert: false,
    hatGespraech: false,
    text: PROFIL_KNOPF.normal,
    hinweis: '',
    gespraech: '',
  }
  // Der Server hat es gerade abgelehnt: der Weg bleibt sichtbar, aber gesperrt.
  // Die alte Aussage (`darf_schreiben`) wird NICHT nachgezogen — sie war falsch.
  if (verweigert === true) {
    const gespraech = String(treffer?.gespraech || '').trim()
    return {
      sichtbar: true,
      deaktiviert: true,
      hatGespraech: Boolean(gespraech),
      text: gespraech ? PROFIL_KNOPF.gespraech : PROFIL_KNOPF.normal,
      hinweis: PROFIL_NICHT_MOEGLICH,
      gespraech,
    }
  }
  if (!treffer || typeof treffer !== 'object') return leer
  const gespraech = String(treffer.gespraech || '').trim()
  // Kein Konto: auffindbar, aber nicht beschreibbar (Konzept Punkt 3).
  if (treffer.hat_konto === false) {
    return {
      sichtbar: true,
      deaktiviert: true,
      hatGespraech: Boolean(gespraech),
      text: PROFIL_KNOPF.keinKonto,
      hinweis: KEIN_KONTO_TEXT,
      gespraech,
    }
  }
  // Die EINE Zusage des Servers. Fehlt sie, gibt es keinen Knopf.
  if (treffer.darf_schreiben !== true) return leer
  if (gespraech) {
    return {
      sichtbar: true,
      deaktiviert: false,
      hatGespraech: true,
      text: PROFIL_KNOPF.gespraech,
      hinweis: '',
      gespraech,
    }
  }
  return {
    sichtbar: true,
    deaktiviert: false,
    hatGespraech: false,
    text: PROFIL_KNOPF.normal,
    hinweis: NOCH_KEIN_GESPRAECH,
    gespraech: '',
  }
}

// ── Liste und Verlauf eines 1:1-Gesprächs ───────────────────────────────────

/** Ist der Eintrag ein Direktgespräch (1:1)? */
export function istDirekt(eintrag) {
  return Boolean(eintrag) && String(eintrag.art || '') === 'direkt'
}

/**
 * Der Titel eines 1:1-Gesprächs; ohne Namen „Unbekannte Person“ (Karte UI-2
 * Punkt 6). Ein Eintrag aus dem Altbestand kann leer ankommen (Mitgliedsdatensatz
 * weg, Anzeigename nie gesetzt) — „Gespräch“ oder eine leere Zeile nennt keinen,
 * den man ansprechen könnte. Der Wortlaut selbst steht in `nachrichtenLogik`
 * (`UNBEKANNTE_PERSON`) — EINE Stelle, damit Liste und Kopf nicht auseinanderlaufen.
 */
export function direktTitel(eintrag) {
  const roh = String(eintrag?.titel || '').trim()
  return roh || UNBEKANNTE_PERSON
}

/**
 * Was in der Liste rechts unter dem Titel steht — im 1:1 GAR NICHTS.
 *
 * CHAT-7a hatte dort „gelesen“ stehen; das war falsch verortet (Karte UI-2
 * Punkt 1): der Lesestand einer Liste ist MEIN Stand, und der gehört nicht als
 * Wort neben die Uhrzeit — der Zähler `ungelesen` sagt bereits alles. Im 1:1
 * steht also nur die Zeit; in Gruppen bleibt „N im Gespräch“.
 */
export function zeilenKontoText(eintrag) {
  if (istDirekt(eintrag)) return ''
  const zahl = Math.max(0, Number(eintrag?.teilnehmer) || 0)
  return zahl ? `${zahl} im Gespräch` : ''
}

/**
 * Die Zeile unter dem Titel des offenen Gesprächs (Verlaufskopf).
 *
 * Im 1:1 gibt es nichts zu zählen und niemanden aufzuzählen — dort bleibt sie
 * LEER (Karte UI-2 Punkt 5). Vorher stand da „gelesen“ und, wenn die Liste noch
 * nicht da war, ein Gruppen-Satz über Untergruppen. Ein Text über die Gruppe
 * in einem 1:1 ist schlicht falsch benannt.
 *
 * @param {{istDirekt?: boolean, teilnehmer?: number}} lage
 */
export function verlaufUnterzeile({ istDirekt: direkt = false, teilnehmer = 0 } = {}) {
  if (direkt) return ''
  const zahl = Math.max(0, Number(teilnehmer) || 0)
  return zahl ? `${zahl} im Gespräch` : ''
}

/**
 * Darf in dieses Gespräch geschrieben werden?
 *
 * Karte UI-2 Punkt 2: Senden wird AUSSCHLIESSLICH durch eine 403-Antwort des
 * Servers gesperrt (`sendenVonServerGesperrt`, gesetzt in `sende`). Vorher
 * sperrte diese Stelle zusätzlich aus ANZEIGEFELDERN — ein leeres `mitglied`
 * (laut Backend nur Anzeige) und ein Gruppen-Chat, der gerade nicht in der
 * Liste stand, obwohl die Liste lediglich (noch) nicht geladen war. Beides war
 * Rechtelogik aus Darstellung und nahm Menschen das Schreiben, die es durften.
 *
 * Geblieben ist EINE Bedingung: es gibt ein offenes Gespräch. Ohne Gespräch
 * keine Eingabe — das ist keine Rechtefrage, sondern Geometrie.
 *
 * CHAT-5-UI: Dazu kommt das Serverfeld `darf_senden` aus `meine_gespraeche`
 * (dieselbe Aktion wie „Umfrage starten“). Es ist keine abgeleitete Rechtelogik,
 * sondern die Antwort des Servers auf genau diese Frage; fehlt das Feld (alter
 * Server), bleibt es beim bisherigen „ja“ — der Server entscheidet ohnehin
 * erneut.
 */
export function sendbar(eintrag, { gesperrt = false } = {}) {
  if (gesperrt === true) return false
  if (eintrag?.darf_senden === false) return false
  return Boolean(eintrag)
}

/**
 * Ein Fehler beim Senden: ist es „nicht mehr erreichbar“ (1:1, Gegenüber weg)
 * oder ein gewöhnlicher Hinweis?
 *
 * 403 heißt bei den Chat-Endpunkten OHNE Inhalt „kein Zugriff“ (Server `_h()`).
 * In einem 1:1 ist die einzige sinnvolle Lesart: das Gegenüber ist nicht mehr
 * erreichbar. Der Verlauf bleibt stehen, die Eingabe weicht dem Hinweis.
 * In einer Gruppe bleibt es beim gewohnten Fehlertext — dort gibt es kein
 * Gegenüber, das „weg“ sein könnte (Karte UI-2 Punkt 2).
 */
export function sendeFehlerZustand(fehler, { direkt = false } = {}) {
  const status = Number(fehler?.status) || 0
  const art = String(fehler?.exc_type || fehler?.excType || '')
  if (direkt && (status === 403 || art === 'PermissionError')) {
    return { gesperrt: true, titel: NICHT_ERREICHBAR.titel, text: NICHT_ERREICHBAR.text }
  }
  return { gesperrt: false, titel: 'Die Nachricht ging nicht raus', text: fehlertext(fehler) }
}

// ── Kontaktsperre (CHAT-7b-UI-b, Konzept S3) ────────────────────────────────

/**
 * Wie die eine Aktion heißt: hier und in der Sperrliste (EINE Quelle — zwei
 * Wortlaute für dieselbe Sache wären zwei Wahrheiten).
 */
export const SPERR_AKTION = 'Nicht mehr anschreiben lassen'

/** Knopf der Liste „Gesperrte Personen“: hebt EINE Sperre auf. */
export const AUFHEBEN = 'Aufheben'

/** Abschnitt der Einstellungen (Gruppe „Datenschutz“), eigene Adresse. */
export const SPERR_SEITE = {
  titel: 'Gesperrte Personen',
  href: '#/einstellungen/sperren',
}

/** Leerzustand der Liste — ein Satz, kein Katalogtext (§15). */
export const SPERR_LEER = 'Du hast niemanden gesperrt.'

/**
 * Einleitung des Abschnitts: was die Sperre tut und was NICHT. Sie erscheint
 * nur hier (die gesperrte Person erfährt nichts) — deshalb steht der Satz
 * „erfährt davon nichts“ genau einmal auf der Seite.
 */
export const SPERR_EINLEITUNG = 'Personen auf dieser Liste können dir keine Nachrichten '
  + 'mehr schreiben, und du ihnen auch nicht. Die andere Seite erfährt davon nichts. '
  + 'Du kannst eine Sperre jederzeit aufheben.'

/** Fehler beim Aufheben, wenn der Server nicht mag (kein „Unbekannter Fehler“). */
export const SPERR_FEHLER = 'Die Sperre konnte nicht aufgehoben werden.'

/**
 * Name der gesperrten Person für Rückfrage, Hinweis und Liste. Fehlt er (der
 * Server kürzt Ausgetretene, ein Altbestand kann leer ankommen), steht dort
 * „diese Person“ — ein Satz ohne Namen ist besser als ein Satz mit `null`.
 */
export function sperrName(anzeigename, mitglied) {
  return String(anzeigename || '').trim() || String(mitglied || '').trim() || 'diese Person'
}

/**
 * Die Rückfrage vor dem Sperren. Geschlechtsneutral: das Gegenüber wird NICHT
 * mit „sie/er“ benannt („diese Person“, „der Person“) — der Anzeigename ist
 * der einzige Name im Satz.
 *
 * Der zweite Satz sagt, was die andere Seite NICHT erfährt (Konzept S3: die
 * Sperre ist still, ohne Begründung), der dritte, wie sie wieder weggeht.
 */
export function sperrFrage(anzeigename, mitglied) {
  const name = sperrName(anzeigename, mitglied)
  return `${name} kann dir dann keine Nachrichten mehr schreiben, und du dieser Person auch nicht. `
    + `${name} erfährt davon nichts. Du kannst das jederzeit in den Einstellungen aufheben.`
}

/** Die Rückfrage als Objekt für `bestaetigen` (Dialog des Hauses). */
export function sperrBestaetigung(anzeigename, mitglied) {
  return {
    titel: 'Nicht mehr anschreiben lassen?',
    text: sperrFrage(anzeigename, mitglied),
    aktion: SPERR_AKTION,
  }
}

/**
 * Der ruhige Hinweis NACH dem Sperren (`role="status"` — keine Alarmfarbe:
 * es ist eine Auskunft, kein Fehler).
 */
export function sperrErfolg(anzeigename, mitglied) {
  const name = sperrName(anzeigename, mitglied)
  return `${name} kann dir keine Nachrichten mehr schreiben, und du dieser Person auch nicht. `
    + `Aufheben kannst du das jederzeit unter Einstellungen › ${SPERR_SEITE.titel}.`
}

/**
 * Die Sperrliste aus der Antwort von `chat.meine_sperren` — NUR die Felder,
 * die der Server schickt (`mitglied`, `anzeigename`, `bild`, `angelegt_am`).
 * Ein Eintrag ist ein Link auf das Personenprofil; ohne Kennung gibt es kein
 * Ziel, ohne Namen kein Wort (die Zeile fällt weg, statt „—“ zu zeigen).
 *
 * Fail closed: fehlt `sperren`, ist die Liste LEER — sie enthält dann nur
 * keinen Eintrag, keine Behauptung über Menschen.
 */
export function sperrListe(antwort) {
  const roh = Array.isArray(antwort?.sperren) ? antwort.sperren : []
  const out = []
  const gesehen = new Set()
  for (const e of roh) {
    const mitglied = String(e?.mitglied || '').trim()
    if (!mitglied || gesehen.has(mitglied)) continue
    gesehen.add(mitglied)
    out.push({
      mitglied,
      name: sperrName(e?.anzeigename, mitglied),
      bild: String(e?.bild || '').trim(),
      angelegtAm: String(e?.angelegt_am || '').trim(),
      /** Ziel des Namens: das Personenprofil (dieselbe Adresse wie überall). */
      href: profilAdresse(mitglied),
    })
  }
  return out
}

/**
 * Steht die Person des offenen 1:1 auf der EIGENEN Sperrliste?
 *
 * Das entscheidet allein die Liste aus `chat.meine_sperren` — NICHT eine
 * Eigenschaft des Gesprächs. Den Chat-Endpunkten ist „gesperrt“ nach aussen
 * nicht anzusehen (Server: derselbe Text wie „nicht erreichbar“); der einzige
 * Ort, an dem die eigene Sperre sichtbar ist, ist die eigene Liste.
 *
 * Ohne Kennung: `false`. Ohne Liste: `false` (dann gibt es keinen Aufheben-
 * Link — aber auch keine Behauptung, man habe gesperrt).
 */
export function istGesperrt(mitglied, liste) {
  const kennung = String(mitglied || '').trim()
  if (!kennung || !Array.isArray(liste)) return false
  return liste.some((e) => String(e?.mitglied || '').trim() === kennung)
}

/**
 * Der eine Satz unter dem „nicht erreichbar“-Hinweis — NUR für die sperrende
 * Seite (Karte Punkt 2). Der Hinweis darüber ist absichtlich derselbe wie bei
 * jeder anderen Ursache; dieser Satz verrät die Sperre nur der Person, die sie
 * selbst gesetzt hat.
 *
 * `einstellungen`: Link in den Abschnitt „Gesperrte Personen“ (die Sperre
 * wird dort aufgehoben, nicht hier — eine zweite Aufhebe-Stelle wäre ein
 * zweiter Weg an derselben Entscheidung).
 */
export function sperrHinweis() {
  return {
    text: 'Du hast diese Person gesperrt.',
    linkText: `${AUFHEBEN} unter Einstellungen › ${SPERR_SEITE.titel}`,
    href: SPERR_SEITE.href,
  }
}

