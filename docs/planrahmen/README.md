# Plan-Rahmen — Dokumentation (Verweis)

Die Dokumentation des Plan-Rahmens liegt **im Python-Paket**, nicht hier:
das Repo-Verzeichnis `docs/` steht in `.dockerignore` und fehlt im Docker-Image.
Alle zur Laufzeit und in Tests benoetigten Dateien werden daher mit dem Paket
ausgeliefert und ueber `importlib.resources` gelesen.

Paketpfad: `backend/src/diakronos_app/planrahmen/doku/`

| Datei | Zweck |
|---|---|
| `LEITFADEN.md` | Prinzipien + Bausteine in Prosa, „wann nehme ich was?“ |
| `KONZEPT.md` | das vollstaendige Konzept (P1–P12, Beispiele C1/C2) |
| `AGENT-ONBOARDING.md` | Fragenkatalog und Fallen fuer den Onboarding-Agenten |
| `KOCHBUCH.md` | Uebersicht ueber die geprueften Beispiele |
| `REFERENZ.md` | **generiert** aus Schema + Registries (nicht von Hand aendern) |
| `GLOSSAR.md` | verbindliche Wortwahl und Anrede der Oberflaeche (Standard S15) |
| `kochbuch/*.json` | gepruefte Beispiel-Plantypen (Chor, Freizeit, Prediger, Programm, …) |
| `instanzen/*.json` | Beispiel-Instanzdaten (konkrete Eintraege, geprueft via `eintraege.py`) |

Die `REFERENZ.md` wird mit `python3 backend/scripts/planrahmen_doku.py` neu
erzeugt; ein Test prueft, dass die eingecheckte Fassung aktuell ist.
