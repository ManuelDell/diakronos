/**
 * CHAT-10b — Service Worker für Benachrichtigungen aufs Gerät.
 *
 * WARUM ES IHN GIBT
 * Ein Browser zeigt eine Benachrichtigung nur, wenn ein Service Worker sie
 * anzeigt. Diese Datei tut GENAU das — und sonst nichts:
 *
 *   * `push`            Nutzlast lesen und eine Meldung zeigen.
 *   * `notificationclick` das Gespräch öffnen.
 *
 * KEIN `fetch`-Zweig, KEIN Zwischenspeicher (Vorgabe der Karte): dieser Worker
 * fasst keine Anfrage der Seite an. Ohne `fetch`-Zuhörer bleibt jede Anfrage
 * beim Netz — ein Offline-Cache wäre eine zweite Wahrheit über den Datenstand
 * und ist hier ausdrücklich nicht gewollt.
 *
 * ABLAGE UND GELTUNGSBEREICH
 * Die Datei liegt unter `frontend/public/` und wird vom Build unverändert nach
 * `dist/sw.js` kopiert. Der Server liefert sie an der WURZEL aus (`/sw.js`,
 * `spa.py::_sw_datei`), nicht unter `/diakonos/` — nur so reicht der
 * Geltungsbereich (`/`) für die ganze App, auch unter einem Betriebs-Präfix.
 * Aus demselben Grund schickt der Server `Service-Worker-Allowed: /` mit.
 *
 * WAS IN DER NUTZLAST STEHT — UND WAS NIE
 * Der Server schickt `{titel, text, ziel}` (`api/push.py`). Es gibt keinen
 * Nachrichteninhalt und keinen Absendernamen; `text` ist der Satz der Glocke
 * („es gibt etwas Neues in …“). Diese Datei zeigt AUSSCHLIESSLICH diese drei
 * Felder und erfindet nichts dazu: was nicht in der Nutzlast steht, steht auch
 * nicht in der Meldung.
 *
 * `ziel` ist eine SPA-Hash-Route (`#/nachrichten/<gespräch>`). Sie wird beim
 * Klick NICHT blind geöffnet, sondern gegen das feste Muster geprüft — eine
 * fremde Adresse (etwa `https://…` oder `javascript:…`) kann so nie zum Ziel
 * werden.
 */

/* eslint-env serviceworker */

'use strict'

//: Das Ziel, wenn die Nutzlast keines (oder ein ungültiges) nennt.
const NACHRICHTEN_ZIEL = '#/nachrichten'

//: Muster einer erlaubten Adresse: AUSSCHLIESSLICH eine Hash-Route der SPA
//: unter `#/nachrichten`. Bewusst eng (`#/nachrichten` oder
//: `#/nachrichten/<ein Name ohne Punkt-Pfad>`): der Hash bleibt auf der Seite,
//: ein Schema oder eine Herkunft kann darin nicht stecken, und `..`-Segmente
//: (Pfad-Ausbruch) sind ausgeschlossen.
const ZIEL_MUSTER = /^#\/nachrichten(?:\/[^\s\\"'<>]*)?$/
//: Ein `..`-Segment ist ein Pfad-Ausbruch — auch in einem Hash nie ein Ziel.
const PUNKT_PFAD = /(?:^|\/)\.\.?(?:\/|$)/

//: Die Meldung, wenn die Nutzlast unbrauchbar ist.
const NEUTRALER_TITEL = 'Neue Nachricht'
const NEUTRALER_TEXT = 'Es gibt etwas Neues.'

/**
 * Ein Feld der Nutzlast als reinen Text.
 *
 * Nur Zeichenketten und (kleine) Zahlen werden gezeigt — ein Objekt oder ein
 * Feld, das erst beim Anzeigen ausgewertet würde, ergibt leeren Text. Länge
 * begrenzt, damit eine fehlerhafte Nutzlast keine riesige Meldung erzeugt.
 */
function text(wert) {
  if (typeof wert === 'string') return wert.trim().slice(0, 500)
  if (typeof wert === 'number' && Number.isFinite(wert)) return String(wert)
  return ''
}

/**
 * Das Ziel eines Klicks — nur `#/nachrichten…`, sonst die Gesprächsliste.
 *
 * Diese Prüfung ist die EINZIGE Stelle, an der eine Adresse aus der Nutzlast
 * zu einer Navigation wird. Sie läuft schon beim Anzeigen (die Meldung trägt
 * das geprüfte Ziel in `data.ziel`) und noch einmal beim Klick — ein alter,
 * zwischengespeicherter Eintrag kann damit ebenfalls kein fremdes Ziel öffnen.
 */
