/**
 * UX2b — „Rückgängig“ nach dem Löschen (Papierkorb im Server, höchstens 7 Tage).
 *
 * Der Server legt gelöschte Zeilen in den Papierkorb (``geloescht_am``) und
 * liefert beim Löschen ``wiederherstellbar_bis``. Die Oberfläche meldet das
 * ehrlich („in den Papierkorb gelegt — bis … rückgängig zu machen“) statt
 * „unwiderruflich gelöscht“, und das Zurückholen läuft über die
 * ``<bereich>.wiederherstellen_*``-Endpunkte.
 *
 * TWO STATUS-WEGE, EINE Meldung (Prinzip S4): beide Seiten — Liste und Detail —
 * benutzen dieselbe Funktion, damit Text und Wirkung nie auseinanderlaufen.
 */
/**
 * Der API-Aufruf wird ERST BEI GEBRAUCH geladen (dynamischer Import).
 *
 * `useApi.js` zieht die Vue-Laufzeit und die Sitzungs-Schicht mit; ein
 * statischer Import machte dieses reine Textmodul in einem Node-Test ohne
 * `node_modules` unladen (UX2b-Wächter: `frontend/tests/ux2b-papierkorb.test.mjs`
 * prüft Frist, Meldung und Endpunkte ohne Browser).
 */
async function apiCall(...argumente) {
  const modul = await import('./useApi.js')
  return modul.apiCall(...argumente)
}

/**
 * Frist aus der Antwort des Servers als deutschen Text („am 11.11.2026“).
 *
 * Leere oder unbrauchbare Angaben ergeben ``''`` — die Meldung sagt dann nur
 * „im Papierkorb“ und erfindet kein Datum.
 */
export function fristText(wiederherstellbarBis) {
  const roh = String(wiederherstellbarBis || '').trim()
  if (!roh) return ''
  // Serverformat: "JJJJ-MM-TT HH:MM:SS" (lokale Zeit, ohne Zone).
  const treffer = /^(\d{4})-(\d{2})-(\d{2})/.exec(roh)
  if (!treffer) return ''
  const [, jahr, monat, tag] = treffer
  return `${tag}.${monat}.${jahr}`
}

/** Meldung nach dem Löschen — sagt genau, was passiert ist. */
export function papierkorbMeldung(titel, wiederherstellbarBis) {
  const wann = fristText(wiederherstellbarBis)
  const name = String(titel || '').trim()
  const anfang = name ? `„${name}“ ist im Papierkorb` : 'Im Papierkorb'
  return wann
    ? `${anfang} — bis zum ${wann} rückgängig zu machen.`
    : `${anfang}.`
}

/**
 * Rückfrage vor dem Löschen: KEIN „unwiderruflich“ mehr (das wäre falsch),
 * aber die Folge wird konkret genannt.
 */
export function loeschFrage(titel, bereich) {
  const name = String(titel || '').trim()
  const was = name ? `„${name}“` : `Diese ${bereich || 'Zeile'}`
  return {
    titel: `${bereich || 'Eintrag'} löschen?`,
    text: `${was} kommt in den Papierkorb und ist 7 Tage lang wiederherstellbar. `
      + 'Danach wird sie endgültig entfernt.',
    aktion: 'In den Papierkorb',
    gefahr: true,
    abbrechen: 'Behalten',
  }
}

/**
 * Endpunkt zum Zurückholen je Bereich (die eine Wahrheit, auch für Tests).
 *
 * Die Schlüssel sind die Bereiche der Karte; der Wert ist der vollständige
 * Aufrufname und der Parameter, den der Server erwartet.
 */
export const WIEDERHERSTELLEN = {
  beitrag: { pfad: 'diakronos.diakonos.api.beitraege.wiederherstellen_beitrag', feld: 'beitrag_id' },
  artikel: { pfad: 'diakronos.diakonos.api.wiki.wiederherstellen_wiki_artikel', feld: 'artikel_id' },
  gruppe: { pfad: 'diakronos.diakonos.api.gruppen.wiederherstellen_gruppe', feld: 'name' },
  termin: { pfad: 'diakronos.kronos.api.event_crud.wiederherstellen_event', feld: 'name' },
  lied: { pfad: 'diakronos.psalmos.api.musik.wiederherstellen_lied', feld: 'lied' },
}

/**
 * Ruft den passenden Wiederherstellen-Endpunkt.
 *
 * Rückgabe ``{ok: true}`` oder ``{ok: false, fehler: '<Klartext>'}`` — die
 * Oberfläche zeigt den Fehler als Meldung, statt still nichts zu tun.
 */
export async function wiederherstellen(bereich, kennung) {
  const eintrag = WIEDERHERSTELLEN[bereich]
  if (!eintrag) return { ok: false, fehler: 'Für diesen Bereich gibt es kein Zurückholen.' }
  try {
    await apiCall(eintrag.pfad, { [eintrag.feld]: kennung })
    return { ok: true }
  } catch (fehler) {
    return { ok: false, fehler: fehler?.message || 'Zurückholen fehlgeschlagen.' }
  }
}
