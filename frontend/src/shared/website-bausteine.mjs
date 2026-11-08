/**
 * BS-2d — Prüfbare Regeln des Bereichs „Bausteine“ (ohne Vue).
 *
 * Warum eine eigene Datei: „Ist der Stand aktuell?“, „welche Freigaben nutzt
 * dieser Baustein?“, „welcher Knopf gehört dazu?“ sind FACHLOGIK. Im Bauteil
 * wären sie nur als Quelltext lesbar (`assert.match`), also nicht nachweisbar
 * — dieselbe Aufteilung wie `shared/website-freigaben.mjs` (BS-1d).
 *
 * Vertrag des Servers (BS-2a/BS-2a2, `api/website.py`):
 *
 *   GET  diakronos.diakronos.api.website.bausteine_status
 *        -> {erreichbar: bool,
 *            mitgeliefert_version: int,   # was Diakronos mitbringt
 *            installiert_version: int,    # was im Website-Baukasten liegt (0 = nichts)
 *            veraltet: bool,              # installiert < mitgeliefert
 *            revision: str,
 *            hinweis: str,                # Klartext, wenn nicht abrufbar
 *            bausteine: [{kennung, name, version}, …]}
 *   POST diakronos.diakronos.api.website.bausteine_installieren
 *        -> {version: int, bausteine: [kennung, …], revision: str, weg: "zip"|"einzeln"}
 *
 * WICHTIG (Karte BS-2d): Die Liste der Bausteine kommt AUSSCHLIESSLICH aus
 * `bausteine_status` — nichts wird hier hart kodiert. Der Stand je Zeile
 * entsteht aus dem Vergleich der installierten Fassung mit der
 * mitgelieferten; eine Zeile ohne Eintrag gilt NICHT als installiert
 * (Default AUS, G1).
 *
 * BS-2d2 (Nacharbeit): Name, Beschreibung und Freigaben liefert der Server in
 * `mitgeliefert[]` (BS-2d1 — gelesen aus `block.json` der Quelle). Die früher
 * hier stehende feste Zuordnungstabelle Kennung → Freigaben ist ERSATZLOS
 * entfernt: sie hätte jede neue Freigabe an zwei Stellen verlangt und bei
 * einer Änderung still gelogen. Fehlt eine Angabe, sagt die Oberfläche das
 * („unbekannt“), statt eine Freigabe zu erfinden.
 *
 * Angebunden wird der Website-Baukasten in der Oberfläche „Website-Baukasten“
 * — der Bereich heißt deshalb nach der Konzept-Entscheidung UX3a so, „Primo“
 * ist nur der technische Anbieter (WEB-1).
 */

/** Rollen mit Zugriff auf die Bausteine — deckungsgleich mit `_require_website_rolle`. */
export const BAUSTEIN_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']

/** Wie viele Freigaben JE BAUSTEIN genannt werden; der Rest wird gezählt. */
export const FREIGABEN_MAX = 4

/**
 * Anzeigename des Werkzeugs (Konzept-Entscheidung: „Website-Baukasten“).
 * Steht hier EINMAL, damit Knopf, Anleitung und Meldungen denselben Namen
 * tragen (Prinzip S4).
 */
export const WERKZEUG = 'Website-Baukasten'

/**
 * Kurzanleitung (Karten-Ziel): wo der Baustein in der Website eingesetzt und
 * wie er angepasst wird. Als DATEN, nicht als Fließtext im Bauteil — so prüft
 * ein Test die Sätze, und die Reihenfolge bleibt an einer Stelle.
 *
 * @returns {string[]} drei Sätze
 */
export function bausteineAnleitung() {
  return [
    `Im ${WERKZEUG} einen Block hinzufügen und die Bibliothek wählen.`,
    'Dort die Gruppe „Diakronos“ öffnen und den gewünschten Baustein einsetzen.',
    'Felder im Baustein anpassen; Farben, Schriften und Abstände kommen aus den Site-Stilen (--dk-*).',
  ]
}

/**
 * Darf dieser Benutzer den Bereich „Bausteine“ sehen?
 *
 * Wie `darfFreigabenVerwalten` (BS-1d) nur Komfort: der Server weist jede
 * Anfrage ohne Website-Rolle mit 403 ab. Die Sichtbarkeit ist trotzdem nötig,
 * weil die Seite sonst einen Bereich zeigt, der immer nur Fehler liefert.
 *
 * @param {{rollen?: unknown}} [eingabe]
 * @returns {boolean}
 */
export function darfBausteineSehen({ rollen = null } = {}) {
  const vorhanden = new Set(
    (Array.isArray(rollen) ? rollen : []).map((r) => String(r || '').trim()),
  )
  return BAUSTEIN_ROLLEN.some((r) => vorhanden.has(r))
}

