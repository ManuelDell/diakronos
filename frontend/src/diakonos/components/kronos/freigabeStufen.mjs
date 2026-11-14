/**
 * UI-R4 — Moderationsstufen in der Prüfliste.
 *
 * Der Server (Rechte-Kern) entscheidet, WELCHE Stufe dran ist und OB der
 * Aufrufer sie prüfen darf: `get_kanban_board_data` liefert je Termin
 * `stufe` (untergruppe | gruppe | gemeinde | null) und `darf_pruefen`,
 * `event_crud.get_offene_aenderungen` je Änderungsvorschlag `stufe`.
 *
 * Diese Datei übersetzt das nur in Worte und blendet nichts Eigenes ein:
 * Sie erfindet keine Rechte.
 *
 * Die Anzeigenamen der Stufen kommen vom SERVER (`get_rollen_erklaerung()
 * .stufen_titel`, R-12): „Untergruppe“, „Gruppe“, „Alle Mitglieder der
 * Gemeinde“. Hier stehen KEINE eigenen Begriffslisten mehr — die Oberfläche
 * schreibt keine Rechte-Texte fest.
 *
 * UI-R4c (Punkt 1): Die Titel sind KEINE Objekte für „geht jetzt an …“.
 * „Alle Mitglieder der Gemeinde“ sind die Personen, die etwas SICHTBAR
 * bekommen — nicht die Prüfer. „… geht jetzt an Alle Mitglieder der Gemeinde“
 * klang deshalb nach erteilter Freigabe für alle. Die Stufe steht jetzt als
 * STUFE im Satz: „… geht jetzt an die Freigabe der Stufe „{titel}““. Die
 * Stufennamen sind damit immer als Stufe lesbar (auch „Nächste Stufe: …“).
 *
 * Endpunkt: `diakronos.api.rechte.get_rollen_erklaerung`; das Ergebnis wird
 * EINMAL geladen (`ladeStufenTitel`) und in `stufenTitel` gemerkt.
 *
 * WICHTIG: Diese Datei bleibt OHNE Vue-Import (reine Regeln). Sie wird auch
 * von `pruefZeile.mjs` benutzt, und Tests laden reine Helfer in einem
 * jsdom-Kontext — ein Vue-Import zöge dort ein zweites Vue mit eigenem
 * `document` nach (im Lauf gemessen: 6 UX3i-Mounttests brachen mit
 * „Cannot read properties of null (reading 'createElement')“).
 * Die reaktive Ablage liegt in `freigabeStufenReaktiv.mjs`.
 */

/**
 * UI-R4b — die Stufen-Kette rechnet NUR der Server.
 *
 * Hier stand bis UI-R4 eine feste Folge `STUFEN = ['untergruppe', 'gruppe',
 * 'gemeinde']`, aus der `naechsteStufe()` die nächste Stufe ableitete. Das war
 * falsch: die Kette kann eine Stufe ÜBERSPRINGEN (ein Inhalt aus einer
 * Untergruppe, der für die ganze Gemeinde gedacht ist, geht nach der
 * Untergruppe direkt an die Gemeinde). Seit R-12d nennt der Server die
 * nächste offene Stufe in der Antwort:
 *   · `resolve_conflict`            → `offen` (Liste), `naechste_stufe`
 *   · `finalize_staged_events`      → `festgelegt`, `weitergereicht`,
 *                                     `ergebnisse[id].naechste_stufe`
 * Die Oberfläche LIEST sie und erfindet keine. Ein fehlendes Feld bleibt
 * ehrlich leer („wartet auf die nächste Stufe“), statt geraten zu werden.
 */

/** Endpunkt der Stufen-Titel (EINE Quelle neben dem Rechte-Kern). */
export const STUFEN_TITEL_ENDPUNKT = 'diakronos.api.rechte.get_rollen_erklaerung'

/** Unbekannte/fehlende Stufe: ehrlich neutral, nie eine erfundene Stufe. */
export const STUFE_UNBEKANNT = '—'

