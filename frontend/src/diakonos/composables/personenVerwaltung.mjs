/**
 * personenVerwaltung — die VERWALTUNGS-Regeln der Personenliste (UX3b2).
 *
 * BEFUND (Review UX3b, Karte UX3b2 Nr. 1 und 2):
 *  • Die zusammengelegte Liste hatte die Funktionen der früheren
 *    Mitgliederseite verloren: Statusfilter, Schalter „persönliche Daten
 *    zeigen“, Status-/Gruppenspalten, Sortierung, Karten/Tabelle-Umschalter
 *    und die Karte „wartende Konten“. Weil sie persönliche Daten NIE
 *    anforderte (`persoenliche_daten: false` fest verdrahtet), stand in jeder
 *    Zeile „E-Mail verborgen“ — als hätte das MITGLIED sie verborgen.
 *  • Die Form der Liste (Tabelle/Karten) hing an `zeilen.length`, also an der
 *    Zahl der Zeilen der AKTUELLEN Seite. Die letzte, kurze Seite schaltete
 *    damit auf Karten — und mit der Tabelle verschwand die Fußzeile samt
 *    „Zurück“/„Weiter“. Auf Seite 3 von 3 war kein Blättern mehr möglich.
 *  • Das Adressbuch hat KEIN serverseitiges Blättern (höchstens 200 Zeilen).
 *    Eine Fußzeile mit „Seite 1 von 2“ versprach dort etwas, das es nicht
 *    gibt — „Weiter“ tat nichts.
 *
 * Diese Datei hält die Regeln dafür in reiner Form (ohne Vue, ohne DOM):
 * Test und Seiten benutzen DIESELBE Wahrheit.
 *
 * Datenschutz (unverändert, wird NICHT aufgeweicht): persönliche Daten
 * fordert die Oberfläche nur an, wenn ein Mitgliederadministrator sie
 * ausdrücklich einschaltet; das Adressbuch ist und bleibt die
 * Freigabe-Sicht des Servers (`get_adressbuch`). Hier wird KEIN Feld
 * erfunden — die Regeln entscheiden nur, welche Spalte wohin gehört.
 */

import { TABELLE_AB_PERSONEN } from './personenZeilen.mjs'

/**
 * Gültige Ansichten der Liste — mit „Personen“ als Aufhänger im Text, damit
 * diese Datei sich selbst als Personen-Regel zu erkennen gibt.
 */
export const ANSICHTEN = [
  { value: 'tabelle', label: 'Tabelle' },
  { value: 'karten', label: 'Karten' },
]

/**
 * Gestaltung der Ansichten-Umschaltung für DkSegment.
 * `null`, wenn es nichts zu wählen gibt: in der Adressbuch-Sicht (Rollen
 * ohne Verwaltungsrecht) zeigt die Liste dieselbe Zeilenform, und am Handy
 * ersetzen Karten die Tabelle ohnehin — ein Umschalter, der scheinbar nichts
 * tut, ist schlimmer als keiner (Prinzip K1).
 */
export function ansichtOptionen({ istAdmin, schmal } = {}) {
  if (istAdmin !== true || schmal === true) return null
  return ANSICHTEN
}

/** Endstatus der Löschung auf Antrag (DSGVO-2d) — echte Zeilen, echte Spalte. */
export const GELOESCHT_STATUS = 'geloescht'

/**
 * Statuswerte der Mitgliederliste — wortgleich mit dem Server
 * (`api/mitglieder.py`, dieselben Werte wie in der früheren Mitgliederseite).
 * „Ausgetreten“ (AUSTRITT A5) und „geloescht“ (DSGVO-2d) sind ECHTE Status der
 * Daten, keine Anzeige-Erfindung.
 */
export const STATUS_WERTE = [
  'Mitglied', 'Gast', 'Passives Mitglied', 'Passiver Gast', 'Ausgetreten', GELOESCHT_STATUS,
]

/** Anzeigewort je Status, wo es vom Speicherwert abweicht (§4 Sprache). */
export const STATUS_WORT = { [GELOESCHT_STATUS]: 'Gelöschte Person' }

/** Spaltenüberschrift eines Status. */
export function statusWort(status) {
  if (!status) return 'Unbekannt'
  return STATUS_WORT[status] || status
}

