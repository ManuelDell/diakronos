<template>
    <div class="dk-pub-page">
        <div class="dk-pub-card" style="max-width: 400px;">

            <!-- WEB-7 (U2, U6): toter Gast-Link / ohne Token — der Browser
                 steht schon auf dem Weg zur Hauptseite. Bis dahin bleibt die
                 Karte leer: keine Meldung, kein „Zurück“ auf die Fehlerseite. -->
            <div v-if="umgeleitet" class="dk-pub-center" aria-hidden="true">&nbsp;</div>

            <!-- Fehler-Seite: NUR für Fälle mit Rückmeldung (U3) — Rate-Limit,
                 Serverfehler, zeitliche Grenze des Links. -->
            <div v-else-if="linkFehler" class="dk-pub-center">
                <div class="dk-pub-icon-large">🔒</div>
                <h1 class="dk-pub-title">Zugang nicht möglich</h1>
                <p class="dk-pub-muted">{{ linkFehler }}</p>
            </div>

            <!-- Erfolgseite -->
            <div v-else-if="success" class="dk-pub-center">
                <div class="dk-pub-icon-large">✅</div>
                <h1 class="dk-pub-title">Anmeldung übermittelt!</h1>
                <p class="dk-pub-muted">Danke! Deine Anmeldung wurde übermittelt.</p>
            </div>

            <!-- Formular -->
            <template v-else>
                <h1 class="dk-pub-title">Gast-Anmeldung</h1>
                <p class="dk-pub-muted" style="margin-bottom:24px">
                    Schnell und einfach – nur dein Name und eine kurze Datenschutzzustimmung.
                </p>

                <DkFehlertext v-if="fehler" :message="fehler" class="mb-4" />

                <form @submit.prevent="absenden" class="dk-pub-form" novalidate>
                    <DkField label="Vorname" required>
                        <template #default="{ id, ariaDescribedby, ariaInvalid }">
                            <DkEingabe :id="id" v-model="form.vorname" autocomplete="given-name"
                                       :aria-describedby="ariaDescribedby" :aria-invalid="ariaInvalid" />
                        </template>
                    </DkField>
                    <DkField label="Nachname" required>
                        <template #default="{ id, ariaDescribedby, ariaInvalid }">
                            <DkEingabe :id="id" v-model="form.nachname" autocomplete="family-name"
                                       :aria-describedby="ariaDescribedby" :aria-invalid="ariaInvalid" />
                        </template>
                    </DkField>

                    <!-- DSGVO / Einwilligung: Text kommt vom Server
                         (window.__diakronos.texte). Genau dieser Wortlaut wird
                         beim Absenden als Beleg gespeichert (N9b/H-1).
                         Reiner Text, kein HTML. -->
                    <div class="dk-pub-dsgvo">
                        <p v-if="willkommenstext" class="dk-pub-willkommen">{{ willkommenstext }}</p>
                        <p class="dk-pub-dsgvo-text" style="font-size:12px">{{ texte.einwilligung }}</p>
                        <label class="dk-pub-check">
                            <input type="checkbox" v-model="form.dsgvo" class="dk-pub-checkbox" />
                            <span class="dk-pub-dsgvo-label" style="font-size:12px">Ich stimme zu. *</span>
                        </label>
                    </div>

                    <DkButton type="submit" variant="primary" block :loading="loading">
                        Anmelden
                    </DkButton>
                </form>
            </template>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../shared/basis.js'
// WEB-7: Entscheidung „toter Link -> Hauptseite ohne Meldung“ (U2).
import {
    brauchtWeiterleitung,
    weiterleitenZurHauptseite,
} from '../shared/linkziel.js'
// WEB-8b: CSRF-Ablehnung automatisch heilen (Token neu, 1 Wiederholung).
import { heileOderMelde } from '../shared/csrf-heilung.js'
// DEP-1: eigene Bausteine statt frappe-ui (Button/FormControl/ErrorMessage).
import DkButton from '../diakonos/components/ui/DkButton.vue'
import DkField from '../diakonos/components/ui/DkField.vue'
import DkEingabe from '../diakonos/components/ui/DkEingabe.vue'
import DkFehlertext from '../diakonos/components/ui/DkFehlertext.vue'

const token      = window.__diakronos?.token || ''
// WEB-7: `linkGrund` vom Server (`spa.py::_link_grund`) — „toter Link“ gegen
// „die Person braucht eine Erklärung“ (Bremse 429, Serverfehler, zeitliche
// Grenze) abgrenzen.
const linkGrund  = window.__diakronos?.linkGrund || ''
const linkFehler = window.__diakronos?.linkFehler || ''

// WEB-7 (U2): ungültiger/abgelaufener/deaktivierter Gast-Token oder Seite
// ohne `?token=` -> sofort auf die Wurzel der DOMAIN, ohne Meldung.
// `replace` ersetzt den Verlaufseintrag (U6).
const umgeleitet = weiterleitenZurHauptseite(
    brauchtWeiterleitung({ grund: linkGrund, tokenFehlt: !token }),
)
// N9b (H-1, M-1): Einwilligungstext und Willkommenstext kommen vom Server.
// Es ist GENAU der Wortlaut, den submit_gast als Beleg speichert.
const texte      = window.__diakronos?.texte || {}
const willkommenstext = (window.__diakronos?.willkommenstext || '').trim()

const success = ref(false)
const loading = ref(false)
const fehler  = ref('')

const form = reactive({ vorname: '', nachname: '', dsgvo: false })

