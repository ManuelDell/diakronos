/**
 * FE-ABBAU — Seiten-Abbau, der auch nach einem ROTEN `assert` läuft.
 *
 * Warum diese Datei (Folge von FE-HAENGER, Commit 4ce2d6b2): In den
 * Nachrichten-Testdateien stand `s.abbaum()` als LETZTE Zeile im Test. Warf
 * eine Zusage vorher, wurde die Seite nie abgebaut — `pages/Nachrichten.vue`
 * hält aber einen Takt (`taktGeber`, 10 s, plant sich neu). Der offene Timer
 * hielt die Ereignisschleife am Leben, `node --test` wartete auf seinen
 * Kindprozess und der FE-Teststep im Docker-Build hing 1–6 h (TOOL-404,
 * UX-K2, Sammel 22).
 *
 * Die Lösung ist winzig und in jeder Datei gleich: JEDE Montage meldet ihren
 * `abbaum` hier an, und EIN `test.afterEach` baut alles ab, was noch steht.
 * `node:test` ruft `afterEach` auch dann auf, wenn der Test geworfen hat.
 *
 *   const seitenAbbau = new SeitenAbbau()   // EINMAL je Datei, oben
 *   test.afterEach(() => seitenAbbau.alle())
 *   // … in mounten():
 *   seitenAbbau.anmelden(abbaum)
 *
 * `abbaum()` bleibt im Test stehen (idempotent) — die Zusagen der Tests
 * bleiben unverändert.
 */
export class SeitenAbbau {
  constructor() {
    /** Die noch offenen Abbauten — jeder baut GENAU EINMAL ab. */
    this.offen = new Set()
  }

  /**
   * Eine Montage anmelden. Gibt denselben `ab` zurück, damit die Zeile in
   * `mounten()` eine bleibt: `return abbaum: seitenAbbau.anmelden(ab)`.
   */
  anmelden(ab) {
    if (typeof ab !== 'function') return ab
    // Der Abbau meldet sich selbst ab — ob er nun vom Test kommt oder von
    // `alle()`; ein zweiter Aufruf tut nichts.
    const einmal = () => {
      if (!this.offen.delete(einmal)) return
      try { ab() } catch { /* Aufräumen darf nie werfen */ }
    }
    this.offen.add(einmal)
    return einmal
  }

  /** ALLE offenen Seiten abbauen (aus `test.afterEach`). */
  alle() {
    for (const ab of [...this.offen]) ab()
    this.offen.clear()
  }

  /** Wie viele Seiten gerade offen sind — für Diagnose und Mutationsprobe. */
  get anzahl() {
    return this.offen.size
  }
}
