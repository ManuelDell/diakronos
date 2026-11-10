"""BEZIEHUNGEN (DEV-B4a) — Personen zueinander eintragen und entfernen.

Befund DMB-72325633c6b5 (Dev-Modus 29.10.): `MitgliedDetail.vue` zeigte den
Reiter „Beziehungen" nur lesend (`mitglieder.get_beziehungen_for_mitglied`);
im Bearbeitungsmodus konnte man nichts eintragen und nichts entfernen. Der
Altcode pflegte Beziehungen ueber `doc.append("beziehungen", …)` und einen
`on_update`-Hook (`Mitglied._sync_beziehungen`,
`referenz/diakronos-frappe/…/doctype/mitglied/mitglied.py:227-276`). Im
Standalone-Backend gibt es keinen Doc-Hook — diese Datei ist der Weg.

REGELN (Kartenanforderung, je Regel ein Test in
`backend/tests/test_devb4a_beziehungen.py`)

  * **Nur die Verwaltung** (Review 10.11.): alle drei Endpunkte — auch der
    LESENDE `get_beziehungen_auswahl` — pruefen zuerst
    `permissions.require_admin()` (Rollen `Mitgliederadministrator` /
    `System Manager`), dieselbe Schranke wie `admin_einwilligung_setzen`
    (DEV-B4b). Ein normales Mitglied bekommt 403, auch fuer sein eigenes
    Profil: die Auswahl zaehlt ALLE waehlbaren Personen des Bestands auf und
    ginge damit an der `ancestor_path`-Sichtbarkeit vorbei, und Eintragen
    schreibt eine Zeile BEI DER ANDEREN Person (sonst koennte sich jeder als
    Ehepartner einer beliebigen Person eintragen). Der Reiter „Beziehungen"
    ist in der Oberflaeche ebenfalls nur fuer die Verwaltung sichtbar.
  * **CSRF**: alle schreibenden Funktionen `@whitelist(methods=["POST"])` —
    ohne POST prueft die CSRF-Schicht den Kopf nicht (`main.py`).
  * **Audit-Protokoll**: jede Aenderung steht in `Audit Log`
    (`api.audit.log`, wie `ressourcen._audit_entscheidung`). Ein Fehler im
    Protokoll macht die bereits gespeicherte Aenderung nicht kaputt.
  * **Gegenrichtung automatisch**: A→B „Kind" bedeutet B→A „Elternteil"
    (Abbildung wie im Altcode, `_INVERSE`); die gespiegelte Zeile traegt
    `ist_spiegel=1` und wird vom Endpunkt selbst gepflegt.
  * **Beziehung ist symmetrisch** (Review 10.11.): existiert zwischen den
    beiden Personen schon irgendeine Zeile — gleiche Richtung, Gegenrichtung,
    auch eine dort SELBST eingetragene Zeile ohne Spiegel-Marke —, wird
    nichts angelegt. Bei gleicher Art heisst es „besteht bereits"; bei
    anderer Art „besteht bereits von der anderen Seite als …". Damit gibt es
    je Personenpaar genau EINE Aussage, und „Entfernen" darf und muss beide
    Richtungen abraeumen (sonst bliebe eine halbe Beziehung stehen).
  * **Keine Selbstbeziehung**: A→A wird abgelehnt.

„Entfernen" raeumt BEIDE Richtungen ab — die Zeile bei der Zielperson
(ziel→quelle) geht immer mit, unabhaengig von `ist_spiegel`: eine haengende
Gegenrichtung waere eine Beziehung, die nur noch auf einer Seite steht (der
Altcode haette sie ueber `_sync_beziehungen` nie wieder aufgeloest). Die
Ruecknahme („Zuruecknehmen", UX2c) bietet die Oberflaeche an — dafuer gibt es
kein eigenes Zeitfenster: die Zeile ist wieder anlegbar, solange niemand sonst
etwas geaendert hat.
"""

from __future__ import annotations

from typing import Any

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.beziehungen"

