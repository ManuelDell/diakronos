/**
 * ON-4 — Einrichtungs-Hinweise im Alltag (Übersicht, Einstellungen, leere Listen).
 *
 * WARUM ES DIESES MODUL GIBT
 * Drei Stellen zeigen denselben Zustand aus `einrichtung.status`
 * (`backend/src/diakronos_app/api/einrichtung.py`, Vertrag docs/ON2-VERTRAG.md):
 * die Karte auf der Übersicht (Entwurf Frame 10), die amber Leisten in den
 * Einstellungen (Frame 11) und der Leerzustand der Mitgliederliste
 * (Frame 12). Jede Stelle würde die Wahrheitslogik sonst selbst nachbauen —
 * und „offen“ heißt an drei Stellen etwas anderes, sobald ein Punkt dazukommt.
 *
 * Hier steht deshalb NUR die darstellende Rechnung, damit sie testbar ist:
 *
 *   - `statusLaden()` / `statusStand` — EIN Statusabruf für alle sichtbaren
 *     Stellen (die Übersicht holt ihn beim Anzeigen, die Einstellungen ebenso;
 *     zwei Abrufe zeigten sonst zwei Stände).
 *   - `leistenZeigen(status, rollen, heute)` — überhaupt Hinweise zeigen?
 *     (nicht für Nicht-Admins, nicht während des Assistenten, nicht bei
 *     „Später erinnern“).
 *   - `hinweisFuer(status, schluessel, …)` — die amber Leiste einer
 *     Einstellungs-Seite (nur wenn der zugehörige Punkt offen ist).
 *   - `gemeindeHinweis(status)` — was auf „Gemeinde“ fehlt (Name, Logo,
 *     Kontakt) als Aufzählung für die Leiste.
 *   - `mitgliederLeerzustand(...)` — freundlicher Leerzustand vs. „Filter
 *     greift“ (Frame 12 und die Suche dürfen nicht denselben Text zeigen).
 *   - `leerzustandFuerListe(status, schluessel, …)` — dasselbe für Kalender.
 *
 * Bewusst KEINE Farben/Schriften/Radien: das ist Sache der Komponenten und der
 * Tokens (`tokens.css`). Hier stehen nur Sätze (wörtlich aus dem Entwurf) und
 * Wahrheitswerte.
 *
 * KEINE eigene Anfrage: `statusLaden` benutzt `apiCall` — derselbe Weg wie der
 * Assistent (POST, CSRF, Betriebspräfix über `apiUrl` in `useApi.js`). Der
 * Status ist serverseitig auf Admin-Rollen beschränkt; wer nicht darf, bekommt
 * keine Leisten (der Fehler wird still übergangen — ein Hinweis darf die Seite
 * nicht aufhalten).
 */
import { ref } from 'vue'

import { apiCall } from './useApi.js'
import {
  erinnerungAktiv,
  logoQuelle,
  monogramm,
  offenePunkte,
  tagIso,
} from './einrichtung.mjs'

const EINRICHTUNG = 'diakronos.diakonos.api.einrichtung.'

//: Ziel der Einstellungen (Sammel-Ziel für den Punkt `module`; der Server
//: nennt es in `einrichtung.status` bereits selbst als `ziel`).
export const EINSTELLUNGEN_ROUTE = '#/einstellungen'

//: Ziel des Mailversands (Einstellungen → Mailversand).
export const MAILVERSAND_ROUTE = '#/einstellungen/mailversand'

//: Ziel der Gemeinde-Einstellungen.
export const GEMEINDE_ROUTE = '#/einstellungen/gemeinde'

//: Ziel der Mitgliederliste.
export const MITGLIEDER_ROUTE = '#/personen/liste'

//: Ziel des Imports.
export const IMPORT_ROUTE = '#/personen/import'

//: Ziel der Kalenderverwaltung.
export const KALENDER_VERWALTUNG_ROUTE = '#/kalender/verwalten'

