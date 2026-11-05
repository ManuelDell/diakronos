/**
 * BS-1d — Prüfbare Regeln der Oberfläche „Website-Freigaben“ (ohne Vue).
 *
 * Warum eine eigene Datei: Slug-Prüfung, Rollen-Sichtbarkeit, die Texte vor
 * dem Einschalten eines Schalters und die Umrechnung der Serverantwort sind
 * FACHLOGIK. In der Komponente wären sie nur als Quelltext lesbar
 * (`assert.match`), also nicht nachweisbar — hier sind es reine Funktionen,
 * dieselbe Aufteilung wie bei `website.mjs` (WEB-3) und `einrichtung.mjs`
 * (ON-2).
 *
 * Vertrag des Servers (BS-1a, dokumentiert in docs/BETRIEBSANLEITUNG.md
 * Abschnitt 18.3 und backend/src/diakronos_app/api/website.py):
 *
 *   GET  diakronos.diakronos.api.website.freigaben_lesen
 *        -> {kalender:[{name,titel,freigabe,slug,nur_oeffentliche_kategorien}],
 *            gruppen:[{name,titel,freigabe,slug}],
 *            beitraege_anzahl:int,
 *            beitraege:[{name,titel,veroeffentlicht}],
 *            postfaecher:[{slug,bezeichnung,email,aktiv}],
 *            postfach_fallback:{aktiv,bezeichnung},
 *            kategorien:[{name,titel,oeffentlich}]}
 *   POST diakronos.diakronos.api.website.freigabe_setzen
 *        {art:"kalender"|"gruppe", name, freigabe, slug?, nur_oeffentliche_kategorien?}
 *   POST diakronos.diakronos.api.website.beitrag_auf_website  {name, wert}
 *   POST diakronos.diakronos.api.website.postfach_speichern
 *        {slug, bezeichnung, email, aktiv?, sortierung?}
 *   POST diakronos.diakronos.api.website.postfach_loeschen    {slug}
 *   POST diakronos.diakronos.api.website.kategorie_oeffentlich {name, wert}
 *
 * Die Slugs-Prüfung ist eine VORPRÜFUNG für die Oberfläche (sofortige
 * Rückmeldung am Feld). Die Wahrheit bleibt beim Server
 * (`website/freigaben.py`): ein hier abgelehnter Slug ist dort ebenfalls
 * ungültig, und was hier durchgeht, kann dort trotzdem als „vergeben“
 * abgelehnt werden — beides wird im Formular gezeigt, nicht überschrieben.
 */
// UX2f: E-Mail-Regel aus der gemeinsamen Quelle (Feld = Prüfung).
import { email as emailRegel } from '../diakonos/composables/feldPruefung.mjs'


/** Rollen mit Zugriff auf „Website-Freigaben“ — Deckungsgleich mit
 * `_require_website_rolle` im Backend. */
export const FREIGABE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']

/** Slugs, die das Backend für sich behält (`RESERVIERT` in `website/freigaben.py`). */
export const RESERVIERTE_SLUGS = ['diakronos', 'primo', 'admin', 'api', 'login', 'standard']

/** Zeichen-Vorrat einer Adresse auf der Website. */
export const SLUG_ZEICHEN = /^[a-z0-9-]+$/
/** Dieselbe Grenze wie `SLUG_MAX` im Backend. */
export const SLUG_MAX = 140

/** Bezeichnung eines Kontakt-Postfachs (`BEZEICHNUNG_MAX` in `website/freigaben.py`). */
export const BEZEICHNUNG_MAX = 140
/** Adresslänge (`EMAIL_MAX` in `website/freigaben.py`). */
export const EMAIL_MAX = 320

/**
 * Darf dieser Benutzer den Bereich „Website-Freigaben“ sehen?
 *
 * Wie `darfWebsite` (WEB-3) nur Komfort: der Server prüft jede Anfrage
 * erneut und antwortet ohne Rolle mit 403 (fail closed).
 *
 * @param {{rollen?: string[]|null}} [optionen]
 * @returns {boolean}
 */
export function darfFreigabenVerwalten({ rollen = null } = {}) {
  const vorhanden = new Set(
    (Array.isArray(rollen) ? rollen : []).map((r) => String(r || '').trim()),
  )
  return FREIGABE_ROLLEN.some((r) => vorhanden.has(r))
}

