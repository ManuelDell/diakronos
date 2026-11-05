/**
 * ON-3 — Reine Logik des Einrichtungs-Assistenten (Entwurf Frames 04–09, 14, 15).
 *
 * Dieses Modul enthält KEINEN Vue-Zustand und keine Anfrage: es rechnet nur,
 * was der Assistent anzeigt und wohin er geht. Das ist die Stelle, an der man
 * sich im Browser still vertut — ein Assistent, der nach „Überspringen“ zwei
 * Schritte weit springt, der „Zurück“ auf dem ersten Schritt anbietet oder
 * beim Wiedereinstieg den FALSCHEN Schritt öffnet, fällt niemandem auf, weil
 * jede einzelne Ansicht dabei richtig aussieht.
 *
 * Aufrufer: `pages/einrichtung/Assistent.vue` (Bildschirm) und
 * `frontend/tests/on3-einrichtung-assistent.test.mjs` (Nachweis).
 *
 * Bewusst KEINE Farben/Schriften/Radien und keine CSS-Variablen: das ist Sache
 * der Komponenten und von `tokens.css` (ON-0a/ON-0c). Hier steht nur Text und
 * Wahrheitslogik — dieselbe Trennung wie in `composables/einrichtung.mjs`.
 */

import { email as emailRegel, plz as plzRegel, url as urlRegel } from './feldPruefung.mjs'

/**
 * Die sechs Schritte des Assistenten in Anzeigereihenfolge.
 *
 * `schluessel` ist der Schritt-Schlüssel des Servers
 * (`einrichtung.schritt_setzen`, VERTRAG docs/ON2-VERTRAG.md Abschnitt 2);
 * `"fertig"` ist KEIN Server-Schritt — dort gibt es nichts zu speichern, der
 * Abschluss läuft über `einrichtung.abschliessen`.
 */
export const SCHRITTE = Object.freeze([
  { schluessel: 'gemeinde', anzeige: 'Gemeinde' },
  { schluessel: 'kontakt', anzeige: 'Kontakt' },
  { schluessel: 'mailversand', anzeige: 'Mailversand' },
  { schluessel: 'module', anzeige: 'Module' },
  { schluessel: 'mitglieder_kalender', anzeige: 'Mitglieder & Kalender' },
  { schluessel: 'fertig', anzeige: 'Fertig' },
])

/** Schlüssel der Server-Schritte (ohne „fertig“) — in derselben Reihenfolge. */
export const SERVER_SCHRITTE = Object.freeze(
  SCHRITTE.filter((s) => s.schluessel !== 'fertig').map((s) => s.schluessel),
)

/** Anzahl der Schritte für „Schritt n von 6“ (Entwurf 14: sechs inkl. Fertig). */
export const SCHRITT_ANZAHL = SCHRITTE.length

/** Gültige Zustände eines Schritts (`einrichtung.schritt_setzen`). */
export const ZUSTAENDE = Object.freeze(['offen', 'erledigt', 'uebersprungen'])

/** Index eines Schritts zu seinem Schlüssel; -1 wenn unbekannt. */
export function schrittIndex(schluessel) {
  return SCHRITTE.findIndex((s) => s.schluessel === schluessel)
}

/**
 * Die Schritte mit ihrem Zustand, wie die linke Leiste (Desktop) sie zeigt.
 *
 * `status.schritte` kommt vom Server (immer alle fünf, in Serverreihenfolge).
 * Fehlt ein Schritt in der Antwort, gilt er als `offen` — ein fehlender
 * Eintrag darf nie als „erledigt“ durchgehen (er wäre eine falsche Auskunft).
 * Der sechste Eintrag „Fertig“ ist erreicht, sobald der Assistent
 * abgeschlossen ist; er ist nie „übersprungen“.
 */