/** Ganze Zahl >= 0 aus beliebiger Server-Angabe; alles andere ist 0. */
function zahl(wert) {
  const n = Number(wert)
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.floor(n)
}

/**
 * Stand der Bibliothek als reine Zahlen (null-Werte zählen als 0).
 *
 * @param {object|null|undefined} daten  Antwort von `bausteine_status`
 * @returns {{erreichbar: boolean, mitgeliefert: number, installiert: number,
 *            veraltet: boolean, hinweis: string, revision: string}}
 */
export function bausteineStand(daten) {
  const mitgeliefert = zahl(daten?.mitgeliefert_version)
  const installiert = zahl(daten?.installiert_version)
  const erreichbar = daten?.erreichbar === true
  return {
    erreichbar,
    mitgeliefert,
    installiert,
    // Nur ein erreichbares Werkzeug kann veraltet sein. Die Rechnung wird
    // NICHT geglaubt, sondern aus den Zahlen gestellt — der Server rechnet
    // genauso (`Stand.veraltet`), eine Abweichung wäre ein Anzeigefehler.
    veraltet: erreichbar && installiert < mitgeliefert,
    hinweis: String(daten?.hinweis ?? '').trim(),
    revision: String(daten?.revision ?? '').trim(),
  }
}

/**
 * Zustand des BEREICHS (Kopfzeile): Ton, Titel und der eine Satz darunter.
 *
 * Fünf Zustände (Prinzip I5): nicht erreichbar · nichts installiert ·
 * veraltet · aktuell · nichts mitgeliefert (Auslieferungsfehler).
 *
 * @param {object|null|undefined} daten
 * @returns {{ton: string, titel: string, text: string, aktion: string}}
 *   `ton`: Badge-Variante (ok|warn|err|neutral), `aktion`: Beschriftung des
 *   einen Knopfes ('' = kein Knopf möglich).
 */
export function bausteineZustand(daten) {
  const stand = bausteineStand(daten)
  if (!stand.erreichbar) {
    return {
      ton: 'warn',
      titel: 'Nicht abrufbar',
      text: stand.hinweis
        || `Der Stand im ${WERKZEUG} lässt sich gerade nicht lesen. Ein Einspielen ist erst möglich, wenn die Anbindung steht.`,
      aktion: '',
    }
  }
  if (stand.mitgeliefert < 1) {
    return {
      ton: 'err',
      titel: 'Nichts mitgeliefert',
      text: 'Diese Installation bringt keine Bausteine mit. Bitte den Support informieren.',
      aktion: '',
    }
  }
  if (stand.installiert < 1) {
    return {
      ton: 'info',
      titel: 'Noch nicht eingespielt',
      text: `Im ${WERKZEUG} liegt noch keiner der mitgelieferten Bausteine.`,
      aktion: 'In Website-Baukasten einspielen',
    }
  }
  if (stand.veraltet) {
    return {
      ton: 'warn',
      titel: 'Aktualisierung verfügbar',
      text: `Eingespielt ist Fassung ${stand.installiert}, mitgeliefert ist Fassung ${stand.mitgeliefert}.`,
      aktion: 'Im Website-Baukasten aktualisieren',
    }
  }
  return {
    ton: 'ok',
    titel: 'Aktuell',
    text: `Eingespielt ist Fassung ${stand.installiert} — so viel bringt diese Installation mit.`,
    aktion: '',
  }
}

/**
 * Anzeige eines Freigabenamens. Der Server nennt die Freigaben mit ihrem
 * technischen Namen (`termine`, `kontaktpostfaecher`, … — Positivliste
 * `FREIGABEN` in `website/bausteine.py`); die Oberfläche spricht deutsch.
 *
 * Unbekannte Namen werden NICHT verschluckt und NICHT umgedeutet: sie
 * erscheinen, wie der Server sie nennt. Ein Name, den diese Liste nicht kennt,
 * ist eine Lücke der ANZEIGE (neue Freigabe im Server), keine erfundene
 * Freigabe.
 */
export const FREIGABE_NAMEN = {
  termine: 'Termine',
  kalender: 'Kalender',
  gruppen: 'Gruppen',
  beitraege: 'Beiträge',
  kontaktpostfaecher: 'Kontakt-Postfächer',
}

/** Text, wenn der Server zu einem Baustein KEINE Freigabe-Angabe macht. */
export const FREIGABEN_UNBEKANNT = 'unbekannt'