/**
 * Slug-Form prüfen (ohne Eindeutigkeit — die kennt nur der Server).
 *
 * Reihenfolge der Meldungen ist die Reihenfolge, in der man den Fehler am
 * Feld behebt: leer → Zeichen → Verwaltung → Länge → Form → reserviert.
 *
 * @param {unknown} wert
 * @returns {{ok: boolean, slug: string, fehler: string}}
 */
export function slugPruefen(wert) {
  const slug = String(wert ?? '').trim()
  if (!slug) return { ok: false, slug, fehler: 'Bitte einen Kürzel angeben.' }
  if (!SLUG_ZEICHEN.test(slug)) {
    return {
      ok: false,
      slug,
      fehler: 'Nur Kleinbuchstaben ohne Umlaute, Ziffern und Bindestriche (a-z, 0-9, -).',
    }
  }
  if (slug.length > SLUG_MAX) {
    return { ok: false, slug, fehler: `Höchstens ${SLUG_MAX} Zeichen.` }
  }
  if (slug.startsWith('-') || slug.endsWith('-')) {
    return { ok: false, slug, fehler: 'Der Kürzel darf nicht mit einem Bindestrich beginnen oder enden.' }
  }
  if (slug.includes('--')) {
    return { ok: false, slug, fehler: 'Bitte keine zwei Bindestriche hintereinander.' }
  }
  if (RESERVIERTE_SLUGS.includes(slug.toLowerCase())) {
    return { ok: false, slug, fehler: 'Dieser Kürzel ist reserviert. Bitte einen anderen wählen.' }
  }
  return { ok: true, slug, fehler: '' }
}

/**
 * Die Warnung, die VOR dem Einschalten eines Kalenders bestätigt werden muss
 * (Orchestrator-Zusatz 2026-11-02).
 *
 * Der Text nennt die Felder, die öffentlich werden, und ausdrücklich die
 * KOMPLETTE Beschreibung — dort stehen in der Praxis interne Notizen
 * (Vorbereitung, Absprachen), und die verschwinden nicht dadurch, dass der
 * Termin „nur im Kalender“ stand.
 *
 * @param {string} titel  Anzeigename des Kalenders
 * @returns {string}
 */
export function kalenderWarnung(titel) {
  const name = String(titel ?? '').trim()
  const wer = name ? `„${name}“` : 'dieses Kalenders'
  return `Titel, Zeit, Ort und die KOMPLETTE Beschreibung aller Termine ${wer} `
    + 'werden öffentlich — auch interne Notizen in der Beschreibung. '
    + 'Bitte vorher prüfen, ob dort nichts steht, was nicht auf die Website gehört.'
}

/**
 * Die Warnung beim Einschalten einer Gruppe.
 *
 * Genannt wird nur, was der Baustein öffentlich zeigen darf; Personen
 * (Mitglieder, Mitarbeiter, Leitungen) sind NICHT dabei.
 *
 * @param {string} titel
 * @returns {string}
 */
export function gruppenWarnung(titel) {
  const name = String(titel ?? '').trim()
  const wer = name ? `„${name}“` : 'dieser Gruppe'
  return `Von ${wer} werden Name, Typ, Beschreibung, Treffzeit, Treffpunkt und Bild `
    + 'öffentlich. Personen (Mitglieder, Mitarbeiter, Leitung) erscheinen nicht.'
}

/**
 * Hinweistext zu den Terminarten, die bei eingeschaltetem
 * `nur_oeffentliche_kategorien` trotzdem erscheinen. Ohne freigegebene
 * Terminart wäre die Einschränkung „kein Termin“ — das muss dastehen, sonst
 * wundert sich der Redakteur über einen leeren Kalender.
 *
 * @param {number} anzahlOeffentlich  Anzahl Kategorien mit `oeffentlich`
 * @returns {string}
 */
export function kategorieHinweis(anzahlOeffentlich) {
  const anzahl = Number(anzahlOeffentlich)
  if (!Number.isFinite(anzahl) || anzahl <= 0) {
    return 'Achtung: Es ist keine Terminart als öffentlich freigegeben. '
      + 'Mit dieser Einstellung erscheint KEIN Termin auf der Website.'
  }
  return anzahl === 1
    ? 'Nur Termine aus der einen als öffentlich freigegebenen Terminart erscheinen.'
    : `Nur Termine aus den ${anzahl} als öffentlich freigegebenen Terminarten erscheinen.`
}

/**
 * Kurzanleitung (U5) als DATEN, nicht als Fließtext im Template — so kann ein
 * Test die Sätze prüfen, und die Reihenfolge bleibt an einer Stelle.
 *
 * @returns {string[]} zwei bis vier Sätze
 */