export function schrittListe(status) {
  const vomServer = new Map()
  const roh = Array.isArray(status?.schritte) ? status.schritte : []
  for (const eintrag of roh) {
    if (!eintrag || !eintrag.schluessel) continue
    const zustand = ZUSTAENDE.includes(eintrag.zustand) ? eintrag.zustand : 'offen'
    vomServer.set(eintrag.schluessel, zustand)
  }
  const abgeschlossen = status?.assistent_abgeschlossen === true
  return SCHRITTE.map((schritt) => {
    if (schritt.schluessel === 'fertig') {
      return { ...schritt, zustand: abgeschlossen ? 'erledigt' : 'offen' }
    }
    return { ...schritt, zustand: vomServer.get(schritt.schluessel) || 'offen' }
  })
}

/**
 * Der Schritt, bei dem ein Wiedereinstieg beginnt.
 *
 * Mit Absicht NICHT „der letzte offene“: die Entwürfe springen immer an die
 * erste unerledigte Stelle (Frame 04 zeigt Schritt 1, weil dort die Gemeinde
 * fehlt). Übersprungene Schritte zählen dabei als unerledigt — übersprungen
 * heisst genau „die Entscheidung ist noch offen“ (ON-2b/F2).
 *
 * Ist alles erledigt oder der Assistent schon abgeschlossen, ist der
 * Einstieg die Fertig-Übersicht (Frame 09/15).
 *
 * @param {object} status Antwort von `einrichtung.status`
 * @returns {string} Schritt-Schlüssel ('gemeinde' … 'fertig')
 */
export function startSchritt(status) {
  if (status?.assistent_abgeschlossen === true) return 'fertig'
  const liste = schrittListe(status)
  const erster = liste.find((s) => s.schluessel !== 'fertig' && s.zustand !== 'erledigt')
  return erster ? erster.schluessel : 'fertig'
}

/** Gibt es einen Schritt davor? (Für „Zurück“.) */
export function hatZurueck(schluessel) {
  return schrittIndex(schluessel) > 0
}

/**
 * Der Schritt nach dem übergebenen, oder `null` auf „Fertig“.
 * Auf „Fertig“ gibt es kein „Weiter“ mehr — dort steht „Zur Übersicht“.
 */
export function naechsterSchritt(schluessel) {
  const i = schrittIndex(schluessel)
  if (i < 0 || i >= SCHRITTE.length - 1) return null
  return SCHRITTE[i + 1].schluessel
}

/** Der Schritt davor, oder `null` auf dem ersten. */
export function vorherigerSchritt(schluessel) {
  const i = schrittIndex(schluessel)
  if (i <= 0) return null
  return SCHRITTE[i - 1].schluessel
}

/** „Schritt 2 von 6“ — Wortlaut aus Entwurf 14. */
export function schrittText(schluessel) {
  const i = schrittIndex(schluessel)
  const nummer = i < 0 ? 1 : i + 1
  return `Schritt ${nummer} von ${SCHRITT_ANZAHL}`
}

/**
 * Anteil des Segmentbalkens (0…1) — Entwurf 14 zeigt auf Schritt 1 von 6
 * bereits ein Sechstel (`58` von `350` px).
 */
export function segmentAnteil(schluessel) {
  const i = schrittIndex(schluessel)
  const nummer = i < 0 ? 1 : i + 1
  return nummer / SCHRITT_ANZAHL
}

/**
 * Anzeige-Label eines Zustands für die Leiste (`Übersprungen` unter dem
 * Schritt, Entwurf 07/08/09). Erledigte und offene Schritte tragen keins.
 */
export function zustandLabel(zustand) {
  return zustand === 'uebersprungen' ? 'Übersprungen' : ''
}

/**
 * Prüfung eines Schritts VOR dem Speichern — `{ feld: meldung }`, leer heisst
 * in Ordnung. Die Grenzen sind die des Servers (`gemeinde_speichern`,
 * ON2-VERTRAG Abschnitt 1), damit ein Fehler am Feld erscheint und nicht erst
 * als Serverantwort am Seitenende.
 *
 * @param {string} schluessel Schritt-Schlüssel
 * @param {object} entwurf Eingaben des Schritts
 */
