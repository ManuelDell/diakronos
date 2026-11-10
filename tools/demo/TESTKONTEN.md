# Testkonten der Demo „Musterhausen“ (SEED-R1)

Alle Konten gehoeren **bestehenden Personen** der Demo — es wurden weder neue
Personen noch neue Rollenverteilungen erfunden (Manuel 09.11.: „Nutze die
bestehenden Rollenverteilungen, die bereits konfiguriert sind. Kreiere fuer den
Test keine neuen.“). `musterhausen.py` legt sie zusammen mit der Demo an.

**Passwort:** die vier Leitungs-Konten bekommen beim Anlegen den
Passwort-Hash von `admin@example.org` — also dasselbe Passwort wie das
Admin-Konto (hier nicht notiert). Bestehende Konten werden nie ueberschrieben:
`admin@example.org` und `anna.beispiel@example.org` behalten ihr bisheriges
Passwort (oeffentlicher Demo-Standard `musterhausen-demo`, sofern nicht
geaendert).

| Konto | Person | Rolle | verantwortlich fuer (bestehend) | was testen |
|---|---|---|---|---|
| `admin@example.org` | Miriam Sonnleitner | System Manager, Mitgliederadministrator, Kalenderadministrator, Ressourcenmoderator (unveraendert) | keine Gruppe mehr (der fruehere Admin-Rueckfall ist entfernt); **bleibt** Moderator aller Kalender und `moderiert_von` der bestaetigten Demo-Buchungen (bewusst nicht neu verteilt) | MUSS: alle Verwaltungsseiten, Mitglieder, Rollen, Kalender, Ressourcen, Plaene; jede Gruppe verwalten (Rollen-Kurzschluss). DARF NICHT: in einer Gruppe als Verantwortlicher stehen. |
| `rebekka.fink@example.org` | Rebekka Fink | Mitglied | Verantwortliche Gruppe „Chor“ (Leitung), Website-Ansprechpartnerin Chor | MUSS: Chor verwalten (Mitglieder hinzufuegen/entfernen, Gruppendaten, Aufgaben/Ankuendigungen); Planrahmen-Plan „Chorplan …“ bearbeiten (Vorlage ist an die Gruppe Chor gebunden); „Dienstplan Gottesdienst“ bearbeiten (Gruppe des Plans = Chor). DARF NICHT: Jugendkreis, Kinderdienst, Technikteam, Lobpreis verwalten; Verwaltung (Mitglieder, Rollen) oeffnen. |
| `samuel.fink@example.org` | Samuel Fink | Mitglied | Verantwortlicher Gruppe „Jugendkreis“ (Leitung) | MUSS: Jugendkreis verwalten (Mitglieder, Gruppendaten, Untergruppe anlegen, Aufgaben/Ankuendigungen). DARF NICHT: Chor oder Kinderdienst verwalten, Plaene bearbeiten, Verwaltung oeffnen. |
| `susanne.gerlach@example.org` | Susanne Gerlach | Mitglied | Verantwortliche Gruppe „Kinderdienst“ (Leitung), Leitung „Dienstplan Kinderdienst“ | MUSS: Kinderdienst verwalten; „Dienstplan Kinderdienst“ (Dienstplan-Modul) bearbeiten. DARF NICHT: Chor/Jugendkreis/Technik verwalten, den Planrahmen-Plan „Kindergottesdienst …“ bearbeiten (der gehoert Anna als Planverantwortlicher, die Vorlage ist an keine Gruppe gebunden), Verwaltung oeffnen. |
| `niklas.jaeger@example.org` | Niklas Jäger | Mitglied | Verantwortlicher Gruppe „Technikteam“ (Leitung) | MUSS: Technikteam verwalten. DARF NICHT: Chor/Kinderdienst/Jugendkreis verwalten, Plaene bearbeiten, Verwaltung oeffnen. |
| `anna.beispiel@example.org` | Anna Beispiel | Mitglied | **bestehend, unveraendert:** Dienstbereich „Musik“ (Verantwortliche + Website-Ansprechpartnerin), Leitung „Dienstplan Gottesdienst“, Planverantwortliche aller Planrahmen-Plaene der Demo | MUSS: Gruppen des Bereichs Musik verwalten (Chor, Lobpreis — ueber den Dienstbereich); „Dienstplan Gottesdienst“ und die Planrahmen-Plaene bearbeiten. DARF NICHT: Jugendkreis/Kinderdienst/Technikteam verwalten, Mitglieder oder Rollen aendern, Kalender moderieren. |

Hinweis: Anna ist damit **kein** „darf nichts“-Kontrollkonto — ihre
Verantwortungen stammen aus dem Bestand und wurden bewusst nicht umverteilt.

Was **nicht** neu verteilt wurde (bewusst so, Manuel 09.11.):

* Kalender-Moderatoren: bleiben, wie konfiguriert (Verwaltungskonto).
* Buchungen: `moderiert_von` bleibt, wie es ist.
* Dienstplan-Leitungen: Gottesdienst = Anna Beispiel, Kinderdienst = Susanne Gerlach.
* Weitere Gruppen-Leitungen ohne Konto (Simon Pahl — Lobpreis, Philipp Moser —
  Hauskreis, Matthias Reuter — Hauskreis Nord) stehen nur im Freitextfeld
  `gruppe.leiter` — ohne Verantwortungszeile und ohne Admin als Rueckfall.

## Umfang der Konten

Der Seed legt **sechs** Konten an: Verwaltung, Anna (Kontrollkonto) und die vier
Personen oben. „Fuenf Testkonten“ in der Karte meint die Nicht-Admin-Konten
(Anna + vier Leitungs-Personen).

## Nachziehen auf einer bestehenden Demo

```
python tools/demo/musterhausen.py --nachziehen   # Stand SEED-R1 herstellen
python tools/demo/musterhausen.py --entfernen    # Demo entfernen (raeumt auch die neuen Konten)
```

`--nachziehen` macht nur zwei Dinge und ist idempotent: (1) fehlende
Testkonten anlegen (Passwort-Hash = der aktuelle von `admin@example.org`;
bestehende Konten/Passwoerter bleiben unangetastet) und mit ihrem Mitglied
verknuepfen; (2) Gruppen-Verantwortungszeilen `<gruppe>-verantwortlich`, die
auf `admin@example.org` zeigen (Admin-Rueckfall des alten Seeds), auf das Konto
der Leitung umstellen bzw. — bei Leitung ohne Konto — entfernen. Kalender,
Dienstplaene, Website, Mitglieder und von Hand gesetzte Verantwortliche fasst
es nicht an. `--nachziehen --pruefen` zaehlt nur (Rollback).

## Stand auf `devecg` (Demo von vor BS-3a)

Dort gibt es keine Website-Ansprechpartner und keine
Dienstbereichs-Verantwortung — Anna ist dort also **nicht** Verantwortliche
„Musik“ und Rebekka **nicht** Website-Ansprechpartnerin; `--nachziehen` legt
das bewusst nicht nach. Anna leitet dort „Dienstplan Gottesdienst“ und ist
Planverantwortliche aller acht Planrahmen-Plaene.
