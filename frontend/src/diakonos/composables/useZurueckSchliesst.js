/**
 * useZurueckSchliesst — die Zurück-Taste (bzw. die Zurück-Geste am Handy)
 * schließt ein offenes Fenster, statt die Seite zu verlassen.
 *
 * Befund OP-HANDY-7: Das Termin-Fenster im Kalender blieb nach „Zurück“ offen
 * und blockierte Taps; der „Mehr“-Knopf der Handy-Navigation ließ die Seite
 * dahinter wechseln; der Foto-Dialog im Profil verließ die Seite ganz. Nur
 * KronosCalendar kannte ein `popstate` — und dort nur für den Tagesansicht-
 * Wechsel.
 *
 * Die Buchführung (welches Fenster ist offen, wer schließt) liegt in
 * `fensterstapel.mjs` und ist dort ohne Browser geprüft. Diese Composable
 * verbindet sie mit `history.pushState`/`popstate`.
 *
 * P2-3b — zwei Nacharbeiten aus dem Code-Review (R-P2-3-code, B1/W1):
 *
 * B1 Navigation vs. Zurück: Ein Fenster schließt auf ZWEI Wegen.
 *   (a) Über die Oberfläche (✕/Esc/Überlappung): seine History-Marke muss
 *       verbraucht werden — sonst bliebe eine Leiche und „Zurück“ bräuchte
 *       zwei Tipps.
 *   (b) Über einen Link IM Fenster (z. B. Eintrag im „Mehr“-Blatt): dabei
 *       navigiert der Browser VORWÄRTS. Ein `history.back()` würde die
 *       Zielseite sofort wieder verlassen — der Nutzer landete wieder auf der
 *       Ausgangsseite. Hier darf NICHT zurückgegangen werden.
 *
 *   Zur Erkennung: Der Vue-Watcher läuft VOR der Standardaktion des Links —
 *   im Browser steht die neue Adresse erst einen Makrotask später fest (im
 *   echten Gerät nachgemessen). Deshalb wird der Eintrag NICHT sofort
 *   verbraucht, sondern einen Makrotask später geprüft: hat sich die Adresse
 *   seit dem Öffnen geändert, war es eine Navigation → Eintrag bleibt stehen;
 *   sonst (✕/Esc/Überlappung) wird er per `history.back()` verbraucht.
 *
 * P3-4c (Restpunkt 11) — NAVIGATION AUS DEM FENSTER: Der Fenster-Eintrag hat
 *   dieselbe Adresse wie die Ausgangsseite. Führte ein Link im Fenster die
 *   Seite vorwärts, blieb er als Leiche stehen — „Zurück" landete dort (ohne
 *   sichtbare Wirkung), erst der zweite Tipp führte weiter. Seit P3-4c fängt
 *   ein Capture-Listener den Klick ab (`beiKlickImFenster`), verbraucht den
 *   Fenster-Eintrag und setzt das Ziel per `location.replace` in den
 *   Ausgangseintrag. Im echten Chromium gemessen (normal und 6-fach
 *   gedrosselt): Zurück 1 → Ausgangsseite, Zurück 2 → Seite davor.
 *   `location.replace` statt `replaceState`, weil Chromium bei
 *   `replaceState` mit Adresse KEIN `hashchange` auslöst — der Router bliebe
 *   auf der alten Seite.
 *
 * W1 Gestapelte Fenster: „Zurück“ schließt NUR das oberste Fenster. Ein
 *   selbst ausgelöstes `history.back()` (Eintrag verbrauchen) darf nicht als
 *   Nutzer-„Zurück“ missverstanden werden und das darunterliegende Fenster
 *   mitnehmen — deshalb zählt `eigeneRuecknahmen` die eigenen Aufrufe.
 *
 * Verwendung (in `<script setup>`):
 *   const offen = ref(false)
 *   useZurueckSchliesst(offen, () => { offen.value = false })
 */
import { watch, onBeforeUnmount } from 'vue'
import { Fensterstapel } from './fensterstapel.mjs'

// EIN Stapel für die ganze Sitzung — so schließt Zurück gestapelte Fenster
// in der richtigen Reihenfolge (oberstes zuerst).
const stapel = new Fensterstapel()
let popstateAngemeldet = false

// Marke -> Schließen-Funktion DIESES Fensters. „Zurück“ ruft daraus nur die
// Funktion des obersten Fensters (W1) statt alle offenen Fenster.
const nachMarke = new Map()

