# Datenschutz-Verwaltung (N6)

Adresse: `#/mitglieder/datenschutz`, nur für Mitgliederadministratoren und
System Manager. `#/dsgvo` leitet Administratoren dorthin, alle anderen ins
Profil weiter.

## Übersicht

Die Übersicht zählt Personen anhand der gespeicherten Einwilligung zur
Datenverarbeitung. Fehlt die Angabe, wird der letzte Widerruf unterschieden;
Foto- und Werbeeinwilligungen verändern den allgemeinen Stand nicht.

## Auskunft

Die Auskunft lädt eine JSON-Datei mit Personenstamm, wirksamen lokalen Konten
(ohne Passwort und Token) und den fachlich der Person zugeordneten Datensätzen:
Fremdschlüssel, Kindzeilen von Person und Konto sowie typgeprüfte Verweise, die
über Dokumenttyp plus Namen auf die Person zeigen (zum Beispiel Protokoll- und
Dateiverweise).

Bloße Autorenschaft oder Bearbeitung, Leitung oder Zuteilung ist **keine**
Zuordnung fremder Personeninhalte: `taetigkeiten` enthält dafür ausschließlich
Tabelle, Objektkennung und die eigenen Referenzfelder — niemals fremde
Stammdaten, Antworten aus dem Registrierungsverfahren, Protokollwerte oder
Nachrichteninhalte. Antworten und Kindzeilen werden nur für fachlich der Person
zugeordnete Anmeldungen ergänzt. Dateiinhalte werden nicht eingebettet;
Freitextnennungen ohne technische Zuordnung müssen gesondert geprüft werden.
Dies ist **kein** automatischer Volltext- oder Dateiscanner.

## Löschung (Anonymisieren)

Das Anonymisieren verlangt zwei Dialogschritte und das abgetippte Wort
`ANONYMISIEREN`. Der Server verlangt POST, `bestaetigt=true` und
`bestaetigung="ANONYMISIEREN"`.

Er überschreibt den Personenstamm, sperrt wirksame lokale Konten (über die
Kontoverknüpfung **und** über die eindeutige E-Mail-Adresse), entfernt deren
Passwort und widerruft alle Sitzungen. Historie, technische Kennungen,
Nachweise und Dateien bleiben bestehen. Aufbewahrungsfristen und
Freitextnennungen sind vorher manuell zu prüfen. In einem externen
Anmeldedienst (Authentik) wird nichts gelöscht.

Verwaltungskonten sind durch die vorhandenen Schranken geschützt;
insbesondere darf der letzte aktive Verwaltungszugang nicht verloren gehen.
Personenstamm, Kontensperre, Nachweis und Erledigung des Antrags werden
gemeinsam (atomar) gespeichert.

## Zusammenspiel mit dem Profil (N7)

```
POST /api/method/diakronos.diakonos.api.datenschutz.loeschung_beantragen
  {"bestaetigt": true}
```

Betrifft nur die eigene Person, es gibt kein `mitglied_id`-Argument und der
Aufruf ist je Person wiederholbar. Antwort: `{mitglied, beantragt_am,
status:"offen"}` in der üblichen `message`-Hülle. Kein Sofortwiderruf, keine
Änderung an Konto oder Personenstamm.

Für Administratoren liefert `datenschutz.get_loeschantraege` die offenen
Anträge mit Personennamen. `datenschutz.anonymisieren` mit `nur_antrag=true`
verlangt einen offenen Antrag und erledigt ihn zusammen mit der
Anonymisierung. Ohne `nur_antrag` lässt sich auch ein mündlich oder schriftlich
mitgeteilter Löschwunsch bearbeiten. Die Tabelle der Löschanträge ist bewusst
kein frei beschreibbarer Datensatz.

Im Profil verweigert die frühere Aktion „eigene Daten löschen“ jetzt mit
Hinweis auf den Löschantrag; eigene Auskunft und Antragsstand stehen dort
bereit. Einzelheiten: [N7-DATENSCHUTZ.md](N7-DATENSCHUTZ.md).
