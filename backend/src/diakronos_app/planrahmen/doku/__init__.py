"""Dokumentation des Plan-Rahmens, die im Python-Paket mitgeliefert wird.

Dieses Unterpaket traegt die Dateien, die zur Laufzeit oder in Tests gebraucht
werden und deshalb IM Image vorhanden sein muessen (das Repo-Verzeichnis
``docs/`` steht in ``.dockerignore`` und fehlt im Container, siehe
NACHTRAG DOCKER). Konkret:

- die generierte Referenz ``REFERENZ.md`` (aus Schema + Registries),
- die handgeschriebenen Dokumente ``LEITFADEN.md``, ``KONZEPT.md``,
  ``AGENT-ONBOARDING.md`` und ``KOCHBUCH.md``,
- die geprueften Beispiele ``kochbuch/*.json`` (Plantypen) und
  ``instanzen/*.json`` (konkrete Eintraege eines Plans).

Der Zugriff erfolgt ausschliesslich ueber :mod:`importlib.resources` (siehe
:mod:`diakronos_app.planrahmen.ressourcen`), damit er sowohl bei der
Editable-Install im Image als auch bei einer Nicht-Editable-Install
(Package-Data, siehe ``pyproject.toml``) funktioniert — nie ueber Pfade
relativ zum Repo oder absolute Host-Pfade.
"""
