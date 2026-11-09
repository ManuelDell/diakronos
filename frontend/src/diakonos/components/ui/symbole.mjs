/**
 * UX2e — Symbol-Vorrat für Menüeinträge (eine Strichfamilie).
 *
 * Bewusst eine eigene .mjs-Datei und NICHT im `<script setup>` von
 * DkSymbol.vue: eine SFC mit `<script setup>` darf nichts exportieren
 * (@vue/compiler-sfc bricht sonst ab). Hier liegt der Vorrat, dort nur das
 * Zeichnen; die Node-Tests prüfen jeden in den Seiten benutzten Namen gegen
 * diese Liste.
 *
 * Alle Pfade stammen aus lucide (ISC-Lizenz), 24er-Raster, Strichstärke 2.
 *   p = Pfade (je Pfad ein Eintrag), c = Kreise [cx, cy, r]
 */
export const SYMBOLE = {
  // Bearbeiten (Stift)
  bearbeiten: { p: ['M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z'] },
  // Sehen / Profil öffnen
  ansehen: { p: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z'], c: [[12, 12, 3]] },
  // Teilen / weitergeben
  teilen: { p: ['M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7', 'M16 6l-4-4-4 4', 'M12 2v13'] },
  // Nachricht (Briefumschlag)
  nachricht: { p: ['M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z', 'm22 7-10 6L2 7'] },
  // Gruppe / Personen
  gruppe: { p: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M22 21v-2a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'], c: [[9, 7, 4]] },
  // Kalender
  kalender: { p: ['M8 2v4', 'M16 2v4', 'M3 10h18', 'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z'] },
  // Erneut versuchen (Kreispfeil)
  erneut: { p: ['M3 12a9 9 0 1 0 3-6.7L3 8', 'M3 3v5h5'] },
  // Herunterladen
  herunterladen: { p: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'm7 10 5 5 5-5', 'M12 15V3'] },
  // Entfernen (aus etwas heraus): Tür mit Pfeil — „Aus Gruppe entfernen"
  entfernen: { p: ['M14 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3', 'M10 8l-4 4 4 4', 'M6 12h9'] },
  // Löschen (dauerhaft): Mülleimer
  loeschen: { p: ['M3 6h18', 'M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2', 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6', 'M10 11v6', 'M14 11v6'] },
  // Rolle ändern (Ebenen)
  rolle: { p: ['M12 2 2 7l10 5 10-5-10-5Z', 'm2 17 10 5 10-5', 'm2 12 10 5 10-5'] },
  // Notiz / Text
  notiz: { p: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z', 'M14 2v6h6', 'M8 13h8', 'M8 17h5'] },
  // Kopie
  kopie: { p: ['M8 8h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V8Z', 'M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2'] },
  // Wartung (Schlüssel)
  wartung: { p: ['m14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76Z'] },
  // Freigeben (Haken)
  freigeben: { p: ['M21.8 10A10 10 0 1 1 17 3.34', 'm9 12 2 2 4-4'] },
  // Prüfen (Lupe)
  pruefen: { p: ['m21 21-4.35-4.35'], c: [[11, 11, 8]] },
  // Abbrechen (X)
  abbrechen: { p: ['M18 6 6 18', 'M6 6l12 12'] },
  // UX3i (A4): Schreibrecht in der Kalenderauswahl — „Eintragen erlaubt“ nur
  // als dezentes Symbol mit Tooltip, nicht als Text in jeder Zeile.
  stift: { p: ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'] },
  // UX3i (A4): Pfeil „Prüfen ›“ in der rechten Spalte.
  weiter: { p: ['M9 6l6 6-6 6'] },

  // UX3f — Suchen (Lupe) für die Suchzeile der Befehlspalette. Gleiche
  // Strichfamilie wie alle übrigen Symbole (lucide, ISC).
  suchen: { p: ['m21 21-4.35-4.35'], c: [[11, 11, 8]] },
  // UX3f — Hinzufügen (Plus) für die Aktionen „Termin anlegen“ /
  // „Person anlegen“.
  hinzufuegen: { p: ['M12 5v14', 'M5 12h14'] },
  // UX3j (Entwurf A3): „Filter“ in der Kopfzeile von „Personen“ — Trichter,
  // dieselbe Strichfamilie (lucide, ISC).
  filter: { p: ['M22 3H2l8 9.46V19l4 2v-8.54L22 3Z'] },
  // UX3j (Entwurf A3): „Person anlegen“ — Person mit Plus (lucide
  // „user-plus“), damit der Primärknopf in allen Reitern dasselbe Zeichen
  // trägt.
  'person-plus': {
    p: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
      'M22 21v-2a4 4 0 0 0-3-3.87',
      'M19 8v6',
      'M22 11h-6'],
    c: [[9, 7, 4]],
  },
}

/** Alle verfügbaren Symbolnamen — für die Node-Tests. */
export const SYMBOLNAMEN = Object.keys(SYMBOLE)

export default SYMBOLE