from diakronos_app.frappe_compat import get_all, get_value, whitelist
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.api_helpers import (
    _create,
    _delete_doc,
    _new_name,
    _now,
    column_names,
    log_error,
)
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    PermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.session import session

#: Erlaubte Beziehungsarten — dieselbe Liste wie `_INVERSE` im Altcode
#: (`doctype/mitglied/mitglied.py:20-26`). Eine freie Eingabe gaebe es dort
#: nicht (Select-Feld), und die Gegenrichtung waere sonst „Sonstiges" ohne
#: Bedeutung.
BEZIEHUNGSARTEN: tuple[str, ...] = (
    "Elternteil",
    "Kind",
    "Ehepartner",
    "Geschwister",
    "Sonstiges",
)

#: A→B vom Typ X bedeutet B→A vom Typ Y (Altcode `_INVERSE`, 1:1).
INVERS: dict[str, str] = {
    "Elternteil": "Kind",
    "Kind": "Elternteil",
    "Ehepartner": "Ehepartner",
    "Geschwister": "Geschwister",
    "Sonstiges": "Sonstiges",
}

_CHILD_FELDER = (
    "name", "creation", "modified", "modified_by", "owner", "docstatus",
    "idx", "beziehung_zu", "beziehungstyp", "ist_spiegel",
    "parent", "parentfield", "parenttype",
)


def _zeilen(parent: str) -> list[dict[str, Any]]:
    """Alle Beziehungszeilen einer Person (in `idx`-Reihenfolge)."""
    return get_all(
        "Mitglied Beziehung",
        filters={"parent": parent, "parenttype": "Mitglied"},
        fields=list(_CHILD_FELDER),
        order_by="idx asc",
    ) or []


def _name_von(mitglied_id: str) -> str:
    """Anzeigename einer Person, sonst ihre Kennung (nie leer)."""
    row = get_value("Mitglied", mitglied_id, ["vorname", "nachname"], as_dict=True)
    if not row:
        return str(mitglied_id)
    teile = [str(row.get("vorname") or "").strip(), str(row.get("nachname") or "").strip()]
    return " ".join(t for t in teile if t) or str(mitglied_id)


def _pruefe_verwaltung() -> None:
    """Nur die Verwaltung — dieselbe Schranke wie `admin_einwilligung_setzen`.

    `permissions.require_admin()` prueft die Rollen `Mitgliederadministrator`
    und `System Manager` (Review 10.11.). Sie GILT AUCH fuer das Lesen
    (`get_beziehungen_auswahl`): die Liste zaehlt alle waehlbaren Personen auf
    und ginge sonst an der `ancestor_path`-Sichtbarkeit vorbei.
    """
    permissions.require_admin()


def _pruefe_mitschrift(mitglied_id: str, quelle: str, art: str) -> None:
    """Darf `quelle` die Beziehungszeile von `mitglied_id` sehen?

    `get_mitglied_detail` kuerzt den Anzeigenamen ausgetretener
    Beziehungspartner (AUSTRITT A3). Wer eine neue Zeile eintraegt, muss
    dieselbe Grenze halten — sonst liesse sich der Klarname einer
    ausgetretenen Person ueber „Beziehung hinzufuegen" abfragen.
    """
    from diakronos_app.frappe_compat.personen_anzeige import ist_ausgeschieden

    ziel = get_value(
        "Mitglied", mitglied_id,
        ["name", "vorname", "nachname", "ausgeschlossen", "status", "austritt_datum"],
        as_dict=True,
    )
    if not ziel:
        throw(f"Mitglied {mitglied_id!r} nicht gefunden.", DoesNotExistError)
    if not ist_ausgeschieden(ziel):
        return
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import darf_vertrauliches_sehen

    if not darf_vertrauliches_sehen(mitglied_id):
        throw(
            "Diese Person ist ausgetreten — eine Beziehung zu ihr lässt sich hier "
            "nicht eintragen.",
            PermissionError,
        )


