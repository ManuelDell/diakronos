"""A1c3, Punkt 1: Es darf nur EINE Wahrheit fuer die Admin-Rollen geben.

`frappe_compat/permissions.py::ADMIN_ROLES` ist die Quelle. `spa.py` hatte
eine **zweite, eigene** Kopie und benutzte sie fuer `is_admin` im Boot-Objekt;
`erstinstallation.py::ADMIN_ROLLEN` eine dritte. Heute sind alle drei
identisch, deshalb ist es kein akuter Fehler — es ist eine stille Falle:

  Wer eine der Listen erweitert, bekommt ein Boot-Objekt mit falschem
  `is_admin`, ohne dass irgendwo ein Fehler auftritt. Genau die Sorte
  Abweichung, die in einer Permissions-Datei nicht passieren darf.

Gemessen am alten Stand: die Tests `test_spa_hat_keine_eigene_admin_rolle`
und `test_erstinstallation_hat_keine_eigene_admin_rolle` schlagen um, weil
beide Module eine eigene Konstante fuehren.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "diakronos_app"


def _zuweisungen(dateiname: str, name: str) -> dict[str, ast.expr] | None:
    """Alle `NAME = …`-Zuweisungen einer Datei auf Modulebene.

    Bewusst per AST statt `hasattr`: ein Re-Export (`from … import
    ADMIN_ROLES`) ist etwas anderes als eine eigene Definition, und genau
    diesen Unterschied muss dieser Test sehen koennen. Gibt `None` zurueck,
    wenn die Datei die Konstante gar nicht kennt.

    Nur einfache `name = wert` (kein Tuple-Packing, kein AnnAssign): alles
    andere waere in diesem Repo ohnehin eine Ueberraschung, und ein
    unerwartetes Muster soll hier als Fehler auffallen, nicht stillschweigend
    durchrutschen.
    """
    baum = ast.parse((SRC / dateiname).read_text(encoding="utf-8"))
    treffer: dict[str, ast.expr] = {}
    for knoten in baum.body:
        if not isinstance(knoten, ast.Assign) or len(knoten.targets) != 1:
            continue
        ziel = knoten.targets[0]
        if isinstance(ziel, ast.Name) and ziel.id == name:
            treffer[name] = knoten.value
    return treffer or None


# ── spa.py ─────────────────────────────────────────────────────────────────
#
# Der eigentliche Fund der Karte: `spa.py` benutzt die Liste fuer `is_admin`
# im Boot-Objekt, also fuer die Anzeige der Verwaltungs-Eintraenge. Eine
# eigene Kopie hier heisst: der Admin-Status kann im Boot-Objekt falsch sein,
# waehrend die API es richtig berechnet.


def test_spa_hat_keine_eigene_admin_rolle() -> None:
    """`spa.py` definiert `ADMIN_ROLES` nicht mehr selbst.

    Erlaubt ist ausschliesslich ein Re-Export aus `permissions` — dann ist die
    Sichtbarkeit des Namens erhalten (fuer Leser und Alt-Import), aber es
    gibt keine zweite Wahrheit mehr.
    """
    from diakronos_app.frappe_compat import permissions
    from diakronos_app import spa

    zuweisungen = _zuweisungen("spa.py", "ADMIN_ROLES")
    if zuweisungen is None:
        # Kein Name in spa.py: spa.py benutzt permissions.ADMIN_ROLES direkt
        # beim Aufruf. Das ist die schlichte Variante und ebenfalls gueltig.
        assert not hasattr(spa, "ADMIN_ROLES") or spa.ADMIN_ROLES is permissions.ADMIN_ROLES
        return

    # Es gibt genau eine Zuweisung — und die muss ein Re-Export sein.
    assert len(zuweisungen) == 1, f"spa.py definiert ADMIN_ROLES mehrfach: {zuweisungen}"
    wert = next(iter(zuweisungen.values()))
    assert isinstance(wert, ast.Name), (
        "spa.py darf ADMIN_ROLES nur per Re-Export aus permissions uebernehmen, "
        f"gefunden wurde ein {type(wert).__name__}-Ausdruck"
    )
    assert spa.ADMIN_ROLES is permissions.ADMIN_ROLES


def test_erstinstallation_hat_keine_eigene_admin_rolle() -> None:
    """`erstinstallation.py::ADMIN_ROLLEN` ist ebenfalls nur ein Re-Export.

    Hier geht es um eine andere Richtung: die Erstinstallation VERGIBT die
    Rollen. Eine eigene Liste hier bedeutet, dass sie einem Benutzer Rollen
    zuteilt, die `permissions` nicht als Admin kennt — der Benutzer waere
    dann weder Admin noch sichtbar als einer angelegt worden.
    """
    from diakronos_app.frappe_compat import permissions
    from diakronos_app import erstinstallation

    zuweisungen = _zuweisungen("erstinstallation.py", "ADMIN_ROLLEN")
    if zuweisungen is None:
        assert (
            not hasattr(erstinstallation, "ADMIN_ROLLEN")
            or erstinstallation.ADMIN_ROLLEN is permissions.ADMIN_ROLES
        )
        return

    assert len(zuweisungen) == 1, f"mehrfache ADMIN_ROLLEN: {zuweisungen}"
    wert = next(iter(zuweisungen.values()))
    assert isinstance(wert, ast.Name) and wert.id == "ADMIN_ROLES", (
        "ADMIN_ROLLEN muss ein Re-Export von permissions.ADMIN_ROLES sein"
    )
    # Und die tatsaechlich vergebenen Rollen muessen dieselben sein.
    assert set(erstinstallation.ADMIN_ROLLEN) == set(permissions.ADMIN_ROLES)


def test_alle_drei_stellen_nennen_dieselben_rollen() -> None:
    """Gegenprobe unabhängig vom Import-Mechanismus: die INHALTE stimmen.

    Die beiden Tests oben schaauen auf die Herkunft der Liste. Dieser hier
    vergleicht die tatsächlich im Lauf benutzten Werte — damit der Zusicherung
    auch dann noch etwas bedeutet, wenn jemand `spa.py` auf die eine oder
    andere Weise doch wieder umschreibt.
    """
    from diakronos_app.frappe_compat import permissions
    from diakronos_app import erstinstallation, spa

    erwartet = {"System Manager", "Mitgliederadministrator"}
    assert set(permissions.ADMIN_ROLES) == erwartet

    if hasattr(spa, "ADMIN_ROLES"):
        assert set(spa.ADMIN_ROLES) == erwartet
    if hasattr(erstinstallation, "ADMIN_ROLLEN"):
        assert set(erstinstallation.ADMIN_ROLLEN) == erwartet


# ── Was die Konstante bewirkt ─────────────────────────────────────────────
#
# Der Import-Mechanismus ist die halbe Sache. Der andere Test ist der
# End-to-End-Beweis: eine erweiterte `ADMIN_ROLES` muss sich im Boot-Objekt
# bemerkbar machen. Wuerde spa.py sie ignorieren, waere der Test oben gruen
# und das Boot-Objekt trotzdem falsch.


@pytest.mark.parametrize("rolle", ["System Manager", "Mitgliederadministrator"])
def test_rollenliste_wirkt_ueber_die_spa_in_den_boot(patched_db, monkeypatch, rolle: str):
    """Eine Admin-Rolle aus `permissions` ergibt `is_admin` im Boot-Objekt.

    Geprueft wird der Weg, um den es hier geht: `Has Role` -> `get_roles` ->
    `is_admin` im Boot-Objekt. Am alten Code schlug dieser Test nicht um
    (die Kopien waren identisch) — er haelt aber fest, dass die
    Vereinheitlichung diesen Weg nicht kaputtgemacht hat.
    """
    from diakronos_app.frappe_compat import permissions
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.spa import boot_fuer_request

    monkeypatch.setattr(permissions, "ADMIN_ROLES", (rolle,))

    sess = patched_db()
    try:
        sess.add(User(name="chef@example.org", email="chef@example.org", enabled=True))
        sess.add(HasRole(
            name="chef-SM", parent="chef@example.org", parenttype="User",
            parentfield="roles", role=rolle, docstatus=0, idx=1,
        ))
        sess.commit()
    finally:
        sess.close()

    from diakronos_app.frappe_compat import session

    try:
        session.user = "chef@example.org"
        assert boot_fuer_request()["is_admin"] is True
    finally:
        session.user = permissions.GUEST
