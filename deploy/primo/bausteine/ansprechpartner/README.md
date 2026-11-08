# Diakronos: Ansprechpartner

Zeigt die Ansprechpartner einer Gemeinde auf der Website — mit Name, Bereich,
optionalem Foto und einem Kontakt-Knopf.

## Datenschutz ist hier der Kern

Es erscheinen **nur Personen, die ihrer Nennung auf der Website selbst
zugestimmt haben**. Die Zustimmung gibt die Person in Diakronos im eigenen
Profil (`website.meine_einwilligung_setzen`), nicht die Verwaltung:

* `website_einwilligung` — Grundzustimmung (Default **aus**)
* `website_einwilligung_foto` — eigene Zustimmung zum Bild. Ohne diese
  Zustimmung liefert die API keine Bildadresse und die Bild-Route antwortet
  404.
* `website_anzeigename` — freiwillig, z. B. nur der Vorname

Der **Widerruf wirkt sofort**: die Lese-API prüft die Schalter bei jeder
Anfrage, es gibt keinen Zwischenspeicher. Wer widerruft, verschwindet mit dem
nächsten Seitenaufruf — auch aus dem Baustein, ohne dass der Redakteur etwas
tun muss.

Die Verwaltung wählt nur aus, **welche Funktionen/Positionen** überhaupt
erscheinen dürfen (Organigramm: Dienstbereich oder Gruppe) und ob ein
Kontakt-Postfach daran hängt. Sie kann keine Einwilligung setzen — das ist
technisch ausgeschlossen (eigene Endpunkte, eigener Nachweis im Test).

## Felder

| Feld | Bedeutung |
|---|---|
| Überschrift | Titel über der Liste |
| Einleitung | optionaler Text unter der Überschrift |
| Diakronos-Adresse | absolute Adresse von Diakronos; wird beim Einspielen vorbelegt |
| Nur dieser Bereich | optionaler Filter auf den Anzeigenamen eines Bereichs |
| Darstellung | `karten` (Raster) oder `liste` (eine Zeile je Person) |
| Foto anzeigen | schaltet das Bild ab, auch wenn die Person zugestimmt hat |
| Kontakt-Knopf-Text | Beschriftung; **leer = kein Knopf** |
| Adresse des Kontaktformulars | `{postfach}` wird durch den Postfach-Slug ersetzt; relative Pfade sind erlaubt |
| Text während des Ladens / Leertext / Fehlertext | Beschriftungen |

## Datenquelle

```
GET {Diakronos-Adresse}/website/oeffentlich/ansprechpartner?bereich=<optional>
-> {"message": [{"bereich", "funktion", "name", "foto_url", "postfach"}, …]}
```

Es werden ausschließlich diese fünf Felder gelesen. **Keine** E-Mail-Adresse,
**keine** Telefonnummer, keine Adresse, kein Geburtsdatum, keine interne
Personenkennung und keine Einwilligungsdaten — weder in der Antwort noch im
Baustein.

`foto_url` ist eine relative oder absolute Bildadresse
(`/website/bild/person/<gesalzene Kennung>`); der Baustein setzt bei relativen
Adressen den Ursprung der Diakronos-Adresse davor. `postfach` ist ein
Postfach-**Slug** aus Diakronos (`website_kontakt_postfach`), keine Adresse;
die Website hängt ihn an das Kontaktformular, das die Nachricht dann über
Diakronos versendet.

## Verhalten im Browser

* Abruf im `$effect` (kein `onMount` — Primo rendert Abschnitte mit
  `svelte/server`), Zeitlimit 8 s, `cache: 'no-store'`.
* `aria-live="polite"` an der Liste, `role="status"` an Lade-, Leer- und
  Fehlertext; das Bild trägt einen Alt-Text (der Name).
* Der Kontakt-Knopf ist ein **Link** auf das Kontaktformular — kein Absenden
  aus dem Baustein heraus.
* Mobil zuerst; Raster ab 40 em zweispaltig, ab 60 em dreispaltig.
* Farben ausschließlich über `--dk-*`-Custom-Properties, die gelesen (nie
  deklariert) werden; kein externes CDN, keine Fremdschriften.