/**
 * Marke einer Seite: Logo ODER Monogramm (`logoQuelle`/`monogramm` in
 * `einrichtung.mjs` — dieselbe Regel wie die Seitenleiste und der Assistent).
 *
 * `daten` ist die Antwort von `gemeinde.gemeinde_get_einstellungen` (oder der
 * Status): `logo_url` kommt FERTIG (Betriebspräfix + `?v=`) und wird nicht
 * nachgebaut. Ohne Namen bleibt der Produktbuchstabe „D“ — dann steht die
 * Marke nicht leer da.
 *
 * @returns {{logo: string|null, buchstabe: string}}
 */
export function markenDaten(daten = {}) {
  const logo = logoQuelle(daten)
  const buchstabe = monogramm(daten, String(daten?.gemeindename || daten?.organisationsname || ''))
  return { logo, buchstabe: buchstabe === '?' ? 'D' : buchstabe }
}

/**
 * Wörtlich aus dem Entwurf (Frame 10/11/12). Die Sätze stehen hier EINMAL,
 * damit Leiste, Karte und Leerzustand nicht auseinanderlaufen können.
 */
export const TEXTE = {
  // Frame 10 — Karte auf der Übersicht
  karteTitel: 'Einrichtung abschließen',
  karteUnterzeile: 'Sie können jeden Punkt einzeln nachholen.',
  spaeterErinnern: 'Später erinnern',
  einrichten: 'Einrichten',
  // Fuẞ der Karte: die Angaben werden in den Einstellungen gepflegt.
  einstellungenOeffnen: 'Zu den Einstellungen',
  karteSchliessen: 'Einrichtung später erinnern',
  // Frame 11 — Einstellungen
  mailversandTitel: 'Mailversand ist noch nicht eingerichtet.',
  mailversandText:
    'Einladungen, Passwort-Links und Benachrichtigungen können derzeit nicht verschickt werden.',
  gemeindeTitel: 'Die Gemeinde ist noch nicht eingerichtet.',
  gemeindeFuss: 'Diese Angaben erscheinen in der App und in geteilten Links.',
  // Frame 12 — leere Mitgliederliste
  mitgliederLeerTitel: 'Noch keine Mitglieder',
  mitgliederLeerText:
    'Sobald Sie Personen anlegen oder eine CSV importieren, erscheinen sie hier '
    + 'mit Kontaktangaben und Gruppenzugehörigkeit.',
  mitgliederLeerFuss: 'Der Import erwartet eine CSV mit Vorname, Nachname und E-Mail.',
  mitgliederAnlegen: 'Mitglied anlegen',
  csvImportieren: 'CSV importieren',
  // Leere Kalenderliste (dasselbe Muster)
  kalenderLeerTitel: 'Noch keine Kalender',
  kalenderLeerText:
    'Sobald Sie einen Kalender anlegen, erscheinen hier seine Termine.',
  kalenderAnlegen: 'Kalender anlegen',
  // Suche/Filter — bewusst NICHT der Leerzustand aus Frame 12.
  mitgliederFilterTitel: 'Keine Mitglieder gefunden',
  mitgliederFilterText: 'Suche oder Filter anpassen.',
  kalenderFilterTitel: 'Keine Kalender freigegeben',
  kalenderFilterText: 'Sobald Ihnen ein Kalender freigegeben ist, erscheint er hier.',
}

/** Ist jemand Admin? Der Boot liefert `is_admin` und `roles` (spa.py). */
function istAdmin(rollen) {
  if (rollen === true) return true
  if (!rollen || rollen === false) return false
  if (Array.isArray(rollen)) {
    return rollen.includes('System Manager') || rollen.includes('Mitgliederadministrator')
  }
  // Das Boot-Objekt selbst (window.__DIakonosBOOT): EIN Feld entscheidet —
  // dieselbe Regel wie der Router-Guard. Der Server prüft erneut (403).
  return rollen.is_admin === true
}

/**
 * Der geladene Status — MODULWEIT, damit Übersicht und Einstellungen denselben
 * Stand zeigen und ein Seitenwechsel nicht neu fragt. `null` = noch nicht
 * geladen (oder Laden fehlgeschlagen → dann bleiben die Hinweise weg).
 */
