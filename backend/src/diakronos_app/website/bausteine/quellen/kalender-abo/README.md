# Baustein `kalender-abo` — Diakronos: Kalender-Abo

**Was er zeigt:** einen freigegebenen Kalender aus Diakronos zum Abonnieren —
den Abo-Link (`webcal://…`), die Adresse zum Eintragen (`https://…ics`), einen
Kopieren-Knopf und eine kurze, allgemein gehaltene Anleitung für Handy,
Outlook und Google Kalender.

**Datenquelle**

1. `GET {Diakronos-Adresse}/website/oeffentlich/kalender` (L1) → `[{slug, titel, farbe}]`
   — nur freigegebene Kalender. Ist das Feld „Kalender-Kennung“ leer, nimmt
   der Block den ERSTEN Eintrag dieser Liste (ebenfalls nur freigegeben).
2. Die Abo-Adresse wird daraus gebaut:
   `https://…/website/ical/<slug>.ics` (L7). Der Feed antwortet mit
   `text/calendar` und 404, wenn der Kalender nicht freigegeben ist.

**Felder**

| Feld | Bedeutung |
|---|---|
| Überschrift | Titel über dem Block |
| Diakronos-Adresse | absolute Adresse der Diakronos-Installation |
| Kalender-Kennung | Slug des Kalenders (leer = erster freigegebener) |
| Einleitungstext | freier Text über den Adressen |
| Beschriftung Abo-Link / zweite Adresse / Kopieren-Knopf | Texte |
| Text nach dem Kopieren | Bestätigung (`aria-live`) |
| Kurzanleitung: Handy / Outlook / Google | drei Texte, generisch |
| Leertext, Lade-/Fehlertext | Beschriftungen |

**Verhalten**

* Der Abo-Link ist ein `<a href="webcal://…">` — am Handy öffnet das
  Kalenderprogramm und fragt nach dem Hinzufügen.
* Der Kopieren-Knopf nutzt `navigator.clipboard`; ohne diese Berechtigung wird
  das Adressfeld markiert und ausgewählt, damit ein Kopieren von Hand geht.
  Der Knopf ist ein `<button type="button">` und löst kein Absenden aus.
* Die Anleitung ist bewusst allgemein („Kalender hinzufügen“, „Aus dem
  Internet abonnieren“, „Per URL“) — kein Produktname einer Gemeinde, keine
  festen Pfade.

**Freigabe (G1):** L1 und L7 liefern nur freigegebene Kalender; ein nicht
freigegebener Slug antwortet 404, ohne zu verraten, ob es ihn gibt.