def _audit(aktion: str, mitglied_id: str, beschreibung: str) -> None:
    """Audit-Eintrag zur Aenderung (Beiwerk — Fehler stoppen nichts)."""
    try:
        from diakronos_app.api.audit import log as _audit_log

        _audit_log("Profiländerung", "Mitglied", mitglied_id, f"{aktion}: {beschreibung}")
    except Exception as ex:  # noqa: BLE001 — Protokoll ist Beiwerk
        log_error(str(ex), "beziehungen_audit")


def _anlegen(mitglied_id: str, ziel: str, art: str, *, spiegel: bool) -> str:
    """Eine Beziehungszeile schreiben und ihre Kennung zurueckgeben."""
    naechster_idx = max((int(z.get("idx") or 0) for z in _zeilen(mitglied_id)), default=0) + 1
    return _create(
        "Mitglied Beziehung",
        {
            "name": _new_name(),
            "parent": mitglied_id,
            "parenttype": "Mitglied",
            "parentfield": "beziehungen",
            "beziehung_zu": ziel,
            "beziehungstyp": art,
            "ist_spiegel": 1 if spiegel else 0,
            "idx": naechster_idx,
            "docstatus": 0,
            "creation": _now(),
            "modified": _now(),
            "owner": session.user,
            "modified_by": session.user,
        },
    )


def _lese_argumente(mitglied_id, person_id, beziehungsart) -> tuple[str, str, str]:
    """Parameter pruefen und normalisieren (Strings, getrimmt)."""
    quelle = str(mitglied_id or "").strip()
    ziel = str(person_id or "").strip()
    art = str(beziehungsart or "").strip()
    if not quelle or not ziel:
        throw("Bitte eine Person auswählen.", ValidationError)
    if not art:
        throw("Bitte eine Beziehungsart auswählen.", ValidationError)
    if art not in BEZIEHUNGSARTEN:
        throw(
            "Unbekannte Beziehungsart. Möglich sind: "
            + ", ".join(BEZIEHUNGSARTEN) + ".",
            ValidationError,
        )
    return quelle, ziel, art


# ── Endpunkte ───────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_beziehungen_auswahl(mitglied_id, suche=""):
    """Personen fuer „Beziehung eintragen": `[{mitglied, name, in_beziehung}]`.

    Dieselbe Auswahlliste wie „Mitglied hinzufügen" in einer Gruppe
    (`api.gruppen_auswahl.waehlbare_mitglieder`): nur Menschen, die
    aufgenommen werden koennen (keine Ausgetretenen/Verstorbenen), gesucht
    wird in Vor-/Nachname — nicht in der E-Mail (B-1: die E-Mail ist ein
    Adressbuch-Feld und kein Suchfeld).

    Die abgefragte Person selbst erscheint NICHT (Selbstbeziehung) und
    Personen, zu denen schon eine Beziehung besteht, tragen
    `in_beziehung=True` (Hinweis in der Liste, kein Fehler beim Klick).

    Recht: NUR die Verwaltung (`_pruefe_verwaltung`). Die Liste zaehlt alle
    waehlbaren Personen des Bestands auf und ginge an der
    `ancestor_path`-Sichtbarkeit vorbei — lesend oder nicht.
    """
    quelle = str(mitglied_id or "").strip()
    if not quelle:
        throw("mitglied_id fehlt.", ValidationError)
    _pruefe_verwaltung()
    if get_value("Mitglied", quelle, "name") is None:
        throw(f"Mitglied {quelle!r} nicht gefunden.", DoesNotExistError)

    from diakronos_app.api.gruppen_auswahl import waehlbare_mitglieder

    vorhanden = {str(z.get("beziehung_zu")) for z in _zeilen(quelle)}
    ergebnis = []
    for person in waehlbare_mitglieder(suche=str(suche or ""), limit=0):
        kennung = str(person.get("mitglied") or "")
        if not kennung or kennung == quelle:
            continue
        ergebnis.append({
            "mitglied": kennung,
            "name": person.get("name") or kennung,
            "in_beziehung": kennung in vorhanden,
        })
    return {"success": True, "data": ergebnis}