export function pruefeSchritt(schluessel, entwurf = {}) {
  const fehler = {}
  if (schluessel === 'gemeinde') {
    if (!String(entwurf.gemeindename ?? '').trim()) {
      fehler.gemeindename = 'Bitte den Gemeindenamen eintragen.'
    } else if (String(entwurf.gemeindename).trim().length > 140) {
      fehler.gemeindename = 'Der Gemeindename ist zu lang (höchstens 140 Zeichen).'
    }
    if (String(entwurf.kurzname ?? '').trim().length > 40) {
      fehler.kurzname = 'Der Kurzname ist zu lang (höchstens 40 Zeichen).'
    }
  }
  if (schluessel === 'kontakt') {
    // UX2f: E-Mail, PLZ und Website prüfen mit denselben Regeln wie die
    // Felder selbst (composables/feldPruefung.mjs) — ein Text, eine Wahrheit.
    // Die Website ist hier freiwillig, aber wenn etwas dasteht, muss es eine
    // Webadresse sein (nicht bloß „beginnt mit http").
    // Nur BEANSTANDETE Felder landen im Ergebnis (ein leerer Text ist kein
    // Fehler und darf nicht als leerer Eintrag erscheinen).
    const email = String(entwurf.kontakt_email ?? '').trim()
    if (email && emailRegel()(email)) fehler.kontakt_email = emailRegel()(email)
    const plz = String(entwurf.plz ?? '').trim()
    if (plz && plzRegel()(plz)) fehler.plz = plzRegel()(plz)
    const website = String(entwurf.website ?? '').trim()
    if (website && urlRegel()(website)) fehler.website = urlRegel()(website)
    if (String(entwurf.strasse ?? '').trim().length > 120) {
      fehler.strasse = 'Die Straße ist zu lang (höchstens 120 Zeichen).'
    }
    if (String(entwurf.ort ?? '').trim().length > 120) {
      fehler.ort = 'Der Ort ist zu lang (höchstens 120 Zeichen).'
    }
    if (String(entwurf.telefon ?? '').trim().length > 40) {
      fehler.telefon = 'Die Telefonnummer ist zu lang (höchstens 40 Zeichen).'
    }
  }
  return fehler
}

/**
 * Die Felder, die `gemeinde_speichern` für den jeweiligen Schritt bekommt.
 *
 * WICHTIG — der Server schreibt ALLE Kontaktfelder immer und ein leerer Wert
 * LÖSCHT die Angabe (ON2-VERTRAG Abschnitt 1). Deshalb wird hier der
 * VOLLSTÄNDIGE Satz aus dem geladenen Stand plus den Eingaben des Schritts
 * gebaut: „Weiter“ in Schritt 2 darf nie die Anschrift wegwerfen, nur weil
 * Schritt 2 ein Feld nicht anzeigt.
 *
 * @param {string} schluessel 'gemeinde' | 'kontakt'
 * @param {object} geladen Antwort von `gemeinde.gemeinde_get_einstellungen`
 * @param {object} entwurf Eingaben des Schritts
 */
export function speicherRumpf(schluessel, geladen = {}, entwurf = {}) {
  const g = geladen || {}
  const text = (wert) => String(wert ?? '').trim()
  const basis = {
    gemeindename: text(g.gemeindename),
    kontakt_email: text(g.kontakt_email),
    oeffentliche_adresse: text(g.oeffentliche_adresse),
    willkommenstext: String(g.willkommenstext ?? ''),
    kurzname: text(g.kurzname),
    strasse: text(g.strasse),
    plz: text(g.plz),
    ort: text(g.ort),
    telefon: text(g.telefon),
    website: text(g.website),
  }
  if (schluessel === 'gemeinde') {
    basis.gemeindename = text(entwurf.gemeindename ?? basis.gemeindename)
    basis.kurzname = text(entwurf.kurzname ?? basis.kurzname)
  } else if (schluessel === 'kontakt') {
    for (const feld of ['strasse', 'plz', 'ort', 'kontakt_email', 'telefon', 'website']) {
      if (entwurf[feld] !== undefined) basis[feld] = text(entwurf[feld])
    }
  }
  return basis
}

