/**
 * gruppenAnlegen — reine Logik für „Neue Gruppe/Untergruppe“ in der
 * Listenansicht (DEV-1, Befund DMB-7bc7150a146e) und für die Filterchips
 * (Befund DMB-c6f79cf0f5c6).
 *
 * Kein Vue, kein DOM: die Darstellung sitzt in `GruppeAnlegenDialog.vue`
 * (ein Dialog für Liste UND Bereichs-Rahmen) bzw. in `pages/Gruppen.vue`.
 */

/** Wie `filterChips.chipName`: leere Angaben gelten als eigener Bereich. */
function alsText(wert) {
  if (wert === null || wert === undefined) return ''
  const art = typeof wert
  if (art !== 'string' && art !== 'number') return ''
  return String(wert).trim()
}

/**
 * Die tatsächlich vorkommenden Dienstbereiche einer Gruppenliste, deutsch
 * sortiert und ohne Doppel.
 *
 * Befund DMB-c6f79cf0f5c6: Bei nur EINEM Bereich (alle Gruppen in
 * „Jugendarbeit“) hat die Chip-Zeile keine sichtbare Wirkung — jede Auswahl
 * zeigt dieselben Gruppen. Dann bleibt die Zeile weg (`length > 1`).
 */
export function bereicheAus(eintraege = [], schluessel = (e) => e && e.dienstbereich_name) {
  const liste = Array.isArray(eintraege) ? eintraege : []
  const namen = new Set()
  for (const e of liste) namen.add(alsText(schluessel(e)))
  return [...namen].sort((a, b) => a.localeCompare(b, 'de'))
}

/** Entscheidung für die Chip-Zeile: erst ab zwei Bereichen ist Filtern sinnvoll. */
export function zeigeChips(eintraege = [], schluessel) {
  return bereicheAus(eintraege, schluessel).length > 1
}

/**
 * Anlege-Rechte des Servers (`create_permissions` aus
 * `get_gruppen_page_data` / `get_user_create_permissions`) auf die Form
 * bringen, die die Vorlage braucht.
 *
 * Der Server entscheidet; die Oberfläche zeigt nur, was er erlaubt. Fehlt die
 * Angabe (oder kommt sie als Unsinn), gilt „nein“ — fail closed.
 */
export function anlegenRechte(perms) {
  const p = perms && typeof perms === 'object' ? perms : {}
  return {
    canCreateGruppe: p.can_create_gruppe === true,
    canCreateUntergruppe: p.can_create_untergruppe === true,
    canCreateDienstbereich: p.can_create_dienstbereich === true,
    // `can_create_any` des Servers gilt, sonst ergibt es sich aus den Teilen.
    canCreateAny: p.can_create_any === true
      || p.can_create_gruppe === true
      || p.can_create_untergruppe === true
      || p.can_create_dienstbereich === true,
  }
}

/**
 * Der Server-Aufruf eines Anlege-Formulars (ANGELEGTYP → Methode + Parameter).
 *
 * Einzige Quelle für beide Oberflächen: der Organigramm-Dialog und
 * `GruppeAnlegenDialog.vue` fragen hier. Die Feldnamen sind die des Servers
 * (UXD-R4): `dienstbereich` statt `parent`, `gruppe` statt `parent`.
 */
export const ANLEGE_AUFRUFE = {
  dienstbereich: 'diakronos.diakonos.api.gruppen.create_dienstbereich',
  gruppe: 'diakronos.diakonos.api.gruppen.create_gruppe',
  untergruppe: 'diakronos.diakonos.api.gruppen.create_untergruppe',
}

/**
 * Parameter und Toast-Text für einen Anlege-Aufruf.
 * @param {'dienstbereich'|'gruppe'|'untergruppe'} typ
 * @param {{name:string, parent?:string, farbe?:string}} f
 */
export function anlegeAufruf(typ, f = {}) {
  const name = String(f.name || '').trim()
  if (typ === 'dienstbereich') {
    return {
      methode: ANLEGE_AUFRUFE.dienstbereich,
      parameter: { name, farbe: f.farbe || '' },
      toast: 'Dienstbereich angelegt',
    }
  }
  if (typ === 'untergruppe') {
    return {
      methode: ANLEGE_AUFRUFE.untergruppe,
      parameter: { name, gruppe: f.parent },
      toast: 'Untergruppe angelegt',
    }
  }
  return {
    methode: ANLEGE_AUFRUFE.gruppe,
    parameter: { name, dienstbereich: f.parent },
    toast: 'Gruppe angelegt',
  }
}

