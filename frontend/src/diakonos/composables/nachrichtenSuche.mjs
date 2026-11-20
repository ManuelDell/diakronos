/**
 * CHAT-3c — die Regeln der Personensuche in „Nachrichten“, ohne DOM und ohne Vue.
 *
 * Die Suche (`components/chat/ChatSuche.vue` und `pages/Nachrichten.vue`)
 * zeichnet nur. WAS gesucht wird, WANN gefragt wird und WELCHE Antwort zählt,
 * steht HIER — prüfbar im Node-Test (`tests/chat3c-personensuche.test.mjs`).
 *
 * Grundlagen (Chat-Konzept 10.1 Punkte 2–4, 10.3):
 *   * EIN Feld, zwei Trefferarten: „Personen und Gespräche suchen“.
 *   * Gespräche werden CLIENTSEITIG aus der geladenen Liste gefiltert (Titel).
 *   * Personen ab `SUCHE_MIN_ZEICHEN` Zeichen über `chat.personen_suchen`
 *     (CHAT-R2b, fertig) — entprellt, veraltete Antworten verworfen.
 *   * Ein Personentreffer führt auf das Profil (`#/mitglied/<id>`), ein
 *     Gesprächstreffer in den Verlauf. Personen OHNE Konto
 *     (`hat_konto: false`) stehen dabei, sind aber NICHT antippbar — und
 *     „nicht antippbar“ ist hier die Adresse `null`, nicht eine geprüfte
 *     Bedingung im Zeichner.
 *
 * Review R1 (MUSS 2/3): Die ADRESSE ist ein Eingang, kein Rückkanal. Solange
 * jemand tippt, bestimmt AUSSCHLIESSLICH das Feld, was gesucht wird. Die
 * Adresse wird nachgezogen (still, ohne Lesemarke); sie überschreibt das Feld
 * nie. Sonst löschte ein `?q=…`-Rückweg das gerade Getippte, und ein
 * Zwischenstand von einem Zeichen zeigte Treffer UND Liste doppelt.
 *
 * WAS HIER NICHT STEHT: kein Netzaufruf (der Zeichner gibt `holen` hinein),
 * kein Timer (`entpreller` bekommt Timer und Uhr hinein), keine Farben.
 */

import { gruppierteListe, gespraechHash } from './nachrichtenLogik.mjs'

// ── Grenzen (eine Stelle) ───────────────────────────────────────────────────

/**
 * Kürzeste Sucheingabe. Dieselbe Zahl wie `SUCHE_MIN_ZEICHEN` in
 * `backend/src/diakronos_app/api/chat.py` — der Server antwortet unterhalb
 * ohnehin mit einer leeren Liste; die Oberfläche soll dafür gar nicht erst
 * fragen (Karte: „unter 2 Zeichen kein Aufruf“).
 */
export const SUCHE_MIN_ZEICHEN = 2

/** Wartezeit nach dem letzten Tastendruck, bevor Personen gefragt werden. */
export const ENTPRELLUNG_MS = 300

/** Platzhalter des einen Suchfelds (Karte Punkt 1, Entwurf B-desktop). */
export const SUCH_PLATZHALTER = 'Personen und Gespräche suchen'

/** Adresse der Suche (Router-Eintrag vorhanden, `router.js`: `#/nachrichten/suche`). */
export const SUCH_HASH = '#/nachrichten/suche'

/** Überschriften der beiden Abschnitte (Karte Punkt 1). */
export const ABSCHNITT_GESPRAECHE = 'Gespräche'
export const ABSCHNITT_PERSONEN = 'Personen'

/** Hinweis am Treffer einer Person ohne Konto (Karte Punkt 2, 10.1 Punkt 3). */
export const OHNE_KONTO_TEXT = 'hat kein Konto'

/** Leerzustand, wenn weder Gespräch noch Person passt (GENAU EIN Text). */
export const SUCHE_LEER = {
  titel: 'Nichts gefunden',
  text: 'Suche nach dem Namen einer Person oder dem Namen eines Gesprächs.',
}

