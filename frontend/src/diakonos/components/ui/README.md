# UI-Bibliothek — „A · Ruhig & Klar“

Zentrale Bausteine der Diakonos-Oberfläche. **Alle Seiten und Komponenten
bauen nur noch hieraus.** Farben, Schrift, Abstände und Radien stammen
ausschliesslich aus `../../tokens.css` — feste Farbwerte (`#hex`, `rgb()`,
`hsl()`) in `.vue`-Dateien verbietet der Wächter-Test
(`frontend/tests/waechter-tokens.test.mjs`).

## Grundregeln

- **Nur Tokens.** In Styles immer `var(--…)` verwenden. Kein `#2563eb`, kein
  `rgb(…)`, kein `hsl(…)` — Farbe kommt aus `tokens.css`.
- **Wortwahl zentral.** Statuswörter und ihre Kennzeichen kommen aus
  `statussprache.mjs` (`entwurf` → „Entwurf", `muss` → „Fehler"), nie lokal
  neu erfunden.
- **Deutsch, einfach.** Keine Fachbegriffe („Slot") in sichtbaren Texten.
  Zielgruppe: ehrenamtliche Planer:innen und Mitglieder.
- **Keine schweren Abhängigkeiten.** Ausser Vue und dem vorhandenen Bestand
  nichts Neues.

## Bausteine

| Baustein        | Zweck                                            |
| --------------- | ------------------------------------------------ |
| `DkButton`      | Aktion: `primary`/`secondary`/`ghost`/`danger`, `sm`/`md` |
| `DkBadge`       | Kennzeichen: `neutral`/`ok`/`warn`/`err`/`info`/`akzent` |
| `DkCard`        | Fläche mit Kopf, Aktionen, Fuss                  |
| `DkDialog`      | Modaler Dialog mit Fokusfalle, Esc, aria; `beforeClose` prüft Verwerfen |
| `DkBestaetigung` | Globales Fenster für `bestaetigen({titel,text,aktion,gefahr})`; Abbrechen ist Standard |
| `DkField`       | Hülle für Eingabe: Label, Hilfe, Fehler          |
| `DkDatumZeit`   | Datum/Uhrzeit: deutsch angezeigt, ISO im Modell, Vorschlag 19:00–20:00 (S8) |
| `DkFilterChips` | Filterzeile als Chips, abwählbar, „Alle“ als Ruhezustand (S9) |
| `DkSkelett`     | Ladeplatzhalter — die eine Ladeform (S10)        |
| `DkSelect`      | Auswahlfeld                                      |
| `DkCheckbox`    | Ja/Nein-Kästchen                                 |
| `DkSegment`     | Umschalter als Segmentleiste                     |
| `DkTabs`        | Reiter mit Unterstrich-Aktivzustand              |
| `DkTable`       | Tabelle mit Kopf, leerem Zustand, Scrollen       |
| `DkHint`        | Hinweisfläche + Schrittfolge                     |
| `DkEmpty`       | Leerzustand                                      |
| `DkToast`       | `useToast`: Erfolg 4 s, Fehler bis Schließen, Live-Ansage, Pause bei Maus/Fokus |
| `DkPageHeader`  | Seitenkopf: Brotkrumen, Titel, Kennzeichen, Aktionen |

## Beispiele

### Aktion und Kennzeichen

```vue
<DkButton variant="primary" @click="veroeffentlichen">Veröffentlichen</DkButton>
<DkButton variant="ghost" size="sm" @click="abbrechen">Abbrechen</DkButton>

<DkBadge :variant="statusSprache(plan.status).variant">
  {{ statusSprache(plan.status).wort }}
</DkBadge>
```

### Seitenkopf

```vue
<DkPageHeader
  :krumen="[{ text: 'Pläne', href: '#/planrahmen' }, { text: plan.titel }]"
  :title="plan.titel"
  :badges="[{ text: '01.10. – 31.12.2026' }, { text: statusSprache(plan.status).wort, variant: statusSprache(plan.status).variant }]"
>
  <template #actions>
    <DkButton variant="primary" @click="veroeffentlichen">Veröffentlichen</DkButton>
  </template>
</DkPageHeader>
```

### Formularfeld

```vue
<DkField label="Titel" help="z. B. Chorplan Herbst 2026" :error="fehler.titel">
  <input class="dk-ui-eingabe" :id="…" />
</DkField>

<DkField label="Planvorlage">
  <DkSelect v-model="plantyp" :options="vorlagen" placeholder="— bitte wählen —" />
</DkField>
```

### Dialog

Schreibfenster verwenden `useFormularSchutz`: nach dem Befüllen `merken()`,
`darfSchliessen` als `beforeClose` an den Dialog und beim Abbrechen prüfen.
Erst nach bestätigtem Verwerfen schließen. Erfolgreiches Speichern schließt
direkt. Während des Speicherns sind Schließen und erneutes Speichern gesperrt.
Hintergrundklick schließt Formulare nie. Abbrechen verwendet `ghost`.


```vue
<DkDialog v-model="offen" title="Neuer Plan" size="md">
  …Inhalt…
  <template #footer>
    <DkButton variant="ghost" @click="offen = false">Abbrechen</DkButton>
    <DkButton variant="primary" @click="speichern">Anlegen</DkButton>
  </template>
</DkDialog>
```

### Hinweis mit Schritten

```vue
<DkHint variant="akzent" :schritte="['Wer kann was?', 'Plan erstellt', 'Prüfen & veröffentlichen']" :aktiv="2">
  Noch zwei Schritte bis der Plan fertig ist.
</DkHint>
```

### Leerzustand in der Tabelle

```vue
<DkTable :spalten="spalten" :leer="!zeilen.length" leer-titel="Keine Termine">
  <tr v-for="z in zeilen" :key="z.id"><td>…</td></tr>
  <template #leer>
    <DkButton variant="primary" @click="terminHinzufuegen">Termin hinzufügen</DkButton>
  </template>
</DkTable>
```

## Do / Don't

| ✔ Do                                                        | ✘ Don't                                                     |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| `color: var(--text)`                                        | `color: #15182a`                                            |
| `background: var(--surface)`                                | `background: white`                                         |
| Statuswort aus `statusSprache(…)`                           | `status === 'veroeffentlicht' ? 'Veröffentlicht' : 'Entwurf'` |
| `DkButton`, `DkCard`, `DkTable` verwenden                   | Eigenes `<button class="…">` mit eigenen Farben             |
| Ein Kennzeichen je Aussage (`DkBadge`)                      | Farbe direkt am Text (`<span style="color: …">`)            |
| Abstände aus `var(--sp-…)` / `var(--pad)`                   | `margin: 13px` frei erfunden                                |
| Neue Bausteine in `components/ui/` ergänzen                 | Eigene Knöpfe in jeder Seite neu bauen                      |

## Neuen Baustein ergänzen

1. Datei unter `components/ui/` anlegen, ausschliesslich Tokens verwenden.
2. Beispiel und Tabellenzeile hier ergänzen.
3. Der Wächter-Test deckt `components/ui/` automatisch mit ab.
