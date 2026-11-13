/**
 * MT-7b — EIN Weg zurück zur Liste: merken, ERSETZEN, wiederherstellen.
 *
 * BEFUND (drittes Review zu MT-7/MT-7b): Der erste Umbau hatte zwei Lücken.
 *
 *   (1) Zurück-Falle: Die Leseseite sprang mit `navigate(ziel)` — das setzt
 *       `location.hash` und legt einen NEUEN Verlaufseintrag an.
 *       Verlauf: [Liste, Leseseite, Liste?q]. Der Zurück-Knopf des Browsers
 *       führte dann wieder auf die Leseseite.
 *   (2) Filterverlust: Der Listen-Eintrag im Verlauf trug die Filter NICHT
 *       (`?q=`/`?kategorie=` stand nur im Merker, nicht in der Adresse), und
 *       `Wiki.vue` merkte sich beim Öffnen gar nichts mehr in der Adresse.
 *       Browser-„Zurück“ landete also auf der Liste OHNE Suche.
 *
 * ENTSCHEIDUNG (Operator 13.11.): KEIN `history.back()`.
 *   · Die Liste schreibt ihre vollständige Adresse (mit Filtern) IN IHREN
 *     EIGENEN Verlaufs-Eintrag (`history.replaceState`, wie `Lieder.vue`) und
 *     merkt sie sich zusätzlich hier (`rueckwegMerken`).
 *   · „‹ zurück“ ERSETZT den Eintrag der Leseseite durch die Listen-Adresse
 *     (`rueckwegErsetzen` → `location.replace`). Damit bleibt ein
 *     Verlaufs-Eintrag weniger statt einer mehr: der Zurück-Knopf des
 *     Browsers führt an der Leseseite vorbei.
 *   · Der Merker nennt außerdem die zuletzt geöffnete Kennung, damit die Liste
 *     nach dem Zurück den Fokus wieder auf dieses Element legt.
 *
 * Gültigkeit (Review-Punkt 5): Der Merker gilt NUR, solange der Nutzer aus
 * der Liste kam. Beim Verlassen der Liste in eine andere Seite (Gruppen-Detail,
 * Menü, …) wird er verworfen — sonst landete „zurück“ später im alten `?q=`.
 *
 * Importfrei — im Docker-Build (node --test) und im Browser gleichermaßen
 * nutzbar; ohne `window` (Node) bleiben die Funktionen stumm.
 */

/** Schlüssel der `sessionStorage`; Wert: `{ adresse, kennung }` als JSON. */
export const RUECKWEG_SCHLUESSEL = 'mt7bRueckweg'

/** Im Speicher des Tabs — schneller Weg, funktioniert auch ohne sessionStorage. */
let imSpeicher = null

/** Kennung des zuletzt geöffneten Eintrags (für den Fokus in der Liste). */
let letzteKennung = ''

const BEREINIGT_LEER = Object.freeze({ adresse: '', kennung: '' })

/**
 * Prüft eine gemerkte Adresse: nur eine Listen-Adresse (Pfad ohne Filter,
 * Abfrage erlaubt) wird angenommen — nie eine andere Seite und nie eine
 * Leseseite. So schickt ein alter Eintrag „zurück“ nicht in eine Sackgasse.
 *
 * @param {unknown} adresse
 * @param {string} liste Pfad der Liste ohne Abfrage, z. B. '#/wiki'
 * @returns {string} bereinigte Adresse oder '' (nichts Brauchbares gemerkt)
 */
export function bereinigeAdresse(adresse, liste) {
  const wert = typeof adresse === 'string' ? adresse.trim() : ''
  if (!wert || !liste) return ''
  if (wert !== liste && !wert.startsWith(`${liste}?`)) return ''
  // Ein zweites Fragezeichen ist kein Ziel mehr (kein doppelter Abfrageteil).
  const frage = wert.indexOf('?')
  if (frage !== -1 && wert.slice(frage + 1).includes('?')) return ''
  return wert
}