/**
 * Server-Titel der Stufen (`{untergruppe: 'Untergruppe', …}`).
 *
 * Schlichter Container — geladen wird über `ladeStufenTitel`. Leer, solange
 * die Antwort fehlt; dann steht `STUFE_UNBEKANNT`, nie ein erfundenes Wort.
 *
 * @type {{ wert: Record<string, string> }}
 */
export const stufenTitel = { wert: {} }

/**
 * Zuletzt geladene Titel (immer der aktuelle Stand).
 * @returns {Record<string, string>}
 */
export function aktuelleStufenTitel() {
  return stufenTitel.wert
}

/**
 * Die Stufen-Titel vom Server holen und merken.
 *
 * Ein Fehler bleibt folgenlos: die Namen fehlen dann, aber die Anzeige
 * behauptet keine Stufe. Mehrfachaufrufe laden neu (billige Abfrage, die
 * Rollen-Erklärung ist statisch).
 *
 * Der Rückgabewert ist der neue Stand — die Oberfläche legt ihn in ihre
 * reaktive Ablage (`freigabeStufenReaktiv.mjs`).
 *
 * @param {(pfad: string, args?: object) => Promise<any>} apiCall
 * @returns {Promise<Record<string, string>>}
 */
export async function ladeStufenTitel(apiCall) {
  if (typeof apiCall !== 'function') return stufenTitel.wert
  try {
    const antwort = await apiCall(STUFEN_TITEL_ENDPUNKT, {})
    const titel = antwort?.stufen_titel
    if (titel && typeof titel === 'object' && Object.keys(titel).length) {
      stufenTitel.wert = { ...titel }
    }
  } catch {
    /* Ohne Antwort keine Namen — die Anzeige bleibt neutral. */
  }
  return stufenTitel.wert
}

/**
 * Name einer Stufe für Fließtext („wartet auf Freigabe für: Untergruppe“).
 *
 * Der Name ist der SERVER-Titel der Stufe. Fehlt er (noch), steht
 * `STUFE_UNBEKANNT` — die Oberfläche erfindet keinen Stufennamen.
 *
 * Liest den zuletzt geladenen Stand (`stufenTitel.wert`). Für reaktives
 * Neuzeichnen in Bauteilen siehe `freigabeStufenReaktiv.mjs`: dort wird der
 * Stand in einem `shallowRef` gehalten, und `stufenNameReaktiv` liest ihn.
 *
 * `kurz` bleibt als Parameter erhalten, weil die Titel selbst schon kurz
 * sind; der Server liefert genau einen Titel je Stufe.
 *
 * @param {string|null|undefined} stufe
 * @param {{kurz?: boolean}} [_optionen] — ohne Wirkung (Server-Titel gelten)
 * @returns {string}
 */
export function stufenName(stufe, _optionen = {}) {
  const schluessel = String(stufe || '').trim()
  if (!schluessel) return STUFE_UNBEKANNT
  return stufenTitel.wert[schluessel] || STUFE_UNBEKANNT
}

/**
 * Darf der Aufrufer diesen Eintrag prüfen? NUR der Server entscheidet.
 *
 * Fail closed: fehlt `darf_pruefen` (alte Antwort, Fehler), gilt „nicht
 * prüfen“ — die Knöpfe bleiben weg und der Server entscheidet ohnehin.
 *
 * @param {object|null|undefined} eintrag
 * @returns {boolean}
 */
export function darfPruefen(eintrag) {
  return eintrag?.darf_pruefen === true
}

/**
 * Ist der Eintrag noch nicht durch? Nur dann steht „wartet auf Freigabe für: …“.
 *
 * Wartend ist er genau dann, wenn der Server eine Stufe nennt (`stufe`) —
 * also jemand fehlt noch. `darf_pruefen` sagt nur, ob dieser Jemand der
 * Aufrufer ist, nicht ob etwas offen ist. Ohne Stufe: keine Warteline (es
 * wird keine Stufe erfunden).
 *
 * @param {object|null|undefined} eintrag
 * @returns {boolean}
 */
