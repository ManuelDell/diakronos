/**
 * UX2a — Der Rückgängig-Stapel (reine Logik, ohne Browser und ohne Vue).
 *
 * WARUM EIN STAPEL UND NICHT EIN EINZELNER PLATZ
 * Sobald eine Aktion sofort ausgeführt wird statt nachzufragen (Prinzip I2,
 * „Rückgängig statt Rückfrage“), muss der Nutzer sie zurücknehmen können —
 * auch wenn er in der Zwischenzeit weiterarbeitet. Zwei kurz nacheinander
 * entfernte Zeilen müssen BEIDE zurückholbar sein; der Stapel nimmt sie in
 * umgekehrter Reihenfolge zurück (die zuletzt ausgeführte Aktion zuerst).
 *
 * DIE ENTSCHEIDUNGEN DIESER KARTE (UX2a)
 *  1. Eine neue Aktion wird SOFORT ausgeführt (der Aufrufer führt sie aus und
 *     meldet sie hier nur an). Es gibt keinen Vorher-Zustand zu sichern —
 *     `rueckgaengig()` ruft die vom Aufrufer mitgegebene Funktion, die die
 *     Gegenrichtung ausführt (z. B. POST des Papierkorbs rückgängig).
 *  2. Gestapelt werden höchstens GRENZE Einträge. Ältere fallen heraus und
 *     sind NICHT mehr zurückholbar — genau wie ihre Meldung verschwindet.
 *  3. `rueckgaengig()` gibt es zweimal: `zuruecknehmen()` (nimmt den obersten)
 *     und `zuruecknehmen(id)` (nimmt einen bestimmten, weil der Nutzer auf die
 *     Meldung GENAU DIESER Aktion geklickt hat).
 *  4. Je Eintrag läuft eine Frist: ABlaufMS nach dem Anmelden ist die Aktion
 *     nicht mehr zurückholbar. Der Timer selbst lebt in `useRueckgaengig.js`
 *     (dort gibt es `setTimeout`); diese Datei rechnet nur mit Zeiten, die der
 *     Aufrufer übergibt — dadurch ist sie ohne Browser prüfbar.
 *  5. Eine Rücknahme wird nur EINMAL ausgeführt: danach ist der Eintrag weg.
 *     Ein liegengebliebener Meldungs-Knopf oder ein zweites Strg+Z darf keine
 *     zweite Gegenbuchung auslösen.
 *  6. Fehler werden NICHT verschluckt: `zuruecknehmen()` wirft weiter, damit
 *     der Aufrufer eine Meldung zeigen kann („Das hat nicht geklappt …“).
 *  7. UX2a2b: Hover/Fokus auf der Meldung halten die Frist WIRKLICH an —
 *     nicht nur die Anzeige. `pausieren(id)` merkt sich, wann (und mit
 *     welcher Restzeit) die Frist angehalten wurde, `fortsetzen(id)` schiebt
 *     das Ablaufziel um die Standzeit nach hinten (gedeckelt, siehe
 *     `HALTE_DECKEL_MS`). Weder Anhalten noch Fortsetzen geht über `jetzt`
 *     hinaus — eine liegengebliebene Bremse hebt die Frist nie auf.
 */

/** Standardfrist: die Meldung bietet 8 s lang „Rückgängig“ an. */
export const ABlaufMS = 8000

/**
 * UX2a2b: So lange darf Hover/Fokus die Frist höchstens anhalten (ms).
 *
 * Ohne Deckel hielte ein liegengelassener Zeiger eine Aktion unbegrenzt
 * zurückholbar; nach einem Tab-Schlaf (eingefrorene Takt-Uhr) stünde die
 * Meldung sonst Stunden später noch voller Frist da. Der Deckel wird
 * `fortsetzen` mitgegeben (die Verbindung nimmt ihn aus
 * `HALTE_ZUSATZ_MS` in `useToast.js` — EINE Zahl für Anzeige und Frist).
 */
export const HALTE_DECKEL_MS = 20000

/** Höchstens fünf Aktionen gleichzeitig zurückholbar. */
export const GRENZE = 5

/**
 * Ein Eintrag ist nur gültig, wenn er eine Beschreibung (für die Meldung und
 * für Hilfstechnik) und eine ausführbare Rücknahme hat. Eine fehlende
 * Rücknahme wäre eine Meldung, die nichts tut — das ist ein Programmierfehler
 * und wird hier abgewiesen, nicht still hingenommen.
 */
function pruefeEintrag(beschreibung, rueckgaengigFn) {
  const text = typeof beschreibung === 'string' ? beschreibung.trim() : ''
  if (!text) throw new TypeError('Rückgängig: Beschreibung fehlt')
  if (typeof rueckgaengigFn !== 'function') {
    throw new TypeError(`Rückgängig: Rücknahme für „${text}“ ist keine Funktion`)
  }
  return text
}