/**
 * Die Freigaben eines Bausteins — aus der Serverantwort (`mitgeliefert[]`).
 *
 * Quelle ist AUSSCHLIESSLICH der Eintrag aus `bausteine_status`: die
 * Freigaben stehen in der `block.json` des Bausteins (BS-2d1) und kommen mit
 * der Liste. Hier ist KEINE Zuordnung hinterlegt (BS-2d2: die feste Tabelle
 * ist entfallen) — was der Server nicht nennt, wird nicht erfunden.
 *
 * @param {object|null|undefined} eintrag  Eintrag aus `mitgeliefert[]`
 * @returns {string[]} deutsche Namen der Freigabegruppen, in Serverreihenfolge
 */
export function bausteinFreigaben(eintrag) {
  const roh = Array.isArray(eintrag?.freigaben) ? eintrag.freigaben : []
  const namen = []
  for (const eintragName of roh) {
    const kennung = String(eintragName ?? '').trim()
    if (!kennung || namen.includes(FREIGABE_NAMEN[kennung] || kennung)) continue
    namen.push(FREIGABE_NAMEN[kennung] || kennung)
  }
  return namen
}

/**
 * Stand EINER Zeile — „mitgeliefert“ oder „installiert“.
 *
 * Eine Zeile ist installiert, wenn die Bibliothek dafür einen Eintrag hat.
 * Liegt sie hinter der mitgelieferten Fassung, heißt das „ältere Fassung“;
 * das ist kein Fehler, sondern der Grund für „aktualisieren“.
 *
 * @param {{version?: unknown}|null|undefined} eintrag  Eintrag aus `bausteine[]`
 * @param {number} mitgeliefert
 * @returns {{installiert: boolean, veraltet: boolean, ton: string, text: string}}
 */
export function bausteinZeileStand(eintrag, mitgeliefert) {
  const fassung = zahl(eintrag?.version)
  if (!eintrag || fassung < 1) {
    return { installiert: false, veraltet: false, ton: 'neutral', text: 'mitgeliefert' }
  }
  const ziel = zahl(mitgeliefert)
  if (ziel >= 1 && fassung < ziel) {
    return { installiert: true, veraltet: true, ton: 'warn', text: `ältere Fassung (${fassung})` }
  }
  return { installiert: true, veraltet: false, ton: 'ok', text: `installiert (${fassung})` }
}

/**
 * Die Zeilen des Bereichs: mitgelieferte Bausteine + installierte Fassung.
 *
 * Reihenfolge = Reihenfolge der Serverliste (`mitgeliefert[]`, der Installer
 * sortiert nach `block.json:index`, BS-2a). Mehrfacheinträge derselben Kennung
 * (alte und neue Fassung im Werkzeug) werden zusammengefasst: die HÖCHSTE
 * Fassung zählt.
 *
 * Je Zeile:
 *   kennung       Kennung des Bausteins
 *   name          `name` aus `mitgeliefert[]`; fehlt er, die Kennung
 *   beschreibung  `beschreibung` aus `mitgeliefert[]`; fehlt sie, ''
 *   freigaben     Freigaben aus `mitgeliefert[]` (deutsch); fehlt die Angabe,
 *                 [] — die Anzeige sagt dann „unbekannt“ (`freigabenHinweis`)
 *   fassung       höchste im Werkzeug liegende Fassung (0 = nicht dort)
 *   stand         `bausteinZeileStand`: mitgeliefert / installiert / ältere
 *
 * Ein Baustein, der im Werkzeug liegt, aber NICHT mitgeliefert wird (von Hand
 * angelegt, aus einer älteren Auslieferung), bleibt sichtbar — er ist Teil des
 * Stands. Sein Name kommt dann aus dem Blocknamen des Werkzeugs, wenn der
 * einen kennt.
 *
 * @param {object|null|undefined} daten
 * @returns {Array<{kennung: string, name: string, beschreibung: string,
 *                  freigaben: string[], freigabenBekannt: boolean,
 *                  fassung: number, stand: object}>}
 */
export function bausteinZeilen(daten) {
  const stand = bausteineStand(daten)
  const hoechste = new Map()
  for (const eintrag of Array.isArray(daten?.bausteine) ? daten.bausteine : []) {
    const kennung = String(eintrag?.kennung ?? '').trim()
    if (!kennung) continue
    const fassung = zahl(eintrag?.version)
    if (!hoechste.has(kennung) || hoechste.get(kennung).version < fassung) {
      hoechste.set(kennung, { ...eintrag, kennung, version: fassung })
    }
  }
  // Quelle für Name, Beschreibung und Freigaben ist `mitgeliefert[]` (BS-2d1:
  // die block.json der Quelle). Ohne das Feld — ältere Server, Fehler in den
  // Quellen — bleibt die Zeile karg, aber die Liste ist nicht leer: was im
  // Werkzeug liegt, wird weiterhin gezeigt.
  const quelle = Array.isArray(daten?.mitgeliefert) ? daten.mitgeliefert : []
  const zeilen = []
  const gesehen = new Set()
  for (const eintrag of quelle) {
    const kennung = String(eintrag?.kennung ?? '').trim()
    if (!kennung || gesehen.has(kennung)) continue
    gesehen.add(kennung)
    zeilen.push(zeileFuer(kennung, eintrag, hoechste.get(kennung), stand.mitgeliefert))
  }
  for (const eintrag of hoechste.values()) {
    if (gesehen.has(eintrag.kennung)) continue
    gesehen.add(eintrag.kennung)
    zeilen.push(zeileFuer(eintrag.kennung, null, eintrag, stand.mitgeliefert))
  }
  return zeilen
}

