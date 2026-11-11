/**
 * A10-N3 (Punkt 6) — WO die Wochenansicht am Handy aufschlägt.
 *
 * BEFUND (Live-Sichtprüfung 10.11.): Die Woche startete bei 6:00, die Termine
 * der Gemeinde liegen abends (19:00–21:00) — man sah ein leeres Raster und
 * musste erst scrollen. Außerdem klebte die erste Stundenbeschriftung
 * („6:00“) ohne Abstand an der Kopfzeile.
 *
 * REGEL (Karte): automatisch zum FRÜHESTEN Termin der gezeigten Woche
 * scrollen; gibt es keinen, zur AKTUELLEN UHRZEIT (aber nie unter den
 * Arbeitsbeginn).
 *
 * A10-N4 (Punkt B): „früheste UHRZEIT“ heißt Uhrzeit — NICHT der
 * chronologisch erste Termin. Vorher galt der Termin mit dem kleinsten
 * Zeitstempel; lag der am Mittwoch um 09:00 und der früheste Tagesbeginn der
 * Woche am Sonntag um 8:00, sprang die Woche nach 8:00 statt nach 7:00
 * (Morgenandacht) — und umgekehrt bei einem späten Montagstermin zu tief.
 * Jetzt zählt das MINIMUM der Stunden über alle Termine der Woche.
 *
 * Warum eine eigene Datei ohne Vue/DOM: das Verhalten ist prüfbar, ohne einen
 * Browser zu starten (`tests/a10n3-kalender-feinschliff.test.mjs` und
 * `tests/a10n4-kalender-nacharbeit.test.mjs` rechnen es mit festen Daten
 * durch). Die Anwendung auf das DOM (`.ec-main` scrollen) steht in
 * `KronosCalendar.vue` und benutzt NUR diese Funktionen.
 *
 * @param {object} p
 * @param {Array} p.termine  Termine der Woche (Objekte mit `start`, `allDay`)
 * @param {Date}  p.jetzt    „jetzt“ (einspeisbar, damit der Test fest ist)
 * @param {number[]} p.stunden  sichtbare Stundenzahlen des Rasters (z. B. [0..23])
 * @returns {number} gewünschte Startstunde (ganzzahlig, innerhalb der Liste)
 */
export function startStunde({ termine = [], jetzt = new Date(), stunden = [] } = {}) {
  const liste = (Array.isArray(stunden) ? stunden : [])
    .map((s) => Number(s))
    .filter((s) => Number.isFinite(s))
    .sort((a, b) => a - b)
  if (!liste.length) return 0
  const min = liste[0]
  const max = liste[liste.length - 1]
  const klemmen = (h) => Math.min(max, Math.max(min, h))

  // Frühste UHRZEIT der Woche (nur Termine mit Uhrzeit — ein Ganztagstermin
  // hat keine Stunde, nach der man scrollen könnte).
  const stundenDerTermine = (Array.isArray(termine) ? termine : [])
    .filter((t) => t && !t.allDay)
    .map((t) => {
      const d = t.start instanceof Date ? t.start : new Date(t.start)
      return Number.isNaN(d.getTime()) ? null : d
    })
    .filter(Boolean)
    .map((d) => d.getHours())
  if (stundenDerTermine.length) {
    const fruehestes = Math.min(...stundenDerTermine)
    // Eine Stunde VOR dem frühesten Termin: der Termin steht dann nicht als
    // erste Zeile direkt an der Kopfzeile (die Kopfzeile verdeckt sonst
    // seinen Titel — der Befund „6:00 klebt an der Kopfzeile“).
    return klemmen(fruehestes - 1)
  }
  // Kein Termin: die aktuelle Uhrzeit, eine Stunde vorher als Vorlauf.
  const stunde = jetzt instanceof Date && !Number.isNaN(jetzt.getTime())
    ? jetzt.getHours() - 1
    : min
  return klemmen(Math.round(stunde))
}