// ── Adresse ─────────────────────────────────────────────────────────────────

/** Ist das die Suche? (`#/nachrichten/suche`, auch mit `?q=…` und ohne
 *  Schluss-Schrägstrich.) `gespraechAusHash` in `nachrichtenLogik.mjs` liefert
 *  dafür `null` — die Suche ist KEINE Gesprächskennung. */
export function istSuchHash(hash) {
  const pfad = String(hash || '').split('?')[0].replace(/\/+$/, '')
  return pfad === SUCH_HASH
}

/**
 * Die Adresse der Suche zum Begriff (`?q=` nur, wenn es etwas zu tragen gibt).
 *
 * Hinein geht der ROHE, getrimmte Begriff („Müller“), nicht der gefaltete
 * Suchbegriff des Servers („mueller“) — die Adresse ist zum Teilen und
 * Wiederfinden da, nicht zum Suchen (Review R1, SOLL a).
 *
 * CHAT-3c-2 (MUSS B): Zweiter Parameter ist die Kennung des Gesprächs, das am
 * Desktop RECHTS offen bleibt, während gesucht wird (`&offen=<kennung>`). Steht
 * sie in der Adresse, ist „Feld leeren“ kein Rückschritt in die Liste, sondern
 * ins Gespräch.
 */
export function suchHash(q, offen = '') {
  const begriff = String(q ?? '').trim()
  const kennung = String(offen ?? '').trim()
  const anhang = kennung ? `offen=${encodeURIComponent(kennung)}` : ''
  if (!begriff) return anhang ? `${SUCH_HASH}?${anhang}` : SUCH_HASH
  let basis
  try {
    basis = `${SUCH_HASH}?q=${encodeURIComponent(begriff)}`
  } catch {
    // Unlesbare Kodierung ist kein Grund, die Suche zu verlassen.
    basis = SUCH_HASH
  }
  return anhang ? `${basis}&${anhang}` : basis
}

/**
 * Die Kennung des offenen Gesprächs aus einer Suchadresse
 * (`#/nachrichten/suche?q=anna&offen=CHAT-2`). Leer, wenn die Adresse keine
 * Suche ist oder kein `offen` trägt.
 */
export function offenAusHash(hash) {
  if (!istSuchHash(hash)) return ''
  const rest = String(hash || '').split('?')[1] || ''
  try {
    return String(new URLSearchParams(rest).get('offen') || '').trim()
  } catch {
    return ''
  }
}

/**
 * Der Suchbegriff aus einer Adresse (`#/nachrichten/suche?q=anna%20b`).
 * Leer, wenn die Adresse keine Suche ist oder kein `q` trägt.
 */
export function qAusHash(hash) {
  if (!istSuchHash(hash)) return ''
  const rest = String(hash || '').split('?')[1] || ''
  try {
    const wert = new URLSearchParams(rest).get('q')
    return String(wert || '').trim()
  } catch {
    return ''
  }
}

/**
 * Ist die Suche nach dieser Adresse OFFEN? (Review R1, SOLL d: `#/nachrichten/
 * suche` ohne `q` verhält sich wie der Listenmodus — also nicht offen.)
 */
export function sucheOffenBei(hash) {
  return istSuchHash(hash) && qAusHash(hash) !== ''
}

/** Ziel des Profils einer Person (`#/mitglied/<id>`, bestehende Seite). */
export function profilHash(mitglied) {
  const kennung = String(mitglied || '').trim()
  if (!kennung) return ''
  return `#/mitglied/${encodeURIComponent(kennung)}`
}

// ── Eingabe, Entprellung ────────────────────────────────────────────────────

/** Der Suchbegriff, wie ihn der Server erwartet: getrimmt, gefaltet, klein. */
export function suchbegriff(wert) {
  let text = String(wert ?? '').normalize('NFC').trim().toLowerCase()
  for (const [von, nach] of [['ß', 'ss'], ['ä', 'ae'], ['ö', 'oe'], ['ü', 'ue']]) {
    text = text.split(von).join(nach)
  }
  return text.split(/\s+/).filter(Boolean).join(' ')
}

