<template>
  <div class="ue-diakronos">
    <!-- ABN-3: "Über Diakronos" — die laufende Version an EINER ruhigen Stelle.
         Die Werte kommen aus dem Boot-Objekt (`window.__DIakonosBOOT`), das der
         Server aus DERSELBEN Quelle fuellt wie /healthz
         (`diakronos_app.version_auskunft_sichtbar`). Hier wird nichts
         nachgefragt und nichts geraten: fehlt der Wert, steht "unbekannt" —
         nicht eine plausible Zahl. ABN-3b/N9: die Build-Kennung (Zeile
         "Stand") liefert der Server NUR an Administratoren — andere Sitzungen
         sehen dort "nicht im Build vermerkt". -->
    <section class="ue-karte" aria-labelledby="ue-titel">
      <h3 id="ue-titel" class="ue-titel">Über Diakronos</h3>
      <p class="ue-einleitung">
        Diese Angaben brauchen Sie, wenn Sie beim Support nachfragen oder ein
        Update einspielen: sie sagen, welcher Stand hier gerade läuft.
      </p>

      <dl class="ue-liste">
        <div class="ue-zeile">
          <dt class="ue-schluessel">Version</dt>
          <dd class="ue-wert">
            <span class="ue-version" data-ue-feld="version">{{ version }}</span>
          </dd>
        </div>
        <div class="ue-zeile">
          <dt class="ue-schluessel">Stand (Git)</dt>
          <!-- Ohne Build-Kennung erscheint die Zeile NICHT: ein leerer Wert
               neben "Stand" sähe aus wie ein Fehler. ABN-3b/N9: die Kennung
               kommt nur fuer angemeldete Administratoren aus dem Boot-Objekt;
               fuer alle anderen bleibt es beim Text unten. -->
          <dd v-if="git" class="ue-wert">
            <code class="ue-hash" data-ue-feld="git">{{ git }}</code>
          </dd>
          <dd v-else class="ue-wert ue-wert--leer">nicht im Build vermerkt</dd>
        </div>
      </dl>

      <p class="ue-hinweis">
        Ein Update und der Rückweg auf den vorigen Stand sind je ein Befehl auf
        dem Server; die Anleitung dazu steht in der Betriebsanleitung,
        Abschnitt 18 („Update und Rückweg“). Dieses Fenster ändert nichts —
        es zeigt nur, was läuft.
      </p>
    </section>
  </div>
</template>

<script setup>
/**
 * ABN-3: Abschnitt "Über Diakronos" in den Einstellungen (Gruppe "Erweitert").
 *
 * Warum ein eigener Abschnitt und nicht nur die Fußzeile: die Fußzeile der
 * Seitenleiste ist eingeklappt unsichtbar, und am Handy liegt sie unter der
 * Schublade. Wer vor einem Update wissen will, was läuft, findet es hier —
 * zwei Klicks, ohne Entwicklerwerkzeuge.
 *
 * Werte: `version` und `git` liest die Funktion `versionAusBoot()` aus dem
 * Boot-Objekt; sie ist ohne Vue prüfbar (`./version.mjs`). Kein zweiter
 * Abruf, keine eigene Formatierung.
 */
import { versionAusBoot } from './version.mjs'

const { version, git } = versionAusBoot()
</script>

<style scoped>
/* Farben und Maße ausschließlich aus den Projekt-Tokens (tokens.css):
   hell und dunkel kommen damit ohne eigene Medienabfrage aus. */
.ue-diakronos {
  max-width: 46rem;
}

.ue-karte {
  padding: var(--sp-4) var(--sp-5);
  border: var(--rahmen-breite) solid var(--dk-border);
  border-radius: var(--radius);
  background: var(--dk-surface);
}

.ue-titel {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-h3);
  font-weight: var(--fw-fett);
  color: var(--dk-text);
}

.ue-einleitung {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-unterzeile);
  color: var(--dk-text-muted);
}

.ue-liste {
  margin: 0;
  display: grid;
  gap: var(--sp-2);
}

.ue-zeile {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--sp-2) var(--sp-3);
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--dk-border);
}

.ue-zeile:first-child {
  padding-top: 0;
  border-top: 0;
}

.ue-schluessel {
  min-width: 9rem;
  font-size: var(--fs-unterzeile);
  color: var(--dk-text-muted);
}

.ue-wert {
  margin: 0;
  font-size: var(--fs-16);
  color: var(--dk-text);
}

.ue-version {
  font-variant-numeric: var(--fs-tabular);
}

.ue-hash {
  font-family: var(--font-mono);
  font-size: var(--fs-unterzeile);
  /* Lange Hashwerte dürfen umbrechen statt die Karte zu sprengen. */
  overflow-wrap: anywhere;
}

.ue-wert--leer {
  color: var(--dk-text-muted);
  font-size: var(--fs-unterzeile);
}

.ue-hinweis {
  margin: var(--sp-4) 0 0;
  font-size: var(--fs-unterzeile);
  color: var(--dk-text-muted);
}

/* Handy (390 px): Schlüssel und Wert stehen untereinander — nebeneinander
   bliebe für den Wert zu wenig Platz, der Hash liefe über den Rand. */
@media (max-width: 30rem) {
  .ue-karte {
    padding: var(--sp-3) var(--sp-4);
  }

  .ue-zeile {
    flex-direction: column;
    gap: var(--sp-1);
  }

  .ue-schluessel {
    min-width: 0;
    font-size: var(--fs-sm);
  }
}
</style>