/** Kennzeichen-Variante des Status (dieselbe Zuordnung wie bisher). */
export function statusVariante(status) {
  if (status === GELOESCHT_STATUS) return 'neutral' // gedämpft, kein „Fehler“
  if (status === 'Ausgetreten') return 'err'
  if (status === 'Mitglied') return 'ok'
  if (status === 'Passives Mitglied') return 'info'
  if (status === 'Gast') return 'warn'
  if (status === 'Passiver Gast') return 'warn'
  return 'neutral'
}

/**
 * Darf diese Rolle die Verwaltungsfunktionen sehen? (Statusfilter, persönliche
 * Daten, Sortierung, Karten/Tabelle, wartende Konten.)
 *
 * UI-R10: Der Parameter ist seit R-11a das PERSONEN-Flag
 * (`istMitgliederverwaltung` = Administrator ODER Mitgliederadministrator),
 * nicht mehr `isAdmin` — die Mitgliederverwaltung pflegt diese Liste. Der Name
 * bleibt, weil die Regel dieselbe ist (ein Wahrheitswert, fail closed).
 */
export function verwaltungSichtbar(istMitgliederverwaltung) {
  return istMitgliederverwaltung === true
}

/**
 * Darf die Oberfläche persönliche Daten beim Server ANFORDERN?
 * Nur Verwaltung UND nur nach ausdrücklichem Einschalten — der Server prüft
 * zusätzlich (`persoenliche_daten` ist dort ebenfalls fail closed).
 */
export function persoenlicheDatenAnfordern(istMitgliederverwaltung, schalter) {
  return istMitgliederverwaltung === true && schalter === true
}

/**
 * Text des Umschalters „persönliche Daten zeigen/verbergen“ — EINE
 * Formulierung, wie auf der früheren Mitgliederseite.
 */
export function datenschalterText(schalter) {
  return schalter === true ? 'Persönliche Daten verbergen' : 'Persönliche Daten anzeigen'
}

/**
 * Statusfilter-Optionen: „Alle“ + je Status die Zahl aus der Server-Antwort.
 * Zahlen sind eine ANZEIGE der Server-Zählung — fehlt sie, steht dort nichts
 * (nie eine erfundene Null). Nur der Endstatus „geloescht“ erscheint, wenn es
 * solche Zeilen wirklich gibt (ein leerer Chip wäre Rauschen).
 *
 * @param {{statusZaehler?: object, gesamtAlle?: number}} werte
 */
export function statusFilterOptionen({ statusZaehler, gesamtAlle } = {}) {
  const zaehler = statusZaehler && typeof statusZaehler === 'object' ? statusZaehler : {}
  const zahl = (wert) => (Number.isFinite(Number(wert)) ? String(Number(wert)) : null)
  const alle = zahl(gesamtAlle)
  const optionen = STATUS_WERTE
    .filter((s) => s !== GELOESCHT_STATUS || Number(zaehler[s] ?? 0) > 0)
    .map((s) => ({
      value: s,
      // Ohne Serverzahl kein Number-Gefühl erzeugen: nur das Wort.
      label: [statusWort(s), zahl(zaehler[s])].filter((t) => t !== null).join(' '),
    }))
  return [{ value: '', label: alle === null ? 'Alle' : `Alle ${alle}` }, ...optionen]
}

/**
 * Sortierung: umschalten A–Z ⇄ Z–A. Liefert den NÄCHSTEN Wert; nur ein
 * ausdrückliches 'desc' gilt als absteigend — alles Unbekannte wird wie die
 * Vorgabe „aufsteigend“ behandelt (der Server tut dasselbe: `sort_order` ist
 * genau dann desc, wenn dort 'desc' steht).
 */
export function naechsteSortierung(sortOrder) {
  return sortOrder === 'desc' ? 'asc' : 'desc'
}

/** Beschriftung des Sortierknopfes (Richtung, die ER einstellt). */
export function sortierBeschriftung(sortOrder) {
  return sortOrder === 'asc' ? 'A–Z' : 'Z–A'
}

/**
 * Form der Liste — nach GESAMTZAHL, nicht nach der aktuellen Seite.
 *
 * `gesamt` ist die Zahl der Treffer der ganzen Suche/Filterung (Server-
 * `total`). Eine gewählte Ansicht (`wunsch`) hat Vorrang; unbekannte Werte
 * fallen auf die Regel nach Gesamtzahl zurück.
 *
 * @param {{gesamt?: number, wunsch?: string}} werte → 'tabelle' | 'karten'
 */
