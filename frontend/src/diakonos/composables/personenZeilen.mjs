/**
 * personenZeilen — EINE Zeilenform für „Personen“ (UX3b).
 *
 * Die Seite „Personen“ zeigt für alle Rollen dieselbe Liste (Entwurf A3,
 * Manuel: „Personen = Mitglieder + Adressbuch“). Welche FELDER in einer Zeile
 * stehen dürfen, entscheidet aber NICHT die Ansicht, sondern der Server:
 *
 *   • Administratoren lesen `get_mitglieder_liste` (persönliche Daten nur auf
 *     Anforderung) — dieselbe Quelle wie die Mitgliederliste bisher.
 *   • Alle anderen lesen `get_adressbuch` — seit B2 die EINE Freigabe-Sicht
 *     (`adressbuch_sichtbarkeit` streng beachtet, kein Feld-Zuwachs).
 *
 * Diese Datei ist die Brücke dazwischen: sie übersetzt beide Antworten in
 * dieselbe Zeilenform, damit die Liste nur einmal gebaut ist. Sie erfindet
 * KEINE Felder — was der Server nicht liefert, steht als `null`/leer da.
 */

/**
 * Quelle der Personenliste je Rolle.
 *   'liste'      — Admin: Mitgliederliste (Status, Gruppen, Verwaltung).
 *   'adressbuch' — alle anderen: die Freigabe-Sicht (nur Kontaktdaten).
 *
 * Bewusst ein reiner Wahrheitswert aus der Sitzung (kein zweites Recht):
 * `isAdmin` ist im Boot-Objekt derselbe Wert, den der Server prüft.
 */
export function personenQuelle(istAdmin) {
  return istAdmin === true ? 'liste' : 'adressbuch'
}

/** Anzeigename einer Zeile (Vor- + Nachname, nie „null“). */
function nameAus(zeile) {
  const teile = [zeile?.vorname, zeile?.nachname]
    .map(t => String(t ?? '').trim())
    .filter(Boolean)
  return teile.join(' ')
}

/** „12345 Musterhausen“ — leer, wenn beides fehlt. */
function ortAus(zeile) {
  const plz = String(zeile?.postleitzahl ?? '').trim()
  const ort = String(zeile?.wohnort ?? '').trim()
  return [plz, ort].filter(Boolean).join(' ')
}

/**
 * Jahr eines Zeitstempels, sonst ein Gedankenstrich.
 * „Dabei seit“ stand in der früheren Mitgliederliste als Jahreszahl
 * (`new Date(m.creation).getFullYear()`); eine kaputte Angabe wird nie „NaN“.
 */
function jahreszahl(wert) {
  const roh = String(wert ?? '').trim()
  if (!roh) return '–'
  const jahr = new Date(roh).getFullYear()
  return Number.isFinite(jahr) ? String(jahr) : '–'
}

/**
 * Zeile aus einer Antwort von `get_mitglieder_liste` (Admin).
 * Die Kennung `name` trägt das Profilziel (`#/mitglied/‹name›`).
 *
 * UX3b2: Die Verwaltungsliste braucht die Felder der früheren Mitgliederseite
 * — Status, Gruppen, Straße/Nummer und „dabei seit“. Sie werden hier nur
 * DURCHGEREICHT (kein Feld erfunden): fehlt eines, bleibt es leer, und die
 * Ansicht zeigt dann „–“.
 */
export function zeileAusListe(roh) {
  const z = roh || {}
  return {
    name: z.name ?? '',
    vorname: z.vorname ?? '',
    nachname: z.nachname ?? '',
    anzeigename: String(z.full_name ?? '').trim() || nameAus(z),
    email: z.email ?? null,
    telefonnummer: z.telefonnummer ?? null,
    ort: ortAus(z),
    postleitzahl: String(z.postleitzahl ?? '').trim(),
    wohnort: String(z.wohnort ?? '').trim(),
    strasse: String(z.straße ?? z.strasse ?? '').trim(),
    nummer: String(z.nummer ?? '').trim(),
    geburtstag: z.geburtstag ?? null,
    foto: z.foto ?? '',
    status: z.status ?? '',
    gruppen: Array.isArray(z.gruppen) ? z.gruppen : [],
    dabeiSeit: jahreszahl(z.creation),
    quelle: 'liste',
  }
}

/**
 * Zeile aus einer Antwort von `get_adressbuch` (alle anderen).
 * Das Adressbuch liefert KEINEN Status und KEINE Gruppen — beide bleiben
 * leer, damit die Ansicht sie nicht als „unbekannt“ behauptet.
 */
export function zeileAusAdressbuch(roh) {
  const z = roh || {}
  return {
    name: z.name ?? '',
    vorname: z.vorname ?? '',
    nachname: z.nachname ?? '',
    anzeigename: nameAus(z),
    email: z.email ?? null,
    telefonnummer: z.telefonnummer ?? null,
    ort: ortAus(z),
    geburtstag: z.geburtstag ?? null,
    foto: z.foto ?? '',
    status: '',
    gruppen: [],
    quelle: 'adressbuch',
    // Die Quelle liefert keinen Status — eine Marke „Unbekannt“ wäre eine
    // Behauptung. Die Ansicht lässt das Kennzeichen deshalb weg.
    ohneStatus: true,
  }
}

