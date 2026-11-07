/**
 * suche.mjs — Einstellungen: Gruppen und Suche (Karte UX3h).
 *
 * Der Entwurf A6 und der Kartentext verlangen:
 *
 *   * die linke Liste in FÜNF Gruppen — Gemeinde · Zugang · Kommunikation ·
 *     Datenschutz · Erweitert (Prinzip N3: 3–7 je Gruppe, Seltenes unten);
 *   * ein Suchfeld OBEN, das sowohl die BEREICHE als auch die FELDNAMEN
 *     filtert (Stichwortliste je Bereich) und zum Feld springt.
 *
 * Diese Datei hält beides ohne Vue und ohne DOM — damit ist die Ordnung im
 * Node-Test prüfbar (`frontend/tests/ux3h-einstellungen-gruppen-suche.test.mjs`):
 * welche Gruppe ein Bereich hat, welche Stichworte er trägt, was ein
 * Suchbegriff trifft und welche Felder ein Bereich hat.
 *
 * GRUNDSÄTZE, die hier als Regel stehen (nicht als Meinung der Seite):
 *
 *   * Ein Eintrag trägt GENAU seine Stichworte — keine erfundenen. Die Liste
 *     ist aus den Feldern und Überschriften des jeweiligen Abschnitts
 *     abgeleitet (Quelle je Eintrag im Kommentar).
 *   * Die Suche ist unscharf im Sinne von „enthält“ (Kleinschreibung,
 *     Umlaute egal), NICHT im Sinne von Tippfehler-Toleranz: ein Suchbegriff,
 *     den niemand eingetippt hat, soll nicht plötzlich alles treffen.
 *   * Kein Bereich erfindet Felder: `FELDER` nennt nur Beschriftungen, die im
 *     Abschnitt wirklich stehen — ein Test vergleicht beides.
 */

/** Die fünf Gruppen in der Reihenfolge des Entwurfs (A6). */
export const GRUPPEN = [
  { id: 'gemeinde', titel: 'Gemeinde' },
  { id: 'zugang', titel: 'Zugang' },
  { id: 'kommunikation', titel: 'Kommunikation' },
  { id: 'datenschutz', titel: 'Datenschutz' },
  { id: 'erweitert', titel: 'Erweitert' },
]

/**
 * Stichworte je Bereich. Sie sind DAS, was die Suche findet, wenn jemand nach
 * einem Feldnamen sucht („SMTP“, „Logo“, „Aufbewahrung“, „Passwort“).
 *
 * Herkunft je Zeile (Abschnittsdatei in pages/einstellungen/):
 *   gemeinde      Gemeinde.vue    — Name, Kurzname, Kontakt, Logo, Anschrift,
 *                                   Telefon, Website, öffentliche Adresse,
 *                                   Willkommenstext, Module
 *   website       Website.vue     — Anbindung des Website-Baukastens
 *   anmeldung     Anmeldung.vue   — Anmeldeverfahren, Authentik, Konten
 *   registrierung Registrierung.vue — Link-Vorgaben, Anmeldeformulare
 *   rollen        RollenRechte.vue — Rollen, Rechte, Verantwortliche
 *   mailversand   Mailversand.vue — SMTP, Absender, Passwort, Testmail
 *   datenschutz   DatenschutzTexte.vue — Einwilligung, Erklärung, Aufbewahrung
 *   datensicherung Datensicherung.vue — Sicherungen, Uhrzeit, Aufbewahrung
 *   papierkorb    Papierkorb.vue   — gelöschte Einträge zurückholen
 *   gestaltung    Gestaltung.vue   — Abstände, Rahmen, Rundungen
 *   dev-modus     DevModus.vue     — Demo-Daten, Befunde, Werkzeuge
 */
