"""UX1j — „Gestaltung“-Einstellungen: die EINE Positivliste der einstellbaren Tokens.

Warum es dieses Paket gibt
--------------------------
Manuel will Abstände, Ränder, Rahmen und Radien in den Einstellungen
bearbeiten (und zurücksetzen) können — aber **nur** diese. Farben, Schriften
und Klickflächen bleiben unangetastet: Farben tragen die Bedeutung (Status,
Kontrast, Hell/Dunkel), Schriften die Lesbarkeit, und die Klickfläche ist eine
Barrierefreiheits-Zusage (44 px bei Touch). Wer sie „einstellbar“ macht, macht
sie abschaltbar.

Deshalb steht hier eine **geschlossene Liste** (`TOKENS`) und nichts anderes.
Was nicht in ihr steht, kommt weder in die Datenbank noch in das ausgelieferte
CSS. Das ist die einzige Stelle, an der ein neues einstellbares Maß eingetragen
wird.

Aufbau
------
* `tokens.py` — Positivliste mit Bereich, Einheit und Skalen-Gruppe; Prüfung
  eines Wertes und der aufsteigenden Skala.
* `speicher.py` — Tabelle `gestaltung_abweichung` (Lesen, Schreiben,
  Zurücksetzen) und das CSS der Abweichungen.
* `api.py` — die drei Endpunkte `gestaltung.lesen/.speichern/.zuruecksetzen`.
* `route.py` — die öffentliche Route `{Präfix}/gestaltung.css`.

Vertrag für UX1k (Oberfläche)
-----------------------------
`gestaltung.lesen` liefert die Felder mit `token`, `standard`, `einheit`,
`min`, `max`, `schritt`, `gruppe` und `wert` — die Oberfläche braucht keine
eigene Liste. `gestaltung.speichern` nimmt `{token: wert}` (px-Zahl oder
`"16px"`), `gestaltung.zuruecksetzen` optional ein einzelnes `token`.
"""

from __future__ import annotations

__all__ = ["tokens", "speicher", "api", "route"]