/**
 * Der Stapel. Eine Instanz gehört zu einer Anwendung (eine für die ganze
 * Sitzung, siehe `useRueckgaengig.js`); für Tests lässt sich eine eigene
 * bauen.
 */
export class RueckgaengigStapel {
  /**
   * @param {{ grenze?: number, ablaufMs?: number }} [vorgaben]
   */
  constructor(vorgaben = {}) {
    this.grenze = Number.isInteger(vorgaben.grenze) && vorgaben.grenze > 0
      ? vorgaben.grenze
      : GRENZE
    this.ablaufMs = Number.isFinite(vorgaben.ablaufMs) && vorgaben.ablaufMs > 0
      ? vorgaben.ablaufMs
      : ABlaufMS
    /** Älteste zuerst, oberster Eintrag = zuletzt ausgeführt. */
    this.eintraege = []
    this.naechsteId = 1
    /** Wird bei jeder Änderung gerufen (auch Prüf-Takt: siehe `pruefen`). */
    this.beobachter = null
    /**
     * UX2a2 (F4): Der Vorgang, der gerade angemeldet hat. Strg+Z gehört dem
     * Vorgang, der den Zuhörer angehängt hat — eine Taste aus einem ALTEN
     * Zustand darf keine Aktion eines späteren Vorgangs zurücknehmen.
     */
    this._vorgang = null
    /** Wie viele Vorgänge am Stapel hören (Anmelden/Zurücknehmen/Abmelden). */
    this.hoerer = 0
    /** Alle, die beim Schließen einer Meldung gefragt werden (F3/F4/F5). */
    this.schliessBeobachter = []
  }

  /** Auf Änderungen hören (eine Zuhörer-Funktion, ersetzt die alte). */
  beobachten(fn) {
    this.beobachter = typeof fn === 'function' ? fn : null
    return () => { if (this.beobachter === fn) this.beobachter = null }
  }

  _melden() {
    if (this.beobachter) this.beobachter()
  }

  /**
   * Eine sofort ausgeführte Aktion anmelden.
   *
   * @param {string} beschreibung  Was passiert ist („Aus Gruppe entfernt“) —
   *                               steht so in der Meldung.
   * @param {Function} rueckgaengigFn  Führt die Gegenrichtung aus (darf async).
   * @param {{ jetzt?: number }} [optionen]
   * @returns {{ id: number, beschreibung: string, ablauf: number }}
   *          `ablauf` ist der Zeitpunkt, ab dem die Aktion nicht mehr
   *          zurückholbar ist.
   */
  registrieren(beschreibung, rueckgaengigFn, optionen = {}) {
    const text = pruefeEintrag(beschreibung, rueckgaengigFn)
    const jetzt = Number.isFinite(optionen.jetzt) ? optionen.jetzt : 0
    // UX2a2 (F4): Der EINTRAG merkt sich, wer ihn angemeldet hat. Nur dieser
    // Vorgang (und wer ausdrücklich benannt wird) darf ihn zurücknehmen —
    // Strg+Z aus einem alten Zustand trifft damit keine neuere Aktion.
    const vorgang = optionen.vorgang || this._vorgang
    const eintrag = {
      id: this.naechsteId++,
      beschreibung: text,
      rueckgaengigFn,
      ablauf: jetzt + this.ablaufMs,
      erlaubt: [vorgang],
      // UX2a2b: Anhalten durch Hover/Fokus (siehe `pausieren`/`fortsetzen`).
      haelt: false,
      angehaltenSeit: 0,
      angehaltenGesamt: 0,
      angehaltenBei: null,
    }
    // UX2a2 (F3/F4): Eine NEUE Aktion hält den Takt an, bis sie abgelaufen
    // ist — auch wenn der Stapel gerade leer war (`useToast` steht dann noch).
    if (optionen.neu) this._seitNeu = Number.isFinite(optionen.jetzt) ? optionen.jetzt : 0
    this.eintraege.push(eintrag)
    // Ältere fallen heraus — ihre Meldung verschwindet (der Aufrufer räumt
    // sie über `beobachten` ab), zurückholbar sind sie nicht mehr.
    while (this.eintraege.length > this.grenze) this.eintraege.shift()
    this._melden()
    return { id: eintrag.id, beschreibung: eintrag.beschreibung, ablauf: eintrag.ablauf }
  }

  /** Der oberste (zuletzt angemeldete) Eintrag oder `null`. */
  oberster() {
    return this.eintraege.length ? this.eintraege[this.eintraege.length - 1] : null
  }

  /** Alle noch offenen Einträge (älteste zuerst) — für Prüfungen und Meldungen. */
  alle() {
    return this.eintraege.slice()
  }

