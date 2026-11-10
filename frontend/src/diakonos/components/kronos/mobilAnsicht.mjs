/**
 * A10 — Kalender auf dem Handy: die EINE Wahrheit der Mobil-Ansicht.
 *
 * Warum eine eigene Datei ohne Vue/DOM: Die Karte A10 verlangt prüfbares
 * Verhalten (Standardansicht je Benutzer, „Als Standard verwenden“,
 * Tagesliste, Statuszeile, schwebender Knopf). Hier stehen die Regeln als
 * reine Funktionen — `tests/a10-*.test.mjs` führt sie wirklich aus, der
 * Wegwerf-Stack zeigt dasselbe im Browser.
 *
 * ENTSCHEIDUNG MANUEL (08.11., verbindlich):
 *   * Auf dem Handy setzt JEDE Person ihre Standard-Ansicht selbst —
 *     Monat · Woche · Liste. Ohne eigene Wahl gilt „Liste“ (Entwurf A10).
 *   * Die Wahl gilt JE BENUTZER. Einen serverseitigen Mechanismus für
 *     Ansichts-Einstellungen gibt es nicht (geprüft: kein Konto-Feld, kein
 *     Endpunkt für Ansichten) — deshalb `localStorage` mit Nutzer-Hash im
 *     Schlüssel, wie UX3f es für den Paletten-Verlauf macht
 *     (`composables/befehlspalette.mjs`). Abmelden löscht die Einträge.
 *   * Gesetzt wird über das „⋯“-Menü („Als Standard verwenden“ an der
 *     aktuellen Ansicht), nicht über einen eigenen Einstellungs-Dialog.
 *
 * Der Desktop ist NICHT Teil dieser Karte: dort gilt A4 unverändert
 * (Reiterleiste Monat · Woche · Liste).
 */

import { wandZeit } from '../../../shared/zeit.mjs'

/** Basis-Schlüssel im Browserspeicher; je Nutzer kommt `:<hash>` dazu. */
export const STANDARD_SCHLUESSEL = 'dk-kalender-standard-ansicht'

/** Erlaubte Ansichten der Segmentsteuerung (Entwurf A10, links nach rechts). */
export const MOBIL_ANSICHTEN = Object.freeze([
  { id: 'monat', label: 'Monat', ansicht: 'dayGridMonth' },
  { id: 'woche', label: 'Woche', ansicht: 'timeGridWeek' },
  { id: 'liste', label: 'Liste', ansicht: 'listMonth' },
])

/** Die Vorgabe ohne eigene Wahl: der Entwurf A10 startet in der Liste. */
export const STANDARD_VORGABE = 'liste'

/**
 * Kleiner, stabiler Hash (FNV-1a, 32 Bit) — DIESELBE Rechnung wie
 * `nutzerHash` in `composables/befehlspalette.mjs` (dort geprüft). Die
 * Nutzerkennung steht so nicht im Klartext im Speicher des Browsers; das ist
 * KEIN Sicherheitsmerkmal, nur Datensparsamkeit wie bei UX3f.
 */
