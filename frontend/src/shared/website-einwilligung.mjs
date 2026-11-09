/**
 * BS-3b — Fachlogik des Profil-Abschnitts „Auf der Website als Ansprechpartner
 * erscheinen“ und des Verwaltungsbereichs „Ansprechpartner“.
 *
 * Warum eine eigene Datei (dasselbe Muster wie `website.mjs`,
 * `website-bausteine.mjs` oder `gestaltung.mjs`): die Regeln hier sind
 * PRÜFBAR — ein Node-Test kann sie ausführen. In der Komponente wären sie nur
 * als Quelltext lesbar.
 *
 * Die Regeln sind KEINE Erfindung, sondern die Bedienvorgabe der Karte BS-3b
 * (Punkt 1/2) auf den Vertrag von BS-3a (`api/website.py`):
 *
 *   meine_einwilligung_lesen  -> {website_einwilligung, website_einwilligung_am,
 *                                 website_einwilligung_foto, website_anzeigename,
 *                                 foto_erlaubt, oeffentlich}
 *   meine_einwilligung_setzen -> dieselbe Form nach dem Schreiben
 *   ansprechpartner_bereiche_lesen -> {bereiche[], auswahl{dienstbereich[],
 *                                      gruppe[]}, postfaecher[], einwilligungen_verwaltbar}
 *
 * WICHTIG (DSGVO): Der Server nimmt die Einwilligung NUR von der Person
 * selbst an (Admins bekommen 403). Diese Datei enthält deshalb bewusst KEINE
 * Funktion, die eine Einwilligung für Dritte baut — sie kann es nicht, und
 * das ist Absicht.
 */

/** Grenze des Anzeigenamens — dieselbe wie `website/einwilligung.py`. */
export const ANZEIGENAME_MAX = 140

/** Höchstlänge einer Bereichs-Bezeichnung (`api/website.py`, 140 Zeichen). */
export const BEZEICHNUNG_MAX = 140

/**
 * Der ERKLÄRTEXT des Schalters — wortgleich in beiden Oberflächen und in den
 * Tests. Was erscheint / was nie erscheint / Widerruf (Kartenvorgabe P1).
 */
export const EINWILLIGUNG_ERKLAERUNG = [
  'Was erscheinen kann: dein Name oder dein Anzeigename, die Funktion, für die du eingetragen bist, und — nur wenn du es zusätzlich erlaubst — dein Foto.',
  'Was nie erscheint: E-Mail-Adresse, Telefonnummer, Anschrift, Geburtstag.',
  'Du kannst die Zustimmung jederzeit widerrufen. Sie wirkt sofort: dein Name verschwindet dann von der nächsten Abfrage an.',
]

/**
 * Zustand des Einwilligungs-Abschnitts aus der Serverantwort.
 *
 * Nicht jede Umgebung liefert jedes Feld (die SPA zeigt den Abschnitt auch in
 * einer frisch migrierten Installation): fehlende Werte gelten als „nicht
 * zugestimmt“ — Default AUS (G1).
 *
 * @param {object|null} antwort Rohe Antwort von `meine_einwilligung_lesen`
 * @returns {{einwilligung: boolean, foto: boolean, anzeigename: string,
 *            fotoErlaubt: boolean, oeffentlich: boolean, am: string|null}}
 */
export function einwilligungStand(antwort) {
  const a = antwort || {}
  const einwilligung = a.website_einwilligung === true
  return {
    einwilligung,
    // Die rohe Foto-Zustimmung — OHNE Einwilligung wirkungslos; die Anzeige
    // leitet daraus keinen „aktiv“-Eindruck ab, dafür steht `fotoErlaubt`.
    foto: a.website_einwilligung_foto === true,
    anzeigename: typeof a.website_anzeigename === 'string' ? a.website_anzeigename : '',
    fotoErlaubt: a.foto_erlaubt === true && einwilligung,
    oeffentlich: a.oeffentlich === true,
    am: a.website_einwilligung_am || null,
  }
}

/**
 * Der Anzeigename, wie er auf der Website stünde — für die Vorschau.
 *
 * Leer = voller Name (der Server nimmt dann `oeffentlicher_name`). Hier wird
 * NICHTS erfunden: die Vorschau zeigt entweder den eingegebenen Anzeigenamen
 * oder den vollen Namen, den die Seite ohnehin kennt.
 *
 * @param {string} anzeigename
 * @param {{vorname?: string, nachname?: string}} person
 * @returns {string}
 */