export const statusStand = ref(null)

let laufend = null

/**
 * Status laden (einmal, dann aus dem Stand) — oder mit `neu: true` erzwingen.
 *
 * Fehler werden STILL übergangen: ein Einrichtungshinweis darf keine Seite
 * aufhalten, und der Server antwortet Nicht-Admins ohnehin mit 403 (die
 * Leisten sind dann schlicht nicht da, die Seite funktioniert weiter).
 *
 * @returns {Promise<object|null>} der Status oder `null`.
 */
export function statusLaden({ neu = false } = {}) {
  if (!neu && statusStand.value) return Promise.resolve(statusStand.value)
  if (laufend) return laufend
  laufend = apiCall(EINRICHTUNG + 'status', {})
    .then((antwort) => {
      const wert = antwort?.message || antwort
      statusStand.value = wert && typeof wert === 'object' ? wert : null
      return statusStand.value
    })
    .catch(() => statusStand.value)
    .finally(() => { laufend = null })
  return laufend
}

/** Stand für Tests und nach dem Einrichten setzen (z. B. neu geladener Status). */
export function setzeStatusStand(wert) {
  statusStand.value = wert && typeof wert === 'object' ? wert : null
  laufend = null
  return statusStand.value
}

/** Nach einem erledigten Punkt neu lesen (kein erneuter Aufbau der Seite). */
export function statusAuffrischen() {
  return statusLaden({ neu: true })
}

/**
 * Sollen die amber Hinweise (Leisten/Karte) überhaupt erscheinen?
 *
 * Nein, wenn
 *   - niemand mit Admin-Rolle schaut (der Server weist Nicht-Admins ohnehin ab),
 *   - kein Status geladen ist (Ladefehler → lieber nichts behaupten),
 *   - der Assistent noch läuft (er ist dann die Baustelle — ON-2 `karteZeigen`),
 *   - „Später erinnern“ noch gilt.
 *
 * Der Einrichtungs-Assistent selbst hat seine eigene Checkliste und braucht
 * die Leisten nicht.
 */
export function leistenZeigen(status, rollen, heute = new Date()) {
  if (!istAdmin(rollen)) return false
  if (!status || typeof status !== 'object') return false
  if (status.assistent_abgeschlossen !== true) return false
  return !erinnerungAktiv(status, heute)
}

/**
 * Ist ein bestimmter Punkt noch offen?
 * Unbekannter Schlüssel → `false` (dann gibt es keinen Hinweis, statt eines
 * Hinweises auf etwas, das der Server nicht kennt).
 */
export function punktOffen(status, schluessel) {
  const punkte = Array.isArray(status?.punkte) ? status.punkte : []
  const treffer = punkte.find((p) => p && p.schluessel === schluessel)
  return Boolean(treffer) && treffer.erledigt === false
}

/** Der Punkt selbst (oder `null`) — für Titel/Hinweis aus der Server-Antwort. */
export function punkt(status, schluessel) {
  const punkte = Array.isArray(status?.punkte) ? status.punkte : []
  return punkte.find((p) => p && p.schluessel === schluessel) || null
}

//: Welche Einstellungs-Seite für welchen Punkt zuständig ist. EINE Tabelle,
//: damit Leiste, Menüpunkt und Karte nicht auseinanderlaufen.
//:
//: NACHTRAG Orchestrator (2026-11-03): Es gibt KEINEN eigenen Abschnitt
//: „Einrichtung“. Nach der Ersteinrichtung werden alle Angaben AUSSCHLIESSLICH
//: in den Einstellungen gepflegt — darum zeigt hier jede Seite nur ihre
//: eigenen Punkte, und die Karte schickt jeden offenen Punkt auf sein Ziel aus
//: `einrichtung.status` (Einstellungen bzw. Mitglieder-/Kalenderverwaltung).
const SEITEN_PUNKTE = {
  mailversand: ['mailversand'],
  gemeinde: ['gemeindename', 'logo', 'kontakt'],
}

