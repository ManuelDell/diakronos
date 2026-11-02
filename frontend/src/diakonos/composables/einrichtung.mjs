/**
 * ON-2 — Einrichtung: Karte, Fortschritt und Monogramm.
 *
 * Die Oberflaeche baut ihre Angaben NICHT selbst aus einzelnen Feldern nach,
 * sondern aus der Antwort von `einrichtung.status` (Server = eine Quelle der
 * Wahrheit, siehe `backend/src/diakronos_app/api/einrichtung.py`). Dieses Modul
 * haelt nur die rein darstellende Rechnung, damit sie testbar ist:
 *
 *   - `karteZeigen(status, heute)` — ob die Einrichtungs-Karte auf der
 *     Uebersicht erscheint (nicht, wenn alles erledigt ist, der Assistent noch
 *     laeuft oder „Spaeter erinnern“ noch gilt).
 *   - `offenePunkte(status)` — die noch offenen Punkte in Serverreihenfolge
 *     (Karte „Einrichtung abschliessen“, Entwurf Frame 10).
 *   - `fortschrittText(status)` — „3 von 7 offen“ / „4 von 7 Punkten erledigt“
 *     (woertlich aus dem Entwurf).
 *   - `monogramm(status, gemeindename)` — der Buchstabe fuer den Platzhalter,
 *     wenn kein Logo hinterlegt ist (`kurzname` vor `gemeindename`, Entwurf 04:
 *     „Ohne Logo verwendet Diakronos ein Monogramm.“).
 *   - `logoQuelle(status)` — die Fertig-Adresse des Logos oder `null`.
 *
 * Bewusst KEINE Farben/Schriften/Radien: das ist Sache der Komponenten und der
 * Tokens (`tokens.css`). Hier steht nur Text und Wahrheitslogik.
 */

/** Ein Datum als `YYYY-MM-DD` in LOKALER Zeit (nicht UTC-verschoben). */
export function tagIso(datum) {
  const d = datum instanceof Date ? datum : new Date(datum)
  if (Number.isNaN(d.getTime())) return ''
  const monat = String(d.getMonth() + 1).padStart(2, '0')
  const tag = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${monat}-${tag}`
}

/**
 * Gilt die Erinnerung noch? `erinnerung_ab` ist ein Datum: die Karte bleibt bis
 * EINSCHLIESSLICH dieses Tages ausgeblendet (der Server liefert nur zukuenftige
 * Daten — ein vergangenes Datum kommt gar nicht erst an).
 */
export function erinnerungAktiv(status, heute = new Date()) {
  const bis = String(status?.erinnerung_ab || '').trim()
  if (!bis) return false
  const heuteIso = tagIso(heute)
  return Boolean(heuteIso) && bis >= heuteIso
}

/**
 * Soll die Einrichtungs-Karte auf der Uebersicht erscheinen?
 *
 * Nein, wenn
 *   - alles erledigt ist (`offen_anzahl === 0`) — dann gibt es nichts zu tun,
 *   - der Assistent noch NICHT abgeschlossen ist (dann laeuft er gerade; die
 *     Karte waere eine zweite Baustelle),
 *   - „Spaeter erinnern“ noch gilt.
 */
export function karteZeigen(status, heute = new Date()) {
  if (!status || typeof status !== 'object') return false
  const offen = Number(status.offen_anzahl)
  if (!Number.isFinite(offen) || offen <= 0) return false
  if (status.assistent_abgeschlossen !== true) return false
  return !erinnerungAktiv(status, heute)
}

/** Die offenen Punkte in der Reihenfolge des Servers (Frame 10). */
export function offenePunkte(status) {
  const punkte = Array.isArray(status?.punkte) ? status.punkte : []
  return punkte.filter((p) => p && p.erledigt === false)
}

/**
 * „3 von 7 offen“ bzw. „4 von 7 Punkten erledigt“ — woertlich aus dem Entwurf.
 * Bei 0 offen kommt der Erledigt-Satz, sonst der Offen-Satz.
 */
export function fortschrittText(status) {
  const gesamt = Number(status?.gesamt_anzahl) || 0
  const offen = Number(status?.offen_anzahl) || 0
  const erledigt = Number.isFinite(Number(status?.erledigt_anzahl))
    ? Number(status.erledigt_anzahl)
    : Math.max(0, gesamt - offen)
  if (!gesamt) return ''
  if (offen === 0) return `${erledigt} von ${gesamt} Punkten erledigt`
  return `${offen} von ${gesamt} offen`
}

/** Anteil erledigter Punkte 0…1 (fuer den Fortschrittsbalken). */
export function fortschrittAnteil(status) {
  const gesamt = Number(status?.gesamt_anzahl) || 0
  if (gesamt <= 0) return 0
  const erledigt = Number.isFinite(Number(status?.erledigt_anzahl))
    ? Number(status.erledigt_anzahl)
    : gesamt - (Number(status?.offen_anzahl) || 0)
  return Math.min(1, Math.max(0, erledigt / gesamt))
}

/**
 * Buchstabe fuer das Monogramm.
 *
 * Reihenfolge wie im Entwurf: Kurzname vor Gemeindename („Erscheint in
 * Kopfzeile und Kalenderkuerzeln“). Genommen wird der erste Buchstabe bzw. die
 * erste Ziffer; Umlaute und Akzente werden auf ihren Grundbuchstaben reduziert
 * („Ökumene“ -> „O“). Leer -> ``?`` (der Aufrufer zeigt dann nichts Besonderes).
 */
export function monogramm(status, gemeindename = '') {
  const kandidaten = [status?.kurzname, status?.gemeindename, gemeindename]
  for (const roh of kandidaten) {
    const text = String(roh ?? '').trim()
    if (!text) continue
    const erstes = text.replace(/^[^\p{L}\p{N}]+/u, '')[0]
    if (!erstes) continue
    const grund = erstes.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    return (grund || erstes).toUpperCase()
  }
  return '?'
}

/**
 * Adresse des hinterlegten Logos oder `null`.
 *
 * Der Server liefert `logo_url` bereits MIT Betriebspraefix (WEB-5a) aus; hier
 * wird NICHTS nachgebaut. Ein leerer Wert heisst „kein Logo“ -> Monogramm.
 */
export function logoQuelle(status) {
  const url = String(status?.logo_url || '').trim()
  if (!url || status?.logo_vorhanden === false) return null
  return url
}