export function wartetNoch(eintrag) {
  if (!eintrag || typeof eintrag !== 'object') return false
  return Boolean(String(eintrag.stufe || '').trim())
}

/**
 * „wartet auf Freigabe für: <Stufe>“ — der Name ist der Server-Titel der
 * Stufe. `null`, wenn nichts wartet (dann steht keine Zeile).
 *
 * UI-R4d (Punkt 5): Die frühere Form „wartet auf: <Titel>“ las sich wie ein
 * Empfänger („wartet auf: Alle Mitglieder der Gemeinde“) — derselbe Fehler,
 * den UI-R4c in den Freigabe-Sätzen behoben hat. Die Stufe steht jetzt mit
 * dem Wort „Freigabe“ davor und ist damit immer als STUFE lesbar
 * (siehe `alsStufeText` für die Fließtext-Form).
 *
 * @param {object|null|undefined} eintrag
 * @returns {string|null}
 */
export function wartetAufText(eintrag) {
  if (!wartetNoch(eintrag)) return null
  return `wartet auf Freigabe für: ${stufenName(eintrag?.stufe)}`
}

/**
 * Ein Termin der Tafel gilt als „von mir zu prüfen“, wenn die Antwort das sagt
 * UND der Termin noch nicht festgelegt/abgelehnt ist. Der Status kommt vom
 * Server; diese Prüfung verhindert nur, dass eine alte Antwort einen erledigten
 * Termin in die Zählung hebt.
 *
 * @param {object|null|undefined} eintrag
 * @returns {boolean}
 */
export function zaehltAlsZuPruefen(eintrag) {
  if (!darfPruefen(eintrag)) return false
  const status = String(eintrag?.status || '')
  if (status && status !== 'Vorschlag' && status !== 'Konflikt') return false
  return true
}

/**
 * UI-R4c (Punkt 3) — ist das ein Konflikt, den nur der Dialog freigeben darf?
 *
 * Ein Einzeltermin trägt `status === 'Konflikt'`. Für SERIENKARTEN kommt
 * `has_konflikt` NICHT vom Server: `ModerationBoard.vue` (`groupItems`) baut
 * die Serienkarte im Client und setzt `has_konflikt`, sobald einer ihrer
 * Termine `status === 'Konflikt'` hat. Deshalb rechnet das Feld immer auf
 * denselben Server-Status zurück — es ist eine Ableitung, keine
 * Server-Auskunft.
 *
 * Die ID, die in `konflikte` (Brett-Antwort) steht, entscheidet zusätzlich —
 * dort hat der Server den Termin eingeordnet.
 *
 * WICHTIG: `column` gibt es am Item NICHT (das gehört zur Spalte der Vorlage);
 * die frühere Prüfung `item?.column === 'konflikte'` war deshalb nie wahr.
 *
 * @param {object|null|undefined} item Karte bzw. Eintrag (auch Serienkarte)
 * @param {string[]} [konfliktIds] IDs aus der Konfliktspalte der Antwort
 * @returns {boolean}
 */
export function istKonfliktEintrag(item, konfliktIds = []) {
  if (!item || typeof item !== 'object') return false
  const serie = item.type === 'serie'
  if (serie ? item.has_konflikt === true : item.status === 'Konflikt') return true
  if (String(item.status || '').trim() === 'Vorschlag') return false
  const ids = new Set(
    serie
      ? [item.id, ...(item.event_ids || []), ...(item.events || []).map(e => e?.id)]
      : [item.id],
  )
  return (Array.isArray(konfliktIds) ? konfliktIds : [])
    .some(id => ids.has(id))
}

/**
 * Zählt die Einträge, die der Nutzer wirklich prüfen darf.
 *
 * @param {Array<object>|null|undefined} eintraege
 * @returns {number}
 */
export function zaehleZuPruefen(eintraege) {
  if (!Array.isArray(eintraege)) return 0
  return eintraege.filter(zaehltAlsZuPruefen).length
}

