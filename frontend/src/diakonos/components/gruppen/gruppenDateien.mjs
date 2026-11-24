/**
 * DATEIEN-4 — die Regeln der Gruppendateien, ohne DOM und ohne Vue.
 *
 * Grundlage ist das FERTIGE Backend (DATEIEN-3,
 * `backend/src/diakronos_app/api/dateien.py`) — hier wird NUR gespiegelt,
 * nichts erfunden:
 *
 *   dateien.liste(gruppe, untergruppe?)      → Kopf + `dateien: [...]`
 *   dateien.hochladen(gruppe, untergruppe?, datei=<Multipart>)
 *   dateien.anpinnen(name, an)               (Pin setzen/lösen)
 *   dateien.umbenennen(name, dateiname)
 *   dateien.loeschen(name)                   (in den Papierkorb, F5)
 *   dateien.wiederherstellen(name)           (nur MODERIEREN)
 *   dateien.papierkorb(gruppe, untergruppe?) (nur MODERIEREN)
 *   dateien.datei(name)                      (Ausliefern, GET)
 *   dateien.einstellungen(gruppe) / .einstellung_setzen(gruppe, schluessel, wert)
 *
 * Der KOPF der Liste nennt, was der Aufrufer darf
 * (`darf_hochladen`, `darf_anpinnen`, `max_bytes`); je Datei steht es noch
 * einmal (`darf_anpinnen`, `darf_bearbeiten`, `eigene`). Die Oberfläche
 * entscheidet NICHTS selbst — sie blendet nur aus, was der Server ohnehin
 * verweigert (fail closed: fehlt das Feld, gibt es keinen Knopf).
 *
 * Aufbewahrung des Papierkorbs (F5): `PAPIERKORB_TAGE` = 30. Der Server rechnet
 * den Endzeitpunkt und liefert ihn je Zeile als `loeschbar_ab`; die eigene
 * Rechnung hier ist nur der Rückfall, wenn das Feld fehlt.
 */

// ── Grenzen ────────────────────────────────────────────────────────────────

/** Aufbewahrung im Papierkorb in Tagen — `PAPIERKORB_TAGE` in `models/dateien.py`. */
export const PAPIERKORB_TAGE = 30

/** Längster Anzeigename — `GDT_NAME_MAX` in `models/dateien.py`. */
export const NAME_MAX = 120

// ── Endpunkte (EINE Stelle, wie `anhaenge.mjs` im Chat) ────────────────────

/** Die Aufrufpfade des Backends (dotted paths, wie in `api/dateien.py`). */
export const PFADE = Object.freeze({
  liste: 'diakronos.diakonos.api.dateien.liste',
  hochladen: 'diakronos.diakonos.api.dateien.hochladen',
  anpinnen: 'diakronos.diakonos.api.dateien.anpinnen',
  umbenennen: 'diakronos.diakonos.api.dateien.umbenennen',
  loeschen: 'diakronos.diakonos.api.dateien.loeschen',
  wiederherstellen: 'diakronos.diakonos.api.dateien.wiederherstellen',
  papierkorb: 'diakronos.diakonos.api.dateien.papierkorb',
  datei: 'diakronos.diakonos.api.dateien.datei',
  einstellungen: 'diakronos.diakonos.api.dateien.einstellungen',
  einstellung_setzen: 'diakronos.diakonos.api.dateien.einstellung_setzen',
})

// ── Texte (eine Stelle, deutsche Wörter ohne Fachbegriffe) ─────────────────

export const TEXTE = Object.freeze({
  leer: 'Noch keine Dateien',
  leerText: 'Hier sammelt die Gruppe Dokumente, Bilder und anderes. '
    + 'Wer hochladen darf, legt die erste Datei an.',
  herunterladen: 'Herunterladen',
  oeffnen: 'Öffnen',
  umbenennen: 'Umbenennen',
  anpinnen: 'Anpinnen',
  loesen: 'Pin lösen',
  loeschen: 'Löschen',
  eigene: 'von mir',
  angepinnt: 'Angepinnt',
  hochladen: 'Datei hochladen',
  hochladenLaeuft: 'wird hochgeladen …',
  papierkorb: 'Papierkorb',
  papierkorbLeer: 'Der Papierkorb ist leer',
  papierkorbLeerText: 'Gelöschte Dateien bleiben hier, bis sie endgültig entfernt werden.',
  wiederherstellen: 'Wiederherstellen',
  grenzeUnbekannt: 'Die Größe der Dateien ist gerade nicht bekannt.',
})