/**
 * EINE Zeile. `quelle` ist der Eintrag aus `mitgeliefert[]` (oder null, wenn
 * der Baustein nur im Werkzeug liegt), `eintrag` der Stand im Werkzeug.
 */
function zeileFuer(kennung, quelle, eintrag, mitgeliefert) {
  const freigaben = bausteinFreigaben(quelle)
  return {
    kennung,
    name: String(quelle?.name ?? '').trim() || kennung,
    beschreibung: String(quelle?.beschreibung ?? '').trim(),
    freigaben,
    // „Bekannt“ heißt: der Server hat zu diesem Baustein ÜBERHAUPT eine
    // Freigabe-Angabe gemacht — auch eine ausdrücklich LEERE. Ist das Feld
    // vorhanden (auch als null oder mit unbekannten Namen), ist das eine
    // Aussage; fehlt es ganz, weiß die Oberfläche nichts (→ „unbekannt“).
    freigabenBekannt: quelle != null && Object.hasOwn(quelle, 'freigaben'),
    fassung: zahl(eintrag?.version),
    stand: bausteinZeileStand(eintrag, mitgeliefert),
  }
}

/**
 * Der Satz unter einer Zeile: „Nutzt die Freigaben: …“ / „Braucht keine
 * Freigabe aus Diakronos.“ / „Freigaben: unbekannt“.
 *
 * Die drei Fälle sind BEWUSST verschieden (G1): eine ausdrücklich leere Liste
 * heißt „dieser Baustein fragt keine Freigabe-Daten ab“, eine fehlende Angabe
 * heißt „weiß die Oberfläche nicht“ — daraus darf keine Freigabe und keine
 * Unbedenklichkeit werden.
 *
 * @param {{freigaben?: string[], freigabenBekannt?: boolean}|null|undefined} zeile
 * @returns {string}
 */
export function freigabenHinweis(zeile) {
  const namen = Array.isArray(zeile?.freigaben) ? zeile.freigaben.filter(Boolean) : []
  if (namen.length) return `Nutzt die Freigaben: ${freigabenText(namen)}`
  // Bekannt-leer nur bei echter Serverangabe; sonst „unbekannt“.
  if (zeile?.freigabenBekannt === true) return 'Braucht keine Freigabe aus Diakronos.'
  return `Freigaben: ${FREIGABEN_UNBEKANNT}`
}

/**
 * Freigaben als Satz für die Anzeige: „Gruppen, Termine“ (+ „und 2 weitere“).
 *
 * @param {string[]} freigaben
 * @returns {string} '' wenn keine bekannt sind
 */
export function freigabenText(freigaben) {
  const liste = (Array.isArray(freigaben) ? freigaben : [])
    .map((f) => String(f ?? '').trim())
    .filter(Boolean)
  if (!liste.length) return ''
  if (liste.length <= FREIGABEN_MAX) return liste.join(', ')
  const rest = liste.length - FREIGABEN_MAX
  return `${liste.slice(0, FREIGABEN_MAX).join(', ')} und ${rest} weitere`
}

/**
 * Ergebnis-Meldung nach „einspielen“ — Klartext, ohne Jargon (Prinzip I4).
 *
 * @param {object|null|undefined} ergebnis  Antwort von `bausteine_installieren`
 * @returns {{ton: string, text: string}}
 */
export function installationsMeldung(ergebnis) {
  const zahlBausteine = Array.isArray(ergebnis?.bausteine) ? ergebnis.bausteine.length : 0
  const version = zahl(ergebnis?.version)
  if (zahlBausteine < 1) {
    return {
      ton: 'warn',
      text: `Es wurde nichts eingespielt. Bitte im ${WERKZEUG} nachsehen, ob die Bibliothek erreichbar ist.`,
    }
  }
  const stueck = zahlBausteine === 1 ? '1 Baustein' : `${zahlBausteine} Bausteine`
  const fassung = version >= 1 ? ` (Fassung ${version})` : ''
  return { ton: 'ok', text: `${stueck}${fassung} im ${WERKZEUG} eingespielt.` }
}
