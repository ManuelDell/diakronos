/**
 * Reine Rechenregeln des Import-Reiters (N11).
 *
 * Hier steht NUR Logik ohne Vue und ohne Netz — dieselbe Datei laeuft im
 * Node-Test (`frontend/tests/n11-import.test.mjs`) und im Browser. Alles,
 * was der Server ohnehin prueft, wird hier NICHT nachgebaut; die Datei hilft
 * nur beim Sortieren der Datei (Trennzeichen, Kopfzeile, Spalten).
 */

/** Feldnamen der Zuordnung — Reihenfolge = Anzeige im Zuordnungsschritt. */
export const IMPORT_FELDER = [
  { feld: 'vorname', label: 'Vorname', pflicht: true },
  { feld: 'nachname', label: 'Nachname', pflicht: true },
  { feld: 'email', label: 'E-Mail', pflicht: false },
  { feld: 'telefon', label: 'Telefon', pflicht: false },
  { feld: 'geburtstag', label: 'Geburtsdatum', pflicht: false },
  { feld: 'strasse', label: 'Straße', pflicht: false },
  { feld: 'plz', label: 'Postleitzahl', pflicht: false },
  { feld: 'ort', label: 'Wohnort', pflicht: false },
]

/** Kopfzeilen-Erkennung — dieselbe Zuordnung wie im Server (`_IMPORT_KOPF`). */
const KOPF_ERKENNUNG = {
  vorname: 'vorname',
  nachname: 'nachname',
  'e-mail': 'email',
  email: 'email',
  mail: 'email',
  telefon: 'telefon',
  telefonnummer: 'telefon',
  geburtsdatum: 'geburtstag',
  geburtstag: 'geburtstag',
  straße: 'strasse',
  strasse: 'strasse',
  plz: 'plz',
  postleitzahl: 'plz',
  ort: 'ort',
  wohnort: 'ort',
}

/** Zeilen der Datei sind Notbehelf: Der Server parst ebenfalls selbst. */
export const MAX_KOPFZEILEN = 2000

/**
 * Erste Zeile der Datei zerlegen. Trennzeichen wie im Server: Semikolon,
 * wenn es mindestens so oft vorkommt wie das Komma (deutsche Excel-Dateien),
 * sonst Komma. Ein BOM am Anfang wird entfernt.
 */
export function ersteZeile(text) {
  const sauber = String(text || '').replace(/^\ufeff/, '')
  const zeile = sauber.split(/\r\n|\n|\r/)[0] || ''
  const trenner = (zeile.match(/;/g) || []).length >= (zeile.match(/,/g) || []).length ? ';' : ','
  return { trenner, kopf: zerlegeZeile(zeile, trenner) }
}

/**
 * Eine Zeile in Zellen zerlegen — mit Beachtung von Anfuehrungszeichen.
 *
 * N11 (Operator-Nachtrag, Neu A): Ein Wert mit Semikolon, Anfuehrungszeichen
 * oder Zeilenumbruch steht in der CSV in Anfuehrungszeichen. Ein naives
 * `split(';')` zerlegte solche Zellen und verschob damit die ganze Zeile —
 * genau der Fehler, der vorher schon im Export steckte. Der Server liest die
 * Datei ohnehin selbst mit dem csv-Modul; hier muss die Vorschau trotzdem
 * dieselbe Aufteilung sehen wie er.
 */
export function zerlegeZeile(zeile, trenner) {
  const text = String(zeile || '')
  const zellen = []
  let aktuell = ''
  let inAnfuehrung = false
  for (let i = 0; i < text.length; i += 1) {
    const zeichen = text[i]
    if (inAnfuehrung) {
      if (zeichen === '"' && text[i + 1] === '"') {
        aktuell += '"'
        i += 1
      } else if (zeichen === '"') {
        inAnfuehrung = false
      } else {
        aktuell += zeichen
      }
      continue
    }
    if (zeichen === '"' && aktuell.trim() === '') {
      // Nur ein Anfuehrungszeichen am ZELLANFANG oeffnet einen Quoteblock.
      inAnfuehrung = true
      continue
    }
    if (zeichen === trenner) {
      zellen.push(aktuell.trim())
      aktuell = ''
      continue
    }
    aktuell += zeichen
  }
  zellen.push(aktuell.trim())
  return zellen
}

