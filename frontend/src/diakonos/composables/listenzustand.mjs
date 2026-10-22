/**
 * listenzustand — Such- und Filterzustand in der Adresse (OP-UI-8, Standard S9).
 *
 * Befund: Bei „Lieder“ und „Gruppen“ ging die Suche nach „Detail ansehen →
 * Zurück“ verloren, während sie bei Mitgliedern blieb (Modulzustand). Die
 * Adresse ist der dauerhafte Ort: `#/lieder?q=Herr&gruppenname=…`. Sie
 * überlebt das Öffnen eines Details, das Zurückkehren und lässt sich teilen.
 *
 * Reine Funktionen (ohne Vue/DOM-Abhängigkeit beim Auswerten) — der Aufrufer
 * reicht den Hash-String herein. So ist die Logik ohne Browser prüfbar.
 */

/** Befehlsnamen, die wir in der Adresse zulassen (Reihenfolge = Schreib-Reihenfolge). */
export const LISTEN_SCHLUESSEL = ['q', 'gruppenname', 'kategorie', 'anlass', 'rechte_status']

/** Abfrageteil eines Hash-Strings zerlegen (`#/lieder?a=1` → URLSearchParams). */
export function adresseLesen(hash) {
  const roh = String(hash || '')
  const frage = roh.indexOf('?')
  if (frage === -1) return new URLSearchParams()
  return new URLSearchParams(roh.slice(frage + 1))
}

/**
 * Zustand → Abfrageteil.
 * Leere Werte werden weggelassen, damit die Adresse sauber bleibt
 * (`#/lieder`, nicht `#/lieder?q=&kategorie=`).
 */
export function adresseSchreiben(pfad, zustand = {}) {
  const params = new URLSearchParams()
  for (const schluessel of LISTEN_SCHLUESSEL) {
    const wert = zustand[schluessel]
    if (wert === null || wert === undefined || wert === '') continue
    params.set(schluessel, String(wert))
  }
  const frage = params.toString()
  return frage ? `${pfad}?${frage}` : pfad
}

/** Nur den Pfad ohne Abfrageteil. */
export function pfadOhneAbfrage(hash) {
  return String(hash || '').split('?')[0]
}

/**
 * Zustand aus einem Hash lesen. Fehlende Schlüssel bleiben leer.
 * Gibt genau die Schlüssel aus LISTEN_SCHLUESSEL zurück — nichts anderes.
 */
export function zustandAusAdresse(hash) {
  const params = adresseLesen(hash)
  const zustand = {}
  for (const schluessel of LISTEN_SCHLUESSEL) zustand[schluessel] = params.get(schluessel) || ''
  return zustand
}