export function angezeigterName(anzeigename, person = {}) {
  const eigen = String(anzeigename || '').trim()
  if (eigen) return eigen
  return [person.vorname, person.nachname].filter(Boolean).join(' ').trim()
}

/**
 * Ist der Foto-Schalter überhaupt wählbar?
 *
 * Kartenvorgabe: „nur wählbar, wenn Einwilligung an UND ein Foto vorhanden;
 * sonst Hinweis“. Ohne Einwilligung lehnt der Server `foto=true` mit 417 ab —
 * die Oberfläche darf den Schalter also gar nicht erst anbieten.
 *
 * @param {{einwilligung: boolean, hatFoto: boolean}} lage
 * @returns {boolean}
 */
export function fotoWaehlbar({ einwilligung, hatFoto } = {}) {
  return Boolean(einwilligung && hatFoto)
}

/**
 * Der Hinweistext unter dem Foto-Schalter — genau EINER, je nach Lage.
 *
 * @param {{einwilligung: boolean, hatFoto: boolean, foto: boolean}} lage
 * @returns {string} leer, wenn der Schalter ohne Einschränkung nutzbar ist
 */
export function fotoHinweis({ einwilligung, hatFoto, foto } = {}) {
  if (!einwilligung) {
    return 'Ein Foto kann erst erscheinen, wenn du der Nennung deines Namens zugestimmt hast.'
  }
  if (!hatFoto) {
    return 'Du hast noch kein Profilfoto hinterlegt. Lade zuerst oben ein Foto hoch — dann kannst du hier zustimmen.'
  }
  if (!foto) {
    return 'Ohne deine Zustimmung erscheint kein Bild — Name und Funktion erscheinen trotzdem.'
  }
  return ''
}

/**
 * Was der Profil-Abschnitt gerade an den Server schicken würde.
 *
 * Zwei Regeln der Karte, beide hier (statt in der Komponente):
 *
 *  1. **Nur Geändertes.** Verglichen wird mit dem GELADENEN Stand — ein Wert,
 *     der auf den Ausgangswert zurückgeht, ist keine Änderung (UX3h3).
 *  2. **Widerruf nimmt die Foto-Zustimmung mit.** Der Server setzt sie beim
 *     Widerruf selbst zurück; die Oberfläche schickt sie NICHT mit (sonst
 *     stünde im Aufruf ein Feld, das die Person nie angefasst hat).
 *
 * @param {{einwilligung: boolean, foto: boolean, anzeigename: string}} stand
 *        der geladene Stand (aus `einwilligungStand`)
 * @param {{einwilligung: boolean, foto: boolean, anzeigename: string}} entwurf
 *        was gerade in den Feldern steht
 * @returns {{einwilligung?: boolean, foto?: boolean, anzeigename?: string, leer: boolean}}
 */
export function einwilligungAenderungen(stand, entwurf) {
  const s = stand || {}
  const e = entwurf || {}
  const aenderungen = {}

  const einwilligungJetzt = e.einwilligung === true
  if (einwilligungJetzt !== (s.einwilligung === true)) {
    aenderungen.einwilligung = einwilligungJetzt
  }

  // Foto nur, wenn die Einwilligung BLEIBT: im Widerruf ist sie Sache des
  // Servers, und ohne Einwilligung ist sie wirkungslos (417).
  if (einwilligungJetzt) {
    const fotoJetzt = e.foto === true
    const fotoVorher = s.einwilligung === true && s.foto === true
    if (fotoJetzt !== fotoVorher) aenderungen.foto = fotoJetzt
  }

  const genannt = String(e.anzeigename ?? '').trim()
  const vorher = String(s.anzeigename ?? '').trim()
  if (genannt !== vorher) aenderungen.anzeigename = genannt

  const leer = Object.keys(aenderungen).length === 0
  return leer ? { leer: true } : { ...aenderungen, leer: false }
}

/**
 * Darf gespeichert werden? (Knopf gesperrt, solange nichts geändert ist.)
 *
 * Zusätzlich gesperrt, solange ein unbrauchbarer Anzeigename in den Feldern
 * steht: eine Meldung beim Absenden wäre später als nötig.
 *
 * @param {{einwilligung: boolean, foto: boolean, anzeigename: string}} stand
 * @param {{einwilligung: boolean, foto: boolean, anzeigename: string}} entwurf
 * @returns {{speicherbar: boolean, grund: string}}
 */