/**
 * Darf für diese Eingabe überhaupt gefragt werden? (Karte Punkt 1: „ab 2
 * Zeichen“.) Gezählt werden die Zeichen NACH dem Trimmen — zwei Leerzeichen
 * sind keine Suche.
 *
 * Gefaltet wird hier NICHT: „Öl“ sind zwei Zeichen, gleich wie „oe l“. Die
 * Mindestlänge gilt der Eingabe, nicht dem Suchbegriff des Servers.
 */
export function darfPersonenFragen(wert) {
  return String(wert ?? '').trim().length >= SUCHE_MIN_ZEICHEN
}

/** Ist das Feld leer (nichts Getipptes, auch keine Leerzeichen)? */
export function istLeer(wert) {
  return String(wert ?? '').trim() === ''
}

/**
 * Soll die Trefferfläche statt der Liste stehen? Sobald etwas im Feld steht —
 * auch EIN Zeichen (dann gibt es keine Personentreffer, aber auch keine
 * Doppelanzeige von Treffern und voller Liste; Review R1, MUSS 3c).
 */
export function sucheSichtbar(wert) {
  return !istLeer(wert)
}

/**
 * Der Entpreller: sammelt Tastendrücke und lässt erst nach `ENTPRELLUNG_MS`
 * Ruhe EINEN Aufruf zu. Timer und Uhr werden hineingegeben (im Betrieb
 * `setTimeout`/`clearTimeout`, im Test Attrappen) — hier steht kein Timer,
 * den man beim Abbau vergessen könnte; `beenden()` räumt ihn auf.
 *
 * Ein neuer Tastendruck verwirft den alten Termin (`abbrechen`). Der Aufruf
 * bekommt den Begriff, für den er fällig war — der Aufrufer vergleicht ihn mit
 * der aktuellen Eingabe und darf eine späte Antwort verwerfen (`istAktuell`).
 *
 * `darfFragen` entscheidet, ob für einen Begriff überhaupt gefragt wird.
 * Vorgabe ist die Regel der Personensuche (ab `SUCHE_MIN_ZEICHEN` Zeichen);
 * die Erwähnungs-Auswahl (CHAT-9b-2) gibt `() => true` hinein — dort zählt
 * jeder Namensanfang, auch „@“ allein.
 *
 * @param {{ warte?: number, jetzt?: () => number,
 *           timer?: (fn: () => void, ms: number) => any,
 *           timerAus?: (id: any) => void,
 *           beiFaelligkeit: (begriff: string) => any,
 *           darfFragen?: (begriff: string) => boolean }} optionen
 */
export function entpreller({
  warte = ENTPRELLUNG_MS,
  timer = (fn, ms) => setTimeout(fn, ms),
  timerAus = (id) => clearTimeout(id),
  beiFaelligkeit = () => {},
  darfFragen = darfPersonenFragen,
} = {}) {
  let laufend = null
  let letzterBegriff = ''
  let beendet = false
  let anlaeufe = 0

  function stoppen() {
    if (laufend !== null) {
      try { timerAus(laufend) } catch { /* ein kaputter Timer darf nicht blocken */ }
      laufend = null
    }
  }

  return {
    /**
     * Neuer Tastendruck. Unterhalb der Mindestlänge wird NICHT geplant — und ein
     * noch offener Termin fällt weg (sonst fragte die Suche nach „an“, während
     * schon „a“ im Feld steht).
     */
    tippen(begriff) {
      if (beendet) return false
      letzterBegriff = String(begriff ?? '')
      stoppen()
      if (!darfFragen(letzterBegriff)) return false
      anlaeufe += 1
      laufend = timer(() => {
        laufend = null
        if (beendet) return
        beiFaelligkeit(letzterBegriff)
      }, Math.max(0, Number(warte) || 0))
      return true
    },
    /** Offenen Termin fallen lassen, ohne den Entpreller zu beenden
     *  (Feld geleert, Begriff von außen übernommen — Review R1, SOLL b). */
    abbrechen() {
      stoppen()
    },
    /** Alles fallen lassen (Suche geschlossen, Seite abgebaut). */
    beenden() {
      beendet = true
      stoppen()
    },
    /** Läuft ein Termin? (Nur für den Test — kein Betriebsweg.) */
    istGeplant: () => laufend !== null,
    stand: () => ({ laufend: laufend !== null, begriff: letzterBegriff, beendet, anlaeufe }),
  }
}