/**
 * Freigabe-Antwort des Servers in eine ehrliche Meldung übersetzen.
 *
 * Zwei Wege sagen „noch nicht fertig“:
 *  · `aenderung_freigeben` liefert `{wartet_weiter: true, meldung}` — die
 *    STUFE ist freigegeben, die Änderung aber nicht übernommen.
 *  · `resolve_conflict` (Termin) nennt seit R-12d `offen` und
 *    `naechste_stufe`; bleibt der Status „Vorschlag“/„Konflikt“, ist eine
 *    weitere Stufe offen. „Festgelegt“ heißt fertig.
 *
 * Deshalb wird das Fortbestehen IMMER aus der Antwort abgeleitet — nie aus
 * der Stufe, die der Aufrufer gerade geprüft hat (sonst stünde „Termin
 * freigegeben“, obwohl er noch wartet).
 *
 * Die NÄCHSTE Stufe wird ebenfalls nur gelesen: `naechste_stufe` aus der
 * Antwort (R-12d). Die früher hier gerechnete feste Folge war falsch, sobald
 * die Kette eine Stufe überspringt (untergruppe → gemeinde). Nennt der Server
 * keinen Namen, bleibt der Satz ohne Stufennamen.
 *
 * @param {object|null|undefined} antwort
 * @param {{art?: 'termin'|'aenderung', stufe?: string|null}} [kontext]
 *        `stufe`: die zuletzt geprüfte Stufe — nur Rückfall, wenn der Server
 *        „wartet weiter“ sagt, aber gar keinen Namen nennt.
 * @returns {{text: string, ton: 'success'|'warning', weiter: boolean}}
 */
export function freigabeMeldung(antwort, { art = 'aenderung', stufe = null } = {}) {
  const meldung = String(antwort?.meldung || '').trim()
  const konflikt = Array.isArray(antwort?.belegung_konflikt) && antwort.belegung_konflikt.length > 0
  const weiter = wartetWeiter(antwort)

  if (weiter) {
    // Der Satz des Servers gilt wörtlich (er nennt die nächste Stufe selbst).
    if (meldung) return { text: meldung, ton: 'warning', weiter: true }
    const wer = alsStufeText(naechsteStufeName(antwort, stufe))
    const was = art === 'termin' ? 'der Termin' : 'die Änderung'
    return {
      text: wer
        ? `Stufe freigegeben — ${was} geht jetzt an ${wer}.`
        : `Stufe freigegeben — ${was} wartet auf die nächste Stufe.`,
      ton: 'warning',
      weiter: true,
    }
  }

  // Die Server-Meldungen schreiben „ueberschneidet“ (ae/ue, ohne Umlaute);
  // beide Formen müssen als Warnung erkannt werden, sonst wird aus der
  // Warnung ein grünes „erledigt“.
  if (meldung && /überschneid|ueberschneid/i.test(meldung)) {
    return { text: meldung, ton: 'warning', weiter: false }
  }

  if (konflikt) {
    return {
      text: 'Freigegeben — Achtung: der Termin überschneidet sich mit einer anderen Belegung.',
      ton: 'warning',
      weiter: false,
    }
  }

  if (meldung) return { text: meldung, ton: 'success', weiter: false }

  return {
    text: art === 'termin' ? 'Termin freigegeben.' : 'Änderung übernommen.',
    ton: 'success',
    weiter: false,
  }
}

/**
 * Ist nach dieser Antwort noch eine Stufe offen?
 *
 * 1. `wartet_weiter === true` → ja (Änderungen).
 * 2. `offen` (Liste, R-12d) nicht leer → ja.
 * 3. `new_status`/`status` vorhanden und nicht „Festgelegt“ → ja (Termin bleibt
 *    Vorschlag/Konflikt).
 * 4. Gar keine Statusauskunft (= alter Server, abgelehnter Termin): dann
 *    bleibt es beim Bisherigen — der Aufrufer wertet es als fertig.
 *
 * @param {object|null|undefined} antwort
 * @returns {boolean}
 */
