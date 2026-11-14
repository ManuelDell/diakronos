"""R-10: Was bewirkt welche Rolle? — EINE Quelle fuer die Erklaerungen (ⓘ).

Manuel (Rechte-Gespraech): „was ich schlecht fand, war das unklar war was
welche rolle bewirkt. da wäre eine infomöglichkeit gut.“ Die Texte stehen
HIER neben dem Rechte-Kern, damit Oberflaeche (ⓘ, Seite „Rollen & Rechte“)
und Pruefung nicht auseinanderlaufen. Ein Test vergleicht die Schluessel mit
``kern.SYSTEMROLLEN`` und ``kern.MODULE``.
"""

from __future__ import annotations

from diakronos_app.rechte import kern

#: Systemrollen (Benutzerverwaltung). Schluessel = Rollenname in ``Has Role``.
SYSTEMROLLEN: dict[str, dict[str, object]] = {
    "System Manager": {
        "titel": "Administrator",
        "kurz": "Darf als Einzige(r) alles.",
        "darf": [
            "Gruppen anlegen und ihre erste Hauptverantwortliche bzw. ihren ersten Hauptverantwortlichen bestimmen",
            "Module je Gruppe festlegen (Kalender, Beiträge, Wiki, Aufgaben, Lieder, Dienstpläne)",
            "Inhalte für die ganze Gemeinde anlegen",
            "alle Freigaben, Rollen und Einstellungen ändern",
        ],
        "darf_nicht": [],
    },
    kern.SYSTEMROLLEN["mitgliederverwaltung"]: {
        "titel": "Mitgliederverwaltung",
        "kurz": "Pflegt Personen und ihre Daten — nicht die Gruppen.",
        "darf": ["Mitglieder anlegen, bearbeiten, ausschließen", "alle Personendaten sehen",
                 "Konten, Registrierung und Datenschutz-Anfragen bearbeiten"],
        "darf_nicht": ["Gruppen anlegen oder löschen", "Rollen in Gruppen vergeben",
                       "Inhalte für die ganze Gemeinde anlegen",
                       "Gemeinde-Einstellungen und Papierkorb verwalten"],
    },
    kern.SYSTEMROLLEN["kalender_moderation"]: {
        "titel": "Kalender-Moderation",
        "kurz": "Prüft, was für die ganze Gemeinde sichtbar wird, und pflegt Gemeinde-Kalender.",
        "darf": ["Gemeinde-Kalender anlegen und pflegen",
                 "Termine und Kalender-Freigaben „für alle Mitglieder der Gemeinde“ prüfen"],
        "darf_nicht": ["in Kalender einer Gruppe schreiben, die nicht für die Gemeinde freigegeben sind"],
    },
    kern.SYSTEMROLLEN["raumverwaltung"]: {
        "titel": "Raumverwaltung",
        "kurz": "Entscheidet über Raum- und Ressourcen-Anfragen.",
        "darf": ["Buchungen von Räumen und Ressourcen bestätigen oder ablehnen"],
        "darf_nicht": [],
    },
    kern.SYSTEMROLLEN["website_redaktion"]: {
        "titel": "Website-Redaktion",
        "kurz": "Pflegt, was auf der öffentlichen Website erscheint.",
        "darf": ["Inhalte für die Website freigeben"],
        "darf_nicht": [],
    },
    "Mitglied": {
        "titel": "Mitglied",
        "kurz": "Sieht die Namen aller Mitglieder und die Inhalte der eigenen Gruppen.",
        "darf": ["Inhalte der eigenen Gruppen lesen", "Termine im Kalender der eigenen Gruppen sehen",
                 "eigene Daten freigeben oder verbergen", "bei anderen „Daten anfragen“"],
        "darf_nicht": ["in Gruppen schreiben, ohne dass HV oder MV es freigeben"],
    },
}

GAST = {
    "titel": "Gast",
    "kurz": "Kein Konto — sieht genau einen Wiki-Artikel oder Beitrag über einen Link mit Passwort.",
    "darf": ["den freigegebenen Inhalt lesen, bis der Link abläuft (Standard 3 Tage)"],
    "darf_nicht": ["irgendetwas anderes sehen"],
}

#: Rollen in einer Gruppe (Manuel: „HV“ meint immer HV und MV — ausser beim Ernennen).
GRUPPENROLLEN: dict[str, dict[str, object]] = {
    "HV": {
        "titel": "Hauptverantwortliche(r) (HV)",
        "kurz": "Leitet die Gruppe. Genau eine Person je Gruppe.",
        "darf": ["alles, was die Module der Gruppe erlauben (anlegen, bearbeiten, prüfen)",
                 "Mitverantwortliche (MV) ernennen und entfernen",
                 "Gruppenleitungen der Untergruppen ernennen",
                 "Lesen/Schreiben/Moderieren an einzelne Personen freigeben (gilt sofort)",
                 "das HV-Amt mit Sicherheitsabfrage übertragen (wird danach MV)"],
        "darf_nicht": ["Module der Gruppe ändern (macht der Administrator)"],
    },
    "MV": {
        "titel": "Mitverantwortliche(r) (MV)",
        "kurz": "Darf alles wie die HV — außer HV und MV ernennen.",
        "darf": ["alles, was die Module der Gruppe erlauben", "Gruppenleitungen ernennen",
                 "Freigaben an Personen vergeben"],
        "darf_nicht": ["HV oder MV ernennen"],
    },
    "GL": {
        "titel": "Gruppenleitung (GL, Untergruppe)",
        "kurz": "Leitet eine Untergruppe; was an die Gruppe oder Gemeinde geht, prüfen zuerst HV/MV.",
        "darf": ["Kalender und Inhalte der Untergruppe anlegen und pflegen",
                 "Termine im Kalender der Gruppe vorschlagen"],
        "darf_nicht": ["in der Hauptgruppe direkt schreiben", "Moderationsrecht vergeben"],
    },
    "Mitglied": {
        "titel": "Gruppenmitglied",
        "kurz": "Liest, was die Gruppe teilt.",
        "darf": ["Inhalte der Gruppe lesen (wenn die Gruppe standardmäßig lesen darf)",
                 "eigene zugewiesene Aufgaben abhaken"],
        "darf_nicht": ["schreiben — außer HV/MV geben es frei"],
    },
}

