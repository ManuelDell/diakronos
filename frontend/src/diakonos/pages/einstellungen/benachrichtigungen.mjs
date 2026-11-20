/**
 * CHAT-10b — Benachrichtigungen aufs Gerät: die Sätze und die Umrechnung.
 *
 * Ohne Vue und ohne Browser, damit die Sätze und die Schlüssel-Umrechnung im
 * Node-Test prüfbar sind (`tests/chat10b-push.test.mjs`). Die Seite
 * (`pages/einstellungen/Benachrichtigungen.vue`) bindet sie nur.
 *
 * WORUM ES GEHT
 * Der Server (`api/push.py`) schickt der Benachrichtigung GENAU
 * `{titel, text, ziel}` — nie den Inhalt einer Nachricht. Die Oberfläche sagt
 * das offen („zeigt nur, in welchem Gespräch etwas Neues ist“) und erklärt in
 * Alltagssprache, was der Schalter tut. „Push“, „Subscription“ oder
 * „VAPID“ stehen in KEINEM sichtbaren Text: das sind Wörter der Technik, nicht
 * der Gemeinde.
 */

/** Die Adresse des Service Workers — mit Betriebs-Präfix (`mitBasis`). */
export const SW_PFAD = '/sw.js'

/** Überschrift des Abschnitts. */
export const PUSH_TITEL = 'Benachrichtigungen aufs Gerät'

/** Einleitung: was der Schalter bewirkt. */
export const PUSH_EINLEITUNG =
  'Du kannst dich auf diesem Gerät benachrichtigen lassen, wenn in einem '
  + 'Gespräch etwas Neues steht — auch wenn Diakronos gerade nicht offen ist.'

/** Der Satz unter dem Schalter — die wichtigste Zusage. */
export const PUSH_INHALTSSATZ =
  'Die Benachrichtigung zeigt nur, in welchem Gespräch etwas Neues ist — nie den Inhalt.'

/** Server kennt keine Schlüssel (Push ist nicht eingerichtet). */
export const PUSH_SERVER_AUS =
  'Auf diesem Server sind Benachrichtigungen aufs Gerät nicht eingerichtet.'

/** Der Browser kann es nicht (kein Service Worker / keine Benachrichtigungen). */
export const PUSH_BROWSER_FEHLT = 'Dieser Browser unterstützt das nicht.'

/**
 * iPhone/iPad: Safari zeigt Benachrichtigungen nur für eine zum Home-Bildschirm
 * hinzugefügte Web-App. EIN sachlicher Satz, kein Werbetext.
 */
export const PUSH_IPHONE_HINWEIS =
  'Auf dem iPhone geht das nur, wenn Diakronos auf dem Home-Bildschirm liegt.'

/** Die Berechtigung wurde abgelehnt — und wie man sie zurückholt. */
export const PUSH_VERWEIGERT =
  'Benachrichtigungen sind für Diakronos im Browser gesperrt. Du kannst das in '
  + 'den Einstellungen des Browsers wieder erlauben (bei Safari unter '
  + '„Einstellungen › Websites › Benachrichtigungen“).'

/** Der Schalter selbst. */
export const PUSH_SCHALTER = 'Auf diesem Gerät benachrichtigen'

/** Fehler beim Anschalten. */
export const PUSH_FEHLER_EIN =
  'Das Gerät konnte nicht angemeldet werden. Bitte später noch einmal versuchen.'

/** Fehler beim Ausschalten. */
export const PUSH_FEHLER_AUS =
  'Das Gerät konnte nicht abgemeldet werden. Bitte später noch einmal versuchen.'

/**
 * Der Server kennt die Anmeldung nicht (Push ist dort inzwischen aus).
 *
 * Wird als Fehler beim ANSCHALTEN gezeigt — deshalb derselbe Satz wie
 * `PUSH_FEHLER_EIN`; eine dritte Formulierung für denselben Fall verwirrt nur.
 */
export { PUSH_FEHLER_EIN as PUSH_SERVER_WEG }

/**
 * Kann dieser Browser Benachrichtigungen aufs Gerät?
 *
 * Verlangt ALLE drei Teile: Service Worker, Benachrichtigungen und die
 * Abonnement-Schnittstelle (`PushManager`). Fehlt eines, sagt die Oberfläche
 * „Dieser Browser unterstützt das nicht.“ statt einen Schalter zu zeigen, der
 * nichts tut.
 *
 * Die Prüfungen hängen an `globalThis.navigator`/`globalThis.Notification`,
 * nicht an `window`: die Umgebung wird übergeben, damit der Test ohne Browser
 * prüfen kann.
 */