// ── Antworten ───────────────────────────────────────────────────────────────

/**
 * Zählt diese Antwort? Nur die Antwort zur LETZTEN Eingabe zählt (Karte Punkt
 * 1: „veraltete Antworten verwerfen“). Verglichen wird der FALT-GLEICHE
 * Begriff — „Anna “ und „anna“ sind dieselbe Frage, „ann“ und „anna“ nicht.
 */
export function istAktuell(gefragt, eingabe) {
  const a = suchbegriff(gefragt)
  const b = suchbegriff(eingabe)
  return Boolean(b) && a === b
}

/**
 * Ein Personentreffer, wie die Zeile ihn braucht (Server: `_suche_treffer`).
 *
 * `href` ist die EINE Entscheidung „antippbar?“: Personen OHNE Konto
 * (`hat_konto: false`) haben kein Ziel — sie bleiben sichtbar, aber ohne Link
 * (Karte Punkt 2, Konzept 10.1 Punkt 3). Was der Zeichner daraus macht, ist
 * Darstellung (ausgegraut, kein `<a>`).
 *
 * CHAT-7a (Konzept 10.1 Punkt 4): Gibt es zu der Person schon ein
 * Direktgespräch (`gespraech` aus `chat.personen_suchen`), führt der Treffer
 * DIREKT in dieses Gespräch — sonst auf das Profil, wo „Nachricht schreiben“
 * steht. Ein Treffer führt nie in ein Gespräch, das es nicht gibt: ohne
 * `gespraech` bleibt es beim Profil.
 */
export function personTreffer(t) {
  if (!t || typeof t !== 'object') return null
  const mitglied = String(t.mitglied || '').trim()
  if (!mitglied) return null
  const name = String(t.anzeigename || '').trim() || mitglied
  const hatKonto = t.hat_konto === true
  const gespraech = String(t.gespraech || '').trim()
  return {
    mitglied,
    name,
    bild: String(t.bild || '').trim(),
    hatKonto,
    darfSchreiben: t.darf_schreiben === true,
    gespraech,
    hinweis: hatKonto ? '' : OHNE_KONTO_TEXT,
    href: hatKonto ? (gespraech ? gespraechHash(gespraech) : profilHash(mitglied)) : '',
  }
}

/**
 * Die Liste der Personentreffer aus der Server-Antwort (`{treffer, limit}`).
 * Ohne Filter — für Aufrufer, die keine Gesprächstreffer daneben zeigen.
 */
export function personenAusAntwort(antwort) {
  const roh = Array.isArray(antwort?.treffer) ? antwort.treffer : []
  return roh.map(personTreffer).filter(Boolean)
}

/**
 * Personentreffer OHNE die Personen, deren 1:1 schon als Gesprächstreffer
 * dasteht (Karte CHAT-7a-UI-2, Punkt 8; Review R1, MUSS 1).
 *
 * Beide Treffer führen in DENSELBEN Chat — zweimal dieselbe Person unter
 * „Gespräche“ und „Personen“ ist keine zweite Auskunft, sondern eine
 * Doppelung.
 *
 * Verglichen wird über die KENNUNG, nicht über den Namen: der Personentreffer
 * trägt sein 1:1 in `gespraech` (Server: `chat.personen_suchen`), die
 * Gesprächszeile ihre Kennung in `name` (`chat.meine_gespraeche` /
 * `_gespraech_kopf`) — beides ist derselbe Schlüssel (`C-1`).
 *
 * Ein Namensvergleich war falsch (Operator-Review R1): „Anna Schmidt-Berger“
 * verschwand, sobald es ein 1:1 „Anna Schmidt“ gab, und eine gleichnamige
 * Person ohne Gespräch fiel mit weg.
 *
 * @param {Array<object>} personen Zeilen aus `personenAusAntwort`
 * @param {Array<object>} gespraechstreffer Abschnitte aus `gespraechsTreffer`
 */
