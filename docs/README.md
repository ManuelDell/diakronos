# Dokumentenindex

Alle Dokumente in `docs/`, je Dokument ein Satz und die Zielgruppe. Das
Projekt-README mit Installation und Betrieb liegt im Repo-Wurzelverzeichnis:
[../README.md](../README.md).

## Betrieb und Anwendung

| Dokument | Worum es geht | Zielgruppe |
|---|---|---|
| [BETRIEBSANLEITUNG.md](BETRIEBSANLEITUNG.md) | Installation, Anmeldung, Sperren und Notweg, Oberfläche, Sicherheit im Betrieb, Dev-Modus, Datensicherung, HTTPS/Domain und nginx-Umstellung (Abschnitt 10), Anmeldung über Authentik (Abschnitt 11). | Betreiber |
| [N6-DATENSCHUTZ.md](N6-DATENSCHUTZ.md) | Datenschutz-Verwaltung: Einwilligungen, Auskunft als JSON-Ausfuhr, Löschung auf Antrag, Sichtbarkeiten. | Betreiber (Mitgliederadministratoren, System Manager) |
| [N7-DATENSCHUTZ.md](N7-DATENSCHUTZ.md) | Profilseite aus Sicht des Mitglieds: eigene Daten einsehen, Einwilligungen erteilen und widerrufen. | Betreiber und Mitglieder |

## Entwicklung

| Dokument | Worum es geht | Zielgruppe |
|---|---|---|
| [ENTWICKLER-README.md](ENTWICKLER-README.md) | Aufbau, Arbeitsweise, Code-Regeln, offene Punkte und der Weg zur Veröffentlichung. | Entwickler |
| [GOOGLE-IMPORT.md](GOOGLE-IMPORT.md) | Einstieg und Überblick zum Kalenderimport (iCal und Google) mit Verweisen auf G1a, G1b und G2. | Betreiber und Entwickler |
| [G1A-GOOGLE-IMPORT.md](G1A-GOOGLE-IMPORT.md) | iCal-Upload, verschlüsselte Google-Zugangsdaten, Zeitvertrag. | Entwickler |
| [G1B-GOOGLE-OAUTH.md](G1B-GOOGLE-OAUTH.md) | OAuth, Google-API, Import als Hintergrundauftrag, Callback, Cloud-Console-Anleitung. | Entwickler (Cloud-Console-Teil auch Betreiber) |
| [G2-KALENDER-IMPORT.md](G2-KALENDER-IMPORT.md) | Die Importseite `#/kalender/import`, Browser-Prüfung, Betriebs-Gate. | Entwickler |
| [planrahmen/README.md](planrahmen/README.md) | Verweis: die Plan-Rahmen-Dokumentation (Leitfaden, Konzept, Kochbuch, Referenz) liegt im Python-Paket. | Entwickler |

## Lesereihenfolge

**Betreiber, der installiert**

1. [../README.md](../README.md): Installation, `.env`, erster Administrator, HTTPS.
2. [BETRIEBSANLEITUNG.md](BETRIEBSANLEITUNG.md): Abschnitte 2 (erste Schritte), 3 und 4 (Anmeldung, Sperren), 8.9 (vor dem Internet-Betrieb).
3. [BETRIEBSANLEITUNG.md](BETRIEBSANLEITUNG.md) Abschnitt 10 (HTTPS), bei bestehendem HTTP-Stack 10.6.
4. Bei Kalenderimport: BETRIEBSANLEITUNG 5.6, dann [GOOGLE-IMPORT.md](GOOGLE-IMPORT.md).
5. Datenschutz und Löschung: [N6-DATENSCHUTZ.md](N6-DATENSCHUTZ.md) und [N7-DATENSCHUTZ.md](N7-DATENSCHUTZ.md).
6. Bei Problemen: BETRIEBSANLEITUNG Abschnitt 7 und 10.5.

**Entwickler, der einsteigt**

1. [ENTWICKLER-README.md](ENTWICKLER-README.md): die drei Sätze am Anfang, dann Abschnitte 1 bis 3 (Aufbau, Arbeiten, Code-Regeln).
2. ENTWICKLER-README Abschnitt 4 (offene Punkte), 5 (Veröffentlichen) und 6 (Dokumentationsindex).
3. [BETRIEBSANLEITUNG.md](BETRIEBSANLEITUNG.md) zum Verständnis des Betriebsverhaltens.
4. Je nach Thema: [GOOGLE-IMPORT.md](GOOGLE-IMPORT.md) mit [G1a](G1A-GOOGLE-IMPORT.md), [G1b](G1B-GOOGLE-OAUTH.md), [G2](G2-KALENDER-IMPORT.md); Kalender-Anbindung: BETRIEBSANLEITUNG Abschnitt 6; HTTPS: BETRIEBSANLEITUNG Abschnitt 10; Plan-Rahmen: [planrahmen/README.md](planrahmen/README.md).
