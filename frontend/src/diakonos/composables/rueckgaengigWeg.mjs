/**
 * UX2c — der Rückgängig-Weg je Aktion (eine Wahrheit für Oberfläche und Tests).
 *
 * Prinzip I2: Rückfrage nur für Unumkehrbares; alles andere wird sofort
 * ausgeführt und über „Rückgängig“ (10 s = `ANZEIGE_MS`, Strg+Z) korrigierbar. Damit das
 * nicht an jeder Stelle anders heißt und anders ruft, steht hier:
 *
 *  1. `RUECKGAENGIG_WEGE` — je Vorgang der Endpunkt der Gegenrichtung und
 *     seine Felder. Die Namen sind die ECHTEN whitelist-Namen des Servers (so
 *     wie `useVerwaltung.js`/`useWebsiteFreigaben.js` sie rufen); der Test
 *     `frontend/tests/ux2c-endgueltig.test.mjs` prüft sie gegen
 *     `backend/src/diakronos_app/api/` UND gegen die Aufrufstelle im Frontend.
 *  2. `MELDUNGEN` — der Text der Rückgängig-Meldung („Aus Gruppe entfernt“).
 *     Er beschreibt die AUSGEFÜHRTE Aktion, nicht den Gegenweg.
 *  3. `abbildung({...})` — der Aufruf der Gegenrichtung, ohne Netz (reine
 *     Funktion). Damit prüfbar ist, WAS gesendet würde, bevor es gesendet
 *     wird — auch dort, wo kein Browser läuft.
 *  4. `wiederherstellen` — derselbe Aufruf über `useApi` (erst bei Gebrauch
 *     geladen, damit dieses Textmodul ohne `node_modules` ladbar bleibt).
 *
 * GRUNDSATZ (Review 06.11.): Ein „Rückgängig“ gibt es NUR, wenn es den Zustand
 * VOLLSTÄNDIG wiederherstellt. Ist das nicht der Fall (verlorene Felder, anderer
 * Status), bleibt die Rückfrage — Beispiele: Buchung stornieren (`Ressourcen.vue`)
 * und Mitglied aus einer Gruppe entfernen (`GruppeDetail.vue`), die deshalb
 * hier NICHT mehr stehen.
 *
 * Der Papierkorb (UX2b, `papierkorb.mjs`) bleibt die Quelle für Gelöschtes im
 * Papierkorb (Beitrag, Artikel, Lied, Termin). Was NICHT im Papierkorb liegt
 * und vollständig wiederherstellbar ist (Wert in der Auswahl, Kalender,
 * Ressource, Kontakt-Postfach), steht hier.
 */

/**
 * Je Vorgang: Endpunkt der Gegenrichtung und die Felder, die er erwartet.
 *
 * `POST` in `aufruf` ist der vollständige whitelist-Name (Modulpräfix wie in
 * den Aufrufstellen); `args` bildet die Angaben, die die Seite hat (das
 * Objekt/die Antwort des Hinwegs), auf die Parameter des Servers ab. Fehlt
 * eine Angabe, gibt die Abbildung `null` zurück — dann wird NICHT geraten und
 * der Aufrufer meldet den Fehler.
 */