export function listenFormFuer({ gesamt, wunsch } = {}) {
  if (wunsch === 'tabelle' || wunsch === 'karten') return wunsch
  const n = Number(gesamt)
  if (!Number.isFinite(n)) return 'karten'
  return n >= TABELLE_AB_PERSONEN ? 'tabelle' : 'karten'
}

/**
 * Kennt diese Quelle serverseitiges Blättern?
 *  • 'liste'      — ja (start/limit, `total` vom Server).
 *  • 'adressbuch' — nein (höchstens 200 Zeilen, kein `total`).
 * Nur dann darf eine Fußzeile mit „Seite x von y“ und Zurück/Weiter stehen.
 */
export function kenntSeiten(quelle) {
  return quelle === 'liste'
}

/**
 * Was die Fußzeile zeigt, oder null (dann steht keine Fußzeile).
 *
 *  • Ohne Blättern (Adressbuch): NUR die Anzahl — keine Seitenzahl, keine
 *    Knöpfe (Befund 4: „Seite 1 von 2“, „Weiter“ tat nichts).
 *  • Mit Blättern: Anzahl + Seite; `sichtbar`/`gesamt` sagt, wie viel der
 *    aktuellen Seite geladen ist.
 *
 * @param {{quelle?: string, gesamt?: number, sichtbar?: number,
 *          seite?: number, seiten?: number}} werte
 */
export function fusszeileFuer({ quelle, gesamt, sichtbar, seite, seiten } = {}) {
  const g = Number(gesamt) || 0
  if (g <= 0) return null
  const wort = g === 1 ? 'Person' : 'Personen'
  if (!kenntSeiten(quelle)) return `${g} ${wort}`
  const s = Math.max(1, Number(seite) || 1)
  const n = Math.max(1, Number(seiten) || 1)
  if (typeof sichtbar === 'number' && sichtbar !== g) {
    return `${sichtbar} von ${g} ${wort} · Seite ${s} von ${n}`
  }
  return `${g} ${wort} · Seite ${s} von ${n}`
}

/**
 * Blätter-Knöpfe: mit Blättern wie bisher (erste/letzte Seite deaktiviert);
 * OHNE Blättern beide aus (keine wirkungslosen Knöpfe).
 */
export function blaetterKnopfZustand({ quelle, seite, seiten } = {}) {
  if (!kenntSeiten(quelle)) return { zurueck: false, weiter: false, sichtbar: false }
  const s = Math.max(1, Number(seite) || 1)
  const n = Math.max(1, Number(seiten) || 1)
  return { zurueck: s > 1, weiter: s < n, sichtbar: true }
}

/**
 * Zielseite eines Blätter-Klicks — geprüft, nicht geraten.
 * Unbekannt/unmöglich (unter 1, über der letzten, aktuell) → null.
 */
export function zielSeite(jetzt, ziel, seiten) {
  const n = Number(ziel)
  const jetztSeite = Math.max(1, Number(jetzt) || 1)
  const letzte = Math.max(1, Number(seiten) || 1)
  if (!Number.isFinite(n) || n < 1 || n > letzte || n === jetztSeite) return null
  return n
}

/**
 * Spalten der Personenliste (Reihenfolge = Reihenfolge der Zellen im Markup).
 *
 * Verwaltung (Quelle „Mitgliederliste“, Reihenfolge wie bisher): Name, Status,
 * Gruppen, persönliche Spalten, „Dabei seit“. Persönliche Spalten (Telefon,
 * E-Mail, Adresse, Geburtstag) stehen NUR darin, wenn sie auch angefragt
 * werden — sonst behauptete die Überschrift „E-Mail“, die Zeile zeige sie; sie
 * zeigt dann „nicht angefordert“.
 *
 * Freigabe-Sicht (Adressbuch, alle anderen): Name, E-Mail, Telefon, Ort und —
 * wenn es etwas zu fragen gibt (`anfrage`) — die Aktionsspalte.
 *
 * WARUM DIE SPALTEN HIER STEHEN UND NICHT IM BAUSTEIN (Review zu UI-R7,
 * Punkt 1): Kopf und Zeilen sind getrennte Stellen im Markup. Lagen sie
 * getrennt, driftete der Kopf weg (4 Überschriften, 5 Zellen — „72070
 * Tübingen“ stand unter „Telefon“, der Knopf hatte gar keine). Jetzt kommt
 * beides aus DIESER Funktion, und ein Node-Test vergleicht Kopf und Zellen.
 *
 * @param {{persoenlich?: boolean, anfrage?: boolean}} werte
 */