function pruefeZiel(wert) {
  const ziel = typeof wert === 'string' ? wert.trim() : ''
  if (!ZIEL_MUSTER.test(ziel) || PUNKT_PFAD.test(ziel)) return NACHRICHTEN_ZIEL
  return ziel
}

/**
 * Wie `pruefeZiel`, aber für die ANZEIGE: ein fehlendes/ungültiges Ziel ergibt
 * `''` („kein Ziel“) statt der Gesprächsliste — die Meldung soll dann nur
 * sagen, dass etwas Neues da ist, und beim Klick auf die Liste führen.
 */
function anzeigeZiel(wert) {
  const ziel = typeof wert === 'string' ? wert.trim() : ''
  if (!ziel) return ''
  if (!ZIEL_MUSTER.test(ziel) || PUNKT_PFAD.test(ziel)) return ''
  return ziel
}

/**
 * Die Nutzlast lesen: JSON, sonst `null`. Wirft nie.
 *
 * `PushMessageData.json()` ist SYNCHRON und wirft bei kaputtem Inhalt sofort —
 * deshalb steht hier ein `try` und KEIN `.then`. Ein `await` auf das Ergebnis
 * (siehe `push`-Zuhörer) wäre falsch: das Ergebnis ist das JSON selbst, kein
 * Versprechen.
 */
function liesNutzlast(ereignis) {
  try {
    return ereignis.data ? ereignis.data.json() : null
  } catch (fehler) {
    return null
  }
}

/** Anzeige-Daten aus der Nutzlast — immer brauchbar, notfalls neutral. */
function anzeigeAus(nutzlast) {
  if (!nutzlast || typeof nutzlast !== 'object') {
    return { titel: NEUTRALER_TITEL, text: NEUTRALER_TEXT, ziel: '' }
  }
  const titel = text(nutzlast.titel) || NEUTRALER_TITEL
  const koerper = text(nutzlast.text) || NEUTRALER_TEXT
  // Für die Anzeige gilt: ein ungültiges Ziel wird zu „kein Ziel“ — die
  // Meldung behauptet dann keinen Ort, und der Klick landet auf der Liste.
  return { titel, text: koerper, ziel: anzeigeZiel(nutzlast.ziel) }
}

/**
 * `push`: Meldung zeigen.
 *
 * `waitUntil` wird SOFORT und mit einem Versprechen gerufen — der Browser
 * verlängert damit das Leben des Workers, bis die Meldung steht. Die Nutzlast
 * wird synchron gelesen (`PushMessageData.json()` ist synchron); erst danach
 * beginnt die Kette, und ein Fehler in irgendeinem Schritt führt zur neutralen
 * Meldung. Der Worker endet also nie ohne Anzeige.
 *
 * Der `tag` ist das Ziel: mehrere Meldungen desselben Gesprächs ersetzen
 * einander, statt den Sperrbildschirm zu füllen. `renotify` bleibt aus —
 * eine ersetzte Meldung soll nicht erneut klingeln.
 */
self.addEventListener('push', function (ereignis) {
  ereignis.waitUntil(
    Promise.resolve()
      .then(function () {
        return anzeigeAus(liesNutzlast(ereignis))
      })
      .then(function (anzeige) {
        return self.registration.showNotification(anzeige.titel, {
          body: anzeige.text,
          data: { ziel: anzeige.ziel },
          tag: anzeige.ziel || 'diakronos',
        })
      })
      .catch(function () {
        return self.registration.showNotification(NEUTRALER_TITEL, {
          body: NEUTRALER_TEXT,
          data: { ziel: '' },
          tag: 'diakronos',
        })
      }),
  )
})

/**
 * `notificationclick`: das Gespräch öffnen — und NIE eine fremde Herkunft.
 *
 * Reihenfolge:
 *   1. Die Adresse der App-Seite bestimmen (`seitenAdresse`, aus dem Scope).
 *   2. Ein bereits offenes Fenster DIESER Seite nehmen (seine Adresse MUSS mit
 *      dieser Adresse beginnen, die Herkunft zusätzlich stimmen), in den
 *      Vordergrund holen und dorthin navigieren — kein zweites Fenster, kein
 *      Verlust des bisherigen Zustands.
 *   3. Sonst ein neues Fenster auf `adresse + ziel` öffnen.
 *
 * Das Ziel wird vorher gegen `ZIEL_MUSTER` geprüft und ausschließlich an die
 * EIGENE Adresse gehängt (Hash-Route) — eine fremde Herkunft kann so nie
 * geöffnet werden.
 */
