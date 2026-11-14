/**
 * UI-R1 — Gruppen-Einstellungen: Rollen (HV, MV, GL) — reine Logik.
 *
 * Diese Datei entscheidet NICHTS über Rechte. Sie ordnet nur, was der Server
 * liefert, und macht aus einer Server-Antwort eine Zeile der Oberfläche:
 *
 *   * `rollenOrdnen`     HV oben, dann MV, dann GL je Untergruppe;
 *   * `darfHinzufuegen`/
 *     `darfEntfernen`    welcher Knopf gezeigt wird (die Server-Endpunkte
 *                        weisen Unbefugte ohnehin mit 403/417 ab);
 *   * `hvUebertragen`    Sicherheitsabfrage: der getippte Name muss zur neuen
 *                        Person passen, sonst wird nicht gesendet;
 *   * `rollenOptionenFuer` Namen für die Auswahl (Personen-Auswahl kennt nur
 *                        `benutzer` + `name`).
 *
 * Ohne Vue, damit `node --test` die Regeln prüft (tests/ui-r1-*.test.mjs).
 */

/** Reihenfolge der Rollen in der Anzeige (HV zuerst). */
export const ROLLEN_RANG = { HV: 0, MV: 1, GL: 2 };

/** Ausgeschriebene Rollen (Kartenbegriffe, Manuel 11.11.). */
export const ROLLEN_NAME = {
  HV: 'Hauptverantwortliche/r',
  MV: 'Mitverantwortliche/r',
  GL: 'Gruppenleitung',
};

/** Kurzform für Chips/Badges — die Langform steht im Erklärtext. */
export const ROLLEN_KURZ = { HV: 'HV', MV: 'MV', GL: 'GL' };

/**
 * Erklärtext zum HV-Amt: es kann nur übertragen, nicht entfernt werden.
 * EINE Quelle für Karte, Dialog und Test.
 */
export const HV_HINWEIS =
  'Das HV-Amt kann nur übertragen, nicht entfernt werden. '
  + 'Wer es abgibt, wird Mitverantwortliche/r oder scheidet ganz aus der Rolle.'

/** Wie die Seite heißt (Reiter und Adresse `#/gruppe/<id>/einstellungen`). */
export const EINSTELLUNGEN_REITER = 'einstellungen'

