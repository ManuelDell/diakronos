/**
 * LI1 — reine Formular-Logik des Lied-Bearbeitens (node-testbar, ohne Vue).
 *
 * EINE Wahrheit für das Anlegen UND Ändern eines Liedes: Die Komponente
 * `components/lieder/LiedBearbeiten.vue` rendert nur; alles Rechnen,
 * Prüfen und Übersetzen in API-Nutzlasten steht hier.
 *
 * Bewusste Grenzen (siehe „Bekannte Grenzen“ in der Karte):
 *  - Titel ist Pflicht (Server lehnt einen leeren Titel ebenfalls ab).
 *  - Quelle 'kopie' blendet Buch/Nummer/Seite aus UND leert sie — sonst
 *    stünde nach dem Umschalten noch eine alte Nummer in der Nutzlast.
 *  - Der Server schreibt Buch/Nummer/Seite als einfache Felder; das Formular
 *    schickt sie deshalb IMMER mit (auch leer), damit ein Wechsel auf „Kopie“
 *    die alten Angaben wirklich entfernt.
 */

import { liedAnzeige, istKopie } from '../planrahmen/lied-anzeige.mjs'

/* ── Quellen (LN1) ───────────────────────────────────────────────────────── */

export const QUELLEN = [
  { wert: 'buch', label: 'Liederbuch / Heft (mit Nummer)', hilfe: 'Das Lied steht in einem Buch und hat dort eine Nummer.' },
  { wert: 'kopie', label: 'Kopie / Einzelblatt (ohne Nummer)', hilfe: 'Loses Blatt oder Einzelblatt — es gibt keine Buchnummer.' },
  { wert: 'ohne', label: 'Ohne Angabe', hilfe: 'Noch nicht gepflegt. Später änderbar.' },
]

/** Hat das Lied eine Nummer? → nur bei 'buch' sind Buch/Nummer/Seite sinnvoll. */
export function quellenfelderSichtbar(quelle) {
  return quelle === 'buch'
}

/** Quellen-Beschriftung (Klartext, keine Fachbegriffe). */
export function quelleLabel(quelle) {
  const treffer = QUELLEN.find((q) => q.wert === quelle)
  return treffer ? treffer.label : QUELLEN[2].label
}

/* ── Strophen ────────────────────────────────────────────────────────────── */

export const STROPHEN_TYPEN = ['Strophe', 'Refrain', 'Bridge']

/**
 * Freie Eingabe in einen bekannten Strophen-Typ übersetzen.
 * Unbekanntes bleibt erhalten (nie stillschweigend „Strophe“ nennen).
 */
export function typNormalisieren(typ) {
  const text = String(typ ?? '').trim()
  if (!text) return 'Strophe'
  const treffer = STROPHEN_TYPEN.find((t) => t.toLowerCase() === text.toLowerCase())
  return treffer || text
}

/** Neue, leere Strophe ans Ende. */
export function stropheHinzufuegen(strophen, typ = 'Strophe') {
  const liste = Array.isArray(strophen) ? strophen : []
  const naechste = liste.reduce((m, s) => Math.max(m, Number(s?.nummer) || 0), 0) + 1
  return [...liste, { nummer: naechste, typ: typNormalisieren(typ), text: '', sprache: '', nur_chor: false }]
}

/** Strophe an einer Stelle entfernen und neu durchnummerieren. */
export function stropheEntfernen(strophen, index) {
  const liste = (Array.isArray(strophen) ? strophen : []).filter((_, i) => i !== index)
  return strophenNummerieren(liste)
}

/** Strophe eine Stelle nach oben/unten schieben (richtung: -1 | +1). */
export function stropheVerschieben(strophen, index, richtung) {
  const liste = [...(Array.isArray(strophen) ? strophen : [])]
  const ziel = index + richtung
  if (index < 0 || index >= liste.length || ziel < 0 || ziel >= liste.length) return liste
  const [element] = liste.splice(index, 1)
  liste.splice(ziel, 0, element)
  return strophenNummerieren(liste)
}

/** fortlaufende Nummern 1..n (Reihenfolge = Liste). */
export function strophenNummerieren(strophen) {
  return (Array.isArray(strophen) ? strophen : []).map((s, i) => ({ ...s, nummer: i + 1 }))
}

/* ── Material (Noten/Audio/Notensatz) ────────────────────────────────────── */

/** Material nach Art für die Anzeige gruppieren (Reihenfolge bleibt stabil). */
export function materialNachArt(material) {
  const gruppen = new Map()
  for (const m of material || []) {
    const art = m?.art || 'sonstiges'
    if (!gruppen.has(art)) gruppen.set(art, [])
    gruppen.get(art).push(m)
  }
  return [...gruppen.entries()].map(([art, eintraege]) => ({ art, eintraege }))
}

/** Haben zwei Dateinamen dieselbe Endung? (Auswahl der richtigen Material-Art) */
export function endungPasst(dateiname, endungen) {
  const endung = ('.' + String(dateiname || '').split('.').pop()).toLowerCase()
  return (endungen || []).map((e) => e.toLowerCase()).includes(endung)
}

/* ── Formular ⇄ Nutzlast ─────────────────────────────────────────────────── */

/** Leeres Formular für „Neues Lied“. */
export function leeresFormular() {
  return {
    name: '',
    titel: '',
    alternativtitel: '',
    quelle: 'ohne',
    buch: '',
    gesangbuch_nummer: '',
    seite: '',
    ccli_nummer: '',
    notiz: '',
    aktiv: true,
    kategorien: [],
    anlaesse: [],
    strophen: [],
  }
}