async function absenden() {
    fehler.value = ''
    if (!form.vorname.trim() || !form.nachname.trim()) {
        fehler.value = 'Vor- und Nachname sind Pflichtfelder.'
        return
    }
    if (!form.dsgvo) {
        fehler.value = 'Bitte stimme der Datenschutzzustimmung zu.'
        return
    }

    loading.value = true
    try {
        // WEB-8b: derselbe Aufruf als Funktion, damit eine CSRF-Ablehnung
        // still geheilt werden kann (Token neu + genau eine Wiederholung,
        // sonst Force-Refresh). Der Token wird je Versuch frisch gelesen.
        const anfrage = () => fetch(apiUrl('diakronos.diakonos.api.registrierung.submit_gast'), {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || window.csrf_token || '',
            },
            body: JSON.stringify({ token, vorname: form.vorname.trim(), nachname: form.nachname.trim(), dsgvo: form.dsgvo,
                // N12b (W2a): die Fassung, die der Person angezeigt wurde.
                // Ohne dieses Feld nimmt der Server den Rueckwaerts-Pfad und
                // belegt die AKTUELLE statt der angezeigten Fassung — der
                // Nachweis waere dann nicht mehr Art. 7 DSGVO (angezeigt =
                // bestaetigt). Wie auf der Registrierungsseite.
                dsgvo_fassung: texte.einwilligung_fassung ?? '' }),
        })
        // WEB-8b: `heileOderMelde` führt die Anfrage selbst aus. Nur bei einer
        // CSRF-Ablehnung holt es still ein frisches Token und wiederholt GENAU
        // EINMAL (sonst Force-Refresh mit 60-s-Schleifenschutz). Ohne CSRF
        // kommt unverändert die erste Antwort zurück.
        // WEB-8c (R2): die erste Antwort wird mitgegeben — `heileOderMelde`
        // wiederholt nur bei einer CSRF-Ablehnung und dann genau einmal.
        // WEB-8d (M1): `gast: true` — die Person hat hier KEIN Konto. Der
        // Token-Abruf über `session.sitzung_status` verlangt Anmeldung, ein
        // Gast bekam 401 und landete auf `/login`. Stattdessen: höchstens ein
        // Neuladen (frisches Seiten-Token), danach die Meldung auf dieser Seite.
        const erste = await anfrage()
        const { res, data } = await heileOderMelde({ anfrage, res: erste, gast: true })
        if (!res.ok || data?.exc) {
            fehler.value = parseServerError(data)
            return
        }
        success.value = true
    } catch (e) {
        // WEB-8c (R8) / WEB-8d (N3): Läuft bereits ein Neuladen/eine
        // Weiterleitung, blitzt KEIN „Verbindungsfehler" auf. WEB-8d (M1):
        // `e.meldung` heißt „Seite ist stehen geblieben" — dann kommt der
        // feste Hinweis an die Stelle der Fehlermeldung.
        if (e?.neuLaden || e?.weitergeleitet) return
        if (e?.meldung && e?.hinweis) { fehler.value = e.hinweis; return }
        fehler.value = 'Verbindungsfehler. Bitte versuche es erneut.'
    } finally {
        loading.value = false
    }
}

function parseServerError(data) {
    if (!data) return 'Ein Fehler ist aufgetreten. Bitte versuche es erneut.'
    // UXD-R27: der Serverfehlertext steht in `message` (Compat-Schicht:
    // `_error_response` -> {"message": …}); die Frappe-Schreibweise
    // `_server_messages` wird weiter unterstuetzt (Altbestand).
    if (typeof data.message === 'string' && data.message.trim()) {
        return data.message
    }
    try {
        const msgs = JSON.parse(data._server_messages || '[]')
        if (msgs.length) return JSON.parse(msgs[0]).message
    } catch {}
    return 'Ein Fehler ist aufgetreten. Bitte versuche es erneut.'
}
</script>

<style>
/* Diakronos Public Page — gast lädt diakonos/index.css (tokens.css), daher
   stammen alle Farben/Raumwerte aus dem gemeinsamen Token-System. */

.dk-pub-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

.dk-pub-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 520px;
  padding: 40px;
}

/* Inhaltsumbruch, kein Layout: nur der Innenabstand der öffentlichen Karte
   (die Seite selbst ist immer zentriert, ohne Rahmen). */
@media (max-width: 640px) {
  .dk-pub-card { padding: 24px; }
  .dk-pub-page { padding: 16px; }
}

.dk-pub-center { text-align: center; }

.dk-pub-icon-large { font-size: 48px; margin-bottom: 16px; }

.dk-pub-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 6px 0;
  letter-spacing: -0.01em;
}

.dk-pub-muted {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
  line-height: 1.5;
}

.dk-pub-form { display: flex; flex-direction: column; gap: 14px; }

.dk-pub-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
}

.dk-pub-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
  flex-shrink: 0;
}

.dk-pub-dsgvo {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 14px;
  font-size: 13px;
}

.dk-pub-dsgvo-text {
  color: var(--muted);
  margin: 0 0 10px 0;
  line-height: 1.5;
  white-space: pre-line;
}

/* N9b: gepflegter Willkommenstext ueber dem Formular. */
.dk-pub-willkommen {
  color: var(--text);
  font-weight: 500;
  margin: 0 0 10px 0;
  line-height: 1.5;
  white-space: pre-line;
}

.dk-pub-dsgvo-label {
  font-weight: 500;
  color: var(--text);
}
</style>
