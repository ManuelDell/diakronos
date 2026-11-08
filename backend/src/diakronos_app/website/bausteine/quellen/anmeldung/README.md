# Veranstaltungs-Anmeldung (`anmeldung`)

Zeigt die Termine mit **offener Anmeldung** und führt zum **bestehenden
Diakronos-Gast-Anmeldeformular**. Der Baustein baut keine eigene Anmeldung und
erfindet keine Adresse.

## Felder

| Feld | Bedeutung |
|---|---|
| Überschrift | Titel über der Liste |
| Diakronos-Adresse | Absolute Adresse der Diakronos-Installation |
| Kalender-Kennungen | kommagetrennt; leer = alle freigegebenen Kalender |
| Kennung eines einzelnen Termins | optional; die **öffentliche Kennung** (`id` aus der API) oder ein Gruppen-Slug |
| Anzahl der Termine | 1–50 |
| Anmeldung in neuem Tab öffnen | `target="_blank"` mit `rel="noopener noreferrer"` |
| Beschriftung des Anmeldeknopfs | „Jetzt anmelden" |
| Texte | Laden, Leertext, Fehlertext |

## Datenquelle und Auswahl

`GET {Diakronos-Adresse}/website/oeffentlich/termine?von=…&bis=…&limit=500&kalender=…`

Die Lese-API (BS-1b, L2) kennt keinen Parameter „nur Termine mit Anmeldung".
Der Baustein holt deshalb das Zeitfenster (heute bis +400 Tage, wie die API es
zulässt) und behält **nur** Zeilen mit brauchbarer `anmeldung_url`. Erst danach
greift `Anzahl` — die Liste zeigt also nie einen Termin ohne Anmeldeknopf.

`anmeldung_url` ist nur gesetzt, wenn in Diakronos **alles** zutrifft:

* `anmeldung_aktiv` am Termin,
* es gibt einen Registrierungslink, er ist `aktiv` und trägt ein Token,
* sein Typ ist **Gast-Anmeldung** (ein Mitglieds-Registrierungslink ist nie
  öffentlich),
* heute liegt im Gültigkeitsfenster (`gueltig_ab` / `gueltig_bis`).

Die Adresse selbst kommt aus `anmeldung.registrierungslink.link_anzeige` —
dieselbe Funktion wie Verwaltung und Teilen-Link, damit Präfix
(`DIAKRONOS_BASE_PATH`) und gepflegte öffentliche Adresse nicht
auseinanderlaufen. Ist keine öffentliche Adresse gepflegt, ist sie **relativ**
(`/diakonos/gast?token=…`); der Baustein setzt die Diakronos-Adresse davor.
Alles, was kein `http(s)` wird, fällt weg — dann entfällt der Knopf.

## Warum ein Link und kein Knopf

Das Ziel ist eine andere Seite (das Gast-Formular). Ein `<a>` ist dafür das
richtige Element — Tastatur, Mittelklick, „in neuem Tab öffnen" funktionieren
von selbst. Er sieht nur wie ein Knopf aus (mindestens 44 px hoch, Touch-Ziel).
