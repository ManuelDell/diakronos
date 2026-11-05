/**
 * UX2f — Prüfregeln für Eingabefelder („Feld mit Prüfung").
 *
 * EINE Quelle für die Prüfung: `DkField` (Anzeige am Feld, aria) und die
 * Seiten (Sammelprüfung beim Speichern) greifen auf dieselben Funktionen zu.
 * Damit kann die Meldung an einer Stelle nicht anders lauten als an der
 * anderen.
 *
 * REGELN (Karte UX2f): pflicht, email, url, plz, laenge, eigene Funktion.
 * Jede Regel ist eine Funktion `wert => meldungOderLeer`:
 *   * `''` heißt „in Ordnung"
 *   * jede andere Zeichenkette ist die Meldung, die am Feld erscheint
 *
 * TEXTE NACH FEHLERKATALOG-MUSTER: „was fehlt + Beispiel". Beispiel:
 *   „Es fehlt der Teil nach dem @ – z. B. example.org."
 * Niemals Fachjargon, nie ein Code, nie nur „ungültig" (I4).
 *
 * EINGABEN BLEIBEN ERHALTEN (Karte UX2f, I4): Eine Prüfung liest nur, sie
 * schreibt nie in das Modell und nie in das DOM. `DkField` zeigt die Meldung,
 * das Feld behält seinen Wert.
 *
 * Leere Werte: nur `pflicht` beanstandet sie. Alle anderen Regeln lassen ein
 * leeres Feld in Ruhe (wer nichts eingibt, bekommt keinen Fehler über ein
 * Feld, das niemand ausfüllen muss) — auch `email()`, `url()` und `plz()`.
 * UX2f2a: Das gilt jetzt WIRKLICH für jede Regel; vorher meldeten `email` und
 * `plz` ein leeres Feld, und die Seiten mussten es mit `…Frei`-Hüllen
 * (`wert ? regel(wert) : ''`) abfangen. Diese Hüllen sind damit überflüssig.
 *
 * Nur reines JavaScript, keine Importe — läuft im Image-Build (`node --test`)
 * und im Browser.
 */

/** Sichtbarer Text eines Wertes; `null`/`undefined` werden zu `''`. */
export function text(wert) {
  return String(wert ?? '').trim()
}

/** Mehrfache Leerzeichen zu einem, AUSSEN nicht schneiden (für Längen). */
function innen(wert) {
  return String(wert ?? '')
}

// ── Die Regeltexte an EINER Stelle ─────────────────────────────────────────
export const MELDUNGEN = {
  pflicht: (name) => `Bitte ${name} angeben.`,
  emailLeer: 'Bitte die E-Mail-Adresse angeben – z. B. maria.lang@example.org.',
  emailAt: 'Es fehlt das @ – z. B. maria.lang@example.org.',
  emailDoppelAt: 'Es steht mehr als ein @ darin – z. B. maria.lang@example.org.',
  emailLokal: 'Es fehlt der Teil vor dem @ – z. B. maria.lang@example.org.',
  emailDomain: 'Es fehlt der Teil nach dem @ – z. B. example.org.',
  // BEFUND der Browser-Abnahme: hier stand als Beispiel „example.org" — genau
  // der Teil, der schon dasteht. Das Beispiel zeigt den GANZEN Aufbau.
  emailPunkt: 'Es fehlt die Endung der Adresse – z. B. maria.lang@example.org.',
  emailLeerzeichen: 'Die Adresse darf keine Leerzeichen enthalten – z. B. maria.lang@example.org.',
  emailZeichen: (zeichen) =>
    `Das Zeichen „${zeichen}" gehört nicht in eine E-Mail-Adresse – erlaubt sind Buchstaben, Ziffern und . _ % + -`,
  urlLeer: 'Bitte die Adresse der Website angeben – z. B. https://www.example.org.',
  urlLeerzeichen: 'Die Adresse darf keine Leerzeichen enthalten – z. B. https://www.example.org.',
  urlSchema: 'Die Adresse muss mit http:// oder https:// beginnen – z. B. https://www.example.org.',
  urlDoppelSchema: 'Es steht zweimal http:// bzw. https:// davor – z. B. https://www.example.org.',
  urlHost: 'Es fehlt der Name der Website nach http:// bzw. https:// – z. B. www.example.org.',
  urlPunkt: 'Es fehlt die Endung des Namens – z. B. www.example.org.',
  urlZeichen: 'Der Name der Website enthält ein unerlaubtes Zeichen – erlaubt sind Buchstaben, Ziffern, Punkt und Bindestrich.',
  plzLeer: (beispiel) => `Bitte die Postleitzahl angeben – z. B. ${beispiel}.`,
  plzStellen: (ist, soll, beispiel) =>
    `Die Postleitzahl hat ${ist} ${ist === 1 ? 'Stelle' : 'Stellen'}, nötig sind ${soll} – z. B. ${beispiel}.`,
  plzZiffern: (beispiel) => `Die Postleitzahl besteht nur aus Ziffern – z. B. ${beispiel}.`,
}

