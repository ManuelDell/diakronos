<template>
  <!--
    R6: Öffentliche Gastseite `#/gast/<token>` — ohne Anmeldung, ohne
    App-Navigation. Zeigt NUR, was der Server mit `gast_inhalt` herausgibt:
    Titel, Datum und bereits bereinigtes HTML.

    Der Token wird NIE geloggt, nie an Dritte geschickt und steht nur in der
    Adresse dieser Seite (der Server liefert sie mit `no-referrer` aus).
  -->
  <div class="dk-pub-page">
    <div class="dk-pub-card" :class="{ 'r6-gastinhalt-breit': !!inhalt }">

      <!-- Kein Token in der Adresse: die Seite ist kein Link, sondern eine
           Adresse ohne Ziel. Keine Rückfrage — derselbe Hinweis wie bei einem
           ungültigen Link, damit nichts über den Unterschied verrät. -->
      <div v-if="!token" class="dk-pub-center">
        <div class="dk-pub-icon-large" aria-hidden="true">🔒</div>
        <h1 class="dk-pub-title">Zugang nicht möglich</h1>
        <p class="dk-pub-muted">{{ GAST_FEHLER_ABGELAUFEN }}</p>
      </div>

      <!-- Passwort abfragen, solange kein Inhalt da ist. -->
      <template v-else-if="!inhalt">
        <h1 class="dk-pub-title">Geschützter Inhalt</h1>
        <p class="dk-pub-muted r6-gastinhalt-unterzeile">
          Dieser Inhalt ist für Gäste freigegeben. Gib das Passwort ein, das du
          dazu bekommen hast.
        </p>

        <p v-if="meldung" class="r6-gastinhalt-fehler" role="alert">{{ meldung }}</p>

        <!-- OP-UI-23: Enter im Feld schickt ab (wie der Knopf).
             Befund (Review 12.11., Punkt 3): ohne `v-slot="feld"` stand
             `<label for>` ohne Ziel im DOM und das Passwortfeld hatte keinen
             zugänglichen Namen. `name` hilft Passwort-Managern zusätzlich;
             `autocomplete="off"` bleibt (Karte). -->
        <form class="dk-pub-form" @submit.prevent="absenden" novalidate>
          <DkField v-slot="feld" label="Passwort" :error="feldFehler">
            <input
              :id="feld.id"
              ref="passwortFeld"
              v-model="passwort"
              class="dk-ui-eingabe"
              type="password"
              name="gast-passwort"
              autocomplete="off"
              :maxlength="200"
              :aria-describedby="feld['aria-describedby']"
              :aria-invalid="feld['aria-invalid']"
              @input="feldFehler = ''"
            />
          </DkField>
          <DkButton type="submit" variant="primary" block :loading="laedt" :disabled="laedt">
            Anzeigen
          </DkButton>
        </form>
      </template>

      <!-- Inhalt -->
      <template v-else>
        <article class="r6-gastinhalt">
          <header class="r6-gastinhalt-kopf">
            <p class="r6-gastinhalt-art">{{ inhalt.typ === 'wiki' ? 'Wiki-Artikel' : 'Beitrag' }}</p>
            <h1 class="r6-gastinhalt-titel">{{ inhalt.titel }}</h1>
            <p v-if="datumText" class="r6-gastinhalt-datum">{{ datumText }}</p>
          </header>
          <!-- Bereits serverseitig bereinigt (`website.oeffentlich_inhalt.html_erlaubt`);
               DOMPurify als zweite Schicht — Pflicht von SEC-9: `v-html` nur an
               einen `sanitize(…)`-Aufruf, der im selben Bauteil als
               `DOMPurify.sanitize` belegt ist. -->
          <div class="r6-gastinhalt-text" v-html="sanitize(inhalt.inhalt)" />
        </article>
      </template>

    </div>
  </div>
</template>

<script setup>
/**
 * R6 — öffentliche Gastseite. Einstieg `src/gastinhalt/main.js`; der Server
 * liefert ihn für `/diakonos/gastinhalt` aus (ohne Anmeldung), die Kennung
 * steht im Hash: `#/gast/<token>`.
 *
 * Fehlertexte sind fest (Karte): ungültig/abgelaufen, falsches Passwort,
 * zu viele Versuche. Welcher gilt, entscheidet der HTTP-Status — der Server
 * antwortet 404 bzw. 403 (`api.rechte.gast_inhalt`).
 */
