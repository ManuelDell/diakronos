/**
 * CHAT-3a — der Ungelesen-Zähler am Platz „Nachrichten“ (Handy-Leiste).
 *
 * Die Zahl ist die SUMME aus `chat.meine_gespraeche` (`ungelesen` je Gespräch),
 * dieselbe Abfrage, die die Seite „Nachrichten“ für ihre Liste macht.
 *
 * Review R1 (MUSS 4) — WARUM DIESER TAKT SO RUHIG IST:
 *   * Je Takt gibt es GENAU EINE Abfrage dieses Endpunkts. Solange die Seite
 *     „Nachrichten“ offen ist, fragt SIE und schickt die fertige Summe im
 *     Ereignis `dk-chat-ungelesen` (`detail.ungelesen`); dieser Takt ist dann
 *     PAUSIERT (`seiteOffen` UND die Eigenmeldung der Seite über
 *     `dk-chat-seite` → `seiteMeldet`) — sonst liefen zwei Abfragen
 *     gegeneinander. Die Eigenmeldung schließt das Fenster zwischen Aufbau der
 *     Seite und dem Wechsel des Seitennamens im Router.
 *   * Am Desktop gibt es die Leiste gar nicht. Dort fragt die App-Wurzel
 *     deshalb NICHT (`handyLage`): nur die Handy-Lage zeigt den Zähler.
 *   * In der Handy-Lage, während eine andere Seite offen ist, fragt sie alle
 *     `TAKT_LANG_MS` (60 s) — die Zahl ist Beiwerk, kein Fachvorgang, und der
 *     Chat selbst fragt im 10-Sekunden-Takt.
 *
 * Regeln, die hier und NICHT in der Komponente stehen:
 *   * nur bei sichtbarem Tab abfragen (`darfAbfragen`),
 *   * kein zweiter Abruf, solange einer läuft,
 *   * ohne Chat-Modul gar nicht fragen (fail closed: sonst 403 im Protokoll),
 *   * Fehler still schlucken — ein Zähler ist Beiwerk, kein Fachvorgang,
 *   * beim Verlassen den Takt anhalten (EIN Timer, EIN Beobachter, kein
 *     Neustart danach — Review R1, Timer-Leck).
 */
import { onUnmounted, ref } from 'vue'
import { apiGet } from './useApi.js'
import { modulChatErlaubt } from '../modulRechte.mjs'
import { darfAbfragen, ungelesenSumme } from './nachrichtenLogik.mjs'

/** Takt des App-Zählers, solange eine andere Seite offen ist: eine Minute. */
export const TAKT_LANG_MS = 60_000

/**
 * @param {{aktiv?: () => boolean, seiteOffen?: () => boolean,
 *          handyLage?: () => boolean,
 *          abfragen?: () => Promise<any>}} [optionen]
 *   `aktiv`      sagt, ob überhaupt gefragt werden soll (Betrieb: Chat-Modul),
 *   `seiteOffen` ist wahr, solange die Seite „Nachrichten“ den Zähler selbst
 *                führt (dann pausiert dieser Takt),
 *   `handyLage`  ist wahr, wenn die Leiste sichtbar ist (Desktop: kein Takt),
 *   `abfragen`   ist der Abruf — im Test eine Attrappe.
 */
