import { GELOESCHT_ANZEIGE, istGeloescht } from '../../composables/geloeschte-person.mjs'

export const DATENSCHUTZ_STAND = { ok: 'Vorhanden', fehlt: 'Fehlt', widerrufen: 'Widerrufen' }

export function gefiltertePersonen(personen, stand, suche) {
  const q = suche.trim().toLocaleLowerCase('de')
  return personen.filter(m => (!stand || m.dsgvo_status === stand)
    && `${m.vorname || ''} ${m.nachname || ''} ${m.email || ''}`.toLocaleLowerCase('de').includes(q))
}

/**
 * Anzeigename einer Zeile der DSGVO-Liste (DSGVO-2d).
 *
 * Eine geloeschte Person traegt keinen Namen mehr: der Server liefert dort
 * bereits "Gelöschte Person" und `geloescht: true`. Der Helfer haelt den Text
 * an EINER Stelle, damit die Liste nicht auf einen Restnamen zurueckfaellt,
 * sollte ein alter Sicherungsstand noch einen tragen.
 */
export function personenAnzeige(m) {
  if (!m) return ''
  if (m.geloescht || istGeloescht(m)) return GELOESCHT_ANZEIGE
  const voll = [m.vorname, m.nachname].filter(Boolean).join(' ').trim()
  return voll || 'Person ohne Namen'
}

export function zweiteBestaetigung(schritt, wort) {
  return schritt === 2 && wort === 'ANONYMISIEREN'
}