/** Die Punkte, die zu einer Einstellungs-Seite gehören (Serverreihenfolge). */
export function punkteFuerSeite(status, seite) {
  const schluessel = SEITEN_PUNKTE[String(seite || '')] || []
  return schluessel
    .map((s) => punkt(status, s))
    .filter((p) => p && p.erledigt === false)
}

/**
 * Die amber Leiste einer Einstellungs-Seite — `null`, wenn alles erledigt ist.
 *
 * @returns {null | {seite: string, titel: string, text: string,
 *                   fehlend: Array<{schluessel: string, titel: string}>,
 *                   ziel: string, zielText: string}}
 */
export function hinweisFuer(status, seite, rollen, heute = new Date()) {
  if (!leistenZeigen(status, rollen, heute)) return null
  const offene = punkteFuerSeite(status, seite)
  if (!offene.length) return null
  const fehlend = offene.map((p) => ({ schluessel: p.schluessel, titel: p.titel }))
  if (seite === 'mailversand') {
    return {
      seite,
      titel: TEXTE.mailversandTitel,
      text: TEXTE.mailversandText,
      fehlend,
      // „Einrichten“ führt auf DIESE Seite (die Felder stehen darunter).
      ziel: MAILVERSAND_ROUTE,
      zielText: TEXTE.einrichten,
    }
  }
  if (seite === 'gemeinde') {
    return {
      seite,
      titel: TEXTE.gemeindeTitel,
      text: TEXTE.gemeindeFuss,
      fehlend,
      ziel: GEMEINDE_ROUTE,
      zielText: TEXTE.einrichten,
    }
  }
  return null
}

/** „Einrichtung abschließen — 3 von 7 offen“ (Frame 10, Zähler aus dem Server). */
export function karteTitelMitZahl(status) {
  const offen = Number(status?.offen_anzahl)
  const gesamt = Number(status?.gesamt_anzahl)
  if (!Number.isFinite(offen) || !Number.isFinite(gesamt) || gesamt <= 0) {
    return TEXTE.karteTitel
  }
  return `${TEXTE.karteTitel} — ${offen} von ${gesamt} offen`
}

/**
 * Die Zeilen der Übersichts-Karte (Frame 10): nur offene Punkte, in
 * Serverreihenfolge, jeder mit „Einrichten“ auf sein Ziel.
 */
export function kartenZeilen(status) {
  return offenePunkte(status).map((p) => ({
    schluessel: p.schluessel,
    text: p.hinweis || p.titel || '',
    // Ziel AUS DEM SERVER (Einstellungs-Unterseite bzw. Mitglieder/Kalender) —
    // die Oberfläche rät hier nichts. `#/einstellungen` ist nur ein Notnagel.
    ziel: p.ziel || EINSTELLUNGEN_ROUTE,
    zielText: TEXTE.einrichten,
  }))
}

/**
 * Leerzustand der MITGLIEDERLISTE (Frame 12).
 *
 * Drei Fälle, die im Browser leicht verwechselt werden:
 *   - es gibt überhaupt keine Person (Server: `gesamt_alle === 0`) → der
 *     freundliche Zustand mit zwei Wegen (CSV-Import / von Hand).
 *   - es gibt Personen, aber Suche/Filter greifen → „Suche oder Filter
 *     anpassen“ (ein „Noch keine Mitglieder“ wäre hier schlicht falsch).
 *   - die Zahl ist unbekannt (`null`) → wie „Filter greift“ behandeln; lieber
 *     zu wenig behaupten als fälschlich „alles leer“.
 *
 * Die Wege sind die VORHANDENEN: `#/personen/import` (Import-Reiter) und
 * der Dialog „Mitglied hinzufügen“ der Liste (`anlegen: true` → der Aufrufer
 * öffnet den vorhandenen Dialog, statt eine zweite Maske zu bauen).
 *
 * @returns {{leer: boolean, titel: string, text: string, fuss: string,
 *            zeigeImport: boolean, zeigeAnlegen: boolean, anlegen: boolean}}
 */