// ── Kleine Helfer ──────────────────────────────────────────────────────────

/** Zahl aus einer Serverantwort oder `null`, wenn sie unbrauchbar ist. */
function zahl(wert) {
  if (wert === null || wert === undefined || wert === '') return null
  const n = Number(wert)
  return Number.isFinite(n) ? n : null
}

/** Ist der Wert ausdrücklich wahr? (fehlt/falsch → `false`, fail closed) */
export function wahr(wert) {
  return wert === true || wert === 'true' || wert === 1 || wert === '1'
}

// ── Kopf der Liste ─────────────────────────────────────────────────────────

/**
 * Der Kopf der Antwort von `dateien.liste`.
 *
 * `darf_hochladen` steuert den Hochladen-Knopf, `darf_anpinnen` den Pin,
 * `max_bytes` die Vorab-Prüfung der Dateiauswahl (F9: dieselbe Grenze wie im
 * Chat). Fehlt `max_bytes`, wird NICHTS abgewiesen — die Grenze entscheidet
 * dann der Server, und seine Meldung erscheint im Hinweis.
 *
 * @param {object} antwort Antwort von `dateien.liste`
 * @returns {{darfHochladen: boolean, darfAnpinnen: boolean, maxBytes: number|null, anzahl: number}}
 */
export function kopfAus(antwort) {
  const a = antwort && typeof antwort === 'object' ? antwort : {}
  const max = zahl(a.max_bytes)
  const dateien = Array.isArray(a.dateien) ? a.dateien : []
  return {
    darfHochladen: wahr(a.darf_hochladen),
    darfAnpinnen: wahr(a.darf_anpinnen),
    maxBytes: max !== null && max > 0 ? Math.floor(max) : null,
    anzahl: dateien.length,
  }
}

/**
 * Warum darf diese Datei NICHT hochgeladen werden? Leer = sie darf.
 *
 * Geprüft wird nur, was der BROWSER sicher weiß: leere Datei, offenkundig zu
 * groß. Typ und Inhalt prüft allein der Server (Magie, Sperrliste) — hier
 * steht deshalb keine Typ-Regel.
 */
export function uploadHindernis(datei, maxBytes) {
  if (!datei) return 'Bitte eine Datei auswählen.'
  const groesse = zahl(datei?.size)
  if (groesse !== null && groesse <= 0) return 'Die Datei ist leer.'
  const grenze = zahl(maxBytes)
  if (groesse !== null && grenze !== null && grenze > 0 && groesse > grenze) {
    return `Die Datei ist zu groß (höchstens ${mbText(grenze)}).`
  }
  return ''
}

/** Eine Grenze in MB als Satz-Zahl („25 MB“) — ganze MB ohne Nachkommastelle. */
export function mbText(bytes) {
  const n = zahl(bytes)
  if (n === null || n <= 0) return ''
  const mb = n / (1024 * 1024)
  if (Number.isInteger(mb)) return `${mb} MB`
  return `${mb.toFixed(1).replace('.', ',')} MB`
}

/** Dateigröße für die Zeile („1,2 MB“) — leere Angabe bei unbekanntem Wert. */
export function groesseText(bytes) {
  const n = zahl(bytes)
  if (n === null || n < 0) return ''
  if (n < 1000) return `${Math.round(n)} B`
  const kb = n / 1000
  if (kb < 1000) {
    // Glatte kB ohne Nachkommastelle, krumme mit einer (deutsches Komma).
    const gerundet = Math.round(kb * 10) / 10
    return `${Number.isInteger(gerundet) ? gerundet : gerundet.toFixed(1).replace('.', ',')} kB`
  }
  const mb = kb / 1000
  return `${mb.toFixed(1).replace('.', ',')} MB`
}

// ── Datum und Papierkorb ───────────────────────────────────────────────────

/**
 * Datum aus der Serverantwort („2026-11-23 14:05:00“, Wandzeit der Gemeinde)
 * als `YYYY-MM-DD`. Unbekanntes bleibt leer — keine erfundene Zahl.
 */
export function datumText(wert) {
  const text = String(wert || '').trim()
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(text)
  if (!treffer) return ''
  return `${treffer[3]}.${treffer[2]}.${treffer[1]}`
}

