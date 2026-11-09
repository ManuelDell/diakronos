<template>
  <!-- UX3j (Entwurf A3): EIN Rahmen für den Bereich „Personen“ — die Seite
       `pages/Personen.vue` selbst. Vorher stand hier eine zweite Umsetzung mit
       einer SEITLICHEN Bereichsliste (UX-A2a); die ist mit A3 entfallen: in
       ALLEN Reitern steht dieselbe Reiterzeile oben. Damit es nur noch EINEN
       Personen-Rahmen gibt, lädt diese Datei ihn — sie bleibt als Adress-Ziel
       der Seitennamen (`MitgliederListe`, `MitgliederAnfragen`, …) und der
       Router-Tabelle erhalten. -->
  <Personen />
</template>

<script setup>
/**
 * Personen — Adress-Ziel der Reiter-Seitennamen (UX3j).
 *
 * Warum die Datei bleibt: `router.js` lädt für die Seitennamen
 * `MitgliederListe`, `MitgliederAnfragen`, `MitgliederDatenschutz`,
 * `MitgliederImport`, `MitgliederLoeschantraege` und `MitgliederUebersicht`
 * diesen Rahmen. Diese Namen sind Anker für Rechte-Guard, Fenstertitel und
 * Tests; sie zeigen jetzt alle auf DENSELBEN Personen-Rahmen
 * (`pages/Personen.vue`) — es gibt keine zweite Personen-Navigation mehr.
 *
 * Den Reiter entscheidet der Rahmen aus der Adresse
 * (`#/personen/<reiter>[/<unter>]`, menue.js); „Übersicht“ und
 * „Löschanträge“ sind keine Reiter (A3) — ihre Adressen bleiben erreichbar.
 */
import Personen from '../Personen.vue'
</script>