/**
 * P3-4 (Restpunkt 11): Zähler selbst ausgelöster `back()`-Aufrufe.
 *
 * Ein eigenes „Aufräum-Back" (✕/Esc) darf nicht als Nutzer-„Zurück"
 * missverstanden werden und ein zweites Fenster schließen. Das zugehörige
 * `popstate` wird als eigenständige Aufgabe unmittelbar nach dem `back()`
 * zugestellt — ein echtes Zurück des Nutzers kommt davor nicht dazwischen.
 *
 * Sonderfall Verweigerung: Verweigert ein `beforeClose`-Wächter das
 * Schließen, wird das Fenster NICHT geschlossen — dann darf auch kein
 * `back()` laufen und der Zähler bleibt unberührt.
 */
let eigeneRuecknahmen = 0

/**
 * Bei `popstate` „Zurück" das oberste Fenster schließen.
 *
 * P3-4 (Restpunkt 11): Lehnt der Schließer ab (`beforeClose` verweigert, z. B.
 * ungespeicherte Eingaben), bleibt das Fenster offen — sein History-Eintrag
 * wurde vom Nutzer-„Zurück" aber bereits verbraucht. Dann wird die Marke
 * erneut angelegt (`pushState`), damit das Fenster wieder einen eigenen
 * Eintrag besitzt: sonst verließe der NÄCHSTE „Zurück"-Tipp die Seite, obwohl
 * das Fenster noch offen ist.
 */
function beiPopstate() {
  // Eigenes „Aufräum-Back" (✕/Esc) → nur quittieren, nicht eingreifen.
  if (eigeneRuecknahmen > 0) {
    eigeneRuecknahmen -= 1
    // P3-4c: Das eigene `back()` kam von einem abgefangenen Link-Klick. Der
    // Fenster-Eintrag ist jetzt verbraucht; das gemerkte Ziel kommt als neuer
    // Eintrag dahinter (Zurück 1 → Ausgangsseite, Zurück 2 → Seite davor).
    if (warteAufZiel) {
      const ziel = warteAufZiel
      warteAufZiel = null
      try { window.location.hash = ziel } catch { /* Sandbox */ }
    }
    return
  }
  warteAufZiel = null
  const marke = stapel.oberste()
  if (!stapel.zurueckGehen().schliessen) return   // kein Fenster offen → nicht uns
  const schliessen = nachMarke.get(marke)
  nachMarke.delete(marke)
  if (!schliessen) return
  // P3-4 (Restpunkt 11): Der Schließer darf ablehnen (beforeClose verweigert,
  // z. B. ungespeicherte Eingaben). Dann bleibt das Fenster offen — sein
  // History-Eintrag wurde vom Nutzer-„Zurück" aber bereits verbraucht. Er wird
  // erneut angelegt, damit der NÄCHSTE „Zurück"-Tipp nicht die Seite verlässt.
  Promise.resolve(schliessen()).then((geschlossen) => {
    if (geschlossen !== false) return
    stapel.wiederOeffnen(marke)
    nachMarke.set(marke, schliessen)
    try { window.history.pushState({ dkFenster: marke }, '') } catch { /* Sandbox */ }
  }).catch(() => { /* Verweigerung ist kein Fehler */ })
}

/** Die aktuelle Adresse ohne Abfrageteil (im Testlauf evtl. nicht vorhanden). */
function aktuellerHash() {
  return typeof window !== 'undefined' && window.location ? window.location.hash : null
}

/**
 * P3-4c (Restpunkt 11) — Marke eines Fensters entfernen.
 *
 * Der beim Öffnen angelegte Eintrag trägt DIESELBE Adresse wie die
 * Ausgangsseite. Wird das Fenster über ✕/Esc geschlossen, muss sein Eintrag
 * verbraucht werden (siehe `verbraucheWennKeineNavigation`); bei einer
 * Navigation aus dem Fenster heraus sorgt `verbucheNavigation` dafür, dass der
 * Fenster-Eintrag verschwindet, statt als Leiche stehenzubleiben.
 *
 * Hier bleibt nur die Marke `dkFenster` aus dem Zustand — die Adresse NICHT
 * anfassen: die Seite hat ihren Listen-/Filterzustand (z. B. `?q=…`,
 * OP-UI-8) in denselben Eintrag geschrieben, und ein `replaceState` mit
 * Adresse löste in Chromium KEIN `hashchange` aus (der Router hinge fest).
 */