/**
 * Wann wird diese Papierkorb-Zeile ENDGÜLTIG entfernt? (F5, 30 Tage)
 *
 * Der Server liefert den Zeitpunkt (`loeschbar_ab`); fehlt er, wird aus
 * `geloescht_am` + `PAPIERKORB_TAGE` gerechnet. Fehlt auch das, gibt es keinen
 * Satz — lieber nichts sagen als ein falsches Datum.
 */
export function endgueltigAm(zeile) {
  const direkt = datumText(zeile?.loeschbar_ab)
  if (direkt) return direkt
  const geloescht = String(zeile?.geloescht_am || '').trim()
  const treffer = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(geloescht)
  if (!treffer) return ''
  const [, jahr, monat, tag, stunde, minute, sekunde] = treffer
  const zeit = new Date(Date.UTC(
    Number(jahr), Number(monat) - 1, Number(tag),
    Number(stunde), Number(minute), Number(sekunde || 0),
  ))
  if (Number.isNaN(zeit.getTime())) return ''
  zeit.setUTCDate(zeit.getUTCDate() + PAPIERKORB_TAGE)
  const zz = (n) => String(n).padStart(2, '0')
  return `${zz(zeit.getUTCDate())}.${zz(zeit.getUTCMonth() + 1)}.${zeit.getUTCFullYear()}`
}

/** Der Satz der Papierkorb-Zeile: „wird am 23.12.2026 endgültig gelöscht“. */
export function papierkorbEndeText(zeile) {
  const am = endgueltigAm(zeile)
  return am ? `wird am ${am} endgültig gelöscht` : ''
}

// ── Die Zeilen der Liste ───────────────────────────────────────────────────

/**
 * Die Einträge in der Reihenfolge, die die Oberfläche zeigt.
 *
 * Der Server sortiert schon (angepinnte zuerst) — hier bleibt die REIHENFOLGE
 * seiner Antwort. Ein Ersatz für fehlende Felder gibt es nicht: was fehlt,
 * ist leer (keine erfundenen Namen, keine 0-Byte-Angaben).
 */
export function zeilenAus(antwort) {
  const a = antwort && typeof antwort === 'object' ? antwort : {}
  const roh = Array.isArray(a.dateien) ? a.dateien : []
  return roh
    .filter((z) => z && typeof z === 'object')
    .map((z) => ({
      name: String(z.name || ''),
      dateiname: String(z.dateiname || '') || 'Ohne Namen',
      mime: String(z.mime || ''),
      groesse: zahl(z.groesse),
      groesseText: groesseText(z.groesse),
      angelegtAm: String(z.angelegt_am || ''),
      angelegtVon: String(z.angelegt_von || ''),
      eigene: wahr(z.eigene),
      angepinnt: wahr(z.angepinnt),
      darfAnpinnen: wahr(z.darf_anpinnen),
      darfBearbeiten: wahr(z.darf_bearbeiten),
    }))
    .filter((z) => z.name)
}

/**
 * Die Aktionen einer Datei — NUR was der Server je Zeile meldet.
 *
 * `darf_bearbeiten` deckt Umbenennen UND Löschen (beide sind SCHREIBEN mit
 * `besitzer`; der Server rechnet das je Datei aus). Der Pin hängt an
 * `darf_anpinnen`. Herunterladen kann jeder, der die Datei sieht (LESEN hat
 * die Liste schon verlangt).
 */
export function aktionenFuerZeile(zeile) {
  // Eine Zeile kommt entweder so, wie `liste` sie liefert (`darf_bearbeiten`,
  // snake_case), oder schon normalisiert aus `zeilenAus` (`darfBearbeiten`).
  // Beide Formen gelten — sonst hinge das Menü davon ab, welcher Weg sie baut.
  const z = zeile && typeof zeile === 'object' ? zeile : {}
  const bearbeiten = wahr(z.darfBearbeiten) || wahr(z.darf_bearbeiten)
  const anpinnen = wahr(z.darfAnpinnen) || wahr(z.darf_anpinnen)
  const eintraege = [
    { key: 'herunterladen', label: TEXTE.herunterladen, icon: 'herunterladen' },
  ]
  if (bearbeiten) {
    eintraege.push({ key: 'umbenennen', label: TEXTE.umbenennen, icon: 'stift' })
  }
  if (anpinnen) {
    eintraege.push({
      key: 'anpinnen',
      label: wahr(z.angepinnt) ? TEXTE.loesen : TEXTE.anpinnen,
      icon: 'pin',
    })
  }
  if (bearbeiten) {
    eintraege.push({ key: 'loeschen', label: TEXTE.loeschen, icon: 'loeschen', gefahr: true })
  }
  return eintraege
}

