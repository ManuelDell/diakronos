"""AUFR-1 — Waechter: Uebergabe- und Abnahme-Arbeitsnotizen gehoeren nicht ins Repo.

Regel 17 (Hermes-Board, 08.11.): Uebergabe-Notizen (``*-UEBERGABE.md``),
Abnahme-Arbeitsprotokolle (``abnahme*.txt``) und Wegwerf-Skripte werden als
Kartenkommentar bzw. im Scratch abgelegt — NICHT im Repo.

Der Test liest den Git-Index (``git ls-files``) der Repo-Wurzel, damit auch
eine gerade hinzugefuegte, aber noch nicht committete Notiz auffaellt. Ist git
nicht verfuegbar oder liegt der Test ausserhalb eines Repos, entfaellt die
Pruefung mit Begruendung (SKIP) — im Image laeuft sie ueber ``backend/`` im
Repo-Checkout mit.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]

# Pfade, die mit AUFR-1 entfernt wurden. Kommen sie zurueck, ist die Karte
# rueckgaengig gemacht worden — das faellt hier auf, ohne dass jemand die
# Board-Historie lesen muss.
ENTFERNT = (
    "BS2A-UEBERGABE.md",
    "BS2B-UEBERGABE.md",
    "BS2C-UEBERGABE.md",
    "ROUTE-LIFECYCLE-UEBERGABE.md",
    "ST1-UEBERGABE.md",
    "ST2-UEBERGABE.md",
    "UI2-UEBERGABE.md",
    "docs/g2-abnahme/abnahme.txt",
    "tools/abnahme-b3/cleanup-final.txt",
)

# Dauerhafte Abnahme-Doku (verschoben). Ihre Existenz ist gewollt.
ABLAGE = ("docs/abnahmen/A1C11-ABNAHME.md", "docs/abnahmen/G3-HTTPS-ABNAHME.md")


def _versionierte_dateien() -> list[str]:
    try:
        ergebnis = subprocess.run(
            ["git", "-C", str(WURZEL), "ls-files", "--cached", "--others",
             "--exclude-standard", "-z"],
            check=True, capture_output=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        # Ohne git (Test-Container): Dateisystem der Wurzel prüfen statt zu überspringen.
        if not (WURZEL / "backend").is_dir():
            pytest.skip("Repo-Wurzel nicht vorhanden — Waechter uebersprungen")
        return [p.relative_to(WURZEL).as_posix() for p in WURZEL.rglob("*")
                if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts]
    pfade = ergebnis.stdout.decode("utf-8").split("\0")
    return [p for p in pfade if p]


def _ist_uebergabe_in_wurzel(pfad: str) -> bool:
    """``*-UEBERGABE.md`` direkt in der Repo-Wurzel (auch klein geschrieben)."""
    return "/" not in pfad and pfad.lower().endswith("-uebergabe.md")


def test_keine_uebergabedatei_in_der_repo_wurzel() -> None:
    treffer = [p for p in _versionierte_dateien() if _ist_uebergabe_in_wurzel(p)]
    assert not treffer, (
        "Uebergabe-Notizen gehoeren nicht ins Repo (Regel 17) — als Kartenkommentar "
        f"ablegen: {treffer}"
    )


def test_entfernte_arbeitsnotizen_bleiben_entfernt() -> None:
    dateien = set(_versionierte_dateien())
    zurueck = [p for p in ENTFERNT if p in dateien]
    assert not zurueck, f"AUFR-1 rueckgaengig gemacht? wieder versioniert: {zurueck}"


def test_abnahme_doku_liegt_in_der_ablage() -> None:
    dateien = set(_versionierte_dateien())
    for pfad in ABLAGE:
        assert pfad in dateien, f"Abnahme-Doku fehlt in der Ablage: {pfad}"
    assert (WURZEL / "docs" / "abnahmen" / "README.md").is_file(), \
        "docs/abnahmen/README.md erklaert die Ablage"


def test_export_schliesst_die_ablage_aus() -> None:
    """Das Protokoll ist Doku im Repo, aber nicht im oeffentlichen Export (PUB-1)."""
    ausschluss = WURZEL / "tools" / "oeffentlich" / "ausschluss.txt"
    if not ausschluss.is_file():
        pytest.skip("tools/oeffentlich/ liegt nicht im Checkout")
    regeln = [
        z.strip() for z in ausschluss.read_text(encoding="utf-8").splitlines()
        if z.strip() and not z.strip().startswith("#")
    ]
    assert "docs/abnahmen/" in regeln, "Export-Regel fuer docs/abnahmen/ fehlt"