export function kurzanleitung() {
  return [
    'Schalte hier frei, was auf der Website erscheinen darf: Termine, Gruppen und Beiträge.',
    'Jede Freigabe gilt einzeln und ist sofort aus — nichts wird ohne dein Zutun öffentlich.',
    'Vergib je Kalender und Gruppe einen Kürzel; er ist der Name in der Adresse der Website.',
    'Die Kontakt-Postfächer bestimmen, wohin Nachrichten des Website-Formulars gehen.',
  ]
}

/**
 * Anzahl der Beiträge, die auf der Website stehen (U3).
 *
 * Der Server zählt `auf_website` bereits; fehlt die Zahl (älterer Server),
 * wird aus der Liste gezählt — nie eine erfundene 0, wenn die Liste Zeilen hat.
 *
 * @param {{beitraege_anzahl?: unknown, beitraege?: Array<unknown>|null}|null} daten
 * @returns {number}
 */
export function beitraegeAufWebsite(daten) {
  const roh = daten?.beitraege_anzahl
  const zahl = Number(roh)
  if (roh !== null && roh !== undefined && Number.isFinite(zahl) && zahl >= 0) return zahl
  return Array.isArray(daten?.beitraege) ? daten.beitraege.length : 0
}

/**
 * Zeile für Zeile: eine Freigabe-Zeile der Serverantwort in Anzeigeform.
 *
 * Unbekannte/fehlende Werte werden NICHT als „freigegeben“ gedeutet (G1:
 * Default AUS) — nur ein echtes `true` zählt.
 *
 * @param {{name?: unknown, titel?: unknown, freigabe?: unknown, slug?: unknown,
 *          nur_oeffentliche_kategorien?: unknown}} zeile
 * @returns {{name: string, titel: string, freigabe: boolean, slug: string,
 *            nurOeffentlicheKategorien: boolean}}
 */
export function freigabeZeile(zeile) {
  const quelle = zeile || {}
  const name = String(quelle.name ?? '').trim()
  const titel = String(quelle.titel ?? '').trim()
  return {
    name,
    titel: titel || name,
    freigabe: quelle.freigabe === true,
    slug: String(quelle.slug ?? '').trim(),
    // `nur_oeffentliche_kategorien` gibt es nur bei Kalendern; bei Gruppen
    // bleibt der Wert `false` (nicht verwendet, aber einheitliche Form).
    nurOeffentlicheKategorien: quelle.nur_oeffentliche_kategorien === true,
  }
}

/**
 * Was schickt die Oberfläche an `freigabe_setzen`?
 *
 * Der Slug wird NUR mitgeschickt, wenn er sich vom gespeicherten Wert
 * unterscheidet. Grund (BS-1a2/F3): Ein mitgeschickter Slug wird vom Server
 * nie umbenannt und sein Konflikt bleibt ein Fehler — ein unverändert
 * mitgeschickter Slug würde also nur eine überflüssige Prüfung auslösen, und
 * bei zwei gleichnamigen Zeilen eine Meldung, die niemand verursacht hat.
 *
 * Ein LEERER Slug wird nie geschickt: der Server leitet beim Freigeben selbst
 * einen ab; ein leerer Wert würde nur „kein Slug“ heißen und ist am Endpunkt
 * ohnehin „nicht geliefert“.
 *
 * @param {{art: string, name: string, freigabe: boolean,
 *          slug?: string, gespeicherterSlug?: string,
 *          nurOeffentlicheKategorien?: boolean}} eingabe
 * @returns {Record<string, unknown>}
 */
export function freigabeNutzlast({ art, name, freigabe, slug = '', gespeicherterSlug = '', nurOeffentlicheKategorien = null }) {
  const nutzlast = { art: String(art || ''), name: String(name || ''), freigabe: freigabe === true }
  const neu = String(slug ?? '').trim()
  const alt = String(gespeicherterSlug ?? '').trim()
  if (neu && neu !== alt) nutzlast.slug = neu
  if (art === 'kalender' && typeof nurOeffentlicheKategorien === 'boolean') {
    nutzlast.nur_oeffentliche_kategorien = nurOeffentlicheKategorien
  }
  return nutzlast
}

