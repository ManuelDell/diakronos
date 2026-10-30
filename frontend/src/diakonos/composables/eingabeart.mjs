/**
 * FIX-6 — EIN gemeinsames Kriterium für Geräte- und Zeigegerätelagen
 * (Befund DMB-d446e449ba22; Operator-Entscheidung vom 27.10.).
 *
 * Befund: Ein Touch-Gerät mit Desktop-Breite (Notebook mit Touchscreen,
 * Convertible, Tablet im Querformat, Viewport 1410×755) bekam mobile
 * Bedienelemente: der Bearbeiten-Knopf der Startseite wurde zur breiten
 * Leiste, „Moderation“ verlor seine Beschriftung, im Kalender verschwanden
 * Jahreszahl und Ressourcenplan, die Inhaltsseite bekam 80 px Fußabstand für
 * eine untere Leiste, die dort gar nicht erscheint.
 *
 * Die erste Fassung dieser Karte hing ALLES an „Breite UND feiner Zeiger“.
 * Der Operator hat das getrennt — zwei Fragen, zwei Kriterien:
 *
 *   1. LAYOUT — Seitenleiste oder Mobil-Layout (einspaltig, untere Leiste,
 *      Desktop-Kopfzeile ohne Jahreszahl/Ressourcenplan): NUR nach der Breite.
 *
 *        mobilLayout = Breite <= 720 px
 *
 *      Ein schmales Fenster MIT Maus bekommt also Mobil-Layout samt unterer
 *      Leiste (Navigation!); ein Touch-Laptop mit 1410 px bekommt Desktop.
 *
 *   2. TOUCH-ANPASSUNGEN — größere Tippziele (OP-HANDY-26), 16-px-Eingabe-
 *      schrift gegen den iOS-Zoom (OP-HANDY-14), Wisch-/Touch-Hinweise: NUR
 *      nach dem Zeigegerät, unabhängig von der Breite.
 *
 *        groberZeiger = (pointer: coarse)
 *
 *      Ein iPad im Querformat (1024 px) behält damit 16 px und Tippziele,
 *      ein Desktop mit Maus bekommt sie nie.
 *
 * Nie Kriterium ist die bloße Touch-FÄHIGKEIT (`(any-pointer: coarse)`,
 * `maxTouchPoints`, `ontouchstart`): ein Touch-Laptop mit Maus ist ein
 * Desktop. `(any-pointer: fine)` ebenso wenig — daraus folgte in der ersten
 * Fassung, dass ein Handy mit angeschlossener Maus kein Mobil-Layout mehr
 * bekäme.
 *
 * FIX-6c: Diese Datei hält nur noch die ZAHL. Die früheren Helfer
 * (`useEingabeart`, `lageImBrowser`, `istMobilLayoutImBrowser`, `istTouch`,
 * `GROBER_ZEIGER_ABFRAGE`) hat keine Komponente importiert — nur die Tests
 * selbst; das lebende CSS liest seine Bedingungen aus `index.css`. Sie sind
 * entfernt, damit hier keine Schnittstelle steht, die niemand benutzt.
 *
 * Wer eine BREITEN-Entscheidung im Skript braucht, nimmt `MOBIL_GRENZE_PX`
 * (so macht es `PrTabelle.vue`, und über `HANDY_HINWEIS_PX`
 * auch `composables/handyHinweis.mjs`; `adressbuch.mjs` ebenso). Eine
 * `matchMedia`-Zeichenkette stand hier früher als `SCHMAL_ABFRAGE` — auch sie
 * hatte keinen Leser (das CSS schreibt seine Bedingung selbst) und ist weg.
 *
 * Wer eine ZEIGER-Entscheidung braucht, schreibt die Bedingung ins CSS
 * (`(pointer: coarse)`) — hier gibt es dafür bewusst keinen zweiten Ort.
 *
 * Dieselben Bedingungen stehen als CSS in `index.css`
 * («FIX-6 · Layout nur nach Breite» / «FIX-6 · Touch nur bei grobem Zeiger»)
 * und in den Komponenten; Stylesheets können nicht importieren. Beide
 * Fassungen müssen gleich bleiben — der Node-Test
 * `tests/fix6-zeigegeraet.test.mjs` prüft genau das, ebenso der Wächter
 * `tests/fix6-keine-zeiger-syntax.test.mjs` (kein `not (... or ...)`, weil
 * Safari < 16.4 das nicht kann) und `tests/fix6c-toter-code.test.mjs`
 * (kein zweiter Ort für die Zahl 720, keine toten Exporte).
 *
 * Diese Datei kommt ohne laufende Vue-Instanz aus, damit sie in Node prüfbar
 * ist (kein `vue`-Import).
 */

/**
 * Grenze in Pixeln, bis zu der die App das Mobil-Layout nutzt.
 * Die EINE Mobilgrenze der App. Deckungsgleich mit
 * `@media (max-width: 720px)` in `index.css` (`.dk-app` einspaltig,
 * Seitenleiste aus, untere Leiste an).
 *
 * Abgeleitet davon: `HANDY_HINWEIS_PX` (`composables/handyHinweis.mjs`) und
 * `kartenAnsicht` (`composables/adressbuch.mjs`).
 */
export const MOBIL_GRENZE_PX = 720
