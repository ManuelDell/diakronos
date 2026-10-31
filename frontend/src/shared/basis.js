/**
 * WEB-5b — EINE Quelle fuer den Betriebs-Praefix (`basePath`).
 *
 * Warum: Diakronos kann unter einem Praefix laufen (`DIAKRONOS_BASE_PATH=/diakonos`).
 * Dann liegen API, Anmeldung, Dateien und socket.io unter `{basePath}/…`, die
 * SPA selbst unter `{basePath}/diakonos`. Jede Stelle, die eine Backend-Adresse
 * selbst zusammengebaut hat, zeigte vorher fest auf `/api/…`, `/files/…`,
 * `/login`, `/logout` — unter dem Praefix also auf 404 (bzw. auf die Website,
 * die auf `/` liegt).
 *
 * Vorher stand `basePath` NIRGENDS im Frontend, obwohl der Server es seit
 * WEB-5a im Boot-Objekt mitliefert (siehe `frontend/BOOT_VERTRAG.md`).
 *
 * Regeln (Waechter: `tests/web5b-praefix.test.mjs`):
 *   - Diese Datei ist die EINZIGE Stelle in `frontend/src`, die ein
 *     Backend-Pfad-Literal wie `"/api/…"` enthalten darf.
 *   - Alle anderen Dateien bauen ihre Adressen ueber `mitBasis()`, `apiUrl()`,
 *     `dateiUrl()`, `socketPfad()`, `anmeldeUrl()` — oder ueber einen der
 *     zentralen Helfer (`useApi.js`, `shared/sitzung-pruefen.js`), die es tun.
 *   - Hash-Routen der SPA (`#/…`) bekommen KEINEN Praefix: der Router bleibt
 *     unveraendert, der Hash ist relativ zur aktuellen Seite.
 *
 * Ohne Praefix (`basePath` leer/fehlend) ist das Ergebnis Zeichen fuer Zeichen
 * die alte Adresse — das ist die Gegenprobe der Karte („unveraendert ohne
 * Praefix").
 */

/**
 * Betriebs-Praefix dieses Dokuments, normalisiert:
 * fuehrender Schraegstrich, KEIN abschliessender, ohne Schraegstrich = "".
 *
 * Gelesen wird `window.__DIakonosBOOT.basePath` (WEB-5a-Vertrag). Der Server
 * normalisiert den Wert bereits; das Frontend prueft trotzdem defensiv, weil
 * die Bundles `gast`, `registrierung` und `organigramm` auch von Seiten
 * geladen werden koennen, in denen das Objekt fehlt (dann: kein Praefix).
 *
 * BEWUSST bei jedem Aufruf gelesen statt beim Modul-Import zwischengespeichert:
 * `useSitzungsablauf.js` schreibt `window.__DIakonosBOOT` zur Laufzeit um,
 * Tests setzen das Objekt nach dem Import. Ein zwischengespeicherter Wert
 * waere eine zweite Wahrheit.
 */
export function basisPfad() {
  let roh = ''
  try {
    roh = globalThis.window?.__DIakonosBOOT?.basePath || ''
  } catch {
    roh = ''
  }
  let pfad = String(roh).trim()
  if (!pfad || pfad === '/') return ''
  if (!pfad.startsWith('/')) pfad = '/' + pfad
  return pfad.replace(/\/+$/, '')
}

/**
 * Setzt den Betriebs-Praefix vor einen absoluten Backend-Pfad.
 *
 *   mitBasis('/api/method/x')   -> '/api/method/x'        (ohne Praefix)
 *                               -> '/diakronos/api/method/x' (mit Praefix)
 *   mitBasis('logout')          -> '/logout' / '/diakronos/logout'
 *   mitBasis('')                -> Praefix selbst ('/diakonos' bzw. '')
 *
 * Idempotent: ein bereits praefigierter Pfad wird NICHT doppelt versehen
 * (der Server liefert z. B. `file_url` und Registrierungslinks schon
 * praefigiert aus — die duerfen nicht zu `/diakronos/diakronos/…` werden).
 */
export function mitBasis(pfad) {
  const basis = basisPfad()
  let rest = String(pfad ?? '')
  rest = rest.startsWith('/') ? rest : '/' + rest
  if (!basis) return rest
  if (rest === basis || rest.startsWith(basis + '/')) return rest
  // Leerer Pfad = der Präfix selbst (OHNE Schluss-Schrägstrich: '/diakonos/'
  // würde von Starlette als Wurzel des Mounts gelesen und ggf. umgeleitet).
  if (rest === '/') return basis
  return basis + rest
}

/** Adresse einer Frappe-Methode: `apiUrl('diakronos.x.y')` bzw. mit Praefix davor. */
export function apiUrl(methode) {
  return mitBasis('/api/method/' + String(methode || ''))
}

/** Adresse einer Ressource: `ressourceUrl('Element/abc?fields=[…]')`. */
export function ressourceUrl(pfad) {
  return mitBasis('/api/resource/' + String(pfad || ''))
}

/**
 * Adresse einer hochgeladenen Datei.
 *
 * Der Server stellt `file_url` in API-Antworten bereits mit Praefix voran
 * (WEB-5a). Aeltere/alte Daten koennen noch das nackte `/files/…` liefern —
 * `mitBasis` ist idempotent und macht daraus genau eine Praefix-Ebene.
 * Absolute Adressen (`http://…`, `data:`, `blob:`) bleiben unveraendert.
 */
export function dateiUrl(url) {
  const text = String(url ?? '')
  if (!text) return ''
  if (/^[a-z][a-z0-9+.-]*:/i.test(text) || text.startsWith('//')) return text
  return mitBasis(text)
}

/**
 * Adresse der Anmeldemaske, mit Ruecksprungziel (`redirect-to`).
 *
 * `grund` (WEB-8c R4) ist eine FESTE Kennung, kein Freitext: die Maske bildet
 * sie auf einen festen Hinweis ab. So kann niemand beliebigen Text ueber die
 * Adresse einschleusen — und der Hinweis reist trotzdem mit.
 *   `grund=csrf` -> „Sitzung abgelaufen — bitte neu anmelden."
 */
export function anmeldeUrl(ziel, grund) {
  const basis = mitBasis('/login')
  const teile = []
  if (ziel !== undefined && ziel !== null && ziel !== '') {
    teile.push('redirect-to=' + encodeURIComponent(String(ziel)))
  }
  const kennung = typeof grund === 'string' ? grund.trim() : ''
  if (kennung) teile.push('grund=' + encodeURIComponent(kennung))
  return teile.length ? basis + '?' + teile.join('&') : basis
}

/**
 * Pfad der socket.io-Verbindung fuer den Client.
 *
 * WEB-5a-Vertrag: Request-Pfad `{basePath}/socket.io`, also
 * `io({path: socketPfad()})`. Ohne Praefix exakt `/socket.io` (so war es
 * vorher fest verdrahtet).
 */
export function socketPfad() {
  return mitBasis('/socket.io')
}

/** Adresse des Zustandspruefers (Docker-Healthcheck/Statusanzeigen). */
export function healthUrl() {
  return mitBasis('/healthz')
}