export function nutzerHash(kennung) {
  const text = String(kennung || '').trim().toLowerCase()
  if (!text) return ''
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

/** Ist das eine bekannte Ansicht (`monat` / `woche` / `liste`)? */
export function istAnsicht(wert) {
  return MOBIL_ANSICHTEN.some((a) => a.id === String(wert || ''))
}

const BIBLIOTHEK_JE_ANSICHT = Object.freeze(
  Object.fromEntries(MOBIL_ANSICHTEN.map((a) => [a.id, a.ansicht])),
)

/** Ansichts-Kennung → Ansicht der Kalender-Bibliothek (`listMonth` …). */
export function bibliothekAnsicht(id) {
  const treffer = MOBIL_ANSICHTEN.find((a) => a.id === String(id || ''))
  return treffer ? treffer.ansicht : BIBLIOTHEK_JE_ANSICHT[STANDARD_VORGABE]
}

/** Ansicht der Kalender-Bibliothek → Kennung der Segmentsteuerung. */
export function ansichtKennung(bibliothekWert) {
  const wert = String(bibliothekWert || '')
  if (wert === 'timeGridDay' || wert === 'timeGridWeek') return 'woche'
  if (wert === 'listMonth' || wert.startsWith('list')) return 'liste'
  // Alles andere (Monat, Ressourcen-Zeitraster aus dem ⋯-Menü) zeigt die
  // Monats-Seite — die Segmentsteuerung hat kein eigenes Segment dafür.
  return wert.startsWith('timeGrid') ? 'woche' : 'monat'
}

/**
 * Schlüssel EINES Nutzers. Ohne Kennung (Gast, fehlendes Boot-Objekt) gibt
 * es KEINEN Schlüssel (`''`): dort gibt es keinen zweiten Nutzer, dessen Wahl
 * man sehen könnte — ein gemeinsamer Basisschlüssel wäre aber ein Speicher
 * für ALLE (Review 09.11., Punkt 3). Ohne Kennung wird deshalb weder
 * gespeichert noch gelesen; es gilt die Vorgabe.
 */
export function standardSchluessel(nutzer) {
  const hash = nutzerHash(nutzer)
  return hash ? `${STANDARD_SCHLUESSEL}:${hash}` : ''
}

/**
 * Gespeicherte Standard-Ansicht lesen. Was nicht lesbar ist (gesperrter
 * Speicher, fremder Wert, keine Nutzerkennung), ergibt die Vorgabe `liste` —
 * nie `undefined`.
 */
export function standardLesen(speicher, nutzer) {
  const schluessel = standardSchluessel(nutzer)
  if (!schluessel) return STANDARD_VORGABE
  const roh = lies(speicher, schluessel)
  return istAnsicht(roh) ? String(roh) : STANDARD_VORGABE
}

/**
 * Standard-Ansicht setzen. Still ohne Speicher (privater Modus) — und
 * ausdrücklich OHNE Nutzerkennung gar nicht (Review 09.11., Punkt 3):
 * ein gemeinsamer Schlüssel würde jedem die Wahl des anderen zeigen.
 * Rückgabe `false` heißt „nicht gespeichert“ (die Seite sagt es ehrlich).
 */
export function standardSetzen(speicher, nutzer, ansicht) {
  if (!istAnsicht(ansicht)) return false
  const schluessel = standardSchluessel(nutzer)
  if (!schluessel) return false
  try {
    speicher?.setItem?.(schluessel, String(ansicht))
    return true
  } catch (_) {
    return false
  }
}

/**
 * Beim Abmelden (und beim Identitätswechsel): ALLE Standard-Schlüssel
 * löschen, die nicht zu diesem Nutzer gehören. Ohne Kennung wird alles
 * gelöscht — dieselbe fail-closed-Regel wie beim Paletten-Verlauf.
 *
 * Rückgabe: Anzahl der entfernten Einträge (für den Test).
 */
export function standardFuerNutzerAufraeumen(speicher, nutzer) {
  const weg = []
  try {
    if (!speicher || typeof speicher.key !== 'function') return 0
    const behalten = nutzerHash(nutzer)
    for (let i = 0; i < speicher.length; i += 1) {
      const k = speicher.key(i)
      if (!k) continue
      // Ein alter, nutzerloser Basisschlüssel (aus der Zeit vor der Regel
      // „ohne Kennung nicht speichern“) wird ebenfalls entfernt — er gehört
      // keinem Benutzer und darf nicht stehen bleiben.
      if (!k.startsWith(STANDARD_SCHLUESSEL)) continue
      if (behalten && k === `${STANDARD_SCHLUESSEL}:${behalten}`) continue
      weg.push(k)
    }
    for (const k of new Set(weg)) speicher.removeItem(k)
  } catch (_) {
    return 0
  }
  return new Set(weg).size
}

function lies(speicher, schluessel) {
  try {
    return speicher?.getItem?.(schluessel) ?? ''
  } catch (_) {
    return ''
  }
}

/**
 * Abmelde-Schritt für den `useAbmelden`-Ablauf (Review 09.11., Punkt 2):
 * Die persönliche Standard-Ansicht ist nutzerbezogen und darf nach dem
 * Abmelden NICHT stehen bleiben. `useAbmelden` ruft genau diese Funktion —
 * sie nimmt den Speicher als Argument, weil der Abmelde-Ablauf im Node-Test
 * ohne Browser läuft (`tests/a10-aushang.test.mjs`).
 *
 * Rückgabe: Anzahl der entfernten Einträge (0, wenn nichts zu tun war).
 */
export function abmeldenAufraeumen(speicher) {
  return standardFuerNutzerAufraeumen(speicher, '')
}

/**
 * Darf die Statuszeile „Zu prüfen“ erscheinen?
 *
 * Dieselbe Rechteprüfung wie das Desktop-Panel „Zu prüfen“ (UX3d/UX3i):
 * `can_moderate` aus dem Boot-Objekt — der Server liefert die Daten
 * (Board, Zähler) ohnehin nur Moderatoren. Ohne den Schlüssel gilt `false`
 * (fail closed): dann gibt es die Zeile NICHT — auch keinen leeren Platz
 * und kein Abzeichen „Moderator“ (Karte A10).
 */
export function zeigeModerationszeile({ can_moderate = false } = {}) {
  return can_moderate === true
}

/**
 * Der schwebende Knopf „+ Termin anlegen“ erscheint nur mit Schreibrecht
 * auf MINDESTENS einen Kalender — dieselbe Regel wie der Primärknopf am
 * Desktop (UXK-R10). Die Rechte kommen vom Server (`get_accessible_calendars`
 * -> `write`).
 */
export function zeigeAnlegenKnopf(kalender) {
  if (!Array.isArray(kalender)) return false
  return kalender.some((k) => k && k.write === true)
}

/** Datumsteile eines Server-/Kalenderwerts; `null`, wenn unbrauchbar. */
function alsDatum(wert) {
  if (!wert) return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  if (typeof wert === 'object') {
    // Kalender-Bibliothek: `{ year, month (0-basiert), day }`.
    const { year, month, day } = wert
    if (Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)) {
      const d = new Date(year, month, day, 12)
      return Number.isNaN(d.getTime()) ? null : d
    }
    return null
  }
  if (typeof wert === 'number') {
    const d = new Date(wert)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const text = String(wert).trim()
  if (!text) return null
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return new Date(`${text}T12:00:00`)
  // Termin-Zeiten sind Wandzeiten der Gemeinde (ZEIT-2: shared/zeit.mjs).
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(text)) return wandZeit(text)
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * Ende eines Termins EINSCHLIESSLICH (Diakronos speichert das Ende inklusiv;
 * die Kalender-Bibliothek rechnet es exklusiv). Für „bis zu diesem Tag
 * sichtbar“ zählt deshalb das Ende MIT — zeigt es auf Mitternacht, ist der
 * Vortag der letzte Tag.
 */
function letzterTag(termin) {
  const ende = alsDatum(termin?.end ?? termin?.element_end)
  const endeTag = tagText(ende)
  if (!endeTag) return tagText(termin?.start ?? termin?.element_start)
  if (ende && ende.getHours() === 0 && ende.getMinutes() === 0) {
    return tagText(new Date(new Date(`${endeTag}T12:00:00`).getTime() - 12 * 3600 * 1000))
  }
  return endeTag
}

/** `JJJJ-MM-TT` eines Datums in ORTSZEIT (nicht UTC — sonst rutscht der Tag). */
export function tagText(wert) {
  const d = alsDatum(wert)
  if (!d) return ''
  const zwei = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${zwei(d.getMonth() + 1)}-${zwei(d.getDate())}`
}

/** Heutiger Tag in Ortszeit (`JJJJ-MM-TT`). */
export function heuteText(jetzt = new Date()) {
  return tagText(jetzt)
}

/** Monatsschlüssel `JJJJ-MM` eines Datums (Vorgabe: heute). */
export function monatsSchluessel(wert = new Date()) {
  const d = alsDatum(wert instanceof Date ? wert : `${String(wert).slice(0, 10)}T12:00:00`)
  if (!d) return heuteText().slice(0, 7)
  return tagText(d).slice(0, 7)
}

const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
]

/** „November 2026“ (Entwurf A10, Mini-Monat). */
export function monatsTitel(monat) {
  const m = String(monat || '').match(/^(\d{4})-(\d{2})$/)
  if (!m) return ''
  const nummer = Number(m[2])
  if (!(nummer >= 1 && nummer <= 12)) return ''
  return `${MONATE[nummer - 1]} ${m[1]}`
}

/** „Sonntag, 8. November“ (Entwurf A10, Kopf der Tagesliste). */
export function tagTitel(wert) {
  const d = alsDatum(wert)
  if (!d) return ''
  return d.toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' })
}

/** „So., 8. Nov.“ — kleinere Form für die Monats-Kopfzeile. */
export function tagKurz(wert) {
  const d = alsDatum(wert)
  if (!d) return ''
  return d.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' })
}

/** Wochentagsköpfe des Mini-Monats (Mo–So, wie die App: firstDay = 1). */
export const WOCHENTAGE = Object.freeze(['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'])

/**
 * Raster des Mini-Monats: Wochenzeilen Mo–So, IMMER volle Wochen.
 *
 * `monat` = `JJJJ-MM`. Jede Zelle: `{ tag: 'JJJJ-MM-TT', zahl, imMonat,
 * istHeute }`. Der Entwurf A10 zeigt sechs Wochen (auch October-Tage grau).
 *
 * @param {string} monat
 * @param {Date} [jetzt]
 */
export function miniRaster(monat, jetzt = new Date()) {
  const m = String(monat || '').match(/^(\d{4})-(\d{2})$/)
  if (!m) return []
  const jahr = Number(m[1])
  const nummer = Number(m[2])
  if (!(nummer >= 1 && nummer <= 12)) return []
  const erster = new Date(jahr, nummer - 1, 1, 12)
  // Mo = 0 … So = 6 (JS: So = 0).
  const versatz = (erster.getDay() + 6) % 7
  const start = new Date(jahr, nummer - 1, 1 - versatz, 12)
  const heute = tagText(jetzt)
  const zeilen = []
  for (let w = 0; w < 6; w += 1) {
    const tage = []
    for (let t = 0; t < 7; t += 1) {
      const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7 + t, 12)
      const tag = tagText(d)
      tage.push({
        tag,
        zahl: d.getDate(),
        imMonat: d.getMonth() === nummer - 1 && d.getFullYear() === jahr,
        istHeute: tag === heute,
      })
    }
    // Eine sechste Woche ohne einen einzigen Tag des Monats entfällt —
    // sonst stünde eine leere Zeile im Mini-Monat (Entwurf: fünf Wochen).
    if (w === 5 && !tage.some((x) => x.imMonat)) break
    zeilen.push(tage)
  }
  return zeilen
}

/** Bereiche je Zeile: `[startTag, endTag]` eines Termins. */
function bereich(termin) {
  const start = alsDatum(termin?.start ?? termin?.element_start)
  const startTag = tagText(termin?.start ?? termin?.element_start)
  const ende = alsDatum(termin?.end ?? termin?.element_end)
  const endeTag = tagText(termin?.end ?? termin?.element_end)
  return { start, startTag, ende, endeTag }
}

/**
 * Ist der Termin an diesem Tag sichtbar? Mehrtägige Termine hängen an jedem
 * Tag ihres Zeitraums; ganztägig schließt das Ende EIN (Diakronos-Speicherung,
 * siehe datumZeit/ICAL-1b).
 */
export function terminAmTag(termin, tag) {
  const ziel = String(tag || '')
  if (!ziel) return false
  const startTag = tagText(termin?.start ?? termin?.element_start)
  if (!startTag) return false
  if (startTag === ziel) return true
  return startTag <= ziel && ziel <= letzterTag(termin)
}

/** „09:30“ — leer bei ganztägigen und mehrtägigen Terminen. */
export function terminZeit(termin, tag) {
  const t = termin || {}
  if (t.allDay || t.all_day) return ''
  const { start, endeTag, startTag } = bereich(t)
  if (!start) return ''
  // Am zweiten und weiteren Tag eines mehrtägigen Termins steht keine
  // Startzeit — sie gehörte zum ersten Tag. Der erste Tag zeigt „ganztägig“
  // nur, wenn der Termin ohne Uhrzeit beginnt (0:00).
  if (String(tag || '') && startTag !== String(tag)) return ''
  if (endeTag && endeTag > startTag) {
    if (start.getHours() === 0 && start.getMinutes() === 0) return 'ganztägig'
  }
  return `${String(start.getHours()).padStart(2, '0')}:${String(start.getMinutes()).padStart(2, '0')}`
}

/**
 * Zusatzzeile einer Tageszeile (Entwurf A10: „Ort · Zusatz“).
 * Ort = Ressource (primär oder die erste zusätzliche), Zusatz = Beschreibung
 * in EINER ruhigen Zeile, gekürzt.
 */
export function terminZusatz(termin, maxLaenge = 60) {
  const t = termin || {}
  const ort = String(t.ressource_name || t.ort || '').trim()
    || (Array.isArray(t.zusaetzliche_ressourcen)
      ? String(t.zusaetzliche_ressourcen[0]?.ressource_name || t.zusaetzliche_ressourcen[0]?.freitext_ressource || '').trim()
      : '')
    || String(t.ressource || '').trim()
  const roh = String(t.description || '').trim().split('\n').map((z) => z.trim()).filter(Boolean)[0] || ''
  const zusatz = roh.length > maxLaenge ? `${roh.slice(0, maxLaenge - 1).trimEnd()}…` : roh
  return [ort, zusatz].filter(Boolean).join(' · ')
}

/**
 * Termine EINES Tages, sortiert: zuerst ganztägige/ohne Uhrzeit, dann nach
 * Beginn, dann nach Titel. Jeder Eintrag trägt seine Anzeigefelder.
 */
export function tagesTermine(termine, tag) {
  const liste = (Array.isArray(termine) ? termine : [])
    .filter((t) => terminAmTag(t, tag))
    .map((t) => {
      const { start } = bereich(t)
      const ohneZeit = !!(t.allDay || t.all_day) || !start
      return {
        termin: t,
        zeit: terminZeit(t, tag),
        titel: String(t.title || t.element_name || '').trim() || 'Termin ohne Titel',
        zusatz: terminZusatz(t),
        ohneZeit,
        beginn: start ? start.getTime() : Number.MAX_SAFE_INTEGER,
      }
    })
  return liste.sort((a, b) => {
    if (a.ohneZeit !== b.ohneZeit) return a.ohneZeit ? -1 : 1
    if (a.beginn !== b.beginn) return a.beginn - b.beginn
    return a.titel.localeCompare(b.titel, 'de')
  })
}

/**
 * Punkte je Tag im Mini-Monat (Entwurf A10): „gold“ = zu prüfen,
 * „navy“ (Kalenderfarbe) = normaler Termin. Die Kennung kommt von außen
 * (`pruefIds`), damit hier nichts geraten wird.
 *
 * @returns {Map<string, {normal: boolean, pruefen: boolean, anzahl: number}>}
 */
export function punkteJeTag(termine, pruefIds = [], tagSpanne = null) {
  const pruef = new Set((Array.isArray(pruefIds) ? pruefIds : []).map(String))
  const karte = new Map()
  const eintragen = (tag, eintrag) => {
    if (!tag) return
    const vorhanden = karte.get(tag) || { normal: false, pruefen: false, anzahl: 0 }
    vorhanden.normal = vorhanden.normal || eintrag.normal
    vorhanden.pruefen = vorhanden.pruefen || eintrag.pruefen
    vorhanden.anzahl += eintrag.anzahl
    karte.set(tag, vorhanden)
  }
  for (const termin of Array.isArray(termine) ? termine : []) {
    const kennung = String(termin?.id || termin?.name || '')
    const istPruef = kennung && pruef.has(kennung)
    const startTag = tagText(termin?.start ?? termin?.element_start)
    const endeTag = letzterTag(termin)
    if (!startTag) continue
    // Jeden Tag des Zeitraums markieren (mehrtägig), begrenzt auf `tagSpanne`.
    const von = new Date(`${startTag}T12:00:00`)
    const bis = endeTag && endeTag > startTag ? new Date(`${endeTag}T12:00:00`) : von
    let d = new Date(von.getTime())
    let schutz = 0
    while (d.getTime() <= bis.getTime() && schutz < 400) {
      const tag = tagText(d)
      if (!tagSpanne || (tag >= tagSpanne[0] && tag <= tagSpanne[1])) {
        eintragen(tag, { normal: !istPruef, pruefen: !!istPruef, anzahl: 1 })
      }
      d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1, 12)
      schutz += 1
    }
  }
  return karte
}

/**
 * Einträge des „⋯“-Menüs der Mobil-Kopfzeile (Entwurf A10, Entscheidung
 * Manuel): alles Seltene — Kalenderauswahl, Heute ‹ ›, „Als Standard
 * verwenden“ an der AKTUELLEN Ansicht (aktiver Standard mit Häkchen),
 * Ressourcenplan, Verwalten/Import (nur Kalenderadmin), Lesemodus,
 * abgelehnte Termine, Hilfe.
 *
 * Die Einträge sind reine Daten; was ein Klick tut, entscheidet die Seite
 * (`pages/Kalender.vue`) — dieselbe Trennung wie bei `kalenderMenue` (UX3i).
 */
export function mobilMenue({
  ansicht = STANDARD_VORGABE,
  standard = STANDARD_VORGABE,
  istKalenderAdmin = false,
  hatSchreibrecht = false,
  lesemodus = true,
} = {}) {
  // Entwurf A10 verbietet die alten Werkzeugzeilen mit sieben kleinen
  // Knöpfen; die häufigsten Wege („Heute“, „‹ ›“, Kalenderauswahl) stehen
  // deshalb als 44-px-Knöpfe in der Kopfzeile selbst. Das Menü trägt nur
  // noch, was selten gebraucht wird — und bleibt damit bei höchstens acht
  // Einträgen (DkAktionen, Entwurf B1).
  const eintraege = []
  const aktuelle = MOBIL_ANSICHTEN.find((a) => a.id === String(ansicht)) || MOBIL_ANSICHTEN[2]
  eintraege.push({
    key: 'standard',
    // Der Entwurf nennt die Handlung: „Als Standard verwenden“ — bei der
    // bereits gesetzten Ansicht steht das Häkchen und ein stiller Text.
    label: String(standard) === aktuelle.id
      ? `„${aktuelle.label}“ ist dein Standard`
      : `„${aktuelle.label}“ als Standard verwenden`,
    icon: String(standard) === aktuelle.id ? 'haekchen' : 'pruefen',
    aktion: 'standardSetzen',
    haekchen: String(standard) === aktuelle.id,
    disabled: String(standard) === aktuelle.id,
  })
  eintraege.push({ key: 'ressourcenplan', label: 'Ressourcenplan', icon: 'kalender', aktion: 'ressourcenplan' })
  if (istKalenderAdmin === true) {
    eintraege.push({ key: 'verwalten', label: 'Kalender verwalten', icon: 'bearbeiten', href: '#/kalender/verwalten' })
    eintraege.push({ key: 'importieren', label: 'Kalender importieren', icon: 'herunterladen', href: '#/kalender/import' })
  }
  if (hatSchreibrecht === true) {
    eintraege.push({
      key: 'bearbeiten',
      label: lesemodus ? 'Bearbeiten einschalten' : 'Bearbeiten ausschalten',
      icon: 'stift',
      aktion: 'bearbeitenUmschalten',
    })
  }
  eintraege.push({ key: 'abgelehnte', label: 'Abgelehnte Termine', icon: 'abbrechen', aktion: 'abgelehnteTermine' })
  eintraege.push({ key: 'hilfe', label: 'Hilfe & Infos', icon: 'notiz', aktion: 'hilfe' })
  return eintraege
}

/** Nur Zahlen, die wirklich eine Zahl sind — nie eine erfundene 0. */
function zahlOderNull(wert) {
  if (wert === null || wert === undefined || wert === '') return null
  const n = Number(wert)
  return Number.isFinite(n) ? n : null
}

/** Text der goldenen Statuszeile (Entwurf A10): „Zu prüfen (3) · Von Gruppen eingetragen“. */
export function pruefZeilenText(zahl) {
  const n = zahlOderNull(zahl)
  // Ohne bekannte Zahl ODER bei 0 steht keine Zahl: „Zu prüfen · …“.
  const kopf = (n !== null && n > 0) ? `Zu prüfen (${n})` : 'Zu prüfen'
  return `${kopf} · Von Gruppen eingetragen`
}

export default {
  STANDARD_SCHLUESSEL,
  MOBIL_ANSICHTEN,
  STANDARD_VORGABE,
  nutzerHash,
  istAnsicht,
  bibliothekAnsicht,
  ansichtKennung,
  standardSchluessel,
  standardLesen,
  standardSetzen,
  standardFuerNutzerAufraeumen,
  abmeldenAufraeumen,
  zeigeModerationszeile,
  zeigeAnlegenKnopf,
  tagText,
  heuteText,
  monatsSchluessel,
  monatsTitel,
  tagTitel,
  tagKurz,
  miniRaster,
  terminAmTag,
  terminZeit,
  terminZusatz,
  tagesTermine,
  punkteJeTag,
  mobilMenue,
  pruefZeilenText,
}
