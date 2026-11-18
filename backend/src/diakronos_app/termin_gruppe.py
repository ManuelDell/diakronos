"""`Element.gruppe` folgt dem Kalender — EINE Stelle statt je Schreibweg.

BEFUND (BUG-T1, Manuel 17.11.)
------------------------------
`Element.gruppe` (`models/kronos.py`, FK -> `gruppe.name`, also NUR
Hauptgruppen) wurde von KEINEM Schreibweg gesetzt: `create_event`,
`create_series`, `save_event`, `update_event`, der Google-/iCal-Import und
`_create("Element", …)` nahmen das Feld nicht an, die Oberfläche schickt es
nicht. Gelesen wird es trotzdem — `planrahmen/datenquelle_db.py`
(``gruppe=e.gruppe``), `planrahmen/engine/datenquelle.py`
(``kalender_termine(gruppe=…)``) und die Ersatzregel in
`api/gruppen.py::get_gruppe_termine`. Auf Bestandsterminen war es leer.

DIE ENTSCHEIDUNG (Manuel 17.11.): Diakronos setzt das Feld automatisch aus
dem Kalender.

DIE REGEL
---------
  * `gruppe` = Gruppe des Kalenders aus dem Rechtesystem
    (``rechte_objekt`` mit ``typ='kalender'``, ``objekt=<kalender>``:
    ``gruppe``). Bei einem UNTERGRUPPEN-Kalender steht dort bereits die
    HAUPTgruppe (``untergruppe`` nennt die Untergruppe) — genau das verlangt
    der FK, der nur ``gruppe.name`` zulässt.
  * Hat der Kalender KEINE Gruppe (Gemeinde-Kalender, Kalender ganz ohne
    ``rechte_objekt``-Zeile, leere ``gruppe``), wird NICHTS gesetzt: ein
    ausdrücklich mitgegebener Wert bleibt stehen, ein vorhandener Wert der
    Zeile bleibt stehen, beim Anlegen ohne Angabe bleibt die Spalte leer.
    Begründung (Review 17.11.): eine fehlende Kalenderzuordnung ist KEINE
    Aussage darüber, dass der Termin zu keiner Gruppe gehört — sie ist nur
    keine Angabe. Werte zu löschen wäre Datenverlust (Altbestand aus der Zeit
    vor dieser Regel, Sonderfälle wie ein bewusst gesetzter Vertretungstermin
    in einem Nachbarkalender). Die Regel ergänzt, sie löscht nicht.
  * Hat der Kalender eine Gruppe, ist der KALENDER die Wahrheit: eine
    abweichend mitgegebene ``gruppe`` wird überschrieben. ``gruppe`` ist eine
    ABGELEITETE Angabe („zu welcher Gruppe gehört dieser Termin“), keine
    Eingabe; zwei Quellen für dieselbe Angabe laufen sonst auseinander
    (Regression BUG-T1: das Feld war auf jedem Termin leer, obwohl der
    Kalender die Zuordnung kennt).
  * Kalenderwechsel auf einen Kalender MIT Gruppe -> neue Gruppe.
    Kalenderwechsel auf einen Kalender OHNE Gruppe -> Wert bleibt; ein
    ausdrücklich mitgegebenes ``gruppe`` gewinnt dann (der Aufrufer sagt,
    wohin der Termin gehört, der Zielkalender sagt es nicht).

WARUM KEIN `before_flush` (obwohl die Karte das vorschlägt)
-----------------------------------------------------------
Die Schreibwege laufen NICHT alle über eine einzige Sitzung: `_create` baut
die Zeile als `Element(**data)` (ORM), der Google-/iCal-Import ebenfalls
(`db.add(Element(...))`), `/api/resource` in `frappe_compat/router.py`
schreibt mit eigener `SessionLocal()`-Sitzung. Ein `before_flush` müsste in
`db.SessionLocal` registriert sein, sonst ist er wirkungslos — und Tests wie
der Google-Import bauen ihre Sitzung selbst (`sessionmaker(...)`), ein
sitzungsgebundenes Ereignis liefe dort gar nicht. Deshalb sitzt die Regel in
`ergaenze_gruppe`, einer reinen Funktion, die ALLE Schreibwege aufrufen, und
zwar VOR dem Anlegen/Setzen der Zeile:

  * `frappe_compat/api_helpers._create`   — `create_event`, `create_series`,
    Kanban, `frappe.client.insert`, jeder Weg über `_create("Element", …)`,
  * `api/kronos/google_import._create_element_from_dict` — Google und iCal,
  * `frappe_compat/api_helpers._update_doc` — Kalenderwechsel (`save_event`,
    `update_event`, Kanban-Umhängen); ohne Kalenderwechsel keine Abfrage,
  * `frappe_compat/router._apply_resource_write` — `/api/resource/{Element}`
    (POST und PUT) schreibt mit eigener Sitzung und läuft NICHT über
    `_create`.

Wege an der ORM vorbei (rohes SQL) gibt es nicht — geprüft per grep über
`src/`, `tests/` und `tools/` (`INSERT INTO element`, `UPDATE element`,
`insert(`/`update(` auf `Element`): kein Treffer. Die Migration
`tg1_element_gruppe_kalender` trägt den Bestand nach und fasst dabei nur
LEERE Werte an.

NICHT überschrieben: eine Zeile, die schon existiert und deren
`element_calendar` sich NICHT ändert, wird nicht angefasst — ein reines
`set_value({"status": …})` (Kanban-Freigabe) löst weder Abfrage noch
Neuberechnung aus.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

__all__ = ["kalendergruppe", "ergaenze_gruppe", "KALENDER_TYP"]

#: `typ` der Kalender-Zeile im EINEN Rechtesystem (`RechteObjekt`).
KALENDER_TYP = "kalender"


def kalendergruppe(session: Session, kalender: str | None) -> str | None:
    """Hauptgruppe des Kalenders aus `rechte_objekt` (None = ohne Zuordnung).

    Gelesen wird in DER Sitzung, in der geschrieben wird — keine zweite
    Verbindung mitten in einer Transaktion (SQLite teilt im Test EINE
    Verbindung, PostgreSQL sieht ungeflushte Zeilen einer Fremdsitzung nicht).
    """
    if not kalender:
        return None
    from diakronos_app.models.rechte import RechteObjekt

    wert = session.scalar(
        select(RechteObjekt.gruppe).where(
            RechteObjekt.typ == KALENDER_TYP,
            RechteObjekt.objekt == str(kalender),
        )
    )
    text = str(wert or "").strip()
    return text or None


def ergaenze_gruppe(
    session: Session,
    werte: dict[str, Any],
    *,
    vorher: str | None = None,
    kalender_geaendert: bool = True,
) -> dict[str, Any]:
    """`werte` um die ABGELEITETE ``gruppe`` ergänzen (Anlegen/Ändern).

    ``vorher`` ist der Kalender der BESTEHENDEN Zeile — der Aufrufer erkennt
    daran, ob sich der Kalender ändert (``kalender_geaendert``).
    ``kalender_geaendert=False`` lässt `werte` unberührt: dann hat der
    Aufrufer den Kalender nicht angefasst und die Ableitung ist schon
    geschehen (spart eine Abfrage je `set_value`).

    Gesetzt wird NUR, wenn der Kalender eine Gruppe hat. Sonst bleibt ein in
    `werte` mitgegebener Wert stehen — der Aufrufer setzt dann keinen
    bestehenden Wert der Zeile. Die Rückgabe ist ein NEUES Dict.
    """
    if not kalender_geaendert:
        return werte
    ausgabe = dict(werte)
    ziel = kalendergruppe(session, ausgabe.get("element_calendar"))
    if ziel is None:
        # Kalender ohne Gruppenzuordnung: keine Aussage — ein von Hand
        # gesetzter Wert bleibt. AUSNAHME Verschieben: kam die Gruppe aus dem
        # ALTEN Kalender (der eine Gruppe hatte), war sie abgeleitet und folgt
        # dem Kalender — sonst stuende der Termin weiter auf der alten
        # Gruppenseite (Review 18.11.).
        if "gruppe" not in werte and kalendergruppe(session, vorher) is not None:
            ausgabe["gruppe"] = None
        return ausgabe
    ausgabe["gruppe"] = ziel
    return ausgabe