/** Normalisiert einen Namen für den Vergleich in der Sicherheitsabfrage. */
export function normalName(wert) {
  return String(wert ?? '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
}

/**
 * Rollen einer Gruppe in Anzeige-Reihenfolge.
 *
 * R-12c: jede Zeile bringt `name` (Anzeigename) und `untergruppe_name` mit;
 * `benutzer` (Kontokennung für die Knöpfe) gibt es nur für HV/MV/Admin —
 * Lesende bekommen `null`. Es wird deshalb NIE eine Kennung als Name
 * angezeigt, wenn der Server einen Namen liefert.
 *
 * @param {Array<{benutzer?: string|null, rolle: string, untergruppe?: string|null, name?: string, untergruppe_name?: string|null}>} rollen
 * @param {{nurUntergruppe?: string}} [optionen] nur die GL DIESER Untergruppe
 * @returns {{hv: object[], mv: object[], gl: object[], glJeUntergruppe: Array<{untergruppe: string, eintraege: object[]}>, alle: object[], anzahl: number}}
 */
export function rollenOrdnen(rollen, optionen = {}) {
  const nurUntergruppe = optionen?.nurUntergruppe ? String(optionen.nurUntergruppe) : ''
  const sauber = (Array.isArray(rollen) ? rollen : [])
    .filter((r) => r && ROLLEN_RANG[r.rolle] !== undefined)
    .filter((r) => !nurUntergruppe || (r.rolle === 'GL' && String(r.untergruppe || '') === nurUntergruppe))
    .map((r) => ({
      benutzer: r.benutzer ? String(r.benutzer) : null,
      rolle: r.rolle,
      untergruppe: r.untergruppe || null,
      untergruppeName: r.untergruppe_name || null,
      // Der Server liefert den Anzeigenamen; fehlt er, bleibt die Zeile
      // namenlos statt eine Kontokennung (E-Mail) zu verraten.
      name: String(r.name || 'Unbekannte Person'),
    }))

  const nachName = (a, b) => a.name.localeCompare(b.name, 'de')
  const hv = sauber.filter((r) => r.rolle === 'HV').sort(nachName)
  const mv = sauber.filter((r) => r.rolle === 'MV').sort(nachName)
  const gl = sauber.filter((r) => r.rolle === 'GL').sort(nachName)

  // GL je Untergruppe, Untergruppen alphabetisch; ohne Untergruppe zuletzt
  // (sollte der Server das je liefern, fällt der Eintrag nicht weg).
  const gruppen = new Map()
  for (const eintrag of gl) {
    const schluessel = eintrag.untergruppe || ''
    if (!gruppen.has(schluessel)) gruppen.set(schluessel, [])
    gruppen.get(schluessel).push(eintrag)
  }
  const glJeUntergruppe = [...gruppen.entries()]
    .map(([untergruppe, eintraege]) => ({
      untergruppe,
      // Anzeigename der Untergruppe (R-12c) — sonst die Kennung.
      anzeige: eintraege.find((e) => e.untergruppeName)?.untergruppeName || untergruppe,
      eintraege,
    }))
    .sort((a, b) => {
      if (!a.untergruppe) return 1
      if (!b.untergruppe) return -1
      return String(a.anzeige).localeCompare(String(b.anzeige), 'de')
    })

  return {
    hv,
    mv,
    gl,
    glJeUntergruppe,
    alle: [...hv, ...mv, ...gl],
    anzahl: sauber.length,
  }
}

/**
 * Darf „MV hinzufügen/entfernen“ gezeigt werden?
 * Serverfeld `darf_hv_mv_ernennen` (Aktion „rollen“ an der Gruppe — nur HV).
 */
export function darfMvPflegen(daten) {
  return Boolean(daten?.darf_hv_mv_ernennen)
}

/**
 * Darf „GL hinzufügen/entfernen“ für eine Untergruppe gezeigt werden?
 * Serverfeld `darf_verwalten` (HV/MV der Gruppe bzw. Admin).
 */
export function darfGlPflegen(daten) {
  return Boolean(daten?.darf_verwalten)
}

/**
 * Darf das HV-Amt übertragen werden? Dieselbe Aktion wie MV ernennen
 * (`darf_hv_mv_ernennen`); der Server prüft zusätzlich, dass nur der
 * amtierende HV oder der Administrator überträgt.
 */
export function darfHvUebertragen(daten) {
  return Boolean(daten?.darf_hv_mv_ernennen)
}

/**
 * Darf die Einstellungsseite (Reiter) überhaupt erscheinen?
 * Sie ist für HV/MV/GL und Admin gedacht; ein reines Mitglied sieht den
 * Reiter nicht. Grundlage sind die Rechtefelder aus
 * `get_gruppe_detail.rechte` (`verwalten`, `rollen`) — dieselbe Antwort, die
 * die Gruppenseite ohnehin lädt; durchgesetzt wird serverseitig.
 */
export function darfEinstellungenSehen(daten) {
  return Boolean(daten?.darf_verwalten || daten?.darf_hv_mv_ernennen)
}

/**
 * Sicherheitsabfrage der HV-Übertragung.
 *
 * Der getippte Name muss zur gewählten Person passen (Vergleich ohne
 * Groß/Klein und mit zusammengefassten Leerzeichen) — sonst bleibt „HV-Amt
 * übertragen“ gesperrt. So kann niemand aus Versehen die falsche Person
 * einsetzen.
 *
 * @returns {{ok: boolean, grund: ''|'person'|'bestaetigung'}}
 */
export function hvUebertragenPruefen({ neuerHv, name, eingabe }) {
  if (!neuerHv || !normalName(name)) return { ok: false, grund: 'person' }
  if (normalName(eingabe) !== normalName(name)) return { ok: false, grund: 'bestaetigung' }
  return { ok: true, grund: '' }
}

/**
 * Personen-Auswahl (get_personen_auswahl) in Auswahlzeilen übersetzen.
 * Der Server liefert nur `benutzer` und `name` — mehr wird hier nicht
 * erfunden.
 */
export function personenAuswahl(personen) {
  return (Array.isArray(personen) ? personen : [])
    .filter((p) => p && p.benutzer && p.name)
    .map((p) => ({ benutzer: String(p.benutzer), name: String(p.name) }))
}

/**
 * Personen, die für eine Rolle noch in Frage kommen: wer die Rolle schon hat,
 * steht nicht in der Hinzufügen-Liste.
 */
export function freiePersonen(personen, vorhandene, rollen = null) {
  const belegt = new Set(
    (Array.isArray(vorhandene) ? vorhandene : [])
      .filter((v) => !rollen || rollen.includes(v.rolle))
      .map((v) => v.benutzer),
  )
  return personenAuswahl(personen).filter((p) => !belegt.has(p.benutzer))
}