function entschaerfeEigenenEintrag() {
  if (typeof window === 'undefined' || !window.history) return
  const zustand = { ...(window.history.state || {}) }
  if (!('dkFenster' in zustand)) return
  delete zustand.dkFenster
  try {
    window.history.replaceState(Object.keys(zustand).length ? zustand : null, '')
  } catch {
    /* Browser verweigert replaceState (Sandbox/Datei-URL): dann bleibt die
       Marke stehen und „Zurück" braucht einen Tipp mehr — nichts bricht. */
  }
}

// ── P3-4c: Navigation aus einem Fenster heraus ──────────────────────────────
/**
 * Ziel einer Navigation aus einem offenen Fenster (Hash-Router), sonst null.
 *
 * Nur Sprungadressen im selben Dokument: externe Ziele, `target=_blank` und
 * Downloads laufen am Verlauf vorbei und dürfen nicht abgefangen werden.
 */
function hashZielVon(ereignis) {
  const el = ereignis?.target
  if (!el || typeof el.closest !== 'function') return null
  const link = el.closest('a[href]')
  if (!link) return null
  const href = link.getAttribute('href') || ''
  if (href.length < 2 || href[0] !== '#') return null
  if (link.target && link.target !== '_self') return null
  if (link.hasAttribute('download')) return null
  if (ereignis.defaultPrevented || ereignis.button > 0 || ereignis.metaKey ||
      ereignis.ctrlKey || ereignis.shiftKey || ereignis.altKey) return null
  return href
}

/**
 * Ein Klick auf einen Link im offenen Fenster wird ABGEFANGEN, statt den
 * Browser vorwärts navigieren zu lassen:
 *
 * Ohne diesen Eingriff entsteht der tote Eintrag (Befund R-P3-4b, W1). Der
 * Verlauf ist beim Klick
 *     #/vorher · #/start · [#/start = Fenster]
 * Der Link im „Mehr“-Blatt hängt mit dem href einen WEITEREN Eintrag an
 * (`#/ziel`). „Zurück“ landet dann erst auf dem Fenster-Eintrag, der genauso
 * aussieht wie `#/start` — ein Tipp ohne sichtbare Wirkung; erst der zweite
 * führt weiter.
 *
 * Ablauf hier: Der Fenster-Eintrag wird VERBRAUCHT (`history.back()`), und im
 * folgenden `popstate` wird das Ziel als NEUER Eintrag gesetzt
 * (`location.hash = ziel`). Der Verlauf wird damit von
 *     #/vorher · A · [A = Fenster]
 * auf
 *     #/vorher · A
 * verkürzt — A steht nur noch EINMAL da (die Ausgangsseite selbst), und das
 * Ziel hängt sauber dahinter:
 *     #/vorher · A · B
 * Ergebnis: Zurück 1 → A, Zurück 2 → die Seite VOR A.
 *
 * Warum nicht `replaceState(url)` im Watcher: das löst in Chromium KEIN
 * `hashchange` aus (`popstate` allein) — der Router bliebe auf der alten
 * Seite stehen. `location.hash = ziel` feuert `hashchange` wie ein Link.
 * Warum nicht `location.replace(ziel)`: das ERSETZT den Ausgangseintrag,
 * dann fehlt A im Verlauf ganz (Zurück 1 spränge direkt auf die Seite VOR A).
 */
function beiKlickImFenster(ereignis) {
  const ziel = hashZielVon(ereignis)
  if (!ziel) return
  const zustand = window.history?.state
  if (!zustand || !('dkFenster' in zustand)) return
  // Kein Vorwärts-Eintrag, kein Seitenwechsel durch den Browser.
  ereignis.preventDefault()
  // K1 (R-P3-4c): Der Klick wird in der Capture-Phase abgefangen, also laufen
  // die eigenen @click-Handler der Links NICHT mehr. Wer je einen Link mit
  // zusätzlicher Logik in ein Fenster legt, muss sie hier ergänzen.
  ereignis.stopPropagation()
  // Das Fenster über den normalen Schließer schließen. `beiPopstate` quittiert
  // das eigene `back()` über `eigeneRuecknahmen` und schließt nichts doppelt.
  const marke = stapel.oberste()
  const schliessen = marke !== null ? nachMarke.get(marke) : null
  if (schliessen) {
    nachMarke.delete(marke)
    stapel.zurueckGehen()
  }
  // W-1 (R-P3-4c): Das Ergebnis des Schließens ABWARTEN. Verweigert ein
  // `beforeClose`-Wächter („Änderungen verwerfen?“ -> „Weiter bearbeiten“),
  // bleibt alles, wie es ist: Fenster offen, Adresse unverändert, Eintrag
  // unberührt. Vorher lief `back()` unabhängig davon — die Rückfrage wurde
  // vom `popstate` der Zielzuweisung sofort wieder geschlossen.
  const weiter = schliessen
    ? Promise.resolve()
        .then(() => schliessen())
        .then((geschlossen) => geschlossen !== false)
        .catch(() => false)
    : Promise.resolve(true)
  return weiter.then((darfWeiter) => {
    if (!darfWeiter) {
      // Stapel und Marke zurücknehmen (wie `beiPopstate` bei Verweigerung):
      // das Fenster gilt weiter als offen, der nächste „Zurück“ trifft es.
      if (schliessen) {
        stapel.wiederOeffnen(marke)
        nachMarke.set(marke, schliessen)
      }
      return
    }
    entschaerfeEigenenEintrag()
    // Ziel erst NACH dem Zurückspringen setzen (im `popstate`): vorher steht
    // noch der Fenster-Eintrag vorn, ein Hash-Wechsel würde ihn nur ersetzen.
    warteAufZiel = ziel
    eigeneRuecknahmen += 1
    window.history.back()
  })
}