export function browserKannPush(umgebung = globalThis) {
  const nav = umgebung && umgebung.navigator
  const meldung = umgebung && umgebung.Notification
  return Boolean(
    nav
    && nav.serviceWorker
    && typeof nav.serviceWorker.register === 'function'
    && meldung
    && typeof meldung.requestPermission === 'function'
    && umgebung.PushManager,
  )
}

/**
 * Ist das ein iPhone/iPad (Safari)?
 *
 * Nur für den Hinweis gedacht — die Fähigkeitsfrage entscheidet
 * `browserKannPush`, nicht diese Erkennung. Ohne Browserangabe `false`
 * (dann bleibt der Hinweis weg; nichts wird behauptet).
 *
 * BEWUSST NUR die Kennung der Browser-Angabe: eine Touch-Fähigkeit ist KEIN
 * Kriterium im Haus (FIX-6, wächtergeprüft) — und ohne sie wäre ein iPad im
 * Desktop-Modus („Macintosh“) nicht zu erkennen. Er wird deshalb NICHT als
 * iPad behandelt: der Satz bleibt dann aus, statt auf einem Mac zu erscheinen.
 */
export function istIphone(umgebung = globalThis) {
  const nav = umgebung && umgebung.navigator
  const kennung = String((nav && nav.userAgent) || '')
  if (!kennung) return false
  return /iPhone|iPad|iPod/.test(kennung)
}

/**
 * Der öffentliche Schlüssel des Servers als `Uint8Array`
 * (`applicationServerKey` der Abo-Schnittstelle).
 *
 * Der Schlüssel ist Base64url (RFC 4648 §5: `-` und `_` statt `+` und `/`,
 * Auffüllung mit `=` optional). `atob` kennt nur die Standardform — deshalb
 * wird zuerst übersetzt und aufgefüllt. Ungültiger Inhalt ergibt `null`: die
 * Oberfläche meldet dann den Fehler, statt ein Abonnement mit falschem
 * Schlüssel zu versuchen (der Versand schlüge später fehl, ohne dass jemand
 * wüsste warum).
 */
export function schluesselBytes(base64url, atobFn = null) {
  const text = String(base64url || '').trim()
  if (!text) return null
  // Base64url-Zeichen plus höchstens zwei Füllzeichen am Ende.
  if (!/^[A-Za-z0-9_\-+/]+={0,2}$/.test(text)) return null
  const standard = text.replace(/-/g, '+').replace(/_/g, '/')
  const fehlend = (4 - (standard.length % 4)) % 4
  const aufgefuellt = standard + '='.repeat(fehlend)
  const dekodiere = atobFn || (typeof globalThis.atob === 'function'
    ? globalThis.atob.bind(globalThis)
    : null)
  if (!dekodiere) return null
  let roh
  try {
    roh = dekodiere(aufgefuellt)
  } catch {
    return null
  }
  // `globalThis.Uint8Array` statt `Uint8Array`: derselbe Typ, aber der Node-
  // Test sieht die Abhängigkeit und kann sie bedienen (FIX-8-Regel des Hauses).
  const bytes = new globalThis.Uint8Array(roh.length)
  for (let i = 0; i < roh.length; i += 1) bytes[i] = roh.charCodeAt(i)
  // VAPID-Schlüssel sind unkomprimierte Punkte auf P-256: genau 65 Bytes,
  // beginnend mit 0x04. Alles andere wird gar nicht erst versucht.
  return bytes.length === 65 && bytes[0] === 4 ? bytes : null
}

/**
 * Welcher Zustand gehört auf die Seite? — EINE Entscheidung, in Reihenfolge:
 *
 *   1. `server_aus`  — der Server kennt keine Schlüssel (`aktiv: false`);
 *   2. `browser_aus` — dieser Browser kann es nicht;
 *   3. `verweigert`  — der Browser hat es für diese Seite gesperrt;
 *   4. `an`/`aus`    — Schalter, je nach bestehendem Abonnement.
 *
 * `an` heißt: es GIBT ein Abonnement UND der Server kennt es (`serverAn`).
 * Ohne die Servermeldung bleibt der Schalter aus — das Gerät bekäme sonst
 * Meldungen, die niemand schickt.
 */
export function zustand({ serverAktiv = false, browserKann = true, berechtigung = '', abonniert = false, serverAn = false } = {}) {
  if (!serverAktiv) return 'server_aus'
  if (!browserKann) return 'browser_aus'
  if (berechtigung === 'denied') return 'verweigert'
  return abonniert && serverAn ? 'an' : 'aus'
}

/** Darf der Schalter bedient werden? (nur im Zustand `aus`/`an`) */
export function schalterSichtbar(zustand_) {
  return zustand_ === 'aus' || zustand_ === 'an'
}
