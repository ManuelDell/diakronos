"""DSGVO-1b: der Wächter über die Verweise auf Mitglied und Konto.

WARUM DIESER TEST EXISTIERT
--------------------------
Die Umhängung auf die neutrale Kennung (`dsgvo_anonymisierung.verweise()`)
leitet ihre Spaltenliste aus den SQLAlchemy-Metadaten ab. Das ist nur dann
sicher, wenn JEDE Fremdschlüssel-Spalte auf `mitglied.name` bzw. `user.name`
auch eine Entscheidung im Inventar hat — sonst zeigt nach der Löschung ein
Verweis ins Leere (oder die Löschung scheitert am Constraint, R-DSGVO-1, K3:
`ressourcen_buchung.moderiert_von` und `ablaufplan_position.verantwortlicher`
fehlten genau dort).

Kommt künftig eine FK dazu, schlägt dieser Test fehl — und die Entscheidung
gehört in die Karte, die das Feld einführt, nicht in die Löschroutine.
"""
from __future__ import annotations

import pytest

from diakronos_app import dsgvo_anonymisierung as modul


def _fks() -> dict[str, list[tuple[str, str]]]:
    return modul.verweise()


def test_jede_fk_auf_mitglied_oder_user_ist_versorgt():
    """Jede FK auf `mitglied.name`/`user.name` hat eine Inventar-Entscheidung."""
    offen = []
    for ziel, paare in _fks().items():
        for tabelle, spalte in paare:
            if ziel == "user" and tabelle in modul.KONTO_ZEILEN:
                continue  # Zeile wird gelöscht, der Verweis verschwindet mit ihr
            art = modul.SPALTEN.get(tabelle, {}).get(spalte, (None, None))[0]
            if art is None:
                offen.append(f"{tabelle}.{spalte} (FK auf {ziel}.name)")
    assert offen == [], (
        "Fremdschlüssel ohne DSGVO-Entscheidung in dsgvo_anonymisierung.SPALTEN:\n  "
        + "\n  ".join(sorted(offen))
    )


def test_die_fk_liste_ist_nicht_leer():
    """Gegenprobe: die Ableitung aus den Metadaten liefert wirklich Spalten."""
    fks = _fks()
    assert len(fks["mitglied"]) >= 20, fks["mitglied"]
    assert len(fks["user"]) >= 10, fks["user"]


@pytest.mark.parametrize("tabelle,spalte", [
    # Die beiden Posten, die in R-DSGVO-1 (K3) gefehlt haben:
    ("ressourcen_buchung", "moderiert_von"),
    ("ablaufplan_position", "verantwortlicher"),
])
def test_die_gefehlten_posten_sind_erfasst(tabelle, spalte):
    """K3: genau die zwei Spalten, an denen die Löschung abbrach."""
    assert (tabelle, spalte) in _fks()["user"] + _fks()["mitglied"]
    art = modul.SPALTEN[tabelle][spalte][0]
    assert art in ("mitglied", "user_null", "user_platzhalter"), art


def test_wert_spalten_nennen_nur_existierende_spalten():
    """Ein Tippfehler in `WERT_SPALTEN` würde eine echte Spalte still übergehen."""
    from diakronos_app.models.base import Base

    vorhanden = {(m.local_table.name, c.name)
                 for m in Base.registry.mappers for c in m.local_table.c}
    fehlend = [f"{t}.{s}" for t, spalten in modul.WERT_SPALTEN.items()
               for s in spalten if (t, s) not in vorhanden]
    assert fehlend == [], f"WERT_SPALTEN nennt unbekannte Spalten: {fehlend}"


def test_neue_kennung_ist_kein_name():
    """`geloescht-<hex>` ist eine technische Kennung, kein Personenbezug."""
    import re

    kennung = modul.neue_kennung()
    assert re.fullmatch(r"geloescht-[0-9a-f]{32}", kennung), kennung
    assert kennung != modul.neue_kennung(), "Kennung muss zufällig sein"