export const STICHWORTE = {
  gemeinde: ['Name', 'Kurzname', 'Kontakt', 'E-Mail', 'Logo', 'Anschrift', 'Adresse',
    'Straße', 'PLZ', 'Ort', 'Telefon', 'Website', 'Öffentliche Adresse',
    'Willkommenstext', 'Module', 'Zeitzone'],
  website: ['Website', 'Website-Baukasten', 'Anbindung', 'Veröffentlichen', 'Primo'],
  anmeldung: ['Anmeldung', 'Login', 'Anmeldeverfahren', 'Passwort', 'Authentik',
    'Gruppe', 'Konten', 'Freischalten', 'Sperren'],
  registrierung: ['Registrierung', 'Anmeldelinks', 'Gültigkeitsdauer', 'Formulare',
    'Höchstzahl', 'QR-Code'],
  rollen: ['Rollen', 'Rechte', 'Verantwortliche', 'Bereiche', 'Gruppen', 'Zuweisen'],
  mailversand: ['E-Mail', 'Mailversand', 'SMTP', 'Mailserver', 'Absender',
    'Absenderadresse', 'Benutzername', 'Port', 'Verschlüsselung', 'Testmail',
    'Passwort'],
  datenschutz: ['Datenschutz', 'Einwilligung', 'Datenschutzerklärung',
    'Aufbewahrung', 'Löschung', 'Texte', 'Veröffentlichung'],
  datensicherung: ['Datensicherung', 'Sicherung', 'Backup', 'Automatisch sichern',
    'Uhrzeit', 'Aufbewahrung', 'Wiederherstellen'],
  papierkorb: ['Papierkorb', 'gelöscht', 'zurückholen', 'Wiederherstellen'],
  gestaltung: ['Gestaltung', 'Abstände', 'Rahmen', 'Rundungen', 'Musteransicht',
    'Zurücksetzen'],
  'dev-modus': ['Entwicklermodus', 'Dev-Modus', 'Demo-Daten', 'Befunde', 'Werkzeuge'],
}

/**
 * Felder je Bereich — die Ziele, zu denen die Suche springt.
 *
 * `id` ist die Kennung, die der Abschnitt dem Feld gibt (`dk-sprung-…`); der
 * Abschnitt setzt sie selbst (siehe `sprungZiel`), damit die Kennung im
 * Markup steht und nicht nur hier behauptet wird.
 */
export const FELDER = {
  gemeinde: [
    { id: 'name', label: 'Name der Gemeinde', stichworte: ['Name', 'Gemeindename'] },
    { id: 'kurzname', label: 'Kurzname', stichworte: ['Kürzel', 'Kurzname'] },
    { id: 'kontakt-email', label: 'Kontakt-E-Mail', stichworte: ['E-Mail', 'Kontakt'] },
    { id: 'logo', label: 'Logo', stichworte: ['Logo', 'Bild', 'Monogramm'] },
    { id: 'strasse', label: 'Straße und Hausnummer', stichworte: ['Anschrift', 'Straße'] },
    { id: 'plz', label: 'PLZ', stichworte: ['Postleitzahl', 'Anschrift'] },
    { id: 'ort', label: 'Ort', stichworte: ['Anschrift'] },
    { id: 'telefon', label: 'Telefon', stichworte: ['Telefon', 'Rufnummer'] },
    { id: 'website', label: 'Website', stichworte: ['Webseite', 'Internet'] },
    { id: 'oeffentliche-adresse', label: 'Öffentliche Adresse',
      stichworte: ['Adresse', 'URL', 'Links'] },
    { id: 'willkommenstext', label: 'Willkommenstext',
      stichworte: ['Begrüßung', 'Anmeldeseite'] },
  ],
  anmeldung: [
    // Die Feldnamen sind die der Seite: „Unbekannte Personen“ (Auswahl) und
    // „Gruppe in Authentik“ / „Rolle in Diakronos“ (Zuordnungen).
    { id: 'unbekannte-personen', label: 'Unbekannte Personen',
      stichworte: ['Anmeldeverfahren', 'neue Konten', 'Abweisen', 'Freischaltung'] },
    { id: 'authentik-gruppen', label: 'Authentik-Gruppen und Rollen',
      stichworte: ['Authentik', 'Gruppe', 'Rolle', 'Zuordnung'] },
  ],
  registrierung: [
    { id: 'gueltigkeit', label: 'Gültigkeitsdauer (Tage)',
      stichworte: ['Ablauf', 'Gültigkeit'] },
    { id: 'hoechstzahl', label: 'Höchstzahl Anmeldungen', stichworte: ['Maximum'] },
  ],
  mailversand: [
    { id: 'host', label: 'Name des Mailservers', stichworte: ['SMTP', 'Mailserver'] },
    { id: 'verschluesselung', label: 'Verschlüsselung', stichworte: ['TLS', 'SSL'] },
    { id: 'port', label: 'Port', stichworte: ['Port'] },
    { id: 'benutzername', label: 'Benutzername', stichworte: ['Anmeldung', 'Konto'] },
    { id: 'passwort', label: 'Passwort', stichworte: ['Passwort', 'Postfach'] },
    { id: 'absender', label: 'Absenderadresse', stichworte: ['Absender', 'E-Mail'] },
    { id: 'absendername', label: 'Absendername', stichworte: ['Absender'] },
    { id: 'testmail', label: 'Testmail', stichworte: ['Test', 'Probe'] },
  ],
  datenschutz: [
    { id: 'einwilligung', label: 'Einwilligungstext', stichworte: ['Einwilligung'] },
    { id: 'datenschutzerklaerung', label: 'Datenschutzerklärung',
      stichworte: ['Erklärung', 'DSGVO'] },
    { id: 'aufbewahrung', label: 'Hinweis zur Aufbewahrung', stichworte: ['Aufbewahrung'] },
    { id: 'veroeffentlichung', label: 'Veröffentlichung', stichworte: ['veröffentlichen'] },
  ],
  datensicherung: [
    { id: 'automatisch', label: 'Täglich automatisch sichern', stichworte: ['Automatik'] },
    { id: 'uhrzeit', label: 'Uhrzeit', stichworte: ['Uhrzeit', 'Zeitpunkt'] },
    { id: 'aufbewahrungstage', label: 'Sicherungen aufbewahren für',
      stichworte: ['Aufbewahrung', 'Frist'] },
  ],
  gestaltung: [
    { id: 'abstaende', label: 'Abstände', stichworte: ['Abstand', 'Skala'] },
    { id: 'rahmen', label: 'Rahmen', stichworte: ['Rahmenbreite'] },
    { id: 'rundungen', label: 'Rundungen', stichworte: ['Eckenradius', 'Radius'] },
  ],
}