MODULE: dict[str, str] = {
    "kalender": "Kalender der Gruppe: HV/MV legen an; Freigaben je Kalender (Lesen, Schreiben, Moderieren).",
    "beitraege": "Beiträge der Gruppe: HV/MV schreiben, Mitglieder lesen; einzeln oder per Gast-Link freigebbar.",
    "wiki": "Wiki der Gruppe: HV/MV schreiben, Mitglieder lesen; einzeln oder per Gast-Link freigebbar.",
    "aufgaben": "Aufgaben der Gruppe: HV/MV weisen zu; abhaken darf, wem die Aufgabe zugewiesen ist.",
    "lieder": "Lieder: HV/MV pflegen die Liedersammlung; wer das Modul in keiner Gruppe hat, sieht keine Lieder.",
    "dienstplaene": "Dienstpläne und Vorlagen: HV/MV erstellen und delegieren; den ganzen Plan sieht, wer im Kalender schreibt.",
}

STUFEN: dict[str, str] = {
    kern.STUFE_UNTERGRUPPE: "Leitung der Untergruppe (GL, HV/MV)",
    kern.STUFE_GRUPPE: "Gruppenleitung (HV/MV)",
    kern.STUFE_GEMEINDE: "Gemeinde-Moderation (Kalender-Moderation, Moderationsrecht am Kalender)",
}


#: Anzeigenamen (UI-R8: keine Titel im Frontend festschreiben).
MODUL_TITEL: dict[str, str] = {
    "kalender": "Kalender",
    "beitraege": "Beiträge",
    "wiki": "Wiki",
    "aufgaben": "Aufgaben",
    "lieder": "Lieder",
    "dienstplaene": "Dienstpläne",
}

STUFEN_TITEL: dict[str, str] = {
    kern.STUFE_UNTERGRUPPE: "Untergruppe",
    kern.STUFE_GRUPPE: "Gruppe",
    kern.STUFE_GEMEINDE: "Alle Mitglieder der Gemeinde",
}

#: Reihenfolge der Systemrollen auf der Seite „Rollen & Rechte“.
SYSTEMROLLEN_REIHENFOLGE: tuple[str, ...] = (
    "System Manager",
    kern.SYSTEMROLLEN["mitgliederverwaltung"],
    kern.SYSTEMROLLEN["kalender_moderation"],
    kern.SYSTEMROLLEN["raumverwaltung"],
    kern.SYSTEMROLLEN["website_redaktion"],
    "Mitglied",
)

#: Einleitungen der Abschnitte (eine Quelle, Begriffe nach Manuel 11.11.).
EINLEITUNGEN: dict[str, str] = {
    "systemrollen": "Systemrollen vergibt der Administrator in der Benutzerverwaltung. "
                    "Nur der Administrator darf alles; die übrigen Rollen sind Fachverwaltungen.",
    "gast": "Gäste haben kein Konto. Sie sehen genau einen freigegebenen Inhalt über einen Link mit Passwort.",
    "gruppenrollen": "Jede Gruppe hat genau eine Hauptverantwortliche bzw. einen Hauptverantwortlichen (HV) "
                     "und beliebig viele Mitverantwortliche (MV). Untergruppen haben eine Gruppenleitung (GL).",
    "module": "Welche Module eine Gruppe nutzt, legt der Administrator je Gruppe fest. "
              "HV und MV bearbeiten, Mitglieder lesen.",
    "stufen": "Was über die eigene Gruppe hinaus sichtbar werden soll, wird geprüft — zuerst von der "
              "Leitung, bei Inhalten für alle Mitglieder der Gemeinde danach von der Gemeinde-Moderation.",
}


def alles() -> dict:
    """Alle Erklaerungen in einer Antwort (fuer ⓘ und „Rollen & Rechte“)."""
    return {"systemrollen": SYSTEMROLLEN, "gast": GAST, "gruppenrollen": GRUPPENROLLEN,
            "module": MODULE, "stufen": STUFEN,
            "modul_titel": MODUL_TITEL, "stufen_titel": STUFEN_TITEL,
            "systemrollen_reihenfolge": list(SYSTEMROLLEN_REIHENFOLGE),
            "einleitungen": EINLEITUNGEN}