export function wartetWeiter(antwort) {
  if (!antwort || typeof antwort !== 'object') return false
  if (antwort.wartet_weiter === true) return true
  if (Array.isArray(antwort.offen) && antwort.offen.length > 0) return true
  const status = String(antwort.new_status ?? antwort.status ?? '').trim()
  if (!status) return false
  return status !== 'Festgelegt' && status !== 'Abgelehnt'
}

/**
 * Offene Stufen aus einer Server-Antwort (`offen`, R-12d).
 *
 * Nur eine Liste ist eine Auskunft; alles andere zählt als „keine Angabe“
 * (leere Liste) — die Oberfläche erfindet keine Stufe.
 *
 * @param {object|null|undefined} antwort
 * @returns {string[]}
 */
export function offeneStufen(antwort) {
  const roh = antwort?.offen
  if (!Array.isArray(roh)) return []
  return roh.map(s => String(s || '').trim()).filter(Boolean)
}

/**
 * Nächste offene Stufe aus der Antwort — `naechste_stufe` (R-12d).
 *
 * Fehlt das Feld, wird NICHTS gerechnet: die frühere feste Folge war bei der
 * Kette untergruppe → gemeinde falsch. Rückfall ist allein die erste offene
 * Stufe, die der Server in `offen` mitschickt.
 *
 * @param {object|null|undefined} antwort
 * @returns {string|null}
 */
export function naechsteStufe(antwort) {
  const direkt = String(antwort?.naechste_stufe || '').trim()
  if (direkt) return direkt
  const rest = offeneStufen(antwort)
  return rest.length ? rest[0] : null
}

/**
 * Titel der nächsten offenen Stufe (`stufen_titel` des Servers).
 *
 * Ohne Server-Namen bleibt es `null` — der Satz nennt dann keine Stufe.
 * `rueckfall` gilt nur, wenn weder `naechste_stufe` noch `offen` in der
 * Antwort steht (alte Antwort): dann ist die zuletzt geprüfte Stufe die
 * einzige Auskunft, die es gibt — und auch die wird nur benannt, wenn der
 * Server dafür einen Titel kennt.
 *
 * @param {object|null|undefined} antwort
 * @param {string|null|undefined} [rueckfall]
 * @returns {string|null}
 */
export function naechsteStufeName(antwort, rueckfall = null) {
  let schluessel = naechsteStufe(antwort)
  if (!schluessel && !('naechste_stufe' in (antwort || {})) && !Array.isArray(antwort?.offen)) {
    schluessel = String(rueckfall || '').trim() || null
  }
  if (!schluessel) return null
  const name = stufenName(schluessel)
  return name === STUFE_UNBEKANNT ? null : name
}

/**
 * UI-R4c (Punkt 1) — ein Stufentitel als Stufe im Satz.
 *
 * Der Servertitel ist ein NAME („Alle Mitglieder der Gemeinde“), kein Prüfer.
 * In „geht jetzt an {name}“ klang er wie die erteilte Freigabe für alle.
 * Diese Funktion macht daraus „die Freigabe der Stufe „{name}““.
 *
 * @param {string|null|undefined} name Server-Titel (schon übersetzt)
 * @returns {string|null} `null`, wenn kein Name vorliegt (nichts behaupten)
 */
export function alsStufeText(name) {
  const text = String(name || '').trim()
  return text ? `die Freigabe der Stufe „${text}“` : null
}

/**
 * UI-R4c (Punkt 4) — welche Stufen sind in den Ergebnissen (`ergebnisse`) offen?
 *
 * Gesucht wird `ergebnisse[id].naechste_stufe` (R-12d) bzw. die erste Stufe
 * aus `ergebnisse[id].offen`. Liefert die SERVER-SCHLÜSSEL (`'gemeinde'`), nie
 * Titel — die Namen kommen erst über `stufenName`.
 *
 * @param {object|null|undefined} antwort
 * @returns {string[]} eindeutige, sortierte Schlüssel
 */
