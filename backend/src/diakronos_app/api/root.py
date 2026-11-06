"""ON-6: der erste Administrator ist ``root`` — Kennzeichnung, Schutz, Uebertragung.

WOZU EIN EIGENES API-MODUL
--------------------------
Die Karte verlangt in Punkt 3 einen EIGENEN Endpunkt fuer die Uebertragung:
„Uebertragung von root nur durch root selbst (eigener Endpunkt, POST,
Bestaetigung).“ Genau das ist ``root_uebertragen``. Der Endpunkt aendert nur
die root-Kennzeichnung — keine Rollen, keine Mitgliederdaten.

Endpunkte
---------
``status``            (GET)  — wer ist root, und bin ich es? (Oberflaeche)
``root_uebertragen``  (POST) — root an ein anderes Konto uebergeben.

Rechte
------
* ``status``: jede angemeldete Person sieht NUR die eigene Antwort; der Name
  des root ist Verwaltungswissen und geht nur an Admin-Rollen und an root
  selbst. Alle anderen bekommen ``ist_root: false`` und keinen Namen.
* ``root_uebertragen``: ausschliesslich der eingetragene root selbst. Es gibt
  absichtlich KEINEN Weg fuer einen System Manager, root zu uebernehmen oder
  zu setzen — sonst waere der Schutz aus Punkt 3 wertlos.

Bestaetigung und Passwort
-------------------------
Die Uebertragung verlangt ``bestaetigt=true`` UND das Passwort von Root. Das
Passwort schuetzt gegen eine fremde, bereits offene Sitzung (geteiltes
Geraet); es wird ueber ``frappe_compat.passwoerter`` geprueft, nie geloggt.
Die neue root-Person muss ein AKTIVES Konto mit Rolle ``System Manager`` sein
— root an ein einfaches Mitglied zu geben waere eine Rechteausweitung durch
die Hintertuer.
"""

from __future__ import annotations

from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
    DoesNotExistError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
)
from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.session import session

__all__ = ["status", "root_uebertragen", "_ist_system_manager"]


def _aktueller_user() -> str:
    user = str(session.user or "").strip()
    if not user or user == "Guest":
        throw("Anmeldung verweigert.", FrappePermissionError)
    return user


def _ist_system_manager(user: str) -> bool:
    """Traegt ``user`` die Rolle ``System Manager``? (Ziel der Uebertragung.)"""
    return "System Manager" in get_roles(user)


def _ist_admin(user: str) -> bool:
    from diakronos_app.frappe_compat.permissions import ADMIN_ROLES

    rollen = set(get_roles(user))
    return bool(rollen & set(ADMIN_ROLES))


@whitelist(allow_guest=False)
def status():
    """Wer ist root — und bin ich es?

    Liefert ``{root: <Name|None>, ist_root: bool}``. Der NAME des root ist
    Verwaltungswissen: nur Admin-Rollen und root selbst sehen ihn. Alle anderen
    bekommen ``root: None`` — die Antwort verraet damit nicht, wer der
    maechtigste Benutzer der Gemeinde ist (dieselbe Ueberlegung wie bei
    ``kuerze_name`` in den Kontenlisten).
    """
    from diakronos_app import root_benutzer

    user = _aktueller_user()
    bin_root = root_benutzer.ist_root(user)
    zeige_namen = bin_root or _ist_admin(user)
    return {
        "root": root_benutzer.root_name() if zeige_namen else None,
        "ist_root": bin_root,
    }