export function personenOhneGespraech(personen, gespraechstreffer) {
  const personenListe = Array.isArray(personen) ? personen : []
  // Gesprächstreffer sind ZEILEN der Liste (`listenZeile` aus
  // `gespraechsTreffer`) — `art` und `name` stehen dort genauso wie in den
  // Rohdaten des Servers.
  const kennungen = new Set((Array.isArray(gespraechstreffer) ? gespraechstreffer : [])
    .flatMap((abschnitt) => (Array.isArray(abschnitt?.eintraege) ? abschnitt.eintraege : []))
    .filter((z) => String(z?.art || '') === 'direkt')
    .map((z) => String(z?.name || '').trim())
    .filter(Boolean))
  if (!kennungen.size) return personenListe
  return personenListe.filter((person) => !kennungen.has(String(person?.gespraech || '').trim()))
}

/**
 * Gespräche clientseitig filtern — über den TITEL, wie er in der Liste steht
 * (Karte Punkt 1). Gefaltet wie der Server (`suchbegriff`): „weiss“ findet
 * „Weiß“, „MUELLER“ findet „Müller“.
 *
 * Ergebnis sind DIESELBEN Abschnitte wie `gruppierteListe` (Gruppe,
 * Untergruppe) — die Suche sortiert nicht neu, sie lässt weg.
 *
 * @param {Array<object>} gespraeche die geladene Liste (`meine_gespraeche`)
 * @param {string} q der Suchbegriff
 */
export function gespraechsTreffer(gespraeche, q, jetzt = new Date()) {
  const begriff = suchbegriff(q)
  if (!begriff) return []
  return gruppierteListe(gespraeche, jetzt)
    .map((abschnitt) => ({
      ...abschnitt,
      eintraege: abschnitt.eintraege.filter((z) => suchbegriff(z.titel).includes(begriff)),
    }))
    .filter((abschnitt) => abschnitt.eintraege.length > 0)
}

/**
 * Was die Personenfläche zeigt: `ruhe` (noch zu kurz), `laedt`, `fehler`,
 * `leer`, `treffer`. EINE Stelle — vorher prüfte der Zeichner vier
 * Bedingungen in der Vorlage und eine davon wurde beim Nachbessern vergessen
 * (Review R1, MUSS 1: die leere „Personen“-Überschrift).
 *
 * @param {{ begriff?: string, laedt?: boolean, fehler?: string,
 *           treffer?: Array<object> }} lage
 * @returns {'ruhe'|'laedt'|'fehler'|'leer'|'treffer'}
 */
export function personenZustand({ begriff = '', laedt = false, fehler = '', treffer = [] } = {}) {
  if (!darfPersonenFragen(begriff)) return 'ruhe'
  // Ein Fehler schlägt das Laden: der Satz bleibt stehen, bis jemand „erneut
  // versuchen“ tippt — ein Skelett darüber sähe aus, als liefe noch etwas.
  if (String(fehler || '').trim()) return 'fehler'
  if (laedt) return 'laedt'
  return (Array.isArray(treffer) ? treffer.length : 0) ? 'treffer' : 'leer'
}

/** Steht die Personenfläche überhaupt da? (ruhe = nichts, auch keine
 *  Überschrift: im Listenmodus gibt es keinen Abschnitt „Personen“.) */
export function personenSichtbar(zustand) {
  return zustand === 'laedt' || zustand === 'fehler' || zustand === 'leer' || zustand === 'treffer'
}