export function stufenEintraege(antwort) {
  const ergebnisse = antwort?.ergebnisse
  if (!ergebnisse || typeof ergebnisse !== 'object') return []
  const schluessel = new Set()
  for (const eintrag of Object.values(ergebnisse)) {
    const s = naechsteStufe(eintrag)
    if (s) schluessel.add(s)
  }
  return [...schluessel].sort()
}

/**
 * Fehlermeldung eines verweigerten Prüfens (403/417) verständlich machen.
 *
 * Der Server schickt bei falscher Stufe bereits den fertigen Satz
 * („… wartet noch auf die Freigabe durch …“). Der wird NIE ersetzt —
 * Umschreiben würde eine andere Stufe behaupten, als der Server geprüft hat.
 * Nur ein leerer/unbekannter Fehler bekommt einen eigenen Satz; nennt der
 * Server keinen Stufennamen (noch nicht geladen), bleibt der Satz ohne ihn.
 *
 * @param {unknown} fehler
 * @param {string|null|undefined} stufe
 * @returns {string}
 */
export function verweigerungText(fehler, stufe = null) {
  const roh = typeof fehler === 'string' ? fehler : (fehler?.message || fehler?.statusText || '')
  const text = String(roh || '').trim()
  const istVerweigerung = fehler?.status === 403 || fehler?.status === 417
    || /fehlt dir die Berechtigung|keine Berechtigung|nicht prüfen|wartet noch auf die Freigabe/i.test(text)
  if (text && (istVerweigerung || !/^\s*(error|fehler)\s*:?\s*$/i.test(text))) return text
  const name = stufe ? stufenName(stufe) : STUFE_UNBEKANNT
  if (name !== STUFE_UNBEKANNT) {
    return `Diese Stufe prüft die Zuständigen der Stufe „${name}“ — Du kannst hier nicht freigeben.`
  }
  return 'Du kannst diesen Vorschlag nicht prüfen.'
}

/**
 * Meldung für „Alle freigeben“/Ziehen aus `finalize_staged_events` (R-12d).
 *
 * Der Server zählt ehrlich: `festgelegt` stehen im Kalender, `weitergereicht`
 * warten auf eine weitere Stufe (`ergebnisse[id].naechste_stufe`).
 * Gemeldet wird genau das — kein „N Termine freigegeben“, wenn die meisten
 * nur eine Stufe weiter sind.
 *
 * Kennt die Antwort die Felder NICHT (alter Server), fällt es auf
 * `freigabeMeldung` zurück (dort entscheidet `wartet_weiter`/`status`).
 *
 * @param {object|null|undefined} antwort
 * @returns {{text: string, ton: 'success'|'warning', weiter: boolean,
 *            festgelegt: number, weitergereicht: number}}
 */
export function sammelMeldung(antwort) {
  const zaehlbar = antwort && typeof antwort === 'object'
    && (Number.isFinite(Number(antwort.festgelegt)) || Number.isFinite(Number(antwort.weitergereicht)))
  if (!zaehlbar) {
    const m = freigabeMeldung(antwort, { art: 'termin' })
    return { ...m, festgelegt: m.weiter ? 0 : 1, weitergereicht: m.weiter ? 1 : 0 }
  }
  const fest = Math.max(0, Math.trunc(Number(antwort.festgelegt) || 0))
  const weiter = Math.max(0, Math.trunc(Number(antwort.weitergereicht) || 0))
  // UI-R4c (Punkt 4): Eine Stufe wird nur genannt, wenn für ALLE wartenden
  // Termine dieselbe dran ist. Sonst bleiben die übrigen ungenannt.
  const wartetAuf = wartetAufSatz(antwort)

  if (!fest && !weiter) {
    return { text: 'Nichts freigegeben.', ton: 'warning', weiter: false, festgelegt: 0, weitergereicht: 0 }
  }
  if (!weiter) {
    return {
      text: `${zaehlwort(fest, 'Termin', 'Termine')} freigegeben.`,
      ton: 'success', weiter: false, festgelegt: fest, weitergereicht: 0,
    }
  }
  if (!fest) {
    return {
      text: `${zaehlwort(weiter, 'Termin', 'Termine')} ${weiter === 1 ? 'wartet' : 'warten'} auf ${wartetAuf}.`,
      ton: 'warning', weiter: true, festgelegt: 0, weitergereicht: weiter,
    }
  }
  return {
    text: `${fest} freigegeben, ${weiter} ${weiter === 1 ? 'wartet' : 'warten'} auf ${wartetAuf}.`,
    ton: 'warning', weiter: true, festgelegt: fest, weitergereicht: weiter,
  }
}

