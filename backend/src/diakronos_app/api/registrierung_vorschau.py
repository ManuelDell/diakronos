"""Formular-VORSCHAU fuer die Verwaltung (REG-1b).

Karte REG-1b, Punkt 3: „Vorschau-Knopf im Formular-Editor: zeigt das Formular
genau so, wie Besucher es sehen (gleiche Komponente wie die oeffentliche
Registrierungsseite, ohne Absenden).“

Zwei Fehler waeren hier die naheliegenden:

1. **Eigene Vorlage.** Eine zweite Anzeige im Editor driftet von der
   oeffentlichen Seite weg — genau der Befund, der die Vorschau erst noetig
   macht. Deshalb liefert dieser Endpunkt NUR DIE DATEN; angezeigt wird die
   Komponente ``registrierung/components/DkAnmeldeformular.vue``, dieselbe, die
   die oeffentliche Seite benutzt.
2. **Erfundene Angaben.** Felder, Beschreibung, Schalter und Bilder kommen
   aus dem gespeicherten Anmeldeformular (ein Aufruf mit ``formular_id``) oder
   — beim ersten Anlegen — aus den Angaben, die gerade im Editor stehen. Nichts
   wird geraten: fehlt das Formular, ist die Antwort leer.

Bilder: Die Vorschau kennt keinen Registrierungslink. Der Bildpfad der
oeffentlichen Seite haengt aber am Link-Token. Damit der angemeldete
Administrator sein Bild trotzdem sieht, wird ein EIGENER Vorschau-Token
gesetzt (``vorschau-<formular-id>``); ``_validate_token(admin=True)``
akzeptiert ihn nur fuer Administratoren und nur fuer ein vorhandenes Formular.
Der Token erscheint nicht in der Antwort, er steckt hoechstens im Bildpfad.
"""

from __future__ import annotations

from typing import Any

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.registry import whitelist

#: Pfadname der Endpunkte fuer die Oberflaeche (`apiCall('…get_formular_vorschau')`).
#: Ohne diesen Namen landet die Methode unter ihrem Python-Pfad
#: (`diakronos_app.api.…`) und die SPA findet sie nicht (404) — jede andere
#: Portierung dieses Projekts traegt ihn aus demselben Grund.
FRAPPE_MODULE = "diakronos.diakonos.api.registrierung_vorschau"

__all__ = [
    "PRAEFIX_VORSCHAU_TOKEN",
    "ist_vorschau_token",
    "get_formular_vorschau",
]

#: Praefix des Vorschau-Tokens fuer Formularbilder (REG-1b).
PRAEFIX_VORSCHAU_TOKEN = "vorschau-"


def ist_vorschau_token(token: Any) -> bool:
    """Ist das ein Vorschau-Token (`vorschau-<formular>`)? Kein Link-Token."""
    return str(token or "").startswith(PRAEFIX_VORSCHAU_TOKEN)


def _vorschau_token(formular_id: str) -> str:
    """Bild-Token der Vorschau: reiner Formularname hinter dem Praefix."""
    return f"{PRAEFIX_VORSCHAU_TOKEN}{formular_id}"


def _als_int(wert, vorgabe: int = 0) -> int:
    try:
        return int(wert or 0)
    except (TypeError, ValueError):
        return vorgabe


def _felder_aus_json(felder) -> list[dict]:
    """Feldliste aus der Anfrage (JSON-String oder Liste) -> Anzeigeform.

    Dieselbe Form, die `registrierung._formular_felder` liefert — nur ohne
    Datenbank, weil die Vorschau auch ungespeicherte Aenderungen zeigen muss.
    """
    import json

    if isinstance(felder, str):
        try:
            felder = json.loads(felder or "[]")
        except (TypeError, ValueError):
            felder = []
    if not isinstance(felder, list):
        return []
    ergebnis: list[dict] = []
    for zeile in felder:
        if not isinstance(zeile, dict):
            continue
        label = str(zeile.get("label") or "").strip()
        if not label:
            continue
        ergebnis.append(
            {
                "label": label,
                "feldtyp": zeile.get("feldtyp") or "Text",
                "optionen": zeile.get("optionen") or "",
                "pflichtfeld": 1 if _als_int(zeile.get("pflichtfeld")) else 0,
                "fuer_gaeste": 1 if _als_int(zeile.get("fuer_gaeste")) else 0,
                "fuer_kinder": 1 if _als_int(zeile.get("fuer_kinder")) else 0,
            }
        )
    return ergebnis