/** Kleinschreibung + Umlaute aufgelöst — „Öffentliche“ == „oeffentliche“. */
export function normalisiere(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
}

/** Enthält `text` den Suchbegriff `begriff` (beide normalisiert)? */
export function enthaelt(text, begriff) {
  const n = normalisiere(begriff).trim()
  if (!n) return false
  return normalisiere(text).includes(n)
}

/**
 * Felder eines Bereichs, die auf den Suchbegriff passen.
 * Leerer Begriff → leere Liste (die Seite zeigt dann den ganzen Abschnitt).
 */
export function trefferFelder(bereichId, begriff) {
  const felder = FELDER[bereichId] || []
  if (!normalisiere(begriff).trim()) return []
  return felder.filter((f) => enthaelt([f.label, f.id, ...(f.stichworte || [])].join(' '), begriff))
}

/**
 * Bereiche, die auf den Suchbegriff passen — über Stichworte UND Felder.
 * Ergebnis: Map id → { bereich, felder } in der Reihenfolge der Gruppen.
 */
export function trefferBereiche(abschnitte, begriff) {
  const out = new Map()
  if (!normalisiere(begriff).trim()) return out
  for (const a of abschnitte) {
    const felder = trefferFelder(a.id, begriff)
    const stichworte = (STICHWORTE[a.id] || []).join(' ')
    if (felder.length || enthaelt([a.label, stichworte].join(' '), begriff)) {
      out.set(a.id, { bereich: a, felder })
    }
  }
  return out
}

/** Felder in der Reihenfolge des Entwurfs (leere Gruppen fallen weg). */
export function gruppiere(abschnitte) {
  const out = GRUPPEN.map((g) => ({ ...g, eintraege: [] }))
  const nach = new Map(out.map((g) => [g.id, g]))
  for (const a of abschnitte) {
    const ziel = nach.get(a.gruppe) || nach.get('erweitert')
    ziel.eintraege.push(a)
  }
  return out.filter((g) => g.eintraege.length)
}
