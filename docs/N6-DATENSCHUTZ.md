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

## Aufbewahrungsfristen (Verzeichnis der Verarbeitungstätigkeiten)

Art. 30 DSGVO verlangt nicht nur „was geschieht mit den Daten“, sondern auch
**wie lange** sie bleiben — und eine Frist, die niemand durchsetzt, ist keine
Frist. Die folgende Tabelle ist deshalb die lesbare Fassung des Inventars
(`backend/src/diakronos_app/dsgvo_anonymisierung.py`, `AUFBEWAHRUNG_FRISTEN`)
und wird automatisch durchgesetzt: täglich um 00:00 UTC durch den
Scheduler-Job `chat_aufbewahrung` (`chat_aufbewahrung.aufraeumen()`).

| Daten | Frist | Einstellbar | Gemessen ab |
|---|---|---|---|
| Gruppengespräche (Nachrichten, Reaktionen, Lesestände, Teilnahmen, Glocken-Merker) | **24 Monate** (Standard) | ja, `chat_frist_gruppe_monate` (1…120) | letzte Nachricht im Gespräch; ohne Nachrichten ab Anlage |
| Direktgespräche und Runden | **12 Monate** (Standard) | ja, `chat_frist_direkt_monate` (1…120) | letzte Nachricht im Gespräch; ohne Nachrichten ab Anlage |
| Text gelöschter/entfernter Nachrichten | **6 Monate**, dann endgültig leer | nein | Zeitpunkt der Löschung |
| Stimmenzeilen offener Umfragen | **6 Monate**, dann gelöscht (Zähler bleibt) | nein | Schließung der Umfrage |
| Meldungen | **12 Monate** nach Abschluss | nein | Entscheidung der Moderation |

**Wer darf die Fristen ändern.** Nur Administratoren (Entscheidung F8 in
`docs/konzepte/CHAT-KONZEPT.md` §9) — geprüft über den zentralen Rechte-Kern
(`rechte.ist_admin`), nicht über eine eigene Rollenlogik. Moderationsrechte
(HV/MV/GL) genügen ausdrücklich **nicht**: die Frist ist eine Zusage der
Gemeinde an alle ihre Mitglieder, keine Einstellung einer Gruppe.

```
chat.fristen_lesen()                                    jedes angemeldete Konto
chat.fristen_speichern(chat_frist_gruppe_monate=…,      nur Administrator (POST)
                       chat_frist_direkt_monate=…)
```

**Was der Löschlauf nicht tut.** Er löscht kein Gespräch, das noch
Nachrichten innerhalb der Frist hat; er leert keinen Text, der noch nicht
gelöscht ist; er entfernt keine offene Meldung (sie wartet auf eine
Entscheidung) und keine Stimme einer noch laufenden Umfrage.

**Offene Meldung setzt die Frist aus.** Solange zu einer Nachricht des
Gesprächs eine Meldung **offen** ist, wird das Gespräch nicht gelöscht — die
Meldestelle braucht den Ausschnitt, über den sie entscheiden soll. Nach der
Entscheidung greift die Frist beim nächsten Lauf. (Entschiedene Meldungen
halten nichts fest.)

**Kein toter Link in der Glocke.** Chat-Benachrichtigungen
(`document_type` `chat_gespraech` / `chat_nachricht` / `chat_meldung`), die auf
ein gelöschtes Ziel zeigen, werden **gelöscht**, nicht entkoppelt: eine Glocke
ohne Ziel führt in keinen Verlauf und hätte keinen Zweck mehr. Die Bedingung
ist je `document_type` als `NOT EXISTS` formuliert, es wird keine Namensliste
geladen. Benachrichtigungen anderer Bereiche bleiben unberührt.

**Was der Löschlauf nicht kann.** Er ersetzt die Anonymisierung (Art. 17)
nicht: er entfernt Daten nach Ablauf der Frist, er beantwortet keinen
Löschwunsch und keine Auskunft. Die Fristen gelten unabhängig davon.