@whitelist(allow_guest=False)
def get_formular_vorschau(
    formular_id: str = "",
    felder: Any = None,
    mit_kinder: Any = None,
    mit_gaesten: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Daten der Formular-Vorschau (nur Mitgliederadministratoren).

    Zwei Betriebsarten:

    * ``formular_id`` gesetzt -> Werte des GESPEICHERTEN Formulars
      (Banner, Hintergrund, Beschreibung, Felder). Das ist der Normalfall der
      Vorschau aus dem Editor.
    * ohne ``formular_id`` -> die Angaben aus dem Editor selbst
      (``felder``, ``mit_kinder``, ``mit_gaesten``); so laesst sich ein noch
      nicht gespeichertes Formular ansehen.

    Zusaetzlich werden die Texte der oeffentlichen Seite mitgegeben
    (Einwilligung/Datenschutz, Willkommenstext) — die Vorschau zeigt denselben
    Wortlaut, den die Person spaeter bestaetigt.

    Rueckgabeform ist die von ``window.__diakronos`` der oeffentlichen Seite:
    die Komponente braucht keine Umrechnung.
    """
    # Rollenpruefung wie ueberall in der Verwaltung (`require_admin` ->
    # `_has_admin_role`): dieselbe Pruefung, die auch das Bearbeiten des
    # Formulars verlangt. Kein stiller leerer Kasten — die Vorschau zeigt
    # Besucherdaten und ist damit Verwaltungssache.
    from diakronos_app.frappe_compat.permissions import require_admin

    require_admin()

    from diakronos_app import spa
    from diakronos_app.api.registrierung import _formular_felder

    formular_id = str(formular_id or "").strip()
    beschreibung = str(kwargs.get("beschreibung") or "")

    if formular_id:
        from diakronos_app.frappe_compat.api_helpers import get_doc

        doc = get_doc("Anmeldeformular", formular_id)
        if doc is None:
            raise ValidationError("Anmeldeformular nicht gefunden.")
        # DERSELBE Weg wie die oeffentliche Anzeige (eine Quelle):
        # `_formular_felder` liest Felder, Schalter, Beschreibung und Bilder.
        link = {"anmeldeformular": doc.name, "slug": _vorschau_token(doc.name)}
        daten = _formular_felder(link, token=_vorschau_token(doc.name))
        kopf_bezeichnung = doc.get("bezeichnung") or doc.name
    else:
        daten = {
            "felder": _felder_aus_json(felder),
            "mit_kinder": 1 if _als_int(mit_kinder) else 0,
            "mit_gaesten": 1 if _als_int(mit_gaesten) else 0,
            "beschreibung": "",
            "banner_bild": "",
            "hintergrund_bild": "",
        }
        kopf_bezeichnung = ""

    # REG-1b: Der Editor zeigt die ungespeicherte Beschreibung, sobald sie im
    # Feld steht — sonst waere die Vorschau beim Tippen veraltet.
    from diakronos_app.anmeldung.formularbilder import normalisiere_beschreibung

    if beschreibung.strip():
        daten["beschreibung"] = normalisiere_beschreibung(beschreibung)

    daten.update(
        {
            "bezeichnung": kopf_bezeichnung,
            "texte": spa.oeffentliche_texte(),
            "willkommenstext": spa._willkommenstext(),
        }
    )
    return daten