export const RUECKGAENGIG_WEGE = {
  /**
   * Wert aus der Auswahl der Liederpflege entfernt → wieder hinzufügen.
   *
   * Der Server kennt für Werte genau eine Pflege-Funktion mit drei Aktionen
   * (`hinzufuegen` | `umbenennen` | `entfernen`, `dienste.py`). „Entfernen“
   * löscht die Zuordnungen der Lieder mit — deshalb bleibt das Entfernen eine
   * Rückfrage (siehe `ANGEZEIGT` unten) und nur das HINZUFÜGEN ist umkehrbar.
   */
  auswahlwert: {
    aufruf: 'diakronos.planrahmen.api.sammlungsmerkmal_werte_pflegen',
    args: ({ plantyp, schluessel, wert, plan = null }) => (
      plantyp && schluessel && String(wert || '').trim()
        ? {
          plantyp,
          schluessel,
          aktion: 'hinzufuegen',
          wert: String(wert).trim(),
          neu: null,
          plan: plan || null,
        }
        : null
    ),
  },
  /**
   * Kalender gelöscht (ging nur, solange keine Termine darin standen und nichts
   * darauf zeigt) → mit denselben Angaben neu anlegen.
   *
   * Was `create_kalender` NICHT annimmt, kann nicht wiederhergestellt werden:
   * `calender_details` (nur vom Google-Import gesetzt, kein Parameter der
   * Anlage) und `creation`/`owner`. Ein Kalender aus einem Google-Import
   * bekommt diesen Hinweis also nicht zurück — er ist der EINZIGE Fall, in dem
   * etwas fehlt; deshalb bietet die Seite das Rückgängig nur an, solange
   * `calender_details` leer ist (siehe `vollstaendig()` unten).
   */
  kalender: {
    aufruf: 'diakronos.kronos.api.kalender_verwaltung.create_kalender',
    args: (kalender) => {
      const titel = String(kalender?.titel || '').trim()
      if (!titel) return null
      return {
        titel,
        farbe: kalender.farbe || '',
        selbstverwaltet: kalender.selbstverwaltet === true,
        leserechte: Array.isArray(kalender.leserechte) ? kalender.leserechte : [],
        schreibrechte: Array.isArray(kalender.schreibrechte) ? kalender.schreibrechte : [],
        moderatoren: Array.isArray(kalender.moderatoren) ? kalender.moderatoren : [],
      }
    },
  },
  /**
   * Kontakt-Postfach der Website entfernt → mit denselben Angaben wieder
   * anlegen (`postfach_speichern` arbeitet je Kürzel; derselbe Slug legt die
   * Zeile neu an). Der Slug war der Schlüssel der gelöschten Zeile.
   */
  postfach: {
    aufruf: 'diakronos.diakronos.api.website.postfach_speichern',
    args: ({ slug, bezeichnung = '', email = '', aktiv = true, sortierung = null }) => {
      const kuerzel = String(slug || '').trim()
      // Der Server verlangt Kürzel, Bezeichnung UND Adresse — fehlt die
      // Adresse, wird NICHT mit leerem Feld geraten (der Server lehnt es ab,
      // und der Nutzer bekäme statt „zurückgeholt“ eine Fehlermeldung).
      if (!kuerzel || !String(email || '').trim()) return null
      const nutzlast = {
        slug: kuerzel,
        bezeichnung: String(bezeichnung || '').trim() || kuerzel,
        email: String(email).trim(),
        aktiv: aktiv !== false,
      }
      if (Number.isFinite(Number(sortierung))) nutzlast.sortierung = Number(sortierung)
      return nutzlast
    },
  },
  /**
   * Ressource gelöscht (ging nur ohne Buchung/Termin) → neu anlegen.
   *
   * `wartung` kommt aus `get_ressourcen_verwaltung` als 1 | 0 (Zahl, wie die
   * anderen Ja/Nein-Felder der Liste) — `wartung === true` wäre dort IMMER
   * falsch und die wiederhergestellte Ressource stünde plötzlich frei. Zahlen
   * und Wahrheitswerte werden deshalb beide verstanden.
   *
   * Nicht wiederherstellbar ist `bild`: `create_ressource` kennt das Feld
   * nicht, `get_ressourcen_verwaltung` liefert es nicht. Eine Ressource MIT
   * Bild bekommt es also nicht zurück — die Seite bietet das Rückgängig
   * deshalb nur an, solange kein Bild hinterlegt ist (`vollstaendig()`).
   */
  ressource: {
    aufruf: 'diakronos.diakonos.api.ressourcen.create_ressource',
    args: (ressource) => {
      const name = String(ressource?.name || ressource?.ressource_name || '').trim()
      if (!name) return null
      return {
        name,
        typ: ressource.typ || 'Raum',
        kapazitaet: ressource.kapazitaet ?? '',
        beschreibung: ressource.beschreibung || '',
        tags: ressource.tags || '',
        wartung: Boolean(Number(ressource.wartung === true ? 1 : ressource.wartung || 0)),
      }
    },
  },
}

/**
 * Was die Gegenrichtung NICHT mitbringen kann — je Vorgang eine Prüfung der
 * Angaben, die die Seite hat. `true` = der Zustand kommt vollständig zurück.
 *
 * Der Test hält fest, dass jede Seite mit „Rückgängig“ diese Prüfung benutzt
 * (Wächter) — sonst könnte ein Feld stillschweigend verloren gehen.
 */
export const VOLLSTAENDIG = {
  auswahlwert: () => true,
  kalender: (kalender) => !String(kalender?.calender_details || '').trim(),
  postfach: ({ slug, email } = {}) => !!String(slug || '').trim() && !!String(email || '').trim(),
  ressource: (ressource) => !String(ressource?.image || ressource?.bild || '').trim(),
}