export function mitgliederLeerzustand({ gesamtAlle = null, admin = false } = {}) {
  // ACHTUNG: `Number(null)` ist 0 — eine UNBEKANNTE Zahl (`null`, Feld fehlt)
  // darf aber nicht als „nichts vorhanden“ durchgehen. Deshalb wird zuerst auf
  // einen echten Wert geprüft, erst dann gewandelt.
  const wirklichLeer = gesamtAlle !== null && gesamtAlle !== undefined
    && gesamtAlle !== ''
    && Number.isFinite(Number(gesamtAlle)) && Number(gesamtAlle) === 0
  if (!wirklichLeer) {
    return {
      leer: false,
      titel: TEXTE.mitgliederFilterTitel,
      text: TEXTE.mitgliederFilterText,
      fuss: '',
      zeigeImport: false,
      zeigeAnlegen: false,
      anlegen: false,
    }
  }
  return {
    leer: true,
    titel: TEXTE.mitgliederLeerTitel,
    text: TEXTE.mitgliederLeerText,
    fuss: TEXTE.mitgliederLeerFuss,
    // Beide Wege sind Verwaltungsarbeit — der Server weist andere ab.
    zeigeImport: admin === true,
    zeigeAnlegen: admin === true,
    anlegen: true,
  }
}

/**
 * Leerzustand der KALENDERLISTE (dasselbe Muster, Frame 12).
 *
 * `anzahl` ist die Zahl der sichtbaren Kalender; `gesamt` die Zahl aller
 * Kalender der Gemeinde (nur Admin bekannt, sonst `null`). Ohne `gesamt` wird
 * „nichts freigegeben“ NICHT behauptet — dann gilt „Filter/Rechte“.
 */
export function kalenderLeerzustand({ anzahl = 0, gesamt = null, admin = false } = {}) {
  const sichtbar = Number(anzahl) || 0
  if (sichtbar > 0) {
    return { leer: false, titel: '', text: '', fuss: '', zeigen: false }
  }
  const alle = Number(gesamt)
  if (admin === true && Number.isFinite(alle) && alle === 0) {
    return {
      leer: true,
      titel: TEXTE.kalenderLeerTitel,
      text: TEXTE.kalenderLeerText,
      fuss: '',
      zeigen: true,
      ziel: KALENDER_VERWALTUNG_ROUTE,
      zielText: TEXTE.kalenderAnlegen,
    }
  }
  return {
    leer: false,
    titel: TEXTE.kalenderFilterTitel,
    text: TEXTE.kalenderFilterText,
    fuss: '',
    zeigen: true,
    ziel: '',
    zielText: '',
  }
}

/**
 * „Später erinnern“: die Karte bleibt bis einschließlich (heute + Tage)
 * ausgeblendet (`erinnerung_ab`), siehe docs/ON2-VERTRAG.md. Der Aufruf geht
 * über `einrichtung.erinnern_spaeter`; die Antwort wird in den Stand
 * übernommen, damit die Karte sofort verschwindet (kein zweiter Abruf nötig).
 */
export const ERINNERUNG_TAGE = 7

export function erinnerungBis(heute = new Date(), tage = ERINNERUNG_TAGE) {
  const basis = new Date(heute.getTime())
  basis.setDate(basis.getDate() + Math.max(1, Number(tage) || ERINNERUNG_TAGE))
  return tagIso(basis)
}

/**
 * Ruft `einrichtung.erinnern_spaeter` auf und übernimmt das Datum.
 * @returns {Promise<string>} das Datum (`YYYY-MM-DD`) oder `''` bei Fehler.
 */
export async function spaeterErinnern(tage = ERINNERUNG_TAGE, heute = new Date()) {
  try {
    const antwort = await apiCall(EINRICHTUNG + 'erinnern_spaeter', { tage })
    const d = antwort?.message || antwort
    const bis = String(d?.erinnerung_ab || erinnerungBis(heute, tage))
    if (statusStand.value && typeof statusStand.value === 'object') {
      statusStand.value = { ...statusStand.value, erinnerung_ab: bis }
    }
    return bis
  } catch {
    // Der Hinweis bleibt stehen — er ist wichtiger als die Erinnerung.
    return ''
  }
}