/** Einen gemerkten Rohwert lesen — Form prüfen, nicht die Adresse. */
function rohLesen() {
  // Im Speicher steht IMMER ein Objekt (`null` = nichts gemerkt) — sonst
  // überschriebe der leere Alt-Wert `''` einen gültigen Stand aus der
  // `sessionStorage` (Neuladen der Leseseite).
  if (imSpeicher !== null) return imSpeicher
  try {
    const roh = window.sessionStorage.getItem(RUECKWEG_SCHLUESSEL)
    if (!roh) return ''
    if (roh.startsWith('{')) {
      const daten = JSON.parse(roh)
      return { adresse: String(daten?.adresse || ''), kennung: String(daten?.kennung || '') }
    }
    return roh // alte Form: nur die Adresse
  } catch {
    return '' // kein Speicher (privater Modus, gesperrt) — der feste Weg genügt
  }
}

/**
 * Den Merker für eine Liste lesen (bereinigt).
 * @param {string} liste Pfad der Liste, z. B. '#/beitraege'
 * @returns {{adresse: string, kennung: string}}
 */
function merkerLesen(liste) {
  const roh = rohLesen()
  if (!roh) return BEREINIGT_LEER
  if (typeof roh === 'string') return { adresse: bereinigeAdresse(roh, liste), kennung: '' }
  const adresse = bereinigeAdresse(roh.adresse, liste)
  if (!adresse) return BEREINIGT_LEER
  // Eine Kennung ohne Adresse ist wertlos (und umgekehrt nicht: ohne Kennung
  // gibt es nur keinen Fokus, der Rückweg gilt trotzdem).
  return { adresse, kennung: typeof roh.kennung === 'string' ? roh.kennung : '' }
}

/**
 * Die vollständige Adresse der Liste merken, bevor ein Eintrag geöffnet wird.
 * @param {string} adresse Adresse mit Filtern, z. B. '#/wiki?kategorie=technik&q=beamer'
 * @param {string} liste Pfad der Liste ohne Abfrage, z. B. '#/wiki'
 * @param {string} [kennung] Kennung des geöffneten Eintrags (für den Fokus danach)
 * @returns {{adresse: string, kennung: string}} der gemerkte Stand (leer = nichts)
 */
export function rueckwegMerken(adresse, liste, kennung = '') {
  const sauber = bereinigeAdresse(adresse, liste)
  if (!sauber) return BEREINIGT_LEER
  const stand = { adresse: sauber, kennung: kennung ? String(kennung) : '' }
  imSpeicher = stand
  letzteKennung = stand.kennung
  try {
    window.sessionStorage.setItem(RUECKWEG_SCHLUESSEL, JSON.stringify(stand))
  } catch {
    // Kein Speicher: der Merker im Tab gilt weiterhin.
  }
  return stand
}

/**
 * Das Merkziel von „‹ zurück“ — die gemerkte Listen-Adresse MIT Filtern.
 * Es wird IMMER eine Adresse der Liste zurückgegeben (ohne Merker: ohne Filter).
 * @param {string} liste Pfad der Liste, z. B. '#/beitraege'
 * @returns {string}
 */
export function rueckwegZiel(liste) {
  return merkerLesen(liste).adresse || liste
}

/**
 * Die Kennung des zuletzt geöffneten Eintrags (Review-Punkt 4): Die Liste
 * setzt nach dem Aufbau den Fokus auf dieses Element zurück.
 * @param {string} liste Pfad der Liste
 * @returns {string} Kennung oder '' (kein Merker / keine Kennung)
 */
export function rueckwegKennung(liste) {
  return merkerLesen(liste).kennung || letzteKennung
}

/**
 * Zurück zur Liste — als ERSETZEN, nicht als Push (Review-Punkt 1).
 *
 * `location.replace` tauscht den Eintrag der Leseseite gegen die
 * Listen-Adresse aus: Verlauf [Liste, Leseseite] → [Liste, Liste?q] wird zu
 * [Liste, Liste?q]. Der Zurück-Knopf des Browsers führt damit an der
 * Leseseite vorbei, und der Vorschlag „kein neuer Eintrag je Klick“ gilt.
 * (Chromium löst dabei ein `hashchange` aus — der Router wechselt die Seite.)
 *
 * @param {string} liste Pfad der Liste, z. B. '#/beitraege'
 * @returns {string} das tatsächlich angefahrene Ziel
 */