/**
 * P3-4c: Das nach einem abgefangenen Klick gemerkte Ziel (null = keins).
 * Wird im `popstate` des eigenen `back()` in den Verlauf gesetzt.
 */
let warteAufZiel = null

/**
 * Den eigenen History-Eintrag verbrauchen — nur bei Schließen ÜBER DIE
 * OBERFLÄCHE (✕/Esc/Überlappung), wenn keine Navigation stattfand.
 *
 * B1: Erst nach einem Makrotask prüfen, damit eine Navigation über einen Link
 * im Fenster Zeit hat, die Adresse zu setzen. Hat sie (Adresse geändert), wird
 * NICHT zurückgegangen — der Eintrag gehört jetzt dem Ziel (Restpunkt 11:
 * Marke hat der Watcher bereits synchron entfernt).
 */
function verbraucheWennKeineNavigation(hashBeimOeffnen) {
  setTimeout(() => {
    if (aktuellerHash() !== hashBeimOeffnen) return
    eigeneRuecknahmen += 1
    window.history.back()
  }, 0)
}

export function useZurueckSchliesst(offen, schliessen) {
  let eigeneMarke = null
  // Adresse beim Öffnen — weicht sie beim Schließen ab, wurde navigiert (B1).
  let eigenerHash = null

  watch(offen, (ist) => {
    if (ist) {
      eigeneMarke = stapel.oeffnen()
      eigenerHash = aktuellerHash()
      nachMarke.set(eigeneMarke, () => schliessen())
      window.history.pushState({ dkFenster: eigeneMarke }, '')
      if (!popstateAngemeldet) {
        window.addEventListener('popstate', beiPopstate)
        // P3-4c: Klicks auf Links im Fenster abfangen, BEVOR der Browser dem
        // href folgt (Capture-Phase läuft von oben nach unten, also vor dem
        // @click-Handler der Seite). Nur so entsteht kein zweiter Eintrag
        // neben dem Fenster-Eintrag (toter Eintrag, Restpunkt 11).
        if (typeof document !== 'undefined') {
          document.addEventListener('click', beiKlickImFenster, true)
          popstateAngemeldet = true
        }
      }
    } else if (eigeneMarke !== null) {
      const marke = eigeneMarke
      const hashBeimOeffnen = eigenerHash
      eigeneMarke = null
      eigenerHash = null
      nachMarke.delete(marke)
      // Restpunkt 11: Die Marke JETZT aus dem eigenen Eintrag nehmen.
      entschaerfeEigenenEintrag()
      // Über das Fenster geschlossen (✕/Esc/Überlappung): der Eintrag wurde
      // nicht von einer Navigation übernommen und muss verbraucht werden.
      // Ging der Klick auf einen Link (P3-4c), hat `beiKlickImFenster` den
      // Eintrag bereits verbraucht und das Fenster geschlossen — hier ist
      // dann nichts mehr zu tun (`verbrauchen` greift nicht, weil die Marke
      // dort schon abgeräumt wurde).
      if (stapel.schliessen(marke).verbrauchen) {
        verbraucheWennKeineNavigation(hashBeimOeffnen)
      }
    }
  }, { immediate: false })

  onBeforeUnmount(() => {
    if (eigeneMarke !== null) {
      nachMarke.delete(eigeneMarke)
      stapel.schliessen(eigeneMarke)
      eigeneMarke = null
      eigenerHash = null
    }
  })
}

export default useZurueckSchliesst