import { computed, onMounted, ref } from 'vue'
import DOMPurify from 'dompurify'
import DkButton from '../diakonos/components/ui/DkButton.vue'
import DkField from '../diakonos/components/ui/DkField.vue'
import { apiUrl } from '../shared/basis.js'
// R6 (Review 12.11., Punkt 6): EINE Quelle für Server-Zeitstempel und
// Kalendertage — kein zweiter Leseweg in dieser Seite.
import { GEMEINDE_ZONE, serverDatumText, serverZeitText } from '../shared/zeit.mjs'
import {
  GAST_FEHLER_ABGELAUFEN,
  gastFehlertext,
  gastNutzlast,
} from '../diakonos/composables/r6Gastzugang.mjs'

/** Token aus dem Hash `#/gast/<token>`; leer, wenn keiner dasteht. */
function tokenAusAdresse() {
  const hash = String(window.location.hash || '')
  const treffer = hash.match(/^#\/gast\/([^/?#]+)/)
  if (!treffer) return ''
  try {
    return decodeURIComponent(treffer[1])
  } catch {
    return ''
  }
}

const token = tokenAusAdresse()
const passwort = ref('')
const laedt = ref(false)
const meldung = ref('')
const feldFehler = ref('')
const inhalt = ref(null)
const passwortFeld = ref(null)

/** Zweite Bereinigungsschicht für den Gastinhalt (SEC-9). */
function sanitize(html) { return DOMPurify.sanitize(html || '') }

const datumText = computed(() => {
  const d = inhalt.value?.datum
  if (!d) return ''
  // `datum` ist ein Tag (`JJJJ-MM-TT`) oder ein Zeitstempel. Ein reiner Tag
  // darf durch keine Zeitzonenrechnung rutschen (`serverDatumText`); ein
  // Zeitstempel wird als Serverzeit (UTC) in der Zone der Gemeinde gezeigt.
  return /^\d{4}-\d{2}-\d{2}$/.test(String(d).trim()) ? serverDatumText(d) : serverZeitText(d)
})

onMounted(() => {
  if (token) passwortFeld.value?.focus()
})

async function absenden({ wiederholt = false } = {}) {
  if (laedt.value) return
  meldung.value = ''
  feldFehler.value = ''
  if (!passwort.value) {
    feldFehler.value = 'Bitte gib das Passwort ein.'
    return
  }
  laedt.value = true
  try {
    const antwort = await fetch(apiUrl('rechte.gast_inhalt'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrfToken(),
      },
      body: JSON.stringify({ token, passwort: passwort.value }),
    })
    let daten = null
    try {
      daten = await antwort.json()
    } catch {
      daten = null
    }
    if (!antwort.ok || daten?.exc) {
      // 417 = CSRF-Token fehlt/ungültig. Der Token liegt in der Sitzung; also
      // holen und GENAU EINMAL wiederholen (der Server prüft ihn vor der
      // Ausführung — die Wiederholung ist unbedenklich).
      if (antwort.status === 417 && !wiederholt) {
        wiederholt = true
        laedt.value = false
        await holeCsrfToken()
        return absenden({ wiederholt: true })
      }
      meldung.value = gastFehlertext(antwort.status, servertext(daten))
      // Falsches Passwort: Feld leeren und fokussieren — niemand tippt ein
      // Passwort zweimal mit demselben Fehler ab.
      if (antwort.status === 403) {
        passwort.value = ''
        requestAnimationFrame(() => passwortFeld.value?.focus())
      }
      return
    }
    // Die Compat-Schicht legt JEDE Nutzlast unter `message` (wie `apiCall`
    // sie auspackt). Ohne dieses Auspacken blieben Titel, Datum und Inhalt
    // leer — die öffentliche Seite zeigte „Beitrag“ und sonst nichts.
    const nutzlast = gastNutzlast(daten)
    inhalt.value = {
      typ: nutzlast?.typ || '',
      titel: nutzlast?.titel || '',
      inhalt: nutzlast?.inhalt || '',
      datum: nutzlast?.datum || '',
    }
  } catch {
    meldung.value = 'Keine Verbindung. Bitte prüfe dein Netz und versuche es erneut.'
  } finally {
    laedt.value = false
  }
}

/**
 * CSRF-Token dieses Dokuments.
 *
 * Ein Gast ohne Sitzung braucht keinen: die CSRF-Middleware prüft nur, wenn es
 * eine Sitzung gibt. Ist jemand angemeldet und öffnet den Link, muss der Token
 * mit — er steht dann im Boot-Objekt; fehlt er, wird er über die bestehende
 * Adresse `frappe.sessions.get_csrf_token` geholt (POST, siehe
 * `auth_middleware._WEITERE_AUSNAHMEN`).
 */
const csrfWert = ref(window.__DIakonosBOOT?.csrf_token || '')

function csrfToken() {
  return csrfWert.value || ''
}