/**
 * UI-R4c (Punkt 4) — die Stufe der WARTENDEN Termine als Satzteil.
 *
 * Vorher nannte die Meldung die erste gefundene `naechste_stufe` — auch wenn
 * die übrigen Termine auf anderen Stufen lagen. Hier wird nur dann EINE Stufe
 * genannt, wenn die Ergebnisse GENAU EINE offene Stufe melden; sonst bleibt es
 * `null` (der Satz sagt dann „auf weitere Stufen“, siehe `wartetAufSatz`).
 *
 * @param {object|null|undefined} antwort
 * @returns {string|null}
 */
export function sammelStufeText(antwort) {
  const stufen = stufenEintraege(antwort)
  if (stufen.length !== 1) return null
  const name = stufenName(stufen[0])
  return name === STUFE_UNBEKANNT ? null : alsStufeText(name)
}

/**
 * Objekt-Teil der Wartemeldung: die EINE offene Stufe, „die nächste Stufe“
 * oder „weitere Stufen“.
 *
 * UI-R4d (Punkt 4): Vorher stand ohne `ergebnisse` immer „weitere Stufen“ —
 * auch bei EINEM wartenden Termin, für den es keine „weiteren“ gibt. Die
 * Mehrzahl steht jetzt nur, wenn sie stimmt:
 *  · eine benannte Stufe → „die Freigabe der Stufe „…““ (aus `ergebnisse`),
 *  · sonst EIN wartender Termin → „die nächste Stufe“,
 *  · sonst (mehrere) → „weitere Stufen“.
 *
 * @param {object|null|undefined} antwort
 * @returns {string}
 */
export function wartetAufSatz(antwort) {
  const benannt = sammelStufeText(antwort)
  if (benannt) return benannt
  const offen = Math.max(0, Math.trunc(Number(antwort?.weitergereicht) || 0))
  return offen <= 1 ? 'die nächste Stufe' : 'weitere Stufen'
}

/** „1 Termin“ / „2 Termine“ (sprachlich, ohne eigene Begriffsliste). */
function zaehlwort(n, einzahl, mehrzahl) {
  return `${n} ${n === 1 ? einzahl : mehrzahl}`
}

/**
 * Ein Freigabe-Antrag (`api.rechte.get_offene_sichtbarkeits_antraege`) in eine
 * Zeile der Prüfliste übersetzen.
 *
 * Der Server liefert seit R-12 die Anzeige mit — es wird KEIN Schlüssel
 * geraten und kein Ziel abgeleitet:
 *  · `titel`            Titel des Inhalts („Chorproben“)
 *  · `gruppe_name` / `untergruppe_name`  Klartextnamen
 *  · `ziel`             „gruppe“ | „gemeinde“ — das ZIEL des Antrags, auch
 *                       wenn zuerst die Gruppenstufe entscheidet
 *  · `stufe`            die Stufe, die JETZT dran ist (Schlüssel für
 *                       `entscheide_sichtbarkeit`)
 *
 * `typ`/`objekt` bleiben die Schlüssel für den Entscheid. Fehlt `ziel` (alte
 * Antwort), wird es nicht erfunden: dann steht kein Ziel im Satz.
 *
 * `stufeText` liest die Server-Titel über `stufenName` — wer ihn reaktiv
 * braucht (Titel treffen nach dem ersten Zeichnen ein), nimmt
 * `antragZeileReaktiv`. Sonst bliebe „Stufe: —“ stehen (Punkt UI-R4b/6).
 *
 * @param {object|null|undefined} antrag
 * @param {(stufe: string|null|undefined) => string} [namensgeber]
 *        Wie ein Stufen-Schlüssel heißt (Standard: `stufenName`).
 * @returns {{typ: string, objekt: string, titel: string, stufe: string,
 *            stufeText: string, ziel: string|null, zielText: string|null}|null}
 */