/**
 * Prüft die Eingaben eines Postfachs VOR dem Aufruf (U4).
 *
 * Dieselben Regeln wie `_email_pruefen`/`_bezeichnung_pruefen` im Backend,
 * aber als Feldmeldung: genau EIN `@`, keine Leerzeichen, Punkt in der
 * Domain, nicht zu lang.
 *
 * @param {{slug?: unknown, bezeichnung?: unknown, email?: unknown}} eingabe
 * @returns {{ok: boolean, felder: {slug: string, bezeichnung: string, email: string}}}
 */
export function postfachPruefen({ slug = '', bezeichnung = '', email = '' } = {}) {
  const slugErg = slugPruefen(slug)
  const nameWert = String(bezeichnung ?? '').trim()
  const mailWert = String(email ?? '').trim()

  let nameFehler = ''
  if (!nameWert) nameFehler = 'Bitte eine Bezeichnung angeben.'
  else if (nameWert.length > BEZEICHNUNG_MAX) {
    nameFehler = `Die Bezeichnung ist zu lang (höchstens ${BEZEICHNUNG_MAX} Zeichen).`
  }

  // UX2f: Die Adresse prüft dieselbe Regel wie das Feld (Kontakt-Postfächer).
  // Ein fehlender Wert behält den alten Wortlaut („Bitte eine E-Mail-Adresse
  // angeben.") — der ist an dieser Stelle schon so eingeführt.
  let mailFehler = ''
  if (!mailWert) {
    mailFehler = 'Bitte eine E-Mail-Adresse angeben.'
  } else if (mailWert.length > EMAIL_MAX) {
    mailFehler = `Die E-Mail-Adresse ist zu lang – erlaubt sind höchstens ${EMAIL_MAX} Zeichen.`
  } else {
    mailFehler = emailRegel()(mailWert)
  }

  const felder = { slug: slugErg.fehler, bezeichnung: nameFehler, email: mailFehler }
  return { ok: !felder.slug && !felder.bezeichnung && !felder.email, felder }
}

/**
 * Sortierung des Postfach-Dialogs: der nächste freie Zehner-Schritt hinter dem
 * höchsten vorhandenen Wert — dieselbe Regel wie der Server beim Anlegen
 * (`hoechste + 10`), hier nur als Vorschlag im Feld.
 *
 * @param {Array<{sortierung?: unknown}>|null} postfaecher
 * @returns {number}
 */
export function naechsteSortierung(postfaecher) {
  const werte = (Array.isArray(postfaecher) ? postfaecher : [])
    .map((p) => Number(p?.sortierung))
    .filter((n) => Number.isFinite(n))
  const hoechste = werte.length ? Math.max(...werte) : 0
  return hoechste + 10
}

/**
 * Der Klartext-Hinweis zum Rückfall-Postfach (U4).
 *
 * Der Server meldet in `postfach_fallback`, ob ohne eigene Zeilen die Adresse
 * aus der Konfiguration (`WEBSITE_KONTAKT_EMPFAENGER`) gilt. Stehen Zeilen da
 * und ist keine aktiv, fällt er NICHT still zurück — das muss die Oberfläche
 * genauso deutlich sagen wie den Fall „Rückfall greift“.
 *
 * @param {{postfach_fallback?: {aktiv?: unknown, bezeichnung?: unknown}|null,
 *          postfaecher?: Array<{aktiv?: unknown}>|null}|null} daten
 * @returns {{text: string, ton: string}}
 */
export function postfachHinweis(daten) {
  const postfaecher = Array.isArray(daten?.postfaecher) ? daten.postfaecher : []
  const bezeichnung = String(daten?.postfach_fallback?.bezeichnung ?? '').trim() || 'Standard'
  if (postfaecher.length === 0) {
    return {
      text: `Keine eigenen Postfächer: Nachrichten des Website-Formulars gehen an die `
        + `in der Konfiguration hinterlegte Adresse (Postfach „${bezeichnung}“).`,
      ton: 'info',
    }
  }
  const aktive = postfaecher.filter((p) => p?.aktiv === true).length
  if (aktive === 0) {
    return {
      text: 'Kein Postfach ist aktiv: Das Kontaktformular kann derzeit keine Nachricht '
        + 'zustellen. Es wird NICHT auf die Adresse aus der Konfiguration zurückgefallen — '
        + 'bitte ein Postfach aktivieren.',
      ton: 'warn',
    }
  }
  return {
    text: aktive === 1
      ? 'Ein Postfach ist aktiv und nimmt die Nachrichten des Website-Formulars auf.'
      : `${aktive} Postfächer sind aktiv und nehmen die Nachrichten des Website-Formulars auf.`,
    ton: 'ok',
  }
}
