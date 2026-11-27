/**
 * ASVS2-3: Vorpruefung im Browser (der Server prueft verbindlich).
 * Rueckgabe: Fehlertext oder ''.
 */
export function pruefeEingabe(aktuell, neu, wiederholung) {
  if (!aktuell) return 'Bitte das aktuelle Passwort eingeben.'
  if (!neu || neu.length < 8) return 'Das neue Passwort braucht mindestens 8 Zeichen.'
  if (neu !== wiederholung) return 'Die beiden neuen Passwörter stimmen nicht überein.'
  if (neu === aktuell) return 'Das neue Passwort muss sich vom aktuellen unterscheiden.'
  return ''
}
