/**
 * fensterstapel — reine Buchführung für „Zurück schließt das Fenster“
 * (OP-HANDY-7). Ohne Vue und ohne DOM, damit sie sich ohne Browser prüfen
 * lässt; `useZurueckSchliesst` verbindet sie mit `history`/`popstate`.
 *
 * Ein Fenster = eine Marke auf einem Stapel. Zurück schließt immer das
 * oberste Fenster (das zuletzt geöffnete). Wird ein Fenster anders beendet
 * (✕, Esc, Übernehmen), muss sein History-Eintrag verbraucht werden —
 * sonst bliebe eine Leiche in der History und „Zurück“ bräuchte zwei Tipps.
 */

export class Fensterstapel {
  constructor() {
    this._stapel = []
    this._zaehler = 0
  }

  /** Ein Fenster öffnen → neue Marke. */
  oeffnen() {
    const marke = ++this._zaehler
    this._stapel.push(marke)
    return marke
  }

  /**
   * Marke des obersten Fensters, ohne es zu entfernen (null = Stapel leer).
   * „Zurück“ darf nur DIESES Fenster schließen (P2-3b W1) — die Marke wird
   * vor dem Abräumen erfragt, damit der Aufrufer den richtigen Schließer ruft.
   */
  oberste() {
    return this._stapel.length ? this._stapel[this._stapel.length - 1] : null
  }

  /**
   * Der Browser hat „Zurück“ gemeldet. Das oberste Fenster schließen.
   * Ist der Stapel leer, gehört der Sprung nicht uns (→ nicht eingreifen).
   */
  zurueckGehen() {
    if (this._stapel.length === 0) return { schliessen: false }
    this._stapel.pop()
    return { schliessen: true }
  }

  /**
   * Ein Fenster wurde anders als über „Zurück“ beendet. Seinen Eintrag aus
   * dem Stapel nehmen und den eigenen History-Eintrag verbrauchen.
   */
  schliessen(marke) {
    if (marke === null || marke === undefined) return { verbrauchen: false }
    const index = this._stapel.lastIndexOf(marke)
    if (index < 0) return { verbrauchen: false }
    this._stapel.splice(index, 1)
    return { verbrauchen: true }
  }

  /** Liegt diese Marke noch im Stapel? */
  enthaelt(marke) {
    return this._stapel.includes(marke)
  }

  /**
   * P3-4 (Restpunkt 11): Ein Fenster, dessen Schließen VERWEIGERT wurde, wieder
   * als offen führen. „Zurück" hatte seine Marke bereits abgeräumt; das
   * Fenster ist aber weiterhin sichtbar und muss deshalb wieder einen eigenen
   * History-Eintrag bekommen. Die alten Marken davor bleiben erhalten.
   */
  wiederOeffnen(marke) {
    if (marke === null || marke === undefined) return false
    if (this._stapel.includes(marke)) return true
    this._stapel.push(marke)
    return true
  }

  /** Zahl der offenen Fenster (für Tests). */
  tiefe() {
    return this._stapel.length
  }
}

export default Fensterstapel
