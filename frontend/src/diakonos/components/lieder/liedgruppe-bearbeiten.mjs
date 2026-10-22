/**
 * P1-10 — reine Formular-Logik der Liedgruppen-Pflege (node-testbar, ohne Vue).
 *
 * UXM-R9: Liedgruppen koennen angelegt, geaendert, geloescht und mit Liedern
 * gefuellt werden. Die Komponente `components/lieder/LiedgruppeBearbeiten.vue`
 * rendert nur; alles Rechnen und Uebersetzen in API-Nutzlasten steht hier.
 *
 * Bewusste Regeln:
 *  - Der Gruppenname ist Pflicht (der Server lehnt einen leeren Namen ebenso ab).
 *  - Der Typ bestimmt den Charakter (Buch/Projekt/Sammlung/frei ...); die
 *    erlaubten Werte liegen in `LIEDGRUPPE_TYPEN` und stimmen mit dem Server
 *    ueberein (`api.psalmos.musik.LIEDGRUPPE_TYPEN`).
 *  - Die Liederzuordnung ist eine geordnete Liste; `reihenfolge` ist die
 *    Listenposition (1..n), weil der Server danach sortiert.
 */

//: Typ-Werte wie im Backend (`api.psalmos.musik.LIEDGRUPPE_TYPEN`).
export const LIEDGRUPPE_TYPEN = [
  'Gesangbuch', 'Buch', 'Projekt', 'Sammlung', 'Reihe', 'Mappe',
  'Werk', 'Musical', 'Kantate', 'Sonstiges',
]

//: Klartext-Hilfe je Typ (was ist gemeint — keine Fachbegriffe).
export const TYP_HILFEN = {
  Gesangbuch: 'Ein gebundenes Liederbuch (z. B. das Gesangbuch der Gemeinde).',
  Buch: 'Ein Liederbuch oder Heft, das als eigenes Werk geführt wird.',
  Projekt: 'Lieder für ein bestimmtes Vorhaben (z. B. Freizeit, Musical-Aufführung).',
  Sammlung: 'Eine lose Sammlung, z. B. „Lieder für Trauungen“.',
  Reihe: 'Eine feste Reihe, z. B. eine Andachtsreihe.',
  Mappe: 'Eine Mappe oder ein Ordner mit Liedern.',
  Werk: 'Ein größeres Werk (Oratorium, Kantate, Musical).',
  Musical: 'Ein Musical mit Liedern und Rollen.',
  Kantate: 'Eine Kantate mit Liedern und Rollen.',
  Sonstiges: 'Etwas anderes — der Name erklärt es.',
}

//: Status-Werte wie im Backend.
export const LIEDGRUPPE_STATUS = ['Aktiv', 'Archiviert']

/** Leere Liedgruppe fuer „Neue Liedgruppe". */
export function leereGruppe() {
  return {
    name: '',
    gruppenname: '',
    typ: 'Sammlung',
    status: 'Aktiv',
    dauer_minuten: '',
    komponist: '',
    textautor: '',
    verlag: '',
    lizenzhinweis: '',
    beschreibung: '',
    lieder: [],
  }
}

/** Formular aus einem Liedgruppen-Detail (get_liedgruppe_detail) aufbauen. */
export function gruppeAusDetail(detail = {}) {
  const basis = leereGruppe()
  const g = detail?.liedgruppe || {}
  return {
    ...basis,
    name: String(g.name || ''),
    gruppenname: String(g.gruppenname || ''),
    typ: g.typ || 'Sammlung',
    status: g.status || 'Aktiv',
    dauer_minuten: g.dauer_minuten ?? '',
    komponist: String(g.komponist || ''),
    textautor: String(g.textautor || ''),
    verlag: String(g.verlag || ''),
    lizenzhinweis: String(g.lizenzhinweis || ''),
    beschreibung: String(g.beschreibung || ''),
    lieder: (detail?.lieder || []).map((row, i) => ({
      lied: String(row?.lied || ''),
      titel: String(row?.titel || ''),
      fassung: row?.fassung || '',
      nummer: row?.nummer ?? '',
      szene: row?.szene || '',
      notiz: row?.notiz || '',
      reihenfolge: Number(row?.reihenfolge) || i + 1,
    })),
  }
}

