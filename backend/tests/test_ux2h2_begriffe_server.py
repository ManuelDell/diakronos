"""UX2h2 — Begriffe: die Texte des Servers ziehen nach.

Die Oberfläche war in UX2h/UX3a auf die verbindlichen Begriffe umgestellt
(„Prüfen“ statt „Moderation“, „Website-Baukasten“ statt „Primo“). Der Server
lieferte an mehreren Stellen weiter die alten Wörter — und genau diese Texte
sieht der Nutzer ZUERST, weil die Oberfläche `meldung` bevorzugt anzeigt.

Was dieser Test festhält:

1. **Meldungen** — jedes Rückgabefeld `meldung` und jede geworfene Meldung
   (HTTPException/ValidationError/FrappePermissionError …) der geprüften
   Module nennt die alten Wörter nicht mehr. Geprüft wird der QUELLTEXT der
   Nutzertexte über den AST: `throw(<Text>)`, `meldung=<Text>` und
   `…["meldung"] = <Text>` — Kommentare und Docstrings sind ausdrücklich
   erlaubt (technische Erklärungen dürfen „Primo“ sagen).
2. **Bezeichnungen** — der Suchtreffer für die Website-Einstellungen heißt
   „Website-Baukasten“, die DSGVO-Zeilengründe nennen keine „Moderation“.
3. **Technik bleibt Technik** — `logger.*`, Klassennamen (`PrimoAbgelehnt`),
   Feldnamen (`is_moderator`) und die Adapter (`website/primo.py`) sind NICHT
   betroffen; der Test würde sie sonst fälschlich anzeigen.

Rot war das vor der Karte: `moderation.py` sagte „Terminmoderation“,
`series.py` ebenfalls, `kanban_api.py`/`moderation.py` warfen „Keine
Moderationsrechte fuer Kalender …“, `suche.py` zeigte „Website (Primo)“,
`website.py` und `bausteine.py` meldeten „Primo“.

Läuft IM Image (`backend/Dockerfile`, Testliste der Python-Suite) und liest
nur das Python-Paket — keine Datenbank, kein Netz.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "diakronos_app"

#: Ältere Bezeichnungen, die in NUTZERTEXTEN nicht mehr stehen dürfen.
#: `Moderation` deckt „Terminmoderation“, „Moderationsrechte“, „Kalender-
#: Moderation“ mit ab; `Primo` deckt „Website (Primo)“ ab.
ALTE_WOERTER = ("Moderation", "Primo", "Moderationsrecht")

#: Nutzertexte stehen in diesen Bausteinen — der Rest (Logs, Kommentare,
#: Adapter-Namen) ist Technik und bleibt.
GEPRUEFTE_MODULE = (
    "api/kronos/moderation.py",
    "api/kronos/series.py",
    "api/kronos/kanban_api.py",
    "api/kronos/event_crud.py",
    "api/kronos/permissions.py",
    "api/kronos/ressource_api.py",
    "api/suche.py",
    "api/website.py",
    "api/dashboard.py",
    "api/ressourcen.py",
    "dsgvo_anonymisierung.py",
    "website/bausteine.py",
)


def _baum(pfad: Path) -> ast.Module:
    return ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))


def _text(wert: ast.AST) -> str | None:
    """Statischer Text eines Ausdrucks — auch aus f-Strings und `+`-Ketten."""
    if isinstance(wert, ast.Constant) and isinstance(wert.value, str):
        return wert.value
    if isinstance(wert, ast.JoinedStr):
        teile = [
            t.value for t in wert.values
            if isinstance(t, ast.Constant) and isinstance(t.value, str)
        ]
        return "".join(teile) if teile else None
    if isinstance(wert, ast.BinOp) and isinstance(wert.op, ast.Add):
        links, rechts = _text(wert.left), _text(wert.right)
        if links is None and rechts is None:
            return None
        return (links or "") + (rechts or "")
    return None


def _diskussions_position(knoten: ast.AST) -> int:
    return getattr(knoten, "lineno", 0)


def _nutzertexte(pfad: Path) -> list[tuple[int, str]]:
    """Alle Textstellen, die als Meldung an den Nutzer gehen.

    Erkannt werden:
      * `throw(<Text>` — Meldung einer Ausnahme (erstes Argument),
      * `meldung=<Text>` — Rückgabefeld,
      * `<…>["meldung"] = <Text>` — Rückgabefeld per Zuweisung,
      * `hinweis=<Text>` — Klartext-Feld der Antwort (`website/bausteine.py`).
    """
    gefunden: list[tuple[int, str]] = []
    for knoten in ast.walk(_baum(pfad)):
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name) \
                and knoten.func.id == "throw" and knoten.args:
            text = _text(knoten.args[0])
            if text:
                gefunden.append((_diskussions_position(knoten), text))
        if isinstance(knoten, ast.Call):
            for schluessel in knoten.keywords:
                if schluessel.arg in ("meldung", "hinweis"):
                    text = _text(schluessel.value)
                    if text:
                        gefunden.append((_diskussions_position(knoten), text))
        if isinstance(knoten, ast.Assign) and isinstance(knoten.value, ast.AST):
            for ziel in knoten.targets:
                if isinstance(ziel, ast.Subscript):
                    schluessel = ziel.slice
                    if isinstance(schluessel, ast.Constant) \
                            and schluessel.value in ("meldung", "hinweis"):
                        text = _text(knoten.value)
                        if text:
                            gefunden.append((_diskussions_position(knoten), text))
        if isinstance(knoten, ast.AnnAssign) and isinstance(knoten.target, ast.Subscript):
            schluessel = knoten.target.slice
            if isinstance(schluessel, ast.Constant) \
                    and schluessel.value in ("meldung", "hinweis"):
                text = _text(knoten.value) if knoten.value is not None else None
                if text:
                    gefunden.append((_diskussions_position(knoten), text))
    return gefunden


@pytest.mark.parametrize("modul", GEPRUEFTE_MODULE)
def test_ux2h2_keine_alten_begriffe_in_nutzertexten(modul):
    """Jede Meldung/allgemein sichtbare Textstelle nennt die alten Wörter nicht."""
    pfad = SRC / modul
    assert pfad.exists(), f"Modul fehlt: {modul}"
    verstoesse = [
        (zeile, text, wort)
        for zeile, text in _nutzertexte(pfad)
        for wort in ALTE_WOERTER
        if wort.lower() in text.lower()
    ]
    assert not verstoesse, (
        f"{modul}: alte Begriffe in Nutzertexten (Zeile, Text, Wort): "
        + "; ".join(f"{z}: {t!r} -> {w}" for z, t, w in verstoesse)
    )


def test_ux2h2_wachend_erkannte_stellen():
    """Der Wächter sieht überhaupt Meldungen — sonst ist er blind grün."""
    texte = [t for _, t in _nutzertexte(SRC / "api/kronos/moderation.py")]
    assert any("wartet auf Freigabe" in t for t in texte), texte


def test_ux2h2_wartende_aenderung_meldung():
    """Die Meldung der wartenden Änderung sagt „geprüft“, nicht „Terminmoderation“."""
    texte = [t for _, t in _nutzertexte(SRC / "api/kronos/moderation.py")]
    meldung = [t for t in texte if "wartet auf Freigabe" in t]
    assert meldung, "Meldung der wartenden Änderung fehlt"
    assert any("geprüft" in t for t in meldung), meldung


def test_ux2h2_fehlendes_pruefrecht_sagt_was_jetzt():
    """Statt „Keine Moderationsrechte fuer Kalender X“ sagt der Text, was fehlt."""
    for modul in ("api/kronos/moderation.py", "api/kronos/kanban_api.py"):
        pfad = SRC / modul
        roh = pfad.read_text(encoding="utf-8")
        assert "fehlt dir das Recht, Termine zu prüfen" in roh, f"{modul}: erklärender Text fehlt"
        assert "Keine Moderationsrechte fuer" not in roh, modul


def test_ux2h2_suchtreffer_website_baukasten():
    """Die Befehlspalette findet die Website-Einstellungen unter dem neuen Namen."""
    from diakronos_app.api.suche import _EINSTELLUNGEN

    titel = [titel for _, titel, _ in _EINSTELLUNGEN]
    assert "Website-Baukasten" in titel, titel
    assert not [t for t in titel if "Primo" in t], titel


def test_ux2h2_dsgvo_gruende_ohne_moderation():
    """Die Gründe der Zeilenlöschung sind für Betroffene lesbar (kein Jargon)."""
    from diakronos_app.dsgvo_anonymisierung import ZEILEN_LOESCHEN

    for tabelle, grund in ZEILEN_LOESCHEN:
        for wort in ALTE_WOERTER:
            assert wort.lower() not in grund.lower(), f"{tabelle}: Grund nennt „{wort}“ — {grund}"


def test_ux2h2_technik_darf_primo_sagen():
    """Klassennamen und Adapter sind Technik — sie bleiben unverändert."""
    adapter = (SRC / "website" / "primo.py").read_text(encoding="utf-8")
    assert "class PrimoAbgelehnt" in adapter, "Adapter-Klasse umbenannt — bitte prüfen"