@whitelist(methods=["POST"], allow_guest=False)
def add_beziehung(mitglied_id, person_id, beziehungsart):
    """Beziehung eintragen — mit Gegenrichtung, ohne Doppelung.

    Antwort: `{success, beziehung, gegenrichtung, bestand}`.
    `bestand=True` heisst: die Beziehung gab es schon (die vorhandene Zeile
    steht in `beziehung`, es wurde nichts angelegt).

    Eine Beziehung ist SYMMETRISCH (Review 10.11.): gibt es zwischen den
    beiden Personen schon irgendeine Zeile — in diese Richtung, als Gegen-
    richtung oder als eigenhaendig eingetragene Zeile der anderen Seite —,
    wird nichts angelegt. Gleiche Art: „besteht bereits"; andere Art:
    „besteht bereits von der anderen Seite als …".
    """
    quelle, ziel, art = _lese_argumente(mitglied_id, person_id, beziehungsart)
    _pruefe_verwaltung()
    if get_value("Mitglied", ziel, "name") is None:
        throw("Die gewählte Person wurde nicht gefunden.", DoesNotExistError)
    if quelle == ziel:
        throw("Eine Person kann keine Beziehung zu sich selbst haben.", ValidationError)

    # Die ZIELPERSON ist eine andere Person — ihr Name darf nur gelesen
    # werden, wenn sie nicht ausgetreten ist (AUSTRITT A3).
    _pruefe_mitschrift(ziel, quelle, art)

    eigene = [z for z in _zeilen(quelle) if str(z.get("beziehung_zu")) == ziel]
    fremde = [z for z in _zeilen(ziel) if str(z.get("beziehung_zu")) == quelle]

    # Eigene Zeile schon da: gleiche Art = Doppelung, andere Art = zweite
    # Wahrheit („Ehepartner" UND „Geschwister") — beides wird abgelehnt.
    # Eine SPIEGEL-Zeile (ist_spiegel=1) stammt dagegen aus einem Eintrag der
    # Gegenseite: dann nennt die Meldung, was dort steht.
    if eigene:
        zeile = eigene[0]
        vorhandene_art = str(zeile.get("beziehungstyp"))
        if not bool(zeile.get("ist_spiegel")):
            if vorhandene_art == art:
                throw(f"Die Beziehung besteht bereits („{vorhandene_art}“).",
                      ValidationError)
            throw(
                f"Die Beziehung besteht bereits („{vorhandene_art}“) — bitte sie "
                "zuerst entfernen.",
                ValidationError,
            )
        # Spiegel-Zeile: die Aussage steht bei der anderen Person — dort lautet
        # sie INVERS[typ] (A→B „Kind" heisst bei B „Elternteil").
        eigene_art_gegenseite = INVERS.get(vorhandene_art, vorhandene_art)
        # Verglichen wird in DIESER Sicht: die Spiegelzeile hat dieselbe
        # Blickrichtung wie der neue Eintrag (quelle→ziel).
        if vorhandene_art == art:
            throw(
                f"Die Beziehung besteht bereits von der anderen Seite als "
                f"„{eigene_art_gegenseite}“.",
                ValidationError,
            )
        throw(
            f"Zwischen beiden Personen besteht bereits eine Beziehung von der "
            f"anderen Seite als „{eigene_art_gegenseite}“ — bitte sie zuerst "
            "entfernen.",
            ValidationError,
        )

    # Gegenrichtung steht schon da (auch eigenhaendig von der anderen Seite
    # eingetragen, also ohne Spiegel-Marke): keine zweite Zeile.
    if fremde:
        andere_art = str(fremde[0].get("beziehungstyp"))
        if andere_art == INVERS[art]:
            throw(
                f"Die Beziehung besteht bereits von der anderen Seite als "
                f"„{andere_art}“.",
                ValidationError,
            )
        throw(
            f"Zwischen beiden Personen besteht bereits eine Beziehung von der "
            f"anderen Seite als „{andere_art}“ — bitte sie zuerst entfernen.",
            ValidationError,
        )

    # Gegenzeile ziel→quelle anlegen; sie gehoert diesem Eintrag.
    gegen_art = INVERS[art]
    name_gegen = _anlegen(ziel, quelle, gegen_art, spiegel=True)
    gegenrichtung = {"name": name_gegen, "beziehung_zu": quelle,
                     "beziehungstyp": gegen_art, "ist_spiegel": 1}

    name = _anlegen(quelle, ziel, art, spiegel=False)
    zeile = {
        "name": name,
        "parent": quelle,
        "beziehung_zu": ziel,
        "beziehung_zu_name": _name_von(ziel),
        "beziehungstyp": art,
        "ist_spiegel": 0,
    }
    _audit("Beziehung eingetragen", quelle,
           f"„{art}“ zu {_name_von(ziel)} ({ziel})")
    return {
        "success": True,
        "beziehung": zeile,
        "gegenrichtung": gegenrichtung,
        "bestand": False,
    }


