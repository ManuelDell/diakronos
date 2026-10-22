<template>
  <div class="reg-zugang">
    <p class="reg-zugang-text">
      <strong>{{ vorname }}</strong> wurde angelegt. Gib den Link selbst weiter —
      die Person vergibt damit ihr Passwort (Entscheidung: kein Mailversand).
    </p>
    <RegLinkTeilen :link="link" :bezeichnung="bezeichnung" />
    <p class="reg-zugang-mini">
      Ohne E-Mail-Adresse gibt es keine Person, die den Link annehmen kann; dann
      bleibt der Personeneintrag ohne Zugang.
    </p>
  </div>
</template>

<script setup>
/**
 * PersonZugang — Karte „Zugang“ nach dem Anlegen einer Person (N3).
 *
 * Konzept Abschnitt 4: „Bei ‚Link senden‘ zeigt das Fenster sofort den Link
 * (Kopieren, Teilen, QR-Code).“ Der Zugangs-Weg selbst (Konto anlegen, Link
 * erzeugen) entsteht mit N4/N5; diese Karte ist die Anzeige des fertigen
 * Links und wird von dort mit `link` versorgt — nichts Halbfertiges wird
 * gezeigt, solange kein Link vorliegt.
 *
 * Bewusst dieselben Bausteine wie im Unterbereich „Links & QR-Codes“:
 * voller Link, Kopieren/Teilen, QR (lokal, PNG, Druck).
 */
import RegLinkTeilen from './RegLinkTeilen.vue'

defineProps({
  /** Voller Link (vom Server, `/diakonos/…?token=…`). */
  link: { type: String, required: true },
  /** Anzeigename für Überschrift und PNG-Dateiname. */
  vorname: { type: String, default: '' },
  bezeichnung: { type: String, default: 'Zugang' },
})
</script>

<style scoped>
.reg-zugang { display: flex; flex-direction: column; gap: var(--sp-3); }
.reg-zugang-text { margin: 0; color: var(--text); line-height: 1.5; }
.reg-zugang-mini { font-size: var(--fs-xs); color: var(--muted); margin: 0; }
</style>
