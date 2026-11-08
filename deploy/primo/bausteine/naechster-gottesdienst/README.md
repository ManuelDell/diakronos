# Baustein `naechster-gottesdienst` — Diakronos: Nächster Gottesdienst

**Was er zeigt:** den nächsten freigegebenen Termin aus Diakronos groß —
Wochentag, Datum, Uhrzeit, Ort — mit optionalem Zusatztext und Zusatzlink
(z. B. Livestream). Der Name „Gottesdienst“ ist nur die Vorgabe der
Überschrift; über Kategorie oder Kalender ist der Block für jeden Anlass
brauchbar (generisch, G2).

**Datenquelle (BS-1b, L3):**
`GET {Diakronos-Adresse}/website/oeffentlich/naechster_termin?kategorie&kalender&gruppe`
→ `{"message": { … }}` oder `{"message": null}`, wenn nichts ansteht. Genutzt
werden nur `titel, beginn, ende, ganztaegig, ort` (aus der Positivliste).

**Felder**

| Feld | Bedeutung |
|---|---|
| Überschrift | z. B. „Nächster Gottesdienst“ |
| Diakronos-Adresse | absolute Adresse der Diakronos-Installation |
| Zeigt den nächsten Termin aus | „einem Kalender“ oder „einer Kategorie“ |
| Kalender-Kennung | Slug (bei Auswahl „Kalender“), leer = alle freigegebenen |
| Kategorie-Kennung | Kennung (bei Auswahl „Kategorie“) |
| Zusatztext | freier Text unter dem Termin (leer = keiner) |
| Adresse des Zusatzlinks / Beschriftung | z. B. Livestream-Adresse und „Livestream“ |
| Ort anzeigen | Schalter |
| Leertext, Lade-/Fehlertext | Beschriftungen |

**Verhalten**

* Wochentag und Datum in `Europe/Berlin`, Datum ausgeschrieben
  („Sonntag, 8. November 2026“), ganztägige Termine ohne Uhrzeit.
* Der Zusatzlink erscheint nur bei einer `http(s)`-Adresse; Text und Adresse
  sind Felder, damit jede Gemeinde ihre eigene Beschriftung setzen kann.
* Steht nichts an, zeigt der Block den Leertext — keine leere Karte.

**Freigabe (G1):** Es geht nur hinaus, was in Diakronos freigegeben ist.
