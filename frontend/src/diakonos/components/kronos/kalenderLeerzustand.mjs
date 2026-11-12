/**
 * MT-5 — Leerzustand der Kalender-LISTE.
 *
 * BEFUND (Manuel, Live-Test 11.11.): In der Ansicht „Liste“ stand ohne
 * Termine der ENGLISCHE Bibliothekstext der Terminbibliothek („No events“).
 * Er kommt aus dem Paket `@event-calendar/build` — die Bibliothek führt ihre
 * Texte fest im Bundle, eine Übersetzungstabelle gibt es dort nicht. Der Text
 * wird deshalb über die eine Stelle überschrieben, die die Bibliothek dafür
 * kennt (`noEventsContent`), und mit dem eigenen Leerzustand (DkEmpty)
 * gefüllt.
 *
 * Diese Datei ist REINE RECHNUNG ohne Browser: sie sagt, WAS in den
 * Leerzustand gehört (Titel, Text, Symbol). Gebaut wird der Inhalt im
 * Kalender-Baustein mit der ECHTEN Komponente `components/ui/DkEmpty.vue`
 * (`h(DkEmpty, {…})`) — nur so greifen ihre Regeln; eine selbstgeschriebene
 * HTML-Zeichenkette trägt deren `scoped`-Attribute nicht (Review 11.11.).
 * Geprüft in `tests/mt5-kalender-leerzustand.test.mjs`.
 *
 * GROUND TRUTH (Bundle 5.18.0, `package.json` → `@event-calendar/build`):
 *   Vorgabe der Bibliothek:  noEventsContent: `No events` (Zeichenkette)
 *   Gelesen wird sie NUR vom Listen-Plugin (listDay/listWeek/listMonth/
 *   listYear) — die Raster-Ansichten (Tag/Woche/Monat) haben keinen eigenen
 *   Leerzustand, dort steht ein leeres Raster. Der Text gilt deshalb für
 *   jede Ansicht gleich, die ihn zeigt (kein Unterschied nach Lage).
 *   Im Browser geprüft (11.11.): der Ansichtstyp kommt hier als `listMonth`
 *   an — das ist die Ansicht der Auswahl „Liste“ (`mobilAnsicht.mjs`).
 *
 * Die Form des Leerzustands ist die der App (Prinzip I5 „jeder Zustand
 * gestaltet“): Symbol, Titel, erklärender Satz, KEIN Knopf — die Handlung
 * „Termin anlegen“ steht als Primärknopf der Ansicht bereits in der
 * Kopfzeile (Prinzip S1 „genau ein Primärknopf je Ansicht“).
 */

/** Der englische Bibliothekstext, den dieser Baustein ersetzt. */
export const ENGLISCHER_LEERTEXT = 'No events'

/** Symbol des Leerzustands (wie `DkEmpty` es als Vorgabe trägt). */
export const LEER_SYMBOL = '—'

/** Titelzeile des Leerzustands (Begriff der App: „Termin“, nie „Event“). */
export const LEER_TITEL = 'Keine Termine'

/** Erklärender Satz. */
export const LEER_TEXT = 'In diesem Zeitraum ist nichts eingetragen.'

/** Die Angaben, die dem Baustein `DkEmpty` untergelegt werden. */
export function leerzustandInhalt() {
  return { icon: LEER_SYMBOL, title: LEER_TITEL, text: LEER_TEXT }
}