/** Ist der aktuelle Stand eine Neuanlage? */
export function istNeu(formular) {
  return !String(formular?.name || '').trim()
}

/** Formular pruefen → { fehler: {feld: meldung}, ok }. */
export function pruefen(formular) {
  const fehler = {}
  const name = String(formular?.gruppenname || '').trim()
  if (!name) fehler.gruppenname = 'Bitte einen Namen für die Liedgruppe eintragen.'
  if (name.length > 140) fehler.gruppenname = 'Der Name ist zu lang (höchstens 140 Zeichen).'
  if (formular?.typ && !LIEDGRUPPE_TYPEN.includes(formular.typ)) {
    fehler.typ = 'Diesen Typ gibt es nicht.'
  }
  const dauer = formular?.dauer_minuten
  if (dauer !== '' && dauer !== null && dauer !== undefined) {
    const n = Number(dauer)
    if (!Number.isFinite(n) || n < 0 || n > 600) {
      fehler.dauer_minuten = 'Bitte eine Dauer zwischen 0 und 600 Minuten angeben.'
    }
  }
  return { fehler, ok: Object.keys(fehler).length === 0 }
}

/** Nutzlast fuer `save_liedgruppe`. */
export function nutzlast(formular) {
  const dauer = formular?.dauer_minuten
  const werte = {
    gruppenname: String(formular?.gruppenname || '').trim(),
    typ: formular?.typ || 'Sammlung',
    status: formular?.status || 'Aktiv',
    komponist: String(formular?.komponist || '').trim(),
    textautor: String(formular?.textautor || '').trim(),
    verlag: String(formular?.verlag || '').trim(),
    lizenzhinweis: String(formular?.lizenzhinweis || '').trim(),
    beschreibung: String(formular?.beschreibung || '').trim(),
    lieder: zuordnungenNormalisieren(formular?.lieder || []),
  }
  if (dauer !== '' && dauer !== null && dauer !== undefined) {
    werte.dauer_minuten = Number(dauer)
  }
  if (formular?.name) werte.name = formular.name
  return werte
}

/** Liederzuordnung normalisieren: nur echte Lieder, reihenfolge = 1..n. */
export function zuordnungenNormalisieren(lieder) {
  return (lieder || [])
    .filter((z) => z && String(z.lied || '').trim())
    .map((z, i) => {
      const zeile = { lied: String(z.lied).trim(), reihenfolge: i + 1 }
      if (z.fassung) zeile.fassung = z.fassung
      if (z.nummer !== '' && z.nummer !== null && z.nummer !== undefined) zeile.nummer = z.nummer
      if (z.szene) zeile.szene = z.szene
      if (z.notiz) zeile.notiz = z.notiz
      return zeile
    })
}

/**
 * Ein Lied an die Zuordnung anhaengen (Duplikate werden uebersprungen).
 * Liefert eine neue Liste — die Reihenfolge bleibt die Reihenfolge des
 * Hinzufuegens, weil der Server danach sortiert.
 */
export function liedHinzufuegen(lieder, lied) {
  const name = String(lied?.name || lied?.lied || '').trim()
  if (!name) return [...(lieder || [])]
  if ((lieder || []).some((z) => String(z.lied) === name)) return [...lieder]
  return [...(lieder || []), {
    lied: name, titel: String(lied?.titel || ''), fassung: lied?.fassung || '',
    nummer: lied?.gesangbuch_nummer ?? lied?.nummer ?? '', szene: '', notiz: '',
  }]
}

/** Ein Lied an einer Stelle entfernen und neu durchnummerieren. */
export function liedEntfernen(lieder, index) {
  const liste = (lieder || []).filter((_, i) => i !== index)
  return liste.map((z, i) => ({ ...z, reihenfolge: i + 1 }))
}

/** Ein Lied eine Stelle verschieben (richtung: -1 | +1). */
export function liedVerschieben(lieder, index, richtung) {
  const liste = [...(lieder || [])]
  const ziel = index + richtung
  if (index < 0 || index >= liste.length || ziel < 0 || ziel >= liste.length) return liste
  const [element] = liste.splice(index, 1)
  liste.splice(ziel, 0, element)
  return liste.map((z, i) => ({ ...z, reihenfolge: i + 1 }))
}