export function verwaltungSpalten({ persoenlich } = {}) {
  const spalten = [
    { key: 'name', label: 'Name' },
    { key: 'status', label: 'Status' },
    { key: 'gruppen', label: 'Gruppen' },
  ]
  if (persoenlich === true) {
    spalten.push(
      { key: 'telefon', label: 'Telefon' },
      { key: 'email', label: 'E-Mail' },
      { key: 'adresse', label: 'Adresse' },
      { key: 'geburtstag', label: 'Geburtstag' },
    )
  }
  spalten.push({ key: 'dabei', label: 'Dabei seit' })
  return spalten
}

/** Überschrift der Aktionsspalte — für das Auge versteckt, für Vorlesehilfen da. */
export const AKTIONEN_SPALTE = 'Aktionen'

/**
 * Spalten der Freigabe-Sicht (Adressbuch): Name, E-Mail, Telefon, Ort.
 * `anfrage: true` hängt die Aktionsspalte an (R-9: es gibt Personen, die man
 * fragen kann). Ohne Anfrage-Möglichkeit bleibt sie weg — eine leere
 * Knopfspalte wäre eine Behauptung.
 *
 * @param {{anfrage?: boolean}} werte
 */
export function freigabeSpalten({ anfrage } = {}) {
  const spalten = [
    { key: 'name', label: 'Name' },
    { key: 'email', label: 'E-Mail' },
    { key: 'telefon', label: 'Telefon' },
    { key: 'ort', label: 'Ort' },
  ]
  if (anfrage === true) spalten.push({ key: 'aktion', label: AKTIONEN_SPALTE, aktion: true })
  return spalten
}

/**
 * „Adresse“ einer Zeile — Straße/Nr. und PLZ/Ort aus EINER Hand.
 * Sie baut nur, was da ist; fehlt alles, steht ein Gedankenstrich.
 */
export function adressZeile(zeile) {
  const z = zeile || {}
  const teile = []
  const strasse = String(z.strasse ?? z.straße ?? '').trim()
  const nummer = String(z.nummer ?? '').trim()
  if (strasse) teile.push([strasse, nummer].filter(Boolean).join(' '))
  const ort = String(z.ort ?? '').trim()
  if (ort) teile.push(ort)
  return teile.join(', ') || '–'
}

/**
 * Wie viel von der Liste ist geladen (Fußzeile der Verwaltungsliste, wie
 * bisher: „20 von 142 geladen“).
 */
export function ladeStand({ sichtbar, gesamt } = {}) {
  const s = Number(sichtbar) || 0
  const g = Number(gesamt) || 0
  return `${s} von ${g} geladen`
}

/**
 * Ist die Liste am Ende angekommen? Solange `sichtbar < gesamt`, gibt es
 * weitere Zeilen (der „Mehr laden“-Knopf bleibt stehen).
 */
export function weitereVorhanden({ sichtbar, gesamt } = {}) {
  const s = Number(sichtbar) || 0
  const g = Number(gesamt) || 0
  return s < g
}

/**
 * Startfilter aus der Adresse (`#/personen/liste?status=Mitglied`): Kacheln
 * der Übersicht verlinken mit gesetztem Filter. Nur bekannte Status gelten;
 * fehlt der Parameter oder ist er unbekannt, gilt „Alle“ ('').
 */
export function statusAusAdresse(hash) {
  const text = String(hash || '')
  const frage = text.indexOf('?')
  if (frage === -1) return ''
  const wert = new URLSearchParams(text.slice(frage + 1)).get('status') || ''
  return STATUS_WERTE.includes(wert) ? wert : ''
}

/** Adresse mit ersetztem `status` (für `history.replaceState`): der Filter
 *  bleibt im aktuellen Verlaufseintrag, „zurück“ aus dem Detail stellt ihn
 *  wieder her. Leerer Wert entfernt den Parameter. */
export function adresseMitStatus(hash, wert) {
  const [pfad, suche = ''] = String(hash || '').split('?')
  const parameter = new URLSearchParams(suche)
  if (wert) parameter.set('status', wert)
  else parameter.delete('status')
  const rest = parameter.toString()
  return rest ? `${pfad}?${rest}` : pfad
}