/**
 * Ab dieser Personenzahl ist die Tabelle der Standard (Entwurf A3).
 * Darunter zeigt die Liste Karten: bei wenigen Personen ist eine Tabelle
 * eine leere Fläche mit Linien, eine Karte trägt Name und Kontakt direkt.
 */
export const TABELLE_AB_PERSONEN = 20

/**
 * Form der Liste: 'tabelle' ab TABELLE_AB_PERSONEN Zeilen, sonst 'karten'.
 * `anzahl` ist die Gesamtzahl der TREFFER der aktuellen Suche — eine leere
 * Suche mit 3 Treffern bleibt eine Karte, auch wenn die Gemeinde 142 hat.
 */
export function listenForm(anzahl) {
  const n = Number(anzahl)
  if (!Number.isFinite(n)) return 'karten'
  return n >= TABELLE_AB_PERSONEN ? 'tabelle' : 'karten'
}

/** Klartext für „E-Mail verborgen“ — EINE Formulierung (§4 Sprache). */
export const EMAIL_VERBORGEN = 'E-Mail verborgen'

/**
 * Klartext für das Feld, das der Server NICHT geliefert hat, weil die
 * Verwaltung die persönlichen Daten nicht angefordert hat (UX3b2). Die Zeile
 * sagt damit die Wahrheit, statt dem Mitglied etwas zu unterstellen.
 */
export const NICHT_ANGEFORDERT = 'nicht angefordert'

/**
 * Anzeige der E-Mail-Zelle.
 * `nenner` unterscheidet „nicht freigegeben“ (Server lieferte `null`) von
 * „keine Adresse hinterlegt“ (leere Zeichenkette) — beides sieht gleich aus,
 * die Vorlesehilfe soll es aber nicht verwechseln.
 */
export function emailAnzeige(wert, { angefordert = true } = {}) {
  const roh = wert === null || wert === undefined ? '' : String(wert).trim()
  if (roh) return { text: roh, verborgen: false }
  // Nicht angefragt ist KEIN Verbergen: „E-Mail verborgen“ behauptete, das
  // MITGLIED habe die Adresse verborgen. Das stimmt nur, wenn der Server sie
  // liefern sollte und sie trotzdem fehlt.
  if (angefordert === false) return { text: NICHT_ANGEFORDERT, verborgen: false, angefordert: false }
  return { text: EMAIL_VERBORGEN, verborgen: true }
}

/** Anzeige der Telefon-Zelle — leere Werte bekommen einen Gedankenstrich. */
export function telefonAnzeige(wert) {
  const roh = wert === null || wert === undefined ? '' : String(wert).trim()
  return roh || '–'
}

/** Initialen für den Avatar (zwei Buchstaben, wie in der Mitgliederliste). */
export function initialen(anzeigename) {
  const teile = String(anzeigename || '').trim().split(/\s+/).filter(Boolean)
  if (!teile.length) return '?'
  if (teile.length === 1) return teile[0].slice(0, 2).toUpperCase()
  return (teile[0][0] + teile[teile.length - 1][0]).toUpperCase()
}

/**
 * Fußzeile der Tabelle (Entwurf A3: „142 Personen · Seite 1 von 12“).
 * Ohne Treffer steht dort nichts (`null`) — die leere Fläche sagt es schon,
 * eine Zeile „0 Personen · Seite 1 von 0“ wäre Lärm.
 *
 * @param {{gesamt:number, seite:number, seiten:number, sichtbar?:number}} werte
 */
export function fusszeile({ gesamt, seite, seiten, sichtbar } = {}) {
  const g = Number(gesamt) || 0
  if (g <= 0) return null
  const s = Math.max(1, Number(seite) || 1)
  const n = Math.max(1, Number(seiten) || 1)
  const wort = g === 1 ? 'Person' : 'Personen'
  if (typeof sichtbar === 'number' && sichtbar !== g) {
    return `${sichtbar} von ${g} ${wort} · Seite ${s} von ${n}`
  }
  return `${g} ${wort} · Seite ${s} von ${n}`
}

/** Blätter-Knöpfe: „Zurück“ ist auf Seite 1 deaktiviert, „Weiter“ auf der letzten. */
export function blaetternMoeglich(seite, seiten) {
  const s = Math.max(1, Number(seite) || 1)
  const n = Math.max(1, Number(seiten) || 1)
  return { zurueck: s > 1, weiter: s < n }
}

/** Seitenzahl aus Gesamtzahl und Seitengröße (immer mindestens 1). */
export function seitenzahl(gesamt, seiteGroesse) {
  const g = Number(gesamt) || 0
  const s = Number(seiteGroesse) || 0
  if (g <= 0 || s <= 0) return 1
  return Math.max(1, Math.ceil(g / s))
}
