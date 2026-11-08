# Gruppen-Steckbrief (`gruppe-steckbrief`)

Steckbrief **einer** freigegebenen Gruppe: Bild, Beschreibung, Treffzeit,
Treffpunkt und die nächsten Termine.

## Felder

| Feld | Bedeutung |
|---|---|
| Überschrift | leer = Name der Gruppe aus Diakronos |
| Diakronos-Adresse | Absolute Adresse der Diakronos-Installation |
| Kennung der Gruppe | **Pflicht**: der `website_slug` der Gruppe (z. B. `kinderkreis`) |
| Anzahl der nächsten Termine | 0–20; 0 blendet die Terminliste ganz aus |
| Kontakt-Hinweistext | freier Text, leer = kein Hinweis |
| Beschriftungen | Treffzeit, Treffpunkt, „Nächste Termine", ganztägig |
| Texte | Laden, Leertext, Leertext Termine, Fehlertext |

## Datenquelle

`GET {Diakronos-Adresse}/website/oeffentlich/gruppe?slug=<kennung>`

Die Antwort trägt `slug, name, typ, beschreibung, treffzeit, treffpunkt,
bild_url` und `naechste_termine` (max. 10, aus **freigegebenen** Kalendern,
Feld-Positivliste wie die Terminliste).

## Nicht freigegeben = Leertext, nicht Fehler

Ist die Gruppe nicht freigegeben, unbekannt oder im Papierkorb, antwortet die
API mit **404** — ohne zu verraten, welcher Fall vorliegt. Der Baustein zeigt
dann den Leertext, nicht den Fehlertext: ein Fehler klingt nach „kaputt", ein
fehlender Steckbrief ist aber ein Inhaltszustand.

Der Kontakt-Hinweis ist ein **freier Redakteurstext** — der Baustein ergänzt
bewusst keine Adresse und keinen Namen aus Diakronos (G1: keine
Personendaten/Autor-Namen öffentlich).