export function speichernMoeglich(stand, entwurf) {
  const { anzeigename } = entwurf || {}
  if (String(anzeigename ?? '').trim().length > ANZEIGENAME_MAX) {
    return {
      speicherbar: false,
      grund: `Der Anzeigename darf höchstens ${ANZEIGENAME_MAX} Zeichen lang sein.`,
    }
  }
  const aenderungen = einwilligungAenderungen(stand, entwurf)
  if (aenderungen.leer) return { speicherbar: false, grund: '' }
  return { speicherbar: true, grund: '' }
}

/**
 * Der Text der Rückmeldung nach dem Speichern.
 *
 * Kartenvorgabe: Widerruf „ohne Rückfrage, mit Rückgängig“. Deshalb nennt der
 * Widerruf die Rücknahme ausdrücklich; alles andere bestätigt nur.
 *
 * @param {object} aenderungen aus `einwilligungAenderungen`
 * @returns {{ton: string, text: string, rueckgaengig: boolean}}
 */
export function speicherMeldung(aenderungen) {
  const a = aenderungen || {}
  if (a.einwilligung === false) {
    return {
      ton: 'success',
      text: 'Deine Zustimmung ist widerrufen. Dein Name erscheint nicht mehr auf der Website.',
      // UX2c: Der Widerruf ist UMKEHRBAR — die Rücknahme wird angeboten.
      rueckgaengig: true,
    }
  }
  if (a.einwilligung === true) {
    return {
      ton: 'success',
      text: 'Danke. Wenn du eine Aufgabe auf der Website hast, erscheint dein Name jetzt dort.',
      rueckgaengig: false,
    }
  }
  return {
    ton: 'success',
    text: 'Deine Angaben zur Website sind gespeichert.',
    rueckgaengig: false,
  }
}

// ══════════════════════════════════════════════════════════════════════════
// Verwaltungsseite „Ansprechpartner“
// ══════════════════════════════════════════════════════════════════════════

/** Die zwei Knotenarten des Organigramms — wie `api/website.BEREICH_ARTEN`. */
export const BEREICH_ARTEN = [
  { value: 'dienstbereich', label: 'Dienstbereich' },
  { value: 'gruppe', label: 'Gruppe' },
]

/**
 * Eine Zeile der gespeicherten Auswahl, für die Oberfläche normalisiert.
 *
 * @param {object} zeile Rohe Serverzeile
 * @param {number} stelle Listenposition (Rückfall für die Sortierung)
 * @returns {{art: string, funktion: string, bezeichnung: string,
 *            postfach: string, sortierung: number, schluessel: string}}
 */
export function auswahlZeile(zeile, stelle = 0) {
  const z = zeile || {}
  const art = String(z.art || '').trim().toLowerCase()
  const funktion = String(z.funktion || '').trim()
  const sortierung = Number.isFinite(Number(z.sortierung)) ? Number(z.sortierung) : stelle
  return {
    art,
    funktion,
    bezeichnung: String(z.bezeichnung || ''),
    postfach: String(z.postfach || ''),
    sortierung,
    // EIN stabiler Schlüssel für `v-for`/Vergleiche: Art + Funktion sind
    // serverseitig eindeutig (Index `uq_website_ansprechpartner_art_funktion`).
    schluessel: `${art}:${funktion}`,
  }
}

/**
 * Die gespeicherte Auswahl als Zeilenliste (Reihenfolge: Sortierung, Funktion).
 *
 * @param {object|null} antwort Rohe Antwort von `ansprechpartner_bereiche_lesen`
 * @returns {object[]}
 */
export function bereicheZeilen(antwort) {
  const roh = Array.isArray(antwort?.bereiche) ? antwort.bereiche : []
  return roh
    .map((z, i) => auswahlZeile(z, i))
    .sort((a, b) => a.sortierung - b.sortierung || a.schluessel.localeCompare(b.schluessel))
}

/**
 * Der Funktionskatalog je Art, flach und mit Anzeigenamen.
 *
 * `auswahl.dienstbereich` ist im Vertrag eine LISTE (`[{funktion, bezeichnung}]`),
 * nicht ein Objekt — die alte Doku-Form (`{name: {bezeichnung}}`) wird
 * trotzdem verkraftet, damit ein Serverumbau die Oberfläche nicht blind macht.
 *
 * @param {object|null} antwort
 * @param {string} art
 * @returns {{funktion: string, bezeichnung: string}[]}
 */
