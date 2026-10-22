"""Deklaration (registry) und Logik (auswertung) der Regel-Bausteine.

Die Deklaration (``registry.py``) beschreibt, WAS es gibt (Bausteine,
Feldarten, Fuellstrategien) und versorgt Pruefung und Dokumentation. Die Logik
(``auswertung.py``) wertet die Bausteine zur Laufzeit aus (Engine, P2). Beide
haengen ueber denselben Schluessel zusammen.
"""

from .registry import (
    FELDARTEN,
    FUELLSTRATEGIEN,
    REGEL_BAUSTEINE,
    Feldart,
    Fuellstrategie,
    RegelBaustein,
    alle_bausteine,
    bekannte_bausteine,
    bekannte_feldarten,
    bekannte_fuellstrategien,
    eingebaute_attribute_lieder,
    eingebaute_attribute_person,
    eingebaute_attribute_sammlung,
    eingebaute_attribut_schluessel,
    hole_baustein,
    logik_fabrik,
    registriere_logik,
)
from .auswertung import (
    REGEL_LOGIK,
    Kontext,
    bewerte,
    bewerte_alle,
    muster_passt,
    pruefe_plan,
    regeln_mit_strategie,
    stufe_der_regel,
)

__all__ = [
    "FELDARTEN",
    "FUELLSTRATEGIEN",
    "REGEL_BAUSTEINE",
    "REGEL_LOGIK",
    "Kontext",
    "Feldart",
    "Fuellstrategie",
    "RegelBaustein",
    "alle_bausteine",
    "bekannte_bausteine",
    "bekannte_feldarten",
    "bekannte_fuellstrategien",
    "bewerte",
    "bewerte_alle",
    "eingebaute_attribute_lieder",
    "eingebaute_attribute_person",
    "eingebaute_attribute_sammlung",
    "eingebaute_attribut_schluessel",
    "hole_baustein",
    "logik_fabrik",
    "muster_passt",
    "pruefe_plan",
    "regeln_mit_strategie",
    "registriere_logik",
    "stufe_der_regel",
]