export function useChatZaehler({
  aktiv = () => modulChatErlaubt(),
  seiteOffen = () => false,
  handyLage = () => true,
  abfragen = () => apiGet('chat.meine_gespraeche'),
} = {}) {
  const ungelesen = ref(null)
  /**
   * Führt gerade eine ANDERE Stelle den Zähler (die Seite „Nachrichten“)?
   *
   * MUSS 4: `seiteOffen()` allein genügt nicht — der Seitenname wechselt erst
   * mit dem Router, während die Seite schon aufgebaut wird; in diesem Fenster
   * liefe die Abfrage doppelt. Die Seite meldet sich deshalb selbst über
   * `dk-chat-seite` (Betrieb: `App.vue` reicht das hierher durch). Beide
   * Bedingungen zusammen sind EINE Aussage: „jemand anders fragt“.
   */
  let fremd = false
  const fremdBedingt = () => fremd || seiteOffen() === true

  /** Darf dieser Takt JETZT fragen? */
  function darfFragen() {
    if (!aktiv()) return false
    if (fremdBedingt()) return false // die Seite fragt (EIN Abruf je Takt)
    if (!handyLage()) return false // ohne Leiste gibt es nichts anzuzeigen
    return true
  }

  async function holen() {
    if (!aktiv()) {
      ungelesen.value = null
      return
    }
    const antwort = await abfragen()
    const liste = Array.isArray(antwort?.gespraeche) ? antwort.gespraeche : []
    ungelesen.value = ungelesenSumme(liste)
  }

  /**
   * Der Takt der App-Wurzel: `setTimeout`-Kette — nach jedem Lauf wird neu
   * geplant, und `gestoppt` verhindert einen Neustart nach dem Abbau (kein
   * Timer-Leck; derselbe Befund wie in der Seite, Review R1).
   */
  let timer = null
  let abmelden = null
  let laeuft = false
  let letzterAbruf = 0
  let gestoppt = false

  function sichtbar() {
    return typeof document === 'undefined' || document.hidden !== true
  }

  function planen(ms = TAKT_LANG_MS) {
    if (gestoppt || timer) return
    if (!sichtbar()) return // verborgen: der Beobachter weckt uns
    if (!darfFragen()) return // pausiert (Seite offen / keine Leiste)
    timer = setTimeout(lauf, ms)
  }

  async function lauf() {
    timer = null
    if (gestoppt) return
    if (!darfFragen() || !darfAbfragen({ sichtbar: sichtbar(), laeuft, letzterAbruf, jetzt: Date.now(), takt: TAKT_LANG_MS })) {
      if (darfFragen()) planen()
      return
    }
    laeuft = true
    letzterAbruf = Date.now()
    try {
      await holen()
    } catch {
      // still — der Zähler ist Beiwerk
    } finally {
      laeuft = false
      if (!gestoppt) planen()
    }
  }

  /**
   * Die fertige Zahl von der Seite übernehmen (ihr Ereignis trägt sie) — KEIN
   * zweiter Abruf von `meine_gespraeche`.
   *
   * CHAT-3a-3 (Klein): `null` heißt „die Seite hat noch KEINE Zahl“ (sie meldet
   * das beim Aufbau, `mitteilungSenden(null)`), nicht „null ungelesen“. Vorher
   * machte `Number(null)` daraus 0 — beim Öffnen der Seite sprang der Zähler
   * der Leiste kurz auf 0 und zählte dann sichtbar hoch. Alles, was keine Zahl
   * ist (auch `null`, `undefined`, `''`), lässt den Stand unverändert.
   */
  function uebernehmen(zahl) {
    if (zahl === null || zahl === undefined || zahl === '') return
    const wert = Number(zahl)
    if (Number.isFinite(wert) && wert >= 0) ungelesen.value = Math.trunc(wert)
  }

  /**
   * Die Seite „Nachrichten“ führt den Zähler jetzt (oder nicht mehr) — sie
   * meldet es über `dk-chat-seite`. Übernimmt sie, wird der eigene Termin
   * abgeräumt (sie fragt ohnehin im 10-Sekunden-Takt); gibt sie ihn zurück,
   * startet der lange Takt mit EINEM Abruf, damit die Zahl nicht bis zu einer
   * Minute veraltet stehen bleibt.
   */
  function seiteMeldet(offen) {
    const war = fremd
    fremd = offen === true
    if (gestoppt || war === fremd) return
    if (fremd) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      return
    }
    if (darfFragen() && sichtbar()) {
      timer = setTimeout(lauf, 0)
    }
  }

  function beimSichtbarmachen() {
    if (gestoppt) return
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (!sichtbar()) return
    // Zurück auf der Seite: EIN Abruf, wenn dieser Takt zuständig ist.
    if (darfFragen()) timer = setTimeout(lauf, 0)
  }

  function anhalten() {
    gestoppt = true
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (typeof abmelden === 'function') {
      try { abmelden() } catch { /* egal */ }
    }
    abmelden = null
  }

  // EIN Abruf sofort, damit der Zähler beim Aufbau steht. Ausserhalb der
  // Handy-Lage und bei offener Seite entfällt er (nichts anzuzeigen).
  if (darfFragen() && sichtbar()) holen().catch(() => {})
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', beimSichtbarmachen)
    abmelden = () => document.removeEventListener('visibilitychange', beimSichtbarmachen)
  }
  planen()
  onUnmounted(anhalten)

  return { ungelesen, holen, uebernehmen, seiteMeldet, anhalten, darfFragen, planen }
}