/**
 * Darf dieser Eintrag gelöscht werden — und mit welcher Rückfrage (F4)?
 *
 * Eigene Dateien jeder, der sie hochgeladen hat; FREMDE nur die Leitung
 * (HV/MV, in der Untergruppe GL). Die Rückfrage nennt genau diese Folge: die
 * Datei wandert in den Papierkorb und ist dort 30 Tage wiederherstellbar.
 *
 * @returns {{ja: boolean, titel: string, text: string, aktion: string}}
 */
export function loeschRueckfrage(zeile) {
  const z = zeile && typeof zeile === 'object' ? zeile : {}
  const name = String(z.dateiname || 'Die Datei')
  const fremd = !wahr(z.eigene)
  return {
    ja: darfLoeschen(z),
    titel: fremd ? 'Fremde Datei löschen?' : 'Datei löschen?',
    text: `„${name}“ wandert in den Papierkorb und lässt sich dort `
      + `${PAPIERKORB_TAGE} Tage lang wiederherstellen. Danach wird sie endgültig entfernt.`,
    aktion: TEXTE.loeschen,
  }
}

/** Rechtshinweis, wenn eine Datei NICHT bearbeitet werden darf (nur zum Lesen). */
export function darfLoeschen(zeile) {
  return wahr(zeile?.darfBearbeiten) || wahr(zeile?.darf_bearbeiten)
}

// ── Papierkorb ─────────────────────────────────────────────────────────────

/**
 * Die Zeilen des Papierkorbs (`dateien.papierkorb`).
 *
 * Nur wer dort aufräumen darf, bekommt Daten — ein 403 ist deshalb kein
 * Fehler der Seite, sondern die Antwort „es gibt für dich hier nichts zu
 * räumen“ (die Ansicht erscheint gar nicht erst).
 */
export function papierkorbZeilen(antwort) {
  const a = antwort && typeof antwort === 'object' ? antwort : {}
  const roh = Array.isArray(a.dateien) ? a.dateien : []
  return roh
    .filter((z) => z && typeof z === 'object')
    .map((z) => ({
      name: String(z.name || ''),
      dateiname: String(z.dateiname || '') || 'Ohne Namen',
      groesse: zahl(z.groesse),
      groesseText: groesseText(z.groesse),
      geloeschtAm: String(z.geloescht_am || ''),
      geloeschtVon: String(z.geloescht_von || ''),
      endeText: papierkorbEndeText(z),
    }))
    .filter((z) => z.name)
}

/** Tage, die im Papierkorb gelten — aus der Antwort, sonst die Serverzahl. */
export function aufbewahrungTage(antwort) {
  const n = zahl(antwort?.aufbewahrung_tage)
  return n !== null && n > 0 ? Math.floor(n) : PAPIERKORB_TAGE
}

// ── Einstellungen ──────────────────────────────────────────────────────────

/** Die beiden Schalter der Karte „Dateien“ (Namen wie im Kern). */
export const SCHALTER = Object.freeze([
  {
    key: 'dateien_hochladen_alle',
    label: 'Alle Mitglieder dürfen hochladen',
    help: 'Ist der Schalter aus, laden nur noch die Verantwortlichen Dateien hoch.',
  },
  {
    key: 'dateien_anpinnen_alle',
    label: 'Alle Mitglieder dürfen anpinnen',
    help: 'Angepinnte Dateien stehen oben in der Liste — für alle sichtbar.',
  },
])

/**
 * Der Stand der Karte aus `dateien.einstellungen`.
 *
 * `darf_aendern` kommt vom Server (VERWALTEN an der Gruppe) — ist es falsch,
 * stehen die Schalter gesperrt da (lesbar, nicht klickbar).
 */
export function einstellungenAus(antwort) {
  const a = antwort && typeof antwort === 'object' ? antwort : {}
  const werte = a.werte && typeof a.werte === 'object' ? a.werte : {}
  const stand = {}
  for (const s of SCHALTER) stand[s.key] = wahr(werte[s.key])
  return { werte: stand, darfAendern: wahr(a.darf_aendern) }
}
