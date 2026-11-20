/**
 * SEC-11 · GEMEINSAME LESER für die Wächter um `call_method`.
 *
 * Eine Stelle für das, was `sec11-get-schreibend` (GET an einen schreibenden
 * Endpunkt) und `sec11d-post-nur-get` (POST an einen GET-only-Endpunkt)
 * GLEICH brauchen:
 *
 *   1. das Inventar `backend/src/diakronos_app/frappe_compat/inventar/
 *      whitelist.json` (erzeugt von tools/whitelist_inventar.py) und
 *   2. die Quelltexte unter `frontend/src` mit Zeilennummern.
 *
 * Bewusst KEINE Kopie in beiden Testdateien: sonst driften die Pfade und die
 * Datei-Endungen auseinander und der eine Wächter prüft etwas anderes als der
 * andere. Reines ESM ohne Abhängigkeiten — läuft mit `node --test` im Image
 * und lokal. (Der Name endet NICHT auf `.test.mjs`, damit die Testliste ihn
 * nicht als eigenen Testlauf einzieht.)
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const WURZEL = new URL('../', import.meta.url)

/** Quelltexte der SPA (`frontend/src`). */
export const SRC = new URL('src/', WURZEL)

/** Das Inventar der whitelist-Funktionen (gleiche Datei für alle SEC-11-Wächter). */
export const INVENTAR = new URL(
  '../backend/src/diakronos_app/frappe_compat/inventar/whitelist.json', WURZEL)

export const SRC_PFAD = fileURLToPath(SRC)
export const INVENTAR_PFAD = fileURLToPath(INVENTAR)

/** Alle Quelltexte unter `verzeichnis` (relativ zu src/), ohne Testdateien. */
export function alleQuellen(verzeichnis = '') {
  const pfad = new URL(verzeichnis, SRC)
  let ausgabe = []
  for (const eintrag of readdirSync(pfad)) {
    const kind = statSync(new URL(eintrag, pfad))
    if (kind.isDirectory()) {
      ausgabe = ausgabe.concat(alleQuellen(verzeichnis + eintrag + '/'))
    } else if (/\.(js|mjs|vue)$/.test(eintrag) && !/\.test\.mjs$/.test(eintrag)) {
      ausgabe.push(verzeichnis + eintrag)
    }
  }
  return ausgabe
}

/** Alle Quellzeilen als `{ datei, nr, zeile }`. */
export function quellzeilen() {
  const ausgabe = []
  for (const rel of alleQuellen()) {
    const text = readFileSync(new URL(rel, SRC), 'utf8')
    text.split('\n').forEach((zeile, i) => ausgabe.push({ datei: rel, nr: i + 1, zeile }))
  }
  return ausgabe
}

/** Das Inventar als Objekt; fehlt die Datei, ist das ein Testfehler. */
export function inventar() {
  if (!existsSync(INVENTAR_PFAD)) {
    throw new Error(
      'inventar/whitelist.json fehlt — tools/whitelist_inventar.py laufen lassen')
  }
  return JSON.parse(readFileSync(INVENTAR_PFAD, 'utf8'))
}

/** Einträge des Inventars nach Funktionsnamen (`name`). */
export function eintraegeNachName() {
  const karte = new Map()
  for (const eintrag of inventar().eintraege) {
    if (!karte.has(eintrag.name)) karte.set(eintrag.name, [])
    karte.get(eintrag.name).push(eintrag)
  }
  return karte
}

/**
 * Namen der Endpunkte, deren DEKLARIERTE `methoden` den POST NICHT enthalten
 * (typisch: `["GET"]`).
 *
 * Nur die DEKLARATION zählt: ein Eintrag ohne `methoden` (Feld `null`, also
 * die Frappe-Vorgabe GET **oder** POST) nimmt sehr wohl POST an — ihn hier
 * aufzunehmen machte den Wächter zu einem Verbotskatalog für das halbe
 * Backend. Datensätze ohne Namen (z. B. `logout` als Route) fallen raus: der
 * Wächter prüft Methoden, keine Routen.
 */
export function nurGetNamen() {
  const namen = new Set()
  for (const eintrag of inventar().eintraege) {
    const methoden = Array.isArray(eintrag.methoden) ? eintrag.methoden : null
    if (!methoden || !eintrag.name) continue
    if (!methoden.some((m) => String(m).toUpperCase() === 'POST')) namen.add(eintrag.name)
  }
  return namen
}

/** Der Inventar-Eintrag zu einem Endpunktnamen (für Meldungen/Tests). */
export function eintragZuName(name) {
  const treffer = eintraegeNachName().get(name) || []
  return treffer.length ? treffer[0] : null
}