/** Zeilen der Datei (ohne Leerzeilen am Ende) — fuer den Zeilen-Hinweis. */
export function datenzeilen(text) {
  const sauber = String(text || '').replace(/^\ufeff/, '')
  const zeilen = sauber.split(/\r\n|\n|\r/).filter(z => z.trim() !== '')
  return Math.max(0, zeilen.length - 1)
}

/** Zuordnung Feldname -> Spaltenkopf aus bekannten Kopfzeilen ableiten. */
export function erkenneSpalten(kopf) {
  const erkannt = {}
  for (const spalte of kopf || []) {
    const schluessel = String(spalte || '').trim().toLocaleLowerCase('de')
    const feld = KOPF_ERKENNUNG[schluessel]
    if (feld && !erkannt[feld]) erkannt[feld] = spalte
  }
  return erkannt
}

/**
 * Sind die Pflichtspalten zugeordnet? Rueckgabe der fehlenden Beschriftungen —
 * leer heisst „weiter zum naechsten Schritt".
 */
export function fehlendePflichtspalten(zuordnung) {
  return IMPORT_FELDER
    .filter(f => f.pflicht && !(zuordnung || {})[f.feld])
    .map(f => f.label)
}

/**
 * Zellwert fuer die Vorschautabelle. Der Server liefert die Felder bereits
 * geprueft; hier wird nur lesbar gemacht, was leer ist.
 */
export function feldAnzeige(felder, feld) {
  const wert = felder ? felder[feld] : null
  if (wert === null || wert === undefined || wert === '') return '–'
  return String(wert)
}

/** Name einer Zeile fuer die Vorschau (Fallback: „Zeile N"). */
export function zeilenName(eintrag) {
  const f = (eintrag && eintrag.felder) || {}
  const name = [f.vorname, f.nachname].filter(Boolean).join(' ')
  return name || `Zeile ${eintrag ? eintrag.zeile : '?'}`
}

/** Deutsche Beschriftung eines Dublettengrunds (Server: `dublette.grund`). */
const DUBLETTEN_GRUND = {
  email: 'Diese E-Mail-Adresse gibt es schon',
  // K-c (SEC-c): eine Adresse, die in der Datei schon vergeben ist, meldet
  // der Server jetzt als Fehlerzeile (`fehler`), nicht mehr als Dublette.
  email_in_datei: 'Diese E-Mail-Adresse steht mehrfach in der Datei',
  name: 'Diesen Namen gibt es schon',
  name_in_datei: 'Dieser Name steht mehrfach in der Datei',
}

export function dublettenGrund(dublette) {
  if (!dublette) return ''
  return DUBLETTEN_GRUND[dublette.grund] || 'Sieht aus wie eine bereits vorhandene Person'
}

/** Kurztext je Zeilenstatus fuer die Vorschau. */
export function statusWort(status) {
  if (status === 'neu') return 'Neu'
  if (status === 'dublette') return 'Möglich doppelt'
  return 'Fehler'
}

/**
 * Anfuehrungszeichen fuer den ueblichen CSV-Fall: Ein Wert mit Semikolon,
 * Anfuehrungszeichen oder Zeilenumbruch gehoert in Anfuehrungszeichen. Nur
 * fuer den Muster-Download — der echte Export kommt vom Server.
 */
export function csvZelle(wert) {
  const text = wert === null || wert === undefined ? '' : String(wert)
  if (/[";\r\n]/.test(text)) return '"' + text.replace(/"/g, '""') + '"'
  return text
}

/** Muster-Datei zum Herunterladen (Kopfzeile + eine Beispielzeile). */
export function musterCsv() {
  const kopf = ['Vorname', 'Nachname', 'E-Mail', 'Telefon', 'Geburtsdatum', 'Straße', 'PLZ', 'Ort']
  const beispiel = ['Maria', 'Beispiel', 'maria.beispiel@example.org', '+49 711 123456', '14.03.1975', 'Hauptstraße 5', '70173', 'Stuttgart']
  const kopfzeile = kopf.map(csvZelle).join(';')
  // Beispielwerte bewusst NICHT entschaerft: die Datei ist eine Vorlage zum
  // Ausfuellen mit festen, unschaedlichen Beispieldaten. Die Telefonnummer
  // zeigt das internationale `+` — der Import akzeptiert beide Formen
  // (`+49 …` wie `'+49 …`, siehe `_entschaerfung_loesen` im Server).
  return '\ufeff' + kopfzeile + '\r\n' + beispiel.join(';') + '\r\n'
}