/**
 * A10-N3 (Punkt 6, Review-Nacharbeit 3) — Welche Stunde im Zeitraster ganz
 * oben stehen soll, damit die „angeschnittene 6:00“ nicht an der Kopfzeile
 * klebt.
 *
 * Die Bibliothek setzt `.ec-time-grid .ec-slot { inset-block-start: -.5lh }`
 * — jede Stundenbeschriftung sitzt eine HALBE ZEILENHÖHE über ihrer Stunde,
 * damit sie vertikal mittig zur Stundenlinie steht. Die erste Beschriftung
 * ragt damit über den Inhalt hinaus; der Scroll-Container schneidet sie an
 * der Kopfzeile ab (Befund „6:00 klebt an der Kopfzeile“).
 *
 * Frühere Fassung setzte dafür `paddingBlockStart` auf den SCROLLER — dann
 * liefen die Stundenzeilen ÜBER der Tageskopfzeile durch (die Kopfzeile ist
 * dort `position: sticky`). Diese Fassung löst es OHNE Padding: der
 * Scroll-Versatz bekommt die halbe Zeilenhöhe als Zuschlag, sodass die erste
 * Beschriftung vollständig sichtbar wird. Der Scroll-Container selbst bleibt
 * unverändert.
 *
 * @param {number} zeilenHoehe  Höhe einer Beschriftungszeile in px (line-height)
 * @returns {number} Zuschlag in px (ganzzahlig, nie negativ)
 */
export function beschriftungsVersatz(zeilenHoehe) {
  const h = Number(zeilenHoehe)
  if (!Number.isFinite(h) || h <= 0) return 0
  return Math.round(h / 2)
}

/**
 * A10-N4 (Punkt B) — Höhe einer STUNDE im Zeitraster.
 *
 * BEFUND: Der Sprung landete bei ~7:15 statt beim Termin um 8:00. Ursache:
 * der Code rechnete `index * --ec-slot-height`, die Bibliothek setzt
 * `--ec-slot-height` aber je SLOT — und ein Slot ist 30 Minuten
 * (`slotDuration` = `00:30`, Standard). Beschriftet wird nur jeder ZWEITE
 * Slot (`--ec-slot-label-periodicity` = 2). Eine Stunde ist damit
 * `slotHeight × periodizität`, nicht `slotHeight`.
 *
 * Die Periodizität kommt vom DEMSELBEN Element wie die Slot-Höhe (im DOM
 * gelesen, s. `KronosCalendar.vue`) — nicht aus einer zweiten Annahme.
 * Fehlt sie (ältere Fassung der Bibliothek), gilt 1: dann ist die
 * Slot-Höhe bereits die Stundenhöhe.
 *
 * @param {number} slotHoehe  `--ec-slot-height` in px
 * @param {number} periodizitaet  `--ec-slot-label-periodicity` (Schritte je Stunde)
 * @returns {number} Höhe einer Stunde in px (0, wenn nichts gemessen wurde)
 */
export function stundenHoehe(slotHoehe, periodizitaet) {
  const h = Number.parseFloat(slotHoehe)
  if (!Number.isFinite(h) || h <= 0) return 0
  const p = Number.parseFloat(periodizitaet)
  const schritte = Number.isFinite(p) && p > 0 ? p : 1
  return h * schritte
}

/**
 * A10-N4 (Punkt B) — Der Scroll-Versatz (scrollTop) für eine Zielstunde.
 *
 * Vorrang hat der OFFSET der Ziel-Beschriftung im Raster (`offsetTop`): er
 * ist die Wahrheit der Bibliothek, egal wie Slots, Periodizität oder
 * Kopfzeilen gerade gerechnet werden. Erst wenn keine Beschriftung gefunden
 * wurde, wird aus der Stundenhöhe gerechnet.
 *
 * @param {object} p
 * @param {number} p.offsetTop  `offsetTop` der Ziel-Beschriftung (px) oder null
 * @param {number} p.index      Index der Zielstunde in den sichtbaren Stunden
 * @param {number} p.stundenHoehe  Höhe einer Stunde in px
 * @param {number} p.versatz    Zuschlag für die angeschnittene Beschriftung
 * @returns {number} scrollTop (ganzzahlig, nie negativ)
 */