async function holeCsrfToken() {
  try {
    const res = await fetch(apiUrl('frappe.sessions.get_csrf_token'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
    const daten = await res.json().catch(() => null)
    const neu = daten?.message?.csrf_token || daten?.csrf_token || ''
    if (neu) csrfWert.value = neu
  } catch {
    // Kein Token erhältlich: die Wiederholung scheitert erneut und meldet
    // den Serverfall — kein erfundener Wert.
  }
}

/** Fehlertext der Antwort (`message` der Compat-Schicht, `_server_messages` alt). */
function servertext(daten) {
  if (!daten) return ''
  if (typeof daten.message === 'string' && daten.message.trim()) return daten.message
  try {
    const liste = JSON.parse(daten._server_messages || '[]')
    if (liste.length) return JSON.parse(liste[0]).message || ''
  } catch { /* alte Form nicht vorhanden */ }
  return ''
}

// Nur für die Vorlage: derselbe Text wie im Leerzustand.
defineExpose({ GAST_FEHLER_ABGELAUFEN, GEMEINDE_ZONE })
</script>

<style scoped>
/* Diakronos Public Page — dieselbe Gestalt wie die öffentliche Gast-Anmeldung
   (`registrierung/main.js` lädt dieselben Tokens). Alle Farben/Raumwerte aus
   tokens.css; kein Hartwert. */
.dk-pub-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--sp-5);
  font-family: var(--font);
  font-size: var(--fs-14);
  line-height: 1.5;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

.dk-pub-card {
  background: var(--surface);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 400px;
  padding: var(--sp-6);
  margin: auto;
}
/* Inhalt braucht Lesebreite — das Passwortformular braucht sie nicht. */
.dk-pub-card.r6-gastinhalt-breit {
  max-width: var(--lesebreite, 720px);
  padding: var(--sp-6) var(--pad);
}

.dk-pub-center { text-align: center; }
.dk-pub-icon-large { font-size: var(--fs-26); margin-bottom: var(--sp-4); }
.dk-pub-title {
  font-size: var(--fs-20);
  font-weight: var(--fw-fett);
  color: var(--text);
  margin: 0 0 var(--sp-1);
  letter-spacing: -0.01em;
}
.dk-pub-muted { font-size: var(--fs-14); color: var(--muted); margin: 0; line-height: 1.5; }
.r6-gastinhalt-unterzeile { margin-bottom: var(--sp-4); }
.dk-pub-form { display: flex; flex-direction: column; gap: var(--sp-3); }

.r6-gastinhalt-fehler {
  margin: 0 0 var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-sm);
  line-height: 1.5;
}

.r6-gastinhalt { display: flex; flex-direction: column; gap: var(--sp-4); }
.r6-gastinhalt-kopf { border-bottom: var(--rahmen-breite) solid var(--divider); padding-bottom: var(--sp-3); }
.r6-gastinhalt-art {
  margin: 0 0 var(--sp-1);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.r6-gastinhalt-titel {
  margin: 0 0 var(--sp-1);
  font-size: var(--fs-h2);
  font-weight: var(--fw-fett);
  line-height: 1.3;
  color: var(--text);
}
.r6-gastinhalt-datum { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.r6-gastinhalt-text { font-size: var(--fs); line-height: 1.7; color: var(--text); max-width: var(--lesebreite); }
.r6-gastinhalt-text :deep(p) { margin: 0 0 var(--sp-3); }
.r6-gastinhalt-text :deep(ul),
.r6-gastinhalt-text :deep(ol) { margin: 0 0 var(--sp-3) var(--sp-4); padding: 0; }
.r6-gastinhalt-text :deep(li) { margin-bottom: var(--sp-1); }
.r6-gastinhalt-text :deep(h1),
.r6-gastinhalt-text :deep(h2),
.r6-gastinhalt-text :deep(h3) { font-size: var(--fs-h3); margin: var(--sp-4) 0 var(--sp-2); }
.r6-gastinhalt-text :deep(a) { color: var(--primary); }
.r6-gastinhalt-text :deep(img) { max-width: 100%; height: auto; }
.r6-gastinhalt-text :deep(table) { width: 100%; border-collapse: collapse; }
.r6-gastinhalt-text :deep(td),
.r6-gastinhalt-text :deep(th) { padding: var(--sp-2); border-bottom: var(--rahmen-breite) solid var(--divider); }

/* Am Handy weniger Rand: reine Polsterung, keine Layout-Umschaltung.
   Umbruch bei der Mobilgrenze der App; der 640px-Wert gehört der
   Entscheidungstabelle dieses Pakets. */
@media (max-width: 720px) {
  .dk-pub-page { padding: var(--sp-4); }
  .dk-pub-card { padding: var(--sp-5); }
  .dk-pub-card.r6-gastinhalt-breit { padding-top: var(--sp-5); }
}
</style>
