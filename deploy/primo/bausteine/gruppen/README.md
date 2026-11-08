# Gruppen-Übersicht (`gruppen`)

Zeigt die in Diakronos **freigegebenen** Gruppen. Nichts ist öffentlich, solange
es in Diakronos nicht ausdrücklich freigegeben ist (`website_freigabe = true`,
ein `website_slug` gesetzt, Sichtbarkeit nicht „Versteckt", nicht im Papierkorb).

## Felder

| Feld | Bedeutung |
|---|---|
| Überschrift | Titel über der Liste |
| Diakronos-Adresse | Absolute Adresse der Diakronos-Installation (der Installer setzt sie vor) |
| Darstellung | `kacheln` oder `liste` |
| Gruppentyp | Filter auf den Gruppentyp (Name), leer = alle |
| Link-Muster für die Detailseite | optional; `{slug}` wird ersetzt, z. B. `/gruppen/{slug}`. Ohne `{slug}` wird der Slug angehängt. Leer = kein Link |
| Beschriftung des Detail-Links | Text des Links („Mehr erfahren") |
| Texte | Laden, Leertext, Fehlertext |

## Datenquelle

`GET {Diakronos-Adresse}/website/oeffentlich/gruppen?typ=…`

Genutzt werden ausschließlich `slug, name, typ, beschreibung, bild_url`
(Feld-Positivliste der Lese-API, BS-1b). **Nicht** ausgegeben und nicht
angezeigt: Verantwortliche, Leiter, Mitglieder, Dienstbereich, interne
Kennungen.

## Ohne Bild

Ist bei einer Gruppe kein Bild hinterlegt (oder ist es kein Rasterformat),
liefert die API `bild_url = ""`. Der Baustein rendert dann **kein** `<img>` —
es entsteht kein leerer Bildplatz, der Textblock beginnt direkt mit der
Überschrift.

## Bildadresse

`bild_url` kann relativ sein (`/diakronos/website/bild/gruppe/<slug>`); der
Baustein setzt die Diakronos-Adresse davor. Das Bild wird nur ausgeliefert,
solange die Gruppe freigegeben ist (dieselbe Prüfung wie die Liste).