export function scrollZiel({ offsetTop = null, index = 0, stundenHoehe: stundenPx = 0, versatz = 0 } = {}) {
  // `null`/`undefined` = KEIN Messwert. `Number(null)` wäre 0 — das würde als
  // echter Offset durchgehen und den Sprung auf 0 setzen (Befund im Test).
  const gemessen = offsetTop !== null && offsetTop !== undefined && offsetTop !== ''
  const top = gemessen ? Number(offsetTop) : Number.NaN
  const roh = Number.isFinite(top) && top >= 0
    ? top
    : (Number(index) || 0) * (Number(stundenPx) || 0)
  const abzug = Number(versatz) || 0
  return Math.max(0, Math.round(roh - abzug))
}

/**
 * A10-N4 (Punkt C) — Darf der einmalige Wochen-Sprung jetzt laufen?
 *
 * BEFUND: Der Sprung hing an einem Flag, das beim ersten gerenderten Frame
 * geschlossen wurde (`datesSet` öffnet, rAF schließt). Bei langsamer Quelle
 * war zu diesem Zeitpunkt NOCH KEIN Termin im Raster — die Woche blieb bei
 * „jetzt − 1 h“ stehen, obwohl die Termine Millisekunden später kamen.
 *
 * REGEL (Karte): das Flag schließt erst, wenn
 *   - Termine gefunden wurden (dann ist das Ziel belastbar), ODER
 *   - die Quelle fertig geladen hat (`eventSources`-Callback, auch bei 0
 *     Terminen — dann gilt „jetzt − 1 h“ zu Recht), ODER
 *   - der Nutzer selbst gescrollt hat (sein Wille gewinnt).
 *
 * @param {object} p
 * @param {boolean} p.offen      ist der Sprung noch zu erledigen?
 * @param {boolean} p.termine    stehen Termine im Raster?
 * @param {boolean} p.geladen    hat die Quelle fertig gemeldet?
 * @param {boolean} p.nutzerScroll  hat der Nutzer gescrollt?
 * @returns {'springen'|'warten'|'schliessen'} was jetzt zu tun ist
 */
export function sprungEntscheidung({ offen, termine, geladen, nutzerScroll } = {}) {
  if (!offen) return 'schliessen'
  if (nutzerScroll) return 'schliessen'
  if (termine) return 'springen'
  if (geladen) return 'springen'
  return 'warten'
}

/**
 * A10-N3 (Punkt 6) — Der Text im Terminblock der ENGEN Lage (Handy-Woche).
 *
 * In einer ~50-px-Spalte ist für Titel + Zeitraum kein Platz: gemessen wurde
 * aus „19:30–21:30“ ein „19:…“ (Ellipse mitten in der Uhrzeit). Der Block
 * trägt deshalb im Zeitraster der engen Lage nur die ANFANGSZEIT („19:30“);
 * der Zeitraum und der Titel stehen im `title`/`aria-label` und in der
 * Tagesliste unter dem Mini-Monat.
 *
 * @param {string} text  z. B. „19:30–21:30“ (aus `chipText.zeitBlockText`)
 * @returns {string}     z. B. „19:30“ — unverändert, wenn kein Bereich
 */
export function engeZeit(text) {
  const t = String(text ?? '').trim()
  if (!t) return ''
  // Trenner der Bibliothek: Halbgeviertstrich, Gedankenstrich oder „-“.
  const treffer = /^(\d{1,2}:\d{2})\s*[–—-]/.exec(t)
  return treffer ? treffer[1] : t
}
