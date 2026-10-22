# Eigene Daten und Datenschutz (N7)

Profil: `#/profile`. Jeder sieht nur die der eigenen Sitzung zugeordnete
Person. Wer kein Konto oder keinen zugeordneten Personeneintrag hat, wendet
sich an die Gemeindeverwaltung; sie bearbeitet die Wünsche unter
**Mitglieder → Datenschutz**.

## Bedienung

Foto- und Werbeeinwilligungen lassen sich erteilen und widerrufen. Der Stand
der Einwilligung zur Datenverarbeitung und ihr Datum werden angezeigt.
Gespeicherte Nachweise (einschließlich vorhandener Texte) stehen in der
Auskunft; Fragen oder der Widerruf der Einwilligung zur Datenverarbeitung
laufen über die Gemeinde. Die Schalter für das Adressbuch bleiben separat im
Profil.

**„Meine Daten ansehen / herunterladen“** öffnet die eigene Auskunft als JSON
und bietet einen tatsächlichen Dateidownload. Es ist derselbe fachliche Weg wie
in der Verwaltung ([N6](N6-DATENSCHUTZ.md)), aber ohne freie Zielauswahl und
ohne Verwaltungsrechte. Fremde Inhalte, bloße Autorenschaft und Zugangsdaten
sind genauso abgegrenzt wie dort.

**„Löschung beantragen“** erklärt vor dem Absenden Wirkung und Grenzen. Erst
nach Eingabe von `BEANTRAGEN` und Bestätigung entsteht ein Antrag. Die Person
bleibt angemeldet, Einwilligungen und Daten bleiben unverändert. Der Server
verlangt POST und `bestaetigt=true`. Der offene Antrag ist wiederholbar und
bleibt nach dem Neuladen sichtbar. Geprüft wird er von der Verwaltung im Reiter
Datenschutz. Die frühere Aktion zum sofortigen Löschen antwortet mit 417 und
einem Hinweis auf den Antrag — niemals mit einer Sofortlöschung, auch nicht für
ältere Clients.

## Eigene Endpunkte

Unter `diakronos.diakonos.api.datenschutz`:

```
meine_auskunft()                        gleiche Auskunft wie in der Verwaltung, eigene Person
mein_loeschantrag()                     null oder {mitglied, beantragt_am, status}
loeschung_beantragen(bestaetigt=true)   der Antragsweg aus N6
```

Alle verlangen eine Anmeldung. Ohne eindeutige Verknüpfung zur Person wird
verweigert. Ein mitgeschicktes `mitglied_id` kann das Ziel nicht ändern.

## Was die Anonymisierung entfernt

- Zugeordnete Anmeldezeilen verlieren Namen, Kontaktdaten, Geburtstag, Adresse
  und Freitext; ihre Antwort- und Kindzeilen werden entfernt. Fremde
  Anmeldungen bleiben unverändert. Alles geschieht in derselben Transaktion wie
  Personenstamm, Kontensperre, Widerrufsnachweise und Antragserledigung; ein
  gezielt ausgelöster Fehler beim Protokollschreiben prüft den vollständigen
  Rücklauf.
- Strukturangaben (Pfad im Baum, Eintrittsdatum, Bemerkungsstatus) werden
  geleert; Bereich und Familienbeziehungen — auch die Gegenrichtung sowie
  Verweise auf Eltern- und Partnereinträge — werden entfernt.
- Der technische Schlüssel der Person wird **nicht** in den Nachnamen kopiert:
  importierte Kennungen können Klarnamen sein. In der Anzeige steht danach
  „Gelöscht Person“. Der Primärschlüssel bleibt wegen historischer Verweise
  erhalten.

## Bekannte Grenzen

Das ist **keine vollständige Anonymisierung aller historischen Inhalte**:
technische Kennungen (Personen- und Kontokennung sowie historische Verweise)
können Klarnamen oder E-Mail-Adressen enthalten. Sie werden nicht umbenannt;
eine Kontokennung bleibt belegt. Beide Dialoge nennen diesen Umstand
ausdrücklich. Dateiinhalte, Freitextnennungen, historische Nachweise und
Konten in einem externen Anmeldedienst müssen gesondert geprüft werden. Es gibt
keine neue Frist- oder Aufbewahrungsregel und keinen automatischen Mailversand.

## Prüfung

`backend/tests/test_n7_profil_datenschutz.py` deckt ab: Auflösung der eigenen
Person, Gast und fehlende Zuordnung, Antragsstand, gesperrter Altpfad,
Bereinigung von Registrierungs- und Strukturangaben, vollständigen Rücklauf und
den Fall, dass eine Kennung ein Klarname ist. Die bestehenden Zustands- und
Sitzungstests laufen jetzt über den bestätigten Antrag plus Verwaltungsaktion
statt über die abgeschaffte Sofortlöschung; der zentrale Sitzungswiderruf wird
am neuen Weg geprüft. `frontend/tests/n7-profil.test.mjs` ist in der
Testliste des Docker-Builds enthalten.