/**
 * Ein Logo-Austausch im Schritt „Gemeinde“: Der Server ist die Quelle, die
 * Oberfläche reicht `logo_url` UNVERÄNDERT weiter (ON2-VERTRAG Abschnitt 1).
 * Diese Funktion entscheidet nur, WELCHE Adresse die Vorschau zeigt.
 *
 * @param {object} status   Einrichtungs-Status (trägt kein Logo — nur der
 *                          Gemeinde-Endpunkt tut das; hier bleibt es `null`)
 * @param {object} gemeinde Antwort von `gemeinde_get_einstellungen`
 */
export function logoVorschau(gemeinde) {
  const url = String(gemeinde?.logo_url ?? '').trim()
  if (!url || gemeinde?.logo_vorhanden === false) return null
  return url
}

/**
 * Ist die Datei im Rahmen des Servers? Geprüft wird VOR dem Upload, damit die
 * Absage am Feld steht und nicht als 417 zurückkommt.
 *
 * Erlaubt sind PNG, JPEG, WebP und SVG bis 2 MB (ON2-VERTRAG, `max. 2 MB`).
 * Der Server prüft zusätzlich Magic-Bytes/Kopfdaten — hier wird bewusst nur
 * die grobe Form geprüft (eine zweite, unvollständige Bildprüfung wäre eine
 * Fehlerquelle).
 *
 * @param {{name?: string, size?: number}} datei
 * @returns {string} Fehlertext oder ''
 */
export function logoDateiFehler(datei, maxBytes = 2 * 1024 * 1024) {
  if (!datei) return 'Bitte eine Bilddatei auswählen.'
  const name = String(datei.name || '')
  const endung = (name.split('.').pop() || '').toLowerCase()
  if (!['png', 'jpg', 'jpeg', 'webp', 'svg'].includes(endung)) {
    return 'Dateityp nicht erlaubt. Erlaubt sind PNG, JPEG, WebP oder SVG.'
  }
  if (Number(datei.size) > maxBytes) {
    return 'Die Datei ist zu groß (max. 2 MB).'
  }
  return ''
}

/**
 * Die Zeitzone, wie der Entwurf sie zeigt: „Europe/Berlin (MEZ/MESZ)“.
 *
 * Der Server liefert die Kennung (CALENDAR_TIMEZONE). Ein Zusatz in Klammern
 * erscheint NUR, wenn der Browser ihn für genau diese Zone kennt — sonst
 * stünde dort eine geratene Angabe, und die Zeitzone ist kein Feld, an dem man
 * einen Fehler bemerken würde.
 */
export function zeitzoneAnzeige(kennung) {
  const zone = String(kennung ?? '').trim()
  if (!zone) return ''
  try {
    const teile = new Intl.DateTimeFormat('de-DE', { timeZone: zone, timeZoneName: 'short' })
      .formatToParts(new Date())
    const kurz = teile.find((t) => t.type === 'timeZoneName')?.value || ''
    return kurz ? `${zone} (${kurz})` : zone
  } catch {
    // Unbekannte Zone im Browser: nur die Kennung, nichts dazuerfinden.
    return zone
  }
}

/**
 * Beschriftung des „Zur Übersicht“-Knopfs auf dem Fertig-Schirm (Frame 09/15).
 * EINE Quelle für Text und Verhalten: der Knopf ruft bei offenen Punkten
 * `einrichtung.abschliessen` und geht dann zur Übersicht.
 */
export const ABSCHLUSS_TEXT = 'Zur Übersicht'

/**
 * Weg nach dem Fertig-Schirm. Der Assistent ist dann abgeschlossen — die
 * Übersichts-Karte (ON-2) übernimmt die offenen Punkte.
 */
export const UEBERSICHT_ROUTE = '#/'