/** Kann dieser Vorgang mit DIESEN Angaben vollständig zurückgenommen werden? */
export function vollstaendig(vorgang, daten) {
  const pruefung = VOLLSTAENDIG[vorgang]
  if (!pruefung) return false
  try {
    return pruefung(daten || {}) === true
  } catch {
    return false
  }
}

/**
 * Der Text der Rückgängig-Meldung je Vorgang (Prinzip I2/S4: ein Begriff).
 *
 * Kurz, weil die Meldung 10 s (`ANZEIGE_MS`) am unteren Rand steht. Der Name des Objekts
 * gehört dazu, wenn die Seite ihn kennt — dann weiß man, WAS zurückkommt.
 */
export const MELDUNGEN = {
  auswahlwert: (wert) => (wert ? `„${wert}“ entfernt` : 'Wert entfernt'),
  kalender: (titel) => (titel ? `Kalender „${titel}“ gelöscht` : 'Kalender gelöscht'),
  ressource: (name) => (name ? `„${name}“ gelöscht` : 'Gelöscht'),
}

/** Der Meldungstext zu einem Vorgang (unbekannt → neutraler Satz). */
export function meldung(vorgang, name) {
  const bauen = MELDUNGEN[vorgang]
  return typeof bauen === 'function' ? bauen(name) : 'Rückgängig möglich'
}

/**
 * Text einer Rückgängig-Meldung: die AUSGEFÜHRTE Aktion, kurz (Prinzip S4: ein
 * Begriff je Konzept). Steht hier und nicht in `useRueckgaengigAktion.js`,
 * weil dieses Modul ohne Vue und ohne `node_modules` ladbar ist — der Test
 * prüft den Text damit direkt.
 *
 * @param {string} was    z. B. „Aus Gruppe entfernt“
 * @param {string} [name] Objekt-/Personenname (optional, wird angehängt)
 */
export function undoText(was, name = '') {
  const satz = String(was || '').trim() || 'Erledigt'
  const n = String(name || '').trim()
  return n ? `${satz}: ${n}` : satz
}

/**
 * Was die Gegenrichtung sendet — ohne Netz (reine Funktion).
 *
 * @param {string} vorgang  Schlüssel aus `RUECKGAENGIG_WEGE`
 * @param {object} daten    Angaben der Seite (Objekt bzw. Antwort des Hinwegs)
 * @returns {{aufruf: string, args: object}|null}  `null`, wenn Angaben fehlen
 *          oder der Vorgang unbekannt ist (nie raten)
 */
export function abbildung(vorgang, daten) {
  const weg = RUECKGAENGIG_WEGE[vorgang]
  if (!weg) return null
  let args = null
  try {
    args = weg.args(daten || {})
  } catch {
    args = null
  }
  if (!args || typeof args !== 'object') return null
  return { aufruf: weg.aufruf, args }
}

async function apiCall(...argumente) {
  const modul = await import('./useApi.js')
  return modul.apiCall(...argumente)
}

/**
 * Die Gegenrichtung ausführen.
 *
 * Rückgabe wie `papierkorb.wiederherstellen`: `{ok: true, antwort}` oder
 * `{ok: false, fehler: '<Klartext>'}` — die Seiten zeigen den Fehler als
 * Meldung, statt still nichts zu tun (Prinzip I4).
 *
 * Wichtig: `apiCall` wirft NICHT bei jeder Ablehnung. Ein whitelist-Endpunkt
 * antwortet fachlich auch mit `{success: false, message: '…'}` (z. B. wenn der
 * Name inzwischen wieder vergeben ist). Ohne diese Prüfung meldete die Seite
 * „wieder da“, obwohl nichts angelegt wurde — deshalb wird `success === false`
 * wie ein Fehler behandelt.
 */
export async function wiederherstellen(vorgang, daten) {
  const befehl = abbildung(vorgang, daten)
  if (!befehl) return { ok: false, fehler: 'Für diesen Schritt gibt es kein Zurück.' }
  try {
    const antwort = await apiCall(befehl.aufruf, befehl.args)
    if (antwort && antwort.success === false) {
      return {
        ok: false,
        fehler: antwort.message || 'Das Zurücknehmen hat nicht geklappt.',
      }
    }
    return { ok: true, antwort }
  } catch (fehler) {
    return { ok: false, fehler: fehler?.message || 'Das Zurücknehmen hat nicht geklappt.' }
  }
}
