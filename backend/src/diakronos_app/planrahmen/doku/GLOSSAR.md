# Glossar der Oberfläche (Standard S15)

Verbindliche Wortwahl für alles, was Ehrenamtliche in Diakronos lesen.
Quelle im Code: `frontend/src/diakonos/components/ui/begriffe.mjs`
(Wächter: `frontend/tests/p3-1-begriffe.test.mjs`).

Zielgruppe sind Chorleiterinnen, Freizeitleiter, Musikteams und Mitglieder —
keine Software-Fachsprache, keine internen Kennungen im Text.

## Anrede

**„du“ überall.** Keine „Sie“-Form, kein „ihr“ für eine einzelne Person.
Ausnahme: In Aufzählungen darf „Sie“ als Fürwort für eine Sache stehen
(„Diese Angaben … Sie werden sofort gespeichert.“) — das ist kein Anredefall.

## Begriffe

| Statt … | heißt es | Bedeutung |
|---|---|---|
| Genehmigen, Bestätigen, Festlegen | **Freigeben** | Einen Vorschlag oder Termin verbindlich machen. |
| Anmeldung (für einen Antrag) | **Registrierung** | „Anmeldung“ ist NUR die Anmeldung mit Konto (Login). |
| Plantyp | **Planvorlage** | Die wiederverwendbare Vorlage eines Plans. |
| Dashboard | **Übersicht** | Die Startseite. |
| Merkmal | **Eigenschaft** | Eine Angabe, die eine Person oder ein Eintrag haben kann. |
| Vorschlag erzeugen, generieren | **Automatisch einteilen** | Die Engine füllt die Plätze nach den Regeln. |
| Vorschlag (als Ergebnis) | **Auswahl** | Was beim automatischen Einteilen herauskommt. |
| vorgeschlagen, Vorschlag (als Zustand) | **Wartet auf Freigabe** | Noch nicht verbindlich. |

## Verben für Schreiben

* **Anlegen** — etwas Neues erzeugen (Plan, Vorlage, Eintrag).
* **Speichern** — Änderungen an einem bestehenden Objekt übernehmen.
* **Veröffentlichen** — einen Plan für alle sichtbar machen.

## Produktname

Der Produktname ist **Diakronos** — festgelegt, nicht mehr wechselnd.
„Diakonos“ ist die alte Schreibweise und wird in der Oberfläche nicht mehr
verwendet.

## Menügruppen

Das Hauptmenü ist nach **Aufgaben** geschnitten, nicht nach Produktteilen:
Gemeinde · Termine & Dienste · Infos · Musik · Verwaltung.
Gruppen wie „Diakonos“ oder „Kronos“ gibt es in der Oberfläche nicht.

## Kennungen

Interne Kennungen (`1_weihnachtstag`, `d2cbfb42-5`, `FROHE_STUNDE`,
`gestaltung`) erscheinen nie im Text. Angezeigt wird immer der Anzeigename aus
dem Katalog (`Heiligabend`, `1. Weihnachtstag`, der Liedtitel, `Frohe Stunde`).