export function rueckwegErsetzen(liste) {
  const ziel = rueckwegZiel(liste)
  if (typeof window !== 'undefined' && window.location?.replace) {
    try {
      window.location.replace(ziel)
      return ziel
    } catch {
      // Kein Verlauf (Sandbox/Datei-URL): der Hash-Sprung bleibt.
    }
  }
  if (typeof window !== 'undefined' && window.location) window.location.hash = ziel
  return ziel
}

/**
 * Den Merker leeren (Tests, Abmelden, Verlassen der Liste — Review-Punkt 5).
 * @param {string} [liste] Nur leeren, wenn der Merker zu DIESER Liste gehört
 *   (die Liste selbst ruft ihn beim Verlassen auf; ohne Angabe wird immer
 *   geleert).
 */
export function rueckwegVergessen(liste = '') {
  if (liste && !merkerLesen(liste).adresse) return
  imSpeicher = null
  letzteKennung = ''
  try {
    window.sessionStorage.removeItem(RUECKWEG_SCHLUESSEL)
  } catch {
    // Kein Speicher — nichts zu tun.
  }
}

/**
 * Die Adresse der AKTUELLEN Seite in ihren Verlaufs-Eintrag schreiben
 * (Review-Punkt 2, wie `Lieder.vue`). Damit hat der Listen-Eintrag die Filter
 * schon, bevor der Eintrag geöffnet wird — Browser-„Zurück“ landet auf der
 * gefilterten Liste, weil die Liste beim Aufbau aus der Adresse übernimmt.
 * Kein Routenwechsel, kein neuer Eintrag.
 *
 * @param {string} adresse Adresse mit Filtern
 * @returns {boolean} ob geschrieben wurde
 */
export function adresseImVerlaufSetzen(adresse) {
  if (typeof window === 'undefined' || !window.history?.replaceState) return false
  try {
    window.history.replaceState(window.history.state, '', adresse)
    return true
  } catch {
    return false // Verlauf nicht verfügbar (Sandbox) — der Merker trägt weiter
  }
}

// ── Gültigkeit am ROUTENWECHSEL (Review-Punkt 5) ────────────────────────────
// Ein Klick im Seiteninhalt allein genügt nicht: der Menüpunkt „Lieder“ sitzt
// im Gerüst (`AppSidebar.vue`), außerhalb jeder Seite. Der Router sieht JEDEN
// Wechsel — und weiß, von welcher Seite er kommt. Deshalb gilt: Der Merker
// überlebt nur den Weg Liste → Leseseite derselben Liste; jede andere
// Abfolge verwirft ihn (sonst landete „zurück“ später im alten `?q=`).

/** Vergleichsschlüssel einer Adresse: Pfad ohne Abfrage (für „dieselbe Seite“). */
function pfadVon(adresse) {
  const wert = String(adresse || '')
  const frage = wert.indexOf('?')
  return frage === -1 ? wert : wert.slice(0, frage)
}

/**
 * Darf der Merker nach diesem Wechsel weiter gelten?
 * @param {string} von Adresse der verlassenen Seite
 * @param {string} nach Adresse der neuen Seite
 * @param {string} liste Pfad der Liste, z. B. '#/beitraege'
 * @returns {boolean} true = behalten (Liste → eigene Leseseite)
 */
export function rueckwegBleibtGueltig(von, nach, liste) {
  if (!liste) return false
  const vonPfad = pfadVon(von)
  const nachPfad = pfadVon(nach)
  // Aus der Liste heraus: Öffnen eines Eintrags (`#/liste/<kennung>`) oder
  // Umbenennen des Listen-Eintrags im Verlauf (gleicher Pfad, `replaceState`
  // mit Filtern) — beides gehört zum Merker.
  if (vonPfad === liste) {
    return nachPfad === liste || nachPfad.startsWith(`${liste}/`)
  }
  // Auf der Leseseite: ein weiterer Eintrag DERSELBEN Liste („Ähnliche
  // Artikel“) oder zurück auf die Liste selbst (über den Knopf, der den
  // Merker noch braucht, um den Fokus zu setzen).
  if (vonPfad.startsWith(`${liste}/`)) {
    return nachPfad.startsWith(`${liste}/`) || nachPfad === liste
  }
  return false
}