/**
 * Die Abschnitte, wie der Zeichner sie zeigt — GENAU EINE „Personen“-
 * Überschrift, und im Listenmodus keine (Review R1, MUSS 1).
 *
 * Der Parameter heißt `personenZustand` (nicht `zustand`): in `ChatSuche.vue`
 * gibt es eine gleichnamige Ref, und ein Parameter, der eine äußere Variable
 * beschattet, ist die Quelle genau dieser Sorte Fehler (ein Aufruf mit
 * `zustand: undefined` fiel auf den ÄUSSEREN Wert zurück).
 *
 * Bisher stand die Statusfläche ohne Bedingung da (leere Überschrift) und bei
 * Treffern zusätzlich die Trefferliste (Überschrift doppelt). Hier ist beides
 * eine Entscheidung:
 *
 *   * Gespräche: nur mit Treffern.
 *   * Personen: Überschrift und Zeilen bei `treffer`; nur Überschrift bei
 *     `laedt`/`fehler`; GAR NICHTS bei `ruhe`.
 *   * Leerzustand („Nichts gefunden“): GENAU EIN Text, wenn es KEINEN
 *     Personentreffer, KEINEN Gesprächstreffer und KEINEN Personenfehler
 *     gibt. Er steht allein (Überschrift + Statusfläche) und trägt darum KEINE
 *     „Personen“-Überschrift — vorher standen hier zwei Leer-Texte
 *     nebeneinander („Niemand gefunden …“ und „Nichts gefunden“; CHAT-3c-2,
 *     SOLL c).
 *
 * CHAT-7a-UI-2 (Punkt 8): Eine Person, deren 1:1 schon unter „Gespräche“
 * steht, wird hier ausgeblendet (`personenOhneGespraech`). Das zählt auch für
 * die Entscheidungen darunter — sonst stünde „Personen“ mit einer leeren Liste
 * da oder der Leerzustand bliebe aus, obwohl sichtbar nichts übrig ist.
 *
 * @param {{ gespraeche?: Array<object>, zustand?: string, personen?: Array<object> }} lage
 */
export function suchAbschnitte({ gespraeche = [], zustand: personenZustand = 'ruhe', personen = [] } = {}) {
  const gespraechsListe = Array.isArray(gespraeche) ? gespraeche : []
  const personenRoh = Array.isArray(personen) ? personen : []
  const stand = personenZustand
  // Doppelte Treffer fallen weg — UNABHÄNGIG davon, ob gerade geladen wird
  // (die Gesprächstreffer stehen schon fest, die Personentreffer kommen nach).
  const personenListe = personenOhneGespraech(personenRoh, gespraechsListe)

  const leer = gespraechsListe.length === 0
    && stand === 'leer'
    && personenListe.length === 0
  // Der eine Leerzustand steht für sich — keine zweite Überschrift darüber,
  // kein zweiter Satz darunter. CHAT-7a-UI-2 (Punkt 8): Die Doppelprüfung kann
  // ALLE Personentreffer wegnehmen; dann steht keine leere „Personen“-Fläche da
  // (und bei leerem Rest auch keine leere Trefferfläche ohne Erklärung).
  const personenDa = (personenSichtbar(stand) && !leer)
    && !(stand === 'treffer' && personenListe.length === 0)
  return {
    /** Abschnitte der Gesprächstreffer (aus `gespraechsTreffer`). */
    gespraeche: gespraechsListe,
    /** Steht der Abschnitt „Personen“ da (genau einmal, nur bei Bedarf)? */
    personen: personenDa,
    /** Die Zeilen des Abschnitts Personen (leer bei laedt/fehler/leer). */
    personenZeilen: stand === 'treffer' ? personenListe : [],
    /** Steht die Statusfläche (Skelett/Fehler/Leer-Text) statt der Zeilen? */
    personenStatus: personenDa && (stand === 'laedt' || stand === 'fehler'),
    /** Steht der EINE Leerzustand da? */
    leer,
  }
}