export function antragZeile(antrag, namensgeber = stufenName) {
  if (!antrag || typeof antrag !== 'object') return null
  const typ = String(antrag.typ || '').trim()
  const objekt = String(antrag.objekt || '').trim()
  const stufe = String(antrag.stufe || '').trim()
  if (!typ || !objekt || !stufe) return null
  const titel = String(antrag.titel || '').trim() || objekt
  const ziel = String(antrag.ziel || '').trim() || null
  const name = typeof namensgeber === 'function' ? namensgeber : stufenName
  return {
    typ,
    objekt,
    titel,
    stufe,
    stufeText: name(stufe),
    ziel,
    zielText: zielText(antrag, ziel),
  }
}

/**
 * „die ganze Gruppe Kirchenchor“ bzw. „alle Mitglieder der Gemeinde“ aus den
 * Server-Feldern — nie „öffentlich“, nie ein geratener Name.
 *
 * Ziel `gruppe` heißt: der Inhalt einer UNTERGRUPPE soll für die GANZE Gruppe
 * sichtbar werden (das Ziel ist die Gruppe, nicht die Untergruppe). Die
 * Untergruppe ist hier nur die Herkunft des Inhalts und gehört nicht in den
 * Ziel-Satz. Fehlt der Gruppenname, wird kein Name erfunden.
 *
 * @param {object} antrag
 * @param {string|null} ziel
 * @returns {string|null}
 */
function zielText(antrag, ziel) {
  const gruppe = String(antrag?.gruppe_name || '').trim()
  const untergruppe = String(antrag?.untergruppe_name || '').trim()
  if (ziel === 'gruppe') {
    // Nur wenn der Inhalt einer Untergruppe gehört, ist „die ganze Gruppe“
    // die richtige Steigerung; sonst ist die Gruppe selbst das Ziel.
    if (untergruppe && gruppe) return `die ganze Gruppe ${gruppe}`
    if (gruppe) return `die Gruppe ${gruppe}`
    if (untergruppe) return `die Untergruppe ${untergruppe}`
    return null
  }
  if (ziel === 'gemeinde') return 'alle Mitglieder der Gemeinde'
  return null
}

/**
 * Alle Anträge zu Zeilen — ungültige fallen still heraus (kein Klickziel
 * ohne Schlüssel, kein Eintrag ohne Stufe).
 *
 * @param {Array<object>|null|undefined} antraege
 * @param {(stufe: string|null|undefined) => string} [namensgeber]
 * @returns {Array<ReturnType<typeof antragZeile>>}
 */
export function antragZeilen(antraege, namensgeber = stufenName) {
  if (!Array.isArray(antraege)) return []
  return antraege.map(a => antragZeile(a, namensgeber)).filter(Boolean)
}

/** Objektart → Klartext für die Zeile „Kalender „Gottesdienste““. */
const TYP_KLARTEXT = {
  kalender: 'Kalender',
  beitrag: 'Beitrag',
  wiki: 'Wiki-Artikel',
  wiki_artikel: 'Wiki-Artikel',
  plan: 'Plan',
  lied: 'Lied',
  ressource: 'Ressource',
}

/**
 * „Kalender „Chorproben“ für alle Mitglieder der Gemeinde“ — Satz für die
 * Zeile. Fehlt das Ziel in der Antwort, steht der Inhalt ohne Zielangabe
 * (kein erfundenes Ziel).
 *
 * @param {ReturnType<typeof antragZeile>} zeile
 * @returns {string}
 */
export function antragSatz(zeile) {
  if (!zeile) return ''
  const art = TYP_KLARTEXT[zeile.typ] || zeile.typ
  return zeile.zielText
    ? `${art} „${zeile.titel}“ für ${zeile.zielText}`
    : `${art} „${zeile.titel}“`
}