  /** Wie viele Aktionen gerade zurückholbar sind. */
  get laenge() {
    return this.eintraege.length
  }

  /**
   * UX2a2 (F4): Ist der Strg+Z-Zuhörer für DIESEN Vorgang noch angemeldet?
   *
   * Die Verbindung (`useRueckgaengig.js`) meldet den Zuhörer beim ersten
   * `useRueckgaengig()` an und nimmt ihn erst ab, wenn der letzte Vorgang
   * `abmelden()` gerufen hat — nicht schon, wenn der Stapel kurz leer ist.
   * Sonst bliebe ein Zuhörer aus einem alten Seitenstand am Fenster hängen
   * und Strg+Z auf der NEUEN Seite nähme still eine Aktion zurück.
   */
  hoert(kennung) {
    return this._vorgang !== null && this._vorgang === kennung && this.hoerer > 0
  }

  /**
   * UX2a2 (F4/F3): Das Schließen einer Meldung bekannt geben — Esc, Klick auf
   * „Rückgängig“ und Ablauf rufen das. Die Verbindung nutzt es, um den Fokus
   * zu retten (F3) und die Position der Meldungen nachzuziehen (F5).
   *
   * @param {{ grund: string, id: string|null }} ereignis
   */
  geschlossen(ereignis) {
    for (const fn of this.schliessBeobachter.slice()) {
      try { fn(ereignis || {}) } catch { /* ein Beobachter darf den anderen nicht blockieren */ }
    }
  }

  /** Auf Schließen von Meldungen hören; Rückgabe meldet wieder ab. */
  aufSchliessen(fn) {
    if (typeof fn !== 'function') return () => {}
    this.schliessBeobachter.push(fn)
    return () => {
      this.schliessBeobachter = this.schliessBeobachter.filter(f => f !== fn)
    }
  }

  /**
   * Abgelaufene Einträge entfernen.
   *
   * @param {number} jetzt
   * @returns {object[]} die entfernten Einträge
   */
  pruefen(jetzt) {
    const zeit = Number.isFinite(jetzt) ? jetzt : 0
    const behalten = []
    const abgelaufen = []
    for (const eintrag of this.eintraege) {
      // UX2a2b: Ein angehaltener Eintrag läuft nicht ab — die Meldung steht
      // (Hover/Fokus), der Nutzer will den Knopf treffen, nicht die Uhr.
      if (!eintrag.haelt && zeit >= eintrag.ablauf) abgelaufen.push(eintrag)
      else behalten.push(eintrag)
    }
    if (abgelaufen.length) {
      this.eintraege = behalten
      this._melden()
    }
    return abgelaufen
  }

  /**
   * UX2a2b: Die Frist eines Eintrags anhalten (Hover/Fokus auf der Meldung).
   *
   * Mehrfaches Anhalten ändert nichts: die Anhaltezeitpunkte liegen ohnehin
   * nicht in der Standzeit (zwischen zwei Anrufen läuft keine Uhr). Ein
   * bereits abgelaufener Eintrag wird NICHT wiederbelebt — er fällt beim
   * nächsten `pruefen` heraus, und ein späteres `fortsetzen` findet ihn
   * nicht mehr.
   *
   * @param {number} id
   * @param {number} jetzt
   * @returns {boolean} true, wenn der Eintrag (weiterhin) angehalten ist
   */
  pausieren(id, jetzt) {
    const eintrag = this.eintraege.find(e => e.id === id)
    if (!eintrag) return false
    const zeit = Number.isFinite(jetzt) ? jetzt : 0
    if (!eintrag.haelt) {
      eintrag.haelt = true
      eintrag.angehaltenSeit = zeit
      eintrag.angehaltenGesamt = 0
      eintrag.angehaltenBei = jetzt
    } else if (Number.isFinite(jetzt)) {
      // Schon angehalten: den Stand nachführen, damit `fortsetzen` ohne
      // Uhrzeit weiterrechnen kann.
      eintrag.angehaltenBei = jetzt
    }
    return true
  }

  /**
   * UX2a2b: Die Frist wieder anlaufen lassen — um die Standzeit verlängert.
   *
   * Die Restzeit bleibt also erhalten (sie wird nicht neu geschenkt), und das
   * neue Ablaufziel überschreitet `jetzt + deckelMs` nie: ein liegengelassener
   * Zeiger darf die Aktion nicht unbegrenzt zurückholbar halten.
   *
   * @param {number} id
   * @param {{ jetzt?: number, deckelMs?: number }} [optionen]
   * @returns {object|null} der fortgesetzte Eintrag oder `null`
   */
  fortsetzen(id, optionen = {}) {
    const eintrag = this.eintraege.find(e => e.id === id)
    if (!eintrag || !eintrag.haelt) return null
    const jetzt = Number.isFinite(optionen.jetzt) ? optionen.jetzt : eintrag.angehaltenBei
    const standzeit = Math.max(0, jetzt - eintrag.angehaltenSeit)
    const gewachsen = eintrag.ablauf + standzeit
    const deckel = Number.isFinite(optionen.deckelMs) && optionen.deckelMs >= 0
      ? jetzt + optionen.deckelMs
      : gewachsen
    eintrag.ablauf = Math.min(gewachsen, deckel)
    eintrag.haelt = false
    eintrag.angehaltenSeit = 0
    eintrag.angehaltenGesamt = (eintrag.angehaltenGesamt || 0) + standzeit
    eintrag.angehaltenBei = null
    this._melden()
    return eintrag
  }