@whitelist(methods=["POST"], allow_guest=False)
def root_uebertragen(konto: str, passwort: str = "", bestaetigt: Any = False,
                     request=None) -> dict[str, Any]:
    """Uebergibt root an ``konto`` — nur root selbst, mit Passwort und Bestaetigung.

    Reihenfolge der Pruefungen (jede einzeln begruendet):

    1. Aufrufer ist der eingetragene root (sonst 403 mit generischer Meldung —
       ein Nicht-Root erfaehrt nicht, wer root ist).
    2. Bestaetigung gesetzt (dieselbe Form wie ``loeschung_beantragen``).
    3. Passwort von root stimmt (gegen ``user.password_hash``).
    4. Ziel existiert, ist aktiv (``enabled``) und traegt ``System Manager``.

    Danach in EINER Transaktion: Eintrag umschreiben, Ziel bekommt die
    Kennrolle, alter root verliert sie. Die eigene Sitzung von root bleibt
    bestehen — sie ist nach der Uebertragung eine gewoehnliche Admin-Sitzung.
    """
    from diakronos_app import root_benutzer
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.benutzer_status import vergiss
    from diakronos_app.frappe_compat.passwoerter import pruefe
    from diakronos_app.models.core import User

    user = _aktueller_user()
    if not root_benutzer.ist_root(user):
        throw(
            "Nur der Root-Benutzer darf die Root-Rechte übertragen.",
            FrappePermissionError,
        )

    ziel = str(konto or "").strip()
    if not ziel:
        raise ValidationError("Bitte das Konto angeben, das Root werden soll.")
    if ziel == user:
        raise ValidationError("Dieses Konto ist bereits Root.")
    wert = bestaetigt
    if isinstance(wert, str):
        wert = wert.strip().lower() in ("true", "1", "yes")
    if wert is not True:
        raise ValidationError("Bitte die Übertragung der Root-Rechte bestätigen.")
    if not str(passwort or ""):
        raise ValidationError("Bitte das eigene Passwort zur Bestätigung angeben.")

    with SessionLocal() as sess:
        # ON-6b: Pruefung UND Wechsel in EINER Transaktion, die die
        # Gemeinde-Zeile sperrt (`with_for_update`). Ohne die Sperre konnten
        # zwei parallele Aufrufe beide „root ist noch ich“ sehen und danach
        # nacheinander schreiben — der zweite haette einen zweiten Marker
        # gesetzt (zwei Zeilen in `gruppen_root_user`) bzw. den ersten
        # ueberschrieben, je nach Reihenfolge der Commits.
        #
        # Die Sperre liegt auf der Zeile, die die Wahrheit traegt
        # (`gemeinde_einstellungen.root_benutzer`) — dieselbe, die
        # `root_benutzer.markiere`/`entferne` schreiben. SQLite kennt kein
        # `FOR UPDATE`; dort ist die Sperre wirkungslos und wird vom Dialekt
        # still ignoriert — im Betrieb (PostgreSQL) greift sie.
        from sqlalchemy import select

        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        zeile = sess.execute(
            select(GemeindeEinstellungen)
            .where(GemeindeEinstellungen.name == GEMEINDE_EINSTELLUNGEN_NAME)
            .with_for_update()
        ).scalar_one_or_none()
        if zeile is None or not root_benutzer.ist_root_in(sess, user):
            # Fail closed: ohne Zeile gibt es keinen root — dann darf auch
            # niemand uebertragen. Dieselbe Meldung wie oben (kein Orakel).
            throw(
                "Nur der Root-Benutzer darf die Root-Rechte übertragen.",
                FrappePermissionError,
            )

        alt = sess.get(User, user)
        if alt is None:
            throw("Anmeldung verweigert.", FrappePermissionError)
        if not pruefe(str(passwort), alt.password_hash or ""):
            # Gleiche Meldung wie ein fehlendes Ziel: kein Orakel, das ein
            # fremdes Passwort bestaetigt oder verneint.
            throw("Das Passwort stimmt nicht.", FrappePermissionError)
        neu = sess.get(User, ziel)
        if neu is None:
            raise DoesNotExistError("Benutzerkonto nicht gefunden.")
        if not bool(neu.enabled):
            raise ValidationError(
                "Das Konto ist gesperrt. Bitte zuerst freischalten."
            )
        if not _ist_system_manager(ziel):
            raise ValidationError(
                "Root kann nur an ein Konto mit der Rolle „System Manager“ "
                "übergeben werden."
            )
        # `markiere` schreibt Eintrag UND Kennrolle; `entferne` nimmt dem alten
        # root beides in derselben Transaktion (kein Zwischenstand mit zwei
        # Markern). Der Commit am Ende gibt die Sperre frei.
        root_benutzer.entferne(sess, user)
        root_benutzer.markiere(sess, ziel)
        sess.commit()

    # Der Status-Cache haelt „existiert und enabled“ je Konto — die Rollen
    # selbst werden NICHT gecacht, aber ein frisch eingetragener root soll
    # sofort ohne Cache-Frist wirken (wie `konto_sperren` es macht).
    vergiss(user)
    vergiss(ziel)
    return {"ok": True, "root": ziel}
