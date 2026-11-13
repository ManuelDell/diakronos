/**
 * MT-3 — Die EINE Zeit einer Meldung (ms): 10 Sekunden.
 *
 * Sie gilt für ALLES, was mit einer Meldung zu tun hat:
 *   * wie lange die Meldung STEHT (Anzeige), und
 *   * wie lange ihre Aktion zurückholbar ist (Frist des Rückgängig-Stapels).
 *
 * WARUM EINE EIGENE DATEI: Der Meldungsdienst (`useToast.js`) und der
 * Rückgängig-Stapel (`rueckgaengigStapel.mjs`) brauchen die Zahl beide, und
 * sie importieren einander schon (der Dienst die Grenze, der Stapel die
 * Anzeigedauer). Stand die Zahl in einem der beiden, entstand ein Zyklus, der
 * beim Laden je nach Reihenfolge `Cannot access … before initialization` wirft
 * (im Test nachgestellt, 11.11.). Eine Zahl ohne Abhängigkeiten bricht ihn.
 *
 * ZWEI ZAHLEN FÜR EINE SACHE waren der Befund der Review-Nacharbeit: die
 * Aktion lief nach 8 s ab, während ihre Meldung noch 2 s sichtbar stand — der
 * Knopf war weg, die Meldung noch da. Wer die Zahl ändert, ändert beides.
 */
export const ANZEIGE_MS = 10_000