  /**
   * Eine Aktion zurücknehmen.
   *
   * Ohne Argument: den obersten Eintrag (Strg+Z). Mit `id`: genau diesen
   * (Klick auf die Meldung dieser Aktion). Der Eintrag wird VOR dem Aufruf
   * entfernt — eine Rücknahme läuft höchstens einmal, auch wenn die
   * Rücknahme-Funktion selbst Fehler wirft oder asynchron ist.
   *
   * @param {(number|{jetzt?: number})} [idOderOptionen]  Eine Zahl = Id; ein
   *        Objekt = nur Optionen (dann oberster Eintrag).
   * @param {{ jetzt?: number }} [optionen]
   * @returns {Promise<object|null>} der zurückgenommene Eintrag oder `null`,
   *          wenn es nichts (mehr) zurückzunehmen gibt.
   */
  async zuruecknehmen(idOderOptionen, optionen = {}) {
    const istId = typeof idOderOptionen === 'number'
    const id = istId ? idOderOptionen : undefined
    const vorgaben = istId ? optionen : (idOderOptionen || {})
    const jetzt = Number.isFinite(vorgaben.jetzt) ? vorgaben.jetzt : 0
    // UX2a2 (F4): Wer nimmt zurück? Nur DER Vorgang, der den Eintrag auch
    // angemeldet hat (`erlaubt`), oder ein ausdrücklich erlaubter Aufruf
    // (`kraft`, z. B. die Meldung DIESER Aktion). Damit kann ein Tastendruck
    // aus einem ALTEN Zustand keine neuere Aktion zurücknehmen.
    // F4: Ohne ausdrückliche Angabe gilt der angemeldete Vorgang als
    // Berechtigter, wenn es einen gibt; ist niemand angemeldet, gelten die
    // alten Regeln (Aufrufe aus Bausteinen und Prüfungen ohne Verbindung).
    const kraft = vorgaben.kraft === undefined ? this._vorgang : vorgaben.kraft
    this.pruefen(jetzt)
    const index = typeof id === 'number'
      ? this.eintraege.findIndex(e => e.id === id)
      : this.eintraege.length - 1
    if (index < 0) return null
    let eintrag = this.eintraege[index]
    if (kraft && !eintrag.erlaubt.includes(kraft)) {
      // Durchreichen: die nächste Berechtigung in der Kette darf es versuchen,
      // die folgende darf es nicht mehr. Genau EIN Durchreichen je Kette.
      if (kraft.kette && kraft.kette.length) {
        return this.zuruecknehmen(id ?? undefined, {
          ...vorgaben, kraft: { ...kraft, kette: kraft.kette.slice(1) },
        })
      }
      return null
    }
    if (!kraft && !eintrag.erlaubt.includes(this._vorgang)) {
      // Strg+Z aus einem alten Zustand (die Meldung ist längst zu): nicht
      // die Aktion eines SPÄTEREN Vorgangs zurücknehmen.
      return null
    }
    const [entfernt] = this.eintraege.splice(index, 1)
    eintrag = entfernt
    this._melden()
    await eintrag.rueckgaengigFn()
    return eintrag
  }

  /**
   * UX2a2 (F4): Eine Rückgängig-Meldung wurde geschlossen (Esc), ohne dass
   * zurückgenommen wurde. Ihr Eintrag verlässt den Stapel — ein späteres
   * Strg+Z darf GENAU DIESE Aktion nicht mehr treffen (die Meldung ist weg,
   * der Nutzer sieht nicht mehr, was er zurücknimmt).
   *
   * @param {number} id
   * @returns {boolean} true, wenn der Eintrag entfernt wurde
   */
  verwerfen(id) {
    const index = this.eintraege.findIndex(e => e.id === id)
    if (index < 0) return false
    this.eintraege.splice(index, 1)
    this._melden()
    return true
  }

  /** Alles vergessen (z. B. beim Abmelden) — führt NICHTS aus. */
  leeren() {
    if (!this.eintraege.length) return
    this.eintraege = []
    this._melden()
  }
}