/**
 * Formular aus einem Lied-Detail (get_lied_detail) aufbauen.
 * Fehlt die Quelle (Altbestand), wird sie aus Buch/Nummer/Seite abgeleitet —
 * nie umgekehrt (die Anzeige verlässt sich auf den Serverwert).
 */
export function formularAusLied(lied = {}, strophen = []) {
  const basis = leeresFormular()
  const quelle = String(lied?.quelle || '').trim() || ableiteteQuelle(lied)
  return {
    ...basis,
    name: String(lied?.name || ''),
    titel: String(lied?.titel || ''),
    alternativtitel: String(lied?.alternativtitel || ''),
    quelle,
    buch: quelle === 'buch' ? String(lied?.buch || '') : '',
    gesangbuch_nummer: quelle === 'buch' ? String(lied?.gesangbuch_nummer || '') : '',
    seite: quelle === 'buch' ? String(lied?.seite || '') : '',
    ccli_nummer: String(lied?.ccli_nummer || ''),
    notiz: String(lied?.notiz || ''),
    aktiv: lied?.aktiv === undefined ? true : !!lied.aktiv,
    kategorien: [...(lied?.kategorien || [])],
    anlaesse: [...(lied?.anlaesse || [])],
    strophen: strophenNummerieren((strophen || []).map((s) => ({
      nummer: s?.nummer, typ: typNormalisieren(s?.typ), text: String(s?.text || ''),
      sprache: String(s?.sprache || ''), nur_chor: !!s?.nur_chor,
    }))),
  }
}

/** Quelle aus vorhandenen Angaben ableiten (nur Vorbelegung, nie Wahrheit). */
export function ableiteteQuelle(lied = {}) {
  if (String(lied?.quelle || '').trim()) return String(lied.quelle).trim()
  if (lied?.buch || lied?.gesangbuch_nummer || lied?.seite) return 'buch'
  return 'ohne'
}

/**
 * Beim Wechsel der Quelle Buch/Nummer/Seite leeren, wenn sie ausgeblendet sind.
 * Ein ausgeblendetes Feld darf nie unbemerkt weiterleben.
 */
export function quelleGewechselt(formular, neueQuelle) {
  if (neueQuelle === 'buch') return { ...formular, quelle: 'buch' }
  return { ...formular, quelle: neueQuelle, buch: '', gesangbuch_nummer: '', seite: '' }
}

/** Verständliche Kennung des aktuellen Formularstands ('JN 1297', 'Kopie', ''). */
export function formularAnzeige(formular) {
  return liedAnzeige({
    quelle: formular?.quelle, buch: formular?.buch,
    gesangbuch_nummer: formular?.gesangbuch_nummer, seite: formular?.seite,
  })
}

/** Ist der aktuelle Formularstand eine Kopie? */
export function formularIstKopie(formular) {
  return istKopie({ quelle: formular?.quelle })
}

/**
 * Formular prüfen. Liefert { fehler: {feld: meldung}, ok: bool }.
 * Der einzige Pflichtwert ist der Titel — alles andere darf leer bleiben.
 */
export function pruefen(formular) {
  const fehler = {}
  if (!String(formular?.titel || '').trim()) {
    fehler.titel = 'Bitte einen Titel eintragen.'
  }
  if (String(formular?.titel || '').trim().length > 140) {
    fehler.titel = 'Der Titel ist zu lang (höchstens 140 Zeichen).'
  }
  for (const [i, s] of (formular?.strophen || []).entries()) {
    if (!String(s?.text || '').trim()) {
      fehler['strophe-' + i] = `Strophe ${i + 1} hat noch keinen Text.`
    }
  }
  return { fehler, ok: Object.keys(fehler).length === 0 }
}

/**
 * Nutzlast für `diakronos.psalmos.api.musik.save_lied`:
 * Anlegen ohne `name`, Ändern mit `name`. Strophen, Kategorien und Anlässe
 * werden immer mitgeschickt (Listen ersetzen den Bestand — eine Wahrheit).
 */
export function nutzlast(formular) {
  const quelle = formular?.quelle || 'ohne'
  const werte = {
    titel: String(formular?.titel || '').trim(),
    alternativtitel: String(formular?.alternativtitel || '').trim(),
    quelle,
    gesangbuch_nummer: quelle === 'buch' ? String(formular?.gesangbuch_nummer || '').trim() : '',
    buch: quelle === 'buch' ? String(formular?.buch || '').trim() : '',
    seite: quelle === 'buch' ? String(formular?.seite || '').trim() : '',
    ccli_nummer: String(formular?.ccli_nummer || '').trim(),
    notiz: String(formular?.notiz || ''),
    aktiv: formular?.aktiv === undefined ? true : !!formular.aktiv,
    strophen: strophenNummerieren((formular?.strophen || []).map((s) => ({
      nummer: s?.nummer, typ: typNormalisieren(s?.typ), text: String(s?.text || ''),
      sprache: String(s?.sprache || ''), nur_chor: !!s?.nur_chor,
    }))),
    kategorien: (formular?.kategorien || []).map((k) => String(k)).filter((k) => k.trim()),
    anlaesse: (formular?.anlaesse || []).map((a) => String(a)).filter((a) => a.trim()),
  }
  if (formular?.name) werte.name = formular.name
  return werte
}

/** Anlegen oder Ändern? (Der Aufrufer wählt damit Route und Rückweg.) */
export function istNeuanlage(formular) {
  return !String(formular?.name || '').trim()
}
