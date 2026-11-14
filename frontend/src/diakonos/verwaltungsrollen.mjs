/**
 * UI-R10b — EINE Quelle für „das sind Verwaltungsrollen“.
 *
 * Der Server verlangt für den Schalter „Verwaltungsrollen über Authentik-Gruppen“
 * und für Zuordnungen auf diese Rollen einen System Manager
 * (`anmeldung/einstellungen_api._pruefe_admin_gruppen` gegen
 * `frappe_compat.permissions.ADMIN_ROLES`). Das Frontend sperrt genau diese
 * Rollen für alle anderen — dieselbe Liste, an EINER Stelle:
 * `pages/einstellungen/RollenRechte.vue` und `pages/einstellungen/Anmeldung.vue`
 * importieren sie hier, statt sie je Seite zu wiederholen.
 *
 * Eigene Datei (nicht `RollenRechte.vue`): die beiden Seiten sind Geschwister;
 * ein Import quer über Seiten hinweg wäre eine Abhängigkeit ohne Grund, und ein
 * Test kann die Liste ohne DOM und ohne SFC-Kompilierung lesen.
 *
 * Reihenfolge wie `ADMIN_ROLES` im Server.
 */
export const VERWALTUNGSROLLEN = ['System Manager', 'Mitgliederadministrator']

/** Trägt diese Rollenkennung Verwaltungsrechte? */
export function istVerwaltungsrolle(rolle) {
  return VERWALTUNGSROLLEN.includes(String(rolle || ''))
}