export function funktionsKatalog(antwort, art) {
  const teil = antwort?.auswahl?.[art]
  if (!teil) return []
  const liste = Array.isArray(teil)
    ? teil.map((e) => ({ funktion: String(e?.funktion || ''), bezeichnung: String(e?.bezeichnung || '') }))
    : Object.entries(teil).map(([funktion, wert]) => ({
      funktion: String(funktion),
      bezeichnung: String(wert?.bezeichnung || funktion),
    }))
  return liste
    .filter((e) => e.funktion)
    .sort((a, b) => a.bezeichnung.localeCompare(b.bezeichnung, 'de') || a.funktion.localeCompare(b.funktion))
}

/**
 * Die Postfach-Auswahl (Slug + Bezeichnung, ohne Adresse) — BS-1a.
 *
 * @param {object|null} antwort
 * @returns {{slug: string, bezeichnung: string}[]}
 */
export function postfachAuswahl(antwort) {
  const roh = Array.isArray(antwort?.postfaecher) ? antwort.postfaecher : []
  return roh
    .map((p) => ({ slug: String(p?.slug || ''), bezeichnung: String(p?.bezeichnung || p?.slug || '') }))
    .filter((p) => p.slug)
}

/**
 * Die Anzeige-Bezeichnung einer Zeile: eigene Bezeichnung, sonst der Name des
 * Datensatzes aus dem Katalog, sonst die Kennung.
 *
 * @param {object} zeile
 * @param {{funktion: string, bezeichnung: string}[]} katalog
 * @returns {string}
 */
export function bereichBezeichnung(zeile, katalog = []) {
  const eigen = String(zeile?.bezeichnung || '').trim()
  if (eigen) return eigen
  const treffer = katalog.find((e) => e.funktion === zeile?.funktion)
  return (treffer && treffer.bezeichnung) || String(zeile?.funktion || '')
}

/**
 * Was der Server bekommt: die VOLLE Liste (delete-and-replace, BS-3a).
 *
 * Bewusst schmal: `art`, `funktion`, `bezeichnung`, `postfach`, `sortierung`.
 * KEIN Einwilligungsfeld — der Server lehnt ein solches mit 403 ab, und diese
 * Oberfläche hat keines.
 *
 * @param {object[]} zeilen
 * @returns {object[]}
 */
export function bereicheNutzlast(zeilen = []) {
  return (zeilen || []).map((z, stelle) => ({
    art: String(z.art || ''),
    funktion: String(z.funktion || ''),
    bezeichnung: String(z.bezeichnung || '').trim(),
    // Ein leerer Wert heißt „kein Postfach“ — als `null` gesendet, nicht als "".
    postfach: String(z.postfach || '').trim() || null,
    sortierung: Number.isFinite(Number(z.sortierung)) ? Number(z.sortierung) : stelle,
  }))
}

/**
 * Ist die Auswahl gegenüber dem geladenen Stand geändert? (UX3h3-Muster.)
 *
 * @param {object|null} antwort geladene Serverantwort
 * @param {object[]} zeilen was gerade in der Liste steht
 * @returns {boolean}
 */
export function auswahlGeaendert(antwort, zeilen = []) {
  const vorher = bereicheZeilen(antwort)
  const jetzt = zeilen || []

  if (vorher.length !== jetzt.length) return true
  for (let i = 0; i < vorher.length; i += 1) {
    const a = vorher[i]
    const b = jetzt[i] || {}
    const hp = String(b.postfach ?? '').trim()
    if (String(a.art) !== String(b.art ?? '').trim().toLowerCase()) return true
    if (String(a.funktion) !== String(b.funktion ?? '').trim()) return true
    if (String(a.bezeichnung).trim() !== String(b.bezeichnung ?? '').trim()) return true
    if (String(a.postfach) !== hp) return true
  }
  return false
}

/**
 * Ein Eintrag darf nur einmal vorkommen (Server: 417 bei doppelter Funktion).
 *
 * @param {object[]} zeilen
 * @param {string} art
 * @param {string} funktion
 * @returns {boolean}
 */
export function bereitsGewaehlt(zeilen = [], art, funktion) {
  return (zeilen || []).some(
    (z) => z.art === art && z.funktion === funktion,
  )
}

/**
 * Hinweis, dass die Einwilligung nicht hier gesetzt wird (Kartenvorgabe P1).
 * Steht wortgleich im Bereich und in den Tests.
 */
export const EINWILLIGUNG_NUR_SELBST =
  'Ob jemand auf der Website erscheint, entscheidet die Person selbst in ihrem Profil. Die Einwilligung lässt sich hier nicht setzen und nicht widerrufen.'