/**
 * Schreibt eine Zahl in Worten, damit die Meldung bei „5 Ziffern" den
 * Beispielwert nennt. Nur 5 (Deutschland) bekommt das Muster 71638.
 */
export function plzBeispiel(stellen) {
  const g = Number(stellen)
  if (g === 4) return '1015'
  if (g === 5) return '71638'
  return '0'.repeat(Math.max(0, g))
}

// ── Die Regeln ─────────────────────────────────────────────────────────────
/**
 * Pflichtfeld. `name` ist das Wort, das in der Meldung steht
 * („Bitte einen Vornamen angeben." → name: 'einen Vornamen').
 */
export function pflicht(name = 'einen Wert') {
  return (wert) => (text(wert) ? '' : MELDUNGEN.pflicht(name))
}

/**
 * E-Mail-Adresse. Geprüft wird in der Reihenfolge, in der ein Mensch die
 * Adresse tippt — so nennt die Meldung immer den ERSTEN fehlenden Teil
 * („maria.lang@" → es fehlt der Teil nach dem @).
 *
 * Bewusst nachsichtig: eine Adresse, die diese Regel passiert, muss nicht
 * jede Sonderform des Standards erfüllen. Der Server entscheidet verbindlich
 * (Dublettenprüfung, Anlegen) — hier geht es um Tippfehler, die man sieht.
 */