self.addEventListener('notificationclick', function (ereignis) {
  ereignis.notification.close()
  const daten = ereignis.notification && ereignis.notification.data
  const ziel = pruefeZiel(daten && daten.ziel)

  ereignis.waitUntil(
    seitenAdresse().then(function (adresse) {
      return self.clients
        .matchAll({ type: 'window', includeUncontrolled: true })
        .then(function (fenster) {
          const eigene = (fenster || []).filter(function (f) {
            return istEigenesFenster(f, adresse)
          })
          if (!eigene.length) return self.clients.openWindow(adresse + ziel)
          const offen = eigene[0]
          return Promise.resolve(offen.focus())
            .then(function () {
              if (typeof offen.navigate !== 'function') return offen
              return offen.navigate(adresse + ziel)
            })
            .catch(function () {
              return self.clients.openWindow(adresse + ziel)
            })
        })
    }),
  )
})

/**
 * `activate`: die Seite sofort übernehmen.
 *
 * Beim ERSTEN Registrieren ist der Worker nach `register()` noch nicht
 * „aktiv“; ohne `claim()` bedient er die schon offene Seite erst nach dem
 * nächsten Laden. Für eine Anmeldung, die im selben Klick abgeschlossen wird
 * (`pushManager.subscribe`), ist das zu spät — deshalb übernimmt er hier
 * ausdrücklich alle offenen Fenster seines Geltungsbereichs.
 */
self.addEventListener('activate', function (ereignis) {
  ereignis.waitUntil(
    Promise.resolve(self.clients && self.clients.claim ? self.clients.claim() : undefined)
      .catch(function () { /* Übernehmen ist eine Verbesserung, kein Muss */ }),
  )
})

/**
 * Ist das ein Fenster DIESER App? — Adresse UND Herkunft müssen passen.
 *
 * `adresse` ist die Seitenadresse (ohne abschließenden Schrägstrich), z. B.
 * `https://gemeinde.example.org/diakonos`. Eine andere Seite derselben Herkunft
 * (Website, Verwaltung) wird NICHT genommen — sie würde sonst zur App
 * umgeleitet. Die Herkunft wird zusätzlich aus der Fensteradresse gelesen,
 * damit ein gleich aussehender Pfad auf einem anderen Rechner nie zählt.
 */
function istEigenesFenster(fenster, adresse) {
  if (!fenster || typeof fenster.url !== 'string') return false
  const url = fenster.url
  if (url.indexOf(adresse) !== 0) return false
  const rest = url.charAt(adresse.length)
  // Genau die Seite oder ein Unterpfad — nicht `…/diakonos-alt`.
  if (rest !== '' && rest !== '/' && rest !== '#' && rest !== '?') return false
  try {
    return new URL(url).origin === herkunft()
  } catch (fehler) {
    return false
  }
}

/**
 * Die Herkunft dieses Workers (`https://gemeinde.example.org`) — ohne
 * abschließenden Schrägstrich, damit sich Adressen sauber zusammensetzen.
 * Fremde Herkünfte entstehen hier nie: jede Navigation hängt an
 * `seitenAdresse()` (aus dem Scope, mit dieser Herkunft geprüft), und ein Ziel
 * wird vorher gegen `ZIEL_MUSTER` geprüft und ausschließlich als Hash
 * angehängt.
 */
function herkunft() {
  return String(self.location.origin || '').replace(/\/+$/, '')
}

/**
 * Die Adresse der SPA-Seite (ohne Hash) — Grundlage jeder Navigation.
 *
 * Ein Service Worker läuft unter `/sw.js`, kennt aber das Verzeichnis der
 * Seite, die ihn registriert hat, über `clients.matchAll` NICHT zuverlässig
 * (kein Fenster offen). Deshalb wird sie aus dem GELTUNGSBEREICH abgeleitet:
 * der Scope ist die App-Wurzel (`/diakonos` bzw. `/{praefix}/diakonos`),
 * gesetzt beim Registrieren (`Benachrichtigungen.vue`: `{ scope: … }`).
 * `registration.scope` ist genau diese Adresse MIT abschließendem
 * Schrägstrich — ein `location.href` derselben Seite.
 *
 * Fällt der Scope auf die Herkunft zurück (kein eigener Scope), bleibt die
 * Herkunft — dann gilt das alte Verhalten (Wurzel + Hash).
 */
function seitenAdresse() {
  const scope = String((self.registration && self.registration.scope) || '').replace(/\/+$/, '')
  const basis = scope && scope.indexOf(herkunft()) === 0 ? scope : herkunft()
  return Promise.resolve(basis)
}