@whitelist(methods=["POST"], allow_guest=False)
def remove_beziehung(mitglied_id, beziehung_name):
    """Eine Beziehungszeile entfernen — samt Gegenrichtung.

    Die Kennung ist die Zeile AUS DER ANSICHT von `mitglied_id` (die SPA
    schickt `b.name`); eine Zeile einer anderen Person wird verweigert, damit
    niemand ueber geratene Kennungen fremde Beziehungen loescht.

    Die Gegenzeile ziel→quelle geht IMMER mit (Review 10.11.: die Beziehung
    ist symmetrisch) — auch wenn sie dort eigenhaendig eingetragen wurde.
    Sonst bliebe eine halbe Beziehung stehen.

    Antwort: `{success, entfernt: [{name, beziehung_zu, beziehungstyp}],
    wiederherstellbar: {beziehung_zu, beziehungsart}}` — die Angaben genuegen,
    um dieselbe Beziehung wieder einzutragen („Zuruecknehmen", UX2c).
    """
    quelle = str(mitglied_id or "").strip()
    zeile_name = str(beziehung_name or "").strip()
    if not quelle or not zeile_name:
        throw("mitglied_id und beziehung_name sind erforderlich.", ValidationError)
    _pruefe_verwaltung()

    zeile = next((z for z in _zeilen(quelle) if str(z.get("name")) == zeile_name), None)
    if zeile is None:
        throw("Diese Beziehung gibt es nicht (mehr) — bitte die Seite neu laden.",
              DoesNotExistError)

    ziel = str(zeile.get("beziehung_zu") or "")
    art = str(zeile.get("beziehungstyp") or "")
    entfernt = [{
        "name": str(zeile.get("name")),
        "beziehung_zu": ziel,
        "beziehungstyp": art,
    }]

    # Gegenrichtung: jede Zeile BEI DER ANDEREN PERSON, die auf diese zeigt.
    # Sie geht IMMER mit (die Beziehung ist symmetrisch) — unabhaengig davon,
    # ob `add_beziehung` sie als Spiegel angelegt hat oder ob die andere Seite
    # sie eigenhaendig eingetragen hat. Eine halbe Beziehung waere keine
    # Aussage mehr.
    if ziel:
        for gegen in _zeilen(ziel):
            if str(gegen.get("beziehung_zu")) == quelle:
                entfernt.append({
                    "name": str(gegen.get("name")),
                    "beziehung_zu": quelle,
                    "beziehungstyp": str(gegen.get("beziehungstyp") or ""),
                })

    for eintrag in entfernt:
        _delete_doc("Mitglied Beziehung", eintrag["name"])

    _audit("Beziehung entfernt", quelle,
           f"„{art}“ zu {_name_von(ziel)} ({ziel})"
           + (" samt Gegenrichtung" if len(entfernt) > 1 else ""))
    return {
        "success": True,
        "entfernt": entfernt,
        "wiederherstellbar": {"beziehung_zu": ziel, "beziehungsart": art},
    }


__all__ = [
    "INVERS",
    "FRAPPE_MODULE",
    "get_beziehungen_auswahl",
    "add_beziehung",
    "remove_beziehung",
    "BEZIEHUNGSARTEN",
]