export function email() {
  return (wert) => {
    const roh = innen(wert).trim()
    // Leeres Feld: nur `pflicht` beanstandet das (s. Kopfkommentar).
    if (!roh) return ''
    if (/\s/.test(roh)) return MELDUNGEN.emailLeerzeichen
    const ats = (roh.match(/@/g) || []).length
    if (ats === 0) return MELDUNGEN.emailAt
    if (ats > 1) return MELDUNGEN.emailDoppelAt
    const [lokal, domain] = roh.split('@')
    if (!lokal) return MELDUNGEN.emailLokal
    if (!domain) return MELDUNGEN.emailDomain
    // Erlaubte Zeichen: alles außer Leerraum, Steuerzeichen und den
    // Trennern, die in keiner Adresse vorkommen. Deutsche Umlaute und
    // Punkte in der Domain bleiben zulässig.
    const verboten = roh.match(/[<>,;:"'()[\]\\]/)
    if (verboten) return MELDUNGEN.emailZeichen(verboten[0])
    if (!domain.includes('.')) return MELDUNGEN.emailPunkt
    if (domain.startsWith('.') || domain.endsWith('.') || domain.includes('..')) {
      return MELDUNGEN.emailPunkt
    }
    if (!lokal.replace(/\./g, '')) return MELDUNGEN.emailLokal
    return ''
  }
}

/**
 * Website-Adresse: muss mit http:// oder https:// beginnen und einen Namen mit
 * Endung haben.
 *
 * UX2f2a: `http://` ist wieder erlaubt, wie vor UX2f (`/^https?:\/\//i`).
 * LAN-Instanzen und gespeicherte Websites laufen ohne Zertifikat über http —
 * sie als Fehler zu melden hieße, die eigene Adresse der Gemeinde
 * zurückzuweisen.
 */
export function url() {
  return (wert) => {
    const roh = innen(wert).trim()
    // Leeres Feld: nur `pflicht` beanstandet das (s. Kopfkommentar).
    if (!roh) return ''
    if (/\s/.test(roh)) return MELDUNGEN.urlLeerzeichen
    if (!/^https?:\/\//i.test(roh)) return MELDUNGEN.urlSchema
    const rest = roh.replace(/^https?:\/\//i, '')
    if (/^https?:\/\//i.test(rest)) return MELDUNGEN.urlDoppelSchema
    const host = rest.split('/')[0].split('?')[0].split('#')[0]
    if (!host) return MELDUNGEN.urlHost
    if (!/^[A-Za-z0-9\u00c0-\u024f.-]+(:\d+)?$/.test(host)) return MELDUNGEN.urlZeichen
    const ohnePort = host.replace(/:\d+$/, '')
    if (!ohnePort.includes('.') || ohnePort.startsWith('.') || ohnePort.endsWith('.')) {
      return MELDUNGEN.urlPunkt
    }
    return ''
  }
}

/**
 * Postleitzahl: nur Ziffern, feste Stellenzahl (Vorgabe 5).
 * Vierstellige Länder (z. B. Österreich) sind über `stellen` abgedeckt.
 */
export function plz(stellen = 5) {
  const soll = Number(stellen) || 5
  return (wert) => {
    const roh = innen(wert).trim()
    // Leeres Feld: nur `pflicht` beanstandet das (s. Kopfkommentar).
    if (!roh) return ''
    if (!/^\d+$/.test(roh)) return MELDUNGEN.plzZiffern(plzBeispiel(soll))
    if (roh.length !== soll) return MELDUNGEN.plzStellen(roh.length, soll, plzBeispiel(soll || 5))
    return ''
  }
}

/**
 * Länge in Zeichen. `{ min, max }`; fehlt eine Grenze, gilt sie nicht.
 * Die Meldung nennt die erreichte Zahl UND die Grenze — so weiß man, wie
 * weit man noch muss.
 */
export function laenge({ min = 0, max = Infinity, name = 'Der Text' } = {}) {
  return (wert) => {
    const roh = innen(wert).trim()
    if (!roh) return min > 0 ? `Bitte ${name === 'Der Text' ? 'einen Text' : name} angeben.` : ''
    const n = [...roh].length
    if (min && n < min) {
      return `${name} ist mit ${n} Zeichen zu kurz – nötig sind mindestens ${min}.`
    }
    if (Number.isFinite(max) && n > max) {
      return `${name} ist mit ${n} Zeichen zu lang – erlaubt sind höchstens ${max}. Bitte ${n - max} Zeichen kürzen.`
    }
    return ''
  }
}

/**
 * Eigene Funktion (Karte: „eigene Funktion"). Der Aufrufer übergibt eine
 * Funktion `(wert, form) => meldungOderLeer`. Sie darf ruhig `null`/`false`
 * zurückgeben — das bedeutet „in Ordnung".
 */
export function eigene(fn) {
  return (wert, form) => {
    if (typeof fn !== 'function') return ''
    const ergebnis = fn(wert, form)
    if (ergebnis === true || ergebnis === null || ergebnis === undefined) return ''
    if (ergebnis === false) return 'Bitte diesen Wert prüfen.'
    return String(ergebnis)
  }
}

/**
 * Regeln zu EINER Prüf-Funktion zusammenfassen. Eine Regel darf eine Funktion
 * sein (aus pflicht/email/… ODER direkt `wert => meldung`). Der Wert kommt
 * ungeschnitten an; jede Regel schneidet selbst.
 *
 * `pruefe(wert, form)` gibt die erste Meldung zurück oder `''`.
 */
export function regeln(...liste) {
  const regelnListe = liste.flat().filter(Boolean)
  return (wert, form) => {
    for (const regel of regelnListe) {
      const meldung = typeof regel === 'function' ? regel(wert, form) : ''
      if (meldung) return String(meldung)
    }
    return ''
  }
}

/**
 * Prüft mehrere Felder auf einmal (Sammelprüfung beim Speichern).
 * `felder` = { name: [wert, regel] oder [wert, regel, form] }.
 * Ergebnis: { name: meldung } nur für beanstandete Felder.
 */
export function pruefeAlle(felder, form = {}) {
  const ergebnisse = {}
  for (const [name, eintrag] of Object.entries(felder || {})) {
    if (!eintrag) continue
    const [wert, regel, eigeneForm] = Array.isArray(eintrag) ? eintrag : [eintrag, null]
    if (typeof regel !== 'function') continue
    const meldung = regel(wert, eigeneForm ?? form)
    if (meldung) ergebnisse[name] = meldung
  }
  return ergebnisse
}
